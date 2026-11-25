"""The most general Lagrangian as a typed model (DM12): operators → ``ModelSpec`` terms.

The generator works with left-handed spinors; DM8's pipeline reads Dirac
notation. The translation, term by term:
- a scalar block φ or φ* is the field φ, conjugated or not; a spinor ψ is ψ,
  and ψᶜ (or a right-handed field's conjugate) is ψ̄;
- a complex coupling y of φ ψψᶜ + h.c. is two real couplings, y_s φ ψ̄ψ and
  y_p φ ψ̄iγ⁵ψ (scalar and pseudoscalar);
- the two chiral currents of a Dirac field, V ψ†σ̄ψ and V ψᶜ†σ̄ψᶜ, are its vector
  and axial currents;
- other spinor pairs keep the label "chiral".

Masses of single fields stay with the fields; a tadpole is noted (it is removed
by shifting the field). Every coupling is symbolic, named after its
structure and fields, with its mass dimension 4 − d. Flavour structures of
Standard Model fermions are taken universal, which is stated as an assumption.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import NamedTuple

from adroit.core.model_spec import (Charges, FieldRole, ModelCoupling, ModelField, ModelSpec, ModelTerm,
                                   Occurrence, Phase)
from adroit.model_building.lagrangian import Operator

PREFIX = {"potential": "lam", "mass": "m2", "yukawa": "y", "vector_current": "g", "scalar_current": "g",
          "vector_scalar": "lam", "kinetic_mixing": "eps", "eft": "c"}


def _occurrence(block: str, field: str) -> Occurrence:
    """φ* and ψᶜ are conjugated; (ψᶜ)† is not."""
    starred = block.endswith("*")
    base = block[:-1] if starred else block
    return Occurrence(field=field, conjugate=starred != base.endswith("^c"))


def _dirac_currents(operators: list[Operator]) -> tuple[list[tuple[str, str]], set[int]]:
    """(vector, field) pairs whose two chiral currents are both allowed, and those operators' indices."""
    chiral: dict[tuple[str, str], list[int]] = {}
    for i, op in enumerate(operators):
        if op.structure == "vector_current" and len(set(op.fields[1:])) == 1:
            bases = {b.rstrip("*") for b in op.blocks[1:]}
            if len(bases) == 1:
                chiral.setdefault((op.fields[0], op.fields[1]), []).append(i)
    pairs = [k for k, idx in chiral.items() if len(idx) == 2]
    return pairs, {i for k in pairs for i in chiral[k]}


def _name(op: Operator, index: int, used: Counter) -> str:
    base = PREFIX.get(op.structure, "c")
    if op.structure == "potential" and len(op.blocks) == 3:
        base = "mu"
    stem = f"{base}_{'_'.join(dict.fromkeys(op.fields))}"
    used[stem] += 1
    return stem if used[stem] == 1 and op.count == 1 else f"{stem}_{used[stem]}"


def _terms(op: Operator, used: Counter) -> tuple[list[ModelTerm], list[ModelCoupling]]:
    """A ModelSpec term (or two, for a Dirac Yukawa) and its couplings."""
    dimension = int(round(4 - op.dimension))
    occurrences = [_occurrence(b, f) for b, f in zip(op.blocks, op.fields)]
    dirac_pair = (op.structure == "yukawa" and len(set(op.fields[:2])) == 1
                  and {b.endswith("^c") for b in op.blocks[:2]} == {False, True})
    if dirac_pair:
        out_t, out_c = [], []
        stem = _name(op, 0, used)
        for label in ("scalar", "pseudoscalar"):
            name = stem + ("_s" if label == "scalar" else "_p")
            out_t.append(ModelTerm(fields=occurrences, lorentz=label, coupling=name, text=f"{op.text} ({label})"))
            out_c.append(ModelCoupling(name=name, mass_dimension=dimension,
                                       justification="generated: one real part of the complex Yukawa coupling"))
        return out_t, out_c
    name = _name(op, 0, used)
    term = ModelTerm(fields=occurrences, lorentz=op.lorentz, coupling=name, plus_hc=not op.hermitian, text=op.text)
    return [term], [ModelCoupling(name=name, mass_dimension=dimension,
                                  justification=f"generated: {op.count} independent coupling(s) of this structure")]


