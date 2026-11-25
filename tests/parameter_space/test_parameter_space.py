"""DM13: the computable classes, the envelope, the scan, the verdict and the plots (offline)."""

import math
from pathlib import Path

import pytest
import yaml

from adroit.constraints import spin1
from adroit.core.model_spec import ModelSpec
from adroit.parameter_space import limits, plots
from adroit.parameter_space.classes import Point, ScalarClass, Spin1Class, fermi_ratio
from adroit.parameter_space.classify import Unsupported, classify
from adroit.parameter_space.scan import Axis, PointResult, ScanRequest, ScanResult, evaluate
from adroit.parameter_space.verdict import _crossings, judge_point, verdict

MODELS = Path(__file__).resolve().parents[2] / "docs" / "dm13"
V1 = Spin1Class(kind=spin1.Spin1Kind.vector, name="V1")


def spec(name: str) -> ModelSpec:
    return ModelSpec.model_validate(yaml.safe_load((MODELS / f"{name}.yaml").read_text()))


def test_axis_values_and_unknown_parameter():
    assert Axis(parameter="m_chi", low=1, high=100, n=3).values() == pytest.approx([1, 10, 100])
    assert Axis(parameter="g_q", low=0, high=1, log=False, n=3).values() == pytest.approx([0, 0.5, 1])
    with pytest.raises(ValueError, match="unknown parameter"):
        Axis(parameter="lambda", low=1, high=2).values()


def test_scalar_width_is_the_textbook_one_for_a_single_channel():
    p = Point(m_chi=400.0, m_med=50.0, g_chi=1.0, g_q=1.0)          # S → bb̄ and lighter only
    b = next(f for f in spin1.FERMIONS if f.name == "b")
    beta = math.sqrt(1 - 4 * b.mass_gev ** 2 / 50.0 ** 2)
    bb = 3 * 50.0 * (b.mass_gev / 246.22) ** 2 * beta ** 3 / (8 * math.pi)
    assert ScalarClass().width(p) > bb
    assert ScalarClass().width(p) == pytest.approx(bb, rel=0.25)      # b dominates over c and τ (g_ℓ = 0)


def test_scalar_couplings_give_p_wave_and_s_wave_as_expected():
    p = Point(m_chi=100.0, m_med=500.0, g_chi=1.0, g_q=1.0)
    scalar = sum(ScalarClass().sigma_v_today(p, 1e-3).values())
    pseudo = sum(ScalarClass(dm_pseudoscalar=True, sm_pseudoscalar=True).sigma_v_today(p, 1e-3).values())
    assert pseudo > 1e4 * scalar                                       # χ̄χ is p-wave, χ̄iγ⁵χ is s-wave


def test_scalar_mediator_pairs_open_above_the_mediator_mass():
    cls = ScalarClass(dm_pseudoscalar=True, sm_pseudoscalar=True)
    light = cls.sigma_v_today(Point(m_chi=400.0, m_med=500.0, g_chi=1.0, g_q=1.0), 1e-3)
    heavy = cls.sigma_v_today(Point(m_chi=600.0, m_med=500.0, g_chi=1.0, g_q=1.0), 1e-3)
    assert light["SS"] == 0.0 and heavy["SS"] > 0.0
    assert 0 < cls.omega_h2(Point(m_chi=600.0, m_med=500.0, g_chi=1.0, g_q=1.0)) < cls.omega_h2(
        Point(m_chi=600.0, m_med=500.0, g_chi=0.5, g_q=1.0))


@pytest.mark.needs("diamx")
def test_direct_detection_kinds():
    p = Point(m_chi=100.0, m_med=500.0, g_chi=1.0, g_q=1.0)
    kind, sigma = ScalarClass().dd(p)
    assert kind == "SI" and 1e-50 < sigma < 1e-40
    assert ScalarClass(dm_pseudoscalar=True).dd(p) == ("momentum-suppressed", 0.0)
    assert V1.dd(p)[0] == "SI"
    assert Spin1Class(kind=spin1.Spin1Kind.axial).dd(p)[0] in ("SD-proton", "SD-neutron")   # one interference band


def test_envelope_is_finite_inside_the_validated_ranges():
    grid, best, who = limits.table("SI")
    assert len(grid) == len(best) == len(who) == 500
    assert 1e-48 < limits.envelope("SI", 100.0) < 1e-45
    assert limits.setter("SI", 100.0)
    assert limits.setter("SD-proton", 1e4) == "XENONnT SR0+SR1"       # validated to 10 TeV (R2 follow-up)


def test_fermi_ratio_is_none_off_the_record_and_halved_for_dirac():
    record = {"bb": {"limit_cm3_s": [[10.0, 1e-26], [1000.0, 1e-25]]}}
    assert fermi_ratio({"b": 2e-26}, 10.0, record) == pytest.approx(1.0)
    assert fermi_ratio({"b": 2e-26}, 1e5, record) is None
    assert fermi_ratio({"Z'Z'": 0.0, "gg": 1e-20}, 10.0, record) is None     # unsupported prompt channel needs a spectral calculation


