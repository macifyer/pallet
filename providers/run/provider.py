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

PATH discovery is conservative: the PATH directories are only listed
(os.scandir + one stat per entry for the executable bit, re-listed when a
directory's mtime changes). Nothing found is ever run to learn about it (no
--help, no --version, no .desktop parsing). An exact command name offers
"Command: <name>"; `run:<prefix>` also lists prefix matches. These rows are
fallbacks too, confirm-gated, and run the bare command in a visible terminal.
"""
from __future__ import annotations
import json
import os
import re
import stat
import sys

MIN_LEN = 3
MAX_PATH_ROWS = 5
NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,79}")


class PathIndex:
    """Executable names on PATH, by listing directories only."""

    def __init__(self, path: str | None = None):
        self.path = path
        self.dirs: dict[str, tuple[float, frozenset[str]]] = {}
        self._union: tuple[tuple, set[str]] = ((), set())

    def _dirs(self) -> list[str]:
        raw = os.environ.get("PATH", "") if self.path is None else self.path
        seen, out = set(), []
        for d in raw.split(os.pathsep):
            if d and os.path.isabs(d) and d not in seen:
                seen.add(d); out.append(d)
        return out

    def _list(self, d: str) -> frozenset[str]:
        names = set()
        try:
            with os.scandir(d) as it:
                for e in it:
                    if not NAME_RE.fullmatch(e.name): continue
                    try:
                        st = e.stat()  # follows symlinks; never opens or runs the file
                    except OSError:
                        continue
                    if stat.S_ISREG(st.st_mode) and st.st_mode & 0o111:
                        names.add(e.name)
        except OSError:
            pass
        return frozenset(names)

    def names(self) -> set[str]:
        stamp, parts = [], []
        for d in self._dirs():
            try: mtime = os.stat(d).st_mtime
            except OSError: continue
            cached = self.dirs.get(d)
            if not cached or cached[0] != mtime:
                cached = (mtime, self._list(d))
                self.dirs[d] = cached
            stamp.append((d, mtime)); parts.append(cached[1])
        if self._union[0] != tuple(stamp):
            self._union = (tuple(stamp), set().union(*parts))
        return self._union[1]


INDEX = PathIndex()


def command_row(name: str, score: float) -> dict:
    return {
        "id": "run:cmd:" + name, "fallback": True, "title": f"Command: {name}",
        "subtitle": "Found on PATH · runs in a foot terminal", "icon": "utilities-terminal",
        "fallbackIcon": "❯", "keywords": name, "score": score, "provider": "run",
        "actions": [{
            "type": "launch", "title": "Run in terminal", "argv": ["foot", "--", name],
            "danger": "confirm", "tone": "warning",
            "confirmation": {"title": f"Run '{name}'?",
                             "detail": "Opens a visible foot terminal running this PATH command with no arguments. Pallet never ran it to discover it."},
        }, {"type": "copy", "title": "Copy command", "text": name}],
    }


def discover(q: str, scoped: bool, index: PathIndex) -> list[dict]:
    if not NAME_RE.fullmatch(q): return []
    names = index.names()
    rows = [command_row(q, 0.3)] if q in names else []
    if scoped:
        rows += [command_row(n, 0.28) for n in sorted(n for n in names if n.startswith(q) and n != q)[:MAX_PATH_ROWS - len(rows)]]
    return rows


def search(query: str, scope: str = "", index: PathIndex | None = None) -> list[dict]:
    q = query.strip()
    if len(q) < MIN_LEN: return []
    found = discover(q, scope == "run", INDEX if index is None else index)
    return found + run_row(q)


def run_row(q: str) -> list[dict]:
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
            print(json.dumps({"id": msg.get("id", ""), "results": search(str(msg.get("query", "")), str(msg.get("scope", "")))}), flush=True)
        elif msg.get("op") == "warm":
            INDEX.names()
        elif msg.get("op") == "cancel":
            print(json.dumps({"id": msg.get("target", ""), "cancelled": True}), flush=True)
        elif msg.get("op") == "execute":
            print(json.dumps({"id": msg.get("id", ""), "executed": False, "error": "run actions are launched by the host"}), flush=True)

if __name__ == "__main__": main()
