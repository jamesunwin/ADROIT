"""A typed model in the gauge basis (G1): its fields as components, and its Lagrangian as polynomials.

The generic route works with the most general renormalisable theory's ingredients (and the
non-renormalisable terms a model states):
- **real scalar coordinates** x_k. A complex component is F_m = (x_re + i x_im)/√2. A real multiplet
  (φ_{−m} = (−1)^m φ_m*) has x₀ = F₀ and F_{±m} built from one pair. The kinetic term is then ½(∂x)² for every
  coordinate.
- **left-handed Weyl spinors** ψ_i:
  - a Dirac field χ = (ξ, η†) is two blocks, ξ in (R, Y) and η in (R̄, −Y);
  - a Majorana field is one block in its real representation;
  - a left-handed Weyl field is itself; a right-handed one enters as its conjugate.
  - A block's component η_m is the conjugate partner of ξ_m (charge −Q).
- **vectors**: B and W^A of the Standard Model (unbroken phase), the photon A and the Z (broken phase), and the
  model's new vectors.

**Colour** is unbroken, so it never mixes. A coloured multiplet is held as one colour component: its masses do
not depend on the colour index. A term's colour structure is kept for the vertices (G2), and a bilinear that
gives a mass must be colour-diagonal.

**The Lagrangian's pieces**, numerically, at the model's coupling values:
- the potential V(x), a polynomial;
- the fermion bilinears, L ⊃ −½ M_ij(x) ψ_iψ_j + h.c., each M_ij a polynomial;
- the vectors' couplings to the scalars: D_μ x = ∂_μ x − Σ_V t^V x V_μ, with t^V real and antisymmetric. These
  come from the covariant derivative for the Standard Model's gauge bosons. For a new vector they come from the
  model's explicit currents, with its explicit seagulls V V φ*φ;
- the vectors' explicit masses and kinetic mixing.

**Masses as stated.** A field's ``mass_gev`` is its Lagrangian mass, used only when no explicit two-field term
involves it:
- a scalar's m² |F|², or ½ m² F² if it is real;
- a Dirac fermion's M χ̄χ; a Majorana fermion's ½ M χ̄χ (the multiplet's invariant bilinear);
- a vector's ½ m² V².

A scalar with a vacuum value has no stated mass: its m² follows from the vacuum (``spectrum``).
"""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass, field

import numpy as np

from adroit.constraints.higgs import M_H         # 125.09 GeV: the library's Higgs, which its widths are anchored to
from adroit.core.model_spec import FieldRole, ModelField, ModelSpec, ModelTerm, Phase
from adroit.model_building.indices import Contraction, contraction, su2_generators, su2_metric

Poly = dict[tuple[int, ...], complex]          # sorted coordinate indices (with repetition) → coefficient

V_EW = 246.21965                               # (√2 G_F)^(−1/2), GeV
M_W, M_Z = 80.37, 91.1876                        # the SM's inputs (G_F scheme; ADROIT's STANDARD_MODEL table)
G2 = 2 * M_W / V_EW                            # SU(2) coupling at tree level: m_W = g v/2
G1 = G2 * math.sqrt(M_Z ** 2 - M_W ** 2) / M_W  # g′ = g tan θ_W, with cos θ_W = m_W/m_Z
E_EM = G1 * G2 / math.hypot(G1, G2)             # e = g s_W, the photon's coupling in the vertices
ALPHA_0 = 1 / 137.035999084                      # the Thomson limit
E_THOMSON = math.sqrt(4 * math.pi * ALPHA_0)     # e(0), DarkCast's (its ge = 0.302822)
# Kinetic mixing −(ε/2) V_μν F^μν (or −(ε/2c_W) V_μν B^μν) means DarkCast's ε: V couples to the electromagnetic
# current as ε e(0) Q, the Thomson-limit charge that a sub-GeV dark sector's processes see and every published ε
# assumes (decision D29, G12; G1's photon itself couples with the G_F scheme's e, 1.8% above). The mixing is
# scaled by e(0)/e to that end (``_vector_term``). A vertex's stated coupling reads e and α as e(0) and α(0), so
# that a current ε e Q f̄γf V written out is the same coupling as the kinetic mixing it stands for; s_W², v, m_h,
# m_W and m_Z at G1's values, so that a stated Higgs potential in m_h puts h where G1 does (125.09 GeV, against the
# table's 125.25). Write W and Z couplings through the fields' gauge charges, which G1 builds itself.
ELECTROWEAK = {"e": E_THOMSON, "alpha": ALPHA_0, "s_w2": 1 - (M_W / M_Z) ** 2, "v": V_EW, "m_h": M_H,
               "m_W": M_W, "m_Z": M_Z}
PHOTON_LIKE = {"A", "B"}                         # the SM vectors whose kinetic mixing is DarkCast's ε
CONTACT = {"SS", "SP", "PS", "PP", "VV", "VA", "AV", "AA", "TT"}   # four-fermion Γ ⊗ Γ': dark, then SM bilinear
SUPPORTED = {"scalar", "pseudoscalar", "chiral", "vector", "axial", "scalar_current", "kinetic_mixing"} | CONTACT


class GaugeBasisError(ValueError):
    """The model cannot be put in the gauge basis; the reason names what is missing or unsupported."""


# --- polynomials -----------------------------------------------------------------------------------

def poly_mul(p: Poly, q: Poly) -> Poly:
    """The product of two polynomials."""
    out: Poly = {}
    for a, x in p.items():
        for b, y in q.items():
            key = tuple(sorted(a + b))
            out[key] = out.get(key, 0) + x * y
    return out


def poly_add(p: Poly, q: Poly, scale: complex = 1.0) -> Poly:
    """p + scale·q."""
    out = dict(p)
    for k, v in q.items():
        out[k] = out.get(k, 0) + scale * v
    return out


def linear(form: dict[int, complex]) -> Poly:
    """A linear form Σ a_k x_k as a polynomial."""
    return {(k,): v for k, v in form.items() if v != 0}


