"""Resonance searches beyond SModelS's maps (the portal library, part 5; docs/portal_library_5.md).

- **Dijets below 1.5 TeV and broad dijets.** CMS's limit on a leptophobic Z′'s universal quark
  coupling g_q′ (arXiv:1806.00843, 0.6–3.7 TeV, data scouting below 1.6 TeV) for Γ/m ≤ 10%: a Z′ with
  σ and BR(jj) acts as g_eff² = σ BR(jj)/(σ₁ BR_ref(jj)), with σ₁ the unit-coupling σ and BR_ref the
  quark-only Z′'s; r = (g_eff/g_lim)². Broader Z′ (Γ/m 10–12%) from 1.5 TeV: ATLAS's limits on Gaussian
  signals of relative width 0–15% (arXiv:1910.08447), with the acceptance of ATLAS's DM Z′ of the same width;
  12% is ATLAS's widest DM Z′, and wider is undecided (``ATLAS_GAUSSIAN_MAX``; docs/widths.md). The decision
  follows ATLAS's recipe for its Gaussian limits (2026-10-17, the external audit's item 18): the Breit–Wigner's
  long tails removed by keeping 0.8–1.2 M, against the 10% Gaussian (``TRUNCATION``, ``RECIPE_GAUSSIAN``). The
  Breit–Wigner matched at its full width at half maximum, σ_G = Γ/2.355, excluding alone gives a flag: against
  ATLAS's own Breit–Wigner Z′ limits it is too strong by a factor 1.6–1.7, and the recipe weaker by about 2–3.5,
  so the decision is good up to an O(1) factor, on the conservative side (the audit proposals of 2026-10-16 §4;
  scripts/validate_dijet_breit_wigner.py).
- **tt̄ resonances** of a scalar or pseudoscalar coupling to the top (CMS arXiv:1908.01115, 400–750 GeV,
  interference with QCD tt̄ included): the coupling modifier g_Φtt (the top coupling in units of the
  Standard Model's m_t/v) against its excluded bands at relative widths 0.5–25%. Between two tabulated
  widths a point is excluded only if both exclude it and allowed only if both allow it. CMS's signal is one
  state produced through the top loop: a state whose b-quark loop changes gg → Φ by more than 10%, or that
  another state of its CP overlaps within their widths, is undecided (``TOP_LOOP_TOLERANCE``).
- **The 2HDM+a's mono-Higgs** (ATLAS arXiv:2108.13391): ATLAS's upper limit σ₉₅(m_A, m_a) on the
  gluon-fused signal, which fixes the kinematics, against σ(gg → A) BR(A → a h) BR(a → χχ̄) at any
  (sin θ, tan β), interpolated over ATLAS's grid. Leading order, as ATLAS's benchmark is. Only for a
  narrow A (Γ/m ≤ 10%). There our resonant σ is 0.419–1.240 of ATLAS's full benchmark σ over its 50
  narrow-A nodes (median 0.89; lower at small m_a, where non-resonant diagrams add, and above 1 at 14
  nodes). The recast is therefore not conservative either way (corrected 2026-10-10, R4): a point is
  excluded only if r exceeds 1.240, allowed only if r is below 0.419, and undecided between
  (``RESONANT_OVER_FULL``). That band holds at ATLAS's benchmark couplings (sin θ = 0.35, tan β = 1,
  λ₃ = λ_P1 = λ_P2 = 3). Beyond them (2026-10-12) MadGraph's full loop-induced gg → h a, over sin θ 0.2–0.7 and
  tan β 1–5 at four narrow-A nodes (m_A 600–1200 GeV, m_a 150–300 GeV), shifts our ratio to the full σ by a
  factor s relative to the benchmark; inside that box the band is widened by the range of s at the point's
  (sin θ, tan β) (``SHIFTS``, ``shift_range``; scripts/madgraph_xsec/monoh_calibration.py, docs/monoh/README.md).
  Outside the benchmark and the box the point is undecided. For a broader A the non-resonant production dominates and the
  point is undecided.
- **The 2HDM+a's mono-Z** (ATLAS arXiv:2111.08372), which publishes only contours (sin θ = 0.35, 0.7):
  at fixed (m_a, m_H) the signal σ(gg → H) BR(H → a Z) BR(a → χχ̄) is compared with the contour's
  reference model. At the contour's own benchmark couplings (tan β = 1, λ's = 3), inside it with at least its
  rate: excluded; outside with at most its rate: allowed; otherwise undecided. No interpolation in the rate is
  assumed. Beyond the benchmarks (2026-10-12) MadGraph's full gg → Z a times BR(a → χχ̄), over sin θ 0.2–0.7 and
  tan β 1–5 at four narrow-H nodes (m_H 500–800 GeV, m_a 150–300 GeV), shifts our ratio to the full rate by s
  relative to each contour's benchmark, within 0.959–1.021 (``SHIFTS_Z``; scripts/madgraph_xsec/monoz_calibration.py,
  docs/monoz/README.md). Inside that box the thresholds become the range of s at the point: excluded inside a
  contour at ≥ max s times its rate, allowed outside at ≤ min s times it. Elsewhere the point is undecided.
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

from adroit.constraints import audit_notes
from adroit.constraints import searches as s
from adroit.constraints.searches import Outcome
from adroit.parameter_space.classes import Point, ScalarClass

DIJET, TTBAR = "LHC dijet resonances (CMS, ATLAS)", "LHC tt̄ resonances (CMS)"
ATLAS_GAUSSIAN = "atlas-1910.08447-dijet-gaussian"
# searches whose evaluator attaches the audit notes of the record that decided (the dijet's two records decide apart)
OWN_NOTES = {DIJET}
MONOH, MONOZ = "2HDM+a mono-Higgs (ATLAS)", "2HDM+a mono-Z (ATLAS)"
NARROW_DIJET = 0.10               # Γ/m up to which CMS's narrow-resonance coupling limit is used: "approximately valid"
                                  # below 10% for masses under ~4 TeV (arXiv:1806.00843 §4.4); its record ends at 3.7 TeV
# ATLAS's widest DM Z′ (g_q = 0.5, Γ/m = 12%, "nearly the maximum width to which this search is sensitive",
# arXiv:1910.08447 §3), the widest for which it gives the acceptance A: the Gaussian limits are used up to it.
ATLAS_GAUSSIAN_MAX = 0.12
# ATLAS's recipe for its Gaussian limits (arXiv:1407.1376 App. A.1, to which arXiv:1703.09127 §6 refers for these
# particle-level limits): "any long tails ... should be removed", keeping 0.8–1.2 M, and the Gaussian σ_G = 0.08 M
# (±2σ_G inside the window) "rounded up to be conservative": the 10% limit. The share inside the window is of the
# events passing the inclusive selection's m_jj > 1.1 TeV (arXiv:1910.08447 Table 1).
TRUNCATION = (0.8, 1.2)
RECIPE_GAUSSIAN = 10.0            # σ_G/m (%)
MJJ_MIN = 1100.0                  # GeV
# CMS's tt̄ limits are for one state produced through the top-quark loop; the interference with QCD tt̄ "depends on the
# specific signal model, and can be significantly modified by new particles appearing in the loop" (arXiv:1908.01115
# §1). A state is compared only if the b-quark loop changes its gg → Φ by at most this fraction, and no other state of
# the same CP overlaps it within their widths.
TOP_LOOP_TOLERANCE = 0.10
CMS_DIJET_LOW, ATLAS_GAUSSIAN_LOW = 600.0, 1500.0     # GeV: where CMS's coupling limit and ATLAS's Gaussian limits start
NARROW_2HDMA = 0.10               # Γ/m of A (H) up to which its resonant production describes mono-h (mono-Z)
# Our resonant σ over ATLAS's full benchmark σ, the smallest and largest over its 50 narrow-A nodes (2026-10-10, from
# scripts/validate_portal_library_5.py's benchmark points): the band within which a mono-h ratio is undecided.
RESONANT_OVER_FULL = (0.4189, 1.2400)
# ATLAS's benchmark couplings, at which that band was measured over ATLAS's own grid of masses. The dark matter's mass
# and coupling enter through BR(a → χχ̄), which the resonant rate carries itself.
BENCHMARK = {"sinp": 0.35, "tanbeta": 1.0, "lam3": 3.0, "laP1": 3.0, "laP2": 3.0}
# Beyond the benchmark (the owner, 2026-10-12: extend the calibration): the box MadGraph's full gg → h a covered. Only
# interpolation: the masses stay within the four nodes' span.
CALIBRATED = {"sinp": (0.2, 0.7), "tanbeta": (1.0, 5.0), "lam3": (3.0, 3.0), "laP1": (3.0, 3.0), "laP2": (3.0, 3.0)}
CALIBRATED_MASSES = {"m_A": (600.0, 1200.0), "m_a": (150.0, 300.0)}
# The shift s of our resonant-to-full ratio from the benchmark, its smallest and largest over the narrow-A nodes at each
# (sin θ, tan β) computed (docs/monoh/calibration.json, "shift_range"; rounded outward). The band there is
# RESONANT_OVER_FULL times that range; between grid points, the envelope of the four corners around the point.
SHIFTS: dict[tuple[float, float], tuple[float, float]] = {
    (0.2, 1.0): (0.575, 0.967), (0.2, 2.0): (0.848, 1.315), (0.2, 3.0): (0.935, 1.518), (0.2, 5.0): (0.990, 1.688),
    (0.35, 1.0): (1.000, 1.000), (0.35, 2.0): (1.090, 1.349), (0.35, 3.0): (1.113, 1.469), (0.35, 5.0): (1.118, 1.586),
    (0.5, 1.0): (1.081, 1.894), (0.5, 2.0): (0.353, 1.957), (0.5, 3.0): (0.374, 1.973), (0.5, 5.0): (0.393, 1.986),
    (0.7, 1.0): (0.314, 1.348), (0.7, 2.0): (0.138, 1.295), (0.7, 3.0): (0.145, 1.284), (0.7, 5.0): (0.155, 1.271),
}
# The mono-Z calibration (2026-10-12; scripts/madgraph_xsec/monoz_calibration.py, docs/monoz/calibration.json):
# MadGraph's full gg → Z a (the H s-channel and the top-quark boxes) times BR(a → χχ̄), at four (m_H, m_a) nodes where
# H is narrow, over the same (sin θ, tan β) grid. Per contour (its sin θ) and grid point, the smallest and largest
# shift s of our resonant-to-full ratio from the contour's benchmark (rounded outward). All lie within 0.959–1.021:
# the boxes' share hardly changes with the couplings, unlike the non-resonant share of mono-h.
MONOZ_CALIBRATED_MASSES = {"m_H": (500.0, 800.0), "m_a": (150.0, 300.0)}
SHIFTS_Z: dict[float, dict[tuple[float, float], tuple[float, float]]] = {
    0.35: {
        (0.2, 1.0): (0.997, 1.004), (0.2, 2.0): (0.981, 1.017),
        (0.2, 3.0): (0.978, 1.017), (0.2, 5.0): (0.981, 1.021),
        (0.35, 1.0): (1.000, 1.000), (0.35, 2.0): (0.983, 1.015),
        (0.35, 3.0): (0.981, 1.015), (0.35, 5.0): (0.986, 1.014),
        (0.5, 1.0): (0.989, 1.008), (0.5, 2.0): (0.991, 1.008),
        (0.5, 3.0): (0.994, 1.010), (0.5, 5.0): (1.004, 1.007),
        (0.7, 1.0): (0.995, 1.021), (0.7, 2.0): (0.988, 1.010),
        (0.7, 3.0): (0.988, 1.020), (0.7, 5.0): (0.982, 1.015),
    },
    0.7: {
        (0.2, 1.0): (0.977, 1.009), (0.2, 2.0): (0.962, 1.009),
        (0.2, 3.0): (0.959, 1.011), (0.2, 5.0): (0.962, 1.015),
        (0.35, 1.0): (0.980, 1.005), (0.35, 2.0): (0.964, 1.004),
        (0.35, 3.0): (0.962, 1.009), (0.35, 5.0): (0.967, 1.012),
        (0.5, 1.0): (0.987, 1.006), (0.5, 2.0): (0.972, 1.009),
        (0.5, 3.0): (0.975, 1.010), (0.5, 5.0): (0.985, 1.010),
        (0.7, 1.0): (1.000, 1.000), (0.7, 2.0): (0.989, 1.007),
        (0.7, 3.0): (0.998, 1.005), (0.7, 5.0): (0.998, 1.005),
    },
}
FWHM = 2.0 * math.sqrt(2.0 * math.log(2.0))
M_H = 125.09


def _family(cls) -> str:
    from adroit.parameter_space.searches import family
    return family(cls)


def _two_hdma(cls) -> bool:
    return _family(cls) == "ufo" and "atlas_2hdma" in getattr(cls, "searches", [])


# --- dijets --------------------------------------------------------------------------------------------

@lru_cache(maxsize=256)
def _reference_jj(m: float) -> float:
    """BR(jj) of a quark-only Z′ (vector, universal coupling): the five light flavours over all quarks."""
    from adroit.constraints import spin1
    widths = {f.name: spin1.partial_width(m, f.mass_gev, f.colours, 1.0, 0.0) for f in spin1.FERMIONS
              if f.family == "quark"}
    return sum(w for name, w in widths.items() if name != "t") / sum(widths.values())


def dijet(cls, p: Point, unverified: bool) -> Outcome | None:
    """A Z′'s dijet resonance below SModelS's maps (CMS, from 0.6 TeV) and when broad (ATLAS, from 1.5 TeV). A generic
    model's every new neutral vector, from its portrait and production (P3), the strongest outcome kept."""
    from adroit.parameter_space import searches as ps
    from adroit.parameter_space.flavour_vector import FlavourVectorClass
    generic = ps.generic_mediators(cls, p, 1)
    if generic:
        return _strongest([_dijet(cls, q, built, unverified, made.why, generic=True) for q, built, _, made in generic])
    if isinstance(cls, FlavourVectorClass):
        universal = cls.universal_point(p)
        if universal is None:
            return None
        from adroit.parameter_space.classes import Spin1Class
        cls, p = Spin1Class(name=cls.name), universal
    built = ps._z_prime(cls, p)
    if built is None:
        return None
    return _dijet(cls, p, built, unverified)


