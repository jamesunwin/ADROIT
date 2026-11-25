"""The auditor's DG recheck (the independent audit of 2026-11-06 (dg recheck), pin 43332a2): DH-01, a calibrated review packet taking
its overlay's digest from this process's map of draws after its draw's hold had ended, so that another thread's packet,
completed meanwhile, gave its overlay to the first beside the first curve's geometry; DH-03, the single idea's
calculation dates lost when its request's preparation took the decorator that records them; DH-04, a figure that is a
link drawn under its target folder's lock, over an entry in a folder another writer held. (DH-02, the plane's own
appearance of each point, is repaired in ``tests/version_matrix.py`` and its harnesses.) No calculation, provider or
signature: the curves, pages and results are fixtures, labelled simulated; $0 is spent."""
from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from adroit.core.durable import Busy, publishing
from tests.orchestrator import test_df_fixes as df

ROOT = Path(__file__).parents[2]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- DH-01: a review packet is its writer's whole -------------------------------------------------------------------

def _page() -> bytes:
    """A blank source page (the page a figure was digitised from), SIMULATED."""
    from PIL import Image
    stream = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(stream, format="PNG")
    return stream.getvalue()


def _contract(label: str):
    """Curve ``label`` of a SIMULATED digitised figure on ``_page``: A's rising, B's falling (the auditor's DH-01 fixture)."""
    from adroit.core.private_limits import LimitContract
    rising = [(10, 1e-43), (20, 2e-43), (40, 4e-43)]
    return LimitContract(
        adapter="si_isoscalar_curve", benchmark="elastic_contact_O1_cp_equals_cn", quantity="sigma_nucleon_cm2",
        units="cm2", points=rising if label == "A" else [(10, 4e-43), (20, 3e-43), (40, 2.5e-43)],
        mass_range=(10, 40), halo={"rho_gev_cm3": .3, "v0_km_s": 220., "v_earth_km_s": 232., "v_esc_km_s": 544.},
        confidence_level=.95, construction="SIMULATED source", selection="observed", dataset_id="synthetic:race",
        overlap="disjoint_from_selected", origin="figure_digitised", x_relative_error=.05, y_relative_error=.05,
        assumptions=["SIMULATED local source; no physics calculation"], source_panel="SIMULATED",
        x_scale="log", y_scale="log",
        figure_axes={"asset_sha256": sha(_page()), "page": 1, "pixel_box": [20, 20, 380, 280], "x_range": [8, 50],
                     "y_range": [.5e-43, 6e-43]})


@contextmanager
def packets():
    """The review packet's sources stood in for: ``synthetic:A`` and ``synthetic:B`` are curves A and B on one blank
    page, each with two printed anchors (``limit_contract``, ``_page_image``); the packet's rendering, its draw, its
    writer and its reader (``_reviewed``) are ADROIT's."""
    from adroit.constraints import experimental_review as review
    value = {"scientific": {"claims": [{"key": "validation_reference", "value": {"points": [[12, 1.2e-43],
                                                                                            [30, 3e-43]]}}]}}
    contracts = {"synthetic:A": _contract("A"), "synthetic:B": _contract("B")}
    with patch.object(review, "limit_contract", side_effect=lambda ref, *a: (contracts[ref], value)), \
            patch.object(review, "_page_image", return_value=_page()):
        yield contracts


B_PACKET = """
import json, sys
from pathlib import Path
from tests.orchestrator.test_dh_fixes import packets
from adroit.constraints import experimental_review as review
out = Path(sys.argv[1])
with packets():
    print("trying", flush=True)
    report = review.plot_packet("synthetic:B", "limit", out, object())
print(json.dumps({k: report[k] for k in ("overlay_sha256", "geometry_sha256")}), flush=True)
"""


def _b_packet(out: Path, by: str):
    """B, the whole packet writer of curve B into ``out``, in another thread or another process: (a callable that
    waits until B is trying, a callable that waits up to its seconds for B to finish, and a callable that waits for B
    to finish and gives its report's overlay and geometry)."""
    if by == "another process":
        process = subprocess.Popen([sys.executable, "-c", B_PACKET, str(out)], cwd=ROOT, stdout=subprocess.PIPE,
                                   text=True)

        def waiting(seconds):
            try:
                process.wait(seconds)
            except subprocess.TimeoutExpired:
                pass
        return (lambda: process.stdout.readline().strip() == "trying", waiting,
                lambda: (process.wait(90), json.loads(process.stdout.readline()))[1])
    from adroit.constraints import experimental_review as review
    trying, found = threading.Event(), {}

    def b():
        trying.set()
        report = review.plot_packet("synthetic:B", "limit", out, object())
        found.update({k: report[k] for k in ("overlay_sha256", "geometry_sha256")})
    thread = threading.Thread(target=b)
    thread.start()
    return (lambda: trying.wait(10), thread.join, lambda: (thread.join(90), found)[1])


