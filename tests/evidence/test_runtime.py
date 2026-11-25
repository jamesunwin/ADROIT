from pathlib import Path

import pytest

from adroit.core.dm_state import ConstraintRecord, ConstraintClass
from adroit.core.evidence import EvidenceContext
from adroit.evidence.runtime import capture, capture_request, finish, file_hash


def test_capture_binds_sources_inputs_and_software_without_credentials(tmp_path: Path,
                                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    from adroit.evidence import runtime
    from adroit.constraints import database
    root=tmp_path/"project"
    root.mkdir()
    data=root/"table.yaml"
    data.write_text("value: 0\n")
    user=tmp_path/"anomaly.yaml"
    user.write_text("selected: true\n")
    record=ConstraintRecord(id="test",name="test",source="paper",constraint_class=ConstraintClass.collider,
                            data_file="table.yaml")
    monkeypatch.setattr(runtime,"PROJECT_ROOT",root)
    monkeypatch.setattr(runtime,"_package_inputs",lambda:[data])
    monkeypatch.setattr(database,"records",lambda:(record,))
    monkeypatch.setattr("adroit.orchestrator.track1_identity.dependencies",lambda:{"python":"test-python",
        "versions":{"numpy":"test"},"inputs":{"adroit":{"path":str(root),"sha256":"same-code"},
        "missing backend":{"path":str(root/"missing"),"sha256":"missing"}}})
    first=capture([user])
    assert first.origin=="captured" and first.sources[0].review=="unreviewed"
    assert first.sources[0].data_sha256==file_hash(data)
    assert next(b for b in first.backends if b.name=="missing backend").status=="unavailable"
    assert finish(first).origin=="captured"
    data.write_text("value: 1\n")
    changed=finish(first)
    assert changed.origin=="changed_during_run" and changed.sources==first.sources
    assert changed.identity==first.identity and changed.notes
    assert finish(EvidenceContext()).origin=="legacy_unknown"
    with pytest.raises(ValueError):
        capture([tmp_path])
    secret=tmp_path/".env"
    secret.write_text("not read")
    with pytest.raises(ValueError):
        capture([secret])


def test_request_capture_selects_only_declared_anomaly_inputs(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    from adroit.orchestrator.signal import SignalRequest
    from adroit.evidence import runtime
    file=tmp_path/"anomaly.yaml"
    seen=[]
    def fake(files: list[Path],experiments: list[str]) -> EvidenceContext:
        seen.append((files,experiments))
        return EvidenceContext()
    monkeypatch.setattr(runtime,"capture",fake)
    request=SignalRequest(experiment=f"record:{file}",null_modules=["DEAP-3600 (2019)"])
    assert capture_request(request).origin=="legacy_unknown"
    assert seen==[([file],[request.experiment,"DEAP-3600 (2019)"])]
