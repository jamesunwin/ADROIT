"""R-24's kit: the opt-in command log and the declared analysis of the usability sessions."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from adroit.evaluation import assistance_timing as timing
from adroit.evaluation import usability, usage_log
from adroit.orchestrator.cli import app

T0 = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
HASH = "a" * 64


def session(participant: str, task: str, condition: str, seconds: float, success: bool = True,
            attest: bool = True) -> timing.ResearcherSession:
    s = timing.start(participant, task, HASH, condition, now=T0)
    return timing.transition(s, "finish", attest=attest, success=success, now=T0 + timedelta(seconds=seconds))


def test_the_sus_score_runs_from_0_to_100() -> None:
    assert usability.sus_score([3] * 10) == 50.0
    assert usability.sus_score([5, 1] * 5) == 100.0 and usability.sus_score([1, 5] * 5) == 0.0
    with pytest.raises(ValueError):
        usability.sus_score([3] * 9 + [6])


def test_the_analysis_pairs_task_by_task_and_names_what_it_leaves_out() -> None:
    unsuccessful = session("P02", "T2", "assisted", 300, success=False)
    sessions = [session("P01", "T1", "manual", 1800), session("P01", "T1", "assisted", 600),
                session("P02", "T1", "manual", 1200), session("P02", "T1", "assisted", 900),
                session("P02", "T2", "manual", 2400), unsuccessful]
    report = usability.analyse(sessions, [usability.SusResponse(participant="P01", answers=[4, 2] * 5)])
    t1, t2 = report.tasks
    assert (t1.task, t1.pairs, t1.seconds_saved, t1.median_seconds_saved) == ("T1", 2, [1200.0, 300.0], 750.0)
    assert t2.pairs == 0 and t2.success == {"manual": "1 of 1", "assisted": "0 of 1"}
    assert unsuccessful.id in report.excluded and len(report.excluded) == 2      # its unpaired manual partner too
    assert report.pairs == 2 and report.wilcoxon_p is None and report.sus == {"P01": 75.0}
    text = usability.markdown(report)
    assert "| T1 | 2 | 1200 s, 300 s | 750 s | 2 of 2 | 2 of 2 |" in text and "no test (fewer than 6" in text


def test_six_pairs_are_tested_two_sided() -> None:
    from scipy.stats import wilcoxon
    saved = [600, 300, -120, 900, 450, 50]
    sessions = [x for k, d in enumerate(saved) for x in (session(f"P{k}", "T1", "manual", 1000 + d),
                                                          session(f"P{k}", "T1", "assisted", 1000))]
    report = usability.analyse(sessions)
    assert report.wilcoxon_p == pytest.approx(wilcoxon(saved).pvalue) and report.quartiles_seconds_saved


def test_a_command_is_named_without_its_arguments() -> None:
    import typer.main
    group = typer.main.get_command(app)
    assert usage_log.command_path(group, "evidence", ["evidence", "export", "/private/x", "--out", "b.zip"]) == \
        "evidence export"
    assert usage_log.command_path(group, "track1", ["track1", "models/secret_model.yaml"]) == "track1"
    assert usage_log.command_path(group, "assist-session", []) == "assist-session"


def test_the_log_is_off_unless_asked_and_keeps_only_name_time_outcome_and_label(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder, log = tmp_path / "secret_folder", tmp_path / "usage.jsonl"
    folder.mkdir()
    monkeypatch.delenv(usage_log.LOG, raising=False)
    assert CliRunner().invoke(app, ["assist-session", "summary", str(folder)]).exit_code == 0 and not log.exists()
    monkeypatch.setenv(usage_log.LOG, str(log))
    monkeypatch.setenv(usage_log.SESSION, "P01-T1-assisted")
    monkeypatch.setattr(sys, "argv", ["adroit", "assist-session", "summary", str(folder)])
    assert CliRunner().invoke(app, ["assist-session", "summary", str(folder)]).exit_code == 0
    monkeypatch.setenv(usage_log.SESSION, "someone@example.org")
    monkeypatch.setattr(sys, "argv", ["adroit", "evidence", "verify", str(folder / "none.zip")])
    assert CliRunner().invoke(app, ["evidence", "verify", str(folder / "none.zip")]).exit_code != 0
    first, second = usage_log.read(log)
    assert (first.command, first.outcome, first.session) == ("assist-session summary", "ok", "P01-T1-assisted")
    assert (second.command, second.outcome, second.session) == ("evidence verify", "error", "")
    assert "secret_folder" not in log.read_text() and "example.org" not in log.read_text()


def test_the_report_command_reads_sessions_answers_and_logs(tmp_path: Path) -> None:
    folder = tmp_path / "sessions"
    for k, s in enumerate([session("P01", "T1", "manual", 1500), session("P01", "T1", "assisted", 500)]):
        timing.save(s, folder / f"{k}.json")
    sus = tmp_path / "sus.json"
    sus.write_text(json.dumps([{"participant": "P01", "answers": [5, 1] * 5}]))
    log = tmp_path / "usage.jsonl"
    usage_log.record(log, "track1", T0, 42.0, "ok")
    out = tmp_path / "report.md"
    args = ["assist-session", "report", str(folder), "--sus", str(sus), "--usage", str(log), "--out", str(out)]
    run = CliRunner().invoke(app, args)
    assert run.exit_code == 0 and "| T1 | 1 | 1000 s | 1000 s | 1 of 1 | 1 of 1 |" in out.read_text()
    assert "P01 100.0" in run.output and "| (no label) | 1 | 42 s | 0 |" in run.output
    assert CliRunner().invoke(app, args).exit_code != 0                      # the report is never overwritten


def test_the_task_table_holds_each_statements_hash() -> None:
    import hashlib
    import re
    docs = Path(__file__).resolve().parents[2] / "docs" / "usability"
    listed = dict(re.findall(r"\[`tasks/(T\d)\.txt`\]\(tasks/T\d\.txt\) \| `([0-9a-f]{64})`", (docs / "tasks.md").read_text()))
    assert sorted(listed) == ["T1", "T2", "T3", "T4"]
    for task, digest in listed.items():
        assert hashlib.sha256((docs / "tasks" / f"{task}.txt").read_bytes()).hexdigest() == digest, task


def _costly(participant, task, condition, seconds, success=True, cost=0.0):
    return session(participant, task, condition, seconds, success).model_copy(update={"api_cost_usd": cost})


def test_a_retry_is_a_repeat_not_a_pair_and_every_assisted_session_is_costed():
    """The batch audit's B20-05: a failed assisted attempt ($2) and its successful retry ($0.50) had paired as one
    session costing $0.50, and an unpaired failed session's $3 had vanished from the cost."""
    retried = [_costly("P01", "T1", "manual", 100), _costly("P01", "T1", "assisted", 10, False, 2.0),
               _costly("P01", "T1", "assisted", 90, True, 0.5)]
    report = usability.analyse(retried)
    assert report.pairs == 0 and report.api_cost_usd == pytest.approx(2.5)
    assert all("repeated (1 manual, 2 assisted" in why for why in report.excluded.values()) and len(report.excluded) == 3
    unpaired = usability.analyse([_costly("P01", "T1", "manual", 100), _costly("P01", "T1", "assisted", 80),
                                  _costly("P02", "T1", "assisted", 80, False, 3.0)])
    assert unpaired.pairs == 1 and unpaired.api_cost_usd == pytest.approx(3.0)
    assert list(unpaired.excluded.values()) == ["unpaired"]


