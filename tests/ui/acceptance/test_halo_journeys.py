"""Halo phase 1's headless journeys and their mutation controls: the fixed common SHM benchmark chosen on a form, through
the launched command, the calculation and the saved result, to the study page, the point table, the export and a
continuation, in Track 1 and in Track 2; a family not yet available refused on the form. Each control restores one
defect (the form ignoring the choice, the calculation dropping it, a checkpoint's identity omitting it, an export losing
the qualification, a future family mapped to the SHM) and requires the journey to fail at the invariant it breaks,
after the journey has passed as built (``test_mutation_controls.guards``)."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest
import yaml
from nicegui import ui
from nicegui.testing import User
from typer.testing import CliRunner

from adroit.core import halo_choice
from adroit.parameter_space.classes import Spin1Class
from adroit.parameter_space.scan import PointResult
from tests.ui.acceptance.test_journeys import TYPED, inline  # noqa: F401
from tests.ui.acceptance.test_mutation_controls import UNGUARDED, guards

SUBSTITUTED = {
    "the halo journeys' Track 1 points": "a toy evaluation at each point (Ωh² = 0.12 m_χ/100 GeV; the local density "
                                         "of the halo in force recorded as its value; colliders allowed) in place of "
                                         "the model's relic solver and searches; the halo's dispatch, the benchmark's "
                                         "evaluation, the scan, verdict, certificate, writer, pages and exports are "
                                         "ADROIT's",
    "the halo journeys' scan workers": "threads of the test (the toy reaches every grid point)",
    "the halo journeys' setup check": "its machine items (the external data the real searches read) reported as "
                                      "not used",
    "the halo journeys' Track 2 search": "a toy germanium search and null with real recoil rates, their published halo "
                                         "the older 220/232/544 km/s convention (tests.orchestrator.test_halo_phase1)",
    "the halo journeys' complementary verdicts": "not computed (they read the solar model and the records' data); "
                                                 "the halo they are asked at is recorded and checked",
}
DENSITY = "local density seen (toy)"


def _toy_track1(monkeypatch) -> None:
    """The Track 1 substitutions (``SUBSTITUTED``): the scan's own dispatch on the halo in force runs, the point is the
    toy's."""
    from concurrent.futures import ThreadPoolExecutor
    from adroit.orchestrator import setup_check
    from adroit.parameter_space import halo_limits, scan
    monkeypatch.setattr(setup_check, "machine_items", lambda needs, tools_dir=None: [setup_check.Item(
        section="uses", message=f"{need} (SUBSTITUTED: not used)") for need in needs])
    monkeypatch.setattr(scan, "ProcessPoolExecutor", ThreadPoolExecutor)
    monkeypatch.setattr("adroit.parameter_space.limit_tables.current", lambda *a, **k: [])
    monkeypatch.setattr("adroit.parameter_space.plots.direct_detection", lambda *a, **k: None)
    monkeypatch.setattr(Spin1Class, "omega_h2", lambda self, p: 0.12 * p.m_chi / 100.0)
    monkeypatch.setattr("adroit.parameter_space.searches.prefetch_lhc", lambda c, p, *a: [None] * len(p))

    def evaluate(cls, p, *args, **kwargs):
        state = halo_limits.active()
        return PointResult(point=p, omega_h2=0.12 * p.m_chi / 100.0, dd_kind="SI", dd_sigma_cm2=0, dd_limit_cm2=1,
                           excluded={"toy": False, "colliders (CMS)": False},
                           values={DENSITY: state.rho_gev_cm3 if state is not None else -1.0})
    monkeypatch.setattr(scan, "_evaluate", evaluate)


def _select(user: User, marker: str):
    return user.find(marker=marker).elements.pop()


