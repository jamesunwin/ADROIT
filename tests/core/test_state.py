"""Tests for the typed state schemas in ``adroit.core.state``.

Three properties are checked for the models: (1) valid construction produces the
expected typed object, (2) every model survives a JSON round-trip unchanged, and
(3) invalid data — a bad enum, an out-of-range confidence, a missing required
field, or a stray extra field — is rejected at construction with a
``ValidationError``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adroit.core.state import (
    AdjudicationEntry,
    AdjudicationRecord,
    DataSourceKind,
    DataSourceRef,
    EvidenceState,
    FitResult,
    StrictModel,
    ModelCandidate,
    ParameterSpec,
    ProblemSpec,
    QualitativeFeature,
    QualitativeFeatureKind,
    RevisionAction,
    RevisionActionKind,
    RunState,
    RunStatus,
    VariableInfo,
)


def _damped_oscillator_run() -> RunState:
    """Build a fully-populated RunState for a damped-oscillator investigation."""
    source = DataSourceRef(
        kind=DataSourceKind.timeseries,
        path_or_url="data/oscillator.csv",
        description="Measured displacement x(t).",
    )
    problem = ProblemSpec(
        scientific_objective="Explain the decaying oscillation in x(t).",
        admissible_data=[source],
        context_literature=["ref:hooke1678"],
        constraints=["energy is dissipated"],
        evaluation_criteria=["AIC", "held-out RMSE"],
        exclusions=["driven forcing"],
    )
    evidence = EvidenceState(
        problem_id=problem.id,
        summary="Amplitude decays while oscillating at roughly constant period.",
        variables=[
            VariableInfo(name="t", units="s", role_guess="independent"),
            VariableInfo(name="x", units="m", role_guess="observable"),
        ],
        qualitative_features=[
            QualitativeFeature(
                feature=QualitativeFeatureKind.oscillation,
                confidence=0.95,
                evidence_snippet="clear periodic zero-crossings",
            ),
            QualitativeFeature(
                feature=QualitativeFeatureKind.decay,
                confidence=0.8,
                evidence_snippet="peak amplitude falls monotonically",
            ),
        ],
        numeric_payload_ref="runs/xt.npz",
    )
    candidate = ModelCandidate(
        family_id="linear_damped_sho",
        name="Damped harmonic oscillator",
        symbolic_form="x'' + 2*gamma*x' + omega0**2*x",
        latex_form=r"\ddot{x} + 2\gamma\dot{x} + \omega_0^2 x = 0",
        parameters=[
            ParameterSpec(name="gamma", meaning="damping rate", prior_low=0.0, prior_high=5.0, units="1/s"),
            ParameterSpec(name="omega0", meaning="natural frequency", prior_low=0.1, prior_high=50.0, units="rad/s"),
        ],
        observables=["x"],
        assumptions=["linear restoring force", "viscous damping"],
        expected_signatures=["exponential envelope", "fixed period"],
        justification="Oscillation with monotone decay is the textbook SHO signature.",
        provenance_evidence_ids=[evidence.id],
    )
    fit = FitResult(
        candidate_id=candidate.id,
        param_estimates={"gamma": 0.31, "omega0": 6.28},
        param_uncertainties={"gamma": 0.02, "omega0": 0.05},
        loss=0.0123,
        aic=-42.0,
        bic=-38.0,
        residual_diagnostics={"durbin_watson": 1.98},
        heldout_score=0.91,
        fit_success=True,
        notes="Converged in 14 iterations.",
    )
    adjudication = AdjudicationRecord(
        entries=[
            AdjudicationEntry(candidate_id=candidate.id, criterion="AIC", score=0.9, rationale="lowest AIC"),
        ],
        final_ranking=[candidate.id],
    )
    revision = RevisionAction(
        action=RevisionActionKind.adjust_priors,
        target_candidate_id=candidate.id,
        description="Widen the damping prior after boundary-hugging estimate.",
    )
    return RunState(
        problem=problem,
        evidence=[evidence],
        shortlist=[candidate.family_id],
        candidates=[candidate],
        fits=[fit],
        adjudications=[adjudication],
        revisions=[revision],
        status=RunStatus.adjudicated,
    )


# --- Valid construction ----------------------------------------------------


def test_valid_run_constructs_with_expected_values() -> None:
    run = _damped_oscillator_run()
    assert run.status is RunStatus.adjudicated
    assert run.problem.admissible_data[0].kind is DataSourceKind.timeseries
    assert run.evidence[0].qualitative_features[0].feature is QualitativeFeatureKind.oscillation
    assert run.candidates[0].parameters[0].name == "gamma"
    assert run.fits[0].param_estimates["omega0"] == pytest.approx(6.28)


def test_ids_are_unique_and_auto_populated() -> None:
    a, b = ProblemSpec(scientific_objective="x"), ProblemSpec(scientific_objective="y")
    assert a.id and b.id and a.id != b.id


def test_fit_result_has_auto_id() -> None:
    fit = FitResult(candidate_id="c1", loss=0.1, aic=1.0, bic=2.0)
    assert fit.id and fit.id != FitResult(candidate_id="c1", loss=0.1, aic=1.0, bic=2.0).id


def test_created_at_is_timezone_aware() -> None:
    problem = ProblemSpec(scientific_objective="x")
    assert problem.created_at.tzinfo is not None


# --- JSON round-trip -------------------------------------------------------

_ROUND_TRIP_CASES = [
    DataSourceRef(kind=DataSourceKind.image, path_or_url="fig1.png"),
    VariableInfo(name="T", units="K"),
    QualitativeFeature(feature=QualitativeFeatureKind.power_law, confidence=0.5),
    ParameterSpec(name="k", prior_low=0.0, prior_high=1.0),
    ProblemSpec(scientific_objective="probe criticality"),
]


@pytest.mark.parametrize("obj", _ROUND_TRIP_CASES)
def test_json_round_trip_equality_small_models(obj: StrictModel) -> None:
    assert type(obj).from_json(obj.to_json()) == obj


def test_json_round_trip_equality_full_run() -> None:
    run = _damped_oscillator_run()
    assert RunState.from_json(run.to_json()) == run


def test_json_round_trip_preserves_enums_as_enums() -> None:
    run = RunState.from_json(_damped_oscillator_run().to_json())
    assert run.status is RunStatus.adjudicated
    assert run.revisions[0].action is RevisionActionKind.adjust_priors


# --- Invalid data rejected -------------------------------------------------


def test_bad_enum_raises() -> None:
    with pytest.raises(ValidationError):
        DataSourceRef(kind="hologram", path_or_url="x")  # type: ignore[arg-type]


def test_confidence_above_one_raises() -> None:
    with pytest.raises(ValidationError):
        QualitativeFeature(feature=QualitativeFeatureKind.decay, confidence=1.5)


def test_confidence_below_zero_raises() -> None:
    with pytest.raises(ValidationError):
        QualitativeFeature(feature=QualitativeFeatureKind.decay, confidence=-0.1)


def test_missing_required_field_raises() -> None:
    with pytest.raises(ValidationError):
        ModelCandidate(family_id="f", name="n")  # type: ignore[call-arg]  # no symbolic_form


def test_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        VariableInfo(name="t", flavor="strange")  # type: ignore[call-arg]


def test_assignment_is_validated() -> None:
    feature = QualitativeFeature(feature=QualitativeFeatureKind.decay, confidence=0.5)
    with pytest.raises(ValidationError):
        feature.confidence = 2.0


def test_a_parameter_is_read_on_its_natural_scale() -> None:
    from adroit.core.state import ParameterSpec
    rate = ParameterSpec(name="k", prior_low=0.01, prior_high=100.0)
    assert rate.on_log_scale() and abs(rate.position(1.0) - 0.5) < 1e-12
    signed = ParameterSpec(name="b", prior_low=-10.0, prior_high=10.0)
    assert not signed.on_log_scale() and signed.position(0.0) == 0.5
    narrow = ParameterSpec(name="c", prior_low=1.0, prior_high=10.0)
    assert not narrow.on_log_scale()                       # one decade: linear
    declared = ParameterSpec(name="c", prior_low=1.0, prior_high=10.0, scale="log")
    assert declared.on_log_scale() and abs(declared.position(10 ** 0.5) - 0.5) < 1e-12
    forced = ParameterSpec(name="k", prior_low=0.01, prior_high=100.0, scale="linear")
    assert not forced.on_log_scale() and forced.position(1.0) < 0.01
    assert rate.position(-1.0) != rate.position(-1.0)     # NaN: not on a log scale
