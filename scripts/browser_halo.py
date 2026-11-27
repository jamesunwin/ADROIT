"""Halo phases 1 and 2's release browser journeys (``scripts/browser_acceptance.py`` runs them): the halo chosen beside
the model in the installed Chrome, through the ordinary launcher, a real calculation in a child process at small scale,
the study page and its point table, a server restart, the export, an incompatible resume and a continuation; and a
comparison the fixed benchmark cannot calculate, refused with its reason. Phase 2's (``shmpp_*``) do the same with SHM++
in each track, compare each run with the same request made on the command line, and add a missing input and a stale
copy. What a journey substitutes is in ``SUBSTITUTED``; its mutation controls are ``CONTROLS``
(``scripts/netguard/acceptance_mutations.py``)."""
from __future__ import annotations

import csv
import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from browser_harness import Workbench, wait_finished  # noqa: E402

MODEL = "halo_model.yaml"
SUBSTITUTED = {
    "the halo journeys' calculations": "none substituted: each run computes its own points (Track 1: a typed vector "
                                       "model on a 3 × 2 plane at the fixed SHM benchmark, and on a 2 × 2 plane over "
                                       "the SHM region by default; Track 2: CDMS II Si (2013) "
                                       "with the same model at 10 GeV, 1,000 toys, the four default null searches "
                                       "by the direct route at the benchmark); the scan's checkpoint, the export and "
                                       "the refused resume are the command line's own",
    "the halo journeys' calculation cache": "the checkout's own (data/calculation-cache, with data/external), shared "
                                            "as journey 2's is",
}
HALO = ("halo_track1", "halo_track2", "halo_unavailable", "halo_default")
SHMPP = ("shmpp_track1", "shmpp_track2")
SUBSTITUTED.update({
    "the SHM++ journeys' calculations": "none substituted: each run computes its own points with SHM++'s tables "
                                        "(Track 1: the typed vector model on a 2 × 2 plane, 2–8 GeV, where CRESST-III "
                                        "and CDMSlite decide, the slow one by its own procedure within the point's "
                                        "budget; Track 2: CDMS II Si (2013) with the same model at 10 GeV, 1,000 toys, "
                                        "the four default null searches by the direct route at SHM++); each is "
                                        "compared with the same request made on the command line",
    "the SHM++ journeys' stale copy": "a copy of the Track 1 study whose certificates name another sha256 for the "
                                      "local densities file, as if the file had changed since they were certified",
})
DESCRIBES = {"the halo journeys' calculations": HALO, "the halo journeys' calculation cache": HALO + SHMPP,
             "the SHM++ journeys' calculations": SHMPP, "the SHM++ journeys' stale copy": ("shmpp_track1",)}
IDENTITY = re.compile(r"identity ([0-9a-f]{12})")


def _model_text() -> str:
    import yaml
    from adroit.parameter_space import simplified
    return yaml.safe_dump(simplified.model("vector", 10, 125, .001, .25).model_dump(mode="json"))


def _launched(page, bench: Workbench, kind: str) -> tuple[Path, list[str]]:
    """The run the page launched: its folder (from the live page's address) and its command as the launcher recorded
    it (``job.json``)."""
    from urllib.parse import parse_qs, urlparse
    path = page.wait(lambda: (parse_qs(urlparse(page.url()).query).get("path") or [""])[0], "the run's folder")
    folder = bench.root / "runs" / path
    command = page.wait(lambda: json.loads((folder / "job.json").read_text())["command"]
                        if (folder / "job.json").exists() else None, "the run's job record")
    assert command[0] == kind, command
    return folder, command


def _cli(bench: Workbench, *words: str) -> subprocess.CompletedProcess:
    """The command line as a child of the workbench's environment."""
    return subprocess.run([sys.executable, "-m", "adroit.orchestrator.cli", *words], cwd=ROOT, env=bench.env,
                          capture_output=True, text=True, timeout=900)


FAMILY_SELECT = """() => { const f = [...document.querySelectorAll('.q-select')].find(s => s.offsetParent !== null &&
    s.querySelector('.q-field__label') && s.querySelector('.q-field__label').innerText.trim() === 'halo family');
    return f ? f.querySelector('.q-field__control') : null; }"""
OPTIONS = """(() => { const items = [...document.querySelectorAll('.q-menu .q-item')].filter(i => i.offsetParent !== null
        && i.innerText.trim());
    return items.length >= 3 ? Object.fromEntries(items.map(i => [i.innerText.trim().split(' (')[0],
        i.classList.contains('disabled') || i.classList.contains('q-item--disabled')
        || i.getAttribute('aria-disabled') === 'true'])) : null; })()"""
