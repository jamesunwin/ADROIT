"""Electroweak multiplets: the wino (a Majorana SU(2) triplet) and the higgsino (a Dirac doublet, Y = ½).

The dark matter is the neutral member of a multiplet whose only interactions are the
electroweak gauge interactions, so its mass M alone sets the relic density (the minimal
dark matter of Cirelli, Fornengo & Strumia, hep-ph/0512090). The charged members are
heavier by δ (radiative splitting: 165 MeV for the wino, 341 MeV for the higgsino, slot
g_q in GeV) and coannihilate; at M ≳ 1 TeV the exchange of W, Z and photons between the
annihilating pair (the Sommerfeld effect) changes the rate by O(1).

**The rate.** Two-particle states are grouped by charge Q and spin S. In each sector the
s-wave annihilation is a matrix Γ between states (its tree-level σv), and the potential V
is a matrix of Yukawa and Coulomb terms; the multi-state Schrödinger equation
(``sommerfeld.enhancement``) gives the wave functions at the origin A, and state j
annihilates at σv_j = (A†ΓA)_jj. In the Griest–Seckel bath of the multiplet's states,

    ⟨σ_eff v⟩(T) = Σ_sectors Σ_j e^{−Δ_j/T} ⟨σv_j⟩_T / Z(T)²,  Z = Σ_k g_k e^{−δ_k/T} / Σ_k g_k,

with Δ_j the state's threshold above the neutral pair and ⟨·⟩_T the Maxwell–Boltzmann
average over the pair's kinetic energy. The normalisation is such that at tree level, with
no splitting, ⟨σ_eff v⟩ = Σ Tr Γ = σ_eff: 37πα₂²/12M² for the wino (Mitridate et al.,
arXiv:1702.01141 eq. (17)), π(81 + 12t² + 43t⁴)α₂²/128M² for the higgsino (Cirelli et al.).

**Matrices.** Wino: Hisano et al. hep-ph/0610249 eqs. (2)–(5) and Cirelli, Strumia &
Tamburini (CST) arXiv:0706.4071 eqs. (10)–(13), with the Q = 1 potential's sign by spin from
Mitridate et al. eqs. (80)–(84) (S = 0: +α₂e^{−m_W r}/r; S = 1: −α₂e^{−m_W r}/r). Higgsino:
CST eqs. (21)–(22) with Γ halved to the Griest–Seckel normalisation, the Z term of V₁₁ with
its α₂ (Hisano et al. hep-ph/0412403 eq. (30)), and the charged thresholds 2δ.

**Couplings.** α₂(m_Z) = 0.0347 and α = 1/128.9 in the potentials (Beneke et al.,
arXiv:1601.04718); α₂ and α_Y at 2M (one-loop Standard Model running) in Γ.

**Bound states** (``bound_states``; Mitridate et al. sections 4–7). The wino's I = 1 pair
(α_eff = 2α₂) binds when the Bohr momentum beats the W mass, M > κ m_W/α_eff (Hulthén, κ = 1.74:
M ≳ 2.0 TeV), with E_B = (α_eff² M/4)(1 − y)², y = κ m_W/(α_eff M), below T_c ≈ 160 GeV and the
Debye limit T < 2M/(25 × 1.7). It is captured from the I = 3 p-wave by emitting a photon:
σv = (256/3)(πα₂²/M²) S_BSF(α₂/v, 2α₂/v) × s_W²/3 (averaged over the 6 states, as σ_eff), decays
at Γ = 8α₂⁵M (1 − y²), and is ionised by the bath's photons (Milne: g_χ²/2g_B = 18). Our choice:
the capture also carries the factor 1 − y² of the shallow bound state's wave function, as the
decay does (Mitridate's eq. (63)); without it Ωh² falls by 3.7% at 2.9 TeV, with it by 2.7%
(Mitridate et al.: 1.3–2%).
The higgsino's only attractive channel (α_eff = 3α₂/4 + α_Y/4) binds only above M ≈ 5 TeV, so it
has no bound state where its relic is thermal (above 5 TeV it is not computed).
**γ-ray lines** (``line_sigma_v``, 2026-10-04). The wino's neutral pair reaches the photons only through
its charged component at the origin, d = A₁₂ of the Q = 0, S = 0 sector (Hisano et al.
hep-ph/0412403 eqs. (28), (46)–(49)): σv_γγ = 2πα²|d|²/M², σv_Zγ = (2c_W²/s_W²) σv_γγ, so
σv_γγ + ½σv_Zγ = 2παα₂|d|²/M² (α₂ at m_Z, as in the potential). The Sudakov logarithms of the
exclusive final state suppress this by the ratio of Ovanesyan, Slatyer & Stewart's NLL and
tree-level Sommerfeld curves (arXiv:1409.8294 Fig. 2, digitised: 0.81 at 0.5 TeV, 0.53 at 2.9 TeV,
0.33 at 10 TeV), a smooth function of M multiplied in. Validated against the NLL curve of
Baumgart et al. (arXiv:1808.08956, the curve H.E.S.S. compares with) to 1–25% away from the
2.3 TeV resonance. The higgsino's line is dominated by its one-loop amplitude, which the
Sommerfeld matrices do not hold: its σv_line is the NLL′ curve of Beneke, Urban & Vollmann
(arXiv:2203.01692) as plotted by H.E.S.S. (arXiv:2608.07234 Fig. 1), halved (the survey finds
the plotted curve is the photon count, 2σv_line).
**Since 2026-10-15 (decision D21) the default is DMγSpec's** (``constraints.resummed_lines``: NLL′ with the NLO
potentials, 0.5–100 TeV, the wino within 10 MeV of its 164.1 MeV splitting). It moves the wino's Sommerfeld
resonances: off resonance it is 0.5–1.8 times the curves above, which stay as its cross-check
(``hess_reference_line``) and its fallback; the higgsino agrees with them to 1–5%.
**Not included:** excited bound states, thermal masses, and the p-wave annihilation. The higgsino's neutral states are
taken as degenerate in the relic density and in the potentials (their splitting is far below the freeze-out
temperature), and as split into Majorana states today (below); a splitting below ~200 keV (the inelastic reach of
xenon experiments) is excluded by Z-mediated scattering, which is listed as pending.
**The higgsino today** (AL2-02, 2026-11-14; the owner's decision). Its neutral states are degenerate in the relic
density and in the potentials, but split into Majorana states today (as its lines say), so only the lightest
annihilates, as a self-conjugate particle: in the spin-0 sector alone, the s-wave of the spin-1 sector being forbidden
for two identical Majorana fermions. Its rate today is 8 (A†Γ^{S=0}A)₂₂, at tree level πα₂²(3 + 2t² + t⁴)/16M² (WW and
ZZ), not the degenerate Dirac pair's 8 Σ_S (2.4–3 times as large, most of it the spin-1 sector's Z-mediated fermion
pairs). The class stays Dirac for the relic density (``self_conjugate``), so today's rate is given doubled against the
searches' halving for a Dirac pair, as its lines are: every search that halves compares 8 (A†Γ^{S=0}A)₂₂.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from functools import lru_cache
from typing import ClassVar, Literal

import numpy as np

from adroit.constraints import relic, sommerfeld
from adroit.constraints.annihilation import GEV2_TO_CM3_S
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.base import Nucleon, Portal, c1_of_sigma

M_W, M_Z = 80.377, 91.1876
SW2 = 0.2312
CW2 = 1.0 - SW2
ALPHA_EM = 1.0 / 128.9
ALPHA_2_MZ = 0.034723
SPLITTING = {"wino": 0.165, "higgsino": 0.341}
LINE_SPEED = 1e-3               # the Milky Way's dark matter, relative speed in units of c
# NLL+SE / tree+SE of the wino's line (Ovanesyan, Slatyer & Stewart arXiv:1409.8294 Fig. 2, digitised): (M in GeV, ratio)
LINE_SUDAKOV = ((100.0, 1.068), (200.0, 1.016), (316.0, 0.908), (500.0, 0.812), (1000.0, 0.698), (2000.0, 0.591),
                (2500.0, 0.564), (3170.0, 0.515), (5000.0, 0.439), (10000.0, 0.332), (20000.0, 0.243))
# the higgsino's σv_line (cm³/s): Beneke, Urban & Vollmann's NLL′ as plotted by H.E.S.S. 2026, halved (module docstring)
HIGGSINO_LINE = ((500.0, 1.2e-28), (1000.0, 0.955e-28), (2000.0, 1.05e-28), (5000.0, 4.7e-28), (10000.0, 4.15e-28))
HIGGSINO_ZGAMMA = 0.886         # σv_Zγ/σv_γγ of the higgsino (Hisano et al. eq. (31))
# spin-independent scattering from electroweak loops (cm²; see ``nucleon``)
SIGMA_SI = {"wino": 2.3e-47, "higgsino": 7.4e-50}
_AmplitudeKey = tuple[Callable[[float], np.ndarray], tuple[float, ...], tuple[float, ...], float, float, float]
_AmplitudeCache = dict[_AmplitudeKey, np.ndarray]


def alpha_2(q: float) -> float:
    """α₂(Q) at one loop in the Standard Model (b₂ = −19/6)."""
    return 1.0 / (1.0 / ALPHA_2_MZ + 19.0 / (12.0 * math.pi) * math.log(q / M_Z))


def alpha_y(q: float) -> float:
    """α_Y(Q) = α/c_W² at m_Z, run at one loop (b_Y = 41/6)."""
    return 1.0 / (CW2 / ALPHA_EM - 41.0 / (12.0 * math.pi) * math.log(q / M_Z))


class Sector:
    """One charge-and-spin sector: thresholds (units of δ), Coulomb tails, V(r) and Γ (GeV⁻²)."""

    def __init__(self, name: str, thresholds: list[float], tails: list[float], potential, gamma: np.ndarray,
                 multiplicity: int = 1) -> None:
        self.name, self.thresholds, self.tails = name, np.array(thresholds), np.array(tails)
        self.potential, self.gamma, self.multiplicity = potential, gamma, multiplicity


def _yukawa(alpha: float, mass: float):
    return lambda r: alpha * math.exp(-mass * r) / r


def wino_sectors(m: float) -> list[Sector]:
    """The wino's sectors (module docstring), Γ in GeV⁻²."""
    a2, a = ALPHA_2_MZ, ALPHA_EM
    g = math.pi * alpha_2(2.0 * m) ** 2 / m ** 2
    w, z = _yukawa(a2, M_W), _yukawa(a2 * CW2, M_Z)

    def q0(r):
        return np.array([[-a / r - z(r), -math.sqrt(2.0) * w(r)], [-math.sqrt(2.0) * w(r), 0.0]])
    return [
        Sector("Q=0, S=0", [2.0, 0.0], [a, 0.0], q0, g / 9.0 * np.array([[3.0, math.sqrt(2.0)], [math.sqrt(2.0), 2.0]])),
        Sector("Q=0, S=1", [2.0], [a], lambda r: np.array([[-a / r - z(r)]]), np.array([[25.0 / 36.0 * g]])),
        Sector("Q=1, S=0", [1.0], [0.0], lambda r: np.array([[w(r)]]), np.array([[g / 9.0]]), 2),
        Sector("Q=1, S=1", [1.0], [0.0], lambda r: np.array([[-w(r)]]), np.array([[25.0 / 36.0 * g]]), 2),
        Sector("Q=2, S=0", [2.0], [-a], lambda r: np.array([[a / r + z(r)]]), np.array([[g / 9.0]]), 2),
    ]


