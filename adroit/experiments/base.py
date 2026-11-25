"""The interface every experiment module implements, and the tools modules share.

A module is one search. Given the physics (particle, interaction, halo,
nuclear input) it predicts the signal in that search's observable
(``expected_signal``), and from its data it sets an upper limit on the
signal strength κ, the factor by which that prediction can be scaled
before it is excluded (``upper_limit``). Since the rate is linear in a
cross-section, a limit on κ is a limit on the cross-section:
σ_limit = κ_up × σ_reference.

Each module also declares the conventions of its collaboration's own
analysis (``conventions``) and the limits it published
(``published_limits``); ``validation.validate`` compares the two.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
from scipy.special import ndtr

from adroit.core.dm_state import (CrossSectionKind, DarkMatterParticle, ExpectedSignal,
                                      ExperimentInfo, HaloModel, InteractionModel, LimitCurve,
                                      ModelLayer, NuclearModel, OperatorCoefficient,
                                      PublishedConventions, Target)
from adroit.external import fetch
from adroit.inference.nuisance import BackgroundRate
from adroit.physics import conventions as cv
from adroit.physics import rates
from adroit.statistics import intervals, optimum_interval

REFERENCE_SIGMA_CM2 = 1e-40      # the cross-section a limit is scaled from


class DataUnavailable(RuntimeError):
    """A module's data have not been fetched."""


