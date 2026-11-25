"""Explicit typed-model maps to existing portals, using coefficients in L.

Field content alone does not fix a model. These maps require the interactions
and flavour that the numerical portal actually computes. Unrepresented
interactions are rejected, except scalar self-quartics (irrelevant to the
portal's tree-level annihilation to other particles), which are reported.
"""

from __future__ import annotations

import math
from collections import Counter

from adroit.constraints import higgs, kinetic_mixing as km
from adroit.core.model_spec import FieldRole, ModelField, ModelSpec, ModelTerm, Phase
from adroit.library.interactions import derivation
from adroit.library.interactions.model_checks import coupling_value
from adroit.parameter_space.classes import Point
from adroit.parameter_space.classify import Unsupported
from adroit.parameter_space.portals.base import Portal
from adroit.parameter_space.portals.higgs import HiggsPortalScalar
from adroit.parameter_space.portals.tchannel import PARTNERS, TChannel
from adroit.parameter_space.portals.vector import DarkPhoton

PortalMatch = tuple[Portal, Point, list[str]]


def _fields(term: ModelTerm) -> Counter[str]:
    return Counter(o.field for o in term.fields)


def _singlet(field: ModelField) -> bool:
    c = field.charges
    return c.su3 == "1" and c.su2 == 1 and c.hypercharge == c.electric_charge == 0


def _mass(field: ModelField, default: float, slot: str, notes: list[str]) -> float:
    if field.mass_gev is None:
        notes.append(f"default {slot} = {default:g} GeV (library benchmark): {field.name}'s mass was not supplied")
        return default
    if not math.isfinite(field.mass_gev) or field.mass_gev <= 0:
        raise Unsupported(f"{field.name}: the portal needs a positive finite mass, not {field.mass_gev}")
    return field.mass_gev


def _coefficient(spec: ModelSpec, term: ModelTerm, scale: float, slot: str,
                 default: float | None, notes: list[str], dimension: int = 0) -> float:
    """Map C in L to a parameter; default only a single declared symbolic coefficient."""
    value = coupling_value(spec, term)
    if value is None:
        missing = next((c for c in spec.couplings if c.name == term.coupling.strip() and c.value is None), None)
        if missing is None or missing.mass_dimension != dimension or default is None:
            raise Unsupported(f"the coefficient {term.coupling!r} needs an explicit finite real value")
        notes.append(f"default {slot} = {default:g}: coefficient {missing.name} was not supplied "
                     f"(library benchmark; C = {default / scale:g} in L, {slot} = {scale:g} C)")
        return default
    if not math.isfinite(value):
        raise Unsupported(f"the coefficient {term.coupling!r} is not finite")
    scaled = derivation.evaluate_expression(term.coupling, derivation.symbol_table(spec), scale=2.0)
    if not math.isclose(scaled, 2.0 ** dimension * value, rel_tol=1e-10, abs_tol=0):
        unit = "dimensionless" if dimension == 0 else f"of mass dimension {dimension}"
        raise Unsupported(f"the coefficient {term.coupling!r} must be {unit} for this portal")
    mapped = scale * value
    if not math.isfinite(mapped):
        raise Unsupported(f"the mapped coefficient {term.coupling!r} is not finite")
    notes.append(f"{slot} = {mapped:.17g} from coefficient {term.coupling} = {value:.17g} in L "
                 f"({slot} = {scale:.17g} C)")
    return mapped


def _remaining(spec: ModelSpec, used: list[ModelTerm], notes: list[str]) -> None:
    for term in spec.terms:
        if any(term is t for t in used) or all(spec.field(o.field).role is FieldRole.standard_model
                                              for o in term.fields):
            continue
        if coupling_value(spec, term) == 0:
            continue
        names = _fields(term)
        field = spec.field(next(iter(names)))
        conjugates = sum(o.conjugate for o in term.fields)
        if (len(names) == 1 and len(term.fields) == 4 and field.spin == 0 and term.lorentz == "scalar"
                and (field.self_conjugate or conjugates == 2)):
            notes.append(f"self-quartic {term.coupling} retained in the typed model; it does not enter "
                         "this portal's tree-level annihilation to other particles or scattering")
            continue
        raise Unsupported(f"additional interaction {term.text or term.coupling!r} is not represented by this portal")


