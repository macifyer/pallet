#!/usr/bin/env python3
"""Omarchy menu parity: panels, triggers, style, and learning.

Every argv below is copied verbatim from default/omarchy/omarchy-menu.jsonc
(upstream omarchy-menu definition). Panels are summoned through the same
omarchy-shell IPC the native menu uses; toggles run Omarchy's own commands
silently. Nothing is invented and no search text ever reaches a shell.
"""
from __future__ import annotations
import json
import sys

MAX_RESULTS = 15
BLUE = "#89b4fa"
GREEN = "#a6e3a1"
YELLOW = "#f9e2af"
PURPLE = "#cba6f7"

def shell(*parts: str) -> list[str]:
    return ["omarchy-shell", "shell", "summon", *parts]

def entry(title: str, subtitle: str, icon: str, argv: list[str], aliases: str, icons: list[str] | None = None, glyph: str = "", color: str = BLUE) -> dict:
    return {"title": title, "subtitle": subtitle, "icon": icon, "icons": icons or [], "fallbackIcon": glyph, "fallbackColor": color,
            "aliases": (title + " " + aliases).lower(),
            "actions": [{"type": "launch", "title": title, "argv": argv}, {"type": "copy", "title": "Copy command", "text": " ".join(argv)}]}

ENTRIES: list[dict] = [
    # Panels (bar-widget control panels, summoned like the native shell does)
    entry("Network", "Wi-Fi and networking panel", "network-wireless", shell("omarchy.network"), "wifi wi-fi network internet ethernet wireless connection", glyph="\U0001f4f6"),
    entry("Bluetooth", "Bluetooth devices panel", "bluetooth-active", shell("omarchy.bluetooth"), "bluetooth bt devices pair", icons=["bluetooth", "bluetooth-symbolic"], glyph="\u1f535".replace("\u1", "\\U0001") if False else "\U0001f535"),
    entry("Audio", "Volume and devices panel", "audio-volume-high", shell("omarchy.audio"), "audio sound volume mic microphone speaker output input", glyph="\U0001f50a"),
    entry("Power", "Battery and power profiles panel", "battery-full", shell("omarchy.power"), "power battery charge profile laptop", icons=["battery-good", "preferences-system-power"], glyph="\U0001f50b"),
    entry("Network Speed Test", "Measure internet throughput", "network-wireless", shell("omarchy.speedtest"), "speedtest speed test network bandwidth download upload", glyph="\u23f1"),
    # Trigger: tools and silent toggles, exactly the native menu's actions
    entry("Emoji Picker", "Pick an emoji into the clipboard", "face-smile", ["omarchy-menu-emoji"], "emoji emojis smile picker symbol", glyph="\U0001f600"),
    entry("Screenshot", "Capture the screen (interactive)", "applets-screenshooter", ["omarchy-capture-screenshot"], "screenshot capture screen shot grab", icons=["camera-photo", "screenshooter"], glyph="\U0001f4f8"),
    entry("Stay Awake", "Toggle idle lock (caffeine)", "weather-clear-night", ["omarchy-toggle-idle"], "stay awake caffeine idle lock keep on", glyph="\u2615", color=YELLOW),
    entry("Notifications", "Toggle notification silencing", "preferences-system-notifications", ["omarchy-toggle-notification-silencing"], "notifications silence silent mute do not disturb dnd", glyph="\U0001f514", color=YELLOW),
    entry("Nightlight", "Toggle the nightlight (hyprsunset)", "night-light", ["omarchy-toggle-nightlight"], "nightlight night light warm blue filter", icons=["weather-clear-night"], glyph="\U0001f317", color=YELLOW),
    entry("Menu Bar", "Toggle the top menu bar", "panel", ["omarchy-toggle-bar"], "menu bar top bar hide bar show bar", glyph="\u25a4", color=YELLOW),
    entry("Window Gaps", "Toggle Hyprland window gaps", "view-grid", ["omarchy-hyprland-window-gaps-toggle"], "window gaps gap spacing borders", glyph="\u25eb", color=YELLOW),
    entry("Animations", "Toggle Hyprland animations", "animations", ["omarchy-toggle-animations"], "animations animate effects motion blur", glyph="\u2728", color=YELLOW),
    # Style
    entry("Theme", "Pick a system theme", "preferences-desktop-theme", shell("omarchy.image-picker", "{\"source\":\"themes\"}"), "theme themes color scheme colors style", glyph="\U0001f3a8", color=PURPLE),
    entry("Wallpaper", "Pick a desktop background", "preferences-desktop-wallpaper", ["bash", "-c", "background=$(omarchy-theme-bg-switcher); [[ -n $background ]] && omarchy-theme-bg-set \"$background\""], "wallpaper background bg picture image", glyph="\U0001f5bc", color=PURPLE),
    # Learn
    entry("Keybindings", "Browse Omarchy keybindings", "input-keyboard", ["omarchy-menu-keybindings"], "keybindings keys shortcuts hotkeys help", glyph="\u2328", color=GREEN),
    entry("Omarchy Manual", "Open the official manual", "help-contents", ["omarchy-launch-webapp", "https://omarchy/manual/"], "omarchy manual docs documentation help learn", glyph="\U0001f4d6", color=GREEN),
    entry("Hyprland Wiki", "Open the Hyprland wiki", "help-contents", ["omarchy-launch-webapp", "https://wiki.hypr.land/"], "hyprland wiki docs help learn", glyph="\U0001f4d8", color=GREEN),
    entry("Arch Wiki", "Open the Arch Linux wiki", "help-contents", ["omarchy-launch-webapp", "https://wiki.archlinux/title/Main_page"], "arch wiki linux docs help learn", glyph="\U0001f4da", color=GREEN),
]

def score(query: str, e: dict) -> float:
    title = e["title"].lower()
    if title.startswith(query): return 0.92
    if any(word.startswith(query) for word in title.split()): return 0.82
    if query in title: return 0.7
    if any(word.startswith(query) for word in e["aliases"].split()): return 0.62
    if query in e["aliases"]: return 0.52
    if query in e["subtitle"].lower(): return 0.4
    return 0.0

def search(query: str) -> list[dict]:
    q = query.strip().lower()
    if not q: return []
    ranked = sorted(((score(q, e), e) for e in ENTRIES), key=lambda pair: pair[0], reverse=True)
    out: list[dict] = []
    for s, e in ranked:
        if s == 0.0 or len(out) >= MAX_RESULTS: break
        out.append({"id": "omarchy:" + e["title"].lower().replace(" ", "-"), "title": e["title"], "subtitle": e["subtitle"], "icon": e["icon"], "icons": e["icons"], "fallbackIcon": e["fallbackIcon"], "fallbackColor": e["fallbackColor"], "keywords": e["aliases"], "score": s, "provider": "omarchy", "actions": e["actions"]})
    return out

def main() -> None:
    for line in sys.stdin:
        try: msg = json.loads(line)
        except json.JSONDecodeError: continue
        if msg.get("op") == "search": print(json.dumps({"id": msg.get("id", ""), "results": search(str(msg.get("query", "")))}), flush=True)
        elif msg.get("op") == "cancel": print(json.dumps({"id": msg.get("target", ""), "cancelled": True}), flush=True)
        elif msg.get("op") == "execute": print(json.dumps({"id": msg.get("id", ""), "executed": False}), flush=True)

if __name__ == "__main__": main()
