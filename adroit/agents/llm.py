"""LLM client layer -- the ONLY module permitted to import the anthropic and openai SDKs.

Everything else in the system talks to language models through the
:class:`StructuredLLM` interface, so the rest of the codebase stays testable
offline via :class:`FakeLLMClient`. The real :class:`LLMClient` requests a JSON
object conforming to a Pydantic model's schema, validates it, and retries up to
twice -- feeding the validation error back to the model -- before giving up.
Every call is logged to the provenance store (model, prompts, response, tokens,
latency), and :class:`CachingLLMClient` memoizes results in a local SQLite cache
to keep evaluation costs down and runs reproducible.

Model defaults come from :mod:`adroit.core.config`: a Sonnet-class model for
routine calls (``claude-sonnet-5``) with an Opus-class override for hard steps
(``claude-opus-4-8``), both overridable via environment variables.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sqlite3
import threading
import time
from uuid import uuid4
from hashlib import sha256
from pathlib import Path
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Literal, Protocol, runtime_checkable

import anthropic
from pydantic import BaseModel, ValidationError

from adroit.agents.budget import BudgetAccount, BudgetExceeded, UnknownLedger

from adroit.core.config import get_settings
from adroit.core.durable import Held
from adroit.core.pricing import (
    CACHE_WRITE_1H_MULT,
    CACHE_WRITE_MULT,
    bounded_price,
    cache_read_price,
    price_per_token,
)

# Re-exported: the terseness clause lives SDK-free in core.prompts so the
# ingest layer can use it without importing the agents package.
from adroit.core.prompts import TERSE_CLAUSE  # noqa: F401
from adroit.core.provenance import EventType, LLMCallRecord, ProvenanceStore

_MEDIA_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp",
}

# Retries must be explicit and individually reserved; transport errors may be billed.
_MAX_API_RETRIES = 0  # transport failures have uncertain billing; never retry them invisibly
# Per-request timeout (seconds): caps a hung connection so retries can't wedge for
# an unbounded time; comfortably above the latency of an 8k-token structured call.
_REQUEST_TIMEOUT_S = 180.0
# Fast-fail timeout for the cheap health ping used by the orchestrator's
# degradation-recovery loop (should return quickly whether up or down).
_PROBE_TIMEOUT_S = 20.0

# The environment variable holding each provider's key (read by core.config from the environment or the project's .env).
KEY_VARIABLES = {"anthropic": ("Anthropic", "ANTHROPIC_API_KEY"), "openai": ("OpenAI", "OPENAI_API_KEY")}
# One lock for every paid ledger written in this process: a command's clients may share one ledger file (a workbench
# job's own ledger), and a journalled response can be long.
_JOURNAL_LOCK = threading.Lock()


class MissingCredentials(ValueError):
    """A provider's API key is not set: known before any request leaves the process, so nothing is reserved against
    the budget and nothing is sent (the workflow audit's WA-04, 2026-10-24: the SDK's TypeError had been journalled as
    a request whose bill is unknown, its reservation kept, and shown as "the provider call failed (TypeError)")."""


def missing_key(provider: str) -> str:
    """What to do when a provider's key is not set, naming its variable and never a key."""
    name, variable = KEY_VARIABLES[provider]
    return (f"no {name} API key: set {variable} in your environment or in the .env file of the ADROIT project folder "
            "(the checkout, or the folder above the installed package: docs/installation.md), then run again; nothing "
            "was sent and nothing was reserved")


def key_problem(provider: str, key: str) -> str:
    """Why a provider's key cannot be used, naming its variable and never its value, or "": not set, or holding a
    space or a non-printable character once its surrounding whitespace is stripped (the settings strip it). The
    security addendum's AL3-25 (2026-11-16): a key with a trailing space had been refused by the HTTP layer with the
    key in its message, and printed whole in the command's traceback and the workbench run's log."""
    if not key:
        return missing_key(provider)
    # a key is printable ASCII: a typographic quote or another non-ASCII character had passed, then failed in the HTTP
    # layer after the spend was reserved, leaving the ledger "billing_uncertain" (the audit loop's AL4-14(a))
    if any(c.isspace() or not c.isprintable() or not c.isascii() for c in key):
        name, variable = KEY_VARIABLES[provider]
        return (f"the {name} API key in {variable} holds a space, a line break, a typographic quote or another "
                "character a key cannot hold: set it again (the key alone, on one line, in plain quotes or none), then "
                "run again; nothing was sent and nothing was reserved")
    return ""


# each provider's own endpoint; another is used only where ADROIT_ALLOWED_ENDPOINTS names it (AL3-26)
PROVIDER_ENDPOINTS = {"anthropic": "https://api.anthropic.com", "openai": "https://api.openai.com/v1"}
ENDPOINT_VARIABLES = {"anthropic": "ANTHROPIC_BASE_URL", "openai": "OPENAI_BASE_URL"}


def endpoint(provider: str) -> tuple[str, str]:
    """(the endpoint a provider's client is built with, why it is refused or ""). The provider's own unless its
    variable (``ANTHROPIC_BASE_URL``, ``OPENAI_BASE_URL``, in the environment or ``.env``) names another; that one is
    used only where ``ADROIT_ALLOWED_ENDPOINTS`` (comma-separated) names it too, else the client is refused before
    anything is reserved or sent, and built with the provider's own (the security addendum's AL3-26, 2026-11-16: the
    SDKs had taken the variable themselves, plain http included, and the key and the prompts had gone there)."""
    from urllib.parse import urlsplit
    from adroit.core.config import env
    own = PROVIDER_ENDPOINTS[provider]
    settings = get_settings()
    named = getattr(settings, f"{provider}_base_url", "") or ""
    if not named or named.rstrip("/") == own:
        return own, ""
    allowed = {u.strip().rstrip("/") for u in env("ALLOWED_ENDPOINTS").split(",") if u.strip()}
    if named.rstrip("/") in allowed:
        return named, ""
    name, _ = KEY_VARIABLES[provider]
    return own, (f"{ENDPOINT_VARIABLES[provider]} points {name} requests at {urlsplit(named).netloc or named!r}, which "
                 f"is not {name}'s own endpoint ({own}): your key and prompts would go there. Unset it, or allow that "
                 "endpoint explicitly with ADROIT_ALLOWED_ENDPOINTS; nothing was sent and nothing was reserved")


def host(url: str) -> str:
    """An endpoint's host, as shown beside the model and the cost."""
    from urllib.parse import urlsplit
    return urlsplit(url).netloc or url


# HTTP status codes that indicate a transient/degraded API (a later retry may work),
# as opposed to a client/auth error (400/401/403) that no retry will fix.
_DEGRADED_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504, 529})


def is_degraded_error(exc: BaseException) -> bool:
    """True if ``exc`` signals transient API degradation that a retry might clear.

    Covers connection drops and timeouts (``APIConnectionError`` and its
    ``APITimeoutError`` subclass) and overloaded/rate-limited/5xx responses.
    Client-side errors (bad request, auth) are NOT degraded and should fail fast.
    """
    if isinstance(exc, anthropic.APIConnectionError):  # includes APITimeoutError
        return True
    return getattr(exc, "status_code", None) in _DEGRADED_STATUS


# HTTP statuses with which a provider refuses a request before generating anything, and bills nothing for it: a
# malformed or too large request, a key or permission refused, a model not found, a rate limit (the audit loop's
# AL1-10, 2026-11-14: such a refusal had kept its whole reservation, so an expired key used up a session's cap in two
# or three attempts with nothing billed).
_UNBILLED_STATUS = frozenset({400, 401, 403, 404, 413, 422, 429})


def unbilled_refusal(exc: BaseException) -> int | None:
    """The status with which the provider answered a request it refused unbilled (``_UNBILLED_STATUS``: the SDKs'
    ``APIStatusError`` carries it as ``status_code``), else None: a transport failure, a timeout, a cancellation or any
    other status, whose bill is not known; and None for any error once the provider has accepted the request
    (``accepted``), whatever its status."""
    if _ACCEPTED.get():
        return None
    status = getattr(exc, "status_code", None)
    return status if type(status) is int and status in _UNBILLED_STATUS else None


