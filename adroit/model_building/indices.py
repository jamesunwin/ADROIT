"""Gauge-index contractions of a model's terms (G1): representation matrices, invariant tensors, and the index
notation of ``ModelTerm.indices``.

**Bases.** An SU(2) multiplet of dimension n = 2j + 1 is held in the spherical basis, its components ordered
m = j, j − 1, …, −j, with the Condon–Shortley generators: T₃ = diag(m), T± = T₁ ± iT₂ and
T₊|m⟩ = √(j(j+1) − m(m+1)) |m+1⟩. For the doublet this is (φ⁺, φ⁰) of a Y = ½ field, and T^a = σ^a/2. A real
multiplet (odd n, Y = 0, self-conjugate) obeys φ_{−m} = (−1)^m φ_m*; for the triplet that is
φ_{±1} = ∓(φ₁ ∓ iφ₂)/√2, φ₀ = φ₃ (``cart`` converts). SU(3): the fundamental's generators are t^a = λ^a/2
(Gell-Mann), the antifundamental's −(t^a)ᵀ, the adjoint's (T^a)_{bc} = −i f^{abc}.

**The notation.** A term's ``indices`` is a product of factors, each a field or an invariant tensor with its
indices in brackets; a repeated index is summed:

    H*[i] phi[i] phi*[j] H[j]           (H†φ)(φ†H)
    eps[i,j] D[i] H[j] S                 ε^{ij} D_i H_j S, with ε₁₂ = +1
    H*[i] sigma[A,i,j] H[j] cart[A,m] Delta[m]      (H†σ^A H) Δ^A, Δ a real triplet

- A field factor is the field's name, with ``*`` for its conjugate, and its indices: the SU(2) index first (if the
  field is not an SU(2) singlet), then the colour index (if it is coloured). ``F*[m]`` is the conjugate of F's
  component m. A conjugate is not a lowered index.
- SU(2) tensors:
  - ``delta[i,j]``;
  - ``eps[i,j]`` (doublets);
  - ``metric[m,n]``, the invariant bilinear of any dimension: (−1)^m δ_{n,−m} for integer j, ε for
    half-integer j;
  - ``sigma[A,i,j]`` (Pauli);
  - ``T[A,m,n]``, the generator in the representation of the field that carries m;
  - ``cart[A,m]``, a triplet's Cartesian component A from its spherical ones (``cartc[A,m]`` for a
    conjugated triplet: (φ^A)* = Σ U*_{Am} φ_m*). A runs over 1–3.
- Colour tensors:
  - ``delta[c,d]``;
  - ``lam[a,c,d]`` (t^a = λ^a/2);
  - ``f[a,b,c]``;
  - ``eps3[c,d,e]``.

**Defaults.** Without ``indices``, a term's contraction is the unique invariant when there is one and it pairs
each field with its conjugate (δ, or the metric for two real or two identical fields). Otherwise the term must
state its indices, and ``contraction`` says so.
"""

from __future__ import annotations

import math
import re
import string
from functools import lru_cache

import numpy as np

from adroit.core.model_spec import ModelField, ModelSpec, ModelTerm

TENSOR_ARITY = {"delta": 2, "eps": 2, "metric": 2, "sigma": 3, "T": 3, "cart": 2, "cartc": 2, "lam": 3, "f": 3,
                "eps3": 3}
COLOUR_DIM = {"1": 1, "3": 3, "3bar": 3, "8": 8}
_FACTOR = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)(\*?)(?:\[([^\]]*)\])?")


class IndexError_(ValueError):
    """A term's contraction cannot be built: the reason says what to state."""


# --- representation matrices ------------------------------------------------------------------------

