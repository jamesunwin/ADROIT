"""Units, constants and conventions: the one place where they are fixed.

Most errors in direct-detection phenomenology are errors of convention: a
factor of 2 in the isospin basis, the nucleon mass used in a reduced mass, a
coupling quoted with or without its mass scale. Every module takes its
constants and its conversions from here.

**Units.** Masses and energies are in GeV unless a name says otherwise
(``_kev``); speeds are in km/s; cross-sections are in cm²; rates are in events
per kg of target per day per keV of recoil energy.

**Couplings.** A nonrelativistic operator O_i enters the interaction as

    (c_i^0 + c_i^1 τ_3) O_i ,      c_i^p = c_i^0 + c_i^1 ,   c_i^n = c_i^0 − c_i^1 ,

with coefficients of dimension 1/mass². A *dimensionless* coupling d_i is the
coefficient in units of 1/m_v², with m_v = 246.2 GeV: c_i = d_i / m_v². This
is the normalisation of arXiv:1308.6288, which LZ uses (arXiv:2609.02823).
- An **isoscalar** coupling ("s") is c^0 alone: c^p = c^n.
- An **isovector** coupling ("v") is c^1 alone: c^p = −c^n.

**The spin-independent cross-section.** For the operator O_1,

    σ_N = (c_1^N)² μ_N² / π ,

with μ_N the reduced mass of the dark matter particle and the nucleon N.

**The nucleon mass** in μ_N is the mean of the proton and neutron masses.
Some codes use the atomic mass unit instead, which changes a rate at fixed
cross-section by 1.5% (docs/dm0_tool_audit.md).

**The operator mass.** The momentum-dependent operators carry q/m_N (O_3 =
i S_N·(q/m_N × v⊥), O_10 = i S_N·q/m_N, ...). This m_N fixes what a
coefficient of such an operator means. It is the atomic mass unit here, as in
WIMpy_NREFT and WimPyDD, the code LZ's published tables come from
(``OPERATOR_MASS_GEV``). A nucleus of mass number A has mass A atomic mass units.
"""

from __future__ import annotations

import math

# --- constants (CODATA 2018) --------------------------------------------------------
C_KM_S = 299_792.458                 # speed of light, km/s
HBARC_GEV_FM = 0.1973269804          # ħc, GeV fm
HBARC_GEV_CM = HBARC_GEV_FM * 1e-13  # ħc, GeV cm
AMU_GEV = 0.93149410242              # atomic mass unit
M_PROTON_GEV = 0.93827208816
M_NEUTRON_GEV = 0.93956542052
M_NUCLEON_GEV = 0.5 * (M_PROTON_GEV + M_NEUTRON_GEV)
GEV_IN_KG = 1.78266192e-27           # 1 GeV/c² in kg
KEV = 1.0e-6                         # 1 keV in GeV
HBAR_GEV_S = 6.582119569e-25         # ħ, GeV s
SECONDS_PER_DAY = 86_400.0

# --- conventions ---------------------------------------------------------------------
M_V_GEV = 246.2                      # the mass scale of a dimensionless coupling
OPERATOR_MASS_GEV = AMU_GEV          # m_N in the operators' q/m_N (see above)


def reduced_mass(m1: float, m2: float) -> float:
    """The reduced mass m1 m2 / (m1 + m2)."""
    return m1 * m2 / (m1 + m2)


def nuclear_mass_gev(mass_number: int) -> float:
    """The mass of a nucleus of ``mass_number`` nucleons, as A atomic mass units."""
    return mass_number * AMU_GEV


def momentum_transfer_gev(recoil_kev: float, target_mass_gev: float) -> float:
    """The momentum transfer q = √(2 m_T E_R) of a nuclear recoil of energy E_R."""
    return math.sqrt(2.0 * target_mass_gev * recoil_kev * KEV)