def _strongest(outcomes: list) -> Outcome | None:
    """Several mediators' outcomes as one, by the point's own rule (``searches.strongest``; AL3-14: the first allowed
    one, at the smaller ratio, and the first undecided one's reason alone, had been taken)."""
    from adroit.parameter_space import searches as ps
    return ps.strongest(outcomes)


def _dijet(cls, p: Point, built: tuple, unverified: bool, why_not: str = "", generic: bool = False) -> Outcome | None:
    """One mediator's dijet outcome, ``built`` as ``searches._z_prime`` gives it (m_med its mass)."""
    from adroit.parameter_space import searches as ps
    if built[0] is None:                       # outside the tables' masses: not applied; without them: undecided
        missing = ps.production_unavailable(*ps.VECTOR_TABLES.values())
        if not missing and why_not and "outside" not in why_not:
            missing = why_not
        return Outcome(name=DIJET, excluded=None, why=missing) if missing else None
    sigma, _, _, widths = built
    if generic and (sum(widths.values()) <= 0 or sigma <= 0):      # a generic vector coupled to no quark
        return None
    total = sum(widths.values())
    jj = sum(w for k, w in widths.items() if k != "dm" and abs(k[0]) <= 5) / total
    width = total / p.m_med
    ratios, blocked, flags = [], None, []
    if width <= NARROW_DIJET:
        r = _cms_dijet(cls, p, sigma, jj)
        if r is None and (unknown := _cms_unknown(p)):     # CMS's limit applies here: never silently absent (AL2-14)
            return Outcome(name=DIJET, excluded=None, why=unknown)
        if r is not None:
            stop = s._blocked(DIJET, "cms-1806.00843-dijet", unverified)
            blocked = blocked or stop
            ratios += [] if stop else [r]
    elif width > ATLAS_GAUSSIAN_MAX:
        return Outcome(name=DIJET, excluded=None, why=f"Γ/m = {width:.2f} is broader than ATLAS's widest DM Z′ (12%), the "
                       "widest it gives the acceptance for (arXiv:1910.08447)")
    else:
        r, matched, why = _atlas_gaussian(p, sigma * jj, width)
        if r is not None:
            stop = s._blocked(DIJET, ATLAS_GAUSSIAN, unverified)
            blocked = blocked or stop
            if not stop:
                ratios.append(r)
                flags += audit_notes.flags([ATLAS_GAUSSIAN])
                if matched > 1.0 >= r:
                    flags.append(f"dijets: ATLAS's Gaussian limit with the Breit–Wigner matched at its full width at "
                                 f"half maximum excludes this Z′ (ratio {matched:.3g}), ATLAS's truncation recipe does "
                                 f"not (ratio {r:.3g}); the matching is too strong by 1.6–1.7 against ATLAS's own "
                                 "Breit–Wigner limits, so this is flagged, not counted as an exclusion: the verdict is "
                                 "good up to an O(1) factor")
        elif CMS_DIJET_LOW <= p.m_med < ATLAS_GAUSSIAN_LOW:
            return Outcome(name=DIJET, excluded=None, why=f"a broad Z′ (Γ/m = {width:.2f}) at {p.m_med:.0f} GeV: CMS's "
                           "limit is for narrow resonances and ATLAS's Gaussian limits start at 1.5 TeV")
        elif why:
            return Outcome(name=DIJET, excluded=None, why=f"a broad Z′ (Γ/m = {width:.2f}): {why}")
    if not ratios:
        return blocked
    return Outcome(name=DIJET, excluded=max(ratios) > 1.0, ratio=max(ratios), flags=flags)