@lru_cache(maxsize=None)
def su2_generators(n: int) -> np.ndarray:
    """(T₁, T₂, T₃) of SU(2) in dimension n, spherical basis m = j … −j (shape (3, n, n))."""
    j = (n - 1) / 2
    m = j - np.arange(n)
    plus = np.zeros((n, n), dtype=complex)
    for k in range(1, n):                               # T₊ raises m: row k−1 (m + 1), column k (m)
        plus[k - 1, k] = math.sqrt(j * (j + 1) - m[k] * (m[k] + 1))
    minus = plus.conj().T
    out = np.array([(plus + minus) / 2, (plus - minus) / 2j, np.diag(m).astype(complex)])
    out.setflags(write=False)
    return out


@lru_cache(maxsize=None)
def su2_metric(n: int) -> np.ndarray:
    """The invariant bilinear C_{m m'} of two SU(2) n-plets: (−1)^m δ_{m',−m} for integer j (so that
    Σ C φ_m φ_{m'} = Σ|φ_m|² for a real multiplet), ε (ε₁₂ = +1) for half-integer j."""
    j = (n - 1) / 2
    out = np.zeros((n, n))
    for k in range(n):
        m = j - k
        sign = (-1) ** round(m) if n % 2 else (-1) ** round(j - m)
        out[k, n - 1 - k] = sign
    out.setflags(write=False)
    return out


@lru_cache(maxsize=None)
def triplet_cartesian() -> np.ndarray:
    """U with φ_A = Σ_m U_{Am} φ_m: a triplet's Cartesian components from its spherical ones (m = 1, 0, −1)."""
    r = 1 / math.sqrt(2)
    out = np.array([[-r, 0, r], [-1j * r, 0, -1j * r], [0, 1, 0]], dtype=complex)
    out.setflags(write=False)
    return out


@lru_cache(maxsize=None)
def gell_mann() -> np.ndarray:
    """The eight Gell-Mann matrices λ^a (shape (8, 3, 3))."""
    lam = np.zeros((8, 3, 3), dtype=complex)
    lam[0][0, 1] = lam[0][1, 0] = 1
    lam[1][0, 1], lam[1][1, 0] = -1j, 1j
    lam[2][0, 0], lam[2][1, 1] = 1, -1
    lam[3][0, 2] = lam[3][2, 0] = 1
    lam[4][0, 2], lam[4][2, 0] = -1j, 1j
    lam[5][1, 2] = lam[5][2, 1] = 1
    lam[6][1, 2], lam[6][2, 1] = -1j, 1j
    lam[7] = np.diag([1, 1, -2]) / math.sqrt(3)
    lam.setflags(write=False)
    return lam


@lru_cache(maxsize=None)
def su3_structure() -> np.ndarray:
    """f^{abc} from [t^a, t^b] = i f^{abc} t^c, t = λ/2."""
    t = gell_mann() / 2
    out = np.zeros((8, 8, 8))
    for a in range(8):
        for b in range(8):
            comm = t[a] @ t[b] - t[b] @ t[a]
            for c in range(8):
                out[a, b, c] = float(np.real(-2j * np.trace(comm @ t[c])))
    out.setflags(write=False)
    return out


@lru_cache(maxsize=None)
def su3_generators(rep: str) -> np.ndarray:
    """The generators of SU(3) in "3", "3bar" or "8" (shape (8, d, d))."""
    if rep == "3":
        return gell_mann() / 2
    if rep == "3bar":
        return -np.transpose(gell_mann() / 2, (0, 2, 1))
    if rep == "8":
        return -1j * su3_structure().astype(complex)
    raise IndexError_(f"no SU(3) generators for {rep!r}")


def _levi_civita3() -> np.ndarray:
    out = np.zeros((3, 3, 3))
    for (a, b, c), sign in (((0, 1, 2), 1), ((1, 2, 0), 1), ((2, 0, 1), 1), ((0, 2, 1), -1), ((2, 1, 0), -1),
                            ((1, 0, 2), -1)):
        out[a, b, c] = sign
    return out


# --- contractions ------------------------------------------------------------------------------------

