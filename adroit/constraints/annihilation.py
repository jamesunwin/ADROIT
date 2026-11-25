"""Annihilation cross-sections of dark matter in the spin-1 simplified models (DM7).

Two processes, both at tree level and at every energy (arXiv:1703.05703,
Fig. 1):

**χχ̄ → f f̄ through the s-channel mediator**, for couplings (a, b) of χ and
of f in −Z′_μ ψ̄γ^μ(a + bγ⁵)ψ:

    σ(s) = N_c β_f / (12π s β_χ) × {F_χ(s) F_f(s) + 12 b_χ² b_f² m_χ² m_f² (1 − s/M²)²}
           / [(s − M²)² + M² Γ²] ,

    F_i(s) = a_i² (s + 2m_i²) + b_i² (s − 4m_i²) ,   β_i = √(1 − 4m_i²/s) .

The last term comes from the q_μq_ν/M² part of the propagator: it is the
helicity-suppressed s-wave of the axial-vector model. The formula agrees
with the explicit amplitude of ``amplitudes`` to 10⁻⁶ for every coupling
structure, and its v → 0 limits are eqs. 3.3 and 3.4 of arXiv:1703.05703.

**χχ̄ → Z′Z′ through t- and u-channel χ exchange**, open when m_χ > M. This
is computed from the explicit amplitude, with all polarisations: for an
axial-vector mediator the longitudinal modes matter beyond the s-wave.

The width Γ is fixed (a Breit–Wigner of constant width, as in MadDM).
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from adroit.constraints import amplitudes, spin1
from adroit.constraints.spin1 import Spin1Model

GEV2_TO_CM3_S = 0.3893793721e-27 * 2.99792458e10   # 1 GeV⁻² (× c) in cm³/s


def fermion_pair_sigma(s: np.ndarray, m: float, m_f: float, colours: int,
                       chi: tuple[float, float], f: tuple[float, float],
                       m_med: float, width: float) -> np.ndarray:
    """σ(χχ̄ → f f̄) in GeV⁻² at the squared energies s (zero below threshold)."""
    s = np.asarray(s, dtype=float)
    a_chi, b_chi = chi
    a_f, b_f = f
    threshold = 4.0 * max(m, m_f) ** 2
    open_ = s > threshold * (1.0 + 1e-12)          # rounding at the threshold itself is closed
    s_ = np.where(open_, s, 2.0 * threshold)
    beta_chi = np.sqrt(1.0 - 4.0 * m * m / s_)
    beta_f = np.sqrt(1.0 - 4.0 * m_f * m_f / s_)
    f_chi = a_chi ** 2 * (s_ + 2 * m * m) + b_chi ** 2 * (s_ - 4 * m * m)
    f_f = a_f ** 2 * (s_ + 2 * m_f * m_f) + b_f ** 2 * (s_ - 4 * m_f * m_f)
    longitudinal = 12.0 * b_chi ** 2 * b_f ** 2 * m * m * m_f * m_f * (1.0 - s_ / m_med ** 2) ** 2
    breit_wigner = (s_ - m_med ** 2) ** 2 + (m_med * width) ** 2
    sigma = colours * beta_f / (12.0 * np.pi * s_ * beta_chi) * (f_chi * f_f + longitudinal) / breit_wigner
    return np.where(open_, sigma, 0.0)


def _fermion_pair(s: np.ndarray, model: Spin1Model, m_dm: float, f: spin1.Fermion, gamma: float) -> np.ndarray:
    """σ(χχ̄ → f f̄) in GeV⁻²; a quark pair closed below the hadronic opening, √s < 2m_π (``hadronic_window``: no
    hadronic final state there; C21-02)."""
    from adroit.constraints import hadronic_window as hw
    s = np.asarray(s, dtype=float)
    sigma = fermion_pair_sigma(s, m_dm, f.mass_gev, f.colours, model.dm_couplings(), model.couplings(f),
                               model.m_med_gev, gamma)
    return np.where(np.sqrt(s) >= hw.opening(False), sigma, 0.0) if f.family == "quark" else sigma


def to_standard_model(s: np.ndarray, model: Spin1Model, m_dm: float) -> np.ndarray:
    """σ(χχ̄ → any f f̄) in GeV⁻², summed over quarks (from the hadronic opening), charged leptons and neutrinos."""
    gamma = spin1.width(model, m_dm)
    return sum(_fermion_pair(s, model, m_dm, f, gamma) for f in model.fermions())


# σ(χχ̄ → Z′Z′) × β_χ is smooth in u = √s/(2m) − 1 above its threshold and is tabulated
# once per (m, M). The threshold is u = M/m − 1 when m < M: the channel is then closed at
# rest but open in the thermal tail ("forbidden" annihilation, Griest & Seckel 1991).
_PAIR_STEPS = np.concatenate([[0.0], np.geomspace(1e-6, 20.0, 60)])


def _pair_threshold(m: float, m_med: float) -> float:
    return max(m_med / m - 1.0, 0.0)


@lru_cache(maxsize=512)
def _pair_table(m: float, m_med: float, a: float, b: float) -> tuple[np.ndarray, np.ndarray]:
    u_nodes = _pair_threshold(m, m_med) + _PAIR_STEPS
    values = []
    for u in u_nodes:
        s = (2.0 * m * (1.0 + max(u, 1e-9))) ** 2 * (1.0 + 1e-12)
        beta = np.sqrt(1.0 - 4.0 * m * m / s)
        values.append(amplitudes.pair_sigma(s, m, m_med, (a, b)) * beta)
    return u_nodes, np.array(values)


def to_mediator_pairs(s: np.ndarray, model: Spin1Model, m_dm: float) -> np.ndarray:
    """σ(χχ̄ → Z′Z′) in GeV⁻², interpolated from the explicit amplitude (zero below √s = 2M)."""
    s = np.asarray(s, dtype=float)
    if s.size == 0 or np.sqrt(s.max()) <= 2.0 * model.m_med_gev:
        return np.zeros_like(s)
    u_nodes, table = _pair_table(m_dm, model.m_med_gev, *model.dm_couplings())
    u = np.sqrt(s) / (2.0 * m_dm) - 1.0
    beta = np.sqrt(np.clip(1.0 - 4.0 * m_dm * m_dm / np.maximum(s, 1e-300), 0.0, None))
    smooth = np.interp(np.clip(u, u_nodes[0], u_nodes[-1]), u_nodes, table)
    open_ = (u > u_nodes[0]) & (beta > 0)
    return np.where(open_, smooth / np.where(beta > 0, beta, 1.0), 0.0)


def total(s: np.ndarray, model: Spin1Model, m_dm: float) -> np.ndarray:
    """The total annihilation cross-section σ(χχ̄ → anything) in GeV⁻²."""
    return to_standard_model(s, model, m_dm) + to_mediator_pairs(s, model, m_dm)


def sigma_v_today(model: Spin1Model, m_dm: float, v_rel: float = 1e-3) -> dict[str, float]:
    """σv (cm³/s) by channel at the relative speed ``v_rel`` (in units of c), e.g. in dwarf galaxies.

    The keys are the final states: each fermion's name, and "Z'Z'". A quark pair below the hadronic opening is zero
    (closed); in the hadronic window it is a free-quark number that the caller must not use
    (``spin1.annihilation_window``).
    """
    beta = 0.5 * v_rel                            # v_rel = 2β for small speeds
    s = 4.0 * m_dm ** 2 / (1.0 - beta ** 2)
    gamma = spin1.width(model, m_dm)
    out = {}
    for f in model.fermions():
        out[f.name] = float(_fermion_pair(np.array([s]), model, m_dm, f, gamma)[0]) * v_rel * GEV2_TO_CM3_S
    out["Z'Z'"] = float(to_mediator_pairs(np.array([s]), model, m_dm)[0]) * v_rel * GEV2_TO_CM3_S
    return out


def omega_h2(model: Spin1Model, m_dm: float) -> float:
    """The thermal relic density Ωh² of the model's dark matter (``relic``)."""
    from adroit.constraints import relic
    return relic.omega_h2(lambda s: total(s, model, m_dm), m_dm,
                          resonance_gev=model.m_med_gev, width_gev=spin1.width(model, m_dm))
