"""The relic density's validation against Saikawa & Shirai (arXiv:2005.03544): the s-wave cross section a Majorana
fermion needs for Ωh² = 0.120, ADROIT's against theirs (S_2, fetched into the tools folder; never copied here).

    OMP_NUM_THREADS=2 nice -n 10 uv run python scripts/validate_relic_ss2020.py [--out PATH]

The gate, declared before it ran (``docs/relic_low_mass.md``): within 3% at every tabulated mass from 1 to 1000 GeV;
10 MeV–1 GeV and above 1 TeV are reported, not gated. Their g_s today (3.931) against ADROIT's (3.909, from
s₀ = 2891.2 cm⁻³) moves Ωh² by 0.56%, and they integrate to T = 1 eV against ADROIT's x = 10⁴: both are inside the
allowance and are not corrected for.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
ITEM = "Saikawa-Shirai relic cross sections (DM2020)"
GATE, LOW, HIGH = 0.03, 1.0, 1000.0
CM3_S_PER_GEV2 = 1.1673e-17                 # 1 GeV⁻² in cm³ s⁻¹ (ħ²c³)


def required(m: float, target: float = 0.120) -> float:
    """ADROIT's constant s-wave ⟨σv⟩ (cm³/s) giving Ωh² = target for a Majorana fermion of mass m."""
    from adroit.constraints import relic
    species = relic.dark_matter(m, 0.5, True)

    def gap(log_sv: float) -> float:
        sv = math.exp(log_sv) / CM3_S_PER_GEV2
        return math.log(relic.omega_h2_rate(species, lambda t: np.full_like(t, sv)) / target)
    return math.exp(brentq(gap, math.log(1e-27), math.log(1e-24), xtol=1e-6))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "docs" / "receipts" / "a development receipt (relic_ss2020_validation)"))
    args = parser.parse_args()
    from adroit.external.fetch import fetch, locate
    folder = locate(ITEM) or fetch(ITEM)
    table = np.loadtxt(Path(folder) / "S_2.dat")
    rows, worst = [], 0.0
    for m, sv26, *_ in table:
        if not 0.01 <= m <= 1e4:
            continue
        mine = required(float(m))
        theirs = sv26 * 1e-26
        ratio = mine / theirs
        gated = LOW <= m <= HIGH
        if gated:
            worst = max(worst, abs(ratio - 1))
        rows.append(f"| {m:.4g} | {theirs:.4g} | {mine:.4g} | {ratio:.4f} | {'yes' if gated else 'reported'} |")
        print(rows[-1], flush=True)
    passed = worst <= GATE
    lines = ["# The relic density against Saikawa & Shirai (arXiv:2005.03544)", "",
             f"s-wave Majorana, Ωh² = 0.120. Gate (declared before running): within {100 * GATE:g}% from {LOW:g} to "
             f"{HIGH:g} GeV. Largest gated deviation: {100 * worst:.2f}% — **{'passed' if passed else 'missed'}**.", "",
             "| m (GeV) | theirs (cm³/s) | ADROIT (cm³/s) | ADROIT / theirs | gated |", "|---|---|---|---|---|", *rows]
    Path(args.out).write_text("\n".join(lines) + "\n")
    print(f"largest gated deviation {100 * worst:.2f}%: {'passed' if passed else 'missed'}; written to {args.out}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
