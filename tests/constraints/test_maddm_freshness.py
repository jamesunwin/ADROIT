"""Failed/partial engine attempts must never consume an earlier output."""
import subprocess
from types import SimpleNamespace

import pytest

from adroit.constraints import maddm


@pytest.fixture
def engine(tmp_path, monkeypatch):
    model, backend, work = [tmp_path / name for name in ("model", "backend", "work")]
    for path in (model, backend / "bin", work):
        path.mkdir(parents=True)
    (model / "particles.py").write_text("x = Particle(pdg_code=99, name='x', width=Param.WX)")
    (backend / "bin/maddm").write_text("backend v1")
    monkeypatch.setattr(maddm, "mg5_dir", lambda: backend)
    return model, backend, work


@pytest.mark.parametrize("mode", ["run", "widths"])
def test_nonzero_exit_rejects_stale_sentinels(engine, monkeypatch, mode):
    model, _, work = engine
    old = work / "benchmark/output/run_01"
    old.mkdir(parents=True)
    (old / "MadDM_results.txt").write_text("Omegah2 = 0.777\nx_f = 25\nsigmav_xf = 1e-26")
    (old / "maddm.out").write_text("alpha_u: 1 : 0 : 0 : 0")
    (work / "widths.txt").write_text("DECAY 99 42")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: SimpleNamespace(
        returncode=7, stdout="failed", stderr="engine error"))
    with pytest.raises(RuntimeError, match="exit 7"):
        if mode == "run":
            maddm.run(model, "x", {}, "benchmark", work)
        else:
            maddm.widths(model, ["x"], work)
    assert list(work.glob("*/engine.log"))
    assert not list(work.glob("cache-*.json"))


def test_timeout_retains_log(engine, monkeypatch):
    model, _, work = engine
    def timeout(*a, **kw):
        raise subprocess.TimeoutExpired("engine", 10, output="partial")
    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="timed out"):
        maddm.run(model, "x", {}, "benchmark", work)
    assert "partial" in next(work.glob("*/engine.log")).read_text()


def _success(monkeypatch, calls, *, partial=False, nonfinite=False):
    def run(command, *, cwd, **kw):
        calls.append(cwd)
        if command[-1].endswith("widths.mg5"):
            (cwd / "widths.txt").write_text("DECAY 99 0.12")
        else:
            output = cwd / "benchmark/output/run_01"
            output.mkdir(parents=True)
            omega = "1e999" if nonfinite else "0.12"
            (output / "MadDM_results.txt").write_text(f"Omegah2 = {omega}\nx_f = 25\nsigmav_xf = 2e-26")
            if not partial:
                (output / "maddm.out").write_text("alpha_u: 1 : 0 : 0 : 0")
        return SimpleNamespace(returncode=0, stdout="success", stderr="")
    monkeypatch.setattr(subprocess, "run", run)


@pytest.mark.parametrize("partial,nonfinite", [(True, False), (False, True)])
def test_invalid_current_output_is_rejected(engine, monkeypatch, partial, nonfinite):
    model, _, work = engine
    _success(monkeypatch, [], partial=partial, nonfinite=nonfinite)
    with pytest.raises(RuntimeError):
        maddm.run(model, "x", {}, "benchmark", work)
    assert not list(work.glob("cache-*.json"))


def test_reuse_binds_model_parameters_backend_and_output(engine, monkeypatch):
    model, backend, work = engine
    calls = []
    _success(monkeypatch, calls)
    def run(params=None):
        return maddm.run(model, "x", params or {}, "benchmark", work)
    assert run().omega_h2 == 0.12
    assert run().omega_h2 == 0.12 and len(calls) == 1
    run({"m": 20})
    assert len(calls) == 2
    (backend / "bin/maddm").write_text("backend v2")
    run()
    assert len(calls) == 3
    (model / "parameters.py").write_text("mass=30")
    run()
    assert len(calls) == 4
    (calls[-1] / "benchmark/output/run_01/maddm.out").write_text("corrupt")
    run()
    assert len(calls) == 5
    assert len(set(calls)) == 5


def test_width_success_and_verified_reuse(engine, monkeypatch):
    model, _, work = engine
    calls = []
    _success(monkeypatch, calls)
    assert maddm.widths(model, ["x"], work) == {99: 0.12}
    assert maddm.widths(model, ["x"], work) == {99: 0.12}
    assert len(calls) == 1


def test_partial_width_card_is_rejected(engine, monkeypatch):
    model, _, work = engine
    _success(monkeypatch, [])
    with pytest.raises(RuntimeError, match="Missing requested width"):
        maddm.widths(model, ["absent"], work)