class ExperimentModule(ABC):
    """One direct-detection search, exchangeable with any other (build plan, section 5)."""

    @property
    @abstractmethod
    def info(self) -> ExperimentInfo:
        """What the module declares about its search."""

    @abstractmethod
    def target(self) -> Target:
        """The detector target."""

    @abstractmethod
    def conventions(self) -> PublishedConventions:
        """The halo and nuclear input of the collaboration's published analysis."""

    @abstractmethod
    def published_limits(self) -> list[LimitCurve]:
        """The limits the collaboration published, which the module must reproduce."""

    @abstractmethod
    def expected_signal(self, particle: DarkMatterParticle, interaction: InteractionModel,
                        halo: HaloModel, model: NuclearModel,
                        target: Target | None = None) -> ExpectedSignal:
        """The signal the interaction predicts in this search, at unit strength.

        ``target`` replaces the module's target (``published_target``); by
        default the module's own is used.
        """

    def upper_limits(self, signals: list[ExpectedSignal], cl: float = 0.9) -> list[float]:
        """``upper_limit`` for several signals; a module may do them together."""
        return [self.upper_limit(signal, cl) for signal in signals]

    def limits_on(self, kind: CrossSectionKind, masses_gev: list[float],
                  halo: HaloModel | None = None, model: NuclearModel | None = None,
                  cl: float = 0.9, target: Target | None = None) -> list[float]:
        """``limit_on`` at several masses, with the signals handed over together."""
        conventions = self.conventions()
        signals = []
        for mass in masses_gev:
            interaction = reference_interaction(kind, REFERENCE_SIGMA_CM2, mass)
            signals.append(self.expected_signal(DarkMatterParticle(mass_gev=mass), interaction,
                                                halo or conventions.halo,
                                                model or conventions.model_for(kind), target))
        sensitive = [s for s in signals if s.total_events > 0.0]
        kappas = iter(self.upper_limits(sensitive, cl))
        return [REFERENCE_SIGMA_CM2 * next(kappas) if s.total_events > 0.0 else math.inf
                for s in signals]

    def reference_limits(self, kind: CrossSectionKind, masses_gev: list[float],
                         workers: int = 1, cl: float = 0.9) -> list[float]:
        """Cross-section limits by the collaboration's own procedure and conventions (DM5).

        By default ``limits_on`` with the published target; a module whose
        published limit comes from a different procedure (CDMSlite's median
        over realisations) overrides this.
        """
        return self.limits_on(kind, masses_gev, cl=cl, target=self.published_target(kind))

    def published_target(self, kind: CrossSectionKind) -> Target:
        """The target as the collaboration's analysis of ``kind`` treated it.

        By default the natural target. A collaboration that let only some
        isotopes carry spin-dependent scattering overrides this.
        """
        return self.target()

    def validated_range(self, kind: CrossSectionKind) -> tuple[float, float] | None:
        """The masses (GeV) over which this module reproduces its published limit.

        From the last DM3 validation run (``status``); outside it, the
        module's limits are flags, not constraints.
        """
        from adroit.experiments import status
        return status.validated_range(self.info.name, kind)

    @abstractmethod
    def upper_limit(self, signal: ExpectedSignal, cl: float = 0.9) -> float:
        """The largest signal strength κ the data allow at confidence level ``cl``."""

    def limit_on(self, kind: CrossSectionKind, mass_gev: float, halo: HaloModel | None = None,
                 model: NuclearModel | None = None, cl: float = 0.9,
                 target: Target | None = None) -> float:
        """The upper limit on a cross-section per nucleon at one mass, in cm².

        By default under the collaboration's own halo and nuclear input, on
        the natural target; infinite where the search sees no signal at all.
        """
        conventions = self.conventions()
        particle = DarkMatterParticle(mass_gev=mass_gev)
        interaction = reference_interaction(kind, REFERENCE_SIGMA_CM2, mass_gev)
        signal = self.expected_signal(particle, interaction, halo or conventions.halo,
                                      model or conventions.model_for(kind), target)
        if signal.total_events <= 0.0:
            return math.inf
        return REFERENCE_SIGMA_CM2 * self.upper_limit(signal, cl)

    # --- a search with events to explain (Path 2) ----------------------------------------
    # A module whose search shows events that Path 2 should explain supplies the first three;
    # the rest have general defaults. Path 2 takes everything specific to a search from here:
    # no experiment, energy range, coupling convention or model space is built into it.

    def observations(self) -> tuple[np.ndarray, np.ndarray]:
        """(event energies, the resolution σ at each), in keV, for Path 2's signal fit."""
        raise NotImplementedError(f"{self.info.name} provides no event list for a signal fit")

    def signal_grid_kev(self) -> np.ndarray:
        """The energies on which ``expected_signal`` gives its density, for the signal fit."""
        raise NotImplementedError(f"{self.info.name} provides no signal grid")

    def background_on_grid(self) -> np.ndarray:
        """The background density on ``signal_grid_kev``, in events per keV."""
        raise NotImplementedError(f"{self.info.name} provides no background model")

    def background_at(self, energies_kev: np.ndarray) -> np.ndarray:
        """The background density at the given energies (events per keV)."""
        return np.interp(np.asarray(energies_kev, dtype=float), self.signal_grid_kev(),
                         self.background_on_grid())

    def background_rate(self) -> BackgroundRate | None:
        """The background count and its stated relative uncertainty, if the search gives one.

        With one, Path 2 profiles the background's scale θ (``inference.nuisance``);
        by default (None) the background is fixed at ``background_on_grid``.
        """
        return None

    def resolution_on_grid(self) -> np.ndarray:
        """σ(E) on the signal grid, in keV; by default the events' median resolution, constant."""
        _, sigma = self.observations()
        return np.full(self.signal_grid_kev().size, float(np.median(sigma)))

    def candidate_values(self, card_id: str, isospin: str) -> dict[str, float]:
        """A library card's couplings at unit strength, in this search's published convention.

        By default the unit dimensionless coupling 1/m_v², isoscalar ("s") or isovector ("v").
        """
        from adroit.library.interactions import registry
        return registry.isospin_values(card_id, isospin, cv.coupling_gev2(1.0))

    def model_space(self) -> list[dict] | None:
        """The models the collaboration itself fitted, if it published a set: dicts with label,
        card_id, isospin, mass_gev and splitting_kev. None: Path 2 uses the library's own space."""
        return None

    def q_max_gev(self) -> float:
        """The largest momentum transfer the search sees: its heaviest nucleus at its highest energy."""
        heaviest = max(i.mass_number for i in self.target().isotopes)
        return math.sqrt(2.0 * cv.nuclear_mass_gev(heaviest) * self.info.energy_window_kev[1] * cv.KEV)


# --- shared tools --------------------------------------------------------------------


def reference_interaction(kind: CrossSectionKind, sigma_cm2: float,
                          mass_gev: float) -> InteractionModel:
    """The nonrelativistic interaction that gives a cross-section per nucleon of ``sigma_cm2``."""
    if kind is CrossSectionKind.si:
        c = cv.c1_from_sigma_si(sigma_cm2, mass_gev)
        coefficient = OperatorCoefficient(operator=1, proton=c, neutron=c)
    else:
        c = cv.c4_from_sigma_sd(sigma_cm2, mass_gev)
        proton = kind is CrossSectionKind.sd_proton
        coefficient = OperatorCoefficient(operator=4, proton=c if proton else 0.0,
                                          neutron=0.0 if proton else c)
    return InteractionModel(name=f"{kind.value}, σ = {sigma_cm2:.3g} cm²",
                            layer=ModelLayer.nonrelativistic, coefficients=[coefficient])


