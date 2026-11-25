"""A guard on reading saved output back (the owner, 2026-11-03, after the auditor's DA recheck, DB-02; extended by the version
handle's step 3, decided by the owner the same day, with the auditor's guard limit).

A study's saved files (its result, its evidence sidecar, its report, its study record) are read by the resolver
(``evidence.version``, which reads them as one checked transaction) and by the modules that publish them
(``evidence.build``, ``evidence.bindings``, ``orchestrator.studies``), and nowhere else, except at a call site listed
below with its count and why. Two kinds of read are watched:
- a direct read (``read_text``, ``read_bytes``, ``open``) of a path built in the same function from a saved file's name
  (``result.json``, ``report.md``, ``study.json``, ``*.evidence.json``, ``studies.FILE``) or by ``report_path`` or
  ``sidecar_path`` (whether a file is there, ``exists``, reads none of it, and is not watched);
- a call to one of the readers the resolver absorbs (``READERS``), by its name, an alias or its module.

This is a lint, not a proof (the auditor's review of the plan): it does not see a path passed in from elsewhere and read
there, a reader reached by another route than its import, or a consumer that resolves twice and joins the two. What
holds the rule is that consumers take a version (``evidence.version.Version``) or a token, and the acceptance matrix
(``tests/evidence/test_version_matrix.py``); this guard catches a new read that bypasses them."""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SAVED = {"result.json": "result", "report.md": "report", "study.json": "record"}
BUILDS = {"report_path": "report", "sidecar_path": "evidence"}        # functions returning a saved file's path
NAMED = {("studies", "FILE"): "record"}                               # ``studies.FILE``
READS = {"read_text", "read_bytes", "open"}
RESOLVER = {"adroit/evidence/version.py"}
PUBLICATION = {"adroit/evidence/build.py", "adroit/evidence/bindings.py", "adroit/orchestrator/studies.py"}
READERS = {f"adroit.evidence.build.{name}" for name in ("read_saved", "result_bytes", "evidence_held", "evidence_identity",
                                                         "evidence_of", "read", "version_now")} | {
    "adroit.evidence.bindings.read_report", "adroit.evidence.bindings.figure", "adroit.orchestrator.studies.held_record",
    "adroit.orchestrator.studies.load", "adroit.evidence.results.load_result"}

# (module, function, what): (how many, why reading there is sound)
DIRECT: dict[tuple[str, str, str], tuple[int, str]] = {}       # none: every saved file is read by the resolver
CALLS: dict[tuple[str, str, str], tuple[int, str]] = {
    ("adroit/ui/pages.py", "_live_state", "version_now"):
        (2, "the live page's check that the result was not replaced while the run's live cost was read beside the "
            "report of its version (the auditor's CZ recheck, DA-02): a look at the file's version, no bytes read"),
}


def _saved(node: ast.AST, names: dict[str, str]) -> str:
    """"result", "report", "evidence" or "record" where ``node`` builds a saved file's path (or names one built so)."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            if sub.value in SAVED:
                return SAVED[sub.value]
            if sub.value.endswith(".evidence.json"):
                return "evidence"
        if isinstance(sub, ast.Call):
            called = sub.func.attr if isinstance(sub.func, ast.Attribute) else getattr(sub.func, "id", "")
            if called in BUILDS:
                return BUILDS[called]
        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and (sub.value.id, sub.attr) in NAMED:
            return NAMED[sub.value.id, sub.attr]
        if isinstance(sub, ast.Name) and sub.id in names:
            return names[sub.id]
    return ""


def _reads(function: ast.AST) -> list[tuple[int, str]]:
    """Each direct read in ``function`` of a saved file's path built in it: (line, what)."""
    names: dict[str, str] = {}
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and (kind := _saved(node.value, names)):
            names.update({t.id: kind for t in node.targets if isinstance(t, ast.Name)})
    found = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in READS:
            kind = _saved(node.func.value, names)
        elif isinstance(node.func, ast.Name) and node.func.id == "open" and node.args:
            kind = _saved(node.args[0], names)
        else:
            continue
        if kind:
            found.append((node.lineno, kind))
    return found


