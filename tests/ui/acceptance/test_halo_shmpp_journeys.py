"""Halo phase 2's headless journeys and their mutation controls: SHM++ chosen on a form, its fixed benchmark and its
applicability shown before launch, through the launched command, the calculation (its tables, the Sun's for capture)
and the saved result, to the study page, the point table, the export, a stale copy and the continuations; in Track 1 and
in Track 2; and what SHM++ cannot do refused with its reason. Each control restores one defect and requires the journey
to fail at the invariant it breaks, after the journey has passed as built (``test_mutation_controls.guards``):

- SHM substituted for SHM++ (the calculation at the SHM with SHM++'s numbers);
- the Sausage's anisotropy dropped (the generator's dispersions made isotropic);
- the detector's and the Sun's distributions interchanged (each table generated with the other's boost);
- a cache keyed without the mixture (the limit cache by the table's SHM fields, not its values);
- a continuation reset to the SHM (a reanalysis drafted with the SHM benchmark);
- a pending comparison labelled allowed (a comparison SHM++ cannot calculate taken as calculated).
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
from pathlib import Path

import numpy as np
import pytest
from nicegui import ui
from nicegui.testing import User
from typer.testing import CliRunner

from adroit.core import halo_choice
from adroit.halo_models import shm_plus_plus as shmpp
from adroit.parameter_space import halo_limits
from adroit.parameter_space.scan import PointResult
from tests.ui.acceptance.test_halo_journeys import DENSITY, _fresh, _select, _toy_track1
from tests.ui.acceptance.test_journeys import TYPED, inline  # noqa: F401
from tests.ui.acceptance.test_mutation_controls import UNGUARDED, guards

# SHM++'s snapshot as this checkout's generator makes it, taken when this module is imported: before any control
# restores a defect, so that a defect cannot also change the reference it is judged against
REFERENCE = halo_choice.fixed("shm-plus-plus")
TABLE_SEEN = "SHM++ detector table seen (toy)"        # 1: the point was calculated with SHM++'s own detector table
SUN_SEEN = "SHM++ Sun table seen for capture (toy)"    # 1: capture would take SHM++'s own Sun-frame table
UNSUPPORTED = "not calculated with SHM++: fixed benchmark"

SUBSTITUTED = {
    "the SHM++ journeys' Track 1 points": "a toy evaluation at each point (Ωh² = 0.12 m_χ/100 GeV; a direct-detection "
                                         "ratio given through Path 1, so not calculable at a benchmark; the halo in "
                                         "force recorded: its density, whether its detector table and the table "
                                         "capture would take are SHM++'s own) in place of the model's relic solver "
                                         "and searches; the halo's dispatch, the benchmark's evaluation, the scan, "
                                         "verdict, certificates, writer, pages and exports are ADROIT's",
    "the SHM++ journeys' limit cache": "two real limits of CRESST-III at 3 GeV (its own procedure, in process), one "
                                       "with SHM++ and one with SHM++ at η = 0.3, as a sensitivity study would compute "
                                       "them in one process",
    "the SHM++ journeys' Track 2 search": "a toy germanium search and null with real recoil rates (tests.orchestrator."
                                          "test_halo_phase1), their published halo the older 220/232/544 km/s "
                                          "convention",
    "the SHM++ journeys' complementary verdicts": "not computed (they read the solar model and the records' data); the "
                                                  "halo they are asked at is recorded and checked",
    "the SHM++ journeys' stale copy": "a copy of the Track 1 study whose certificates name another sha256 for the local "
                                      "densities file, as if the file had changed since they were certified",
}


def _fresh_caches() -> None:
    """A fresh process's caches: every table generated, verified and limited again (each run of a journey)."""
    halo_choice._generated.cache_clear()
    halo_choice._VERIFIED.clear()
    halo_limits.exact_at_table.cache_clear()
    halo_limits.blind_at_table.cache_clear()
    halo_limits._TABLES.clear()


