"""The searches of ``constraints.searches`` applied to the portal library's models, point by point.

``outcomes(cls, p, unverified)`` returns every search that applies to the model at the point;
the scan records each as a constraint (excluded, allowed, or undecided, which makes the point
pending). Each evaluator below says when it applies.
"""

from __future__ import annotations

import bisect
import math
import subprocess

import numpy as np

from adroit.constraints import audit_notes
from adroit.constraints import searches as s
from adroit.constraints import spin1
from adroit.constraints.searches import Outcome
from adroit.parameter_space import halo_limits
from adroit.parameter_space.classes import Point, ScalarClass, Spin1Class

CMB, DARK_PHOTON, FLAVOUR = "CMB (Planck)", "dark-photon searches", "flavour (B → K a)"
DILEPTON, LEP_CONTACT, SQUARK = "LHC dilepton resonances (ATLAS)", "LEP-II contact interactions", "LHC squark search (ATLAS)"
LEP_CONTACT_MIN = 300.0           # GeV: LEP's contact bound needs M ≫ √s ≈ 209 GeV
# GeV: the dilepton recast's highest mass (the owner's data audit, 2026-10-12). Its constant fiducial/LO correction
# (1.087, the SSM median over 1–5 TeV) holds to about ±10% up to 4.5 TeV; above, ATLAS's SSM fiducial σ falls to
# 0.88 (5 TeV) and 0.578 (6 TeV) of the LO σ, so the constant would overshoot by up to 88%. Most likely the off-shell
# tail, which depends on the Z′'s width: extending this needs the B − L fiducial σ itself.
DILEPTON_MAX = 4500.0
G2, LMU = "muon g−2", "L_μ − L_τ (CCFR)"
IDM_LEP, TWO_HDMA = "LEP (inert doublet)", "LHC 2HDM+a searches (ATLAS)"

VISIBLE_PROMPT = ["BaBar_Lees2014xha", "LHCb_Aaij2019bvg_prompt", "CMS_CMS2019kiy", "KLOE_Anastasi2018azp_combined",
                  "KLOE_Anastasi2015qla", "A1_Merkel2014avp", "APEX_Abrahamyan2011gv", "NA48_Batley2015lha",
                  "BESIII_Ablikim2017aab", "HPS_Adrian2018scb"]       # HPS 2018 is a prompt bump hunt (2026-10-13)
VISIBLE_DISPLACED = ["LHCb_Aaij2019bvg_displaced", "E137_Andreas2012mt", "E141_Riordan1987aw",
                     "E774_Bross1989mp", "KEK_Konaka1986cb", "Orsay_Davier1989wz", "NuCAL_Blumlein1991xh",
                     "NuCAL_Tsai2019mtm", "CHARM_Tsai2019mtm", "PS191_Bernardi1985ny", "NOMAD_Astier2001ck",
                     "NA64_Banerjee2019hmi"]
INVISIBLE = ["BaBar_Lees2017lec", "NA64_NA642019imj", "NA62_CortinaGil2019nuo", "LEP_Fox2011fx"]
REACH_GEV = 200.0
# DarkCast's searches (bump hunts, beam dumps, missing mass) assume a narrow A′ or Z′. ADROIT applies them up to
# Γ/m = 10%, one threshold for all (the owner, 2026-10-12, as for SModelS), until each experiment's resolution is
# recorded; a broader mediator is undecided (docs/widths.md).
DARKCAST_NARROW = 0.10
Z4MU = "L_μ − L_τ (Z → 4μ)"
# Z → 4μ's records and the Γ/m each holds below (CMS: g′²/4π < 0.01; ATLAS: its 2% mass resolution)
FOUR_MU = {"cms-1808.03684-4mu": 0.01, "atlas-2301.09342-4mu": 0.02}
# Below the best sensitivity either paper prints (CMS 3.4 × 10⁻³ in its Fig. 6, ATLAS "0.003" in its text): an
# effective g′ under it is out of their reach at every mass, so no outcome (as before the records), not pending
FOUR_MU_FLOOR = 2e-3


def family(cls) -> str:
    """The model's family (its ``family`` field, else its class name), which decides the searches that apply."""
    return getattr(cls, "family", type(cls).__name__)


# --- the CMB ----------------------------------------------------------------------------------------------

F_EFF = {"hadrons": "qqbar", "e": "e+e-", "mu": "mu+mu-", "tau": "tau+tau-", "u": "qqbar", "d": "qqbar", "s": "qqbar", "c": "ccbar",
         "b": "bbbar", "t": "ttbar", "W": "W+W-", "Z": "Z0Z0", "g": "gg", "gamma": "gammagamma",
         "aa_photons": "gammagamma", "hh": "hh"}
NO_ENERGY = {"nu", "nu_e", "nu_mu", "nu_tau", "invisible"}
CMB_REACH = 3.2e-29        # cm³ s⁻¹ GeV⁻¹: a tenth of Planck 2018's limit


TEX = {"e+e-": "e^+e^-", "mu+mu-": r"\mu^+\mu^-", "tau+tau-": r"\tau^+\tau^-", "qqbar": r"q\bar{q}",
       "ccbar": r"c\bar{c}", "bbbar": r"b\bar{b}", "ttbar": r"t\bar{t}", "W+W-": "W^+W^-", "Z0Z0": "Z^0Z^0",
       "gg": "gg", "gammagamma": r"\gamma\gamma", "hh": "hh"}


def _f_eff(m: float) -> tuple[dict[str, float], float, float] | None:
    """(f_eff by channel, smallest, largest open) at m, from Slatyer's table (5 GeV – 100 TeV)."""
    import numpy as np
    table = s.f_eff_table()
    if table is not None and m < table[0][0]:
        low_mass = s.f_eff_low_mass(m)                 # below 5 GeV: e, γ exactly and μ from the Michel spectrum
        if low_mass is None:
            return None
        open_ = [v for v in low_mass.values() if v > 0]
        return low_mass, min(open_), max(open_)
    if table is None or not table[0][0] <= m <= table[0][-1]:
        return None
    masses, names, values = table
    out = {}
    for key, tex in TEX.items():
        column = values[:, names.index(tex)]
        valid = column > 0
        if valid.any() and m >= masses[valid][0]:
            out[key] = float(np.interp(math.log(m), np.log(masses[valid]), column[valid]))
    open_ = [v for v in out.values() if v > 0]
    return out, min(open_), max(open_)


def _first_tabulated(channel: str) -> float | None:
    """The lowest mass (GeV) at which Slatyer tabulates a channel's f_eff. Below it the table's zeros mean "not
    computed" (bb̄ to 6, W⁺W⁻ to 90, ZZ to 100, hh to 130, tt̄ to 180 GeV), not zero deposition, so ``_f_eff``
    leaves the channel untabulated there (the owner's record review, 2026-10-13)."""
    table = s.f_eff_table()
    if table is None or channel not in TEX:
        return None
    masses, names, values = table
    column = values[:, names.index(TEX[channel])]
    return float(masses[column > 0][0]) if (column > 0).any() else None



def dm_mass(cls, p: Point) -> float:
    """The dark matter's physical mass at the point: the engine's own where it differs from m_χ (a generic model,
    whose m_χ is a Lagrangian parameter shifted by mixing or a vacuum value), else m_χ (the audit's G3/G4-4, G12:
    the limits had been read at the Lagrangian mass, 14% off for a Higgs-portal singlet)."""
    own = getattr(cls, "dark_matter_mass", None)
    return float(own(p)) if callable(own) else p.m_chi


def cmb(cls, p: Point, unverified: bool) -> Outcome | None:
    """Applies where p_ann could reach ``CMB_REACH`` even with f_eff = 1 (a tenth of Planck's limit)."""
    m_dm = dm_mass(cls, p)          # the physical dark-matter mass (the audit's G3/G4-4, G12)
    hadronic = today_hadronic(cls, p)
    if (unknown := today_unknown(cls, p)) and unknown != hadronic:
        return Outcome(name=CMB, excluded=None, why=unknown)
    try:
        rates = s.s_wave(cls, p)
    except s.CMBUnresolved as error:                 # AL6-02: undecided, not the extrapolation's rate
        return Outcome(name=CMB, excluded=None, why=str(error))
    factor = 1.0 if (cls.self_conjugate() if callable(getattr(cls, "self_conjugate", None)) else False) else 0.5
    if hadronic:
        return _cmb_without_hadrons(cls, p, rates, factor, m_dm, hadronic, unverified)
    if factor * sum(v for k, v in rates.items() if k not in NO_ENERGY) / m_dm < CMB_REACH:
        return None
    blocked = s._blocked(CMB, "planck-2018-pann", unverified)
    if blocked:
        return blocked
    limit = s._record("planck-2018-pann").data["p_ann_cm3_s_gev"]
    reason = _spectrum_reference_reason(cls,p)
    if reason:
        upper = sum(v for k,v in rates.items() if k not in NO_ENERGY)*factor/m_dm
        return Outcome(name=CMB,excluded=False if upper < limit else None,
            value=upper/limit,why=("allowed even with f_eff = 1; "+reason) if upper < limit else reason)
    feff = _f_eff(m_dm)
    if feff is None:
        total = sum(v for k, v in rates.items() if k not in NO_ENERGY) * factor / m_dm
        if total < limit:
            return Outcome(name=CMB, excluded=False, why="allowed even with f_eff = 1", value=total / limit,
                           ratio=None)
        return Outcome(name=CMB, excluded=None, why=f"f_eff is not available at m_χ = {m_dm:.3g} GeV")
    table, low, high = feff
    lower = upper = 0.0
    untabulated, ranged = [], []
    for name, rate in rates.items():
        if name in NO_ENERGY:
            continue
        known = table.get(F_EFF.get(name, ""), None)
        bounds = (known, known) if known is not None else (
            cls.cmb_f_eff_range(name, p) if hasattr(cls, "cmb_f_eff_range") else None)     # a cascade's (G6)
        if bounds is None:
            untabulated.append(name)
            bounds = (0.0, 1.0)
        elif known is None:
            ranged.append(name)                      # bounds decide; no single ratio for the likelihood
        lower += factor * rate * bounds[0] / m_dm
        upper += factor * rate * bounds[1] / m_dm
    exact = not (untabulated or ranged)
    if lower > limit:
        return Outcome(name=CMB, excluded=True, value=lower / limit, ratio=lower / limit if exact else None)
    if upper < limit:
        return Outcome(name=CMB, excluded=False, value=upper / limit, ratio=upper / limit if exact else None)
    return Outcome(name=CMB, excluded=None, value=lower / limit, why=_untabulated_reason(untabulated, m_dm))


def _cmb_without_hadrons(cls, p: Point, rates: dict, factor: float, m: float, hadronic: str,
                         unverified: bool) -> Outcome:
    """The CMB where the quark channels' σv today is not computed (the hadronic window): every f_eff is positive, so
    the other channels' p_ann at their smallest f_eff is a lower bound on the whole; it excludes alone or the CMB is
    undecided (never allowed: the hadronic σv has no upper bound here)."""
    blocked = s._blocked(CMB, "planck-2018-pann", unverified)
    if blocked:
        return blocked
    limit = s._record("planck-2018-pann").data["p_ann_cm3_s_gev"]
    feff = _f_eff(m)
    table = feff[0] if feff is not None else {}
    partons = {"u", "d", "s", "c", "b", "t", "g", "hadrons", "qqbar"}
    lower = sum(factor * rate * (table.get(F_EFF.get(name, ""), None) or 0.0) / m
                for name, rate in rates.items() if name not in NO_ENERGY and not set(name.replace("~", "").split()) &
                partons)                                      # the quark and gluon pairs are not computed here
    if lower > limit:
        return Outcome(name=CMB, excluded=True, value=lower / limit, ratio=None,
                       flags=[f"excluded by the channels computed alone; {hadronic}"])
    return Outcome(name=CMB, excluded=None, value=lower / limit, why=f"{hadronic}; the channels computed alone do not "
                   "exclude, and the hadronic σv has no upper bound here")


def _untabulated_reason(channels: list[str], m: float) -> str:
    """Why the CMB bracket cannot decide: which channels' f_eff are not tabulated, and why."""
    below = [f"{F_EFF[c]} (Slatyer tabulates it from {_first_tabulated(F_EFF[c]):g} GeV)" for c in channels
             if F_EFF.get(c) in TEX and _first_tabulated(F_EFF[c]) is not None and m < _first_tabulated(F_EFF[c])]
    cascades = [c for c in channels if F_EFF.get(c) not in TEX]
    parts = ([f"the cascade channel{'s' if len(cascades) > 1 else ''} {', '.join(cascades)}"] if cascades else []) + \
        ([f"{', '.join(below)}, at m_χ = {m:.3g} GeV"] if below else [])
    return (f"f_eff is not tabulated for {' and '.join(parts) or 'a channel'}, and the rigorous energy-deposition "
            "bracket 0 ≤ f_eff ≤ 1 straddles the limit")


# --- dark photons -------------------------------------------------------------------------------------------

def _dark_photon_branching(cls, p: Point) -> float:
    """BR(A′ → dark matter): its partial width over the A′'s own total width (``bosons``: below 2 GeV its hadrons by
    the measured R ratio), as everything else reads the model (0 below threshold). The recheck's RC21-06, 2026-10-22:
    the Standard Model's part had been summed over free quarks, 0.26 against the model's own 0.49 at m_A′ = 0.1 GeV,
    and BaBar's invisible search at 0.1 GeV allowed a point the consistent fraction leaves pending."""
    from adroit.parameter_space.portals.vector import _width
    meds, dark, _ = cls.bosons(p)
    m = meds[1].mass
    if 2.0 * p.m_chi >= m or meds[1].width <= 0:
        return 0.0
    to_dm = _width(m, {f.name: (0.0, 0.0) for f in spin1.FERMIONS}, dark[1], p.m_chi, cls._dm())
    return to_dm / meds[1].width


def dark_photon(cls, p: Point, unverified: bool) -> Outcome | None:
    """Retain the source CL; unavailable conversions are pending at 95%. Above 200 GeV the dark photon's LHC and
    electroweak-precision limits are not records yet: pending, never silent (audit M14)."""
    if family(cls) == "inelastic_dark_photon":
        return Outcome(name=DARK_PHOTON, excluded=None,
                       why="the inelastic A′ decays to χ₁χ₂ with χ₂ → χ₁ f f̄ (semi-visible, possibly displaced); "
                           "DarkCast's visible and invisible limits do not apply as published")
    if family(cls) == "dark_photon" and p.m_med > REACH_GEV:
        return Outcome(name=DARK_PHOTON, excluded=None,
                       why=f"m_A′ = {p.m_med:.3g} GeV: the LHC dilepton and electroweak-precision limits above "
                           f"{REACH_GEV:.0f} GeV are not yet records")
    result = _dark_photon_native(cls, p, unverified)
    if result is None:
        return None
    record = s._record("darkcast-dark-photon")
    # Each search keeps its own CL (data/darkcast_searches.yaml): a 90% exclusion stays native and is pending at 95%;
    # an "allowed" carries over to 95% (the owner's record review, 2026-10-13).
    return result.model_copy(update={"highest_confidence_level": 0.95, "source": record.source}).at95()


def _dark_photon_native(cls, p: Point, unverified: bool) -> Outcome | None:
    generic = _generic_dark_photons(cls, p)
    if generic is not None:
        from adroit.parameter_space.resonances import _strongest
        return _strongest([Outcome(name=DARK_PHOTON, excluded=None,
                                   why=f"m_A′ = {m:.3g} GeV: the LHC dilepton and electroweak-precision limits above "
                                       f"{REACH_GEV:.0f} GeV are not yet records") if m > REACH_GEV else
                           _edges([_darkcast(epsilon, m, width, invisible, unverified, visible)
                                   for width, invisible, visible in corners], unknown)
                           for epsilon, m, corners, unknown in generic])
    if family(cls) != "dark_photon" or p.m_med > REACH_GEV:
        return None
    return _darkcast(p.g_q, p.m_med, cls.bosons(p)[0][1].width, _dark_photon_branching(cls, p), unverified)


PHOTON_PATTERN = 1e-3            # a generic vector's couplings are a dark photon's within this residual (P4)


def _generic_dark_photons(cls, p: Point) -> list[tuple] | None:
    """A generic model's new vectors whose couplings are photon-like (``generic_portrait``: residual below
    ``PHOTON_PATTERN``, no Z part), as (ε, m, each extreme assignment of (Γ, BR(invisible), the share of Standard
    Model pairs), what the unresolved decays and the hadronic window leave unknown: ``assignments``,
    ``unresolved_reason``); None for any other model. ε is DarkCast's, relative to
    the electron's charge at the Thomson limit: the photon-like coefficient times the model's photon coupling to a
    unit charge over e(0) (a spec that writes −κ e Q_f with e at the Thomson limit gives ε = κ)."""
    from adroit.model_building.gauge_basis import E_THOMSON
    from adroit.parameter_space.portals import generic_portrait as gp
    from adroit.parameter_space.portals.generic import GenericModel
    if not isinstance(cls, GenericModel):
        return None
    out = []
    unit = abs(gp._standard()["A"]["e"][0])                 # G2's photon coupling to a unit charge
    for m in gp.portraits(cls, p):
        if m.spin != 1 or m.pattern_residual > PHOTON_PATTERN or abs(m.z_like) > PHOTON_PATTERN * abs(m.photon_like):
            continue
        epsilon = abs(m.photon_like) * unit / E_THOMSON
        out.append((epsilon, m.mass_gev, m.assignments(), m.unresolved_reason()))
    return out


def _darkcast(epsilon: float, m: float, width: float, invisible: float, unverified: bool,
              visible: float | None = None) -> Outcome | None:
    """DarkCast's visible (prompt, displaced) and invisible limits on a dark photon of kinetic mixing ε, mass m, width Γ,
    invisible branching fraction and share of Standard Model pairs (``_dark_photon_native``'s rules; 1 − BR(invisible)
    unless given). A visible search reads the Standard Model pairs' resonance, which a new state's cascade does not
    make, so their exact share decides it; the displaced searches, whose limits are the minimal dark photon's lifetime,
    apply only to a dark photon that decays to Standard Model pairs alone (the owner's decision #7, 2026-10-20)."""
    blocked = s._blocked(DARK_PHOTON, "darkcast-dark-photon", unverified)
    if blocked:
        return blocked
    if s._tool("DarkCast") is None:
        return Outcome(name=DARK_PHOTON, excluded=None, why="DarkCast is not in the tools folder (adroit setup --fetch)")
    visible = 1.0 - invisible if visible is None else visible
    minimal = invisible == 0.0 and visible == 1.0
    groups = [(VISIBLE_PROMPT, epsilon * math.sqrt(visible)), (INVISIBLE, epsilon * math.sqrt(invisible))]
    if minimal:
        groups.append((VISIBLE_DISPLACED, epsilon))
    exclusions, covered, skipped, ratio = [], [], [], None
    for stems, coupling in groups:
        for stem in stems:
            verdict = s.darkcast_excludes(stem, m, coupling) if coupling > 0 else None
            if verdict is None:
                continue
            gate = _darkcast_width_gate(stem, width, m, minimal=minimal)
            if gate:
                # Outside the search's narrow-peak assumption its limit says nothing, either way: a broader signal
                # samples other masses, backgrounds and efficiencies (the owner's record review, 2026-10-13).
                skipped.append(gate)
                continue
            covered.append(stem)
            r = s.darkcast_ratio(stem, m, coupling)
            if verdict:
                exclusions.append((s.darkcast_info(stem)["cl"] or 0.90, r or 1.0, stem))
            else:
                ratio = max(ratio or 0.0, r or 0.0)
    return _dark_photon_verdict(exclusions, covered, skipped, ratio, invisible, m)


def _dark_photon_verdict(exclusions: list, covered: list[str], skipped: list[str], ratio: float | None,
                         invisible: float, m: float) -> Outcome:
    """Excluded by the highest-CL applicable search that excludes (its CL kept); else undecided if any search covering
    the mass cannot apply at this width; else allowed at the lowest CL among them; else no search covers it."""
    if exclusions:
        cl, r, stem = max(exclusions)
        return Outcome(name=DARK_PHOTON, excluded=True, why=stem, value=invisible, ratio=max(1.0, r),
                       confidence_level=cl)
    if skipped:
        return Outcome(name=DARK_PHOTON, excluded=None, value=invisible, why="; ".join(skipped))
    if covered:
        cl = min(s.darkcast_info(stem)["cl"] or 0.90 for stem in covered)
        return Outcome(name=DARK_PHOTON, excluded=False, value=invisible, ratio=ratio, confidence_level=cl)
    return Outcome(name=DARK_PHOTON, excluded=None, why=f"no recorded search covers m_A′ = {m:.3g} GeV")