def higgsino_sectors(m: float) -> list[Sector]:
    """The higgsino's sectors (module docstring), Γ in GeV⁻²."""
    a2, a = ALPHA_2_MZ, ALPHA_EM
    g = math.pi * alpha_2(2.0 * m) ** 2 / m ** 2 / 2.0          # CST's Dirac Γ, halved (module docstring)
    t2 = alpha_y(2.0 * m) / alpha_2(2.0 * m)
    w = _yukawa(a2 / 2.0, M_W)
    z_charged = _yukawa(a2 * (2.0 * CW2 - 1.0) ** 2 / (4.0 * CW2), M_Z)
    z_neutral = _yukawa(a2 / (4.0 * CW2), M_Z)

    def q0(r):
        return np.array([[-a / r - z_charged(r), -w(r)], [-w(r), -z_neutral(r)]])
    s0 = g / 64.0 * np.array([[3 + 2 * t2 + t2 ** 2, 3 - 2 * t2 + t2 ** 2], [3 - 2 * t2 + t2 ** 2, 3 + 2 * t2 + t2 ** 2]])
    s1 = g / 128.0 * np.array([[41 * t2 ** 2 + 25, 41 * t2 ** 2 - 25], [41 * t2 ** 2 - 25, 41 * t2 ** 2 + 25]])
    q1 = _yukawa(a2 * (2.0 * CW2 - 1.0) / (4.0 * CW2), M_Z)
    return [
        Sector("Q=0, S=0", [2.0, 0.0], [a, 0.0], q0, s0),
        Sector("Q=0, S=1", [2.0, 0.0], [a, 0.0], q0, s1),
        Sector("Q=1, S=0", [1.0], [0.0], lambda r: np.array([[q1(r)]]), np.array([[g * t2 / 16.0]]), 2),
        Sector("Q=1, S=1", [1.0], [0.0], lambda r: np.array([[q1(r)]]), np.array([[25.0 * g / 64.0]]), 2),
    ]