SM_FIELDS: dict[str, ModelField] = {
    "Q": ModelField(name="Q", role=FieldRole.standard_model, spin=0.5, chirality="L", generations=3,
                    charges=Charges(su3="3", su2=2, hypercharge=1 / 6)),
    "uR": ModelField(name="uR", role=FieldRole.standard_model, spin=0.5, chirality="R", generations=3,
                     charges=Charges(su3="3", hypercharge=2 / 3)),
    "dR": ModelField(name="dR", role=FieldRole.standard_model, spin=0.5, chirality="R", generations=3,
                     charges=Charges(su3="3", hypercharge=-1 / 3)),
    "L": ModelField(name="L", role=FieldRole.standard_model, spin=0.5, chirality="L", generations=3,
                    charges=Charges(su2=2, hypercharge=-1 / 2)),
    "eR": ModelField(name="eR", role=FieldRole.standard_model, spin=0.5, chirality="R", generations=3,
                     charges=Charges(hypercharge=-1.0)),
    "H": ModelField(name="H", role=FieldRole.standard_model, spin=0, charges=Charges(su2=2, hypercharge=1 / 2)),
    "B": ModelField(name="B", role=FieldRole.standard_model, spin=1, self_conjugate=True),
}


GENERATIONS = {"e": 1, "mu": 2, "tau": 3, "u": 1, "c": 2, "t": 3, "d": 1, "s": 2, "b": 3}


class Identity(NamedTuple):
    """How a model's own ``standard_model`` fields are read by the generator."""

    own: dict[str, str]          # generator name → the model's name, where one model field has its quantum numbers
    shared: dict[str, str]       # the model's name → generator name, where several do (mu and tau: both eR)
    notes: list[str]


def _quantum_numbers(field: ModelField) -> tuple:
    from adroit.model_building.content import snap
    c = field.charges
    return (field.spin, field.self_conjugate, field.chirality, c.su3, c.su2, snap(c.hypercharge),
            tuple(sorted((k, snap(v)) for k, v in c.extra.items() if v)))


def generation(name: str) -> int | None:
    """The generation a field's name states (mu, muR, tau_R, bR → 2, 3, 3), or None."""
    stem = name.removesuffix("_R").removesuffix("_L")
    stem = stem[:-1] if len(stem) > 1 and stem[-1] in "RL" else stem
    return GENERATIONS.get(stem)


def sm_identity(spec: ModelSpec) -> Identity:
    """Each ``standard_model`` field the model writes under its own name, matched by its quantum numbers (spin,
    chirality, SU(3), SU(2), Y) to a generator field: a right-handed muon ``mu``, spin ½ in (1, 1, −1), is the
    generator's ``eR`` in generation 2 (live check L2)."""
    found: dict[str, list[ModelField]] = {}
    for f in spec.fields:
        if f.role is FieldRole.standard_model and f.name not in SM_FIELDS:
            match = next((n for n, g in SM_FIELDS.items() if _quantum_numbers(g) == _quantum_numbers(f)), None)
            if match:
                found.setdefault(match, []).append(f)
    own = {n: fs[0].name for n, fs in found.items() if len(fs) == 1}
    shared = {f.name: n for n, fs in found.items() if len(fs) > 1 for f in fs}
    notes = []
    for n, fs in found.items():
        for f in fs:
            g = generation(f.name)
            which = (f"generation {g} of 3" if g else
                     "one generation" if f.generations == 1 else f"{f.generations} generations")
            notes.append(f"{f.name} has the quantum numbers of the Standard Model's {n} and is read as {n}, {which}"
                         + ("; the general Lagrangian keeps this flavour, and couplings to the other generations "
                            "are a flavour choice, not missing terms" if len(fs) == 1 else
                            f"; with {', '.join(x.name for x in fs if x is not f)} it shares {n}'s terms, whose "
                            "flavour structure the generator takes universal"))
    return Identity(own=own, shared=shared, notes=notes)


def _own_names(term: ModelTerm, own: dict[str, str]) -> ModelTerm:
    """A generated term with the model's names for its Standard Model fields, in its fields and its text."""
    if not any(o.field in own for o in term.fields):
        return term
    text = term.text
    for generator, name in own.items():
        text = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(generator)}(?![A-Za-z0-9_])", name, text)
    return term.model_copy(update={"text": text, "fields": [o.model_copy(update={"field": own.get(o.field, o.field)})
                                                            for o in term.fields]})


