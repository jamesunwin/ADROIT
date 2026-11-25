"""The equation of state's band on the thermal contour (the owner's decision #3, 2026-10-20; ``verdict._eos_band``):
a decided crossing is judged again at its root refound with Saikawa & Shirai's upper and lower tables; the same status
at all three stands, with the band noted; else it is pending, EOS-sensitive, naming what decides."""
import importlib

import pytest

from adroit.constraints import relic
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.scan import Axis, PointResult, ScanRequest, ScanResult, _point_at

v = importlib.import_module('adroit.parameter_space.verdict')
SHIFT = {'': 1.0, 'ss2020-upper': 0.96, 'ss2020-lower': 1.04}      # a toy's Ωh² under each table


def _density(p: Point) -> float:
    return .006 * p.m_chi * SHIFT[relic.current_eos()]


def _grid() -> ScanResult:
    request = ScanRequest(model_class=Spin1Class(), fixed=Point(m_chi=10, m_med=30),
                          x=Axis(parameter='m_chi', low=10, high=40, n=2),
                          y=Axis(parameter='g_chi', low=.1, high=.2, n=2), mediator_ratio=3)
    return ScanResult(request=request, xs=request.x.values(), ys=request.y.values(), points=[
        PointResult(point=_point_at(request, x, y), omega_h2=.006 * x, dd_kind='SI', dd_sigma_cm2=0, dd_limit_cm2=1,
                    excluded={'toy': False, 'colliders (CMS)': False}) for y in request.y.values() for x in request.x.values()])


@pytest.fixture
def toy(monkeypatch):
    """The nominal root at m_χ = 20 GeV, the upper table's at 20.83 and the lower's at 19.23; a toy constraint
    excludes above ``threshold`` GeV."""
    monkeypatch.setattr(Spin1Class, 'omega_h2', lambda self, p: _density(p))
    monkeypatch.setattr('adroit.parameter_space.searches.prefetch_lhc', lambda cls, pts, *a: [None] * len(pts))
    limit = {}

    def evaluate(cls, p, *args):
        return PointResult(point=p, omega_h2=_density(p), dd_kind='SI', dd_sigma_cm2=0, dd_limit_cm2=1,
                           excluded={'toy': p.m_chi > limit['threshold'], 'colliders (CMS)': False})
    monkeypatch.setattr(v, 'evaluate', evaluate)
    return limit


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_crossing_the_band_decides_differently_is_pending_and_names_what_decides(toy):
    toy['threshold'] = 20.5
    verdict = v.verdict(_grid())
    assert verdict.crossings and all(c.status == 'pending' for c in verdict.crossings)
    reason = next(x for x in verdict.crossings[0].pending if x.startswith('EOS-sensitive'))
    assert reason.startswith('EOS-sensitive: viable at the nominal root, excluded at the root with the upper table, '
                             'viable at the root with the lower table') and 'deciding: toy' in reason, reason
    assert 'm_chi = 20.83' in reason and 'm_chi = 19.23' in reason
    assert verdict.level == 'viable_pending'


@pytest.mark.eos_band
@pytest.mark.parametrize('threshold, status', [(25.0, 'viable'), (15.0, 'excluded')])
@pytest.mark.needs("eos")
def test_a_crossing_decided_alike_at_all_three_roots_stands_with_the_band_noted(toy, threshold, status):
    toy['threshold'] = threshold
    verdict = v.verdict(_grid())
    assert verdict.crossings and all(c.status == status for c in verdict.crossings)
    assert any(f.startswith(f"the equation of state's band: {status} also at the roots") for f in
               verdict.crossings[0].flags)


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_the_band_is_left_out_of_the_disagreement_checks_and_a_root_without_its_bracket(toy, monkeypatch):
    """``_across`` and ``_beyond`` judge other targets: no band there. A decided root without its cell cannot have
    the band computed: it is pending, not left as it was (the consistency audit's CA-01, 2026-10-24)."""
    toy['threshold'] = 20.5
    calls = []
    monkeypatch.setattr(v, '_eos_root', lambda *a, **k: calls.append(a) or v.Crossing(point=a[1].point,
                                                                                      status='viable'))
    result = _grid()
    roots, omitted = v._thermal_roots(result, v.OMEGA)
    assert v._verdict_from_roots(result, roots, omitted, 80, None, target=v.OMEGA).crossings and not calls
    v._verdict_from_roots(result, roots, omitted, 80, None)                  # the request's target: the band
    assert len(calls) == 2 * len(roots)
    nominal = v.Crossing(point=roots[0].point, status='viable')
    cellless = roots[0].model_copy(update={'bracket': None})
    judged = v._eos_band(result, cellless, nominal, 0, None, None, 0.12)
    assert judged.status == 'pending' and "this root's grid cell is not recorded" in judged.pending[-1]
    assert 'bracket' not in cellless.model_dump(mode='json')


