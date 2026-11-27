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


# --- R9-02 (the signal/DD audit): a reassessment never writes over a study or into an existing folder ---------------

def _snapshot(folder) -> dict:
    """Every file under ``folder`` (following no link out of it) and its SHA-256."""
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


@pytest.mark.parametrize("where", ["the source itself", "a link to the source", "inside the source",
                                   "another existing study", "an empty existing folder"])
def test_an_occupied_or_aliased_destination_is_refused_with_every_byte_unchanged(tmp_path, every_halo_excludes,
                                                                                 where) -> None:
    from adroit.orchestrator import reassess as module
    folder = _study(tmp_path)
    _over_region(folder)
    other = tmp_path / "other"
    other.mkdir()
    (other / "result.json").write_text('{"a saved study": true}')
    out = {"the source itself": folder, "a link to the source": tmp_path / "link",
           "inside the source": folder / "child", "another existing study": other,
           "an empty existing folder": tmp_path / "empty"}[where]
    if where == "a link to the source":
        out.symlink_to(folder, target_is_directory=True)
    if where == "an empty existing folder":
        out.mkdir()
    before, before_other = _snapshot(folder), _snapshot(other)
    with pytest.raises(ValueError, match="nothing was"):        # ``reassess.Occupied``, a ValueError: named so that
        module.reassess(folder, out, budget=3)                     # the code before R9-02 shows what it did instead
    assert _snapshot(folder) == before and _snapshot(other) == before_other     # no byte changed, no file added
    assert not every_halo_excludes                                              # nothing was calculated
    assert not (folder / "child").exists()


def test_a_repeated_default_command_makes_a_new_study(tmp_path, every_halo_excludes) -> None:
    from adroit.orchestrator.reassess import next_free, reassess
    folder = _study(tmp_path)
    _over_region(folder)
    first, _ = reassess(folder, next_free(folder.with_name(folder.name + "_reassessed")), budget=3)
    second, _ = reassess(folder, next_free(folder.with_name(folder.name + "_reassessed")), budget=3)
    assert first.name.endswith("_reassessed") and second.name.endswith("_reassessed_2")
    assert (first / "result.json").is_file() and (second / "result.json").is_file()


def test_a_failure_removes_only_the_new_folder(tmp_path, monkeypatch) -> None:
    from adroit.orchestrator import reassess as module
    folder = _study(tmp_path)
    _over_region(folder)
    before = _snapshot(folder)
    monkeypatch.setattr(module, "_track1", lambda *a: (_ for _ in ()).throw(RuntimeError("stood-in failure")))
    out = tmp_path / "new"
    with pytest.raises(RuntimeError, match="stood-in"):
        module.reassess(folder, out, budget=3)
    assert not out.exists() and _snapshot(folder) == before


def test_a_failure_never_removes_a_folder_moved_into_the_claimed_path(tmp_path, monkeypatch) -> None:
    """RA-02 (the repairs audit): after the claim, the claimed folder is moved aside and another study moved into its
    path; the calculation then fails. Cleanup had removed that study by pathname. Now it is left untouched, the error
    says so, and the claimed folder (moved aside by someone else) is not this call's to touch either."""
    import os
    from adroit.orchestrator import reassess as module
    folder = _study(tmp_path)
    _over_region(folder)
    other = tmp_path / "another_study"
    other.mkdir()
    (other / "result.json").write_text('{"another study": true}')
    before = _snapshot(other)
    out = tmp_path / "new"

    def swap_then_fail(*a):
        os.rename(out, tmp_path / "moved_aside")
        os.rename(other, out)
        raise RuntimeError("stood-in failure after the swap")
    monkeypatch.setattr(module, "_track1", swap_then_fail)
    with pytest.raises(RuntimeError, match="stood-in") as raised:
        module.reassess(folder, out, budget=3)
    assert _snapshot(out) == before                                   # the other study, intact, where it was moved
    assert any("was kept" in n for n in getattr(raised.value, "__notes__", []))
    assert (tmp_path / "moved_aside").is_dir()


def test_a_folder_swapped_in_as_the_claim_is_exposed_is_never_taken(tmp_path, monkeypatch) -> None:
    """RB-02 and RC-03 (the rechecks): as the claim appears at its destination, it is moved aside and an empty folder
    put there, into which another writer then writes. A claim proved at the destination (by emptiness, owner or age)
    had taken that folder for its own and removed the other writer's data on failure. Now the claim's identity is
    taken in private before it is exposed: the swapped-in folder is refused, untouched, and nothing is calculated."""
    import os
    import pathlib
    from adroit.orchestrator import reassess as module
    folder = _study(tmp_path)
    _over_region(folder)
    out = tmp_path / "new"
    calculated = []

    def other_writer_then_fail(*a):
        calculated.append(a)
        (out / "theirs.json").write_text('{"another writer": true}')   # into the folder now at the path
        raise RuntimeError("stood-in failure")
    monkeypatch.setattr(module, "_track1", other_writer_then_fail)

    def swap_in_an_empty_folder():
        if not (tmp_path / "moved_aside").exists():
            os.replace(out, tmp_path / "moved_aside")
        real_mkdir(out)
    real_mkdir, real_rename = pathlib.Path.mkdir, os.rename

    def mkdir_then_swap(self, *a, **k):          # the claim made in place (before RC-03)
        real_mkdir(self, *a, **k)
        if self == out:
            swap_in_an_empty_folder()
    monkeypatch.setattr(pathlib.Path, "mkdir", mkdir_then_swap)

    def rename_then_swap(src, dst, *a, **k):     # the claim exposed by renaming it into place (RC-03)
        real_rename(src, dst, *a, **k)
        if pathlib.Path(dst) == out and pathlib.Path(src).name.startswith(".new.claim-"):
            swap_in_an_empty_folder()
    monkeypatch.setattr(os, "rename", rename_then_swap)
    with pytest.raises((ValueError, RuntimeError)):
        module.reassess(folder, out, budget=3)
    if not calculated:                            # refused before anything: the other writer writes afterwards
        (out / "theirs.json").write_text('{"another writer": true}')
    assert (out / "theirs.json").read_text() == '{"another writer": true}'     # never removed as this call's own


