"""The 2HDM+a through the generic route (P5 of ``docs/generic_route_next.md``): the LHC DM Working Group's model
(Bauer, Haisch & Kahlhoefer, arXiv:1701.07427; the library's UFO ``Pseudoscalar_2HDM``) recognised in a generic model by
a structural match, so that ATLAS's 2HDM+a combination, mono-h and mono-Z apply to it.

**The model in the Higgs basis.** The UFO writes its potential in the Higgs basis, Φ₁ with the vacuum v and Φ₂ without:
V = μ₁|Φ₁|² + μ₂|Φ₂|² + (μ₃Φ₁†Φ₂ + h.c.) + l₁|Φ₁|⁴ + l₂|Φ₂|⁴ + l₃|Φ₁|²|Φ₂|² + l₄|Φ₁†Φ₂|²
    + [l₅(Φ₁†Φ₂)² + l₆|Φ₁|²Φ₁†Φ₂ + l₇|Φ₂|²Φ₁†Φ₂ + h.c.] + ½m_P²P² + P(i μ_P Φ₁†Φ₂ + h.c.)
    + P²[l_P1|Φ₁|² + l_P2|Φ₂|² + l_P(Φ₁†Φ₂ + h.c.)],
with L ⊃ i y_χ P χ̄γ⁵χ and type-II Yukawas, Φ₂'s being Φ₁'s times cot β for up-type quarks and −tan β for down-type
quarks and leptons. ``higgs_basis`` is the UFO's own map (its ``parameters.py``) from the Working Group's parameters
(the masses, sin θ, tan β, sin(β − α), λ₃, λ_P1, λ_P2, y_χ, m_χ) to these; ``spec`` writes the model as a generic spec
(Φ₁ is the Standard Model's H, so only at alignment, sin(β − α) = 1, where μ₁ and l₁ are the Standard Model's).

**The match.** A generic model whose new fields are a second colourless scalar doublet with |Y| = ½ and a real
colourless scalar singlet, both Z₂-even, and a Dirac fermion as the dark matter, is read at the point from its own
rules: the five scalar masses; sin θ and y_χ from a's and A's couplings to χ; tan β from H's, A's and a's Yukawa
couplings relative to the Standard Model h's (the type-II pattern checked flavour by flavour to 10⁻⁶, the θ it implies
against the χ couplings', and the relative sign of a's and A's couplings); alignment from h's couplings; λ₃, λ_P1 and
λ_P2 from the trilinears h H⁺H⁻, h a a and H a a (``_lambdas``). The library's UFO at those parameters must then give
the generic model's scalar trilinear and quartic couplings and its gauge couplings between different states within 1%
(``_compared``). Then the library's evaluators run on the UFO at those parameters (``Match.portal``); otherwise the
searches are undecided with the reason. Yukawa couplings are compared as ratios to the same code's h coupling: the
two codes' Yukawa masses differ (G2 runs m_b and m_c to m_h), their ratios do not.
"""
from __future__ import annotations

import cmath
import math

from adroit.core.state import StrictModel

TOLERANCE = 0.01                 # the couplings, the UFO against the generic model (``_compared``)
PATTERN = 1e-6                   # coupling ratios (dimensionless)


