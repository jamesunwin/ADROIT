"""The portal library's part 4: every validation gate of docs/portal_library_4.md, section 6, run and tabulated.

``uv run python scripts/validate_portal_library_4.py`` (local computation: SModelS and MadGraph's tables in the tools
folder; about a minute). Prints a Markdown table and exits non-zero if a gate fails. The ranges were declared after
the development runs (docs, section 6): these gates guard against regressions and record the agreement.
"""

from __future__ import annotations

import math
import sys
import time
from contextlib import contextmanager

from adroit.constraints import lhc, loops, production, resummed_lines
from adroit.constraints import searches as s
from adroit.parameter_space import scan
from adroit.parameter_space import searches as ps
from adroit.parameter_space.classes import Point
from adroit.parameter_space.library import ENTRIES
from adroit.parameter_space.portals import multiplet
from adroit.parameter_space.portals.multiplet import ElectroweakMultiplet

GEV2_CM2 = 0.3894e-27
M_MU = 0.1056584
# the survey's independent tree-level + Sommerfeld line (MS-bar couplings) and Baumgart et al.'s NLL (H.E.S.S.'s curve)
WINO_TREE = {1000.0: 1.44e-26, 2900.0: 5.75e-26, 5000.0: 5.93e-27}
WINO_NLL = {1000.0: 7.95e-27, 2900.0: 3.23e-26, 5000.0: 2.09e-27}
Z_COUPLINGS = {"u": (0.0708456, -0.1851753), "d": (-0.1280105, 0.1851753)}


def _sigma(c: float, m: float, factor: float = 1.0) -> float:
    mu = m * loops.M_NUCLEON / (m + loops.M_NUCLEON)
    return factor * mu * mu * c * c / math.pi * GEV2_CM2


def loop_gates() -> list[tuple[str, float, float, float, str]]:
    out = []
    for m, m_phi, ref in ((300.0, 360.0, 3.65e-44), (1000.0, 1100.0, 5.0e-46)):
        f_p, _ = loops.coloured_partner_si(m, m_phi, 1.0, "u")
        out.append((f"coloured partner ({m:g}, {m_phi:g}): σ_p / Hisano et al.", _sigma(f_p, m, 4.0) / ref, 0.95, 1.05,
                    f"{ref:.3g} cm² (the survey, arXiv:1007.2601 eqs.)"))
    out.append(("lepton partner (100 GeV, μ = 1.1): F_A / Kopp et al. eq. 10",
                loops.anapole_moment(100.0, 100.0 * math.sqrt(1.1), 1.0, M_MU) / 5.53e-6, 0.98, 1.02, "5.53 × 10⁻⁶ GeV⁻²"))
    moment, radius = loops.dirac_moments(100.0, 110.0, 1.0, M_MU)
    out.append(("Dirac lepton partner: μ_χ / Kopp and Ibarra & Wild", moment / loops.E_CHARGE / 3.54e-5, 0.98, 1.02,
                "3.54 × 10⁻⁵ e GeV⁻¹"))
    out.append(("Dirac lepton partner: b_χ / Ibarra & Wild eq. 12", radius / loops.E_CHARGE / 5.16e-6, 0.98, 1.02,
                "5.16 × 10⁻⁶ e GeV⁻²"))
    for m, ref in ((100.0, 9.0e-48), (500.0, 2.7e-47)):
        c_p, _ = loops.two_hdma_si(m, 250.0, 600.0, 600.0, 600.0, 0.35, 1.0, 3.0, 3.0, 3.0, 1.0)
        out.append((f"2HDM+a Working Group benchmark, m_χ = {m:g}: σ_p / the survey", _sigma(c_p, m) / ref, 0.95, 1.05,
                    f"{ref:.2g} cm² (Abe, Fujiwara & Hisano's triangles)"))
    c_p, _ = loops.two_hdma_si(700.0, 100.0, 750.0, 750.0, 750.0, 0.35, 1.0, loops.M_H ** 2 / loops.V_EW ** 2, 0.0, 0.0,
                               1.0)
    out.append(("2HDM+a, Bell et al. Fig. 5 at 700 GeV: σ_p / the figure", _sigma(c_p, 700.0) / 1e-47, 0.5, 1.5,
                "≈ 10⁻⁴⁷ cm² read off the plot (Bell's compact formula: 6.2 × 10⁻⁴⁸)"))
    lam3 = loops.M_H ** 2 / loops.V_EW ** 2
    g = loops.two_hdma_couplings(100.0, 600.0, 600.0, 600.0, 0.1, 40.0, lam3, 0.0, 0.0)
    m, sn = 1000.0, 0.1
    cs = math.sqrt(1 - sn * sn)
    haa = g["haa"] * cs * cs * loops._b0_prime(100.0, m)
    total = haa + g["hAA"] * sn * sn * loops._b0_prime(600.0, m) \
        + 2 * g["haA"] * sn * cs * loops._b1_difference(600.0, 100.0, m) / (600.0 ** 2 - 100.0 ** 2)
    out.append(("2HDM+a: triangles / the h a a diagram (Abe et al. Sec. 4.1)", total / haa, 0.55, 0.65, "“0.6 times”"))
    return out


