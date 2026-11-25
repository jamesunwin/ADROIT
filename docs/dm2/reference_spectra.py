"""Reference spectra for the DM2 gate: WIMpy_NREFT and WimPyDD against the project's rates.

Each reference code runs twice:
- **as published**, to record how far its own rounding moves it;
- **patched**, with its rounded constants replaced by the CODATA values of
  ``conventions`` and, for WimPyDD, its six-figure response table replaced by
  the full-precision coefficients the project ships. The patched runs test
  the physics (the operator algebra, the kinematics, the normalisation) and
  are the gate's references.

The halo is the project's Standard Halo Model in both: WIMpy_NREFT evaluates
it in closed form with the same parameters, and WimPyDD is given it as 8000
velocity streams. WIMpy_NREFT omits the Φ̃' response, so O_12 and O_13 are
compared with WimPyDD only; it has no mass splitting, so inelastic cases are
too.

Run from the repository root (reference codes in data/external/):

    uv run python docs/dm2/reference_spectra.py

It writes tests/physics/fixtures/reference_spectra.json and the summary
docs/dm2/reference_summary.txt, which the numbers in docs/dm2_forward_model.md
come from.
"""

from __future__ import annotations

import json
import re
from datetime import date
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from extract_responses import WIMPYDD_ITAR  # noqa: E402

from adroit.core.dm_state import (DarkMatterParticle, HaloModel, InteractionModel,  # noqa: E402
                                      ModelLayer, OperatorCoefficient)
from adroit.physics import conventions as cv  # noqa: E402
from adroit.physics import halo as halos  # noqa: E402
from adroit.physics import nuclear, rates, targets  # noqa: E402
from adroit.external import fetch  # noqa: E402

EXTERNAL = ROOT / "data/external"
WORK = EXTERNAL / "dm2_reference"
DRIVER = Path(__file__).parent / "reference_drivers.py"
FIXTURE = ROOT / "tests/physics/fixtures/reference_spectra.json"
SUMMARY = Path(__file__).parent / "reference_summary.txt"
PYTHON = {"wimpy": EXTERNAL / ".venv-audit/bin/python",
          "wimpydd": EXTERNAL / ".venv-wimpydd/bin/python"}
ENERGIES = np.geomspace(1.0, 400.0, 24)
SCALE = cv.coupling_gev2(1.0)
NO_PHI_TILDE = {12, 13}          # WIMpy_NREFT lacks the Φ̃' response these feed


# --- the cases -----------------------------------------------------------------------


def _case(name: str, isotope: str, coefficients: dict[int, tuple[float, float]],
          mass: float = 100.0, spin: float = 0.5, splitting: float = 0.0,
          gate: bool = True) -> dict:
    """One comparison. WIMpy_NREFT takes part only where it can compute the case."""
    codes = ["wimpydd"]
    covered = isotope in nuclear.shell_model_table()
    if covered and splitting == 0.0 and not NO_PHI_TILDE & set(coefficients):
        codes.append("wimpy")
    return {"name": name, "isotope": isotope, "mass_gev": mass, "spin": spin,
            "splitting_kev": splitting, "energies_kev": ENERGIES.tolist(),
            "coefficients": {str(op): list(c) for op, c in coefficients.items()},
            "codes": codes, "gate": gate}


