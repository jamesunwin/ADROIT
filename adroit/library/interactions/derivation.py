"""A derivation: a model's quark-level Wilson coefficients as formulas, and their checks (DM8).

The one step of Path 1 that may need a language model is to derive, from a
``ModelSpec``, the coefficients of DirectDM's quark-level operators. A
``Derivation`` holds them as formulas in the model's couplings and masses
(and named Standard Model constants). Every number then comes from this
module: the formulas are parsed by SymPy against a closed symbol table and
evaluated. A symbol the table does not know is an error, so a derivation
cannot slip in an unstated input.

Checks, in the plan's order of weight:
1. **Dimensions.** Scaling every mass by λ must scale a coefficient of an
   operator of dimension d by λ^{4−d} (DirectDM's Ĉ = C/Λ^{d−4}).
2. **Known limits and the library** (``matching``, ``nr_projection``).
3. **A second, independent derivation,** compared numerically at random
   parameter points (``compare``), up to one overall sign, and at the
   nucleon level after DirectDM.
"""

from __future__ import annotations

import math
import re

import numpy as np
import sympy
from pydantic import Field

from adroit.core.model_spec import ModelSpec
from adroit.core.state import StrictModel
from adroit.library.interactions import matching, quark_level
from adroit.library.interactions.quark_level import DMType, QuarkLevelModel

# Standard Model constants a formula may use: (value, mass dimension). PDG-style values; the quark masses are the
# inputs, not the kinematics (``kinematics.KINEMATIC_MASSES``): m_b and m_c the MS-bar m̄_q(m̄_q) (they run from
# there: ``constraints.higgs``), m_u, m_d, m_s the MS-bar masses at 2 GeV, m_t and the leptons' pole masses.
STANDARD_MODEL = {
    "v": (246.22, 1), "m_h": (125.25, 1), "m_W": (80.37, 1), "m_Z": (91.1876, 1),
    "G_F": (1.1663787e-5, -2), "e": (math.sqrt(4 * math.pi / 137.035999084), 0),
    "alpha": (1 / 137.035999084, 0), "s_w2": (0.23121, 0), "pi": (math.pi, 0),
    "m_u": (0.00216, 1), "m_d": (0.00467, 1), "m_s": (0.0934, 1), "m_c": (1.27, 1),
    "m_b": (4.18, 1), "m_t": (172.5, 1), "m_e": (0.000511, 1), "m_mu": (0.10566, 1),
    "m_tau": (1.77686, 1),
}
COEFFICIENT_DIMENSION = re.compile(r"^C([567])")
AGREEMENT = 0.01                        # two derivations agree within 1%, coefficient by coefficient


class WilsonTerm(StrictModel):
    """One Wilson coefficient: DirectDM's name and a formula for its value (in GeV units)."""

    name: str
    expression: str
    note: str = ""


class Derivation(StrictModel):
    """A model's quark-level coefficients, with what was dropped and why."""

    model_name: str
    dm_type: DMType = DMType.dirac
    flavours: int = Field(default=5, ge=3, le=5)
    terms: list[WilsonTerm]
    library_card: str = ""                          # a card the model is equivalent to, if any
    library_values: dict[str, str] = Field(default_factory=dict)   # its parameters, as formulas
    dropped: list[str] = Field(default_factory=list)
    justifications: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    derived_by: str = ""                            # a model id, or "user"


def symbol_table(model: ModelSpec, overrides: dict[str, float] | None = None,
                 standard: dict[str, float] | None = None) -> dict[str, tuple[float, int]]:
    """Every symbol a formula may use: Standard Model constants (``standard`` replaces some of their values; the
    model's own couplings still take precedence), the couplings, m_<field> masses, then ``overrides``."""
    table = dict(STANDARD_MODEL)
    for name, value in (standard or {}).items():
        table[name] = (value, STANDARD_MODEL[name][1])
    for c in model.couplings:
        if c.value is not None:
            table[c.name] = (c.value, c.mass_dimension)
    for f in model.fields:
        if f.mass_gev is not None:
            table[f"m_{f.name}"] = (f.mass_gev, 1)
    for name, value in (overrides or {}).items():
        table[name] = (value, table.get(name, (0.0, 0))[1])
    return table


FUNCTIONS = {"sqrt": sympy.sqrt, "exp": sympy.exp, "log": sympy.log, "abs": sympy.Abs,
             "sin": sympy.sin, "cos": sympy.cos, "tan": sympy.tan, "atan": sympy.atan}
