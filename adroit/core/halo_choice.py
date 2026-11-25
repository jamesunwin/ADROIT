"""The halo a calculation uses: one typed request and resolution shared by Track 1, Explain a signal and Track 2 (halo
phase 1, ``docs/halo_phase_1_shared_configuration.md``).

Two choices are kept apart:

- **The family:** the form of the local velocity distribution, by a stable machine id. ``shm``, the Standard Halo
  Model (a truncated Maxwellian), is implemented. ``shm-plus-plus`` (SHM++: the round halo and the anisotropic Gaia
  Sausage, ``halo_models.shm_plus_plus``) is implemented as a fixed benchmark only (halo phase 2). ``shm-lmc`` (an
  LMC-affected benchmark) is registered as planned: asking for it is refused, never calculated as another family under
  its name.
- **The treatment:** how the calculation uses the halo.
  - ``region``: the SHM's declared uncertainty region (``halo_region.HaloPreset``), an envelope over the owner's
    working priors. Track 1's default, and Explain a signal's for its constraints and plane.
  - ``published``: each experiment's and record's own published halo, the reproduction its modules were validated in.
    Track 2's fits and null limits always work this way unless the benchmark is asked for.
  - ``benchmark``: one fixed common benchmark, a documented numerical distribution. Every comparison able to use it
    does; one that cannot is named, never computed at another halo. A fixed benchmark is not a confidence interval,
    and the halo's uncertainty is not propagated with it.

**A request** records its treatment as it did before phase 1, so that every earlier request keeps its identity:
- Track 1: a ``HaloPreset``, ``"published"``, or nothing in a request saved before the choice existed;
- Track 2: no field.

The fixed benchmark is a ``FixedHalo``: the benchmark's id, version and numerical values, copied when the request is
made. A later change to the registry never changes a saved request's physics. A generated benchmark (SHM++) also holds
its parameters, its numerical settings and its tables (the detector's and the Sun's, with their sha256): the snapshot
every calculation of the request uses, checked against its generator before it is used (``verify``).

**The family decides the snapshot's form** (``GENERATED``, ``FixedHalo.generated``): a generated family's snapshot holds
every generated field, a standard family's none of them, or it is not a ``FixedHalo`` at all (``_form``); and a
benchmark of another family is never calculated under this one's name (``verify``). A halo phase 2 audit (HB-01,
2026-11-11) had found the machinery chosen by whether the optional parameters were present: a snapshot naming SHM++
but holding a standard halo and no generator fields was calculated as the SHM under SHM++'s label.

**A calculation reads the halo data files it was resolved with** (``holding``, ``held``): the bytes whose sha256 its
resolution records, held from that reading, never a file read before or after it under another identity. The same
audit (HB-03) had found the local densities cached with no identity: a long-lived process that had read them once kept
their old values under a new resolution's sha256.

**``resolve``** turns any of these into a ``Resolution``. It is the immutable description that pages, reports, exports
and certificates show and bind. Its ``identity`` is the sha256 of its physical content: numbers, frame, time convention
and the halo data files it reads. Labels and prose are left out, so a change of wording never invalidates a
calculation, while a change of a number or of a data file's bytes does.

**A calculation's halo is its own** (``own``, ``intact``): ``resolve`` takes a copy of the value, nested values and all,
so a resolution shares no object with its caller; each run calculates with its own copy of its request; and at its end
the halo it calculated with must still resolve to its resolution's content, or nothing is published under it. The auditor's
halo phase 1 audit (HA-05, 2026-11-12) had found a resolution holding the request's own nested halo: a density changed
after the resolution was calculated with and saved, with the resolution's old identity and summary.

**What can use a treatment** (``CONSUMERS``): each halo-dependent comparison names the capabilities it needs and the
treatments it supports. One that cannot use the treatment in force gets a typed reason (``unsupported``), which the
calculation makes a named pending reason or a refusal. An independent exclusion still stands.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ConfigDict, Field, model_validator

from adroit.core.dm_state import HaloModel
from adroit.core.state import StrictModel
from adroit.halo_models import shm_plus_plus as shmpp
from adroit.halo_models.frames import SunFrameTable, frame_of

SCHEMA = 1
PACKAGE = Path(__file__).resolve().parents[1]


class Treatment(str, Enum):
    """How a calculation uses the halo (module docstring)."""
    region = "region"
    published = "published"
    benchmark = "benchmark"


class Capability(str, Enum):
    """What a family's distribution supplies to the comparisons that need it."""
    recoil = "recoil"                    # detector-frame velocity integrals η, η⊥: recoil rates for any operator
    solar = "solar"                      # a solar-frame distribution: capture in the Sun
    local_density = "local-density"      # the local density: the Galactic searches' fixed-profile rescaling
    count_ratio = "count-ratio"          # inside the SHM accepted-count ratio's validated domain (``halo_limits``)
    modulation = "annual-modulation"     # a time-dependent laboratory frame
    directional = "directional"          # the angular distribution in the laboratory
    pair_velocity = "pair-velocity"      # a pairwise relative-velocity distribution over a source region