# whether the request being sent in this context has been accepted by its provider: a background response queued
# (``OpenAIClient._respond``). An error after that, a poll or a cancellation refused with 429 or 404 among them, leaves
# its bill unknown (the audit loop's AL2: such a refusal had been settled at $0 while the response it polled was billed)
_ACCEPTED: ContextVar[bool] = ContextVar("adroit_request_accepted", default=False)


def accepted() -> None:
    """Note that the request being sent in this context was accepted by its provider (``unbilled_refusal``)."""
    _ACCEPTED.set(True)

# Token prices live in adroit.core.pricing (one table for budget, eval
# estimates, and the dashboard). Rough per-image input-token estimate for the
# fallback budget path that cannot see billed usage (a ~1MP figure is ~1.5k tokens).
_IMAGE_TOKEN_ESTIMATE = 1500
# Server-side prompt caching (2026-09-25 rework; docs/remediation_plan.md). The
# API caches the request prefix tools -> system -> messages up to a cache_control
# breakpoint, but only when that prefix reaches the model's minimum (1,024 tokens
# on Sonnet 5 / Opus 4.8); a shorter marked prefix is skipped at no cost. So the
# client always marks the system prompt (instructions + JSON schema), and a user
# message may carry a STABLE prefix -- library context shared by many calls,
# e.g. the family catalogue or one family's card -- ahead of its per-call
# content. Agents join the two with CACHE_SPLIT (:func:`with_cached_prefix`);
# only the real client acts on it, sending the stable part as its own content
# block with a breakpoint, while fakes, the local cache and the offline client
# see one plain string.
CACHE_SPLIT = "\n\n<<cache-split>>\n\n"
CacheTTL = Literal["5m", "1h"]


def with_cached_prefix(stable: str, variable: str) -> str:
    """Join a stable, cacheable prefix and the per-call content of one user message."""
    return f"{stable}{CACHE_SPLIT}{variable}"


def _cache_control(ttl: CacheTTL) -> dict:
    """The breakpoint marker: 5-minute (default) or 1-hour ephemeral cache."""
    return {"type": "ephemeral"} if ttl == "5m" else {"type": "ephemeral", "ttl": "1h"}


def _join_split(message: dict) -> dict:
    """A message with any CACHE_SPLIT replaced by a blank line (caching disabled)."""
    content = message.get("content")
    if isinstance(content, str) and CACHE_SPLIT in content:
        return {**message, "content": content.replace(CACHE_SPLIT, "\n\n")}
    return dict(message)


def _usage_payload(response: object) -> dict:
    """The billed token counts of one response, for the provenance event payload."""
    usage = getattr(response, "usage", None)
    return {k: getattr(usage, k, 0) or 0 for k in
            ("input_tokens", "output_tokens", "cache_read_input_tokens",
             "cache_creation_input_tokens")}


def _split_cached_prefix(messages: list[dict], ttl: CacheTTL) -> list[dict]:
    """Turn a CACHE_SPLIT in the first user message into [stable (breakpoint), rest]."""
    out = [dict(m) for m in messages]
    for m in out:
        if m.get("role") != "user":
            continue
        content = m["content"]
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else list(content)
        for i, block in enumerate(blocks):
            text = block.get("text", "") if block.get("type") == "text" else ""
            if CACHE_SPLIT in text:
                stable, rest = text.split(CACHE_SPLIT, 1)
                blocks[i:i + 1] = [{"type": "text", "text": stable,
                                    "cache_control": _cache_control(ttl)},
                                   {"type": "text", "text": rest}]
                m["content"] = blocks
                return out
        return out  # only the first user message can hold the shared prefix
    return out


def _dispatch(client: object, request: dict, send: Callable[..., object]) -> object:
    """Apply the installed budget to each individual request, including retries. A client without its provider's key
    is refused here, before the budget reserves anything and before any dispatch (``MissingCredentials``)."""
    missing = getattr(client, "missing_credentials", "")
    if missing:
        raise MissingCredentials(missing)
    budget = getattr(client, "request_budget", None)
    return budget.request(request, send) if budget is not None else send(**request)


def _estimate_tokens(text: str) -> int:
    """Rough token count for cost accounting (~4 characters per token)."""
    return max(1, len(text) // 4)


@runtime_checkable
class StructuredLLM(Protocol):
    """Interface every LLM client (real, fake, caching) implements."""

    def complete_structured(
        self, system: str, messages: list[dict], response_model: type[BaseModel],
        images: list[str | Path] | None = None, **kwargs: object,
    ) -> BaseModel:
        """Return a validated instance of ``response_model`` for the given prompt."""
        ...

    async def complete_structured_async(
        self, system: str, messages: list[dict], response_model: type[BaseModel],
        images: list[str | Path] | None = None, **kwargs: object,
    ) -> BaseModel:
        """Awaitable form of :meth:`complete_structured` for concurrent fan-out."""
        ...


def _image_block(path: str | Path) -> dict:
    """Build a base64 image content block from a local image path."""
    p = Path(path)
    media_type = _MEDIA_TYPES.get(p.suffix.lower())
    if media_type is None:
        raise ValueError(f"unsupported image type {p.suffix!r} for {p}")
    data = base64.standard_b64encode(p.read_bytes()).decode("ascii")
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


def _attach_images(messages: list[dict], images: list[str | Path]) -> list[dict]:
    """Return a copy of ``messages`` with image blocks added to the last user turn."""
    out = [dict(m) for m in messages]
    for m in reversed(out):
        if m["role"] == "user":
            text = m["content"] if isinstance(m["content"], str) else ""
            m["content"] = [{"type": "text", "text": text}, *(_image_block(i) for i in images)]
            return out
    raise ValueError("images given but no user message to attach them to")


def _bounded_image_material(request: dict, provider: str) -> tuple[dict,int]:
    """Bound Anthropic inline images without treating base64 bytes as text tokens.

    Provider vision docs (checked 2026-10-09) cap native visual tokens at 4784
    for high-resolution models, 1568 otherwise. Reserve 8192 per verified inline
    image including ample framing; URL/file-id images remain unsupported here.
    https://platform.claude.com/docs/en/build-with-claude/vision
    """
    from PIL import Image
    count=0
    def clean(value):
        nonlocal count
        if isinstance(value,list):
            return [clean(x) for x in value]
        if isinstance(value,dict):
            if value.get('type') in ('image','image_url','input_image'):
                source=value.get('source',{})
                if provider!='anthropic' or value.get('type')!='image' or source.get('type')!='base64':
                    raise ValueError('budgeted vision requires verified Anthropic inline image bytes')
                data=base64.b64decode(source.get('data',''),validate=True)
                if not data or len(data)>5_000_000:
                    raise ValueError('image exceeds the supported byte limit')
                from adroit.core.images import opened
                with opened(data,'image exceeds the supported dimension limit') as im:
                    if max(im.size)>8000 or im.width*im.height>64_000_000:
                        raise ValueError('image exceeds the supported dimension limit')
                    mime=Image.MIME.get(im.format)
                    if mime!=source.get('media_type'):
                        raise ValueError('image bytes do not match declared media type')
                    im.verify()
                count+=1
                return {'type':'image','source':{'type':'base64','media_type':mime,'data':'bounded image'}}
            return {k:clean(v) for k,v in value.items()}
        return value
    return clean(request),8192*count


def journalled_text(response: object) -> str:
    """The answer's text in a response as the budgeted client journals it (``state: received``), whatever its
    provider: Anthropic's text blocks (``content``), else OpenAI's ``output_text``, else the ``output_text`` parts of
    its output messages; "" for anything else, a damaged record included. The one reader of journalled answers
    (the independent audit, NA15-02, 2026-11-16: recovery read Anthropic's shape alone, so an OpenAI answer already
    paid for was asked for, and paid for, again)."""
    if not isinstance(response, dict):
        return ""
    content = response.get("content")
    if isinstance(content, list):
        text = "".join(b.get("text", "") for b in content
                       if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str))
        if text:
            return text
    if isinstance(response.get("output_text"), str) and response["output_text"]:
        return response["output_text"]
    return "".join(part["text"] for item in response.get("output") or []
                   if isinstance(item, dict) and item.get("type") == "message"
                   for part in item.get("content") or []
                   if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str))


