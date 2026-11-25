"""The auditor's DU recheck (2026-11-10), DV-01 and DV-02.

DV-01: a run's budgeted client, given its run's ledger through a link to the run's folder, chose its ledger at each
entry by scanning the ledgers its process had opened. Once the link led elsewhere (to an empty folder), it fell back to
the link's path: a second journal began there, its request was sent, and the run's page read the run's own ledger,
which lacked it, as all the run spent; re-pointed before its first request, the run read "no paid request was sent"
(the auditor's ``du_boundary_edges``, ``run_alias_*``). A client now keeps one ledger for its life
(``BudgetedLLMClient._bound``): its run's, as opened, where its path names one when it is made, else the one it first
journals to; a path that leads elsewhere since is refused before anything is journalled.

DV-02: an append's final readback read the journal and its mark in the folder it had locked, without asking whether
that folder was still at the journal's path. Renamed away as the readback began, an older coherent copy put at its
path, the reservation was acknowledged in the moved folder and sent; the next entry was refused and the live account
froze, but every later reading read the copy as all that was spent (the auditor's ``du_readback_process``). The readback now
checks the folder and the file at the path (``durable._recorded``), refusing before anything is sent; and a request
sent whose next entry cannot be journalled leaves a notice beside its ledger, which every reading of the ledger then
refuses as holding less than was spent (``budget.leave_unjournalled``, ``budget.unjournalled``).

Every dollar is simulated (100 input and 20 output tokens a request, $0.0008); no provider is contacted."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.agents.test_budget_reservations import ask
from tests.orchestrator.test_do_fixes import SPENT, _client, _entries, _in_job, _refused, _session

PAID = ["idea", "--text", "x", "--budget", "1", "--out", "."]


def _run(tmp: Path, name: str = "job", attempt: str = "attempt-a") -> Path:
    """A workbench run's folder, its job recorded and its paid ledger opened by its run."""
    from adroit.orchestrator import preflight
    from adroit.ui import engine
    folder = tmp / name
    folder.mkdir(parents=True)
    engine.save(engine.Job(title="the run", kind="idea", command=PAID, folder=str(folder), status="completed",
                           returncode=0, attempt=attempt))
    (folder / "log.txt").write_text("")
    with _in_job(folder, attempt):
        preflight.open_job_ledger(folder / "paid.jsonl")
    return folder


def _cost(folder: Path):
    """The run's cost as its every page reads it, and in words."""
    from adroit.orchestrator import accounting
    from adroit.ui import engine
    c = accounting.cost(folder, engine.load(folder))
    return c, accounting.run_line(c)


def _requests(folder: Path) -> dict:
    """The requests a reading of the run's ledger finds (``budget.read_owned``), by state."""
    from adroit.agents.budget import read_owned
    return {rid: r.state for rid, r in read_owned(folder / "paid.jsonl")[0].items()}


def _point(link: Path, target: Path) -> None:
    link.unlink()
    link.symlink_to(target, target_is_directory=True)


# --- DV-01: a run's client keeps its run's ledger ---------------------------------------------------------------

def _aliased(tmp: Path, how: str) -> tuple[Path, Path, Path]:
    """The run's folder, its ledger's path through a link (``how``: to the run's folder, or to the folder above it),
    and the link."""
    folder = _run(tmp / "runs")
    if how == "a link to its folder":
        link = tmp / "alias"
        link.symlink_to(folder, target_is_directory=True)
        return folder, link / "paid.jsonl", link
    link = tmp / "above"
    link.symlink_to(folder.parent, target_is_directory=True)
    return folder, link / "job" / "paid.jsonl", link


def _elsewhere(tmp: Path, how: str, where: str) -> Path:
    """Where the link is led instead: an empty folder (the auditor's), or another run's folder, its ledger opened by
    its own run in this process."""
    if where == "an empty folder":
        other = tmp / "other"
        (other / "job").mkdir(parents=True)
        return other if how == "a link to the folder above it" else other / "job"
    other_runs = tmp / "other_runs"
    other_runs.mkdir()
    folder = _run(other_runs, attempt="attempt-b")
    return other_runs if how == "a link to the folder above it" else folder


LINKS = ("a link to its folder", "a link to the folder above it")
ELSEWHERE = ("an empty folder", "another run's opened folder")


@pytest.mark.parametrize("where", ELSEWHERE)
@pytest.mark.parametrize("how", LINKS)
def test_a_run_s_client_whose_link_is_led_elsewhere_between_requests_is_refused(tmp_path, how, where):
    """The auditor's ``run_alias_between_requests``, and the matrix's ancestor link and another opened run: one request
    sent and journalled in the run's ledger; the link then led elsewhere; the second request is refused before it is
    sent, nothing written there; the run's ledger and every reading of its cost hold the one request sent."""
    folder, ledger, link = _aliased(tmp_path, how)
    target = _elsewhere(tmp_path, how, where)
    before = _entries(target if how == "a link to its folder" else target / "job")
    with _in_job(folder, "attempt-a"):
        llm, calls = _client(ledger, cap=1.0)
        ask(llm)
        _point(link, target)
        refused = _refused(lambda: ask(llm))
    assert len(calls) == 1, "a request was sent through a link led away from its run's ledger"
    assert _entries(target if how == "a link to its folder" else target / "job") == before, \
        "a journal was begun, or another run's written on, where the link now leads"
    assert list(_requests(folder).values()) == ["settled"]
    c, words = _cost(folder)
    assert c.run_usd == pytest.approx(SPENT) and not c.damaged and "$0.0008" in words
    assert "no longer leads to" in refused and not llm.account.unjournalled, refused
    assert list(llm._held) == [Path(os.path.abspath(folder / "paid.jsonl"))]