CAPABILITY_TEXT = {
    Capability.recoil: "detector-frame velocity integrals (η, η⊥) for recoil rates",
    Capability.solar: "a solar-frame velocity distribution (capture in the Sun)",
    Capability.local_density: "a local density for the Galactic searches' fixed-profile rescaling",
    Capability.count_ratio: "the SHM accepted-count ratio's validated domain",
    Capability.modulation: "annual modulation",
    Capability.directional: "directional rates",
    Capability.pair_velocity: "a pairwise relative-velocity distribution over a source region",
}


class Family(StrictModel):
    """A registered family of local velocity distributions."""
    model_config = ConfigDict(frozen=True)
    id: str                              # stable machine id, never a display label
    label: str                           # the short label a form shows
    title: str
    available: bool
    status: str                          # what is implemented, or why it is not yet
    benchmark: str = ""                  # its fixed benchmark's id ("" while none is defined)
    capabilities: tuple[Capability, ...] = ()


class Benchmark(StrictModel):
    """A fixed benchmark: one documented numerical distribution, given (the SHM) or generated from its parameters at
    its numerical settings (SHM++)."""
    model_config = ConfigDict(frozen=True)
    id: str
    version: int
    family: str
    title: str
    source: str
    time: str                            # the time convention, in words
    halo: HaloModel | None = None
    parameters: shmpp.Parameters | None = None
    numerics: shmpp.Numerics | None = None


SHM_CAPABILITIES = (Capability.recoil, Capability.solar, Capability.local_density, Capability.count_ratio)
# SHM++: its tables give recoil rates and capture; no count ratio (a shape-changing distribution, outside the SHM ratio's
# validation), no modulation or directions (one instant's nondirectional distribution), no pair velocities
SHMPP_CAPABILITIES = (Capability.recoil, Capability.solar, Capability.local_density)

FAMILIES: dict[str, Family] = {
    "shm": Family(id="shm", label="SHM", title="Standard Halo Model", available=True, status="implemented",
                  benchmark="shm-2105.00599", capabilities=SHM_CAPABILITIES),
    "shm-plus-plus": Family(id="shm-plus-plus", label="SHM++",
                            title="SHM++ (Evans, O'Hare and McCabe, arXiv:1810.11468)", available=True,
                            status="implemented as a fixed benchmark (halo phase 2): the round halo and the Gaia "
                                   "Sausage, generated as detector- and Sun-frame tables",
                            benchmark="shmpp-1810.11468", capabilities=SHMPP_CAPABILITIES),
    "shm-lmc": Family(id="shm-lmc", label="SHM + LMC",
                      title="an LMC-affected benchmark (its source and definition still to be chosen)",
                      available=False,
                      status="not implemented yet (halo phase 3): the benchmark, its data and their terms are still "
                             "to be chosen and validated"),
}
DEFAULT_FAMILY = "shm"

BENCHMARKS: dict[str, Benchmark] = {
    "shm-2105.00599": Benchmark(
        id="shm-2105.00599", version=1, family="shm",
        title="the SHM at the recommended conventions of arXiv:2105.00599",
        source="Baxter et al., arXiv:2105.00599, Table 1 (ρ₀, v₀, v_esc, the Sun's peculiar velocity, v_LSR = v₀) and "
               "Eq. 12 (the Earth's velocity on 9 March); ADROIT's default HaloModel()",
        time="a fixed date: the Earth's velocity on 9 March, when the detector's speed equals its annual mean "
             "(arXiv:2105.00599, Eq. 12); no annual modulation",
        halo=HaloModel()),
    "shmpp-1810.11468": Benchmark(
        id="shmpp-1810.11468", version=1, family="shm-plus-plus",
        title="SHM++ at Table I of arXiv:1810.11468",
        source="Evans, O'Hare and McCabe, arXiv:1810.11468v3 (PRD 99, 023012): Eqs. 1–7 and Table I (ρ₀ = 0.55 GeV/cm³, "
               "v₀ = 233, v_esc = 528 km/s, β = 0.9, η = 0.2); the Sun's peculiar velocity (11.1, 12.24, 7.25) km/s and "
               "the instant of the authors' code (github.com/mccabech/SHMpp); the Earth's velocity by McCabe, "
               "arXiv:1312.1355 (docs/halo_shmplusplus.md)",
        time=shmpp.TIME, parameters=shmpp.BENCHMARK, numerics=shmpp.Numerics()),
}
# the families whose benchmark is generated from parameters as tables (SHM++): what decides a snapshot's form and the
# machinery it is calculated with, never which of its fields happen to be present (HB-01)
GENERATED = frozenset(f.id for f in FAMILIES.values()
                      if f.benchmark in BENCHMARKS and BENCHMARKS[f.benchmark].parameters is not None)
