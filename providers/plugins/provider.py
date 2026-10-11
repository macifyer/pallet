#!/usr/bin/env python3
"""Search and summon installed Omarchy shell plugins.

The Quattro shell is a plugin host: every first-party panel/overlay and
every third-party install declares itself in a manifest.json with an id,
name, description, and kinds. This provider scans the third-party directory
(~/.config/omarchy/plugins) plus known first-party locations, so results
reflect the machine's actual setup: install a plugin and it becomes
searchable in Pallet without any code change here.

Results are summoned through the shell's documented CLI (the same IPC the
native menu uses for image-picker/speedtest). Pallet itself is excluded --
toggling the palette from inside the palette is a hall of mirrors.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

MAX_RESULTS = 15
SELF_ID = "io.github.macifyer.pallet"

SCAN_DIRS = [
    Path.home() / ".config/omarchy/plugins",
    Path.home() / ".local/share/omarchy/shell/plugins",
    Path("/usr/share/omarchy/shell/plugins"),
    Path("/usr/local/share/omarchy/shell/plugins"),
]

ICON_BY_KIND = {
    "overlay": ("preferences-system-windows", "◧"),
    "menu": ("application-menu", "☰"),
    "bar-widget": ("panel", "▤"),
    "panel": ("view-grid", "▦"),
    "service": ("system-run", "⚙"),
    "widget": ("window-duplicate", "▣"),
}

_plugins: list[dict] = []

def load_plugins() -> list[dict]:
    found: dict[str, dict] = {}
    for root in SCAN_DIRS:
        if not root.is_dir():
            continue
        for manifest in sorted(root.glob("*/manifest.json")):
            try:
                spec = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
            except (OSError, json.JSONDecodeError):
                continue
            pid = str(spec.get("id", "")).strip()
            if not pid or pid == SELF_ID or pid in found:
                continue
            kinds = spec.get("kinds") if isinstance(spec.get("kinds"), list) else []
            kinds = [str(k) for k in kinds]
            icon, glyph = next((ICON_BY_KIND[k] for k in kinds if k in ICON_BY_KIND), ("application-x-addon", "🧩"))
            tail = pid.split(".")[-1].replace("-", " ").replace("_", " ")
            found[pid] = {
                "id": pid,
                "title": str(spec.get("name") or tail.title()),
                "subtitle": str(spec.get("description") or " · ".join(kinds) or "Omarchy plugin"),
                "icon": icon,
                "glyph": glyph,
                "kinds": kinds,
                "aliases": (tail + " " + pid.replace(".", " ").replace("-", " ")).lower(),
            }
    return sorted(found.values(), key=lambda p: p["title"].lower())

def score(query: str, p: dict) -> float:
    title = p["title"].lower()
    if title.startswith(query): return 0.9
    if any(word.startswith(query) for word in title.split()): return 0.8
    if any(word.startswith(query) for word in p["aliases"].split()): return 0.62
    if query in title or query in p["aliases"]: return 0.55
    if query in p["subtitle"].lower(): return 0.4
    return 0.0

def result_for(p: dict, s: float) -> dict:
    summon = ["omarchy-shell", "shell", "summon", p["id"]]
    toggle = ["omarchy-shell", "shell", "toggle", p["id"]]
    return {
        "id": "plugins:" + p["id"],
        "title": p["title"],
        "subtitle": p["subtitle"],
        "icon": p["icon"],
        "fallbackIcon": p["glyph"],
        "keywords": p["aliases"] + " plugin plugins shell panel extension addon",
        "score": s,
        "provider": "plugins",
        "actions": [
            {"type": "launch", "title": "Summon", "argv": summon},
            {"type": "launch", "title": "Toggle", "argv": toggle},
            {"type": "copy", "title": "Copy plugin id", "text": p["id"]},
        ],
    }

def search(query: str) -> list[dict]:
    q = query.strip().lower()
    if not q:
        return []
    ranked = sorted(((score(q, p), p) for p in _plugins), key=lambda pair: pair[0], reverse=True)
    return [result_for(p, s) for s, p in ranked if s > 0][:MAX_RESULTS]

def main() -> None:
    global _plugins
    _plugins = load_plugins()
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("op") == "search":
            print(json.dumps({"id": msg.get("id", ""), "results": search(str(msg.get("query", "")))}), flush=True)
        elif msg.get("op") == "cancel":
            print(json.dumps({"id": msg.get("target", ""), "cancelled": True}), flush=True)
        elif msg.get("op") == "execute":
            print(json.dumps({"id": msg.get("id", ""), "executed": False}), flush=True)

if __name__ == "__main__":
    main()
