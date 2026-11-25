import json

import pytest

from adroit.evaluation import core
from adroit.evaluation.core import Case, CaseResult, Half, Suite


def _suite(n: int = 40) -> Suite:
    return Suite(name="toy", description="toy",
                 cases=lambda: [Case(suite="toy", id=f"c{i}", inputs={"x": i}) for i in range(n)],
                 run_case=lambda c: CaseResult(case_id=c.id, passed=c.inputs["x"] % 3 != 0, note=f"x={c.inputs['x']}"),
                 summarise=lambda results, cases: {"passed": sum(bool(r.passed) for r in results), "cases": len(cases)})


def test_a_case_keeps_its_half_whatever_else_is_added() -> None:
    first = {c.id: c.half for c in _suite(40).cases()}
    more = {c.id: c.half for c in _suite(400).cases()}
    assert all(more[k] is v for k, v in first.items())
    assert 150 < sum(h is Half.development for h in more.values()) < 250


def test_the_half_depends_on_the_suite_and_the_id() -> None:
    halves = {core.half_of(s, f"c{i}") for s in ("a", "b") for i in range(20)}
    assert halves == {Half.development, Half.held_out}
    assert core.half_of("a", "c1") is core.half_of("a", "c1")


def test_a_development_run_is_stored_but_not_entered_in_the_ledger(store) -> None:
    out = core.run(_suite())
    assert out.half is Half.development and all(core.half_of("toy", r.case_id) is Half.development for r in out.results)
    assert out.summary["cases"] == len(out.results)
    saved = (store / "results" / "toy.jsonl").read_text().splitlines()
    assert len(saved) == 1 and json.loads(saved[0])["half"] == "development"
    assert not (store / "ledger.jsonl").exists()


def test_the_held_out_half_needs_a_reason_and_is_entered_in_the_ledger(store) -> None:
    with pytest.raises(ValueError, match="reason"):
        core.run(_suite(), Half.held_out)
    out = core.run(_suite(), Half.held_out, reason="confirm a change")
    started, entry = [json.loads(line) for line in (store / "ledger.jsonl").read_text().splitlines()]
    assert started["event"] == "started" and entry["event"] == "completed"
    assert entry["suite"] == "toy" and entry["reason"] == "confirm a change" and entry["cases"] == len(out.results)


def test_a_held_out_run_that_crashes_or_is_not_stored_still_leaves_a_ledger_entry(store, monkeypatch) -> None:
    """Release audit minor: the entry was written only after a stored run completed."""
    core.run(_suite(), Half.held_out, reason="unstored", store=False)
    def crash(case):
        raise RuntimeError("crash")
    with pytest.raises(RuntimeError, match="crash"):
        core.run(_suite().model_copy(update={"run_case": crash}), Half.held_out, reason="crashed")
    lines = [json.loads(line) for line in (store / "ledger.jsonl").read_text().splitlines()]
    assert [(e["reason"], e["event"]) for e in lines] == [("unstored", "started"), ("crashed", "started")]
    assert lines[0]["stored"] is False


def test_a_partial_run_is_summarised_on_the_cases_it_ran(store) -> None:
    suite = _suite()
    cases = [c for c in suite.cases() if c.half is Half.development]
    out = core.finish(suite, Half.development, [suite.run_case(c) for c in cases[:3]], cases, "stopped")
    assert out.summary["cases"] == 3 and out.reason == "stopped"
    core.save(out)
    assert (store / "results" / "toy.jsonl").exists()


def test_the_report_lists_the_failed_cases(store) -> None:
    text = core.report(core.run(_suite(), store=False))
    assert "the development half" in text and "| passed |" in text
    assert "Failed cases" in text and "x=" in text
    assert not (store / "results").exists()
