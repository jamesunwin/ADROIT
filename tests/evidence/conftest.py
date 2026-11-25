from pathlib import Path

import pytest

from adroit.core.evidence import EvidenceContext, SourceEvidence, InputArtifact
from adroit.evidence.build import save
from adroit.evidence.runtime import file_hash
from adroit.model_building.audit import audit
from adroit.orchestrator.track1 import Track1Result, for_portal
from adroit.parameter_space.classes import Point
from adroit.parameter_space.scan import Axis, PointResult, ScanRequest, ScanResult
from adroit.parameter_space.verdict import classify, Verdict


@pytest.fixture
def context() -> EvidenceContext:
    return EvidenceContext(origin="captured", identity="test-calculation-context", code_sha256="test-code",
        sources=[SourceEvidence(id="planck-2018-omega", reference="Planck", review="unreviewed"),
                 SourceEvidence(id="experiment:detector", reference="detector", review="not_required")])


@pytest.fixture
def point_result() -> PointResult:
    return PointResult(point=Point(m_chi=50, m_med=300, g_chi=.2, g_q=.1, g_l=0),
        omega_h2=.12, dd_kind="SI", dd_sigma_cm2=0., dd_limit_cm2=None,
        excluded={"direct detection": None, "perturbativity": False},
        pending=["direct detection: backend unavailable"], ratios={})


@pytest.fixture
def track1_file(tmp_path: Path, point_result: PointResult) -> Path:
    request = for_portal("higgs_portal_scalar", literature=False, workers=1)
    scan_request = ScanRequest(model_class=request.model_class, fixed=point_result.point,
        x=Axis(parameter="m_chi", low=10, high=20, n=2),
        y=Axis(parameter="g_chi", low=.1, high=.2, n=2))
    crossing = classify(scan_request.model_class, point_result)
    verdict = Verdict(level="viable_pending", summary="saved point pending", target=.12, crossings=[crossing])
    result = Track1Result(request=request, audit=audit(request.spec), fixed=point_result.point,
        scan=ScanResult(request=scan_request, xs=[10,20], ys=[.1,.2], points=[point_result]), verdict=verdict)
    path = tmp_path / "study" / "result.json"
    path.parent.mkdir()
    path.write_text(result.model_dump_json(indent=1))
    path.with_name("report.md").write_text("saved report")
    return path


@pytest.fixture
def captured_file(track1_file: Path, context: EvidenceContext, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr("adroit.evidence.build.finish", lambda c, read=None, consumed=None: c)
    data = track1_file.parent / "chosen.yaml"
    data.write_text("value: 0\n")
    context.inputs = [InputArtifact(name="chosen.yaml", location=str(data), sha256=file_hash(data),
                                   role="user_input", redistribution="user_selected")]
    save(track1_file, context=context)
    return track1_file
