"""The release acceptance layer (the consolidation plan's M4, the owner's direction D-5, 2026-10-25): the workbench
served by the ordinary command, driven in the installed Chrome (``scripts/browser.py``: its DevTools protocol, no
driver), its runs launched by the ordinary launcher as real child processes, their durable outputs opened by the
primary completion action, and reopened after the server restarts.

    uv run python scripts/browser_acceptance.py                 # every journey; exit 0 only if all pass
    uv run python scripts/browser_acceptance.py --only intake
    uv run python scripts/browser_acceptance.py --repeat 2      # all again, a fresh Chrome profile each time

Every writable location is a temporary folder of its own. No credential of the person's reaches any child: every
variable that names a key, token, secret or password is removed and each provider key set empty (which the settings'
``.env`` loader then leaves empty). Only 127.0.0.1 is contacted, and that is enforced, not assumed (``network``, run
first): every Python child imports ``scripts/netguard/sitecustomize.py``, which refuses any connection or name
resolution outside this machine beneath every client, the proxy variables point at a closed local port, and Chrome is
fenced (``browser.Chrome.fence``); negative controls show each refusal. A paid step is refused for want of a key,
sent to an address on this machine that refuses it, or answered by a provider fixture on this machine ($0).

Exit codes: 0 every journey passed; 1 a journey failed; 3 a prerequisite is missing here (no Chrome, or the tools a
real calculation needs), so release acceptance is not established.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from browser import Chrome, chrome_tail, chrome_version, find_chrome  # noqa: E402
import browser_harness  # noqa: E402
from browser_harness import (NEGATIVE, NotEstablished, Workbench, child_environment, helper,  # noqa: E402,F401
                             journey_network, submit, wait_finished)
from browser_harness import free_port  # noqa: E402
from browser_journeys import DESCRIBES as RUN_DESCRIBES, JOURNEYS as RUN_JOURNEYS, SUBSTITUTED as RUN_SUBSTITUTED  # noqa: E402
import browser_halo  # noqa: E402

NOT_ESTABLISHED = 3
SUBSTITUTED = {
    "provider": "no provider is contacted: a paid step without a key is refused before anything is reserved; with a "
                "dummy key its request goes to a closed port on this machine (a transport failure after dispatch)",
    "history's studies": "the saved studies' verdicts are computed by the real verdict code over a toy plane (Ωh² = "
                         "0.12/g², one toy constraint) and written by runs._write; no scan runs for them (journey 2's "
                         "promoted children compute theirs: its own entries)",
}
# The journeys each entry describes: only the chosen journeys' entries are printed, and so reach the receipt (the auditor's
# CT recheck, CU-05, 2026-10-28: a blanket "no scan runs in the browser layer" had stood beside the promotions' scans)
DESCRIBES = {"provider": ("no_key", "uncertain"), "history's studies": ("history",)}
TYPED_MODEL = None          # set in main: a typed vector model's YAML


# --- journeys ----------------------------------------------------------------------------------------------------

def journey_intake(browser, root: Path) -> list[str]:
    """Journey 1's release half: the intake form → the ordinary launcher → ``adroit models step`` as a real child
    process → its draft (durable output) → the primary action → the draft page; the server restarted, the draft
    reopened. A typed model costs nothing: the cost shown says so."""
    bench = Workbench(root / "intake", warm=("/models/intake",)).start()
    seen = []
    try:
        page = browser.page()
        page.goto(bench.url + "/models/intake")

        def fill():
            page.choose("Model input kind", "A typed model (YAML, $0)")
            page.type_into("Idea, TeX or typed field/model YAML", TYPED_MODEL)
        seen += submit(page, fill, "Start reviewed intake", lambda: "/live" in page.url(),
                       "the live page of the launched run")
        text = wait_finished(page)
        assert "Draft ready for review" in text, f"the intake's run page reads 'Draft ready for review': {text[:800]}"
        assert "This run: $0" in text, "the cost of a typed model, $0, is shown"
        seen.append("live page: draft ready, $0")
        page.ready()
        seen.append(_steady_primary_action(page, "review model draft"))
        page.click_text("Review model draft", hold=1.5)        # the primary completion action, held across a tick
        page.wait(lambda: "/models/intake" in page.url() and "session=" in page.url(), "the draft page")
        page.wait_text("Candidate 1")
        draft_url = page.url()
        seen.append("primary action: the draft page, candidate shown")
        page.goto("about:blank", ready=False)
        bench.restart()
        page.goto(draft_url)
        page.wait_text("Candidate 1")
        seen.append("after a restart: the same draft")
    finally:
        bench.stop()
    return seen


def _steady_primary_action(page, words: str) -> str:
    """A finished run's page keeps its primary button between refresh ticks, and the button is a link the browser
    follows itself (the auditor's CO recheck, 2026-10-26: the page had been rebuilt every second, and a click on the
    replaced button was lost, intermittently, under load). The element is marked, two ticks pass, and the mark must
    still be there."""
    mark = f"""(() => {{ const b = [...document.querySelectorAll('a, button')].find(e => e.offsetParent !== null
                    && e.innerText.trim().toLowerCase() === {json.dumps(words)});
                if (!b) return null; b.dataset.journeyMark = '1'; return [b.tagName, b.getAttribute('href') || '']; }})()"""
    tag, href = page.wait(lambda: page.evaluate(mark), f"the primary action {words!r}")
    assert tag == "A" and href, f"the primary action is a link the browser follows ({tag}, {href!r})"
    time.sleep(2.5)
    assert page.evaluate("document.querySelector('[data-journey-mark]') !== null"), \
        "the finished run's page kept its primary button across refresh ticks (it was rebuilt under the click)"
    return f"the finished run's page steady across refresh ticks; its primary action a link ({href.split('?')[0]})"


def _paid_intake_form(page) -> None:
    page.type_into("Idea, TeX or typed field/model YAML", "a Z2-odd real scalar singlet")
    page.type_into("Session budget ($)", "1")
    page.tick("I approve this spend")


def journey_no_key(browser, root: Path) -> list[str]:
    """Journey 1 with a missing prerequisite: a paid intake with no API key is refused by the child process before
    anything is reserved, and the run page says which variable to set and that nothing was sent."""
    bench = Workbench(root / "no_key", warm=("/models/intake",)).start()
    try:
        page = browser.page()
        page.goto(bench.url + "/models/intake")
        notes = submit(page, lambda: _paid_intake_form(page), "Start reviewed intake", lambda: "/live" in page.url(),
                       "the live page of the launched run")
        text = wait_finished(page)
        assert "ANTHROPIC_API_KEY" in text, "the variable to set is named"
        assert "no paid request was sent" in text or "This run: $0" in text, "nothing was sent or reserved"
        return notes + ["a paid intake without a key: refused, the variable named, nothing sent"]
    finally:
        bench.stop()


def journey_uncertain(browser, root: Path) -> list[str]:
    """Journey 1 with uncertain spending: a dummy key and a provider address on this machine that refuses the
    connection; the request is reserved before dispatch and its bill is then unknown: the run page shows the
    reservation, never "$0" or "no paid request was sent"."""
    closed = free_port()                       # nothing listens there
    bench = Workbench(root / "uncertain", keys={"ANTHROPIC_API_KEY": "sk-ant-simulated-not-a-key",
                                                "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{closed}"},
                      warm=("/models/intake",)).start()
    try:
        page = browser.page()
        page.goto(bench.url + "/models/intake")
        notes = submit(page, lambda: _paid_intake_form(page), "Start reviewed intake", lambda: "/live" in page.url(),
                       "the live page of the launched run")
        text = wait_finished(page)
        assert "reserved whose bill is not yet known" in text, text[:1200]
        assert "no paid request was sent" not in text
        return notes + ["a request whose bill is unknown: its reservation shown, not $0"]
    finally:
        bench.stop()


SEED = """
import json, runpy
from pathlib import Path
from unittest.mock import patch
from adroit.constraints import relic
from adroit.core.config import get_settings
from adroit.parameter_space.classes import Spin1Class
from adroit.parameter_space.likelihood import LikelihoodSettings
from adroit.parameter_space.scan import PointResult
import importlib
v = importlib.import_module('adroit.parameter_space.verdict')
H = runpy.run_path('tests/parameter_space/test_eos_verdict.py')
H['DESIGN']['omega'] = lambda t, g: 0.12 / g ** 2
def evaluate(cls, p, *a):
    return PointResult(point=p, omega_h2=H['_toy_density'](p), dd_kind='SI', dd_sigma_cm2=0, dd_limit_cm2=1,
                       excluded={'toy': False, 'colliders (CMS)': False})