MENU = "[...document.querySelectorAll('.q-menu')].map(m => m.outerHTML.slice(0, 1500)).join('\\n')"


def _families_listed(page) -> dict:
    """The halo family select's options as the page lists them (label → disabled), the select then closed."""
    page._click_found(FAMILY_SELECT, "the select labelled 'halo family'")
    try:
        found = page.wait(lambda: page.evaluate(OPTIONS), "the halo family's options", timeout=20)
    except TimeoutError as error:
        raise AssertionError(f"SHM++ beside the SHM, and SHM + LMC listed, disabled: no menu of three options "
                             f"({page.evaluate(MENU)})") from error
    page._click_found(FAMILY_SELECT, "the select labelled 'halo family', to close it")
    page.wait(lambda: not page.evaluate(OPTIONS), "the halo family's options closed", timeout=10)
    return found


def _choose_in_place(page, label: str, option: str) -> None:
    """Choose ``option`` in the select labelled ``label``, clicking the option where the menu shows it, never scrolling
    to it: a select at the foot of a long page opens its menu above itself, and scrolling the page closes the menu
    (``browser.Page.choose`` scrolls each option into view first)."""
    finder = f"""() => {{ const f = [...document.querySelectorAll('.q-select')].find(s => s.offsetParent !== null &&
        s.querySelector('.q-field__label') && s.querySelector('.q-field__label').innerText.trim() === {json.dumps(label)});
        return f ? f.querySelector('.q-field__control') : null; }}"""
    where = f"""(() => {{ const i = [...document.querySelectorAll('.q-menu .q-item')].find(e => e.offsetParent !== null
        && e.innerText.trim() === {json.dumps(option)}); if (!i) return null; const r = i.getBoundingClientRect();
        return r.height > 0 ? [r.left + r.width / 2, r.top + r.height / 2] : null; }})()"""
    for attempt in range(3):
        time.sleep(1.0)              # a section just unfolded is still moving: a click during its transition misses
        page._click_found(finder, f"the select labelled {label!r}")
        try:
            x, y = page.wait(lambda: page.evaluate(where), f"the option {option!r} of {label!r}", timeout=10)
            page.mouse_click(x, y)
            page.wait(lambda: page.value_of(label) == option, f"the select {label!r} to show {option!r}", timeout=10)
            return
        except TimeoutError:
            if attempt == 2:
                raise


def _drafted(page) -> None:
    """The reanalysis page reopens the study's inputs; its draft (the editable request) keeps the benchmark."""
    page.click_text("Reopen saved inputs")
    page.wait(lambda: "shm-2105.00599" in page.value_of("Prepopulated numerical/scientific request (YAML)"),
              "the reanalysis draft: it keeps the benchmark")


def journey_halo_track1(browser, root: Path) -> list[str]:
    """Track 1: a typed model → its halo, SHM + LMC listed but disabled, the fixed benchmark chosen, its summary → the
    scan, a real child → the launched command names it → the study: its halo line, each point at the benchmark in the
    point table → a restart, the same → the export's halo column and halo.json, one identity → a resume with the
    published halos refused, naming the halo → Run again as Signal best fits: the draft keeps the benchmark."""
    bench = Workbench(root / "halo_track1", share_cache=True, warm=("/new/track1",))
    (bench.root / "runs" / MODEL).write_text(_model_text())
    bench.start()
    seen = []
    try:
        page = browser.page()
        page.goto(bench.url + f"/new/track1?model={MODEL}")
        page.wait_text("halo family")
        listed = _families_listed(page)
        assert listed == {"SHM": False, "SHM++": False, "SHM + LMC": True}, \
            f"SHM++ beside the SHM, and SHM + LMC listed, disabled: {listed}"
        seen.append(f"the halo family offered: {listed} (true: disabled)")
        page.click_text("Advanced: axis strings")
        page.type_into("x axis", "m_chi:10:1000:log:3")
        page.type_into("y axis", "g_chi:0.05:0.5:log:2")
        page.choose("halo treatment", "a fixed common benchmark")
        page.wait_text("Halo uncertainty not propagated")
        seen.append("the benchmark's summary shown before launch")
        page.wait_text("Scan setup")
        page.click_text("Scan")
        page.wait(lambda: "/live" in page.url(), "the scan's live page")
        folder, command = _launched(page, bench, "track1")
        assert "--halo" in command and command[command.index("--halo") + 1] == "benchmark", \
            f"the launched command carries --halo benchmark: {command}"
        text = wait_finished(page, timeout=1800)
        assert "\ncompleted\n" in text, f"the scan completed: {text[:1500]}"
        seen.append("the scan, a real child, completed; its command carries --halo benchmark")
        page.click_text("Open the study")
        page.wait_text("Halo: SHM, a fixed common benchmark")
        study_url, study = page.url(), page.text()
        identity = IDENTITY.search(study.split("Halo: SHM, a fixed common benchmark", 1)[1]).group(1)
        page.click_text("Explain a point")
        page.wait(lambda: "at the fixed benchmark halo" in page.text(), "the point table names each point's halo",
                  timeout=60)
        seen.append(f"the study: its halo line (identity {identity}) and the point table's halo column")
        page.goto("about:blank", ready=False)
        bench.restart()
        page.goto(study_url)
        page.wait_text(f"identity {identity}")
        seen.append("after a restart: the same halo and identity")
        out = bench.root / "tables"
        done = _cli(bench, "evidence", "tables", str(folder / "result.json"), "--out", str(out))
        assert done.returncode == 0, done.stderr[-800:]
        rows = list(csv.DictReader(io.StringIO((out / "points.csv").read_text())))
        assert rows and all(r["halo"].startswith("at the fixed benchmark halo") for r in rows), \
            "the export names each point's halo"
        halo = json.loads((out / "halo.json").read_text())["resolution"]
        assert halo["identity"].startswith(identity), "the export's halo identity is the study's"
        seen.append("the export: each point's halo, and halo.json with the study's identity")
        other = [*command, "--resume"]
        other[other.index("--halo") + 1] = "published"
        refused = _cli(bench, *other)
        assert refused.returncode != 0 and "the halo differs" in refused.stdout + refused.stderr, \
            "a resume with another halo is refused, naming the halo"
        seen.append("a resume with the published halos: refused, naming the halo")
        page.goto(study_url)
        page.click_text("Run again")
        page.click_text("As Signal best fits")
        _drafted(page)
        seen.append("Run again as Signal best fits: the draft keeps the benchmark")
    finally:
        bench.stop(runs=True)
    return seen


