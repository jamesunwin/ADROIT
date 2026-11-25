"""A model as a physicist reads it (the owner, 2026-10-13): its field content as a table and its Lagrangian in the
usual notation, as one LaTeX document for the workbench to typeset.

Pure functions of the ``ModelSpec``. The TeX stored with a model revision (``tex.render``) is unchanged; this is a
view of the same data. Every name is reduced to letters, digits and known Greek letters before it reaches TeX, so a
field or coupling name cannot inject TeX commands.

Each term is written from its Lorentz label (``ModelTerm.lorentz``) with the coupling as its full coefficient in L:
``scalar`` ψ̄₁ψ₂ (or a product of bosons), ``pseudoscalar`` ψ̄₁iγ⁵ψ₂, ``vector`` ψ̄₁γ^μψ₂ V_μ, ``axial``
ψ̄₁γ^μγ⁵ψ₂ V_μ, ``chiral`` ψ_a ψ_b for two left-handed Weyl spinors or V_μ ψ_a†σ̄^μψ_b, ``tensor`` and ``dipole``
ψ̄₁σ^{μν}ψ₂ V_{μν}, ``anapole`` ψ̄₁γ^μγ⁵ψ₂ ∂^ν V_{μν}, ``charge_radius`` ψ̄₁γ^μψ₂ ∂^ν V_{μν}, ``scalar_current``
V_μ φ†i∂↔^μφ and ``kinetic_mixing`` V_{μν}W^{μν}. Anything else is shown as 𝒪_label(fields). Gauge and flavour
indices are left implicit (contracted to a singlet).
"""

from __future__ import annotations

import ast
import re
from fractions import Fraction

from adroit.core.model_spec import STANDARD_MODEL_FIELDS, FieldRole, ModelField, ModelSpec, ModelTerm, Phase

GREEK = {g: "\\" + g for g in ("alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa",
                               "lambda", "mu", "nu", "xi", "pi", "rho", "sigma", "tau", "upsilon", "phi", "chi", "psi",
                               "omega", "Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Upsilon", "Phi",
                               "Psi", "Omega")}
GREEK.update({"lam": r"\lambda", "eps": r"\epsilon", "kap": r"\kappa"})
UNICODE = dict(zip("αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΦΨΩ",
                   ("alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa", "lambda",
                    "mu", "nu", "xi", "pi", "rho", "sigma", "tau", "upsilon", "phi", "chi", "psi", "omega", "Gamma",
                    "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Phi", "Psi", "Omega")))
SM_SYMBOLS = {"uR": "u_R", "dR": "d_R", "eR": "e_R", "qL": "Q_L", "lL": "L_L", "Q": "Q", "L": "L", "mu": r"\mu",
              "tau": r"\tau", "nu": r"\nu", "nu_e": r"\nu_e", "nu_mu": r"\nu_\mu", "nu_tau": r"\nu_\tau",
              "gamma": r"\gamma", "Wa": "W^a"}
ROLES = {FieldRole.dark_matter: "dark matter", FieldRole.mediator: "mediator",
         FieldRole.standard_model: "Standard Model", FieldRole.other: "other"}
GAMMA = {"scalar": "", "pseudoscalar": r"i\gamma^5", "vector": r"\gamma^\mu", "axial": r"\gamma^\mu\gamma^5",
         "tensor": r"\sigma^{\mu\nu}", "dipole": r"\sigma^{\mu\nu}", "anapole": r"\gamma^\mu\gamma^5",
         "charge_radius": r"\gamma^\mu"}


def _clean(text: str) -> str:
    """Letters and digits only, Greek letters spelled out."""
    return re.sub(r"[^A-Za-z0-9_]", "", "".join(UNICODE.get(c, c) for c in text))


def _word(part: str) -> str:
    """One name part: a Greek letter, a single italic letter, a letter with an index (H2 → H₂), or upright text."""
    if part in GREEK:
        return GREEK[part]
    indexed = re.fullmatch(r"([A-Za-z])(\d+[A-Za-z]*|[a-oq-z])", part)
    if indexed:
        return indexed.group(1) + "_{" + indexed.group(2) + "}"
    return part if len(part) == 1 or part.isdigit() else r"\mathrm{" + part + "}"


