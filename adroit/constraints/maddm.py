"""MadDM, called as an external tool for DM8's numerical cross-check.

MadGraph5_aMC@NLO (arXiv:1405.0301) and its plugin MadDM (relic density
arXiv:1308.4955; direct detection arXiv:1505.04190; v3 arXiv:1804.00044 and
2107.04598) are used as dependencies: installed by the user in the tools folder
(``<tools>/mg5amcnlo-3.8.0`` with MadDM's 3.3 release candidate in its PLUGIN
folder), called as programs, never copied into this repository.

What is taken from MadDM, and what is not:
- **Taken:** the relic density and ⟨σv⟩ at freeze-out, and the quark-level
  coefficients α_q MadDM matches from the full model at zero momentum (printed in
  ``maddm.out``: per quark, the scalar and vector spin-independent and the axial
  and tensor spin-dependent coefficients).
- **Not taken as they stand:** the nucleon cross-sections of the 3.3 release
  candidate. Its RAPIDD code applies σ = 4μ²|f|²/π (12μ²|f|²/π for spin-dependent)
  without the factor ½ on f that MadDM 3.2.13 applied to Dirac and complex fields,
  so they are four times too large for those (DM8 record, section 14).
- **Widths** of new states are computed by MadGraph itself (``compute_widths``) in a
  separate session, because MadDM's mode cannot run that command, and passed to
  MadDM as numbers.
- **⟨σv⟩ today per final state** (``indirect``, G6's cross-check, the owner's decision D14):
  MadDM's tree-level 2 → 2 mode (``generate indirect_detection 2to2lo``, ``sigmav_method
  inclusive``), which needs no spectra and so installs nothing. Its madevent route does not
  compile with MadGraph 3.8 (2026-10-14).
"""

from __future__ import annotations

import re
import json
import math
import tempfile
from hashlib import sha256
import subprocess
from pathlib import Path

from pydantic import Field

from adroit.core.config import child_environment
from adroit.core.config import get_settings
from adroit.core.model_spec import ModelSpec
from adroit.core.state import StrictModel
from adroit.library.interactions import derivation as dv
from adroit.library.interactions import ufo
from adroit.library.interactions.ufo import MG5, UfoExtension

QUARK_ORDER = ("d", "u", "s", "c", "b", "t")
TIMEOUT_S = 3600


class MadDMResult(StrictModel):
    """What one MadDM run gave."""

    omega_h2: float | None = None
    x_f: float | None = None
    sigmav_xf_cm3_s: float | None = None
    alpha: dict[str, list[float]] = Field(default_factory=dict)       # quark → [SIe, SIo, SDe, SDo]
    sigma_raw_cm2: dict[str, float] = Field(default_factory=dict)     # MadDM's own (see the module note)
    widths_gev: dict[str, float] = Field(default_factory=dict)


def mg5_dir() -> Path:
    """The user's MadGraph installation."""
    return get_settings().tools_dir / MG5


def workdir(name: str) -> Path:
    """A work folder for one model, in the tools folder: MadGraph cannot use a path with spaces."""
    return get_settings().tools_dir / "maddm-work" / re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def python() -> Path:
    """The Python MadGraph runs under (arm64, with numpy and scipy)."""
    return get_settings().tools_dir / ".venv-mg5" / "bin" / "python"


def available() -> bool:
    """MadGraph, MadDM and MadDM's RAPIDD library are installed."""
    rapidd = mg5_dir() / "PLUGIN/maddm/vendor/RAPIDD_for_DM/lib/build/libRAPIDD.dylib"
    return python().exists() and (mg5_dir() / "bin/maddm").exists() and rapidd.exists()


def parse_results(text: str) -> dict[str, float]:
    """MadDM_results.txt: Ωh², x_f, ⟨σv⟩(x_f) and MadDM's nucleon cross-sections (the first of each pair)."""
    out = {}
    for key, value in re.findall(r"^(\w+)\s*=\s*\[?([-+0-9.eE]+)", text, flags=re.M):
        out[key] = float(value)
    return out


