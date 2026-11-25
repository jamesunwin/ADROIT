"""Feng & Smolinsky (arXiv:1707.03835), complex scalar φφ* → A′ → e⁺e⁻: Ωh² at the zoo's four points by the paper's
own method (eqs. (2), (5), (8), (9), (23), (28)) and by ADROIT's, one change at a time ($0; the G12 closure record, the Feng
question; decision D31). Also the sensitivity to the degrees of freedom below T = 1 MeV.

One species is solved with its own degeneracy and rate (g = 1, ⟨σv⟩), φ and φ* together with theirs (g = 2, ⟨σv⟩/2);
with equal populations n = 2n_φ, so the second is exactly twice the first, which the counting control checks (the
external audit's A11, 2026-10-16: both columns had used g = 2, so the ratio had not isolated the counting). The Feng
et al. points include the held-out resonance entry, unblinded at the owner's request on 2026-10-16; each run of this
script on it is recorded in docs/dm10/post_unblinding.jsonl.

    uv run python scripts/feng_relic_check.py
"""


import math

import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq

from adroit.constraints import relic

ALPHA = 1 / 137.035999          # the paper's α in κ e (Thomson limit; D29's e(0))
ME = 0.000510999
POINTS = {  # name: (m_A′, m_X, α_X, κ²) in GeV, from the zoo's targets (the paper's Fig. 1 readings)
    "off-res 100 MeV": (0.1, 0.03333, 0.5, 1.936e-08),
    "off-res 30 MeV": (0.03, 0.01, 0.5, 1.556e-09),
    "eps_R 0.1": (0.1, 0.04767, 0.5, 2.46e-12),
    "eps_R 0.01": (0.1, 0.04975, 0.5, 8.67e-14),
}


def widths(ma, mx, ax, k2):
    """Γ(A′ → φφ*) (eq. 5) and Γ(A′ → e⁺e⁻) (eq. 2)."""
    b2 = max(1 - 4 * mx ** 2 / ma ** 2, 0.0)
    g_inv = 4 * math.pi * ax * ma / (48 * math.pi) * b2 ** 1.5
    r = 4 * ME ** 2 / ma ** 2
    g_e = k2 * 4 * math.pi * ALPHA * ma / (12 * math.pi) * math.sqrt(1 - r) * (1 + r / 2)
    return g_inv, g_e


def sigma_v_lab(eps, ma, mx, ax, k2, running=False):
    """Eq. (28): σ v_lab at ε = (s − 4m²)/4m², with a constant width (the paper) or Γ(√s) (``running``)."""
    s = 4 * mx ** 2 * (1 + eps)
    g_inv, g_e = widths(ma, mx, ax, k2)
    if running:     # the p-wave invisible width and the e⁺e⁻ width at √s, scaled as m Γ → √s Γ(√s)
        b2 = max(1 - 4 * mx ** 2 / s, 0.0)
        mg = 4 * math.pi * ax * s / (48 * math.pi) * b2 ** 1.5 + g_e * s / ma
    else:
        mg = ma * (g_inv + g_e)
    if 1 + eps - ME ** 2 / mx ** 2 <= 0:
        return 0.0
    num = eps * (ME ** 2 + 2 * (1 + eps) * mx ** 2) * math.sqrt(1 + eps - ME ** 2 / mx ** 2) / (
        (1 + 2 * eps) * math.sqrt(1 + eps))
    return 16 * math.pi * k2 * ALPHA * ax / 3 * num / ((s - ma ** 2) ** 2 + mg ** 2)


def v_lab(eps):
    return 2 * math.sqrt(eps) * math.sqrt(1 + eps) / (1 + 2 * eps)


def peak(ma, mx, ax, k2):
    g_inv, g_e = widths(ma, mx, ax, k2)
    return (ma ** 2 - 4 * mx ** 2) / (4 * mx ** 2), ma * (g_inv + g_e) / (4 * mx ** 2)   # ε_R, γ_R


def nr_average(x, p, running=False):
    """Eq. (23): ⟨σv⟩_NR = 2 x^{3/2}/√π ∫ σ v_lab ε^{1/2} e^{−xε} dε, the peak resolved."""
    eps_r, gamma_r = peak(*p)
    def f(e):
        return sigma_v_lab(e, *p, running=running) * math.sqrt(e) * math.exp(-x * e)
    top = 60.0 / x
    breaks = sorted({b for b in (eps_r - 50 * gamma_r, eps_r, eps_r + 50 * gamma_r) if 0 < b < top})
    edges = [0.0, *breaks, top]
    total = sum(quad(f, a, b, limit=400, epsabs=0, epsrel=1e-9)[0] for a, b in zip(edges[:-1], edges[1:]))
    return 2 * x ** 1.5 / math.sqrt(math.pi) * total


def gg_average(xs, p, running=False):
    """The relativistic (Gondolo–Gelmini) average on ADROIT's nodes: σ = σ v_lab / v_lab."""
    ma, mx = p[0], p[1]
    g_inv, g_e = widths(*p)
    u = relic.energy_grid(mx, ma, g_inv + g_e)
    eps = (1 + u) ** 2 - 1
    sig = np.array([sigma_v_lab(e, *p, running=running) / v_lab(e) if e > 0 else 0.0 for e in eps])
    return relic.thermal_average(u, sig, xs)


