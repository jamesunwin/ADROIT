"""One resolved version of a saved study: the shared version handle (the version handle plan; decided by the
owner on 2026-11-03, after the auditor's DB/VI recheck).

The rule: resolve a version once, then use that exact version for everything displayed, downloaded, exported or
continued. A study's saved output is a state, and every observable a page, a command or an action reports is evaluated
in that one state: ``resolve`` prepares it from the folder once, and its consumers are handed it, never the folder to
read again. Each of the auditor's rechecks from CR to DC had found a boundary where a second read joined a part of one
publication to a part of another; this one object holds the identities each repair had passed by hand.

A ``Version`` holds each part's bytes as read:
- the result, and what its bytes give on request: its JSON, its typed result and its headline, each a fresh copy;
- its evidence: the sidecar's bytes, checked against the result's (``build.saved_of``); without one, the evidence is
  rebuilt from the result and is said to be (``legacy``);
- its study record: what it says of the result (title, cost, dates, the run that published it) is the result's only
  where the record names it; beside a promotion's record, the parent result the promotion records
  (``studies.described``);
- with ``presentation``, its report and each figure the report or the result names, checked against the report's
  binding (``evidence.bindings``);
- its graph's edges: a promotion's children and its parent, each with the digest its record keeps (``follow``).

A part it does not hold is in an explicit state ("absent", "unreadable", "unread", "legacy", "unbound", "other",
"damaged", "interrupted"), never an omitted check.

**An interrupted publication** (its output's mark, ``build.mark_path``, read with the parts: ``interrupted``): its report and
its study record read as "interrupted", never as the result's, whatever digest they name, since they may be an earlier
publication's beside a later one's result and evidence (the auditor's portability audit, IC-01, 2026-11-10: with the result
bytes the same, the earlier report and record had read as bound).

Resolution is a checked transaction. Each file is read once, through one descriptor, as one version of it
(``core.file_reads``); then each is looked at again, and one replaced, appeared or gone meanwhile makes the whole read
again, up to ``file_reads.TRIES`` times, then ``Unsettled``: a version never holds half of each. What it derives (its
checks, its typed views) is derived from the bytes it holds, never from the folder.

A ``Token`` names a version for later: a link, a command's argument, a draft. ``resolve`` of a token returns the version
only where each identity the token names still holds, else ``Changed``, naming the part. A token naming nothing but its
locator (a fresh selection; a link to a study as it is saved now) resolves the version saved now, once.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any, NamedTuple

from adroit.core import file_reads

NONE = "none"           # a part's identity where there is no file: no sidecar (build.NO_EVIDENCE), no report
                        # (bindings.NO_REPORT), no study record, no result
UNREAD = "unread"       # a part's identity where this resolution did not read it
UNREADABLE = "unreadable"   # where its file is there and cannot be read
PARTS = ("result", "evidence", "presentation", "record")
WHAT = {"result": "study's result", "evidence": "result's evidence", "presentation": "result's report",
        "record": "study's record"}
QUERY = {"result": "sha256", "evidence": "evidence", "presentation": "report", "record": "record"}


class Changed(ValueError):
    """A version is not the one a token names: its ``part`` holds another (``found``: its identity now)."""

    def __init__(self, part: str, expected: str, found: str):
        super().__init__(f"the {WHAT[part]} has changed since it was read ({_short(expected)} then, {_short(found)} "
                         "now)")
        self.part, self.expected, self.found = part, expected, found


def _short(identity: str) -> str:
    return identity[:12] + "…" if len(identity) == 64 else identity or "none"


class Unsettled(OSError):
    """A study's files changed each time they were read together (``file_reads.TRIES`` attempts)."""


@dataclass(frozen=True)
class _Read:
    """One file as read: its bytes (None where there is no file, or it was not read: ``why``), and its version then
    (``file_reads.identity``; None where there was no file)."""
    path: str
    data: bytes | None
    version: tuple | None
    why: str = ""

    @property
    def identity(self) -> str:
        if self.data is not None:
            return hashlib.sha256(self.data).hexdigest()
        if self.version is None:
            return NONE
        return UNREAD if self.why.startswith("larger") else UNREADABLE


