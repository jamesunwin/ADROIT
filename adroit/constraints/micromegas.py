"""micrOMEGAs as an optional, independent relic-density cross-check (a program in the tools folder).

micrOMEGAs 7.1 (Bélanger et al. arXiv:2606.06645; 6.0: arXiv:2312.14894) is built in the tools folder
(adroit setup) and never copied into this repository; mo_omega.c beside this module is the
small C program compiled into each model directory.

The physics lives entirely in the compiled micrOMEGAs program ``mo_omega`` (built
from ``mo_omega.c`` inside a micrOMEGAs model directory). This module only

1. translates physics-named parameters (``M_H0``, ``lambda_345`` ...) into the
   model's native CalcHEP variable names (``MHX``, ``laL`` ...), applying the
   normalisation factors documented in :data:`MODELS`;
2. runs the executable with a wall-clock timeout; and
3. parses its ``MO_*`` key=value lines into a typed, JSON-serialisable result.

Freeze-out quantities returned per off-shell mode ``w:z`` (``VWdecay``/``VZdecay``):

* ``0:0`` -- 2->2 only. Annihilation into W W* / Z Z* is absent, and the
  automatically computed widths (e.g. the Higgs width) omit 1->3 decays.
* ``1:1`` -- adds 2->3 final states with one virtual W/Z for DM-DM annihilation
  (micrOMEGAs' default; needed for M_DM just below m_W, m_Z).
* ``2:2`` -- as ``1:1`` but also for co-annihilation channels.

CLI::

    python micromegas_driver.py '{"model": "IDM", "params": {"M_H0": 72.77, ...}}'
    echo '{...}' | python micromegas_driver.py -
    python micromegas_driver.py --build IDM      # (re)compile mo_omega in IDM/

Physics caveats for cross-checks:

* In mode ``0:0`` the automatic Higgs width also loses h -> W W*, Z Z*
  (3.07 vs 3.99 MeV), which inflates resonant h-pole annihilation. To isolate the
  effect of the VV* final states, impose one width in all modes, e.g.
  ``settings.fixed_widths = {"h": 4.1e-3}``.
* The shipped IDM uses EE=0.31340 (1/alpha=127.94), SW=0.48075, MW=80.385, so
  MZ = MW/cos(theta_W) = 91.674 GeV and v = 2 MW SW/EE = 246.6 GeV. Pass ``EE``,
  ``SW``, ``MW`` (native names) to match another program's electroweak scheme;
  e.g. a G_F scheme (EE=0.30833, SW=0.472243, MW=80.379) moves BP1 by -1.4%.

Concurrency note: the first call for a model or a new kinematic region compiles
matrix-element libraries into ``<model>/work/so_generated`` (about 10 s for IDM).
Concurrent runs were tested to be safe, but a serial warm-up point is cheap.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from adroit.core.config import child_environment

INSTALL_NAME = "micromegas_7.1.10"
EXECUTABLE_NAME = "mo_omega"
C_SOURCE_NAME = "mo_omega.c"
_MODE_RE = re.compile(r"^\d+(:\d+)?$")
_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


class MicromegasModel(BaseModel):
    """Description of one micrOMEGAs model directory and its parameter conventions.

    Attributes:
        directory: Model directory name inside the micrOMEGAs installation.
        aliases: Physics alias -> (native CalcHEP variable, multiplicative factor),
            i.e. ``native = factor * alias_value``.
        derived: Constrained (func1.mdl) parameters echoed back for convention checks.
        conventions: Human-readable statement of the Lagrangian normalisation.
    """

    model_config = ConfigDict(frozen=True)

    directory: str
    aliases: dict[str, tuple[str, float]]
    derived: tuple[str, ...] = ()
    conventions: str = ""


MODELS: dict[str, MicromegasModel] = {
    "IDM": MicromegasModel(
        directory="IDM",
        aliases={
            "M_H0": ("MHX", 1.0), "M_A0": ("MH3", 1.0), "M_Hpm": ("MHC", 1.0),
            "lambda_2": ("la2", 1.0), "lambda_L": ("laL", 1.0),
            "lambda_345": ("laL", 0.5), "m_h": ("Mh", 1.0),
        },
        derived=("mu2", "la3", "la4", "la5"),
        conventions=(
            "V = mu2|H2|^2 + la2|H2|^4 + la3|H1|^2|H2|^2 + la4|H1^+H2|^2 "
            "+ la5/2[(H1^+H2)^2 + h.c.]; M_H0^2 = mu2 + laL v^2, "
            "laL = (la3+la4+la5)/2 = lambda_345/2; g(h H0 H0) = -lambda_345 v. "
            "Kalinowski et al. use lambda_2/2 |H2|^4, i.e. la2 = lambda_2(K)/2. "
            "DM is ~X (= H0, PDG 35); ~H3 = A0; ~H+ = H+."
        ),
    ),
    "SingletDM": MicromegasModel(
        directory="SingletDM",
        aliases={
            "M_S": ("Mdm1", 1.0), "lambda_hs": ("laSH", 0.5),
            "lambda_s": ("laS", 1.0), "m_h": ("Mh", 1.0),
        },
        derived=("muSq1",),
        conventions=(
            "Real scalar S=~x1: V = 1/2 muS^2 S^2 + laSH S^2 |H|^2 + 1/4 laS S^4, "
            "Mdm1 = physical mass (muS^2 = Mdm1^2 - laSH v^2); g(h S S) = -2 laSH v. "
            "Alias lambda_hs uses the 1/2 lambda_hs S^2|H|^2 convention (laSH = lambda_hs/2)."
        ),
    ),
    "ZpPortal": MicromegasModel(
        directory="ZpPortal",
        aliases={
            "M_DM": ("Mdm", 1.0), "M_Zp": ("MZp", 1.0), "g_SM": ("gZp", 1.0),
            "g_DM": ("gZpDm", 1.0), "m_h": ("Mh", 1.0),
        },
        conventions=(
            "Dirac DM ~dm with vector coupling gZpDm Zp_mu dmbar gamma^mu dm; SM fermion f "
            "couples vectorially with gZp*Yp_f (defaults: quarks Yp=1, charged leptons and "
            "neutrinos Yp=-3, i.e. 3(B-L)); no Z-Zp mixing."
        ),
    ),
}


class OmegaSettings(BaseModel):
    """Numerical settings forwarded to ``mo_omega``.

    Attributes:
        vv_modes: Off-shell modes ``"w:z"`` (or ``"k"`` for w=z=k) to compute.
        primary_mode: Mode reported as top-level ``omega_h2``; default = last of vv_modes.
        fast: darkOmega accuracy flag: 0 accurate (default; ~10% slower than 1),
            1 micrOMEGAs "fast" (up to ~4% off near the Higgs pole), -1 "no 2->3
            interpolation" (identical to 0 in our IDM tests).
        beps: Co-annihilation Boltzmann cut-off Beps.
        fixed_widths: Particle name -> imposed total width [GeV] (e.g. ``{"h": 4.1e-3}``).
        channel_cut: If set, return channels contributing more than this fraction.
        timeout_s: Wall-clock limit for the subprocess.
        n_threads: If set, exported as ``nParProc`` to cap micrOMEGAs threads.
    """

    vv_modes: list[str] = Field(default_factory=lambda: ["0:0", "1:1"])
    primary_mode: str | None = None
    fast: Literal[-1, 0, 1] = 0
    beps: float = 1e-5
    fixed_widths: dict[str, float] = Field(default_factory=dict)
    channel_cut: float | None = None
    timeout_s: float = 600.0
    n_threads: int | None = None

    @field_validator("vv_modes", mode="before")
    @classmethod
    def _normalise_modes(cls, value: list[str | int]) -> list[str]:
        out = []
        for item in value:
            text = str(item)
            if not _MODE_RE.match(text):
                raise ValueError(f"bad VV mode {item!r}; use 'k' or 'w:z'")
            out.append(text if ":" in text else f"{text}:{text}")
        return out


class OmegaRequest(BaseModel):
    """Input: model name, parameters (aliases or native names) and settings."""

    model: str
    params: dict[str, float]
    settings: OmegaSettings = Field(default_factory=OmegaSettings)
    install_dir: str | None = None


class Channel(BaseModel):
    """One annihilation channel's fractional contribution to 1/Omega."""

    process: str
    fraction: float


