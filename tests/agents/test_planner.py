"""G10's planner with the offline fake: every criterion recomputed by the core (``agents.planner``)."""

from adroit.agents.llm import FakeLLMClient
from adroit.agents.planner import ComputationPlan, Planner
from adroit.evaluation import zoo


def test_the_core_overrides_a_wrong_plan_and_records_why():
    e = next(x for x in zoo.entries() if x.id == "wino_majorana_triplet_bottaro")
    spec = zoo._spec(e, e.targets[0])
    wrong = ComputationPlan(route="generic", long_range="none", coannihilators=[], resonances=["Z"])
    checked = Planner(FakeLLMClient([wrong])).run(spec)
    assert checked.plan.long_range == "bound_states" and checked.plan.resonances == []
    assert any(d.startswith("long-range effects") for d in checked.disagreements)
    assert checked.plan.route in ("both", "library")


def test_a_model_neither_route_takes_is_planned_as_none():
    """The audit's AG-6 (G12): a model the library and G1 both refuse (here, no neutral Z₂-odd state) is "none", with
    the agent's "generic" recorded as a disagreement."""
    from adroit.core.model_spec import ModelSpec
    spec = ModelSpec.model_validate({"name": "charged", "phase": "unbroken", "fields": [
        {"name": "E", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 500.0,
         "charges": {"hypercharge": 1.0}}]})
    checked = Planner(FakeLLMClient([ComputationPlan(route="generic")])).run(spec)
    assert checked.plan.route == "none"
    assert any(d.startswith("route: the plan says generic, the core none") for d in checked.disagreements)
