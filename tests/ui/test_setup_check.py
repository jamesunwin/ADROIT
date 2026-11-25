"""The setup check on the run forms (the owner's plan of 2026-10-18, §B): shown with the reviewed Track 1 setup, and
on demand for Explain a signal and Signal best fits; it launches nothing."""
import pytest
import yaml
from nicegui.testing import User

from adroit.ui.app import build_pages
from tests.ui.test_model_approval import launches, workspace


async def test_the_track1_form_shows_the_check_with_the_reviewed_setup(user: User, tmp_path, monkeypatch):
    root, folder, spec = workspace(tmp_path)
    calls = launches(monkeypatch)
    (root / 'model.yaml').write_text(yaml.safe_dump(spec.model_dump(mode='json')))
    build_pages(root)
    await user.open('/new/track1?model=model.yaml')
    await user.should_see('This analysis will use')
    user.find(marker='setup_check')
    await user.should_see('Duration: duration unknown: no comparable earlier run')
    assert not calls


async def test_explain_a_signal_checks_on_demand(user: User, tmp_path, monkeypatch):
    root, folder, spec = workspace(tmp_path)
    calls = launches(monkeypatch)
    build_pages(root)
    await user.open('/new/single')
    user.find('the model (YAML, with coupling values)').elements.pop().value = yaml.safe_dump(spec.model_dump(mode='json'))
    user.find(marker='check_setup').click()
    await user.should_see('Setup check')
    await user.should_see('background-only simulations')
    assert not calls


@pytest.mark.needs("cresst", "cdmslite", "optimum_interval", "solar_model")   # it launches (OL-06)
async def test_a_slow_setup_check_runs_off_the_page_and_a_stale_answer_is_discarded(user: User, tmp_path, monkeypatch):
    """UO-06's addendum (the auditor's audit of c2f9174): the setup check, shown automatically, had run on the page's event
    loop, freezing it for 78.6 s on a cold generic model. It runs in a worker thread now: the page answers at once
    with "checking the setup…", and an answer computed for inputs since changed is not shown."""
    import asyncio
    import time
    from adroit.ui import wizards
    root, folder, spec = workspace(tmp_path)
    calls = launches(monkeypatch)
    (root / 'model.yaml').write_text(yaml.safe_dump(spec.model_dump(mode='json')))
    real, seen = wizards._track1_check, []

    def slow(root, model, x, y, ratio, token, limits, profile):
        seen.append(x)
        time.sleep(1.5)                                  # a cold domain check, shortened
        return real(root, model, x, y, ratio, token, limits, profile)
    monkeypatch.setattr(wizards, "_track1_check", slow)
    build_pages(root)
    started = time.perf_counter()
    await user.open('/new/track1?model=model.yaml')
    await user.should_see('checking the setup…', retries=20)
    assert time.perf_counter() - started < 1.5                       # the page answered before the check ended
    ticks = []

    async def tick():
        for _ in range(5):
            ticks.append(time.perf_counter())
            await asyncio.sleep(0.05)
    await tick()
    assert max(b - a for a, b in zip(ticks, ticks[1:])) < 0.5        # the event loop is not blocked meanwhile
    await user.should_see('This analysis will use', retries=60)
    # a change during a check: only the newer inputs' answer is shown
    x_axis = user.find('x axis').elements.pop()
    x_axis.value = 'm_chi:20:200:log:3'
    user.find('x axis').trigger('blur')
    await user.should_see('m_chi 20–200 (3 points)', retries=60)
    assert len(seen) >= 2 and seen[-1].startswith('m_chi:20:200')
    user.find(marker='run_model_scan').click()
    await user.should_see('Run: model', retries=50)
    assert len(calls) == 1 and 'm_chi:20:200:log:3' in calls[0][0]


