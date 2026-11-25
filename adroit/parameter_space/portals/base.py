"""The portal library's common machinery: what every portal model gives the scan.

A portal model is a class with a few physics methods; this base turns them
into everything the scan and the verdict read, as DM13's classes do:
- ``channels(s, p)``: σ(DM DM → X)(s) by final state X, in GeV⁻²;
- ``coannihilation(p)``: other species in the bath and every pair's σ(s),
  if the model has partners near the dark matter's mass; ``thermal_pairs(p)``
  adds rates that depend on the temperature (bound-state formation);
- ``nucleon(p)``: the dark matter's couplings to protons and neutrons at zero
  momentum transfer, c₁ (spin-independent) and c₄ (spin-dependent), in the
  normalisation of ``physics.conventions``;
- ``invisible(p)``: the widths of the Higgs or Z boson into dark matter;
- ``pending(p)``: constraints that apply to the model but that ADROIT does not
  yet compute (beam dumps, flavour, dilepton resonances, ...), so the verdict
  calls such points pending, not viable;
- ``domain(p)``: why Ωh² is not computed at a point, if it is not.

**Parameters.** A point keeps DM13's five slots (m_χ, m_med, g_χ, g_q, g_ℓ);
each model says what its slots mean (``LABELS``), e.g. g_q is the kinetic
mixing ε of a dark photon, or the mixing angle sin θ of a singlet scalar.

**Direct detection.** Every non-zero channel (SI, SD-proton, SD-neutron) is
compared with its own validated limits (``dd_channels``): spin-independent
couplings that differ for protons and neutrons module by module, with each
target's Z/A. A channel without a validated limit at the mass makes the
outcome pending unless another channel excludes; ``dd`` reports the channel
that decides.
"""

from __future__ import annotations

import math
from typing import ClassVar

import numpy as np

from adroit.constraints import relic
from adroit.constraints.annihilation import GEV2_TO_CM3_S
from adroit.core.dm_state import InteractionModel, OperatorCoefficient
from adroit.core.state import StrictModel
from adroit.parameter_space import dd_channels
from adroit.parameter_space.classes import Point
from adroit.physics import conventions


class Nucleon(StrictModel):
    """Couplings to nucleons at q → 0 (GeV⁻²): σ_SI = c₁²μ²/π, σ_SD = 3c₄²μ²/(16π)."""

    c1_p: float = 0.0
    c1_n: float = 0.0
    c1_p_odd: float = 0.0           # a Dirac or complex relic's C-odd (vector) part, whose rate adds to c₁'s
    c1_n_odd: float = 0.0
    c4_p: float = 0.0
    c4_n: float = 0.0
    suppressed: str = ""            # why the leading scattering is absent (momentum-suppressed, loop-induced)
    structure: str = ""             # a nonrelativistic structure of ``operator_limits`` (e.g. "anapole"), compared
    scale: float = 0.0              # through Path 1: the interaction is ``scale`` × the structure's unit one


def fermi_ratio(channels: dict[str, float], m: float, record: dict, self_conjugate: bool) -> float | None:
    """Apply a source-supported pure prompt channel, preserving DM conjugacy."""
    from adroit.constraints.indirect import FERMI_CHANNELS, pure_ratio
    return pure_ratio(channels, m, {k: v["limit_cm3_s"] for k, v in record.items()},
                      FERMI_CHANNELS, self_conjugate)


