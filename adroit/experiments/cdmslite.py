"""CDMSlite Run 2: germanium at 70 V bias (arXiv:1509.02448, 1707.01632).

The collaboration's release gives the 318 event energies and the signal
efficiency in electron-equivalent energy (keVee), the exposure (70.10 kg
days) and the published limits. The detector measures the recoil energy
plus the Neganov–Trofimov–Luke phonons of the ionisation it creates, so a
nuclear recoil of energy E_nr reads as

    E_ee = E_nr (1 + Y(E_nr) eV_b/ε) / (1 + eV_b/ε),   eV_b/ε = 70 V / 3 eV ,

with the Lindhard yield Y = k g(ε)/(1 + k g(ε)), g = 3ε^0.15 + 0.7ε^0.6 + ε,
ε = 11.5 E_nr(keV) Z^(−7/3), and k = 0.157 for the "best-fit" limit of the
release. Events and efficiency are converted to nuclear-recoil energy
between 56 eVee and 2 keVee, and the limit is Yellin's optimum interval
(release, section 3). The release's halo is v₀ = 220 km/s, v_E = 232 km/s,
v_esc = 544 km/s with the Helm form factor.

The published ("official") limit is instead the median over realisations
of the analysis, each with an efficiency curve drawn from the release's
1000 samples and k drawn uniformly from [0.1, 0.2] (``official_limit``).
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from functools import cached_property, lru_cache
from itertools import repeat

import numpy as np
from scipy.optimize import brentq

from adroit.core.dm_state import (CrossSectionKind, DarkMatterParticle, DataKind, DataSet,
                                      ExpectedSignal, ExperimentInfo, Fidelity, HaloModel,
                                      InteractionModel, LimitCurve, NuclearModel,
                                      PublishedConventions, Target)
from adroit.experiments.base import (REFERENCE_SIGMA_CM2, ExperimentModule, data_folder,
                                         element_rates, interval_limit, interval_method,
                                         read_columns, reference_interaction, standard_halo)
from adroit.physics import targets

ITEM = "CDMSlite Run 2 data release (arXiv:1707.01632)"
EXPOSURE_KG_DAY = 70.10
WINDOW_KEVEE = (0.056, 2.0)
BIAS_OVER_EPSILON = 70.0 / 3.0         # eV_b / ε_γ
LINDHARD_K = 0.157
K_RANGE = (0.1, 0.2)                   # the official analysis samples k uniformly here
GERMANIUM_Z = 32


def lindhard_yield(recoil_kev: np.ndarray, k: float = LINDHARD_K, z: int = GERMANIUM_Z) -> np.ndarray:
    """The Lindhard ionisation yield of a nuclear recoil (release, Eq. 2)."""
    eps = 11.5 * np.asarray(recoil_kev, dtype=float) * z ** (-7.0 / 3.0)
    g = 3.0 * eps ** 0.15 + 0.7 * eps ** 0.6 + eps
    return k * g / (1.0 + k * g)


def electron_equivalent(recoil_kev: np.ndarray, k: float = LINDHARD_K) -> np.ndarray:
    """E_ee of a nuclear recoil of energy E_nr (release, Eq. 3)."""
    e = np.asarray(recoil_kev, dtype=float)
    return e * (1.0 + lindhard_yield(e, k) * BIAS_OVER_EPSILON) / (1.0 + BIAS_OVER_EPSILON)


def nuclear_recoil(energy_kevee: float, k: float = LINDHARD_K) -> float:
    """E_nr giving a measured E_ee: the inverse of ``electron_equivalent``."""
    return float(brentq(lambda e: float(electron_equivalent(e, k)) - energy_kevee,
                        1e-9, 50.0 * energy_kevee + 1.0, xtol=1e-14, rtol=1e-12))


class CdmsliteRun2(ExperimentModule):
    """CDMSlite Run 2 (2016 and 2018 analyses of the same data)."""

    name = "CDMSlite Run 2"

    def __init__(self) -> None:
        self.folder = data_folder(ITEM) / "CDMSlite_Run2_data" / "data_files"

    @property
    def info(self) -> ExperimentInfo:
        """Germanium, the search window in keVnr, the release's event list and the interval method."""
        low, high = (nuclear_recoil(e) for e in WINDOW_KEVEE)
        return ExperimentInfo(
            name=self.name, target="Ge", exposure_kg_day=EXPOSURE_KG_DAY,
            energy_window_kev=(low, high), observables=["nuclear-recoil energy (keVnr)"],
            fidelity=Fidelity.B, statistical_method=interval_method(),
            data=[DataSet(experiment=self.name, kind=DataKind.events,
                          path=str(self.folder / "eventEnergy_keVee.txt"),
                          source="arXiv:1707.01632v3 (ancillary files)")],
            references=["arXiv:1509.02448", "arXiv:1707.01632"])

    def target(self) -> Target:
        """Natural germanium."""
        return targets.target("Ge")

    def conventions(self) -> PublishedConventions:
        """The release's halo (v0 = 220, v_E = 232, v_esc = 544 km/s), the Helm form factor and Klos et al.'s ⁷³Ge
        structure factors."""
        return PublishedConventions(
            halo=standard_halo(220.0, 232.0, 544.0), nuclear_model=NuclearModel.helm,
            spin_dependent_model=NuclearModel.klos,
            note="the release's section 3.2: ρ = 0.3 GeV/cm³, v0 = 220, v_E = 232, "
                 "v_esc = 544 km/s, Helm form factor; Lindhard k = 0.157 (best fit); "
                 "spin-dependent limits with the 73Ge structure factors of Klos et al. "
                 "including two-body currents (arXiv:1707.01632, section VII.B)")

    def published_limits(self) -> list[LimitCurve]:
        """The official median limits (third column), where the search is sensitive."""
        curves = []
        for kind, name in [(CrossSectionKind.si, "SI"), (CrossSectionKind.sd_proton, "SD_p"),
                           (CrossSectionKind.sd_neutron, "SD_n")]:
            table = read_columns(self.folder / f"limits_{name}_GeVc2_cm2.txt", columns=3)
            finite = np.isfinite(table[:, 2])
            curves.append(LimitCurve(
                experiment=self.name, kind=kind, masses_gev=table[finite, 0].tolist(),
                cross_sections_cm2=table[finite, 2].tolist(),
                source=f"arXiv:1707.01632v3, limits_{name}_GeVc2_cm2.txt (official median)",
                note="the release also gives a single 'best-fit' limit, which the module's "
                     "choices follow; the official median samples k in [0.1, 0.2]"))
        return curves

    @cached_property
    def events(self) -> np.ndarray:
        """Event energies in keVnr, within the search window."""
        kevee = read_columns(self.folder / "eventEnergy_keVee.txt", columns=1)[:, 0]
        kevee = kevee[(kevee >= WINDOW_KEVEE[0]) & (kevee <= WINDOW_KEVEE[1])]
        return np.sort([nuclear_recoil(e) for e in kevee])

    @cached_property
    def recoil_grid(self) -> np.ndarray:
        """Nuclear-recoil energies spanning the window."""
        low, high = (nuclear_recoil(e) for e in WINDOW_KEVEE)
        return np.geomspace(low, high, 1500)

    @cached_property
    def efficiency(self) -> np.ndarray:
        """The best-fit efficiency on ``recoil_grid``."""
        table = read_columns(self.folder / "efficiency_bestFit_keVee.txt", columns=2)
        return np.interp(electron_equivalent(self.recoil_grid), table[:, 0], table[:, 1],
                         left=0.0, right=0.0)

    def expected_signal(self, particle: DarkMatterParticle, interaction: InteractionModel,
                        halo: HaloModel, model: NuclearModel,
                        target: Target | None = None) -> ExpectedSignal:
        """Expected events per keVnr on ``recoil_grid``: the exposure times the best-fit efficiency times the rate."""
        grid = self.recoil_grid
        rate = sum(element_rates(grid, particle, interaction, target or self.target(),
                                 halo, model).values())
        density = EXPOSURE_KG_DAY * self.efficiency * rate
        return ExpectedSignal(experiment=self.name, interaction_id=interaction.id,
                              particle=particle, total_events=float(np.trapezoid(density, grid)),
                              observable=grid.tolist(), density=density.tolist())

    def upper_limit(self, signal: ExpectedSignal, cl: float = 0.9) -> float:
        """The interval-method limit (``interval_limit``) against the observed events in the window."""
        return interval_limit(self.events, signal, cl)

    @cached_property
    def efficiency_samples(self) -> tuple[np.ndarray, np.ndarray]:
        """(bin energies in keVee, samples as columns): the release's 1000 efficiency curves."""
        bins = read_columns(self.folder / "efficiency_bestFit_keVee.txt", columns=1)[:, 0]
        samples = np.loadtxt(self.folder / "efficiency_samples.txt")
        return bins, samples

    def official_limit(self, kind: CrossSectionKind, mass_gev: float, realisations: int = 300,
                       seed: int = 20260929, cl: float = 0.9) -> float:
        """The published procedure: the median limit over sampled efficiencies and k.

        The recoil spectrum is computed once on a grid wide enough for every k;
        each realisation re-maps the window, the events and the efficiency to
        nuclear-recoil energy with its own k and sets its own limit.
        """
        conventions = self.conventions()
        particle = DarkMatterParticle(mass_gev=mass_gev)
        interaction = reference_interaction(kind, REFERENCE_SIGMA_CM2, mass_gev)
        low = nuclear_recoil(WINDOW_KEVEE[0], K_RANGE[1])
        high = nuclear_recoil(WINDOW_KEVEE[1], K_RANGE[0])
        wide = np.geomspace(low, high, 3000)
        rate = sum(element_rates(wide, particle, interaction, self.target(), conventions.halo,
                                 conventions.model_for(kind)).values())
        kevee = read_columns(self.folder / "eventEnergy_keVee.txt", columns=1)[:, 0]
        kevee = kevee[(kevee >= WINDOW_KEVEE[0]) & (kevee <= WINDOW_KEVEE[1])]
        bins, samples = self.efficiency_samples
        rng = np.random.default_rng(seed)
        limits = []
        for column in rng.choice(samples.shape[1], size=realisations, replace=False):
            k = rng.uniform(*K_RANGE)
            window = [nuclear_recoil(e, k) for e in WINDOW_KEVEE]
            grid = np.geomspace(window[0], window[1], 1500)
            efficiency = np.interp(electron_equivalent(grid, k), bins, samples[:, column],
                                   left=0.0, right=0.0)
            density = EXPOSURE_KG_DAY * efficiency * np.interp(grid, wide, rate)
            total = float(np.trapezoid(density, grid))
            if total <= 0.0:
                limits.append(np.inf)
                continue
            signal = ExpectedSignal(experiment=self.name, particle=particle, total_events=total,
                                    observable=grid.tolist(), density=density.tolist())
            events = np.sort([nuclear_recoil(e, k) for e in kevee])
            limits.append(REFERENCE_SIGMA_CM2 * interval_limit(events, signal, cl))
        return float(np.median(limits))

    def reference_limits(self, kind: CrossSectionKind, masses_gev: list[float],
                         workers: int = 1, cl: float = 0.9) -> list[float]:
        """The official procedure: the published limit is its median (``official_limit``)."""
        if cl != 0.9:
            return [self.official_limit(kind, m, cl=cl) for m in masses_gev]
        return self.official_limits(kind, masses_gev, workers=workers)

    def official_limits(self, kind: CrossSectionKind, masses_gev: list[float],
                        realisations: int = 300, workers: int = 1) -> list[float]:
        """``official_limit`` at several masses, in ``workers`` processes.

        Each mass has its own fixed seed, so the result does not depend on
        ``workers``. A script that uses more than one needs an
        ``if __name__ == "__main__":`` guard (processes are spawned).
        """
        if workers <= 1:
            return [self.official_limit(kind, m, realisations) for m in masses_gev]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(_official_limit, repeat(kind), masses_gev, repeat(realisations)))


@lru_cache(maxsize=1)
def _module() -> CdmsliteRun2:
    return CdmsliteRun2()


def _official_limit(kind: CrossSectionKind, mass_gev: float, realisations: int) -> float:
    """One official limit, in a worker process."""
    return _module().official_limit(kind, mass_gev, realisations)
