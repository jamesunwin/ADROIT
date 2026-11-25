"""What micrOMEGAs answers, checked against the request before it is called a result (an operating-conditions audit's
IE-02, 2026-11-10; ``micromegas._unusable``).

A stand-in ``mo_omega`` in a stand-in installation prints a set answer and exits 0, through the real adapter and its
command line. The auditor's responses: MO_DONE alone, the mode's row with err=1, the requested mode absent and another
present, Ωh² NaN or negative had each been "ok" (the command line exiting 0), with the last mode's or the erring mode's
Ωh² as the result; incomplete MO_OMEGA fields had raised KeyError out of the adapter."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from adroit.constraints import micromegas as md

INFO = "MO_INFO micrO=/x/micromegas_7.1.10 cdm=~X Mcdm=72.77 spin2=0 pdg=35 charge3=0 cdim=1\n"
DONE = "MO_DONE status=0\n"


def row(mode: str = "1:1", omega: str = "0.123", xf: str = "23.1", err: str = "0") -> str:
    w, z = mode.split(":")
    return (f"MO_OMEGA mode={mode} VWdecay={w} VZdecay={z} fast=0 Beps=1e-05 Omega={omega} Xf={xf} err={err} "
            "wh=0.00399 time=0.4\n")


@pytest.fixture
def install(tmp_path):
    """A micrOMEGAs installation whose IDM ``mo_omega`` prints ``answer.txt`` and exits with ``code.txt``."""
    folder = tmp_path / "micromegas_7.1.10"
    (folder / "IDM").mkdir(parents=True)
    exe = folder / "IDM" / md.EXECUTABLE_NAME
    exe.write_text(f'#!/bin/sh\ncat "{folder / "answer.txt"}"\nexit "$(cat "{folder / "code.txt"}")"\n')
    exe.chmod(0o755)
    (folder / "code.txt").write_text("0")
    return folder


def _answer(install: Path, text: str, modes=("1:1",), primary=None):
    (install / "answer.txt").write_text(text)
    request = md.OmegaRequest(model="IDM", params={"M_H0": 72.77}, install_dir=str(install),
                              settings={"vv_modes": list(modes), "primary_mode": primary})
    return request, md.run_micromegas(request)


def _cli(request: md.OmegaRequest) -> tuple[int, dict]:
    done = subprocess.run([sys.executable, "-m", "adroit.constraints.micromegas", request.model_dump_json()],
                          capture_output=True, text=True, timeout=120)
    return done.returncode, json.loads(done.stdout)


def test_a_complete_answer_for_the_requested_mode_is_ok(install):
    request, result = _answer(install, INFO + row("0:0", "0.93", "22.1") + row() + DONE, modes=("0:0", "1:1"))
    assert result.status == "ok" and result.error is None
    assert (result.omega_h2, result.x_f, result.dm_mass_gev) == (0.123, 23.1, 72.77)
    assert _cli(request)[0] == 0


BAD = {
    "MO_DONE alone": (INFO + DONE, "no result for the requested mode 1:1"),
    "the mode's row with err=1": (INFO + row(err="1") + DONE, "darkOmega reported error 1 for the mode 1:1"),
    "the requested mode absent, another present": (INFO + row("0:0", "0.93") + DONE, "no result for the requested mode 1:1"),
    "Ωh² NaN": (INFO + row(omega="nan") + DONE, "Ωh² for the mode 1:1 is nan"),
    "Ωh² negative": (INFO + row(omega="-0.1") + DONE, "Ωh² for the mode 1:1 is -0.1"),
    "Ωh² zero": (INFO + row(omega="0") + DONE, "Ωh² for the mode 1:1 is 0.0"),
    "x_f not finite": (INFO + row(xf="inf") + DONE, "x_f for the mode 1:1 is inf"),
    "the mode answered twice": (INFO + row() + row(omega="0.2") + DONE, "more than one result for the mode 1:1"),
    "incomplete MO_OMEGA fields": (INFO + "MO_OMEGA mode=1:1 Omega=0.12\n" + DONE, "cannot be read (KeyError"),
    "a number that is not one": (INFO + row(omega="abc") + DONE, "cannot be read (ValueError"),
    "a channel of no mode": (INFO + row() + "MO_CHANNEL mode=2:2 frac=0.5 proc=x\n" + DONE, "cannot be read (KeyError"),
    "a dark-matter mass that is not one": (INFO.replace("72.77", "abc") + row() + DONE, "cannot be read (ValueError"),
}


@pytest.mark.parametrize("case", list(BAD))
def test_an_answer_that_is_not_the_requested_result_is_an_error_with_no_density(install, case):
    """Each of the auditor's responses (and its kin), the process exiting 0: an error naming why, no Ωh² or x_f in
    its summary (never another mode's), and the command line exits 1."""
    text, why = BAD[case]
    request, result = _answer(install, text)
    assert result.status == "error" and why in result.error
    assert result.omega_h2 is None and result.x_f is None
    code, printed = _cli(request)
    assert code == 1 and printed["status"] == "error" and printed["omega_h2"] is None


def test_every_requested_mode_must_be_answered_but_only_the_primary_is_the_result(install):
    """A requested mode missing is an error even where the primary is answered; another mode's own err stays in its row
    (``modes``), the result being the primary's."""
    request, result = _answer(install, INFO + row() + DONE, modes=("0:0", "1:1"))
    assert result.status == "error" and "no result for the requested mode 0:0" in result.error
    request, result = _answer(install, INFO + row("0:0", "0.93", err="2") + row() + DONE, modes=("0:0", "1:1"))
    assert result.status == "ok" and result.omega_h2 == 0.123 and result.modes[0].err == 2
    request, result = _answer(install, INFO + row("0:0", "0.93", err="2") + row() + DONE, modes=("0:0", "1:1"),
                              primary="0:0")
    assert result.status == "error" and "darkOmega reported error 2 for the mode 0:0" in result.error


def test_a_failed_exit_keeps_its_error_and_gives_no_density(install):
    (install / "code.txt").write_text("7")
    request, result = _answer(install, INFO + row() + "MO_ERROR msg=unknown_parameter name=XX\n")
    assert result.status == "error" and "unknown_parameter" in result.error and result.omega_h2 is None
    assert _cli(request)[0] == 1


def test_the_cross_check_shows_no_micromegas_density_for_an_unusable_answer(install, monkeypatch):
    """``parameter_space.crosscheck``, the adapter's one caller, reads its Ωh² and error: it had shown the erring
    mode's Ωh² beside ADROIT's (and a ratio)."""
    from adroit.parameter_space import crosscheck, library
    from adroit.parameter_space.classes import Point
    (install / "answer.txt").write_text(INFO + row(err="1") + DONE)
    monkeypatch.setattr(md, "resolve_install", lambda request_dir: install)
    monkeypatch.setattr(type(library.entry("inert_doublet").model_class), "omega_h2", lambda self, point: 0.12)
    point = Point(m_chi=72.77, m_med=114.6, g_chi=-0.0044, g_q=35.0)
    check = crosscheck.crosscheck("inert_doublet", point)
    assert check.micromegas is None and check.ratio is None and "darkOmega reported error 1" in check.error