from adroit.model_building.audit import audit
from adroit.orchestrator import runs, studies, track1
from adroit.parameter_space import simplified
root = get_settings().runs_dir
with patch.object(Spin1Class, 'omega_h2', lambda self, p: H['_toy_density'](p)), \\
     patch('adroit.parameter_space.searches.prefetch_lhc', lambda c, p, *a: [None] * len(p)), \\
     patch.object(v, 'evaluate', evaluate), patch.object(relic, 'eos_folder', lambda: None), \\
     patch('adroit.core.certificate.EOS_BAND_ASSESSED', True):     # saved as an earlier policy decided it: the
    scan = H['_plane']([0.98, 1.02])                                 # page must show what is stored
    cuts, combined = v.verdict_pair(scan, likelihood=LikelihoodSettings())
spec = simplified.model('vector', 10, 30)
request = track1.Track1Request(spec=spec, model_class=Spin1Class(), fixed=scan.request.fixed, x=scan.request.x,
                               y=scan.request.y, likelihood=LikelihoodSettings(), literature=False)
result = track1.Track1Result(request=request, audit=audit(spec), class_name='vector', fixed=request.fixed, scan=scan,
                             verdict=cuts, likelihood_verdict=combined,
                             notes=['SUBSTITUTED: a toy plane, verdict computed without the tables'])
