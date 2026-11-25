"""The owner's decision #3 (the equation of state's band) on the single-idea workflow's headline: the candidate audit's
C21-07 (2026-10-21). The fitted band's thermal points are judged again with Saikawa & Shirai's upper and lower tables,
as the plane's crossings are (``verdict._eos_band``); before, the headline read the nominal table alone."""
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from adroit.constraints import relic
from adroit.orchestrator import single_idea as si
from adroit.parameter_space import simplified
from adroit.parameter_space.scan import PointResult
from adroit.parameter_space.classes import Point, Spin1Class
from tests.parameter_space.test_eos_verdict import SHIFT


def _study(tmp_path, excluded_above: float, scale: float = 0.006, poor_fit_above: float = 1e9,
           masses: tuple[float, ...] = (10, 40), nominal=None, unresolved_tables_from: float = 1e9,
           poor_fit_at: float | None = None, z_of=None, physical: bool = False, q0_of=None):
    """The workflow with its fit and constraints replaced by a toy (the audit's controls): Ωh² = scale × m_χ (or
    ``nominal(m)``) × the table's shift, a fit at every mass (local Z = 2, or 0.5 above ``poor_fit_above`` GeV), and
    an exclusion above ``excluded_above`` GeV; with a table, the brackets from ``unresolved_tables_from`` GeV fail to
    refine; ``z_of(m)``, the local Z at each mass; ``physical``, the fit as a bounded physical fit (q0 = Z²) rather
    than the inverse. The thermal refinement, the tables and the headline are the workflow's own."""
    from adroit.core.model_spec import PhysicalFitRange
    from adroit.parameter_space.physical_fit import FitSettings, PhysicalFit
    def density(p: Point) -> float:
        return (nominal(p.m_chi) if nominal else scale * p.m_chi) * SHIFT[relic.current_eos()]

    def band_point(m: float) -> si.BandPoint:
        p = Point(m_chi=m, m_med=1000, g_chi=.5)
        z = z_of(m) if z_of else 0.5 if m > poor_fit_above or poor_fit_at and abs(m - poor_fit_at) < 1e-6 else 2
        fit = PhysicalFit(bounds=PhysicalFitRange(low=0, high=.5), settings=FitSettings(), point=p, resolved=True,
                          identifiable=True, at_boundary=False, q0=q0_of(m) if q0_of else z * z) if physical else None
        return si.BandPoint(m_chi=m, s_hat=4, events_at_unit=4, mu_hat=1, mu_68=(.8, 1.2), z_local=z,
                            physical_fit=fit, point=p, m_med=1000, omega_h2=density(p),
                            status="excluded" if m > excluded_above else "viable",
                            excluded_by=["toy"] if m > excluded_above else [], fitted_value=.5,
                            evaluation=PointResult(point=p, omega_h2=density(p), dd_kind="SI", dd_sigma_cm2=0,
                                                   dd_limit_cm2=1, excluded={"toy": m > excluded_above}))
    refine = si.refine

    def refine_or_fail(point_at, *args, **kwargs):
        if relic.current_eos() and point_at(0).m_chi >= unresolved_tables_from:
            return SimpleNamespace(converged=False, reason="unresolved refinement (injected)")
        return refine(point_at, *args, **kwargs)
    spec = simplified.model("vector", 20, 1000)
    if physical:
        spec = spec.model_copy(update={"physical_fit": PhysicalFitRange(low=0, high=.5)})
    request = si.SingleIdeaRequest(experiment="CDMS II Si (2013)", spec=spec,
                                   masses_gev=list(masses), null_modules=[], literature=False, workers=1)
    cls, point = Spin1Class(), Point(m_chi=20, m_med=1000)
    with ExitStack() as stack:
        for obj, name, value in [
                (Spin1Class, "omega_h2", lambda self, p: density(p)),
                (Spin1Class, "domain", lambda self, p: ""),
                (si, "_checked", lambda r: (r, None, object(), True)),
                (si.user_models, "candidates", lambda *a: []),
                (si, "_fitted", lambda r, *a: ([band_point(m) for m in masses], si.SingleIdeaResult(request=r))),
                (si, "classify", lambda s: (cls, point, "")), (si, "_native", lambda *a: None),
                (si, "_on_band", lambda cls, p, b, *a, **k: band_point(b.m_chi)),
                (si, "_fit_at", lambda module, cls, p, m, spin: band_point(m)),
                (si, "_plane", lambda *a: (None, [])), (si, "refine", refine_or_fail)]:
            stack.enter_context(patch.object(obj, name, value))
        return si._study(request, tmp_path)


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_fitted_thermal_point_the_tables_judge_differently_is_pending(tmp_path):
    """Nominal root at 20 GeV, viable; with the upper table at 20.83 GeV, above the exclusion at 20.5 GeV: excluded.
    The plane gives this crossing pending, EOS-sensitive; so does the single-idea headline now."""
    result = _study(tmp_path, excluded_above=20.5)
    (thermal,) = result.thermal
    assert thermal.status == "pending" and any(r.startswith("EOS-sensitive: viable at the nominal point")
                                               and "excluded at the point with the upper table" in r
                                               for r in thermal.pending)
    assert result.level == "viable_pending" and result.thermal_viability == "viable_pending"


