"""Annihilation through s-channel mediators, several at once and interfering (the portal models).

Every formula has the same shape. The amplitude factorises into the dark
matter's vertex, the propagators P_i = 1/(s − M_i² + iM_iΓ_i), and the final
state's vertex, so after the phase-space integral

    σ(s) = Σ_ij Re(P_i P_j*) × In_ij(s) × Out_ij(√s) ,

where Out_ij is the width that a boson of mass √s would have into the final
state (with the couplings of mediators i and j in place of the squares), and
In_ij carries the dark matter's spin average, flux and couplings. For one
mediator it reduces to the formulas of ``annihilation`` (DM7, checked against
explicit amplitudes) and of the Higgs-portal literature (arXiv:1306.4710);
the interference terms are checked against explicit amplitudes in the tests.

**Spin-1 mediators**, couplings −V_μ ψ̄γ^μ(a + bγ⁵)ψ to fermions and
−g V_μ i(φ*∂^μφ − φ∂^μφ*) to a complex scalar:
- Dirac (or Majorana, couplings at the level of the Feynman rule) dark matter:
  In_ij = [a_i a_j (s + 2m²) + b_i b_j (s − 4m²)] / (√s β), and the helicity
  term 12 b_i b_j b_fi b_fj m² m_f² (1 − s/M_i²)(1 − s/M_j²) N_c β_f/(12π s β);
- a complex scalar: In_ij = g_i g_j √s β;
- Out_ij = N_c √s β_f [a_fi a_fj (1 + 2m_f²/s) + b_fi b_fj β_f²]/(12π).

**Spin-0 mediators**, couplings −φ ψ̄(y_s + i y_p γ⁵)ψ, −μ φ S² /2 (a real
scalar S, Feynman rule −iμ), −μ φ V_μV^μ /2 (a real vector V):
- Dirac or Majorana: In_ij = (y_si y_sj β² + y_pi y_pj) √s/(2β);
- a scalar: In_ij = μ_i μ_j /(√s β);
- a vector: In_ij = μ_i μ_j [2 + (s − 2m²)²/(4m⁴)]/(9√s β);
- into Standard Model states through a mediator mixing with the Higgs boson
  (couplings κ_i × the Higgs boson's): Out_ij = κ_i κ_j Γ_h(√s) (``higgs.width``);
- into a fermion pair: Out_ij = N_c √s (g_si g_sj β_f³ + g_pi g_pj β_f)/(8π).

β = √(1 − 4m²/s) and β_f likewise. All cross-sections are in GeV⁻².
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from adroit.constraints import higgs


@dataclass(frozen=True)
class Mediator:
    """An s-channel mediator: its mass and total width (GeV), the M_i and Γ_i of its propagator."""
    mass: float
    width: float


def _open(s: np.ndarray, *masses: float) -> tuple[np.ndarray, np.ndarray]:
    threshold = 4.0 * max(masses) ** 2
    open_ = s > threshold * (1.0 + 1e-12)
    return open_, np.where(open_, s, 2.0 * threshold + 1.0)


def _beta(s: np.ndarray, m: float) -> np.ndarray:
    return np.sqrt(np.clip(1.0 - 4.0 * m * m / s, 0.0, None))


def _products(s: np.ndarray, mediators: list[Mediator]) -> list[list[np.ndarray]]:
    """Re(P_i P_j*) for every pair of mediators."""
    props = [1.0 / (s - md.mass ** 2 + 1j * md.mass * md.width) for md in mediators]
    return [[np.real(pi * np.conj(pj)) for pj in props] for pi in props]


def vector_to_fermions(s: np.ndarray, m: float, dm: str, dm_couplings: list[tuple[float, float]],
                       m_f: float, colours: int, f_couplings: list[tuple[float, float]],
                       mediators: list[Mediator]) -> np.ndarray:
    """σ(DM DM̄ → f f̄) through spin-1 mediators; ``dm`` is "fermion" or "complex_scalar".

    For a complex scalar the couplings are (g, 0).
    """
    s = np.asarray(s, dtype=float)
    open_, s_ = _open(s, m, m_f)
    beta, beta_f = _beta(s_, m), _beta(s_, m_f)
    rp = _products(s_, mediators)
    root = np.sqrt(s_)
    total = np.zeros_like(s_)
    n = len(mediators)
    for i in range(n):
        for j in range(n):
            (a_i, b_i), (a_j, b_j) = dm_couplings[i], dm_couplings[j]
            (af_i, bf_i), (af_j, bf_j) = f_couplings[i], f_couplings[j]
            out = colours * root * beta_f * (af_i * af_j * (1.0 + 2.0 * m_f ** 2 / s_)
                                             + bf_i * bf_j * beta_f ** 2) / (12.0 * np.pi)
            if dm == "complex_scalar":
                inner = a_i * a_j * root * beta
                extra = 0.0
            else:
                inner = (a_i * a_j * (s_ + 2.0 * m * m) + b_i * b_j * (s_ - 4.0 * m * m)) / (root * beta)
                extra = (12.0 * b_i * b_j * bf_i * bf_j * m * m * m_f * m_f
                         * (1.0 - s_ / mediators[i].mass ** 2) * (1.0 - s_ / mediators[j].mass ** 2)
                         * colours * beta_f / (12.0 * np.pi * s_ * beta))
            total += rp[i][j] * (inner * out + extra)
    return np.where(open_, total, 0.0)


def _scalar_in(s: np.ndarray, m: float, dm: str, ci: tuple[float, float], cj: tuple[float, float]) -> np.ndarray:
    beta, root = _beta(s, m), np.sqrt(s)
    if dm == "fermion":
        return (ci[0] * cj[0] * beta ** 2 + ci[1] * cj[1]) * root / (2.0 * beta)
    if dm == "scalar":
        return ci[0] * cj[0] / (root * beta)
    if dm == "vector":
        return ci[0] * cj[0] * (2.0 + (s - 2.0 * m * m) ** 2 / (4.0 * m ** 4)) / (9.0 * root * beta)
    raise ValueError(f"unknown dark matter kind {dm!r}")


def scalar_to_standard_model(s: np.ndarray, m: float, dm: str, dm_couplings: list[tuple[float, float]],
                             kappas: list[float], mediators: list[Mediator],
                             channels: tuple[str, ...] | None = None, width=None) -> np.ndarray:
    """σ(DM DM → φ_i* → SM) through scalars mixing with the Higgs boson, every final state of Γ_h(√s).

    ``dm`` is "fermion" (couplings (y_s, y_p)), "scalar" or "vector" (couplings (μ, 0)). ``width``: Γ_h* as a function
    of √s, in place of the SM table's (``higgs.light_channel_width`` below it).
    """
    s = np.asarray(s, dtype=float)
    open_, s_ = _open(s, m)
    gamma = width(np.sqrt(s_)) if width is not None else higgs.width(np.sqrt(s_), channels)
    rp = _products(s_, mediators)
    total = np.zeros_like(s_)
    for i in range(len(mediators)):
        for j in range(len(mediators)):
            total += rp[i][j] * _scalar_in(s_, m, dm, dm_couplings[i], dm_couplings[j]) * kappas[i] * kappas[j] * gamma
    return np.where(open_, total, 0.0)


def scalar_to_fermions(s: np.ndarray, m: float, dm: str, dm_couplings: list[tuple[float, float]],
                       m_f: float, colours: int, f_couplings: list[tuple[float, float]],
                       mediators: list[Mediator]) -> np.ndarray:
    """σ(DM DM → φ_i* → f f̄) through scalars with couplings −φ f̄(g_s + i g_p γ⁵)f."""
    s = np.asarray(s, dtype=float)
    open_, s_ = _open(s, m, m_f)
    beta_f, root = _beta(s_, m_f), np.sqrt(s_)
    rp = _products(s_, mediators)
    total = np.zeros_like(s_)
    for i in range(len(mediators)):
        for j in range(len(mediators)):
            (gs_i, gp_i), (gs_j, gp_j) = f_couplings[i], f_couplings[j]
            out = colours * root * (gs_i * gs_j * beta_f ** 3 + gp_i * gp_j * beta_f) / (8.0 * np.pi)
            total += rp[i][j] * _scalar_in(s_, m, dm, dm_couplings[i], dm_couplings[j]) * out
    return np.where(open_, total, 0.0)


def sigma_v(sigma: np.ndarray, s: np.ndarray, m: float) -> np.ndarray:
    """σ v_rel with v_rel = 2β (the relative speed in the centre-of-momentum frame, β ≪ 1)."""
    return sigma * 2.0 * _beta(np.asarray(s, dtype=float), m)


def vector_unequal_to_fermions(s: np.ndarray, m1: float, m2: float, dm_couplings: list[tuple[float, float]],
                               m_f: float, colours: int, f_couplings: list[tuple[float, float]],
                               mediators: list[Mediator]) -> np.ndarray:
    """σ(χ₁χ₂ → V* → f f̄) for an off-diagonal vector current χ̄₂γ^μχ₁ with m₁ ≠ m₂ (inelastic dark matter).

    The dark trace contracted with the final state's transverse tensor gives
    T = 4s(s − m₁² − m₂² + 4m₁m₂) + 2(m₁ − m₂)²(s − (m₁ + m₂)²); σ = Σ_ij Re(P_iP_j*) a_i a_j
    × (2Γ_ij(√s)/√s) T / (4 · 2λ^½(s, m₁², m₂²)). For m₁ = m₂ it is the Dirac formula. The
    final state's longitudinal part, ∝ m_f²(m₁ − m₂)², is left out.
    """
    s = np.asarray(s, dtype=float)
    threshold = max(m1 + m2, 2.0 * m_f) ** 2
    open_ = s > threshold * (1.0 + 1e-12)
    s_ = np.where(open_, s, 2.0 * threshold + 1.0)
    lam = np.sqrt(np.clip((s_ - m1 * m1 - m2 * m2) ** 2 - 4.0 * m1 * m1 * m2 * m2, 0.0, None))
    trace = 4.0 * s_ * (s_ - m1 ** 2 - m2 ** 2 + 4.0 * m1 * m2) + 2.0 * (m1 - m2) ** 2 * (s_ - (m1 + m2) ** 2)
    beta_f = _beta(s_, m_f)
    root = np.sqrt(s_)
    rp = _products(s_, mediators)
    total = np.zeros_like(s_)
    for i in range(len(mediators)):
        for j in range(len(mediators)):
            (af_i, bf_i), (af_j, bf_j) = f_couplings[i], f_couplings[j]
            width = colours * root * beta_f * (af_i * af_j * (1.0 + 2.0 * m_f ** 2 / s_)
                                               + bf_i * bf_j * beta_f ** 2) / (12.0 * np.pi)
            total += rp[i][j] * dm_couplings[i][0] * dm_couplings[j][0] * (2.0 * width / root) * trace / (8.0 * lam)
    return np.where(open_, total, 0.0)