def omega_paper(p, avg, g_dof=1.0, geff_at="freeze-out"):
    """Eqs. (8)–(9): x_f from the freeze-out condition, then 8.77e-11 GeV⁻² [g_eff^{1/2} ∫ ⟨σv⟩/x² dx]⁻¹."""
    mx = p[1]
    mpl = relic.M_PLANCK_GEV

    def condition(x):
        g, h, _ = relic.degrees_of_freedom(mx / x)
        return 63 * math.sqrt(5) * x ** -0.5 * math.exp(-x) * g_dof / (32 * math.pi ** 3) * math.sqrt(g) / h \
            * mx * mpl * avg(x) - 1
    xf = brentq(condition, 2.0, 80.0)
    g_half = math.sqrt(relic.degrees_of_freedom(mx / xf)[0]) if geff_at == "freeze-out" else math.sqrt(geff_at)
    xs = np.geomspace(xf, 1e7, 1500)
    integrand = np.array([avg(x) for x in xs]) / xs ** 2
    return 8.77e-11 / (g_half * np.trapezoid(integrand, xs)), xf


def omega_boltzmann(p, sv_nodes, x_nodes, dirac=True):
    """ADROIT's Boltzmann solve (relic.freeze_out) with ⟨σv⟩ given on x_nodes."""
    return relic.OMEGA_PER_MY * p[1] * relic.freeze_out(p[1], x_nodes, sv_nodes, dirac=dirac)


def omega_species(p, running=False):
    """ADROIT's own path (``relic.omega_h2_species``: φ and φ*, one degree of freedom each, the relativistic
    average with the resonance resolved) with the analytic σ(s)."""
    ma, mx = p[0], p[1]
    g_inv, g_e = widths(*p)
    def sigma(s):
        eps = np.asarray(s) / (4 * mx ** 2) - 1
        return np.array([sigma_v_lab(e, *p, running=running) / v_lab(e) if e > 0 else 0.0 for e in np.atleast_1d(eps)])
    return relic.omega_h2_species(relic.dark_matter(mx, 0.0, False), {(0, 1): sigma}, [(ma, g_inv + g_e)])



X = np.geomspace(1.0, 2e4, 140)


def boltzmann(p, sv, g):
    """Ωh² from the full Boltzmann solve with ⟨σv⟩ ``sv`` on X and equilibrium degeneracy ``g``."""
    m = p[1]
    return relic.OMEGA_PER_MY * m * relic.freeze_out(m, X, sv, log_yeq=lambda x: relic.log_equilibrium_yield(x, m, g))


def counting_control(m: float = 80.0, sigma_v: float = 2.2e-9) -> tuple[float, float]:
    """(Y(g = 2, σ/2)/Y(g = 1, σ), Y(g = 2, σ/2)/Y(g = 2, σ)) for a constant rate at mass ``m``: 2 exactly by the
    change of variables, and the old diagnostic's mixed comparison (the audit's 1.99998 and 1.936)."""
    sv = np.full_like(X, sigma_v)
    one = boltzmann((0.0, m), sv, 1.0)
    both = boltzmann((0.0, m), sv / 2, 2.0)
    return both / one, both / boltzmann((0.0, m), sv, 2.0)


def realistic_dof(temperature):
    """g_eff, h_eff, g*^{1/2} below 1 MeV with the neutrinos decoupled (T_ν from entropy in γ + e±); ADROIT's above."""
    if temperature >= 1e-3:
        return ORIGINAL(temperature)
    def gas(t):
        r, q = relic._species(0.000511 / t, 1)
        g_ge = 2 + 4 * r * 30 / math.pi ** 2
        h_ge = 2 + 4 * (r + q) * 45 / (2 * math.pi ** 2)
        tnu3 = h_ge / 5.5                               # (T_ν/T)³: 11/2 = γ + e± relativistic, at decoupling
        return g_ge + 5.25 * tnu3 ** (4 / 3), h_ge + 5.25 * tnu3
    g, h = gas(temperature)
    dt = 1e-3 * temperature
    slope = (math.log(gas(temperature + dt)[1]) - math.log(gas(temperature - dt)[1])) / (2 * dt / temperature)
    return g, h, h / math.sqrt(g) * (1 + slope / 3)


ORIGINAL = relic.degrees_of_freedom

if __name__ == "__main__":
    exact, mixed = counting_control()
    print(f"counting control (80 GeV, constant rate): Y(g=2, σ/2)/Y(g=1, σ) = {exact:.7f}; "
          f"Y(g=2, σ/2)/Y(g=2, σ) = {mixed:.7f}")
    print(f"{'point':18s} {'paper eq8-9':>11s} {'Boltz,1 sp':>10s} {'φ+φ*':>8s} {'+rel avg':>9s} {'species':>8s} {'dof<1MeV':>9s}")
    for name, p in POINTS.items():
        nr = np.array([nr_average(x, p) for x in X])
        gg = gg_average(X, p)
        a = omega_paper(p, lambda x: nr_average(x, p))[0]
        b = boltzmann(p, nr, 1.0)       # full solution, one species: the paper's counting, g = 1 and ⟨σv⟩
        c = boltzmann(p, nr / 2, 2.0)   # φ and φ* together: g = 2 and ⟨σv⟩/2, exactly 2b
        d = boltzmann(p, gg / 2, 2.0)   # the relativistic average
        e = omega_species(p)            # ADROIT's own path
        relic.degrees_of_freedom = realistic_dof
        f = boltzmann(p, gg / 2, 2.0)
        relic.degrees_of_freedom = ORIGINAL
        print(f"{name:18s} {a:11.4f} {b:10.4f} {c:8.4f} {d:9.4f} {e:8.4f} {f:9.4f}")
    for t in (2e-3, 1e-3, 5e-4, 3e-4, 1e-4, 3e-5):
        print(f"T = {t*1e3:.2f} MeV: ADROIT (g, h, g*½) = {tuple(round(v, 3) for v in ORIGINAL(t))};"
              f" decoupled ν: {tuple(round(v, 3) for v in realistic_dof(t))}")