def symbol(name: str) -> str:
    """A field or coupling name as a symbol: ``chi`` → χ, ``g_chi`` → g_χ, ``F5P`` → F_{5P}, ``Zp`` → Z′,
    ``m2_F5P_F5M`` → m_{2,F5P,F5M}."""
    if name in SM_SYMBOLS:
        return SM_SYMBOLS[name]
    head, *rest = [p for p in _clean(name).split("_") if p] or ["?"]
    prime = bool(re.fullmatch(r"[A-Z]p", head)) or "prime" in rest
    rest = [p for p in rest if p != "prime"]
    match = re.fullmatch(r"([A-Za-z]+?)(\d+[A-Za-z]*)", head) if head not in GREEK else None
    base, index = (match.group(1), [match.group(2)]) if match else (head[0] if prime else head, [])
    subscript = [*index, *(_word(p) for p in rest)]
    out = (base if len(base) == 1 else GREEK.get(base, r"\mathrm{" + base + "}")) + ("'" if prime else "")
    if not prime and not index and len(base) == 2 and re.fullmatch(r"[A-Z][a-oq-z]", base):
        out = base[0]                                    # Xd → X_d
        subscript = [base[1], *subscript]
    if subscript:
        out += "_{" + ",".join(subscript) + "}"
    return out


def coefficient(text: str) -> str:
    """A coupling's arithmetic (names, numbers, + − × /, powers, sqrt, exp, log, abs) in the usual notation."""
    try:
        return _expression(ast.parse(text, mode="eval").body)
    except (SyntaxError, ValueError):
        return symbol(text)


def _expression(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return symbol(node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return f"{node.value:g}"
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        inner = _expression(node.operand)
        if isinstance(node.operand, ast.BinOp) and isinstance(node.operand.op, (ast.Add, ast.Sub)):
            inner = r"\left(" + inner + r"\right)"
        return ("-" if isinstance(node.op, ast.USub) else "") + inner
    if isinstance(node, ast.BinOp):
        a, b = _expression(node.left), _expression(node.right)
        if isinstance(node.op, ast.Div):
            return r"\frac{" + a + "}{" + b + "}"
        if isinstance(node.op, ast.Pow):
            return "{" + a + "}^{" + b + "}"
        if isinstance(node.op, ast.Mult):
            wrap = [r"\left(" + x + r"\right)" if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub))
                    else x for x, n in ((a, node.left), (b, node.right))]
            return wrap[0] + r"\," + wrap[1]
        if isinstance(node.op, (ast.Add, ast.Sub)):
            return a + (" + " if isinstance(node.op, ast.Add) else " - ") + b
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and len(node.args) == 1 \
            and node.func.id in ("sqrt", "exp", "log", "abs"):
        x = _expression(node.args[0])
        return {"sqrt": r"\sqrt{" + x + "}", "abs": r"\left|" + x + r"\right|"}.get(
            node.func.id, "\\" + node.func.id + r"\left(" + x + r"\right)")
    raise ValueError("outside the arithmetic view")


def kind(field: ModelField) -> str:
    """The field's type in words: real or complex scalar, Dirac, Majorana or Weyl fermion, real or complex vector."""
    if field.spin == 0:
        return "real scalar" if field.self_conjugate else "complex scalar"
    if field.spin == 0.5:
        if field.chirality:
            return ("left" if field.chirality == "L" else "right") + "-handed Weyl fermion"
        return "Majorana fermion" if field.self_conjugate else "Dirac fermion"
    if field.spin == 1:
        return "real vector" if field.self_conjugate else "complex vector"
    return f"spin {field.spin:g}"


def _charged(field: ModelField, phase: Phase) -> bool:
    c = field.charges
    abelian = c.hypercharge if phase is Phase.unbroken else c.electric_charge
    return c.su3 != "1" or c.su2 > 1 or abelian != 0 or any(c.extra.values())


def _number(value: float, inline: bool = False) -> str:
    """A charge as an integer or a fraction (n/d in a subscript, a small fraction otherwise)."""
    f = Fraction(value).limit_denominator(12)
    if abs(float(f) - value) > 1e-9:
        return f"{value:g}"
    if f.denominator == 1:
        return str(f.numerator)
    sign = "-" if f < 0 else ""
    return sign + (f"{abs(f.numerator)}/{f.denominator}" if inline else rf"\tfrac{{{abs(f.numerator)}}}{{{f.denominator}}}")


def _representation(field: ModelField, phase: Phase) -> str:
    c = field.charges
    colour = r"\bar{3}" if c.su3 == "3bar" else c.su3
    if phase is Phase.broken:
        return colour
    return f"({colour},{c.su2})_{{{_number(c.hypercharge, inline=True)}}}"


