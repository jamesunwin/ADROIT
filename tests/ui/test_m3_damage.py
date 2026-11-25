"""The consolidation plan's M3 (2026-10-25): browsing around damage, never calculating through it.

A damaged record beside valid ones, the workbench built afresh (as after a restart): every page and command names it
and the healthy work goes on. A damaged record that an operation depends on (a cancellation file, the active profile,
a selected model, a session's budget record) stops that operation with the reason. Two writers of one shared record
lose neither update, and a write cut short leaves the previous file. Every record is written in the test's own
folders; no provider, request or calculation, $0; signatures only on a scratch copy of the records, synthetic.
"""
from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from nicegui.testing import User

from adroit.core.durable import DamagedRecord
from adroit.orchestrator import studies
from adroit.ui import batch, engine
from tests.ui.test_batch import _batch, _run
from tests.ui.test_consistency_records import _approved_revision, _job


# --- calculating through damage, never ----------------------------------------------------------------------------

@pytest.mark.parametrize("body", ["{", "[1]", ""])
def test_an_unreadable_cancellation_file_stops_the_run_rather_than_permitting_it(tmp_path, body):
    """Its control file had been read with a bare ``json.loads``: one that could not be read raised in the runner,
    which ended before writing the job's final status. It now stops the run as if cancelled, saying why."""
    from adroit.ui import runner
    job = engine.Job(title="a run", kind="track1", folder=str(tmp_path), command=["track1", "--out", "."],
                     acknowledged=False)
    engine.save(job)
    (tmp_path / engine.CONTROL).write_text(body)
    assert engine.cancelled(tmp_path) and "stopped as if cancelled" in engine.control_unreadable(tmp_path)
    done = runner.run(tmp_path, engine.command_sha256(job.command))
    assert done.status == "cancelled" and "stopped as if cancelled" in done.note


def test_an_unreadable_cancellation_file_stops_a_batch_dispatching(tmp_path):
    root = tmp_path / "runs"
    folder, approval = _batch(root, ["a", "b"])
    (folder / batch.CONTROL).write_text("{ torn")
    launched = []
    done = _run(folder, approval, launch=lambda *a, **k: launched.append(a), poll=lambda f: None,
                stop=lambda f: None, sleep=lambda s: None)
    assert launched == [] and done.status == "cancelled" and "cannot be read" in done.note
    assert [x.status for x in done.items] == ["cancelled", "cancelled"]


@pytest.fixture
def damaged_active(tmp_path):
    """The experimental library with a damaged record of the active selection."""
    from adroit.library.experimental import ExperimentalCatalog
    catalog = ExperimentalCatalog()
    catalog.path("active_profile.json").parent.mkdir(parents=True, exist_ok=True)
    catalog.path("active_profile.json").write_text("{")
    return catalog


def test_a_damaged_active_profile_stops_a_run_and_never_falls_back_to_the_defaults(damaged_active):
    from adroit.library import experimental_profiles as profiles
    with pytest.raises(DamagedRecord, match="active_profile.json cannot be read .*activate a profile"):
        profiles.selected("")
    assert profiles.current() == profiles.DAMAGED
    assert profiles.selected("none") == ""                      # the defaults, chosen explicitly, still work


def test_a_command_using_the_damaged_active_profile_stops_in_one_line(damaged_active, tmp_path, capsys):
    """As the command line runs (``cli.app``): one line naming the record and what to do, exit status 1, nothing
    calculated."""
    from adroit.orchestrator import cli
    from adroit.parameter_space.simplified import model as simplified
    import yaml
    model = tmp_path / "model.yaml"
    model.write_text(yaml.safe_dump(simplified("vector", 10, 30).model_dump(mode="json")))
    with pytest.raises(SystemExit) as stopped:
        cli.app(["track1", str(model), "--out", str(tmp_path / "out")])
    err = capsys.readouterr().err
    assert stopped.value.code == 1 and "active_profile.json cannot be read" in err and "Traceback" not in err
    assert not (tmp_path / "out" / "result.json").exists()


def test_a_damaged_active_profile_is_replaced_only_by_an_explicit_activation_and_kept(damaged_active):
    from adroit.library import experimental_profiles as profiles
    with pytest.raises(ValueError, match="changed since review"):
        profiles.activate("", "", confirmed=True)                 # a view that did not see the damage
    assert profiles.activate("", profiles.DAMAGED, confirmed=True) == ""
    assert profiles.active() == ""
    kept = list(damaged_active.path("active_profile.json").parent.glob("active_profile.json.damaged-*"))
    assert len(kept) == 1 and kept[0].read_text() == "{"