def _read(path: Path, limit: int | None = None) -> _Read:
    """``path`` read once, as one version of the file; one larger than ``limit`` bytes is not read."""
    where = str(path)
    try:
        version, data = file_reads.consistent(where, lambda *v: (
            v, None if limit is not None and v[2] > limit else file_reads.read(where, v)))
    except FileNotFoundError:
        return _Read(where, None, None)
    except OSError as error:
        from adroit.core.durable import reason
        return _Read(where, None, _now(where), f"cannot be read ({reason(error)})")
    if data is None:
        return _Read(where, None, version, f"larger than {limit // 1_000_000} MB, not read")
    return _Read(where, data, version)


def _now(where: str) -> tuple | None:
    """The version of a file now; None where there is none (or it cannot be looked at)."""
    try:
        return file_reads.identity(os.stat(where))
    except OSError:
        return None


@dataclass(frozen=True)
class Token:
    """A version named for later (a link, a command's argument, a draft): its result file (``path``, a locator
    only) and the identity of each part it was shown or acted on with (``Version.identity``; "" names nothing, and
    ``resolve`` does not check that part)."""
    path: str
    result: str = ""
    evidence: str = ""
    presentation: str = ""
    record: str = ""

    def named(self) -> dict[str, str]:
        """The parts the token names, with their identities."""
        return {part: getattr(self, part) for part in PARTS if getattr(self, part)}

    def query(self, root: Path, key: str = "path") -> dict[str, str]:
        """The token as a link's parameters: its locator relative to ``root`` (``key``: a study's folder, for its
        ``result.json``; else the result file), and each identity it names (``sha256``, ``evidence``, ``report``,
        ``record``)."""
        path = Path(self.path)
        where = path.parent if path.name == "result.json" else path
        return {key: str(where.resolve().relative_to(Path(root).resolve())),
                **{QUERY[part]: value for part, value in self.named().items()}}

    @classmethod
    def from_query(cls, root: Path, params: dict, key: str = "path") -> Token:
        """A token from a link's parameters (``query``); ``ValueError`` where its locator leaves ``root``, or a file
        of the study it names does (a link to its result, its evidence, its report, its record or a figure that is a
        symbolic link out of the runs directory: the auditor's version-handle audit, an observation made a case)."""
        root = Path(root).resolve()
        where = (root / str(params.get(key, ""))).resolve()
        if where != root and root not in where.parents:
            raise ValueError("outside the runs directory")
        result = _result_file(where)
        for path in _study_files(result):
            target = path.resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"outside the runs directory ({path.name} links out of it)")
        return cls(str(result), **{part: str(params.get(QUERY[part]) or "") for part in PARTS})

    def text(self) -> str:
        """The token as one line (a command's argument, a draft's record)."""
        return json.dumps({"path": self.path, **self.named()}, sort_keys=True, separators=(",", ":"))

    @classmethod
    def parse(cls, text: str) -> Token:
        """A token from its line (``text``); ``ValueError`` where it is not one."""
        held = json.loads(text)
        if not isinstance(held, dict) or not isinstance(held.get("path"), str) or set(held) - {"path", *PARTS} \
                or not all(isinstance(held.get(p, ""), str) for p in PARTS):
            raise ValueError("not a version token")
        return cls(**held)


def _study_files(result: Path) -> list[Path]:
    """The files beside a result that are symbolic links (what a link's locator could reach outside its folder)."""
    try:
        return [p for p in [result, *result.parent.iterdir()] if p.is_symlink()]
    except OSError:
        return []


def _result_file(where: Path) -> Path:
    """A locator as a result file: a study's folder names its ``result.json``."""
    return where / "result.json" if where.is_dir() or (not where.exists() and where.suffix != ".json") else where