def _cms_unknown(p: Point) -> str:
    """Why CMS's narrow dijet limit, which applies at this mass, cannot be compared: the vector table that gives its
    reference coupling's σ is missing or does not reach the mass; "" otherwise (outside CMS's masses it does not
    apply)."""
    from adroit.constraints import production
    from adroit.parameter_space import searches as ps
    table = ps.VECTOR_TABLES["vector"]
    if s.interpolate(s._bundled("cms-1806.00843-dijet")["limit"], p.m_med) is None or production.sigma_pb(table, p.m_med):
        return ""
    return production.unavailable(table) or f"MadGraph's {table} does not reach {p.m_med:.4g} GeV, where CMS's limit applies"


def _cms_dijet(cls, p: Point, sigma: float, jj: float) -> float | None:
    from adroit.constraints import production
    from adroit.parameter_space import searches as ps
    limit = s.interpolate(s._bundled("cms-1806.00843-dijet")["limit"], p.m_med)
    unit = production.sigma_pb(ps.VECTOR_TABLES["vector"], p.m_med)
    if limit is None or not unit:
        return None
    g_eff2 = sigma * jj / (unit * _reference_jj(p.m_med))
    return g_eff2 / limit ** 2


def _atlas_gaussian(p: Point, sigma_jj: float, width: float) -> tuple[float | None, float | None, str]:
    """(ratio by ATLAS's recipe, ratio with σ_G = Γ/2.355, why): σ A BR(jj) over ATLAS's Gaussian limit, with the
    acceptance A of ATLAS's DM Z′ of the same width (its g_q columns have Γ/m = 3g_q²/(2π)), interpolated linearly in
    the width between the columns that cover this mass. By the recipe A is times the share inside 0.8–1.2 M
    (``window_fraction``), against the 10% Gaussian; matched, against the Gaussian at σ_G = Γ/2.355. None, and why,
    where the limits, the acceptances or the production table do not cover the point (no extrapolation)."""
    data = s._bundled(ATLAS_GAUSSIAN)
    gaussian = 100.0 * width / FWHM
    widths = sorted(float(w) for w in data["gaussian_limits"])
    if gaussian > widths[-1]:
        return None, None, f"σ_G/m = {gaussian:.1f}% is broader than ATLAS's 15% Gaussian"
    limits = [s.interpolate(data["gaussian_limits"][str(w)], p.m_med) for w in widths]
    if any(x is None for x in limits):
        return None, None, ""                                      # outside ATLAS's masses: the search does not apply
    acceptance, why = _acceptance(p.m_med, width)
    if acceptance is None:
        return None, None, why
    share = window_fraction(p.m_med, width)
    if share is None:
        return None, None, "the Breit–Wigner's share inside ATLAS's window needs the Z′ production table"
    accepted = sigma_jj * acceptance
    recipe = accepted * share / float(np.interp(RECIPE_GAUSSIAN, widths, limits))
    return recipe, accepted / float(np.interp(gaussian, widths, limits)), ""


