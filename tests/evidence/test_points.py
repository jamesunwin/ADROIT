"""Explain a point of a saved study (the owner's workbench plan, 2026-10-18, §A): every constraint in exactly one of
excluded / allowed / pending, from the saved result alone, missing values kept missing, and nothing recalculated."""

from __future__ import annotations

import pytest

from adroit.evidence import points as pts
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.limits import StatisticalLimit
from adroit.parameter_space.scan import Axis, PointResult, ScanRequest, ScanResult
from adroit.parameter_space.verdict import Crossing, Verdict

RECORD = 'atlas-2301.10731-hinv'


def _row(m_chi: float, m_med: float, *, excluded: bool = False, omega: float | None = 0.12) -> PointResult:
    """A saved grid point: a direct-detection comparison (allowed or excluding), an allowed collider search and a
    record awaiting verification (pending)."""
    return PointResult(point=Point(m_chi=m_chi, m_med=m_med, g_chi=1.0, g_q=0.25), omega_h2=omega, dd_kind='SI',
                       dd_sigma_cm2=2e-45 if excluded else 1e-46, dd_limit_cm2=1e-45,   # σ/limit is the ratio
                       excluded={'direct detection': excluded, 'colliders (CMS)': False,
                                 'invisible Higgs width (ATLAS)': None},
                       values={'direct detection': 2.0 if excluded else 0.1},
                       ratios={'direct detection': 2.0 if excluded else 0.1},
                       statistical_limits={'direct detection': StatisticalLimit(value=1e-45, confidence_level=0.9,
                                                                                source='LZ 2024', construction='PLR')},
                       pending=['the invisible Higgs width: its record (ATLAS, arXiv:2301.10731) awaits a person\'s '
                                f'verification ({RECORD})'])


def _result(tmp_path):
    """A small saved Track 1 result of a vector mediator: a 2 × 2 grid and one thermal root."""
    import yaml
    from adroit.core.model_spec import ModelSpec
    from adroit.model_building.audit import audit
    from adroit.orchestrator.track1 import Track1Request, Track1Result
    from pathlib import Path
    docs = Path(__file__).resolve().parents[2] / 'docs'
    spec = ModelSpec.model_validate(yaml.safe_load((docs / 'dm13' / 'vector_mediator.yaml').read_text()).get('spec') or
                                    yaml.safe_load((docs / 'dm13' / 'vector_mediator.yaml').read_text()))
    request = ScanRequest(model_class=Spin1Class(), fixed=Point(m_chi=100, m_med=1000, g_chi=1.0, g_q=0.25),
                          x=Axis(parameter='m_med', low=500, high=1000, n=2), y=Axis(parameter='m_chi', low=50, high=100, n=2))
    grid = [_row(50, 500, excluded=True), _row(50, 1000), _row(100, 500, omega=None), _row(100, 1000)]
    scan = ScanResult(request=request, xs=[500, 1000], ys=[50, 100], points=grid)
    root = _row(75, 750)
    crossing = Crossing(point=root.point, status='pending', pending=list(root.pending), omega_h2=0.12, target=0.12,
                        relative_residual=1e-4, converged=True, kind='contour', evaluation=root)
    verdict = Verdict(level='viable_pending', summary='evaluated thermal solutions survive computed constraints',
                      target=0.12, crossings=[crossing])
    result = Track1Result(request=Track1Request(spec=spec, literature=False), audit=audit(spec), class_name='vector',
                          scan=scan, verdict=verdict)
    path = tmp_path / 'result.json'
    path.write_text(result.model_dump_json(indent=1))
    return path


@pytest.fixture
def saved(tmp_path, monkeypatch):
    """The fixture's result, with every physics evaluator set to raise: an explanation that recalculates fails."""
    from adroit.parameter_space import scan as scan_module
    def refuse(*args, **kwargs):
        raise AssertionError('an explanation must not recalculate')
    monkeypatch.setattr(scan_module, 'evaluate', refuse)
    monkeypatch.setattr(Spin1Class, 'omega_h2', refuse)
    monkeypatch.setattr(Spin1Class, 'dd', refuse)
    return _result(tmp_path)


def test_the_point_table_lists_the_grid_and_the_root(saved) -> None:
    from adroit.evidence.results import load_result
    workflow, result = load_result(saved)
    rows = {r.point_id: r for r in pts.points(workflow, result)}
    assert set(rows) == {'grid:0', 'grid:1', 'grid:2', 'grid:3', 'contour:0'}
    assert rows['grid:0'].status == 'excluded' and rows['grid:0'].reason == 'direct detection'
    assert rows['grid:1'].status == 'pending' and 'awaits a person' in rows['grid:1'].reason
    assert rows['contour:0'].kind == 'thermal root' and rows['grid:2'].omega_h2 is None
    assert rows['grid:1'].coordinates == {'m_chi': 50, 'm_med': 1000, 'g_chi': 1.0, 'g_q': 0.25, 'g_l': 0.0}