def _extract_json(text: str) -> str:
    """Strip optional markdown code fences (with or without newlines) and return the JSON."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped[3:]
        if stripped.startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.rsplit("```", 1)[0]
    return stripped.strip()


class LLMClient:
    """A structured-output client wrapping the Anthropic Messages API."""

    provider = "anthropic"

    def __init__(self, *, model: str | None = None, api_key: str | None = None,
                 max_tokens: int = 4096, provenance_store: ProvenanceStore | None = None,
                 client: object | None = None, use_prompt_caching: bool = True,
                 usage_hook: Callable[..., None] | None = None,
                 cache_ttl: CacheTTL = "5m", timeout_s: float = _REQUEST_TIMEOUT_S) -> None:
        """Create a client. Pass ``client`` to inject a stub (tests never hit the network). ``timeout_s`` bounds one
        request: a reply of many output tokens (G11's drafts, 32,000) needs longer than the default.

        ``usage_hook(model, input_tokens, output_tokens, cache_read, cache_creation,
        *, cache_creation_1h)`` is invoked once per API *request* with the billed token counts from the
        response -- including the extra requests made by validation retries -- so a
        budget wrapper can charge actual spend rather than an estimate.
        :class:`BudgetedLLMClient` registers itself here automatically when the slot
        is free. ``use_prompt_caching`` puts a ``cache_control`` breakpoint on the
        system prompt and on a user message's stable prefix (see
        :func:`with_cached_prefix`) so repeats bill at the cached-read rate;
        ``cache_ttl`` is ``"5m"`` (bursty interactive runs) or ``"1h"`` (evaluation
        sweeps, where the same prompt recurs every ~10-15 minutes).
        """
        settings = get_settings()
        self.model = model or settings.llm_model
        self.max_tokens = max_tokens
        self.provenance_store = provenance_store
        self.use_prompt_caching = use_prompt_caching
        self.cache_ttl = cache_ttl
        self.usage_hook = usage_hook
        key = (api_key or settings.anthropic_api_key.get_secret_value()).strip()
        url, refused = endpoint(self.provider)
        self.endpoint = host(url)
        self.missing_credentials = "" if client is not None else key_problem(self.provider, key) or refused
        sendable = key if not self.missing_credentials else "not-set"      # never a refused key, never sent anyway
        self._client = client if client is not None else anthropic.Anthropic(
            api_key=sendable, base_url=url, max_retries=_MAX_API_RETRIES, timeout=timeout_s)
        # A separate fast-fail client for cheap health pings (no retries, short timeout).
        self._probe_client = None if client is not None else anthropic.Anthropic(
            api_key=sendable, base_url=url, max_retries=0, timeout=_PROBE_TIMEOUT_S)

    def ping(self) -> bool:
        """Cheap health probe: True if the API answers, False if degraded.

        Raises a non-degraded error (e.g. auth) rather than masking it, so a real
        configuration problem is not mistaken for a transient outage.
        """
        try:
            _dispatch(self, dict(model=self.model, max_tokens=4,
                      messages=[{"role": "user", "content": "ping"}]),
                      (self._probe_client or self._client).messages.create)
            return True
        except Exception as exc:  # noqa: BLE001 - degraded -> False, anything else re-raised
            if is_degraded_error(exc):
                return False
            raise

    def complete_structured(
        self, system: str, messages: list[dict], response_model: type[BaseModel],
        images: list[str | Path] | None = None, *, model: str | None = None,
        max_tokens: int | None = None, run_id: str | None = None, actor: str = "llm_client",
        max_retries: int = 2,
    ) -> BaseModel:
        """Request, parse, and validate a ``response_model`` instance, retrying on failure.

        On a JSON/validation error the offending output and the error are appended to
        the conversation and the model is asked again, up to ``max_retries`` times.

        Raises:
            ValueError: if no valid response is obtained within the retry budget.
        """
        request, convo, system_prompt = self.request_for(system, messages, response_model, images, model=model,
                                                         max_tokens=max_tokens)
        model, max_tokens, system_payload = request["model"], request["max_tokens"], request["system"]

        last_error = ""
        started = time.perf_counter()
        for _ in range(max_retries + 1):
            response = _dispatch(self, dict(model=model, max_tokens=max_tokens,
                                 system=system_payload, messages=convo), self._client.messages.create)
            self._report_usage(model, response)
            text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
            if not text.strip() and getattr(response, "stop_reason", "") == "max_tokens":
                # The whole output budget went to reasoning: the same request again would too, and is billed.
                last_error = (f"the response used all {max_tokens} output tokens before any answer; raise "
                              "max_tokens (not retried)")
                self._log_failed_attempt(run_id, actor, model, system_prompt, convo, text, response, last_error,
                                         time.perf_counter() - started)
                raise ValueError(f"no {response_model.__name__}: {last_error}")
            try:
                result = response_model.model_validate_json(_extract_json(text))
                self._log(run_id, actor, model, system_prompt, convo, result, response,
                          time.perf_counter() - started)
                return result
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                # Failed attempts were still billed: leave them in provenance too,
                # so a cost audit from the event log sees every paid request.
                self._log_failed_attempt(run_id, actor, model, system_prompt, convo, text,
                                         response, last_error,
                                         time.perf_counter() - started)
                convo = convo + [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": f"That was not valid: {last_error}. "
                     "Respond with ONLY a JSON object matching the schema."},
                ]
        raise ValueError(f"no valid {response_model.__name__} after "
                         f"{max_retries + 1} attempts: {last_error}")

    def request_for(self, system: str, messages: list[dict], response_model: type[BaseModel],
                    images: list[str | Path] | None = None, *, model: str | None = None,
                    max_tokens: int | None = None) -> tuple[dict, list[dict], str]:
        """The first request ``complete_structured`` sends, its conversation and its system prompt; the rehearsal
        (``agents.rehearsal``) prices it without sending it."""
        model = model or self.model
        max_tokens = max_tokens or self.max_tokens
        convo = _attach_images(messages, images) if images else [dict(m) for m in messages]
        convo = (_split_cached_prefix(convo, self.cache_ttl) if self.use_prompt_caching
                 else [_join_split(m) for m in convo])
        system_prompt = self._schema_system(system, response_model)
        return (dict(model=model, max_tokens=max_tokens, system=self._system_payload(system_prompt), messages=convo),
                convo, system_prompt)

    async def complete_structured_async(
        self, system: str, messages: list[dict], response_model: type[BaseModel],
        images: list[str | Path] | None = None, **kwargs: object,
    ) -> BaseModel:
        """Run :meth:`complete_structured` in a worker thread so calls can overlap.

        The Anthropic call blocks on network I/O; delegating to a thread lets many
        independent completions proceed concurrently under ``asyncio.gather``
        without a native async client, and yields results identical to the
        sequential path.
        """
        return await asyncio.to_thread(
            self.complete_structured, system, messages, response_model, images, **kwargs)

    def _log_failed_attempt(self, run_id: str | None, actor: str, model: str,
                            system_prompt: str, convo: list[dict], text: str,
                            response: object, error: str, latency: float) -> None:
        """Record a billed-but-invalid attempt to provenance (if configured)."""
        if self.provenance_store is None or run_id is None:
            return
        usage = getattr(response, "usage", None)
        record = LLMCallRecord(
            model=model, prompt_text=json.dumps({"system": system_prompt, "messages": convo}),
            response_text=text,
            prompt_tokens=getattr(usage, "input_tokens", None),
            completion_tokens=getattr(usage, "output_tokens", None),
            total_tokens=(getattr(usage, "input_tokens", 0) or 0)
            + (getattr(usage, "output_tokens", 0) or 0),
            latency_s=latency,
        )
        self.provenance_store.log_event(
            run_id=run_id, actor=actor, event_type=EventType.llm_called,
            payload={"validation_error": error[:500], "usage": _usage_payload(response)},
            llm=record)

    def _system_payload(self, system_prompt: str):
        """The system prompt as sent: a text block with a cache breakpoint.

        The (system + JSON schema) prefix is byte-identical across an agent's
        calls. It is always marked: below the model's minimum cacheable length
        the API skips the breakpoint at no cost, and above it (alone or together
        with a user message's stable prefix) repeats bill at the cached-read rate.
        """
        if self.use_prompt_caching:
            return [{"type": "text", "text": system_prompt,
                     "cache_control": _cache_control(self.cache_ttl)}]
        return system_prompt

    def _report_usage(self, model: str, response: object) -> None:
        """Feed one request's billed token counts to the usage hook, if registered.

        Per the Anthropic API, ``usage.input_tokens`` EXCLUDES cached tokens:
        cache reads and cache writes are reported separately as
        ``cache_read_input_tokens`` / ``cache_creation_input_tokens``, so passing
        all four counts never double-charges.
        """
        if self.usage_hook is None:
            return
        read, written, written_1h = self._cache_usage(response)
        usage = getattr(response, "usage", None)
        self.usage_hook(model, getattr(usage, "input_tokens", 0) or 0,
                        getattr(usage, "output_tokens", 0) or 0, read, written,
                        cache_creation_1h=written_1h)

    def _cache_usage(self, response: object) -> tuple[int, int, int]:
        """(cache reads, cache writes, of which 1-hour writes) for one response.

        1-hour writes bill at 2x input rather than 1.25x; the API reports them in
        ``usage.cache_creation.ephemeral_1h_input_tokens`` when it breaks writes
        down, else every write is attributed to this client's TTL.
        """
        usage = getattr(response, "usage", None)
        read = getattr(usage, "cache_read_input_tokens", 0) or 0
        written = getattr(usage, "cache_creation_input_tokens", 0) or 0
        breakdown = getattr(usage, "cache_creation", None)
        one_hour = getattr(breakdown, "ephemeral_1h_input_tokens", None) if breakdown else None
        if not isinstance(one_hour, int):
            one_hour = written if self.cache_ttl == "1h" else 0
        return read, written, one_hour

    @staticmethod
    def _schema_system(system: str, response_model: type[BaseModel]) -> str:
        """Append the required JSON schema to the system prompt."""
        schema = json.dumps(response_model.model_json_schema())
        return (f"{system}\n\nRespond with ONLY a single JSON object conforming to this "
                f"JSON schema, with no prose and no code fences:\n{schema}")

    def _log(self, run_id: str | None, actor: str, model: str, system_prompt: str,
             convo: list[dict], result: BaseModel, response: object, latency: float) -> None:
        """Record the call to the provenance store if one is configured."""
        if self.provenance_store is None or run_id is None:
            return
        usage = getattr(response, "usage", None)
        prompt_text = json.dumps({"system": system_prompt, "messages": convo})
        record = LLMCallRecord(
            model=model, prompt_text=prompt_text, response_text=result.model_dump_json(),
            prompt_tokens=getattr(usage, "input_tokens", None),
            completion_tokens=getattr(usage, "output_tokens", None),
            total_tokens=(getattr(usage, "input_tokens", 0) or 0)
            + (getattr(usage, "output_tokens", 0) or 0),
            latency_s=latency,
        )
        self.provenance_store.log_event(
            run_id=run_id, actor=actor, event_type=EventType.llm_called,
            payload={"response_type": type(result).__name__, "usage": _usage_payload(response)},
            llm=record)

    def count_tokens(self, system: str, messages: list[dict],
                     response_model: type[BaseModel] | None = None,
                     model: str | None = None) -> int:
        """Exact input-token count of a request as this client would send it (free API).

        Used to check that a cacheable prefix reaches the model's minimum length.
        """
        system_prompt = self._schema_system(system, response_model) if response_model else system
        convo = [_join_split(m) for m in messages]
        result = self._client.messages.count_tokens(
            model=model or self.model, system=system_prompt, messages=convo)
        return int(result.input_tokens)


def _ask_for_json(convo: list[dict]) -> list[dict]:
    """The conversation, its last message asking for JSON if no message mentions it.

    OpenAI's JSON mode refuses a request whose input messages never contain the
    word "json", even when the instructions do.
    """
    if any("json" in str(m.get("content", "")).lower() for m in convo) or not convo:
        return convo
    last = dict(convo[-1])
    last["content"] = f"{last['content']}\n\nRespond with the JSON object."
    return [*convo[:-1], last]


class OpenAIClient:
    """A structured-output client for OpenAI models: DM8's second, independent derivation.

    The same interface as :class:`LLMClient`, on OpenAI's Responses API in JSON mode: the
    reply is validated against the Pydantic model and, on failure, retried with the error.
    The ``openai`` package is imported only when no stub ``client`` is injected, so the
    offline suite does not need it. Billed usage goes to ``usage_hook`` (reasoning tokens
    are output tokens); cached input is charged at the model's cache-read price.
    """

    provider = "openai"

    def __init__(self, *, model: str, api_key: str | None = None, max_tokens: int = 32_000,
                 reasoning_effort: str | None = None, provenance_store: ProvenanceStore | None = None,
                 client: object | None = None, usage_hook: Callable[..., None] | None = None,
                 timeout_s: float = _REQUEST_TIMEOUT_S, background: bool = False,
                 poll_s: float = 5.0, deadline_s: float = 1800.0) -> None:
        """Create a client; pass ``client`` to inject a stub (tests never hit the network).

        ``timeout_s`` bounds one HTTP request. A reasoning model can think for longer
        than a server holds a connection open; a request cut off is retried, and may
        still be billed. With ``background``, the request is queued and returns at
        once, and the client polls for the result every ``poll_s`` seconds: no
        connection is held while the model thinks. A response not finished within
        ``deadline_s`` is cancelled (which stops its billing) and counts as a failure.
        """
        self.background, self.poll_s, self.deadline_s = background, poll_s, deadline_s
        self.model = model
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self.provenance_store = provenance_store
        self.usage_hook = usage_hook
        key = (api_key or get_settings().openai_api_key.get_secret_value()).strip()
        url, refused = endpoint(self.provider)
        self.endpoint = host(url)
        self.missing_credentials = "" if client is not None else key_problem(self.provider, key) or refused
        if client is None:
            import openai  # noqa: PLC0415 - optional: only the paid checker needs it
            # a placeholder where the key cannot be used: the SDK refuses a client without one, and the request is
            # refused before dispatch anyway (``_dispatch``), with what to do
            client = openai.OpenAI(api_key=key if not self.missing_credentials else "not-set", base_url=url,
                                   max_retries=_MAX_API_RETRIES, timeout=timeout_s)
        self._client = client

    def request_for(self, system: str, messages: list[dict], response_model: type[BaseModel],
                    images: list[str | Path] | None = None, *, model: str | None = None,
                    max_tokens: int | None = None) -> tuple[dict, list[dict], str]:
        """The first request ``complete_structured`` sends, its conversation and its instructions (see
        ``LLMClient.request_for``)."""
        if images:
            raise ValueError("OpenAIClient takes text only")
        instructions = LLMClient._schema_system(system, response_model)
        convo = _ask_for_json([_join_split(m) for m in messages])
        extra = {"reasoning": {"effort": self.reasoning_effort}} if self.reasoning_effort else {}
        return (dict(model=model or self.model, instructions=instructions, input=convo,
                     max_output_tokens=max_tokens or self.max_tokens, text={"format": {"type": "json_object"}}, **extra),
                convo, instructions)

    def complete_structured(
        self, system: str, messages: list[dict], response_model: type[BaseModel],
        images: list[str | Path] | None = None, *, model: str | None = None,
        max_tokens: int | None = None, run_id: str | None = None, actor: str = "llm_client",
        max_retries: int = 2,
    ) -> BaseModel:
        """Request, parse and validate a ``response_model`` instance, retrying on failure.

        Raises:
            ValueError: if no valid response is obtained within the retry budget, or images are given.
        """
        request, convo, instructions = self.request_for(system, messages, response_model, images, model=model,
                                                        max_tokens=max_tokens)
        model = request["model"]
        last_error, started = "", time.perf_counter()
        for _ in range(max_retries + 1):
            response = _dispatch(self, {**request, "input": convo}, self._respond)
            usage = getattr(response, "usage", None)
            tokens = (getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0)
            cached = getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", 0) or 0
            if self.usage_hook is not None:      # input_tokens includes the cached ones
                self.usage_hook(model, tokens[0] - cached, tokens[1], cached, 0, cache_creation_1h=0)
            text = getattr(response, "output_text", "") or ""
            try:
                result = response_model.model_validate_json(_extract_json(text))
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                self._log(run_id, actor, model, instructions, convo, text, tokens, started, last_error)
                convo = convo + [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": f"That was not valid: {last_error}. "
                     "Respond with ONLY a JSON object matching the schema."}]
                continue
            self._log(run_id, actor, model, instructions, convo, result.model_dump_json(), tokens, started)
            return result
        raise ValueError(f"no valid {response_model.__name__} after "
                         f"{max_retries + 1} attempts: {last_error}")

    def _respond(self, **request: object) -> object:
        """One response: directly, or queued in the background and polled until it is done.

        Raises:
            TimeoutError: if a background response is not done by the deadline (it is cancelled).
            RuntimeError: if a background response fails or is cancelled.
        """
        if not self.background:
            return self._client.responses.create(**request)
        started = time.monotonic()                  # every blocking operation counts against the deadline (NA15-11)
        response = self._client.responses.create(background=True, store=True, **request)
        accepted()                                  # queued: billable, whatever a poll then answers (AL2)
        def preserve(answer):
            budget = getattr(self, "request_budget", None)
            if budget is not None:
                raw = answer.model_dump(mode="json") if hasattr(answer, "model_dump") else vars(answer)
                budget._journal(dict(state="background_received", response=raw))
        preserve(response)
        while getattr(response, "status", "completed") in ("queued", "in_progress"):
            elapsed = time.monotonic() - started     # its transport and journal included, not the sleeps alone
            if elapsed >= self.deadline_s:          # (the independent audit, NA15-11, 2026-11-16: a poll that
                cancelled = self._client.responses.cancel(response.id)   # took 10 s had counted as none, and
                if cancelled is not None:                                # another was started; "after 2 s" said)
                    preserve(cancelled)
                raise TimeoutError(f"no response after {elapsed:.0f} s (the deadline {self.deadline_s:g} s); cancelled")
            time.sleep(min(self.poll_s, self.deadline_s - elapsed))
            response = self._client.responses.retrieve(response.id)
            preserve(response)
        if getattr(response, "status", "completed") not in ("completed", "incomplete"):
            raise RuntimeError(f"the response ended {response.status}: {getattr(response, 'error', '')}")
        return response

    async def complete_structured_async(
        self, system: str, messages: list[dict], response_model: type[BaseModel],
        images: list[str | Path] | None = None, **kwargs: object,
    ) -> BaseModel:
        """Run :meth:`complete_structured` in a worker thread so calls can overlap."""
        return await asyncio.to_thread(
            self.complete_structured, system, messages, response_model, images, **kwargs)

    def _log(self, run_id: str | None, actor: str, model: str, instructions: str, convo: list[dict],
             text: str, tokens: tuple[int, int], started: float, error: str = "") -> None:
        """Record one billed request (valid or not) to the provenance store, if configured."""
        if self.provenance_store is None or run_id is None:
            return
        record = LLMCallRecord(
            model=model, prompt_text=json.dumps({"system": instructions, "messages": convo}),
            response_text=text, prompt_tokens=tokens[0], completion_tokens=tokens[1],
            total_tokens=sum(tokens), latency_s=time.perf_counter() - started)
        payload = {"usage": {"input_tokens": tokens[0], "output_tokens": tokens[1]}}
        if error:
            payload["validation_error"] = error[:500]
        self.provenance_store.log_event(run_id=run_id, actor=actor, event_type=EventType.llm_called,
                                        payload=payload, llm=record)


class FakeLLMClient:
    """Offline stand-in that returns canned Pydantic objects from a FIFO queue."""

    def __init__(self, responses: list[BaseModel] | None = None, *, model: str = "fake-model",
                 provenance_store: ProvenanceStore | None = None) -> None:
        """Seed the queue with ``responses``; each call pops the next one."""
        self.model = model
        self.provenance_store = provenance_store
        self._queue: list[BaseModel] = list(responses or [])
        self.calls: list[dict] = []

    def enqueue(self, response: BaseModel) -> None:
        """Add a canned response to the back of the queue."""
        self._queue.append(response)

    @property
    def call_count(self) -> int:
        """Number of ``complete_structured`` calls made so far."""
        return len(self.calls)

    def complete_structured(
        self, system: str, messages: list[dict], response_model: type[BaseModel],
        images: list[str | Path] | None = None, *, run_id: str | None = None,
        actor: str = "fake_llm", **kwargs: object,
    ) -> BaseModel:
        """Return the next canned response, recording the call and optional provenance."""
        self.calls.append({"system": system, "messages": messages,
                           "response_model": response_model, "images": images})
        if not self._queue:
            raise RuntimeError("FakeLLMClient queue is empty")
        result = self._queue.pop(0)
        if self.provenance_store is not None and run_id is not None:
            self.provenance_store.log_event(
                run_id=run_id, actor=actor, event_type=EventType.llm_called,
                payload={"response_type": type(result).__name__},
                llm=LLMCallRecord(model=self.model, prompt_text=system,
                                  response_text=result.model_dump_json()))
        return result

    async def complete_structured_async(
        self, system: str, messages: list[dict], response_model: type[BaseModel],
        images: list[str | Path] | None = None, **kwargs: object,
    ) -> BaseModel:
        """Awaitable form of :meth:`complete_structured` (delegates in a thread)."""
        return await asyncio.to_thread(
            self.complete_structured, system, messages, response_model, images, **kwargs)


class CachingLLMClient:
    """Memoizes structured completions in a local SQLite cache keyed by (model, prompt)."""

    def __init__(self, inner: StructuredLLM, cache_path: str | Path, namespace: str = "") -> None:
        """Wrap ``inner``, persisting results under ``cache_path``.

        ``namespace`` is mixed into every cache key, so distinct systems (e.g. the
        full pipeline vs. a baseline) never share cache entries even when a prompt
        coincides -- keeping benchmark comparisons fair and independently cached.
        """
        self._inner = inner
        self._namespace = namespace
        self._path = Path(cache_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False + a lock lets concurrent async fan-out (which runs
        # each call in a worker thread) share one connection safely.
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS llm_cache "
                "(key TEXT PRIMARY KEY, model TEXT, response_json TEXT)")
            self._conn.commit()

    @property
    def model(self) -> str:  # pragma: no cover - passthrough
        """The wrapped client's model id (``unknown`` if it does not expose one)."""
        return getattr(self._inner, "model", "unknown")

    @staticmethod
    def _image_fingerprint(path: str | Path) -> str:
        """Content hash of an image so the cache keys on what the model SEES.

        Keying on the path alone would serve a stale response after a figure is
        regenerated at the same location; an unreadable path falls back to the
        path string (the subsequent real call will raise the real error).
        """
        try:
            return sha256(Path(path).read_bytes()).hexdigest()
        except OSError:
            return str(path)

    def _key(self, model: str, system: str, messages: list[dict],
             response_model: type[BaseModel], images: list[str | Path] | None) -> str:
        material = json.dumps(
            {"namespace": self._namespace, "model": model, "system": system,
             "messages": messages, "schema": response_model.model_json_schema(),
             "images": [self._image_fingerprint(p) for p in images or []]},
            sort_keys=True, default=str)
        return sha256(material.encode("utf-8")).hexdigest()

    def complete_structured(
        self, system: str, messages: list[dict], response_model: type[BaseModel],
        images: list[str | Path] | None = None, *, model: str | None = None,
        **kwargs: object,
    ) -> BaseModel:
        """Return a cached result if present, else delegate to the wrapped client and store it."""
        effective_model = model or getattr(self._inner, "model", "unknown")
        key = self._key(effective_model, system, messages, response_model, images)
        with self._lock:  # DB read only; the network call below runs unlocked for concurrency
            row = self._conn.execute(
                "SELECT response_json FROM llm_cache WHERE key = ?", (key,)).fetchone()
        if row is not None:
            return response_model.model_validate_json(row[0])
        forwarded = {**kwargs}
        if model is not None:
            forwarded["model"] = model
        result = self._inner.complete_structured(system, messages, response_model, images,
                                                  **forwarded)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO llm_cache (key, model, response_json) VALUES (?, ?, ?)",
                (key, effective_model, result.model_dump_json()))
            self._conn.commit()
        return result

    async def complete_structured_async(
        self, system: str, messages: list[dict], response_model: type[BaseModel],
        images: list[str | Path] | None = None, **kwargs: object,
    ) -> BaseModel:
        """Awaitable form of :meth:`complete_structured` (cache hit or delegated call)."""
        return await asyncio.to_thread(
            self.complete_structured, system, messages, response_model, images, **kwargs)


