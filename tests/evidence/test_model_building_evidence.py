"""Rep-2: idea and Lagrangian results saved with their evidence and exported as bundles (the batch plan's §8)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from adroit.core.model_spec import ModelSpec
from adroit.evidence.archive import export_run, verify_bundle
from adroit.evidence.build import read
from adroit.evidence.results import load_result
from adroit.orchestrator import ideas, runs
from tests.evidence.test_archive import mutate_zip
from tests.orchestrator.test_lagrangian import derivation, needs_directdm, spec as v1_spec


def singlet() -> ModelSpec:
    return ModelSpec.model_validate({"name": "singlet", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1},
        {"name": "S", "role": "mediator", "spin": 0, "self_conjugate": True}]})


@pytest.fixture(scope="module")
def idea_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out, _ = runs.idea(ideas.IdeaRequest(fields_spec=singlet()), folder=tmp_path_factory.mktemp("idea") / "singlet",
                       name="singlet")
    return out


def _restamp(files: dict[str, bytes], names: list[str]) -> None:
    """Make the manifest's hashes agree with changed files, as a forger would."""
    manifest = json.loads(files["manifest.json"])
    for row in manifest["artifacts"]:
        if row["path"] in names:
            row.update(sha256=hashlib.sha256(files[row["path"]]).hexdigest(), size=len(files[row["path"]]))
    files["manifest.json"] = json.dumps(manifest).encode()


def test_an_idea_run_saves_its_evidence_with_no_experiment_among_its_sources(idea_run: Path) -> None:
    envelope = read(idea_run / "result.json")
    assert envelope.workflow == "idea" and envelope.context.origin == "captured" and not envelope.warnings
    assert not [s for s in envelope.context.sources if s.id.startswith("experiment:")]
    assert set(envelope.summary) == {"models", "dropped"} and envelope.observations == []
    assert [m["name"] for m in envelope.engine_mapping["models"]] == ["singlet"]
    assert len(envelope.certificates["audits"]) == 1
    assert load_result(idea_run / "result.json")[0] == "idea"         # detected without the sidecar's word


def test_an_idea_run_exports_with_its_model_files_and_verifies(idea_run: Path, tmp_path: Path) -> None:
    bundle = tmp_path / "idea.zip"
    manifest = export_run(idea_run, bundle)
    names = [a.path for a in manifest.artifacts]
    assert manifest.nodes[0].workflow == "idea" and "studies/n0/report.md" in names
    written = sorted(p.name for p in (idea_run / "models").glob("*.yaml"))
    assert written and [n for n in names if n.startswith("studies/n0/models/")] == [
        f"studies/n0/models/{n}" for n in written]
    checked = verify_bundle(bundle)
    assert checked.valid and checked.nodes[0].provenance == "captured" and checked.nodes[0].summary["dropped"] == []


def test_a_changed_idea_conclusion_is_caught_even_with_the_hashes_redone(idea_run: Path, tmp_path: Path) -> None:
    source, target = tmp_path / "good.zip", tmp_path / "forged.zip"
    export_run(idea_run, source)

    def alter(files: dict[str, bytes]) -> None:
        result = json.loads(files["studies/n0/result.json"])
        result["dropped"] = ["a proposal said to be dropped"]
        files["studies/n0/result.json"] = json.dumps(result).encode()
        envelope = json.loads(files["studies/n0/evidence.json"])
        envelope["result_sha256"] = hashlib.sha256(files["studies/n0/result.json"]).hexdigest()
        files["studies/n0/evidence.json"] = json.dumps(envelope).encode()
        _restamp(files, ["studies/n0/result.json", "studies/n0/evidence.json"])
    mutate_zip(source, target, alter)
    checked = verify_bundle(target)
    assert not checked.valid and "conclusion mismatch" in checked.issues[0]


def test_an_idea_result_saved_before_rep2_exports_as_legacy(tmp_path: Path) -> None:
    folder = tmp_path / "old_idea"
    folder.mkdir()
    (folder / "result.json").write_text(ideas.run(ideas.IdeaRequest(fields_spec=singlet())).model_dump_json())
    bundle = tmp_path / "old.zip"
    export_run(folder, bundle)
    checked = verify_bundle(bundle)
    assert checked.valid and checked.nodes[0].provenance != "captured"
    assert any("calculation provenance" in r for r in checked.reproduction_reasons)


def _model_yaml(**extra: object) -> str:
    from adroit.orchestrator import lagrangian
    request = lagrangian.LagrangianRequest(spec=v1_spec(), derivation=derivation(), **extra)
    return yaml.safe_dump(request.model_dump(mode="json"), allow_unicode=True)