folder = root / 'toy_plane'
folder.mkdir(parents=True)
runs._write(folder, result, track1.report(result), 'track1', 'a toy plane')
studies.record(folder, 'track1', 'a toy plane, without the tables')
(root / 'broken_run').mkdir()
(root / 'broken_run' / 'job.json').write_text('{}')
"""


# The point table's headers as the version matrix's column contract heads them (``tests/version_matrix.COLUMNS``),
# the halo column among them since halo phase 1 (the contract had it; this copy had not, and the merged branch's gate
# found the history journey heading the drawn table otherwise, 2026-11-12)
POINT_HEADS = ["point", "kind", "coordinates", "Ωh²", "status", "first exclusion or pending reason", "halo", ""]
OMEGA = re.compile(r"—|-?\d+(\.\d+)?(e[+-]?\d+)?")              # ``points._number``: Ωh² to four figures, or none


def point_table(page) -> str:
    """The study page's point table as Chrome draws it (the auditor's DJ recheck, DK-03, 2026-11-07: the page cells read the
    rows and columns given to the table; this reads what a person sees): its headers, in order, the contract's
    (``POINT_HEADS``), and in each row a cell of its column's kind under each: a status word under "status", Ωh² as a
    number under "Ωh²", the link "explain" last. Its sort icons' names are not header text."""
    page.click_text("Explain a point", ".q-expansion-item .q-item")
    script = """(() => {
        const t = [...document.querySelectorAll('.q-table__container')].find(t => t.offsetParent !== null
                   && t.innerText.includes('first exclusion or pending reason'));
        if (!t) return null;
        const text = e => { const c = e.cloneNode(true); c.querySelectorAll('.q-icon').forEach(i => i.remove());
                            return c.innerText.trim(); };
        const rows = [...t.querySelectorAll('tbody tr')].map(r => [...r.querySelectorAll('td')].map(text));
        return rows.length ? {heads: [...t.querySelectorAll('thead th')].map(text), rows} : null; })()"""
    found = page.wait(lambda: page.evaluate(script), "the point table, drawn")
    heads, rows = found["heads"], found["rows"]
    assert heads == POINT_HEADS, f"the point table's columns are headed {heads}, not {POINT_HEADS}"
    status, omega = heads.index("status"), heads.index("Ωh²")
    for cells in rows:
        assert len(cells) == len(heads) and cells[status] in ("allowed", "pending", "excluded", "not evaluated") \
            and OMEGA.fullmatch(cells[omega]) and cells[-1] == "explain", \
            f"the point table's columns: a row reads {cells} under {heads}"
    return f"its point table, drawn: {len(rows)} rows under the {len(heads)} contracted headers, each cell of its kind"


