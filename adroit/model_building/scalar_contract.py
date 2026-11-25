"""Complete Z2 potential expansion and explicit scalar mass/vertex matching."""

from __future__ import annotations

from collections import Counter
import math

from adroit.core.model_spec import ModelSpec, ModelTerm, Occurrence, ModelCoupling, FieldRole, Phase
from adroit.core.model_contracts import ResolvedScalarPotential
from adroit.library.interactions.model_checks import coupling_value
from adroit.library.interactions.derivation import evaluate_expression, symbol_table


def coefficients(
    potential: ResolvedScalarPotential, phase: Phase
) -> dict[str, tuple[list[Occurrence], float, int]]:
    """Full coefficients in L=-V, including quadratic and SM-self terms."""
    h, s = potential.higgs_field, potential.singlet_field

    def fields(name: str, n: int) -> list[Occurrence]:
        return [Occurrence(field=name) for _ in range(n)]

    hh = [Occurrence(field=h, conjugate=True), Occurrence(field=h)]
    p = potential
    if phase is Phase.unbroken:
        return {
            "H2": (hh, p.mu_h2_gev2, 2),
            "H4": (hh + hh, -p.lambda_h, 0),
            "S2": (fields(s, 2), -p.mu_s2_gev2 / 2, 2),
            "S4": (fields(s, 4), -p.lambda_s / 4, 0),
            "HS": (hh + fields(s, 2), -p.lambda_hs / 2, 0),
        }
    return {
        "h2": (fields(h, 2), -(p.higgs_mass_gev**2) / 2, 2),
        "h3": (fields(h, 3), -p.lambda_h * p.v_gev, 1),
        "h4": (fields(h, 4), -p.lambda_h / 4, 0),
        "S2": (fields(s, 2), -(p.singlet_mass_gev**2) / 2, 2),
        "S4": (fields(s, 4), -p.lambda_s / 4, 0),
        "hSS": (fields(h, 1) + fields(s, 2), -p.lambda_hs * p.v_gev / 2, 1),
        "hhSS": (fields(h, 2) + fields(s, 2), -p.lambda_hs / 4, 0),
    }


def resolved_spec(spec: ModelSpec) -> ModelSpec:
    """Expand a declared complete potential, or verify every supplied scalar coefficient."""
    if spec.scalar_potential is None:
        return spec
    from adroit.parameter_space.classify import Unsupported

    potential = spec.scalar_potential.resolve()
    _fields(spec, potential)
    expected = coefficients(potential, spec.phase)
    if spec.terms:
        _verify_terms(spec, expected)
        return spec
    couplings = list(spec.couplings)
    terms = []
    for key, (fields, value, dimension) in expected.items():
        name = "potential_" + key
        if any(c.name == name for c in couplings):
            raise Unsupported(
                f"reserved derived scalar coefficient {name} conflicts with supplied coupling"
            )
        couplings.append(
            ModelCoupling(
                name=name,
                value=value,
                mass_dimension=dimension,
                justification="derived from declared complete potential, L=-V",
            )
        )
        terms.append(ModelTerm(fields=fields, lorentz="scalar", coupling=name, text=f"L=-V: {key}"))
    return spec.model_copy(update={"terms": terms, "couplings": couplings})


def _verify_terms(
    spec: ModelSpec, expected: dict[str, tuple[list[Occurrence], float, int]]
) -> None:
    from adroit.parameter_space.classify import Unsupported

    matched = set()
    for term in spec.terms:
        key = next(
            (
                name
                for name, (fields, _, _) in expected.items()
                if Counter((o.field, o.conjugate) for o in fields)
                == Counter((o.field, o.conjugate) for o in term.fields)
            ),
            None,
        )
        value = coupling_value(spec, term)
        if key is None:
            if value == 0:
                continue
            raise Unsupported(
                f"additional potential/interaction {term.text or term.coupling!r} not represented by this exact Z2 contract"
            )
        if (
            key in matched
            or term.lorentz != "scalar"
            or term.plus_hc
            or value is None
            or not math.isclose(value, expected[key][1], rel_tol=1e-10, abs_tol=1e-12)
        ):
            raise Unsupported(
                f"scalar coefficient {key} inconsistent with the declared complete potential"
            )
        scaled = evaluate_expression(term.coupling, symbol_table(spec), scale=2)
        if not math.isclose(scaled, value * 2 ** expected[key][2], rel_tol=1e-10, abs_tol=0):
            raise Unsupported(f"scalar coefficient {key} has inconsistent mass dimension")
        matched.add(key)
    if matched != expected.keys():
        raise Unsupported(
            f"declared potential terms incomplete: missing {sorted(expected.keys() - matched)}"
        )


def _fields(spec: ModelSpec, p: ResolvedScalarPotential) -> None:
    from adroit.parameter_space.classify import Unsupported

    dark = [f for f in spec.fields if f.role is FieldRole.dark_matter]
    if len(dark) != 1 or dark[0].name != p.singlet_field:
        raise Unsupported("scalar potential requires exactly its declared real singlet DM field")
    s, h = spec.field(p.singlet_field), spec.field(p.higgs_field)
    if (
        s.spin != 0
        or not s.self_conjugate
        or s.dark_parity != -1
        or s.generations != 1
        or s.charges.su3 != "1"
        or s.charges.su2 != 1
        or s.charges.hypercharge
        or s.charges.electric_charge
        or any(s.charges.extra.values())
    ):
        raise Unsupported("complete Z2 scalar potential needs one real, neutral, odd singlet")
    if h.dark_parity == -1:
        raise Unsupported("the Higgs must be even under the declared unbroken dark Z2")
    if (
        h.role is not FieldRole.standard_model
        or h.spin != 0
        or h.generations != 1
        or h.charges.su3 != "1"
        or any(h.charges.extra.values())
    ):
        raise Unsupported("declared Higgs field must be the SM scalar with one generation")
    if spec.phase is Phase.unbroken:
        if h.charges.su2 != 2 or h.self_conjugate or h.charges.hypercharge != 0.5:
            raise Unsupported("unbroken potential needs H doublet with Y=1/2 and H†H")
    elif (
        h.charges.su2 != 1
        or h.charges.electric_charge
        or h.charges.hypercharge
        or not h.self_conjugate
    ):
        raise Unsupported("broken potential needs the real neutral physical Higgs field")
    for field, mass in ((s, p.singlet_mass_gev), (h, p.higgs_mass_gev)):
        if field.mass_gev is not None and not math.isclose(
            field.mass_gev, mass, rel_tol=1e-10, abs_tol=0
        ):
            raise Unsupported(
                f"supplied {field.name} mass {field.mass_gev} conflicts with potential-derived {mass}"
            )
    if any(f.role is FieldRole.mediator or (f.role is FieldRole.other) for f in spec.fields):
        raise Unsupported(
            "extra mediator/field content is outside the complete Higgs-plus-singlet potential contract"
        )
