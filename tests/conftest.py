"""Top-level test configuration: NiceGUI's headless User fixture for the workbench (DM15), and the ``needs`` marker.

NiceGUI is a development dependency, so the workbench's tests run with plain
``uv run pytest``; without it they are skipped instead of failing collection.

``@pytest.mark.needs("diamx", ...)`` (B20-08): a test that needs something from the tools folder or a fetched data
release is skipped, with what it needs named, on a machine without it (the Intel runner has neither). Each check is
the package's own (``NEEDS``), so a test skips exactly where its calculation would stop for want of the item. A test
that checks a refusal or a pending outcome when a tool is absent is not marked: it runs everywhere.
"""

import functools
import os
from collections.abc import Callable

# The tests read the command line's plain text: Typer forces a coloured, styled terminal when GITHUB_ACTIONS (or
# FORCE_COLOR, PY_COLORS) is set, and its ANSI codes then split the words and option names the tests look for (the CI
# diagnosis of 2026-11-25: 58 of 63 failures on the Intel runner). Typer's own switch turns that off; it is read when
# Typer is first imported, so it is set here, before anything imports it, and subprocesses inherit it. The command
# line itself, outside the tests, is unchanged.
os.environ.setdefault("_TYPER_FORCE_DISABLE_TERMINAL", "1")
from importlib import import_module
from pathlib import Path

collect_ignore: list[str] = []
try:
    import nicegui  # noqa: F401

    pytest_plugins = ["nicegui.testing.user_plugin"]
except ImportError:  # pragma: no cover - only without the development dependencies
    collect_ignore = ["ui"]


import pytest  # noqa: E402


def _small_values_compared_relatively() -> None:
    """``pytest.approx`` without an absolute tolerance compares an expected value below 10⁻⁹ in size relatively only.
    pytest's default absolute tolerance, 10⁻¹², otherwise makes any two such values equal (``1e-25 ==
    approx(2e-25, rel=0.03)`` is True), and the suite's cross-sections (cm²) and rates (cm³/s) are all far below it:
    such comparisons could not fail (the audit loop's cycle 3: four did, once made relative). A comparison with
    ``abs`` given, or of an expected 0, is pytest's own."""
    from _pytest.python_api import ApproxScalar
    tolerance = ApproxScalar.tolerance

    def relative(self):
        try:
            size = abs(self.expected)
        except TypeError:
            return tolerance.fget(self)
        if self.abs is None and 0 < size < 1e-9:
            return (self.rel if self.rel is not None else self.DEFAULT_RELATIVE_TOLERANCE) * size
        return tolerance.fget(self)
    ApproxScalar.tolerance = property(relative)


_small_values_compared_relatively()


def _fetched(module: str, item: str) -> Callable[[], bool]:
    """Whether the manifest item named by ``module.item`` has been fetched (``external.fetch.locate``)."""
    def check() -> bool:
        from adroit.external import fetch
        return fetch.locate(getattr(import_module(module), item)) is not None
    return check


def _true(module: str, function: str, *args: str) -> Callable[[], bool]:
    """Whether ``module.function(*args)`` says the item is there: True, or an empty reason why not."""
    def check() -> bool:
        answer = getattr(import_module(module), function)(*args)
        return answer is True or (isinstance(answer, str) and answer == "")
    return check


def _darkcast() -> bool:
    from adroit.constraints import searches
    return searches._tool("DarkCast") is not None


def _f_eff() -> bool:
    from adroit.constraints import searches
    return searches._tool("Slatyer f_eff") is not None


def _susy_tables() -> bool:
    from adroit.constraints import lhc
    return lhc.unavailable(*lhc.TABLES) == ""


def _production_tables() -> bool:
    """MadGraph's production tables every search reads (``constraints.production``), by the names the package uses."""
    from adroit.constraints import production
    from adroit.parameter_space import searches
    from adroit.parameter_space.portals import generic_production as generic
    names = [*searches.VECTOR_TABLES.values(), *searches.SCALAR_TABLES.values(), *searches.IDM_TABLES.values(),
             *generic.QUARK_TABLES.values(), *generic.GLUON_TABLES.values(), production.K_TABLE]
    return production.unavailable(*names) == ""


def _revised_xenon() -> bool:
    """Haxton & McElvain's revised density matrices for xenon (``physics.haxton``; the Elastic folder has none for
    ¹²⁴Xe and ¹²⁶Xe): without them ``haxton_2022`` is the shell model's responses, and says so in its record."""
    from adroit.physics import haxton, targets
    return any(haxton.density_matrix_file(i) is not None for i in targets.target("Xe").isotopes)