@dataclass(frozen=True, eq=False)
class Version:
    """A study's saved output as one checked read (``resolve``): the bytes of each part, and what they give."""
    path: Path                      # the result file: a locator, never reread for this version
    _result: _Read
    _evidence: _Read | None         # None: not read (``resolve(evidence=False)``)
    _record: _Read
    _report: _Read | None = None    # None: not read (no ``presentation``)
    _figures: tuple[tuple[str, _Read], ...] = ()
    _mark: _Read | None = None      # its output's mark (``build.mark_path``), read with it (IC-01, HE-01)

    @property
    def interrupted(self) -> bool:
        """Whether its output's last publication was interrupted (its mark there when it was read): its report
        and study record may be of an earlier publication (module docstring)."""
        return self._mark is not None and self._mark.version is not None

    @property
    def folder(self) -> Path:
        """The study's folder: a locator."""
        return self.path.parent

    # --- its identities ---------------------------------------------------------------------------------------------

    def identity(self, part: str) -> str:
        """The identity of a part as read: the SHA-256 of its bytes (the record's: of its scientific header,
        ``studies.header``); ``NONE`` where there is no file; ``UNREADABLE`` where it could not be read; ``UNREAD``
        where this resolution did not read it."""
        if part == "result":
            return self._result.identity
        if part == "evidence":
            return UNREAD if self._evidence is None else self._evidence.identity
        if part == "presentation":
            return UNREAD if self._report is None else self._report.identity
        if part == "record":
            from adroit.orchestrator.studies import header
            return header(self._record.data) if self._record.data is not None else self._record.identity
        raise ValueError(f"no such part of a version: {part}")

    @property
    def result_sha256(self) -> str:
        """The digest of the result's bytes; "" where there are none."""
        return hashlib.sha256(self._result.data).hexdigest() if self._result.data is not None else ""

    def token(self) -> Token:
        """This version named for later: each part it read, by its identity (a part it did not read, by none)."""
        named = {part: self.identity(part) for part in PARTS}
        return Token(str(self.path), **{part: value if value != UNREAD else "" for part, value in named.items()})

    # --- the result -------------------------------------------------------------------------------------------------

    @property
    def content(self) -> bytes | None:
        """The result's bytes as read (None where there are none)."""
        return self._result.data

    @property
    def result_state(self) -> str:
        """"held", "absent", "unreadable" (there, and it cannot be read) or "unread" (larger than the list reads)."""
        if self._result.data is not None:
            return "held"
        return {NONE: "absent", UNREAD: "unread"}.get(self._result.identity, "unreadable")

    @property
    def kind(self) -> str:
        """The study's kind as its record holds it ("" without a readable one)."""
        study = self._study
        return study.kind if study is not None else ""

    def snapshot(self):
        """The result as ``study_headline.snapshot`` reads it (its JSON, a fresh copy; its damage), as the study's kind
        (``kind``)."""
        from adroit.orchestrator.study_headline import Snapshot, snapshot_of
        if self._result.data is None:
            if self._result.version is None:
                return Snapshot(kind=self.kind)
            why = self._result.why
            return Snapshot(kind=self.kind, damage=f"its result is {why.replace(', not read', ' and is not read')} "
                            "for a badge" if why.startswith("larger") else f"its result {why}")
        return snapshot_of(self._result.data, self.kind, self._result.version)

    def headline(self):
        """The result's headline (``study_headline.headline_from``)."""
        from adroit.orchestrator.study_headline import headline_from
        return headline_from(self.snapshot())

    def data(self) -> Any:
        """The result's JSON, a fresh copy; ``ValueError`` where its bytes are not JSON."""
        self._require_result()
        return json.loads(self._result.data)

    @cached_property
    def _saved(self):
        """``build.saved_of`` of the result's bytes and the sidecar's, as read: the snapshot, or the error."""
        from adroit.evidence.build import saved_of, sidecar_path
        if self._evidence.data is None and self._evidence.version is not None:     # there, and unreadable: not absent
            return OSError(f"{sidecar_path(self.path).name} {self._evidence.why}")
        try:
            return saved_of(self.path, self._result.data, self._evidence.data)
        except (ValueError, TypeError) as error:
            return error

    def saved(self):
        """The result and its evidence as ``build.read_saved`` gives them (a fresh copy), checked against each other;
        ``FileNotFoundError`` without a result, ``OSError`` where it cannot be read, ``ValueError`` naming a mismatch or
        damage."""
        self._require_result()
        if self._evidence is None:
            raise ValueError(f"{self.path}: its evidence was not read with it")
        found = self._saved
        if isinstance(found, Exception):
            raise found.with_traceback(None)
        return found._replace(data=copy.deepcopy(found.data), result=found.result.model_copy(deep=True),
                              envelope=found.envelope.model_copy(deep=True))

    def typed(self):
        """The typed result, a fresh copy (``saved``)."""
        return self.saved().result

    def envelope(self):
        """The evidence, a fresh copy (``saved``)."""
        return self.saved().envelope

    @property
    def workflow(self) -> str:
        """The result's workflow, as its checked evidence names it; "" where it cannot be checked."""
        found = self._saved if self._evidence is not None and self._result.data is not None else None
        return found.workflow if found is not None and not isinstance(found, Exception) else ""

    @property
    def evidence_state(self) -> str:
        """"bound" (its sidecar is of these bytes, every check passing), "legacy" (it has none: rebuilt from the
        result where it can be, said so), "other" (its sidecar names another version), "damaged" (it, or the result it
        checks, cannot be read as one: ``evidence_why``), or "unread"."""
        if self._evidence is None or self._result.data is None:
            return "unread"
        if self._evidence.data is None:
            return "legacy" if self._evidence.version is None else "damaged"
        found = self._saved
        if not isinstance(found, Exception):
            return "bound"
        return "other" if str(found) == "evidence/result content mismatch" else "damaged"

    @property
    def evidence_why(self) -> str:
        """Why the evidence is "other" or "damaged" ("" where it is neither)."""
        if self.evidence_state not in ("other", "damaged"):
            return ""
        return self._evidence.why or str(self._saved)

    def held_evidence(self):
        """The evidence as a page shows it beside the result (``build.HeldEvidence``, as ``build.evidence_held`` gave
        it): its identity and envelope where the sidecar read names this result's bytes (what it holds is shown beside
        the result without the snapshot's other checks, ``saved``); ``build.NO_EVIDENCE`` and none without a sidecar;
        "" and none where it is another version's, cannot be read, or was not read, so nothing is shown of it."""
        from adroit.core.evidence import EvidenceEnvelope
        from adroit.evidence.build import NO_EVIDENCE, HeldEvidence
        if self._evidence is None or self._result.data is None:
            return HeldEvidence("", None)
        if self._evidence.data is None:
            return HeldEvidence(NO_EVIDENCE if self._evidence.version is None else "", None)
        try:
            envelope = EvidenceEnvelope.model_validate_json(self._evidence.data)
        except ValueError:
            return HeldEvidence("", None)
        if envelope.result_sha256 != self.result_sha256:
            return HeldEvidence("", None)
        return HeldEvidence(self.identity("evidence"), envelope)

    def dates(self) -> tuple[str, str]:
        """When the result was calculated, as its evidence records it (start, completion; "" where not recorded),
        distinct from when its report was written."""
        try:
            context = self.saved().envelope.context
        except (OSError, ValueError):
            return "", ""
        return context.calculation_started_at, context.calculation_completed_at

    def _require_result(self) -> None:
        if self._result.data is None:
            if self._result.version is None:
                raise FileNotFoundError(f"{self.path}: no saved result")
            raise OSError(f"{self.path} {self._result.why}")

    # --- its study record -------------------------------------------------------------------------------------------

    @cached_property
    def _study(self):
        from adroit.orchestrator import studies
        if self._record.data is None:
            return None
        try:
            return studies.parsed(self.folder, self._record.data)
        except ValueError:
            return None

    def study(self):
        """The study record as read (``studies.load``'s form, a fresh copy); None where there is none, or it is not a
        record. What it says of the result is the result's only where ``record_state`` is "bound" (as found where
        "unbound")."""
        study = self._study
        return study.model_copy(deep=True) if study is not None else None

    @property
    def record_bytes(self) -> bytes | None:
        """The study record's bytes as read (an export attaches them)."""
        return self._record.data

    @property
    def described(self) -> str:
        """The digest of the result the record beside this one describes (``studies.described``): a promotion's parent
        result, else this result's; "" where it cannot be known."""
        if self._result.data is None:
            return ""
        from adroit.orchestrator.studies import described
        if self.path.name == "result.json":
            return self.result_sha256
        try:
            found = self.saved() if self._evidence is not None else None
        except (OSError, ValueError):
            found = None
        if found is None:
            return ""
        return described(found.workflow, found.result, self.result_sha256)

    @property
    def record_state(self) -> str:
        """"bound" (the record names the result it describes), "unbound" (it names none: written before, as found),
        "other" (it names another version: what it says of the result is not this result's), "interrupted" (the
        folder's last publication was interrupted: ``interrupted``), "unread" (no result is held to check it against),
        "absent", "unreadable", or "damaged" (not a study record)."""
        from adroit.orchestrator.studies import named
        if self._record.data is None:
            return "absent" if self._record.version is None else "unreadable"
        study = self._study
        if study is None:
            return "damaged"
        return "interrupted" if self.interrupted else named(study, self.described)

    def publisher(self) -> str | None:
        """The run the record names as the one that published it, for its cost (``studies.publisher``); None for a
        record naming no result (as found), or none held."""
        from adroit.orchestrator.studies import publisher
        study = self._study
        return publisher(study) if study is not None else None

    # --- its presentation -------------------------------------------------------------------------------------------

    def report(self):
        """The report as read with the result (``bindings.Report``, a fresh copy): "bound", "other", "unbound",
        "interrupted" (``interrupted``), "absent" or "unreadable"; ``ValueError`` where it was not read (no
        ``presentation``)."""
        from adroit.evidence.bindings import Report, report_of
        if self._report is None:
            raise ValueError(f"{self.path}: its report was not read with it")
        if self._report.data is None and self._report.version is not None:
            return Report("unreadable", "", None)
        found = report_of(self._report.data, self.result_sha256 or None)
        return found._replace(state="interrupted") if self.interrupted and found.state != "absent" else found

    def figure(self, name: str) -> bytes | None:
        """A figure's bytes as read with its report, where the report is bound to this result and names exactly these
        bytes (``bindings.figure_of``); else None."""
        from adroit.evidence.bindings import figure_of
        return figure_of(dict(self._figures).get(name, _Read("", None, None)).data, name, self.report())

    def figure_as_found(self, name: str) -> bytes | None:
        """A figure's bytes as read with the report, unchecked: for a report recording no binding (written before),
        shown or exported as found, saying so. None where there are none."""
        return dict(self._figures).get(name, _Read("", None, None)).data

    @property
    def figures(self) -> tuple[str, ...]:
        """The figures read with the report: those it embeds or binds, and the result's ``plots``."""
        return tuple(name for name, _ in self._figures)

    # --- its graph --------------------------------------------------------------------------------------------------

    def edges(self) -> list:
        """A promotion's edges (``archive.promotion_edges``: its children, then its parent, each with the digest its
        record keeps); [] for any other result, or one that cannot be read."""
        from adroit.evidence.archive import promotion_edges
        try:
            found = self.saved()
        except (OSError, ValueError):
            return []
        return promotion_edges(self.path, found.result) if found.workflow == "promotion" else []

    # --- the transaction --------------------------------------------------------------------------------------------

    def _reads(self) -> list[_Read]:
        return [r for r in (self._result, self._evidence, self._record, self._report, self._mark) if r is not None] + \
            [r for _, r in self._figures]

    def _settled(self) -> bool:
        """Whether each file read is, now, the version read: none replaced, appeared or gone meanwhile."""
        return all(_now(r.path) == r.version for r in self._reads())


