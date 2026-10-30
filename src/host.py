#!/usr/bin/env python3
"""Pallet core host: fans a query out to providers and streams merged results.

Scope prefixes (`files:`/`f:`, `obsidian:`/`o:`, `apps:`/`a:`, `omarchy:`/`om:`,
`system:`/`sys:`, `windows:`/`w:`, `menus:`/`m:`, `plugins:`/`p:`, `run:`,
`web:`) focus one provider. The prefix is stripped before providers see it;
responses echo `scope` and `bare` so UI ranking matches what providers matched.

Streaming contract (backwards compatible): every message for a query carries
the *complete* merged result set so far, so a consumer that only keeps the
last message per id still sees everything. Early messages carry
`"final": false` and list the providers still `pending`; the final message has
`"final": true` and lists `unresolved` providers (timed out or failed). A
provider that answers after the deadline produces one more final message with
the late results while its query is still current.
"""
from __future__ import annotations
import asyncio
import contextlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
PROVIDERS_DIR = ROOT / "providers"
# Deadline for the final message (footer reports providers missing it).
MERGE_TIMEOUT_S = 0.6
# First partial emit waits this long after the request so near-simultaneous
# replies land in one paint instead of several.
EARLY_EMIT_S = 0.012
# Later partial emits are coalesced to at most one per window.
COALESCE_S = 0.03
# After the final message, keep listening this long for stragglers (only while
# the client is connected) so slow providers still show up instead of vanishing.
LATE_GRACE_S = 2.5
RESTART_BACKOFF_S = 30.0
# Frecency: chosen results get a small `recent` boost (0..1) the frontend
# folds into ranking *within* a match tier. Typed commands are never stored.
HISTORY_MAX = 400
HISTORY_HALF_LIFE_S = 14 * 86400
HISTORY_SKIP = {"run"}
SCOPES = {
    "f": "files", "file": "files", "files": "files",
    "o": "obsidian", "ob": "obsidian", "obsidian": "obsidian",
    "a": "apps", "app": "apps", "apps": "apps",
    "om": "omarchy", "omarchy": "omarchy", "menu": "omarchy",
    "s": "system", "sys": "system", "system": "system",
    "w": "windows", "win": "windows", "window": "windows", "windows": "windows",
    "m": "menus", "menus": "menus",
    "p": "plugins", "plugin": "plugins", "plugins": "plugins",
    "run": "run",
    "web": "defaults", "default": "defaults", "defaults": "defaults",
}

def log(*args): print("host:", *args, file=sys.stderr, flush=True)

def discover_manifests():
    found = []
    if not PROVIDERS_DIR.is_dir(): return found
    for entry in sorted(PROVIDERS_DIR.iterdir()):
        if entry.name.startswith("_") or not entry.is_dir(): continue
        manifest = entry / "manifest.json"
        if manifest.is_file(): found.append(manifest)
    return found

def resolve_exec(argv):
    out = []
    for arg in argv:
        candidate = ROOT / arg
        out.append(str(candidate) if "/" in arg and not Path(arg).is_absolute() and candidate.exists() else arg)
    return out

def split_scope(query: str) -> tuple[str, str]:
    text = query.strip()
    if ":" not in text: return "", text
    prefix, rest = text.split(":", 1)
    scope = SCOPES.get(prefix.strip().lower())
    if not scope: return "", text
    return scope, rest.strip()

def _int(value, default=0):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else default

def history_path():
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "pallet" / "history.json"

class History:
    """Per-result use counts with exponential decay, persisted as JSON.

    Disabled with PALLET_HISTORY=0. Keys match the frontend's Fuzzy.keyOf:
    provider + NUL + (id or title)."""
    def __init__(self, path=None, enabled=None):
        self.enabled = os.environ.get("PALLET_HISTORY", "1") != "0" if enabled is None else enabled
        self.path = path or history_path()
        self.entries: dict[str, list] = {}
        if self.enabled: self._load()
    def _load(self):
        try: data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError): return
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(key, str) and isinstance(value, list) and len(value) == 2 \
                        and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
                    self.entries[key] = [float(value[0]), float(value[1])]
    @staticmethod
    def key(provider, rid, title=""):
        return f"{provider}\0{rid or title}"
    def record(self, provider, rid, title="", now=None):
        if not self.enabled or not isinstance(provider, str) or not provider or provider in HISTORY_SKIP: return
        if not (rid or title): return
        now = time.time() if now is None else now
        key = self.key(provider, rid, title)
        weight, at = self.entries.get(key, (0.0, now))
        self.entries[key] = [self._decayed(weight, at, now) + 1.0, now]
        if len(self.entries) > HISTORY_MAX:
            for stale in sorted(self.entries, key=lambda k: self.entries[k][1])[:len(self.entries) - HISTORY_MAX]:
                del self.entries[stale]
        self._save()
    @staticmethod
    def _decayed(weight, at, now):
        return weight * 0.5 ** (max(0.0, now - at) / HISTORY_HALF_LIFE_S)
    def score(self, provider, rid, title="", now=None):
        entry = self.entries.get(self.key(provider, rid, title))
        if not entry: return 0.0
        weight = self._decayed(entry[0], entry[1], time.time() if now is None else now)
        return round(min(1.0, weight / 5.0), 3)
    def annotate(self, rows):
        if not self.enabled or not self.entries: return
        now = time.time()
        for row in rows:
            value = self.score(row.get("provider", ""), row.get("id", ""), row.get("title", ""), now)
            if value > 0 and "recent" not in row: row["recent"] = value
    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.entries, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as err:
            log(f"history: could not save: {err}")

