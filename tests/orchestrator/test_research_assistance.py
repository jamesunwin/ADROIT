"""Measured assistance never substitutes parameters, source truth or physical results."""

from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from typer.testing import CliRunner

from adroit.agents.llm import FakeLLMClient
from adroit.core.assistance import (
    AssistanceProposal,
    AssistanceReview,
    PlanStep,
    ReviewClaim,
    SourceRequest,
)
from adroit.orchestrator import research_assistance as service, cli
from adroit.orchestrator.single_idea import SingleIdeaRequest
from adroit.parameter_space.simplified import model
from adroit.parameter_space.native_joint import JointSettings, LOW_MASS_NULL
from adroit.core.model_spec import PhysicalFitRange
from adroit.retrieval.source_evidence import gather
from adroit.retrieval.source_evidence import fetch_pdf
from adroit.retrieval.references import Reference
from adroit.evaluation.assistance_timing import (
    start,
    transition,
    summarize,
    save,
    ResearcherSession,
)
from adroit.evaluation.assistance_value import score, AssistanceTask


def request():
    spec = model("vector", 8.6, 500, 0.001, 0.25).model_copy(
        update={"physical_fit": PhysicalFitRange(low=0, high=0.32)}
    )
    study = SingleIdeaRequest(
        experiment="CDMS II Si (2013)",
        spec=spec,
        masses_gev=[8.6],
        null_modules=[LOW_MASS_NULL],
        native_joint=JointSettings(null_experiment=LOW_MASS_NULL, toys=3),
        literature=False,
        workers=1,
        grid=4,
        toys=20,
    )
    return service.AssistanceRequest(goal="Review my bounded native study", study=study)


def test_baseline_executes_original_request_and_saves_actual_native_artifact(tmp_path):
    original = request()
    before = original.model_dump_json()
    result = service.run(original, tmp_path, execute_plan=True)
    assert result.executed == ["native_joint"] and result.physics_input_preserved
    assert original.model_dump_json() == before
    assert (tmp_path / "native_result.json").exists()
    assert result.calculation_artifacts["native_result.json"]
    assert '"native_complete"' in result.model_dump_json()
    assert (
        not result.vetted and result.api_cost_usd == 0 and result.researcher_seconds_saved is None
    )


def test_review_distinguishes_completed_domain_fit_from_missing_calibration():
    import json
    from adroit.core.fit_domain import PhysicalDomain,FitCoordinate,DomainFitSettings
    from adroit.parameter_space.multiparameter_fit import DomainFit
    from adroit.parameter_space.native_joint import JointResult
    from adroit.parameter_space.classify import classify
    original=request()
    _,point,_=classify(original.study.spec)
    domain=PhysicalDomain(coordinates=[FitCoordinate(parameter='m_chi',values=[8.6]),
                                      FitCoordinate(parameter='g_chi',low=0,high=.32)])
    settings=original.study.native_joint.model_copy(update={'domain':domain})
    study=original.study.model_copy(update={'native_joint':settings})
    native=JointResult(settings=settings,masses_gev=[8.6],reference_point=point,bounds=None,
        domain_fit=DomainFit(domain=domain,reference_point=point,settings=DomainFitSettings(),
                            resolved=True),complete=True)
    typed=original.model_copy(update={'study':study,'native_result':native,
        'draft_claims':[service.ReportClaim(kind='native_z',value=3.)]})
    ctx=service.context(typed)
    flags=service.probes(ctx)
    facts={fact.id:json.loads(fact.value) for fact in ctx.facts}
    assert facts['native_domain_fit_resolved'] and not facts['native_complete']
    assert flags['incomplete_calibration'] and not flags['nr_mislabel']
    assert not flags['input_result_mismatch']
    stale=typed.model_copy(update={'native_result':native.model_copy(update={'bounds':study.spec.physical_fit})})
    assert service.probes(service.context(stale))['input_result_mismatch']


