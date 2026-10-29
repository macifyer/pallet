#!/usr/bin/env python3
"""System controls Omarchy binds to keys but does not list in its menu.

Volume, microphone, media, brightness, keyboard backlight, Bluetooth power,
notifications, window helpers and quick status. Every argv is the exact
command an Omarchy keybinding runs (default/hypr/bindings/*.lua and the
dispatch table in default/hypr/helpers.lua); README.md lists the source of
each. Power, session, update and package rows live in the omarchy provider,
which mirrors the native menu, so they are not duplicated here.
"""
from __future__ import annotations
import json
import sys

MAX_RESULTS = 15
BLUE = "#89b4fa"
GREEN = "#a6e3a1"
YELLOW = "#f9e2af"
RED = "#f38ba8"
PURPLE = "#cba6f7"


def ipc(target: str, method: str) -> list[str]:
    return ["omarchy-shell", target, method]


def entry(key, title, subtitle, icon, argv, words, glyph, color=BLUE, confirm=None):
    action = {"type": "launch", "title": title, "argv": argv}
    if confirm:
        tone, ctitle, detail = confirm
        action.update({"danger": "confirm", "tone": tone, "confirmation": {"title": ctitle, "detail": detail}})
    return {"key": key, "title": title, "subtitle": subtitle, "icon": icon, "fallbackIcon": glyph,
            "fallbackColor": color, "keywords": (title + " " + words).lower(),
            "actions": [action, {"type": "copy", "title": "Copy command", "text": " ".join(argv)}]}


ENTRIES = [
    # Audio (bindings/media.lua; helpers.lua maps {audio=...} to omarchy-audio-output-volume)
    entry("volume-up", "Volume Up", "Raise output volume", "audio-volume-high", ["omarchy-audio-output-volume", "raise"], "louder sound audio increase", "🔊"),
    entry("volume-down", "Volume Down", "Lower output volume", "audio-volume-low", ["omarchy-audio-output-volume", "lower"], "quieter sound audio decrease", "🔉"),
    entry("mute", "Mute Audio", "Toggle output mute", "audio-volume-muted", ["omarchy-audio-output-volume", "mute-toggle"], "mute unmute sound audio speaker silence", "🔇"),
    entry("mic-mute", "Mute Microphone", "Toggle microphone mute", "microphone-sensitivity-muted", ["omarchy-audio-input-mute"], "mic microphone mute unmute input", "🎙"),
    entry("audio-output", "Switch Audio Output", "Cycle to the next output device", "audio-speakers", ["omarchy-audio-output-switch"], "speaker headphones output device sink", "🎧"),
    entry("media-source", "Switch Media Source", "Cycle which player the media keys control", "multimedia-player", ["omarchy-audio-source-switch"], "player media source", "🎵"),
    # Media (bindings/media.lua {ipc = "media.*"})
    entry("play-pause", "Play / Pause", "Toggle playback", "media-playback-start", ipc("media", "playPause"), "play pause music media resume", "⏯", GREEN),
    entry("next-track", "Next Track", "Skip to the next track", "media-skip-forward", ipc("media", "next"), "next skip music media song", "⏭", GREEN),
    entry("previous-track", "Previous Track", "Go to the previous track", "media-skip-backward", ipc("media", "previous"), "previous back music media song", "⏮", GREEN),
    # Brightness (bindings/media.lua; helpers.lua maps {brightness=...} to +5% / 5%-)
    entry("brightness-up", "Brightness Up", "Raise display brightness 5%", "display-brightness-high", ["omarchy-brightness-display", "+5%"], "brighter screen display backlight", "🔆", YELLOW),
    entry("brightness-down", "Brightness Down", "Lower display brightness 5%", "display-brightness-low", ["omarchy-brightness-display", "5%-"], "dimmer dim screen display backlight", "🔅", YELLOW),
    entry("brightness-max", "Brightness Maximum", "Set display brightness to 100%", "display-brightness-high", ["omarchy-brightness-display", "100%"], "full brightest screen display", "☀", YELLOW),
    entry("brightness-min", "Brightness Minimum", "Set display brightness to 1%", "display-brightness-low", ["omarchy-brightness-display", "1%"], "lowest darkest screen display", "🌑", YELLOW),
    entry("kbd-up", "Keyboard Backlight Up", "Raise keyboard backlight", "keyboard-brightness", ["omarchy-brightness-keyboard", "up"], "keyboard backlight brighter kbd", "⌨", YELLOW),
    entry("kbd-down", "Keyboard Backlight Down", "Lower keyboard backlight", "keyboard-brightness", ["omarchy-brightness-keyboard", "down"], "keyboard backlight dimmer kbd", "⌨", YELLOW),
    entry("kbd-cycle", "Keyboard Backlight Cycle", "Cycle keyboard backlight levels", "keyboard-brightness", ["omarchy-brightness-keyboard", "cycle"], "keyboard backlight toggle kbd", "⌨", YELLOW),
    # Bluetooth power (bin/omarchy-bluetooth-power)
    entry("bt-on", "Bluetooth On", "Turn Bluetooth on (remembered across reboots)", "bluetooth-active", ["omarchy-bluetooth-power", "on"], "bluetooth bt enable power radio", "🔵"),
    entry("bt-off", "Bluetooth Off", "Turn Bluetooth off (remembered across reboots)", "bluetooth-disabled", ["omarchy-bluetooth-power", "off"], "bluetooth bt disable power radio airplane", "⚪"),
    # Notifications (bindings/utilities.lua {ipc = "notifications.*"})
    entry("notif-dismiss", "Dismiss Notification", "Dismiss the latest notification", "notification-disabled", ipc("notifications", "dismissOne"), "notifications clear close dismiss last", "🔕", PURPLE),
    entry("notif-dismiss-all", "Dismiss All Notifications", "Clear every notification", "notification-disabled", ipc("notifications", "dismissAll"), "notifications clear all dismiss", "🔕", PURPLE),
    entry("notif-invoke", "Open Last Notification", "Invoke the latest notification's action", "preferences-system-notifications", ipc("notifications", "invokeLast"), "notifications invoke open last click", "🔔", PURPLE),
    entry("notif-history", "Notification History", "Show notification history", "preferences-system-notifications", ipc("notifications", "showHistory"), "notifications history log past", "📜", PURPLE),
    # Windows (bindings/utilities.lua, bindings/tiling.lua) - act on the focused window
    entry("win-transparency", "Toggle Window Transparency", "Make the focused window opaque or transparent", "preferences-desktop-effects", ["omarchy-hyprland-window-transparency-toggle"], "opacity transparent opaque window", "◐"),
    entry("win-pop", "Pop Window Out", "Float and pin the focused window", "window-pin", ["omarchy-hyprland-window-pop"], "float pin pop picture window", "📌"),
    entry("win-tiled-fullscreen", "Toggle Tiled Full Screen", "Full screen within the tiling layout", "view-fullscreen", ["omarchy-hyprland-window-tiled-fullscreen-toggle"], "fullscreen maximize tiled window", "⛶"),
    entry("win-minimize", "Minimize Window", "Minimize the focused window to the dock", "window-minimize", ["omarchy-hyprland-window-minimize"], "minimize hide dock window", "▁"),
    entry("fullscreen-desktop", "Toggle Full Screen Desktop", "Hide the bar and gaps for a full-screen desktop", "view-fullscreen", ["omarchy-toggle-fullscreen-desktop"], "fullscreen desktop zen focus bar", "⛶", YELLOW),
    entry("win-close-all", "Close All Windows", "Close every open window", "window-close", ["omarchy-hyprland-window-close-all"], "close quit kill all windows", "✖", RED,
          ("danger", "Close all windows?", "Closes every open application window (unsaved work may prompt or be lost).")),
    # Quick status (bindings/utilities.lua)
    entry("show-time", "Show Time", "Show the time as a notification", "preferences-system-time", ["omarchy-notification-time"], "time clock date now", "🕒", GREEN),
    entry("show-battery", "Show Battery Remaining", "Show battery level and time remaining", "battery-good", ["omarchy-notification-battery"], "battery charge power remaining", "🔋", GREEN),
    entry("agent-pick", "Pick Agent", "Launch an AI coding agent", "utilities-terminal", ["omarchy-agent", "--pick"], "ai agent coding assistant claude codex", "🤖", GREEN),
]