class Contraction:
    """A term's gauge structure as coefficient tensors over its field occurrences, in a fixed order.

    ``occurrences[k]`` is (field, conjugated). ``su2[m₁, …, m_K]`` and ``colour[c₁, …, c_K]`` are the coefficients
    of Π_k F_k[m_k, c_k] (an occurrence that is a singlet of the group has an axis of length 1), so that the term is
    coupling × Σ su2 · colour · Π F.
    """

    def __init__(self, occurrences: list[tuple[str, bool]], su2: np.ndarray, colour: np.ndarray,
                 numeric: tuple[str, ...] = ()) -> None:
        self.occurrences, self.su2, self.colour = occurrences, su2, colour
        self.numeric = numeric                     # the groups whose tensor is the unique invariant, computed (L-3)

    def __repr__(self) -> str:
        return f"Contraction({self.occurrences}, su2 {self.su2.shape}, colour {self.colour.shape})"


def _dims(field: ModelField) -> tuple[int, int]:
    """(SU(2) dimension, colour dimension) of a field."""
    return field.charges.su2, COLOUR_DIM[field.charges.su3]


def _parse(text: str) -> list[tuple[str, bool, list[str]]]:
    """The factors of the index notation: (name, conjugated, indices)."""
    out, position = [], 0
    text = text.strip()
    while position < len(text):
        match = _FACTOR.match(text, position)
        if not match or match.end() == position:
            raise IndexError_(f"cannot read the index notation at {text[position:]!r}")
        name, star, inner = match.group(1), match.group(2) == "*", match.group(3)
        indices = [s.strip() for s in inner.split(",")] if inner else []
        out.append((name, star, indices))
        position = match.end()
    return out


def _field_slots(field: ModelField, indices: list[str]) -> tuple[str | None, str | None]:
    """(SU(2) index, colour index) of a field factor, checked against its representation."""
    n, d = _dims(field)
    wanted = int(n > 1) + int(d > 1)
    if len(indices) != wanted:
        raise IndexError_(f"{field.name} takes {wanted} index(es) (SU(2) first, then colour); got {indices}")
    su2 = indices[0] if n > 1 else None
    colour = indices[-1] if d > 1 else None
    return su2, colour


def _tensor(name: str, ranges: list[int]) -> np.ndarray:
    """An invariant tensor's array for these index ranges."""
    if name == "delta":
        if ranges[0] != ranges[1]:
            raise IndexError_(f"delta joins indices of ranges {ranges}")
        return np.eye(ranges[0])
    if name == "eps":
        return su2_metric(2)
    if name == "metric":
        return su2_metric(ranges[0])
    if name == "sigma":
        return 2 * su2_generators(2)
    if name == "T":
        return su2_generators(ranges[1])
    if name == "cart":
        return triplet_cartesian()
    if name == "cartc":
        return np.conj(triplet_cartesian())
    if name == "lam":
        return gell_mann() / 2
    if name == "f":
        return su3_structure()
    if name == "eps3":
        return _levi_civita3()
    raise IndexError_(f"unknown tensor {name!r}")


_FIXED = {"eps": ("su2", [2, 2]), "sigma": ("su2", [3, 2, 2]), "cart": ("su2", [3, 3]), "cartc": ("su2", [3, 3]),
          "lam": ("colour", [8, 3, 3]), "f": ("colour", [8, 8, 8]), "eps3": ("colour", [3, 3, 3])}