def _acceptance(m: float, width: float) -> tuple[float | None, str]:
    """(A, why): the acceptance of ATLAS's DM Z′ of this width at this mass, linear in the width between the g_q
    columns that cover the mass; None, and why, outside them."""
    acceptances = {}                                   # A at this mass from each coupling's column, by its width
    for g, column in s._bundled(ATLAS_GAUSSIAN)["zprime_acceptance"].items():
        value = s.interpolate([r for r in column if r[1] is not None], m)
        if value is not None:
            acceptances[3.0 * float(g) ** 2 / (2.0 * math.pi)] = value
    nodes = sorted(acceptances)
    if not nodes or not nodes[0] * (1 - 1e-9) <= width <= nodes[-1] * (1 + 1e-9):
        span = f"Γ/m = {100 * nodes[0]:.1f}–{100 * nodes[-1]:.1f}%" if nodes else "no width"
        return None, f"ATLAS gives its DM Z′'s acceptance at {m:.0f} GeV for {span} only (arXiv:1910.08447)"
    return float(np.interp(width, nodes, [acceptances[w] for w in nodes])), ""


def window_fraction(m: float, width: float) -> float | None:
    """The share of a Z′'s selected dijets (m_jj > 1.1 TeV) inside ATLAS's window 0.8–1.2 M: the Breit–Wigner
    density L(m) m³/((m² − M²)² + M²Γ²), Γ = width × M, with the q q̄ luminosity L(m) ∝ σ(m) of the narrow-width
    vector table (σ ∝ dL/dτ at τ = m²/s). Leading order at parton level: final-state radiation, which moves events
    below the window, is left out. Integrated within the table only (to 6 TeV), so above M = 5 TeV the window loses
    part of its upper side and the share is lower (conservative). None without the table."""
    from adroit.constraints import production
    from adroit.parameter_space import searches as ps
    name = ps.VECTOR_TABLES["vector"]
    if not production.available(name):
        return None
    held = production.table(name)              # one reading: the grid's range and its cross-sections (DY-02)
    if len(held.masses) < 2 or held.masses[-1] <= max(MJJ_MIN, held.masses[0]):
        return None
    grid = np.linspace(max(MJJ_MIN, held.masses[0]), held.masses[-1], 1201)
    density = np.exp(held.spline(np.log(grid))) * grid ** 3 / ((grid ** 2 - m ** 2) ** 2 + (m * m * width) ** 2)
    inside = (grid >= TRUNCATION[0] * m) & (grid <= TRUNCATION[1] * m)
    total = float(np.trapezoid(density, grid))
    return float(np.trapezoid(density[inside], grid[inside])) / total if total > 0 and inside.sum() > 1 else None


