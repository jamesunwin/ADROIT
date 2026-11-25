"""The $0 rehearsal of a paid command (G12's live check L7): requests priced as the budget gate prices them, none sent."""

import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from adroit.agents.llm import BudgetedLLMClient, LLMClient
from adroit.agents.rehearsal import Rehearsal


class Answer(BaseModel):
    value: int = 0


SYSTEM, MESSAGES = "Calculate.", [{"role": "user", "content": "2+2 " * 500}]


def test_the_rehearsal_reserves_what_the_budget_gate_reserves(tmp_path):
    """The same request, sent through the budgeted client and rehearsed: the same reservation."""
    def create(**kw):
        return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"value": 4}')],
                               usage=SimpleNamespace(input_tokens=100, output_tokens=20))
    raw = LLMClient(model="claude-opus-5-5", max_tokens=8192, client=SimpleNamespace(
        messages=SimpleNamespace(create=create)))
    paid = BudgetedLLMClient(raw, dollar_budget=5.0, ledger_path=tmp_path / "calls.jsonl")
    paid.complete_structured(SYSTEM, MESSAGES, Answer)
    reserved = next(json.loads(line)["reserved_usd"] for line in (tmp_path / "calls.jsonl").read_text().splitlines()
                    if json.loads(line).get("state") == "reserved")
    rehearsal = Rehearsal("claude-opus-5-5")
    reply = rehearsal.complete_structured(SYSTEM, MESSAGES, Answer, actor="audit")
    assert reply == Answer() and rehearsal.requests == [("audit", pytest.approx(reserved, rel=1e-12))]


def test_the_rehearsal_sends_nothing_and_sums_its_requests():
    rehearsal = Rehearsal("gpt-5.6-sol")
    for actor in ("a", "b"):
        rehearsal.complete_structured(SYSTEM, MESSAGES, Answer, actor=actor)
    (a, x), (b, y) = rehearsal.requests
    assert x == y > 0 and rehearsal.largest == x and rehearsal.total == pytest.approx(2 * x)
    assert rehearsal.suggested_cap() == pytest.approx(round(x + 0.25 * x + 0.005, 2), abs=0.011)
    with pytest.raises(RuntimeError, match="sends no request"):
        rehearsal._client._client.responses


def test_a_schema_without_an_empty_reply_cannot_be_rehearsed():
    class Needs(BaseModel):
        value: int
    with pytest.raises(ValueError, match="no empty reply"):
        Rehearsal("claude-opus-5-5").complete_structured(SYSTEM, MESSAGES, Needs)