def journey_history(browser, root: Path) -> list[str]:
    """Journeys 4 and 6, and M1's qualification, in the browser: a saved study (its verdict computed without the
    equation-of-state tables, with their band assessed as before 1.0.0's nominal policy, so it is stored VIABLE PENDING
    where the present code would decide VIABLE) beside a damaged run record. Studies lists the study with its stored headline and names
    the damaged record; the study opens with what is not certified; its Download menu's evidence bundle is saved by
    the browser and checked on the bundle page (its hashes agree, its saved decision shown); after a restart, the
    same study and bundle again."""
    bench = Workbench(root / "history", warm=("/studies",))
    helper(SEED, bench.env)
    bench.start()
    downloads = root / "history" / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    seen = []
    try:
        page = browser.page()
        try:
            page.call("Browser.setDownloadBehavior", behavior="allow", downloadPath=str(downloads))
        except RuntimeError:
            page.call("Page.setDownloadBehavior", behavior="allow", downloadPath=str(downloads))
        for attempt in ("before", "after"):
            page.goto(bench.url + "/studies")
            page.wait_text("a toy plane, without the tables")
            text = page.text()
            assert "VIABLE PENDING" in text, "the stored headline, not a re-derived one"
            assert "broken_run/job.json" in text, "the damaged run record is named"
            page.click_text("a toy plane, without the tables", "a")
            page.wait(lambda: "/study" in page.url(), "the study page")
            page.ready()
            page.wait_text("VIABLE PENDING")
            report = page.text()
            assert "not certified" in report or "adroit setup --fetch" in report, report[:1200]
            if attempt == "before":
                seen.append(point_table(page))
                page.click_text("Download")
                page.click_text("Evidence bundle (verified ZIP)", ".q-menu .q-item")
                bundle = page.wait(lambda: next((p for p in downloads.glob("*.zip")), None),
                                   "the browser to save the bundle", 180)
            page.goto(bench.url + "/bundle")
            page.type_into("The bundle's folder or file", str(bundle))
            page.click_text("Check")
            page.wait_text("hashes agree")
            page.wait_text("Saved decisions")
            seen.append(f"{attempt} a restart: badge, damage named, the study and its qualification, its bundle "
                        "verified on the bundle page")
            if attempt == "before":
                page.goto("about:blank", ready=False)          # nothing left to reconnect when the server restarts
                bench.restart()
    finally:
        bench.stop()
    return seen


JOURNEYS = {"network": journey_network, "intake": journey_intake, "no_key": journey_no_key,
            "uncertain": journey_uncertain, "history": journey_history, **RUN_JOURNEYS, **browser_halo.JOURNEYS}
SUBSTITUTED.update(RUN_SUBSTITUTED)
SUBSTITUTED.update(browser_halo.SUBSTITUTED)
DESCRIBES.update(RUN_DESCRIBES)
DESCRIBES.update(browser_halo.DESCRIBES)


def substituted(chosen) -> dict[str, str]:
    """What the ``chosen`` journeys substitute: each entry of ``SUBSTITUTED`` describing one of them (``DESCRIBES``)."""
    return {name: words for name, words in SUBSTITUTED.items() if set(DESCRIBES[name]) & set(chosen)}


