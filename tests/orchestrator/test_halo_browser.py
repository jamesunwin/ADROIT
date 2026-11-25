"""Halo phase 1's release browser layer, offline: its journeys and controls registered with the runner, each halo
mutation applied only in the processes it names and restoring its defect there (``scripts/netguard/
acceptance_mutations.py``), and the substitutions printed only for the journeys run. No browser, no child process."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "netguard"))

import acceptance_mutations as mutations  # noqa: E402
import browser_acceptance  # noqa: E402
import browser_halo  # noqa: E402

from adroit.core import checkpoint, halo_choice  # noqa: E402
from adroit.parameter_space import halo_region  # noqa: E402
from adroit.parameter_space.halo_region import HaloPreset  # noqa: E402

CLI = [sys.executable, "-m", "adroit.orchestrator.cli"]


def test_the_halo_journeys_and_controls_run_with_the_release_layer():
    assert set(browser_halo.JOURNEYS) <= set(browser_acceptance.JOURNEYS)
    for journey, mutation, invariant in browser_halo.CONTROLS:
        assert (journey, mutation, invariant) in browser_acceptance.CONTROLS and mutation in mutations.MUTATIONS
    assert set(browser_acceptance.substituted(["halo_track1"])) == {
        name for name, journeys in browser_halo.DESCRIBES.items() if "halo_track1" in journeys}
    assert not set(browser_acceptance.substituted(["intake"])) & set(browser_halo.SUBSTITUTED)


def test_each_halo_mutation_is_applied_only_in_its_processes():
    module, where, _ = mutations.MUTATIONS["halo_dropped_by_child"]
    assert where([*CLI, "track1", "m.yaml"]) and not where([*CLI, "workbench", "--port", "1"])
    for argv in ([*CLI, "track1", "m.yaml"], [*CLI, "track1", "m.yaml", "--resume"]):     # the first run and its resume
        assert mutations.MUTATIONS["halo_checkpoint_identity_omitted"][1](argv)
    assert not mutations.MUTATIONS["halo_checkpoint_identity_omitted"][1]([*CLI, "workbench", "--port", "1"])
    assert mutations.MUTATIONS["halo_export_unqualified"][1]([*CLI, "evidence", "tables", "r.json", "--out", "o"])
    for name in ("halo_form_ignored", "future_family_as_shm"):
        assert mutations.MUTATIONS[name][1]([*CLI, "workbench", "--port", "1"])
        assert not mutations.MUTATIONS[name][1]([*CLI, "track1", "m.yaml"])


def test_each_halo_mutation_restores_its_defect(tmp_path):
    from adroit.evidence import halo
    from adroit.ui import forms
    m = SimpleNamespace(halo_flags=forms.halo_flags)
    mutations._halo_form_ignored(m)
    assert m.halo_flags("track1", "benchmark") == [] and forms.halo_flags("track1", "benchmark")
    m = SimpleNamespace(of=halo_region.of)
    mutations._halo_dropped_by_child(m)
    assert m.of(halo_choice.fixed()) is None and m.of(HaloPreset()) == HaloPreset()
    m = SimpleNamespace(Checkpoint=type("Copy", (checkpoint.Checkpoint,), {}))
    mutations._halo_checkpoint_identity_omitted(m)
    m.Checkpoint(tmp_path, {"spec": "x", "halo": "published"}, {"code": "1"})
    m.Checkpoint(tmp_path, {"spec": "x", "halo": "other"}, {"code": "1"}, resume=True)       # taken: the defect
    m = SimpleNamespace(point_label=halo.point_label)
    mutations._halo_export_unqualified(m)
    assert m.point_label(None, None) == ""
    m = SimpleNamespace(FAMILIES=dict(halo_choice.FAMILIES))
    mutations._future_family_as_shm(m)
    assert m.FAMILIES["shm-lmc"].available and not halo_choice.FAMILIES["shm-lmc"].available


def test_the_shmpp_journeys_controls_and_substitutions_are_registered():
    assert {"shmpp_track1", "shmpp_track2"} <= set(browser_acceptance.JOURNEYS)
    mine = [c for c in browser_halo.CONTROLS if c[0].startswith("shmpp")]
    assert {m for _, m, _ in mine} == {"shmpp_as_shm", "shmpp_isotropic", "shmpp_frames_interchanged",
                                       "shmpp_continuation_reset"}
    assert {"the SHM++ journeys' calculations", "the SHM++ journeys' stale copy"} <= \
        set(browser_acceptance.substituted(["shmpp_track1"]))
    for name in ("shmpp_as_shm", "shmpp_isotropic", "shmpp_frames_interchanged"):
        assert mutations.MUTATIONS[name][1]([*CLI, "track1", "m.yaml"])
        assert not mutations.MUTATIONS[name][1]([*CLI, "workbench", "--port", "1"])
    assert mutations.MUTATIONS["shmpp_continuation_reset"][1]([*CLI, "workbench", "--port", "1"])
    assert not mutations.MUTATIONS["shmpp_continuation_reset"][1]([*CLI, "track1", "m.yaml"])


def test_a_generator_defect_is_planted_in_a_track1_run_and_the_workers_it_spawns(monkeypatch):
    """A defect in the code is in every process of a run: the two generator mutations reach the scan workers a Track 1
    run spawns (they check the snapshot they are given, the halo phase 2 audit's HB-02), and no other spawned process."""
    import multiprocessing.spawn
    worker = [sys.executable, *multiprocessing.spawn.get_command_line(tracker_fd=3, pipe_handle=4)[1:]]
    monkeypatch.delenv(mutations.SPAWNED_BY, raising=False)
    for name in ("shmpp_isotropic", "shmpp_frames_interchanged"):
        where = mutations.MUTATIONS[name][1]
        assert not where(worker)                                   # a worker of anything else: not planted
        monkeypatch.setattr(sys, "orig_argv", [*CLI, "track1", "m.yaml"])
        planted = []
        monkeypatch.setattr(sys, "meta_path", [*sys.meta_path])
        mutations.install(name)                                    # the run: planted, and named to its workers
        planted.append(isinstance(sys.meta_path[0], mutations._Hook))
        assert planted == [True] and where(worker)                 # a worker the run spawns: planted
        monkeypatch.delenv(mutations.SPAWNED_BY)
    assert not mutations.MUTATIONS["shmpp_as_shm"][1](worker)       # the others as before


def test_each_shmpp_mutation_restores_its_defect():
    import numpy as np
    from adroit.halo_models import shm_plus_plus as shmpp
    from adroit.orchestrator import reanalysis
    from adroit.parameter_space import halo_limits
    fixed, p = halo_choice.fixed("shm-plus-plus"), shmpp.BENCHMARK
    m = SimpleNamespace(State=halo_limits.State, at_tables=halo_limits.at_tables)
    mutations._shmpp_as_shm(m)
    assert m.at_tables(fixed, halo_limits.Budget(0)).table is None
    assert halo_limits.at_tables(fixed, halo_limits.Budget(0)).table is not None
    m = SimpleNamespace(dispersions=shmpp.dispersions, n_round=shmpp.n_round, n_sausage=shmpp.n_sausage)
    mutations._shmpp_isotropic(m)
    assert m.dispersions(p)[0] == m.dispersions(p)[1] and m.n_sausage(p) == shmpp.n_round(p)
    assert shmpp.dispersions(p)[0] != shmpp.dispersions(p)[1]
    m = SimpleNamespace(Parameters=type("Copy", (shmpp.Parameters,), {}))
    mutations._shmpp_frames_interchanged(m)
    assert np.allclose(m.Parameters(**p.model_dump()).boost("detector"), p.v_sun())
    assert np.allclose(p.boost("detector"), p.v_detector())
    m = SimpleNamespace(_converted_halo=reanalysis._converted_halo)
    mutations._shmpp_continuation_reset(m)
    saved = {"halo": fixed.model_dump(mode="json")}
    assert m._converted_halo("track1", saved, "signal")["halo"]["family"] == "shm"
    assert reanalysis._converted_halo("track1", saved, "signal")["halo"]["family"] == "shm-plus-plus"
