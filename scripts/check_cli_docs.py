"""R11's gate on the command line: every documented command and flag exists, and every option has help.

Walks the installed CLI (Typer → Click) and the documentation (README.md, DEVELOPMENT.md, docs/**/*.md):
- every `adroit <command> [<subcommand>] … --flag` written in the documents names a real command and a real flag;
- every command and option of the CLI has a help text.

    uv run python scripts/check_cli_docs.py          # $0, seconds; exit 1 on any finding
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DOCS = [ROOT / "README.md", ROOT / "DEVELOPMENT.md", *sorted((ROOT / "docs").rglob("*.md"))]
CALL = re.compile(r"adroit((?:\s+[a-z][a-z0-9-]*)+)((?:\s+[^`\n]*)?)")


def _tree():
    """(path, command) for every command of the Typer app; Typer vendors its own Click, so groups are duck-typed."""
    import typer
    from adroit.orchestrator.cli import app
    out = []

    def walk(cmd, path: tuple[str, ...]) -> None:
        out.append((path, cmd))
        if hasattr(cmd, "list_commands"):
            for name in cmd.list_commands(None):
                walk(cmd.get_command(None, name), (*path, name))
    walk(typer.main.get_command(app), ())
    return out


def commands() -> dict[tuple[str, ...], set[str]]:
    """Every command path → its option names (``--x`` and ``-x``)."""
    return {path: {opt for p in cmd.params for opt in (*getattr(p, "opts", ()), *getattr(p, "secondary_opts", ()))}
            for path, cmd in _tree()}


def missing_help() -> list[str]:
    found = []
    for path, cmd in _tree():
        name = " ".join(path)
        if path and not (cmd.help or getattr(cmd, "short_help", None)):
            found.append(f"command `adroit {name}` has no help")
        for p in cmd.params:
            if getattr(p, "param_type_name", "") == "option" and not getattr(p, "help", None) and p.name != "help":
                found.append(f"option {'/'.join(p.opts)} of `adroit {name}` has no help")
    return found


def documented(known: dict[tuple[str, ...], set[str]]) -> list[str]:
    """Calls in the documents whose command or flag does not exist."""
    found = []
    for doc in DOCS:
        for number, line in enumerate(doc.read_text().splitlines(), 1):
            for match in CALL.finditer(line):
                words = match.group(1).split()
                path: tuple[str, ...] = ()
                for word in words:                                 # the longest command path the words name
                    if (*path, word) in known:
                        path = (*path, word)
                    else:
                        break
                if not path:
                    found.append(f"{doc.relative_to(ROOT)}:{number}: `adroit {words[0]}` is not a command")
                    continue
                rest = match.group(0)
                for flag in re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*)", rest):
                    if flag not in known[path] and flag != "--help":
                        found.append(f"{doc.relative_to(ROOT)}:{number}: `adroit {' '.join(path)}` has no {flag}")
    return found


def main() -> int:
    known = commands()
    findings = missing_help() + documented(known)
    for f in findings:
        print(f)
    print(f"{len(known)} commands; {len(findings)} findings")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
