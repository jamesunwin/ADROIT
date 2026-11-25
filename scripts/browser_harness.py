"""The release browser layer's harness (``scripts/browser_acceptance.py`` runs the journeys): the children's
environment (no credential of the person's, the network guard first, the proxy variables at a closed local port), the
workbench served on a free port of this machine, helpers run in a child, forms that must not reload under the
journey, and the network boundary's negative controls (``journey_network``)."""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from browser import closed_port, local_get  # noqa: E402

CREDENTIAL = re.compile(r"API_KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|_AUTH", re.I)
PROVIDER_VARIABLES = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_BASE_URL", "OPENAI_BASE_URL")
GUARD = ROOT / "scripts" / "netguard"
PYCACHE: Path | None = None  # set by the runner: one bytecode cache for the run's children, outside the checkout
MUTATION = ""                # set by the runner for one mutation control: the defect its children restore


class NotEstablished(Exception):
    """A prerequisite of a journey is missing here: the journey is not established, which is never a pass."""


def free_port() -> int:
    return closed_port()


def child_environment(root: Path, keys: dict[str, str] | None = None) -> dict[str, str]:
    """The environment of every child the layer starts (the workbench, its runs, the helpers): no credential of the
    person's (``CREDENTIAL``; each provider key empty), no ``ADROIT_`` setting of theirs, the network guard first on
    ``PYTHONPATH``, the proxy variables at a closed local port (127.0.0.1 exempt), refusals logged under ``root``."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("ADROIT_") and not CREDENTIAL.search(k)
           and k.lower() not in ("http_proxy", "https_proxy", "all_proxy", "no_proxy")
           and k != "PYTHONDONTWRITEBYTECODE"}
    env.update({name: "" for name in PROVIDER_VARIABLES})
    env.update(keys or {})
    stubs = [env[name] for name in ("ANTHROPIC_BASE_URL", "OPENAI_BASE_URL") if env.get(name)]
    if stubs:                        # the layer's own provider stub on this machine, allowed explicitly as a person
        env["ADROIT_ALLOWED_ENDPOINTS"] = ",".join(stubs)   # would allow another endpoint (the security addendum's AL3-26)
    env["PYTHONPATH"] = os.pathsep.join([str(GUARD), *[p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                                                       if p]])
    proxy = f"http://127.0.0.1:{closed_port()}"
    env.update({name: proxy for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy",
                                         "all_proxy")})
    env["NO_PROXY"] = env["no_proxy"] = "127.0.0.1,localhost"
    env["ADROIT_NETWORK_GUARD_LOG"] = str(root / "network_refusals.jsonl")
    env["ADROIT_PROCESS_LOG"] = str(root / "process_starts.jsonl")      # each child's start (the guard writes it)
    env.update(TMPDIR=str(root / "tmp"), MPLCONFIGDIR=str(root / "mpl"), OMP_NUM_THREADS="2",
               ADROIT_EMBEDDINGS="hash", ANONYMIZED_TELEMETRY="False", HF_HUB_OFFLINE="1")
    if MUTATION:
        env["ADROIT_ACCEPTANCE_MUTATION"] = MUTATION
    if PYCACHE is not None:          # compiled once per run, outside the checkout (a fresh venv has no bytecode)
        env["PYTHONPYCACHEPREFIX"] = str(PYCACHE)
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    return env


class Workbench:
    """``adroit workbench`` on a free port of this machine, every writable folder under ``root``. Every server started
    is registered (``LIVE``) until stopped, so that the runner stops whatever a failing journey or control left
    (``stop_all``): no workbench outlives its journey."""
    LIVE: list["Workbench"] = []

    def __init__(self, root: Path, tools: Path | None = None, keys: dict[str, str] | None = None,
                 warm: tuple[str, ...] = (), share_cache: bool = False) -> None:
        self.root, self.port, self.process, self.warm = root, free_port(), None, warm
        root.mkdir(parents=True, exist_ok=True)
        self.env = child_environment(root, keys)
        for name, folder in {"RUNS_DIR": "runs", "PROJECTS_DIR": "projects", "MODEL_LIBRARY_DIR": "model_library",
                             "EXPERIMENTAL_LIBRARY_DIR": "experimental_library", "DATA_DIR": "data"}.items():
            (root / folder).mkdir(parents=True, exist_ok=True)
            self.env[f"ADROIT_{name}"] = str(root / folder)
        if share_cache:              # a real calculation's: the checkout's fetched data and calculation cache, linked
            for name in ("external", "calculation-cache"):
                (ROOT / "data" / name).mkdir(parents=True, exist_ok=True)
                (root / "data" / name).symlink_to(ROOT / "data" / name)
        if tools is not None:
            self.env["ADROIT_TOOLS_DIR"] = str(tools)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self, timeout: float = 240.0) -> "Workbench":
        """Serve, wait until the home page answers (``timeout``, generous for a loaded machine), and render each page
        in ``warm`` once, so that a journey's first page is not its server's first render."""
        self.log = open(self.root / f"workbench_{int(time.time() * 1000)}.log", "w")
        self.process = subprocess.Popen([sys.executable, "-m", "adroit.orchestrator.cli", "workbench", "--port",
                                         str(self.port), "--no-browser"], cwd=ROOT, env=self.env,
                                        stdout=self.log, stderr=subprocess.STDOUT)
        Workbench.LIVE.append(self)
        try:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError(f"the workbench exited ({self.process.returncode}); see {self.log.name}")
                try:
                    local_get(self.url + "/", timeout=30)
                    break
                except OSError:
                    time.sleep(0.5)
            else:
                raise RuntimeError(f"the workbench did not answer within {timeout:.0f} s; see {self.log.name}")
        except BaseException:
            self.stop()
            raise
        for path in self.warm:          # best effort: a page's own error is the journey's to report, in the browser
            try:
                local_get(self.url + path, timeout=180)
            except OSError:
                pass
        return self

    def stop(self, runs: bool = False) -> None:
        """Stop the server; with ``runs``, also every process it started that is still alive (a run's child keeps
        going in its own session otherwise), each identified by the guard's process log and checked to be the very
        process that logged it before it is stopped (``stop_runs``)."""
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=30)
        self.process = None
        if self in Workbench.LIVE:
            Workbench.LIVE.remove(self)
        if runs:
            self.stop_runs()

    @classmethod
    def stop_all(cls) -> list[str]:
        """Stop every server still registered, and its runs; the folders of those that were left running."""
        left = [str(bench.root) for bench in cls.LIVE if bench.process is not None]
        for bench in list(cls.LIVE):
            bench.stop(runs=True)
        return left

    def stop_runs(self) -> list[str]:
        """Stop each process this workbench's children logged (the guard's process log: each records its own pid,
        start time and command line as it starts) that is still that process: the process now at its pid has the
        logged command line and started no later than it logged (``owned``). A pid now held by another process (a pid
        reused since) is left alone, and so is one whose process cannot be read; both are said (returned, and
        printed). The auditor's CR recheck (CS-08, 2026-10-27): a logged command naming this journey and any process alive
        at that pid had been enough to stop it, so cleanup could stop an unrelated process holding a reused pid."""
        import signal
        log = self.root / "process_starts.jsonl"
        left = []
        for line in log.read_text().splitlines() if log.exists() else []:
            entry = json.loads(line)
            pid = entry.get("pid")
            if not isinstance(pid, int) or pid == os.getpid():
                continue
            now = running(pid)
            if now is None:
                continue                        # gone: nothing to stop
            if not owned(entry, *now):
                left.append(f"pid {pid} is not the process this workbench logged there (now: {now[1][:100]!r}); "
                            "not stopped")
                continue
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for note in left:
            print(f"  cleanup: {note}", flush=True)
        return left

    def restart(self) -> None:
        self.stop()
        self.start()


def running(pid: int) -> tuple[float, str] | None:
    """(when the process now at ``pid`` started, to the second, as epoch seconds; its whole command line), or None
    where no process holds it."""
    found = subprocess.run(["ps", "-ww", "-o", "lstart=", "-o", "command=", "-p", str(pid)], capture_output=True,
                           text=True, env={**os.environ, "LC_ALL": "C"})
    parts = found.stdout.strip().split(None, 5)
    if found.returncode or len(parts) < 5:
        return None
    try:
        started = time.mktime(time.strptime(" ".join(parts[:5]), "%a %b %d %H:%M:%S %Y"))
    except ValueError:
        return None
    return started, parts[5] if len(parts) > 5 else ""


def owned(entry: dict, started: float, command: str) -> bool:
    """Whether the process now at a logged pid is the one that logged it (``Workbench.stop_runs``): its command line
    is the logged one, and it started no later than the time it logged (a process holding a reused pid started after
    the logging one ended). An entry without its start time or command line proves nothing, nor one whose time is not
    a time (not finite, or not after the epoch: the auditor's DW recheck, DX-02, 2026-11-12)."""
    logged, argv = entry.get("time"), entry.get("argv")
    if not isinstance(logged, (int, float)) or not math.isfinite(logged) or logged <= 0 \
            or not isinstance(argv, list) or not argv:
        return False
    return " ".join(" ".join(map(str, argv)).split()) == " ".join(command.split()) and started <= logged


def helper(code: str, env: dict) -> str:
    """Run ``code`` in a fresh interpreter of this checkout with the workbench's environment (it writes fixtures);
    its standard output."""
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, timeout=900, capture_output=True,
                          text=True)
    if done.returncode:
        raise RuntimeError(f"a helper failed ({done.returncode}): {done.stderr[-1500:]}")
    return done.stdout


