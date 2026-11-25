"""PPPC photon showers, branching mixtures and finite-mass scalar cascades."""

from __future__ import annotations

from functools import lru_cache
import math
from pathlib import Path
from typing import Literal, Any

import numpy as np
from pydantic import Field, model_validator
from scipy.integrate import cumulative_trapezoid

from adroit.core.state import StrictModel
from adroit.external.fetch import locate
from adroit.parameter_space.classes import Point, ScalarClass

PPPC_ITEM = "PPPC photon spectra"
COLUMNS = {
    "e": 4,
    "mu": 7,
    "tau": 10,
    "u": 11,
    "d": 11,
    "s": 11,
    "c": 12,
    "b": 13,
    "t": 14,
    "W": 17,
    "Z": 20,
    "g": 21,
    "hh": 23,
    "nu_e": 24,
    "nu_mu": 25,
    "nu_tau": 26,
}
THRESHOLDS = {
    "e": 0.000511,
    "mu": 0.105658,
    "tau": 1.77686,
    "u": 0.0022,
    "d": 0.0047,
    "s": 0.096,
    "c": 1.27,
    "b": 4.18,
    "t": 173.0,
    "W": 80.379,
    "Z": 91.1876,
    "hh": 125.09,
    "g": 0.0,
    "nu_e": 0.0,
    "nu_mu": 0.0,
    "nu_tau": 0.0,
}


class SpectrumUnavailable(ValueError):
    """The inputs lack a supported shower or decay description."""


class Decay(StrictModel):
    """One visible pair decay and its fraction of the mediator width."""

    channel: str
    branching: float = Field(gt=0, le=1, allow_inf_nan=False)


class Daughter(StrictModel):
    """One particle of a two-body annihilation (G6): a Standard Model particle that showers promptly (``channel``,
    half its PPPC pair yield at its energy) or a new state that decays at rest into pairs (``decays``, the remainder
    ``invisible``) and is boosted to its energy."""

    mass_gev: float = Field(ge=0, allow_inf_nan=False)
    channel: str = ""
    decays: list[Decay] = Field(default_factory=list)


class Component(StrictModel):
    """One prompt annihilation, an explicit two-scalar decay topology, or a two-body final state of distinct
    particles (``two_body``: χχ → X Y, generalising the scalar pair)."""

    channel: str
    branching: float = Field(gt=0, le=1, allow_inf_nan=False)
    mode: Literal["prompt", "scalar_pair", "two_body"] = "prompt"
    mediator_mass_gev: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    decays: list[Decay] = Field(default_factory=list)
    daughters: list[Daughter] = Field(default_factory=list)


class SpectrumRequest(StrictModel):
    """A mass and the complete, normalised annihilation branching fractions."""

    mass_gev: float = Field(gt=0, allow_inf_nan=False)
    components: list[Component]

    @model_validator(mode="after")
    def _normalised(self) -> SpectrumRequest:
        if not self.components or not math.isclose(
            sum(c.branching for c in self.components), 1.0, rel_tol=0, abs_tol=1e-10
        ):
            raise ValueError("Annihilation branching fractions must sum to one")
        for c in self.components:
            if c.mode == "prompt" and (c.decays or c.mediator_mass_gev is not None):
                raise ValueError("Prompt components cannot supply ignored mediator decays")
            if c.mode == "two_body":
                if len(c.daughters) != 2 or sum(d.mass_gev for d in c.daughters) > 2 * self.mass_gev:
                    raise ValueError("A two-body final state needs two daughters on shell")
                for d in c.daughters:
                    if bool(d.channel) == bool(d.decays) or (d.decays and not math.isclose(
                            sum(x.branching for x in d.decays), 1.0, rel_tol=0, abs_tol=1e-10)):
                        raise ValueError("A daughter showers (channel) or decays (fractions summing to one)")
            if c.mode == "scalar_pair":
                if c.mediator_mass_gev is None or c.mediator_mass_gev > self.mass_gev:
                    raise ValueError("A scalar pair must be on shell")
                if not c.decays or not math.isclose(
                    sum(d.branching for d in c.decays), 1.0, rel_tol=0, abs_tol=1e-10
                ):
                    raise ValueError("Mediator decay fractions must sum to one")
        return self


class PhotonSpectrum(StrictModel):
    """Photons per annihilation per GeV, with the generating assumptions."""

    request: SpectrumRequest
    energies_gev: list[float]
    dnde_per_gev: list[float]
    source: str = "PPPC4DMID release 6.0, arXiv:1012.4515, 1009.0224"
    assumptions: list[str] = Field(
        default_factory=lambda: [
            "unpolarized PPPC showers including electroweak corrections",
            "light u,d,s use the PPPC light-quark shower",
            "isotropic on-shell spin-zero mediator decays",
            "mediators decay promptly within the emitting source; no displaced transport",
        ]
    )


