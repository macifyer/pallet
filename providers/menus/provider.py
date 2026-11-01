#!/usr/bin/env python3
"""Search and invoke menu items of the focused application, over AT-SPI.

Adapted from MaNi4's omarchy-search-menu-items (MIT License):
https://github.com/MaNi4/omarchy-search-menu-items

Scope of this port: the menu-bar walk — finding the frame, fetching the
tree a level at a time, collecting items, invoking DoAction. Deliberately
deferred: the button fallback, the org.gtk.Actions export, multi-frame
title disambiguation, and the Chromium accessibility-flag prompter.

The focused app resolves from Hyprland (hyprctl activewindow -j).

Latency model (cache-first, never blocking stdin):
- Walks run on one worker thread with a total time budget (WALK_BUDGET).
- A search for a window with a cached tree answers immediately from the
  cache; a cache older than CACHE_TTL is re-walked in the background
  (stale-while-revalidate).
- A search for a window with no cache queues a walk and answers when it
  finishes, unless the query was cancelled or superseded first.
- The host's `warm` op (overlay opened) starts the walk before the first
  keystroke, so the cache is usually ready by the time you type.
- Without python-gobject or an accessibility bus the provider stays up and
  answers every search with no results instead of crashing.

Requires: python-gobject (gi), hyprctl in PATH, AT-SPI enabled.
"""

from __future__ import annotations

import hashlib
import json
import queue
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from functools import partial
from typing import Callable, NamedTuple

try:  # Optional: without gi the provider answers with no results.
    from gi.repository import Gio, GLib
except Exception:  # ImportError, ValueError (namespace version), ...
    Gio = GLib = None

ACCESSIBLE = "org.a11y.atspi.Accessible"
ACTION = "org.a11y.atspi.Action"
APPLICATION = "org.a11y.atspi.Application"
PROPERTIES = "org.freedesktop.DBus.Properties"

# AT-SPI role and state numbers (atspi-constants.h).
MENU, MENU_BAR, POPUP_MENU = 33, 34, 41
ITEM_ROLES = {8, 35, 45}  # check menu item, menu item, radio menu item
CONTENT_ROLES = {60, 82, 92, 93, 94, 95, 96}  # terminal and document roles
ACTIVE, CHECKED, ENABLED, SENSITIVE = 1, 4, 8, 24

MAX_DEPTH = 12
MAX_NODES = 6000
WALK_BUDGET = 1.2  # seconds for a whole walk (frame search + menu tree)
CALL_TIMEOUT = 800  # milliseconds per batched round
CACHE_TTL = 8.0  # seconds before a cached tree is re-walked in the background
CACHE_MAX = 16  # windows kept
FOCUS_TTL = 0.75  # seconds a hyprctl focus lookup is reused
MAX_RESULTS = 12

EXPECTED_ERRORS = {
    "org.freedesktop.DBus.Error.UnknownMethod",
    "org.freedesktop.DBus.Error.UnknownInterface",
    "org.freedesktop.DBus.Error.UnknownObject",
}

MODIFIERS = {
    "<Primary>": "Ctrl+",
    "<Control>": "Ctrl+",
    "<Ctrl>": "Ctrl+",
    "<Shift>": "Shift+",
    "<Alt>": "Alt+",
    "<Super>": "Super+",
    "<Meta>": "Meta+",
}
MODIFIER_ORDER = ["Super", "Meta", "Ctrl", "Alt", "Shift"]


class Ref(NamedTuple):
    """Where an object lives on the accessibility bus."""
    bus: str
    path: str


DBUS = Ref("org.freedesktop.DBus", "/org/freedesktop/DBus")
REGISTRY = Ref("org.a11y.atspi.Registry", "/org/a11y/atspi/accessible/root")


@dataclass
class Node:
    children: list[Ref] = field(default_factory=list)
    role: int = -1
    state: int = 0
    name: str = ""
    key: str = ""
    actions: int = 0

    def has(self, state: int) -> bool:
        return bool(self.state >> state & 1)

    @property
    def label(self) -> str:
        return clean(self.name)

    @property
    def usable(self) -> bool:
        return self.actions > 0 and (self.has(ENABLED) or self.has(SENSITIVE))


