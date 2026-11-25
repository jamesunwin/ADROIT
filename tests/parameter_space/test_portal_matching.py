"""Typed portal parameters must reach the physics without benchmark substitution."""

import math
from pathlib import Path

import pytest

from adroit.constraints import higgs, kinetic_mixing as km
from adroit.core.model_spec import ModelSpec, ModelTerm
from adroit.parameter_space import library
from adroit.parameter_space.classify import Unsupported, classify


def scalar_spec(value: float | None) -> ModelSpec:
    spec = library.entry("higgs_portal_scalar").spec()
    return spec.model_copy(update={"couplings": [c.model_copy(update={"value": value})
                                                for c in spec.couplings]})


@pytest.mark.parametrize("value", [0.001, 1.0, 0.0, -0.03])
def test_scalar_full_lagrangian_coefficient_is_preserved(value: float) -> None:
    spec = scalar_spec(value)
    cls, point, notes = classify(spec)
    # ModelTerm.coupling is C in L; this portal uses V = lambda S^2 H†H / 2.
    assert point.g_chi == pytest.approx(-2.0 * value)
    assert point.m_chi == spec.dark_matter.mass_gev
    assert point.m_med == higgs.M_H
    assert any("g_chi" in note and "lam_H_S" in note for note in notes)
    nucleon_mass = (0.93827208816 + 0.93956542052) / 2
    mu = point.m_chi * nucleon_mass / (point.m_chi + nucleon_mass)
    coefficient = -2 * value * 0.307 * 0.939 / (2 * higgs.M_H ** 2 * point.m_chi)
    expected = mu ** 2 * coefficient ** 2 / math.pi * (0.1973269804e-13) ** 2
    assert cls.dd(point)[1] == pytest.approx(expected, rel=1e-12, abs=0.0)


def test_scalar_audit_pair_has_a_million_fold_rate_difference() -> None:
    small, p_small, _ = classify(scalar_spec(0.001))
    large, p_large, _ = classify(scalar_spec(1.0))
    assert large.dd(p_large)[1] / small.dd(p_small)[1] == pytest.approx(1e6)


def test_scalar_coefficient_expression_and_round_trip() -> None:
    spec = scalar_spec(0.08)
    terms = [t.model_copy(update={"coupling": "-lam_H_S/2"}) if "H" in {o.field for o in t.fields}
             else t for t in spec.terms]
    spec = ModelSpec.model_validate_json(spec.model_copy(update={"terms": terms}).model_dump_json())
    assert classify(spec)[1].g_chi == pytest.approx(0.08)


def test_symbolic_scalar_default_is_named_individually() -> None:
    _, point, notes = classify(scalar_spec(None))
    assert point.g_chi == library.entry("higgs_portal_scalar").point.g_chi
    assert any("default" in n and "lam_H_S" in n and "g_chi" in n for n in notes)


@pytest.mark.parametrize("coefficient", ["unknown", "1/0", "sqrt(-1)"])
def test_invalid_scalar_coefficient_cannot_become_a_benchmark(coefficient: str) -> None:
    spec = scalar_spec(0.01)
    terms = [t.model_copy(update={"coupling": coefficient}) if "H" in {o.field for o in t.fields}
             else t for t in spec.terms]
    with pytest.raises(Unsupported, match="coefficient"):
        classify(spec.model_copy(update={"terms": terms}))


def partner_spec(flavour: str = "dR", value: float = 0.37, generations: int = 1) -> ModelSpec:
    coloured = flavour in ("uR", "dR", "bR")
    charge = 2 / 3 if flavour == "uR" else -1 / 3 if coloured else -1.0
    charges = {"su3": "3" if coloured else "1", "hypercharge": charge}
    return ModelSpec.model_validate({
        "name": "explicit partner", "phase": "unbroken",
        "fields": [
            {"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True,
             "mass_gev": 100},
            {"name": "phi", "role": "mediator", "spin": 0, "mass_gev": 400, "charges": charges},
            {"name": flavour, "role": "standard_model", "spin": 0.5, "chirality": "R",
             "generations": generations, "charges": charges}],
        "couplings": [{"name": "y", "value": value}],
        "terms": [{"fields": [{"field": "phi", "conjugate": True},
                                {"field": "chi", "conjugate": True}, {"field": flavour}],
                   "lorentz": "chiral", "coupling": "y", "plus_hc": True}]})


