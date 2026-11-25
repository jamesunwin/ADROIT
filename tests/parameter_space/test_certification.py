"""One certification of each decisive claim (the consolidation plan's M1, 2026-10-25; ``core.certificate``,
``parameter_space.certification``): the plane's roots and band points carry a certificate, the gate leaves a claim
with a failed or unknown check pending while keeping what its computed constraints gave, the headline rests on
certified claims (D-2), band points are checked across the equation of state's band (D-1), and a conclusion says
whether it depends on an unverified record (D-4)."""
import importlib
import runpy
from pathlib import Path

import pytest

from adroit.constraints import relic
from adroit.core.certificate import LEGACY, POLICY, Certificate, Check, reading
from adroit.parameter_space.classes import Spin1Class
from adroit.parameter_space.likelihood import LikelihoodSettings
from adroit.parameter_space.scan import PointResult
from tests.unsigned_records import used

v = importlib.import_module('adroit.parameter_space.verdict')
H = runpy.run_path(str(Path(__file__).with_name('test_eos_verdict.py')))


@pytest.fixture
def plane(monkeypatch):
    """``test_eos_verdict``'s design plane: Ωh²(t, g) for the nominal (t = 0) and the two tables (±1), a toy
    exclusion between two couplings, and the records evaluation says it used."""
    monkeypatch.setattr(Spin1Class, 'omega_h2', lambda self, p: H['_toy_density'](p))
    monkeypatch.setattr('adroit.parameter_space.searches.prefetch_lhc', lambda cls, pts, *a: [None] * len(pts))
    setup = {'between': (5.0, 6.0), 'used': []}

    def evaluate(cls, p, *args):
        return PointResult(point=p, omega_h2=H['_toy_density'](p), dd_kind='SI', dd_sigma_cm2=0, dd_limit_cm2=1,
                           excluded={'toy': setup['between'][0] < p.g_chi < setup['between'][1],
                                     'colliders (CMS)': False}, unverified_records=list(setup['used']),
                           records={r: v for rid in setup['used'] for r, v in used(rid).items()})
    monkeypatch.setattr(v, 'evaluate', evaluate)
    return setup


def test_a_certificate_reads_legacy_stale_certified_or_open():
    assert reading(None) == LEGACY
    ok = Certificate(claim_kind='thermal_solution', scope='x', checks=[Check(name='root', state='satisfied')],
                     policy=POLICY)
    assert ok.decided and reading(ok) == 'certified'
    assert reading(ok.model_copy(update={'policy': 'an-earlier-policy'})).startswith('stale')
    waiting = ok.model_copy(update={'checks': [Check(name='eos_band', state='unknown', reason='tables missing')]})
    assert not waiting.decided and reading(waiting) == 'not certified: tables missing'
    assert ok.policy == POLICY


def test_an_old_crossing_has_no_certificate_and_its_json_is_unchanged():
    """An old result reads "legacy, not assessed", its saved JSON (and so its evidence hash) unchanged."""
    old = {'point': {'m_chi': 20.0, 'm_med': 60.0, 'g_chi': 0.1, 'g_q': 0.25, 'g_l': 0.0}, 'status': 'viable'}
    c = v.Crossing.model_validate(old)
    assert c.certificate is None and reading(c.certificate) == LEGACY
    assert 'certificate' not in c.model_dump(mode='json')


@pytest.mark.eos_band
def test_every_contour_root_and_band_point_carries_its_claims_certificate(plane, monkeypatch):
    monkeypatch.setattr(relic, 'eos_folder', lambda: None)
    H['DESIGN']['omega'], gs = H['BAND_CASES']['roots and band points']
    cuts, combined = v.verdict_pair(H['_plane'](gs), likelihood=LikelihoodSettings())
    kinds = {c.kind: c.certificate.claim_kind for c in combined.crossings}
    assert kinds == {'contour': 'thermal_solution', 'theory_band': 'theory_band_membership'}
    for c in cuts.crossings + combined.crossings:
        names = [x.name for x in c.certificate.checks]
        assert names[-5:] == ['thermal_history', 'finite_comparisons', 'records', 'discovery', 'halo']
        assert c.certificate.check('eos_band').state == 'unknown' and c.status == 'pending'
        assert c.certificate.computed_status == 'viable'