class ModeResult(BaseModel):
    """Relic density for one VWdecay/VZdecay setting."""

    mode: str
    vw_decay: int
    vz_decay: int
    omega_h2: float
    x_f: float
    err: int
    higgs_width_gev: float
    time_s: float
    channels: list[Channel] = Field(default_factory=list)


class OmegaResult(BaseModel):
    """Output: top-level summary plus per-mode details and provenance."""

    status: Literal["ok", "error", "timeout"]
    omega_h2: float | None = None
    x_f: float | None = None
    model: str
    native_params: dict[str, float]
    settings: OmegaSettings
    version: str
    executable: str
    dm_name: str | None = None
    dm_mass_gev: float | None = None
    derived: dict[str, float] = Field(default_factory=dict)
    modes: list[ModeResult] = Field(default_factory=list)
    wall_time_s: float = 0.0
    error: str | None = None


def resolve_params(model: str, params: dict[str, float]) -> dict[str, float]:
    """Map physics aliases to native CalcHEP variable names.

    Native names (e.g. ``MHX``) pass through unchanged; micrOMEGAs itself rejects
    names that are not free parameters of the model.

    Args:
        model: Key of :data:`MODELS`.
        params: Alias or native name -> value.

    Returns:
        Native name -> value.

    Raises:
        KeyError: Unknown model.
        ValueError: Malformed name, non-finite value, or two keys mapping to one variable.
    """
    spec = MODELS[model]
    native: dict[str, float] = {}
    for key, value in params.items():
        if not _NAME_RE.match(key):
            raise ValueError(f"illegal parameter name {key!r}")
        if not math.isfinite(float(value)):
            raise ValueError(f"non-finite value for {key}")
        name, factor = spec.aliases.get(key, (key, 1.0))
        if name in native:
            raise ValueError(f"parameter {name} given twice (via {key})")
        native[name] = factor * float(value)
    return native


