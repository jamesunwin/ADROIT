"""Colour algebra for the tree engine (``tree``): SU(3) tensors, vertex colour structures and the colour sum.

A vertex's colour structure is written as a UFO colour string over its legs' positions (1-based, in the
vertex's slot order), with negative integers for summed indices:

| factor | tensor |
|---|---|
| ``Identity(i,j)`` | δ_ij (two triplet legs, or two octet legs) |
| ``T(a,i,j)`` | (λ^a/2)_ij, a an octet leg, i a triplet leg and j an antitriplet leg (UFO's convention) |
| ``f(a,b,c)``, ``d(a,b,c)`` | the SU(3) structure constants and the symmetric d-symbols |
| ``Epsilon(i,j,k)``, ``EpsilonBar(i,j,k)`` | ε_ijk |

Terms may be added and multiplied by numbers: ``T(3,-1,1)*T(4,2,-1) + T(4,-1,1)*T(3,2,-1)``. An empty
structure is inferred from the legs' representations (``default_structure``): none coloured gives 1, two
coloured legs δ, a triplet pair with an octet T, three octets f, a triplet pair with two octets {T^a, T^b}.

**The colour sum.** Each diagram d of a process carries a colour tensor c_d over the four external legs,
the internal line's index summed between its two vertices. The colour-summed square of the amplitude is
Σ_dd' K_dd' M_d M_d'*, K_dd' = Σ_colours c_d c_d'*, averaged over the initial legs' colours.
"""

from __future__ import annotations

import re
from functools import lru_cache
from itertools import product

import numpy as np

DIMENSION = {"1": 1, "3": 3, "3bar": 3, "8": 8}
CONJUGATE = {"1": "1", "3": "3bar", "3bar": "3", "8": "8"}


@lru_cache(maxsize=1)
def gell_mann() -> np.ndarray:
    """The eight Gell-Mann matrices λ^a, shape (8, 3, 3)."""
    lam = np.zeros((8, 3, 3), dtype=complex)
    lam[0][0, 1] = lam[0][1, 0] = 1
    lam[1][0, 1], lam[1][1, 0] = -1j, 1j
    lam[2][0, 0], lam[2][1, 1] = 1, -1
    lam[3][0, 2] = lam[3][2, 0] = 1
    lam[4][0, 2], lam[4][2, 0] = -1j, 1j
    lam[5][1, 2] = lam[5][2, 1] = 1
    lam[6][1, 2], lam[6][2, 1] = -1j, 1j
    lam[7] = np.diag([1, 1, -2]) / np.sqrt(3)
    return lam


@lru_cache(maxsize=1)
def generators() -> np.ndarray:
    """T^a = λ^a/2, shape (8, 3, 3)."""
    return gell_mann() / 2.0


@lru_cache(maxsize=1)
def structure_constants() -> tuple[np.ndarray, np.ndarray]:
    """(f^abc, d^abc) from [T^a, T^b] = i f^abc T^c and {T^a, T^b} = δ^ab/3 + d^abc T^c."""
    t = generators()
    comm = np.einsum("aij,bjk->abik", t, t) - np.einsum("bij,ajk->abik", t, t)
    anti = np.einsum("aij,bjk->abik", t, t) + np.einsum("bij,ajk->abik", t, t)
    f = np.real(-2j * np.einsum("abik,cki->abc", comm, t))
    d = np.real(2.0 * np.einsum("abik,cki->abc", anti, t))
    return f, d


@lru_cache(maxsize=1)
def epsilon() -> np.ndarray:
    """ε_ijk, shape (3, 3, 3)."""
    e = np.zeros((3, 3, 3))
    for i, j, k in product(range(3), repeat=3):
        e[i, j, k] = (i - j) * (j - k) * (k - i) / 2
    return e


def _tensor(name: str) -> np.ndarray:
    f, d = structure_constants()
    return {"T": generators(), "f": f, "d": d, "Epsilon": epsilon(), "EpsilonBar": epsilon()}[name]


def default_structure(reps: list[str]) -> str:
    """The colour structure of a vertex whose legs have these representations, when it is not stated.

    Raises:
        ValueError: if the representations admit no default (state the structure on the vertex).
    """
    coloured = [i + 1 for i, r in enumerate(reps) if r != "1"]
    if not coloured:
        return "1"
    kinds = sorted(reps[i - 1] for i in coloured)
    trip = [i for i in coloured if reps[i - 1] == "3"]
    anti = [i for i in coloured if reps[i - 1] == "3bar"]
    octets = [i for i in coloured if reps[i - 1] == "8"]
    if len(coloured) == 2 and DIMENSION[kinds[0]] == DIMENSION[kinds[1]]:
        return f"Identity({coloured[0]},{coloured[1]})"
    if len(trip) == 1 and len(anti) == 1 and len(octets) == 1:
        return f"T({octets[0]},{trip[0]},{anti[0]})"
    if len(octets) == 3 and len(coloured) == 3:
        return f"f({octets[0]},{octets[1]},{octets[2]})"
    if len(trip) == 1 and len(anti) == 1 and len(octets) == 2:
        a, b = octets
        i, j = trip[0], anti[0]
        return f"T({a},{i},-1)*T({b},-1,{j}) + T({b},{i},-1)*T({a},-1,{j})"
    raise ValueError(f"no default colour structure for legs in {reps}: state it on the vertex")