def _darkcast_resolution(info: dict, m: float) -> float | None:
    """A search's mass resolution σ_m (GeV) at m, as its paper states it (data/darkcast_searches.yaml): a formula; the
    smallest σ quoted; or, for a missing-mass search, σ(M²)/(2m), at most 10% of m. None if unstated."""
    if "resolution_formula_gev" in info:
        formula = info["resolution_formula_gev"]
        return formula["constant"] + formula["per_mass"] * m
    if info.get("resolution_m2_gev2"):
        return min(info["resolution_m2_gev2"] / (2.0 * m), DARKCAST_NARROW * m)
    return info.get("resolution_gev")


def _darkcast_width_gate(stem: str, width: float, m: float, minimal: bool) -> str:
    """'' if a DarkCast search applies to an A′ of this width at m, else why not (the owner's record review,
    2026-10-13): a mass-peak search only below its resolution, or, with an unstated resolution, only to the minimal
    dark photon (no A′ → χχ̄; its width ∝ ε² is far below any resolution); a missing-energy search for Γ/m ≤ 10%; a
    beam dump is applied only to the minimal dark photon."""
    info = s.darkcast_info(stem)
    if info["signal"] == "beam dump":
        return ""
    if info["signal"] == "missing energy":
        return "" if width <= DARKCAST_NARROW * m else (f"{info['name']}: Γ/m = {100 * width / m:.0f}% is above the "
                                                        f"{100 * DARKCAST_NARROW:.0f}% ADROIT takes as narrow")
    sigma = _darkcast_resolution(info, m)
    if sigma is None:
        return "" if minimal else (f"{info['name']}: its mass resolution is not stated, so it is applied only where "
                                   "the A′ cannot decay to dark matter")
    return "" if width < sigma else (f"{info['name']}: Γ = {1e3 * width:.3g} MeV is not below its mass resolution, "
                                     f"{1e3 * sigma:.3g} MeV")


# --- flavour --------------------------------------------------------------------------------------------------

def flavour(cls, p: Point, unverified: bool) -> Outcome | None:
    """Retain the source CL; unavailable conversions are pending at 95%."""
    result = _flavour_native(cls, p, unverified)
    if result is None:
        return None
    record = s._record("flavour-b-to-k-invisible")
    return result.model_copy(update={"confidence_level": record.confidence_level,
                                     "source": record.source}).at95()


def _flavour_native(cls, p: Point, unverified: bool) -> Outcome | None:
    """B⁺ → K⁺ a for the pseudoscalar portal with Yukawa-like couplings (g_Y = g_q/√2), or a generic model's light
    CP-odd scalars with Yukawa-like quark couplings (``_generic_flavour``, P4), the strongest outcome kept."""
    generic = _generic_flavour(cls, p)
    if isinstance(generic, str):
        return Outcome(name=FLAVOUR, excluded=None, why=generic)
    if generic is not None:
        outcomes = [_edges([_b_to_k(m, g, edge, unverified) for edge in bounds], unknown)
                    for m, g, bounds, _, _, unknown, _ in generic]
        return _strongest(outcomes) if outcomes else None
    if not (isinstance(cls, ScalarClass) and cls.dm_pseudoscalar and cls.sm_pseudoscalar) or p.m_med >= s.M_B - s.M_K:
        return None
    low, high, unknown = cls.width_bounds(p)            # a's hadronic width, in the hadronic window 0 ≤ Γ_had ≤ m_a
    to_dm = cls._widths(p)[0].get("dm", 0.0)
    edges = sorted({to_dm / w if w > 0 else 0.0 for w in (low, high)})
    return _edges([_b_to_k(p.m_med, p.g_q, invisible, unverified) for invisible in edges], unknown)


FLAVOUR_MUMU = "flavour (B → K a, a → μμ)"
LHCB_WINDOW_GEV = (0.25, 0.41)      # ADROIT's choice: LHCb's lowest mass to 3m_π, where a decays only to leptons and
#                                     photons (Dolan et al. §2.2); above, its hadronic decays are not computed
LHCB_TAU_PS = (0.1, 1000.0)         # LHCb's lifetimes, 0.1 < τ(χ) < 1000 ps (the paper's text), 41 of them
HBAR_GEV_PS = 6.582119569e-13       # ħ in GeV ps


def b_to_k_mumu(cls, p: Point, unverified: bool) -> Outcome | None:
    """LHCb's B⁺ → K⁺a(→ μμ) (record lhcb-1612.07818-b-to-k-mumu) for a light pseudoscalar with Yukawa-like quark
    couplings, as BaBar's invisible search (``_flavour_native``): the library's pseudoscalar portal or a generic
    model's light CP-odd scalars (``_generic_flavour``); BR(B → K a) from the BaBar record's inputs, BR(a → μμ) and
    the lifetime from the a's widths to leptons and dark matter at tree level and to two photons at one loop
    (``searches.pseudoscalar_photon_width``, Dolan et al. eq. (B.2)), reliable only below 3m_π
    (``LHCB_WINDOW_GEV``)."""
    generic = _generic_flavour(cls, p)
    if isinstance(generic, str):
        return None
    if generic is not None:
        found = [_lhcb_mumu(m, g, mumu * width / (width + photons) if width + photons > 0 else 0.0, width + photons,
                            unverified) for m, g, _, mumu, width, _, photons in generic]
        found = [o for o in found if o is not None]
        return _strongest(found) if found else None
    if not (isinstance(cls, ScalarClass) and cls.dm_pseudoscalar and cls.sm_pseudoscalar) or \
            not LHCB_WINDOW_GEV[0] <= p.m_med <= LHCB_WINDOW_GEV[1]:
        return None
    _, fermions = cls._couplings(p)            # below 3m_π: the quark channels closed, no hadronic width unknown
    width = cls.width(p) + s.pseudoscalar_photon_width(p.m_med, {f.name: g for f, _, g in fermions})
    mu, _, g_mu = next(x for x in fermions if x[0].name == "mu")
    partial = 0.0
    if p.m_med > 2 * mu.mass_gev:
        partial = p.m_med * g_mu ** 2 * math.sqrt(1 - 4 * mu.mass_gev ** 2 / p.m_med ** 2) / (8 * math.pi)
    return _lhcb_mumu(p.m_med, p.g_q, partial / width if width > 0 else 0.0, width, unverified)


def _lhcb_mumu(m_a: float, g_q: float, mumu: float, width: float, unverified: bool) -> Outcome | None:
    """One pseudoscalar against LHCb's map: BR(B → K a) × BR(a → μμ) over the limit at (m_a, τ_a); None outside the
    window, undecided outside the map's lifetimes or in a vetoed mass."""
    if not LHCB_WINDOW_GEV[0] <= m_a <= LHCB_WINDOW_GEV[1] or mumu <= 0:
        return None
    blocked = (s._blocked(FLAVOUR_MUMU, "lhcb-1612.07818-b-to-k-mumu", unverified)
               or s._blocked(FLAVOUR_MUMU, "flavour-b-to-k-invisible", unverified))   # its theory inputs (AL1-07)
    if blocked:
        return blocked
    tau = HBAR_GEV_PS / width if width > 0 else math.inf
    if not LHCB_TAU_PS[0] <= tau <= LHCB_TAU_PS[1]:
        return Outcome(name=FLAVOUR_MUMU, excluded=None, why=f"τ_a = {tau:.3g} ps is outside LHCb's 0.1–1000 ps")
    m_mev = m_a * 1e3
    limit = lhcb_limit(s._bundled("lhcb-1612.07818-b-to-k-mumu")["rows"], m_mev, math.log10(tau))
    if limit is None:
        return Outcome(name=FLAVOUR_MUMU, excluded=None, why=f"m_a = {m_mev:.4g} MeV is in a mass LHCb vetoes")
    data = s._record("flavour-b-to-k-invisible").data
    br = s.b_to_k_pseudoscalar(m_a, g_q / math.sqrt(2.0), data["h_s_per_g_y"], data["f0"], data["f0_pole_gev2"],
                               data["mb_minus_ms_gev"])
    ratio = br * mumu / limit
    return Outcome(name=FLAVOUR_MUMU, excluded=ratio > 1.0, ratio=ratio, value=br * mumu)


def lhcb_limit(rows: list[dict], m_mev: float, log_tau: float) -> float | None:
    """LHCb's limit at (m, τ): each row is its limit at one lifetime, τ = 10^k ps (k = −1, −0.9, …, 3; the figure draws
    each from its lifetime up one cell, so its top row reaches 10^3.1 ps, past the paper's 1000 ps), its mass segments
    the figure's cells. Between two of its lifetimes, the weaker of their two limits at m (the true limit between
    them is not shown); exactly at one, its own. None where either row vetoes m (no segment there)."""
    grid = [r["log10_tau_ps"] for r in rows]
    k = bisect.bisect_right(grid, log_tau + 1e-9) - 1
    if k < 0 or log_tau > grid[-1] + 1e-9:
        return None
    near = [rows[k]] if abs(grid[k] - log_tau) <= 1e-9 or k == len(rows) - 1 else [rows[k], rows[k + 1]]
    found = [next((v for lo, hi, v in r["segments"] if lo <= m_mev <= hi), None) for r in near]
    return None if None in found else 10 ** max(found)


EWPT = "electroweak precision (S, T)"
CDF_FLAG = "the fit with CDF's m_W (PDG 2024 eq. 10.107) would {}: a flag, the owner's decision"


def electroweak_precision(cls, p: Point, unverified: bool) -> Outcome | None:
    """S and T at one loop, exactly (``constraints.oblique``), against PDG 2024's fit with U = 0 (record
    pdg-2024-electroweak-st): the inert doublet (the library's UFO or a generic dark doublet, ``_generic_inert``) and
    the 2HDM+a at alignment (the library's UFO or a generic model read as it). Excluded where χ² of (S, T) exceeds
    5.99 (two degrees of freedom, 95%); the fit with CDF's m_W only flags (the owner, 2026-10-19)."""
    from adroit.constraints import oblique
    from adroit.parameter_space.portals import generic_2hdma
    inert = _generic_inert(cls, p)
    if isinstance(inert, str):
        return Outcome(name=EWPT, excluded=None, why=inert)
    found = generic_2hdma.match(cls, p)
    if isinstance(found, str):
        return Outcome(name=EWPT, excluded=None, why=found)
    if inert is not None:
        st = oblique.inert_doublet(*inert)
    elif "lep_inert_doublet" in getattr(cls, "searches", []):
        model = cls.model(p)
        st = oblique.inert_doublet(*(model.particles[n].mass for n in (cls.dm, *cls.partners[:2])))
    elif found is not None or "atlas_2hdma" in getattr(cls, "searches", []):
        ufo, q = found.portal() if found is not None else (cls, p)
        x = ufo._overrides(q)
        if abs(x["sinbma"] - 1.0) > 1e-9:
            return Outcome(name=EWPT, excluded=None, why=f"sin(β − α) = {x['sinbma']:.4g}: S and T are computed at "
                                                         "alignment")
        st = oblique.two_hdm_a(x["mh2"], x["mh3"], x["mh4"], x["mhc"], x["sinp"])
    else:
        return None
    blocked = s._blocked(EWPT, "pdg-2024-electroweak-st", unverified)
    if blocked:
        return blocked
    d = s._record("pdg-2024-electroweak-st").data
    chi2 = _st_chi2(st, d["s"], d["t"], d["sigma_s"], d["sigma_t"], d["rho"])
    cdf = _st_chi2(st, d["cdf_s"], d["cdf_t"], d["cdf_sigma_s"], d["cdf_sigma_t"], d["rho"])
    excluded = chi2 > d["chi2_95"]
    flags = [CDF_FLAG.format("exclude it" if not excluded else "allow it")] if (cdf > d["chi2_95"]) != excluded else []
    return Outcome(name=EWPT, excluded=excluded, value=chi2, delta_chi2=chi2, flags=flags,
                   why=f"S = {st[0]:.3g}, T = {st[1]:.3g}")


def _st_chi2(st: tuple[float, float], s0: float, t0: float, ds: float, dt: float, rho: float) -> float:
    """(S − S₀, T − T₀) against the fit's correlated Gaussian."""
    a, b = (st[0] - s0) / ds, (st[1] - t0) / dt
    return (a * a - 2 * rho * a * b + b * b) / (1 - rho * rho)


LEP_CHARGED = "LEP (charged partners)"
LEP_REACH_GEV = 104.0               # LEP's highest √s/2: a heavier charged state was not pair produced
LEPTON_PARTNERS = {"muR": "mu", "tauR": "tau", "eR": "e"}


def lep_charged(cls, p: Point, unverified: bool) -> Outcome | None:
    """LEP's searches for charged partners below its reach (``LEP_REACH_GEV``): a chargino-like fermion (the charged
    member of a doublet or triplet; ALEPH at any mass splitting, DELPHI's by splitting) and a right-handed smuon- or
    stau-like scalar (OPAL), for the library's t-channel lepton partners and a generic model's Z₂-odd charged states;
    another charged state below the reach is undecided, its search not a record. An inert doublet's charged state is
    left to LEP's inert-doublet limit (inert_doublet)."""
    if isinstance(_generic_inert(cls, p), tuple):
        return None
    states = _lep_states(cls, p)
    found = [_lep_state(kind, lepton, mass, split, unverified, note) for kind, lepton, mass, split, note in states
             if mass < LEP_REACH_GEV]
    return _strongest(found) if found else None


def _lep_states(cls, p: Point) -> list[tuple[str, str, float, float, str]]:
    """(kind, lepton, mass, mass − m_χ, note) of each Z₂-odd charged colourless state: kind 'chargino', 'wino' (a
    triplet's), 'slepton' (an SU(2)-singlet scalar with |Y| = 1; the lepton it joins to the dark matter), 'cascade'
    (one of these whose decay is not the search's, the note says why) or 'other'.

    A search's bound holds for its decay: a chargino's to the dark matter through a W (LEP's χ̃± → χ̃⁰W*), a smuon's
    or stau's to its lepton and the dark matter. So the state must join the dark matter through such a vertex of the
    model's own rules, and its splitting is from the dark matter only then; a state whose W partner is another
    neutral state, or with no such vertex, is not the search's (the tactical audit's T20-07: a decoupled singlet's
    mass had set a doublet's "splitting")."""
    from adroit.parameter_space.portals.generic import GenericModel
    if family(cls) == "t_channel" and cls.partner in LEPTON_PARTNERS:
        return [("slepton", LEPTON_PARTNERS[cls.partner], p.m_med, p.m_med - p.m_chi, "")]
    if not isinstance(cls, GenericModel):
        return []
    from adroit.parameter_space.portals.generic_checks import dominant_field
    mb, rules, _ = cls.at(p)
    dark = mb.spectrum.dark_matter()
    out = []
    for state in mb.spectrum.states:
        if state.parity != -1 or abs(abs(state.charge) - 1) > 1e-9 or state.colour != "1" or state.kind == "goldstone":
            continue
        f = dominant_field(mb, state)
        kind, lepton, note = "other", "", ""
        if f.spin == 0.5 and f.charges.su2 in (2, 3):
            kind = "wino" if f.charges.su2 == 3 else "chargino"
            partners = _w_partners(rules, state.name)
            if dark.name not in partners:
                kind, note = "cascade", (f"its W partners ({', '.join(sorted(partners)) or 'none'}) do not include "
                                         f"the dark matter {dark.name}: LEP's chargino searches assume that decay")
        elif f.spin == 0 and f.charges.su2 == 1 and math.isclose(abs(f.charges.hypercharge), 1.0):
            kind, lepton = "slepton", _joined_lepton(cls.model_spec(), f.name)
            if lepton and not _joins(rules, (state.name, lepton, dark.name)):
                kind, note = "cascade", (f"no vertex joins it to the {lepton} and the dark matter {dark.name}: OPAL's "
                                         f"slepton search assumes that decay")
        out.append((kind, lepton, state.mass_gev, state.mass_gev - dark.mass_gev, note))
    return out


def _w_partners(rules, name: str) -> set[str]:
    """The states a state joins through a W vertex of the rules (antiparticle marks dropped)."""
    out: set[str] = set()
    for v in rules.vertices:
        legs = [leg.rstrip("~") for leg in v.legs]
        if len(legs) == 3 and "W" in legs and name in legs:
            out |= {leg for leg in legs if leg not in ("W", name)}
    return out


def _joins(rules, names: tuple[str, ...]) -> bool:
    """Whether one three-point vertex of the rules joins exactly these states (antiparticle marks dropped)."""
    return any(len(v.legs) == 3 and sorted(leg.rstrip("~") for leg in v.legs) == sorted(names) for v in rules.vertices)


def _joined_lepton(spec, field: str) -> str:
    """The charged lepton a scalar's Yukawa terms join it to ("mu", "tau", "e"), or "" if none or several."""
    names = {"mu": "mu", "muR": "mu", "tau": "tau", "tauR": "tau", "e": "e", "eR": "e"}
    found = {names[o.field] for t in spec.terms if any(o.field == field for o in t.fields)
             for o in t.fields if o.field in names}
    return found.pop() if len(found) == 1 else ""


def _lep_state(kind: str, lepton: str, mass: float, split: float, unverified: bool, note: str = "") -> Outcome:
    """One charged state against the LEP records (``lep_charged``)."""
    if kind == "cascade":
        return Outcome(name=LEP_CHARGED, excluded=None, why=f"a charged state at {mass:.4g} GeV: {note}")
    if kind in ("chargino", "wino"):
        blocked = s._blocked(LEP_CHARGED, "lep-charginos", unverified)
        if blocked:
            return blocked
        d = s._record("lep-charginos").data
        steps = ((3.0, d["from_3_gev"]), (5.0, d["from_5_gev"]),
                 (10.0, d["wino_from_10_gev"] if kind == "wino" else d["from_10_gev"]))
        excluded = mass < d["any_split_gev"] or any(split >= floor and mass < bound for floor, bound in steps)
        return Outcome(name=LEP_CHARGED, excluded=excluded, value=mass,
                       why=f"a chargino-like state at {mass:.4g} GeV, {split:.3g} GeV above the dark matter")
    if kind == "slepton" and lepton in ("mu", "tau"):
        blocked = s._blocked(LEP_CHARGED, "opal-hep-ex-0309014-sleptons", unverified)
        if blocked:
            return blocked
        d = s._record("opal-hep-ex-0309014-sleptons").data
        bound, floor = d[f"{lepton}_r_gev"], d[f"{lepton}_r_split_gev"]
        if split < floor:
            return Outcome(name=LEP_CHARGED, excluded=None, why=f"the right-handed {lepton} partner is {split:.3g} GeV "
                           f"above the dark matter; OPAL's {bound:g} GeV holds from a {floor:g} GeV splitting")
        return Outcome(name=LEP_CHARGED, excluded=mass < bound, value=mass)
    return Outcome(name=LEP_CHARGED, excluded=None, why=f"a charged {kind if kind != 'other' else 'state'} at "
                   f"{mass:.4g} GeV{' (' + lepton + ')' if lepton else ''}: LEP's search for it is not a record")


def strongest(outcomes: list) -> Outcome | None:
    """Several outcomes of one search as one (None where there is none): an exclusion if any (the largest ratio), else
    an undecided one naming every reason, else the allowed one with the largest ratio. The one rule for a point's
    verdict (``scan._by_name``, AL2-05), a generic model's several mediators (``resonances``), an exported observation
    and a ratio's level (AL3-14: those had taken the first)."""
    found = [o for o in outcomes if o is not None]
    if len(found) <= 1:
        return found[0] if found else None
    excluding = [o for o in found if o.excluded]
    waiting = [o for o in found if o.excluded is None]
    if excluding:
        return max(excluding, key=lambda o: o.ratio or 0.0)
    if waiting:
        return waiting[0].model_copy(update={"why": "; ".join(dict.fromkeys(o.why for o in waiting if o.why))})
    return max(found, key=lambda o: o.ratio or 0.0)


def _strongest(outcomes: list[Outcome]) -> Outcome:
    """An exclusion if any, else an undecided outcome if any, else the allowed one with the largest ratio."""
    return (next((o for o in outcomes if o.excluded), None) or next((o for o in outcomes if o.excluded is None), None)
            or max(outcomes, key=lambda o: o.ratio or 0.0))


def _distinct(bounds: tuple[float, float]) -> tuple[float, ...]:
    """BR(invisible)'s extreme assignments, one value where they agree (``generic_portrait.invisible_bounds``)."""
    return tuple(dict.fromkeys(bounds))


