"""Tests for the LLM client layer -- all offline (no network) except the live smoke.

The real :class:`LLMClient` is exercised with an injected stub in place of the
anthropic client, so its parse/retry/provenance logic is covered without any API
call. :class:`FakeLLMClient` and :class:`CachingLLMClient` are tested directly.

Run only fast tests (skip the one live API call):  uv run pytest -m "not live"
Run just the live smoke test:                        uv run pytest -m live
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from adroit.agents.llm import (
    BudgetedLLMClient,
    BudgetExceeded,
    CachingLLMClient,
    FakeLLMClient,
    LLMClient,
    RoleRoutedLLM,
    _estimate_tokens,
    role_for_actor,
)
from adroit.core.config import get_settings
from adroit.core.pricing import price_per_token
from adroit.core.provenance import EventType, ProvenanceStore


class Weather(BaseModel):
    """Small response model for the tests."""

    city: str
    temp_c: float


class _StubMessages:
    """Stub for ``anthropic.Anthropic().messages`` returning canned text per call."""

    def __init__(self, texts: list[str], usage: SimpleNamespace) -> None:
        self._texts = list(texts)
        self._usage = usage
        self.create_calls: list[dict] = []
        self.stop_reason = "end_turn"

    def create(self, *, model: str, max_tokens: int, system, messages: list[dict]):
        # ``system`` may be a plain string or a cache_control content-block list.
        self.create_calls.append({"model": model, "system": system, "messages": messages})
        block = SimpleNamespace(type="text", text=self._texts.pop(0))
        return SimpleNamespace(content=[block], usage=self._usage, model=model,
                               stop_reason=self.stop_reason)


class FakeAnthropic:
    """Injected stand-in for the anthropic client (no network)."""

    def __init__(self, texts: list[str], input_tokens: int = 100, output_tokens: int = 20) -> None:
        self.messages = _StubMessages(
            texts, SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens))


def _client(texts: list[str], **kwargs) -> tuple[LLMClient, FakeAnthropic]:
    fake = FakeAnthropic(texts, **kwargs)
    return LLMClient(client=fake, model="claude-sonnet-5"), fake


# --- LLMClient: structured parse + retry ----------------------------------


def test_a_reply_cut_off_before_any_answer_is_not_retried() -> None:
    """All output tokens spent before any text (a long reasoning): a retry would be billed and fail alike."""
    client, fake = _client(["", '{"city": "Paris", "temp_c": 21.5}'])
    fake.messages.stop_reason = "max_tokens"
    with pytest.raises(ValueError, match="before any answer"):
        client.complete_structured("sys", [{"role": "user", "content": "x"}], Weather)
    assert len(fake.messages.create_calls) == 1


def test_structured_parse_success() -> None:
    client, fake = _client(['{"city": "Paris", "temp_c": 21.5}'])
    result = client.complete_structured(
        system="Extract the weather.", messages=[{"role": "user", "content": "Paris, 21.5C"}],
        response_model=Weather)
    assert isinstance(result, Weather)
    assert result.city == "Paris" and result.temp_c == 21.5
    assert len(fake.messages.create_calls) == 1


def test_markdown_fenced_json_is_parsed() -> None:
    client, _ = _client(['```json\n{"city": "Rome", "temp_c": 30.0}\n```'])
    result = client.complete_structured(system="x", messages=[{"role": "user", "content": "y"}],
                                        response_model=Weather)
    assert result.city == "Rome"


def test_single_line_fenced_json_is_parsed_without_a_paid_retry() -> None:
    client, fake = _client(['```json{"city": "Oslo", "temp_c": 5.0}```'])
    result = client.complete_structured(system="x", messages=[{"role": "user", "content": "y"}],
                                        response_model=Weather)
    assert result.city == "Oslo"
    assert len(fake.messages.create_calls) == 1  # cosmetic fence must not cost a retry


def test_retry_on_invalid_feeds_error_back_then_succeeds() -> None:
    # First response is missing temp_c (ValidationError); second is valid.
    client, fake = _client(['{"city": "Paris"}', '{"city": "Paris", "temp_c": 21.5}'])
    result = client.complete_structured(system="x", messages=[{"role": "user", "content": "y"}],
                                        response_model=Weather)
    assert result.temp_c == 21.5
    assert len(fake.messages.create_calls) == 2
    retry_messages = fake.messages.create_calls[1]["messages"]
    assert any(m["role"] == "assistant" for m in retry_messages)  # bad output echoed back
    assert any(m["role"] == "user" and "not valid" in m["content"] for m in retry_messages)


def test_retry_budget_exhausted_raises() -> None:
    client, fake = _client(['nonsense', 'still bad', '{"city": "x"}'])  # 3 invalid attempts
    with pytest.raises(ValueError, match="no valid Weather"):
        client.complete_structured(system="x", messages=[{"role": "user", "content": "y"}],
                                   response_model=Weather)
    assert len(fake.messages.create_calls) == 3  # initial + 2 retries


def test_images_are_attached_to_last_user_message(tmp_path: Path) -> None:
    image = tmp_path / "figure.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n fake bytes")
    client, fake = _client(['{"city": "Nice", "temp_c": 25.0}'])
    client.complete_structured(system="x", messages=[{"role": "user", "content": "describe"}],
                               response_model=Weather, images=[image])
    content = fake.messages.create_calls[0]["messages"][-1]["content"]
    assert isinstance(content, list)
    assert any(block.get("type") == "image" for block in content)


# --- Provenance -----------------------------------------------------------


def test_provenance_record_created() -> None:
    store = ProvenanceStore.open(":memory:")
    fake = FakeAnthropic(['{"city": "Paris", "temp_c": 21.5}'], input_tokens=123, output_tokens=45)
    client = LLMClient(client=fake, model="claude-sonnet-5", provenance_store=store)
    client.complete_structured(system="s", messages=[{"role": "user", "content": "u"}],
                               response_model=Weather, run_id="run-1")
    events = [e for e in store.get_run_events("run-1") if e.event_type is EventType.llm_called]
    assert len(events) == 1
    ev = events[0]
    assert ev.llm_model == "claude-sonnet-5"
    assert ev.llm_prompt_tokens == 123 and ev.llm_completion_tokens == 45
    assert ev.llm_total_tokens == 168
    assert ev.llm_latency_s is not None and ev.llm_latency_s >= 0.0
    assert "Paris" in ev.llm_response_text and ev.llm_prompt_hash and len(ev.llm_prompt_hash) == 64


# --- FakeLLMClient --------------------------------------------------------


def test_fake_llm_client_returns_canned_in_order() -> None:
    a, b = Weather(city="A", temp_c=1.0), Weather(city="B", temp_c=2.0)
    fake = FakeLLMClient([a, b])
    assert fake.complete_structured("s", [{"role": "user", "content": "x"}], Weather) is a
    assert fake.complete_structured("s", [{"role": "user", "content": "x"}], Weather) is b
    assert fake.call_count == 2
    with pytest.raises(RuntimeError):
        fake.complete_structured("s", [{"role": "user", "content": "x"}], Weather)


def test_fake_llm_client_logs_provenance() -> None:
    store = ProvenanceStore.open(":memory:")
    fake = FakeLLMClient([Weather(city="A", temp_c=1.0)], provenance_store=store)
    fake.complete_structured("s", [{"role": "user", "content": "x"}], Weather, run_id="r")
    events = [e for e in store.get_run_events("r") if e.event_type is EventType.llm_called]
    assert len(events) == 1 and events[0].llm_model == "fake-model"


# --- CachingLLMClient -----------------------------------------------------


def test_cache_hit_avoids_second_inner_call(tmp_path: Path) -> None:
    fake = FakeLLMClient([Weather(city="Paris", temp_c=21.5)])  # only one canned response
    cache = CachingLLMClient(fake, tmp_path / "cache.sqlite")
    system, messages = "Extract.", [{"role": "user", "content": "Paris 21.5"}]
    first = cache.complete_structured(system, messages, Weather)
    assert first.city == "Paris" and fake.call_count == 1
    # Identical call must hit the cache -- the inner queue is empty, so a second
    # delegated call would raise. It does not, proving the cache served it.
    second = cache.complete_structured(system, messages, Weather)
    assert second.city == "Paris" and second.temp_c == 21.5
    assert fake.call_count == 1


def test_cache_keys_on_image_content_not_path(tmp_path: Path) -> None:
    img = tmp_path / "fig.png"
    img.write_bytes(b"\x89PNG version one")
    fake = FakeLLMClient([Weather(city="V1", temp_c=1.0), Weather(city="V2", temp_c=2.0)])
    cache = CachingLLMClient(fake, tmp_path / "c.sqlite")
    msg = [{"role": "user", "content": "describe"}]

    first = cache.complete_structured("s", msg, Weather, [img])
    hit = cache.complete_structured("s", msg, Weather, [img])
    assert first.city == hit.city == "V1" and fake.call_count == 1   # true hit

    img.write_bytes(b"\x89PNG version two -- regenerated figure")    # same path, new content
    fresh = cache.complete_structured("s", msg, Weather, [img])
    assert fresh.city == "V2" and fake.call_count == 2               # stale entry NOT served


def test_failed_attempts_are_logged_to_provenance() -> None:
    store = ProvenanceStore.open(":memory:")
    fake = FakeAnthropic(["bad one", "bad two", "bad three"])
    client = LLMClient(client=fake, model="claude-sonnet-5", provenance_store=store)
    with pytest.raises(ValueError, match="no valid Weather"):
        client.complete_structured("s", [{"role": "user", "content": "u"}], Weather,
                                   run_id="r-fail")
    events = [e for e in store.get_run_events("r-fail") if e.event_type is EventType.llm_called]
    assert len(events) == 3                          # every BILLED attempt is auditable
    assert events[0].llm_response_text == "bad one"  # the invalid output is preserved


def test_cache_miss_on_different_prompt(tmp_path: Path) -> None:
    fake = FakeLLMClient([Weather(city="A", temp_c=1.0), Weather(city="B", temp_c=2.0)])
    cache = CachingLLMClient(fake, tmp_path / "cache2.sqlite")
    first = cache.complete_structured("s", [{"role": "user", "content": "one"}], Weather)
    second = cache.complete_structured("s", [{"role": "user", "content": "two"}], Weather)
    assert first.city == "A" and second.city == "B" and fake.call_count == 2


# --- BudgetedLLMClient: actual billed usage vs estimate fallback -----------


def _msg(text: str = "u") -> list[dict]:
    return [{"role": "user", "content": text}]


def test_budgeted_charges_actual_billed_usage() -> None:
    client, _ = _client(['{"city": "Paris", "temp_c": 21.5}'],
                        input_tokens=1000, output_tokens=200)
    budget = BudgetedLLMClient(client)
    budget.complete_structured("s", _msg(), Weather)
    p_in, p_out = price_per_token("claude-sonnet-5")
    assert budget.input_tokens == 1000 and budget.output_tokens == 200
    assert budget.spent == pytest.approx(1000 * p_in + 200 * p_out)
    assert budget.calls == 1


def test_budgeted_counts_every_validation_retry_request() -> None:
    # First response missing temp_c -> a second billed API request is made.
    client, fake = _client(['{"city": "Paris"}', '{"city": "Paris", "temp_c": 21.5}'],
                           input_tokens=100, output_tokens=10)
    budget = BudgetedLLMClient(client)
    budget.complete_structured("s", _msg(), Weather)
    assert len(fake.messages.create_calls) == 2
    assert budget.input_tokens == 200 and budget.output_tokens == 20  # both requests billed
    assert budget.calls == 1                                          # one logical call


def test_budget_refuses_an_input_that_cannot_fit() -> None:
    client, fake = _client(["bad"], input_tokens=100_000, output_tokens=1)
    budget = BudgetedLLMClient(client, dollar_budget=0.25)
    with pytest.raises(BudgetExceeded):
        budget.complete_structured("s", _msg("x" * 100_000), Weather)
    assert not fake.messages.create_calls and budget.spent == 0


def test_budgeted_estimate_fallback_includes_schema_tokens() -> None:
    import json as _json
    fake = FakeLLMClient([Weather(city="A", temp_c=1.0)])  # no usage_hook slot -> estimates
    budget = BudgetedLLMClient(fake)
    budget.complete_structured("sys", _msg("hi"), Weather)
    expected = (_estimate_tokens("sys")
                + _estimate_tokens(_json.dumps(_msg("hi"), default=str))
                + _estimate_tokens(_json.dumps(Weather.model_json_schema())))
    assert budget.input_tokens == expected  # the appended JSON schema is not free


def test_budgeted_never_clobbers_a_preinstalled_usage_hook() -> None:
    seen: list[tuple] = []
    client, _ = _client(['{"city": "P", "temp_c": 1.0}'])
    client.usage_hook = lambda *args, **kwargs: seen.append(args)
    budget = BudgetedLLMClient(client)
    budget.complete_structured("s", _msg(), Weather)
    assert seen and seen[0][:3] == ("claude-sonnet-5", 100, 20)  # original hook still fires
    assert budget.input_tokens > 0                 # and the budget fell back to estimates


# --- prompt caching: request structure and cache-aware budget math ----------


def test_long_system_prompts_get_a_cache_control_block(tmp_path: Path) -> None:
    pad = "x" * 5000  # (system + schema) beyond the minimum cacheable length
    client, fake = _client(['{"city": "A", "temp_c": 1.0}'])
    client.complete_structured(system=pad, messages=_msg(), response_model=Weather)
    sent = fake.messages.create_calls[0]["system"]
    assert isinstance(sent, list) and sent[0]["cache_control"] == {"type": "ephemeral"}
    assert sent[0]["text"].startswith(pad)          # schema is inside the cached prefix


def test_the_system_prompt_is_always_marked_and_the_flag_disables_it() -> None:
    # Below the model's minimum the API skips a breakpoint at no cost, so even a
    # short system prompt is marked (it may reach the minimum with a user prefix).
    client, fake = _client(['{"city": "A", "temp_c": 1.0}'])
    client.complete_structured(system="short", messages=_msg(), response_model=Weather)
    sent = fake.messages.create_calls[0]["system"]
    assert isinstance(sent, list) and sent[0]["cache_control"] == {"type": "ephemeral"}

    off = LLMClient(client=FakeAnthropic(['{"city": "B", "temp_c": 2.0}']),
                    model="claude-sonnet-5", use_prompt_caching=False)
    off.complete_structured(system="y" * 5000, messages=_msg(), response_model=Weather)
    assert isinstance(off._client.messages.create_calls[0]["system"], str)


def test_a_stable_user_prefix_becomes_its_own_cached_block() -> None:
    from adroit.agents.llm import CACHE_SPLIT, with_cached_prefix
    client, fake = _client(['{"city": "A", "temp_c": 1.0}'])
    msg = [{"role": "user", "content": with_cached_prefix("CATALOGUE", "today's data")}]
    client.complete_structured(system="s", messages=msg, response_model=Weather)
    content = fake.messages.create_calls[0]["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "CATALOGUE",
                          "cache_control": {"type": "ephemeral"}}
    assert content[1] == {"type": "text", "text": "today's data"}
    assert CACHE_SPLIT not in str(fake.messages.create_calls[0])   # the marker never reaches the API
    assert msg[0]["content"] == with_cached_prefix("CATALOGUE", "today's data")  # caller untouched


def test_one_hour_ttl_marks_every_breakpoint_and_disabled_caching_drops_the_marker() -> None:
    from adroit.agents.llm import CACHE_SPLIT, with_cached_prefix
    fake = FakeAnthropic(['{"city": "A", "temp_c": 1.0}'])
    client = LLMClient(client=fake, model="claude-sonnet-5", cache_ttl="1h")
    msg = [{"role": "user", "content": with_cached_prefix("STABLE", "var")}]
    client.complete_structured(system="s", messages=msg, response_model=Weather)
    call = fake.messages.create_calls[0]
    one_hour = {"type": "ephemeral", "ttl": "1h"}
    assert call["system"][0]["cache_control"] == one_hour
    assert call["messages"][0]["content"][0]["cache_control"] == one_hour

    off_fake = FakeAnthropic(['{"city": "A", "temp_c": 1.0}'])
    off = LLMClient(client=off_fake, model="claude-sonnet-5", use_prompt_caching=False)
    off.complete_structured(system="s", messages=msg, response_model=Weather)
    sent = off_fake.messages.create_calls[0]["messages"][0]["content"]
    assert sent == "STABLE\n\nvar" and CACHE_SPLIT not in sent


def test_a_validation_retry_keeps_the_cached_prefix() -> None:
    from adroit.agents.llm import with_cached_prefix
    client, fake = _client(['not json', '{"city": "A", "temp_c": 1.0}'])
    msg = [{"role": "user", "content": with_cached_prefix("STABLE", "var")}]
    client.complete_structured(system="s", messages=msg, response_model=Weather)
    first, retry = (c["messages"] for c in fake.messages.create_calls)
    assert retry[0] == first[0] and len(retry) == 3   # same prefix, plus the correction turn


def test_one_hour_cache_writes_are_charged_at_twice_the_input_price() -> None:
    from adroit.core.pricing import CACHE_READ_MULT, CACHE_WRITE_1H_MULT
    usage = SimpleNamespace(input_tokens=50, output_tokens=10, cache_read_input_tokens=0,
                            cache_creation_input_tokens=400,
                            cache_creation=SimpleNamespace(ephemeral_1h_input_tokens=400,
                                                           ephemeral_5m_input_tokens=0))
    fake = FakeAnthropic(['{"city": "A", "temp_c": 1.0}'])
    fake.messages._usage = usage
    budget = BudgetedLLMClient(LLMClient(client=fake, model="claude-sonnet-5", cache_ttl="1h"))
    budget.complete_structured("s", _msg(), Weather)
    p_in, p_out = price_per_token("claude-sonnet-5")
    assert budget.spent == pytest.approx(50 * p_in + 10 * p_out + 400 * p_in * CACHE_WRITE_1H_MULT)
    assert CACHE_READ_MULT == 0.1


def test_provenance_records_the_cache_usage_of_each_call(tmp_path: Path) -> None:
    from adroit.core.provenance import ProvenanceStore
    usage = SimpleNamespace(input_tokens=50, output_tokens=10, cache_read_input_tokens=900,
                            cache_creation_input_tokens=0)
    fake = FakeAnthropic(['{"city": "A", "temp_c": 1.0}'])
    fake.messages._usage = usage
    store = ProvenanceStore.open(tmp_path / "p.sqlite")
    client = LLMClient(client=fake, model="claude-sonnet-5", provenance_store=store)
    client.complete_structured("s", _msg(), Weather, run_id="r1", actor="a")
    import json
    payload = json.loads(store.get_run_events("r1")[0].payload_json)
    assert payload["usage"] == {"input_tokens": 50, "output_tokens": 10,
                                "cache_read_input_tokens": 900, "cache_creation_input_tokens": 0}


def test_count_tokens_asks_the_api_for_the_request_as_sent() -> None:
    from adroit.agents.llm import with_cached_prefix
    fake = FakeAnthropic([])
    seen = {}

    def count_tokens(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(input_tokens=1234)

    fake.messages.count_tokens = count_tokens
    client = LLMClient(client=fake, model="claude-sonnet-5")
    n = client.count_tokens("s", [{"role": "user", "content": with_cached_prefix("A", "B")}], Weather)
    assert n == 1234 and seen["system"].startswith("s") and "schema" in seen["system"]
    assert seen["messages"][0]["content"] == "A\n\nB"


def test_budget_charges_cache_reads_and_writes_at_their_multipliers() -> None:
    from adroit.core.pricing import CACHE_READ_MULT, CACHE_WRITE_MULT
    usage = SimpleNamespace(input_tokens=100, output_tokens=10,
                            cache_read_input_tokens=1000, cache_creation_input_tokens=200)
    fake = FakeAnthropic(['{"city": "A", "temp_c": 1.0}'])
    fake.messages._usage = usage
    client = LLMClient(client=fake, model="claude-sonnet-5")
    budget = BudgetedLLMClient(client)
    budget.complete_structured("s", _msg(), Weather)
    p_in, p_out = price_per_token("claude-sonnet-5")
    expected = (100 * p_in + 10 * p_out
                + 1000 * p_in * CACHE_READ_MULT + 200 * p_in * CACHE_WRITE_MULT)
    assert budget.spent == pytest.approx(expected)
    assert budget.cache_read_tokens == 1000 and budget.cache_creation_tokens == 200
    assert budget.input_tokens == 100   # API semantics: input excludes cached tokens


# --- RoleRoutedLLM: per-role model routing ---------------------------------


class _ModelRecorder:
    """Minimal inner client that records the model each call arrived with."""

    model = "base-model"

    def __init__(self) -> None:
        self.models: list[str | None] = []

    def complete_structured(self, system, messages, response_model, images=None, *,
                            model=None, **kwargs):
        self.models.append(model)
        return Weather(city="X", temp_c=0.0)


def test_role_for_actor_mapping() -> None:
    assert role_for_actor("tabular_ingest") == "ingest"
    assert role_for_actor("figure_ingest") == "ingest"
    assert role_for_actor("text_ingest") == "ingest"
    assert role_for_actor("suitability_agent") == "suitability"
    assert role_for_actor("construction_agent") == "construction"
    assert role_for_actor("refinement_agent") == "refinement"
    assert role_for_actor("tournament_plausibility") == "plausibility"


def test_role_routed_llm_injects_the_roles_model() -> None:
    inner = _ModelRecorder()
    routed = RoleRoutedLLM(inner, {"ingest": "claude-haiku-4-5",
                                   "construction": "claude-opus-4-8"})
    msg = [{"role": "user", "content": "u"}]
    routed.complete_structured("s", msg, Weather, actor="figure_ingest")
    routed.complete_structured("s", msg, Weather, actor="construction_agent")
    routed.complete_structured("s", msg, Weather, actor="suitability_agent")   # unrouted role
    routed.complete_structured("s", msg, Weather, actor="figure_ingest",
                               model="claude-sonnet-5")                        # explicit wins
    assert inner.models == ["claude-haiku-4-5", "claude-opus-4-8", None, "claude-sonnet-5"]


def test_role_routed_llm_over_cache_keys_on_the_routed_model(tmp_path: Path) -> None:
    # The same prompt sent under two differently-routed actors must occupy two
    # cache entries (the routed model is decided BEFORE the cache sees the call).
    fake = FakeLLMClient([Weather(city="A", temp_c=1.0), Weather(city="B", temp_c=2.0)])
    routed = RoleRoutedLLM(CachingLLMClient(fake, tmp_path / "c.sqlite"),
                           {"ingest": "haiku-ish", "construction": "opus-ish"})
    msg = [{"role": "user", "content": "same prompt"}]
    first = routed.complete_structured("s", msg, Weather, actor="tabular_ingest")
    second = routed.complete_structured("s", msg, Weather, actor="construction_agent")
    assert (first.city, second.city) == ("A", "B") and fake.call_count == 2   # no false hit
    again = routed.complete_structured("s", msg, Weather, actor="text_ingest")  # same role: ingest
    assert again.city == "A" and fake.call_count == 2                          # true cache hit


# --- Live smoke test (single real API call) -------------------------------


@pytest.mark.live
def test_live_structured_smoke() -> None:
    settings = get_settings()
    if not settings.anthropic_api_key.get_secret_value():
        pytest.skip("no ANTHROPIC_API_KEY set")

    class Answer(BaseModel):
        value: int

    client = LLMClient()
    result = client.complete_structured(
        system="You are a precise calculator.",
        messages=[{"role": "user", "content": "What is 3 + 4? Respond with the integer only."}],
        response_model=Answer)
    assert result.value == 7


# --- the OpenAI client (DM8's checker), against a stub of the Responses API ---------------

class _StubResponses:
    def __init__(self, replies: list[str]) -> None:
        self.replies, self.calls = list(replies), []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.replies.pop(0),
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=200))


def _openai(replies: list[str], **kwargs):
    from adroit.agents.llm import OpenAIClient
    stub = SimpleNamespace(responses=_StubResponses(replies))
    return OpenAIClient(model="gpt-test", client=stub, **kwargs), stub.responses


def test_openai_client_parses_validates_and_retries() -> None:
    client, stub = _openai(['{"city": 3}', '{"city": "Paris", "temp_c": 21.5}'])
    out = client.complete_structured("You report weather as JSON.", [{"role": "user", "content": "Paris?"}],
                                     Weather)
    assert out == Weather(city="Paris", temp_c=21.5) and len(stub.calls) == 2
    first, second = stub.calls
    assert first["text"] == {"format": {"type": "json_object"}} and "JSON schema" in first["instructions"]
    assert "That was not valid" in second["input"][-1]["content"]


def test_openai_client_charges_every_request_to_the_budget() -> None:
    from adroit.agents.llm import BudgetedLLMClient
    client, _ = _openai(['not json', '{"city": "Oslo", "temp_c": -3.0}'], reasoning_effort="high")
    client.model = "gpt-5.6-sol"
    budgeted = BudgetedLLMClient(client, dollar_budget=10.0)
    budgeted.complete_structured("s", [{"role": "user", "content": "Oslo?"}], Weather)
    p_in, p_out = price_per_token("gpt-5.6-sol")
    assert budgeted.input_tokens == 2000 and budgeted.output_tokens == 400
    assert budgeted.spent == pytest.approx(2000 * p_in + 400 * p_out)


def test_openai_client_logs_to_provenance_and_refuses_images(tmp_path: Path) -> None:
    store = ProvenanceStore.open(":memory:")
    client, stub = _openai(['{"city": "Rome", "temp_c": 30.0}'], provenance_store=store,
                           reasoning_effort="medium")
    client.complete_structured("s", [{"role": "user", "content": "Rome?"}], Weather, run_id="r1")
    assert stub.calls[0]["reasoning"] == {"effort": "medium"}
    events = [e for e in store.get_run_events("r1") if e.event_type is EventType.llm_called]
    assert len(events) == 1 and events[0].llm_model == "gpt-test" and events[0].llm_total_tokens == 1200
    with pytest.raises(ValueError, match="text only"):
        client.complete_structured("s", [], Weather, images=[tmp_path / "x.png"])


def test_dm8_prices_and_their_cache_reads() -> None:
    """The owner's figures (2026-10-01): $4/$20 per MTok for both; cache reads $0.20 and $0.40."""
    from adroit.core.pricing import cache_read_price
    assert price_per_token("claude-opus-5-5") == (4.0e-6, 20.0e-6) == price_per_token("gpt-5.6-sol")
    assert cache_read_price("claude-opus-5-5") == 0.20e-6 and cache_read_price("gpt-5.6-sol") == 0.40e-6
    assert cache_read_price("claude-sonnet-5") == pytest.approx(0.2e-6)