def score(query: str, item: dict) -> float:
    title = item["title"].lower()
    if title == query: return 0.95
    if title.startswith(query): return 0.92
    if any(word.startswith(query) for word in title.replace("/", " ").split()): return 0.82
    if query in title: return 0.7
    if any(word.startswith(query) for word in item["keywords"].split()): return 0.6
    if query in item["keywords"]: return 0.5
    if query in item["subtitle"].lower(): return 0.4
    return 0.0


def search(query: str) -> list[dict]:
    q = " ".join(query.strip().lower().split())
    if not q: return []
    ranked = sorted(((score(q, e), n, e) for n, e in enumerate(ENTRIES)), key=lambda t: (-t[0], t[1]))
    out: list[dict] = []
    for s, _, e in ranked:
        if s == 0.0 or len(out) >= MAX_RESULTS: break
        out.append({"id": "system:" + e["key"], "title": e["title"], "subtitle": e["subtitle"], "icon": e["icon"],
                    "fallbackIcon": e["fallbackIcon"], "fallbackColor": e["fallbackColor"], "keywords": e["keywords"],
                    "score": s, "provider": "system", "actions": e["actions"]})
    return out


def main() -> None:
    for line in sys.stdin:
        try: msg = json.loads(line)
        except json.JSONDecodeError: continue
        if not isinstance(msg, dict): continue
        op = msg.get("op")
        if op == "search": print(json.dumps({"id": msg.get("id", ""), "results": search(str(msg.get("query", "")))}), flush=True)
        elif op == "cancel": print(json.dumps({"id": msg.get("target", ""), "cancelled": True}), flush=True)
        elif op == "execute": print(json.dumps({"id": msg.get("id", ""), "executed": False, "error": "system actions are launched by the host"}), flush=True)


if __name__ == "__main__": main()
