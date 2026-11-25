"""U0 core tests: gate models, auto-approval semantics, file-channel protocol.

Fully offline and GUI-free; the scientist's side is scripted through the
injectable ``sleep_fn``.
"""

from __future__ import annotations

import json

import pytest

from adroit.orchestrator import gates
from adroit.orchestrator.gates import (
    BudgetConfirmResponse,
    EvidenceReviewResponse,
    FileGateChannel,
    FinalReviewResponse,
    GateRequest,
    ShortlistReviewResponse,
)


def _request(gate_id: str = gates.SHORTLIST_REVIEW, seq: int = 7) -> GateRequest:
    return GateRequest(gate_id=gate_id, run_id="run-g1", seq=seq, stage="shortlist",
                       payload={"families": ["a", "b"]}, created_at=123.0)


# --- auto-approval -----------------------------------------------------------


def test_auto_approve_defaults() -> None:
    auto = gates.AutoApproveGates()
    assert auto.ask(_request(gates.EVIDENCE_REVIEW), EvidenceReviewResponse).approved
    shortlist = auto.ask(_request(), ShortlistReviewResponse)
    assert shortlist.approved and shortlist.family_ids is None
    final = auto.ask(_request(gates.FINAL_REVIEW), FinalReviewResponse)
    assert final.accepted and not final.extra_refinement


def test_auto_approve_never_waves_through_a_requested_budget_gate() -> None:
    request = _request(gates.BUDGET_CONFIRM)
    unrequested = gates.AutoApproveGates()
    assert unrequested.ask(request, BudgetConfirmResponse).approved is True
    requested = gates.AutoApproveGates([gates.BUDGET_CONFIRM])
    assert requested.ask(request, BudgetConfirmResponse).approved is False


# --- file channel --------------------------------------------------------------


class _Responder:
    """A scripted scientist: each poll tick may drop a response file."""

    def __init__(self, run_dir, script) -> None:
        self.run_dir = run_dir
        self.script = list(script)  # one callable (or None) per sleep tick
        self.ticks = 0

    def __call__(self, _delay: float) -> None:
        if self.ticks >= len(self.script):
            raise AssertionError("channel polled longer than the script allows")
        action = self.script[self.ticks]
        self.ticks += 1
        if action is not None:
            action()


def test_round_trip_writes_request_and_honors_response(tmp_path) -> None:
    request = _request()
    answer = ShortlistReviewResponse(approved=True, family_ids=["logistic_growth"])
    responder = _Responder(tmp_path, [
        lambda: gates.respond(tmp_path, 7, gates.SHORTLIST_REVIEW, answer)])
    channel = FileGateChannel(tmp_path, sleep_fn=responder)
    result = channel.ask(request, ShortlistReviewResponse)
    assert result == answer
    # the request file exists, carries the payload, and pending() now says answered
    on_disk = json.loads((tmp_path / "gates" / "7_shortlist_review.request.json")
                         .read_text(encoding="utf-8"))
    assert on_disk["payload"] == {"families": ["a", "b"]}
    assert gates.pending(tmp_path) == []


def test_malformed_response_is_discarded_and_second_honored(tmp_path) -> None:
    response_file = tmp_path / "gates" / "7_shortlist_review.response.json"

    def write_garbage() -> None:
        response_file.parent.mkdir(parents=True, exist_ok=True)
        response_file.write_text('{"approved": tru', encoding="utf-8")

    good = ShortlistReviewResponse(approved=True)
    responder = _Responder(tmp_path, [
        write_garbage, None,
        lambda: gates.respond(tmp_path, 7, gates.SHORTLIST_REVIEW, good)])
    channel = FileGateChannel(tmp_path, sleep_fn=responder)
    # tick 1 drops garbage; the channel deletes it and keeps waiting
    result = channel.ask(_request(), ShortlistReviewResponse)
    assert result == good


def test_semantic_validator_forces_a_reask(tmp_path) -> None:
    known = {"logistic_growth", "oscillator_linear_damped"}

    def check(response: ShortlistReviewResponse) -> None:
        unknown = set(response.family_ids or []) - known
        if unknown:
            raise ValueError(f"unknown family ids: {sorted(unknown)}")

    bad = ShortlistReviewResponse(approved=True, family_ids=["not_a_family"])
    good = ShortlistReviewResponse(approved=True, family_ids=["logistic_growth"])
    responder = _Responder(tmp_path, [
        lambda: gates.respond(tmp_path, 7, gates.SHORTLIST_REVIEW, bad),
        lambda: gates.respond(tmp_path, 7, gates.SHORTLIST_REVIEW, good)])
    channel = FileGateChannel(tmp_path, sleep_fn=responder)
    result = channel.ask(_request(), ShortlistReviewResponse, validate=check)
    assert result == good