@pytest.mark.parametrize("by", ["another thread", "another process"])
def test_a_review_packet_is_its_writer_s_whole(tmp_path, by):
    """DH-01, the auditor's case: A writes the packet of curve A; at the return of its overlay's draw, B, the whole packet
    writer of curve B into the same folder (another thread, or another process), starts, and is given five seconds to
    write its packet while A's is being written. A's packet is written whole
    under its hold of the folder, from its first file to its record: its record names A's overlay as A drew it, beside
    A's geometry, and B waits for it. Then B's is written whole: the folder is B's packet, which the reader accepts as
    B's, and refuses as A's. Before, the thread's B completed inside A's packet, and A's record named B's overlay beside
    A's geometry, which the reader accepted."""
    from adroit.constraints import experimental_review as review
    out = tmp_path / "packet"
    real, seen = review._source_overlay, {}

    def overlay(reference, *args, **kwargs):
        path = real(reference, *args, **kwargs)
        if reference == "synthetic:A":
            seen["A overlay"] = sha(Path(path).read_bytes())
            seen["B"] = _b_packet(out, by)
            assert seen["B"][0]()
            seen["B"][1](5)                              # B given 5 s to write its packet, A's still being written
        return path
    with packets() as contracts:
        with patch.object(review, "_source_overlay", overlay):
            a = review.plot_packet("synthetic:A", "limit", out, object())
        b = seen["B"][2]()
        reviewed = review._reviewed(out, "synthetic:B", "limit", contracts["synthetic:B"])
        with pytest.raises(ValueError, match="another revision or result"):
            review._reviewed(out, "synthetic:A", "limit", contracts["synthetic:A"])
    page = _page()
    assert a["overlay_sha256"] == seen["A overlay"] != b["overlay_sha256"], (a, seen, b)
    assert a["geometry_sha256"] == review._identity(page, contracts["synthetic:A"])[1] != b["geometry_sha256"]
    assert reviewed == (sha(page), b["geometry_sha256"], b["overlay_sha256"])
    assert sha((out / "source_overlay.png").read_bytes()) == b["overlay_sha256"]


def test_a_review_packet_is_read_as_its_writer_wrote_it(tmp_path):
    """DH-01's baseline: a packet written whole is read as its writer's: the reader's page, geometry and overlay are
    the ones its writer recorded, the overlay as drawn."""
    from adroit.constraints import experimental_review as review
    out = tmp_path / "packet"
    with packets() as contracts:
        a = review.plot_packet("synthetic:A", "limit", out, object())
        reviewed = review._reviewed(out, "synthetic:A", "limit", contracts["synthetic:A"])
    assert reviewed == (a["source_image_sha256"], a["geometry_sha256"], a["overlay_sha256"])
    assert a["overlay_sha256"] == sha((out / "source_overlay.png").read_bytes())