@pytest.mark.needs("eos")
def test_a_fitted_thermal_point_the_tables_agree_on_stands(tmp_path):
    """The exclusion far from every root (above 30 GeV): viable at all three tables, the headline viable."""
    result = _study(tmp_path, excluded_above=30.0)
    assert [b.status for b in result.thermal] == ["viable"] and result.level == "viable"


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_thermal_point_only_a_table_has_leaves_the_headline_undetermined(tmp_path):
    """Ωh² = 0.0029 m_χ: over the fitted masses 10–40 GeV the nominal Ωh² is 0.029–0.116, no root; with the lower
    table (× 1.04) 0.0302–0.1206, a root at 39.8 GeV. Nominally no thermal point; with a table's, undetermined,
    EOS-sensitive."""
    result = _study(tmp_path, excluded_above=100.0, scale=0.0029)
    assert not result.thermal
    assert result.level == "undetermined" and result.summary.startswith("EOS-sensitive: the lower table has a "
                                                                        "thermal point")


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_tables_point_that_fails_the_fit_does_not_support_viability(tmp_path):
    """The recheck's RC21-03 (2026-10-22): every status viable, but at the upper table's root (20.83 GeV) the fit's
    local Z is 0.5, below the anomaly-fit criterion; the nominal viable point is pending, EOS-sensitive, not viable."""
    result = _study(tmp_path, excluded_above=100.0, poor_fit_above=20.5)
    (thermal,) = result.thermal
    assert thermal.status == "pending" and any("below the declared anomaly-fit threshold" in r for r in thermal.pending)
    assert result.level == "viable_pending"


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_unresolved_table_brackets_keep_an_excluded_headline_undetermined(tmp_path):
    """The recheck's RC21-04 (2026-10-22): Ωh² 0.08, 0.13, 0.124, 0.13 at 10–40 GeV, every point excluded; the upper
    table's brackets above 20 GeV fail to refine (injected). They could hold a viable explanation: the headline is
    undetermined, and the saved result keeps them."""
    result = _study(tmp_path, excluded_above=0.0, masses=(10, 20, 30, 40), unresolved_tables_from=19.99,
                    nominal=lambda m: float(np.interp(m, [10, 20, 30, 40], [.08, .13, .124, .13])))
    assert result.level == "undetermined" and "the upper table: 20–30 GeV thermal bracket" in result.summary
    assert any(p.startswith("the upper table: 30–40 GeV") for p in result.thermal_pending)


