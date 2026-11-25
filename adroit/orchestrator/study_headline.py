"""A saved study's headline as the Studies list, its badge, its filter and the study's card show it, read from the
stored verdict, never re-derived (the consolidation plan's M1, 2026-10-25). Before, the badge read Track 1's cuts level
alone, gave an Explain-a-signal study none, never showed the combined view, and did not say that a conclusion depends
on an unverified record (D-4).

The auditor's consolidation audit (2026-10-25): the stored level is shown with the certification of the claims it rests on
beside it (CO-07: a stale or legacy headline had looked like a current one; ``core.certificate.assessment``), and a
result whose content is not what a result holds is named, never a page's error (CO-06: one ``null`` where a list
belongs had made the Studies page fail).

The auditor's CR recheck (CS-01, 2026-10-27): a study's result is read as its kind's (``study.json``), checked against that
kind's model before any badge (``headline_of``), and only a Track 1 or single-idea result has one: a result of another
shape had shown VIABLE on a study of every kind. The support a stored headline names is read strictly: a named
support set that is missing, or indices that are not positions, are damage, never "rests on less".

The auditor's CV recheck (CW-01, 2026-10-30): a study's result is read once, as one version of the file, and its badge and
its validation are of those same bytes (``snapshot``). The validation had been kept by the file's size and modification
time, so a malformed replacement keeping both read with the valid result's validation: VIABLE and certified in Studies
and on the study, while its point and its export refused it."""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import NamedTuple

LIMIT = 20_000_000                  # a result file larger than this is not read for a badge
SHORT = {"viable": "VIABLE", "viable_pending": "VIABLE PENDING", "excluded": "EXCLUDED", "pending": "PENDING",
         "overabundant": "OVERABUNDANT", "underabundant": "UNDERABUNDANT", "no_fit": "NO FIT",
         "no_thermal": "NO RESOLVED THERMAL EXPLANATION", "undetermined": "UNDETERMINED"}
UNVERIFIED = "UNVERIFIED RECORDS"
MARK = {"stale": "STALE CERTIFICATION", "legacy": "NOT ASSESSED (LEGACY)"}     # shown beside the stored level


class Headline(NamedTuple):
    """A saved result's headline: the badge's words, the level the filter keys on, the certification of the claims
    it rests on (``core.certificate.ASSESSMENTS``, or "" where it rests on none), and why the result could not be
    read as a result ("" if it could)."""
    words: str = ""
    level: str = ""
    certification: str = ""
    damage: str = ""


BADGED = {"track1": "verdict", "single_idea": "band"}       # the kinds whose result has a headline, and its shape


def headline(data: object, kind: str = "") -> Headline:
    """The ``Headline`` of a saved result: Track 1's cuts level, with the combined view's where it differs; a
    single-idea study's (Explain a signal) headline level; " · UNVERIFIED RECORDS" where the conclusion depends on one
    (its stored qualifiers); " · STALE CERTIFICATION" or " · NOT ASSESSED (LEGACY)" where the claims it rests on are
    so (CO-07); an empty one for any other result, and for a study ``kind`` without one (``BADGED``). A result that is
    not what it should be gives an empty headline with the reason (CO-06)."""
    try:
        return _headline(data, kind)
    except (TypeError, ValueError, KeyError, AttributeError) as error:
        return Headline(damage=f"its content is not a readable result ({_why(error)})")


