"""The auditor's consolidation audit (2026-10-25) through the rendered workbench: CO-06 (one malformed result had made the
whole Studies page fail) and CO-07 (a stale or legacy headline had looked like a current one in the history). The
studies are written as the workbench writes them (``test_certification_journey._saved_study``: a real verdict over a
toy plane) or, for the malformed ones, as the bytes named."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from urllib.parse import urlencode

import pytest
from nicegui.testing import User

from adroit.orchestrator import annotations, studies
from tests.ui.acceptance.test_certification_journey import _saved_study

MALFORMED = {
    "truncated JSON": '{"verdict": {"level": "vi',
    "a null list": json.dumps({"request": {"null_modules": None}}),
    "a number for a list": json.dumps({"request": {"null_modules": 3}}),
    "a certificate that is not a record": json.dumps({"band": [], "level": "viable", "thermal": [{"certificate": []}]}),
    "a malformed certificate": json.dumps({"verdict": {"level": "viable",
                                                       "crossings": [{"certificate": {"claim_kind": 3}}]}}),
    "qualifiers that are not words": json.dumps({"verdict": {"level": "viable", "qualifiers": [1]}}),
}


def _folder(name: str) -> str:
    return name.replace(" ", "_")


def _history(root: Path) -> Path:
    """A healthy study, and beside it one study for each malformed result of ``MALFORMED``."""
    from adroit.model_building.audit import audit
    from adroit.orchestrator import track1
    from adroit.parameter_space import simplified
    from adroit.parameter_space.verdict import Verdict
    spec = simplified.model("vector", 10, 30)
    healthy = root / "healthy"
    healthy.mkdir(parents=True)
    (healthy / "result.json").write_text(track1.Track1Result(     # a Track 1 result, as its kind's model reads one
        request=track1.Track1Request(spec=spec), audit=audit(spec),
        verdict=Verdict(level="viable", summary="", target=.12)).model_dump_json())
    studies.record(healthy, "track1", "the healthy study")
    for name, body in MALFORMED.items():
        folder = root / _folder(name)
        folder.mkdir()
        (folder / "result.json").write_text(body)
        studies.record(folder, "track1", f"a result with {name}")
    return root


def test_every_malformed_result_is_named_and_its_study_kept(tmp_path):
    """CO-06 at the source the history reads (``annotations.facts``): no malformed result raises; each is named."""
    root = _history(tmp_path / "runs")
    rows = {s.title: annotations.facts(root, s) for _, s in studies.tree(root)}
    assert not rows["the healthy study"].damage and rows["the healthy study"].badge == "VIABLE"
    for name in MALFORMED:
        assert rows[f"a result with {name}"].damage, name


async def test_the_studies_page_lists_the_healthy_study_beside_malformed_results(user: User, tmp_path):
    """CO-06 through the rendered page, before and after a restart: every study listed, the damage named; the
    malformed study's own page names its result rather than failing."""
    from adroit.ui.app import build_pages
    root = _history(build_pages(tmp_path / "runs"))
    for _ in range(2):                                     # the second time: the pages built afresh (a restart)
        build_pages(root)
        await user.open("/studies")
        await user.should_see("the healthy study")
        for name in MALFORMED:
            await user.should_see(f"a result with {name}")
        await user.should_see(marker="unreadable_results")
    await user.open("/study?" + urlencode({"path": _folder("a malformed certificate")}))
    await user.should_see(marker="unreadable_result")                 # the card names its result
    await user.open("/study?" + urlencode({"path": _folder("a null list")}))
    await user.should_see("a result with a null list")               # rendered, not a server error


def _readings(root: Path, monkeypatch, tables: bool) -> dict[str, Path]:
    """Three otherwise identical saved studies: as written (current), its certificates made under an earlier policy
    (stale), and without certificates (legacy)."""
    current = _saved_study(root, monkeypatch, tables=tables, between=(5.0, 6.0))
    out = {"current": current}
    for label in ("stale", "legacy"):
        folder = root / label
        folder.mkdir()
        data = json.loads((current / "result.json").read_text())
        for view in ("verdict", "likelihood_verdict"):
            for c in data[view]["crossings"]:
                if label == "stale":
                    c["certificate"]["policy"] = "an-earlier-policy"
                else:
                    c.pop("certificate")
        (folder / "result.json").write_text(json.dumps(data))
        shutil.copy(current / "report.md", folder / "report.md")
        studies.record(folder, "track1", f"the {label} study")
        out[label] = folder
    return out


