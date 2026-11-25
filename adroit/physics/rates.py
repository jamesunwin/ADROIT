"""Differential recoil rates for any nonrelativistic interaction.

The rate per kg of target, per day, per keV of recoil energy:

    dR/dE_R = Σ_T x_T  ρ/(2π m_χ)  4π/(2J_T+1)
              Σ_k Σ_{ττ'} W_k^{ττ'}(q) [ R_k^{ττ'} η(v_min) + R⊥_k^{ττ'} η⊥(v_min) ] ,

summed over the isotopes T of the target with mass fractions x_T. The three
factors are independent:
- **the halo**: η and η⊥, the inverse-speed integrals of the velocity
  distribution above v_min (:mod:`halo`);
- **the nucleus**: the response functions W_k (:mod:`nuclear`);
- **the particle physics**: R_k and R⊥_k, quadratic in the operator
  coefficients, the parts of the dark matter response without and with v⊥²
  (arXiv:1308.6288, Eq. 38; ``_pair_weights``). Here q = √(2 m_T E_R) and
  v_min = |m_T E_R/μ_T + δ| / √(2 m_T E_R), so inelastic and exothermic
  scattering enter only through v_min.

The operators covered are O_1 and O_3 … O_15 of arXiv:1308.6288, for dark
matter of any spin. O_2 = (v⊥)² is omitted, as in that reference: no
relativistic interaction produces it at leading order (it appears only as an
O(v²) correction to O_1, whose nuclear response it shares); O_16 … O_20
(spin-1 dark matter, arXiv:1505.03117) are outside the first build
(docs/adroit_phase2.md).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from adroit.core.dm_state import (DarkMatterParticle, HaloModel, InteractionModel, Isotope,
                                      ModulationSpectrum, RecoilSpectrum, Target)
from adroit.physics import halo as halos
from adroit.physics import nuclear
from adroit.physics.conventions import (C_KM_S, GEV_IN_KG, HBAR_GEV_S, HBARC_GEV_CM, KEV,
                                            OPERATOR_MASS_GEV, SECONDS_PER_DAY,
                                            nuclear_mass_gev, reduced_mass)
from adroit.physics.nuclear import NuclearModel

OPERATORS = (1, *range(3, 16))
N_OPERATOR_SLOTS = 16    # coefficient arrays are indexed by operator number, 0 … 15

# From (number density in cm⁻³) × (coefficients² in GeV⁻⁴) to events/(keV kg day):
# (ħc)³ turns cm⁻³ into GeV³, and the result, in GeV⁻¹, is a rate per unit energy,
# mass and time in natural units.
RATE_UNIT = HBARC_GEV_CM ** 3 * KEV / GEV_IN_KG / HBAR_GEV_S * SECONDS_PER_DAY


def isospin_coefficients(interaction: InteractionModel,
                         q_gev: np.ndarray | None = None) -> np.ndarray:
    """The coefficients as the responses read them, in GeV⁻².

    Row τ = 0 holds c^p + c^n and row τ = 1 holds c^p − c^n (the normalisation
    of the nuclear tables); the column is the operator number. Without
    ``q_gev`` the shape is (2, 16), and the interaction must not depend on q;
    with it, (2, 16, len(q)), each coefficient evaluated at every q.
    """
    if q_gev is None and interaction.depends_on_q:
        raise ValueError("the interaction depends on q: give the momentum transfers")
    shape = (2, N_OPERATOR_SLOTS) if q_gev is None else (2, N_OPERATOR_SLOTS, len(q_gev))
    c = np.zeros(shape)
    for coefficient in interaction.coefficients:
        if coefficient.operator not in OPERATORS:
            raise ValueError(f"O_{coefficient.operator} is not covered: the rate handles "
                             f"O_1 and O_3 … O_15")
        factor = 1.0 if q_gev is None else coefficient.q_factor(q_gev)
        c[0, coefficient.operator] += (coefficient.proton + coefficient.neutron) * factor
        c[1, coefficient.operator] += (coefficient.proton - coefficient.neutron) * factor
    return c


def _pair_weights(a: np.ndarray, b: np.ndarray, spin_factor: float,
                  qm2: np.ndarray) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """R_k and R⊥_k for the coefficient rows a = c^τ and b = c^τ' (arXiv:1308.6288, Eq. 38).

    ``spin_factor`` is j_χ(j_χ+1) and ``qm2`` is (q/m_N)². The five responses
    after Σ' carry their extra (q/m_N)² here, so that every term multiplies
    W_k directly. Both lists follow the order of ``nuclear.RESPONSES``.
    """
    j3, j12 = spin_factor / 3.0, spin_factor / 12.0
    zero = np.zeros_like(qm2)
    phi_a, phi_b = a[12] - qm2 * a[15], b[12] - qm2 * b[15]
    plain = [
        a[1] * b[1] + j3 * qm2 * a[11] * b[11],                                    # M
        qm2 / 4 * a[10] * b[10] + j12 * (a[4] * b[4] + qm2 * (a[4] * b[6] + a[6] * b[4])
                                         + qm2 ** 2 * a[6] * b[6]),                # Σ''
        j12 * (a[4] * b[4] + qm2 * a[9] * b[9]),                                   # Σ'
        qm2 * (qm2 / 4 * a[3] * b[3] + j12 * phi_a * phi_b),                       # Φ''
        qm2 * j12 * (a[12] * b[12] + qm2 * a[13] * b[13]),                         # Φ̃'
        qm2 * j3 * (qm2 * a[5] * b[5] + a[8] * b[8]),                              # Δ
        qm2 * (a[3] * b[1] + j3 * phi_a * b[11]),                                  # Φ''M
        qm2 * j3 * (a[5] * b[4] - a[8] * b[9]),                                    # ΔΣ'
    ]
    transverse = [
        j3 * (qm2 * a[5] * b[5] + a[8] * b[8]),                                    # M
        j12 * (a[12] * b[12] + qm2 * a[13] * b[13]),                               # Σ''
        (qm2 * a[3] * b[3] + a[7] * b[7]) / 8 + j12 * (phi_a * phi_b + qm2 * a[14] * b[14]) / 2,
        zero, zero, zero, zero, zero,
    ]
    return [plain_k + zero for plain_k in plain], [t + zero for t in transverse]


def response_terms(energies_kev: np.ndarray, particle: DarkMatterParticle,
                   coefficients: np.ndarray | InteractionModel, isotope: Isotope,
                   model: NuclearModel) -> tuple[np.ndarray, np.ndarray]:
    """(P, Q): the nucleus and the operators together, at each recoil energy.

    P = 4π/(2J+1) Σ_k Σ_ττ' W_k^ττ' R_k^ττ' and Q the same with R⊥_k, so that for a
    relative speed w above v_min (speeds in units of c)

        w² dσ/dE_R = m_T/(2π) [P + Q (w² − v_min²)] .

    The direct-detection rate averages this over the halo; capture in the Sun
    (``constraints.capture``) integrates it over the solar interior.
    """
    energies = np.asarray(energies_kev, dtype=float)
    m_t = nuclear_mass_gev(isotope.mass_number)
    q = np.sqrt(2.0 * m_t * energies * KEV)
    if isinstance(coefficients, InteractionModel):
        coefficients = isospin_coefficients(coefficients, q if coefficients.depends_on_q else None)
    w = nuclear.responses(isotope, q, model)
    qm2 = (q / OPERATOR_MASS_GEV) ** 2
    spin_factor = particle.spin * (particle.spin + 1.0)
    p_total, q_total = np.zeros_like(energies), np.zeros_like(energies)
    for t in (0, 1):
        for u in (0, 1):
            plain, transverse = _pair_weights(coefficients[t], coefficients[u], spin_factor, qm2)
            for k in range(len(nuclear.RESPONSES)):
                p_total += w[k, t, u] * plain[k]
                q_total += w[k, t, u] * transverse[k]
    norm = 4.0 * math.pi / (2.0 * isotope.spin + 1.0)
    return norm * p_total, norm * q_total


def isotope_rate(energies_kev: np.ndarray, particle: DarkMatterParticle,
                 coefficients: np.ndarray | InteractionModel, isotope: Isotope, halo: HaloModel,
                 model: NuclearModel) -> np.ndarray:
    """dR/dE_R per kg of the pure isotope, in events/(keV kg day).

    ``coefficients`` is either ``isospin_coefficients(interaction)`` or the
    interaction itself; an interaction that depends on q must be passed
    itself, since q at a given recoil energy depends on the isotope.
    """
    energies = np.asarray(energies_kev, dtype=float)
    m_t = nuclear_mass_gev(isotope.mass_number)
    mu = reduced_mass(particle.mass_gev, m_t)
    recoil = energies * KEV
    q = np.sqrt(2.0 * m_t * recoil)
    v_min = np.abs(m_t * recoil / mu + particle.mass_splitting_kev * KEV) / q * C_KM_S
    eta, eta_perp = halos.velocity_integrals(v_min, halo)
    eta_nat, eta_perp_nat = eta * C_KM_S, eta_perp / C_KM_S     # speeds in units of c
    plain, transverse = response_terms(energies, particle, coefficients, isotope, model)
    density = halo.rho_gev_cm3 / particle.mass_gev
    total = plain * eta_nat + transverse * eta_perp_nat
    return np.clip(density / (2.0 * math.pi) * total * RATE_UNIT, 0.0, None)


def _energies(energies_kev: Sequence[float] | np.ndarray) -> np.ndarray:
    """Recoil energies as an array, all positive."""
    energies = np.atleast_1d(np.asarray(energies_kev, dtype=float))
    if np.any(energies <= 0.0):
        raise ValueError("recoil energies must be positive")
    return energies


def _target_rate(energies: np.ndarray, particle: DarkMatterParticle,
                 coefficients: np.ndarray | InteractionModel, target: Target, halo: HaloModel,
                 model: NuclearModel) -> np.ndarray:
    """dR/dE_R per kg of target: the mass-weighted sum over its isotopes."""
    return sum(isotope.mass_fraction
               * isotope_rate(energies, particle, coefficients, isotope, halo, model)
               for isotope in target.isotopes)


def differential_rate(energies_kev: Sequence[float] | np.ndarray, particle: DarkMatterParticle,
                      interaction: InteractionModel, target: Target,
                      halo: HaloModel | None = None,
                      model: NuclearModel = NuclearModel.shell_model) -> RecoilSpectrum:
    """The recoil spectrum dR/dE_R of an interaction on a target, in events/(keV kg day).

    Args:
        energies_kev: Recoil energies, keV (positive).
        particle: The dark matter particle (mass, spin, mass splitting).
        interaction: Its nonrelativistic coefficients, in the nucleon basis, GeV⁻².
        target: The detector target (``targets.target('Xe')``).
        halo: The halo; the Standard Halo Model by default.
        model: The nuclear responses; the shell model by default.

    Returns:
        The spectrum, recording the halo and the nuclear input it used.
    """
    halo = halo or HaloModel()
    energies = _energies(energies_kev)
    rate = _target_rate(energies, particle, interaction, target, halo, model)
    return RecoilSpectrum(target=target.name, energies_kev=energies.tolist(), rate=rate.tolist(),
                          particle=particle, interaction_id=interaction.id, halo=halo,
                          nuclear_input=nuclear.describe(target, model))


def annual_modulation(energies_kev: Sequence[float] | np.ndarray, particle: DarkMatterParticle,
                      interaction: InteractionModel, target: Target,
                      halo: HaloModel | None = None,
                      model: NuclearModel = NuclearModel.shell_model,
                      samples: int = 24) -> ModulationSpectrum:
    """The annual modulation of the rate: its mean, amplitude and peak day at each energy.

    The rate is computed on ``samples`` days spread evenly over the year and
    its first Fourier harmonic taken. The halo must be a standard one, whose
    detector-frame velocities change as the Earth orbits the Sun.
    """
    halo = halo or HaloModel()
    energies = _energies(energies_kev)
    days = np.arange(samples) * halos.DAYS_PER_YEAR / samples
    rates = np.array([_target_rate(energies, particle, interaction, target,
                                   halos.halo_on_day(halo, day), model) for day in days])
    omega_t = 2.0 * math.pi * days / halos.DAYS_PER_YEAR
    cosine = 2.0 / samples * np.cos(omega_t) @ rates
    sine = 2.0 / samples * np.sin(omega_t) @ rates
    peak = (np.arctan2(sine, cosine) % (2.0 * math.pi)) * halos.DAYS_PER_YEAR / (2.0 * math.pi)
    return ModulationSpectrum(target=target.name, energies_kev=energies.tolist(),
                              mean_rate=rates.mean(axis=0).tolist(),
                              amplitude=np.hypot(cosine, sine).tolist(), peak_day=peak.tolist(),
                              particle=particle, interaction_id=interaction.id, halo=halo,
                              nuclear_input=nuclear.describe(target, model))


def recoil_range_kev(particle: DarkMatterParticle, isotope: Isotope,
                     halo: HaloModel | None = None) -> tuple[float, float] | None:
    """The recoil energies the halo's fastest particle can reach, or None if none.

    Solving v_min(E) = v_max: E± = μ²/(2 m_T) (v_max ± √(v_max² − 2δ/μ))².
    """
    v = halos.max_speed_km_s(halo or HaloModel()) / C_KM_S
    m_t = nuclear_mass_gev(isotope.mass_number)
    mu = reduced_mass(particle.mass_gev, m_t)
    discriminant = v * v - 2.0 * particle.mass_splitting_kev * KEV / mu
    if discriminant < 0.0:
        return None
    root = math.sqrt(discriminant)
    scale = mu * mu / (2.0 * m_t) / KEV
    return scale * (v - root) ** 2, scale * (v + root) ** 2
