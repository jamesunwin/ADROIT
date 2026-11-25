"""The browser gate's account of attempts to make a DevTools connection to a tab again, after the auditor's DS recheck
(2026-11-10), DT-02: an attempt whose new connection was made, its handshake done, and then closed by Chrome as its
domains were enabled had been said nowhere and counted nowhere, nor counted against the limit of three: five such
attempts were made, and the summary said nothing of them. Each attempt is now counted as it begins and said as what it
came to: made again only once its connection is usable, its domains enabled and its watch added; else as one that could
not be made, its new connection closed (``browser.Page.reattach``). Offline: Chrome and its DevTools endpoints
simulated, as in ``test_dr_browser``."""

from __future__ import annotations

import sys

import pytest

from tests.orchestrator.test_dr_browser import MUTATION, _Tab, gate  # noqa: F401  (the fixture)

# the three calls that make a new connection usable, each where Chrome closes it in turn
STEPS = ("Page.enable", "Runtime.enable", "Page.addScriptToEvaluateOnNewDocument")


class _Made(_Tab):
    """A new DevTools connection to the tab, its handshake made, closed by Chrome (``BrokenPipeError``) at its call
    ``step``; whether it was closed by its maker kept."""

    def __init__(self, step: int):
        super().__init__("done", fails_after=step)
        self.closed = False

    def close(self):
        self.closed = True


def _failing(monkeypatch, step: int, usable_from: int | None = None) -> list[_Tab]:
    """Every new connection made to a tab closed by Chrome at its ``step`` call, or, from the ``usable_from``-th made
    on, usable: the connections made, in order."""
    made: list[_Tab] = []

    def connect(url):
        made.append(_Tab("complete") if usable_from is not None and len(made) >= usable_from else _Made(step))
        return made[-1]
    monkeypatch.setattr(sys.modules["browser"], "WebSocket", connect)
    return made


def _lost(acceptance, monkeypatch, name: str = "lost") -> None:
    """A journey ``name`` waiting, briefly, on its tab, whose first connection Chrome closes: it fails."""
    def lost(browser, root):
        page = browser.page()
        page.wait(lambda: page.evaluate("document.title") == "done", "the run to end", timeout=0.5, every=0.01)
        return ["SIMULATED journey"]
    monkeypatch.setitem(acceptance.JOURNEYS, name, lost)


def _failed(out: str, label: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith(f"  {label}: ") and
            "could not be made again (BrokenPipeError" in line]


NONE_MADE = "; no DevTools connection to a tab made again: 3 attempt(s) failed, each said above"


@pytest.mark.parametrize("step", STEPS)
def test_a_journey_s_attempts_closed_as_they_were_made_usable_are_said_and_counted_as_failed(
        gate, tmp_path, capsys, monkeypatch, step):  # noqa: F811
    """DT-02, the auditor's ``ds_reconnect_enable``: a journey's tab, each new connection to it closed by Chrome at ``step``.
    Three attempts are made, no fourth; each is said under the journey's label as one that could not be made again,
    with its cause, its new connection closed; none is counted as made again, and the summary says so. Before, each
    was said nowhere, counted nowhere, and attempts went on past the three."""
    made = _failing(monkeypatch, STEPS.index(step))
    _lost(gate, monkeypatch)
    done = gate.run_once("chrome", ["lost"], tmp_path, "", set())
    out = capsys.readouterr().out
    assert done == (0, 1, 0), out
    assert len(made) == sys.modules["browser"].REATTACH_LIMIT, "an attempt past the limit was made"
    assert len(_failed(out, "lost")) == 3 == len(gate.REATTACHED), \
        "an attempt that failed once its connection was made was not said, or not counted"
    assert gate.MADE_AGAIN == [] and gate.reattached_clause() == NONE_MADE
    assert all(connection.closed for connection in made), "a connection that could not be made usable was left open"


@pytest.mark.parametrize("step", STEPS)
def test_a_mutation_control_s_attempts_closed_as_they_were_made_usable_are_counted_as_failed(
        gate, tmp_path, capsys, monkeypatch, step):  # noqa: F811
    """The same during a mutation control: said under the control's label as attempts that failed, three, none
    counted as made again."""
    made = _failing(monkeypatch, STEPS.index(step))
    _lost(gate, monkeypatch, "fake")
    gate.run_controls("chrome", {"fake"}, ["fake"], tmp_path)
    out = capsys.readouterr().out
    assert len(made) == 3 and len(_failed(out, f"control fake × {MUTATION}")) == 3 == len(gate.REATTACHED), \
        "an attempt that failed once its connection was made, during a mutation control, was not said or counted"
    assert gate.MADE_AGAIN == [] and gate.reattached_clause() == NONE_MADE


@pytest.mark.parametrize("step", STEPS)
def test_at_chrome_s_first_navigation_attempts_that_failed_and_one_made_again_are_counted_apart(capsys, monkeypatch,
                                                                                               step):
    """A fresh Chrome's first navigation, its connection closed once the navigation is asked: two attempts whose new
    connections Chrome closes at ``step``, then one made again and usable, the page then loaded. Said under the
    first navigation's label and counted apart: one made again, two that failed, their connections closed."""
    from tests.orchestrator.test_dr_browser import _Chrome
    from tests.orchestrator.test_browser_layer import _load
    acceptance = _load("browser_acceptance")
    harness = sys.modules["browser"]
    monkeypatch.setattr(harness, "local_get", lambda url, timeout=30.0, method="GET":
                        b'[{"id": "tab", "webSocketDebuggerUrl": "ws://127.0.0.1:1/tab"}]')
    made = _failing(monkeypatch, STEPS.index(step), usable_from=2)
    assert acceptance.responsive(_Chrome(harness, "complete", fails_after=1), timeout=10) == "", \
        "an attempt that failed once its connection was made stopped Chrome's first navigation, said nowhere"
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.startswith("  Chrome's first navigation: ")]
    assert len(lines) == 3 and len(_failed(out, "Chrome's first navigation")) == 2 and \
        "made again to the same tab" in lines[2], out
    assert len(acceptance.REATTACHED) == 3 and acceptance.MADE_AGAIN == [acceptance.REATTACHED[2]]
    assert acceptance.reattached_clause() == "; 1 DevTools connection(s) to a tab made again and 2 attempt(s) to " \
                                             "make one again that failed, each said above"
    assert made[0].closed and made[1].closed