def _edges(outcomes: list[Outcome], unknown: str) -> Outcome:
    """One search judged at each extreme assignment (the owner's decision #7, 2026-10-20; the hadronic window's
    widths): a single outcome is itself; else the decision every assignment gives, from the assignment nearer the
    limit (the smaller ratio of exclusions, the larger of allowed), flagged with ``unknown``; else pending, with
    ``unknown`` and the pending assignment's own reason, or the search deciding differently at two assignments. The
    native-CL decision is reconciled the same way (the auditor's RC20-04, 2026-10-20: a native exclusion at one assignment
    had been kept unqualified where another allowed): kept only where every assignment gives it, else None."""
    if len(outcomes) == 1:
        return outcomes[0]

    def ratio(o: Outcome) -> float:
        return o.ratio if o.ratio is not None else o.native_ratio or 0.0
    native = _native_edges(outcomes)
    decided = {o.excluded for o in outcomes}
    if len(decided) == 1 and None not in decided:
        chosen = (min if outcomes[0].excluded else max)(outcomes, key=ratio)
        return chosen.model_copy(update={"flags": chosen.flags + [f"{unknown}; decided alike at both"], **native})
    pending = next((o for o in outcomes if o.excluded is None), None)
    why = f"{unknown}; {pending.why}" if pending is not None and pending.why else \
        f"{unknown}; the search excludes at one assignment and allows at the other"
    base = pending if pending is not None else outcomes[0]
    return base.model_copy(update={"excluded": None, "value": None, "ratio": None, "why": why, **native})


def _native_edges(outcomes: list[Outcome]) -> dict:
    """The native-CL decision every assignment gives, with the ratio nearest its limit; None where they differ or
    any is undecided."""
    natives = {o.native_excluded for o in outcomes}
    if len(natives) != 1 or None in natives:
        return {"native_excluded": None, "native_ratio": None}
    (excluded,) = natives
    ratios = [o.native_ratio for o in outcomes if o.native_ratio is not None]
    return {"native_excluded": excluded, "native_ratio": (min if excluded else max)(ratios) if ratios else None}


def _generic_flavour(cls, p: Point) -> list[tuple] | str | None:
    """A generic model's new CP-odd scalars below m_B − m_K, each as (m_a, g_q, BR(invisible)'s two extreme assignments,
    BR(μμ), Γ, what the unresolved decays leave unknown: ``invisible_bounds``, Γ(a → γγ) at one loop from its own
    fermion couplings when its channels have no photon pair: ``searches.pseudoscalar_photon_width``) with g_q its quarks'
    Yukawa-like factor (L ⊃ −i g_q (m_q/v) a q̄γ⁵q: each quark's pseudoscalar coupling over the h's, the h's taken in the
    masses the state's couplings carry, the model's declared Yukawa inputs (``yukawa.carried_masses``; the owner's #2),
    the same for every quark it couples to, to 10⁻⁶; leptons may differ, as the library's g_ℓ). None for any other model (or without
    such a scalar); the reason for a light CP-odd scalar coupled to quarks otherwise, since the record's b → s a is the
    top loop of Yukawa-like couplings (Dolan et al.)."""
    from adroit.parameter_space.portals import generic_portrait as gp
    from adroit.parameter_space.portals.generic import GenericModel
    if not isinstance(cls, GenericModel):
        return None
    from adroit.model_building import yukawa
    sm = gp._standard()["h"]
    out = []
    for m in gp.portraits(cls, p):
        quarks = [c for c in m.standard_model if c.fermion in QUARK_NAMES]
        if m.spin != 0 or m.mass_gev >= s.M_B - s.M_K or not quarks:
            continue
        if m.cp != "odd":
            return f"{m.name} below m_B − m_K couples to quarks as a {m.cp or 'mixed'} scalar; the record's B → K a is a pseudoscalar's"
        carried = yukawa.carried_masses(cls.at(p)[0], m.name)
        if carried is None:
            return (f"{m.name} mixes the Higgs boson with a new scalar under a declared Yukawa convention: its quark "
                    "couplings carry two conventions")
        factors = [c.odd / (sm[c.fermion][0] * carried[c.fermion] / yukawa.mass(yukawa.SM, c.fermion))
                   for c in quarks]
        if len(quarks) < len(QUARK_NAMES) or max(factors) - min(factors) > 1e-6 * max(abs(f) for f in factors):
            return (f"{m.name}'s quark couplings are not Yukawa-like (each quark's mass times one factor): the "
                    "record's b → s a is the top loop of Yukawa-like couplings")
        photons = 0.0 if m.partial("A", "A") > 0 else \
            s.pseudoscalar_photon_width(m.mass_gev, {c.fermion: c.odd for c in m.standard_model})
        out.append((m.mass_gev, abs(factors[0]), _distinct(m.invisible_bounds()),
                    m.partial("mu", "mu~") / m.width_gev if m.width_gev else 0.0, m.width_gev, m.unresolved_reason(),
                    photons))
    return out or None


QUARK_NAMES = ("u", "d", "s", "c", "b", "t")


def _b_to_k(m_a: float, g_q: float, invisible: float, unverified: bool) -> Outcome:
    """BaBar's B⁺ → K⁺ + invisible on a pseudoscalar of mass m_a with Yukawa-like factor g_q (g_Y = g_q/√2) and
    invisible branching fraction ``invisible``."""
    blocked = s._blocked(FLAVOUR, "flavour-b-to-k-invisible", unverified)
    if blocked:
        return blocked
    data = s._record("flavour-b-to-k-invisible").data
    s_b = (m_a / s.M_B) ** 2
    if s_b > data["s_b_max"]:
        return Outcome(name=FLAVOUR, excluded=None, why=f"m_a = {m_a:.3g} GeV (s_B = {s_b:.2f}) is above BaBar's "
                       f"signal region s_B < {data['s_b_max']}: its s_B-binned partial branching fractions are not yet "
                       "in the record")
    br = s.b_to_k_pseudoscalar(m_a, g_q / math.sqrt(2.0), data["h_s_per_g_y"], data["f0"], data["f0_pole_gev2"],
                               data["mb_minus_ms_gev"])
    ratio = br * invisible / data["br_limit"]
    if ratio > 1.0:
        return Outcome(name=FLAVOUR, excluded=True, value=ratio, ratio=ratio)
    if br * (1.0 - invisible) > data["visible_floor"]:
        return Outcome(name=FLAVOUR, excluded=None, value=br * invisible / data["br_limit"],
                       why="a decays visibly: LHCb's B → K a (→ μμ) is compared separately (250–410 MeV); B → K a "
                           "(→ hadrons) is not yet a record")
    return Outcome(name=FLAVOUR, excluded=False, value=ratio, ratio=ratio)


# --- Z′ of B − L and L_μ − L_τ --------------------------------------------------------------------------------

def _branching(cls, p: Point, names: tuple[str, ...]) -> float:
    md = cls.mediator(p)
    couplings = cls.fermions(p)
    part = sum(spin1.partial_width(p.m_med, f.mass_gev, f.colours, *couplings[f.name]) for f in spin1.FERMIONS
               if f.name in names)
    return part / md.width if md.width > 0 else 0.0


def dilepton(cls, p: Point, unverified: bool) -> Outcome | None:
    """Applies to a B − L Z′ at m_Z′ ≥ 209 GeV: LEP-II's contact bound on (g/M)² (used from 300 GeV) and ATLAS's
    dilepton-resonance limit on σ·BR(Z′ → ee) from 250 GeV to 4.5 TeV, for Γ/m up to 10%. A generic model's every new
    neutral vector with an e⁺e⁻ channel (P3): ATLAS's limit with its σ (``generic_production``) and BR(ee) (its
    portrait); LEP's contact bound, calibrated on B − L's charges, is not applied to another pattern."""
    import numpy as np
    generic = generic_mediators(cls, p, 1)
    if generic:
        found = [_atlas_dilepton(q.m_med, 100.0 * m.width_gev / m.mass_gev, made.sigma_pb,
                                 m.partial("e", "e~") / m.width_gev, unverified, made.why)
                 for q, _, m, made in generic if m.partial("e", "e~") > 0 and m.width_gev > 0 and m.mass_gev >= 209.0]
        lep = [_lep_contact(g, m.mass_gev, unverified)               # calibrated on B − L's charges: those only
               for g, m in (_generic_pattern(cls, p, B_MINUS_L_CHARGES) or []) if m.mass_gev >= 209.0]
        found = lep + [o for o in found if o is not None]           # each search its own outcome, as B − L's
        return found or None
    if family(cls) != "charged_zprime" or cls.charges != "B-L" or p.m_med < 209.0:
        return None
    out = [_lep_contact(p.g_q, p.m_med, unverified)]
    blocked = s._blocked(DILEPTON, "atlas-1903.06248-dilepton", unverified)
    if blocked:
        return out + [blocked]
    table = s._bundled("atlas-1903.06248-dilepton")
    rows = np.array([[np.nan if v is None else v for v in r] for r in table["rows"]], dtype=float)
    m = p.m_med
    if m > rows[-1, 0]:                    # beyond the search's reach: no information; LEP's contact bound applies
        return out
    if m > DILEPTON_MAX:
        return out + [Outcome(name=DILEPTON, excluded=None,
                              why=f"m_Z′ = {m / 1e3:.2f} TeV is above 4.5 TeV, where the fiducial/LO correction is not "
                                  "calibrated (ATLAS's SSM fiducial σ falls to 0.58 of LO at 6 TeV)")]
    if m < rows[0, 0]:
        return out + [Outcome(name=DILEPTON, excluded=None, why=f"m_Z′ = {m:.3g} GeV is below ATLAS's 250 GeV")]
    width = 100.0 * cls.mediator(p).width / m
    widths = table["widths_pct"]
    if width > widths[-1]:
        return out + [Outcome(name=DILEPTON, excluded=None, why=f"Γ/m = {width:.1f}% is wider than ATLAS's 10%")]
    log_m = np.log(rows[:, 0])

    def at(column: int) -> float:
        good = ~np.isnan(rows[:, column])
        return float(np.exp(np.interp(math.log(m), log_m[good], np.log(rows[good, column]))))

    def limit_at(width_pct: float, column: int) -> float:
        """The observed limit at full resolution (every HEPData mass) where the bundle has it."""
        full = table.get("limits_full", {}).get(f"{width_pct:g}")
        if not full:
            return at(column)
        curve = np.array(full)
        return float(np.exp(np.interp(math.log(m), np.log(curve[:, 0]), np.log(curve[:, 1]))))
    limits = [limit_at(w, 1 + i) for i, w in enumerate(widths)]
    limit = float(np.interp(width, widths, limits))
    correction = table["correction_fid_over_lo"]
    sigma_br = p.g_q ** 2 * at(len(widths) + 1) * _branching(cls, p, ("e",)) * correction
    return out + [Outcome(name=DILEPTON, excluded=sigma_br > limit, value=sigma_br / limit, ratio=sigma_br / limit)]


def _lep_contact(g: float, m: float, unverified: bool) -> Outcome:
    """LEP-II's contact bound on a B − L vector, (g/M)² against its M/g (used from ``LEP_CONTACT_MIN``)."""
    blocked = s._blocked(LEP_CONTACT, "lep-contact-bl", unverified)
    limit = s._record("lep-contact-bl").data["m_over_g_gev"]
    contact = (limit * g / m) ** 2                                 # the effect scales as (g/M)²
    if m < LEP_CONTACT_MIN:                                        # the contact approximation needs M ≫ √s ≈ 209 GeV
        return blocked or Outcome(name=LEP_CONTACT, excluded=None, value=m / g / limit,
                                  why=f"M = {m:.0f} GeV is not ≫ LEP's √s ≈ 209 GeV: the contact bound is used from "
                                      f"{LEP_CONTACT_MIN:.0f} GeV")
    return blocked or Outcome(name=LEP_CONTACT, excluded=contact > 1.0, value=m / g / limit, ratio=contact)


def _atlas_dilepton(m: float, width_pct: float, sigma_pb: float | None, br_ee: float, unverified: bool,
                    why_not: str = "") -> Outcome | None:
    """ATLAS's dilepton-resonance limit (arXiv:1903.06248) on one vector: σ·BR(ee) times the record's fiducial/LO
    correction against the observed limit (fb) at its width, under the same domain as B − L's (250 GeV to 4.5 TeV,
    Γ/m ≤ 10%). σ (pb, MadGraph's per-flavour tables, NNPDF2.3) is brought to the record's own leading order
    (PDF4LHC21, against which its correction was taken) by the ratio of their B − L cross sections at the mass, so
    the flavour decomposition is MadGraph's and the normalisation the record's. None beyond the search's reach or
    where σ is outside the production tables."""
    import numpy as np
    blocked = s._blocked(DILEPTON, "atlas-1903.06248-dilepton", unverified)
    if blocked:
        return blocked
    table = s._bundled("atlas-1903.06248-dilepton")
    rows = np.array([[np.nan if v is None else v for v in r] for r in table["rows"]], dtype=float)
    if m > rows[-1, 0]:
        return None
    if m > DILEPTON_MAX:
        return Outcome(name=DILEPTON, excluded=None, why=f"m = {m / 1e3:.2f} TeV is above 4.5 TeV, where the fiducial/LO "
                       "correction is not calibrated")
    if m < rows[0, 0]:
        return Outcome(name=DILEPTON, excluded=None, why=f"m = {m:.3g} GeV is below ATLAS's 250 GeV")
    widths = table["widths_pct"]
    if width_pct > widths[-1]:
        return Outcome(name=DILEPTON, excluded=None, why=f"Γ/m = {width_pct:.1f}% is wider than ATLAS's 10%")
    if sigma_pb is None:          # inside ATLAS's masses its σ is wanted: undecided with the reason, never absent (AL3-13)
        return Outcome(name=DILEPTON, excluded=None,
                       why=why_not or f"the Z′'s production cross-section is not tabulated at {m:.4g} GeV")
    from adroit.constraints import production
    madgraph_bl = production.sigma_pb(VECTOR_TABLES["B-L"], m)
    if not madgraph_bl:                        # the search applies here: undecided, never silently absent (AL2-14)
        return Outcome(name=DILEPTON, excluded=None, why=production.unavailable(VECTOR_TABLES["B-L"]) or
                       f"MadGraph's {VECTOR_TABLES['B-L']} does not reach {m:.4g} GeV, where ATLAS's limit applies")
    log_m = np.log(rows[:, 0])
    column = table["columns"].index("sigma_lo_bl_g1_fb")
    good = ~np.isnan(rows[:, column])
    record_bl = float(np.exp(np.interp(math.log(m), log_m[good], np.log(rows[good, column]))))
    sigma_br_lo = sigma_pb * record_bl / madgraph_bl * br_ee            # fb, at the record's leading order

    def limit_at(width: float, column: int) -> float:
        full = table.get("limits_full", {}).get(f"{width:g}")
        if not full:
            good = ~np.isnan(rows[:, column])
            return float(np.exp(np.interp(math.log(m), log_m[good], np.log(rows[good, column]))))
        curve = np.array(full)
        return float(np.exp(np.interp(math.log(m), np.log(curve[:, 0]), np.log(curve[:, 1]))))
    limit = float(np.interp(width_pct, widths, [limit_at(w, 1 + i) for i, w in enumerate(widths)]))
    sigma_br = sigma_br_lo * table["correction_fid_over_lo"]
    return Outcome(name=DILEPTON, excluded=sigma_br > limit, value=sigma_br / limit, ratio=sigma_br / limit)


def lmu_ltau(cls, p: Point, unverified: bool) -> list[Outcome] | None:
    """Applies to an L_μ − L_τ Z′: the BaBar/Belle II searches, CCFR's trident limit, and CMS's and ATLAS's Z → 4μ. Its
    muon g − 2 is the model's total (``muon_g2``)."""
    generic = _generic_lmu(cls, p)
    if generic is not None:                     # a generic model's vectors with L_μ − L_τ's charges (P4)
        return [o for args in generic for o in _lmu_outcomes(*args, unverified)] or None
    if family(cls) != "charged_zprime" or cls.charges != "Lmu-Ltau":
        return None
    width, muons, vanilla, invisible = _lmu_numbers(cls, p)
    return _lmu_outcomes(p.g_q, p.m_med, width, muons, vanilla, (invisible,), "", unverified)


def _lmu_dark_width(p: Point) -> float:
    """The library's L_μ − L_τ Z′'s partial width into its (Dirac) dark matter, GeV."""
    from adroit.parameter_space.portals.vector import _width
    return _width(p.m_med, {f.name: (0.0, 0.0) for f in spin1.FERMIONS}, (p.g_chi, 0.0), p.m_chi, "fermion")


def _lmu_numbers(cls, p: Point) -> tuple[float, float, float, float]:
    """(Γ, BR(μμ), BR(μμ) without the dark matter, BR(invisible)) of the library's L_μ − L_τ Z′ at the point. The
    invisible fraction is the dark matter's and the neutrinos' partial widths over the Z′'s own total width
    (``mediator``: its hadrons by the measured R ratio below 2 GeV), as BR(μμ) is (the re-audit's RR22-05, 2026-10-22:
    one minus the visible fermions' free-quark widths had put the R ratio's difference into the invisible fraction)."""
    total = cls.mediator(p).width if hasattr(cls, "mediator") else 0.0
    couplings = cls.fermions(p)
    neutrinos = sum(spin1.partial_width(p.m_med, f.mass_gev, f.colours, *couplings[f.name]) for f in spin1.FERMIONS
                    if f.family == "neutrino")
    invisible = (_lmu_dark_width(p) + neutrinos) / total if total > 0 else 0.0
    return (total, _branching(cls, p, ("mu",)), _branching(cls, p.model_copy(update={"g_chi": 0.0}), ("mu",)),
            invisible)


LMU_PATTERN = 1e-3               # a generic vector's couplings are a charge pattern's within this residual (P4)
# (g_V, g_A) per unit coupling in the portrait's convention: a left-handed neutrino's vector coupling g is (g, −g)/2
LMU_CHARGES = {"mu": (1.0, 0.0), "tau": (-1.0, 0.0), "nu_mu": (0.5, -0.5), "nu_tau": (-0.5, 0.5)}
B_MINUS_L_CHARGES = {**{q: (1 / 3, 0.0) for q in ("u", "d", "s", "c", "b", "t")},
                     **{lep: (-1.0, 0.0) for lep in ("e", "mu", "tau")},
                     **{nu: (-0.5, 0.5) for nu in ("nu_e", "nu_mu", "nu_tau")}}


def _generic_pattern(cls, p: Point, charges: dict) -> list[tuple[float, object]] | None:
    """A generic model's new vectors whose couplings to the Standard Model are ``charges`` times one coupling g
    (and nothing else, residual below ``LMU_PATTERN``), as (g, portrait); None for any other model."""
    import numpy as np
    from adroit.parameter_space.portals import generic_portrait as gp
    from adroit.parameter_space.portals.generic import GenericModel
    if not isinstance(cls, GenericModel):
        return None
    out = []
    for m in gp.portraits(cls, p):
        if m.spin != 1 or not m.standard_model or m.width_gev <= 0:
            continue
        names = sorted({c.fermion for c in m.standard_model} | set(charges))
        g = np.array([v for f in names for v in ((m.coupling(f).even, m.coupling(f).odd) if m.coupling(f) else (0, 0))])
        basis = np.array([v for f in names for v in charges.get(f, (0.0, 0.0))])
        coupling = float(g @ basis / (basis @ basis))
        if np.linalg.norm(g - coupling * basis) <= LMU_PATTERN * np.linalg.norm(g):
            out.append((abs(coupling), m))
    return out


def _generic_lmu(cls, p: Point) -> list[tuple] | None:
    """A generic model's new vectors whose couplings are L_μ − L_τ's (μ and ν_μ +g′, τ and ν_τ −g′, the neutrinos
    left-handed, nothing else; residual below ``LMU_PATTERN``), as ``_lmu_outcomes``' (g′, m, Γ, BR(μμ), BR(μμ)
    among the Standard Model pairs alone, BR(invisible)'s two extreme assignments, what the unresolved decays leave
    unknown); None for any other model. The second BR(μμ) is the vanilla L_μ − L_τ's, which the 4μ limits assume: Γ(μμ)
    over the width into Standard Model fermion pairs alone, neutrinos included, summed from those channels (the auditor's
    RC20-05, 2026-10-20: subtracting the dark matter's pair by a Dirac spelling had left a Majorana pair, χ⁰χ⁰, in the
    denominator; an unresolved pair counted as Standard Model had raised the 4μ coupling, √(BR(μμ)/vanilla), by
    √(1 + Γ_unresolved/Γ_SM pairs), the owner's decision #7). L_μ − L_τ's charges have no quark, so no hadronic window."""
    from adroit.model_building.feynman import SM_FERMIONS
    matched = _generic_pattern(cls, p, LMU_CHARGES)
    if matched is None:
        return None
    pairs = {f.name for f in SM_FERMIONS} | {f"{f.name}~" for f in SM_FERMIONS}
    out = []
    for g_prime, m in matched:
        muons = m.partial("mu", "mu~")
        standard = sum(c.width_gev for c in m.channels if set(c.final) <= pairs)
        out.append((abs(g_prime), m.mass_gev, m.width_gev, muons / m.width_gev,
                    muons / standard if standard > 0 else 0.0, _distinct(m.invisible_bounds()),
                    m.unresolved_reason()))
    return out


