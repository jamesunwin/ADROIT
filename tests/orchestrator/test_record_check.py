"""A language model's check of a user-added record (the owner, 2026-11-18, the post-review changes item 2): it
signs the review as the model's only on a passed check; ADROIT decides from its answer, confirming each newer paper
it names; a major defect is re-read by the record assistant and checked again, at most twice, then comes back to the
researcher; a suggestion is applied first. Offline: fake models, a fake literature search and a fake arXiv."""
from __future__ import annotations

import pytest

from adroit.agents.llm import FakeLLMClient
from adroit.agents.record_check import CHECKS, CheckItem, Defect, NewerResult, RecordCheckAnswer
from adroit.constraints.experimental_review import (approve_by_model, bind, current_review, load_review, packet,
                                                    validate)
from adroit.core.config import get_settings
from adroit.core.evidence import SourceEvidence
from adroit.core.pricing import CHECKER_MODELS, DEFAULT_CHECKER, bounded_price
from adroit.core.private_limits import SourceReview
from adroit.evidence.observations import review_label
from adroit.orchestrator.record_check import RecordChecker, confirmed, decide, same_title
from adroit.retrieval.references import Reference, parse_search
from tests.experimental_extraction_fixtures import answer
from tests.orchestrator.test_experimental_extraction import setup
from tests.private_limit_fixtures import fixture

LATER = Reference(kind="arxiv", id="2507.00001", title="Dark matter search results from the full exposure",
                  authors=["A. Author"], year=2025, verified=True)


def verdict(ok: bool = True, newer=()) -> RecordCheckAnswer:
    """A checking model's answer: everything passes, or one major defect in the import."""
    items = [CheckItem(name=name, passed=True, reason="as the source gives it", location="source, p. 1")
             for name in CHECKS]
    defects = [] if ok else [Defect(severity="major", what="the background count", record_says="0.4 events",
                                    source_says="0.5 events (the alternative estimate)", location="source, line 3")]
    return RecordCheckAnswer(
        right_limit=CheckItem(name="right_limit", passed=True, reason="the result the record names"),
        imported_correctly=CheckItem(name="imported_correctly", passed=ok, reason="as the source" if ok else
                                     "the background count differs"),
        checklist=items, defects=defects, newer_results=list(newer), compared_against="the search's papers",
        knowledge_cutoff="2026-01", summary="checked")


def checker(catalog, papers=(LATER,), known=(LATER,)) -> RecordChecker:
    return RecordChecker(catalog, search=lambda query, n: list(papers),
                         lookup=lambda refs: {r.id: r for r in known if r.id in {x.id for x in refs}})


def drafted(tmp_path):
    """An assisted-extraction record (its result "signal"), drafted by Claude Opus 5.5's fake."""
    catalog, r, svc, s = setup(tmp_path)
    step = svc.step(s.session_id, llm=FakeLLMClient([answer(r.sources[0].sha256)]))
    return catalog, r, step.output_revision


def test_fable_is_priced_and_the_default_checker():
    assert DEFAULT_CHECKER == "claude-fable-5-1" and set(CHECKER_MODELS) == {"claude-fable-5-1", "gpt-5.6-sol"}
    assert bounded_price("claude-fable-5-1") == (10.0e-6, 50.0e-6)


def test_a_passed_check_signs_the_review_as_the_model_s_and_it_binds(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "experimental_library_dir", tmp_path / "private")
    catalog, r = fixture(tmp_path)
    service = checker(catalog)
    run = service.start(r.reference, "limit", 1.0)
    fake = FakeLLMClient([verdict()])
    outcome = service.run(run.session_id, llm_for=lambda model: fake)
    assert outcome.status == "approved" and outcome.revisions == [r.reference]
    review = load_review(outcome.review_id, catalog)
    assert review.checked_by_model == "claude-fable-5-1" and review.by_model and "not a person" in review.researcher
    assert current_review(r.reference, "limit", catalog).review_id == review.review_id
    sent = fake.calls[0]["messages"][0]["content"]
    assert "2507.00001" in sent and '"record"' in sent                # the literature search and the record were sent
    value = packet(r.reference, "limit", catalog=catalog)
    validation = validate(r.reference, "limit", .02, value["scientific_sha256"], catalog)
    bound = bind(r.reference, "limit", review.review_id, validation.validation_id, catalog)
    from adroit.evidence.runtime import _private_limit_evidence
    [source], _ = _private_limit_evidence([bound.reference])
    assert source.review == "verified" and source.reviewed_by_model == "claude-fable-5-1"
    from adroit.core.evidence import EvidenceContext
    context = EvidenceContext.model_construct(sources=[source])
    assert review_label("verified", [source.id], context) == ("verified: checked by Claude Fable 5.1, not by a "
                                                               "person")


