"""Single source of truth for LLM token prices (USD per token).

Both the budget/cost accounting in :mod:`adroit.agents.llm` and the read-only
dashboard chart import from here, so a price change lands everywhere at once.
This module is deliberately SDK-free (core must never import the provider SDK).

List prices checked against provider documentation on 2026-10-05.
Anthropic retained Sonnet 5's $2/$10 per MTok as its standard rate.
"""

from __future__ import annotations

import re

# model id -> (USD per input token, USD per output token)
TOKEN_PRICES: dict[str, tuple[float, float]] = {
    # DM8's two models: the owner's figures from the providers' pricing pages, 2026-10-01.
    # gpt-5.6-sol at its standard tier; the page's second tier ($8 input) is not used for short prompts.
    "claude-opus-5-5": (4.0e-6, 20.0e-6),
    "gpt-5.6-sol": (4.0e-6, 20.0e-6),
    "claude-sonnet-5": (2.0e-6, 10.0e-6),
    "claude-opus-4-8": (5.0e-6, 25.0e-6),
    # the record check's default model (CHECKER_MODELS): Anthropic's pricing page, checked 2026-11-18 ($10 / $50 per
    # MTok; one price at every context length; cache hits at 0.025 × input)
    "claude-fable-5-1": (10.0e-6, 50.0e-6),
    "claude-haiku-4-5": (1.0e-6, 5.0e-6),
    "fake-model": (1.0e-6, 1.0e-6),
}

# Conservative display fallback only; unknown models cannot authorize paid dispatch.
DEFAULT_PRICE: tuple[float, float] = (3.0e-6, 15.0e-6)

# Anthropic prompt-caching multipliers on the INPUT price: a cached prefix READ
# bills at 10% of base input; WRITING a prefix into the 5-minute cache bills at
# 125%, into the 1-hour cache at 200%.
CACHE_READ_MULT = 0.1
CACHE_WRITE_MULT = 1.25
CACHE_WRITE_1H_MULT = 2.0

# Where a model's cache-read price is not CACHE_READ_MULT × input (USD per token).
CACHE_READ_PRICES: dict[str, float] = {
    "claude-fable-5-1": 0.25e-6,
    "claude-opus-5-5": 0.20e-6,
    "gpt-5.6-sol": 0.40e-6,
}


def price_per_token(model: str | None) -> tuple[float, float]:
    """Return (input, output) USD-per-token prices for ``model``.

    Matching is exact first, then by longest known prefix so dated ids
    (``claude-haiku-4-5-20251001``) resolve to their family's price. Unknown or
    missing ids fall back to :data:`DEFAULT_PRICE`.
    """
    if model:
        if model in TOKEN_PRICES:
            return TOKEN_PRICES[model]
        for key in sorted(TOKEN_PRICES, key=len, reverse=True):
            if model.startswith(key):
                return TOKEN_PRICES[key]
    return DEFAULT_PRICE


def bounded_price(model: str) -> tuple[float, float]:
    """Known standard-tier prices only; an unknown model cannot authorize spend."""
    for key in sorted(TOKEN_PRICES, key=len, reverse=True):
        if model == key or re.fullmatch(re.escape(key) + r"-(?:\d{8}|\d{4}-\d{2}-\d{2})", model):
            return TOKEN_PRICES[key]
    raise ValueError(f"No verified budget price for model {model!r}")


# Minimum cacheable prompt length (tokens) per model, from Anthropic's prompt-
# caching guide (checked 2026-09-25). A shorter marked prefix is processed
# without caching, silently and at no cost.
MIN_CACHEABLE_TOKENS: dict[str, int] = {
    "claude-fable-5-1": 512, "claude-mythos-5-1": 512, "claude-opus-5-5": 512,
    "claude-opus-5": 512, "claude-fable-5": 512, "claude-mythos-5": 512,
    "claude-opus-4-8": 1024, "claude-sonnet-5": 1024, "claude-sonnet-4-6": 1024,
    "claude-sonnet-4-5": 1024, "claude-opus-4-1": 1024, "claude-opus-4": 1024,
    "claude-sonnet-4": 1024,
    "claude-mythos-preview": 2048, "claude-opus-4-7": 2048, "claude-3-5-haiku": 2048,
    "claude-opus-4-6": 4096, "claude-opus-4-5": 4096, "claude-haiku-4-5": 4096,
}


def cache_read_price(model: str | None) -> float:
    """USD per cached input token read: the model's own price if listed, else CACHE_READ_MULT × input."""
    if model:
        for key in sorted(CACHE_READ_PRICES, key=len, reverse=True):
            if model == key or model.startswith(key + "-"):
                return CACHE_READ_PRICES[key]
    return price_per_token(model)[0] * CACHE_READ_MULT


def min_cacheable_tokens(model: str | None) -> int:
    """Minimum cacheable prefix for ``model`` (longest-prefix match on dated ids).

    Unknown models get the largest documented minimum (4,096), so a report never
    calls a prefix cacheable when it might not be.
    """
    if model:
        for key in sorted(MIN_CACHEABLE_TOKENS, key=len, reverse=True):
            if model == key or model.startswith(key + "-"):
                return MIN_CACHEABLE_TOKENS[key]
    return 4096


# The primary paid models a researcher can choose (the CLI's --model and the workbench's menu); each must be
# priced above. Add a model here, with its price, to offer it.
PRIMARY_MODELS = {"claude-opus-5-5": "Claude Opus 5.5 (Anthropic)", "gpt-5.6-sol": "GPT-5.6 Sol (OpenAI)"}
DEFAULT_PRIMARY = "claude-opus-5-5"
# The models that may check a user-added record instead of a person (the owner, 2026-11-18,
# the post-review changes item 2): Claude Fable 5.1 by default, which never drafts a record, or GPT-5.6 Sol.
CHECKER_MODELS = {"claude-fable-5-1": "Claude Fable 5.1 (Anthropic)", "gpt-5.6-sol": "GPT-5.6 Sol (OpenAI)"}
DEFAULT_CHECKER = "claude-fable-5-1"


def model_name(model: str) -> str:
    """A model's name as people read it ("Claude Fable 5.1"), or its identifier where it has none here."""
    named = {**PRIMARY_MODELS, **CHECKER_MODELS}.get(model, model)
    return named.split(" (")[0]
