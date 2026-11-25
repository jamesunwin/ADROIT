"""Whether two typed models are the same physics (G10's deterministic check of an agent's model).

Two writings of one model may name their fields differently, order their terms differently, and differ by field
redefinitions (a phase, a sign, a chiral rotation). What they must share is what G1 and G2 compute:

- **the spectrum:** every mass-basis state's spin, electric charge, colour, Z₂ parity and mass, as a multiset;
- **the vertices, under one mapping of the particles** (``_mappings``): each of the second model's new states is
  mapped onto a state of the first with the same signature (a complex one onto its particle or, charge-conjugated,
  its antiparticle), the Standard Model's onto themselves, and every mapping the spectrum allows is tried. Under a
  mapping, the vertices are compared leg by leg (``_canonical``: G2's slots carry the barred spinor and the
  current's momentum order), each pair equal up to one phase;
- **the phases, solved globally** (``_rephasable``): a field redefinition multiplies each vertex by e^{iΣθ}, with a
  real phase θ for each complex field and a sign for each self-conjugate one, and G1 fixes every mass real and
  positive. The phases must come from one such redefinition, a linear system modulo 2π whose integer kernel leaves
  a GF(2) system for the signs. So g_u = g_d and g_u = −g_d for a Z′ differ, as do vector and axial couplings, and a
  relative complex phase between two vertices (g S P*Q + i g T P*Q against g S P*Q + g T P*Q), while a Z′ written with
  the opposite sign throughout, a complex field rephased, or a term written as its own conjugate does not.

The external audit of 2026-10-16 (A02, A03) found that the comparison had keyed states by signature, so degenerate
species could swap from vertex to vertex, and had compared the couplings of vertices with a complex field by
magnitude alone; it also used c ∓ c₂ for a scalar vertex's chiral parts, where G2's are c ∓ ic₂. A writing the
comparison cannot map (more than ``MAX_MAPPINGS`` mappings among degenerate states; a charge conjugation that would
join one field's particle to another's antiparticle) is "not established", never equal. (The audit's G1-1, G12, had
found the earlier √(|c|² + |c₂|²), which equated a vector Z′ with an axial one.)

Masses agree to ``MASS_TOLERANCE`` (relative), couplings to ``COUPLING_TOLERANCE`` (relative, with an absolute
floor).

**The SM Higgs, as a diagnostic.** A model written in the unbroken phase always has G1's SM-like h; one written in
the broken phase as a simplified model has it only if it declares it. ``compare(..., without_sm_higgs=True)`` sets
aside the SM-like h (spin 0, even, neutral, at M_H) and its vertices on both sides, to say whether that is the only
difference. It is a diagnosis, not a pass: the two models still differ by the h.

**Decision D19 (the owner, 2026-10-15).** ``compare(..., d19=True)`` sets the SM-like h aside only where, in both
models, no vertex joins it to a new state: every leg of every vertex with the h is a Standard Model particle. Such
an h changes no dark-matter observable; an h that couples to anything new (a Higgs portal, a mixing scalar) is compared as
usual. **Extended (the owner, 2026-10-15):** an h whose only vertices with new states come through the vector portal
(h Z A′ and h A′ A′ at O(ε), where A′ mixes kinetically with a Standard Model vector) is also set aside: a dark
photon written in the unbroken phase has them, and the same model written as a broken-phase simplified model does
not. The guide keeps the agent in the unbroken phase, where G1 checks gauge
invariance. (D19's other half, a degenerate partner compared at the paper's exact degeneracy rather than the zoo's
regulator, is the gate script's.) The comparison is the precision G1 and G2 test themselves at: an agent's model that passes reproduces the
hand-written one's spectrum and Feynman rules.
"""

from __future__ import annotations

import dataclasses
import math
from collections import defaultdict

from adroit.core.model_spec import ModelSpec
from adroit.core.state import StrictModel

MASS_TOLERANCE = 1e-5
COUPLING_TOLERANCE = 1e-4
COUPLING_FLOOR = 1e-9


class Equivalence(StrictModel):
    """The verdict: equal or not, whether the comparison could be made at all (``established``: a writing it cannot
    map is "not established", never equal), and every difference found."""
    equal: bool
    established: bool = True
    differences: list[str]


def _signature(p) -> tuple:
    """A state's signature: spin, charge, colour, Z₂ parity, mass (rounded to the tolerance's scale)."""
    return (p.spin, round(p.charge, 4), p.colour, p.parity, p.mass)


def _same_mass(a: float, b: float) -> bool:
    return abs(a - b) <= MASS_TOLERANCE * max(abs(a), abs(b), 1e-3)


