"""Which result a saved report describes, and which figures (the auditor's CX recheck, CY-03, 2026-11-01).

A study's report and its figures are written beside its result and read apart from it: holding one version of the
result, the study page had shown another's report (A's VIABLE badge above B's EXCLUDED report), and an export had
attached it to A's node. Each report ADROIT writes beside a result now ends with its binding, an HTML comment the page
does not show: the SHA-256 of the result's bytes it was written from, and of each figure beside it as it was then. A
reader holding a result shows or exports a report only where its binding names that result, and a figure only where its
bytes, read once, have the digest the binding names. A report written before keeps no binding: it is said to be
unbound, never taken as the held result's.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import NamedTuple

MARK = "<!-- adroit-binding "
_BINDING = re.compile(r"\n*<!-- adroit-binding (\{[^\n]*\}) -->\n*\Z")
FIGURE = re.compile(r"!\[[^\]]*\]\(([^)/:]+\.png)\)")      # a figure beside the report, as the page embeds it


class Binding(NamedTuple):
    """The result a report was written from (``result_sha256``) and each figure's digest then (name: SHA-256)."""
    result_sha256: str
    figures: dict[str, str]


def figures_of(report: str, result: object) -> list[str]:
    """The figures a report and its result name: those it embeds, and the result's ``plots``."""
    return sorted({*FIGURE.findall(report), *(Path(p).name for p in getattr(result, "plots", []) or [])})


def report_path(path: Path) -> Path:
    """The report written beside a saved result."""
    path = Path(path)
    return path.with_name("report.md") if path.name == "result.json" else path.with_suffix(".md")


def _draws(path: Path, claim=None) -> dict[str, str]:
    """Where the figure at ``path`` is named as drawn: the hold of its folder this thread's writer has (``claim``,
    else ``durable.holding``), whose draws are its own (the auditor's DE recheck, DF-01, 2026-11-05: a writer refused at its
    record had first drawn over the holder's figure, and the holder's report, binding this process's latest draw at
    that path, had named the refused writer's figure as its own). Where no writer holds the folder, nowhere: a draw's
    identity is its writer's, never a map of this process's draws by path, read after its hold has ended (the auditor's DG
    recheck, DH-01, 2026-11-06: a review packet had taken another writer's overlay from that map as its own)."""
    from adroit.core.durable import holding
    owner = claim if claim is not None else holding(path)
    return owner.drawn if owner is not None else {}


def _key(path: Path) -> str:
    """A figure's name among its writer's draws: the directory entry its writer replaces (``durable.entry``), never a
    link's target (DH-04)."""
    from adroit.core.durable import entry
    return str(entry(path))


def drawn(path: Path, sha256: str) -> None:
    """Remember the digest of a figure's bytes as its writer wrote them to ``path`` (``write_figure``), or as it
    verified them where it keeps a figure it drew before: a report bound later names that figure, not the file as read
    again (the auditor's CY recheck, CZ-02, 2026-11-01: a writer had taken the identity it bound from a later read of its
    destination). Kept by the writer's hold of the folder (``_draws``; DF-01), and only there (DH-01)."""
    _draws(path)[_key(path)] = sha256


def drawn_digest(path: Path) -> str:
    """The digest its writer's hold keeps for the figure at ``path``: of the bytes it wrote there (``write_figure``),
    or verified there (``drawn``); "" where it holds none, and where no writer of this thread holds the folder. Never
    read from the file: a record of a figure's identity (a checkpoint, a review packet) keeps this, so that a
    replacement written after the draw is never recorded as the figure drawn (the auditor's CZ recheck, DA-01, 2026-11-02);
    and it is read under the hold the figure was drawn under (DH-01)."""
    return _draws(path).get(_key(path), "")


def write_figure(fig, path: Path, dpi: int) -> Path:
    """A matplotlib figure written whole to ``path`` (its format from the suffix), and its digest remembered
    (``drawn``), under a hold of its folder from before it is rendered until its digest is kept: its writer's hold
    where this thread's writer holds the folder (``durable.holding``), else one taken for the draw (``publishing``),
    which waits for another writer's as every writer does, then ``Busy``, nothing drawn (the auditor's DF recheck, DG-02,
    2026-11-06: the folder only probed before the draw, a figure still rendering when another writer took the folder
    had been written over that writer's own, under its hold). The folder held is the one whose entry is replaced
    (``durable.entry``): a figure that is a link is replaced in its own folder, never under its target's lock (the auditor's
    DG recheck, DH-04, 2026-11-06). A writer that keeps a figure's identity (a report's binding, a review packet's
    record) draws it under its own hold, and reads the identity there."""
    from adroit.core.durable import entry, holding, publishing
    if holding(path) is not None:
        return _render(fig, path, dpi)
    with publishing(entry(path).parent):
        return _render(fig, path, dpi)


