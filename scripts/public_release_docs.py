"""The documentation files the public release must keep, because the code, tests or scripts use them.

The owner's decision (2026-11-20): the public ADROIT repository gets an agreed list of files, never
drafts or audits, but every file under ``docs/`` that ``adroit/``, ``tests/`` or ``scripts/`` names
ships with it. This script finds those files, so that none is dropped when the list is drawn up.

A path is found in three forms:

* a string ``"docs/dm3/validation_results.json"`` (a file, a folder, or a glob pattern);
* a chain ``ROOT / "docs" / "dm13" / "file.yaml"``, read up to its first part that is not a string;
* a name bound to such a chain (``DOCS = ... / "docs"``), then extended in the same file
  (``DOCS / "usability"``).

A chain that stops at a part that is not a string (``DOCS / f"{name}.md"``) needs the whole folder it
reached; one that stops at ``docs/`` itself cannot be narrowed and is listed for a person to read.
Mentions that name no tracked file (test placeholders, prefixes of files a script writes) are listed
too, so each can be checked by eye.

Usage: ``uv run python scripts/public_release_docs.py [--list]`` (``--list`` prints only the paths).
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("adroit", "tests", "scripts")
STRING = re.compile(r"""["'`(\s]((?:\./)?docs/[A-Za-z0-9_.*/{}-]*)""")
PART = r"""\s*/\s*(?:f?["']([^"']*)["']|([A-Za-z_][A-Za-z0-9_.()\[\]]*))"""
CHAIN = re.compile(r"""["']docs["']((?:""" + PART + r""")*)""")
BIND = re.compile(r"""^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=.*["']docs["']((?:""" + PART + r""")*)""", re.M)
STEP = re.compile(PART)


def tracked_docs() -> list[str]:
    """Return every file under ``docs/`` that git tracks, as paths relative to the repository."""
    out = subprocess.run(["git", "ls-files", "docs"], cwd=ROOT, capture_output=True, text=True, check=True)
    return out.stdout.split()


def _walk(start: str, tail: str) -> tuple[str, bool]:
    """Extend ``start`` by the string parts of ``tail``; say whether a non-string part ended it."""
    path = start
    for match in STEP.finditer(tail):
        literal, name = match.group(1), match.group(2)
        if name is not None or literal is None:
            return path, True
        if "{" in literal:
            return f"{path}/{literal.split('{')[0]}", True
        path = f"{path}/{literal}"
    return path, False


def mentions(text: str) -> set[tuple[str, bool]]:
    """Return the docs paths one source file names, each with whether it was cut short."""
    found = {(m.group(1).removeprefix("./").rstrip("/."), "{" in m.group(1)) for m in STRING.finditer(text)}
    found |= {_walk("docs", m.group(1)) for m in CHAIN.finditer(text)}
    for bound in BIND.finditer(text):
        base, open_ = _walk("docs", bound.group(2))
        if base != "docs":
            found.add((base, open_))
        for use in re.finditer(rf"\b{bound.group(1)}\b((?:{PART})+)", text):
            found.add(_walk(base, use.group(1)))
    return {(p.split("{")[0].rstrip("/") if cut else p, cut) for p, cut in found}


def resolve(mentioned: set[tuple[str, bool]],
            tracked: list[str]) -> tuple[set[str], dict[str, int], set[str], set[str]]:
    """Return (named files, folders named whole with their sizes, mentions to read, unmatched mentions).

    A folder named whole may be one the code reads file by file or one a script writes into; which,
    and so how much of it ships, is for the owner to agree.
    """
    required, folders, review, unmatched = set(), {}, set(), set()
    for path, cut in mentioned:
        if path == "docs":
            review.add("docs/ (the whole folder: a chain that cannot be narrowed, or a walk of every document)")
            continue
        if "*" in path:
            hits = [t for t in tracked if fnmatch.fnmatch(t, path)]
        elif path in tracked:
            hits = [path]
        elif inside := [t for t in tracked if t.startswith(path + "/")]:
            folders[path] = len(inside)
            continue
        else:
            hits = [t for t in tracked if t.startswith(path)] if cut else []
        (required.update(hits) if hits else unmatched.add(path))
    return required, folders, review, unmatched


def sources() -> list[Path]:
    """Return the Python, YAML, TOML and JSON files of the code, the tests and the scripts."""
    kinds = ("*.py", "*.yaml", "*.yml", "*.toml", "*.json", "*.txt")
    return sorted(p for folder in SOURCES for kind in kinds for p in (ROOT / folder).rglob(kind))


def main() -> None:
    """Print the docs files the release must keep, then the mentions a person should read."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="print only the required paths")
    args = parser.parse_args()
    mentioned: set[tuple[str, bool]] = set()
    for source in sources():
        mentioned |= mentions(source.read_text(errors="replace"))
    required, folders, review, unmatched = resolve(mentioned, tracked_docs())
    print("\n".join(sorted(required)))
    if args.list:
        return
    print(f"\n# {len(required)} files named one by one")
    print("# folders named whole (files in each; read or written, to agree):",
          *(f"{f} ({n})" for f, n in sorted(folders.items())), sep="\n#   ")
    print("# to read by eye:", *sorted(review), sep="\n#   ")
    print("# naming no tracked file (placeholders, prefixes, globs):", *sorted(unmatched), sep="\n#   ")


if __name__ == "__main__":
    main()