async def journey_halo_track1(user: User, root: Path, monkeypatch, inline) -> dict:  # noqa: F811
    """Track 1: a typed model → the fixed SHM benchmark chosen beside it (SHM + LMC refused first) → its summary → the scan
    → the study: its halo line, each point at the benchmark (the toy saw its density), the point table's halo column →
    the export's halo column and halo.json, one identity with the result → resume asked with another halo: refused,
    naming the halo."""
    from adroit.evidence import exports
    _toy_track1(monkeypatch)
    seen = {}
    (root / "model.yaml").write_text(TYPED)
    await user.open("/new/track1?model=model.yaml")
    user.find("x axis").elements.pop().value = "m_chi:10:1000:log:3"
    user.find("y axis").elements.pop().value = "g_chi:0.05:0.5:log:2"
    _select(user, "halo-treatment").value = "benchmark"
    _select(user, "halo-family").value = "shm-lmc"
    await user.should_see("Cannot launch: SHM + LMC (shm-lmc) is not implemented yet")
    _select(user, "halo-family").value = "shm"
    await user.should_see("a fixed common benchmark: the SHM at the recommended conventions of arXiv:2105.00599")
    await user.should_see("reviewed")
    user.find(marker="run_model_scan").click()
    await user.should_see("Study complete", retries=200)
    folder = next(f for f in inline if (f / "result.json").exists())
    command = json.loads((folder / "job.json").read_text())["command"]
    assert "--halo" in command and command[command.index("--halo") + 1] == "benchmark", \
        "the launched command carries the benchmark"
    saved = json.loads((folder / "result.json").read_text())
    assert (saved["request"].get("halo") or {}).get("benchmark") == "shm-2105.00599", \
        "the saved request carries the benchmark"
    identity = (saved.get("halo_resolution") or {}).get("identity", "")
    points = saved["scan"]["points"]
    assert all((p.get("halo") or {}).get("treatment") == "benchmark" for p in points), \
        "every point calculated at the benchmark"
    assert {p["values"][DENSITY] for p in points} == {0.3}, "the calculation saw the benchmark's density"
    seen["result"] = identity
    user.find(marker="primary_action").click()
    await user.should_see("Halo: SHM, a fixed common benchmark")
    await user.should_see(f"identity {identity[:12]}")
    files = exports.tables(folder / "result.json")
    rows = list(csv.DictReader(io.StringIO(files["points.csv"].decode())))
    assert rows and all(r["halo"].startswith("at the fixed benchmark halo") for r in rows), \
        "the export names each point's halo"
    assert json.loads(files["halo.json"])["resolution"]["identity"] == identity, "the export's halo is the result's"
    seen["export"] = "halo column and halo.json"
    other = [*command, "--resume"]
    other[other.index("--halo") + 1] = "published"
    refused = CliRunner().invoke(__import__("adroit.orchestrator.cli", fromlist=["app"]).app, other)
    assert refused.exit_code != 0 and "the halo differs" in refused.output, \
        "a resume with another halo is refused, naming the halo"
    seen["resume"] = "refused"
    return seen


async def journey_halo_track2(user: User, root: Path, monkeypatch, inline) -> dict:  # noqa: F811
    """Track 2: a toy search and null whose published halo is not the benchmark → the fixed SHM benchmark chosen →
    the run: the fit, the null limit and the verdicts' halo the benchmark → the study page's halo line → a reanalysis
    as Constrain a model, drafted with the same benchmark."""
    from adroit.experiments import registry
    from adroit.orchestrator import signal
    from adroit.orchestrator.reanalysis import Reanalysis
    from tests.orchestrator.test_halo_phase1 import OlderNull, OlderToy
    monkeypatch.setitem(registry.SIGNAL_SEARCHES, "older toy", OlderToy)
    monkeypatch.setitem(registry.MODULES, "older null", OlderNull)
    asked = []

    def judged(candidate, include_unverified=False, halo=None, certificates=None):
        asked.append(halo)
        return [], {}
    monkeypatch.setattr(signal.complementary, "judged", judged)
    seen = {}
    await user.open("/new/track2")
    experiment = next(e for e in user.find(kind=ui.select).elements if "older toy" in (e.options or []))
    experiment.value = "older toy"
    nulls = next(e for e in user.find(kind=ui.select).elements if e.props.get("multiple") and "older null" in
                 (e.options or []))
    nulls.value = ["older null"]
    model = next(e for e in user.find(kind=ui.textarea).elements
                 if str(e.props.get("placeholder", "")).startswith("a typed model with its couplings"))
    model.value = TYPED
    user.find("their masses (GeV)").elements.pop().value = "20"
    user.find("the library's space as well").elements.pop().value = False
    user.find("background-only simulations").elements.pop().value = 1000
    user.find("Check fitted points as physical models").elements.pop().value = False
    _select(user, "halo-treatment").value = "benchmark"
    await user.should_see("a fixed common benchmark")
    user.find("Fit, combine and rank").click()
    await user.should_see("Study complete", retries=200)
    folder = next(f for f in inline if (f / "result.json").exists())
    saved = json.loads((folder / "result.json").read_text())
    assert (saved["request"].get("halo") or {}).get("benchmark") == "shm-2105.00599", \
        "the saved request carries the benchmark"
    assert asked and all(h == halo_choice.fixed().halo for h in asked), "the verdicts were asked at the benchmark"
    assert saved["halo_resolution"]["treatment"] == "benchmark", "the result records the benchmark"
    seen["result"] = saved["halo_resolution"]["identity"]
    user.find(marker="primary_action").click()
    await user.should_see("Halo: SHM, a fixed common benchmark")
    from adroit.library.personal import Catalog
    draft = Reanalysis(Catalog(root / ".models")).open(str(folder), target="track1")
    assert (draft.request.get("halo") or {}).get("benchmark") == "shm-2105.00599", \
        "a reanalysis as Track 1 keeps the benchmark"
    seen["reanalysis"] = "benchmark kept"
    return seen