def _plane(gs: list[float]) -> ScanResult:
    """A plane in (m_χ, g_χ) whose Ωh² depends on g_χ alone (``_toy_density``), as the audit's design controls."""
    request = ScanRequest(model_class=Spin1Class(), fixed=Point(m_chi=10, m_med=30),
                          x=Axis(parameter='m_chi', low=10, high=20, n=2),
                          y=Axis(parameter='g_chi', low=gs[0], high=gs[-1], n=len(gs), log=False), mediator_ratio=3)
    return ScanResult(request=request, xs=request.x.values(), ys=request.y.values(), points=[
        PointResult(point=_point_at(request, x, y), omega_h2=_toy_density(_point_at(request, x, y), ''),
                    dd_kind='SI', dd_sigma_cm2=0, dd_limit_cm2=1, excluded={'toy': False, 'colliders (CMS)': False})
        for y in request.y.values() for x in request.x.values()])


DESIGN = {}                                                       # the density in use: one of the two cases below


def _toy_density(p: Point, label: str | None = None) -> float:
    t = {'': 0.0, 'ss2020-upper': 1.0, 'ss2020-lower': -1.0}[relic.current_eos() if label is None else label]
    return DESIGN['omega'](t, p.g_chi)


@pytest.fixture
def design(monkeypatch):
    """The recheck's RB20-07 design controls (2026-10-20): Ωh²(t, g) with t = 0 nominal, +1 and −1 the two tables."""
    monkeypatch.setattr(Spin1Class, 'omega_h2', lambda self, p: _toy_density(p))
    monkeypatch.setattr('adroit.parameter_space.searches.prefetch_lhc', lambda cls, pts, *a: [None] * len(pts))
    excluded = {}

    def evaluate(cls, p, *args):
        return PointResult(point=p, omega_h2=_toy_density(p), dd_kind='SI', dd_sigma_cm2=0, dd_limit_cm2=1,
                           excluded={'toy': excluded['between'][0] < p.g_chi < excluded['between'][1],
                                     'colliders (CMS)': False})
    monkeypatch.setattr(v, 'evaluate', evaluate)
    return excluded


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_an_interior_equation_of_state_is_outside_the_three_table_claim(design):
    """Its first case: Ωh² = 0.12(1 − 0.04t)/g², the three roots g = 1, 0.9798 and 1.0198 all allowed with an exclusion
    for 1.009 < g < 1.011, which the root of t = −½ (g = 1.0099) would meet. The check holds at the two supplied
    tables and says so, not of every equation of state between them."""
    DESIGN['omega'] = lambda t, g: 0.12 * (1 - 0.04 * t) / g ** 2
    design['between'] = (1.009, 1.011)
    verdict = v.verdict(_plane([0.5, 2.0]))
    assert verdict.level == 'viable' and verdict.crossings
    flag = next(f for f in verdict.crossings[0].flags if f.startswith("the equation of state's band"))
    assert 'the two supplied tables, not every equation of state between them' in flag


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_root_only_a_table_has_leaves_a_rootless_verdict_pending(design):
    """Its second case: Ωh² = 0.121 + 0.04(g − 1)² − 0.004t has no nominal root (overabundant everywhere), while the
    upper table's (t = 1) has two, g = 0.726 and 1.274. The search for new roots finds both, and the verdict is
    pending, EOS-sensitive, not overabundant."""
    DESIGN['omega'] = lambda t, g: 0.121 + 0.04 * (g - 1) ** 2 - 0.004 * t
    design['between'] = (5.0, 6.0)
    verdict = v.verdict(_plane([0.5, 1.0, 1.5]))
    assert verdict.level == 'pending' and not verdict.crossings
    reasons = [u for u in verdict.unresolved if u.startswith('EOS-sensitive')]
    assert len(reasons) == 4 and all('the upper table has a thermal root' in u for u in reasons)  # two m_χ columns
    assert sorted({round(float(u.split('g_chi = ')[1].split(',')[0]), 3) for u in reasons}) == [0.726, 1.274]


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_tables_root_on_a_grid_node_leaves_a_rootless_verdict_pending(design):
    """The RV22 audit's RX22-03 (2026-10-22): Ωh² = 0.121 + 0.004(g − 1)² − 0.001t has no nominal root, while the
    upper table's is 0.12 exactly at the grid node g = 1. The strict sign change skipped it and the verdict read
    overabundant; a root at an end is a root, found once per node."""
    DESIGN['omega'] = lambda t, g: 0.121 + 0.004 * (g - 1) ** 2 - 0.001 * t
    design['between'] = (5.0, 6.0)
    verdict = v.verdict(_plane([0.5, 1.0, 1.5]))
    assert verdict.level == 'pending' and not verdict.crossings
    reasons = [u for u in verdict.unresolved if 'the upper table has a thermal root' in u]
    assert len(reasons) == 2 and all('g_chi = 1,' in u for u in reasons)          # one per m_χ column, not per edge


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_table_that_cannot_be_computed_leaves_a_rootless_verdict_pending(design):
    """RX22-03's second case: the upper table's Ωh² unavailable; the edge was skipped and the verdict overabundant."""
    DESIGN['omega'] = lambda t, g: None if t == 1.0 else 0.121 + 0.004 * (g - 1) ** 2 - 0.001 * t
    design['between'] = (5.0, 6.0)
    verdict = v.verdict(_plane([0.5, 1.0, 1.5]))
    assert verdict.level == 'pending'
    assert any("the upper table's Ωh² could not be computed at the ends of" in u and 'incomplete' in u
               for u in verdict.unresolved)


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_tables_root_whose_density_moves_when_judged_does_not_decide_the_band(design, monkeypatch):
    """The RV22 audit's RX22-05 (2026-10-22), a fault injection: the tables' roots solve to 0.12, but the constraints'
    evaluation there gives 0.132. The nominal root is rechecked to 1%; the tables' were not, and the band read viable."""
    DESIGN['omega'] = lambda t, g: 0.12 * (1 - 0.04 * t) / g ** 2

    def evaluate(cls, p, *args):
        return PointResult(point=p, omega_h2=_toy_density(p) * (1.1 if relic.current_eos() else 1.0), dd_kind='SI',
                           dd_sigma_cm2=0, dd_limit_cm2=1, excluded={'toy': False, 'colliders (CMS)': False})
    monkeypatch.setattr(v, 'evaluate', evaluate)
    verdict = v.verdict(_plane([0.5, 2.0]))
    assert verdict.crossings and all(c.status == 'pending' for c in verdict.crossings)
    assert verdict.level == 'viable_pending'
    reason = next(x for x in verdict.crossings[0].pending if x.startswith('EOS-sensitive'))
    assert 'pending at the root with the upper table' in reason
    assert 'changed or was unavailable when constraints were evaluated' in reason


