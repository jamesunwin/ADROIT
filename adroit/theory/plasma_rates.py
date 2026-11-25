"""Leading-order plasma conversion rates for the eR Majorana family (M27; the owner's request of 2026-10-19: build the
plasma rates, validate them against their limits, leading order only). They decide the certificate's physical
prerequisite when a request asks for them (``ConversionRequest.plasma``); the component certificate is unchanged.

**What changes from the vacuum Born rates** (``source_born``), all at leading order in the couplings:
- **thermal masses on every light or charged leg** (one loop, hard modes, unbroken phase, Q = T₃ + Y): the electron's
  asymptotic mass m_e = g′|Y|T/2 on the external and the exchanged e_R; the B's transverse asymptotic mass
  m_B² = m_D²/2 with m_D² = (11/6) g′²T² (the Standard Model's hypercharges), which also regulates the soft B that the
  vacuum calculation cut by hand; the partner's M_T² = M² + g′²Y²T²/4 (its Yukawa term, y²T², is negligible for
  |y| ≤ 10⁻³); χ, a gauge singlet, none. With these masses B → e ē is closed (m_B ≈ 0.96 g′T < 2m_e = g′T), so the
  exchanged electron is never on shell;
- **quantum statistics for the light particles**: incoming B (Bose–Einstein) and ē (Fermi–Dirac), outgoing e with
  Pauli blocking and outgoing B with Bose enhancement, in the plasma frame, with χ and φ (m ≫ T) Maxwell–Boltzmann;
- **decays** φ → χ e at the thermal masses, with Pauli blocking, and the inverse decays by detailed balance.

**What it is not:** not a matched calculation beyond leading order, and not HTL-resummed: the exchanged electron
carries the asymptotic mass, which fixes the coefficient of the collinear logarithm ln(1/g′) exactly and leaves the
constant under it uncertain at O(1). That uncertainty is the bank's thermal masses scaled by ½ and 2.

**Validation (limits only):** the vacuum, Maxwell–Boltzmann limit reproduces ``source_born``; the collinear
logarithm's coefficient equals collinear factorisation (the Weyl splitting B → e_R ē times the narrow inverse decay
χ ē → φ); the quantum factors tend to 1 where the light energies are large; the inverse decays computed directly equal
the decays times the equilibrium ratio.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from scipy.special import kve

from adroit.constraints import processes as pr
from adroit.constraints.amplitudes import _BASIS, bar, spinor_u, spinor_v, slash
from adroit.theory.conversion_amplitudes import decay_width

DEBYE_B = 11.0 / 6.0               # m_D²/(g′²T²) for U(1)_Y with the Standard Model's content
SCALES = (0.5, 1.0, 2.0)           # the thermal masses varied: the O(1) constant under the leading logarithm


def thermal_masses(T: float, g_prime: float, M: float, scale: float = 1.0) -> tuple[float, float, float]:
    """(m_e, m_B, M_T) in GeV: the e_R's and the B's asymptotic masses and the partner's, the thermal parts scaled
    by ``scale``."""
    gt = scale * g_prime * T
    return gt / 2.0, gt * math.sqrt(DEBYE_B / 2.0), math.sqrt(M * M + gt * gt / 4.0)


def _momentum(s: float, a: float, b: float) -> float:
    return math.sqrt(max((s - (a + b) ** 2) * (s - (a - b) ** 2), 0.0)) / (2.0 * math.sqrt(s))


@lru_cache(maxsize=16)
def _gauss(n: int) -> tuple[np.ndarray, np.ndarray]:
    x, w = np.polynomial.legendre.leggauss(n)
    return x, w


def squared(s: float, m: float, M: float, mf: float, mb: float, channel: str, n: int = 48):
    """(cos θ*, angular weights, spin-averaged |M|² at unit couplings, p_in, p_out) at the nodes of a logarithmic
    angular coordinate that resolves the exchanged electron's pole, for χ B → φ e (``chi_B``) or χ ē → φ B
    (``chi_ebar``), with a B of mass ``mb`` (its two transverse polarisations) and the partner's mass ``M`` in the
    propagators too. ``mb = 0`` is ``source_born``'s vacuum kinematics."""
    root = math.sqrt(s)
    light_in, heavy_out, light_out = (mb, M, mf) if channel == "chi_B" else (mf, M, mb)
    pin, pout = _momentum(s, m, light_in), _momentum(s, heavy_out, light_out)
    e_in = (s + light_in ** 2 - m * m) / (2 * root)
    e_out = (s + light_out ** 2 - heavy_out ** 2) / (2 * root)
    # E_f E_b − p_in p_out, in a form free of cancellation (f the electron, b the B)
    e_f, e_b, p_f, p_b = (e_out, e_in, pout, pin) if channel == "chi_B" else (e_in, e_out, pin, pout)
    x = (p_f ** 2 * mb ** 2 + mf ** 2 * p_b ** 2 + mf ** 2 * mb ** 2) / (e_f * e_b + p_f * p_b)
    delta = (2 * x - mb * mb) / (2 * pin * pout)
    if not delta > 0:
        raise ArithmeticError("the exchanged electron would be on shell (B → e ē open)")
    nodes, weights = _gauss(n)
    high = math.log1p(2 / delta)
    z = (nodes + 1) * high / 2
    r = delta * np.expm1(z)
    jac = delta * np.exp(z) * weights * high / 2
    fd = mb * mb - 2 * (x + pin * pout * r)
    if channel == "chi_B":
        p, b, phi, f, _, _ = pr.frame(s, m, mb, M, mf, 1 - r)
        phi[:, 1] = pout * np.sqrt(r * (2 - r))
        f[:, 1] = -phi[:, 1]
        signed_phi, signed_B, q = -phi, -b, f - b
        sd = mb * mb - 2 * (phi[:, 0] * b[:, 0] + pout * pin * (1 - r))
        fermion = spinor_u
    else:
        p, f, phi, b, _, _ = pr.frame(s, m, mf, M, mb, 1 - r)
        phi[:, 1] = pout * np.sqrt(r * (2 - r))
        b[:, 1] = -phi[:, 1]
        signed_phi, signed_B, q = -phi, b, b - f
        sd = np.full(n, s - M * M)
        fermion = spinor_v
    total = np.zeros(n)
    for eps in pr._transverse(b):
        scalar = pr._dot(2 * signed_phi - signed_B, eps) / sd
        chain = slash(eps) @ (slash(q) + mf * pr.UNIT[None]) @ pr.P_L / fd[:, None, None] + scalar[:, None, None] * pr.P_L[None]
        for xi in _BASIS:
            u = spinor_u(p[:, 1:], m, xi)
            for eta in _BASIS:
                total += abs(np.einsum("ni,nij,nj->n", bar(fermion(f[:, 1:], mf, eta)), chain, u)) ** 2
    return 1 - r, jac, total / 4, pin, pout


