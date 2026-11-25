"""A cheap bracket on the Sommerfeld effect in freeze-out, from group theory alone (G4's estimate, decision D4).

Where long-range forces matter and no module computes them (G7), ADROIT refuses Ωh² by default. On request it gives
the perturbative Ωh² with a warning and this bracket. The bracket needs only the gauge representations of the
annihilating pairs and the perturbative rate of each pair, and costs three re-solutions of the Boltzmann equation.

**The potential in each channel.** Two states in representations R₁ and R₂ of a gauge group exchange its bosons. In
the symmetric limit the potential is diagonal in the irreducible representations R of R₁ ⊗ R₂, with Coulomb strength

    α_eff(R) = α [C₂(R₁) + C₂(R₂) − C₂(R)]/2          (non-abelian; positive = attractive),

with quadratic Casimirs C₂ = (n² − 1)/4 for SU(2)'s n-dimensional representation and 0, 4/3, 10/3, 3, 6, 16/3, 8 for
SU(3)'s 1, 3 (3̄), 6 (6̄), 8, 10 (10̄), 15 (15̄), 27. An abelian group adds −α q₁q₂ (q the charges of the two
states as they enter: a particle–antiparticle pair attracts, α q², two particles repel). The groups' strengths
add channel by channel. This reproduces the n-plet engine's α₂(2n² − 1 − I²)/8 + Y²α_Y (``portals.nplet``) and the
colour factors of ``sommerfeld.COLOUR``.

**The Sommerfeld factor of one channel** (s-wave, relative velocity v; μ = m/2 for a pair of mass m each):
- a massless mediator: Coulomb, S = X/(1 − e^{−X}), X = 2πα/v (``sommerfeld.coulomb``, X = πα/β with v = 2β);
- a mediator of mass m_V: Hulthén (κ = 1.74, as ``portals.nplet``), with a = πmv/(κm_V) and c = 4ακm_V/(mv²),

      S = (2πα/v) sinh a / [cosh a − cos(a√(c − 1))]     (c > 1, attractive),
      S = (2πα/v) sinh a / [cosh a − cosh(a√(1 − c))]    (c ≤ 1, or α < 0 with √(1 + |c|)),

  **with the resonance phase a√(c − 1) frozen at π/2** once it passes π/2. This removes the zero-energy resonances
  (the first lies at phase 2π), and keeps their off-resonance value between peaks: S = (2πα/v) tanh a. That value
  saturates at 2π²αm/(κm_V) as v → 0, is Coulomb's at long range (a ≫ 1), and → 1 once the Bohr momentum αμ falls
  below the mediator mass, which switches the effect off. The choice was fixed before the calibration.
- thermally averaged over the Maxwell–Boltzmann distribution of the pair's kinetic energy K = μv²/2 at T = m/x.

**The bracket.** If a pair's hard annihilation is shared among its channels with fractions f_R ≥ 0, its
Sommerfeld-enhanced rate is Σ_R f_R S_R σv, which lies between min_R S_R and max_R S_R times σv. Channels from which
no final state can emerge at tree level carry no hard rate and may be dropped (``PairRate.final_su2_max``: two
Standard Model particles carry SU(2) dimension at most 5, so an n-plet pair annihilates into them only from I ≤ 5).
So, pair by pair:
- **low Ωh²:** each pair's rate × ⟨S⟩ of its most attractive channel;
- **high Ωh²:** × ⟨S⟩ of its least attractive (most repulsive) channel;
- **central Ωh²:** × Σ_R w_R ⟨S_R⟩, with w_R the share of the pair's two-particle states in R (dim R/dim R₁dim R₂),
  or the caller's channel shares of the hard rate where they are known.

Within its approximations (the symmetric limit, a potential diagonal in R, resonances removed) the low and high
values bracket the Sommerfeld effect. **Not included:** bound-state formation, which lowers Ωh² further (by up to a
factor of order 2 for electroweak 5-plets and coloured partners); resonances of a massive mediator; thermal (Debye)
masses; mixing of channels by mass splittings (the broken phase). The calibration against ADROIT's full engines is in
``docs/g4_bracket.md``.

**Couplings.** α is the caller's. ``bohr_alpha`` gives the convention used in the calibration: α at the Bohr momentum
λα(q)μ of the most attractive channel, solved self-consistently.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from fractions import Fraction
from typing import Literal

import numpy as np
from pydantic import Field

from adroit.constraints import relic
from adroit.core.state import StrictModel

KAPPA = 1.74                                  # Hulthén's κ (Mitridate et al. eq. (31); ``portals.multiplet.KAPPA``)
LONG_RANGE = 40.0                             # a = πmv/κm_V beyond which the Hulthén factor is Coulomb's
_Y = np.geomspace(1e-6, 50.0, 200)            # K/T for the Maxwell–Boltzmann average (as ``portals.nplet``)
_W = 2.0 / math.sqrt(math.pi) * np.sqrt(_Y) * np.exp(-_Y)
WARNING = ("a perturbative estimate: the Sommerfeld effect is bracketed from group theory, not computed. Bound states "
           "are not included and lower Ωh² further; resonances of a massive mediator are not included")

SU3_CASIMIR = {"1": 0.0, "3": 4 / 3, "3bar": 4 / 3, "6": 10 / 3, "6bar": 10 / 3, "8": 3.0, "10": 6.0, "10bar": 6.0,
               "15": 16 / 3, "15bar": 16 / 3, "27": 8.0}
SU3_DIMENSION = {"1": 1, "3": 3, "3bar": 3, "6": 6, "6bar": 6, "8": 8, "10": 10, "10bar": 10, "15": 15, "15bar": 15,
                 "27": 27}
SU3_PRODUCTS = {                                # 1 ⊗ R = R is handled in ``su3_product``
    ("3", "3bar"): ["1", "8"], ("3bar", "3"): ["1", "8"],
    ("3", "3"): ["3bar", "6"], ("3bar", "3bar"): ["3", "6bar"],
    ("3", "8"): ["3", "6bar", "15"], ("8", "3"): ["3", "6bar", "15"],
    ("3bar", "8"): ["3bar", "6", "15bar"], ("8", "3bar"): ["3bar", "6", "15bar"],
    ("8", "8"): ["1", "8", "8", "10", "10bar", "27"],
}


class GaugeForce(StrictModel):
    """One gauge group's long-range force on the dark states."""
    group: Literal["SU2", "SU3", "U1"]
    name: str = ""                            # a U(1)'s name, matching ``PairRep.charges`` ("Y", a dark U(1), …)
    alpha: float = Field(ge=0.0)
    mediator_gev: float = Field(default=0.0, ge=0.0)   # the exchanged boson's mass (0: Coulomb)