class Provider:
    def __init__(self, name, argv, inbox, spec=None, on_reply=None):
        spec = spec or {}
        self.name, self.argv, self.inbox, self.proc = name, argv, inbox, None
        self.on_reply = on_reply
        # Routing hints from the manifest. `minQuery`: skip unscoped queries
        # shorter than this. `scopedOnly`: only answer when explicitly scoped.
        self.min_query = _int(spec.get("minQuery"), 0)
        self.scoped_only = spec.get("scopedOnly") is True
        self.started_at = 0.0
        self.restarts = 0
    @property
    def alive(self): return self.proc is not None and self.proc.returncode is None
    def wants(self, scope: str, bare: str) -> bool:
        if scope: return scope == self.name
        if self.scoped_only: return False
        return len(bare) >= self.min_query
    async def start(self):
        self.started_at = time.monotonic()
        try: self.proc = await asyncio.create_subprocess_exec(*self.argv, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=ROOT, limit=1 << 22)
        except OSError as err: log(f"{self.name}: failed to start: {err}"); self.proc = None; return
        asyncio.create_task(self._read_stdout(self.proc)); asyncio.create_task(self._read_stderr(self.proc))
    async def ensure_running(self):
        """Restart a crashed provider at most once per backoff window."""
        if self.alive or time.monotonic() - self.started_at < RESTART_BACKOFF_S: return
        self.restarts += 1
        log(f"{self.name}: restarting (attempt {self.restarts})")
        await self.start()
    async def _read_stdout(self, proc):
        try:
            async for raw in proc.stdout:
                line = raw.strip()
                if not line: continue
                try: msg = json.loads(line)
                except json.JSONDecodeError: continue
                if not isinstance(msg, dict): continue
                if "executed" in msg and self.on_reply is not None:
                    # Action replies go straight to the client; they never
                    # belong to a search merge.
                    self.on_reply(self.name, msg); continue
                await self.inbox.put((self.name, msg))
        except (ValueError, asyncio.LimitOverrunError) as err:
            log(f"{self.name}: unreadable output: {err}")
        log(f"{self.name}: exited")
    async def _read_stderr(self, proc):
        async for raw in proc.stderr: log(f"{self.name}: {raw.decode(errors='replace').rstrip()}")
    async def send(self, msg):
        if not self.alive: return
        try: self.proc.stdin.write(json.dumps(msg).encode()+b"\n"); await self.proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError): pass

# Launches mirror how Omarchy itself runs commands (shell/Commons/Util.qml):
# argv through `bash -lc 'exec "$@"'` (Util.execArgv) and menu action strings
# through `bash -lc <action>` (Util.execDetached, what Menu.qml runAction does).
# The login shell sources /etc/profile.d/omarchy.sh (default/bash/env-bootstrap),
# so omarchy-* scripts get OMARCHY_PATH and PATH even when the shell process
# that started this host has a thinner environment. Stdin/stdout are detached
# and the child gets its own session, so closing the palette never kills it.
LAUNCH_WATCH_S = 4.0
_emit_lock = threading.Lock()

def omarchy_bin_dirs():
    roots = [os.environ.get("OMARCHY_PATH") or "", "/usr/share/omarchy",
             os.path.expanduser("~/.local/share/omarchy")]
    seen, out = set(), []
    for root in roots:
        d = os.path.join(root, "bin") if root else ""
        if d and d not in seen and os.path.isdir(d): seen.add(d); out.append(d)
    return out

def launch_env():
    """Environment for launched commands: PATH also covers Omarchy's bin dirs
    (dev-linked or ~/.local/share installs) and OMARCHY_PATH is set if missing."""
    env = dict(os.environ)
    parts = [p for p in env.get("PATH", "").split(":") if p]
    for d in omarchy_bin_dirs() + [os.path.expanduser("~/.local/bin")]:
        if d not in parts: parts.append(d)
    env["PATH"] = ":".join(parts or ["/usr/local/bin", "/usr/bin"])
    if not env.get("OMARCHY_PATH"):
        for d in omarchy_bin_dirs():
            env["OMARCHY_PATH"] = os.path.dirname(d); break
    return env

