"""PICO-60 C₃F₈, complete exposure (arXiv:1902.04031), as the collaboration analysed it.

Two exposures of the same chamber:

| threshold | exposure (kg days) | single-bubble candidates |
|---|---|---|
| 2.45 keV | 1404 | 3 |
| 3.29 keV | 1167 | 0 (arXiv:1702.07666) |

Each has its own fluorine and carbon nucleation efficiencies, digitised from
the vector data of the paper's Fig. 3 (``digitised.load("pico60_2019_fig3")``).
The collaboration combined them in a profile likelihood ratio (Cowan et al.,
arXiv:1007.1727) with each background rate free and non-negative:

    L(κ, b) = Π_i Poisson(n_i | κ μ_i + b_i),   b̂_i = max(0, n_i − κ μ_i) ,

with the 90% limit set on the one-sided statistic. The paper does not say
how its threshold was calibrated; at 0 and 3 events the asymptotic value
(1.64) gives a limit about 2.5 times stronger than the published one, so the
module uses a Neyman construction with toy experiments
(``poisson.free_background_limit``), which reduces to the classical Poisson
limits in one bin. Its efficiency nuisance parameters, fitted to calibration
data, are not public; the module uses the best-fit curves. The published halo is v₀ = 220,
v_E = 232, v_esc = 544 km/s, ρ = 0.3 GeV/cm³, and the nuclear responses are
those of Anand et al., the shell model here.
"""

from __future__ import annotations

from functools import cached_property

import numpy as np

from adroit.core.dm_state import (CrossSectionKind, DarkMatterParticle, ExpectedSignal,
                                      ExperimentInfo, Fidelity, HaloModel, InteractionModel,
                                      LimitCurve, NuclearModel, PublishedConventions, Target)
from adroit.experiments import digitised
from adroit.experiments.base import ExperimentModule, element_rates, standard_halo
from adroit.physics import targets
from adroit.statistics import profile
from adroit.statistics.poisson import free_background_limit

EXPOSURES = (("2.45", 1404.0, 3), ("3.29", 1167.0, 0))     # threshold, kg days, events
GRID_KEV = np.geomspace(2.0, 300.0, 1500)


class Pico60(ExperimentModule):
    """PICO-60 C₃F₈ (2017 and 2019 exposures combined)."""

    name = "PICO-60 C3F8 (2019)"

    @cached_property
    def efficiencies(self) -> dict[str, dict[str, tuple[np.ndarray, np.ndarray]]]:
        """Per threshold and element: (energies in keV, efficiency) of the best-fit curve."""
        figure = digitised.load("pico60_2019_fig3")
        out = {}
        for threshold, _exposure, _events in EXPOSURES:
            panel = figure[f"threshold_{threshold}_keV"]
            out[threshold] = {element: (np.array(panel[f"{element}_best_fit"]["energy_kev"]),
                                        np.array(panel[f"{element}_best_fit"]["efficiency"]))
                              for element in ("F", "C")}
        return out

    @property
    def info(self) -> ExperimentInfo:
        """C₃F₈, the two exposures' total, single-bubble counts and the profile likelihood with toy experiments."""
        return ExperimentInfo(
            name=self.name, target="C3F8",
            exposure_kg_day=sum(exposure for _t, exposure, _n in EXPOSURES),
            energy_window_kev=(2.45, float(GRID_KEV[-1])),
            observables=["single-bubble candidates in each of two exposures"],
            fidelity=Fidelity.B, background_model=False,
            statistical_method="profile likelihood over the two exposures, backgrounds free "
                               "and non-negative; Neyman construction with toy experiments",
            references=["arXiv:1902.04031", "arXiv:1702.07666"])

    def target(self) -> Target:
        """C₃F₈."""
        return targets.target("C3F8")

    def conventions(self) -> PublishedConventions:
        """arXiv:1902.04031, section VI: the Lewin–Smith halo (v0 = 220, v_E = 232, v_esc = 544 km/s) and the
        shell-model responses of Anand et al."""
        return PublishedConventions(
            halo=standard_halo(220.0, 232.0, 544.0), nuclear_model=NuclearModel.shell_model,
            spin_dependent_model=NuclearModel.shell_model,
            note="arXiv:1902.04031, section VI: Lewin-Smith halo; responses of Anand et al.")

    def published_limits(self) -> list[LimitCurve]:
        """PICO's SD-proton limit, digitised from Fig. 7's vector data."""
        curve = digitised.load("pico60_2019_fig6_fig7")["limit_sd_proton"]
        return [LimitCurve(experiment=self.name, kind=CrossSectionKind.sd_proton,
                           masses_gev=curve["mass_gev"], cross_sections_cm2=curve["cross_section_cm2"],
                           source="arXiv:1902.04031, Fig. 7, digitised from its vector data")]

    def expected_signal(self, particle: DarkMatterParticle, interaction: InteractionModel,
                        halo: HaloModel, model: NuclearModel,
                        target: Target | None = None) -> ExpectedSignal:
        """Expected events in each exposure: ``observable`` indexes them, ``density`` counts them."""
        rates = element_rates(GRID_KEV, particle, interaction, target or self.target(), halo, model)
        counts = []
        for threshold, exposure, _events in EXPOSURES:
            total = 0.0
            for element, rate in rates.items():
                energies, efficiency = self.efficiencies[threshold][element]
                accepted = np.interp(GRID_KEV, energies, efficiency, left=0.0, right=1.0) * rate
                total += float(np.trapezoid(accepted, GRID_KEV))
            counts.append(exposure * total)
        return ExpectedSignal(experiment=self.name, interaction_id=interaction.id,
                              particle=particle, total_events=float(sum(counts)),
                              observable=[0.0, 1.0], density=counts)

    def upper_limit(self, signal: ExpectedSignal, cl: float = 0.9) -> float:
        """The limit on the signal's multiplier given each exposure's observed count, with free non-negative
        backgrounds (``free_background_limit``)."""
        observed = [events for _t, _e, events in EXPOSURES]
        return free_background_limit(observed, signal.density, cl)

    def asymptotic_limit(self, signal: ExpectedSignal, cl: float = 0.9) -> float:
        """The same likelihood with the asymptotic threshold (anti-conservative here; for comparison)."""
        return profile.upper_limit(self.profiled_nll(signal), scale=3.0 / signal.total_events, cl=cl)

    @staticmethod
    def profiled_nll(signal: ExpectedSignal):
        """−ln L(κ) with each exposure's background at its best non-negative value."""
        expected = np.array(signal.density)
        observed = np.array([events for _t, _e, events in EXPOSURES], dtype=float)

        def nll(kappa: float) -> float:
            signal_counts = kappa * expected
            background = np.maximum(0.0, observed - signal_counts)
            mean = signal_counts + background
            with np.errstate(divide="ignore", invalid="ignore"):
                terms = np.where(observed > 0, observed * np.log(mean), 0.0) - mean
            return float(-np.sum(terms))

        return nll