def test_an_incomplete_cleanup_is_said_and_its_place_named(tmp_path, monkeypatch) -> None:
    """RB-02's second part: a nested folder that cannot be removed had left partial output behind silently."""
    import os
    import stat as _stat
    from adroit.orchestrator import reassess as module
    folder = _study(tmp_path)
    _over_region(folder)
    out = tmp_path / "new"
    locked = []

    def write_then_fail(*a):
        nested = out / "nested"
        nested.mkdir()
        (nested / "partial.json").write_text("{}")
        nested.chmod(_stat.S_IRUSR | _stat.S_IXUSR)        # its file cannot be removed
        locked.append(nested)
        raise RuntimeError("stood-in failure")
    monkeypatch.setattr(module, "_track1", write_then_fail)
    try:
        with pytest.raises(RuntimeError) as raised:
            module.reassess(folder, out, budget=3)
        notes = getattr(raised.value, "__notes__", [])
        assert any("was kept" in n and str(out) in n for n in notes)
        assert (out / "nested" / "partial.json").exists()              # nothing written is removed
    finally:
        for d in [out, *out.rglob("*")] if out.exists() else []:
            if d.is_dir():
                os.chmod(d, 0o700)



# --- RD-01 (the third recheck): one destination, one claim -----------------------------------------------------------

def test_two_reassessments_racing_for_one_destination_cannot_both_claim_it(tmp_path, monkeypatch) -> None:
    """Both pass the existence check, then claim at the same instant: exactly one succeeds. (A rename onto the
    destination had let the second replace the first's empty claim, and later its published study.)"""
    import os
    import threading
    from adroit.orchestrator import reassess as module
    folder = _study(tmp_path)
    out = tmp_path / "new"
    barrier = threading.Barrier(2)
    real_mkdir = os.mkdir

    def mkdir_together(path, *a, **k):
        if os.fspath(path) == os.fspath(out):
            barrier.wait(timeout=10)                      # both claimants have passed every check
        return real_mkdir(path, *a, **k)
    monkeypatch.setattr(os, "mkdir", mkdir_together)
    real_rename = os.rename

    def rename_together(src, dst, *a, **k):              # the claim as the code before RD-01 exposed it (RE-06)
        if os.fspath(dst) == os.fspath(out):
            barrier.wait(timeout=10)
        return real_rename(src, dst, *a, **k)
    monkeypatch.setattr(os, "rename", rename_together)
    outcomes = []

    def claim():
        try:
            module._reserve(folder, out)
            outcomes.append("claimed")
        except module.Occupied:
            outcomes.append("refused")
    threads = [threading.Thread(target=claim) for _ in range(2)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=20)
    assert sorted(outcomes) == ["claimed", "refused"]


def test_an_empty_folder_already_at_the_destination_is_refused(tmp_path) -> None:
    from adroit.orchestrator import reassess as module
    folder = _study(tmp_path)
    (tmp_path / "new").mkdir()
    with pytest.raises(module.Occupied):
        module._reserve(folder, tmp_path / "new")



def test_a_study_moved_into_the_claim_before_publication_is_never_written_over(tmp_path, monkeypatch) -> None:
    """RE-01 (the fourth recheck): just after the claim, another study is moved into the claimed path; a successful
    reassessment had then written its figures and result over that study. Now it refuses before writing anything, the
    study byte for byte unchanged."""
    import os
    from adroit.orchestrator import reassess as module
    folder = _study(tmp_path)
    _over_region(folder)
    other = _study(tmp_path / "elsewhere")
    before = _snapshot(other)
    out = tmp_path / "new"
    real = module._reserve

    def reserve_then_substitute(*a):        # at the claim's boundary, as the audit's control did
        claimed = real(*a)
        os.rmdir(out)                       # the empty claim taken away, an existing study put in its place
        os.rename(other, out)
        return claimed
    monkeypatch.setattr(module, "_reserve", reserve_then_substitute)
    with pytest.raises(ValueError, match="did not write"):
        module.reassess(folder, out, budget=1)
    assert _snapshot(out) == before
