"""G3's reference values: MadGraph's standalone matrix elements at fixed phase-space points.

For each model and process below, MadGraph 3.8 (in the tools folder) writes its standalone Fortran code; a small
driver evaluates |M|² — summed over final and averaged over initial helicities and colours, with MadGraph's
1/(identical final particles) — at centre-of-momentum points with p₁ along +z and k₁ at angle θ in the x–z plane,
the frame of ``adroit.constraints.tree``. The UFO model itself is dumped through MadGraph's Python
(``ufo_model.dump``), so the fast tests rebuild the same model without MadGraph.

Writes ``tests/constraints/data/g3_madgraph.json`` (the matrix elements, the masses MadGraph used),
``tests/constraints/data/g3_ufo_<model>.json.gz`` (the dumps) and ``tests/constraints/data/g3_madgraph_widths.json``
(MadGraph's two-body widths, ``compute_widths``, with the partial widths it set to zero). Run from the repository root:

    python docs/g3/madgraph_references.py [--work DIR]

MadGraph runs with ``zerowidth_tchannel False`` (widths in every propagator, as the engine), each model's
``-full`` restriction (the UFO's own parameter values, as the dump), and explicit coupling orders (≤ 10 each):
by default MadGraph keeps only the leading order of its WEIGHTED count, dropping, say, the photon and Z
s-channel of squark pairs into quarks where the gluon's exists.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "tests" / "constraints" / "data"

CASES: dict[str, list[str]] = {
    "sm": ["e+ e- > w+ w-", "e+ e- > mu+ mu-", "e+ e- > z h", "u u~ > g g", "t t~ > g g", "g g > t t~",
           "a a > w+ w-", "w+ w- > z z", "u d~ > w+ a", "e+ e- > e+ e-", "e- e- > e- e-", "t t~ > t t~",
           "b b~ > t t~", "t t~ > z h"],
    "MSSM_SLHA2": ["n1 n1 > b b~", "n1 n1 > e+ e-", "n1 n1 > w+ w-", "n1 n2 > z h01", "n1 x1+ > w+ a",
                   "n1 x1+ > u d~", "x1+ x1- > w+ w-", "go go > g g", "go go > u u~", "su1 su1~ > g g",
                   "su1 su1~ > u u~", "su1 su1 > u u", "n1 su1 > u g", "su1 g > u n1", "n1 n1 > h01 h01",
                   "n1 n1 > z z", "b b~ > z h01", "x1+ x1- > z h01", "u u~ > su1 su1~", "z z > h01 h01",
                   "w+ h01 > w+ h01", "n1 su1 > n1 su1", "su1 g > su1 g", "x1+ x1- > w+ h-", "n1 n2 > x1+ x1-"],
    "DMsimp_s_spin1": ["xd xd~ > y1 y1", "xd xd~ > t t~", "xd xd~ > b b~"],
}
ORDERS = {"sm": ("QCD", "QED"), "MSSM_SLHA2": ("QCD", "QED"), "DMsimp_s_spin1": ("QCD", "QED", "DMV")}
ROOTS_FACTORS = (1.2, 2.0, 5.0)
COS_THETA = (-0.7, 0.1, 0.6)

DRIVER = """      PROGRAM ADROIT_ME
      IMPLICIT NONE
      REAL*8 ZERO
      PARAMETER (ZERO=0D0)
      INCLUDE "coupl.inc"
      INCLUDE "nexternal.inc"
      REAL*8 P(0:3,NEXTERNAL), ME, PMASS(NEXTERNAL)
      INTEGER I, IOS
      CALL SETPARA('../../Cards/param_card.dat')
      INCLUDE "pmass.inc"
      WRITE(*,'(A,4E24.16)') 'MASSES ', (PMASS(I), I=1,NEXTERNAL)
      OPEN(7, FILE='PS.input', STATUS='OLD')
 10   CONTINUE
      DO I=1,NEXTERNAL
        READ(7,*,IOSTAT=IOS) P(0,I),P(1,I),P(2,I),P(3,I)
        IF (IOS.NE.0) GOTO 20
      ENDDO
      CALL SMATRIX(P,ME)
      WRITE(*,'(A,E24.16)') 'ME ', ME
      GOTO 10
 20   CLOSE(7)
      END
