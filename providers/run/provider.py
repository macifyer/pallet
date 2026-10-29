#!/usr/bin/env python3
"""Suggest running the typed query as a shell command.

Raycast-flavored: any query also produces one trailing result that runs
the text verbatim in a visible foot terminal. Pallet never executes search
text itself — the chosen action hands the text to foot, which runs it in
the user's login shell in a real, inspectable window. Because this is the
deliberate boundary where typed text becomes a command, the action carries
danger: confirm — the two-Enter sheet is the user's final say.

Scored low on purpose and marked `"fallback": true`: the frontend ranks
fallbacks below every real match regardless of score, so "Run:" is a floor,
never a lid. The id carries the query so selection-follow and confirmation
binding can never mistake one typed command for another.
"""
from __future__ import annotations
import json
import sys

MIN_LEN = 3

def search(query: str) -> list[dict]:
    q = query.strip()
    if len(q) < MIN_LEN: return []
    shown = q if len(q) <= 64 else q[:61] + "..."
    return [{
        "id": "run:" + q,
        "fallback": True,
        "title": f"Run: {shown}",
        "subtitle": "Run as a command in a foot terminal — executes verbatim",
        "icon": "utilities-terminal",
        "icons": ["terminal", "utilities-terminal-symbolic"],
        "fallbackIcon": "⌨",
        "keywords": "run command shell terminal exec execute",
        "score": 0.25,
        "provider": "run",
        "actions": [{
            "type": "launch",
            "title": "Run in terminal",
            "argv": ["foot", "--", "sh", "-lc", q],
            "danger": "confirm",
            "tone": "warning",
            "confirmation": {
                "title": f"Run '{shown}'?",
                "detail": "Opens a visible foot terminal and executes exactly what you typed, in your login shell. Pallet itself never runs search text.",
            },
        }, {"type": "copy", "title": "Copy command", "text": q}],
    }]

def main() -> None:
    for line in sys.stdin:
        try: msg = json.loads(line)
        except json.JSONDecodeError: continue
        if msg.get("op") == "search":
            print(json.dumps({"id": msg.get("id", ""), "results": search(str(msg.get("query", "")))}), flush=True)
        elif msg.get("op") == "cancel":
            print(json.dumps({"id": msg.get("target", ""), "cancelled": True}), flush=True)
        elif msg.get("op") == "execute":
            print(json.dumps({"id": msg.get("id", ""), "executed": False, "error": "run actions are launched by the host"}), flush=True)

if __name__ == "__main__": main()
