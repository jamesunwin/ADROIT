"""Scans of a model's parameter space against every computed constraint (DM13).

A scan is a grid over two parameters (a ``Point``'s masses or couplings, each
on a linear or logarithmic axis), the others held fixed. At each point:
- **the relic density** Ωh² (thermal freeze-out);
- **direct detection**: the model's cross-section against the strongest
  validated limit of the system's own modules at that mass, of the matching
  kind (``limits.at95`` evaluates the module procedure at 95%);
- **gamma rays from dwarf galaxies** (Fermi-LAT's curated record): a supported pure-channel ratio;
- **capture in the Sun** (IceCube's curated record): the capture rate times
  the equilibrium fraction against the rate the limit allows;
- **colliders**: CMS's curated record, only where the model is one of its
  benchmarks (the Working Group's couplings); otherwise not applicable, and
  said so;
- **perturbativity**: a coupling above √(4π).

Each constraint's verdict at a point is True (excluded), False (allowed) or
None (not computed there). Points run in ``worker_count`` processes (``ADROIT_SCAN_WORKERS``).
"""

from __future__ import annotations

import math
import os
from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
from pydantic import Field, field_validator, model_validator, JsonValue

from adroit.constraints.speeds import DWARF_SPEED, sun_speed   # one definition with Path 2's (AL3-33)
from adroit.core.dm_state import ConstraintVerdict, DarkMatterParticle
from adroit.core.halo_choice import FixedHalo
from adroit.core.state import StrictModel
from adroit.core.theory import ScalarVacuumCertificate,ScalarUnitarityCertificate
from adroit.core.certificate import Versions
from adroit.core.checkpoint import Checkpoint, CheckpointMismatch
from adroit.constraints import relic
from adroit.constraints.searches import _bundled as s_bundled, admits as s_admits, confirmed, records_used, \
    unverified_used
from adroit.constraints.indirect import SpectralComparison, fermi_mixture, spectral_comparison
from adroit.constraints.dwarf_likelihood import SpectralLimit
from adroit.parameter_space import dd_channels, halo_limits, halo_region, limits, relations, searches
from adroit.parameter_space.dd_channels import ChannelOutcome
from adroit.parameter_space.relations import CouplingRelation
from adroit.parameter_space.classes import Point, ScalarClass, Spin1Class, fermi_ratio
from adroit.parameter_space.flavour_vector import FlavourVectorClass
from adroit.parameter_space.portals.scalar_potential import CompleteScalarPortal
from adroit.parameter_space.portals.higgs import HiggsPortalFermion, HiggsPortalScalar, HiggsPortalVector, SingletMixing
from adroit.parameter_space.portals.multiplet import ElectroweakMultiplet
from adroit.parameter_space.portals.nplet import ElectroweakNplet
from adroit.parameter_space.portals.tchannel import TChannel
from adroit.parameter_space.portals.ufo import UFOPortal
from adroit.parameter_space.portals.generic import GenericModel
from adroit.parameter_space.portals.vector import ChargedZPrime, DarkPhoton, InelasticDarkPhoton, ZPortal
from adroit.core.private_limits import BoundPrivateLimit
from adroit.core.private_searches import BoundPrivateSearch
from adroit.core.running import ScalarRGCertificate
from adroit.core.chemical_equilibrium import ChemicalEquilibriumCertificate

ModelClass = (FlavourVectorClass | Spin1Class | ScalarClass | CompleteScalarPortal | HiggsPortalScalar | HiggsPortalFermion | HiggsPortalVector | SingletMixing
              | InelasticDarkPhoton | DarkPhoton | ZPortal | ChargedZPrime | TChannel | ElectroweakMultiplet | ElectroweakNplet
              | UFOPortal | GenericModel)

FERMI = "fermi-1503.02641-dsph"
HIGGS_INVISIBLE, Z_INVISIBLE = "atlas-2301.10731-hinv", "lep-hep-ex-0509008-zinv"
INVISIBLE_H, INVISIBLE_Z = "invisible Higgs width (ATLAS)", "invisible Z width (LEP)"
ICECUBE = "icecube-1612.05949-sd"
PARAMETERS = ("m_chi", "m_med", "g_chi", "g_q", "g_l")


class Axis(StrictModel):
    """One scan axis: the ``Point`` slot it varies, its range and number of values, logarithmic or linear."""
    parameter: str
    low: float
    high: float
    log: bool = True
    n: int = Field(default=24, ge=2, le=200)

    def values(self) -> list[float]:
        """The axis's n values from low to high, geometrically or linearly spaced; ValueError for a slot a ``Point``
        does not have."""
        if self.parameter not in PARAMETERS:
            raise ValueError(f"unknown parameter {self.parameter!r}; scan one of {', '.join(PARAMETERS)}")
        grid = np.geomspace(self.low, self.high, self.n) if self.log else np.linspace(self.low, self.high, self.n)
        return grid.tolist()



class DiscoveryPending(StrictModel):
    """An unresolved constraint-discovery requirement as a scan applies it (``constraint_discovery.pending_spans``):
    an allowed point it covers is pending, never excluded (the stacked audit's S18-03)."""
    text: str
    m_chi: tuple[float, float] | None = None   # the requirement's declared mass range, GeV; None: everywhere
    outside: bool = False                      # it applies outside the ranges instead (beyond the surveyed domain)
    # the mediator-mass range (the fresh audit's F19-04); left out when absent, so earlier requests keep their identity
    m_med: tuple[float, float] | None = Field(default=None, exclude_if=lambda v: v is None)

    def applies(self, m_chi: float | None, m_med: float | None = None) -> bool:
        """Whether it covers a point (an unknown coordinate on a declared range: yes): inside every declared range, or,
        for ``outside``, outside at least one."""
        spans = [(span, value) for span, value in ((self.m_chi, m_chi), (self.m_med, m_med)) if span is not None]
        if not spans or any(value is None for _, value in spans):
            return True
        return all(low <= value <= high for (low, high), value in spans) != self.outside