def parse_alpha(text: str) -> dict[str, list[float]]:
    """maddm.out: 'alpha_q: SIe : SIo : SDe : SDo' per quark."""
    out = {}
    for quark, values in re.findall(r"alpha_([a-z]):\s*(.+)", text):
        out[quark] = [float(v) for v in values.split(":")[:4]]
    return out


def parse_widths(text: str) -> dict[int, float]:
    """'DECAY pdg width' lines of a parameter card."""
    return {int(p): float(w) for p, w in re.findall(r"^\s*DECAY\s+(-?\d+)\s+([-+0-9.eE]+)", text, flags=re.M)}


OFFLINE_PROFILE = "(version 1)(allow default)(deny network*)"


def offline(command: list[str]) -> list[str]:
    """The command with the network denied (macOS's sandbox-exec; Linux's unshare -rn where it is allowed), so that
    MadGraph and MadDM cannot fetch anything. MadDM's ``output`` falls back to generating every mode when a
    ``generate`` produced nothing, and its indirect mode then downloads and installs tools (DRAGON, LHAPDF): seen on
    2026-10-14 for a direct-detection run. Unchanged where neither tool is available."""
    import shutil
    if shutil.which("sandbox-exec"):
        return ["sandbox-exec", "-p", OFFLINE_PROFILE, *command]
    if shutil.which("unshare") and subprocess.run(["unshare", "-rn", "true"], capture_output=True,
                                                                   env=child_environment()).returncode == 0:
        return ["unshare", "-rn", *command]
    return command


def _run(args: list[str], cwd: Path) -> str:
    """Run once, offline (``offline``), retain diagnostics, and never interpret output after failure."""
    try:
        done = subprocess.run(offline(["nice", "-n", "10", str(python()), *args]), cwd=cwd,
                              capture_output=True, text=True, timeout=TIMEOUT_S, env=child_environment())
    except subprocess.TimeoutExpired as error:
        (cwd / "engine.log").write_text(f"TIMEOUT after {TIMEOUT_S}s\n{error.stdout!r}\n{error.stderr!r}")
        raise RuntimeError(f"External engine timed out; see {cwd / 'engine.log'}") from error
    except OSError as error:
        (cwd / "engine.log").write_text(f"START FAILED: {error}")
        raise RuntimeError(f"External engine could not start; see {cwd / 'engine.log'}") from error
    log = done.stdout + done.stderr
    (cwd / "engine.log").write_text(log)
    if done.returncode:
        raise RuntimeError(f"External engine exit {done.returncode}; see {cwd / 'engine.log'}\n{log[-2000:]}")
    return log


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _identity(model: Path, request: dict) -> str:
    """Bind cached results to model contents, parameters and engine sources."""
    engine = mg5_dir()
    files = [*model.rglob("*.py"), *engine.glob("VERSION*"), *engine.glob("bin/maddm"),
             *engine.glob("bin/mg5_aMC"), *engine.glob("PLUGIN/**/*.py"),
             *engine.glob("madgraph/**/*.py"), *engine.glob("PLUGIN/**/*.dylib"), *engine.glob("PLUGIN/**/*.so")]
    material = {str(p.resolve()): _digest(p) for p in sorted(set(files)) if p.is_file()}
    material["request"] = request
    material["python"] = str(python().resolve())
    if python().exists():
        material["python_sha256"] = _digest(python().resolve())
    material["parser_version"] = "M14-2"
    return sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def _cached(work: Path, key: str) -> dict | None:
    path = work / f"cache-{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        payload_hash = sha256(json.dumps(data["result"], sort_keys=True).encode()).hexdigest()
        if (data["identity"] == key and data.get("result_sha256") == payload_hash and data["outputs"]
                and all(_digest(Path(p)) == digest for p, digest in data["outputs"].items())):
            return data["result"]
    except (OSError, ValueError, KeyError):
        pass
    return None


def _save(work: Path, key: str, result: dict, outputs: list[Path]) -> None:
    # Only called after successful exit and validated, newly isolated outputs.
    data = {"identity": key, "result": result,
            "result_sha256": sha256(json.dumps(result, sort_keys=True).encode()).hexdigest(),
            "outputs": {str(p.resolve()): _digest(p) for p in outputs}}
    target = work / f"cache-{key}.json"
    temporary = outputs[0].parent / "cache.json"
    temporary.write_text(json.dumps(data, indent=2))
    temporary.replace(target)


