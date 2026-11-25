"""The resummed γ-ray line and endpoint of a pure SU(2) n-plet of Majorana dark matter (odd n, Y = 0), at NLL (G8;
the owner's decision of 2026-10-15).

**The factorisation** is Baumgart et al.'s for the wino (arXiv:1808.08956), extended by Baumgart, Rodd, Slatyer &
Vaidya to the quintuplet (arXiv:2309.11562, Sec. 2). Every function of the soft-collinear effective theory (the hard
evolution U_H, the jet and soft evolutions V_J, V_S, ω_J, ω_S, and Λ^a–Λ^d) is independent of the representation. The
dark matter enters only through the operator χᵀiσ₂{T^a, T^b}χ between the incoming χ⁰χ⁰ pair and the vacuum. Charge
conservation leaves two structures of it, M^{ab} = A δ^{ab}_⊥ + B δ^{a3}δ^{b3}, so with the Sommerfeld amplitudes s₀Q
of the pairs (χ^{+Q}χ^{−Q}) at the origin (j = (n − 1)/2):

    b = Σ_{Q≥1} Q² s₀Q,    a = ½ j(j + 1) (√2 s₀₀ + 2 Σ_{Q≥1} s₀Q) − b,

and the two combinations of the factorisation are

    𝓕₀ = 2 Λ^d |a + b|² + r_HS^{12/β₀} Λ^c |a − 2b|²,
    𝓕₁ = r_H^{6/β₀} [ r_HS^{6/β₀} Λ^a |a − 2b|² + c_H Λ^b (8|b|² − 4|a|² + 4 Re ab*) − 12 s_H Λ^b Im ab* ].

These reproduce, term by term, the wino's (a = s₀± + √2 s₀₀, b = s₀±) and the quintuplet's (a = 2s₀±± + 5s₀± + 3√2
s₀₀, b = 4s₀±± + s₀±) published 𝓕₀ and 𝓕₁ (``tests/constraints/test_endpoint_nll.py``). The tree-level line is
2πα₂²s_W²|b|²/M².

**The rate** is the cumulative cross-section of photons with E > z_cut M (the line-equivalent rate H.E.S.S. compares;
the exclusive γγ + ½Zγ line is its z_cut → 1 limit), eq. (4.6) of arXiv:1808.08956 at the canonical scales μ_H = 2M,
μ_J = 2M√(1 − z), μ_S = 2M(1 − z) (each not below m_W, where its evolution stops). The weak coupling runs at one loop
(β₀ = 19/6) from 1/α(m_Z) = 127.944 and s_W²(m_Z) = 0.23126, the papers' inputs.

**The line searches' rate** (``line_sigma_v``) is the cumulative rate above z_cut = 1 − 0.10, the H.E.S.S. window
(``searches.HESS_LINE_RESOLUTION``), at the relative speed 10⁻³ (``searches.LINE_SPEED``; the quintuplet paper's
v). It is computed for 1–100 TeV: below, the factorisation's M ≫ m_W fails (arXiv:1808.08956 Sec. 5); above, it is not
checked. Bound states' own lines are not included (arXiv:2309.11562 Fig. 7: subdominant except at isolated masses near
the Sommerfeld peaks).

**Checks** (docs/g8_today.md). The wino, with DMγSpec's own NLO Sommerfeld factors, is within 4% of its NLL′ rate at
every z_cut from 0.7 to 0.99, from 1 to 10 TeV. The quintuplet's line is that paper's (Fig. 1) within 1.7% at the
thermal mass 13.6 TeV (inside its band), and its NLL/tree ratio is that paper's within 1–3% from 1 to 100 TeV.

**The Sommerfeld amplitudes** come from the potential of arXiv:2309.11562 eq. (3.5) (γ, Z and W exchange between the
neutral pairs) at NLO: the W and Z Yukawa terms take Beneke, Szafron & Urban's fitting functions (arXiv:1909.04584,
2107.09688), as that paper's eq. (3.7) writes them, on the same group structure, so for any n. The potential's
coupling is the quintuplet paper's, α₂ = α(m_Z)/s_W² = 0.0338: with it the quintuplet's thirteen Sommerfeld
resonances between 1.8 and 90 TeV fall within 0.4% of that paper's (Fig. 15), while Beneke et al.'s own α̂₂(m_Z) =
0.0350 (DMγSpec's wino) puts them 3–4% lower (``ALPHA2_BENEKE``). The splittings are M_Q − M₀ = Q²δ₀ with the
two-loop δ₀ = 164 MeV, so the pair thresholds are 2Q²δ₀ (``amplitudes``). The NLO terms move the resonances up in mass
by about 6% against the LO potential (the wino's first: 2.255 → 2.390 TeV here at α̂₂ = 0.0350, 2.282 → 2.421 in
DMγSpec). The phases are the formulas': an SU(2) singlet (M^{ab} ∝ δ^{ab}, so A = B)
has a = 2b, i.e. s₀Q = √2 s₀₀ for every Q. The charge basis of the generators (Condon–Shortley J±) writes the singlet
Σ_m (−1)^{j−m}|m, −m⟩, so its pair amplitudes carry (−1)^Q, which ``amplitudes`` removes. (For the wino this is
χ^± = (χ¹ ∓ iχ²)/√2 of arXiv:1808.08956, and DMγSpec's sign of Re s₀₀s₀±*.)
"""