def shift(p: Poly, v: np.ndarray) -> Poly:
    """p(v + y) as a polynomial in y: the expansion about the vacuum."""
    out: Poly = {}
    for key, c in p.items():
        expansion: Poly = {(): c}
        for k in key:
            expansion = poly_mul(expansion, {(): v[k], (k,): 1.0} if v[k] != 0 else {(k,): 1.0})
        out = poly_add(out, expansion)
    return {k: c for k, c in out.items() if abs(c) > 1e-14 * max(1.0, abs(c))}


def degree_part(p: Poly, n: int) -> Poly:
    """The terms of degree n."""
    return {k: c for k, c in p.items() if len(k) == n}


def hessian(p: Poly, size: int) -> np.ndarray:
    """∂²p/∂y_a∂y_b at y = 0 (from the degree-2 terms)."""
    out = np.zeros((size, size), dtype=complex)
    for key, c in degree_part(p, 2).items():
        a, b = key
        if a == b:
            out[a, a] += 2 * c
        else:
            out[a, b] += c
            out[b, a] += c
    return out


def gradient(p: Poly, size: int) -> np.ndarray:
    """∂p/∂y at y = 0."""
    out = np.zeros(size, dtype=complex)
    for key, c in degree_part(p, 1).items():
        out[key[0]] += c
    return out


# --- components ------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Coordinate:
    """A real scalar coordinate: the field, its SU(2) component m, the part ("re", "im" or "r") and charge Q."""
    field: str
    m: float
    part: str
    charge: float
    colour: str
    parity: int


@dataclass(frozen=True)
class Weyl:
    """A left-handed Weyl component: field, block ("xi" for the field, "eta" for the conjugate partner), m, Q."""
    field: str
    block: str
    m: float
    charge: float
    colour: str
    parity: int


@dataclass
class Components:
    """The model's components and the maps from each field's components to them."""
    coordinates: list[Coordinate] = field(default_factory=list)
    scalar_forms: dict[str, list[dict[int, complex]]] = field(default_factory=dict)   # field → F_m as forms in x
    weyl: list[Weyl] = field(default_factory=list)
    weyl_index: dict[tuple[str, str, int], int] = field(default_factory=dict)        # (field, block, k) → i
    vectors: list[str] = field(default_factory=list)


def _m_values(n: int) -> list[float]:
    j = (n - 1) / 2
    return [j - k for k in range(n)]


def _charge(f: ModelField, m: float, phase: Phase) -> float:
    return f.charges.electric_charge if phase is Phase.broken else m + f.charges.hypercharge


def _real_multiplet(f: ModelField) -> bool:
    return f.self_conjugate and f.charges.hypercharge == 0 and not any(f.charges.extra.values())


def add_scalar(comp: Components, f: ModelField, phase: Phase) -> None:
    """Add a scalar field's real coordinates and the linear forms of its components (module docstring)."""
    n, forms, r = f.charges.su2, [], 1 / math.sqrt(2)
    ms = _m_values(n)
    parity = f.dark_parity or 1
    def new(m: float, part: str) -> int:
        comp.coordinates.append(Coordinate(f.name, m, part, _charge(f, m, phase), f.charges.su3, parity))
        return len(comp.coordinates) - 1
    if not _real_multiplet(f):
        for m in ms:
            re, im = new(m, "re"), new(m, "im")
            forms.append({re: r, im: 1j * r})
    else:
        if n % 2 == 0:
            raise GaugeBasisError(f"{f.name}: a real scalar must be in an odd-dimensional (real) representation")
        by_m: dict[float, dict[int, complex]] = {}
        for m in ms:
            if m > 0:
                re, im = new(m, "re"), new(m, "im")
                by_m[m] = {re: r, im: 1j * r}
                by_m[-m] = {re: (-1) ** round(m) * r, im: -(-1) ** round(m) * 1j * r}   # φ₋ₘ = (−1)^m φₘ*
            elif m == 0:
                by_m[0.0] = {new(0.0, "r"): 1.0}
        forms = [by_m[m] for m in ms]
    comp.scalar_forms[f.name] = forms


def add_fermion(comp: Components, f: ModelField, phase: Phase) -> None:
    """Add a fermion field's Weyl blocks: ξ (and η for a Dirac field; a right-handed field is its η alone)."""
    n, parity = f.charges.su2, f.dark_parity or 1
    blocks = ["xi"] if f.self_conjugate or f.chirality == "L" else ["eta"] if f.chirality == "R" else ["xi", "eta"]
    for block in blocks:
        sign = 1 if block == "xi" else -1
        for k, m in enumerate(_m_values(n)):
            comp.weyl_index[(f.name, block, k)] = len(comp.weyl)
            comp.weyl.append(Weyl(f.name, block, m, sign * _charge(f, m, phase), f.charges.su3, parity))


# --- the Lagrangian ------------------------------------------------------------------------------

@dataclass
class GaugeBasis:
    """The model's Lagrangian in the gauge basis (module docstring): the pieces the spectrum needs, and the terms
    kept for the vertices (G2)."""
    spec: ModelSpec
    comp: Components
    potential: Poly = field(default_factory=dict)          # V(x), without the solved mass parameters
    quadratic: dict[str, float | None] = field(default_factory=dict)   # field → m² of ½m²Σx² (None: solved)
    vevs: dict[str, float] = field(default_factory=dict)   # field → v
    fermion: dict[tuple[int, int], Poly] = field(default_factory=dict)  # (i ≤ j) → holomorphic coefficient
    gauge: dict[str, np.ndarray] = field(default_factory=dict)          # vector → t^V on the coordinates
    vector_mass: dict[tuple[str, str], Poly] = field(default_factory=dict)  # (V ≤ W) → m²_VW(x)
    kinetic: dict[tuple[str, str], float] = field(default_factory=dict)     # (V < W) → K_VW
    explicit_vectors: set[str] = field(default_factory=set)               # new vectors (explicit couplings)
    for_vertices: list[ModelTerm] = field(default_factory=list)          # terms with SM fermions (G2)
    notes: list[str] = field(default_factory=list)


def _sm_fermion(f: ModelField) -> bool:
    return f.role is FieldRole.standard_model and f.spin == 0.5


def _scalar_forms(gb: GaugeBasis, name: str, conj: bool) -> list[dict[int, complex]]:
    forms = gb.comp.scalar_forms[name]
    return [{k: np.conj(v) for k, v in f.items()} for f in forms] if conj else forms


