"""Regression guard: the terseness clause for LLM-facing prompts has one source.

Output tokens are ~70% of measured spend; the clause caps the prose fields
without touching anything a metric reads. The agents that carry it are
rebuilt in DM8 and DM9, each with its own check that its system prompt
includes the clause.
"""

from __future__ import annotations

from adroit.core.prompts import TERSE_CLAUSE


def test_terse_clause_is_single_sourced() -> None:
    from adroit.agents.llm import TERSE_CLAUSE as reexported
    assert reexported is TERSE_CLAUSE          # one definition, re-exported
    assert "Be terse" in TERSE_CLAUSE and "50 words" in TERSE_CLAUSE