@pytest.mark.parametrize("how", LINKS)
def test_a_run_s_client_whose_link_is_led_elsewhere_before_its_first_request_is_refused(tmp_path, how):
    """The auditor's ``run_alias_before_first_request``: the client made through the link while it leads to its run's
    opened ledger, the link then led to an empty folder: its first request is refused, nothing sent or written, and the
    run's cost is truly that no paid request was sent. Before, one was sent into a journal begun there."""
    folder, ledger, link = _aliased(tmp_path, how)
    target = _elsewhere(tmp_path, how, "an empty folder")
    with _in_job(folder, "attempt-a"):
        llm, calls = _client(ledger, cap=1.0)
        _point(link, target)
        refused = _refused(lambda: ask(llm))
    assert not calls, "a request was sent through a link led away from its run's ledger before its first request"
    assert "no longer leads to" in refused, refused
    assert not list(target.rglob("paid.jsonl*")), "a journal was begun where the link now leads"
    assert _requests(folder) == {} and "no paid request was sent" in _cost(folder)[1]


def test_a_run_s_client_whose_link_is_led_elsewhere_between_its_reservation_and_receipt_freezes(tmp_path):
    """The matrix's third placement: the link led away once the reservation is journalled, as the request is sent.
    Its receipt cannot be journalled (refused: the link no longer leads to the run's ledger), so the account freezes
    and a notice is left beside the run's ledger: every reading of the run's cost says what it spent is not known,
    never the ledger's reservation alone as settled; the next request is never sent; nothing is written elsewhere."""
    from adroit.agents.budget import UNJOURNALLED
    from adroit.agents.llm import UnknownLedger
    folder, ledger, link = _aliased(tmp_path, "a link to its folder")
    target = _elsewhere(tmp_path, "a link to its folder", "an empty folder")
    with _in_job(folder, "attempt-a"):
        llm, calls = _client(ledger, cap=1.0)
        create = llm._inner._client.messages.create
        llm._inner._client.messages.create = lambda **kw: (_point(link, target), create(**kw))[1]
        with pytest.raises(ValueError, match="no longer leads to"):
            ask(llm)
        with pytest.raises(UnknownLedger):
            ask(llm)
    assert len(calls) == 1 and llm.account.unjournalled
    notices = [p.name for p in folder.iterdir() if UNJOURNALLED in p.name]
    assert len(notices) == 1 and "attempt-a" in (folder / notices[0]).read_text()
    c, words = _cost(folder)
    assert c.run_usd is None and "less than was spent" in words and "$0.0008" not in words.split("(")[0], words
    assert not list(target.rglob("paid.jsonl*"))


def test_a_run_s_client_through_a_link_that_keeps_leading_to_its_ledger_journals_every_request(tmp_path):
    """What stays: the link unchanged, both requests are journalled in the run's ledger by its own name, and its cost
    is both."""
    folder, ledger, _ = _aliased(tmp_path, "a link to its folder")
    with _in_job(folder, "attempt-a"):
        llm, calls = _client(ledger, cap=1.0)
        ask(llm)
        ask(llm)
    assert len(calls) == 2 and list(_requests(folder).values()) == ["settled", "settled"]
    assert _cost(folder)[0].run_usd == pytest.approx(2 * SPENT)


# --- DV-02: the final readback, and what is known after it -----------------------------------------------------

def _older_copy_at_entry_of_readback(ledger: Path, earlier: Path, moved: Path, how: str):
    """``durable._recorded`` entered with its journal's folder renamed to ``moved`` and the earlier coherent copy
    ``earlier`` put at its path (``how``: the folder itself, the folder above it, or a link to the copy), then run
    unchanged: the auditor's deterministic barrier."""
    from adroit.core import durable
    real, done = durable._recorded, []

    def recorded(path, handle, after, folder):
        if not done:
            done.append(True)
            if how == "the folder above it":
                ledger.parent.parent.rename(moved)
                shutil.copytree(earlier, ledger.parent.parent)
            else:
                ledger.parent.rename(moved)
                if how == "a link to the copy":
                    shutil.copytree(earlier, moved.parent / "copy")
                    ledger.parent.symlink_to(moved.parent / "copy", target_is_directory=True)
                else:
                    shutil.copytree(earlier, ledger.parent)
        return real(path, handle, after, folder)
    return patch.object(durable, "_recorded", recorded)