def higgs_basis(x: dict[str, float], v: float) -> dict[str, float]:
    """The UFO's Higgs-basis parameters from the Working Group's (module docstring; its ``parameters.py``, with
    the vacuum v), in forms that do not subtract nearly equal masses (the auditor's RC20-03, 2026-10-20):
    m_A² = m_H3² cos²θ + m_H4² sin²θ and m_P² = m_H3² sin²θ + m_H4² cos²θ, sums of positive terms (the UFO's
    (m_H3² + m_H4² ± (m_H3² − m_H4²) cos 2θ)/2 had cancelled a 0.5 MeV singlet's m_P² to zero under a rule that set
    every sum below 10⁻¹² of its terms to zero); l4 and l5 from mass differences, (m² − m_A²) = (m² − m_H3²) cos²θ +
    (m² − m_H4²) sin²θ, so an exact degeneracy (H = A = H±, the recheck's RB20-05) gives exactly zero. The other sums
    are exactly rounded (``math.fsum``); no small residual is set to zero."""
    mh1, mh2, mh3, mh4, mhc = (x[k] ** 2 for k in ("mh1", "mh2", "mh3", "mh4", "mhc"))
    s, tb, lam3 = x["sinbma"], x["tanbeta"], x["lam3"]
    c2 = (cmath.cos(2 * (math.pi / 2 - cmath.asin(s)))).real
    s2 = (cmath.sin(2 * (math.pi / 2 - cmath.asin(s)))).real
    d, dm, v2 = tb - 1 / tb, mh2 - mh1, v * v
    sp2 = x["sinp"] ** 2
    cp2 = 1 - sp2

    def from_a(m2: float) -> float:
        """m² − m_A², from the mass differences."""
        return (m2 - mh3) * cp2 + (m2 - mh4) * sp2
    fsum = math.fsum
    out = {
        "mA2": mh3 * cp2 + mh4 * sp2, "mP2": mh3 * sp2 + mh4 * cp2,
        "mu1": -fsum((mh1 * (1 + c2), mh2 * (1 - c2))) / 4, "mu3": -dm * s2 / 4,
        "mu2": fsum((-mh1, -mh2, 8 * mhc, -4 * lam3 * v2, -3 * dm * c2, -dm * d * s2)) / 4,
        "l1": fsum((mh1 * (1 + c2), mh2 * (1 - c2))) / (4 * v2),
        "l2": fsum((-4 * mhc * d ** 2, mh1 * (1 + d ** 2), mh2 * (1 + d ** 2), 2 * lam3 * d ** 2 * v2,
                    dm * (-7 + 3 / tb ** 2 + 3 * tb ** 2) * c2, -dm * (tb ** -3 - 5 / tb + 5 * tb - tb ** 3) * s2))
        / (4 * v2),
        "l3": fsum((mh1, mh2, -4 * mhc, 4 * lam3 * v2, 3 * dm * c2, dm * d * s2)) / (2 * v2),
        "l4": fsum((-2 * from_a(mhc), (mh1 - mhc) * (1 - c2), (mh2 - mhc) * (1 + c2))) / (2 * v2),
        "l5": fsum((from_a(mh1) * (1 - c2), from_a(mh2) * (1 + c2))) / (4 * v2),
        "l6": dm * s * math.sqrt(max(1 - s * s, 0.0)) / v2,
        "l7": fsum((-mh1 * d, -mh2 * d, 4 * mhc * d, -2 * lam3 * d * v2, -3 * dm * d * c2, -dm * (-1 + d ** 2) * s2))
        / (2 * v2),
        "muP": (mh3 - mh4) * 2 * x["sinp"] * math.sqrt(1 - x["sinp"] ** 2) / (2 * v),
        "lP": (x["laP2"] - x["laP1"]) * tb / (1 + tb ** 2),
        "lP1": (x["laP1"] + x["laP2"] * tb ** 2) / (1 + tb ** 2),
        "lP2": (x["laP2"] + x["laP1"] * tb ** 2) / (1 + tb ** 2),
    }
    return out


