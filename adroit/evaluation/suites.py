"""The registry of DM10's suites."""

from __future__ import annotations

from adroit.evaluation.core import Suite


def suites() -> dict[str, Suite]:
    """Every suite by name (imported here, so that a suite's dependencies load only when asked for)."""
    from adroit.evaluation import historical, injection, limits, lz_tables, zoo
    return {s.name: s for s in (injection.SUITE, lz_tables.SUITE, limits.SUITE, historical.SUITE, zoo.SUITE)}