def _same(table, reference) -> bool:
    return table is not None and table.speeds_km_s == reference.speeds_km_s and \
        table.speed_density == reference.speed_density


def _toy_shmpp(monkeypatch) -> None:
    """``SUBSTITUTED``'s Track 1 points: the scan's own dispatch on the halo in force runs, the point is the toy's."""
    from adroit.parameter_space import scan
    _toy_track1(monkeypatch)
    monkeypatch.setattr(scan, "dd_channels_of", lambda *a: [])      # its comparison is Path 1's (no channel)

    def evaluate(cls, p, *args, **kwargs):
        state = halo_limits.active()
        return PointResult(point=p, omega_h2=0.12 * p.m_chi / 100.0, dd_kind="SI", dd_sigma_cm2=0, dd_limit_cm2=1,
                           dd_ratio=0.5, excluded={"direct detection": False, "colliders (CMS)": False},
                           ratios={"direct detection": 0.5}, ratio_confidence_levels={"direct detection": 0.95},
                           values={DENSITY: state.rho_gev_cm3 if state is not None else -1.0,
                                   TABLE_SEEN: float(state is not None and _same(state.table, REFERENCE.halo)),
                                   SUN_SEEN: float(_same(halo_limits.capture_halo(), REFERENCE.sun))})
    monkeypatch.setattr(scan, "_evaluate", evaluate)


def _cresst_at(fixed) -> float:
    state = halo_limits.at_tables(fixed, halo_limits.Budget(0))
    value, _, how = halo_limits.module_limit(state, "CRESST-III 2019", "SI", 3.0, False)
    assert value is not None, f"CRESST-III's limit with SHM++: {how}"
    return value