def spec(x: dict[str, float], name: str = "two_hdm_a_higgs_basis"):
    """The 2HDM+a at the Working Group's parameters ``x`` as a generic spec in the Higgs basis (module docstring),
    at alignment only. L = −V, so each potential coefficient enters as −l."""
    from adroit.core.model_spec import ModelSpec
    from adroit.model_building.gauge_basis import V_EW
    if not math.isclose(x["sinbma"], 1.0, abs_tol=1e-12):
        raise ValueError("the generic spec of the 2HDM+a is written at alignment, sin(β − α) = 1")
    h = higgs_basis(x, V_EW)
    p_mass2 = h["mP2"] - h["lP1"] * V_EW ** 2        # the UFO's m_P² holds l_P1 v²; the Lagrangian's does not
    if h["mu2"] <= 0:
        raise ValueError(f"μ₂ = {h['mu2']:.4g} GeV² is not a positive mass term")
    tb = x["tanbeta"]
    doublet = {"su2": 2, "hypercharge": 0.5}
    fields = [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": x["MXd"]},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": doublet},
        {"name": "H2", "role": "mediator", "spin": 0, "charges": doublet, "mass_gev": math.sqrt(h["mu2"])},
        {"name": "P", "role": "mediator", "spin": 0, "self_conjugate": True},
        {"name": "Q", "role": "standard_model", "spin": 0.5, "chirality": "L", "generations": 3,
         "charges": {"su3": "3", "su2": 2, "hypercharge": 1 / 6}},
        {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R", "generations": 3,
         "charges": {"su3": "3", "hypercharge": 2 / 3}},
        {"name": "dR", "role": "standard_model", "spin": 0.5, "chirality": "R", "generations": 3,
         "charges": {"su3": "3", "hypercharge": -1 / 3}},
        {"name": "L", "role": "standard_model", "spin": 0.5, "chirality": "L", "generations": 3,
         "charges": {"su2": 2, "hypercharge": -0.5}},
        {"name": "eR", "role": "standard_model", "spin": 0.5, "chirality": "R", "generations": 3,
         "charges": {"hypercharge": -1.0}},
    ]

    def occ(*names):
        return [{"field": n.rstrip("*"), "conjugate": n.endswith("*")} for n in names]
    quartic = [
        (("H2", "H2", "H2*", "H2*"), "l2", "", False),
        (("H", "H*", "H2", "H2*"), "l3", "H[i] H*[i] H2[j] H2*[j]", False),
        (("H", "H*", "H2", "H2*"), "l4", "H[i] H*[j] H2[j] H2*[i]", False),
        (("H*", "H*", "H2", "H2"), "l5", "H*[i] H*[j] H2[i] H2[j]", True),
        (("H", "H*", "H*", "H2"), "l6", "H[i] H*[i] H*[j] H2[j]", True),
        (("H*", "H2", "H2", "H2*"), "l7", "H*[i] H2[i] H2[j] H2*[j]", True),
        (("H", "H*", "P", "P"), "lP1", "", False),
        (("H2", "H2*", "P", "P"), "lP2", "", False),
        (("H*", "H2", "P", "P"), "lP", "", True),
    ]
    terms, couplings = [], []
    for fs, key, idx, hc in quartic:
        terms.append({"fields": occ(*fs), "lorentz": "scalar", "coupling": f"c_{key}", "plus_hc": hc, "indices": idx})
        couplings.append({"name": f"c_{key}", "value": -h[key]})
    terms += [
        {"fields": occ("P", "P"), "lorentz": "scalar", "coupling": "c_mP"},          # −½ m₀² P², either sign
        {"fields": occ("H*", "H2", "P"), "lorentz": "scalar", "coupling": "-I*mu_P", "plus_hc": True},
        {"fields": occ("chi*", "chi", "P"), "lorentz": "pseudoscalar", "coupling": "y_chi"},
        {"fields": occ("Q*", "H2", "dR"), "lorentz": "scalar", "coupling": "xi_d*sqrt(2)*m_q/v", "plus_hc": True},
        {"fields": occ("Q*", "H2*", "uR"), "lorentz": "scalar", "coupling": "xi_u*sqrt(2)*m_q/v", "plus_hc": True},
        {"fields": occ("L*", "H2", "eR"), "lorentz": "scalar", "coupling": "xi_d*sqrt(2)*m_l/v", "plus_hc": True},
    ]
    couplings += [{"name": "c_mP", "value": -p_mass2 / 2, "mass_dimension": 2},
                  {"name": "mu_P", "value": h["muP"], "mass_dimension": 1}, {"name": "y_chi", "value": x["gPXd"]},
                  {"name": "xi_u", "value": 1 / tb}, {"name": "xi_d", "value": -tb}]
    return ModelSpec.model_validate({"name": name, "phase": "unbroken", "fields": fields, "terms": terms,
                                     "couplings": couplings})


class Match(StrictModel):
    """A generic model read as the 2HDM+a: the Working Group's parameters, and how it compared with the UFO."""
    values: dict[str, float]
    names: dict[str, str]                      # the generic model's particle → the UFO's
    worst: str = ""                            # the largest difference found, for the record

    def portal(self):
        """The library's UFO model at these parameters, and its point (the scan's slots)."""
        from adroit.parameter_space import library
        from adroit.parameter_space.classes import Point
        base = library.entry("two_hdm_a").model_class
        x = self.values
        fixed = {k: repr(float(x[k])) for k in ("mh1", "mh2", "mh3", "mhc", "lam3", "laP1", "laP2", "sinbma")}
        params = {**base.parameters, **fixed, "MXd": "m_chi", "mh4": "m_med", "gPXd": "g_chi", "sinp": "g_q",
                  "tanbeta": "g_l"}
        point = Point(m_chi=x["MXd"], m_med=x["mh4"], g_chi=x["gPXd"], g_q=x["sinp"], g_l=x["tanbeta"])
        return base.model_copy(update={"parameters": params}), point


