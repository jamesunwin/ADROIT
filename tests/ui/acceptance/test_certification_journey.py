"""M1's acceptance (the consolidation plan, 2026-10-25; the auditor's consistency audit, CA-01): remove the
equation-of-state tables, and the saved result, the report, the Studies badge and its filter, the evidence's point
table and its explanation of a point all lose thermal certification together, while an experimental exclusion of a
fixed point is still shown as one. A Track 1 study saved by the real writer (``runs._write``) from a real verdict over
a toy plane: the density and the constraint outcomes are substituted (``SUBSTITUTED``), everything else is ADROIT's.
"""
from __future__ import annotations

import importlib
import json
import runpy
from pathlib import Path

import pytest
from nicegui.testing import User

from adroit.constraints import relic
from adroit.parameter_space.classes import Spin1Class
from adroit.parameter_space.likelihood import LikelihoodSettings
from adroit.parameter_space.scan import PointResult

SUBSTITUTED = {"density": "Ωh² = 0.12/g² (toy, the same with every table)",
               "constraints": "one toy constraint, excluding between two couplings, through verdict.evaluate"}
v = importlib.import_module("adroit.parameter_space.verdict")
H = runpy.run_path(str(Path(__file__).parents[2] / "parameter_space" / "test_eos_verdict.py"))


def _saved_study(root: Path, monkeypatch, *, tables: bool, between: tuple[float, float]) -> Path:
    """A Track 1 study written as the workbench writes one, its verdict computed over the toy plane."""
    from adroit.model_building.audit import audit
    from adroit.orchestrator import runs, studies, track1
    from adroit.parameter_space import simplified
    monkeypatch.setattr(Spin1Class, "omega_h2", lambda self, p: H["_toy_density"](p))
    monkeypatch.setattr("adroit.parameter_space.searches.prefetch_lhc", lambda cls, pts, *a: [None] * len(pts))

    def evaluate(cls, p, *args):
        return PointResult(point=p, omega_h2=H["_toy_density"](p), dd_kind="SI", dd_sigma_cm2=0, dd_limit_cm2=1,
                           excluded={"toy": between[0] < p.g_chi < between[1], "colliders (CMS)": False})
    monkeypatch.setattr(v, "evaluate", evaluate)
    if not tables:
        monkeypatch.setattr(relic, "eos_folder", lambda: None)
    H["DESIGN"]["omega"] = lambda t, g: 0.12 / g ** 2
    scan = H["_plane"]([0.98, 1.02])
    scan = scan.model_copy(update={"points": [r.model_copy(update={"excluded": {
        "toy": between[0] < r.point.g_chi < between[1], "colliders (CMS)": False}}) for r in scan.points]})
    cuts, combined = v.verdict_pair(scan, likelihood=LikelihoodSettings())
    spec = simplified.model("vector", 10, 30)
    request = track1.Track1Request(spec=spec, model_class=Spin1Class(), fixed=scan.request.fixed, x=scan.request.x,
                                   y=scan.request.y, likelihood=LikelihoodSettings(), literature=False)
    result = track1.Track1Result(request=request, audit=audit(spec), class_name="vector", fixed=request.fixed,
                                 scan=scan, verdict=cuts, likelihood_verdict=combined,
                                 notes=[f"SUBSTITUTED: {k}: {w}" for k, w in SUBSTITUTED.items()])
    folder = root / ("with_tables" if tables else "without_tables")
    folder.mkdir(parents=True)
    runs._write(folder, result, track1.report(result), "track1", "a toy plane")
    studies.record(folder, "track1", "a toy plane" + ("" if tables else " (no tables)"))
    return folder


def _surfaces(folder: Path) -> dict:
    """What each surface says of the saved study."""
    from adroit.evidence.points import points
    from adroit.evidence.results import load_result
    from adroit.orchestrator import study_headline
    data = json.loads((folder / "result.json").read_text())
    workflow, result = load_result(folder / "result.json")
    table = points(workflow, result)
    return {"stored": data["verdict"]["level"], "combined": data["likelihood_verdict"]["level"],
            "report": (folder / "report.md").read_text(), "badge": study_headline.of(folder)[0],
            "filter": study_headline.of(folder)[1],
            "rows": {r.status for r in table if r.kind != "grid sample"}}