def _occurrence(spec: ModelSpec, name: str, conjugate: bool) -> str:
    field = spec.field(name)
    s = symbol(name)
    if not conjugate:
        return s
    if field.spin == 0.5 and not field.chirality:
        return r"\overline{" + s + "}"
    return s + r"^\dagger"


def _lower(sym: str, index: str) -> str:
    """A lower index on a symbol, braced if the symbol has one already (X_d → {X_d}_μ, not a double subscript)."""
    return ("{" + sym + "}" if "_" in sym else sym) + index


def _strength(name: str) -> str:
    return r"F_{\mu\nu}" if name in ("A", "gamma") else _lower(symbol(name), r"_{\mu\nu}")


def term(spec: ModelSpec, t: ModelTerm) -> str:
    """One term of L: its coefficient times its operator (with + h.c. if stated)."""
    by_spin: dict[float, list[tuple[str, bool]]] = {0.0: [], 0.5: [], 1.0: []}
    for occ in t.fields:
        by_spin.setdefault(spec.field(occ.field).spin, []).append((occ.field, occ.conjugate))
    fermions, scalars, vectors = by_spin[0.5], by_spin[0.0], by_spin[1.0]
    operator = _operator(spec, t.lorentz, fermions, scalars, vectors)
    if operator is None or len(by_spin) > 3:
        names = ",".join(_occurrence(spec, o.field, o.conjugate) for o in t.fields)
        operator = r"\mathcal{O}_{\mathrm{" + (_clean(t.lorentz).replace("_", " ") or "term") + "}}(" + names + ")"
    c = coefficient(t.coupling)
    if " + " in c or " - " in c[1:]:
        c = r"\left(" + c + r"\right)"
    return c + r"\," + operator + (r" + \mathrm{h.c.}" if t.plus_hc else "")


def _scalar_product(spec: ModelSpec, scalars: list[tuple[str, bool]]) -> str:
    """Bosons multiplied: a field met with and without conjugation as (φ†φ), repeats as powers."""
    out, counts = [], {}
    for item in scalars:
        counts[item] = counts.get(item, 0) + 1
    for (name, conj), n in counts.items():
        if conj and (name, False) in counts:
            continue
        pair = min(n, counts.get((name, True), 0)) if not conj else 0
        if pair:
            s = symbol(name)
            out.append(r"(" + s + r"^\dagger " + s + ")" + (f"^{pair}" if pair > 1 else ""))
        rest = n - pair
        if rest:
            occurrence = _occurrence(spec, name, conj)
            if rest > 1:
                occurrence = ("(" + occurrence + ")" if "dagger" in occurrence else "{" + occurrence + "}") + f"^{rest}"
            out.append(occurrence)
    return r"\,".join(out)


def _operator(spec: ModelSpec, label: str, fermions, scalars, vectors) -> str | None:
    bosons = _scalar_product(spec, scalars)
    if label == "kinetic_mixing" and len(vectors) == 2 and not fermions and not scalars:
        return _strength(vectors[0][0]) + _strength(vectors[1][0]).replace(r"_{\mu\nu}", r"^{\mu\nu}")
    if label == "scalar_current" and len(vectors) == 1 and len(scalars) == 2 and not fermions:
        s = symbol(scalars[-1][0])
        return _lower(symbol(vectors[0][0]), r"_\mu") + r"\, " + s + r"^\dagger i\overleftrightarrow{\partial^\mu} " + s
    if len(fermions) == 2:
        return _bilinear(spec, label, fermions, vectors, bosons)
    if len(fermions) == 4 and not vectors and label in GAMMA and "nu" not in GAMMA[label]:
        lower = GAMMA[label].replace("^\\mu", "_\\mu")
        return (_sandwich(spec, fermions[:2], GAMMA[label]) + _sandwich(spec, fermions[2:], lower)) + \
            (r"\," + bosons if bosons else "")
    if not fermions and label == "scalar" and len(vectors) in (0, 2):
        lorentz = _lower(symbol(vectors[0][0]), r"_\mu") + " " + symbol(vectors[1][0]) + r"^\mu" if vectors else ""
        return r"\,".join(x for x in (lorentz, bosons) if x)
    return None


def _sandwich(spec: ModelSpec, pair: list[tuple[str, bool]], gamma: str) -> str:
    (a, ca), (b, cb) = pair
    if not ca and cb:
        (a, ca), (b, cb) = (b, cb), (a, ca)
    left = r"\overline{" + symbol(a) + "}" if ca or not spec.field(a).chirality else symbol(a)
    return "(" + left + (" " + gamma + " " if gamma else " ") + _occurrence(spec, b, False) + ")"


