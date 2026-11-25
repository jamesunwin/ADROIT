"""The combined audit of 2026-10-24 (the independent audit of 2026-10-24 (v1 combined)): V1-02 to V1-04, the workbench's
accounting of old and damaged records and its history with an unreadable study. (V1-01 is in
tests/parameter_space/test_eos_verdict.py, V1-05 in tests/external/test_fetch.py.)

Each run here is a folder as the workbench leaves it (its job, log, records and paid ledger), written directly: no
provider, request or calculation.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from nicegui.testing import User

from adroit.orchestrator import studies
from adroit.ui import engine, outcomes

IDEA = ["idea", "--text", "x", "--budget", "1", "--out", "."]
RESERVED = {"id": "r", "state": "reserved", "provider": "anthropic", "model": "claude-opus-5-5", "reserved_usd": 0.4}


def _run(folder: Path, *, study: dict | None = None, log: str = "", stop: dict | None = None,
         ledger: list | str | None = None, command: list[str] = IDEA) -> engine.Job:
    """A finished workbench run's folder with the records given, and its job."""
    folder.mkdir(parents=True)
    job = engine.Job(title=folder.name, kind=command[0], command=command, folder=str(folder), status="failed",
                     returncode=2)
    engine.save(job)
    if study is not None:
        (folder / studies.FILE).write_text(json.dumps(study))
    if log:
        (folder / engine.LOG).write_text(log)
    if stop is not None:
        (folder / "result.json").write_text(json.dumps(stop))
    if ledger is not None:
        (folder / "paid.jsonl").write_text(ledger if isinstance(ledger, str)
                                           else "".join(json.dumps(r) + "\n" for r in ledger))
    return job


def _line(tmp_path: Path, name: str, **records) -> str:
    folder = tmp_path / name
    return outcomes.run_line(outcomes.cost(folder, _run(folder, **records)))


def _legacy(**update) -> dict:
    """A complete study record from before a run kept its own ledger (``cost_usd`` as given, or left out)."""
    record = studies.Study(kind="idea", title="old", folder=".").model_dump(mode="json")
    record.pop("cost_usd")
    return {**record, **update}


SPLIT = {"status": "budget_stopped", "committed_usd": 0.4024, "settled_usd": 0.0024, "uncertain_usd": 0.4}
NOW_LINE = "spent $0.0024 settled, and up to $0.4000 reserved for requests whose bill is not known\n"
BOTH = "This run: $0.0024 settled, and up to $0.4000 reserved whose bill is not yet known"
CASES = {
    # (records, the line expected, or the words it must hold and must not)
    "an old study record without a cost": ({"study": _legacy()}, "not available", "$0 settled"),
    "an old study record of $0": ({"study": _legacy(cost_usd=0.0)}, "not available", "$0 settled"),
    "an old study record of $0.0024": ({"study": _legacy(cost_usd=0.0024)},
                                       "This run: $0.0024 settled, as its study record shows (it keeps settled "
                                       "dollars alone", None),
    "today's spent line with a reservation": ({"log": NOW_LINE}, BOTH, None),
    "the audit's spent line and a split stop record": (
        {"log": "spent $0.0024; up to $0.4000 reserved whose bill is not yet known\n", "stop": SPLIT}, BOTH, None),
    "a split stop record and a study record": ({"stop": SPLIT, "study": _legacy(cost_usd=0.0024)}, BOTH, None),
    "a stop record without its split": ({"stop": {"status": "budget_stopped", "committed_usd": 0.4024}},
                                        "This run: up to $0.4024 committed", None),
    "a spent line to the cent": ({"log": "spent $0.12\n"}, "This run: about $0.1200", None),
}


@pytest.mark.parametrize("case", CASES)
def test_old_and_incomplete_accounting_is_never_a_settled_zero_nor_a_settled_subtotal(tmp_path, case):
    """V1-02: an old study record without a cost or of $0 read "This run: $0 settled, as the study record ... shows",
    though such a record keeps settled dollars alone; a log's settled figure was taken before the stop record that
    split the run's $0.4024 into $0.0024 settled and $0.40 reserved, and before the reservation on its own line."""
    records, expected, forbidden = CASES[case]
    line = _line(tmp_path, "run", **records)
    assert expected in line, line
    assert "no paid request was sent" not in line
    if forbidden:
        assert forbidden not in line, line


def test_a_free_command_still_costs_nothing(tmp_path):
    assert _line(tmp_path, "free", study=_legacy(), command=["track1", "--out", "."]) == "This run: $0 (no paid request)"


DAMAGED = {
    "a settlement without its reservation": [{"id": "r", "state": "settled", "cost_usd": 0.024}],
    "a state its writer never journals": [RESERVED, {"id": "r", "state": "refunded"}],
    "a request settled twice": [RESERVED, {"id": "r", "state": "settled", "cost_usd": 0.01},
                                {"id": "r", "state": "settled", "cost_usd": 0.01}],
    "a request reserved twice": [RESERVED, RESERVED],
    "a negative cost": [RESERVED, {"id": "r", "state": "settled", "cost_usd": -0.01}],
    "a reservation that is not a number": [{**RESERVED, "reserved_usd": "0.4"}],
    "an answer for a request never reserved": [{"id": "q", "state": "received", "response": {}}],
    "a line that is not JSON": '{"id": "r", "state": "reser\n',
    "a line that is not an entry": "[1, 2]\n",
    "a background response with no request": [{"state": "background_received", "response": {"usage": {}}}],
    "a background response after its request settled": [RESERVED, {"id": "r", "state": "settled", "cost_usd": 0.0024},
                                                         {"state": "background_received", "response": {}}],
}