def cross_section(s: float, m: float, M: float, mf: float, mb: float, channel: str, n: int = 48) -> float:
    """The unit-coupling cross section (``squared`` integrated over angles)."""
    light_in, light_out = (mb, mf) if channel == "chi_B" else (mf, mb)
    if math.sqrt(s) <= max(m + light_in, M + light_out):
        return 0.0
    _, jac, msq, pin, pout = squared(s, m, M, mf, mb, channel, n)
    return (pout / pin) * float(np.sum(jac * msq)) / (32 * math.pi * s)


@lru_cache(maxsize=16)
def _laguerre(n: int) -> tuple[np.ndarray, np.ndarray]:
    """Nodes and weights for ∫₀^∞ du √u e^{−u} F(u): a heavy particle's momentum, p ∝ √u near rest."""
    from scipy.special import roots_genlaguerre
    x, w = roots_genlaguerre(n, 0.5)
    return x, w


def _occupation(energy: np.ndarray, T: float, kind: str) -> np.ndarray:
    """f(E) of a light particle: ``boson``, ``fermion`` or ``mb`` (Maxwell–Boltzmann)."""
    e = energy / T
    if kind == "mb":
        return np.exp(-e)
    return 1.0 / np.expm1(e) if kind == "boson" else 1.0 / (np.exp(e) + 1.0)


