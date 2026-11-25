"""A comparison that is not a finite number decides nothing (the consistency audit's CA-03, 2026-10-24): a nan ratio
beside an excluding one made the combined likelihood nan, nan > 2.71 read False, and the point, then the headline,
viable; a constraint's own "excluded" read from such a value (nan > 1) said allowed."""
import importlib
import math

import pytest

from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.likelihood import LikelihoodSettings
from adroit.parameter_space.scan import PointResult

v = importlib.import_module('adroit.parameter_space.verdict')


def _row(p: Point, bad: float, failed_excluded: bool = False, chi2: dict | None = None) -> PointResult:
    """A point excluded by 'known' (ratio 2) whose other comparison, 'failed', gave ``bad``."""
    return PointResult(point=p, omega_h2=.006 * p.m_chi, dd_kind='SI', dd_limit_cm2=1, dd_sigma_cm2=0, model_pending=[],
                       excluded={'known': True, 'failed': failed_excluded}, ratios={'known': 2, 'failed': bad},
                       chi2=chi2 or {})


@pytest.mark.parametrize('bad', [math.nan, math.inf, -math.inf, -2.0])
@pytest.mark.parametrize('likelihood', [None, LikelihoodSettings()], ids=['cuts', 'combined'])
def test_an_invalid_comparison_is_pending_and_the_finite_exclusion_stands(bad, likelihood):
    c = v.classify(Spin1Class(), _row(Point(m_chi=20, m_med=60), bad), likelihood)
    assert c.status == 'excluded' and any(p.startswith('failed: its comparison gave') for p in c.pending)
    if likelihood is not None:
        assert c.r_combined == pytest.approx(2.0) and 'without failed' in c.excluded_by[-1]


@pytest.mark.parametrize('likelihood', [None, LikelihoodSettings()], ids=['cuts', 'combined'])
def test_alone_an_invalid_comparison_leaves_the_point_pending_not_viable(likelihood):
    row = _row(Point(m_chi=20, m_med=60), math.nan).model_copy(update={
        'excluded': {'failed': False}, 'ratios': {'failed': math.nan}})
    c = v.classify(Spin1Class(), row, likelihood)
    assert c.status == 'pending' and not c.excluded_by


def test_a_measurement_left_out_can_be_negative_so_the_rest_decides_nothing():
    """A Δχ² can lower q: without it, the limits' q is no lower bound."""
    row = _row(Point(m_chi=20, m_med=60), 0.5, chi2={'g-2': math.nan})
    c = v.classify(Spin1Class(), row, LikelihoodSettings())
    assert c.status == 'pending' and not c.excluded_by and any(p.startswith('g-2:') for p in c.pending)


def test_zero_is_a_valid_ratio():
    c = v.classify(Spin1Class(), _row(Point(m_chi=20, m_med=60), 0.0), LikelihoodSettings())
    assert c.status == 'excluded' and not any('its comparison gave' in p for p in c.pending)


@pytest.mark.needs("eos")              # without the tables the band is unresolved and the headline pending
def test_the_headline_is_not_made_viable_by_a_nan(monkeypatch):
    """The audit's control: every root excluded by 'known' with 'failed' nan; combined read viable."""
    import runpy
    from pathlib import Path
    h = runpy.run_path(str(Path(__file__).with_name('test_eos_verdict.py')))
    monkeypatch.setattr(Spin1Class, 'omega_h2', lambda self, p: .006 * p.m_chi)
    monkeypatch.setattr(v, 'evaluate', lambda cls, p, *a: _row(p, math.nan))
    monkeypatch.setattr('adroit.parameter_space.searches.prefetch_lhc', lambda c, p, *a: [None] * len(p))
    monkeypatch.setattr(v, '_eos_checked', lambda result, root, c, *args: (c, v.Check(
        name='eos_band', state='not_applicable')))     # the band's judgements counted apart
    cuts, combined = v.verdict_pair(h['_grid'](), likelihood=LikelihoodSettings())
    assert cuts.level == 'excluded' and combined.level == 'excluded'
    assert all(c.status == 'excluded' for c in combined.crossings if c.kind == 'contour')


@pytest.mark.parametrize('likelihood', [None, LikelihoodSettings()], ids=['cuts', 'combined'])
def test_at_a_halo_sample_a_nan_ratio_is_undecided_not_allowed(likelihood):
    """The same at each sample of the halo region (``verdict._sample_status``): direct detection's ratio nan at one
    halo, its "excluded" False there, read as allowed at that halo."""
    from adroit.parameter_space.halo_region import HaloEvaluation, HaloOutcome, HaloPointSample
    p = Point(m_chi=20, m_med=60)

    def sample(ratio):
        return HaloPointSample(v0_km_s=233, v_esc_km_s=528, rho_gev_cm3=.4, where='centre', outcomes={
            'direct detection': HaloOutcome(excluded=bool(ratio > 1), ratio=ratio, confidence_level=.95,
                                            sidedness='one-sided')})
    row = PointResult(point=p, omega_h2=.12, dd_kind='SI', dd_limit_cm2=1, dd_sigma_cm2=.5, dd_ratio=.5,
                      model_pending=[], excluded={'direct detection': False}, ratios={'direct detection': .5},
                      ratio_confidence_levels={'direct detection': .95}, ratio_sidedness={'direct detection': 'one-sided'},
                      halo=HaloEvaluation(region='test', samples=[sample(.5), sample(math.nan)]))
    status, excluded, pending = v._sample_status(row, row.halo.samples[1], [], [], likelihood)
    assert status == 'pending' and not excluded and any('direct detection: its comparison gave nan' in x for x in pending)
    assert v._sample_status(row, row.halo.samples[0], [], [], likelihood)[0] == 'viable'
    assert v.classify(Spin1Class(), row, likelihood).status == 'pending'
