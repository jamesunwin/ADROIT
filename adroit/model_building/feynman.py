"""Feynman rules in the mass basis (G2): every vertex of a typed model's physical states.

From G1's mass basis (``spectrum.compute``), the Lagrangian expanded about the vacuum is rewritten in the physical
fields, and each vertex is a derivative of it:

    V(Φ_a, Φ_b, …) = ∂ⁿL/∂Φ_a∂Φ_b… (the combinatorial factor included),

with the gauge-basis coordinates y = Σ A Φ (scalars), Weyl spinors ψ = Σ B w (fermions) and vectors V = Σ R E.
The pieces:
- **scalars:** V_abc = −∂³V and V_abcd = −∂⁴V of the shifted potential;
- **Yukawas:** from L ⊃ −½ M_ij(y) ψ_iψ_j + h.c., the first (FFS) and second (FFSS) derivatives of M_ij.
  Each Weyl pair is written as a four-component bilinear Ψ̄_A P_L Ψ_B, and its h.c. gives the P_R part;
- **gauge interactions:** of the scalars, from ½(D y)², D y = ∂y − Σ t^V y V. These give the current
  −V (∂y)ᵀ t^V y (VSS), the vacuum term (t^V v)·(t^W y) V W (VVS) and the seagull ½ (t^V y)·(t^W y) V W (VVSS).
  Of the fermions, from ψ† σ̄ G^V ψ V (FFV). Of SU(2)'s own bosons, the triple vertex (VVV);
- **the Standard Model's fermions** in their mass basis, with their couplings to the gauge bosons (rotated with
  any mixing of the neutral vectors) and to the scalars through each state's H⁰ component.

**Leg names.** A real scalar, a Majorana fermion and a neutral vector are their own antiparticles. Any other state s
has antiparticle ``s~``. The field Φ_s annihilates an incoming s, and Φ_s* an incoming s~. Every leg is incoming, as
in ``constraints.tree``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from adroit.model_building import gauge_basis as gbm
from adroit.model_building.spectrum import MassBasis

TOLERANCE = 1e-10


@dataclass(frozen=True)
class Symbol:
    """A mass-basis field: the state, conjugated or not (Φ_s or Φ_s*)."""
    state: str
    conj: bool = False

    def leg(self, self_conjugate: bool) -> str:
        """The incoming leg this field annihilates."""
        return self.state if (not self.conj or self_conjugate) else f"{self.state}~"


@dataclass
class MassVertex:
    """One vertex: kind (as ``constraints.tree``), incoming legs in slot order, couplings, colour structure."""
    kind: str
    legs: tuple[str, ...]
    c: complex
    c2: complex = 0.0
    colour: str = ""
    structure: tuple = ()           # FFFF: ((Γ, Γ', c), ...), as ``tree.Vertex``


@dataclass
class Fields:
    """The mass-basis fields of each kind and the rotations from the gauge basis to them."""
    scalars: list[Symbol] = field(default_factory=list)
    scalar_map: np.ndarray | None = None          # A[k, a] = ∂y_k/∂Φ_a
    self_conjugate: set[str] = field(default_factory=set)


def scalar_fields(mb: MassBasis) -> Fields:
    """The scalar fields Φ_a (one per real state; Φ_s and Φ_s* per complex state) and A[k, a]."""
    kinds = {s.name: s.kind for s in mb.spectrum.states}
    columns, symbols, real = [], [], set()
    for name, u in mb.scalar_states:
        if kinds[name] == "real":
            columns.append(u.real)
            symbols.append(Symbol(name))
            real.add(name)
        else:
            columns += [u, u.conj()]                      # y ⊃ u F + u* F*
            symbols += [Symbol(name), Symbol(name, True)]
    size = len(mb.vacuum)
    a = np.array(columns).T if columns else np.zeros((size, 0))
    return Fields(scalars=symbols, scalar_map=a, self_conjugate=real)


def derivative_tensor(poly: gbm.Poly, degree: int, size: int) -> np.ndarray:
    """The symmetric tensor of n-th derivatives at y = 0, from the polynomial's degree-n terms."""
    out = np.zeros((size,) * degree, dtype=complex)
    from itertools import permutations
    for key, c in gbm.degree_part(poly, degree).items():
        counts = math.prod(math.factorial(key.count(k)) for k in set(key))
        for perm in set(permutations(key)):
            out[perm] += c * counts
    return out


def scalar_vertices(mb: MassBasis, f: Fields) -> list[MassVertex]:
    """SSS and SSSS: V = −∂ⁿV in the physical fields, once per unordered set of legs."""
    out = []
    size = len(mb.vacuum)
    for degree, kind in ((3, "SSS"), (4, "SSSS")):
        t = derivative_tensor(mb.potential, degree, size)
        if not np.any(t):
            continue
        for _ in range(degree):
            t = np.tensordot(t, f.scalar_map, axes=([0], [0]))     # contract the gauge index, append the field one
        n = len(f.scalars)
        from itertools import combinations_with_replacement
        for idx in combinations_with_replacement(range(n), degree):
            value = -t[idx]
            if abs(value) > TOLERANCE * max(1.0, float(np.max(np.abs(t)))):
                legs = tuple(f.scalars[i].leg(f.scalars[i].state in f.self_conjugate) for i in idx)
                out.append(MassVertex(kind, legs, complex(value)))
    return out


# --- the fermions ------------------------------------------------------------------------------------

@dataclass(frozen=True)
class WeylState:
    """A mass-basis Weyl component: its state and role ("maj" λ, "chi" the particle side of a Dirac fermion,
    "zeta" its antiparticle side)."""
    state: str
    role: str


def fermion_fields(mb: MassBasis) -> tuple[list[WeylState], np.ndarray]:
    """The mass-basis Weyl components w and B[i, w] = ∂ψ_i/∂w (ψ = U* λ for Majorana; W* χ and Z ζ for Dirac)."""
    states, columns = [], []
    for name, left, right in mb.fermion_states:
        if right is None:
            states.append(WeylState(name, "maj"))
            columns.append(left)
        else:
            states += [WeylState(name, "chi"), WeylState(name, "zeta")]
            columns += [left, right]
    n = len(mb.gauge.comp.weyl)
    return states, (np.array(columns).T if columns else np.zeros((n, 0)))


def leg(w: WeylState) -> str:
    """The species whose four-component field has w as its upper (left-handed) component, which is also the
    incoming leg when w appears as the conjugate of a lower component: λ_A → A, χ_A → A, ζ_A → A~ (ζ_A is the upper
    component of Ψ_Aᶜ)."""
    return f"{w.state}~" if w.role == "zeta" else w.state


def conjleg(w: WeylState) -> str:
    """The antiparticle of ``leg``: the slot f̄ of a term Ψ̄_X … with w the upper component of Ψ_X."""
    return w.state if w.role == "zeta" else (w.state if w.role == "maj" else f"{w.state}~")


def _anti(state: str, self_conjugate: set[str]) -> str:
    return state if state in self_conjugate else f"{state}~"


def yukawa_vertices(mb: MassBasis, f: Fields) -> list[MassVertex]:
    """FFS and FFSS from L ⊃ −½ M_ij(y) ψ_iψ_j + h.c. (the holomorphic coefficients are ``gauge.fermion``): each Weyl
    pair w_pw_q is Ψ̄_A P_L Ψ_B (legs A~, B), its h.c. Ψ̄_B P_R Ψ_A; Γ = c_L P_L + c_R P_R = c + i c₂γ⁵."""
    weyl, b = fermion_fields(mb)
    if not weyl:
        return []
    majorana = {w.state for w in weyl if w.role == "maj"}
    size = len(mb.vacuum)
    acc: dict[tuple, list[complex]] = {}
    for degree, kind in ((1, "FFS"), (2, "FFSS")):
        h = np.zeros((size,) * degree + (len(mb.gauge.comp.weyl),) * 2, dtype=complex)
        for (i, j), poly in mb.gauge.fermion.items():
            t = derivative_tensor(gbm.shift(poly, mb.vacuum), degree, size)
            factor = 2.0 if i == j else 1.0                   # H_ii = 2h_ii; H_ij = H_ji = h_ij
            h[..., i, j] += factor * t
            if i != j:
                h[..., j, i] += t
        if not np.any(h):
            continue
        h = np.einsum("...ij,ip,jq->...pq", h, b, b)          # Bᵀ H B on the Weyl indices
        for _ in range(degree):
            h = np.moveaxis(np.tensordot(h, f.scalar_map, axes=([0], [0])), -1, -3)
        _collect_yukawas(h, weyl, f, kind, majorana, acc)
    return [MassVertex(kind, legs, (cl + cr) / 2, (cr - cl) / 2j) for (kind, legs), (cl, cr) in acc.items()]