def cases() -> list[dict]:
    """Every operator alone; every operator at once on each isotope; spins, masses, splittings."""
    rng = np.random.default_rng(20260929)
    every = {op: tuple(rng.uniform(-1.0, 1.0, 2) * SCALE) for op in rates.OPERATORS}
    without = {op: c for op, c in every.items() if op not in NO_PHI_TILDE}
    generic = (SCALE, -0.37 * SCALE)
    out = [_case(f"O{op} alone", "Xe131", {op: generic}) for op in rates.OPERATORS]
    for isotope in ("Xe129", "Xe132", "Xe136", "Ge73", "Ge74", "I127", "Na23", "F19",
                    "Ar40", "Si28", "O16", "Ca40", "C12"):
        out.append(_case("all operators", isotope, every))
        out.append(_case("all but O12, O13", isotope, without))
    for mass in (10.0, 1000.0):
        out.append(_case("all operators", "Xe131", every, mass=mass))
    for spin in (0.0, 1.0):
        out.append(_case("all but O12, O13", "Xe131", without, spin=spin))
    out += [
        _case("inelastic O1", "Xe131", {1: generic}, mass=1000.0, splitting=100.0),
        _case("inelastic, all operators", "Xe131", every, mass=1000.0, splitting=60.0),
        _case("exothermic O4", "Xe129", {4: generic}, mass=50.0, splitting=-30.0),
        _case("exothermic, all operators", "F19", every, mass=20.0, splitting=-20.0),
        _case("inelastic O4", "Ge73", {4: generic}, mass=500.0, splitting=50.0),
        _case("Helm O1 (no shell model)", "W184", {1: generic}, gate=False),
        _case("approximate O4 (no shell model)", "W183", {4: generic}, gate=False),
    ]
    return out


# --- the patched reference codes -----------------------------------------------------


def _replace(text: str, pattern: str, value: str) -> str:
    """Replace a regular expression that must occur at least once."""
    new, count = re.subn(pattern, value, text)
    if count == 0:
        raise RuntimeError(f"pattern {pattern!r} not found")
    return new


def patch_wimpy(dest: Path) -> Path:
    """WIMpy_NREFT with CODATA constants in place of its rounded ones."""
    source = fetch.locate("WIMpy_NREFT")
    if source is None:
        raise RuntimeError("WIMpy_NREFT is missing; run adroit setup --fetch --only WIMpy_NREFT")
    shutil.copytree(source / "WIMpy", dest / "WIMpy", dirs_exist_ok=True)
    path = dest / "WIMpy/DMUtils.py"
    text = path.read_text()
    for pattern, value in [
        (r"m_A = A\*0\.9315", f"m_A = A*{cv.AMU_GEV!r}"),
        (r"3e5\*np\.sqrt\(", f"{cv.C_KM_S!r}*np.sqrt("),
        (r"/\(\(3e5\*\*2\)\)", f"/(({cv.C_KM_S!r}**2))"),
        (r"amu = 931\.5e3", f"amu = {cv.AMU_GEV * 1e6!r}"),
        (r"q1\*\(1e-12/1\.97e-7\)", f"q1/{cv.HBARC_GEV_FM * 1e6!r}"),
        (r"1\.69612985e14", f"{rates.RATE_UNIT * cv.C_KM_S!r}"),
    ]:
        text = _replace(text, pattern, value)
    path.write_text(text)
    return dest


def _full_precision_table(original: Path) -> str:
    """WimPyDD's response table with the project's full-precision coefficients."""
    rows = [line.split() for line in original.read_text().splitlines() if line.strip()]
    table = nuclear.shell_model_table()
    for isotope, itar in WIMPYDD_ITAR.items():
        grid = table["H1" if isotope == "H" else isotope]["responses"]
        for k, name in enumerate(nuclear.RESPONSES):
            for a in (0, 1):
                for b in (0, 1):
                    # WimPyDD transposes each matrix as it reads the file.
                    coeffs = grid.get(name, [[[], []], [[], []]])[b][a]
                    row = ((itar - 1) * 8 + k) * 4 + a * 2 + b
                    rows[row] = [repr(c) for c in coeffs] + ["0"] * (11 - len(coeffs))
    return "\n".join(" ".join(r) for r in rows) + "\n"


