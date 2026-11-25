"""Tests for the single-source token-price table used by budget, eval, and dashboard."""

from __future__ import annotations

from adroit.core.pricing import DEFAULT_PRICE, TOKEN_PRICES, price_per_token


def test_exact_match_returns_table_price() -> None:
    assert price_per_token("claude-opus-4-8") == (5.0e-6, 25.0e-6)
    assert price_per_token("fake-model") == (1.0e-6, 1.0e-6)


def test_dated_model_id_resolves_by_prefix() -> None:
    assert price_per_token("claude-haiku-4-5-20251001") == TOKEN_PRICES["claude-haiku-4-5"]


def test_unknown_or_missing_model_falls_back_to_default() -> None:
    assert price_per_token("some-other-model") == DEFAULT_PRICE
    assert price_per_token(None) == DEFAULT_PRICE
    assert price_per_token("") == DEFAULT_PRICE


def test_sonnet5_is_charged_at_current_standard_price() -> None:
    # Anthropic retained $2/$10 as standard pricing (checked 2026-10-05).
    assert TOKEN_PRICES["claude-sonnet-5"] == (2.0e-6, 10.0e-6)
