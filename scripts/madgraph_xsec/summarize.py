"""Print representative numbers from all tables (for the report)."""

from __future__ import annotations

import json
import statistics

from mgxsec_common import OUT_DIR
from xsec_lookup import Table


def med_seconds(name: str, col: str = "seconds") -> float:
    """Median wall time per point of a table."""
    d = json.loads((OUT_DIR / name).read_text())
    i = d["columns"].index(col)
    return statistics.median(r[i] for r in d["data"])


def main() -> None:
    """Print summary tables."""
    print("== Z' (pb), unit coupling")
    ms = (50, 100, 200, 500, 1000, 2000, 3000, 4000, 5000, 6000)
    print("M:", ms)
    for n in ("vector", "axial", "u", "d", "s", "c", "b", "uptype", "downtype", "BminusL"):
        t = Table(f"zprime_spin1_{n}_13TeV_LO.json")
        print(f"{n:9s}", "  ".join(f"{t(m):.3e}" for m in ms))
    print("median s/point vector, u:", med_seconds("zprime_spin1_vector_13TeV_LO.json"),
          med_seconds("zprime_spin1_u_13TeV_LO.json"))
    print("== gg -> S (pb), unit Yukawa multipliers")
    ms = (10, 20, 50, 125, 200, 300, 350, 400, 500, 750, 1000, 1500, 2000, 3000)
    print("M:", ms)
    for n in ("S_tb", "S_t", "S_b", "P_tb", "P_t", "P_b"):
        t = Table(f"ggS_spin0_{n}_13TeV_LO.json")
        print(f"{n:5s}", "  ".join(f"{t(m):.3e}" for m in ms))
    print("median s/point S_tb:", med_seconds("ggS_spin0_S_tb_13TeV_LO.json"))
    kf = json.loads((OUT_DIR / "ggS_kfactors_13TeV.json").read_text())
    c = kf["columns"]
    for m in (125, 200, 300, 400, 500, 750, 1000, 1500, 2000, 3000):
        kl = Table("ggS_kfactors_13TeV.json", sigma_col=c.index("K_loop"))(m)
        ke = Table("ggS_kfactors_13TeV.json", sigma_col=c.index("K_EFT"))(m)
        print(f"K at {m}: K_loop = {kl:.3f}  K_EFT = {ke:.3f}")
    print("== inert doublet (pb), equal masses")
    ms = (50, 65, 80, 100, 150, 200, 300, 500, 750, 1000)
    print("M:", ms)
    for ch in ("H0A0", "HpmH0", "HpmA0", "HpHm"):
        f = OUT_DIR / f"idm_{ch}_equal_masses_13TeV_LO.json"
        if f.exists():
            t = Table(f.name, sigma_col=3)
            print(f"{ch:6s}", "  ".join(f"{t(m):.3e}" for m in ms), " median s:",
                  med_seconds(f.name))


if __name__ == "__main__":
    main()
