"""One press of a launching form starts one request (NP17-01, 2026-11-17).

A rendered form's launching button is wrapped by ``once``. Its press runs the form's handler with the form's
``Submission`` current, and a handler that has started something goes to its page by ``go``, which marks the
submission done. Then:

- a press while the form's handler is still running, or after it has started something, starts nothing: it says so,
  and after a start it goes to that page again (two quick presses of an intake had made two paid sessions, each with
  its own cap: the non-physics audit of ``a7335be``, NP17-01);
- a press the handler refuses (an invalid form, a budget not confirmed) leaves the form open, to be corrected and
  pressed again;
- the button is disabled while its press is handled and once it has started something, as a visible second safeguard;
- a new rendering of the page is a new form, so starting another run is a new submission.

The guard is the server's, not the browser's: NiceGUI handles one rendered page's events in order, and the check and
the mark are made on its event loop, so no two presses of one form both start.
"""

from __future__ import annotations

import inspect
from contextvars import ContextVar
from typing import Any, Callable

from nicegui import ui

_CURRENT: ContextVar["Submission | None"] = ContextVar("adroit_submission", default=None)

ALREADY = "This form has already started its request: opening it again. Reload the page to start another."
BUSY = "This form's request is being started."


class Submission:
    """One rendered form's submission: ``pressed`` while a press is handled, ``target`` (a page) once it started."""

    def __init__(self) -> None:
        self.pressed = False
        self.target: str | None = None


def go(url: str) -> None:
    """Go to ``url``, the page of what the current press started, and mark its form's submission done."""
    form = _CURRENT.get()
    if form is not None:
        form.target = url
    ui.navigate.to(url)


def _takes_event(handler: Callable) -> bool:
    try:
        return any(p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                   for p in inspect.signature(handler).parameters.values())
    except (TypeError, ValueError):
        return False


def once(handler: Callable) -> Callable[[Any], Any]:
    """``handler`` as a launching button's press: at most one start per rendered form (module docstring)."""
    form = Submission()
    takes_event = _takes_event(handler)

    def release(sender: Any) -> None:
        form.pressed = False
        if form.target is None and sender is not None and hasattr(sender, "enable"):
            sender.enable()

    def press(event: Any) -> Any:
        sender = getattr(event, "sender", None)
        if form.target is not None:
            ui.notify(ALREADY)
            ui.navigate.to(form.target)
            return None
        if form.pressed:
            ui.notify(BUSY)
            return None
        form.pressed = True
        if sender is not None and hasattr(sender, "disable"):
            sender.disable()
        token = _CURRENT.set(form)
        try:
            result = handler(event) if takes_event else handler()
        except BaseException:
            release(sender)
            raise
        finally:
            _CURRENT.reset(token)
        if not inspect.isawaitable(result):
            release(sender)
            return None

        async def finish() -> None:              # an async handler: the form stays pressed until it ends
            again = _CURRENT.set(form)
            try:
                await result
            finally:
                _CURRENT.reset(again)
                release(sender)
        return finish()

    return press
