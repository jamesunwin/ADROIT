"""Halo phase 1's shared contract (``adroit.core.halo_choice``): the registry, the fixed benchmark, the resolution of
every treatment, its identity, the comparisons a treatment does not support, and the requests that carry the choice.
Offline, no physics."""
from __future__ import annotations

import json
import threading

import pytest

from adroit.core import halo_choice
from adroit.core.dm_state import HaloModel
from adroit.core.halo_choice import FixedHalo, Treatment, UnknownHalo, resolve
from adroit.parameter_space import halo_limits, halo_region
from adroit.parameter_space.halo_region import HaloPreset

# the numbers each treatment's schema-1 requests were calculated with, pinned: a request saved with ``halo: published``,
# a preset or a benchmark is read by these, so a change to them is a new schema, never a silent reinterpretation
SHM_2105_00599 = dict(rho_gev_cm3=0.3, v0_km_s=238.0, v_esc_km_s=544.0, v_lsr_km_s=(0.0, 238.0, 0.0),
                      v_peculiar_km_s=(11.1, 12.2, 7.3), v_earth_km_s=(29.2, -0.1, 5.9))
PRESET = dict(rho_median_gev_cm3=0.40, sigma_ln_rho=0.35, v0_km_s=233.0, sigma_v0_km_s=20.0, v_esc_km_s=528.0,
              sigma_v_esc_km_s=30.0, level=0.95, interior=12, seed=20261019, full_calculations=2)


def test_the_historical_conventions_are_the_ones_saved_requests_were_calculated_with():
    assert HaloModel().model_dump(include=set(SHM_2105_00599)) == {k: v for k, v in SHM_2105_00599.items()}
    assert HaloPreset().model_dump(include=set(PRESET)) == PRESET
    centre = halo_limits.velocity_halo(233.0, 528.0, 0.4)
    assert centre.v_lsr_km_s == (0.0, 233.0, 0.0) and centre.v_peculiar_km_s == SHM_2105_00599["v_peculiar_km_s"]
    assert centre.v_earth_km_s == SHM_2105_00599["v_earth_km_s"]


def test_the_registry_has_stable_ids_apart_from_its_labels_and_the_lmc_is_not_available():
    assert list(halo_choice.FAMILIES) == ["shm", "shm-plus-plus", "shm-lmc"]
    assert [f.label for f in halo_choice.FAMILIES.values()] == ["SHM", "SHM++", "SHM + LMC"]
    assert halo_choice.available("shm").benchmark == "shm-2105.00599"
    assert halo_choice.available("shm-plus-plus").benchmark == "shmpp-1810.11468"      # halo phase 2
    with pytest.raises(UnknownHalo, match="not implemented yet.*no other halo stands in"):
        halo_choice.available("shm-lmc")
    with pytest.raises(UnknownHalo):
        halo_choice.fixed("shm-lmc")
    with pytest.raises(UnknownHalo, match="'einasto' is not a halo family; the families are shm, shm-plus-plus"):
        halo_choice.family("einasto")
    with pytest.raises(UnknownHalo, match="not a benchmark of SHM"):
        halo_choice.fixed("shm", "shm-lmc-benchmark")


def test_the_fixed_benchmark_is_the_documented_shm_copied_when_the_request_is_made():
    fixed = halo_choice.fixed()
    assert fixed.model_dump(mode="json")["halo"] == HaloModel().model_dump(mode="json")
    assert (fixed.family, fixed.benchmark, fixed.version, fixed.full_calculations) == ("shm", "shm-2105.00599", 1, 2)
    fixed.halo.v0_km_s = 999.0                                # a request's copy: the registry is not changed
    assert halo_choice.BENCHMARKS["shm-2105.00599"].halo.v0_km_s == 238.0
    assert halo_limits.parameterised(halo_choice.fixed().halo)
    assert not halo_limits.parameterised(HaloModel(v_lsr_km_s=(0.0, 250.0, 0.0)))
    with pytest.raises(ValueError, match="frozen"):
        halo_choice.fixed().benchmark = "other"


def test_each_treatment_resolves_to_its_numbers_conventions_and_capabilities():
    region = resolve(HaloPreset())
    assert region.treatment is Treatment.region and region.region["v0_km_s"] == 233.0
    assert region.halo == halo_limits.velocity_halo(233.0, 528.0, 0.4)
    assert set(region.data) == set(halo_choice.HALO_DATA) and all(region.data.values())
    benchmark = resolve(halo_choice.fixed())
    assert benchmark.treatment is Treatment.benchmark and benchmark.halo == HaloModel()
    assert benchmark.time.startswith("fixed date: 9 March") and benchmark.full_calculations == 2
    assert halo_choice.Capability.solar in benchmark.capabilities
    assert "halo uncertainty not propagated" in benchmark.summary.lower()
    published = resolve("published")
    assert published.treatment is Treatment.published and published.recorded and published.halo is None
    assert "different numerical assumptions" in published.summary
    legacy = resolve(None)                         # a Track 1 request saved before the choice existed
    assert legacy.treatment is Treatment.published and not legacy.recorded and "Not recorded" in legacy.summary
    track2 = resolve(None, track="track2")         # Track 2's established reading: recorded, each search's own halo
    assert track2.recorded and "signal search's for its fit" in track2.summary
    assert halo_choice.equivalent(legacy, track2) and not halo_choice.equivalent(published, region)
    with pytest.raises(UnknownHalo, match="not a halo treatment"):
        resolve("einasto")


