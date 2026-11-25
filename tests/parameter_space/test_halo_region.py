"""The halo region (the owner's specification of 2026-10-19): its samples, each module's limit at a halo, the
Galactic density scale, and a point's classification over the region."""
import math

import pytest

from adroit.parameter_space import halo_limits, halo_region
from adroit.parameter_space.classes import Point
from adroit.parameter_space.halo_region import HaloEvaluation, HaloOutcome, HaloPointSample, HaloPreset
from adroit.parameter_space.scan import PointResult, ScanRequest

XENON = "XENONnT SR0+SR1"


def test_the_region_is_the_joint_95_percent_ball_and_its_samples_cover_it():
    preset = HaloPreset()
    r = halo_region.radius(0.95)
    assert r == pytest.approx(2.7955, abs=1e-4)
    found = halo_region.samples(preset)
    assert [s.where for s in found].count("centre") == 1 and [s.where for s in found].count("boundary") == 8
    assert [s.where for s in found].count("interior") == preset.interior
    centre = found[0]
    assert (centre.v0_km_s, centre.v_esc_km_s) == (233.0, 528.0)
    assert centre.rho_low_gev_cm3 == pytest.approx(0.40 * math.exp(-0.35 * r))          # ≈ 0.150
    assert centre.rho_high_gev_cm3 == pytest.approx(0.40 * math.exp(0.35 * r))          # ≈ 1.064
    for s in found[1:9]:                                     # on the boundary the density interval closes
        assert s.rho_low_gev_cm3 == pytest.approx(0.40) and s.rho_high_gev_cm3 == pytest.approx(0.40)
        d = math.hypot((s.v0_km_s - 233) / 20, (s.v_esc_km_s - 528) / 30)
        assert d == pytest.approx(r)
    for s in found[9:]:
        assert math.hypot((s.v0_km_s - 233) / 20, (s.v_esc_km_s - 528) / 30) < r
    more = halo_region.doubled(preset)
    assert len(more) == preset.interior and not {(s.v0_km_s, s.v_esc_km_s) for s in more} & \
        {(s.v0_km_s, s.v_esc_km_s) for s in found}


def test_the_local_circular_speed_moves_with_v0():
    halo = halo_limits.velocity_halo(213.0, 500.0, 0.3)
    assert halo.v_lsr_km_s == (0.0, 213.0, 0.0) and halo.rho_gev_cm3 == 0.3
    assert halo_limits.velocity_halo(238.0, 544.0, 0.3).v_lab_km_s == pytest.approx(
        halo_limits.velocity_halo(238.0, 544.0, 0.3).v_lab_km_s)


def test_the_region_is_labelled_from_each_halos_status():
    assert halo_region.over(["excluded"] * 3, [False] * 3) == halo_region.EXCLUDED
    assert halo_region.over(["viable"] * 3, [False] * 3) == halo_region.ALLOWED
    assert halo_region.over(["excluded", "viable"], [False, False]) == halo_region.SENSITIVE
    assert halo_region.over(["viable", "viable"], [False, True]) == halo_region.INCOMPLETE
    assert halo_region.over(["excluded", "excluded"], [False, True]) == halo_region.EXCLUDED   # decided anyway
    assert halo_region.over(["excluded", "viable", "viable"], [False, False, True]) == halo_region.SENSITIVE


def test_a_request_without_a_region_keeps_its_identity_and_the_setting_decides_the_default(monkeypatch):
    from adroit.parameter_space.classes import Spin1Class
    from adroit.parameter_space.scan import Axis
    request = ScanRequest(model_class=Spin1Class(), fixed=Point(m_chi=100, m_med=1000),
                          x=Axis(parameter="m_med", low=500, high=1000, n=2),
                          y=Axis(parameter="m_chi", low=50, high=100, n=2))
    assert "halo" not in request.model_dump(mode="json")
    assert "halo" in request.model_copy(update={"halo": HaloPreset()}).model_dump(mode="json")
    from types import SimpleNamespace
    monkeypatch.setattr(halo_region, "default", lambda: "preset")
    assert halo_region.resolved(SimpleNamespace(halo=None, model_copy=lambda update: SimpleNamespace(**update))
                                ).halo == HaloPreset()
    monkeypatch.setattr(halo_region, "default", lambda: "published")
    assert halo_region.of(halo_region.resolved(
        SimpleNamespace(halo=None, model_copy=lambda update: SimpleNamespace(**update))).halo) is None


