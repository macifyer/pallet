#!/usr/bin/env python3
"""Search files and directories under $HOME.

The index is built in a background thread with fd when available (respects
the provider's own exclude list verbatim), otherwise os.walk with the same
names pruned. A cold build publishes chunks as it goes, so the first query
answers immediately from what is indexed (marked partial, with one follow-up
when the build completes). Stale indexes (INDEX_TTL_S) rebuild in the
background while the old one keeps serving. No per-entry stat() at build time.

Search: candidates come from a packed lowercase haystack per chunk (str.find),
are narrowed incrementally while the user types forward, scored, reduced with
a top-k heap, and only the top candidates are stat()ed for the recency nudge.

The primary Enter action is context-aware: code/text files open in your
editor ($VISUAL/$EDITOR, GUI editors direct, terminal editors via foot -e),
markdown inside an Obsidian vault (any ancestor holding .obsidian/) opens in
Obsidian, and everything else falls through to the xdg-open MIME default —
which intentionally stays available afterwards for odd defaults.
"""

from __future__ import annotations

import heapq
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from bisect import bisect_right
from pathlib import Path
from typing import Any
from urllib.parse import quote

HOME = Path.home()
INDEX_TTL_S = 60
MIN_QUERY_LEN = 3
MAX_RESULTS = 12
MAX_ENTRIES = 60_000

PRUNE = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".cache",
    ".npm", ".rustup", ".cargo", ".mozilla", ".config/chromium",
    ".local/share/Trash", "vendor/bundle", "dist-newstyle",
}

GUI_EDITORS = ("code", "codium", "zed", "kate", "subl", "gedit", "mousepad")
TERM_EDITORS = ("hx", "helix", "nvim", "vim", "nano", "emacs")
MARKDOWN_SUFFIXES = {".md", ".markdown"}

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

def fd_available() -> bool:
    return shutil.which("fd") is not None


PRUNE_PATHS = {p for p in PRUNE if "/" in p}


def skipped(rel_parts: tuple[str, ...]) -> bool:
    # Single names prune anywhere; multi-segment entries (".config/chromium")
    # prune that path prefix (and any nested occurrence).
    if any(part in PRUNE for part in rel_parts):
        return True
    joined = "/".join(rel_parts)
    return any(joined == p or joined.startswith(p + "/") or ("/" + p + "/") in ("/" + joined + "/") for p in PRUNE_PATHS)


CHUNK = 4096            # entries per searchable chunk
PUBLISH_EVERY_S = 0.05  # cold build: publish partial chunks this often
RECENCY_CANDIDATES = 48 # stat() only this many best candidates per query


class Chunk:
    """A slice of the index packed into one lowercase haystack string.

    Candidate generation is a C-speed `str.find` over the haystack; every
    score tier requires the query as a substring of the lowercase relative
    path, so nothing outside the hits can rank.
    """
    __slots__ = ("rels", "lowers", "dirs", "starts", "hay")

    def __init__(self, rels: list[str], dirs: list[bool]):
        self.rels = rels
        self.lowers = [rel.lower() for rel in rels]
        self.dirs = dirs
        starts = []
        pos = 0
        for rel in rels:
            starts.append(pos)
            pos += len(rel) + 1
        self.starts = starts
        self.hay = "\n".join(self.lowers) + "\n"

    def hits(self, q: str):
        hay, starts, find = self.hay, self.starts, self.hay.find
        pos = find(q)
        while pos != -1:
            i = bisect_right(starts, pos) - 1
            yield i
            nxt = starts[i + 1] if i + 1 < len(starts) else len(hay)
            pos = find(q, nxt)


class Index:
    def __init__(self):
        self.chunks: list[Chunk] = []
        self.complete = False
        self.version = 0
        self.built_at = 0.0

    def count(self) -> int:
        return sum(len(c.rels) for c in self.chunks)


_index = Index()
_lock = threading.Lock()
_building = threading.Event()
_on_complete = None  # callback(Index) run on the builder thread


def iter_fd():
    """Yield (rel, is_dir) from fd: directories first, then files."""
    base = ["fd", "--hidden", "--color", "never", "--base-directory", str(HOME)]
    for name in sorted(PRUNE):
        base += ["--exclude", name]
    yielded = 0
    for kind, is_dir in (("d", True), ("f", False)):
        cmd = base + ["--type", kind, "--max-results", str(MAX_ENTRIES), "."]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        except OSError:
            return
        try:
            for line in proc.stdout:
                rel = line.rstrip("\n").rstrip("/")
                if rel.startswith("./"):
                    rel = rel[2:]
                if not rel or skipped(Path(rel).parts):
                    continue
                yield rel, is_dir
                yielded += 1
                if yielded >= MAX_ENTRIES:
                    return
        finally:
            proc.kill() if proc.poll() is None else None
            proc.wait()


