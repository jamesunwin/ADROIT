"""Faithful mapping from declared flavour currents to the existing vector engine."""

from __future__ import annotations

from collections import Counter
import math

from adroit.core.model_spec import ModelSpec, ModelField, ModelTerm, FieldRole, Phase
from adroit.constraints import spin1
from adroit.core.model_contracts import VECTOR_FLAVOURS
from adroit.parameter_space.classes import Point
from adroit.parameter_space.flavour_vector import FlavourVectorClass


def match(spec: ModelSpec) -> tuple[FlavourVectorClass, Point, list[str]]:
    """Require supplied masses/currents, explicit zero flavours and represented interactions."""
    from adroit.parameter_space.classify import Unsupported, _current, _value

    contract = spec.vector_currents
    if contract is None or spec.phase is not Phase.broken:
        raise Unsupported(
            "flavour-vector contract requires the broken phase and explicit vector_currents"
        )
    dm, med = _dark_fields(spec)
    used = []
    dm_terms = [
        t
        for t in spec.terms
        if Counter(o.field for o in t.fields) == Counter({dm.name: 2, med.name: 1})
    ]
    if len(dm_terms) != 1 or dm_terms[0].lorentz != "vector":
        raise Unsupported("one explicitly specified vector dark current required")
    _current(spec, dm_terms[0], med.name, dm.name)
    used.append(dm_terms[0])
    couplings = {f: 0.0 for f in VECTOR_FLAVOURS}
    masses = {}
    notes = [
        "full coefficients C in L map to g=-C in L=-V_mu sum g_f fbar gamma^mu f; no neutrino completion"
    ]
    _flavours(spec, med, couplings, masses, used, notes)
    for term in spec.terms:
        if term in used or _value(spec, term) == 0:
            continue
        raise Unsupported(
            f"additional interaction {term.text or term.coupling!r} is not represented by the flavour-vector contract"
        )
    cls = FlavourVectorClass(
        name=spec.name,
        flavour_couplings=couplings,
        fermion_masses_gev=masses,
        field_flavours=contract.flavours,
    )
    return (
        cls,
        Point(
            m_chi=dm.mass_gev,
            m_med=med.mass_gev,
            g_chi=-_coefficient(spec, dm_terms[0]),
            g_q=0,
            g_l=0,
        ),
        notes,
    )


def _dark_fields(spec: ModelSpec) -> tuple[ModelField, ModelField]:
    from adroit.parameter_space.classify import Unsupported

    dark = [f for f in spec.fields if f.role is FieldRole.dark_matter]
    mediators = [f for f in spec.fields if f.role is FieldRole.mediator]
    if len(dark) != 1 or len(mediators) != 1:
        raise Unsupported("one Dirac DM field and one real neutral vector mediator required")
    dm, med = dark[0], mediators[0]
    if dm.generations != 1 or med.generations != 1:
        raise Unsupported("one generation of DM and mediator required")
    if (
        dm.spin != 0.5
        or dm.self_conjugate
        or dm.chirality
        or med.spin != 1
        or not med.self_conjugate
    ):
        raise Unsupported("contract requires full-Dirac DM and a self-conjugate spin-1 mediator")
    for field in (dm, med):
        c = field.charges
        if (
            c.su3 != "1"
            or c.su2 != 1
            or c.electric_charge
            or c.hypercharge
            or any(c.extra.values())
        ):
            raise Unsupported(
                "only SM-neutral singlet DM/mediator with no extra declared gauge charges represented"
            )
        if field.mass_gev is None or not math.isfinite(field.mass_gev) or field.mass_gev <= 0:
            raise Unsupported(f"{field.name}: explicit positive finite physical mass required")
    return dm, med


def _flavours(
    spec: ModelSpec,
    med: ModelField,
    couplings: dict[str, float],
    masses: dict[str, float],
    used: list[ModelTerm],
    notes: list[str],
) -> None:
    from adroit.parameter_space.classify import Unsupported, _current

    for flavour, field_name in spec.vector_currents.flavours.items():
        field = spec.field(field_name)
        _check_flavour(field, flavour)
        terms = [
            t
            for t in spec.terms
            if Counter(o.field for o in t.fields) == Counter({field_name: 2, med.name: 1})
        ]
        if len(terms) != 1 or terms[0].lorentz != "vector":
            raise Unsupported(
                f"{flavour}: one named full-Dirac vector coefficient required; missing is not zero"
            )
        _current(spec, terms[0], med.name, field_name)
        couplings[flavour] = -_coefficient(spec, terms[0])
        used.append(terms[0])
        if field.mass_gev is not None:
            if not math.isfinite(field.mass_gev) or field.mass_gev < 0:
                raise Unsupported(f"{flavour}: finite nonnegative supplied fermion mass required")
            masses[flavour] = field.mass_gev
        else:
            mass = next(f.mass_gev for f in spin1.FERMIONS if f.name == flavour)
            notes.append(
                f"{flavour} mass not supplied: declared engine pole convention {mass:g} GeV"
            )


def _check_flavour(field: ModelField, flavour: str) -> None:
    from adroit.parameter_space.classify import Unsupported

    quark = flavour in VECTOR_FLAVOURS[:6]
    charge = 2 / 3 if flavour in ("u", "c", "t") else -1 / 3 if quark else -1.0
    c = field.charges
    if (
        field.role is not FieldRole.standard_model
        or field.generations != 1
        or field.spin != 0.5
        or field.self_conjugate
        or field.chirality
        or c.su3 != ("3" if quark else "1")
        or c.su2 != 1
        or not math.isclose(c.electric_charge, charge, abs_tol=1e-12)
        or any(c.extra.values())
    ):
        raise Unsupported(
            f"{flavour}: field map requires one full-Dirac SM flavour with its broken-phase colour/electric charge"
        )


def _coefficient(spec: ModelSpec, term: ModelTerm) -> float:
    from adroit.library.interactions.derivation import evaluate_expression, symbol_table
    from adroit.parameter_space.classify import Unsupported, _value

    value = _value(spec, term)
    table = symbol_table(spec)
    if value == 0:
        table = {
            name: (1.0 if number == 0 else number, dimension)
            for name, (number, dimension) in table.items()
        }
        probe = evaluate_expression(term.coupling, table)
    else:
        probe = value
    scaled = evaluate_expression(term.coupling, table, scale=2)
    if not math.isclose(scaled, probe, rel_tol=1e-10, abs_tol=0):
        raise Unsupported("full vector-current coefficients must be dimensionless")
    return value
