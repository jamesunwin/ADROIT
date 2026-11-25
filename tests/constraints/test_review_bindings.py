from datetime import date
from pathlib import Path

import pytest
import yaml

from adroit.constraints import database,review
from adroit.constraints.review_identity import fingerprint,signature_status,selected_data


@pytest.fixture
def bound_workspace(tmp_path: Path,monkeypatch: pytest.MonkeyPatch) -> Path:
    from adroit.constraints import review_identity
    data=tmp_path/"data.yaml"
    data.write_text(yaml.safe_dump({"source":"paper","panels":{"V1":{"points":[[1,2],[2,3],[3,4]]},
                                                      "V2":{"points":[[1,9],[2,8],[3,7]]}}}))
    path=tmp_path/"records.yaml"
    # Use the production record's block format rather than emitter-dependent indentation.
    path.write_text("records:\n  - id: example-V1\n    name: example\n    source: paper\n"
                    "    constraint_class: collider\n    data_file: data.yaml\n    confidence_level: 0.9\n"
                    "    assumptions: [fixed benchmark]\n")
    monkeypatch.setattr(database,"RECORDS",path)
    monkeypatch.setattr(review_identity,"PROJECT_ROOT",tmp_path)
    monkeypatch.setattr(review_identity,"LEGACY_BINDINGS",tmp_path/"no-baselines.yaml")
    database.records.cache_clear()
    yield path
    database.records.cache_clear()
    database.data.cache_clear()


def test_human_stamp_binds_data_and_metadata_preserving_date(bound_workspace: Path) -> None:
    current=database.record("example-V1")
    expected=fingerprint(current)
    review.verify(current.id,"A. Physicist",on=date(2026,10,8),expected_sha256=expected)
    signed=database.record(current.id)
    assert signed.usable and signature_status(signed).state=="current"
    assert signed.verification_sha256==expected and signed.verified_by=="A. Physicist"
    text=bound_workspace.read_text().replace("confidence_level: 0.9","confidence_level: 0.95")
    bound_workspace.write_text(text)
    changed=database.record(current.id)  # no cache_clear: live edits must be noticed
    assert not changed.usable and signature_status(changed).state=="stale"
    assert changed.verified_on==signed.verified_on and changed.verified_by==signed.verified_by
    review.verify(current.id,"Second reviewer",on=date(2026,10,9))
    renewed=database.record(current.id)
    assert renewed.usable and renewed.verification_history[0].by=="A. Physicist"
    assert renewed.verification_history[0].payload_sha256==expected


def test_only_relevant_panel_changes_invalidate_and_missing_data_is_not_approved(bound_workspace: Path) -> None:
    review.verify("example-V1","Reviewer")
    current=database.record("example-V1")
    data=bound_workspace.parent/"data.yaml"
    contents=yaml.safe_load(data.read_text())
    contents["panels"]["V2"]["points"][0][1]=100
    data.write_text(yaml.safe_dump(contents))
    assert current.usable
    contents["panels"]["V1"]["points"][0][1]=5
    data.write_text(yaml.safe_dump(contents))
    assert not current.usable
    assert selected_data(current)["panels"].keys()=={"V1"}
    data.unlink()
    assert signature_status(current).state=="unavailable"
    with pytest.raises(FileNotFoundError):
        review.verify("example-V1","Reviewer again")


@pytest.mark.parametrize("field,old,new",[("source","paper","revised paper"),
    ("assumptions","fixed benchmark","different flavour"),
    ("data_file","data.yaml","other.yaml")])
def test_scientific_edits_invalidate_old_human_signature(bound_workspace: Path,field: str,old: str,new: str) -> None:
    review.verify("example-V1","Reviewer")
    bound_workspace.write_text(bound_workspace.read_text().replace(old,new))
    assert not database.record("example-V1").usable


def test_display_name_change_does_not_force_an_unrelated_review(bound_workspace: Path) -> None:
    review.verify("example-V1","Reviewer")
    bound_workspace.write_text(bound_workspace.read_text().replace("name: example","name: new display"))
    assert database.record("example-V1").usable


def test_panel_staleness_is_rejected_at_the_human_signing_boundary(bound_workspace: Path) -> None:
    expected=fingerprint(database.record("example-V1"))
    bound_workspace.write_text(bound_workspace.read_text().replace("fixed benchmark","changed benchmark"))
    with pytest.raises(ValueError,match="changed since"):
        review.verify("example-V1","Reviewer",expected_sha256=expected)
    assert database.record("example-V1").verified_on is None


def test_verifying_a_curve_never_changes_its_cl_or_benchmark_eligibility(bound_workspace: Path) -> None:
    from adroit.constraints.searches import Outcome
    review.verify("example-V1","Reviewer")
    record=database.record("example-V1")
    assert record.usable and record.confidence_level==.9 and record.assumptions==["fixed benchmark"]
    result=Outcome(name="example",excluded=False,ratio=.5,confidence_level=record.confidence_level).at95()
    assert result.excluded is False and result.ratio is None and "hence at 95%" in result.why      # R3: allowed at 90% is allowed at 95%
    result=Outcome(name="example",excluded=True,ratio=2.,confidence_level=record.confidence_level).at95()
    assert result.excluded is None and result.ratio is None and "95% comparison needs" in result.why


def test_nine_existing_approvals_are_labelled_migration_baselines() -> None:
    """The nine historical approvals keep their migration bindings. A record whose content changed since (R9's
    corrections) is stale until re-signed; none counts as verified without a matching binding or a new seal."""
    from adroit.constraints.review_identity import LEGACY_BINDINGS,_bindings
    bound={b.record_id for b in _bindings(LEGACY_BINDINGS.read_text()).bindings}
    assert len(bound)==9
    for r in database.records():
        state=signature_status(r).state
        if r.id in bound and not r.verification_sha256:
            assert state in ("legacy_baseline","stale") and r.usable==(state=="legacy_baseline")
        if r.usable:
            assert state in ("legacy_baseline","current")


@pytest.mark.usefixtures("resigned")
def test_the_nine_approvals_count_once_rebound_to_their_corrected_content() -> None:
    verified=[r for r in database.records() if r.usable]
    legacy=[r for r in verified if signature_status(r).state=="legacy_baseline"]
    # the nine earlier approvals, plus any record the owner has signed since with a payload-bound seal (R9); a
    # re-signed one of the nine is current, so the legacy ones are at most those nine
    nine = {"cms-2405.13778-V1", "cms-2405.13778-A1", "cms-2405.13778-V2", "cms-2405.13778-A2", "icecube-1612.05949-sd",
            "icecube-1612.05949-si", "fermi-1503.02641-dsph", "atlas-2301.10731-hinv", "lep-hep-ex-0509008-zinv"}
    assert {r.id for r in legacy} <= nine
    assert all(signature_status(r).state=="current" for r in verified if r not in legacy)



def test_notes_are_outside_the_signed_content() -> None:
    """The owner (2026-10-13): adding or correcting the reviewer's notes never voids a signature."""
    from adroit.constraints import review_identity
    record = database.record("sabti-1910.01649-bbn")
    assert review_identity.fingerprint(record.model_copy(update={"notes": "one"})) == \
        review_identity.fingerprint(record.model_copy(update={"notes": "another"}))
    assert "notes" in review_identity.REVIEW_FIELDS
