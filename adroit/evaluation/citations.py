"""Every number cites its run (DM11): the citations of the paper and the design document.

A number in the paper carries ``\\run{path}`` (LaTeX) and in the design document
``(run: path)`` (Markdown; several may share the parentheses, separated by
``;``), where the path is a record or results file in the repository,
optionally followed by ``#section``. ``missing`` lists the citations
whose file does not exist, so a moved or renamed result is caught.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATTERNS = (re.compile(r"\\run\{([^}]+)\}"), re.compile(r"(?:\(|;\s+)run:\s+`?([^;)#\n`]+)"))


def citations(text: str) -> list[str]:
    """The cited paths in a text, in order (each path without its ``#section``)."""
    found = []
    for pattern in PATTERNS:
        found += [(m.start(), m.group(1).split("#")[0].strip()) for m in pattern.finditer(text)]
    return [path for _, path in sorted(found)]


def missing(text: str, root: Path = ROOT) -> list[str]:
    """The cited paths that do not exist in the repository."""
    return sorted({path for path in citations(text) if not (root / path).exists()})


def check(files: list[Path], root: Path = ROOT) -> dict[str, list[str]]:
    """For each file, the cited paths that are missing (an empty list: every citation resolves)."""
    return {str(f): missing(f.read_text(), root) for f in files}
