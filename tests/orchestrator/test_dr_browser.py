"""The browser gate's account of DevTools connections made again, after the auditor's DQ recheck (2026-11-09), DR-02: a
connection to a tab made again during a mutation control had been printed nowhere and counted nowhere (only the
journeys' were), so a summary naming none did not show that none was made. Every connection made again is now said
under its journey's, its control's or Chrome's first navigation's label and counted (``browser_acceptance.said``),
whatever the outcome. Offline: Chrome and its DevTools endpoints simulated; each tab's first connection is closed
(``BrokenPipeError``) during a wait and made again to the same tab by the real ``browser.Page.reattach``."""

from __future__ import annotations

import base64
import contextlib
import json
import sys
from types import SimpleNamespace

import pytest

from tests.orchestrator.test_browser_layer import _load

MUTATION, INVARIANT = "SIMULATED_defect", "SIMULATED invariant"


class _Tab:
    """A DevTools connection to one tab: each call answered (a script's value ``value``, a screenshot's bytes), and
    closed by Chrome (``BrokenPipeError``) at its call after the first ``fails_after``, where set."""

    def __init__(self, value: str = "done", fails_after: int | None = None):
        self.value, self.fails_after, self.pending, self.calls = value, fails_after, [], 0

    def send(self, text):
        if self.fails_after is not None and self.calls >= self.fails_after:
            raise BrokenPipeError(32, "Broken pipe")
        self.calls += 1
        message = json.loads(text)
        result = {"Runtime.evaluate": {"result": {"value": self.value}},
                  "Page.captureScreenshot": {"data": base64.b64encode(b"png").decode()}}.get(message["method"], {})
        self.pending.append(json.dumps({"id": message["id"], "result": result}))

    def receive(self, deadline):
        return self.pending.pop(0)

    def close(self):
        pass

    sock = SimpleNamespace(close=lambda: None)          # what ``reattach`` closes of a connection made again


class _Chrome:
    """A Chrome whose every new tab's first connection is closed during the tab's first wait (or, ``fails_after``,
    after that many calls), its tab then found again at its DevTools endpoint."""

    def __init__(self, harness, value: str = "done", fails_after: int = 0):
        self.harness, self.value, self.fails_after, self.pages, self.log = harness, value, fails_after, [], None

    def page(self):
        page = self.harness.Page(_Tab(self.value, self.fails_after), "tab", 9222, None)
        self.pages.append(page)
        return page


@pytest.fixture
def gate(monkeypatch, tmp_path):
    """The gate, its Chrome simulated, one journey ``fake`` and one mutation control of it (``MUTATION``, its
    invariant ``INVARIANT``); the journey's behaviour set by ``gate.outcome``."""
    gate = _load("browser_acceptance")
    harness = sys.modules["browser"]
    monkeypatch.setattr(harness, "local_get", lambda url, timeout=30.0, method="GET": json.dumps(
        [{"id": "tab", "webSocketDebuggerUrl": "ws://127.0.0.1:1/tab"}]).encode())
    monkeypatch.setattr(harness, "WebSocket", lambda url: _Tab(gate.chrome_value))
    gate.chrome_value, gate.outcome = "done", "passes"

    @contextlib.contextmanager
    def start(chrome, env=None, log=None):
        yield _Chrome(harness, gate.chrome_value)

    def fake(browser, root):
        page = browser.page()
        page.wait(lambda: page.evaluate("document.title") == "done", "the run to end", timeout=5, every=0.01)
        if gate.outcome == "not established":
            raise gate.NotEstablished("SIMULATED: a precondition missing")
        if gate.outcome == "fails" or (gate.outcome == "detects" and gate.browser_harness.MUTATION == MUTATION):
            raise AssertionError(INVARIANT if gate.outcome == "detects" else "SIMULATED: another failure")
        return ["SIMULATED journey"]
    monkeypatch.setattr(gate.Chrome, "start", start)
    monkeypatch.setattr(gate, "child_environment", lambda root, keys=None: {})
    monkeypatch.setattr(gate, "responsive", lambda browser, timeout=600.0: "")
    monkeypatch.setattr(gate.Workbench, "stop_all", classmethod(lambda cls: []))
    monkeypatch.setitem(gate.JOURNEYS, "fake", fake)
    monkeypatch.setattr(gate, "CONTROLS", [("fake", MUTATION, INVARIANT)])
    return gate


