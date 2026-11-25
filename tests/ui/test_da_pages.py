"""The auditor's CZ recheck, DA-02 (2026-11-02): the live run page had shown a report bound to another version of the run's
result. The budget-stop writer had refused (its record, A, $0.10 committed, replaced by B, $0.20 committed and settled,
while its report was written), and the page had shown A's report under "The run's summary" beside B's cost. It now
reads the report against the result its cost was read from, and withholds one of another version, saying so. The
classic page (``adroit workbench --classic``) had read them apart too; it now reads them as one."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from nicegui.testing import User

from adroit.core.durable import write_atomic
from adroit.evidence import build
from adroit.evidence.bindings import read_report

A_REPORT = "$0.100000 committed"            # A's report: "LLM budget stopped before dispatch: $0.100000 committed of …"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stopped(folder: Path, replace: bool) -> Exception:
    """The real budget-stop writer (``cli._budget_boundary``) after a simulated ``BudgetExceeded`` (A: $0.10
    committed); with ``replace``, B ($0.20 committed and settled) published at the check after its report
    (``build.kept``), so that it refuses. Its job record as the workbench leaves a failed run. What it raised."""
    from adroit.agents.budget import BudgetExceeded
    from adroit.orchestrator import cli
    from adroit.ui import engine
    folder.mkdir(parents=True)

    @cli._budget_boundary
    def stopped(out):
        error = BudgetExceeded(.1, .25, .2)
        error.ledger_path = str(folder / "not_recorded.jsonl")
        raise error
    real = build.kept

    def interleave(path, content):
        b = {**json.loads(content), "committed_usd": .2, "settled_usd": .2, "uncertain_usd": 0.0}
        write_atomic(path, json.dumps(b).encode())
        return real(path, content)
    raised: Exception = AssertionError("the writer returned")
    with patch.object(build, "kept", interleave if replace else real):
        try:
            stopped(out=folder)
        except Exception as error:      # noqa: BLE001 - the refusal, or the budget stop's exit
            raised = error
    engine.save(engine.Job(title="AUDIT budget-stop publication", kind="agents",
                           command=["agents", "unused.json", "--budget", ".25"], folder=str(folder), status="failed",
                           returncode=1, note=str(raised)))
    return raised


async def test_the_live_page_withholds_a_report_of_another_version_of_its_result(user: User, tmp_path):
    """DA-02, the auditor's case: the writer refused; the folder holds B's record and A's report, bound to A. The live page
    shows B's cost and withholds A's report, saying why; A's committed total is not shown as this run's summary."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    raised = _stopped(root / "stopped", replace=True)
    assert isinstance(raised, build.Replaced)
    held = sha((root / "stopped" / "result.json").read_bytes())
    assert read_report(root / "stopped" / "report.md", held).state == "other"
    await user.open("/live?" + urlencode({"path": "stopped"}))
    await user.should_see("AUDIT budget-stop publication")
    await user.should_see(marker="live_report_withheld")
    await user.should_see("This run: $0.2000")
    await user.should_not_see(A_REPORT)


async def test_the_live_page_shows_the_report_of_its_result(user: User, tmp_path):
    """DA-02's positive control: nothing replaced. The report is bound to the record, and the live page shows it as
    the run's summary, with no qualification."""
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    _stopped(root / "stopped", replace=False)
    assert read_report(root / "stopped" / "report.md",
                       sha((root / "stopped" / "result.json").read_bytes())).state == "bound"
    await user.open("/live?" + urlencode({"path": "stopped"}))
    await user.should_see("The run's summary (report.md)")
    await user.should_see(A_REPORT)
    await user.should_not_see(marker="live_report_withheld")
    await user.should_not_see(marker="live_report_unchecked")


def test_the_classic_page_reads_a_run_s_report_and_figures_as_one(tmp_path, monkeypatch):
    """The classic page (DA-02's class): a report of another version of the run's result is withheld with the plots
    (its publication, stopped by B's (``Replaced``), keeps its mark, so the page says it was interrupted: the auditor's
    merge-round audit, HE-01, 2026-11-12); a bound report's figures are embedded from the bytes checked against its
    binding, one replaced since withheld, saying so; a report recording no link (written before) is shown as found,
    saying so, with the folder's plots."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from adroit.evidence import bindings
    from adroit.evidence.results import load_result
    from adroit.orchestrator import runs
    from adroit.workbench import pages
    from adroit.workbench.jobs import Job
    from adroit.workbench.server import report_view
    from tests.orchestrator.test_cw_recheck import _toy_study
    _stopped(tmp_path / "stopped", replace=True)
    report, images, note, embedded, _ = report_view(tmp_path / "stopped")
    assert report is None and not images and not embedded and "interrupted" in note
    folder = _toy_study(tmp_path / "runs", monkeypatch, False)
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    bindings.write_figure(fig, folder / "parameter_plane.png", 50)
    plt.close(fig)
    drawn = (folder / "parameter_plane.png").read_bytes()
    _, result = load_result(folder / "result.json")
    runs._write(folder, result.model_copy(update={"plots": ["parameter_plane.png"]}),
                "# Track 1\n\nAUDIT the plane\n\n![plane](parameter_plane.png)\n", "track1", "a toy plane")
    report, images, note, embedded, _ = report_view(folder)
    assert "AUDIT the plane" in report and embedded == {"parameter_plane.png": drawn} and not images and not note
    page = pages.job_page(Job(id="t", kind="track1", title="t", status="done"), report, images, note, embedded)
    assert "data:image/png;base64," in page and "/file/t/parameter_plane.png" not in page
    write_atomic(folder / "parameter_plane.png", drawn + b"\0")
    report, images, note, embedded, _ = report_view(folder)
    assert not embedded and not images and "parameter_plane.png" in note
    (folder / "report.md").write_text("# Track 1\n\nAUDIT written before\n")
    report, images, note, embedded, _ = report_view(folder)
    assert "AUDIT written before" in report and images == ["parameter_plane.png"] and "no link" in note