def _contracted(gb: GaugeBasis, c: Contraction, fixed: dict[int, int], scalars: list[int]) -> Poly:
    """Σ over the scalar slots' components of su2[...] Π F(x), the other slots held at ``fixed`` components."""
    out: Poly = {}
    tensor = c.su2
    for idx in zip(*np.nonzero(tensor)):
        if any(idx[k] != v for k, v in fixed.items()):
            continue
        term: Poly = {(): complex(tensor[idx])}
        for k in scalars:
            name, conj = c.occurrences[k]
            term = poly_mul(term, linear(_scalar_forms(gb, name, conj)[idx[k]]))
        out = poly_add(out, term)
    return out


def _colour_ok(c: Contraction) -> bool:
    """True if the term's colour structure is trivial for the masses: none, or one colour-diagonal pair."""
    live = [k for k, size in enumerate(c.colour.shape) if size > 1]
    if not live:
        return True
    flat = np.squeeze(c.colour)
    return len(live) == 2 and flat.shape[0] == flat.shape[1] and np.allclose(flat, np.eye(flat.shape[0]))


def _flavour_value(spec: ModelSpec, term: ModelTerm) -> None:
    """A term with SM fermions may use each flavour's own mass (m_q, m_l, m_f; G2 evaluates it per flavour): its
    coupling must have a finite value with those set."""
    from adroit.library.interactions.derivation import evaluate_expression, symbol_table
    try:
        value = evaluate_expression(term.coupling, symbol_table(spec, {"m_q": 1.0, "m_l": 1.0, "m_f": 1.0},
                                                                     ELECTROWEAK), allow_complex=True)
    except (KeyError, ValueError, NameError, TypeError, ZeroDivisionError):
        value = None
    if value is None or not cmath.isfinite(complex(value)):
        raise GaugeBasisError(f"the coupling {term.coupling!r} of {term.text or term.lorentz} has no value")


def _value(spec: ModelSpec, term: ModelTerm) -> complex:
    from adroit.library.interactions.derivation import evaluate_expression, symbol_table
    try:
        value = evaluate_expression(term.coupling, symbol_table(spec, standard=ELECTROWEAK), allow_complex=True)
    except (ValueError, TypeError, ZeroDivisionError):
        value = None
    if value is None:
        raise GaugeBasisError(f"the coupling {term.coupling!r} of {term.text or term.lorentz} has no value")
    if not cmath.isfinite(complex(value)):
        raise GaugeBasisError(f"the coupling {term.coupling!r} of {term.text or term.lorentz} is not finite")
    return value


_OPERATOR_DIMENSION = {0: 1.0, 0.5: 1.5, 1: 1.0}
_DERIVATIVES = {"scalar_current": 1, "kinetic_mixing": 2}
_CURRENTS = {"vector", "axial", "scalar_current", "kinetic_mixing"}


def _check_term(spec: ModelSpec, term: ModelTerm, fields: list) -> None:
    """Refuse a term that breaks the dark parity, or whose coupling's declared mass dimension the operator
    contradicts.

    The parity is checked on non-current terms: a current may be odd under a charge conjugation that the field
    parities do not express (a U(1)'s vector dark matter, V → −V with Φ → Φ*). A dimension is checked where the
    coupling is one named coupling declared with a non-zero dimension (0 is also the default, so it is not read as
    a statement)."""
    label = term.text or term.coupling
    if term.lorentz not in _CURRENTS and math.prod(f.dark_parity or 1 for f in fields) != 1:
        raise GaugeBasisError(f"{label}: the term breaks the dark parity (its fields' parities multiply to −1)")
    bare = term.coupling.strip().lstrip("+-").strip()
    declared = next((c for c in spec.couplings if c.name == bare), None)
    if declared is not None and declared.mass_dimension != 0:
        want = 4 - sum(_OPERATOR_DIMENSION[f.spin] for f in fields) - _DERIVATIVES.get(term.lorentz, 0)
        if abs(declared.mass_dimension - want) > 1e-9:
            raise GaugeBasisError(f"{label}: the coupling {bare} is declared with mass dimension "
                                  f"{declared.mass_dimension}, but the operator needs {want:g}")


_GAMMA = {"scalar": (1.0, 1.0), "pseudoscalar": (-1j, 1j), "chiral": (0.0, 1.0)}   # Γ = α P_L + β P_R


def _add_fermion_poly(gb: GaugeBasis, i: int, j: int, h: Poly) -> None:
    """Add h(x) ψ_iψ_j to the holomorphic bilinears."""
    key = (min(i, j), max(i, j))
    gb.fermion[key] = poly_add(gb.fermion.get(key, {}), h)


def _conjugate(gb: GaugeBasis, f: ModelField, m: int) -> list[tuple[int, float]]:
    """The Weyl components holding the conjugate of f's component m: a Dirac field's partner block η_m; for a Majorana
    field (η = ξ in a real representation) Σ C_{mm'} ξ_{m'}, C the invariant metric (L-3, 2026-11-21: the h.c. had used
    ξ_m, which only a metric-paired tensor tolerates, since CᵀCC ∝ C; the unique invariant of a triplet and two
    doublets is not one, and its charges came out reversed)."""
    if not f.self_conjugate:
        return [(gb.comp.weyl_index[(f.name, "eta", m)], 1.0)]
    metric = su2_metric(f.charges.su2)
    return [(gb.comp.weyl_index[(f.name, "xi", n)], metric[m, n]) for n in range(f.charges.su2) if metric[m, n]]