from __future__ import annotations

import math

import numpy as np
from scipy.special import digamma, gamma, polygamma

ALPHA_MZ = 1.0 / 127.944          # α(m_Z)
SW2 = 0.23126                     # s_W²(m_Z)
M_W, M_Z = 80.379, 91.1876
BETA0, BETA1 = 19.0 / 6.0, -35.0 / 6.0
GAMMA0, GAMMA1 = 4.0, 4.0 * (70.0 / 9.0 - 2.0 * math.pi ** 2 / 3.0)   # the two-loop cusp, arXiv:1808.08956 eq. (3.7)
# (arXiv:2309.11562 prints (8/9)(35 − π²), a typo for 280/9 − 8π²/3: the audit's G8-6, G12)
EULER = 0.5772156649015329
ALPHA2_BENEKE = 0.0350009         # α̂₂(m_Z) of Beneke et al.'s NLO potential (arXiv:1909.04584) and of DMγSpec
DELTA0 = 0.164                    # M₊ − M₀ (GeV) at two loops; M_Q − M₀ = Q²δ₀ (arXiv:2309.11562 App. A)
GEV2_CM3_S = 0.3893794e-27 * 2.99792458e10      # GeV⁻² × c → cm³/s


def alpha_w(mu: float) -> float:
    """α₂(μ) at one loop from α₂(m_Z) = α/s_W²."""
    a = ALPHA_MZ / SW2 / (4.0 * math.pi)
    return 4.0 * math.pi * a / (1.0 + 2.0 * BETA0 * a * math.log(mu / M_Z))


def _r(mu0: float) -> float:
    """α₂(m_W)/α₂(μ₀) (one loop)."""
    return 1.0 / (1.0 + 2.0 * alpha_w(mu0) / (4.0 * math.pi) * BETA0 * math.log(M_W / mu0))


def _evolution(r: float, a0: float, sign: float, k: float) -> float:
    """exp{sign k Γ₀/β₀² [(ln r + 1/r − 1)/α̃(μ₀) + (Γ₁/Γ₀ − β₁/β₀)(r − 1 − ln r) − β₁/(2β₀) ln² r]}."""
    bracket = (math.log(r) + 1.0 / r - 1.0) / a0 + (GAMMA1 / GAMMA0 - BETA1 / BETA0) * (r - 1.0 - math.log(r)) \
        - BETA1 / (2.0 * BETA0) * math.log(r) ** 2
    return math.exp(sign * k * GAMMA0 / BETA0 ** 2 * bracket)


def ab(n: int, s: dict[int, complex]) -> tuple[complex, complex]:
    """(a, b) of an odd n-plet from its Sommerfeld amplitudes s = {Q: s₀Q} (module docstring)."""
    if n % 2 != 1 or n < 3:
        raise ValueError("an odd SU(2) representation, n ≥ 3")
    j = (n - 1) // 2
    charged = [s.get(q, 0.0) for q in range(1, j + 1)]
    b = sum(q * q * x for q, x in zip(range(1, j + 1), charged))
    a = 0.5 * j * (j + 1) * (math.sqrt(2.0) * s.get(0, 1.0) + 2.0 * sum(charged)) - b
    return complex(a), complex(b)


