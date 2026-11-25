"""What the optimum interval's program returns, checked before any caller sees it, and its deadline (an
operating-conditions audit's IE-03 and IE-04, 2026-11-10; ``optimum_interval``'s module docstring).

The program is a stand-in executable printing a set answer, its calls counted; the cache is real, in a folder of the
test's. The auditor's fixture: "3.0 0" gives 0.3 for ten expected events, while "-1.0 0" and "nan 0" had reached both
limit procedures, with the cache or without it (the cache stored neither, but returned each), and a program that slept
was stopped only by the auditor's own watchdog."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from adroit.core import calculation_cache
from adroit.core.config import Settings
from adroit.core.dm_state import DarkMatterParticle, ExpectedSignal
from adroit.experiments import base, private_search
from adroit.statistics import optimum_interval as oi

STAND_IN = '''
import os, subprocess, sys, time
from pathlib import Path
here = Path(sys.argv[1])
sys.stdin.read()
with (here / "calls").open("a") as calls:
    calls.write("1")
answer = (here / "answer").read_text()
if answer == "sleep":                              # the program and a descendant, sleeping
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    (here / "pids").write_text(f"{os.getpid()} {child.pid}")
    time.sleep(60)
if answer.startswith("exit "):                   # "exit N", or "exit N: TEXT", TEXT printed first
    code, _, text = answer[5:].partition(": ")
    print(text)
    sys.stderr.write("the stand-in failed\\n")
    sys.exit(int(code))
print(answer)
'''


class _Program:
    """The optimum interval's executable, a stand-in answering ``answer`` (module docstring)."""

    def __init__(self, folder: Path, monkeypatch) -> None:
        folder.mkdir()
        self.folder = folder
        (folder / "stand_in.py").write_text(STAND_IN)
        self.binary = folder / "adroit_oi"
        self.binary.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{folder / "stand_in.py"}" "{folder}"\n')
        self.binary.chmod(0o755)
        self.cache = folder.parent / "data"
        monkeypatch.setattr(oi, "executable", lambda: self.binary)
        monkeypatch.setattr(oi.cache_identity, "native", lambda binary: {"stand-in": self.answer})
        monkeypatch.setattr(calculation_cache, "get_settings", lambda: Settings(data_dir=self.cache))
        monkeypatch.delenv("ADROIT_CALCULATION_CACHE", raising=False)
        monkeypatch.delenv("ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S", raising=False)

    @property
    def answer(self) -> str:
        return (self.folder / "answer").read_text()

    def answers(self, text: str) -> None:
        (self.folder / "answer").write_text(text)

    @property
    def calls(self) -> int:
        path = self.folder / "calls"
        return len(path.read_text()) if path.exists() else 0

    def stored(self) -> list[Path]:
        return sorted(self.cache.rglob("*.json"))


@pytest.fixture
def program(tmp_path, monkeypatch):
    return _Program(tmp_path / "program", monkeypatch)


FRACTIONS = np.array([0.2, 0.8])
SIGNAL = ExpectedSignal(experiment="fixture", particle=DarkMatterParticle(mass_gev=10), interaction_id="fixture",
                        total_events=10.0, observable=[1.0, 2.0, 3.0, 4.0], density=[0.25, 0.25, 0.25, 0.25])
EVENTS = np.array([1.5, 3.5])


def test_a_limit_is_returned_reused_and_reaches_both_procedures(program):
    program.answers("3.0 0")
    assert oi.optimum_interval_limit(FRACTIONS) == oi.optimum_interval_limit(FRACTIONS) == (3.0, 0)
    assert program.calls == 1 and len(program.stored()) == 1                  # stored once, then reused
    assert base.interval_limit(EVENTS, SIGNAL) == pytest.approx(0.3)
    assert private_search.interval_upper(EVENTS, SIGNAL, 0.9, "optimum_interval") == pytest.approx(0.3)


BAD = ["-1.0 0", "nan 0", "0.0 0", "inf 0", "-inf 0", "3.0 2", "3.0 64", "3.0 128", "3.0 66", "3.0 259", "", "garbage",
       "3.0", "3.0 x", "exit 3", "exit 1: 3.0 0"]