FINAL = ("completed", "failed", "budget_stopped", "cancelled")        # a job's final status, as its badge reads


# a live page as one frame: its whole text, and its outcome's headline (the page's one card: ``pages.show_outcome``)
SNAPSHOT = ("(() => { const card = document.querySelector('.q-card');"
            " return [document.body ? document.body.innerText : '',"
            " (card ? card.innerText : '').trim().split('\\n')[0]]; })()")


def ended(page) -> str:
    """A live page's text once its run has ended and the whole page says so, "" before: its status badge final and
    its outcome's headline no longer "…: running" (``outcomes.unfinished``). Both are read in one script evaluation,
    which no update of the page can interleave, and the text returned is the one judged (the auditor's CR recheck, CS-06,
    2026-10-27: read in two calls, the outcome could change between them, and the text returned still said
    "running")."""
    found = page.evaluate(SNAPSHOT)
    text, headline = found if isinstance(found, list) and len(found) == 2 else ("", "")
    if not (text and any(f"\n{w}\n" in text for w in FINAL)) or headline.endswith(": running"):
        return ""
    return text


def wait_finished(page, timeout: float = 600.0) -> str:
    """Wait until a live page shows that its run ended (``ended``); its text. The status badge is updated in place
    and the outcome rebuilt, and Chrome can draw the badge a frame before the outcome: the auditor's CR recheck
    (2026-10-26) read "completed" beside "Promotion: running" in that frame, and the journey's next assertion failed.
    Waiting on the badge alone had read the page between the two."""
    return page.wait(lambda: ended(page), "the run to end", timeout)


