#!/usr/bin/env python3
"""Omarchy menu parity: every entry of the installed Omarchy menu, searchable.

Source of truth is the menu definition Omarchy itself loads
(shell/plugins/menu/Menu.qml): `$OMARCHY_PATH/default/omarchy/omarchy-menu.jsonc`
overlaid per key by the user's `~/.config/omarchy/extensions/omarchy-menu.jsonc`
(same merge as MenuModel.mergeMenuSources). Nothing is vendored or invented:
if the file is missing, only the small curated panel list below is offered.

Running an entry never re-implements its command. Every row launches
`omarchy-menu summon <id>` as argv; the native menu resolves the id and runs
a leaf's action itself, or opens a submenu (bin/omarchy-menu,
Menu.qml openRoute). Search text never reaches a shell.

Guards (`when:` hides a row, `disabled:` marks installed software) are the
menu's own bash conditions. They are evaluated off the request path, in one
background bash batch built only from the trusted menu files - the same thing
the native menu does on every open (MenuModel.guardScript). Until a guarded
row's answer is known, it opens its parent submenu instead of running, so the
native menu applies the guard. `checked:` marks are not evaluated.

Destructive or system-state entries (power, remove, reset, updates, security,
DNS, channel, ...) carry `danger: confirm` so they need a second Enter.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

MAX_RESULTS = 15
GUARD_TTL_S = 30.0
GUARD_TIMEOUT_S = 8.0
GUARD_GROUPS = 8
BLUE = "#89b4fa"
GREEN = "#a6e3a1"
YELLOW = "#f9e2af"
PURPLE = "#cba6f7"
RED = "#f38ba8"


# ----------------------------------------------------------------- menu files

def omarchy_roots() -> list[Path]:
    roots = []
    env = os.environ.get("OMARCHY_PATH")
    if env:
        roots.append(Path(env))
    roots += [Path("/usr/share/omarchy"), Path.home() / ".local/share/omarchy"]
    return roots


def menu_paths() -> tuple[Path | None, Path]:
    default = next((r / "default/omarchy/omarchy-menu.jsonc" for r in omarchy_roots()
                    if (r / "default/omarchy/omarchy-menu.jsonc").is_file()), None)
    user = Path.home() / ".config/omarchy/extensions/omarchy-menu.jsonc"
    return default, user


def strip_jsonc(text: str) -> str:
    """Drop // and /* */ comments outside strings, then trailing commas."""
    out, i, n, in_string = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if c == '"':
                in_string = False
        elif c == '"':
            in_string = True; out.append(c)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        else:
            out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def _aliases(value) -> list[str]:
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str) and v]
    return [value] if isinstance(value, str) and value else []


def normalize(item_id: str, raw: dict) -> dict:
    parent = raw.get("parent")
    if not isinstance(parent, str):
        parent = item_id.rsplit(".", 1)[0] if "." in item_id else "root"
    text = lambda k: raw.get(k) if isinstance(raw.get(k), str) else ""
    return {
        "id": item_id, "parent": parent, "label": text("label") or item_id,
        "action": text("action"), "target": text("target"), "provider": text("provider"),
        "description": text("description"), "aliases": _aliases(raw.get("aliases")),
        "when": text("when"), "disabled": text("disabled"),
    }


def parse_menu(text: str) -> list[dict]:
    try:
        data = json.loads(strip_jsonc(text))
    except ValueError:
        return []
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("items"), dict):
        data = data["items"]
    return [normalize(k, v) for k, v in data.items() if isinstance(k, str) and isinstance(v, dict)]


def merge(defaults: list[dict], user: list[dict]) -> tuple[dict, list[str]]:
    items: dict[str, dict] = {}
    order: list[str] = []
    for source, raws in ((defaults, None), (user, None)):
        for entry in source:
            if entry["id"] not in items:
                order.append(entry["id"]); items[entry["id"]] = dict(entry)
            else:
                # Per-key overlay: only fields the user file declares win.
                declared = entry.get("_declared", entry.keys())
                items[entry["id"]].update({k: entry[k] for k in declared})
    return items, order


