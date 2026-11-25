"""The Standard Model Higgs boson: its couplings, and its width at any virtuality (the portal models).

Annihilation through an s-channel Higgs boson into Standard Model states X
factorises into the dark sector's vertex and the width a Higgs boson of mass
√s would have,

    σ(DM DM → h* → X) ∝ √s Γ_h(√s) / |s − m_h² + i m_h Γ_h|² ,

which sums every final state, including those with one boson off its shell
(Cline, Kainulainen, Scott & Weniger, arXiv:1306.4710). This module gives
Γ_h(m) by channel:
- **f f̄** (b, c, τ, μ, t): Γ = N_c G_F m_f(m)² m β³/(4√2π), with m_b and m_c run
  at one loop in QCD to the scale m;
- **W W and Z Z**, with both bosons on or off their shells: the double
  Breit–Wigner integral of the two-body width (the treatment of HDECAY), which
  is smooth through the threshold;
- **g g**: the quark loops (t, b, c) with α_s(m) at one loop;
- **γγ and Zγ**: scaled from their values at 125.09 GeV as m³ (together 0.4%).

Each channel is anchored to the LHC Higgs Cross Section Working Group's value
at m_h = 125.09 GeV (CERN Yellow Report 4, arXiv:1610.07922; the branching
ratio page of 2016): one constant per channel stands for the higher orders, so
that Γ_h(125.09 GeV) = 4.100 MeV with the tabulated branching ratios. Away from
the Higgs mass the shape is the leading-order one. The WW and ZZ factors (1.016 and
1.096) are calibrated where one boson is far off its shell; they are kept up to
m_h and fade linearly to 1 at the pair threshold 2M_V, so that on-shell pairs have
the leading-order width (release audit: the ZZ factor applied at every virtuality
gave +9.6% there). The fermion and gluon factors, QCD corrections, apply at every m. Below m ≈ 10 GeV the hadronic
channels are only indicative (perturbative quarks and gluons).
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

G_F = 1.1663787e-5                 # GeV⁻²
V_HIGGS = 246.22                   # GeV, (√2 G_F)^(−1/2)
M_H = 125.09
M_H_SIGMA = 0.24                   # GeV: ATLAS and CMS's combined m_h = 125.09 ± 0.21 (stat) ± 0.11 (syst), arXiv:1503.07589
M_W, GAMMA_W = 80.37, 2.085
M_Z, GAMMA_Z = 91.1876, 2.4952
SIN2_W = 0.2312
ALPHA_S_MZ = 0.118
M_T_POLE = 172.5
M_B_MSBAR, M_C_MSBAR = 4.18, 1.27  # m_q(m_q)
M_B_POLE, M_C_POLE = 4.78, 1.67    # the Higgs widths' own thresholds and loop masses (pole masses): this
                                   # prescription's, kept for h; the benchmarks' kinematics are
                                   # kinematics.KINEMATIC_MASSES (b 4.7, the DMsimp card's)
LEPTONS = {"tau": 1.77686, "mu": 0.10566}

# CERN YR4 (arXiv:1610.07922), branching ratio page, m_H = 125.09 GeV
YR4_WIDTH_GEV = 4.100e-3
YR4_BR = {"b": 5.809e-1, "tau": 6.256e-2, "mu": 2.171e-4, "c": 2.884e-2, "g": 8.180e-2,
          "gamma": 2.270e-3, "Zgamma": 1.541e-3, "W": 2.152e-1, "Z": 2.641e-2}


def alpha_s(mu: float) -> float:
    """α_s(μ) at one loop, from α_s(m_Z) with five flavours (four below m_b, six above m_t)."""
    def run(a0: float, mu0: float, mu1: float, nf: int) -> float:
        b0 = (33.0 - 2.0 * nf) / (12.0 * math.pi)
        return a0 / (1.0 + a0 * b0 * math.log(mu1 ** 2 / mu0 ** 2))
    mu = max(mu, 1.5)
    if mu >= M_T_POLE:
        return run(run(ALPHA_S_MZ, M_Z, M_T_POLE, 5), M_T_POLE, mu, 6)
    if mu >= M_B_MSBAR:
        return run(ALPHA_S_MZ, M_Z, mu, 5)
    return run(run(ALPHA_S_MZ, M_Z, M_B_MSBAR, 5), M_B_MSBAR, mu, 4)


def running_mass(quark: str, mu: float) -> float:
    """m_b(μ) or m_c(μ) at one loop (MS-bar): m(μ) = m(m) [α_s(μ)/α_s(m)]^(γ₀/2β₀)."""
    mu = max(mu, 1.5)
    if quark == "b":
        return M_B_MSBAR * (alpha_s(mu) / alpha_s(M_B_MSBAR)) ** (12.0 / 23.0)
    if mu <= M_B_MSBAR:
        return M_C_MSBAR * (alpha_s(mu) / alpha_s(M_C_MSBAR)) ** (12.0 / 25.0)
    at_mb = M_C_MSBAR * (alpha_s(M_B_MSBAR) / alpha_s(M_C_MSBAR)) ** (12.0 / 25.0)
    return at_mb * (alpha_s(mu) / alpha_s(M_B_MSBAR)) ** (12.0 / 23.0)


def _fermions(m: float, name: str) -> float:
    if name in ("b", "c"):
        pole, mass, colours = (M_B_POLE, running_mass(name, m), 3) if name == "b" else (M_C_POLE, running_mass(name, m), 3)
    elif name == "t":
        pole = mass = M_T_POLE
        colours = 3
    else:
        pole = mass = LEPTONS[name]
        colours = 1
    if m <= 2.0 * pole:
        return 0.0
    beta = math.sqrt(1.0 - 4.0 * pole ** 2 / m ** 2)
    return colours * G_F * mass ** 2 * m * beta ** 3 / (4.0 * math.sqrt(2.0) * math.pi)


def _two_body_vv(m: float, q1: np.ndarray, q2: np.ndarray, delta: float) -> np.ndarray:
    """Γ(h → V(q1) V(q2)) for virtualities q1, q2 (GeV): δ G_F m³/(16√2π) λ^½ (λ + 12 x₁x₂)."""
    x1, x2 = (q1 / m) ** 2, (q2 / m) ** 2
    lam = np.clip((1.0 - x1 - x2) ** 2 - 4.0 * x1 * x2, 0.0, None)
    return delta * G_F * m ** 3 / (16.0 * math.sqrt(2.0) * math.pi) * np.sqrt(lam) * (lam + 12.0 * x1 * x2)


@lru_cache(maxsize=4096)
def _vector_pair(m: float, boson: str) -> float:
    """Γ(h → VV) with both bosons on or off their shells (double Breit–Wigner, HDECAY's treatment)."""
    mass, width, delta = (M_W, GAMMA_W, 2.0) if boson == "W" else (M_Z, GAMMA_Z, 1.0)
    if m < 1.0:
        return 0.0
    if m > 2.0 * mass + 40.0 * width:            # far above threshold: both on shell
        return float(_two_body_vv(m, np.array([mass]), np.array([mass]), delta)[0])
    # q² = M² + MΓ tan θ maps the Breit–Wigner to a flat measure in θ
    lo, hi = math.atan((0.0 - mass ** 2) / (mass * width)), math.atan((m ** 2 - mass ** 2) / (mass * width))
    t = np.linspace(lo, hi, 400)
    q = np.sqrt(np.clip(mass ** 2 + mass * width * np.tan(t), 0.0, None))
    t1, t2 = np.meshgrid(t, t, indexing="ij")
    q1, q2 = np.meshgrid(q, q, indexing="ij")
    integrand = np.where(q1 + q2 < m, _two_body_vv(m, q1, q2, delta), 0.0) / math.pi ** 2
    return float(np.trapezoid(np.trapezoid(integrand, t, axis=1), t))


def _gluons(m: float) -> float:
    """Γ(h → gg) = G_F α_s² m³/(36√2π³) |Σ_q (3/4) A_½(τ_q)|² (t, b, c loops)."""
    def a_half(tau: float) -> complex:
        if tau <= 1.0:
            f = complex(math.asin(math.sqrt(tau)) ** 2)
        else:
            r = math.sqrt(1.0 - 1.0 / tau)
            f = -0.25 * (math.log((1.0 + r) / (1.0 - r)) - 1j * math.pi) ** 2
        return 2.0 * (tau + (tau - 1.0) * f) / tau ** 2
    total = sum(0.75 * a_half(m ** 2 / (4.0 * q ** 2)) for q in (M_T_POLE, M_B_POLE, M_C_POLE))
    return G_F * alpha_s(m) ** 2 * m ** 3 / (36.0 * math.sqrt(2.0) * math.pi ** 3) * abs(total) ** 2


def _leading_order(m: float) -> dict[str, float]:
    return {"b": _fermions(m, "b"), "c": _fermions(m, "c"), "tau": _fermions(m, "tau"),
            "mu": _fermions(m, "mu"), "t": _fermions(m, "t"), "W": _vector_pair(round(m, 6), "W"),
            "Z": _vector_pair(round(m, 6), "Z"), "g": _gluons(m)}


@lru_cache(maxsize=1)
def _anchors() -> dict[str, float]:
    """One factor per channel: the Working Group's partial width at 125.09 GeV over the leading order."""
    lo = _leading_order(M_H)
    return {k: YR4_BR[k] * YR4_WIDTH_GEV / lo[k] for k in ("b", "c", "tau", "mu", "W", "Z", "g")} | {"t": 1.0}


def anchor(name: str, m: float) -> float:
    """The channel's higher-order factor at virtuality m (module docstring)."""
    k = _anchors()[name]
    if name not in ("W", "Z"):
        return k
    threshold = 2.0 * (M_W if name == "W" else M_Z)
    fade = min(max((threshold - m) / (threshold - M_H), 0.0), 1.0)
    return 1.0 + (k - 1.0) * fade


def partial_widths(m: float) -> dict[str, float]:
    """Γ(h* → X) in GeV by channel for a Higgs boson of mass m (GeV)."""
    out = {name: anchor(name, m) * value for name, value in _leading_order(m).items()}
    scale = (m / M_H) ** 3
    out["gamma"] = YR4_BR["gamma"] * YR4_WIDTH_GEV * scale
    out["Zgamma"] = YR4_BR["Zgamma"] * YR4_WIDTH_GEV * scale if m > M_Z else 0.0
    return out


WIDTH_FROM = 2.0          # GeV: the SM width's table starts here; below it ``width`` gives none (not a physical zero)


@lru_cache(maxsize=1)
def _table() -> tuple[np.ndarray, dict[str, np.ndarray]]:
    masses = np.geomspace(WIDTH_FROM, 2e4, 700)
    rows = [partial_widths(float(m)) for m in masses]
    return masses, {k: np.array([r[k] for r in rows]) for k in rows[0]}


def width(m: float | np.ndarray, channels: tuple[str, ...] | None = None) -> np.ndarray:
    """Γ_h(m) in GeV, summed over all channels (or the ones named), interpolated in ln m on the table; above its last
    mass, the partial widths' sum at m itself (the second addendum to cycle 3, AL3-34, 2026-11-16: the width had been
    held at its 20 TeV value, 8 times too small at 40 TeV)."""
    masses, table = _table()
    m = np.asarray(m, dtype=float)
    names = channels or tuple(table)
    total = sum(table[k] for k in names)
    out = np.exp(np.interp(np.log(np.clip(m, masses[0], masses[-1])), np.log(masses),
                           np.log(np.maximum(total, 1e-300)))) * (m >= masses[0])
    above = m > masses[-1]
    if np.any(above):
        out = np.where(above, np.vectorize(lambda x: sum(partial_widths(float(x))[k] for k in names))(
            np.where(above, m, masses[-1])), out)
    return out


M_E = 0.51099895e-3


def leptonic_width(m: float) -> float:
    """Γ(h* → e⁺e⁻, μ⁺μ⁻, τ⁺τ⁻) in GeV for a Higgs boson of mass m at tree level, G_F m_ℓ² m β³/(4√2π) for each open
    lepton: below ``WIDTH_FROM`` the part of its width ADROIT computes (no hadron is open below 2m_π; above it the
    hadronic part is not computed, ``hadronic_window``)."""
    return float(sum(light_channel_width(m, name) for name in ("e", "mu", "tau")))


def light_channel_width(m: float | np.ndarray, channel: str) -> np.ndarray:
    """Γ(h* → channel) in GeV for a Higgs boson of mass m below ``WIDTH_FROM``, where the table has none: a charged
    lepton pair ("e", "mu", "tau") at tree level (the table's μ⁺μ⁻ carries YR4's higher-order factor, 0.971, so the
    rate steps by 3% at 2 GeV), and γγ by the table's own prescription (YR4's branching scaled as m³). The quark and
    gluon pairs are not here: closed below 2m_π and not computed in the hadronic window (``hadronic_window``); the
    four-body W*W* and Z*Z*, below 3 × 10⁻¹⁰ of μ⁺μ⁻ at 2 GeV and falling faster below it, are left out."""
    m = np.asarray(m, dtype=float)
    if channel == "gamma":
        return YR4_BR["gamma"] * YR4_WIDTH_GEV * (m / M_H) ** 3
    mass = {"e": M_E, **LEPTONS}[channel]
    beta2 = np.clip(1.0 - 4.0 * mass ** 2 / np.maximum(m, 1e-300) ** 2, 0.0, None)
    return np.where(m > 2.0 * mass, G_F * mass ** 2 * m * beta2 ** 1.5 / (4.0 * math.sqrt(2.0) * math.pi), 0.0)


def branching(m: float) -> dict[str, float]:
    """The branching ratios of a Higgs boson of mass m."""
    widths = partial_widths(m)
    total = sum(widths.values())
    return {k: v / total for k, v in widths.items()}


GAMMA_H = YR4_WIDTH_GEV
