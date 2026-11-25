"""General electroweak n-plets (the owner, 2026-10-13): a Majorana fermion n-plet of SU(2)_L with Y = 0, or a Dirac
fermion n-plet with hypercharge Y ≠ 0, as the only new fields (minimal dark matter; Cirelli, Fornengo & Strumia
hep-ph/0512090). The thermal relic follows Bottaro et al. (BB21 = arXiv:2107.09688, real; BB22 = arXiv:2205.04486,
complex) in the SU(2)_L × U(1)_Y symmetric limit, with the channel rates and bound states of Mitridate, Redi, Smirnov
& Strumia (MRSS = arXiv:1702.01141 v3). The wino and the higgsino keep their own broken-phase engine
(``portals.multiplet``); this one generalises to any (n, Y).

**Two-body channels.** A pair decomposes into isospin I = 1, 3, …, 2n − 1 (I the dimension). A real pair (χχ)
obeys (−1)^{L+S+(I−1)/2} = 1 (BB21 eq. (11)); a complex one (χχ̄) has every (I, S). The potential is Coulombic with
the attractive strength

    α_eff(I) = α₂ (2n² − 1 − I²)/8 + Y² α_Y

(MRSS p. 8 for SU(2), with α_eff > 0 attractive; the hypercharge term attracts χ and χ̄ in every channel, BB22
eq. (B1), whose printed SU(2) term carries the opposite sign convention).

**Annihilation** (s-wave, averaged over all g_χ² initial states, the convention of MRSS eq. (17) that ADROIT's
relic solver uses: g_χ = 2n Majorana, 4n Dirac). Per channel, in units of π/M²:
- Majorana: (I, S) = (1, 0): α₂²(n² − 1)²/48n; (5, 0): α₂²(n² − 1)(n² − 4)/24n; (3, 1): 25α₂²(n² − 1)/32n. These
  sum to MRSS eq. (17) and reproduce its n = 3 and n = 5 decompositions (eqs. (85), (89)) exactly.
- Dirac: (1, 0): α₂²(n² − 1)²/96n + α_Y²Y⁴/2n; (5, 0): α₂²(n² − 1)(n² − 4)/48n; (3, 0): α₂α_Y Y²(n² − 1)/4n;
  (3, 1): 25α₂²(n² − 1)/64n; (1, 1): 41α_Y²Y²/16n. The sum is Cirelli, Strumia & Tamburini's s-wave (arXiv:0706.4071
  eq. (39)); the split follows the final states (BB → I = 1, WB → I = 3, an s-channel B → I = 1, S = 1) and is not
  published channel by channel (checked against the total only).
Each channel is multiplied by its s-wave Sommerfeld factor, Hulthén (MRSS eq. (28), κ = 1.74) with the vector mass
m_W below T_c and the Debye mass √(11/6) g₂ T above (MRSS eq. (72)); p-waves are left out (BB22 eq. (B3)).

**Bound states** (``bound_states``). Capture into the 1s and 2s states of every attractive channel I_f, from the
p-wave of I_f ± 2 by emitting a W (MRSS eqs. (51)–(52); the group factor Σ|C_J + γC_T|² = (I+1)(4n² − (I+1)²)/32 ×
(1 ∓ (I+1)γ/2)², I the smaller isospin, upper sign for I → I + 2, γ = α₂/α_eff(I_f), which reproduces MRSS
Table 1), and, for a complex pair, from the p-wave of I_f itself by emitting a B (the abelian case of MRSS eq. (49),
group factor I_f Y²). Each state exists below T = (α_eff/α₂) M/(25 × 1.7 n_B²) (MRSS eq. (73)) and, below T_c, for
M > κ n_B² m_W/α_eff (Hulthén). Its annihilation width is Γ = ½|ψ(0)|² σ(I_f, S) g_χ²/I_f(2S + 1), which gives
MRSS's 3240α₂⁵M, 15625α₂⁵M/48 and 567α₂⁵M/4 for the 5-plet's 1s₁, 1s₃, 1s₅ and the wino's 8α₂⁵M. A state enters
with Γ/(Γ + Γ_ion) (ionisation by detailed balance, ``sommerfeld.ionisation_equilibrium``), or with R = 1 (the
choice of BB22 for complex n-plets) if ``ionisation`` is off. A state that cannot annihilate (I ≥ 7, or a channel
with no s-wave rate) is left out with ionisation, since its decays to lower states are not computed; 2p states are
left out (MRSS eq. (53) carries a factor not verified here).

**Couplings.** α₂ and α_Y run at one loop in the Standard Model (``multiplet.alpha_2``): at M in annihilation, at
the inverse Bohr radius α₂(M)M in the potentials and the capture (MRSS p. 29).

**Below T_c** (160 GeV) a bound state is the Hulthén one, E_B(1 − n_B²y)² with y = κm_W/α_eff M (MRSS eq. (31)), and
capture emits massive vectors: a W with (k/ω)(1 − k²/3ω²)(1 + c_W²/2) + s_W²/3 of the massless rate, the photon's
s_W²/3 alone when ω < m_W (MRSS eq. (56)).

**Validation** (thermal masses in TeV for Ωh² = 0.11933; ``docs/nplet.md``):

    n_Y     this engine   potentials' α at M   Bottaro et al.
    3_1     2.67          2.62                 2.85 ± 0.14   (their SE in the broken phase, n < 6)
    4_1/2   4.50          4.35                 4.8 ± 0.3
    5_0    15.5          13.5                 13.6 ± 0.8    (MRSS: ≈ 14)
    5_1    10.7           9.56                 9.9 ± 0.7

The scale of α in the potentials, which Bottaro et al. do not state, moves the 5-plets by ±9%: that is the engine's
theory uncertainty. With the Sommerfeld effect alone the 5- and 7-plets are within 4% of their Fig. 1 (9.33, 22.2).
From n = 6 the bound states of channels I ≥ 7, which annihilate only through chains of transitions, matter and
are not computed (the 6_1/2 comes out 18 TeV against their 31.8), so ``domain`` stops at n = 5. The wino and the
higgsino are routed to ``portals.multiplet``.

**Direct detection** at one loop: Bottaro et al. arXiv:2205.04486 eqs. (17)–(18) with Hisano et al.'s nucleon inputs
(``constraints.loops``), which give the wino's 2.3 × 10⁻⁴⁷ cm² ADROIT uses; σ_SI is 2–2.5 times Bottaro et al.'s
(FLAG inputs) at Y = 0 and up to 6 times near the Y ≠ 0 cancellation, carried as an amplitude uncertainty.
**Not computed:** annihilation today (it needs the broken-phase Sommerfeld effect; every search that uses it is
undecided, ``today_unknown``), Z-mediated inelastic scattering below xenon's reach, 2p states, the LHC.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import ClassVar, Literal

import numpy as np
from pydantic import Field

from adroit.constraints import sommerfeld
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.base import Nucleon, Portal, c1_of_sigma
from adroit.parameter_space.portals.multiplet import KAPPA, M_W, T_C, alpha_2, alpha_y

DEBYE = math.sqrt(11.0 / 6.0)              # m_D = √(11/6) g T for SU(2) (MRSS eq. (72))
DEBYE_BOUND = 25.0 * 1.7                   # a state n_B exists below T = λ M/(25 × 1.7 n_B²) (MRSS eq. (73))
_Y_GRID = np.geomspace(1e-6, 50.0, 200)    # K/T for the Maxwell–Boltzmann average
_WEIGHT = 2.0 / math.sqrt(math.pi) * np.sqrt(_Y_GRID) * np.exp(-_Y_GRID)


def potential_scale(m: float) -> float:
    """The scale (GeV) of α₂ and α_Y in the potentials and the capture: the inverse Bohr radius α₂(M)M (MRSS p. 29)."""
    return alpha_2(m) * m


def pair_channels(n: int, real: bool) -> list[tuple[int, int]]:
    """The (I, S) of the s-wave two-body states: every (I, S) for a complex pair; (−1)^{S+(I−1)/2} = 1 for a real
    one."""
    return [(i, s) for i in range(1, 2 * n, 2) for s in (0, 1) if not real or (s + (i - 1) // 2) % 2 == 0]


def lam(n: int, i: int) -> float:
    """λ_I = (2n² − 1 − I²)/8: the SU(2) potential's strength in units of α₂, positive when attractive."""
    return (2.0 * n * n - 1.0 - i * i) / 8.0


