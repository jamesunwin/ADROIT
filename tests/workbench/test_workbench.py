"""The workbench: jobs, pages, routes and forms, without a server or the network."""

from http import HTTPStatus

import pytest

from adroit.orchestrator import runs
from adroit.workbench import jobs, pages, server
from adroit.workbench.jobs import Board, Job


@pytest.fixture
def board(tmp_path):
    return Board(tmp_path)


def _report(folder):
    (folder / "report.md").write_text("# Report\n\n| a | b |\n|---|---|\n| 1 | <script> |\n")
    (folder / "plot.png").write_bytes(b"\x89PNG")


def test_a_job_runs_in_its_own_folder_and_records_its_state(board) -> None:
    job = board.submit("exclusion", "O1 s", {"card": "O1"}, _report)
    board.wait()
    done = board.get(job.id)
    assert done.status == "done" and done.finished and (board.runs_dir / job.id / "report.md").is_file()


def test_a_failed_job_keeps_its_error(board) -> None:
    def broken(folder):
        raise ValueError("no such card")
    job = board.submit("exclusion", "bad", {}, broken)
    board.wait()
    failed = board.get(job.id)
    assert failed.status == "failed" and "no such card" in failed.error


def test_runs_on_disk_are_listed_including_the_command_lines(board) -> None:
    (board.runs_dir / "signal_LZ").mkdir()
    (board.runs_dir / "signal_LZ" / "report.md").write_text("x")
    (board.runs_dir / "empty").mkdir()
    listed = jobs.list_runs(board.runs_dir)
    assert [j.id for j in listed] == ["signal_LZ"] and listed[0].kind == "signal" and listed[0].status == "done"


def test_pages_escape_what_they_show() -> None:
    page = pages.job_page(Job(id="r1", kind="exclusion", title="<b>x</b>", status="done"),
                          "| a |\n|---|\n| <script>alert(1)</script> |\n", ["plot.png"])
    assert "<script>alert" not in page and "&lt;b&gt;x&lt;/b&gt;" in page
    assert "<table>" in page and "/file/r1/plot.png" in page


def test_a_running_job_refreshes_and_a_finished_one_does_not() -> None:
    running = pages.job_page(Job(id="r", kind="signal", title="t", status="running"), None, [])
    done = pages.job_page(Job(id="r", kind="signal", title="t", status="done"), "ok", [])
    assert 'http-equiv="refresh"' in running and 'http-equiv="refresh"' not in done


def test_the_forms_list_the_library_and_the_modules() -> None:
    form = pages.exclusion_form({"O1": "the SI contact"}, ["CRESST-III 2019"])
    assert "O1: the SI contact" in form and "CRESST-III 2019" in form and "/run/exclusion" in form
    signal = pages.signal_form(["LZ extended window (2026)"], ["CDMSlite Run 2", "DEAP-3600 (2019)"], ["CDMSlite Run 2"])
    assert "value='CDMSlite Run 2' checked" in signal and "value='DEAP-3600 (2019)'>" in signal


def test_a_file_outside_a_run_folder_is_never_served(board) -> None:
    job = board.submit("exclusion", "x", {}, _report)
    board.wait()
    assert pages.safe_file(board.runs_dir, job.id, "plot.png") is not None
    assert pages.safe_file(board.runs_dir, job.id, "../../etc/passwd") is None
    assert pages.safe_file(board.runs_dir, "..", "x") is None


def test_routes(board, monkeypatch) -> None:
    job = board.submit("exclusion", "x", {}, _report)
    board.wait()
    assert server.route(board, "/")[1] is HTTPStatus.OK
    body, _, kind = server.route(board, f"/job/{job.id}")
    assert "<table>" in body and kind == "text/html"
    assert server.route(board, f"/file/{job.id}/plot.png")[2] == "image/png"
    monkeypatch.setattr(server, "tools", lambda: "# t\n\nRequired: 9 of 9 present.")
    assert "Required: 9 of 9" in server.route(board, "/tools")[0]
    for missing in ("/nothing", "/job/none", f"/file/{job.id}/none.png"):
        with pytest.raises(FileNotFoundError):
            server.route(board, missing)


def test_the_evaluation_page_shows_the_gate_and_both_halves(board) -> None:
    gate, summaries = server.evaluation()
    page = pages.evaluation_page(gate, summaries)
    assert "lz_tables" in summaries and "held-out half" in page and "the gate passes" in page


def test_a_form_becomes_the_same_call_as_the_command_line(board, monkeypatch) -> None:
    seen = {}
    monkeypatch.setattr(runs, "exclusion", lambda *a: seen.setdefault("args", a))
    job = server.submit(board, "exclusion", {"card": ["O1"], "isospin": ["s"], "values": [""], "masses": ["10, 100"],
                                             "splitting": ["0"], "modules": ["CRESST-III 2019"]})
    board.wait()
    card, isospin, values, masses, splitting, modules, folder = seen["args"]
    assert (card, isospin, values, masses, splitting, modules) == ("O1", "s", {}, [10.0, 100.0], 0.0, ["CRESST-III 2019"])
    assert folder == board.runs_dir / job.id


def test_a_form_that_does_not_parse_starts_nothing(board) -> None:
    with pytest.raises(ValueError):
        server.submit(board, "exclusion", {"card": ["O1"], "masses": ["ten"]})
    with pytest.raises(ValueError):
        server.submit(board, "lagrangian", {"model": [""]})
    with pytest.raises(ValueError):
        server.submit(board, "nothing", {})
    assert jobs.list_runs(board.runs_dir) == []


def test_two_submissions_in_one_second_keep_their_own_folders(board, monkeypatch) -> None:
    """The re-audit's R18-3 control on the classic board: the clock frozen, the same kind and title."""
    from datetime import datetime

    class Frozen(datetime):
        @classmethod
        def now(cls, *a, **k):
            return cls(2026, 10, 18, 0, 0, 0)
    monkeypatch.setattr(jobs, "datetime", Frozen)
    a = board.submit("signal", "same title", {"model": "A"}, lambda p: (p / "result.txt").write_text("A"))
    b = board.submit("signal", "same title", {"model": "B"}, lambda p: (p / "result.txt").write_text("B"))
    board.wait()
    assert a.id != b.id and len(jobs.list_runs(board.runs_dir)) == 2
    assert board.get(a.id).inputs == {"model": "A"} and (board.runs_dir / a.id / "result.txt").read_text() == "A"
    assert board.get(b.id).inputs == {"model": "B"} and (board.runs_dir / b.id / "result.txt").read_text() == "B"