def iter_walk():
    for dirpath, dirnames, filenames in os.walk(HOME):
        rel_dir = Path(dirpath).relative_to(HOME)
        if skipped(rel_dir.parts):
            dirnames[:] = []
            continue
        prefix = "" if str(rel_dir) == "." else str(rel_dir) + "/"
        dirnames[:] = [d for d in dirnames if d not in PRUNE and not skipped(Path(prefix + d).parts)]
        for name in dirnames:
            yield prefix + name, True
        for name in filenames:
            yield prefix + name, False


def build_index(publish_partial: bool | None = None) -> Index:
    """Build a fresh index. A cold build publishes chunks as they fill so
    searches see partial results within milliseconds; a refresh keeps
    serving the previous index and swaps atomically at the end."""
    global _index
    cold = not _index.complete if publish_partial is None else publish_partial
    fresh = Index()
    fresh.version = _index.version + 1
    if cold:
        with _lock:
            _index = fresh
    rels: list[str] = []
    dirs: list[bool] = []
    last_publish = time.monotonic()
    source = iter_fd() if fd_available() else iter_walk()
    total = 0
    try:
        for rel, is_dir in source:
            rels.append(rel)
            dirs.append(is_dir)
            total += 1
            now = time.monotonic()
            if len(rels) >= CHUNK or (cold and now - last_publish >= PUBLISH_EVERY_S and rels):
                chunk = Chunk(rels, dirs)
                with _lock:
                    fresh.chunks = fresh.chunks + [chunk]
                    fresh.version += 1
                rels, dirs = [], []
                last_publish = now
            if total >= MAX_ENTRIES:
                break
    except OSError as err:
        print(f"files: index error: {err}", file=sys.stderr, flush=True)
    with _lock:
        if rels:
            fresh.chunks = fresh.chunks + [Chunk(rels, dirs)]
        fresh.version += 1
        fresh.complete = True
        fresh.built_at = time.time()
        _index = fresh
    return fresh


def _build_worker():
    try:
        built = build_index()
        cb = _on_complete
        if cb is not None:
            cb(built)
    finally:
        _building.clear()


def start_build() -> bool:
    """Start a background (re)build unless one is running."""
    if _building.is_set():
        return False
    _building.set()
    threading.Thread(target=_build_worker, name="files-index", daemon=True).start()
    return True


def ensure_fresh() -> None:
    """Never blocks: kicks a background rebuild when the index is stale."""
    if not _index.complete and not _building.is_set():
        start_build()
    elif _index.complete and time.time() - _index.built_at > INDEX_TTL_S:
        start_build()


def icon_for(path: str, is_dir: bool) -> str:
    if is_dir:
        return "folder"
    return ICON_BY_SUFFIX.get(Path(path).suffix.lower(), "text-x-generic")


def is_text_like(is_dir: bool, rel: str) -> bool:
    if is_dir:
        return False
    return ICON_BY_SUFFIX.get(Path(rel).suffix.lower(), "").startswith("text-")


def terminal_here(directory: str) -> list[str]:
    # Omarchy's default terminal entry point (bin/omarchy-launch-terminal uses
    # xdg-terminal-exec --dir); foot is the fallback from the base packages.
    if shutil.which("xdg-terminal-exec"):
        return ["xdg-terminal-exec", "--dir=" + directory]
    return ["foot", "--working-directory", directory]


def editor_argv(path: str) -> list[str] | None:
    # Omarchy's editor launcher honours Setup > Defaults > Editor
    # (bin/omarchy-launch-editor).
    if shutil.which("omarchy-launch-editor"):
        return ["omarchy-launch-editor", path]
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


def in_obsidian_vault(parent: Path) -> bool:
    """A markdown file belongs to Obsidian iff an ancestor holds .obsidian/."""
    cur = parent
    while True:
        if (cur / ".obsidian").is_dir():
            return True
        if cur == HOME or cur == cur.parent:
            return False
        cur = cur.parent


def display_parent(rel: str) -> str:
    parent = str(Path(rel).parent)
    return "~/" + parent if parent != "." else "~/"


WORD_BOUNDARY = frozenset("_-/. ")


def base_score(query: str, rel_lower: str, is_dir: bool) -> float:
    """Basename prefix 0.9 > word prefix anywhere in the path 0.78 >
    basename substring 0.62 > path substring 0.45 (0 = no match)."""
    pos = rel_lower.find(query)
    if pos < 0:
        return 0.0
    cut = rel_lower.rfind("/") + 1
    if rel_lower.startswith(query, cut):
        base = 0.9
    else:
        base = 0.0
        while pos != -1:
            if pos == 0 or rel_lower[pos - 1] in WORD_BOUNDARY:
                base = 0.78
                break
            pos = rel_lower.find(query, pos + 1)
        if base == 0.0:
            base = 0.62 if rel_lower.find(query, cut) != -1 else 0.45
    if is_dir:
        base -= 0.03
    return base - 0.005 * (rel_lower.count("/") - 1)


def recency_bonus(mtime: float) -> float:
    age_days = (time.time() - mtime) / 86400 if mtime else 365
    return 0.04 if age_days < 7 else (0.02 if age_days < 30 else 0.0)