_TOKEN = re.compile(r"\s*(?:(\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)|([A-Za-z][A-Za-z0-9_]*)|(\*\*|[-+*/()]))")


def _check_tokens(expression: str, table: dict) -> None:
    """Only numbers, arithmetic, parentheses, known symbols and FUNCTIONS: the formula is
    untrusted text and SymPy evaluates what it parses."""
    position = 0
    stripped = expression.rstrip()
    while position < len(stripped):
        match = _TOKEN.match(stripped, position)
        if not match or match.end() == position:
            raise ValueError(f"unexpected text at {stripped[position:position + 12]!r} in {expression!r}")
        name = match.group(2)
        if name and name not in table and name not in FUNCTIONS:
            raise ValueError(f"unknown symbol {name!r} in {expression!r}")
        position = match.end()


class NotFinite(ValueError):
    """A formula with no finite value at the stated point: a pole, 0/0, or an overflow (the auditor's UO-02)."""


def evaluate_expression(expression: str, table: dict[str, tuple[float, int]], scale: float = 1.0,
                        allow_complex: bool = False) -> float | complex:
    """The formula's value, every mass scaled by ``scale`` (for the dimension check). ``allow_complex`` (G1's terms,
    whose ``+ h.c.`` makes the Lagrangian real) admits the imaginary unit I and a complex value."""
    from adroit.core.arithmetic import ArithmeticRefused, check_formula
    try:
        check_formula(expression)
    except ArithmeticRefused as error:
        raise ValueError(str(error)) from None
    _check_tokens(expression, {**table, "I": (1.0, 0)} if allow_complex else table)
    symbols = {name: sympy.Symbol(name) for name in table}
    extra = {"I": sympy.I} if allow_complex else {}
    parsed = sympy.sympify(expression, locals={**symbols, **FUNCTIONS, **extra})
    unknown = {str(s) for s in parsed.free_symbols} - set(table)
    if unknown:
        raise ValueError(f"unknown symbols {sorted(unknown)} in {expression!r}")
    values = {symbols[n]: v * scale ** d for n, (v, d) in table.items() if symbols[n] in parsed.free_symbols}
    # exact substitution first (the auditor's UO-02): a pole such as 1/(m_Zp² − 4m_χ²) at m_Zp = 2m_χ, or 0/0, is complex
    # infinity or undefined there, where evalf(subs=…) returns a large finite artefact (−2.2 × 10¹²⁷)
    exact = parsed.xreplace({k: sympy.Float(v) for k, v in values.items()})
    if exact.has(sympy.zoo, sympy.nan, sympy.oo, -sympy.oo) or exact.is_finite is False:
        raise NotFinite(f"{expression!r} is not finite at these values (a pole or an undefined value)")
    result = complex(parsed.evalf(subs=values))
    if not (math.isfinite(result.real) and math.isfinite(result.imag)):
        raise NotFinite(f"{expression!r} is not finite at these values ({result})")
    if allow_complex:
        return result
    if abs(result.imag) > 1e-12 * max(abs(result.real), 1e-300):
        raise ValueError(f"{expression!r} is complex: {result}")
    return result.real


def evaluate(derivation: Derivation, model: ModelSpec, overrides: dict[str, float] | None = None) -> QuarkLevelModel:
    """The derivation as DirectDM input, its formulas evaluated."""
    table = symbol_table(model, overrides)
    coefficients = {t.name: evaluate_expression(t.expression, table) for t in derivation.terms}
    return QuarkLevelModel(name=derivation.model_name, dm_type=derivation.dm_type,
                           flavours=derivation.flavours, coefficients=coefficients,
                           dropped=list(derivation.dropped))


def dimension_problems(derivation: Derivation, model: ModelSpec) -> list[str]:
    """Coefficients that do not scale as λ^{4−d} when every mass is scaled by λ."""
    table = symbol_table(model)
    out = []
    for t in derivation.terms:
        match = COEFFICIENT_DIMENSION.match(t.name)
        if not match:
            out.append(f"{t.name}: not a DirectDM coefficient name")
            continue
        expected = 4 - int(match.group(1))
        base = evaluate_expression(t.expression, table)
        scaled = evaluate_expression(t.expression, table, scale=2.0)
        if base == 0.0:
            continue
        power = math.log(abs(scaled / base)) / math.log(2.0)
        if abs(power - expected) > 1e-6:
            out.append(f"{t.name} = {t.expression}: scales as mass^{power:.3g}, needs mass^{expected}")
    return out


