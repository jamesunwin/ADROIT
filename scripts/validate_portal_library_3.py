"""The portal library's part 3: every validation gate of docs/portal_library_3.md, section 7, run and tabulated.

``uv run python scripts/validate_portal_library_3.py`` (local computation: micrOMEGAs, SModelS and MadGraph's
Python, all in the tools folder; about 10 minutes). Prints a Markdown table and exits non-zero if a gate fails.
The relic gates compare the two codes like with like, ADROIT on micrOMEGAs' own degrees of freedom (Drees, Hajkarim &
Schmitz): with ADROIT's (Saikawa & Shirai, since 2026-10-19) its Ωh² is 3.2–4.3% higher at these points below 1 TeV
and 1.4% at 3 TeV, the equation of state's systematic (docs/relic_low_mass.md), which had put four singlet gates
outside 5%.
"""

from __future__ import annotations

import sys
import time

import numpy as np

from adroit.parameter_space import crosscheck as cc
from adroit.parameter_space import likelihood as lk
from adroit.parameter_space import searches as ps
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.multiplet import ElectroweakMultiplet
from adroit.parameter_space.portals.tchannel import TChannel
from adroit.parameter_space.portals.vector import DarkPhoton

IDM = {"BP1": (72.77, 107.803, 114.639, -0.00440723, 0.20), "BP4": (73.68, 100.112, 145.728, -0.00440723, 0.20),
       "BP6": (72.14, 109.548, 154.761, -0.00234, 0.20), "BM1": (55.0, 63.0, 150.0, 1e-4, 0.20),
       "BM4": (70.0, 170.0, 200.0, 0.02, 0.20), "HP2": (557.0, 562.316, 565.417, -0.1385, 0.05),
       "HP10": (990.0, 992.36, 998.12, -0.051, 0.05)}
SINGLET = [(40.0, 0.1), (50.0, 0.1), (57.0, 0.1), (60.0, 1e-3), (62.0, 3e-4), (66.0, 0.01), (100.0, 0.1),
           (300.0, 0.1), (1000.0, 0.1), (3000.0, 0.1)]
LHC = [("u_R partner 900/100 GeV", TChannel(partner="uR"), Point(m_chi=100.0, m_med=900.0, g_chi=1.0), 2.32),
       ("u_R partner 1500/100 GeV", TChannel(partner="uR"), Point(m_chi=100.0, m_med=1500.0, g_chi=1.0), 0.46),
       ("μ_R partner 400/100 GeV", TChannel(partner="muR"), Point(m_chi=100.0, m_med=400.0, g_chi=1.0), 1.67),
       ("wino 500 GeV", ElectroweakMultiplet(multiplet="wino"), Point(m_chi=500.0, m_med=1.0, g_q=0.0), 3.16)]


def gates() -> list[tuple[str, float, float, float, str]]:
    out = []
    for name, (h, a, c, lam, tol) in IDM.items():
        r = cc.crosscheck("inert_doublet", Point(m_chi=h, m_med=c, g_chi=lam, g_q=a - h), its_equation_of_state=True)
        out.append((f"inert doublet {name}: Ωh² / micrOMEGAs 7.1.10", r.ratio, 1 - tol, 1 + tol,
                    ("same electroweak inputs; W W*, Z Z* in both" if tol > 0.1 else "same electroweak inputs")
                    + "; micrOMEGAs' degrees of freedom in both"))
    for m, lam in SINGLET:
        r = cc.crosscheck("higgs_portal_scalar", Point(m_chi=m, m_med=125.0, g_chi=lam), its_equation_of_state=True)
        out.append((f"scalar singlet {m:g} GeV, λ_hs = {lam:g}: Ωh² / micrOMEGAs", r.ratio, 0.95, 1.05,
                    "each code's own Higgs width (h → SS included); micrOMEGAs' degrees of freedom in both"))
    for label, cls, p, ref in LHC:
        outcome = ps.lhc_search(cls, p, True)
        out.append((f"SModelS r, {label}", outcome.value / ref, 0.9, 1.1,     # value: r, whatever the verdict
                    f"the install survey's r = {ref}"))
    p = Point(m_chi=2900.0, m_med=1.0, g_q=0.0)
    ratio = (ElectroweakMultiplet(multiplet="wino").omega_h2(p)
             / ElectroweakMultiplet(multiplet="wino", bound_states=False).omega_h2(p))
    out.append(("wino 2.9 TeV: Ωh²(bound states) / Ωh²(Sommerfeld only)", ratio, 0.96, 0.995,
                "Mitridate et al. 0.980–0.987"))
    out.append(_hadron_gate())
    out.append(("combined likelihood: r_comb of r = (0.6, 0.8)", lk.combined_ratio(lk.combined({"a": 0.6, "b": 0.8}, {})),
                0.999, 1.001, "√(0.6² + 0.8²) = 1"))
    return out


def _hadron_gate() -> tuple[str, float, float, float, str]:
    dp, p = DarkPhoton(), Point(m_chi=0.8, m_med=3.0, g_chi=1.0, g_q=1e-4)
    below, above = dp.channels(np.array([1.99 ** 2]), p), dp.channels(np.array([2.01 ** 2]), p)
    r_below = float(below["hadrons"][0]) / float(below["e"][0])
    r_above = sum(float(above[q][0]) for q in ("u", "d", "s")) / float(above["e"][0])
    return ("dark photon: hadrons/e⁺e⁻ at 1.99 GeV over quarks/e⁺e⁻ at 2.01 GeV", r_below / r_above, 0.95, 1.15,
            "the measured R (2.18) against N_c ΣQ² = 2")


def main() -> int:
    """Run every gate, print the table, and return the exit code: 0 when all pass, 1 otherwise."""
    from adroit.core.receipts import exit_code, validation_table
    start = time.time()
    rows = gates()
    table, failed = validation_table(rows)
    print(table)
    print(f"\n{len(rows) - failed} of {len(rows)} gates pass ({time.time() - start:.0f} s)")
    return exit_code(not failed)


if __name__ == "__main__":
    sys.exit(main())
