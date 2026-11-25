"""Arithmetic in a few named slots, read from text without executing it.

A model file can relate a portal's parameters to the scan's slots, e.g. ``"m_chi + g_q"`` or
``"math.sqrt(2)*g_chi"``. Such text may come from a saved result or an evidence bundle, so it is
parsed into a syntax tree and evaluated by walking that tree: only numbers, the named slots, the
constants ``math.pi`` and ``math.e``, the functions of :data:`FUNCTIONS`, ``+ − × ÷ **`` and a sign
are understood. Anything else (attribute access, subscripts, comprehensions, other names or calls)
is refused before evaluation, so no code in the text can run.

All arithmetic is in floating point, so a huge power overflows at once instead of building a huge
integer.
"""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Mapping

MAX_LENGTH = 200
MAX_NODES = 64
CONSTANTS = {"pi": math.pi, "e": math.e}
FUNCTIONS = {name: getattr(math, name) for name in
             ("sqrt", "exp", "log", "log10", "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh",
              "fabs")}
BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
          ast.Pow: operator.pow}
UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class ArithmeticRefused(ValueError):
    """Text that is not plain arithmetic in the allowed slots."""


def parse(expression: str, names: frozenset[str] | set[str]) -> ast.Expression:
    """The syntax tree of ``expression``, checked against the whitelist (nothing evaluated).

    Args:
        expression: the text, e.g. ``"m_chi + g_q"``.
        names: the slots it may use.

    Raises:
        ArithmeticRefused: for anything but plain arithmetic in ``names``.
    """
    if not isinstance(expression, str) or not expression.strip() or len(expression) > MAX_LENGTH:
        raise ArithmeticRefused(f"not an arithmetic expression of at most {MAX_LENGTH} characters: {expression!r}")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as error:
        raise ArithmeticRefused(f"not arithmetic: {expression!r} ({error.msg})") from None
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_NODES:
        raise ArithmeticRefused(f"too long an expression ({len(nodes)} terms): {expression!r}")
    called = {id(n.func) for n in nodes if isinstance(n, ast.Call)}
    prefixes = {id(n.value) for n in nodes if isinstance(n, ast.Attribute)}
    for node in nodes:
        _check(node, names, expression, called, prefixes)
    return tree


def _check(node: ast.AST, names: frozenset[str] | set[str], expression: str, called: set[int],
           prefixes: set[int]) -> None:
    """Refuse one node outside the whitelist. ``called``: the ids of called nodes; ``prefixes``: of the
    names before a dot."""
    ok = isinstance(node, (ast.Expression, ast.Load, *BINARY, *UNARY))
    if isinstance(node, ast.Constant):
        ok = type(node.value) in (int, float)
    elif isinstance(node, ast.BinOp):
        ok = type(node.op) in BINARY
    elif isinstance(node, ast.UnaryOp):
        ok = type(node.op) in UNARY
    elif isinstance(node, ast.Name):
        ok = node.id == "math" if id(node) in prefixes else (node.id in names and id(node) not in called)
    elif isinstance(node, ast.Attribute):
        wanted = FUNCTIONS if id(node) in called else CONSTANTS
        ok = isinstance(node.value, ast.Name) and node.value.id == "math" and node.attr in wanted
    elif isinstance(node, ast.Call):
        ok = (isinstance(node.func, ast.Attribute) and not node.keywords
              and all(not isinstance(a, ast.Starred) for a in node.args))
    if not ok:
        raise ArithmeticRefused(f"{type(node).__name__} is not allowed in a parameter expression: {expression!r}")


FORMULA_FUNCTIONS = frozenset({"sqrt", "exp", "log", "abs", "sin", "cos", "tan", "asin", "acos", "atan", "sinh",
                               "cosh", "tanh", "conjugate", "re", "im"})
FORMULA_LENGTH = 1000


def check_formula(expression: str) -> str:
    """``expression`` unchanged if it is a coupling formula (a ModelTerm's ``coupling``), else ArithmeticRefused.

    A formula may name any symbol (the model's couplings and masses, SM constants, ``I``), but only as a plain name
    that does not start with an underscore; it may call only the functions of :data:`FORMULA_FUNCTIONS`, by name
    and without keywords; and it holds only numbers, ``+ − × ÷ **`` and a sign. A formula is later given to SymPy,
    which evaluates text as Python, so anything else (attributes, subscripts, strings, other calls such as
    ``eval(chr(95) + …)``) is refused here, before any evaluation."""
    if not isinstance(expression, str) or not expression.strip() or len(expression) > FORMULA_LENGTH:
        raise ArithmeticRefused(f"not a coupling formula of at most {FORMULA_LENGTH} characters: {expression!r}")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as error:
        raise ArithmeticRefused(f"not a formula: {expression!r} ({error.msg})") from None
    called = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    for node in ast.walk(tree):
        ok = isinstance(node, (ast.Expression, ast.Load, *BINARY, *UNARY))
        if isinstance(node, ast.Constant):
            ok = type(node.value) in (int, float)
        elif isinstance(node, ast.BinOp):
            ok = type(node.op) in BINARY
        elif isinstance(node, ast.UnaryOp):
            ok = type(node.op) in UNARY
        elif isinstance(node, ast.Name):
            ok = not node.id.startswith("_") and (id(node) not in called or node.id in FORMULA_FUNCTIONS)
        elif isinstance(node, ast.Call):
            ok = (isinstance(node.func, ast.Name) and node.func.id in FORMULA_FUNCTIONS and not node.keywords
                  and all(not isinstance(a, ast.Starred) for a in node.args))
        if not ok:
            raise ArithmeticRefused(f"{type(node).__name__} is not allowed in a coupling formula: {expression!r}")
    return expression


def evaluate(expression: str, values: Mapping[str, float]) -> float:
    """The value of ``expression`` with the slots set to ``values``.

    Raises:
        ArithmeticRefused: for anything but plain arithmetic in ``values``' names.
        ArithmeticError: for a division by zero, an overflow or a domain error.
    """
    tree = parse(expression, frozenset(values))
    try:
        result = _value(tree.body, values)
    except (ValueError, TypeError) as error:   # math's domain errors; a complex power of a negative base
        raise ArithmeticError(f"{expression!r}: {error}") from None
    if not math.isfinite(result):
        raise ArithmeticError(f"{expression!r} is not finite")
    return result


def _value(node: ast.AST, values: Mapping[str, float]) -> float:
    """Walk a checked tree."""
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        return float(values[node.id])
    if isinstance(node, ast.Attribute):
        return CONSTANTS[node.attr]
    if isinstance(node, ast.UnaryOp):
        return UNARY[type(node.op)](_value(node.operand, values))
    if isinstance(node, ast.BinOp):
        return float(BINARY[type(node.op)](_value(node.left, values), _value(node.right, values)))
    if isinstance(node, ast.Call):
        return float(FUNCTIONS[node.func.attr](*(_value(a, values) for a in node.args)))
    raise ArithmeticRefused(f"{type(node).__name__} is not allowed")
