"""The permanent acceptance gate's headless journeys (the consolidation plan's M4, 2026-10-25): each step through the
workbench's pages, asserting where it leads, the scientific qualification it shows (from the stored certificate) and
the cost it shows (from the accounting facts). The real command line runs in process (``inline``); the browser and
the child processes are the release layer's (``scripts/browser_acceptance.py``). Journeys 5 and 6 are in
``test_accounting_journeys.py`` and ``test_damage_journeys.py``; M1's surfaces in ``test_certification_journey.py``.

Each journey is also a function (``journey_*``), so that the mutation controls (``test_mutation_controls.py``) can
run it against a deliberately broken workbench and require it to fail.
"""
from __future__ import annotations

from pydantic import SecretStr
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
import yaml
from nicegui import ui
from nicegui.testing import User

from adroit.constraints import relic
from adroit.parameter_space.classes import Spin1Class
from adroit.parameter_space.scan import PointResult
from tests.ui.test_run_outcomes import (IDEA_TOKENS, MODELS, VALUES_TOKENS, ProviderDown, dollars,  # noqa: F401
                                        idea_replies, inline, page, proposals, provider, start_intake, usd)

SUBSTITUTED = {
    "the provider": "a scripted SDK behind the real budgeted client and journal (tests/ui/test_run_outcomes.Provider)",
    "the launcher": "the real command line in process (inline), the job record and log written as the runner does",
    "journey 1's scan": "Ωh² = 0.12 m_χ/100 GeV and one toy constraint (allowed) in place of the model's relic "
                        "solver and searches; the scan, verdict, certificate, writer and pages are ADROIT's",
    "journey 1's setup check": "its machine items (the external data the real searches would read: CRESST-III, "
                               "CDMSlite, the optimum interval, the solar model) reported as not used, since the "
                               "toy replaces those searches: the journey never depends on this machine's data "
                               "(the auditor's CO-08: it had stopped at 'Setup check: blocked' without them)",
    "journey 1's scan workers": "the scan's two worker processes run as threads of the test, so the toy reaches every "
                                "grid point (CO-08's repair: spawned workers had not seen the toy, and the grid had "
                                "silently run the real searches, which read DIAMX's data)",
    "journey 1's limit-table note": "the scan's note on precomputed limit tables says none is used (the toy uses "
                                    "none; finding the current ones fingerprints the experiments' data files)",
    "journey 1's direct-detection figure": "not drawn (it overlays the experiments' published limits, read from "
                                           "their data files); the parameter-plane figure is ADROIT's",
    "journey 2's children": "single_idea.run returns a study whose thermal point waits for the equation-of-state "
                            "tables; the promotion, its child folders and their records are ADROIT's",
    "journey 3's requests": "two free requests (adroit setup); the batch runner runs in process",
}
TYPED = yaml.safe_dump(__import__("adroit.parameter_space.simplified", fromlist=["model"]).model(
    "vector", 10, 125, .001, .25).model_dump(mode="json"))


def _toy_physics(monkeypatch) -> None:
    """Journey 1's substituted scan and its setup check's machine items (``SUBSTITUTED``)."""
    from adroit.orchestrator import setup_check
    from adroit.parameter_space import scan, verdict
    monkeypatch.setattr(setup_check, "machine_items", lambda needs, tools_dir=None: [setup_check.Item(
        section="uses", message=f"{need} (SUBSTITUTED: not used; the toy replaces these searches)") for need in needs])
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(scan, "ProcessPoolExecutor", ThreadPoolExecutor)    # the toy reaches every grid point
    monkeypatch.setattr("adroit.parameter_space.limit_tables.current", lambda *a, **k: [])
    monkeypatch.setattr("adroit.parameter_space.plots.direct_detection", lambda *a, **k: None)
    density = lambda p: 0.12 * p.m_chi / 100.0                               # noqa: E731
    monkeypatch.setattr(Spin1Class, "omega_h2", lambda self, p: density(p))
    monkeypatch.setattr("adroit.parameter_space.searches.prefetch_lhc", lambda c, p, *a: [None] * len(p))

    def evaluate(cls, p, *args, **kwargs):
        return PointResult(point=p, omega_h2=density(p), dd_kind="SI", dd_sigma_cm2=0, dd_limit_cm2=1,
                           excluded={"toy": False, "colliders (CMS)": False})
    monkeypatch.setattr(scan, "evaluate", evaluate)
    monkeypatch.setattr(verdict, "evaluate", evaluate)


