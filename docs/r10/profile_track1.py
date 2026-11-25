"""R10: where a Track 1 scan spends its time. One process (workers = 1), cProfile, no literature search.

    uv run python docs/r10/profile_track1.py PORTAL X_AXIS Y_AXIS OUT_FOLDER     # e.g. higgs_portal_scalar m_chi:11:9000:log:4 g_chi:1e-5:10:log:4

Prints the wall time, the DIAMX subprocess calls and their time, and the twenty most expensive functions.
"""

from __future__ import annotations

import cProfile
import pstats
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def axis(text: str):
    from adroit.parameter_space.scan import Axis
    name, low, high, scale, n = text.split(":")
    return Axis(parameter=name, low=float(low), high=float(high), log=scale == "log", n=int(n))


def main(argv: list[str]) -> int:
    from adroit.experiments import xenon
    from adroit.orchestrator import track1
    portal, x, y, out = argv
    calls = []
    original = xenon.DiamxXenon._run_locked

    def timed(self, *args, **kwargs):
        start = time.time()
        try:
            return original(self, *args, **kwargs)
        finally:
            calls.append((self.search, time.time() - start))
    xenon.DiamxXenon._run_locked = timed
    request = track1.for_portal(portal, x=axis(x), y=axis(y), workers=1, literature=False)
    profile = cProfile.Profile()
    start = time.time()
    profile.enable()
    result = track1.run(request, Path(out))
    profile.disable()
    wall = time.time() - start
    print(f"wall {wall:.0f} s; verdict {result.verdict.level}; DIAMX runs {len(calls)}, {sum(t for _, t in calls):.0f} s")
    for search in sorted({s for s, _ in calls}):
        print(f"  {search}: {sum(1 for s, _ in calls if s == search)} runs, {sum(t for s, t in calls if s == search):.0f} s")
    pstats.Stats(profile).sort_stats("cumulative").print_stats(25)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
