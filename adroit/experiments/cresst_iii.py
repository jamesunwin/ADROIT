"""CRESST-III 2019, detector A: CaWO₄ with a 30.1 eV threshold (arXiv:1904.00498, 1905.07335).

The collaboration's data release gives the energies of the 441 events in
the acceptance region, the cut-survival probability, and for each element
the probability that its recoils fall in the acceptance region. The
expected spectrum in reconstructed energy is

    p̃(E') = Θ(E' − E_thr) Σ_x ε_x,Acc(E') ∫ ε̃(E) p_x(E) N(E' − E; σ) dE ,

summed over x = O, Ca, W, with σ = 4.6 eV. The limit is Yellin's optimum
interval with all events treated as possible signal, as published.

**Assumptions, recorded (owner's decisions of 2026-09-29):**
- **The cut survival acts in true energy.** The release is ambiguous: its
  Eq. 1 (page 3) applies ε̃ outside the convolution, in reconstructed energy,
  while its appendix (page 5, and the caption of Fig. 6 on page 6) gives the
  curve "as a function of simulated energy". The module multiplies p_x(E) by
  ε̃(E) inside the convolution, as the appendix reads. The two agree above
  about 0.35 GeV; below it this reading gives weaker limits than the
  collaboration's released ones, by about 50 times at 0.16 GeV.
  ``cut_survival="reconstructed"`` gives Eq. 1's reading instead, which
  reproduces the released limits there.
- **The exposure is 5.594 kg days** before selection, from the release's
  Table I; the text on the same page says 5.689 kg days.
- **The detector speed through the halo is 232 km/s** (Lewin & Smith); the
  paper gives v₀ = 220 km/s and v_esc = 544 km/s but not this.
- **Spin-dependent scattering is carried by ¹⁷O alone** (⟨S_n⟩ = 0.5), as in
  the paper (section VI.2). ¹⁸³W has no spin response in this project
  (``physics/data/isotopes.yaml``), and ⁴³Ca none either. For its published
  comparison the module uses the ¹⁷O abundance the collaboration assumed,
  0.0367% (``published_target``).
"""

from __future__ import annotations

from functools import cached_property

import numpy as np

from adroit.core.dm_state import (CrossSectionKind, DarkMatterParticle, DataKind, DataSet,
                                      ExpectedSignal, ExperimentInfo, Fidelity, HaloModel,
                                      InteractionModel, LimitCurve, NuclearModel,
                                      PublishedConventions, Target)
from adroit.experiments.base import (ExperimentModule, data_folder, element_rates,
                                         interval_limit, interval_method, read_columns, smear,
                                         standard_halo)
from adroit.physics import targets

ITEM = "CRESST-III data release (arXiv:1905.07335)"
EXPOSURE_KG_DAY = 5.594        # Table I of the release; its text says 5.689 (see above)
THRESHOLD_KEV = 0.0301
RESOLUTION_KEV = 0.0046
TOP_KEV = 16.0
PB_TO_CM2 = 1e-36
O17_ABUNDANCE = 0.000367    # the minimal natural abundance CRESST assumed