@lru_cache(maxsize=64)
def _table(m: float, M: float, mf: float, mb: float, channel: str, threshold: float, T: float, n: int):
    """|M|² (unit couplings) at ``n`` angular nodes on a logarithmic grid of √s above ``threshold``, for
    interpolation in log(√s − threshold) node by node."""
    w = np.geomspace(1e-7 * T, 80.0 * T, 320)
    rows = [squared((threshold + v) ** 2, m, M, mf, mb, channel, n) for v in w]
    cos = np.array([row[0] for row in rows])
    jac = np.array([row[1] for row in rows])
    msq = np.array([row[2] for row in rows])
    pout = np.array([row[4] for row in rows])
    return np.log(w), cos, jac, msq, pout


def _k_min(p: np.ndarray, e_p: np.ndarray, cos_a: np.ndarray, m: float, ma: float, s_min: float) -> np.ndarray:
    """The light particle's smallest momentum (at the relative angle) giving s ≥ s_min."""
    c = (s_min - m * m - ma * ma) / 2.0
    a = e_p * e_p - (p * cos_a) ** 2
    disc = np.clip(c * c - ma * ma * a, 0.0, None)
    return np.clip((c * p * cos_a + e_p * np.sqrt(disc)) / a, 0.0, None)


def scattering_rate(m: float, M: float, y: float, g: float, T: float, channel: str, masses: tuple[float, float, float],
                    statistics: bool | str = True, cut: float = 0.0, nodes: tuple[int, int, int, int] = (16, 16, 40, 12),
                    angles: int = 48) -> float:
    """The up-rate per χ (GeV) of χ B → φ e or χ ē → φ B, both charge conjugates, in the plasma frame: χ
    Maxwell–Boltzmann, the incoming light particle Bose–Einstein or Fermi–Dirac and the outgoing one enhanced or
    blocked (``statistics``; ``"incoming"``: only the incoming occupation, for the limit checks; else all
    Maxwell–Boltzmann and unblocked), at the masses (m_e, m_B, M_T) given; ``cut``
    raises the threshold √s ≥ M_T + max(cut, the outgoing light mass), the vacuum calculation's soft cut. The table
    and the light particle's momenta start at the higher of the incoming and outgoing thresholds: with a small
    splitting and a heavy thermal mass on the incoming leg, m_χ + m_in exceeds M_T + m_out, and nodes between the two
    had no incoming momentum (the audit's PX-07: NaN rates at m_χ = 8 TeV, M = 8.08 TeV, T = 800 GeV)."""
    me, mb, MT = masses
    ma, mout = (mb, me) if channel == "chi_B" else (me, mb)
    incoming = "mb" if not statistics else ("boson" if channel == "chi_B" else "fermion")
    outgoing = None if statistics in (False, "incoming") else ("fermion" if channel == "chi_B" else "boson")
    threshold = max(MT + max(cut, mout), m + ma)
    log_w, cos_t, jac_t, msq_t, pout_t = _table(m, MT, me, mb, channel, threshold, T, angles)
    nu, na, nk, nphi = nodes
    u, wu = _laguerre(nu)
    ca, wa = _gauss(na)
    # k − k_min on a logarithmic Gauss–Legendre grid from 10⁻⁶ T to 60 T: resolves a cross section that grows as
    # 1/(√s − threshold) (the vacuum's soft B) as well as the plasma's smooth threshold
    gl, gw = _gauss(nk)
    low, high = math.log(1e-6 * T), math.log(60.0 * T)
    dk = np.exp(low + (gl + 1) * (high - low) / 2)
    wk = gw * (high - low) / 2 * dk
    e_p = m + T * u[:, None, None]
    p = np.sqrt(e_p * e_p - m * m)
    cos_a = ca[None, :, None]
    k = _k_min(p, e_p, cos_a, m, ma, threshold ** 2) + dk[None, None, :]
    e_k = np.sqrt(k * k + ma * ma)
    s = m * m + ma * ma + 2 * (e_p * e_k - p * k * cos_a)
    root = np.sqrt(s)
    weight = (wu[:, None, None] * np.sqrt(T * (2 * m + T * u[:, None, None])) * e_p / (m * m * kve(2, m / T))) \
        * wa[None, :, None] \
        * wk[None, None, :] * k * k * _occupation(e_k, T, incoming) / (4 * math.pi ** 2) \
        / (4 * e_p * e_k)
    # |M|² and its angular nodes at each √s, interpolated node by node in log(√s − threshold)
    lw = np.log(np.clip(root - threshold, math.exp(log_w[0]), math.exp(log_w[-1])))
    flat = lw.ravel()
    msq = np.stack([np.interp(flat, log_w, msq_t[:, j]) for j in range(angles)], axis=1)
    jac = np.stack([np.interp(flat, log_w, jac_t[:, j]) for j in range(angles)], axis=1)
    cos = np.stack([np.interp(flat, log_w, cos_t[:, j]) for j in range(angles)], axis=1)
    pout = np.array([_momentum(v, MT, mout) for v in s.ravel()])
    factor = np.ones_like(msq)
    if outgoing is not None:
        factor = _final_factor(p, e_p, k, e_k, cos_a, s, cos, MT, mout, T, outgoing, nphi).reshape(msq.shape)
    angular = (jac * msq * factor).sum(1) * 2 * math.pi
    phase = pout / (16 * math.pi ** 2 * root.ravel()) * angular
    return 2.0 * 2.0 * y * y * g * g * float(np.sum(weight.ravel() * phase))