def _sector_rates(sector: Sector, m: float, delta: float, kinetic: np.ndarray, sommerfeld_on: bool,
                  amplitudes: _AmplitudeCache | None = None) -> np.ndarray:
    """σv_j (GeV⁻²) of each state j of a sector at kinetic energies K above its own threshold: (states, K)."""
    n = len(sector.thresholds)
    thresholds = sector.thresholds * delta
    lowest = thresholds.min()
    out = np.zeros((n, len(kinetic)))
    for j in range(n):
        for k, kin in enumerate(kinetic):
            if not sommerfeld_on:
                out[j, k] = sector.gamma[j, j]
                continue
            energy = thresholds[j] - lowest + kin
            mu = 0.5 * m
            momentum = math.sqrt(2.0 * mu * kin)
            r_max = max(30.0 / M_W, 6.0 / max(momentum, 1e-3)) if np.any(sector.tails) else 30.0 / M_W
            end = min(r_max, 400.0 / M_W)
            key = (sector.potential, tuple(thresholds - lowest), tuple(sector.tails), mu, float(energy), end)
            a = amplitudes.get(key) if amplitudes is not None else None
            if a is None:
                a = sommerfeld.enhancement(lambda r: sector.potential(r), thresholds - lowest, sector.tails,
                                           mu, energy, r_max=end)
                if amplitudes is not None:
                    a.setflags(write=False)
                    amplitudes[key] = a
            out[j, k] = float(np.real(np.conj(a[:, j]) @ sector.gamma @ a[:, j]))
    return out