def parse_user(text: str) -> list[dict]:
    """Like parse_menu, but remember which fields were declared so an
    override that only retitles keeps the shipped action."""
    try:
        data = json.loads(strip_jsonc(text))
    except ValueError:
        return []
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("items"), dict):
        data = data["items"]
    out = []
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, dict):
            entry = normalize(k, v)
            entry["_declared"] = ["id"] + [f for f in v if f in entry]
            out.append(entry)
    return out


# ------------------------------------------------------------------ policies

# Destructive or system-state routes need a second Enter. Prefix match on ids.
CONFIRM = [
    ("system.suspend", "warning"), ("system.hibernate", "warning"), ("system.logout", "warning"),
    ("system.reboot", "warning"), ("system.shutdown", "danger"),
    ("remove.", "danger"), ("setup.reset", "danger"), ("setup.direct-boot", "warning"),
    ("setup.security.", "warning"), ("setup.network.dns.", "warning"), ("setup.plugin.remove", "danger"),
    ("update.omarchy", "positive"), ("update.channel.", "warning"), ("update.config.", "warning"),
    ("update.themes", "positive"), ("update.process.", "warning"), ("update.hardware.", "warning"),
    ("update.firmware", "warning"), ("update.password.", "warning"), ("update.time", "warning"),
    ("trigger.reminder.clear", "danger"), ("trigger.hardware.hybrid-gpu-", "warning"),
    ("appearance.branding.about.default", "warning"), ("appearance.branding.screensaver.default", "warning"),
    ("install.", "positive"),
]
# Pickers that only open an interactive chooser: nothing happens until you pick.
NO_CONFIRM = {"install.package", "install.aur", "install.webapp", "install.tui", "update.timezone"}

# Extra words people type for an entry, beyond its labels/ids/aliases.
KEYWORDS = {
    "system.shutdown": "shut down power off halt",
    "system.reboot": "restart",
    "system.logout": "log out sign out exit session",
    "system.suspend": "sleep",
    "system.lock": "lock screen",
    "trigger.toggle.idle-lock-on": "caffeine stay awake idle",
    "trigger.toggle.idle-lock-off": "caffeine stay awake idle",
    "trigger.toggle.notifications-off": "dnd do not disturb mute silence",
    "trigger.toggle.notifications-on": "dnd do not disturb unmute",
    "trigger.capture.color": "color picker hyprpicker eyedropper",
    "trigger.capture.text": "ocr text recognition",
    "trigger.share.receive": "localsend",
    "appearance.background": "wallpaper background",
    "learn.omarchy": "manual docs documentation help",
}
CONFIRM_DETAIL = "Runs Omarchy's own menu command: {cmd}"


def confirm_for(item_id: str) -> str:
    if item_id in NO_CONFIRM:
        return ""
    for prefix, tone in CONFIRM:
        if item_id == prefix or (prefix.endswith((".", "-")) and item_id.startswith(prefix)):
            return tone
    return ""


def display_title(items: dict, entry: dict) -> str:
    label = entry["label"]
    parts = entry["id"].split(".")
    root = items.get(parts[0], {}).get("label", parts[0].title())
    parent = items.get(entry["parent"], {})
    if parts[0] in ("install", "remove") and len(parts) > 1:
        return label if label.lower().startswith(root.lower()) else f"{root} {label}"
    if parts[0] == "update" and len(parts) == 2:
        return f"Update {label}"
    if parts[0] == "update" and len(parts) > 2:
        return f"Update {parent.get('label', '')}: {label}"
    if entry["id"].startswith("setup.default.") and len(parts) == 4:
        return f"Default {parent.get('label', '')}: {label}"
    if entry["id"].startswith("setup.network.dns.") and len(parts) == 4:
        return f"DNS: {label}"
    return label


# ------------------------------------------------------------------- guards

