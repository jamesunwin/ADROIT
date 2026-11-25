"""The browser layer's DevTools connection, after the auditor's DP recheck (2026-11-09): its connection to a promotion's tab
had broken (``BrokenPipeError``) while the tab lived on, and the wait polled the dead connection until its deadline;
Chrome's own output had gone nowhere. Offline: a socket and Chrome's DevTools endpoints simulated, no Chrome started."""

from __future__ import annotations

import json
import socket
import struct

from tests.orchestrator.test_browser_layer import _load


class _Socket:
    """A socket whose reads come in the ``chunks`` given (``None``: a read that times out), and which records what is
    sent and each timeout set."""

    def __init__(self, chunks=()):
        self.chunks, self.sent, self.timeouts = list(chunks), b"", []

    def recv(self, n):
        if not self.chunks:
            raise socket.timeout()
        chunk = self.chunks.pop(0)
        if chunk is None:
            raise socket.timeout()
        return chunk

    def sendall(self, data):
        self.sent += data

    def settimeout(self, value):
        self.timeouts.append(value)

    def close(self):
        pass


def _ws(browser, chunks=()):
    ws = object.__new__(browser.WebSocket)
    ws.sock, ws.buffer, ws.deadline = _Socket(chunks), b"", 0.0
    return ws


def _text_frame(text: str) -> bytes:
    payload = text.encode()
    return bytes([0x81, 126]) + struct.pack(">H", len(payload)) + payload


def test_a_message_whose_deadline_passes_part_way_is_read_whole_next_time():
    """A read whose deadline passes part way through a frame keeps what it read: the next reading returns the whole
    message, never one read from the middle of a frame (before, the frame's header was lost, and the stream read
    from its payload on)."""
    import pytest
    browser = _load("browser")
    frame = _text_frame(json.dumps({"id": 1, "result": {"value": "x" * 300}}))
    ws = _ws(browser, [frame[:6], None])
    with pytest.raises(TimeoutError):
        ws.receive(deadline=0.0)
    ws.sock.chunks = [frame[6:]]
    assert json.loads(ws.receive(deadline=0.0)) == {"id": 1, "result": {"value": "x" * 300}}


def test_a_frame_is_sent_whole_under_its_own_timeout():
    """A frame is sent under ``SEND_TIMEOUT``, never the reads' one-second poll, which is set again after it."""
    browser = _load("browser")
    ws = _ws(browser)
    ws.send("{}")
    assert ws.sock.timeouts == [browser.SEND_TIMEOUT, 1.0] and ws.sock.sent[0] == 0x81


class _Answers:
    """A DevTools connection that answers each call (``result`` {}), records its methods, and fails with ``broken``
    while ``broken`` is set."""

    def __init__(self, broken=None):
        self.methods, self.broken, self.pending = [], broken, []

    def send(self, text):
        if self.broken is not None:
            raise self.broken
        message = json.loads(text)
        self.methods.append(message["method"])
        self.pending.append(json.dumps({"id": message["id"], "result": {"result": {"value": "done"}}}))

    def receive(self, deadline):
        return self.pending.pop(0)

    sock = _Socket()


def test_a_connection_chrome_closed_is_made_again_to_the_same_tab_and_said(tmp_path, monkeypatch):
    """A wait whose connection Chrome closed makes a new one to the same tab, its domains enabled and its console watch
    added again, and waits on: nothing is navigated, reloaded, clicked or typed. It is said, with the end of Chrome's
    own log; the wait's value is read through the new connection."""
    browser = _load("browser")
    log = tmp_path / "chrome.log"
    log.write_text("[ERROR:devtools_http_handler.cc] SIMULATED: a connection closed\n")
    fresh = _Answers()
    monkeypatch.setattr(browser, "local_get", lambda url, timeout=30.0, method="GET": json.dumps(
        [{"id": "other", "webSocketDebuggerUrl": "ws://127.0.0.1:1/other"},
         {"id": "tab", "webSocketDebuggerUrl": "ws://127.0.0.1:1/tab"}]).encode())
    made = []
    monkeypatch.setattr(browser, "WebSocket", lambda url: made.append(url) or fresh)
    page = browser.Page(_Answers(BrokenPipeError(32, "Broken pipe")), "tab", 9222, log)
    assert page.wait(lambda: page.evaluate("document.title") == "done", "the run to end", timeout=5, every=0.01)
    assert made == ["ws://127.0.0.1:1/tab"] and page.ws is fresh
    assert fresh.methods == ["Page.enable", "Runtime.enable", "Page.addScriptToEvaluateOnNewDocument",
                             "Runtime.evaluate"]
    assert len(page.reattached) == 1 and "made again to the same tab: nothing reloaded or done again" in \
        page.reattached[0] and "BrokenPipeError" in page.reattached[0] and "SIMULATED: a connection closed" in \
        page.reattached[0]


def test_a_tab_that_is_gone_is_not_made_again_and_the_wait_fails_as_before(tmp_path, monkeypatch):
    """Where the tab is gone, no connection is made again: the wait fails at its deadline, naming its first error and
    when, and the attempt is said; at most ``REATTACH_LIMIT`` attempts are made."""
    import pytest
    browser = _load("browser")
    monkeypatch.setattr(browser, "local_get", lambda url, timeout=30.0, method="GET": b"[]")
    page = browser.Page(_Answers(BrokenPipeError(32, "Broken pipe")), "tab", 9222, None)
    with pytest.raises(TimeoutError, match="first error at .*BrokenPipeError"):
        page.wait(lambda: page.evaluate("1"), "the run to end", timeout=0.3, every=0.01)
    assert len(page.reattached) == browser.REATTACH_LIMIT
    assert all("could not be made again" in line for line in page.reattached)