class ScanRequest(StrictModel):
    """A scan's inputs: the model class, the fixed point, the two axes, the relic fraction, and the relations,
    records and private limits and searches it applies."""
    model_class: ModelClass
    fixed: Point
    x: Axis
    y: Axis
    relic_fraction: float = 1.0          # of Ωh² = 0.12 (thermal freeze-out)
    workers: int = Field(default=2, ge=1, le=256)
    mediator_ratio: float | None = Field(default=None, gt=0, allow_inf_nan=False)  # m_med = ratio × m_χ
    unverified_records: bool = False     # use constraint records no person has verified yet
    private_limits: list["BoundPrivateLimit"] = Field(default_factory=list)
    private_searches: list[BoundPrivateSearch] = Field(default_factory=list)
    # couplings the model ties together (``relations``), imposed at every point; left out of the request's
    # serialised form when there are none, so earlier requests keep their identity
    coupling_relations: list[CouplingRelation] = Field(default_factory=list, exclude_if=lambda v: not v)
    # the propagation model for charged cosmic-ray bounds (``constraints.propagation``); None: the setting. Left out
    # of the serialised form when unset, so earlier requests keep their identity
    propagation: str | None = Field(default=None, exclude_if=lambda v: v is None)
    # the generic route for the same model (the owner, 2026-10-15): it computes a point the model class refuses by
    # its own domain, where both axes are masses (``engine_for``). Left out of the serialised form when unset
    fallback_class: GenericModel | None = Field(default=None, exclude_if=lambda v: v is None)
    # the halo region every point is evaluated over (``halo_region``), or the fixed benchmark every point is calculated
    # at (``halo_choice.FixedHalo``); None: each experiment's published halo (the reproduction mode, and every earlier
    # request)
    halo: halo_region.HaloPreset | FixedHalo | None = Field(default=None, exclude_if=lambda v: v is None)
    # a pinned discovery assessment's unresolved requirements, applied to every evaluated point before the verdict
    # (S18-03); left out of the serialised form when there are none
    discovery: list[DiscoveryPending] = Field(default_factory=list, exclude_if=lambda v: not v)

    @field_validator("propagation")
    @classmethod
    def _known_propagation(cls, value: str | None) -> str | None:
        from adroit.constraints.propagation import normalise
        return None if value is None else normalise(value)

    @model_validator(mode="after")
    def _independent_axes(self) -> ScanRequest:
        if self.x.parameter == self.y.parameter:
            raise ValueError("the two scan axes must be different parameters")
        relations.check(self.coupling_relations, (self.x.parameter, self.y.parameter))
        if self.mediator_ratio is not None and "m_med" in (self.x.parameter, self.y.parameter):
            raise ValueError("m_med cannot be a scan axis when mediator_ratio determines it")
        if isinstance(self.model_class,FlavourVectorClass) and any(a.parameter in ("g_q","g_l") for a in (self.x,self.y)):
            raise ValueError("flavour currents are fixed explicitly; g_q/g_l are not scan coordinates")
        if isinstance(self.model_class,CompleteScalarPortal) and (self.mediator_ratio is not None or any(
                a.parameter not in ("m_chi","g_chi") for a in (self.x,self.y))):
            raise ValueError("complete scalar family scans m_chi/lambda_HS only; the Higgs mediator is fixed")
        return self




RELIC_PENDING = "the relic density: "     # A06's pending reason (``PointResult.relic_validity``)


class PointResult(StrictModel):
    """Everything evaluated at one grid point: Ωh², the direct-detection comparison, each constraint's verdict, ratio
    and statistical construction, flags, pending searches and the scalar certificates."""
    point: Point
    photon_limit: SpectralLimit | None = None
    omega_h2: float | None
    dd_kind: str
    dd_sigma_cm2: float
    dd_limit_cm2: float | None
    excluded: dict[str, bool | None]      # constraint → verdict at this point
    values: dict[str, float] = Field(default_factory=dict)     # what a constraint compared, e.g. BR(h → inv)
    flags: list[str] = Field(default_factory=list)    # verdicts at this point that are unreliable
    pending: list[str] = Field(default_factory=list)  # searches that apply but are undecided here, with the reason
    # Ωh² from a thermal history outside the supported one (A06), apart from undecided searches: the scan's verdict
    # does not rest on it (the external audit of 2026-10-17, R17-4); absent from older results
    relic_validity: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)
    # the engine's own pending reasons here (``cls.pending``), saved when the point is evaluated so that a saved view
    # classifies the point without calling the model (the fresh audit's F19-07); None where the engine names none,
    # and in older results
    model_pending: list[str] | None = Field(default=None, exclude_if=lambda v: v is None)
    dd_ratio: float | None = None         # rate / 95% limit of a structure compared through Path 1 (``operator_limits``)
    ratios: dict[str, float] = Field(default_factory=dict)     # prediction / 95% limit, for the combined likelihood
    chi2: dict[str, float] = Field(default_factory=dict)       # Δχ² of a measurement (g − 2) at this point
    statistical_limits: dict[str, limits.StatisticalLimit] = Field(default_factory=dict)
    native_constraints: dict[str, searches.Outcome] = Field(default_factory=dict)
    search_results: list[searches.Outcome] = Field(default_factory=list)
    ratio_confidence_levels: dict[str, float | None] = Field(default_factory=dict)
    ratio_sidedness: dict[str, str] = Field(default_factory=dict)   # "one-sided"/"two-sided"/"unknown" per ratio
    dd_channels: list[ChannelOutcome] = Field(default_factory=list)   # every channel compared (R2)
    model_contract: dict[str,JsonValue] = Field(default_factory=dict)
    vacuum_certificate: ScalarVacuumCertificate | None = None
    unitarity_certificate: ScalarUnitarityCertificate | None = None
    running_certificate: ScalarRGCertificate | None = None
    chemical_certificate: ChemicalEquilibriumCertificate | None = None
    # the point over the halo region (``halo_evaluation``): every halo-dependent constraint at each sample; absent in
    # the published-halo reproduction and in older results
    halo: halo_region.HaloEvaluation | None = Field(default=None, exclude_if=lambda v: v is None)
    # the unverified records its constraints used, where the run enabled them (``searches.admits``; the owner's
    # direction D-4): a conclusion resting on the point says it depends on them; absent where none, and in older results
    unverified_records: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)
    # every record its constraints used, verified or not, with the version they used (``searches.admits``,
    # ``searches.confirmed``; "" where it is not known): what a claim resting on the point is bound to (the auditor's CR
    # recheck, CS-02, 2026-10-27; CS recheck, CT-01, 2026-10-28); absent where none, and in older results (a list of
    # ids before CT-01, read as versions not known)
    records: Versions = Field(default_factory=dict, exclude_if=lambda v: not v)