def journey_halo_track2(browser, root: Path) -> list[str]:
    """Track 2: CDMS II Si (2013) with a typed model at one mass → the fixed benchmark chosen → the run, a real child,
    its command naming it → the study's halo line → after a restart the same → Run again as Constrain a model: the
    draft keeps the benchmark."""
    bench = Workbench(root / "halo_track2", share_cache=True, warm=("/new/track2",)).start()
    seen = []
    try:
        page = browser.page()
        page.goto(bench.url + "/new/track2")
        page.wait_text("halo treatment")
        page.choose("the search with events", "CDMS II Si (2013)")
        page.click_text("Also compare your own models (optional)")     # the restructured page (2026-11-18)
        page.click_text("Paste a typed model (YAML)")
        page.type_into("a typed model with its couplings; leave empty for the library alone", _model_text())
        page.type_into("their masses (GeV)", "10")
        page.click_text("the library's space as well", ".q-checkbox")
        page.click_text("3. Options (defaults are fine for a first run)")
        page.type_into("background-only simulations", "1000")
        page.click_text("Check fitted points as physical models", ".q-checkbox")
        page.choose("halo treatment", "a fixed common benchmark")
        page.wait_text("Halo uncertainty not propagated")
        time.sleep(1.0)              # the unfolded sections settled: a click during their transition is lost
        page.click_text("Fit, combine and rank")
        page.wait(lambda: "/live" in page.url(), "the run's live page")
        _, command = _launched(page, bench, "signal")
        assert "--halo" in command and command[command.index("--halo") + 1] == "benchmark", \
            f"the launched command carries --halo benchmark: {command}"
        text = wait_finished(page, timeout=1800)
        assert "\ncompleted\n" in text, f"the run completed: {text[:1500]}"
        seen.append("the Track 2 run, a real child, completed; its command carries --halo benchmark")
        page.click_text("Open the study")
        page.wait_text("Halo: SHM, a fixed common benchmark")
        study_url = page.url()
        page.goto("about:blank", ready=False)
        bench.restart()
        page.goto(study_url)
        page.wait_text("Halo: SHM, a fixed common benchmark")
        seen.append("the study's halo line, the same after a restart")
        page.click_text("Run again")
        page.click_text("As Constrain a model")
        _drafted(page)
        seen.append("Run again as Constrain a model: the draft keeps the benchmark")
    finally:
        bench.stop(runs=True)
    return seen