def role_for_actor(actor: str) -> str:
    """Map a provenance actor name to its model-routing role.

    ``tabular_ingest`` / ``figure_ingest`` / ``text_ingest`` -> ``ingest``;
    ``suitability_agent`` -> ``suitability`` (likewise construction/refinement);
    ``tournament_plausibility`` -> ``plausibility``; anything else is its own role.
    """
    if actor.endswith("_ingest"):
        return "ingest"
    if actor == "tournament_plausibility":
        return "plausibility"
    return actor.removesuffix("_agent")


class RoleRoutedLLM:
    """Routes each structured call to a per-role model, keyed by the call's ``actor``.

    This is the cost lever the build plan asks for ("LLM models per role"): e.g.
    a Haiku-class model for ingestion, the default Sonnet-class model for the
    agents, an Opus-class override for hard steps. Wrap it OUTERMOST --
    ``RoleRoutedLLM(CachingLLMClient(BudgetedLLMClient(LLMClient(...))))`` -- so
    the routed model is part of the cache key and of the budget's per-model
    pricing. An explicit ``model=`` at a call site always wins; an actor whose
    role is not in the map falls through to the inner client's default model.
    """

    def __init__(self, inner: StructuredLLM, models_by_role: dict[str, str]) -> None:
        """Wrap ``inner`` with a role -> model-id map (ids pre-resolved by the caller)."""
        self._inner = inner
        self._models = dict(models_by_role)

    @property
    def model(self) -> str:  # pragma: no cover - passthrough
        """The wrapped client's model id (``unknown`` if it does not expose one)."""
        return getattr(self._inner, "model", "unknown")

    def _route(self, model: str | None, actor: str) -> str | None:
        return model or self._models.get(role_for_actor(actor))

    def complete_structured(
        self, system: str, messages: list[dict], response_model: type[BaseModel],
        images: list[str | Path] | None = None, *, model: str | None = None,
        actor: str = "llm_client", **kwargs: object,
    ) -> BaseModel:
        """Delegate with the role's model injected (explicit ``model`` wins)."""
        return self._inner.complete_structured(
            system, messages, response_model, images,
            model=self._route(model, actor), actor=actor, **kwargs)

    async def complete_structured_async(
        self, system: str, messages: list[dict], response_model: type[BaseModel],
        images: list[str | Path] | None = None, **kwargs: object,
    ) -> BaseModel:
        """Awaitable form of :meth:`complete_structured` (delegates in a thread)."""
        return await asyncio.to_thread(
            self.complete_structured, system, messages, response_model, images, **kwargs)