"""


def momenta(s: float, m: list[float], cos_theta: float) -> list[list[float]]:
    """p₁, p₂ along ±z and k₁, k₂ at angle θ in the x–z plane (the engine's frame)."""
    root = math.sqrt(s)

    def mom(a: float, b: float) -> float:
        return math.sqrt(max((s - (a + b) ** 2) * (s - (a - b) ** 2), 0.0)) / (2 * root)
    p, k = mom(m[0], m[1]), mom(m[2], m[3])
    e = [(s + m[0] ** 2 - m[1] ** 2) / (2 * root), (s + m[1] ** 2 - m[0] ** 2) / (2 * root),
         (s + m[2] ** 2 - m[3] ** 2) / (2 * root), (s + m[3] ** 2 - m[2] ** 2) / (2 * root)]
    sin = math.sqrt(1 - cos_theta ** 2)
    return [[e[0], 0, 0, p], [e[1], 0, 0, -p], [e[2], k * sin, 0, k * cos_theta], [e[3], -k * sin, 0, -k * cos_theta]]


def run_madgraph(model: str, processes: list[str], work: Path) -> Path:
    """MadGraph's standalone code for these processes, given by PDG codes (MadGraph renames some models'
    particles), one SubProcesses/P<n>_* folder each."""
    from adroit.constraints import maddm
    out = work / f"{model}_standalone"
    lines = ["set automatic_html_opening False", "set zerowidth_tchannel False", f"import model {model}-full"]
    orders = " ".join(f"{name}<=10" for name in ORDERS[model])
    lines += [("generate " if i == 0 else "add process ") + f"{proc} {orders} @{i + 1}" for i, proc in enumerate(processes)]
    lines += [f"output standalone {out} -f"]
    script = work / f"{model}.mg5"
    script.write_text("\n".join(lines) + "\n")
    done = subprocess.run([str(maddm.python()), str(maddm.mg5_dir() / "bin" / "mg5_aMC"), str(script)],
                          capture_output=True, text=True, cwd=work, timeout=3600)
    if done.returncode or not out.exists():
        raise RuntimeError(done.stdout[-3000:] + done.stderr[-3000:])
    return out


def evaluate(folder: Path, points: list[list[list[float]]]) -> tuple[list[float], list[float]]:
    """(the masses MadGraph uses, |M|² at each point) from one SubProcesses/P* folder."""
    subprocess.run(["make", "check"], cwd=folder, capture_output=True, check=True)
    (folder / "adroit_me.f").write_text(DRIVER)
    lib = folder.parents[1] / "lib"
    subprocess.run(["gfortran", "-w", "-fPIC", "-ffixed-line-length-132", "-o", "adroit_me", "adroit_me.f", "matrix.o",
                    f"-L{lib}", "-ldhelas", "-lmodel"], cwd=folder, capture_output=True, check=True)
    (folder / "PS.input").write_text("\n".join(" ".join(f"{x:.16e}" for x in leg) for point in points for leg in point)
                                     + "\n")
    done = subprocess.run(["./adroit_me"], cwd=folder, capture_output=True, text=True, check=True)
    masses = [float(x) for x in re.search(r"MASSES (.*)", done.stdout).group(1).split()]
    values = [float(x) for x in re.findall(r"ME\s+(\S+)", done.stdout)]
    return masses, values


def process_of(folder: Path) -> str:
    """The process a P* folder computes, from its matrix.f header."""
    text = (folder / "matrix.f").read_text()
    return re.search(r"Process: (.*?) WEIGHTED", text).group(1).strip()


WIDTHS = ("t", "x1+", "go", "su1", "n2", "w+", "z")


def madgraph_widths(card: Path, work: Path) -> dict:
    """MadGraph's two-body widths of ``WIDTHS`` in the MSSM at this card, by PDG code, and each partial width it
    dropped as below its QCD scale (parent PDG → [[daughters], width])."""
    from adroit.constraints import maddm
    script = work / "widths.mg5"
    script.write_text("set automatic_html_opening False\nimport model MSSM_SLHA2-full\n"
                      f"compute_widths {' '.join(WIDTHS)} --body_decay=2 --path={card} --output={work / 'widths.dat'}\n")
    done = subprocess.run([str(maddm.python()), str(maddm.mg5_dir() / "bin" / "mg5_aMC"), str(script)],
                          capture_output=True, text=True, cwd=work, timeout=3600)
    widths = {int(m.group(1)): float(m.group(2))
              for m in re.finditer(r"^DECAY\s+(-?\d+)\s+(\S+)", (work / "widths.dat").read_text(), re.M)}
    dropped: dict[int, list] = {}
    for m in re.finditer(r"partial width of particle (\S+) lower than QCD scale:(\S+)\. Set it to zero\. \(\[(.*?)\]\)",
                         done.stdout):
        dropped.setdefault(m.group(1), []).append([[int(x) for x in m.group(3).split(",")], float(m.group(2))])
    return {"widths": widths, "dropped": dropped}


def main(work: Path) -> None:
    from adroit.constraints import maddm, ufo_model
    DATA.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict] = {}
    for model, processes in CASES.items():
        names_only = ufo_model.dump(maddm.mg5_dir() / "models" / model, {})
        pdg = {p["name"]: p["pdg"] for p in names_only["particles"]}
        by_lower = {p["name"].lower(): p["name"] for p in names_only["particles"]}
        cases = [[by_lower[n.lower()] for n in proc.replace(">", "").split()] for proc in processes]
        codes = [f"{pdg[a]} {pdg[b]} > {pdg[c]} {pdg[d]}" for a, b, c, d in cases]
        standalone = run_madgraph(model, codes, work)
        # MadGraph reads its param card, written to 7 digits: the dump is evaluated at the same card, since a
        # rounding of 10⁻⁷ in a mixing matrix spoils gauge cancellations differently in the two codes.
        dump = ufo_model.dump(maddm.mg5_dir() / "models" / model, {}, standalone / "Cards" / "param_card.dat")
        (DATA / f"g3_ufo_{model}.json.gz").write_bytes(gzip.compress(json.dumps(dump).encode()))
        tree_model, _ = ufo_model.to_model(dump, full_colour=True)
        for folder in sorted((standalone / "SubProcesses").glob("P*")):
            number = int(re.match(r"P(\d+)_", folder.name).group(1))
            names = cases[number - 1]
            process = f"{names[0]} {names[1]} > {names[2]} {names[3]}"
            m = [abs(tree_model.particles[n].mass) for n in names]
            threshold = max(m[0] + m[1], m[2] + m[3], 100.0)
            grid = [(f * threshold, c) for f in ROOTS_FACTORS for c in COS_THETA]
            points = [momenta(r * r, m, c) for r, c in grid]
            masses, values = evaluate(folder, points)
            out[f"{model}: {process}"] = {"model": model, "names": names, "masses": masses,
                                          "points": [{"sqrt_s": r, "cos_theta": c, "me": v}
                                                     for (r, c), v in zip(grid, values)]}
            print(f"{model}: {process}: {len(values)} points")
    (DATA / "g3_madgraph.json").write_text(json.dumps(out, indent=1) + "\n")
    card = work / "MSSM_SLHA2_standalone" / "Cards" / "param_card.dat"
    (DATA / "g3_madgraph_widths.json").write_text(json.dumps(madgraph_widths(card, work), indent=1) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--work", type=Path, default=None, help="a folder without spaces for MadGraph's output")
    args = parser.parse_args()
    main(args.work or Path(tempfile.mkdtemp(prefix="adroit_g3_")))