BAND_CASES = {'roots and band points': (lambda t, g: 0.12 / g ** 2, [0.98, 1.02]),
              'band points alone': (lambda t, g: 0.125, [0.98, 1.02])}


@pytest.mark.eos_band
@pytest.mark.parametrize('case', BAND_CASES)
@pytest.mark.parametrize('between, status', [((5.0, 6.0), 'viable'), ((0.0, 10.0), 'excluded')])
def test_without_the_tables_no_theory_band_point_decides_the_combined_view(design, monkeypatch, case, between, status):
    """The combined audit's V1-01 (2026-10-24): without Saikawa & Shirai's tables the contour's roots waited for the
    band, but the combined mode's theory-band points, nominal grid points, still decided its headline (VIABLE, in the
    report, the saved result and the export). Every band point within 10% of the target (the band of
    ``relic_chi2``), with and without a root on the contour, allowed and excluded."""
    from adroit.parameter_space.likelihood import LikelihoodSettings
    DESIGN['omega'], gs = BAND_CASES[case]
    design['between'] = between
    monkeypatch.setattr(relic, 'eos_folder', lambda: None)
    cuts, combined = v.verdict_pair(_plane(gs), likelihood=LikelihoodSettings())
    band = [c for c in combined.crossings if c.kind == 'theory_band']
    assert len(band) == 4 and combined.level == 'viable_pending' and cuts.level in ('viable_pending', 'pending')
    assert all(c.status == 'pending' and not c.excluded_by for c in combined.crossings + cuts.crossings)
    assert all(any('adroit setup --fetch' in p for p in c.pending) for c in combined.crossings + cuts.crossings)
    assert any("the equation of state's band is not computed" in u for u in combined.unresolved)


@pytest.mark.needs("eos")
def test_with_the_tables_the_theory_band_still_decides_the_combined_view(design):
    """V1-01's control: the tables present (moving nothing here), the band points and the roots stand as judged."""
    from adroit.parameter_space.likelihood import LikelihoodSettings
    DESIGN['omega'], gs = BAND_CASES['roots and band points']
    design['between'] = (5.0, 6.0)
    cuts, combined = v.verdict_pair(_plane(gs), likelihood=LikelihoodSettings())
    assert cuts.level == 'viable' and combined.level == 'viable'
    assert sum(c.kind == 'theory_band' and c.status == 'viable' for c in combined.crossings) == 4