@dataclass
class Item:
    path: list[str]
    label: str
    key: str
    enabled: bool
    checked: bool
    ref: Ref


def clean(text: str) -> str:
    text = " ".join((text or "").replace("\t", " ").split())
    return text if len(text) <= 70 else text[:69].rstrip() + "\u2026"


def shortcut(binding: str) -> str:
    """'Ctrl+Shift+S' from the toolkit's spelling: GTK gives
    'mnemonic;path;accelerator', Qt the accelerator alone."""
    binding = binding or ""
    accelerator = binding.split(";")[-1]
    # A bare Alt+letter is an in-menu mnemonic, not a real shortcut.
    if not accelerator or (";" not in binding and re.fullmatch(r"Alt\+.", accelerator)):
        return ""
    for token, name in MODIFIERS.items():
        accelerator = accelerator.replace(token, name)
    if accelerator.endswith("+"):  # the key is "+" itself
        held = [part for part in accelerator[:-1].split("+") if part]
        key = "+"
    else:
        *held, key = accelerator.split("+")
    held.sort(key=lambda n: MODIFIER_ORDER.index(n) if n in MODIFIER_ORDER else len(MODIFIER_ORDER))
    return "+".join(held + [key.upper() if len(key) == 1 else key.capitalize()])


def focused_window() -> dict | None:
    try:
        out = subprocess.run(
            ["hyprctl", "activewindow", "-j"],
            capture_output=True, text=True, timeout=3,
        ).stdout
        data = json.loads(out)
        if isinstance(data, dict) and data.get("address"):
            return data
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return None


class Batch:
    """Sends many calls on one connection and waits for all answers."""

    def __init__(self, connection, timeout: int = CALL_TIMEOUT):
        self.connection = connection
        self.timeout = timeout
        self.loop = GLib.MainLoop()
        self.pending = 0

    def call(self, ref: Ref, interface: str, method: str, arguments,
             done: Callable[[tuple | None], None]) -> None:
        self.pending += 1

        def finished(connection, result):
            try:
                reply = connection.call_finish(result).unpack()
            except GLib.Error as error:
                remote = Gio.DBusError.get_remote_error(error) or ""
                if remote not in EXPECTED_ERRORS:
                    log(f"{interface}.{method} on {ref.bus}: {error.message}")
                reply = None
            done(reply)
            self.pending -= 1
            if self.pending == 0:
                self.loop.quit()

        self.connection.call(
            ref.bus, ref.path, interface, method, arguments, None,
            Gio.DBusCallFlags.NONE, self.timeout, None, finished,
        )

    def wait(self) -> None:
        if self.pending:
            self.loop.run()


def accessibility_bus(session):
    address = session.call_sync(
        "org.a11y.Bus", "/org/a11y/bus", "org.a11y.Bus", "GetAddress",
        None, GLib.VariantType("(s)"), Gio.DBusCallFlags.NONE, 1000, None,
    ).unpack()[0]
    return Gio.DBusConnection.new_for_address_sync(
        address,
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None, None,
    )


class Tree:
    """The accessibility tree of one app, fetched a level at a time."""

    def __init__(self, batch: Batch):
        self.batch = batch

    def fetch(self, refs: list[Ref], *, children: bool = False, role: bool = False,
              state: bool = False, name: bool = False, actions: bool = False) -> dict[Ref, Node]:
        nodes = {ref: Node() for ref in refs}
        call = self.batch.call
        for ref, node in nodes.items():
            if children:
                call(ref, ACCESSIBLE, "GetChildren", None, partial(_set_children, node))
            if role:
                call(ref, ACCESSIBLE, "GetRole", None, partial(_set_role, node))
            if state:
                call(ref, ACCESSIBLE, "GetState", None, partial(_set_state, node))
            if name:
                call(ref, PROPERTIES, "Get",
                     GLib.Variant("(ss)", (ACCESSIBLE, "Name")), partial(_set_name, node))
            if actions:
                call(ref, ACTION, "GetActions", None, partial(_set_actions, node))
        self.batch.wait()
        return nodes


