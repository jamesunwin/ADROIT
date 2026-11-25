"""The owner's JU1, item 3 (2026-11-16): a constraint survey's page had stopped at a table of needed limits. An unclear
result ADROIT can calculate is now taken in by the researcher ("included"), fetched and drafted at the next run like
any supported missing result; a result with no calculation is "not currently supported" and is not fetched. Offline:
the fake network, resolver and language model of the discovery tests."""
import pytest

from adroit.agents.llm import FakeLLMClient
from adroit.core.config import get_settings
from adroit.orchestrator import constraint_discovery as cd
from tests.orchestrator.test_constraint_discovery import (HINV, OTHER, PDF_SHA, TABLE_SHA, Web, _abstracts, _answer,
                                                          _key, _model, _proposals, _resolver)

MONOJET = _key('Monojet search (synthetic)', f'arXiv:{OTHER}')


@pytest.fixture
def unclear(tmp_path, monkeypatch):
    """A survey whose invisible-Higgs result came back unclear (the relevance step was unsure of it)."""
    from adroit.library.experimental import ExperimentalCatalog
    monkeypatch.setattr(get_settings(), 'data_dir', tmp_path / 'data')
    monkeypatch.setattr(get_settings(), 'experimental_library_dir', tmp_path / 'private')   # this test's own
    service = cd.Discovery(ExperimentalCatalog(tmp_path / 'private'), abstracts=_abstracts, fetch=Web(),
                           resolver=_resolver)
    path, _ = _model(tmp_path)
    s = service.start(str(path), cd.Options(budget=1.0))
    service.run(s.session_id, llm=FakeLLMClient([_proposals(uncertain=True)]))
    return service, s.session_id


def test_an_unclear_result_is_shown_as_such_and_an_unsupported_one_as_not_currently_supported(unclear) -> None:
    service, session = unclear
    found = {c.candidate_id: c for c in service.candidates(session)}
    assert found[HINV].category == 'uncertain' and service.stage(found[HINV]) == 'unclear whether it applies'
    assert found[MONOJET].category == 'needs_new_machinery'
    assert service.stage(found[MONOJET]) == 'not currently supported'
    assert found[HINV].acquisition.status == 'not_attempted'           # an unclear result is not fetched by itself
    assert service.includable(session) == {HINV}                     # ADROIT has the invisible-Higgs calculation


def test_an_included_result_is_fetched_and_drafted_at_the_next_run(unclear) -> None:
    service, session = unclear
    decision = service.include(session, HINV, 'it bounds our scalar below m_h/2', 'a researcher')
    assert decision.kind == 'included' and service.decisions(session)[-1] == decision
    found = {c.candidate_id: c for c in service.candidates(session)}
    assert (found[HINV].category, found[HINV].adapter) == ('missing_supported', 'sm_higgs_invisible')
    assert {k: v['status'] for k, v in service._read(session, 'state.json').items()
            if k in ('acquisition', 'extraction', 'packets')} == dict.fromkeys(('acquisition', 'extraction',
                                                                              'packets'), 'pending')
    service.run(session, llm=FakeLLMClient([_answer(f'discovery_{HINV[:8]}', TABLE_SHA, PDF_SHA)]))
    found = {c.candidate_id: c for c in service.candidates(session)}
    assert found[HINV].acquisition.status == 'retrieved' and found[HINV].draft
    assert service.stage(found[HINV]) == 'needs your review'
    assert {k: v['status'] for k, v in service._read(session, 'state.json').items()} == dict.fromkeys(
        cd.STAGE_ORDER, 'done')


def test_an_inclusion_survives_a_reassessment(unclear) -> None:
    service, session = unclear
    service.include(session, HINV, 'it applies', 'a researcher')
    service._stage(session, 'assessment', 'pending')                  # the assessment runs again (a resume)
    service._assess(service.session(session))
    found = {c.candidate_id: c for c in service.candidates(session)}
    assert (found[HINV].category, found[HINV].adapter) == ('missing_supported', 'sm_higgs_invisible')


def test_only_an_unclear_result_with_a_calculation_is_included(unclear) -> None:
    service, session = unclear
    with pytest.raises(ValueError, match='only a result whose relevance is unclear'):
        service.include(session, MONOJET, 'it applies', 'a researcher')
    with pytest.raises(ValueError, match='no such candidate'):
        service.include(session, 'nothing', 'it applies', 'a researcher')
    s = service.session(session)
    monojet = next(c for c in service.candidates(session) if c.candidate_id == MONOJET)
    assert service._adapter(s, monojet.model_copy(update={'category': 'uncertain'})) == ''   # no calculation
    assert service.decisions(session) == []
