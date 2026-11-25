"""A user's model as Track 2 candidates (DM14): its nucleon-level interaction at each mass.

A typed model (DM8 or DM12) enters Path 2 beside the library, one candidate
per dark matter mass. Its interaction at a mass comes from:
- its computable class (DM13: a spin-1 or scalar mediator), which gives the
  interaction directly at its stated couplings; or
- its derivation (DM8's Wilson coefficients), reduced by DirectDM.

A model with neither cannot enter, and the reason is given. Path 2 then
scales every coupling by one strength μ, as for a card, so μ̂ = 1 means the
model's stated couplings explain the events.
"""

from __future__ import annotations

import math

from adroit.core.dm_state import InteractionModel
from adroit.core.model_spec import ModelSpec
from adroit.library.interactions import derivation as dv
from adroit.library.interactions import quark_level
from adroit.orchestrator.signal import Candidate
from adroit.parameter_space.classify import Unsupported, classify


def interaction(spec: ModelSpec, mass_gev: float, derivation: dv.Derivation | None = None) -> InteractionModel:
    """The model's nucleon-level interaction at one dark matter mass.

    Raises:
        Unsupported: if the model is in no computable class and has no derivation.
    """
    try:
        cls, point, _ = classify(spec)
    except Unsupported as error:
        if derivation is None:
            raise Unsupported(f"{error}; and no derivation (DM8's Wilson coefficients) was given") from error
        dm = spec.dark_matter
        quark = dv.evaluate(derivation, spec, {f"m_{dm.name}": mass_gev})
        return quark_level.to_interaction(quark, mass_gev)[1]
    return cls.interaction(point.model_copy(update={"m_chi": mass_gev}))


def candidates(spec: ModelSpec, masses_gev: list[float], derivation: dv.Derivation | None = None) -> list[Candidate]:
    """One Path 2 candidate per mass, labelled ``<model>@<mass>``."""
    if any(not math.isfinite(m) or m <= 0 for m in masses_gev) or len(set(masses_gev)) != len(masses_gev):
        raise ValueError("candidate masses must be distinct, positive and finite")
    spin = spec.dark_matter.spin
    return [Candidate(label=f"{spec.name}@{int(m) if float(m).is_integer() else repr(float(m))}",
                      display_label=f"{spec.name}@{m:g}", mass_gev=m, interaction=interaction(spec, m, derivation),
                      spin=spin, model=spec.name)
            for m in masses_gev]