def widths(model_dir: Path, particles: list[str], workdir: Path) -> dict[int, float]:
    """Fresh two-body widths, or a content- and engine-bound successful result."""
    workdir.mkdir(parents=True, exist_ok=True)
    key = _identity(model_dir, {"particles": particles, "kind": "widths"})
    cached = _cached(workdir, key)
    if cached is not None:
        return {int(k): v for k, v in cached.items()}
    attempt = Path(tempfile.mkdtemp(prefix="widths-", dir=workdir))
    out, commands = attempt / "widths.txt", attempt / "widths.mg5"
    commands.write_text(f"import model {model_dir.resolve()}\ncompute_widths {' '.join(particles)} --body_decay=2 "
                        f"--output={out.resolve()}\nexit\n")
    log = _run([str(mg5_dir() / "bin/mg5_aMC"), str(commands.resolve())], attempt)
    if not out.exists():
        raise RuntimeError(f"MadGraph computed no current widths:\n{log[-2000:]}")
    result = parse_widths(out.read_text())
    if not result or any(not math.isfinite(v) or v < 0 for v in result.values()):
        raise RuntimeError(f"Invalid widths in {out}")
    # A partial card must contain every requested particle, not just SM widths.
    particle_text = (model_dir / "particles.py").read_text()
    for name in particles:
        blocks = re.findall(r"Particle\((.*?)\)", particle_text, re.S)
        pdgs = [int(m.group(1)) for block in blocks
                if re.search(r"name\s*=\s*['\"]" + re.escape(name) + r"['\"]", block)
                and (m := re.search(r"pdg_code\s*=\s*(-?\d+)", block))]
        if not pdgs or any(pdg not in result for pdg in pdgs):
            raise RuntimeError(f"Missing requested width {name} in {out}")
    _save(workdir, key, result, [out, attempt / "engine.log"])
    return result


def script(model_dir: Path, dm: str, name: str, params: dict[str, float], relic: bool, direct: bool,
           coannihilators: list[str] | None = None) -> str:
    """A MadDM command file: generate, output, launch with the switches and parameters set."""
    lines = [f"import model {model_dir}", f"define darkmatter {dm}"]
    lines += [f"define coannihilator {' '.join(coannihilators)}"] if coannihilators else []
    lines += ["generate relic_density"] if relic else []
    lines += ["add direct" if relic else "generate direct"] if direct else []
    lines += [f"output {name}", f"launch {name}"]
    lines += ["direct = ON", "direct_electron = OFF"] if direct else []
    lines += [f"set {k} {v}" for k, v in params.items()]
    return "\n".join(lines) + "\n"


def run(model_dir: Path, dm: str, params: dict[str, float], name: str, workdir: Path,
        relic: bool = True, direct: bool = True, coannihilators: list[str] | None = None) -> MadDMResult:
    """One MadDM run; ``params`` must include every new state's width (from ``widths``)."""
    if Path(name).name != name or name in (".", ".."):
        raise ValueError("MadDM output name must be a single path component")
    workdir.mkdir(parents=True, exist_ok=True)
    key = _identity(model_dir, dict(dm=dm, params=params, relic=relic, direct=direct,
                                     coannihilators=coannihilators, kind="run"))
    cached = _cached(workdir, key)
    if cached is not None:
        return MadDMResult.model_validate(cached)
    attempt = Path(tempfile.mkdtemp(prefix="run-", dir=workdir))
    commands = attempt / f"{name}.maddm"
    commands.write_text(script(model_dir.resolve(), dm, name, params, relic, direct, coannihilators))
    log = _run([str(mg5_dir() / "bin/maddm"), str(commands.resolve())], attempt)
    output = attempt / name / "output" / "run_01"
    files = [output / "maddm.out", output / "MadDM_results.txt"]
    if not all(p.exists() for p in files):
        raise RuntimeError(f"MadDM gave no complete current output:\n{log[-2000:]}")
    results = parse_results(files[1].read_text())
    alpha = parse_alpha(files[0].read_text()) if direct else {}
    if relic and any(k not in results or not math.isfinite(results[k]) or results[k] <= 0
                     for k in ("Omegah2", "x_f", "sigmav_xf")):
        raise RuntimeError(f"Missing or invalid relic output in {output}")
    if direct and (not alpha or any(len(v) != 4 or not all(math.isfinite(x) for x in v)
                                   for v in alpha.values())):
        raise RuntimeError(f"Missing or invalid direct-detection coefficients in {output}")
    if any(not math.isfinite(v) for v in results.values()):
        raise RuntimeError(f"Nonfinite MadDM output in {output}")
    result = MadDMResult(omega_h2=results.get("Omegah2"), x_f=results.get("x_f"),
                        sigmav_xf_cm3_s=results.get("sigmav_xf"), alpha=alpha,
                        sigma_raw_cm2={k: v for k, v in results.items() if k.startswith("SigmaN")})
    _save(workdir, key, result.model_dump(), [*files, attempt / "engine.log"])
    return result