def _said(out: str, label: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith(f"  {label}: ") and "made again to the same tab" in
            line and "BrokenPipeError" in line]


@pytest.mark.parametrize("outcome", ["passes", "fails"])
def test_a_journey_s_connection_made_again_is_said_and_counted(gate, tmp_path, capsys, outcome):
    """A journey's tab, its connection closed and made again: said under the journey's label and counted once,
    whether the journey passed or failed."""
    gate.outcome = outcome
    done = gate.run_once("chrome", ["fake"], tmp_path, "[1/2] ", set())
    out = capsys.readouterr().out
    assert done == ((1, 0, 0) if outcome == "passes" else (0, 1, 0)), out
    assert len(_said(out, "[1/2] fake")) == 1 and len(gate.REATTACHED) == 1 and gate.MADE_AGAIN == gate.REATTACHED, \
        out


@pytest.mark.parametrize("outcome", ["detects", "passes", "fails", "not established"])
def test_a_mutation_control_s_connection_made_again_is_said_and_counted(gate, tmp_path, capsys, outcome):
    """DR-02, the auditor's ``dq_reconnect_reporting``: a mutation control's tab, its connection closed and made again:
    said under the control's label and counted once, whether the control detected its defect at its invariant, its
    journey passed with the defect restored, failed elsewhere, or was not established. Before, it was printed nowhere
    and counted nowhere."""
    gate.outcome = outcome
    done = gate.run_controls("chrome", {"fake"}, ["fake"], tmp_path)
    out = capsys.readouterr().out
    assert done == {"detects": (1, 0, 0), "passes": (0, 1, 0), "fails": (0, 1, 0),
                    "not established": (0, 0, 1)}[outcome], out
    assert len(_said(out, f"control fake × {MUTATION}")) == 1, \
        "a connection made again during a mutation control was not said"
    assert len(gate.REATTACHED) == 1 and gate.MADE_AGAIN == gate.REATTACHED, \
        "a connection made again during a mutation control was not counted"


def test_a_connection_made_again_at_chrome_s_first_navigation_is_said_and_counted(monkeypatch, capsys):
    """A fresh Chrome's first navigation (``responsive``), its connection closed once the navigation is asked and
    made again while its page loads: said and counted."""
    gate = _load("browser_acceptance")
    harness = sys.modules["browser"]
    monkeypatch.setattr(harness, "local_get", lambda url, timeout=30.0, method="GET": json.dumps(
        [{"id": "tab", "webSocketDebuggerUrl": "ws://127.0.0.1:1/tab"}]).encode())
    monkeypatch.setattr(harness, "WebSocket", lambda url: _Tab("complete"))
    browser = _Chrome(harness, "complete", fails_after=1)
    assert gate.responsive(browser, timeout=10) == "" and not browser.pages
    out = capsys.readouterr().out
    assert len(_said(out, "Chrome's first navigation")) == 1 and len(gate.REATTACHED) == 1 and \
        gate.MADE_AGAIN == gate.REATTACHED, out


def test_the_summary_counts_every_connection_made_again(gate, tmp_path, capsys):
    """The gate's summary names the connections made again in its journeys and its controls together: none, then
    one of a journey's and one of a control's."""
    assert gate.reattached_clause() == ""
    gate.run_once("chrome", ["fake"], tmp_path / "run", "", set())
    gate.outcome = "detects"
    gate.run_controls("chrome", {"fake"}, ["fake"], tmp_path / "controls")
    assert gate.reattached_clause() == "; 2 DevTools connection(s) to a tab made again, each said above"