def _four_component(gb: GaugeBasis, term: ModelTerm, c: Contraction, a: int, b: int, scalars: list[int],
                    k: complex) -> None:
    """k Ψ̄_a Γ Ψ_b P(x) (+ h.c.): holo(T) = kαP η_aξ_b, and with + h.c. also (kβP)* η_bξ_a.

    The barred field's index labels the conjugate of its component m. For a Dirac field that is its partner block
    η_m. For a Majorana field (η = ξ in a real representation) it is Σ C_{mm'} ξ_{m'} with C the invariant metric,
    since the conjugate of ξ_m transforms as (−1)^m ξ₋ₘ."""
    alpha, beta = _GAMMA.get(term.lorentz, (None, None))
    if alpha is None:
        raise GaugeBasisError(f"a fermion bilinear with lorentz {term.lorentz!r} is not a mass or Yukawa term")
    fa, fb = (gb.spec.field(c.occurrences[x][0]) for x in (a, b))
    def barred(ma: int) -> list[tuple[int, float]]:
        if not fa.self_conjugate:
            return [(gb.comp.weyl_index[(fa.name, "eta", ma)], 1.0)]
        metric = su2_metric(fa.charges.su2)
        return [(gb.comp.weyl_index[(fa.name, "xi", m)], metric[ma, m]) for m in range(fa.charges.su2)
                if metric[ma, m]]
    def own(f, m: int, want: str) -> int:
        return gb.comp.weyl_index[(f.name, "xi" if f.self_conjugate else want, m)]
    for ma in range(c.su2.shape[a]):
        for mb in range(c.su2.shape[b]):
            p = _contracted(gb, c, {a: ma, b: mb}, scalars)
            if not p:
                continue
            ib = own(fb, mb, "xi")
            if alpha:
                for ia, weight in barred(ma):
                    _add_fermion_poly(gb, ia, ib, {key: k * alpha * weight * v for key, v in p.items()})
            if term.plus_hc and beta:                    # the h.c.: b's component conjugated, a's unbarred
                for ib2, weight in _conjugate(gb, fb, mb):
                    _add_fermion_poly(gb, ib2, own(fa, ma, "xi"),
                                      {key: np.conj(k * beta * v) * weight for key, v in p.items()})


def _majorana_type(gb: GaugeBasis, term: ModelTerm, c: Contraction, a: int, b: int, scalars: list[int],
                   k: complex) -> None:
    """k \\overline{Ψ_aᶜ} Γ Ψ_b P(x) + h.c., the bilinear of two fields written without a conjugation mark (for a Dirac
    field, a Majorana mass). With Ψ = (ξ, η†) and Ψᶜ = (η, ξ†), ξ_a takes the place a barred field's η_a has in
    ``_four_component``: holo gets kαP ξ_aξ_b, and the h.c. of kβP η_a†η_b† adds (kβP)* η_bη_a. A Dirac field's
    −½δ(\\overline{Ψᶜ}Ψ + h.c.) gives both its components the Majorana mass δ, so with a Dirac mass M its states are
    M ± δ, a pseudo-Dirac pair."""
    alpha, beta = _GAMMA.get(term.lorentz, (None, None))
    if alpha is None:
        raise GaugeBasisError(f"a fermion bilinear with lorentz {term.lorentz!r} is not a mass or Yukawa term")
    fa, fb = (gb.spec.field(c.occurrences[x][0]) for x in (a, b))
    def own(f, m: int, want: str) -> int:
        return gb.comp.weyl_index[(f.name, "xi" if f.self_conjugate else want, m)]
    for ma in range(c.su2.shape[a]):
        for mb in range(c.su2.shape[b]):
            p = _contracted(gb, c, {a: ma, b: mb}, scalars)
            if not p:
                continue
            if alpha:
                _add_fermion_poly(gb, own(fa, ma, "xi"), own(fb, mb, "xi"), {key: k * alpha * v for key, v in p.items()})
            if beta:                                     # the h.c. of kβP η_a†η_b†: both components conjugated
                for ib2, wb in _conjugate(gb, fb, mb):
                    for ia2, wa in _conjugate(gb, fa, ma):
                        _add_fermion_poly(gb, ib2, ia2, {key: np.conj(k * beta * v) * wa * wb for key, v in p.items()})


def _two_component(gb: GaugeBasis, term: ModelTerm, c: Contraction, a: int, b: int, scalars: list[int],
                   k: complex) -> None:
    """k ψ_a ψ_b P(x) of Weyl fields: holomorphic when both are left-handed (a right-handed field ψ_R is η†, its
    conjugate block). A right-handed pair contributes its conjugate; either way the term implies its h.c."""
    def left(x: int) -> tuple[str, bool]:
        name, conj = c.occurrences[x]
        f = gb.spec.field(name)
        is_left = (f.chirality == "L" and not conj) or (f.chirality == "R" and conj)
        return ("xi" if f.chirality == "L" else "eta"), is_left
    (ba, la), (bb, lb) = left(a), left(b)
    if la != lb:
        raise GaugeBasisError(f"{term.text or term.coupling}: a left- and a right-handed spinor form a vector "
                              "bilinear, not a mass or Yukawa term")
    for ma in range(c.su2.shape[a]):
        for mb in range(c.su2.shape[b]):
            p = _contracted(gb, c, {a: ma, b: mb}, scalars)
            if not p:
                continue
            ia = gb.comp.weyl_index[(c.occurrences[a][0], ba, ma)]
            ib = gb.comp.weyl_index[(c.occurrences[b][0], bb, mb)]
            _add_fermion_poly(gb, ia, ib, {key: (k * v if la else np.conj(k * v)) for key, v in p.items()})


def _fermion_term(gb: GaugeBasis, term: ModelTerm, c: Contraction, k: complex) -> None:
    """A dark fermion bilinear times scalars: its contribution to M_ij(x)."""
    kinds = [gb.spec.field(n) for n, _ in c.occurrences]
    fermions = [x for x, f in enumerate(kinds) if f.spin == 0.5]
    scalars = [x for x, f in enumerate(kinds) if f.spin == 0]
    if len(fermions) != 2 or len(scalars) + 2 != len(kinds):
        raise GaugeBasisError(f"{term.text or term.coupling}: a fermion term needs two fermions and only scalars")
    a, b = fermions
    weyl = [bool(kinds[x].chirality) for x in fermions]
    if all(weyl):
        _two_component(gb, term, c, a, b, scalars, k)
        return
    if any(weyl):
        raise GaugeBasisError(f"{term.text or term.coupling}: a bilinear of a Weyl field and a four-component field "
                              "is not supported")
    if c.occurrences[b][1] and not c.occurrences[a][1]:
        a, b = b, a                                       # the barred (conjugated) field first
    if c.occurrences[a][1] and c.occurrences[b][1]:
        raise GaugeBasisError(f"{term.text or term.coupling}: both fermions conjugated")
    if not c.occurrences[a][1] and not (kinds[a].self_conjugate and kinds[b].self_conjugate):
        if not term.plus_hc:
            raise GaugeBasisError(f"{term.text or term.coupling}: a Majorana-type bilinear (no field conjugated) needs "
                                  "+ h.c.")
        _majorana_type(gb, term, c, a, b, scalars, k)
        return
    _four_component(gb, term, c, a, b, scalars, k)