def _imports(tree: ast.AST, module: str) -> tuple[dict[str, str], dict[str, str]]:
    """(names imported: local name → its full name; modules imported: local name → the module's full name)."""
    names, modules = {}, {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            base = node.module if node.level == 0 else ".".join(module.split(".")[:-node.level] + [node.module])
            for alias in node.names:
                full = f"{base}.{alias.name}"
                if (ROOT / Path(*full.split("."))).with_suffix(".py").exists():
                    modules[alias.asname or alias.name] = full
                else:
                    names[alias.asname or alias.name] = full
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modules[alias.asname or alias.name] = alias.name
    return names, modules


def _calls(function: ast.AST, names: dict[str, str], modules: dict[str, str], module: str) -> list[tuple[int, str]]:
    """Each call in ``function`` to one of ``READERS``: (line, the reader's name)."""
    found = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Name):
            full = names.get(f.id, f"{module}.{f.id}")
        elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in modules:
            full = f"{modules[f.value.id]}.{f.attr}"
        else:
            continue
        if full in READERS:
            found.append((node.lineno, full.rsplit(".", 1)[1]))
    return found


def scan(source: str, module: str) -> tuple[Counter, Counter]:
    """(direct reads, reader calls) in ``source``, each counted by (module, function, what)."""
    tree = ast.parse(source)
    dotted = module.removesuffix(".py").replace("/", ".")
    names, modules = _imports(tree, dotted)
    reads, calls = Counter(), Counter()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            reads.update((module, node.name, kind) for _, kind in _reads(node))
            calls.update((module, node.name, reader) for _, reader in _calls(node, names, modules, dotted))
    return reads, calls


def _package() -> tuple[Counter, Counter]:
    reads, calls = Counter(), Counter()
    for path in sorted((ROOT / "adroit").rglob("*.py")):
        module = path.relative_to(ROOT).as_posix()
        if module in RESOLVER | PUBLICATION:
            continue
        found = scan(path.read_text(), module)
        reads += found[0]
        calls += found[1]
    return reads, calls


def _listed(table: dict) -> Counter:
    return Counter({key: count for key, (count, _) in table.items()})


def test_a_saved_file_is_read_only_by_the_resolver_and_its_writers():
    """Each direct read of a study's saved file outside the resolver and the publication modules is one listed in
    ``DIRECT``, as many times as listed; and each listed one still exists, as many times."""
    reads, _ = _package()
    assert reads == _listed(DIRECT), ("read it through the version (``evidence.version.resolve``), or list why this "
                                      f"read is sound and how many: found {dict(reads)}")


def test_the_readers_the_resolver_absorbs_are_called_only_where_listed():
    """Each call to a reader the resolver absorbs (``READERS``) outside the resolver and the publication modules is
    one listed in ``CALLS``, as many times as listed; and each listed one still exists, as many times."""
    _, calls = _package()
    assert calls == _listed(CALLS), ("take the version, or resolve it, instead; or list why this call is sound and how "
                                     f"many: found {dict(calls)}")


@pytest.mark.parametrize("source, found", [
    ("def native_fit(out):\n    typer.echo((out/'report.md').read_text())\n", "report"),           # DB-02, as it was
    ("def f(folder):\n    path = folder / 'report.md'\n    return path.read_text()\n", "report"),
    ("def f(result):\n    return report_path(result).read_bytes()\n", "report"),
    ("def f(folder):\n    with open(folder / 'report.md') as handle:\n        return handle.read()\n", "report"),
    ("def f(folder):\n    return (folder / 'result.json').read_bytes()\n", "result"),
    ("def f(path):\n    return sidecar_path(path).read_bytes()\n", "evidence"),
    ("def f(folder):\n    return (folder / 'result.evidence.json').read_text()\n", "evidence"),
    ("def f(folder):\n    return (folder / studies.FILE).read_text()\n", "record"),
    ("def f(folder):\n    return json.loads((folder / 'study.json').read_bytes())\n", "record"),
], ids=["DB-02", "by name", "report_path", "open", "result", "sidecar_path", "sidecar by name", "studies.FILE",
        "a record"])
def test_the_guard_sees_a_direct_read(source, found):
    """The guard is not vacuous: each kind of direct read is seen."""
    assert {kind for (_, _, kind) in scan(source, "m.py")[0]} == {found}


@pytest.mark.parametrize("source", [
    "from adroit.evidence.build import read_saved\ndef f(p):\n    return read_saved(p)\n",
    "from adroit.evidence.build import read_saved as r\ndef f(p):\n    return r(p)\n",
    "from adroit.evidence import build\ndef f(p):\n    return build.read_saved(p)\n",
    "from adroit.orchestrator import studies\ndef f(p):\n    return studies.load(p)\n",
    "from adroit.evidence.bindings import read_report\ndef f(p, h):\n    return read_report(p, h)\n",
], ids=["by name", "by alias", "by module", "a record", "a report"])
def test_the_guard_sees_a_reader_called(source):
    """The guard is not vacuous: a reader the resolver absorbs is seen, by its name, an alias or its module."""
    assert sum(scan(source, "adroit/m.py")[1].values()) == 1
