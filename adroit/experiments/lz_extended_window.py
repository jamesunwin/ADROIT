"""LZ's extended-window search (arXiv:2609.02823): its tables, events, and a fidelity-B module.

**The published record.** The HEPData record (ins3199115, CC0; a manual
download) gives, for each of 43 interaction models (L01–L20 in isoscalar "s"
and isovector "v" form, and the inelastic O01 and O04), the limits on the
dimensionless coupling, the expected-limit bands and the local significance
at each mass. It also gives three event samples in (S1c, log₁₀ S2c). It has
no background model, which LZ fits in two dimensions to 1710 events,
nearly all electron recoils.

**The module (DM5), fidelity B.** Above about 100 keV the nuclear-recoil
band is almost free of background, and the search's one nuclear-recoil-like
event, the event of interest at 248 ± 23 (stat) ± 23 (sys) keV, dominates
the inference there. The module keeps just that:
- the signal is exposure (220 d × 4.71 t) × efficiency (Fig. S2, digitised)
  × dR/dE in true recoil energy;
- the likelihood is L(s) = e^{−s} [s f(E*) + b*], with f(E*) the signal's
  normalised spectral density at the event (smeared by σ* = 32.5 keV, the
  two uncertainties combined) and b* the density of nuclear-recoil-like
  background there;
- b* is fixed by one published number: the 3.4σ local significance of L10
  (isoscalar, 1000 GeV) in LZ's Table S7;
- intervals are two-sided profile-likelihood intervals at 90%, with the
  asymptotic threshold χ²₁ = 2.706.

It leaves out the electron-recoil leakage into the nuclear-recoil band below
about 110 keV, so it is approximate for signals concentrated there.
**LZ's conventions**, needed for its numbers: the revised xenon responses
(``NuclearModel.haxton_2022``), the Lagrangians' matching scale m_M = m_N
(arXiv:2404.17666), and the halo of arXiv:2105.00599.
"""

from __future__ import annotations

import math
from functools import cached_property, lru_cache
from pathlib import Path

import numpy as np
import yaml
from scipy.optimize import brentq
from scipy.special import ndtri

from adroit.core.dm_state import (DarkMatterParticle, ExpectedSignal,
                                  ExperimentInfo, Fidelity, HaloModel, InteractionModel,
                                  LimitCurve, NuclearModel, PublishedConventions,
                                  PublishedModelTable, Target)
from adroit.experiments import digitised
from adroit.experiments.base import ExperimentModule, data_folder, element_rates
from adroit.physics import targets
from adroit.physics.conventions import OPERATOR_MASS_GEV

ITEM = "LZ extended window (arXiv:2609.02823)"
EXPERIMENT = "LZ extended window (2026)"
SAMPLES = ("Science", "PromptVeto", "DelayedVeto")
QUANTITY = "dimensionless coupling d = c m_v², m_v = 246.2 GeV"


def _columns(record: dict) -> dict[str, list[float]]:
    """Each dependent variable of a HEPData table, by its header name."""
    return {v["header"]["name"]: [float(x["value"]) for x in v["values"]]
            for v in record["dependent_variables"]}


def read_table(path: Path) -> PublishedModelTable:
    """One model's table from its HEPData YAML file."""
    record = yaml.safe_load(path.read_text())
    masses = [float(x["value"]) for x in record["independent_variables"][0]["values"]]
    columns = _columns(record)
    return PublishedModelTable(
        experiment=EXPERIMENT, model=path.stem, quantity=QUANTITY, masses_gev=masses,
        upper=columns["Upper Limit"], lower=columns["Lower Limit"], median=columns["Median"],
        band_1sigma=(columns["-1 sigma"], columns["+1 sigma"]),
        band_2sigma=(columns["-2 sigma"], columns["+2 sigma"]),
        local_significance=columns["Local Significance"],
        splitting_kev=columns.get("Delta (keV)", []),
        source=f"HEPData ins3199115 (doi:10.17182/hepdata.182472), {path.name}")


