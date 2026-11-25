"""R5 (audit M9): couplings the model ties together stay tied along a scan."""

from pathlib import Path

import pytest
import sympy
import yaml

from adroit.core.model_spec import ModelSpec
from adroit.parameter_space import library, relations
from adroit.parameter_space.classify import Unsupported, classify, coupling_relations
from adroit.parameter_space.relations import CouplingRelation
from adroit.parameter_space.scan import Axis, ScanRequest, _point_at
from adroit.parameter_space.scan_setup import model_relations, preview

DM13 = Path(__file__).resolve().parents[2] / "docs" / "dm13"


def _shared(dm: str = "g", quark: str = "g") -> ModelSpec:
    """DM13's vector mediator with one coupling symbol g for the dark matter and the quarks."""
    data = yaml.safe_load((DM13 / "vector_mediator.yaml").read_text())
    data["couplings"] = [{"name": "g", "value": 0.3}, {"name": "h", "value": 0.2}]
    data["terms"][0]["coupling"], data["terms"][1]["coupling"] = dm, quark
    return ModelSpec.model_validate(data)


def test_one_symbol_for_dark_matter_and_quarks_ties_g_q_to_g_chi() -> None:
    spec = _shared()
    cls, point, _ = classify(spec)
    assert point.g_chi == point.g_q == 0.3
    assert coupling_relations(spec) == [CouplingRelation(derived="g_q", source="g_chi", factor=1.0)]


def test_a_shared_symbol_model_keeps_g_chi_equal_to_g_q_along_its_scan() -> None:
    spec = _shared()
    cls, point, _ = classify(spec)
    x, y = Axis(parameter="m_chi", low=10.0, high=1000.0, n=4), Axis(parameter="g_q", low=1e-3, high=1.0, n=5)
    ties = model_relations(spec, "", x, y)                       # g_q is scanned, so g_χ follows it
    assert ties == [CouplingRelation(derived="g_chi", source="g_q", factor=1.0)]
    setup = preview(cls, point, x, y, coupling_relations=ties)
    assert setup.derived == {"g_chi": "1 * g_q"} and "g_chi" not in setup.fixed
    request = ScanRequest(model_class=cls, fixed=point, x=x, y=y, coupling_relations=ties)
    for gx in x.values():
        for gy in y.values():
            p = _point_at(request, gx, gy)
            assert p.g_chi == p.g_q == gy


def test_proportional_and_unrelated_couplings() -> None:
    assert coupling_relations(_shared("g", "g/3")) == [CouplingRelation(derived="g_q", source="g_chi", factor=1 / 3)]
    assert coupling_relations(_shared("g", "h")) == []
    with pytest.raises(Unsupported, match="not proportional"):
        coupling_relations(_shared("g", "g**2"))


def test_a_scalar_mediators_yukawa_factor_is_tied_without_its_mass() -> None:
    g = sympy.Symbol("g")
    assert relations.detect({"g_chi": g, "g_q": g, "g_l": -g}) == [
        CouplingRelation(derived="g_q", source="g_chi", factor=1.0),
        CouplingRelation(derived="g_l", source="g_chi", factor=-1.0)]


def test_orienting_puts_the_scanned_coupling_first_and_refuses_two_tied_axes() -> None:
    ties = [CouplingRelation(derived="g_q", source="g_chi", factor=1 / 3),
            CouplingRelation(derived="g_l", source="g_chi", factor=-1.0)]
    turned = relations.orient(ties, ("m_chi", "g_l"))
    assert {(r.derived, r.source, round(r.factor, 12)) for r in turned} == {("g_chi", "g_l", -1.0),
                                                                            ("g_q", "g_l", round(-1 / 3, 12))}
    with pytest.raises(ValueError, match="only one of them"):
        relations.orient(ties, ("g_q", "g_l"))
    with pytest.raises(ValueError, match="independent scan axis"):
        relations.check(ties, ("g_q", "m_chi"))