def match(engine, p) -> Match | str | None:
    """The generic model read as the 2HDM+a at the point (module docstring): the match, the reason it is not the
    model, or None if it does not have the 2HDM+a's fields."""
    from adroit.parameter_space.portals.generic import GenericModel
    if not isinstance(engine, GenericModel):
        return None
    if not _fields(engine.model_spec()):
        return None
    key = (engine.spec_json, engine.scan, engine.tied, p.m_chi, p.m_med)
    if key not in _MATCHES:
        if len(_MATCHES) > 256:
            _MATCHES.clear()
        _MATCHES[key] = _read(engine, p)
    return _MATCHES[key]


_MATCHES: dict[tuple, Match | str] = {}


def _fields(spec) -> bool:
    """The 2HDM+a's new fields and no others: a Z₂-even colourless scalar doublet with |Y| = ½, a real Z₂-even
    colourless scalar singlet, and a Dirac fermion as the dark matter."""
    new = [f for f in spec.fields if f.role.value != "standard_model"]
    if len(new) != 3 or any(f.charges.su3 != "1" or any(f.charges.extra.values()) for f in new):
        return False
    doublet = [f for f in new if f.spin == 0 and f.dark_parity != -1 and f.charges.su2 == 2
               and math.isclose(abs(f.charges.hypercharge), 0.5)]
    singlet = [f for f in new if f.spin == 0 and f.dark_parity != -1 and f.charges.su2 == 1 and f.self_conjugate
               and f.charges.hypercharge == 0]
    dirac = [f for f in new if f.spin == 0.5 and f.dark_parity == -1 and not f.self_conjugate and f.charges.su2 == 1
             and f.charges.hypercharge == 0]
    return len(doublet) == len(singlet) == len(dirac) == 1


def _read(engine, p) -> Match | str:
    """The Working Group's parameters from the model's rules at the point, then the comparison with the UFO."""
    from adroit.model_building.gauge_basis import V_EW
    from adroit.parameter_space.portals import generic_portrait as gp
    from adroit.parameter_space.portals.generic import _feeble
    _, rules, tree_model = engine.at(p)
    if why := _feeble(engine.spec_json, engine.scan, engine.tied, p.m_chi, p.m_med):
        return f"the generic route refuses it: {why}"            # its own reason, not a wrong CP content (RB20-05)
    found = gp.portraits(engine, p)
    even, odd = [m for m in found if m.cp == "even"], [m for m in found if m.cp == "odd"]
    charged = [r for r in rules.particles if r.parity == 1 and r.spin == 0 and math.isclose(abs(r.charge), 1.0)]
    dm = [r for r in rules.particles if r.parity == -1 and r.spin == 0.5]
    if len(found) != 3 or len(even) != 1 or len(odd) != 2 or len(charged) != 1 or len(dm) != 1:
        return ("its new scalars are not one CP-even and two CP-odd neutral states and a charged one "
                f"({', '.join(m.cp or '?' for m in found)}; {len(charged)} charged)")
    sm = gp._standard()["h"]
    own = gp._sm_couplings(rules, "h", set(sm))
    off = max(abs(own.get(f, (0.0, 0.0))[0] / sm[f][0] - 1) for f in sm if sm[f][0])
    if off > PATTERN:
        return (f"h's couplings differ from the Standard Model's (by up to {off:.2g}): the 2HDM+a away from "
                "alignment, which the generic route does not state and ATLAS's searches are not calibrated for")
    from adroit.core.model_spec import YUKAWA_CONVENTIONS
    declared = engine.model_spec().yukawa
    ratios = _yukawa_ratios(even[0], odd, sm, declared)
    if isinstance(ratios, str):
        other = next((c for c in YUKAWA_CONVENTIONS if c != declared
                      and not isinstance(_yukawa_ratios(even[0], odd, sm, c), str)), None)
        if other:                                               # named, not read as a wrong Yukawa type (decision #2)
            return (f"its new scalars' Yukawas follow the {other!r} convention's inputs while the model declares "
                    f"{declared!r}: a Yukawa-convention mismatch, not a wrong Yukawa type")
        return ratios
    return _type_two(engine, p, even[0], odd, charged[0], dm[0], ratios, tree_model, rules, V_EW)


