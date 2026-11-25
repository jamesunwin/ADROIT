"""Direct-detection limits at one halo of the declared region (``halo_region``; the owner's specification of
2026-10-19, its six conditions for the slow modules).

**The density** enters every module's signal only as ρ₀/m at a fixed velocity distribution, so each module's limit
on the cross-section is exactly ∝ 1/ρ₀, whatever its likelihood (counting, interval or profile): only (v₀, v_esc)
need work, and every limit here is computed at ρ_ref = 0.4 GeV cm⁻³ and scaled.

**Fast modules** (CRESST-III, DEAP-3600, PICO-60): the module's own procedure at the sample's velocities, exactly
(its conventions' halo replaced by the sample's, ``at_halo``).

**Slow modules** (the xenon searches through DIAMX, CDMSlite's median over efficiency realisations): a validated count
ratio,

    L_h = L_ref · (ρ_ref,module / ρ₀) · N_ref / N_h,

with L_ref ADROIT's own 95% limit at the module's reference halo (``limits.per_module95``: its table or its direct
calculation, never a published 90% curve) and N the signal counts the analysis accepts at unit reference
cross-section: for a xenon search the sum over its runs of exposure × ∫ ε(E_R) dR/dE_R dE_R with each run's published
efficiency curve (DIAMX's data; the module's ``total_events`` is the recoil spectrum before the detector response and
is not used), for CDMSlite its best-fit-efficiency signal. The ratio holds only where it was validated
(``data/halo_count_ratio.yaml``, ``scripts/validate_halo_count_ratio.py``): per module and interaction, at masses and
halos declared before the full calculations ran. The largest relative discrepancy seen there, e, is an empirical
estimate, not a bound. A comparison is decided by the ratio only when it clears the limit by the table's tolerance and
2e; otherwise, or outside the validated masses, the full procedure at that halo decides (``Mode.full``, within the
point's budget), or the module gives no limit there and the point is pending. A count ratio is a cut only: it never
enters a significance, a fit or a combined likelihood (``exact`` is False on its limits).

**What a validation entry must hold to be used** (the audit's PX-06): every declared checkpoint (masses × halos), each
with finite positive reference, full and ratio limits; the declaration's identity (the sha256 of
``halo_validation_points.yaml``) and gate; the error e recomputed from the points within the gate; the inputs it was
computed from (the module's own, as its limit tables fingerprint them, and the accepted-count code); and a halo inside
the region it sampled (the ellipse through its boundary halos). Anything else is not validated.

**A limit must be a number** (PX-02): a module's limit at a halo that is not finite and positive, or a procedure that
fails, leaves the module without a limit there (the halo unresolved); an infinite limit stands only where the analysis
accepts no signal at all at that halo (zero accepted counts: the module cannot see the point).

**A generated benchmark** (SHM++, halo phase 2; ``State.table``): a distribution of another shape, given as the
detector's and the Sun's tables. No count ratio: the SHM's validation does not cover it, so every module takes its own
procedure with the table as its halo (the fast ones always, the slow ones within the point's budget), each calculation
cached by the table's identity (``tabulated``), never by v₀ and v_esc. An edge-clause mass's published-curve floor has
no validated scaling to it, so the module gives no limit there. An infinite limit stands only where the module sees no
recoil at all from the table. Capture in the Sun takes the Sun's table (``capture_halo``); the Galactic searches its
density.

**The halo data files** (the count ratio's validation and declaration, the Galactic records' local densities) are read
as the calculation was resolved with them (``halo_choice.held``): its run's identities in force, else the files as
they are now; each cache of what they hold is keyed by their sha256, never by nothing (a halo phase 2 audit's HB-03,
2026-11-11: the densities had been cached once per process, and a new resolution bound a file's new sha256 while its
old values were used).
"""
from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import math
import subprocess
import textwrap
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

from adroit.core.dm_state import HaloModel
from adroit.parameter_space import limit_tables

RHO_REF = 0.4
FAST = ("CRESST-III 2019", "DEAP-3600 (2019)", "PICO-60 C3F8 (2019)")
COUNTED = ("LZ WS2022+WS2024", "XENONnT SR0+SR1", "PandaX-4T Run0+Run1", "CDMSlite Run 2")
VALIDATION = Path(__file__).resolve().parent / "data" / "halo_count_ratio.yaml"
DECLARED = Path(__file__).resolve().parent / "data" / "halo_validation_points.yaml"
FAILED = (OSError, RuntimeError, ValueError, ArithmeticError, subprocess.SubprocessError)   # a procedure that failed


