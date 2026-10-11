#!/usr/bin/env python3
"""Search installed applications via XDG .desktop entries.

Advisory-scored results; final ordering happens in the frontend's Fuzzy.rank.
Launch actions are raw argv arrays — never shell strings.

Entries are skipped when their binary cannot be resolved: TryExec when the
file declares it (per the freedesktop spec), otherwise the Exec argv[0].
This hides the .desktop debris an uninstall leaves behind — pacman removes
tracked files, but user-level entries (Wine, AppImages, web-app shortcuts)
survive the death of the binary they point at.

Desktop entries may declare extra ways to invoke the app through the
Actions= key and [Desktop Action ...] groups (new window, private window,
profile picker, ...). The spec expects launchers to expose these, so each
one surfaces here as a titled launch action — no per-app code anywhere.
"""

import json
import os
import shlex
import shutil
import sys
from pathlib import Path

XDG_DIRS = [
    Path.home() / ".local/share/applications",
    Path.home() / ".local/share/flatpak/exports/share/applications",
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
    Path("/var/lib/flatpak/exports/share/applications"),
]

# Exec field codes (%u, %F, ...) are launch-time placeholders. They must
# never reach execDetached as literal arguments.
FIELD_MARK = "%"

MAX_RESULTS = 15
MAX_DESKTOP_ACTIONS = 6  # panel caps at 320px; 6 + Launch + Copy name fits


def resolves(token: str) -> bool:
    """Whether an executable token names a runnable program."""
    if not token:
        return False
    if "/" in token:
        return os.access(token, os.X_OK)
    return shutil.which(token) is not None


def split_exec(exec_line: str) -> list[str]:
    try:
        tokens = shlex.split(exec_line, posix=True)
    except ValueError:  # unbalanced quoting exists in the wild
        tokens = exec_line.split()
    return [t for t in tokens if not t.startswith(FIELD_MARK)]


def parse_desktop(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    section: str | None = None
    fields: dict[str, str] = {}
    action_groups: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if not section or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if section == "Desktop Entry":
            fields.setdefault(key, value)
        elif section.startswith("Desktop Action "):
            group = action_groups.setdefault(section.removeprefix("Desktop Action "), {})
            group.setdefault(key, value)

    if fields.get("Type", "Application") != "Application":
        return None
    lowered = {k.lower(): v for k, v in fields.items()}
    if lowered.get("nodisplay") == "true" or lowered.get("hidden") == "true":
        return None

    name = fields.get("Name", "")
    argv = split_exec(fields.get("Exec", ""))
    if not name or not argv:
        return None
    if lowered.get("terminal") == "true":
        return None  # needs a terminal wrapper; out of M1 scope

    # Ghost filter: honor TryExec per spec; then require the Exec binary
    # itself to resolve. Wrappers like `env` or `flatpak` resolve fine;
    # binaries removed by an uninstall do not.
    try_exec = fields.get("TryExec", "")
    if try_exec and not resolves(try_exec):
        return None
    if not resolves(argv[0]):
        return None

    # freedesktop "Additional applications actions": every id in Actions=
    # names a [Desktop Action <id>] group with its own Name/Exec. These are
    # the app's self-declared extras (e.g. Firefox "New Private Window").
    desktop_actions: list[dict] = []
    for action_id in (a for a in fields.get("Actions", "").split(";") if a):
        group = action_groups.get(action_id, {})
        action_name = group.get("Name", "").strip()
        action_argv = split_exec(group.get("Exec", ""))
        if not action_name or not action_argv:
            continue
        if not resolves(action_argv[0]):
            continue
        desktop_actions.append({"title": action_name, "argv": action_argv})
        if len(desktop_actions) >= MAX_DESKTOP_ACTIONS:
            break

    return {
        "name": name,
        "subtitle": fields.get("GenericName") or fields.get("Comment", ""),
        "icon": fields.get("Icon", ""),
        "argv": argv,
        "desktop_actions": desktop_actions,
        "keywords": fields.get("Keywords", "").replace(";", " ").lower(),
    }


def load_apps() -> list[dict]:
    seen: set[str] = set()  # per-desktop-file dedupe across XDG dirs
    apps: list[dict] = []
    for directory in XDG_DIRS:
        if not directory.is_dir():
            continue
        for desktop in sorted(directory.glob("*.desktop")):
            if desktop.name in seen:
                continue
            seen.add(desktop.name)
            app = parse_desktop(desktop)
            if app is not None:
                apps.append(app)
    apps.sort(key=lambda a: a["name"].lower())
    return apps


def score(query: str, app: dict) -> float:
    name = app["name"].lower()
    if name.startswith(query):
        return 0.95
    if any(word.startswith(query) for word in name.split()):
        return 0.85
    if query in name:
        return 0.7
    if query in app["subtitle"].lower() or query in app["keywords"]:
        return 0.45
    return 0.0


def actions_for(app: dict) -> list[dict]:
    actions = [{"type": "launch", "title": "Launch", "argv": app["argv"]}]
    for desktop_action in app["desktop_actions"]:
        actions.append({
            "type": "launch",
            "title": desktop_action["title"],
            "argv": desktop_action["argv"],
        })
    actions.append({"type": "copy", "title": "Copy name", "text": app["name"]})
    return actions


def search(query: str, apps: list[dict]) -> list[dict]:
    q = query.strip().lower()
    if not q:
        return []
    ranked = sorted(
        ((score(q, app), app) for app in apps),
        key=lambda pair: pair[0],
        reverse=True,
    )
    out: list[dict] = []
    for s, app in ranked:
        if s == 0.0 or len(out) >= MAX_RESULTS:
            break
        out.append(
            {
                "id": f"apps:{app['name']}",
                "title": app["name"],
                "subtitle": app["subtitle"],
                "icon": app["icon"],
                "keywords": app["keywords"],
                "score": s,
                "provider": "apps",
                "actions": actions_for(app),
            }
        )
    return out


def main() -> None:
    apps = load_apps()
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("op") == "search":
            results = search(str(msg.get("query", "")), apps)
            print(json.dumps({"id": msg.get("id", ""), "results": results}), flush=True)
        elif msg.get("op") == "cancel":
            print(json.dumps({"id": msg.get("target", ""), "cancelled": True}), flush=True)
        elif msg.get("op") == "execute":
            print(json.dumps({"id": msg.get("id", ""), "executed": False}), flush=True)


if __name__ == "__main__":
    main()