class ScanResult(StrictModel):
    """A scan's request, its axis values and the result at every grid point (row-major: y outer, x inner)."""
    request: ScanRequest
    xs: list[float]
    ys: list[float]
    points: list[PointResult]             # row-major: y outer, x inner
    notes: list[str] = Field(default_factory=list)


def _point_at(request: ScanRequest, x: float, y: float) -> Point:
    """Construct a grid or contour point: fixed values, then axes, then mass and coupling relations."""
    p = request.fixed.model_copy(update={request.x.parameter: x, request.y.parameter: y})
    if request.mediator_ratio is not None:
        p = p.model_copy(update={"m_med": request.mediator_ratio * p.m_chi})
    return relations.apply(p, request.coupling_relations)


def _fermi_limits() -> dict:
    """Fermi-LAT's dwarf limits, channel by channel, as read now (``constraints.searches._bundled``: the values and
    the version noted for the evaluation from one read). A cache kept for the process had gone on giving the old curve
    after its file changed, while the certificate bound the new one (the auditor's CT recheck, CU-01, 2026-10-28)."""
    return s_bundled(FERMI)["limits"]


def _icecube_limits() -> dict:
    """IceCube's limits on the SD-proton cross section, channel by channel, as read now (``_fermi_limits``)."""
    return s_bundled(ICECUBE)["limits"]["SD_proton"]["limits_cm2"]


def _soft_neutrinos() -> frozenset[str]:
    """Channels whose products stop in the Sun before decaying (the IceCube mixture rule's no-signal list)."""
    from adroit.constraints import mixtures
    return frozenset(mixtures.rule(ICECUBE)["none"]["channels"])


SOFT_NEUTRINOS = _soft_neutrinos()


def _icecube_applies(cls, p: Point) -> bool:
    """Whether IceCube's search of the Sun constrains the point at all: the dark matter lies in its curves' mass
    range and annihilates today into a channel with neutrinos above the detector's threshold. Light quarks, gluons,
    electrons and photons give none, and muons stop in the Sun before decaying. At the physical mass
    (``searches.dm_mass``), as every other indirect search (AL2-18)."""
    low = min(curve[0][0] for curve in _icecube_limits().values())
    if searches.dm_mass(cls, p) < low:
        return False
    sun = cls.sigma_v_today(p, sun_speed(searches.dm_mass(cls, p)))
    return any(rate > 0 and name not in SOFT_NEUTRINOS for name, rate in sun.items())


def _icecube(cls, p: Point) -> tuple[bool | None, float | None, str]:
    """(excluded, ratio, why) of IceCube's search of the Sun, by the conservative mixture rule
    (``constraints.mixtures``): the annihilation rate at capture equilibrium compared channel by channel, at the
    physical mass (``searches.dm_mass``; AL2-18: it had been the Lagrangian m_χ)."""
    from adroit.constraints import capture, database, mixtures, verdicts
    m = searches.dm_mass(cls, p)
    if unknown := searches.today_unknown(cls, p):
        return None, None, unknown
    if isinstance(cls,FlavourVectorClass) and cls.spectrum_reference_reason(p):
        return None, None, cls.spectrum_reference_reason(p)
    sun = cls.sigma_v_today(p, sun_speed(m))
    total = sum(v for v in sun.values() if v > 0)
    if total <= 0:
        return None, None, "no annihilation today"
    if not capture.available():                       # never downloaded mid-calculation (the fallback review's D3)
        return None, None, capture.UNAVAILABLE
    particle = DarkMatterParticle(mass_gev=m)
    rate = capture.capture_rate(particle, cls.interaction(p), halo=halo_limits.capture_halo())  # at a region's halo
    conjugate = bool(cls.self_conjugate()) if callable(getattr(cls, "self_conjugate", None)) else False
    annihilating = rate * capture.equilibrium_fraction(rate, total, m, self_conjugate=conjugate) / total   # per ⟨σv⟩

    def per_rate(curve: str) -> float | None:
        sigma = database.interpolate_limit(_icecube_limits()[curve], m)
        if sigma is None:
            return None
        allowed = capture.capture_rate(particle, verdicts._reference("SD_proton", sigma, m))
        return annihilating / allowed if allowed > 0 else None

    found = mixtures.bound(ICECUBE, sun, m, per_rate)
    return found.excluded, found.ratio, found.why()             # decided too: by an approximation (NA15-07)


def _fermi_mixture(cls, p: Point, channels: dict[str, float],
                   unverified: bool) -> tuple[float | None, SpectralComparison]:
    """A mixture against the dwarfs: the verified 2015 curves by the conservative mixture rule when it decides,
    else the separate 2024 spectral recast (never both: their data overlap). At the physical mass
    (``searches.dm_mass``; AL2-18: the mixture had been read at the Lagrangian m_χ, 2.887 for 2.598 at 114 GeV)."""
    conjugate = cls.self_conjugate() if hasattr(cls, "self_conjugate") else False
    curves = {k: v["limit_cm3_s"] for k, v in _fermi_limits().items()}
    m = searches.dm_mass(cls, p)
    mixture = fermi_mixture(channels, m, curves, conjugate)
    if mixture.excluded is not None:
        return mixture.ratio, SpectralComparison(record_id=FERMI, why=mixture.why())     # its statement (AL4-12)
    spectral = spectral_comparison(channels, m, conjugate, unverified, cls, p)
    if spectral.ratio is None:
        spectral = spectral.model_copy(update={"why": f"{spectral.why}; the 2015 curves: {mixture.why()}"})
    return spectral.ratio, spectral