def _collect_yukawas(h: np.ndarray, weyl: list[WeylState], f: Fields, kind: str, majorana: set[str],
                     acc: dict) -> None:
    """Add each holomorphic monomial w_pw_q Φ (= Ψ̄_X P_L Ψ_Y Φ, legs (leg(w_p), leg(w_q), Φ)) and its conjugate's
    P_R part (legs (conjleg(w_q), conjleg(w_p), Φ*))."""
    scale = max(1.0, float(np.max(np.abs(h))))
    n_s = len(f.scalars)
    from itertools import combinations_with_replacement, product
    scalar_sets = list(combinations_with_replacement(range(n_s), 1 if kind == "FFS" else 2))
    for p, q in product(range(len(weyl)), repeat=2):
        if q < p:
            continue
        for s_ in scalar_sets:
            value = h[s_ + (p, q)] if kind == "FFSS" else h[s_[0], p, q]
            if abs(value) <= TOLERANCE * scale:
                continue
            legs = tuple(f.scalars[x].leg(f.scalars[x].state in f.self_conjugate) for x in s_)
            conj = tuple(Symbol(f.scalars[x].state, not f.scalars[x].conj).leg(f.scalars[x].state in f.self_conjugate)
                         for x in s_)
            acc.setdefault((kind, (leg(weyl[p]), leg(weyl[q])) + legs), [0j, 0j])[0] += value
            acc.setdefault((kind, (conjleg(weyl[q]), conjleg(weyl[p])) + conj), [0j, 0j])[1] += np.conj(value)


# --- the vectors ----------------------------------------------------------------------------------------

@dataclass
class VectorFields:
    """The gauge-basis vectors, the mass-basis vector fields E (W and W* for the charged boson) and R[V, E]."""
    gauge: list[str]
    symbols: list[Symbol]
    rotation: np.ndarray
    self_conjugate: set[str]


def vector_fields(mb: MassBasis) -> VectorFields:
    """V_gauge = Σ R[V, E] E. In the unbroken phase W¹ = (W + W*)/√2 and W² = i(W − W*)/√2, with W the W⁺ field."""
    gauge = list(mb.gauge.comp.vectors)
    symbols, columns, real = [], [], set()
    r = 1 / math.sqrt(2)
    for name, amplitudes in mb.vector_states:
        if name == "W" and "W1" in gauge:
            for conj in (False, True):
                col = np.zeros(len(gauge), dtype=complex)
                col[gauge.index("W1")] = r
                col[gauge.index("W2")] = (-1j if conj else 1j) * r
                symbols.append(Symbol("W", conj))
                columns.append(col)
            continue
        if name == "W":                                            # below breaking: W is the W⁺ field itself
            for conj in (False, True):
                col = np.zeros(len(gauge), dtype=complex)
                col[gauge.index("W")] = 1.0 if not conj else 0.0
                symbols.append(Symbol("W", conj))
                columns.append(col)
            continue
        col = np.zeros(len(gauge), dtype=complex)
        for g, a in amplitudes.items():
            col[gauge.index(g)] = a
        symbols.append(Symbol(name))
        columns.append(col)
        real.add(name)
    return VectorFields(gauge, symbols, np.array(columns).T, real)


def _derived_vectors(mb: MassBasis) -> list[str]:
    """The vectors whose seagulls follow from their generator t^V (the SM's; a new vector with no stated seagull)."""
    gb = mb.gauge
    seagulled = {x for (a, b), p in gb.vector_mass.items() for x in (a, b) if any(k for k in p)}
    return [n for n in gb.gauge if n not in gb.explicit_vectors or n not in seagulled]


def _vector_mass_tensors(mb: MassBasis) -> tuple[np.ndarray, np.ndarray]:
    """∂M²_ab/∂y_k and ∂²M²_ab/∂y_k∂y_l for L ⊃ ½ Σ M²_ab(y) V_a V_b: from (t^a(v+y))·(t^b(v+y)) and the stated
    seagulls."""
    gb, v = mb.gauge, mb.vacuum
    n_v, size = len(gb.comp.vectors), len(v)
    d1 = np.zeros((n_v, n_v, size), dtype=complex)
    d2 = np.zeros((n_v, n_v, size, size), dtype=complex)
    index = {name: i for i, name in enumerate(gb.comp.vectors)}
    derived = [n for n in _derived_vectors(mb) if n in index]
    for a in derived:
        for b in derived:
            ta, tb = gb.gauge[a], gb.gauge[b]
            i, j = index[a], index[b]
            d1[i, j] += (ta @ v) @ tb + (tb @ v) @ ta
            d2[i, j] += ta.T @ tb + tb.T @ ta
    for (a, b), poly in gb.vector_mass.items():
        shifted = gbm.shift(poly, v)
        i, j = index[a], index[b]
        for target, degree in ((d1, 1), (d2, 2)):
            t = derivative_tensor(shifted, degree, size)
            target[i, j] += t
            if a != b:
                target[j, i] += t
    return d1, d2


def gauge_scalar_vertices(mb: MassBasis, f: Fields, vf: VectorFields) -> list[MassVertex]:
    """VSS (c = i Σ_a R M^a_bc with M^a = Aᵀt^aA), VVS and VVSS (derivatives of ½ Σ M²_ab(y) V_aV_b)."""
    out = []
    gb = mb.gauge
    index = {name: i for i, name in enumerate(gb.comp.vectors)}
    legs = [s.leg(s.state in f.self_conjugate) for s in f.scalars]
    vlegs = [s.leg(s.state in vf.self_conjugate) for s in vf.symbols]
    a_map, r = f.scalar_map, vf.rotation
    current = np.zeros((len(vf.symbols), a_map.shape[1], a_map.shape[1]), dtype=complex)
    for name, t in gb.gauge.items():
        if name in index:
            current += np.einsum("e,bc->ebc", r[index[name]], a_map.T @ t @ a_map)
    scale = max(1.0, float(np.max(np.abs(current)))) if current.size else 1.0
    for e in range(len(vf.symbols)):
        for b in range(a_map.shape[1]):
            for c in range(b + 1, a_map.shape[1]):
                if abs(current[e, b, c]) > TOLERANCE * scale:
                    out.append(MassVertex("VSS", (vlegs[e], legs[b], legs[c]), complex(1j * current[e, b, c])))
    d1, d2 = _vector_mass_tensors(mb)
    t1 = np.einsum("abk,ae,bf,kc->efc", d1, r, r, a_map)
    t2 = np.einsum("abkl,ae,bf,kc,ld->efcd", d2, r, r, a_map, a_map)
    from itertools import combinations_with_replacement
    s1 = max(1.0, float(np.max(np.abs(t1)))) if t1.size else 1.0
    for e, g in combinations_with_replacement(range(len(vf.symbols)), 2):
        for c in range(a_map.shape[1]):
            if abs(t1[e, g, c]) > TOLERANCE * s1:
                out.append(MassVertex("VVS", (vlegs[e], vlegs[g], legs[c]), complex(t1[e, g, c])))
            for d in range(c, a_map.shape[1]):
                if abs(t2[e, g, c, d]) > TOLERANCE * s1:
                    out.append(MassVertex("VVSS", (vlegs[e], vlegs[g], legs[c], legs[d]), complex(t2[e, g, c, d])))
    return out


def triple_gauge_vertices(mb: MassBasis, vf: VectorFields) -> list[MassVertex]:
    """VVV from L ⊃ −g ε^{abc}(∂_μW^a_ν)W^{bμ}W^{cν}: c = −i g ε_abc R R R (the rule i × V, D = ∂ − igT·W)."""
    if "W1" not in vf.gauge:
        return _broken_triple_gauge(vf)
    from adroit.model_building.indices import _levi_civita3
    idx = [vf.gauge.index(x) for x in ("W1", "W2", "W3")]
    eps = _levi_civita3()
    r = vf.rotation[idx]
    c = -1j * gbm.G2 * np.einsum("abc,ae,bf,cg->efg", eps, r, r, r)
    out = []
    names = [s.leg(s.state in vf.self_conjugate) for s in vf.symbols]
    from itertools import combinations
    for e, f_, g in combinations(range(len(vf.symbols)), 3):
        if abs(c[e, f_, g]) > TOLERANCE:
            out.append(MassVertex("VVV", (names[e], names[f_], names[g]), complex(c[e, f_, g])))
    return out


def _broken_triple_gauge(vf: VectorFields) -> list[MassVertex]:
    """Below breaking: W⁺W⁻γ and W⁺W⁻Z with the unbroken phase's couplings, −e and −g c_W in this convention, rotated
    with any neutral mixing."""
    cw = gbm.M_W / gbm.M_Z
    e, gz = gbm.G2 * math.sqrt(1 - cw * cw), gbm.G2 * cw
    out = []
    for k, s in enumerate(vf.symbols):
        if s.state == "W":
            continue
        c = -(e * vf.rotation[vf.gauge.index("A"), k] + gz * vf.rotation[vf.gauge.index("Z"), k])
        if abs(c) > TOLERANCE:
            out.append(MassVertex("VVV", ("W", "W~", s.leg(True)), complex(c)))
    return out