def _lmu_outcomes(g: float, m: float, width: float, muons: float, vanilla: float, invisible: tuple[float, ...],
                  unknown: str, unverified: bool) -> list[Outcome]:
    """The BaBar/Belle II searches, CCFR's trident limit and Z → 4μ (CMS, ATLAS) on an L_μ − L_τ vector of coupling g′,
    mass m, width Γ and its branching fractions (``lmu_ltau``), BR(invisible) as its one value or its two extreme
    assignments (``_edges``, with ``unknown`` the reason they leave)."""
    p = Point(m_chi=1.0, m_med=m, g_q=g)
    out = []
    out.append(_edges([_lmu_native_at(p, width, muons, vanilla, edge, unverified) for edge in invisible], unknown))
    trident = _ccfr(p, unverified)
    if trident is not None:
        out.append(Outcome(name=LMU, excluded=trident[0], ratio=trident[1],
                           source=s._record("ccfr-1406.2332-trident").source))
    else:
        out.append(Outcome(name=LMU, excluded=None, why="no applicable verified 95% CCFR limit"))
    four = _z_to_4mu(m, g, width, muons, vanilla, unverified)
    if four is not None:
        out.append(four)
    return out


def _z_to_4mu(m: float, g: float, width: float, muons: float, vanilla: float, unverified: bool) -> Outcome | None:
    """CMS's and ATLAS's Z → 4μ on an L_μ − L_τ vector (the owner, 2026-10-19: each record stands, the stronger
    decides): each limit on g′ for B(Z′ → μμ) = 1/3, applied to g′ √(BR(μμ)/BR(μμ) without the dark matter) (as
    BaBar's), log-interpolated in m, where the Z′ is narrower than the record states. An exclusion decides (the larger
    ratio); else any applicable search that cannot decide (an unsigned record, a width beyond its assumption) leaves the
    outcome undecided, naming every such record and reason; allowed only where every applicable search allows (the
    recheck's RB20-04, 2026-10-20: an allowed reviewed search had hidden an unsigned one). None outside both records'
    masses or below their reach (``FOUR_MU_FLOOR``)."""
    effective = g * math.sqrt(muons / vanilla) if vanilla > 0 else 0.0
    if effective < FOUR_MU_FLOOR:
        return None
    outcomes = []
    for rid, narrow in FOUR_MU.items():
        points = s._bundled(rid)["points"]
        masses = [x for x, _ in points]
        if not masses[0] <= m <= masses[-1]:
            continue
        blocked = s._blocked(Z4MU, rid, unverified)
        if blocked:
            outcomes.append(blocked)
            continue
        source = s._record(rid).source
        if width >= narrow * m:
            outcomes.append(Outcome(name=Z4MU, excluded=None, source=source,
                                    why=f"Γ/m = {width / m:.3g} is above the {narrow:.0%} its limit assumes"))
            continue
        limit = math.exp(float(np.interp(m, masses, [math.log(y) for _, y in points])))
        ratio = effective / limit
        outcomes.append(Outcome(name=Z4MU, excluded=ratio > 1.0, ratio=ratio, source=source))
    if not outcomes:
        return None
    excluding = [o for o in outcomes if o.excluded is True]
    if excluding:
        return max(excluding, key=lambda o: o.ratio)
    waiting = [o for o in outcomes if o.excluded is None]
    if not waiting:
        return max(outcomes, key=lambda o: o.ratio)
    if len(outcomes) == 1:
        return waiting[0]
    allowing = [o for o in outcomes if o.excluded is False]       # one outcome naming every undecided record (B20-11)
    why = "; ".join(dict.fromkeys(o.why for o in waiting if o.why))
    if allowing:
        why += "; " + "; ".join(f"{o.source} allows (ratio {o.ratio:.3g}) but does not decide alone" for o in allowing)
    return Outcome(name=Z4MU, excluded=None, why=why,
                   source="; ".join(dict.fromkeys(o.source for o in waiting if o.source)))


LMU_NATIVE = "L_μ − L_τ (BaBar/Belle II)"


def _lmu_native(cls, p: Point, unverified: bool) -> Outcome:
    """The native 90% searches on the library's L_μ − L_τ Z′ (``_lmu_native_at``)."""
    return _lmu_native_at(p, *_lmu_numbers(cls, p), unverified)


def _lmu_native_at(p: Point, width: float, muons: float, vanilla: float, invisible: float, unverified: bool) -> Outcome:
    """The native 90% searches have a separate applicability gate from CCFR (g′ and m from the point)."""
    blocked = s._blocked(LMU_NATIVE, "lmu-ltau-babar-belle2", unverified)
    if blocked:
        return blocked.model_copy(update={"confidence_level": .9,
                                   "source": s._record("lmu-ltau-babar-belle2").source}).at95()
    decided, ratios, reasons = [], [0.0], []
    if s._tool("DarkCast") is not None and vanilla > 0:
        coupling = p.g_q * math.sqrt(muons / vanilla)
        babar = s.darkcast_excludes("BaBar_TheBABAR2016rlg", p.m_med, coupling)
        if babar is not None and width >= BABAR_4MU_RESOLUTION:      # BaBar's 4μ bump hunt assumes a narrow Z′
            reasons.append(f"BaBar's 4μ limit is for a Z′ narrower than its mass resolution, 1–9 MeV (ADROIT takes "
                           f"the smallest); here Γ = {1e3 * width:.3g} MeV (a broader Z′ needs a width-dependent "
                           "reinterpretation)")
        else:
            decided.append(babar)
            ratios.append(s.darkcast_ratio("BaBar_TheBABAR2016rlg", p.m_med, coupling) or 0.0)
    elif vanilla > 0 and BABAR_4MU_REACH[0] <= p.m_med <= BABAR_4MU_REACH[1]:     # never read as allowed (AL2-04)
        reasons.append("BaBar's 4μ limit (arXiv:1606.03501) is read through DarkCast, which is not in the tools folder "
                       "(adroit setup --fetch)")
    belle = s.interpolate(s._bundled("lmu-ltau-babar-belle2")["points"], p.m_med)
    if belle is not None and width < belle2_resolution(p.m_med):
        coupling = p.g_q * math.sqrt(max(invisible, 0.0))
        decided.append(coupling > belle)
        ratios.append((coupling / belle) ** 2)
    elif belle is not None:                                        # Belle II assumes a negligible width
        reasons.append(f"Belle II's limit is for a Z′ width negligible against its recoil-mass resolution; here "
                       f"Γ = {1e3 * width:.3g} MeV ≥ {1e3 * belle2_resolution(p.m_med):.3g} MeV (arXiv:2212.03066)")
    why = "; ".join(reasons)
    # excluded if a search excludes; undecided while BaBar or Belle II applies but cannot decide (a broad Z′); allowed
    # only if every search that applies allows (a BaBar None is outside its masses and does not apply)
    excluded = (True if any(d is True for d in decided) else None if why else
                False if any(d is not None for d in decided) else None)
    return Outcome(name=LMU_NATIVE, excluded=excluded, ratio=max(ratios), why=why,
                   confidence_level=0.9, source=s._record("lmu-ltau-babar-belle2").source).at95()


# BaBar's e⁺e⁻ → μ⁺μ⁻Z′(→ μ⁺μ⁻) (arXiv:1606.03501, p. 4): narrow-signal templates, "the resolution varies between
# 1−9 MeV"; no mass dependence is given, so ADROIT takes the smallest at every mass (conservative), as for Belle II
# below: Γ_Z′ < 1 MeV (the owner's record review, 2026-10-13: before, Γ/m ≤ 10%, which let a 136 MeV width through).
BABAR_4MU_RESOLUTION = 0.001       # GeV
# The masses BaBar's 4μ search could reach, from the muon pair's threshold to the B factory's √s (GeV): without DarkCast,
# which holds the limit and its own masses, a point here is undecided on it, never allowed (AL2-04)
BABAR_4MU_REACH = (2 * 0.1056584, 10.58)
# Belle II's invisible Z′ (arXiv:2212.03066): "the intrinsic width Γ_Z′ ... is negligible compared with the experimental
# resolution". Its recoil-mass-squared resolution is 0.06–0.23 GeV² (0.06 at 80 GeV², 0.23 at 9 GeV²); ADROIT takes
# the smallest, 0.06 GeV², at every mass (conservative), so σ_M = 0.06 GeV² / (2 M).
BELLE2_RESOLUTION_M2 = 0.06


def belle2_resolution(m_gev: float) -> float:
    """Belle II's recoil-mass resolution (GeV) at M, as ADROIT takes it: the width below which its limit applies."""
    return BELLE2_RESOLUTION_M2 / (2.0 * m_gev)


def _ccfr(p: Point, unverified: bool) -> tuple[bool, float] | None:
    """(excluded, (g′/limit)²) from the CCFR trident record; None if it may not be used or is not fetched."""
    if s._blocked(LMU, "ccfr-1406.2332-trident", unverified) or s._tool("CCFR trident (digitised)") is None:
        return None
    data = s._record("ccfr-1406.2332-trident").data
    if p.m_med > data["highest_mass_gev"]:
        limit = p.m_med / data["heavy_m_over_g_gev"]
    else:
        import numpy as np
        rows = np.loadtxt(s._tool("CCFR trident (digitised)") / "CCFR.txt", ndmin=2)
        rows = rows[rows[:, 0] <= data["highest_mass_gev"]]
        limit = s.interpolate(rows.tolist(), p.m_med)
        if limit is None:
            return None
    return p.g_q > limit, (p.g_q / limit) ** 2


def muon_g2(cls, p: Point, unverified: bool) -> Outcome | None:
    """Muon g − 2 (record muon-g2-2025) from the model's total one-loop contribution, the same calculation for a
    library model and a generic one (the owner's decision #11, 2026-10-20): every new state coupled to the muon, its
    parts summed before the total is compared, so that parts of opposite sign cancel (``g2_parts``). Pending where the
    model has a state coupled to the muon whose contribution is not computed (the total is then unknown), a neutral
    scalar among them: its two-loop Barr–Zee terms can be substantial, so its one loop alone does not give the total
    (the owner, 2026-10-20; Ilisie, arXiv:1502.04199), and a validated bound on the omitted part is deferred. A
    scalar with no coupling to the muon does not count. None where nothing new couples to the muon."""
    parts, unknown, scalars = g2_parts(cls, p)
    if not parts and not unknown and not scalars:
        return None
    blocked = s._blocked(G2, "muon-g2-2025", unverified)
    if blocked:
        return blocked
    total = sum(delta for _, delta in parts)
    named = "; ".join(f"{label}: {delta:.3g}" for label, delta in parts)
    if unknown or scalars:
        reasons = ([f"the neutral-scalar contribution, including relevant two-loop terms, is not computed "
                    f"({', '.join(scalars)})"] if scalars else []) + \
                  ([f"the total Δa_μ is not computed: {'; '.join(unknown)}"] if unknown else [])
        computed = f" (the computed part is {named})" if parts else ""
        return Outcome(name=G2, excluded=None, value=total if parts else None, why="; ".join(reasons) + computed)
    out = _g2(G2, total, unverified)
    return out.model_copy(update={"why": f"Δa_μ = {total:.3g}, the sum of {named}" if len(parts) > 1 else named})


def g2_parts(cls, p: Point) -> tuple[list[tuple[str, float]], list[str], list[str]]:
    """The one-loop parts of Δa_μ that ADROIT computes, as (state, Δa_μ); the states coupled to the muon whose part it
    does not compute; and, apart, the neutral scalars among them (``muon_g2``). Computed (one loop, the record's own convention):
    - a new neutral vector with vector and axial couplings to the muon (``muon_g2_vector`` + ``muon_g2_axial``);
    - a charged scalar with a neutral, colourless fermion (the dark matter, a neutrino or another), joined to the
      muon with one chirality (``muon_g2_scalar_partner``): a μ_R partner, a doublet's or triplet's charged scalar.
    Not computed: a neutral scalar coupled to the muon (its two-loop Barr–Zee terms can compete with its one loop); a
    partner coupled to both chiralities (the chirality flip, enhanced by the fermion's mass); a new fermion coupled to
    the muon; a contact term contributes only beyond one loop."""
    from adroit.parameter_space.portals.generic import GenericModel
    if isinstance(cls, GenericModel):
        return _generic_g2_parts(cls, p)
    return _library_g2_parts(cls, p), *_library_g2_scalars(cls, p)


def _neutral_fermion(x) -> bool:
    return x.spin == 0.5 and abs(x.charge) < 1e-9 and x.colour == "1"


def _vector_g2(g_v: float, g_a: float, m: float) -> float:
    return float(s.muon_g2_vector(g_v, m) + s.muon_g2_axial(g_a, m))


def _library_g2_parts(cls, p: Point) -> list[tuple[str, float]]:
    """A library model's parts (``g2_parts``), from its own couplings: the dark photon's A′ after the mixing's exact
    diagonalisation, a charged Z′'s (L_μ − L_τ's with its loop-induced kinetic mixing), an s-channel vector's, and a
    μ_R partner's. Its other families have no state ``g2_parts`` computes coupled to the muon."""
    fam = family(cls)
    if fam in ("dark_photon", "inelastic_dark_photon"):
        mediators, _, fermions = cls.bosons(p)
        return [("A′", _vector_g2(*fermions["mu"][1], mediators[1].mass))]
    if fam == "charged_zprime":
        g_v, g_a = cls.fermions(p)["mu"]
        return [("Z′", _vector_g2(g_v, g_a, cls.mediator(p).mass))] if g_v or g_a else []
    if isinstance(cls, Spin1Class):
        g_v, g_a = cls.model(p).couplings(next(f for f in spin1.FERMIONS if f.name == "mu"))
        return [("Z′", _vector_g2(g_v, g_a, p.m_med))] if g_v or g_a else []
    if fam == "t_channel" and cls.partner == "muR":
        return [("φ (μ_R partner)", s.muon_g2_scalar_partner(p.g_chi, p.m_med, p.m_chi))]
    return []


def _library_g2_scalars(cls, p: Point) -> tuple[list[str], list[str]]:
    """A library model's states coupled to the muon whose part is not computed, as ``g2_parts``' last two lists: its
    neutral scalars with a coupling to the muon (a scalar or pseudoscalar mediator with g_ℓ ≠ 0, a singlet mixed with
    the Higgs boson, a UFO portal's new neutral scalars with a muon vertex)."""
    from adroit.parameter_space.portals.higgs import SingletMixing
    from adroit.parameter_space.portals.ufo import UFOPortal
    if isinstance(cls, ScalarClass):
        return [], (["S (its g_ℓ)"] if p.g_l else [])
    if isinstance(cls, SingletMixing):
        return [], (["h₂ (mixed with the Higgs boson)"] if p.g_q else [])
    if isinstance(cls, UFOPortal):
        try:
            model = cls.model(p)
        except (OSError, RuntimeError, ValueError) as error:
            return [f"its UFO model could not be read ({str(error)[:120]})"], []
        found = set()
        for v in model.vertices:
            if v.kind != "FFS" or not (complex(v.c) or complex(v.c2)):
                continue
            legs = [model.particles[x] for x in v.legs]
            if sum(abs(x.pdg) == 13 for x in legs) == 2:
                found |= {x.name for x in legs if x.spin == 0 and abs(x.charge) < 1e-9 and abs(x.pdg) != 25}
        return [], sorted(found)
    return [], []


def _generic_g2_parts(cls, p: Point) -> tuple[list[tuple[str, float]], list[str], list[str]]:
    """A generic model's parts (``g2_parts``): its new neutral bosons' couplings to the muon from their portraits, and
    every other three-point vertex joining the muon to a new state from its Feynman rules."""
    from adroit.model_building.feynman import SM_FERMIONS
    from adroit.parameter_space.portals import generic_portrait as gp
    parts, unknown, scalars, bosons = [], [], [], set()
    for m in gp.portraits(cls, p):
        muon = m.coupling("mu")
        if muon is None:
            continue
        bosons.add(m.name)
        if m.spin == 1:
            parts.append((m.name, _vector_g2(muon.even, muon.odd, m.mass_gev)))
        else:
            scalars.append(m.name)
    _, rules, _ = cls.at(p)
    standard = {f.name for f in SM_FERMIONS} | set(gp.STANDARD)
    by = {x.name: x for x in rules.particles} | {x.anti: x for x in rules.particles if x.anti}
    partners: dict[tuple[str, str], tuple[float, bool]] = {}   # (scalar, fermion): coupling, chirality flip
    for v in rules.vertices:
        legs = [leg.rstrip("~") for leg in v.legs]
        new = {leg for leg in legs if leg not in standard} - bosons
        if len(legs) != 3 or "mu" not in legs or not new:
            continue
        other = [leg for leg in legs[:2] if leg != "mu"]
        if v.kind == "FFS" and len(other) == 1 and _neutral_fermion(by[other[0]]) and abs(by[legs[2]].charge) > 1e-9:
            # G2's vertex c + ic₂γ⁵ is (c + ic₂)P_R + (c − ic₂)P_L; its conjugate vertex swaps the two
            chiral = abs(complex(v.c) + 1j * complex(v.c2)), abs(complex(v.c) - 1j * complex(v.c2))
            y, flips = partners.get((legs[2], other[0]), (0.0, False))
            partners[legs[2], other[0]] = (max(y, *chiral), flips or min(chiral) > gp.TINY * max(chiral))
        else:
            unknown.append(f"the vertex {' '.join(v.legs)} joins the muon to a new state ADROIT's g − 2 does not "
                           "compute")
    for (name, fermion), (y, flips) in sorted(partners.items()):
        if flips:
            unknown.append(f"{name} joins {fermion} to the muon with both chiralities (the chirality flip is not "
                           "computed)")
        else:
            parts.append((f"{name} with {fermion}", s.muon_g2_scalar_partner(y, by[name].mass, by[fermion].mass)))
    return parts, list(dict.fromkeys(unknown)), scalars


def _g2(name: str, delta: float, unverified: bool) -> Outcome:
    blocked = s._blocked(name, "muon-g2-2025", unverified)
    if blocked:
        return blocked
    d = s._record("muon-g2-2025").data
    low, high = d["delta_a_mu"] - 1.96 * d["sigma"], d["delta_a_mu"] + 1.96 * d["sigma"]
    chi2 = ((d["delta_a_mu"] - delta) / d["sigma"]) ** 2 - (d["delta_a_mu"] / d["sigma"]) ** 2
    return Outcome(name=name, excluded=not low <= delta <= high, value=delta, delta_chi2=chi2)


# --- partners ----------------------------------------------------------------------------------------------------

def partner(cls, p: Point, unverified: bool) -> Outcome | None:
    """Applies to a t-channel partner (a μ_R partner's muon g − 2 is the model's total, ``muon_g2``): for a u_R or d_R
    partner, ATLAS's one-squark
    contour in (m_φ, m_χ). The contour assumes QCD pair production, which is not established as a lower bound on the
    partner's (``QCD_ONLY``), so it decides nothing: pending inside it and outside (decision D33)."""
    if family(cls) != "t_channel":
        return None
    if cls.partner not in ("uR", "dR"):
        return None
    blocked = s._blocked(SQUARK, "atlas-2010.14293-squark", unverified)
    if blocked:
        return blocked
    from matplotlib.path import Path as Polygon
    contour = s._bundled("atlas-2010.14293-squark")["points"]
    lowest = min(x for x, _ in contour)
    if p.m_med < lowest:
        return Outcome(name=SQUARK, excluded=None, why=f"m_φ = {p.m_med:.3g} GeV is below the search's {lowest:.0f} GeV")
    region = Polygon([*contour, (lowest, 0.0)])
    where = "inside" if region.contains_point((p.m_med, p.m_chi)) else "outside"
    return Outcome(name=SQUARK, excluded=None, why=f"{where} ATLAS's one-squark contour, which assumes QCD pair "
                                                   f"production: {QCD_ONLY}")


# --- models read from UFO files --------------------------------------------------------------------------------------

def inert_doublet(cls, p: Point, unverified: bool) -> Outcome | None:
    """Applies to a UFO model listing ``lep_inert_doublet``, or a generic model whose dark sector is an inert doublet
    (``_generic_inert``, P5): LEP's excluded region in (m_H0, m_A0, m_H±) and the Z and W decay thresholds."""
    generic = _generic_inert(cls, p)
    if generic is None and "lep_inert_doublet" not in getattr(cls, "searches", []):
        return None
    if isinstance(generic, str):
        return Outcome(name=IDM_LEP, excluded=None, why=generic)
    blocked = s._blocked(IDM_LEP, "lep-inert-doublet", unverified)
    if blocked:
        return blocked
    if generic:
        h0, a0, hc = generic
    else:
        model = cls.model(p)
        h0, a0, hc = (model.particles[n].mass for n in (cls.dm, *cls.partners[:2]))
    d = s._record("lep-inert-doublet").data
    excluded = ((h0 < d["h0_below"] and a0 < d["a0_below"] and a0 - h0 > d["split_above"]) or hc < d["charged_below"]
                or h0 + a0 < d["m_z"] or h0 + hc < d["m_w"] or a0 + hc < d["m_w"] or 2.0 * hc < d["m_z"])
    return Outcome(name=IDM_LEP, excluded=excluded)


