"""The portal library's part 5: the validation gates of docs/portal_library_5.md, run and tabulated.

``uv run python scripts/validate_portal_library_5.py`` (local; about 20 s). Prints a Markdown table and exits non-zero
if a gate fails. The ranges were declared after the development runs (docs, section 5): regression guards.
"""

from __future__ import annotations

import math
import sys
import time

import numpy as np

from adroit.constraints import searches as s
from adroit.parameter_space import resonances as rs
from adroit.parameter_space import scan
from adroit.parameter_space import searches as ps
from adroit.parameter_space.classes import Point
from adroit.parameter_space.library import ENTRIES, TWO_HDM_A


def monoh_gates() -> list[tuple[str, float, float, float, str]]:
    """Our mono-Higgs recast at ATLAS's own benchmark (tan β = 1, sin θ = 0.35) against ATLAS's verdict and σ."""
    data = s._bundled("atlas-2108.13391-monoh")
    agree = total = 0
    ratios = []
    for m_big, m_a, theory in data["benchmark_sigma"]:
        cls = rs._reference(TWO_HDM_A, 0.35, m_big)
        p = Point(m_chi=10.0, m_med=m_a, g_chi=1.0, g_q=0.35, g_l=1.0)
        out = rs.monoh(cls, p, True)
        if out is None or out.excluded is None:
            continue
        atlas = next(r[2] for r in data["sigma95"] if r[:2] == [m_big, m_a]) < theory
        total += 1
        agree += out.excluded == atlas
        ratios.append(1e3 * rs._resonant_rates(cls, p)["h"] / theory)
    return [(f"2HDM+a mono-h: verdicts agreeing with ATLAS's at its grid points with a narrow A ({total})",
             agree / total, 0.95, 1.0, "ATLAS's σ₉₅ against its benchmark σ (arXiv:2108.13391)"),
            (f"2HDM+a mono-h: median σ(resonant, ours) / ATLAS's benchmark σ, narrow A (the {total} decided points)",
             float(np.median(ratios)), 0.7, 1.1, "ATLAS's σ includes non-resonant diagrams: ours should be at or below it")]


def monoz_gate() -> tuple[str, float, float, float, str]:
    """Plumbing: on ATLAS's own sin θ = 0.35 plane the monotone rule must return the contour's verdict."""
    contour = s._bundled("atlas-2111.08372-monoz")["contours"]["0.35"]
    agree = total = 0
    for m_a in (150.0, 250.0, 350.0):
        for m_big in (500.0, 700.0, 900.0, 1100.0):
            cls = rs._reference(TWO_HDM_A, 0.35, m_big)
            out = rs.monoz(cls, Point(m_chi=10.0, m_med=m_a, g_chi=1.0, g_q=0.35, g_l=1.0), True)
            if out is None or out.excluded is None:
                continue
            total += 1
            agree += out.excluded == rs._inside(contour, m_a, m_big)
    return (f"2HDM+a mono-Z on ATLAS's own plane: the contour's verdict ({total} points; plumbing)", agree / total, 1.0,
            1.0, "the reference model is the point itself")


def dijet_gate() -> tuple[str, float, float, float, str]:
    """CMS's dijet coupling limit, recast, against CMS's own V1/A1 summary where SModelS has no map (0.65–1.5 TeV)."""
    by = {e.id: e for e in ENTRIES}
    agree = total = 0
    for eid in ("dmwg_V1", "dmwg_A1"):
        cls, base = by[eid].model_class, by[eid].point
        for m_chi in (400.0, 700.0, 1000.0):
            for m_med in (650.0, 700.0, 800.0, 900.0, 1000.0, 1100.0, 1200.0, 1300.0, 1400.0, 1500.0):
                p = base.model_copy(update={"m_chi": m_chi, "m_med": m_med})
                out, cms = rs.dijet(cls, p, True), scan._collider(cls, p, True)   # a reference, signed or not
                if out is None or out.excluded is None or cms is None or cms.excluded is None:
                    continue
                total += 1
                agree += out.excluded == cms.excluded
    return (f"dijets below 1.5 TeV: CMS's coupling limit, recast, against CMS's V1/A1 contour ({total} points)",
            agree / total, 1.0, 1.0, "cms-2405.13778 (the experiment's own interpretation)")


def zz_gate() -> tuple[str, float, float, float, str]:
    """Broad ZZ: the interpolated limit is monotone in the width (wider signals are harder to see)."""
    zz = s._bundled("atlas-2009.14791-zz")
    worst = min(ps._zz_limit(zz, m, w2, "")[0] / ps._zz_limit(zz, m, w1, "")[0]      # the tables themselves
                for m in (400.0, 700.0, 1000.0, 1500.0) for w1, w2 in ((1.0, 5.0), (5.0, 10.0), (10.0, 15.0)))
    return ("broad ZZ: smallest limit(wider) / limit(narrower) over masses and widths", worst, 1.0, math.inf,
            "ATLAS's tables 12–15: limits weaken with width")


def main() -> int:
    """Run every gate, print the table, and return the exit code: 0 when all pass, 1 otherwise."""
    from adroit.core.receipts import exit_code, validation_table
    start = time.time()
    rows = monoh_gates() + [monoz_gate(), dijet_gate(), zz_gate()]
    table, failed = validation_table(rows)
    print(table)
    print(f"\n{len(rows) - failed} of {len(rows)} gates pass ({time.time() - start:.0f} s)")
    return exit_code(not failed)


if __name__ == "__main__":
    sys.exit(main())