@pytest.mark.parametrize("flavour", ["uR", "dR", "bR", "eR", "muR", "tauR"])
def test_partner_flavour_and_yukawa_are_preserved(flavour: str) -> None:
    cls, point, _ = classify(partner_spec(flavour))
    assert cls.partner == flavour and cls.majorana
    assert (point.m_chi, point.m_med, point.g_chi) == (100, 400, 0.37)


def test_three_generation_partner_is_not_an_up_only_model() -> None:
    with pytest.raises(Unsupported, match="flavour|generation"):
        classify(partner_spec("uR", generations=3))


def test_left_handed_partner_is_not_a_right_handed_model() -> None:
    spec = partner_spec()
    fields = [f.model_copy(update={"chirality": "L"}) if f.role.value == "standard_model" else f
              for f in spec.fields]
    with pytest.raises(Unsupported, match="right-handed"):
        classify(spec.model_copy(update={"fields": fields}))


def dark_photon_spec(scalar: bool = False) -> ModelSpec:
    return ModelSpec.model_validate({
        "name": "explicit dark photon", "phase": "unbroken",
        "fields": [
            {"name": "chi", "role": "dark_matter", "spin": 0 if scalar else 0.5, "mass_gev": 12,
             "charges": {"extra": {"X": 1}}},
            {"name": "X", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 50},
            {"name": "B", "role": "standard_model", "spin": 1, "self_conjugate": True}],
        "couplings": [{"name": "gD", "value": 0.41}, {"name": "eta", "value": 0.002}],
        "terms": [
            {"fields": [{"field": "X"}, {"field": "B"}], "lorentz": "kinetic_mixing",
             "coupling": "-eta/2"},
            {"fields": [{"field": "X"}, {"field": "chi", "conjugate": True}, {"field": "chi"}],
             "lorentz": "scalar_current" if scalar else "vector", "coupling": "gD"},
            *([{"fields": [{"field": "X"}, {"field": "X"}, {"field": "chi", "conjugate": True},
                            {"field": "chi"}], "lorentz": "scalar", "coupling": "gD**2"}]
              if scalar else [])]})


@pytest.mark.parametrize("scalar", [False, True])
def test_dark_photon_preserves_current_and_hypercharge_mixing(scalar: bool) -> None:
    cls, point, notes = classify(dark_photon_spec(scalar))
    assert cls.scalar_dm is scalar
    assert (point.m_chi, point.m_med, point.g_chi) == (12, 50, 0.41)
    assert point.g_q == pytest.approx(0.002 * km.COS_W)
    assert any("g_q" in n and "eta" in n for n in notes)


def test_majorana_dark_current_is_not_a_dirac_dark_photon() -> None:
    spec = dark_photon_spec()
    fields = [f.model_copy(update={"self_conjugate": True}) if f.name == "chi" else f for f in spec.fields]
    with pytest.raises(Unsupported, match="Dirac|complex"):
        classify(spec.model_copy(update={"fields": fields}))


def test_singlet_potential_is_not_a_specified_mixing_angle() -> None:
    spec = library.entry("singlet_scalar_mixing").spec()
    with pytest.raises(Unsupported, match="mixing|mass.eigenstate"):
        classify(spec)


@pytest.mark.parametrize("flavour", ["dR", "muR"])
def test_dirac_partner_mapping_does_not_change_flavour(flavour: str) -> None:
    spec = partner_spec(flavour, value=0)
    fields = [f.model_copy(update={"self_conjugate": False}) if f.name == "chi" else f for f in spec.fields]
    cls, point, _ = classify(spec.model_copy(update={"fields": fields}))
    assert not cls.majorana and cls.partner == flavour and point.g_chi == 0


def test_partner_without_a_yukawa_is_unsupported() -> None:
    with pytest.raises(Unsupported, match="Yukawa"):
        classify(partner_spec().model_copy(update={"terms": []}))