def structures(a: complex, b: complex, lam: tuple[float, float, float, float], r_h: float,
               r_hs: float) -> tuple[float, float]:
    """(𝓕₀, 𝓕₁) from (a, b), (Λ^a, Λ^b, Λ^c, Λ^d), r_H and r_HS = r_H/r_S (module docstring)."""
    lam_a, lam_b, lam_c, lam_d = lam
    phase = 6.0 * math.pi / BETA0 * math.log(r_h)
    c_h, s_h = math.cos(phase), math.sin(phase)
    ab_ = a * b.conjugate()
    f0 = 2.0 * lam_d * abs(a + b) ** 2 + r_hs ** (12 / BETA0) * lam_c * abs(a - 2 * b) ** 2
    f1 = r_h ** (6 / BETA0) * (r_hs ** (6 / BETA0) * lam_a * abs(a - 2 * b) ** 2
                               + c_h * lam_b * (8 * abs(b) ** 2 - 4 * abs(a) ** 2 + 4 * ab_.real)
                               - 12 * s_h * lam_b * ab_.imag)
    return f0, f1


def cumulative(m: float, n: int, s: dict[int, complex], z_cut: float = 1.0) -> float:
    """σv (cm³/s) of photons with E > z_cut M, line-equivalent, at NLL (module docstring)."""
    a, b = ab(n, s)
    one_minus = max(1.0 - z_cut, 1e-12)
    mu_h = 2.0 * m
    mu_j, mu_s = max(2.0 * m * math.sqrt(one_minus), M_W), max(2.0 * m * one_minus, M_W)
    th_j, th_s = float(2.0 * m * math.sqrt(one_minus) > M_W), float(2.0 * m * one_minus > M_W)
    a_h, a_j, a_s = (alpha_w(x) / (4.0 * math.pi) for x in (mu_h, mu_j, mu_s))
    r_h, r_j, r_s = _r(mu_h), _r(mu_j), _r(mu_s)
    u_h = r_h ** 2 * _evolution(r_h, a_h, -1.0, 2.0)
    v_j = math.exp(math.log(_evolution(r_j, a_j, 1.0, 2.0)) - math.log(r_j))
    v_s = _evolution(r_s, a_s, -1.0, 1.5)
    k = GAMMA1 / GAMMA0 - BETA1 / BETA0
    w_j = -2.0 * GAMMA0 / BETA0 * (math.log(r_j) + a_j * k * (r_j - 1.0)) * th_j
    w_s = 1.5 * GAMMA0 / BETA0 * (math.log(r_s) + a_s * k * (r_s - 1.0)) * th_s
    d1_j = EULER + digamma(1.0 - w_j)
    d2_j = d1_j ** 2 - polygamma(1, 1.0 - w_j)
    d1_js = EULER + digamma(1.0 - w_j - 2.0 * w_s)
    d2_js = d1_js ** 2 - polygamma(1, 1.0 - w_j - 2.0 * w_s)
    lam_a = 1 + a_j * GAMMA0 * d2_js * th_j + a_j * BETA0 * d1_js * th_j - 12 * a_s * (d2_js - d1_js) * th_s
    lam_b = 1 + a_j * GAMMA0 * d2_js * th_j + a_j * BETA0 * d1_js * th_j - 12 * a_s * d2_js * th_s
    lam_c = 1 + a_j * GAMMA0 * d2_j * th_j + a_j * BETA0 * d1_j * th_j + 24 * a_s * d1_j * th_s
    lam_d = 1 + a_j * GAMMA0 * d2_j * th_j + a_j * BETA0 * d1_j * th_j
    f0, f1 = structures(a, b, (lam_a, lam_b, lam_c, lam_d), r_h, r_h / r_s)
    jet = ((v_j - 1.0) * th_j + 1.0)
    soft = ((v_s - 1.0) * th_s + 1.0)
    body = f0 * math.exp(EULER * w_j) / gamma(1.0 - w_j) \
        + soft * f1 * math.exp(EULER * (w_j + 2.0 * w_s)) / gamma(1.0 - w_j - 2.0 * w_s)
    sigma_v = math.pi * alpha_w(mu_h) ** 2 * SW2 / (9.0 * m * m) * u_h * jet * body     # σ × v, GeV⁻²
    return float(sigma_v * GEV2_CM3_S)