class PairRep(StrictModel):
    """Two annihilating states' representations: SU(2) dimensions, SU(3) representations, and U(1) charges (each
    state's own, so a particle and its antiparticle carry q and −q)."""
    su2: tuple[int, int] = (1, 1)
    su3: tuple[str, str] = ("1", "1")
    charges: dict[str, tuple[float, float]] = Field(default_factory=dict)


class Channel(StrictModel):
    """One irreducible channel of a pair: its SU(2) dimension and SU(3) representation, its share of the pair's
    two-particle states, and its potential (α_eff > 0 attractive) with the mediator mass it is given."""
    su2: int
    su3: str
    share: float
    alpha: float
    mediator_gev: float


class PairRate(StrictModel):
    """A pair's representations and its perturbative contribution to ⟨σ_eff v⟩ on the x nodes (GeV⁻²), with
    optional channel shares of its hard rate (keys "I/su3", e.g. "1/1"), which replace the state-counting shares
    in the central value, and optionally the largest SU(2) dimension its final states can carry (``final_su2_max``:
    5 for any two Standard Model particles, W ⊗ W), which removes the channels whose hard rate vanishes at tree
    level."""
    pair: PairRep
    rate: list[float]
    shares: dict[str, float] = Field(default_factory=dict)
    final_su2_max: int | None = None