def velocity_halo(v0_km_s: float, v_esc_km_s: float, rho_gev_cm3: float = RHO_REF) -> HaloModel:
    """The Standard Halo Model at these parameters, the local circular speed equal to v₀ (v_LSR = v₀) and the Sun's
    peculiar and the Earth's velocities as in the default halo: the laboratory velocity follows."""
    return HaloModel(label=f"SHM: v0 {v0_km_s:.1f}, v_esc {v_esc_km_s:.1f}, rho {rho_gev_cm3:.3f}",
                     rho_gev_cm3=rho_gev_cm3, v0_km_s=v0_km_s, v_esc_km_s=v_esc_km_s,
                     v_lsr_km_s=(0.0, v0_km_s, 0.0))


def parameterised(halo: HaloModel) -> bool:
    """Whether a halo is one this machinery evaluates at: a standard halo equal to ``velocity_halo`` at its own v₀,
    v_esc and ρ₀ (v_LSR = v₀, the default solar and Earth velocities), its label aside."""
    if halo.kind.value != "standard":
        return False
    return velocity_halo(halo.v0_km_s, halo.v_esc_km_s, halo.rho_gev_cm3).model_copy(update={"label": halo.label}) == halo


@dataclass
class Budget:
    """Full calculations a point may still spend. Every distinct one the point needs counts once, cached or not, so
    that a point's result never depends on what another point computed first, and the same calculation used again
    within the point (the other end of a density interval, a repeated comparison) costs nothing more (PX-05)."""
    remaining: int
    spent: list[str] = field(default_factory=list)
    keys: set = field(default_factory=set)
    # the modules that decided the point's direct detection at the region's centre: the budget goes to them first at
    # every other halo (``strongest_first``; the owner's plan of 2026-11-24, section 3)
    prefer: tuple[str, ...] = ()

    def take(self, key: tuple, what: str) -> bool:
        """Spend one on the calculation ``key`` (described by ``what``), unless the point already has; False when it
        has not and none is left."""
        if key in self.keys:
            return True
        if self.remaining <= 0:
            return False
        self.remaining -= 1
        self.keys.add(key)
        self.spent.append(what)
        return True


@dataclass
class State:
    """The halo every halo-dependent quantity is taken at, inside ``using``."""
    v0_km_s: float
    v_esc_km_s: float
    rho_gev_cm3: float
    full: bool = False                    # the full procedure for the slow modules (else the count ratio)
    defer: bool = False                   # a comparison the count ratio cannot decide is noted, not recomputed
    budget: Budget = field(default_factory=lambda: Budget(0))
    fragile: list[str] = field(default_factory=list)          # comparisons the count ratio could not decide
    spent: list[str] = field(default_factory=list)            # full calculations used at this halo
    # (module, kind, mass) -> how its limit was taken; keyed by the comparison, not the module, so that one interaction's
    # construction never stands for another's (PX-03)
    constructions: dict[tuple[str, str, float], str] = field(default_factory=dict)
    margins: dict[tuple[str, str, float], float] = field(default_factory=dict)   # what a comparison must clear
    # each count-ratio limit moved to the end of its margin: +1 its weakest, −1 its strongest (``halo_evaluation``
    # asks whether a comparison holds at both ends, PX-01)
    bias: int = 0
    # a fixed benchmark (``halo_choice.FixedHalo``), not a sample of a region: a module whose own published halo is
    # this halo takes its own published procedure there (``own_halo``)
    benchmark: bool = False
    # a generated benchmark (SHM++; ``at_tables``): the detector's and the Sun's tables, the identity every calculation
    # at them is cached by, and its name; v₀ and v_esc are then NaN, so that nothing takes it for a standard halo
    table: HaloModel | None = None
    sun: HaloModel | None = None
    key: str = ""
    name: str = ""

    def approximate(self) -> bool:
        """Whether any limit taken at this halo came from a count ratio (a cut only, never combined)."""
        return any(how.startswith("count ratio") for how in self.constructions.values())


_STATE: ContextVar[State | None] = ContextVar("halo_state", default=None)
_TABLES: dict[str, HaloModel] = {}       # a generated benchmark's detector table at ρ_ref, by its identity


def tabulated(table: HaloModel) -> str:
    """The identity of a detector-frame table as a velocity distribution: the sha256 of its whole record at ρ_ref,
    every speed, density, frame and boost included (its label aside). Registered, so that calculations cached by it
    find it."""
    from adroit.halo_models import shm_plus_plus
    from adroit.halo_models.frames import frame_of
    if table.kind.value != "tabulated" or frame_of(table) != "detector":
        raise ValueError("direct detection takes a table in the detector's frame")
    at_reference = table.model_copy(update={"rho_gev_cm3": RHO_REF, "label": "generated benchmark"})
    key = shm_plus_plus.sha256(at_reference)
    _TABLES.setdefault(key, at_reference)
    return key


