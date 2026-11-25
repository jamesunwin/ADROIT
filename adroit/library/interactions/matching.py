"""Is an interaction one the library already has? Card by card, by a linear fit (DM8).

A derived interaction (from a bespoke Lagrangian, through ``quark_level``) is
compared with every card. A card's coefficients are linear in its nucleon
couplings (parameters ending _p or _n): each term carries exactly one. Where
the nucleon side is a Standard Model boson's (the photon's charges and
moments, the Z's charges, the Higgs's f_N), those are constants, never fitted,
and the card is fitted in its dark matter coupling instead. So for
each card, with its other parameters at reference values (the dark matter
coupling at 1, a mediator in the contact limit unless the interaction has a
propagator of its own), the best nucleon couplings follow from linear least
squares, and the residual says how far the card is from the interaction.

**The measure.** Each operator's coefficient is weighted by its natural size
in a rate: (q/m_N)^k for its powers of q/m_N, and 10⁻³ for each power of the
transverse velocity v⊥. The coefficients are compared on momentum transfers
from 1 MeV to 300 MeV, for protons and neutrons. The relative residual is
‖T − Σ x_k B_k‖ / ‖T‖. Below 10⁻⁶ the card is the interaction; up to 5% it
is the interaction up to what the residual names (for instance the pion pole
that a quark-level axial current induces, which the nucleon-level card
omits). A coupling whose fitted effect is below 0.1% of the interaction is not
determined by it, and is set to zero and listed as such.
"""

from __future__ import annotations

import numpy as np
from pydantic import Field

from adroit.core.dm_state import DarkMatterParticle, InteractionModel
from adroit.core.state import StrictModel
from adroit.library.interactions import registry
from adroit.physics.conventions import OPERATOR_MASS_GEV

Q_GRID = np.geomspace(1e-3, 0.3, 24)
Q_OVER_M = {1: 0, 3: 1, 4: 0, 5: 1, 6: 2, 7: 0, 8: 0, 9: 1, 10: 1, 11: 1, 12: 0, 13: 1, 14: 1, 15: 2}
VELOCITY = {3: 1, 5: 1, 7: 1, 8: 1, 12: 1, 13: 1, 14: 1, 15: 1}
EXACT, CLOSE = 1e-6, 0.05
INFLUENCE = 1e-3                       # below this a fitted coupling is undetermined
CONTACT_MASS_GEV = 1e5
MESONS = (0.13498, 0.547862)           # the pion and eta poles DirectDM produces


class CardMatch(StrictModel):
    """How well one card reproduces an interaction."""

    card_id: str
    residual: float                          # relative, in the weighted measure
    values: dict[str, float]                 # the fitted nucleon couplings (others at reference)
    reference: dict[str, float] = Field(default_factory=dict)   # the other parameters used
    remainder: dict[int, float] = Field(default_factory=dict)   # operator → its share of the residual
    undetermined: list[str] = Field(default_factory=list)       # couplings with < 0.1% effect, set to 0

    @property
    def verdict(self) -> str:
        """"same", "close" (within 5%, up to the remainder) or "different"."""
        return "same" if self.residual < EXACT else "close" if self.residual < CLOSE else "different"


def _weights() -> np.ndarray:
    """(operator, q) weights: (q/m_N)^k (10⁻³)^velocity."""
    ops = sorted(Q_OVER_M)
    return np.array([(Q_GRID / OPERATOR_MASS_GEV) ** Q_OVER_M[o] * 1e-3 ** VELOCITY.get(o, 0) for o in ops])


def vector(interaction: InteractionModel) -> np.ndarray:
    """The interaction as one weighted vector over (nucleon, operator, q)."""
    ops = sorted(Q_OVER_M)
    out = np.zeros((2, len(ops), Q_GRID.size))
    for c in interaction.coefficients:
        if c.operator in Q_OVER_M:
            factor = c.q_factor(Q_GRID)
            out[0, ops.index(c.operator)] += c.proton * factor
            out[1, ops.index(c.operator)] += c.neutron * factor
    return (out * _weights()[None]).ravel()


