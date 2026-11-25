"""Historical searches with events, built from their papers (DM10's historical-excess suite).

Each search is one record in ``data/historical/``: the target, the exposure, the
window, the event energies, the background the collaboration expected, the
efficiency (digitised from a figure, or the points the paper's text gives),
the halo, and the numbers the paper quotes that the module must reproduce
(``quoted``). One class serves every record, so a further search is a further
file, not further code.

The model of a search, for a recoil spectrum dR/dE (per kg, day, keV):

    dN/dE = exposure × ε(E) × dR/dE ,   E in the window,

with the events as the paper lists them, a Gaussian resolution of one width,
and the paper's expected background count, spread in E by the shape the paper
gives (counts in energy bins, ``background_shape``) or else flat (each record
says what this misses). Limits are Yellin's
optimum interval with every event treated as possible signal, as in the papers.
"""

from __future__ import annotations

import math
from functools import cached_property, lru_cache
from importlib import resources

import numpy as np
import yaml

from adroit.core.dm_state import (CrossSectionKind, DarkMatterParticle, DataKind, DataSet,
                                      ExpectedSignal, ExperimentInfo, Fidelity, HaloModel,
                                      InteractionModel, LimitCurve, NuclearModel,
                                      PublishedConventions, Target)
from adroit.experiments import digitised
from adroit.inference.nuisance import BackgroundRate
from adroit.experiments.base import (REFERENCE_SIGMA_CM2, ExperimentModule, element_rates,
                                         interval_limit, interval_method, reference_interaction,
                                         standard_halo)
from adroit.physics import targets

GRID_POINTS = 800


@lru_cache(maxsize=None)
def record(key: str) -> dict:
    """One search's record, e.g. ``"cdms_ii_si_2013"``."""
    text = resources.files("adroit.experiments").joinpath(f"data/historical/{key}.yaml").read_text()
    return yaml.safe_load(text)


def records() -> list[str]:
    """The keys of every historical record."""
    folder = resources.files("adroit.experiments").joinpath("data/historical")
    return sorted(p.name.removesuffix(".yaml") for p in folder.iterdir() if p.name.endswith(".yaml"))


def shape_on_grid(edges, counts, total: float, window: tuple[float, float] | list[float],
                  grid: np.ndarray) -> np.ndarray:
    """A background of ``total`` expected events in ``window`` (keV), spread by a histogram's shape (``counts`` in
    the bins with ``edges``), as a density (events per keV) on ``grid``: each bin's counts spread evenly over its width,
    the shape restricted to the window, and scaled so that its exact integral over the window is ``total``.

    One rule for every record, inline or digitised (the auditor's bounded-interfaces audit, BI-01, 2026-11-12). Before, a
    digitised shape had been scaled by its count over every bin, and an inline one by its integral on ``grid`` over the
    window: with bins wider than the window the two had put 4 and 8 events in it for one record's 8, and a uniform
    signal's fitted count had been 6 and 2. A shape whose bins lie in the window (CDMS II Si's: 7–20, 20–30 and
    30–100 keV over 7–100 keV) is spread as before, bit for bit. The module's grid integral (``background_rate``)
    reproduces ``total`` up to the smoothing of the shape's steps on the grid (0.11% for CDMS II Si, as before). The
    window's top is read within the window: a bin that begins there is outside it.

    Raises:
        ValueError: the bins do not cover the window, or put nothing in it.
    """
    edges, counts = np.asarray(edges, float), np.asarray(counts, float)
    low, high = float(window[0]), float(window[1])
    if edges.size != counts.size + 1 or edges[0] > low or edges[-1] < high:
        raise ValueError(f"the background shape's bins ({edges[0]:g}-{edges[-1]:g} keV) do not cover the window "
                         f"{low:g}-{high:g} keV")
    width = np.diff(edges)
    overlap = np.clip(np.minimum(edges[1:], high) - np.maximum(edges[:-1], low), 0.0, None)
    inside = float(np.sum(counts * (overlap / width)))          # the shape's count in the window: Σ counts where inside
    if not inside > 0:
        raise ValueError(f"the background shape puts nothing in the window {low:g}-{high:g} keV")
    density = total * counts / inside / width
    at = np.minimum(np.asarray(grid, float), np.nextafter(high, low))     # the window's top read within it
    index = np.clip(np.searchsorted(edges, at, side="right") - 1, 0, len(counts) - 1)
    return density[index]