MASS_RANGE = (1000.0, 100000.0)    # GeV: where line_sigma_v is computed (module docstring)


def line_sigma_v(n: int, m: float, v_rel: float = 1e-3, window: float = 0.10) -> float | None:
    """σv_line (cm³/s) of a pure Majorana n-plet (odd n, Y = 0) of mass ``m`` (GeV): the γγ-equivalent rate of
    photons with E > (1 − window) M at relative speed ``v_rel``, or None outside ``MASS_RANGE``."""
    if not MASS_RANGE[0] <= m <= MASS_RANGE[1]:
        return None
    return cumulative(m, n, amplitudes(n, m, v_rel), 1.0 - window)


NLL_BAND = 0.05           # NLL against NLL′: DMγSpec's NLL′ wino is 4% above this NLL off resonance (G8)


def theory_band(n: int) -> tuple[float, float, str]:
    """(low, high, why): the factors bracketing ``line_sigma_v``'s rate (decision D30, G12, the owner's points 4 and 5;
    decision D32). ±5% for the resummation's order (NLL here, NLL′ the next). For n ≥ 5, bound states' line photons
    are not computed: the quintuplet paper finds them a few percent of direct annihilation except at isolated masses
    near the Sommerfeld peaks (arXiv:2309.11562, Fig. 7), where they lead, so the rate has no justified upper edge
    (``math.inf``) and an allowed result is pending; they only add photons, so the lower edge, and an exclusion,
    stand (the external audit's A05, 2026-10-16: a +5% had been taken as the upper edge). For the wino they vanish at
    leading order (the L = 0 → 1 capture's coefficient is zero in unbroken SU(2))."""
    if n >= 5:
        return 1.0 - NLL_BAND, math.inf, ("NLL against NLL′ ±5%; bound states' line photons are not computed and can "
                                          "lead at isolated masses near the Sommerfeld peaks, so no upper edge")
    return 1.0 - NLL_BAND, 1.0 + NLL_BAND, "NLL against NLL′ ±5%"


def tree_line(m: float, n: int, s: dict[int, complex]) -> float:
    """The tree-level line with the Sommerfeld effect, σv_γγ + ½σv_Zγ = 2πα₂²s_W²|b|²/M² (cm³/s), α₂ at m_Z."""
    _, b = ab(n, s)
    return 2.0 * math.pi * (ALPHA_MZ / SW2) ** 2 * SW2 * abs(b) ** 2 / m ** 2 * GEV2_CM3_S


