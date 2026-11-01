#!/usr/bin/env python3

from __future__ import annotations
import asyncio
import contextlib
import json
import os
import select
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
PROVIDERS_DIR = ROOT / "providers"

MERGE_TIMEOUT_S = 0.6

EARLY_EMIT_S = 0.012

COALESCE_S = 0.03

LATE_GRACE_S = 2.5
RESTART_BACKOFF_S = 30.0

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

LAUNCH_WATCH_S = 4.0
STDERR_CAP = 4096
_emit_lock = threading.Lock()
_action_log_lock = threading.Lock()
ENV_SNAPSHOT_KEYS = (
    "PATH", "OMARCHY_PATH", "HOME", "SHELL", "USER", "LOGNAME",
    "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR",
    "XDG_CURRENT_DESKTOP", "HYPRLAND_INSTANCE_SIGNATURE",
)

def omarchy_bin_dirs():
    roots = [os.environ.get("OMARCHY_PATH") or "", "/usr/share/omarchy",
             os.path.expanduser("~/.local/share/omarchy")]
    seen, out = set(), []
    for root in roots:
        d = os.path.join(root, "bin") if root else ""
        if d and d not in seen and os.path.isdir(d): seen.add(d); out.append(d)
    return out

def launch_env():
    env = dict(os.environ)
    parts = [p for p in env.get("PATH", "").split(":") if p]
    for d in omarchy_bin_dirs() + [os.path.expanduser("~/.local/bin")]:
        if d not in parts: parts.append(d)
    env["PATH"] = ":".join(parts or ["/usr/local/bin", "/usr/bin"])
    if not env.get("OMARCHY_PATH"):
        for d in omarchy_bin_dirs():
            env["OMARCHY_PATH"] = os.path.dirname(d); break
    return env

def action_log_path():
    # Unfinished: om:/s: rows still do not run in the Omarchy VM. Next agent: on a fresh boot, read this log (command, exit, stderr, PATH, OMARCHY_PATH) and fix the launch it shows dying.
    override = os.environ.get("PALLET_ACTION_LOG")
    if override == "0":
        return None
    if override:
        return Path(override)
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "pallet" / "actions.jsonl"

def env_snapshot(env):
    snap = {key: env.get(key, "") for key in ENV_SNAPSHOT_KEYS}
    snap.update({key: env[key] for key in env if key.startswith("XDG_") and key not in snap})
    snap["keys"] = sorted(env)
    return snap

def append_action_log(record, path):
    if path is None:
        return
    line = json.dumps(record, separators=(",", ":"), ensure_ascii=False)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _action_log_lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except OSError as err:
        log(f"action log: {err}")

def _stderr_text(chunks):
    return b"".join(chunks).decode("utf-8", "replace")[:STDERR_CAP]

def _read_stderr(fd, chunks, total):
    eof = False
    while True:
        try:
            data = os.read(fd, 65536)
        except BlockingIOError:
            return total, eof
        except OSError:
            return total, True
        if not data:
            return total, True
        if total < STDERR_CAP:
            take = data[:STDERR_CAP - total]
            chunks.append(take)
            total += len(take)

def _watch(proc, record, on_fail, path):
    fd = proc.stderr.fileno()
    os.set_blocking(fd, False)
    chunks, total = [], 0
    deadline = time.monotonic() + LAUNCH_WATCH_S
    code = None
    while True:
        total, eof = _read_stderr(fd, chunks, total)
        code = proc.poll()
        if code is not None:
            total, _eof = _read_stderr(fd, chunks, total)
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0 or eof:
            if eof:
                with contextlib.suppress(subprocess.TimeoutExpired):
                    code = proc.wait(timeout=max(0.0, remaining))
            break
        with contextlib.suppress(Exception):
            select.select([fd], [], [], min(0.2, remaining))
    record["stderr"] = _stderr_text(chunks)
    record["phase"] = "watch"
    record["exit"] = code
    record["running"] = code is None
    append_action_log(record, path)
    if code is None:
        threading.Thread(target=_follow, args=(proc, fd, dict(record), path), daemon=True).start()
        return
    label = record.get("label") or "command"
    if code in (126, 127):
        msg = f"command not found: {label}" if code == 127 else f"cannot run: {label}"
        log(f"launch failed: {msg}")
        if on_fail is not None: on_fail(msg[:300])
    elif code:
        log(f"launch: {record.get('label')} exited with status {code}")
    if proc.stderr is not None:
        with contextlib.suppress(Exception):
            proc.stderr.close()

def _follow(proc, fd, record, path):
    chunks, total = [], 0
    while True:
        with contextlib.suppress(Exception):
            select.select([fd], [], [], 1.0)
        total, eof = _read_stderr(fd, chunks, total)
        if eof or proc.poll() is not None:
            total, _eof = _read_stderr(fd, chunks, total)
            break
    with contextlib.suppress(Exception):
        record["exit"] = proc.wait()
    record["phase"] = "exit"
    record["running"] = False
    record["ts"] = time.time()
    record["stderr"] = _stderr_text(chunks)
    append_action_log(record, path)
    if proc.stderr is not None:
        with contextlib.suppress(Exception):
            proc.stderr.close()

def spawn_detached(argv=None, command=None, on_fail=None, action_id=""):
    env = launch_env()
    path = action_log_path()
    record = {"ts": time.time(), "id": action_id, "kind": "command" if command is not None else "argv",
              "env": env_snapshot(env)}
    if command is not None:
        if not isinstance(command, str) or not command.strip():
            record.update(phase="reject", error="invalid command", command=command if isinstance(command, str) else "")
            append_action_log(record, path)
            return "invalid command"
        full, label = ["bash", "-lc", command], command.split(None, 1)[0]
        record["command"] = command
    else:
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
            record.update(phase="reject", error="invalid command")
            append_action_log(record, path)
            return "invalid command"
        if shutil.which(argv[0], path=env["PATH"]) is None:
            err = f"command not found: {argv[0]}"
            record.update(phase="reject", error=err, argv=argv, label=argv[0], command=argv[0])
            append_action_log(record, path)
            return err
        full, label = ["bash", "-lc", 'exec "$@"', "bash", *argv], argv[0]
        record["argv"] = list(argv)
        record["command"] = " ".join(argv)
    record["label"] = label
    record["exec"] = full
    try:
        proc = subprocess.Popen(full, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                start_new_session=True, cwd=os.path.expanduser("~"), close_fds=True, env=env)
    except OSError as err:
        message = f"{label}: {err.strerror or err}"
        record.update(phase="reject", error=message)
        append_action_log(record, path)
        return message
    record["pid"] = proc.pid
    threading.Thread(target=_watch, args=(proc, record, on_fail, path), daemon=True).start()
    return None

class Host:
    def __init__(self, history=None):
        self.inbox = asyncio.Queue(); self.providers = []; self.merge_task = None; self.latest_qid = None
        self.history = history if history is not None else History(enabled=False)
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
        aid = msg.get("id", "")
        loop = asyncio.get_running_loop()
        def failed(error):
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(self.emit, {"id": aid, "executed": False, "error": error})
        if "command" in msg:
            call = lambda: spawn_detached(command=msg.get("command"), on_fail=failed, action_id=aid)
        else:
            call = lambda: spawn_detached(msg.get("argv"), on_fail=failed, action_id=aid)
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
