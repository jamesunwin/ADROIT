"""The workbench's pages read the one stored assessment (the owner's plan of 2026-11-24): a thermal root excluded at
the halo region's centre whose robustness is incomplete is listed with its own status and explained, qualified, on its
point page; never as plain pending. Headless (NiceGUI's ``User``); the real-browser journeys are deferred to 1.0.1
(the owner, 2026-11-24). The root is the saved vector study's 88.59 GeV point (``tests/fixtures/vector_dd_pending``)."""
import gzip
import json
from pathlib import Path
from urllib.parse import urlencode

from nicegui.testing import User

from adroit.evidence.points import CENTRAL
from adroit.ui.app import build_pages

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _study(tmp_path) -> Path:
    """A small saved Track 1 study (``tests.evidence.test_points._result``) whose thermal root is the vector's 88.59 GeV
    point as saved: pending, its halo coverage incomplete, excluded by direct detection at the region's centre."""
    from adroit.orchestrator import studies
    from adroit.orchestrator.track1 import Track1Result
    from adroit.parameter_space.verdict import Crossing
    from tests.evidence.test_points import _result
    folder = tmp_path / "runs" / "vector_central"
    folder.mkdir(parents=True)
    path = _result(folder)
    saved = next(c for c in json.load(gzip.open(FIXTURES / "vector_dd_pending.json.gz"))["pending_crossings"]
                 if abs(c["point"]["m_chi"] - 88.59) < 0.01)
    result = Track1Result.model_validate_json(path.read_text())
    root = Crossing.model_validate(saved | {"kind": "contour", "converged": True})
    result = result.model_copy(update={"verdict": result.verdict.model_copy(update={"crossings": [root]}),
                                       "fixed": result.scan.request.fixed})
    path.write_text(result.model_dump_json(indent=1))
    (folder / "report.md").write_text("# Track 1\n")
    studies.record(folder, "track1", "a vector, central exclusion")
    return folder


async def test_the_central_exclusion_is_listed_and_explained_qualified(user: User, tmp_path) -> None:
    _study(tmp_path)
    build_pages(tmp_path / "runs")
    await user.open("/study?" + urlencode({"path": "vector_central"}))
    table = user.find(marker="points").elements.pop()
    row = next(r for r in table.rows if r["point"] == "contour:0")
    assert row["status"] == CENTRAL
    assert row["reason"] == "excluded at the central SHM by direct detection; halo robustness incomplete"
    await user.open("/study/point?" + urlencode({"path": "vector_central", "point": "contour:0"}))
    await user.should_see(CENTRAL)