LINKS = "[...document.querySelectorAll('a[href]')].map(a => a.href)"


def study_link(hrefs: list[str], path: str) -> str:
    """The first of ``hrefs`` that opens the study at exactly ``path`` (the ``/study`` page, its parsed ``path``
    parameter equal to it), or "": a link to a study under it, or to one whose path merely begins with it, is not one
    (the auditor's CR recheck, CS-07, 2026-10-27: "a link whose address contains path=signal" had accepted the child's links
    to itself)."""
    from urllib.parse import parse_qs, urlparse
    for href in hrefs:
        found = urlparse(href)
        if found.path == "/study" and parse_qs(found.query).get("path") == [path]:
            return href
    return ""


def study_path(url: str) -> str:
    """The study a ``/study`` page's address opens ("" for any other page)."""
    from urllib.parse import parse_qs, urlparse
    found = urlparse(url)
    return (parse_qs(found.query).get("path") or [""])[0] if found.path == "/study" else ""


def follow(page, path: str, what: str) -> None:
    """Click the page's own link to the study at exactly ``path`` (``study_link``), and wait until that study's page
    is open; the page having no such link fails, naming ``what`` (the navigation the journey establishes: a direct
    address does not show that the page offers it)."""
    href = study_link(page.evaluate(LINKS) or [], path)
    if not href:
        raise AssertionError(f"{what}: the page at {page.url()} has no link to the study {path!r}")
    page.evaluate(f"[...document.querySelectorAll('a[href]')].find(a => a.href === {json.dumps(href)})?.click()")
    page.wait(lambda: study_path(page.url()) == path, f"{what}: the study {path!r} opened")


