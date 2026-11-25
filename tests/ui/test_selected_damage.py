"""The auditor's CO recheck (2026-10-26): a result record that is present but not a result object. CR-03: ``null``, a
list or a number had read as absent, so an empty paid journal beside it said "no paid request was sent"; a torn
file was already named. CR-06: such a result, or one of the wrong schema, selected from Studies, had made its
study's page a server error (the request reader of "inputs updated" and the approval panel), though the list named
it. Records are written directly, as the auditor's controls wrote them; no provider, request or calculation, $0."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

import pytest
from nicegui.testing import User
from typer.testing import CliRunner

from adroit.orchestrator import accounting, studies
from adroit.ui import engine

BODIES = {"null": "null", "a list": "[]", "a number": "7", "a torn file": "{"}
WRONG = {"track1": {"verdict": "viable"}, "single_idea": {"band": 3, "level": "viable"},
         "signal": {"tournament": [], "fits": 1}, "idea": {"status": "budget_stopped", "committed_usd": 0.4}}
IDEA = ["idea", "--text", "x", "--budget", "1", "--out", "."]


def _slug(text: str) -> str:
    return text.replace(" ", "_")


def _paid_run(folder: Path, body: str) -> None:
    """A finished paid run (``adroit idea --budget 1``) with an empty paid journal and ``body`` as its result."""
    folder.mkdir(parents=True)
    engine.save(engine.Job(title=folder.name, kind="idea", command=IDEA, folder=str(folder), status="failed",
                           returncode=3))
    (folder / "paid.jsonl").write_text("")
    (folder / "result.json").write_text(body)
    (folder / engine.LOG).write_text("")
    studies.record(folder, "idea", f"the run with {folder.name.replace('_', ' ')}")


@pytest.mark.parametrize("name", BODIES)
def test_a_result_that_is_not_an_object_withdraws_no_paid_request_was_sent(tmp_path, name):
    """CR-03 at the common reader and the command line: the damage named on the run's line, its card's figure and
    ``adroit studies``; never "no paid request was sent"."""
    from adroit.orchestrator.cli import app
    folder = tmp_path / "runs" / _slug(name)
    _paid_run(folder, BODIES[name])
    c = accounting.cost(folder, engine.load(folder))
    assert not c.sent_none and c.damaged and "its result record (result.json)" in c.damaged[0], c.damaged
    assert "no paid request was sent" not in accounting.run_line(c)
    listed = CliRunner().invoke(app, ["studies", str(tmp_path / "runs")])
    assert listed.exit_code == 0 and "no paid request was sent" not in listed.stdout, listed.stdout


def _studies(root: Path) -> dict[str, Path]:
    """One study of each kind for each damaged body, and one of the wrong schema; and a healthy neighbour."""
    out = {}
    healthy = root / "healthy"
    healthy.mkdir(parents=True)
    (healthy / "result.json").write_text(json.dumps({"verdict": {"level": "viable"}}))
    studies.record(healthy, "track1", "the healthy study")
    for kind, wrong in WRONG.items():
        for name, body in [*BODIES.items(), ("the wrong schema", json.dumps(wrong))]:
            folder = root / f"{kind}_{_slug(name)}"
            folder.mkdir()
            (folder / "result.json").write_text(body)
            studies.record(folder, kind, f"a {kind} study with {name}")
            out[f"{kind}_{_slug(name)}"] = folder
    return out


async def test_a_selected_damaged_result_is_named_on_its_page_before_and_after_a_restart(user: User, tmp_path):
    """CR-06 through the rendered pages: each study opened from Studies shows its title, its damage named, and none
    of what acts on its result (promotion, approval, the points); after the pages are built afresh (a restart), the
    same. A point of a damaged result is "unavailable", not a server error. No result's bytes change by viewing."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    folders = _studies(root)
    before = {k: hashlib.sha256((f / "result.json").read_bytes()).hexdigest() for k, f in folders.items()}
    for _ in range(2):
        build_pages(root)
        await user.open("/studies")
        await user.should_see("the healthy study")
        for key, folder in folders.items():
            await user.open("/study?" + urlencode({"path": folder.name}))
            await user.should_see(studies.load(folder).title)
            schema = key.endswith("the_wrong_schema")
            if not schema or key.split("_the_")[0] in ("signal", "idea"):
                await user.should_see(marker="damaged_result")
            await user.should_not_see("Promote a candidate to studies")
            await user.should_not_see("Approve models to constrain")
        await user.open("/study/point?" + urlencode({"path": "track1_null", "point": "grid:0"}))
        await user.should_see("Point unavailable")
    assert before == {k: hashlib.sha256((f / "result.json").read_bytes()).hexdigest() for k, f in folders.items()}


async def test_a_paid_run_page_with_a_result_that_is_not_an_object_names_it(user: User, tmp_path):
    """CR-03 on the run's page and the study card: the damage named, "no paid request was sent" absent."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    for name, body in BODIES.items():
        _paid_run(root / _slug(name), body)
    for name in BODIES:
        await user.open("/live?" + urlencode({"path": _slug(name)}))
        await user.should_see("its result record (result.json)")
        await user.should_not_see("no paid request was sent")
        await user.open("/study?" + urlencode({"path": _slug(name)}))
        await user.should_not_see("no paid request was sent")
