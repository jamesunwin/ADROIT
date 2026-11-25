"""A dark matter model as typed data: fields, couplings and interaction terms (DM8).

Path 1 for arbitrary Lagrangians starts from a model the library does not
have. The intake (a language-model agent, opt-in, or the user by hand) turns
a Lagrangian or a particle content into a ``ModelSpec``. Deterministic checks
then read it (``library.interactions.model_checks``): gauge invariance,
hermiticity and an anomaly flag. A term names its fields, with conjugation,
so that those checks need no parsing of formulas.

**Phases.** A model may be written above electroweak symmetry breaking
(fields carry SU(3)_c × SU(2)_L × U(1)_Y charges, with Q = T₃ + Y) or below
it (fields carry SU(3)_c and their electric charge, as quarks and the Z do in
a simplified model). New gauge groups are named in ``extra`` charges.

**Freeze-out** (the working assumption, 2026-10-01). A model also states:
- the symmetry that keeps the dark matter stable, as a parity per field
  (``dark_parity`` −1 for an odd field, +1 for an even one);
- the fraction of Ωh² = 0.12 it is meant to supply;
- the cosmological history assumed (standard: radiation domination from a
  reheating temperature far above m_χ/20, no late entropy release).

**Standard Model fields** carry the names of ``STANDARD_MODEL_FIELDS``, so that
the checks can tell what the dark sector couples to.
"""

from __future__ import annotations

from enum import Enum
import keyword
import math
import re

from pydantic import Field, field_validator, model_validator

from adroit.core.state import StrictModel
from adroit.core.kinematics import KINEMATIC_MASSES
from adroit.core.running import RGRequest
from adroit.core.chemical_equilibrium import ConversionRequest
from adroit.core.model_contracts import VectorCurrentContract,ScalarPotentialContract


class Phase(str, Enum):
    """Whether the model is written above or below electroweak symmetry breaking."""

    unbroken = "unbroken"
    broken = "broken"


STANDARD_COSMOLOGY = ("standard: radiation domination from a reheating temperature far above m_χ/20, "
                      "Standard Model degrees of freedom, no late entropy release")

# name → sector; "q" is every quark with one coupling, "l" every charged lepton, "nu" every neutrino
STANDARD_MODEL_FIELDS: dict[str, str] = {
    **{n: "quark" for n in ("q", "u", "d", "s", "c", "b", "t", "Q", "uR", "dR", "qL")},
    **{n: "lepton" for n in ("l", "e", "mu", "tau", "L", "eR", "lL")},
    **{n: "neutrino" for n in ("nu", "nu_e", "nu_mu", "nu_tau")},
    "h": "higgs", "H": "higgs", "A": "photon", "gamma": "photon", "Z": "z", "W": "w", "G": "gluon",
    "g": "gluon", "B": "hypercharge", "Wa": "w",
}
HEAVY_QUARKS = {q: KINEMATIC_MASSES[q] for q in ("t", "b", "c")}   # GeV, kinematic; "q" includes the top


YUKAWA_CONVENTIONS = ("sm", "DMsimp_s_spin0_MD")    # ``model_building.yukawa``: the stated Yukawas' inputs


class FieldRole(str, Enum):
    """A field's role in the model: dark matter, mediator, Standard Model or other."""
    dark_matter = "dark_matter"
    mediator = "mediator"
    standard_model = "standard_model"
    other = "other"


class Charges(StrictModel):
    """Gauge charges. SU(3) as "1", "3", "3bar" or "8"; SU(2) as the dimension of the multiplet."""

    su3: str = "1"
    su2: int = Field(default=1, ge=1)
    hypercharge: float = 0.0              # Y, with Q = T₃ + Y (unbroken phase)
    electric_charge: float = 0.0          # Q (broken phase)
    extra: dict[str, float] = Field(default_factory=dict)   # charges under new U(1)s, by name

    @model_validator(mode="after")
    def _a_known_colour(self) -> "Charges":
        if self.su3 not in ("1", "3", "3bar", "8"):
            raise ValueError(f"su3 must be 1, 3, 3bar or 8; got {self.su3!r}")
        return self