def with_standard_model(spec: ModelSpec, names: set[str]) -> list[ModelField]:
    """The model's fields plus the Standard Model fields its terms use (unbroken phase)."""
    have = {f.name for f in spec.fields}
    return list(spec.fields) + [SM_FIELDS[n] for n in sorted(names) if n in SM_FIELDS and n not in have]


def general_spec(base: ModelSpec, operators: list[Operator]) -> ModelSpec:
    """The base model's fields with every generated operator as a symbolic term."""
    used: Counter = Counter()
    terms, couplings, notes = [], [], []
    pairs, paired = _dirac_currents(operators)
    for vector, field in pairs:
        occurrences = [Occurrence(field=vector), Occurrence(field=field, conjugate=True), Occurrence(field=field)]
        for label in ("vector", "axial"):
            name = f"g_{vector}_{field}_{label[0]}"
            terms.append(ModelTerm(fields=occurrences, lorentz=label, coupling=name,
                                   text=f"{vector}_μ {field}̄ γ^μ{'γ⁵' if label == 'axial' else ''} {field}"))
            couplings.append(ModelCoupling(name=name, mass_dimension=0,
                                           justification="generated: the two chiral currents of a Dirac field"))
    for i, op in enumerate(operators):
        if i in paired:
            continue
        if len(op.fields) == 1:
            notes.append(f"{op.text}: a tadpole, removed by shifting the field" if op.structure == "potential"
                         else f"{op.text}: generated")
            continue
        if op.structure == "mass" and len(set(op.fields)) == 1:
            continue
        t, c = _terms(op, used)
        terms += t
        couplings += c
    assumptions = list(base.assumptions) + notes + [
        "generated by ADROIT's renormalizable-operator generator: every allowed term, couplings symbolic",
        "Standard Model flavour structures taken universal (one coupling per structure)"]
    identity = sm_identity(base)
    if identity.own:                                 # the model's own flavour keeps its name (mu, not eR)
        terms = [_own_names(t, identity.own) for t in terms]
        assumptions += [n for n in identity.notes if "keeps this flavour" in n]
    fields = with_standard_model(base, {o.field for t in terms for o in t.fields})
    data = base.model_dump()
    data.update(fields=[f.model_dump() for f in fields], terms=[t.model_dump() for t in terms],
                couplings=[c.model_dump() for c in couplings], assumptions=assumptions, phase=Phase.unbroken.value)
    return _contracted(ModelSpec.model_validate(data))


def _contracted(spec: ModelSpec) -> ModelSpec:
    """Each term whose gauge contraction is not unique, as one term per independent contraction with its indices
    stated (``indices.stated_contractions``): H H† H₂ H₂† has two, λ₃|H|²|H₂|² and λ₄|H†H₂|², and one coupling each.
    Before 2026-10-20 the generator wrote one term and left its indices unstated, so the second coupling was missing
    and G1 refused the term; a term these pairings do not span is still left for its indices to be stated."""
    from adroit.model_building import indices
    terms, couplings = [], {c.name: c for c in spec.couplings}
    for term in spec.terms:
        try:
            found = indices.default_contraction(spec, term)
            if found.numeric:                            # L-3: say which normalisation the coupling multiplies
                groups = " and ".join("SU(2)" if g == "su2" else "colour" for g in found.numeric)
                term = term.model_copy(update={"text": f"{term.text or term.coupling} (the unique {groups} "
                                                       "invariant, unit-normalised: Σ|C|² = 1)"})
            terms.append(term)
            continue
        except indices.IndexError_:
            stated = indices.stated_contractions(spec, term)
        if not stated:
            terms.append(term)
            continue
        for n, text in enumerate(stated, start=1):
            name = term.coupling if n == 1 else f"{term.coupling}_c{n}"
            terms.append(term.model_copy(update={"indices": text, "coupling": name,
                                                 "text": term.text if n == 1 else f"{term.text} (contraction {n})"}))
            if n > 1:
                couplings[name] = couplings[term.coupling].model_copy(update={
                    "name": name, "justification": f"generated: contraction {n} of {len(stated)} of this structure"})
    return spec.model_copy(update={"terms": terms, "couplings": list(couplings.values())})