def broken_higgs_vertices(mb: MassBasis, f: Fields, vf: VectorFields) -> list[MassVertex]:
    """Below breaking, h's couplings to W and Z from m_W²(1 + h/v)² W⁺W⁻ + ½m_Z²(1 + h/v)² Z²: VVS 2m²/v, VVSS 2m²/v²
    (Z rotated with any neutral mixing)."""
    coords = mb.gauge.comp.coordinates
    k = next((i for i, c in enumerate(coords) if c.field == "h"), None)
    if k is None or "W1" in vf.gauge:
        return []
    v, out = gbm.V_EW, []
    legs = [s.leg(s.state in f.self_conjugate) for s in f.scalars]
    z = vf.gauge.index("Z")
    from itertools import combinations_with_replacement
    for a, la in enumerate(legs):
        if abs(f.scalar_map[k, a]) < TOLERANCE:
            continue
        out.append(MassVertex("VVS", ("W", "W~", la), 2 * gbm.M_W ** 2 / v * f.scalar_map[k, a]))
        for e, g in combinations_with_replacement(range(len(vf.symbols)), 2):
            if vf.symbols[e].state == "W" or vf.symbols[g].state == "W":
                continue
            c = 2 * gbm.M_Z ** 2 / v * vf.rotation[z, e] * vf.rotation[z, g] * f.scalar_map[k, a]
            if abs(c) > TOLERANCE:
                out.append(MassVertex("VVS", (vf.symbols[e].leg(True), vf.symbols[g].leg(True), la), c))
        for b in range(a, len(legs)):
            ab = f.scalar_map[k, a] * f.scalar_map[k, b]
            if abs(ab) > TOLERANCE:
                out.append(MassVertex("VVSS", ("W", "W~", la, legs[b]), 2 * gbm.M_W ** 2 / v ** 2 * ab))
                out.append(MassVertex("VVSS", ("Z", "Z", la, legs[b]), 2 * gbm.M_Z ** 2 / v ** 2 * ab))
    return out


# --- fermion currents ---------------------------------------------------------------------------------

def _weyl_currents(mb: MassBasis) -> dict[str, np.ndarray]:
    """G^V on the dark Weyl components, L ⊃ ψ† σ̄^μ G^V ψ V_μ: the SM's g T^a (−g T^a* on a conjugate block) and
    g′Y (−g′Y), and the stated currents Ψ̄_aγ(g_L P_L + g_R P_R)Ψ_b = g_L ξ_a†σ̄ξ_b − g_R η_b†σ̄η_a."""
    gb = mb.gauge
    n = len(gb.comp.weyl)
    out: dict[str, np.ndarray] = {v: np.zeros((n, n), dtype=complex) for v in gb.comp.vectors}
    if "W1" in out:
        from adroit.model_building.indices import su2_generators
        for i, w in enumerate(gb.comp.weyl):
            f = gb.spec.field(w.field)
            sign = 1 if w.block == "xi" else -1
            out["B"][i, i] += sign * gbm.G1 * f.charges.hypercharge
            t = su2_generators(f.charges.su2)
            ks = [k for k, x in enumerate(gb.comp.weyl) if x.field == w.field and x.block == w.block]
            row = ks.index(i)
            for a, label in enumerate(("W1", "W2", "W3")):
                gen = t[a] if w.block == "xi" else -np.conj(t[a])
                for col, j in enumerate(ks):
                    out[label][i, j] += gbm.G2 * gen[row, col]
    if "A" in out and "W1" not in out:                  # below breaking: a new charged singlet's eQ and Z coupling
        for i, w in enumerate(gb.comp.weyl):
            f = gb.spec.field(w.field)
            if f.role.value == "standard_model":
                continue
            photon, z = gbm.broken_charges(f)
            sign = 1 if w.block == "xi" else -1
            out["A"][i, i] += sign * photon
            out["Z"][i, i] += sign * z
    for term in gb.for_vertices:
        _explicit_current(mb, term, out)
    return out


_CURRENT = {"vector": (1.0, 1.0), "axial": (-1.0, 1.0)}             # γ^μ = γ(P_L + P_R), γ^μγ⁵ = γ(P_R − P_L)


def _explicit_current(mb: MassBasis, term, out: dict[str, np.ndarray]) -> None:
    """A stated current of dark fermions (a term with one vector and two dark fermions): four-component fields'
    γ^μ(1 or γ⁵), or left-handed Weyl fields' w†σ̄^μw."""
    gb, spec = mb.gauge, mb.gauge.spec
    fields = [spec.field(o.field) for o in term.fields]
    vectors = [f for f in fields if f.spin == 1]
    fermions = [o for o in term.fields if spec.field(o.field).spin == 0.5]
    if len(vectors) != 1 or len(fermions) != 2 or any(gbm._sm_fermion(spec.field(o.field)) for o in fermions):
        return
    if term.lorentz not in _CURRENT:
        raise gbm.GaugeBasisError(f"{term.text or term.coupling}: a {term.lorentz} current is not supported")
    k = gbm._value(spec, term)
    gl, gr = (k * x for x in _CURRENT[term.lorentz])
    bar = next((o for o in fermions if o.conjugate), fermions[0])
    other = fermions[1] if bar is fermions[0] else fermions[0]
    fa, fb = spec.field(bar.field), spec.field(other.field)
    if (fa.self_conjugate and fa.charges.su2 > 1) or (fb.self_conjugate and fb.charges.su2 > 1):
        raise gbm.GaugeBasisError(f"{term.text or term.coupling}: a stated current of a Majorana multiplet is not "
                                  "supported")
    g = out[vectors[0].name]
    weyl = [f.chirality in ("L", "R") and not f.self_conjugate for f in (fa, fb)]
    if weyl[0] != weyl[1]:
        raise gbm.GaugeBasisError(f"{term.text or term.coupling}: a current between a Weyl field and a four-component "
                                  "field is not supported; write both alike")
    if weyl[0] and (fa.chirality != fb.chirality or term.lorentz != "vector"):
        raise gbm.GaugeBasisError(f"{term.text or term.coupling}: a stated current of Weyl fields is supported between "
                                  "two left-handed or two right-handed fields (lorentz \"vector\")")
    d = np.zeros_like(g)
    if weyl[0] and fa.chirality == "R":
        _right_handed_current(gb, term, fa, fb, k, d)
        _hermitian_current(term, d, k)
        g += d
        return
    for m in range(fa.charges.su2):
        xa = gb.comp.weyl_index[(fa.name, "xi", m)]
        xb = gb.comp.weyl_index[(fb.name, "xi", m)]
        d[xa, xb] += gl
        if term.plus_hc and fa.name != fb.name:
            d[xb, xa] += np.conj(gl)
        if weyl[0]:                                     # a left-handed Weyl current w†σ̄w: no right-handed part
            continue
        ea = gb.comp.weyl_index[(fa.name, "xi" if fa.self_conjugate else "eta", m)]
        eb = gb.comp.weyl_index[(fb.name, "xi" if fb.self_conjugate else "eta", m)]
        d[eb, ea] += -gr
        if term.plus_hc and fa.name != fb.name:
            d[ea, eb] += -np.conj(gr)
    _hermitian_current(term, d, k, fa.self_conjugate and fa.name == fb.name)
    g += d


def _right_handed_current(gb, term, fa, fb, k: complex, d: np.ndarray) -> None:
    """A current of right-handed Weyl fields, ψ_Ra†σ^μψ_Rb (L-9, 2026-11-21: a B − L model's ν_R current had been
    refused). A right-handed field is its conjugate block, ψ_R = η† (``gauge_basis.add_fermion``), so
    ψ_Ra†σ^μψ_Rb = η_a σ^μ η_b† = −η_b†σ̄^μη_a: the coupling enters on the η components, transposed and with the opposite
    sign, as the right-handed part of a four-component current does (``_explicit_current``: −g_R)."""
    for m in range(fa.charges.su2):
        ea = gb.comp.weyl_index[(fa.name, "eta", m)]
        eb = gb.comp.weyl_index[(fb.name, "eta", m)]
        d[eb, ea] += -k
        if term.plus_hc and fa.name != fb.name:
            d[ea, eb] += -np.conj(k)