def v_min_km_s(recoil_kev: float, target_mass_gev: float, dm_mass_gev: float,
               splitting_kev: float = 0.0) -> float:
    """The least dark matter speed that can give a recoil of energy E_R.

    v_min = | m_T E_R / μ_T + δ | / √(2 m_T E_R), with δ the mass splitting
    (δ > 0: the dark matter particle is excited; δ < 0: it de-excites; δ = 0:
    elastic).
    """
    mu = reduced_mass(dm_mass_gev, target_mass_gev)
    e = recoil_kev * KEV
    beta = abs(target_mass_gev * e / mu + splitting_kev * KEV) / math.sqrt(
        2.0 * target_mass_gev * e)
    return beta * C_KM_S


def to_isospin(c_proton: float, c_neutron: float) -> tuple[float, float]:
    """(c^0, c^1) from (c^p, c^n): c^0 = (c^p + c^n)/2, c^1 = (c^p − c^n)/2."""
    return 0.5 * (c_proton + c_neutron), 0.5 * (c_proton - c_neutron)


def to_nucleon(c_isoscalar: float, c_isovector: float) -> tuple[float, float]:
    """(c^p, c^n) from (c^0, c^1): c^p = c^0 + c^1, c^n = c^0 − c^1."""
    return c_isoscalar + c_isovector, c_isoscalar - c_isovector


def coupling_gev2(dimensionless: float) -> float:
    """A coefficient in GeV⁻² from its dimensionless value: c = d / m_v²."""
    return dimensionless / M_V_GEV ** 2


def dimensionless_coupling(coefficient_gev2: float) -> float:
    """The dimensionless value of a coefficient in GeV⁻²: d = c m_v²."""
    return coefficient_gev2 * M_V_GEV ** 2


def sigma_si_cm2(c1_gev2: float, dm_mass_gev: float,
                 nucleon_mass_gev: float = M_NUCLEON_GEV) -> float:
    """The spin-independent cross-section per nucleon, σ = c_1² μ_N² / π, in cm²."""
    mu = reduced_mass(dm_mass_gev, nucleon_mass_gev)
    return c1_gev2 ** 2 * mu ** 2 / math.pi * HBARC_GEV_CM ** 2


def c1_from_sigma_si(sigma_cm2: float, dm_mass_gev: float,
                     nucleon_mass_gev: float = M_NUCLEON_GEV) -> float:
    """The O_1 coefficient (GeV⁻², positive) of a spin-independent cross-section in cm²."""
    mu = reduced_mass(dm_mass_gev, nucleon_mass_gev)
    return math.sqrt(math.pi * sigma_cm2) / (mu * HBARC_GEV_CM)


def sigma_sd_cm2(c4_gev2: float, dm_mass_gev: float,
                 nucleon_mass_gev: float = M_NUCLEON_GEV) -> float:
    """The spin-dependent cross-section on a free nucleon from O₄, σ = 3 c₄² μ_N²/(16π), in cm².

    For spin-½ dark matter the spin average of (S_χ·S_N)² over initial and
    sum over final states is 3/16, so |M|² = 3c₄²/16 and σ = μ_N²|M|²/π.
    This is the cross-section on a free nucleon that experiments quote; the
    rate code gives the same normalisation (tests/physics/test_rates.py).
    """
    mu = reduced_mass(dm_mass_gev, nucleon_mass_gev)
    return 3.0 * c4_gev2 ** 2 * mu ** 2 / (16.0 * math.pi) * HBARC_GEV_CM ** 2


def c4_from_sigma_sd(sigma_cm2: float, dm_mass_gev: float,
                     nucleon_mass_gev: float = M_NUCLEON_GEV) -> float:
    """The O₄ coefficient (GeV⁻², positive) of a spin-dependent cross-section on a free nucleon."""
    mu = reduced_mass(dm_mass_gev, nucleon_mass_gev)
    return math.sqrt(16.0 * math.pi * sigma_cm2 / 3.0) / (mu * HBARC_GEV_CM)
