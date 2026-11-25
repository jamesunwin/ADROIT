"""A standard-library model's typed form, read with its own engine (OB-11, 2026-11-24).

For most standard entries a general map (``classify``) already computes the typed benchmark with the entry's engine;
those are left to it. For the rest (``benchmarks.TypedBenchmark.bind``) no general map does: the fermion and vector
Higgs portals, the singlet mixing with the Higgs, the Z portals, the gauged B − L and L_μ − L_τ, the inert doublet,
the 2HDM+a and the Dirac 5-plet. Such a typed model is read here, when it is the entry's own: its name is the entry's
and its structure (fields, interactions, couplings' names and dimensions) is the entry's benchmark's exactly. Its
couplings' and masses' values may differ (that is the point of choosing one and editing its numbers); a model whose
Lagrangian was edited is not the entry's and goes to the general maps.

Each engine slot is a formula of the model's couplings and field masses (``slots``); a coupling the engine holds
(``held``) must keep its value, or the model is refused with the reason, never computed as if it had it. An entry
Explain a signal cannot compute (``unsupported``) is refused with what it would need."""

from __future__ import annotations

import math

from adroit.core.model_spec import FieldRole, ModelSpec
from adroit.parameter_space.relations import CouplingRelation


def _entry(spec: ModelSpec):
    from adroit.parameter_space import library
    entry = library.BY_ID.get(spec.name)
    return entry if entry is not None and entry.typed.bind else None


def structure(spec: ModelSpec) -> tuple:
    """What makes a typed model this model, its numbers aside: the phase, the fields (all but their masses), the
    interactions (all but their display text) and the couplings' names and dimensions."""
    fields = tuple(sorted((f.name, f.role.value, f.spin, f.self_conjugate, f.chirality, f.generations,
                           f.charges.su3, f.charges.su2, f.charges.hypercharge, f.charges.electric_charge,
                           tuple(sorted(f.charges.extra.items())), f.dark_parity) for f in spec.fields))
    terms = tuple(sorted((tuple((o.field, o.conjugate) for o in t.fields), t.lorentz, t.coupling.replace(" ", ""),
                          t.plus_hc, t.indices, repr(t.flavour)) for t in spec.terms))
    couplings = tuple(sorted((c.name, c.mass_dimension) for c in spec.couplings))
    contracts = (spec.vector_currents, spec.scalar_potential, spec.scalar_running, spec.chemical_equilibrium,
                 spec.physical_fit)
    return spec.phase.value, spec.yukawa, fields, terms, couplings, tuple(c is None for c in contracts)


def is_entry(spec: ModelSpec) -> bool:
    """Whether ``spec`` is its library entry's bound typed model (name and structure), whatever its numbers."""
    entry = _entry(spec)
    return entry is not None and structure(spec) == structure(entry.benchmark_spec())


def _value(spec: ModelSpec, formula: str) -> float:
    from adroit.library.interactions import derivation
    value = derivation.evaluate_expression(formula, derivation.symbol_table(spec))
    if not math.isfinite(value):
        raise ValueError(f"{formula} is not finite")
    return float(value)


def bind(spec: ModelSpec):
    """(the entry's engine, its point, notes) for a standard entry's own bound typed model; None for any other model.
    Raises ``classify.Unsupported`` for an entry Explain a signal cannot compute, a held coupling edited, or a value
    missing."""
    from adroit.parameter_space.classify import Unsupported
    if not is_entry(spec):
        return None
    entry = _entry(spec)
    typed = entry.typed
    if typed.unsupported:
        raise Unsupported(f"{entry.title}: {typed.unsupported}")
    values = {c.name: c.value for c in spec.couplings}
    missing = [n for n, v in values.items() if v is None or not math.isfinite(v)]
    if missing:
        raise Unsupported(f"{entry.title}: the coupling {', '.join(missing)} needs a finite value")
    for name, held in typed.held.items():
        if not math.isclose(values[name], held, rel_tol=1e-12, abs_tol=0):
            raise Unsupported(f"{entry.title}: its engine holds {name} = {held:g}; another value ({values[name]:g}) "
                              "is not computed by it")
    dm = spec.dark_matter
    mediators = [f for f in spec.fields if f.role is FieldRole.mediator]
    if dm.mass_gev is None or (mediators and mediators[0].mass_gev is None):
        raise Unsupported(f"{entry.title}: every new field needs its mass")
    update = {"m_chi": dm.mass_gev}
    if mediators:
        update["m_med"] = mediators[0].mass_gev
    try:
        update |= {slot: _value(spec, formula) for slot, formula in typed.slots.items()}
    except (ValueError, ArithmeticError, KeyError) as error:
        raise Unsupported(f"{entry.title}: its engine's parameters cannot be read: {error}") from None
    point = entry.point.model_copy(update=update)
    notes = [f"the standard library's {entry.id}, read with its own engine ({type(entry.model_class).__name__}): "
             + ", ".join(f"{slot} = {formula}" for slot, formula in typed.slots.items())]
    return entry.model_class.model_copy(deep=True), point, notes


def relations(spec: ModelSpec) -> list[CouplingRelation] | None:
    """The engine slots a bound model ties to its fitted coupling (``ties``: g_χ = n_χ g_BL follows g_BL, say);
    None for a model that is not a bound entry."""
    if not is_entry(spec):
        return None
    return [CouplingRelation(derived=d, source=s, factor=_value(spec, f)) for d, s, f in _entry(spec).typed.ties]


def free_coupling(engine) -> bool:
    """Whether the engine has a coupling Explain a signal can fit in its g_χ slot: the electroweak multiplets have only
    gauge interactions, so none (their g_χ slot is read by nothing)."""
    from adroit.parameter_space.portals.multiplet import ElectroweakMultiplet
    from adroit.parameter_space.portals.nplet import ElectroweakNplet
    return not isinstance(engine, (ElectroweakMultiplet, ElectroweakNplet))


def availability(entry) -> tuple[bool, str]:
    """(whether Explain a signal can run the entry's typed benchmark, why not): every entry is listed, with this."""
    from adroit.parameter_space.classify import Unsupported, classify
    spec = entry.benchmark_spec()
    try:
        classify(spec)
    except Unsupported as error:
        return False, str(error)
    return True, ""