# --- tt̄ ------------------------------------------------------------------------------------------------

def _top_states(cls, p: Point) -> list[tuple[str, str, float, float, float, float]]:
    """(label, "scalar" | "pseudoscalar", m, Γ, g_Φtt, g_Φbb) of each state coupling to the top (couplings in units of
    the Standard Model's Yukawas)."""
    from adroit.parameter_space import searches as ps
    if isinstance(cls, ScalarClass):
        built = ps._scalar(cls, p)
        if built is None:                        # in the hadronic window (m_S ≤ 3 GeV): no tt̄ to judge
            return []
        widths = built[3]
        return [("S", "pseudoscalar" if cls.sm_pseudoscalar else "scalar", p.m_med, sum(widths.values()), p.g_q, p.g_q)]
    if _family(cls) == "singlet_mixing":
        widths = ps._scalar(cls, p)[3]
        mixing = cls._mixing(p)[0]
        return [("h₂", "scalar", p.m_med, sum(widths.values()), mixing, mixing)]
    generic = ps.generic_mediators(cls, p, 0)
    if generic:                       # a generic model's scalars (P3): pure CP only, CMS's signal is one or the other
        out = []
        for _, built, m, _ in generic:
            g_t, g_b = (_yukawa_units(m, q) for q in ("t", "b"))
            if m.cp in ("even", "odd") and g_t:
                out.append((m.name, "scalar" if m.cp == "even" else "pseudoscalar", m.mass_gev, m.width_gev, g_t, g_b))
            elif g_t:
                out.append((m.name, "mixed", m.mass_gev, m.width_gev, g_t, g_b))
        return out
    if _two_hdma(cls):
        x = cls._overrides(p)
        model = cls.model(p)
        s_t, t_b = x["sinp"], x["tanbeta"]
        c_t = math.sqrt(max(1.0 - s_t * s_t, 0.0))
        out = []
        for label, name, cp, g, g_b in (("a", "h4", "pseudoscalar", s_t / t_b, s_t * t_b),
                                        ("A", "h3", "pseudoscalar", c_t / t_b, c_t * t_b),
                                        ("H", "h2", "scalar", 1.0 / t_b, t_b)):
            state = model.particles[name]
            total = sum(w for w, _ in ps._two_body_channels(model, state))
            out.append((label, cp, state.mass, total, g, g_b))
        return out
    return []


def _yukawa_units(m, quark: str) -> float:
    """A portrait's scalar or pseudoscalar coupling to the quark in units of the Standard Model's Yukawa, in the
    gluon-fusion tables' masses (``generic_production.TABLE_MASSES``), as g_Φtt and the library's g_q are."""
    from adroit.parameter_space.portals.generic_production import TABLE_MASSES, V_GEV
    c = m.coupling(quark)
    if c is None:
        return 0.0
    return (c.even if m.cp != "odd" else c.odd) * V_GEV / TABLE_MASSES[quark]


def _top_loop_mismatch(cp: str, m: float, g_t: float, g_b: float) -> str:
    """Why CMS's top-loop-only signal model does not describe this state ('' if it does): the b-quark loop changes
    gg → Φ by more than ``TOP_LOOP_TOLERANCE``."""
    from adroit.parameter_space import searches as ps
    if g_b == 0.0:
        return ""
    both, top = ps.gluon_fusion_pb("P" if cp == "pseudoscalar" else "S", g_t, g_b, m), \
        ps.gluon_fusion_pb("P" if cp == "pseudoscalar" else "S", g_t, 0.0, m)
    if not both or not top:
        return "" if abs(g_b) <= abs(g_t) else "the b-quark loop's share of gg → Φ could not be computed"
    change = both / top - 1.0
    if abs(change) <= TOP_LOOP_TOLERANCE:
        return ""
    return (f"the b-quark loop changes gg → Φ by {100 * change:+.0f}%, while CMS's interference with QCD tt̄ assumes the "
            "top-quark loop alone (arXiv:1908.01115)")


TTBAR_G_REACH = 3.0     # the coupling axis of CMS's figures ends at g = 3 (arXiv:1908.01115 Figs. 5, 6; islands reach it)


def _excluded_at(entry: dict, m: float, g: float) -> bool | None:
    """Whether g is excluded at mass m by one width's borders; None outside the mass range, or above the figures'
    couplings (``TTBAR_G_REACH``), where neither an island's upper edge nor the exclusion is shown (AL2-15: g = 5 had
    been excluded, and g = 10 above an island's lower edge allowed)."""
    lower = s.interpolate(entry["lower"], m) if "lower" in entry else None
    if lower is None or g > TTBAR_G_REACH:
        return None
    if g <= lower:
        return False
    low = s.interpolate(entry["island_low"], m) if "island_low" in entry else None
    if low is None or g < low:
        return True
    high = s.interpolate(entry["island_high"], m) if "island_high" in entry else None
    return high is not None and g > high