@pytest.mark.parametrize("answer", BAD)
@pytest.mark.parametrize("cache", [True, False])
def test_what_is_not_a_limit_is_refused_cold_warm_and_uncached_and_never_stored(program, answer, cache):
    """The auditor's negative and NaN answers, Yellin's refused flags (2, 64, 128, alone or with others), output that
    is not a limit and a flag, and a failed exit (with a limit printed or not): each raises, the first call and the next alike, with the cache or
    without it, and nothing is stored; and both limit procedures raise it, never returning a number."""
    program.answers(answer)
    for _ in range(2):
        with pytest.raises(oi.OptimumIntervalFailed):
            oi.optimum_interval_limit(FRACTIONS, cache=cache)
    assert program.calls == 2 and program.stored() == []
    with pytest.raises(oi.OptimumIntervalFailed):
        base.interval_limit(EVENTS, SIGNAL)
    with pytest.raises(oi.OptimumIntervalFailed):
        private_search.interval_upper(EVENTS, SIGNAL, 0.9, "optimum_interval")
    assert issubclass(oi.OptimumIntervalFailed, RuntimeError)     # what each search's caller takes as unavailable


@pytest.mark.parametrize("flag", [1, 4, 8, 16, 32, 256, 261])
def test_the_flags_that_still_give_a_limit_return_it_with_the_flag_uncached(program, flag):
    """1 ("should be ok"), a table extrapolated (4, 8), the interval's own status (16, 32) and more than one solution
    (256: the value is still the absolute upper limit) give their limit and their flag; only flag 0 is stored, as
    before."""
    program.answers(f"3.0 {flag}")
    assert oi.optimum_interval_limit(FRACTIONS) == oi.optimum_interval_limit(FRACTIONS) == (3.0, flag)
    assert program.calls == 2 and program.stored() == []


def _gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def test_a_call_past_its_deadline_is_stopped_whole_and_refused(program, monkeypatch):
    """The auditor's sleeping program (and its sleeping descendant), reached: the product, not a watchdog, stops both
    at the deadline, and the call is refused, naming it."""
    program.answers("sleep")
    monkeypatch.setenv("ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S", "1.5")
    started = time.monotonic()
    with pytest.raises(oi.OptimumIntervalFailed, match="deadline of 1.5 s"):
        oi.optimum_interval_limit(FRACTIONS)
    assert 1.4 < time.monotonic() - started < 15
    pids = [int(x) for x in (program.folder / "pids").read_text().split()]
    deadline = time.monotonic() + 10
    while not all(_gone(pid) for pid in pids) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert all(_gone(pid) for pid in pids) and program.stored() == []


CALLER = '''
import sys
from pathlib import Path
from adroit.statistics.optimum_interval import _calculate
_calculate(Path(sys.argv[1]), "0.9 0\\n")
'''


def test_a_caller_ended_while_its_program_runs_ends_the_program_too(program, tmp_path):
    """The program runs in its caller's process group: a cancel that ends a run's calculation (its group, ``ui.engine``)
    ends it and what it started, before its deadline. (The repair's first form, a session of the program's own, had
    left both running when the auditor's watchdog ended their caller.)"""
    import signal
    import subprocess
    program.answers("sleep")
    (tmp_path / "caller.py").write_text(CALLER)
    caller = subprocess.Popen([sys.executable, str(tmp_path / "caller.py"), str(program.binary)],
                              start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 30
    while not (program.folder / "pids").exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    pids = [int(x) for x in (program.folder / "pids").read_text().split()]
    os.killpg(caller.pid, signal.SIGKILL)
    caller.wait(timeout=10)
    deadline = time.monotonic() + 10
    while not all(_gone(pid) for pid in pids) and time.monotonic() < deadline:
        time.sleep(0.05)
    survivors = [pid for pid in pids if not _gone(pid)]
    for pid in survivors:                        # the test's own stand-ins, whatever happened
        os.kill(pid, signal.SIGKILL)
    assert not survivors


@pytest.mark.parametrize("setting, seconds", [(None, 60.0), ("2.5", 2.5), (" 10 ", 10.0)])
def test_the_deadline_is_sixty_seconds_unless_set(monkeypatch, setting, seconds):
    if setting is None:
        monkeypatch.delenv("ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S", raising=False)
    else:
        monkeypatch.setenv("ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S", setting)
    assert oi.deadline() == seconds


@pytest.mark.parametrize("setting", ["0", "-1", "abc", "nan", "inf"])
def test_a_deadline_that_is_not_a_positive_number_refuses_before_the_program_runs(program, monkeypatch, setting):
    program.answers("3.0 0")
    monkeypatch.setenv("ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S", setting)
    with pytest.raises(oi.OptimumIntervalFailed, match="is not a positive number of seconds"):
        oi.optimum_interval_limit(FRACTIONS)
    assert program.calls == 0
