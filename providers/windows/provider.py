#!/usr/bin/env python3
"""Search and control live Hyprland windows.

Window addresses come from hyprctl clients -j and are treated as ephemeral
capabilities: every action re-reads clients and refuses unknown addresses.
All hyprctl calls are explicit argv arrays; no shell is involved.

Icons resolve through .desktop entries, not wishful thinking: a startup map
associates StartupWMClass, desktop-file stem, Name, and Exec basename with
each entry's Icon (user dirs win over system dirs, per XDG precedence).
Results emit the layered icon contract -- primary name, ordered `icons`
candidates, `fallbackIcon` glyph -- so classes like "zen" (browser) pick up
their declared app icon instead of rendering bare.

Dispatching is Lua-era (Hyprland 0.55+): hyprctl dispatch wraps its argument
as hl.dispatch(<arg>), so every call is a hl.dsp.* dispatcher-object
expression. Legacy string dispatcher syntax was removed with hyprlang.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

MAX_RESULTS = 15
ADDRESS = re.compile(r"^0x[0-9a-fA-F]+$")

XDG_APPS_DIRS = [
    Path.home() / ".local/share/applications",
    Path.home() / ".local/share/flatpak/exports/share/applications",
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
    Path("/var/lib/flatpak/exports/share/applications"),
]

_icons: dict[str, str] = {}


def load_icon_map() -> dict[str, str]:
    """Associate window-class-ish tokens with declared desktop icons."""
    mapping: dict[str, str] = {}
    for directory in XDG_APPS_DIRS:
        if not directory.is_dir():
            continue
        for desktop in sorted(directory.glob("*.desktop")):
            try:
                text = desktop.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fields: dict[str, str] = {}
            in_entry = False
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("[") and line.endswith("]"):
                    in_entry = line == "[Desktop Entry]"
                    continue
                if not in_entry or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                fields.setdefault(key, value)
            icon = fields.get("Icon", "").strip()
            if not icon:
                continue
            keys = {desktop.name.removesuffix(".desktop").lower()}
            for key in ("StartupWMClass", "Name"):
                token = fields.get(key, "").strip().lower()
                if token:
                    keys.add(token)
            exec_line = fields.get("Exec", "").split()
            if exec_line:
                stem = Path(exec_line[0]).name.lower()
                if stem not in ("env", "flatpak", "sh", "bash"):
                    keys.add(stem)
            for key in keys:
                mapping.setdefault(key, icon)  # user dirs win: seen first
    return mapping


def hyprctl_json(*args: str) -> Any:
    try:
        out = subprocess.run(
            ["hyprctl", *args, "-j"],
            check=False, capture_output=True, text=True, timeout=2,
        ).stdout
        return json.loads(out)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def eval_dispatch(builder: str) -> bool:
    """Feed a hl.dsp.* dispatcher-object expression to hyprctl dispatch.

    The compositor replies with the text "ok" on success and an error
    message on failure, so both the exit code and the reply are checked.
    """
    try:
        result = subprocess.run(
            ["hyprctl", "dispatch", builder],
            check=False, capture_output=True, text=True, timeout=2,
        )
        return result.returncode == 0 and result.stdout.strip().startswith("ok")
    except (OSError, subprocess.TimeoutExpired):
        return False


def clients() -> list[dict]:
    value = hyprctl_json("clients")
    return value if isinstance(value, list) else []


def active_address() -> str:
    value = hyprctl_json("activewindow")
    return str(value.get("address", "")) if isinstance(value, dict) else ""


def workspace_label(client: dict) -> str:
    workspace = client.get("workspace") or {}
    if not isinstance(workspace, dict):
        return "workspace ?"
    name = str(workspace.get("name", "")).strip()
    wid = workspace.get("id", "?")
    return name if name else "workspace " + str(wid)


def icon_candidates(client: dict) -> list[str]:
    """Ordered icon guesses: desktop-declared icons first, then raw class
    names, then generic app icons."""
    seen: set[str] = set()
    out: list[str] = []
    for token in (client.get("class"), client.get("initialClass")):
        low = str(token or "").strip().lower()
        if not low:
            continue
        for name in (_icons.get(low, ""), low):
            if name and name not in seen:
                seen.add(name)
                out.append(name)
    for generic in ("applications-other", "application-x-executable"):
        if generic not in seen:
            out.append(generic)
    return out


def visible_client(client: dict) -> bool:
    address = str(client.get("address", ""))
    return bool(ADDRESS.fullmatch(address)) and bool(client.get("mapped", True)) and not bool(client.get("hidden", False))


def score(query: str, client: dict, active: str) -> float:
    title = str(client.get("title", "")).lower()
    klass = str(client.get("class", "")).lower()
    initial = str(client.get("initialClass", "")).lower()
    workspace = workspace_label(client).lower()
    if title.startswith(query) or klass.startswith(query) or initial.startswith(query):
        base = 0.94
    elif any(word.startswith(query) for word in title.split()) or any(word.startswith(query) for word in klass.split()):
        base = 0.86
    elif query in title or query in klass or query in initial:
        base = 0.74
    elif query in workspace:
        base = 0.55
    else:
        return 0.0
    if str(client.get("address")) == active:
        base = min(1.0, base + 0.05)
    return base


def result_for(client: dict, rank: float) -> dict:
    address = str(client["address"])
    title = str(client.get("title") or client.get("class") or "Untitled window")
    klass = str(client.get("class") or client.get("initialClass") or "Unknown app")
    icons = icon_candidates(client)
    state: list[str] = [workspace_label(client), klass]
    if client.get("floating"):
        state.append("floating")
    if client.get("fullscreen"):
        state.append("fullscreen")
    return {
        "id": "windows:" + address,
        "title": title,
        "subtitle": " \u00b7 ".join(state),
        "icon": icons[0],
        "icons": icons[1:],
        "fallbackIcon": "\u25a3",
        "keywords": " ".join([klass, str(client.get("initialClass") or ""), workspace_label(client)]).lower(),
        "score": rank,
        "provider": "windows",
        "actions": [
            {"type": "custom", "kind": "focus-window", "title": "Focus window", "address": address},
            {"type": "custom", "kind": "close-window", "title": "Close window", "address": address},
            {"type": "custom", "kind": "toggle-floating", "title": "Toggle floating", "address": address},
            {"type": "custom", "kind": "toggle-fullscreen", "title": "Toggle fullscreen", "address": address},
            {"type": "copy", "title": "Copy title", "text": title},
        ],
    }


def resolve_live(address: object) -> bool:
    if not isinstance(address, str) or not ADDRESS.fullmatch(address):
        return False
    return any(str(client.get("address")) == address for client in clients())


def execute(action: dict) -> bool:
    address = action.get("address")
    if not resolve_live(address):
        return False
    # Lua snippets are built from a regex-validated hex address and fixed
    # kind constants — search text and window titles never reach them.
    selector = f'window = "address:{address}"'
    kind = action.get("kind")
    if kind == "focus-window":
        return eval_dispatch(f"hl.dsp.focus({{ {selector} }})")
    if kind == "close-window":
        return eval_dispatch(f"hl.dsp.window.close({{ {selector} }})")
    if kind == "toggle-floating":
        return eval_dispatch(f'hl.dsp.window.float({{ action = "toggle", {selector} }})')
    if kind == "toggle-fullscreen":
        return eval_dispatch(f'hl.dsp.window.fullscreen({{ mode = "fullscreen", action = "toggle", {selector} }})')
    return False


def search(query: str) -> list[dict]:
    q = query.strip().lower()
    if not q:
        return []
    active = active_address()
    ranked = [(score(q, client, active), client) for client in clients() if visible_client(client)]
    ranked = [(rank, client) for rank, client in ranked if rank > 0]
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [result_for(client, rank) for rank, client in ranked[:MAX_RESULTS]]


def main() -> None:
    global _icons
    _icons = load_icon_map()
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        op = msg.get("op")
        if op == "search":
            print(json.dumps({"id": msg.get("id", ""), "results": search(str(msg.get("query", "")))}), flush=True)
        elif op == "execute":
            action = msg.get("action")
            ok = execute(action) if isinstance(action, dict) else False
            print(json.dumps({"id": msg.get("id", ""), "executed": ok}), flush=True)
        elif op == "cancel":
            print(json.dumps({"id": msg.get("target", ""), "cancelled": True}), flush=True)


if __name__ == "__main__":
    main()
