"""Non-perturbative effects of long-range forces on annihilation: the Sommerfeld effect and bound states.

**The Coulomb Sommerfeld factor.** Two particles of velocity β each in their centre of
momentum (relative velocity 2β), interacting through V(r) = −α_eff/r, annihilate with
σ → S σ_0, S = X/(1 − e^{−X}), X = πα_eff/β (Sommerfeld; Hisano et al. hep-ph/0412403;
for coloured pairs e.g. de Simone, Giudice & Strumia arXiv:1402.6287). Attractive α_eff > 0
gives S > 1, repulsive α_eff < 0 gives S < 1.

**Colour.** For a pair in the representation R of SU(3), made of r₁ and r₂,
α_eff = α_s [C₂(r₁) + C₂(r₂) − C₂(R)]/2: for a colour triplet and its antiparticle the
singlet has +4/3 α_s and the octet −1/6 α_s; for two triplets the antitriplet has +2/3 α_s
and the sextet −1/3 α_s.

**Bound states of a scalar colour triplet X and its antiparticle** (Harz & Petraki,
arXiv:1805.01200, eqs. (2.42), (3.13)–(3.24); Garny & Heisig, arXiv:2112.01499, eqs.
(11)–(16)). An octet pair captures into the colour-singlet ground state by emitting a
gluon, (X X†)₈ → B(1S)₁ + g:

    σ_BSF v_rel = (2⁷·17²/3⁵) π α_s^BSF α_s^B / m² × S_BSF(ζ_S, ζ_B),
    S_BSF = [2πζ_S/(1 − e^{−2πζ_S})] (1 + ζ_S²) ζ_B⁴ e^{−4ζ_S arccot ζ_B} / (1 + ζ_B²)³,

with ζ_S = −α_s^S/(6 v_rel) (the octet's repulsion) and ζ_B = (4/3) α_s^B / v_rel, averaged
over the 9 colour states of the pair. The bound state, of binding energy E_B = (4/9) m (α_s^B)²,
decays into gluons at Γ_dec = (32/81) m (α_s^ann)² (α_s^B)³, and the bath's gluons ionise it
at Γ_ion = (g_X²/g_B)(mT/4π)^{3/2} e^{−E_B/T} ⟨σ_BSF v⟩ (detailed balance; g_X = 3, g_B = 1).
In ionisation equilibrium the pair annihilates through the bound state at

    ⟨σ_BSF v⟩_eff = ⟨σ_BSF v⟩ Γ_dec / (Γ_dec + Γ_ion),

where ⟨σ_BSF v⟩ is the Maxwell–Boltzmann average of the relative velocity with the gluon's
Bose enhancement 1 + f_g(ω), ω = E_B + μv²/2. Scales of α_s (Harz & Petraki, Table 2):
m for the decay, the Bohr momentum μ (4/3) α_s^B for the bound state (solved
self-consistently), μ v_rel for the scattering state (not below the Bohr momentum), and ω for
the emission. Excited states (≈ +20% on this rate, Garny & Heisig eq. (75)) and thermal masses
are not included.
"""

from __future__ import annotations

import numpy as np

C_F, C_A = 4.0 / 3.0, 3.0
COLOUR = {"singlet": C_F, "octet": C_F - C_A / 2.0, "antitriplet": 2.0 / 3.0, "sextet": -1.0 / 3.0}


def coulomb(alpha_eff: float, beta: np.ndarray) -> np.ndarray:
    """S(β) = X/(1 − e^{−X}), X = πα_eff/β; 1 at α_eff = 0. Attractive (X > 0): X/(−expm1(−X)), which tends to X
    and never overflows; repulsive (X < 0): X e^X/expm1(X), the same function, which tends to |X| e^{−|X|} without
    overflow. X itself is not clipped (the independent audit, NA15-10, 2026-11-16: it had been clipped at ±700,
    so S stopped at 700: 3141.6 at α = 0.1, β = 10⁻⁴)."""
    beta = np.maximum(np.asarray(beta, dtype=float), 1e-12)
    x = np.pi * alpha_eff / beta
    with np.errstate(invalid="ignore", divide="ignore", over="ignore", under="ignore"):
        attractive = x / -np.expm1(-x)
        repulsive = x * np.exp(x) / np.expm1(x)
        out = np.where(np.abs(x) < 1e-8, 1.0 + 0.5 * x, np.where(x > 0, attractive, repulsive))
    return out