async def test_the_library_pickers_are_filled_off_the_page(user: User, tmp_path, monkeypatch):
    """The auditor's OL-01: the scan panel's "A model from my library" listed the library on the event loop, working out each
    saved model's support (a generic engine's domain: 73 s cold). It is filled in a worker thread after the page."""
    import time
    from nicegui import ui
    from adroit.ui import model_library
    root, folder, spec = workspace(tmp_path)

    def slow(track=''):
        time.sleep(1.5)                                  # a cold domain check, shortened
        return {'catalog:m@r': 'a saved model'}
    monkeypatch.setattr(model_library, 'options', slow)
    build_pages(root)
    started = time.perf_counter()
    await user.open('/new/track1')
    assert time.perf_counter() - started < 1.5                      # the page did not wait for the listing
    picker = next(e for e in user.find(kind=ui.select).elements if e.props.get('label') == 'A model from my library')
    for _ in range(60):
        if picker.options:
            break
        await asyncio_sleep(0.1)
    assert picker.options == {'catalog:m@r': 'a saved model'}


async def asyncio_sleep(seconds: float) -> None:
    import asyncio
    await asyncio.sleep(seconds)


@pytest.mark.needs("cresst", "cdmslite", "optimum_interval", "solar_model")   # it launches (R7-05)
async def test_scan_runs_every_choice_as_it_stood_when_pressed(user: User, tmp_path, monkeypatch):
    """The auditor's OL-03: Scan captured the model and axes, but read the literature box (and the halo, coverage, survey pin
    and batch switch) after its check; a change made during the check entered the run. All are captured at the press."""
    import threading
    from adroit.ui import wizards
    root, folder, spec = workspace(tmp_path)
    calls = launches(monkeypatch)
    (root / 'model.yaml').write_text(yaml.safe_dump(spec.model_dump(mode='json')))
    entered, release, real = threading.Event(), threading.Event(), wizards._ready_to_scan

    def held(*args, **kwargs):
        entered.set()                                    # Scan was pressed and its snapshot taken
        release.wait(10)                                 # the check is still running
        return real(*args, **kwargs)
    monkeypatch.setattr(wizards, '_ready_to_scan', held)
    build_pages(root)
    await user.open('/new/track1?model=model.yaml')
    await user.should_see('Scan setup: active coordinates')
    user.find(marker='run_model_scan').click()
    for _ in range(100):
        if entered.is_set():
            break
        await asyncio_sleep(0.05)
    assert entered.is_set()
    box = user.find('search arXiv for prior work on this model (free; contacts arxiv.org)').elements.pop()
    box.value = True                                     # changed while the check runs
    release.set()
    await user.should_see('Run: model')
    assert len(calls) == 1 and '--literature' not in calls[0][0]


async def _wait(condition, tries: int = 100) -> None:
    import asyncio
    for _ in range(tries):
        if condition():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("the condition was never met")


async def test_an_axis_typed_during_a_pending_preview_is_never_overwritten(user: User, tmp_path, monkeypatch):
    """The auditor's OL-04: a pending preview wrote its axes back over an axis typed without leaving the field. The answer is
    applied only to the inputs it was computed for; otherwise it is computed again, and the typed axis stays."""
    import threading
    from adroit.ui import forms
    root, folder, spec = workspace(tmp_path)
    (root / 'model.yaml').write_text(yaml.safe_dump(spec.model_dump(mode='json')))
    entered, release, real = threading.Event(), threading.Event(), forms.review_scan
    held = {'first': True}

    def review(*args, **kwargs):
        if held.pop('first', False):
            entered.set()
            release.wait(10)                             # the first preview is still being worked out
        return real(*args, **kwargs)
    monkeypatch.setattr(forms, 'review_scan', review)
    build_pages(root)
    await user.open('/new/track1?model=model.yaml')
    await _wait(entered.is_set)
    x_axis = user.find('x axis').elements.pop()
    x_axis.value = 'm_chi:20:200:log:3'                 # typed, the field not left
    release.set()
    await user.should_see('m_chi 20–200 (3 points)')
    assert x_axis.value == 'm_chi:20:200:log:3'