def resolve(where: Token | Path | str, *, presentation: bool = False, evidence: bool = True,
            limit: int | None = None) -> Version:
    """The version of a saved study, read once as one checked transaction: ``where`` names its result file or its
    folder (a fresh selection: the version saved now), or a ``Token`` (its version: ``Changed`` naming the part that
    is not the one named). ``presentation``: read its report and figures too (a token naming one does); ``evidence``:
    read its evidence sidecar (False only for a list, which shows no evidence; a token naming one does); ``limit``: a
    result larger than this many bytes is not read (a list's badge). ``Unsettled`` where the files changed each time
    they were read together."""
    token = where if isinstance(where, Token) else Token(str(where))
    path = _result_file(Path(token.path))
    presentation = presentation or bool(token.presentation)
    evidence = evidence or bool(token.evidence)
    for _ in range(file_reads.TRIES):
        version = _attempt(path, presentation, evidence, limit)
        if version._settled():
            break
    else:
        raise Unsettled(f"{path.parent}: its files changed each time they were read together "
                        f"({file_reads.TRIES} attempts)")
    for part, expected in token.named().items():
        if (found := version.identity(part)) != expected:
            raise Changed(part, expected, found)
    return version


def _attempt(path: Path, presentation: bool, evidence: bool, limit: int | None) -> Version:
    """One reading of each part of a study (``resolve``)."""
    from adroit.evidence.bindings import report_path
    from adroit.evidence.build import mark_path, sidecar_path
    from adroit.orchestrator.studies import FILE
    mark = _read(mark_path(path))                   # its own output's mark (HE-01)
    result = _read(path, limit)
    sidecar = _read(sidecar_path(path)) if evidence else None
    record = _read(path.parent / FILE)
    report, figures = None, ()
    if presentation:
        report = _read(report_path(path))
        names = _figure_names(report.data, result.data, path.parent)
        figures = tuple((name, _read(path.parent / name)) for name in names)
    return Version(path, result, sidecar, record, report, figures, mark)