def _ttbar_state(data: dict, cp: str, m: float, width_pct: float, g: float) -> bool | None:
    widths = data["widths_pct"]
    if width_pct > widths[-1]:
        return None
    width_pct = max(width_pct, widths[0])
    upper = next(w for w in widths if w >= width_pct)
    lower = max(w for w in widths if w <= width_pct)
    verdicts = {_excluded_at(data["borders"][cp][str(w)], m, g) for w in (lower, upper)}
    return verdicts.pop() if len(verdicts) == 1 else None


def ttbar(cls, p: Point, unverified: bool) -> Outcome | None:
    """CMS's tt̄ resonance search on each state that couples to the top (module docstring)."""
    every = [x for x in _top_states(cls, p) if x[4] != 0.0]
    states = [x for x in every if 400.0 <= x[2] <= 750.0]
    if not states:
        return None
    blocked = s._blocked(TTBAR, "cms-1908.01115-ttbar", unverified)
    if blocked:
        return blocked
    data = s._bundled("cms-1908.01115-ttbar")
    undecided = []
    for label, cp, m, total, g, g_b in states:
        if cp == "mixed":
            undecided.append(f"{label} ({m:.0f} GeV): couples to the top as a scalar and a pseudoscalar, and CMS's "
                             "signal is one or the other")
            continue
        overlapping = [o[0] for o in every if o[0] != label and o[1] == cp and abs(o[2] - m) < o[3] + total]
        mismatch = (f"{', '.join(overlapping)} of the same CP overlaps it within their widths, and CMS's limit is for "
                    "one state" if overlapping else _top_loop_mismatch(cp, m, g, g_b))
        if mismatch:
            undecided.append(f"{label} ({m:.0f} GeV): {mismatch}")
            continue
        verdict = _ttbar_state(data, cp, m, 100.0 * total / m, abs(g))
        if verdict:
            return Outcome(name=TTBAR, excluded=True, value=abs(g), why=f"{label}: g_tt = {abs(g):.3g} at {m:.0f} GeV")
        if verdict is None:
            undecided.append(f"{label} ({m:.0f} GeV, Γ/m = {total / m:.2f}, g_tt = {abs(g):.3g}): between CMS's "
                             f"tabulated widths, broader than 25%, or above its figures' g = {TTBAR_G_REACH:g}")
    if undecided:
        return Outcome(name=TTBAR, excluded=None, why="CMS's tt̄ limit does not decide: " + "; ".join(undecided))
    return Outcome(name=TTBAR, excluded=False)


# --- the 2HDM+a's mono-Higgs and mono-Z -------------------------------------------------------------------

def _branching(model, parent: str, finals: set[int]) -> float:
    from adroit.parameter_space import searches as ps
    channels = ps._two_body_channels(model, model.particles[parent])
    total = sum(w for w, _ in channels)
    return sum(w for w, d in channels if {abs(x) for x in d} == finals) / total if total > 0 else 0.0


def _resonant_rates(cls, p: Point) -> dict[str, float | None]:
    """LO σ (pb) of gg → A → a h and gg → H → a Z, with a → χχ̄, at the point; None where the gluon-fusion tables
    give no σ or K-factor (never an invented zero)."""
    from adroit.parameter_space import searches as ps
    x = cls._overrides(p)
    model = cls.model(p)
    s_t, t_b = x["sinp"], x["tanbeta"]
    c_t = math.sqrt(max(1.0 - s_t * s_t, 0.0))
    a, big_a, big_h = (model.particles[n] for n in ("h4", "h3", "h2"))
    dm = abs(model.particles[cls.dm].pdg)
    invisible = _branching(model, "h4", {dm})
    out = {}
    for key, state, cp, g_t, g_b, finals in (("h", big_a, "P", c_t / t_b, c_t * t_b, {25, abs(a.pdg)}),
                                             ("Z", big_h, "S", -1.0 / t_b, t_b, {23, abs(a.pdg)})):
        sigma = ps.gluon_fusion_pb(cp, g_t, g_b, state.mass)
        k = _k(state.mass)
        out[key] = None if sigma is None or not k else sigma / k * _branching(model, state.name, finals) * invisible
    return out


def _rates_missing() -> str:
    """Why the 2HDM+a's resonant rates are unknown: the gluon-fusion tables or their K-factor."""
    from adroit.constraints import production
    from adroit.parameter_space import searches as ps
    return ps.production_unavailable(*(f"ggS_spin0_{cp}_{q}_13TeV_LO" for cp in "SP" for q in ("t", "b", "tb")),
                                     production.K_TABLE) or "the gluon-fusion σ is outside its tables' masses"


def _relative_width(model, name: str) -> float:
    from adroit.parameter_space import searches as ps
    state = model.particles[name]
    return sum(w for w, _ in ps._two_body_channels(model, state)) / state.mass


def _k(mass: float) -> float | None:
    from adroit.constraints import production
    return production.gluon_fusion_k(mass)


@lru_cache(maxsize=4)
def _sigma95_interpolator():
    from scipy.interpolate import LinearNDInterpolator
    grid = np.array(s._bundled("atlas-2108.13391-monoh")["sigma95"], dtype=float)
    return LinearNDInterpolator(grid[:, :2], np.log(grid[:, 2]))