def _same_data(found: list, ratios: dict[str, float]) -> None:
    """Drop SModelS's ratio from the combined likelihood when its analysis is one a dedicated record already holds
    (``searches.SAME_ANALYSIS``): the same data counted once."""
    lhc = next((o for o in found if o.name == searches.LHC and o.ratio is not None), None)
    if lhc is not None and any(name in ratios and any(lhc.why.startswith(a) for a in analyses)
                               for name, analyses in searches.SAME_ANALYSIS.items()):
        ratios.pop(searches.LHC, None)


def _collider(cls: ModelClass, p: Point, unverified: bool = False) -> ConstraintVerdict | None:
    """Retain CMS's decision and domain reason; None for an unmatched benchmark. A record whose signature is stale
    or missing decides nothing unless ``unverified`` (audit M16)."""
    from adroit.constraints import database, verdicts
    completion = cls.completion(p)
    name = verdicts.benchmark_of(completion) if completion is not None else None
    if name is None:
        return None
    candidate = verdicts.Candidate(label="scan", particle=DarkMatterParticle(mass_gev=p.m_chi),
                                   interaction=cls.interaction(p), completion=completion)
    record = database.record(f"cms-2405.13778-{name}")
    if not s_admits(record, unverified):
        return verdicts._needs(record, candidate, "a person's verification of its record (its signature is stale "
                                                  "or missing)")
    return verdicts.collider(candidate, record)


def _invisible(cls, p: Point, unverified: bool) -> tuple[dict[str, bool | None], dict[str, float]]:
    """The Higgs and Z widths into dark matter against their records (only those a person verified, unless asked)."""
    from adroit.constraints import database, higgs
    widths = cls.invisible(p) if hasattr(cls, "invisible") else {}
    excluded, values = {}, {}
    if "h" in widths:
        record = database.record(HIGGS_INVISIBLE)
        # ATLAS limits σ × BR(inv)/σ_SM: with SM couplings scaled by s (cos²θ for a mixed singlet) that is
        # s Γ_inv/(s Γ_SM + Γ_inv); s = 1 for every other model.
        s = cls.higgs_coupling_scale(p) if hasattr(cls, "higgs_coupling_scale") else 1.0
        br = s * widths["h"] / (s * higgs.GAMMA_H + widths["h"])
        values["BR(h → invisible)"] = br
        excluded[INVISIBLE_H] = br > record.data["br_limit"] if s_admits(record, unverified) else None
    if "Z" in widths:
        record = database.record(Z_INVISIBLE)
        values["Γ(Z → invisible, new) (MeV)"] = 1e3 * widths["Z"]
        excluded[INVISIBLE_Z] = 1e3 * widths["Z"] > record.data["width_limit_mev"] if s_admits(record, unverified) else None
    return excluded, values


def _ratio_level(name: str, stats: dict, found: list) -> float | None:
    """The confidence level of a ratio's limit, from its statistical record or its search outcome."""
    if name in stats:
        return stats[name].confidence_level
    chosen = searches.strongest([o for o in found if o.name == name])        # the outcome the verdict used (AL3-14)
    return chosen.confidence_level if chosen is not None else None


def _ratio_sidedness(name: str, stats: dict) -> str:
    """A ratio's construction: a module's own (``limits.sidedness``); published upper limits one-sided."""
    if name == "direct detection":
        return stats[name].sidedness if name in stats else "unknown"
    return "one-sided"


def _invisible_ratios(values: dict[str, float], excluded: dict[str, bool | None]) -> dict[str, float]:
    """BR(h → inv)/limit and ΔΓ_Z/limit where those records were used."""
    from adroit.constraints import database
    out = {}
    if excluded.get(INVISIBLE_H) is not None:
        out[INVISIBLE_H] = values["BR(h → invisible)"] / database.record(HIGGS_INVISIBLE).data["br_limit"]
    if excluded.get(INVISIBLE_Z) is not None:
        out[INVISIBLE_Z] = values["Γ(Z → invisible, new) (MeV)"] / database.record(Z_INVISIBLE).data["width_limit_mev"]
    return out


class DirectDetection(StrictModel):
    """The direct-detection comparison at one point (``direct_detection``)."""

    kind: str                                  # the deciding channel, or a structure, or why there is none
    sigma_cm2: float
    limit_cm2: float | None                    # the deciding channel's 95% limit
    ratio: float | None                        # prediction / 95% limit, for the combined likelihood
    dd_ratio: float | None = None              # a structure's or an exact flavour current's rate / 95% limit
    excluded: bool | None
    pending: list[str] = Field(default_factory=list)
    statistic: limits.StatisticalLimit | None = None
    native90: limits.StatisticalLimit | None = None
    channels: list[ChannelOutcome] = Field(default_factory=list)


LIGHT_MEDIATOR_GEV = 1.0      # below: a mediator's momentum dependence matters at the searches' momentum transfers
LIGHT_MEDIATOR = "direct detection: a light mediator's momentum dependence is not in the envelope comparison"


def direct_detection(cls, p: Point, si_excluded_modules: tuple[str, ...] = ()) -> DirectDetection:
    """Every non-zero channel against its validated 95% limits (``dd_channels``), or a structure through Path 1.

    ``si_excluded_modules``: modules a selected private spin-independent result supersedes (SI only). Where the
    scattering's mediator is lighter than ``LIGHT_MEDIATOR_GEV``, the comparison's contact-limit rate is above the
    rate with the propagator 1/(q² + m²)²: an allowed point stays allowed, an excluded one is undecided with the reason,
    and the ratio is not combined (the second addendum to cycle 3, AL3-32, 2026-11-16: at m_med = 20 MeV and m_χ = 20 GeV
    the rate with the propagator is 0.03 of the contact one on xenon, and four classes said nothing).
    """
    found = _direct_detection(cls, p, si_excluded_modules)
    if not _light_mediator(cls, p):
        return found
    excluded, pending = light_mediator_rule(found.excluded, found.pending)
    return found.model_copy(update={"ratio": None, "dd_ratio": None, "excluded": excluded, "pending": pending})