def _final_factor(p, e_p, k, e_k, cos_a, s, cos, MT, mout, T, kind, nphi) -> np.ndarray:
    """1 − f_F or 1 + f_B of the outgoing light particle at its plasma-frame energy, averaged over its CM azimuth."""
    shape = np.broadcast_shapes(p.shape, k.shape, cos_a.shape)
    p, e_p, k, e_k, cos_a = (np.broadcast_to(a, shape).ravel() for a in (p, e_p, k, e_k, cos_a))
    sin_a = np.sqrt(np.clip(1 - cos_a ** 2, 0, None))
    total = np.stack([k * sin_a, np.zeros_like(k), p + k * cos_a], axis=1)       # χ along z, k in the x–z plane
    energy = e_p + e_k
    beta = total / energy[:, None]
    b = np.linalg.norm(beta, axis=1)
    gamma = 1 / np.sqrt(1 - b * b)
    unit = np.divide(beta, b[:, None], out=np.zeros_like(beta), where=b[:, None] > 0)
    chi = np.stack([np.zeros_like(p), np.zeros_like(p), p], axis=1)
    along = (chi * unit).sum(1)
    chi_star = chi + ((gamma - 1) * along - gamma * e_p * b)[:, None] * unit         # χ's momentum in the CM frame
    cos_psi = (chi_star * unit).sum(1) / np.maximum(np.linalg.norm(chi_star, axis=1), 1e-300)
    sin_psi = np.sqrt(np.clip(1 - cos_psi ** 2, 0, None))
    root = np.sqrt(s.ravel())
    q = np.array([_momentum(v, MT, mout) for v in s.ravel()])
    e_star = (s.ravel() + mout * mout - MT * MT) / (2 * root)
    cos_b = -cos                                                    # the outgoing light particle opposite φ
    sin_b = np.sqrt(np.clip(1 - cos_b ** 2, 0, None))
    phis = (np.arange(nphi) + 0.5) * 2 * math.pi / nphi
    out = np.zeros_like(cos)
    for ph in phis:
        e_lab = gamma[:, None] * (e_star[:, None] + b[:, None] * q[:, None]
                                  * (cos_psi[:, None] * cos_b + sin_psi[:, None] * sin_b * math.cos(ph)))
        f = _occupation(e_lab, T, kind)
        out += (1 - f) if kind == "fermion" else (1 + f)
    return out / nphi


