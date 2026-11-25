"""The relative speeds of annihilating dark matter in the Sun and in dwarf galaxies: one definition, used by Track 1's
scan and Path 2's verdicts alike (the second addendum to the audit loop's cycle 3, AL3-33, 2026-11-16: the two had
used 10⁻³ and 10⁻⁴ for the Sun, 10⁻⁴ and 2 × 10⁻⁵ for dwarfs, so a p-wave rate in the Sun was 24 times its thermal
one in the scan, and 92 times Path 2's).

Two particles each with a Maxwellian of one-dimensional dispersion σ have a relative speed whose root mean square is
√6 σ. In the Sun, captured dark matter has thermalised at the core's temperature, σ² = T_c/m_χ; in a dwarf galaxy σ
is the stellar line-of-sight dispersion.

The dwarfs' speed is a convention, one value for every dwarf: σ = 10 km/s, so v_rel = √6 × 10 km/s = 8.2 × 10⁻⁵ c, a
fair single value for the classical dwarfs (their dispersions are about 6–12 km/s). The ultra-faint dwarfs are nearer
3–5 km/s: there a p-wave rate (∝ v²) would be several times smaller, and a Sommerfeld-enhanced one (∝ 1/v) larger. No
verdict seen depends on the choice (the owner's review, 2026-11-16); a value for each dwarf is deferred to 1.0.1
(the deferred list).
"""

from __future__ import annotations

import math

C_KM_S = 299_792.458
SUN_CORE_TEMPERATURE_GEV = 1.57e7 * 8.617333262e-14      # 1.57 × 10⁷ K (the standard solar model's centre)
DWARF_DISPERSION_KM_S = 10.0                    # a convention (module docstring): classical 6–12, ultra-faint 3–5 km/s
DWARF_DISPERSION_RANGE_KM_S = (3.0, 12.0)       # the range the convention stands for, ultra-faint to classical
DWARF_SPEED = math.sqrt(6.0) * DWARF_DISPERSION_KM_S / C_KM_S   # 8.2 × 10⁻⁵


def sun_speed(m_dm_gev: float) -> float:
    """The relative speed (units of c) of dark matter of mass m thermalised in the Sun's core: √(6 T_c / m)."""
    return math.sqrt(6.0 * SUN_CORE_TEMPERATURE_GEV / m_dm_gev)
