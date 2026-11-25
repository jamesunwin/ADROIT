"""Studies (DM14): every run's record, with its parent and children, so that Track 2 can recurse.

A study is one run folder with a ``study.json`` beside its result and report:
- its kind (idea, track1, signal, single_idea, promotion, ...) and title;
- its inputs and the steps it took;
- its cost in dollars (language models only; everything else is $0);
- its outputs (the files it wrote);
- its parent (the study it was promoted from) and its children;
- the SHA-256 of the result it describes, as its writer published it (``result_sha256``).

What a record says of its result (its kind, title, inputs, cost and calculation dates) is of the version its digest
names; its children and its outputs are the folder's navigation, which may change without relabelling the science.
The auditor's version-identity audit, VI-01 (2026-11-03): a record, kept apart from its result, had given a study page, a
download and a verified bundle one result with another publication's title and cost.

A study is named by its folder, and a promotion writes each child's folder
inside its parent's ``children/``, so the tree on disk is the tree of studies.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import Field

from adroit.core.state import StrictModel

FILE = "study.json"
LOCK = ".study.lock"                  # a study's publication lock (``durable.publishing``): its parts and children


class Study(StrictModel):
    """One study's record (``study.json``): its kind, title, inputs, steps, cost, outputs, parent and children."""
    kind: str
    title: str
    folder: str                          # on disk ".", and the parent and children relative to it
    created: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    inputs: dict = Field(default_factory=dict)
    steps: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    outputs: list[str] = Field(default_factory=list)
    parent: str = ""                     # the parent study's folder
    children: list[str] = Field(default_factory=list)
    calculation_started_at: str = ''
    calculation_completed_at: str = ''
    model_references: list[str] = Field(default_factory=list)
    # the SHA-256 of the result this record describes, as its writer published it (VI-01); "" in a record written
    # before, which no reader can tie to a version of its result
    result_sha256: str = Field(default="", exclude_if=lambda v: not v)
    # the workbench run that published it in its folder (its job's ``attempt``), whose cost is this study's; "" where it
    # was published outside one, or before records named it (the auditor's DB/VI recheck, DC-01, 2026-11-03)
    attempt: str = Field(default="", exclude_if=lambda v: not v)


def described(workflow: str, result, digest: str) -> str:
    """The digest of the result the study record beside a saved result describes: for a promotion, the parent result it
    records (``Promotion.parent_sha256``: a promotion's file is written in its parent study's folder, beside that
    study's record), else the result's own (``digest``). The one rule of every reader that attaches the record (the
    export, ``archive._node``, and the references download, ``exports.request``: the auditor's DB/VI recheck, DC-05,
    2026-11-03, the download had checked a promotion's parent record against the promotion)."""
    return getattr(result, "parent_sha256", "") if workflow == "promotion" else digest


def publisher(study: Study) -> str | None:
    """The run a record names as the one that published it, for its cost (``accounting.study_cost``): its ``attempt``
    ("" for none) where it names its result; None for a record written before, read as found (DC-01)."""
    return study.attempt if study.result_sha256 else None


def binding(study: Study, content: bytes | None) -> str:
    """Whether ``study`` describes the result whose bytes, as its reader holds them, are ``content``: "bound" (it names
    their digest), "other" (it names another version's), "unbound" (it names none: written before records named one, so
    it is as found), or "unread" (no result is held to check it against)."""
    import hashlib
    return named(study, hashlib.sha256(content).hexdigest() if content is not None else "")


def named(study: Study, digest: str) -> str:
    """``binding`` against a result's digest ("": none held)."""
    if not study.result_sha256:
        return "unbound"
    if not digest:
        return "unread"
    return "bound" if digest == study.result_sha256 else "other"


def held_record(folder: Path, digest: str) -> tuple[bytes, str, Study | None]:
    """A folder's study record read once (its bytes, as an export attaches them), its binding to the result whose digest
    its reader holds (``named``), and the record: "absent" without one, "damaged" where it is not a study record."""
    try:
        data = (Path(folder) / FILE).read_bytes()
    except FileNotFoundError:
        return b"", "absent", None
    try:
        record = Study.model_validate_json(data)
    except ValueError:
        return data, "damaged", None
    return data, named(record, digest), record


def load(folder: Path) -> Study:
    """A folder's study, with its folder, parent and children as absolute paths."""
    return parsed(folder, (Path(folder).resolve() / FILE).read_bytes())


def parsed(folder: Path, data: bytes) -> Study:
    """A study record's bytes, as its reader holds them, as ``load`` reads them (``ValueError`` where they are not
    one)."""
    folder = Path(folder).resolve()
    s = Study.model_validate_json(data)
    absolute = lambda p: str((folder / p).resolve()) if p else ""  # noqa: E731
    return s.model_copy(update={"folder": str(folder), "parent": absolute(s.parent),
                                "children": [absolute(c) for c in s.children]})