def strength(n: int, y: float, i: int, q: float) -> float:
    """α_eff of channel I at the scale q: α₂λ_I + Y²α_Y (positive attractive)."""
    return alpha_2(q) * lam(n, i) + y * y * alpha_y(q)


def degrees(n: int, y: float) -> int:
    """g_χ: 2n for a Majorana n-plet (Y = 0), 4n for a Dirac one."""
    return 2 * n if y == 0 else 4 * n


def hard_rates(n: int, y: float, m: float) -> dict[tuple[int, int], float]:
    """σv (GeV⁻²) of each (I, S) channel at tree level, averaged over all g_χ² initial states (module docstring)."""
    a2, ay, unit = alpha_2(m), alpha_y(m), math.pi / m ** 2
    n2 = n * n
    if y == 0:
        rates = {(1, 0): a2 ** 2 * (n2 - 1) ** 2 / (48 * n), (5, 0): a2 ** 2 * (n2 - 1) * (n2 - 4) / (24 * n),
                 (3, 1): 25 * a2 ** 2 * (n2 - 1) / (32 * n)}
    else:
        rates = {(1, 0): a2 ** 2 * (n2 - 1) ** 2 / (96 * n) + ay ** 2 * y ** 4 / (2 * n),
                 (5, 0): a2 ** 2 * (n2 - 1) * (n2 - 4) / (48 * n), (3, 0): a2 * ay * y * y * (n2 - 1) / (4 * n),
                 (3, 1): 25 * a2 ** 2 * (n2 - 1) / (64 * n), (1, 1): 41 * ay ** 2 * y * y / (16 * n)}
    return {k: unit * v for k, v in rates.items() if v > 0 and k[0] < 2 * n}


