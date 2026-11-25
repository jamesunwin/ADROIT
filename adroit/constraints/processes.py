"""Tree-level 2 → 2 processes of the portal models, from explicit spinors and polarisations.

The method of ``amplitudes`` (DM7): spinors and polarisation vectors written
out in the Dirac representation, the squares summed numerically in the
centre-of-momentum frame, the angle integrated by Gauss–Legendre quadrature.
Nothing is expanded in the velocity. Processes:

- **fermion dark matter → two scalars** (χχ̄ → φ_a φ_b): t- and u-channel χ
  exchange with vertices −φ χ̄(y_s + i y_p γ⁵)χ, plus a contact or s-channel
  term C(s) χ̄(c_s + i c_p γ⁵)χ (a Higgs portal's χ̄χhh, an s-channel scalar);
- **scalar dark matter → hh**: contact, s-channel and t/u exchange;
- **vector dark matter → hh**: likewise, with the massive vector propagator;
- **t-channel mediators** (χ χ̄ or χχ → f f̄): a scalar φ with
  y φ* χ̄ P_R f + h.c., one diagram for Dirac and two (with the relative sign
  of Fermi statistics) for Majorana dark matter;
- **coannihilations of a scalar partner φ** carrying the charge of f under a
  gauge group (QCD's SU(3), or an abelian group in the unbroken phase):
  φφ* → VV, φφ* → f′f̄′ (s-channel V, and χ exchange for f′ = f), φφ → ff
  (Majorana χ), and χφ → fV.

Gauge invariance fixes the relative signs of the gauge diagrams; each
amplitude is checked by the Ward identity (ε → k gives zero) in the tests.
Colour is summed exactly: an amplitude T^bT^a A₁ + T^aT^b A₂ has
Σ|M|² = (16/3)(|A₁|² + |A₂|²) − (4/3) Re A₁A₂*.

Metric (+, −, −, −); natural units, GeV; cross-sections in GeV⁻².
"""

from __future__ import annotations

import numpy as np

from adroit.constraints.amplitudes import _BASIS, GAMMA, GAMMA5, METRIC, bar, polarisations, slash, spinor_u, spinor_v

UNIT = np.eye(4, dtype=complex)
P_L, P_R = 0.5 * (UNIT - GAMMA5), 0.5 * (UNIT + GAMMA5)
NODES = 24