def light_mediator_rule(excluded: bool | None, pending: list[str]) -> tuple[bool | None, list[str]]:
    """AL3-32's rule for a comparison through a mediator lighter than ``LIGHT_MEDIATOR_GEV``, at the centre and at
    every halo sample (the audit loop's AL4-01, 2026-11-16: the samples had kept the contact comparison): an allowed
    outcome stands, an excluded one is undecided with ``LIGHT_MEDIATOR``; the caller combines no ratio."""
    if excluded:
        return None, [*pending, LIGHT_MEDIATOR]
    return excluded, list(pending)


def _light_mediator(cls, p: Point) -> bool:
    """Whether the scattering is through a mediator lighter than ``LIGHT_MEDIATOR_GEV``: m_med of the classes whose
    direct detection goes through it (a spin-1 or scalar mediator, a charged Z′, the singlet's h₂, the dark photon)."""
    from adroit.parameter_space.portals.higgs import SingletMixing
    from adroit.parameter_space.portals.vector import ChargedZPrime, DarkPhoton
    return isinstance(cls, (Spin1Class, ScalarClass, ChargedZPrime, SingletMixing, DarkPhoton)) and \
        p.m_med < LIGHT_MEDIATOR_GEV


def _direct_detection(cls, p: Point, si_excluded_modules: tuple[str, ...] = ()) -> DirectDetection:
    """The comparison itself (``direct_detection``)."""
    m_dm = searches.dm_mass(cls, p)          # the physical dark-matter mass (the audit's G3/G4-4, G12)
    from adroit.parameter_space import operator_limits
    kind, sigma = cls.dd(p)
    if kind in limits.DD_KINDS:
        channels = dd_channels_of(cls, p, kind, sigma)
        found = dd_channels.compare(channels, m_dm, si_excluded_modules)
        best = found.decisive
        native = limits.StatisticalLimit(value=limits.envelope(best.kind, m_dm), confidence_level=.9,
                                         source=limits.setter(best.kind, m_dm),
                                         construction="native published-curve validation envelope (retained separately)")
        # the likelihood takes a band's lower end, so it never excludes where the cuts leave a band pending, and
        # never a channel whose prediction is not computable (AL1-01)
        ratio = found.combinable
        combined = found.combined_channel or best           # the ratio's construction is its channel's (AL3-07)
        return DirectDetection(kind=best.kind, sigma_cm2=best.sigma_cm2, excluded=found.excluded,
                               limit_cm2=best.limit.value if best.limit else None, ratio=ratio,
                               pending=found.pending, statistic=combined.limit, native90=native,
                               channels=found.channels)
    dd_ratio, statistic, pending = None, None, []
    if kind in operator_limits.STRUCTURES:
        dd_ratio, statistic = operator_limits.ratio95(kind, m_dm, sigma), operator_limits.limit95(kind, m_dm)
    if isinstance(cls, FlavourVectorClass) and cls.universal_point(p) is None:
        statistic = cls.dd_statistical_limit(p)
        dd_ratio = (1 / statistic.value ** 2) if statistic.value is not None and statistic.value > 0 else (
            0.0 if p.g_chi == 0 and statistic.source else None)
    if statistic is not None:
        pending += [f"direct detection ({name}): {why}" for name, why in statistic.omitted.items()]
    excluded = None if dd_ratio is None else dd_ratio > 1.0
    if excluded is False and limits.excludes_only(statistic):       # D1: a maximum-gap limit never allows (C21-04)
        excluded = None
    return DirectDetection(kind=kind, sigma_cm2=sigma, limit_cm2=None, ratio=dd_ratio, dd_ratio=dd_ratio,
                           excluded=excluded, pending=pending, statistic=statistic)


def dd_channels_of(cls, p: Point, kind: str, sigma: float) -> list[dd_channels.Channel]:
    """The channels a point scatters through, for a kind the modules compare (none for any other)."""
    if kind not in limits.DD_KINDS:
        return []
    return cls.dd_channels(p) if hasattr(cls, "dd_channels") else [dd_channels.Channel(kind=kind, sigma_cm2=sigma)]


def _superseded(private_limits: list | None, private_searches: list | None) -> tuple[str, ...]:
    """The modules a selected private limit or private search supersedes (validated selection first)."""
    from adroit.parameter_space.private_limits import validate_selection
    excluded_modules=validate_selection(private_limits or [])
    if private_searches:
        excluded_modules=tuple(sorted(set(excluded_modules)|{t for b in private_searches for t in b.contract.supersedes}))
    return excluded_modules


def _gamma_rays(cls: ModelClass, p: Point, unverified: bool) -> tuple[float | None, SpectralComparison]:
    """(prediction / limit, the spectral comparison) against the Fermi-LAT dwarfs; None where undecided."""
    m_dm = searches.dm_mass(cls, p)          # the physical dark-matter mass (the audit's G3/G4-4, G12)
    channels = cls.sigma_v_today(p, DWARF_SPEED)
    indirect_reason = searches.today_unknown(cls, p) or (
        cls.spectrum_reference_reason(p) if isinstance(cls,FlavourVectorClass) else "")
    from adroit.constraints import database
    fermi_gate = "" if s_admits(database.record(FERMI), unverified) else \
        "its record (Fermi-LAT 2015) awaits a person's verification"               # audit M16: the verification gate
    ratio = None if (indirect_reason or fermi_gate) else cls.fermi(channels, m_dm, _fermi_limits()) if hasattr(cls, "fermi") \
        else fermi_ratio(channels, m_dm, _fermi_limits())
    spectral = SpectralComparison(why=indirect_reason or fermi_gate)
    if ratio is None and not (indirect_reason or fermi_gate):
        ratio, spectral = _fermi_mixture(cls, p, channels, unverified)
    return ratio, spectral


def _sun(cls: ModelClass, p: Point, unverified: bool) -> searches.Outcome:
    """IceCube's search of the Sun at 95% (its record awaits verification unless ``unverified``)."""
    from adroit.constraints import database
    ice_gate = "" if s_admits(database.record(ICECUBE), unverified) else \
        "its record (IceCube 2016) awaits a person's verification"
    sun_excluded, sun, sun_why = (None, None, ice_gate) if ice_gate else _icecube(cls, p)
    return searches.Outcome(
        name="capture in the Sun (IceCube)", excluded=sun_excluded, ratio=sun, why=sun_why,
        confidence_level=0.9, source=ICECUBE).at95()


