"""Matched MadDM references for the 2HDM+a gates of docs/portal_library_2.md (re-declared 2026-10-10).

MadDM's g* is an ideal gas of every particle in its species list, ``include/model_info.txt``. For part 2's
2HDM+a process folders that list also holds the ghosts (ghA, ghZ, ghW⁺, ghW⁻, ghG), MadDM's direct-detection
auxiliary fields (sdmm, vdmm) and the model's particles at the default card's masses (the dark matter at
1 GeV). For each of the four folders in ``<tools>/maddm-work/p2hdm/`` this script:

1. copies the folder to ``<tools>/maddm-work/p2hdm_matched/`` and re-runs MadDM's compiled relic program
   unchanged, which must reproduce part 2's stored Ωh² (the copy changes nothing else);
2. replaces the species list with the physical one: MadDM's 17 Standard Model entries, the dark matter at m_χ,
   H, A and H± at M_A, and a at M_a, at the masses of the folder's own param_card;
3. re-runs the program and records both Ωh².

    uv run python scripts/maddm_matched_gstar.py

Writes ``docs/portal_library_2/maddm_matched_reference.json``. Needs the process folders and MadDM's build in
the tools folder; runs no paid service.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adroit.core.config import get_settings  # noqa: E402

POINTS = [(600, 250, 150), (600, 250, 300), (1000, 400, 170), (1000, 400, 300)]   # (M_A, M_a, m_χ), part 2
OUT = ROOT / "docs" / "portal_library_2" / "maddm_matched_reference.json"
SM_ENTRIES = 17
UNPHYSICAL = 7          # ghA, ghZ, ghW+, ghW-, ghG, sdmm, vdmm: the entries the physical list drops


def masses(folder: Path) -> dict[int, float]:
    """BLOCK MASS of the folder's param_card, by PDG code."""
    text = (folder / "Cards" / "param_card.dat").read_text()
    block = re.search(r"BLOCK MASS[^\n]*\n(.*?)\n\s*(?:BLOCK|DECAY|#\s*$)", text, re.S | re.I).group(1)
    return {int(m.group(1)): float(m.group(2)) for m in re.finditer(r"^\s*(\d+)\s+([-+0-9.eE]+)", block, re.M)}


def physical_list(original: str, mass: dict[int, float]) -> str:
    """The species list with only the physical particles, at the run's masses."""
    lines = original.strip().splitlines()
    count, sm, bsm = int(lines[0]), lines[1:1 + SM_ENTRIES], lines[1 + SM_ENTRIES:]
    if count != len(lines) - 1 or len(bsm) != 5 + UNPHYSICAL:
        raise ValueError(f"unexpected species list ({count} entries, {len(bsm)} beyond the Standard Model)")
    new = [f"{mass[52]}  4.0  1",               # the dark matter Xd (Dirac): fermion, 4 states
           f"{mass[37]}  2.0  0",               # H±
           f"{mass[35]}  1.0  0",               # H
           f"{mass[36]}  1.0  0",               # A
           f"{mass[55]}  1.0  0"]               # a
    return "\n".join([str(SM_ENTRIES + len(new)), *sm, *new]) + "\n"


def relic(folder: Path, run: str) -> float:
    """Run MadDM's relic program in ``folder``; Ωh² from its output."""
    (folder / "output" / run).mkdir(parents=True, exist_ok=True)
    subprocess.run(["./maddm.x", f"output/{run}/maddm.out"], cwd=folder, check=True, capture_output=True,
                   timeout=1800)
    text = (folder / "output" / run / "maddm.out").read_text()
    return float(re.search(r"Omegah\^2:\s*([-+0-9.eE]+)", text).group(1))


def stored(folder: Path) -> float:
    """Part 2's stored Ωh² for the folder."""
    text = (folder / "output" / "run_01" / "maddm.out").read_text()
    return float(re.search(r"Omegah\^2:\s*([-+0-9.eE]+)", text).group(1))


def one(heavy: int, light: int, dm: int, work: Path) -> dict:
    """The original and the matched Ωh² at one point."""
    name = f"p{heavy}_{light}_{dm}"
    source, copy = work / "p2hdm" / name, work / "p2hdm_matched" / name
    shutil.rmtree(copy, ignore_errors=True)
    shutil.copytree(source, copy, symlinks=True)
    mass = masses(copy)
    if (mass[52], mass[55], mass[35], mass[36], mass[37]) != (dm, light, heavy, heavy, heavy):
        raise ValueError(f"{name}: param_card masses {mass} are not the point's")
    original_list = (copy / "include" / "model_info.txt").read_text()
    reproduced = relic(copy, "unchanged")
    if abs(reproduced / stored(source) - 1.0) > 1e-9:
        raise ValueError(f"{name}: the copy gives {reproduced}, not part 2's {stored(source)}")
    matched_list = physical_list(original_list, mass)
    (copy / "include" / "model_info.txt").write_text(matched_list)
    matched = relic(copy, "matched_gstar")
    return {"point": {"M_A": heavy, "M_a": light, "m_chi": dm}, "folder": str(copy), "omega_h2_original": reproduced,
            "omega_h2_matched": matched, "matched_over_original": matched / reproduced,
            "species_original": original_list.strip().splitlines(), "species_matched": matched_list.strip().splitlines()}


def main() -> int:
    """Compute the four matched references and write their record."""
    work = get_settings().tools_dir / "maddm-work"
    rows = [one(*p, work) for p in POINTS]
    record = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "maddm": "3.3",
              "declaration": "docs/portal_library_2.md, re-declaration of 2026-10-10", "points": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=1) + "\n")
    for r in rows:
        print(f"{r['point']}: original {r['omega_h2_original']:.4g}, physical g* {r['omega_h2_matched']:.4g} "
              f"(× {r['matched_over_original']:.4f})")
    print(f"written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