def _figure_names(report: bytes | None, result: bytes | None, folder: Path) -> list[str]:
    """The figures a report and its result name (``bindings.figures_of``, and those its binding names), and the PNGs
    beside them (a report written before ADROIT bound its figures is exported with them as found), each a name within
    the study's folder."""
    from adroit.evidence.archive_models import safe_member
    from adroit.evidence.bindings import FIGURE, binding
    text = report.decode("utf-8", errors="replace") if report is not None else ""
    names = set(FIGURE.findall(text))
    if (bound := binding(text)) is not None:
        names |= set(bound.figures)
    try:
        plots = json.loads(result).get("plots", []) if result is not None else []
    except (ValueError, AttributeError):
        plots = []
    names |= {p for p in plots if isinstance(p, str)} if isinstance(plots, list) else set()
    names |= {p.name for p in folder.glob("*.png")}
    out = []
    for name in sorted(names):
        try:
            out.append(safe_member(name))
        except ValueError:
            continue
    return out


AS_FOUND = ("*Read as found.* {what} This is a diagnostic output, not a held version of a saved study: nothing checks it "
            "against one later (ADROIT's version handle covers saved studies' results, evidence, reports and records; "
            "the version handle plan).")


def as_found(what: str) -> str:
    """The statement a diagnostic output's report makes of its weaker guarantee (the owner's decision, 2026-11-03, on
    the version-handle plan): the theory checks, the neutrino fog, the intake, extraction and discovery reports and the
    advisory outputs are read as found, each saying what it was made of."""
    return "\n\n" + AS_FOUND.format(what=what.strip()) + "\n"