def _index_types(spec: ModelSpec, factors) -> dict[str, tuple[str, int]]:
    """Each index letter's group ("su2" or "colour") and range, from the field slots and the fixed tensors."""
    known: dict[str, tuple[str, int]] = {}
    def note(letter: str, kind: str, size: int) -> None:
        if letter in known and known[letter] != (kind, size):
            raise IndexError_(f"index {letter} is used as {known[letter]} and as {(kind, size)}")
        known[letter] = (kind, size)
    for name, _, idx, tensor in factors:
        if tensor:
            if name in _FIXED:
                kind, sizes = _FIXED[name]
                for letter, size in zip(idx, sizes):
                    note(letter, kind, size)
            continue
        field = spec.field(name)
        su2, colour = _field_slots(field, idx)
        if su2:
            note(su2, "su2", field.charges.su2)
        if colour:
            note(colour, "colour", COLOUR_DIM[field.charges.su3])
    for _ in range(3):                                   # delta, metric and T inherit from their partners
        for name, _, idx, tensor in factors:
            if tensor and name in ("delta", "metric", "T"):
                pair = idx if name != "T" else idx[1:]
                found = [known[x] for x in pair if x in known]
                if found:
                    for letter in pair:
                        note(letter, *found[0])
                if name == "T":
                    note(idx[0], "su2", 3)
    missing = [x for _, _, idx, _ in factors for x in idx if x not in known]
    if missing:
        raise IndexError_(f"cannot tell the range of index(es) {sorted(set(missing))}")
    return known


def _einsum(group: str, spec: ModelSpec, factors, types, slots) -> np.ndarray:
    """Contract one group's tensors into a tensor over the field slots (axes of length 1 for singlets)."""
    letters = iter(string.ascii_letters)
    alias = {x: next(letters) for x in types}
    operands, subscripts, out = [], [], ""
    for k, (index, size) in enumerate(slots):
        if index is None:
            out_letter = next(letters)
            operands.append(np.ones(1))
            subscripts.append(out_letter)
        else:
            out_letter = next(letters)
            operands.append(np.eye(size))
            subscripts.append(out_letter + alias[index])
        out += out_letter
    counts: dict[str, int] = {}
    for name, _, idx, tensor in factors:
        if not tensor:
            continue
        if any(types[x][0] != group for x in idx):
            if all(types[x][0] != group for x in idx):
                continue
            raise IndexError_(f"{name} mixes SU(2) and colour indices")
        operands.append(_tensor(name, [types[x][1] for x in idx]))
        subscripts.append("".join(alias[x] for x in idx))
    for index, _ in slots:
        if index is not None:
            counts[index] = counts.get(index, 0) + 1
    for name, _, idx, tensor in factors:
        if tensor and all(types[x][0] == group for x in idx):
            for x in idx:
                counts[x] = counts.get(x, 0) + 1
    unpaired = [x for x, c in counts.items() if c != 2 and types[x][0] == group]
    if unpaired:
        raise IndexError_(f"index(es) {sorted(unpaired)} must appear exactly twice (the term is not invariant)")
    return np.einsum(",".join(subscripts) + "->" + out, *operands)


def _classified(spec: ModelSpec, text: str) -> list[tuple[str, bool, list[str], bool]]:
    """The factors with a flag: a tensor is unconjugated, carries its arity of indices, and is not a field of that
    name with a different number of indices (a field named T is a field in T[m], the generator in T[A,m,n])."""
    names = {f.name for f in spec.fields}
    out = []
    for name, star, idx in _parse(text):
        tensor = name in TENSOR_ARITY and not star and len(idx) == TENSOR_ARITY[name] and \
            not (name in names and name not in TENSOR_ARITY)
        if name in names and name in TENSOR_ARITY and len(idx) != TENSOR_ARITY[name]:
            tensor = False
        if not tensor and name not in names:
            raise IndexError_(f"{name} is neither a field of the model nor an invariant tensor")
        out.append((name, star, idx, tensor))
    return out