def _generic_inert(cls, p: Point) -> tuple[float, float, float] | str | None:
    """A generic model's inert doublet (P5's structural match): its new fields are one Z₂-odd colourless scalar SU(2)
    doublet with |Y| = ½ and nothing else, so that its gauge couplings, and LEP's pair production and A₀ → H₀Z*,
    H± → H₀W* decays (Lundström et al.), are the inert doublet's whatever its potential. (m_H₀, m_A₀, m_H±) from the
    model's own spectrum at the point, H₀ the lighter neutral state (A₀ = H₀ if they are one complex state). None if the
    model has no such doublet; the reason if it has one among other new fields."""
    from adroit.parameter_space.portals.generic import GenericModel
    if not isinstance(cls, GenericModel):
        return None
    new = [f for f in cls.model_spec().fields if f.role.value != "standard_model"]
    doublets = [f for f in new if f.dark_parity == -1 and f.spin == 0 and f.charges.su2 == 2 and f.charges.su3 == "1"
                and math.isclose(abs(f.charges.hypercharge), 0.5)]
    if not doublets:
        return None
    others = [f.name for f in new if f is not doublets[0]]
    if others or any(doublets[0].charges.extra.values()):
        return (f"the dark doublet {doublets[0].name} comes with {', '.join(others) or 'a new gauge charge'}: LEP's "
                "inert-doublet limit assumes the doublet alone (A₀ → H₀Z*, H± → H₀W*)")
    _, rules, _ = cls.at(p)
    odd = [r for r in rules.particles if r.parity == -1 and r.spin == 0]
    neutral = sorted(r.mass for r in odd if abs(r.charge) < 1e-9)
    charged = [r.mass for r in odd if math.isclose(abs(r.charge), 1.0)]
    if len(charged) != 1 or len(neutral) not in (1, 2):
        return f"the doublet's spectrum is not H₀, A₀, H± ({len(neutral)} neutral, {len(charged)} charged states)"
    return neutral[0], neutral[-1], charged[0]


def two_hdma(cls, p: Point, unverified: bool) -> Outcome | None:
    """Applies to a UFO model listing ``atlas_2hdma``: ATLAS's (m_a, m_A) contour of scenario 1a, a point-in-polygon
    test; pending outside the scenario's parameters or the plane. A generic model read as the 2HDM+a
    (``generic_2hdma.match``) is judged as the library's UFO at the parameters read from it."""
    from adroit.parameter_space.portals import generic_2hdma
    found = generic_2hdma.match(cls, p)
    if isinstance(found, str):
        return Outcome(name=TWO_HDMA, excluded=None, why=found)
    if found is not None:
        cls, p = found.portal()
    if "atlas_2hdma" not in getattr(cls, "searches", []):
        return None
    blocked = s._blocked(TWO_HDMA, "atlas-2306.00641-2hdma", unverified)
    if blocked:
        return blocked
    values = cls._overrides(p)
    required = {"MXd": 10.0, "sinp": 0.35, "tanbeta": 1.0, "gPXd": 1.0,
                "sinbma": 1.0, "lam3": 3.0, "laP1": 3.0, "laP2": 3.0}
    missing = [key for key, target in required.items()
               if key not in values or not math.isclose(values[key], target, rel_tol=1e-8, abs_tol=1e-8)]
    m_a, m_heavy = values.get("mh4", 0.0), values.get("mh3", 0.0)
    missing += [key for key in ("mh2", "mhc") if key not in values or
                not math.isclose(values[key], m_heavy, rel_tol=1e-8)]
    # The library uses the measured Higgs mass (125.09 GeV); the source rounds it to 125.
    if not 124.99 <= values.get("mh1", 0) <= 125.10:
        missing.append("mh1 ≈ 125 GeV")
    if missing or 2.0 * values.get("MXd", p.m_chi) >= m_a:
        return Outcome(name=TWO_HDMA, excluded=None, source=s._record("atlas-2306.00641-2hdma").source,
                       why="outside ATLAS scenario 1a (mχ=10 GeV, alignment, λ₃=λP1=λP2=3, "
                           "degenerate heavy scalars): " + ", ".join(missing or ["a → χχ̄ closed"]))
    boundary = s._bundled("atlas-2306.00641-2hdma")["points"]
    if not boundary[0][0] <= m_a <= boundary[-1][0] or m_heavy < 250.0:
        return Outcome(name=TWO_HDMA, excluded=None, why=f"(m_a, m_A) = ({m_a:.3g}, {m_heavy:.3g}) GeV is outside "
                                                         "ATLAS's plane")
    if m_heavy > max(point[1] for point in boundary):                  # mini audit: above the contour's reach
        return Outcome(name=TWO_HDMA, excluded=None, why=f"m_A = {m_heavy:.4g} GeV is above the highest m_A the "
                                                         "observed contour reaches; ATLAS's plane gives no evidence")
    # The contour folds back (m_a ≈ 470–558 GeV): a point-in-polygon test on the contour closed along the plane's
    # lower edge, never a single-valued interpolation (audit M3; at m_a = 500 GeV it crosses m_A = 736.5, 870.6 and
    # 1361.2 GeV, leaving an allowed island).
    from adroit.parameter_space.resonances import _inside
    polygon = [*boundary, [boundary[-1][0], TWO_HDMA_FLOOR], [boundary[0][0], TWO_HDMA_FLOOR]]
    return Outcome(name=TWO_HDMA, excluded=_inside(polygon, m_a, m_heavy))


BSGAMMA, BSMUMU = "B → X_s γ (charged Higgs)", "B_s → μμ (2HDM)"


def two_hdm_flavour(cls, p: Point, unverified: bool) -> list[Outcome] | None:
    """Applies to the 2HDM+a (the library's UFO, or a generic model read as it, ``generic_2hdma``): the charged
    Higgs's B → X_s γ bound (type II, M_H± ≥ 800 GeV for tan β ≥ 0.4) and the type-II 2HDM's B_s → μμ regions in the
    M_H± – tan β plane (200–1500 GeV), both excluding (the owner, 2026-10-19); the light a's contribution to B_s → μμ is
    not included (the record says so)."""
    from adroit.parameter_space.portals import generic_2hdma
    found = generic_2hdma.match(cls, p)
    if isinstance(found, str):           # the 2HDM+a's fields, not read as it: undecided, with why (B20-10)
        why = f"the model has the 2HDM+a's fields but is not read as it: {found}"
        return [Outcome(name=BSGAMMA, excluded=None, why=why), Outcome(name=BSMUMU, excluded=None, why=why)]
    if found is None and "atlas_2hdma" not in getattr(cls, "searches", []):
        return None
    if found is not None:
        cls, p = found.portal()
    values = cls._overrides(p)
    m_charged, tan_beta = values["mhc"], values["tanbeta"]
    return [_bsgamma(m_charged, tan_beta, unverified), _bsmumu(m_charged, tan_beta, unverified)]


def _bsgamma(m_charged: float, tan_beta: float, unverified: bool) -> Outcome:
    blocked = s._blocked(BSGAMMA, "li-2412.04572-bsgamma", unverified)
    if blocked:
        return blocked
    d = s._record("li-2412.04572-bsgamma").data
    if tan_beta < d["tan_beta_min"]:
        return Outcome(name=BSGAMMA, excluded=None, why=f"tan β = {tan_beta:.3g} is below {d['tan_beta_min']:g}, "
                       "where the record's bound does not stand alone (R_b and the cot β terms)")
    return Outcome(name=BSGAMMA, excluded=m_charged < d["m_charged_min_gev"], value=m_charged,
                   ratio=d["m_charged_min_gev"] / m_charged)


def _bsmumu(m_charged: float, tan_beta: float, unverified: bool) -> Outcome:
    blocked = s._blocked(BSMUMU, "dmwg-1810.09420-bsmumu", unverified)
    if blocked:
        return blocked
    d = s._bundled("dmwg-1810.09420-bsmumu")
    low, high = d["low"], d["high"]
    if not low[0][0] <= m_charged <= low[-1][0]:
        return Outcome(name=BSMUMU, excluded=None, why=f"M_H± = {m_charged:.4g} GeV is outside the record's "
                       f"{low[0][0]:.0f}–{low[-1][0]:.0f} GeV")
    below = float(np.interp(m_charged, [x for x, _ in low], [y for _, y in low]))
    above = float(np.interp(m_charged, [x for x, _ in high], [y for _, y in high]))
    return Outcome(name=BSMUMU, excluded=not below <= tan_beta <= above, value=tan_beta,
                   why=f"allowed tan β {below:.3g}–{above:.3g} at M_H± = {m_charged:.4g} GeV")


TWO_HDMA_FLOOR = 250.0           # GeV: the lower edge of ATLAS's (m_a, m_A) plane, where the contour is closed


BBN = "BBN and N_eff"
NEFF_FREEZE_IN = "ibe-1912.12152-dark-photon-neff"
THERMALISATION_SPREAD = 3.0      # ε within this factor of 10⁻⁸: the thermalisation is approximate (item 18, 2026-10-17)
M_E_MEV = 0.51099895


def _freeze_in_dark_photon(cls, p: Point, unverified: bool) -> Outcome:
    """A dark photon below thermalisation (ε < 10⁻⁸), produced by freeze-in: Planck's N_eff excludes the red region of
    Ibe et al.'s Fig. 4(a) in (m_A′, ε) (record ibe-1912.12152-dark-photon-neff; the owner, 2026-10-13)."""
    blocked = s._blocked(BBN, NEFF_FREEZE_IN, unverified)
    if blocked:
        return blocked
    mass_mev = p.m_med * 1e3
    if 2.0 * p.m_chi < p.m_med:
        return Outcome(name=BBN, excluded=None, why="the A′ can decay to dark matter, and Ibe et al.'s N_eff region is "
                                                    "for one that decays to e⁺e⁻")
    if mass_mev < 2.0 * M_E_MEV:
        return Outcome(name=BBN, excluded=None, why="below the e⁺e⁻ threshold the A′ decays to three photons; the CMB "
                                                    "distortion and reionisation bound there is not recorded")
    data = s._bundled(NEFF_FREEZE_IN)
    if p.g_q < data["frame"]["epsilon"][0]:
        return Outcome(name=BBN, excluded=False, why="below Ibe et al.'s ε = 10⁻¹¹, where N_eff is standard (the "
                                                     "figure's outermost contour closes above 2 × 10⁻¹¹)")
    from adroit.parameter_space.resonances import _inside
    region = [[math.log10(m), math.log10(e)] for m, e in zip(data["mass_mev"], data["epsilon"])]
    return Outcome(name=BBN, excluded=_inside(region, math.log10(mass_mev), math.log10(p.g_q)))


def _dark_photon_bbn(cls, p: Point, unverified: bool, d: dict, mass_mev: float) -> Outcome:
    """Thermalised above ε = 10⁻⁸, Sabti et al.'s mass bound; below, freeze-in in Ibe et al.'s region. Their 10⁻⁸ is a
    representative value: within ``THERMALISATION_SPREAD`` of it, a verdict the other side would change is flagged,
    good up to an O(1) factor in ε (the owner, 2026-10-17; the external audit's item 18)."""
    threshold = d["dark_photon_thermal_epsilon"]

    def thermalised() -> Outcome:
        return s._blocked(BBN, "sabti-1910.01649-bbn", unverified) or Outcome(
            name=BBN, excluded=mass_mev < d["electrophilic_vector_mev"])

    def freeze_in() -> Outcome:
        return _freeze_in_dark_photon(cls, p, unverified)

    above = p.g_q >= threshold
    chosen, other = (thermalised, freeze_in) if above else (freeze_in, thermalised)
    out = chosen()
    if out.excluded is None or not threshold / THERMALISATION_SPREAD <= p.g_q <= threshold * THERMALISATION_SPREAD:
        return out
    alternative = other()
    if alternative.excluded in (None, out.excluded):
        return out
    word = {True: "excluded", False: "allowed"}
    return out.model_copy(update={"flags": out.flags + [
        f"BBN: ε = {p.g_q:.2g} is within a factor {THERMALISATION_SPREAD:g} of the dark photon's thermalisation at "
        f"ε ≈ 10⁻⁸, a representative value (Ibe et al.): {'thermalised' if above else 'by freeze-in'} it is "
        f"{word[out.excluded]}, {'by freeze-in' if above else 'thermalised'} {word[alternative.excluded]}; the verdict "
        "is good up to an O(1) factor in ε"]})


def bbn(cls, p: Point, unverified: bool) -> Outcome | None:
    """A light vector mediator in equilibrium at neutrino decoupling (Sabti et al.; record sabti-1910.01649-bbn)."""
    fam = family(cls)
    d = s._record("sabti-1910.01649-bbn").data
    generic = _generic_dark_photons(cls, p)
    if generic is not None:                     # a generic model's light vectors by their coupling pattern (P4)
        from adroit.parameter_space.resonances import _strongest
        below = d["applies_below_mev"] / 1e3
        dm = cls.dark_matter_mass(p)                # the A′ → χχ̄ question the freeze-in branch asks
        found = [_dark_photon_bbn(cls, Point(m_chi=dm, m_med=m, g_q=e), unverified, d, m * 1e3)
                 for e, m, *_ in generic if m < below]
        for charges, name in ((B_MINUS_L_CHARGES, "B-L"), (LMU_CHARGES, "Lmu-Ltau")):
            found += [_charged_bbn(name, g, m.mass_gev * 1e3, d, unverified)
                      for g, m in _generic_pattern(cls, p, charges) if m.mass_gev < below]
        return _strongest(found)
    if fam not in ("dark_photon", "charged_zprime") or p.m_med * 1e3 >= d["applies_below_mev"]:
        return None
    mass_mev = p.m_med * 1e3
    if fam == "dark_photon":
        return _dark_photon_bbn(cls, p, unverified, d, mass_mev)
    return _charged_bbn(cls.charges, p.g_q, mass_mev, d, unverified)


NEFF = "N_eff (Planck 2018)"
# The contours hold where the Z′ equilibrates through inverse decays, g ≥ 1.3 × 10⁻¹⁰ (m/MeV)^½ (the paper's text, for a
# light Z′): below, a Z′ that never equilibrates can decay late (its Fig. 4: N_eff = 4.39 at 5 MeV, g = 10⁻¹⁰), which
# Fig. 2 does not show; there BBN's own outcome is already undecided. 40 MeV is ADROIT's own limit, not the paper's: above
# it every contour lies to its left in the figure, at every coupling the figure shows.
NEFF_REACH = (1.3e-10, 40.0)
ACT_FLAG = "ACT DR6 (N_eff = 2.86 ± 0.13) disfavours ΔN_eff > 0.1 here (a flag, the owner's decision)"


def neff(cls, p: Point, unverified: bool) -> Outcome | None:
    """ΔN_eff of a light L_μ − L_τ Z′ (Escudero et al.; record escudero-1901.02010-neff): the library's (with its
    loop's kinetic mixing, the figure's bottom frame) or a generic vector with exactly those charges (the top frame)."""
    from adroit.parameter_space.resonances import _strongest
    matched = _generic_pattern(cls, p, LMU_CHARGES)
    if matched is not None:
        found = [_lmu_neff(g, m.mass_gev, _beyond_standard(m), "no_mixing", unverified) for g, m in matched]
        found = [o for o in found if o is not None]
        return _strongest(found) if found else None
    if family(cls) != "charged_zprime" or cls.charges != "Lmu-Ltau":
        return None
    total = cls.mediator(p).width                 # its own total width, as _lmu_numbers (the RV22 audit's RX22-06:
    share = _lmu_dark_width(p) / total if total > 0 else 0.0     # one minus every free-fermion width counted u, d)
    return _lmu_neff(p.g_q, p.m_med, share, "natural_mixing", unverified)


def _beyond_standard(m) -> float:
    """The share of a portrait's width into anything but a pair of Standard Model fermions: the dark matter (Dirac
    or Majorana, whatever its names) and any other new state, from the channels' own widths. Not read from a
    channel that may be closed (the tactical audit's T20-06: the muons' share is zero below their threshold, where
    the whole N_eff reach lies)."""
    from adroit.model_building.feynman import SM_FERMIONS
    standard = {f.name for f in SM_FERMIONS} | {f"{f.name}~" for f in SM_FERMIONS}
    other = sum(c.width_gev for c in m.channels if not set(c.final) <= standard)
    return other / m.width_gev if m.width_gev > 0 else 0.0


def neff_benchmark(frame: str, dm_share: float) -> str:
    """Why a Z′ with more than 1% of its width into the dark matter has no ΔN_eff outcome: Escudero et al.'s Z′ has
    L_μ − L_τ's couplings only, and in the bottom frame (``natural_mixing``) the photon's through ε = g/70, so where
    ADROIT applies the contours, below 40 MeV, it decays to neutrinos and, with the mixing, to e⁺e⁻ (their eqs.
    (2.7)–(2.8)); never to dark matter. The 1% is ADROIT's threshold, not the paper's (the record's assumptions;
    the auditor's DJ recheck, DK-04, 2026-11-07: the explanation had said μ, τ and neutrinos, without the mixing's e⁺e⁻)."""
    decays = ("to neutrinos and, through its kinetic mixing (ε = g/70), to e⁺e⁻" if frame == "natural_mixing"
              else "to neutrinos only (no kinetic mixing)")
    return (f"the Z′ decays to the dark matter ({dm_share * 100:.3g}% of its width); the contours are for the paper's Z′, "
            f"with L_μ − L_τ's couplings only, which below 40 MeV decays {decays}, never to dark matter. More than 1% "
            "of its width into dark matter is undecided: ADROIT's threshold, not the paper's")


def _lmu_neff(g: float, m_gev: float, dm_share: float, frame: str, unverified: bool) -> Outcome | None:
    """Inside the ΔN_eff = 0.5 contour excluded, between 0.2 and 0.5 undecided, outside allowed (flagged inside 0.1);
    None outside the reach (``NEFF_REACH``)."""
    from adroit.parameter_space.resonances import _inside
    m_mev = m_gev * 1e3
    if m_mev > NEFF_REACH[1] or g < NEFF_REACH[0] * math.sqrt(m_mev):
        return None
    blocked = s._blocked(NEFF, "escudero-1901.02010-neff", unverified)
    if blocked:
        return blocked
    d = s._bundled("escudero-1901.02010-neff")
    if not d["mass_range_log10_mev"][0] <= math.log10(m_mev) <= d["mass_range_log10_mev"][1] or \
            not d["coupling_range_log10"][0] <= math.log10(g) <= d["coupling_range_log10"][1]:
        return None                               # outside the figure's frame: its contours say nothing there
    if dm_share > 0.01:                           # the source's benchmark, as its record states it (the auditor's DJ recheck,
        return Outcome(name=NEFF, excluded=None, why=neff_benchmark(frame, dm_share))       # DK-04, 2026-11-07)
    x, y = math.log10(m_mev), math.log10(g)

    def inside(level: str) -> bool:
        c = d[frame][level]
        polygon = [*c, [c[-1][0], 1.0], [-20.0, 1.0], [-20.0, c[0][1]]]
        return _inside(polygon, x, y)
    if inside("0.5"):
        return Outcome(name=NEFF, excluded=True, why="inside the ΔN_eff = 0.5 contour")
    if inside("0.2"):
        return Outcome(name=NEFF, excluded=None, why="ΔN_eff between 0.2 and 0.5: Planck 2018's ΔN_eff ≲ 0.3 crosses "
                                                     "the band, which the contours do not resolve")
    return Outcome(name=NEFF, excluded=False, flags=[ACT_FLAG] if inside("0.1") else [])


def _charged_bbn(charges: str, g: float, mass_mev: float, d: dict, unverified: bool) -> Outcome:
    """Sabti et al.'s bound on a light B − L or L_μ − L_τ vector of coupling g (``bbn``)."""
    blocked = s._blocked(BBN, "sabti-1910.01649-bbn", unverified)
    if blocked:
        return blocked
    if charges == "B-L":
        floor = d["b_minus_l_g_at_10_mev"] * math.sqrt(d["b_minus_l_mev"] / mass_mev)
        return Outcome(name=BBN, excluded=mass_mev < d["b_minus_l_mev"] and g > floor)
    if g < d["lmu_ltau_thermal_g"]:
        return Outcome(name=BBN, excluded=None, why="the Z′ is below its thermalisation coupling; its inverse decays "
                                                    "still raise N_eff (not computed)")
    return Outcome(name=BBN, excluded=mass_mev < d["neutrinophilic_vector_mev"])