def test_the_density_enters_analytically_and_galactic_limits_scale_as_its_square():
    state = halo_limits.State(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=0.8)
    with halo_limits.using(state):
        assert halo_limits.density_scale("calore-2202.03076-pbar") == pytest.approx((0.8 / 0.385) ** 2)
        assert halo_limits.density_scale("fermi-lat-1506.00013-lines") == pytest.approx(4.0)
        assert halo_limits.density_scale("a record that states no density") == 1.0
        assert halo_limits.capture_halo().rho_gev_cm3 == 0.8
    assert halo_limits.density_scale("calore-2202.03076-pbar") == 1.0 and halo_limits.capture_halo() is None


@pytest.mark.needs("diamx")
def test_the_count_ratio_at_the_reference_velocities_is_the_density_ratio():
    """At the module's own reference velocities (238, 544 km/s; v_LSR = v₀) only the density moves the limit."""
    state = halo_limits.State(v0_km_s=238.0, v_esc_km_s=544.0, rho_gev_cm3=0.6)
    assert halo_limits.scale(XENON, "SI", 100.0, state) == pytest.approx(0.3 / 0.6, rel=1e-9)
    slower = halo_limits.State(v0_km_s=180.0, v_esc_km_s=450.0, rho_gev_cm3=0.3)
    assert halo_limits.scale(XENON, "SI", 10.0, slower) > 1.5            # a light WIMP loses its fast tail


def test_an_unvalidated_slow_module_needs_a_full_calculation_and_a_spent_budget_leaves_it_out(monkeypatch):
    monkeypatch.setattr(halo_limits, "validated", lambda module, kind, mass, state=None: None)
    calls = []
    monkeypatch.setattr(halo_limits, "exact", lambda *a: calls.append(a) or 1e-46)
    state = halo_limits.State(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=0.4, budget=halo_limits.Budget(1))
    value, margin, how = halo_limits.module_limit(state, XENON, "SI", 100.0, False)
    assert value == pytest.approx(1e-46, rel=1e-6, abs=0) and margin == 0.0 and "own procedure" in how and len(calls) == 1
    value, _, how = halo_limits.module_limit(state, XENON, "SI", 200.0, False)
    assert value is None and "budget is spent" in how and len(calls) == 1
    assert state.budget.spent and state.spent


def test_a_validated_count_ratio_scales_the_reference_and_widens_the_margin(monkeypatch):
    from adroit.parameter_space import limits
    monkeypatch.setattr(halo_limits, "validated", lambda module, kind, mass, state=None: 0.05)
    monkeypatch.setattr(halo_limits, "scale", lambda module, kind, mass, state: 0.5)
    monkeypatch.setattr(halo_limits, "_reference", lambda state, module, kind, mass: (2e-46, ""))
    monkeypatch.setattr(limits, "reference_tolerance", lambda module, kind, mass: 0.01)
    state = halo_limits.State(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=0.6)
    value, margin, how = halo_limits.module_limit(state, XENON, "SI", 100.0, False)
    assert value == pytest.approx(1e-46, rel=1e-6, abs=0) and margin == pytest.approx(1.01 * 1.10 - 1) and how.startswith("count ratio")


# --- the classification over the region ----------------------------------------------------------------------------

def _sample(excluded: bool | None, rho: float = 0.4, unresolved=(), exact=True, ratio=None, where="interior"):
    return HaloPointSample(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=rho, where=where,
                           outcomes={"direct detection": HaloOutcome(excluded=excluded, ratio=ratio, exact=exact)},
                           unresolved=list(unresolved))


def _point(samples, excluded=None, pending=(), ratios=None, **evaluation) -> PointResult:
    return PointResult(point=Point(m_chi=100, m_med=1000), omega_h2=0.12, dd_kind="SI", dd_sigma_cm2=1e-47,
                       dd_limit_cm2=1e-46, excluded={"direct detection": False, **(excluded or {})},
                       pending=list(pending), ratios=ratios or {}, model_pending=[],
                       halo=HaloEvaluation(region="the test region", samples=samples, converged=True, **evaluation))


def test_a_point_excluded_at_every_halo_is_excluded_throughout():
    from adroit.parameter_space.verdict import classify
    c = classify(None, _point([_sample(True), _sample(True, rho=0.2)]))
    assert c.status == "excluded" and c.halo == halo_region.EXCLUDED and c.excluded_by == ["direct detection"]
    assert c.nominal_status == "viable"