def _hermitian_current(term, d: np.ndarray, k: complex, own_majorana: bool = False) -> None:
    """A stated current is a hermitian w†σ̄ G w (G = G†) that does not vanish. Ψ̄₁γ^μΨ₂ between two Majorana fields
    is anti-hermitian, so its coupling is imaginary (i e_D χ̄₁γχ₂, as the papers write it); a real one, or its
    "+ h.c.", had been read silently (Berlin et al.'s reference had lost the i: the closure audit, G12)."""
    scale = max(abs(k), 1e-300)
    if np.max(np.abs(d - d.conj().T), initial=0.0) > 1e-9 * scale:
        raise gbm.GaugeBasisError(f"{term.text or term.coupling}: the current is not hermitian (between two Majorana "
                                  "fields Ψ̄₁γ^μΨ₂ needs an imaginary coupling, i g; between distinct Dirac or Weyl "
                                  "fields, + h.c.)")
    if abs(k) > 0 and np.max(np.abs(d), initial=0.0) <= 1e-9 * scale:
        if own_majorana:
            raise gbm.GaugeBasisError(f"{term.text or term.coupling}: a Majorana field has no vector current "
                                      "(χ̄γ^μχ = 0); write its axial current χ̄γ^μγ⁵χ")
        raise gbm.GaugeBasisError(f"{term.text or term.coupling}: the current vanishes (a real coupling of Ψ̄₁γ^μΨ₂ "
                                  "between two Majorana fields with its + h.c.); write i g without + h.c.")


def current_vertices(mb: MassBasis, vf: VectorFields) -> list[MassVertex]:
    """FFV of the dark fermions: G′ = B† G B in the mass basis, each w_p†σ̄w_q as Ψ̄_Pγ P_L Ψ_Q (both on the particle
    side) or −Ψ̄_Qγ P_R Ψ_P (both on the antiparticle side); a Majorana pair once, a diagonal Majorana as −G γγ⁵."""
    weyl, b = fermion_fields(mb)
    if not weyl:
        return []
    majorana = {w.state for w in weyl if w.role == "maj"}
    currents = _weyl_currents(mb)
    index = {name: i for i, name in enumerate(mb.gauge.comp.vectors)}
    acc: dict[tuple, list[complex]] = {}
    names = [s.leg(s.state in vf.self_conjugate) for s in vf.symbols]
    for e in range(len(vf.symbols)):
        g = sum(vf.rotation[index[v], e] * (b.conj().T @ m @ b) for v, m in currents.items() if v in index)
        if not isinstance(g, np.ndarray):
            continue
        scale = max(1.0, float(np.max(np.abs(g))))
        for p in range(len(weyl)):
            for q in range(len(weyl)):
                if abs(g[p, q]) > TOLERANCE * scale:
                    _add_current(acc, weyl[p], weyl[q], g[p, q], names[e], majorana)
    return [MassVertex("FFV", legs, (gl + gr) / 2, (gr - gl) / 2) for legs, (gl, gr) in acc.items()]


def _add_current(acc: dict, p: WeylState, q: WeylState, coef: complex, vector: str, majorana: set[str]) -> None:
    """w_p†σ̄w_q V = Ψ̄_X γ P_L Ψ_Y V with legs (conjleg(w_p), leg(w_q), V); for one Majorana field,
    λ†σ̄λ = Ψ̄γP_LΨ = −½Ψ̄γγ⁵Ψ, so with the identical-field 2 the vertex is γ(P_L − P_R) × coef."""
    cell = acc.setdefault((conjleg(p), leg(q), vector), [0j, 0j])
    cell[0] += coef
    if p == q and p.role == "maj":
        cell[1] += -coef


# --- the Standard Model's fermions -----------------------------------------------------------------------

@dataclass(frozen=True)
class SMFermion:
    """A Standard Model fermion in its mass basis."""
    name: str
    mass: float
    charge: float
    t3: float                 # of its left-handed part
    colour: str
    partner: str              # its SU(2) partner (u ↔ d, ν ↔ e)
    up: bool                  # up-type (H̃ Yukawa) or not


def _sm_fermion_list() -> list[SMFermion]:
    """The fermions at their kinematic masses (``kinematics.KINEMATIC_MASSES``: b the DMsimp card's 4.7 GeV)."""
    from adroit.core.kinematics import KINEMATIC_MASSES as KIN
    out = []
    for up, down in (("u", "d"), ("c", "s"), ("t", "b")):
        out += [SMFermion(up, KIN[up], 2 / 3, 0.5, "3", down, True),
                SMFermion(down, KIN[down], -1 / 3, -0.5, "3", up, False)]
    for lep, nu in (("e", "nu_e"), ("mu", "nu_mu"), ("tau", "nu_tau")):
        out += [SMFermion(nu, 0.0, 0.0, 0.5, "1", lep, True), SMFermion(lep, KIN[lep], -1.0, -0.5, "1", nu, False)]
    return out


SM_FERMIONS = _sm_fermion_list()
RUNNING = ("b", "c")                    # Yukawas with the MS-bar mass at m_h (as ``constraints.higgs``)


def yukawa_mass(name: str) -> float:
    """The mass in a Standard Model fermion's Yukawa coupling, y = m/v: m_b and m_c run (one loop, MS-bar, from
    m̄_b(m̄_b) = 4.18 and m̄_c(m̄_c) = 1.27 GeV) to m_h, as the library's Higgs widths take them; t and the leptons
    at their pole masses, u, d, s at the PDG MS-bar masses at 2 GeV (``derivation.STANDARD_MODEL``). The kinematic
    masses are separate (``SM_FERMIONS``, from ``kinematics.KINEMATIC_MASSES``)."""
    if name in RUNNING:
        from adroit.constraints.higgs import running_mass
        return running_mass(name, gbm.M_H)
    from adroit.library.interactions.derivation import STANDARD_MODEL
    return 0.0 if name.startswith("nu") else STANDARD_MODEL[f"m_{name}"][0]
GENERIC = {"q": [f.name for f in SM_FERMIONS if f.colour == "3"],
           "l": ["e", "mu", "tau"], "nu": ["nu_e", "nu_mu", "nu_tau"], "L": ["e", "mu", "tau", "nu_e", "nu_mu", "nu_tau"],
           "Q": [f.name for f in SM_FERMIONS if f.colour == "3"], "qL": [f.name for f in SM_FERMIONS if f.colour == "3"],
           "lL": ["e", "mu", "tau", "nu_e", "nu_mu", "nu_tau"], "QL": [f.name for f in SM_FERMIONS if f.colour == "3"],
           **{f"L{s}{x}": [x, f"nu_{x}"] for x in ("e", "mu", "tau") for s in ("", "_")}}   # one lepton doublet: Le, L_mu, …
LEFT = ("nu", "L", "Q", "qL", "QL", "lL", "Le", "Lmu", "Ltau", "L_e", "L_mu", "L_tau")
RIGHT = {"uR": "u", "dR": "d", "eR": "e", "muR": "mu", "tauR": "tau"}
RIGHT_GENERATIONS = {"uR": ["u", "c", "t"], "dR": ["d", "s", "b"], "eR": ["e", "mu", "tau"]}


def sm_names(field: str, generations: int = 1) -> tuple[list[str], str]:
    """The SM fermions a spec field stands for, and its chirality ("" both, "L" or "R"). A right-handed name is its
    first-generation flavour, or with ``generations`` 3 all three, as the Standard Model's own uR, dR and eR are
    declared (``spec.SM_FIELDS``)."""
    if field in RIGHT:
        if generations == 1:
            return [RIGHT[field]], "R"
        if generations == 3 and field in RIGHT_GENERATIONS:
            return RIGHT_GENERATIONS[field], "R"
        raise gbm.GaugeBasisError(f"{field} with {generations} generations: G2 reads uR, dR and eR as one generation "
                                  "or three; name the flavours otherwise")
    if field in GENERIC:
        return GENERIC[field], "L" if field in LEFT else ""
    if not any(f.name == field for f in SM_FERMIONS):
        raise gbm.GaugeBasisError(f"{field}: not a Standard Model fermion G2 knows; name it by flavour (u, d, e, nu_e, "
                                  f"…), by chirality ({', '.join(RIGHT)}), or for all flavours "
                                  f"({', '.join(GENERIC)})")
    return [field], "L" if field.startswith("nu") else ""


