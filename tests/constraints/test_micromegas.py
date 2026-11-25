"""micrOMEGAs as a cross-check (constraints.micromegas): the parameter mapping and, if built, runs.

Unit tests are pure (no subprocess). Tests marked ``slow`` call the compiled
micrOMEGAs executables and are skipped automatically when they are not built.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from adroit.constraints import micromegas as md

HERE = Path(__file__).parent
IDM_EXE = md.resolve_install(None) / "IDM" / md.EXECUTABLE_NAME
needs_idm = pytest.mark.skipif(not IDM_EXE.is_file(), reason="micrOMEGAs IDM driver not built")

BP1 = {"M_H0": 72.77, "M_A0": 107.803, "M_Hpm": 114.639, "lambda_2": 0.722565,
       "lambda_345": -0.00440723, "m_h": 125.09}

CANNED = """VERTEX: W- W+ h
PROCESS: ~X,~X->AllEven,1*x{A,Z
MO_INFO micrO=/x/micromegas_7.1.10 cdm=~X Mcdm=72.77 spin2=0 pdg=35 charge3=0 cdim=1
MO_VAR name=la3 value=0.25
MO_OMEGA mode=0:0 VWdecay=0 VZdecay=0 fast=0 Beps=1e-05 Omega=0.93 Xf=22.1 err=0 wh=0.00307 time=0.01
MO_CHANNEL mode=0:0 frac=0.99 proc=~X,~X->W+,W-
MO_OMEGA mode=1:1 VWdecay=1 VZdecay=1 fast=0 Beps=1e-05 Omega=0.123 Xf=23.1 err=0 wh=0.00399 time=0.4
MO_DONE status=0
"""


# ---------------------------------------------------------------- unit tests
def test_resolve_params_maps_aliases_with_factors() -> None:
    native = md.resolve_params("IDM", BP1)
    assert native["MHX"] == 72.77 and native["MHC"] == 114.639
    assert native["laL"] == pytest.approx(-0.00440723 / 2)  # lambda_L = lambda_345 / 2
    assert native["Mh"] == 125.09


def test_resolve_params_passes_native_names_and_singlet_factor() -> None:
    assert md.resolve_params("IDM", {"MbMb": 4.23}) == {"MbMb": 4.23}
    assert md.resolve_params("SingletDM", {"lambda_hs": 0.2})["laSH"] == pytest.approx(0.1)


@pytest.mark.parametrize("params", [
    {"lambda_L": 0.01, "lambda_345": 0.02},     # both map to laL
    {"bad name": 1.0},
    {"MHX": float("nan")},
])
def test_resolve_params_rejects_bad_input(params: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        md.resolve_params("IDM", params)


def test_resolve_params_unknown_model() -> None:
    with pytest.raises(KeyError):
        md.resolve_params("NoSuchModel", {})


def test_settings_normalise_modes() -> None:
    assert md.OmegaSettings(vv_modes=[0, "1", "2:1"]).vv_modes == ["0:0", "1:1", "2:1"]
    with pytest.raises(ValidationError):
        md.OmegaSettings(vv_modes=["x"])


def test_build_command_contains_all_options() -> None:
    s = md.OmegaSettings(vv_modes=["0", "1"], fixed_widths={"h": 4.1e-3}, channel_cut=0.05)
    cmd = md.build_command(Path("/x/mo_omega"), {"MHX": 72.77}, s, ("la3",))
    assert cmd[:3] == ["/x/mo_omega", "-m", "0:0,1:1"]
    pairs = list(zip(cmd, cmd[1:], strict=False))
    for pair in (("-f", "0"), ("-w", "h=0.0041"), ("-c", "0.05"), ("-v", "la3")):
        assert pair in pairs
    assert cmd[-1] == "MHX=72.77"


def test_parse_output_reads_all_record_types() -> None:
    p = md.parse_output(CANNED)
    assert p["done"] and not p["errors"]
    assert p["info"]["cdm"] == "~X" and p["vars"] == {"la3": 0.25}
    assert [m.mode for m in p["modes"]] == ["0:0", "1:1"]
    assert p["modes"][0].channels[0].process == "~X,~X->W+,W-"
    assert p["modes"][1].higgs_width_gev == pytest.approx(0.00399)


def test_summarise_picks_primary_mode() -> None:
    p = md.parse_output(CANNED)
    assert md._summarise(p, md.OmegaSettings(vv_modes=["0", "1"])) == (0.123, 23.1)
    assert md._summarise(p, md.OmegaSettings(vv_modes=["0", "1"], primary_mode="0")) == (0.93, 22.1)


def test_install_version() -> None:
    assert md.install_version(Path("/a/micromegas_7.1.10")) == "micrOMEGAs 7.1.10"


def test_missing_executable_gives_error_status(tmp_path: Path) -> None:
    req = md.OmegaRequest(model="IDM", params=BP1, install_dir=str(tmp_path / "micromegas_9.9"))
    res = md.run_micromegas(req)
    assert res.status == "error" and "not found" in res.error
    assert res.version == "micrOMEGAs 9.9"


# ---------------------------------------------------------- integration tests
@pytest.mark.slow
@needs_idm
def test_idm_bp1_matches_reference_values() -> None:
    res = md.run_micromegas(md.OmegaRequest(model="IDM", params=BP1))
    assert res.status == "ok", res.error
    by_mode = {m.mode: m for m in res.modes}
    # micrOMEGAs 7.1.10 (fast=0): 0.1229; publication (micrOMEGAs 4.3.5): 0.12007
    assert res.omega_h2 == pytest.approx(0.12285, rel=0.01)
    assert res.omega_h2 == pytest.approx(0.12007, rel=0.05)
    assert by_mode["0:0"].omega_h2 > 5 * by_mode["1:1"].omega_h2  # W W* dominates
    assert res.dm_name == "~X" and res.dm_mass_gev == pytest.approx(72.77)
    lam = res.derived
    assert lam["la3"] + lam["la4"] + lam["la5"] == pytest.approx(-0.00440723, abs=1e-8)


@pytest.mark.slow
@needs_idm
def test_fixed_higgs_width_is_applied() -> None:
    s = md.OmegaSettings(vv_modes=["0", "1"], fixed_widths={"h": 4.1e-3})
    res = md.run_micromegas(md.OmegaRequest(model="IDM", params=BP1, settings=s))
    assert res.status == "ok", res.error
    assert all(m.higgs_width_gev == pytest.approx(4.1e-3) for m in res.modes)


@pytest.mark.slow
@needs_idm
def test_unknown_native_parameter_reports_error() -> None:
    res = md.run_micromegas(md.OmegaRequest(model="IDM", params={"NotAVar": 1.0}))
    assert res.status == "error" and "unknown_parameter" in res.error


@pytest.mark.slow
@needs_idm
def test_timeout_is_reported() -> None:
    s = md.OmegaSettings(vv_modes=["1"], timeout_s=0.05)
    res = md.run_micromegas(md.OmegaRequest(model="IDM", params=BP1, settings=s))
    assert res.status == "timeout"


@pytest.mark.slow
@pytest.mark.parametrize("model,params", [
    ("SingletDM", {"M_S": 700.0, "lambda_hs": 0.3, "lambda_s": 0.1, "m_h": 125.09}),
    ("ZpPortal", {"M_DM": 500.0, "M_Zp": 1500.0, "g_SM": 0.1, "g_DM": 0.5}),
])
def test_other_models_run(model: str, params: dict[str, float]) -> None:
    exe = md.resolve_install(None) / md.MODELS[model].directory / md.EXECUTABLE_NAME
    if not exe.is_file():
        pytest.skip(f"{model} driver not built")
    res = md.run_micromegas(md.OmegaRequest(model=model, params=params))
    assert res.status == "ok", res.error
    assert 1e-4 < res.omega_h2 < 10


@pytest.mark.slow
@needs_idm
def test_cli_json_round_trip() -> None:
    req = json.dumps({"model": "IDM", "params": BP1, "settings": {"vv_modes": [0]}})
    out = subprocess.run([sys.executable, "-m", "adroit.constraints.micromegas", "-"],
                         input=req, capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stdout + out.stderr
    data = json.loads(out.stdout)
    assert data["status"] == "ok" and data["version"] == "micrOMEGAs 7.1.10"
    assert set(data) >= {"omega_h2", "x_f", "settings", "version"}
