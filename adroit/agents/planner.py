"""G10's planner: a typed model → a typed computation plan, every criterion of which the core recomputes (paid;
opt-in).

The agent reads the model and proposes how to compute it: the route (the library's engine, the generic engine, or
both as a cross-check), the regime (whether long-range effects matter, which states coannihilate, which s-channel
poles lie near threshold) and the theory uncertainties it expects. It plans; it computes nothing. ``check`` then
recomputes each criterion deterministically:
- **route:** whether the library's maps take the model (``classify``) and whether the generic engine builds it;
- **long-range effects:** G7's analysis of the bath (``generic_lr``), and G4's bracket where G7 refuses;
- **coannihilation:** the bath (Z₂-odd states within 30% of the dark matter's mass);
- **resonances:** bosons with a width within 10% of twice the dark matter's mass.

Where the plan and the core disagree, the core's value is used and the disagreement is recorded: a plan never
reaches a verdict that the core would not. A model that neither route takes has the route "none" (the audit's AG-6,
G12: it had been reported as "generic"). The expected uncertainties and the notes are the agent's advice, passed
through unchecked: they are not criteria and decide nothing.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from adroit.agents.llm import StructuredLLM
from adroit.core.model_spec import ModelSpec
from adroit.core.state import StrictModel

DEFAULT_MODEL = "claude-opus-5-5"
NEAR_POLE = 0.10

PLAN_SYSTEM = """You plan how ADROIT should compute a dark matter model's relic density and its searches. You do
not compute anything. Return JSON for the ComputationPlan schema:
- route: "library" if one of ADROIT's validated engines covers the model as written (a Higgs portal, a simplified
  vector or scalar mediator, a t-channel partner, an electroweak multiplet, a dark photon, an inert doublet), "generic"
  if only the generic engine from the model's own Feynman rules can, "both" if both apply (the generic route as a
  cross-check), "none" if neither can.
- long_range: "none", "sommerfeld" (long-range forces change freeze-out: gauge multiplets at the TeV scale,
  coloured partners near degeneracy, light mediators), or "bound_states" (the effect includes bound-state
  formation).
- coannihilators: the names of the fields whose states lie within ~30% of the dark matter's mass.
- resonances: the names of bosons whose mass lies within ~10% of twice the dark matter's mass.
- uncertainties: each {source, size} you expect to dominate (e.g. the scale of α in the potential, ±10% in mass).
- notes: anything a researcher should check first.
Return only the JSON object."""


class Uncertainty(StrictModel):
    source: str
    size: str


class ComputationPlan(StrictModel):
    """The agent's plan (module docstring)."""
    route: Literal["library", "generic", "both", "none"]
    long_range: Literal["none", "sommerfeld", "bound_states"] = "none"
    coannihilators: list[str] = Field(default_factory=list)
    resonances: list[str] = Field(default_factory=list)
    uncertainties: list[Uncertainty] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CheckedPlan(StrictModel):
    """The plan as the core recomputed it, and where the agent's differed."""
    plan: ComputationPlan
    disagreements: list[str] = Field(default_factory=list)


class Planner:
    """A model → ``ComputationPlan`` (module docstring)."""

    def __init__(self, llm: StructuredLLM, model: str = DEFAULT_MODEL) -> None:
        self.llm, self.model = llm, model

    def run(self, spec: ModelSpec, run_id: str | None = None) -> CheckedPlan:
        """The agent's plan, checked (``check``)."""
        message = [{"role": "user", "content": f"The model:\n{spec.model_dump_json(indent=1)}"}]
        proposed = self.llm.complete_structured(PLAN_SYSTEM, message, ComputationPlan, model=self.model,
                                                run_id=run_id, actor="planner")
        return check(spec, proposed)


def core_view(spec: ModelSpec) -> dict:
    """The criteria as the core computes them: route, long-range regime, coannihilators, resonances."""
    from adroit.parameter_space.classify import Unsupported, classify
    from adroit.parameter_space.portals.generic import GenericModel, bath_states
    try:
        classify(spec, generic_route=False)          # the library's own maps (G12: the default now falls back)
        library = True
    except Unsupported:
        library = False
    except Exception:                                  # noqa: BLE001 - a map failing is "not covered"
        library = False
    view = {"library": library, "generic": True, "long_range": "none", "coannihilators": set(), "resonances": set()}
    try:
        engine = GenericModel.of(spec)
        p = engine.point()
        mb, rules, _ = engine.at(p)
    except ValueError:
        view["generic"] = False
        return view
    dm = mb.spectrum.dark_matter()
    names = {s.name: s for s in mb.spectrum.states}
    from adroit.parameter_space.portals.generic_checks import dominant_field
    for name, _, _ in bath_states(mb, rules):
        state = names.get(name.rstrip("~"))
        if state is not None and state.name != dm.name:
            view["coannihilators"].add(dominant_field(mb, state).name)
    for x in rules.particles:
        if x.parity == 1 and x.width > 0 and abs(x.mass - 2 * dm.mass_gev) <= NEAR_POLE * 2 * dm.mass_gev:
            view["resonances"].add(x.name)
    found = engine.long_range_effects(p)
    if found.groups:
        view["long_range"] = "bound_states" if any(g.bound for g in found.groups) else "sommerfeld"
    elif found.refused and engine.domain(p):
        view["long_range"] = "sommerfeld"
    return view


def check(spec: ModelSpec, plan: ComputationPlan) -> CheckedPlan:
    """The plan with every criterion recomputed by the core (module docstring)."""
    view = core_view(spec)
    out, disagreements = plan.model_copy(deep=True), []
    route = ("both" if view["library"] and view["generic"] else "library" if view["library"]
             else "generic" if view["generic"] else "none")
    if plan.route != route:
        disagreements.append(f"route: the plan says {plan.route}, the core {route}")
        out.route = route
    if plan.long_range != view["long_range"]:
        disagreements.append(f"long-range effects: the plan says {plan.long_range}, the core {view['long_range']}")
        out.long_range = view["long_range"]
    for key in ("coannihilators", "resonances"):
        said, found = set(getattr(plan, key)), view[key]
        if said != found:
            disagreements.append(f"{key}: the plan says {sorted(said) or 'none'}, the core {sorted(found) or 'none'}")
            setattr(out, key, sorted(found))
    return CheckedPlan(plan=out, disagreements=disagreements)