def _headline(data: object, kind: str = "") -> Headline:
    if not isinstance(data, dict):
        return Headline(damage="its content is not a JSON object") if data is not None else Headline()
    if kind and kind not in BADGED:
        return Headline()
    shape = BADGED.get(kind, "")
    verdict = data.get("verdict") if isinstance(data.get("verdict"), dict) and shape != "band" else None
    if verdict and isinstance(verdict.get("level"), str) and verdict["level"]:
        level = verdict["level"]
        words = _words(verdict)
        combined = data.get("likelihood_verdict") if isinstance(data.get("likelihood_verdict"), dict) else None
        qualifiers = _strings(verdict.get("qualifiers"), "verdict.qualifiers")
        claims = _resting(verdict, "verdict", "crossings", ROOTS)
        if combined and isinstance(combined.get("level"), str):
            qualifiers += _strings(combined.get("qualifiers"), "likelihood_verdict.qualifiers")
            claims += _resting(combined, "likelihood_verdict", "crossings", ROOTS)
            if combined["level"] != level:
                words += f" · combined: {_words(combined)}"
        return _finished(words, level, qualifiers, claims)
    if shape != "verdict" and "band" in data and isinstance(data.get("level"), str) and data["level"]:
        level = data["level"]                                                        # a single-idea study
        if not isinstance(data["band"], list) or not isinstance(data.get("eos_thermal", {}), dict):
            raise TypeError("result.band is not a list of fitted masses" if not isinstance(data["band"], list) else
                            "result.eos_thermal is not a record of each table's points")
        claims = _resting(data, "result", "thermal", TABLES)
        qualifiers = [q for t in claims for q in _strings((t.get("certificate") or {}).get("qualifiers"),
                                                          "thermal.certificate.qualifiers")]
        summary = data.get("summary")                 # a level resting on no claim states its records there (AL3-18)
        if isinstance(summary, str) and RESTS_IN_SUMMARY in summary:
            qualifiers.append(RESTS_IN_SUMMARY)
        return _finished(SHORT.get(level, level.replace("_", " ").upper()), level, qualifiers, claims)
    return Headline()


FOUND_EXCLUDED = "ALL FOUND EXCLUDED · COVERAGE INCOMPLETE"


def _words(view: dict) -> str:
    """A verdict's badge words: its level's, or, for a pending one whose every stored thermal solution is excluded,
    ``FOUND_EXCLUDED`` (the owner, 2026-11-23; ``verdict.all_found_excluded``, read from the stored statuses)."""
    level = view["level"]
    crossings = view.get("crossings")
    if level == "pending" and isinstance(crossings, list) and crossings and all(
            isinstance(c, dict) and c.get("status") == "excluded" for c in crossings):
        return FOUND_EXCLUDED
    return SHORT.get(level, level.replace("_", " ").upper())


ROOTS = {"table_roots": ("rests_on_table_roots", False)}     # a verdict's other claims: one list
RESTS_IN_SUMMARY = "this conclusion depends on unverified records"   # a single idea's "no thermal" on the relic target
TABLES = {"eos_thermal": ("rests_on_tables", True)}           # a single-idea study's: one list per table


def _resting(view: dict, where: str, field: str, others: dict[str, tuple[str, bool]]) -> list[dict]:
    """The claims a stored headline rests on: those its result names (``rests_on``, positions in ``field``; and for
    each of ``others``, a list or each table's list of claims, the positions its index field names), never re-derived
    here (the auditor's CO recheck, CR-04, 2026-10-26: the history had assessed every candidate, so an unrelated waiting
    point un-certified a viable witness). A result from before the fields rests on every claim in ``field``; one that
    names support it does not hold, or names it with anything but positions (false, 0, a list where each table's
    belong), raises (the auditor's CR recheck, CS-01, 2026-10-27: those had read as resting on less, and certified)."""
    claims = _dicts(view.get(field), f"{where}.{field}")
    named = {index: view.get(index) for index, _ in others.values()}
    if view.get("rests_on") is None:
        if any(v is not None and v != [] and v != {} for v in named.values()):
            raise TypeError(f"{where} names claims besides its own without rests_on")
        return claims
    out = [claims[i] for i in _positions(view.get("rests_on"), len(claims), f"{where}.rests_on")]
    for name, (index, per_table) in others.items():
        chosen, found = named[index], view.get(name)
        if chosen is None:
            continue
        if not per_table:
            rows = _dicts(found, f"{where}.{name}")
            out += [rows[i] for i in _positions(chosen, len(rows), f"{where}.{index}")]
            continue
        if not isinstance(chosen, dict):
            raise TypeError(f"{where}.{index} is not a record of each table's positions")
        if chosen and not isinstance(found, dict):
            raise TypeError(f"{where}.{index} names table points that {where}.{name} does not hold")
        for table, positions in chosen.items():
            rows = _dicts(found.get(table), f"{where}.{name}.{table}")
            out += [rows[i] for i in _positions(positions, len(rows), f"{where}.{index}.{table}")]
    return out