def _render(fig, path: Path, dpi: int) -> Path:
    """``write_figure`` under its hold: the figure rendered, written whole, and its digest kept by the hold."""
    import io
    from adroit.core.durable import write_atomic
    stream = io.BytesIO()
    fig.savefig(stream, format=Path(path).suffix.lstrip(".").lower() or "png", dpi=dpi)
    data = stream.getvalue()
    write_atomic(path, data)
    drawn(path, hashlib.sha256(data).hexdigest())
    return Path(path)


def bind(report: str, result_sha256: str, folder: Path, figures: list[str], claim=None) -> str:
    """``report`` bound to the result whose bytes have ``result_sha256``, and to each of ``figures`` in ``folder``: as
    its writer drew it (``drawn``: under its hold of the folder, ``claim``, where it holds it), else as it is now (read
    once; one absent is left out); an earlier binding is replaced."""
    digests = {}
    for name in figures:
        if held := _draws(Path(folder) / name, claim).get(_key(Path(folder) / name)):
            digests[name] = held
            continue
        try:
            digests[name] = hashlib.sha256((Path(folder) / name).read_bytes()).hexdigest()
        except OSError:
            continue
    held = json.dumps({"result_sha256": result_sha256, "figures": digests}, sort_keys=True)
    return unbound(report).rstrip("\n") + f"\n\n{MARK}{held} -->\n"


def unbound(report: str) -> str:
    """``report`` without its binding."""
    return _BINDING.sub("\n", report) if _BINDING.search(report) else report


def binding(report: str) -> Binding | None:
    """A report's binding, or None (a report written before ADROIT bound them, or one whose binding is unreadable)."""
    found = _BINDING.search(report)
    if not found:
        return None
    try:
        held = json.loads(found.group(1))
        figures = held.get("figures", {})
        if not isinstance(held.get("result_sha256"), str) or not isinstance(figures, dict):
            return None
        return Binding(held["result_sha256"], {str(k): str(v) for k, v in figures.items()})
    except (ValueError, AttributeError):
        return None


class Report(NamedTuple):
    """A study's report as read once (``data``, its bytes; ``text``, as text), against the result its reader holds:
    ``state`` is "bound" (it names that result), "other" (it names another version), "unbound" (it names none: written
    before), "absent", or, as its reader finds, "unsettled" (it names none, and the result was replaced while it was
    read, so it cannot be checked against the result held)."""
    state: str
    text: str
    binding: Binding | None
    data: bytes = b""


def read_report(path: Path, held_sha256: str | None) -> Report:
    """The report at ``path``, read once, against the result whose bytes have ``held_sha256`` (None: the result cannot
    be read, so no report is bound to it)."""
    try:
        data = Path(path).read_bytes()
    except (FileNotFoundError, IsADirectoryError):
        return Report("absent", "", None)
    return report_of(data, held_sha256)


def report_of(data: bytes | None, held_sha256: str | None) -> Report:
    """``read_report`` of a report's bytes as its reader holds them (None: there is none)."""
    if data is None:
        return Report("absent", "", None)
    text = data.decode("utf-8", errors="replace")
    found = binding(text)
    if found is None:
        return Report("unbound", text, None, data)
    return Report("bound" if held_sha256 is not None and found.result_sha256 == held_sha256 else "other",
                  text, found, data)


NO_REPORT = "none"            # the presentation identity of a result with no report beside it


def presentation(report: Report) -> str:
    """The identity of a report as its reader read it (``read_report``), for an action that reader starts to require:
    the SHA-256 of its bytes, which name its figures' (``NO_REPORT`` where there is none). The auditor's version-identity audit,
    VI-03 (2026-11-03): a figure download from a page showing report A had sent report B's figures, the result the
    same."""
    return NO_REPORT if report.state == "absent" else hashlib.sha256(report.data).hexdigest()


def figure(folder: Path, name: str, report: Report) -> bytes | None:
    """A figure's bytes, read once, where the report is bound and names it with exactly these bytes' digest; else None
    (another version, absent, or not named)."""
    if report.state != "bound" or report.binding is None or name not in report.binding.figures:
        return None
    try:
        data = (Path(folder) / name).read_bytes()
    except OSError:
        return None
    return figure_of(data, name, report)


def figure_of(data: bytes | None, name: str, report: Report) -> bytes | None:
    """``figure`` of a figure's bytes as its reader holds them (None: there are none)."""
    if data is None or report.state != "bound" or report.binding is None or name not in report.binding.figures:
        return None
    return data if hashlib.sha256(data).hexdigest() == report.binding.figures[name] else None
