"""The model zoo's harness (G0, 2026-10-13): a mapped model's targets are computed and compared; a model no engine
covers is refused with its reason; the controls are summarised apart."""

import math

import pytest

from adroit.core.state import StrictModel
from adroit.evaluation import core, zoo
from adroit.parameter_space.classes import Point

SOURCE = {"arxiv": "2107.09688", "page": 3, "location": "Table I", "quote": "Majorana fermion 3 2.86 ± 0.01"}
WINO = {"id": "wino_control", "title": "the wino", "category": "electroweak_multiplet", "in_library": True,
        "reference": {"arxiv": "2107.09688"}, "needs": ["sommerfeld"],
        "spec": {"phase": "unbroken", "fields": [{"name": "chi", "role": "dark_matter", "spin": 0.5,
                                                   "self_conjugate": True, "dark_parity": -1, "mass_gev": 2860.0,
                                                   "charges": {"su2": 3}}]},
        "targets": [{"quantity": "thermal_mass_gev", "value": 2860.0, "uncertainty": 10.0, "source": SOURCE},
                    {"quantity": "sigma_si_cm2", "value": 2.3e-47, "source": SOURCE}]}
SINGLET_DOUBLET = {"id": "singlet_doublet", "title": "singlet–doublet", "category": "mixed_multiplets",
                   "reference": {"arxiv": "1109.2604"}, "needs": ["ewsb_mixing"],
                   "spec": {"phase": "unbroken", "fields": [
                       {"name": "S", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
                        "mass_gev": 200.0},
                       {"name": "D1", "role": "other", "spin": 0.5, "chirality": "L", "dark_parity": -1,
                        "mass_gev": 300.0, "charges": {"su2": 2, "hypercharge": -0.5}},
                       {"name": "D2", "role": "other", "spin": 0.5, "chirality": "L", "dark_parity": -1,
                        "mass_gev": 300.0, "charges": {"su2": 2, "hypercharge": 0.5}}]},
                   "targets": [{"quantity": "omega_h2", "value": 0.12, "source": SOURCE}]}


def test_a_control_is_computed_and_a_model_no_engine_covers_is_refused_with_its_reason(monkeypatch):
    """The wino's engine takes minutes: its numbers are stubbed at the entry point ``run_case`` calls
    (``computed_by``; the fresh audit's F19-08: the stub had replaced ``compute``, which ``run_case`` does not call,
    so the real engine ran), and so is its generic cross-check; the stubs count their calls. The numbers themselves
    are the slow test below."""
    from adroit.parameter_space.classify import Unsupported
    real, calls = zoo.computed_by, []

    def computed_by(entry, target):
        if entry.id == "wino_control":
            calls.append(target.quantity)
            return {"thermal_mass_gev": 2880.0, "sigma_si_cm2": 2.3e-47}[target.quantity], "", "library"
        return real(entry, target)
    monkeypatch.setattr(zoo, "computed_by", computed_by)
    monkeypatch.setattr(zoo, "route_agreement", lambda entry: calls.append("generic") or {})
    control = zoo.run_case(core.Case(suite=zoo.NAME, id="wino_control", inputs=WINO))
    assert calls == ["thermal_mass_gev", "sigma_si_cm2", "generic"]
    assert control.metrics["status"] == "computed" and control.metrics["compared"] == 2
    assert control.metrics["t0_thermal_mass_gev_met"] and control.passed
    assert control.metrics["engine"] == "ElectroweakMultiplet"                    # the standard engine that ran it
    refused = zoo.run_case(core.Case(suite=zoo.NAME, id="singlet_doublet", inputs=SINGLET_DOUBLET))
    assert refused.metrics["status"] == "refused" and refused.metrics["reason"] and refused.passed is False
    summary = zoo.summarise([control, refused], [])
    assert summary["controls_computed"] == 1 and summary["new_refused"] == 1 and summary["controls_targets_met"] == 2
    assert issubclass(Unsupported, ValueError)


@pytest.mark.slow
def test_the_wino_control_is_computed_by_its_engine():
    """The control above with nothing stubbed: the library's electroweak-multiplet engine computes both targets."""
    control = zoo.run_case(core.Case(suite=zoo.NAME, id="wino_control", inputs=WINO))
    assert control.metrics["status"] == "computed" and control.metrics["compared"] == 2
    assert control.metrics["engine"] == "ElectroweakMultiplet"
    assert control.metrics["t0_thermal_mass_gev_met"], control.metrics


