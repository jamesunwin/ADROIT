"""Budget caps apply before each paid request, even during retry and fan-out."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from adroit.agents.budget import BudgetAccount
from adroit.agents.llm import BudgetedLLMClient, BudgetExceeded, LLMClient, OpenAIClient


class Answer(BaseModel):
    value: int


def client(tmp_path, replies=None, *, send=None, account=None, cap=0.25):
    calls = []
    replies = iter(replies or ['{"value":4}'])

    def create(**kw):
        calls.append(kw)
        if send:
            return send(**kw)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=next(replies))],
                               usage=SimpleNamespace(input_tokens=100, output_tokens=20))

    raw = LLMClient(model="claude-opus-5-5", max_tokens=128,
                    client=SimpleNamespace(messages=SimpleNamespace(create=create)))
    budget = BudgetedLLMClient(raw, dollar_budget=None if account else cap,
                              account=account, ledger_path=tmp_path / "calls.jsonl")
    return budget, calls


def ask(llm):
    return llm.complete_structured("Calculate.", [{"role":"user", "content":"2+2"}], Answer)


def test_tiny_cap_prevents_any_request(tmp_path):
    llm, calls = client(tmp_path, cap=0.000001)
    with pytest.raises(BudgetExceeded):
        ask(llm)
    assert not calls and llm.spent == 0


def test_next_retry_is_reserved_and_paid_invalid_answer_survives(tmp_path):
    llm, calls = client(tmp_path, replies=["bad"], cap=0.25)
    original = llm._inner._client.messages.create

    def lower_cap(**kw):
        response = original(**kw)
        llm.dollar_budget = 0.001
        return response

    llm._inner._client.messages.create = lower_cap
    with pytest.raises(BudgetExceeded):
        ask(llm)
    assert len(calls) == 1 and llm.spent == pytest.approx(0.0008)
    assert 'bad' in llm.ledger_path.read_text()


def test_paid_valid_response_is_not_discarded_at_cap(tmp_path):
    llm, _ = client(tmp_path)
    assert ask(llm).value == 4
    llm.dollar_budget = llm.spent
    with pytest.raises(BudgetExceeded):
        ask(llm)
    assert '"value":4' in llm.ledger[1]["response"]["content"][0].text


def test_shared_atomic_reservation_and_provider_caps():
    account = BudgetAccount(0.25, {"anthropic": 0.2, "openai": 0.1})
    barrier = Barrier(2)

    def reserve(_):
        barrier.wait()
        try:
            return account.reserve("anthropic", 0.15)
        except BudgetExceeded:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        keys = list(pool.map(reserve, range(2)))
    assert sum(k is not None for k in keys) == 1
    key = next(k for k in keys if k)
    account.settle(key, 0.08)
    with pytest.raises(BudgetExceeded):
        account.reserve("openai", 0.11)
    other = account.reserve("openai", 0.1)
    account.release(other)
    assert account.spent == {"anthropic": 0.08} and not account.reservations


@pytest.mark.parametrize("error", [TimeoutError, KeyboardInterrupt])
def test_uncertain_billing_retains_reservation(tmp_path, error):
    def fail(**kw):
        raise error()
    llm, calls = client(tmp_path, send=fail, cap=0.05)
    with pytest.raises(error):
        ask(llm)
    assert len(llm.account.reservations) == 1
    with pytest.raises(BudgetExceeded):
        ask(llm)
    assert len(calls) == 1


def test_unknown_price_fails_closed(tmp_path):
    llm, calls = client(tmp_path)
    llm._inner.model = "unpriced-model"
    with pytest.raises(ValueError, match="verified budget price"):
        ask(llm)
    assert not calls


def test_unknown_adapter_cannot_bypass_request_reservations(tmp_path):
    with pytest.raises(ValueError, match="bounded request adapter"):
        BudgetedLLMClient(SimpleNamespace(provider="anthropic"), dollar_budget=.25,
                          ledger_path=tmp_path / "unknown.jsonl")


def test_openai_reasoning_maximum_blocks_before_dispatch(tmp_path):
    calls = []
    raw = OpenAIClient(model="gpt-5.6-sol", client=SimpleNamespace(
        responses=SimpleNamespace(create=lambda **kw: calls.append(kw))))
    llm = BudgetedLLMClient(raw, dollar_budget=0.25, ledger_path=tmp_path / "openai.jsonl")
    with pytest.raises(BudgetExceeded):
        ask(llm)
    assert not calls


def test_response_without_usage_keeps_reservation_and_answer(tmp_path):
    def response(**kw):
        return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"value":4}')])
    llm, _ = client(tmp_path, send=response)
    assert ask(llm).value == 4
    assert llm.account.reservations and llm.ledger[-1]["state"] == "billing_uncertain"


def test_failed_background_response_is_preserved_before_error(tmp_path):
    response = SimpleNamespace(id="paid-background", status="failed", error="failure", output_text="partial answer")
    raw = OpenAIClient(model="gpt-5.6-sol", max_tokens=128, background=True,
                       client=SimpleNamespace(responses=SimpleNamespace(create=lambda **kw: response)))
    llm = BudgetedLLMClient(raw, dollar_budget=.25, ledger_path=tmp_path / "background.jsonl")
    with pytest.raises(RuntimeError, match="ended failed"):
        ask(llm)
    assert "partial answer" in llm.ledger_path.read_text()
    assert llm.account.reservations
