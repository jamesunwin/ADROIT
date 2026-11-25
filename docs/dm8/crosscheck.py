"""DM8's numerical cross-check (verification rank two): ADROIT's own UFO files and MadDM.

1. **The UFO writer against DMsimp** (the LHC DM Working Group's FeynRules model),
   vertex by vertex at matched parameters, for V1, A1 and complex scalar dark
   matter (DMsimp writes the scalar current with a ½: its g_VXc is 2g here).
2. **MadDM against DM7's relic code** for V1 and A1, with ADROIT's UFO files and
   MadGraph's own widths.
3. **MadDM against the gate's derivations.** For each gate model MadDM can treat
   (the writer refuses dipoles and the anapole; MadDM's direct detection has no
   pseudoscalar operator), ADROIT's UFO file of the reference model goes through
   MadDM, and its quark-level coefficients α_q are compared with both agents'
   Wilson coefficients in MadDM's normalisation (its EffOperators model), up to
   one overall sign, over the quarks the model couples and the coefficients with a
   nucleon form factor in MadDM (scalar: all quarks; vector: u, d; axial and
   tensor: u, d, s). A Higgs-mediated coupling uses MadGraph's Yukawa masses:
   - Dirac: α_SIe = m_q C75q (the top: −m_t C71), α_SIo = C61q, α_SDe = C64q;
   - complex scalar: α_SIo = C61q, α_SIe = m_q C63q/(2m_φ);
   - real scalar: α_SIe = m_q C63q/(4m_S) (the top: −m_t C65/(4m_S)).

Run from the repository root (about an hour; needs MadGraph and MadDM in the tools
folder):

    uv run python docs/dm8/crosscheck.py          # all three parts
    uv run python docs/dm8/crosscheck.py 3        # one part; the others are kept from crosscheck.json

Writes docs/dm8/crosscheck.txt and crosscheck.json.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.constraints import annihilation, maddm, spin1  # noqa: E402
from adroit.core.config import get_settings  # noqa: E402
from adroit.core.model_spec import ModelSpec  # noqa: E402
from adroit.library.interactions import derivation as dv  # noqa: E402
from adroit.library.interactions import ufo  # noqa: E402

HERE = Path(__file__).parent
WORK = get_settings().tools_dir / "maddm-work" / "crosscheck"
REFERENCE = {m["id"]: m for m in yaml.safe_load((HERE / "gate_models.yaml").read_text())["models"]}
GATE = {r["id"]: r for r in json.loads((HERE / "gate_live_deriver.json").read_text())["models"]}
DMSIMP = maddm.mg5_dir() / "models" / "DMsimp_s_spin1"
QUARK_PAIRS = ("d", "u", "s", "c", "b", "t")

_DUMP = r"""
import cmath, importlib, json, sys
model_dir, overrides = sys.argv[1], json.loads(sys.argv[2])
sys.path[:0] = [model_dir, model_dir.rsplit('/', 1)[0]]
m = importlib.import_module(model_dir.rsplit('/', 1)[1])
ns = {'cmath': cmath, 'complex': complex, 'abs': abs}
for f in m.all_functions:
    ns[f.name] = eval('lambda %s: %s' % (','.join(f.arguments), f.expr), ns)
for p in m.all_parameters:
    ns[p.name] = overrides.get(p.name, p.value) if p.nature == 'external' else eval(p.value, ns)
out = []
for v in m.all_vertices:
    for (i, j), c in v.couplings.items():
        z = complex(eval(c.value, ns))
        out.append([[p.name for p in v.particles], v.lorentz[j].structure, z.real, z.imag])
print(json.dumps(out))
"""


def vertices(model_dir: Path, overrides: dict[str, float]) -> list:
    """Every vertex's (particles, Lorentz structure, coupling value), the model evaluated at ``overrides``."""
    done = subprocess.run([str(maddm.python()), "-c", _DUMP, str(model_dir), json.dumps(overrides)],
                          capture_output=True, text=True, timeout=600)
    if done.returncode:
        raise RuntimeError(done.stderr[-2000:])
    return json.loads(done.stdout)


def _canonical(rows: list, rename: dict[str, str], keep: set[str]) -> dict:
    out: dict = {}
    for particles, structure, re_, im in rows:
        names = [rename.get(p, p) for p in particles]
        if not keep & set(names) or abs(complex(re_, im)) < 1e-14:
            continue
        value = complex(re_, im)
        if structure == "P(1,3) - P(1,2)":
            structure, value = "P(1,2) - P(1,3)", -value
        out.setdefault(tuple(names), {})[structure] = out.get(tuple(names), {}).get(structure, 0) + value
    return out