def at_tables(fixed, budget: Budget) -> State:
    """The state of a generated fixed benchmark (``halo_choice.FixedHalo.generated``): its tables, its density."""
    return State(v0_km_s=math.nan, v_esc_km_s=math.nan, rho_gev_cm3=fixed.parameters.rho_gev_cm3, budget=budget,
                 benchmark=True, table=fixed.detector(), sun=fixed.solar(), key=tabulated(fixed.detector()),
                 name=f"{fixed.benchmark} v{fixed.version}")


def describe(state: State) -> str:
    """Where a state's limits are taken, in words."""
    if state.table is not None:
        return f"at the generated benchmark {state.name} (its tables {state.key[:12]})"
    return (f"at the halo v₀ = {state.v0_km_s:.1f} km/s, v_esc = {state.v_esc_km_s:.1f} km/s, "
            f"ρ₀ = {state.rho_gev_cm3:.3g} GeV/cm³")


def velocities(state: State) -> tuple:
    """The key of a state's velocity distribution for a cache: (v₀, v_esc), or ("table", identity)."""
    return ("table", state.key) if state.table is not None else (state.v0_km_s, state.v_esc_km_s)


def halo_at(key: tuple) -> HaloModel:
    """The velocity distribution (at ρ_ref) a ``velocities`` key names."""
    if key[0] == "table":
        return _TABLES[key[1]]
    return velocity_halo(*key)


@contextmanager
def using(state: State):
    """Inside: ``limits.per_module95``, ``at95`` and ``tolerance`` give their values at ``state``'s halo."""
    token = _STATE.set(state)
    try:
        yield state
    finally:
        _STATE.reset(token)


def active() -> State | None:
    """The halo in use, or None (each module's own reference halo)."""
    return _STATE.get()


def at_halo(module, halo: HaloModel):
    """The module with its conventions' halo replaced: its own procedure (``reference_limits``) then runs there."""
    conventions = module.conventions().model_copy(update={"halo": halo})
    changed = copy.copy(module)
    changed.conventions = lambda: conventions
    return changed


@limit_tables.held(8192, lambda module, *_: limit_tables.inputs(module))      # by the module's inputs (DY-01)
def exact(module: str, kind: str, mass_gev: float, v0_km_s: float, v_esc_km_s: float) -> float:
    """The module's own 95% limit (cm², at ρ_ref) at the sample's velocities: its full procedure."""
    from adroit.core.dm_state import CrossSectionKind
    from adroit.experiments import registry
    m = at_halo(registry.load_module(module), velocity_halo(v0_km_s, v_esc_km_s))
    return float(m.reference_limits(CrossSectionKind(kind), [mass_gev], workers=1, cl=0.95)[0])


@limit_tables.held(8192, lambda module, *_: limit_tables.inputs(module))
def exact_at_table(module: str, kind: str, mass_gev: float, key: str) -> float:
    """The module's own 95% limit (cm², at ρ_ref) with a generated benchmark's table as its halo: its full
    procedure, cached by the table's identity (``tabulated``)."""
    from adroit.core.dm_state import CrossSectionKind
    from adroit.experiments import registry
    m = at_halo(registry.load_module(module), _TABLES[key])
    return float(m.reference_limits(CrossSectionKind(kind), [mass_gev], workers=1, cl=0.95)[0])


@limit_tables.held(8192, lambda module, *_: limit_tables.inputs(module))
def blind_at_table(module: str, kind: str, mass_gev: float, key: str) -> bool:
    """Whether the module sees no recoil at all from the table at this mass (its signal before the detector response
    is zero): only then is an infinite limit its limit."""
    from adroit.core.dm_state import CrossSectionKind, DarkMatterParticle
    from adroit.experiments import registry
    from adroit.experiments.base import REFERENCE_SIGMA_CM2, reference_interaction
    m = registry.load_module(module)
    k = CrossSectionKind(kind)
    signal = m.expected_signal(DarkMatterParticle(mass_gev=mass_gev),
                               reference_interaction(k, REFERENCE_SIGMA_CM2, mass_gev), _TABLES[key],
                               m.conventions().model_for(k), m.published_target(k))
    return signal.total_events == 0.0


