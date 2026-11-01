#!/usr/bin/env python3
"""Omarchy's opinionated default apps, the way Omarchy's own keys launch them.

Every launch argv is copied from default/hypr/bindings/applications.lua or
utilities.lua (helpers.lua turns `{omarchy=X}` into `omarchy-launch-X`,
`{webapp=URL}` into `omarchy-launch-webapp URL`, `{tui=X}` into
`omarchy-launch-tui X`). README.md lists the source of each row.

Apps that already ship a .desktop file (YouTube, WhatsApp, HEY, Google Maps,
...) come from the apps provider; this one adds what a .desktop file does not
offer: Omarchy's launch-or-focus wrappers, the private window, TUIs, the
shortcut-only web apps, and searches inside Omarchy's web apps.

Searches pass the typed text only as a percent-encoded URL argument to
`omarchy-launch-webapp` / `omarchy-launch-browser` (argv, no shell). Never to
the `*-or-focus-*` wrappers, which eval their arguments.
"""
from __future__ import annotations
import hashlib
import json
import re
import shutil
import sys
from urllib.parse import quote

MAX_RESULTS = 12
MAX_TERM = 300
BLUE = "#89b4fa"
GREEN = "#a6e3a1"
PURPLE = "#cba6f7"
RED = "#f38ba8"


def app(key, title, subtitle, icon, argv, words, glyph, color=BLUE, keys="", needs=""):
    sub = subtitle + (" · " + keys if keys else "")
    return {"key": key, "title": title, "subtitle": sub, "icon": icon, "fallbackIcon": glyph, "fallbackColor": color,
            "keywords": (title + " " + words).lower(), "argv": argv, "needs": needs}


def webapp(url):
    return ["omarchy-launch-webapp", url]


CATALOG = [
    # applications.lua: essential bindings
    app("terminal", "Terminal", "Open the default terminal", "utilities-terminal", ["omarchy-launch-terminal"], "shell console alacritty ghostty kitty", "❯", keys="Super+Return"),
    app("browser", "Browser", "Open the default browser", "web-browser", ["omarchy-launch-browser"], "web internet chromium", "🌐", keys="Super+Shift+B"),
    app("browser-private", "Private Browser Window", "Open the default browser in a private/incognito window", "web-browser", ["omarchy-launch-browser", "--private"], "incognito private browsing web", "🕶", PURPLE, keys="Super+Shift+Alt+B"),
    app("file-manager", "File Manager", "Open Nautilus", "system-file-manager", ["omarchy-launch-nautilus"], "files nautilus folders explorer", "📁", keys="Super+Shift+F"),
    app("editor", "Editor", "Open the default editor (Omarchy defaults)", "accessories-text-editor", ["omarchy-launch-editor"], "nvim neovim code text", "✎", keys="Super+Shift+N"),
    # applications.lua: preinstalled apps and TUIs
    app("tmux", "Tmux Terminal", "Attach to tmux or start the Work session", "utilities-terminal", ["omarchy-launch-terminal-tmux"], "tmux multiplexer session work", "❯", keys="Super+Alt+Return"),
    app("herdr", "Herdr Terminal", "Open a terminal running herdr", "utilities-terminal", ["omarchy-launch-terminal-herdr"], "herdr agents", "❯", keys="Super+Ctrl+Return"),
    app("music", "Music", "Focus or launch Spotify (offers to install it if missing)", "spotify", ["omarchy-launch-spotify"], "spotify songs player", "🎵", GREEN, keys="Super+Shift+M"),
    app("music-tui", "Music TUI", "Focus or launch cliamp in a terminal", "multimedia-player", ["omarchy-launch-or-focus-tui", "cliamp"], "cliamp terminal player songs", "🎵", GREEN, keys="Super+Shift+Alt+M"),
    app("signal", "Signal", "Focus or launch Signal (offers to install it if missing)", "signal-desktop", ["omarchy-launch-signal"], "chat messenger messages", "💬", keys="Super+Shift+G"),
    app("passwords", "Passwords", "Launch 1Password (offers to install it if missing)", "1password", ["omarchy-launch-1password"], "1password password manager vault secrets", "🔑", keys="Super+Shift+/"),
    app("docker", "Docker", "Open lazydocker in a terminal", "docker", ["omarchy-launch-tui", "omarchy-launch-docker-tui"], "lazydocker containers images", "🐳", keys="Super+Shift+D", needs="lazydocker"),
    # utilities.lua
    app("activity", "Activity", "System monitor (btop) in a terminal", "utilities-system-monitor", ["omarchy-launch-tui", "btop"], "btop top htop processes cpu memory task manager", "📈", GREEN, keys="Super+Shift+T"),
    # applications.lua: web apps without a .desktop file of their own
    app("chatgpt", "ChatGPT", "Web app", "chatgpt", webapp("https://chatgpt.com"), "ai openai gpt chat assistant", "🤖", GREEN, keys="Super+Shift+A"),
    app("grok", "Grok", "Web app", "grok", webapp("https://grok.com"), "ai xai chat assistant", "🤖", keys="Super+Shift+Alt+A"),
    app("hey-calendar", "Calendar (HEY)", "HEY Calendar web app", "x-office-calendar", webapp("https://app.hey.com/calendar/weeks/"), "hey calendar schedule events week", "📅", keys="Super+Shift+C"),
    app("hey-new-email", "New Email (HEY)", "Compose a HEY email in its own window", "mail-message-new", webapp("https://app.hey.com/messages/new?display=standalone&new_window=true"), "hey compose write mail email message", "✉", keys="Super+Shift+Alt+E"),
    app("x-post", "New X Post", "Compose a post on X", "x", webapp("https://x.com/compose/post"), "x twitter tweet compose post write", "✕", keys="Super+Shift+Alt+X"),
]