def submit(page, fill, button: str, arrived, what: str, timeout: float = 240.0) -> list[str]:
    """Fill a form (``fill``), press ``button``, and wait until ``arrived()``. The page must stay the one filled: one
    that reloads meanwhile (NiceGUI reloads a page its server has forgotten, and what was typed is lost) fails the
    journey, its console saying why (``browser.SOCKET_WATCH``); it is never filled and sent again. The auditor's CR recheck
    (2026-10-27) counted such refilled forms as passes assisted by the harness; the cause was the workbench forgetting
    a page whose own thread had been busy for some seconds, which it no longer does (``adroit.ui.app.RECONNECT``).
    Returns what it notes ([]: kept for the journeys' transcripts)."""
    def reached() -> bool:
        try:
            return bool(arrived())
        except (RuntimeError, OSError):
            return False
    document = page.ready()
    fill()
    if page.document() != document:
        raise AssertionError(f"{what}: the page reloaded while its form was filled ({console_tail(page)})")
    page.click_text(button)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if reached():
            return []
        now = page.document()
        if now and now != document and not reached():
            raise AssertionError(f"{what}: the page reloaded after its form was sent ({console_tail(page)})")
        time.sleep(0.25)
    raise TimeoutError(f"waited {timeout:.0f} s for {what}; the page at {page.url()}: {page.text()[:600]!r}; "
                       f"{console_tail(page)}")


def console_tail(page, lines: int = 6) -> str:
    """The page's latest console messages, in one line (``browser.Page.console``)."""
    found = list(getattr(page, "console", []))[-lines:]
    return "its console: " + (" | ".join(found) if found else "nothing")


# --- the network boundary ----------------------------------------------------------------------------------------

NEGATIVE = r'''
import json, socket, urllib.request
out = {"guard": getattr(socket, "ADROIT_NETWORK_GUARD", "")}
def refused(error):
    while error is not None:
        if "ADROIT network guard" in str(error):
            return True
        error = error.__cause__ or error.__context__
    return False
def attempt(name, call, expect="guard"):
    if not out["guard"]:
        out[name] = "not attempted: the guard is not installed"
        return
    try:
        call()
        out[name] = "CONNECTED"
    except Exception as error:
        if expect == "guard":
            out[name] = "refused by the guard" if refused(error) else f"failed otherwise: {type(error).__name__}: {error}"
        else:
            out[name] = ("refused at the closed local proxy" if isinstance(error, (ConnectionRefusedError,)) or
                         "Connection refused" in str(error) else f"failed otherwise: {type(error).__name__}: {error}")
def httpx_direct():
    import httpx
    with httpx.Client(trust_env=False, timeout=3) as client:
        client.get("http://192.0.2.1/")
attempt("a literal external address", lambda: socket.create_connection(("192.0.2.1", 80), timeout=3))
attempt("an external name", lambda: socket.create_connection(("example.invalid", 80), timeout=3))
attempt("a raw socket", lambda: socket.socket().connect(("192.0.2.1", 443)))
attempt("a UDP datagram", lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b"x", ("192.0.2.1", 53)))
attempt("urllib ignoring the proxy", lambda: urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
    "http://192.0.2.1/", timeout=3))
attempt("httpx ignoring the proxy", httpx_direct)
attempt("urllib through the proxy variables", lambda: urllib.request.urlopen("http://192.0.2.1/", timeout=3),
        expect="proxy")
server = socket.socket()
server.bind(("127.0.0.1", 0))
server.listen()
socket.create_connection(server.getsockname(), timeout=3).close()
out["loopback"] = "connected"
print(json.dumps(out))
'''


def journey_network(browser, root: Path) -> list[str]:
    """The boundary, shown (negative controls): in a child with the layer's environment the guard is installed and
    refuses a literal external address, an external name, a raw socket, a datagram and clients that ignore the proxy
    variables (each attempted only once the guard is confirmed, at a reserved documentation address that reaches no
    one); a client honouring the variables meets the closed local proxy; loopback still works. Chrome cannot load an
    external address or name."""
    env = child_environment(root / "network")
    found = json.loads(helper(NEGATIVE, env).strip().splitlines()[-1])
    assert found.pop("guard"), "the network guard is not installed in the children"
    assert found.pop("loopback") == "connected", "loopback connections must work"
    for name, outcome in found.items():
        want = "refused at the closed local proxy" if "proxy variables" in name else "refused by the guard"
        assert outcome == want, f"{name}: {outcome}"
    seen = [f"Python child: {name} {outcome}" for name, outcome in found.items()]
    page = browser.page()
    for url in ("http://192.0.2.1/", "http://example.invalid/"):
        result = page.goto(url, ready=False, error_ok=True)
        assert result.get("errorText"), f"Chrome loaded {url}: its fence does not hold"
        seen.append(f"Chrome: {url} not loaded ({result['errorText']})")
    return seen
