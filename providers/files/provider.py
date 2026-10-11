#!/usr/bin/env python3
"""Search files and directories under $HOME.

The index is built once at startup with fd when available (respects the
provider's own exclude list verbatim), otherwise os.walk with the same
names pruned. It refreshes lazily after INDEX_TTL_S of staleness. Search
scores basename first, then path components, and nudges recent files up.

Text/code files gain an Open-in-editor action: $VISUAL/$EDITOR wins; GUI
editors launch directly, terminal editors via foot -e. xdg-open remains the
default Open — some desktops attach plain text to odd handlers like
browsers.

Actions are plain launch/open argv; no custom execute capability is needed.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HOME = Path.home()
INDEX_TTL_S = 60
MIN_QUERY_LEN = 3
MAX_RESULTS = 12
MAX_ENTRIES = 60_000

# Names pruned wherever they appear: build output, VCS internals, package
# caches — places where a search hit is nearly never what the user wants.
PRUNE = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".cache",
    ".npm", ".rustup", ".cargo", ".mozilla", ".config/chromium",
    ".local/share/Trash", "vendor/bundle", "dist-newstyle",
}

GUI_EDITORS = ("code", "codium", "zed", "kate", "subl", "gedit", "mousepad")
TERM_EDITORS = ("hx", "helix", "nvim", "vim", "nano", "emacs")

ICON_BY_SUFFIX: dict[str, str] = {
    ".png": "image-x-generic", ".jpg": "image-x-generic", ".jpeg": "image-x-generic",
    ".gif": "image-x-generic", ".webp": "image-x-generic", ".svg": "image-x-generic",
    ".pdf": "application-pdf",
    ".mp3": "audio-x-generic", ".flac": "audio-x-generic", ".ogg": "audio-x-generic",
    ".wav": "audio-x-generic", ".m4a": "audio-x-generic",
    ".mp4": "video-x-generic", ".mkv": "video-x-generic", ".webm": "video-x-generic",
    ".zip": "package-x-generic", ".tar": "package-x-generic", ".gz": "package-x-generic",
    ".xz": "package-x-generic", ".zst": "package-x-generic",
    ".py": "text-x-script", ".sh": "text-x-script", ".js": "text-x-script",
    ".ts": "text-x-script", ".lua": "text-x-script", ".rs": "text-x-script",
    ".md": "text-markdown", ".txt": "text-x-generic",
    ".json": "text-x-generic", ".toml": "text-x-generic", ".yaml": "text-x-generic",
    ".yml": "text-x-generic", ".html": "text-html", ".css": "text-css",
}

_index: list[tuple[str, str, bool, float]] = []  # (path, lower, is_dir, mtime)
_index_built_at = 0.0


def fd_available() -> bool:
    return shutil.which("fd") is not None


def skipped(rel_parts: tuple[str, ...]) -> bool:
    return any(part in PRUNE for part in rel_parts)


def build_index() -> None:
    global _index, _index_built_at
    entries: list[tuple[str, str, bool, float]] = []
    if fd_available():
        cmd = ["fd", "--type", "f", "--type", "d", "--hidden"]
        for name in sorted(PRUNE):
            cmd += ["--exclude", name]
        cmd += [".", str(HOME)]
        try:
            out = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=10).stdout
            for line in out.splitlines()[:MAX_ENTRIES]:
                path = HOME / line
                rel = Path(line)
                if skipped(rel.parts):
                    continue
                is_dir = line.endswith("os.sep") or path.is_dir()
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    mtime = 0.0
                entries.append((line.rstrip("/"), line.lower(), is_dir, mtime))
        except (OSError, subprocess.TimeoutExpired):
            entries = []
    if not entries:  # os.walk fallback (also covers fd-with-no-matches edge)
        for dirpath, dirnames, filenames in os.walk(HOME):
            rel_dir = Path(dirpath).relative_to(HOME)
            if skipped(rel_dir.parts):
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d not in PRUNE]
            for name in dirnames + filenames:
                rel = str(rel_dir / name) if str(rel_dir) != "." else name
                full = Path(dirpath) / name
                is_dir = name in dirnames
                try:
                    mtime = full.stat().st_mtime
                except OSError:
                    mtime = 0.0
                entries.append((rel, rel.lower(), is_dir, mtime))
                if len(entries) >= MAX_ENTRIES:
                    _index = entries
                    _index_built_at = time.time()
                    return
    _index = entries
    _index_built_at = time.time()


def ensure_fresh() -> None:
    if not _index or time.time() - _index_built_at > INDEX_TTL_S:
        build_index()


def icon_for(path: str, is_dir: bool) -> str:
    if is_dir:
        return "folder"
    suffix = Path(path).suffix.lower()
    return ICON_BY_SUFFIX.get(suffix, "text-x-generic")


def is_text_like(is_dir: bool, path: str) -> bool:
    if is_dir:
        return False
    suffix = Path(path).suffix.lower()
    icon = ICON_BY_SUFFIX.get(suffix, "")
    return icon.startswith("text-")


def editor_argv(path: str) -> list[str] | None:
    """$VISUAL/$EDITOR first; GUI editors direct, terminal editors via foot."""
    explicit = os.environ.get("VISUAL") or os.environ.get("EDITOR") or ""
    if explicit:
        try:
            cmd = shlex.split(explicit)
        except ValueError:
            cmd = explicit.split()
        if not cmd:
            return None
        name = Path(cmd[0]).name
        if name in GUI_EDITORS:
            return cmd + [path]
        return ["foot", "-e"] + cmd + [path]
    for name in GUI_EDITORS:
        if shutil.which(name):
            return [name, path]
    for name in TERM_EDITORS:
        if shutil.which(name):
            return ["foot", "-e", name, path]
    return None


def display_parent(rel: str) -> str:
    parent = str(Path(rel).parent)
    return "~/" + parent if parent != "." else "~/"


def score(query: str, rel_lower: str, is_dir: bool, mtime: float) -> float:
    name = rel_lower.rsplit("/", 1)[-1]
    if name.startswith(query):
        base = 0.9
    elif any(part.startswith(query) for part in rel_lower.replace("_", " ").replace("-", " ").replace("/", " ").split()):
        base = 0.78
    elif query in name:
        base = 0.62
    elif query in rel_lower:
        base = 0.45
    else:
        return 0.0
    if is_dir:
        base -= 0.03  # files usually win ties with their containing folder
    age_days = (time.time() - mtime) / 86400 if mtime else 365
    base += 0.04 if age_days < 7 else (0.02 if age_days < 30 else 0.0)
    return min(0.97, base - 0.005 * (rel_lower.count("/") - 1))  # deep paths lose slightly


def actions_for(rel: str, is_dir: bool) -> list[dict]:
    path = str(HOME / rel)
    parent = str(HOME / str(Path(rel).parent)) if str(Path(rel).parent) != "." else str(HOME)
    actions: list[dict[str, Any]] = [
        {"type": "open", "title": "Open", "url": path},
    ]
    if is_dir:
        actions.append({"type": "launch", "title": "Open terminal here", "argv": ["foot", "--working-directory", path]})
    else:
        if is_text_like(is_dir, rel):
            argv = editor_argv(path)
            if argv:
                actions.append({"type": "launch", "title": "Open in editor", "argv": argv})
        actions.append({"type": "open", "title": "Open containing folder", "url": parent})
        actions.append({"type": "launch", "title": "Open terminal here", "argv": ["foot", "--working-directory", parent]})
    actions.append({"type": "copy", "title": "Copy path", "text": path})
    return actions


def search(query: str) -> list[dict]:
    q = query.strip().lower()
    if len(q) < MIN_QUERY_LEN:
        return []
    ensure_fresh()
    ranked = sorted(
        ((score(q, rel_lower, is_dir, mtime), rel, is_dir) for rel, rel_lower, is_dir, mtime in _index),
        key=lambda pair: pair[0],
        reverse=True,
    )
    out: list[dict] = []
    for s, rel, is_dir in ranked:
        if s == 0.0 or len(out) >= MAX_RESULTS:
            break
        name = rel.rsplit("/", 1)[-1]
        out.append({
            "id": "files:" + rel,
            "title": name,
            "subtitle": display_parent(rel),
            "icon": icon_for(rel, is_dir),
            "keywords": " ".join(rel.lower().rsplit("/")[:-1]),
            "fallbackIcon": "\U0001f4c1" if is_dir else "\U0001f4c4",
            "score": s,
            "provider": "files",
            "actions": actions_for(rel, is_dir),
        })
    return out


def main() -> None:
    build_index()
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
