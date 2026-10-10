#!/usr/bin/env python3
"""Search and invoke menu items of the focused application, over AT-SPI.

Adapted from MaNi4's omarchy-search-menu-items (MIT License):
https://github.com/MaNi4/omarchy-search-menu-items

Scope of this port: the menu-bar walk — finding the frame, fetching the
tree a level at a time, collecting items, invoking DoAction. Deliberately
deferred: the button fallback, the org.gtk.Actions export, multi-frame
title disambiguation, and the Chromium accessibility-flag prompter.

The focused app resolves from Hyprland (hyprctl activewindow -j). Walks are
cached per window for CACHE_TTL seconds, because walking a whole tree per
keystroke would waste the launcher's latency budget.

Requires: python-gobject (gi), hyprctl in PATH, AT-SPI enabled.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from functools import partial
from typing import Callable, NamedTuple

from gi.repository import Gio, GLib

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
READ_BUDGET = 2.0  # seconds per walk
CALL_TIMEOUT = 1500  # milliseconds per batched round
CACHE_TTL = 4.0  # seconds before a window's menu tree is walked again

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

    def __init__(self, connection: Gio.DBusConnection, timeout: int = CALL_TIMEOUT):
        self.connection = connection
        self.timeout = timeout
        self.loop = GLib.MainLoop()
        self.pending = 0

    def call(self, ref: Ref, interface: str, method: str, arguments: GLib.Variant | None,
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


def accessibility_bus(session: Gio.DBusConnection) -> Gio.DBusConnection:
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


def walk_items(a11y: Gio.DBusConnection, pid: int, title: str) -> list[Item]:
    batch = Batch(a11y)
    frames, _ = app_frames(batch, pid)
    frame = choose_frame(frames, title)
    if frame is None:
        return []
    tree = Tree(batch)
    menubar = find_menubar(tree, frame, frames[frame], time.monotonic() + READ_BUDGET)
    if menubar is None:
        return []
    return collect_items(tree, menubar, time.monotonic() + READ_BUDGET)


def press(a11y: Gio.DBusConnection, ref: Ref) -> None:
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


def main() -> None:
    session = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    a11y = accessibility_bus(session)
    cache: dict = {}  # key: window address -> {"at": float, "pid": int, "items": list[Item]}

    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        op = msg.get("op")
        if op == "search":
            query = str(msg.get("query", "")).strip().lower()
            window = focused_window()
            items: list[Item] = []
            if window:
                key = window["address"]
                cached = cache.get(key)
                if cached and time.monotonic() - cached["at"] < CACHE_TTL:
                    items = cached["items"]
                else:
                    try:
                        items = walk_items(a11y, int(window["pid"]), str(window.get("title", "")))
                        cache[key] = {"at": time.monotonic(), "pid": int(window["pid"]), "items": items}
                    except Exception as err:
                        log(f"walk failed: {err}")
            results = [
                {
                    "id": f"menus:{i}",
                    "title": item.label,
                    "subtitle": " \u203a ".join(item.path) + (f"  ({item.key})" if item.key else ""),
                    "icon": "system-run",
                    "score": s,
                    "provider": "menus",
                    "actions": [{"type": "custom", "kind": "press", "id": i}] if item.enabled else [],
                }
                for i, item in enumerate(items)
                for s in [score(query, item)]
                if s > 0.0
            ][:12]
            print(json.dumps({"id": msg.get("id", ""), "results": results}), flush=True)

        elif op == "execute":
            action = msg.get("action") or {}
            window = focused_window()
            ok = False
            if window and action.get("kind") == "press":
                cached = cache.get(window["address"])
                if cached:
                    index = action.get("id")
                    if isinstance(index, int) and 0 <= index < len(cached["items"]):
                        press(a11y, cached["items"][index].ref)
                        ok = True
            print(json.dumps({"id": msg.get("id", ""), "executed": ok}), flush=True)

        elif op == "cancel":
            print(json.dumps({"id": msg.get("target", ""), "cancelled": True}), flush=True)


if __name__ == "__main__":
    main()