GENERATED_FIELDS = ("parameters", "numerics", "sun", "tables")
GENERATED_TEXT = {"parameters": "parameters", "numerics": "numerical settings", "sun": "Sun-frame table",
                  "tables": "tables' sha256"}

HALO_DATA = {    # the package's halo data files a treatment reads (``Resolution.data``)
    "local densities": "constraints/data/local_densities.yaml",
    "count-ratio validation": "parameter_space/data/halo_count_ratio.yaml",
    "count-ratio declaration": "parameter_space/data/halo_validation_points.yaml",
    # the targeted validation of 2026-11-24, beside the original (``halo_limits.validated``)
    "count-ratio targeted validation": "parameter_space/data/halo_count_ratio_targeted.yaml",
    "count-ratio targeted declaration": "parameter_space/data/halo_validation_points_targeted.yaml",
}
FRAME = "galactic"                       # a Galactic-frame distribution, boosted to the detector (or the Sun)
AXES = "galactic: toward the Galactic centre, along the rotation, toward the north pole"
UNITS = "km/s; GeV/cm³"
FIXED_DATE = "fixed date: 9 March (arXiv:2105.00599, Eq. 12)"


class UnknownHalo(ValueError):
    """A family, benchmark or treatment that is unknown or not available: nothing is calculated."""


def family(family_id: str) -> Family:
    """The registered family (any status), or ``UnknownHalo``."""
    found = FAMILIES.get(family_id)
    if found is None:
        raise UnknownHalo(f"{family_id!r} is not a halo family; the families are {', '.join(FAMILIES)}")
    return found


def available(family_id: str) -> Family:
    """The family if it can be calculated, else ``UnknownHalo`` naming why: a planned family is never run as another."""
    found = family(family_id)
    if not found.available:
        raise UnknownHalo(f"{found.label} ({found.id}) is {found.status}; nothing is calculated, and no other halo "
                          "stands in for it")
    return found


class FixedHalo(StrictModel):
    """A request's fixed common benchmark (``Treatment.benchmark``): the registry's values when the request was made.
    A generated benchmark's ``halo`` is its detector-frame table, ``sun`` the Sun's, with its parameters, numerical
    settings and the tables' sha256 as generated (absent from an SHM benchmark's record, which reads as before)."""
    model_config = ConfigDict(frozen=True)
    treatment: Literal["benchmark"] = "benchmark"
    schema_version: Literal[1] = 1
    family: str
    benchmark: str
    version: int
    halo: HaloModel
    # per Track 1 point: the slow modules' full procedures at this halo where no validated shortcut decides (as the
    # region's ``HaloPreset.full_calculations``); beyond it the comparison is pending, never taken at another halo
    full_calculations: int = Field(default=2, ge=0, le=64)
    sun: SunFrameTable | None = Field(default=None, exclude_if=lambda v: v is None)
    parameters: shmpp.Parameters | None = Field(default=None, exclude_if=lambda v: v is None)
    numerics: shmpp.Numerics | None = Field(default=None, exclude_if=lambda v: v is None)
    tables: dict[str, str] = Field(default_factory=dict, exclude_if=lambda v: not v)   # frame: sha256, as generated

    @model_validator(mode="after")
    def _of_its_family(self) -> FixedHalo:
        if why := _form(self):
            raise ValueError(why)
        return self

    @property
    def generated(self) -> bool:
        """Whether its family's distribution is generated from parameters as tables (SHM++), not a standard halo: by
        its family (``GENERATED``), whatever fields it holds."""
        return self.family in GENERATED

    def solar(self) -> HaloModel:
        """The halo capture in the Sun takes: a generated benchmark's Sun-frame table, or the standard halo, which
        capture boosts to the Sun itself."""
        if not self.generated:
            return self.halo
        if self.sun is None or frame_of(self.sun) != "sun":
            raise UnknownHalo(f"{self.benchmark}: no Sun-frame table; a detector's table is not the Sun's distribution")
        return self.sun

    def detector(self) -> HaloModel:
        """The halo a recoil rate takes: the standard halo, or a generated benchmark's detector-frame table."""
        if self.generated and frame_of(self.halo) != "detector":
            raise UnknownHalo(f"{self.benchmark}: its recoil table is not in the detector's frame")
        return self.halo


def _form(value: FixedHalo) -> str:
    """Why a snapshot is not of its family's form ("" when it is): a generated family's holds every generated field
    (its parameters, numerical settings, Sun-frame table and the two tables' sha256), a standard family's none."""
    if value.generated:
        missing = [GENERATED_TEXT[name] for name in GENERATED_FIELDS if not getattr(value, name)]
        if missing:
            return (f"{value.benchmark}: a snapshot of {family(value.family).label} without its {', '.join(missing)}: "
                    "refused, never calculated as another halo under its name")
        if set(value.tables) != {"detector", "sun"}:
            return (f"{value.benchmark}: its tables' sha256 name the frames {sorted(value.tables)}, not the detector "
                    "and the Sun")
        return ""
    extra = [GENERATED_TEXT[name] for name in GENERATED_FIELDS if getattr(value, name)]
    if extra:
        return (f"{value.benchmark}: a snapshot of {value.family}, a standard halo, holding a generated benchmark's "
                f"{', '.join(extra)}: refused")
    return ""