def test_a_review_packet_s_overlay_replaced_since_is_refused(tmp_path):
    """DH-01's reader: a packet whose overlay another writer has drawn over since (a standalone draw, under a hold
    taken for it) is refused as changed, never accepted with the new overlay."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from adroit.constraints import experimental_review as review
    from adroit.evidence.bindings import write_figure
    out = tmp_path / "packet"
    with packets() as contracts:
        review.plot_packet("synthetic:A", "limit", out, object())
        fig, ax = plt.subplots()
        ax.plot([0, 1], [1, 0])
        write_figure(fig, out / "source_overlay.png", 40)
        plt.close(fig)
        with pytest.raises(ValueError, match="changed since it was drawn"):
            review._reviewed(out, "synthetic:A", "limit", contracts["synthetic:A"])


def test_a_review_packet_read_while_another_is_written_is_refused(tmp_path):
    """DH-01's reader, read while B's packet is written whole into the folder, after it has read A's record and before
    its page and overlay: refused as changed, never A's record with B's picture."""
    from adroit.constraints import experimental_review as review
    out = tmp_path / "packet"
    real, done = Path.read_bytes, []

    def read_bytes(self):
        if self.name == "source_page.bin" and not done:
            done.append(True)
            review.plot_packet("synthetic:B", "limit", out, object())
        return real(self)
    with packets() as contracts:
        review.plot_packet("synthetic:A", "limit", out, object())
        with patch.object(Path, "read_bytes", read_bytes), \
                pytest.raises(ValueError, match="changed since it was drawn|another curve or calibration"):
            review._reviewed(out, "synthetic:A", "limit", contracts["synthetic:A"])
    assert done


def test_a_review_packet_and_its_review_listing_are_one_writer_s(tmp_path, monkeypatch):
    """DH-01, the command (``adroit experiments review``): the packet and its ``review.json`` are written under one hold
    of the folder; with the folder held by another writer, it waits, then refuses, writing nothing."""
    from typer.testing import CliRunner
    from adroit.constraints import experimental_review as review
    from adroit.orchestrator import experimental_cli
    out = tmp_path / "packet"
    calls = []
    monkeypatch.setattr(review, "packet", lambda ref, result, keys=None: {"keys": ["limit_contract",
                                                                                     "validation_reference"]})
    monkeypatch.setattr(review, "plot_packet", lambda *a, **k: calls.append(k.get("claim")) or {"plot": ""})
    command = ["review", "synthetic:A", "--result", "limit", "--out", str(out)]
    with df._held(out, "another thread"), df._waiting():
        before = df._files(out)
        result = CliRunner().invoke(experimental_cli.app, command)
        said = re.sub(r"[\s│╭╮╰╯─]+", " ", result.output)
        assert result.exit_code != 0 and "nothing was written" in said, result.output
        assert df._files(out) == before and not calls
    result = CliRunner().invoke(experimental_cli.app, command)
    assert result.exit_code == 0, result.output
    assert calls and calls[0] is not None and (out / "review.json").exists()


# --- DH-03: a single idea's result records when it was calculated ---------------------------------------------------

def _calculated(request, folder, fetch=None, claim=None):
    """``single_idea._study`` stood in for (no fit, scan or search): a typed result of its request, SIMULATED."""
    from adroit.orchestrator.single_idea import SingleIdeaResult
    Path(folder).mkdir(parents=True, exist_ok=True)
    return SingleIdeaResult(request=request, level="undetermined", summary="SIMULATED calculation",
                            fit_quality="not_computed", constraint_compatibility="undetermined",
                            thermal_viability="undetermined", unsupported="SIMULATED calculation")


def test_a_single_idea_result_records_when_it_was_calculated(tmp_path, monkeypatch):
    """DH-03, the auditor's case: a single idea run afresh (its request prepared, its calculation alone stood in for) records
    when its calculation started and completed, in order, and its report says so. Before, ``prepared``, inserted below
    the decorator that records them, had taken it, and the result kept no dates ("Calculation date: unknown")."""
    from adroit.orchestrator import single_idea
    from tests.orchestrator.test_research_assistance import request
    monkeypatch.setattr(single_idea, "_study", _calculated)
    result = single_idea.run(single_idea.prepared(request().study), tmp_path / "idea")
    assert result.calculation_started_at and result.calculation_completed_at, result
    assert result.calculation_started_at <= result.calculation_completed_at
    report = single_idea.report(result)                 # dated from the result's own dates (``dated_report``)
    assert f"Calculation started (UTC): {result.calculation_started_at}" in report
    assert "unknown / not recorded" not in report


def test_a_promotion_child_s_dates_are_its_calculation_s(tmp_path, monkeypatch):
    """DH-03, the promotion's child (``promote._study``, its calculation alone stood in for): its typed result records
    its calculation's start and completion, within its evidence's (captured before the calculation, completed with its
    publication), and its saved report says when it was calculated."""
    from adroit.orchestrator.single_idea import SingleIdeaResult
    from tests.orchestrator import test_dg_fixes as dg
    folder = dg._promotion_child(tmp_path, monkeypatch, False)
    envelope, _ = dg._captured(folder)
    result = SingleIdeaResult.model_validate_json((folder / "result.json").read_bytes())
    context = envelope.context
    assert result.calculation_started_at and result.calculation_completed_at, result
    assert context.calculation_started_at <= result.calculation_started_at <= result.calculation_completed_at
    assert not context.calculation_completed_at or result.calculation_completed_at <= context.calculation_completed_at
    assert "Calculation started (UTC):" in (folder / "report.md").read_text()


# --- DH-04: a figure that is a link is drawn under its own folder's hold -------------------------------------------

B_DRAWS = """
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from adroit.core import durable
from adroit.evidence.bindings import write_figure
durable.publishing.__wrapped__.__defaults__ = (None, 0.2)
fig, ax = plt.subplots()
ax.plot([0, 1], [1, 0])
try:
    write_figure(fig, Path(sys.argv[1]), 40)
