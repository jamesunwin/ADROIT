"""The optimum interval method, through Yellin's own code (an external tool).

The code and its Monte Carlo tables are fetched from the manifest item
"Optimum interval code (Yellin)" and compiled once with gfortran, with a
small driver that reads the confidence level and the events' cumulative
signal fractions from standard input and prints the upper limit on μ and
Yellin's status flag. Nothing here is committed: the code is used with
citation (S. Yellin, Phys. Rev. D 66 (2002) 032005; arXiv:0709.2701).

Every call's result is checked before it is returned, calculated or reused: μ
finite and positive, and the flag none of ``REFUSED_FLAGS``; and every call has
a deadline (``deadline``), past which the program is stopped. A result that is
not a limit, or a call that fails or passes its deadline, raises
``OptimumIntervalFailed``, which its callers take as the limit unavailable (an
operating-conditions audit's IE-03 and IE-04, 2026-11-10: a negative or NaN μ
had been returned whenever the cache, which admits only good results, did not
store it, and a call had no deadline).

The program reads its input from, and writes its output to, files of the call's
own (``_calculate``), never pipes: a call waits for the program alone. Where it
is stopped at its deadline, or gives no limit, what it started that still holds
those files is found by them (``_holders``) and stopped too, wherever it has
gone. Before, a process the program had started in a session of its own, left
when the program exited, had held the call's pipe open past the deadline, and
the call had waited for it (the auditor's DV–IE recheck, DW-04, 2026-11-11). A call
that gives a limit does not look (``lsof`` costs about 0.4 s, and a search makes
hundreds of calls): a process such a program left runs on, unwaited for.
"""

from __future__ import annotations

import contextlib
import math
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from adroit.core.config import env
from adroit.external import fetch
from adroit.core.calculation_cache import reuse
from adroit.core.state import StrictModel
from adroit.statistics import cache_identity

ITEM = "Optimum interval code (Yellin)"
SOURCES = ("UpperLimNew2.f", "y_vs_CLf2.f", "CMaxinfNew2.f", "ConfLev2.f", "ConfLevNew2.f",
           "Cinf2.f", "CERN_Stuff2.f")
EXECUTABLE = "adroit_oi"

DRIVER = """\
      Program agenticDmOI
C     Reads CL and N, then the N sorted cumulative signal fractions;
C     prints the optimum-interval upper limit on mu and the status flag.
      Implicit None
      Integer*8 If, I, N, Iflag, NMax
      Parameter (NMax=150000)
      Real*8 CL, FC(0:NMax+1), FB(0:NMax+1), muB, UpperLim, mu
      muB = 0.D0
      If = 1
      read(*,*) CL, N
      read(*,*) (FC(I), I=1,N)
      FC(0) = 0.D0
      FC(N+1) = 1.D0
      Do I=0,N+1
         FB(I) = FC(I)
      EndDo
      mu = UpperLim(CL, If, N, FC, muB, FB, Iflag)
      write(*,'(ES24.16,1X,I10)') mu, Iflag
      end
"""


class OptimumIntervalUnavailable(RuntimeError):
    """The optimum interval code is not fetched, or cannot be compiled here."""


class OptimumIntervalFailed(OptimumIntervalUnavailable):
    """One call gave no limit: the program failed, ran past its deadline, or returned what is not a limit (module
    docstring)."""


# Yellin's status flag bits that say the value returned is not a limit (UpperLimNew2.f's header): 2, more than 10
# iterations needed but not obtained ("may be serious"); 64, CMax = CMaxbar not solved; 128, not solved because the
# limit wants to be negative. The others are accepted, the flag returned with the limit (the owner, 2026-11-11): 1,
# "should be ok"; 4 and 8, a table extrapolated; 16 and 32, the optimum interval's own status; 256, more than one
# solution, the value still the absolute upper limit.
REFUSED_FLAGS = 2 | 64 | 128
# one call's deadline in seconds where ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S does not set one (the owner, 2026-11-11):
# a call takes under 0.1 s for the searches' few hundred events, and 0.9 s for 50,000
DEADLINE_S = 60.0