def test_an_excluded_table_point_whose_fit_decides_nothing_does_not_keep_an_exclusion():
    """The re-audit's RR22-03 (2026-10-22): a table's excluded point whose bounded physical fit sat at its range's edge
    kept the nominal exclusion (an explanation beyond the edge neither found nor excluded), and an excluded table-only
    point with an undecided fit left an all-excluded headline standing. An excluded point keeps an exclusion only if it
    also fits; a definitively poor fit ("below") still does."""
    from adroit.core.model_spec import PhysicalFitRange
    from adroit.parameter_space.physical_fit import FitSettings, PhysicalFit
    p = Point(m_chi=20.8, m_med=1000, g_chi=.5)

    def row(status: str, fit: PhysicalFit | None = None, z: float = 2.0) -> si.BandPoint:
        return si.BandPoint(m_chi=p.m_chi, s_hat=4, events_at_unit=4, mu_hat=1, mu_68=(.8, 1.2), z_local=z, point=p,
                            status=status, physical_fit=fit)
    edge = PhysicalFit(bounds=PhysicalFitRange(low=0, high=.5), settings=FitSettings(), point=p, resolved=True,
                       identifiable=True, at_boundary=True, q0=4.0)
    nominal = row("excluded")
    assert si._fit_state(row("excluded", edge)) == "edge" and not si._supports(nominal, row("excluded", edge))
    assert si._supports(nominal, row("excluded")) and si._supports(nominal, row("viable", z=0.5))   # "below"
    for state in ("edge", "unresolved", "unidentifiable", "no_statistic"):
        assert si._eos_level("excluded", "nominal", [("a table's point", "excluded", state)], [])[0] == "undetermined"
    assert si._eos_level("excluded", "nominal", [("a table's point", "excluded", "eligible")], [])[0] == "excluded"
    assert si._eos_level("excluded", "nominal", [("a table's point", "viable", "below")], [])[0] == "excluded"


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_nominal_point_that_does_not_fit_does_not_hide_the_tables_points(tmp_path):
    """The re-audit's RV22-02 (2026-10-22): the nominal root at 20 GeV fails the fit (local Z 0.5) while the tables'
    roots at 20.83 and 19.23 GeV, between the same fitted masses, fit and survive; the nominal root's cell had hidden
    them, the headline "no thermal". It is undetermined, EOS-sensitive, and the saved result keeps those points."""
    result = _study(tmp_path, excluded_above=100.0, poor_fit_at=20.0)
    assert result.level == "undetermined" and "the upper table has a thermal point" in result.summary
    assert any("the lower table has a thermal point" in p for p in result.thermal_pending)
    assert _study(tmp_path, excluded_above=100.0).level == "viable"            # the nominal root fitting: unchanged


def _peaked(m: float) -> float:
    """A local Z peaked at 20 GeV: 2 there, 0.26 at the fitted masses 10 and 30 GeV (the RV22 audit's RX22-04)."""
    return 2 * np.exp(-((m - 20) / 7) ** 2)


@pytest.mark.parametrize("physical", [False, True])
@pytest.mark.needs("eos")
def test_a_refitted_thermal_point_that_fits_is_not_overruled_by_the_coarse_band(tmp_path, physical):
    """The RV22 audit's RX22-04 (2026-10-22): fitted at 10 and 30 GeV only (Z = 0.26), the root at 20 GeV refitted to
    Z = 2, viable at all three tables (20, 20.83, 19.23 GeV); the headline said "no fit" from the band alone. Both fit
    representations."""
    result = _study(tmp_path, excluded_above=100.0, masses=(10, 30), z_of=_peaked, physical=physical)
    assert [b.status for b in result.thermal] == ["viable"] and si._fit_state(result.thermal[0]) == "eligible"
    assert result.level == "viable" and result.fit_quality == "fits"