@pytest.mark.parametrize("entry", library.ENTRIES, ids=lambda e: e.id)
def test_each_library_entrys_relations_hold_along_its_scan(entry) -> None:
    ties = model_relations(None, entry.id, entry.x, entry.y)
    request = ScanRequest(model_class=entry.model_class, fixed=entry.point, x=entry.x, y=entry.y,
                          mediator_ratio=entry.mediator_ratio, coupling_relations=ties)
    for r in ties:
        assert getattr(entry.point, r.derived) == pytest.approx(r.factor * getattr(entry.point, r.source))
    for gx in entry.x.values()[::5]:
        for gy in entry.y.values()[::5]:
            p = _point_at(request, gx, gy)
            assert all(getattr(p, r.derived) == pytest.approx(r.factor * getattr(p, r.source)) for r in ties)


def test_the_lmu_entry_ties_g_chi_to_g_q_at_unit_charge() -> None:
    e = library.entry("lmu_minus_ltau")
    request = ScanRequest(model_class=e.model_class, fixed=e.point, x=e.x, y=e.y, mediator_ratio=e.mediator_ratio,
                          coupling_relations=model_relations(None, e.id, e.x, e.y))
    p = _point_at(request, 3.0, 0.04)
    assert p.g_chi == p.g_q == 0.04 and p.m_med == 9.0


def test_no_relations_leave_a_requests_serialised_form_unchanged() -> None:
    e = library.entry("dmwg_V1")
    request = ScanRequest(model_class=e.model_class, fixed=e.point, x=e.x, y=e.y)
    assert "coupling_relations" not in request.model_dump(mode="json")


def test_the_lmu_scan_now_has_thermal_roots_at_g_prime_0_023_to_0_055() -> None:
    """Audit M9: at fixed g_χ = 10⁻³ the plane was overabundant everywhere; on the unit-charge tie the relic
    contour crosses g′ = 0.023 (m_χ = 1 GeV) to 0.055 (10 GeV)."""
    import math
    from scipy.optimize import brentq
    e = library.entry("lmu_minus_ltau")
    request = ScanRequest(model_class=e.model_class, fixed=e.point, x=e.x, y=e.y, mediator_ratio=e.mediator_ratio,
                          coupling_relations=model_relations(None, e.id, e.x, e.y))
    def log_excess(m, log_g):
        return math.log(e.model_class.omega_h2(_point_at(request, m, math.exp(log_g))) / 0.12)
    roots = [math.exp(brentq(lambda lg: log_excess(m, lg), math.log(1e-4), math.log(0.1), xtol=1e-4))
             for m in (1.0, 10.0)]
    assert roots == pytest.approx([0.0231, 0.0553], rel=0.03)
    untied = request.model_copy(update={"coupling_relations": []})
    assert e.model_class.omega_h2(_point_at(untied, 1.0, 0.1)) > 1.0


def test_an_unstated_mediator_mass_is_an_explicit_assumption() -> None:
    data = yaml.safe_load((DM13 / "vector_mediator.yaml").read_text())
    data["fields"][1].pop("mass_gev")
    _, point, notes = classify(ModelSpec.model_validate(data))
    assert point.m_med == 1000.0
    assert any(n.startswith("assumed m_med = 1000 GeV: Zp's mass was not stated") for n in notes)


def test_multi_symbol_couplings_in_a_fixed_ratio_are_related() -> None:
    """A Lagrangian with g_χ = g h and g_q = 2 g h fixes g_q = 2 g_χ; g h and g alone stay refused."""
    import sympy
    from adroit.parameter_space import relations
    g, h = sympy.symbols("g h")
    (rel,) = relations.detect({"g_chi": g * h, "g_q": 2 * g * h})
    assert (rel.derived, rel.source, rel.factor) == ("g_q", "g_chi", 2.0)
    with pytest.raises(ValueError, match="not proportional"):
        relations.detect({"g_chi": g * h, "g_q": g})