def build_command(exe: Path, native: dict[str, float], settings: OmegaSettings,
                  derived: tuple[str, ...] = ()) -> list[str]:
    """Assemble the ``mo_omega`` argument vector.

    Args:
        exe: Path of the compiled executable.
        native: Native parameter assignments.
        settings: Numerical settings.
        derived: Constrained parameters to echo (``-v``).

    Returns:
        Argument list for :func:`subprocess.run`.
    """
    cmd = [str(exe), "-m", ",".join(settings.vv_modes), "-f", str(settings.fast),
           "-b", repr(settings.beps)]
    for particle, width in settings.fixed_widths.items():
        cmd += ["-w", f"{particle}={width!r}"]
    if settings.channel_cut is not None:
        cmd += ["-c", repr(settings.channel_cut)]
    for name in derived:
        cmd += ["-v", name]
    cmd += [f"{name}={value!r}" for name, value in native.items()]
    return cmd


def _kv(line: str) -> dict[str, str]:
    """Split ``MO_TAG k1=v1 k2=v2`` into a dict (values contain no spaces)."""
    return dict(tok.split("=", 1) for tok in line.split()[1:] if "=" in tok)


def parse_output(stdout: str) -> dict:
    """Parse the ``MO_*`` lines printed by ``mo_omega``.

    Args:
        stdout: Full standard output of the executable.

    Returns:
        Dict with keys ``info``, ``vars``, ``modes`` (list of ModeResult),
        ``errors`` (list of str) and ``done`` (bool).
    """
    out: dict = {"info": {}, "vars": {}, "modes": [], "errors": [], "done": False}
    by_mode: dict[str, ModeResult] = {}
    for line in stdout.splitlines():
        tag = line.split(" ", 1)[0]
        if tag == "MO_INFO":
            out["info"] = _kv(line)
        elif tag == "MO_VAR":
            kv = _kv(line)
            out["vars"][kv["name"]] = float(kv["value"])
        elif tag == "MO_OMEGA":
            kv = _kv(line)
            res = ModeResult(
                mode=kv["mode"], vw_decay=int(kv["VWdecay"]), vz_decay=int(kv["VZdecay"]),
                omega_h2=float(kv["Omega"]), x_f=float(kv["Xf"]), err=int(kv["err"]),
                higgs_width_gev=float(kv["wh"]), time_s=float(kv["time"]))
            by_mode[res.mode] = res
            out["modes"].append(res)
        elif tag == "MO_CHANNEL":
            kv = _kv(line)
            by_mode[kv["mode"]].channels.append(
                Channel(process=kv["proc"], fraction=float(kv["frac"])))
        elif tag == "MO_ERROR":
            out["errors"].append(line[len("MO_ERROR "):].strip())
        elif tag == "MO_DONE":
            out["done"] = True
    return out