def test_the_test_is_on_participants_not_on_their_repeated_tasks():
    """B20-06: four participants with the same saving on each of their four tasks had given 16 'independent' pairs
    and p = 0.0004; one observation per participant gives no test below six participants."""
    sessions = [s for who, saved in (("P01", 10), ("P02", 20), ("P03", 30), ("P04", 40)) for task in ("T1", "T2", "T3", "T4")
                for s in (session(who, task, "manual", 100), session(who, task, "assisted", 100 - saved))]
    report = usability.analyse(sessions)
    assert report.pairs == 16 and report.wilcoxon_p is None
    assert report.participants == {"P01": 10.0, "P02": 20.0, "P03": 30.0, "P04": 40.0}
    assert "no test (fewer than 6 participants" in usability.markdown(report)


@pytest.mark.parametrize("label, kept", [("P03", True), ("P03-T2", True), ("P03-T2-assisted", True),
                                         ("James_Unwin", False), ("P03-T2-other", False), ("p03", False)])
def test_only_the_protocols_pseudonyms_are_recorded(tmp_path, monkeypatch, label, kept):
    """B20-07: a name written with an underscore had passed a character filter."""
    monkeypatch.setenv(usage_log.SESSION, label)
    entry = usage_log.record(tmp_path / "log.jsonl", "track1", T0, 1.0, "ok")
    assert entry.session == (label if kept else "")