class Bracket(StrictModel):
    """Ωh² perturbatively and with the Sommerfeld effect bracketed (module docstring)."""
    omega_perturbative: float
    omega_low: float
    omega_central: float
    omega_high: float
    alpha_max: float
    alpha_min: float
    channels: list[Channel]
    warning: str = WARNING


# --- group theory -------------------------------------------------------------------------------------------------

def su2_casimir(n: int) -> float:
    """C₂ of SU(2)'s n-dimensional representation: j(j + 1) = (n² − 1)/4."""
    return (n * n - 1) / 4.0


def su2_product(n1: int, n2: int) -> list[int]:
    """The dimensions of the irreducible representations in n₁ ⊗ n₂ (each once): |n₁ − n₂| + 1, …, n₁ + n₂ − 1."""
    return list(range(abs(n1 - n2) + 1, n1 + n2, 2))


def su3_product(r1: str, r2: str) -> list[str]:
    """The irreducible representations in r₁ ⊗ r₂ (with repetition), for 1, 3, 3̄ and 8.

    Raises:
        ValueError: for a product not tabulated.
    """
    if r1 == "1":
        return [r2]
    if r2 == "1":
        return [r1]
    found = SU3_PRODUCTS.get((r1, r2))
    if found is None:
        raise ValueError(f"the colour product {r1} ⊗ {r2} is not tabulated")
    return list(found)


def channels(pair: PairRep, forces: list[GaugeForce]) -> list[Channel]:
    """Every irreducible channel of the pair with its share of the states and its α_eff (module docstring).

    The mediator mass of a channel is the strength-weighted mean of its groups' (Σ|α_g| m_g / Σ|α_g|).
    """
    (n1, n2), (c1, c2) = pair.su2, pair.su3
    nonabelian = {f.group: f for f in forces if f.group in ("SU2", "SU3")}
    abelian = [f for f in forces if f.group == "U1" and f.name in pair.charges]
    total = n1 * n2 * SU3_DIMENSION[c1] * SU3_DIMENSION[c2]
    out = []
    for i in su2_product(n1, n2):
        for r in su3_product(c1, c2):
            parts: list[tuple[float, float]] = []                  # (α contribution, mediator mass)
            if "SU2" in nonabelian and n1 * n2 > 1:
                g = nonabelian["SU2"]
                parts.append((g.alpha * (su2_casimir(n1) + su2_casimir(n2) - su2_casimir(i)) / 2.0, g.mediator_gev))
            if "SU3" in nonabelian and (c1, c2) != ("1", "1"):
                g = nonabelian["SU3"]
                parts.append((g.alpha * (SU3_CASIMIR[c1] + SU3_CASIMIR[c2] - SU3_CASIMIR[r]) / 2.0, g.mediator_gev))
            for f in abelian:
                q1, q2 = pair.charges[f.name]
                parts.append((-f.alpha * q1 * q2, f.mediator_gev))
            alpha = sum(a for a, _ in parts)
            weight = sum(abs(a) for a, _ in parts)
            mediator = sum(abs(a) * m for a, m in parts) / weight if weight > 0 else 0.0
            out.append(Channel(su2=i, su3=r, share=i * SU3_DIMENSION[r] / total, alpha=alpha, mediator_gev=mediator))
    return out


def bohr_alpha(alpha_of_q: Callable[[float], float], strength: float, mu: float, iterations: int = 60) -> float:
    """α at the Bohr momentum q = λα(q)μ of a channel of strength λ (α_eff = λα), solved by iteration."""
    alpha = alpha_of_q(max(mu, 1.0))
    for _ in range(iterations):
        alpha = alpha_of_q(max(strength * alpha * mu, 1.0))
    return alpha


# --- the Sommerfeld factor ------------------------------------------------------------------------------------------