def test_every_constraint_is_in_exactly_one_group_and_the_groups_give_the_status(saved) -> None:
    excluded = pts.explain(saved, 'grid:0')
    groups = {c.constraint: c.group for c in excluded.comparisons}
    assert groups['direct detection'] == 'excluded' and groups['colliders (CMS)'] == 'allowed'
    assert groups['invisible Higgs width (ATLAS)'] == 'pending'
    assert len(excluded.comparisons) == len({c.constraint for c in excluded.comparisons})
    pending = pts.explain(saved, 'grid:1')
    assert not any(c.group == 'excluded' for c in pending.comparisons) and pending.row.status == 'pending'


def test_a_comparison_carries_its_prediction_limit_cl_source_and_review(saved) -> None:
    found = pts.explain(saved, 'grid:0')
    dd = next(c for c in found.comparisons if c.constraint == 'direct detection')
    assert (dd.ratio, dd.limit, dd.native_confidence_level, dd.required_confidence_level) == (2.0, 1e-45, 0.9, 0.95)
    assert dd.construction == 'PLR' and dd.units == 'cm²'          # the prediction's and the limit's (S18-10)
    assert dd.prediction is not None and dd.prediction == pytest.approx(dd.ratio * dd.limit)
    assert found.origin == 'reconstructed from the saved result'


def test_a_pending_record_links_to_its_review_page(saved) -> None:
    found = pts.explain(saved, 'grid:1')
    hinv = next(c for c in found.comparisons if c.constraint == 'invisible Higgs width (ATLAS)')
    assert any(link.target == f'/record?id={RECORD}' for link in hinv.links)
    assert pts.links('a reason that names nothing known', []) == []


def test_a_missing_value_stays_missing(saved) -> None:
    found = pts.explain(saved, 'grid:2')
    omega = next(c for c in found.calculated if c['observable'] == 'omega_h2')
    assert omega['value'] is None and any(line.startswith('omega_h2: not calculated') for line in found.missing)


def test_a_thermal_root_quotes_its_target_and_residual(saved) -> None:
    found = pts.explain(saved, 'contour:0')
    assert found.row.kind == 'thermal root'
    assert found.context == ['refined thermal root for Ωh² = 0.12 (relative residual 0.0001; converged)',
                             'halo: Published halos (reproduction), not recorded']    # a result from before the choice


def test_an_unknown_point_is_refused(saved) -> None:
    with pytest.raises(ValueError, match='no point'):
        pts.explain(saved, 'grid:99')


def _rewrite(path, change):
    from adroit.evidence.results import load_result
    workflow, result = load_result(path)
    change(result)
    path.write_text(result.model_dump_json(indent=1))
    return workflow, result


def test_a_grid_sample_and_a_root_at_the_same_coordinates_are_not_joined(saved) -> None:
    """S18-09 (the stacked audit of 2026-10-18): the audit's control. A refined root saved at grid:0's coordinates
    with its own ratio 0.123456 and Ωh² 0.121234 does not replace grid:0's saved 2.0 and 0.12, in the inspector or the
    table, and the table has one row per point and observable."""
    from adroit.evidence import exports

    def same_place(result):
        grid = result.scan.points[0]
        root = grid.model_copy(deep=True)
        root.omega_h2, root.ratios['direct detection'], root.excluded['direct detection'] = 0.121234, 0.123456, False
        result.verdict.crossings[0] = result.verdict.crossings[0].model_copy(update={
            'point': root.point, 'evaluation': root, 'omega_h2': root.omega_h2, 'status': 'pending'})
    _rewrite(saved, same_place)
    grid = pts.explain(saved, 'grid:0')
    assert next(c.ratio for c in grid.comparisons if c.constraint == 'direct detection') == 2.0
    assert next(c['value'] for c in grid.calculated if c['observable'] == 'omega_h2') == 0.12
    root = pts.explain(saved, 'contour:0')
    assert next(c.ratio for c in root.comparisons if c.constraint == 'direct detection') == 0.123456
    rows = [r for r in exports.table(saved) if r['point'] == 'grid:0' and r['observable'] == 'direct detection']
    assert len(rows) == 1 and rows[0]['value'] == 2.0 and rows[0]['excluded'] == 'true'