class Portal(StrictModel):
    """A portal model: the base of the library's classes (see the module's text)."""

    name: str = ""
    LABELS: ClassVar[dict[str, str]] = {}
    SPIN: ClassVar[float] = 0.5
    SELF_CONJUGATE: ClassVar[bool] = False

    # --- what each model gives --------------------------------------------------------------
    def channels(self, s: np.ndarray, p: Point) -> dict[str, np.ndarray]:
        """σ(DM DM → X)(s) by final state X, in GeV⁻²; every model defines it."""
        raise NotImplementedError

    def nucleon(self, p: Point) -> Nucleon:
        """Couplings c₁, c₄ to protons and neutrons at q → 0 (``Nucleon``); by default no tree-level scattering."""
        return Nucleon(suppressed="no tree-level scattering")

    def coannihilation(self, p: Point) -> tuple[list, dict] | None:
        """The bath's species and every pair's σ(s) in GeV⁻² (``relic.omega_h2_species``) when partners lie near m_χ;
        None for the dark matter alone."""
        return None

    def thermal_pairs(self, p: Point) -> dict:
        """Rates of pairs of the bath that depend on the temperature, ⟨σv⟩(T) (``relic.omega_h2_species``)."""
        return {}

    def resonances(self, p: Point) -> list[tuple[float, float]]:
        """The s-channel poles (mass, width) in GeV that the thermal average resolves; none by default."""
        return []

    def invisible(self, p: Point) -> dict[str, float]:
        """Widths (GeV) of the Higgs (key h) or Z (key Z) boson into dark matter; none by default."""
        return {}

    def pending(self, p: Point) -> list[str]:
        """Constraints that apply at the point but that ADROIT does not compute, so the verdict calls the point
        pending, not viable; none by default."""
        return []

    def domain(self, p: Point) -> str:
        """Why Ωh² is not computed at the point; empty where it is."""
        return ""

    def spin(self) -> float:
        """The dark matter's spin (``SPIN``)."""
        return self.SPIN

    def self_conjugate(self) -> bool:
        """Whether the dark matter is its own antiparticle (``SELF_CONJUGATE``)."""
        return self.SELF_CONJUGATE

    def perturbative(self, p: Point) -> bool:
        """Whether every coupling slot (g_χ, g_q, g_ℓ) is at most √(4π) in magnitude."""
        return max(abs(p.g_chi), abs(p.g_q), abs(p.g_l)) <= math.sqrt(4.0 * math.pi)

    # --- what the scan reads -------------------------------------------------------------------
    def total(self, s: np.ndarray, p: Point) -> np.ndarray:
        """σ(DM DM → anything)(s) in GeV⁻²: the sum of ``channels``, quarks and gluons closed below the hadronic
        opening (``close_partons``)."""
        return sum(close_partons(s, self.channels(s, p)).values())

    def omega_h2(self, p: Point) -> float | None:
        """Ωh² from freeze-out of the dark matter alone (``total``) or of the coannihilating bath
        (``coannihilation``, ``thermal_pairs``); None outside the ``domain``."""
        if self.domain(p):
            return None
        bath = self.coannihilation(p)
        if bath is None:
            return relic.omega_h2_single(lambda s: self.total(s, p), p.m_chi, self.spin(), self.self_conjugate(),
                                         self.resonances(p))
        species, pairs = bath
        return relic.omega_h2_species(species, pairs, self.resonances(p), self.thermal_pairs(p))

    def freeze_out_x(self, p: Point) -> float | None:
        """x_f = m_χ/T_f of the bath ``omega_h2`` solves: where the yield first reaches twice its equilibrium value."""
        if self.domain(p):
            return None
        bath = self.coannihilation(p)
        if bath is None:
            species = relic.dark_matter(p.m_chi, self.spin(), self.self_conjugate())
            pairs = {(0, 0) if self.self_conjugate() else (0, 1): lambda s: self.total(s, p)}
            return relic.freeze_out_x_species(species, pairs, self.resonances(p))
        species, pairs = bath
        return relic.freeze_out_x_species(species, pairs, self.resonances(p), self.thermal_pairs(p))

    def sigma_v_today(self, p: Point, v_rel: float) -> dict[str, float]:
        """σv (cm³/s) by final state at relative velocity ``v_rel`` (in units of c): ``channels`` at s = 4m_χ²/(1 −
        β²), β = v_rel/2, quarks and gluons closed below the hadronic opening (``close_partons``)."""
        beta = 0.5 * v_rel
        s = np.array([4.0 * p.m_chi ** 2 / (1.0 - beta ** 2)])
        return {k: float(v[0]) * v_rel * GEV2_TO_CM3_S for k, v in close_partons(s, self.channels(s, p)).items()}

    def dd_channels(self, p: Point) -> list[dd_channels.Channel]:
        """Every non-zero scattering channel at q → 0 (none for a structure or a suppressed scattering)."""
        n = self.nucleon(p)
        if n.structure:
            return []
        return dd_channels.channels_of(n.c1_p, n.c1_n, n.c4_p, n.c4_n, p.m_chi, c1_odd=(n.c1_p_odd, n.c1_n_odd))

    def dd(self, p: Point) -> tuple[str, float]:
        """(kind, σ in cm²) of the channel that decides (``dd_channels``); for a structure of
        ``operator_limits``, (its name, the strength relative to its unit interaction)."""
        n = self.nucleon(p)
        if n.structure:
            return n.structure, n.scale
        return decisive(self.dd_channels(p), p.m_chi, n.suppressed or "momentum-suppressed")

    def interaction(self, p: Point) -> InteractionModel:
        """The nonrelativistic interaction of ``nucleon``'s couplings: its O₁ and O₄ terms (a zero O₁ term if both
        vanish)."""
        n = self.nucleon(p)
        terms = [OperatorCoefficient(operator=1, proton=n.c1_p, neutron=n.c1_n)] if (n.c1_p or n.c1_n) else []
        if n.c4_p or n.c4_n:
            terms.append(OperatorCoefficient(operator=4, proton=n.c4_p, neutron=n.c4_n))
        return InteractionModel(name=self.name or type(self).__name__, layer="nonrelativistic",
                                coefficients=terms or [OperatorCoefficient(operator=1)])

    def completion(self, p: Point) -> None:
        """The spin-1 simplified model the collider records compare with (``verdicts.benchmark_of``); None for a
        portal model."""
        return None

    def fermi(self, channels: dict[str, float], m: float, record: dict) -> float | None:
        """σv / limit against the Fermi-LAT dwarfs for a single pure prompt channel (``fermi_ratio``), with the
        model's conjugacy; None where no such channel applies."""
        return fermi_ratio(channels, m, record, self.self_conjugate())

    def label(self, slot: str) -> str:
        """The axis label of a slot (``LABELS``), or the slot's own name."""
        return self.LABELS.get(slot, slot)