def test_a_stopped_lagrangian_exports_and_its_stop_is_a_review_task(tmp_path: Path) -> None:
    broken = v1_spec().model_dump(mode="json")
    broken["fields"][1]["charges"] = {"electric_charge": 1.0}
    request = yaml.safe_load(_model_yaml())
    request["spec"] = broken
    out, _ = runs.lagrangian(yaml.safe_dump(request), folder=tmp_path / "stopped")
    envelope = read(out / "result.json")
    assert envelope.workflow == "lagrangian" and envelope.summary["status"].startswith("stopped")
    queue = envelope.certificates["review_queue"]
    assert any(a["role"] == "study" and a["blocks_conclusion"] and "deterministic checks" in task["reason"]
               for task in queue["tasks"] for a in task["affected"])
    bundle = tmp_path / "stopped.zip"
    export_run(out, bundle)
    assert verify_bundle(bundle).valid


@needs_directdm
def test_a_complete_lagrangian_exports_its_interactions_and_matches(tmp_path: Path) -> None:
    out, _ = runs.lagrangian(_model_yaml(masses_gev=[100.0], run_exclusion=False), folder=tmp_path / "v1")
    envelope = read(out / "result.json")
    assert envelope.summary["status"] == "complete" and envelope.context.origin == "captured"
    assert set(envelope.engine_mapping["interactions"]) == {"100"} and envelope.engine_mapping["card_matches"]
    assert not [s for s in envelope.context.sources if s.id.startswith("experiment:")]   # no exclusion was run
    bundle = tmp_path / "v1.zip"
    export_run(out, bundle)
    checked = verify_bundle(bundle)
    assert checked.valid and checked.nodes[0].workflow == "lagrangian"


def test_a_copy_in_the_evidence_that_disagrees_with_the_result_does_not_verify(idea_run: Path, tmp_path: Path) -> None:
    """The batch audit's B20-03: verification compared the conclusion only, so a certificate or engine mapping that
    no longer said what the result says (a Lagrangian's changed Wilson coefficients) still verified. Every copy is now
    checked against the typed result."""
    source, target = tmp_path / "good.zip", tmp_path / "forged.zip"
    export_run(idea_run, source)

    def alter(files: dict[str, bytes]) -> None:
        envelope = json.loads(files["studies/n0/evidence.json"])
        envelope["engine_mapping"]["models"][0]["name"] = "another model"
        files["studies/n0/evidence.json"] = json.dumps(envelope).encode()
        _restamp(files, ["studies/n0/evidence.json"])
    mutate_zip(source, target, alter)
    checked = verify_bundle(target)
    assert not checked.valid and "copy mismatch" in checked.issues[0]


def test_an_edited_model_file_is_flagged_and_an_unreadable_one_refused(idea_run: Path, tmp_path: Path) -> None:
    """B20-03's attachments and B20-04: a model file that is not the one the run wrote is exported with a warning;
    one holding two YAML documents (a credential check that cannot be trusted) is refused."""
    import shutil
    folder = tmp_path / "copy"
    shutil.copytree(idea_run, folder)
    model = sorted((folder / "models").glob("*.yaml"))[0]
    data = yaml.safe_load(model.read_text())
    data["spec"]["name"] = "edited"
    model.write_text(yaml.safe_dump(data))
    manifest = export_run(folder, tmp_path / "edited.zip")
    assert any("not a model this run built" in w for w in manifest.warnings)
    model.write_text(model.read_text() + "---\napi_key: synthetic\n")
    with pytest.raises(ValueError, match="2 YAML documents"):
        export_run(folder, tmp_path / "two.zip")


def test_a_legal_yaml_merge_is_read_and_a_repeated_explicit_key_still_refused(idea_run: Path, tmp_path: Path) -> None:
    """The recheck's RB20-03 (2026-10-20), its control: the strict loader had built YAML's merge key (<<) as a key and
    refused a legal merged mapping, so a model attachment written with one could not be exported. A merge is now read
    as the safe loader reads it; an explicit key may override a merged one; a repeated explicit key is still refused."""
    import shutil
    from adroit.evidence import archive
    merged = "base: &b\n  m: 1.0\n  g: 2.0\nmodel:\n  <<: *b\n  g: 3.0\n"
    assert archive._structured("m.yaml", merged.encode()) == yaml.safe_load(merged)
    with pytest.raises(ValueError, match="repeated"):
        archive._structured("m.yaml", (merged + "  g: 4.0\n").encode())
    folder = tmp_path / "copy"
    shutil.copytree(idea_run, folder)
    model = sorted((folder / "models").glob("*.yaml"))[0]
    model.write_text("defaults: &d\n  note: merged\n" + model.read_text() + "extra:\n  <<: *d\n")
    export_run(folder, tmp_path / "merged.zip")                               # exported, not refused
    import zipfile
    with zipfile.ZipFile(tmp_path / "merged.zip") as bundle:
        assert any(name.endswith(model.name) for name in bundle.namelist())