def _ufo_models() -> bool:
    """The packaged UFO models (``<tools>/ufo``) and MadGraph's Python, which reads them (``constraints.ufo_model``)."""
    from adroit.constraints import maddm
    from adroit.external import fetch
    return maddm.python().exists() and all(fetch.locate(m) is not None for m in ("InertDoublet_UFO", "Pseudoscalar_2HDM"))


NEEDS: dict[str, tuple[str, Callable[[], bool]]] = {
    "diamx": ("DIAMX (the xenon searches)", _fetched("adroit.experiments.xenon", "ITEM")),
    "cresst": ("CRESST-III's data release", _fetched("adroit.experiments.cresst_iii", "ITEM")),
    "cdmslite": ("CDMSlite Run 2's data release", _fetched("adroit.experiments.cdmslite", "ITEM")),
    "optimum_interval": ("Yellin's optimum interval code, built", _true("adroit.statistics.optimum_interval",
                                                                         "available")),
    "solar_model": ("the B16 standard solar model (without it capture-based verdicts are undecided)",
                    _fetched("adroit.constraints.capture", "SOLAR_MODEL")),
    "pppc": ("PPPC's photon spectra", _fetched("adroit.constraints.spectra", "PPPC_ITEM")),
    "pdg_r_ratio": ("the PDG's R-ratio file", _true("adroit.constraints.hadrons", "available")),
    "darkcast": ("DarkCast", _darkcast),
    "f_eff": ("Slatyer's f_eff table (the CMB)", _f_eff),
    "susy_tables": ("the SUSY Working Group's production tables", _susy_tables),
    "production_tables": ("MadGraph's production tables (madgraph-xsec)", _production_tables),
    "madgraph": ("MadGraph and its Python (.venv-mg5)", _true("adroit.constraints.pair_production", "available")),
    "ufo_models": ("the UFO models and MadGraph's Python, which reads them", _ufo_models),
    "directdm": ("DirectDM and its environment (.venv-directdm)", _true("adroit.library.interactions.quark_level",
                                                                         "available")),
    "revised_xenon": ("Haxton & McElvain's revised xenon density matrices (Elastic)", _revised_xenon),
    "poppler": ("Poppler's pdftoppm, which renders PDF pages for preview (an external program; pypdf has none)",
                lambda: __import__("shutil").which("pdftoppm") is not None),
    "eos": ("Saikawa & Shirai's equation-of-state tables (fetched by setup, not shipped: every thermal-relic verdict's "
            "band reads them)", _fetched("adroit.constraints.relic", "EOS_ITEM")),
}


@functools.cache
def _present(name: str) -> bool:
    """Whether ``NEEDS[name]`` is on this machine: checked once a session, with the settings the session started with."""
    return NEEDS[name][1]()


def pytest_collection_modifyitems(config, items) -> None:
    """A name ``needs`` does not know stops the session (a typo must not read as a skip)."""
    unknown = {n for item in items for mark in item.iter_markers("needs") for n in mark.args if n not in NEEDS}
    if unknown:
        raise pytest.UsageError(f"@pytest.mark.needs: unknown {', '.join(sorted(unknown))}; known: {', '.join(NEEDS)}")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item) -> None:
    """Skip a test whose ``needs`` are not all on this machine, naming each one missing; before any fixture runs."""
    missing = [NEEDS[n][0] for mark in item.iter_markers("needs") for n in mark.args if not _present(n)]
    if missing:
        pytest.skip(f"needs {'; '.join(dict.fromkeys(missing))}: not on this machine (adroit setup)")


@pytest.fixture
def resigned(tmp_path, monkeypatch):
    """The records signed before R9's text corrections, as if their verifier had re-signed the corrected content:
    each legacy binding rebound to its record's current payload. For tests about a calculation, which should not
    depend on whether the owner has re-signed yet; tests about signing itself do not use it."""
    import yaml
    from adroit.constraints import database, review_identity
    data = yaml.safe_load(review_identity.LEGACY_BINDINGS.read_text())
    records = {r.id: r for r in database.records()}
    for binding in data["bindings"]:
        if binding["record_id"] in records:
            binding["payload_sha256"] = review_identity.fingerprint(records[binding["record_id"]])
    path = tmp_path / "review_bindings.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    monkeypatch.setattr(review_identity, "LEGACY_BINDINGS", path)
    return path


@pytest.fixture
def awaiting(tmp_path, monkeypatch):
    """Mark records as awaiting a person's verification, whatever records.yaml says (a copy of it without their
    signatures): for tests of the verification gate, which should not depend on which records the owner has signed."""
    import re
    from adroit.constraints import database

    def mark(*ids: str) -> None:
        """Only the signature lines go: the file keeps its layout, which signing (``review.verify``) relies on."""
        text = database.RECORDS.read_text()
        for record_id in ids:
            start = text.index(f"  - id: {record_id}\n")
            end = text.find("\n  - id: ", start + 1)
            end = len(text) if end < 0 else end + 1
            block = re.sub(r"^    (verified_on|verified_by|verification_sha256):[^\n]*\n", "", text[start:end],
                           flags=re.M)
            text = text[:start] + block + text[end:]
        path = tmp_path / "records_awaiting.yaml"
        path.write_text(text)
        monkeypatch.setattr(database, "RECORDS", path)
    return mark


