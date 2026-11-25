"""Load the interaction library, resolve a card to operator coefficients, and build its graph.

A card resolves down its layers to the coefficients the rate reads: a
mediator card to Lagrangian couplings d_j, each Lagrangian to operator
coefficients c_i (arXiv:1308.6288, Table 1). Along the way the powers of q
multiply and a mediator's propagator is carried to every coefficient
(``OperatorCoefficient``). Nothing in the chain is approximate beyond the
reductions themselves, which the cards' ``dropped`` lists record.
"""

from __future__ import annotations

import math
from collections import defaultdict
from functools import lru_cache
from importlib import resources

import networkx as nx
import yaml

from adroit.core.dm_state import (DarkMatterParticle, InteractionModel, ModelLayer,
                                      OperatorCoefficient)
from adroit.library.interactions.schema import Deformation, InteractionCard, Kinematics
from adroit.physics.conventions import OPERATOR_MASS_GEV

CARD_FILES = ("nonrelativistic.yaml", "lagrangians.yaml", "mediators.yaml")
NUCLEONS = ("p", "n")
BELOW = {ModelLayer.mediator: ModelLayer.relativistic,
         ModelLayer.relativistic: ModelLayer.nonrelativistic}
# (operator, q power, mediator mass) → [proton, neutron] coefficient, GeV units
Amplitude = dict[tuple[int, int, float | None], list[float]]


@lru_cache(maxsize=1)
def cards() -> dict[str, InteractionCard]:
    """Every card of the library, by id."""
    out: dict[str, InteractionCard] = {}
    folder = resources.files("adroit.library.interactions").joinpath("cards")
    for name in CARD_FILES:
        for entry in yaml.safe_load(folder.joinpath(name).read_text()):
            card = InteractionCard.model_validate(entry)
            if card.id in out:
                raise ValueError(f"card {card.id} is defined twice")
            out[card.id] = card
    return out


def card(card_id: str) -> InteractionCard:
    """One card, by id."""
    try:
        return cards()[card_id]
    except KeyError:
        raise KeyError(f"no card {card_id!r} in the library") from None


def _monomial(term_powers: dict[str, int], values: dict[str, float], m_chi: float) -> float:
    """Π m^a over the term's powers, from the particle's mass, m_N and the card's values."""
    known = {"m_chi": m_chi, "m_N": OPERATOR_MASS_GEV, **values}
    return math.prod(known[name] ** power for name, power in term_powers.items())


def _nucleon_value(names: list[str], values: dict[str, float], nucleon: str) -> float:
    """The product of the couplings, with {N} standing for the nucleon."""
    return math.prod(values[name.replace("{N}", nucleon)] for name in names)


def _expand(card_id: str, values: dict[str, float], m_chi: float) -> Amplitude:
    """The card as operator coefficients per unit of its own couplings (recursive)."""
    this = card(card_id)
    full = {**this.defaults(), **values}
    propagator = full[this.mediator_mass] if this.mediator_mass else None
    out: Amplitude = defaultdict(lambda: [0.0, 0.0])
    for term in this.terms:
        size = term.factor * _monomial(term.powers, full, m_chi)
        per_nucleon = [size * _nucleon_value(term.couplings, full, n) for n in NUCLEONS]
        if term.target.startswith("O"):
            key = (int(term.target[1:]), term.q_power, propagator)
            out[key] = [a + b for a, b in zip(out[key], per_nucleon)]
            continue
        # a Lagrangian: its own couplings d_p, d_n are what this term supplies
        below = card(term.target)
        for n_index, nucleon in enumerate(NUCLEONS):
            unit = {"d_p": 1.0 if nucleon == "p" else 0.0, "d_n": 1.0 if nucleon == "n" else 0.0,
                    "m_M": full.get("m_M", below.parameter("m_M").default)}
            for (op, q_power, _), coeff in _expand(below.id, unit, m_chi).items():
                key = (op, q_power + term.q_power, propagator)
                out[key][n_index] += per_nucleon[n_index] * coeff[n_index]
    return dict(out)


