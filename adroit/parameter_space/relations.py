"""Coupling relations of a declared model: a coupling held in proportion to another along a scan (R5, audit M9).

A Lagrangian can give two couplings one symbol. g Z′_μ (χ̄γ^μχ + μ̄γ^μμ − τ̄γ^μτ) sets g_χ = g_q = g′ (L_μ − L_τ
with unit dark charge), and −g_BL Z′_μ (⅓ q̄γ^μq + ⅓ χ̄γ^μχ − ℓ̄γ^μℓ) sets g_χ = g_q/3. A scan that varies one
of them must move the other, or it leaves the model. Each relation reads ``derived = factor × source``. The scan
imposes it at every point, as ``mediator_ratio`` imposes m_med = ratio × m_χ. Geometrically, the scan's two
axes then parametrise a plane inside the surface the relations cut out of coupling space.
"""

from __future__ import annotations

import math
from typing import Literal

import sympy
from pydantic import model_validator

from adroit.core.state import StrictModel

COUPLINGS = ("g_chi", "g_q", "g_l")
Coupling = Literal["g_chi", "g_q", "g_l"]


class CouplingRelation(StrictModel):
    """derived = factor × source, at every point of a scan."""

    derived: Coupling
    source: Coupling
    factor: float

    @model_validator(mode="after")
    def _proper(self) -> CouplingRelation:
        if self.derived == self.source:
            raise ValueError("a coupling relation ties two different couplings")
        if not math.isfinite(self.factor) or self.factor == 0:
            raise ValueError("a coupling relation's factor must be finite and non-zero")
        return self

    def text(self, label=lambda k: k) -> str:
        """The relation as written in a report, e.g. "g_chi = 0.333333 × g_q"."""
        return f"{label(self.derived)} = {self.factor:.6g} × {label(self.source)}"


def check(relations: list[CouplingRelation], axes: tuple[str, str] = ()) -> None:
    """Raise ValueError unless each coupling is derived at most once, from a coupling that is not itself derived,
    and no derived coupling is a scan axis."""
    derived = [r.derived for r in relations]
    if len(derived) != len(set(derived)):
        raise ValueError("a coupling can be derived from only one other")
    if any(r.source in derived for r in relations):
        raise ValueError("a coupling relation cannot derive from a derived coupling; give each relation the "
                         "group's free coupling as its source")
    for r in relations:
        if r.derived in axes:
            raise ValueError(f"{r.derived} is tied to {r.source} ({r.text()}) and cannot be an independent scan axis")


def apply(point, relations: list[CouplingRelation]):
    """The point with every derived coupling set from its source."""
    if not relations:
        return point
    return point.model_copy(update={r.derived: r.factor * getattr(point, r.source) for r in relations})


def orient(relations: list[CouplingRelation], axes: tuple[str, str]) -> list[CouplingRelation]:
    """The same ties, rewritten so that a scanned coupling is the source of its group: scanning g_χ in a model
    with g_χ = g_q/3 gives g_q = 3 g_χ. Raises ValueError if both axes are in one group."""
    check(relations)
    groups: dict[str, dict[str, float]] = {}
    for r in relations:
        groups.setdefault(r.source, {r.source: 1.0})[r.derived] = r.factor
    out = []
    for root, members in groups.items():
        scanned = [m for m in members if m in axes]
        if len(scanned) > 1:
            raise ValueError(f"{' and '.join(scanned)} are tied by the model; only one of them can be a scan axis")
        free = scanned[0] if scanned else root
        out += [CouplingRelation(derived=m, source=free, factor=c / members[free])
                for m, c in members.items() if m != free]
    return out


def detect(expressions: dict[str, sympy.Expr]) -> list[CouplingRelation]:
    """The relations among couplings whose expressions are proportional to one shared symbol.

    ``expressions`` maps each coupling slot to its Lagrangian coefficient, with masses and the electroweak scale
    already removed. Two slots that share a symbol are related only if their ratio is a nonzero real number (g
    and 2g, or g·h and 2g·h); any other sharing (g and g², g and g·h) raises ValueError, since a linear relation
    cannot keep it.
    """
    out: list[CouplingRelation] = []
    slots = [s for s in COUPLINGS if s in expressions]
    for i, a in enumerate(slots):
        for b in slots[i + 1:]:
            shared = expressions[a].free_symbols & expressions[b].free_symbols
            if not shared:
                continue
            ratio = sympy.simplify(expressions[b] / expressions[a])
            if not (ratio.is_number and ratio.is_real and ratio != 0):
                raise ValueError(f"{a} = {expressions[a]} and {b} = {expressions[b]} share "
                                 f"{', '.join(sorted(map(str, shared)))} but are not proportional; "
                                 "the scan can hold only a linear relation")
            if b not in {r.derived for r in out}:
                source = next((r.source for r in out if r.derived == a), a)
                factor = float(ratio) * (next((r.factor for r in out if r.derived == a), 1.0))
                out.append(CouplingRelation(derived=b, source=source, factor=factor))
    return out
