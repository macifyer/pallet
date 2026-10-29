"""Time budgets for tests that measure real subprocess timing.

Slow machines (a TCG VM, a loaded CI box) can set PALLET_TEST_TIME_SCALE,
for example 5. The scale is also calibrated once from this Python's own
start-up time, so budgets grow by themselves where every process is slow.
It is never below 1, so fast machines keep the original budgets; only the
time limits scale, never what a test checks.
"""
import os
import subprocess
import sys
import time

REFERENCE_STARTUP_S = 0.05  # `python3 -c pass` on an ordinary laptop
MAX_SCALE = 20.0
_scale = None


def scale() -> float:
    global _scale
    if _scale is None:
        try:
            forced = float(os.environ.get('PALLET_TEST_TIME_SCALE', '') or 0)
        except ValueError:
            forced = 0.0
        start = time.monotonic()
        subprocess.run([sys.executable, '-c', 'pass'], check=False)
        measured = min(MAX_SCALE, (time.monotonic() - start) / REFERENCE_STARTUP_S)
        _scale = max(1.0, forced, measured)
    return _scale


def budget(seconds: float) -> float:
    return seconds * scale()
