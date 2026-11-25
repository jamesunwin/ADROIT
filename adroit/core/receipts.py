"""Where gate and validation scripts write, and how a validation table is read.

A gate script's tracked receipts in ``docs/`` are the record of a declared run. A
later run must not replace them by accident, so every script writes to a fresh
folder under ``runs/gates/<gate>/`` unless the owner names another with ``--out``
(for example the tracked ``docs/dm13`` folder, to re-record a receipt on purpose).

Exit codes are shared by every script and command: 0 passed, 1 failed, and
:data:`BUDGET_STOPPED` when a paid command stopped at its budget before finishing.
"""

from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path

from adroit.core.config import get_settings

PASSED, FAILED, BUDGET_STOPPED = 0, 1, 3

Row = tuple[str, float | None, float, float, str]


def gate_output(gate: str, out: str | Path | None = None) -> Path:
    """The folder a gate script writes to, created.

    Args:
        gate: the gate's name, e.g. ``"dm13"``.
        out: the owner's folder; when empty, a new dated folder under ``runs/gates/<gate>/``.
    """
    if out:
        folder = Path(out)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        folder = get_settings().runs_dir / "gates" / gate / stamp
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def add_out_argument(parser: argparse.ArgumentParser, gate: str) -> None:
    """Add the shared ``--out`` option to a gate script's parser."""
    parser.add_argument("--out", default="", help=f"folder for the outputs (default: a new runs/gates/{gate}/<UTC> "
                                                  "folder; name docs/... only to re-record a tracked receipt)")


def row_passes(value: float | None, low: float, high: float) -> bool:
    """True when a gate's value is a number inside its declared range (None and NaN fail)."""
    return value is not None and not math.isnan(value) and low <= value <= high


def validation_table(rows: list[Row]) -> tuple[str, int]:
    """A validation script's Markdown table and its number of failed gates.

    Args:
        rows: (gate, value, low, high, reference) per gate, the range declared before the run.
    """
    lines = ["| gate | ours | declared range | reference | result |", "|---|---|---|---|---|"]
    failed = 0
    for name, value, low, high, ref in rows:
        ok = row_passes(value, low, high)
        failed += not ok
        shown = "none" if value is None else f"{value:.3f}"
        lines.append(f"| {name} | {shown} | {low:g}–{high:g} | {ref} | {'pass' if ok else 'FAIL'} |")
    return "\n".join(lines), failed


def exit_code(passed: bool) -> int:
    """The shared exit code of a finished gate: 0 passed, 1 failed."""
    return PASSED if passed else FAILED