class Followed(NamedTuple):
    """One edge of a version's graph (``follow``): the version it reaches (None where it is not followed), and what a
    reader says of it: why it is not followed (``archive.unavailable``), or "" where it is the version the record
    names, or the record names none (``archive.edge_notes`` qualifies those)."""
    edge: Any
    version: Version | None
    note: str


def follow(version: Version, *, presentation: bool = False) -> list[Followed]:
    """Each edge of a promotion's graph (``Version.edges``), resolved to the version its record names: another saved
    there now, or none, is not followed, saying why, never taken in its place (the auditor's CY recheck, CZ-01; its
    version-identity audit, VI-04). An edge whose record keeps no digest (made before ADROIT kept them) is resolved as
    found. The parent named as this result's own file is left out."""
    from adroit.evidence.archive import unavailable
    out = []
    for edge in version.edges():
        target = Path(edge.target)
        if edge.role == "parent" and target.exists() and target.resolve() == version.path.resolve():
            continue
        try:
            found = resolve(Token(str(target), result=edge.expected), presentation=presentation)
        except Changed as other:
            out.append(Followed(edge, None, unavailable(edge, "" if other.found in (NONE, UNREADABLE) else
                                                        other.found)))
            continue
        if found.result_state != "held":
            if edge.role == "child" or edge.expected:
                out.append(Followed(edge, None, unavailable(edge)))
            continue
        out.append(Followed(edge, found, ""))
    return out