def _scalar_term(gb: GaugeBasis, term: ModelTerm, c: Contraction, k: complex) -> None:
    """A pure scalar term: L ⊃ k P(x) (+ h.c.), so V ⊃ −k P."""
    p = {key: k * v for key, v in _contracted(gb, c, {}, list(range(len(c.occurrences)))).items()}
    if term.plus_hc:
        p = poly_add(p, {key: np.conj(v) for key, v in p.items()})
    elif any(abs(v.imag) > 1e-9 * max(1.0, abs(v)) for v in poly_add(p, {kk: np.conj(v) for kk, v in p.items()},
                                                                    -1).values()):
        raise GaugeBasisError(f"{term.text or term.coupling}: the term is not hermitian and has no + h.c.")
    gb.potential = poly_add(gb.potential, p, -1.0)


def _vector_term(gb: GaugeBasis, term: ModelTerm, c: Contraction, k: complex) -> None:
    """Kinetic mixing, an explicit vector mass or seagull, or a scalar current (its generator, for the
    Goldstone directions); fermion currents are kept for the vertices (G2)."""
    kinds = [gb.spec.field(n) for n, _ in c.occurrences]
    vectors = [x for x, f in enumerate(kinds) if f.spin == 1]
    scalars = [x for x, f in enumerate(kinds) if f.spin == 0]
    names = sorted(c.occurrences[x][0] for x in vectors)
    if term.lorentz == "kinetic_mixing":
        a, b = names
        scale = E_THOMSON / E_EM if PHOTON_LIKE & {a, b} else 1.0                  # DarkCast's ε (D29, above)
        gb.kinetic[(a, b)] = gb.kinetic.get((a, b), 0.0) - 2 * scale * float(np.real(k))   # L ⊃ C V_μν W^μν
        return
    if term.lorentz == "scalar_current":
        _current(gb, term, c, vectors[0], scalars, k)
        return
    if len(vectors) == 2 and len(vectors) + len(scalars) == len(kinds) and term.lorentz == "scalar":
        p = _contracted(gb, c, {}, scalars) if scalars else {(): 1.0}
        factor = 2.0 if names[0] == names[1] else 1.0                                  # ½ m² V² against V·W
        key = (names[0], names[1])
        gb.vector_mass[key] = poly_add(gb.vector_mass.get(key, {}), {kk: factor * k * v for kk, v in p.items()})
        return
    gb.for_vertices.append(term)


def _current(gb: GaugeBasis, term: ModelTerm, c: Contraction, v: int, scalars: list[int], k: complex) -> None:
    """i k V^μ(F ∂_μF* − F*∂_μF) for D F = ∂F + i k V F: the generator −k on F's components, as t^V on x."""
    vector = c.occurrences[v][0]
    (fa, ca), (fb, cb) = (c.occurrences[x] for x in scalars)
    if fa != fb or ca == cb:
        raise GaugeBasisError(f"{term.text or term.coupling}: a scalar current of two different fields is not "
                              "supported")
    gb.explicit_vectors.add(vector)
    size = len(gb.comp.coordinates)
    t = gb.gauge.get(vector, np.zeros((size, size)))
    n = len(gb.comp.scalar_forms[fa])
    gb.gauge[vector] = t + real_action(gb, fa, -k * np.eye(n) * 1j)


def _field_matrix(gb: GaugeBasis, name: str) -> tuple[list[int], np.ndarray]:
    """(F's coordinates, the complex matrix A with F_m = Σ A_{mk} x_k on them)."""
    forms = gb.comp.scalar_forms[name]
    coords = sorted({k for f in forms for k in f})
    a = np.array([[f.get(k, 0) for k in coords] for f in forms], dtype=complex)
    return coords, a


def real_action(gb: GaugeBasis, name: str, operator: np.ndarray) -> np.ndarray:
    """The real matrix on all coordinates that acts on F's coordinates as the complex ``operator`` acts on its
    components (A x′ = O A x), and as zero elsewhere."""
    coords, a = _field_matrix(gb, name)
    stack = np.vstack([a.real, a.imag])
    image = operator @ a
    solution, *_ = np.linalg.lstsq(stack, np.vstack([image.real, image.imag]), rcond=None)
    size = len(gb.comp.coordinates)
    out = np.zeros((size, size))
    out[np.ix_(coords, coords)] = solution
    return out


def _standard_model_gauge(gb: GaugeBasis) -> None:
    """t^V of W¹, W², W³ and B on every scalar coordinate: D F = ∂F − i g T^A W^A F − i g′ Y B F."""
    size = len(gb.comp.coordinates)
    for name in gb.comp.scalar_forms:
        f = gb.spec.field(name) if name in {x.name for x in gb.spec.fields} else _HIGGS
        n = f.charges.su2
        for a, label in enumerate(("W1", "W2", "W3")):
            gb.gauge[label] = gb.gauge.get(label, np.zeros((size, size))) + \
                real_action(gb, name, 1j * G2 * su2_generators(n)[a])
        gb.gauge["B"] = gb.gauge.get("B", np.zeros((size, size))) + \
            real_action(gb, name, 1j * G1 * f.charges.hypercharge * np.eye(n))


_HIGGS = ModelField(name="H", role=FieldRole.standard_model, spin=0, charges={"su2": 2, "hypercharge": 0.5},
                    vev_gev=V_EW)
_LAMBDA_H = M_H ** 2 / (2 * V_EW ** 2)                  # V ⊃ λ|H|⁴, m_h² = 2λv²


def _explicit_bilinear(spec: ModelSpec, name: str) -> bool:
    """True if a two-field term (no vector) involves the field: its mass is then stated by terms."""
    return any(len(t.fields) == 2 and name in {o.field for o in t.fields}
               and all(spec.field(o.field).spin != 1 for o in t.fields) and t.lorentz != "kinetic_mixing"
               for t in spec.terms)


