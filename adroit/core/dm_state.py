"""Typed state for dark matter direct detection.

The objects that pass between the physics core, the experiment modules, the
constraints and the tournament. Each is validated on construction, like the
run state in :mod:`adroit.core.state`. Units and conventions are those of
:mod:`adroit.physics.conventions`.

The chain they describe:

    DarkMatterParticle + InteractionModel + HaloModel + Target
        → RecoilSpectrum                      (the physics core)
        → LikelihoodResult, per experiment    (an experiment module)
        → ConstraintVerdict, per constraint   (the complementary constraints)
"""

from __future__ import annotations

import math
from datetime import date
from enum import Enum
from typing import Literal

import numpy as np
from pydantic import Field, model_validator

from adroit.core.state import StrictModel, _new_id

# --- the dark matter particle --------------------------------------------------------


class DarkMatterParticle(StrictModel):
    """A dark matter particle: its mass, spin and mass splitting.

    ``mass_splitting_kev`` is δ = m_χ* − m_χ, the mass gained in the
    scattering: δ > 0 is inelastic (endothermic), δ < 0 exothermic, δ = 0
    elastic.
    """

    mass_gev: float = Field(gt=0.0)
    spin: float = 0.5
    mass_splitting_kev: float = 0.0
    self_conjugate: bool = False

    @model_validator(mode="after")
    def _spin_is_a_half_integer(self) -> "DarkMatterParticle":
        if self.spin < 0 or (2 * self.spin) != int(2 * self.spin):
            raise ValueError(f"spin must be 0, 1/2, 1, ...; got {self.spin}")
        return self

    @property
    def kinematics(self) -> str:
        """'elastic', 'inelastic' (δ > 0) or 'exothermic' (δ < 0)."""
        if self.mass_splitting_kev == 0.0:
            return "elastic"
        return "inelastic" if self.mass_splitting_kev > 0.0 else "exothermic"


# --- the halo ------------------------------------------------------------------------


class HaloKind(str, Enum):
    """How the velocity distribution is given."""

    standard = "standard"      # the Standard Halo Model: a truncated Maxwellian
    tabulated = "tabulated"    # a tabulated speed distribution in the detector frame