def colour_factor(channel: str, alpha_s: float, beta: np.ndarray) -> np.ndarray:
    """The Sommerfeld factor of a coloured pair's channel (``COLOUR``) at the potential's α_s."""
    return coulomb(COLOUR[channel] * alpha_s, beta)


def beta_of(s: float, m: float) -> float:
    """The velocity of each of two particles of mass m in their centre of momentum."""
    return float(np.sqrt(max(1.0 - 4.0 * m * m / s, 0.0)))


# --- bound states of a coloured pair ---------------------------------------------------------------------

G_TRIPLET, G_BOUND = 3.0, 1.0


def _alpha_s(q: float) -> float:
    from adroit.constraints.higgs import alpha_s
    return alpha_s(q)


def alpha_bohr(m: float) -> float:
    """α_s^B of the colour-singlet ground state of a pair of mass m each: α = α_s(½m · (4/3)α)."""
    alpha = _alpha_s(m)
    for _ in range(60):
        alpha = _alpha_s(0.5 * m * C_F * alpha)
    return alpha


def binding_energy(m: float) -> float:
    """E_B = μ(C_F α_s^B)²/2 = (4/9) m (α_s^B)² (GeV)."""
    return 0.5 * (0.5 * m) * (C_F * alpha_bohr(m)) ** 2


def bsf_sigma_v(v_rel: np.ndarray, m: float) -> np.ndarray:
    """σ_BSF v_rel (GeV⁻²) of a scalar triplet pair into the 1S singlet and a gluon (module docstring)."""
    v = np.maximum(np.asarray(v_rel, dtype=float), 1e-9)
    mu, a_b = 0.5 * m, alpha_bohr(m)
    bohr = mu * C_F * a_b
    a_s = np.array([_alpha_s(max(mu * x, bohr)) for x in v])
    a_bsf = np.array([_alpha_s(0.5 * mu * ((C_F * a_b) ** 2 + x * x)) for x in v])
    zeta_s, zeta_b = -a_s / (6.0 * v), C_F * a_b / v
    shape = capture_shape(zeta_s, zeta_b)
    return 2.0 ** 7 * 17.0 ** 2 / 3.0 ** 5 * np.pi * a_bsf * a_b / m ** 2 * shape


def capture_shape(zeta_s: np.ndarray, zeta_b: np.ndarray) -> np.ndarray:
    """S_BSF(ζ_S, ζ_B) of capture into a ground state (Harz & Petraki eq. (2.42b)); ζ_S < 0 is repulsive."""
    with np.errstate(over="ignore"):
        s0 = 2.0 * np.pi * zeta_s / -np.expm1(-2.0 * np.pi * zeta_s)
    return s0 * (1.0 + zeta_s ** 2) * zeta_b ** 4 * np.exp(-4.0 * zeta_s * np.arctan(1.0 / zeta_b)) / (1.0 + zeta_b ** 2) ** 3


def ionisation_equilibrium(sigma_v, m: float, e_b: float, gamma_dec: float, ion_g: float,
                           temperature: np.ndarray, active=None) -> np.ndarray:
    """⟨σ_BSF v⟩ Γ_dec/(Γ_dec + Γ_ion)(T) for a pair of mass m each, μ = m/2.

    ``sigma_v(v_rel)`` is the capture rate; the Maxwell–Boltzmann average includes the emitted
    boson's Bose enhancement 1 + f(ω), ω = E_B + μv²/2; Γ_ion = ion_g (mT/4π)^{3/2} e^{−E_B/T} ⟨σ_BSF v⟩
    (detailed balance); ``active(T)`` switches the bound state off where it does not exist.
    """
    temperature = np.atleast_1d(np.asarray(temperature, dtype=float))
    mu = 0.5 * m
    y = np.geomspace(1e-5, 60.0, 160)                 # μv²/2T
    weight = 2.0 / np.sqrt(np.pi) * np.sqrt(y) * np.exp(-y)
    out = np.zeros_like(temperature)
    for k, t in enumerate(temperature):
        if active is not None and not active(t):
            continue
        v = np.minimum(np.sqrt(2.0 * t * y / mu), 1.0)
        bose = 1.0 + 1.0 / np.expm1((e_b + t * y) / t)
        average = np.trapezoid(weight * bose * sigma_v(v), y)
        gamma_ion = ion_g * (m * t / (4.0 * np.pi)) ** 1.5 * np.exp(-e_b / t) * average
        out[k] = average * gamma_dec / (gamma_dec + gamma_ion)
    return out


