"""Halo phase 2's SHM++ in the shared contract (``adroit.core.halo_choice``): its fixed benchmark as a snapshot (the
parameters, numerical settings and both tables with their sha256), checked against its generator before use; its
resolution and identity, which separate every parameter, the frame, a table's bytes, the generator's version and the
benchmark's; checkpoints that refuse a change; and the SHM's identities as they were. Offline."""
from __future__ import annotations

import json
from functools import lru_cache

import pytest

from adroit.core import halo_choice
from adroit.core.halo_choice import Capability, UnknownHalo, resolve, verify
from adroit.core.dm_state import HaloModel
from adroit.halo_models import shm_plus_plus as shmpp
from adroit.halo_models.frames import SunFrameTable, frame_of
from adroit.parameter_space import halo_region

# phase 1's identities (the SHM benchmark, the region, the published halos), as the phase 1 branch resolves them
PHASE1 = {"benchmark": "d4ffb6e326dd", "region": "512fbd2f0636", "published": "7a828ad53ad1"}
# the halo data files phase 1's identities were made with (66e1c7d); the count ratio's validation has since been
# recomputed (DW-01, 1dc86a3), and an identity covers its bytes
PHASE1_DATA = {"local densities": "b922637b643d4855ee0b50ecac369cc8a4c7049106daed13739d6ae5e4565153",
               "count-ratio validation": "42f126a5af193e3f6c6698a6124c2948fbbc43c5c9cd5cfd126d37a31cce7905",
               "count-ratio declaration": "73f2486a26e73397a7e80adf1b9339f199d5533cced8fb6846654fccd7f68a4b"}


@lru_cache(maxsize=1)
def benchmark() -> halo_choice.FixedHalo:
    return halo_choice.fixed("shm-plus-plus")


def test_the_shm_identities_are_phase_ones():
    """With phase 1's halo data files, each SHM identity is phase 1's, digit for digit; with today's (the count ratio's
    validation recomputed for DW-01), it moves with their bytes and with nothing else."""
    for name, value in (("benchmark", halo_choice.fixed()), ("region", halo_region.HaloPreset()),
                        ("published", "published")):
        found = resolve(value)
        then = found.model_copy(update={"data": {k: PHASE1_DATA[k] for k in found.data if k in PHASE1_DATA}})
        assert halo_choice.identity_of(then)[:12] == PHASE1[name]
        assert found.data == halo_choice.data_identity(tuple(found.data))
    assert set(json.loads(halo_choice.fixed().model_dump_json())) == {
        "treatment", "schema_version", "family", "benchmark", "version", "halo", "full_calculations"}


def test_the_benchmark_is_a_snapshot_of_the_papers_values_and_its_tables():
    fixed = benchmark()
    p = fixed.parameters
    assert (p.rho_gev_cm3, p.v0_km_s, p.v_esc_km_s, p.beta, p.eta) == (0.55, 233.0, 528.0, 0.9, 0.2)
    assert p.v_peculiar_km_s == (11.1, 12.24, 7.25) and p.v_earth_km_s == shmpp.earth_velocity(7364.3)
    assert fixed.numerics == shmpp.Numerics(speeds=1601, polar=64, azimuth=64, generator=shmpp.GENERATOR)
    assert frame_of(fixed.halo) == "detector" and frame_of(fixed.sun) == "sun" and fixed.generated
    assert isinstance(fixed.sun, SunFrameTable) and type(fixed.halo) is HaloModel
    assert fixed.tables == {"detector": shmpp.sha256(fixed.halo), "sun": shmpp.sha256(fixed.sun)}
    assert fixed.detector() is fixed.halo and fixed.solar() is fixed.sun
    assert verify(fixed) == "" and halo_region.checked(fixed) is fixed
    saved = halo_choice.FixedHalo.model_validate_json(fixed.model_dump_json())
    assert saved == fixed and verify(saved) == ""


def test_its_resolution_names_what_it_supplies_and_what_it_does_not():
    r = resolve(benchmark())
    assert r.family == "shm-plus-plus" and r.treatment.value == "benchmark" and r.halo is None
    assert [c.weight for c in r.components] == [pytest.approx(0.8), 0.2]
    assert set(r.capabilities) == {Capability.recoil, Capability.solar, Capability.local_density}
    assert r.tables == benchmark().tables and r.parameters["beta"] == 0.9 and r.numerics["speeds"] == 1601
    assert "fixed benchmark; halo uncertainty not propagated" in r.summary
    assert any("no accepted-count ratio" in x for x in r.limitations)
    assert any("no annual modulation and no directional rates" in x for x in r.limitations)
    for consumer in ("direct-detection", "capture", "galactic-lines", "antiprotons"):
        assert halo_choice.unsupported(r, consumer) == ""
    for consumer in ("path1-structure", "flavour-vector", "private-si-curve", "private-search", "native-joint"):
        assert halo_choice.unsupported(r, consumer).startswith(halo_choice.CONSUMERS[consumer].name)
    assert not halo_choice.equivalent(r, resolve(halo_choice.fixed()))