def install_version(install_dir: Path) -> str:
    """Return e.g. ``'micrOMEGAs 7.1.10'`` from an install directory name."""
    match = re.search(r"micromegas_([\d.]+\w*)", install_dir.name)
    return f"micrOMEGAs {match.group(1)}" if match else f"micrOMEGAs ({install_dir.name})"


def resolve_install(request_dir: str | None) -> Path:
    """Pick the install directory: request > $MICROMEGAS_DIR > default."""
    from adroit.core.config import get_settings
    default = get_settings().tools_dir / INSTALL_NAME
    return Path(request_dir or os.environ.get("MICROMEGAS_DIR") or default).expanduser()


def _run_subprocess(cmd: list[str], timeout_s: float, env: dict[str, str]) -> tuple[str, int]:
    """Run ``cmd`` in its own process group; kill the whole group on timeout.

    Returns:
        (stdout, returncode). Raises subprocess.TimeoutExpired on timeout.
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, errors="replace", env=env, start_new_session=True)
    try:
        stdout, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise
    return stdout, proc.returncode


def _primary(settings: OmegaSettings) -> str:
    """The mode whose result is the summary: ``primary_mode``, else the last of ``vv_modes``."""
    wanted = settings.primary_mode or settings.vv_modes[-1]
    return wanted if ":" in wanted else f"{wanted}:{wanted}"


def _summarise(parsed: dict, settings: OmegaSettings) -> tuple[float | None, float | None]:
    """(omega_h2, x_f) of the primary mode; (None, None) where it has no result, never another mode's."""
    chosen = next((m for m in parsed["modes"] if m.mode == _primary(settings)), None)
    return (chosen.omega_h2, chosen.x_f) if chosen else (None, None)


def _unusable(parsed: dict, settings: OmegaSettings) -> str | None:
    """Why a clean run's output is not the requested result (None where it is): every requested mode answered once,
    and the primary one with no error from darkOmega (its ``err``) and a finite positive Ωh² and x_f. A clean exit with
    MO_DONE is not enough: mo_omega.c prints darkOmega's error in its mode's row and goes on (an operating-conditions
    audit's IE-02, 2026-11-10)."""
    answered = [m.mode for m in parsed["modes"]]
    missing = [m for m in dict.fromkeys([*settings.vv_modes, _primary(settings)]) if m not in answered]
    if missing:
        return f"no result for the requested mode{'s' if len(missing) > 1 else ''} {', '.join(missing)}"
    twice = sorted({m for m in answered if answered.count(m) > 1})
    if twice:
        return f"more than one result for the mode{'s' if len(twice) > 1 else ''} {', '.join(twice)}"
    row = next(m for m in parsed["modes"] if m.mode == _primary(settings))
    if row.err:
        return f"darkOmega reported error {row.err} for the mode {row.mode}"
    for name, value in (("Ωh²", row.omega_h2), ("x_f", row.x_f)):
        if not (math.isfinite(value) and value > 0):
            return f"its {name} for the mode {row.mode} is {value!r}, not a finite positive number"
    return None