def test_openai_cached_input_is_charged_at_the_cache_price() -> None:
    from adroit.agents.llm import BudgetedLLMClient, OpenAIClient
    usage = SimpleNamespace(input_tokens=1000, output_tokens=100,
                            input_tokens_details=SimpleNamespace(cached_tokens=600))
    stub = SimpleNamespace(responses=SimpleNamespace(
        create=lambda **kw: SimpleNamespace(output_text='{"city": "Nice", "temp_c": 20.0}', usage=usage)))
    budgeted = BudgetedLLMClient(OpenAIClient(model="gpt-5.6-sol", client=stub))
    budgeted.complete_structured("s", [{"role": "user", "content": "Nice?"}], Weather)
    assert budgeted.spent == pytest.approx(400 * 4e-6 + 600 * 0.4e-6 + 100 * 20e-6)


def test_openai_input_always_mentions_json() -> None:
    """OpenAI's JSON mode refuses input that never says "json"; the client adds it only when absent."""
    client, stub = _openai(['{"city": "Lyon", "temp_c": 18.0}', '{"city": "Lyon", "temp_c": 18.0}'])
    client.complete_structured("s", [{"role": "user", "content": "Lyon?"}], Weather)
    assert stub.calls[0]["input"][-1]["content"] == "Lyon?\n\nRespond with the JSON object."
    client.complete_structured("s", [{"role": "user", "content": "Lyon, as JSON?"}], Weather)
    assert stub.calls[1]["input"][-1]["content"] == "Lyon, as JSON?"