def _is_sm_higgs(p) -> bool:
    from adroit.model_building.gauge_basis import M_H
    return p.spin == 0 and p.parity == 1 and abs(p.charge) < 1e-9 and _same_mass(p.mass, M_H)


def _without_sm_higgs(rules):
    """G2's rules without the SM-like h and its vertices (module docstring)."""
    gone = {p.name for p in rules.particles if _is_sm_higgs(p)}
    return dataclasses.replace(rules, particles=[p for p in rules.particles if p.name not in gone],
                               vertices=[v for v in rules.vertices if not gone & set(v.legs)])


def _sm_names(rules) -> set[str]:
    """The Standard Model particles of G2's rules, and their antiparticles."""
    from adroit.model_building.ufo_export import SM_NAMES
    return {x for p in rules.particles if p.name in SM_NAMES for x in (p.name, p.anti) if x}


def portal_vectors(spec: ModelSpec) -> frozenset[str]:
    """The new vectors that mix kinetically with a Standard Model one (a ``kinetic_mixing`` term)."""
    out = set()
    for t in spec.terms:
        if t.lorentz == "kinetic_mixing":
            out |= {o.field for o in t.fields if spec.field(o.field).role.value != "standard_model"}
    return frozenset(out)


def sm_higgs_alone(rules, portal: frozenset[str] = frozenset()) -> bool:
    """Whether no vertex joins the SM-like h to a new state, other than the vectors of ``portal`` (D19; module
    docstring). True where there is no h."""
    sm = _sm_names(rules) | set(portal)
    higgs = {p.name for p in rules.particles if _is_sm_higgs(p)}
    return all(set(v.legs) <= sm for v in rules.vertices if higgs & set(v.legs))


def _states(rules) -> list[tuple]:
    out = []
    for p in rules.particles:
        out.append(_signature(p))
        if p.anti:
            out.append((p.spin, round(-p.charge, 4), {"3": "3bar", "3bar": "3"}.get(p.colour, p.colour), p.parity,
                        p.mass))
    return sorted(out, key=lambda s: (s[0], s[1], s[2], s[3], s[4]))


def _match_states(a: list[tuple], b: list[tuple]) -> list[str]:
    """Differences between two spectra (multisets of signatures, masses to tolerance)."""
    out, pool = [], list(b)
    for s in a:
        found = next((k for k, t in enumerate(pool) if t[:4] == s[:4] and _same_mass(t[4], s[4])), None)
        if found is None:
            out.append(f"the state (spin {s[0]}, charge {s[1]:+g}, colour {s[2]}, parity {s[3]:+d}) at {s[4]:.6g} GeV "
                       "has no counterpart")
        else:
            pool.pop(found)
    out += [f"the state (spin {t[0]}, charge {t[1]:+g}, colour {t[2]}, parity {t[3]:+d}) at {t[4]:.6g} GeV is extra"
            for t in pool]
    return out


def _names(rules) -> dict[str, tuple]:
    """Every particle and antiparticle name → its state signature."""
    out = {}
    for p in rules.particles:
        out[p.name] = _signature(p)
        if p.anti:
            out[p.anti] = (p.spin, round(-p.charge, 4), {"3": "3bar", "3bar": "3"}.get(p.colour, p.colour), p.parity,
                           p.mass)
    return out


MAX_MAPPINGS = 5040   # 7!: the most particle mappings tried among degenerate states before "not established"
PHASE_TOLERANCE = 1e-3


class _Unsupported(Exception):
    """A writing the comparison cannot map: the answer is "equivalence not established", never "equal"."""


@dataclasses.dataclass(frozen=True)
class _Field:
    name: str
    anti: str          # the antiparticle's name; "" for a self-conjugate field
    sig: tuple
    sm: bool


def _fields(rules) -> list[_Field]:
    sm = _sm_names(rules)
    return [_Field(p.name, p.anti if p.anti and p.anti != p.name else "", _signature(p), p.name in sm)
            for p in rules.particles]


def _anti_sig(sig: tuple) -> tuple:
    return (sig[0], round(-sig[1], 4), {"3": "3bar", "3bar": "3"}.get(sig[2], sig[2]), sig[3], sig[4])


def _fits(x: tuple, y: tuple) -> bool:
    return x[:4] == y[:4] and _same_mass(x[4], y[4])