def _own_propagators(interaction: InteractionModel) -> list[float]:
    masses = {c.mediator_mass_gev for c in interaction.coefficients if c.mediator_mass_gev}
    return sorted(m for m in masses if not any(abs(m - meson) < 1e-3 for meson in MESONS))


def fit_card(card_id: str, particle: DarkMatterParticle, interaction: InteractionModel) -> CardMatch | None:
    """The best nucleon couplings of one card for the interaction; None if the card has none."""
    card = registry.card(card_id)
    linear = _linear_parameters(card)
    if not linear:
        return None
    reference = {p.name: p.default for p in card.parameters if p.name not in linear}
    if card.mediator_mass:
        own = _own_propagators(interaction)
        reference[card.mediator_mass] = own[0] if own else CONTACT_MASS_GEV
    for name in reference:
        if name.startswith("g_chi"):
            reference[name] = 1.0
    target = vector(interaction)
    norm = float(np.linalg.norm(target)) or 1.0
    columns = {k: vector(registry.resolve(card_id, particle, {**reference, **{n: float(n == k) for n in linear}}))
               for k in linear}
    kept, x = _fit(columns, target, norm)
    rest = target - sum((x[k] * columns[k] for k in kept), np.zeros_like(target))
    ops = sorted(Q_OVER_M)
    per_op = (rest.reshape(2, len(ops), Q_GRID.size) ** 2).sum(axis=(0, 2))
    remainder = {o: float(np.sqrt(v) / norm) for o, v in zip(ops, per_op) if np.sqrt(v) / norm > 1e-6}
    return CardMatch(card_id=card_id, residual=float(np.linalg.norm(rest) / norm),
                     values={k: x.get(k, 0.0) for k in linear}, reference=reference,
                     remainder=remainder, undetermined=sorted(set(linear) - set(kept)))


def _fit(columns: dict[str, np.ndarray], target: np.ndarray, norm: float) -> tuple[list[str], dict[str, float]]:
    """Least squares, dropping couplings whose fitted effect is below INFLUENCE of the target.

    A coupling that moves the weighted coefficients by less than 0.1% is not determined
    by the interaction (its fitted value would only absorb subleading differences between
    reductions); it is set to zero and reported as undetermined.
    """
    kept = list(columns)
    while kept:
        basis = np.array([columns[k] for k in kept]).T
        solution, *_ = np.linalg.lstsq(basis, target, rcond=None)
        influence = {k: float(np.linalg.norm(v * columns[k]) / norm) for k, v in zip(kept, solution)}
        weakest = min(kept, key=lambda k: influence[k])
        if influence[weakest] >= INFLUENCE or len(kept) == 1:
            return kept, {k: float(v) for k, v in zip(kept, solution)}
        kept.remove(weakest)
    return [], {}


# Standard Model inputs on the cards whose nucleon side is a Standard Model boson: the photon's
# (charges and magnetic moments), the Z's and the Higgs's. They are never fitted, so a
# disagreement in them shows as a residual.
STANDARD_MODEL = {"e", "Q_p", "Q_n", "kappa_p", "kappa_n", "G_F", "m_Z", "fN_p", "fN_n", "m_h",
                  "m_nucleon", "v_h"}
STANDARD_MODEL_BY_CARD = {"M_z_portal": {"gV_p", "gV_n", "gA_p", "gA_n"}}


def _linear_parameters(card) -> list[str]:
    """The parameters to fit: the nucleon couplings, or else the dark matter couplings."""
    constants = STANDARD_MODEL | STANDARD_MODEL_BY_CARD.get(card.id, set())
    names = [p.name for p in card.parameters if p.name not in constants]
    nucleon = [name for name in names if name.endswith(("_p", "_n"))]
    if nucleon:
        return nucleon
    return [name for name in names if name != card.mediator_mass and not name.startswith("m_")]


def match(particle: DarkMatterParticle, interaction: InteractionModel,
          card_ids: list[str] | None = None) -> list[CardMatch]:
    """Every card's fit to the interaction, best first."""
    fits = []
    for card_id in card_ids or list(registry.cards()):
        try:
            fitted = fit_card(card_id, particle, interaction)
        except (KeyError, ValueError):
            continue
        if fitted is not None:
            fits.append(fitted)
    return sorted(fits, key=lambda f: (f.residual, f.card_id))