def _bilinear(spec: ModelSpec, label: str, fermions, vectors, bosons: str) -> str | None:
    weyl = all(spec.field(f).chirality for f, _ in fermions)
    tail = r"\," + bosons if bosons else ""
    if weyl and label in ("chiral", "scalar") and not vectors:
        return " ".join(_occurrence(spec, f, c) for f, c in fermions) + tail
    if label == "chiral" and not vectors and any(c for _, c in fermions):
        # a Weyl and a four-component fermion: ψ̄ χ, with χ^c for a conjugated second field
        (a, _), (b, cb) = fermions if fermions[0][1] else fermions[::-1]
        return r"\overline{" + symbol(a) + r"}\, " + symbol(b) + ("^c" if cb else "") + tail
    if weyl and label in ("chiral", "vector") and len(vectors) == 1:
        (a, ca), (b, cb) = fermions if fermions[0][1] or not fermions[1][1] else fermions[::-1]
        return (_lower(symbol(vectors[0][0]), r"_\mu") + r"\, " + symbol(a) + r"^\dagger \bar\sigma^\mu " + symbol(b)
                + tail)
    if weyl or label not in GAMMA:
        return None
    body = _sandwich(spec, fermions, GAMMA[label])[1:-1]
    if label in ("vector", "axial") and len(vectors) == 1:
        return body + r"\, " + _lower(symbol(vectors[0][0]), r"_\mu") + tail
    if label in ("tensor", "dipole") and len(vectors) == 1:
        return body + r"\, " + _strength(vectors[0][0]) + tail
    if label in ("anapole", "charge_radius") and len(vectors) == 1:
        return body + r"\, \partial^\nu " + _strength(vectors[0][0]).replace(r"_{\mu\nu}", r"_{\mu\nu}") + tail
    if label in ("scalar", "pseudoscalar") and not vectors:
        return body + tail
    return None


def _has_mass_term(spec: ModelSpec, name: str) -> bool:
    """Whether L already holds a bilinear of this field (the generator writes masses as terms)."""
    return any(len(t.fields) == 2 and t.lorentz in ("scalar", "chiral", "pseudoscalar")
               and name in {o.field for o in t.fields} for t in spec.terms)


def kinetic(spec: ModelSpec, field: ModelField) -> str:
    """The field's free Lagrangian: its kinetic term with D_μ if it is charged, and its mass unless L holds one."""
    s, m = symbol(field.name), "m_{" + symbol(field.name) + "}"
    d = "D" if _charged(field, spec.phase) else r"\partial"
    massive = field.mass_gev is not None and not _has_mass_term(spec, field.name)
    if field.spin == 0.5 and field.chirality:
        return "i " + s + r"^\dagger \bar\sigma^\mu " + d + r"_\mu " + s
    if field.spin == 0.5:
        half = r"\tfrac12 " if field.self_conjugate else ""
        inside = r"i\gamma^\mu " + d + r"_\mu" + (" - " + m if massive else "")
        return half + r"\overline{" + s + r"}\left(" + inside + r"\right)" + s
    if field.spin == 0 and field.self_conjugate:
        return r"\tfrac12\, \partial_\mu " + s + r"\, \partial^\mu " + s + (
            r" - \tfrac12 " + m + "^2 " + s + "^2" if massive else "")
    if field.spin == 0:
        return (r"(" + d + r"_\mu " + s + r")^\dagger " + d + r"^\mu " + s +
                (" - " + m + "^2 " + s + r"^\dagger " + s if massive else ""))
    if field.spin == 1:
        return (r"-\tfrac14 " + _lower(s, r"_{\mu\nu}") + s + r"^{\mu\nu}" +
                (r" + \tfrac12 " + m + "^2 " + _lower(s, r"_\mu") + " " + s + r"^\mu" if massive else ""))
    return r"\text{(spin " + f"{field.spin:g}" + r": not written)}"


