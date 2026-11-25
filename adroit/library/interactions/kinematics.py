"""The kinematic modifiers of a card: elastic, inelastic and exothermic scattering (DM4).

A modifier sets the dark matter's mass splitting δ = m_χ* − m_χ: zero for
elastic scattering, positive when the dark matter is excited in the
collision (inelastic), negative when it de-excites (exothermic). The rate
takes it through v_min (``physics.rates``); the card says which modifiers its
physics allows.
"""

from __future__ import annotations

from adroit.core.dm_state import DarkMatterParticle
from adroit.library.interactions.schema import InteractionCard, Kinematics


def apply(card: InteractionCard, particle: DarkMatterParticle, kinematics: Kinematics,
          splitting_kev: float = 0.0) -> DarkMatterParticle:
    """The particle with the splitting the modifier asks for.

    Args:
        card: the interaction, whose ``kinematics`` must allow the modifier.
        particle: the dark matter particle.
        kinematics: elastic, inelastic or exothermic.
        splitting_kev: |δ| in keV; ignored (and must be 0) for elastic scattering.

    Raises:
        ValueError: if the card does not allow the modifier, or δ does not fit it.
    """
    if kinematics not in card.kinematics:
        raise ValueError(f"{card.id} does not allow {kinematics.value} scattering "
                         f"(it allows {', '.join(k.value for k in card.kinematics)})")
    if kinematics is Kinematics.elastic:
        if splitting_kev:
            raise ValueError("elastic scattering has no mass splitting")
        return particle.model_copy(update={"mass_splitting_kev": 0.0})
    if splitting_kev <= 0.0:
        raise ValueError(f"{kinematics.value} scattering needs a splitting |δ| > 0")
    sign = 1.0 if kinematics is Kinematics.inelastic else -1.0
    return particle.model_copy(update={"mass_splitting_kev": sign * splitting_kev})