def parse_contraction(spec: ModelSpec, term: ModelTerm) -> Contraction:
    """The contraction a term's ``indices`` states (module docstring)."""
    factors = _classified(spec, term.indices)
    fields = [(n, star) for n, star, _, tensor in factors if not tensor]
    if sorted(fields) != sorted((o.field, o.conjugate) for o in term.fields):
        raise IndexError_(f"the index notation names {sorted(fields)}, the term "
                          f"{sorted((o.field, o.conjugate) for o in term.fields)}")
    types = _index_types(spec, factors)
    su2_slots, colour_slots = [], []
    for name, _, idx, tensor in factors:
        if tensor:
            continue
        field = spec.field(name)
        su2, colour = _field_slots(field, idx)
        su2_slots.append((su2, field.charges.su2))
        colour_slots.append((colour, COLOUR_DIM[field.charges.su3]))
    su2 = _einsum("su2", spec, factors, types, su2_slots)
    colour = _einsum("colour", spec, factors, types, colour_slots)
    return Contraction(fields, su2, colour)


def _real(field: ModelField) -> bool:
    """A field in a real representation that is its own conjugate."""
    return field.self_conjugate and field.charges.hypercharge == 0 and not any(field.charges.extra.values())


def _pairs(spec: ModelSpec, occ: list[tuple[str, bool]], dim) -> list[tuple[int, int, str]] | None:
    """Pair the non-singlet occurrences of one group: (k, l, "delta" or "metric"), or None if there is no
    unambiguous pairing. A field pairs with its own conjugate (δ) or, if real, with itself (the metric); a lone
    pair of two different fields pairs by δ (one conjugated) or the metric (neither or both), in the order listed."""
    live = [k for k, (name, _) in enumerate(occ) if dim(spec.field(name)) > 1]
    if not live:
        return []
    if len(live) == 2:
        k, q = live
        (a, ca), (b, cb) = occ[k], occ[q]
        if dim(spec.field(a)) != dim(spec.field(b)):
            return None
        return [(k, q, "delta" if ca != cb else "metric")]
    out, free = [], list(live)
    while free:
        k = free.pop(0)
        name, conj = occ[k]
        partner = next((q for q in free if occ[q][0] == name and occ[q][1] != conj), None)
        kind = "delta"
        if partner is None and _real(spec.field(name)):
            partner, kind = next((q for q in free if occ[q][0] == name), None), "metric"
        if partner is None:
            return None
        free.remove(partner)
        out.append((k, partner, kind))
    return out


def _invariant_count(spec: ModelSpec, occ: list[tuple[str, bool]]) -> int:
    """The number of independent SU(3) × SU(2) invariants of the occurrences (identical ones symmetrised)."""
    from collections import Counter
    from adroit.model_building.groups import Rep, invariants
    counts = Counter(occ)
    factors = []
    for (name, conj), n in counts.items():
        f = spec.field(name)
        factors.append((Rep(f.charges.su3, f.charges.su2, 1, conjugate=conj), n, f.spin != 0.5 or n == 2))
    return invariants(factors)


def default_contraction(spec: ModelSpec, term: ModelTerm) -> Contraction:
    """The term's unique pairing contraction (module docstring), or IndexError_ saying that its indices must be
    stated."""
    occ = [(o.field, o.conjugate) for o in term.fields]
    label = term.text or " ".join(f"{n}{'*' if c else ''}" for n, c in occ)
    tensors, numeric = {}, []
    for group, dim, metric in (("su2", lambda f: f.charges.su2, su2_metric),
                               ("colour", lambda f: COLOUR_DIM[f.charges.su3], lambda d: np.eye(d))):
        pairs = _pairs(spec, occ, dim)
        if pairs is None:
            # no bilinear pairing (a triplet joined to two doublets, three colour triplets): the group's invariant,
            # computed, where it is the only one (L-3, 2026-11-21: triplet–doublet and quintuplet completions had
            # been refused although their Yukawa is unique)
            found = unique_invariant(spec, occ, group)
            if found is None:
                raise IndexError_(f"the term {label} has no unique pairing of its {group} indices: state them "
                                  "(ModelTerm.indices)")
            tensors[group] = found
            numeric.append(group)
            continue
        sizes = [dim(spec.field(n)) for n, _ in occ]
        out = np.ones(tuple(sizes))
        for k, q, kind in pairs:
            matrix = np.eye(sizes[k]) if kind == "delta" else metric(sizes[k])
            shape = [1] * len(occ)                      # k < q: the pair's matrix on axes (k, q)
            shape[k], shape[q] = sizes[k], sizes[q]
            out = out * matrix.reshape(shape)
        tensors[group] = out
    live = [o for o in occ if spec.field(o[0]).charges.su2 > 1 or spec.field(o[0]).charges.su3 != "1"]
    if len(live) > 2 and _invariant_count(spec, live) != 1:
        raise IndexError_(f"the term {label} has {_invariant_count(spec, live)} independent gauge contractions: "
                          "state its indices (ModelTerm.indices)")
    return Contraction(occ, tensors["su2"], tensors["colour"], tuple(numeric))