@pytest.fixture
def eos_copy(tmp_path, monkeypatch):
    """Saikawa & Shirai's tables copied into the test's folder and read from there (``relic.eos_folder``), so that a
    test may change a table's bytes, and see a certificate bound to it read stale, without touching the tools folder
    (the auditor's CO recheck, CR-01, 2026-10-26). Use with ``@pytest.mark.needs("eos")``."""
    import shutil
    from adroit.constraints import relic
    source, folder = relic.eos_folder(), tmp_path / "eos-tables"
    folder.mkdir()
    for file, _ in relic.EOS_TABLES.values():
        shutil.copy2(source / file, folder / file)
    monkeypatch.setattr(relic, "eos_folder", lambda: folder)
    return folder


LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0", "::", ""})
CHILD_GUARD = Path(__file__).resolve().parents[1] / "scripts" / "netguard"     # the release layer's process guard


def _own_names() -> frozenset[str]:
    """This machine's own host name, as ``socket.gethostname`` gives it, with and without ".local" (AL2-20: a lookup
    of it had been refused, though it names this machine)."""
    import socket
    name = socket.gethostname()
    base = name.removesuffix(".local")
    return frozenset({name, name.lower(), base, base.lower(), f"{base}.local", f"{base.lower()}.local"})


class _Fence:
    """The tests' network fence (hard rule 4; the audit loop's AL1-16 and AL2-20, 2026-11-14). Installed when this
    file is imported, before any test module is, so a call at import, at collection or in a session fixture is fenced
    as one in a test: a lookup (``getaddrinfo``, by position or keyword, ``gethostbyname``, ``gethostbyname_ex``,
    ``gethostbyaddr``, ``getnameinfo`` but for a numeric answer), a connection (``connect``, ``connect_ex``) or a datagram (``sendto``, ``sendmsg``) to any host
    but this machine is refused as a machine without a network refuses it (``OSError``) and recorded: against the
    running test, which then fails (``_no_network``), else against the session, which then fails
    (``pytest_sessionfinish``). A Python process a test starts imports the release layer's guard
    (``scripts/netguard``, first on ``PYTHONPATH``), which refuses the same and journals it, and the test fails for its
    lines as for its own; that guard then runs the ``sitecustomize`` it hides, an outer guard of the caller's (AL3-17). Not fenced: a process started with ``-I`` or with its own environment, and programs not in
    Python. A test marked ``live`` is exempt."""

    def __init__(self) -> None:
        import os
        import tempfile
        self.open = False
        self.early: list[str] = []
        self.attempts = self.early
        self.local = LOCAL_HOSTS | _own_names()
        self.journal = Path(tempfile.mkdtemp(prefix="adroit-test-fence-")) / "children.jsonl"
        self.journal.touch()
        os.environ["ADROIT_NETWORK_GUARD_LOG"] = str(self.journal)
        os.environ["PYTHONPATH"] = os.pathsep.join(filter(None, [str(CHILD_GUARD), os.environ.get("PYTHONPATH")]))

    def remote(self, host: object) -> bool:
        name = host.decode() if isinstance(host, bytes) else host
        return name is not None and str(name).split("%")[0] not in self.local

    def refuse(self, host: object) -> None:
        import threading
        import traceback
        if self.open:
            return
        stack = "".join(traceback.format_stack(limit=14)[:-3])
        self.attempts.append(f"{host} (thread {threading.current_thread().name}):\n{stack}")
        raise OSError(f"a test reached for {host}: the network is fenced in the tests (tests/conftest.py)")

    def children_since(self, offset: int) -> list[str]:
        """The child processes' refusals journalled after ``offset`` bytes."""
        with self.journal.open() as stream:
            stream.seek(offset)
            return [f"a child process: {line.strip()}" for line in stream if line.strip()]

    def install(self) -> None:
        import socket
        fence = self
        resolve, by_name, by_name_ex, by_address = (socket.getaddrinfo, socket.gethostbyname, socket.gethostbyname_ex,
                                                    socket.gethostbyaddr)
        name_of = socket.getnameinfo
        connect, connect_ex, sendto, sendmsg = (socket.socket.connect, socket.socket.connect_ex, socket.socket.sendto,
                                                socket.socket.sendmsg)

        def getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):      # noqa: A002 - the library's names
            if fence.remote(host):
                fence.refuse(host)
            return resolve(host, port, family, type, proto, flags)

        def one(original):
            def lookup(host):
                if fence.remote(host):
                    fence.refuse(host)
                return original(host)
            return lookup

        def getnameinfo(sockaddr, flags):
            host = sockaddr[0] if isinstance(sockaddr, tuple) and sockaddr else None
            if not flags & socket.NI_NUMERICHOST and fence.remote(host):
                fence.refuse(host)
            return name_of(sockaddr, flags)

        def checked(self, address) -> None:
            if (self.family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple) and address
                    and fence.remote(address[0])):
                fence.refuse(address[0])

        def guarded_connect(self, address):
            checked(self, address)
            return connect(self, address)

        def guarded_connect_ex(self, address):
            checked(self, address)
            return connect_ex(self, address)

        def guarded_sendto(self, data, *args):
            checked(self, args[-1])
            return sendto(self, data, *args)

        def guarded_sendmsg(self, buffers, *args):
            if len(args) >= 3:
                checked(self, args[2])
            return sendmsg(self, buffers, *args)
        socket.getaddrinfo, socket.gethostbyname = getaddrinfo, one(by_name)
        socket.gethostbyname_ex, socket.gethostbyaddr = one(by_name_ex), one(by_address)
        socket.getnameinfo = getnameinfo
        socket.socket.connect, socket.socket.connect_ex = guarded_connect, guarded_connect_ex
        socket.socket.sendto, socket.socket.sendmsg = guarded_sendto, guarded_sendmsg