def _pending(cls: ModelClass, p: Point, dd: DirectDetection, ice: searches.Outcome, applies: bool,
             collider: ConstraintVerdict | None, ratio: float | None, spectral: SpectralComparison) -> list[str]:
    """The constraints that apply here but are undecided, with the reason (before the library's searches)."""
    pending = [f"capture in the Sun (IceCube): {ice.why}"] if applies and ice.excluded is None else []
    if isinstance(cls, (FlavourVectorClass, TChannel, GenericModel)):
        pending += cls.pending(p)
    if collider is not None and collider.excluded is None:
        pending.append(f"colliders (CMS): {collider.needed_calculation}")
    if ratio is None:
        pending.append(f"Fermi-LAT dwarfs: {spectral.why}")
    pending += [reason for reason in dd.pending if reason not in pending]
    return pending


def _add_searches(found: list[searches.Outcome], native: dict[str, searches.Outcome],
                  excluded: dict[str, bool | None], values: dict[str, float], pending: list[str],
                  ratios: dict[str, float]) -> dict[str, float]:
    """Add the library's search outcomes to the point's verdicts, one per search name (``_by_name``); returns the Δχ²
    of the measurements."""
    chi2 = {}
    for outcome in _by_name(found):
        if outcome.confidence_level != 0.95:
            native[outcome.name] = outcome
        excluded[outcome.name] = outcome.excluded
        if outcome.value is not None:
            values[outcome.name] = outcome.value
        if outcome.excluded is None:
            pending.append(f"{outcome.name}: {outcome.why}")
        elif outcome.ratio is not None:
            ratios[outcome.name] = outcome.ratio
        if outcome.excluded is not None and outcome.delta_chi2 is not None:
            chi2[outcome.name] = outcome.delta_chi2
    return chi2


def _by_name(found: list[searches.Outcome]) -> list[searches.Outcome]:
    """One outcome per search name, in the order the names first appear. Where an evaluator gives one per mediator
    (the generic dilepton and L_μ − L_τ searches), the strongest: an exclusion if any (the largest ratio), else an
    undecided one naming every reason, else the allowed one with the largest ratio (AL2-05: a later outcome of the
    same name had overwritten an exclusion in the point's verdicts)."""
    groups: dict[str, list[searches.Outcome]] = {}
    for outcome in found:
        groups.setdefault(outcome.name, []).append(outcome)
    return [searches.strongest(group) for group in groups.values()]


def _point_flags(cls: ModelClass, p: Point, found: list[searches.Outcome]) -> list[str]:
    """The model's own flags, the searches' flags, and the edge of a completion's frame."""
    flags = list(cls.flags(p)) if hasattr(cls, "flags") else []
    flags += [flag for outcome in found for flag in outcome.flags if flag not in flags]
    if cls.completion(p) is not None:
        from adroit.constraints import verdicts
        if verdicts.near_frame(p.m_med, p.m_chi):
            flags.append(verdicts.EDGE_FLAG)
    return flags


def _statistics(cls: ModelClass, p: Point, dd: DirectDetection, spectral: SpectralComparison,
                excluded: dict[str, bool | None], ratios: dict[str, float]) -> dict[str, limits.StatisticalLimit]:
    """Each decided comparison's statistical construction: direct detection's, then the curated records'."""
    stats = {"direct detection": dd.statistic} if dd.statistic else {}
    if dd.native90:
        stats["direct detection (native 90%)"] = dd.native90
    from adroit.constraints import database
    source_ids = {"gamma rays (Fermi-LAT dwarfs)": FERMI, INVISIBLE_H: HIGGS_INVISIBLE, INVISIBLE_Z: Z_INVISIBLE}
    if spectral.limit is not None or spectral.why:
        source_ids["gamma rays (Fermi-LAT dwarfs)"] = spectral.record_id
    completion = cls.completion(p)
    if completion is not None:
        from adroit.constraints.verdicts import benchmark_of
        benchmark = benchmark_of(completion)
        if benchmark:
            source_ids["colliders (CMS)"] = f"cms-2405.13778-{benchmark}"
    for name, rid in source_ids.items():
        record = database.record(rid)
        if name in excluded:
            stats[name] = limits.StatisticalLimit(value=ratios.get(name), confidence_level=record.confidence_level,
                source=record.source, construction=("source SED spectral recast; value is prediction/profiled upper limit"
                    if name == "gamma rays (Fermi-LAT dwarfs)" and spectral.limit is not None else
                    "published 95% comparison; value is prediction/limit when available"))
    return stats


def _with_private(result: PointResult, cls: ModelClass, p: Point, private_limits: list | None,
                  private_searches: list | None) -> PointResult:
    """The point with the selected private limits, then the selected private searches, applied."""
    if private_limits:
        from adroit.parameter_space.private_limits import apply
        result=apply(result,cls,p,private_limits)
    if private_searches:
        from adroit.parameter_space.private_searches import apply as apply_searches
        result=apply_searches(result,cls,p,private_searches)
    return result


def evaluate(cls, p: Point, unverified: bool = False, lhc_result: dict | None = None,private_limits: list | None=None,
             private_searches:list|None=None) -> PointResult:
    """Every computed constraint at one point (``lhc_result``: SModelS's result, fetched in a batch). Over the halo
    region in force (``halo_region.using``): at its centre, with every halo-dependent constraint at each of its samples
    (``halo_evaluation``); at a fixed benchmark in force, at that halo (``halo_evaluation.at_benchmark``)."""
    preset = halo_region.preset()

    def nominal() -> PointResult:
        return _evaluate(cls, p, unverified, lhc_result, private_limits, private_searches)
    with unverified_used() as used, records_used() as every:   # the unverified records its constraints use (D-4),
        if preset is None:                                       # and every record they use (CS-02)
            result = nominal()
        elif isinstance(preset, FixedHalo):                      # one fixed benchmark (halo phase 1)
            from adroit.parameter_space import halo_evaluation
            result = halo_evaluation.at_benchmark(cls, p, preset, nominal)
        else:
            from adroit.parameter_space import halo_evaluation
            result = halo_evaluation.evaluate(cls, p, preset, nominal, unverified)
    found = {**({"unverified_records": sorted(used)} if used else {}),
             **({"records": confirmed(every)} if every else {})}        # as they were used (CT-01)
    return result.model_copy(update=found) if found else result


