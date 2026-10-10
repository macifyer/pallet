#!/usr/bin/env python3
"""Pallet core host.

Owns provider subprocesses and the query lifecycle the QML frontend drives:

    QML bridge --NDJSON--> host --NDJSON (fanout)--> providers
    QML bridge <--NDJSON-- host <--NDJSON (merge)--- providers

The protocol is defined in docs/PROVIDERS.md; this file is transport.
stdout belongs to the provider-worker messages; provider stderr is mirrored
with a prefix.
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
MERGE_TIMEOUT_S = 0.15  # latency budget, docs/PROVIDERS.md rule 4


def log(*args: object) -> None:
    print("host:", *args, file=sys.stderr, flush=True)


def discover_manifests() -> list[Path]:
    if not PROVIDERS_DIR.is_dir():
        return []
    found: list[Path] = []
    for entry in sorted(PROVIDERS_DIR.iterdir()):
        # Underscore convention: providers/_template is scaffolding,
        # never loaded as a live provider.
        if entry.name.startswith("_") or not entry.is_dir():
            continue
        manifest = entry / "manifest.json"
        if manifest.is_file():
            found.append(manifest)
        else:
            log(f"{entry.name}: no manifest.json; skipped")
    return found


def resolve_exec(argv: list[str]) -> list[str]:
    """Repo-relative path args become absolute; everything else passes through."""
    out: list[str] = []
    for arg in argv:
        if "/" in arg and not Path(arg).is_absolute():
            candidate = ROOT / arg
            out.append(str(candidate) if candidate.exists() else arg)
        else:
            out.append(arg)
    return out


class Provider:
    """One provider subprocess speaking docs/PROVIDERS.md NDJSON."""

    def __init__(self, name: str, argv: list[str], inbox: asyncio.Queue) -> None:
        self.name = name
        self.argv = argv
        self.inbox = inbox
        self.proc: asyncio.subprocess.Process | None = None

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def start(self) -> None:
        try:
            self.proc = await asyncio.create_subprocess_exec(
                *self.argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=ROOT,
            )
        except OSError as err:
            log(f"{self.name}: failed to start: {err}")
            return
        asyncio.create_task(self._read_stdout())
        asyncio.create_task(self._read_stderr())

    async def _read_stdout(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        async for raw in self.proc.stdout:
            line = raw.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                log(f"{self.name}: unparseable line {line[:120]!r}")
                continue
            await self.inbox.put((self.name, msg))
        # M2: respawn policy. A dead provider simply stops answering.
        log(f"{self.name}: exited")

    async def _read_stderr(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        async for raw in self.proc.stderr:
            log(f"{self.name}: {raw.decode(errors='replace').rstrip()}")

    async def send(self, msg: dict) -> None:
        if not self.alive or self.proc is None or self.proc.stdin is None:
            return
        try:
            self.proc.stdin.write(json.dumps(msg).encode() + b"\n")
            await self.proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as err:
            log(f"{self.name}: write failed: {err}")


class Host:
    def __init__(self) -> None:
        self.inbox: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()
        self.providers: list[Provider] = []
        self.merge_task: asyncio.Task | None = None
        self.latest_qid: str | None = None

    async def broadcast(self, msg: dict) -> None:
        await asyncio.gather(*(p.send(msg) for p in self.providers))

    async def discard_pending(self) -> None:
        """Input changed or was cancelled: stop merging, tell providers."""
        if self.merge_task is not None and not self.merge_task.done():
            self.merge_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.merge_task
        self.merge_task = None
        if self.latest_qid is not None:
            await self.broadcast({"id": "", "op": "cancel", "target": self.latest_qid})

    async def on_search(self, msg: dict) -> None:
        await self.discard_pending()
        self.latest_qid = str(msg.get("id", ""))
        await self.broadcast(msg)
        self.merge_task = asyncio.create_task(self._merge(self.latest_qid))

    async def on_cancel(self, msg: dict) -> None:
        target = str(msg.get("target", ""))
        if target == self.latest_qid:
            await self.discard_pending()
            self.latest_qid = None
        else:
            await self.broadcast(msg)

    async def on_execute(self, msg: dict) -> None:
        """A launch/copy/open action the frontend cannot do itself: send it
        to the provider that authored the result."""
        wanted = str(msg.get("provider", ""))
        for provider in self.providers:
            if provider.name == wanted:
                await provider.send({"id": msg.get("id", ""), "op": "execute", "action": msg.get("action")})
                return
        log(f"execute: no provider {wanted!r}")

    async def _merge(self, qid: str) -> None:
        """Collect the first response from each live provider, within budget."""
        pending = {p.name for p in self.providers if p.alive}
        merged: list[dict] = []
        deadline = time.monotonic() + MERGE_TIMEOUT_S

        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                name, msg = await asyncio.wait_for(self.inbox.get(), remaining)
            except asyncio.TimeoutError:
                break
            if msg.get("id") != qid or "results" not in msg:
                continue  # stale qid or trivia; single-merge makes this safe
            pending.discard(name)
            for result in msg["results"]:
                if isinstance(result, dict) and "provider" not in result:
                    result["provider"] = name
                merged.append(result)

        if pending:
            log(f"{qid}: merge deadline hit; slow: {sorted(pending)}")
        self.emit({"id": qid, "results": merged})

    @staticmethod
    def emit(msg: dict) -> None:
        print(json.dumps(msg, separators=(",", ":")), flush=True)


async def read_client(host: Host) -> None:
    """stdin from the QML bridge: search / cancel / execute ops, one JSON object per line."""
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(limit=1 << 16)
    await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), sys.stdin
    )
    while True:
        raw = await reader.readline()
        if not raw:
            return  # bridge is gone; shut down cleanly
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            log(f"unparseable client line {raw[:120]!r}")
            continue
        op = msg.get("op")
        if op == "search":
            await host.on_search(msg)
        elif op == "cancel":
            await host.on_cancel(msg)
        elif op == "execute":
            await host.on_execute(msg)
        else:
            log(f"unknown op {op!r}")


async def amain() -> None:
    host = Host()
    for manifest in discover_manifests():
        try:
            spec = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError as err:
            log(f"{manifest}: {err}")
            continue
        name = spec.get("name", manifest.parent.name)
        argv = spec.get("exec")
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
            log(f"{name}: manifest missing a valid exec array")
            continue
        host.providers.append(Provider(name, resolve_exec(argv), host.inbox))

    for provider in host.providers:
        await provider.start()
    log(f"providers up: {[p.name for p in host.providers if p.alive] or 'none'}")

    try:
        await read_client(host)
    finally:
        for p in host.providers:
            if p.alive and p.proc is not None:
                p.proc.terminate()


if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
