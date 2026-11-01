
import os
import subprocess
import sys
import time

REFERENCE_STARTUP_S = 0.05
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