def journey_halo_unavailable(browser, root: Path) -> list[str]:
    """Explain a signal at the fixed benchmark with a native joint fit, which has no form at a benchmark: the run is
    refused before it calculates, its page naming why, no traceback and no study."""
    bench = Workbench(root / "halo_unavailable", share_cache=True, warm=("/new/single",)).start()
    try:
        page = browser.page()
        page.goto(bench.url + "/new/single")
        page.type_into("the model (YAML, with coupling values)", _model_text())
        page.click_text("Advanced calculation options")
        page.wait_text("native joint fit with")
        _choose_in_place(page, "native joint fit with", "DEAP-3600 (2019)")
        page.choose("halo treatment", "a fixed common benchmark")
        page.click_text("Run the study")
        page.wait(lambda: "/live" in page.url(), "the run's live page")
        text = wait_finished(page, timeout=900)
        assert "\nfailed\n" in text, f"the run is refused: {text[:1500]}"
        flat = re.sub(r"[│╭╮╰╯─\s]+", " ", text)            # the command line's error box, its lines joined
        assert "native joint signal/null likelihood: not calculated with SHM: fixed benchmark" in flat, \
            "the refusal names the comparison that cannot use the benchmark"
        assert "Traceback" not in text, "a refusal, not a traceback"
        return ["Explain a signal with a native joint fit at the benchmark: refused before calculating, the reason "
                "named on its run page, no traceback"]
    finally:
        bench.stop(runs=True)


def journey_halo_default(browser, root: Path) -> list[str]:
    """The defaults, unchanged and stated: Track 1 over the SHM region (its default; a 2 × 2 plane, every point over
    the region) and Track 2 with each search's published halo, each from its form's summary → the run → the study's
    halo line and, for Track 1, each point's label over the region → a restart → the export's halo.json → Run again in
    the other track: the draft states the halo it will use."""
    seen = []
    bench = Workbench(root / "halo_default", share_cache=True, warm=("/new/track1", "/new/track2"))
    (bench.root / "runs" / MODEL).write_text(_model_text())
    bench.start()
    try:
        page = browser.page()
        page.goto(bench.url + f"/new/track1?model={MODEL}")
        page.wait_text("SHM over the owner's working Standard Halo Model preset")      # the setting: the region
        page.click_text("Advanced: axis strings")
        page.type_into("x axis", "m_chi:10:1000:log:2")
        page.type_into("y axis", "g_chi:0.05:0.5:log:2")
        page.wait_text("Scan setup")
        page.click_text("Scan")
        page.wait(lambda: "/live" in page.url(), "the scan's live page")
        folder, command = _launched(page, bench, "track1")
        assert "--halo" not in command, f"the default launches without a halo of its own (the setting): {command}"
        text = wait_finished(page, timeout=3600)
        assert "\ncompleted\n" in text, f"the scan completed: {text[:1500]}"
        page.click_text("Open the study")
        page.wait_text("Halo: SHM over the owner's working Standard Halo Model preset")
        study_url = page.url()
        page.click_text("Explain a point")
        page.wait(lambda: "the tested halo region" in page.text() or "halo-sensitive" in page.text()
                  or "halo coverage incomplete" in page.text(), "each point's label over the region", timeout=60)
        seen.append("Track 1 by default: the region's summary before launch; the study's halo line and each point's "
                    "label over the region")
        page.goto("about:blank", ready=False)
        bench.restart()
        page.goto(study_url)
        page.wait_text("Halo: SHM over the owner's working Standard Halo Model preset")
        out = bench.root / "tables"
        done = _cli(bench, "evidence", "tables", str(folder / "result.json"), "--out", str(out))
        assert done.returncode == 0, done.stderr[-800:]
        assert json.loads((out / "halo.json").read_text())["resolution"]["treatment"] == "region", \
            "the export names the region"
        page.click_text("Run again")
        page.click_text("As Signal best fits")
        page.click_text("Reopen saved inputs")
        page.wait(lambda: "experiment:" in page.value_of("Prepopulated numerical/scientific request (YAML)"),
                  "the reanalysis draft")
        assert "halo:" not in page.value_of("Prepopulated numerical/scientific request (YAML)"), \
            "a region has no Track 2 form: the draft names none (each search's published halo)"
        seen.append("after a restart the same; the export names the region; Run again as Signal best fits drafts "
                    "with each search's published halo")
        page.goto(bench.url + "/new/track2")
        page.wait_text("Each experiment's own published halo")
        page.choose("the search with events", "CDMS II Si (2013)")
        page.click_text("Also compare your own models (optional)")     # the restructured page (2026-11-18)
        page.click_text("Paste a typed model (YAML)")
        page.type_into("a typed model with its couplings; leave empty for the library alone", _model_text())
        page.type_into("their masses (GeV)", "10")
        page.click_text("the library's space as well", ".q-checkbox")
        page.click_text("3. Options (defaults are fine for a first run)")
        page.type_into("background-only simulations", "1000")
        page.click_text("Check fitted points as physical models", ".q-checkbox")
        time.sleep(1.0)              # the unfolded sections settled: a click during their transition is lost
        page.click_text("Fit, combine and rank")
        page.wait(lambda: "/live" in page.url(), "the run's live page")
        folder, command = _launched(page, bench, "signal")
        assert "--halo" not in command, f"Track 2's default launches without a halo: {command}"
        text = wait_finished(page, timeout=1800)
        assert "\ncompleted\n" in text, f"the run completed: {text[:1500]}"
        page.click_text("Open the study")
        page.wait_text("Halo: Each experiment's own published halo")
        page.click_text("Run again")
        page.click_text("As Constrain a model")
        page.click_text("Reopen saved inputs")
        page.wait(lambda: "halo: published" in page.value_of("Prepopulated numerical/scientific request (YAML)"),
                  "the reanalysis draft as Track 1: it states the published halos")
        seen.append("Track 2 by default: each search's published halo stated before launch and on its study; Run "
                    "again as Constrain a model drafts with the published halos")
    finally:
        bench.stop(runs=True)
    return seen