PARTONS = frozenset({"u", "d", "s", "c", "b", "t", "g"})


def partonic(name: str) -> bool:
    """Whether a final state, by its channel's name ("u", "g", "u u~"), is quarks and gluons only (the measured R
    ratio's "hadrons" is not)."""
    parts = name.replace("~", "").split()
    return bool(parts) and all(x in PARTONS for x in parts)


def close_partons(s, channels: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """``channels`` with every quark and gluon final state zero below the hadronic opening, √s < 2m_π: no hadron is
    open there (``hadronic_window``; the recheck's RC21-01, 2026-10-22: the Z portal and the t-channel classes had
    free quarks below it, today and in Ωh²)."""
    from adroit.constraints import hadronic_window as hw
    below = np.sqrt(np.asarray(s, dtype=float)) < hw.opening(False)
    if not np.any(below):
        return channels
    return {k: np.where(below, 0.0, v) if partonic(k) else v for k, v in channels.items()}


def decisive(channels: list[dd_channels.Channel], mass: float, none: str = "momentum-suppressed"
             ) -> tuple[str, float]:
    """(kind, σ) of the deciding channel; a single isoscalar or spin-dependent channel needs no limit."""
    if not channels:
        return none, 0.0
    if len(channels) == 1 and channels[0].c_p is None:
        return channels[0].kind, channels[0].sigma_cm2
    best = dd_channels.compare(channels, mass).decisive
    return best.kind, best.sigma_cm2


def sigma_from(c: float, m: float) -> float:
    """σ_SI (cm²) of an O₁ coefficient."""
    return conventions.sigma_si_cm2(c, m)


def c1_of_sigma(sigma_cm2: float, m: float, sign: float = 1.0) -> float:
    """The O₁ coefficient (GeV⁻²) of σ_SI in cm², with the sign of ``sign``; 0 for σ_SI ≤ 0."""
    return math.copysign(conventions.c1_from_sigma_si(sigma_cm2, m), sign) if sigma_cm2 > 0 else 0.0


# --- channels from explicit amplitudes, tabulated once per point ----------------------------------

_STEPS = np.concatenate([[0.0], np.geomspace(1e-6, 25.0, 46)])
_TABLES: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}


def tabulated(key: tuple, sigma_at, m: float, sqrt_s_threshold: float, s: np.ndarray) -> np.ndarray:
    """σ(s) of a 2 → 2 channel computed point by point (``sigma_at(s)``), interpolated in u = √s/(2m) − 1.

    σ × β (β of the initial state) is smooth above the channel's threshold, so it is
    tabulated on fixed steps in u from the threshold and interpolated; ``key`` identifies
    the channel and the point (the cache holds the last 4,000 tables).
    """
    s = np.asarray(s, dtype=float)
    u0 = max(sqrt_s_threshold / (2.0 * m) - 1.0, 0.0)
    if key not in _TABLES:
        if len(_TABLES) > 4000:
            _TABLES.clear()
        nodes = u0 + _STEPS
        values = []
        for u in nodes:
            ss = (2.0 * m * (1.0 + max(u, 1e-9))) ** 2 * (1.0 + 1e-10)
            values.append(sigma_at(ss) * math.sqrt(max(1.0 - 4.0 * m * m / ss, 0.0)))
        _TABLES[key] = (nodes, np.array(values))
    nodes, table = _TABLES[key]
    u = np.sqrt(s) / (2.0 * m) - 1.0
    beta = np.sqrt(np.clip(1.0 - 4.0 * m * m / np.maximum(s, 1e-300), 0.0, None))
    smooth = np.interp(np.clip(u, nodes[0], nodes[-1]), nodes, table)
    return np.where((u > nodes[0]) & (beta > 0), smooth / np.where(beta > 0, beta, 1.0), 0.0)