def _band(values: dict, m_big: float, m_a: float) -> tuple[tuple[float, float] | None, str]:
    """The resonant-to-full band at the point: ATLAS's own at its benchmark couplings, the widened one inside the
    calibrated box; otherwise None, with what lies outside the box."""
    if all(math.isclose(float(values[k]), v, abs_tol=1e-9) for k, v in BENCHMARK.items()):
        return RESONANT_OVER_FULL, ""
    away = [f"{k} = {float(values[k]):g}" for k, (lo, hi) in CALIBRATED.items()
            if not lo - 1e-9 <= float(values[k]) <= hi + 1e-9]
    away += [f"{k} = {m:g} GeV" for (k, (lo, hi)), m in zip(CALIBRATED_MASSES.items(), (m_big, m_a))
             if not lo - 1e-6 <= m <= hi + 1e-6]
    if away:
        return None, ", ".join(away)
    low, high = shift_range(float(values["sinp"]), float(values["tanbeta"]))
    return (RESONANT_OVER_FULL[0] * low, RESONANT_OVER_FULL[1] * high), ""


def shift_range(sin_theta: float, tan_beta: float,
                table: dict[tuple[float, float], tuple[float, float]] | None = None) -> tuple[float, float]:
    """The smallest and largest shift s at (sin θ, tan β) inside the calibrated box: the envelope over the grid
    points that bracket it (at most four corners; one at a grid point). ``table``: mono-h's ``SHIFTS`` by default, or
    one contour's of ``SHIFTS_Z``."""
    table = SHIFTS if table is None else table

    def bracket(grid: list[float], x: float) -> set[float]:
        return {max(g for g in grid if g <= x + 1e-9), min(g for g in grid if g >= x - 1e-9)}
    corners = [table[(a, b)] for a in bracket(sorted({k[0] for k in table}), sin_theta)
               for b in bracket(sorted({k[1] for k in table}), tan_beta)]
    return min(c[0] for c in corners), max(c[1] for c in corners)


def monoh(cls, p: Point, unverified: bool) -> Outcome | None:
    """ATLAS's mono-Higgs search on the 2HDM+a's A → a h, a → χχ̄ (module docstring)."""
    from adroit.parameter_space.portals import generic_2hdma
    found = generic_2hdma.match(cls, p)
    if isinstance(found, str):
        return Outcome(name=MONOH, excluded=None, why=found)
    if found is not None:                                    # a generic model read as the 2HDM+a: the library's UFO
        cls, p = found.portal()
    if not _two_hdma(cls):
        return None
    model = cls.model(p)
    m_a, m_big = model.particles["h4"].mass, model.particles["h3"].mass
    if m_big < m_a + M_H:
        return None
    if _relative_width(model, "h3") > NARROW_2HDMA:
        return Outcome(name=MONOH, excluded=None, why="A is broad (Γ/m > 10%): its non-resonant production, which "
                                                      "dominates there, is not modelled")
    log_limit = float(_sigma95_interpolator()(m_big, m_a))
    if math.isnan(log_limit):
        return Outcome(name=MONOH, excluded=None, why=f"(m_A, m_a) = ({m_big:.0f}, {m_a:.0f}) GeV is outside ATLAS's grid")
    band, away = _band(cls._overrides(p), m_big, m_a)
    if band is None:
        return Outcome(name=MONOH, excluded=None, why="the resonant-to-full band is calibrated at ATLAS's benchmark "
                       "(sin θ = 0.35, tan β = 1, λ₃ = λ_P1 = λ_P2 = 3) and, beyond it, for sin θ 0.2–0.7, tan β 1–5, "
                       "m_A 600–1200 GeV and m_a 150–300 GeV with the λ's at 3; here " + away)
    blocked = s._blocked(MONOH, "atlas-2108.13391-monoh", unverified)
    if blocked:
        return blocked
    rate = _resonant_rates(cls, p)["h"]
    if rate is None:
        return Outcome(name=MONOH, excluded=None, why=_rates_missing())
    r = 1e3 * rate / math.exp(log_limit)                                    # pb → fb
    low, high = band
    if low <= r <= high:
        return Outcome(name=MONOH, excluded=None, value=r,
                       why=f"r = {r:.2f} (resonant σ only) is within the band {low}–{high} that ATLAS's full σ can be "
                           "relative to ours; non-resonant diagrams decide")
    return Outcome(name=MONOH, excluded=r > high, ratio=r)


def _inside(polygon: list[list[float]], x: float, y: float) -> bool:
    """Ray casting; the polygon is closed by joining its ends."""
    inside = False
    n = len(polygon)
    for i in range(n):
        (x1, y1), (x2, y2) = polygon[i], polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def _reference(cls, sin_theta: float, m_heavy: float):
    """The 2HDM+a of ATLAS's mono-Z plane: tan β = 1, λ₃ = λ_P1 = λ_P2 = 3, m_χ = 10 GeV, y_χ = 1."""
    parameters = dict(cls.parameters)
    parameters.update({"sinp": repr(sin_theta), "tanbeta": "1.0", "lam3": "3.0", "laP1": "3.0", "laP2": "3.0",
                       "MXd": "10.0", "gPXd": "1.0", "mh2": repr(m_heavy), "mh3": repr(m_heavy), "mhc": repr(m_heavy)})
    return cls.model_copy(update={"parameters": parameters})