def _runs(module) -> list[tuple[float, np.ndarray]]:
    """(exposure in tonne-years, efficiency curve (E_R keV, ε)) of each run of a xenon search, from DIAMX's
    configuration and data."""
    folder = Path(module.folder)
    config = json.loads((folder / "config" / module.spec["config"]).read_text())
    out = []
    for run in config["experiments"]:
        name = run["experiment_name"]
        data = folder / "diamx" / "data"
        found = next((data / f for f in (f"{name}_eff_nr_total_median.csv", f"{name}_eff_median.csv")
                      if (data / f).is_file()), None)
        if found is None:
            raise FileNotFoundError(f"no efficiency curve for the run {name}")
        out.append((float(run["livetime"]) * float(run["fiducial_mass"]), np.loadtxt(found, delimiter=",")))
    return out


@lru_cache(maxsize=8192)
def accepted(module: str, kind: str, mass_gev: float, v0_km_s: float | None, v_esc_km_s: float | None) -> float:
    """The signal counts the analysis accepts at the reference cross-section (and ρ_ref), at the sample's velocities
    or (None, None) at the module's own reference halo."""
    from adroit.core.dm_state import CrossSectionKind, DarkMatterParticle
    from adroit.experiments import registry
    from adroit.experiments.base import REFERENCE_SIGMA_CM2, reference_interaction
    from adroit.experiments.xenon import DiamxXenon, ENERGIES_KEV, SD_MODEL
    m = registry.load_module(module)
    k = CrossSectionKind(kind)
    conventions = m.conventions()
    halo = conventions.halo.model_copy(update={"rho_gev_cm3": RHO_REF}) if v0_km_s is None else \
        velocity_halo(v0_km_s, v_esc_km_s)
    particle = DarkMatterParticle(mass_gev=mass_gev)
    interaction = reference_interaction(k, REFERENCE_SIGMA_CM2, mass_gev)
    if isinstance(m, DiamxXenon):
        model = SD_MODEL if k is not CrossSectionKind.si else conventions.model_for(k)
        signal = m.expected_signal(particle, interaction, halo, model, m.published_target(k))
        spectrum = np.asarray(signal.density)                                # events / keV / tonne-year
        total = 0.0
        for exposure, curve in _runs(m):
            efficiency = np.interp(ENERGIES_KEV, curve[:, 0], curve[:, 1], left=0.0, right=0.0)
            total += exposure * float(np.trapezoid(efficiency * spectrum, ENERGIES_KEV))
        return total
    signal = m.expected_signal(particle, interaction, halo, conventions.model_for(k), m.published_target(k))
    return float(signal.total_events)


_ACCEPTED_AT: dict[str, str] = {}


def counted(module: str, kind: str, mass_gev: float, v0_km_s: float | None, v_esc_km_s: float | None) -> float:
    """``accepted`` at the version of the module's inputs as they are now (``limit_tables.inputs``; the auditor's DX recheck,
    DY-01, 2026-11-13): its cache, kept by its arguments, is cleared whenever a module's inputs are found changed since
    it was last used. Its source, decorator included, is one of the validation's inputs (``inputs_sha256``), so it is
    left as it is, and the calculation asks it through here."""
    version = limit_tables.inputs(module)
    if _ACCEPTED_AT.get(module, version) != version and hasattr(accepted, "cache_clear"):
        accepted.cache_clear()
    _ACCEPTED_AT[module] = version
    return accepted(module, kind, mass_gev, v0_km_s, v_esc_km_s)


VALIDATION_FILES = ("count-ratio validation", "count-ratio declaration")   # ``halo_choice.HALO_DATA``'s names


def validation() -> dict:
    """The count ratio's validation per module and kind (``scripts/validate_halo_count_ratio.py``): every checkpoint
    and its summary, as the calculation reads the file (``halo_choice.held``); {} before it has run."""
    return _parsed("count-ratio validation")


def targeted_validation() -> dict:
    """``validation`` of the targeted validation of 2026-11-24 (``TARGETED_FILES``)."""
    return _parsed("count-ratio targeted validation")


def _parsed(name: str) -> dict:
    from adroit.core import halo_choice
    found = halo_choice.parsed(name)
    return {} if found is None else (found[1] or {})