# --- halo phase 2: SHM++ -------------------------------------------------------------------------------------------

SHMPP_LINE = "Halo: SHM++, fixed benchmark; halo uncertainty not propagated"
UNSUPPORTED = "not calculated with SHM++: fixed benchmark"


def _shmpp_reference():
    """SHM++'s snapshot as this checkout's generator makes it, in this process (where no mutation is applied)."""
    from adroit.core import halo_choice
    return halo_choice.fixed("shm-plus-plus")


def _constructions(value) -> list[str]:
    """Every direct-detection limit's construction in a saved result (``limits._strongest``)."""
    found = []
    if isinstance(value, dict):
        text = value.get("construction")
        if isinstance(text, str) and text.startswith("module procedure evaluated at CL=0.95"):
            found.append(text)
        for item in value.values():
            found += _constructions(item)
    elif isinstance(value, list):
        for item in value:
            found += _constructions(item)
    return found


def _shmpp_checked(data: dict) -> list[str]:
    """The invariants on a saved SHM++ run, judged here, apart from its child: the request's snapshot is SHM++'s (not
    interchanged, the generator's output), and every direct-detection limit was taken with its tables."""
    from adroit.core import halo_choice
    from adroit.parameter_space import halo_limits
    reference = _shmpp_reference()
    halo = halo_choice.FixedHalo.model_validate(data["request"]["halo"])
    assert (halo.family, halo.benchmark) == ("shm-plus-plus", "shmpp-1810.11468"), "the saved request carries SHM++"
    assert halo.halo.speed_density != reference.sun.speed_density, \
        "the detector's and the Sun's tables are not interchanged"
    assert halo_choice.verify(halo) == "" and halo.tables == reference.tables, \
        "the saved tables are SHM++'s generator's output"
    assert data["halo_resolution"]["tables"] == reference.tables, "the result's resolution names SHM++'s tables"
    seen = [f"the saved snapshot: SHM++'s own tables ({reference.tables['detector'][:12]}, "
            f"{reference.tables['sun'][:12]}), checked against the generator here"]
    if "scan" in data:
        key = halo_limits.tabulated(reference.halo)[:12]
        limits = _constructions(data["scan"]) + _constructions(data.get("verdict", {}))
        assert limits and all(f"its tables {key}" in c for c in limits), \
            "every direct-detection limit taken with SHM++'s tables"
        seen.append(f"every direct-detection limit ({len(limits)}) taken with SHM++'s tables ({key})")
    return seen


def _compared(cli: dict, browser: dict, fields: tuple[str, ...]) -> None:
    """The command line's run and the workbench's agree in every scientific field named."""
    for field in fields:
        a, b = cli, browser
        for part in field.split("."):
            a, b = a.get(part) if isinstance(a, dict) else None, b.get(part) if isinstance(b, dict) else None
        assert a == b, f"the same request on the command line gives the same {field}"


def _scientific(points: list[dict]) -> list:
    return [(p.get("point"), p.get("excluded"), p.get("pending"), p.get("ratios"), p.get("omega_h2"))
            for p in points]