async def journey_shmpp_track1(user: User, root: Path, monkeypatch, inline) -> dict:  # noqa: F811
    """Track 1: a typed model → SHM++ chosen beside it (its treatment the fixed benchmark only), its benchmark and
    applicability shown → the scan → the saved snapshot (SHM++'s own tables, not interchanged) → every point with SHM++'s
    tables (capture with the Sun's), and what it cannot calculate pending, named → the study's halo line → the export →
    a stale copy shown stale → a resume at the SHM benchmark refused → a reanalysis as Signal best fits keeps SHM++ →
    two SHM++ mixtures in one process keep their own limits."""
    from adroit.evidence import exports
    from adroit.library.personal import Catalog
    from adroit.orchestrator.reanalysis import Reanalysis
    _fresh_caches()
    _toy_shmpp(monkeypatch)
    seen = {}
    (root / "model.yaml").write_text(TYPED)
    await user.open("/new/track1?model=model.yaml")
    user.find("x axis").elements.pop().value = "m_chi:10:1000:log:3"
    user.find("y axis").elements.pop().value = "g_chi:0.05:0.5:log:2"
    family, treatment = _select(user, "halo-family"), _select(user, "halo-treatment")
    family.value = "shm-plus-plus"
    assert treatment.value == "benchmark" and list(treatment.options) == ["benchmark"], \
        "SHM++ is a fixed benchmark only"
    await user.should_see("SHM++, fixed benchmark; halo uncertainty not propagated")
    details = _select(user, "halo-details-text").content
    assert "β = 0.9 and share η = 0.2" in details and "no accepted-count ratio" in details and \
        "no annual modulation" in details, "the benchmark's numbers and applicability are shown before launch"
    await user.should_see("reviewed")
    user.find(marker="run_model_scan").click()
    await user.should_see("Study complete", retries=200)
    folder = next(f for f in inline if (f / "result.json").exists())
    command = json.loads((folder / "job.json").read_text())["command"]
    assert command[command.index("--halo") + 1] == "benchmark" and \
        command[command.index("--halo-family") + 1] == "shm-plus-plus", "the launched command carries SHM++"
    saved = json.loads((folder / "result.json").read_text())
    halo = halo_choice.FixedHalo.model_validate(saved["request"]["halo"])
    assert (halo.family, halo.benchmark) == ("shm-plus-plus", "shmpp-1810.11468"), "the saved request carries SHM++"
    assert halo.halo.speed_density != REFERENCE.sun.speed_density, \
        "the detector's and the Sun's tables are not interchanged"
    assert _same(halo.halo, REFERENCE.halo) and _same(halo.sun, REFERENCE.sun), \
        "the saved tables are SHM++'s generator's output, its Sausage anisotropic"
    points = saved["scan"]["points"]
    assert all((p.get("halo") or {}).get("treatment") == "benchmark" for p in points), \
        "every point calculated at the benchmark"
    assert {p["values"][DENSITY] for p in points} == {0.55} and all(p["values"][TABLE_SEEN] == 1.0 for p in points), \
        "every point calculated with SHM++'s own tables"
    assert all(p["values"][SUN_SEEN] == 1.0 for p in points), "capture takes SHM++'s Sun-frame table"
    crossings = saved["verdict"]["crossings"]
    assert crossings and all(c["status"] == "pending" and any(UNSUPPORTED in x for x in c["pending"])
                             for c in crossings), "the comparison SHM++ cannot calculate is pending, named"
    identity = saved["halo_resolution"]["identity"]
    seen["result"] = identity
    user.find(marker="primary_action").click()
    await user.should_see("Halo: SHM++, fixed benchmark; halo uncertainty not propagated")
    await user.should_see(f"identity {identity[:12]}")
    files = exports.tables(folder / "result.json")
    rows = list(csv.DictReader(io.StringIO(files["points.csv"].decode())))
    assert rows and all(r["halo"].startswith("at the fixed benchmark halo (SHM++") for r in rows), \
        "the export names each point's halo"
    exported = json.loads(files["halo.json"])["resolution"]
    assert exported["identity"] == identity and exported["tables"] == REFERENCE.tables, "the export's halo is the result's"
    seen["stale"] = await _stale_copy(user, root, folder)
    other = [*command, "--resume"]
    del other[other.index("--halo-family"):other.index("--halo-family") + 2]           # the SHM's benchmark
    refused = CliRunner().invoke(__import__("adroit.orchestrator.cli", fromlist=["app"]).app, other)
    assert refused.exit_code != 0 and "the halo differs" in refused.output, \
        "a resume at the SHM benchmark is refused, naming the halo"
    draft = Reanalysis(Catalog(root / ".models")).open(str(folder), target="signal")
    kept = draft.request.get("halo") or {}
    assert kept.get("benchmark") == "shmpp-1810.11468" and kept.get("tables") == REFERENCE.tables, \
        "a reanalysis keeps SHM++, its tables unchanged"
    variant = halo_choice._generated(REFERENCE.parameters.model_copy(update={"eta": 0.3}), REFERENCE.numerics, "SHM++")
    other_mixture = REFERENCE.model_copy(update={"halo": variant[0], "sun": variant[1]})
    assert _cresst_at(REFERENCE) != _cresst_at(other_mixture), "two SHM++ mixtures take their own limits"
    seen["continuations"] = "kept"
    return seen


async def _stale_copy(user: User, root: Path, folder: Path) -> str:
    """A copy of the study whose certificates were certified on another local-densities file: shown stale, naming it."""
    import shutil
    from adroit.orchestrator import studies
    copy = root / "stale_shmpp"
    shutil.copytree(folder, copy, ignore=shutil.ignore_patterns("study.json", "children"))
    text = (copy / "result.json").read_text()
    data = json.loads(text)
    old = data["halo_resolution"]["data"]["local densities"]
    assert old and text.count(old) > 1, "the study's claims are certified on the local densities file"
    (copy / "result.json").write_text(text.replace(old, "0" * 64))
    studies.record(copy, "track1", "an SHM++ study certified on an earlier local densities file")
    await user.open("/study?path=stale_shmpp")
    await user.should_see("the halo data file (local densities) changed since it was certified")
    return "stale, naming the local densities file"