class HaloModel(StrictModel):
    """The local dark matter density and velocity distribution.

    The default is the Standard Halo Model with the parameters recommended in
    arXiv:2105.00599 (its Table 1): an isotropic Maxwellian of most probable
    speed v_0 in the Galactic frame, truncated at the escape speed, seen from
    a detector moving at the Sun's velocity plus the Earth's.

    A ``tabulated`` halo gives the speed distribution f(v) in the detector
    frame directly, normalised to ∫ f(v) dv = 1. It is the route for any
    deviation from the standard model: streams, debris flows, the results of
    simulations.
    """

    kind: HaloKind = HaloKind.standard
    label: str = "Standard Halo Model (arXiv:2105.00599)"
    rho_gev_cm3: float = Field(default=0.3, gt=0.0)
    v0_km_s: float = Field(default=238.0, gt=0.0)
    v_esc_km_s: float = Field(default=544.0, gt=0.0)
    # Galactic coordinates (toward the centre, along the rotation, toward the north pole).
    v_lsr_km_s: tuple[float, float, float] = (0.0, 238.0, 0.0)
    v_peculiar_km_s: tuple[float, float, float] = (11.1, 12.2, 7.3)
    # The Earth's velocity about the Sun on 9 March, when the detector's speed
    # equals its annual average (arXiv:2105.00599, Eq. 12).
    v_earth_km_s: tuple[float, float, float] = (29.2, -0.1, 5.9)
    speeds_km_s: list[float] = Field(default_factory=list)
    speed_density: list[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def _a_tabulated_halo_has_its_table(self) -> "HaloModel":
        if self.kind is HaloKind.tabulated:
            if len(self.speeds_km_s) < 2 or len(self.speeds_km_s) != len(self.speed_density):
                raise ValueError("a tabulated halo needs speeds_km_s and speed_density of the "
                                 "same length (at least 2)")
            if any(b <= a for a, b in zip(self.speeds_km_s, self.speeds_km_s[1:])):
                raise ValueError("speeds_km_s must increase")
            if any(f < 0.0 for f in self.speed_density):
                raise ValueError("speed_density must not be negative")
        return self

    @property
    def v_lab_km_s(self) -> float:
        """The detector's speed through the halo: |v_LSR + v_peculiar + v_Earth|."""
        total = [a + b + c for a, b, c in
                 zip(self.v_lsr_km_s, self.v_peculiar_km_s, self.v_earth_km_s)]
        return math.sqrt(sum(x * x for x in total))

    @property
    def is_default(self) -> bool:
        """Whether this is the Standard Halo Model with its recommended parameters."""
        return self == HaloModel()


# --- targets -------------------------------------------------------------------------


class Isotope(StrictModel):
    """One isotope of a target: its nucleus and its share of the target by mass."""

    element: str
    mass_number: int = Field(gt=0)
    atomic_number: int = Field(gt=0)
    spin: float = Field(ge=0.0)
    mass_fraction: float = Field(gt=0.0, le=1.0)

    @property
    def name(self) -> str:
        """E.g. 'Xe131'."""
        return f"{self.element}{self.mass_number}"


class Target(StrictModel):
    """A detector target: a set of isotopes whose mass fractions sum to 1."""

    name: str
    isotopes: list[Isotope] = Field(min_length=1)

    @model_validator(mode="after")
    def _fractions_sum_to_one(self) -> "Target":
        total = sum(i.mass_fraction for i in self.isotopes)
        if abs(total - 1.0) > 1e-3:
            raise ValueError(f"the mass fractions of {self.name} sum to {total:.4f}, not 1")
        return self


# --- interactions --------------------------------------------------------------------


class ModelLayer(str, Enum):
    """The level at which an interaction is described (build plan, section 3)."""

    mediator = "mediator"                # a simplified model with its mediator
    quark = "quark"                      # quark- and gluon-level operators (DirectDM's basis, DM8)
    relativistic = "relativistic"        # a relativistic operator or Lagrangian
    nonrelativistic = "nonrelativistic"  # nucleon-level operators O_i


class OperatorCoefficient(StrictModel):
    """The coefficient of one nonrelativistic operator, in the nucleon basis.

    A constant coefficient is in GeV⁻². A coefficient may also depend on the
    momentum transfer q, as the reductions of many relativistic interactions
    and all light mediators do:

        c(q) = value × (q / q_scale)^q_power × m²/(q² + m²),

    the last factor only when ``mediator_mass_gev`` = m is given (a
    propagator, 1 in the contact limit q ≪ m). An interaction may hold the
    same operator more than once, with different q-dependences; the terms add.
    """

    operator: int = Field(ge=1, le=20)     # i of O_i
    proton: float = 0.0
    neutron: float = 0.0
    q_power: int = 0
    q_scale_gev: float = Field(default=1.0, gt=0.0)
    mediator_mass_gev: float | None = Field(default=None, gt=0.0)

    @property
    def isoscalar(self) -> float:
        """c^0 = (c^p + c^n)/2."""
        return 0.5 * (self.proton + self.neutron)

    @property
    def isovector(self) -> float:
        """c^1 = (c^p − c^n)/2."""
        return 0.5 * (self.proton - self.neutron)

    @property
    def depends_on_q(self) -> bool:
        """Whether the coefficient varies with the momentum transfer."""
        return self.q_power != 0 or self.mediator_mass_gev is not None

    def q_factor(self, q_gev: np.ndarray) -> np.ndarray:
        """(q/q_scale)^q_power × m²/(q² + m²) at the momentum transfers q (GeV)."""
        q = np.asarray(q_gev, dtype=float)
        factor = (q / self.q_scale_gev) ** self.q_power if self.q_power else np.ones_like(q)
        if self.mediator_mass_gev is not None:
            factor = factor * self.mediator_mass_gev ** 2 / (q * q + self.mediator_mass_gev ** 2)
        return factor


class InteractionModel(StrictModel):
    """An interaction of dark matter with nucleons, at one layer of description.

    ``coefficients`` are the nonrelativistic coefficients the interaction maps
    to, which is what the rate calculation reads. ``card_id`` names the library
    card it came from; a bespoke interaction has none. ``dropped`` lists what
    of a fuller model is not represented in the coefficients.
    """

    id: str = Field(default_factory=_new_id)
    name: str
    layer: ModelLayer
    card_id: str = ""
    coefficients: list[OperatorCoefficient] = Field(default_factory=list)
    parameters: dict[str, float] = Field(default_factory=dict)
    dropped: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _one_coefficient_per_term(self) -> "InteractionModel":
        terms = [(c.operator, c.q_power, c.q_scale_gev, c.mediator_mass_gev)
                 for c in self.coefficients]
        if len(terms) != len(set(terms)):
            raise ValueError("an operator appears twice with the same q-dependence: "
                             f"{[t[0] for t in terms]}")
        return self

    @property
    def depends_on_q(self) -> bool:
        """Whether any coefficient varies with the momentum transfer."""
        return any(c.depends_on_q for c in self.coefficients)


# --- spectra -------------------------------------------------------------------------


class RecoilSpectrum(StrictModel):
    """A differential recoil rate dR/dE_R on a target, with everything it assumed.

    ``rate`` is in events per kg of target per day per keV, at the recoil
    energies ``energies_kev``. The halo and the nuclear input are recorded with
    the spectrum, because at high recoil energy both change it by factors
    (docs/dm0_tool_audit.md).
    """

    target: str
    energies_kev: list[float] = Field(min_length=1)
    rate: list[float] = Field(min_length=1)
    particle: DarkMatterParticle
    interaction_id: str = ""
    halo: HaloModel = Field(default_factory=HaloModel)
    nuclear_input: str = ""

    @model_validator(mode="after")
    def _rate_matches_energies(self) -> "RecoilSpectrum":
        if len(self.rate) != len(self.energies_kev):
            raise ValueError("rate and energies_kev must have the same length")
        if any(r < 0.0 or not math.isfinite(r) for r in self.rate):
            raise ValueError("a rate must be finite and not negative")
        return self


class ModulationSpectrum(StrictModel):
    """The annual modulation of a recoil rate, energy by energy.

    R(E, t) ≈ mean_rate(E) + amplitude(E) cos(2π (t − peak_day(E)) / 365.25),
    with t in days after 1 January: the first harmonic of the rate over a year.
    ``amplitude`` is never negative; where the modulation reverses (at low
    energy for heavy dark matter), ``peak_day`` moves by half a year instead.
    Rates are in events per kg per day per keV, as in ``RecoilSpectrum``.
    """

    target: str
    energies_kev: list[float] = Field(min_length=1)
    mean_rate: list[float] = Field(min_length=1)
    amplitude: list[float] = Field(min_length=1)
    peak_day: list[float] = Field(min_length=1)
    particle: DarkMatterParticle
    interaction_id: str = ""
    halo: HaloModel = Field(default_factory=HaloModel)
    nuclear_input: str = ""

    @model_validator(mode="after")
    def _columns_match(self) -> "ModulationSpectrum":
        n = len(self.energies_kev)
        if not len(self.mean_rate) == len(self.amplitude) == len(self.peak_day) == n:
            raise ValueError("mean_rate, amplitude and peak_day must match energies_kev")
        if any(a < 0.0 for a in self.amplitude):
            raise ValueError("an amplitude is not negative; a reversal shows in peak_day")
        return self


# --- experiments ---------------------------------------------------------------------


class Fidelity(str, Enum):
    """What an experiment has released, which sets how its data can be used."""

    A = "A"   # event-level data and a background model: a full likelihood
    B = "B"   # counts, efficiency, background expectation: a binned Poisson likelihood
    C = "C"   # a limit curve only: rescaled for the same spectrum, else a flag


class DataKind(str, Enum):
    """The form of a released data set."""

    events = "events"
    counts = "counts"
    limit_curve = "limit_curve"
    efficiency = "efficiency"
    background_model = "background_model"


class DataSet(StrictModel):
    """One released data file of an experiment, with its provenance."""

    experiment: str
    kind: DataKind
    path: str
    source: str = ""          # a DOI or URL
    licence: str = ""
    sha256: str = ""
    note: str = ""


class ExperimentInfo(StrictModel):
    """What an experiment module declares about its search (build plan, section 5)."""

    name: str
    target: str
    exposure_kg_day: float = Field(gt=0.0)
    energy_window_kev: tuple[float, float]
    observables: list[str] = Field(default_factory=list)
    fidelity: Fidelity
    statistical_method: str = ""
    data: list[DataSet] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    validated: bool = False
    validation_note: str = ""
    background_model: bool = False    # whether the module models its backgrounds

    @model_validator(mode="after")
    def _window_is_ordered(self) -> "ExperimentInfo":
        low, high = self.energy_window_kev
        if not 0.0 <= low < high:
            raise ValueError(f"the energy window must satisfy 0 <= low < high; got {low}, {high}")
        return self

    @property
    def enters_likelihoods(self) -> bool:
        """Only a validated module above fidelity C contributes a likelihood term."""
        return self.validated and self.fidelity is not Fidelity.C

    @property
    def supports_discovery(self) -> bool:
        """Whether the module can measure a signal, not only exclude one.

        A search that treats every event as possible signal (Yellin's methods)
        sets valid limits but cannot claim an excess.
        """
        return self.enters_likelihoods and self.background_model


class LikelihoodResult(StrictModel):
    """The outcome of confronting one interaction with one experiment's data."""

    experiment: str
    interaction_id: str
    particle: DarkMatterParticle
    expected_signal: float = Field(ge=0.0)
    best_fit: dict[str, float] = Field(default_factory=dict)
    log_likelihood: float | None = None
    local_significance: float | None = None
    upper_limit: float | None = None
    lower_limit: float | None = None
    confidence_level: float = Field(default=0.9, gt=0.0, lt=1.0)
    limit_on: str = ""        # the quantity the limits refer to


class NuclearModel(str, Enum):
    """Which nuclear responses a rate uses (``adroit.physics.nuclear``)."""

    shell_model = "shell_model"
    helm = "helm"
    klos = "klos"      # the shell model, with Klos et al.'s spin structure factors (O₄ only)
    haxton_2022 = "haxton_2022"   # the revised density matrices of Haxton & McElvain, as LZ uses


class CrossSectionKind(str, Enum):
    """The cross-section per nucleon a limit is quoted on."""

    si = "SI"                  # O₁, isoscalar (c^p = c^n): σ = c² μ_N²/π
    sd_proton = "SD-proton"    # O₄, proton only: σ = 3 c² μ_N²/(16π)
    sd_neutron = "SD-neutron"  # O₄, neutron only


class LimitCurve(StrictModel):
    """An upper limit on a cross-section per nucleon, as a function of the dark matter mass.

    Masses where a search has no sensitivity are left out.
    """

    experiment: str
    kind: CrossSectionKind
    masses_gev: list[float] = Field(min_length=2)
    cross_sections_cm2: list[float] = Field(min_length=2)
    confidence_level: float = Field(default=0.9, gt=0.0, lt=1.0)
    source: str = ""
    note: str = ""

    @model_validator(mode="after")
    def _a_curve_is_well_formed(self) -> "LimitCurve":
        if len(self.masses_gev) != len(self.cross_sections_cm2):
            raise ValueError("masses and cross-sections must have the same length")
        if any(b <= a for a, b in zip(self.masses_gev, self.masses_gev[1:])):
            raise ValueError("masses must increase")
        if any(not (0.0 < x < math.inf) for x in self.cross_sections_cm2):
            raise ValueError("cross-sections must be positive and finite")
        return self


class PublishedConventions(StrictModel):
    """The assumptions a collaboration used for its published limit.

    A module reproduces the published limit under these, so that the
    comparison is like for like; in a fit it uses the run's own halo and
    nuclear input instead.
    """

    halo: HaloModel
    nuclear_model: NuclearModel = NuclearModel.helm              # for spin-independent limits
    spin_dependent_model: NuclearModel = NuclearModel.shell_model  # for spin-dependent limits
    note: str = ""

    def model_for(self, kind: "CrossSectionKind") -> NuclearModel:
        """The nuclear input the collaboration used for a limit of this kind."""
        return self.nuclear_model if kind is CrossSectionKind.si else self.spin_dependent_model


class ExpectedSignal(StrictModel):
    """What an interaction predicts in one search, for unit signal strength.

    ``observable`` is the grid of the search's observable on which
    ``density`` (events per unit observable) is given; ``total_events`` is
    its integral over the search window. ``energy_scale`` says whether the
    observable is the true recoil energy, which a signal fit smears by the
    search's resolution, or already reconstructed, which it must not smear
    again (the external audit of 2026-10-16, A09). A counting search's
    observable (PICO-60's thresholds) is not an energy, and it has no events
    to smear.
    """

    experiment: str
    interaction_id: str = ""
    particle: DarkMatterParticle
    total_events: float = Field(ge=0.0)
    observable: list[float] = Field(default_factory=list)
    density: list[float] = Field(default_factory=list)
    relative_uncertainty: float = Field(default=0.0, ge=0.0)   # of total_events, from systematics
    energy_scale: Literal["true", "reconstructed"] = "true"


class PublishedModelTable(StrictModel):
    """A collaboration's published results for one interaction model, mass by mass.

    For LZ's extended window (arXiv:2609.02823) the quantity is the
    dimensionless coupling d = c m_v²; each mass has the upper and lower
    limits (the lower is 0 unless the interval excludes zero), the median
    expected limit with its bands, and the local significance.
    ``splitting_kev`` is given for inelastic models.
    """

    experiment: str
    model: str
    quantity: str
    masses_gev: list[float] = Field(min_length=1)
    upper: list[float]
    lower: list[float]
    median: list[float]
    band_1sigma: tuple[list[float], list[float]]
    band_2sigma: tuple[list[float], list[float]]
    local_significance: list[float]
    splitting_kev: list[float] = Field(default_factory=list)
    source: str = ""

    @model_validator(mode="after")
    def _columns_match(self) -> "PublishedModelTable":
        n = len(self.masses_gev)
        columns = [self.upper, self.lower, self.median, *self.band_1sigma, *self.band_2sigma,
                   self.local_significance]
        if any(len(c) != n for c in columns) or (self.splitting_kev and len(self.splitting_kev) != n):
            raise ValueError(f"every column of {self.model} must have one entry per mass")
        return self


class ValidationResult(StrictModel):
    """A module's limit set against the collaboration's, mass by mass (build plan, DM3).

    The rules (decision 4, and the owner's decisions of 2026-09-29):
    - **A point passes** if reproduced/published lies within [1/tolerance,
      tolerance], or, at a steep kinematic edge, if the reproduced curve
      reaches the published cross-section within a small shift in mass
      (``edge_passes``: the published slope |d ln σ/d ln m| exceeds 8 and
      the shift is at most 3%).
    - **The validated range** is a contiguous run of passing masses: the one
      containing the tested mass where the published limit is strongest, if
      that mass passes, and otherwise the widest.
    - **A module counts for the DM3 gate** if its validated range spans at
      least a decade and includes that mass.
    """

    experiment: str
    kind: CrossSectionKind | None = None
    masses_gev: list[float]
    published_cm2: list[float]
    reproduced_cm2: list[float]
    edge_passes: list[bool] = Field(default_factory=list)
    tolerance: float = Field(default=1.3, gt=1.0)
    method: str = ""
    note: str = ""
    # For limits that are not cross-sections against mass (DM5): what is compared, along what.
    model: str = ""                         # e.g. "L10s": the interaction, where not a kind
    quantity: str = "cross-section (cm²)"   # the values in published_cm2, reproduced_cm2
    variable: str = "mass (GeV)"            # the values in masses_gev

    @model_validator(mode="after")
    def _a_kind_or_a_model(self) -> "ValidationResult":
        if self.kind is None and not self.model:
            raise ValueError("a validation result needs a cross-section kind or a model")
        return self

    @property
    def key(self) -> str:
        """The label of the comparison: the kind, or the model."""
        return self.model or self.kind.value

    @property
    def ratios(self) -> list[float]:
        """Reproduced over published, at each mass."""
        return [r / p for r, p in zip(self.reproduced_cm2, self.published_cm2)]

    @property
    def point_passes(self) -> list[bool]:
        """Whether each mass passes, by its ratio or by the edge clause."""
        edges = self.edge_passes or [False] * len(self.masses_gev)
        return [1.0 / self.tolerance <= r <= self.tolerance or e for r, e in zip(self.ratios, edges)]

    @property
    def passed(self) -> bool:
        """Whether every tested mass passes."""
        return bool(self.ratios) and all(self.point_passes)

    @property
    def strongest_mass_gev(self) -> float | None:
        """The tested mass where the published limit is strongest."""
        if not self.masses_gev:
            return None
        return self.masses_gev[min(range(len(self.masses_gev)), key=lambda i: self.published_cm2[i])]

    def _runs(self) -> list[tuple[int, int]]:
        """The contiguous runs of passing masses, as (first, last) indices."""
        runs: list[tuple[int, int]] = []
        for i, ok in enumerate(self.point_passes):
            if ok and runs and runs[-1][1] == i - 1:
                runs[-1] = (runs[-1][0], i)
            elif ok:
                runs.append((i, i))
        return runs

    @property
    def validated_range(self) -> tuple[float, float] | None:
        """The validated masses (GeV), or None if no mass passes."""
        runs = self._runs()
        if not runs:
            return None
        best = self.masses_gev.index(self.strongest_mass_gev)
        around = [r for r in runs if r[0] <= best <= r[1]]
        low, high = around[0] if around else max(
            runs, key=lambda r: self.masses_gev[r[1]] / self.masses_gev[r[0]])
        return self.masses_gev[low], self.masses_gev[high]

    @property
    def counts_for_gate(self) -> bool:
        """Whether the validated range holds the strongest published limit and is wide enough.

        Along mass it must span a decade; along any other variable (a mass
        splitting, which starts at zero) at least half of the tested range.
        """
        span, best = self.validated_range, self.strongest_mass_gev
        if span is None or best is None or not span[0] <= best <= span[1]:
            return False
        if self.variable.startswith("mass"):
            return span[0] > 0 and span[1] / span[0] >= 10.0
        return span[1] - span[0] >= 0.5 * (max(self.masses_gev) - min(self.masses_gev))


# --- complementary constraints -------------------------------------------------------


class ConstraintClass(str, Enum):
    """The kind of measurement a constraint comes from."""

    direct_detection = "direct_detection"
    solar_capture = "solar_capture"
    indirect_detection = "indirect_detection"
    relic_density = "relic_density"
    collider = "collider"
    beam_dump = "beam_dump"
    flavour = "flavour"
    cosmology = "cosmology"


TIER_OF_CLASS = {
    ConstraintClass.direct_detection: 1,
    ConstraintClass.solar_capture: 2,
    ConstraintClass.indirect_detection: 3,
    ConstraintClass.relic_density: 3,
    ConstraintClass.collider: 3,
    ConstraintClass.beam_dump: 3,
    ConstraintClass.flavour: 3,
    ConstraintClass.cosmology: 3,
}


class FigureRef(StrictModel):
    """Where a record's data can be compared with its source: a page of an arXiv paper."""

    arxiv: str                        # e.g. "1903.06248"
    page: int = Field(default=1, ge=1)
    label: str = ""                   # e.g. "Fig. 3(a)"


class VerificationStamp(StrictModel):
    """A retained human approval and the scientific payload it was bound to."""

    on: date
    by: str
    payload_sha256: str = ""


class ConstraintRecord(StrictModel):
    """One entry of the curated constraint database.

    A record is used only once a person has verified it (``verified_on``).
    Its ``assumptions`` are the model assumptions under which the published
    constraint holds.
    """

    id: str = Field(default_factory=_new_id)
    name: str
    constraint_class: ConstraintClass
    source: str                       # a DOI or arXiv identifier
    data_file: str = ""
    assumptions: list[str] = Field(default_factory=list)
    verified_on: date | None = None
    verified_by: str = ""
    verification_sha256: str = ""
    verification_history: list[VerificationStamp] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    quantity: str = ""                # what is bounded, e.g. "sigma_v_cm3_s by channel"
    confidence_level: float | None = Field(default=None, gt=0, lt=1)
    statistical_construction: str = "see cited source; no likelihood conversion assumed"
    data: dict[str, float] = Field(default_factory=dict)       # small values held inline
    benchmark: str = ""               # set when the record holds for one model only
    checks: list[str] = Field(default_factory=list)            # machine checks of the transcription
    notes: str = ""                   # the reviewer's notes (Markdown): where each stored value is in its source, …;
                                      # documentation, outside the signed scientific payload (review_identity)
    figure: FigureRef | None = None   # the source figure (or table) to compare the data with

    @property
    def tier(self) -> int:
        """1: the operator alone decides; 2: needs an annihilation channel; 3: a completion."""
        return TIER_OF_CLASS[self.constraint_class]

    @property
    def usable(self) -> bool:
        """Whether the human approval still applies to the scientific payload."""
        from adroit.constraints.review_identity import signature_status
        return signature_status(self).usable


class Applicability(str, Enum):
    """Whether a constraint can be applied to a model as it stands."""

    applies = "applies"
    applies_with_assumptions = "applies_with_assumptions"
    needs_calculation = "needs_calculation"


class ConstraintVerdict(StrictModel):
    """What one constraint says about one model.

    ``excluded`` is None when the constraint cannot be applied without a
    further calculation, which ``needed_calculation`` then names: the system
    states what it cannot conclude.
    """

    constraint_id: str
    interaction_id: str
    applicability: Applicability
    excluded: bool | None = None
    assumptions: list[str] = Field(default_factory=list)
    needed_calculation: str = ""
    note: str = ""
    confidence_level: float | None = None
    native_excluded: bool | None = None

    @model_validator(mode="after")
    def _a_verdict_matches_its_applicability(self) -> "ConstraintVerdict":
        if self.applicability is Applicability.needs_calculation:
            if self.excluded is not None:
                raise ValueError("a constraint that needs a calculation gives no verdict yet")
            if not self.needed_calculation:
                raise ValueError("name the calculation that is needed")
        if self.applicability is Applicability.applies_with_assumptions and not self.assumptions:
            raise ValueError("state the assumptions under which the constraint applies")
        return self
