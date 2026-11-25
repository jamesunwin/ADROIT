"""Which computable class a typed model belongs to, and its parameter point (DM13).

A model is read term by term (DM8's ``ModelSpec``, either phase):
- **spin-1 mediator**: Dirac dark matter and one neutral vector mediator, with a
  vector (or axial) coupling to the dark matter and the same structure to the
  quarks, one universal value, and optionally to the charged leptons;
- **scalar mediator**: Dirac dark matter and one real scalar mediator, with a
  scalar or pseudoscalar coupling to the dark matter, and couplings to quarks in
  proportion to their masses (written g·m_q/v).

Anything else raises ``Unsupported`` with the reason. The scan then cannot
compute the relic density, and the report says so.
"""

from __future__ import annotations

from collections import Counter
import math

import sympy

from adroit.constraints import spin1
from adroit.core.model_spec import FieldRole, ModelField, ModelSpec, ModelTerm, sector
from adroit.library.interactions.model_checks import coupling_value
from adroit.parameter_space.classes import V_HIGGS, Point, ScalarClass, Spin1Class
from adroit.parameter_space import relations
from adroit.parameter_space.portals.base import Portal
from adroit.parameter_space.relations import CouplingRelation

QUARKS = {"quark"}
LEPTONS = {"lepton"}


class Unsupported(ValueError):
    """The model is not in a class whose whole picture the scan can compute."""


def _value(spec: ModelSpec, term: ModelTerm) -> float:
    """A term's finite numerical coupling."""
    value = coupling_value(spec, term)
    if value is None:
        raise Unsupported(f"the coupling {term.coupling} has no value")
    if not math.isfinite(value):
        raise Unsupported(f"the coupling {term.coupling} is not finite")
    return value


def _yukawa_value(spec: ModelSpec, term: ModelTerm, name: str, family: str) -> float:
    """Preserve a linear own-mass Yukawa and any explicit electroweak scale."""
    from adroit.core.arithmetic import check_formula
    expr = sympy.sympify(check_formula(term.coupling))           # never text SymPy would run as Python
    masses = {s for s in expr.free_symbols if str(s).startswith("m_")}
    allowed = {f"m_{name}", "m_q" if family == "quark" else "m_l", "m_f"}
    if len(masses) != 1 or str(next(iter(masses))) not in allowed:
        raise Unsupported(f"{name}: the simplified Yukawa must use this fermion's own mass")
    v = sympy.Symbol("v")
    mass_symbol = next(iter(masses))
    supplied = next((c.value for c in spec.couplings if c.name == str(mass_symbol)), None)
    fixed = next((f.mass_gev for f in spin1.FERMIONS if f.name == name), None)
    if supplied is not None and (fixed is None or supplied != fixed):
        raise Unsupported(f"{name}: the supplied {mass_symbol} cannot replace the engine's own flavour mass")
    coefficient = sympy.simplify(expr * v / mass_symbol)
    if any(str(s).startswith("m_") or s == v for s in coefficient.free_symbols):
        raise Unsupported("the simplified scalar class requires a linear g*m_f/v Yukawa")
    values = {sympy.Symbol(c.name): c.value for c in spec.couplings if c.value is not None}
    number = coefficient.subs(values)
    scale = values.get(v, V_HIGGS)
    if not number.is_number or not math.isfinite(scale) or scale <= 0:
        raise Unsupported(f"the Yukawa coupling {term.coupling} or its electroweak scale has no finite value")
    value = float(number) * V_HIGGS / scale
    if not math.isfinite(value):
        raise Unsupported(f"the coupling {term.coupling} is not finite")
    return value


def _current(spec: ModelSpec, term: ModelTerm, mediator: str, fermion: str) -> None:
    """The simplified engine represents one hermitian full-Dirac current."""
    field = spec.field(fermion)
    if (Counter(o.field for o in term.fields) != Counter({mediator: 1, fermion: 2})
            or sorted(o.conjugate for o in term.fields if o.field == fermion) != [False, True]
            or term.plus_hc or field.spin != 0.5 or field.self_conjugate or field.chirality):
        raise Unsupported("the simplified class needs one hermitian full-Dirac current per coupling; "
                          "chiral, flavour-changing and additional-h.c. structures need a separate map")


