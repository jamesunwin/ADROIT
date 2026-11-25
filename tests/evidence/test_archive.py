import hashlib
import json
from pathlib import Path
import stat
import zipfile

import pytest
from typer.testing import CliRunner

from adroit.evidence.archive import export_run, read_bundle, verify_bundle
from adroit.evidence.archive_models import safe_member
from adroit.evidence.build import read
from adroit.orchestrator.cli import app


def mutate_zip(source: Path, destination: Path, change: object) -> None:
    with zipfile.ZipFile(source) as archive:
        files={name:archive.read(name) for name in archive.namelist()}
    change(files)
    with zipfile.ZipFile(destination,"w") as archive:
        for name,data in files.items():
            archive.writestr(name,data)


def test_archive_reconstructs_exact_pending_reasons_without_calculations(captured_file: Path,
                                                                      tmp_path: Path,
                                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("export or verification called a numerical calculation")
    monkeypatch.setattr("adroit.parameter_space.scan.evaluate",forbidden)
    before=captured_file.read_bytes()
    manifest=export_run(captured_file,tmp_path/"portable.zip")
    verified=verify_bundle(tmp_path/"portable.zip")
    assert verified.valid and len(verified.nodes)==1
    assert verified.nodes[0].summary==read(captured_file).summary
    assert verified.nodes[0].summary["verdict"]["crossings"][0]["pending"]
    assert captured_file.read_bytes()==before and verified.reproduction_status=="not_checked"
    _,files=read_bundle(tmp_path/"portable.zip")
    assert any(name.endswith("chosen.yaml") for name in files)
    assert manifest.nodes[0].workflow=="track1"
    with pytest.raises(ValueError,match="already exists"):
        export_run(captured_file,tmp_path/"portable.zip")


def test_missing_or_changed_input_is_reported_not_replaced(captured_file: Path,tmp_path: Path) -> None:
    (captured_file.parent/"chosen.yaml").write_text("value: changed")
    manifest=export_run(captured_file,tmp_path/"changed-input.zip")
    assert manifest.warnings and manifest.references[0].name=="chosen.yaml"
    verified=verify_bundle(tmp_path/"changed-input.zip",check_environment=True)
    assert verified.valid and verified.reproduction_status=="incomplete"
    assert any("chosen.yaml" in reason for reason in verified.reproduction_reasons)


@pytest.mark.parametrize("name",["../outside","/outside","a/../b","a//b","a/./b","C:/outside",r"a\b"])
def test_unsafe_paths_are_rejected_before_archive_reads(name: str,tmp_path: Path) -> None:
    with pytest.raises(ValueError,match="unsafe"):
        safe_member(name)
    path=tmp_path/"hostile.zip"
    with zipfile.ZipFile(path,"w") as archive:
        archive.writestr(name,"malicious")
    result=verify_bundle(path)
    assert not result.valid and "unsafe" in result.issues[0]
    assert not (tmp_path.parent/"outside").exists()


def test_symlink_archive_member_is_rejected(tmp_path: Path) -> None:
    path=tmp_path/"link.zip"
    with zipfile.ZipFile(path,"w") as archive:
        info=zipfile.ZipInfo("linked")
        info.external_attr=(stat.S_IFLNK|0o777)<<16
        archive.writestr(info,"../../outside")
    assert "links" in verify_bundle(path).issues[0]


@pytest.mark.parametrize("operation",["changed","missing","extra","version"])
def test_modified_missing_and_incompatible_artifacts(captured_file: Path,tmp_path: Path,operation: str) -> None:
    source=tmp_path/"good.zip"
    export_run(captured_file,source)
    target=tmp_path/f"{operation}.zip"
    def alter(files: dict[str, bytes]) -> None:
        if operation=="changed":
            files["studies/n0/result.json"]+=b" "
        elif operation=="missing":
            files.pop("studies/n0/result.json")
        elif operation=="extra":
            files["unrelated.txt"]=b"extra"
        else:
            manifest=json.loads(files["manifest.json"])
            manifest["schema_version"]=3
            files["manifest.json"]=json.dumps(manifest).encode()
    mutate_zip(source,target,alter)
    assert not verify_bundle(target).valid


def test_sidecar_request_mismatch_is_detected_even_with_updated_file_hashes(captured_file: Path,tmp_path: Path) -> None:
    from adroit.core.evidence import content_hash
    source=tmp_path/"good.zip"
    export_run(captured_file,source)
    def alter(files: dict[str, bytes]) -> None:
        name="studies/n0/evidence.json"
        envelope=json.loads(files[name])
        envelope["original_inputs"]["workers"]=2
        envelope["input_sha256"]=content_hash(envelope["original_inputs"])
        files[name]=json.dumps(envelope).encode()
        manifest=json.loads(files["manifest.json"])
        row=next(r for r in manifest["artifacts"] if r["path"]==name)
        row.update(sha256=hashlib.sha256(files[name]).hexdigest(),size=len(files[name]))
        files["manifest.json"]=json.dumps(manifest).encode()
    target=tmp_path/"wrong-request.zip"
    mutate_zip(source,target,alter)
    assert "request mismatch" in verify_bundle(target).issues[0]


def test_unrelated_files_secrets_and_private_prompts_are_not_exported(captured_file: Path,tmp_path: Path) -> None:
    (captured_file.parent/".env").write_text("do not include")
    (captured_file.parent/"unrelated.json").write_text('{"private":"do not include"}')
    (captured_file.parent/"assistance.json").write_text(json.dumps({"prompt_text":"private prompt",
        "response_text":"private answer","proposal":{"action":"review"},"cost_usd":.01}))
    export_run(captured_file,tmp_path/"default.zip")
    _,files=read_bundle(tmp_path/"default.zip")
    assert not any("assistance" in n or ".env" in n or "unrelated" in n for n in files)
    export_run(captured_file,tmp_path/"agents.zip",include_agents=True)
    _,files=read_bundle(tmp_path/"agents.zip")
    assert b"private prompt" not in files["studies/n0/assistance.json"]
    export_run(captured_file,tmp_path/"private.zip",include_agents=True,include_private_prompts=True)
    _,files=read_bundle(tmp_path/"private.zip")
    assert b"private prompt" in files["studies/n0/assistance.json"]
    with pytest.raises(ValueError,match="require"):
        export_run(captured_file,tmp_path/"bad-option.zip",include_private_prompts=True)
    (captured_file.parent/"assistance.json").write_text('{"api_key":"not exportable"}')
    with pytest.raises(ValueError,match="credentials"):
        export_run(captured_file,tmp_path/"secret.zip",include_agents=True)


def test_plot_symlink_cannot_import_unrelated_file(captured_file: Path,tmp_path: Path) -> None:
    from adroit.evidence.build import save
    from adroit.evidence.results import load_result
    kind,result=load_result(captured_file)
    outside=tmp_path/"outside.png"
    outside.write_bytes(b"private")
    (captured_file.parent/"plot.png").symlink_to(outside)
    result.plots=["plot.png"]
    captured_file.write_text(result.model_dump_json())
    save(captured_file,kind)
    with pytest.raises(ValueError,match="linked"):
        export_run(captured_file,tmp_path/"linked-export.zip")


def test_explicit_separate_advisory_file_is_optional_and_scrubbed(captured_file: Path,tmp_path: Path) -> None:
    review=tmp_path/"separate_review.json"
    review.write_text('{"cost_usd":0.1,"prompt_text":"private","supported_claims":[]}')
    export_run(captured_file,tmp_path/"with-review.zip",agent_evidence=[review])
    manifest,files=read_bundle(tmp_path/"with-review.zip")
    assert any(a.role=="advisory" for a in manifest.artifacts)
    assert json.loads(files["advisory/0.json"])=={"cost_usd":.1,"supported_claims":[]}


def test_legacy_cli_export_and_fresh_directory_verification(track1_file: Path,tmp_path: Path) -> None:
    runner=CliRunner()
    archive=tmp_path/"move"/"saved.zip"
    outcome=runner.invoke(app,["evidence","export",str(track1_file),"--out",str(archive)])
    assert outcome.exit_code==0,outcome.output
    fresh=tmp_path/"fresh"
    fresh.mkdir()
    moved=fresh/"saved.zip"
    archive.replace(moved)
    outcome=runner.invoke(app,["evidence","verify",str(moved)])
    assert outcome.exit_code==0,outcome.output
    assert json.loads(outcome.output)["nodes"][0]["provenance"]=="legacy_unknown"