_FACTOR = re.compile(r"([A-Za-z]+)\(([-0-9,\s]+)\)")


def _split_terms(text: str) -> list[tuple[complex, str]]:
    """'2*A + B - C' → [(2, 'A'), (1, 'B'), (-1, 'C')] (top-level + and − only)."""
    terms, depth, start = [], 0, 0
    text = text.replace(" ", "")
    for k, ch in enumerate(text):
        depth += ch == "("
        depth -= ch == ")"
        if ch in "+-" and depth == 0 and k > start and text[k - 1] not in "*(,":
            terms.append(text[start:k])
            start = k
    terms.append(text[start:])
    out = []
    for term in terms:
        sign = -1.0 if term.startswith("-") else 1.0
        term = term.lstrip("+-")
        factors = term.split("*")
        number = 1.0
        rest = []
        for factor in factors:
            if _FACTOR.fullmatch(factor):
                rest.append(factor)
            else:
                number *= complex(factor) if "j" in factor else float(factor)
        out.append((sign * number, "*".join(rest)))
    return out


def vertex_tensor(structure: str, reps: list[str]) -> np.ndarray:
    """The colour tensor of a vertex over its slots (``_vertex_tensor``, cached)."""
    return _vertex_tensor(structure, tuple(reps))


@lru_cache(maxsize=4096)
def _vertex_tensor(structure: str, reps: tuple[str, ...]) -> np.ndarray:
    """The colour tensor of a vertex over its slots (dimension 1 for a colourless slot), complex.

    Args:
        structure: a UFO colour string over 1-based slot positions, "1", or "" (inferred from ``reps``).
        reps: each slot's representation as an incoming leg ("1", "3", "3bar", "8").
    """
    if not structure:
        structure = default_structure(reps)
    dims = [DIMENSION[r] for r in reps]
    total = np.zeros(dims, dtype=complex)
    letters = "abcdefgh"
    for number, product_text in _split_terms(structure):
        if not product_text or product_text == "1":
            total += number * np.ones(dims)
            continue
        operands, subscripts, dummy_dims = [], [], {}
        for name, args in _FACTOR.findall(product_text):
            idx = [int(x) for x in args.split(",")]
            labels = "".join(letters[i - 1] if i > 0 else "uvwxyz"[-i - 1] for i in idx)
            if name == "Identity":
                dim = next((dims[i - 1] for i in idx if i > 0), None) or next(
                    (dummy_dims[i] for i in idx if i in dummy_dims), None)
                if dim is None:
                    raise ValueError(f"cannot size {name}({args})")
                tensor = np.eye(dim)
            else:
                tensor = _tensor(name)
            for i, n in zip(idx, tensor.shape):
                if i < 0:
                    dummy_dims[i] = n
            operands.append(tensor)
            subscripts.append(labels)
        out_labels = "".join(letters[k] for k in range(len(dims)) if dims[k] > 1)
        used = set("".join(subscripts))
        missing = [letters[k] for k in range(len(dims)) if dims[k] > 1 and letters[k] not in used]
        if missing:
            raise ValueError(f"the colour structure {structure!r} leaves coloured slots unindexed")
        value = np.einsum(",".join(subscripts) + "->" + out_labels, *operands)
        total += number * value.reshape(dims)
    return total


def diagram_tensor(uses: list[tuple[np.ndarray, tuple]], leg_dims: list[int]) -> np.ndarray:
    """The colour tensor of a diagram over the four external legs.

    Args:
        uses: each vertex's colour tensor and its slots' edges (an external leg 0–3, or "x" for the internal line).
        leg_dims: the colour dimension of each external leg.
    """
    letters = "abcd"
    operands, subscripts = [], []
    for tensor, edges in uses:
        operands.append(tensor)
        subscripts.append("".join(letters[e] if e != "x" else "x" for e in edges))
    out = "".join(letters[k] for k in range(4))
    value = np.einsum(",".join(subscripts) + "->" + out, *operands)
    return value.reshape(leg_dims)


def interference(tensors: list[np.ndarray]) -> np.ndarray:
    """K_dd' = Σ_colours c_d c_d'* of a process's diagrams (Hermitian)."""
    flat = np.array([t.ravel() for t in tensors])
    return flat @ flat.conj().T