@lru_cache(maxsize=64)
def rate_table(kind: str, m: float, delta: float, sommerfeld_on: bool) -> tuple:
    """(kinetic energies, [(sector multiplicity, thresholds, σv table)]) of a multiplet, computed once."""
    sectors = wino_sectors(m) if kind == "wino" else higgsino_sectors(m)
    v_rel = np.concatenate([np.geomspace(2e-4, 0.03, 14), np.geomspace(0.04, 1.3, 16)])
    kinetic = 0.25 * m * v_rel ** 2                       # μ v_rel² / 2 with μ = M/2
    # The higgsino's two Q=0 spin sectors share V, thresholds and Coulomb
    # tails. Solve their wave functions once; apply each distinct Γ separately.
    amplitudes: _AmplitudeCache = {}
    return kinetic, [(s.multiplicity, s.thresholds * delta,
                      _sector_rates(s, m, delta, kinetic, sommerfeld_on, amplitudes))
                     for s in sectors]


def effective_rate(kind: str, m: float, delta: float, temperature: np.ndarray, sommerfeld_on: bool = True) -> np.ndarray:
    """⟨σ_eff v⟩(T) in GeV⁻² (module docstring)."""
    kinetic, sectors = rate_table(kind, m, delta, sommerfeld_on)
    temperature = np.atleast_1d(np.asarray(temperature, dtype=float))
    species = _species(kind, m, delta)
    g_total = sum(sp.dof for sp in species)
    out = np.zeros_like(temperature)
    log_k = np.log(kinetic)
    for i, t in enumerate(temperature):
        y = np.geomspace(1e-6, 50.0, 200)                  # K/T
        weight = 2.0 / math.sqrt(math.pi) * np.sqrt(y) * np.exp(-y)
        z = sum(sp.dof * math.exp(-(sp.mass - m) / t) for sp in species) / g_total
        total = 0.0
        for multiplicity, thresholds, table in sectors:
            for j, threshold in enumerate(thresholds):
                values = np.exp(np.interp(np.log(np.clip(t * y, kinetic[0], kinetic[-1])), log_k,
                                          np.log(np.maximum(table[j], 1e-300))))
                total += multiplicity * math.exp(-threshold / t) * np.trapezoid(weight * values, y)
        out[i] = total / z ** 2
    return out


