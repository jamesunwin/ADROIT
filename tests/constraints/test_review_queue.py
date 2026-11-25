from pathlib import Path
from datetime import datetime,timedelta,timezone
import json

import pytest
from typer.testing import CliRunner

from adroit.core.evidence import EvidenceContext,EvidenceEnvelope,EvidenceObservation,SourceEvidence,content_hash
from adroit.constraints.review_queue import SelectedEvidence,build_queue,load_selected,queue_for,report
from adroit.constraints.review_packets import packet_for,packet_report


def selection(status: str="pending",workflow: str="track1",suffix: str="") -> SelectedEvidence:
    engine={"name":"test", "family":"test"}
    point={"m_chi":10.,"m_med":1000.,"g_chi":.1,"g_q":.25,"g_l":0.}
    from adroit.core.evidence import physical_identity
    sid=physical_identity(engine,point)
    source=SourceEvidence(id="flavour-b-to-k-invisible",reference="paper",review="unreviewed",
                          metadata={"constraint_class":"flavour"})
    observation=EvidenceObservation(subject_id=sid,physical_input=point,observable="flavour",
        calculation="not_calculated",review="unreviewed",source_ids=[source.id],
        native_confidence_level=.9,required_confidence_level=.95,
        reasons=["its record (flavour-b-to-k-invisible) awaits a person's verification"],
        details={"comparison":.1})
    result={"verdict":{"crossings":[{"point":point,"status":status,"kind":"contour","evaluation":{}}]}}
    if workflow=="single_idea":
        result={"track1":result,"band":[]}
    envelope=EvidenceEnvelope(workflow=workflow,result_sha256=content_hash([workflow,suffix]),input_sha256="input",
        engine_mapping=engine,context=EvidenceContext(origin="captured",sources=[source]),
        observations=[observation,observation.model_copy(deep=True)])
    return SelectedEvidence(envelope=envelope,result=result)


def test_review_and_recast_are_distinct_and_repeat_views_do_not_inflate_priority() -> None:
    queue=build_queue([selection(),selection()])
    assert len(queue.tasks)==2
    verify,recast=queue.tasks
    assert verify.kind=="source_verification" and recast.kind=="recast_likelihood"
    assert all(t.blocked_points==1 and t.affected_studies==1 and len(t.affected)==1 for t in queue.tasks)
    assert verify.affected[0].reasons==selection().envelope.observations[0].reasons


def test_pending_requested_points_rank_above_already_excluded_checks() -> None:
    pending=selection()
    excluded=selection("excluded",suffix="excluded")
    excluded.envelope.observations[0].source_ids=[]
    excluded.envelope.observations[1].source_ids=[]
    excluded.envelope.observations[0].reasons=["backend unavailable"]
    excluded.envelope.observations[1].reasons=["backend unavailable"]
    excluded.envelope.observations[0].calculation="unavailable_backend"
    excluded.envelope.observations[1].calculation="unavailable_backend"
    queue=build_queue([excluded,pending])
    assert queue.tasks[0].blocked_points==1
    assert any(t.kind=="backend" and t.blocked_points==0 for t in queue.tasks)
    assert "already excluded" in queue.ranking


def test_scan_diagnostics_are_opt_in_and_unknown_is_not_allowed() -> None:
    current=selection()
    current.result={}
    assert build_queue([current]).tasks==[]
    queue=build_queue([current],include_scan=True)
    assert queue.tasks and all(t.blocked_points==0 for t in queue.tasks)
    assert all(a.observation.excluded is None for t in queue.tasks for a in t.affected)


def test_same_physical_input_has_same_reason_in_both_tracks() -> None:
    t1=build_queue([selection()])
    si=build_queue([selection(workflow="single_idea")])
    assert [(t.id,t.reason,t.kind) for t in t1.tasks]==[(t.id,t.reason,t.kind) for t in si.tasks]
    assert t1.tasks[0].affected[0].observation.identity==si.tasks[0].affected[0].observation.identity


def test_old_thermal_point_keeps_explicit_waiting_reason_without_inventing_a_review() -> None:
    current=selection()
    current.envelope.observations=[]
    current.envelope.context=EvidenceContext()
    crossing=current.result["verdict"]["crossings"][0]
    crossing.update(evaluation=None,pending=["its record (hess-1805.05741-lines) awaits a person's verification"],
                    omega_h2=.12000001,relative_residual=1e-7)
    queue=build_queue([current])
    assert len(queue.tasks)==1 and queue.tasks[0].record_id=="hess-1805.05741-lines"
    assert queue.tasks[0].blocked_points==1
    affected=queue.tasks[0].affected[0]
    assert affected.observation.review=="legacy_unknown" and affected.observation.value is None
    assert affected.observation.details["omega_h2"]==.12000001