def _source(function) -> str:
    """A function's syntax tree without its docstring (``limit_tables._content``'s rule)."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree)


@limit_tables.held(16, lambda module: limit_tables.inputs(module))
def inputs_sha256(module: str) -> str:
    """The identity of what a module's validation was computed from: its own inputs, as its limit tables fingerprint
    them, and the accepted-count code (``accepted``, ``_runs``)."""
    from adroit.parameter_space import limit_tables
    return hashlib.sha256((limit_tables.fingerprint(module) + _source(accepted) + _source(_runs)).encode()).hexdigest()


def declaration() -> tuple[dict, str]:
    """The declared validation points and the sha256 of their file, as the calculation reads it (``halo_choice.held``)."""
    return _declared("count-ratio declaration")


def targeted_declaration() -> tuple[dict, str]:
    """``declaration`` of the targeted validation of 2026-11-24."""
    return _declared("count-ratio targeted declaration")


def _declared(name: str) -> tuple[dict, str]:
    from adroit.core import halo_choice
    found = halo_choice.parsed(name)
    if found is None:
        raise FileNotFoundError(f"the count ratio's declaration ({name}) cannot be read")
    return copy.deepcopy(found[1]), found[0]


def summarise(points: list[dict], gate: float) -> tuple[float, bool]:
    """(e, passed) of one module and kind's checkpoints: e the largest |L_ratio/L_full − 1|; passed only if every
    reference, full and ratio limit is finite and positive and e is within the gate (a NaN never hides, PX-06)."""
    values = [p[k] for p in points for k in ("reference_cm2", "full_cm2", "ratio_cm2")]
    if not points or not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in values):
        return math.nan, False
    e = max(abs(p["ratio_cm2"] / p["full_cm2"] - 1.0) for p in points)
    return e, e <= gate


def _usable(module: str, kind: str) -> tuple[float, tuple[float, float], tuple[float, float, float, float]] | None:
    """``_usable_at`` for the validation and declaration as the calculation reads them: its run's (``halo_choice.held``),
    else the files as they are now, each read once and held for this reading."""
    from adroit.core import halo_choice
    force = halo_choice.in_force() or {}
    if all(name in force for name in VALIDATION_FILES):
        return _usable_at(module, kind, tuple(force[name] for name in VALIDATION_FILES))
    now = {**force, **halo_choice.data_identity(tuple(n for n in VALIDATION_FILES if n not in force))}
    with halo_choice.holding(now):
        return _usable_at(module, kind, tuple(now[name] for name in VALIDATION_FILES))


@limit_tables.held(256, lambda module, *_: limit_tables.inputs(module))      # its entry's inputs_sha256 (DY-01)
def _usable_at(module: str, kind: str, files: tuple[str, ...]
               ) -> tuple[float, tuple[float, float], tuple[float, float, float, float]] | None:
    """(e, (lowest, highest) validated mass, (v₀, v_esc) of the region's centre and its semi-axes) of a validation
    entry that holds everything it must (module docstring), else None; cached by the files' sha256 (``files``, in
    force as it is called)."""
    return _entry(module, kind, validation(), *declaration())


TARGETED_FILES = ("count-ratio targeted validation", "count-ratio targeted declaration")


def _targeted(module: str, kind: str) -> tuple[float, tuple[float, float], tuple[float, float, float, float]] | None:
    """``_usable`` for the targeted validation of 2026-11-24 (``data/halo_validation_points_targeted.yaml``, declared
    before its calculations ran; ``scripts/validate_halo_count_ratio.py --targeted``): the same checks, against its
    own declaration and gate, never extending the original's masses or halos."""
    from adroit.core import halo_choice
    force = halo_choice.in_force() or {}
    if all(name in force for name in TARGETED_FILES):
        return _targeted_at(module, kind, tuple(force[name] for name in TARGETED_FILES))
    now = {**force, **halo_choice.data_identity(tuple(n for n in TARGETED_FILES if n not in force))}
    with halo_choice.holding(now):
        return _targeted_at(module, kind, tuple(now[name] for name in TARGETED_FILES))


@limit_tables.held(256, lambda module, *_: limit_tables.inputs(module))
def _targeted_at(module: str, kind: str, files: tuple[str, ...]
                 ) -> tuple[float, tuple[float, float], tuple[float, float, float, float]] | None:
    """``_usable_at`` of the targeted validation."""
    try:
        declared = targeted_declaration()
    except FileNotFoundError:
        return None
    return _entry(module, kind, targeted_validation(), *declared)


def _entry(module: str, kind: str, data: dict, declared: dict, sha: str
           ) -> tuple[float, tuple[float, float], tuple[float, float, float, float]] | None:
    """One validation entry, used only where it holds everything it must (module docstring): its declaration's sha256
    and gate, the module's inputs, every declared checkpoint finite and positive, and its error within the gate."""
    entry = data.get("modules", {}).get(module, {}).get(kind)
    if not entry:
        return None
    masses = declared.get("modules", {}).get(module, {}).get(kind)
    gate = float(declared["gate_max_discrepancy"])
    if masses is None or entry.get("declared_sha256", data.get("declared_sha256")) != sha or \
            float(data.get("gate_max_discrepancy", -1)) != gate or entry.get("inputs_sha256") != inputs_sha256(module):
        return None
    points = entry.get("points", [])
    if sorted((p["halo"], float(p["mass_gev"])) for p in points) != \
            sorted((h, float(m)) for h in declared["halos"] for m in masses):
        return None
    e, passed = summarise(points, gate)
    if not passed:
        return None
    centre = next(p for p in points if p["halo"] == "centre")
    v0, ve = float(centre["v0_km_s"]), float(centre["v_esc_km_s"])
    a = max(abs(float(p["v0_km_s"]) - v0) for p in points)
    b = max(abs(float(p["v_esc_km_s"]) - ve) for p in points)
    return e, (min(masses), max(masses)), (v0, ve, a, b)