def bound_state_rate(m: float, temperature: np.ndarray) -> np.ndarray:
    """⟨σ_BSF v⟩_eff(T) in GeV⁻² of a coloured pair: capture into the ground state, in ionisation equilibrium."""
    a_b = alpha_bohr(m)
    gamma_dec = 32.0 / 81.0 * m * _alpha_s(m) ** 2 * a_b ** 3
    return ionisation_equilibrium(lambda v: bsf_sigma_v(v, m), m, binding_energy(m), gamma_dec,
                                  G_TRIPLET ** 2 / G_BOUND, temperature)


# --- the multi-state Sommerfeld effect (electroweak multiplets) --------------------------------------

THRESHOLD_ROUNDING = 1e-12            # relative distance from a threshold that is rounding, not physics
GROWTH = 25.0                         # κ r beyond which the regular solutions are re-orthonormalised on the way out
GROWTH_STEP = 4.0                     # κ Δr of one stretch between re-orthonormalisations


def _threshold_wave(alpha_mu: float, r: float) -> tuple[complex, complex]:
    """Outgoing (attractive), decaying (repulsive), or constant free wave at zero energy.

    u″ + 2μα u/r = 0 gives √r H₁⁽¹⁾(√(8μαr)) for an attractive Coulomb
    tail, and √r K₁(√(8μ|α|r)) for a repulsive one. Its scale is arbitrary.
    """
    from scipy.special import h1vp, hankel1, kve
    if alpha_mu == 0:
        return 1.0, 0.0
    z = np.sqrt(8.0 * abs(alpha_mu) * r)
    if alpha_mu < 0:
        slope = 1.0 / (2.0 * r) - z * (kve(0, z) + kve(2, z)) / (4.0 * r * kve(1, z))
        return 1.0, complex(slope)
    h = np.sqrt(r) * hankel1(1, z)
    dh = h / (2.0 * r) + np.sqrt(r) * h1vp(1, z) * z / (2.0 * r)
    scale = max(abs(h), abs(dh))
    return complex(h / scale), complex(dh / scale)


def _asymptotic(eta: float, k: float, r: float, open_: bool,
                alpha_mu: float = 0.0) -> tuple[complex, complex, complex, complex]:
    """(F, F′, H, H′) at r of an s-wave in a channel with a Coulomb tail (η = −μα/k; η = 0 without one).

    Open: F the regular Coulomb wave over k (sin(kr)/k free) and H = (G + iF)/k outgoing.
    Closed (k = κ): F unused, H the decaying Whittaker function.
    At threshold F is unused and H is the analytic zero-energy tail wave.
    """
    import mpmath
    if k == 0:
        return 0.0, 0.0, *_threshold_wave(alpha_mu, r)
    if open_:
        f, g = mpmath.coulombf(0, eta, k * r), mpmath.coulombg(0, eta, k * r)
        df = mpmath.diff(lambda x: mpmath.coulombf(0, eta, x), k * r) * k
        dg = mpmath.diff(lambda x: mpmath.coulombg(0, eta, x), k * r) * k
        return (complex(f) / k, complex(df) / k, complex(g + 1j * f) / k, complex(dg + 1j * df) / k)
    w = mpmath.whitw(-eta, 0.5, 2 * k * r)
    dw = mpmath.diff(lambda x: mpmath.whitw(-eta, 0.5, x), 2 * k * r) * 2 * k
    # only the closed wave's log-derivative enters the matching (its own amplitude is discarded); W ~ e^{−κr} itself
    # underflows a double beyond κr ≈ 720 (the audit's G8-3, G12: a quintuplet at 20 TeV and v = 10⁻⁴ crashed)
    return 0.0, 0.0, 1.0 + 0j, complex(dw / w)