def vector_mass(t: float, q: float, debye: bool = True) -> float:
    """The exchanged vector's mass: m_W below T_c, the Debye mass √(11/6) g₂ T above (or m_W if ``debye`` is off)."""
    if t < T_C or not debye:
        return M_W
    return DEBYE * math.sqrt(4.0 * math.pi * alpha_2(q)) * t


def hulthen(alpha: float, v: np.ndarray, m: float, m_v: float) -> np.ndarray:
    """The s-wave Sommerfeld factor of a Hulthén potential (MRSS eq. (28), κ = 1.74); Coulomb where the range is
    long (πMv/κm_V > 40); 1 at α = 0."""
    v = np.asarray(v, dtype=float)
    if alpha == 0:
        return np.ones_like(v)
    coulomb = 2.0 * math.pi * alpha / v / -np.expm1(-2.0 * math.pi * alpha / v)
    a = math.pi * m * v / (KAPPA * m_v)
    far = a > 40.0
    out = np.array(coulomb, dtype=float)
    near = ~far
    if near.any():
        an, vn = a[near], v[near]
        root = np.sqrt((1.0 - 4.0 * alpha * KAPPA * m_v / (m * vn ** 2)).astype(complex))
        denominator = np.cosh(an) - np.cosh(an * root).real
        out[near] = 2.0 * math.pi * alpha * np.sinh(an) / (vn * denominator)
    return np.maximum(out, 0.0)


def annihilation_rate(n: int, y: float, m: float, t: float, sommerfeld_on: bool = True, debye: bool = True) -> float:
    """⟨Σ_I S_I σ_I v⟩ (GeV⁻²) at temperature t: each channel's hard rate times its thermally averaged Sommerfeld
    factor."""
    rates = hard_rates(n, y, m)
    if not sommerfeld_on:
        return sum(rates.values())
    q = potential_scale(m)
    v = np.minimum(np.sqrt(4.0 * t * _Y_GRID / m), 1.0)
    m_v = vector_mass(t, q, debye)
    total = 0.0
    for (i, _), rate in rates.items():
        total += rate * float(np.trapezoid(_WEIGHT * hulthen(strength(n, y, i, q), v, m, m_v), _Y_GRID))
    return total


def group_terms(n: int, i_initial: int, i_final: int) -> tuple[float, float, float]:
    """(K, c, sign) of a W emitted between isospins I_i → I_f = I_i ± 2, such that Σ_{aMM'}|a C_J + b C_T|² =
    K (a + sign·c·b)² for any real a, b: K = (I+1)(4n² − (I+1)²)/32, c = (I+1)/2, I the smaller isospin, sign −1
    for I → I + 2 and +1 for I + 2 → I (MRSS Table 1 and eq. (50), any n)."""
    small = min(i_initial, i_final)
    return (small + 1) * (4 * n * n - (small + 1) ** 2) / 32.0, (small + 1) / 2.0, -1.0 if i_final > i_initial else 1.0


