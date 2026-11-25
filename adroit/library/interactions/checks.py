"""The validity conditions of a card, checked for a particular use (DM4).

Each failed condition comes back as a flag in words, so that a result built
on the card carries it (build plan, DM6: "operator validity" is a flag).
"""

from __future__ import annotations

import math

from adroit.core.dm_state import DarkMatterParticle
from adroit.library.interactions.schema import InteractionCard, Parameter, ValidityKind

CONTACT_MARGIN = 10.0     # a contact operator needs its mediator 10 times heavier than q


def _couplings(card: InteractionCard, values: dict[str, float]) -> list[tuple[Parameter, float]]:
    """The card's free dimensionless couplings, at the values used."""
    full = {**card.defaults(), **values}
    return [(p, full[p.name]) for p in card.parameters
            if p.unit == "1" and p.prior.value != "fixed"]


def flags(card: InteractionCard, particle: DarkMatterParticle, q_max_gev: float,
          values: dict[str, float] | None = None, mediator_mass_gev: float | None = None,
          majorana: bool = False) -> list[str]:
    """The card's conditions that this use breaks, in words ([] if none).

    Args:
        card: the interaction.
        particle: the dark matter particle (spin and splitting).
        q_max_gev: the largest momentum transfer of the search.
        values: the card's parameter values, where not the defaults.
        mediator_mass_gev: for a contact card, the mass of the mediator behind it, if known.
        majorana: whether the dark matter is its own antiparticle.
    """
    values = values or {}
    out = []
    for condition in card.validity:
        kind = condition.kind
        if kind is ValidityKind.contact and mediator_mass_gev is not None \
                and mediator_mass_gev < CONTACT_MARGIN * q_max_gev:
            out.append(f"{card.id}: a contact interaction, but the mediator "
                       f"({mediator_mass_gev:.3g} GeV) is not much heavier than q up to "
                       f"{q_max_gev:.3g} GeV; use a mediator card with its propagator")
        elif kind is ValidityKind.spin_half and particle.spin != 0.5:
            out.append(f"{card.id}: written for spin-1/2 dark matter, not spin {particle.spin}")
        elif kind is ValidityKind.dirac_only and majorana:
            out.append(f"{card.id}: vanishes for Majorana dark matter")
        elif kind is ValidityKind.inelastic_only and particle.mass_splitting_kev == 0.0:
            out.append(f"{card.id}: needs a mass splitting")
        elif kind is ValidityKind.perturbative:
            large = [p.name for p, v in _couplings(card, values) if abs(v) > 4.0 * math.pi]
            if large:
                out.append(f"{card.id}: couplings {', '.join(large)} exceed 4π")
    return out
