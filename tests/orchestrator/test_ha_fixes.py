"""The auditor's halo phase 1 audit, repaired (the independent audit of 2026-11-12 (halo phase1); the record
the HA repair record of 2026-11-12):

- HA-05: a calculation's halo is its own. A resolution shares no object with the value it resolves, each run calculates
  with its own copy of its request, and a halo changed while a run calculates is refused at its end: nothing is
  published under the identity it was resolved with. A saved resolution whose values do not give its identity reads as
  altered, not as recorded.
- HA-06: the inventory says where IceCube's limit is converted, route by route, and its count of the records with no
  halo input is the code's.
- HA-01 to HA-04 were repaired by the phase 2 audit's repairs and its recheck's (HB-02, HB-03, HC-01 to HC-03), whose
  tests are in ``test_hb_fixes.py`` and ``test_hc_fixes.py``. One case of HA-01's is added here: a declaration's values
  and its sha256 come from one reading.

Offline: toy searches with real recoil rates (``test_halo_phase1``'s); Track 1's and Explain a signal's calculations
stood in for (``test_hb_fixes``'s); IceCube's capture a spy."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml

from adroit.constraints import capture, database, verdicts
from adroit.core import halo_choice
from adroit.core.dm_state import DarkMatterParticle, HaloModel, InteractionModel, OperatorCoefficient
from adroit.core.halo_choice import HaloChanged, identity_of, resolve
from adroit.evidence import build, exports
from adroit.evidence import halo as saved_halo
from adroit.orchestrator import signal, single_idea, track1
from adroit.parameter_space import halo_limits
from adroit.parameter_space.halo_region import HaloPreset
from tests.orchestrator.test_halo_phase1 import _request, toys  # noqa: F401 (a fixture)
from tests.orchestrator.test_hb_fixes import files, plus  # noqa: F401 (a fixture)

DOC = (Path(__file__).resolve().parents[2] / "docs" / "halo_constraint_support.md").read_text()


def _values() -> dict:
    """A halo value of each kind a request holds: the SHM benchmark, SHM++'s, the region, the published halos, none."""
    return {"SHM benchmark": halo_choice.fixed(), "SHM++": plus(), "region": HaloPreset(), "published": "published",
            "none": None}


def _changed(kind: str):
    """The same value with one number changed, as a nested value changed after it was resolved would have it."""
    value = _values()[kind]
    if kind == "region":
        return value.model_copy(update={"rho_median_gev_cm3": 0.6})
    if kind in ("published", "none"):
        return None if kind == "published" else "published"
    return value.model_copy(update={"halo": value.halo.model_copy(update={"rho_gev_cm3": 0.6})})


def _denser(request) -> None:
    request.halo.halo.rho_gev_cm3 = 0.6       # a nested value of the request the run was given, changed as it runs


# --- HA-05: a calculation's halo is its own -----------------------------------------------------------------------------

def test_a_resolution_shares_no_object_with_the_value_it_resolves():
    value = halo_choice.fixed()
    resolution = resolve(value)
    value.halo.rho_gev_cm3 = 0.6                                   # the caller's object, changed after it is resolved
    assert resolution.halo.rho_gev_cm3 == 0.3 and identity_of(resolution) == resolution.identity
    assert resolution.halo is not value.halo


@pytest.mark.parametrize("kind", list(_values()))
def test_a_halo_as_resolved_is_intact_and_a_changed_one_is_refused(kind):
    for track in ("track1", "track2"):
        value = _values()[kind]
        resolution = resolve(value, track=track)
        halo_choice.intact(resolution, value, track=track)
        if kind in ("published", "none") and track == "track2":
            continue                    # Track 2 reads no halo as the published halos: the same resolution's content
        with pytest.raises(HaloChanged, match="changed while it ran.*nothing is published"):
            halo_choice.intact(resolution, _changed(kind), track=track)


def test_a_resolution_changed_after_it_was_identified_is_refused():
    """The resolution and the value changed alike, as when they shared one object (the defect): they still agree, so
    only the resolution's own identity can refuse it."""
    resolution = resolve(halo_choice.fixed())
    resolution.halo.rho_gev_cm3 = 0.6                  # its own nested value: it no longer gives its identity
    with pytest.raises(HaloChanged):
        halo_choice.intact(resolution, _changed("SHM benchmark"))       # a value resolving to what it now holds


def test_explain_a_signal_refuses_a_halo_changed_while_it_calculates(toys, monkeypatch):  # noqa: F811
    """The auditor's control: the density of the request a run was given changed as it calculates. At the phase 1 pin it was
    calculated with 0.6 and saved and exported with the identity and summary of 0.3."""
    real = signal._run
    monkeypatch.setattr(signal, "_run", lambda request: _denser(request) or real(request))
    with pytest.raises(HaloChanged, match="nothing is published"):
        signal.run(_request(halo_choice.fixed()))


