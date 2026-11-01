#!/usr/bin/env python3
"""Measure Pallet host latency: time-to-first and time-to-final per query.

The bench copies the plugin into a temporary directory, points the host at a
synthetic $HOME (so the files provider indexes a realistic tree without
touching real data), optionally adds a slow "straggler" provider that stands
in for a heavy AT-SPI menu walk, and then drives the host over its normal
NDJSON stdin/stdout contract.

  python3 scripts/bench_host.py                 # default scenario
  python3 scripts/bench_host.py --files 60000 --straggler-ms 1500 --json

Older hosts emit one message per query; newer hosts may emit early partial
messages and mark the last one with "final": true. Both are handled: a message
without a "final" key is treated as final.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import select
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORDS = ("notes report config project invoice draft photo screenshot budget "
         "meeting todo readme design src lib test build docs archive music "
         "video thesis resume letter plan backup theme dotfiles scripts").split()
EXTS = (".md", ".txt", ".py", ".pdf", ".png", ".jpg", ".json", ".toml", ".sh", ".lua")
WARM_QUERIES = ("fire", "lock", "screenshot", "theme", "notes", "report.pdf",
                "f:budget", "reboot", "term", "config")
TYPING = ("c", "co", "con", "conf", "confi", "config")

STRAGGLER = r'''#!/usr/bin/env python3
import json, sys, time
DELAY = float(sys.argv[1])
for line in sys.stdin:
    try: msg = json.loads(line)
    except json.JSONDecodeError: continue
    if msg.get("op") != "search": continue
    time.sleep(DELAY)
    print(json.dumps({"id": msg["id"], "results": [{"id": "slow:" + msg["query"],
          "title": "Slow " + msg["query"], "score": 0.3,
          "actions": [{"type": "copy", "text": "x"}]}]}), flush=True)
'''


def make_home(count: int) -> Path:
    home = Path(tempfile.gettempdir()) / f"pallet-bench-home-{count}"
    marker = home / ".pallet-bench-complete"
    if marker.exists():
        return home
    shutil.rmtree(home, ignore_errors=True)
    rng = random.Random(42)
    made = 0
    dirs = [home]
    while made < count:
        parent = rng.choice(dirs)
        if len(dirs) < count // 20 and rng.random() < 0.08:
            d = parent / f"{rng.choice(WORDS)}-{made}"
            d.mkdir(parents=True, exist_ok=True)
            dirs.append(d)
        else:
            parent.mkdir(parents=True, exist_ok=True)
            name = f"{rng.choice(WORDS)}_{rng.choice(WORDS)}_{made}{rng.choice(EXTS)}"
            (parent / name).touch()
        made += 1
    marker.touch()
    return home


def stage_plugin(straggler_ms: int) -> Path:
    stage = Path(tempfile.mkdtemp(prefix="pallet-bench-"))
    for part in ("src", "providers"):
        shutil.copytree(ROOT / part, stage / part, ignore=shutil.ignore_patterns("__pycache__"))
    if straggler_ms > 0:
        d = stage / "providers" / "slowpoke"
        d.mkdir()
        (d / "provider.py").write_text(STRAGGLER)
        (d / "manifest.json").write_text(json.dumps({
            "name": "slowpoke", "exec": ["python3", "providers/slowpoke/provider.py", str(straggler_ms / 1000)]}))
    return stage


class HostClient:
    def __init__(self, stage: Path, home: Path):
        env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / ".local/share"))
        env.pop("OMARCHY_PATH", None)
        self.t0 = time.monotonic()
        self.proc = subprocess.Popen([sys.executable, str(stage / "src" / "host.py")], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, cwd=stage, text=True, bufsize=1)
        self.buf = ""
        self.n = 0

    def send(self, msg):
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def readline(self, timeout: float):
        end = time.monotonic() + timeout
        while "\n" not in self.buf:
            left = end - time.monotonic()
            if left <= 0:
                return None
            ready, _, _ = select.select([self.proc.stdout], [], [], left)
            if not ready:
                return None
            chunk = os.read(self.proc.stdout.fileno(), 65536).decode()
            if not chunk:
                return None
            self.buf += chunk
        line, self.buf = self.buf.split("\n", 1)
        return json.loads(line) if line.strip() else {}

    def query(self, text: str, timeout: float = 5.0, sent_at: float | None = None):
        self.n += 1
        qid = f"b{self.n}"
        start = sent_at if sent_at is not None else time.monotonic()
        self.send({"id": qid, "op": "search", "query": text})
        first = final = None
        first_files = None
        count = 0
        while True:
            msg = self.readline(max(0.0, start + timeout - time.monotonic()))
            if msg is None:
                break
            if msg.get("id") != qid or "results" not in msg:
                continue
            now = (time.monotonic() - start) * 1000
            first = now if first is None else first
            if first_files is None and any(r.get("provider") == "files" for r in msg["results"]):
                first_files = now
            count = len(msg["results"])
            if msg.get("final", True):
                final = now
                break
        return {"query": text, "first_ms": first, "final_ms": final, "files_ms": first_files, "results": count}

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=3)
        except Exception:
            self.proc.kill()


def fmt(v):
    return "  -  " if v is None else f"{v:7.1f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--files", type=int, default=60000, help="synthetic $HOME entries (default 60000)")
    ap.add_argument("--straggler-ms", type=int, default=0, help="add a provider that answers after N ms")
    ap.add_argument("--rounds", type=int, default=3, help="warm rounds per query (median reported)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    home = make_home(args.files)
    stage = stage_plugin(args.straggler_ms)
    report = {"files": args.files, "straggler_ms": args.straggler_ms, "cold": None, "warm": [], "typing": []}
    try:
        client = HostClient(stage, home)
        # Cold: query the instant the host is spawned, like a palette opened at login.
        cold = client.query("notes", timeout=15.0, sent_at=client.t0)
        report["cold"] = cold
        # Let background work (if any) settle before measuring warm latency.
        time.sleep(2.0)
        client.query("warmup", timeout=5.0)
        for q in WARM_QUERIES:
            runs = [client.query(q) for _ in range(args.rounds)]
            report["warm"].append({
                "query": q,
                "first_ms": statistics.median([r["first_ms"] or 0 for r in runs]),
                "final_ms": statistics.median([r["final_ms"] or 0 for r in runs]),
                "results": runs[-1]["results"],
            })
        for q in TYPING:
            report["typing"].append(client.query(q))
        client.close()
    finally:
        shutil.rmtree(stage, ignore_errors=True)

    if args.json:
        print(json.dumps(report, indent=2))
        return
    c = report["cold"]
    print(f"synthetic HOME entries: {args.files}   straggler: {args.straggler_ms or 'none'} ms")
    print(f"cold 'notes' (sent at spawn): first {fmt(c['first_ms'])} ms  final {fmt(c['final_ms'])} ms  files {fmt(c['files_ms'])} ms")
    print(f"{'query':<14}{'first ms':>10}{'final ms':>10}{'results':>9}")
    for r in report["warm"]:
        print(f"{r['query']:<14}{fmt(r['first_ms']):>10}{fmt(r['final_ms']):>10}{r['results']:>9}")
    w = report["warm"]
    print(f"{'median':<14}{fmt(statistics.median(r['first_ms'] for r in w)):>10}{fmt(statistics.median(r['final_ms'] for r in w)):>10}")
    print("typing 'config' one key at a time:")
    for r in report["typing"]:
        print(f"  {r['query']:<12}{fmt(r['first_ms']):>10}{fmt(r['final_ms']):>10}{r['results']:>9}")


if __name__ == "__main__":
    main()