def test_stale_step_is_dropped_and_irrelevant_facts_cannot_confirm_a_claim(tmp_path):
    original = request().model_copy(
        update={"draft_claims": [service.ReportClaim(kind="full_likelihood", value=True)]}
    )
    ctx = service.context(original)
    h = ctx.input_hash
    proposal = AssistanceProposal(
        input_hash=h,
        steps=[PlanStep(action="native_joint", input_hash="stale", reason="do not execute")],
    )
    review = AssistanceReview(
        input_hash=h,
        claims=[
            ReviewClaim(
                issue="fidelity_overclaim",
                fact_ids=["has_study"],
                explanation="irrelevant citation",
            ),
            ReviewClaim(
                issue="fidelity_overclaim",
                fact_ids=["draft_claims", "native_fidelity"],
                explanation="module is fidelity B",
            ),
        ],
    )
    llm = FakeLLMClient([proposal, review])
    result = service.run(original, tmp_path, llm=llm, model="fake-model", execute_plan=True)
    assert result.dropped_steps == ["native_joint"] and result.executed == []
    assert [c.confirmed for c in result.vetted] == [False, True]
    assert len(llm.calls) == 2 and result.physics_input_preserved
    measured = score(AssistanceTask(id="fidelity", expected_issues=["fidelity_overclaim"]), result)
    assert measured.agent_caught == ["fidelity_overclaim"] and measured.added_over_baseline == []
    assert measured.researcher_seconds_saved is None


def test_advisory_failure_preserves_baseline_and_cli_zero_budget_needs_no_provider(tmp_path):
    original = service.AssistanceRequest(goal="Clarify missing model", missing_fields=["model"])
    result = service.run(original, tmp_path / "failure", llm=FakeLLMClient(), model="fake-model")
    assert result.status == "degraded" and result.review_origin == "deterministic"
    assert result.baseline_issues == ["missing_input"] and result.vetted[0].confirmed
    path = tmp_path / "request.json"
    path.write_text(original.model_dump_json())
    out = CliRunner().invoke(
        cli.app, ["assist", str(path), "--out", str(tmp_path / "offline"), "--budget", "0"]
    )
    assert out.exit_code == 0, out.output
    assert "Mode: deterministic" in out.output and "not yet measured" in out.output


