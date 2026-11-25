"""R1 (audit C1): an evidence bundle or a saved run is data. A crafted model class can neither run code nor be
taken as the engine: replay and resume rebuild the class from the typed model and refuse a different one."""

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from adroit.evidence.archive import export_run, verify_bundle
from adroit.evidence.replay import replay_bundle
from adroit.parameter_space.library import INERT_DOUBLET


def _payload(marker: Path) -> str:
    """The audit's proof of concept: make a folder, then stop before any engine runs."""
    return ("([c for c in ().__class__.__base__.__subclasses__() if c.__name__=='_wrap_close'][0]"
            f".__init__.__globals__['mkdir']({str(marker)!r}), 1/0)[1]")


def _craft(archive: Path, out: Path, model_class: dict) -> Path:
    """Replace the saved engine in a Track 1 bundle and re-hash everything, as an attacker would."""
    with zipfile.ZipFile(archive) as z:
        files = {n: z.read(n) for n in z.namelist()}
    manifest = json.loads(files["manifest.json"])
    node = manifest["nodes"][0]
    result = json.loads(files[node["result_path"]])
    result["scan"]["request"]["model_class"] = model_class      # the saved request must match the envelope's
    files[node["result_path"]] = json.dumps(result, indent=1).encode()
    envelope = json.loads(files[node["evidence_path"]])
    envelope["result_sha256"] = hashlib.sha256(files[node["result_path"]]).hexdigest()
    files[node["evidence_path"]] = json.dumps(envelope, indent=1).encode()
    for artifact in manifest["artifacts"]:
        if artifact["path"] in (node["result_path"], node["evidence_path"]):
            artifact["sha256"] = hashlib.sha256(files[artifact["path"]]).hexdigest()
            artifact["size"] = len(files[artifact["path"]])
    files["manifest.json"] = json.dumps(manifest, indent=1).encode()
    with zipfile.ZipFile(out, "w") as w:
        for name, data in files.items():
            w.writestr(name, data)
    return out


def test_a_crafted_ufo_expression_is_refused_and_runs_no_code(track1_file: Path, tmp_path: Path) -> None:
    archive = tmp_path / "track1.zip"
    export_run(track1_file, archive)
    marker = tmp_path / "MARKER_created_by_bundle_expression"
    crafted = {**INERT_DOUBLET.model_dump(mode="json"), "name": "crafted", "parameters": {"MX": _payload(marker)}}
    bundle = _craft(archive, tmp_path / "crafted.zip", crafted)
    verified = verify_bundle(bundle)
    assert not verified.valid and verified.assurance.startswith("not internally consistent")
    issue = verified.issues[0]
    assert "does not validate" in issue and "UFOPortal.parameters" in issue and len(issue) <= 2000
    with pytest.raises(ValueError):
        replay_bundle(bundle)
    assert not marker.exists()
    from typer.testing import CliRunner
    from adroit.orchestrator import cli
    refused = CliRunner().invoke(cli.app, ["evidence", "replay", str(bundle)])
    assert refused.exit_code == 2 and "does not validate" in refused.output and len(refused.output) < 4000
    assert not marker.exists()


def test_a_crafted_model_folder_is_refused(track1_file: Path, tmp_path: Path) -> None:
    archive = tmp_path / "track1.zip"
    export_run(track1_file, archive)
    crafted = {**INERT_DOUBLET.model_dump(mode="json"), "model_dir": "../../Downloads/evil_ufo"}
    bundle = _craft(archive, tmp_path / "crafted.zip", crafted)
    assert not verify_bundle(bundle).valid
    with pytest.raises(ValueError):
        replay_bundle(bundle)


def test_a_well_formed_but_different_engine_is_not_replayed(track1_file: Path, tmp_path: Path) -> None:
    archive = tmp_path / "track1.zip"
    export_run(track1_file, archive)
    verified = verify_bundle(archive)
    assert verified.valid and verified.assurance.startswith("internally consistent; provenance not verified")
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read("manifest.json"))
        saved = json.loads(z.read(manifest["nodes"][0]["result_path"]))["scan"]["request"]["model_class"]
    forged = {**saved, "name": "a forged engine"}
    bundle = _craft(archive, tmp_path / "forged.zip", forged)
    assert verify_bundle(bundle).valid                     # internally consistent, so verify cannot tell
    replay = replay_bundle(bundle)
    assert replay.status == "incomplete" and "never run as given" in replay.reasons[0]
    assert "untrusted" in replay.trust


def test_resume_refuses_a_tampered_model_class(tmp_path: Path) -> None:
    from adroit.core.checkpoint import Manifest
    from adroit.orchestrator.track1 import for_portal, saved_request
    request = for_portal("higgs_portal_scalar", literature=False, workers=1)
    folder = tmp_path / "run"
    (folder / ".track1-checkpoint").mkdir(parents=True)

    def save(inputs: dict) -> None:
        manifest = Manifest(identity="x", inputs=inputs, dependencies={})
        (folder / ".track1-checkpoint/manifest.json").write_text(manifest.model_dump_json())
    save(request.model_dump(mode="json"))
    assert saved_request(folder) == request
    forged = request.model_dump(mode="json")
    forged["model_class"]["name"] = "a forged engine"
    save(forged)
    with pytest.raises(ValueError, match="never run as given"):
        saved_request(folder)
    marker = tmp_path / "MARKER"
    forged["model_class"] = {**INERT_DOUBLET.model_dump(mode="json"), "parameters": {"MX": _payload(marker)}}
    save(forged)
    with pytest.raises(ValueError):
        saved_request(folder)
    assert not marker.exists()
    from typer.testing import CliRunner
    from adroit.orchestrator import cli
    refused = CliRunner().invoke(cli.app, ["track1", "--resume", "--out", str(folder)])
    assert refused.exit_code == 2 and "does not validate" in refused.output and len(refused.output) < 4000


def test_resume_through_the_command_line_explains_the_refusal(tmp_path: Path) -> None:
    from typer.testing import CliRunner
    from adroit.core.checkpoint import Manifest
    from adroit.orchestrator import cli
    from adroit.orchestrator.track1 import for_portal
    forged = for_portal("higgs_portal_scalar", literature=False, workers=1).model_dump(mode="json")
    forged["model_class"]["name"] = "a forged engine"
    (tmp_path / ".track1-checkpoint").mkdir()
    (tmp_path / ".track1-checkpoint/manifest.json").write_text(
        Manifest(identity="x", inputs=forged, dependencies={}).model_dump_json())
    out = CliRunner().invoke(cli.app, ["track1", "--resume", "--out", str(tmp_path)])
    assert out.exit_code != 0 and "never run as given" in out.output


def test_replay_and_verify_say_what_they_establish(track1_file: Path, tmp_path: Path) -> None:
    from typer.testing import CliRunner
    from adroit.orchestrator import cli
    archive = tmp_path / "track1.zip"
    export_run(track1_file, archive)
    verified = CliRunner().invoke(cli.app, ["evidence", "verify", str(archive)])
    assert "provenance not verified" in verified.output
    replayed = CliRunner().invoke(cli.app, ["evidence", "replay", str(archive)])
    assert "untrusted data" in replayed.stderr