def _species(kind: str, m: float, delta: float) -> list[relic.Species]:
    if kind == "wino":
        return [relic.Species(m, 2.0), relic.Species(m + delta, 2.0), relic.Species(m + delta, 2.0)]
    return [relic.Species(m, 2.0), relic.Species(m, 2.0), relic.Species(m + delta, 2.0), relic.Species(m + delta, 2.0)]


@lru_cache(maxsize=256)
def wino_line(m: float, delta: float, v_rel: float = LINE_SPEED) -> float:
    """σv_γγ + ½σv_Zγ (cm³/s) of the wino's neutral pair with the Sommerfeld effect, at tree level: 2παα₂|A₁₂|²/M²."""
    sector = wino_sectors(m)[0]
    thresholds = sector.thresholds * delta
    mu, kinetic = 0.5 * m, 0.25 * m * v_rel ** 2
    r_max = min(max(30.0 / M_W, 6.0 / math.sqrt(2.0 * mu * kinetic)), 400.0 / M_W)
    a = sommerfeld.enhancement(sector.potential, thresholds - thresholds.min(), sector.tails, mu, kinetic, r_max=r_max)
    return 2.0 * math.pi * ALPHA_EM * ALPHA_2_MZ * abs(a[0, 1]) ** 2 / m ** 2 * GEV2_TO_CM3_S


def _log_interp(table: tuple, m: float, linear: bool = False) -> float:
    """A tabulated function of M, interpolated in ln M (log of the value unless ``linear``), clamped at the ends."""
    masses = np.log([a for a, _ in table])
    values = np.array([b for _, b in table])
    if linear:
        return float(np.interp(math.log(m), masses, values))
    return float(np.exp(np.interp(math.log(m), masses, np.log(values))))


T_C = 160.0                     # GeV: the electroweak crossover
KAPPA = 1.74                    # Hulthén: the critical point of a Yukawa potential (Mitridate et al. eq. (31))


def wino_bound_rate(m: float, temperature: np.ndarray) -> np.ndarray:
    """⟨σ_BSF v⟩_eff(T) of the wino's 1s, I = 1 bound state (module docstring); 0 where it does not exist."""
    a2 = ALPHA_2_MZ
    alpha_eff = 2.0 * a2
    y = KAPPA * M_W / (alpha_eff * m)
    if y >= 1.0:
        return np.zeros_like(np.atleast_1d(np.asarray(temperature, dtype=float)))
    e_b = alpha_eff ** 2 * m / 4.0 * (1.0 - y) ** 2
    gamma_dec = 8.0 * a2 ** 5 * m * (1.0 - y * y)

    def sigma_v(v):                    # the Coulomb capture, × (1 − y²) for the shallow (Hulthén) bound state
        coulomb = 256.0 / 3.0 * math.pi * a2 ** 2 / m ** 2 * sommerfeld.capture_shape(a2 / v, 2.0 * a2 / v)
        return coulomb * SW2 / 3.0 * (1.0 - y * y)
    return sommerfeld.ionisation_equilibrium(sigma_v, m, e_b, gamma_dec, 36.0 / 2.0, temperature,
                                             active=lambda t: t < min(T_C, 2.0 * m / (25.0 * 1.7)))


DMYSPEC_WINO_SPLITTING = 0.1641         # GeV: DMγSpec's wino tables
DMYSPEC_SPLITTING = 0.010                # GeV: a wino splitting this close takes DMγSpec's rate


