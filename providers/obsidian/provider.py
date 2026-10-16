#!/usr/bin/env python3
"""Explicit Obsidian intent routing; never infer note creation from search.

The host supplies optional scope metadata. Generic launcher queries do not
become Obsidian searches unless they name Obsidian or explicitly request a
new note. No indexing, vault selection, or CLI readiness is claimed here.
"""
from __future__ import annotations
import hashlib
import json
import re
import shutil
import sys
from urllib.parse import urlencode, quote

MAX_RESULTS = 15
BLUE = "#89b4fa"
PURPLE = "#cba6f7"
GREEN = "#a6e3a1"
YELLOW = "#f9e2af"

def has_obsidian() -> bool:
    return shutil.which("obsidian") is not None

def entry(title: str, subtitle: str, icon: str, argv: list[str] | None = None, url: str | None = None, aliases: str = "", glyph: str = "◆", color: str = BLUE, danger: str = "none", tone: str = "", confirm_title: str = "", confirm_detail: str = "") -> dict:
    if argv is not None:
        action: dict = {"type": "launch", "title": title, "argv": argv}
    else:
        action = {"type": "open", "title": title, "url": url or "obsidian://choose-vault"}
    if danger == "confirm":
        action["danger"] = "confirm"; action["tone"] = tone or "warning"; action["confirmation"] = {"title": confirm_title, "detail": confirm_detail}
    text = " ".join(argv) if argv is not None else (url or "")
    return {"title": title, "subtitle": subtitle, "icon": icon, "icons": [icon], "fallbackIcon": glyph, "fallbackColor": color,
            "aliases": (title + " " + aliases).lower(),
            "actions": [action, {"type": "copy", "title": "Copy target", "text": text}]}

def uri(action: str, **params: str) -> str:
    query = urlencode({k: v for k, v in params.items() if v}, quote_via=quote)
    return "obsidian://" + action + ("?" + query if query else "")

def base_entries(q: str) -> list[dict]:
    present = has_obsidian()
    entries = [
        entry("Open Obsidian", "Launch Obsidian", "obsidian", argv=["obsidian"] if present else ["xdg-open", "obsidian://choose-vault"], aliases="obsidian notes vault markdown app launch", glyph="📓"),
        entry("Obsidian Daily Note", "Create or open today's daily note", "obsidian", url=uri("daily"), aliases="obsidian daily today journal note", glyph="🗓", color=GREEN),
        entry("Obsidian Search", "Open Obsidian's search view" + (f' for "{q}"' if len(q) >= 2 else ""), "obsidian", url=uri("search", query=q), aliases="obsidian search find notes vault content", glyph="🔎", color=PURPLE),
        entry("Obsidian Vault Manager", "Choose or manage vaults", "obsidian", url=uri("choose-vault"), aliases="obsidian vault choose vaults manage", glyph="🗂", color=YELLOW),
    ]
    if len(q) >= 3:
        entries.insert(1, entry(f"New Obsidian Note: {q}", "Create a note named after this query", "obsidian", url=uri("new", name=q), aliases="obsidian new note create markdown", glyph="📝", color=GREEN))
    if present:
        entries.append(entry("Obsidian CLI reference", "Open `obsidian help` in a visible terminal", "utilities-terminal", argv=["foot", "--", "sh", "-lc", "obsidian help; printf '\\n(See the README CLI setup section for registration and AI notes.)\\n'; exec $SHELL"], aliases="obsidian cli shell command help ai", glyph="⌨", color=YELLOW))
    return entries

def score(query: str, e: dict) -> float:
    title = e["title"].lower(); aliases = e["aliases"]; subtitle = e["subtitle"].lower()
    if "obsidian".startswith(query): base = 0.72
    elif title.startswith(query): base = 0.9
    elif any(word.startswith(query) for word in title.split()): base = 0.82
    elif query in title: base = 0.7
    elif any(word.startswith(query) for word in aliases.split()): base = 0.68
    elif query in aliases or query in subtitle: base = 0.55
    else: return 0.0
    return base

def search(query: str) -> list[dict]:
    q = query.strip()
    if not q: return []
    ranked = sorted(((score(q.lower(), e), e) for e in base_entries(q)), key=lambda pair: pair[0], reverse=True)
    out = []
    for s, e in ranked:
        if s == 0.0 or len(out) >= MAX_RESULTS: break
        out.append({"id": "obsidian:" + e["title"].lower().replace(" ", "-").replace(":", "")[:80], "title": e["title"], "subtitle": e["subtitle"], "icon": e["icon"], "icons": e["icons"], "fallbackIcon": e["fallbackIcon"], "fallbackColor": e["fallbackColor"], "keywords": e["aliases"], "score": s, "provider": "obsidian", "actions": e["actions"]})
    return out

def main() -> None:
    for line in sys.stdin:
        try: msg = json.loads(line)
        except json.JSONDecodeError: continue
        if msg.get("op") == "search": print(json.dumps({"id": msg.get("id", ""), "results": search(str(msg.get("query", "")))}), flush=True)
        elif msg.get("op") == "cancel": print(json.dumps({"id": msg.get("target", ""), "cancelled": True}), flush=True)
        elif msg.get("op") == "execute": print(json.dumps({"id": msg.get("id", ""), "executed": False}), flush=True)
if __name__ == "__main__": main()