def _evidence(browser, root: Path, name: str, error: Exception) -> Path:
    """A failed journey's evidence under ``root/failures``: its last page's screenshot, address and text, and why; that
    page's console (its connection's drops and reconnections, and why NiceGUI reloaded it: ``browser.SOCKET_WATCH``)
    and the end of its workbench's log (the auditor's CR recheck, 2026-10-27: a reloaded form and a click that launched
    nothing had been left undiagnosed)."""
    folder = root / "failures" / name
    folder.mkdir(parents=True, exist_ok=True)
    lines = [f"{type(error).__name__}: {error}", load_line()]
    if browser.pages:
        page = browser.pages[-1]
        try:
            page.screenshot(folder / "page.png")
            lines += [f"url: {page.url()}", "", page.text()]
        except (RuntimeError, OSError) as problem:
            lines.append(f"the page could not be read: {type(problem).__name__}: {problem}")
        lines += ["", "the page's console (latest last):", *page.console]
        lines += ["", "its DevTools connection closed, and each attempt to make it again (made again or not):",
                  *page.reattached] if page.reattached else []
        lines += ["", f"the end of Chrome's own log ({browser.log}), its display noise left out:",
                  *chrome_tail(browser.log, 40)] if browser.log is not None else []
    logs = sorted((root / name).glob("**/workbench_*.log"), key=lambda p: p.stat().st_mtime) \
        if (root / name).is_dir() else []
    if logs:
        lines += ["", f"the end of its workbench's log ({logs[-1]}):", *logs[-1].read_text(errors="replace")
                  .splitlines()[-40:]]
    (folder / "what_happened.txt").write_text("\n".join(lines))
    return folder


# (journey, the defect restored in its children: scripts/netguard/acceptance_mutations.py, the invariant its failure
# must name): each control runs only after its journey has passed in the same run (its baseline)
CONTROLS = [("intake", "intake_read_as_study", "Draft ready for review"),
            ("intake", "live_view_rebuilt_every_tick", "kept its primary button"),
            ("history", "damaged_record_breaks_listing", "a toy plane, without the tables"),
            ("history", "point_table_mislabelled", "the point table's columns"),
            ("batch_free", "batch_interrupted_hidden", "'interrupted'"),
            ("batch_provider", "live_child_read_as_dead", "follows the live child"),
            ("batch_provider", "reservation_read_as_settled", "'reserved'"),
            # ("promotion_no_eos", "eos_open_ignored", ...): the band's headline rule, not run under 1.0.0's nominal
            # equation-of-state policy (core.certificate.EOS_POLICY), so its defect cannot be seen; with the band, 1.0.2
            ("accounting", "shared_budget_ignored", "which this session shares"),
            ("accounting_uncertain", "reservation_read_as_settled", "('reserved')"),
            ("accounting_lost", "lost_journal_read_as_empty", "the session sent another request"),
            *browser_halo.CONTROLS]


def run_controls(chrome: str, passed: set[str], chosen: list[str], root: Path) -> tuple[int, int, int]:
    """Each mutation control (``CONTROLS``) whose journey was chosen: (detected at its invariant, failed, not
    established: its journey had not passed, so a failure would not be a detection)."""
    detected = failed = missing = 0
    for journey, mutation, invariant in CONTROLS:
        if journey not in chosen:
            continue
        if journey not in passed:
            missing += 1
            print(f"NOT ESTABLISHED control {journey} × {mutation}: the journey did not pass as built")
            continue
        browser_harness.MUTATION = mutation
        try:
            with Chrome.start(chrome, env=child_environment(root / "chrome"), log=root / "chrome.log") as browser:
                why = responsive(browser)
                if why:
                    missing += 1
                    print(f"NOT ESTABLISHED control {journey} × {mutation}: {why}")
                    continue
                try:
                    JOURNEYS[journey](browser, root / f"control_{journey}_{mutation}")
                except NotEstablished as why:
                    missing += 1
                    print(f"NOT ESTABLISHED control {journey} × {mutation}: {why}")
                except Exception as error:                 # noqa: BLE001 - judged against the invariant below
                    if invariant in str(error):
                        detected += 1
                        print(f"CONTROL {journey} × {mutation}: detected at {invariant} "
                              f"({type(error).__name__}: {str(error)[:160]})")
                    else:
                        failed += 1
                        print(f"FAIL control {journey} × {mutation}: failed, but not at {invariant}: "
                              f"{type(error).__name__}: {str(error)[:300]}")
                else:
                    failed += 1
                    print(f"FAIL control {journey} × {mutation}: the journey passed with the defect restored")
                finally:
                    said(browser, f"control {journey} × {mutation}")
        finally:
            browser_harness.MUTATION = ""
            Workbench.stop_all()
    return detected, failed, missing