def _mappings(fa: list[_Field], fb: list[_Field]):
    """Every one-to-one map of the second model's fields onto the first's that the spectrum allows, as
    {name: (name, conjugated)}: a Standard Model field onto itself; a new field onto a field of the same signature, a
    complex one onto the other's particle or, where the signatures allow, its antiparticle (charge conjugation).
    One mapping holds across every vertex (the external audit's A02, 2026-10-16: states had been keyed by signature,
    so degenerate species could swap from vertex to vertex). Raises _Unsupported past ``MAX_MAPPINGS``."""
    by_name = {f.name: f for f in fa}
    fixed, free = {}, []
    for f in fb:
        if f.sm:
            if f.name not in by_name:
                raise _Unsupported(f"the Standard Model field {f.name} is in one model only")
            fixed[f.name] = (f.name, False)
        else:
            free.append(f)
    pool = [f for f in fa if not f.sm]
    count = 0

    def options(f: _Field, used: set[str]):
        for g in pool:
            if g.name in used or bool(g.anti) != bool(f.anti):
                continue
            if _fits(f.sig, g.sig):
                yield g.name, False
            if g.anti and _fits(f.sig, _anti_sig(g.sig)):
                yield g.name, True

    def walk(i: int, used: set[str], chosen: dict):
        nonlocal count
        if i == len(free):
            count += 1
            if count > MAX_MAPPINGS:
                raise _Unsupported(f"more than {MAX_MAPPINGS} mappings of degenerate states")
            yield {**fixed, **chosen}
            return
        f = free[i]
        for name, conj in dict.fromkeys(options(f, used)):
            yield from walk(i + 1, used | {name}, {**chosen, f.name: (name, conj)})
    yield from walk(0, set(), {})


def _leg_names(mapping: dict, fa: list[_Field], fb: list[_Field]) -> tuple[dict[str, str], set[str]]:
    """(each of the second model's leg names → the first's, the second's leg names whose field is conjugated)."""
    anti = {f.name: f.anti for f in fa}
    names, conjugated = {}, set()
    for f in fb:
        target, conj = mapping[f.name]
        names[f.name] = anti[target] if conj and anti[target] else target
        if f.anti:
            names[f.anti] = target if conj else anti[target]
        if conj:
            conjugated |= {f.name, f.anti}
    return names, conjugated


def _chiral(kind: str, c: complex, c2: complex) -> tuple[complex, complex]:
    """(c_L, c_R) of an FFS (c + ic₂γ⁵) or FFV (γ(c + c₂γ⁵)) vertex (``feynman._chiral``; the old comparison had used
    c ∓ c₂ for both)."""
    return (c - 1j * c2, c + 1j * c2) if kind == "FFS" else (c - c2, c + c2)


def _canonical(kind: str, legs: list[str], c: complex, c2: complex, conjugated: list[bool], real: set[str]):
    """The vertex with its legs in one order and the sign the reordering implies, or None where a charge conjugation
    would join one field's particle to another's antiparticle (not compared).

    G2's slots carry meaning: a fermion pair's first slot is the barred spinor, so (x, y~) with the particle first is
    the charge-conjugated, transposed form of ȳΓx; and a VSS vertex's two scalar slots carry the current's momentum
    order. So a pair of fermions is ordered by name with ψ̄₁Γψ₂ = ψ̄₂ᶜ(CΓᵀC⁻¹)ψ₁ᶜ (a vector coupling changes sign;
    axial, scalar and pseudoscalar do not), a VSS current's scalars with the current's sign, and a VVV vertex's legs
    with the permutation's sign. A charge-conjugated field needs no sign of its own: its renamed legs are G2's
    transposed form, which the ordering then resolves."""
    legs = list(legs)
    if kind in ("FFS", "FFV"):
        if conjugated[0] != conjugated[1]:
            return None
        if legs[0] > legs[1]:
            legs[0], legs[1] = legs[1], legs[0]
            if kind == "FFV":
                c = -c
        return (kind, tuple(legs[:2]) + tuple(sorted(legs[2:]))), (c, c2)
    if kind == "VSS":
        if conjugated[1] != conjugated[2]:
            return None
        if legs[1] > legs[2]:
            legs[1], legs[2] = legs[2], legs[1]
            c, c2 = -c, -c2
        return (kind, tuple(legs)), (c, c2)
    order = sorted(range(len(legs)), key=lambda k: legs[k])
    if kind == "VVV" and _odd_permutation(order):
        c, c2 = -c, -c2
    return (kind, tuple(legs[k] for k in order)), (c, c2)


def _odd_permutation(order: list[int]) -> bool:
    seen, odd = set(), False
    for start in range(len(order)):
        length, k = 0, start
        while k not in seen:
            seen.add(k)
            k = order[k]
            length += 1
        odd ^= length > 0 and length % 2 == 0
    return odd