def resting_claims(data: object) -> list[dict]:
    """The claims a stored result's headline rests on (``_resting``), for the readers beside the badge (the study
    card's stale reason); [] for any other result, or one that cannot be read as a result."""
    if not isinstance(data, dict):
        return []
    try:
        verdict = data.get("verdict") if isinstance(data.get("verdict"), dict) else None
        if verdict:
            combined = data.get("likelihood_verdict") if isinstance(data.get("likelihood_verdict"), dict) else {}
            return [*_resting(verdict, "verdict", "crossings", ROOTS),
                    *(_resting(combined, "likelihood_verdict", "crossings", ROOTS) if combined else [])]
        if "band" in data:
            return _resting(data, "result", "thermal", TABLES)
    except (TypeError, ValueError, KeyError, AttributeError):
        pass
    return []


def _positions(value: object, size: int, where: str) -> list[int]:
    if not isinstance(value, list) or not all(isinstance(i, int) and not isinstance(i, bool) and 0 <= i < size
                                              for i in value):
        raise TypeError(f"{where} does not name the result's claims")
    return list(value)


def _finished(words: str, level: str, qualifiers: list[str], claims: list[dict]) -> Headline:
    certification = _certification(claims)
    mark = f" · {MARK[certification]}" if certification in MARK else ""
    return Headline(words + _unverified(qualifiers) + mark, level.replace("_", " "), certification)


def _certification(claims: list[dict]) -> str:
    """The stored claims' assessment against the data as they are now (``certification.assessed``): "" where the
    headline rests on no claim (a rootless verdict); a certificate that is not one raises (CO-06)."""
    if not claims:
        return ""
    from adroit.core.certificate import Certificate
    from adroit.parameter_space.certification import assessed
    stored = [c.get("certificate") for c in claims]
    return assessed([Certificate.model_validate(c) if c is not None else None for c in stored])