def _higgs_coupling(spec: ModelSpec, terms: list[ModelTerm], default: float, notes: list[str]) -> float:
    """Match S² H†H, or both gauge-related h S² and h² S² coefficients."""
    dm = spec.dark_matter
    name = "H" if spec.phase is Phase.unbroken else "h"
    h = next((f for f in spec.fields if f.name == name), None)
    if (h is None or h.role is not FieldRole.standard_model or h.spin != 0 or h.generations != 1
            or h.charges.su3 != "1" or any(h.charges.extra.values())):
        raise Unsupported("the scalar Higgs map requires the Standard Model Higgs field")
    if spec.phase is Phase.unbroken:
        if (len(terms) != 1 or h.charges.su2 != 2
                or not math.isclose(h.charges.hypercharge, 0.5, abs_tol=1e-6)
                or _fields(terms[0]) != Counter({dm.name: 2, "H": 2}) or terms[0].lorentz != "scalar"
                or sorted(o.conjugate for o in terms[0].fields if o.field == "H") != [False, True]
                or terms[0].plus_hc):
            raise Unsupported("the scalar Higgs map requires exactly one hermitian S² H†H coefficient")
        return _coefficient(spec, terms[0], -2.0, "g_chi", default, notes)
    if not _singlet(h) or (h.mass_gev is not None and not math.isclose(h.mass_gev, higgs.M_H, rel_tol=1e-10)):
        raise Unsupported(f"the scalar Higgs portal fixes the physical Higgs mass to {higgs.M_H:g} GeV")
    cubic = [t for t in terms if _fields(t) == Counter({dm.name: 2, "h": 1})]
    quartic = [t for t in terms if _fields(t) == Counter({dm.name: 2, "h": 2})]
    if (len(terms) != 2 or len(cubic) != 1 or len(quartic) != 1
            or any(t.lorentz != "scalar" or t.plus_hc for t in terms)):
        raise Unsupported("the broken-phase scalar Higgs map needs both h S² and h² S² coefficients")
    coupling = _coefficient(spec, cubic[0], -2 / higgs.V_HIGGS, "g_chi", None, notes, dimension=1)
    other = _coefficient(spec, quartic[0], -4.0, "g_chi", None, notes)
    if not math.isclose(coupling, other, rel_tol=1e-10, abs_tol=0):
        raise Unsupported("h S² and h² S² do not give the same scalar Higgs portal coupling")
    return coupling


def _scalar_higgs(spec: ModelSpec) -> PortalMatch:
    from adroit.parameter_space import library
    dm = spec.dark_matter
    if not _singlet(dm) or any(dm.charges.extra.values()):
        raise Unsupported("the scalar Higgs portal requires a real neutral singlet")
    terms = [t for t in spec.terms if dm.name in _fields(t) and any(o.field in ("H", "h") for o in t.fields)]
    notes = ["read as the real scalar Higgs portal; coefficients are the full coefficients in L"]
    benchmark = library.entry("higgs_portal_scalar").point
    coupling = _higgs_coupling(spec, terms, benchmark.g_chi, notes)
    _remaining(spec, terms, notes)
    point = Point(m_chi=_mass(dm, benchmark.m_chi, "m_chi", notes), m_med=higgs.M_H,
                  g_chi=coupling, g_q=0, g_l=0)
    notes.append(f"m_med = {higgs.M_H:g} GeV: the physical Standard Model Higgs mass")
    return HiggsPortalScalar(name=spec.name), point, notes


