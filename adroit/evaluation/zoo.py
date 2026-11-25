"""The model zoo (G0 of docs/freeze_out_build.md, the owner 2026-10-13): freeze-out models from the literature with published targets, to measure
what ADROIT computes from a model it was not written for (coverage), and how well (accuracy).

- **Entries** (``data/model_zoo.yaml``): the model as typed data (a ModelSpec: fields, couplings, terms) at its
  benchmark; the paper's own Lagrangian (for the language-model intake path, G10); the capabilities it needs; and each
  target with its source (arXiv, 1-based page, location, verbatim quote) and stated uncertainty.
- **Halves** are DM10's (``core.half_of``): fixed by a hash of the suite and the id before any result is seen. The
  held-out half runs only to confirm a declared step and is ledgered (``adroit eval model_zoo --held-out --reason``).
- **Controls** (``in_library``) are models ADROIT was built or validated against; they test the harness and are
  summarised apart, since they are not a fair test of adapting to a new model.
- **Two routes** (the owner: the zoo adds to the standard library, it replaces nothing). The typed route maps the
  model (``classify``), as an intake would. A model the standard library holds (``library``: its portal entry) is
  computed through that entry's validated engine when the typed route refuses it, and the refusal is recorded: the
  library computes the model, but the intake does not yet reach it.
- **A case:** a refusal is recorded with its reason. A mapped model's targets are computed: Ωh² at the point; the
  thermal mass (the m_χ at which Ωh² meets the target); the thermal splitting Δ = m_med/m_χ − 1 at fixed m_χ (for
  forbidden channels, where Ωh² depends exponentially on Δ); σ_SI. A target computed with less physics than the
  engine's (perturbative only, say) sets the engine's switches (``engine_options``). A target is met within the
  source's stated uncertainty or the default tolerance (``TOLERANCE``); an exception is an error, which is a bug.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from adroit.core.state import StrictModel
from adroit.evaluation.core import Case, CaseResult, Suite

DATA = Path(__file__).parent / "data" / "model_zoo.yaml"
NAME = "model_zoo"
TOLERANCE = {"thermal_mass_gev": 0.10, "thermal_splitting": 0.10, "omega_h2": 0.20,
             "sigma_si_cm2": 1.0}                                 # relative; σ_SI within a factor 2
COMPARED = tuple(TOLERANCE)
GRID = 4                       # the root search's grid: the published value × 3^(k/GRID), k = −GRID … GRID


class ZooSource(StrictModel):
    """Where a target is printed."""
    arxiv: str
    page: int
    location: str
    quote: str


class ZooTarget(StrictModel):
    """One published number: the quantity, its value and stated uncertainty, the benchmark it refers to (``at``, in
    the paper's names), the changes to the entry's model for that benchmark (``overrides``: field masses in GeV and
    coupling values), the library route's slots (``point``), the engine switches that reproduce the authors' physics
    (``engine_options``), and, for a thermal mass or splitting, the Ωh² it was solved for."""
    quantity: Literal["thermal_mass_gev", "thermal_splitting", "omega_h2", "sigma_si_cm2", "sigma_v_cm3_s"]
    value: float
    uncertainty: float | None = None
    at: dict[str, float | str] = Field(default_factory=dict)
    overrides: dict[str, dict[str, float]] = Field(default_factory=dict)
    point: dict[str, float] = Field(default_factory=dict)
    engine_options: dict[str, float | bool] = Field(default_factory=dict)
    omega_target: float = 0.12
    mediator_ratio: float | None = None          # thermal mass: the mediator mass tied to m_χ, as the paper ties it
    scan: str = ""                               # the generic route: the parameter m_χ sets ("" the DM field's mass)
    tied: str = ""                               # the generic route: the parameter m_med sets
    source: ZooSource
    tool: str = ""


class ZooEntry(StrictModel):
    """One model of the zoo (module docstring)."""
    id: str
    title: str
    category: str
    in_library: bool = False
    library: str = ""                            # the standard-library portal entry that is this model, if any
    reference: dict[str, str | int]
    lagrangian: dict[str, str | int] = Field(default_factory=dict)
    needs: list[str] = Field(default_factory=list)
    spec: dict
    targets: list[ZooTarget]
    notes: str = ""

    @model_validator(mode="after")
    def _library_targets_have_slots(self) -> "ZooEntry":
        if self.library and any("m_chi" not in t.point for t in self.targets):
            raise ValueError(f"{self.id}: the library route needs each target's slots (point.m_chi at least)")
        return self


@lru_cache(maxsize=1)
def entries(path: Path = DATA) -> tuple[ZooEntry, ...]:
    """Every zoo entry, in file order."""
    return tuple(ZooEntry.model_validate(e) for e in yaml.safe_load(path.read_text())["entries"])


def _spec(entry: ZooEntry, target: ZooTarget):
    """The entry's ModelSpec at a target's benchmark (its overrides applied: field masses, vacuum values, couplings)."""
    from adroit.core.model_spec import ModelSpec
    data = yaml.safe_load(yaml.safe_dump(entry.spec))              # a deep copy
    for field in data.get("fields", []):
        if field["name"] in target.overrides.get("masses", {}):
            field["mass_gev"] = target.overrides["masses"][field["name"]]
        if field["name"] in target.overrides.get("vevs", {}):
            field["vev_gev"] = target.overrides["vevs"][field["name"]]
    for coupling in data.get("couplings", []):
        if coupling["name"] in target.overrides.get("couplings", {}):
            coupling["value"] = target.overrides["couplings"][coupling["name"]]
    return ModelSpec.model_validate({"name": entry.id, **data})


def mapped(entry: ZooEntry, target: ZooTarget):
    """(engine, point, route, why the typed route refused): the typed model as ``classify`` maps it; else, for a model
    the standard library holds, that entry's engine at the target's slots; else the generic route (G4), the model
    computed from its own Feynman rules. Raises Unsupported if none applies."""
    from adroit.parameter_space.classify import Unsupported, classify
    try:
        cls, point, _ = classify(_spec(entry, target), generic_route=False)     # the zoo routes the generic itself
        return cls, point, "typed", ""
    except Unsupported as error:
        if entry.library:
            from adroit.parameter_space import library
            held = library.entry(entry.library)
            return held.model_class, held.point.model_copy(update=target.point), "library", str(error)
        return (*_generic(entry, target), "generic", str(error))


def _generic(entry: ZooEntry, target: ZooTarget):
    """(the generic engine, its point) for the target's benchmark; Unsupported if the model cannot be built."""
    from adroit.parameter_space.classify import Unsupported
    from adroit.parameter_space.portals.generic import GenericModel
    switches = {k: v for k, v in target.engine_options.items() if k in ("sommerfeld", "bound_states")}
    engine = GenericModel.of(_spec(entry, target), scan=target.scan, tied=target.tied, **switches)
    try:
        point = engine.point()
        engine.at(point)
    except ValueError as error:
        raise Unsupported(f"the generic route cannot build the model: {error}") from None
    return engine, point


def _solve(omega: Callable[[float], float | None], value: float) -> tuple[float | None, str]:
    """(the x nearest ``value`` at which omega(x) changes sign, why none): the grid value × 3^(k/GRID) is searched
    outward from the published value on both sides, then the bracket is bisected in ln x to 0.2%. None if Ωh² is not
    computed at the published value, or no sign change is found within value × [1/3, 3] where it is computed."""
    grid = [value * 3.0 ** (k / GRID) for k in range(-GRID, GRID + 1)]
    f = {GRID: omega(grid[GRID])}
    if f[GRID] is None:
        return None, "Ωh² is not computed at the published value"
    live, bracket = {1, -1}, None
    for step in range(1, GRID + 1):
        for side in sorted(live, reverse=True):
            j = GRID + side * step
            f[j] = omega(grid[j])
            if f[j] is None:
                live.discard(side)
            elif f[j] * f[j - side] <= 0:
                bracket = (min(j, j - side), max(j, j - side))
                break
        if bracket or not live:
            break
    if bracket is None:
        return None, "Ωh² does not reach the target within the published value × [1/3, 3] where it is computed"
    low, high, f_low = math.log(grid[bracket[0]]), math.log(grid[bracket[1]]), f[bracket[0]]
    while high - low > 2e-3:                                     # 0.2% in x: about 7 more evaluations
        mid = 0.5 * (low + high)
        f_mid = omega(math.exp(mid))
        if f_mid is None:
            return None, f"Ωh² is not computed at {math.exp(mid):.4g}, inside the bracket"
        low, high, f_low = (mid, high, f_mid) if f_mid * f_low > 0 else (low, mid, f_low)
    return math.exp(0.5 * (low + high)), ""


def _thermal(cls, point, target: ZooTarget) -> tuple[float | None, str]:
    """The thermal mass (m_χ, any mediator tied to it by ``mediator_ratio``) or the thermal splitting (Δ, with
    m_med = m_χ(1 + Δ) at fixed m_χ) at which Ωh² meets the target's Ωh²."""
    def update(x: float) -> dict[str, float]:
        if target.quantity == "thermal_splitting":
            return {"m_med": point.m_chi * (1.0 + x)}
        return {"m_chi": x} | ({"m_med": target.mediator_ratio * x} if target.mediator_ratio else {})

    def omega(x: float) -> float | None:
        value = cls.omega_h2(point.model_copy(update=update(x)))
        return None if value is None else value - target.omega_target
    return _solve(omega, target.value)


def engine(entry: ZooEntry) -> str:
    """The engine that computes the entry (its class's name); raises Unsupported if none does."""
    return type(mapped(entry, entry.targets[0])[0]).__name__


def compute(entry: ZooEntry, target: ZooTarget) -> tuple[float | None, str]:
    """(the computed value, why not) of one target; raises Unsupported if the model is refused. Where the typed or
    library engine refuses the target by its own domain, the generic route computes it (``fallback``)."""
    return computed_by(entry, target)[:2]


def computed_by(entry: ZooEntry, target: ZooTarget) -> tuple[float | None, str, str]:
    """(value, why not, the route that computed it): ``compute``'s, with the route (the owner, 2026-10-15)."""
    cls, point, route, _ = mapped(entry, target)
    value, why = _evaluate(cls, point, route, target)
    if value is not None or route == "generic":
        return value, why, route
    domain = cls.domain(point) if hasattr(cls, "domain") else ""
    if not domain:
        return value, why, route
    from adroit.parameter_space.classify import Unsupported
    try:
        engine, gpoint = _generic(entry, target)
    except Unsupported:
        return value, why, route
    value, generic_why = _evaluate(engine, gpoint, "generic", target)
    return (value, "", f"generic (fallback: the {route} engine's domain: {domain})") if value is not None else \
        (None, f"{why}; the generic route: {generic_why}", route)


def _evaluate(cls, point, route: str, target: ZooTarget) -> tuple[float | None, str]:
    """One target from an engine at its point (the engine switches applied; the generic engine reads its physics
    from the model itself, so only its long-range switches apply)."""
    options = dict(target.engine_options)
    if route == "generic":
        options = {k: v for k, v in options.items() if k in ("sommerfeld", "bound_states")}
    unknown = sorted(set(options) - set(type(cls).model_fields))
    if unknown:
        return None, f"{type(cls).__name__} has no switch {', '.join(unknown)} for the authors' treatment"
    cls = cls.model_copy(update=options)
    if target.quantity == "omega_h2":
        value = cls.omega_h2(point)
        return value, "" if value is not None else (cls.domain(point) if hasattr(cls, "domain") else "") or \
            "Ωh² is not computed here"
    if target.quantity in ("thermal_mass_gev", "thermal_splitting"):
        value, why = _thermal(cls, point, target)
        domain = cls.domain(point.model_copy(update={"m_chi": target.value})) if hasattr(cls, "domain") and \
            target.quantity == "thermal_mass_gev" and value is None else ""
        return value, f"{why} ({domain})" if domain else why
    if target.quantity == "sigma_si_cm2":
        return _proton_si(cls, point)
    return None, f"{target.quantity} is not compared"


def _proton_si(cls, point) -> tuple[float | None, str]:
    """The published σ_SI: the dark matter–proton cross-section, σ_p = (c₁ᵖ)²μ_p²/π. Where c₁ᵖ ≠ c₁ⁿ the scan's
    ``dd`` gives the deciding module's own cross-section instead, which is not what the papers quote."""
    from adroit.parameter_space.portals.base import sigma_from
    n = cls.nucleon(point)
    if n.structure or not (n.c1_p or n.c1_p_odd):
        return None, f"no spin-independent scattering on protons ({n.structure or n.suppressed or 'c₁ᵖ = 0'})"
    return sigma_from(n.c1_p, point.m_chi) + sigma_from(n.c1_p_odd, point.m_chi), ""


def met(target: ZooTarget, value: float) -> bool:
    """Whether a computed value meets the target: within the source's uncertainty or the default tolerance (σ_SI
    within a factor 1 + tolerance either way)."""
    stated = (target.uncertainty or 0.0) / abs(target.value)
    tolerance = max(stated, TOLERANCE[target.quantity])
    if target.quantity == "sigma_si_cm2":
        return 1.0 / (1.0 + tolerance) <= value / target.value <= 1.0 + tolerance
    return abs(value / target.value - 1.0) <= tolerance


def run_case(case: Case) -> CaseResult:
    """One entry: refused (with the reason), an error, or each target computed and compared, with the route. A
    control is also computed through the generic route, beside its library engine (``route_agreement``)."""
    from adroit.parameter_space.classify import Unsupported
    entry = ZooEntry.model_validate(case.inputs)
    metrics: dict[str, bool | int | float | str] = {"category": entry.category, "control": entry.in_library,
                                                   "needs": ", ".join(entry.needs)}
    passed_all, compared, reasons = True, 0, []
    for k, target in enumerate(entry.targets):
        tag = f"t{k}_{target.quantity}"
        try:
            value, why, by = computed_by(entry, target)
        except Unsupported as error:
            metrics |= {"status": "refused", "reason": str(error)}
            return CaseResult(case_id=entry.id, passed=False, metrics=metrics, note=f"refused: {error}")
        except Exception as error:                     # noqa: BLE001 - every exception in a case is a finding
            metrics |= {"status": "error", "reason": f"{type(error).__name__}: {error}"}
            return CaseResult(case_id=entry.id, passed=False, metrics=metrics, note=f"error: {error}")
        metrics[f"{tag}_published"] = target.value
        if value is None:
            metrics[f"{tag}_why"] = why
            reasons.append(why)
            passed_all = False if target.quantity in COMPARED else passed_all
            continue
        compared += 1
        if by.startswith("generic (fallback"):
            metrics[f"{tag}_route"] = by
        metrics[f"{tag}_computed"] = value
        metrics[f"{tag}_met"] = met(target, value)
        passed_all = passed_all and metrics[f"{tag}_met"]
    cls, _, route, refusal = mapped(entry, entry.targets[0])
    status = "computed" if compared or route != "generic" else "refused"
    metrics |= {"status": status, "compared": compared, "engine": type(cls).__name__, "route": route}
    metrics |= {"typed_refusal": refusal} if refusal else {}
    if status == "refused":
        metrics["reason"] = next((r for r in reasons if r), "nothing computed")
    if entry.in_library:
        metrics |= route_agreement(entry)
    return CaseResult(case_id=entry.id, passed=passed_all and compared > 0, metrics=metrics)


def route_agreement(entry: ZooEntry) -> dict[str, float | str | bool]:
    """A control through the generic route too: each target's generic value, its ratio to the library's or typed
    engine's, and whether they agree within the target's tolerance (the cross-check inside the library)."""
    from adroit.parameter_space.classify import Unsupported
    out: dict[str, float | str | bool] = {}
    for k, target in enumerate(entry.targets):
        if target.quantity not in COMPARED:
            continue
        tag = f"t{k}_{target.quantity}"
        try:
            engine, point = _generic(entry, target)
            value, why = _evaluate(engine, point, "generic", target)
        except Unsupported as error:
            out[f"{tag}_generic_why"] = str(error)
            continue
        except Exception as error:                     # noqa: BLE001 - a failure of the cross-check is a finding
            out[f"{tag}_generic_why"] = f"{type(error).__name__}: {error}"
            continue
        if value is None:
            out[f"{tag}_generic_why"] = why
            continue
        out[f"{tag}_generic"] = value
        try:
            reference, _, route = computed_by(entry, target)
        except Exception:                              # noqa: BLE001
            reference, route = None, ""
        if route.startswith("generic"):               # the generic route is not its own reference (G3/G4-10)
            out[f"{tag}_generic_why"] = "the library's engine refuses this target, so there is nothing to compare"
            continue
        if reference:
            out[f"{tag}_generic_ratio"] = value / reference
            out[f"{tag}_generic_agrees"] = met(target.model_copy(update={"value": reference, "uncertainty": None}),
                                               value)
    return out


def summarise(results: list[CaseResult], cases: list[Case]) -> dict[str, float | str]:
    """Coverage and accuracy, the controls apart from the new models: computed (through the library, through the
    generic route), refused, errors; targets met; and the controls' generic-route agreement."""
    out: dict[str, float | str] = {}
    for label, control in (("new", False), ("controls", True)):
        group = [r for r in results if r.metrics.get("control") is control]
        status = [r.metrics.get("status") for r in group]
        targets = [v for r in group for k, v in r.metrics.items() if k.endswith("_met")]
        out |= {f"{label}_models": len(group), f"{label}_computed": status.count("computed"),
                f"{label}_by_library": sum(r.metrics.get("route") == "library" for r in group),
                f"{label}_by_generic": sum(r.metrics.get("route") == "generic" and r.metrics.get("status") == "computed"
                                           for r in group),
                f"{label}_refused": status.count("refused"), f"{label}_errors": status.count("error"),
                f"{label}_targets_compared": len(targets), f"{label}_targets_met": sum(targets)}
    agreement = [v for r in results for k, v in r.metrics.items() if k.endswith("_generic_agrees")]
    out |= {"controls_generic_compared": len(agreement), "controls_generic_agree": sum(agreement)}
    return out


def cases() -> list[Case]:
    """Every entry as a case of the suite (its half fixed by its id)."""
    return [Case(suite=NAME, id=e.id, inputs=e.model_dump(mode="json")) for e in entries()]


SUITE = Suite(name=NAME, description="G0: freeze-out models from the literature, with published targets (coverage and "
                                     "accuracy)", cases=cases, run_case=run_case, summarise=summarise)