def test_a_real_thermal_mass_is_found_by_bisection():
    """The Dirac 5-plet through the general n-plet engine: 10.75 TeV at Ωh² = 0.12 against Bottaro et al.'s 9.9 ±
    0.7 TeV (within the 10% default)."""
    entry = zoo.ZooEntry.model_validate({**WINO, "id": "quintuplet_dirac", "spec": {"phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 9900.0,
         "charges": {"su2": 5, "hypercharge": 1.0}}]}, "targets": [
        {"quantity": "thermal_mass_gev", "value": 9900.0, "uncertainty": 700.0, "source": SOURCE}]})
    value, why = zoo.compute(entry, entry.targets[0])
    assert why == "" and value == pytest.approx(10750.0, rel=0.02) and zoo.met(entry.targets[0], value)


def test_the_tolerance_is_the_sources_or_the_default():
    target = zoo.ZooTarget(quantity="omega_h2", value=0.12, uncertainty=0.06, source=zoo.ZooSource(**SOURCE))
    assert zoo.met(target, 0.17) and not zoo.met(target, 0.19)                     # ±50% stated
    sigma = zoo.ZooTarget(quantity="sigma_si_cm2", value=1e-47, source=zoo.ZooSource(**SOURCE))
    assert zoo.met(sigma, 1.9e-47) and zoo.met(sigma, 0.6e-47) and not zoo.met(sigma, 2.2e-47)


def test_the_halves_are_fixed_by_the_id():
    case = core.Case(suite=zoo.NAME, id="wino_control")
    assert case.half is core.half_of(zoo.NAME, "wino_control")


def test_the_root_nearest_the_published_value_is_found():
    """Ωh² crosses the target twice (below and above a resonance, say): the crossing nearest the published value."""
    def omega(x):
        return (x - 1.0) * (x - 4.0)
    assert zoo._solve(omega, 1.2)[0] == pytest.approx(1.0, rel=2e-3)
    assert zoo._solve(omega, 3.5)[0] == pytest.approx(4.0, rel=2e-3)
    assert "does not reach" in zoo._solve(lambda x: x + 1.0, 1.0)[1]                # no crossing in × [1/3, 3]
    assert "does not reach" in zoo._solve(lambda x: None if x > 1.5 else x - 2.0, 1.0)[1]   # not computed past 1.5
    assert "not computed at the published" in zoo._solve(lambda x: None, 1.0)[1]


class Forbidden(StrictModel):
    """A stand-in engine: Ωh² = 0.12 exp(40(Δ − 0.3)), Δ = m_med/m_χ − 1, as for forbidden channels."""
    sommerfeld: bool = True

    def omega_h2(self, p: Point) -> float:
        return 0.12 * math.exp(40.0 * (p.m_med / p.m_chi - 1.0 - 0.3))


def test_a_thermal_splitting_and_the_engine_switches(monkeypatch):
    entry = zoo.ZooEntry.model_validate({**SINGLET_DOUBLET, "targets": [
        {"quantity": "thermal_splitting", "value": 0.309, "uncertainty": 0.003, "omega_target": 0.12,
         "source": SOURCE},
        {"quantity": "omega_h2", "value": 0.12, "engine_options": {"sommerfeld": False}, "source": SOURCE},
        {"quantity": "omega_h2", "value": 0.12, "engine_options": {"bound_states": False}, "source": SOURCE}]})
    monkeypatch.setattr(zoo, "mapped", lambda e, t: (Forbidden(), Point(m_chi=1.0, m_med=1.3), "typed", ""))
    value, why = zoo.compute(entry, entry.targets[0])
    assert value == pytest.approx(0.3, rel=2e-3) and zoo.met(entry.targets[0], value)    # Δ within 10%
    assert zoo.compute(entry, entry.targets[1])[0] == pytest.approx(0.12)
    value, why = zoo.compute(entry, entry.targets[2])                                     # a switch it lacks
    assert value is None and "no switch bound_states" in why


def test_a_library_model_the_typed_route_refuses_is_computed_by_its_library_engine():
    """The higgsino with its splitting operator: the n-plet map refuses the extra term, so the library's validated
    higgsino engine computes it, and the refusal is kept."""
    entry = zoo.ZooEntry.model_validate({
        **WINO, "id": "higgsino_with_operator", "library": "higgsino",
        "spec": {"phase": "unbroken", "fields": [
            {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 1080.0,
             "charges": {"su2": 2, "hypercharge": 0.5}},
            {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}],
                 "couplings": [{"name": "y0", "mass_dimension": -1}],
                 "terms": [{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi", "conjugate": True},
                                       {"field": "H"}, {"field": "H"}], "lorentz": "scalar", "coupling": "y0/4",
                            "plus_hc": True}]},
        "targets": [{"quantity": "thermal_mass_gev", "value": 1080.0, "point": {"m_chi": 1080.0, "m_med": 1.0,
                                                                                 "g_q": 0.0}, "source": SOURCE}]})
    cls, point, route, refusal = zoo.mapped(entry, entry.targets[0])
    assert route == "library" and "gauge interactions only" in refusal
    assert type(cls).__name__ == "ElectroweakMultiplet" and point.m_chi == 1080.0
    with pytest.raises(ValueError, match="slots"):
        zoo.ZooEntry.model_validate({**entry.model_dump(), "targets": [{**entry.targets[0].model_dump(),
                                                                         "point": {}}]})