def code_folder() -> Path | None:
    """The folder holding the Fortran sources and tables, if fetched."""
    root = fetch.locate(ITEM)
    return None if root is None else root / "CDMSlite_Run2_data" / "OI_code"


def executable() -> Path:
    """The compiled driver, building it on first use.

    Raises:
        OptimumIntervalUnavailable: if the code is not fetched or gfortran is missing.
    """
    folder = code_folder()
    if folder is None:
        raise OptimumIntervalUnavailable(f"fetch the manifest item {ITEM!r} first")
    binary = folder / EXECUTABLE
    if binary.is_file():
        return binary
    compiler = shutil.which("gfortran")
    if compiler is None:
        raise OptimumIntervalUnavailable("gfortran is needed to compile the optimum interval code")
    (folder / "adroit_oi.f").write_text(DRIVER)
    subprocess.run([compiler, "-O2", "-frecord-marker=4", "-std=legacy", "-fdefault-integer-8",
                    "-o", EXECUTABLE,
                    "adroit_oi.f", *SOURCES], cwd=folder, check=True, capture_output=True)
    return binary


def available() -> bool:
    """Whether the optimum interval can be computed here."""
    try:
        executable()
    except (OptimumIntervalUnavailable, subprocess.CalledProcessError):
        return False
    return True


class _Input(StrictModel):
    text: str


class _Limit(StrictModel):
    mu: float
    flag: int


def optimum_interval_limit(fractions: np.ndarray, cl: float = 0.9, *, cache: bool = True) -> tuple[float, int]:
    """The optimum-interval upper limit on μ, and Yellin's status flag (0 is normal).

    Args:
        fractions: Each event's cumulative signal fraction F_i in [0, 1].
        cl: The confidence level.

    Raises:
        OptimumIntervalFailed: the call gave no limit (module docstring).
    """
    values = np.sort(np.clip(np.asarray(fractions, dtype=float), 0.0, 1.0))
    text = f"{cl:.10f} {len(values)}\n" + "\n".join(f"{v:.15e}" for v in values) + "\n"
    binary = executable()
    value = reuse("yellin-optimum-interval", _Input(text=text), lambda: cache_identity.native(binary),
                  lambda: _calculate(binary, text), _Limit,
                  lambda r: math.isfinite(r.mu) and r.mu > 0 and r.flag == 0, enabled=cache)
    return usable(value.mu, value.flag)


def usable(mu: float, flag: int) -> tuple[float, int]:
    """(μ, flag) where they are a limit: μ finite and positive, the flag none of ``REFUSED_FLAGS``.

    Raises:
        OptimumIntervalFailed: naming why they are not.
    """
    if not (math.isfinite(mu) and mu > 0):
        raise OptimumIntervalFailed(f"the optimum interval code returned μ = {mu!r} (flag {flag}), not a finite "
                                    "positive limit")
    if flag & REFUSED_FLAGS:
        raise OptimumIntervalFailed(f"the optimum interval code's status flag {flag} says its limit was not found "
                                    "(bit 2: not converged; 64 or 128: not solved)")
    return mu, flag


def deadline() -> float:
    """One call's deadline in seconds: ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S where set, else ``DEADLINE_S``.

    Raises:
        OptimumIntervalFailed: the setting is not a positive number of seconds.
    """
    text = env("OPTIMUM_INTERVAL_TIMEOUT_S", "").strip()
    if not text:
        return DEADLINE_S
    try:
        seconds = float(text)
    except ValueError:
        seconds = math.nan
    if not (math.isfinite(seconds) and seconds > 0):
        raise OptimumIntervalFailed(f"ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S = {text!r} is not a positive number of "
                                    "seconds")
    return seconds