# --- annihilation today (G6's cross-check) --------------------------------------------------------------------

HALO_SPEED = 2e-5                  # MadDM's vave_indirect_cont, in c (its default: the dwarfs')
PB_CM3_S = 2.99e-26                # MadDM's pbtocm3: it takes c = 2.99×10¹⁰ cm/s
C_CM_S = 2.99792458e10
MADDM_FINALS = {"hh": "hh", "ddx": "d", "uux": "u", "ssx": "s", "ccx": "c", "bbx": "b", "ttx": "t", "zz": "Z",
                "wpwm": "W", "emep": "e", "mummup": "mu", "tamtap": "tau", "vevex": "nu_e", "vmvmx": "nu_mu",
                "vtvtx": "nu_tau", "gg": "g", "zh": "Zh"}


def indirect_script(model_dir: Path, dm: str, name: str, halo: float = HALO_SPEED) -> str:
    """A MadDM command file for ⟨σv⟩ today at tree level, per final state. ``maddm_first_indirect`` is set False
    so that MadDM does not ask which tools to install (its 'sigmav' mode needs none)."""
    return "\n".join(["set maddm_first_indirect False", f"import model {model_dir}", f"define darkmatter {dm}",
                      "generate indirect_detection 2to2lo", f"output {name}", f"launch {name}", "indirect = sigmav",
                      "relic = ON", "direct = OFF", "set sigmav_method inclusive",
                      f"set vave_indirect_cont {halo}"]) + "\n"


def parse_sigma_v(names_inc: str, out: str) -> dict[str, float]:
    """MadDM's 'sigma*v:' lines (``maddm.out``) by final state, the process names taken from
    ``include/process_names.inc`` in order: ``maddm.out`` keeps only their first 12 characters."""
    names = sorted(re.findall(r"PROCESS_NAMES\((\d+)\)\s*=\s*'(\S+)'", names_inc), key=lambda kv: int(kv[0]))
    values = re.findall(r"sigma\*v:\S*\s+([-+0-9.eE]+)\s*cm", out)
    if len(values) != len(names):
        raise RuntimeError(f"MadDM gave {len(values)} σv values for {len(names)} processes")
    found: dict[str, float] = {}
    for (_, process), value in zip(names, values):
        final = process.split("_", 1)[1]
        found[final] = found.get(final, 0.0) + float(value)
    return found


def relative(sigma_v: dict[str, float], halo: float = HALO_SPEED) -> tuple[float, dict[str, float]]:
    """(v_rel, σv_rel in cm³/s by final state) from MadDM's 2 → 2 values.

    MadDM gives each particle the momentum m·u with u = √3 v_halo and multiplies σ by u (``taacs_ID``), so the
    relative speed is 2u and it prints ½σv_rel; it converts with c = 2.99×10¹⁰ cm/s."""
    u = math.sqrt(3.0) * halo
    factor = 2.0 * C_CM_S * 1e-36 / PB_CM3_S
    return 2.0 * u, {k: v * factor for k, v in sigma_v.items()}