def _set_children(node: Node, reply: tuple | None) -> None:
    if reply is not None:
        node.children = [Ref(*child) for child in reply[0]]


def _set_role(node: Node, reply: tuple | None) -> None:
    if reply is not None:
        node.role = reply[0]


def _set_state(node: Node, reply: tuple | None) -> None:
    if reply is not None:
        low, high = reply[0]
        node.state = low | high << 32


def _set_name(node: Node, reply: tuple | None) -> None:
    if reply is not None:
        node.name = reply[0]


def _set_actions(node: Node, reply: tuple | None) -> None:
    if reply is not None:
        entries = reply[0]
        node.actions = len(entries)
        if entries and not node.key:
            node.key = entries[0][2]


def owners(batch: Batch, names: list[str], pid: int) -> list[str]:
    """The bus names that belong to the process."""
    owned: list[str] = []

    def keep(name: str, reply: tuple | None) -> None:
        if reply and reply[0] == pid:
            owned.append(name)

    for name in names:
        batch.call(DBUS, DBUS.bus, "GetConnectionUnixProcessID",
                   GLib.Variant("(s)", (name,)), partial(keep, name))
    batch.wait()
    return owned


def app_frames(batch: Batch, pid: int) -> tuple[dict[Ref, Node], dict[Ref, Node]]:
    """The root node map and this app's windows."""
    tree = Tree(batch)
    apps = tree.fetch([REGISTRY], children=True)[REGISTRY].children
    by_bus = {ref.bus: ref for ref in apps}
    own = [by_bus[bus] for bus in owners(batch, list(by_bus), pid)]
    frames = [frame for node in tree.fetch(own, children=True).values() for frame in node.children]
    return tree.fetch(frames, children=True, role=True, state=True, name=True), frames


def choose_frame(frames: dict[Ref, Node], title: str) -> Ref | None:
    active = [ref for ref, node in frames.items() if node.has(ACTIVE)]
    if active:
        return active[0]
    titled = [ref for ref, node in frames.items() if title and node.name == title]
    return titled[0] if titled else (next(iter(frames), None))


def find_menubar(tree: Tree, frame: Ref, root_node: Node, deadline: float) -> Ref | None:
    level = [(frame, root_node)]
    for _ in range(10):
        below: list[Ref] = []
        for ref, node in level:
            if node.role == MENU_BAR:
                return ref
            if node.role not in CONTENT_ROLES:
                below.extend(node.children)
        if not below or time.monotonic() > deadline:
            return None
        level = list(tree.fetch(below[:MAX_NODES], children=True, role=True).items())
    return None


def menu_items(nodes: dict[Ref, Node], menu: Ref, path: tuple[str, ...] = ()):
    for child in nodes[menu].children:
        node = nodes.get(child)
        if node is None:
            continue
        if node.role == POPUP_MENU:
            yield from menu_items(nodes, child, path)
        elif node.role == MENU or (node.role in ITEM_ROLES and node.children):
            if node.label:
                yield from menu_items(nodes, child, path + (node.label,))
        elif node.role in ITEM_ROLES and node.label:
            yield list(path), child, node


def collect_items(tree: Tree, menubar: Ref, deadline: float) -> list[Item]:
    nodes = tree.fetch([menubar], children=True)
    level = nodes[menubar].children
    depth = 0
    while level and depth <= MAX_DEPTH and len(nodes) < MAX_NODES and time.monotonic() < deadline:
        fetched = tree.fetch(level, children=True, role=True, state=True, name=True, actions=True)
        nodes.update(fetched)
        level = [child for ref in level for child in fetched[ref].children if child not in nodes]
        depth += 1
    return [
        Item(list(path), node.label, shortcut(node.key), node.usable, node.has(CHECKED), ref)
        for path, ref, node in menu_items(nodes, menubar)
    ]