def group_factor(n: int, i_initial: int, i_final: int, gamma: float) -> float:
    """Σ_{aMM'} |C_J + γ C_T|² for a W emitted between isospins I_i → I_f (MRSS Table 1, any n)."""
    k, c, sign = group_terms(n, i_initial, i_final)
    return k * (1.0 + sign * c * gamma) ** 2


def _sommerfeld_times(zeta_s: np.ndarray, exponent: np.ndarray) -> np.ndarray:
    """2πζ_S/(1 − e^{−2πζ_S}) × e^{exponent}, computed in logarithms so that a repulsive initial channel (ζ_S < 0,
    where both factors are huge or tiny) neither overflows nor divides inf by inf."""
    x = 2.0 * math.pi * np.asarray(zeta_s, dtype=float)
    log_s0 = np.where(x > 0, np.log(np.abs(x)) - np.log(-np.expm1(-np.abs(x))),
                      np.log(np.abs(x) + 1e-300) - np.abs(x) - np.log(-np.expm1(-np.abs(x)) + 1e-300))
    return np.exp(np.minimum(log_s0 + exponent, 700.0))


def shape_1s(zeta_s: np.ndarray, zeta_b: np.ndarray) -> np.ndarray:
    """Harz & Petraki's S_BSF(ζ_S, ζ_B) of capture into a ground state (``sommerfeld.capture_shape``), stable for a
    repulsive initial channel."""
    tail = (1.0 + zeta_s ** 2) * zeta_b ** 4 / (1.0 + zeta_b ** 2) ** 3
    return _sommerfeld_times(zeta_s, -4.0 * zeta_s * np.arctan(1.0 / zeta_b)) * tail


def shape_2s(zeta_s: np.ndarray, zeta_b: np.ndarray) -> np.ndarray:
    """The velocity dependence of capture into 2s (MRSS eq. (52) in ζ_S = α_i/v, ζ_B = α_f/v):
    2¹⁴π ζ_S ζ_B⁴ (1 + ζ_S²) e^{−4ζ_S arccot(ζ_B/2)} / 3(ζ_B² + 4)⁵(1 − e^{−2πζ_S}), stable for ζ_S < 0."""
    tail = 2.0 ** 13 * zeta_b ** 4 * (1.0 + zeta_s ** 2) / (3.0 * (zeta_b ** 2 + 4.0) ** 5)
    return _sommerfeld_times(zeta_s, -4.0 * zeta_s * np.arctan(2.0 / zeta_b)) * tail


def _bound_states(n: int, y: float, m: float) -> list[dict]:
    """Every 1s and 2s state of an attractive channel, with the channels it is captured from: (I_i, α of the
    emitted vector, K, c, sign, γ) for a W (I_i = I_f ± 2) and, for a complex pair, a B (I_i = I_f, K = I_f Y²)."""
    q = potential_scale(m)
    a2, ay, g = alpha_2(q), alpha_y(q), degrees(n, y)
    real = y == 0
    rates = hard_rates(n, y, m)
    out = []
    for i_f, spin in pair_channels(n, real):
        a_f = strength(n, y, i_f, q)
        if a_f <= 0:
            continue
        sources = [(i_i, a2, *group_terms(n, i_i, i_f), a2 / a_f) for i_i in (i_f - 2, i_f + 2) if 1 <= i_i < 2 * n]
        if not real:
            sources.append((i_f, ay, i_f * y * y, 0.0, 0.0, 0.0))
        for level in (1, 2):
            out.append({"I": i_f, "S": spin, "n_B": level, "alpha_f": a_f, "sources": sources,
                        "rate": rates.get((i_f, spin), 0.0), "g": g})
    return out


