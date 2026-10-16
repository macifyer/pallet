#!/usr/bin/env python3
"""Pallet core host with provider-scoped prefixes.

`files:`/`f:`, `obsidian:`/`o:`, and `apps:`/`app:` focus matching providers.
The prefix is stripped before providers see it; responses echo `scope` and
`bare` so the UI rankings match what providers matched.
"""
from __future__ import annotations
import asyncio
import contextlib
import json
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
PROVIDERS_DIR = ROOT / "providers"
MERGE_TIMEOUT_S = 0.5
SCOPES = {"f": "files", "file": "files", "files": "files", "o": "obsidian", "ob": "obsidian", "obsidian": "obsidian", "a": "apps", "app": "apps", "apps": "apps"}

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

class Provider:
    def __init__(self, name, argv, inbox): self.name, self.argv, self.inbox, self.proc = name, argv, inbox, None
    @property
    def alive(self): return self.proc is not None and self.proc.returncode is None
    async def start(self):
        try: self.proc = await asyncio.create_subprocess_exec(*self.argv, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=ROOT)
        except OSError as err: log(f"{self.name}: failed to start: {err}"); return
        asyncio.create_task(self._read_stdout()); asyncio.create_task(self._read_stderr())
    async def _read_stdout(self):
        async for raw in self.proc.stdout:
            line = raw.strip()
            if not line: continue
            try: msg = json.loads(line)
            except json.JSONDecodeError: continue
            await self.inbox.put((self.name, msg))
        log(f"{self.name}: exited")
    async def _read_stderr(self):
        async for raw in self.proc.stderr: log(f"{self.name}: {raw.decode(errors='replace').rstrip()}")
    async def send(self, msg):
        if not self.alive: return
        try: self.proc.stdin.write(json.dumps(msg).encode()+b"\n"); await self.proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError): pass

class Host:
    def __init__(self): self.inbox = asyncio.Queue(); self.providers = []; self.merge_task = None; self.latest_qid = None
    async def send_to(self, names, msg):
        chosen = [p for p in self.providers if names is None or p.name in names]
        await asyncio.gather(*(p.send(msg) for p in chosen), return_exceptions=True)
    async def discard_pending(self):
        if self.merge_task and not self.merge_task.done():
            self.merge_task.cancel()
            with contextlib.suppress(asyncio.CancelledError): await self.merge_task
        if self.latest_qid is not None: await self.send_to(None, {"id":"","op":"cancel","target":self.latest_qid})
    async def on_search(self, msg):
        scope, bare = split_scope(str(msg.get("query", "")))
        await self.discard_pending(); self.latest_qid = str(msg.get("id", ""))
        names = {p.name for p in self.providers if scope == "" or p.name == scope}
        await self.send_to(names, {"id": self.latest_qid, "op": "search", "query": bare})
        self.merge_task = asyncio.create_task(self._merge(self.latest_qid, names, scope, bare))
    async def on_cancel(self, msg): await self.discard_pending()
    async def on_execute(self, msg):
        wanted = str(msg.get("provider", ""))
        for provider in self.providers:
            if provider.name == wanted:
                await provider.send({"id": msg.get("id", ""), "op": "execute", "action": msg.get("action")}); return
    async def _merge(self, qid, names, scope, bare):
        pending = {p.name for p in self.providers if p.alive and p.name in names}
        merged = []; deadline = time.monotonic() + MERGE_TIMEOUT_S
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0: break
            try: name, msg = await asyncio.wait_for(self.inbox.get(), remaining)
            except asyncio.TimeoutError: break
            if msg.get("id") != qid or "results" not in msg or name not in pending: continue
            pending.discard(name)
            for result in msg["results"]:
                if isinstance(result, dict): result.setdefault("provider", name); merged.append(result)
        self.emit({"id": qid, "results": merged, "scope": scope, "bare": bare})
    @staticmethod
    def emit(msg): print(json.dumps(msg, separators=(",", ":")), flush=True)

async def read_client(host):
    loop = asyncio.get_running_loop(); reader = asyncio.StreamReader(limit=1 << 16)
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
    while True:
        raw = await reader.readline()
        if not raw: return
        try: msg = json.loads(raw)
        except json.JSONDecodeError: continue
        if msg.get("op") == "search": await host.on_search(msg)
        elif msg.get("op") == "cancel": await host.on_cancel(msg)
        elif msg.get("op") == "execute": await host.on_execute(msg)

async def amain():
    host = Host()
    for manifest in discover_manifests():
        try: spec = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError: continue
        argv = spec.get("exec")
        if isinstance(argv, list) and argv and all(isinstance(a, str) for a in argv):
            host.providers.append(Provider(spec.get("name", manifest.parent.name), resolve_exec(argv), host.inbox))
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