def _yukawa_ratios(heavy, odd, sm: dict, convention: str) -> dict | str:
    """Each new scalar's coupling to each fermion group as a multiple of the Higgs boson's, taken in the model's
    declared Yukawa inputs (``model_building.yukawa``: h's own couplings are the "sm" convention's, so they are
    rescaled by m_f(declared)/m_f(sm)), checked to be one factor per group; or why not. The Higgs boson's alignment is
    checked apart, against the Standard Model's own couplings."""
    from adroit.model_building import yukawa
    from adroit.model_building.feynman import SM_FERMIONS
    groups = {"up": [f.name for f in SM_FERMIONS if f.up and f.colour == "3"],
              "down": [f.name for f in SM_FERMIONS if not f.up and f.colour == "3"], "lepton": ["e", "mu", "tau"]}
    ratios = {}
    for m, part in ((heavy, "even"), *((x, "odd") for x in odd)):
        for group, names in groups.items():
            scale = {f: yukawa.mass(convention, f) / yukawa.mass(yukawa.SM, f) for f in names}
            values = [getattr(m.coupling(f), part) / (sm[f][0] * scale[f]) if m.coupling(f) else 0.0 for f in names]
            if max(values) - min(values) > PATTERN * max(max(abs(v) for v in values), PATTERN):
                return f"{m.name}'s {group}-type couplings are not each fermion's Yukawa times one factor"
            ratios[m.name, group] = values[0]
    return ratios


def _type_two(engine, p, heavy, odd, charged, dm, ratios, tree_model, rules, v) -> Match | str:
    """tan β, θ and y_χ from the couplings (the type-II pattern checked), the λ's from the trilinears."""
    big, small = sorted(odd, key=lambda m: -abs(ratios[m.name, "up"]))        # A: the larger doublet part
    r = {k: ratios[name, k] for name in (heavy.name,) for k in ("up", "down", "lepton")}
    if not (r["up"] and r["down"]) or abs(r["down"] - r["lepton"]) > PATTERN * abs(r["down"]) \
            or abs(abs(r["up"] * r["down"]) - 1) > PATTERN or r["up"] * r["down"] > 0:
        return (f"H's couplings are not type II (up {r['up']:.4g}, down {r['down']:.4g}, leptons {r['lepton']:.4g} "
                "times h's; type II has −cot β, tan β, tan β)")
    tb = abs(r["down"])
    for m in (big, small):
        u, d, lep = (ratios[m.name, k] for k in ("up", "down", "lepton"))
        if m is small and u == d == lep == 0.0:
            continue                      # a pure singlet (θ = 0 exactly): no Yukawas to compare (B20-10)
        if u * d <= 0 or abs(d - lep) > PATTERN * abs(d) or abs(d / u - tb * tb) > PATTERN * tb * tb:
            return f"{m.name}'s couplings are not type II at tan β = {tb:.4g} (up {u:.4g}, down {d:.4g})"
    if heavy.dark_matter and abs(heavy.dark_matter.even) + abs(heavy.dark_matter.odd) > PATTERN:
        return "H couples to the dark matter, which the 2HDM+a's does not"
    g_a = small.dark_matter.odd if small.dark_matter else 0.0
    g_A = big.dark_matter.odd if big.dark_matter else 0.0
    evens = [abs(m.dark_matter.even) for m in (big, small) if m.dark_matter]
    if not g_a and not g_A:
        return "a and A do not couple to the dark matter"
    if not g_a or (evens and max(evens) > PATTERN * max(abs(g_a), abs(g_A))):
        return "a's and A's couplings to the dark matter are not pseudoscalar"
    y = math.hypot(g_a, g_A)
    sin_t, cos_t = abs(g_A) / y, abs(g_a) / y
    from_yukawas = abs(ratios[small.name, "up"] / ratios[big.name, "up"])
    if abs(from_yukawas - sin_t / cos_t) > 1e-5 * max(1.0, sin_t / cos_t):
        return (f"a and A mix by tan θ = {sin_t / cos_t:.5g} in their dark-matter couplings and "
                f"{from_yukawas:.5g} in their Yukawas: not one mixing angle")
    if (g_a * ratios[big.name, "up"]) * (g_A * ratios[small.name, "up"]) > 0:
        return "a's and A's couplings have the wrong relative sign for the 2HDM+a (their interference)"
    x = {"MXd": dm.mass, "mh1": next(q.mass for q in rules.particles if q.name == "h"), "mh2": heavy.mass_gev,
         "mh3": big.mass_gev, "mh4": small.mass_gev, "mhc": charged.mass, "sinp": sin_t, "tanbeta": tb,
         "sinbma": 1.0, "gPXd": y}
    lam = _lambdas(x, tree_model, heavy.name, big.name, small.name, charged, -math.copysign(1.0, r["up"]), v)
    if isinstance(lam, str):
        return lam
    names = {"h": "h1", heavy.name: "h2", big.name: "h3", small.name: "h4", charged.name: "h+",
             charged.anti or f"{charged.name}~": "h-", dm.name: "Xd"}
    found = Match(values={**x, **lam}, names=names)
    worst = _compared(found, tree_model)
    if worst[0] > TOLERANCE:
        return f"the library's 2HDM+a at the parameters read from it differs: {worst[1]}"
    return found.model_copy(update={"worst": worst[1]})


