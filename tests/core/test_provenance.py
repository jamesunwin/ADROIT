"""Tests for the append-only provenance store in ``adroit.core.provenance``.

A synthetic damped-oscillator run of ~10 events is logged — including a nested
tool call and an LLM call — then reconstructed and checked for exact equality
against the known original ``RunState``. The exported audit file is parsed back
to confirm it is valid, complete JSON.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adroit.core.provenance import (
    Event,
    EventType,
    LLMCallRecord,
    ProvenanceStore,
)
from adroit.core.state import (
    DataSourceKind,
    DataSourceRef,
    EvidenceState,
    FitResult,
    ModelCandidate,
    ParameterSpec,
    ProblemSpec,
    QualitativeFeature,
    QualitativeFeatureKind,
    RunState,
    RunStatus,
    VariableInfo,
)


def _build_expected_run() -> RunState:
    """Construct the ground-truth RunState the provenance log will encode."""
    problem = ProblemSpec(
        scientific_objective="Explain the decaying oscillation in x(t).",
        admissible_data=[DataSourceRef(kind=DataSourceKind.timeseries, path_or_url="x.csv")],
    )
    evidence = EvidenceState(
        problem_id=problem.id,
        summary="Oscillation with decaying amplitude.",
        variables=[VariableInfo(name="x", units="m", role_guess="observable")],
        qualitative_features=[
            QualitativeFeature(feature=QualitativeFeatureKind.oscillation, confidence=0.95),
            QualitativeFeature(feature=QualitativeFeatureKind.decay, confidence=0.8),
        ],
    )
    c1 = ModelCandidate(
        family_id="linear_damped_sho",
        name="Damped SHO",
        symbolic_form="x'' + 2*gamma*x' + omega0**2*x",
        parameters=[ParameterSpec(name="gamma", prior_low=0.0, prior_high=5.0)],
    )
    c2 = ModelCandidate(
        family_id="undamped_sho",
        name="Undamped SHO",
        symbolic_form="x'' + omega0**2*x",
    )
    fit = FitResult(
        candidate_id=c1.id,
        param_estimates={"gamma": 0.31, "omega0": 6.28},
        loss=0.01,
        aic=-42.0,
        bic=-38.0,
    )
    return RunState(problem=problem, evidence=[evidence], candidates=[c1, c2], fits=[fit])


def _log_synthetic_run(store: ProvenanceStore, run: RunState) -> int:
    """Log ~10 events encoding ``run``; return the number of events written."""
    rid = run.id
    n = 0
    store.log_event(run_id=rid, actor="orchestrator", event_type=EventType.state_created,
                    payload=run.problem)
    n += 1
    load = store.log_event(run_id=rid, actor="ingest_tool", event_type=EventType.tool_called,
                           payload={"tool": "load_csv", "path": "x.csv"})
    n += 1
    # Nested tool call: a child event pointing at the loader above.
    store.log_event(run_id=rid, actor="ingest_tool", event_type=EventType.tool_called,
                    payload={"tool": "detect_columns"}, parent_event_id=load.event_id)
    n += 1
    store.log_event(run_id=rid, actor="ingest_agent", event_type=EventType.state_created,
                    payload=run.evidence[0])
    n += 1
    store.log_event(run_id=rid, actor="suitability_agent", event_type=EventType.llm_called,
                    payload={"purpose": "family shortlist"},
                    llm=LLMCallRecord(model="claude-sonnet-5", prompt_text="Which families fit?",
                                      response_text="damped SHO", prompt_tokens=12,
                                      completion_tokens=5, total_tokens=17, latency_s=0.42))
    n += 1
    store.log_event(run_id=rid, actor="construction_agent", event_type=EventType.state_created,
                    payload=run.candidates[0])
    n += 1
    store.log_event(run_id=rid, actor="construction_agent", event_type=EventType.state_created,
                    payload=run.candidates[1])
    n += 1
    store.log_event(run_id=rid, actor="fit_tool", event_type=EventType.state_created,
                    payload=run.fits[0])
    n += 1
    store.log_event(run_id=rid, actor="adjudicator", event_type=EventType.decision,
                    payload={"chosen": run.candidates[0].id})
    n += 1
    store.log_event(run_id=rid, actor="fit_tool", event_type=EventType.error,
                    payload={"message": "convergence warning on candidate 2"})
    n += 1
    return n


@pytest.fixture()
def store() -> ProvenanceStore:
    """A fresh in-memory provenance store."""
    return ProvenanceStore.open(":memory:")


def test_events_are_ordered_and_counted(store: ProvenanceStore) -> None:
    run = _build_expected_run()
    n = _log_synthetic_run(store, run)
    events = store.get_run_events(run.id)
    assert len(events) == n >= 10
    assert [e.seq for e in events] == sorted(e.seq for e in events)


def test_nested_tool_call_forms_a_tree(store: ProvenanceStore) -> None:
    run = _build_expected_run()
    _log_synthetic_run(store, run)
    events = store.get_run_events(run.id)
    children = [e for e in events if e.parent_event_id is not None]
    assert len(children) == 1
    parent_ids = {e.event_id for e in events}
    assert children[0].parent_event_id in parent_ids  # child references a real event


def test_reconstruct_matches_original(store: ProvenanceStore) -> None:
    run = _build_expected_run()
    _log_synthetic_run(store, run)
    reconstructed = store.reconstruct_run(run.id)
    assert reconstructed == run


def test_snapshot_restores_scalar_fields(store: ProvenanceStore) -> None:
    # shortlist and status are scalars carried only by a full RunState snapshot,
    # not by the typed sub-object events; a snapshot must recover them exactly.
    run = _build_expected_run()
    run.shortlist = [run.candidates[0].family_id]
    run.status = RunStatus.fitted
    _log_synthetic_run(store, run)
    store.log_event(run_id=run.id, actor="orchestrator", event_type=EventType.state_created,
                    payload=run)
    reconstructed = store.reconstruct_run(run.id)
    assert reconstructed == run
    assert reconstructed.shortlist == [run.candidates[0].family_id]
    assert reconstructed.status is RunStatus.fitted


def test_incremental_replay_omits_scalars_without_snapshot(store: ProvenanceStore) -> None:
    # Documents the design boundary: without a snapshot, sub-object replay leaves
    # scalar fields at their defaults (the nested artifacts are still recovered).
    run = _build_expected_run()
    run.shortlist = ["linear_damped_sho"]
    run.status = RunStatus.fitted
    _log_synthetic_run(store, run)  # no snapshot event
    reconstructed = store.reconstruct_run(run.id)
    assert reconstructed.shortlist == []
    assert reconstructed.status is RunStatus.created
    assert reconstructed.candidates == run.candidates  # nested artifacts still faithful


def test_llm_event_persists_all_fields(store: ProvenanceStore) -> None:
    run = _build_expected_run()
    _log_synthetic_run(store, run)
    llm_events = [e for e in store.get_run_events(run.id) if e.event_type is EventType.llm_called]
    assert len(llm_events) == 1
    ev = llm_events[0]
    assert ev.llm_model == "claude-sonnet-5"
    assert ev.llm_prompt_hash and len(ev.llm_prompt_hash) == 64  # sha-256 hex digest
    assert ev.llm_prompt_text == "Which families fit?"
    assert ev.llm_total_tokens == 17
    assert ev.llm_latency_s == pytest.approx(0.42)


def test_export_run_produces_valid_json(store: ProvenanceStore, tmp_path: Path) -> None:
    run = _build_expected_run()
    n = _log_synthetic_run(store, run)
    out = tmp_path / "audit.json"
    returned = store.export_run(run.id, out)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded == returned
    assert loaded["run_id"] == run.id
    assert loaded["n_events"] == n
    # The LLM event's structured block survives export.
    llm_entries = [e for e in loaded["events"] if e["event_type"] == "llm_called"]
    assert llm_entries and llm_entries[0]["llm"]["model"] == "claude-sonnet-5"
    # A state_created payload is a readable, tagged envelope.
    state_entries = [e for e in loaded["events"] if e["event_type"] == "state_created"]
    assert state_entries[0]["payload"]["state_type"] == "ProblemSpec"


def test_reconstruct_missing_run_raises(store: ProvenanceStore) -> None:
    with pytest.raises(ValueError):
        store.reconstruct_run("no-such-run")


def test_persists_to_disk_and_reopens(tmp_path: Path) -> None:
    run = _build_expected_run()
    db = tmp_path / "prov.sqlite"
    store = ProvenanceStore.open(db)
    _log_synthetic_run(store, run)
    reopened = ProvenanceStore.open(db)
    assert reopened.reconstruct_run(run.id) == run
    assert isinstance(reopened.get_run_events(run.id)[0], Event)