class Comparison(StrictModel):
    """Two derivations compared at random parameter points.

    Up to one overall sign: reversing every coefficient leaves every rate unchanged
    (a rate is quadratic in them), and conventions (the sign of e, of the Maxwell
    equation) can reverse them all.
    """

    points: int
    max_relative_difference: float             # coefficient by coefficient, at the better overall sign
    by_coefficient: dict[str, float]           # the largest relative difference of each
    only_in_first: list[str] = Field(default_factory=list)
    only_in_second: list[str] = Field(default_factory=list)
    sign: int = 1                              # −1: the second agrees with every coefficient reversed
    nucleon_difference: float | None = None    # after DirectDM, in matching's weighted measure

    @property
    def agree_coefficients(self) -> bool:
        """Within AGREEMENT for every coefficient, and the same coefficients."""
        return (self.max_relative_difference <= AGREEMENT and not self.only_in_first
                and not self.only_in_second)

    @property
    def agree(self) -> bool:
        """What a recoil can tell: at the nucleon level if computed, else coefficient by coefficient."""
        if self.nucleon_difference is not None:
            return self.nucleon_difference <= AGREEMENT
        return self.agree_coefficients


def random_points(model: ModelSpec, points: int, seed: int) -> list[dict[str, float]]:
    """Parameter points: each coupling ×10^U(−1,1) with its sign kept, each mass ×10^U(−0.3,0.3)."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(points):
        point = {c.name: c.value * 10 ** rng.uniform(-1, 1) for c in model.couplings if c.value}
        point.update({f"m_{f.name}": f.mass_gev * 10 ** rng.uniform(-0.3, 0.3)
                      for f in model.fields if f.mass_gev})
        out.append(point)
    return out


def _worst(pairs: list[tuple[dict, dict]], names: set[str], sign: int) -> dict[str, float]:
    worst: dict[str, float] = {}
    for a, b in pairs:
        for name in names:
            scale = max(abs(a[name]), abs(b[name]), 1e-300)
            worst[name] = max(worst.get(name, 0.0), abs(a[name] - sign * b[name]) / scale)
    return worst


def nucleon_difference(first: list[QuarkLevelModel], second: list[QuarkLevelModel],
                       masses_gev: list[float]) -> float:
    """The largest relative difference after DirectDM, in matching's measure, at the better overall sign."""
    worst = {1: 0.0, -1: 0.0}
    for a, b, mass in zip(first, second, masses_gev):
        va = matching.vector(quark_level.to_interaction(a, mass)[1])
        vb = matching.vector(quark_level.to_interaction(b, mass)[1])
        scale = max(np.linalg.norm(va), np.linalg.norm(vb), 1e-300)
        for sign in worst:
            worst[sign] = max(worst[sign], float(np.linalg.norm(va - sign * vb) / scale))
    return min(worst.values())


def compare(first: Derivation, second: Derivation, model: ModelSpec, points: int = 6,
            seed: int = 20261001, nucleon: bool = False) -> Comparison:
    """The largest relative difference of each coefficient over random parameter points.

    With ``nucleon``, also the difference of the nucleon-level interactions DirectDM gives
    (at each point's dark matter mass), which decides agreement: coefficients that cannot
    reach a nuclear recoil, or reach it below 1%, then do not stop a run.
    """
    a_names, b_names = {t.name for t in first.terms}, {t.name for t in second.terms}
    grid = random_points(model, points, seed)
    a_models = [evaluate(first, model, point) for point in grid]
    b_models = [evaluate(second, model, point) for point in grid]
    pairs = [(a.coefficients, b.coefficients) for a, b in zip(a_models, b_models)]
    by_sign = {sign: _worst(pairs, a_names & b_names, sign) for sign in (1, -1)}
    sign = min(by_sign, key=lambda s: (max(by_sign[s].values(), default=0.0), -s))
    difference = None
    if nucleon:
        dm = model.dark_matter
        masses = [point.get(f"m_{dm.name}", dm.mass_gev) for point in grid]
        difference = nucleon_difference(a_models, b_models, masses)
    return Comparison(points=points, max_relative_difference=max(by_sign[sign].values(), default=0.0),
                      by_coefficient=by_sign[sign], only_in_first=sorted(a_names - b_names),
                      only_in_second=sorted(b_names - a_names), sign=sign, nucleon_difference=difference)
