"""Group theory for model building (DM12): SU(3) × SU(2) representations and their invariants.

A representation is held as its **states**: one weight per basis state. SU(2)
weights are the integers 2m; SU(3) weights are integer 3-vectors (three times
the weight in the orthonormal basis, so that the fundamental's are
(2, −1, −1) and its permutations). An irreducible SU(3) representation of
Dynkin labels (p, q) is the traceless part of Sym^p(3) ⊗ Sym^q(3̄),

    states(p, q) = states(Sym^p 3 ⊗ Sym^q 3̄) − states(Sym^{p−1} 3 ⊗ Sym^{q−1} 3̄),

so its weights follow exactly from the fundamental's, with no tables.

**Invariants.** The number of singlets in a representation with weight
multiplicities m(λ) follows from the Weyl character formula,

    n₀ = Σ_{σ ∈ W} ε(σ) m(ρ − σρ),

with ρ the Weyl vector: for SU(2), n₀ = m(0) − m(2); for SU(3), a sum over the
six permutations of the three coordinates. For a product of the two groups
the sum runs over both Weyl groups at once.

**Identical fields.** n copies of one field enter as its symmetric power
(bosons, or fermion pairs whose Lorentz contraction is antisymmetric) or its
antisymmetric power. Each basis state carries its flavour index too, so the
count of invariants is the number of independent couplings, flavour included.
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from itertools import combinations, combinations_with_replacement, permutations, product

SU3_NAMES = {"1": (0, 0), "3": (1, 0), "3bar": (0, 1), "8": (1, 1), "6": (2, 0), "6bar": (0, 2),
             "10": (3, 0), "10bar": (0, 3)}
_FUNDAMENTAL = ((2, -1, -1), (-1, 2, -1), (-1, -1, 2))
_RHO3 = (3, 0, -3)                       # ω1 + ω2, scaled by 3


def _add(a: tuple, b: tuple) -> tuple:
    return tuple(x + y for x, y in zip(a, b))


def _neg(a: tuple) -> tuple:
    return tuple(-x for x in a)


def _sym_weights(base: tuple[tuple, ...], n: int) -> Counter:
    """Weights of the n-th symmetric power of a representation with these states."""
    zero = (0,) * len(base[0])
    out: Counter = Counter()
    for choice in combinations_with_replacement(range(len(base)), n):
        w = zero
        for i in choice:
            w = _add(w, base[i])
        out[w] += 1
    return out


@lru_cache(maxsize=None)
def su3_weights(p: int, q: int) -> tuple[tuple[int, int, int], ...]:
    """The states of the SU(3) irrep (p, q): one weight per state, as integer 3-vectors."""
    def tensor(p_: int, q_: int) -> Counter:
        if p_ < 0 or q_ < 0:
            return Counter()
        out: Counter = Counter()
        for a, na in _sym_weights(_FUNDAMENTAL, p_).items():
            for b, nb in _sym_weights(tuple(_neg(f) for f in _FUNDAMENTAL), q_).items():
                out[_add(a, b)] += na * nb
        return out
    full, trace = tensor(p, q), tensor(p - 1, q - 1)
    states = []
    for w, n in full.items():
        states += [w] * (n - trace.get(w, 0))
    return tuple(sorted(states))


def su3_rep(name: str) -> tuple[int, int]:
    """Dynkin labels of a named SU(3) representation ("1", "3", "3bar", "8", ...)."""
    try:
        return SU3_NAMES[name]
    except KeyError:
        raise ValueError(f"unknown SU(3) representation {name!r}; known: {', '.join(SU3_NAMES)}") from None


def su3_conjugate(name: str) -> str:
    """The name of the conjugate SU(3) representation, (p, q) → (q, p)."""
    p, q = su3_rep(name)
    return next(k for k, v in SU3_NAMES.items() if v == (q, p))


def su2_weights(dim: int) -> tuple[int, ...]:
    """The states of the SU(2) irrep of dimension dim: weights 2m = dim−1, dim−3, …, 1−dim."""
    if dim < 1:
        raise ValueError("an SU(2) multiplet has dimension ≥ 1")
    return tuple(range(dim - 1, -dim, -2))


class Rep:
    """A representation of SU(3) × SU(2) with flavour: its states, each (SU(3) weight, SU(2) weight).

    Flavour (generations) multiplies the states: each copy is a distinct state of the same weight.
    """

    def __init__(self, su3: str = "1", su2: int = 1, flavours: int = 1, conjugate: bool = False) -> None:
        p, q = su3_rep(su3)
        w3 = su3_weights(q, p) if conjugate else su3_weights(p, q)
        w2 = su2_weights(su2)                     # SU(2) is self-conjugate (pseudo-real or real)
        self.states: tuple[tuple, ...] = tuple((a, b) for a in w3 for b in w2 for _ in range(flavours))

    @property
    def dimension(self) -> int:
        """The number of states, flavours included."""
        return len(self.states)


def power_weights(rep: Rep, n: int, symmetric: bool) -> Counter:
    """Joint weights of the n-th symmetric (or antisymmetric) power of a representation."""
    pick = combinations_with_replacement if symmetric else combinations
    out: Counter = Counter()
    for choice in pick(range(rep.dimension), n):
        a, b = (0, 0, 0), 0
        for i in choice:
            a, b = _add(a, rep.states[i][0]), b + rep.states[i][1]
        out[(a, b)] += 1
    return out


def product_weights(*parts: Counter) -> Counter:
    """Joint weights of a tensor product of representations given by their weight multiplicities."""
    out: Counter = Counter({((0, 0, 0), 0): 1})
    for part in parts:
        nxt: Counter = Counter()
        for (a, b), n in out.items():
            for (c, d), m in part.items():
                nxt[(_add(a, c), b + d)] += n * m
        out = nxt
    return out


def _parity(perm: tuple[int, ...]) -> int:
    sign, seen = 1, set()
    for i in range(len(perm)):
        if i in seen:
            continue
        j, length = i, 0
        while j not in seen:
            seen.add(j)
            j, length = perm[j], length + 1
        sign *= (-1) ** (length - 1)
    return sign


_WEYL3 = [(_parity(p), tuple(_RHO3[i] for i in p)) for p in permutations(range(3))]
_WEYL2 = [(1, 1), (-1, -1)]                 # ρ = 1 in units of 2m; σρ = ±1


def singlets(weights: Counter) -> int:
    """The number of SU(3) × SU(2) invariants in a representation (Weyl character formula)."""
    total = 0
    for s3, rho3 in _WEYL3:
        shift3 = tuple(r - x for r, x in zip(_RHO3, rho3))          # ρ − σρ for SU(3)
        for s2, rho2 in _WEYL2:
            total += s3 * s2 * weights.get((shift3, 1 - rho2), 0)
    return total


def invariants(factors: list[tuple[Rep, int, bool]]) -> int:
    """Independent invariants of a product of fields: each factor is (representation, copies, symmetric).

    Distinct fields multiply; n copies of one field enter as its symmetric (or antisymmetric) n-th power.
    """
    parts = [power_weights(rep, n, sym) for rep, n, sym in factors]
    return singlets(product_weights(*parts))


def dimension_of(su3: str, su2: int) -> int:
    """The dimension of an SU(3) × SU(2) irrep (for checks and messages)."""
    p, q = su3_rep(su3)
    return len(su3_weights(p, q)) * su2


def _check_dimensions() -> None:
    """The weight construction gives the known dimensions (run by the tests)."""
    for name, dim in {"1": 1, "3": 3, "3bar": 3, "8": 8, "6": 6, "10": 10}.items():
        assert len(su3_weights(*su3_rep(name))) == dim, name


__all__ = ["Rep", "invariants", "singlets", "power_weights", "product_weights", "su3_weights", "su2_weights",
           "su3_rep", "su3_conjugate", "dimension_of", "SU3_NAMES", "product"]