@pytest.mark.parametrize("case", DAMAGED)
def test_a_damaged_ledger_is_unreadable_not_empty(tmp_path, case):
    """V1-03: a ledger holding only a settlement of $0.024, its reservation missing, was read as holding no request,
    and the page said "This run: $0 (no paid request was sent)"."""
    line = _line(tmp_path, "run", ledger=DAMAGED[case])
    assert line.startswith("This run: not available (the run's paid ledger could not be read"), line


VALID = {
    "empty": ("", "This run: $0 (no paid request was sent)"),
    "reserved and answered, its bill not yet in": (
        [RESERVED, {"id": "r", "state": "received", "response": {}}],
        "This run: $0.0000 settled, and up to $0.4000 reserved whose bill is not yet known"),
    "its bill uncertain": ([RESERVED, {"id": "r", "state": "billing_uncertain", "error": "TimeoutError"}],
                           "This run: $0.0000 settled, and up to $0.4000 reserved whose bill is not yet known"),
    "settled": ([RESERVED, {"id": "r", "state": "received", "response": {}},
                 {"id": "r", "state": "settled", "cost_usd": 0.0024, "bound_exceeded": False}], "This run: $0.0024"),
    "a response kept while polling, and a session's new cap": (     # the writer reserves before it dispatches (CA-06)
        [RESERVED, {"state": "background_received", "response": {}}, {"state": "cap_raised", "previous": 1, "new": 2,
                                                                  "at": "2026-10-24T00:00:00Z"},
         {"id": "r", "state": "settled", "cost_usd": 0.0024}], "This run: $0.0024"),
}


@pytest.mark.parametrize("case", VALID)
def test_a_ledger_its_writer_kept_reads_as_before(tmp_path, case):
    ledger, expected = VALID[case]
    assert _line(tmp_path, "run", ledger=ledger) == expected


async def test_the_card_and_the_list_show_the_pages_figure(user: User, tmp_path):
    """V1-02's consumers: the study card and the line in Studies give the run page's figure, the reservation
    included; a study not run from the workbench, its record's settled dollars as such."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    derive = ["lagrangian", "--derive", "--description", "x", "--budget", "1", "--out", "."]
    _run(root / "stopped", log=NOW_LINE, command=derive)
    studies.record(root / "stopped", "lagrangian", "a stopped derivation", cost_usd=0.0024)
    (root / "command_line").mkdir()
    studies.record(root / "command_line", "lagrangian", "a derivation from the command line", cost_usd=0.0024)
    await user.open("/study?path=stopped")
    await user.should_see("cost: $0.0024 settled, and up to $0.4000 reserved whose bill is not yet known")
    await user.open("/study?path=command_line")
    await user.should_see("cost $0.0024 settled")
    await user.open("/studies")
    await user.should_see("$0.0024 settled + up to $0.4000 reserved")


@pytest.mark.parametrize("bad", ["{}", '{"kind": "track1", "title": "cut sho'])
async def test_an_unreadable_study_is_named_and_the_rest_still_listed_and_usable(user: User, tmp_path, bad):
    """V1-04: one ``study.json`` holding ``{}`` stopped ``studies.tree``, so the Studies page and the Signal best fits
    form (which lists the saved studies) gave an internal error. The record is named with why, its page says it
    cannot be read, and every other study and form works."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    (root / "good").mkdir()
    studies.record(root / "good", "track1", "a good study")
    (root / "partial").mkdir()
    (root / "partial" / studies.FILE).write_text(bad)
    assert [s.title for _, s in studies.tree(root)] == ["a good study"]
    assert [p.parent.name for p, _ in studies.unreadable(root)] == ["partial"]
    await user.open("/studies")
    await user.should_see("a good study")
    await user.should_see("1 study record(s) could not be read and are not listed: partial/study.json")
    await user.open("/new/track2")
    await user.should_see("Signal best fits")
    await user.open("/study?path=partial")
    await user.should_see("Study record unreadable")


def test_a_study_record_is_published_whole(tmp_path, monkeypatch):
    """V1-04's prevention: a record is written in full beside the old one and then put in its place, so a write cut
    short leaves the previous record, never part of one."""
    study = studies.record(tmp_path, "track1", "first")
    before = (tmp_path / studies.FILE).read_text()

    def cut(*args):
        raise OSError("disk full")
    for step in ("os.fsync", "os.replace"):           # cut short while written, or before it is put in place (M3)
        with monkeypatch.context() as patched:
            patched.setattr(step, cut)
            with pytest.raises(OSError):
                studies.save(study.model_copy(update={"title": "second"}))
        assert (tmp_path / studies.FILE).read_text() == before
        assert not list(tmp_path.glob(".study.json.*.tmp"))


# --- the records prepared for signing: the PDG's review is not an arXiv paper ------------------------------------

PDG_RECORD = "pdg-2024-electroweak-st"


async def test_the_pdg_records_review_page_names_its_review_without_an_arxiv_link(user: User, tmp_path, monkeypatch):
    from adroit.core.config import get_settings
    from adroit.ui.app import build_pages
    monkeypatch.setattr(get_settings(), "tools_dir", tmp_path / "tools")              # its PDF not put there
    build_pages(tmp_path / "runs")
    await user.open(f"/record?id={PDG_RECORD}")
    await user.should_see("Compare with Particle Data Group 2024, Review 10")
    await user.should_see("Not an arXiv paper")
    await user.should_not_see("open the paper on arXiv")