async def journey_typed_intake_to_study(user: User, root: Path, monkeypatch, tables: bool) -> dict:
    """Journey 1: a typed model → the intake run → its draft (the primary action) → review and approve → the
    model's page → Constrain this model (Track 1) → the scan run → the study (the primary action): its headline badge
    from the stored verdict, its cost from the accounting facts. Returns what each step showed."""
    _toy_physics(monkeypatch)
    if not tables:
        monkeypatch.setattr(relic, "eos_folder", lambda: None)
    seen = {}
    await user.open("/models/intake")
    kind = next(e for e in user.find(kind=ui.select).elements if e.props.get("label") == "Model input kind")
    kind.value = "typed"
    user.find("Idea, TeX or typed field/model YAML").elements.pop().value = TYPED
    user.find("Start reviewed intake").click()
    await user.should_see("Draft ready for review")
    await user.should_see("This run: $0")
    seen["intake"] = "draft ready, $0"
    user.find(marker="primary_action").click()
    await user.should_see("Candidate 1")
    seen["draft"] = "the draft page"
    user.find("I reviewed the transcription, assumptions, parameters and canonical model").click()
    user.find("Save reviewed revision").click()
    await user.should_see("Constrain this model (Track 1)")
    from adroit.library.personal import Catalog
    reference = Catalog().listing()[0][-1].reference
    seen["model"] = reference
    await user.open("/new/track1?" + urlencode({"catalog": reference}))
    user.find("x axis").elements.pop().value = "m_chi:10:1000:log:6"
    user.find("y axis").elements.pop().value = "g_chi:0.05:0.5:log:3"
    await user.should_see("reviewed")
    user.find(marker="run_model_scan").click()
    await user.should_see("Study complete", retries=200)
    seen["scan"] = "study complete"
    user.find(marker="primary_action").click()
    want = "VIABLE" if tables else "VIABLE PENDING"
    await user.should_see(want)
    await user.should_see("cost: $0 (no paid request)")
    seen["study"] = want
    return seen


@pytest.mark.eos_band
@pytest.mark.parametrize("tables", [pytest.param(True, marks=pytest.mark.needs("eos")), False],
                         ids=["with the tables", "without the tables"])
async def test_journey_1_a_typed_model_to_its_study(user: User, tmp_path, monkeypatch, inline, tables):  # noqa: F811
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    seen = await journey_typed_intake_to_study(user, root, monkeypatch, tables)
    assert seen["study"] == ("VIABLE" if tables else "VIABLE PENDING")
    study = next(Path(f) for f in inline if (Path(f) / "result.json").exists())
    stored = json.loads((study / "result.json").read_text())["verdict"]
    assert stored["level"] == ("viable" if tables else "viable_pending")
    assert all(c.get("certificate") for c in stored["crossings"])          # the badge's level is the stored one


async def journey_uncertain_bill(user: User, root: Path, provider) -> None:  # noqa: F811
    """Journey 1 with uncertain spending: the request is reserved, then the transport fails after dispatch: the run
    page shows the reservation, the session's too, and the primary action still leads back to the session."""
    provider["anthropic"].replies.append(ProviderDown("the connection dropped after dispatch"))
    await start_intake(user, "anthropic")
    await user.should_see("reserved whose bill is not yet known")
    await user.should_not_see("no paid request was sent")


async def test_journey_1_with_an_uncertain_bill(user: User, tmp_path, provider, inline):  # noqa: F811
    from adroit.ui.app import build_pages
    build_pages(tmp_path / "runs")
    await journey_uncertain_bill(user, tmp_path / "runs", provider)