def _lambdas(x, tree_model, heavy, big, small, charged, sign_heavy, v) -> dict[str, float] | str:
    """λ₃, λ_P1 and λ_P2 from the trilinears h H⁺H⁻, h a a and H a a, which at alignment are −l₃v, −[(l₃ + l₄ − 2l₅)
    s_θ² + 2l_P1 c_θ²]v + 2μ_P s_θc_θ and −(l₇s_θ² + 2l_P c_θ²)v (the UFO's vertices; H's sign as the UFO's)."""
    def c(*legs) -> float:
        found = tree_model.find(list(legs))
        return float(found[0][0].c.real) if found else 0.0
    anti = charged.anti or f"{charged.name}~"
    tb, s, co = x["tanbeta"], x["sinp"], math.sqrt(1 - x["sinp"] ** 2)
    l3 = -c("h", charged.name, anti) / v
    lam3 = (2 * v * v * l3 - x["mh1"] ** 2 - x["mh2"] ** 2 + 4 * x["mhc"] ** 2 - 3 * (x["mh2"] ** 2 - x["mh1"] ** 2)) / (4 * v * v)
    h = higgs_basis({**x, "lam3": lam3, "laP1": 0.0, "laP2": 0.0}, v)
    l7_read = -sign_heavy * c(heavy, charged.name, anti) / v
    if abs(l7_read - h["l7"]) > TOLERANCE * max(abs(h["l7"]), 1e-3):
        return f"H H⁺H⁻ is {l7_read * v:.4g} GeV against the 2HDM+a's {h['l7'] * v:.4g} GeV at λ₃ = {lam3:.4g}"
    lp1 = (-c("h", small, small) + 2 * h["muP"] * s * co - (h["l3"] + h["l4"] - 2 * h["l5"]) * s * s * v) / (2 * co * co * v)
    lp = (-sign_heavy * c(heavy, small, small) / v - h["l7"] * s * s) / (2 * co * co)
    gap = lp * (1 + tb * tb) / tb                                     # λ_P2 − λ_P1
    lap1 = lp1 - gap * tb * tb / (1 + tb * tb)
    return {"lam3": lam3, "laP1": lap1, "laP2": lap1 + gap}