@lru_cache(maxsize=4)
def _table(path: str, size: int, mtime: int, ctime: int) -> np.ndarray:
    data = np.loadtxt(path, skiprows=1)
    if (
        data.ndim != 2
        or data.shape[1] != 30
        or not np.isfinite(data).all()
        or (data[:, 2:] < 0).any()
    ):
        raise SpectrumUnavailable("Invalid PPPC photon table")
    data.setflags(write=False)
    return data


def table(path: Path | None = None) -> np.ndarray:
    """Load current PPPC contents; no mass or energy extrapolation is allowed."""
    if path is None:
        root = locate(PPPC_ITEM)
        if root is None:
            raise SpectrumUnavailable("PPPC photon spectra are not installed")
        path = root / "AtProduction_gammas.dat"
    stat = path.stat()
    return _table(str(path.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def prompt(mass_gev: float, channel: str, energies_gev: np.ndarray, data: np.ndarray) -> np.ndarray:
    """Photons per annihilation per GeV from the actual pair shower."""
    if channel not in COLUMNS or mass_gev <= THRESHOLDS[channel]:
        raise SpectrumUnavailable(f"Unsupported or closed prompt channel {channel}")
    masses = np.unique(data[:, 0])
    if not masses[0] <= mass_gev <= masses[-1]:
        raise SpectrumUnavailable("Mass outside the PPPC release")
    high = int(np.searchsorted(masses, mass_gev, side="left"))
    low = max(0, high - 1) if masses[high] != mass_gev else high
    a, b = data[data[:, 0] == masses[low]], data[data[:, 0] == masses[high]]
    if masses[low] <= THRESHOLDS[channel] or (
        not channel.startswith("nu_") and not (a[:, COLUMNS[channel]] > 0).any()
    ):
        raise SpectrumUnavailable(f"No supported lower shower bracket for {channel}")
    weight = (
        0.0
        if low == high
        else math.log(mass_gev / masses[low]) / math.log(masses[high] / masses[low])
    )
    yields = (1 - weight) * a[:, COLUMNS[channel]] + weight * b[:, COLUMNS[channel]]
    energies = np.asarray(energies_gev, float)
    if not np.isfinite(energies).all() or (energies <= 0).any():
        raise ValueError("Photon energies must be finite and positive")
    logx = np.log10(energies / mass_gev)
    result = np.interp(logx, a[:, 1], yields, left=0.0, right=0.0) / (energies * math.log(10.0))
    result[energies >= mass_gev] = 0.0
    return result


LINES = ("gamma", "aa_photons", "photons", "Zgamma", "hgamma")    # channels with a monochromatic photon
GAMMA_COLUMN = 22                  # PPPC's γγ column: the line in its last x step, below it the electroweak continuum
LINE_STEP = 10 ** -0.05            # PPPC's last step in x = E/m_χ
M_Z = 91.1876
TWO_BOSON_MIN_GEV = 250.0          # Zh and Zγ: each boson's energy within 3.5% of m_χ


def binned(mass_gev: float, channel: str, edges: np.ndarray, data: np.ndarray, samples: int = 16) -> np.ndarray:
    """Photons per annihilation in each energy bin (``edges`` in GeV), for a channel of the mixture rules.

    Besides the PPPC prompt channels: γγ (``gamma``, ``aa_photons``, ``photons``) is two photons at m_χ plus
    PPPC's electroweak continuum below its last x step; Zh is half of ZZ plus half of hh and Zγ half of ZZ plus
    one photon at m_χ − m_Z²/4m_χ, each boson taken at E ≈ m_χ (so only for m_χ ≥ 250 GeV); ``nu`` of
    unspecified flavour is the largest of the three flavours in each bin; ``gg`` is the gluon shower.
    """
    edges = np.asarray(edges, float)
    lo, hi = edges[:-1], edges[1:]
    grid = np.exp(np.linspace(np.log(lo), np.log(hi), samples, axis=1))     # (bins, samples)

    def counts(name: str) -> np.ndarray:
        dnde = prompt(mass_gev, name, grid.ravel(), data).reshape(grid.shape)
        return np.trapezoid(dnde * grid, np.log(grid), axis=1)

    def line(energy: float, number: float) -> np.ndarray:
        return np.where((lo <= energy) & (energy < hi), number, 0.0)

    if channel in ("gamma", "aa_photons", "photons"):
        return _gamma_continuum(mass_gev, grid, data) + line(mass_gev, 2.0)
    if channel in ("Zh", "Zgamma"):
        if mass_gev < TWO_BOSON_MIN_GEV:
            raise SpectrumUnavailable(f"{channel} below {TWO_BOSON_MIN_GEV:g} GeV: the bosons' energies differ")
        if channel == "Zh":
            return 0.5 * counts("Z") + 0.5 * counts("hh")
        return 0.5 * counts("Z") + line(mass_gev - M_Z ** 2 / (4 * mass_gev), 1.0)
    if channel == "nu":
        return np.max([counts(f) for f in ("nu_e", "nu_mu", "nu_tau")], axis=0)
    return counts("g" if channel == "gg" else channel)


def _gamma_continuum(mass_gev: float, grid: np.ndarray, data: np.ndarray) -> np.ndarray:
    """PPPC's γγ electroweak continuum below its last x step, per bin of ``grid``."""
    masses = np.unique(data[:, 0])
    if not masses[0] <= mass_gev <= masses[-1]:
        raise SpectrumUnavailable("Mass outside the PPPC release")
    high = int(np.searchsorted(masses, mass_gev, side="left"))
    low = max(0, high - 1) if masses[high] != mass_gev else high
    a, b = data[data[:, 0] == masses[low]], data[data[:, 0] == masses[high]]
    weight = 0.0 if low == high else math.log(mass_gev / masses[low]) / math.log(masses[high] / masses[low])
    yields = (1 - weight) * a[:, GAMMA_COLUMN] + weight * b[:, GAMMA_COLUMN]
    dnde = np.interp(np.log10(grid / mass_gev), a[:, 1], yields, left=0.0, right=0.0) / (grid * math.log(10.0))
    dnde[grid >= mass_gev * LINE_STEP] = 0.0
    return np.trapezoid(dnde * grid, np.log(grid), axis=1)


def boost(
    rest_energies: np.ndarray,
    rest_dnde: np.ndarray,
    energies: np.ndarray,
    mass_gev: float,
    mediator_mass_gev: float,
) -> np.ndarray:
    """Exact isotropic massless-particle boost of TWO scalar decays into the lab.

    The rest shower already represents the fermion pair of one mediator decay.
    The factor two here represents two mediators, not a second fermion pair.
    """
    if not (
        math.isfinite(mass_gev)
        and math.isfinite(mediator_mass_gev)
        and 0 < mediator_mass_gev <= mass_gev
    ):
        raise SpectrumUnavailable("The scalar pair is not on shell")
    rest_energies, rest_dnde, energies = map(
        lambda x: np.asarray(x, dtype=float), (rest_energies, rest_dnde, energies)
    )
    if (
        rest_energies.ndim != 1
        or rest_energies.shape != rest_dnde.shape
        or len(rest_energies) < 2
        or not np.isfinite(rest_energies).all()
        or not np.isfinite(rest_dnde).all()
        or (rest_energies <= 0).any()
        or (rest_dnde < 0).any()
        or (np.diff(rest_energies) <= 0).any()
        or energies.ndim != 1
        or not np.isfinite(energies).all()
        or (energies <= 0).any()
    ):
        raise ValueError("Invalid rest-frame spectrum or lab energies")
    gamma = mass_gev / mediator_mass_gev
    if not math.isfinite(gamma):
        raise SpectrumUnavailable("The scalar boost exceeds floating-point support")
    beta = math.sqrt(1 - (mediator_mass_gev / mass_gev) ** 2)
    if beta < 1e-10:
        return 2 * np.interp(energies / gamma, rest_energies, rest_dnde, left=0, right=0) / gamma
    primitive = cumulative_trapezoid(rest_dnde / rest_energies, rest_energies, initial=0.0)
    lo = energies / (gamma * (1 + beta))
    hi = energies * gamma * (1 + beta)
    integral = np.interp(hi, rest_energies, primitive, left=0, right=primitive[-1]) - np.interp(
        lo, rest_energies, primitive, left=0, right=primitive[-1]
    )
    return np.maximum(integral, 0.0) / (gamma * beta)


def spectrum(
    request: SpectrumRequest, energies_gev: np.ndarray | None = None, path: Path | None = None
) -> PhotonSpectrum:
    """Combine every requested prompt/cascade branch without discarding unknown channels."""
    data = table(path)
    energies = (
        np.geomspace(request.mass_gev * 1e-8, request.mass_gev, 1601)
        if energies_gev is None
        else np.asarray(energies_gev, float)
    )
    if (
        energies.ndim != 1
        or energies.size < 2
        or not np.isfinite(energies).all()
        or (energies <= 0).any()
        or (np.diff(energies) <= 0).any()
    ):
        raise ValueError("A spectrum needs a positive increasing energy grid")
    total = np.zeros_like(energies)
    for c in request.components:
        if c.mode == "prompt":
            yield_ = prompt(request.mass_gev, c.channel, energies, data)
        elif c.mode == "two_body":
            yield_ = _two_body(request.mass_gev, c.daughters, energies, data)
        else:
            half = c.mediator_mass_gev / 2
            if c.mediator_mass_gev == request.mass_gev:
                yield_ = 2 * sum(
                    d.branching * prompt(half, d.channel, energies, data) for d in c.decays
                )
            else:
                rest = np.geomspace(half * 1e-9, half, 4001)
                yield_ = sum(d.branching * prompt(half, d.channel, rest, data) for d in c.decays)
                yield_ = boost(rest, yield_, energies, request.mass_gev, c.mediator_mass_gev)
        total += c.branching * yield_
    return PhotonSpectrum(
        request=request, energies_gev=energies.tolist(), dnde_per_gev=total.tolist()
    )


def _two_body(mass_gev: float, daughters: list[Daughter], energies: np.ndarray, data: np.ndarray) -> np.ndarray:
    """Photons per annihilation χχ → X Y: each daughter at its energy E = (4m² + m_X² − m_Y²)/4m, a Standard Model
    particle as half its PPPC pair yield at E, a new state's decays at rest (``invisible`` gives none) boosted by
    E/m_X (``boost``, which counts two such states, halved)."""
    (x, y) = daughters
    total = np.zeros_like(energies)
    for d, other in ((x, y), (y, x)):
        energy = (4 * mass_gev ** 2 + d.mass_gev ** 2 - other.mass_gev ** 2) / (4 * mass_gev)
        if d.channel:
            total += 0.5 * prompt(energy, d.channel, energies, data)
            continue
        half = d.mass_gev / 2
        rest = np.geomspace(half * 1e-9, half, 4001)
        at_rest = sum(dec.branching * prompt(half, dec.channel, rest, data) for dec in d.decays
                      if dec.channel != "invisible")
        if not isinstance(at_rest, np.ndarray):
            continue
        total += 0.5 * boost(rest, at_rest, energies, energy, d.mass_gev)
    return total


def scalar_decays(cls: ScalarClass, point: Point) -> list[Decay]:
    """Decay fractions from this model's actual scalar/pseudoscalar fermion couplings."""
    widths = {}
    for f, gs, gp in cls._couplings(point)[1]:
        if point.m_med > 2 * f.mass_gev:
            beta = math.sqrt(1 - 4 * f.mass_gev**2 / point.m_med**2)
            widths[f.name] = (
                f.colours * point.m_med * (gs * gs * beta**3 + gp * gp * beta) / (8 * math.pi)
            )
    total = sum(widths.values())
    if total <= 0:
        raise SpectrumUnavailable("No supported visible mediator decay")
    return [
        Decay(channel=name, branching=value / total) for name, value in widths.items() if value > 0
    ]


def from_rates(
    mass_gev: float, rates: dict[str, float], cls: Any = None, point: Point | None = None
) -> SpectrumRequest:
    """Translate physical partial annihilation rates; unknown decays remain unsupported."""
    total = sum(rates.values())
    if (
        any(not math.isfinite(v) or v < 0 for v in rates.values())
        or not math.isfinite(total)
        or total <= 0
    ):
        raise SpectrumUnavailable("Invalid or zero annihilation rates")
    components = []
    for channel, rate in rates.items():
        if rate <= 0:
            continue
        if channel == "SS" and isinstance(cls, ScalarClass) and point is not None:
            components.append(
                Component(
                    channel=channel,
                    branching=rate / total,
                    mode="scalar_pair",
                    mediator_mass_gev=point.m_med,
                    decays=scalar_decays(cls, point),
                )
            )
        elif channel in COLUMNS:
            components.append(Component(channel=channel, branching=rate / total))
        elif hasattr(cls, "cascade") and point is not None and (found := cls.cascade(channel, point)) is not None:
            components.append(found.model_copy(update={"branching": rate / total}))
        elif channel in LINES:
            raise SpectrumUnavailable(
                f"{channel} has a γ-ray line, which a likelihood read at each bin's reference energy (the 2024 "
                "dwarf release) cannot hold; the 2015 mixture rule counts the line in its bin (binned)")
        else:
            raise SpectrumUnavailable(
                f"No supported photon shower or decay description for {channel}"
            )
    return SpectrumRequest(mass_gev=mass_gev, components=components)