def test_a_saved_ratio_is_not_shown_as_a_limit(saved) -> None:
    """S18-10: the audit's control. A records-based statistic holds the prediction/limit ratio (0.5), not the bound;
    the inspector shows the saved BR prediction and the record's bound from the run's captured context, and direct
    detection's σ from its own field."""
    from adroit.constraints import database
    from adroit.parameter_space.scan import INVISIBLE_H, DirectDetection, SpectralComparison, _statistics
    from adroit.parameter_space.portals.higgs import HiggsPortalScalar
    bound = database.record(RECORD).data['br_limit']

    def ratio_only(result):
        row = result.scan.points[1]
        row.excluded = {INVISIBLE_H: False, 'direct detection': False}
        row.pending = []
        row.values = {'BR(h → invisible)': bound / 2}
        row.ratios = {INVISIBLE_H: 0.5, 'direct detection': 0.1}
        dd = DirectDetection(kind='SI', sigma_cm2=row.dd_sigma_cm2, limit_cm2=row.dd_limit_cm2, ratio=0.1,
                             excluded=False, statistic=row.statistical_limits['direct detection'])
        row.statistical_limits = _statistics(HiggsPortalScalar(), row.point, dd, SpectralComparison(), row.excluded,
                                             row.ratios)
    _rewrite(saved, ratio_only)
    found = {c.constraint: c for c in pts.explain(saved, 'grid:1').comparisons}
    h = found[INVISIBLE_H]           # this legacy result kept no captured sources: the bound is missing, not 0.5
    assert (h.prediction, h.limit, h.ratio) == (pytest.approx(bound / 2), None, 0.5)
    dd = found['direct detection']
    assert (dd.prediction, dd.limit, dd.units) == (1e-46, 1e-45, 'cm²')
    from types import SimpleNamespace
    from adroit.evidence.build import read
    from adroit.evidence.results import load_result
    _, result = load_result(saved)
    captured = SimpleNamespace(sources=[SimpleNamespace(id=RECORD, metadata=database.record(RECORD).model_dump(mode='json'))])
    obs = {o.observable: o for o in pts.own_observations(result.scan.points[1], {}, read(saved))}
    with_context = pts._comparison(INVISIBLE_H, 'allowed', obs[INVISIBLE_H], result.scan.points[1], [], '', captured)
    assert (with_context.limit, with_context.units) == (pytest.approx(bound), 'branching ratio')


def test_figure_downloads_use_only_saved_numbers(saved) -> None:
    """S18-11: with every evaluator set to raise (the ``saved`` fixture), the figures are still drawn: direct
    detection from the σ and limit saved with each relic-contour point."""
    from adroit.evidence import exports
    files = exports.figures(saved, ('svg',))
    assert 'parameter_plane.svg' in files and 'direct_detection.svg' in files


def test_discovery_requirements_reach_the_grid_view_and_the_table(saved) -> None:
    """S18-03 (the views): a result whose pinned assessment leaves a requirement unresolved everywhere shows its
    otherwise allowed grid samples as pending with the requirement, in the table, the inspector and the export."""
    from adroit.core.constraint_discovery import DiscoveryCoverage, Requirement
    from adroit.evidence import exports
    from adroit.evidence.results import load_result

    def allowed_with_discovery(result):
        for p in result.scan.points:
            p.pending, p.excluded = [], {k: False for k in p.excluded}
        result.discovery_coverage = DiscoveryCoverage(
            session_id='a' * 32, assessment_sha256='b' * 64, model_sha256='c' * 64, model_reference='catalog:model',
            searched_at='2026-10-18', requirements=[Requirement(candidate_id='t', name='unprocessed monojet',
                                                                 reference='arXiv:2107.13021',
                                                                 constraint_class='collider',
                                                                 reason='a new record awaits review')])
    _rewrite(saved, allowed_with_discovery)
    workflow, result = load_result(saved)
    grid = next(r for r in pts.points(workflow, result) if r.point_id == 'grid:1')
    assert grid.status == 'pending' and grid.reason.startswith('discovery: unprocessed monojet')
    assert any(c.group == 'pending' and c.constraint == 'discovery' for c in pts.explain(saved, 'grid:1').comparisons)
    assert any(r['point'] == 'grid:1' and r['observable'] == 'constraint discovery' for r in exports.table(saved))


def test_an_unestablished_comparison_is_one_pending_card_with_its_ratio(saved) -> None:
    """RD-05 (the third recheck): the point's status read pending, but its card for the same comparison had appeared
    under both excluded (with no reason) and pending. A record of unknown version that no table places qualifies every
    comparison, so direct detection here is one pending card, with the reason and its saved ratio."""
    import json
    data = json.loads(saved.read_text())
    data["scan"]["points"][0]["records"] = {"a-record-of-unknown-version": ""}
    saved.write_text(json.dumps(data))
    found = pts.explain(saved, "grid:0")
    cards = [c for c in found.comparisons if c.constraint == "direct detection"]
    assert [c.group for c in cards] == ["pending"]
    assert any("a-record-of-unknown-version" in r for r in cards[0].reasons)
    assert found.row.status == "pending"