def _changed(**update) -> halo_choice.FixedHalo:
    return benchmark().model_copy(update=update)


def test_every_physical_change_is_another_identity():
    base = resolve(benchmark()).identity
    eta = halo_choice._generated(benchmark().parameters.model_copy(update={"eta": 0.3}), benchmark().numerics, "SHM++")
    other_eta = _changed(parameters=benchmark().parameters.model_copy(update={"eta": 0.3}), halo=eta[0], sun=eta[1],
                         tables={"detector": shmpp.sha256(eta[0]), "sun": shmpp.sha256(eta[1])})
    swapped = _changed(halo=benchmark().sun, sun=benchmark().halo,
                       tables={"detector": benchmark().tables["sun"], "sun": benchmark().tables["detector"]})
    density = list(benchmark().halo.speed_density)
    density[700] *= 1.0 + 1e-6
    nudged = _changed(halo=benchmark().halo.model_copy(update={"speed_density": density}))
    newer = _changed(numerics=benchmark().numerics.model_copy(update={"generator": shmpp.GENERATOR + 1}))
    version = _changed(version=2)
    budget = _changed(full_calculations=4)
    identities = {resolve(x).identity for x in (other_eta, swapped, nudged, newer, version, budget)}
    assert base not in identities and len(identities) == 6
    relabelled = _changed(halo=benchmark().halo.model_copy(update={"label": "another name"}))
    assert resolve(relabelled).identity == base                     # a label is not physics


def test_a_snapshot_that_is_not_its_generators_output_is_refused():
    density = list(benchmark().halo.speed_density)
    density[700] *= 1.0 + 1e-6
    edited = _changed(halo=benchmark().halo.model_copy(update={"speed_density": density}))
    assert "bytes are not those its recorded sha256 names" in verify(edited)
    resealed = edited.model_copy(update={"tables": {**edited.tables, "detector": shmpp.sha256(edited.halo)}})
    assert "not its generator's output" in verify(resealed)
    swapped = _changed(halo=benchmark().sun, sun=benchmark().halo,
                       tables={"detector": benchmark().tables["sun"], "sun": benchmark().tables["detector"]})
    assert "not a table in the detector's frame" in verify(swapped)
    newer = _changed(numerics=benchmark().numerics.model_copy(update={"generator": shmpp.GENERATOR + 1}))
    assert f"version {shmpp.GENERATOR + 1} of the SHM++ generator" in verify(newer)
    for broken in (edited, resealed, swapped, newer):
        with pytest.raises(ValueError, match="nothing is calculated"):
            halo_region.checked(broken)
    with pytest.raises(UnknownHalo, match="not in the detector's frame"):
        swapped.detector()


def test_a_checkpoint_refuses_to_resume_across_any_change(tmp_path):
    from adroit.core.checkpoint import Checkpoint, CheckpointMismatch
    inputs = {"spec": "x", "halo": benchmark().model_dump(mode="json")}
    Checkpoint(tmp_path, inputs, {"code": "1"})
    density = list(benchmark().halo.speed_density)
    density[3] *= 1.0 + 1e-9
    for other in (_changed(halo=benchmark().halo.model_copy(update={"speed_density": density})), _changed(version=2),
                  halo_choice.fixed()):
        with pytest.raises(CheckpointMismatch, match="the halo differs"):
            Checkpoint(tmp_path, {**inputs, "halo": other.model_dump(mode="json")}, {"code": "1"}, resume=True)
    Checkpoint(tmp_path, inputs, {"code": "1"}, resume=True)


def test_the_sensitivity_halos_stay_in_the_family_and_never_edit_a_table():
    fixed = benchmark()
    lower = halo_choice.varied(fixed, {"v0_km_s": 220.0})
    assert frame_of(lower) == "detector" and lower.v0_km_s == 220.0 and lower.v_lsr_km_s == (0.0, 220.0, 0.0)
    assert lower.speed_density != fixed.halo.speed_density and lower.label.startswith("SHM++ sensitivity")
    assert shmpp.agrees(lower, fixed.parameters.model_copy(update={"v0_km_s": 220.0}), "detector",
                        fixed.numerics) == ""
    shm = halo_choice.varied(halo_choice.fixed(), {"v_esc_km_s": 600.0})      # phase 1's, unchanged
    assert shm == halo_choice.fixed().halo.model_copy(update={"v_esc_km_s": 600.0})