def _evaluate(cls, p: Point, unverified: bool, lhc_result: dict | None, private_limits: list | None,
              private_searches: list | None) -> PointResult:
    omega, unresolved = _relic_at(cls, p)
    dd = direct_detection(cls, p, _superseded(private_limits, private_searches))
    kind, sigma, limit, dd_ratio = dd.kind, dd.sigma_cm2, dd.limit_cm2, dd.dd_ratio
    perturbative = cls.perturbative(p) if hasattr(cls, "perturbative") else \
        max(abs(p.g_chi), abs(p.g_q), abs(p.g_l)) <= math.sqrt(4 * math.pi)
    collider = _collider(cls, p, unverified)
    excluded: dict[str, bool | None] = {
        "direct detection": dd.excluded,
        "gamma rays (Fermi-LAT dwarfs)": None,
        "capture in the Sun (IceCube)": None,
        "colliders (CMS)": collider.excluded if collider is not None else None,
        "perturbativity": not perturbative,
    }
    ratio, spectral = _gamma_rays(cls, p, unverified)
    excluded["gamma rays (Fermi-LAT dwarfs)"] = None if ratio is None else ratio > 1.0
    ratios = {"gamma rays (Fermi-LAT dwarfs)": ratio} if ratio is not None else {}
    if dd.ratio is not None:
        ratios["direct detection"] = dd.ratio
    native = {"capture in the Sun (IceCube)": _sun(cls, p, unverified)}
    # IceCube supplies native-90% curves: an allowed point is allowed at 95% too; a native exclusion is undecided.
    ice = native["capture in the Sun (IceCube)"]
    applies = _icecube_applies(cls, p)
    if applies:
        excluded["capture in the Sun (IceCube)"] = ice.excluded
    else:                                  # not applicable here: no entry, neither a verdict nor a pending reason
        excluded.pop("capture in the Sun (IceCube)", None)
    invisible, values = _invisible(cls, p, unverified)
    excluded.update(invisible)
    ratios.update(_invisible_ratios(values, invisible))
    pending = _pending(cls, p, dd, ice, applies, collider, ratio, spectral)
    validity = []
    if unresolved:
        pending.append(unresolved)
        validity.append(unresolved.removeprefix(RELIC_PENDING))
    if omega is not None and (history := relic.thermal_history_reason(lambda: cls.omega_h2(p),
                                                                     searches.dm_mass(cls, p), omega)):
        pending.append(f"{RELIC_PENDING}{history}")                      # the external audit's A06
        validity.append(history)
    found = searches.outcomes(cls, p, unverified, lhc_result)              # the library's searches, the CMB, the LHC
    chi2 = _add_searches(found, native, excluded, values, pending, ratios)
    _same_data(found, ratios)
    flags = _point_flags(cls, p, found)
    stats = _statistics(cls, p, dd, spectral, excluded, ratios)
    result=PointResult(point=p, omega_h2=omega, dd_kind=kind, dd_sigma_cm2=sigma, dd_limit_cm2=limit,
                       photon_limit=spectral.limit, **_certificates(cls, p),
                       excluded=excluded, values=values, flags=flags, pending=pending, ratios=ratios, chi2=chi2,
                       relic_validity=validity, dd_ratio=dd_ratio, native_constraints=native,
                       model_pending=list(cls.pending(p)) if hasattr(cls, "pending") else None,
                       statistical_limits=stats,
                       search_results=found, dd_channels=dd.channels,
                       ratio_confidence_levels={name: _ratio_level(name, stats, found) for name in ratios},
                       ratio_sidedness={name: _ratio_sidedness(name, stats) for name in ratios},
                       model_contract=(cls.point_potential(p).model_dump(mode="json") if isinstance(cls,CompleteScalarPortal)
                           else cls.model(p).model_dump(mode="json") if isinstance(cls,FlavourVectorClass) else {}))
    return _with_private(result, cls, p, private_limits, private_searches)


def _relic_at(cls, p: Point) -> tuple[float | None, str]:
    """(Ωh², "") or, where the solve did not finish, (None, its pending reason): never the yield where the
    integrator stopped."""
    try:
        return cls.omega_h2(p), ""
    except relic.RelicUnresolved as error:
        return None, f"{RELIC_PENDING}{error}"


def _certificates(cls, p: Point) -> dict:
    """A point's theory certificates, where its class issues them (``PointResult``'s fields)."""
    scalar = isinstance(cls, CompleteScalarPortal)
    return {"vacuum_certificate": cls.vacuum_certificate(p) if scalar else None,
            "unitarity_certificate": cls.unitarity_certificate(p) if scalar else None,
            "running_certificate": cls.running_certificate(p) if scalar and cls.running else None,
            "chemical_certificate": cls.chemical_certificate(p) if isinstance(cls, TChannel) else None}


MASS_AXES = frozenset({"m_chi", "m_med"})
GENERIC_FLAG = "computed by the generic route"        # the flag of a point the fallback computed (``engine_for``)


def engine_for(request: ScanRequest, p: Point) -> tuple[object, str]:
    """(the engine that computes point p, the flag saying so): the model class, or, where it refuses p by its own
    domain and both axes are masses, the request's generic fallback (if that computes p)."""
    cls, fallback = request.model_class, request.fallback_class
    if fallback is None or {request.x.parameter, request.y.parameter} - MASS_AXES:
        return cls, ""
    domain = cls.domain(p) if hasattr(cls, "domain") else ""
    if not domain or fallback.domain(p):
        return cls, ""
    return fallback, f"{GENERIC_FLAG}: outside the {type(cls).__name__} engine's domain ({domain})"