@pytest.mark.eos_band
@pytest.mark.parametrize("tables", [pytest.param(True, marks=pytest.mark.needs("eos")), False],
                         ids=["with the tables", "without the tables"])
async def test_stale_and_legacy_headlines_are_qualified_on_every_history_surface(user: User, tmp_path, monkeypatch,
                                                                                 tables):
    """CO-07: the stored level is the same on all three; its certification differs, visibly, on the Studies badge,
    the study's card and the point's explanation, and is filterable on its own; nothing is rewritten by viewing."""
    from adroit.evidence.points import points
    from adroit.evidence.results import load_result
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    folders = _readings(root, monkeypatch, tables)
    before = {k: hashlib.sha256((f / "result.json").read_bytes()).hexdigest() for k, f in folders.items()}
    level = "VIABLE" if tables else "VIABLE PENDING"
    badges = {"current": level, "stale": f"{level} · STALE CERTIFICATION",
              "legacy": f"{level} · NOT ASSESSED (LEGACY)"}
    rows = {s.folder: annotations.facts(root, s) for _, s in studies.tree(root)}
    for label, folder in folders.items():
        assert rows[str(folder)].badge == badges[label] and rows[str(folder)].verdict == level.lower()
    assert [f.folder for f, _ in annotations.select([(f, None) for f in rows.values()], certification="stale")] \
        == [str(folders["stale"])]
    await user.open("/studies")
    for words in badges.values():
        await user.should_see(words)
    for label, folder in folders.items():
        await user.open("/study?" + urlencode({"path": folder.name}))
        if label in ("stale", "legacy") or not tables:
            await user.should_see(marker="study_certification")
        else:
            await user.should_not_see(marker="study_certification")
        workflow, result = load_result(folder / "result.json")
        point = next(r for r in points(workflow, result) if r.kind == "thermal root").point_id
        await user.open("/study/point?" + urlencode({"path": folder.name, "point": point}))
        expected = {"current": "Certification: certified" if tables else "Certification: not certified",
                    "stale": "Certification: stale: certified under policy an-earlier-policy",
                    "legacy": "Certification: legacy, not assessed"}[label]
        await user.should_see(expected)
    assert before == {k: hashlib.sha256((f / "result.json").read_bytes()).hexdigest() for k, f in folders.items()}


@pytest.mark.eos_band
@pytest.mark.needs("eos")
async def test_an_independent_viable_witness_reads_certified_through_the_history(user: User, tmp_path):
    """The auditor's CO recheck, CR-04 (2026-10-26), through the rendered workbench: the single-idea study whose headline
    rests on one certified viable point, beside a waiting one (``_witness``). The Studies badge carries no mark, the
    certification filter finds it certified, its card says nothing is uncertified, and the waiting point's own
    explanation still says why it waits."""
    from adroit.ui.app import build_pages
    from tests.orchestrator.test_single_idea_support_certified import _witness
    root = build_pages(tmp_path / "runs")
    folder = root / "witness"
    result = _witness(tmp_path / "calculation")
    folder.mkdir()
    (folder / "result.json").write_text(result.model_dump_json())
    studies.record(folder, "single_idea", "the witness study")
    rows = {s.folder: annotations.facts(root, s) for _, s in studies.tree(root)}
    assert rows[str(folder)].badge == "VIABLE" and rows[str(folder)].certification == "certified"
    assert [f.folder for f, _ in annotations.select([(f, None) for f in rows.values()], certification="certified")] \
        == [str(folder)]
    await user.open("/studies")
    await user.should_see("the witness study")
    await user.open("/study?" + urlencode({"path": "witness"}))
    await user.should_not_see(marker="study_certification")
    await user.open("/study/point?" + urlencode({"path": "witness", "point": "thermal:0"}))
    await user.should_see("Certification: not certified")
    await user.open("/study/point?" + urlencode({"path": "witness", "point": "thermal:1"}))
    await user.should_see("Certification: certified")