def _partner_flavour(spec: ModelSpec, med: ModelField, term: ModelTerm) -> str:
    fields = [spec.field(o.field) for o in term.fields if spec.field(o.field).role is FieldRole.standard_model]
    if len(fields) != 1 or fields[0].generations != 1:
        raise Unsupported("the t-channel portal needs one explicit SM flavour, not a generation multiplet")
    f = fields[0]
    name = f.name if f.name in PARTNERS else f"{f.name}R"
    if name not in PARTNERS:
        raise Unsupported(f"the t-channel flavour {f.name!r} is not represented by a numerical portal")
    if f.spin != 0.5 or f.chirality == "L" or (f.chirality != "R" and f.name not in PARTNERS):
        raise Unsupported("the t-channel portal requires a right-handed SM fermion")
    _, charge, coloured = PARTNERS[name]
    for field in (med, f):
        c = field.charges
        q = c.hypercharge if spec.phase is Phase.unbroken else c.electric_charge
        if c.su3 != ("3" if coloured else "1") or c.su2 != 1 or not math.isclose(q, charge, abs_tol=1e-6):
            raise Unsupported(f"{field.name}'s charges do not match the right-handed flavour {name}")
    phi = next(o for o in term.fields if o.field == med.name)
    sm = next(o for o in term.fields if o.field == f.name)
    if phi.conjugate == sm.conjugate:
        raise Unsupported("the t-channel Yukawa needs conjugate partner and SM charges")
    return name


def _tchannel(spec: ModelSpec, med: ModelField) -> PortalMatch:
    from adroit.parameter_space import library
    dm = spec.dark_matter
    if not _singlet(dm) or med.self_conjugate or (dm.chirality and not dm.self_conjugate):
        raise Unsupported("the t-channel portal requires singlet dark matter and a complex scalar partner")
    terms = [t for t in spec.terms if dm.name in _fields(t) and med.name in _fields(t)]
    if (len(terms) != 1 or len(terms[0].fields) != 3 or _fields(terms[0])[dm.name] != 1
            or _fields(terms[0])[med.name] != 1 or terms[0].lorentz != "chiral" or not terms[0].plus_hc):
        raise Unsupported("the t-channel portal requires one chiral partner–DM–SM Yukawa plus h.c.")
    term = terms[0]
    flavour = _partner_flavour(spec, med, term)
    benchmark_id = "tchannel_uR_majorana" if dm.self_conjugate else "tchannel_uR_dirac"
    benchmark = library.entry(benchmark_id if PARTNERS[flavour][2] else "lepton_portal_muR").point
    notes = [f"read as the {flavour} t-channel portal, with the supplied SM flavour"]
    y = _coefficient(spec, term, 1.0, "g_chi", benchmark.g_chi, notes)
    _remaining(spec, [term], notes)
    point = Point(m_chi=_mass(dm, benchmark.m_chi, "m_chi", notes),
                  m_med=_mass(med, benchmark.m_med, "m_med", notes), g_chi=y, g_q=0, g_l=0)
    return TChannel(name=spec.name, partner=flavour, majorana=dm.self_conjugate, conversion=spec.chemical_equilibrium), point, notes


def _dark_current(spec: ModelSpec, med: ModelField, notes: list[str]) -> tuple[float, list[ModelTerm]]:
    dm = spec.dark_matter
    terms = [t for t in spec.terms if _fields(t) == Counter({dm.name: 2, med.name: 1})]
    label = "scalar_current" if dm.spin == 0 else "vector"
    if (len(terms) != 1 or terms[0].lorentz != label or terms[0].plus_hc
            or sorted(o.conjugate for o in terms[0].fields if o.field == dm.name) != [False, True]):
        raise Unsupported("the dark photon needs an explicit pure dark current coefficient; "
                          "gauge charges alone do not specify its numerical coupling")
    g = _coefficient(spec, terms[0], 1.0, "g_chi", None, notes)
    if dm.spin == 0:
        seagulls = [t for t in spec.terms if _fields(t) == Counter({dm.name: 2, med.name: 2})]
        contact = coupling_value(spec, seagulls[0]) if len(seagulls) == 1 else None
        if (len(seagulls) != 1 or seagulls[0].lorentz != "scalar" or seagulls[0].plus_hc
                or sorted(o.conjugate for o in seagulls[0].fields if o.field == dm.name) != [False, True]
                or contact is None or not math.isclose(contact, g * g, rel_tol=1e-10, abs_tol=0)):
            raise Unsupported("the complex-scalar dark photon needs the gauge-related X² chi*chi coefficient g_chi²")
        _coefficient(spec, seagulls[0], 1.0, "g_chi²", None, notes)
        terms += seagulls
    return g, terms