def enhancement(potential, thresholds: np.ndarray, coulomb_alpha: np.ndarray, mu: float, energy: float,
                r_max: float, r_min: float = 1e-7) -> np.ndarray:
    """The matrix A_ij of wave functions at the origin: channel i's amplitude for an incoming wave in channel j.

    Solves u″ = 2μ[V(r) + Δ − E] u for the s-wave, N channels with thresholds Δ (GeV, above the
    lowest) and potential matrix ``potential(r)`` (GeV, N×N), from N regular solutions (u(0) = 0,
    u′(0) = 1) matched at ``r_max`` to Coulomb waves (α of the channel's tail, attractive > 0)
    in open channels and decaying waves in closed ones. Without a potential A = 1, so the
    annihilation of state j is σv_j = (A† Γ A)_jj with Γ the matrix of tree-level σv.
    Columns of closed incoming channels are zero.

    A closed channel's regular solution grows as e^{κr}, κ = √(2μ(Δ − E)). Once κ r_max passes ``GROWTH`` (a
    quintuplet at 70 TeV has κ r_max ~ 100) every column of the solution matrix turns towards that one growing mode
    and the matching loses them. The integration then goes in stretches of κΔr = ``GROWTH_STEP``, after each of
    which the columns are re-orthonormalised (Y = QR, Y → Q): a change of basis of the regular solutions, which the
    weights undo at the end (``_regular_solutions``).

    A channel within rounding (``THRESHOLD_ROUNDING``) of its threshold is taken at the threshold, on either side.
    A rounding error of 10⁻¹⁷ GeV below an attractive Coulomb threshold is otherwise a closed channel with
    η = μα/κ ~ 10⁷: the Whittaker wave overflows (the wino at M = 1 TeV, δ = 0.2 + 4×10⁻¹⁷ GeV, where a sample energy
    of the neutral pair meets the charged pair's threshold 2δ). The Rydberg levels there are 10⁻²³ GeV apart; the
    threshold wave is the continuation from above, which the thermal average sees.
    """
    n = len(thresholds)
    thresholds = np.asarray(thresholds, dtype=float)

    def rhs(r, y):
        u = y[: n * n].reshape(n, n)
        du = y[n * n:].reshape(n, n)
        w = 2.0 * mu * (potential(r) + np.diag(thresholds - energy))
        return np.concatenate([du.ravel(), (w @ u).ravel()])

    kappa = float(np.sqrt(2.0 * mu * max(float(np.max(thresholds)) - energy, 0.0)))
    u, du, basis = _regular_solutions(rhs, n, r_min, r_max, kappa)
    out = np.zeros((n, n), dtype=complex)
    asym = []
    for i in range(n):
        excess = energy - thresholds[i]
        if abs(excess) <= THRESHOLD_ROUNDING * max(abs(energy), abs(thresholds[i])):
            excess = 0.0                  # a rounding-level distance from the threshold is the threshold itself
        open_ = excess > 0
        k = np.sqrt(2.0 * mu * abs(excess))
        eta = -mu * coulomb_alpha[i] / k if k > 0 else 0.0
        asym.append((open_, *_asymptotic(eta, k, r_max, open_, alpha_mu=mu * coulomb_alpha[i])))
    for j in range(n):
        if not asym[j][0]:
            continue
        # unknowns: c (n regular-solution weights) and t (n outgoing amplitudes)
        m = np.zeros((2 * n, 2 * n), dtype=complex)
        rhs_vec = np.zeros(2 * n, dtype=complex)
        for i in range(n):
            _, f, df, h, dh = asym[i]
            scale = max(abs(h), abs(dh)) or 1.0           # a deeply closed channel's wave is ~e^{−κr}: rescaled
            m[i, :n], m[n + i, :n] = u[i], du[i]
            m[i, n + i], m[n + i, n + i] = -h / scale, -dh / scale
            if i == j:
                rhs_vec[i], rhs_vec[n + i] = f, df
        out[:, j] = basis @ np.linalg.solve(m, rhs_vec)[:n]
    return out


def _regular_solutions(rhs, n: int, r_min: float, r_max: float, kappa: float):
    """(U, U′, B) at r_max: N regular solutions (columns), and the change of basis B from the solutions with u(0) = 0,
    u′(0) = 1 to these, which the weights of the matching multiply (``enhancement``)."""
    from scipy.integrate import solve_ivp
    stretches = 1 if kappa * r_max <= GROWTH else int(np.ceil(kappa * (r_max - r_min) / GROWTH_STEP))
    y = np.vstack([r_min * np.eye(n), np.eye(n)])
    basis = np.eye(n)
    edges = np.linspace(r_min, r_max, stretches + 1)
    for k, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
        state = np.concatenate([y[:n].ravel(), y[n:].ravel()])
        sol = solve_ivp(rhs, (a, b), state, method="DOP853", rtol=1e-9, atol=1e-14)
        y = np.vstack([sol.y[: n * n, -1].reshape(n, n), sol.y[n * n:, -1].reshape(n, n)])
        if k < stretches - 1:
            q, r = np.linalg.qr(y)
            y, basis = q, basis @ np.linalg.inv(r)
    return y[:n], y[n:], basis