def validated(module: str, kind: str, mass_gev: float, state: "State | None" = None) -> float | None:
    """The count ratio's empirical error e for the module and kind at this mass (and the state's velocities, inside
    the region its validation sampled), or None outside what was validated: the original validation's entry or the
    targeted one's (``_targeted``), each within its own masses; where both cover the mass, the larger e."""
    covering = []
    for found in (_usable(module, kind), _targeted(module, kind)):
        if found is None:
            continue
        e, (low, high), (v0, ve, a, b) = found
        if not low * (1 - 1e-9) <= mass_gev <= high * (1 + 1e-9):
            continue
        if state is not None and (a <= 0 or b <= 0 or
                                  ((state.v0_km_s - v0) / a) ** 2 + ((state.v_esc_km_s - ve) / b) ** 2 > 1 + 1e-4):
            continue                      # outside the velocities validated (1e-4: the stored values' rounding)
        covering.append(e)
    return max(covering) if covering else None


def scale(module: str, kind: str, mass_gev: float, state: State) -> float:
    """The count ratio's factor (ρ_ref,module/ρ₀) · N_ref/N_h: a module's limit at the state's halo over its limit at
    its own reference halo, as far as the accepted counts say (inf where nothing is accepted)."""
    from adroit.experiments import registry
    counts = counted(module, kind, mass_gev, state.v0_km_s, state.v_esc_km_s)
    reference = counted(module, kind, mass_gev, None, None)
    if not (math.isfinite(counts) and counts >= 0 and math.isfinite(reference) and reference > 0):
        raise ArithmeticError(f"{module}: accepted counts {counts!r} at this halo, {reference!r} at its own")
    if counts == 0:
        return math.inf                   # the analysis accepts no signal here: the module cannot see the point
    rho_ref = registry.load_module(module).conventions().halo.rho_gev_cm3
    return rho_ref / state.rho_gev_cm3 * reference / counts


def _full(state: State, module: str, kind: str, mass_gev: float, why: str) -> tuple[float | None, str]:
    """The slow module's own procedure at the state's halo, if the point's budget allows (one velocity calculation
    serves every density)."""
    v0, ve = state.v0_km_s, state.v_esc_km_s
    where = f"{state.name} (tables {state.key[:12]})" if state.table is not None else f"v₀ {v0:.1f}, v_esc {ve:.1f} km/s"
    what = f"{module} {kind} at {mass_gev:.4g} GeV, {where} ({why})"
    if not state.budget.take((module, kind, mass_gev, *velocities(state)), what):
        return None, f"halo: a full calculation at this halo is needed ({why}); the point's budget is spent"
    if what not in state.spent:
        state.spent.append(what)
    return _procedure(state, module, kind, mass_gev), "its own procedure at this halo"


def _procedure(state: State, module: str, kind: str, mass_gev: float) -> float:
    """The module's own procedure at the state's velocities (its table, or v₀ and v_esc), at the state's density."""
    found = exact_at_table(module, kind, mass_gev, state.key) if state.table is not None else \
        exact(module, kind, mass_gev, state.v0_km_s, state.v_esc_km_s)
    return found * RHO_REF / state.rho_gev_cm3


def _reference(state: State, module: str, kind: str, mass_gev: float) -> tuple[float | None, str]:
    """The module's own 95% limit at its reference halo, for the count ratio: from its current table, else by its own
    procedure, which is a full calculation and spends the point's budget (PX-05)."""
    from adroit.parameter_space import limit_tables, limits
    use = limits.tables_allowed()
    if not (use and limit_tables.lookup(module, kind, mass_gev)):
        what = f"{module} {kind} at {mass_gev:.4g} GeV at its own reference halo (no current table)"
        if not state.budget.take((module, kind, mass_gev, "reference"), what):
            return None, "halo: the count ratio needs the module's reference limit, a full calculation; the point's " \
                         "budget is spent"
        if what not in state.spent:
            state.spent.append(what)
    value, why = limits.reference_limit(module, kind, mass_gev, use)
    return value, (why and f"halo: no reference limit for the count ratio ({why})")