def patch_wimpydd(dest: Path) -> Path:
    """WimPyDD with CODATA constants and full-precision responses (without WimPyC).

    WimPyDD builds its coded experiments when imported, so their folders are copied too.
    """
    source, target = EXTERNAL / "manual/WimPyDD", dest / "WimPyDD"
    target.mkdir(parents=True, exist_ok=True)
    for item in ("Targets", "Halo_functions", "Experiments"):
        shutil.copytree(source / item, target / item, dirs_exist_ok=True)
    (target / "__init__.py").write_text("from .package import *\n")
    constants = [
        (r"hbarc=197\.e-3", f"hbarc={cv.HBARC_GEV_FM!r}"),
        (r"0\.931e0", f"{cv.AMU_GEV!r}"),
        (r"(?<![\d.])0\.931(?!\d)", f"{cv.AMU_GEV!r}"),
        (r"c_light=3\.e5", f"c_light={cv.C_KM_S!r}"),
        (r"\*300\.(?!\d)", f"*{cv.C_KM_S / 1000.0!r}"),
        (r"hbarc2=0\.389e-27", f"hbarc2={cv.HBARC_GEV_CM ** 2!r}"),
        (r"6\.02e23", "6.02214076e23"),
    ]
    text = (source / "package.py").read_text()
    for pattern, value in constants:
        text = _replace(text, pattern, value)
    (target / "package.py").write_text(text)
    for path in (target / "Targets/Nuclear_response_functions").glob("*_func_w*.py"):
        text = path.read_text().replace("hbarc=197.e-3", f"hbarc={cv.HBARC_GEV_FM!r}")
        if "import numpy as np" not in text:      # 42Ca, 44Ca, 46Ca use np without importing it
            text = "import numpy as np\n" + text
        path.write_text(text)
    table = target / "Targets/Nuclear_response_functions/nuclear_response_functions_coefficients_table.dat"
    table.write_text(_full_precision_table(table))
    return dest


def original_wimpydd(dest: Path) -> Path:
    """WimPyDD as published, without WimPyC (which the rates do not need)."""
    source, target = EXTERNAL / "manual/WimPyDD", dest / "WimPyDD"
    target.mkdir(parents=True, exist_ok=True)
    for item in ("Targets", "Halo_functions", "Experiments"):
        shutil.copytree(source / item, target / item, dirs_exist_ok=True)
    shutil.copy(source / "package.py", target / "package.py")
    (target / "__init__.py").write_text("from .package import *\n")
    return dest


# --- running and comparing -----------------------------------------------------------


def streams(halo: HaloModel, step: float = 0.1) -> dict:
    """The halo as velocity streams: η(v) as a sum of steps, one per bin of width ``step``."""
    edges = np.arange(0.0, halos.max_speed_km_s(halo) + step, step)
    eta, _ = halos.velocity_integrals(edges, halo)
    return {"v": (0.5 * (edges[:-1] + edges[1:])).tolist(), "delta_eta": (-np.diff(eta)).tolist()}


def run(code: str, root: Path, selected: list[dict], halo: HaloModel) -> list[list[float]]:
    """Run one reference code on the selected cases, in its own environment."""
    payload = {"cases": selected, "streams": streams(halo) if code == "wimpydd" else None,
               "halo": {"v_lab": halo.v_lab_km_s, "v0": halo.v0_km_s, "v_esc": halo.v_esc_km_s}}
    cases_path, out_path = WORK / f"{code}_cases.json", WORK / f"{code}_{root.name}.json"
    cases_path.write_text(json.dumps(payload))
    subprocess.run([str(PYTHON[code]), str(DRIVER), code, str(cases_path), str(out_path),
                    str(root)], check=True, cwd=root, stdin=subprocess.DEVNULL)
    return json.loads(out_path.read_text())


def ours(case: dict) -> np.ndarray:
    """The project's rate for a case, per kg of the pure isotope."""
    particle = DarkMatterParticle(mass_gev=case["mass_gev"], spin=case["spin"],
                                  mass_splitting_kev=case["splitting_kev"])
    interaction = InteractionModel(name=case["name"], layer=ModelLayer.nonrelativistic,
                                   coefficients=[OperatorCoefficient(operator=int(op), proton=p,
                                                                     neutron=n)
                                                 for op, (p, n) in case["coefficients"].items()])
    isotope = targets.single_isotope(case["isotope"]).isotopes[0]
    return rates.isotope_rate(np.array(case["energies_kev"]), particle,
                              rates.isospin_coefficients(interaction), isotope, HaloModel(),
                              nuclear.NuclearModel.shell_model)