def _sm_gauge_currents(mb: MassBasis) -> dict[str, dict[tuple[str, str], list[complex]]]:
    """Gauge vector → {(f₁, f₂): [g_L, g_R]} for L ⊃ f̄₁γ(g_L P_L + g_R P_R)f₂ V, in the gauge basis."""
    out: dict[str, dict] = {v: {} for v in mb.gauge.comp.vectors}
    def add(v: str, a: str, b: str, gl: complex, gr: complex) -> None:
        cell = out[v].setdefault((a, b), [0j, 0j])
        cell[0] += gl
        cell[1] += gr
    by = {f.name: f for f in SM_FERMIONS}
    for f in SM_FERMIONS:
        if "W3" in out:
            add("W3", f.name, f.name, gbm.G2 * f.t3, 0)
            add("B", f.name, f.name, gbm.G1 * (f.charge - f.t3), gbm.G1 * f.charge if f.mass or f.charge else 0)
            p = by[f.partner]
            add("W1", f.name, p.name, gbm.G2 / 2, 0)
            add("W2", f.name, p.name, (-0.5j if f.t3 > 0 else 0.5j) * gbm.G2, 0)
        else:
            cw = gbm.M_W / gbm.M_Z
            sw2 = 1 - cw * cw
            e = gbm.G2 * math.sqrt(sw2)
            add("A", f.name, f.name, e * f.charge, e * f.charge)
            add("Z", f.name, f.name, gbm.G2 / cw * (f.t3 - sw2 * f.charge), -gbm.G2 / cw * sw2 * f.charge)
    for term in mb.gauge.for_vertices:
        _sm_explicit_current(mb, term, out)
    return out


def _sm_explicit_current(mb: MassBasis, term, out: dict) -> None:
    """A stated current of SM fermions, k f̄γ(1 or γ⁵)f V (a chiral field keeps its projection)."""
    spec = mb.gauge.spec
    fields = [spec.field(o.field) for o in term.fields]
    vectors = [f for f in fields if f.spin == 1]
    sm = [o for o in term.fields if gbm._sm_fermion(spec.field(o.field))]
    if len(vectors) != 1 or len(sm) != 2 or len(fields) != 3 or sm[0].field != sm[1].field:
        return
    if term.lorentz not in _CURRENT:
        raise gbm.GaugeBasisError(f"{term.text or term.coupling}: a {term.lorentz} current of SM fermions is not "
                                  "supported")
    names, chirality = sm_names(sm[0].field, spec.field(sm[0].field).generations)
    for name in names:
        k = _sm_coupling(spec, term, name)
        gl, gr = (k * x for x in _CURRENT[term.lorentz])
        if chirality == "L":
            gr = 0
        elif chirality == "R":
            gl = 0
        cell = out[vectors[0].name].setdefault((name, name), [0j, 0j])
        cell[0] += gl
        cell[1] += gr


def _sm_coupling(spec, term, name: str) -> complex:
    """A term's coupling for one SM flavour: m_q, m_l and m_f stand for that flavour's mass in its Yukawa, under the
    model's declared convention (``yukawa.mass``; the default "sm": m_b and m_c running to m_h, as in h's own Yukawa,
    so that a stated m_q/v·tanβ is tanβ times h's; the audit's G1-12, G12: the pole masses had made it 1.39 tanβ for
    the b); e, α, s_W² and v are G1's (``gauge_basis.ELECTROWEAK``). The Standard Model Higgs boson's own Yukawas
    (``_sm_yukawas``) and the kinematic masses do not depend on it."""
    from adroit.library.interactions.derivation import evaluate_expression, symbol_table
    from adroit.model_building import yukawa
    mass = yukawa.mass(spec.yukawa, name)               # the model's declared Yukawa inputs (decision #2)
    table = symbol_table(spec, {"m_q": mass, "m_l": mass, "m_f": mass}, gbm.ELECTROWEAK)
    return evaluate_expression(term.coupling, table, allow_complex=True)


def sm_vertices(mb: MassBasis, f: Fields, vf: VectorFields) -> list[MassVertex]:
    """The SM fermions' FFV (gauge currents rotated to the mass basis; W directly below breaking) and FFS (each
    scalar state's H⁰ and H⁺ components)."""
    out = []
    index = {name: i for i, name in enumerate(mb.gauge.comp.vectors)}
    vlegs = [s.leg(s.state in vf.self_conjugate) for s in vf.symbols]
    if "W1" not in index:                                                       # below breaking: W± directly
        for up in (x for x in SM_FERMIONS if x.up):
            g = gbm.G2 / math.sqrt(2)                                           # (g/√2) ū γ P_L d W⁺ + h.c.
            out += [MassVertex("FFV", (f"{up.name}~", up.partner, "W"), g / 2, -g / 2),
                    MassVertex("FFV", (f"{up.partner}~", up.name, "W~"), g / 2, -g / 2)]
    for v, pairs in _sm_gauge_currents(mb).items():
        for e in range(len(vf.symbols)):
            weight = vf.rotation[index[v], e]
            if abs(weight) < TOLERANCE:
                continue
            for (a, b), (gl, gr) in pairs.items():
                out.append(MassVertex("FFV", (f"{a}~", b, vlegs[e]), weight * (gl + gr) / 2, weight * (gr - gl) / 2))
    out += _sm_yukawas(mb, f)
    return _merge(out)


def _sm_yukawas(mb: MassBasis, f: Fields) -> list[MassVertex]:
    """−(m_f/v)(y_re f̄f + i s_f y_im f̄γ⁵f) from H⁰ (s_f = −1 up-type), and H⁺ ū(y_u P_L − y_d P_R)d + h.c. with
    y = √2 m/v; below breaking, −(m_f/v) h f̄f."""
    coords = mb.gauge.comp.coordinates
    def find(field: str, m: float, part: str) -> int | None:
        return next((k for k, c in enumerate(coords) if c.field == field and c.m == m and c.part == part), None)
    legs = [s.leg(s.state in f.self_conjugate) for s in f.scalars]
    a = f.scalar_map
    out = []
    v = gbm.V_EW
    re0, im0 = (find("H", -0.5, "re"), find("H", -0.5, "im")) if "H" in mb.gauge.comp.scalar_forms else \
        (find("h", 0.0, "r"), None)
    rep, imp = find("H", 0.5, "re"), find("H", 0.5, "im")
    by = {x.name: x for x in SM_FERMIONS}
    for idx, leg in enumerate(legs):
        for x in SM_FERMIONS:
            if not x.mass:
                continue
            y = yukawa_mass(x.name) / v
            c = -y * (a[re0, idx] if re0 is not None else 0)
            c2 = -y * (-1 if x.up else 1) * (a[im0, idx] if im0 is not None else 0)
            if abs(c) > TOLERANCE or abs(c2) > TOLERANCE:
                out.append(MassVertex("FFS", (f"{x.name}~", x.name, leg), c, c2))
        if rep is None:
            continue
        hp = (a[rep, idx] + 1j * a[imp, idx]) / math.sqrt(2)       # coefficient of Φ in H⁺
        hm = (a[rep, idx] - 1j * a[imp, idx]) / math.sqrt(2)       # in H⁻
        for up in (x for x in SM_FERMIONS if x.up):
            down = by[up.partner]
            yu, yd = math.sqrt(2) * yukawa_mass(up.name) / v, math.sqrt(2) * yukawa_mass(down.name) / v
            for coef, legs_, cl, cr in ((hp, (f"{up.name}~", down.name, leg), yu, -yd),
                                        (hm, (f"{down.name}~", up.name, leg), -yd, yu)):
                if abs(coef) > TOLERANCE and (cl or cr):
                    out.append(MassVertex("FFS", legs_, coef * (cl + cr) / 2, coef * (cr - cl) / 2j))
    return out


def _oriented(x: MassVertex) -> MassVertex:
    """A fermion vertex with its two fermion slots in name order: swapping them is Ψ̄_XΓΨ_Y = Ψ̄_YᶜΓ′Ψ_Xᶜ,
    Γ′ = CΓᵀC⁻¹, which keeps a scalar or pseudoscalar coupling and reverses a vector one (γ^μ → −γ^μ)."""
    if x.kind not in ("FFS", "FFSS", "FFV") or x.legs[0] <= x.legs[1]:
        return x
    legs = (x.legs[1], x.legs[0]) + x.legs[2:]
    return MassVertex(x.kind, legs, -x.c if x.kind == "FFV" else x.c, x.c2, x.colour)


def _merge(vertices: list[MassVertex]) -> list[MassVertex]:
    """Sum the vertices with the same kind and legs (fermion slots in canonical order)."""
    acc: dict[tuple, MassVertex] = {}
    for x in map(_oriented, vertices):
        key = (x.kind, x.legs, x.colour)
        if x.kind == "FFFF":
            old = acc.get(key)
            structure = (old.structure if old else ()) + x.structure
            acc[key] = MassVertex(x.kind, x.legs, 0.0, 0.0, x.colour, structure)
            continue
        if key in acc:
            acc[key] = MassVertex(x.kind, x.legs, acc[key].c + x.c, acc[key].c2 + x.c2, x.colour)
        else:
            acc[key] = x
    return [x for x in acc.values() if abs(x.c) > TOLERANCE or abs(x.c2) > TOLERANCE
            or any(abs(c) > 0 for _, _, c in x.structure)]


# --- stated Yukawas with SM fermions ------------------------------------------------------------------