# G2's SM fermion names (``feynman.GENERIC``, ``RIGHT``): Q had been missing, so a doublet Yukawa written with Q read as
# flavour-changing (G12's live check L9)
LEFT_DOUBLETS = {"Q", "qL", "QL", "lL", "L", "Le", "Lmu", "Ltau", "L_e", "L_mu", "L_tau"}
SM_HYPERCHARGE = {"Q": 1 / 6, "qL": 1 / 6, "QL": 1 / 6, "lL": -0.5, "L": -0.5, "Le": -0.5, "Lmu": -0.5, "Ltau": -0.5,
                  "L_e": -0.5, "L_mu": -0.5, "L_tau": -0.5, "uR": 2 / 3, "dR": -1 / 3, "eR": -1.0, "muR": -1.0,
                  "tauR": -1.0}
HYPERCHARGE_ROUNDING = 1e-3      # hypercharges are multiples of 1/6: 0.6667 for 2/3 is rounding, not a new charge


def _supported_shape(spec: ModelSpec, term: ModelTerm) -> None:
    """Refuse a term that G2 has no Feynman rule for, rather than dropping it (the audit's G1-5 and G3/G4-9, G12): a
    vector or axial term that is not one vector and two fermions (a scalar's current is ``scalar_current``); a
    current joining a new fermion to an SM one, or two different SM fermions (flavour-changing); a four-fermion
    contact term other than ``_contact_shape``'s; and a Yukawa of two different SM fermions other than a doublet's
    (Q̄Φd_R)."""
    fields = [spec.field(o.field) for o in term.fields]
    fermions = [f for f in fields if f.spin == 0.5]
    sm = [f for f in fermions if _sm_fermion(f)]
    where = term.text or term.coupling
    if spec.phase is Phase.unbroken and sm and all(f.name in SM_HYPERCHARGE for f in sm):
        total = sum((-1 if o.conjugate else 1) * (SM_HYPERCHARGE.get(o.field) if _sm_fermion(spec.field(o.field))
                                                  else spec.field(o.field).charges.hypercharge) for o in term.fields)
        if abs(total) > HYPERCHARGE_ROUNDING:       # the audit's G1-7 (G12): a φ(Y = 0) χ̄ e_R had been accepted
            raise GaugeBasisError(f"{where}: its hypercharges sum to {total:+g}, not 0")
    if len(fermions) > 2:
        _contact_shape(spec, term, fields, where)
        return
    if sm and len(fermions) == 2 and len(fields) > 3:     # the audit loop's AL4-04, 2026-11-16: c S S ū u had passed,
        raise GaugeBasisError(f"{where}: a term of a fermion pair with a Standard Model fermion and "      # then been
                              f"{len(fields) - 2} bosons (S S q̄q, V V q̄q) has no rule on the generic route, so it "  # left
                              "would be left out of the model's calculation")                                  # out
    if term.lorentz in ("vector", "axial"):
        if [f.spin for f in fields].count(1) != 1 or len(fermions) != 2 or len(fields) != 3:
            raise GaugeBasisError(f"{where}: a {term.lorentz} current is one vector and two fermions (a scalar's "
                                  "current is lorentz scalar_current)")
        if len(sm) == 1:
            raise GaugeBasisError(f"{where}: a current joining a new fermion to a Standard Model one is not supported")
    if len(sm) == 2 and sm[0].name != sm[1].name:
        doublet = any(f.spin == 0 and f.charges.su2 == 2 and f.role is not FieldRole.standard_model for f in fields)
        if term.lorentz in ("vector", "axial") or not (doublet and {f.name for f in sm} & LEFT_DOUBLETS):
            raise GaugeBasisError(f"{where}: a coupling joining two different Standard Model fermions "
                                  f"({sm[0].name}, {sm[1].name}) is flavour-changing and not supported")


def _contact_shape(spec: ModelSpec, term: ModelTerm, fields: list, where: str) -> None:
    """A four-fermion contact term G2 has a rule for (2026-10-20): (Ψ̄_D Γ Ψ_D)(f̄ Γ' f) with the dark bilinear first,
    of one colourless SU(2)-singlet dark fermion (four-component) and one Standard Model fermion field, each barred
    field written first, ``lorentz`` naming Γ ⊗ Γ' (``CONTACT``: S, P = iγ⁵, V, A, T). A Weyl Standard Model field's
    bilinear is its chiral current (Γ' = V): above electroweak breaking only those are gauge invariant at dimension 6.
    Anything else is refused: a dark self-interaction, four Standard Model fermions, a flavour-changing pair."""
    if term.lorentz not in CONTACT or len(fields) != 4 or any(f.spin != 0.5 for f in fields):
        raise GaugeBasisError(f"{where}: a four-fermion contact term is four fermions with lorentz one of "
                              f"{', '.join(sorted(CONTACT))} (Γ ⊗ Γ': the dark bilinear's, then the Standard Model's)")
    occ = term.fields
    pairs = [(occ[0], occ[1]), (occ[2], occ[3])]
    if any(a.field != b.field or not a.conjugate or b.conjugate for a, b in pairs):
        raise GaugeBasisError(f"{where}: a contact term is two bilinears Ψ̄Ψ of one field each, the barred field first")
    dark, sm = (spec.field(a.field) for a, _ in pairs)
    if _sm_fermion(dark) or not _sm_fermion(sm):
        raise GaugeBasisError(f"{where}: a contact term joins one dark fermion's bilinear (first) to one Standard Model "
                              "fermion's (dark self-interactions and four Standard Model fermions are not supported)")
    if dark.chirality or dark.charges.su2 != 1 or dark.charges.su3 != "1":
        raise GaugeBasisError(f"{where}: the dark fermion of a contact term is a four-component colourless SU(2) "
                              "singlet")
    if sm.chirality and term.lorentz[1] != "V":
        raise GaugeBasisError(f"{where}: {sm.name} is a Weyl field, whose bilinear in a contact term is its current "
                              "(Γ' = V)")