def bulk_mask(case: dict, halo: HaloModel, margin_km_s: float = 50.0) -> np.ndarray:
    """Energies whose v_min lies at least ``margin_km_s`` below the fastest particle."""
    m_t = cv.nuclear_mass_gev(int(re.sub(r"\D", "", case["isotope"])))
    v_min = np.array([cv.v_min_km_s(e, m_t, case["mass_gev"], case["splitting_kev"])
                      for e in case["energies_kev"]])
    return v_min < halos.max_speed_km_s(halo) - margin_km_s


def deviation(mine: np.ndarray, reference: list[float], mask: np.ndarray) -> float:
    """The largest |mine/reference − 1| over the masked energies where the reference is positive."""
    ref = np.asarray(reference)
    use = mask & (ref > 1e-12 * ref.max()) if ref.max() > 0 else mask & False
    return float(np.max(np.abs(mine[use] / ref[use] - 1.0))) if use.any() else 0.0


def main() -> None:
    """Run every reference, write the fixture, print the summary."""
    from adroit.external import fetch

    halo = HaloModel()
    WORK.mkdir(parents=True, exist_ok=True)
    all_cases = cases()
    roots = {"wimpy": {"patched": patch_wimpy(WORK / "wimpy_exact"),
                       "published": fetch.locate("WIMpy_NREFT")},
             "wimpydd": {"patched": patch_wimpydd(WORK / "wimpydd_exact"),
                         "published": original_wimpydd(WORK / "wimpydd_published")}}
    results: dict[tuple[str, str], dict[int, list[float]]] = {}
    for code, versions in roots.items():
        indices = [i for i, c in enumerate(all_cases) if code in c["codes"]]
        for version, root in versions.items():
            spectra = run(code, root, [all_cases[i] for i in indices], halo)
            results[(code, version)] = dict(zip(indices, spectra))
    lines = [f"{'case':34s} {'isotope':7s} {'code':8s} {'patched bulk':>12s} {'tail':>9s} "
             f"{'published bulk':>15s} {'tail':>9s}"]
    for i, case in enumerate(all_cases):
        mine, bulk = ours(case), bulk_mask(case, halo)
        for code in case["codes"]:
            patched, published = results[(code, "patched")][i], results[(code, "published")][i]
            if isinstance(patched, str):
                raise RuntimeError(f"patched {code} failed on {case['name']}, {case['isotope']}: "
                                   f"{patched}")
            case[code] = patched
            as_published = (f"fails ({published.split(':')[0]})" if isinstance(published, str)
                            else f"{deviation(mine, published, bulk):15.1e} "
                                 f"{deviation(mine, published, ~bulk):9.1e}")
            lines.append(f"{case['name']:34s} {case['isotope']:7s} {code:8s} "
                         f"{deviation(mine, patched, bulk):12.1e} "
                         f"{deviation(mine, patched, ~bulk):9.1e} {as_published}")
    print("\n".join(lines))
    SUMMARY.write_text(f"# Output of docs/dm2/reference_spectra.py, run {date.today()}.\n"
                       "# Largest |ours/reference - 1| over 24 energies, 1-400 keV; bulk: v_min "
                       "at least 50 km/s below the fastest particle.\n" + "\n".join(lines) + "\n")
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps({
        "description": "Reference spectra (events/(keV kg day), per kg of the pure isotope) "
                       "from WIMpy_NREFT and WimPyDD with CODATA constants and full-precision "
                       "responses; made by docs/dm2/reference_spectra.py.",
        "halo": "the Standard Halo Model of arXiv:2105.00599 (HaloModel defaults)",
        "cases": all_cases}, indent=1) + "\n")
    print(f"wrote {FIXTURE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