@pytest.mark.eos_band
@pytest.mark.parametrize("physical", [False, True])
@pytest.mark.needs("eos")
def test_a_tables_refitted_point_that_fits_leaves_a_no_fit_headline_undetermined(tmp_path, physical):
    """RX22-04's first case: no nominal root (Ωh² = 0.125 − 0.0002(m − 20) > 0.12 from 10 to 30 GeV); with the upper
    table (× 0.96) a root at 20 GeV, refitted to Z = 2, viable. "No fit" stood, the table's point unsaved; now the
    headline is undetermined, EOS-sensitive, its reason saved."""
    result = _study(tmp_path, excluded_above=100.0, masses=(10, 30), z_of=_peaked, physical=physical,
                    nominal=lambda m: 0.125 - 0.0002 * (m - 20))
    assert not result.thermal and result.level == "undetermined"
    assert result.summary.startswith("EOS-sensitive: the upper table has a thermal point at m_χ = 20 GeV (viable; "
                                     "its fit meets the anomaly-fit criterion)")
    assert any(r.startswith("the upper table has a thermal point at m_χ = 20 GeV") for r in result.thermal_pending)


@pytest.mark.eos_band
@pytest.mark.parametrize("physical", [False, True])
@pytest.mark.needs("eos")
def test_a_tables_refit_that_fits_is_saved_as_a_fit_not_as_no_fit(tmp_path, physical):
    """The RX22 audit's RY23-02 (2026-10-23): with no nominal root and the upper table's root at 20 GeV refitted to
    Z = 2, the headline was undetermined but the saved fit quality "no_fit", into the evidence summary too. A fit
    found is not a thermal explanation: the fit quality is "fits", the headline stays undetermined, and the table's
    refitted point is saved."""
    from adroit.evidence import results
    result = _study(tmp_path, excluded_above=100.0, masses=(10, 30), z_of=_peaked, physical=physical,
                    nominal=lambda m: 0.125 - 0.0002 * (m - 20))
    assert result.level == "undetermined" and result.fit_quality == "fits"
    assert [round(b.m_chi, 3) for b in result.eos_thermal["upper"]] == [20.0]
    saved = results.summary("single_idea", result)
    assert saved["fit_quality"] == "fits" and saved["eos_thermal"]["upper"][0]["m_chi"] == pytest.approx(20.0)


@pytest.mark.parametrize("physical", [False, True])
def test_a_fit_without_a_finite_statistic_does_not_say_no_fit(tmp_path, physical):
    """The RX22 audit's RY23-03 (2026-10-23): the nominal root at 20 GeV refitted with no finite statistic (the
    coarse fits and the tables' points definitively poor) gave a definitive "no fit", the statistic's absence read as
    Z < 1. It is undetermined, its reason saved."""
    def z_of(m: float) -> float:
        return float("nan") if abs(m - 20) < 1e-3 else 0.5
    result = _study(tmp_path, excluded_above=100.0, masses=(10, 30), z_of=z_of, physical=physical)
    assert result.level == "undetermined" and result.fit_quality == "undetermined"
    assert "has no finite statistic" in result.summary
    assert any("the fit at m_χ = 20 GeV has no finite statistic" in r for r in result.thermal_pending)


NONFINITE = [("inverse", float("inf")), ("inverse", float("-inf")), ("inverse", float("nan")),
             ("physical", float("inf")), ("physical", float("-inf")), ("physical", float("nan")), ("physical", None)]


@pytest.mark.parametrize("representation, bad", NONFINITE)
def test_a_thermal_point_without_a_finite_statistic_does_not_certify_viability(tmp_path, representation, bad):
    """The RY23 audit's RZ23-01 (2026-10-23): beside eligible coarse fits and tables' refits, the nominal root at
    20 GeV refitted with an infinite statistic was accepted (Z = ∞ ≥ 1) and the headline read viable. A thermal point
    is accepted only by its fit state; one without a finite statistic leaves the headline undetermined, saved."""
    physical = representation == "physical"
    at_root = lambda m: abs(m - 20) < 1e-3                                       # noqa: E731
    result = _study(tmp_path, excluded_above=100.0, masses=(10, 30), physical=physical,
                    z_of=lambda m: (bad if bad is not None else float("nan")) if at_root(m) and not physical else 2.0,
                    q0_of=(lambda m: bad if at_root(m) else 4.0) if physical else None)
    (point,) = result.thermal
    assert si._fit_state(point) == "no_statistic" and result.level == "undetermined"
    assert any("the thermal point at m_χ = 20 GeV has no finite fit statistic" in r for r in result.thermal_pending)