def _model_checks(spec: ModelSpec) -> None:
    """Refusals that keep G1 from misreading a model (the audit's G1-3, G1-4, G1-8; G12; a new field of several
    generations, G1-9, is expanded before them: ``generations``): a vector with a stated mass beside a mass from terms
    or a vacuum; the SM-like h's own potential stated below breaking (G1 adds it); a declared h above breaking (the
    doublet is H); and kinetic mixing with a Standard Model vector the phase does not have (A or Z below breaking, B
    above)."""
    broken = spec.phase is Phase.broken
    for f in spec.fields:
        if f.role is not FieldRole.standard_model and f.spin not in (0, 0.5, 1):    # had been skipped silently
            raise GaugeBasisError(f"{f.name}: spin {f.spin:g} is not supported (spin 0, ½ and 1 are; spin above 1 "
                                  "is deferred)")
        if f.name == "h" and f.role is FieldRole.standard_model and not broken:
            raise GaugeBasisError("h is the broken phase's Higgs; above breaking the Standard Model's Higgs is the "
                                  "doublet H")
        if f.spin == 1 and f.role is not FieldRole.standard_model and f.mass_gev is not None:
            explicit = any(len(t.fields) == 2 and all(o.field == f.name for o in t.fields) for t in spec.terms)
            higgsed = any(t.lorentz == "scalar_current" and any(o.field == f.name for o in t.fields)
                          and any(spec.field(o.field).vev_gev for o in t.fields) for t in spec.terms)
            if explicit or higgsed:
                raise GaugeBasisError(f"{f.name} states its mass twice: mass_gev and "
                                      f"{'an explicit mass term' if explicit else 'a vacuum value it couples to'}")
    for t in spec.terms:
        names = [o.field for o in t.fields]
        if broken and names and set(names) == {"h"}:
            raise GaugeBasisError("the SM-like h's own potential is G1's below breaking; do not state it")
        if t.lorentz == "kinetic_mixing":
            sm = [n for n in names if spec.field(n).role is FieldRole.standard_model]
            allowed = {"A", "Z"} if broken else {"B"}
            if any(n not in allowed for n in sm):
                raise GaugeBasisError(f"kinetic mixing with {', '.join(sm)}: the {spec.phase.value} phase's vectors "
                                      f"are {', '.join(sorted(allowed))}")


def _one_mass_statement(spec: ModelSpec) -> None:
    """A new field states its mass once: ``mass_gev``, or explicit terms. With both, the terms replace the stated
    mass (module docstring), so a stated mass beside a bilinear of the field with itself (χ̄χ, χ̄iγ⁵χ, |φ|²) is
    refused as ambiguous. A bilinear joining two different fields (a Dirac mass between two Weyl fields) is not."""
    for f in spec.fields:
        if f.role is FieldRole.standard_model or f.mass_gev is None or f.spin == 1:
            continue
        # the field's own mass term: f̄f or |φ|² (one occurrence conjugated), or any square of a self-conjugate field;
        # a Majorana splitting ψψ or a holomorphic φφ beside mass_gev is a different structure, and allowed
        own = next((t for t in spec.terms if len(t.fields) == 2 and {o.field for o in t.fields} == {f.name}
                    and (f.self_conjugate or t.fields[0].conjugate != t.fields[1].conjugate)), None)
        if own is not None:
            raise GaugeBasisError(f"{f.name} states its mass twice: mass_gev = {f.mass_gev:g} GeV and the two-field "
                                  f"term {own.text or own.lorentz} (coupling {own.coupling}); give one of them: an "
                                  "explicit mass term with mass_gev null, or mass_gev without a two-field term of "
                                  f"{f.name} alone")


def _stated_masses(gb: GaugeBasis) -> None:
    """Each field's ``mass_gev`` as its Lagrangian mass term (module docstring)."""
    spec = gb.spec
    for f in spec.fields:
        if f.role is FieldRole.standard_model or f.mass_gev is None:
            continue
        # a stated mass is the diagonal entry; a two-field term joining the field to another adds a mixing to it
        # (the audit's G1-3, G12: any such term had silently replaced it). A Weyl field's partner is its terms'.
        if f.spin == 0.5 and f.chirality and _explicit_bilinear(spec, f.name):
            continue
        if f.spin == 0 and not f.vev_gev:
            gb.quadratic[f.name] = f.mass_gev ** 2
        elif f.spin == 0.5:
            _fermion_mass(gb, f)
        elif f.spin == 1:
            gb.vector_mass[(f.name, f.name)] = poly_add(gb.vector_mass.get((f.name, f.name), {}),
                                                        {(): f.mass_gev ** 2})


def _fermion_mass(gb: GaugeBasis, f: ModelField) -> None:
    """M χ̄χ (Dirac: −M η_mξ_m) or ½M χ̄χ in a real representation (−½ M C_{mm'} λ_mλ_{m'})."""
    n, m = f.charges.su2, f.mass_gev
    real = f.self_conjugate or (f.chirality and _real_multiplet(f.model_copy(update={"self_conjugate": True})))
    if real:
        c = su2_metric(n)
        block = "eta" if f.chirality == "R" and not f.self_conjugate else "xi"     # a right-handed field is held as η
        for a in range(n):
            for b in range(n):
                if c[a, b]:
                    i = gb.comp.weyl_index[(f.name, block, a)]
                    j = gb.comp.weyl_index[(f.name, block, b)]
                    _add_fermion_poly(gb, i, j, {(): -0.5 * m * c[a, b]})
        return
    if f.chirality:
        gb.notes.append(f"{f.name}: a Weyl field in a complex representation has no mass of its own; its stated "
                        f"{m:g} GeV is not used (a two-field term must give its partner)")
        return
    for a in range(n):
        _add_fermion_poly(gb, gb.comp.weyl_index[(f.name, "eta", a)], gb.comp.weyl_index[(f.name, "xi", a)],
                          {(): -m})


def _with_higgs(spec: ModelSpec) -> ModelSpec:
    """The model with the Standard Model's Higgs doublet H (vev 246.22 GeV) in the unbroken phase."""
    if spec.phase is not Phase.unbroken:
        return spec
    fields = [f.model_copy(update={"vev_gev": V_EW}) if f.name == "H" else f for f in spec.fields]
    if "H" not in {f.name for f in fields}:
        fields.append(_HIGGS)
    return spec.model_copy(update={"fields": fields})


