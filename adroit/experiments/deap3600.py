"""DEAP-3600, 231 live days (arXiv:1902.04048): liquid argon, pulse-shape discrimination.

758 tonne days of exposure (3279 kg of argon), no events in the region of
interest of 95–200 detected photoelectrons (PE), and a Poisson limit at 90%.
The WIMP acceptance against PE, and the recoil-energy scale of its top axis,
are digitised from the vector data of the paper's Fig. 21
(``digitised.load("deap3600_2019_fig21")``). The total acceptance is the
product of the fiducial acceptance (about 25% of the argon) and that of the
pulse-shape and background-rejection cuts combined.

The photoelectron yield of a recoil is smeared with the resolution of the
paper's Table I, σ² = 1.4 PE × μ + 0.0004 μ². The collaboration folded its
systematic uncertainties into the limit by the prescription of Cousins and
Highland; the module does the same with those it can quantify: the light
yield, (6.1 ± 0.4) PE/keVee (Table I), propagated to the expected signal by
rescaling the photoelectron scale, and the 2.9% exposure uncertainty. The
uncertainties of the quenching and of the acceptance curves are not
published in usable form and are left out. The published halo is
v₀ = 220 km/s, v_esc = 544 km/s, ρ = 0.3 GeV/cm³ (McCabe's model, whose
mean detector speed is about 232 km/s, the value used here).
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
from adroit.statistics.poisson import cousins_highland_limit

EXPOSURE_KG_DAY = 758_000.0
ROI_PE = (95.0, 200.0)
OBSERVED = 0
LIGHT_YIELD_RELATIVE = 0.4 / 6.1       # Table I: (6.1 ± 0.4) PE/keVee
EXPOSURE_RELATIVE = 0.029


def resolution_pe(mean_pe: np.ndarray) -> np.ndarray:
    """The width of the detected-PE distribution for a given mean (Table I)."""
    return np.sqrt(1.4 * mean_pe + 0.0004 * mean_pe ** 2)


class Deap3600(ExperimentModule):
    """DEAP-3600, first-year search (2019)."""

    name = "DEAP-3600 (2019)"

    @cached_property
    def figure(self) -> dict:
        """The digitised vector data of the paper's Fig. 21: the acceptance curves and the energy axis."""
        return digitised.load("deap3600_2019_fig21")

    @cached_property
    def energy_scale(self) -> tuple[float, float]:
        """(PE per keVnr, offset): the straight line through the top axis's ticks."""
        axis = self.figure["energy_axis"]
        slope, offset = np.polyfit(axis["energy_kevnr"], axis["photoelectrons"], 1)
        return float(slope), float(offset)

    def acceptance(self, photoelectrons: np.ndarray) -> np.ndarray:
        """The total WIMP acceptance (a fraction) at each PE."""
        curves = self.figure["curves"]
        fiducial = np.interp(photoelectrons, curves["fiducial"]["photoelectrons"],
                             curves["fiducial"]["acceptance_percent"])
        cuts = np.interp(photoelectrons, curves["fprompt_and_background_rejection"]["photoelectrons"],
                         curves["fprompt_and_background_rejection"]["acceptance_percent"])
        return np.clip(fiducial, 0.0, 100.0) * np.clip(cuts, 0.0, 100.0) / 1e4

    @property
    def info(self) -> ExperimentInfo:
        """Argon, 758 tonne days; the window is the 95–200 PE region of interest in keVnr (``energy_scale``), with no
        events and a Cousins-Highland Poisson limit."""
        slope, offset = self.energy_scale
        window = tuple(float((pe - offset) / slope) for pe in ROI_PE)
        return ExperimentInfo(
            name=self.name, target="Ar", exposure_kg_day=EXPOSURE_KG_DAY,
            energy_window_kev=window, observables=["detected photoelectrons"],
            fidelity=Fidelity.B, background_model=False,
            statistical_method="Poisson limit with systematic uncertainties folded in "
                               "(Cousins-Highland), no events observed",
            references=["arXiv:1902.04048"])

    def target(self) -> Target:
        """Natural argon."""
        return targets.target("Ar")

    def conventions(self) -> PublishedConventions:
        """The paper's halo (v₀ = 220 km/s, v_esc = 544 km/s, ρ = 0.3 GeV/cm³) with an assumed detector speed of 232
        km/s, and the Helm form factor."""
        return PublishedConventions(
            halo=standard_halo(220.0, 232.0, 544.0), nuclear_model=NuclearModel.helm,
            note="arXiv:1902.04048, section VIII: v0 = 220, v_esc = 544 km/s, ρ = 0.3 GeV/cm³; "
                 "the detector speed of 232 km/s is assumed; Helm form factor")

    def published_limits(self) -> list[LimitCurve]:
        """The SI limit of the paper's Fig. 24, digitised from its vector data."""
        curve = digitised.load("deap3600_2019_fig24")["deap3600_this_work"]
        return [LimitCurve(experiment=self.name, kind=CrossSectionKind.si,
                           masses_gev=curve["mass_gev"], cross_sections_cm2=curve["cross_section_cm2"],
                           source="arXiv:1902.04048, Fig. 24, digitised from its vector data")]

    def _events(self, particle: DarkMatterParticle, interaction: InteractionModel,
                halo: HaloModel, model: NuclearModel, target: Target,
                light_yield: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
        """(reconstructed PE, events per PE) with the resolution and a scaled light yield."""
        slope, offset = self.energy_scale
        true_pe = np.linspace(40.0, 300.0, 1041)
        energies = (true_pe / light_yield - offset) / slope
        keep = energies > 1.0
        rate = np.zeros_like(true_pe)
        rate[keep] = sum(element_rates(energies[keep], particle, interaction, target,
                                       halo, model).values())
        per_pe = rate / (slope * light_yield)                      # events/(kg day PE), true PE
        reco = np.linspace(*ROI_PE, 421)
        width = resolution_pe(true_pe)
        kernel = np.exp(-0.5 * ((reco[:, None] - true_pe[None, :]) / width[None, :]) ** 2)
        kernel /= width[None, :] * np.sqrt(2.0 * np.pi)
        smeared = kernel @ (per_pe * np.gradient(true_pe))
        return reco, EXPOSURE_KG_DAY * self.acceptance(reco) * smeared

    def expected_signal(self, particle: DarkMatterParticle, interaction: InteractionModel,
                        halo: HaloModel, model: NuclearModel,
                        target: Target | None = None) -> ExpectedSignal:
        """Events per PE over the region of interest, with the relative uncertainties of the light yield (by
        rescaling the PE scale) and the exposure (2.9%) combined in quadrature."""
        target = target or self.target()
        pe, density = self._events(particle, interaction, halo, model, target)
        total = float(np.trapezoid(density, pe))
        shifted = [float(np.trapezoid(self._events(particle, interaction, halo, model, target,
                                                   1.0 + sign * LIGHT_YIELD_RELATIVE)[1], pe))
                   for sign in (1.0, -1.0)]
        light_yield_effect = abs(shifted[0] - shifted[1]) / (2.0 * total) if total > 0 else 0.0
        return ExpectedSignal(experiment=self.name, interaction_id=interaction.id,
                              particle=particle, total_events=total, observable=pe.tolist(),
                              density=density.tolist(), energy_scale="reconstructed",
                              relative_uncertainty=float(np.hypot(light_yield_effect,
                                                                  EXPOSURE_RELATIVE)))

    def upper_limit(self, signal: ExpectedSignal, cl: float = 0.9) -> float:
        """κ_up: the Cousins-Highland Poisson limit for no observed events, over the expected total."""
        return cousins_highland_limit(OBSERVED, signal.relative_uncertainty, cl) / signal.total_events