def test_explicit_additional_higgs_partner_interaction_is_not_discarded() -> None:
    spec = library.entry("tchannel_uR_majorana").spec()
    fields = [f.model_copy(update={"generations": 1}) if f.name == "uR" else f for f in spec.fields]
    with pytest.raises(Unsupported, match="additional interaction"):
        classify(spec.model_copy(update={"fields": fields}))
    couplings = [c.model_copy(update={"value": 0.0}) if c.name == "lam_H_phi" else c for c in spec.couplings]
    cls, point, notes = classify(spec.model_copy(update={"fields": fields, "couplings": couplings}))
    assert cls.partner == "uR" and cls.majorana
    assert point.g_chi == library.entry("tchannel_uR_majorana").point.g_chi
    assert any("default g_chi" in n for n in notes)


@pytest.mark.parametrize("mass", [0, -1, float("nan"), float("inf")])
def test_explicit_invalid_portal_mass_is_not_replaced(mass: float) -> None:
    spec = scalar_spec(0.01)
    fields = [f.model_copy(update={"mass_gev": mass}) if f.name == "S" else f for f in spec.fields]
    with pytest.raises(Unsupported, match="positive finite mass"):
        classify(spec.model_copy(update={"fields": fields}))


def test_dimensionful_quartic_is_not_a_dimensionless_portal_coupling() -> None:
    spec = scalar_spec(0.01)
    couplings = [c.model_copy(update={"mass_dimension": 1}) if c.name == "lam_H_S" else c
                 for c in spec.couplings]
    with pytest.raises(Unsupported, match="dimensionless"):
        classify(spec.model_copy(update={"couplings": couplings}))


def test_scalar_cubic_cannot_be_read_as_the_z2_portal() -> None:
    spec = scalar_spec(0.01)
    terms = [t.model_copy(update={"fields": t.fields[:-1]}) if "H" in _names(t) else t for t in spec.terms]
    with pytest.raises(Unsupported, match="S² H†H"):
        classify(spec.model_copy(update={"terms": terms}))


def _names(term: ModelTerm) -> set[str]:
    return {o.field for o in term.fields}


@pytest.mark.parametrize("scalar", [False, True])
def test_zero_dark_couplings_are_preserved(scalar: bool) -> None:
    spec = dark_photon_spec(scalar)
    spec = spec.model_copy(update={"couplings": [c.model_copy(update={"value": 0}) for c in spec.couplings]})
    _, point, _ = classify(spec)
    assert point.g_chi == point.g_q == 0


def test_unknown_contact_is_not_zero_even_for_zero_dark_current() -> None:
    spec = dark_photon_spec(True)
    terms = [t.model_copy(update={"coupling": "unknown"}) if len(t.fields) == 4 else t for t in spec.terms]
    couplings = [c.model_copy(update={"value": 0}) if c.name == "gD" else c for c in spec.couplings]
    with pytest.raises(Unsupported, match="gauge-related"):
        classify(spec.model_copy(update={"terms": terms, "couplings": couplings}))


def test_generated_dark_charge_does_not_supply_a_current_value() -> None:
    with pytest.raises(Unsupported, match="explicit pure dark current"):
        classify(library.entry("dark_photon_dirac").spec())


def test_direct_sm_coupling_cannot_hide_kinetic_mixing() -> None:
    data = dark_photon_spec().model_dump()
    data["fields"].append({"name": "q", "role": "standard_model", "spin": 0.5})
    data["terms"].append({"fields": [{"field": "q", "conjugate": True}, {"field": "q"}, {"field": "X"}],
                          "lorentz": "vector", "coupling": "0.1"})
    with pytest.raises(Unsupported, match="additional interaction"):
        classify(ModelSpec.model_validate(data))


def test_field_order_does_not_change_the_dark_photon_mapping() -> None:
    spec = dark_photon_spec()
    reordered = spec.model_copy(update={"fields": list(reversed(spec.fields))})
    assert classify(spec) == classify(reordered)


@pytest.mark.needs("diamx", "cdmslite", "solar_model")
def test_track1_retains_explicit_scalar_coupling_and_mapping_notes(tmp_path: Path) -> None:
    from adroit.orchestrator import track1
    from adroit.parameter_space.scan import Axis
    spec = scalar_spec(0.02)
    # The requested coupling scan may override its axis, but the classified input
    # and unscanned parameters must remain faithful and survive result serialisation.
    request = track1.Track1Request(spec=spec, literature=False, workers=1,
                                  x=Axis(parameter="m_chi", low=80, high=100, n=2),
                                  y=Axis(parameter="g_chi", low=0.01, high=0.03, n=2))
    result = track1.run(request, tmp_path)
    saved = track1.Track1Result.model_validate_json(result.model_dump_json())
    assert saved.fixed.g_chi == -0.04
    assert saved.scan.request.fixed == saved.fixed
    assert saved.request.spec == spec
    assert "lam_H_S" in track1.report(saved)
    assert sorted({p.point.g_chi for p in saved.scan.points}) == [0.01, 0.03]


