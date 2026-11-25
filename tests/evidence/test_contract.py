from pathlib import Path

import pytest
from pydantic import ValidationError

from adroit.core.evidence import (
    EvidenceContext, EvidenceEnvelope, EvidenceObservation, SourceEvidence, content_hash, physical_identity,
)
from adroit.evidence.build import build, read, sidecar_path
from adroit.evidence.observations import point_observations, constraint_observation
from adroit.evidence.results import load_result, result_type, summary
from adroit.parameter_space.scan import PointResult


def test_hash_and_physical_identity_preserve_numbers() -> None:
    assert content_hash({"a":0.,"b":None}) == content_hash({"b":None,"a":0.})
    assert content_hash({"a":0.}) != content_hash({"a":None})
    assert physical_identity({"name":"one","coupling":.1},{"m_chi":7.1}) == physical_identity(
        {"name":"two","coupling":.1},{"m_chi":7.1})
    assert physical_identity({"coupling":.1},{"m_chi":7.1}) != physical_identity(
        {"coupling":.1},{"m_chi":7.10000001})


def test_review_and_schema_never_fabricate_a_signature() -> None:
    with pytest.raises(ValidationError):
        SourceEvidence(id="r", review="verified")
    source = SourceEvidence(id="r", review="verified", reviewed_by="reviewer", reviewed_on="2026-10-08")
    assert source.review == "verified"
    with pytest.raises(ValidationError):
        EvidenceEnvelope(schema_version=2, workflow="track1",result_sha256="a",input_sha256="b")
    with pytest.raises(ValidationError):
        EvidenceObservation(subject_id="x",physical_input={},observable="x",value=float("nan"))


def test_zero_missing_backend_and_unreviewed_are_distinct(point_result: PointResult,
                                                         context: EvidenceContext) -> None:
    observations = point_observations(point_result, {"family":"test"},context)
    by_name = {o.observable:o for o in observations}
    assert by_name["direct_detection_prediction"].value == 0
    assert by_name["direct_detection_prediction"].calculation == "computed"
    assert by_name["direct detection"].value is None
    assert by_name["direct detection"].calculation == "unavailable_backend"
    assert by_name["omega_h2"].calculation == "computed"
    assert by_name["omega_h2"].review == "unreviewed"
    assert by_name["perturbativity"].excluded is False
    assert by_name["perturbativity"].review == "not_required"


def test_verdict_adapter_preserves_refusal_and_native_cl(context: EvidenceContext) -> None:
    observation = constraint_observation({"constraint_id":"planck-2018-omega","excluded":None,
        "applicability":"needs_calculation","needed_calculation":"unsupported topology",
        "confidence_level":.9},"model",context)
    assert observation.review == "unreviewed" and observation.calculation == "not_calculated"
    assert observation.required_confidence_level == .95 and observation.native_confidence_level == .9
    assert observation.excluded is None and observation.reasons == ["unsupported topology"]


def test_legacy_load_does_not_add_current_source_signatures(track1_file: Path) -> None:
    before = track1_file.read_bytes()
    envelope = read(track1_file)
    assert envelope.context.origin == "legacy_unknown" and not envelope.context.sources
    assert not sidecar_path(track1_file).exists() and before == track1_file.read_bytes()
    kind,result=load_result(track1_file)
    assert kind=="track1" and envelope.summary==summary(kind,result)
    assert build(kind,result,envelope.result_sha256).identity==envelope.identity
    with pytest.raises(ValueError,match="unsupported"):
        result_type("unknown")


def test_bound_sidecar_detects_result_and_input_changes(captured_file: Path) -> None:
    envelope = read(captured_file)
    assert envelope.context.origin == "captured"
    assert envelope.certificates["missing_contour_comparisons"] == 0
    changed=envelope.model_copy(deep=True)
    changed.original_inputs["workers"]=2
    sidecar_path(captured_file).write_text(changed.model_dump_json())
    with pytest.raises(ValueError,match="input identity"):
        read(captured_file)
    sidecar_path(captured_file).write_text(envelope.model_dump_json())
    captured_file.write_text(captured_file.read_text()+"\n")
    with pytest.raises(ValueError,match="content mismatch"):
        read(captured_file)