async def test_the_profile_page_and_the_wizards_name_a_damaged_active_profile(user: User, tmp_path, damaged_active):
    from adroit.ui.app import build_pages
    build_pages(tmp_path / "runs")
    await user.open("/experiments/profiles")
    await user.should_see(marker="damaged_active_profile")
    await user.should_see("none: the active profile cannot be read")
    await user.open("/new/track1")
    await user.should_see("The active profile cannot be read: choose one, or the packaged defaults, explicitly")


def test_a_damaged_selected_model_stops_what_uses_it_with_the_reason(tmp_path):
    from adroit.library.personal import Catalog
    good = _approved_revision()
    path = Catalog().root / "models" / good.model_id / "revisions" / f"{good.revision_id}.json"
    path.write_text("{")
    with pytest.raises(DamagedRecord, match="cannot be read .*choose another revision"):
        Catalog().load(good.reference)


def test_a_damaged_budget_record_stops_a_paid_step_before_any_request(tmp_path):
    """A session's paid ledger that cannot be read (a settlement without its reservation) stops its next paid step
    before anything is reserved or sent: the account cannot be rebuilt."""
    from adroit.agents.llm import FakeLLMClient
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import Intake
    service = Intake(Catalog(tmp_path / "models"))
    s = service.start(budget=1)
    (service.folder(s.session_id) / "paid.jsonl").write_text(json.dumps({"id": "q", "state": "settled",
                                                                         "cost_usd": 0.02}) + "\n")
    fake = FakeLLMClient()
    with pytest.raises(ValueError, match="never reserved"):
        service.step(s.session_id, "idea", "a dark photon portal", llm=fake)
    assert fake.calls == []


# --- lost updates and writes cut short ------------------------------------------------------------------------------