def test_track1_reports_ambiguous_mixing_without_a_scan(tmp_path: Path) -> None:
    from adroit.orchestrator import track1
    request = track1.Track1Request(spec=library.entry("singlet_scalar_mixing").spec(), literature=False)
    result = track1.run(request, tmp_path)
    assert result.scan is None and "mixing" in result.unsupported
    assert "UNDETERMINED" in track1.report(result)


def broken_scalar_spec() -> ModelSpec:
    return ModelSpec.model_validate({
        "name": "broken scalar portal", "phase": "broken",
        "fields": [{"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True, "mass_gev": 80},
                   {"name": "h", "role": "standard_model", "spin": 0, "self_conjugate": True,
                    "mass_gev": higgs.M_H}],
        "couplings": [{"name": "lam", "value": 0.07}],
        "terms": [{"fields": [{"field": "S"}, {"field": "S"}, {"field": "h"}],
                   "lorentz": "scalar", "coupling": "-lam*v/2"},
                  {"fields": [{"field": "S"}, {"field": "S"}, {"field": "h"}, {"field": "h"}],
                   "lorentz": "scalar", "coupling": "-lam/4"}]})


def test_gauge_related_broken_scalar_coefficients_match_the_same_portal() -> None:
    spec = broken_scalar_spec()
    cls, point, _ = classify(spec)
    assert point.g_chi == pytest.approx(0.07)
    assert point.m_med == higgs.M_H
    assert cls.nucleon(point).c1_p == pytest.approx(0.07 * 0.307 * 0.939 / (2 * higgs.M_H ** 2 * 80))


@pytest.mark.parametrize("change", ["missing", "inconsistent", "mass"])
def test_incomplete_or_different_broken_higgs_models_are_rejected(change: str) -> None:
    spec = broken_scalar_spec()
    if change == "missing":
        spec = spec.model_copy(update={"terms": spec.terms[:1]})
    elif change == "inconsistent":
        spec = spec.model_copy(update={"terms": [spec.terms[0], spec.terms[1].model_copy(update={"coupling": "-lam/2"})]})
    else:
        spec = spec.model_copy(update={"fields": [spec.fields[0], spec.fields[1].model_copy(update={"mass_gev": 130})]})
    with pytest.raises(Unsupported, match="Higgs"):
        classify(spec)


def test_each_unspecified_partner_mass_has_its_own_default_note() -> None:
    spec = partner_spec()
    fields = [f.model_copy(update={"mass_gev": None}) for f in spec.fields]
    _, point, notes = classify(spec.model_copy(update={"fields": fields}))
    assert point.g_chi == 0.37
    assert any("default m_chi" in n for n in notes)
    assert any("default m_med" in n for n in notes)


def test_scalar_dark_matter_refusal_names_the_scalar_maps_not_the_dirac_scan() -> None:
    """Live check L3: a real scalar with a Z2-odd partner was refused as 'the scan computes Dirac fermion dark
    matter'; the reason now names the maps that exist for scalar dark matter and the field that breaks them."""
    from adroit.core.model_spec import Charges, FieldRole, ModelField
    spec = library.entry("higgs_portal_scalar").spec()
    partner = ModelField(name="A", role=FieldRole.other, spin=0, self_conjugate=True, mass_gev=70.0,
                         charges=Charges(), dark_parity=-1)
    with pytest.raises(Unsupported) as refused:
        classify(spec.model_copy(update={"fields": [*spec.fields, partner]}))
    text = str(refused.value)
    assert "Dirac fermion dark matter" not in text and "real scalar" in text
    assert "Higgs portal" in text and "dark photon" in text and "A (spin 0, other)" in text
    from adroit.parameter_space.classify import _dark_matter_refusal
    dm = spec.dark_matter.model_copy(update={"spin": 0.5})
    majorana = spec.model_copy(update={"fields": [dm if f is spec.dark_matter else f for f in spec.fields]})
    assert "t-channel" in _dark_matter_refusal(majorana)