class ModelField(StrictModel):
    """One field: its spin, conjugation property, chirality, mass and charges."""

    name: str
    role: FieldRole
    spin: float = Field(ge=0.0)
    self_conjugate: bool = False          # real scalar, Majorana fermion, real vector
    chirality: str = ""                   # "L" or "R" for a Weyl fermion; "" otherwise
    generations: int = Field(default=1, ge=1)
    mass_gev: float | None = None
    masses_gev: list[float] | None = None    # one per generation of a new field, in place of mass_gev (G1's expansion)
    mass_justification: str = ""
    charges: Charges = Field(default_factory=Charges)
    dark_parity: int | None = None        # under the stabilising symmetry: −1 odd, +1 even, None unstated
    vev_gev: float | None = None          # a scalar's vacuum value: ⟨φ⁰⟩ = v/√2 (complex) or v (real); G1

    @model_validator(mode="after")
    def _chirality_is_for_fermions(self) -> "ModelField":
        if self.chirality not in ("", "L", "R"):
            raise ValueError("chirality is L, R or empty")
        if self.chirality and self.spin != 0.5:
            raise ValueError(f"{self.name}: only a spin-1/2 field has a chirality")
        if self.dark_parity not in (None, -1, 1):
            raise ValueError(f"{self.name}: dark_parity is −1, +1 or unstated")
        if self.vev_gev is not None and (self.spin != 0 or not math.isfinite(self.vev_gev)):
            raise ValueError(f"{self.name}: only a scalar has a vacuum value, and it must be finite")
        if self.masses_gev is not None and not all(math.isfinite(m) and m >= 0 for m in self.masses_gev):
            raise ValueError(f"{self.name}: each generation's mass must be finite and non-negative")
        return self


COUPLING_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")      # a coupling's name: an ASCII identifier (AL2-11)


class ModelCoupling(StrictModel):
    """A coupling: its value (None while symbolic), its mass dimension, and why it has that value."""

    name: str
    value: float | None = None
    mass_dimension: int = 0               # 0 for a dimensionless coupling; e.g. −1 for a dipole moment
    justification: str = ""

    @field_validator("name")
    @classmethod
    def _not_a_keyword(cls, value: str) -> str:
        """A formula is read as Python's arithmetic, so a keyword (``lambda``) cannot name a coupling (the audit's
        G1-14, G12: it had read as "no value"); and the name is written into generated source (a UFO model's
        parameters, which MadGraph imports), so it is an identifier of ASCII letters, digits and underscores, never
        anything else (AL2-11: a line break, a quote or an operator reached the source as written)."""
        if not COUPLING_NAME.fullmatch(value):
            raise ValueError(f"{value!r} cannot name a coupling: use letters, digits and underscores, starting with a "
                             "letter or an underscore (e.g. g_chi)")
        if keyword.iskeyword(value):
            raise ValueError(f"{value!r} is a reserved word in formulas; name the coupling otherwise (e.g. "
                             f"{value[:3]!r})")
        return value


class PhysicalFitRange(StrictModel):
    """Declared range of the Point.g_chi slot; other parameters remain fixed.

    This is the class's physical slot (e.g. a portal coupling), not an
    arbitrary Lagrangian symbol or an unconstrained NR amplitude.
    """

    low: float = Field(allow_inf_nan=False)
    high: float = Field(allow_inf_nan=False)
    parameter: str = "g_chi"

    @model_validator(mode="after")
    def _ordered(self) -> "PhysicalFitRange":
        if self.parameter != "g_chi" or self.low >= self.high:
            raise ValueError("physical_fit requires g_chi and low < high")
        return self

    @classmethod
    def perturbative_branch(cls, value: float) -> "PhysicalFitRange":
        """The existing original-sign branch when no range was declared."""
        bound = math.sqrt(4 * math.pi)
        return cls(low=-bound if value < 0 else 0., high=0. if value < 0 else bound)


class Occurrence(StrictModel):
    """A field in a term, conjugated or not (ψ† or ψ̄ counts as conjugated)."""

    field: str
    conjugate: bool = False