def walk_items(a11y, pid: int, title: str) -> list[Item]:
    deadline = time.monotonic() + WALK_BUDGET
    batch = Batch(a11y)
    frames, _ = app_frames(batch, pid)
    frame = choose_frame(frames, title)
    if frame is None or time.monotonic() > deadline:
        return []
    tree = Tree(batch)
    menubar = find_menubar(tree, frame, frames[frame], deadline)
    if menubar is None:
        return []
    return collect_items(tree, menubar, deadline)


def press(a11y, ref: Ref) -> None:
    a11y.call_sync(
        ref.bus, ref.path, ACTION, "DoAction",
        GLib.Variant("(i)", (0,)), None, Gio.DBusCallFlags.NONE, 2000, None,
    )


def score(query: str, item: Item) -> float:
    """Kept deliberately below the apps provider's range: menu items should
    augment the list, not elbow their way past your apps."""
    label = item.label.lower()
    crumb = " ".join(item.path).lower()
    if label.startswith(query):
        return 0.50
    if any(word.startswith(query) for word in label.split()):
        return 0.45
    if query in label:
        return 0.40
    if query in crumb or query in (crumb + " " + label):
        return 0.33
    return 0.0


def log(*args: object) -> None:
    print("menus:", *args, file=sys.stderr, flush=True)


def item_id(address: str, item: Item) -> str:
    digest = hashlib.sha1("\u0000".join([address, *item.path, item.label]).encode()).hexdigest()[:12]
    return f"menus:{digest}"


def results_for(query: str, address: str, items: list[Item]) -> list[dict]:
    scored = [(score(query, item), i, item) for i, item in enumerate(items)]
    scored = sorted((t for t in scored if t[0] > 0.0), key=lambda t: (-t[0], t[1]))[:MAX_RESULTS]
    return [
        {
            "id": item_id(address, item),
            "title": item.label,
            "subtitle": " \u203a ".join(item.path) + (f"  ({item.key})" if item.key else ""),
            "icon": "system-run",
            "score": s,
            "provider": "menus",
            # The action names the item by path + label so a re-walk between
            # search and Enter can never press a different item.
            "actions": [{"type": "custom", "kind": "press", "id": i, "window": address,
                         "path": list(item.path), "label": item.label}] if item.enabled else [],
        }
        for s, i, item in scored
    ]