def indirect(model_dir: Path, dm: str, name: str, workdir: Path,
             halo: float = HALO_SPEED) -> tuple[float, dict[str, float]]:
    """(v_rel, ⟨σv⟩ in cm³/s by MadDM's final-state name) at tree level, offline; see ``relative``."""
    if Path(name).name != name or name in (".", ".."):
        raise ValueError("MadDM output name must be a single path component")
    if len(dm) > ufo.MADGRAPH_NAME_MAX:
        raise ValueError(f"{dm}: longer than MadDM's output carries ({ufo.MADGRAPH_NAME_MAX} characters); the UFO "
                         "writers give such names a code (ufo.code_name)")
    workdir.mkdir(parents=True, exist_ok=True)
    key = _identity(model_dir, dict(dm=dm, halo=halo, kind="indirect"))
    cached = _cached(workdir, key)
    if cached is None:
        attempt = Path(tempfile.mkdtemp(prefix="id-", dir=workdir))
        commands = attempt / f"{name}.maddm"
        commands.write_text(indirect_script(model_dir.resolve(), dm, name, halo))
        log = _run([str(mg5_dir() / "bin/maddm"), str(commands.resolve())], attempt)
        files = [attempt / name / "include" / "process_names.inc", attempt / name / "output" / "run_01" / "maddm.out"]
        if not all(f.exists() for f in files):
            raise RuntimeError(f"MadDM gave no complete current output:\n{log[-2000:]}")
        found = parse_sigma_v(files[0].read_text(), files[1].read_text())
        if not found or any(not math.isfinite(v) or v < 0 for v in found.values()):
            raise RuntimeError(f"Invalid σv in {files[1]}")
        cached = {"sigma_v": found}
        _save(workdir, key, cached, [*files, attempt / "engine.log"])
    return relative(cached["sigma_v"], halo)


# --- a derivation checked against MadDM's quark-level coefficients (verification rank two) -------

AGREEMENT = 0.01
YUKAWA = {"d": "ymdown", "u": "ymup", "s": "ymstrange", "c": "ymc", "b": "ymb", "t": "ymt"}
# the coefficients with a nucleon form factor in MadDM: (SIe, SIo, SDe, SDo)
REACHES_NUCLEON = {q: (True, q in "ud", q in "uds", q in "uds") for q in QUARK_ORDER}


class MadDMCoefficients(StrictModel):
    """MadDM's α_q for a model, and what is needed to compare them."""

    alpha: dict[str, list[float]]
    coupled: list[str]                       # quarks the dark sector reaches at tree level
    masses: dict[str, float]                 # the quark masses the model's couplings use


class AlphaComparison(StrictModel):
    """A derivation against MadDM's coefficients, up to one overall sign."""

    covered: bool
    reason: str = ""
    max_relative_difference: float | None = None
    sign: int = 1
    spurious: list[str] = Field(default_factory=list)          # uncoupled quarks MadDM gives a coefficient
    expected: dict[str, list[float]] = Field(default_factory=dict)

    @property
    def agree(self) -> bool:
        """Within AGREEMENT, where MadDM covers the interaction."""
        return not self.covered or (self.max_relative_difference or 0.0) <= AGREEMENT


def coupled_quarks(ext: UfoExtension) -> tuple[set[str], bool]:
    """The quarks the dark sector reaches at tree level, and whether through the Higgs."""
    new = {f"P.{p.name}" for p in ext.particles} | {f"P.{p.name}__tilde__" for p in ext.particles}
    to_new = {v.particles[1][2:] for v in ext.vertices if v.particles[1][2:] in QUARK_ORDER and v.particles[2] in new}
    through_higgs = any("P.H" in v.particles and set(v.particles) & new for v in ext.vertices)
    return (set(QUARK_ORDER) if through_higgs else to_new), through_higgs


def card_value(card: str, name: str) -> float:
    """A parameter of a param_card by its comment name."""
    for line in card.splitlines():
        if line.strip().lower().endswith(f"# {name.lower()}"):
            return float(line.split()[1])
    raise KeyError(name)