def field_table(spec: ModelSpec) -> str:
    """The field content as a LaTeX table: symbol, type, role, gauge representation, Q, Z₂ parity and mass."""
    unbroken = spec.phase is Phase.unbroken
    rep = r"$(\mathrm{SU}(3)_c,\mathrm{SU}(2)_L)_Y$" if unbroken else r"$\mathrm{SU}(3)_c$"
    extra = sorted({k for f in spec.fields for k in f.charges.extra})
    # Above electroweak breaking Q = T₃ + Y differs across a multiplet: the representation says it all.
    head = ["Field", "Type", "Role", rep, *([] if unbroken else ["$Q$"]), r"$Z_2$",
            *[r"$\mathrm{U}(1)_{" + symbol(k) + "}$" for k in extra], "Mass (GeV)"]
    rows = []
    for f in spec.fields:
        stated = f.dark_parity if f.dark_parity is not None else (1 if f.role is FieldRole.standard_model else None)
        parity = {-1: "$-$", 1: "$+$"}.get(stated, "?")
        generations = f" ($\\times {f.generations}$)" if f.generations > 1 else ""
        rows.append([f"${symbol(f.name)}$", kind(f) + generations, ROLES[f.role], f"${_representation(f, spec.phase)}$",
                     *([] if unbroken else [f"${_number(f.charges.electric_charge)}$"]), parity,
                     *[f"${_number(f.charges.extra.get(k, 0.0))}$" for k in extra],
                     f"{f.mass_gev:g}" if f.mass_gev is not None else "--"])
    spec_cols = "lllc" + ("" if unbroken else "c") + "c" * (1 + len(extra)) + "r"
    lines = [r"\begin{tabular}{" + spec_cols + "}", r"\hline", " & ".join(head) + r" \\", r"\hline"]
    lines += [" & ".join(r) + r" \\" for r in rows] + [r"\hline", r"\end{tabular}"]
    return "\n".join(lines)


def lagrangian(spec: ModelSpec) -> str:
    """L = L_SM + L_kin + L_int, one term per line, as an align* environment."""
    new = [f for f in spec.fields if f.role is not FieldRole.standard_model and f.name not in STANDARD_MODEL_FIELDS]
    lines = [r"\mathcal{L} &= \mathcal{L}_{\rm SM} + \mathcal{L}_{\rm kin} + \mathcal{L}_{\rm int}"]
    for label, parts in ((r"\mathcal{L}_{\rm kin}", [kinetic(spec, f) for f in new]),
                         (r"\mathcal{L}_{\rm int}", [term(spec, t) for t in spec.terms])):
        if not parts:
            empty = r"\text{no new fields}" if "kin" in label else (
                r"\text{no interaction terms in the model's data (its gauge interactions are in } \mathcal{L}_{\rm kin}"
                r"\text{; a portal class may add its own)}")
            lines.append(label + r" &: " + empty)
            continue
        lines.append(label + " &= " + parts[0])
        lines += [r"&\quad " + (p if p.startswith("-") else "+ " + p) for p in parts[1:]]
    # an aligned block placed at the left margin (a display would centre it in the page's width)
    return (r"\par\smallskip\noindent\hspace*{1.5em}$\displaystyle\begin{aligned}" + "\n" + " \\\\[2pt]\n".join(lines)
            + "\n" + r"\end{aligned}$\par\smallskip")


def couplings(spec: ModelSpec) -> str:
    """The couplings' values, and those still without one."""
    given = [f"${symbol(c.name)} = {c.value:g}$" for c in spec.couplings if c.value is not None]
    missing = [f"${symbol(c.name)}$" for c in spec.couplings if c.value is None]
    out = []
    if given:
        out.append(r"\textbf{Couplings:} " + ", ".join(given) + ".")
    if missing:
        out.append(r"\textbf{No value yet:} " + ", ".join(missing) + ".")
    return r"\par\smallskip ".join(out)


def document(spec: ModelSpec) -> str:
    """The whole view as a standalone LaTeX document: the field content, the Lagrangian and the couplings."""
    phase = "above electroweak symmetry breaking" if spec.phase is Phase.unbroken else "below electroweak symmetry breaking"
    return "\n".join([
        r"\documentclass[12pt,border=10pt,varwidth=19cm]{standalone}",
        r"\usepackage{amsmath,amssymb}",
        r"\begin{document}",
        r"\textbf{Field content} (" + phase + r")\par\smallskip",
        field_table(spec),
        r"\par\bigskip\textbf{Lagrangian}",
        lagrangian(spec),
        couplings(spec),
        r"\par\smallskip{\footnotesize Gauge and flavour indices are contracted to singlets; $D_\mu$ is the gauge-covariant "
        r"derivative; each coefficient is the full coefficient of its operator in $\mathcal{L}$.}",
        r"\end{document}",
    ])