def _strings(value: object, where: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise TypeError(f"{where} is not a list of words")
    return list(value)


def _dicts(value: object, where: str) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        raise TypeError(f"{where} is not a list of records")
    return list(value)


def read(data: object) -> tuple[str, str]:
    """(the badge's words, the level the filter keys on) of a saved result (``headline``)."""
    found = headline(data)
    return found.words, found.level


def _unverified(qualifiers: list[str]) -> str:
    return f" · {UNVERIFIED}" if any(q.startswith(("depends on unverified records", "this conclusion depends"))
                                     for q in qualifiers) else ""


class Snapshot(NamedTuple):
    """A study's ``result.json`` as one read: its JSON (None where there is none, or it is damaged), its study's kind
    (``study.json``), why it is not a result of that kind ("" if it is; ``unlike``), the bytes read (None where none
    were): the JSON and the reason both of those bytes; and the version of the file they were read as
    (``core.file_reads``), by which a reader can tell whether it has changed since."""
    data: object = None
    kind: str = ""
    damage: str = ""
    content: bytes | None = None
    version: tuple | None = None


def snapshot_of(content: bytes, kind: str, version: tuple | None = None) -> Snapshot:
    """``snapshot`` of a result's bytes as its reader holds them (``evidence.version``, which reads them with the
    rest of the study), checked against its study's ``kind``."""
    from adroit.core.durable import reason
    try:
        data = json.loads(content)
    except ValueError as error:
        return Snapshot(kind=kind, damage=f"its result cannot be read ({reason(error)})", content=content,
                        version=version)
    if data is not None and (why := unlike(content, kind)):
        return Snapshot(kind=kind, damage=why, content=content, version=version)
    return Snapshot(data, kind, content=content, version=version)


SHOWN = ("bound", "unbound", "unread")   # record states whose title, date and cost a list shows (``listed``)


def held(folder: Path, limit: int | None = LIMIT):
    """A study as a list shows it: its record and its result read as one checked transaction
    (``evidence.version.resolve``: no evidence; a result larger than ``limit`` bytes not read), so that a row, a picker
    or a command names, dates and costs a study by the record read with the result whose verdict it shows. The auditor's
    version-identity audit, VI-01, and its DB/VI recheck, DC-01 (2026-11-03): a page and the history had joined A's
    record to B's result, read apart; the version handle (the owner, 2026-11-03) reads them together.
    ``evidence.version.Unsettled`` where they changed each time they were read."""
    from adroit.evidence.version import resolve
    return resolve(folder, evidence=False, limit=limit)


def offered(root: Path, kinds: tuple[str, ...]) -> list:
    """The saved studies of ``kinds`` with a result, each a version as a list reads it (``held``), for a picker or a
    list that names them by ``listed`` (DC-01); one that cannot be read together is left out, as ``tree`` leaves out a
    record it cannot read (``studies.unoffered`` names those)."""
    from adroit.evidence.version import Unsettled
    from adroit.orchestrator import studies
    out = []
    for _, s in studies.tree(root):
        if s.kind in kinds and (Path(s.folder) / "result.json").exists():
            try:
                found = held(Path(s.folder))
            except Unsettled:
                continue
            if found.kind in kinds:
                out.append(found)
    return out


def listed(found) -> str:
    """How a list of studies names one (the history, ``adroit studies``, the pickers of saved studies, a model's
    analyses), from its version (``held``): its record's title, where the record describes the result read or names
    none (as found); else its folder, saying why its record's title is not shown. The auditor's DB/VI recheck, DC-01
    (2026-11-03): the history and the pickers had named B's result by A's title."""
    name = Path(found.folder).name
    if found.record_state in SHOWN:
        return found.study().title
    if found.record_state == "other":
        return f"{name} (its study record describes another version of its result)"
    if found.record_state == "interrupted":             # the auditor's portability audit, IC-01
        return f"{name} (its last publication was interrupted: its study record may be of an earlier one)"
    return f"{name} (its study record cannot be read)"


def headline_of(folder: Path) -> Headline:
    """``headline`` of a study folder's ``result.json``, read as its study's kind, of its version as a list reads it
    (``held``): an empty one without it; the reason where it cannot be read, or where it is not a result of its kind
    (CS-01: no badge then)."""
    return held(folder).headline()


def headline_from(found: Snapshot) -> Headline:
    """``headline`` of a ``snapshot``: its damage, or the headline of its data as its study's kind."""
    return Headline(damage=found.damage) if found.damage else headline(found.data, found.kind)


KEPT = 512                                  # validations kept, by a result's bytes and its kind (``unlike``)
_VALIDATED: dict[tuple[str, str], str] = {}
_LOCK = threading.Lock()


def unlike(content: bytes, kind: str) -> str:
    """Why ``content``, a result's bytes, is not a result of its study's ``kind`` (``evidence.results.result_type``,
    whose models check that the support a headline names is the result's own), or "": a kind ADROIT has no model for is
    not checked. Kept by the digest of the bytes and the kind (CS-01: each version validated once). The auditor's CV recheck,
    CW-01 (2026-10-30): kept by the file's size and modification time, a malformed replacement keeping both had been
    read with the validation of the bytes before it."""
    key = (hashlib.sha256(content).hexdigest(), kind)
    with _LOCK:
        if key in _VALIDATED:
            return _VALIDATED[key]
    found = _unlike(content, kind)
    with _LOCK:
        while len(_VALIDATED) >= KEPT:
            _VALIDATED.pop(next(iter(_VALIDATED)))
        _VALIDATED[key] = found
    return found


def _unlike(content: bytes, kind: str) -> str:
    from adroit.evidence.results import result_type
    try:
        model = result_type(kind)
    except ValueError:
        return ""
    try:
        model.model_validate_json(content)
    except ValueError as error:
        return f"its content is not a {kind.replace('_', '-')} result ({_why(error)})"
    return ""


def _why(error: BaseException) -> str:
    """An error in one line: a validation error's first problem and where, else ``durable.reason``."""
    from pydantic import ValidationError
    from adroit.core.durable import reason
    if isinstance(error, ValidationError) and (problems := error.errors()):
        first = problems[0]
        where = ".".join(str(x) for x in first.get("loc", ())) or "the result"
        more = f" (and {len(problems) - 1} more)" if len(problems) > 1 else ""
        return f"{where}: {first.get('msg', '')}{more}"
    return reason(error)


def of(folder: Path) -> tuple[str, str]:
    """``read`` of a study folder's ``result.json`` (("", "") without one, or unreadable)."""
    found = headline_of(folder)
    return found.words, found.level


def colour(words: str) -> str:
    """The badge's colour, from its first level."""
    return {"VIABLE": "green", "VIABLE PENDING": "teal", "EXCLUDED": "red", "PENDING": "orange",
            "OVERABUNDANT": "brown", "UNDERABUNDANT": "brown", "NO FIT": "grey", "UNDETERMINED": "orange",
            "NO RESOLVED THERMAL EXPLANATION": "grey"}.get(words.split(" · ")[0], "grey")