def _checked(state: State, module: str, kind: str, mass_gev: float, value: float, margin: float,
             how: str) -> tuple[float | None, float, str]:
    """The limit if it is a number (module docstring), else none and why."""
    if math.isfinite(value) and value > 0:
        return value, margin, how
    if value == math.inf and state.table is not None and blind_at_table(module, kind, mass_gev, state.key):
        return value, 0.0, "no recoil at all from this halo (the module cannot see the point)"
    if value == math.inf and state.table is None and module in COUNTED and \
            counted(module, kind, mass_gev, state.v0_km_s, state.v_esc_km_s) == 0:
        return value, 0.0, "no accepted signal at this halo (the module cannot see the point)"
    return None, 0.0, f"halo: the module's procedure gave no valid limit at this halo ({value!r})"


def own_halo(module: str, state: State) -> bool:
    """Whether the state's velocities are the module's own published halo: the same distribution in every velocity
    (v₀, v_esc, v_LSR, the Sun's and the Earth's velocities), its density aside, which scales analytically."""
    from adroit.experiments import registry
    if state.table is not None:
        return False                      # no module's published halo is a generated benchmark
    mine = registry.load_module(module).conventions().halo
    here = velocity_halo(state.v0_km_s, state.v_esc_km_s)
    return mine.model_copy(update={"label": "", "rho_gev_cm3": 1.0}) == \
        here.model_copy(update={"label": "", "rho_gev_cm3": 1.0})


def _published_here(state: State, module: str, kind: str, mass_gev: float,
                    full: bool) -> tuple[float | None, float, str]:
    """At a fixed benchmark that is the module's own published halo: its published procedure's 95% limit (its table,
    within the table's tolerance, or its own procedure when the comparison is recomputed exactly), its density scaled
    analytically. The same limit as the published-halo reproduction, never a count ratio."""
    from adroit.experiments import registry
    from adroit.parameter_space import limits
    use = limits.tables_allowed() and not full
    value, why = limits.reference_limit(module, kind, mass_gev, use)
    if value is None:
        return None, 0.0, f"halo: no limit at its own published halo ({why})"
    rho_ref = registry.load_module(module).conventions().halo.rho_gev_cm3
    margin = limits.reference_tolerance(module, kind, mass_gev) if use else 0.0
    return value * rho_ref / state.rho_gev_cm3, margin, "its own published procedure (this benchmark is its published halo)"


def module_limit(state: State, module: str, kind: str, mass_gev: float, full: bool) -> tuple[float | None, float, str]:
    """(the module's 95% limit at the state's halo or None, the tolerance its comparison must clear, how it was
    taken or why there is none); ``full``: the slow modules' full procedure. A floor at an edge-clause mass
    (``limits.edge_floor``) moves with the count ratio's factor; a count-ratio limit moves to its margin's end with
    ``state.bias``."""
    from adroit.parameter_space import limits
    try:
        if state.table is not None:
            return _at_table(state, module, kind, mass_gev)
        if state.benchmark and own_halo(module, state):
            value, margin, how = _published_here(state, module, kind, mass_gev, full)
            return (None, 0.0, how) if value is None else _checked(state, module, kind, mass_gev, value, margin, how)
        if module in COUNTED:
            error = validated(module, kind, mass_gev, state)
            if not full and error is not None:
                reference, why = _reference(state, module, kind, mass_gev)
                if reference is None:
                    return None, 0.0, why
                margin = (1 + limits.reference_tolerance(module, kind, mass_gev)) * (1 + 2 * error) - 1
                value = reference * scale(module, kind, mass_gev, state) * (1 + margin) ** state.bias
                return _checked(state, module, kind, mass_gev, value, margin,
                                f"count ratio (validated; largest discrepancy seen {100 * error:.1f}%)")
            value, how = _full(state, module, kind, mass_gev, "near the limit" if error is not None else
                               "outside the count ratio's validated masses and halos")
        elif module in FAST:
            value, how = exact(module, kind, mass_gev, state.v0_km_s, state.v_esc_km_s) * RHO_REF / \
                state.rho_gev_cm3, "its own procedure at this halo"
        else:
            return None, 0.0, "halo: this module's limit has no halo variation"
        if value is None:
            return None, 0.0, how
        floor = limits.edge_floor(module, kind, mass_gev)
        if floor:
            value = max(value, floor * scale(module, kind, mass_gev, state))
    except FAILED as error:
        return None, 0.0, f"halo: the module's procedure failed at this halo ({type(error).__name__}: {error})"
    return _checked(state, module, kind, mass_gev, value, 0.0, how)