def _compared(found: Match, tree_model) -> tuple[float, str]:
    """The largest relative difference between the generic model's and the UFO's vertices among the scalars and the
    electroweak bosons, with what it was: SSS, SSSS, VSS and VVS, each vector leg scaled by the ratio of the two codes'
    couplings of that vector to a lepton (their electroweak schemes differ: the UFO's W is 79.82 GeV at tree level,
    G1's 80.37 GeV). A state's own gauge couplings (VSS between a state and its antiparticle, and the quartic VVSS)
    are fixed by its quantum numbers, which ``_fields`` checks, and differ by the schemes' s_W² alone; the VSS between
    different states carry the mixing.

    Every vertex either model has is compared, a missing one as zero, so a quartic the generic model lacks is a
    difference; and a vertex no rephasing of its fields can change the sign of (``_sign_definite``: each real field an
    even number of times, each complex one as often as its antiparticle, as |H₂|⁴'s H⁺H⁺H⁻H⁻) is compared with its
    sign, the others in magnitude (the two codes' field phases may differ). The tactical audit's T20-05 (2026-10-20):
    with λ_P1 = λ_P2 = 0, |H₂|⁴'s coupling set to zero or reversed had still matched."""
    cls, point = found.portal()
    ufo = cls.model(point)
    vectors = _vectors(tree_model, ufo)
    names = dict(found.names) | {v: u for v, (u, _) in vectors.items()}
    inverse = {u: n for n, u in names.items()}
    pairs = []
    for vertex in tree_model.vertices:
        if _comparable(vertex.kind, vertex.legs, names, vectors):
            theirs = ufo.find([names[n] for n in vertex.legs])
            pairs.append((vertex.kind, vertex.legs, vertex.c, theirs[0][0].c if theirs else 0.0))
    for vertex in ufo.vertices:
        legs = tuple(inverse.get(n, "") for n in vertex.legs)
        if _comparable(vertex.kind, legs, names, vectors) and not tree_model.find(list(legs)):
            pairs.append((vertex.kind, legs, 0.0, vertex.c))
    worst, what = 0.0, "none"
    for kind, legs, ours, theirs in pairs:
        ours = complex(ours) * math.prod(vectors[n][1] for n in legs if n in vectors)
        signed = _sign_definite(legs, tree_model.particles)
        a, b = (ours, complex(theirs)) if signed else (abs(ours), abs(complex(theirs)))
        scale = max(abs(a), abs(b))
        if scale < 1e-9:
            continue
        gap = abs(a - b) / scale
        if gap > worst:
            shown = (lambda z: f"{z.real:.5g}") if signed else (lambda z: f"{abs(z):.5g}")
            worst, what = gap, f"{kind} {'-'.join(legs)}: {shown(ours)} against {shown(complex(theirs))}"
    return worst, what


def _comparable(kind: str, legs, names: dict, vectors: dict) -> bool:
    """A vertex ``_compared`` compares: among the mapped scalars and vectors, not a state's own gauge coupling."""
    if kind not in ("SSS", "SSSS", "VSS", "VVS") or not all(n in names for n in legs):
        return False
    scalars = [n for n in legs if n not in vectors]
    return not (kind == "VSS" and scalars[0].rstrip("~") == scalars[1].rstrip("~"))


def _sign_definite(legs, particles: dict) -> bool:
    """Whether a vertex's sign is the same under every rephasing of its fields (``_compared``)."""
    from collections import Counter
    count = Counter(legs)
    for name in {n.rstrip("~") for n in legs}:
        q = particles.get(name)
        anti = q.anti if q is not None and q.anti and q.anti != name else ""
        if anti and count.get(name, 0) != count.get(anti, 0):
            return False
        if not anti and sum(k for n, k in count.items() if n.rstrip("~") == name) % 2:
            return False
    return True


def _vectors(tree_model, ufo) -> dict[str, tuple[str, float]]:
    """The electroweak bosons of the two models matched by spin, charge and mass (the photon by charge alone), each
    with the ratio of the UFO's to the generic model's coupling of it to a lepton (W to e ν, Z to ν ν, the photon to
    e e)."""
    out = {}
    for name, q in tree_model.particles.items():
        if q.spin != 1 or q.colour != "1":
            continue
        match = [n for n, u in ufo.particles.items() if u.spin == 1 and u.colour == "1"
                 and math.isclose(u.charge, q.charge) and abs(u.mass - q.mass) < 0.02 * max(q.mass, 1.0)]
        if len(match) != 1:
            continue
        ratio = _lepton_coupling(ufo, match[0]) / _lepton_coupling(tree_model, name, ufo_names=False)
        out[name] = (match[0], ratio if math.isfinite(ratio) and ratio > 0 else 1.0)
    return out


def _lepton_coupling(model, vector: str, ufo_names: bool = True) -> float:
    """|g_L| + |g_R| of the vector's coupling to the lightest lepton pair it joins (FFV), or nan."""
    for vertex in model.vertices:
        if vertex.kind == "FFV" and vector in vertex.legs:
            others = [n.rstrip("~").rstrip("+-") for n in vertex.legs if n != vector]
            if all(o in ("e", "ve", "nu_e") for o in others):
                return abs(vertex.c) + abs(vertex.c2)
    return float("nan")