def test_the_identity_is_stable_and_changes_with_physics_never_with_a_label(tmp_path, monkeypatch):
    base = resolve(halo_choice.fixed())
    assert resolve(halo_choice.fixed()).identity == base.identity and len(base.identity) == 64
    relabelled = halo_choice.fixed().model_copy(update={"halo": HaloModel(label="another name")})
    assert resolve(relabelled).identity == base.identity
    assert resolve(HaloPreset(label="renamed")).identity == resolve(HaloPreset()).identity
    for change in ({"v0_km_s": 239.0}, {"rho_gev_cm3": 0.31}, {"v_earth_km_s": (0.0, 0.0, 0.0)},
                   {"v_peculiar_km_s": (11.1, 12.24, 7.3)}):
        other = halo_choice.fixed().model_copy(update={"halo": HaloModel(**change)})
        assert resolve(other).identity != base.identity, change
    assert resolve(halo_choice.fixed().model_copy(update={"full_calculations": 3})).identity != base.identity
    assert resolve(HaloPreset(sigma_v0_km_s=21.0)).identity != resolve(HaloPreset()).identity
    for name, path in halo_choice.HALO_DATA.items():     # the same file name, other bytes: another identity
        copy = tmp_path / path
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes((halo_choice.PACKAGE / path).read_bytes())
    monkeypatch.setattr(halo_choice, "PACKAGE", tmp_path)
    assert resolve(halo_choice.fixed()).identity == base.identity
    (tmp_path / halo_choice.HALO_DATA["local densities"]).write_bytes(b"records: {}\n")
    changed = resolve(halo_choice.fixed())
    assert changed.identity != base.identity and halo_choice.equivalent(changed, base)


def test_a_data_file_changed_between_resolution_and_the_end_is_refused(tmp_path, monkeypatch):
    for path in halo_choice.HALO_DATA.values():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_bytes((halo_choice.PACKAGE / path).read_bytes())
    monkeypatch.setattr(halo_choice, "PACKAGE", tmp_path)
    resolution = resolve(HaloPreset())
    halo_choice.unchanged(resolution)
    (tmp_path / halo_choice.HALO_DATA["count-ratio validation"]).write_text("modules: {}\n")
    with pytest.raises(halo_choice.HaloDataChanged, match="count-ratio validation.*changed during the calculation"):
        halo_choice.unchanged(resolution)
    halo_choice.unchanged(resolve("published"))           # reads none of them


def test_what_a_treatment_cannot_calculate_is_named():
    region, benchmark, published = resolve(HaloPreset()), resolve(halo_choice.fixed()), resolve("published")
    for consumer in ("path1-structure", "flavour-vector", "private-si-curve", "private-search", "native-joint"):
        assert halo_choice.unsupported(published, consumer) == ""
        for r in (region, benchmark):
            reason = halo_choice.unsupported(r, consumer)
            assert reason.startswith(halo_choice.CONSUMERS[consumer].name) and r.label in reason
    for consumer in ("direct-detection", "capture", "galactic-lines", "antiprotons"):
        assert halo_choice.unsupported(benchmark, consumer) == ""
    thin = benchmark.model_copy(update={"capabilities": [halo_choice.Capability.recoil]})
    assert "supplies no a solar-frame velocity distribution" in halo_choice.unsupported(thin, "capture")


def test_requests_carry_the_benchmark_and_earlier_requests_keep_their_identity():
    from adroit.orchestrator.signal import SignalRequest
    from adroit.orchestrator.track1 import Track1Request
    from adroit.parameter_space import simplified
    fixed = halo_choice.fixed()
    spec = simplified.model("vector", 10, 1000)
    for request in (Track1Request(spec=spec), SignalRequest(experiment="CDMS II Si (2013)")):
        assert "halo" not in request.model_dump(mode="json")                 # unset: the earlier identity
        chosen = request.model_copy(update={"halo": fixed})
        saved = json.loads(chosen.model_dump_json())
        assert saved["halo"]["treatment"] == "benchmark" and saved["halo"]["halo"]["v0_km_s"] == 238.0
        assert type(request).model_validate_json(chosen.model_dump_json()).halo == fixed
    preset = Track1Request(spec=spec, halo=HaloPreset())
    assert isinstance(Track1Request.model_validate_json(preset.model_dump_json()).halo, HaloPreset)
    assert Track1Request.model_validate_json(Track1Request(spec=spec, halo="published").model_dump_json()).halo \
        == "published"
    evaluation = halo_region.HaloEvaluation(region="r")
    assert "treatment" not in evaluation.model_dump(mode="json")                # an earlier save's identity


def test_two_requests_in_two_threads_never_see_each_others_halo():
    from adroit.orchestrator.signal import fixed_halo
    a, b = halo_choice.fixed(), HaloPreset(v0_km_s=240.0)
    barrier, seen = threading.Barrier(2), {}

    def run(name, value):
        with halo_region.using(value):
            barrier.wait()
            seen[name] = (halo_region.preset(), fixed_halo())
            barrier.wait()
            seen[name + " again"] = halo_region.preset()
    threads = [threading.Thread(target=run, args=("a", a)), threading.Thread(target=run, args=("b", b))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert seen["a"] == (a, a) and seen["b"] == (b, None)
    assert seen["a again"] == a and seen["b again"] == b and halo_region.preset() is None


def test_a_saved_fixed_halo_of_a_family_not_available_is_refused_not_run():
    crafted = FixedHalo(family="shm-lmc", benchmark="shm-2105.00599", version=1, halo=HaloModel())
    with pytest.raises(UnknownHalo, match="SHM \\+ LMC.*not implemented yet"):
        halo_region.checked(crafted)
    off = halo_choice.fixed().model_copy(update={"halo": HaloModel(v_lsr_km_s=(0.0, 250.0, 0.0))})
    with pytest.raises(ValueError, match="not one the direct-detection machinery evaluates at"):
        halo_region.checked(off)