@contextmanager
def _reference_curves():
    """The library's lines from the H.E.S.S. reference curves, DMγSpec's table set aside."""
    saved = resummed_lines.available
    resummed_lines.available = lambda: False
    try:
        yield
    finally:
        resummed_lines.available = saved


def line_gates() -> list[tuple[str, float, float, float, str]]:
    out = []
    wino = ElectroweakMultiplet(name="w", multiplet="wino")
    for m, ref in WINO_TREE.items():
        out.append((f"wino {m / 1e3:g} TeV: tree + Sommerfeld line / the survey's", multiplet.wino_line(m, 0.165) / ref,
                    0.85, 1.15, f"{ref:.3g} cm³/s"))
    # These gates validate the H.E.S.S. reference curves, the library's default before D21 (revised, 2026-10-15) and
    # now DMγSpec's cross-check and fallback: they read that curve, with DMγSpec switched off (G12's release checks:
    # they had read DMγSpec's rate, which has no separate Zγ). DMγSpec's own agreement is G8's (docs/g8_today.md).
    for m, ref in WINO_NLL.items():
        rates = wino.hess_reference_line(Point(m_chi=m, m_med=1.0, g_q=0.0))
        out.append((f"wino {m / 1e3:g} TeV: σv_line (× Sudakov) / Baumgart et al. NLL",
                    (rates["gamma"] + 0.5 * rates["Zgamma"]) / ref, 0.75, 1.35, f"{ref:.3g} cm³/s (H.E.S.S. 2026's curve)"))
    with _reference_curves():
        thermal = ps.lines(wino, Point(m_chi=2900.0, m_med=1.0, g_q=0.0), True)
    out.append(("thermal wino: r(H.E.S.S. 2026, cored profile) / the survey's ×8.5", thermal.ratio / 8.5, 0.85, 1.15,
                "‘excluded for any of the adopted DM profiles’"))
    hino = ps.lines(ElectroweakMultiplet(name="h", multiplet="higgsino"), Point(m_chi=1100.0, m_med=1.0, g_q=0.0), True)
    out.append(("thermal higgsino: r of the lines (not excluded)", hino.ratio, 0.0, 1.0, "σv_line ≈ 10⁻²⁸ cm³/s"))
    for m, ref in ((1.0, 0.18431), (3.162, 0.16233)):
        out.append((f"CMB f_eff(μ⁺μ⁻) at {m:g} GeV / Slatyer's notebook", s.muon_f_eff(m) / ref, 0.97, 1.03,
                    f"{ref} (arXiv:1506.03811)"))
    return out


def production_gates() -> list[tuple[str, float, float, float, str]]:
    sigma = 0.0
    for q, kind in (("u", "u"), ("c", "u"), ("d", "d"), ("s", "d"), ("b", "d")):
        v, a = Z_COUPLINGS[kind]
        sigma += (v * v + a * a) * production.sigma_pb(f"zprime_spin1_{q}_13TeV_LO", 91.1876)
    out = [("the Z from the Z′ tables: σ_LO × BR(ℓℓ) / FEWZ's NNLO", sigma * 0.03366 / 1928.0, 0.70, 0.80,
            "1928 pb (CMS arXiv:2103.02708); 1/K_NNLO ≈ 0.75"),
           ("heavy-Higgs gg → H at 125 GeV / YR4's N3LO", production.heavy_higgs_pb(125.0) / 48.58, 0.80, 1.0,
            "48.58 pb (NNLO+NNLL quark loop expected ≈ 10% lower)")]
    out += _two_hdma_production()
    out.append(_idm_pairs())
    out.append(_cms_agreement())
    return out