INVARIANT_TOLERANCE = 1e-9


def unique_invariant(spec: ModelSpec, occ: list[tuple[str, bool]], group: str) -> np.ndarray | None:
    """The one invariant tensor of a group over the occurrences' representations, or None where there is none or more
    than one: the null space of Σ_k G_k^a acting on slot k, for every generator a (``check_invariant``'s condition),
    symmetrised over identical occurrences. Its phase makes the largest entry real and positive, and it has unit norm
    (Σ|C|² = 1): the coupling multiplies that normalisation, which the term's text states."""
    fields = [spec.field(name) for name, _ in occ]
    sizes = [f.charges.su2 if group == "su2" else COLOUR_DIM[f.charges.su3] for f in fields]
    total = int(np.prod(sizes))
    gens = [_generators(f, group, conj) for f, (_, conj) in zip(fields, occ)]
    blocks = []
    for a in range(gens[0].shape[0]):
        op = np.zeros((total, total), dtype=complex)
        for k, g in enumerate(gens):
            if sizes[k] == 1:
                continue
            factors = [np.eye(s) for s in sizes]
            factors[k] = g[a].T                          # C'[.., n, ..] = Σ_m C[.., m, ..] g[m, n]
            term = factors[0]
            for f in factors[1:]:
                term = np.kron(term, f)
            op += term
        blocks.append(op)
    _, s, vh = np.linalg.svd(np.vstack(blocks))
    null = vh[np.sum(s > INVARIANT_TOLERANCE * max(1.0, s[0])):].conj()
    if null.shape[0] != 1:
        return None
    tensor = null[0].reshape(sizes)
    c = Contraction(occ, tensor if group == "su2" else np.ones([1] * len(occ)),
                    tensor if group == "colour" else np.ones([1] * len(occ)))
    tensor = _symmetrised(c)
    tensor = tensor.reshape(tensor.shape[:len(occ)]) if group == "su2" else tensor.reshape(tensor.shape[len(occ):])
    norm = np.linalg.norm(tensor)
    if norm < INVARIANT_TOLERANCE:
        return None                                      # identical occurrences cancel it
    flat = tensor.ravel()
    lead = flat[np.argmax(np.abs(flat))]
    tensor = tensor * (abs(lead) / lead) / norm
    if np.max(np.abs(tensor.imag)) < INVARIANT_TOLERANCE:
        tensor = tensor.real
    return tensor