def _dark_photon(spec: ModelSpec, med: ModelField) -> PortalMatch:
    from adroit.parameter_space import library
    dm = spec.dark_matter
    if (dm.self_conjugate or dm.spin not in (0, 0.5) or not _singlet(dm) or not _singlet(med)
            or not med.self_conjugate or dm.chirality):
        raise Unsupported("the dark photon map requires Dirac or complex-scalar singlet dark matter")
    mixing = [t for t in spec.terms if t.lorentz == "kinetic_mixing"]
    if (spec.phase is not Phase.unbroken or len(mixing) != 1
            or _fields(mixing[0]) != Counter({med.name: 1, "B": 1}) or mixing[0].plus_hc
            or spec.field("B").role is not FieldRole.standard_model or spec.field("B").spin != 1):
        raise Unsupported("the dark photon map needs one unbroken-phase hypercharge–dark kinetic mixing term")
    benchmark = library.entry("dark_photon_scalar" if dm.spin == 0 else "dark_photon_dirac").point
    notes = ["read as a dark photon with L mixing coefficient C = -epsilon/(2 cos(theta_W))"]
    epsilon = _coefficient(spec, mixing[0], -2 * km.COS_W, "g_q", benchmark.g_q, notes)
    if abs(epsilon) >= km.COS_W:
        raise Unsupported("the kinetic mixing coefficient does not give a positive definite kinetic matrix")
    g, currents = _dark_current(spec, med, notes)
    _remaining(spec, [*mixing, *currents], notes)
    point = Point(m_chi=_mass(dm, benchmark.m_chi, "m_chi", notes),
                  m_med=_mass(med, benchmark.m_med, "m_med", notes), g_chi=g, g_q=epsilon, g_l=0)
    notes.append("m_med is the dark-vector mass parameter before kinetic/mass diagonalisation")
    return DarkPhoton(name=spec.name, scalar_dm=dm.spin == 0), point, notes


def _nplet_kind(dark: list[ModelField]) -> str:
    """'real' or 'complex' for the dark-matter fields of an n-plet, or raise Unsupported: one Majorana field
    (Y = 0), one Dirac field (Y ≠ 0), one Weyl field (Y = 0, a real representation: n odd), or a vectorlike pair of
    Weyl fields (Y and −Y)."""
    n, y = dark[0].charges.su2, dark[0].charges.hypercharge
    if len(dark) == 2:
        a, b = dark
        if not (a.chirality and a.chirality == b.chirality) or not y or not math.isclose(y, -b.charges.hypercharge):
            raise Unsupported("two dark-matter fields form an n-plet only as a vectorlike pair: Weyl fields of one "
                              "chirality with hypercharges Y and −Y")
        return "complex"
    if len(dark) != 1:
        raise Unsupported("an electroweak n-plet is one Majorana or Dirac field, or a vectorlike pair of Weyl fields")
    f = dark[0]
    if f.chirality or f.self_conjugate:
        if y or n % 2 == 0:
            raise Unsupported("a Majorana or single Weyl n-plet must be real: Y = 0 and n odd")
        return "real"
    if not y:
        raise Unsupported("a Dirac n-plet with Y = 0 is two real n-plets: write it as a Majorana field")
    return "complex"