def coefficients(spec: ModelSpec, workdir: Path) -> MadDMCoefficients:
    """MadDM's α_q for the model (its UFO file written by ADROIT). ValueError if the writer refuses it."""
    if " " in str(workdir):
        raise RuntimeError(f"MadGraph cannot use a path with spaces: {workdir}")
    ext = ufo.extension(spec)
    model = ufo.write(spec, workdir / "models")
    unstable = [p for p in ext.particles if p.width != "ZERO"]
    width = widths(model, [p.name for p in unstable], workdir / f"w_{ext.model}") if unstable else {}
    params = {p.name: p.value for p in ext.parameters if p.block in ("MASS", "DMINPUTS")}
    params |= {p.width: width[p.pdg] for p in unstable}
    found = run(model, ext.names[spec.dark_matter.name], params, f"dd_{ext.model}", workdir, relic=False)
    coupled, through_higgs = coupled_quarks(ext)
    card = (workdir / f"dd_{ext.model}" / "Cards" / "param_card.dat").read_text()
    masses = {q: card_value(card, YUKAWA[q] if through_higgs else mass) for q, (_, mass, _) in ufo.QUARKS.items()}
    return MadDMCoefficients(alpha=found.alpha, coupled=sorted(coupled), masses=masses)


def expected_alpha(spec: ModelSpec, derivation: dv.Derivation, masses: dict[str, float]) -> dict[str, list[float]]:
    """The derivation's coefficients in MadDM's normalisation (its EffOperators model), per quark.

    Dirac: α_SIe = m_q C75q (the top: −m_t C71), α_SIo = C61q, α_SDe = C64q. Majorana: half of these
    (MadDM's self-conjugate vertex is 2iα, DirectDM's Majorana operators carry ½). Complex scalar:
    α_SIo = C61q, α_SIe = m_q C63q/(2m_φ); real scalar: α_SIe = m_q C63q/(4m_S) (the top: −m_t C65/(4m_S)).
    """
    c = dv.evaluate(derivation, spec).coefficients
    m = spec.dark_matter.mass_gev
    kind = derivation.dm_type.value
    out = {}
    for q in QUARK_ORDER:
        if kind in ("D", "M"):
            half = 0.5 if kind == "M" else 1.0
            out[q] = [half * masses[q] * c.get(f"C75{q}", -c.get("C71", 0.0) if q == "t" else 0.0),
                      half * c.get(f"C61{q}", 0.0), half * c.get(f"C64{q}", 0.0), 0.0]
        else:
            scale = 1.0 / (2 * m) if kind == "C" else 1.0 / (4 * m)
            out[q] = [masses[q] * scale * c.get(f"C63{q}", -c.get("C65", 0.0) if q == "t" else 0.0),
                      c.get(f"C61{q}", 0.0), 0.0, 0.0]
    return out


def check(spec: ModelSpec, derivation: dv.Derivation, found: MadDMCoefficients) -> AlphaComparison:
    """The derivation against MadDM, over the coupled quarks and the coefficients that reach a nucleon."""
    expected = expected_alpha(spec, derivation, found.masses)
    scale = max(abs(x) for v in expected.values() for x in v)
    if max(abs(x) for v in found.alpha.values() for x in v) < 1e-6 * max(scale, 1e-300):
        return AlphaComparison(covered=False, expected=expected,
                               reason="MadDM's coefficients are all zero: no such operator in its basis")
    worst = {1: 0.0, -1: 0.0}
    for sign in worst:
        for q in found.coupled:
            for got, want, reaches in zip(found.alpha.get(q, [0.0] * 4), expected[q], REACHES_NUCLEON[q]):
                if reaches and (abs(want) > 1e-6 * scale or abs(got) > 1e-6 * scale):
                    worst[sign] = max(worst[sign], abs(sign * got - want) / max(abs(want), abs(got)))
    sign = min(worst, key=worst.get)
    spurious = sorted(q for q in QUARK_ORDER if q not in found.coupled
                      and any(abs(x) > 1e-20 for x in found.alpha.get(q, [])))
    return AlphaComparison(covered=True, max_relative_difference=worst[sign], sign=sign, spurious=spurious,
                           expected=expected)
