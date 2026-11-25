"""Which route computes a model, and with which physics (G12): the workbench's "Run this model".

``report`` answers at $0, with no language model, the questions the planner's check recomputes
(``agents.planner``):
- **the route:** a library or typed engine where one covers the model (``classify`` with the generic route off),
  else the generic route where it builds the model (D27), else none, with each refusal's reason;
- **the physics:** for the generic route, at the model's stated point, what it includes (coannihilation, s-channel
  poles, long-range effects, direct detection, annihilation today, the lines, the LHC) and what it leaves out; for a
  library engine, its entry's own list of what it does not compute.

Only the model is built (G1, G2) and its long-range structure read (G7): no relic density and no search is computed,
so the answer is quick.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from adroit.core.model_spec import ModelSpec
from adroit.core.state import StrictModel

NEAR_POLE = 0.10                  # a boson within 10% of twice the dark matter's mass (as the planner's check)
LIBRARY_ONLY = ["the resonance recasts (dijets, dileptons, tt̄, ZZ) and LEP: the library's families have them, the "
                "generic route not yet"]


class RouteReport(StrictModel):
    """What computes the model, why, and the physics included and left out."""
    route: Literal["library", "generic", "none"]
    engine: str = ""
    why: str = ""
    included: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)      # how the engine reads the model (a library map's notes)


def report(spec: ModelSpec) -> RouteReport:
    """The route that computes ``spec`` and its physics (module docstring)."""
    from adroit.parameter_space.classify import Unsupported, classify
    try:
        cls, point, notes = classify(spec, generic_route=False)
    except Unsupported as refusal:
        return generic_report(spec, str(refusal))
    except Exception as error:                     # noqa: BLE001 - a map that fails does not cover the model
        return generic_report(spec, f"{type(error).__name__}: {error}")
    return _library_report(cls, point, notes)


def _library_report(cls, point, notes: list[str]) -> RouteReport:
    from adroit.parameter_space import library
    name = getattr(cls, "family", type(cls).__name__)
    same = cls.model_dump(exclude={"name"})                 # the entry's class, whatever the model is called
    entry = next((e for e in library.BY_ID.values()
                  if type(e.model_class) is type(cls) and e.model_class.model_dump(exclude={"name"}) == same), None)
    domain = cls.domain(point) if hasattr(cls, "domain") else ""
    missing = list(entry.not_computed) if entry is not None else []
    if domain:
        missing.append(f"at the stated point the engine's domain excludes it ({domain}); the generic route then "
                       "computes it (D27)")
    return RouteReport(route="library", engine=f"the library's {name} engine" + (f" ({entry.id})" if entry else ""),
                       why="a validated engine covers the model", included=[
                           f"the {name} engine, validated against its papers, and every search that applies to it"],
                       missing=missing, notes=list(notes))


def generic_report(spec: ModelSpec, refusal: str) -> RouteReport:
    """The generic route's report for a model the library's engines refuse with ``refusal``."""
    from adroit.parameter_space.portals.generic import GenericModel
    engine = GenericModel.for_spec(spec)
    try:
        p = engine.point()
        mb, rules, model = engine.at(p)
    except ValueError as error:
        return RouteReport(route="none", why=f"the library's engines: {refusal}; the generic route: {error}")
    included = ["the mass basis and Feynman rules from the model's own Lagrangian (G1, G2)",
                "every 2 → 2 annihilation at tree level, with s-channel poles and thresholds (G3, G4)"]
    missing: list[str] = []
    _bath(engine, p, mb, rules, included)
    _long_range(engine, p, included, missing)
    _searches(engine, p, included, missing)
    return RouteReport(route="generic", engine="the generic route", why=f"the library's engines: {refusal}",
                       included=included, missing=missing + LIBRARY_ONLY)


def _bath(engine, p, mb, rules, included: list[str]) -> None:
    """Coannihilating states and s-channel poles near threshold."""
    from adroit.parameter_space.portals.generic import bath_states
    dm = mb.spectrum.dark_matter()
    partners = sorted({name.rstrip("~") for name, _, _ in bath_states(mb, rules)} - {dm.name})
    if partners:
        included.append(f"coannihilation with {', '.join(partners)}")
    poles = [x.name for x in rules.particles
             if x.parity == 1 and x.width > 0 and abs(x.mass - 2 * dm.mass_gev) <= NEAR_POLE * 2 * dm.mass_gev]
    if poles:
        included.append(f"the s-channel pole{'s' if len(poles) > 1 else ''} of {', '.join(poles)}, near threshold")


def _long_range(engine, p, included: list[str], missing: list[str]) -> None:
    """G7's long-range effects, and where it refuses."""
    from adroit.parameter_space.portals.generic import _long_range_flags
    found = engine.long_range_effects(p)
    for flag in _long_range_flags(found, engine.bound_states):
        (missing if "not computed" in flag else included).append(flag)
    missing += [f"long-range effects not computed: {why}" for why in found.refused]
    if domain := engine.domain(p):
        missing.append(f"Ωh² at the stated point: {domain}")


def _searches(engine, p, included: list[str], missing: list[str]) -> None:
    """Direct detection, annihilation today, the lines and the LHC."""
    found = engine.scattering(p)
    included.append(f"direct detection ({found.route}; G5)")
    if unknown := engine.today_unknown(p):
        missing.append(f"annihilation today: {unknown}")
    else:
        included.append("annihilation today by channel, with two-body cascades (G6, and G8 where forces act)")
    kind, line = engine.resummed_line(p)
    if line is not None:
        included.append(f"γ-ray lines: the resummed rate ({kind}) with its theory band (D30)")
    elif upper := engine.lines_upper_bound(p):
        missing.append(f"γ-ray lines: {upper}")
    included.append("the LHC: SModelS on the odd spectrum, MadGraph's LO production where no table applies (G9; "
                    "a lower bound)")
