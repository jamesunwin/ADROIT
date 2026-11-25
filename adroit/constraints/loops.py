"""Direct detection at loop level and higher twist: the portals whose leading scattering is not at tree level.

1. **A coloured scalar partner** φ of a right-handed quark (L ⊃ y φ* χ̄ P_R q + h.c.), Majorana χ:
   the scalar, twist-2 and gluon couplings of Hisano, Ishiwata & Nagata (arXiv:1007.2601 eqs. 6,
   19, 26–31; arXiv:1502.02244 eq. 14). With Δ = m_φ² − m_χ² and q → 0 quark masses:
   f_q = y² m_χ/(16Δ²), g_q⁽¹⁾ = y² m_χ/(4Δ²), and the gluon coupling f_G = −α_s y² m_χ/(192π m_φ²Δ)
   (short distance) plus, for a heavy quark, c_Q (−α_s y² m_χ/(192π Δ²)) (long distance). Then

       f_N/m_N = f_q f_Tq + ¾ [q(2) + q̄(2)] g_q⁽¹⁾ − (8π/9α_s) f_TG f_G ,   σ = (4/π) μ² f_N² ,

   so in ADROIT's normalisation c₁ = 2 f_N. Twist-2 dominates; valid for m_φ − m_χ ≫ m_N.
2. **A lepton partner**, Majorana χ: the anapole form factor F_A (Kopp, Michaels & Smirnov
   arXiv:1401.6457 eq. 10, the full Majorana amplitude coefficient; Sandick et al. arXiv:1608.00642)
   and its nonrelativistic operators, c₈ᵖ = 2eF_A, c₈ⁿ = 0, |c₉ᴺ| = g_N e F_A (g_p = 5.586, g_n = −3.826;
   Del Nobile arXiv:1806.01291 eqs. 2.39, 2.42), built from the library's card M_anapole
   (``parameter_space.operator_limits``). Kopp et al.'s own rate formula, and Bai & Berger's, are not
   consistent with F_A by a factor 4 in rate (the loop survey, 2026-10-04).
   A Dirac χ has F_A/2, and also a charge radius b_χ and a magnetic moment μ_χ (Ibarra & Wild
   arXiv:1503.03382 eqs. 10–13), whose contact part is c₁ᵖ = −e(b_χ + μ_χ/2m_χ).
3. **The 2HDM+a**, Dirac χ: the triangle diagrams through h and H exchange (Abe, Fujiwara & Hisano
   arXiv:1810.01039 eqs. 3.28–3.38, A.56–A.61 with the (t_β − 1/t_β) correction to A.59–A.61), the
   leading contribution for tan β ≲ 10; the boxes (≲ 10%) are left out.
"""

from __future__ import annotations

import math

from scipy.integrate import quad

E_CHARGE = 0.3028
V_EW, M_H, M_NUCLEON = 246.22, 125.09, 0.9389
# hadronic inputs of arXiv:1502.02244 (Tables 1–2): f_Tq and second moments at m_Z
F_T = {"p": {"u": 0.019, "d": 0.027, "s": 0.009}, "n": {"u": 0.013, "d": 0.040, "s": 0.009}}
MOMENTS = {"p": {"u": 0.223 + 0.036, "d": 0.118 + 0.037, "s": 0.0516, "c": 0.0374, "b": 0.0234},
           "n": {"u": 0.118 + 0.037, "d": 0.223 + 0.036, "s": 0.0516, "c": 0.0374, "b": 0.0234}}
C_HEAVY = {"c": 1.32, "b": 1.19, "t": 1.0}
# the 2HDM+a triangles use micrOMEGAs's f_Tq (Abe et al. Table 4)
F_T_AFH = {"p": {"u": 0.0153, "d": 0.0191, "s": 0.0447}, "n": {"u": 0.0110, "d": 0.0273, "s": 0.0447}}


def _coloured_terms(m_chi: float, m_phi: float, y: float, quark: str, nucleon: str) -> tuple[float, float, float]:
    """(scalar, twist-2, gluon) parts of f_N/m_N (GeV⁻³) for Majorana χ with a coloured partner of the quark."""
    delta = m_phi ** 2 - m_chi ** 2
    scalar = y * y * m_chi / (16.0 * delta ** 2)
    twist = y * y * m_chi / (4.0 * delta ** 2)
    gluon_short = y * y * m_chi / (216.0 * m_phi ** 2 * delta)          # −(8π/9α_s) f_G, α_s cancels
    gluon_long = C_HEAVY.get(quark, 0.0) * y * y * m_chi / (216.0 * delta ** 2)
    f_tg = 1.0 - sum(F_T[nucleon].values())
    return (F_T[nucleon].get(quark, 0.0) * scalar, 0.75 * MOMENTS[nucleon][quark] * twist,
            f_tg * (gluon_short + gluon_long))