def _capture(state: dict, n: int, y: float, m: float, v: np.ndarray, emission=None) -> np.ndarray:
    """σ_BSF v (GeV⁻²) into one bound state, summed over the channels it is captured from: MRSS eq. (51) for 1s,
    π α_emit α_f/M² (2S+1)/g² K(1 ± cγ)² × 2¹⁰/3 S_BSF(ζ_S, ζ_B), and eq. (52) for 2s, with the group sum
    K(a ± cγb′)², a = ζ_B(ζ_B − 2ζ_S) − 4, b′ = ζ_B(3ζ_B − 4ζ_S) − 4."""
    q = potential_scale(m)
    a_f, spin, g = state["alpha_f"], state["S"], state["g"]
    total = np.zeros_like(v)
    for i_i, a_emit, k, c, sign, gamma in state["sources"]:
        zeta_s, zeta_b = strength(n, y, i_i, q) / v, a_f / v
        prefactor = math.pi * a_emit * a_f / m ** 2 * (2 * spin + 1) / g ** 2 * k
        if emission is not None:
            prefactor = prefactor * emission(c == 0.0)
        if state["n_B"] == 1:
            total = total + prefactor * (1.0 + sign * c * gamma) ** 2 * 2.0 ** 10 / 3.0 * shape_1s(zeta_s, zeta_b)
        else:
            a = zeta_b * (zeta_b - 2.0 * zeta_s) - 4.0
            b = zeta_b * (3.0 * zeta_b - 4.0 * zeta_s) - 4.0
            total = total + prefactor * (a + sign * c * gamma * b) ** 2 * shape_2s(zeta_s, zeta_b)
    return total


@lru_cache(maxsize=64)
def _states(n: int, y: float, m: float) -> tuple:
    return tuple(_bound_states(n, y, m))


def annihilation_width(rate: float, g: int, i: int, spin: int, alpha: float, m: float, level: int = 1) -> float:
    """Γ (GeV) of an s-wave bound state n_B s in channel (I, S) annihilating: ½|ψ(0)|² σ(I, S) g_χ²/I(2S + 1) with
    the Coulomb |ψ(0)|² = (αM/2)³/π n_B³ and σ(I, S) averaged over the g_χ² initial states. It gives MRSS's widths:
    3240α₂⁵M, 15625α₂⁵M/48 and 567α₂⁵M/4 for the 5-plet's 1s₁, 1s₃, 1s₅ (table (91)), and 8α₂⁵M for the wino."""
    return 0.5 * (alpha * m / 2.0) ** 3 / math.pi / level ** 3 * rate * g ** 2 / (i * (2 * spin + 1))


def emission_below(omega: np.ndarray, abelian: bool) -> np.ndarray:
    """Below T_c, the rate of emitting the vector relative to a massless one (MRSS eqs. (55)–(56)): for a W³-like
    (SU(2)) emission (k/ω)(1 − k²/3ω²)(1 + c_W²/2) + s_W²/3 with k = √(ω² − m_W²) (the photon's s_W²/3 alone when
    ω < m_W); for a B, its photon part c_W² plus its Z part s_W² (3/2)(k/ω)(1 − k²/3ω²) with m_Z."""
    from adroit.parameter_space.portals.multiplet import CW2, M_Z, SW2

    def massive(m_v):
        k2 = np.maximum(omega ** 2 - m_v ** 2, 0.0)
        return np.sqrt(k2) / omega * (1.0 - k2 / (3.0 * omega ** 2))
    if abelian:
        return CW2 + SW2 * 1.5 * massive(M_Z)
    return massive(M_W) * (1.0 + CW2 / 2.0) + SW2 / 3.0


def _state_rate(state: dict, n: int, y: float, m: float, temperature: np.ndarray, ionisation: bool) -> np.ndarray:
    """One bound state's ⟨σ_BSF v⟩ R(T): above T_c a Coulomb state captured by massless emission, below T_c the
    Hulthén state (E_B (1 − n_B² y)², |ψ(0)|² (1 − n_B⁴y²), MRSS eqs. (31), (63)) captured by massive emission; each
    only where the state exists (module docstring)."""
    level, a_f, i_f, spin = state["n_B"], state["alpha_f"], state["I"], state["S"]
    y_h = KAPPA * level ** 2 * M_W / (a_f * m)
    debye_t = a_f / alpha_2(potential_scale(m)) * m / (DEBYE_BOUND * level ** 2)
    out = np.zeros_like(temperature)
    for broken in (False, True):
        if broken and y_h >= 1.0:
            continue
        shrink = (1.0 - level ** 2 * y_h) ** 2 if broken else 1.0
        e_b = a_f ** 2 * m / (4.0 * level ** 2) * shrink
        origin = (1.0 - level ** 4 * y_h ** 2) if broken else 1.0
        width = origin * annihilation_width(state["rate"], state["g"], i_f, spin, a_f, m, level)
        if ionisation and width <= 0:
            continue

        def active(t, broken=broken):
            return t < debye_t and (t < T_C) == broken

        def sigma_v(v, broken=broken, e_b=e_b):
            if not broken:
                return _capture(state, n, y, m, v)
            omega = e_b + m * v ** 2 / 4.0
            return _capture(state, n, y, m, v, lambda abelian: emission_below(omega, abelian))
        if ionisation:
            ion_g = state["g"] ** 2 / (2.0 * i_f * (2 * spin + 1))
            out += sommerfeld.ionisation_equilibrium(sigma_v, m, e_b, width, ion_g, temperature, active)
        else:
            out += sommerfeld.ionisation_equilibrium(sigma_v, m, e_b, 1e300, 1.0, temperature, active)
    return out