@pytest.mark.eos_band
def test_waiting_points_all_excluded_by_their_constraints_read_pending_not_viable_pending(plane, monkeypatch):
    """D-2: without the tables every decided point waits; where every one is excluded by its computed constraints
    the headline is "pending", the exclusions kept in each certificate; one surviving point makes it "viable,
    pending"."""
    monkeypatch.setattr(relic, 'eos_folder', lambda: None)
    H['DESIGN']['omega'], gs = H['BAND_CASES']['roots and band points']
    plane['between'] = (0.0, 10.0)                      # every point excluded, the grid's rows too
    scan = H['_plane'](gs)
    scan = scan.model_copy(update={'points': [r.model_copy(update={'excluded': {'toy': True, 'colliders (CMS)': False}})
                                              for r in scan.points]})
    cuts, combined = v.verdict_pair(scan, likelihood=LikelihoodSettings())
    for view in (cuts, combined):
        assert view.level == 'pending' and 'excluded by its computed constraints' in view.summary
        assert all(c.certificate.computed_status == 'excluded' and c.certificate.computed_excluded_by == ['toy']
                   for c in view.crossings)
    plane['between'] = (5.0, 6.0)                       # none excluded
    cuts, combined = v.verdict_pair(H['_plane'](gs), likelihood=LikelihoodSettings())
    assert cuts.level == combined.level == 'viable_pending'
    assert combined.support and all('(computed: viable)' in s for s in combined.support)


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_band_point_that_a_table_moves_out_of_the_relic_band_waits(plane):
    """D-1: Ωh² = 0.12(1 + 0.3t)/g² keeps the contour's roots on target only at the nominal; a band point at g = 1.02
    (Ωh² = 0.115) is inside the band nominally (χ²_Ω < 3.84 with the 10% theory uncertainty) and outside it with the
    upper table (0.150). The table check is at the point's own parameters; the band point waits, EOS-sensitive."""
    H['DESIGN']['omega'] = lambda t, g: 0.12 * (1 + 0.3 * t) / g ** 2
    cuts, combined = v.verdict_pair(H['_plane']([0.98, 1.02]), likelihood=LikelihoodSettings())
    band = [c for c in combined.crossings if c.kind == 'theory_band']
    assert band and all(c.status == 'pending' for c in band)
    check = band[0].certificate.check('eos_band')
    assert check.state == 'failed' and 'outside it with the upper' in check.reason
    assert band[0].certificate.bound.eos_tables and all(band[0].certificate.bound.eos_tables.values())


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_band_point_inside_the_band_with_every_table_stands(plane):
    H['DESIGN']['omega'] = lambda t, g: 0.12 * (1 + 0.01 * t) / g ** 2
    cuts, combined = v.verdict_pair(H['_plane']([0.98, 1.02]), likelihood=LikelihoodSettings())
    band = [c for c in combined.crossings if c.kind == 'theory_band']
    assert band and all(c.status == 'viable' and c.certificate.decided for c in band)
    assert 'inside the relic band with Saikawa & Shirai' in band[0].certificate.check('eos_band').reason


def test_an_excluded_root_from_an_unsupported_thermal_history_is_not_certified(plane, monkeypatch):
    """The gate on A06: an exclusion at a root whose Ωh² rests on an unsupported history is an exclusion of that
    point, not of a certified thermal solution; it waits, its computed exclusion kept."""
    monkeypatch.setattr(relic, 'eos_folder', lambda: None)
    H['DESIGN']['omega'], gs = H['BAND_CASES']['roots and band points']
    original = v.evaluate
    monkeypatch.setattr(v, 'evaluate', lambda cls, p, *a: original(cls, p, *a).model_copy(update={
        'excluded': {'toy': True}, 'relic_validity': ['Ωh² moves by 62% with the neutrinos decoupled']}))
    cuts = v.verdict_pair(H['_plane'](gs))[0]
    root = cuts.crossings[0]
    assert root.status == 'pending' and root.certificate.check('thermal_history').state == 'failed'
    assert root.certificate.computed_status == 'excluded'


@pytest.mark.parametrize('enabled, used, words', [
    (False, [], None), (True, [], 'unverified records enabled for this run (this conclusion uses none)'),
    (True, ['dampe-2112.08860-lines'], 'this conclusion depends on unverified records: dampe-2112.08860-lines')])
def test_a_conclusion_says_whether_it_depends_on_an_unverified_record(plane, monkeypatch, enabled, used, words):
    """D-4: the run's setting ("unverified records enabled") apart from the conclusion's dependence ("depends on an
    unverified record"), on the headline and on each claim it rests on."""
    H['DESIGN']['omega'], gs = H['BAND_CASES']['roots and band points']
    monkeypatch.setattr(v, '_eos_checked', lambda result, root, c, *a: (c, Check(name='eos_band', state='satisfied')))
    plane['used'] = used
    scan = H['_plane'](gs)
    scan = scan.model_copy(update={'request': scan.request.model_copy(update={'unverified_records': enabled})})
    cuts = v.verdict_pair(scan)[0]
    assert cuts.level == 'viable'
    if words is None:
        assert not cuts.qualifiers and 'unverified' not in cuts.summary
    else:
        assert cuts.qualifiers == [words] and words in cuts.summary
    assert all(c.certificate.bound.unverified_records == used for c in cuts.crossings)


def test_the_record_gate_notes_each_unverified_record_it_admits():
    from adroit.constraints import database
    from adroit.constraints.searches import admits, unverified_used
    waiting = database.record('dampe-2112.08860-lines').model_copy(update={'verified_on': None, 'verified_by': ''})
    with unverified_used() as used:
        assert not admits(waiting, False) and not used
        assert admits(waiting, True) and used == {'dampe-2112.08860-lines'}
    assert admits(waiting, True)                       # outside a collection nothing is noted, nothing fails