def _stale_copy(page, bench: Workbench, folder: Path) -> str:
    """A copy of the study whose certificates were certified on another local densities file: its page says it is
    stale, naming the file; viewing it never rewrites it."""
    import hashlib
    import shutil
    copy = bench.root / "runs" / "stale_shmpp"
    shutil.copytree(folder, copy, ignore=shutil.ignore_patterns("study.json", "children"))
    text = (copy / "result.json").read_text()
    old = json.loads(text)["halo_resolution"]["data"]["local densities"]
    assert old and text.count(old) > 1, "the study's claims are certified on the local densities file"
    (copy / "result.json").write_text(text.replace(old, "0" * 64))
    done = subprocess.run([sys.executable, "-c", "import sys; from pathlib import Path; from adroit.orchestrator import "
                           "studies; studies.record(Path(sys.argv[1]), 'track1', 'an SHM++ study certified on an "
                           "earlier local densities file')", str(copy)], cwd=ROOT, env=bench.env, capture_output=True,
                          text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-600:]
    before = hashlib.sha256((copy / "result.json").read_bytes()).hexdigest()
    page.goto(bench.url + "/study?path=stale_shmpp")
    page.wait_text("the halo data file (local densities) changed since it was certified")
    assert hashlib.sha256((copy / "result.json").read_bytes()).hexdigest() == before, "viewing never rewrites it"
    return "a copy certified on an earlier local densities file: shown stale, naming the file; unchanged by viewing"


def _missing_input(page) -> str:
    """The reanalysis draft with its Sun-frame table removed: refused as it is saved, naming it, no draft saved and
    nothing calculated (a snapshot not of its family's form is not read: the halo phase 2 audit's HB-01; before it,
    the draft was saved and its review named the table)."""
    import yaml
    label = "Prepopulated numerical/scientific request (YAML)"
    draft = yaml.safe_load(page.value_of(label))
    assert draft["halo"].pop("sun", None) is not None, "the draft holds SHM++'s Sun-frame table"
    page.type_into(label, yaml.safe_dump(draft, sort_keys=False))
    before = page.url()
    page.click_text("Save changes / review this draft")
    page.wait_text("halo: shmpp-1810.11468: a snapshot of SHM++ without its Sun-frame table: refused")
    time.sleep(1.0)
    assert page.url() == before, "no draft is saved without its Sun-frame table"
    return "the draft without SHM++'s Sun-frame table: refused as it is saved, naming it; no draft, nothing calculated"


