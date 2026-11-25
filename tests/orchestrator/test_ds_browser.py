"""The browser gate's account of attempts to make a DevTools connection to a tab again, after the auditor's DR recheck
(2026-11-09), DS-02: three attempts to reach a tab no longer there, each said as one that could not be made again,
had been counted in the gate's summary as three connections made again. A connection made again is now counted apart
(``browser.Page.made_again``; ``browser_acceptance.MADE_AGAIN``), and the summary names the attempts that failed as
failed (``browser_acceptance.reattached_clause``). Offline: Chrome and its DevTools endpoints simulated, as in
``test_dr_browser``; a tab gone is one absent from its DevTools endpoint's list."""

from __future__ import annotations

import sys

import pytest

from tests.orchestrator.test_dr_browser import gate  # noqa: F401  (the fixture)

NONE_MADE = "; no DevTools connection to a tab made again: 3 attempt(s) failed, each said above"


def _gone(acceptance, monkeypatch):
    """Every tab's first connection closed during a wait (``BrokenPipeError``), and the tab no longer listed at its
    DevTools endpoint: each attempt to make the connection again fails (``StopIteration``). A journey ``gone`` waits on
    it, briefly, and so fails."""
    harness = sys.modules["browser"]
    monkeypatch.setattr(harness, "local_get", lambda url, timeout=30.0, method="GET": b"[]")

    def gone(browser, root):
        page = browser.page()
        page.wait(lambda: page.evaluate("document.title") == "done", "the run to end", timeout=0.5, every=0.01)
        return ["SIMULATED journey"]
    monkeypatch.setitem(acceptance.JOURNEYS, "gone", gone)


def _failed(out: str, label: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith(f"  {label}: ") and "could not be made again "
            "(StopIteration" in line and "BrokenPipeError" in line]


def test_attempts_that_failed_are_said_and_counted_as_failed(gate, tmp_path, capsys, monkeypatch):  # noqa: F811
    """DS-02, the auditor's ``dr_reconnect_failure_v2``: a journey whose tab is gone fails; each of its three attempts to
    make the connection again is said under its label as one that could not be made, none is counted as a connection
    made again, and the summary says so. Before, the summary said "3 DevTools connection(s) to a tab made again"."""
    _gone(gate, monkeypatch)
    done = gate.run_once("chrome", ["gone"], tmp_path, "", set())
    out = capsys.readouterr().out
    assert done == (0, 1, 0), out
    assert len(_failed(out, "gone")) == sys.modules["browser"].REATTACH_LIMIT == len(gate.REATTACHED), out
    assert gate.reattached_clause() == NONE_MADE, "attempts that failed were counted as connections made again"
    assert gate.MADE_AGAIN == []


@pytest.mark.parametrize("outcome", ["detects", "passes", "fails", "not established"])
def test_a_mutation_control_s_attempts_that_failed_are_counted_as_failed(gate, tmp_path, capsys, monkeypatch,  # noqa: F811
                                                                         outcome):
    """A mutation control's tab gone, whatever the control's outcome: its attempts said under the control's label as
    ones that failed, none counted as made again."""
    from tests.orchestrator.test_dr_browser import MUTATION
    monkeypatch.setattr(sys.modules["browser"], "local_get", lambda url, timeout=30.0, method="GET": b"[]")
    gate.outcome = outcome
    gate.run_controls("chrome", {"fake"}, ["fake"], tmp_path)
    out = capsys.readouterr().out
    assert len(_failed(out, f"control fake × {MUTATION}")) == len(gate.REATTACHED) == 3, out
    assert gate.reattached_clause() == NONE_MADE, \
        "attempts that failed during a mutation control were counted as connections made again"
    assert gate.MADE_AGAIN == []


def test_the_summary_counts_connections_made_again_and_attempts_failed_apart(gate, tmp_path, capsys,  # noqa: F811
                                                                             monkeypatch):
    """A journey's connection made again, then another journey's tab gone: the summary names one connection made again
    and three attempts that failed."""
    gate.run_once("chrome", ["fake"], tmp_path / "made", "", set())
    _gone(gate, monkeypatch)
    gate.run_once("chrome", ["gone"], tmp_path / "gone", "", set())
    assert gate.reattached_clause() == "; 1 DevTools connection(s) to a tab made again and 3 attempt(s) to make one " \
                                       "again that failed, each said above", "attempts that failed were counted as made"
    assert len(gate.MADE_AGAIN) == 1 and len(gate.REATTACHED) == 4