def test_source_diff_shows_missing_historical_curves_honestly() -> None:
    from adroit.constraints import database
    record=database.record("cms-2405.13778-V1")
    previous=SourceEvidence(id=record.id,reference="old paper",metadata=record.model_dump(mode="json"),
                           data_path=record.data_file,data_sha256="old-data")
    previous.metadata["assumptions"]=["old assumption"]
    current=selection()
    current.envelope.context.sources=[previous]
    packet=packet_for(record.id,current)
    assert any(d.field=="assumptions" for d in packet.differences)
    assert "not captured" in packet.previous_curve_status and not packet.previous_curves
    assert packet.current_curves and packet.source_page==record.figure.page
    assert "old assumption" in packet_report(packet)


def test_archived_curves_are_used_for_historical_comparison() -> None:
    from adroit.constraints import database
    from adroit.core.config import PROJECT_ROOT
    import hashlib
    record=database.record("cms-2405.13778-V1")
    data=(PROJECT_ROOT/record.data_file).read_bytes()
    sha=hashlib.sha256(data).hexdigest()
    current=selection()
    current.envelope.context.sources=[SourceEvidence(id=record.id,reference=record.source,
        metadata=record.model_dump(mode="json"),data_path=record.data_file,data_sha256=sha)]
    current.archived_inputs={sha:data.decode()}
    packet=packet_for(record.id,current)
    assert packet.previous_curve_status=="captured historical data"
    assert packet.previous_curves==packet.current_curves


def test_review_timing_reuses_existing_human_attestation_protocol(tmp_path: Path,monkeypatch: pytest.MonkeyPatch) -> None:
    from adroit.constraints import review
    from adroit.evaluation import assistance_timing as timing
    packet=packet_for("lep-contact-bl")
    now=datetime(2026,10,8,tzinfo=timezone.utc)
    original_start=timing.start
    monkeypatch.setattr(timing,"start",lambda p,t,h,c:original_start(p,t,h,c,now))
    path=tmp_path/"timer.json"
    review.start_timing(packet,"Researcher","assisted",path)
    saved=timing.ResearcherSession.model_validate_json(path.read_text())
    assert saved.input_hash==packet.timing_identity and saved.api_cost_usd==0
    with pytest.raises(ValueError):
        review.start_timing(packet,"Researcher","assisted",path)
    with pytest.raises(ValueError):
        review.mark_timing(path,"finish")
    original_transition=timing.transition
    monkeypatch.setattr(timing,"transition",lambda s,a,**kw:original_transition(s,a,now=now+timedelta(seconds=60),**kw))
    review.mark_timing(path,"finish",attest=True,success=True)
    assert timing.summarize([timing.ResearcherSession.model_validate_json(path.read_text())]).mean_seconds_saved is None


def test_selected_archive_and_ui_cli_export_reason_consistency(tmp_path: Path,monkeypatch) -> None:
    # Compare scientific reasons under the same render clock; separate renders
    # legitimately have different generation timestamps, not different inputs.
    monkeypatch.setattr('adroit.core.chronology.utc_now',lambda:'2026-10-09T00:00:00+00:00')
    from adroit.orchestrator.cli import app
    from adroit.evidence.archive import export_run,read_bundle
    source=Path(__file__).parents[2]/"docs/dm13/reports/axial_mediator/result.json"
    archive=tmp_path/"selected.zip"
    export_run(source,archive)
    manifest,files=read_bundle(archive)
    actual=queue_for(source)
    archived=json.loads(files["studies/n0/review_queue.json"])
    assert archived==actual.model_dump(mode="json")
    packed=build_queue(load_selected(archive)).model_dump(mode="json")
    assert {k:v for k,v in packed.items() if k!="warnings"}=={k:v for k,v in archived.items() if k!="warnings"}
    # the bundle's review keeps its export's warnings, before the node's own (the auditor's DB/VI recheck, DC-02)
    assert packed["warnings"]==[f"bundle: {w}" for w in manifest.warnings]+archived["warnings"]
    outcome=CliRunner().invoke(app,["records","queue","--run",str(source),"--out",str(tmp_path/"queue.json")])
    assert outcome.exit_code==0,outcome.output
    assert json.loads((tmp_path/"queue.json").read_text())==archived
    assert report(actual) in outcome.output