# Keep the actual adapter types even when a CLI test replaces a constructor.
_RESERVATION_CLIENT_TYPES = (LLMClient, OpenAIClient)


def client_for(model: str, max_tokens: int = 8192):
    """The provider's structured-output client for a model id: OpenAI's for ``gpt-*``, else Anthropic's."""
    return OpenAIClient(model=model, max_tokens=max_tokens) if model.startswith("gpt-") else LLMClient(
        model=model, max_tokens=max_tokens)


_PREFLIGHT: ContextVar[Callable[[str], None] | None] = ContextVar("adroit_preflight", default=None)


@contextmanager
def preflight(show: Callable[[str], None]) -> Iterator[None]:
    """Show, before each paid request is dispatched, its model, the hard cap and its reserved (largest possible)
    cost, for every budgeted client made inside this block (hard rule 6)."""
    token = _PREFLIGHT.set(show)
    try:
        yield
    finally:
        _PREFLIGHT.reset(token)


def preflight_line(model: str, reserved: float, committed: float, cap: float | None, at: str = "") -> str:
    """One paid request's preflight: the model, the host it is sent to (AL3-26), its reservation and the cap it
    counts against."""
    limit = f"the ${cap:.2f} hard cap" if cap is not None else "no cap"
    refused = cap is not None and committed + reserved > cap
    return (f"paid request: {model}{f' at {at}' if at else ''}; reserving up to ${reserved:.4f} before dispatch; "
            f"committed ${committed:.4f} of {limit}" + ("; this exceeds the cap, so it is not sent" if refused else ""))


