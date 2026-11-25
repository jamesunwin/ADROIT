"""The fresh audit's discovery counterexamples (the independent audit of 2026-10-19 (fresh), F19-01–F19-04), as regressions:
synthetic metadata only, no verification, no provider call."""
import pytest
import yaml

from adroit.agents.constraint_discovery import DiscoveryProposal
from adroit.constraints.scouting import Vetted
from adroit.core.constraint_discovery import Candidate, DiscoveryCoverage, InventoryEntry, Requirement, ResultIdentity
from adroit.library.experimental import ExperimentalCatalog
from adroit.orchestrator import constraint_discovery as cd
from adroit.retrieval.references import Reference

HINV = ResultIdentity(quantity='BR(h invisible)', selection='observed', confidence_level=0.95)


@pytest.fixture
def session(tmp_path):
    from adroit.parameter_space.library import entry
    path = tmp_path / 'model.yaml'
    path.write_text(yaml.safe_dump(entry('higgs_portal_scalar').spec().model_dump(mode='json')))
    service = cd.Discovery(ExperimentalCatalog(tmp_path / 'catalog'))
    s = service.start(str(path), cd.Options(budget=0, domain={'m_chi': (10, 60)}))
    for stage in cd.STAGE_ORDER:
        service._stage(s.session_id, stage, 'done')
    return service, s


def _proposal(**changes):
    p = DiscoveryProposal(name='distinct VBF-only invisible Higgs panel', constraint_class='collider',
                          reference='2501.00001', title='Synthetic paper', applicability='applies',
                          bound='BR(h invisible) at 95% CL', domain={'m_chi': (10, 60)},
                          result=HINV.model_copy(update={'channel': 'VBF'}))
    p = DiscoveryProposal.model_validate({**p.model_dump(), **changes})
    return p, Vetted(proposal=p, reference=Reference(kind='arxiv', id=p.reference, title=p.title, verified=True),
                     kept=True)


def _record(service, s, inventory, p, v, selected=()):
    service._write(s.session_id, 'inventory.json', [e.model_dump(mode='json') for e in inventory])
    found = cd.categorise(p, v, inventory, s.domain)
    service._save_candidates(s.session_id, [Candidate(
        candidate_id='test', name=p.name, constraint_class=p.constraint_class.value, reference='arXiv:' + p.reference,
        title=p.title, applicability=p.applicability, domain=p.domain, held_as=p.held_as, result=p.result, **found)])
    coverage = service.coverage(s.session_id)
    return found, coverage


COMBINED = InventoryEntry(reference='record:combined', kind='standard_record', library='standard',
                          title='Combined rather than VBF-only panel', source_ids=['arxiv:2501.00001'],
                          constraint_class='collider', result=HINV.model_copy(update={'channel': 'combination of VBF and ggF'}))
PRIVATE = InventoryEntry(reference='private-limit:' + '1' * 64, kind='personal_limit', library='personal',
                         title='a Higgs bound', source_ids=['arxiv:2501.00001'], adapter='sm_higgs_invisible',
                         result=HINV.model_copy(update={'channel': 'VBF'}))


def test_a_distinct_panel_of_the_same_paper_is_not_covered(session):
    """F19-01 same_paper_distinct_panel: a VBF-only result named as the combined record is still not covered: its
    channel is a constituent of the combination."""
    service, s = session
    p, v = _proposal(held_as='record:combined')
    found, coverage = _record(service, s, [COMBINED], p, v)
    assert found['category'] != 'existing_applicable' and 'another channel' in found['missing']
    assert cd.requirements_at(coverage, 15, [])


def test_a_result_needing_a_calculation_is_not_resolved_by_a_binding_of_its_paper(session):
    """F19-01 personal_needs_calculation_selected: selecting a same-paper binding does not clear a result that needs
    a missing recast."""
    service, s = session
    p, v = _proposal(applicability='needs_calculation', needed_calculation='a distinct missing recast',
                     held_as=PRIVATE.reference)
    found, coverage = _record(service, s, [PRIVATE], p, v)
    assert found['category'] == 'needs_new_machinery' and not found.get('resolvers')
    assert cd.requirements_at(coverage, 15, [PRIVATE.reference])


def test_another_adapters_binding_never_resolves_a_requirement(session):
    """F19-02 wrong_adapter_selected: a Higgs requirement is not resolved by selecting an SI binding of the same
    paper; only the binding shown to be the result resolves it."""
    service, s = session
    si = PRIVATE.model_copy(update={'reference': 'private-limit:' + '2' * 64, 'adapter': 'si_isoscalar_curve',
                                    'result': ResultIdentity(quantity='spin-independent cross section',
                                                             selection='observed', confidence_level=0.9)})
    p, v = _proposal(held_as=PRIVATE.reference)
    found, coverage = _record(service, s, [PRIVATE, si], p, v)
    assert found['resolvers'] == [PRIVATE.reference] and set(found['matches']) == {PRIVATE.reference, si.reference}
    assert cd.requirements_at(coverage, 15, [si.reference])                 # the other adapter's: still pending
    assert not cd.requirements_at(coverage, 15, [PRIVATE.reference])        # the result's own binding: resolved


