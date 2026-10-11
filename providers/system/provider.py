#!/usr/bin/env python3
"""System power, session, update, and package commands.

Every command mirrors the native Omarchy menu. Icons use a primary theme name,
an ordered candidate list, and a glyph fallback so no theme leaves a row bare.
"""
from __future__ import annotations
import json
import sys
MAX_RESULTS = 15
BLUE = "#89b4fa"
GREEN = "#a6e3a1"
YELLOW = "#f9e2af"
RED = "#f38ba8"

def entry(title: str, subtitle: str, icon: str, argv: list[str], aliases: str, icons: list[str] | None = None, fallback_icon: str = "", fallback_color: str = BLUE, danger: str = "none", tone: str = "", confirm_title: str = "", confirm_detail: str = "") -> dict:
    action: dict = {"type": "launch", "title": title, "argv": argv}
    if danger == "confirm":
        action["danger"] = "confirm"; action["tone"] = tone or "warning"; action["confirmation"] = {"title": confirm_title, "detail": confirm_detail}
    return {"title": title, "subtitle": subtitle, "icon": icon, "icons": icons or [], "fallbackIcon": fallback_icon, "fallbackColor": fallback_color, "aliases": (title + " " + aliases).lower(), "actions": [action, {"type": "copy", "title": "Copy command", "text": " ".join(argv)}]}

ENTRIES: list[dict] = [
    entry("Lock", "Lock the screen now", "system-lock-screen", ["omarchy", "system", "lock"], "lock screen screensaver", ["lock", "system-lock"], "\U0001f512"),
    entry("Omarchy Menu", "Open the native Omarchy menu", "application-menu", ["omarchy", "menu", "toggle"], "menu native omarchy", ["open-menu-symbolic", "start-here"], "\u2630"),
    entry("Suspend", "Suspend the machine", "system-suspend", ["systemctl", "suspend"], "suspend sleep rest", ["weather-clear-night", "night-light", "system-suspend-hibernate"], "\U0001f319", YELLOW, "confirm", "warning", "Suspend now?", "Suspends the machine immediately; waking takes a moment."),
    entry("Update Omarchy", "Snapshot, packages, migrations -- the official update", "software-update-available", ["foot", "--", "omarchy", "update"], "update upgrade refresh", ["system-software-update", "software-update-urgent", "view-refresh"], "\u2b06", GREEN, "confirm", "positive", "Update Omarchy?", "Runs 'omarchy update' in a terminal: snapshot, packages, migrations, and a shell restart. Uses Omarchy's own update path -- no raw pacman."),
    entry("Install Package", "Install from the official repos -- Omarchy's installer", "system-software-install", ["xdg-terminal-exec", "--app-id=org.omarchy.terminal", "omarchy-pkg-install"], "install package pacman repo repos", ["package-install", "package"], "\U0001f4e6", GREEN),
    entry("Install from AUR", "Install from the Arch User Repository", "system-software-install", ["xdg-terminal-exec", "--app-id=org.omarchy.terminal", "omarchy-pkg-aur-install"], "aur install yay paru user repository", ["package-install", "package"], "\U0001f4e6", YELLOW),
    entry("Remove Package", "Uninstall a package -- Omarchy's remover", "package-remove", ["xdg-terminal-exec", "--app-id=org.omarchy.terminal", "omarchy-pkg-remove"], "remove uninstall package delete pkg", ["list-remove", "edit-delete"], "\U0001f5d1", RED),
    entry("Log Out", "End the session after closing windows", "system-log-out", ["omarchy", "system", "logout"], "logout log out exit session", ["system-logout", "application-exit"], "\U0001f6aa", YELLOW, "confirm", "warning", "Log out?", "Closes all application windows and ends your session."),
    entry("Reboot", "Restart the machine", "system-reboot", ["omarchy", "system", "reboot"], "reboot restart", ["system-restart", "view-refresh"], "\U0001f504", YELLOW, "confirm", "warning", "Reboot?", "Closes your session and reboots the machine."),
    entry("Shut Down", "Power off the machine", "system-shutdown", ["omarchy", "system", "shutdown"], "shutdown power off halt", ["system-power", "system-shutdown-symbolic"], "\u23fb", RED, "confirm", "danger", "Shut down?", "Closes your session and powers off the machine."),
]

def score(query: str, item: dict) -> float:
    title = item["title"].lower()
    if title.startswith(query): return 0.92
    if any(word.startswith(query) for word in title.split()): return 0.82
    if query in title: return 0.7
    if any(word.startswith(query) for word in item["aliases"].split()): return 0.6
    if query in item["aliases"]: return 0.5
    if query in item["subtitle"].lower(): return 0.4
    return 0.0

def search(query: str) -> list[dict]:
    q = query.strip().lower()
    if not q: return []
    ranked = sorted(((score(q, e), e) for e in ENTRIES), key=lambda pair: pair[0], reverse=True)
    out: list[dict] = []
    for s, e in ranked:
        if s == 0.0 or len(out) >= MAX_RESULTS: break
        out.append({"id": "system:" + e["title"].lower().replace(" ", "-"), "title": e["title"], "subtitle": e["subtitle"], "icon": e["icon"], "icons": e["icons"], "fallbackIcon": e["fallbackIcon"], "fallbackColor": e["fallbackColor"], "keywords": e["aliases"], "score": s, "provider": "system", "actions": e["actions"]})
    return out

def main() -> None:
    for line in sys.stdin:
        try: msg = json.loads(line)
        except json.JSONDecodeError: continue
        if msg.get("op") == "search": print(json.dumps({"id": msg.get("id", ""), "results": search(str(msg.get("query", "")))}), flush=True)
        elif msg.get("op") == "cancel": print(json.dumps({"id": msg.get("target", ""), "cancelled": True}), flush=True)
        elif msg.get("op") == "execute": print(json.dumps({"id": msg.get("id", ""), "executed": False}), flush=True)
if __name__ == "__main__": main()
