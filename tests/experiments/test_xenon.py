"""DIAMX's subprocess environment (experiments.xenon)."""

import pytest


def test_diamx_runs_with_every_numerical_thread_pool_capped(monkeypatch) -> None:
    from adroit.experiments import xenon
    monkeypatch.setenv("XLA_FLAGS", "--xla_cpu_enable_fast_math=false")
    monkeypatch.setenv("PJRT_NPROC", "10")
    env = xenon.capped_environment(2)
    assert all(env[name] == "2" for name in xenon.THREAD_VARIABLES)
    assert {"PJRT_NPROC", "NPROC", "VECLIB_MAXIMUM_THREADS"} <= set(xenon.THREAD_VARIABLES)
    assert env["XLA_FLAGS"] == "--xla_cpu_enable_fast_math=false --xla_cpu_multi_thread_eigen=false"
    assert xenon.capped_environment()["OMP_NUM_THREADS"] == str(xenon.get_settings().numerical_threads)


def test_diamx_may_skip_only_a_spectrum_it_cannot_see(tmp_path) -> None:
    """A finished DIAMX result may lack a spectrum with no events below the xenon regions of interest (an
    inelastic signal far above them): it gets no limit. A missing spectrum that DIAMX could see, a foreign label
    or a non-finite limit leaves the result incomplete, as the external audit required."""
    import json
    import numpy as np
    from adroit.experiments import xenon
    energies = xenon.ENERGIES_KEV
    flat, high = np.ones_like(energies), np.where(energies > 70.0, 1.0, 0.0)
    path = tmp_path / "result.json"
    path.write_text("[]")
    assert xenon._finished(path, {7: high}) == {}
    assert xenon._finished(path, {7: flat}) is None
    path.write_text(json.dumps([{"label": 8, "upper": 2.5}]))
    assert xenon._finished(path, {7: high, 8: flat}) == {8: {"label": 8, "upper": 2.5}}
    for bad in ('[{"label": 9, "upper": 1.0}]', '[{"label": 8, "upper": NaN}]', "[{"):
        path.write_text(bad)
        assert xenon._finished(path, {7: high, 8: flat}) is None, bad


@pytest.mark.needs("solar_model")
def test_one_failing_module_does_not_stop_the_others(monkeypatch) -> None:
    from adroit.orchestrator import exclusion
    original = exclusion._module_limits

    def flaky(module, request, masses):
        if module.info.name == "PICO-60 C3F8 (2019)":
            raise RuntimeError("DIAMX returned incomplete or nonfinite limits")
        return original(module, request, masses)

    monkeypatch.setattr(exclusion, "_module_limits", flaky)
    result = exclusion.run(exclusion.ExclusionRequest(card_id="O1", masses_gev=[50.0],
                                                      modules=["PICO-60 C3F8 (2019)", "DEAP-3600 (2019)"]))
    assert [row.experiment for row in result.per_module] == ["DEAP-3600 (2019)"]
    assert "calculation failed: RuntimeError" in result.skipped["PICO-60 C3F8 (2019)"]
