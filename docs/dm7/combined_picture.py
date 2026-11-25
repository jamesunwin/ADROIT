"""The combined picture of the four spin-1 benchmarks, beside CMS's summary (DM7).

For V1, A1, A2 (the gate's models) and V2, in the plane of mediator mass and
dark matter mass:
- **collider** (curated records): CMS's observed excluded regions;
- **relic density** (computed): the system's Ωh² = 0.12 contour, beside the
  one CMS draws;
- **direct detection** (computed): excluded below m_med,min(m_DM), from the
  strongest validated limit of the system's own modules (SI for the vector
  models, SD on protons for the axial ones; DM3's results store). Since
  σ ∝ m_med⁻⁴, m_med,min = m_ref (σ(m_ref)/σ_lim)^{1/4};
- **capture in the Sun** (computed; IceCube's SD record): excluded where the
  capture rate, times the equilibrium fraction from the model's own ⟨σv⟩,
  exceeds the rate IceCube's limit allows for the model's channel. The
  capture rate goes as m_med⁻⁴ too, so it is computed once per m_DM;
- **gamma rays from dwarf galaxies** (computed; Fermi-LAT's record).

The records were verified by the owner on 2026-10-01, after this was first run.
Run from the repository root (about 10 minutes; two workers, low priority):

    nice -n 10 uv run python docs/dm7/combined_picture.py

Writes docs/dm7/combined_picture.json and combined_picture.png.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.constraints import annihilation, capture, database, spin1, verdicts  # noqa: E402
from adroit.core.dm_state import DarkMatterParticle  # noqa: E402
from adroit.experiments import status  # noqa: E402

HERE = Path(__file__).parent
MODELS = ("V1", "A1", "A2", "V2")
M_MED = np.geomspace(40.0, 1e4, 44)
M_DM = np.linspace(10.0, 2000.0, 44)
M_REF = 1000.0


def dd_limit(kind: str) -> tuple[np.ndarray, np.ndarray]:
    """The strongest validated reproduced limit over the modules, from DM3's results store."""
    store = json.loads((ROOT / "docs/dm3/validation_results.json").read_text())["comparisons"]
    latest = {}
    for entry in store:
        r = entry["result"]
        if r.get("kind") == kind and entry.get("rule"):
            latest[r["experiment"]] = r
    grid, best = np.geomspace(1.0, 1e4, 400), np.full(400, np.inf)
    for name, r in latest.items():
        span = status.validated_range(name, kind)
        if span is None:
            continue
        m, s = np.array(r["masses_gev"]), np.array(r["reproduced_cm2"])
        ok = (m >= span[0] * (1 - 1e-4)) & (m <= span[1] * (1 + 1e-4)) & np.isfinite(s) & (s > 0)
        if ok.sum() < 2:
            continue
        inside = (grid >= m[ok].min()) & (grid <= m[ok].max())
        values = np.exp(np.interp(np.log(grid), np.log(m[ok]), np.log(s[ok])))
        best = np.where(inside, np.minimum(best, values), best)
    return grid, best


def point(task: tuple[str, float, float, float]) -> dict:
    """Ωh², Fermi's ratio, the equilibrium fraction and IceCube's verdict at one point."""
    name, m_med, m_dm, capture_at_ref = task
    model = spin1.benchmark(name, m_med)
    omega = annihilation.omega_h2(model, m_dm)
    candidate = verdicts.Candidate(label=name, particle=DarkMatterParticle(mass_gev=m_dm),
                                   interaction=spin1.interaction(model, m_dm), completion=model)
    fermi = verdicts.indirect(candidate, database.record("fermi-1503.02641-dsph"))
    sun = annihilation.sigma_v_today(model, m_dm, verdicts.SUN_SPEED)
    rate = capture_at_ref * (M_REF / m_med) ** 4
    fraction = capture.equilibrium_fraction(rate, sum(sun.values()), m_dm)
    hard = sum(v for k, v in sun.items() if k in ("t", "tau", "Z'Z'")) / max(sum(sun.values()), 1e-300)
    limits = database.data("icecube-1612.05949-sd")["limits"]["SD_proton"]["limits_cm2"]
    sigma = database.interpolate_limit(limits["WW" if hard > 0.9 else "bb"], m_dm)
    allowed = (capture.capture_rate(DarkMatterParticle(mass_gev=m_dm),
                                    verdicts._reference("SD_proton", sigma, m_dm)) if sigma else None)
    return {"model": name, "m_med": m_med, "m_dm": m_dm, "omega_h2": omega,
            "fermi_ratio": None if fermi.excluded is None else float(fermi.note.split("= ")[1].split(";")[0]),
            "icecube_excluded": None if allowed is None else bool(rate * fraction > allowed)}