def _calculate(binary: Path, text: str) -> _Limit:
    """The driver's last two words for ``text``: μ and the flag. It runs in its caller's process group, so that what
    ends the caller's calculation ends it too (a workbench run's Cancel, ``ui.engine``), with its input and output in
    files of the call's own (module docstring). At its deadline it is stopped with every process it started
    (``_stop``); where it gives no limit, what it started that still runs is stopped too (``_holders``). A result read
    whole that is not a limit (``usable``: μ not finite and positive, a refused flag) gives no limit: it is refused here,
    while the call's files are there to find what holds them (the auditor's DW recheck, DX-03, 2026-11-12: it had been
    refused after the call returned, its files gone, and a program's helper holding them had kept running)."""
    seconds = deadline()
    with tempfile.TemporaryDirectory(prefix="adroit-oi-") as folder:
        files = [Path(folder) / name for name in ("input", "output", "errors")]
        files[0].write_text(text)
        with files[0].open("rb") as stdin, files[1].open("wb") as stdout, files[2].open("wb") as stderr:
            process = subprocess.Popen([str(binary)], stdin=stdin, stdout=stdout, stderr=stderr, cwd=binary.parent)
        try:
            process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            _stop(process, files)
            raise OptimumIntervalFailed(f"the optimum interval code passed its deadline of {seconds:g} s "
                                        "(ADROIT_OPTIMUM_INTERVAL_TIMEOUT_S) and was stopped") from None
        out, err = (path.read_text(errors="replace") for path in files[1:])
        try:
            limit = _read(process.returncode, out, err)
            usable(limit.mu, limit.flag)             # a result that is not a limit is a call that gave none (DX-03)
            return limit
        except OptimumIntervalFailed:
            _kill(_holders(files))                   # what a failed program started and left: stopped, not waited for
            raise


def _read(code: int, out: str, err: str) -> _Limit:
    """μ and the flag, the last two words of the program's output; ``OptimumIntervalFailed`` where it failed or
    printed no limit and flag."""
    if code != 0:
        raise OptimumIntervalFailed(f"the optimum interval code exited with {code}: {(err or out).strip()[-200:]!r}")
    try:
        mu, flag = out.split()[-2:]
        return _Limit(mu=float(mu), flag=int(flag))
    except ValueError:
        raise OptimumIntervalFailed(f"the optimum interval code's output is not a limit and a flag: "
                                    f"{out.strip()[-200:]!r}") from None


CLEANUP_S = 10.0                    # the bound on each step of stopping a call (``ps``, ``lsof``, the reaping)


def _stop(process: subprocess.Popen, files: list[Path]) -> None:
    """Stop the program and its descendants: those found by their parents (as ``ps`` lists them at once, before any is
    stopped), and those holding the call's files (``_holders``: one that left the program's tree, in a session of its
    own, after the program exited); then reap it, within ``CLEANUP_S``. Only it where neither can be read: Yellin's
    driver starts no process."""
    try:
        listed = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True,
                                timeout=CLEANUP_S).stdout
    except (OSError, subprocess.SubprocessError):
        listed = ""
    children: dict[int, list[int]] = {}
    for line in listed.splitlines():
        words = line.split()
        if len(words) == 2 and all(word.isdigit() for word in words):
            children.setdefault(int(words[1]), []).append(int(words[0]))
    tree, waiting = [], [process.pid]
    while waiting:
        tree.append(waiting.pop())
        waiting.extend(children.get(tree[-1], []))
    _kill(tree)
    _kill(_holders(files))
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=CLEANUP_S)


def _holders(files: list[Path]) -> list[int]:
    """The processes holding any of the call's files open (``lsof``): the program's own, or what it started and left,
    since nothing else is given them; this process excepted. [] where ``lsof`` cannot be read."""
    try:
        listed = subprocess.run(["lsof", "-t", "--", *map(str, files)], capture_output=True, text=True,
                                timeout=CLEANUP_S, stdin=subprocess.DEVNULL).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [int(word) for word in listed.split() if word.isdigit() and int(word) != os.getpid()]


def _kill(pids: list[int]) -> None:
    for pid in pids:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGKILL)