def test_openai_client_takes_a_request_timeout() -> None:
    from adroit.agents.llm import OpenAIClient
    stub = SimpleNamespace(responses=_StubResponses(['{"city": "Bonn", "temp_c": 12.0}']))
    assert OpenAIClient(model="gpt-test", client=stub, timeout_s=900.0).model == "gpt-test"


class _QueuedResponses:
    """A stub Responses API in background mode: queued, polled, then a final state."""

    def __init__(self, states: list[str], text: str = '{"city": "Gent", "temp_c": 9.0}') -> None:
        self.states, self.text, self.created, self.cancelled = list(states), text, [], []

    def _now(self, status: str) -> SimpleNamespace:
        done = status == "completed"
        return SimpleNamespace(id="r1", status=status, output_text=self.text if done else "",
                               usage=SimpleNamespace(input_tokens=100, output_tokens=50) if done else None)

    def create(self, **kwargs):
        self.created.append(kwargs)
        return self._now(self.states.pop(0))

    def retrieve(self, response_id: str):
        return self._now(self.states.pop(0))

    def cancel(self, response_id: str) -> None:
        self.cancelled.append(response_id)


def _background(states: list[str], **kwargs):
    from adroit.agents.llm import OpenAIClient
    stub = _QueuedResponses(states)
    return OpenAIClient(model="gpt-test", client=SimpleNamespace(responses=stub), background=True,
                        poll_s=0.0, **kwargs), stub


def test_background_mode_polls_until_the_response_is_done() -> None:
    client, stub = _background(["queued", "in_progress", "in_progress", "completed"])
    out = client.complete_structured("s", [{"role": "user", "content": "Gent?"}], Weather)
    assert out == Weather(city="Gent", temp_c=9.0)
    assert stub.created[0]["background"] is True and stub.created[0]["store"] is True and not stub.states


def test_background_mode_cancels_a_response_past_its_deadline() -> None:
    client, stub = _background(["queued"] + ["in_progress"] * 10, deadline_s=0.0)
    with pytest.raises(TimeoutError):
        client.complete_structured("s", [{"role": "user", "content": "Gent?"}], Weather)
    assert stub.cancelled == ["r1"]


def test_background_mode_reports_a_failed_response() -> None:
    client, _ = _background(["queued", "failed"])
    with pytest.raises(RuntimeError, match="failed"):
        client.complete_structured("s", [{"role": "user", "content": "Gent?"}], Weather)