@pytest.mark.eos_band
@pytest.mark.parametrize("between, without, with_tables", [
    ((5.0, 6.0), "viable_pending", "viable"), ((0.0, 10.0), "pending", "excluded")])
def test_without_the_tables_every_surface_loses_thermal_certification_together(tmp_path, monkeypatch, between,
                                                                               without, with_tables):
    folder = _saved_study(tmp_path, monkeypatch, tables=False, between=between)
    found = _surfaces(folder)
    assert found["stored"] == found["combined"] == without
    assert found["badge"].startswith(without.replace("_", " ").upper()) and found["filter"] == without.replace("_", " ")
    assert "not certified" in found["report"] and "adroit setup --fetch" in found["report"]
    if without == "pending":            # D-2: excluded by the computed constraints, waiting on the band alone: the
        # experimental exclusion is shown as such (the owner, 2026-11-23), its certification not claimed
        assert found["rows"] == {"excluded"} and "excluded by toy" in found["report"]
    else:
        assert found["rows"] == {"pending"}                   # no surviving crossing decided on the surfaces


def test_a_fixed_point_exclusion_still_shows_on_the_grid_without_the_tables(tmp_path, monkeypatch):
    """The grid samples' own exclusions are experimental exclusions of fixed points: they do not wait for the tables
    (the plan's claim kinds), and the point table shows them excluded."""
    from adroit.evidence.points import points
    from adroit.evidence.results import load_result
    folder = _saved_study(tmp_path, monkeypatch, tables=False, between=(0.0, 10.0))
    workflow, result = load_result(folder / "result.json")
    grid = [r for r in points(workflow, result) if r.kind == "grid sample"]
    assert grid and {r.status for r in grid} == {"excluded"}


@pytest.mark.eos_band
def test_a_root_waiting_on_its_thermal_checks_alone_shows_its_exclusion_and_not_a_certification(tmp_path,
                                                                                                monkeypatch):
    """The owner (2026-11-23), superseding the M1 rule that a waiting root's nominal exclusion was not the decision:
    a root its comparisons exclude, whose open checks are its thermal claim's own (here the band, the tables
    missing), shows the exclusion; its certificate still reads not certified."""
    from adroit.evidence.points import explain, points
    from adroit.evidence.results import load_result
    folder = _saved_study(tmp_path, monkeypatch, tables=False, between=(0.0, 10.0))
    workflow, result = load_result(folder / "result.json")
    root = next(r for r in points(workflow, result) if r.kind == "thermal root")
    shown = explain(folder / "result.json", root.point_id)
    toy = next(c for c in shown.comparisons if c.constraint == "toy")
    assert toy.group == "excluded" and root.status == "excluded"
    assert shown.certification.startswith("not certified")


@pytest.mark.needs("eos")
def test_with_the_tables_the_same_study_is_certified_on_every_surface(tmp_path, monkeypatch):
    folder = _saved_study(tmp_path, monkeypatch, tables=True, between=(5.0, 6.0))
    found = _surfaces(folder)
    assert found["stored"] == found["combined"] == "viable" and found["badge"] == "VIABLE"
    assert "not certified" not in found["report"] and found["rows"] == {"allowed"}


@pytest.mark.eos_band
async def test_the_studies_page_shows_the_stored_headline_and_its_combined_view(user: User, tmp_path, monkeypatch):
    """The Studies badge reads the stored verdict: the cuts level, the combined view where it differs, and the
    study's own page the same words."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    _saved_study(root, monkeypatch, tables=False, between=(5.0, 6.0))
    await user.open("/studies")
    await user.should_see("VIABLE PENDING")
    await user.open("/study?path=without_tables")
    await user.should_see("VIABLE PENDING")