async def journey_shmpp_track2(user: User, root: Path, monkeypatch, inline) -> dict:  # noqa: F811
    """Track 2: a toy search and null whose published halo is not SHM++ → SHM++ chosen → the run: the fit and the null
    limit with its detector table, the verdicts asked with its Sun table, its halo flags generated within SHM++ → the
    study's halo line → a reanalysis as Constrain a model and a promotion keep SHM++."""
    from adroit.experiments import registry
    from adroit.library.personal import Catalog
    from adroit.orchestrator import promote, signal, single_idea
    from adroit.orchestrator.reanalysis import Reanalysis
    from adroit.parameter_space import simplified
    from tests.orchestrator.test_halo_phase1 import OlderNull, OlderToy
    _fresh_caches()
    monkeypatch.setitem(registry.SIGNAL_SEARCHES, "older toy", OlderToy)
    monkeypatch.setitem(registry.MODULES, "older null", OlderNull)
    asked, fitted = [], []
    monkeypatch.setattr(signal.complementary, "judged", lambda candidate, include_unverified=False, halo=None,
                        certificates=None: asked.append(halo) or ([], {}))
    expected = OlderToy.expected_signal
    monkeypatch.setattr(OlderToy, "expected_signal", lambda self, particle, interaction, halo, model, target=None:
                        fitted.append(halo) or expected(self, particle, interaction, halo, model, target))
    seen = {}
    await user.open("/new/track2")
    next(e for e in user.find(kind=ui.select).elements if "older toy" in (e.options or [])).value = "older toy"
    next(e for e in user.find(kind=ui.select).elements
         if e.props.get("multiple") and "older null" in (e.options or [])).value = ["older null"]
    next(e for e in user.find(kind=ui.textarea).elements
         if str(e.props.get("placeholder", "")).startswith("a typed model with its couplings")).value = TYPED
    user.find("their masses (GeV)").elements.pop().value = "20"
    user.find("the library's space as well").elements.pop().value = False
    user.find("background-only simulations").elements.pop().value = 1000
    user.find("Check fitted points as physical models").elements.pop().value = False
    _select(user, "halo-family").value = "shm-plus-plus"
    await user.should_see("SHM++, fixed benchmark; halo uncertainty not propagated")
    user.find("Fit, combine and rank").click()
    await user.should_see("Study complete", retries=200)
    folder = next(f for f in inline if (f / "result.json").exists())
    saved = json.loads((folder / "result.json").read_text())
    assert (saved["request"].get("halo") or {}).get("benchmark") == "shmpp-1810.11468", \
        "the saved request carries SHM++"
    assert fitted and _same(fitted[0], REFERENCE.halo), "the fit used SHM++'s detector table"
    assert asked and all(_same(h, REFERENCE.sun) for h in asked), "the verdicts were asked with SHM++'s Sun table"
    assert saved["halo_resolution"]["tables"] == REFERENCE.tables, "the result records SHM++'s tables"
    flags = [f for row in saved["tournament"]["ranking"] for f in row["flags"] if f.startswith("halo")]
    assert all("SHM++ generated again from the fixed benchmark" in f for f in flags), \
        "a halo flag is a labelled SHM++ sensitivity check"
    user.find(marker="primary_action").click()
    await user.should_see("Halo: SHM++, fixed benchmark; halo uncertainty not propagated")
    draft = Reanalysis(Catalog(root / ".models")).open(str(folder), target="track1")
    assert (draft.request.get("halo") or {}).get("tables") == REFERENCE.tables, "a reanalysis keeps SHM++"
    children = []
    monkeypatch.setattr(single_idea, "prepared", lambda request: children.append(request.halo) or
                        (_ for _ in ()).throw(RuntimeError("stopped")))
    result = signal.SignalResult.model_validate(saved)
    with pytest.raises(RuntimeError, match="stopped"):
        promote._study(root / "child", result, signal.Candidate(label="O1s@20", card_id="O1", isospin="s",
                                                                 mass_gev=20.0), "simplified completion",
                       simplified.model("vector", 20, 1000), {"toys": 10, "grid": 4, "masses": 2})
    assert children and _same(children[0].halo, REFERENCE.halo) and _same(children[0].sun, REFERENCE.sun), \
        "a promotion keeps SHM++"
    seen["continuations"] = "kept"
    return seen