PKG_SNAPSHOT = (
    "declare -A __pallet_pkgs=()\n"
    "while IFS= read -r __p; do __pallet_pkgs[$__p]=1; done < <({ pacman -Qq; LC_ALL=C pacman -Qi"
    " | awk '/^[A-Za-z]/ { provides = ($0 ~ /^Provides/); sub(/^[^:]*: /, \"\") }"
    " provides && $0 != \"None\" { n = split($0, p, \" \"); for (i = 1; i <= n; i++) { sub(/[<>=].*/, \"\", p[i]); print p[i] } }'; } 2>/dev/null)\n"
    "__pallet_pkg_has() { [[ -n ${__pallet_pkgs[$1]-} ]] && return 0; [[ $1 == *[\\<\\>=]* ]] && { pacman -Q \"$1\" &>/dev/null; return; }; return 1; }\n"
    "omarchy-pkg-present() { local p; for p in \"$@\"; do __pallet_pkg_has \"$p\" || return 1; done; return 0; }\n"
    "omarchy-pkg-missing() { local p; for p in \"$@\"; do __pallet_pkg_has \"$p\" || return 0; done; return 1; }\n"
    "omarchy-cmd-present() { local c; for c in \"$@\"; do command -v \"$c\" &>/dev/null || return 1; done; return 0; }\n"
    "omarchy-cmd-missing() { local c; for c in \"$@\"; do command -v \"$c\" &>/dev/null || return 0; done; return 1; }\n"
)


def guard_script(guards: list[tuple[int, str, str]]) -> str:
    """One bash script for the given (index, tag, condition) guards, printing
    `<index>:<tag>:<0|1>` per guard; a port of MenuModel.guardScript. The
    conditions come only from the trusted menu files, never from search text."""
    if not guards:
        return ""
    groups = [""] * min(GUARD_GROUPS, len(guards))
    for n, (index, tag, cond) in enumerate(guards):
        line = (f"if {{ {cond}\n}} >/dev/null 2>&1 </dev/null; then echo {index}:{tag}:1; "
                f"else echo {index}:{tag}:0; fi\n")
        groups[n % len(groups)] += line
    body = "".join("{\n" + g + "} &\n" for g in groups)
    return PKG_SNAPSHOT + body + "wait\n"