# Searches inside Omarchy's own web apps (applications.lua URLs) and the
# default browser. `words` are the leading words that pick a site unscoped.
SITES = [
    ("web", "Search the Web", "Google in the default browser", "web-browser", ("google", "search", "web"), lambda t: ["omarchy-launch-browser", "https://www.google.com/search?q=" + t], "🔎"),
    ("youtube", "Search YouTube", "YouTube web app", "youtube", ("youtube", "yt"), lambda t: webapp("https://www.youtube.com/results?search_query=" + t), "▶"),
    ("maps", "Search Google Maps", "Google Maps web app", "google-maps", ("maps", "map", "directions"), lambda t: webapp("https://maps.google.com/?q=" + t), "🗺"),
    ("chatgpt", "Ask ChatGPT", "ChatGPT web app", "chatgpt", ("chatgpt", "gpt"), lambda t: webapp("https://chatgpt.com/?q=" + t), "🤖"),
    ("grok", "Ask Grok", "Grok web app", "grok", ("grok",), lambda t: webapp("https://grok.com/?q=" + t), "🤖"),
    ("x", "Search X", "X web app", "x", ("twitter",), lambda t: webapp("https://x.com/search?q=" + t), "✕"),
]


def encode(term: str) -> str:
    # '-' is encoded too: omarchy-launch-browser rewrites "--private" anywhere in its args.
    return quote(term, safe="").replace("-", "%2D")


def valid_term(term: str) -> bool:
    return 0 < len(term) <= MAX_TERM and all(c.isprintable() for c in term)


def available(entry) -> bool:
    return not entry["needs"] or shutil.which(entry["needs"]) is not None


def row(rid, title, subtitle, icon, glyph, color, keywords, argv, score):
    return {"id": "defaults:" + rid, "title": title, "subtitle": subtitle, "icon": icon, "fallbackIcon": glyph,
            "fallbackColor": color, "keywords": keywords, "score": score, "provider": "defaults",
            "actions": [{"type": "launch", "title": title, "argv": argv},
                        {"type": "copy", "title": "Copy command", "text": " ".join(argv)}]}


def search_row(site, term, score):
    key, title, subtitle, icon, _words, build, glyph = site
    digest = hashlib.sha256(term.encode()).hexdigest()[:12]
    return row(f"search-{key}-{digest}", f"{title}: {term}", subtitle, icon, glyph, BLUE,
               f"{title} {term}".lower(), build(encode(term)), score)


def score(query: str, entry: dict) -> float:
    title = entry["title"].lower()
    if title == query: return 0.95
    if title.startswith(query): return 0.9
    if any(w.startswith(query) for w in re.split(r"[\s()/]+", title) if w): return 0.8
    if query in title: return 0.7
    if any(w.startswith(query) for w in entry["keywords"].split()): return 0.6
    return 0.0


def site_for(word: str):
    return next((s for s in SITES if word in s[4]), None)


def search(query: str, scope: str = "", catalog=None) -> list[dict]:
    catalog = CATALOG if catalog is None else catalog
    text = " ".join(query.split())
    q = text.lower()
    out: list[dict] = []
    # "youtube lofi", "maps coffee" (any scope); "web:lofi" searches every site.
    head, _, rest = text.partition(" ")
    site = site_for(head.lower())
    if site and valid_term(rest):
        out.append(search_row(site, rest, 0.93))
    elif scope == "defaults" and valid_term(text) and not any(score(q, e) >= 0.8 for e in catalog):
        out += [search_row(s, text, 0.9 - n * 0.01) for n, s in enumerate(SITES)]
    if q:
        ranked = sorted(((score(q, e), n, e) for n, e in enumerate(catalog)), key=lambda t: (-t[0], t[1]))
        for s, _, e in ranked:
            if s == 0.0: break
            if available(e):
                out.append(row(e["key"], e["title"], e["subtitle"], e["icon"], e["fallbackIcon"], e["fallbackColor"],
                               e["keywords"], e["argv"], s))
    elif scope == "defaults":
        out += [row(e["key"], e["title"], e["subtitle"], e["icon"], e["fallbackIcon"], e["fallbackColor"],
                    e["keywords"], e["argv"], 0.5) for e in catalog if available(e)]
    return out[:MAX_RESULTS] if scope != "defaults" or q else out


def main() -> None:
    for line in sys.stdin:
        try: msg = json.loads(line)
        except json.JSONDecodeError: continue
        if not isinstance(msg, dict): continue
        op = msg.get("op")
        if op == "search":
            print(json.dumps({"id": msg.get("id", ""), "results": search(str(msg.get("query", "")), str(msg.get("scope", "")))}), flush=True)
        elif op == "cancel":
            print(json.dumps({"id": msg.get("target", ""), "cancelled": True}), flush=True)
        elif op == "execute":
            print(json.dumps({"id": msg.get("id", ""), "executed": False, "error": "default-app actions are launched by the host"}), flush=True)


if __name__ == "__main__": main()