def model_tables(folder: Path | None = None) -> dict[str, PublishedModelTable]:
    """Every model's table, keyed by the model's name (e.g. 'L01s', 'O04s')."""
    root = folder or data_folder(ITEM)
    names = sorted(p for p in root.glob("*.yaml") if p.stem[0] in "LO" and p.stem[1:3].isdigit())
    return {p.stem: read_table(p) for p in names}


def event_sample(sample: str, folder: Path | None = None) -> np.ndarray:
    """One event sample as rows of (S1c in phd, log₁₀ S2c)."""
    if sample not in SAMPLES:
        raise ValueError(f"unknown sample {sample!r}; the record has {', '.join(SAMPLES)}")
    record = yaml.safe_load(((folder or data_folder(ITEM)) / f"{sample}.yaml").read_text())
    s1 = [float(x["value"]) for x in record["independent_variables"][0]["values"]]
    log_s2 = [float(x["value"]) for x in record["dependent_variables"][0]["values"]]
    return np.column_stack([s1, log_s2])


# --- the fidelity-B module (DM5) -------------------------------------------------------

EXPOSURE_KG_DAY = 220.0 * 4710.0
ENERGIES_KEV = np.arange(1.0, 400.0, 0.5)
EVENT_KEV = 248.0
EVENT_SIGMA_KEV = math.hypot(23.0, 23.0)
REFERENCE_MODEL = ("L10", "s", 1000.0)      # its local significance calibrates b*
REFERENCE_SIGNIFICANCE = 3.4                # LZ, Table S7 and HEPData
THRESHOLD_90 = 2.705543454095404            # χ²₁ at 90%


def interval_counts(f_event: float, b_event: float,
                    threshold: float = THRESHOLD_90) -> tuple[float, float, float]:
    """(lower, best, upper) signal counts from one event: L(s) = e^{−s}(s f + b).

    q(s) = 2[(s − ŝ) − ln((s f + b)/(ŝ f + b))], with ŝ = max(0, 1 − b/f); the
    interval is where q ≤ threshold.
    """
    best = max(0.0, 1.0 - b_event / f_event) if f_event > 0.0 else 0.0

    def q(s: float) -> float:
        return 2.0 * ((s - best) - math.log((s * f_event + b_event) / (best * f_event + b_event)))

    upper = brentq(lambda s: q(s) - threshold, best, best + 100.0)
    lower = brentq(lambda s: q(s) - threshold, 0.0, best) if best > 0 and q(0.0) > threshold else 0.0
    return lower, best, upper


def local_significance(f_event: float, b_event: float) -> float:
    """Z = √q₀ for the one event against background only (0 if ŝ = 0)."""
    if f_event <= b_event:
        return 0.0
    r = b_event / f_event
    return math.sqrt(2.0 * (r - 1.0 - math.log(r)))


def ratio_for_significance(z: float) -> float:
    """b/f at which one event has local significance z: r − 1 − ln r = z²/2, r < 1."""
    return brentq(lambda r: r - 1.0 - math.log(r) - 0.5 * z * z, 1e-300, 1.0 - 1e-12)


