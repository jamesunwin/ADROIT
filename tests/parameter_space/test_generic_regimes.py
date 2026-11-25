"""The regimes of the generic route's O(1) disagreements with the literature (D35; the external audit of 2026-10-16,
item 17): each trigger on synthetic models, written here (no held-out entry is built or computed), and the rule that a
decisive verdict inside a regime must survive the relic target's rescaling."""

from __future__ import annotations

import math

import pytest

from adroit.core.model_spec import ModelSpec
from adroit.parameter_space.portals import generic_regimes as gr
from adroit.parameter_space.portals.generic import GenericModel


def _dark_photon(m: float = 1.0, m_v: float = 0.0, alpha: float = 0.1) -> GenericModel:
    """A Dirac fermion X charged under a dark U(1) with vector Ad (massless: dark QED; heavier than X: forbidden)."""
    spec = ModelSpec.model_validate({"name": "dark_u1", "phase": "broken", "fields": [
        {"name": "X", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": m,
         "charges": {"extra": {"Ad": 1.0}}},
        {"name": "Ad", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": m_v}],
        "couplings": [{"name": "e_d", "value": math.sqrt(4 * math.pi * alpha)}],
        "terms": [{"fields": [{"field": "X", "conjugate": True}, {"field": "X"}, {"field": "Ad"}],
                   "lorentz": "vector", "coupling": "e_d"}]})
    return GenericModel.of(spec, sommerfeld=True, bound_states=True)


def _majorana_zprime(m_chi: float, m_zp: float = 300.0) -> GenericModel:
    """Majorana χ with an axial Z′ that couples to u_R."""
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
               "mass_gev": m_chi},
              {"name": "Zp", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": m_zp},
              {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R",
               "charges": {"su3": "3", "hypercharge": 2 / 3}}]
    terms = [{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Zp"}],
              "lorentz": "axial", "coupling": "g"},
             {"fields": [{"field": "uR", "conjugate": True}, {"field": "uR"}, {"field": "Zp"}], "lorentz": "vector",
              "coupling": "g"}]
    spec = ModelSpec.model_validate({"name": "majorana_zp", "phase": "unbroken", "fields": fields, "terms": terms,
                                     "couplings": [{"name": "g", "value": 0.2}]})
    return GenericModel.of(spec, sommerfeld=False)


def test_majorana_dark_matter_near_a_vector_pole_is_in_okadas_regime() -> None:
    near = _majorana_zprime(142.5)                      # 2 m_χ 5% below the Z′, as Okada et al.'s benchmarks
    (found,) = gr.regimes(near, near.point())
    assert "Okada et al." in found and "-5.0%" in found
    assert any(f.startswith(gr.QUALIFICATION) for f in near.flags(near.point()))
    far = _majorana_zprime(100.0)                       # 33% below: outside
    assert gr.majorana_pole(far, far.point()) == ""


def test_dark_qed_is_in_von_harlings_regime() -> None:
    """α = 0.03 at 1 TeV: the long-range effects lower Ωh² by 42%, the bound states about 6 points of it."""
    engine = _dark_photon(m=1000.0, alpha=0.03)
    found = gr.regimes(engine, engine.point())
    assert len(found) == 1 and "von Harling & Petraki" in found[0]
    share = float(found[0].split("lower Ωh² by ")[1].split("%")[0]) / 100
    p = engine.point()
    assert share == pytest.approx(1 - engine.omega_h2(p) / engine.model_copy(update={"sommerfeld": False}).omega_h2(p),
                                  abs=0.006)
    assert gr.MATERIAL <= share < 1
    off = engine.model_copy(update={"bound_states": False})      # a request without them is not this regime
    assert gr.bound_states(off, off.point()) == ""
    weak = _dark_photon(m=1000.0, alpha=0.003)                     # a weak force: a negligible effect
    assert gr.bound_states(weak, weak.point()) == ""


def test_forbidden_annihilation_beyond_the_agreed_splitting() -> None:
    """X X̄ → Ad Ad with Ad heavier than X: a splitting of 0.5 is beyond the 0.309 at which the route agreed with
    D'Agnolo et al.; 0.2 is inside it."""
    beyond = _dark_photon(m=1.0, m_v=1.5)
    found = gr.regimes(beyond, beyond.point())
    assert any("D'Agnolo et al." in f and "Δ = 0.5" in f for f in found)
    inside = _dark_photon(m=1.0, m_v=1.2)
    assert not any("D'Agnolo" in f for f in gr.regimes(inside, inside.point()))


def test_a_model_outside_every_regime_is_unchanged() -> None:
    """A positive control: a Dirac dark matter with a heavy vector mediator that it annihilates through."""
    engine = _dark_photon(m=100.0, m_v=30.0, alpha=0.01)
    assert gr.regimes(engine, engine.point()) == []
    assert not any(f.startswith(gr.QUALIFICATION) for f in engine.flags(engine.point()))


def _grid(n: int = 15, low: float = 40.0, high: float = 320.0, density=lambda m: m / 1000.0,
          excluded=lambda m: True, pending=lambda m: False, missing=()):
    """A scan of a synthetic generic model on (m_χ, m_med) with analytic Ωh² = ``density(m_χ)`` and synthetic
    constraint statuses; the actual bracketing, root refinement, classification and D35 rule run (the external
    audit's R17-2 control, 2026-10-17). Returns (result, patches)."""
    from adroit.parameter_space import searches
    from adroit.parameter_space import verdict as v
    from adroit.parameter_space.scan import Axis, PointResult, ScanRequest, ScanResult, _point_at
    engine = _majorana_zprime(142.5)
    request = ScanRequest(model_class=engine, fixed=engine.point(),
                          x=Axis(parameter="m_chi", low=low, high=high, n=n, log=False),
                          y=Axis(parameter="m_med", low=150.0, high=160.0, n=2, log=False))
    rows = []
    for y in request.y.values():
        for x in request.x.values():
            q = _point_at(request, x, y)
            rows.append(PointResult(point=q, omega_h2=None if x in missing else density(x), dd_kind="SI",
                                    dd_sigma_cm2=0.0, dd_limit_cm2=1.0,
                                    excluded={"synthetic constraint": True} if excluded(x) else {},
                                    pending=["a synthetic pending constraint"] if pending(x) else []))
    result = ScanResult(request=request, xs=request.x.values(), ys=request.y.values(), points=rows)

    def judge(cls, q, *args, **kwargs):
        out = excluded(q.m_chi)
        return v.Crossing(point=q, status="excluded" if out else "pending" if pending(q.m_chi) else "viable",
                          omega_h2=density(q.m_chi), excluded_by=["synthetic constraint"] if out else [],
                          evaluation=PointResult(point=q, omega_h2=density(q.m_chi), dd_kind='SI', dd_sigma_cm2=0.0, dd_limit_cm2=1.0, excluded={}))       # a judgement saves its comparisons
    patches = [(GenericModel, "omega_h2", lambda self, q: density(q.m_chi)), (GenericModel, "domain", lambda self, q: ""),
               (GenericModel, "pending", lambda self, q: []), (searches, "prefetch_lhc", lambda cls, ps, *a: [None] * len(ps)),
               (v, "judge_point", judge), (gr, "regimes", lambda model, q: ["a synthetic regime"])]
    return result, patches


def _judged(monkeypatch, **grid):
    from adroit.parameter_space import verdict as v
    result, patches = _grid(**grid)
    for target, name, value in patches:
        monkeypatch.setattr(target, name, value)
    return v.verdict(result)


@pytest.mark.needs("eos")
def test_an_allowed_point_inside_the_interval_defeats_an_exclusion(monkeypatch) -> None:
    """R17-2's control: Ωh² = m_χ/1000, allowed only for 170 < m_χ < 190 GeV. The roots at Ωh² = 0.048, 0.12 and 0.3
    are excluded; the grid's 180 GeV point (Ωh² = 0.18, inside the interval) is allowed, so the exclusion is not
    established across the disagreement. Before the fix the two ends' agreement certified it."""
    found = _judged(monkeypatch, excluded=lambda m: not 170.0 < m < 190.0)
    assert found.level == "pending" and gr.QUALIFICATION in found.summary
    assert "excluded at the nominal target; not established across the O(1) disagreement (Ωh² = 0.048–0.3)" in found.summary
    assert "viable at m_chi = 180" in found.summary and found.unresolved


@pytest.mark.needs("eos")
def test_a_pending_point_inside_the_interval_defeats_an_exclusion(monkeypatch) -> None:
    found = _judged(monkeypatch, excluded=lambda m: m != 180.0, pending=lambda m: m == 180.0)
    assert found.level == "pending" and "pending at m_chi = 180" in found.summary


@pytest.mark.parametrize("grid, gap", [
    (dict(high=200.0, n=9), "does not span the interval"),                  # Ωh² ≤ 0.2 < 0.3
    (dict(n=2), "no grid point lies inside the band"),                     # 0.04 and 0.32 only
    (dict(missing=(180.0,)), "grid points have no relic calculation")])
def test_an_incompletely_covered_interval_does_not_decide(monkeypatch, grid, gap) -> None:
    """The rule itself, given a decisive nominal level (a missing Ωh² already leaves the nominal verdict pending)."""
    from adroit.parameter_space import verdict as v
    result, patches = _grid(**grid)
    for target, name, value in patches:
        monkeypatch.setattr(target, name, value)
    for level in ("excluded", "viable"):
        found = v._robust(result, v.Verdict(level=level, summary="as computed", target=0.12), 80, None)
        assert found.level == "pending" and gap in found.summary
    assert v.verdict(result).level == "pending"


@pytest.mark.needs("eos")
def test_a_fully_covered_band_keeps_its_level_on_the_evaluated_grid(monkeypatch) -> None:
    allowed = _judged(monkeypatch, excluded=lambda m: False)
    assert allowed.level == "viable" and "viable on the evaluated grid across the disagreement (Ωh² = 0.048–0.3), " \
        "at the scan's resolution" in allowed.summary and "are all allowed" in allowed.summary
    excluded = _judged(monkeypatch)
    assert excluded.level == "excluded" and "are all excluded" in excluded.summary


@pytest.mark.needs("eos")
def test_one_excluded_point_in_the_band_leaves_viability_pending(monkeypatch) -> None:
    """All allowed is stronger than needed and accepted (the owner, 2026-10-17)."""
    found = _judged(monkeypatch, excluded=lambda m: m == 260.0)
    assert found.level == "pending" and "viable at the nominal target; not established" in found.summary


@pytest.mark.needs("eos")
def test_overabundance_beyond_the_interval_stands(monkeypatch) -> None:
    over = _judged(monkeypatch, density=lambda m: 0.5 + m / 1000.0)
    assert over.level == "overabundant" and "every computed grid value is above Ωh² = 0.3" in over.summary
    moved = _judged(monkeypatch, density=lambda m: 0.13 + m / 1e5)          # 0.13–0.133: below 0.3
    assert moved.level == "pending" and "overabundant at the nominal target" in moved.summary


@pytest.mark.needs("eos")
def test_outside_every_regime_the_verdict_is_unchanged(monkeypatch) -> None:
    from adroit.parameter_space import verdict as v
    result, patches = _grid(excluded=lambda m: not 170.0 < m < 190.0)
    for target, name, value in patches:
        monkeypatch.setattr(target, name, value)
    monkeypatch.setattr(gr, "regimes", lambda model, q: [])
    found = v.verdict(result)
    assert found.level == "excluded" and gr.QUALIFICATION not in found.summary


def _band(engine, masses, status, density=lambda m: m / 1000.0):
    from adroit.orchestrator.single_idea import BandPoint
    return [BandPoint(m_chi=m, s_hat=1.0, events_at_unit=1.0, mu_hat=1.0, mu_68=(0.5, 1.5), z_local=2.0,
                      point=engine.point().model_copy(update={"m_chi": m}), omega_h2=density(m), status=status(m))
            for m in masses]


def _thermal_at(engine, status):
    def at(target):
        b = _band(engine, [1000.0 * target], status)[0]
        return [b.model_copy(update={"target": target, "relative_residual": 0.0, "converged": True})], []
    return at


@pytest.mark.parametrize("nominal, status, masses, expected, words", [
    ("excluded", lambda m: "viable" if m == 180.0 else "excluded", range(40, 330, 20), "undetermined",
     "viable at m_χ = 180"),
    ("excluded", lambda m: "pending" if m == 180.0 else "excluded", range(40, 330, 20), "undetermined",
     "pending at m_χ = 180"),
    ("excluded", lambda m: "excluded", range(40, 330, 20), "excluded", "are all excluded"),
    ("viable", lambda m: "viable", range(40, 330, 20), "viable", "are all allowed"),
    ("excluded", lambda m: "excluded", range(40, 210, 20), "undetermined", "does not span the interval")])
def test_explain_a_signal_applies_the_same_rule(monkeypatch, nominal, status, masses, expected, words) -> None:
    from adroit.orchestrator import single_idea
    monkeypatch.setattr(gr, "regimes", lambda model, p: ["a regime"])
    engine = _majorana_zprime(142.5)
    band = _band(engine, [float(m) for m in masses], status)
    thermal = _thermal_at(engine, status)(0.12)[0]
    level, text = single_idea._across_disagreement(engine, engine.point(), band, thermal, (nominal, "as computed"),
                                                   0.12, _thermal_at(engine, status))
    assert level == expected and gr.QUALIFICATION in text and words in text


def test_no_thermal_intersection_stands_only_beyond_the_interval(monkeypatch) -> None:
    from adroit.orchestrator import single_idea
    monkeypatch.setattr(gr, "regimes", lambda model, p: ["a regime"])
    engine = _majorana_zprime(142.5)
    above = _band(engine, [100.0, 200.0], lambda m: "excluded", density=lambda m: 1.0 + m / 1000.0)
    level, text = single_idea._across_disagreement(engine, engine.point(), above, [], ("no_thermal", "as computed"),
                                                   0.12, lambda t: ([], []))
    assert level == "no_thermal" and "above the interval" in text
    near = _band(engine, [100.0, 200.0], lambda m: "excluded", density=lambda m: 0.13 + m / 1e5)
    level, _ = single_idea._across_disagreement(engine, engine.point(), near, [], ("no_thermal", "as computed"),
                                                0.12, lambda t: ([], []))
    assert level == "undetermined"


# The re-audit of 2026-10-18 (R18-1, R18-2, R18-4): a fit hole or an unresolved nominal root inside the band, and a
# regime reached only by a shifted thermal solution.

def _fit(q0: float | None, resolved: bool = True, identifiable: bool = True, at_boundary: bool = False):
    from adroit.core.model_spec import PhysicalFitRange
    from adroit.parameter_space.physical_fit import FitSettings, PhysicalFit
    return PhysicalFit(bounds=PhysicalFitRange(low=0.0, high=3.54), settings=FitSettings(), q0=q0,
                       resolved=resolved, identifiable=identifiable, at_boundary=at_boundary)


HOLES = {"below": dict(z_local=0.0), "below_physical": dict(physical_fit=_fit(0.25)),
         "unresolved": dict(physical_fit=_fit(None, resolved=False)),
         "unidentifiable": dict(physical_fit=_fit(9.0, identifiable=False)),
         "edge": dict(physical_fit=_fit(9.13, at_boundary=True))}
WORDS = {"below": "below the declared anomaly-fit threshold", "below_physical": "below the declared anomaly-fit threshold",
         "unresolved": "an unresolved physical fit", "unidentifiable": "an unidentifiable physical fit",
         "edge": "a physical fit at its range's edge"}


def _holed(engine, status, hole, at=180.0):
    """The band and thermal search of ``_band``/``_thermal_at`` with the fit at ``at`` GeV (Ωh² = at/1000) replaced."""
    band = [b.model_copy(update=HOLES[hole]) if b.m_chi == at else b
            for b in _band(engine, [float(m) for m in range(40, 330, 20)], status)]
    plain = _thermal_at(engine, status)

    def thermal_at(target):
        rows, pending = plain(target)
        return [b.model_copy(update=HOLES[hole]) if abs(b.m_chi - at) < 1e-9 else b for b in rows], pending
    return band, thermal_at


def _across(monkeypatch, nominal, band, thermal, thermal_at, unresolved=()):
    from adroit.orchestrator import single_idea
    monkeypatch.setattr(gr, "regimes", lambda model, p: ["a regime"])
    engine = _majorana_zprime(142.5)
    return single_idea._across_disagreement(engine, engine.point(), band, thermal, (nominal, "as computed"), 0.12,
                                            thermal_at, unresolved)


def test_the_auditors_fit_hole_leaves_viability_undetermined(monkeypatch) -> None:
    """R18-1's control: Ωh² = m_χ/1000, every point allowed, the fit 0 at 180 GeV, so the interior target 0.18 has no
    explanation (``_level`` gives no_thermal there). Before the fix the hole was filtered out and viability certified
    across 0.048–0.3."""
    from adroit.orchestrator import single_idea
    engine = _majorana_zprime(142.5)
    band, thermal_at = _holed(engine, lambda m: "viable", "below")
    assert single_idea._level(band, thermal_at(0.18)[0], True, [])[0] == "no_thermal"
    level, text = _across(monkeypatch, "viable", band, thermal_at(0.12)[0], thermal_at)
    assert level == "undetermined"
    assert "viable at the relic target; not established across the O(1) disagreement (Ωh² = 0.048–0.3)" in text
    assert "below the declared anomaly-fit threshold at m_χ = 180 GeV" in text


@pytest.mark.parametrize("hole", list(HOLES))
def test_every_kind_of_fit_hole_inside_the_band_blocks_viability(monkeypatch, hole) -> None:
    engine = _majorana_zprime(142.5)
    band, thermal_at = _holed(engine, lambda m: "viable", hole)
    level, text = _across(monkeypatch, "viable", band, thermal_at(0.12)[0], thermal_at)
    assert level == "undetermined" and f"{WORDS[hole]} at m_χ = 180 GeV" in text


@pytest.mark.parametrize("hole, expected", [("below", "excluded"), ("below_physical", "excluded"),
                                            ("unresolved", "undetermined"), ("unidentifiable", "undetermined"),
                                            ("edge", "undetermined")])
def test_an_exclusion_skips_a_fit_below_the_threshold_but_not_an_undecided_one(monkeypatch, hole, expected) -> None:
    """A resolved, identifiable fit inside its range whose √q0 is below 1 is no explanation of the anomaly (it improves
    on the background too little), so it cannot defeat an exclusion; it is listed apart. An undecided fit might be an
    explanation and blocks (the owner, 2026-10-18)."""
    engine = _majorana_zprime(142.5)
    band, thermal_at = _holed(engine, lambda m: "viable" if m == 180.0 else "excluded", hole)
    level, text = _across(monkeypatch, "excluded", band, thermal_at(0.12)[0], thermal_at)
    assert level == expected
    if expected == "excluded":
        assert "are all excluded" in text and "1 below the declared anomaly-fit threshold, not explanations" in text
        assert "m_χ = 180 GeV" in text
    else:
        assert f"{WORDS[hole]} at m_χ = 180 GeV" in text


@pytest.mark.parametrize("nominal, status, hole, expected", [
    ("viable", "viable", "below", "undetermined"), ("viable", "viable", "edge", "undetermined"),
    ("excluded", "excluded", "edge", "undetermined"), ("excluded", "excluded", "below", "excluded")])
def test_a_refined_root_is_judged_by_its_fit_before_it_is_filtered(monkeypatch, nominal, status, hole, expected) -> None:
    """One good root and one poor or range-edge root at the same target: the second may not disappear while the
    first survives (the owner's clarification of R18-1)."""
    engine = _majorana_zprime(142.5)
    band = _band(engine, [float(m) for m in range(40, 330, 20)], lambda m: status)
    plain = _thermal_at(engine, lambda m: status)

    def thermal_at(target):
        rows, pending = plain(target)
        return rows + [rows[0].model_copy(update={"m_chi": rows[0].m_chi + 7.0, **HOLES[hole]})], pending
    level, text = _across(monkeypatch, nominal, band, thermal_at(0.12)[0], thermal_at)
    assert level == expected
    if expected == "undetermined":
        assert WORDS[hole] in text


def test_a_fully_good_allowed_band_still_certifies(monkeypatch) -> None:
    engine = _majorana_zprime(142.5)
    band = _band(engine, [float(m) for m in range(40, 330, 20)], lambda m: "viable")
    thermal_at = _thermal_at(engine, lambda m: "viable")
    level, text = _across(monkeypatch, "viable", band, thermal_at(0.12)[0], thermal_at)
    assert level == "viable" and "are all allowed" in text and "below the declared" not in text


def test_an_unresolved_nominal_bracket_blocks_the_band_in_explain_a_signal(monkeypatch) -> None:
    """R18-2 in the single-idea path: a viable nominal root plus a failed bracket at the nominal target."""
    engine = _majorana_zprime(142.5)
    band = _band(engine, [float(m) for m in range(40, 330, 20)], lambda m: "viable")
    thermal_at = _thermal_at(engine, lambda m: "viable")
    level, text = _across(monkeypatch, "viable", band, thermal_at(0.12)[0], thermal_at,
                          ["300–320 GeV thermal bracket: did not converge"])
    assert level == "undetermined" and "at the relic target: 300–320 GeV thermal bracket" in text
    assert _across(monkeypatch, "viable", band, thermal_at(0.12)[0], thermal_at, [])[0] == "viable"


@pytest.mark.needs("eos")
def test_a_failed_nominal_refinement_blocks_the_band_on_the_plane(monkeypatch) -> None:
    """R18-2's control: one nominal refinement fails, another root survives, every point is allowed; the nominal
    level may stay viable, but the band-wide certificate may not be given."""
    from adroit.parameter_space import verdict as v
    result, patches = _grid(excluded=lambda m: False)
    for target, name, value in patches:
        monkeypatch.setattr(target, name, value)
    original = v._thermal_roots

    def roots(result, target, maximum, *args, **kwargs):
        found, omitted = original(result, target, maximum, *args, **kwargs)
        if abs(target - 0.12) < 1e-10:
            found[0] = found[0].model_copy(update={"converged": False, "reason": "a controlled failure"})
        return found, omitted
    monkeypatch.setattr(v, "_thermal_roots", roots)
    found = v.verdict(result)
    assert found.level == "pending" and "viable at the nominal target; not established" in found.summary
    assert "at the nominal target: a controlled failure" in found.summary


@pytest.mark.needs("eos")
def test_a_budget_omitted_nominal_bracket_blocks_the_band_on_the_plane(monkeypatch) -> None:
    """The root budget truncated at the nominal target only (the ends' searches complete)."""
    from adroit.parameter_space import verdict as v
    result, patches = _grid(excluded=lambda m: False)
    for target, name, value in patches:
        monkeypatch.setattr(target, name, value)
    original = v._thermal_roots

    def roots(result, target, maximum, *args, **kwargs):
        found, omitted = original(result, target, maximum, *args, **kwargs)
        return (found[:1], omitted + len(found) - 1) if abs(target - 0.12) < 1e-10 else (found, omitted)
    monkeypatch.setattr(v, "_thermal_roots", roots)
    found = v.verdict(result)
    assert found.level == "pending" and "at the nominal target: 1 candidate brackets/endpoints not refined" in found.summary
    monkeypatch.setattr(v, "_thermal_roots", original)
    assert v.verdict(result).level == "viable"


@pytest.mark.needs("eos")
def test_a_regime_reached_only_by_a_shifted_solution_qualifies_the_plane(monkeypatch) -> None:
    """R18-4's control with the unchanged Majorana-pole predicate (Z′ at 300 GeV): the nominal roots at 120 GeV are
    outside it and excluded; the grid's 140 GeV point (Ωh² = 0.14, inside the interval; 6.7% below the pole) is in it
    and allowed. Before the fix the verdict was a plain exclusion."""
    from adroit.parameter_space import verdict as v
    result, patches = _grid(excluded=lambda m: not 130.0 < m < 150.0)
    for target, name, value in patches:
        monkeypatch.setattr(target, name, value)
    monkeypatch.setattr(gr, "regimes", lambda model, p: [s] if (s := gr.majorana_pole(model, p)) else [])
    found = v.verdict(result)
    assert found.level == "pending" and "Okada et al." in found.summary and gr.QUALIFICATION in found.summary
    assert "viable at m_chi = 140" in found.summary


def test_a_regime_reached_only_by_a_shifted_solution_qualifies_explain_a_signal(monkeypatch) -> None:
    from adroit.orchestrator import single_idea
    monkeypatch.setattr(gr, "regimes", lambda model, p: [s] if (s := gr.majorana_pole(model, p)) else [])
    engine = _majorana_zprime(142.5)
    status = lambda m: "viable" if 130.0 < m < 150.0 else "excluded"    # noqa: E731
    band = _band(engine, [float(m) for m in range(40, 330, 20)], status)
    thermal_at = _thermal_at(engine, status)
    level, text = single_idea._across_disagreement(engine, engine.point(), band, thermal_at(0.12)[0],
                                                   ("excluded", "as computed"), 0.12, thermal_at)
    assert level == "undetermined" and "Okada et al." in text and "viable at m_χ = 140" in text


def test_an_edge_spanning_the_band_brings_in_both_ends(monkeypatch) -> None:
    """Neither end's Ωh² lies inside [0.048, 0.3], but the edge between them spans it, so a shifted target's solution
    lies between them: both are checked (the owner's clarification of R18-4), on the grid and on the band."""
    from adroit.orchestrator import single_idea
    from adroit.parameter_space import verdict as v
    step = lambda m: 0.01 if m < 150.0 else 1.0                          # noqa: E731
    result, patches = _grid(density=step)
    reached = sorted({q.m_chi for q in v._reaching(result, 0.048, 0.3)})
    assert reached == [140.0, 160.0]
    engine = _majorana_zprime(142.5)
    band = _band(engine, [float(m) for m in range(40, 330, 20)], lambda m: "excluded", density=step)
    assert [b.m_chi for b in single_idea._reaching(band, 0.048, 0.3)] == [140.0, 160.0]
    for target, name, value in patches:
        monkeypatch.setattr(target, name, value)
    monkeypatch.setattr(gr, "regimes", lambda model, q: ["a regime at 160 GeV"] if q.m_chi == 160.0 else [])
    far = v.Crossing(point=result.points[3].point, status="excluded", omega_h2=0.12)    # 100 GeV: no regime there
    nominal = v.Verdict(level="excluded", summary="as computed", target=0.12, crossings=[far])
    assert v._regimes(result, nominal) == ["a regime at 160 GeV"]


@pytest.mark.needs("eos")
def test_without_a_reachable_regime_the_verdict_stays_unqualified(monkeypatch) -> None:
    from adroit.parameter_space import verdict as v
    result, patches = _grid(n=29, high=600.0, excluded=lambda m: not 130.0 < m < 150.0)    # 20 GeV steps
    for target, name, value in patches:
        monkeypatch.setattr(target, name, value)
    monkeypatch.setattr(gr, "regimes", lambda model, q: ["far away"] if q.m_chi >= 400.0 else [])
    found = v.verdict(result)                      # the band reaches 320 GeV (the edge 300–320 overlaps 0.3)
    assert found.level == "excluded" and gr.QUALIFICATION not in found.summary


def _discovered(monkeypatch, span, **grid):
    """S18-03 (the stacked audit of 2026-10-18): an unresolved discovery requirement is a pointwise input to the
    verdict, applied to every evaluation (grid rows, nominal roots, shifted-target endpoint roots) before the O(1)
    certificate. The audit's control: Ωh² = m_χ/1000, everything allowed, a requirement at ``span``."""
    from adroit.parameter_space import verdict as v
    from adroit.parameter_space.scan import DiscoveryPending
    result, patches = _grid(**grid)
    for target, name, value in patches:
        monkeypatch.setattr(target, name, value)
    pending = DiscoveryPending(text='discovery: an unreviewed search (synthetic): not reviewed', m_chi=span)
    result = result.model_copy(update={'request': result.request.model_copy(update={'discovery': [pending]})})
    return v.verdict(result)


@pytest.mark.needs("eos")
def test_a_requirement_inside_the_interval_defeats_the_band_wide_certificate(monkeypatch) -> None:
    """Nominal roots at 120 GeV are untouched; the requirement covers the evaluated 180 GeV grid point inside the
    Ωh² = 0.048–0.3 interval, so the band-wide "viable" is refused (it was certified before the repair)."""
    out = _discovered(monkeypatch, (170.0, 190.0), excluded=lambda m: False)
    assert out.level == 'pending' and 'not established across the O(1) disagreement' in out.summary
    assert all(c.status == 'viable' for c in out.crossings if c.point.m_chi == 120.0)


def test_a_requirement_at_a_shifted_endpoint_or_the_nominal_roots_is_seen(monkeypatch) -> None:
    assert _discovered(monkeypatch, (295.0, 305.0), excluded=lambda m: False).level == 'pending'
    nominal = _discovered(monkeypatch, (115.0, 125.0), excluded=lambda m: False)
    assert nominal.level in ('pending', 'viable_pending')
    assert all(c.status == 'pending' and any(p.startswith('discovery:') for p in c.pending)
               for c in nominal.crossings if c.point.m_chi == 120.0)


@pytest.mark.needs("eos")
def test_a_requirement_outside_the_scan_or_on_an_excluded_point_changes_nothing(monkeypatch) -> None:
    assert _discovered(monkeypatch, (500.0, 600.0), excluded=lambda m: False).level == 'viable'
    assert _discovered(monkeypatch, None, excluded=lambda m: True).level == 'excluded'


def test_an_unset_discovery_keeps_the_scan_requests_identity() -> None:
    result, _ = _grid()
    assert 'discovery' not in result.request.model_dump(mode='json')


def test_a_verdict_formed_without_the_requirements_cannot_stay_viable_when_qualified(monkeypatch) -> None:
    """S18-03, the audit's control as it was written: qualifying afterwards a verdict that was formed without the
    requirements (``verdict`` on a scan without them, then ``qualify``) withdraws its "viable"; a verdict formed with
    them is only annotated."""
    from adroit.core.constraint_discovery import DiscoveryCoverage, Requirement
    from adroit.orchestrator.constraint_discovery import pending_spans, qualify
    from adroit.parameter_space import verdict as v
    coverage = DiscoveryCoverage(session_id='s' * 32, assessment_sha256='a' * 64, model_sha256='b' * 64,
                                 model_reference='synthetic', searched_at='2026-10-18', requirements=[
                                     Requirement(candidate_id='gap', name='an unreviewed 170-190 GeV search',
                                                 reference='synthetic', constraint_class='collider',
                                                 reason='not reviewed', domain={'m_chi': (170.0, 190.0)})])
    result, patches = _grid(excluded=lambda m: False)
    for target, name, value in patches:
        monkeypatch.setattr(target, name, value)
    assert qualify(v.verdict(result), coverage, []).level == 'pending'
    applied = result.model_copy(update={'request': result.request.model_copy(update={
        'discovery': pending_spans(coverage, [])})})
    formed = v.verdict(applied)
    assert formed.discovery_applied and qualify(formed, coverage, []).level == formed.level == 'pending'