def test_a_point_whose_classification_changes_is_pending_and_halo_sensitive_with_its_nominal():
    from adroit.parameter_space.verdict import classify
    c = classify(None, _point([_sample(True, rho=1.0), _sample(False, rho=0.15)]))
    assert c.status == "pending" and c.halo == halo_region.SENSITIVE and not c.excluded_by
    assert c.pending[0].startswith("halo: halo-sensitive") and "1 of 2 halos excluded" in c.pending[0]
    assert "nominal at its centre: viable" in c.pending[0]


def test_an_undecided_halo_leaves_the_coverage_incomplete_unless_another_constraint_excludes():
    from adroit.parameter_space.verdict import classify
    c = classify(None, _point([_sample(False), _sample(None, unresolved=["SI (XENONnT SR0+SR1)"])]))
    assert c.status == "pending" and c.halo == halo_region.INCOMPLETE and "XENONnT" in c.pending[0]
    collider = classify(None, _point([_sample(False), _sample(None, unresolved=["SI (XENONnT SR0+SR1)"])],
                                     excluded={"colliders (CMS)": True}))
    assert collider.status == "excluded" and collider.halo == halo_region.EXCLUDED
    assert collider.excluded_by == ["colliders (CMS)"]


def test_a_structure_without_halo_variation_leaves_the_coverage_incomplete():
    from adroit.parameter_space.verdict import classify
    c = classify(None, _point([_sample(False), _sample(False)], unsupported=["direct detection (O8): Path 1"]))
    assert c.status == "pending" and c.halo == halo_region.INCOMPLETE and "Path 1" in c.pending[0]


def test_allowed_throughout_needs_every_halo_allowed():
    from adroit.parameter_space.verdict import classify
    c = classify(None, _point([_sample(False), _sample(False, rho=1.0)]))
    assert c.status == "viable" and c.halo == halo_region.ALLOWED and any("allowed throughout" in f for f in c.flags)


def test_a_count_ratio_never_enters_the_combined_likelihood():
    """Two halo-dependent ratios of 0.8 combine above the 95% threshold only if both are exact (condition 6)."""
    from adroit.parameter_space.likelihood import LikelihoodSettings
    from adroit.parameter_space.verdict import classify
    lines = "γ-ray lines (Fermi-LAT, H.E.S.S.)"

    def sample(exact, saved=True):
        return HaloPointSample(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=0.4, where="centre", outcomes={
            "direct detection": HaloOutcome(excluded=False, ratio=0.8, exact=exact, **(
                {"confidence_level": 0.95, "sidedness": "one-sided"} if saved else {})),
            lines: HaloOutcome(excluded=False, ratio=0.8)})
    ratios = {"direct detection": 0.8, lines: 0.8}
    both = classify(None, _point([sample(True)], excluded={lines: False}, ratios=ratios), LikelihoodSettings())
    counted = classify(None, _point([sample(False)], excluded={lines: False}, ratios=ratios), LikelihoodSettings())
    assert both.status == "excluded" and counted.status == "viable"
    older = classify(None, _point([sample(True, saved=False)], excluded={lines: False}, ratios=ratios),
                     LikelihoodSettings())                  # saved without the construction there: a cut, and said
    assert older.status == "pending" and any("not saved" in x for x in older.pending)


def test_each_halo_combines_direct_detection_with_its_own_construction():
    """PX-04: the experiment deciding at a halo can change; its own construction enters the combination there (a
    two-sided 0.9 crosses the 95% threshold where the centre's one-sided construction would not), and the centre's
    count-ratio cut does not remove an exact limit's metadata at another halo."""
    from adroit.parameter_space.likelihood import LikelihoodSettings
    from adroit.parameter_space.verdict import classify
    def sample(sided):
        return HaloPointSample(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=0.4, where="interior", outcomes={
            "direct detection": HaloOutcome(excluded=False, ratio=0.9, exact=True, confidence_level=0.95,
                                            sidedness=sided)})
    def point(sided):                                       # the centre's direct-detection ratio was a cut
        r = _point([sample(sided)], ratios={"colliders (CMS)": 0.01})
        return r.model_copy(update={"ratio_confidence_levels": {"colliders (CMS)": 0.95},
                                    "ratio_sidedness": {"colliders (CMS)": "one-sided"}})
    assert classify(None, point("two-sided"), LikelihoodSettings()).status == "excluded"
    assert classify(None, point("one-sided"), LikelihoodSettings()).status == "viable"
