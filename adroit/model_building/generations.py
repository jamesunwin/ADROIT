"""Several generations of a new field (the owner's decision #5, 2026-10-20): a new field with N generations is N
fields before G1, ``F1 … FN``, each with the field's quantum numbers.

**Masses.** ``mass_gev`` for every generation, or ``masses_gev``, one per generation. The generations are mass
eigenstates: no mass mixing between them is written.

**Roles.** Of a dark-matter field's generations the lightest is the dark matter and the others its partners (role
"other"); a mediator's are each a mediator.

**Couplings.** A term with one occurrence of an N-generation field becomes N terms; with two (the same field twice, as
F̄γ^μF X, or two such fields), N × M. Each takes the term's coupling times its entry of the term's ``flavour``: a list
(one occurrence) or a matrix (two: rows the first occurrence's generation, columns the second's). Without one: 1 for
every generation (one occurrence), the identity (two: each generation's number conserved). A zero entry writes no
term. A term without "+ h.c." joining a field to its own conjugate (F̄ΓF X) needs a symmetric matrix M, real as every
entry is: Σ_ij M_ij F̄_iΓF_j X is then Σ_i M_ii F̄_iΓF_i X + Σ_{i<j} (M_ij F̄_iΓF_j X + h.c.), each off-diagonal pair
written once with "+ h.c." (G1's rule for a current between distinct fields). More than two occurrences of
multi-generation fields in one term are refused.

**What is then refused** (the generic route's domain: ``generic._components`` and ``_thermal_history``): a Z₂-odd
state that no interaction joins to the dark matter (a second stable component: flavour-conserving couplings conserve
each generation's number), one degenerate with it (it cannot decay), and one whose conversion to the dark matter is
not certified before its own freeze-out (an unresolved thermal history). Multi-component evolution is not computed.
"""
from __future__ import annotations

from itertools import product

from adroit.core.model_spec import FieldRole, ModelField, ModelSpec, ModelTerm, Occurrence


class GenerationError(ValueError):
    """A multi-generation field or term ADROIT cannot expand (module docstring)."""


def expand(spec: ModelSpec) -> ModelSpec:
    """The model with each new field of N > 1 generations written as N fields, and its terms expanded (module
    docstring). A model without one is returned unchanged."""
    many = {f.name: f.generations for f in spec.fields if f.role is not FieldRole.standard_model and f.generations > 1}
    for f in spec.fields:
        if f.masses_gev is not None and f.name not in many:
            raise GenerationError(f"{f.name}: masses_gev is for a new field of several generations")
    if not many:
        for term in spec.terms:
            _no_flavour(term)
        return spec
    names = {f.name for f in spec.fields}
    fields: list[ModelField] = []
    for f in spec.fields:
        fields += _copies(f, names) if f.name in many else [f]
    terms = [t for term in spec.terms for t in _terms(term, many)]
    return spec.model_copy(update={"fields": fields, "terms": terms})


def copy_names(field: ModelField) -> list[str]:
    """The names of a field's generations, ``F1 … FN``."""
    return [f"{field.name}{i + 1}" for i in range(field.generations)]


def _masses(field: ModelField) -> list[float | None]:
    if field.masses_gev is None:
        return [field.mass_gev] * field.generations
    if len(field.masses_gev) != field.generations:
        raise GenerationError(f"{field.name}: {len(field.masses_gev)} masses for {field.generations} generations")
    if field.mass_gev is not None:
        raise GenerationError(f"{field.name}: states its mass twice (mass_gev and masses_gev)")
    return list(field.masses_gev)


def _copies(field: ModelField, names: set[str]) -> list[ModelField]:
    copies = copy_names(field)
    if clash := sorted(set(copies) & names):
        raise GenerationError(f"{field.name}'s generations would be named {', '.join(clash)}, which the model uses")
    masses = _masses(field)
    lightest = min(range(len(masses)), key=lambda i: (masses[i] is None, masses[i] or 0.0, i))
    out = []
    for i, (name, mass) in enumerate(zip(copies, masses)):
        role = FieldRole.other if field.role is FieldRole.dark_matter and i != lightest else field.role
        out.append(field.model_copy(update={"name": name, "generations": 1, "mass_gev": mass, "masses_gev": None,
                                            "role": role}))
    return out


def _no_flavour(term: ModelTerm) -> None:
    if term.flavour is not None:
        raise GenerationError(f"{term.text or term.coupling}: a flavour structure on a term with no multi-generation "
                              "field")


def _terms(term: ModelTerm, many: dict[str, int]) -> list[ModelTerm]:
    slots = [k for k, o in enumerate(term.fields) if o.field in many]
    if not slots:
        _no_flavour(term)
        return [term]
    if len(slots) > 2:
        raise GenerationError(f"{term.text or term.coupling}: more than two occurrences of multi-generation fields")
    sizes = [many[term.fields[k].field] for k in slots]
    entries = _flavour(term, sizes, slots)
    hermitian = _self_conjugate_pair(term, slots)
    out = []
    for index in product(*(range(n) for n in sizes)):
        factor = entries[index]
        if factor == 0 or (hermitian and index[0] > index[1]):     # the lower triangle is the upper's h.c.
            continue
        occurrences = list(term.fields)
        for k, i in zip(slots, index):
            occurrences[k] = Occurrence(field=f"{term.fields[k].field}{i + 1}", conjugate=term.fields[k].conjugate)
        coupling = term.coupling if factor == 1 else f"({term.coupling})*{factor!r}"
        plus_hc = term.plus_hc or (hermitian and index[0] != index[1])
        out.append(term.model_copy(update={"fields": occurrences, "coupling": coupling, "flavour": None, "text": "",
                                           "plus_hc": plus_hc}))
    return out


def _self_conjugate_pair(term: ModelTerm, slots: list[int]) -> bool:
    """Whether the term joins a multi-generation field to its own conjugate without "+ h.c." (F̄ΓF X)."""
    if len(slots) != 2 or term.plus_hc:
        return False
    first, second = term.fields[slots[0]], term.fields[slots[1]]
    return first.field == second.field and first.conjugate != second.conjugate


def _flavour(term: ModelTerm, sizes: list[int], slots: list[int]) -> dict[tuple[int, ...], float]:
    """Each generation index's factor (module docstring)."""
    where = term.text or term.coupling
    if len(sizes) == 1:
        values = [1.0] * sizes[0] if term.flavour is None else term.flavour
        if len(values) != sizes[0] or any(isinstance(v, list) for v in values):
            raise GenerationError(f"{where}: its flavour is a list of {sizes[0]} numbers (one occurrence)")
        return {(i,): float(v) for i, v in enumerate(values)}
    n, m = sizes
    matrix = [[1.0 if i == j else 0.0 for j in range(m)] for i in range(n)] if term.flavour is None else term.flavour
    if len(matrix) != n or any(not isinstance(row, list) or len(row) != m for row in matrix):
        raise GenerationError(f"{where}: its flavour is a {n} × {m} matrix (two occurrences)")
    if _self_conjugate_pair(term, slots) and any(matrix[i][j] != matrix[j][i] for i in range(n) for j in range(i)):
        raise GenerationError(f"{where}: joins {term.fields[slots[0]].field} to its own conjugate without + h.c., so "
                              "its flavour matrix must be symmetric (the term Hermitian)")
    return {(i, j): float(matrix[i][j]) for i in range(n) for j in range(m)}
