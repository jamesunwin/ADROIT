"""Tests for merging multimodal evidence into a single union view."""

from __future__ import annotations

import pytest

from adroit.core.state import (
    EvidenceState,
    QualitativeFeature,
    QualitativeFeatureKind,
    VariableInfo,
    merge_evidence,
)


def _table() -> EvidenceState:
    return EvidenceState(
        problem_id="p", summary="table: displacement vs time",
        variables=[VariableInfo(name="t", role_guess="independent"),
                   VariableInfo(name="x", role_guess="observable", units="m")],
        qualitative_features=[
            QualitativeFeature(feature=QualitativeFeatureKind.oscillation,
                               confidence=0.9, evidence_snippet="dominant FFT peak"),
            QualitativeFeature(feature=QualitativeFeatureKind.decay, confidence=0.4)],
        numeric_payload_ref="table.npz")


def _figure() -> EvidenceState:
    return EvidenceState(
        problem_id="p", summary="figure: envelope shrinks",
        variables=[VariableInfo(name="x", role_guess="plotted", units="")],
        qualitative_features=[
            QualitativeFeature(feature=QualitativeFeatureKind.decay,
                               confidence=0.8, evidence_snippet="shrinking envelope")])


def test_merge_takes_union_with_max_confidence_per_feature() -> None:
    merged = merge_evidence([_table(), _figure()])
    by_kind = {f.feature: f for f in merged.qualitative_features}
    assert by_kind[QualitativeFeatureKind.oscillation].confidence == 0.9
    assert by_kind[QualitativeFeatureKind.decay].confidence == 0.8       # figure's stronger claim
    assert by_kind[QualitativeFeatureKind.decay].evidence_snippet == "shrinking envelope"
    assert "table" in merged.summary and "figure" in merged.summary
    assert merged.numeric_payload_ref == "table.npz"                     # first source with one


def test_merge_deduplicates_variables_first_occurrence_wins() -> None:
    merged = merge_evidence([_table(), _figure()])
    xs = [v for v in merged.variables if v.name == "x"]
    assert len(xs) == 1 and xs[0].units == "m"                           # table's richer entry
    assert {v.name for v in merged.variables} == {"t", "x"}


def test_merge_single_state_is_returned_unchanged() -> None:
    table = _table()
    assert merge_evidence([table]) is table


def test_merge_empty_needs_a_problem_id() -> None:
    empty = merge_evidence([], problem_id="p9")
    assert empty.problem_id == "p9" and not empty.qualitative_features
    with pytest.raises(ValueError):
        merge_evidence([])