def _watch(proc, label, on_fail):
    """Report a launch that dies quickly with a non-zero status; otherwise
    just reap it. stderr is not captured: a pipe would kill long-running apps
    with SIGPIPE once the host goes away, and a file would grow unbounded."""
    code = None
    with contextlib.suppress(Exception):
        code = proc.wait(timeout=LAUNCH_WATCH_S)
    if code is None:
        with contextlib.suppress(Exception): proc.wait()
        return
    if code in (126, 127):
        # The shell could not find or run it: always worth a notification.
        msg = f"command not found: {label}" if code == 127 else f"cannot run: {label}"
        log(f"launch failed: {msg}")
        if on_fail is not None: on_fail(msg[:300])
    elif code:
        # Pickers exit 1 on Esc, toggles report state: log only, no popup.
        log(f"launch: {label} exited with status {code}")

def spawn_detached(argv=None, command=None, on_fail=None):
    """Run argv (or a trusted Omarchy menu action string) detached through a
    login shell. Returns an error string or None; a quick non-zero exit is
    reported later through on_fail."""
    env = launch_env()
    if command is not None:
        if not isinstance(command, str) or not command.strip():
            return "invalid command"
        full, label = ["bash", "-lc", command], command.split(None, 1)[0]
    else:
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
            return "invalid command"
        if shutil.which(argv[0], path=env["PATH"]) is None:
            return f"command not found: {argv[0]}"
        full, label = ["bash", "-lc", 'exec "$@"', "bash", *argv], argv[0]
    try:
        proc = subprocess.Popen(full, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True, cwd=os.path.expanduser("~"), close_fds=True, env=env)
    except OSError as err:
        return f"{label}: {err.strerror or err}"
    threading.Thread(target=_watch, args=(proc, label, on_fail), daemon=True).start()
    return None

