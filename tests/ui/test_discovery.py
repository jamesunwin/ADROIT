"""The workbench's constraint discovery (the owner's request, 2026-10-18): the continuation on a personal model with
one scoped consent, the opt-in at approval, a session's page, and the records' Standard and Personal additions views.
No paid call: the job launcher is replaced, and the session is made with the offline fakes."""
from urllib.parse import urlencode

from nicegui import ui
from nicegui.testing import User

from adroit.ui.app import build_pages
from tests.ui.test_model_library import capture, draft, stored


async def test_the_model_page_offers_discovery_with_its_scope_and_a_confirmed_cap(user: User, tmp_path, monkeypatch):
    calls = capture(monkeypatch)
    r = stored()
    build_pages(tmp_path / 'runs')
    await user.open('/models/view?' + urlencode({'reference': r.reference}))
    await user.should_see('Find relevant limits for this model')
    await user.should_see('Network: arXiv and HEPData only')
    user.find(marker='discover').click()
    assert calls == []                                       # no confirmed cap: nothing starts
    user.find('I approve this spend').click()
    user.find(marker='discover').click()
    await user.should_see('Run:')
    assert calls[0][:3] == ['constraints', 'discover', r.reference] and calls[0][calls[0].index('--budget') + 1] == '1'


async def test_reading_figures_is_its_own_choice(user: User, tmp_path, monkeypatch):
    """The live test's item 4: page images of figures are sent only when the researcher ticks "read figures", which
    says what it sends and that its requests are larger."""
    calls = capture(monkeypatch)
    r = stored()
    build_pages(tmp_path / 'runs')
    await user.open('/models/view?' + urlencode({'reference': r.reference}))
    await user.should_see('Read figures')
    user.find('I approve this spend').click()
    user.find(marker='discover').click()
    assert '--vision' not in calls[0]
    await user.open('/models/view?' + urlencode({'reference': r.reference}))
    user.find(marker='figures').click()
    user.find('I approve this spend').click()
    user.find(marker='discover').click()
    assert calls[1][-1] == '--vision'


async def test_approval_can_start_discovery_as_its_own_job(user: User, tmp_path, monkeypatch):
    calls = capture(monkeypatch)
    svc, s, d = draft()
    build_pages(tmp_path / 'runs')
    await user.open('/models/intake?' + urlencode({'session': s.session_id, 'step': d.step_id}))
    user.find('I reviewed the transcription, assumptions, parameters and canonical model').click()
    user.find('Start constraint discovery after saving').click()
    user.find('I approve this spend').click()
    user.find('Save reviewed revision').click()
    await user.should_see('Run:')
    saved = svc.catalog.list()
    assert len(saved) == 1 and calls[0][:3] == ['constraints', 'discover', saved[0].reference]


async def test_records_have_standard_and_personal_views(user: User, tmp_path):
    from adroit.library.experimental import ExperimentalCatalog
    from tests.private_limit_fixtures import fixture
    _, draft_revision = fixture(tmp_path / 'fixture', catalog=ExperimentalCatalog())
    build_pages(tmp_path / 'runs')
    await user.open('/records')
    await user.should_see('Standard')
    await user.should_see('Personal additions')
    await user.should_see('atlas-2301.10731-hinv')
    user.find('Personal additions').click()
    await user.should_see('Synthetic si_isoscalar_curve')
    await user.should_see(draft_revision.reference)


async def test_a_session_page_shows_each_candidates_stage_and_states(user: User, tmp_path, monkeypatch):
    from adroit.agents.llm import FakeLLMClient
    from adroit.core.config import get_settings
    from adroit.orchestrator import constraint_discovery as cd
    from tests.orchestrator.test_constraint_discovery import (TABLE_SHA, HINV, PDF_SHA, Web, _abstracts, _answer, _model,
                                                              _proposals, _resolver)
    monkeypatch.setattr(get_settings(), 'data_dir', tmp_path / 'data')
    service = cd.Discovery(abstracts=_abstracts, fetch=Web(), resolver=_resolver)
    path, _ = _model(tmp_path)
    s = service.start(str(path), cd.Options(budget=1.0))
    service.run(s.session_id, llm=FakeLLMClient([_proposals(), _answer(f'discovery_{HINV[:8]}', TABLE_SHA, PDF_SHA)]))
    build_pages(tmp_path / 'runs')
    await user.open('/constraints/discovery?' + urlencode({'session': s.session_id}))
    await user.should_see('Constraint discovery: my scalar singlet')
    table = user.find(marker='candidates').elements.pop()
    stages = {row['result'].rsplit(' (', 1)[0]: row['stage'] for row in table.rows}
    assert stages == {'Invisible Higgs decays (synthetic)': 'needs your review',
                      'Monojet search (synthetic)': 'not currently supported',
                      'ATLAS invisible Higgs': 'existing result'}
    await user.should_see('Review and verify the draft of Invisible Higgs decays (synthetic)')
    assert isinstance(table, ui.table)