def _dispatch(gb: GaugeBasis, term: ModelTerm) -> None:
    """One term's contribution (scalars, a dark fermion bilinear, vectors), or kept for the vertices."""
    spec = gb.spec
    fields = [spec.field(o.field) for o in term.fields]
    if term.lorentz not in SUPPORTED:
        raise GaugeBasisError(f"{term.text or term.lorentz}: a {term.lorentz} interaction is not supported by the "
                              "generic route")
    _check_term(spec, term, fields)
    if any(_sm_fermion(f) for f in fields):
        _flavour_value(spec, term)
        gb.for_vertices.append(term)
        return
    _value(spec, term)
    c = contraction(spec, term)
    k = _value(spec, term)
    spins = {f.spin for f in fields}
    if 1 in spins:
        _vector_term(gb, term, c, k)
        return
    if not _colour_ok(c):
        gb.for_vertices.append(term)                     # no mass from a term with more than one coloured pair
        return
    if 0.5 in spins:
        _fermion_term(gb, term, c, k)
    else:
        _scalar_term(gb, term, c, k)


def build(spec: ModelSpec) -> GaugeBasis:
    """The model in the gauge basis (module docstring). Raises GaugeBasisError, or IndexError_ for a contraction
    that must be stated."""
    from adroit.model_building import generations
    try:
        spec = generations.expand(spec)                  # a new field of several generations is that many fields
    except generations.GenerationError as error:
        raise GaugeBasisError(str(error)) from error
    if spec.phase is Phase.broken and any(f.vev_gev for f in spec.fields):
        raise GaugeBasisError("a model written below electroweak symmetry breaking has no vacuum values: its fields "
                              "are already the fluctuations")
    for f in spec.fields:
        if f.mass_gev is not None and not (math.isfinite(f.mass_gev) and f.mass_gev >= 0):
            raise GaugeBasisError(f"{f.name}: a stated mass must be finite and non-negative, not {f.mass_gev}")
    _one_mass_statement(spec)
    _model_checks(spec)
    for term in spec.terms:
        _supported_shape(spec, term)
    spec = _with_higgs(spec)
    gb = GaugeBasis(spec=spec, comp=Components())
    for f in spec.fields:
        if f.spin == 0 and (f.role is not FieldRole.standard_model or f.name in ("H", "h")):
            add_scalar(gb.comp, f, spec.phase)
        elif f.spin == 0.5 and f.role is not FieldRole.standard_model:
            add_fermion(gb.comp, f, spec.phase)
        elif f.spin == 1 and f.role is not FieldRole.standard_model:
            gb.comp.vectors.append(f.name)
            gb.explicit_vectors.add(f.name)
    for f in spec.fields:
        if f.vev_gev and f.spin == 0:                    # a vacuum value of 0 is none (G1-3)
            gb.vevs[f.name] = f.vev_gev
            gb.quadratic[f.name] = None                   # solved from the vacuum
    if spec.phase is Phase.unbroken:
        gb.comp.vectors = ["B", "W1", "W2", "W3"] + gb.comp.vectors
        _standard_model_gauge(gb)
        if not any(sorted((o.field, o.conjugate) for o in t.fields) == [("H", False)] * 2 + [("H", True)] * 2
                   for t in spec.terms):
            gb.potential = poly_add(gb.potential, _higgs_quartic(gb))
    else:
        _broken_standard_model(gb)
        _broken_gauge(gb)
    _stated_masses(gb)
    for term in spec.terms:
        _dispatch(gb, term)
    return gb


def _higgs_quartic(gb: GaugeBasis) -> Poly:
    """λ_H |H|⁴ with λ_H = m_h²/(2v²): the Standard Model's own quartic, unless the model states it."""
    norm: Poly = {}
    for form in gb.comp.scalar_forms["H"]:
        norm = poly_add(norm, poly_mul(linear(form), linear({k: np.conj(v) for k, v in form.items()})))
    return {k: _LAMBDA_H * v for k, v in poly_mul(norm, norm).items()}


def broken_charges(f: ModelField) -> tuple[float, float]:
    """(photon, Z) couplings of a new field written below electroweak breaking, an SU(2) singlet (T₃ = 0, Y = Q):
    e Q and −(g/c_W) s_W² Q, as the unbroken phase gives it after W³–B mixing (the audit's G1-2, G12: such a field had
    no gauge couplings at all). A charged non-singlet has no T₃ here and is refused."""
    q = f.charges.electric_charge or (f.charges.hypercharge if f.charges.su2 == 1 else 0.0)
    if abs(q) < 1e-12:
        return 0.0, 0.0
    if f.charges.su2 > 1:
        raise GaugeBasisError(f"{f.name}: a charged SU(2) {f.charges.su2}-plet written below electroweak breaking "
                              "has no T₃ for its Z coupling; write it in the unbroken phase")
    cw = M_W / M_Z
    return E_EM * q, -G2 / cw * (1 - cw * cw) * q


def _broken_gauge(gb: GaugeBasis) -> None:
    """The photon's and the Z's generators on a broken-phase model's new charged scalars (``broken_charges``)."""
    size = len(gb.comp.coordinates)
    for name in gb.comp.scalar_forms:
        f = next((x for x in gb.spec.fields if x.name == name), None)
        if f is None or f.role is FieldRole.standard_model:
            continue
        photon, z = broken_charges(f)
        n = len(gb.comp.scalar_forms[name])
        for vector, k in (("A", photon), ("Z", z)):
            if k:
                gb.gauge[vector] = gb.gauge.get(vector, np.zeros((size, size))) + \
                    real_action(gb, name, 1j * k * np.eye(n))


def _broken_standard_model(gb: GaugeBasis) -> None:
    """Below electroweak breaking: the photon, Z and W as given vectors, and h's potential
    ½ m_h² h² + (m_h²/2v) h³ + (m_h²/8v²) h⁴ if the model has h."""
    gb.comp.vectors = ["A", "Z", "W"] + gb.comp.vectors
    gb.vector_mass[("Z", "Z")] = {(): M_Z ** 2}
    gb.vector_mass[("W", "W")] = {(): M_W ** 2}
    if "h" in gb.comp.scalar_forms:
        (k,) = gb.comp.scalar_forms["h"][0]
        gb.potential = poly_add(gb.potential, {(k, k): 0.5 * M_H ** 2, (k, k, k): M_H ** 2 / (2 * V_EW),
                                               (k, k, k, k): M_H ** 2 / (8 * V_EW ** 2)})