LHC = "LHC searches (SModelS)"
PARTNER_PDG = {"uR": (2000002, 2, 3, 2), "dR": (2000001, -1, 3, 1), "bR": (2000005, -1, 3, 5),
               "muR": (2000013, -3, 1, 13), "eR": (2000011, -3, 1, 11), "tauR": (2000015, -3, 1, 15)}


def lhc_spectrum(cls, p: Point) -> tuple[str, float | None] | None:
    """(SLHA text, total σ in pb) of a model SModelS can test: t-channel partners, the wino and higgsino."""
    from adroit.constraints import lhc
    fam = family(cls)
    if fam == "t_channel" and not cls.domain(p):
        pdg, charge3, colour, sm = PARTNER_PDG[cls.partner]
        chi = 52 if cls.majorana else 57
        width = p.g_chi ** 2 * p.m_med / (16.0 * math.pi) * (1.0 - (p.m_chi / p.m_med) ** 2) ** 2
        sigma = lhc.cross_section_pb("coloured" if colour == 3 else "slepton", p.m_med)
        if sigma is None:
            return "", None
        particles = [dict(pdg=pdg, label="phi", charge3=charge3, spin_states=1, colour=colour, distinct=True, mass=p.m_med),
                     dict(pdg=chi, label="chi", charge3=0, spin_states=2, colour=1, distinct=not cls.majorana,
                          mass=p.m_chi)]
        return lhc.slha(particles, {pdg: (width, [(1.0, [chi, sm])])}, [((pdg, -pdg), sigma)]), sigma
    if fam == "electroweak_multiplet" and not cls.domain(p):
        return _multiplet_spectrum(cls, p)
    if fam == "generic":                                # G9: from the model's own spectrum (``generic_lhc``)
        text, sigma, _ = cls.lhc_spectrum(p)
        return text, sigma
    return mediator_spectrum(cls, p) if not (hasattr(cls, "domain") and cls.domain(p)) else None


def _multiplet_spectrum(cls, p: Point) -> tuple[str, float | None]:
    from adroit.constraints import lhc
    m, delta = p.m_chi, cls.splitting(p)
    neutral = dict(charge3=0, spin_states=2, colour=1, distinct=False)
    charged = dict(pdg=1000024, label="chi+", charge3=3, spin_states=2, colour=1, distinct=True, mass=m + delta)
    if cls.multiplet == "wino":
        particles = [dict(pdg=1000022, label="chi0", mass=m, **neutral), charged]
        decays = {1000024: (lhc.chargino_width(delta, 2.0), [(1.0, [1000022, 211])])}
        xs = [((1000022, 1000024), lhc.cross_section_pb("wino_c1p_n", m)),
              ((1000022, -1000024), lhc.cross_section_pb("wino_c1m_n", m)),
              ((1000024, -1000024), lhc.cross_section_pb("wino_c1c1", m))]
    else:
        particles = [dict(pdg=1000022, label="chi01", mass=m, **neutral),
                     dict(pdg=1000023, label="chi02", mass=m + 1e-3, **neutral), charged]
        decays = {1000024: (lhc.chargino_width(delta, 1.0), [(0.5, [1000022, 211]), (0.5, [1000023, 211])])}
        plus, minus = lhc.cross_section_pb("hino_n1c1p", m), lhc.cross_section_pb("hino_n1c1m", m)
        xs = [((1000022, 1000024), plus), ((1000022, -1000024), minus), ((1000023, 1000024), plus),
              ((1000023, -1000024), minus), ((1000024, -1000024), lhc.cross_section_pb("hino_c1c1", m)),
              ((1000022, 1000023), lhc.cross_section_pb("hino_n1n2", m))]
    if any(x is None for _, x in xs):
        return "", None
    return lhc.slha(particles, decays, xs), sum(x for _, x in xs)


FERMION_PDG = {"d": 1, "u": 2, "s": 3, "c": 4, "b": 5, "t": 6, "e": 11, "nu_e": 12, "mu": 13, "nu_mu": 14,
               "tau": 15, "nu_tau": 16}
HIGGS_PDG = {"b": (5, -5), "c": (4, -4), "tau": (15, -15), "mu": (13, -13), "t": (6, -6), "W": (24, -24),
             "Z": (23, 23), "g": (21, 21), "gamma": (22, 22), "Zgamma": (23, 22)}
VECTOR_TABLES = {"vector": "zprime_spin1_vector_13TeV_LO", "axial": "zprime_spin1_axial_13TeV_LO",
                 "B-L": "zprime_spin1_BminusL_13TeV_LO"}
SCALAR_TABLES = {False: "ggS_spin0_S_tb_13TeV_LO", True: "ggS_spin0_P_tb_13TeV_LO"}
IDM_TABLES = {"H0A0": "idm_H0A0_equal_masses_13TeV_LO", "HpmH0": "idm_HpmH0_equal_masses_13TeV_LO",
              "HpmA0": "idm_HpmA0_equal_masses_13TeV_LO", "HpHm": "idm_HpHm_equal_masses_13TeV_LO"}
IDM_PDG = {"~H0": 9000101, "~A0": 9000102, "~H+": 9000103}
Z_FRACTIONS = {(11, -11): 0.0336, (13, -13): 0.0337, (15, -15): 0.0337, (12, -12): 0.0667, (14, -14): 0.0667,
               (16, -16): 0.0667, (1, -1): 0.156, (2, -2): 0.116, (3, -3): 0.156, (4, -4): 0.120,
               (5, -5): 0.151}          # the Z's branching fractions (PDG), each neutrino flavour a third of 20%
W_FRACTIONS = {(-11, 12): 0.1071, (-13, 14): 0.1063, (-15, 16): 0.1138, (2, -1): 0.3375, (4, -3): 0.3353}   # W⁺ (PDG)


def mediator_spectrum(cls, p: Point) -> tuple[str, float] | None:
    """(SLHA, σ in pb) of a singly produced s-channel mediator and its decays: a Z′ (DM13's spin-1 class, B − L),
    a scalar or pseudoscalar mediator (DM13's scalar class), the singlet's heavy scalar h₂; or the inert
    doublet's H₀A₀ pair. MadGraph's tables (``constraints.production``) at unit couplings, scaled by the
    couplings squared."""
    if family(cls) == "ufo" and "lep_inert_doublet" in getattr(cls, "searches", []):
        return _inert_pair(cls, p)
    if family(cls) == "ufo" and "atlas_2hdma" in getattr(cls, "searches", []):
        return _two_hdma_spectrum(cls, p)
    built = _z_prime(cls, p) or _scalar(cls, p)
    if built is None:
        return None
    sigma, med_pdg, spin_states, widths = built
    total = sum(widths.values())
    if total <= 0:
        return None
    if sigma is None:                      # the σ table lacks this mass: undecided, never silent (F09 residue)
        return "", None
    from adroit.constraints import lhc
    chi = 57
    particles = [dict(pdg=med_pdg, label="mediator", charge3=0, spin_states=spin_states, colour=1, distinct=False,
                      mass=p.m_med),
                 dict(pdg=chi, label="chi", charge3=0, spin_states=2, colour=1, distinct=True, mass=p.m_chi)]
    channels = [(w / total, list(d if d != "dm" else (chi, -chi))) for d, w in widths.items() if w > 0]
    return lhc.slha(particles, {med_pdg: (total, channels)}, [((med_pdg, 0), sigma)]), sigma


def _z_prime(cls, p: Point):
    """(σ, pdg, spin states, partial widths) of a Z′: q q̄ → Z′ at LO, σ = g_q² σ(g = 1)."""
    from adroit.constraints import production, spin1
    from adroit.parameter_space.classes import Spin1Class
    from adroit.parameter_space.flavour_vector import FlavourVectorClass
    if isinstance(cls,FlavourVectorClass):
        universal=cls.universal_point(p)
        return _z_prime(Spin1Class(name=cls.name),universal) if universal is not None else None
    if isinstance(cls, Spin1Class):
        model = cls.model(p)
        axial = model.kind is spin1.Spin1Kind.axial
        couple = (lambda g: (0.0, g)) if axial else (lambda g: (g, 0.0))
        # each fermion's own coupling, the left-handed neutrinos' g_ν = ±g_ℓ included, so the width is the model's
        # (``spin1.width``) and every branching ratio its own (AL2-03: without them BR(ee) 0.314 for 0.214)
        fermions = {f.name: model.couplings(f) for f in spin1.FERMIONS}
        sigma = production.sigma_pb(VECTOR_TABLES["axial" if axial else "vector"], p.m_med)
        return _scaled(sigma, p.g_q ** 2), 55, 3, _vector_widths(p, fermions, couple(p.g_chi))
    if family(cls) == "charged_zprime" and cls.charges == "B-L":
        sigma = production.sigma_pb(VECTOR_TABLES["B-L"], p.m_med)
        return _scaled(sigma, p.g_q ** 2), 55, 3, _vector_widths(p, cls.fermions(p), (p.g_chi, 0.0))
    return None


def generic_mediators(cls, p: Point, spin: int) -> list[tuple[Point, tuple, object, object]]:
    """A generic model's new neutral bosons of this spin as the library's resonance searches read a mediator (P3 of
    ``docs/generic_route_next.md``): for each, (the point with m_med its mass, (σ, None, spin states, partial widths
    keyed by PDG pair as ``_z_prime``'s, the dark matter's as "dm", any other pair by a key above every PDG code),
    its portrait, its production). From the generic model's own rules (``generic_portrait``, ``generic_production``);
    [] for any other model."""
    from adroit.model_building.ufo_export import SM_NAMES
    from adroit.parameter_space.portals import generic_portrait as gp, generic_production as gpr
    from adroit.parameter_space.portals.generic import GenericModel
    if not isinstance(cls, GenericModel):
        return []
    out = []
    for m in gp.portraits(cls, p):
        if m.spin != spin or m.hadronic_reason:     # in the hadronic window (m ≤ 3 GeV): no LHC spectrum to judge
            continue
        dm = m.dark_matter.fermion if m.dark_matter else cls.at(p)[0].spectrum.dark_matter().name
        widths: dict = {}
        for i, c in enumerate(m.channels):
            a, b = (x.rstrip("~") for x in c.final)
            code = SM_NAMES[a][2] if a == b and a in SM_NAMES else None
            key = ((code, code) if a in ("Z", "A", "g", "h") else (code, -code)) if code else \
                "dm" if a == b == dm else (10_000_000 + i, 0)          # a self-conjugate boson pair as HIGGS_PDG
            widths[key] = widths.get(key, 0.0) + c.width_gev
        made = gpr.single(m)
        out.append((p.model_copy(update={"m_med": m.mass_gev}), (made.sigma_pb, None, 3 if spin == 1 else 1, widths),
                    m, made))
    return out


def _scaled(sigma: float | None, factor: float) -> float | None:
    return None if sigma is None else sigma * factor


def _production():
    from adroit.constraints import production
    return production


def production_unavailable(*names: str) -> str:
    """Why MadGraph's production tables ``names`` cannot be used ('' if they can): a search reports it."""
    return _production().unavailable(*names)


def _missing_tables() -> str:
    """Every LHC production table not in the tools folder, MadGraph's and the SUSY Working Group's ('' if none)."""
    from adroit.constraints import lhc
    production = _production()
    names = [*VECTOR_TABLES.values(), *SCALAR_TABLES.values(), *IDM_TABLES.values(), production.K_TABLE,
             *(f"ggS_spin0_{cp}_{q}_13TeV_LO" for cp in "SP" for q in ("t", "b", "tb"))]
    return "; ".join(filter(None, [lhc.unavailable(*lhc.TABLES), production.unavailable(*names)]))


def _vector_widths(p: Point, fermions: dict, dark: tuple[float, float]) -> dict:
    from adroit.constraints import spin1
    out = {(FERMION_PDG[f.name], -FERMION_PDG[f.name]): spin1.partial_width(p.m_med, f.mass_gev, f.colours,
                                                                             *fermions[f.name])
           for f in spin1.FERMIONS}
    out["dm"] = spin1.partial_width(p.m_med, p.m_chi, 1, *dark)
    return out


def _scalar(cls, p: Point):
    """(σ, pdg, 1, partial widths) of a scalar: gg → S through t and b at LO × the Working Group's K-factor,
    σ = g_q² σ(g = 1); the singlet's h₂ as a Standard-Model-like heavy Higgs × sin²θ (NNLO+NNLL)."""
    from adroit.constraints import production
    if isinstance(cls, ScalarClass):
        computed, unknown = cls._widths(p)
        if unknown:                             # in the hadronic window: no spectrum with a width not computed
            return None
        widths = {("dm" if name == "dm" else (FERMION_PDG[name], -FERMION_PDG[name])): w for name, w in computed.items()}
        from adroit.model_building import yukawa
        from adroit.parameter_space.portals.generic_production import TABLE_MASSES
        g_t, g_b = (p.g_q * yukawa.mass(cls.yukawa, q) / TABLE_MASSES[q] for q in ("t", "b"))   # in the tables' units
        sigma = gluon_fusion_pb("P" if cls.sm_pseudoscalar else "S", g_t, g_b, p.m_med)
        return sigma, 54, 1, widths
    if family(cls) == "singlet_mixing":
        from adroit.constraints import higgs
        sin_t, _ = cls._mixing(p)
        widths = {HIGGS_PDG[k]: sin_t ** 2 * w for k, w in higgs.partial_widths(p.m_med).items()}
        widths["dm"] = cls._to_dm(p.m_med, cls._yukawas(p)[1], p.m_chi)
        return _scaled(production.heavy_higgs_pb(p.m_med), sin_t ** 2), 35, 1, widths
    return None


def _inert_pair(cls, p: Point) -> tuple[str, float] | None:
    """The inert doublet's Drell–Yan pairs H₀A₀, H±H₀, H±A₀ and H⁺H⁻ with A₀ → H₀Z(*), H± → H₀W(*): MadGraph's
    equal-mass table at the pair's mean mass × 2√(m₁m₂)/(m₁ + m₂), within 5% of MadGraph's split-mass runs for mass
    ratios up to 8 (docs/portal_library_4.md). The cascades A₀ → H±W*, H± → A₀W* are left out. A pair heavier than
    the tables' 1 TeV is left out too: there each pair's σ is below 1.5 × 10⁻⁵ pb (two events in 139 fb⁻¹), falling
    with the mass, which no search reaches. A table missing from the tools folder makes the spectrum undecided
    (``("", None)``: ``lhc_search`` names the missing tables), never a spectrum without its pairs (AL2-14)."""
    from adroit.constraints import lhc, production
    model = cls.model(p)
    h0, a0, hc = (model.particles[n] for n in (cls.dm, "~A0", "~H+"))
    if a0.mass <= h0.mass or hc.mass <= h0.mass:
        return None
    if production.unavailable(*IDM_TABLES.values()):
        return "", None
    pdg = IDM_PDG
    xsections = []
    for table, (a, b), (x, y) in ((IDM_TABLES["H0A0"], (pdg["~H0"], pdg["~A0"]), (h0, a0)),
                                  (IDM_TABLES["HpmH0"], (pdg["~H+"], pdg["~H0"]), (hc, h0)),
                                  (IDM_TABLES["HpmA0"], (pdg["~H+"], pdg["~A0"]), (hc, a0)),
                                  (IDM_TABLES["HpHm"], (pdg["~H+"], -pdg["~H+"]), (hc, hc))):
        sigma = production.sigma_pb(table, 0.5 * (x.mass + y.mass))
        if sigma is None:
            reach = production.mass_range(table)
            if reach is None or 0.5 * (x.mass + y.mass) < reach[0]:     # below the table: undecided, not dropped
                return "", None                                          # (AL3-13)
            continue
        sigma *= 2.0 * math.sqrt(x.mass * y.mass) / (x.mass + y.mass)      # the unequal masses' smaller phase space
        charged_single = a == pdg["~H+"] and b != -pdg["~H+"]          # H±X: half each charge
        xsections += [((a, b), 0.5 * sigma), ((-a, b), 0.5 * sigma)] if charged_single else [((a, b), sigma)]
    if not xsections:
        return None
    particles = [dict(pdg=pdg["~H0"], label="H0", charge3=0, spin_states=1, colour=1, distinct=False, mass=h0.mass),
                 dict(pdg=pdg["~A0"], label="A0", charge3=0, spin_states=1, colour=1, distinct=False, mass=a0.mass),
                 dict(pdg=pdg["~H+"], label="H+", charge3=3, spin_states=1, colour=1, distinct=True, mass=hc.mass)]
    decays = {pdg["~A0"]: (max(a0.width, 1e-10), _cascade(a0.mass - h0.mass, 23, Z_FRACTIONS)),
              pdg["~H+"]: (max(hc.width, 1e-10), _cascade(hc.mass - h0.mass, 24, W_FRACTIONS))}
    return lhc.slha(particles, decays, xsections), sum(x for _, x in xsections)


def gluon_fusion_pb(cp: str, g_t: float, g_b: float, mass: float) -> float | None:
    """σ(gg → S) (pb) for Yukawa-like couplings g_t, g_b (units of m_q/v; ``cp`` "S" or "P"), from the unit tables
    with their interference, σ = g_t² σ_t + g_b² σ_b + g_t g_b (σ_tb − σ_t − σ_b), × the K-factor; None where a table
    or the K-factor lacks the mass (a missing K had given the LO σ, about 2.5 times low: the subagent's D2,
    2026-10-20)."""
    from adroit.constraints import production
    tables = [production.sigma_pb(f"ggS_spin0_{cp}_{q}_13TeV_LO", mass) for q in ("t", "b", "tb")]
    k = production.gluon_fusion_k(mass)
    if any(t is None for t in tables) or k is None:
        return None
    s_t, s_b, s_tb = tables
    lo = g_t * g_t * s_t + g_b * g_b * s_b + g_t * g_b * (s_tb - s_t - s_b)
    return max(lo, 0.0) * k


def _two_hdma_spectrum(cls, p: Point) -> tuple[str, float] | None:
    """The 2HDM+a's a, A and H singly produced in gluon fusion (type II, alignment: in units of m_q/v,
    a: g_t = s_θ/t_β, g_b = s_θ t_β; A: c_θ/t_β, c_θ t_β; H: −1/t_β, t_β; Djouadi, Phys. Rept. 459 (2008) 1),
    with every two-body decay of the UFO model (A → a h, H → a Z, a → χχ̄, …) for SModelS. MadGraph on the
    model itself agrees with these σ to 1–3% at the Working Group's benchmark."""
    from adroit.constraints import lhc
    x = cls._overrides(p)
    model = cls.model(p)
    s_t, t_b = x["sinp"], x["tanbeta"]
    c_t = math.sqrt(max(1.0 - s_t * s_t, 0.0))
    production = {"h4": ("P", s_t / t_b, s_t * t_b), "h3": ("P", c_t / t_b, c_t * t_b), "h2": ("S", -1.0 / t_b, t_b)}
    dm = model.particles[cls.dm]
    particles = [dict(pdg=abs(dm.pdg), label="chi", charge3=0, spin_states=2, colour=1, distinct=True, mass=dm.mass)]
    decays, xsections, missing = {}, [], []
    for name in ("h4", "h3", "h2", "h+"):
        state = model.particles[name]
        channels = _two_body_channels(model, state)
        total = sum(w for w, _ in channels)
        particles.append(dict(pdg=abs(state.pdg), label=name, charge3=round(3 * state.charge), spin_states=1,
                              colour=1, distinct=bool(state.anti), mass=state.mass))
        if total > 0:
            decays[abs(state.pdg)] = (total, [(w / total, d) for w, d in channels])
        if name in production:
            sigma = gluon_fusion_pb(*production[name], state.mass)
            if sigma:
                xsections.append(((abs(state.pdg), 0), sigma))
            elif sigma is None:
                missing.append(name)
    if missing or not xsections:           # a production channel without σ would understate the signal
        return "", None
    return lhc.slha(particles, decays, xsections), sum(x for _, x in xsections)


def _two_body_channels(model, x) -> list[tuple[float, list[int]]]:
    """(Γ, [pdg, pdg]) of every two-body decay of x the model's vertices allow."""
    from adroit.constraints import ufo_model
    out, seen = [], set()
    finals = list(model.particles.values())
    for c in finals:
        for d in finals:
            key = tuple(sorted((c.name, d.name)))
            if key in seen or c.mass + d.mass >= x.mass or not (c.pdg and d.pdg):
                continue
            seen.add(key)
            width = ufo_model._two_body(model, x, c, d)
            if width > 0:
                out.append((width, [c.pdg, d.pdg]))
    return out


