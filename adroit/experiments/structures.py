"""Nuclear-response structures validated against published per-model limits (R6, audit M8).

A module's validated ranges (``status``) are for spin-independent and spin-dependent scattering: they test its
statistics with those spectra and its target's O₁ and O₄ responses. Any other interaction (O₃, O₅–O₁₅, a
momentum-dependent mixture, an inelastic splitting) has a different response structure, which those ranges do
not test. ``docs/dm6/validate_direct_route.py`` compares the direct route with LZ's published limits for 43
such structures on xenon (arXiv:2609.02823) and records where each agrees: the structure, its splitting, its
validated masses, the target and the nuclear responses used (``data/validated_structures.yaml``).

A structure validated there transfers only to a calculation on the same target with the same responses.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from adroit.core.dm_state import DarkMatterParticle, InteractionModel

STATUS = Path(__file__).with_name("data") / "validated_structures.yaml"


@lru_cache(maxsize=1)
def load() -> dict:
    """The status file, or an empty one before any validation has run."""
    if not STATUS.exists():
        return {"structures": {}}
    return yaml.safe_load(STATUS.read_text()) or {"structures": {}}


def clear_cache() -> None:
    """Forget the loaded status (tests that write their own)."""
    load.cache_clear()
    _reference.cache_clear()


@lru_cache(maxsize=4096)
def _reference(card: str, isospin: str, mass: float, splitting: float) -> InteractionModel:
    from adroit.experiments.lz_extended_window import lz_values
    from adroit.library.interactions import registry
    particle = DarkMatterParticle(mass_gev=mass, mass_splitting_kev=splitting)
    return registry.resolve(card, particle, lz_values(card, isospin))


def matching(interaction: InteractionModel, particle: DarkMatterParticle) -> tuple[str, dict] | None:
    """(name, entry) of the validated structure the interaction is proportional to at this splitting, else None.
    The mass is not checked here (``validated_at``)."""
    from adroit.library.interactions import degeneracy
    for name, entry in load().get("structures", {}).items():
        if entry["splitting_kev"] != particle.mass_splitting_kev:
            continue
        reference = _reference(entry["card"], entry["isospin"], particle.mass_gev, particle.mass_splitting_kev)
        if degeneracy.proportional(interaction, reference):
            return name, entry
    return None


def validated_at(entry: dict, mass: float, tolerance: float = 1e-4) -> bool:
    """Whether the mass lies in the structure's validated span."""
    span = entry.get("validated_gev")
    return bool(span) and span[0] * (1 - tolerance) <= mass <= span[1] * (1 + tolerance)


def scope() -> tuple[str, str]:
    """(target, nuclear model) of the validation."""
    data = load()
    return data.get("target", ""), data.get("nuclear_model", "")
