"""The portal library's part 2: every validation gate of docs/portal_library_2.md, section 5, run and tabulated.

``uv run python scripts/validate_portal_library_2.py`` (local computation only; MadGraph's Python reads the UFO
files; about 10 minutes). Prints a Markdown table, one row per gate, and exits non-zero if a gate fails.
"""

from __future__ import annotations

import math
import sys
import time

import json
from pathlib import Path

from scipy.optimize import brentq

from adroit.parameter_space import crosscheck as cc
from adroit.parameter_space import library
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.multiplet import ElectroweakMultiplet
from adroit.parameter_space.portals.tchannel import TChannel
from adroit.parameter_space.portals.ufo import UFOPortal

IDM = [("BM5 (Belyaev)", (100, 200, 1.0, 5), 1.3e-4), ("BM6 (Belyaev)", (100, 200, 0.002, 5), 1.7e-3),
       ("HP2 (Kalinowski)", (557, 565.417, -0.1385, 5.316), 0.072092),
       ("HP8 (Kalinowski)", (933, 943.787, -0.2435, 6.968), 0.09639),
       ("HP10 (Kalinowski)", (990, 998.12, -0.051, 2.36), 0.12478)]
TWO_HDM_A = [((600, 250, 150), 0.534), ((600, 250, 300), 9.16e-5), ((1000, 400, 170), 0.0101), ((1000, 400, 300), 0.00391)]
# Re-declared 2026-10-10 (docs/portal_library_2.md): the inert doublet against micrOMEGAs 7.1.10 at the same point and
# electroweak inputs, the 2HDM+a against MadDM with a physical g* species list (scripts/maddm_matched_gstar.py).
MATCHED = Path(__file__).resolve().parents[1] / "docs" / "portal_library_2" / "maddm_matched_reference.json"


def matched_maddm() -> dict[tuple[int, int, int], float]:
    """MadDM's Ωh² with a physical g*, by (M_A, M_a, m_χ)."""
    if not MATCHED.exists():
        raise SystemExit(f"run scripts/maddm_matched_gstar.py first: {MATCHED} is missing")
    rows = json.loads(MATCHED.read_text())["points"]
    return {(r["point"]["M_A"], r["point"]["M_a"], r["point"]["m_chi"]): r["omega_h2_matched"] for r in rows}


def thermal_mass(omega, low: float, high: float) -> float:
    return math.exp(brentq(lambda lm: math.log(omega(math.exp(lm)) / 0.12), math.log(low), math.log(high), xtol=2e-3))


def coloured(se: bool, bsf: bool, partner: str = "uR", g: float = 0.01, delta: float | None = None) -> float:
    model = TChannel(partner=partner, majorana=True, sommerfeld=se, bound_states=bsf)
    return thermal_mass(lambda m: model.omega_h2(Point(m_chi=m, m_med=m + delta if delta else 1.001 * m, g_chi=g)),
                        300.0, 8000.0)


def multiplet(kind: str, se: bool, low: float, high: float) -> float:
    model = ElectroweakMultiplet(multiplet=kind, sommerfeld=se)
    return thermal_mass(lambda m: model.omega_h2(Point(m_chi=m, m_med=1.0, g_q=0.0)), low, high)


def gates() -> list[tuple[str, float, float, float, str]]:
    """(gate, ours, low, high, reference) for every gate."""
    out = []
    for name, (mh, mc, lam, da), ref in IDM:
        r = cc.crosscheck("inert_doublet", Point(m_chi=mh, m_med=mc, g_chi=lam, g_q=da))
        out.append((f"inert doublet {name}: Ωh² / micrOMEGAs 7.1.10", r.ratio, 0.94, 1.06,
                    "same point and electroweak inputs (ours / published: "
                    + (f"{r.adroit / ref:.3f})" if r.adroit is not None else "not computed)")))
    matched = matched_maddm()
    for (heavy, ma, mx), ref in TWO_HDM_A:
        params = {**library.TWO_HDM_A.parameters, "mh2": str(heavy), "mh3": str(heavy), "mhc": str(heavy)}
        model = UFOPortal(**{**library.TWO_HDM_A.model_dump(), "parameters": params})
        omega = model.omega_h2(Point(m_chi=mx, m_med=ma, g_chi=1.0, g_q=0.35, g_l=1.0))
        out.append((f"2HDM+a (M_A, M_a, m_χ) = ({heavy}, {ma}, {mx}): Ωh² / MadDM, physical g*",
                    omega / matched[(heavy, ma, mx)], 0.9, 1.1,
                    f"MadDM 3.3, same UFO, physical g* species (ours / MadDM as run: {omega / ref:.3f})"))
    out.append(("u_R partner, Δm → 0, y = 0.01: thermal mass, no long-range effects (TeV)", coloured(False, False) / 1e3,
                1.2, 1.4, "De Simone et al. 1.3"))
    out.append(("… with the Sommerfeld effect (TeV)", coloured(True, False) / 1e3, 1.6, 1.8, "De Simone et al. 1.7"))
    out.append(("… with bound states (TeV)", coloured(True, True) / 1e3, 2.4, 3.3, "Becker 2.4, Liew 2.5, Harz 3.3"))
    gain = coloured(True, True, "bR", 0.5, 20.0) / coloured(False, False, "bR", 0.5, 20.0)
    out.append(("b_R partner, Δm = 20 GeV, y = 0.5: gain from the long-range effects", gain, 1.45, 1.8,
                "Garny & Heisig 1.67 (with excited states)"))
    wino_tree, wino_se = multiplet("wino", False, 1500, 4000), multiplet("wino", True, 1800, 4500)
    out.append(("wino thermal mass, tree level (TeV)", wino_tree / 1e3, 2.15, 2.45, "Beneke 2.22, Cirelli 2.4"))
    out.append(("wino thermal mass, Sommerfeld (TeV)", wino_se / 1e3, 2.7, 3.1, "Beneke 2.88, Hisano 2.7–3.0"))
    out.append(("wino gain from the Sommerfeld effect", wino_se / wino_tree, 1.25, 1.35, "Beneke 1.30"))
    out.append(("higgsino thermal mass, Sommerfeld (TeV)", multiplet("higgsino", True, 600, 2000) / 1e3, 1.0, 1.15,
                "Bottaro 1.08, Cirelli ≈1.0–1.1"))
    return out


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
