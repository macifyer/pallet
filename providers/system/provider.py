#!/usr/bin/env python3
"""System power, session, update, and package commands.

Every command mirrors the native Omarchy menu: omarchy system lock/logout/
reboot/shutdown (which close application windows first), systemctl suspend,
omarchy menu toggle, and omarchy update in a visible terminal (foot). No raw
pacman, ever -- update and package management go through Omarchy's own
orchestrated scripts. The package trio delegates wholesale: each entry opens
the native menu's exact flow (omarchy-pkg-install / omarchy-pkg-aur-install /
omarchy-pkg-remove) in a terminal, the same as Install > Package, Install >
AUR, and Remove > Package behind SUPER+SPACE.

Destructive or disruptive entries carry danger: confirm, so the frontend
shows the confirmation sheet before a second Enter runs them. Lock is the
one deliberate exception: locking should always be one keystroke away.
"""

from __future__ import annotations

import json
import sys

MAX_RESULTS = 15


def entry(
    title: str,
    subtitle: str,
    icon: str,
    argv: list[str],
    aliases: str,
    danger: str = "none",
    tone: str = "",
    confirm_title: str = "",
    confirm_detail: str = "",
) -> dict:
    action: dict = {"type": "launch", "title": title, "argv": argv}
    if danger == "confirm":
        action["danger"] = "confirm"
        action["tone"] = tone or "warning"
        action["confirmation"] = {"title": confirm_title, "detail": confirm_detail}
    return {
        "title": title,
        "subtitle": subtitle,
        "icon": icon,
        "aliases": (title + " " + aliases).lower(),
        "actions": [action, {"type": "copy", "title": "Copy command", "text": " ".join(argv)}],
    }


ENTRIES: list[dict] = [
    entry("Lock", "Lock the screen now", "system-lock-screen", ["omarchy", "system", "lock"], "lock screen screensaver"),
    entry("Omarchy Menu", "Open the native Omarchy menu", "application-menu", ["omarchy", "menu", "toggle"], "menu native omarchy"),
    entry(
        "Suspend", "Suspend the machine", "system-suspend", ["systemctl", "suspend"], "suspend sleep rest",
        danger="confirm", tone="warning", confirm_title="Suspend now?",
        confirm_detail="Suspends the machine immediately; waking takes a moment.",
    ),
    entry(
        "Update Omarchy", "Snapshot, packages, migrations -- the official update", "software-update-available", ["foot", "--", "omarchy", "update"], "update upgrade refresh",
        danger="confirm", tone="positive", confirm_title="Update Omarchy?",
        confirm_detail="Runs 'omarchy update' in a terminal: snapshot, packages, migrations, and a shell restart. Uses Omarchy's own update path -- no raw pacman.",
    ),
    entry(
        "Install Package", "Install from the official repos -- Omarchy's installer", "system-software-install",
        ["xdg-terminal-exec", "--app-id=org.omarchy.terminal", "omarchy-pkg-install"], "install package pacman repo repos",
        danger="confirm", tone="positive", confirm_title="Install a package?",
        confirm_detail="Opens Omarchy's package installer in a terminal -- the same flow as the native menu's Install > Package.",
    ),
    entry(
        "Install from AUR", "Install from the Arch User Repository", "system-software-install",
        ["xdg-terminal-exec", "--app-id=org.omarchy.terminal", "omarchy-pkg-aur-install"], "aur install yay paru user repository",
        danger="confirm", tone="warning", confirm_title="Install from the AUR?",
        confirm_detail="Opens Omarchy's AUR installer in a terminal (Install > AUR). It will build a community PKGBUILD -- same flow the native menu uses.",
    ),
    entry(
        "Remove Package", "Uninstall a package -- Omarchy's remover", "package-remove",
        ["xdg-terminal-exec", "--app-id=org.omarchy.terminal", "omarchy-pkg-remove"], "remove uninstall package delete pkg",
        danger="confirm", tone="danger", confirm_title="Remove a package?",
        confirm_detail="Opens Omarchy's package remover in a terminal -- the same flow as the native menu's Remove > Package.",
    ),
    entry(
        "Log Out", "End the session after closing windows", "system-log-out", ["omarchy", "system", "logout"], "logout log out exit session",
        danger="confirm", tone="warning", confirm_title="Log out?",
        confirm_detail="Closes all application windows and ends your session.",
    ),
    entry(
        "Reboot", "Restart the machine", "system-reboot", ["omarchy", "system", "reboot"], "reboot restart",
        danger="confirm", tone="warning", confirm_title="Reboot?",
        confirm_detail="Closes your session and reboots the machine.",
    ),
    entry(
        "Shut Down", "Power off the machine", "system-shutdown", ["omarchy", "system", "shutdown"], "shutdown power off halt",
        danger="confirm", tone="danger", confirm_title="Shut down?",
        confirm_detail="Closes your session and powers off the machine.",
    ),
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
        out.append({
            "id": "system:" + e["title"].lower().replace(" ", "-"),
            "title": e["title"], "subtitle": e["subtitle"], "icon": e["icon"],
            "keywords": e["aliases"], "score": s, "provider": "system", "actions": e["actions"],
        })
    return out


def main() -> None:
    for line in sys.stdin:
        try: msg = json.loads(line)
        except json.JSONDecodeError: continue
        if msg.get("op") == "search":
            print(json.dumps({"id": msg.get("id", ""), "results": search(str(msg.get("query", "")))}), flush=True)
        elif msg.get("op") == "cancel":
            print(json.dumps({"id": msg.get("target", ""), "cancelled": True}), flush=True)
        elif msg.get("op") == "execute":
            print(json.dumps({"id": msg.get("id", ""), "executed": False}), flush=True)


if __name__ == "__main__":
    main()