def reference_capture(name: str, m_dm: float) -> float:
    model = spin1.benchmark(name, M_REF)
    return capture.capture_rate(DarkMatterParticle(mass_gev=m_dm), spin1.interaction(model, m_dm))


def main() -> None:
    """Compute the grids, then draw."""
    tasks = []
    for name in MODELS:
        for m_dm in M_DM:
            c_ref = reference_capture(name, float(m_dm))
            tasks += [(name, float(m_med), float(m_dm), c_ref) for m_med in M_MED]
    with ProcessPoolExecutor(max_workers=2) as pool:
        grid = list(pool.map(point, tasks, chunksize=8))
    dd = {kind: [a.tolist() for a in dd_limit(kind)] for kind in ("SI", "SD-proton")}
    (HERE / "combined_picture.json").write_text(json.dumps({"grid": grid, "dd_limits": dd}, indent=0))
    draw(grid, dd)


def dd_boundary(name: str, dd: dict) -> tuple[np.ndarray, np.ndarray]:
    """m_med,min(m_DM) from the direct-detection envelope."""
    kind = "SI" if spin1.BENCHMARKS[name][0] is spin1.Spin1Kind.vector else "SD-proton"
    masses, limits = (np.array(a) for a in dd[kind])
    model = spin1.benchmark(name, M_REF)
    m_min = [M_REF * (spin1.nucleon_cross_section_cm2(model, float(m)) / s) ** 0.25
             if np.isfinite(s) else np.nan for m, s in zip(M_DM, np.interp(M_DM, masses, limits))]
    return M_DM, np.array(m_min)


def draw(grid: list[dict], dd: dict) -> None:
    """Four panels: every constraint class, and CMS's own relic contour dashed."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    record = database.data("cms-2405.13778-V1")
    fig, axes = plt.subplots(2, 2, figsize=(12, 9.5))
    for ax, name in zip(axes.flat, MODELS):
        rows = [r for r in grid if r["model"] == name]
        omega = np.array([r["omega_h2"] for r in rows]).reshape(len(M_DM), len(M_MED))
        ice = np.array([np.nan if r["icecube_excluded"] is None else float(r["icecube_excluded"])
                        for r in rows]).reshape(omega.shape)
        fermi = np.array([np.nan if r["fermi_ratio"] is None else r["fermi_ratio"]
                          for r in rows]).reshape(omega.shape)
        panel = record["panels"][name]
        for polys in verdicts.excluded_regions(panel).values():
            for poly in polys:
                v = poly.vertices
                ax.fill(10 ** v[:, 0], v[:, 1], color="0.8", alpha=0.6, lw=0)
        ax.contourf(M_MED, M_DM, ice, levels=[0.5, 1.5], colors=["tab:orange"], alpha=0.35)
        ax.contourf(M_MED, M_DM, fermi, levels=[1.0, 1e9], colors=["tab:green"], alpha=0.35)
        x, y = dd_boundary(name, dd)
        ax.fill_betweenx(y=x, x1=40.0, x2=np.nan_to_num(y, nan=40.0), color="tab:blue", alpha=0.25)
        ax.contour(M_MED, M_DM, omega, levels=[0.12], colors="black", linewidths=1.6)
        for line in panel["relic"]:
            pts = np.array(line)
            ax.plot(pts[:, 0], pts[:, 1], color="black", ls="--", lw=1.0)
        ax.set(xscale="log", xlim=(40, 1e4), ylim=(0, 2000), title=name,
               xlabel="mediator mass (GeV)", ylabel="dark matter mass (GeV)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c, alpha=a) for c, a in
               (("0.8", 0.6), ("tab:blue", 0.25), ("tab:orange", 0.35), ("tab:green", 0.35))]
    handles += [plt.Line2D([], [], color="black", lw=1.6), plt.Line2D([], [], color="black", ls="--")]
    fig.legend(handles, ["CMS collider (record)", "direct detection (system's modules)",
                         "IceCube, capture in the Sun (tier 2)", "Fermi-LAT dwarfs (tier 3)",
                         "Ωh² = 0.12 (system)", "Ωh² = 0.12 (CMS)"], loc="lower center", ncol=3, fontsize=8)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(HERE / "combined_picture.png", dpi=110)


if __name__ == "__main__":
    main()