def _universal(spec: ModelSpec, terms: list[ModelTerm], mediator: str, family: str,
               yukawa: bool = False) -> float:
    """Do not turn a named flavour into a coupling to its entire SM family."""
    generic = "q" if family == "quark" else "l"
    full = {"u", "d", "s", "c", "b", "t"} if family == "quark" else {"e", "mu", "tau"}
    names, values = [], []
    for term in terms:
        fields = {o.field for o in term.fields if sector(spec.field(o.field)) == family}
        if len(fields) != 1:
            raise Unsupported(f"the simplified class cannot map this {family} flavour structure")
        name = fields.pop()
        _current(spec, term, mediator, name)
        fixed_mass = next((f.mass_gev for f in spin1.FERMIONS if f.name == name), None)
        supplied_mass = spec.field(name).mass_gev
        if name == generic and supplied_mass is not None:
            raise Unsupported(f"a generic {family} multiplet cannot have one supplied mass; "
                              "the simplified class uses the individual SM flavour masses")
        if supplied_mass is not None and fixed_mass is not None and supplied_mass != fixed_mass:
            raise Unsupported(f"the simplified class fixes {name}'s mass to {fixed_mass:g} GeV; "
                              f"the supplied mass {supplied_mass:g} needs a separate map")
        names.append(name)
        values.append(_yukawa_value(spec, term, name, family) if yukawa else _value(spec, term))
    if len(names) != len(set(names)) or set(names) not in ({generic}, full):
        raise Unsupported(f"the simplified class needs a universal {family} coupling; "
                          f"explicit flavours {sorted(names)} cannot be replaced by all flavours")
    if set(names) == full and any(spec.field(n).generations != 1 for n in names):
        raise Unsupported(f"named {family} flavours cannot also stand for generation multiplets")
    if any(v != values[0] for v in values[1:]):
        raise Unsupported(f"the simplified class needs one universal {family} coupling; the supplied values differ")
    return values[0]


def _sectors(spec: ModelSpec, term) -> set[str]:
    return {sector(spec.field(o.field)) for o in term.fields} - {None}


def classify(spec: ModelSpec, generic_route: bool = True) -> tuple[Spin1Class | ScalarClass | Portal, Point, list[str]]:
    """(class, parameter point, notes): a DM13 class, or else a portal of the library, or else the generic route (G4:
    the model computed from its own Feynman rules; ``generic_route=False`` refuses instead). Raises Unsupported.

    The generic route is on by default since the owner's decision of 2026-10-15 (before G12): its direct detection,
    annihilation today and LHC searches (G5, G6, G9) are built, so a model the library's maps refuse is computed from
    its own Lagrangian, with each search's verdict or its reason.

    A standard-library model no general map computes with its entry's engine is read with that engine first
    (``standard_binding``, OB-11), when it is the entry's own typed model."""
    from adroit.parameter_space import standard_binding
    bound = standard_binding.bind(spec)
    if bound is not None:
        return bound
    if spec.vector_currents is not None:
        from adroit.model_building.vector_contract import match
        return match(spec)
    if spec.scalar_potential is not None:
        from adroit.parameter_space.portals.scalar_potential import match
        return match(spec)
    try:
        found = portal(spec)
        mapped = found if found is not None else _simplified(spec)
    except Unsupported as refusal:
        if spec.chemical_equilibrium is not None or not generic_route:
            raise
        mapped = generic(spec, refusal)
    if spec.chemical_equilibrium is not None:
        from adroit.parameter_space.portals.tchannel import TChannel
        if not isinstance(mapped[0],TChannel):
            raise Unsupported("chemical_equilibrium request requires a supported t-channel mapping")
    return mapped


def generic(spec: ModelSpec, refusal: Unsupported) -> tuple[Portal, Point, list[str]]:
    """The generic route for a model the library's maps refuse (``refusal``), if its spectrum and Feynman rules can be
    built; else the library's refusal, with the generic route's reason."""
    from adroit.parameter_space.portals.generic import GenericModel
    try:
        engine = GenericModel.for_spec(spec)
        point = engine.point()
        engine.at(point)
    except (ValueError, KeyError) as error:
        raise Unsupported(f"{refusal}; the generic route cannot build it either: {error}") from None
    return engine, point, [f"the generic route (G4), since the library's maps refuse it: {refusal}"]


def portal(spec: ModelSpec) -> tuple[Portal, Point, list[str]] | None:
    """Match supported portal interactions and map their full Lagrangian coefficients.

    Ambiguous flavour, extra interactions and an unspecified scalar mass-basis
    transformation raise Unsupported rather than selecting a benchmark model.
    """
    from adroit.parameter_space.portal_matching import match_portal
    return match_portal(spec)