async def journey_settled_bill(user: User, root: Path, provider, inline) -> None:  # noqa: F811
    """Journey 1's paid intake, settled: the run page shows its own cost (the proposals and the values, the builder's
    two calls) to $0.0001 and leads to its draft."""
    idea_replies(provider["anthropic"].replies)
    await start_intake(user, "anthropic")
    await user.should_see("Draft ready for review")
    await user.should_see(f"This run: {usd(dollars('anthropic', IDEA_TOKENS) + dollars('anthropic', VALUES_TOKENS))}")
    user.find(marker="primary_action").click()
    await user.should_see("Candidate 1: RealSinglet")


async def test_journey_1_a_paid_intake_shows_its_settled_cost_and_opens_its_draft(user: User, tmp_path, provider,  # noqa: F811
                                                                                   inline):  # noqa: F811
    from adroit.ui.app import build_pages
    build_pages(tmp_path / "runs")
    await journey_settled_bill(user, tmp_path / "runs", provider, inline)


async def test_journey_1_without_a_key_nothing_is_reserved_and_the_variable_is_named(user: User, tmp_path, monkeypatch,
                                                                                     inline):  # noqa: F811
    from adroit.core.config import get_settings
    from adroit.ui.app import build_pages
    monkeypatch.setattr(get_settings(), "anthropic_api_key", SecretStr(""))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    build_pages(tmp_path / "runs")
    await start_intake(user, "anthropic")
    await user.should_see("ANTHROPIC_API_KEY")
    await user.should_not_see("reserved whose bill is not yet known")


def _saved_study(root: Path, monkeypatch) -> Path:
    """A saved Track 1 study (``test_certification_journey``'s, without the tables)."""
    from tests.ui.acceptance.test_certification_journey import _saved_study as saved
    return saved(root, monkeypatch, tables=False, between=(5.0, 6.0))


async def journey_export_and_reopen(user: User, root: Path, monkeypatch) -> None:
    """Journey 4: a saved result → its Download menu's evidence bundle (the bytes the menu sends) → the bundle page:
    its hashes agree and its saved decision is the stored headline → the server rebuilt → the same study and bundle."""
    from adroit.ui.app import build_pages
    from adroit.ui.exports import files
    folder = _saved_study(root, monkeypatch)
    await user.open("/study?" + urlencode({"path": folder.name}))
    await user.should_see("VIABLE PENDING")
    user.find(marker="downloads")                       # the menu is there
    name, data = files("bundle", folder / "result.json")
    bundle = root.parent / name
    bundle.write_bytes(data)
    build_pages(root)                                   # a restart: the pages built afresh on the same runs folder
    await user.open("/bundle?" + urlencode({"path": str(bundle)}))
    await user.should_see("hashes agree")
    await user.should_see("viable_pending")
    await user.open("/study?" + urlencode({"path": folder.name}))
    await user.should_see("VIABLE PENDING")


@pytest.mark.eos_band
async def test_journey_4_a_saved_result_exported_checked_and_reopened(user: User, tmp_path, monkeypatch):
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    await journey_export_and_reopen(user, root, monkeypatch)


def _toy_signal_study(folder: Path, monkeypatch) -> str:
    """A real Signal best fits study (``signal.run``) on the signal tests' synthetic germanium search, written as a
    study; the label of its leading candidate."""
    from adroit.orchestrator import signal, studies
    from tests.orchestrator.test_signal import ToyGermanium
    monkeypatch.setitem(signal.modules.SIGNAL_SEARCHES, "toy germanium", ToyGermanium)
    candidate = signal.Candidate(label="scalar @ 20", card_id="O1", isospin="s", mass_gev=20)
    result = signal.run(signal.SignalRequest(experiment="toy germanium", candidates=[candidate], null_modules=[],
                                             toys=20, leaders=1, complementary=False))
    folder.mkdir(parents=True)
    (folder / "result.json").write_text(result.model_dump_json())
    studies.record(folder, "signal", "Signal fits: toy germanium")
    return candidate.label