def _coverage(gs: list[float]):
    """The plane of ``_plane(gs)`` and its coverage diagnostic (``coverage.diagnose``, real refinement)."""
    from adroit.parameter_space.coverage import CoverageSettings, diagnose
    scan = _plane(gs)
    return scan, diagnose(scan.request, CoverageSettings(max_evaluations=250))


def _damaged_tables(folder):
    """A tools folder whose three tables are present, none as published."""
    for file, _ in relic.EOS_TABLES.values():
        (folder / file).write_text('a damaged table\n')
    return folder


@pytest.mark.eos_band
@pytest.mark.parametrize('tables', ['missing', 'damaged'])
def test_the_coverage_diagnostics_roots_wait_for_the_tables_as_the_planes_roots_do(design, monkeypatch, tmp_path,
                                                                                   tables):
    """The consistency audit's CA-01 (2026-10-24): Ωh² = 0.115 + 0.08(g − 1)² has no bracket on the coarse plane
    (0.135 at both rows) and two roots, g = 0.75 and 1.25, that the coverage diagnostic finds between its finer rows.
    Those roots carried no cell and were taken for a result written before the band: with the tables missing or
    damaged, the six crossings decided cuts and combined VIABLE (the report, the Studies badge and the export with
    them). Each root now carries its cell, and a decided crossing waits for the tables as a plane root does."""
    from adroit.parameter_space.likelihood import LikelihoodSettings
    DESIGN['omega'] = lambda t, g: 0.115 + 0.08 * (g - 1) ** 2
    design['between'] = (5.0, 6.0)
    scan, coverage = _coverage([0.5, 1.5])
    assert coverage.root_attempts and all(r.converged and r.bracket for r in coverage.root_attempts)
    folder = None if tables == 'missing' else _damaged_tables(tmp_path)
    monkeypatch.setattr(relic, 'eos_folder', lambda: folder)
    why = 'adroit setup --fetch' if tables == 'missing' else 'is not the table as published'
    assert why in relic.eos_unavailable()
    cuts, combined = v.verdict_pair(scan, likelihood=LikelihoodSettings(), coverage=coverage)
    contour = [c for c in cuts.crossings + combined.crossings if c.kind == 'contour']
    assert len(contour) == 2 * len(coverage.root_attempts)
    assert all(c.status == 'pending' and not c.excluded_by for c in cuts.crossings + combined.crossings)
    assert all(any(why in p for p in c.pending) for c in cuts.crossings + combined.crossings)
    assert cuts.level == 'viable_pending' and combined.level == 'viable_pending'


@pytest.mark.eos_band
def test_a_damaged_table_leaves_a_plane_root_and_a_band_point_pending_rather_than_raising(design, monkeypatch, tmp_path):
    """CA-01's second case: with one table not as published, a plane root raised a ValueError while the combined
    mode's band points, which checked only that the folder existed, decided. Both now wait, naming the table."""
    from adroit.parameter_space.likelihood import LikelihoodSettings
    DESIGN['omega'], gs = BAND_CASES['roots and band points']
    design['between'] = (5.0, 6.0)
    monkeypatch.setattr(relic, 'eos_folder', lambda: _damaged_tables(tmp_path))
    cuts, combined = v.verdict_pair(_plane(gs), likelihood=LikelihoodSettings())
    assert cuts.crossings and combined.crossings
    assert all(c.status == 'pending' for c in cuts.crossings + combined.crossings)
    assert all(any('is not the table as published' in p and 'delete it' in p for p in c.pending)
               for c in cuts.crossings + combined.crossings)
    assert combined.level == 'viable_pending'


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_with_the_tables_the_coverage_diagnostics_roots_are_judged_across_the_band(design, monkeypatch):
    """CA-01's control: with the tables, each coverage root is refound in its cell with both tables and judged
    there, as a plane root is; here every table keeps it viable, and the band is noted on each."""
    from adroit.parameter_space.likelihood import LikelihoodSettings
    DESIGN['omega'] = lambda t, g: 0.115 + 0.08 * (g - 1) ** 2 - 0.001 * t
    design['between'] = (5.0, 6.0)
    scan, coverage = _coverage([0.5, 1.5])
    calls = []
    original = v._eos_root
    monkeypatch.setattr(v, '_eos_root', lambda *a, **k: calls.append(a[2]) or original(*a, **k))
    cuts, combined = v.verdict_pair(scan, likelihood=LikelihoodSettings(), coverage=coverage)
    contour = [c for c in cuts.crossings if c.kind == 'contour']
    assert contour and all(c.status == 'viable' for c in contour) and cuts.level == 'viable'
    assert all(any(f.startswith("the equation of state's band: viable also") for f in c.flags) for c in contour)
    assert len(calls) == 2 * 2 * len(contour)                     # both tables, cuts and combined
