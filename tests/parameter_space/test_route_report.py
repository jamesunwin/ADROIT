"""Which route computes a model, and with which physics (``parameter_space.route_report``; G12's "Run this model")."""

import math

from adroit.core.model_spec import ModelSpec
from adroit.evaluation import zoo
from adroit.parameter_space import route_report


def test_a_library_model_names_its_engine():
    """The zoo's GAMBIT scalar singlet maps to the library's Higgs portal: no generic route is needed."""
    e = next(x for x in zoo.entries() if x.id == "scalar_singlet_higgs_portal_gambit")
    out = route_report.report(zoo._spec(e, e.targets[0]))
    assert out.route == "library" and "(higgs_portal_scalar)" in out.engine and out.included


def test_a_dark_qed_model_takes_the_generic_route_with_its_bound_states():
    spec = ModelSpec.model_validate({"name": "dark_qed", "phase": "broken", "fields": [
        {"name": "X", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 1000.0,
         "charges": {"extra": {"Ad": 1.0}}},
        {"name": "Ad", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 0.0}],
        "couplings": [{"name": "e_d", "value": math.sqrt(4 * math.pi * 0.03)}],
        "terms": [{"fields": [{"field": "X", "conjugate": True}, {"field": "X"}, {"field": "Ad"}],
                   "lorentz": "vector", "coupling": "e_d"}]})
    out = route_report.report(spec)
    assert out.route == "generic" and out.why.startswith("the library's engines")
    assert any("hydrogen-like" in x for x in out.included)
    assert any("direct detection" in x for x in out.included) and any("resonance recasts" in x for x in out.missing)


def test_a_model_neither_route_builds_says_why():
    spec = ModelSpec.model_validate({"name": "charged", "phase": "unbroken", "fields": [
        {"name": "E", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 500.0,
         "charges": {"hypercharge": 1.0}}]})
    out = route_report.report(spec)
    assert out.route == "none" and "the generic route:" in out.why and not out.included