def pdf_bytes():
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {
                    NameObject("/F1"): DictionaryObject(
                        {
                            NameObject("/Type"): NameObject("/Font"),
                            NameObject("/Subtype"): NameObject("/Type1"),
                            NameObject("/BaseFont"): NameObject("/Helvetica"),
                        }
                    )
                }
            )
        }
    )
    content = DecodedStreamObject()
    content.set_data(
        b"BT /F1 12 Tf 20 100 Td (Primary likelihood evidence with source counts and a finite domain.) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(content)
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def test_gather_reads_real_bytes_binds_cache_and_distinguishes_semantic_verification(tmp_path):
    calls = []

    def resolver(refs):
        return {
            r.id: Reference(kind="arxiv", id=r.id, title="Actual source", verified=True)
            for r in refs
        }

    def download(identifier):
        calls.append(identifier)
        return pdf_bytes()

    req = SourceRequest(arxiv_id="1902.04031", title="Actual source", page=1, anchor="likelihood")
    packets = gather([req], tmp_path, resolver=resolver, download=download)
    assert (
        packets[0].reference_checked
        and packets[0].content_checked
        and not packets[0].claim_verified
    )
    assert len(packets[0].excerpt.split()) <= 25 and packets[0].document_sha256
    (tmp_path / "1902.04031.pdf").write_bytes(b"corrupted cached document")
    assert gather([req], tmp_path, resolver=resolver, download=download)[0].content_checked
    assert len(calls) == 2
    bad = gather(
        [req.model_copy(update={"title": "Unrelated invented title"})],
        tmp_path,
        resolver=resolver,
        download=download,
    )
    assert not bad[0].reference_checked and not bad[0].content_checked


def test_each_evidence_state_is_set_on_its_own_grounds(tmp_path):
    """The external audit's A08 (2026-10-16): an empty anchor had marked the content checked (the page's first words),
    and a description had marked the reference checked. Now: the source exists; a description identifies nothing;
    with no anchor nothing on the page is checked; a contradicted citation is refused; and only an identified
    paper's anchored passage counts as evidence."""
    def resolver(asked):
        return {r.id: Reference(kind="arxiv", id=r.id, title="Primary likelihood evidence", year=2019,
                                abstract="PICO-60 counts in a finite domain", verified=True) for r in asked}
    def download(identifier):
        return pdf_bytes()
    def one(**update):
        req = SourceRequest(arxiv_id="1902.04031", title="Primary likelihood evidence", page=1, anchor="likelihood")
        return gather([req.model_copy(update=update)], tmp_path, resolver=resolver, download=download)[0]
    full = one()
    assert full.exists and full.identity == "title" and full.reference_checked and full.content_checked
    unanchored = one(anchor="")
    assert unanchored.exists and unanchored.reference_checked and not unanchored.content_checked
    assert "nothing on it was checked" in unanchored.note
    described = one(title="PICO-60 counts")
    assert described.exists and described.identity == "description" and not described.reference_checked
    contradicted = one(title="Primary likelihood evidence (2015)")
    assert contradicted.identity == "contradicted" and not contradicted.reference_checked
    assert not contradicted.content_checked and "contradicts" in contradicted.note
    # the external audit of 2026-10-17, I17-2: an anchor of spaces had matched the page and marked it checked
    for blank in (" ", " \t\n "):
        assert SourceRequest(arxiv_id="1902.04031", anchor=blank).anchor == ""
        spaced = one(anchor=blank)
        assert spaced.exists and not spaced.content_checked and "nothing on it was checked" in spaced.note
    with pytest.raises(ValueError, match="letters or digits"):
        SourceRequest(arxiv_id="1902.04031", anchor=" . ")
    assert not one(anchor=" . ").content_checked


def test_researcher_timer_excludes_breaks_failed_tasks_and_unattested_sessions(tmp_path):
    now = datetime(2026, 10, 8, tzinfo=timezone.utc)
    h = "a" * 64
    manual = start("P1", "task", h, "manual", now)
    manual = transition(manual, "pause", now=now + timedelta(seconds=60))
    manual = transition(manual, "resume", now=now + timedelta(seconds=600))
    manual = transition(
        manual, "finish", attest=True, success=True, now=now + timedelta(seconds=630)
    )
    assisted = start("P1", "task", h, "assisted", now)
    assisted = transition(
        assisted, "finish", attest=True, success=True, now=now + timedelta(seconds=30)
    )
    result = summarize([manual, assisted])
    assert result.mean_seconds_saved == 60 and result.paired_completed_tasks == 1
    failed = assisted.model_copy(update={"task_success": False})
    assert summarize([manual, failed]).mean_seconds_saved is None
    assert summarize([]).mean_seconds_saved is None
    with pytest.raises(ValueError, match="attestation"):
        transition(start("P1", "task", h, "manual", now), "finish", now=now)
    with pytest.raises(ValueError, match="reversed"):
        transition(manual, "resume", now=now - timedelta(seconds=1))
    path = tmp_path / "session.json"
    save(manual, path)
    assert ResearcherSession.model_validate_json(path.read_text()) == manual


def test_network_fetch_is_bounded_and_never_accepts_arbitrary_urls(monkeypatch):
    seen = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        def iter_content(self, size):
            yield b"%PDF fake download"

    def get(url, **kwargs):
        seen.append((url, kwargs))
        return Response()

    monkeypatch.setattr("requests.get", get)
    assert fetch_pdf("1902.04031").startswith(b"%PDF")
    assert seen[0][0] == "https://arxiv.org/pdf/1902.04031" and seen[0][1]["timeout"] == 30
    with pytest.raises(ValueError):
        fetch_pdf("file:///private/key")


def test_coverage_orchestrator_preserves_declared_inputs(tmp_path):
    from adroit.orchestrator.native_coverage import CoverageRequest, run
    from adroit.parameter_space.native_coverage import NuisanceScenario, CoverageSettings

    original = request()
    cov = CoverageRequest(
        spec=original.study.spec,
        masses_gev=[8.6],
        scenarios=[NuisanceScenario(theta=0, null_backgrounds=[0, 0])],
        settings=CoverageSettings(outer_trials=1, inner_toys=19, max_fits=100),
    )
    before = cov.model_dump_json()
    result = run(cov, tmp_path)
    assert result.complete and result.fits == 20 and cov.model_dump_json() == before
    assert "not uniform" in (tmp_path / "report.md").read_text()


def test_cli_timer_requires_attestation_and_summary_does_not_impute_time(tmp_path):
    runner = CliRunner()
    path = tmp_path / "session.json"
    out = runner.invoke(
        cli.app, ["assist-session", "start", str(path), "P1", "task", "a" * 64, "manual"]
    )
    assert out.exit_code == 0, out.output
    out = runner.invoke(cli.app, ["assist-session", "mark", str(path), "pause"])
    assert out.exit_code == 0, out.output
    out = runner.invoke(cli.app, ["assist-session", "mark", str(path), "resume"])
    assert out.exit_code == 0, out.output
    out = runner.invoke(cli.app, ["assist-session", "mark", str(path), "finish", "--attest", "--success"])
    assert out.exit_code == 0, out.output
    out = runner.invoke(cli.app, ["assist-session", "summary", str(tmp_path)])
    assert out.exit_code == 0 and '"mean_seconds_saved": null' in out.output