def bound_rate(n: int, y: float, m: float, temperature: np.ndarray, ionisation: bool = True) -> np.ndarray:
    """Σ over bound states of ⟨σ_BSF v⟩ R(T) (GeV⁻²): R from ionisation equilibrium, or 1 if ``ionisation`` is off
    (module docstring)."""
    temperature = np.atleast_1d(np.asarray(temperature, dtype=float))
    return sum((_state_rate(st, n, y, m, temperature, ionisation) for st in _states(n, y, m)),
               np.zeros_like(temperature))


def effective_rate(n: int, y: float, m: float, temperature: np.ndarray, sommerfeld_on: bool = True,
                   bound_states: bool = True, ionisation: bool = True, debye: bool = True) -> np.ndarray:
    """⟨σ_eff v⟩(T) in GeV⁻²: annihilation with the Sommerfeld effect, plus capture into bound states."""
    temperature = np.atleast_1d(np.asarray(temperature, dtype=float))
    out = np.array([annihilation_rate(n, y, m, t, sommerfeld_on, debye) for t in temperature])
    if bound_states and sommerfeld_on:
        out = out + bound_rate(n, y, m, temperature, ionisation)
    return out


def omega_h2(n: int, y: float, m: float, **options) -> float:
    """Ωh² of the n-plet of mass m (GeV): its 2n (Majorana) or 4n (Dirac) degenerate degrees of freedom in one
    bath, with ``effective_rate``."""
    from adroit.constraints import relic
    count = n if y == 0 else 2 * n
    species = [relic.Species(m, 2.0)] * count
    return relic.omega_h2_rate(species, lambda t: effective_rate(n, y, m, t, **options))


def thermal_mass(n: int, y: float, target: float = 0.11933, low: float = 300.0, high: float = 6e5,
                 **options) -> float:
    """The mass (GeV) at which Ωh² = ``target`` (Planck 2018's 0.11933, as Bottaro et al. use), by bisection in
    ln M (Ωh² rises with M)."""
    a, b = math.log(low), math.log(high)
    for _ in range(40):
        mid = 0.5 * (a + b)
        if omega_h2(n, y, math.exp(mid), **options) < target:
            a = mid
        else:
            b = mid
        if b - a < 2e-3:
            break
    return math.exp(0.5 * (a + b))


# --- the model class ----------------------------------------------------------------------------------------------

VALIDATED_N = 5                 # the largest n whose thermal mass is validated (module docstring, Validation)
MIN_MASS = 1000.0               # GeV: below, the symmetric limit is not a fair approximation of freeze-out
XENON_REACH_GEV = 4.5e-4        # δm₀ above which Z-mediated scattering on xenon is kinematically closed (BB22 eq. (6))
TODAY_UNKNOWN = ("the n-plet's annihilation today (v ≈ 10⁻³) needs the broken-phase Sommerfeld effect with its "
                 "resonances, which the symmetric-limit engine does not compute")
M_H_DD, M_W_DD = 125.0, 80.4    # BB22's inputs to eq. (17)
GEV2_TO_CM2 = 0.3893793721e-27
# the amplitude's relative uncertainty (Y = 0, Y ≠ 0): ADROIT's σ_SI (Hisano et al.'s nucleon inputs, which give the
# wino's 2.3 × 10⁻⁴⁷ cm² ADROIT uses) is 2.0–2.2 times Bottaro et al.'s at Y = 0 (FLAG inputs) and 2.5–5.8 times at
# Y ≠ 0, where the Z and W loops partly cancel (their ξ = 16.6 against 12.2 here)
DD_UNCERTAINTY = {False: 0.5, True: 1.0}
DD_NOTE = ("electroweak loops (Bottaro et al. arXiv:2205.04486 eqs. (17)–(18)); the nucleon inputs move σ_SI by a factor "
           "2 (Y = 0) to 6 (Y ≠ 0, near the Z–W cancellation)")