def test_a_person_s_review_and_every_other_source_hash_as_before():
    review = SourceReview(review_id="x", signed_revision="r", result_id="limit", keys=[], scientific_sha256="0" * 64,
                          researcher="A. Person", reviewed_at="2026-11-18", checklist=[])
    assert "checked_by_model" not in review.model_dump() and "check_id" not in review.model_dump()
    assert "reviewed_by_model" not in SourceEvidence(id="s", reference="s").model_dump()
    assert review_label("verified", ["s"], None) == "verified"


def test_a_major_defect_is_re_read_by_the_assistant_and_checked_again(tmp_path):
    catalog, r, ref = drafted(tmp_path)
    service = checker(catalog)
    run = service.start(ref, "signal", 2.0)
    fake = FakeLLMClient([verdict(ok=False), answer(r.sources[0].sha256), verdict()])
    outcome = service.run(run.session_id, llm_for=lambda model: fake)
    assert outcome.status == "approved" and len(outcome.revisions) == 2 and len(outcome.checks) == 2
    reread = fake.calls[1]
    assert "the background count" in reread["messages"][0]["content"]              # the check's report, to the assistant
    scope_session = catalog.load(outcome.revisions[1]).provenance["extraction_session"]
    assert service.budgets.session(scope_session).model == "claude-opus-5-5"      # the assistant's own model
    assert load_review(outcome.review_id, catalog).signed_revision == outcome.revisions[1]


def test_no_agreement_after_two_re_readings_comes_back_to_the_researcher(tmp_path):
    catalog, r, ref = drafted(tmp_path)
    service = checker(catalog)
    run = service.start(ref, "signal", 2.0)
    sha = r.sources[0].sha256
    fake = FakeLLMClient([verdict(False), answer(sha), verdict(False), answer(sha), verdict(False)])
    outcome = service.run(run.session_id, llm_for=lambda model: fake)
    assert outcome.status == "needs_you" and len(outcome.checks) == 3 and len(outcome.revisions) == 3
    assert any("0.5 events" in m for m in outcome.mismatches) and not outcome.review_id
    assert current_review(outcome.final_revision, "signal", catalog) is None
    assert service.outcome(run.session_id) == outcome


def test_a_suggestion_is_applied_first_and_checked_once(tmp_path):
    catalog, r, ref = drafted(tmp_path)
    service = checker(catalog)
    run = service.start(ref, "signal", 2.0, retries=0, instruction="use the alternative background estimate")
    fake = FakeLLMClient([answer(r.sources[0].sha256), verdict(False)])
    outcome = service.run(run.session_id, llm_for=lambda model: fake)
    assert "use the alternative background estimate" in fake.calls[0]["messages"][0]["content"]
    assert outcome.status == "needs_you" and len(outcome.checks) == 1 and len(outcome.revisions) == 2


def test_only_a_confirmed_later_analysis_by_the_same_collaboration_rejects():
    superseded = NewerResult(arxiv_id="arXiv:2507.00001", title="Dark matter search results from the full exposure.",
                             year=2025, relation="superseded")
    invented = NewerResult(arxiv_id="2599.99999", title="A paper that does not exist", relation="superseded")
    misnamed = NewerResult(arxiv_id="2507.00001", title="Something else entirely", relation="superseded")
    stronger = NewerResult(arxiv_id="2507.00001", title=LATER.title, relation="stronger_elsewhere")
    lookup = lambda refs: {r.id: LATER for r in refs if r.id == LATER.id}          # noqa: E731
    found = confirmed(verdict(newer=[superseded, invented, misnamed, stronger]), lookup)
    assert [c.confirmed for c in found] == [True, False, False, True]
    major, notes = decide(verdict(), found)
    assert major == [f"superseded by a later analysis of the same collaboration: arXiv:2507.00001 ({LATER.title}, "
                     "2025)"]
    assert sum("unconfirmed citation, not used" in n for n in notes) == 2 and any("stronger" in n for n in notes)
    broken = confirmed(verdict(newer=[superseded]), lambda refs: (_ for _ in ()).throw(OSError("offline")))
    assert not broken[0].confirmed and "could not be asked" in broken[0].why
    assert decide(verdict(newer=[superseded]), broken)[0] == []                      # never a reason to reject


