"""The setup check before a run (the owner's workbench plan, 2026-10-18, §B): blocking items with their fixes, what
may stay pending, a missing data set on a fresh machine, the estimate's basis, and no network or launch."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from adroit.core.model_spec import ModelSpec
from adroit.orchestrator import setup_check as sc

DOCS = Path(__file__).resolve().parents[2] / 'docs'


def _spec(name: str = 'dm13/axial_mediator.yaml') -> ModelSpec:
    data = yaml.safe_load((DOCS / name).read_text())
    return ModelSpec.model_validate(data.get('spec', data))


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import requests
    def refuse(*a, **k):
        raise AssertionError('the setup check must not use the network')
    monkeypatch.setattr(requests, 'get', refuse)


def test_a_reviewed_complete_model_is_ready_and_an_unreviewed_one_is_blocked(tmp_path) -> None:
    spec = _spec()
    first = sc.check_track1(spec, 'm_med:10:10000:log:4', 'm_chi:1:2000:log:3', root=tmp_path)
    assert first.blocked and any('not the one shown' in i.message for i in first.items)
    again = sc.check_track1(spec, 'm_med:10:10000:log:4', 'm_chi:1:2000:log:3', reviewed=first.review_token,
                            root=tmp_path)
    assert not any('not the one shown' in i.message for i in again.items) and again.points == 12
    assert any(i.section == 'uses' and i.message.startswith('scanned: m_med') for i in again.items)


def test_a_missing_mass_blocks_with_its_fix(tmp_path) -> None:
    spec = _spec()
    blank = spec.model_copy(update={'fields': [f.model_copy(update={'mass_gev': None}) if f.role.value == 'mediator'
                                               else f for f in spec.fields]})
    check = sc.check_track1(blank, root=tmp_path)
    item = next(i for i in check.items if i.message.endswith('has no value'))
    assert item.severity == 'blocking' and 'Refine' in item.fix


def test_a_fresh_machine_lacks_the_data_sets_and_says_how_to_fetch_them(tmp_path) -> None:
    items = sc.machine_items(['direct detection', 'dark photon searches', 'something new'], tools_dir=tmp_path / 'tools')
    missing = [i for i in items if i.section == 'missing']
    assert missing and all(i.fix.startswith('uv run adroit setup --only') for i in missing)
    assert any(i.severity == 'blocking' for i in missing)                     # a required data set
    assert any(i.severity == 'pending' and 'DarkCast' in i.message for i in missing)   # an optional one
    assert any('not checked here' in i.message for i in items)


def test_the_estimate_needs_a_comparable_earlier_run(tmp_path) -> None:
    from adroit.orchestrator import studies
    assert sc.estimate('track1', 'axial', 100, tmp_path) == (None, 'duration unknown: no comparable earlier run')
    folder = tmp_path / 'earlier'
    folder.mkdir()
    (folder / 'result.json').write_text(json.dumps({'class_name': 'axial', 'scan': {'points': [{}] * 50}}))
    studies.record(folder, 'track1', 'earlier')
    s = studies.load(folder).model_copy(update={'folder': '.', 'calculation_started_at': '2026-10-18T10:00:00+00:00',
                                                'calculation_completed_at': '2026-10-18T10:05:00+00:00'})
    (folder / studies.FILE).write_text(s.model_dump_json())
    seconds, basis = sc.estimate('track1', 'axial', 100, tmp_path)
    assert seconds == pytest.approx(600) and 'median rate of 1 earlier track1 run' in basis


def test_explain_a_signal_and_signal_best_fits_have_their_checks(tmp_path) -> None:
    single = sc.check_single(_spec(), 'LZ extended window (2026)', [10, 20, 50], 2000, 4, tools_dir=tmp_path / 'tools')
    assert single.fits == 3 and single.toys == 2000 and single.points == 16
    assert any('LZ extended window (arXiv:2609.02823)' in i.message for i in single.items)
    assert sc.check_signal('', 0, 1000).blocked
    from adroit.experiments import anomaly
    path = tmp_path / 'anomaly.yaml'                     # resolved as the run resolves it (WA-01): a real file
    path.write_text(anomaly.template())
    record = sc.check_signal(f'record:{path}', 1, 1000)
    assert not record.blocked and any('confirmed by a person' in i.message for i in record.items)
