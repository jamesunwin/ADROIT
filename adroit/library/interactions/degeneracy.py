"""Degeneracy classes: interactions whose recoil spectra a target cannot tell apart (DM4).

Two interactions are compared by the shapes of their spectra in a search:
the recoil spectrum on the target, weighted by the search's efficiency and
normalised to unit area over its window. For shapes p and p', the expected
log-likelihood ratio per event, averaged over which of the two is true, is
half the Jeffreys divergence

    J = ∫ (p − p') ln(p/p') dE ,

so telling them apart at z standard deviations takes about N = z²/J events.
Two interactions are degenerate at N events if N_z > N; the classes are the
connected sets of that relation (single linkage). Interactions whose
coefficients are proportional (``proportional``) are degenerate exactly.
"""

from __future__ import annotations

import numpy as np

from adroit.core.dm_state import (DarkMatterParticle, HaloModel, InteractionModel,
                                      NuclearModel, Target)
from adroit.core.state import StrictModel
from adroit.physics import rates

FLOOR = 1e-12        # relative floor on a shape, so that ln(p/p') stays finite


class ModelPoint(StrictModel):
    """One model of a scan: an interaction at a mass (and splitting)."""

    label: str
    interaction: InteractionModel
    particle: DarkMatterParticle


def shape(point: ModelPoint, target: Target, energies_kev: np.ndarray,
          efficiency: np.ndarray, halo: HaloModel | None = None,
          model: NuclearModel = NuclearModel.shell_model) -> np.ndarray | None:
    """The efficiency-weighted spectrum on ``energies_kev``, normalised to unit area.

    None if the interaction gives no events in the window (e.g. a splitting
    too large for the halo's fastest particles).
    """
    spectrum = rates.differential_rate(energies_kev, point.particle, point.interaction, target,
                                       halo, model)
    weighted = np.asarray(spectrum.rate) * efficiency
    area = float(np.trapezoid(weighted, energies_kev))
    return None if area <= 0.0 else weighted / area


def jeffreys_matrix(shapes: np.ndarray, energies_kev: np.ndarray) -> np.ndarray:
    """J between every pair of rows of ``shapes`` (each a normalised shape on the grid)."""
    weights = np.gradient(energies_kev)
    floor = FLOOR * shapes.max(axis=1, keepdims=True)
    logs = np.log(np.maximum(shapes, floor))
    self_term = (shapes * logs * weights).sum(axis=1)
    cross = (shapes * weights) @ logs.T
    j = self_term[:, None] + self_term[None, :] - cross - cross.T
    return np.maximum(j, 0.0)


def events_to_separate(j: np.ndarray | float, z: float = 2.0) -> np.ndarray | float:
    """The events needed to tell two shapes apart at z standard deviations, z²/J."""
    with np.errstate(divide="ignore"):
        return z * z / np.asarray(j, dtype=float)


def classes(labels: list[str], j: np.ndarray, n_events: float, z: float = 2.0) -> list[list[str]]:
    """The degeneracy classes at ``n_events``: connected sets of pairs needing more events."""
    parent = list(range(len(labels)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    threshold = z * z / n_events
    for a, b in zip(*np.nonzero(np.triu(j <= threshold, k=1))):
        parent[root(int(a))] = root(int(b))
    groups: dict[int, list[str]] = {}
    for i, label in enumerate(labels):
        groups.setdefault(root(i), []).append(label)
    return sorted(groups.values(), key=lambda g: labels.index(g[0]))


def _vector(model: InteractionModel) -> dict[tuple, tuple[float, float]]:
    return {(c.operator, c.q_power, c.q_scale_gev, c.mediator_mass_gev): (c.proton, c.neutron)
            for c in model.coefficients}


def proportional(a: InteractionModel, b: InteractionModel, tolerance: float = 1e-9) -> bool:
    """Whether the two interactions' coefficients are proportional, term by term.

    Proportional interactions have identical spectra up to normalisation on
    every target, at every mass: they are degenerate exactly.
    """
    va, vb = _vector(a), _vector(b)
    if set(va) != set(vb) or not va:
        return False
    x = np.array([v for key in sorted(va) for v in va[key]])
    y = np.array([v for key in sorted(vb) for v in vb[key]])
    scale = float(x @ y) / float(y @ y) if float(y @ y) else 0.0
    return scale != 0.0 and float(np.abs(x - scale * y).max()) <= tolerance * float(np.abs(x).max())
