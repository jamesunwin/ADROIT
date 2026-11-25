from pathlib import Path

import pytest

from adroit.core.evidence import EvidenceContext
from adroit.evidence.archive import export_run, verify_bundle
from adroit.evidence.build import save
from adroit.evidence.replay import replay_bundle
from adroit.orchestrator import signal


def test_signal_point_replays_actual_historical_likelihood(tmp_path: Path) -> None:
    request=signal.SignalRequest(experiment="CDMS II Si (2013)",
        candidates=[signal.Candidate(label="O1s@8.6",card_id="O1",isospin="s",mass_gev=8.6)],
        null_modules=[],toys=20,complementary=False)
    result=signal.run(request)
    assert result.engine_candidates[0].interaction is not None
    folder=tmp_path/"signal"
    folder.mkdir()
    path=folder/"result.json"
    path.write_text(result.model_dump_json())
    save(path,"signal")
    archive=tmp_path/"signal.zip"
    export_run(path,archive)
    assert verify_bundle(archive).nodes[0].summary["global_z"]==result.global_z
    replay=replay_bundle(archive)
    assert replay.status=="matched",replay.model_dump()
    assert replay.actual["s_hat"]==result.fits[0].s_hat
    assert replay.reasons and "legacy_unknown" in replay.reasons[0]
    with pytest.raises(ValueError):
        replay_bundle(archive,index=-1)
    with pytest.raises(ValueError):
        replay_bundle(archive,node_id="missing")


def test_point_replay_missing_backend_and_numeric_difference(track1_file: Path,tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    from adroit.evidence.results import load_result
    _,saved=load_result(track1_file)
    archive=tmp_path/"track1.zip"
    export_run(track1_file,archive)
    def missing(*args: object,**kwargs: object) -> None:
        raise FileNotFoundError("backend unavailable")
    monkeypatch.setattr("adroit.parameter_space.scan.evaluate",missing)
    replay=replay_bundle(archive)
    assert replay.status=="incomplete" and "backend unavailable" in replay.reasons[0]
    row=saved.scan.points[0].model_copy(deep=True)
    row.dd_sigma_cm2=1e-3
    monkeypatch.setattr("adroit.parameter_space.scan.evaluate",lambda *a,**k: row)
    replay=replay_bundle(archive)
    assert replay.status=="different" and any("dd_sigma_cm2" in d for d in replay.differences)


def test_replay_tolerance_cannot_hide_a_cross_section_error() -> None:
    from adroit.evidence.replay import _differences
    assert _differences({"dd_sigma_cm2":1e-45},{"dd_sigma_cm2":1e-44},1e-7,1e-9)
    assert not _differences({"q0":0.},{"q0":1e-14},1e-7,1e-9)


def test_both_track_views_share_physical_point_observations(track1_file: Path,tmp_path: Path,
                                                         context: EvidenceContext,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    from adroit.orchestrator.single_idea import SingleIdeaRequest,SingleIdeaResult,BandPoint
    from adroit.evidence.results import load_result
    monkeypatch.setattr("adroit.evidence.build.finish",lambda c,read=None,consumed=None:c)
    _,t1=load_result(track1_file)
    row=t1.scan.points[0]
    request=SingleIdeaRequest(experiment="CDMS II Si (2013)",spec=t1.request.spec,masses_gev=[row.point.m_chi])
    band=BandPoint(m_chi=row.point.m_chi,s_hat=1,events_at_unit=1,mu_hat=1,mu_68=(0,2),z_local=1,
                   point=row.point,evaluation=row,status="pending",pending=row.pending)
    single=SingleIdeaResult(request=request,band=[band],track1=t1,level="viable_pending")
    target=tmp_path/"single.json"
    target.write_text(single.model_dump_json())
    t1e=save(track1_file,"track1",context)
    sie=save(target,"single_idea",context)
    identities1={o.identity for o in t1e.observations}
    identities2={o.identity for o in sie.observations}
    assert identities1==identities2
    assert {o.subject_id for o in t1e.observations}=={o.subject_id for o in sie.observations}


def test_promotion_graph_exports_selected_child_and_parent(track1_file: Path,tmp_path: Path) -> None:
    from adroit.orchestrator.promote import Child,Promotion
    from adroit.orchestrator import studies
    parent=track1_file.parent
    child=parent/"children"/"child"
    child.mkdir(parents=True)
    (child/"result.json").write_bytes(track1_file.read_bytes())
    studies.record(child,"track1","child",parent=parent)
    promotion=Promotion(parent=str(parent),labels=["c"],children=[Child(label="c",model="model",
        origin="user",folder=str(child),level="pending",summary="missing coverage")],
        undetermined={"other":"no supported completion"})
    path=parent/"promotion_c.json"
    path.write_text(promotion.model_dump_json())
    export_run(path,tmp_path/"promotion.zip")
    verified=verify_bundle(tmp_path/"promotion.zip")
    assert verified.valid and len(verified.nodes)==3
    assert verified.nodes[0].summary["undetermined"]==promotion.undetermined


def test_native_result_reconstructs_without_reinventing_missing_model(tmp_path: Path) -> None:
    from adroit.parameter_space.native_joint import JointResult,JointSettings
    result=JointResult(settings=JointSettings(toys=1),masses_gev=[8.6],
                       omitted={"domain":"missing original model"})
    path=tmp_path/"native_result.json"
    path.write_text(result.model_dump_json())
    save(path,"native_joint")
    export_run(path,tmp_path/"native.zip")
    verified=verify_bundle(tmp_path/"native.zip")
    assert verified.valid and verified.nodes[0].summary["omitted"]==result.omitted
    replay=replay_bundle(tmp_path/"native.zip")
    assert replay.status=="incomplete" and "contract missing" in replay.reasons[0]


def test_native_joint_fit_replays_actual_physical_likelihood(tmp_path: Path) -> None:
    from adroit.core.model_spec import PhysicalFitRange
    from adroit.parameter_space.classes import Spin1Class,Point
    from adroit.parameter_space.native_joint import run,JointSettings,LOW_MASS_NULL
    from adroit.parameter_space.physical_fit import FitSettings
    cls=Spin1Class(name="native replay")
    point=Point(m_chi=8.6,m_med=1000,g_chi=.1,g_q=.25,g_l=0)
    result=run(cls,point,[8.6],PhysicalFitRange(low=0,high=.5),
               JointSettings(null_experiment=LOW_MASS_NULL,toys=1,max_toy_fits=1),FitSettings(),.5)
    assert result.complete,result.omitted
    path=tmp_path/"native_result.json"
    path.write_text(result.model_dump_json())
    save(path,"native_joint")
    export_run(path,tmp_path/"native.zip")
    replay=replay_bundle(tmp_path/"native.zip")
    assert replay.status=="matched",replay.model_dump()
    assert replay.actual["point"]==result.fits[0].point.model_dump(mode="json")