def generators(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(J₃, J₊, J₋) of spin j = (n − 1)/2 in the basis of charges j, j − 1, …, −j (arXiv:2309.11562 eq. (3.4))."""
    j = (n - 1) / 2
    q = np.array([j - k for k in range(n)])
    jp = np.zeros((n, n))
    for k in range(1, n):                          # J₊ |q⟩ = √(j(j+1) − q(q+1)) |q + 1⟩
        jp[k - 1, k] = math.sqrt(j * (j + 1) - q[k] * (q[k] + 1))
    return np.diag(q), jp, jp.T


def _delta_w(r: float, alpha2: float) -> float:
    """The NLO addition to e^{−m_W r} (arXiv:2309.11562 eq. (3.7)), L = ln(m_W r)."""
    x = M_W * r
    big = math.log(x)
    if x < 555.0 / 94.0:
        num = (big - 787 / 12) * (big - 736 / 373) * (big - 116 / 65) * (big * big - 286 * big / 59 + 533 / 77)
        den = (big - 512 / 19) * (big - 339 / 176) * (big - 501 / 281) * (big * big - 268 * big / 61 + 38 / 7)
        return -2595.0 / math.pi * alpha2 * math.exp(-79.0 * num / (34.0 * den))
    num = (big - 76 / 43) * (big - 28 / 17) * (big + 37 / 30) * (big * big - 389 * big / 88 + 676 / 129)
    den = (big - 191 / 108) * (big - 256 / 153) * (big + 8412 / 13) * (big * big - 457 * big / 103 + 773 / 146)
    return 2595.0 / math.pi * alpha2 * math.exp(-13267.0 * num / (5.0 * den))


def _delta_z(r: float, alpha2: float, sw2: float) -> float:
    """The NLO addition to c_W² e^{−m_Z r} (arXiv:2309.11562 eq. (3.7))."""
    x = M_W * r
    lz = math.log(M_Z * r)
    photon = -80.0 / 9.0 * sw2 ** 2 * (lz + EULER) / (2.0 * math.pi * (1.0 + 32.0 / 11.0 * x ** (-22.0 / 9.0)))
    running = (19.0 / 6.0 * lz - 1960.0 / 433.0) / (2.0 * math.pi * (1.0 + 7.0 / 59.0 * x ** (61.0 / 29.0)))
    rest = -sw2 * (-1.0 / 30.0 + 4.0 / 135.0 * math.log(x)) / (
        1.0 + 58.0 / 79.0 * x ** (-17.0 / 15.0) + x ** (119.0 / 120.0) / 30.0 + 8.0 / 177.0 * x ** (17.0 / 8.0))
    return alpha2 * (photon + running + rest)


def _pair_block(ta: np.ndarray, tb: np.ndarray, pairs: list[tuple[int, int]]) -> np.ndarray:
    """N N′ (T^A_{ii′} T^B_{jj′} + T^A_{ij′} T^B_{ji′}) between the pairs (L + S even)."""
    norm = [1.0 / math.sqrt(2.0) if i == k else 1.0 for i, k in pairs]
    c = np.zeros((len(pairs), len(pairs)))
    for p, (i, k) in enumerate(pairs):
        for p2, (i2, k2) in enumerate(pairs):
            c[p, p2] = norm[p] * norm[p2] * (ta[i, i2] * tb[k, k2] + ta[i, k2] * tb[k, i2])
    return c


def potential(n: int, alpha2: float, sw2: float, nlo: bool = True):
    """V(r) between the neutral pairs (χ^{+Q}χ^{−Q}, Q = j, …, 1, then χ⁰χ⁰), arXiv:2309.11562 eq. (3.5) with L + S
    even, as a function of r (GeV⁻¹ → GeV, an n_pairs × n_pairs matrix): α₂/r [N (s_W² + c_W² e^{−m_Z r}) +
    C e^{−m_W r}] with N the T³T³ structure and C the W's; at NLO each Yukawa term takes its addition (eq. (3.7))."""
    j3, jp, jm = generators(n)
    jj = (n - 1) // 2
    index = {q: jj - q for q in range(-jj, jj + 1)}
    pairs = [(index[q], index[-q]) for q in range(jj, 0, -1)] + [(index[0], index[0])]
    neutral = _pair_block(j3, j3, pairs)
    charged = 0.5 * (_pair_block(jp, jm, pairs) + _pair_block(jm, jp, pairs))

    def v(r: float) -> np.ndarray:
        z = (1.0 - sw2) * math.exp(-M_Z * r) + (_delta_z(r, alpha2, sw2) if nlo else 0.0)
        w = math.exp(-M_W * r) + (_delta_w(r, alpha2) if nlo else 0.0)
        return alpha2 * (neutral * (sw2 + z) + charged * w) / r
    return v


def amplitudes(n: int, m: float, v_rel: float, alpha2: float = ALPHA_MZ / SW2, sw2: float = SW2, nlo: bool = True,
               delta0: float = DELTA0) -> dict[int, complex]:
    """{Q: s₀Q}: the χ⁰χ⁰ pair's Sommerfeld amplitudes at the origin, at relative speed ``v_rel`` (``potential``;
    splittings Q²δ₀), normalised to s₀₀ = 1 without a potential, in the formulas' phases (module docstring)."""
    from adroit.constraints import sommerfeld
    jj = (n - 1) // 2
    thresholds = np.array([2.0 * q * q * delta0 for q in range(jj, 0, -1)] + [0.0])
    tails = np.array([q * q * alpha2 * sw2 for q in range(jj, 0, -1)] + [0.0])
    mu, kinetic = 0.5 * m, 0.25 * m * v_rel ** 2
    r_max = min(max(30.0 / M_W, 6.0 / math.sqrt(2.0 * mu * kinetic)), 400.0 / M_W)
    column = sommerfeld.enhancement(potential(n, alpha2, sw2, nlo), thresholds, tails, mu, kinetic,
                                    r_max=r_max)[:, -1]
    return {**{q: (-1) ** q * complex(column[jj - q]) for q in range(jj, 0, -1)}, 0: complex(column[-1])}