def _two_hdma_production() -> list[tuple[str, float, float, float, str]]:
    """gg → a, A, H from the unit tables (type-II couplings, interference) against MadGraph on the 2HDM+a model."""
    import json

    runs = json.loads((production.folder() / "validation_2hdma.json").read_text())["items"]
    s_t = 0.35
    c_t = math.sqrt(1 - s_t * s_t)
    couplings = {"g g > h4": ("P", s_t, s_t), "g g > h3": ("P", c_t, c_t), "g g > h2": ("S", -1.0, 1.0)}
    out = []
    for run in runs:
        cp, g_t, g_b = couplings[run["process"]]
        mass = run["mass_gev"]
        ours = ps.gluon_fusion_pb(cp, g_t, g_b, mass) / production.gluon_fusion_k(mass)
        out.append((f"2HDM+a {run['process']} ({mass:g} GeV): σ_LO / MadGraph on Pseudoscalar_2HDM",
                    ours / run["sigma_MG5_Pseudoscalar_2HDM_pb"], 0.95, 1.05, f"{run['sigma_MG5_Pseudoscalar_2HDM_pb']} pb"))
    return out


def _idm_pairs() -> tuple[str, float, float, float, str]:
    """The inert doublet's pair σ from the equal-mass tables (× 2√(m₁m₂)/(m₁ + m₂)) against MadGraph's split runs."""
    import json

    worst = 0.0
    for pair, (i, j) in (("H0A0", (0, 1)), ("HpmH0", (2, 0)), ("HpmA0", (2, 1)), ("HpHm", (2, 2))):
        runs = json.loads((production.folder() / f"idm_{pair}_split_examples_13TeV_LO.json").read_text())["data"]
        for row in runs:
            m1, m2 = row[i], row[j]
            estimate = production.sigma_pb(f"idm_{pair}_equal_masses_13TeV_LO", 0.5 * (m1 + m2)) \
                * 2.0 * math.sqrt(m1 * m2) / (m1 + m2)
            worst = max(worst, abs(estimate / row[3] - 1.0))
    return ("inert doublet pairs: worst |σ(mean-mass rule)/σ(MadGraph) − 1| over 32 split runs", worst, 0.0, 0.05,
            "MadGraph's own runs, mass ratios to 8.3")


def _cms_agreement() -> tuple[str, float, float, float, str]:
    """SModelS with MadGraph's σ against CMS's own V1/A1 summary, where both decide."""
    by = {e.id: e for e in ENTRIES}
    points = [(by[e].model_class, by[e].point.model_copy(update={"m_chi": mc, "m_med": mm}))
              for e in ("dmwg_V1", "dmwg_A1") for mc in (100.0, 1000.0) for mm in (500.0, 1000.0, 2000.0, 3000.0,
                                                                                4000.0, 5000.0)]
    spectra = [ps.lhc_spectrum(c, p) for c, p in points]
    results = iter(lhc.run([sp[0] for sp in spectra]))
    agree = total = 0
    for (cls, p), _ in zip(points, spectra):
        r, cms = next(results).get("r_max"), scan._collider(cls, p, True)   # a reference, signed or not
        if r is not None and cms is not None and cms.excluded is not None:
            total += 1
            agree += (r >= 1.0) == cms.excluded
    return (f"SModelS × MadGraph against CMS's V1/A1 contour ({total} points where both decide)", agree / total, 1.0,
            1.0, "cms-2405.13778 (the experiment's own interpretation)")


def main() -> int:
    """Run every gate, print the table, and return the exit code: 0 when all pass, 1 otherwise."""
    from adroit.core.receipts import exit_code, validation_table
    start = time.time()
    rows = loop_gates() + line_gates() + production_gates()
    table, failed = validation_table(rows)
    print(table)
    print(f"\n{len(rows) - failed} of {len(rows)} gates pass ({time.time() - start:.0f} s)")
    return exit_code(not failed)


if __name__ == "__main__":
    sys.exit(main())
