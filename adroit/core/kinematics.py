"""The Standard Model fermions' kinematic masses, the one table both routes read (the owner's answers, 2026-10-20).

Kept apart from ``physics/`` (whose source the stored limit tables' fingerprints include: a table computed before
this table existed stays current, ``parameter_space.limit_tables``) and imported by the library's fermion table
(``constraints.spin1``), G2's Standard Model fermions and so its UFO exports (``model_building.feynman``) and the
model checks (``core.model_spec.HEAVY_QUARKS``).
"""
from __future__ import annotations

# The Standard Model fermions' kinematic masses (GeV): on external legs, in thresholds, phase space and propagators,
# the same in both routes (the owner, 2026-10-20). u, d, s, c and b are the DMsimp card's MASS-block inputs, MU 0.00255,
# MD 0.00504, MS 0.101, MC 1.27, MB 4.7 (1.27 is numerically the MS-bar m̄_c(m̄_c), not a pole mass); t is 172.5 in
# both routes, an explicit override of the card's MT = 172 (the owner's approval, 2026-10-20); the leptons their pole
# masses. They are not the Yukawa inputs (``model_building.yukawa``), nor the MS-bar inputs that run
# (``constraints.higgs``: m̄_b(m̄_b) = 4.18), nor the Standard Model Higgs widths' own thresholds (``constraints.higgs``:
# 4.78 and 1.67, kept as that prescription's). Below the hadronic opening the light quarks' channels are closed
# whatever their masses (``constraints.hadronic_window``).
KINEMATIC_MASSES = {"u": 0.00255, "d": 0.00504, "s": 0.101, "c": 1.27, "b": 4.7, "t": 172.5,
                    "e": 0.000511, "mu": 0.10566, "tau": 1.77686}
