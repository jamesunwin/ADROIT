"""A model's field content as the building blocks of operators (DM12).

Every field becomes one or more **components** in a uniform convention:
- **Fermions** are left-handed Weyl spinors. A left-handed field is itself; a
  right-handed field ψ_R enters as its conjugate (ψ_R)ᶜ, with conjugate
  representation and opposite charges; a Dirac field is the pair ψ, ψᶜ; a
  Majorana field is one left-handed spinor in a real representation.
- **Scalars** are complex (φ and φ* are distinct building blocks) or real (a
  self-conjugate field in a real representation).
- **Vectors** are either the gauge boson of a new U(1) (a spin-1 field named as
  one of the ``extra`` charges), whose couplings follow from covariant
  derivatives, or a neutral massive vector, which couples to currents.

The Standard Model's fields (above electroweak symmetry breaking) are added
from ``STANDARD_MODEL``: Q, uR, dR, L, eR with three generations, H, and the
field strengths of B, W and G. Charges follow Q = T₃ + Y.
"""

from __future__ import annotations

from fractions import Fraction

from pydantic import Field

from adroit.core.model_spec import Charges, FieldRole, ModelField, ModelSpec
from adroit.core.state import StrictModel
from adroit.model_building.groups import Rep, su3_conjugate


class Component(StrictModel):
    """One building block: a left-handed Weyl spinor, a scalar (or its conjugate), or a vector."""

    name: str                       # e.g. "chi", "chi^c", "S", "S*", "Q"
    field: str                      # the model field it comes from
    kind: str                       # "weyl", "scalar", "vector"
    su3: str = "1"
    su2: int = 1
    hypercharge: float = 0.0
    extra: dict[str, float] = Field(default_factory=dict)
    parity: int = 1                 # under the stabilising Z2
    flavours: int = 1
    real: bool = False              # a real scalar or a Majorana spinor (its own conjugate)
    conjugated: bool = False        # φ* or ψᶜ (relative to the model field)
    standard_model: bool = False
    gauge_of: str = ""              # for a vector: the extra U(1) it gauges ("" for a massive vector)

    def rep(self) -> Rep:
        """The component's SU(3) × SU(2) representation, with its flavours."""
        return Rep(self.su3, self.su2, self.flavours)

    def charges(self) -> dict[str, float]:
        """The component's U(1) charges: the hypercharge Y and any extra charges."""
        return {"Y": self.hypercharge, **self.extra}

    def conjugate(self) -> "Component":
        """φ → φ*, ψ → ψ† (the conjugate representation and charges)."""
        if self.real:
            return self
        name = self.name[:-1] if self.name.endswith("*") else f"{self.name}*"
        return self.model_copy(update={"name": name, "su3": su3_conjugate(self.su3), "hypercharge": -self.hypercharge,
                                       "extra": {k: -v for k, v in self.extra.items()},
                                       "conjugated": not self.conjugated})


def _sm(name: str, field: str, su3: str, su2: int, y: float, kind: str = "weyl", flavours: int = 3,
        conjugated: bool = False) -> Component:
    return Component(name=name, field=field, kind=kind, su3=su3, su2=su2, hypercharge=y, flavours=flavours,
                     standard_model=True, conjugated=conjugated)


# Left-handed Weyl fields (three generations): the doublets, and the conjugates of the right-handed
# singlets (uR^c is (u_R)^c, with the conjugate representation); and the Higgs doublet.
STANDARD_MODEL: list[Component] = [
    _sm("Q", "Q", "3", 2, 1 / 6), _sm("uR^c", "uR", "3bar", 1, -2 / 3, conjugated=True),
    _sm("dR^c", "dR", "3bar", 1, 1 / 3, conjugated=True), _sm("L", "L", "1", 2, -1 / 2),
    _sm("eR^c", "eR", "1", 1, 1.0, conjugated=True), _sm("H", "H", "1", 2, 1 / 2, kind="scalar", flavours=1),
]
STANDARD_MODEL_FIELD_STRENGTHS = {"B": ("1", 1), "W": ("1", 3), "G": ("8", 1)}


def _is_real_rep(c: Charges) -> bool:
    return c.su3 in ("1", "8") and c.su2 % 2 == 1 and c.hypercharge == 0 and not any(c.extra.values())


def snap(charge: float) -> float:
    """A charge as the nearest fraction with denominator ≤ 36, if within 10⁻⁴ (0.6666667 → 2/3).

    Invariance is decided by charges summing to zero exactly, so a charge written to a few
    decimals (in a YAML file, or by a language model) must be read as the fraction it means.
    """
    near = Fraction(charge).limit_denominator(36)
    return float(near) if abs(float(near) - charge) < 1e-4 else charge


def components(field: ModelField, gauge_groups: set[str]) -> list[Component]:
    """The building blocks of one new field. Raises ValueError for what the generator cannot hold."""
    c = field.charges
    base = dict(field=field.name, su3=c.su3, su2=c.su2, hypercharge=snap(c.hypercharge),
                extra={k: snap(v) for k, v in c.extra.items()},
                parity=field.dark_parity or 1, flavours=field.generations)
    if field.spin == 0:
        if field.self_conjugate and not _is_real_rep(c):
            raise ValueError(f"{field.name}: a real scalar must be in a real representation with no U(1) charge")
        return [Component(name=field.name, kind="scalar", real=field.self_conjugate, **base)]
    if field.spin == 0.5:
        if field.self_conjugate:
            if not _is_real_rep(c):
                raise ValueError(f"{field.name}: a Majorana fermion must be in a real representation with no U(1) charge")
            return [Component(name=field.name, kind="weyl", real=True, **base)]
        left = Component(name=field.name, kind="weyl", **base)
        if field.chirality == "L":
            return [left]
        if field.chirality == "R":
            return [left.conjugate().model_copy(update={"name": f"{field.name}^c"})]
        return [left, left.conjugate().model_copy(update={"name": f"{field.name}^c"})]
    if field.spin == 1:
        if c.su3 != "1" or c.su2 != 1 or c.hypercharge or any(c.extra.values()):
            raise ValueError(f"{field.name}: only neutral vectors (a new U(1)'s boson, or a massive neutral "
                             "vector) are supported by the generator")
        gauged = field.name if field.name in gauge_groups else ""
        return [Component(name=field.name, kind="vector", real=True, gauge_of=gauged, **base)]
    raise ValueError(f"{field.name}: spin {field.spin} is not supported (0, 1/2 and 1 are)")


def new_fields(spec: ModelSpec) -> list[ModelField]:
    """The model's fields that are not the Standard Model's."""
    return [f for f in spec.fields if f.role is not FieldRole.standard_model]


def content(spec: ModelSpec) -> list[Component]:
    """Every building block: the Standard Model's, then the model's new fields'."""
    groups = {k for f in spec.fields for k in f.charges.extra}
    out = list(STANDARD_MODEL)
    for f in new_fields(spec):
        out += components(f, groups)
    return out