def fixed(family_id: str = DEFAULT_FAMILY, benchmark_id: str = "") -> FixedHalo:
    """The fixed benchmark of an available family (its default unless ``benchmark_id``), its values copied now; a
    generated one's tables generated now, once, and recorded with their sha256."""
    f = available(family_id)
    chosen = benchmark_id or f.benchmark
    found = BENCHMARKS.get(chosen)
    if found is None or found.family != f.id:
        raise UnknownHalo(f"{chosen!r} is not a benchmark of {f.label}; its benchmark is {f.benchmark or 'not defined'}")
    if found.parameters is None:
        return FixedHalo(family=f.id, benchmark=found.id, version=found.version, halo=found.halo.model_copy(deep=True))
    detector, sun = _generated(found.parameters, found.numerics, f.label)
    return FixedHalo(family=f.id, benchmark=found.id, version=found.version, halo=detector.model_copy(deep=True),
                     sun=sun.model_copy(deep=True), parameters=found.parameters, numerics=found.numerics,
                     tables={"detector": shmpp.sha256(detector), "sun": shmpp.sha256(sun)})


@lru_cache(maxsize=8)
def _generated(parameters: shmpp.Parameters, numerics: shmpp.Numerics, label: str) -> tuple[HaloModel, HaloModel]:
    return shmpp.tables(parameters, numerics, label)


def verify(value: FixedHalo) -> str:
    """Why a fixed benchmark's snapshot cannot be calculated with ("" when it can): it must be of its family's form
    (``_form``; checked again here, for a snapshot made without validation) and name a benchmark of its family; a
    generated benchmark's tables must have the bytes their sha256 records, and be its generator's output for its
    parameters at its numerical settings in their own frames (a table is an implementation of the declared
    distribution, never an anonymous replacement)."""
    if why := _form(value):
        return why
    found = BENCHMARKS.get(value.benchmark)
    if found is None or found.family != value.family:
        return (f"{value.benchmark!r} is not a benchmark of {value.family} (its benchmark is "
                f"{FAMILIES[value.family].benchmark if value.family in FAMILIES else 'not defined'})")
    if not value.generated:
        return ""
    actual = {"detector": shmpp.sha256(value.halo), "sun": shmpp.sha256(value.sun)}
    if actual != value.tables:
        return f"{value.benchmark}: a table's bytes are not those its recorded sha256 names"
    return _verified(value.parameters, value.numerics, actual["detector"], actual["sun"], value)


def _verified(parameters, numerics, detector_sha: str, sun_sha: str, value: FixedHalo) -> str:
    key = (parameters, numerics, detector_sha, sun_sha)
    if key not in _VERIFIED:
        why = shmpp.agrees(value.halo, parameters, "detector", numerics) or \
            shmpp.agrees(value.sun, parameters, "sun", numerics)
        _VERIFIED[key] = f"{value.benchmark}: its table is not its generator's output ({why})" if why else ""
    return _VERIFIED[key]


_VERIFIED: dict[tuple, str] = {}


def varied(value: FixedHalo, change: dict) -> HaloModel:
    """The benchmark's detector halo with one parameter changed, for a sensitivity flag (never the benchmark, never
    another family): the standard halo with the field changed, or a generated benchmark's table generated again at the
    changed parameter (its v_LSR moves with v₀, as SHM++ defines it). A table's own SHM fields are never edited: the
    rate code reads only its values."""
    if not value.generated:
        return value.halo.model_copy(update=change)
    parameters = shmpp.Parameters(**{**value.parameters.model_dump(), **change})
    return _generated(parameters, value.numerics, f"{family(value.family).label} sensitivity")[0]


class Component(StrictModel):
    """One component of a distribution and its weight in the local density."""
    id: str
    weight: float = Field(ge=0.0, le=1.0)