class ElectroweakMultiplet(Portal):
    """The wino or the higgsino (slots: m_χ = M; g_q = the charged–neutral splitting δ in GeV, 0 = radiative)."""

    family: Literal["electroweak_multiplet"] = "electroweak_multiplet"
    multiplet: Literal["wino", "higgsino"] = "wino"
    sommerfeld: bool = True
    bound_states: bool = True
    LABELS: ClassVar[dict[str, str]] = {"m_chi": "M (GeV)", "g_q": "δ (GeV)"}

    def spin(self) -> float:
        """Spin ½ for both multiplets."""
        return 0.5

    def self_conjugate(self) -> bool:
        """True for the (Majorana) wino, False for the (Dirac) higgsino."""
        return self.multiplet == "wino"

    def perturbative(self, p: Point) -> bool:
        """Always True: the only couplings are the electroweak gauge couplings."""
        return True

    def splitting(self, p: Point) -> float:
        """The charged–neutral splitting δ in GeV: the slot g_q, or the radiative value (``SPLITTING``) when g_q is
        not positive."""
        return p.g_q if p.g_q > 0 else SPLITTING[self.multiplet]

    def domain(self, p: Point) -> str:
        """Ωh² is not computed below M = 100 GeV, where LEP excludes the charged states."""
        return "" if p.m_chi >= 100.0 else "LEP excludes charged states below ~100 GeV"

    def omega_h2(self, p: Point) -> float | None:
        """Ωh² from the bath's effective rate (``effective_rate``, with the Sommerfeld effect if ``sommerfeld``)
        plus, for the wino, bound-state formation (``wino_bound_rate``) if ``bound_states``; None outside the
        ``domain``."""
        if self.domain(p):
            return None
        delta = self.splitting(p)
        def rate(t):
            total = effective_rate(self.multiplet, p.m_chi, delta, t, self.sommerfeld)
            if self.bound_states and self.multiplet == "wino":
                total = total + wino_bound_rate(p.m_chi, t)
            return total
        return relic.omega_h2_rate(_species(self.multiplet, p.m_chi, delta), rate)

    def channels(self, s, p: Point) -> dict[str, np.ndarray]:
        """No channels by final state: Ωh² comes from the bath's rate (``omega_h2``) and today's σv from
        ``sigma_v_today``."""
        return {}

    def sigma_v_today(self, p: Point, v_rel: float, with_lines: bool = False) -> dict[str, float]:
        """σv of two neutral states today, with the Sommerfeld effect: gauge-boson continuum ("W"), and for the wino
        its tree-level γγ ("gamma") and Zγ ("Zgamma") rates as their own channels.

        The wino's sector rates include those photon rates (about 8% at tree level, more near a Sommerfeld
        resonance). They are not W continuum, but Zγ still gives a Z's decay products, so the mixture rules bound
        each separately; ``with_lines`` folds them back into one rate (the CMB, where every channel deposits
        energy). The γ-ray line searches read ``line_sigma_v`` instead. The higgsino has no tree-level photons.

        The higgsino's is the lightest Majorana state's (module docstring, "The higgsino today"): the spin-0 sector
        only, doubled, as its lines are, against the searches' halving for a Dirac pair.
        """
        delta = self.splitting(p)
        sectors = wino_sectors(p.m_chi) if self.multiplet == "wino" else higgsino_sectors(p.m_chi)
        kinetic = np.array([0.25 * p.m_chi * v_rel ** 2])
        rates = _sector_rates(sectors[0], p.m_chi, delta, kinetic, self.sommerfeld)      # Q = 0, S = 0
        # σ̄(neutral pair) = 9 (A†ΓA)₂₂ for the wino (Hisano: 2πα₂²/M² at tree level); the higgsino's lightest
        # Majorana state 8 (A†Γ^{S=0}A)₂₂, doubled against the searches' halving for a Dirac pair
        factor = 9.0 if self.multiplet == "wino" else 2.0 * 8.0
        rate = factor * rates[-1, 0] * GEV2_TO_CM3_S
        if self.multiplet != "wino" or with_lines:
            return {"W": rate}
        line = wino_line(p.m_chi, delta, v_rel)                         # σv_γγ = s_W² line, σv_Zγ = 2c_W² line
        gamma, zgamma = SW2 * line, 2.0 * CW2 * line
        return {"W": max(rate - gamma - zgamma, 0.0), "gamma": gamma, "Zgamma": zgamma}

    def cmb_sigma_v(self, p: Point) -> dict[str, float]:
        """⟨σv⟩ during recombination: the Sommerfeld-saturated rate at v_rel = 10⁻⁴, lines included."""
        return self.sigma_v_today(p, 1e-4, with_lines=True)

    def nucleon(self, p: Point) -> Nucleon:
        """Spin-independent scattering through electroweak loops in the heavy limit: σ_SI ≈ 2.3 × 10⁻⁴⁷ cm² for
        the wino (Hisano, Ishiwata & Nagata, arXiv:1504.00915) and 7.4 × 10⁻⁵⁰ cm² for the higgsino (Hisano et
        al. at NLO, arXiv:1504.00915; Hill & Solon arXiv:1409.8290 give ≲ 10⁻⁴⁸, a near-cancellation of the
        scalar and spin-2 amplitudes that makes the higgsino's value uncertain by an order of magnitude)."""
        sigma = SIGMA_SI[self.multiplet]
        if sigma <= 0:
            return Nucleon(suppressed="loop-induced, below 10⁻⁴⁸ cm² (not computed)")
        c = c1_of_sigma(sigma, p.m_chi)
        return Nucleon(c1_p=c, c1_n=c)

    def line_sigma_v(self, p: Point) -> dict[str, float]:
        """σv_γγ and σv_Zγ (cm³/s) of two neutral states today (module docstring, γ-ray lines): DMγSpec's resummed rate
        where its table is installed and its splitting applies (decision D21, the owner, 2026-10-15), else the
        H.E.S.S. reference curves (``hess_reference_line``). The higgsino's neutral states are split into Majorana
        states today (≳ 200 keV), so its lightest annihilates as a self-conjugate particle: its rates are doubled
        against the searches' halving for a Dirac pair."""
        from adroit.constraints import resummed_lines
        applies = self.multiplet == "higgsino" or abs(self.splitting(p) - DMYSPEC_WINO_SPLITTING) <= DMYSPEC_SPLITTING
        line = resummed_lines.line_sigma_v(self.multiplet, p.m_chi) if applies else None
        if line is not None:
            return {"gamma": 2.0 * line if self.multiplet == "higgsino" else line}
        return self.hess_reference_line(p)

    def line_band(self, p: Point) -> tuple[float, float, str]:
        """(low, high, why) bracketing ``line_sigma_v``'s rate: DMγSpec's above 13 TeV (``resummed_lines.
        theory_band``), else (1, 1, "")."""
        from adroit.constraints import resummed_lines
        applies = self.multiplet == "higgsino" or abs(self.splitting(p) - DMYSPEC_WINO_SPLITTING) <= DMYSPEC_SPLITTING
        if applies and resummed_lines.line_sigma_v(self.multiplet, p.m_chi) is not None:
            return resummed_lines.theory_band(p.m_chi)
        return 1.0, 1.0, ""

    def hess_reference_line(self, p: Point) -> dict[str, float]:
        """The rates H.E.S.S. compares with (module docstring): the wino's tree-level Sommerfeld lines × Ovanesyan,
        Slatyer & Stewart's NLL/tree ratio (Baumgart et al.'s NLL curve at 2.9 TeV), the higgsino's digitised NLL′
        curve. Kept as DMγSpec's cross-check and its fallback."""
        if self.multiplet == "higgsino":
            line = 2.0 * _log_interp(HIGGSINO_LINE, p.m_chi)
            gg = line / (1.0 + 0.5 * HIGGSINO_ZGAMMA)
            return {"gamma": gg, "Zgamma": HIGGSINO_ZGAMMA * gg}
        line = wino_line(p.m_chi, self.splitting(p)) * _log_interp(LINE_SUDAKOV, p.m_chi, linear=True)
        return {"gamma": SW2 * line, "Zgamma": 2.0 * CW2 * line}

    def pending(self, p: Point) -> list[str]:
        """For the higgsino, Z-mediated inelastic scattering, which excludes a neutral splitting below ~200 keV;
        nothing for the wino."""
        if self.multiplet == "higgsino":
            return ["direct detection: Z-mediated inelastic scattering excludes a neutral splitting below ~200 keV"]
        return []