def coloured_partner_si(m_chi: float, m_phi: float, y: float, quark: str) -> tuple[float, float]:
    """(f_p, f_n) in GeV⁻² of Majorana χ with a coloured partner of the quark (module docstring, item 1)."""
    return tuple(M_NUCLEON * sum(_coloured_terms(m_chi, m_phi, y, quark, n)) for n in ("p", "n"))


# ⟨x²⟩/⟨x⟩ of quark plus antiquark at μ = m_Z (PDF4LHC21_40, central member; docs/twist2/moments.py), the larger of
# proton and neutron (u in the neutron is d in the proton). They bound the twist-2 series' remainder below.
TWIST2_RATIO = {"u": 0.183, "d": 0.183, "s": 0.062, "c": 0.057, "b": 0.041}


def coloured_partner_weight(m_chi: float, m_phi: float, quark: str) -> float:
    """The fraction w of the near-degeneracy bound ε/(1 − ε) that applies to a Majorana χ's amplitude.

    The twist-2 coefficient expands the partner's propagator in ε x: term n carries ⟨x^{n+1}⟩, and since x ≤ 1 every
    moment beyond ⟨x²⟩ is at most ⟨x²⟩, so its remainder is at most (⟨x²⟩/⟨x⟩) ε/(1 − ε) (a bound, not the
    resummed value). The scalar and gluon parts keep the full ε/(1 − ε). So w = (r T + S + G)/(T + S + G), the larger
    over proton and neutron (the full calculation: docs/twist2/README.md)."""
    r = TWIST2_RATIO.get(quark, 1.0)
    out = 0.0
    for nucleon in ("p", "n"):
        scalar, twist, gluon = (abs(v) for v in _coloured_terms(m_chi, m_phi, 1.0, quark, nucleon))
        total = scalar + twist + gluon
        out = max(out, (r * twist + scalar + gluon) / total if total > 0 else 1.0)
    return out


def anapole_moment(m_chi: float, m_phi: float, y: float, m_lepton: float) -> float:
    """F_A (GeV⁻²) of Majorana χ with a charged scalar partner of a lepton (Kopp et al. eq. 10)."""
    mu, eps = (m_phi / m_chi) ** 2, (m_lepton / m_chi) ** 2
    _, ratio = _loop_ratio(mu, eps)
    bracket = 1.5 * math.log(mu / eps) - (1.0 + 3.0 * mu - 3.0 * eps) * ratio
    return -E_CHARGE * y * y / (96.0 * math.pi ** 2 * m_chi ** 2) * bracket


def _loop_ratio(mu: float, eps: float) -> tuple[float, float]:
    """(D, artanh(√D/(μ−1+ε))/√D) with D = (μ−1−ε)² − 4ε, continued to arctan for D < 0."""
    d = (mu - 1.0 - eps) ** 2 - 4.0 * eps
    c = mu - 1.0 + eps
    if d > 0:
        root = math.sqrt(d)
        return d, math.atanh(min(root / c, 1.0 - 1e-15)) / root
    root = math.sqrt(-d)
    return d, math.atan(root / c) / root


def dirac_moments(m_chi: float, m_phi: float, y: float, m_lepton: float) -> tuple[float, float]:
    """(μ_χ in GeV⁻¹, b_χ in GeV⁻²) of Dirac χ with a charged scalar partner of a lepton (Q_f = −1;
    Ibarra & Wild eqs. 10–13), both including the charge e."""
    mu, eps = (m_phi / m_chi) ** 2, (m_lepton / m_chi) ** 2
    d, ratio = _loop_ratio(mu, eps)
    e = E_CHARGE * y * y
    moment = e / (32.0 * math.pi ** 2 * m_chi) * ((-d + 1.0 - mu - eps) * ratio + 0.5 * (eps - mu) * math.log(eps / mu) - 1.0)
    radius = e / (384.0 * math.pi ** 2 * m_chi ** 2) * (
        2.0 * (8.0 * d * d + (9.0 * mu + 7.0 * eps - 5.0) * d - 4.0 * eps * (3.0 * mu + eps - 1.0)) * ratio / d
        + (8.0 * mu - 8.0 * eps + 1.0) * math.log(eps / mu) + 4.0 * (4.0 + (mu + 3.0 * eps - 1.0) / d))
    return moment, radius