def part1() -> list[str]:
    """ADROIT's UFO against DMsimp, vertex by vertex."""
    cases = [("V1", "G1", "dmchi", {"gVXd": 1.0}, {"gV": 0.25}),
             ("A1", "G2", "dmchi", {"gAXd": 1.0}, {"gA": 0.25}),
             ("complex scalar", "G7", "dmphi", {"gVXc": 2.0}, {"gV": 0.25})]
    out = ["1. ADROIT's UFO files against DMsimp_s_spin1, vertex by vertex"]
    for label, gid, dm, dm_couplings, quark in cases:
        spec = ModelSpec.model_validate(REFERENCE[gid]["reference"]["spec"])
        ours = _canonical(vertices(ufo.write(spec, WORK / "models"), {}), {}, {dm, "dmzp"})
        zero = {k: 0.0 for k in ("gVXd", "gAXd", "gVXc", "gVh")} | {
            f"g{a}{q}{g}{g}": 0.0 for a in "VA" for q in "ud" for g in "123"} | {
            f"g{a}l{g}{g}": 0.0 for a in "VA" for g in "123"} | {f"gnu{g}{g}": 0.0 for g in "123"}
        quarks = {f"{kind}{q}{g}{g}": value for kind, value in quark.items() for q in "ud" for g in "123"}
        dmsimp_values = zero | dm_couplings | quarks
        rename = {"Xd": "dmchi", "Xd~": "dmchi~", "Xc": "dmphi", "Xc~": "dmphi~", "Y1": "dmzp"}
        theirs = _canonical(vertices(DMSIMP, dmsimp_values), rename, {dm, "dmzp"})
        theirs = {k: v for k, v in theirs.items() if dm in "".join(k) or any(q in k for q in QUARK_PAIRS)}
        worst, missing = 0.0, sorted(set(ours) ^ set(theirs))
        for key in set(ours) & set(theirs):
            for structure in set(ours[key]) | set(theirs[key]):
                a, b = ours[key].get(structure, 0), theirs[key].get(structure, 0)
                worst = max(worst, abs(a - b) / max(abs(a), abs(b)))
        out.append(f"  {label}: {len(set(ours) & set(theirs))} vertices compared, largest relative difference "
                   f"{worst:.1e}; in one model only: {missing or 'none'}")
    return out


def _point(gid: str, m_dm: float, m_med: float) -> tuple[Path, dict[str, float]]:
    """ADROIT's UFO file of a reference model at (m_dm, m_med), and MadDM's parameters with the width."""
    raw = REFERENCE[gid]["reference"]["spec"]
    spec = ModelSpec.model_validate(raw)
    fields = [f.model_copy(update={"mass_gev": {"dark_matter": m_dm, "mediator": m_med}.get(f.role.value, f.mass_gev)})
              for f in spec.fields]
    spec = spec.model_copy(update={"fields": fields, "name": f"{spec.name}_{m_dm:g}_{m_med:g}"})
    model = ufo.write(spec, WORK / "models")
    ext = ufo.extension(spec)
    width = maddm.widths(model, [p.name for p in ext.particles if p.width != "ZERO"], WORK / f"w_{spec.name}")
    params = {p.name: p.value for p in ext.parameters if p.block in ("MASS", "DMINPUTS")}
    params |= {p.width: width[p.pdg] for p in ext.particles if p.width != "ZERO"}
    return model, params


def part2() -> list[str]:
    """MadDM (ADROIT's UFO) against DM7's relic code."""
    out = ["", "2. Relic density: MadDM with ADROIT's UFO files against DM7's own code"]
    points = [(100.0, 2000.0), (500.0, 2000.0), (950.0, 2000.0), (1500.0, 1000.0)]
    for label, gid in (("V1", "G1"), ("A1", "G2")):
        for m_dm, m_med in points:
            model, params = _point(gid, m_dm, m_med)
            r = maddm.run(model, "dmchi", params, f"relic_{label}_{m_dm:g}_{m_med:g}", WORK, direct=False)
            ours = annihilation.omega_h2(spin1.benchmark(label, m_med), m_dm)
            out.append(f"  {label} m_χ = {m_dm:g}, M = {m_med:g} GeV: MadDM Ωh² = {r.omega_h2:.3g}, DM7 {ours:.3g}, "
                       f"ratio {r.omega_h2 / ours:.3f}; Γ(Z′) = {params['WDMZP']:.4g} GeV")
    return out


def part3() -> list[str]:
    """MadDM's quark-level coefficients, from each gate model's full Lagrangian, against the derivations."""
    out = ["", "3. MadDM's quark-level coefficients against the gate's derivations (both halves)"]
    checker = {r["id"]: r for r in json.loads((HERE / "gate_live_checker.json").read_text())["models"]}
    for gid in ("G1", "G2", "G3", "G4", "G7", "G8", "G9", "G5", "G6", "G10"):
        # The UFO file is written from the reference model: the intake's terms carried only coupling names
        # (record, section 14); the derivations use the same symbols.
        spec = ModelSpec.model_validate(REFERENCE[gid]["reference"]["spec"])
        derivations = {"claude-opus-5-5": dv.Derivation.model_validate(GATE[gid]["result"]["derivation"]),
                       "gpt-5.6-sol": dv.Derivation.model_validate(checker[gid]["second"])}
        try:
            found = maddm.coefficients(spec, WORK)
        except ValueError as exc:
            out.append(f"  {gid}: not written as UFO ({exc})")
            continue
        for who, derivation in derivations.items():
            c = maddm.check(spec, derivation, found)
            out.append(f"  {gid} ({who}): " + (
                f"largest relative difference {c.max_relative_difference:.1e}"
                f"{' (overall sign reversed)' if c.sign < 0 else ''}" if c.covered else c.reason))
        spurious = maddm.check(spec, derivations["claude-opus-5-5"], found).spurious
        if spurious:
            out.append(f"    MadDM reports coefficients for quarks the model does not couple: {', '.join(spurious)} "
                       "(each the last computed quark's)")
    return out


def main() -> None:
    """All three parts."""
    if not maddm.available():
        raise SystemExit("MadGraph and MadDM are not installed in the tools folder")
    WORK.mkdir(parents=True, exist_ok=True)
    parts = {"1": part1, "2": part2, "3": part3}
    chosen = sys.argv[1].split(",") if len(sys.argv) > 1 else list(parts)
    store = HERE / "crosscheck.json"
    done = json.loads(store.read_text()) if store.exists() else {}
    done |= {k: parts[k]() for k in chosen}
    store.write_text(json.dumps(done, indent=1))
    lines = ["DM8 numerical cross-check: ADROIT's UFO files and MadDM (3.3 release candidate, MadGraph 3.8.0)", ""]
    lines += [line for k in sorted(done) for line in done[k]]
    text = "\n".join(lines) + "\n"
    (HERE / "crosscheck.txt").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
