"""Shared prompt-policy fragments (SDK-free home, importable by every layer).

Output tokens are ~70% of measured LLM spend at 5x the input price, and the
prose fields exist for auditability, not scoring -- nothing in any metric reads
their length. The terseness clause is defined once here so every LLM-facing
system prompt (agents AND ingest) inherits a single source of truth without
the ingest layer having to import the agents package.
"""

from __future__ import annotations

TERSE_CLAUSE = (
    "\nBe terse. Every free-text field (rationale, justification, description): "
    "at most 50 words; cite feature names, passage ids, and numbers instead of "
    "restating inputs. Never echo the provided data, cards, or schema."
)