FENCE = _Fence()
FENCE.install()


@pytest.fixture(autouse=True)
def _no_network(request):
    """The fence for one test (``_Fence``): its attempts, and its child processes', fail it, naming each host and
    where the call came from; the list is the test's own, which a test asking for the fixture by name may inspect. A
    test marked ``live`` is exempt."""
    if request.node.get_closest_marker("live"):
        FENCE.open = True
        try:
            yield []
        finally:
            FENCE.open = False
        return
    attempts: list[str] = []
    outer, FENCE.attempts = FENCE.attempts, attempts
    offset = FENCE.journal.stat().st_size
    try:
        yield attempts
    finally:
        FENCE.attempts = outer
    attempts += FENCE.children_since(offset)
    if attempts:
        pytest.fail("the test reached for the network (refused):\n" + "\n".join(attempts), pytrace=False)


def pytest_sessionfinish(session, exitstatus) -> None:
    """A refusal outside any test (at import, collection or in a session fixture) fails the session."""
    if FENCE.early:
        print("\nthe tests reached for the network outside any test (refused):\n" + "\n".join(FENCE.early))
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture(autouse=True)
def _ledgers_outside_the_repository(tmp_path_factory, monkeypatch):
    """A budgeted client made without a ``ledger_path`` journals under the settings' ``runs/budgets``: in a test,
    a temporary folder, so that no test's ledger sits among the paid runs' (the audit's AG-8, G12)."""
    from adroit.agents import llm
    settings = llm.get_settings().model_copy(update={"runs_dir": tmp_path_factory.getbasetemp() / "runs"})
    monkeypatch.setattr(llm, "get_settings", lambda: settings)


@pytest.fixture(autouse=True)
def _workbench_settings_outside_the_projects(tmp_path_factory, monkeypatch):
    """The workbench's saved choices (``core.workbench_settings``) are read from and written to a temporary file in a
    test, never the researcher's: with the auto-approve setting on there, every spend box would start ticked."""
    from adroit.core import workbench_settings
    path = tmp_path_factory.mktemp("workbench") / workbench_settings.FILE
    monkeypatch.setattr(workbench_settings, "settings_file", lambda: path)


@pytest.fixture(autouse=True)
def _published_halo_unless_asked(monkeypatch):
    """Track 1 in a test uses each experiment's published halo (the reproduction mode, which the existing tests are
    about) unless the test asks for the halo region itself (``tests/parameter_space/test_halo_region.py``): the
    setting's default, the region, is not read from the environment here."""
    from adroit.parameter_space import halo_region
    monkeypatch.setattr(halo_region, "default", lambda: "published")
    monkeypatch.setenv("ADROIT_HALO_REGION", "published")       # and in a run the test launches as a process


@pytest.fixture(autouse=True)
def _eos_band_assessed(request, monkeypatch):
    """``@pytest.mark.eos_band``: the test exercises the equation of state's band, whose assessment ADROIT 1.0 does
    not make (the owner, 2026-11-23: ``core.certificate.EOS_POLICY``, deferred to 1.0.2); it is restored for that
    test alone, so that the deferred machinery keeps its tests."""
    if request.node.get_closest_marker("eos_band") is not None:
        from adroit.core import certificate
        monkeypatch.setattr(certificate, "EOS_BAND_ASSESSED", True)