def load_line() -> str:
    """The machine's load when a journey failed (a deadline missed on a machine running other heavy work says so:
    the full gate of 2026-10-25 met a load average near 100 on 10 cores from another session)."""
    try:
        one, five, fifteen = os.getloadavg()
    except OSError:
        return "load average: not available"
    return f"load average {one:.1f} / {five:.1f} / {fifteen:.1f} (1, 5, 15 min) on {os.cpu_count()} cores"


def responsive(browser, timeout: float = 600.0) -> str:
    """Wait until a fresh Chrome answers a navigation (on a machine saturated by other work a new profile's first
    renderer can take many minutes: the full gate of 2026-10-25, its processes at nice 10 beside another session's ten
    un-niced workers, load average 100–180 on 10 cores); "" once it does, else why not. A browser that does not answer
    is a missing precondition ("not established"), never a journey's failure."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            browser.page().goto("about:blank", ready=False)
            return ""
        except (OSError, RuntimeError):
            time.sleep(5)
        finally:
            said(browser, "Chrome's first navigation")
    return f"Chrome did not answer a navigation within {timeout:.0f} s ({load_line()})"


# every attempt in this gate to make a DevTools connection to a tab again (``browser.Page.reattach``), as said, and
# those of them that made it again, for its summary
REATTACHED: list[str] = []
MADE_AGAIN: list[str] = []


def said(browser, label: str) -> None:
    """Close ``browser``'s pages, each attempt to make a DevTools connection to one of them again
    (``browser.Page.reattach``), made again or not, first printed under ``label`` and counted in the gate's summary
    (``REATTACHED``; ``MADE_AGAIN`` those that made it): after every journey and every mutation control, whatever its
    outcome (passed, failed, detected at its invariant or not established), and after a fresh Chrome's first
    navigation (the auditor's DQ recheck, DR-02, 2026-11-09: a connection made again during a mutation control had been
    printed nowhere and counted nowhere, so a summary naming none did not show that none was made)."""
    for page in browser.pages:
        for line in page.reattached:
            print(f"  {label}: {line}")
        REATTACHED.extend(page.reattached)
        MADE_AGAIN.extend(page.made_again)
        page.close()
    browser.pages.clear()


def reattached_clause() -> str:
    """The summary's account of the attempts in this gate to make a DevTools connection to a tab again: the
    connections made again, and apart from them the attempts that failed, each counted as what it was (the auditor's DR
    recheck, DS-02, 2026-11-09: three attempts that failed had been counted as three connections made again); "" where
    no attempt was made."""
    made, failed = len(MADE_AGAIN), len(REATTACHED) - len(MADE_AGAIN)
    if not made:
        return f"; no DevTools connection to a tab made again: {failed} attempt(s) failed, each said above" \
            if failed else ""
    return f"; {made} DevTools connection(s) to a tab made again" + \
        (f" and {failed} attempt(s) to make one again that failed" if failed else "") + ", each said above"


def run_once(chrome: str, chosen: list[str], root: Path, label: str,
             passed_names: set[str] | None = None) -> tuple[int, int, int]:
    """Every chosen journey in a fresh Chrome (its own profile): (passed, failed, not established); the names of those
    that passed are added to ``passed_names``."""
    passed = failed = missing = 0
    with Chrome.start(chrome, env=child_environment(root / "chrome"), log=root / "chrome.log") as browser:
        why = responsive(browser)
        if why:
            for name in chosen:
                print(f"NOT ESTABLISHED {label}{name}: {why}")
            return 0, 0, len(chosen)
        for name in chosen:
            started = time.monotonic()
            try:
                for line in JOURNEYS[name](browser, root):
                    print(f"  {label}{name}: {line}")
                passed += 1
                if passed_names is not None:
                    passed_names.add(name)
                print(f"PASS {label}{name} ({time.monotonic() - started:.0f} s)")
            except NotEstablished as why:
                missing += 1
                print(f"NOT ESTABLISHED {label}{name}: {why}")
            except Exception as error:                      # each journey reported, the rest still run
                failed += 1
                print(f"FAIL {label}{name}: {type(error).__name__}: {error}")
                print(f"  {load_line()}")
                print(f"  evidence: {_evidence(browser, root, name, error)}")
            finally:
                said(browser, f"{label}{name}")
                left = Workbench.stop_all()
                if left:
                    print(f"  {label}{name}: stopped {len(left)} workbench(es) the journey left running")
    return passed, failed, missing


def main(argv: list[str] | None = None) -> int:
    global TYPED_MODEL
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", default="", help="comma-separated journeys")
    parser.add_argument("--repeat", type=int, default=1, help="run every journey this many times, each in a fresh "
                                                               "Chrome profile with fresh servers")
    parser.add_argument("--keep", action="store_true", help="keep the temporary folders")
    parser.add_argument("--mutation-controls", action="store_true", help="then restore each audited defect in the "
                        "children and require its journey to fail at its invariant")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)      # each journey's lines as they happen, into a log file too
    chrome = find_chrome()
    if not chrome:
        print("release acceptance not established: no Chrome on this machine (set ADROIT_CHROME)")
        return NOT_ESTABLISHED
    import yaml
    from adroit.parameter_space.simplified import model
    TYPED_MODEL = yaml.safe_dump(model("vector", 10, 125, .001, .25).model_dump(mode="json"))
    unknown = [n for n in args.only.split(",") if n and n not in JOURNEYS]
    if unknown:
        parser.error(f"unknown journeys: {', '.join(unknown)} (known: {', '.join(JOURNEYS)})")
    chosen = [n for n in JOURNEYS if not args.only or n in args.only.split(",")]
    print(f"browser: {chrome_version(chrome)}; journeys: {', '.join(chosen)}"
          + (f"; {args.repeat} repetitions" if args.repeat > 1 else ""))
    for name, words in substituted(chosen).items():
        print(f"SUBSTITUTED {name}: {words}")
    root = Path(tempfile.mkdtemp(prefix="adroit-browser-acceptance-", dir=os.environ.get("TMPDIR")))
    browser_harness.PYCACHE = root / "pycache"
    totals, every = [0, 0, 0], None
    for repetition in range(args.repeat):
        label = f"[{repetition + 1}/{args.repeat}] " if args.repeat > 1 else ""
        here = root / f"run{repetition + 1}" if args.repeat > 1 else root
        names: set[str] = set()
        for i, n in enumerate(run_once(chrome, chosen, here, label, names)):
            totals[i] += n
        every = names if every is None else every & names       # passed in every repetition
    passed, failed, missing = totals
    controls = run_controls(chrome, every or set(), chosen, root / "controls") if args.mutation_controls else None
    refusals = sorted(root.rglob("network_refusals.jsonl"))
    outside = [json.loads(line) for path in refusals for line in path.read_text().splitlines()
               if "network" not in path.parts[-2]]
    if outside:                      # a journey's child tried to leave the machine (the guard refused it)
        print(f"network: {len(outside)} connection(s) outside this machine refused during the journeys: "
              + "; ".join(sorted({f"{r['kind']} to {r['target']}" for r in outside}))[:600])
    shown = ""
    if controls is not None:
        detected, wrong, absent = controls
        shown = f"; {detected} of {detected + wrong + absent} mutation controls detect their defect"
        failed, missing = failed + wrong, missing + absent
    print(f"{passed} of {passed + totals[1] + totals[2]} browser journeys pass ({', '.join(chosen)}"
          + (f"; {args.repeat} repetitions, each a fresh Chrome profile and fresh servers" if args.repeat > 1 else "")
          + (f"; {totals[2]} not established" if totals[2] else "") + shown
          + reattached_clause() + ")")
    if args.keep or failed:
        print(f"kept: {root}")
    else:
        shutil.rmtree(root, ignore_errors=True)
    return 1 if failed else NOT_ESTABLISHED if missing else 0


if __name__ == "__main__":
    sys.exit(main())