class LzExtendedWindow(ExperimentModule):
    """LZ's extended-window search at fidelity B: the event of interest on a clean band."""

    name = EXPERIMENT

    @cached_property
    def efficiency(self) -> np.ndarray:
        """ε(E) on ``ENERGIES_KEV``, from LZ's Fig. S2 (digitised), zero outside it."""
        figure = digitised.load("lz_2026_figS2")
        return np.interp(ENERGIES_KEV, figure["energy_kev"], figure["efficiency"],
                         left=0.0, right=0.0)

    @property
    def info(self) -> ExperimentInfo:
        """Xenon, 220 d × 4.71 t, 5.4–269.9 keV; the profile likelihood of the one event of interest."""
        return ExperimentInfo(
            name=self.name, target="Xe", exposure_kg_day=EXPOSURE_KG_DAY,
            energy_window_kev=(5.4, 269.9),
            observables=["true nuclear-recoil energy", "the event of interest (248 keV)"],
            fidelity=Fidelity.B, background_model=False,
            statistical_method="profile likelihood of the one nuclear-recoil-like event on a "
                               "calibrated background density; two-sided, asymptotic, 90%",
            references=["arXiv:2609.02823", "doi:10.17182/hepdata.182472"])

    def target(self) -> Target:
        """Natural xenon."""
        return targets.target("Xe")

    def conventions(self) -> PublishedConventions:
        """LZ's conventions: the revised xenon responses (``haxton_2022``) for SI and SD, and the default
        ``HaloModel`` as the halo of arXiv:2105.00599."""
        return PublishedConventions(
            halo=HaloModel(), nuclear_model=NuclearModel.haxton_2022,
            spin_dependent_model=NuclearModel.haxton_2022,
            note="arXiv:2609.02823: WimPyDD with the revised density matrices (arXiv:2312.02030), "
                 "the halo of arXiv:2105.00599; L_j with m_M = m_N (arXiv:2404.17666)")

    def published_limits(self) -> list[LimitCurve]:
        """None as cross-section curves: LZ publishes coupling limits per model (``model_tables``)."""
        return []

    def expected_signal(self, particle: DarkMatterParticle, interaction: InteractionModel,
                        halo: HaloModel, model: NuclearModel,
                        target: Target | None = None) -> ExpectedSignal:
        """dN/dE = exposure × ε(E) × dR/dE in true recoil energy on ``ENERGIES_KEV``, summed over the target's
        elements. The revised responses' runtime must be installed for ``haxton_2022``, or this refuses, naming what
        is missing (``prescription.require``; V1-01: they had silently become the shell model's)."""
        from adroit.experiments.prescription import require
        require(model, target or self.target())
        rate = sum(element_rates(ENERGIES_KEV, particle, interaction, target or self.target(),
                                 halo, model).values())
        density = EXPOSURE_KG_DAY * self.efficiency * rate
        return ExpectedSignal(experiment=self.name, interaction_id=interaction.id,
                              particle=particle, total_events=float(np.trapezoid(density, ENERGIES_KEV)),
                              observable=ENERGIES_KEV.tolist(), density=density.tolist())

    def event_density(self, signal: ExpectedSignal) -> float:
        """f(E*): the signal's normalised density at the event, smeared by σ* (per keV)."""
        if signal.total_events <= 0.0:
            return 0.0
        kernel = np.exp(-0.5 * ((ENERGIES_KEV - EVENT_KEV) / EVENT_SIGMA_KEV) ** 2)
        kernel /= EVENT_SIGMA_KEV * math.sqrt(2.0 * math.pi)
        return float(np.trapezoid(np.asarray(signal.density) * kernel, ENERGIES_KEV)
                     / signal.total_events)

    def interval(self, signal: ExpectedSignal, cl: float = 0.9) -> tuple[float, float]:
        """(κ_lo, κ_up) on the signal's normalisation, two-sided."""
        if signal.total_events <= 0.0:
            return 0.0, math.inf
        threshold = ndtri(0.5 + 0.5 * cl) ** 2
        low, _, high = interval_counts(self.event_density(signal), background_density(),
                                       threshold)
        return low / signal.total_events, high / signal.total_events

    def upper_limit(self, signal: ExpectedSignal, cl: float = 0.9) -> float:
        """κ_up: the upper end of the two-sided profile-likelihood interval (``interval``)."""
        return self.interval(signal, cl)[1]

    def observations(self) -> tuple[np.ndarray, np.ndarray]:
        """(event energies, resolution at each), keV: the one event of interest (DM6)."""
        return np.array([EVENT_KEV]), np.array([EVENT_SIGMA_KEV])

    def signal_grid_kev(self) -> np.ndarray:
        """``ENERGIES_KEV``: 1 to 400 keV in steps of 0.5 keV."""
        return ENERGIES_KEV

    def candidate_values(self, card_id: str, isospin: str) -> dict[str, float]:
        """LZ's convention: unit coupling 1/m_v², and m_M = m_N for the L_j (``lz_values``)."""
        return lz_values(card_id, isospin)

    def model_space(self) -> list[dict]:
        """LZ's 612 physical models (Tables S7, S8), with the L_j as LZ computes them (``LZ_CARDS``)."""
        return model_space()

    def background_on_grid(self) -> np.ndarray:
        """The background density on ``ENERGIES_KEV`` (events/keV): b*, flat where efficient.

        Only its value at the event is published (through the significance it
        implies); flat is an assumption, which the global significance
        inherits.
        """
        return np.where(self.efficiency > 0.0, background_density(), 0.0)

    def significance(self, signal: ExpectedSignal) -> float:
        """The local significance of the event for this signal, in σ."""
        return local_significance(self.event_density(signal), background_density())


