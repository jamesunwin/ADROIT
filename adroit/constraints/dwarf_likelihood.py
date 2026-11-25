"""McDaniel et al. (2024) benchmark dwarf SED recast for arbitrary photon spectra.

The author's reference-energy, index-two bin templates are retained. This is
not an event-level likelihood or a recalibration using the blank-field sample.
No flux, mass or J-factor extrapolation is used to produce an upper limit.
"""

from __future__ import annotations

import csv
from functools import lru_cache
import math
from pathlib import Path

import numpy as np
from astropy.io import fits
from pydantic import Field, model_validator
from scipy.optimize import brentq, minimize_scalar

from adroit.constraints.spectra import PhotonSpectrum, SpectrumUnavailable
from adroit.core.state import StrictModel
from adroit.external.fetch import locate

RECORD = "fermi-2311.04982-spectral"
ITEM = "McDaniel dwarf likelihoods"
SOURCE = "McDaniel et al., PRD 109, 063024 (2024), arXiv:2311.04982, Figshare 24058650"
BENCHMARK = (
    "Aquarius_2",
    "Bootes_2",
    "Canes_V1",
    "Canes_V2",
    "Carina",
    "Carina_2",
    "Carina_3",
    "Berenices",
    "Draco",
    "Eridanus_2",
    "Fornax",
    "Hercules",
    "Horologium_1",
    "Hydrus_1",
    "Leo_1",
    "Leo_2",
    "Leo_4",
    "Leo_5",
    "Pegasus_3",
    "Phoenix_2",
    "Pisces_2",
    "Reticulum_2",
    "Sagittarius_2",
    "Segue_1",
    "Sextans",
    "Tucana_2",
    "Tucana_4",
    "Ursa_Major_1",
    "Ursa_Major_2",
    "Ursa_Minor",
    "Bootes_4",
    "Centaurus_1",
    "Cetus_2",
    "Cetus_3",
    "Columba_1",
    "Draco_2",
    "Grus_1",
    "Grus_2",
    "Pictor_1",
    "Pictor_2",
    "Reticulum_3",
    "Tucana_5",
)


class DwarfSED(StrictModel):
    """Source differential-flux scans in GeV, cm and seconds, and log10 J prior."""

    name: str
    log10_j: float = Field(allow_inf_nan=False)
    sigma_log10_j: float = Field(gt=0, allow_inf_nan=False)
    energies_gev: list[float]
    flux_per_gev: list[list[float]]
    loglike: list[list[float]]

    @model_validator(mode="after")
    def _valid(self) -> DwarfSED:
        e, f, ll = map(np.asarray, (self.energies_gev, self.flux_per_gev, self.loglike))
        if (
            e.ndim != 1
            or len(e) < 1
            or not np.isfinite(e).all()
            or (e <= 0).any()
            or (np.diff(e) <= 0).any()
            or f.ndim != 2
            or f.shape != ll.shape
            or f.shape[0] != len(e)
            or f.shape[1] < 2
            or not np.isfinite(f).all()
            or not np.isfinite(ll).all()
            or (f[:, 0] != 0).any()
            or (np.diff(f, axis=1) <= 0).any()
        ):
            raise ValueError("Incomplete or invalid dwarf likelihood scan")
        return self


class SpectralLimit(StrictModel):
    """A one-sided profiled 95% upper limit for the supplied photon spectrum."""

    upper95_cm3_s: float
    best_fit_cm3_s: float
    confidence_level: float = 0.95
    threshold: float = 2.71
    source: str = SOURCE
    dwarfs: int
    self_conjugate: bool
    density_fraction: float
    assumptions: list[str] = Field(
        default_factory=lambda: [
            "42-dwarf benchmark, standard point-source SED likelihoods, 0.5 GeV–1 TeV",
            "index-two bin templates evaluated at reference energies, as in the author example",
            "independent Gaussian priors in log10 J, profiled within eight sigma",
            "one-sided upper branch with 2Δlog L = 2.71; mass and spectrum fixed",
            "observed limit; no blank-field discovery-significance calibration",
        ]
    )