def sommerfeld_factor(alpha: float, v: np.ndarray, m: float, mediator_gev: float) -> np.ndarray:
    """S(v) of one channel (module docstring): Coulomb for a massless mediator, else Hulthén with its resonance phase
    frozen at π/2; 1 at α = 0. ``v`` is the relative velocity, ``m`` the mass of each state."""
    v = np.maximum(np.asarray(v, dtype=float), 1e-9)
    if alpha == 0.0:
        return np.ones_like(v)
    x = 2.0 * math.pi * alpha / v
    guarded = np.clip(x, -700.0, 700.0)              # only the exponential is guarded: S = X for X ≫ 1
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        coulomb = np.where(np.abs(x) < 1e-8, 1.0 + 0.5 * x, x / -np.expm1(-guarded))
    if mediator_gev <= 0.0:
        return coulomb
    a = math.pi * m * v / (KAPPA * mediator_gev)
    c = 4.0 * alpha * KAPPA * mediator_gev / (m * v * v)
    out = np.array(coulomb, dtype=float)
    near = a <= LONG_RANGE
    if near.any():
        an, cn, xn = a[near], c[near], x[near]
        resonant = cn > 1.0
        phase = np.minimum(an * np.sqrt(np.where(resonant, cn - 1.0, 0.0)), 0.5 * math.pi)
        other = np.cosh(an * np.sqrt(np.where(resonant, 0.0, 1.0 - cn)))
        denominator = np.cosh(an) - np.where(resonant, np.cos(phase), other)
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            out[near] = xn * np.sinh(an) / denominator
    return np.maximum(np.nan_to_num(out, nan=1.0, posinf=1e300), 0.0)


def thermal_factor(alpha: float, mediator_gev: float, m: float, x_nodes: np.ndarray) -> np.ndarray:
    """⟨S⟩(x): the Maxwell–Boltzmann average of ``sommerfeld_factor`` over the pair's kinetic energy at T = m/x."""
    x_nodes = np.atleast_1d(np.asarray(x_nodes, dtype=float))
    out = np.empty_like(x_nodes)
    for k, x in enumerate(x_nodes):
        v = np.minimum(np.sqrt(4.0 * _Y / x), 1.0)
        out[k] = float(np.trapezoid(_W * sommerfeld_factor(alpha, v, m, mediator_gev), _Y))
    return out


# --- the bracket ----------------------------------------------------------------------------------------------------

def _omega(species: list[relic.Species], x_nodes: np.ndarray, rate: np.ndarray) -> float:
    """Ωh² of the bath with ⟨σ_eff v⟩ given on the x nodes (``relic.freeze_out`` with the bath's equilibrium yield).
    An estimate, not published: without ``freeze_out``'s late-annihilation test (AL6-01), as before."""
    m1 = min(sp.mass for sp in species)
    y0 = relic.freeze_out(m1, x_nodes, rate, log_yeq=lambda x: relic.log_equilibrium_yield_species(x, species),
                          settled=False)
    return relic.OMEGA_PER_MY * m1 * y0


def _key(ch: Channel) -> str:
    return f"{ch.su2}/{ch.su3}"