class ModelTerm(StrictModel):
    """One interaction term: its fields, its Lorentz structure and its coupling."""

    fields: list[Occurrence] = Field(min_length=2)
    lorentz: str                          # e.g. "scalar", "vector", "axial", "dipole", "tensor"
    coupling: str                         # the full coefficient in L, e.g. "g_q*m_q/v" (derivation's symbols)
    plus_hc: bool = False                 # "+ h.c." written after the term
    text: str = ""                        # the term in conventional notation
    indices: str = ""                     # the gauge-index contraction, where it is not unique (G1):
                                          # e.g. "H*[i] phi[i] phi*[j] H[j]"; model_building.indices
    flavour: list[float] | list[list[float]] | None = None   # a multi-generation term's factor per generation (a
                                          # list for one occurrence, a matrix for two; model_building.generations)

    @field_validator("coupling")
    @classmethod
    def _formula(cls, value: str) -> str:
        """A coupling is a formula of names, numbers and named functions (``arithmetic.check_formula``): text from
        a paper or a language model is never evaluated as Python."""
        from adroit.core.arithmetic import check_formula
        return check_formula(value)


class ModelSpec(StrictModel):
    """A dark matter model as data."""

    name: str
    phase: Phase = Phase.broken
    source: str = ""                      # the user's own words, kept with the model
    fields: list[ModelField]
    couplings: list[ModelCoupling] = Field(default_factory=list)
    terms: list[ModelTerm] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    dropped: list[str] = Field(default_factory=list)   # what of the full model is left out
    stability: str = ""                   # the stabilising symmetry, e.g. "Z2: chi → −chi"; "" unstated
    relic_fraction: float = Field(default=1.0, gt=0.0, le=1.0)   # of Ωh² = 0.12, by thermal freeze-out
    yukawa: str = "sm"                    # what m_q, m_l, m_f mean in stated couplings (``model_building.yukawa``)
    cosmology: str = STANDARD_COSMOLOGY
    physical_fit: PhysicalFitRange | None = None
    vector_currents: VectorCurrentContract | None = None
    scalar_potential: ScalarPotentialContract | None = None
    scalar_running: RGRequest | None = None
    chemical_equilibrium: ConversionRequest | None = None

    @model_validator(mode="after")
    def _references_resolve(self) -> "ModelSpec":
        if self.yukawa not in YUKAWA_CONVENTIONS:
            raise ValueError(f"yukawa is one of {', '.join(YUKAWA_CONVENTIONS)}, not {self.yukawa!r}")
        names = [f.name for f in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("field names must be unique")
        if not any(f.role is FieldRole.dark_matter for f in self.fields):
            raise ValueError("a model needs a dark matter field")
        if self.vector_currents is not None and self.scalar_potential is not None:
            raise ValueError("one explicit numerical model contract per ModelSpec")
        if self.chemical_equilibrium is not None and (self.scalar_potential or self.vector_currents):
            raise ValueError("chemical-equilibrium request cannot apply to a scalar/vector contract")
        if self.scalar_running is not None and self.scalar_potential is None:
            raise ValueError("scalar_running requires a complete scalar potential")
        mapped=(list(self.vector_currents.flavours.values()) if self.vector_currents else
                [self.scalar_potential.higgs_field,self.scalar_potential.singlet_field] if self.scalar_potential else [])
        if any(name not in names for name in mapped):
            raise ValueError("model contract field mappings must name declared fields")
        for term in self.terms:
            for occurrence in term.fields:
                if occurrence.field not in names:
                    raise ValueError(f"term {term.text or term.lorentz} names an unknown field "
                                     f"{occurrence.field!r}")
        return self

    def field(self, name: str) -> ModelField:
        """One field by name."""
        return next(f for f in self.fields if f.name == name)

    @property
    def dark_matter(self) -> ModelField:
        """The (first) dark matter field."""
        return next(f for f in self.fields if f.role is FieldRole.dark_matter)


def sector(field: ModelField) -> str | None:
    """The Standard Model sector of a field (quark, lepton, ..., photon), or None for a new field."""
    if field.role is not FieldRole.standard_model:
        return None
    if field.name in STANDARD_MODEL_FIELDS:
        return STANDARD_MODEL_FIELDS[field.name]
    if field.charges.su3 in ("3", "3bar"):
        return "quark"
    if field.spin == 1.0 and field.charges.su3 == "8":
        return "gluon"
    if field.spin == 0.5:
        return "lepton" if abs(field.charges.electric_charge) > 0 or field.charges.su2 == 2 else "neutrino"
    return "unknown"