async def journey_promotion(user: User, root: Path, monkeypatch, inline) -> None:  # noqa: F811
    """Journey 2: a Signal best fits study → Promote (its form) → the promotion run → its child, recorded under the
    parent → the parent's page, which lists it → the child's page, its stored headline (its thermal point waits for
    the equation-of-state tables)."""
    from adroit.orchestrator import single_idea
    label = _toy_signal_study(root / "signal", monkeypatch)
    monkeypatch.setattr(relic, "eos_folder", lambda: None)

    def child(request, folder, fetch=None, **claim):                # claim: its writer's hold of the folder (DF-01)
        Path(folder).mkdir(parents=True, exist_ok=True)
        return single_idea.SingleIdeaResult(request=request, level="viable_pending", summary=(
            "a certified thermal intersection fits the anomaly; constraints remain pending (the equation of state's "
            "band is not computed)"), fit_quality="fits", constraint_compatibility="viable",
            thermal_viability="viable_pending")
    monkeypatch.setattr(single_idea, "run", child)
    await user.open("/study?path=signal")
    user.find("candidate or class").elements.pop().value = label
    user.find("background-only simulations per child study").elements.pop().value = 20
    user.find(kind=ui.button, content="Promote").click()
    await user.should_see("Promotion complete", retries=200)
    user.find(marker="primary_action").click()
    await user.should_see("Signal fits: toy germanium")
    await user.should_see("Studies made from this one")   # the parent lists its children
    child = next(e for e in user.find(kind=ui.link).elements if "/children/" in str(e.props.get("href", "")))
    await user.open(child.props["href"])
    await user.should_see("VIABLE PENDING")               # the child's stored headline (the tables missing)
    back = [e for e in user.find(kind=ui.link).elements if e.props.get("href") == "/study?path=signal"]
    assert back, "the child links back to its parent"


async def journey_batch_resume(user: User, root: Path, monkeypatch, inline) -> None:  # noqa: F811
    """Journey 3: a batch of two requests whose runner could not start (interrupted), beside a damaged batch → the
    batches page: the batch interrupted, the damaged one named → Resume (clicked) → the runner (in process) runs
    both → the batches page: completed → a request's run page: its cost (a free request lists none)."""
    import os
    from adroit.ui import batch
    for name in ("first", "second"):
        batch.add_to_draft(root, ["setup"], root / name, f"the {name} request")

    def cannot(*a, **k):
        raise OSError("no process")
    with pytest.raises(OSError):
        batch.start(root, "a batch of two", popen=cannot)
    (root / "batches" / "broken").mkdir(parents=True)
    (root / "batches" / "broken" / batch.BATCH).write_text("{")
    resumed = []
    original = batch.resume
    monkeypatch.setattr(batch, "resume", lambda folder, confirmed=0.0, popen=None: resumed.append(folder) or original(
        folder, confirmed, popen=lambda *a, **k: SimpleNamespace(pid=os.getpid())))
    await user.open("/batches")
    await user.should_see("interrupted")
    await user.should_see("batch record(s) could not be read")
    user.find(kind=ui.button, content="Resume").click()
    await user.should_see("running")
    (folder,) = resumed
    b = batch.load(Path(folder))
    batch.run(Path(folder), b.approval_sha256, generation=b.generation)   # its runner, in process
    await user.open("/batches")
    await user.should_see("completed")
    user.find("the first request").click()                 # each request opens its run, with its cost
    await user.should_see("This run: $0 (no paid request)")


async def test_journey_3_an_interrupted_batch_resumed_from_its_page(user: User, tmp_path, monkeypatch, inline):  # noqa: F811
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    await journey_batch_resume(user, root, monkeypatch, inline)


async def test_journey_2_a_promotion_records_its_child_under_its_parent(user: User, tmp_path, monkeypatch, inline):  # noqa: F811
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    await journey_promotion(user, root, monkeypatch, inline)