REPLACEMENTS = ("the folder itself", "the folder above it", "a link to the copy")


@pytest.mark.parametrize("how", REPLACEMENTS)
@pytest.mark.parametrize("kind", ["a run's ledger", "a client's own ledger"])
def test_a_reservation_whose_folder_is_replaced_before_its_readback_is_never_sent(tmp_path, kind, how):
    """The auditor's ``replacement_before_final_readback_standalone`` and ``_run``, with the matrix's parent and linked
    replacements: after one settled request, the next reservation's readback begins with its folder renamed away and
    the earlier coherent copy put at its path. Now ``UnfinishedAppend``: the account freezes, the request is never
    sent; the copy at the path is unchanged, and every reading of it holds the one request sent; the moved folder keeps
    the reservation it wrote, with its mark. Before, the request was sent, and the copy read as all that was spent."""
    from adroit.core import durable
    folder = _run(tmp_path / "runs") if kind == "a run's ledger" else tmp_path / "runs" / "job"
    folder.mkdir(parents=True, exist_ok=True)
    ledger = folder / "paid.jsonl"
    with _in_job(folder, "attempt-a"):
        llm, calls = _client(ledger, cap=1.0)
        ask(llm)
        earlier = tmp_path / "earlier"
        shutil.copytree(folder.parent if how == "the folder above it" else folder, earlier)
        moved = tmp_path / "moved"
        with _older_copy_at_entry_of_readback(ledger, earlier, moved, how):
            try:
                ask(llm)
                refused = None
            except (ValueError, OSError) as error:
                refused = error
    assert len(calls) == 1, "a request was sent whose reservation was acknowledged in a folder moved away"
    assert isinstance(refused, durable.UnfinishedAppend) and "as its append was read back" in str(refused), refused
    assert llm.account.unjournalled
    from adroit.agents.budget import read_ledger
    assert [r.state for r in read_ledger(ledger).values()] == ["settled"]
    kept = (moved / "job" if how == "the folder above it" else moved) / "paid.jsonl"
    assert [r.state for r in read_ledger(kept).values()] == ["settled", "open"]      # reserved, never sent
    if kind == "a run's ledger":
        c, words = _cost(ledger.parent)
        assert c.run_usd == pytest.approx(SPENT) and "$0.0008" in words


def test_a_folder_replaced_after_the_readback_leaves_a_notice_every_reading_refuses(tmp_path):
    """What the readback cannot see: the folder replaced once it has checked, before the request is sent. The request
    is sent; its receipt, checked against what the client wrote, is refused; the account freezes and a notice is left
    beside the ledger at its path. The run's cost is then not known on every surface (never the copy's $0.0008 as all
    it spent), a reading of the ledger is refused naming the notice, and a new client of it sends nothing."""
    from adroit.agents.budget import read_ledger
    from adroit.agents.llm import UnknownLedger
    from adroit.core import durable
    folder = _run(tmp_path)
    ledger = folder / "paid.jsonl"
    with _in_job(folder, "attempt-a"):
        llm, calls = _client(ledger, cap=1.0)
        ask(llm)
        earlier = tmp_path / "earlier"
        shutil.copytree(folder, earlier)
        real, done = durable._recorded, []

        def recorded(path, handle, after, at):
            real(path, handle, after, at)
            if not done:                            # once its last check has passed
                done.append(True)
                folder.rename(tmp_path / "moved")
                shutil.copytree(earlier, folder)
        with patch.object(durable, "_recorded", recorded):
            with pytest.raises(ValueError):
                ask(llm)
        assert len(calls) == 2 and llm.account.unjournalled
        assert [p.name for p in folder.iterdir() if "unjournalled-" in p.name], "no notice beside the ledger"
        with pytest.raises(UnknownLedger):
            ask(llm)
        c, words = _cost(folder)
        assert c.run_usd is None and "less than was spent" in words and "$0.0008" not in words.split("(")[0], words
        with pytest.raises(ValueError, match="less than was spent"):
            read_ledger(ledger)
        fresh, sent = _client(ledger, cap=1.0)
        assert _refused(lambda: ask(fresh)) and not sent


def test_a_session_whose_request_lacks_an_entry_spends_nothing_more_until_it_is_reconciled(tmp_path):
    """The notice for a session's ledger: its account, rebuilt for its next step, is refused before anything is
    reserved, and its spending is not read as complete; once the notice is removed (reconciled), it reads again."""
    from adroit.agents.budget import leave_unjournalled
    service, session, llm, calls = _session(tmp_path)
    ask(llm)
    ledger = service.folder(session) / "paid.jsonl"
    assert leave_unjournalled(ledger, "r1", "received", "SIMULATED: its receipt could not be journalled") == ""
    with pytest.raises(ValueError, match="less than was spent"):
        service.account(service.session(session))
    with pytest.raises(ValueError, match="less than was spent"):
        service.snapshot(session)
    for notice in ledger.parent.glob("paid.jsonl.unjournalled-*"):
        notice.unlink()
    assert service.snapshot(session)[0]["spent"] == pytest.approx(SPENT) and len(calls) == 1