@pytest.mark.needs("cresst")           # CRESST-III's real limits with SHM++ (the journey's limit cache)
async def test_shmpp_through_track1(user: User, tmp_path, monkeypatch, inline):  # noqa: F811
    from adroit.ui.app import build_pages
    seen = await journey_shmpp_track1(user, build_pages(tmp_path / "runs"), monkeypatch, inline)
    assert seen["continuations"] == "kept" and seen["stale"].startswith("stale") and len(seen["result"]) == 64


async def test_shmpp_through_track2(user: User, tmp_path, monkeypatch, inline):  # noqa: F811
    from adroit.ui.app import build_pages
    seen = await journey_shmpp_track2(user, build_pages(tmp_path / "runs"), monkeypatch, inline)
    assert seen["continuations"] == "kept"


def test_what_shmpp_cannot_do_is_refused_before_anything_is_calculated(tmp_path):
    """An unsupported comparison (the native joint fit) and a missing required input (a draft whose Sun-frame table was
    removed) are refused, each naming why; nothing is calculated."""
    from adroit.orchestrator import cli
    (tmp_path / "model.yaml").write_text(TYPED)
    refused = CliRunner().invoke(cli.app, ["single-idea", str(tmp_path / "model.yaml"), "--experiment",
                                           "CDMS II Si (2013)", "--out", str(tmp_path / "out"), "--halo", "benchmark",
                                           "--halo-family", "shm-plus-plus", "--native-joint", "DEAP-3600 (2019)"])
    flat = re.sub(r"[│╭╮╰╯─\s]+", " ", refused.output)          # the command line's error box, its lines joined
    assert refused.exit_code != 0 and "native joint signal/null likelihood: not calculated with SHM++" in flat
    assert not (tmp_path / "out" / "result.json").exists()
    missing = REFERENCE.model_copy(update={"sun": None})
    from adroit.parameter_space import halo_region
    with pytest.raises(ValueError, match="without its Sun-frame table: refused.*nothing is calculated"):
        halo_region.checked(missing)                     # made without validation: refused before any calculation
    from adroit.orchestrator.signal import SignalRequest
    with pytest.raises(ValueError, match="without its Sun-frame table: refused"):    # read: refused as it is read
        SignalRequest.model_validate({"experiment": "CDMS II Si (2013)", "halo": REFERENCE.model_dump(
            mode="json", exclude={"sun"})})


# --- the controls -------------------------------------------------------------------------------------------------


def _isotropic(m) -> None:
    """The defect: the Sausage's dispersions and normalisation the round halo's."""
    m.setattr(shmpp, "dispersions", lambda p: (p.v0_km_s / math.sqrt(2.0), p.v0_km_s / math.sqrt(2.0)))
    m.setattr(shmpp, "n_sausage", shmpp.n_round)


def _swapped(self, frame):
    return self.v_sun() if frame == "detector" else self.v_detector()


def _keyed_without_mixture(table):
    """The defect: the limit cache keyed by the table's SHM fields (v₀, v_esc, the boosts), not by its values."""
    import hashlib
    from adroit.halo_models.frames import frame_of
    if table.kind.value != "tabulated" or frame_of(table) != "detector":
        raise ValueError("direct detection takes a table in the detector's frame")
    key = hashlib.sha256(json.dumps(table.model_dump(mode="json", exclude={"label", "speeds_km_s", "speed_density",
                                                                           "rho_gev_cm3"})).encode()).hexdigest()
    halo_limits._TABLES.setdefault(key, table.model_copy(update={"rho_gev_cm3": halo_limits.RHO_REF}))
    return key