def _dot(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.sum(x * y * METRIC, axis=-1)


def frame(s: float, m1: float, m2: float, m3: float, m4: float, cos_theta: np.ndarray):
    """p₁, p₂ along ±z and k₁, k₂ at angle θ in the CM frame, any masses; also |p| and |k|. A mass may be an array
    with one value per angle (``tree.Process.sigma_offshell``: the final legs' off-shell masses, row by row)."""
    root = np.sqrt(s)

    def momentum(a: float, b: float) -> float:
        return np.sqrt(np.maximum((s - (a + b) ** 2) * (s - (a - b) ** 2), 0.0)) / (2.0 * root)
    p, k = momentum(m1, m2), momentum(m3, m4)
    e1, e2 = (s + m1 ** 2 - m2 ** 2) / (2 * root), (s + m2 ** 2 - m1 ** 2) / (2 * root)
    e3, e4 = (s + m3 ** 2 - m4 ** 2) / (2 * root), (s + m4 ** 2 - m3 ** 2) / (2 * root)
    n = len(cos_theta)
    one, zero = np.ones(n), np.zeros(n)
    sin_theta = np.sqrt(1.0 - cos_theta ** 2)
    p1 = np.stack([e1 * one, zero, zero, p * one], axis=1)
    p2 = np.stack([e2 * one, zero, zero, -p * one], axis=1)
    k1 = np.stack([e3 * one, k * sin_theta, zero, k * cos_theta], axis=1)
    k2 = np.stack([e4 * one, -k * sin_theta, zero, -k * cos_theta], axis=1)
    return p1, p2, k1, k2, p, k


def _sigma(squared: np.ndarray, weights: np.ndarray, s: float, p: float, k: float, identical: bool) -> float:
    sigma = (k / p) / (32.0 * np.pi * s) * float(np.sum(weights * squared)) if p > 0 else 0.0
    return 0.5 * sigma if identical else sigma


def _yukawa(c: tuple[complex, complex]) -> np.ndarray:
    return c[0] * UNIT + 1j * c[1] * GAMMA5


def _propagator(ell: np.ndarray, m: float) -> np.ndarray:
    return (slash(ell) + m * UNIT[None]) / (_dot(ell, ell) - m * m)[:, None, None]


def fermion_to_scalars(s: float, m: float, m_a: float, m_b: float, y_a: tuple[float, float],
                       y_b: tuple[float, float], contact: tuple[complex, complex] = (0.0, 0.0),
                       identical: bool = False, points: int = NODES) -> float:
    """σ(χχ̄ → φ_a φ_b): t- and u-channel χ exchange plus a contact term (GeV⁻²)."""
    if np.sqrt(s) <= max(2.0 * m, m_a + m_b) * (1.0 + 1e-12):
        return 0.0
    x, w = np.polynomial.legendre.leggauss(points)
    p1, p2, k1, k2, p, k = frame(s, m, m, m_a, m_b, x)
    ga, gb, gc = _yukawa(y_a), _yukawa(y_b), _yukawa(contact)
    chain = gb @ _propagator(p1 - k1, m) @ ga + ga @ _propagator(p1 - k2, m) @ gb + gc[None]
    total = np.zeros(len(x))
    for x1 in _BASIS:
        u1 = spinor_u(p1[:, 1:], m, x1)
        for x2 in _BASIS:
            v2 = bar(spinor_v(p2[:, 1:], m, x2))
            total += np.abs(np.einsum("ni,nij,nj->n", v2, chain, u1)) ** 2
    return _sigma(total / 4.0, w, s, p, k, identical)


def scalars_to_scalars(s: float, m: float, m_out: float, contact: complex, mu: float, m_exchange: float,
                       identical: bool = True, points: int = NODES) -> float:
    """σ(SS → hh) for M = C(s) + μ²[1/(t − M²) + 1/(u − M²)] (scalar dark matter; real S, no spin average)."""
    if np.sqrt(s) <= max(2.0 * m, 2.0 * m_out) * (1.0 + 1e-12):
        return 0.0
    x, w = np.polynomial.legendre.leggauss(points)
    p1, p2, k1, k2, p, k = frame(s, m, m, m_out, m_out, x)
    t, u = _dot(p1 - k1, p1 - k1), _dot(p1 - k2, p1 - k2)
    amp = contact + mu * mu * (1.0 / (t - m_exchange ** 2) + 1.0 / (u - m_exchange ** 2))
    return _sigma(np.abs(amp) ** 2, w, s, p, k, identical)


def _initial_polarisations(p: np.ndarray, m: float) -> list[np.ndarray]:
    """Polarisations of a massive vector moving along ±z: two transverse and the longitudinal."""
    n = len(p)
    one, zero = np.ones(n), np.zeros(n)
    pz = p[:, 3]
    return [np.stack([zero, one, zero, zero], axis=1), np.stack([zero, zero, one, zero], axis=1),
            np.stack([np.abs(pz) / m, zero, zero, np.sign(pz) * p[:, 0] / m], axis=1)]


def vectors_to_scalars(s: float, m: float, m_out: float, contact: complex, mu: float,
                       identical: bool = True, points: int = NODES) -> float:
    """σ(VV → hh) for M = ε₁·ε₂ C(s) − μ² Σ_{t,u} ε₁·D(ℓ)·ε₂/(ℓ² − m²), D = −g + ℓℓ/m² (average over 9)."""
    if np.sqrt(s) <= max(2.0 * m, 2.0 * m_out) * (1.0 + 1e-12):
        return 0.0
    x, w = np.polynomial.legendre.leggauss(points)
    p1, p2, k1, k2, p, k = frame(s, m, m, m_out, m_out, x)
    total = np.zeros(len(x))
    for e1 in _initial_polarisations(p1, m):
        for e2 in _initial_polarisations(p2, m):
            amp = _dot(e1, e2) * contact
            for ell in (p1 - k1, p1 - k2):
                d = -_dot(e1, e2) + _dot(e1, ell) * _dot(ell, e2) / m ** 2
                amp = amp - mu * mu * d / (_dot(ell, ell) - m * m)
            total += np.abs(amp) ** 2
    return _sigma(total / 9.0, w, s, p, k, identical)


def t_channel_to_fermions(s: float, m: float, m_f: float, m_med: float, y: float, majorana: bool,
                          colours: int = 1, points: int = NODES) -> float:
    """σ(χχ̄ → f f̄), or σ(χχ → f f̄) for Majorana χ, through a t-channel scalar: y φ* χ̄ P_R f + h.c."""
    if np.sqrt(s) <= max(2.0 * m, 2.0 * m_f) * (1.0 + 1e-12):
        return 0.0
    x, w = np.polynomial.legendre.leggauss(points)
    p1, p2, k1, k2, p, k = frame(s, m, m, m_f, m_f, x)
    t, u = _dot(p1 - k1, p1 - k1), _dot(p1 - k2, p1 - k2)
    total = np.zeros(len(x))
    for x1 in _BASIS:
        for x2 in _BASIS:
            u1, u2 = spinor_u(p1[:, 1:], m, x1), spinor_u(p2[:, 1:], m, x2)
            v1, v2 = bar(conjugate(u1)), bar(conjugate(u2))
            for y1 in _BASIS:
                ub = bar(spinor_u(k1[:, 1:], m_f, y1))
                for y2 in _BASIS:
                    vk = spinor_v(k2[:, 1:], m_f, y2)
                    amp = (np.einsum("ni,ij,nj->n", ub, P_L, u1) * np.einsum("ni,ij,nj->n", v2, P_R, vk)
                           / (t - m_med ** 2))
                    if majorana:
                        amp = amp - (np.einsum("ni,ij,nj->n", ub, P_L, u2) * np.einsum("ni,ij,nj->n", v1, P_R, vk)
                                     / (u - m_med ** 2))
                    total += np.abs(y * y * amp) ** 2
    return colours * _sigma(total / 4.0, w, s, p, k, identical=False)


# --- coannihilation of a scalar partner φ that carries f's gauge charge ----------------------------

def conjugate(u: np.ndarray) -> np.ndarray:
    """v(p, s) = C ū(p, s)ᵀ = iγ² u(p, s)*: the v-spinor of the same spin state as u (Dirac representation).

    A Majorana fermion that appears as u in one diagram and v in another must carry the same
    spin label in both, so its v-spinors are built from its u-spinors.
    """
    return np.einsum("ij,nj->ni", 1j * GAMMA[2], u.conj())


def _transverse(k: np.ndarray) -> list[np.ndarray]:
    return polarisations(k, 1.0)[:2]


def _colour_sum(a1: np.ndarray, a2: np.ndarray, coloured: bool) -> np.ndarray:
    if coloured:
        return 16.0 / 3.0 * (np.abs(a1) ** 2 + np.abs(a2) ** 2) - 4.0 / 3.0 * np.real(a1 * np.conj(a2))
    return np.abs(a1 + a2) ** 2


def gauge_pair_amplitudes(p1, p2, k1, k2, e1, e2, m_phi: float) -> tuple[np.ndarray, np.ndarray]:
    """The two colour-ordered parts (A₁ of T^bT^a, A₂ of T^aT^b) of φφ* → V_a V_b, coupling g = 1.

    The abelian amplitude is A₁ + A₂ (scalar QED). The s-channel three-gluon term enters
    A₁ and A₂ with opposite signs, as gauge invariance requires.
    """
    q = k1 + k2
    n_t = _dot(2 * p1 - k1, e1) * _dot(k2 - 2 * p2, e2)
    n_u = _dot(2 * p1 - k2, e2) * _dot(k1 - 2 * p2, e1)
    t, u, s = _dot(p1 - k1, p1 - k1), _dot(p1 - k2, p1 - k2), _dot(q, q)
    seagull = _dot(e1, e2)
    j = p1 - p2
    three = (_dot(j, e1) * _dot(-(q + k1), e2) + _dot(e1, e2) * _dot(k1 - k2, j)
             + _dot(j, e2) * _dot(k2 + q, e1)) / s
    a1 = -(n_t / (t - m_phi ** 2) - seagull + three)
    a2 = -(n_u / (u - m_phi ** 2) - seagull - three)
    return a1, a2


def partners_to_gauge_bosons(s: float, m_phi: float, g: float, coloured: bool, points: int = NODES) -> float:
    """σ(φφ* → VV): two gluons (φ a colour triplet, averaged over 9 colours) or two abelian bosons."""
    return sum(partners_to_gauge_bosons_by_colour(s, m_phi, g, coloured, points))


def partners_to_gauge_bosons_by_colour(s: float, m_phi: float, g: float, coloured: bool,
                                       points: int = NODES) -> tuple[float, float]:
    """σ(φφ* → VV) from the colour-singlet and the colour-octet φφ* states (abelian: all in the first).

    With M = T^bT^a A₁ + T^aT^b A₂, the singlet part is (2/3)|A₁ + A₂|² and the octet part
    (14/3)(|A₁|² + |A₂|²) − (8/3) Re A₁A₂* (they sum to the total; at threshold 2/7 and 5/7).
    """
    if np.sqrt(s) <= 2.0 * m_phi * (1.0 + 1e-12):
        return 0.0, 0.0
    x, w = np.polynomial.legendre.leggauss(points)
    p1, p2, k1, k2, p, k = frame(s, m_phi, m_phi, 0.0, 0.0, x)
    singlet, octet = np.zeros(len(x)), np.zeros(len(x))
    for e1 in _transverse(k1):
        for e2 in _transverse(k2):
            a1, a2 = gauge_pair_amplitudes(p1, p2, k1, k2, e1, e2, m_phi)
            if coloured:
                singlet += 2.0 / 3.0 * np.abs(a1 + a2) ** 2
                octet += 14.0 / 3.0 * (np.abs(a1) ** 2 + np.abs(a2) ** 2) - 8.0 / 3.0 * np.real(a1 * np.conj(a2))
            else:
                singlet += np.abs(a1 + a2) ** 2
    average = 9.0 if coloured else 1.0
    return (g ** 4 * _sigma(singlet / average, w, s, p, k, identical=True),
            g ** 4 * _sigma(octet / average, w, s, p, k, identical=True))


def partners_to_fermions(s: float, m_phi: float, m_f: float, g: float, charge_f: float | tuple[float, float],
                         coloured: bool, y: float = 0.0, m_chi: float = 0.0, colours_f: int = 1,
                         points: int = NODES) -> float:
    """σ(φφ* → f′f̄′): the s-channel gauge boson (coupling g, f′'s charge ``charge_f``), and for f′ = f
    (``y`` ≠ 0) t-channel χ exchange from y φ* χ̄ P_R f + h.c.

    For QCD the colour factors are 2 (s-channel), 9 (χ exchange) and 4 (their interference),
    averaged over 9; for an abelian group f′'s colours multiply. A chiral charge is a pair
    (left, right), e.g. φ's hypercharge times f′'s.
    """
    return sum(partners_to_fermions_by_colour(s, m_phi, m_f, g, charge_f, coloured, y, m_chi, colours_f, points))


def partners_to_fermions_by_colour(s: float, m_phi: float, m_f: float, g: float, charge_f, coloured: bool,
                                   y: float = 0.0, m_chi: float = 0.0, colours_f: int = 1,
                                   points: int = NODES) -> tuple[float, float]:
    """σ(φφ* → f′f̄′) from the colour-singlet and colour-octet φφ* states (abelian: all in the first).

    The gluon couples to the octet only; χ exchange (colour δ_ik δ_jl) puts |a_t|² in the
    singlet, so the singlet part is |a_t|² and the octet part 2|a_s|² + 8|a_t|² + 8 Re a_s a_t*,
    averaged over 9.
    """
    if np.sqrt(s) <= max(2.0 * m_phi, 2.0 * m_f) * (1.0 + 1e-12):
        return 0.0, 0.0
    c_l, c_r = (charge_f, charge_f) if np.isscalar(charge_f) else charge_f
    x, w = np.polynomial.legendre.leggauss(points)
    p1, p2, k1, k2, p, k = frame(s, m_phi, m_phi, m_f, m_f, x)
    j = p1 - p2
    ell = p1 - k1
    prop = (slash(ell) + m_chi * UNIT[None]) / (_dot(ell, ell) - m_chi ** 2)[:, None, None]
    chain_t = P_L[None] @ prop @ P_R[None]
    vertex_s = np.einsum("nm,mij->nij", j * METRIC, GAMMA) @ (c_l * P_L + c_r * P_R)[None] / s
    singlet, octet = np.zeros(len(x)), np.zeros(len(x))
    for y1 in _BASIS:
        ub = bar(spinor_u(k1[:, 1:], m_f, y1))
        for y2 in _BASIS:
            vk = spinor_v(k2[:, 1:], m_f, y2)
            a_s = g * g * np.einsum("ni,nij,nj->n", ub, vertex_s, vk)
            a_t = y * y * np.einsum("ni,nij,nj->n", ub, chain_t, vk)
            if coloured:
                singlet += np.abs(a_t) ** 2 / 9.0
                octet += (2.0 * np.abs(a_s) ** 2 + 8.0 * np.abs(a_t) ** 2 + 8.0 * np.real(a_s * np.conj(a_t))) / 9.0
            else:
                singlet += colours_f * np.abs(a_s + a_t) ** 2
    return _sigma(singlet, w, s, p, k, identical=False), _sigma(octet, w, s, p, k, identical=False)


def partners_to_same_fermions(s: float, m_phi: float, m_f: float, m_chi: float, y: float, coloured: bool,
                              points: int = NODES) -> float:
    """σ(φφ → f f) through Majorana χ in the t- and u-channel (the mass insertion m_χ)."""
    return sum(partners_to_same_fermions_by_colour(s, m_phi, m_f, m_chi, y, coloured, points))


def partners_to_same_fermions_by_colour(s: float, m_phi: float, m_f: float, m_chi: float, y: float, coloured: bool,
                                        points: int = NODES) -> tuple[float, float]:
    """σ(φφ → f f) from the colour-sextet and the colour-antitriplet φφ states (abelian: all in the first).

    With M = (a_t + a_u) S + (a_t − a_u) A (S, A the symmetric and antisymmetric colour
    projectors, traces 6 and 3), |M|² = 6|a_t + a_u|² + 3|a_t − a_u|².
    """
    if np.sqrt(s) <= max(2.0 * m_phi, 2.0 * m_f) * (1.0 + 1e-12):
        return 0.0, 0.0
    x, w = np.polynomial.legendre.leggauss(points)
    p1, p2, k1, k2, p, k = frame(s, m_phi, m_phi, m_f, m_f, x)
    t, u = _dot(p1 - k1, p1 - k1), _dot(p1 - k2, p1 - k2)
    sextet, antitriplet = np.zeros(len(x)), np.zeros(len(x))
    for y1 in _BASIS:
        uk1 = spinor_u(k1[:, 1:], m_f, y1)
        ub1, vk1 = bar(uk1), conjugate(uk1)
        for y2 in _BASIS:
            uk2 = spinor_u(k2[:, 1:], m_f, y2)
            ub2, vk2 = bar(uk2), conjugate(uk2)
            a_t = y * y * m_chi * np.einsum("ni,ij,nj->n", ub1, P_L, vk2) / (t - m_chi ** 2)
            a_u = -y * y * m_chi * np.einsum("ni,ij,nj->n", ub2, P_L, vk1) / (u - m_chi ** 2)
            if coloured:
                sextet += 6.0 * np.abs(a_t + a_u) ** 2
                antitriplet += 3.0 * np.abs(a_t - a_u) ** 2
            else:
                sextet += np.abs(a_t + a_u) ** 2
    average = 9.0 if coloured else 1.0
    return (_sigma(sextet / average, w, s, p, k, identical=True),
            _sigma(antitriplet / average, w, s, p, k, identical=True))


def dm_partner_amplitude(p1, p2, k1, k2, e2, m_chi: float, m_phi: float, m_f: float, xi, eta) -> np.ndarray:
    """The amplitude of χ(p₁) φ(p₂) → f(k₁) V(k₂) per unit couplings (y = g = charge = 1), ε of V given."""
    u1 = spinor_u(p1[:, 1:], m_chi, xi)
    ub = bar(spinor_u(k1[:, 1:], m_f, eta))
    q = p1 + p2
    s_prop = (slash(q) + m_f * UNIT[None]) / (_dot(q, q) - m_f ** 2)[:, None, None]
    a_s = np.einsum("ni,nij,nj->n", ub, slash(e2) @ s_prop @ P_L[None], u1)
    t_phi = _dot(p2 - k2, p2 - k2)
    a_t = np.einsum("ni,ij,nj->n", ub, P_L, u1) * _dot(2 * p2 - k2, e2) / (t_phi - m_phi ** 2)
    return a_s + a_t


def dm_partner_to_fermion_boson(s: float, m_chi: float, m_phi: float, m_f: float, y: float, g: float,
                                charge: float, coloured: bool, points: int = NODES) -> float:
    """σ(χφ → f V): s-channel f and t-channel φ (colour factor 4 over 3 colours; spin average ½)."""
    if np.sqrt(s) <= max(m_chi + m_phi, m_f) * (1.0 + 1e-12):
        return 0.0
    x, w = np.polynomial.legendre.leggauss(points)
    p1, p2, k1, k2, p, k = frame(s, m_chi, m_phi, m_f, 0.0, x)
    total = np.zeros(len(x))
    for xi in _BASIS:
        for eta in _BASIS:
            for e2 in _transverse(k2):
                total += np.abs(dm_partner_amplitude(p1, p2, k1, k2, e2, m_chi, m_phi, m_f, xi, eta)) ** 2
    colour = 4.0 / 3.0 if coloured else 1.0
    return (y * g * charge) ** 2 * colour * _sigma(total / 2.0, w, s, p, k, identical=False)


# --- vector portals -------------------------------------------------------------------------------

def fermion_to_vector_scalar(s: float, m: float, chi: tuple[float, float], m_v: float, m_s: float,
                             g_vvs: float, m_med: float, width: float, points: int = NODES) -> float:
    """σ(χχ̄ → V* → V S): an s-channel vector with couplings −V_μ χ̄γ^μ(a + bγ⁵)χ, and V*VS vertex g_vvs g^μν.

    With the full massive propagator (−g + qq/M²), so an axial coupling's longitudinal part is kept
    (for the Z boson, χχ̄ → Zh).
    """
    if np.sqrt(s) <= max(2.0 * m, m_v + m_s) * (1.0 + 1e-12):
        return 0.0
    x, w = np.polynomial.legendre.leggauss(points)
    p1, p2, k1, k2, p, k = frame(s, m, m, m_v, m_s, x)
    q = p1 + p2
    gamma_mu = np.einsum("mij->mij", GAMMA)
    vertex = gamma_mu @ (chi[0] * UNIT + chi[1] * GAMMA5)
    prop = 1.0 / (s - m_med ** 2 + 1j * m_med * width)
    total = np.zeros(len(x))
    for x1 in _BASIS:
        u1 = spinor_u(p1[:, 1:], m, x1)
        for x2 in _BASIS:
            v2 = bar(spinor_v(p2[:, 1:], m, x2))
            current = np.einsum("ni,mij,nj->nm", v2, vertex, u1)          # J^μ, shape (n, 4)
            for eps in polarisations(k1, m_v):
                amp = (-_dot(current, eps) + _dot(current, q) * _dot(q, eps) / m_med ** 2) * prop * g_vvs
                total += np.abs(amp) ** 2
    return _sigma(total / 4.0, w, s, p, k, identical=False)


def scalars_to_massive_vectors(s: float, m: float, m_v: float, g: float, points: int = NODES) -> float:
    """σ(φφ* → V V) for a complex scalar with an abelian gauge coupling g to a massive V (all polarisations)."""
    if np.sqrt(s) <= max(2.0 * m, 2.0 * m_v) * (1.0 + 1e-12):
        return 0.0
    x, w = np.polynomial.legendre.leggauss(points)
    p1, p2, k1, k2, p, k = frame(s, m, m, m_v, m_v, x)
    total = np.zeros(len(x))
    for e1 in polarisations(k1, m_v):
        for e2 in polarisations(k2, m_v):
            a1, a2 = gauge_pair_amplitudes(p1, p2, k1, k2, e1, e2, m)
            total += np.abs(a1 + a2) ** 2
    return g ** 4 * _sigma(total, w, s, p, k, identical=True)
