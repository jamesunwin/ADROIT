"""R1: parameter expressions are plain arithmetic, read without executing them."""

import math

import pytest

from adroit.core import arithmetic
from adroit.core.arithmetic import ArithmeticRefused, evaluate, parse

SLOTS = {"m_chi": 10.0, "m_med": 500.0, "g_chi": 1.0, "g_q": 0.25, "g_l": 0.0}


@pytest.mark.parametrize("expression,value", [
    ("m_chi", 10.0), ("g_chi/2", 0.5), ("m_chi + g_q", 10.25), ("125.09", 125.09), ("-0.051", -0.051),
    ("1e-05", 1e-05), ("repr", None), ("math.sqrt(2)*g_chi", math.sqrt(2)), ("math.pi*m_chi**2", math.pi * 100),
    ("2**-1", 0.5), ("+m_med - 2*(m_chi - 1)", 482.0), ("math.log10(m_med/5)", 2.0)])
def test_arithmetic_in_the_slots_is_evaluated(expression: str, value: float | None) -> None:
    if expression == "repr":                       # what resonances._reference writes into a copied portal
        expression, value = repr(0.35), 0.35
    assert evaluate(expression, SLOTS) == pytest.approx(value)


@pytest.mark.parametrize("expression", [
    '__import__("os").system("true")', "().__class__.__base__.__subclasses__()", "m_chi.__class__", "math",
    "math.sqrt", "math.sqrt + 1", "math.pi(1)", "math.sqrt(x=1)", "math.sqrt(*[4])", "math.floor(1.5)",
    "os.system(1)", "abs(-1)", "[1][0]", "(1, 2)", "m_chi if g_q else 1", "lambda: 1", "True", '"x"', "m_chi(1)",
    "m_chi // 2", "m_chi % 2", "m_chi @ 2", "~1", "not 1", "m_chi < 1", "x", "1j", "", "   ", "1" * 300,
    "+".join(["m_chi"] * 40),
    "([c for c in ().__class__.__base__.__subclasses__() if c.__name__=='_wrap_close'][0]"
    ".__init__.__globals__['mkdir']('/tmp/x'), 1/0)[1]"])
def test_anything_but_arithmetic_is_refused_before_evaluation(expression: str) -> None:
    with pytest.raises(ArithmeticRefused):
        parse(expression, frozenset(SLOTS))
    with pytest.raises(ArithmeticRefused):
        evaluate(expression, SLOTS)


@pytest.mark.parametrize("expression", ["9.0**9**9", "9**9**9", "1/0", "math.sqrt(-1)", "(-8)**(1/3)", "math.log(0)",
                                        "math.exp(1000)"])
def test_bad_arithmetic_is_an_arithmetic_error_and_stays_in_floating_point(expression: str) -> None:
    with pytest.raises(ArithmeticError):
        evaluate(expression, SLOTS)


def test_only_the_named_slots_are_known() -> None:
    assert evaluate("g_l + 1", SLOTS) == 1.0
    with pytest.raises(ArithmeticRefused):
        evaluate("m_chi", {"g_q": 1.0})


PAYLOAD = "(__import__('builtins').__setattr__('AUDIT_MARK', 1) or 1)*g_chi"


@pytest.mark.parametrize("formula", ["-lam/2", "I*(m_A**2 - m_a**2)*sin2theta/(2*v)",
                                     "atan(sin2theta/sqrt(1 - sin2theta**2))/2", "-sqrt(2)*m_q*tanb/v", "1.5e-6",
                                     "conjugate(y)*g"])
def test_a_coupling_formula_of_names_numbers_and_named_functions_is_accepted(formula: str) -> None:
    assert arithmetic.check_formula(formula) == formula


@pytest.mark.parametrize("formula", [PAYLOAD, "eval(chr(95) + chr(95))", "x.__class__", "a[0]", "'text'",
                                     "__import__", "f(x=1)", "lambda: 1", "g if x else h"])
def test_anything_sympy_would_run_as_python_is_refused(formula: str) -> None:
    """The audit's AG-1 (G12): an agent's or a paper's coupling reached ``sympy.sympify``, which runs text as Python."""
    with pytest.raises(arithmetic.ArithmeticRefused):
        arithmetic.check_formula(formula)


def test_a_model_term_refuses_such_a_coupling_and_the_audit_never_runs_it() -> None:
    import builtins

    from pydantic import ValidationError

    from adroit.core.model_spec import ModelSpec, ModelTerm, Occurrence
    from adroit.model_building import audit
    with pytest.raises(ValidationError, match="not allowed in a coupling formula"):
        ModelTerm(fields=[Occurrence(field="chi"), Occurrence(field="chi")], lorentz="scalar", coupling=PAYLOAD)
    spec = ModelSpec.model_validate({"name": "m", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 10.0}],
        "couplings": [{"name": "g_chi", "value": 1.0}]})
    term = ModelTerm.model_construct(fields=[Occurrence(field="chi"), Occurrence(field="chi")], lorentz="scalar",
                                     coupling=PAYLOAD, plus_hc=False, text="", indices="")
    assert audit.coupling_dimension(spec, term) is None and not hasattr(builtins, "AUDIT_MARK")