def _scalar_coefficients(mb: MassBasis, f: Fields, name: str, conj: bool) -> np.ndarray:
    """The coefficient of each Φ_a in a gauge-singlet scalar field (or its conjugate): Σ_k form_k A[k, a]."""
    forms = mb.gauge.comp.scalar_forms[name]
    if len(forms) != 1:
        raise gbm.GaugeBasisError(f"{name}: a stated Yukawa with SM fermions needs a gauge-singlet scalar")
    form = forms[0]
    out = np.zeros(f.scalar_map.shape[1], dtype=complex)
    for k, c in form.items():
        out += (np.conj(c) if conj else c) * f.scalar_map[k]
    return out


def sm_yukawa_vertices(mb: MassBasis, f: Fields) -> list[MassVertex]:
    """Stated Yukawas with SM fermions: k S f̄(1 or iγ⁵)f (a mediator's), and k S Ψ̄_D P_R f + h.c. (a t-channel
    partner's: in Weyl form ξ_D†η_f†, whose conjugate η_f ξ_D = f̄ P_L Ψ_D)."""
    spec, out = mb.gauge.spec, []
    weyl, b = fermion_fields(mb)
    majorana = {w.state for w in weyl if w.role == "maj"}
    legs = [s.leg(s.state in f.self_conjugate) for s in f.scalars]
    conj_legs = [Symbol(s.state, not s.conj).leg(s.state in f.self_conjugate) for s in f.scalars]
    for term in mb.gauge.for_vertices:
        fields = [spec.field(o.field) for o in term.fields]
        if any(x.spin == 1 for x in fields) or len(fields) != 3:
            continue
        scalar = next(o for o in term.fields if spec.field(o.field).spin == 0)
        fermions = [o for o in term.fields if spec.field(o.field).spin == 0.5]
        sm = [o for o in fermions if gbm._sm_fermion(spec.field(o.field))]
        if len(sm) == 2 and _is_doublet(spec.field(scalar.field)):
            out += _doublet_yukawa(mb, f, term, scalar, sm, legs)
            continue
        phi = _scalar_coefficients(mb, f, scalar.field, scalar.conjugate)
        if len(sm) == 2:
            out += _mediator_yukawa(spec, term, sm[0].field, phi, legs, conj_legs)
        elif len(sm) == 1 and term.lorentz == "chiral":
            dark = next(o for o in fermions if o is not sm[0])
            out += _partner_yukawa(mb, term, dark.field, sm[0].field, phi, weyl, b, majorana, legs, conj_legs)
        else:
            raise gbm.GaugeBasisError(f"{term.text or term.coupling}: a Yukawa with SM fermions of this form is not "
                                      "supported")
    return out


def _is_doublet(field) -> bool:
    return field.spin == 0 and field.charges.su2 == 2 and abs(field.charges.hypercharge - 0.5) < 1e-9 \
        and field.role.value != "standard_model"


def _doublet_yukawa(mb: MassBasis, f: Fields, term, scalar, sm, legs) -> list[MassVertex]:
    """A second Higgs doublet Φ (Y = ½)'s stated Yukawa with SM fermions (the owner, 2026-10-15): k Q̄Φd_R, k L̄Φe_R
    or k Q̄Φ̃u_R (Φ̃ = iσ₂Φ*), + h.c., per flavour. It is the SM's own Yukawa with y_f → −k_f along Φ's coordinates
    (``_sm_yukawas``): Φ⁰'s real and imaginary parts give k f̄f and the pseudoscalar coupling, Φ⁺ gives the charged
    vertices ū P_R d (down-type) or d̄ P_R u (up-type, from Φ̃).

    The generator's Weyl form, k Q u_R^c Φ, k Q d_R^c Φ* or k L e_R^c Φ* + h.c. (``model_building.spec``: the doublet
    unconjugated, the right-handed field conjugated), is the hermitian conjugate of the Dirac form, ε_ij Q_i Φ_j ū_R
    being (ε_ij Q̄_i Φ*_j u_R)†: it is read as the Dirac form with k → k* (G12's live check L9)."""
    spec = mb.gauge.spec
    left, right, dirac, factor = _yukawa_orientation(term, scalar, sm)
    flavours, _ = sm_names(right.field, spec.field(right.field).generations)
    up = right.field == "uR"
    order = _epsilon_order(term, left.field)
    coords = mb.gauge.comp.coordinates
    def find(m: float, part: str) -> int | None:
        return next((k for k, c in enumerate(coords) if c.field == scalar.field and c.m == m and c.part == part), None)
    re0, im0, rep, imp = find(-0.5, "re"), find(-0.5, "im"), find(0.5, "re"), find(0.5, "im")
    a, by, out = f.scalar_map, {x.name: x for x in SM_FERMIONS}, []
    for name in flavours:
        x = by[name]
        stated = _sm_coupling(spec, term, name) * factor
        y = -(stated if dirac else np.conj(stated)) * order      # the SM's y_f = √2 m_f/v ↔ −k_f
        k = -y
        partner = by[x.partner]
        for idx, leg in enumerate(legs):
            # k Φ⁰ d̄_L d_R + h.c. with Φ⁰ = (φ_re + iφ_im)/√2 (Φ⁰* for up-type, through Φ̃): φ_re (Re k + i Im k γ⁵)/√2,
            # φ_im (∓Im k + i(±Re k)γ⁵)/√2, in Γ = c + i c₂γ⁵ (the audit's G1-6, G12: a complex k had given
            # non-hermitian vertices)
            ar = a[re0, idx] if re0 is not None else 0.0
            ai = (-1 if up else 1) * (a[im0, idx] if im0 is not None else 0.0)
            c = (k.real * ar - k.imag * ai) / math.sqrt(2)
            c2 = (k.imag * ar + k.real * ai) / math.sqrt(2)
            if abs(c) > TOLERANCE or abs(c2) > TOLERANCE:
                out.append(MassVertex("FFS", (f"{name}~", name, leg), c, c2))
            if rep is None:
                continue
            hp = (a[rep, idx] + 1j * a[imp, idx]) / math.sqrt(2)
            hm = (a[rep, idx] - 1j * a[imp, idx]) / math.sqrt(2)
            u, d = (x, partner) if up else (partner, x)
            pieces = ((hp, (f"{u.name}~", d.name, leg), 0.0, -y),                       # the h.c. carries k*
                      (hm, (f"{d.name}~", u.name, leg), -np.conj(y), 0.0)) if not up \
                else ((hp, (f"{u.name}~", d.name, leg), np.conj(y), 0.0), (hm, (f"{d.name}~", u.name, leg), 0.0, y))
            if not term.plus_hc:
                pieces = pieces[:1] if not up else pieces[1:]
            for coef, legs_, cl, cr in pieces:
                if abs(coef) > TOLERANCE and (cl or cr):
                    out.append(MassVertex("FFS", legs_, coef * (cl + cr) / 2, coef * (cr - cl) / 2j))
    return out


LORENTZ_OF_DOUBLET_YUKAWA = {"scalar": 1.0, "chiral": 1.0, "pseudoscalar": 1j}


def _yukawa_orientation(term, scalar, sm) -> tuple:
    """(the left-handed doublet, the right-handed field, whether the term is in Dirac form, the factor its Lorentz
    label puts on the coupling) of a doublet Yukawa, or the reason it cannot be read: Q̄Φd_R, L̄Φe_R, Q̄Φ̃u_R (Dirac)
    or Q d_R^c Φ*, L e_R^c Φ*, Q u_R^c Φ (Weyl), + h.c.

    Between a left-handed doublet and a right-handed singlet there is one chiral structure. "scalar" and "chiral" are
    it; in the Dirac form "pseudoscalar", Q̄Φ iγ⁵ d_R, is the same operator with the coupling times i, since
    γ⁵ d_R = d_R (the external audit's A01, 2026-10-16: the label had been ignored, changing the CP structure). Any
    other label, and "pseudoscalar" in the Weyl form, is refused."""
    right = next((o for o in sm if o.field in RIGHT), None)
    left = next((o for o in sm if o is not right), None)
    dirac = right is not None and left is not None and left.conjugate and not right.conjugate
    weyl = right is not None and left is not None and not left.conjugate and right.conjugate
    if not (dirac or weyl):
        raise gbm.GaugeBasisError(f"{term.text or term.coupling}: a doublet Yukawa is written as the left-handed doublet "
                                  "conjugated, the doublet scalar and a right-handed field (Q̄Φd_R, L̄Φe_R, Q̄Φ̃u_R), or "
                                  "in the generator's Weyl form (Q d_R^c Φ*, L e_R^c Φ*, Q u_R^c Φ)")
    if not term.plus_hc:
        raise gbm.GaugeBasisError(f"{term.text or term.coupling}: a doublet Yukawa is written with its + h.c.")
    up = right.field == "uR"
    if scalar.conjugate != (up if dirac else not up):
        raise gbm.GaugeBasisError(f"{term.text or term.coupling}: an up-type Yukawa takes Φ̃ = iσ₂Φ* (the scalar "
                                  "conjugated), a down-type or lepton one Φ itself (the reverse in the Weyl form)")
    factor = LORENTZ_OF_DOUBLET_YUKAWA.get(term.lorentz)
    if factor is None or (factor != 1.0 and not dirac):
        raise gbm.GaugeBasisError(f"{term.text or term.coupling}: a doublet Yukawa's Lorentz structure is 'scalar' or "
                                  "'chiral' (or, in the Dirac form, 'pseudoscalar': the coupling times i), not "
                                  f"{term.lorentz!r}; write a CP phase in the coupling (e.g. I*k)")
    return left, right, dirac, factor