def _electroweak_nplet(spec: ModelSpec) -> PortalMatch | None:
    """A pure electroweak n-plet (portals.nplet): spin-½ dark matter in SU(2)'s n ≥ 2 representation with
    hypercharge Y, a colour singlet, with no new field besides it and no interaction besides its gauge couplings and
    its own mass term; None if the dark matter is no such multiplet."""
    from adroit.parameter_space.portals.nplet import ElectroweakNplet
    dark = [f for f in spec.fields if f.role is FieldRole.dark_matter]
    if (not dark or any(f.role not in (FieldRole.dark_matter, FieldRole.standard_model) for f in spec.fields)
            or any(f.spin != 0.5 or f.charges.su3 != "1" or f.charges.su2 < 2 or f.generations != 1 for f in dark)):
        return None
    n, y = dark[0].charges.su2, abs(dark[0].charges.hypercharge)
    if any(f.charges.su2 != n or any(f.charges.extra.values()) for f in dark):
        raise Unsupported("an electroweak n-plet's fields share one SU(2) representation and carry no other charge")
    if spec.phase is not Phase.unbroken:
        raise Unsupported("an electroweak n-plet is written above electroweak symmetry breaking, with its SU(2) × "
                          "U(1)_Y charges")
    kind = _nplet_kind(dark)
    if y > (n - 1) / 2 or not math.isclose((n - 1) / 2 - y, round((n - 1) / 2 - y)):
        raise Unsupported(f"an n = {n} multiplet with Y = {y:g} has no neutral member (Q = T₃ + Y ≠ 0)")
    names = {f.name for f in dark}
    extra = [t for t in spec.terms if not (len(t.fields) == 2 and {o.field for o in t.fields} <= names)]
    if extra:
        raise Unsupported("the n-plet engine computes the gauge interactions only; this model adds "
                          f"{extra[0].text or extra[0].lorentz}")
    masses = {f.mass_gev for f in dark}
    if None in masses or len(masses) != 1:
        raise Unsupported("the n-plet's fields need one common mass (GeV)")
    m = masses.pop()
    for term in spec.terms:                            # a stated mass coefficient must be the fields' mass
        value = coupling_value(spec, term)
        if value is not None and not math.isclose(abs(value), m, rel_tol=1e-6):
            raise Unsupported(f"the mass term's coefficient {term.coupling} = {value:g} differs from the fields' mass "
                              f"{m:g} GeV")
    point = Point(m_chi=m, m_med=1.0, g_q=0.0)
    if (n, y) in ((3, 0.0), (2, 0.5)):                 # the wino and the higgsino: the broken-phase engine
        from adroit.parameter_space.portals.multiplet import ElectroweakMultiplet
        multiplet = "wino" if n == 3 else "higgsino"
        return (ElectroweakMultiplet(name=multiplet, multiplet=multiplet), point,
                [f"the {multiplet}: M = {m:g} GeV, the broken-phase engine (portals.multiplet)"])
    if n == 2 or kind == "real" and n % 2 == 0:
        raise Unsupported(f"no electroweak engine computes an n = {n} multiplet with Y = {y:g}")
    notes = [f"an electroweak {n}-plet with Y = {y:g} ({'Majorana' if kind == 'real' else 'Dirac'}): M = {m:g} GeV, "
             "its relic density from the SU(2) × U(1) symmetric limit (portals.nplet)"]
    return ElectroweakNplet(name=f"{n}-plet, Y = {y:g}", n=n, hypercharge=y), point, notes


def match_portal(spec: ModelSpec) -> PortalMatch | None:
    """Return an explicit portal map, None for other families, or raise Unsupported.

    Scalar mixing requires a mass-basis/potential matching that is not inferred
    here. Library-selected benchmarks remain available through for_portal().
    """
    nplet = _electroweak_nplet(spec)
    if nplet is not None:
        return nplet
    dm = spec.dark_matter
    others = [f for f in spec.fields if f.role not in (FieldRole.dark_matter, FieldRole.standard_model)]
    if sum(f.role is FieldRole.dark_matter for f in spec.fields) != 1 or dm.generations != 1:
        raise Unsupported("a portal map needs exactly one dark-matter species")
    if dm.spin == 0 and dm.self_conjugate and not others:
        return _scalar_higgs(spec)
    if len(others) > 1:
        raise Unsupported("a supported portal map needs at most one additional mediator species")
    if not others:
        return None
    med = others[0]
    if med.generations != 1:
        raise Unsupported("a portal map needs exactly one mediator species")
    if med.spin == 1 and any(t.lorentz == "kinetic_mixing" for t in spec.terms):
        return _dark_photon(spec, med)
    if dm.spin == 0.5 and med.spin == 0 and not _singlet(med):
        return _tchannel(spec, med)
    if dm.spin == 0.5 and med.spin == 0 and med.self_conjugate and any(
            o.field in ("H", "h") for t in spec.terms for o in t.fields):
        raise Unsupported("singlet scalar mixing needs an explicit mass-eigenstate/potential matching; "
                          "a Higgs interaction does not specify a mixing angle or scalar self-couplings")
    return None