def _at_table(state: State, module: str, kind: str, mass_gev: float) -> tuple[float | None, float, str]:
    """A module's limit at a generated benchmark (module docstring): its own procedure with the table as its halo, the
    slow ones within the point's budget; none at an edge-clause mass."""
    from adroit.parameter_space import limits
    if limits.edge_floor(module, kind, mass_gev):
        return None, 0.0, ("halo: at this mass the module's limit is floored at its published curve (the edge clause), "
                           "which has no validated scaling to this distribution")
    if module in COUNTED:
        value, how = _full(state, module, kind, mass_gev, "no validated count ratio for this distribution")
    elif module in FAST:
        value, how = _procedure(state, module, kind, mass_gev), "its own procedure at this halo"
    else:
        return None, 0.0, "halo: this module's limit has no halo variation"
    if value is None:
        return None, 0.0, how
    return _checked(state, module, kind, mass_gev, value, 0.0, how)


def strongest_first(names, kind: str, mass_gev: float, prefer: tuple[str, ...] = ()) -> list[str]:
    """The eligible modules in the order a point's budget of full calculations should go to them (the owner's plan of
    2026-11-24, section 3: the decisive comparison first, never the budget exhausted on a weaker search before the
    useful one): the fast modules (no budget) as listed; then the slow ones that decided the point at the region's
    centre (``prefer``: ``Budget.prefer``); then the others by their reference limit at this mass, strongest first,
    from their current tables (a module without one last). The limits themselves are unchanged. The reassessment of
    2026-11-24 found the order by tables alone spending a point's whole budget on XENONnT below its validated masses
    while LZ, which decided the point and has no table there, got none."""
    from adroit.parameter_space import limit_tables
    names = list(names)

    def strength(name: str) -> tuple[int, float]:
        if name in prefer:
            return 0, float(prefer.index(name))
        found = limit_tables.lookup(name, kind, mass_gev) if name in COUNTED else None
        return 1, found[0] if found else math.inf
    slow = sorted((n for n in names if n in COUNTED), key=strength)
    return [n for n in names if n not in COUNTED] + slow


def per_module95(state: State, kind: str, mass_gev: float, excluded_modules: tuple[str, ...]
                 ) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, str], ...]]:
    """``limits.per_module95`` at the state's halo: each module validated at the mass with its limit here, and those
    with none, with the reason. No module's reference limit is computed unless its count ratio needs it (PX-05). The
    full procedure when the state asks for it or a comparison is recomputed directly (``limits.exact``)."""
    from adroit.parameter_space import limits
    full = state.full or limits.exact_requested()
    out, missing = [], {}
    for name in strongest_first(limits.eligible(kind, mass_gev, excluded_modules), kind, mass_gev,
                                state.budget.prefer):
        value, margin, how = module_limit(state, name, kind, mass_gev, full)
        state.constructions[name, kind, mass_gev] = how
        if value is None:
            missing[name] = how
            continue
        state.margins[name, kind, mass_gev] = margin
        out.append((name, value))
        if weaker := limits.fallback(name):               # it excludes; it never allows (D1)
            missing[name] = weaker
    return tuple(out), tuple(missing.items())


# --- the Galactic halo's density and capture in the Sun --------------------------------------------------------------

DENSITIES = Path(__file__).resolve().parents[1] / "constraints" / "data" / "local_densities.yaml"


def recorded_densities() -> dict[str, float]:
    """The local density (GeV cm⁻³) each Galactic-halo indirect-detection record's limits assume, as the calculation
    reads the file (``halo_choice.held``: its run's, else the file as it is now)."""
    from adroit.core import halo_choice
    found = halo_choice.parsed("local densities")
    if found is None:
        raise FileNotFoundError(f"the local densities ({DENSITIES}) cannot be read")
    return {k: float(v["rho_gev_cm3"]) for k, v in found[1]["records"].items()}


def density_scale(record_id: str) -> float:
    """(ρ₀/ρ_record)², by which a Galactic-halo record's prediction-to-limit ratio moves at the state's halo (its
    limit on ⟨σv⟩ scales as ρ₀⁻²); 1 outside a halo region, or for a record that states no density."""
    state = _STATE.get()
    rho = recorded_densities().get(record_id)
    return 1.0 if state is None or rho is None else (state.rho_gev_cm3 / rho) ** 2


def capture_halo() -> HaloModel | None:
    """The halo a model's capture in the Sun is computed in at the state's halo (None: the default halo): a generated
    benchmark's Sun-frame table."""
    state = _STATE.get()
    if state is not None and state.table is not None:
        return state.sun
    return None if state is None else velocity_halo(state.v0_km_s, state.v_esc_km_s, state.rho_gev_cm3)