def element_rates(energies_kev: np.ndarray, particle: DarkMatterParticle,
                  interaction: InteractionModel, target: Target, halo: HaloModel,
                  model: NuclearModel) -> dict[str, np.ndarray]:
    """dR/dE_R per kg of target, per day, per keV, split by element."""
    coefficients = interaction if interaction.depends_on_q else rates.isospin_coefficients(interaction)
    out: dict[str, np.ndarray] = {}
    for isotope in target.isotopes:
        rate = isotope.mass_fraction * rates.isotope_rate(
            energies_kev, particle, coefficients, isotope, halo, model)
        out[isotope.element] = out.get(isotope.element, 0.0) + rate
    return out


def smear(true_kev: np.ndarray, density: np.ndarray, reco_kev: np.ndarray,
          sigma_kev: float) -> np.ndarray:
    """∫ p(E) N(E_reco − E; σ) dE for the piecewise-linear interpolant p of a tabulated density.

    Each segment [E_j, E_j+1], on which p = p_j + s_j (E − E_j), is integrated
    against the Gaussian in closed form, with u = (E − E_reco)/σ:

        (p_j + s_j (E_reco − E_j)) [Φ(u_b) − Φ(u_a)] + s_j σ [φ(u_a) − φ(u_b)] .

    It is exact whatever the grid spacing, including spacings much wider than σ.
    """
    e0, e1 = true_kev[:-1], true_kev[1:]
    p0 = density[:-1]
    slope = np.diff(density) / np.diff(true_kev)
    u_a = (e0[None, :] - reco_kev[:, None]) / sigma_kev
    u_b = (e1[None, :] - reco_kev[:, None]) / sigma_kev
    level = p0[None, :] + slope[None, :] * (reco_kev[:, None] - e0[None, :])
    total = level * (ndtr(u_b) - ndtr(u_a)) + slope[None, :] * sigma_kev * (
        np.exp(-0.5 * u_a ** 2) - np.exp(-0.5 * u_b ** 2)) / math.sqrt(2.0 * math.pi)
    return total.sum(axis=1)


def read_columns(path: Path, columns: int = 2) -> np.ndarray:
    """A table separated by whitespace or commas, skipping lines that begin with '#'."""
    rows = [line.replace(",", " ").split()[:columns] for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")]
    return np.array([[float(x) for x in row] for row in rows if len(row) == columns])


def data_folder(item: str) -> Path:
    """The folder of a fetched manifest item.

    Raises:
        DataUnavailable: if it has not been fetched.
    """
    folder = fetch.locate(item)
    if folder is None:
        raise DataUnavailable(f"fetch the data first: adroit.external.fetch.fetch({item!r})")
    return folder


def standard_halo(v0_km_s: float, v_earth_km_s: float, v_esc_km_s: float,
                  rho_gev_cm3: float = 0.3, label: str = "") -> HaloModel:
    """A Standard Halo Model given by v₀, the detector speed and v_esc (older convention).

    Many collaborations quote the detector's speed through the halo as one
    number; it is placed along the rotation direction, with no separate solar
    or orbital motion.
    """
    return HaloModel(label=label or f"SHM: v0 = {v0_km_s}, v_E = {v_earth_km_s}, "
                                    f"v_esc = {v_esc_km_s} km/s",
                     rho_gev_cm3=rho_gev_cm3, v0_km_s=v0_km_s, v_esc_km_s=v_esc_km_s,
                     v_lsr_km_s=(0.0, v_earth_km_s, 0.0), v_peculiar_km_s=(0.0, 0.0, 0.0),
                     v_earth_km_s=(0.0, 0.0, 0.0))


def interval_limit(events: np.ndarray, signal: ExpectedSignal, cl: float = 0.9) -> float:
    """κ_up from Yellin's optimum interval, treating every event as possible signal.

    Falls back to the maximum gap, which is never stronger, when the optimum
    interval code is not available; the fallback is reported by
    ``interval_method``.
    """
    fractions = intervals.cumulative_fractions(np.asarray(events), np.asarray(signal.observable),
                                               np.asarray(signal.density))
    if optimum_interval.available():
        mu, _flag = optimum_interval.optimum_interval_limit(fractions, cl)
    else:
        mu = intervals.maximum_gap_limit(fractions, cl)
    return mu / signal.total_events


def interval_method() -> str:
    """Which of Yellin's methods ``interval_limit`` uses here."""
    if optimum_interval.available():
        return "optimum interval (Yellin), every event treated as possible signal"
    return "maximum gap (Yellin; the optimum interval code is not available here)"