MODEL_MASSES = [10, 12, 14, 17, 21, 30, 40, 50, 100, 200, 400, 1000, 4000]
MODEL_INELASTIC = [(m, d) for m in (400, 1000, 4000) for d in range(0, 351, 50) if (m, d) != (400, 350)]
# The interactions as LZ computed them (cards *_LZ; docs/notes/lz_model_cards.html): L6 and L9 as LZ's covariant
# paper writes them, and L5, L7, L8, L13 and L17 with the vector currents LZ's limits follow. The one source for
# every comparison with LZ; the rest of ADROIT uses Anand et al.'s cards.
LZ_CARDS = {"L05": "L05_LZ", "L06": "L06_LZ", "L07": "L07_LZ", "L08": "L08_LZ", "L09": "L09_LZ", "L13": "L13_LZ",
            "L17": "L17_LZ"}


def model_space() -> list[dict]:
    """LZ's 612 physical models: L1–L20 elastic, and inelastic O1 and O4, each isoscalar and isovector."""
    out = []
    for j in range(1, 21):
        card = LZ_CARDS.get(f"L{j:02d}", f"L{j:02d}")
        out += [dict(label=f"L{j:02d}{i}@{m}", card_id=card, isospin=i, mass_gev=m, splitting_kev=0.0)
                for i in "sv" for m in MODEL_MASSES]
    for op in (1, 4):
        out += [dict(label=f"O{op:02d}{i}@{m},d={d}", card_id=f"O{op}", isospin=i, mass_gev=m,
                     splitting_kev=d) for i in "sv" for m, d in MODEL_INELASTIC]
    return out


def lz_values(card_id: str, isospin: str) -> dict[str, float]:
    """A card's couplings as LZ tabulates them: unit coupling 1/m_v², m_M = m_N for the L_j."""
    from adroit.library.interactions import registry
    values = registry.isospin_values(card_id, isospin, 1.0 / 246.2 ** 2)
    if card_id.startswith("L"):
        values["m_M"] = OPERATOR_MASS_GEV
    return values


def background_density() -> float:
    """b*: the background density at the event, from LZ's significance for L10 at 1000 GeV; of the record's files as
    they are now (each by ``file_reads.stamp``: a replaced record is read again, BI-02)."""
    from adroit.core.file_reads import stamp
    folder = data_folder(ITEM)
    return _background_density(tuple(stamp(p) for p in sorted(folder.iterdir()) if p.is_file()))


@lru_cache(maxsize=2)
def _background_density(files: tuple) -> float:
    from adroit.library.interactions import registry
    card, isospin, mass = REFERENCE_MODEL
    particle = DarkMatterParticle(mass_gev=mass)
    module = LzExtendedWindow()
    conventions = module.conventions()
    signal = module.expected_signal(particle, registry.resolve(card, particle,
                                                               lz_values(card, isospin)),
                                    conventions.halo, conventions.nuclear_model)
    return ratio_for_significance(REFERENCE_SIGNIFICANCE) * module.event_density(signal)