def test_an_unanswered_check_or_a_failed_question_fails():
    answer_ = verdict()
    answer_.checklist = answer_.checklist[1:]
    answer_.right_limit = CheckItem(name="right_limit", passed=False, reason="an expected sensitivity, not a limit")
    major, _ = decide(answer_, [])
    assert "source_values: not answered" in major and any("expected sensitivity" in m for m in major)
    assert same_title("Results from LZ's first run", "results from lz s first run")


def test_a_failed_or_changed_check_cannot_approve(tmp_path):
    catalog, r = fixture(tmp_path)
    service = checker(catalog)
    run = service.start(r.reference, "limit", 1.0)
    check = service.check(run, r.reference, 0, llm_for=lambda model: FakeLLMClient([verdict(False)]))
    assert not check.passed and service.load(check.check_id) == check
    with pytest.raises(ValueError, match="did not pass"):
        approve_by_model(check, catalog)
    with pytest.raises(ValueError, match="changed"):
        approve_by_model(check.model_copy(update={"passed": True, "scientific_sha256": "1" * 64}), catalog)


def test_a_check_needs_a_listed_model_a_budget_and_an_existing_result(tmp_path):
    catalog, r = fixture(tmp_path)
    service = checker(catalog)
    for kwargs in ({"model": "claude-opus-5-5"}, {"budget": 0.0}, {"result_id": "absent"}):
        args = {"reference": r.reference, "result_id": "limit", "budget": 1.0, **kwargs}
        with pytest.raises(ValueError):
            service.start(**args)


def test_the_literature_search_failing_is_said_and_the_check_goes_on(tmp_path):
    catalog, r = fixture(tmp_path)
    service = RecordChecker(catalog, search=lambda q, n: (_ for _ in ()).throw(OSError("offline")),
                            lookup=lambda refs: {})
    run = service.start(r.reference, "limit", 1.0)
    check = service.check(run, r.reference, 0, llm_for=lambda model: FakeLLMClient([verdict()]))
    assert check.passed and "offline" in check.search["error"]


def test_arxiv_s_search_answer_is_read_newest_first():
    atom = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2507.00001v2</id>'
            '<title>Dark matter search\n results</title><published>2025-07-01T00:00:00Z</published>'
            '<author><name>A. Author</name></author><summary>We report.</summary></entry></feed>')
    [paper] = parse_search(atom)
    assert (paper.id, paper.title, paper.year, paper.note) == ("2507.00001", "Dark matter search results", 2025,
                                                               "submitted 2025-07-01")


@pytest.mark.parametrize("first_passes", [False, True])
@pytest.mark.parametrize("name", list(CHECKS))
def test_a_check_answered_twice_fails_whatever_the_order(name, first_passes):
    """The post-review audit's PR-05: the last of two answers had been kept, so a failed check answered again as passed
    approved a wrong record. A repeat fails, in either order."""
    answer_ = verdict()
    again = CheckItem(name=name, passed=first_passes, reason="the second answer")
    first = next(c for c in answer_.checklist if c.name == name).model_copy(update={"passed": not first_passes})
    answer_.checklist = [c for c in answer_.checklist if c.name != name] + [first, again]
    major, _ = decide(answer_, [])
    assert f"{name}: answered 2 times; each check is answered once" in major


def test_an_unknown_check_name_fails_and_the_ordinary_set_passes():
    answer_ = verdict()
    assert decide(answer_, [])[0] == []
    answer_.checklist = [*answer_.checklist, CheckItem(name="looks_fine", passed=True, reason="")]
    assert "looks_fine: not one of the checks asked for" in decide(answer_, [])[0]