def monoz(cls, p: Point, unverified: bool) -> Outcome | None:
    """ATLAS's mono-Z contours on the 2HDM+a's H → a Z, a → χχ̄ (module docstring: the monotone rule)."""
    from adroit.parameter_space.portals import generic_2hdma
    found = generic_2hdma.match(cls, p)
    if isinstance(found, str):
        return Outcome(name=MONOZ, excluded=None, why=found)
    if found is not None:                                    # a generic model read as the 2HDM+a: the library's UFO
        cls, p = found.portal()
    if not _two_hdma(cls):
        return None
    model = cls.model(p)
    m_a, m_big = model.particles["h4"].mass, model.particles["h2"].mass
    if m_big < m_a + 91.1876 or m_a < 100.0:
        return None
    if _relative_width(model, "h2") > NARROW_2HDMA:
        return Outcome(name=MONOZ, excluded=None, why="H is broad (Γ/m > 10%): its non-resonant production, which "
                                                      "dominates there, is not modelled")
    planes = s._bundled("atlas-2111.08372-monoz")["contours"]
    shifts, away = _monoz_shifts(cls._overrides(p), m_big, m_a, planes)
    if not shifts:
        return Outcome(name=MONOZ, excluded=None, why="ATLAS's mono-Z contours are for its benchmark couplings "
                       "(sin θ = 0.35 or 0.7, tan β = 1, λ₃ = λ_P1 = λ_P2 = 3, m_H = m_A = m_H±); MadGraph's "
                       "calibration extends them over sin θ 0.2–0.7, tan β 1–5, m_H 500–800 GeV and m_a 150–300 GeV "
                       f"(λ's = 3), and this point lies outside it ({away})")
    blocked = s._blocked(MONOZ, "atlas-2111.08372-monoz", unverified)
    if blocked:
        return blocked
    rate = _resonant_rates(cls, p)["Z"]
    references = {plane: _resonant_rates(_reference(cls, float(plane), m_big), p)["Z"] for plane in shifts}
    if rate is None or not all(references.values()):
        return Outcome(name=MONOZ, excluded=None, why=_rates_missing())
    sides = [(plane, low, high, rate / references[plane],
              _inside(closed_on_edge(planes[plane]), m_a, m_big), _covered(planes[plane], m_a, m_big))
             for plane, (low, high) in shifts.items()]
    for plane, _low, high, ratio, inside, _covers in sides:
        if inside and ratio >= high * (1 - RATE_PRECISION):
            return Outcome(name=MONOZ, excluded=True, why=f"inside ATLAS's sin θ = {plane} contour, at {ratio:.3g} × "
                                                          f"its reference's rate (≥ {high:.3g}, the calibrated shift)")
    for _plane, low, _high, ratio, inside, covers in sides:
        if not inside and covers and ratio <= low * (1 + RATE_PRECISION):
            return Outcome(name=MONOZ, excluded=False)
    return Outcome(name=MONOZ, excluded=None, why="inside a contour with less than its reference rate (times the "
                                                  "calibrated shift), outside with more, or beyond what it covers")


def _monoz_shifts(values: dict, m_big: float, m_a: float,
                  planes: dict) -> tuple[dict[str, tuple[float, float]], str]:
    """Per contour (keyed as in the record), the range of the shift s at the point: (1, 1) at the contour's own
    benchmark couplings, at any masses; inside the calibrated box, the envelope of ``SHIFTS_Z`` around the point's
    (sin θ, tan β); otherwise none. Returned with what lies outside the box. The heavy states must be degenerate."""
    heavy = [float(values[k]) for k in ("mh2", "mh3", "mhc")]
    if not math.isclose(min(heavy), max(heavy), rel_tol=1e-9):
        return {}, "m_H, m_A and m_H± differ"
    away = [f"{k} = {float(values[k]):g}" for k, (lo, hi) in CALIBRATED.items()
            if not lo - 1e-9 <= float(values[k]) <= hi + 1e-9]
    away += [f"{k} = {m:g} GeV" for (k, (lo, hi)), m in zip(MONOZ_CALIBRATED_MASSES.items(), (m_big, m_a))
             if not lo - 1e-6 <= m <= hi + 1e-6]
    out = {}
    for plane in planes:
        own = {**MONOZ_BENCHMARK, "sinp": float(plane)}
        if all(math.isclose(float(values[k]), v, abs_tol=1e-9) for k, v in own.items()):
            out[plane] = (1.0, 1.0)
        elif not away:
            out[plane] = shift_range(float(values["sinp"]), float(values["tanbeta"]), SHIFTS_Z[float(plane)])
    return out, ", ".join(away)


# A rate at its contour's reference within this relative precision is at it: at a benchmark the shift is exactly 1,
# and the exact comparison had flipped a point read back to 10⁻¹³ (P5's 2HDM+a through the generic route) from
# excluded to undecided.
RATE_PRECISION = 1e-9
MONOZ_EDGE = 100.0               # GeV: the plane's lower m_a edge, where ATLAS's mono-Z contours begin and end
# ATLAS's mono-Z benchmark couplings besides sin θ (one contour each for 0.35 and 0.7). At them the point's resonant
# rate differs from the contour's reference only through BR(a → χχ̄), which multiplies every diagram of gg → Z a, so
# the monotone rule holds as it is; away from them the boxes' share changes, by the shift ``SHIFTS_Z`` measures.
MONOZ_BENCHMARK = {"tanbeta": 1.0, "lam3": 3.0, "laP1": 3.0, "laP2": 3.0}


def closed_on_edge(contour: list[list[float]]) -> list[list[float]]:
    """A mono-Z contour closed along the plane's real edge m_a = 100 GeV, not by a slanted segment between its
    ends (which start and end at m_a ≈ 100–106 GeV)."""
    y_first, y_last = contour[0][1], contour[-1][1]
    return [[MONOZ_EDGE, y_first], *contour, [MONOZ_EDGE, y_last]]


def _covered(contour: list[list[float]], m_a: float, m_big: float) -> bool:
    """Whether a point lies within the region the contour spans: beyond it "outside" is no evidence."""
    xs, ys = [c[0] for c in contour], [c[1] for c in contour]
    return MONOZ_EDGE <= m_a <= max(xs) and min(ys) <= m_big <= max(ys)


EVALUATORS = (dijet, ttbar, monoh, monoz)