def score(query: str, rel_lower: str, is_dir: bool, mtime: float) -> float:
    base = base_score(query, rel_lower, is_dir)
    if base == 0.0:
        return 0.0
    return min(0.97, base + recency_bonus(mtime))


def actions_for(rel: str, is_dir: bool) -> list[dict]:
    path = str(HOME / rel)
    parent_rel = str(Path(rel).parent)
    parent = str(HOME / parent_rel) if parent_rel != "." else str(HOME)
    mime_open: dict[str, Any] = {"type": "open", "title": "Open", "url": path}

    if is_dir:
        return [
            mime_open,
            {"type": "launch", "title": "Open terminal here", "argv": terminal_here(path)},
            {"type": "copy", "title": "Copy path", "text": path},
        ]

    actions: list[dict[str, Any]] = []
    suffix = Path(rel).suffix.lower()
    if suffix in MARKDOWN_SUFFIXES and in_obsidian_vault(Path(parent)) and shutil.which("obsidian"):
        uri = "obsidian://open?path=" + quote(path)
        actions.append({"type": "launch", "title": "Open in Obsidian", "argv": ["obsidian", uri]})
    elif is_text_like(is_dir, rel):
        argv = editor_argv(path)
        if argv:
            actions.append({"type": "launch", "title": "Open in editor", "argv": argv})
    actions += [
        mime_open,
        {"type": "open", "title": "Open containing folder", "url": parent},
        {"type": "launch", "title": "Open terminal here", "argv": terminal_here(parent)},
        {"type": "copy", "title": "Copy path", "text": path},
    ]
    return actions


# Typing forward only narrows substring hits, so the previous query's
# candidates are reused when the new query extends it on the same index.
_last: dict[str, Any] = {"q": "", "version": -1, "cands": None}


_search_lock = threading.Lock()


def candidates(q: str) -> list[tuple[str, str, bool]]:
    with _search_lock:
        return _candidates(q)


def _candidates(q: str) -> list[tuple[str, str, bool]]:
    with _lock:
        index = _index
        chunks = index.chunks
        version = index.version
    last = _last
    if last["cands"] is not None and last["version"] == version and last["q"] and q.startswith(last["q"]):
        cands = [c for c in last["cands"] if q in c[1]]
    else:
        cands = []
        for chunk in chunks:
            rels, lowers, dirs = chunk.rels, chunk.lowers, chunk.dirs
            cands.extend((rels[i], lowers[i], dirs[i]) for i in chunk.hits(q))
    _last.update(q=q, version=version, cands=cands)
    return cands


def search(query: str) -> list[dict]:
    q = query.strip().lower()
    if len(q) < MIN_QUERY_LEN:
        return []
    ensure_fresh()
    scored = ((base_score(q, low, d), rel, d) for rel, low, d in candidates(q))
    top = heapq.nlargest(RECENCY_CANDIDATES, (t for t in scored if t[0] > 0.0), key=lambda t: t[0])
    final = []
    for base, rel, is_dir in top:
        try:
            mtime = (HOME / rel).stat().st_mtime
        except OSError:
            mtime = 0.0
        final.append((min(0.97, base + recency_bonus(mtime)), rel, is_dir))
    final.sort(key=lambda t: (-t[0], t[1]))
    out: list[dict] = []
    for s, rel, is_dir in final[:MAX_RESULTS]:
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


_out_lock = threading.Lock()


def send(msg: dict) -> None:
    with _out_lock:
        print(json.dumps(msg), flush=True)


def main() -> None:
    global _on_complete
    # A query answered while the cold index was still filling gets one
    # follow-up reply (same id) once the index completes, unless cancelled.
    waiting: dict[str, str] = {}
    waiting_lock = threading.Lock()

    def on_complete(_built: Index) -> None:
        with waiting_lock:
            pending = dict(waiting)
            waiting.clear()
        for qid, query in pending.items():
            send({"id": qid, "results": search(query)})

    _on_complete = on_complete
    start_build()
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        op = msg.get("op")
        if op == "search":
            qid = str(msg.get("id", ""))
            query = str(msg.get("query", ""))
            was_complete = _index.complete
            results = search(query)
            if was_complete or len(query.strip()) < MIN_QUERY_LEN:
                send({"id": qid, "results": results})
                continue
            with waiting_lock:
                waiting.clear()
                waiting[qid] = query
            send({"id": qid, "results": results, "partial": True})
            if _index.complete:
                # The build finished while we searched; answer now.
                with waiting_lock:
                    late = waiting.pop(qid, None)
                if late is not None:
                    send({"id": qid, "results": search(late)})
        elif op == "cancel":
            with waiting_lock:
                waiting.pop(str(msg.get("target", "")), None)
            send({"id": msg.get("target", ""), "cancelled": True})
        elif op == "warm":
            ensure_fresh()
        elif op == "execute":
            send({"id": msg.get("id", ""), "executed": False})


if __name__ == "__main__":
    main()