def journey_shmpp_track1(browser, root: Path) -> list[str]:
    """Track 1 with SHM++: a typed model → SHM + LMC listed but disabled, SHM++ chosen (its treatment the fixed
    benchmark only), its numbers and applicability expanded → the scan, a real child, its command naming SHM++ → its
    snapshot and every direct-detection limit judged here → the same request on the command line, the same result →
    the study: its halo line, each point at SHM++ → a restart, the same → the export → a resume at the SHM benchmark
    refused → Run again as Signal best fits: the draft keeps SHM++; without its Sun-frame table it is refused as saved → a stale
    copy."""
    bench = Workbench(root / "shmpp_track1", share_cache=True, warm=("/new/track1",))
    (bench.root / "runs" / MODEL).write_text(_model_text())
    bench.start()
    seen = []
    try:
        page = browser.page()
        page.goto(bench.url + f"/new/track1?model={MODEL}")
        page.wait_text("halo family")
        listed = _families_listed(page)
        assert listed == {"SHM": False, "SHM++": False, "SHM + LMC": True}, \
            f"SHM++ beside the SHM, and SHM + LMC listed, disabled: {listed}"
        page.choose("halo family", "SHM++")
        page.wait_text("SHM++, fixed benchmark; halo uncertainty not propagated")
        assert page.value_of("halo treatment").startswith("a fixed common benchmark"), \
            "choosing SHM++ takes its fixed benchmark"
        page.click_text("Halo: parameters, source and applicability")
        page.wait_text("share η = 0.2")
        for words in ("no accepted-count ratio", "no annual modulation and no directional rates",
                      "Not calculated with this choice"):
            page.wait_text(words)
        seen.append(f"the halo family offered: {listed} (true: disabled); SHM++ chosen, its benchmark, numbers and "
                    "applicability shown before launch")
        page.click_text("Advanced: axis strings")
        page.type_into("x axis", "m_chi:2:8:log:2")
        page.type_into("y axis", "g_chi:0.05:0.5:log:2")
        page.wait_text("Scan setup")
        page.click_text("Scan")
        page.wait(lambda: "/live" in page.url(), "the scan's live page")
        folder, command = _launched(page, bench, "track1")
        assert command[command.index("--halo") + 1] == "benchmark" and \
            command[command.index("--halo-family") + 1] == "shm-plus-plus", \
            f"the launched command carries SHM++: {command}"
        text = wait_finished(page, timeout=1800)
        assert "\ncompleted\n" in text, f"the scan completed: {text[:1500]}"
        data = json.loads((folder / "result.json").read_text())
        seen.append("the scan, a real child, completed; its command carries --halo benchmark --halo-family "
                    "shm-plus-plus")
        seen += _shmpp_checked(data)
        cli_folder = bench.root / "runs" / "shmpp_cli"
        words = [*command]
        words[words.index("--out") + 1] = str(cli_folder)
        done = _cli(bench, *words)
        assert done.returncode == 0, done.stderr[-800:]
        other = json.loads((cli_folder / "result.json").read_text())
        _compared(other, data, ("halo_resolution.identity", "verdict.level", "verdict.summary"))
        assert _scientific(other["scan"]["points"]) == _scientific(data["scan"]["points"]), \
            "the same request on the command line gives the same points"
        seen.append("the same request on the command line: the same resolution, verdict and points")
        page.click_text("Open the study")
        page.wait_text(SHMPP_LINE)
        study_url, study = page.url(), page.text()
        identity = IDENTITY.search(study.split(SHMPP_LINE, 1)[1]).group(1)
        assert data["halo_resolution"]["identity"].startswith(identity), "the page shows the result's identity"
        page.click_text("Explain a point")
        page.wait(lambda: "at the fixed benchmark halo (SHM++" in page.text(), "the point table names SHM++",
                  timeout=120)        # 60 s timed out once under load (the 1.0.1 release checks), as other waits here
        seen.append(f"the study: its halo line (identity {identity}) and the point table's SHM++ column")
        page.goto("about:blank", ready=False)
        bench.restart()
        page.goto(study_url)
        page.wait_text(f"identity {identity}")
        seen.append("after a restart: the same halo and identity")
        out = bench.root / "tables"
        done = _cli(bench, "evidence", "tables", str(folder / "result.json"), "--out", str(out))
        assert done.returncode == 0, done.stderr[-800:]
        rows = list(csv.DictReader(io.StringIO((out / "points.csv").read_text())))
        assert rows and all(r["halo"].startswith("at the fixed benchmark halo (SHM++") for r in rows), \
            "the export names each point's halo"
        exported = json.loads((out / "halo.json").read_text())["resolution"]
        assert exported["identity"].startswith(identity) and exported["tables"] == data["halo_resolution"]["tables"], \
            "the export's halo is the study's"
        seen.append("the export: each point at SHM++, and halo.json with the study's identity and tables")
        other = [*command, "--resume"]
        del other[other.index("--halo-family"):other.index("--halo-family") + 2]
        refused = _cli(bench, *other)
        assert refused.returncode != 0 and "the halo differs" in refused.stdout + refused.stderr, \
            "a resume at the SHM benchmark is refused, naming the halo"
        seen.append("a resume at the SHM benchmark: refused, naming the halo")
        page.goto(study_url)
        page.click_text("Run again")
        page.click_text("As Signal best fits")
        page.click_text("Reopen saved inputs")
        reference = _shmpp_reference()
        page.wait(lambda: "shmpp-1810.11468" in page.value_of("Prepopulated numerical/scientific request (YAML)") and
                  reference.tables["detector"] in page.value_of("Prepopulated numerical/scientific request (YAML)"),
                  "Run again as Signal best fits: the draft keeps SHM++")
        seen.append("Run again as Signal best fits: the draft keeps SHM++ and its tables")
        seen.append(_missing_input(page))
        seen.append(_stale_copy(page, bench, folder))
    finally:
        bench.stop(runs=True)
    return seen