def load(folder: Path | None = None) -> tuple[DwarfSED, ...]:
    """Load every benchmark dwarf or refuse an incomplete source installation."""
    if folder is None:
        folder = locate(ITEM)
    if folder is None:
        raise SpectrumUnavailable("McDaniel dwarf likelihoods are not installed")
    paths = [
        folder / "dSphs.csv",
        *[folder / "dSphs" / "SEDs" / f"{name}_sed.fits" for name in BENCHMARK],
    ]
    try:
        signature = tuple(
            (str(p.resolve()), p.stat().st_size, p.stat().st_mtime_ns, p.stat().st_ctime_ns)
            for p in paths
        )
        return tuple(row.model_copy(deep=True) for row in _load(signature))
    except (OSError, ValueError, KeyError) as error:
        raise SpectrumUnavailable(f"Incomplete dwarf source data: {error}") from error


@lru_cache(maxsize=2)
def _load(signature: tuple) -> tuple[DwarfSED, ...]:
    with Path(signature[0][0]).open() as stream:
        rows = {r["name"]: r for r in csv.DictReader(stream)}
    result = []
    for name, entry in zip(BENCHMARK, signature[1:], strict=True):
        with fits.open(entry[0], memmap=False) as hdus:
            data = hdus["SED"].data
            if len(data) != 26 or hdus["SED"].columns["e_ref"].unit != "MeV":
                raise ValueError(f"Unexpected SED schema for {name}")
            if hdus["SED"].columns["ref_dnde"].unit != "cm-2 MeV-1 ph s-1":
                raise ValueError(f"Unexpected flux units for {name}")
            result.append(
                DwarfSED(
                    name=name,
                    log10_j=float(rows[name]["log10_J"]),
                    sigma_log10_j=float(rows[name]["J_sigma"]),
                    energies_gev=(data["e_ref"] / 1000).tolist(),
                    flux_per_gev=(data["norm_scan"] * data["ref_dnde"][:, None] * 1000).tolist(),
                    loglike=data["dloglike_scan"].tolist(),
                )
            )
    return tuple(result)


def profile(dwarf: DwarfSED, flux_at_j: np.ndarray, sigma_v: float) -> float:
    """Profile one dwarf's J prior, with no Jacobian depending on trial J.

    Gaussian log10 J likelihood normalisation uses the observed J (paper eq.7).
    A global grid locates sampled maxima; local refinement evaluates the
    actual piecewise-linear source likelihood.
    """
    flux, ll = np.asarray(dwarf.flux_per_gev), np.asarray(dwarf.loglike)
    base = np.asarray(flux_at_j) * sigma_v
    if not math.isfinite(sigma_v) or sigma_v < 0 or base.shape != (len(flux),):
        raise ValueError("Invalid annihilation flux")
    if not np.isfinite(base).all() or (base < 0).any():
        raise ValueError("Invalid annihilation flux")
    if not base.any():
        return float(ll[:, 0].sum())
    spread = dwarf.sigma_log10_j
    low = -8 * spread
    upper_flux = float(np.log10(np.min(flux[base > 0, -1] / base[base > 0])))
    high = min(8 * spread, upper_flux)
    if high <= low:
        raise SpectrumUnavailable("Flux exceeds the source scan throughout the bounded J prior")

    def values(z: np.ndarray) -> np.ndarray:
        trial = base[:, None] * 10 ** z[None, :]
        return (
            sum(np.interp(t, f, likelihood) for t, f, likelihood in zip(trial, flux, ll, strict=True))
            - 0.5 * (z / spread) ** 2
        )

    grid = np.unique(np.r_[np.linspace(low, high, 65), np.clip(0.0, low, high)])
    scores = values(grid)
    candidates = [(float(scores[i]), float(grid[i])) for i in (0, len(grid) - 1)]
    for i in range(1, len(grid) - 1):
        if scores[i] >= scores[i - 1] and scores[i] >= scores[i + 1]:
            fit = minimize_scalar(
                lambda z: -values(np.array([z]))[0],
                bounds=(grid[i - 1], grid[i + 1]),
                method="bounded",
                options={"xatol": 1e-8},
            )
            candidates.append((-float(fit.fun), float(fit.x)))
    value, z = max(candidates)
    if z <= low + 1e-6 or z >= high - 1e-6:
        raise SpectrumUnavailable("J-profile maximum meets the prior or source-flux boundary")
    return value