class CresstIII2019(ExperimentModule):
    """CRESST-III detector A (2019)."""

    name = "CRESST-III 2019"

    def __init__(self, cut_survival: str = "true") -> None:
        if cut_survival not in ("true", "reconstructed"):
            raise ValueError("cut_survival is 'true' (the default) or 'reconstructed' (Eq. 1)")
        self.folder = data_folder(ITEM)
        self.cut_survival = cut_survival

    @property
    def info(self) -> ExperimentInfo:
        """CaWO₄, 5.594 kg days, the window from the 30.1 eV threshold to 16 keV; the events of the data release,
        Yellin's interval method."""
        return ExperimentInfo(
            name=self.name, target="CaWO4", exposure_kg_day=EXPOSURE_KG_DAY,
            energy_window_kev=(THRESHOLD_KEV, TOP_KEV), observables=["reconstructed energy (keV)"],
            fidelity=Fidelity.B, statistical_method=interval_method(),
            data=[DataSet(experiment=self.name, kind=DataKind.events,
                          path=str(self.folder / "C3P1_DetA_AR.dat"),
                          source="arXiv:1905.07335v3 (ancillary files)")],
            references=["arXiv:1904.00498", "arXiv:1905.07335"])

    def target(self) -> Target:
        """Natural CaWO₄."""
        return targets.target("CaWO4")

    def conventions(self) -> PublishedConventions:
        """The paper's halo (v₀ = 220 km/s, v_esc = 544 km/s, ρ = 0.3 GeV/cm³) with an assumed detector speed of 232
        km/s, and the Helm form factor."""
        return PublishedConventions(
            halo=standard_halo(220.0, 232.0, 544.0),
            nuclear_model=NuclearModel.helm,
            note="ρ = 0.3 GeV/cm³, v0 = 220 km/s, v_esc = 544 km/s and the Helm form factor, "
                 "as stated in arXiv:1904.00498; the detector speed of 232 km/s is assumed "
                 "(Lewin & Smith), since the paper does not state it")

    def published_limits(self) -> list[LimitCurve]:
        """The released SI and SD-neutron limit curves, converted from pb to cm²."""
        curves = []
        for kind, name in [(CrossSectionKind.si, "SI"), (CrossSectionKind.sd_neutron, "SD")]:
            table = read_columns(self.folder / f"C3P1_DetA_DataRelease_{name}.xy")
            curves.append(LimitCurve(
                experiment=self.name, kind=kind, masses_gev=table[:, 0].tolist(),
                cross_sections_cm2=(table[:, 1] * PB_TO_CM2).tolist(),
                source=f"arXiv:1905.07335v3, C3P1_DetA_DataRelease_{name}.xy",
                note="recomputed by the collaboration with the analytic recipe of the release"))
        return curves

    @cached_property
    def events(self) -> np.ndarray:
        """Reconstructed energies of the events in the acceptance region and the window."""
        energies = read_columns(self.folder / "C3P1_DetA_AR.dat", columns=1)[:, 0]
        return np.sort(energies[(energies >= THRESHOLD_KEV) & (energies <= TOP_KEV)])

    @cached_property
    def _tables(self) -> dict[str, np.ndarray]:
        tables = {"cut": read_columns(self.folder / "C3P1_DetA_cuteff.dat")}
        for element in ("O", "Ca", "W"):
            tables[element] = read_columns(self.folder / f"C3P1_DetA_eff_AR_{element}.dat")
        return tables

    @staticmethod
    def true_grid() -> np.ndarray:
        """True recoil energies: fine near threshold, where the smearing matters."""
        return np.unique(np.concatenate([np.linspace(1e-4, 0.3, 1500),
                                         np.geomspace(0.3, TOP_KEV + 0.05, 400)]))

    @staticmethod
    def reco_grid() -> np.ndarray:
        """Reconstructed energies across the search window."""
        return np.unique(np.concatenate([np.linspace(THRESHOLD_KEV, 0.3, 1000),
                                         np.geomspace(0.3, TOP_KEV, 400)]))

    def published_target(self, kind: CrossSectionKind) -> Target:
        """CaWO₄ for SI; for SD, ¹⁷O as the only spin carrier at the abundance CRESST assumed (``oxygen_17_only``)."""
        if kind is CrossSectionKind.si:
            return self.target()
        return oxygen_17_only(self.target(), O17_ABUNDANCE)

    def expected_signal(self, particle: DarkMatterParticle, interaction: InteractionModel,
                        halo: HaloModel, model: NuclearModel,
                        target: Target | None = None) -> ExpectedSignal:
        """p̃(E') on the reconstructed grid: each element's rate times the exposure, smeared by σ = 4.6 eV and
        weighted by its acceptance, with the cut survival in true or reconstructed energy (``cut_survival``)."""
        true, reco = self.true_grid(), self.reco_grid()
        in_true = self.cut_survival == "true"
        cut = np.interp(true if in_true else reco, *self._tables["cut"].T, left=0.0)
        density = np.zeros_like(reco)
        for element, rate in element_rates(true, particle, interaction, target or self.target(),
                                           halo, model).items():
            before = EXPOSURE_KG_DAY * rate * (cut if in_true else 1.0)
            smeared = smear(true, before, reco, RESOLUTION_KEV)
            acceptance = np.interp(reco, *self._tables[element].T, left=0.0, right=0.0)
            density += acceptance * smeared * (1.0 if in_true else cut)
        return ExpectedSignal(experiment=self.name, interaction_id=interaction.id,
                              particle=particle, total_events=float(np.trapezoid(density, reco)),
                              observable=reco.tolist(), density=density.tolist(),
                              energy_scale="reconstructed")

    def upper_limit(self, signal: ExpectedSignal, cl: float = 0.9) -> float:
        """κ_up by Yellin's optimum interval over the events in the window (``interval_limit``)."""
        return interval_limit(self.events, signal, cl)


def oxygen_17_only(target: Target, abundance: float) -> Target:
    """CaWO₄ with ¹⁷O as the only isotope with spin, at the given atomic abundance of oxygen."""
    oxygen_share = sum(i.mass_fraction for i in target.isotopes if i.element == "O")
    isotopes = []
    for isotope in target.isotopes:
        if isotope.element == "O":
            continue
        isotopes.append(isotope.model_copy(update={"spin": 0.0}))
    o17_share = oxygen_share * abundance * 17.0 / (abundance * 17.0 + (1.0 - abundance) * 16.0)
    o16 = next(i for i in target.isotopes if i.name == "O16")
    o17 = next(i for i in target.isotopes if i.name == "O17")
    isotopes.append(o16.model_copy(update={"mass_fraction": oxygen_share - o17_share}))
    isotopes.append(o17.model_copy(update={"mass_fraction": o17_share}))
    return Target(name=f"{target.name} (17O the only spin carrier)", isotopes=isotopes)