def _cascade(gap: float, boson: int, fractions: dict) -> list[tuple[float, list[int]]]:
    """X → H₀ V for a mass gap above the boson's mass, else X → H₀ f f̄′ with the boson's branching fractions
    (prompt: the 2-body widths miss the 3-body decay, so a floor of 10⁻¹⁰ GeV is set)."""
    if gap > {23: 91.1876, 24: 80.377}[boson]:
        return [(1.0, [IDM_PDG["~H0"], boson])]
    return [(br, [IDM_PDG["~H0"], *pair]) for pair, br in fractions.items()]


SMODELS_NARROW = 0.10            # Γ/m up to which SModelS's narrow-resonance maps are applied to an s-channel mediator
# (ADROIT's choice, after CMS's narrow-dijet statement: SModelS states no threshold; kept by the owner, 2026-10-12)


def _broadest_mediator(cls, p: Point) -> float:
    """The largest Γ/m among the singly produced s-channel mediators SModelS would test (0 for pair production)."""
    built = _z_prime(cls, p) or _scalar(cls, p)
    if built is not None:
        return sum(built[3].values()) / p.m_med
    if family(cls) == "ufo" and "atlas_2hdma" in getattr(cls, "searches", []):
        from adroit.parameter_space.resonances import _relative_width
        model = cls.model(p)
        return max(_relative_width(model, name) for name in ("h4", "h3", "h2"))
    return 0.0


def lhc_search(cls, p: Point, unverified: bool, prefetched: dict | None = None) -> Outcome | None:
    """SModelS's most sensitive LHC search for the model's spectrum (record smodels-3.2.1)."""
    from adroit.constraints import lhc
    spectrum = lhc_spectrum(cls, p)
    if spectrum is None:
        return None
    blocked = s._blocked(LHC, "smodels-3.2.1", unverified)
    if blocked:
        return blocked
    text, sigma = spectrum
    if sigma is None:
        if family(cls) == "generic":
            return Outcome(name=LHC, excluded=None, why=cls.lhc_spectrum(p)[2] or _missing_tables())
        return Outcome(name=LHC, excluded=None, why=_missing_tables() or "production mass outside the tabulated "
                                                                         "cross-section domain")
    broad = _broadest_mediator(cls, p)
    if broad > SMODELS_NARROW:
        return Outcome(name=LHC, excluded=None, why=f"the mediator is broad (Γ/m = {100 * broad:.0f}%): SModelS's maps "
                                                    "assume a narrow resonance, which ADROIT takes as Γ/m ≤ "
                                                    f"{100 * SMODELS_NARROW:.0f}% (its choice, after CMS's narrow "
                                                    "dijets; SModelS states no threshold)")
    if prefetched is None and not lhc.available():
        return Outcome(name=LHC, excluded=None, why="SModelS is not in the tools folder (adroit setup)")
    try:
        result = prefetched or lhc.run([text])[0]
    except (RuntimeError, TimeoutError, subprocess.TimeoutExpired, ValueError) as error:
        return Outcome(name=LHC, excluded=None, why=f"SModelS failed: {error}")
    if result.get("status") == "error":
        return Outcome(name=LHC, excluded=None, why=f"SModelS: {result.get('error', 'error')}"[:200])
    r = result.get("r_max")
    coverage = result.get("coverage")
    if r is None or not math.isfinite(r):
        return Outcome(name=LHC, excluded=None, why="no SModelS result covers this spectrum")
    if _qcd_lower_bound(cls, p):          # decision D33: neither an exclusion nor "allowed" rests on QCD alone
        return Outcome(name=LHC, excluded=None, value=r, coverage=coverage or {}, source="SModelS 3.2.1",
                       why=f"r = {r:.2g} ({result.get('analysis', '')}) with QCD pair production alone: {QCD_ONLY}")
    if r >= 1:
        return Outcome(name=LHC, excluded=True, ratio=r, value=r, coverage=coverage or {},
                       why=str(result.get("analysis", "")), source="SModelS 3.2.1")
    incomplete = coverage is None or result.get("coverage_sigmacut_fb") != 0 or any(
        row.get("total_xsec_fb") is None or not math.isfinite(row["total_xsec_fb"])
        or row["total_xsec_fb"] > 0 for row in (coverage or {}).values())
    if incomplete:
        return Outcome(name=LHC, excluded=None, value=r, coverage=coverage or {}, source="SModelS 3.2.1",
                       why="tested topologies do not exclude; missing/unchecked topology coverage remains")
    if family(cls) == "generic" and f"  {LO_LABEL}" in text:
        return Outcome(name=LHC, excluded=None, value=r, coverage=coverage, source="SModelS 3.2.1",
                       why=f"r = {r:.2g} with MadGraph's leading-order production: {LO_ONLY}")
    return Outcome(name=LHC, excluded=False, ratio=r, value=r, coverage=coverage,
                   why=str(result.get("analysis", "")), source="SModelS 3.2.1")


# A coloured t-channel partner's production is tabulated for QCD alone; t-channel χ exchange adds to it (∝ y⁴ at
# large coupling) and is not computed, nor is its interference with QCD in q q̄ → φφ* (∝ y² g_s², sign not
# established), so the QCD σ is not established as a lower bound and decides nothing either way (decision D33, the
# external audit's R20, 2026-10-16; it had been taken as a lower bound, so that an exclusion stood). The full σ is
# deferred to a future release (docs/benchmark_limits.md, "Known limitation"); a model excluded by another valid
# constraint stays excluded.
# A generic model's production where no table applies is MadGraph's leading order (``constraints.pair_production``)
# with every tree-level diagram, the t-channel exchange and its interference with QCD included (the external audit's
# R17-1, 2026-10-17: MadGraph had kept only the lowest-order diagrams). NLO corrections raise pair production at the
# LHC (K ≈ 1.1–1.5 for electroweak states, more for coloured ones; 1.35–1.37 against the tables), so the complete LO
# σ is taken as a lower bound: an exclusion stands, "allowed" is not shown. QCD_ONLY's tables are not (decision D33).
LO_LABEL = "MG5LO"
LO_ONLY = ("the production cross-section is MadGraph's leading order, taken as a lower bound (NLO corrections raise "
           "it): an exclusion stands, but 'allowed' is not shown")
QCD_ONLY = ("the partner's production is tabulated for QCD alone: t-channel χ exchange (∝ y⁴) adds to it and its "
            "interference with QCD (∝ y² g_s², sign not established) can lower it, and neither is computed, so QCD "
            "alone is not a lower bound and decides nothing: pending")


def _qcd_lower_bound(cls, p: Point | None = None) -> bool:
    """Whether the model's LHC production is QCD's alone, which decides nothing (``QCD_ONLY``, decision D33): a
    coloured t-channel partner (the library's, or a generic model's read from the stop table)."""
    if family(cls) == "generic" and p is not None:
        return "BLOCK QNUMBERS 1000006" in cls.lhc_spectrum(p)[0]
    return family(cls) == "t_channel" and PARTNER_PDG.get(getattr(cls, "partner", ""), (0, 0, 1))[2] == 3


def prefetch_lhc(cls, points: list[Point], unverified: bool) -> list[dict | None]:
    """SModelS on every point in one batch (one database load), aligned with ``points``; None where unused."""
    from adroit.constraints import lhc
    spectra = [lhc_spectrum(cls, p) for p in points]
    usable = s.admits(s._record("smodels-3.2.1"), unverified)
    wanted = [sp[0] for sp in spectra if sp is not None and sp[1] is not None]
    if not wanted or not usable or not lhc.available():
        return [None] * len(points)
    try:
        results = dict(zip(wanted, lhc.run(wanted), strict=True))
    except (RuntimeError, TimeoutError, subprocess.TimeoutExpired, ValueError) as error:
        results = {text: {"status": "error", "error": str(error)} for text in wanted}
    return [results.get(sp[0]) if sp is not None else None for sp in spectra]


HIGGS_MU = "Higgs signal strength (ATLAS)"


def higgs_signal(cls, p: Point, unverified: bool) -> Outcome | None:
    """The 125 GeV Higgs's signal strength for a scalar mixing with it (record atlas-2207.00092-higgs-mu)."""
    generic = family(cls) == "generic"
    if family(cls) != "singlet_mixing" and not generic:
        return None
    if generic and (why := cls.higgs_mu_reason(p)):    # RF23-01: no one state at 125 GeV, or not a universal rescaling
        return Outcome(name=HIGGS_MU, excluded=None, why=why)
    mu = cls.higgs_mu(p) if generic else None
    if generic and mu is None:                          # no new scalar mixes with the h
        return None
    blocked = s._blocked(HIGGS_MU, "atlas-2207.00092-higgs-mu", unverified)
    if blocked:
        return blocked
    if not generic:
        from adroit.constraints import higgs
        sin_t, cos_t = cls._mixing(p)
        new = cls.mediators(p)[0].width - cos_t ** 2 * higgs.GAMMA_H        # h₁'s width beyond the Standard Model's
        mu = cos_t ** 4 * higgs.GAMMA_H / (cos_t ** 2 * higgs.GAMMA_H + new)
    d = s._record("atlas-2207.00092-higgs-mu").data
    chi2 = ((d["mu"] - mu) / d["sigma"]) ** 2 - ((d["mu"] - 1.0) / d["sigma"]) ** 2
    return Outcome(name=HIGGS_MU, excluded=abs(mu - d["mu"]) > 1.96 * d["sigma"], value=mu, delta_chi2=chi2)


HEAVY_SCALAR, MONOJET = "heavy scalar → ZZ, WW (ATLAS)", "LHC monojet, spin-0 mediator (CMS)"
# The widths each search's own paper states its limits for (docs/widths.md); no shared narrow-width default.
# ATLAS ZZ (arXiv:2009.14791 §9.1.1): its narrow-width limit "is valid for models in which the width is less than 0.5% of
# m_H". Its large-width limits (§9.1.2: ggF, Γ/m = 1–15%, from 400 GeV) include the heavy scalar's interference with
# the SM Higgs boson, modelled for H and h with the same production and decay amplitudes, and with the gg → ZZ
# continuum (§5, "Interference modelling"): they apply only to a model that matches those assumptions (``_lwa_mismatch``).
ZZ_NARROW = 0.005
ZZ_LWA_LOW = 400.0
# ATLAS WW (arXiv:2004.14636 §5.6): its spin-0 limits are for narrow resonances "whose intrinsic widths are smaller than
# the detector mass resolution", in ℓνqq ≈ 8% (resolved, 0.5–1 TeV) and 7% at 1 TeV to 4% at 5 TeV (merged); ADROIT
# takes the merged values, the smaller, linear in mass: (GeV, σ_m/m). A width near the resolution still broadens the
# reconstructed peak (the Voigt profile's FWHM: +25% at Γ = σ_m), so the limits apply below WW_NARROW_FRACTION of it,
# the largest ratio ATLAS itself applies them to: its benchmark radion, Γ/m = 3.2% at 3 TeV where σ_m/m ≈ 5.5%
# (Table 1; the owner, 2026-10-12).
WW_RESOLUTION = ((300.0, 0.07), (1000.0, 0.07), (5000.0, 0.04))
WW_NARROW_FRACTION = 0.6
# a dedicated record and the SModelS analyses holding the same data (counted once in the combined likelihood)
# (ATLAS's Gaussian dijet limits are the same paper as SModelS's ATLAS-EXOT-2019-03, but are used only for broad Z′,
# where SModelS's narrow maps give no result, so the two never meet)
# A dedicated record's data and SModelS's analyses that share data: SModelS's ratio leaves the combination when its
# best analysis is listed under a record present at the point. CMS's dijet coupling limit (cms-1806.00843,
# CMS-EXO-16-056, 2016 data) is inside CMS-EXO-19-012's full Run 2 data.
SAME_ANALYSIS = {MONOJET: ("CMS-EXO-20-004",), "LHC dijet resonances (CMS, ATLAS)": ("CMS-EXO-19-012", "CMS-EXO-16-056",
                                                                                   "ATLAS-EXOT-2019-03")}


def heavy_scalar(cls, p: Point, unverified: bool) -> Outcome | None:
    """The singlet mixing's h₂ in ATLAS's ZZ and WW resonance searches: σ(gg → h₂) × BR / limit, the larger, each
    within the widths its paper states (``ZZ_NARROW``, ``WW_RESOLUTION``; docs/widths.md)."""
    generic = generic_mediators(cls, p, 0)
    if generic:                                    # a generic model's scalars through gluon fusion (P3)
        from adroit.parameter_space.resonances import _strongest
        return _strongest([_heavy_scalar(cls, q, built[0], built[3], unverified, m.name) for q, built, m, _ in generic])
    if family(cls) != "singlet_mixing":
        return None
    sigma, _, _, widths = _scalar(cls, p)
    return _heavy_scalar(cls, p, sigma, widths, unverified)


def _heavy_scalar(cls, p: Point, sigma: float | None, widths: dict, unverified: bool,
                  label: str = "") -> Outcome | None:
    """One scalar's ZZ and WW outcome (``heavy_scalar``), m_med its mass; ``label`` a generic model's state (where
    neither search reaches its mass, nothing applies)."""
    total = sum(widths.values())
    if sigma is None and production_unavailable(production_k := _production().K_TABLE):
        return Outcome(name=HEAVY_SCALAR, excluded=None, why=production_unavailable(production_k))
    if sigma is None or total <= 0:
        return None
    width = 100.0 * total / p.m_med
    zz, zz_why = _zz_limit(s._bundled("atlas-2009.14791-zz"), p.m_med, width, _lwa_mismatch(cls, p))
    ww_limit, ww_why = s.interpolate(s._bundled("atlas-2004.14636-ww")["limit"], p.m_med), ""
    if ww_limit is not None and width >= 100.0 * ww_narrow(p.m_med):
        ww_limit, ww_why = None, (f"WW: Γ/m = {width:.2g}% is not below {100.0 * ww_narrow(p.m_med):.1f}%, 0.6 of the "
                                  f"detector mass resolution ({100.0 * ww_resolution(p.m_med):.1f}%): its narrow limits "
                                  "assume a width below the resolution (arXiv:2004.14636 §5.6), and ATLAS applies them "
                                  "up to 0.58 of it (its radion at 3 TeV)")
    ratios, blocked = [], None
    for record_id, final, limit in (("atlas-2009.14791-zz", HIGGS_PDG["Z"], zz), ("atlas-2004.14636-ww", HIGGS_PDG["W"],
                                                                                 ww_limit)):
        if limit is None:
            continue
        stop = s._blocked(HEAVY_SCALAR, record_id, unverified)
        blocked = blocked or stop
        if not stop:
            ratios.append(sigma * widths.get(final, 0.0) / total / limit)
    if not ratios:
        if not (zz_why or ww_why):            # neither search reaches the mass: nothing applies (AL3-12)
            return blocked
        return blocked or Outcome(name=HEAVY_SCALAR, excluded=None, why=f"{label or 'h₂'} (Γ/m = {width:.2g}%) at "
                                  f"{p.m_med:.0f} GeV: " + "; ".join(filter(None, [zz_why, ww_why])))
    if max(ratios) > 1.0:
        return Outcome(name=HEAVY_SCALAR, excluded=True, ratio=max(ratios))
    if blocked:                # allowed only if every record that applies here is verified (AL2-06, as AL1-07)
        return blocked
    if zz_why or ww_why:                       # allowed only if every search that applies here could be compared
        return Outcome(name=HEAVY_SCALAR, excluded=None, ratio=max(ratios),
                       why="below the limit that applies, but " + "; ".join(filter(None, [zz_why, ww_why])))
    return Outcome(name=HEAVY_SCALAR, excluded=False, ratio=max(ratios))


def ww_resolution(m_gev: float) -> float:
    """σ_m/m of ATLAS's ℓνqq search at m (``WW_RESOLUTION``)."""
    return float(np.interp(m_gev, [m for m, _ in WW_RESOLUTION], [r for _, r in WW_RESOLUTION]))


def ww_narrow(m_gev: float) -> float:
    """The Γ/m below which ATLAS's narrow WW limits apply at m: ``WW_NARROW_FRACTION`` of the mass resolution."""
    return WW_NARROW_FRACTION * ww_resolution(m_gev)


def _lwa_mismatch(cls, p: Point) -> str:
    """Why ATLAS's large-width ZZ limits do not describe this model's heavy scalar ('' if they do): matching the width
    is not enough, the interference must be the one ATLAS modelled (``ZZ_NARROW``'s comment)."""
    if family(cls) == "singlet_mixing":
        return ("ATLAS's large-width limits model the H–h interference for H and h with the same production and decay "
                "amplitudes (§5); the singlet's h₂ couples as sin θ and h as cos θ times the SM Higgs boson, so its "
                "H–h interference relative to the signal is cot²θ times ATLAS's, and its interference with the "
                "gg → ZZ continuum is not ATLAS's either")
    return "the model's interference with the SM Higgs boson and the gg → ZZ continuum is not shown to match ATLAS's"


def _zz_limit(data: dict, m: float, width_pct: float, mismatch: str) -> tuple[float | None, str]:
    """ATLAS's ZZ limit at mass m and Γ/m (%), and why there is none: the narrow table below Γ/m = 0.5% (from 210 GeV);
    above, only for a model whose interference matches ATLAS's large-width modelling (``mismatch`` empty), from 400 GeV,
    interpolated linearly in the width between the narrow table (as 0%) and the 1, 5, 10 and 15% tables."""
    narrow = s.interpolate(data["limit"], m)
    if narrow is None and all(s.interpolate(curve, m) is None for curve in data["broad"].values()):
        return None, ""                                            # outside ATLAS's masses: the search does not apply
    if width_pct < 100.0 * ZZ_NARROW:
        return narrow, ""
    reason = (f"ZZ: Γ/m = {width_pct:.2g}% is above the 0.5% to which ATLAS's narrow-width limit applies "
              "(arXiv:2009.14791 §9.1.1)")
    if mismatch:
        return None, f"{reason}, and its large-width limits do not apply: {mismatch}"
    if m < ZZ_LWA_LOW:
        return None, f"{reason}, and its large-width limits start at {ZZ_LWA_LOW:.0f} GeV"
    nodes = [(0.0, narrow)] + [(float(w), s.interpolate(curve, m)) for w, curve in data["broad"].items()]
    nodes = sorted((w, x) for w, x in nodes if x is not None)
    if len(nodes) < 2 or width_pct > nodes[-1][0]:
        return None, f"ZZ: Γ/m = {width_pct:.2g}% is outside ATLAS's large-width limits (1–15%)"
    return float(np.interp(width_pct, [w for w, _ in nodes], [x for _, x in nodes])), ""


THRESHOLD_WIDTHS = 5.0   # m_med − 2m_χ ≥ 5Γ: a Breit–Wigner's tail beyond threshold is ≲ 1/(10π) ≈ 3% (``_threshold``)


def _threshold(m_med: float, m_chi: float, width_gev: float) -> str:
    """Why the on-shell narrow-width rescaling does not hold this close to the invisible-decay threshold, or "".

    The recast takes CMS's m_DM = 1 GeV benchmark's acceptance and rescales the on-shell rate, which holds while the
    mediator is narrow and on shell: the χχ̄ pair then carries its whole momentum, whatever m_χ. Within a few widths of
    m_med = 2m_χ the Breit–Wigner reaches below threshold, and the narrow-width approximation fails (Berdine, Kauer
    & Rainwater, hep-ph/0703058). Required here: m_med − 2m_χ ≥ 5Γ, where the line shape's tail beyond threshold,
    (1/π)(Γ/2)/(m_med − 2m_χ), is ≲ 3%. It is a containment rule, not a validation: near the threshold the recast
    returns pending (the external audit's A07, 2026-10-16: a point 2 GeV above threshold, Γ = 9.4 GeV, had been
    excluded)."""
    gap = m_med - 2.0 * m_chi
    if gap >= THRESHOLD_WIDTHS * width_gev:
        return ""
    return (f"m_med − 2m_χ = {gap:.3g} GeV is within {THRESHOLD_WIDTHS:g} widths (Γ = {width_gev:.3g} GeV) of the "
            "invisible-decay threshold: the narrow-width rescaling does not hold there")