def decay_rate(m: float, M: float, y: float, T: float, masses: tuple[float, float, float], statistics: bool = True,
               nodes: tuple[int, int] = (24, 24)) -> float:
    """φ → χ e per φ (both charge states' partner), thermally averaged in the plasma frame: the rest-frame width at the
    thermal masses, its time dilation, and Pauli blocking of the electron at its plasma-frame energy (``statistics``);
    without blocking it is Γ K₁(M_T/T)/K₂(M_T/T)."""
    me, _, MT = masses
    width = decay_width(m, MT, me, y)
    if width == 0.0:
        return 0.0
    u, wu = _laguerre(nodes[0])
    c, wc = _gauss(nodes[1])
    e_phi = MT + T * u[:, None]
    p_phi = np.sqrt(T * u[:, None] * (2 * MT + T * u[:, None]))
    # the φ's normalised Maxwell–Boltzmann momentum weight (√u absorbed by the nodes), and its time dilation
    weight = wu[:, None] * np.sqrt(T * (2 * MT + T * u[:, None])) * e_phi / (MT * MT * kve(2, MT / T)) * (MT / e_phi)
    if not statistics:
        return width * float(np.sum(weight * wc[None, :] / 2))
    q = _momentum(MT * MT, m, me)
    e_star = (MT * MT + me * me - m * m) / (2 * MT)
    e_lab = (e_phi * e_star + p_phi * q * c[None, :]) / MT
    return width * float(np.sum(weight * wc[None, :] / 2 * (1 - _occupation(e_lab, T, "fermion"))))


def inverse_decay_rate(m: float, M: float, y: float, T: float, masses: tuple[float, float, float],
                       nodes: int = 32) -> float:
    """χ e → φ and χ ē → φ* per χ, computed directly (χ Maxwell–Boltzmann, e Fermi–Dirac): with Σ|M|² = 8π M_T² Γ/q
    the δ-function fixes the relative angle, leaving the electron energies between
    E± = [c E_χ ± p_χ √(c² − m² m_e²)]/m², c = (M_T² − m² − m_e²)/2, and ∫ f_FD dE analytic:
    Γ_up = 2 ∫ d³p f̂(p) M_T² Γ/(4 q E_χ p_χ) · T ln[(1 + e^{−E₋/T})/(1 + e^{−E₊/T})].
    In equilibrium f_χ f_e = f_φ (1 − f_e), so it equals ``decay_rate`` × n_φ/n_χ: detailed balance, the check."""
    me, _, MT = masses
    width = decay_width(m, MT, me, y)
    if width == 0.0:
        return 0.0
    q = _momentum(MT * MT, m, me)
    c = (MT * MT - m * m - me * me) / 2
    u, wu = _laguerre(nodes)
    e_p = m + T * u
    p = np.sqrt(T * u * (2 * m + T * u))
    weight = wu * np.sqrt(T * (2 * m + T * u)) * e_p / (m * m * kve(2, m / T))
    root = p * math.sqrt(max(c * c - m * m * me * me, 0.0))
    low, high = (c * e_p - root) / (m * m), (c * e_p + root) / (m * m)
    occupied = T * (np.log1p(np.exp(-low / T)) - np.log1p(np.exp(-high / T)))
    return 2.0 * float(np.sum(weight * MT * MT * width / (4 * q * e_p * p) * occupied))


def equilibrium_ratio(m: float, MT: float, T: float) -> float:
    """n_φ,total/n_χ in equilibrium (g_φ + g_φ* = g_χ = 2), Maxwell–Boltzmann."""
    return (MT / m) ** 2 * float(kve(2, MT / T) / kve(2, m / T)) * math.exp(-(MT - m) / T)