def coupling_relations(spec: ModelSpec) -> list[CouplingRelation]:
    """The couplings the typed model ties by a shared symbol (audit M9), for the simplified classes' currents,
    whose slots are g_χ, g_q and g_ℓ: g Z′ (χ̄γχ + q̄γq) gives g_q = g_χ. Other mappings tie no scan slots.
    Raises Unsupported for a sharing that a linear relation cannot keep (g and g², say). A standard entry read with
    its own engine ties what its benchmark declares (``standard_binding.relations``)."""
    from adroit.parameter_space import standard_binding
    bound = standard_binding.relations(spec)
    if bound is not None:
        return bound
    if spec.vector_currents is not None or spec.scalar_potential is not None:
        return []
    try:
        if portal(spec) is not None:
            return []
        _, _, dm_term, quark_terms, lepton_terms, _ = _simplified_inputs(spec)
    except Unsupported:
        return []
    terms = {"g_chi": dm_term, "g_q": quark_terms[0]} | ({"g_l": lepton_terms[0]} if lepton_terms else {})
    try:
        return relations.detect({slot: _bare(term.coupling) for slot, term in terms.items()})
    except ValueError as error:
        raise Unsupported(str(error)) from None


def flavour_tie(spec: ModelSpec) -> set[str]:
    """Symbols a flavour-vector contract's dark current shares with its flavour currents (mini audit, M9): that
    class fixes the flavour couplings, so scanning g_χ would break the tie."""
    if spec.vector_currents is None:
        return set()
    dm = spec.dark_matter
    dark = [t for t in spec.terms if Counter(o.field for o in t.fields).get(dm.name, 0) == 2]
    others = [t for t in spec.terms if t not in dark and _sectors(spec, t) & (QUARKS | LEPTONS)]
    symbols = lambda terms: {str(s) for t in terms for s in _bare(t.coupling).free_symbols}  # noqa: E731
    return symbols(dark) & symbols(others)


def _bare(coupling: str) -> sympy.Expr:
    """A coupling without its masses and electroweak scale: g·m_q/v → g."""
    from adroit.core.arithmetic import check_formula
    expr = sympy.sympify(check_formula(coupling))               # never text SymPy would run as Python
    return expr.subs({s: 1 for s in expr.free_symbols if str(s).startswith("m_") or str(s) == "v"})


def _dark_matter_refusal(spec: ModelSpec) -> str:
    """Why no computed map takes this dark matter, naming the maps that exist for its spin (the s-channel
    simplified classes are for Dirac fermions only)."""
    dm = spec.dark_matter
    others = [f"{f.name} (spin {f.spin:g}, {f.role.value})" for f in spec.fields
              if f.role not in (FieldRole.dark_matter, FieldRole.standard_model)]
    if dm.spin == 0:
        kind = "real" if dm.self_conjugate else "complex"
        return (f"no computed map takes this {kind} scalar dark matter: scalar dark matter is computed as a real "
                "singlet whose only new interaction is the Higgs portal, or as a complex singlet coupled to a "
                "kinetically mixed dark photon; " + (f"this model adds {', '.join(others)}" if others else
                                                     "this model is neither"))
    if dm.spin == 0.5:
        return ("Majorana dark matter is computed only with a coloured or charged scalar partner (the t-channel "
                "map); the s-channel simplified classes need Dirac dark matter")
    return f"spin-{dm.spin:g} dark matter is not computed: the maps cover spin-0 and spin-½ dark matter"


