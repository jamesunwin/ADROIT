"""A paid command rehearsed at $0: each request built and priced as the budget gate would, and none sent.

G12's live check L7 found that the DM9 agents on a library-wide result need a cap near $1, although they settle near
$0.25: every request reserves its largest possible cost before it is sent (``llm.reservation``: each UTF-8 byte a
token, the input written to the one-hour cache, every output token used), and a cap below the largest reservation
stops the run partway. The rehearsal runs the command's steps with a client that sends nothing, so the reservations
are known before the first paid request:

- each request is built by the real client's ``request_for`` (with a transport that is never called), so its
  reservation is the one the budget gate would make;
- each reply is the schema's empty answer, so the deterministic steps that follow an answer run on.

Later requests whose content depends on an earlier reply (a variant changing the scout's leaders) are priced as they
would be after an empty reply: an estimate, and it is said so.
"""

from __future__ import annotations

import math
from pathlib import Path

from pydantic import BaseModel

from adroit.agents.llm import LLMClient, OpenAIClient, reservation


class _NoTransport:
    """The stub transport of a client that is never sent anything."""

    def __getattr__(self, name: str):
        raise RuntimeError("the rehearsal sends no request")


class Rehearsal:
    """A structured-output client that sends nothing: it records each request's actor and reservation, and answers
    with the schema's empty reply."""

    def __init__(self, model: str, max_tokens: int = 8192) -> None:
        """``max_tokens`` is the paid client's (``llm.client_for``'s default)."""
        self.model, self.max_tokens = model, max_tokens
        self.requests: list[tuple[str, float]] = []
        provider = "openai" if model.startswith("gpt-") else "anthropic"
        self._client = (OpenAIClient(model=model, max_tokens=max_tokens, client=_NoTransport())
                        if provider == "openai" else LLMClient(model=model, max_tokens=max_tokens,
                                                               client=_NoTransport()))
        self.provider = provider

    def complete_structured(self, system: str, messages: list[dict], response_model: type[BaseModel],
                            images: list[str | Path] | None = None, *, model: str | None = None,
                            max_tokens: int | None = None, actor: str = "llm_client", **_: object) -> BaseModel:
        """Record the request's reservation; return ``response_model``'s empty reply."""
        request, _, _ = self._client.request_for(system, messages, response_model, images, model=model,
                                                 max_tokens=max_tokens)
        self.requests.append((actor, reservation(self.provider, request)))
        try:
            return response_model.model_validate({})
        except ValueError as error:
            raise ValueError(f"{response_model.__name__} has no empty reply: this command cannot be rehearsed") \
                from error

    async def complete_structured_async(self, system: str, messages: list[dict], response_model: type[BaseModel],
                                        images: list[str | Path] | None = None, **kwargs: object) -> BaseModel:
        """As ``complete_structured``."""
        return self.complete_structured(system, messages, response_model, images, **kwargs)

    def suggested_cap(self) -> float:
        """The largest reservation, plus a quarter of the others' (what the requests before it may have settled at:
        they settled at about a tenth in L7), in whole cents rounded up."""
        return math.ceil(100 * (self.largest + 0.25 * (self.total - self.largest))) / 100

    @property
    def largest(self) -> float:
        """The largest single reservation: below it, the command cannot finish."""
        return max((usd for _, usd in self.requests), default=0.0)

    @property
    def total(self) -> float:
        """Every first attempt's reservation together: a cap that finishes even if each costs its most (a reply
        that fails validation is asked again, and each retry reserves its own)."""
        return sum(usd for _, usd in self.requests)