def reservation(provider: str, request: dict) -> float:
    """A request's largest possible cost, reserved before dispatch (``BudgetedLLMClient``) and shown by the
    rehearsal (``agents.rehearsal``)."""
    model = request["model"]
    p_in, p_out = bounded_price(model)
    bounded,visual_tokens=_bounded_image_material(request,provider)
    material = json.dumps(bounded, ensure_ascii=False)
    # Text encodings cannot emit more tokens than UTF-8 bytes. Allow ample
    # framing/schema overhead, and reject long-context price tiers. Images
    # need a separately bounded pixel-token calculation; do not estimate them.
    tokens = visual_tokens + len(material.encode("utf-8")) + 4096 + 256 * len(request.get("messages", request.get("input", [])))
    if tokens > 200_000:
        raise ValueError("Request may enter an unpriced long-context tier; no request dispatched")
    output = request.get("max_tokens", request.get("max_output_tokens"))
    if not isinstance(output, int) or output <= 0:
        raise ValueError("A positive maximum output-token count is required")
    # Worst-case one-hour cache writes; output includes reasoning tokens.
    cost = tokens * p_in * (2 if provider == "anthropic" else 1) + output * p_out
    return cost


def _opened(own: Path) -> Path | None:
    """The workbench run's paid ledger that ``own`` leads to now, among those this process opened (``budget.OPENED``,
    as it is now: a run in another thread may open one meanwhile), by the name it was opened by; None where none."""
    from adroit.agents.budget import OPENED
    from adroit.core.durable import one_entry
    for opened in list(OPENED):
        if opened == str(own) or one_entry(own, opened):
            return Path(opened)
    return None