def _epsilon_order(term, left: str) -> int:
    """+1 for Q̄Φ̃u_R written ε[i,j] Q̄_i Φ*_j (ε₁₂ = +1, the guide's form), −1 for ε[j,i] (the audit's G1-7, G12:
    the indices were not read, so the reversed order kept the sign); +1 without an ε."""
    import re
    eps = re.search(r"eps\[\s*(\w+)\s*,\s*(\w+)\s*\]", term.indices or "")
    mine = re.search(rf"\b{re.escape(left)}\*?\[\s*(\w+)", term.indices or "")
    if not eps or not mine:
        return 1
    return -1 if mine.group(1) == eps.group(2) else 1


def _mediator_yukawa(spec, term, field: str, phi, legs, conj_legs) -> list[MassVertex]:
    out = []
    names, _ = sm_names(field, spec.field(field).generations)
    for name in names:
        k = _sm_coupling(spec, term, name)
        for a, coef in enumerate(phi):
            if abs(coef) < TOLERANCE:
                continue
            value = k * coef
            if term.lorentz == "chiral":
                # c S f̄P_R f = (c/2)(1 + γ⁵), i.e. Γ = c + i c₂γ⁵ with c₂ = −ic/2; with its conjugate c*P_L the sum is
                # Re(c) + i Im(c)γ⁵ (the audit's G1-5, G12: it had been read as a pseudoscalar of twice the size)
                c, c2 = value / 2, -0.5j * value
                hc = (np.conj(value) / 2, 0.5j * np.conj(value))
            else:
                c, c2 = (value, 0j) if term.lorentz == "scalar" else (0j, value)
                hc = (np.conj(c), np.conj(c2))
            out.append(MassVertex("FFS", (f"{name}~", name, legs[a]), c, c2))
            if term.plus_hc:
                out.append(MassVertex("FFS", (f"{name}~", name, conj_legs[a]), *hc))
    return out


def _partner_yukawa(mb, term, dark: str, field: str, phi, weyl, b, majorana, legs, conj_legs) -> list[MassVertex]:
    """k S Ψ̄_D P_R f + h.c. = k S ξ_D†η_f† + k* S* η_f ξ_D: with ξ_D = Σ B w, the vertex (f~, leg(w), S*) with
    c_L = k* B[ξ_D, w] and (conjleg(w), f, S) with c_R = k B*[ξ_D, w]."""
    spec, out = mb.gauge.spec, []
    names, _ = sm_names(field, spec.field(field).generations)
    i = mb.gauge.comp.weyl_index[(dark, "xi", 0)]
    for name in names:
        k = _sm_coupling(spec, term, name)
        for wi, w in enumerate(weyl):
            amp = b[i, wi]
            if abs(amp) < TOLERANCE:
                continue
            for a, coef in enumerate(phi):
                if abs(coef) < TOLERANCE:
                    continue
                cr = k * np.conj(amp) * coef
                out.append(MassVertex("FFS", (conjleg(w), name, legs[a]), cr / 2, cr / 2j))
                cl = np.conj(k) * amp * np.conj(coef)
                out.append(MassVertex("FFS", (f"{name}~", leg(w), conj_legs[a]), cl / 2, -cl / 2j))
    return out


# --- four-fermion contacts ------------------------------------------------------------------------------

def contact_vertices(mb: MassBasis) -> list[MassVertex]:
    """The contact terms k (Ψ̄_DΓΨ_D)(f̄Γ'f) (``gauge_basis._contact_shape``) as FFFF vertices, one per Standard Model
    flavour, k evaluated per flavour (m_q, m_l). The dark field must be its own mass state (a Dirac state, or a
    Majorana one with a real rotation): its bilinears are then the mass state's. A Weyl Standard Model field's bilinear
    is its chiral current, f̄γ^μP_{L,R}f = ½(V ∓ A). The vertex's coefficient is k itself (``tree``: the engine takes
    every contraction); a term written with + h.c. adds its conjugate, k* times the same hermitian operator."""
    spec, out = mb.gauge.spec, []
    for term in mb.gauge.for_vertices:
        if term.lorentz not in gbm.CONTACT:
            continue
        dark, sm = spec.field(term.fields[0].field), spec.field(term.fields[2].field)
        bar, own = _dark_contact_legs(mb, dark.name, term)
        first, second = term.lorentz[0], term.lorentz[1]
        names, _ = sm_names(sm.name, sm.generations)
        for name in names:
            k = _sm_coupling(spec, term, name)
            if term.plus_hc:
                k = k + np.conj(k)
            if sm.chirality:
                sign = -1.0 if sm.chirality == "L" else 1.0
                structure = ((first, "V", k / 2), (first, "A", sign * k / 2))
            else:
                structure = ((first, second, k),)
            out.append(MassVertex("FFFF", (bar, own, f"{name}~", name), 0.0, 0.0, "", structure))
    return out


def _dark_contact_legs(mb: MassBasis, field: str, term) -> tuple[str, str]:
    """(Ψ̄, Ψ) legs of a dark field that is its own mass state, or GaugeBasisError saying why it is not."""
    weyl, b = fermion_fields(mb)
    index = mb.gauge.comp.weyl_index
    where = term.text or term.coupling
    rows = [index[(field, part, 0)] for part in ("xi", "eta") if (field, part, 0) in index]
    used = {w.state for k, w in enumerate(weyl) for i in rows if abs(b[i, k]) > TOLERANCE}
    if len(used) != 1:
        raise gbm.GaugeBasisError(f"{where}: the dark fermion {field} mixes with others ({len(used)} mass states); a "
                                  "contact term is supported for a dark fermion that is its own mass state")
    state = used.pop()
    phases = [b[i, k] for k, w in enumerate(weyl) for i in rows if abs(b[i, k]) > TOLERANCE]
    majorana = all(w.role == "maj" for w in weyl if w.state == state)
    if majorana:
        if any(abs(z * z - 1) > 1e-9 for z in phases):
            raise gbm.GaugeBasisError(f"{where}: {field}'s mass state is rotated by a complex phase (a negative "
                                      "Majorana mass), which would exchange its S and P bilinears")
        return state, state
    if len(phases) != 2 or abs(phases[0] - np.conj(phases[1])) > 1e-9:
        raise gbm.GaugeBasisError(f"{where}: {field}'s left and right components are rephased differently")
    return f"{state}~", state


# --- the strong interaction -----------------------------------------------------------------------------

def gluon_vertices(mb: MassBasis, g_s: float) -> list[MassVertex]:
    """g_s couplings of every coloured state, in the tree engine's colour conventions (its default structures δ,
    T(a, triplet slot, antitriplet slot), f(1,2,3), {T^a, T^b}). The signs are the engine's gauge-consistent set,
    read from MadGraph's MSSM through ``ufo_model`` and checked against the hand-written φφ* → gg
    (docs/g3_tree.md, docs/g2_feynman_rules.md):
    - q̄ q g and a triplet fermion's: FFV, c = −g_s;
    - an octet fermion's: FFV, c = −ig_s;
    - a triplet scalar's: VSS, c = −g_s; its seagull: VVSS, c = g_s²;
    - the gluon's own vertex: VVV, c = −ig_s.
    A colour-octet scalar is not supported."""
    out = [MassVertex("FFV", (f"{q.name}~", q.name, "g"), -g_s) for q in SM_FERMIONS if q.colour == "3"]
    out.append(MassVertex("VVV", ("g", "g", "g"), -1j * g_s))
    for st in mb.spectrum.states:
        if st.colour == "1" or st.spin == 1:
            continue
        self_conjugate = st.kind in ("real", "majorana")
        anti = st.name if self_conjugate else f"{st.name}~"
        if st.spin == 0.5:
            out.append(MassVertex("FFV", (anti, st.name, "g"), -1j * g_s if st.colour == "8" else -g_s))
        elif st.colour == "8":
            raise gbm.GaugeBasisError(f"{st.name}: a colour-octet scalar's gluon couplings are not supported")
        else:
            out += [MassVertex("VSS", ("g", st.name, anti), -g_s), MassVertex("VVSS", ("g", "g", st.name, anti), g_s ** 2)]
    return out