def journey_shmpp_track2(browser, root: Path) -> list[str]:
    """Track 2 with SHM++: CDMS II Si (2013) with a typed model at one mass → SHM++ chosen → the run, a real child, its
    command naming it → its snapshot judged here → the same request on the command line, the same fits and null limits
    → the study's halo line → after a restart the same → Run again as Constrain a model: the draft keeps SHM++ →
    Explain a signal at SHM++ with a native joint fit: refused, naming SHM++."""
    bench = Workbench(root / "shmpp_track2", share_cache=True, warm=("/new/track2", "/new/single")).start()
    seen = []
    try:
        page = browser.page()
        page.goto(bench.url + "/new/track2")
        page.wait_text("halo family")
        page.choose("the search with events", "CDMS II Si (2013)")
        page.click_text("Also compare your own models (optional)")     # the restructured page (2026-11-18)
        page.click_text("Paste a typed model (YAML)")
        page.type_into("a typed model with its couplings; leave empty for the library alone", _model_text())
        page.type_into("their masses (GeV)", "10")
        page.click_text("the library's space as well", ".q-checkbox")
        page.click_text("3. Options (defaults are fine for a first run)")
        page.type_into("background-only simulations", "1000")
        page.click_text("Check fitted points as physical models", ".q-checkbox")
        page.choose("halo family", "SHM++")
        page.wait_text("SHM++, fixed benchmark; halo uncertainty not propagated")
        time.sleep(1.0)              # the unfolded sections settled: a click during their transition is lost
        page.click_text("Fit, combine and rank")
        page.wait(lambda: "/live" in page.url(), "the run's live page")
        folder, command = _launched(page, bench, "signal")
        assert command[command.index("--halo") + 1] == "benchmark" and \
            command[command.index("--halo-family") + 1] == "shm-plus-plus", \
            f"the launched command carries SHM++: {command}"
        text = wait_finished(page, timeout=1800)
        assert "\ncompleted\n" in text, f"the run completed: {text[:1500]}"
        data = json.loads((folder / "result.json").read_text())
        seen.append("the Track 2 run, a real child, completed; its command carries SHM++")
        seen += _shmpp_checked(data)
        cli_folder = bench.root / "runs" / "shmpp_cli"
        words = [*command]
        words[words.index("--out") + 1] = str(cli_folder)
        done = _cli(bench, *words)
        assert done.returncode == 0, done.stderr[-800:]
        other = json.loads((cli_folder / "result.json").read_text())
        _compared(other, data, ("halo_resolution.identity",))
        science = lambda r: ([(f["label"], f["s_hat"], f["z_local"]) for f in r["fits"]],          # noqa: E731
                             [(c["label"], c["null_limits"]) for c in r["combinations"]])
        assert science(other) == science(data), "the same request on the command line gives the same fits and nulls"
        seen.append("the same request on the command line: the same resolution, fits and null limits")
        page.click_text("Open the study")
        page.wait_text(SHMPP_LINE)
        study_url = page.url()
        page.goto("about:blank", ready=False)
        bench.restart()
        page.goto(study_url)
        page.wait_text(SHMPP_LINE)
        seen.append("the study's halo line, the same after a restart")
        page.click_text("Run again")
        page.click_text("As Constrain a model")
        page.click_text("Reopen saved inputs")
        page.wait(lambda: "shmpp-1810.11468" in page.value_of("Prepopulated numerical/scientific request (YAML)"),
                  "Run again as Constrain a model: the draft keeps SHM++")
        seen.append("Run again as Constrain a model: the draft keeps SHM++")
        page.goto(bench.url + "/new/single")
        page.type_into("the model (YAML, with coupling values)", _model_text())
        page.click_text("Advanced calculation options")
        page.wait_text("native joint fit with")
        _choose_in_place(page, "native joint fit with", "DEAP-3600 (2019)")
        page.choose("halo family", "SHM++")
        page.click_text("Run the study")
        page.wait(lambda: "/live" in page.url(), "the run's live page")
        text = wait_finished(page, timeout=900)
        flat = re.sub(r"[│╭╮╰╯─\s]+", " ", text)
        assert "\nfailed\n" in text and f"native joint signal/null likelihood: {UNSUPPORTED}" in flat, \
            "the refusal names the comparison SHM++ cannot calculate"
        assert "Traceback" not in text, "a refusal, not a traceback"
        seen.append("Explain a signal with a native joint fit at SHM++: refused before calculating, naming SHM++")
    finally:
        bench.stop(runs=True)
    return seen


JOURNEYS = {"halo_track1": journey_halo_track1, "halo_track2": journey_halo_track2,
            "halo_unavailable": journey_halo_unavailable, "halo_default": journey_halo_default,
            "shmpp_track1": journey_shmpp_track1, "shmpp_track2": journey_shmpp_track2}
# (journey, the defect restored in its children: scripts/netguard/acceptance_mutations.py, the invariant its failure
# must name)
CONTROLS = [("halo_track1", "halo_form_ignored", "carries --halo benchmark"),
            ("halo_track1", "halo_dropped_by_child", "the point table names each point's halo"),
            ("halo_track1", "halo_checkpoint_identity_omitted", "a resume with another halo is refused"),
            ("halo_track1", "halo_export_unqualified", "the export names each point's halo"),
            ("halo_track1", "future_family_as_shm", "listed, disabled"),
            ("shmpp_track1", "shmpp_as_shm", "every direct-detection limit taken with SHM++'s tables"),
            ("shmpp_track1", "shmpp_isotropic", "the saved tables are SHM++'s generator's output"),
            ("shmpp_track1", "shmpp_frames_interchanged", "the detector's and the Sun's tables are not interchanged"),
            ("shmpp_track1", "shmpp_continuation_reset", "the draft keeps SHM++")]
# two of halo phase 2's six controls run in the headless layer only (tests/ui/acceptance/test_halo_shmpp_journeys.py),
# where they can be exercised: a cache keyed without the mixture needs two SHM++ mixtures in one process, which no
# workbench run makes; a pending comparison labelled allowed needs a comparison SHM++ cannot calculate, which the small
# real plane above does not have (its decisive searches are calculable at SHM++)