def stated_contractions(spec: ModelSpec, term: ModelTerm) -> list[str]:
    """Every independent gauge contraction of a term, each in the index notation, where the default is not unique
    (``default_contraction`` refuses it): the products of bilinear pairings (δ between a field and a conjugate of the
    same multiplet, the metric between two unconjugated or two conjugated SU(2) multiplets; δ between a colour
    triplet and an antitriplet, or two octets), SU(2) by colour, each symmetrised over identical occurrences, kept while
    they are linearly independent, until there are as many as the term has invariants (``_invariant_count``). For
    H H† H₂ H₂† these are (H†H)(H₂†H₂) and (H†H₂)(H₂†H), λ₃ and λ₄ of a second doublet; for H H H₂* H₂* the single
    (H₂†H)(H₂†H), λ₅. [] if the pairings do not span the invariants (a triplet joined to two doublets needs σ, three
    colour triplets ε: those terms must state their indices)."""
    occ = [(o.field, o.conjugate) for o in term.fields]
    live = [o for o in occ if spec.field(o[0]).charges.su2 > 1 or spec.field(o[0]).charges.su3 != "1"]
    wanted = _invariant_count(spec, live) if live else 1
    found: list[str] = []
    basis: list[np.ndarray] = []
    for su2 in _matchings(spec, occ, "su2"):
        for colour in _matchings(spec, occ, "colour"):
            text = _notation(spec, occ, su2, colour)
            c = parse_contraction(spec, term.model_copy(update={"indices": text}))
            vector = _symmetrised(c).ravel()
            if np.linalg.norm(vector) < 1e-12:
                continue
            trial = [*basis, vector]
            if np.linalg.matrix_rank(np.array(trial), tol=1e-9) == len(trial):
                basis, found = trial, [*found, text]
            if len(found) == wanted:
                return found
    return []


def _matchings(spec: ModelSpec, occ: list[tuple[str, bool]], group: str) -> list[list[tuple[int, int, str]]]:
    """Every pairing of one group's non-singlet occurrences into invariant bilinears (``stated_contractions``)."""
    def size(k: int) -> int:
        f = spec.field(occ[k][0])
        return f.charges.su2 if group == "su2" else COLOUR_DIM[f.charges.su3]

    def joins(k: int, q: int) -> str | None:
        if size(k) != size(q):
            return None
        if group == "su2":
            return "delta" if occ[k][1] != occ[q][1] else "metric"
        if size(k) == 8:
            return "delta"
        bar = [(spec.field(occ[x][0]).charges.su3 == "3bar") != occ[x][1] for x in (k, q)]
        return "delta" if bar[0] != bar[1] else None

    def pairings(free: list[int]) -> list[list[tuple[int, int, str]]]:
        if not free:
            return [[]]
        k, rest = free[0], free[1:]
        out = []
        for q in rest:
            kind = joins(k, q)
            if kind:
                out += [[(k, q, kind), *more] for more in pairings([x for x in rest if x != q])]
        return out
    found = pairings([k for k in range(len(occ)) if size(k) > 1])
    return sorted(found, key=lambda m: sum(kind != "delta" for _, _, kind in m))     # δ pairings first


def _notation(spec: ModelSpec, occ: list[tuple[str, bool]], su2: list[tuple[int, int, str]],
              colour: list[tuple[int, int, str]]) -> str:
    """A contraction in the index notation, the field factors in the term's order (the tensors' axes)."""
    slots: dict[int, list[str]] = {k: [] for k in range(len(occ))}
    tensors = []
    for group, pairs, letters in (("su2", su2, "ijklmnpq"), ("colour", colour, "abcdefgh")):
        for n, (k, q, kind) in enumerate(pairs):
            if kind == "delta":
                slots[k].append(letters[n])
                slots[q].append(letters[n])
            else:
                a, b = f"{letters[n]}1", f"{letters[n]}2"
                slots[k].append(a)
                slots[q].append(b)
                tensors.append(f"metric[{a},{b}]")
    for k in slots:                                     # SU(2) index first, then colour (``_field_slots``)
        slots[k].sort(key=lambda x: x[0] in "abcdefgh")
    factors = [f"{name}{'*' if conj else ''}" + (f"[{','.join(slots[k])}]" if slots[k] else "")
               for k, (name, conj) in enumerate(occ)]
    return " ".join([*tensors, *factors])