class HistoricalSearch(ExperimentModule):
    """A search reported in a paper with its events, from its record."""

    def __init__(self, key: str, data: dict | None = None) -> None:
        self.key = key
        self.record = data if data is not None else record(key)
        self.name = self.record["name"]

    @property
    def info(self) -> ExperimentInfo:
        """The search as its record gives it: target, exposure, window, event data and references; fidelity B,
        Yellin's interval method."""
        r = self.record
        return ExperimentInfo(
            name=self.name, target=r["target"], exposure_kg_day=r["exposure_kg_day"],
            energy_window_kev=tuple(r["window_kev"]), observables=["nuclear-recoil energy (keVnr)"],
            fidelity=Fidelity.B, statistical_method=interval_method(),
            data=[DataSet(experiment=self.name, kind=DataKind.events,
                          path=f"adroit/experiments/data/historical/{self.key}.yaml",
                          source=", ".join(r["references"]), note="event energies as the paper lists them")],
            references=list(r["references"]),
            validation_note="checked against the numbers the paper quotes (``quoted``)")

    def target(self) -> Target:
        """The record's target material."""
        return targets.target(self.record["target"])

    def conventions(self) -> PublishedConventions:
        """The paper's halo (a Standard Halo Model from the record's v₀, detector speed, v_esc and ρ) and the Helm
        form factor."""
        h = self.record["halo"]
        return PublishedConventions(
            halo=standard_halo(h["v0_km_s"], h["v_earth_km_s"], h["v_esc_km_s"], h["rho_gev_cm3"]),
            nuclear_model=NuclearModel.helm,
            note=self.record.get("halo_note", "the paper's halo") + "; Helm form factor")

    def published_limits(self) -> list[LimitCurve]:
        """None as curves: the paper's quoted points are checked instead (``quoted_checks``)."""
        return []

    @cached_property
    def grid(self) -> np.ndarray:
        """Recoil energies spanning the window."""
        low, high = self.record["window_kev"]
        return np.linspace(low, high, GRID_POINTS)

    @cached_property
    def efficiency(self) -> np.ndarray:
        """ε(E) on ``grid``: a digitised figure, or the paper's points joined linearly."""
        spec = self.record["efficiency"]
        table = digitised.load(spec["digitised"]) if "digitised" in spec else spec["points"]
        return np.interp(self.grid, table["recoil_energy_kev"], table["efficiency"], left=0.0, right=0.0)

    @cached_property
    def events(self) -> np.ndarray:
        """The event energies (keV), sorted."""
        return np.sort(np.asarray(self.record["events_kev"], dtype=float))

    def expected_signal(self, particle: DarkMatterParticle, interaction: InteractionModel,
                        halo: HaloModel, model: NuclearModel,
                        target: Target | None = None) -> ExpectedSignal:
        """dN/dE = exposure × ε(E) × dR/dE on ``grid``, summed over the target's elements."""
        rate = sum(element_rates(self.grid, particle, interaction, target or self.target(),
                                 halo, model).values())
        density = self.record["exposure_kg_day"] * self.efficiency * rate
        return ExpectedSignal(experiment=self.name, interaction_id=interaction.id, particle=particle,
                              total_events=float(np.trapezoid(density, self.grid)),
                              observable=self.grid.tolist(), density=density.tolist())

    def upper_limit(self, signal: ExpectedSignal, cl: float = 0.9) -> float:
        """κ_up by Yellin's optimum interval over the record's events (``interval_limit``)."""
        return interval_limit(self.events, signal, cl)

    def observations(self) -> tuple[np.ndarray, np.ndarray]:
        """The event energies, each with the record's single resolution width (keV)."""
        return self.events, np.full(self.events.size, float(self.record["resolution_kev"]))

    def signal_grid_kev(self) -> np.ndarray:
        """``grid``: the recoil energies spanning the window."""
        return self.grid

    def background_on_grid(self) -> np.ndarray:
        """The expected background spread by the record's shape (counts in energy bins), else flat."""
        total = self.record["background_events"]
        spec = self.record.get("background_shape")
        if spec is None:
            low, high = self.record["window_kev"]
            return np.full(self.grid.size, total / (high - low))
        table = digitised.load(spec["digitised"])
        return shape_on_grid(table["edges_kev"], table[spec["counts"]], total, self.record["window_kev"], self.grid)

    def background_rate(self) -> BackgroundRate | None:
        """The record's background count with its uncertainties, combined in quadrature."""
        spec = self.record.get("background_uncertainty")
        if spec is None:
            return None
        total = self.record["background_events"]
        minus, plus = (math.sqrt(sum(x * x for x in spec[side])) / total for side in ("minus", "plus"))
        return BackgroundRate(total=float(np.trapezoid(self.background_on_grid(), self.grid)),
                              minus=minus, plus=plus)

    def equivalent_exposure(self, mass_gev: float) -> float:
        """The exposure weighted by ε over the window, for a spin-independent spectrum (kg day)."""
        conventions = self.conventions()
        interaction = reference_interaction(CrossSectionKind.si, REFERENCE_SIGMA_CM2, mass_gev)
        rate = sum(element_rates(self.grid, DarkMatterParticle(mass_gev=mass_gev), interaction,
                                 self.target(), conventions.halo, conventions.nuclear_model).values())
        weighted = np.trapezoid(self.efficiency * rate, self.grid) / np.trapezoid(rate, self.grid)
        return float(self.record["exposure_kg_day"] * weighted)

    def quoted_checks(self) -> list[dict]:
        """Each number the paper quotes beside the module's value: quantity, mass, paper, ours, ratio."""
        out = []
        for q in self.record["quoted"]:
            if q["quantity"] == "si_limit_cm2":
                ours = self.limit_on(CrossSectionKind.si, q["mass_gev"])
            elif q["quantity"] == "equivalent_exposure_kg_day":
                ours = self.equivalent_exposure(q["mass_gev"])
            else:
                raise ValueError(f"unknown quoted quantity {q['quantity']!r}")
            out.append({"quantity": q["quantity"], "mass_gev": q["mass_gev"], "paper": q["value"],
                        "ours": ours, "ratio": ours / q["value"]})
        return out