async def test_the_benchmark_through_track1(user: User, tmp_path, monkeypatch, inline):  # noqa: F811
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    seen = await journey_halo_track1(user, root, monkeypatch, inline)
    assert seen["resume"] == "refused" and len(seen["result"]) == 64


async def test_the_benchmark_through_track2(user: User, tmp_path, monkeypatch, inline):  # noqa: F811
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    seen = await journey_halo_track2(user, root, monkeypatch, inline)
    assert seen["reanalysis"] == "benchmark kept"


# --- the controls -------------------------------------------------------------------------------------------------


def _fresh(user, tmp_path, monkeypatch, inline, journey):  # noqa: F811
    """A fresh run of the journey in its own folder (each of a control's runs)."""
    from adroit.ui.app import build_pages
    count = [0]

    async def run():
        count[0] += 1
        root = build_pages(tmp_path / f"runs{count[0]}")
        inline.clear()
        return await journey(user, root, monkeypatch, inline)
    return run


async def control_form_ignores_choice(user, tmp_path, monkeypatch, inline, defect: bool = True):  # noqa: F811
    """The form launches without the halo it shows. Invariant: the launched command carries the benchmark."""
    from adroit.ui import forms
    return await guards(_fresh(user, tmp_path, monkeypatch, inline, journey_halo_track1),
                        lambda: defect and monkeypatch.setattr(forms, "halo_flags", lambda *a, **k: []),
                        "the launched command carries the benchmark")


async def control_calculation_drops_it(user, tmp_path, monkeypatch, inline, defect: bool = True):  # noqa: F811
    """The run keeps the request but calculates with the published halos. Invariant: every point at the benchmark."""
    from adroit.parameter_space import halo_region
    original = halo_region.of
    return await guards(_fresh(user, tmp_path, monkeypatch, inline, journey_halo_track1),
                        lambda: defect and monkeypatch.setattr(halo_region, "of", lambda v: None if isinstance(
                            v, halo_choice.FixedHalo) else original(v)),
                        "every point calculated at the benchmark")


async def control_checkpoint_omits_halo(user, tmp_path, monkeypatch, inline, defect: bool = True):  # noqa: F811
    """A checkpoint's identity leaves the halo out, so a resume with another halo is taken. Invariant: such a resume is
    refused, naming the halo."""
    from adroit.core import checkpoint
    original = checkpoint.Checkpoint.__init__

    def init(self, folder, inputs, dependencies, resume=False, context=None):
        original(self, folder, {k: v for k, v in inputs.items() if k != "halo"}, dependencies, resume, context)
    return await guards(_fresh(user, tmp_path, monkeypatch, inline, journey_halo_track1),
                        lambda: defect and monkeypatch.setattr(checkpoint.Checkpoint, "__init__", init),
                        "a resume with another halo is refused")


async def control_export_loses_qualification(user, tmp_path, monkeypatch, inline, defect: bool = True):  # noqa: F811
    """The export drops each point's halo. Invariant: the export names each point's halo."""
    from adroit.evidence import halo
    return await guards(_fresh(user, tmp_path, monkeypatch, inline, journey_halo_track1),
                        lambda: defect and monkeypatch.setattr(halo, "point_label", lambda *a: ""),
                        "the export names each point's halo")


async def control_future_family_as_shm(user, tmp_path, monkeypatch, inline, defect: bool = True):  # noqa: F811
    """A family not yet implemented is taken as the SHM. Invariant: the form refuses SHM + LMC ("Cannot launch")."""
    return await guards(_fresh(user, tmp_path, monkeypatch, inline, journey_halo_track1),
                        lambda: defect and monkeypatch.setattr(halo_choice, "available",
                                                               lambda family_id: halo_choice.FAMILIES["shm"]),
                        "Cannot launch: SHM + LMC")


CONTROLS = {"form_ignores_choice": control_form_ignores_choice, "calculation_drops_it": control_calculation_drops_it,
            "checkpoint_omits_halo": control_checkpoint_omits_halo,
            "export_loses_qualification": control_export_loses_qualification,
            "future_family_as_shm": control_future_family_as_shm}


@pytest.mark.parametrize("control", list(CONTROLS))
async def test_each_halo_control_detects_its_defect(user: User, tmp_path, monkeypatch, inline, control):  # noqa: F811
    assert await CONTROLS[control](user, tmp_path, monkeypatch, inline)


@pytest.mark.parametrize("control", list(CONTROLS))
async def test_each_halo_control_fails_without_its_defect(user: User, tmp_path, monkeypatch, inline,  # noqa: F811
                                                          control):
    with pytest.raises(AssertionError, match=UNGUARDED):
        await CONTROLS[control](user, tmp_path, monkeypatch, inline, defect=False)


def test_the_journeys_name_their_substitutions():
    assert all(how for how in SUBSTITUTED.values()) and yaml.safe_load(TYPED)["name"]