def _symmetrised(c: Contraction) -> np.ndarray:
    """The SU(2) ⊗ colour coefficient tensor of a contraction, symmetrised over identical occurrences (what
    multiplies the product of fields)."""
    from itertools import permutations
    k = len(c.occurrences)
    full = np.multiply.outer(c.su2, c.colour)              # axes: su2 slots 0..k−1, then colour slots k..2k−1
    groups: dict[tuple[str, bool], list[int]] = {}
    for i, o in enumerate(c.occurrences):
        groups.setdefault(o, []).append(i)
    for members in groups.values():
        if len(members) < 2:
            continue
        total = np.zeros_like(full)
        perms = list(permutations(members))
        for perm in perms:
            order = list(range(k))
            for a, b in zip(members, perm):
                order[a] = b
            total = total + np.transpose(full, order + [k + x for x in order])
        full = total / len(perms)
    return full


def contraction(spec: ModelSpec, term: ModelTerm) -> Contraction:
    """A term's contraction, the stated ``indices`` or the unique default, checked to be gauge invariant."""
    c = parse_contraction(spec, term) if term.indices.strip() else default_contraction(spec, term)
    if spec.phase.value == "unbroken":
        check_invariant(spec, c, term.text or term.indices or term.coupling,
                        current=term.lorentz in ("vector", "axial"))
    return c


def _generators(field: ModelField, group: str, conj: bool) -> np.ndarray:
    """The generators acting on one occurrence's index: T for a field, −T* for its conjugate."""
    if group == "su2":
        t = su2_generators(field.charges.su2)
    else:
        t = su3_generators(field.charges.su3) if field.charges.su3 != "1" else np.zeros((8, 1, 1))
    return -np.conj(t) if conj else t


def check_invariant(spec: ModelSpec, c: Contraction, label: str = "", current: bool = False) -> None:
    """Raise IndexError_ unless the contraction is SU(2) × SU(3) invariant and its U(1) charges cancel:
    Σ_k G_k acting on slot k annihilates the coefficient tensor, for every generator.

    A ``current`` (vector or axial) of one self-conjugate field, N̄Γ^μN, is neutral under every U(1) whether or not
    N̄ is marked conjugate: for a Majorana field N̄ = NᵀC is notation. (A mass-type product NN, as in NNΦ, does carry
    2q, and is counted as written.)"""
    fields = [spec.field(name) for name, _ in c.occurrences]
    signs = [-1 if conj else 1 for _, conj in c.occurrences]
    pairs = [k for k, f in enumerate(fields) if f.spin == 0.5]
    if current and len(pairs) == 2 and c.occurrences[pairs[0]][0] == c.occurrences[pairs[1]][0] \
            and fields[pairs[0]].self_conjugate:
        signs[pairs[0]], signs[pairs[1]] = -1, 1                   # N̄ΓN: one charge in, one out
    for group, tensor in (("su2", c.su2), ("colour", c.colour)):
        if tensor.size == 1:
            continue
        gens = [_generators(f, group, conj) for f, (_, conj) in zip(fields, c.occurrences)]
        for a in range(gens[0].shape[0]):
            total = np.zeros_like(tensor, dtype=complex)
            for k, g in enumerate(gens):
                if tensor.shape[k] == 1:
                    continue
                total += np.moveaxis(np.tensordot(tensor, g[a], axes=([k], [0])), -1, k)
            if np.max(np.abs(total)) > 1e-9 * max(1.0, float(np.max(np.abs(tensor)))):
                raise IndexError_(f"the term {label or c.occurrences} is not {'SU(2)' if group == 'su2' else 'SU(3)'}"
                                  " invariant with these indices")
    charges = [f.charges for f in fields]
    for key in {"hypercharge"} | {k for ch in charges for k in ch.extra}:
        total = sum(sign * (ch.hypercharge if key == "hypercharge" else ch.extra.get(key, 0.0))
                    for ch, sign in zip(charges, signs))
        if abs(total) > 1e-6:
            raise IndexError_(f"the term {label or c.occurrences} carries net {key} {total:+g}")