def _b0_prime(m_med: float, m_chi: float) -> float:
    return quad(lambda x: x * (1.0 - x) / (m_med ** 2 * x + m_chi ** 2 * (1.0 - x) ** 2), 0.0, 1.0, limit=200)[0]


def _b1_difference(m_big: float, m_small: float, m_chi: float) -> float:
    def f(x):
        return (1.0 - x) * math.log((m_big ** 2 * x + m_chi ** 2 * (1.0 - x) ** 2)
                                    / (m_small ** 2 * x + m_chi ** 2 * (1.0 - x) ** 2))
    return quad(f, 0.0, 1.0, limit=200)[0]


def two_hdma_couplings(m_a: float, m_A: float, m_H: float, m_Hc: float, sin_t: float, tan_b: float,
                       lam3: float, lp1: float, lp2: float) -> dict[str, float]:
    """The h and H trilinears to aa, aA, AA (GeV; Abe et al. A.56–A.61 with M² = 2M_H±² − M_H² + m_h² − λ₃v²)."""
    v, s, c = V_EW, sin_t, math.sqrt(1.0 - sin_t ** 2)
    cb, sb = 1.0 / math.sqrt(1.0 + tan_b ** 2), tan_b / math.sqrt(1.0 + tan_b ** 2)
    lbar = lp1 * cb ** 2 + lp2 * sb ** 2
    m2 = 2.0 * m_Hc ** 2 - m_H ** 2 + M_H ** 2 - lam3 * v * v
    t = tan_b - 1.0 / tan_b
    s2b = 2.0 * sb * cb
    return {"haa": (2 * m2 - 2 * m_a ** 2 - M_H ** 2) * s * s / v - 2 * v * lbar * c * c,
            "hAA": (2 * m2 - 2 * m_A ** 2 - M_H ** 2) * c * c / v - 2 * v * lbar * s * s,
            "haA": -(2 * m2 - m_a ** 2 - m_A ** 2 - M_H ** 2) * s * c / v - 2 * v * lbar * s * c,
            "Haa": (m2 - m_H ** 2) * (s * s / v) * t - v * (lp1 - lp2) * s2b * c * c,
            "HaA": (m_H ** 2 - m2) * (s * c / v) * t - v * (lp1 - lp2) * s2b * s * c,
            "HAA": (m2 - m_H ** 2) * (c * c / v) * t - v * (lp1 - lp2) * s2b * s * s}


def two_hdma_si(m_chi: float, m_a: float, m_A: float, m_H: float, m_Hc: float, sin_t: float, tan_b: float,
                lam3: float, lp1: float, lp2: float, y: float) -> tuple[float, float]:
    """(C_p, C_n) in GeV⁻² of the 2HDM+a's Dirac χ (σ = μ²C²/π, ADROIT's c₁), from the h and H triangles."""
    g = two_hdma_couplings(m_a, m_A, m_H, m_Hc, sin_t, tan_b, lam3, lp1, lp2)
    xa, xA = y * math.sqrt(1.0 - sin_t ** 2), y * sin_t
    b0a, b0A = _b0_prime(m_a, m_chi), _b0_prime(m_A, m_chi)
    mixed = _b1_difference(m_A, m_a, m_chi) / (m_A ** 2 - m_a ** 2) if abs(m_A - m_a) > 1e-6 else 0.0
    c_phi = {}
    for phi in ("h", "H"):
        c_phi[phi] = -m_chi / (16.0 * math.pi ** 2) * (g[phi + "aa"] * xa * xa * b0a + g[phi + "AA"] * xA * xA * b0A
                                                       + 2.0 * g[phi + "aA"] * xA * xa * mixed)
    xi = {"up": {"h": 1.0, "H": -1.0 / tan_b}, "down": {"h": 1.0, "H": tan_b}}
    masses = {"h": M_H, "H": m_H}

    def c_q(kind: str) -> float:
        return -sum(xi[kind][phi] * c_phi[phi] / (masses[phi] ** 2 * V_EW) for phi in ("h", "H"))
    kinds = {"u": "up", "d": "down", "s": "down", "c": "up", "b": "down", "t": "up"}
    c_g = 2.0 / 27.0 * sum(c_q(kinds[q]) for q in ("c", "b", "t"))
    out = []
    for nucleon in ("p", "n"):
        f_tg = 1.0 - sum(F_T_AFH[nucleon].values())
        out.append(M_NUCLEON * (sum(c_q(kinds[q]) * F_T_AFH[nucleon][q] for q in ("u", "d", "s")) + c_g * f_tg))
    return out[0], out[1]