def run_micromegas(request: OmegaRequest) -> OmegaResult:
    """Compute the freeze-out relic density with micrOMEGAs.

    Args:
        request: Model, parameters and settings.

    Returns:
        OmegaResult; ``status`` is ``"error"``/``"timeout"`` instead of raising for
        failures of the external program, its output unreadable or not the requested
        result included (``_unusable``), where its ``omega_h2`` and ``x_f`` are None.
    """
    spec = MODELS[request.model]
    install = resolve_install(request.install_dir)
    exe = install / spec.directory / EXECUTABLE_NAME
    native = resolve_params(request.model, request.params)
    base = dict(model=request.model, native_params=native, settings=request.settings,
                version=install_version(install), executable=str(exe))
    if not exe.is_file():
        return OmegaResult(status="error", error=f"executable not found: {exe}", **base)
    env = child_environment()                   # no credential (AL3-27)
    if request.settings.n_threads:
        env["nParProc"] = str(request.settings.n_threads)
    cmd = build_command(exe, native, request.settings, spec.derived)
    t0 = time.perf_counter()
    try:
        stdout, code = _run_subprocess(cmd, request.settings.timeout_s, env)
    except subprocess.TimeoutExpired:
        return OmegaResult(status="timeout", wall_time_s=time.perf_counter() - t0,
                           error=f"timeout after {request.settings.timeout_s} s", **base)
    try:
        parsed = parse_output(stdout)
        mass = float(parsed["info"]["Mcdm"]) if "Mcdm" in parsed["info"] else None
    except (KeyError, ValueError) as error:
        return OmegaResult(status="error", wall_time_s=time.perf_counter() - t0,
                           error=f"its output cannot be read ({type(error).__name__}: {error}): {stdout[-400:]}",
                           **base)
    ok = code == 0 and parsed["done"] and not parsed["errors"]
    error = None if ok else "; ".join(parsed["errors"]) or f"exit {code}: {stdout[-400:]}"
    if ok and (error := _unusable(parsed, request.settings)):
        ok = False
    omega, x_f = _summarise(parsed, request.settings) if ok else (None, None)
    return OmegaResult(
        status="ok" if ok else "error", omega_h2=omega, x_f=x_f, error=error,
        dm_name=parsed["info"].get("cdm"), derived=parsed["vars"], modes=parsed["modes"],
        dm_mass_gev=mass, wall_time_s=time.perf_counter() - t0, **base)


def build_executable(model: str, install_dir: str | None = None,
                     source: Path | None = None) -> Path:
    """Copy ``mo_omega.c`` into the model directory and compile it with ``make``.

    Args:
        model: Key of :data:`MODELS`.
        install_dir: micrOMEGAs installation (default: see :func:`resolve_install`).
        source: C source (default: ``mo_omega.c`` next to this file).

    Returns:
        Path of the executable.

    Raises:
        subprocess.CalledProcessError: Compilation failed.
    """
    model_dir = resolve_install(install_dir) / MODELS[model].directory
    src = source or Path(__file__).with_name(C_SOURCE_NAME)
    shutil.copy(src, model_dir / C_SOURCE_NAME)
    subprocess.run(["make", f"main={C_SOURCE_NAME}"], cwd=model_dir, check=True,
                   capture_output=True, text=True, env=child_environment())
    return model_dir / EXECUTABLE_NAME


def main(argv: list[str]) -> int:
    """CLI entry point: JSON request (argument or ``-`` for stdin) -> JSON result."""
    if len(argv) == 3 and argv[1] == "--build":
        print(build_executable(argv[2]))
        return 0
    if len(argv) != 2:
        print(__doc__)
        return 2
    raw = sys.stdin.read() if argv[1] == "-" else argv[1]
    result = run_micromegas(OmegaRequest.model_validate_json(raw))
    print(result.model_dump_json(indent=2))
    return 0 if result.status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