def test_timeout_raises_and_leaves_the_request_pending(tmp_path) -> None:
    channel = FileGateChannel(tmp_path, poll_interval_s=1.0,
                              sleep_fn=_Responder(tmp_path, [None, None, None]))
    with pytest.raises(TimeoutError, match="shortlist_review"):
        channel.ask(_request(), ShortlistReviewResponse, timeout_s=2.0)
    (still_pending,) = gates.pending(tmp_path)
    assert still_pending.gate_id == gates.SHORTLIST_REVIEW  # resume will re-ask


def test_resume_reuses_the_existing_request_file(tmp_path) -> None:
    request = _request()
    with pytest.raises(TimeoutError):
        FileGateChannel(tmp_path, poll_interval_s=1.0,
                        sleep_fn=lambda _t: None).ask(
            request, ShortlistReviewResponse, timeout_s=0.0)
    request_file = tmp_path / "gates" / "7_shortlist_review.request.json"
    first_mtime = request_file.stat().st_mtime_ns
    answer = ShortlistReviewResponse(approved=True)
    responder = _Responder(tmp_path, [
        lambda: gates.respond(tmp_path, 7, gates.SHORTLIST_REVIEW, answer)])
    result = FileGateChannel(tmp_path, sleep_fn=responder).ask(
        request, ShortlistReviewResponse)
    assert result == answer
    assert request_file.stat().st_mtime_ns == first_mtime  # not rewritten


def test_pending_orders_by_seq_and_skips_foreign_files(tmp_path) -> None:
    gates_dir = tmp_path / "gates"
    gates_dir.mkdir()
    for seq, gate_id in [(9, gates.FINAL_REVIEW), (3, gates.EVIDENCE_REVIEW)]:
        request = _request(gate_id, seq)
        (gates_dir / f"{seq}_{gate_id}.request.json").write_text(request.to_json(),
                                                                 encoding="utf-8")
    (gates_dir / "0_junk.request.json").write_text("not json", encoding="utf-8")
    result = gates.pending(tmp_path)
    assert [r.seq for r in result] == [3, 9]


# --- U0 wiring additions: interrupts, archiving, the control file ---------------


def test_an_interrupt_aborts_the_wait(tmp_path) -> None:
    from adroit.orchestrator.gates import GateInterrupted
    channel = FileGateChannel(tmp_path, poll_interval_s=0.0, sleep_fn=lambda s: None,
                              interrupt=lambda: "pause")
    with pytest.raises(GateInterrupted) as info:
        channel.ask(_request(), ShortlistReviewResponse)
    assert info.value.action == "pause"
    assert (tmp_path / "gates" / "7_shortlist_review.request.json").is_file()  # still pending


def test_archive_response_keeps_the_answer_but_reopens_the_gate(tmp_path) -> None:
    from adroit.orchestrator.gates import archive_response
    assert archive_response(tmp_path, 3, "budget_confirm", "declined") is None
    gates.respond(tmp_path, 3, "budget_confirm", BudgetConfirmResponse(approved=False))
    kept = archive_response(tmp_path, 3, "budget_confirm", "declined")
    assert kept is not None and kept.is_file() and ".declined." in kept.name
    assert not (tmp_path / "gates" / "3_budget_confirm.response.json").exists()


def test_control_file_request_read_consume(tmp_path) -> None:
    from adroit.orchestrator import control
    assert control.read(tmp_path) is None and control.consume(tmp_path) is None
    control.request(tmp_path, "cancel")
    assert control.read(tmp_path) == "cancel"
    assert control.consume(tmp_path) == "cancel"
    assert control.read(tmp_path) is None
    assert list(tmp_path.glob("control.cancel.*.honored.json"))
    for body in ('{"action": "explode"}', '{ torn', '[1]'):
        (tmp_path / "control.json").write_text(body, encoding="utf-8")
        assert control.read(tmp_path) == "cancel"               # never permission to go on (M3): stopped
    assert control.consume(tmp_path) == "cancel" and list(tmp_path.glob("control.cancel.*.honored.json"))
    with pytest.raises(ValueError):
        control.request(tmp_path, "explode")
