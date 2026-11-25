"""Why a job did not complete and the existing action that recovers it (the owner's workbench plan of 2026-10-18,
part 2 §F); unrecognised text gets no guessed action."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from adroit.orchestrator.recovery import SEEN, attention, diagnose, mark_seen, recent, seen, summary
from adroit.ui import engine


def _job(tmp_path, kind='track1', status='failed', returncode=1, finished=None):
    return engine.Job(title='a run', kind=kind, command=[kind], folder=str(tmp_path), status=status,
                      returncode=returncode, finished=finished or datetime.now().isoformat(timespec='seconds'))


def test_a_budget_stop_offers_the_cap_command_the_log_printed(tmp_path) -> None:
    lines = ['The session cap cannot cover the next request.',
             '- raise the cap (kept in the session and its paid ledger): adroit experiments raise-cap s1 --budget 0.71 --confirmed']
    d = diagnose(_job(tmp_path, 'signal', 'budget_stopped', 3), lines, tmp_path)
    assert d.kind == 'budget' and d.actions[0].target == 'adroit experiments raise-cap s1 --budget 0.71 --confirmed'
    assert 'nothing beyond the cap was sent' in d.summary


def test_a_missing_dependency_names_the_setup_command(tmp_path) -> None:
    lines = ['Traceback (most recent call last):', 'FileNotFoundError: MadGraph5_aMC@NLO is not in the tools folder']
    d = diagnose(_job(tmp_path), lines, tmp_path)
    assert d.kind == 'dependency' and d.actions[0].target == 'uv run adroit setup --only "MadGraph5_aMC@NLO" --fetch'


def test_invalid_input_goes_back_to_the_form(tmp_path) -> None:
    d = diagnose(_job(tmp_path, 'single-idea', returncode=2), ['Error: Invalid value: give a model file'], tmp_path)
    assert d.kind == 'input' and d.actions[0].target == '/new/single' and 'Invalid value' in d.evidence[0]
    (tmp_path / 'result.json').write_text('{}')
    assert diagnose(_job(tmp_path, 'single-idea', returncode=2), ['Error: x'], tmp_path).actions[-1].target == 'reanalyse'


@pytest.mark.parametrize('status, returncode', [('cancelled', -15), ('failed', None)])
def test_an_interrupted_track1_run_with_a_checkpoint_can_resume(tmp_path, status, returncode) -> None:
    assert diagnose(_job(tmp_path, status=status, returncode=returncode), [], tmp_path).actions[0].kind == 'page'
    (tmp_path / '.track1-checkpoint').mkdir()
    (tmp_path / '.track1-checkpoint' / 'manifest.json').write_text('{}')
    d = diagnose(_job(tmp_path, status=status, returncode=returncode), [], tmp_path)
    assert d.kind == 'interrupted' and d.actions[0].kind == 'resume'


def test_an_unrecognised_failure_shows_the_log_and_guesses_nothing_but_its_form(tmp_path) -> None:
    """No recovery is guessed from text it does not recognise; starting over from its own form guesses nothing about
    the cause (the owner, 2026-11-19: a failed run had no way on)."""
    d = diagnose(_job(tmp_path, 'signal'), ['Traceback (most recent call last):', 'ZeroDivisionError: division by zero'],
                 tmp_path)
    assert d.kind == 'failed' and d.evidence[-1] == 'ZeroDivisionError: division by zero'
    assert [(a.kind, a.target) for a in d.actions] == [('page', '/new/track2')]


def test_a_failed_run_of_a_kind_with_no_form_is_offered_nothing(tmp_path) -> None:
    d = diagnose(_job(tmp_path, 'reanalysis'), ['ZeroDivisionError: division by zero'], tmp_path)
    assert d.kind == 'failed' and d.actions == []


def test_the_menu_counts_running_and_recent_attention(tmp_path) -> None:
    import os
    for name, status, finished in (('a', 'running', None), ('b', 'failed', None),
                                   ('c', 'failed', (datetime.now() - timedelta(days=30)).isoformat()),
                                   ('d', 'completed', None)):
        folder = tmp_path / name
        folder.mkdir()
        job = _job(folder, status=status, finished=finished)
        engine.save(job.model_copy(update={'pid': os.getpid() if status == 'running' else 0}))
    assert summary(tmp_path) == {'running': 1, 'attention': 1}
    assert not recent(_job(tmp_path, finished=(datetime.now() - timedelta(days=30)).isoformat()))


# --- what the Activity page has shown is not counted again (the owner, 2026-11-19) ----------------------------------

def _failed(root, name, finished=None):
    folder = root / name
    folder.mkdir()
    engine.save(_job(folder, 'signal', 'failed', 1, finished))
    return folder


def test_what_has_been_seen_is_not_counted_and_what_fails_afterwards_is(tmp_path) -> None:
    _failed(tmp_path, 'a')
    assert summary(tmp_path)['attention'] == 1 and seen(tmp_path) == {}
    mark_seen(tmp_path)
    assert summary(tmp_path)['attention'] == 0
    assert seen(tmp_path) == attention(tmp_path) and len(attention(tmp_path)) == 1      # still listed as needing it
    _failed(tmp_path, 'b')
    assert summary(tmp_path)['attention'] == 1                                          # the new one alone


def test_a_seen_run_that_has_changed_since_is_counted_again(tmp_path) -> None:
    folder = _failed(tmp_path, 'a', (datetime.now() - timedelta(hours=2)).isoformat(timespec='seconds'))
    mark_seen(tmp_path)
    assert summary(tmp_path)['attention'] == 0
    engine.save(_job(folder, 'signal', 'failed', 1))                                    # run again, failed again: now
    assert summary(tmp_path)['attention'] == 1


def test_a_run_record_that_cannot_be_read_is_counted_until_it_is_seen(tmp_path) -> None:
    (tmp_path / 'damaged').mkdir()
    (tmp_path / 'damaged' / engine.JOB).write_text('{}')
    assert summary(tmp_path)['attention'] == 1
    mark_seen(tmp_path)
    assert summary(tmp_path)['attention'] == 0 and list(seen(tmp_path))[0].startswith('record:')


@pytest.mark.parametrize('held', ['', 'not json', '[]', '{"job": 1}', '{"job": null}', '"text"'],
                         ids=['empty', 'not-json', 'a-list', 'a-number', 'null', 'a-string'])
def test_a_seen_record_that_is_damaged_hides_nothing(tmp_path, held) -> None:
    _failed(tmp_path, 'a')
    mark_seen(tmp_path)
    (tmp_path / SEEN).write_text(held)
    assert seen(tmp_path) == {} and summary(tmp_path)['attention'] == 1


def test_a_seen_record_that_cannot_be_opened_hides_nothing(tmp_path) -> None:
    _failed(tmp_path, 'a')
    (tmp_path / SEEN).mkdir()                       # a folder in its place: reading it fails
    assert seen(tmp_path) == {} and summary(tmp_path)['attention'] == 1
    mark_seen(tmp_path)                             # and it cannot be replaced: nothing raised, nothing hidden
    assert summary(tmp_path)['attention'] == 1


def test_marking_as_seen_without_a_runs_folder_writes_nothing(tmp_path) -> None:
    mark_seen(tmp_path / 'absent')
    assert not (tmp_path / 'absent').exists() and summary(tmp_path / 'absent') == {'running': 0, 'attention': 0}


def test_the_seen_record_is_not_read_as_a_run(tmp_path) -> None:
    _failed(tmp_path, 'a')
    mark_seen(tmp_path)
    listed, damaged = engine.listing(tmp_path)
    assert [j.title for j in listed] == ['a run'] and damaged == []