def _simplified_inputs(spec: ModelSpec) -> tuple[ModelField, Point, ModelTerm, list[ModelTerm], list[ModelTerm], list[str]]:
    """Validate fields, masses and the set of represented simplified currents."""
    dm = spec.dark_matter
    if dm.spin != 0.5 or dm.self_conjugate:
        raise Unsupported(_dark_matter_refusal(spec))
    if (dm.charges.su3 != "1" or dm.charges.su2 != 1
            or dm.charges.hypercharge or dm.charges.electric_charge):
        raise Unsupported("the simplified class requires SM-singlet dark matter; extra gauge interactions are not computed")
    mediators = [f for f in spec.fields if f.role is FieldRole.mediator]
    if len(mediators) != 1 or mediators[0].spin not in (0, 1):
        raise Unsupported("the scan computes one scalar or vector mediator; this model has "
                          f"{len(mediators)} mediator(s)")
    med = mediators[0]
    if (not med.self_conjugate or med.charges.su3 != "1" or med.charges.su2 != 1
            or med.charges.hypercharge or med.charges.electric_charge or any(med.charges.extra.values())):
        raise Unsupported("the simplified class requires one real, neutral SM-singlet mediator")
    terms = [t for t in spec.terms if med.name in {o.field for o in t.fields}]
    dm_terms = [t for t in terms if dm.name in {o.field for o in t.fields}]
    quark_terms = [t for t in terms if _sectors(spec, t) & QUARKS]
    lepton_terms = [t for t in terms if _sectors(spec, t) & LEPTONS]
    if len(dm_terms) != 1 or not quark_terms:
        raise Unsupported("the scan needs one coupling of the mediator to the dark matter and one to the quarks")
    notes = []
    for field in (dm, med):
        if field.mass_gev is not None and (not math.isfinite(field.mass_gev) or field.mass_gev <= 0):
            raise Unsupported(f"{field.name}: the supplied mass must be positive and finite")
    m_chi = 100.0 if dm.mass_gev is None else dm.mass_gev
    m_med = 1000.0 if med.mass_gev is None else med.mass_gev
    # an unstated mass is an explicit assumption until a scan axis or a mass ratio replaces it (release audit minor)
    notes += [f"assumed {slot} = {value:g} GeV: {field.name}'s mass was not stated (a scan axis or mass ratio "
              "replaces it)" for slot, value, field in (("m_chi", m_chi, dm), ("m_med", m_med, med))
              if field.mass_gev is None]
    _current(spec, dm_terms[0], med.name, dm.name)
    represented = [*dm_terms, *quark_terms, *lepton_terms]
    for term in spec.terms:
        if (term in represented or all(spec.field(o.field).role is FieldRole.standard_model for o in term.fields)
                or coupling_value(spec, term) == 0):
            continue
        raise Unsupported(f"additional interaction {term.text or term.coupling!r} is not represented by the simplified class")
    point = Point(m_chi=m_chi, m_med=m_med, g_chi=_value(spec, dm_terms[0]))
    return med, point, dm_terms[0], quark_terms, lepton_terms, notes


def _simplified(spec: ModelSpec) -> tuple[Spin1Class | ScalarClass, Point, list[str]]:
    """Map supported universal currents without discarding supplied structure."""
    med, base, dm_term, quark_terms, lepton_terms, notes = _simplified_inputs(spec)
    if med.spin == 1:
        labels = {t.lorentz for t in [dm_term, *quark_terms, *lepton_terms]}
        if labels not in ({"vector"}, {"axial"}):
            raise Unsupported(f"the scan computes pure vector or pure axial couplings; this model has {sorted(labels)}")
        g_q = _universal(spec, quark_terms, med.name, "quark")
        g_l = _universal(spec, lepton_terms, med.name, "lepton") if lepton_terms else 0.0
        if lepton_terms and any(o.field != "l" and sector(spec.field(o.field)) == "lepton"
                               for t in lepton_terms for o in t.fields):
            raise Unsupported("the spin-1 class fixes the left-handed neutrino completion; "
                              "explicit charged-lepton-only currents do not specify that completion")
        if lepton_terms:
            notes.append("generic l denotes the universal charged-lepton benchmark and its tied left-handed neutrino completion")
        kind = spin1.Spin1Kind.vector if labels == {"vector"} else spin1.Spin1Kind.axial
        point = base.model_copy(update={"g_q": g_q, "g_l": g_l})
        return Spin1Class(kind=kind, name=spec.name), point, notes
    dm_label, q_label = dm_term.lorentz, quark_terms[0].lorentz
    if (dm_label not in ("scalar", "pseudoscalar") or q_label not in ("scalar", "pseudoscalar")
            or any(t.lorentz != q_label for t in [*quark_terms, *lepton_terms])):
        raise Unsupported(f"a scalar mediator's couplings must be scalar or pseudoscalar; here {dm_label}, {q_label}")
    if any("m_" not in t.coupling for t in [*quark_terms, *lepton_terms]):
        raise Unsupported("the scan computes a scalar mediator coupling to quarks in proportion to their masses "
                          "(g·m_q/v); this model's quark coupling is universal")
    point = base.model_copy(update={
        "g_q": _universal(spec, quark_terms, med.name, "quark", yukawa=True),
        "g_l": _universal(spec, lepton_terms, med.name, "lepton", yukawa=True) if lepton_terms else 0.0})
    return (ScalarClass(dm_pseudoscalar=dm_label == "pseudoscalar", sm_pseudoscalar=q_label == "pseudoscalar",
                        name=spec.name, yukawa=spec.yukawa), point, notes)        # the model's declared inputs (#2)