class Resolution(StrictModel):
    """The halo of a request, resolved once: what every page, report, export and certificate shows and binds (module
    docstring). ``identity`` excludes ``label`` and ``summary``, the display."""
    model_config = ConfigDict(frozen=True)
    schema_version: int = SCHEMA
    family: str
    treatment: Treatment
    recorded: bool = True                # False: a request saved before the choice existed, read by its schema
    benchmark: str = ""
    benchmark_version: int = 0
    halo: HaloModel | None = None        # the one distribution: the benchmark, or the region's centre
    components: list[Component] = Field(default_factory=list)
    frame: str = ""
    axes: str = ""
    units: str = ""
    time: str = ""
    region: dict = Field(default_factory=dict)          # the declared uncertainty region (``HaloPreset``)
    full_calculations: int | None = None                 # a benchmark's per-point budget (the region's is in ``region``)
    # a generated benchmark (SHM++): its parameters, numerical settings and each frame's table by its sha256 (the tables
    # themselves are in the request); absent from every other resolution's record, so their identities read as before
    parameters: dict = Field(default_factory=dict, exclude_if=lambda v: not v)
    numerics: dict = Field(default_factory=dict, exclude_if=lambda v: not v)
    tables: dict[str, str] = Field(default_factory=dict, exclude_if=lambda v: not v)
    data: dict[str, str] = Field(default_factory=dict)  # the halo data files read, by name: sha256 ("" missing)
    capabilities: list[Capability] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    spatial: str = ""
    limitations: list[str] = Field(default_factory=list)
    label: str = ""
    summary: str = ""
    identity: str = ""


def _physical(resolution: Resolution) -> dict:
    """The content its identity covers: every number, convention and data identity; no label or prose."""
    data = resolution.model_dump(mode="json", exclude={"label", "summary", "identity", "sources", "spatial",
                                                        "limitations", "capabilities"})
    if data.get("halo"):
        data["halo"].pop("label", None)
    data.get("region", {}).pop("label", None)
    return data


