"""A targeted reassessment of a saved study (the owner's plan of 2026-11-24, section 4; ``orchestrator.reassess``):
only what the saved study lacks is calculated, into a new child study whose lineage names the original; the
original's result and evidence bytes are unchanged, and nothing of it is certified again.

The Constrain a model case uses a small saved study over the halo region whose thermal root is the vector's 88.59 GeV
point as saved (excluded at the centre, its halo coverage incomplete), with the halo evaluation itself stood in (a
sample set in which every halo excludes): the reassessment's own code (which points it takes, what it reuses, how it
classifies, certifies, aggregates and writes) runs as built. The halo evaluation's own tests are its own."""
import hashlib
import json

import pytest

from adroit.core.certificate import POLICY
from adroit.parameter_space import halo_evaluation, halo_region
from tests.ui.test_signal_dd_pages import _study


def _over_region(folder) -> None:
    """The saved study as run over the owner's halo region (its scan's request names the preset)."""
    from adroit.orchestrator.track1 import Track1Result
    path = folder / "result.json"
    result = Track1Result.model_validate_json(path.read_text())
    scan = result.scan.model_copy(update={"request": result.scan.request.model_copy(
        update={"halo": halo_region.HaloPreset()})})
    path.write_text(result.model_copy(update={"scan": scan}).model_dump_json(indent=1))


@pytest.fixture
def every_halo_excludes(monkeypatch):
    """The halo evaluation stood in: the saved nominal evaluation it is given is reused (it is never recomputed), and
    every sample's direct detection excludes. Records what it was asked."""
    asked = []

    def evaluate(cls, p, preset, nominal, unverified):
        saved = nominal()
        asked.append((p.m_chi, preset.full_calculations, saved.omega_h2))
        samples = [halo_region.HaloPointSample(v0_km_s=v, v_esc_km_s=528, rho_gev_cm3=0.15, where="sample",
                                               outcomes={"direct detection": halo_region.HaloOutcome(excluded=True,
                                                                                                     ratio=5.0)})
                   for v in (193.0, 233.0, 273.0)]
        from adroit.core.halo_choice import HALO_DATA, data_identity       # what the real one records (``_recorded``)
        halo = halo_region.HaloEvaluation(region=halo_region.describe(preset), samples=samples, converged=True,
                                          full_calculations=["LZ WS2022+WS2024 SI (stood in)"],
                                          data=data_identity(tuple(HALO_DATA)))
        return saved.model_copy(update={"halo": halo})
    monkeypatch.setattr(halo_evaluation, "evaluate", evaluate)
    return asked


def test_an_incomplete_point_is_completed_and_the_original_is_untouched(tmp_path, every_halo_excludes) -> None:
    from adroit.orchestrator.reassess import reassess
    from adroit.orchestrator.track1 import Track1Result
    folder = _study(tmp_path)
    _over_region(folder)
    before = hashlib.sha256((folder / "result.json").read_bytes()).hexdigest()
    out, report = reassess(folder, tmp_path / "runs" / "vector_reassessed", budget=7)
    assert hashlib.sha256((folder / "result.json").read_bytes()).hexdigest() == before       # the original's bytes
    assert every_halo_excludes and every_halo_excludes[0][1] == 7                            # the budget it was given
    assert every_halo_excludes[0][2] is not None                                             # the saved Ωh², reused
    new = Track1Result.model_validate_json((out / "result.json").read_text())
    c = new.verdict.crossings[0]
    assert c.status == "excluded" and c.halo == halo_region.EXCLUDED
    assert c.certificate.policy == POLICY and c.certificate.decided
    lineage = json.loads((out / "reassessment.json").read_text())
    assert lineage["source_result_sha256"] == before and lineage["budget_per_point"] == 7
    [step] = lineage["calculated"]
    assert step["before"]["halo"] == halo_region.INCOMPLETE and step["after"]["halo"] == halo_region.EXCLUDED
    assert step["full_calculations"] == ["LZ WS2022+WS2024 SI (stood in)"]
    evidence = json.loads((out / "result.evidence.json").read_text())
    assert "reassessment_lineage" in json.dumps(evidence)
    assert report.startswith("# Reassessment") and "every fit, scan, relic density" in report.lower()


def test_the_reassessed_study_reopens_through_the_version_handle(tmp_path, every_halo_excludes) -> None:
    from adroit.evidence.points import rows
    from adroit.evidence.version import resolve
    from adroit.orchestrator.reassess import reassess
    folder = _study(tmp_path)
    _over_region(folder)
    out, _ = reassess(folder, tmp_path / "runs" / "vector_reassessed", budget=3)
    snapshot = resolve(out / "result.json").saved()
    found = {r.point_id: r for r, _, _ in rows(snapshot.workflow, snapshot.result)}
    assert found["contour:0"].status == "excluded"


def test_a_point_already_decided_or_halo_sensitive_is_left_as_saved(tmp_path, every_halo_excludes) -> None:
    """Only incomplete coverage is reassessed: a halo-sensitive point is never forced robust."""
    from adroit.orchestrator.reassess import reassess
    from adroit.orchestrator.track1 import Track1Result
    folder = _study(tmp_path)
    _over_region(folder)
    path = folder / "result.json"
    result = Track1Result.model_validate_json(path.read_text())
    sensitive = result.verdict.crossings[0].model_copy(update={"halo": halo_region.SENSITIVE})
    path.write_text(result.model_copy(update={"verdict": result.verdict.model_copy(
        update={"crossings": [sensitive]})}).model_dump_json(indent=1))
    out, _ = reassess(folder, tmp_path / "runs" / "left", budget=3)
    assert not every_halo_excludes
    assert json.loads((out / "reassessment.json").read_text())["calculated"] == []
    assert Track1Result.model_validate_json((out / "result.json").read_text()).verdict.crossings[0].halo == \
        halo_region.SENSITIVE


def test_a_study_not_over_the_region_is_refused(tmp_path) -> None:
    from adroit.orchestrator.reassess import reassess
    folder = _study(tmp_path)
    with pytest.raises(ValueError, match="only a study over the halo region"):
        reassess(folder, tmp_path / "runs" / "refused")
    assert not (tmp_path / "runs" / "refused" / "result.json").exists()