# --- widths --------------------------------------------------------------------------------------------

def _momentum(m: float, m1: float, m2: float) -> float:
    lam = (m * m - (m1 + m2) ** 2) * (m * m - (m1 - m2) ** 2)
    return math.sqrt(max(lam, 0.0)) / (2 * m)


def _chiral(v: MassVertex) -> tuple[complex, complex]:
    """(c_L, c_R) of an FFS (c + ic₂γ⁵) or FFV (γ(c + c₂γ⁵)) vertex."""
    if v.kind == "FFS":
        return v.c - 1j * v.c2, v.c + 1j * v.c2
    return v.c - v.c2, v.c + v.c2


def two_body_width(v: MassVertex, decaying: int, masses: list[float], colour: float = 1.0) -> float:
    """Γ of the vertex's leg ``decaying`` into the other two (closed forms; ``colour`` the colour sum over the
    decaying particle's dimension). A fermion leg decays by ``_fermion_decay``. The identical-particle ½ is the
    caller's."""
    m = masses[decaying]
    rest = [k for k in range(3) if k != decaying]
    m1, m2 = masses[rest[0]], masses[rest[1]]
    p = _momentum(m, m1, m2)
    if p <= 0:
        return 0.0
    c2 = abs(v.c) ** 2
    if v.kind in ("FFS", "FFV") and decaying < 2:
        return float(_fermion_decay(v, m, masses[1 - decaying], masses[2], p) * colour)
    if v.kind == "SSS":
        total = c2 * p / (8 * math.pi * m * m)
    elif v.kind in ("FFS", "FFV"):
        cl, cr = _chiral(v)
        dot = (m * m - m1 * m1 - m2 * m2) / 2
        if v.kind == "FFS":
            sq = 2 * (abs(cl) ** 2 + abs(cr) ** 2) * dot - 4 * m1 * m2 * (cl * np.conj(cr)).real
            total = p / (8 * math.pi * m * m) * sq
        else:
            sq = (abs(cl) ** 2 + abs(cr) ** 2) * (2 * m * m - m1 * m1 - m2 * m2 - (m1 * m1 - m2 * m2) ** 2 / (m * m)) \
                + 12 * m1 * m2 * (cl * np.conj(cr)).real
            total = p / (24 * math.pi * m * m) * sq
    elif v.kind == "VSS" and decaying == 0:
        total = c2 * p ** 3 / (6 * math.pi * m * m)
    elif v.kind == "VSS":
        mv = masses[0]
        total = c2 * p ** 3 / (2 * math.pi * mv * mv) if mv > 0 else 0.0
    elif v.kind == "VVS" and decaying == 2:
        if m1 == 0 or m2 == 0:
            return 0.0
        total = c2 * p / (8 * math.pi * m * m) * (2 + (m * m - m1 * m1 - m2 * m2) ** 2 / (4 * m1 * m1 * m2 * m2))
    elif v.kind == "VVS":
        mv = masses[rest[0]] if rest[0] < 2 else masses[rest[1]]
        if mv == 0:
            return 0.0
        total = c2 * p / (8 * math.pi * m * m) / 3 * (2 + (m * m + mv * mv - masses[2] ** 2) ** 2 / (4 * m * m * mv * mv))
    else:
        return 0.0
    return float(total * colour)


def _fermion_decay(v: MassVertex, m: float, m_f: float, m_b: float, p: float) -> float:
    """Γ(F → f S) or Γ(F → f V) from ū_f Γ(c_L P_L + c_R P_R) u_F, averaged over F's spin:
    Σ|M|² = (|c_L|² + |c_R|²)(m² + m_f² − m_S²) + 4 m m_f Re c_L c_R* for a scalar, and
    (|c_L|² + |c_R|²)(m² + m_f² − 2M² + (m² − m_f²)²/M²) − 12 m m_f Re c_L c_R* for a vector of mass M (none for a
    massless one: a gauge-invariant model has no tree-level F → f γ)."""
    cl, cr = _chiral(v)
    norm, mixed = abs(cl) ** 2 + abs(cr) ** 2, (cl * np.conj(cr)).real
    if v.kind == "FFS":
        sq = norm * (m * m + m_f * m_f - m_b * m_b) + 4 * m * m_f * mixed
    elif m_b > 0:
        sq = norm * (m * m + m_f * m_f - 2 * m_b * m_b + (m * m - m_f * m_f) ** 2 / (m_b * m_b)) - 12 * m * m_f * mixed
    else:
        return 0.0
    return max(p / (16 * math.pi * m * m) * sq, 0.0)


# --- the model ----------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ParticleRecord:
    """A particle of the generated model (``constraints.tree.Particle``'s fields)."""
    name: str
    spin: float
    mass: float
    anti: str
    colour: str
    charge: float
    parity: int
    width: float = 0.0


@dataclass
class Rules:
    """A typed model's Feynman rules in the mass basis: particles (widths included) and vertices."""
    particles: list[ParticleRecord]
    vertices: list[MassVertex]
    g_s: float
    notes: list[str] = field(default_factory=list)


def _particles(mb: MassBasis) -> list[ParticleRecord]:
    out = []
    for s in mb.spectrum.states:
        self_conjugate = s.kind in ("real", "majorana", "vector")
        out.append(ParticleRecord(s.name, s.spin, s.mass_gev, "" if self_conjugate else f"{s.name}~", s.colour,
                                  s.charge, s.parity))
    for q in SM_FERMIONS:
        out.append(ParticleRecord(q.name, 0.5, q.mass, f"{q.name}~", q.colour, q.charge, 1))
    out.append(ParticleRecord("g", 1, 0.0, "", "8", 0.0, 1))
    return out


def vertices(mb: MassBasis, g_s: float) -> list[MassVertex]:
    """Every vertex of the model's physical states (module docstring)."""
    f, vf = scalar_fields(mb), vector_fields(mb)
    out = (scalar_vertices(mb, f) + yukawa_vertices(mb, f) + gauge_scalar_vertices(mb, f, vf)
           + triple_gauge_vertices(mb, vf) + current_vertices(mb, vf) + sm_vertices(mb, f, vf)
           + sm_yukawa_vertices(mb, f) + broken_higgs_vertices(mb, f, vf) + gluon_vertices(mb, g_s)
           + contact_vertices(mb))
    return _merge(out)


def _colour_factor(decaying: str, finals: list[str]) -> float | None:
    """Σ_colours |δ|² over the decaying particle's colours, for the δ structures a two-body decay can have."""
    coloured = [c for c in finals if c != "1"]
    if decaying == "1":
        return {0: 1.0, 2: float({"3": 3, "3bar": 3, "8": 8}[coloured[0]]) if len(coloured) == 2 else None}.get(
            len(coloured))
    return 1.0 if len(coloured) == 1 else None


def widths(particles: list[ParticleRecord], vertex_list: list[MassVertex]) -> dict[str, float]:
    """Tree-level two-body widths of every boson, from the closed forms of ``two_body_width``. Fermions are given
    no width: here they are exchanged only in the t- and u-channels."""
    by = {p.name: p for p in particles}
    by |= {p.anti: p for p in particles if p.anti}
    out = {p.name: 0.0 for p in particles}
    for p in particles:
        if p.spin == 0.5 or p.mass <= 0:
            continue
        for v in vertex_list:
            if v.kind not in ("SSS", "FFS", "FFV", "VSS", "VVS") or v.legs.count(p.name) != 1:
                continue
            k = v.legs.index(p.name)
            others = [by[x] for i, x in enumerate(v.legs) if i != k]
            masses = [by[x].mass for x in v.legs]
            if sum(o.mass for o in others) >= p.mass:
                continue
            colour = _colour_factor(p.colour, [o.colour for o in others])
            if colour is None:
                continue
            width = two_body_width(v, k, masses, colour)
            out[p.name] += width * (0.5 if v.legs[(k + 1) % 3] == v.legs[(k + 2) % 3] else 1.0)
    return out


def feynman_rules(mb: MassBasis, g_s: float | None = None) -> Rules:
    """The model's Feynman rules: particles with their tree-level widths, and every vertex. g_s is α_s at the dark
    matter's mass unless given."""
    if g_s is None:
        from adroit.constraints.higgs import alpha_s
        g_s = math.sqrt(4 * math.pi * alpha_s(max(mb.spectrum.dark_matter().mass_gev, 1.0)))
    particles = _particles(mb)
    vs = vertices(mb, g_s)
    w = widths(particles, vs)
    particles = [ParticleRecord(p.name, p.spin, p.mass, p.anti, p.colour, p.charge, p.parity, w.get(p.name, 0.0))
                 for p in particles]
    return Rules(particles, vs, g_s)