class Host:
    def __init__(self, history=None):
        self.inbox = asyncio.Queue(); self.providers = []; self.merge_task = None; self.latest_qid = None
        self.history = history if history is not None else History(enabled=False)
        # True while the client's stdin is open; enables late straggler emits.
        self.listening = False
    def on_provider_reply(self, name, msg):
        reply = {"id": msg.get("id", ""), "executed": msg.get("executed") is True, "provider": name}
        if isinstance(msg.get("error"), str): reply["error"] = msg["error"][:300]
        self.emit(reply)
    def add_provider(self, name, argv, spec=None):
        self.providers.append(Provider(name, argv, self.inbox, spec, self.on_provider_reply))
    async def send_to(self, names, msg):
        chosen = [p for p in self.providers if names is None or p.name in names]
        await asyncio.gather(*(p.send(msg) for p in chosen), return_exceptions=True)
    async def discard_pending(self):
        if self.merge_task and not self.merge_task.done():
            self.merge_task.cancel()
            with contextlib.suppress(asyncio.CancelledError): await self.merge_task
        if self.latest_qid is not None: await self.send_to(None, {"id":"","op":"cancel","target":self.latest_qid})
    def route(self, scope, bare):
        return {p.name for p in self.providers if p.wants(scope, bare)}
    async def on_search(self, msg):
        scope, bare = split_scope(str(msg.get("query", "")))
        await self.discard_pending(); self.latest_qid = str(msg.get("id", ""))
        names = self.route(scope, bare)
        for p in self.providers:
            if p.name in names: await p.ensure_running()
        await self.send_to(names, {"id": self.latest_qid, "op": "search", "query": bare, "scope": scope})
        self.merge_task = asyncio.create_task(self._merge(self.latest_qid, names, scope, bare))
    async def on_cancel(self, msg):
        if str(msg.get("target", "")) != self.latest_qid:
            return
        await self.discard_pending()
        self.latest_qid = None
        self.merge_task = None
    async def on_warm(self, msg):
        # The overlay opened: let providers refresh caches before the first key.
        await self.send_to(None, {"id": "", "op": "warm"})
    async def on_execute(self, msg):
        wanted = str(msg.get("provider", ""))
        aid = msg.get("id", "")
        for provider in self.providers:
            if provider.name == wanted:
                if not provider.alive:
                    self.emit({"id": aid, "executed": False, "provider": wanted, "error": f"{wanted} provider is not running"}); return
                await provider.send({"id": aid, "op": "execute", "action": msg.get("action")}); return
        self.emit({"id": aid, "executed": False, "provider": wanted, "error": f"unknown provider: {wanted or '?'}"})
    async def on_record(self, msg):
        self.history.record(msg.get("provider"), str(msg.get("result", "")), str(msg.get("title", "")))
    async def on_launch(self, msg):
        """Launch argv, or a menu action string (`command`), on the frontend's
        behalf so failures are reported, including a quick non-zero exit."""
        aid = msg.get("id", "")
        loop = asyncio.get_running_loop()
        def failed(error):
            with contextlib.suppress(RuntimeError):  # loop already closed at shutdown
                loop.call_soon_threadsafe(self.emit, {"id": aid, "executed": False, "error": error})
        if "command" in msg:
            call = lambda: spawn_detached(command=msg.get("command"), on_fail=failed)
        else:
            call = lambda: spawn_detached(msg.get("argv"), on_fail=failed)
        err = await loop.run_in_executor(None, call)
        reply = {"id": aid, "executed": err is None}
        if err: reply["error"] = err; log(f"launch failed: {err}")
        self.emit(reply)
    async def _merge(self, qid, names, scope, bare):
        started = time.monotonic()
        pending = {p.name for p in self.providers if p.alive and p.name in names}
        failed = set(names) - pending
        by_provider: dict[str, list] = {}
        order = [p.name for p in self.providers]
        deadline = started + MERGE_TIMEOUT_S
        late_until = deadline + LATE_GRACE_S
        dirty = False
        emitted_final = False
        next_emit = started + EARLY_EMIT_S

        def snapshot(final):
            merged = []
            for name in order:
                merged.extend(by_provider.get(name, ()))
            msg = {"id": qid, "results": merged, "scope": scope, "bare": bare, "final": final,
                   "pending": sorted(pending), "unresolved": sorted(pending | failed) if final else [],
                   "failed": sorted(failed)}
            return msg

        while True:
            now = time.monotonic()
            if not pending:
                self.emit(snapshot(True)); return
            if not emitted_final and now >= deadline:
                unresolved = sorted(pending | failed)
                if unresolved: log(f"{qid}: no reply from: {unresolved}")
                self.emit(snapshot(True)); emitted_final = True; dirty = False
            if emitted_final and (not self.listening or now >= late_until):
                return
            if dirty and not emitted_final and now >= next_emit:
                self.emit(snapshot(False)); dirty = False; next_emit = now + COALESCE_S
            wake = late_until if emitted_final else deadline
            if dirty and not emitted_final: wake = min(wake, next_emit)
            try: name, msg = await asyncio.wait_for(self.inbox.get(), max(0.0, wake - time.monotonic()))
            except asyncio.TimeoutError: continue
            if msg.get("id") != qid or name not in pending: continue
            if msg.get("cancelled") is True:
                pending.discard(name); continue
            if "results" not in msg or not isinstance(msg["results"], list): continue
            rows = []
            for result in msg["results"]:
                if isinstance(result, dict): result.setdefault("provider", name); rows.append(result)
            self.history.annotate(rows)
            by_provider[name] = rows
            if msg.get("partial") is not True: pending.discard(name)
            if emitted_final:
                # A straggler after the deadline: refresh the final view.
                self.emit(snapshot(True))
            else:
                dirty = True
    @staticmethod
    def emit(msg):
        line = json.dumps(msg, separators=(",", ":"))
        with _emit_lock: print(line, flush=True)

async def read_client(host):
    loop = asyncio.get_running_loop(); reader = asyncio.StreamReader(limit=1 << 16)
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
    host.listening = True
    try:
        while True:
            raw = await reader.readline()
            if not raw: return
            try: msg = json.loads(raw)
            except json.JSONDecodeError: continue
            if not isinstance(msg, dict): continue
            op = msg.get("op")
            if op == "search": await host.on_search(msg)
            elif op == "cancel": await host.on_cancel(msg)
            elif op == "execute": await host.on_execute(msg)
            elif op == "launch": await host.on_launch(msg)
            elif op == "warm": await host.on_warm(msg)
            elif op == "record": await host.on_record(msg)
    finally:
        host.listening = False

async def amain():
    host = Host(History())
    for manifest in discover_manifests():
        try: spec = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError: continue
        if not isinstance(spec, dict): continue
        argv = spec.get("exec")
        if isinstance(argv, list) and argv and all(isinstance(a, str) for a in argv):
            host.add_provider(spec.get("name", manifest.parent.name), resolve_exec(argv), spec)
    for p in host.providers: await p.start()
    log(f"providers up: {[p.name for p in host.providers if p.alive] or 'none'}")
    try:
        await read_client(host)
        # A pipe closes stdin immediately after its last request. Let that
        # search finish within the existing merge budget before shutdown.
        if host.merge_task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await host.merge_task
    finally:
        if host.merge_task is not None and not host.merge_task.done():
            host.merge_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await host.merge_task
        processes = [p.proc for p in host.providers if p.proc is not None]
        for proc in processes:
            if proc.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    proc.terminate()
        for proc in processes:
            try:
                await asyncio.wait_for(proc.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                await proc.wait()

if __name__ == "__main__":
    try: asyncio.run(amain())
    except KeyboardInterrupt: pass