@pytest.mark.skipif(not zoo.DATA.exists(), reason="the zoo's data are not written yet")
def test_every_entry_is_typed_and_has_a_sourced_target():
    from adroit.parameter_space import library
    found = zoo.entries()
    assert len(found) == 31 and sum(e.in_library for e in found) == 14
    for entry in found:
        assert entry.targets and all(t.source.quote and t.source.page >= 1 for t in entry.targets)
        assert all(zoo._spec(entry, t).dark_matter for t in entry.targets)        # every benchmark is a ModelSpec
        if entry.library:
            library.entry(entry.library)


def test_a_target_may_override_a_vacuum_value():
    """D20: a benchmark that changes a dark gauge coupling at fixed vector mass needs its own v_φ = m_V/g_V."""
    spec = {"phase": "unbroken", "fields": [
        {"name": "Vx", "role": "dark_matter", "spin": 1, "self_conjugate": True, "dark_parity": -1},
        {"name": "Phi", "role": "mediator", "spin": 0, "charges": {"extra": {"Vx": 1.0}}, "vev_gev": 22.66}]}
    first = zoo.ZooTarget(quantity="omega_h2", value=0.1, source=zoo.ZooSource(**SOURCE))
    second = zoo.ZooTarget(quantity="omega_h2", value=0.1, source=zoo.ZooSource(**SOURCE),
                           overrides={"vevs": {"Phi": 41.88}, "couplings": {}})
    entry = zoo.ZooEntry(id="vev_override", title="t", category="gauged_u1", reference={"arxiv": "0000.00000"},
                         spec=spec, targets=[first, second])
    assert zoo._spec(entry, first).field("Phi").vev_gev == 22.66
    assert zoo._spec(entry, second).field("Phi").vev_gev == 41.88


def test_a_target_outside_the_typed_engines_domain_falls_back_to_the_generic_route():
    """The owner (2026-10-15): a Majorana χ with a 150 GeV lepton partner, below the library t-channel engine's
    domain (m_φ ≳ 200 GeV), is computed by the generic route, and the route is recorded."""
    spec = {"phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1, "mass_gev": 120.0},
        {"name": "phi", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 150.0,
         "charges": {"hypercharge": -1.0}},
        {"name": "muR", "role": "standard_model", "spin": 0.5, "chirality": "R", "charges": {"hypercharge": -1.0}}],
        "couplings": [{"name": "y", "value": 1.0}],
        "terms": [{"fields": [{"field": "phi", "conjugate": True}, {"field": "chi"}, {"field": "muR"}],
                   "lorentz": "chiral", "coupling": "y", "plus_hc": True}]}
    entry = zoo.ZooEntry(id="light_lepton_partner", title="t", category="t_channel",
                         reference={"arxiv": "0000.00000"}, spec=spec,
                         targets=[zoo.ZooTarget(quantity="omega_h2", value=0.12, source=zoo.ZooSource(**SOURCE))])
    cls, point, route, _ = zoo.mapped(entry, entry.targets[0])
    assert route == "typed" and "200 GeV" in cls.domain(point)
    value, why, by = zoo.computed_by(entry, entry.targets[0])
    assert value is not None and value > 0 and by.startswith("generic (fallback: the typed engine's domain")


def test_route_agreement_does_not_compare_the_generic_route_with_itself(monkeypatch):
    """The audit's G3/G4-10 (G12): where the library's engine refuses a control's target and the generic route
    computes it, ``route_agreement`` has no reference; it had reported the generic against itself (ratio 1)."""
    entry = zoo.ZooEntry(id="synthetic_control", title="t", category="t_channel", in_library=True,
                         reference={"arxiv": "0000.00000"}, spec={"phase": "unbroken", "fields": []},
                         targets=[zoo.ZooTarget(quantity="omega_h2", value=0.12, source=zoo.ZooSource(**SOURCE))])
    monkeypatch.setattr(zoo, "_generic", lambda e, t: (None, None))
    monkeypatch.setattr(zoo, "_evaluate", lambda cls, point, route, t: (0.11, ""))
    monkeypatch.setattr(zoo, "computed_by", lambda e, t: (0.11, "", "generic (fallback: the typed engine's domain)"))
    out = zoo.route_agreement(entry)
    assert "t0_omega_h2_generic_ratio" not in out and "refuses" in out["t0_omega_h2_generic_why"]
    monkeypatch.setattr(zoo, "computed_by", lambda e, t: (0.10, "", "typed"))
    assert zoo.route_agreement(entry)["t0_omega_h2_generic_ratio"] == pytest.approx(1.1)