@pytest.mark.parametrize("workflow", ["track1", "single_idea"])
def test_track_1_and_a_single_idea_refuse_a_halo_changed_while_they_calculate(workflow, tmp_path, monkeypatch):
    from adroit.orchestrator import track1_identity
    from tests import version_matrix as vm
    if workflow == "track1":
        monkeypatch.setattr(track1_identity, "dependencies", lambda: {})
        _, saved = vm.versions(tmp_path / "versions")
        monkeypatch.setattr(track1, "_run", lambda request, *a, **k: _denser(request) or saved)
        with pytest.raises(HaloChanged):
            track1.run(saved.request.model_copy(update={"halo": halo_choice.fixed()}), tmp_path / "track1")
    else:
        saved = vm.single_idea_versions()[1]
        monkeypatch.setattr(single_idea, "_study", lambda request, *a, **k: _denser(request) or saved)
        with pytest.raises(HaloChanged):
            single_idea.run(saved.request.model_copy(update={"halo": halo_choice.fixed()}), tmp_path / "idea")


def test_a_caller_changing_its_request_during_a_run_changes_nothing_the_run_calculates(toys, monkeypatch):  # noqa: F811
    request = _request(halo_choice.fixed())
    real = signal._run

    def meanwhile(own):
        _denser(request)                         # the caller's own request, changed while the run calculates
        return real(own)
    monkeypatch.setattr(signal, "_run", meanwhile)
    result = signal.run(request)
    assert request.halo.halo.rho_gev_cm3 == 0.6
    assert result.request.halo.halo.rho_gev_cm3 == 0.3 == result.halo_resolution.halo.rho_gev_cm3
    assert identity_of(result.halo_resolution) == result.halo_resolution.identity
    assert toys["signal"][0] == halo_choice.fixed().halo                     # the fit at the benchmark as resolved


def test_a_saved_resolution_whose_values_do_not_give_its_identity_reads_as_altered(toys, tmp_path):  # noqa: F811
    result = signal.run(_request(halo_choice.fixed()))
    recorded = result.halo_resolution
    assert saved_halo.resolution_of("signal", result)[1] == saved_halo.RECORDED
    altered = result.model_copy(update={"halo_resolution": recorded.model_copy(
        update={"halo": recorded.halo.model_copy(update={"rho_gev_cm3": 0.6})})})
    found, how = saved_halo.resolution_of("signal", altered)
    assert how == saved_halo.ALTERED and found.identity == recorded.identity
    assert f"identity {recorded.identity[:12]}; {saved_halo.ALTERED}" in saved_halo.line("signal", altered)
    assert "do not give that identity" in saved_halo.identity_note("signal", altered)
    path = tmp_path / "result.json"
    path.write_text(altered.model_dump_json())
    build.save(path, "signal")
    assert json.loads(exports.tables(path)["halo.json"])["how"] == saved_halo.ALTERED


# --- HA-01: a declaration's values and its identity come from one reading -----------------------------------------------

def test_a_declarations_values_and_its_sha256_come_from_one_reading(files, monkeypatch):  # noqa: F811
    """The auditor's case: the declaration replaced while it is read. At the phase 1 pin its gate was read from one version
    and its sha256 from another."""
    declared = files.folder / halo_choice.HALO_DATA["count-ratio declaration"]
    new = yaml.safe_load(declared.read_text())
    new["gate_max_discrepancy"] = 0.01
    new = yaml.safe_dump(new).encode()
    real = Path.read_bytes

    def replaced(path):
        if path == declared:
            path.write_bytes(new)                           # the file replaced as it is read
        return real(path)
    monkeypatch.setattr(Path, "read_bytes", replaced)
    values, sha = halo_limits.declaration()
    assert values["gate_max_discrepancy"] == 0.01 and sha == hashlib.sha256(new).hexdigest()


# --- HA-06: the inventory says what the code does -----------------------------------------------------------------------

def test_the_inventorys_counts_of_records_are_the_codes():
    records = database.records()
    mapped = DOC.split("## The records with no halo input: one row", 1)[1]
    named = [r.id for r in records if f"`{r.id}`" in mapped]
    stated = re.search(r"The (\d+) records with no halo input", DOC)
    assert stated is not None and int(stated.group(1)) == len(named) == 34
    assert f"records.yaml`, {len(records)})" in DOC


def test_icecubes_limit_is_converted_in_track_2_at_the_comparisons_halo_as_the_inventory_says(monkeypatch):
    seen = []
    monkeypatch.setattr(capture, "available", lambda: True)
    monkeypatch.setattr(capture, "capture_rate", lambda particle, interaction, halo=None: seen.append(
        (interaction.name.startswith("reference"), halo)) or 1.0)
    halo = HaloModel(rho_gev_cm3=0.6)
    candidate = verdicts.Candidate(label="routing", particle=DarkMatterParticle(mass_gev=100.0), interaction=(
        InteractionModel(name="O1", layer="nonrelativistic",
                         coefficients=[OperatorCoefficient(operator=1, proton=1e-5, neutron=1e-5)])))
    verdicts.telescope(candidate, database.record("icecube-1612.05949-si"), halo)
    assert seen == [(False, halo), (True, halo)]           # the candidate's capture and the limit's, at the same halo
    assert "in Track 2 at the comparison's halo" in DOC and "converted at H1 always" not in DOC
