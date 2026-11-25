"""Validation of capture in the Sun against IceCube's published capture rates.

IceCube, arXiv:1601.00653 (JCAP 04 (2016) 022), Table 1: 18 supersymmetric
benchmark models, with the cross-sections used for capture (σ′_SI,p, σ′_SD,p:
the cross-sections rescaled by each model's share of the local density) and
the capture rate C from DarkSUSY 5.1.3. The rule, fixed in
docs/dm7_constraints.md before this was first run: the system's C, with
isoscalar SI and proton-only SD at those cross-sections and DarkSUSY's default
halo (ρ = 0.3 GeV/cm³, a Maxwellian with v₀ = 220 km/s and no escape-speed cut,
the Sun moving at 220 km/s), within a factor 1.3 of the published C for at
least 90% of the models.

Run from the repository root (seconds):

    uv run python docs/dm7/capture_check.py

Writes docs/dm7/capture_check.txt.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.constraints import capture  # noqa: E402
from adroit.core.dm_state import (DarkMatterParticle, HaloModel, InteractionModel,  # noqa: E402
                                  OperatorCoefficient)
from adroit.physics import conventions  # noqa: E402

# (m_χ GeV, σ′_SI,p cm², σ′_SD,p cm², C s⁻¹), transcribed from Table 1.
TABLE_1 = [
    (67.8, 4.1e-47, 1.6e-39, 7.9e23), (75.3, 5.1e-47, 9.3e-40, 3.9e23),
    (95.6, 4.0e-48, 6.3e-40, 1.7e23), (102.9, 5.5e-46, 1.9e-40, 4.5e22),
    (116.6, 5.6e-46, 3.3e-40, 6.2e22), (116.6, 2.2e-46, 3.8e-40, 7.1e22),
    (147.5, 4.9e-48, 2.7e-40, 3.2e22), (149.0, 1.5e-44, 2.0e-40, 2.4e22),
    (168.1, 1.3e-45, 1.9e-40, 1.8e22), (175.9, 7.8e-48, 1.5e-40, 1.2e22),
    (275.4, 3.4e-45, 7.0e-41, 2.6e21), (799.4, 3.0e-47, 5.2e-44, 3.9e17),
    (971.6, 4.4e-46, 2.9e-43, 2.5e18), (1019.1, 1.8e-47, 1.7e-44, 1.1e17),
    (1031.3, 8.6e-47, 7.0e-44, 4.7e17), (1078.2, 2.9e-45, 1.2e-42, 1.2e19),
    (1157.6, 1.1e-45, 2.2e-43, 3.4e18), (1213.7, 7.5e-45, 1.8e-42, 2.2e19),
]
DARKSUSY_HALO = HaloModel(label="DarkSUSY 5.1.3 default", rho_gev_cm3=0.3, v0_km_s=220.0,
                          v_esc_km_s=2000.0, v_lsr_km_s=(0.0, 220.0, 0.0),
                          v_peculiar_km_s=(0.0, 0.0, 0.0))
FACTOR, FRACTION = 1.3, 0.9


def interaction(m: float, sigma_si: float, sigma_sd: float) -> InteractionModel:
    """Isoscalar O₁ and proton-only O₄ at the given cross-sections."""
    c1 = conventions.c1_from_sigma_si(sigma_si, m)
    c4 = conventions.c4_from_sigma_sd(sigma_sd, m)
    return InteractionModel(name="benchmark", layer="nonrelativistic", coefficients=[
        OperatorCoefficient(operator=1, proton=c1, neutron=c1),
        OperatorCoefficient(operator=4, proton=c4, neutron=0.0)])


def main() -> None:
    """Compare and write the record."""
    lines = ["Capture in the Sun against IceCube, arXiv:1601.00653, Table 1 (DarkSUSY 5.1.3)",
             f"rule: within ×{FACTOR} for ≥ {FRACTION:.0%} of the models", "",
             "  m (GeV)   C published   C system   ratio   H share"]
    passed = 0
    for m, si, sd, published in TABLE_1:
        parts = capture.capture_rate(DarkMatterParticle(mass_gev=m), interaction(m, si, sd),
                                     DARKSUSY_HALO, by_isotope=True)
        total = sum(parts.values())
        ratio = total / published
        passed += 1 / FACTOR <= ratio <= FACTOR
        lines.append(f"  {m:7.1f}   {published:10.2e}   {total:9.2e}   {ratio:5.2f}   {parts['H1'] / total:6.1%}")
    met = passed >= FRACTION * len(TABLE_1)
    lines += ["", f"{passed}/{len(TABLE_1)} within ×{FACTOR}: {'met' if met else 'NOT met'}"]
    text = "\n".join(lines)
    (ROOT / "docs/dm7/capture_check.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