NAVIGATION = ("children", "outputs")      # a record's navigation: it may change without relabelling the science


def header(data: bytes) -> str:
    """The identity of a study record's scientific header, as its bytes are held: the SHA-256 of its fields but its
    navigation (``NAVIGATION``), canonically written; of its bytes, prefixed "damaged:", where they are not a record.
    A title, cost or date changed changes it; a child added does not (the version-handle plan: the auditor's review)."""
    import hashlib
    import json
    try:
        fields = Study.model_validate_json(data).model_dump(mode="json")
    except ValueError:
        return "damaged:" + hashlib.sha256(data).hexdigest()
    kept = {k: v for k, v in fields.items() if k not in NAVIGATION}
    return hashlib.sha256(json.dumps(kept, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _on_disk(study: Study) -> str:
    """A record as ``save`` writes it: the parent and children relative to the study's folder."""
    folder = Path(study.folder).resolve()
    relative = lambda p: os.path.relpath(p, folder) if p else ""  # noqa: E731
    return study.model_copy(update={"folder": ".", "parent": relative(study.parent),
                                    "children": [relative(c) for c in study.children]}).model_dump_json(indent=1)


def save(study: Study, claim=None) -> Path:
    """Written with the parent and children relative to the study's folder, so a tree can move; under the folder's
    publication lock (``durable.publishing``: ``claim``, its writer's own, held already), so that no other publication's
    part is written between a publication's parts (the auditor's DD recheck, DE-02, 2026-11-05)."""
    from adroit.core.durable import publishing, write_atomic
    folder = Path(study.folder).resolve()
    with publishing(folder, claim):
        return write_atomic(folder / FILE, _on_disk(study))       # whole, synced, published at once


def identity(study: Study) -> str:
    """The identity of a record as ``save`` writes it (``header``): a version's record identity (``evidence.version``),
    known to its writer without reading the file again (the auditor's version-handle audit, DD-01)."""
    return header(_on_disk(study).encode())


def record(folder: Path, kind: str, title: str, inputs: dict | None = None, steps: list[str] | None = None,
           cost_usd: float = 0.0, parent: Path | None = None,calculation_started_at: str='',
           calculation_completed_at: str='',model_references: list[str] | None=None,
           result_sha256: str = "", claim=None) -> Study:
    """Write a folder's study (its outputs are the files in it), and add it to its parent's children, the parent's
    record read, changed and written under its publication lock (``durable.publishing``), so that two children
    recorded at once are both kept (the consolidation plan's M3: publishing whole does not prevent a lost update).
    ``result_sha256``: the digest of the result it describes, of the bytes its writer published, never of the file read
    again (VI-01). In a workbench run's own folder, it names that run's attempt (``preflight.job_attempt``; DC-01).
    ``claim``: its writer's publication of the folder, held already (DE-02)."""
    from adroit.orchestrator.preflight import job_attempt
    folder = Path(folder).resolve()
    outputs = sorted(str(p.relative_to(folder)) for p in folder.iterdir()
                     if p.is_file() and p.name not in (FILE, LOCK))
    children = load(folder).children if (folder / FILE).exists() else []
    study = Study(kind=kind, title=title, folder=str(folder), inputs=inputs or {}, steps=steps or [],
                  cost_usd=cost_usd, outputs=outputs, parent=str(Path(parent).resolve()) if parent else "",
                  children=children,calculation_started_at=calculation_started_at,
                  calculation_completed_at=calculation_completed_at,model_references=model_references or [],
                  result_sha256=result_sha256, attempt=job_attempt(folder) if result_sha256 else "")
    save(study, claim)
    if parent is not None and (Path(parent) / FILE).exists():
        from adroit.core.durable import publishing
        with publishing(Path(parent)) as held:
            mother = load(Path(parent))
            if str(folder) not in mother.children:
                save(mother.model_copy(update={"children": [*mother.children, str(folder)]}), held)
    return study


def forget_child(parent: Path, child: Path) -> None:
    """Remove a deleted study from its parent's children (``ui.deletion``), the parent's record read, changed and
    written under its publication lock, as ``record`` adds one; navigation only, so the parent's identity is unchanged
    (``header``). Nothing where the parent has no record."""
    from adroit.core.durable import publishing
    parent, child = Path(parent).resolve(), Path(child).resolve()
    if not (parent / FILE).exists():
        return
    with publishing(parent) as held:
        mother = load(parent)
        children = [c for c in mother.children if Path(c).resolve() != child]
        if children != mother.children:
            save(mother.model_copy(update={"children": children}), held)


def _when(study: Study) -> datetime:
    """A study's creation time, for ordering (an unreadable one sorts as the oldest)."""
    try:
        value = datetime.fromisoformat(study.created)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def tree(root: Path) -> list[tuple[int, Study]]:
    """Every study under ``root``, depth first from those without a parent among them, the newest of those first and
    each one's children in the order they were made: (depth, study). (The workflow audit's WA-07, 2026-10-24: the
    Studies page said "newest first" and showed the oldest first.) A record that cannot be read is left out
    (``unreadable`` names it), and the rest are listed; each study once, whatever its links say (``inconsistent``
    names links that loop or disagree)."""
    return _graph(_scan(root)[0])[0]


def unreadable(root: Path) -> list[tuple[Path, str]]:
    """The study records under ``root`` that cannot be read, each with why (``tree`` leaves them out; the combined
    audit's V1-04, 2026-10-24: one ``study.json`` holding ``{}`` had stopped the Studies page and the Signal best fits
    form, which lists the saved studies)."""
    return _scan(root)[1]


def unoffered(root: Path) -> str:
    """For a picker of saved studies (Signal best fits, the Records page's study selector, reanalysis, a model's
    analyses, studies to revisit): how many study records it could not read and so does not offer, and where they are
    named; "" if none (the consolidation plan's M3: they had been left out without a word)."""
    bad = unreadable(root)
    if not bad:
        return ""
    return (f"{len(bad)} saved stud{'y' if len(bad) == 1 else 'ies'} could not be read and "
            f"{'is' if len(bad) == 1 else 'are'} not offered here; the Studies page names "
            f"{'it' if len(bad) == 1 else 'them'}")


def inconsistent(root: Path) -> list[tuple[Path, str]]:
    """The study records under ``root`` whose links to parents and children loop or disagree, each with what is wrong.
    Each such study is still listed once by ``tree``. The consistency audit's CA-08 (2026-10-24): a study naming
    itself as its child made the history recurse without end (a RecursionError), and two studies each the other's
    parent vanished from it, named nowhere: each record was valid alone, and only the graph was damaged."""
    return _graph(_scan(root)[0])[1]


def _graph(found: dict[str, Study]) -> tuple[list[tuple[int, Study]], list[tuple[Path, str]]]:
    """(``tree``'s listing, ``inconsistent``'s problems) of the readable studies ``found``: depth first from the
    studies whose parent is not among them, each visited once; a child link to a study already listed, or to one
    whose record names another parent, is named, not followed; a study reached by no walk (its chain of parents
    loops, or its parent does not list it) is listed at depth 0 and named."""
    out: list[tuple[int, Study]] = []
    problems: dict[str, str] = {}
    seen: set[str] = set()

    def walk(key: str, depth: int) -> None:
        seen.add(key)
        out.append((depth, found[key]))
        for child in found[key].children:
            if child not in found:
                continue
            if child in seen:
                problems.setdefault(key, f"names {Path(child).name} as a child, which is already listed "
                                         + ("(itself)" if child == key else "above it or elsewhere"))
            elif found[child].parent != key:
                problems.setdefault(key, f"names {Path(child).name} as a child, whose record names another parent")
            else:
                walk(child, depth + 1)

    newest = sorted(found, key=lambda k: _when(found[k]), reverse=True)
    for key in newest:
        if found[key].parent not in found:
            walk(key, 0)
    for key in newest:                          # every study the walks missed: listed, and why named
        if key not in seen:
            problems.setdefault(key, _unreached(found, key))
            walk(key, 0)
    return out, [(Path(key) / FILE, why) for key, why in problems.items()]


def _unreached(found: dict[str, Study], key: str) -> str:
    """Why no walk from a parentless study reached ``key`` (``_graph``): its chain of parents loops, or its parent
    does not list it as a child."""
    chain, at = [key], found[key].parent
    while at in found and at not in chain:
        chain.append(at)
        at = found[at].parent
    if at in chain:
        return f"its chain of parents loops (through {Path(at).name}); listed without its parent"
    return f"its parent, {Path(found[key].parent).name}, does not list it as a child; listed without its parent"


def _scan(root: Path) -> tuple[dict[str, Study], list[tuple[Path, str]]]:
    """(every readable study under ``root`` by its folder, the unreadable records with why: ``durable.read_each``)."""
    from adroit.core.durable import read_each
    studies, bad = read_each(sorted(Path(root).rglob(FILE)), lambda path: (path, load(path.parent)))
    return ({str(path.parent.resolve()): study for path, study in studies},
            [(Path(d.path), d.why) for d in bad])


def total_cost(root: Path) -> float:
    """The dollars spent by every study under ``root``."""
    return sum(s.cost_usd for _, s in tree(root))