class MenuService:
    """Cache-first menu search with walks on a worker thread.

    `walker(window) -> list[Item]` and `focus() -> dict | None` are injected
    so the scheduling logic is testable without AT-SPI.
    """

    def __init__(self, walker, focus, send, pressor=None):
        self.walker, self.focus_lookup, self.send, self.pressor = walker, focus, send, pressor
        self.cache: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.jobs: "queue.Queue[dict | None]" = queue.Queue()
        self.walking: set[str] = set()
        self.waiting: dict[str, tuple[str, str]] = {}  # qid -> (address, query)
        self.focus_cache: tuple[float, dict | None] = (0.0, None)
        self.worker = threading.Thread(target=self._work, name="menus-walk", daemon=True)
        self.worker.start()

    def focus(self, fresh: bool = False) -> dict | None:
        at, window = self.focus_cache
        if fresh or time.monotonic() - at > FOCUS_TTL:
            window = self.focus_lookup()
            self.focus_cache = (time.monotonic(), window)
        return window

    def schedule(self, window: dict) -> None:
        address = str(window.get("address", ""))
        with self.lock:
            if address in self.walking:
                return
            self.walking.add(address)
        self.jobs.put(window)

    def _work(self) -> None:
        while True:
            window = self.jobs.get()
            if window is None:
                return
            address = str(window.get("address", ""))
            try:
                items = self.walker(window)
            except Exception as err:  # never let one app kill the worker
                log(f"walk failed: {err}")
                items = None
            with self.lock:
                self.walking.discard(address)
                if items is not None:
                    self.cache[address] = {"at": time.monotonic(), "items": items}
                    while len(self.cache) > CACHE_MAX:
                        oldest = min(self.cache, key=lambda k: self.cache[k]["at"])
                        del self.cache[oldest]
                ready = [(qid, q) for qid, (addr, q) in self.waiting.items() if addr == address]
                for qid, _ in ready:
                    del self.waiting[qid]
                cached = self.cache.get(address)
            for qid, q in ready:
                self.send({"id": qid, "results": results_for(q, address, cached["items"]) if cached else []})

    def warm(self) -> None:
        window = self.focus(fresh=True)
        if window is None:
            return
        cached = self.cache.get(str(window.get("address", "")))
        if cached is None or time.monotonic() - cached["at"] > CACHE_TTL:
            self.schedule(window)

    def search(self, qid: str, query: str) -> None:
        query = query.strip().lower()
        window = self.focus()
        if window is None or not query:
            self.send({"id": qid, "results": []}); return
        address = str(window.get("address", ""))
        with self.lock:
            cached = self.cache.get(address)
            if cached is None:
                # Only the newest query waits for a walk.
                self.waiting = {k: v for k, v in self.waiting.items() if v[0] != address}
                self.waiting[qid] = (address, query)
        if cached is None:
            self.schedule(window)
            return
        self.send({"id": qid, "results": results_for(query, address, cached["items"])})
        if time.monotonic() - cached["at"] > CACHE_TTL:
            self.schedule(window)

    def cancel(self, target: str) -> None:
        with self.lock:
            self.waiting.pop(target, None)
        self.send({"id": target, "cancelled": True})

    def find(self, action: dict) -> Item | None:
        address = str(action.get("window", ""))
        with self.lock:
            cached = self.cache.get(address)
        if cached is None:
            return None
        items = cached["items"]
        path, label = action.get("path"), action.get("label")
        index = action.get("id")
        if isinstance(index, int) and 0 <= index < len(items):
            item = items[index]
            if item.label == label and item.path == path:
                return item
        for item in items:
            if item.label == label and item.path == path:
                return item
        return None

    def execute(self, aid: str, action: dict) -> None:
        ok, error = False, ""
        window = self.focus(fresh=True)
        if action.get("kind") != "press":
            error = "unsupported action"
        elif window is None or str(window.get("address", "")) != str(action.get("window", "")):
            error = "the window that owned this menu item is no longer focused"
        else:
            item = self.find(action)
            if item is None:
                error = "menu item is gone"
            elif self.pressor is None:
                error = "accessibility bus unavailable"
            else:
                try:
                    self.pressor(item.ref); ok = True
                except Exception as err:
                    error = f"could not press menu item: {err}"
        reply = {"id": aid, "executed": ok}
        if error:
            reply["error"] = error
        self.send(reply)


_out_lock = threading.Lock()


def send(msg: dict) -> None:
    with _out_lock:
        print(json.dumps(msg), flush=True)


def connect():
    """The accessibility bus connection, or None (logged once)."""
    if Gio is None:
        log("python-gobject (gi) not available; menu search disabled")
        return None
    try:
        return accessibility_bus(Gio.bus_get_sync(Gio.BusType.SESSION, None))
    except Exception as err:
        log(f"accessibility bus unavailable: {err}")
        return None


def main() -> None:
    a11y = connect()
    if a11y is None:
        walker = lambda window: []
        pressor = None
    else:
        walker = lambda window: walk_items(a11y, int(window["pid"]), str(window.get("title", "")))
        pressor = lambda ref: press(a11y, ref)
    service = MenuService(walker, focused_window, send, pressor)
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(msg, dict):
            continue
        op = msg.get("op")
        if op == "search":
            service.search(str(msg.get("id", "")), str(msg.get("query", "")))
        elif op == "warm":
            service.warm()
        elif op == "execute":
            action = msg.get("action")
            service.execute(str(msg.get("id", "")), action if isinstance(action, dict) else {})
        elif op == "cancel":
            service.cancel(str(msg.get("target", "")))


if __name__ == "__main__":
    main()