def identity_of(resolution: Resolution) -> str:
    """The sha256 of the resolution's physical content (canonical JSON)."""
    text = json.dumps(_physical(resolution), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


def _identified(resolution: Resolution) -> Resolution:
    return resolution.model_copy(update={"identity": identity_of(resolution)})


def equivalent(a: Resolution, b: Resolution) -> bool:
    """Whether two resolutions calculate with the same halo: the same treatment, family, benchmark, numbers and
    conventions, whatever their labels, their halo data files' identities (each run's own, as read) and whether the
    choice was recorded (a request saved before it existed was calculated with the published halos)."""
    def physical(r: Resolution) -> dict:
        data = _physical(r)
        data.pop("data", None)
        data.pop("recorded", None)
        return data
    return physical(a) == physical(b)


def data_identity(names: tuple[str, ...]) -> dict[str, str]:
    """The sha256 of each named halo data file as it is now ("" where it cannot be read), its bytes held from this
    reading (``held``)."""
    out = {}
    for name in names:
        data = _read(name)
        out[name] = "" if data is None else _hold(data)
    return out


# --- the halo data files a calculation reads (HB-03) ------------------------------------------------------------------

_HELD: OrderedDict[str, bytes] = OrderedDict()     # sha256 → bytes: the halo data files as they were read, a few each
_PARSED: OrderedDict[str, Any] = OrderedDict()     # sha256 → the YAML of those bytes
_HOLD_LOCK = threading.Lock()
HOLD = 16                                          # the versions held (each file is read anew on a miss)
_IN_FORCE: ContextVar[dict[str, str] | None] = ContextVar("adroit_halo_data", default=None)


def _read(name: str) -> bytes | None:
    try:
        return (PACKAGE / HALO_DATA[name]).read_bytes()
    except OSError:
        return None


def _hold(data: bytes) -> str:
    sha = hashlib.sha256(data).hexdigest()
    with _HOLD_LOCK:
        _HELD[sha] = data
        _HELD.move_to_end(sha)
        while len(_HELD) > HOLD:
            _HELD.popitem(last=False)
    return sha


@contextmanager
def holding(data: dict[str, str] | None):
    """Inside: the halo data files a calculation was resolved with (its ``Resolution.data``, file: sha256) are the ones
    it reads (``held``), in this thread and the tasks it gives its workers (``in_force``). None or {}: none in force."""
    token = _IN_FORCE.set(dict(data) if data else None)
    try:
        yield
    finally:
        _IN_FORCE.reset(token)


def in_force() -> dict[str, str] | None:
    """The halo data files in force (``holding``), file: sha256, or None."""
    found = _IN_FORCE.get()
    return dict(found) if found else None


def held(name: str) -> tuple[str, bytes] | None:
    """A halo data file as a calculation reads it: (sha256, bytes), or None where it is missing. Where its identity is
    in force (``holding``), the bytes of that identity: as held from the resolution's reading, else read again here
    (a worker) and refused (``HaloDataChanged``) where the file no longer has them, never read under another identity.
    Else the file as it is now, read once."""
    force = _IN_FORCE.get()
    if force is not None and name in force:
        sha = force[name]
        if not sha:
            return None                                    # missing when resolved: missing for the calculation
        with _HOLD_LOCK:
            data = _HELD.get(sha)
        if data is None:
            data = _read(name)
            if data is None or _hold(data) != sha:
                raise HaloDataChanged(f"the halo data file ({name}) is not the one this calculation was resolved with "
                                      f"(sha256 {sha[:12]}); nothing is calculated with another. Run it again")
        return sha, data
    data = _read(name)
    return None if data is None else (_hold(data), data)


def parsed(name: str) -> tuple[str, Any] | None:
    """(sha256, its YAML) of a halo data file as a calculation reads it (``held``), parsed once per identity."""
    found = held(name)
    if found is None:
        return None
    sha, data = found
    with _HOLD_LOCK:
        if sha in _PARSED:
            _PARSED.move_to_end(sha)
            return sha, _PARSED[sha]
    value = yaml.safe_load(data.decode())
    with _HOLD_LOCK:
        _PARSED[sha] = value
        while len(_PARSED) > HOLD:
            _PARSED.popitem(last=False)
    return sha, value


def _numbers(h: HaloModel) -> str:
    return (f"ρ₀ = {h.rho_gev_cm3:g} GeV/cm³, v₀ = {h.v0_km_s:g} km/s, v_esc = {h.v_esc_km_s:g} km/s, "
            f"v_LSR = {h.v_lsr_km_s[1]:g} km/s, the Sun's peculiar velocity {tuple(h.v_peculiar_km_s)} km/s, "
            f"the Earth's {tuple(h.v_earth_km_s)} km/s (|v_lab| = {h.v_lab_km_s:.1f} km/s)")


GALACTIC = ("γ-ray lines and antiprotons keep each record's own Galactic profile; its local density is rescaled to this "
            "halo's as (ρ_record/ρ₀)², conditional on the profile's shape: not a spatial recast, and no new J-factor")
ANNIHILATION = ("annihilation velocities are ADROIT's fixed conventions (10⁻³ c in the Galaxy and the Sun, 10⁻⁴ or "
                "2 × 10⁻⁵ c in dwarfs), not derived from the halo; no pairwise relative-velocity distribution is "
                "derived from it")
INDEPENDENT = ("dwarf galaxies (their own J-factors), the CMB, the relic density, BBN and N_eff, colliders, flavour, "
               "precision and laboratory constraints do not depend on the local halo")


FIXED = "fixed benchmark; halo uncertainty not propagated"
NO_COUNT_RATIO = ("no accepted-count ratio: the SHM's validation does not cover a distribution of another shape, so the "
                  "slow direct-detection modules take their full procedure at this halo within the point's budget, and "
                  "beyond it the comparison is pending")


def _generated_resolution(value: FixedHalo, f: Family, found: Benchmark | None, title: str) -> Resolution:
    """A generated benchmark's resolution (SHM++): its parameters, settings and tables' sha256 as they are now."""
    p, n = value.parameters, value.numerics
    tables = {"detector": shmpp.sha256(value.halo), **({"sun": shmpp.sha256(value.sun)} if value.sun else {})}
    limitations = [f"a fixed benchmark ({FIXED}): comparing it with another benchmark or the SHM gives no confidence "
                   "interval", NO_COUNT_RATIO,
                   f"tabulated: {n.speeds if n else '?'} speeds, {n.polar if n else '?'} × {n.azimuth if n else '?'} "
                   "angular nodes (generator version " f"{n.generator if n else '?'}), checked against its generator "
                   "before use", GALACTIC, ANNIHILATION, INDEPENDENT,
                   "no annual modulation and no directional rates: one instant's nondirectional distribution"]
    if found is not None and found.version != value.version:
        limitations.append(f"saved with version {value.version} of {value.benchmark}; the registry now holds version "
                           f"{found.version} (this calculation keeps its saved values)")
    numbers = (f"ρ₀ = {p.rho_gev_cm3:g} GeV/cm³, v₀ = {p.v0_km_s:g} km/s, v_esc = {p.v_esc_km_s:g} km/s, Sausage "
               f"β = {p.beta:g} and η = {p.eta:g}, the Sun's peculiar velocity {tuple(p.v_peculiar_km_s)} km/s, the "
               f"detector's speed {float(sum(x * x for x in p.v_detector())) ** 0.5:.1f} km/s")
    return _identified(Resolution(
        family=f.id, treatment=Treatment.benchmark, benchmark=value.benchmark, benchmark_version=value.version,
        components=[Component(id="round (isotropic Maxwellian)", weight=1.0 - p.eta),
                    Component(id="Gaia Sausage (radially anisotropic Gaussian)", weight=p.eta)],
        frame=FRAME + "; tabulated in the detector's and the Sun's frames", axes=AXES, units=UNITS, time=shmpp.TIME,
        full_calculations=value.full_calculations, parameters=p.model_dump(mode="json"),
        numerics=n.model_dump(mode="json") if n else {}, tables=tables, data=data_identity(tuple(HALO_DATA)),
        capabilities=list(f.capabilities), sources=[found.source] if found is not None else [], spatial=GALACTIC,
        limitations=limitations, label=f"{f.label}: fixed benchmark ({value.benchmark}, v{value.version})",
        summary=f"{f.label}, {FIXED}: {title}; {numbers}. Every comparison able to use it does; the others are named."))


def _benchmark(value: FixedHalo) -> Resolution:
    f = family(value.family)
    found = BENCHMARKS.get(value.benchmark)
    if found is not None and found.family != f.id:
        found = None                     # another family's benchmark lends this one neither its title nor its source
    title = found.title if found is not None and found.version == value.version else value.benchmark
    if value.generated:
        return _generated_resolution(value, f, found, title)
    h = value.halo
    limitations = ["a fixed benchmark: the halo's uncertainty is not propagated, and comparing it with another "
                   "benchmark gives no confidence interval", GALACTIC, ANNIHILATION, INDEPENDENT,
                   "no annual modulation and no directional rates"]
    if found is not None and found.version != value.version:
        limitations.append(f"saved with version {value.version} of {value.benchmark}; the registry now holds version "
                           f"{found.version} (this calculation keeps its saved values)")
    return _identified(Resolution(
        family=f.id, treatment=Treatment.benchmark, benchmark=value.benchmark, benchmark_version=value.version,
        halo=h, components=[Component(id="isotropic Maxwellian", weight=1.0)], frame=FRAME, axes=AXES, units=UNITS,
        time=FIXED_DATE, full_calculations=value.full_calculations, data=data_identity(tuple(HALO_DATA)),
        capabilities=list(f.capabilities),
        sources=[found.source] if found is not None else [], spatial=GALACTIC, limitations=limitations,
        label=f"{f.label}: fixed benchmark ({value.benchmark}, v{value.version})",
        summary=f"{f.label}, a fixed common benchmark: {title}; {_numbers(h)}. Every comparison able to use it does; "
                "the others are named. Halo uncertainty not propagated."))


def _region(value) -> Resolution:
    from adroit.parameter_space import halo_limits, halo_region
    h = halo_limits.velocity_halo(value.v0_km_s, value.v_esc_km_s, value.rho_median_gev_cm3)
    return _identified(Resolution(
        family=DEFAULT_FAMILY, treatment=Treatment.region, halo=h,
        components=[Component(id="isotropic Maxwellian", weight=1.0)], frame=FRAME, axes=AXES, units=UNITS,
        time=FIXED_DATE, region=value.model_dump(mode="json"), data=data_identity(tuple(HALO_DATA)),
        capabilities=list(SHM_CAPABILITIES), sources=["docs/halo_region.md (the owner's specification, 2026-10-19)"],
        spatial=GALACTIC,
        limitations=["an envelope over a declared region, not a profile likelihood; its 95% belongs to the region, not "
                     "to an experiment's confidence level", "the velocity distribution's shape, streams and the LMC "
                     "are not varied (SHM only); the local circular speed moves with v₀",
                     GALACTIC, ANNIHILATION, INDEPENDENT],
        label="SHM: uncertainty region",
        summary=f"SHM over {halo_region.describe(value)}; the centre {_numbers(h)}."))


def _published(recorded: bool, track: str) -> Resolution:
    if track == "track2":
        summary = ("Each experiment's own published halo: the signal search's for its fit, each null search's for its "
                   "limit (a difference between them is noted, not reconciled), the default SHM for the complementary "
                   "verdicts and the forecast; the halo sensitivity flags vary one parameter at a time")
    else:
        summary = ("Each experiment's and record's own published halo (the published-halo reproduction, which the "
                   "modules were validated in); experiments may use different numerical assumptions, and the halo's "
                   "uncertainty is not varied")
    if not recorded:
        summary = ("Not recorded: a request saved before the halo choice existed, read as calculated, with each "
                   "experiment's published halo. " + summary)
    return _identified(Resolution(
        family=DEFAULT_FAMILY, treatment=Treatment.published, recorded=recorded,
        sources=["each experiment module's PublishedConventions; each record's own halo"],
        limitations=["experiments may use different numerical assumptions (the xenon searches arXiv:2105.00599's, the "
                     "others ρ₀ = 0.3 GeV/cm³, v₀ = 220, v_E = 232, v_esc = 544 km/s); no common halo",
                     ANNIHILATION, INDEPENDENT],
        label="Published halos (reproduction)" + ("" if recorded else ", not recorded"), summary=summary))


def resolve(value, *, track: Literal["track1", "track2"] = "track1") -> Resolution:
    """The resolution of a saved request's halo value: a ``FixedHalo``, a ``HaloPreset``, ``"published"``, or None
    (Track 1: a request saved before the choice existed, calculated with the published halos; Track 2: its
    established reading, each experiment's published halo)."""
    from adroit.parameter_space.halo_region import HaloPreset
    value = own(value)                   # nothing the resolution holds is the caller's object (HA-05)
    if isinstance(value, FixedHalo):
        return _benchmark(value)
    if isinstance(value, HaloPreset):
        return _region(value)
    if value == "published":
        return _published(True, track)
    if value is None:
        return _published(track == "track2", track)
    raise UnknownHalo(f"{value!r} is not a halo treatment")


class HaloDataChanged(ValueError):
    """A halo data file changed between a calculation's resolution and its end: what was calculated cannot be labelled
    with the identities it was resolved with."""


def unchanged(resolution: Resolution) -> None:
    """Refuse (``HaloDataChanged``) when a halo data file the resolution names no longer has the bytes it was resolved
    with: the calculation may have read either, so it is not published under the resolution's identity."""
    if not resolution.data:
        return
    now = data_identity(tuple(resolution.data))
    changed = [name for name, sha in resolution.data.items() if now.get(name) != sha]
    if changed:
        raise HaloDataChanged(f"the halo data file{'s' if len(changed) > 1 else ''} ({', '.join(changed)}) changed "
                              "during the calculation; nothing is published under the halo it was resolved with. Run "
                              "it again")


class HaloChanged(ValueError):
    """The halo a calculation was resolved with was changed while it ran (a nested value of its request): what was
    calculated cannot be published under the identity, summary and exports of that resolution (HA-05)."""


def own(value):
    """A copy of a request's halo value (a ``FixedHalo``, a ``HaloPreset``), nested values and all; ``"published"`` and
    None as they are. A calculation resolved and run with it shares no object with whoever holds the value (HA-05)."""
    return value.model_copy(deep=True) if hasattr(value, "model_copy") else value


def intact(resolution: Resolution, value, *, track: Literal["track1", "track2"] = "track1") -> None:
    """Refuse (``HaloChanged``) where the resolution no longer matches its identity, or the halo value a calculation was
    run with no longer resolves to the resolution's content: a nested value was changed after it was resolved, so what
    was calculated may not be what its identity, summary and exports describe (HA-05). The halo data files' bytes are
    ``unchanged``'s; this compares everything else the identity covers."""
    def content(r: Resolution) -> dict:
        return {k: v for k, v in _physical(r).items() if k != "data"}
    if identity_of(resolution) != resolution.identity or content(resolve(value, track=track)) != content(resolution):
        raise HaloChanged("the halo this calculation was resolved with was changed while it ran: its values no longer "
                          "match the identity it was resolved with, so nothing is published under it. Run it again")


# --- what can use a treatment -----------------------------------------------------------------------------------------


class Consumer(StrictModel):
    """A halo-dependent comparison: what it needs and which treatments it supports."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    needs: tuple[Capability, ...] = ()
    treatments: tuple[Treatment, ...] = tuple(Treatment)
    why: str = ""                        # why it supports no other treatment


ALL = tuple(Treatment)
PUBLISHED_ONLY = (Treatment.published,)
CONSUMERS: dict[str, Consumer] = {c.id: c for c in (
    Consumer(id="direct-detection", name="direct detection (the experiment modules)", needs=(Capability.recoil,)),
    Consumer(id="path1-structure", name="direct detection through Path 1 (an operator structure)",
             treatments=PUBLISHED_ONLY, why="its limits are tabulated through Path 1 at each experiment's published "
                                            "halo (operator_limits); they have no halo variation yet"),
    Consumer(id="flavour-vector", name="a flavour-vector model's own direct-detection limit", treatments=PUBLISHED_ONLY,
             why="it is computed through Path 1 at each experiment's published halo; it has no halo variation yet"),
    Consumer(id="private-si-curve", name="a private spin-independent curve", treatments=PUBLISHED_ONLY,
             why="a private curve holds only its paper's halo"),
    Consumer(id="private-search", name="a private search", treatments=PUBLISHED_ONLY,
             why="a private search holds only its paper's halo"),
    Consumer(id="capture", name="capture in the Sun (IceCube)", needs=(Capability.solar,)),
    Consumer(id="galactic-lines", name="γ-ray lines (Fermi-LAT, H.E.S.S., DAMPE)", needs=(Capability.local_density,)),
    Consumer(id="antiprotons", name="antiprotons (AMS-02)", needs=(Capability.local_density,)),
    Consumer(id="native-joint", name="the native joint signal/null likelihood", treatments=PUBLISHED_ONLY,
             why="it is built and calibrated at its searches' common published halo (CDMS II Si with DEAP-3600); it "
                 "has no fixed-benchmark or region form yet"),
)}


def unsupported(resolution: Resolution, consumer_id: str) -> str:
    """Why ``consumer_id`` cannot be calculated with this resolution, or "" when it can."""
    consumer = CONSUMERS[consumer_id]
    if resolution.treatment not in consumer.treatments:
        return f"{consumer.name}: not calculated with {resolution.label}: {consumer.why}"
    missing = [CAPABILITY_TEXT[c] for c in consumer.needs
               if resolution.treatment is not Treatment.published and c not in resolution.capabilities]
    if missing:
        return f"{consumer.name}: {resolution.label} supplies no {', '.join(missing)}"
    return ""
