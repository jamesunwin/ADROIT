"""A constraint survey's page for a researcher who is not building ADROIT (the owner's JU1, item 3, 2026-11-16): what
each result found means and what to do; an unclear result taken in and fetched; resuming within the approved cap; and
proceeding to Constrain a model with the verified limits and the survey's assessment. Offline: the discovery tests'
fakes, and the job launcher replaced."""
from urllib.parse import urlencode

import pytest
from nicegui import ui
from nicegui.testing import User

from adroit.ui.app import build_pages
from tests.ui.test_model_library import capture


@pytest.fixture
def unclear(tmp_path, monkeypatch):
    from adroit.agents.llm import FakeLLMClient
    from adroit.core.config import get_settings
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.orchestrator import constraint_discovery as cd
    from tests.orchestrator.test_constraint_discovery import Web, _abstracts, _model, _proposals, _resolver
    monkeypatch.setattr(get_settings(), 'data_dir', tmp_path / 'data')
    monkeypatch.setattr(get_settings(), 'experimental_library_dir', tmp_path / 'private')
    service = cd.Discovery(ExperimentalCatalog(tmp_path / 'private'), abstracts=_abstracts, fetch=Web(),
                           resolver=_resolver)
    path, _ = _model(tmp_path)
    s = service.start(str(path), cd.Options(budget=1.0))
    service.run(s.session_id, llm=FakeLLMClient([_proposals(uncertain=True)]))
    return service, s.session_id


def _rows(user: User) -> dict:
    table = user.find(marker='candidates').elements.pop()
    return {row['result'].rsplit(' (', 1)[0]: row for row in table.rows}


async def test_each_result_says_what_it_means_and_what_to_do(user: User, tmp_path, unclear) -> None:
    service, session = unclear
    build_pages(tmp_path / 'runs')
    await user.open('/constraints/discovery?' + urlencode({'session': session}))
    rows = _rows(user)
    monojet, hinv = rows['Monojet search (synthetic)'], rows['Invisible Higgs decays (synthetic)']
    assert monojet['status'] == 'not currently supported' and monojet['meaning'].startswith('Not currently supported')
    assert 'proceed without it' in monojet['next']
    assert hinv['status'] == 'unclear whether it applies' and 'fetch its paper and draft its record' in hinv['next']
    assert all('needs_new_machinery' not in str(row) for row in rows.values())
    assert not [e for e in user.client.layout.descendants() if isinstance(e, ui.code)]   # no raw JSON ("[]")
    await user.should_see(marker='proceed_panel')


async def test_an_unclear_result_is_taken_in_then_fetched_by_resuming(user: User, tmp_path, unclear,
                                                                    monkeypatch) -> None:
    from tests.orchestrator.test_constraint_discovery import HINV
    service, session = unclear
    calls = capture(monkeypatch)
    build_pages(tmp_path / 'runs')
    await user.open('/constraints/discovery?' + urlencode({'session': session}))
    user.find(marker='include').click()
    await user.should_see('give your name')                      # a decision carries who made it
    assert service.decisions(session) == []
    user.find(marker='researcher').elements.pop().value = 'a researcher'
    user.find(marker='include').click()
    await user.should_see(marker='fetch_panel')
    assert [d.kind for d in service.decisions(session)] == ['included']
    assert next(c for c in service.candidates(session) if c.candidate_id == HINV).category == 'missing_supported'
    await user.open('/constraints/discovery?' + urlencode({'session': session}))
    user.find(marker='resume').click()
    await user.should_see('approve the resumption first')
    assert calls == []
    user.find(marker='approve_resume').click()
    user.find(marker='resume').click()
    await user.should_see('Run:')
    assert calls[0][:5] == ['constraints', 'resume', session, '--budget', '1']


async def test_proceeding_opens_constrain_a_model_with_the_model_and_the_surveys_assessment(user: User, tmp_path,
                                                                                         unclear) -> None:
    service, session = unclear
    build_pages(tmp_path / 'runs')
    await user.open('/constraints/discovery?' + urlencode({'session': session}))
    user.find(marker='proceed').click()
    await user.should_see('Constrain a model')
    await user.should_see(marker='survey_pin')                   # the finished survey's assessment, pinned
    pin = user.find(marker='survey_pin').elements.pop()
    assert pin.value is True and session in pin.text


def test_proceeding_carries_a_library_model_its_limits_and_the_pin() -> None:
    from urllib.parse import parse_qs, urlsplit
    from adroit.ui.discovery import proceed_target
    url = urlsplit(proceed_target('catalog:m@r', ['private-limit:a', 'private-limit:b'], 'discovery:s@h'))
    assert url.path == '/new/track1' and parse_qs(url.query) == {
        'catalog': ['catalog:m@r'], 'limits': ['private-limit:a,private-limit:b'], 'discovery': ['discovery:s@h']}
    assert 'catalog' not in parse_qs(urlsplit(proceed_target('file:' + '0' * 64, [], 'discovery:s@h')).query)


def test_a_track1_command_carries_the_pinned_assessment() -> None:
    from pathlib import Path
    from adroit.ui import forms
    command = forms.track1_command(Path('m.yaml'), Path('out'), discovery='discovery:abc@' + '0' * 64)
    assert command[command.index('--discovery') + 1] == 'discovery:abc@' + '0' * 64
    assert '--discovery' not in forms.track1_command(Path('m.yaml'), Path('out'))
