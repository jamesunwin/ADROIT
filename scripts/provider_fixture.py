"""A provider fixture on this machine (the release browser layer's, the gap plan's G5, 2026-10-25): a standard-library
HTTP server on 127.0.0.1 answering ``POST /v1/messages`` as Anthropic's Messages API does, without streaming, so that
a run's real budgeted client and journal go through a real transport at $0.

Its answer to a request is chosen by the JSON schema the client puts in the system prompt (the response model's
title: ``ANSWERS``, the same canned answers the headless tests use), with fixed usage (``USAGE``: 100 input and 20
output tokens), so the dollars are known. What it does with each request is planned (``plan``):

- ``answer``: the canned answer;
- ``hold``: nothing until ``release()`` (a barrier: the request is in flight, its run's child process alive), then the
  next planned behaviour, or an answer;
- ``close``: the request read, the connection closed without a response (a connection lost after receipt: the bill is
  unknown);
- ``error``: an overloaded (529) error, which the provider does not bill.

Every request is logged (``received`` and the JSON lines file given): its arrival, the schema's title, the SDK's
retry count and what was done with it. ``python scripts/provider_fixture.py`` serves until interrupted.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

USAGE = {"input_tokens": 100, "output_tokens": 20}
SCHEMA_MARK = "conforming to this JSON schema, with no prose and no code fences:\n"


def _intake_proposals() -> str:
    from tests.ui.test_run_outcomes import proposals
    return proposals()


def _discovery_report() -> str:
    from tests.orchestrator.test_constraint_discovery import _proposals
    return _proposals().model_dump_json()


def _extraction_answer() -> str:
    from adroit.agents.experimental_extraction import ExtractionAnswer
    return ExtractionAnswer(explanation="fixture: nothing transcribed from the selected units",
                            ambiguities=["the provider fixture answers without reading the source"]).model_dump_json()


ANSWERS = {"ModelProposals": _intake_proposals,           # the response model's title -> its canned JSON answer
           "DiscoveryReport": _discovery_report, "ExtractionAnswer": _extraction_answer}


def schema_title(body: dict) -> str:
    """The title of the JSON schema the client asked for ("" where it asked for none)."""
    system = body.get("system", "")
    if isinstance(system, list):
        system = "".join(block.get("text", "") for block in system if isinstance(block, dict))
    if SCHEMA_MARK not in system:
        return ""
    try:
        return json.loads(system.split(SCHEMA_MARK, 1)[1]).get("title", "")
    except (ValueError, AttributeError):
        return ""


class ProviderFixture:
    """The server, its plan and its log (module docstring)."""

    def __init__(self, log: Path | None = None) -> None:
        self.log, self.received, self.planned = log, [], []
        self.lock, self.gate = threading.Lock(), threading.Event()
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self):                        # noqa: N802 - the http.server interface
                fixture._handle(self)

            def log_message(self, *args):
                pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def start(self) -> "ProviderFixture":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.gate.set()
        self.server.shutdown()
        self.server.server_close()

    def plan(self, *behaviours: str) -> None:
        """What to do with the next requests, in order (module docstring); afterwards, ``answer``."""
        with self.lock:
            self.planned += list(behaviours)

    def release(self) -> None:
        """Let a held request go on."""
        self.gate.set()

    def wait_for(self, count: int, timeout: float = 300.0) -> list[dict]:
        """Wait until ``count`` requests have arrived; the log."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if len(self.received) >= count:
                return list(self.received)
            time.sleep(0.2)
        raise TimeoutError(f"the provider fixture received {len(self.received)} requests, not {count}, within "
                           f"{timeout:.0f} s")

    def _next(self) -> str:
        with self.lock:
            return self.planned.pop(0) if self.planned else "answer"

    def _record(self, entry: dict) -> None:
        with self.lock:
            self.received.append(entry)
            if self.log is not None:
                with self.log.open("a") as stream:
                    stream.write(json.dumps(entry) + "\n")

    def _handle(self, handler: BaseHTTPRequestHandler) -> None:
        length = int(handler.headers.get("Content-Length") or 0)
        body = json.loads(handler.rfile.read(length) or b"{}")
        behaviour = self._next()
        entry = {"at": time.time(), "path": handler.path, "schema": schema_title(body), "model": body.get("model"),
                 "retry": handler.headers.get("x-stainless-retry-count", ""), "behaviour": behaviour}
        self._record(entry)
        if behaviour == "hold":
            self.gate.wait()
            self.gate.clear()
            behaviour = self._next()
            entry["after_hold"] = behaviour
        if behaviour == "close":
            handler.close_connection = True
            try:
                handler.connection.shutdown(2)
            except OSError:                      # the client has gone already (its own timeout)
                entry["client_gone"] = True
            return
        if behaviour == "error":
            self._send(handler, 529, {"type": "error", "error": {"type": "overloaded_error",
                                                                  "message": "fixture: overloaded"}})
            return
        answer = ANSWERS.get(entry["schema"])
        if answer is None:
            self._send(handler, 400, {"type": "error", "error": {"type": "invalid_request_error", "message":
                                      f"fixture: no canned answer for the schema {entry['schema']!r}"}})
            return
        self._send(handler, 200, {"id": f"msg_fixture_{uuid.uuid4().hex[:12]}", "type": "message",
                                  "role": "assistant", "model": body.get("model", ""),
                                  "content": [{"type": "text", "text": answer()}], "stop_reason": "end_turn",
                                  "stop_sequence": None, "usage": dict(USAGE)})

    @staticmethod
    def _send(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode()
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(data)))
        handler.send_header("request-id", f"req_fixture_{uuid.uuid4().hex[:12]}")
        handler.end_headers()
        handler.wfile.write(data)


if __name__ == "__main__":
    fixture = ProviderFixture().start()
    print(f"provider fixture at {fixture.url} (Ctrl-C to stop)", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        fixture.stop()