def test_children_recorded_at_once_are_all_kept_by_their_parent(tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    studies.record(parent, "signal", "the parent")
    folders = [parent / "children" / f"c{n}" for n in range(8)]
    for f in folders:
        f.mkdir(parents=True)
    threads = [threading.Thread(target=studies.record, args=(f, "single_idea", f.name), kwargs={"parent": parent})
               for f in folders]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(Path(c).name for c in studies.load(parent).children) == sorted(f.name for f in folders)


def test_two_verifications_at_once_are_both_written(tmp_path, monkeypatch):
    """``review.verify`` reads, changes and writes ``records.yaml`` under its lock: two people signing two records
    at once both have their signature kept. On a scratch copy, the two records' signatures taken off it first (the
    owner has signed them since, 2026-11-06), with a synthetic signer: no record is signed."""
    import re
    from adroit.constraints import database, review
    from adroit.core.config import get_settings
    monkeypatch.setattr(get_settings(), "runs_dir", tmp_path / "runs")
    copy = tmp_path / "records.yaml"
    shutil.copyfile(database.RECORDS, copy)
    ids = ["cms-1808.03684-4mu", "atlas-2301.09342-4mu"]
    text = copy.read_text()
    for record_id in ids:                                 # each as it stood before the owner signed it
        start = text.index(f"  - id: {record_id}\n")
        end = text.index("\n  - id: ", start + 1)
        block = re.sub(r"^    (verified_on|verified_by|verification_sha256|verification_history):[^\n]*\n", "",
                       text[start:end] + "\n", flags=re.M)
        text = text[:start] + block[:-1] + text[end:]
    copy.write_text(text)
    errors = []

    def sign(record_id):
        try:
            review.verify(record_id, "TEST SYNTHETIC", path=copy)
        except Exception as error:                      # reported below, not hidden
            errors.append(error)
    threads = [threading.Thread(target=sign, args=(i,)) for i in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    import yaml
    signed = {r["id"]: r.get("verified_by") for r in yaml.safe_load(copy.read_text())["records"] if r["id"] in ids}
    assert errors == [] and signed == {i: "TEST SYNTHETIC" for i in ids}
    database.records.cache_clear()
    database.data.cache_clear()


def test_a_result_written_short_leaves_the_previous_one(tmp_path, monkeypatch):
    from adroit.orchestrator import runs
    out = tmp_path / "run"
    out.mkdir()
    first = SimpleNamespace(model_dump_json=lambda indent=1: '{"first": true}')
    runs._write(out, first, "the first report", "lagrangian_x", "a run")
    second = SimpleNamespace(model_dump_json=lambda indent=1: '{"second": true}')

    def cut(*args):
        raise OSError("disk full")
    monkeypatch.setattr("os.replace", cut)
    with pytest.raises(OSError):
        runs._write(out, second, "the second report", "lagrangian_x", "a run")
    monkeypatch.undo()
    assert json.loads((out / "result.json").read_text()) == {"first": True}


# --- browsing around damage ---------------------------------------------------------------------------------------

def _damaged_runs(root: Path) -> None:
    """A runs folder with a healthy study and, beside it, a damaged sibling of each family a page lists."""
    _job(root / "healthy")
    studies.record(root / "healthy", "track1", "a healthy study")
    (root / "broken_study").mkdir()
    (root / "broken_study" / studies.FILE).write_text("{")
    (root / "running").mkdir()
    _job(root / "running", "a run with damaged progress")
    (root / "running" / "progress.json").write_text("{")
    (root / batch.DRAFT).parent.mkdir(parents=True, exist_ok=True)
    (root / batch.DRAFT).write_text("[{")


async def test_every_listing_names_its_damaged_records_and_the_healthy_work_goes_on(user: User, tmp_path):
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    _damaged_runs(root)
    await user.open("/batches")
    await user.should_see(marker="unreadable_draft")
    await user.open("/live?path=running")
    await user.should_see(marker="unreadable_progress")
    await user.open("/records")
    await user.should_see(marker="unoffered_studies")
    await user.open("/studies/revisit")
    await user.should_see(marker="unoffered_studies")
    await user.open("/study?path=healthy")
    await user.should_see("a healthy study")


async def test_a_damaged_profile_file_is_named_on_the_profiles_page(user: User, tmp_path):
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.ui.app import build_pages
    folder = ExperimentalCatalog().path("profiles")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ("a" * 64 + ".json")).write_text("{}")
    build_pages(tmp_path / "runs")
    await user.open("/experiments/profiles")
    await user.should_see(marker="unreadable_profiles")
    await user.should_see("In use for new runs: the packaged defaults")


async def test_a_damaged_step_of_an_experimental_session_is_named_and_the_session_shown(user: User, tmp_path):
    from tests.ui.test_consistency_accounting import _extraction
    from adroit.ui.app import build_pages
    service, session, owner = _extraction(tmp_path, linked=False)
    steps = service.budgets.folder(session) / "extractions"
    steps.mkdir(parents=True, exist_ok=True)
    (steps / ("0" * 64 + ".json")).write_text("{")
    assert service.step_listing(session)[1] and pytest.raises(ValueError, service.steps, session)
    build_pages(tmp_path / "runs")
    await user.open(f"/experiments/session?session={session}")
    await user.should_see(marker="unreadable_steps")
    await user.should_see(marker="session_money")


async def test_a_damaged_discovery_session_is_named_on_a_models_page(user: User, tmp_path):
    from adroit.orchestrator.constraint_discovery import Discovery
    from adroit.ui.app import build_pages
    good = _approved_revision()
    bad = Discovery().catalog.root / "discovery" / ("9" * 32)
    bad.mkdir(parents=True)
    (bad / "session.json").write_text("{")
    root = build_pages(tmp_path / "runs")
    (root / "broken").mkdir(parents=True)
    (root / "broken" / studies.FILE).write_text("{")
    from urllib.parse import urlencode
    await user.open("/models/view?" + urlencode({"reference": good.reference}))
    await user.should_see(marker="unreadable_sessions")
    await user.should_see(marker="unoffered_studies")


def test_a_new_run_starts_beside_damaged_records(tmp_path):
    """The healthy work goes on: a launch into a new folder beside a damaged job and a damaged study starts, and the
    listing shows it with the damaged one named."""
    root = tmp_path / "runs"
    (root / "broken").mkdir(parents=True)
    (root / "broken" / engine.JOB).write_text("{}")
    (root / "broken" / studies.FILE).write_text("{")
    started = engine.launch(["track1", "model.yaml", "--out", "."], root / "new", "a new run",
                            popen=lambda *a, **k: SimpleNamespace(pid=4242))
    jobs, damaged = engine.listing(root)
    assert [j.title for j in jobs] == ["a new run"] and started.pid == 4242 and len(damaged) == 1

