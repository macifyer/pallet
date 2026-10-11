#!/usr/bin/env python3
"""System power, session, and update commands.

Every command mirrors the native Omarchy menu: omarchy system lock/logout/
reboot/shutdown (which close application windows first), systemctl suspend,
omarchy menu toggle, and omarchy update in a visible terminal (foot). No raw
pacman, ever — the update path is Omarchy's own orchestrated script.

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
    confirm_title: str = "",
    confirm_detail: str = "",
) -> dict:
    action: dict = {"type": "launch", "title": title, "argv": argv}
    if danger == "confirm":
        action["danger"] = "confirm"
        action["confirmation"] = {"title": confirm_title, "detail": confirm_detail}
    return {
        "title": title,
        "subtitle": subtitle,
        "icon": icon,
        "aliases": (title + " " + aliases).lower(),
        "actions": [action, {"type": "copy", "title": "Copy command", "text": " ".join(argv)}],
    }


ENTRIES: list[dict] = [
    entry(
        "Lock",
        "Lock the screen now",
        "system-lock-screen",
        ["omarchy", "system", "lock"],
        "lock screen screensaver",
    ),
    entry(
        "Omarchy Menu",
        "Open the native Omarchy menu",
        "application-menu",
        ["omarchy", "menu", "toggle"],
        "menu native omarchy",
    ),
    entry(
        "Suspend",
        "Suspend the machine",
        "weather-clear-night",
        ["systemctl", "suspend"],
        "suspend sleep rest",
        danger="confirm",
        confirm_title="Suspend now?",
        confirm_detail="Suspends the machine immediately; waking takes a moment.",
    ),
    entry(
        "Update Omarchy",
        "Snapshot, packages, migrations — the official update",
        "software-update-available",
        ["foot", "--", "omarchy", "update"],
        "update upgrade refresh",
        danger="confirm",
        confirm_title="Update Omarchy?",
        confirm_detail="Runs 'omarchy update' in a terminal: snapshot, packages, migrations, and a shell restart. Uses Omarchy's own update path — no raw pacman.",
    ),
    entry(
        "Log Out",
        "End the session after closing windows",
        "system-log-out",
        ["omarchy", "system", "logout"],
        "logout log out exit session",
        danger="confirm",
        confirm_title="Log out?",
        confirm_detail="Closes all application windows and ends your session.",
    ),
    entry(
        "Reboot",
        "Restart the machine",
        "system-reboot",
        ["omarchy", "system", "reboot"],
        "reboot restart",
        danger="confirm",
        confirm_title="Reboot?",
        confirm_detail="Closes your session and reboots the machine.",
    ),
    entry(
        "Shut Down",
        "Power off the machine",
        "system-shutdown",
        ["omarchy", "system", "shutdown"],
        "shutdown power off halt",
        danger="confirm",
        confirm_title="Shut down?",
        confirm_detail="Closes your session and powers off the machine.",
    ),
]


def score(query: str, item: dict) -> float:
    title = item["title"].lower()
    if title.startswith(query):
        return 0.92
    if any(word.startswith(query) for word in title.split()):
        return 0.82
    if query in title:
        return 0.7
    if any(word.startswith(query) for word in item["aliases"].split()):
        return 0.6
    if query in item["aliases"]:
        return 0.5
    if query in item["subtitle"].lower():
        return 0.4
    return 0.0


def search(query: str) -> list[dict]:
    q = query.strip().lower()
    if not q:
        return []
    ranked = sorted(
        ((score(q, e), e) for e in ENTRIES),
        key=lambda pair: pair[0],
        reverse=True,
    )
    out: list[dict] = []
    for s, e in ranked:
        if s == 0.0 or len(out) >= MAX_RESULTS:
            break
        out.append(
            {
                "id": "system:" + e["title"].lower().replace(" ", "-"),
                "title": e["title"],
                "subtitle": e["subtitle"],
                "icon": e["icon"],
                "keywords": e["aliases"],
                "score": s,
                "provider": "system",
                "actions": e["actions"],
            }
        )
    return out


def main() -> None:
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
            # All actions are launch-type; the frontend runs them itself.
            print(json.dumps({"id": msg.get("id", ""), "executed": False}), flush=True)


if __name__ == "__main__":
    main()