def resolve(card_id: str, particle: DarkMatterParticle, values: dict[str, float] | None = None,
            name: str = "") -> InteractionModel:
    """The card, with parameter ``values`` (defaults elsewhere), as an interaction for the rate.

    The coefficients are in GeV units with q in GeV: ``q_scale_gev`` is 1.
    """
    this = card(card_id)
    unknown = set(values or {}) - {p.name for p in this.parameters}
    if unknown:
        raise KeyError(f"{card_id} has no parameters {sorted(unknown)}")
    amplitude = _expand(card_id, dict(values or {}), particle.mass_gev)
    coefficients = [OperatorCoefficient(operator=op, proton=p, neutron=n, q_power=q_power,
                                        mediator_mass_gev=mass)
                    for (op, q_power, mass), (p, n) in sorted(amplitude.items(),
                                                             key=lambda kv: (kv[0][0], kv[0][1]))
                    if p != 0.0 or n != 0.0]
    return InteractionModel(name=name or this.name, layer=this.layer, card_id=card_id,
                            coefficients=coefficients, parameters={**this.defaults(), **(values or {})},
                            dropped=list(this.dropped), references=list(this.references))


def isospin_values(card_id: str, isospin: str, strength: float) -> dict[str, float]:
    """The couplings of a layer-1 or layer-2 card in isoscalar ("s") or isovector ("v") form.

    In the isospin basis of arXiv:1308.6288, c^0 = (c^p + c^n)/2 and
    c^1 = (c^p − c^n)/2; LZ's unit models are c^s = 1/m_v² (so c^p = c^n) and
    c^v = 1/m_v² (so c^p = −c^n).
    """
    this = card(card_id)
    if not this.isospin_variants:
        raise ValueError(f"{card_id} has no isospin variants")
    prefix = "c" if this.layer is ModelLayer.nonrelativistic else "d"
    sign = {"s": 1.0, "v": -1.0}[isospin]
    return {f"{prefix}_p": strength, f"{prefix}_n": sign * strength}


def graph() -> nx.MultiDiGraph:
    """The neighbour graph: a node per card, an edge per physical deformation.

    Edges from the maps between layers (integrate out the mediator; take the
    nonrelativistic limit), the cards' declared neighbours, and the
    deformations within a card: a change of isospin, a mass splitting, a
    light mediator (self-loops).
    """
    g = nx.MultiDiGraph()
    for c in cards().values():
        g.add_node(c.id, layer=c.layer.value, name=c.name)
    for c in cards().values():
        down = (Deformation.integrate_out_mediator if c.layer is ModelLayer.mediator
                else Deformation.nonrelativistic_limit)
        for target in sorted({t.target for t in c.terms} - {c.id}):
            g.add_edge(c.id, target, deformation=down.value)
        for link in c.neighbours:
            g.add_edge(c.id, link.target, deformation=link.deformation.value)
        if c.isospin_variants:
            g.add_edge(c.id, c.id, deformation=Deformation.change_isospin.value)
        if Kinematics.inelastic in c.kinematics:
            g.add_edge(c.id, c.id, deformation=Deformation.add_mass_splitting.value)
        if c.mediator_mass and c.parameter(c.mediator_mass).prior.value != "fixed":
            g.add_edge(c.id, c.id, deformation=Deformation.make_mediator_light.value)
    return g


def check_library() -> list[str]:
    """Problems with the cards' cross-references ([] if none)."""
    problems = []
    for c in cards().values():
        allowed = {BELOW.get(c.layer)}
        if c.layer is ModelLayer.mediator:
            # a correction beyond Table 1's leading-order reductions may target O_i directly
            allowed.add(ModelLayer.nonrelativistic)
        for t in c.terms:
            target = cards().get(t.target)
            if target is None:
                problems.append(f"{c.id}: term target {t.target} is not a card")
            elif target.id != c.id and target.layer not in allowed:
                problems.append(f"{c.id}: {t.target} is not in the layer below")
        for link in c.neighbours:
            if link.target not in cards():
                problems.append(f"{c.id}: neighbour {link.target} is not a card")
        if c.mediator_mass and c.mediator_mass not in {p.name for p in c.parameters}:
            problems.append(f"{c.id}: mediator mass {c.mediator_mass} is not a parameter")
    return problems