def _reset_to_shm(kind, request, target):
    """The defect: a continuation drafted with the SHM's benchmark in place of the study's."""
    found = ORIGINAL_CONVERTED(kind, request, target)
    if isinstance(found.get("halo"), dict) and found["halo"].get("treatment") == "benchmark":
        found = {**found, "halo": halo_choice.fixed().model_dump(mode="json")}
    return found


def _labelled_allowed(m) -> None:
    """The defect: a point's comparison that SHM++ cannot calculate kept as calculated (allowed), its reason dropped."""
    from adroit.parameter_space import halo_evaluation
    original = halo_evaluation.at_benchmark

    def at_benchmark(cls, p, fixed, nominal):
        r = original(cls, p, fixed, nominal)
        return r.model_copy(update={"pending": [x for x in r.pending if UNSUPPORTED not in x],
                                    "excluded": {**r.excluded, "direct detection": False}})
    m.setattr(halo_evaluation, "at_benchmark", at_benchmark)


def _shm_state(fixed, budget):
    return halo_limits.State(v0_km_s=fixed.parameters.v0_km_s, v_esc_km_s=fixed.parameters.v_esc_km_s,
                             rho_gev_cm3=fixed.parameters.rho_gev_cm3, budget=budget, benchmark=True)


ORIGINAL_CONVERTED = __import__("adroit.orchestrator.reanalysis", fromlist=["_converted_halo"])._converted_halo


def _control(defect_of, invariant: str):
    async def control(user, tmp_path, monkeypatch, inline, defect: bool = True):  # noqa: F811
        return await guards(_fresh(user, tmp_path, monkeypatch, inline, journey_shmpp_track1),
                            lambda: defect and defect_of(monkeypatch), invariant)
    return control


CONTROLS = {
    "shm_for_shmpp": _control(lambda m: m.setattr(halo_limits, "at_tables", _shm_state),
                              "every point calculated with SHM++'s own tables"),
    "anisotropy_dropped": _control(_isotropic,
                                   "the saved tables are SHM++'s generator's output, its Sausage anisotropic"),
    "frames_interchanged": _control(lambda m: m.setattr(shmpp.Parameters, "boost", _swapped),
                                    "the detector's and the Sun's tables are not interchanged"),
    "cache_without_mixture": _control(lambda m: m.setattr(halo_limits, "tabulated", _keyed_without_mixture),
                                      "two SHM++ mixtures take their own limits"),
    "continuation_reset_to_shm": _control(lambda m: m.setattr("adroit.orchestrator.reanalysis._converted_halo",
                                                              _reset_to_shm),
                                          "a reanalysis keeps SHM++"),
    "pending_labelled_allowed": _control(_labelled_allowed, "the comparison SHM++ cannot calculate is pending, named"),
}


@pytest.mark.needs("cresst")
@pytest.mark.parametrize("control", list(CONTROLS))
async def test_each_shmpp_control_detects_its_defect(user: User, tmp_path, monkeypatch, inline, control):  # noqa: F811
    assert await CONTROLS[control](user, tmp_path, monkeypatch, inline)


@pytest.mark.needs("cresst")
@pytest.mark.parametrize("control", list(CONTROLS))
async def test_each_shmpp_control_fails_without_its_defect(user: User, tmp_path, monkeypatch, inline,  # noqa: F811
                                                           control):
    with pytest.raises(AssertionError, match=UNGUARDED):
        await CONTROLS[control](user, tmp_path, monkeypatch, inline, defect=False)


def test_the_journeys_name_their_substitutions():
    assert all(how for how in SUBSTITUTED.values()) and np.isfinite(REFERENCE.parameters.beta)
