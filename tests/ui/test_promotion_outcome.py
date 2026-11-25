"""What a promotion made, said on its run's page (the owner, 2026-11-19: three promotions of an inelastic candidate
made no study, and each page said "Promotion complete. Each promoted model is its own study"; a paid one had not asked
the model builder, without saying so)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from adroit.orchestrator import cli, promote, signal
from adroit.orchestrator.preflight import JOB_OUTPUT
from adroit.ui import engine, outcomes

SI = "CDMS II Si (2013)"
INELASTIC = "O1s@1000,d=300"


def _parent(tmp_path: Path) -> Path:
    """A Signal-best-fits run whose only candidate is inelastic, which no completion reproduces."""
    request = signal.SignalRequest(experiment=SI, null_modules=[], toys=200, leaders=1, candidates=[
        signal.Candidate(label=INELASTIC, card_id="O1", isospin="s", mass_gev=1000.0, splitting_kev=300.0)])
    parent = tmp_path / "runs" / "signal_run"
    parent.mkdir(parents=True)
    (parent / "result.json").write_text(signal.run(request).model_dump_json())
    return parent


def _job(root: Path, parent: Path, status: str = "completed") -> tuple[Path, engine.Job]:
    folder = parent / "children" / "promotion_job"
    folder.mkdir(parents=True)
    job = engine.Job(title="promote", kind="promotion", command=["promote", str(parent), INELASTIC], folder=str(folder),
                     status=status, returncode=0 if status == "completed" else None)
    return folder, job


def _record(parent: Path, folder: Path, children: int, undetermined: dict[str, str]) -> Path:
    record = parent / "promotion_x.json"
    made = [promote.Child(label="O1s@10", model=f"model_{i}", origin="simplified completion",
                          folder=str(parent / "children" / f"model_{i}")) for i in range(children)]
    record.write_text(promote.Promotion(parent=str(parent), labels=["O1s@10"], children=made,
                                        undetermined=undetermined).model_dump_json())
    (folder / JOB_OUTPUT).write_text(json.dumps({"path": str(record.resolve()),
                                                 "sha256": hashlib.sha256(record.read_bytes()).hexdigest()}))
    return record


def test_a_promotion_that_made_no_study_says_so_with_why(tmp_path):
    root = tmp_path / "runs"
    parent = root / "signal_run"
    folder, job = _job(root, parent)
    _record(parent, folder, 0, {INELASTIC: "inelastic (δ = 300 keV): the simplified completions are elastic"})
    out = outcomes.promotion_outcome(root, folder, job)
    assert out.headline == "Promotion complete: no study was made"
    assert "No candidate could be studied. O1s@1000,d=300: inelastic (δ = 300 keV)" in out.detail
    assert out.primary.label == "Back to the signal study" and out.primary.target == "/study?path=signal_run"
    assert "Each promoted model is its own study" not in out.detail


def test_a_promotion_that_made_studies_counts_them_and_names_what_has_none(tmp_path):
    root = tmp_path / "runs"
    parent = root / "signal_run"
    folder, job = _job(root, parent)
    _record(parent, folder, 2, {"O1v@10": "isovector: no computable simplified completion produces it"})
    out = outcomes.promotion_outcome(root, folder, job)
    assert out.headline == "Promotion complete: 2 studies made"
    assert out.detail.startswith("2 studies, each listed under the signal study. Without a study: O1v@10: isovector")
    assert out.primary.label == "Open the signal study and its promoted studies"


def test_a_promotion_whose_record_cannot_be_read_claims_no_study(tmp_path):
    root = tmp_path / "runs"
    parent = root / "signal_run"
    folder, job = _job(root, parent)
    out = outcomes.promotion_outcome(root, folder, job)                       # an older run: no record named
    assert out.headline == "Promotion complete" and "cannot be read here" in out.detail
    assert "Each promoted model is its own study" not in out.detail
    record = _record(parent, folder, 1, {})
    record.write_text(record.read_text().replace("model_0", "model_9"))       # replaced since the run wrote it
    out = outcomes.promotion_outcome(root, folder, job)
    assert "its record has changed since this run wrote it" in out.detail


def test_an_unfinished_promotion_is_said_as_before(tmp_path):
    root = tmp_path / "runs"
    parent = root / "signal_run"
    folder, job = _job(root, parent, status="running")
    out = outcomes.promotion_outcome(root, folder, job)
    assert out.output == "none" and out.primary is None


def test_the_promote_command_names_its_record_and_says_the_builder_was_not_asked(tmp_path, monkeypatch):
    parent = _parent(tmp_path)
    job_folder = parent / "children" / "promotion_job"
    job_folder.mkdir(parents=True)
    monkeypatch.setenv("ADROIT_JOB_FOLDER", str(job_folder))
    done = CliRunner().invoke(cli.app, ["promote", str(parent), INELASTIC, "--toys", "200", "--grid", "4",
                                        "--mass-points", "2"])
    assert done.exit_code == 0, done.output
    made, without, why = outcomes.promoted(job_folder)
    assert (made, why) == (0, "") and without[INELASTIC].startswith("inelastic (δ = 300 keV)")
    assert "model builder was not asked" not in without[INELASTIC]            # no budget: the builder is not in play
    job = engine.Job(title="promote", kind="promotion", command=["promote", str(parent), INELASTIC],
                     folder=str(job_folder), status="completed", returncode=0)
    assert outcomes.promotion_outcome(tmp_path / "runs", job_folder, job).headline == \
        "Promotion complete: no study was made"


def test_with_a_budget_an_inelastic_candidate_says_the_builder_was_not_asked(tmp_path):
    parent = _parent(tmp_path)

    class NeverCalled:
        """A stand-in for the budgeted client: the builder must not be asked for an inelastic candidate."""
        def complete_structured(self, *args, **kwargs):
            raise AssertionError("the model builder was asked")

    out = promote.promote(parent, [INELASTIC], {"toys": 200, "grid": 4, "masses": 2}, llm=NeverCalled())
    assert out.children == []
    assert out.undetermined[INELASTIC].endswith(
        "the model builder was not asked: it is asked only for an elastic candidate with the card's own couplings")
    assert "the model builder was not asked" in promote.report(out)
