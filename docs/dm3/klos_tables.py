"""Transcribe the structure-factor fits of Klos et al. from the paper's TeX source.

The fits are the tables of Appendix D of arXiv:1304.7684v4 (the version whose
appendix typos are corrected): S_ij(u) = exp(−u) Σ_n c_ij,n u^n with
u = p²b²/2, including one- and two-body currents, with the lower and upper
edges of the two-body band fitted separately. The script reads the tables
from the source rather than by hand, and writes
adroit/physics/data/klos2013_structure_factors.yaml.

    curl -L -o klos.tgz https://arxiv.org/e-print/1304.7684v4 && tar xzf klos.tgz
    uv run python docs/dm3/klos_tables.py WIMP_SD_corrected.tex
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "adroit" / "physics" / "data" / "klos2013_structure_factors.yaml"
UPPER = ["S11_min", "S11_max", "S01_min", "S01_max"]
LOWER = ["Sp_min", "Sp_max", "Sn_min", "Sn_max"]


def number(cell: str) -> float:
    """A table entry such as '$-1.32501 \\times 10^{-4}$' as a float."""
    cell = cell.replace("$", "").replace("\\\\", "").strip()
    match = re.fullmatch(r"(-?[\d.]+)\s*(?:\\times\s*10\^\{(-?\d+)\})?", cell)
    if match is None:
        raise ValueError(f"cannot read {cell!r}")
    return float(f"{float(match.group(1)) * 10.0 ** int(match.group(2) or 0):.6g}")


def tables(tex: str) -> dict[str, dict]:
    """Every isotope's fits, keyed by isotope name ('Ge73')."""
    appendix = tex[tex.index("\\section{Fits of the structure factors}"):tex.index("\\begin{thebibliography}")]
    out: dict[str, dict] = {}
    blocks = re.split(r"\\multicolumn\{6\}\{c\}\{\$\^\{(\d+)\}\$([A-Za-z]+)", appendix)[1:]
    for mass, symbol, body in zip(blocks[0::3], blocks[1::3], blocks[2::3]):
        b_fm = float(re.search(r"b=([\d.]+)", body.replace(" ", "")).group(1))
        columns: dict[str, list[float]] = {key: [] for key in ["S00", *UPPER, *LOWER]}
        lower = False
        for line in body.splitlines():
            if "S_{p}" in line:
                lower = True
            cells = line.split("&")
            if not re.match(r"\s*\$(1|u(\^\{?\d+\}?)?)\$\s*$", cells[0]):
                continue
            values = [number(c) for c in cells[1:] if c.strip()]
            names = LOWER if lower else ["S00", *UPPER]
            for name, value in zip(names, values, strict=True):
                columns[name].append(value)
        out[f"{symbol}{mass}"] = {"b_fm": b_fm, "coefficients": columns}
    return out


def main() -> None:
    source = Path(sys.argv[1]).read_text()
    data = {
        "source": "Klos, Menendez, Gazit, Schwenk, Phys. Rev. D 88, 083516 (2013); "
                  "arXiv:1304.7684v4, Appendix D (Tables IV-VIII), one- plus two-body currents",
        "form": "S_ij(u) = exp(-u) * sum_n c_ij,n u^n, u = p^2 b^2 / 2",
        "notes": [
            "S11 and S01 are fitted at the two edges of the two-body-current band; S11 and "
            "|S01| grow together, so an edge pairs S11_min with the S01 of smaller magnitude. "
            "Combined so, S00 + S01 + S11 and S00 - S01 + S11 reproduce the separate Sp and "
            "Sn fits to 0.5% of the larger of them, for every isotope.",
            "The b printed for 19F (1.8032 fm) equals that printed for 23Na; the paper's "
            "formula gives 1.762 fm for A = 19 and agrees with every other b to 0.1%. "
            "The printed value is kept, as the fit's variable u is defined by it.",
            "The fits cover the range of the paper's figures, u up to 5.",
        ],
        "isotopes": tables(source),
    }
    OUT.write_text(yaml.safe_dump(data, sort_keys=False, width=100))
    print(f"wrote {OUT.relative_to(ROOT)}: " + ", ".join(data["isotopes"]))


if __name__ == "__main__":
    main()