@pytest.mark.eos_band
@pytest.mark.parametrize("physical", [False, True])
@pytest.mark.needs("eos")
def test_a_pending_result_with_a_nan_refit_reads_back_as_its_own_evidence(tmp_path, physical):
    """The RY23 audit's RZ23-02 (2026-10-23): a pending study whose tables' refits have NaN statistics was refused on
    reading its own evidence ("decision mismatch": NaN unequal to itself). An unchanged result now reads back; a
    changed table status is still refused; a result without the field still reads."""
    import json

    from adroit.evidence import build
    nan_at_tables = lambda m: float("nan") if abs(m - 20) > 0.5 and 19 < m < 22 else 0.5   # noqa: E731
    result = _study(tmp_path, excluded_above=100.0, masses=(10, 30), physical=physical, z_of=nan_at_tables,
                    q0_of=(lambda m: nan_at_tables(m) ** 2) if physical else None)
    assert result.level == "undetermined" and result.eos_thermal
    path = tmp_path / "out" / "result.json"
    path.parent.mkdir()
    path.write_text(result.model_dump_json())
    build.save(path, "single_idea")
    assert build.read(path).summary["fit_quality"] == result.fit_quality
    sidecar = build.sidecar_path(path)
    data = json.loads(sidecar.read_text())
    data["summary"]["eos_thermal"]["upper"][0]["status"] = "excluded"
    sidecar.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="decision mismatch"):
        build.read(path)
    older = tmp_path / "older" / "result.json"
    older.parent.mkdir()
    older.write_text(result.model_copy(update={"eos_thermal": {}}).model_dump_json())
    build.save(older, "single_idea")
    assert "eos_thermal" not in build.read(older).summary


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_single_idea_thermal_certificate_is_bound_to_the_tables_it_used(tmp_path, eos_copy):
    """The auditor's CO recheck, CR-01 (2026-10-26): the single-idea study's thermal certificates had no tables bound, so
    a changed table left them current. Through ``_study``: the nominal point's certificate is bound to every table
    (its band across them), each table's own point to its own table. One table's bytes changed afterwards: the saved
    result unchanged, its headline reads stale, and so does the point's explanation; the other table's point not."""
    import hashlib
    import json
    from adroit.evidence.points import explain
    from adroit.orchestrator import study_headline
    from adroit.parameter_space import certification
    result = _study(tmp_path, excluded_above=30.0)
    (thermal,) = result.thermal
    assert set(thermal.certificate.bound.eos_tables) == set(relic.EOS_TABLES)
    assert {name: [set(r.certificate.bound.eos_tables) for r in rows] for name, rows in result.eos_thermal.items()} \
        == {"upper": [{"upper"}], "lower": [{"lower"}]}
    saved = tmp_path / "result.json"
    saved.write_text(result.model_dump_json())
    before, data = hashlib.sha256(saved.read_bytes()).hexdigest(), json.loads(saved.read_text())
    assert study_headline.headline(data).certification == "certified"
    lower = eos_copy / relic.EOS_TABLES["lower"][0]
    lower.write_bytes(lower.read_bytes() + b"\n# changed\n")
    found = study_headline.headline(data)
    assert found.certification == "stale" and found.words == "VIABLE · STALE CERTIFICATION"
    assert explain(saved, "thermal:0").certification.startswith("stale: the equation of state's lower table")
    assert explain(saved, "upper-thermal:0").certification == "certified"
    upper = result.eos_thermal["upper"][0].certificate
    assert certification.stale_reasons(upper, certification.current_bound(upper)) == []
    assert hashlib.sha256(saved.read_bytes()).hexdigest() == before
