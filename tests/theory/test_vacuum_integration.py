"""Certificate placement, saved evidence and legacy replay semantics."""

from pathlib import Path
import json

import pytest
import yaml

from adroit.core.model_spec import ModelSpec
from adroit.core.evidence import EvidenceContext
from adroit.evidence.build import build, save, read
from adroit.evidence.archive import export_run, verify_bundle
from adroit.evidence.observations import point_observations
from adroit.parameter_space.classify import classify
from adroit.parameter_space.scan import PointResult, Axis, ScanRequest, ScanResult
from adroit.model_building.audit import audit
from adroit.orchestrator.track1 import Track1Request, Track1Result, report as track_report
from adroit.orchestrator.single_idea import (
    SingleIdeaRequest,
    SingleIdeaResult,
    BandPoint,
    report as idea_report,
)


def result() -> Track1Result:
    spec = ModelSpec.model_validate(
        yaml.safe_load(Path("docs/examples/complete_scalar_singlet.yaml").read_text())
    )
    cls, p, _ = classify(spec)
    request = Track1Request(spec=spec, literature=False, workers=1)
    point = PointResult(
        point=p,
        omega_h2=0.12,
        dd_kind="SI",
        dd_sigma_cm2=cls.dd(p)[1],
        dd_limit_cm2=None,
        excluded={},
        model_contract=cls.point_potential(p).model_dump(mode="json"),
        vacuum_certificate=cls.vacuum_certificate(p),
    )
    scan = ScanResult(
        request=ScanRequest(
            model_class=cls,
            fixed=p,
            x=Axis(parameter="g_chi", low=0.1, high=0.2, n=2),
            y=Axis(parameter="m_chi", low=200, high=300, n=2),
        ),
        xs=[0.1, 0.2],
        ys=[200, 300],
        points=[point] * 4,
    )
    from adroit.parameter_space.verdict import Verdict

    return Track1Result(
        request=request,
        audit=audit(spec),
        fixed=p,
        scan=scan,
        verdict=Verdict(level="viable", summary="experimental example", target=0.12),
    )


def test_certificates_are_scoped_separate_from_structural_and_experimental_flags() -> None:
    saved = result()
    cls = saved.scan.request.model_class
    p = saved.fixed.model_copy(update={"m_chi": 8, "g_chi": 0.4732025259598567})
    failed = cls.vacuum_certificate(p)
    assert failed.vacuum == "short_lived" and failed.passed is False and failed.decay.status == "short_lived"
    assert saved.audit.valid
    text = track_report(saved)
    assert "Tree-level scalar vacuum" in text and "global" in text
    assert "unitarity and RG remain separate" in text
    row = saved.scan.points[0]
    observations = point_observations(row, cls.model_dump(mode="json"), EvidenceContext())
    theory = next(o for o in observations if o.observable == "scalar_tree_vacuum")
    assert theory.review == "not_required" and theory.required_confidence_level is None
    assert theory.excluded is None and theory.details["passed"] is True
    band = BandPoint(
        m_chi=p.m_chi,
        s_hat=3,
        events_at_unit=1,
        mu_hat=1,
        mu_68=(0.5, 2),
        z_local=3,
        point=p,
        fitted_value=p.g_chi,
        m_med=p.m_med,
        evaluation=row.model_copy(update={"point": p, "vacuum_certificate": failed}),
    )
    idea = SingleIdeaResult(
        request=SingleIdeaRequest(experiment="CDMS II Si (2013)", spec=saved.request.spec),
        band=[band],
        level="viable",
        summary="experimental reference",
    )
    assert "short_lived" in idea_report(idea) and "failed global-vacuum" in idea_report(idea)
    envelope = build("single_idea", idea, "sha")
    assert envelope.certificates["band_scalar_tree_vacua"][0]["passed"] is False


def test_new_certificate_export_and_legacy_defaults_preserve_saved_content(tmp_path: Path) -> None:
    saved = result()
    path = tmp_path / "study/result.json"
    path.parent.mkdir()
    path.write_text(saved.model_dump_json())
    save(path)
    archive = tmp_path / "vacuum.zip"
    export_run(path, archive)
    assert verify_bundle(archive).valid
    envelope = read(path)
    assert len(envelope.certificates["scalar_tree_vacua"]) == 4
    assert any(o.observable == "scalar_tree_vacuum" for o in envelope.observations)
    # A pre-M24 result remains without a certificate; reading/exporting never calculates it.
    data = saved.model_dump(mode="json")
    for p in data["scan"]["points"]:
        p.pop("vacuum_certificate")
    path = tmp_path / "old/result.json"
    path.parent.mkdir()
    path.write_text(json.dumps(data))
    envelope = read(path)
    assert not any(o.observable == "scalar_tree_vacuum" for o in envelope.observations)


def test_legacy_replay_retains_new_certificate_and_explains_its_separate_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib

    replay = importlib.import_module("adroit.evidence.replay")
    saved = result()
    row = saved.scan.points[0]
    saved.scan.points = [
        p.model_copy(update={"vacuum_certificate": None}) for p in saved.scan.points
    ]
    path = tmp_path / "old/result.json"
    path.parent.mkdir()
    path.write_text(saved.model_dump_json())
    save(path)
    archive = tmp_path / "old.zip"
    export_run(path, archive)
    expected = saved.scan.points[0].model_dump(mode="json")
    actual = row.model_dump(mode="json")
    monkeypatch.setattr(replay, "_calculate", lambda *args: (expected, actual))
    checked = replay.replay_bundle(archive)
    assert checked.status == "matched" and checked.actual["vacuum_certificate"]["passed"]
    assert any("legacy" in reason for reason in checked.reasons)
    # A saved new certificate is part of strict comparison and must not be ignored.
    expected = row.model_dump(mode="json")
    actual = row.model_dump(mode="json")
    actual["vacuum_certificate"]["passed"] = False
    monkeypatch.setattr(replay, "_calculate", lambda *args: (expected, actual))
    assert replay.replay_bundle(archive).status == "different"