except durable.Busy as error:
    print(error)
    sys.exit(3)
"""


def _linked(tmp: Path) -> tuple[Path, Path, bytes]:
    """``publication/plane.png``, a link to ``assets/source.png`` within the runs tree (as the token's policy allows),
    made before any writer holds either folder: (the link, its target, the target's bytes)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    publication, assets = tmp / "runs" / "publication", tmp / "runs" / "assets"
    publication.mkdir(parents=True)
    assets.mkdir()
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    stream = io.BytesIO()
    fig.savefig(stream, format="png", dpi=40)
    plt.close(fig)
    (assets / "source.png").write_bytes(stream.getvalue())
    (publication / "plane.png").symlink_to(assets / "source.png")
    return publication / "plane.png", assets / "source.png", stream.getvalue()


def _b_draws(path: Path, by: str) -> str:
    """B draws its own figure at ``path`` by ``write_figure`` (another thread, or another process), its wait for
    another's hold shortened: "drawn", or why it was refused."""
    if by == "another process":
        done = subprocess.run([sys.executable, "-c", B_DRAWS, str(path)], cwd=ROOT, capture_output=True, text=True)
        return "drawn" if done.returncode == 0 else done.stdout.strip() or done.stderr.strip()
    import matplotlib.pyplot as plt
    from adroit.evidence.bindings import write_figure
    found = []

    def b():
        fig, ax = plt.subplots()
        ax.plot([0, 1], [1, 0])
        try:
            write_figure(fig, path, 40)
            found.append("drawn")
        except Busy as error:
            found.append(str(error))
        plt.close(fig)
    with df._waiting():
        thread = threading.Thread(target=b)
        thread.start()
        thread.join(30)
    return found[0]


@pytest.mark.parametrize("by", ["another thread", "another process"])
def test_a_figure_that_is_a_link_is_drawn_under_its_own_folder_s_hold(tmp_path, by):
    """DH-04, the auditor's case: ``publication/plane.png`` is a link to ``assets/source.png``, and A, holding
    ``publication``, has bound its report to it. B draws its own figure at ``publication/plane.png`` (another thread,
    or another process): the entry it would replace is in ``publication``, so B waits for A's hold and is refused,
    nothing drawn; the link, its target and A's bound figure are as they were throughout A's hold. Before, B took the
    target folder's lock, and replaced the link inside A's held folder."""
    from adroit.evidence import bindings
    path, target, data = _linked(tmp_path)
    with publishing(path.parent) as claim:
        report = bindings.report_of(bindings.bind("![A](plane.png)", "a" * 64, path.parent, ["plane.png"],
                                                  claim).encode(), "a" * 64)
        said = _b_draws(path, by)
        assert path.is_symlink() and target.read_bytes() == data
        assert bindings.figure_of(path.read_bytes(), "plane.png", report) == data
    assert "nothing was written" in said, said


@pytest.mark.parametrize("by", ["another thread", "another process"])
def test_a_figure_that_is_a_link_is_not_held_by_its_target_s_folder(tmp_path, by):
    """DH-04, the other order: A holds ``assets``, the folder of the link's target. B's figure at
    ``publication/plane.png`` replaces the entry in ``publication``, which no writer holds, so B draws; the target in
    A's held folder is untouched."""
    path, target, data = _linked(tmp_path)
    with publishing(target.parent):
        said = _b_draws(path, by)
        assert target.read_bytes() == data
    assert said == "drawn" and not path.is_symlink() and path.read_bytes() != data


def test_a_writer_s_draw_over_a_link_in_its_folder_is_its_own(tmp_path):
    """DH-04, a writer holding ``publication`` draws its own figure over the link there: under its own hold (no
    second hold, no wait on itself), named by the entry it replaced, never by the link's target, and its report is
    bound to the bytes it drew."""
    import matplotlib.pyplot as plt
    from adroit.evidence import bindings
    from adroit.evidence.bindings import write_figure
    path, target, data = _linked(tmp_path)
    fig, ax = plt.subplots()
    ax.plot([0, 1], [1, 0])
    with publishing(path.parent) as claim:
        write_figure(fig, path, 40)
        drawn = path.read_bytes()
        assert claim.drawn == {str(path.parent.resolve() / "plane.png"): sha(drawn)}
        bound = bindings.binding(bindings.bind("![A](plane.png)", "a" * 64, path.parent, ["plane.png"], claim))
    plt.close(fig)
    assert bound.figures == {"plane.png": sha(drawn)} and target.read_bytes() == data and not path.is_symlink()