def test_disjoint_bindings_leave_their_gap_and_each_others_range_pending(session):
    """F19-02 disjoint-domain control: bindings over 10–20 and 40–60 GeV, only the first selected: 30 GeV (the gap)
    and 50 GeV (only the unselected binding covers it) stay pending; 15 GeV is resolved."""
    service, s = session
    a = PRIVATE.model_copy(update={'domain': {'mass_range': [10, 20]}})
    b = PRIVATE.model_copy(update={'reference': 'private-limit:' + '3' * 64, 'domain': {'mass_range': [40, 60]}})
    p, v = _proposal(held_as=a.reference)
    service._write(s.session_id, 'inventory.json', [e.model_dump(mode='json') for e in (a, b)])
    found = cd.categorise(p, v, [a, b], s.domain)
    service._save_candidates(s.session_id, [Candidate(
        candidate_id='test', name=p.name, constraint_class='collider', reference='arXiv:' + p.reference, title=p.title,
        applicability=p.applicability, domain=p.domain, held_as=p.held_as, result=p.result,
        **{**found, 'resolvers': [a.reference, b.reference]})])
    coverage = service.coverage(s.session_id)
    assert not cd.requirements_at(coverage, 15, [a.reference])
    assert cd.requirements_at(coverage, 30, [a.reference]) and cd.requirements_at(coverage, 50, [a.reference])
    assert not cd.requirements_at(coverage, 50, [a.reference, b.reference])


def test_an_unrelated_supersession_mark_is_rejected_and_the_result_stays_required(session):
    """F19-03 unrelated_supersession: an invisible-Higgs result marked as superseded by a gamma-ray-line record keeps
    its category and stays a requirement."""
    service, s = session
    gamma = InventoryEntry(reference='record:gamma', kind='standard_record', library='standard', title='Gamma rays',
                           source_ids=['arxiv:2601.00002'], constraint_class='indirect_detection',
                           result=ResultIdentity(quantity='gamma ray line cross section', selection='observed',
                                                 confidence_level=0.95))
    c = Candidate(candidate_id='test', name='an invisible Higgs bound', constraint_class='collider',
                  reference='arXiv:2501.00001', title='Synthetic paper', applicability='applies',
                  category='missing_supported', adapter='sm_higgs_invisible', domain={'m_chi': (10, 60)}, result=HINV)
    new = cd.supersession([c], {'test': 'record:gamma'}, [gamma])[0]
    assert new.category == 'missing_supported' and 'another kind of constraint' in new.missing
    service._write(s.session_id, 'inventory.json', [gamma.model_dump(mode='json')])
    service._save_candidates(s.session_id, [new])
    assert cd.requirements_at(service.coverage(s.session_id), 15, [])


def test_the_mediator_mass_scope_qualifies_points_outside_it():
    """F19-04 mediator_scope: a pin surveyed over m_med 100–200 GeV qualifies a point at m_med = 1 TeV, and a
    requirement declared over a mediator range applies only inside it."""
    coverage = DiscoveryCoverage(session_id='a' * 32, assessment_sha256='b' * 64, model_sha256='c' * 64,
                                 model_reference='file:' + 'c' * 64, searched_at='2026-10-19',
                                 domain={'m_med': (100.0, 200.0)}, requirements=[
                                     Requirement(candidate_id='x', name='a mediator search', reference='arXiv:1',
                                                 reason='r', constraint_class='collider',
                                                 domain={'m_med': (150.0, 200.0)})])
    assert any('outside the surveyed range m_med' in t for t in cd.requirements_at(coverage, 50.0, [], m_med=1000.0))
    assert not cd.requirements_at(coverage, 50.0, [], m_med=120.0)
    assert cd.requirements_at(coverage, 50.0, [], m_med=180.0) == ['discovery: a mediator search (arXiv:1): r']


def test_a_supersession_is_confirmed_only_for_the_proposed_replacement(session):
    service, s = session
    c = Candidate(candidate_id='old', name='older', constraint_class='collider', reference='arXiv:2401.00009',
                  title='Older', applicability='applies', category='superseded', superseded_by='record:new', result=HINV)
    service._save_candidates(s.session_id, [c])
    with pytest.raises(ValueError, match='naming the same newer result'):
        service.decide(s.session_id, 'old', 'superseded', 'because', 'Synthetic', replacement='record:other')
    decision = service.decide(s.session_id, 'old', 'superseded', 'because', 'Synthetic', replacement='record:new')
    assert decision.replacement == 'record:new'