async def test_a_worker_failure_is_named_in_the_card_not_left_pending(user: User, tmp_path, monkeypatch):
    """The auditor's OL-05: an unexpected error from either stage left "working…" or "checking…" for good."""
    from adroit.ui import forms, wizards
    root, folder, spec = workspace(tmp_path)
    calls = launches(monkeypatch)
    (root / 'model.yaml').write_text(yaml.safe_dump(spec.model_dump(mode='json')))

    def broken(*args, **kwargs):
        raise RuntimeError('a worker failed')
    monkeypatch.setattr(forms, 'review_scan', broken)
    build_pages(root)
    await user.open('/new/track1?model=model.yaml')
    await user.should_see('the scan setup could not be worked out: RuntimeError: a worker failed')
    await user.should_not_see('working out the scan setup…')
    monkeypatch.undo()
    calls = launches(monkeypatch)
    monkeypatch.setattr(wizards, '_track1_check', broken)
    build_pages(root)
    await user.open('/new/track1?model=model.yaml')
    await user.should_see('the setup check could not be completed: RuntimeError: a worker failed')
    await user.should_not_see('checking the setup…')
    assert not calls


async def test_an_older_check_released_after_a_newer_one_is_not_shown(user: User, tmp_path, monkeypatch):
    """The auditor's OL-06: the stale-answer test had never held an old answer pending. Two overlapping checks, released
    newest first: the card keeps the newer answer when the older one finally arrives."""
    import threading
    from adroit.ui import wizards
    root, folder, spec = workspace(tmp_path)
    (root / 'model.yaml').write_text(yaml.safe_dump(spec.model_dump(mode='json')))
    from adroit.ui import setup_check as card_module
    gates, entered, results, rendered = [threading.Event(), threading.Event()], [], {}, []
    real, real_render = wizards._track1_check, card_module.render

    def held(*args, **kwargs):
        index = len(entered)
        entered.append(args[2])                          # the x axis it checks
        if index < 2:
            gates[index].wait(10)
        results[index] = real(*args, **kwargs)
        return results[index]
    monkeypatch.setattr(wizards, '_track1_check', held)
    monkeypatch.setattr(card_module, 'render', lambda check: (rendered.append(check), real_render(check))[1])
    build_pages(root)
    await user.open('/new/track1?model=model.yaml')
    await _wait(lambda: len(entered) == 1)
    old = entered[0]
    user.find('x axis').elements.pop().value = 'm_chi:20:200:log:3'
    user.find('x axis').trigger('blur')
    await _wait(lambda: len(entered) == 2)
    gates[1].set()                                       # the newer check finishes first
    await user.should_see('m_chi 20–200 (3 points)')
    gates[0].set()                                       # then the older one
    import asyncio
    await asyncio.sleep(1.0)
    parameter, low, high = old.split(':')[:3]
    await user.should_not_see(f'{parameter} {low}–{high}')
    await user.should_see('m_chi 20–200 (3 points)')
    assert results[0] is not results[1] and not any(c is results[0] for c in rendered)   # the stale answer: never rendered


async def test_a_check_finished_after_an_edit_is_checked_again_not_left_pending(user: User, tmp_path, monkeypatch):
    """The auditor's R7-03: an axis typed (field not left) while the setup check ran left "checking the setup…" after the
    check had finished. The setup is checked again for the inputs now."""
    import threading
    from adroit.ui import wizards
    root, folder, spec = workspace(tmp_path)
    (root / 'model.yaml').write_text(yaml.safe_dump(spec.model_dump(mode='json')))
    entered, release, real, first = threading.Event(), threading.Event(), wizards._track1_check, {'held': True}

    def held(*args, **kwargs):
        if first.pop('held', False):
            entered.set()
            release.wait(10)                             # the first check is still running
        return real(*args, **kwargs)
    monkeypatch.setattr(wizards, '_track1_check', held)
    build_pages(root)
    await user.open('/new/track1?model=model.yaml')
    await _wait(entered.is_set)
    x_axis = user.find('x axis').elements.pop()
    x_axis.value = 'm_chi:20:200:log:3'                 # typed during the check, the field not left
    release.set()
    await user.should_see('m_chi 20–200 (3 points)')
    await user.should_not_see('checking the setup…')
    assert x_axis.value == 'm_chi:20:200:log:3'
