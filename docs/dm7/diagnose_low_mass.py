"""Diagnosis, not part of the gate: can the published low-mass relic contour be what
annihilation gives without the light quarks?

For every point below m_DM = 10 GeV that fails gate part 1: Ωh² with every quark,
without u, d, s, and without u, d, s, c. Run after docs/dm7/relic_gate.py, from the
repository root:

    nice -n 10 uv run python docs/dm7/diagnose_low_mass.py > docs/dm7/diagnose_low_mass.txt
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.constraints import annihilation, relic, spin1  # noqa: E402
from adroit.constraints.spin1 import Spin1Model  # noqa: E402


def omega(model: Spin1Model, m: float, exclude: tuple[str, ...] = ()) -> float:
    """Ωh² with the named fermions' channels removed."""
    gamma = spin1.width(model, m)

    def sigma(s):
        kept = [f for f in spin1.FERMIONS if f.name not in exclude]
        return sum(annihilation.fermion_pair_sigma(s, m, f.mass_gev, f.colours, model.dm_couplings(),
                                                   model.couplings(f), model.m_med_gev, gamma)
                   for f in kept) + annihilation.to_mediator_pairs(s, model, m)
    return relic.omega_h2(sigma, m, resonance_gev=model.m_med_gev, width_gev=gamma)


def main() -> None:
    """Print the three values at each failing low-mass point."""
    for r in json.loads((ROOT / "docs/dm7/relic_gate.json").read_text()):
        if r["m_dm"] < 10 and not r["passes"]:
            model = spin1.benchmark(r["model"], r["m_med"])
            full = omega(model, r["m_dm"])
            no_uds = omega(model, r["m_dm"], ("u", "d", "s"))
            no_udsc = omega(model, r["m_dm"], ("u", "d", "s", "c"))
            print(f'{r["model"]} m_med {r["m_med"]:7.1f} m_dm {r["m_dm"]:5.2f}  full {full:.4f}  '
                  f'no u,d,s {no_uds:.4f}  no u,d,s,c {no_udsc:.4f}')


if __name__ == "__main__":
    main()