def _discovery_case(tmp_path):
    import runpy
    from pathlib import Path
    h = runpy.run_path(str(Path(__file__).with_name('test_constraint_discovery.py')))
    service = cd.Discovery(ExperimentalCatalog(tmp_path / 'catalog'), abstracts=h['_abstracts'], fetch=h['Web'](),
                           resolver=h['_resolver'])
    path, _ = h['_model'](tmp_path)
    s = service.start(str(path), cd.Options(budget=1))
    answer = h['_answer']('discovery_' + h['HINV'][:8], h['TABLE_SHA'], h['PDF_SHA'])
    return service, s, h, answer


def test_an_extraction_interrupted_before_its_receipt_is_not_asked_again(tmp_path):
    """F19-05, the audit's extraction control: the receipt write fails after the answer and the revision exist; the
    resume finishes from the saved answer (no third call) and reuses the published revision."""
    from unittest.mock import patch
    from adroit.agents.llm import FakeLLMClient
    from adroit.orchestrator import experimental_extraction as ex
    service, s, h, answer = _discovery_case(tmp_path)
    llm = FakeLLMClient([h['_proposals'](), answer, answer])
    original, failed = ex.atomic_json, []
    def write(path, value):
        if not failed and 'extractions' in path.parts:
            failed.append(path)
            raise OSError('interrupted before the extraction receipt')
        return original(path, value)
    with patch.object(ex, 'atomic_json', write):
        first = service.run(s.session_id, llm)
        calls = llm.call_count
        second = service.run(s.session_id, llm)
    assert first['extraction']['status'] == 'failed' and second['extraction']['status'] == 'done'
    assert llm.call_count == calls == 2                                     # relevance + one extraction, not three
    drafts = [r for r in service.catalog.list() if r.provenance.get('extraction_session')]
    assert len(drafts) == 1                                                 # the published revision reused


def test_a_response_in_the_paid_journal_is_used_instead_of_asking_again(tmp_path):
    """F19-05: interrupted between the provider's response and the saved answer, the step finds the response the
    paid journal received for its invocation and does not dispatch."""
    import json
    from adroit.agents.llm import FakeLLMClient
    service, s, h, answer = _discovery_case(tmp_path)
    try:                                                     # the relevance answer only: extraction cannot run
        service.run(s.session_id, FakeLLMClient([h['_proposals']()]))
    except Exception:                                        # noqa: BLE001 (an exhausted fake, as a crash)
        pass
    c = next(c for c in service.candidates(s.session_id) if c.extraction_session)
    ex = service.extraction
    scope = ex.scope(c.extraction_session)
    units = ex.prepare(c.extraction_session, 0)
    prior = service.catalog.load(scope.revision)
    from adroit.core.evidence import content_hash
    invocation = content_hash({'session': c.extraction_session, 'units': [u.unit_id for u in units], 'instructions':
                               cd.extraction_instruction([c], cd.viewed(scope)), 'prior': prior.reference,
                               'trimmed': False})[:32]
    journal = ex.budgets.folder(scope.budget_session or c.extraction_session) / 'paid.jsonl'
    rows = [{'id': 'k', 'state': 'reserved', 'invocation': invocation},
            {'id': 'k', 'state': 'received', 'response': {'content': [{'type': 'text', 'text': answer.model_dump_json()}]}},
            {'id': 'k', 'state': 'settled', 'cost_usd': 0.01}]
    journal.write_text(journal.read_text() + ''.join(json.dumps(r) + '\n' for r in rows) if journal.exists()
                       else ''.join(json.dumps(r) + '\n' for r in rows))
    never = FakeLLMClient([])
    step = ex.step(c.extraction_session, 0, cd.extraction_instruction([c], cd.viewed(scope)), llm=never)
    assert never.call_count == 0 and step.raw_answer == answer.model_dump(mode='json')


def test_recovery_reads_past_the_settlement_row(session):
    """F19-05: the journal's real order is reserved, received, settled; a relevance answer is recovered after the
    settlement row too."""
    import json
    from adroit.agents.constraint_discovery import DiscoveryReport
    service, s = session
    (service.folder(s.session_id) / 'candidates.json').unlink(missing_ok=True)
    journal = service.budgets.folder(s.session_id) / 'paid.jsonl'
    report = DiscoveryReport(proposals=[_proposal()[0]]).model_dump_json()
    rows = [{'id': 'x', 'state': 'reserved'}, {'id': 'x', 'state': 'received', 'response': {'content': [
        {'type': 'text', 'text': report}]}}, {'id': 'x', 'state': 'settled', 'cost_usd': .01}]
    journal.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    assert service._recovered(s) is not None