@pytest.mark.needs("diamx", "solar_model")
def test_evaluate_excludes_v1_by_direct_detection(awaiting):
    awaiting("planck-2018-pann")                                        # the CMB's record held unverified
    r = evaluate(V1, Point(m_chi=100.0, m_med=1000.0))
    assert r.dd_kind == "SI" and r.excluded["direct detection"] is True
    assert set(r.excluded) == {"direct detection", "gamma rays (Fermi-LAT dwarfs)", "capture in the Sun (IceCube)",
                               "colliders (CMS)", "perturbativity", "CMB (Planck)", "LHC searches (SModelS)",
                               "antiprotons (AMS-02)", "LHC dijet resonances (CMS, ATLAS)"}
    assert r.excluded["perturbativity"] is False
    assert r.excluded["CMB (Planck)"] is None and any("CMB" in x for x in r.pending)     # its record awaits verification


def _result(omegas: list[list[float | None]]) -> ScanResult:
    """A hand-made 2D scan with given Ωh² (rows: y), every constraint allowing."""
    x, y = Axis(parameter="m_med", low=100, high=1000, n=len(omegas[0])), Axis(parameter="m_chi", low=10, high=100,
                                                                              n=len(omegas))
    request = ScanRequest(model_class=V1, fixed=Point(m_chi=50, m_med=500), x=x, y=y, workers=1)
    xs, ys = x.values(), y.values()
    points = [PointResult(point=Point(m_chi=ys[j], m_med=xs[i]), omega_h2=omegas[j][i], dd_kind="SI",
                          dd_sigma_cm2=0.0, dd_limit_cm2=1.0, excluded={"direct detection": False})
              for j in range(len(ys)) for i in range(len(xs))]
    return ScanResult(request=request, xs=xs, ys=ys, points=points)


def test_crossings_solve_the_actual_relic_equation(monkeypatch):
    monkeypatch.setattr(Spin1Class, "omega_h2", lambda self, p: 0.012 * (p.m_med / 100) ** 2)
    found = _crossings(_result([[0.012, 1.2], [0.012, 1.2]]), 0.12)
    assert len(found) == 2
    assert all(f.m_med == pytest.approx(math.sqrt(100 * 1000)) for f in found)    # halfway in ln Ωh² and ln m


@pytest.mark.needs("eos")
def test_verdict_without_a_crossing():
    assert verdict(_result([[1.0, 2.0], [3.0, 4.0]])).level == "overabundant"
    assert verdict(_result([[0.01, None], [0.02, 0.03]])).level == "pending"


@pytest.mark.needs("diamx", "solar_model")
def test_judge_point_names_what_excludes_and_what_is_pending():
    c = judge_point(V1, Point(m_chi=100.0, m_med=1000.0))
    assert c.status == "excluded" and "direct detection" in c.excluded_by
    s = judge_point(ScalarClass(dm_pseudoscalar=True, sm_pseudoscalar=True), Point(m_chi=300.0, m_med=1000.0, g_q=1))
    assert any(r.startswith("LHC searches (SModelS)") for r in s.pending)     # its record awaits verification
    assert any("not compared" in r for r in s.pending)


@pytest.mark.needs("diamx", "cdmslite", "solar_model")
def test_plane_plot_is_written(tmp_path):
    result = _result([[0.012, 1.2], [0.012, 1.2]])
    out = plots.plane(result, verdict(result), tmp_path / "plane.png", title="t")
    assert out.exists() and out.stat().st_size > 1000


def test_classify_the_dm13_models():
    cls, p, _ = classify(spec("vector_mediator"))
    assert isinstance(cls, Spin1Class) and cls.kind is spin1.Spin1Kind.vector and p.g_q == 0.25
    cls, _, _ = classify(spec("axial_mediator"))
    assert cls.kind is spin1.Spin1Kind.axial
    cls, p, _ = classify(spec("scalar_mediator"))
    assert isinstance(cls, ScalarClass) and not cls.dm_pseudoscalar and p.g_q == 1.0


def test_classify_rejects_majorana_dark_matter_with_a_reason():
    s = spec("vector_mediator")
    fields = [f.model_copy(update={"self_conjugate": True}) if f.name == s.dark_matter.name else f for f in s.fields]
    with pytest.raises(Unsupported, match="Majorana"):
        classify(s.model_copy(update={"fields": fields}), generic_route=False)


def test_classify_rejects_a_flavour_universal_scalar_coupling():
    s = spec("scalar_mediator")
    terms = [t.model_copy(update={"coupling": "g_q"}) if "m_q" in t.coupling else t for t in s.terms]
    with pytest.raises(Unsupported, match="in proportion to their masses"):
        classify(s.model_copy(update={"terms": terms}), generic_route=False)