def _quark_couplings(q: str) -> tuple[float, float]:
    """(a_V, a_A) of a quark's Z coupling: T₃/2 − Q s_W², −T₃/2."""
    from adroit.parameter_space.portals.multiplet import SW2
    up = q in ("u", "c", "t")
    t3, charge = (0.5, 2.0 / 3.0) if up else (-0.5, -1.0 / 3.0)
    return t3 / 2.0 - charge * SW2, -t3 / 2.0


def sigma_si(n: int, y: float, nucleon: str = "p") -> tuple[float, float]:
    """(σ_SI in cm², the sign of k_N) from electroweak loops: Bottaro et al. arXiv:2205.04486 eqs. (17)–(18) (Y = 0:
    arXiv:2107.09688 eqs. (38)–(41)), with Hisano et al.'s nucleon inputs (``constraints.loops``)."""
    from adroit.constraints import loops
    from adroit.parameter_space.portals.multiplet import ALPHA_2_MZ
    a2, casimir, y2 = ALPHA_2_MZ, n * n - 1.0, y * y
    f_t = loops.F_T[nucleon]
    kappa = sum(loops.C_HEAVY.values())
    scalar = 0.0
    for q in ("u", "d", "s"):
        av, aa = _quark_couplings(q)
        f_q = -math.pi * a2 ** 2 / (16.0 * M_H_DD ** 2 * M_W_DD) * (casimir - (1.03 + 22.0 * (av ** 2 - aa ** 2)) * y2)
        scalar += f_q * f_t[q]
    twist = 0.0
    for q, moment in loops.MOMENTS[nucleon].items():
        av, aa = _quark_couplings(q)
        g_q = math.pi * a2 ** 2 / (24.0 * M_W_DD ** 3) * (casimir - (4.0 - 18.2 * (av ** 2 + aa ** 2)) * y2)
        twist += 0.75 * moment * g_q
    # f_G ∝ α_s: −(8π/9α_s) f_TG f_G does not depend on α_s
    gluon = -8.0 * math.pi / 9.0 * (1.0 - sum(f_t.values())) * a2 ** 2 / (192.0 * M_H_DD ** 2 * M_W_DD) * (
        (kappa + 2.6) * casimir - (1.03 * kappa - 7.5) * y2)
    k_n = scalar + twist + gluon
    return 4.0 / math.pi * loops.M_NUCLEON ** 4 * k_n ** 2 * GEV2_TO_CM2, math.copysign(1.0, k_n)