class BudgetedLLMClient:
    """Reserve each paid request's upper cost before dispatch and settle usage.

    Wrap inside ``CachingLLMClient`` so local cache hits are free. Received
    responses are journalled before parsing; retries reserve independently.
    Uncertain bills retain their reservations. Fake clients use estimates only.
    """

    def __init__(self, inner: StructuredLLM, *, dollar_budget: float | None = None,
                 account: BudgetAccount | None = None, ledger_path: str | Path | None = None) -> None:
        """Wrap a client; share ``account`` across providers in a single command."""
        if account is not None and dollar_budget is not None:
            raise ValueError("Set the cap on the shared account, not on each client")
        self._inner = inner
        self.account = account or BudgetAccount(dollar_budget)
        self.announce = _PREFLIGHT.get()             # the preflight display in force when the client was made
        self.spent = 0.0
        self.calls = 0
        self.input_tokens = self.output_tokens = 0
        self.cache_read_tokens = self.cache_creation_tokens = 0
        self._lock = threading.Lock()
        self.ledger: list[dict] = []
        self.ledger_path = Path(ledger_path) if ledger_path else (get_settings().runs_dir / "budgets") / f"{uuid4().hex}.jsonl"
        self._held: dict[Path, Held | None] = {}     # what this client last read or wrote of each ledger (``_journal``)
        # the ledger it journals to for its life (``_ledger``): its run's, as opened, where its path names one now; else
        # fixed at its first entry
        self._bound: Path | None = _opened(Path(os.path.abspath(self.ledger_path)))
        self._actuals = isinstance(inner, _RESERVATION_CLIENT_TYPES)
        # a caller's durable identity for the next requests (the fresh audit's F19-05): journalled with each
        # reservation, so that a response received before a crash can be found and used instead of asked again
        self.invocation = ""
        if not self._actuals and not isinstance(inner, FakeLLMClient):
            raise ValueError("Client has no bounded request adapter; only the explicit offline fake may use estimates")
        if self._actuals:
            if getattr(inner, "request_budget", None) is not None:
                raise ValueError("This client already has a request budget")
            inner.request_budget = self

    @property
    def dollar_budget(self) -> float | None:
        """The shared command cap (settled plus outstanding costs)."""
        return self.account.cap

    @dollar_budget.setter
    def dollar_budget(self, value: float | None) -> None:
        """Change the shared command cap, validated first."""
        BudgetAccount(value)  # validate before changing a running account
        with self.account._lock:
            self.account.cap = value

    def _journal(self, event: dict) -> None:
        """Persist every request and received response before parsing or retrying: each line written whole in one
        call, flushed and synced to the disk before the request goes on (the consolidation plan's M3), so a crash
        leaves at most a torn last line, which ``budget.recover_torn_tail`` names and recovers. Each line is appended
        only where the ledger is still the one this client's account was read from, or this client last wrote
        (``durable.append_held``; ``_first_held``): one removed, replaced, emptied, cut short or leading nowhere since
        is refused (``ChangedRecord``), nothing written to it and nothing made in its place, so that what was spent
        before is never lost from it, and a request whose reservation is refused is never sent (the auditor's DN recheck,
        DO-01, 2026-11-08: a link to nothing put in a session's ledger's place between two requests had been made
        anew by the second's reservation, which was sent, and the ledger then held only it). The whole ledger, what
        another writer appended since included, must be one its writers could have kept (``budget.journal_whole``):
        nothing is written after a torn or damaged line. A write that fails once begun (the ledger may hold part or all
        of the line) leaves the account knowing it no longer knows what the ledger holds (``unjournalled``): it reserves
        nothing more, and a reservation whose write so failed is kept, uncertain, never sent (the auditor's DO recheck,
        DP-01, 2026-11-09: a reservation's write cut short, or written whole and its sync failed, had been released,
        and the same client's next request sent, written after the torn line, or the two accounts apart). Once its
        request is sent (every entry but its reservation), any failure to journal one of its entries, refused before
        anything was written or not, leaves the account so too: the ledger then holds less than happened, and the account keeps the request's
        reservation (the auditor's DP recheck, DQ-01, 2026-11-09: a settlement whose append was refused had been settled in
        the live account, which then sent a request against less than the ledger held, one a fresh account refused).
        The ledger is its account's, or its run's, by the name that was read or opened, whatever path leads this
        client to it (``_ledger``; the auditor's DT recheck, DU-02, 2026-11-10)."""
        from adroit.core.durable import append_held
        line = (json.dumps(event, default=lambda x: vars(x)) + "\n").encode()
        sent = event.get("state") != "reserved"          # every other entry is journalled once its request is sent
        with self._lock, _JOURNAL_LOCK:
            path = Path(os.path.abspath(self.ledger_path))
            try:
                path = self._ledger()
                if path not in self._held:
                    self._held[path] = self._first_held(path)
                self._held[path] = append_held(path, line, self._held[path], whole=self._whole(path))
            except BaseException as error:
                # refused before anything was written (a ValueError: ``ChangedRecord``, a ledger that cannot be read),
                # or failed once begun, when the ledger may hold part or all of it
                if sent or not isinstance(error, ValueError):
                    why = (f"the {event.get('state')} entry of a request already sent could not be journalled" if sent
                           else "a write to this paid ledger failed once begun")
                    said = f"{why} ({type(error).__name__}: {error})"
                    if sent:                        # known incomplete: said beside its ledger for every reading (DV-02)
                        from adroit.agents.budget import leave_unjournalled
                        left = leave_unjournalled(self._noticed(path), str(event.get("id", "")),
                                                  str(event.get("state", "")), said)
                        said += f"; {left}" if left else ""
                    with self.account._lock:
                        self.account.unjournalled = self.account.unjournalled or f"{path}: {said}"
                raise
            self.ledger.append(event)

    def _sendable(self) -> None:
        """``UnknownLedger`` where the account froze (``BudgetAccount.unjournalled``) since this request was
        reserved, another client's write to the ledger having failed: the request is kept, never sent. It is read the
        last moment before the provider is called: a request already past it is in flight, and its entries are
        journalled as any other's (the auditor's DP recheck, DQ-04, 2026-11-09: a request reserved before the freeze had been
        sent after it)."""
        if frozen := self.account.unjournalled:
            raise UnknownLedger(frozen)

    def _noticed(self, path: Path) -> Path:
        """The ledger beside which a request's missing entry is said (``budget.leave_unjournalled``): its account's,
        else the one this client is bound to (``_ledger``), else ``path``."""
        if self.account.journal is not None:
            return Path(os.path.abspath(self.account.journal))
        return self._bound or path

    def _ledger(self) -> Path:
        """The paid ledger this client journals to (``_journal``), by the name it was read or opened by: its
        account's, where its account was read from one (``BudgetAccount.journal``: a session's); a workbench job's,
        by the name its run opened it by (``budget.OPENED``); else its own (``ledger_path``). Its own path must name
        that ledger, as it leads now: one entry in one folder, however its folders are reached (a link to one of
        them on the way: ``durable.one_entry``), never by its spelling alone. Where its account was read from a ledger
        its own path does not name, it is refused (``ChangedRecord``), nothing journalled or sent: an account's
        holding and whole-ledger check (``_first_held``, ``_whole``) are of its own ledger, and are never set aside
        for a client of it journalling elsewhere (the auditor's DT recheck, DU-02, 2026-11-10: a client of a session's
        account, given the session's ledger through a link to its folder, was matched to it by its spelling, and so
        appended under every ledger's check, not its session's, and sent a request while the session's record and
        its ledger disagreed, as the same client by its own path was refused). The ledger chosen is written to by the
        name it is chosen by, so a path that leads elsewhere once it is chosen never leads the append there: it is
        made, and its checks made, under that ledger's own writers' lock (``durable.append_held``).

        A client not of an account keeps one ledger for its life (``_bound``): its run's, as opened, where its path
        names one when it is made, else the one it first journals to; a path that leads elsewhere since is refused
        (``ChangedRecord``), nothing journalled, never taken as another ledger (the auditor's DU recheck, DV-01, 2026-11-10:
        a run's client given its ledger through a link to its run's folder, the link then led to an empty folder,
        had begun another journal there and sent its request, and the run's page had read its ledger as all it spent).
        Before its request is sent, nothing is; after, the account freezes (``_journal``)."""
        from adroit.core.durable import ChangedRecord, one_entry
        own = Path(os.path.abspath(self.ledger_path))
        if self.account.journal is not None:
            journal = Path(os.path.abspath(self.account.journal))
            if own == journal or one_entry(own, journal):
                return journal
            raise ChangedRecord(f"{own}: not this client's account's paid ledger ({journal}), which its account was "
                                "read from: a client of an account journals only to the ledger it was read from, "
                                "under its checks; nothing is journalled or sent")
        if self._bound is None:                     # its first entry: its run's ledger, opened since it was made, or its own
            self._bound = _opened(own) or own
        if own == self._bound or one_entry(own, self._bound):
            return self._bound
        raise ChangedRecord(f"{own}: it no longer leads to {self._bound}, the paid ledger this client journals to "
                            "(its run's as opened, or the one it first journalled to): a client keeps its ledger for "
                            "its life, and is never given another by a path that leads elsewhere; nothing is "
                            "journalled or sent")

    def _whole(self, path: Path) -> Callable[[bytes, Path], None]:
        """The whole-ledger check an append to ``path`` is made under (``durable.append_held``): its account's own for
        its account's ledger, where it has one (a session's, its cap raises its record's: ``BudgetAccount.whole``,
        DQ-03); else every paid ledger's (``budget.journal_whole``). ``path`` is the ledger as ``_ledger`` names it."""
        from adroit.agents.budget import journal_whole
        journal = self.account.journal
        if self.account.whole is not None and journal is not None and Path(os.path.abspath(journal)) == path:
            return self.account.whole
        return journal_whole

    def _first_held(self, path: Path) -> Held | None:
        """What the ledger at ``path`` held before this client's first line there: for its account's own ledger (a
        session's), what it held when the account was read from it (``BudgetAccount.held``); for a workbench job's,
        what it held once its run opened it (``budget.OPENED``); for another, what is there now (None where nothing
        is: it is made anew, never through a link). One there that cannot be read is damaged (``ValueError``).
        ``path`` is the ledger as ``_ledger`` names it."""
        from adroit.agents.budget import OPENED, ledger_held
        journal = self.account.journal
        if journal is not None and Path(os.path.abspath(journal)) == path:
            return self.account.held
        if str(path) in OPENED:
            return OPENED[str(path)]
        return ledger_held(path)

    def _reservation(self, request: dict) -> tuple[str, float]:
        provider = self._inner.provider
        return provider, reservation(provider, request)

    def request(self, request: dict, send: Callable[..., object]) -> object:
        """Reserve, dispatch once, preserve the response and settle known usage."""
        provider, bound = self._reservation(request)
        at = getattr(self._inner, "endpoint", "")
        if self.announce is not None:
            self.announce(preflight_line(request["model"], bound, self.account.committed(), self.account.cap, at))
        key = self.account.reserve(provider, bound)
        own = at in ("", host(PROVIDER_ENDPOINTS.get(provider, "")))
        try:
            self._journal(dict(id=key, state="reserved", provider=provider,
                               model=request["model"], reserved_usd=bound,
                               **({} if own else {"endpoint": at}),           # another host, named (AL3-26)
                               **({"invocation": self.invocation} if self.invocation else {})))
        except BaseException:
            if not self.account.unjournalled:   # nothing was written, and no dispatch occurred
                self.account.release(key)
            raise                               # else the ledger may hold it: kept, uncertain, never sent (DP-01)
        self._sendable()
        sending = _ACCEPTED.set(False)
        try:
            response = send(**request)
        except BaseException as error:
            refused = unbilled_refusal(error)
            if refused is None:
                self._journal(dict(id=key, state="billing_uncertain", error=type(error).__name__))
                raise  # retain the reservation, including on cancellation/timeouts
            # refused before any generation: settled at $0, journalled before the account settles it (AL1-10)
            self._journal(dict(id=key, state="settled", cost_usd=0.0, bound_exceeded=False, refused=refused,
                               error=type(error).__name__))
            self.account.settle(key, 0.0)
            raise
        finally:
            _ACCEPTED.reset(sending)
        raw = response.model_dump(mode="json") if hasattr(response, "model_dump") else vars(response)
        self._journal(dict(id=key, state="received", response=raw))
        usage = getattr(response, "usage", None)
        if usage is None:
            self._journal(dict(id=key, state="billing_uncertain", error="missing usage"))
            return response
        inputs, outputs = getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None)
        if not isinstance(inputs, int) or not isinstance(outputs, int) or min(inputs, outputs) < 0:
            self._journal(dict(id=key, state="billing_uncertain", error="invalid usage"))
            return response
        if provider == "anthropic":
            read, written, hour = self._inner._cache_usage(response)
        else:
            read = getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", 0) or 0
            inputs, written, hour = inputs - read, 0, 0
        if any(not isinstance(v, int) or v < 0 for v in (inputs, outputs, read, written, hour)) or hour > written:
            self._journal(dict(id=key, state="billing_uncertain", error="invalid cache usage"))
            return response
        actual = self._record_usage(request["model"], inputs, outputs, read, written,
                                    cache_creation_1h=hour)
        # journalled before the account settles it: the account settles only what its ledger holds (DQ-01)
        self._journal(dict(id=key, state="settled", cost_usd=actual,
                           bound_exceeded=actual > bound))
        self.account.settle(key, actual)
        # settle atomically freezes this provider if a pricing contract changed.
        return response

    def _record_usage(self, model: str, input_tokens: int, output_tokens: int,
                      cache_read: int = 0, cache_creation: int = 0, *,
                      cache_creation_1h: int = 0) -> float:
        """Charge one API request's actual billed usage (invoked by the inner client).

        ``input_tokens`` excludes cached tokens (API semantics); cache reads bill
        at 10% of the input price, 5-minute cache writes at 125% and 1-hour
        writes (``cache_creation_1h`` of the ``cache_creation`` total) at 200%.
        """
        p_in, p_out = price_per_token(model)
        written_5m = max(0, cache_creation - cache_creation_1h)
        cost = (input_tokens * p_in + output_tokens * p_out
                + cache_read * cache_read_price(model)
                + written_5m * p_in * CACHE_WRITE_MULT
                + cache_creation_1h * p_in * CACHE_WRITE_1H_MULT)
        with self._lock:
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens
            self.cache_read_tokens += cache_read
            self.cache_creation_tokens += cache_creation
            self.spent += cost
        return cost

    @property
    def model(self) -> str:  # pragma: no cover - passthrough
        """The wrapped client's model id (``unknown`` if it does not expose one)."""
        return getattr(self._inner, "model", "unknown")

    def _guard(self) -> None:
        """Raise before making a call if the budget is already spent."""
        if self.dollar_budget is not None and self.spent >= self.dollar_budget:
            raise BudgetExceeded(self.spent, self.dollar_budget)

    def _charge_estimate(self, model: str, system: str, messages: list[dict],
                         response_model: type[BaseModel], images: list[str | Path] | None,
                         result: BaseModel) -> None:
        """Fallback accounting: estimate one call's cost from text lengths.

        Counts the JSON schema that :class:`LLMClient` appends to the system prompt
        and a flat allowance per image, so the estimate errs honest rather than low.
        """
        in_tok = (_estimate_tokens(system)
                  + _estimate_tokens(json.dumps(messages, default=str))
                  + _estimate_tokens(json.dumps(response_model.model_json_schema()))
                  + _IMAGE_TOKEN_ESTIMATE * len(images or []))
        out_tok = _estimate_tokens(result.model_dump_json())
        p_in, p_out = price_per_token(model)
        with self._lock:
            self.input_tokens += in_tok
            self.output_tokens += out_tok
            self.spent += in_tok * p_in + out_tok * p_out

    def complete_structured(
        self, system: str, messages: list[dict], response_model: type[BaseModel],
        images: list[str | Path] | None = None, *, model: str | None = None, **kwargs: object,
    ) -> BaseModel:
        """Delegate through per-request reservations; stop before an unfunded dispatch.

        In actual-usage mode even a *failed* structured call is charged (its API
        requests were billed); the failure then propagates unchanged.
        """
        if not self._actuals:
            self._guard()
        try:
            result = self._inner.complete_structured(system, messages, response_model, images,
                                                     model=model, **kwargs)
        except BudgetExceeded as error:
            error.ledger_path = str(self.ledger_path)
            raise
        finally:
            with self._lock:
                self.calls += 1
        if not self._actuals:
            self._charge_estimate(model or self.model, system, messages, response_model,
                                  images, result)
        return result

    async def complete_structured_async(
        self, system: str, messages: list[dict], response_model: type[BaseModel],
        images: list[str | Path] | None = None, **kwargs: object,
    ) -> BaseModel:
        """Awaitable form of :meth:`complete_structured` (delegates in a thread)."""
        return await asyncio.to_thread(
            self.complete_structured, system, messages, response_model, images, **kwargs)