def _table(rules, names: dict[str, str], conjugated: set[str], real: set[str]) -> dict[tuple, list]:
    """{canonical key: [(c, c2)]} of a model's vertices, legs renamed by ``names``; raises _Unsupported for a vertex
    the renaming cannot express."""
    out = defaultdict(list)
    for v in rules.vertices:
        c, c2 = complex(v.c), complex(getattr(v, "c2", 0.0))
        if max(abs(c), abs(c2)) <= COUPLING_FLOOR:
            continue
        found = _canonical(v.kind, [names.get(x, x) for x in v.legs], c, c2, [x in conjugated for x in v.legs], real)
        if found is None:
            raise _Unsupported(f"a {v.kind} vertex charge-conjugates one of its fields only")
        out[found[0]].append(found[1])
    return out


def _sizes(kind: str, pair: tuple[complex, complex]) -> tuple[float, float]:
    if kind in ("FFS", "FFV"):
        left, right = _chiral(kind, *pair)
        return abs(left), abs(right)
    return abs(pair[0]), abs(pair[1])


def _phase(x: tuple[complex, complex], y: tuple[complex, complex]) -> float | None:
    """The one phase φ with y = e^{iφ} x for both parts (a field rephasing multiplies a whole vertex), or None."""
    k = max(range(2), key=lambda i: abs(x[i]))
    if abs(x[k]) <= COUPLING_FLOOR:
        return 0.0 if max(abs(t) for t in y) <= COUPLING_FLOOR else None
    phi = math.atan2((y[k] / x[k]).imag, (y[k] / x[k]).real)
    rotated = [complex(math.cos(phi), math.sin(phi)) * t for t in x]
    scale = max([abs(t) for t in x + y] + [0.0])
    return phi if all(abs(r - t) <= COUPLING_TOLERANCE * scale + COUPLING_FLOOR for r, t in zip(rotated, y)) else None


