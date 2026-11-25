"""The most general renormalizable Lagrangian of a field content (DM12).

Given the Standard Model and a model's new fields (``content``), every
gauge- and Lorentz-invariant operator of mass dimension ≤ 4 that the stated
charges and stabilising Z2 allow, each with its number of independent
couplings (flavour included). Kinetic terms and gauge couplings follow from
the representations and are not listed. The structures:

- **scalar potential**: monomials of degree 1–4 in the scalars and their
  conjugates (tadpoles, masses, cubic and quartic couplings);
- **fermion masses and Yukawa couplings**: ψ_a ψ_b and φ ψ_a ψ_b of
  left-handed spinors (+ h.c.). Two identical spinors contract antisymmetrically
  in their Lorentz indices, so their gauge and flavour part is symmetric;
- **a neutral massive vector V**: currents V_μ ψ_a† σ̄^μ ψ_b between spinors of
  identical representation, scalar currents V_μ φ* i∂↔^μ φ, and V_μ V^μ times
  scalar monomials of degree 0–2;
- **kinetic mixing** V_μν B^μν of any neutral vector, and among new vectors.

The gauge boson of a new U(1) couples through covariant derivatives; only its
kinetic mixing is listed. Operators made only of Standard Model fields are left
out unless asked for (``include_standard_model``), which reproduces the
Standard Model's own Yukawa couplings and potential.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations_with_replacement

from adroit.core.state import StrictModel
from adroit.model_building.content import Component
from adroit.model_building.groups import invariants

TOLERANCE = 1e-9


class Operator(StrictModel):
    """One allowed operator: its building blocks, structure, dimension and number of couplings."""

    blocks: list[str]              # component names, e.g. ["S", "S", "H", "H*"]
    fields: list[str]              # the model fields they come from, with repetition
    structure: str                 # potential, mass, yukawa, vector_current, scalar_current, vector_scalar,
                                   # kinetic_mixing, or eft
    lorentz: str                   # the ModelSpec label: scalar, chiral, vector, scalar_current, kinetic_mixing, ...
    dimension: float
    count: int                     # independent couplings (complex unless hermitian)
    hermitian: bool                # its own conjugate: real couplings, no "+ h.c."
    text: str


def _neutral(blocks: list[Component]) -> bool:
    totals: Counter = Counter()
    for b in blocks:
        for k, v in b.charges().items():
            totals[k] += v
    return all(abs(v) < TOLERANCE for v in totals.values())


def _even(blocks: list[Component]) -> bool:
    sign = 1
    for b in blocks:
        sign *= b.parity
    return sign == 1


def _count(blocks: list[Component], symmetric: bool = True) -> int:
    """Independent invariants: identical blocks enter as a symmetric power (or antisymmetric)."""
    groups = Counter(b.name for b in blocks)
    by_name = {b.name: b for b in blocks}
    return invariants([(by_name[n].rep(), k, symmetric) for n, k in groups.items()])


def _key(blocks: list[Component]) -> tuple[str, ...]:
    return tuple(sorted(b.name for b in blocks))


def _relevant(blocks: list[Component], include_sm: bool) -> bool:
    return include_sm or any(not b.standard_model for b in blocks)


def _operator(blocks: list[Component], structure: str, lorentz: str, dimension: float, count: int,
              hermitian: bool, text: str) -> Operator:
    return Operator(blocks=[b.name for b in blocks], fields=[b.field for b in blocks], structure=structure,
                    lorentz=lorentz, dimension=dimension, count=count, hermitian=hermitian, text=text)


def scalar_potential(comps: list[Component], include_sm: bool = False) -> list[Operator]:
    """Monomials of degree 1–4 in the scalars (and conjugates) that are invariant and even."""
    pool = []
    for c in comps:
        if c.kind == "scalar":
            pool += [c] if c.real else [c, c.conjugate()]
    out, seen = [], set()
    for degree in range(1, 5):
        for idx in combinations_with_replacement(range(len(pool)), degree):
            blocks = [pool[i] for i in idx]
            key = _key(blocks)
            conj_key = _key([b.conjugate() for b in blocks])
            if key in seen or conj_key in seen or not _relevant(blocks, include_sm):
                continue
            if not (_neutral(blocks) and _even(blocks)):
                continue
            n = _count(blocks)
            if n == 0:
                continue
            seen.add(key)
            hermitian = key == conj_key
            structure = "mass" if degree == 2 and hermitian else "potential"
            out.append(_operator(blocks, structure, "scalar", float(degree), n, hermitian, " ".join(key)))
    return out


def fermion_terms(comps: list[Component], include_sm: bool = False) -> list[Operator]:
    """ψ_a ψ_b (mass, d = 3) and φ ψ_a ψ_b (Yukawa, d = 4) of left-handed spinors, + h.c."""
    spinors = [c for c in comps if c.kind == "weyl"]
    scalars = [None]
    for c in comps:
        if c.kind == "scalar":
            scalars += [c] if c.real else [c, c.conjugate()]
    out = []
    for i, a in enumerate(spinors):
        for b in spinors[i:]:
            for s in scalars:
                blocks = [a, b] + ([s] if s is not None else [])
                if not _relevant(blocks, include_sm) or not (_neutral(blocks) and _even(blocks)):
                    continue
                n = _count(blocks)               # identical spinors: symmetric gauge × flavour part
                if n == 0:
                    continue
                structure, dim = ("mass", 3.0) if s is None else ("yukawa", 4.0)
                lorentz = "scalar" if a.field == b.field else "chiral"
                text = " ".join(x.name for x in blocks)
                out.append(_operator(blocks, structure, lorentz, dim, n, False, text))
    return out


def _same_rep(a: Component, b: Component) -> bool:
    return (a.su3, a.su2) == (b.su3, b.su2) and _neutral([a, b.conjugate()])


def _currents(v: Component, comps: list[Component], include_sm: bool) -> list[Operator]:
    """V_μ ψ_a† σ̄^μ ψ_b between spinors of one representation, and V_μ φ* i∂↔^μ φ."""
    spinors = [c for c in comps if c.kind == "weyl"]
    out = []
    for i, a in enumerate(spinors):
        for b in spinors[i:]:
            if _same_rep(a, b) and v.parity * a.parity * b.parity == 1 and _relevant([v, a, b], include_sm):
                out.append(_operator([v, a.conjugate(), b], "vector_current", "chiral", 4.0, a.flavours * b.flavours,
                                     a.name == b.name, f"{v.name}_μ {a.name}† σ̄^μ {b.name}"))
    for c in comps:
        if c.kind == "scalar" and not c.real and v.parity == 1:
            out.append(_operator([v, c.conjugate(), c], "scalar_current", "scalar_current", 4.0, 1, True,
                                 f"{v.name}_μ {c.name}* i∂↔^μ {c.name}"))
    return out


def vector_terms(comps: list[Component], include_sm: bool = False) -> list[Operator]:
    """Neutral vectors: kinetic mixing; for massive ones, currents and couplings V·W × scalars (d ≤ 4)."""
    vectors = [c for c in comps if c.kind == "vector"]
    monomials = [op for op in scalar_potential(comps, include_sm=True) if op.dimension <= 2]
    out = []
    for v in vectors:
        if v.parity == 1:
            out.append(Operator(blocks=[v.name, "B"], fields=[v.field, "B"], structure="kinetic_mixing",
                                lorentz="kinetic_mixing", dimension=4.0, count=1, hermitian=True,
                                text=f"{v.name}_μν B^μν"))
        if not v.gauge_of:
            out += _currents(v, comps, include_sm)
    for i, v in enumerate(vectors):
        for w in vectors[i:]:
            if v.parity * w.parity != 1:
                continue
            if v is not w:
                out.append(_operator([v, w], "kinetic_mixing", "kinetic_mixing", 4.0, 1, True,
                                     f"{v.name}_μν {w.name}^μν"))
            out.append(_operator([v, w], "mass", "scalar", 2.0, 1, True, f"{v.name}_μ {w.name}^μ"))
            if v.gauge_of or w.gauge_of:
                continue                      # a gauge boson's couplings to scalars come from D_μ
            for op in monomials:
                if _parity_of(op, comps) == 1:
                    out.append(Operator(blocks=[v.name, w.name] + op.blocks, fields=[v.field, w.field] + op.fields,
                                        structure="vector_scalar", lorentz="scalar", dimension=2.0 + op.dimension,
                                        count=op.count, hermitian=op.hermitian,
                                        text=f"{v.name}_μ {w.name}^μ ({op.text})"))
    return out


def _parity_of(op: Operator, comps: list[Component]) -> int:
    """The Z2 parity of an operator's blocks."""
    by_name = {c.name: c for c in comps}
    by_name.update({c.conjugate().name: c.conjugate() for c in comps if c.kind == "scalar"})
    sign = 1
    for name in op.blocks:
        sign *= by_name[name].parity
    return sign


def general_lagrangian(comps: list[Component], include_standard_model: bool = False) -> list[Operator]:
    """Every allowed operator of dimension ≤ 4: the potential, fermion masses and Yukawas, vector couplings."""
    return (scalar_potential(comps, include_standard_model) + fermion_terms(comps, include_standard_model)
            + vector_terms(comps, include_standard_model))