def run_guards(guards: list[tuple[int, str, str]], timeout: float = GUARD_TIMEOUT_S) -> dict[tuple[int, str], bool]:
    script = guard_script(guards)
    if not script:
        return {}
    try:
        proc = subprocess.Popen(["bash", "-c", script], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    except OSError as err:
        log(f"guards: cannot run bash: {err}")
        return {}
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        with_suppress(lambda: os.killpg(proc.pid, signal.SIGKILL))
        out, _ = proc.communicate()
        log("guards: timed out; unanswered rows open their parent menu")
    answers = {}
    for line in out.splitlines():
        m = re.fullmatch(r"(\d+):([wd]):([01])", line.strip())
        if m:
            answers[(int(m.group(1)), m.group(2))] = m.group(3) == "1"
    return answers


def with_suppress(fn) -> None:
    try:
        fn()
    except OSError:
        pass


# ------------------------------------------------------------ curated extras

def summon_panel(panel: str) -> list[str]:
    return ["omarchy-shell", "shell", "summon", panel]


# Bar panels and helpers the menu does not list as rows, each a real Omarchy
# command (see README for sources). Dropped automatically if the installed
# menu ever runs the identical command.
EXTRAS = [
    ("panel-network", "Network", "Wi-Fi and networking panel", "network-wireless", summon_panel("omarchy.network"), "wifi wi-fi internet ethernet wireless connection", "📶", BLUE),
    ("panel-bluetooth", "Bluetooth", "Bluetooth devices panel", "bluetooth-active", summon_panel("omarchy.bluetooth"), "bt devices pair", "🔵", BLUE),
    ("panel-audio", "Audio", "Volume and devices panel", "audio-volume-high", summon_panel("omarchy.audio"), "sound volume mic microphone speaker output input", "🔊", BLUE),
    ("panel-power", "Power", "Battery and power profiles panel", "battery-full", summon_panel("omarchy.power"), "battery charge profile laptop", "🔋", BLUE),
    ("panel-display", "Display", "Brightness slider and laptop display panel", "video-display", summon_panel("omarchy.monitor"), "brightness screen monitor laptop", "🖥", BLUE),
    ("panel-calendar", "Calendar", "Clock and calendar panel", "x-office-calendar", summon_panel("omarchy.clock"), "clock date month", "📅", BLUE),
    ("panel-world-clock", "World Clock", "Time in other zones (Elsewhen)", "preferences-system-time", summon_panel("omarchy.elsewhen"), "elsewhen timezone time zones", "🌍", BLUE),
    ("panel-tailscale", "Tailscale", "Tailscale panel", "network-vpn", summon_panel("omarchy.tailscale"), "vpn tailnet", "🛡", BLUE),
    ("panel-weather", "Weather", "Weather panel", "weather-few-clouds", summon_panel("omarchy.weather"), "forecast temperature", "⛅", BLUE),
    ("toggle-animations", "Toggle Animations", "Toggle Hyprland animations", "preferences-desktop-effects", ["omarchy-toggle-animations"], "animations effects motion", "✨", YELLOW),
    ("menu", "Omarchy Menu", "Open the native Omarchy menu", "application-menu", ["omarchy-menu", "toggle"], "menu native omarchy", "☰", BLUE),
]


# ------------------------------------------------------------------ catalog

class Catalog:
    """The parsed menu plus guard answers. Rebuilt when either file changes."""

    def __init__(self, paths=menu_paths, guards=run_guards):
        self.paths, self.guard_runner = paths, guards
        self.lock = threading.Lock()
        self.stamp: tuple = ()
        self.items: dict[str, dict] = {}
        self.order: list[str] = []
        self.rows: list[dict] = []
        self.guard_list: list[tuple[int, str, str]] = []
        self.answers: dict[tuple[int, str], bool] | None = None
        self.answers_at = 0.0
        self.guarding = False

    def _stamp(self) -> tuple:
        out = []
        for p in self.paths():
            try:
                st = p.stat() if p else None
                out.append((str(p), st.st_mtime_ns, st.st_size) if st else None)
            except OSError:
                out.append(None)
        return tuple(out)

    def refresh(self) -> bool:
        stamp = self._stamp()
        if stamp == self.stamp:
            return False
        default, user = self.paths()
        defaults = parse_menu(read(default)) if default else []
        users = parse_user(read(user)) if user else []
        items, order = merge(defaults, users)
        guards = []
        for n, item_id in enumerate(order):
            entry = items[item_id]
            entry["_n"] = n
            if entry["when"]:
                guards.append((n, "w", entry["when"]))
            if entry["disabled"]:
                guards.append((n, "d", entry["disabled"]))
        with self.lock:
            self.stamp, self.items, self.order, self.guard_list = stamp, items, order, guards
            self.answers, self.answers_at = None, 0.0
            self.rows = self._build_rows()
        return True

    def ensure_guards(self, block: bool = False) -> None:
        with self.lock:
            stale = self.answers is None or time.monotonic() - self.answers_at > GUARD_TTL_S
            if not stale or self.guarding or not self.guard_list:
                return
            self.guarding = True
            guards, stamp = list(self.guard_list), self.stamp
        def work():
            try:
                answers = self.guard_runner(guards)
            finally:
                with self.lock:
                    self.guarding = False
            with self.lock:
                if stamp == self.stamp:
                    self.answers, self.answers_at = answers, time.monotonic()
        if block:
            work()
        else:
            threading.Thread(target=work, name="omarchy-guards", daemon=True).start()

    # A row's guard state: True (passes), False (fails), None (unknown yet).
    def _answer(self, entry: dict, tag: str):
        if not entry[{"w": "when", "d": "disabled"}[tag]]:
            return True if tag == "w" else False
        if self.answers is None:
            return None
        return self.answers.get((entry["_n"], tag))

    def _visible(self, entry: dict):
        """False if this row or any ancestor is hidden by `when`; None if unknown."""
        unknown, seen = False, 0
        while entry and entry["id"] != "root" and seen < 16:
            ok = self._answer(entry, "w")
            if ok is False:
                return False
            unknown |= ok is None
            entry = self.items.get(entry["parent"]) if entry["parent"] not in ("", "root") else None
            seen += 1
        return None if unknown else True

    def _chain(self, entry: dict) -> list[dict] | None:
        chain, seen = [], 0
        while entry["parent"] not in ("", "root"):
            parent = self.items.get(entry["parent"])
            if parent is None or parent["action"] or seen > 16:
                return None  # orphan or under an action: not reachable in the native menu
            chain.insert(0, parent); entry = parent; seen += 1
        return chain

    def _build_rows(self) -> list[dict]:
        rows = []
        parents = {e["parent"] for e in self.items.values()}
        for item_id in self.order:
            entry = self.items[item_id]
            if item_id == "root" or entry["target"]:
                continue
            if not entry["action"] and not entry["provider"] and item_id not in parents:
                continue  # an empty submenu: nothing to open, nothing to run
            chain = self._chain(entry)
            if chain is None:
                continue
            crumbs = [c["label"] for c in chain]
            words = " ".join(crumbs + [entry["label"]] + item_id.replace("-", " ").split(".")
                             + entry["aliases"] + [entry["description"], KEYWORDS.get(item_id, "")])
            rows.append({"entry": entry, "title": display_title(self.items, entry), "crumbs": crumbs,
                         "keywords": " ".join(words.lower().split()),
                         "is_menu": not entry["action"]})
        return rows

    def snapshot(self):
        with self.lock:
            return self.rows, self.items, self.answers


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


# ------------------------------------------------------------------ search

def score(q: str, title: str, keywords: str, subtitle: str = "") -> float:
    t = title.lower()
    if t == q: return 0.95
    if t.startswith(q): return 0.92
    if any(w.startswith(q) for w in re.split(r"[\s:›/-]+", t)): return 0.82
    if q in t: return 0.7
    if keywords.startswith(q) or (" " + q) in (" " + keywords): return 0.62
    if q in keywords: return 0.52
    if q in subtitle.lower(): return 0.4
    return 0.0


def menu_result(catalog: Catalog, row: dict, s: float) -> dict | None:
    entry = row["entry"]
    visible = catalog._visible(entry)
    if visible is False:
        return None
    disabled = catalog._answer(entry, "d")
    crumb = " › ".join(["Omarchy", *row["crumbs"]])
    route, note = entry["id"], ""
    if visible is None or disabled is None:
        # Guard not answered yet: let the native menu apply it.
        route = entry["parent"] if entry["parent"] not in ("", "root") else "root"
        note = " · opens in the Omarchy menu"
    subtitle = crumb + ((" › " + entry["label"]) if row["is_menu"] else "")
    if row["is_menu"]:
        subtitle = "Open menu: " + subtitle
    actions: list[dict] = []
    parent_route = entry["parent"] if entry["parent"] not in ("", "root") else "root"
    if disabled is True:
        # Installed already: the native menu lists it disabled in its submenu.
        subtitle += " · ✓ installed"
        note = note or " · opens in the Omarchy menu"
        actions.append({"type": "launch", "title": "Open in Omarchy menu",
                        "argv": ["omarchy-menu", "summon", parent_route]})
    elif row["is_menu"] or note:
        # Submenus (and rows whose guard is not answered yet) open that place
        # in the real Omarchy menu: bin/omarchy-menu summon <route>.
        actions.append({"type": "launch", "title": "Open in Omarchy menu",
                        "argv": ["omarchy-menu", "summon", route]})
    else:
        # A leaf runs the menu's own action string, exactly as Menu.qml
        # runAction does (Util.execDetached: bash -lc <action>), detached.
        action = {"type": "shell", "title": "Run", "command": entry["action"]}
        tone = confirm_for(entry["id"])
        if tone:
            action.update({"danger": "confirm", "tone": tone, "confirmation": {
                "title": f"{row['title']}?", "detail": CONFIRM_DETAIL.format(cmd=entry["action"])}})
        actions.append(action)
    if entry["action"]:
        actions.append({"type": "copy", "title": "Copy command", "text": entry["action"]})
    return {"id": "omarchy:menu:" + entry["id"], "title": row["title"], "subtitle": subtitle + note,
            "icon": "omarchy", "icons": ["application-menu"], "fallbackIcon": "◆",
            "fallbackColor": RED if confirm_for(entry["id"]) == "danger" else PURPLE if row["is_menu"] else BLUE,
            "keywords": row["keywords"], "score": round(s * (0.85 if row["is_menu"] else 1.0), 3),
            "provider": "omarchy", "actions": actions}


BAR_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "omarchy" / "shell.json"
_bar_cache: dict = {"key": None, "ids": None}


def bar_widget_ids(path: Path = BAR_CONFIG) -> set[str] | None:
    """Plugin ids placed in the user's bar, or None when unknown. A bar-widget
    panel only opens through a live widget (shell.qml summon -> summonBarWidget
    returns false otherwise, silently), so panel rows for widgets that are not
    in the bar are hidden instead of doing nothing."""
    try:
        st = path.stat()
        key = (str(path), st.st_mtime_ns, st.st_size)
    except OSError:
        return None
    if _bar_cache["key"] == key:
        return _bar_cache["ids"]
    ids = None
    try:
        layout = json.loads(path.read_text(encoding="utf-8")).get("bar", {}).get("layout")
        if isinstance(layout, dict):
            ids = {str(w.get("id") if isinstance(w, dict) else w)
                   for section in layout.values() if isinstance(section, list) for w in section}
    except (OSError, ValueError, AttributeError):
        ids = None
    _bar_cache.update(key=key, ids=ids)
    return ids


def extras(menu_actions: set[str], bar_ids: set[str] | None = None) -> list[dict]:
    out = []
    for key, title, subtitle, icon, argv, words, glyph, color in EXTRAS:
        if " ".join(argv) in menu_actions:
            continue
        if key.startswith("panel-") and bar_ids is not None and argv[-1] not in bar_ids:
            continue
        out.append({"id": "omarchy:" + key, "title": title, "subtitle": subtitle, "icon": icon,
                    "fallbackIcon": glyph, "fallbackColor": color, "keywords": (title + " " + words).lower(),
                    "provider": "omarchy",
                    "actions": [{"type": "launch", "title": title, "argv": argv},
                                {"type": "copy", "title": "Copy command", "text": " ".join(argv)}]})
    return out


def search(catalog: Catalog, query: str) -> list[dict]:
    q = " ".join(query.strip().lower().split())
    if not q:
        return []
    rows, items, _ = catalog.snapshot()
    menu_actions = {e["action"] for e in items.values() if e["action"]}
    scored = []
    for n, row in enumerate(rows):
        s = score(q, row["title"], row["keywords"])
        if s > 0:
            scored.append((s * (0.85 if row["is_menu"] else 1.0), n, row))
    scored.sort(key=lambda t: (-t[0], t[1]))
    out = []
    for s, _, row in scored:
        if len(out) >= MAX_RESULTS:
            break
        result = menu_result(catalog, row, s / (0.85 if row["is_menu"] else 1.0))
        if result is not None:
            out.append(result)
    for x in extras(menu_actions, bar_widget_ids()):
        s = score(q, x["title"], x["keywords"], x["subtitle"])
        if s > 0:
            out.append(dict(x, score=s))
    out.sort(key=lambda r: -r["score"])
    return out[:MAX_RESULTS]


def log(*args) -> None:
    print("omarchy:", *args, file=sys.stderr, flush=True)


def main() -> None:
    catalog = Catalog()
    catalog.refresh()
    catalog.ensure_guards()
    lock = threading.Lock()
    def send(msg):
        with lock:
            print(json.dumps(msg), flush=True)
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(msg, dict):
            continue
        op = msg.get("op")
        if op == "search":
            catalog.refresh()
            catalog.ensure_guards()
            send({"id": msg.get("id", ""), "results": search(catalog, str(msg.get("query", "")))})
        elif op == "warm":
            catalog.refresh()
            catalog.ensure_guards()
        elif op == "cancel":
            send({"id": msg.get("target", ""), "cancelled": True})
        elif op == "execute":
            send({"id": msg.get("id", ""), "executed": False, "error": "omarchy actions are launched by the host"})


if __name__ == "__main__":
    main()