def bracket(species: list[relic.Species], x_nodes: np.ndarray, pairs: list[PairRate],
            forces: list[GaugeForce]) -> Bracket:
    """Ωh² perturbatively and with each pair's rate times the ⟨S⟩ of its most attractive channel (low), its least
    attractive one (high) and the share-weighted mean (central); ``m`` of the factors is the lightest species'.

    Raises:
        ValueError: if a pair's rate is not on the x nodes.
    """
    x_nodes = np.asarray(x_nodes, dtype=float)
    m = min(sp.mass for sp in species)
    totals = {k: np.zeros_like(x_nodes) for k in ("perturbative", "low", "central", "high")}
    every: list[Channel] = []
    cache: dict[tuple[float, float], np.ndarray] = {}

    def factor(ch: Channel) -> np.ndarray:
        key = (round(ch.alpha, 15), round(ch.mediator_gev, 9))
        if key not in cache:
            cache[key] = thermal_factor(ch.alpha, ch.mediator_gev, m, x_nodes)
        return cache[key]

    for pr in pairs:
        rate = np.asarray(pr.rate, dtype=float)
        if rate.shape != x_nodes.shape:
            raise ValueError("each pair's rate must be given on the x nodes")
        chans = channels(pr.pair, forces)
        if pr.final_su2_max is not None:                        # the selection rule: no hard rate in larger channels
            chans = [c for c in chans if c.su2 <= pr.final_su2_max] or chans
            total = sum(c.share for c in chans)
            chans = [c.model_copy(update={"share": c.share / total}) for c in chans]
        every += chans
        shares = {_key(c): c.share for c in chans}
        if pr.shares:
            norm = sum(pr.shares.values())
            shares = {_key(c): pr.shares.get(_key(c), 0.0) / norm for c in chans}
        strongest = max(chans, key=lambda c: c.alpha)
        weakest = min(chans, key=lambda c: c.alpha)
        totals["perturbative"] += rate
        totals["low"] += rate * factor(strongest)
        totals["high"] += rate * factor(weakest)
        totals["central"] += rate * sum(shares[_key(c)] * factor(c) for c in chans)
    omegas = {k: _omega(species, x_nodes, v) for k, v in totals.items()}
    return Bracket(omega_perturbative=omegas["perturbative"], omega_low=omegas["low"],
                   omega_central=omegas["central"], omega_high=omegas["high"],
                   alpha_max=max(c.alpha for c in every), alpha_min=min(c.alpha for c in every), channels=every)


BracketInputs = tuple[list[relic.Species], np.ndarray, list[PairRate], list[GaugeForce]]


def thermal_masses(inputs: Callable[[float], BracketInputs], target: float, guess: float,
                   tolerance: float = 2e-3) -> dict[str, float | None]:
    """The masses at which each of the bracket's four Ωh² equals ``target``: for each, the sign change of
    Ωh²(m) − target nearest ``guess`` on the grid guess × 1.25^k (|k| ≤ 12), bisected in ln m to ``tolerance``;
    None where there is none."""
    memo: dict[float, Bracket] = {}

    def at(m: float) -> Bracket:
        if m not in memo:
            memo[m] = bracket(*inputs(m))
        return memo[m]

    out: dict[str, float | None] = {}
    for name in ("perturbative", "low", "central", "high"):
        def f(m: float, name: str = name) -> float:
            return getattr(at(m), f"omega_{name}") - target
        out[name] = _nearest_root(f, guess, tolerance)
    return out


def _nearest_root(f: Callable[[float], float], guess: float, tolerance: float) -> float | None:
    """The root of f nearest ``guess`` on the grid guess × 1.25^k, |k| ≤ 12, bisected in ln m."""
    grid = {0: guess}
    values = {0: f(guess)}
    bracketing = None
    for k in range(1, 13):
        for j in (k, -k):
            grid[j] = guess * 1.25 ** j
            values[j] = f(grid[j])
            inner = j - 1 if j > 0 else j + 1
            if values[j] * values[inner] <= 0.0:
                bracketing = (j, inner)
                break
        if bracketing:
            break
    if bracketing is None:
        return None
    (lo, f_lo), (hi, _) = sorted((math.log(grid[j]), values[j]) for j in bracketing)
    while hi - lo > tolerance:
        mid = 0.5 * (lo + hi)
        f_mid = f(math.exp(mid))
        lo, hi, f_lo = (mid, hi, f_mid) if f_mid * f_lo > 0 else (lo, mid, f_lo)
    return math.exp(0.5 * (lo + hi))


def as_fraction(alpha_eff: float, alpha: float) -> str:
    """α_eff/α as a small fraction, for reports (e.g. "4/3")."""
    return str(Fraction(alpha_eff / alpha).limit_denominator(48)) if alpha else "0"