def _task(args: tuple) -> PointResult:
    """One point in a worker: (propagation model, halo region, the halo data files in force (``halo_choice.holding``:
    a worker reads the run's, or refuses), then ``evaluate``'s arguments)."""
    from adroit.constraints import propagation
    from adroit.core import halo_choice
    with propagation.using(args[0]), halo_region.using(args[1]), halo_choice.holding(args[2]):
        return evaluate(*args[3:])


def run(request: ScanRequest, checkpoint: Checkpoint | None = None) -> ScanResult:
    """Every point of the grid, in at most two worker processes."""
    from adroit.parameter_space.scan_setup import validate_axes
    validate_axes(request.model_class,request.x,request.y,request.mediator_ratio)
    xs, ys = request.x.values(), request.y.values()
    grid = [_point_at(request, x, y) for y in ys for x in xs]
    completed = {}
    if checkpoint:
        for i, point in enumerate(grid):
            row = checkpoint.load("scan", str(i), PointResult)
            if row is not None:
                if row.point != point:
                    raise CheckpointMismatch("Cached scan point differs from its declared inputs")
                completed[i] = row
        checkpoint.update("scan", len(completed), len(grid), "completed parameter points")
    pending = [i for i in range(len(grid)) if i not in completed]
    engines = {i: engine_for(request, grid[i]) for i in pending}
    lhc_results = {}
    for engine in {id(e): e for e, _ in engines.values()}.values():
        mine = [i for i in pending if engines[i][0] is engine]
        lhc_results |= dict(zip(mine, searches.prefetch_lhc(engine, [grid[i] for i in mine], request.unverified_records)))
    from adroit.core import halo_choice
    files = halo_choice.in_force()
    tasks = [(request.propagation, request.halo, files, engines[i][0], grid[i], request.unverified_records,
              lhc_results.get(i)) for i in pending]
    if request.private_searches:
        tasks=[(*task,request.private_limits,request.private_searches) for task in tasks]
    elif request.private_limits:
        tasks=[(*task,request.private_limits) for task in tasks]
    def record(index: int, row: PointResult) -> None:
        flag = engines[index][1] if index in engines else ""
        if flag and flag not in row.flags:
            row = row.model_copy(update={"flags": [*row.flags, flag]})
        completed[index] = row
        if checkpoint:
            checkpoint.save("scan", str(index), row)
            checkpoint.update("scan", len(completed), len(grid), "completed parameter points")
    if request.workers > 1:
        with one_thread_each(), ProcessPoolExecutor(max_workers=request.workers) as pool:
            futures = {pool.submit(_task, task): i for i, task in zip(pending, tasks)}
            for future in as_completed(futures):
                record(futures[future], future.result())
    else:
        for i, task in zip(pending, tasks):
            record(i, _task(task))
    points = [completed[i] for i in range(len(grid))]
    return ScanResult(request=request, xs=xs, ys=ys, points=points, notes=_scan_notes(points, request.halo))


def worker_count(requested: int) -> int:
    """The worker processes a scan uses: one where one was asked for (serial, as tests and resumed runs may ask), else
    the setting ``ADROIT_SCAN_WORKERS`` (default: the cores less two). The request's own field stays as it was written,
    so a run's checkpoint identity does not change with the machine (the owner, 2026-11-22: two workers had left most
    cores idle, and 8–12 hour scans)."""
    from adroit.core.config import get_settings
    return 1 if requested <= 1 else get_settings().scan_workers


THREAD_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
                    "NUMEXPR_NUM_THREADS")


@contextmanager
def one_thread_each():
    """While a pool of scan workers is open, each worker's numerical libraries use one thread (unless the person set
    these variables), so that several workers do not each start a thread per core and slow one another down."""
    set_here = [name for name in THREAD_VARIABLES if name not in os.environ]
    for name in set_here:
        os.environ[name] = "1"
    try:
        yield
    finally:
        for name in set_here:
            os.environ.pop(name, None)


def _scan_notes(points: list[PointResult], halo=None) -> list[str]:
    """The scan's notes on what its comparisons do not cover (``run``), and how its direct-detection limits were
    taken at its halo (``halo``, the request's): at a generated benchmark (SHM++) each module's own procedure with its
    table, never a precomputed table of the standard halo's limits (a halo phase 2 audit's HB-04, 2026-11-11: an SHM++
    scan's note had said its limits came from those tables, which it never read)."""
    notes = []
    if all(p.excluded["colliders (CMS)"] is None for p in points):
        notes.append("colliders: CMS's curated limits apply to its own benchmark couplings only; this model is "
                     "not one of them, so collider constraints are not evaluated")
    from adroit.parameter_space import limit_tables
    if isinstance(halo, FixedHalo) and halo.generated:
        notes.append(f"direct detection at {halo.benchmark} v{halo.version}: every search's 95% limit is its own "
                     "procedure with the benchmark's detector-frame table; no precomputed table and no count ratio "
                     "is used (they hold the standard halo's limits). The slow searches (the xenon searches, CDMSlite) "
                     f"take theirs within each point's budget of {halo.full_calculations} full calculations; beyond "
                     "it the comparison is pending, named at the point")
    used = limit_tables.current() if limits.tabulated() and not (isinstance(halo, FixedHalo) and halo.generated) \
        else []
    if used:
        notes.append("direct detection: the slow searches' 95% limits (the xenon searches, CDMSlite, PICO-60) "
                     "come from precomputed tables where they cover the mass "
                     f"({len(used)} current: {', '.join(used)}); a point whose verdict could change within a "
                     "table's stated accuracy is recomputed directly, so every verdict is the direct one "
                     "(--exact-limits: no tables)")
    if all(p.dd_limit_cm2 is None and p.dd_ratio is None for p in points):
        kinds = sorted({p.dd_kind for p in points} - {"SI", "SD-proton", "SD-neutron"})
        notes.append("direct detection: this interaction does not reduce to the spin-independent or "
                     f"spin-dependent kinds the scan compares ({', '.join(kinds) or 'outside the validated ranges'})")
    return notes
