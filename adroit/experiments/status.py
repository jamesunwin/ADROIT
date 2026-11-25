"""Where each module is validated: the status file written by the DM3 validation.

``docs/dm3/validate_modules.py`` compares every module with its
collaboration's published limit, stores the comparisons in
``docs/dm3/validation_results.json``, and records per module and
cross-section kind the validated mass range (``ValidationResult.validated_range``)
in ``data/validated_ranges.yaml``. A module's limit outside its validated
range is reported only as a flag, never used as a constraint.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

import yaml

from adroit.core.dm_state import CrossSectionKind, ValidationResult

STATUS_FILE = "data/validated_ranges.yaml"


@lru_cache(maxsize=1)
def validated_ranges() -> dict:
    """The status file's contents ({} before any validation run)."""
    path = resources.files("adroit.experiments").joinpath(STATUS_FILE)
    return yaml.safe_load(path.read_text()) if path.is_file() else {}


def validated_range(experiment: str, kind: CrossSectionKind | str) -> tuple[float, float] | None:
    """The range over which the module reproduces the published limit, or None.

    ``kind`` is a cross-section kind (a mass range in GeV) or a model label
    such as "L10s" (a range in that comparison's variable).
    """
    key = kind.value if isinstance(kind, CrossSectionKind) else kind
    entry = validated_ranges().get("modules", {}).get(experiment, {}).get(key)
    if not entry or entry["validated_gev"] is None:
        return structure_range(experiment, key)
    low, high = entry["validated_gev"]
    return float(low), float(high)


# A module validated structure by structure (the LZ extended window, against LZ's per-interaction tables) has an
# SI range where its elastic isoscalar O₁ table is validated: O₁ with equal proton and neutron couplings is
# spin-independent scattering, response for response. No elastic O₄ table is validated, so it has no SD range.
STRUCTURE_FOR_KIND = {"SI": "O01s_d0"}


def structure_range(experiment: str, kind: str) -> tuple[float, float] | None:
    """The kind's range from the module's validated structures (``STRUCTURE_FOR_KIND``), or None."""
    from adroit.experiments import structures
    name = STRUCTURE_FOR_KIND.get(kind)
    status = structures.load()
    if name is None or status.get("module") != experiment:
        return None
    entry = status.get("structures", {}).get(name)
    if not entry or entry.get("validated_gev") is None or entry.get("splitting_kev", 0.0) != 0.0:
        return None
    low, high = entry["validated_gev"]
    return float(low), float(high)


def entry(result: ValidationResult) -> dict:
    """The status-file record of one comparison."""
    span = result.validated_range
    inside = [r for m, r in zip(result.masses_gev, result.ratios)
              if span is not None and span[0] <= m <= span[1]]
    best = result.strongest_mass_gev
    return {"validated_gev": None if span is None else [round(span[0], 4), round(span[1], 4)],
            "strongest_published_limit_gev": None if best is None else round(best, 4),
            "counts_for_gate": result.counts_for_gate,
            "every_mass_passes": result.passed,
            "ratio_range_inside": None if not inside else [round(min(inside), 3), round(max(inside), 3)],
            "edge_clause_masses_gev": [round(m, 4) for m, e in zip(result.masses_gev, result.edge_passes) if e],
            "tested_masses": len(result.masses_gev),
            "quantity": result.quantity, "variable": result.variable}
