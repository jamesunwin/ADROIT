"""The interaction library's cards: one interaction each, at one layer (build plan, DM4).

The library is layered (build plan, section 3). Each card maps to the layer
below it through ``terms``:

    layer 3, mediator models     →  the Lagrangians L1–L20 (integrate out the mediator)
    layer 2, Lagrangians L1–L20  →  the operators O_i (take the nonrelativistic limit)
    layer 1, operators O_i       →  the nuclear responses W_k (listed, not mapped)

A term is a monomial. Its contribution to the coefficient of its target is

    factor × Π_couplings × m_χ^a m_N^b m_M^c Π_p p^e × q^q_power ,

with the masses and parameters in GeV, so that every coefficient comes out
in GeV units with q in GeV. ``m_N`` is the operator mass of
``conventions.OPERATOR_MASS_GEV`` and ``m_M`` the matching scale of
arXiv:1308.6288 (its Table 1), m_v = 246.2 GeV by default. A coupling name
containing ``{N}`` stands for the nucleon's own coupling: ``gV_{N}`` is
``gV_p`` for protons and ``gV_n`` for neutrons.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from adroit.core.dm_state import ModelLayer
from adroit.core.state import StrictModel

MASS_SYMBOLS = ("m_chi", "m_N", "m_M")


class PriorKind(str, Enum):
    """How a parameter is drawn when the library is scanned."""

    log_uniform = "log_uniform"
    uniform = "uniform"
    fixed = "fixed"


class Parameter(StrictModel):
    """A parameter of a card, with its prior."""

    name: str
    unit: str
    description: str
    default: float
    prior: PriorKind = PriorKind.fixed
    low: float | None = None
    high: float | None = None
    source: str = ""

    @model_validator(mode="after")
    def _range_for_a_free_prior(self) -> "Parameter":
        if self.prior is not PriorKind.fixed and (self.low is None or self.high is None
                                                  or not self.low < self.high):
            raise ValueError(f"{self.name}: a {self.prior.value} prior needs low < high")
        if self.prior is PriorKind.log_uniform and self.low is not None and self.low <= 0:
            raise ValueError(f"{self.name}: a log-uniform prior needs low > 0")
        return self


class Term(StrictModel):
    """One monomial of a card's map to the layer below."""

    target: str                                   # "O1" … "O15" or "L01" … "L20"
    factor: float
    couplings: list[str] = Field(default_factory=list)
    powers: dict[str, int] = Field(default_factory=dict)
    q_power: int = 0


class Deformation(str, Enum):
    """The physical deformations that connect neighbouring cards (build plan, DM4)."""

    integrate_out_mediator = "integrate_out_mediator"
    nonrelativistic_limit = "nonrelativistic_limit"
    add_mass_splitting = "add_mass_splitting"
    change_isospin = "change_isospin"
    make_mediator_light = "make_mediator_light"
    specialise_couplings = "specialise_couplings"
    change_lorentz_structure = "change_lorentz_structure"


class NeighbourLink(StrictModel):
    """A declared edge of the neighbour graph, beyond the maps between layers."""

    target: str
    deformation: Deformation
    note: str = ""


class ValidityKind(str, Enum):
    """Conditions a card's use must meet; ``library.interactions.checks`` tests them."""

    contact = "contact"                   # a heavy mediator: its mass ≫ q
    dirac_only = "dirac_only"             # vanishes for Majorana dark matter
    spin_half = "spin_half"               # written for spin-1/2 dark matter
    perturbative = "perturbative"         # couplings below 4π
    inelastic_only = "inelastic_only"     # needs a mass splitting δ > 0


class Validity(StrictModel):
    """One validity condition, with its reason."""

    kind: ValidityKind
    note: str = ""


class Kinematics(str, Enum):
    """The kinematic modifiers (build plan, DM4)."""

    elastic = "elastic"
    inelastic = "inelastic"          # δ > 0: the dark matter gains mass in the scattering
    exothermic = "exothermic"        # δ < 0


class InteractionCard(StrictModel):
    """One interaction of the library.

    ``responses`` (layer 1 only) lists the nuclear responses the operator
    reaches, in the names of ``physics.nuclear.RESPONSES``; the tests check it
    against the rate code. ``isospin_variants`` says whether the card comes
    in isoscalar and isovector forms (couplings ``*_p`` and ``*_n``).
    """

    id: str
    name: str
    layer: ModelLayer
    description: str
    interaction: str = ""                     # the operator or Lagrangian, as written
    parameters: list[Parameter] = Field(default_factory=list)
    terms: list[Term] = Field(default_factory=list)
    mediator_mass: str = ""                   # the parameter holding it, for a propagator
    responses: list[str] = Field(default_factory=list)
    parity_time: str = ""                     # "E/E", "O/E", … (arXiv:1308.6288, Table 1)
    isospin_variants: bool = False
    kinematics: list[Kinematics] = Field(default_factory=lambda: [Kinematics.elastic])
    validity: list[Validity] = Field(default_factory=list)
    constraint_tiers: list[int] = Field(default_factory=lambda: [1])
    dropped: list[str] = Field(default_factory=list)
    neighbours: list[NeighbourLink] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)

    def parameter(self, name: str) -> Parameter:
        """The parameter called ``name``."""
        for p in self.parameters:
            if p.name == name:
                return p
        raise KeyError(f"{self.id} has no parameter {name!r}")

    def defaults(self) -> dict[str, float]:
        """Every parameter at its default value."""
        return {p.name: p.default for p in self.parameters}