def _integer_kernel(rows: list[list[int]], n: int) -> list[list[int]]:
    """A Z-basis of {k ∈ Zⁿ : Σⱼ rows[i][j] kⱼ = 0 for every i}: column reduction with a unimodular record."""
    a = [list(r) for r in rows]
    u = [[int(i == j) for j in range(n)] for i in range(n)]

    def combine(j: int, k: int, q: int) -> None:          # column j −= q × column k
        for m in a + u:
            m[j] -= q * m[k]

    def swap(j: int, k: int) -> None:
        for m in a + u:
            m[j], m[k] = m[k], m[j]
    col = 0
    for row in a:
        if col >= n:
            break
        for j in range(col + 1, n):
            while row[j]:
                if not row[col] or abs(row[j]) < abs(row[col]):
                    swap(col, j)
                    continue
                combine(j, col, row[j] // row[col])
        if row[col]:
            col += 1
    return [[u[i][j] for i in range(n)] for j in range(col, n)]


def _rephasable(rows: list[tuple[dict[str, int], frozenset[str], float]]) -> bool:
    """Whether field redefinitions give every vertex its phase (the external audit's A03, 2026-10-16): rows
    (exponents of the complex fields, the self-conjugate fields odd in the vertex, φ), solved as
    Σ_f n_f θ_f + π Σ_r m_r s_r ≡ φ (mod 2π) with θ real and s ∈ {0, 1}. The continuous θ are eliminated by the
    integer kernel of the exponents: each kernel vector k needs k·φ = π t with t an integer, and its signs a parity
    (Σ_v k_v m_v)·s ≡ t (mod 2), the GF(2) system the old comparison solved alone, having dropped the phases of
    vertices with a complex field."""
    complex_fields = sorted({f for n, _, _ in rows for f in n})
    matrix = [[n.get(f, 0) for n, _, _ in rows] for f in complex_fields]
    gf2 = []
    for k in _integer_kernel(matrix, len(rows)):
        total = sum(kv * phi for kv, (_, _, phi) in zip(k, rows)) / math.pi
        t = round(total)
        if abs(total - t) > PHASE_TOLERANCE * max(1, sum(abs(x) for x in k)):
            return False
        odd = set()
        for kv, (_, m, _) in zip(k, rows):
            if kv % 2:
                odd ^= set(m)
        gf2.append((odd, t % 2))
    return _flips_solve(gf2)


def _flips_solve(rows: list[tuple[set, int]]) -> bool:
    """Whether some sign flips of the self-conjugate fields give every row's parity — Gaussian elimination over
    GF(2)."""
    pivots: list[tuple[object, set, int]] = []
    for fields, rhs in rows:
        fields = set(fields)
        for pivot, pfields, prhs in pivots:
            if pivot in fields:
                fields ^= pfields
                rhs ^= prhs
        if fields:
            pivots.append((min(fields, key=str), fields, rhs))
        elif rhs:
            return False
    return True


def _match(table_a: dict, table_b: dict, fa: list[_Field]) -> list[str]:
    """The differences between two models' vertex tables under one mapping (empty: the same physics)."""
    complex_of = {}
    for f in fa:
        if f.anti:
            complex_of[f.name], complex_of[f.anti] = (f.name, 1), (f.name, -1)
    out, rows = [], []
    for key in sorted(set(table_a) | set(table_b), key=str):
        x, y = table_a.get(key, []), table_b.get(key, [])
        if len(x) != len(y):
            out.append(f"{key[0]} vertices on {', '.join(key[1])}: {len(x)} against {len(y)}")
            continue
        x, y = (sorted(t, key=lambda e: _sizes(key[0], e)) for t in (x, y))
        for vx, vy in zip(x, y):
            if not _close(_sizes(key[0], vx), _sizes(key[0], vy)):
                out.append(f"a {key[0]} vertex's coupling on {', '.join(key[1])}: "
                           f"{max(_sizes(key[0], vx)):.6g} against {max(_sizes(key[0], vy)):.6g}")
                continue
            phi = _phase(vx, vy)
            if phi is None:
                out.append(f"a {key[0]} vertex on {', '.join(key[1])} differs in its structure")
                continue
            exponents: dict[str, int] = defaultdict(int)
            for leg in key[1]:
                if leg in complex_of:
                    exponents[complex_of[leg][0]] += complex_of[leg][1]
            odd = frozenset(leg for leg in key[1] if leg not in complex_of and key[1].count(leg) % 2)
            rows.append(({f: n for f, n in exponents.items() if n}, odd, phi))
    if not out and not _rephasable(rows):
        out.append("the couplings' relative signs or phases differ: no rephasing of the fields maps one onto the other")
    return out


def _close(x: tuple, y: tuple) -> bool:
    scale = max([abs(t) for t in x + y] + [0.0])
    return all(abs(p - q) <= COUPLING_TOLERANCE * scale + COUPLING_FLOOR for p, q in zip(x, y))


def _vertices_match(ra, rb) -> tuple[bool, list[str]]:
    """(established, differences) of two models' vertices: equal under some mapping (``_mappings``), or the
    differences of the first mapping tried; not established where no mapping can be tried."""
    fa, fb = _fields(ra), _fields(rb)
    real_a = {f.name for f in fa if not f.anti}
    table_a = _table(ra, {}, set(), real_a)
    first, unsupported = None, ""
    try:
        for mapping in _mappings(fa, fb):
            names, conjugated = _leg_names(mapping, fa, fb)
            try:
                table_b = _table(rb, names, conjugated, real_a)
            except _Unsupported as why:
                unsupported = str(why)
                continue
            diffs = _match(table_a, table_b, fa)
            if not diffs:
                return True, []
            first = first if first is not None else diffs
    except _Unsupported as why:
        return False, [f"equivalence not established: {why}"]
    if first is None:
        return False, [f"equivalence not established: {unsupported or 'no mapping of the states'}"]
    return True, first


def compare(a: ModelSpec, b: ModelSpec, without_sm_higgs: bool = False, d19: bool = False) -> Equivalence:
    """Whether two models have the same spectrum and vertices (module docstring); either failing to build is a
    difference. ``without_sm_higgs`` sets the SM-like h aside on both sides (a diagnosis); ``d19`` does so only where
    neither model joins it to a new state (decision D19; module docstring)."""
    from adroit.model_building import feynman, spectrum
    rules = []
    for label, spec in (("first", a), ("second", b)):
        try:
            rules.append(feynman.feynman_rules(spectrum.compute(spec)))
        except Exception as error:                     # noqa: BLE001 - a model G1 refuses is a difference
            return Equivalence(equal=False, differences=[f"the {label} model does not build: {error}"])
    if without_sm_higgs or (d19 and all(sm_higgs_alone(r, portal_vectors(s)) for r, s in zip(rules, (a, b)))):
        rules = [_without_sm_higgs(r) for r in rules]
    diffs = _match_states(_states(rules[0]), _states(rules[1]))
    established = True
    if not diffs:
        established, diffs = _vertices_match(rules[0], rules[1])
    return Equivalence(equal=established and not diffs, established=established, differences=diffs)