class ElectroweakNplet(Portal):
    """A general electroweak n-plet (module docstring): a Majorana n-plet with Y = 0 or a Dirac one with Y ≠ 0.
    Slots: m_χ = M; g_q = a Dirac n-plet's neutral splitting δm₀ in GeV (0: not stated), unused for a Majorana one."""

    family: Literal["electroweak_nplet"] = "electroweak_nplet"
    n: int = Field(default=5, ge=3, le=13)
    hypercharge: float = Field(default=0.0, ge=0.0)
    bound_states: bool = True
    ionisation: bool = True
    LABELS: ClassVar[dict[str, str]] = {"m_chi": "M (GeV)", "g_q": "δm₀ (GeV)"}

    def spin(self) -> float:
        """Spin ½."""
        return 0.5

    def self_conjugate(self) -> bool:
        """True for a Majorana n-plet (Y = 0)."""
        return self.hypercharge == 0

    def perturbative(self, p: Point) -> bool:
        """True: the only couplings are the electroweak gauge couplings (Landau poles are far above M for n ≤ 5)."""
        return True

    def domain(self, p: Point) -> str:
        """Ωh² is computed for n ≤ 5, Y ≤ 1 and M ≥ 1 TeV, where it is validated; else why not."""
        if self.n > VALIDATED_N:
            return (f"Ωh² of an n = {self.n} multiplet is not computed: its bound states in channels I ≥ 7, which "
                    "reach the Standard Model only through chains of transitions, are not computed (validated for n ≤ "
                    f"{VALIDATED_N})")
        if self.hypercharge > 1.0:
            return (f"Y = {self.hypercharge:g} is not computed: above Y = 1 the neutral splitting comes from operators "
                    "of dimension above 7 and cannot evade Z-mediated scattering (Bottaro et al. arXiv:2205.04486)")
        if p.m_chi < MIN_MASS:
            return f"M = {p.m_chi:.3g} GeV: the symmetric-limit relic calculation applies from {MIN_MASS:g} GeV"
        return ""

    def omega_h2(self, p: Point) -> float | None:
        """Ωh² from ``omega_h2`` (module function) with this model's options; None outside the ``domain``."""
        if self.domain(p):
            return None
        return omega_h2(self.n, self.hypercharge, p.m_chi, bound_states=self.bound_states, ionisation=self.ionisation)

    def channels(self, s, p: Point) -> dict[str, np.ndarray]:
        """None by final state: Ωh² comes from the bath's rate (``omega_h2``)."""
        return {}

    def sigma_v_today(self, p: Point, v_rel: float) -> dict[str, float]:
        """Not computed (``today_unknown``): every search that needs it is undecided."""
        return {}

    def today_unknown(self, p: Point) -> str:
        """Why today's annihilation is not computed (its γ-ray lines are, for a Majorana n-plet: ``resummed_lines``)."""
        return TODAY_UNKNOWN

    def resummed_lines(self, p: Point) -> dict[str, float] | None:
        """A Majorana n-plet's γ-ray line rate today, γγ-equivalent (cm³/s): the NLL resummed rate with the NLO
        Sommerfeld effect (``constraints.endpoint_nll``, 1–100 TeV); None for a Dirac n-plet or outside that range."""
        from adroit.constraints import endpoint_nll
        from adroit.parameter_space.searches import HESS_LINE_RESOLUTION, LINE_SPEED
        if self.hypercharge != 0 or self.n % 2 == 0:
            return None
        line = endpoint_nll.line_sigma_v(self.n, p.m_chi, LINE_SPEED, HESS_LINE_RESOLUTION)
        return None if line is None else {"gamma": line}

    def line_band(self, p: Point) -> tuple[float, float, str]:
        """(low, high, why) bracketing ``resummed_lines``' rate (``endpoint_nll.theory_band``), else (1, 1, "")."""
        from adroit.constraints import endpoint_nll
        if self.resummed_lines(p) is None:
            return 1.0, 1.0, ""
        return endpoint_nll.theory_band(self.n)

    def nucleon(self, p: Point) -> Nucleon:
        """Spin-independent scattering through electroweak loops (``sigma_si``), proton and neutron."""
        sigma_p, sign_p = sigma_si(self.n, self.hypercharge, "p")
        sigma_n, sign_n = sigma_si(self.n, self.hypercharge, "n")
        return Nucleon(c1_p=c1_of_sigma(sigma_p, p.m_chi, sign_p), c1_n=c1_of_sigma(sigma_n, p.m_chi, sign_n))

    def dd_channels(self, p: Point) -> list:
        """The SI channel with its amplitude uncertainty (``DD_UNCERTAINTY``): the nucleon inputs move σ_SI by about
        2 at Y = 0 against Bottaro et al.'s lattice set, and much more near the Y ≠ 0 cancellation."""
        from adroit.parameter_space import dd_channels
        n = self.nucleon(p)
        delta = DD_UNCERTAINTY[self.hypercharge != 0]
        return dd_channels.channels_of(n.c1_p, n.c1_n, 0.0, 0.0, p.m_chi, uncertainty=delta, note=DD_NOTE)

    def pending(self, p: Point) -> list[str]:
        """For a Dirac n-plet whose neutral splitting is below xenon's kinematic reach (450 keV) or not stated,
        Z-mediated inelastic scattering, which is not computed."""
        if self.hypercharge == 0 or p.g_q >= XENON_REACH_GEV:
            return []
        stated = f"δm₀ = {1e3 * p.g_q:.3g} MeV" if p.g_q > 0 else "δm₀ is not stated"
        return [f"direct detection: Z-mediated inelastic scattering ({stated}; below 450 keV xenon can scatter "
                "inelastically) is not computed"]