def monojet_spin0(cls, p: Point, unverified: bool) -> Outcome | None:
    """CMS's monojet limit on the DMsimp spin-0 mediator, recast by μ = g_q² BR_inv/BR_inv(benchmark). A generic
    model whose new scalar is DMsimp's (``generic_lhc.dmsimp_scalar``) is recast with its own width and BR_inv."""
    if family(cls) == "generic":
        return _generic_monojet(cls, p, unverified)
    if not isinstance(cls, ScalarClass) or p.g_q == 0:
        return None
    if p.m_med <= 2.0 * p.m_chi:
        return Outcome(name=MONOJET, excluded=None, why="on-shell invisible decay is closed; NWA recast unavailable")
    data = s._bundled("cms-2107.13021-monojet-spin0")
    limit = s.interpolate(data["pseudoscalar" if cls.sm_pseudoscalar else "scalar"], p.m_med)
    if limit is None:
        return None
    blocked = s._blocked(MONOJET, "cms-2107.13021-monojet-spin0", unverified)
    if blocked:
        return blocked
    bench = data["benchmark"]
    reference = p.model_copy(update={"m_chi": bench["m_dm_gev"], "g_chi": bench["g_chi"],
                                     "g_q": bench["g_q"], "g_l": 0.0})
    width, reference_width = cls.width(p) / p.m_med, cls.width(reference) / p.m_med
    metadata = dict(width_ratio=width, reference_width_ratio=reference_width,
                    source=s._record("cms-2107.13021-monojet-spin0").source)
    if width > reference_width * (1 + 1e-10):
        return Outcome(name=MONOJET, excluded=None, **metadata,
                       why=f"Γ/M={width:.6g} exceeds the source benchmark's {reference_width:.6g}; "
                           "the NWA coupling rescaling has no validated wider-width template")
    if near := _threshold(p.m_med, p.m_chi, width * p.m_med):
        return Outcome(name=MONOJET, excluded=None, **metadata, why=near)
    mu = p.g_q ** 2 * _invisible_fraction(cls, p) / _invisible_fraction(cls, reference)
    return Outcome(name=MONOJET, excluded=mu > limit, ratio=mu / limit, value=mu, **metadata,
                   why="on-shell NWA rescaling, restricted to widths no broader than the source benchmark")


def _generic_monojet(cls, p: Point, unverified: bool) -> Outcome | None:
    """The monojet recast for a generic model that reduces to the DMsimp spin-0 mediator (the owner, 2026-10-15):
    the benchmark's BR_inv and width from the library's scalar class at the same mediator mass, the model's own."""
    from adroit.parameter_space.portals import generic_lhc
    try:
        mb, rules, _ = cls.at(p)
    except ValueError:
        return None
    s_med = generic_lhc.dmsimp_scalar(mb, rules)
    if s_med is None:
        return None
    m_chi = mb.spectrum.dark_matter().mass_gev
    if s_med["m_med"] <= 2.0 * m_chi:
        return Outcome(name=MONOJET, excluded=None, why="on-shell invisible decay is closed; NWA recast unavailable")
    if s_med["br_invisible"] is None:
        return Outcome(name=MONOJET, excluded=None, why="the mediator decays to states G6 cannot name (another new "
                       "state, or a pair outside the spectra tables), so its invisible branching is unknown")
    data = s._bundled("cms-2107.13021-monojet-spin0")
    limit = s.interpolate(data["pseudoscalar" if s_med["pseudoscalar"] else "scalar"], s_med["m_med"])
    if limit is None:
        return None
    blocked = s._blocked(MONOJET, "cms-2107.13021-monojet-spin0", unverified)
    if blocked:
        return blocked
    bench = data["benchmark"]
    library = ScalarClass(dm_pseudoscalar=s_med["pseudoscalar"], sm_pseudoscalar=s_med["pseudoscalar"], name="dmsimp",
                          yukawa="DMsimp_s_spin0_MD")                       # the source's benchmark, its card's inputs
    reference = Point(m_chi=bench["m_dm_gev"], m_med=s_med["m_med"], g_chi=bench["g_chi"], g_q=bench["g_q"], g_l=0.0)
    width, reference_width = s_med["width"] / s_med["m_med"], library.width(reference) / s_med["m_med"]
    metadata = dict(width_ratio=width, reference_width_ratio=reference_width,
                    source=s._record("cms-2107.13021-monojet-spin0").source)
    if width > reference_width * (1 + 1e-10):
        return Outcome(name=MONOJET, excluded=None, **metadata,
                       why=f"Γ/M={width:.6g} exceeds the source benchmark's {reference_width:.6g}; "
                           "the NWA coupling rescaling has no validated wider-width template")
    if near := _threshold(s_med["m_med"], m_chi, s_med["width"]):
        return Outcome(name=MONOJET, excluded=None, **metadata, why=near)
    mu = s_med["g_t"] ** 2 * s_med["br_invisible"] / _invisible_fraction(library, reference)   # top loop, card units
    return Outcome(name=MONOJET, excluded=mu > limit, ratio=mu / limit, value=mu, **metadata,
                   why="the model's scalar as DMsimp's spin-0 mediator (g_q times the SM Yukawas): on-shell NWA "
                       "rescaling with its own width and invisible branching")


def _invisible_fraction(cls, p: Point) -> float:
    widths = _scalar(cls, p)[3]
    total = sum(widths.values())
    return widths.get("dm", 0.0) / total if total > 0 else 0.0


LINES, PBAR = "γ-ray lines (Fermi-LAT, H.E.S.S.)", "antiprotons (AMS-02)"
LINE_SPEED = 1e-3                 # the Milky Way's dark matter, relative speed in units of c
LINE_RECORDS = ("fermi-lat-1506.00013-lines", "hess-1805.05741-lines", "hess-2608.07234-lines", "dampe-2112.08860-lines")
M_Z = 91.1876
PBAR_CHANNELS = {"b": "bb", "u": "qq", "d": "qq", "s": "qq", "W": "WW", "hh": "hh", "mu": "mumu"}


def _self_conjugate(cls) -> bool:
    return cls.self_conjugate() if callable(getattr(cls, "self_conjugate", None)) else False


def line_rates(cls, p: Point) -> tuple[float, float]:
    """(σv_γγ, σv_Zγ) in cm³/s today: the model's own (the multiplets, with the Sommerfeld effect), else its
    photon channels."""
    rates = cls.line_sigma_v(p) if hasattr(cls, "line_sigma_v") else cls.sigma_v_today(p, LINE_SPEED)
    return rates.get("gamma", 0.0) + rates.get("aa_photons", 0.0), rates.get("Zgamma", 0.0)


# Conservative separation guard for Fermi's single-line templates (1506.00013,
# Fig. 1); two appreciable lines separated by <=20% need a two-line likelihood.
# This is an applicability guard, not a claimed calibrated joint resolution test.
FERMI_LINE_SEPARATION = 0.20
HESS_LINE_RESOLUTION = 0.10  # the H.E.S.S. records explicitly use the unresolved combination
# DAMPE (2112.08860) resolves lines (≲ 1.7% above 10 GeV) but fits each in a sliding window of 0.5–1.5 E_line (its
# Methodology; 0.7–1.3 E_line is only its systematic check of the window's width): two appreciable lines within the
# window's half-width share one background fit, so they need a joint likelihood. A conservative applicability guard, as
# Fermi's, not a resolution or a joint-line likelihood (the recheck's RB20-06, 2026-10-20: it had been 0.30, from the
# systematic check's window).
DAMPE_LINE_SEPARATION = 0.50
# (instrument, two-line guard, whether a line outside its curve leaves it pending): Fermi's curve spans 0.2–500 GeV, so
# an uncovered line is a gap; DAMPE's spans only 10–300 GeV, inside Fermi's, which judges a line outside DAMPE's range
RESOLVED_LINES = {"fermi": ("Fermi", FERMI_LINE_SEPARATION, True), "dampe": ("DAMPE", DAMPE_LINE_SEPARATION, False)}


def _line_comparison(record_id: str, gg: float, zg: float, m: float) -> tuple[float | None, str]:
    """Strongest individual line cut (Fermi, DAMPE: resolved lines), or the source-defined unresolved HESS sum."""
    curve = s._bundled(record_id)["limit"]
    energy = m - M_Z ** 2 / (4.0 * m)
    if zg > 0 and energy <= 0:
        return None, "Zγ is below its kinematic threshold"
    separation = (m - energy) / m
    resolved = RESOLVED_LINES.get(record_id.split("-")[0])
    if resolved is not None:
        instrument, guard, pends_outside = resolved
        if not any(rate > 0 and s.interpolate(curve, e) is not None
                   for rate, e in ((gg, m), (zg, energy))):
            return None, f"outside the {instrument} curve"
        if gg > 0 and zg > 0 and separation <= guard:
            return None, f"overlapping {instrument} lines require a two-line spectral likelihood"
        ratios, missing = [], []
        for label, rate, e, multiplicity in (("γγ", gg, m, 1.0), ("Zγ", zg, energy, 0.5)):
            if rate <= 0:
                continue
            limit = s.interpolate(curve, e)
            if limit is None:
                if pends_outside:
                    missing.append(f"{label} energy {e:.6g} GeV outside the source curve")
            else:
                ratios.append(rate * multiplicity * (e / m) ** 2 / limit)
        return (max(ratios) if ratios else None), "; ".join(missing)
    limit = s.interpolate(curve, m)
    if limit is None:
        return None, "outside the H.E.S.S. curve"
    if gg > 0 and zg > 0 and separation > HESS_LINE_RESOLUTION:
        return None, "H.E.S.S. unresolved-line assumption does not hold"
    return (gg + 0.5 * zg) / limit, ""


def _line_ratio(record_id: str, gg: float, zg: float, m: float) -> float | None:
    """Compatibility helper: one record's strongest valid ratio, never a Fermi sum."""
    return _line_comparison(record_id, gg, zg, m)[0]


def lines(cls, p: Point, unverified: bool) -> Outcome | None:
    """Independent line cuts; unresolved/unsupported coverage remains explicit. A model whose lines alone are
    computed (``resummed_lines``, e.g. the library's Majorana n-plet) is compared even where its other annihilation
    today is not."""
    if partial := getattr(cls, "partial_lines", ""):    # a partial line rate decides nothing (the audit loop's AL4-10)
        return Outcome(name=LINES, excluded=None, why=partial)
    m_dm = dm_mass(cls, p)          # the physical dark-matter mass (the audit's G3/G4-4, G12)
    own = getattr(cls, "resummed_lines", None)
    resummed = own(p) if callable(own) else None
    if resummed is None and (unknown := today_unknown(cls, p)):
        return Outcome(name=LINES, excluded=None, why=unknown)
    gg, zg = (resummed.get("gamma", 0.0), resummed.get("Zgamma", 0.0)) if resummed is not None else line_rates(cls, p)
    if gg <= 0 and zg <= 0:
        return None
    factor = 1.0 if _self_conjugate(cls) else 0.5
    ratios, pending, sources = [], [], []
    for record_id in LINE_RECORDS:
        if not s.exists(record_id):
            continue
        ratio, reason = _line_comparison(record_id, gg, zg, m_dm)
        if ratio is None and "outside" in reason:
            continue  # another instrument can cover this energy range
        stop = s._blocked(LINES, record_id, unverified)
        if stop:
            pending.append(stop.why)
            sources.append(record_id)                         # the record a person must verify (B20-11)
        else:
            if reason:
                pending.append(reason)
            if ratio is not None:                            # at a region's halo, its limit scales as ρ₀⁻²
                ratios.append(factor * ratio * halo_limits.density_scale(record_id))
                sources.append(record_id)
    value = max(ratios) if ratios else None
    band = getattr(cls, "line_band", None)                # a resummed rate's theory band (decision D30, G12)
    low, high, band_why = band(p) if callable(band) else (1.0, 1.0, "")
    excluded = True if value is not None and value * low > 1 else None if pending or value is None else \
        False if value * high <= 1 else None
    if excluded is None and value is not None and not pending:
        pending.append(f"below the limit only by the central rate; the theory band has no upper edge ({band_why})"
                       if math.isinf(high) else f"the rate's theory band straddles the limit ({band_why})")
    band_note = f"; theory band ×{low:.2f}–{high:.2f} ({band_why})" if band_why else ""
    bound = getattr(cls, "lines_upper_bound", None)
    upper = bound(p) if callable(bound) else ""
    if upper:       # an unresummed rate decides nothing: near a zero of the tree amplitude the resummed rate is
        excluded = None                                # larger (the audit's G8-5, G12), so it neither allows nor
        pending = [upper] + pending                    # excludes
    return Outcome(name=LINES, excluded=excluded, ratio=value if excluded is not None else None,
                   value=gg + 0.5 * zg, source="; ".join(sources),
                   why="; ".join(pending) or ("strongest individual/source-defined line cut; no quadrature sum"
                                              + band_note if value is not None
                                              else "no published line coverage at these energies"))


def antiprotons(cls, p: Point, unverified: bool) -> Outcome | None:
    """AMS-02's antiprotons (Calore et al. 2022): a pure channel against its curve, a mixture by the conservative
    rule (``constraints.mixtures``), each under the chosen propagation model (``constraints.propagation``). A
    stronger model that excludes where the chosen one does not gives a flag, not an exclusion. No outcome outside
    the record's masses (from 10 GeV), which it does not constrain."""
    m_dm = dm_mass(cls, p)          # the physical dark-matter mass (the audit's G3/G4-4, G12)
    from adroit.constraints import propagation
    from adroit.constraints.indirect import pure_ratio
    record = "calore-2202.03076-pbar"
    if not s.exists(record):
        return None
    if unknown := today_unknown(cls, p):
        return Outcome(name=PBAR, excluded=None, why=unknown)
    rates = cls.sigma_v_today(p, LINE_SPEED)
    if not any(v > 0 for v in rates.values()):
        return None
    curves = s._bundled(record)["limits"]
    if not min(c[0][0] for c in curves.values()) <= m_dm <= max(c[-1][0] for c in curves.values()):
        return None
    blocked = s._blocked(PBAR, record, unverified)
    if blocked:
        return blocked
    if missing := propagation.unavailable(record):         # never the central bound under another model's name
        return Outcome(name=PBAR, excluded=None, why=missing)
    reason = _spectrum_reference_reason(cls,p)
    if reason:
        return Outcome(name=PBAR,excluded=None,why=reason)
    ratio = pure_ratio(rates, m_dm, curves, PBAR_CHANNELS, _self_conjugate(cls))
    central = None if ratio is not None else _pbar_mixture(rates, m_dm, curves, _self_conjugate(cls))

    def under(model: str):
        """(excluded, ratio, mixture bound or None) with the bound of this propagation model."""
        f = propagation.factor(record, model, m_dm) / halo_limits.density_scale(record)   # and ρ₀⁻² at a region's halo
        if central is None:
            return ratio / f > 1.0, ratio / f, None
        bound = _rescaled_bound(central, f)
        return bound.excluded, bound.ratio, bound

    model = propagation.chosen()
    excluded, value, bound = under(model)
    why = "" if bound is None else bound.why() if excluded is not None else \
        f"no pure-channel limit or conservative bound for this mixture, cascade or threshold: {bound.why()}"
    harsher = [(m, r) for m in propagation.stronger(model) for e, r, _ in [under(m)] if e and not excluded]
    flags = [f"antiprotons (AMS-02): excluded under the {m} propagation model (ratio {r:.3g}) but not under the "
             f"chosen {model} one; flagged, not counted as an exclusion" for m, r in harsher]
    source = f"{s._record(record).source}; {model} propagation: {propagation.describe(record, model)}"
    return Outcome(name=PBAR, excluded=excluded, ratio=value, why=why, source=source, flags=flags)


def _rescaled_bound(bound, factor: float):
    """A mixture bound against limits ``factor`` times the central ones (every ratio divided by it)."""
    return bound.model_copy(update={
        "upper": None if bound.upper is None else bound.upper / factor, "lower": bound.lower / factor,
        "terms": [t.model_copy(update={"ratio": None if t.ratio is None else t.ratio / factor}) for t in bound.terms]})


def _pbar_mixture(rates: dict[str, float], mass: float, curves: dict, self_conjugate: bool):
    """The antiproton curves applied to a mixture by the conservative rule (``data/mixture_rules.yaml``)."""
    from adroit.constraints import mixtures
    scale = 1.0 if self_conjugate else 0.5

    def per_rate(curve: str) -> float | None:
        limit = s.interpolate(curves[curve], mass) if curve in curves else None
        return scale / limit if limit else None

    return mixtures.bound("calore-2202.03076-pbar", rates, mass, per_rate)


def today_unknown(cls, p: Point) -> str:
    """Why the model's annihilation today is not computed (its ``today_unknown``), or not all of it (its
    ``today_hadronic``: the quark channels in the hadronic window), or ''. Every search that needs it (the CMB,
    γ-ray lines, antiprotons; the dwarfs and the Sun in ``scan``) is then undecided with this reason, never allowed by
    an empty rate; the CMB alone decides from the channels computed where they exclude by themselves (``cmb``)."""
    method = getattr(cls, "today_unknown", None)
    return (method(p) if callable(method) else "") or today_hadronic(cls, p)


def today_hadronic(cls, p: Point) -> str:
    """Why the annihilation today into quarks is not computed (the hadronic window), or ''."""
    method = getattr(cls, "today_hadronic", None)
    return method(p) if callable(method) else ""


def _spectrum_reference_reason(cls, p: Point) -> str:
    from adroit.parameter_space.flavour_vector import FlavourVectorClass
    return cls.spectrum_reference_reason(p) if isinstance(cls,FlavourVectorClass) else ""


EVALUATORS = (cmb, dark_photon, flavour, dilepton, lmu_ltau, muon_g2, partner, inert_doublet, two_hdma,
              two_hdm_flavour, bbn, neff, b_to_k_mumu, electroweak_precision, lep_charged,
              lhc_search,
              higgs_signal, heavy_scalar, monojet_spin0, lines, antiprotons)


def outcomes(cls, p: Point, unverified: bool = False, lhc_result: dict | None = None) -> list[Outcome]:
    """Every search that applies to the model at the point (``lhc_result``: SModelS's, if fetched in a batch)."""
    from adroit.parameter_space import resonances
    out = []
    for evaluator in (*EVALUATORS, *resonances.EVALUATORS):
        result = evaluator(cls, p, unverified) if evaluator is not lhc_search else lhc_search(cls, p, unverified,
                                                                                               lhc_result)
        if result is None:
            continue
        out += result if isinstance(result, list) else [result]
    records = {CMB: ["planck-2018-pann"], DARK_PHOTON: ["darkcast-dark-photon"],
               FLAVOUR: ["flavour-b-to-k-invisible"], DILEPTON: ["atlas-1903.06248-dilepton"],
               LEP_CONTACT: ["lep-contact-bl"], SQUARK: ["atlas-2010.14293-squark"],
               G2: ["muon-g2-2025"], LMU: ["ccfr-1406.2332-trident"], Z4MU: list(FOUR_MU),
               BSGAMMA: ["li-2412.04572-bsgamma"], BSMUMU: ["dmwg-1810.09420-bsmumu"],
               NEFF: ["escudero-1901.02010-neff"],
               FLAVOUR_MUMU: ["lhcb-1612.07818-b-to-k-mumu", "flavour-b-to-k-invisible"],
               EWPT: ["pdg-2024-electroweak-st"], LEP_CHARGED: ["lep-charginos", "opal-hep-ex-0309014-sleptons"],
               IDM_LEP: ["lep-inert-doublet"], TWO_HDMA: ["atlas-2306.00641-2hdma"],
               BBN: ["sabti-1910.01649-bbn"], LHC: ["smodels-3.2.1"],
               HIGGS_MU: ["atlas-2207.00092-higgs-mu"],
               HEAVY_SCALAR: ["atlas-2009.14791-zz", "atlas-2004.14636-ww"],
               MONOJET: ["cms-2107.13021-monojet-spin0"], LINES: list(LINE_RECORDS),
               PBAR: ["calore-2202.03076-pbar"],
               resonances.DIJET: ["cms-1806.00843-dijet", "atlas-1910.08447-dijet-gaussian"],
               resonances.TTBAR: ["cms-1908.01115-ttbar"],
               resonances.MONOH: ["atlas-2108.13391-monoh"], resonances.MONOZ: ["atlas-2111.08372-monoz"]}
    records[LMU_NATIVE] = ["lmu-ltau-babar-belle2"]
    # the records whose confidence level and construction are the outcome's, where it also reads another record's
    # theory inputs (AL2-13: the invisible decay's record gives B → K a its form factors, not LHCb's 95%)
    limits = {FLAVOUR_MUMU: ["lhcb-1612.07818-b-to-k-mumu"]}
    described = []
    for o in out:
        if o.excluded is not None and o.name in records and o.name not in resonances.OWN_NOTES:   # the audit's item 18
            o = o.model_copy(update={"flags": o.flags + [f for f in audit_notes.flags(records[o.name])
                                                             if f not in o.flags]})
        if o.name in records and o.name != LMU_NATIVE:
            sources = [s._record(rid) for rid in records[o.name]]
            judged = [s._record(rid) for rid in limits.get(o.name, records[o.name])]
            levels = {r.confidence_level for r in judged}
            level = levels.pop() if len(levels) == 1 else None
            construction = "; ".join(r.statistical_construction for r in judged)
            if o.name in (G2, HIGGS_MU, EWPT):
                level, construction = .95, "Gaussian measurement: central 1.96-sigma interval and delta chi-square"
            o = o.model_copy(update={"source": o.source or "; ".join(r.source for r in sources),
                                     "confidence_level": level, "statistical_construction": construction})
        described.append(o.at95())
    return described