CHANNELS = ("chi_B", "chi_ebar")
THRESHOLD = 100.0                  # the equilibrium criterion Γ/H, as the component certificate's
BOUNDARY_TOLERANCE = 0.01


def rate_point(inputs, x: float):
    """The relaxation rate over H at x for each scale of the thermal masses: the blocked decays × (1 + n_φ/n_χ), the
    scatterings × (1 + n_χ/n_φ), and the odd sector's χχ ↔ φφ† (vacuum Born, y⁴; ``conversion_rates._odd``)."""
    from adroit.constraints.relic import M_PLANCK_GEV, degrees_of_freedom
    from adroit.core.chemical_equilibrium import PlasmaRatePoint
    from adroit.theory.conversion_rates import _odd
    p = inputs.point
    m, M, y, g = p.m_chi, p.m_med, p.g_chi, inputs.g_prime
    T = m / x
    hubble = math.sqrt(4 * math.pi ** 3 * degrees_of_freedom(T)[0] / 45) * T * T / M_PLANCK_GEV
    odd = _odd(inputs, x)[1] if inputs.request.include_odd_sector else 0.0
    rates = {}
    for scale in SCALES:
        masses = thermal_masses(T, g, M, scale)
        ratio = equilibrium_ratio(m, masses[2], T)
        down = decay_rate(m, M, y, T, masses)
        scatter = sum(scattering_rate(m, M, y, g, T, channel, masses) for channel in CHANNELS)
        rate = (down * (1 + ratio) + scatter * (1 + 1 / ratio) + (odd or 0.0)) / hubble
        if not (math.isfinite(rate) and rate >= 0):
            raise ArithmeticError(f"the plasma rate at x = {x:.4g}, thermal-mass scale {scale:g}, is {rate!r}")
        rates[str(scale)] = rate
    return PlasmaRatePoint(x=x, temperature_gev=T, hubble_gev=hubble, rates_over_h=rates,
                           odd_sector_relaxation_gev=odd)


def assess(c) -> None:
    """The physical prerequisite at leading order in the plasma: supported if the declared uncertainty's lower edge of
    the lowest scale passes the criterion at every sampled temperature, failed if even the upper edge of the highest
    scale fails at one, else unresolved."""
    r = c.inputs.request
    c.algorithm_version = 5                         # the attempt, recorded whether or not it completes (PX-08)
    try:
        rows = [rate_point(c.inputs, float(x)) for x in np.linspace(r.x_low, r.x_high, r.samples)]
        incomplete = [row.x for row in rows if set(row.rates_over_h) != {str(scale) for scale in SCALES}
                      or not all(math.isfinite(v) and v >= 0 for v in row.rates_over_h.values())]
        if len(rows) != r.samples or incomplete:
            raise ArithmeticError(f"the bank is incomplete (temperatures x = {incomplete})")
    except (ArithmeticError, ValueError) as error:
        c.physical_prerequisite = "unresolved"
        c.reasons = [*c.reasons, f"leading-order plasma rates unresolved: {error}"]
        return
    c.plasma_rates = rows
    low = min((1 - r.rate_relative_uncertainty) * min(row.rates_over_h.values()) for row in rows)
    high = min((1 + r.rate_relative_uncertainty) * max(row.rates_over_h.values()) for row in rows)
    if low > THRESHOLD * (1 + BOUNDARY_TOLERANCE):
        c.physical_prerequisite = "supported"
        word = "supported"
    elif high < THRESHOLD * (1 - BOUNDARY_TOLERANCE):
        c.physical_prerequisite = "failed"
        word = "fails"
    else:
        c.physical_prerequisite = "unresolved"
        word = "is unresolved"
    c.reasons = [*c.reasons, f"chemical equilibrium {word} at leading order in the plasma (thermal masses on every light "
                 "or charged leg, quantum statistics; the thermal masses scaled by ½ and 2 for the constant under the "
                 "leading logarithm; not a matched or HTL-resummed calculation)"]