def flux_factors(
    photons: PhotonSpectrum,
    dwarfs: tuple[DwarfSED, ...],
    self_conjugate: bool = True,
    density_fraction: float = 1.0,
) -> list[np.ndarray]:
    """dΦ/dE per unit σv at each source reference energy and observed J."""
    if not math.isfinite(density_fraction) or not 0 < density_fraction <= 1:
        raise ValueError("Density fraction must be in (0,1]")
    energy, yield_ = np.asarray(photons.energies_gev), np.asarray(photons.dnde_per_gev)
    if (
        energy.ndim != 1
        or energy.shape != yield_.shape
        or len(energy) < 2
        or not np.isfinite(energy).all()
        or not np.isfinite(yield_).all()
        or (energy <= 0).any()
        or (yield_ < 0).any()
        or (np.diff(energy) <= 0).any()
    ):
        raise ValueError("Invalid supplied photon spectrum")
    factor = (
        (1 if self_conjugate else 0.5)
        * density_fraction**2
        / (8 * math.pi * photons.request.mass_gev**2)
    )
    # The released example uses log-log interpolation of differential yields.
    logs = np.log(np.maximum(yield_, 1e-300))
    result = []
    for row in dwarfs:
        e = np.asarray(row.energies_gev)
        dnde = np.exp(np.interp(np.log(e), np.log(energy), logs))
        dnde[np.interp(e, energy, yield_) == 0] = 0.0
        dnde[(e < energy[0]) | (e >= photons.request.mass_gev) | (e > energy[-1])] = 0.0
        result.append(dnde * factor * 10**row.log10_j)
    return result


def _maxima(grid: np.ndarray, scores: np.ndarray, sampled, zero: float) -> list[tuple[float, float]]:
    """(log L, σv) at σv = 0 and at each local maximum of the sampled log-likelihood, refined between its
    neighbours (``upper_limit``)."""
    candidates = [(zero, 0.0)]
    for i in range(1, len(grid) - 1):
        if np.isfinite(scores[i]) and scores[i] >= scores[i - 1] and scores[i] >= scores[i + 1]:
            fit = minimize_scalar(
                lambda x: -sampled(x),
                bounds=(grid[i - 1], grid[i + 1]),
                method="bounded",
                options={"xatol": 1e-6},
            )
            candidates.append((-float(fit.fun), 10 ** float(fit.x)))
    return candidates


def upper_limit(
    photons: PhotonSpectrum,
    dwarfs: tuple[DwarfSED, ...] | None = None,
    self_conjugate: bool = True,
    density_fraction: float = 1.0,
) -> SpectralLimit:
    """Profile σv≥0 and obtain the upper branch, refusing missing table support."""
    dwarfs = load() if dwarfs is None else dwarfs
    if not dwarfs:
        raise SpectrumUnavailable("No dwarf likelihoods supplied")
    factors = flux_factors(photons, dwarfs, self_conjugate, density_fraction)
    if not any(a.any() for a in factors):
        raise SpectrumUnavailable("No photons within the source energy range")

    def loglike(rate: float) -> float:
        return sum(profile(row, flux, rate) for row, flux in zip(dwarfs, factors, strict=True))

    def sampled(x: float) -> float:
        try:
            return loglike(10**x)
        except SpectrumUnavailable:
            return -math.inf

    zero = loglike(0.0)
    # Bracket amplitude using the supplied flux scans rather than a fixed σv range.
    scale = min(
        float(np.min(np.asarray(r.flux_per_gev)[f > 0, -1] / f[f > 0]))
        for r, f in zip(dwarfs, factors, strict=True)
        if (f > 0).any()
    )
    center = math.log10(scale)
    grid = np.linspace(center - 8, center + 3, 45)
    scores = np.array([sampled(x) for x in grid])
    best, rate = max(_maxima(grid, scores, sampled, zero))
    target = best - 2.71 / 2
    above = [
        (x, score)
        for x, score in zip(grid, scores, strict=True)
        if 10**x > rate and np.isfinite(score) and score <= target
    ]
    if not above:
        raise SpectrumUnavailable("No supported 95% upper crossing in the source flux scans")
    high = above[0][0]
    low = math.log10(rate) if rate > 0 else grid[0]
    root = brentq(lambda x: loglike(10**x) - target, low, high, xtol=1e-6)
    return SpectralLimit(
        upper95_cm3_s=10**root,
        best_fit_cm3_s=rate,
        dwarfs=len(dwarfs),
        self_conjugate=self_conjugate,
        density_fraction=density_fraction,
    )