def test_source_and_setting_changes_invalidate_evidence_identity(track1_file: Path,
                                                               context: EvidenceContext) -> None:
    kind,result=load_result(track1_file)
    first=build(kind,result,"same",context)
    changed=context.model_copy(deep=True)
    changed.sources[0].data_sha256="new-source"
    assert build(kind,result,"same",changed).identity != first.identity
    changed=result.model_copy(deep=True)
    changed.request.unverified_records=True
    assert build(kind,changed,"same",context).input_sha256 != first.input_sha256


def test_mutated_typed_request_cannot_claim_calculation_start_identity(track1_file: Path,
                                                                   context: EvidenceContext) -> None:
    kind,result=load_result(track1_file)
    context.request_sha256=content_hash(result.request.model_dump(mode="json"))
    result.request.unverified_records=True
    envelope=build(kind,result,"same",context)
    assert envelope.context.origin=="changed_during_run"
    assert any("typed request" in note for note in envelope.context.notes)


def test_new_envelope_can_be_logged_in_existing_provenance(track1_file: Path) -> None:
    from adroit.core.provenance import ProvenanceStore, EventType, _decode_state
    envelope=read(track1_file)
    store=ProvenanceStore.open(":memory:")
    # The existing public state log also accepts the new typed scientific envelope.
    store.log_event(run_id="evidence-test", actor="export", event_type=EventType.tool_called, payload=envelope)
    event=store.get_run_events("evidence-test")[0]
    assert _decode_state(event.payload_json) == envelope


def test_additive_model_contract_defaults_preserve_saved_inputs_and_digest(
    captured_file: Path,tmp_path: Path
) -> None:
    from adroit.evidence.archive import export_run, verify_bundle
    envelope=read(captured_file)
    original=envelope.original_inputs
    original['spec'].pop('vector_currents')
    original['spec'].pop('scalar_potential')
    envelope.input_sha256=content_hash(original)
    envelope.context.request_sha256=envelope.input_sha256
    sidecar_path(captured_file).write_text(envelope.model_dump_json())
    assert read(captured_file).original_inputs==original
    export_run(captured_file,tmp_path/'old-inputs.zip')
    assert verify_bundle(tmp_path/'old-inputs.zip').valid
    # Normalization accepts missing additive defaults, never a changed physical input.
    original['spec']['relic_fraction']=.5
    envelope.input_sha256=content_hash(original)
    envelope.context.request_sha256=envelope.input_sha256
    sidecar_path(captured_file).write_text(envelope.model_dump_json())
    with pytest.raises(ValueError,match='request mismatch'):
        read(captured_file)


def test_additive_point_contract_preserves_old_conclusions_and_catches_real_changes(
    captured_file: Path,tmp_path: Path
) -> None:
    from adroit.evidence.archive import export_run,verify_bundle
    envelope=read(captured_file)
    # Simulate an M19/M21 sidecar before the additive per-point contract field.
    for crossing in envelope.summary['verdict']['crossings']:
        crossing['evaluation'].pop('model_contract')
    sidecar_path(captured_file).write_text(envelope.model_dump_json())
    original=envelope.summary.copy()
    assert read(captured_file).summary==original
    export_run(captured_file,tmp_path/'old-conclusions.zip')
    verified=verify_bundle(tmp_path/'old-conclusions.zip')
    assert verified.valid and verified.nodes[0].summary==original
    envelope.summary['verdict']['crossings'][0]['status']='viable'
    sidecar_path(captured_file).write_text(envelope.model_dump_json())
    with pytest.raises(ValueError,match='decision mismatch'):
        read(captured_file)


def test_normalized_summary_rejects_removed_or_extra_decision_fields(
    captured_file: Path
) -> None:
    from adroit.evidence.results import summary_matches
    kind,result=load_result(captured_file)
    saved=read(captured_file).summary
    assert summary_matches(kind,saved,result)
    removed={k:v for k,v in saved.items() if k!='verdict'}
    assert not summary_matches(kind,removed,result)
    assert not summary_matches(kind,{**saved,'request':{}},result)
