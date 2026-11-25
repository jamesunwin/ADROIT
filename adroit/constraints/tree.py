"""A general tree-level 2 → 2 engine: any process of a model given as particles and Feynman rules (G3).

A model is a list of particles (spin 0, ½ or 1; Dirac or Majorana; any colour) and vertices. The
engine finds every tree diagram of a 2 → 2 process — the contact term, and the s-, t- and u-channel
exchange of any particle — and evaluates each with explicit spinors and polarisation vectors, summing
the squares over spins, polarisations and colours numerically (the method of ``amplitudes`` and
``processes``), then integrates the angle by Gauss–Legendre quadrature.

**Vertices.** Every leg of a vertex is incoming; an outgoing particle is an incoming antiparticle.
The Feynman rule is i × V, with V the coefficient of the interaction in the Lagrangian times its
combinatorial factor (with i absorbed into c where a derivative coupling has one):

| kind | slots | V |
|---|---|---|
| ``SSS``, ``SSSS`` | scalars | c |
| ``VSS`` | (V, a, b) | c (p_a − p_b)^μ |
| ``VVS``, ``VVSS`` | (V₁, V₂, …) | c g^μν |
| ``VVV`` | (V₁, V₂, V₃) | c [g^μν(k₁ − k₂)^ρ + g^νρ(k₂ − k₃)^μ + g^ρμ(k₃ − k₁)^ν] |
| ``VVVV`` | (V₁, V₂, V₃, V₄) | c g^{12}g^{34} + c₂ g^{13}g^{24} + c₃ g^{14}g^{23} |
| ``FFS`` | (f̄, f, S) | Γ = c + i c₂ γ⁵ |
| ``FFSS`` | (f̄, f, S₁, S₂) | Γ = c + i c₂ γ⁵ |
| ``FFV`` | (f̄, f, V) | Γ = γ^μ(c + c₂ γ⁵) |
| ``FFFF`` | (f̄₁, f₁, f̄₂, f₂) | Σ_k c_k Γ_k ⊗ Γ'_k (``structure``), Γ in S = 1, P = iγ⁵, V = γ^μ, A = γ^μγ⁵, T = σ^μν |

Couplings may be complex, so FFS and FFV carry any chiral couplings: c + i c₂γ⁵ = (c − i c₂) P_L +
(c + i c₂) P_R. For a fermion term ψ̄_i Γ ψ_j X the slots are (f̄ = the antiparticle of i, f = j, X):
the fermion line enters the vertex through slot f and leaves through slot f̄. A term with two identical
Majorana fields, ½ χ̄Γχ X, has V = Γ (the combinatorial 2). A Majorana pair i ≠ j has one vertex,
(χ̄_i, χ_j, X), holding the full coefficient; it serves a fermion line in either direction (below).
The h.c. of a Dirac term is a separate vertex. Each vertex may state its colour structure (``colour``,
a UFO colour string over its 1-based slot positions; ``tree_colour``), or leave it to be inferred.

**Four-fermion contacts (2026-10-20).** An ``FFFF`` vertex is the contact (ψ̄₁Γψ₁)(ψ̄₂Γ'ψ₂) with two fermion lines,
slots (0, 1) and (2, 3), each entering through its second slot. Its V is the Lagrangian coefficient itself, without
a combinatorial factor: the engine takes every Wick contraction of the external legs with the slots (each line
either way when the names allow, and the two lines exchanged), each with its Fermi sign, so the Fierz-crossed terms
of identical fields and a Majorana bilinear's two contractions (S, P, A doubled; V, T cancelled) follow.

**Fermion lines (Denner's rules, Nucl. Phys. B387 (1992) 467).** Each fermion line of a diagram is given
an orientation, the fermion flow, from its external fermion with the lower leg index to the other. A
vertex traversed along its f → f̄ orientation contributes Γ; traversed against it, Γ' = C Γᵀ C⁻¹ (scalar,
pseudoscalar and axial parts unchanged, the vector part reversed in sign). This holds for Dirac and
Majorana fermions alike, so a Majorana line needs no fermion-number arrow. External spinors follow the
flow: an incoming fermion is u(p) where the flow enters and v̄(p) where it leaves; an outgoing one is
ū(k) where the flow leaves and v(k) where it enters. v is built from u of the same spin state (v = C ūᵀ),
as a Majorana particle needs. A fermion propagator is i(p̸ + m)/(p² − m² + imΓ) with p along the flow.
Diagrams with two fermion lines carry the sign of the permutation of their external spinors, written
(ψ̄_end ψ_start)(ψ̄_end ψ_start), relative to a fixed order: Fermi statistics.

**Propagators:** i/(q² − m² + imΓ) for scalars; i(−g + qq/m²)/(q² − m² + imΓ) for massive vectors
(unitary gauge); −ig/q² for massless vectors; the fermion propagator above. The amplitude is
M = Σ_contact V − Σ_exchange V₁ D V₂ (the relative sign of the i's).

**External states.** Massive vectors carry their three polarisations; massless vectors their two
transverse ones only, so gauge-boson final states are physical without ghosts (exact in the unitary
gauge, where all exchanged bosons are physical). Spins and polarisations are averaged over the initial
legs and summed over the final ones; colours likewise (``tree_colour``).

**Not covered:** a four-gluon vertex is accepted only as ``VVVV`` with an
explicit colour string; loops; 2 → 3. Metric (+, −, −, −); GeV; σ in GeV⁻².
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from itertools import permutations, product

import numpy as np

from adroit.constraints import tree_colour
from adroit.constraints.amplitudes import _BASIS, GAMMA, GAMMA5, METRIC, bar, polarisations, slash
from adroit.constraints.processes import _initial_polarisations, _transverse, conjugate, frame

UNIT = np.eye(4, dtype=complex)
NODES = 20
FERMIONIC = ("FFS", "FFSS", "FFV")
FLOW_FROM_HIGHER = False          # the fermion flow's arbitrary direction: |M|² must not depend on it (a test)


@lru_cache(maxsize=None)
def gauss(points: int) -> tuple[np.ndarray, np.ndarray]:
    """Gauss–Legendre nodes and weights on [−1, 1], computed once per order (read-only): ``sigma`` had recomputed
    them at every call, a sixth of an off-shell cross-section's time (F0)."""
    x, w = np.polynomial.legendre.leggauss(points)
    x.flags.writeable = w.flags.writeable = False
    return x, w


def _flow(legs) -> tuple:
    """A fermion line's (start, end): from the lower leg index, or the higher with ``FLOW_FROM_HIGHER``."""
    low, high = sorted(legs)
    return (high, low) if FLOW_FROM_HIGHER else (low, high)


@dataclass(frozen=True)
class Particle:
    """A particle of the model: spin, mass and width (GeV), its antiparticle's name ("" for a self-conjugate
    particle, which for spin ½ is a Majorana fermion), colour, PDG code and electric charge.

    ``colour`` is the representation ("1", "3", "3bar", "8"); ``colours`` its dimension. A model written
    before colour representations (``colours`` = 3 with ``colour`` "1") is read as a triplet whose vertices
    carry δ in colour (the default structure).
    """
    name: str
    spin: float                  # 0, 0.5 or 1
    mass: float
    width: float = 0.0
    anti: str = ""               # the antiparticle's name ("" = self-conjugate)
    colours: int = 1
    pdg: int = 0                 # the PDG code (0 if not given)
    charge: float = 0.0          # electric charge (units of e)
    colour: str = "1"            # "1", "3", "3bar" or "8"

    def __post_init__(self) -> None:
        if self.colour not in tree_colour.DIMENSION:
            raise ValueError(f"{self.name}: colour {self.colour!r} is not 1, 3, 3bar or 8")
        if self.colour != "1":
            object.__setattr__(self, "colours", tree_colour.DIMENSION[self.colour])

    @property
    def conjugate(self) -> str:
        """The antiparticle's name (its own for a self-conjugate particle)."""
        return self.anti or self.name

    @property
    def representation(self) -> str:
        """The colour representation, with a legacy multiplicity of 3 or 8 read as a triplet or an octet."""
        if self.colour != "1":
            return self.colour
        return {3: "3" if self.pdg >= 0 else "3bar", 8: "8"}.get(self.colours, "1")


@dataclass(frozen=True)
class Vertex:
    """A vertex of the table above: its kind, its incoming legs in slot order, the couplings c (c_s for FFS,
    a for FFV), c2 (c_p for FFS, b for FFV) and c3 (VVVV only), and its colour structure ("" = inferred)."""
    kind: str                    # SSS, SSSS, VSS, VVS, VVSS, VVV, VVVV, FFS, FFSS, FFV
    legs: tuple[str, ...]        # incoming particle names, in the order of the table above
    c: complex = 0.0
    c2: complex = 0.0            # c_p (FFS, FFSS) or b (FFV); g^{13}g^{24} for VVVV
    c3: complex = 0.0            # g^{14}g^{23} for VVVV
    colour: str = ""             # a UFO colour string over 1-based slots ("" = inferred from the legs)
    structure: tuple = ()        # FFFF only: ((Γ, Γ', c), ...) with Γ in S, P, V, A, T


def conserved_current(model: "Model", name: str) -> bool:
    """Whether the massive vector ``name`` couples only to conserved currents: vector (not axial) couplings between
    fermions of one mass, scalar currents between scalars of one mass, seagulls, and no vertex with another vector
    alone (no Higgs-mechanism VVS, no self-interaction). Its longitudinal polarisation's k^μ/m part then drops out of
    every amplitude (the Ward identity), and ``_ward_polarisations`` leaves it out."""
    mass = {n: x.mass for n, x in model.particles.items()}
    anti = model.particles[name].anti or name
    for v in model.vertices:
        if name not in v.legs and anti not in v.legs:
            continue
        others = [x for x in v.legs if x not in (name, anti)]
        if v.kind == "FFV":
            if abs(v.c2) > 0 or abs(mass[others[0]] - mass[others[1]]) > 1e-12 * max(mass[others[0]], 1e-30):
                return False
        elif v.kind == "VSS":
            if abs(mass[others[0]] - mass[others[1]]) > 1e-12 * max(mass[others[0]], 1e-30):
                return False
        elif v.kind not in ("VVSS",):
            return False
    return True


def _ward_polarisations(k: np.ndarray, mass: float) -> list[np.ndarray]:
    """``polarisations`` with k^μ/m taken out of the longitudinal vector: ε_L − k/m = −m/(E + |k|) (1, −n̂), exact and
    free of the (E/m)² cancellation that double precision cannot hold for m/m_V ≳ 10⁴ (the audit's G7-2, G12: χχ̄ →
    V′V′ came out negative at 1 TeV with a 10 MeV vector)."""
    e1, e2, _ = polarisations(k, mass)
    kk = np.linalg.norm(k[:, 1:], axis=1)
    n = k[:, 1:] / kk[:, None]
    scale = -mass / (k[:, 0] + kk)
    return [e1, e2, np.concatenate([scale[:, None], -scale[:, None] * n], axis=1)]


@dataclass
class Model:
    """A model as its particles, by name, and its vertices, indexed by their legs (``find``)."""
    particles: dict[str, Particle]
    vertices: list[Vertex] = field(default_factory=list)
    _index: dict = field(default_factory=dict, repr=False)

    def add(self, *particles: Particle) -> None:
        """Add particles, and the antiparticle of each that has one (opposite PDG code, charge and colour)."""
        for p in particles:
            self.particles[p.name] = p
            if p.anti:
                self.particles[p.anti] = Particle(p.anti, p.spin, p.mass, p.width, p.name, p.colours, -p.pdg,
                                                  -p.charge, tree_colour.CONJUGATE[p.colour])

    def find(self, legs: list[str]) -> list[tuple[Vertex, tuple[int, ...]]]:
        """Every vertex whose legs are these (in any order): (vertex, the order of ``legs`` in its slots).

        Safe for concurrent callers (the auditor's OL-02: the workbench's threads share one cached model, and the index had
        been published with its final size before its vertex map was filled, so a second thread cached empty lookups
        and a valid model was refused): the index is built in a local variable and published whole, in one assignment,
        and each call reads the one index object it started with."""
        index = self._index
        vertices = list(self.vertices)
        if index.get("size") != len(vertices):                      # (re)built when vertices are added
            by: dict = {}
            for v in vertices:
                by.setdefault(tuple(sorted(v.legs)), []).append(v)
            index = {"size": len(vertices), "by": by, "found": {}}
            self._index = index                                     # published complete
        key = tuple(legs)
        found = index["found"].get(key)
        if found is None:
            found = []
            for v in index["by"].get(tuple(sorted(legs)), []):
                for order in permutations(range(len(legs))):
                    if all(legs[order[i]] == v.legs[i] for i in range(len(legs))):
                        found.append((v, order))
                        break
            index["found"][key] = found
        return found


# --- bosonic vertices and propagators ------------------------------------------------------------------

def _dot(x, y):
    return np.sum(x * y * METRIC, axis=-1)


@dataclass
class Leg:
    """A leg at a vertex: its particle, incoming momentum (n, 4), and its polarisation if it is an external vector."""

    name: str
    p: np.ndarray
    eps: np.ndarray | None = None        # None for the internal line or a scalar


def _vvv(v: Vertex, legs: list[Leg], open_slot: int | None):
    k1, k2, k3 = (leg.p for leg in legs)
    e = [leg.eps for leg in legs]
    if open_slot is None:
        return v.c * (_dot(e[0], e[1]) * _dot(k1 - k2, e[2]) + _dot(e[1], e[2]) * _dot(k2 - k3, e[0])
                      + _dot(e[2], e[0]) * _dot(k3 - k1, e[1]))
    i, j, k = {0: (0, 1, 2), 1: (1, 2, 0), 2: (2, 0, 1)}[open_slot]
    ki, kj, kk = legs[i].p, legs[j].p, legs[k].p
    ej, ek = e[j], e[k]
    # the cyclic structure with slot i open: g^{ij}(k_i − k_j)^k + g^{jk}(k_j − k_k)^i + g^{ki}(k_k − k_i)^j
    return v.c * (ej * _dot(ki - kj, ek)[:, None] + (_dot(ej, ek))[:, None] * (kj - kk)
                  + ek * _dot(kk - ki, ej)[:, None])


def _vvvv(v: Vertex, legs: list[Leg], open_slot: int | None):
    e = [leg.eps for leg in legs]
    pairs = (((0, 1), (2, 3), v.c), ((0, 2), (1, 3), v.c2), ((0, 3), (1, 2), v.c3))
    if open_slot is None:
        return sum(c * _dot(e[a], e[b]) * _dot(e[x], e[y]) for (a, b), (x, y), c in pairs)
    out = 0.0
    for (a, b), (x, y), c in pairs:
        pair, other = ((a, b), (x, y)) if open_slot in (a, b) else ((x, y), (a, b))
        partner = pair[1] if pair[0] == open_slot else pair[0]
        out = out + c * e[partner] * _dot(e[other[0]], e[other[1]])[:, None]
    return out


def _vertex_value(v: Vertex, legs: list[Leg], open_slot: int | None):
    """V of a bosonic vertex with external polarisations in place; with one internal vector slot left open (n, 4)."""
    if v.kind in ("SSS", "SSSS"):
        return np.full(len(legs[0].p), complex(v.c))
    if v.kind == "VSS":
        vec, a, b = legs
        current = v.c * (a.p - b.p)
        return current if open_slot == 0 else v.c * _dot(vec.eps, a.p - b.p)
    if v.kind in ("VVS", "VVSS"):
        e1, e2 = legs[0].eps, legs[1].eps
        if open_slot == 0:
            return v.c * e2
        if open_slot == 1:
            return v.c * e1
        return v.c * _dot(e1, e2)
    if v.kind == "VVV":
        return _vvv(v, legs, open_slot)
    if v.kind == "VVVV":
        return _vvvv(v, legs, open_slot)
    raise ValueError(f"not a bosonic vertex: {v.kind}")


def _denominator(particle: Particle, q: np.ndarray) -> np.ndarray:
    return _dot(q, q) - particle.mass ** 2 + 1j * particle.mass * particle.width


def _propagate(x, y, particle: Particle, q: np.ndarray):
    """V₁ D V₂ for an internal boson (the i of the propagator removed): x, y are values or currents."""
    denominator = _denominator(particle, q)
    if particle.spin == 0:
        return x * y / denominator
    if particle.mass == 0.0:
        return -_dot(x, y) / denominator
    return (-_dot(x, y) + _dot(x, q) * _dot(q, y) / particle.mass ** 2) / denominator


# --- fermion vertices ------------------------------------------------------------------------------------

def _fermion_current(v: Vertex, ubar: np.ndarray, u: np.ndarray):
    """ū Γ u for an FFS (value) or FFV (current) vertex, along its own orientation."""
    if v.kind in ("FFS", "FFSS"):
        gamma = v.c * UNIT + 1j * v.c2 * GAMMA5
        return np.einsum("ni,ij,nj->n", ubar, gamma, u)
    chiral = v.c * UNIT + v.c2 * GAMMA5
    return np.einsum("ni,mij,jk,nk->nm", ubar, GAMMA, chiral, u)


def _chiral(v: Vertex, reverse: bool) -> np.ndarray:
    """The Dirac matrix of an FFS/FFSS vertex, or the chiral factor (a + bγ⁵) after γ^μ of an FFV vertex,
    with C Γᵀ C⁻¹ applied when the line runs against the vertex's orientation."""
    if v.kind in ("FFS", "FFSS"):
        return v.c * UNIT + 1j * v.c2 * GAMMA5
    return (-v.c if reverse else v.c) * UNIT + v.c2 * GAMMA5


def _fermion_gamma(v: Vertex, eps: np.ndarray | None, reverse: bool = False) -> np.ndarray:
    """Γ of a fermion vertex as (n, 4, 4) matrices (an FFV vertex with its boson's polarisation)."""
    chiral = _chiral(v, reverse)
    if v.kind in ("FFS", "FFSS"):
        return chiral[None]
    return slash(eps) @ chiral[None]


SIGMA = np.array([[0.5j * (GAMMA[m] @ GAMMA[n] - GAMMA[n] @ GAMMA[m]) for n in range(4)] for m in range(4)])


def _bilinear(kind: str, psi: np.ndarray, psibar: np.ndarray, reverse: bool) -> np.ndarray:
    """ψ̄Γψ for one line of a four-fermion vertex: a scalar (S, P), a vector (V, A) or a tensor (T); against the line's
    orientation C Γᵀ C⁻¹, which reverses V and T and keeps S, P and A."""
    if kind == "S":
        return np.einsum("ni,ni->n", psibar, psi)
    if kind == "P":
        return 1j * np.einsum("ni,ij,nj->n", psibar, GAMMA5, psi)
    sign = -1.0 if reverse and kind in ("V", "T") else 1.0
    if kind == "V":
        return sign * np.einsum("ni,mij,nj->nm", psibar, GAMMA, psi)
    if kind == "A":
        return np.einsum("ni,mij,jk,nk->nm", psibar, GAMMA, GAMMA5, psi)
    if kind == "T":
        return sign * np.einsum("ni,mrij,nj->nmr", psibar, SIGMA, psi)
    raise ValueError(f"unknown four-fermion structure {kind!r}")


def _tensor_dot(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """a^μν b_μν."""
    return np.einsum("nmr,m,r,nmr->n", a, METRIC, METRIC, b)


# --- diagrams --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class _Use:
    """A vertex in a diagram: each slot's edge (an external leg 0–3, or "x" for the internal line), and
    whether its fermion line runs against the vertex's orientation."""
    vertex: Vertex
    edges: tuple
    reverse: bool = False
    reverse2: bool = False       # an FFFF vertex's second line (slots 2, 3)


@dataclass(frozen=True)
class _Diagram:
    """One tree diagram: contact (one vertex) or exchange of ``x`` between ``uses[0]`` (legs ``pairs[0]``)
    and ``uses[1]`` (``pairs[1]``); its fermion lines (start, end) and Fermi sign."""
    kind: str
    uses: tuple
    x: Particle | None = None
    pairs: tuple = ()
    chains: tuple = ()
    sign: int = 1


def _parity(order: tuple[int, ...]) -> int:
    """The sign of a permutation (by counting inversions)."""
    inversions = sum(order[i] > order[j] for i in range(len(order)) for j in range(i + 1, len(order)))
    return -1 if inversions % 2 else 1


def _spinors_u(p3: np.ndarray, mass: float, xi: np.ndarray) -> np.ndarray:
    """u(p) = (√(E+m) ξ, σ·p ξ/√(E+m)) with one two-spinor ξ per row (n, 2)."""
    from adroit.constraints.amplitudes import _sigma_dot
    e = np.sqrt(mass ** 2 + np.sum(p3 ** 2, axis=1))
    root = np.sqrt(e + mass)[:, None]
    return np.concatenate([root * xi, np.einsum("nij,nj->ni", _sigma_dot(p3), xi) / root], axis=1)


def _assign(vertex: Vertex, edges: list, names: list[str], fermion_in=None, fermion_out=None):
    """The slot → edge assignment of a vertex: the fermion line enters through slot 1 and leaves through
    slot 0 (standard) or the reverse; other slots by name. Returns (edges by slot, reverse) or None."""
    lookup = dict(zip(edges, names))
    tries = [(False,)]
    if vertex.kind in FERMIONIC:
        a, b = lookup[fermion_out], lookup[fermion_in]
        tries = []
        if vertex.legs[0] == a and vertex.legs[1] == b:
            tries.append((False, fermion_out, fermion_in))
        if vertex.legs[0] == b and vertex.legs[1] == a and a != b:
            tries.append((True, fermion_in, fermion_out))
    for attempt in tries:
        slots = [None] * len(vertex.legs)
        rest = list(edges)
        if vertex.kind in FERMIONIC:
            slots[0], slots[1] = attempt[1], attempt[2]
            rest.remove(attempt[1])
            rest.remove(attempt[2])
        for k, name in enumerate(vertex.legs):
            if slots[k] is not None:
                continue
            match = next((e for e in rest if lookup[e] == name), None)
            if match is None:
                break
            slots[k] = match
            rest.remove(match)
        else:
            return tuple(slots), attempt[0]
    return None


class Process:
    """a b → c d of a model: its diagrams found once, its cross-section at any s."""

    def __init__(self, model: Model, a: str, b: str, c: str, d: str, points: int = NODES) -> None:
        self.model, self.names, self.points = model, (a, b, c, d), points
        self.p = [model.particles[n] for n in (a, b, c, d)]
        self._final: tuple | None = None          # off-shell final masses (``sigma``; arrays in ``sigma_offshell``)
        self._incoming = [a, b, self.p[2].conjugate, self.p[3].conjugate]
        self._fermions = [i for i in range(4) if self.p[i].spin == 0.5]
        if len(self._fermions) % 2:
            raise ValueError(f"{a} {b} → {c} {d}: an odd number of fermions")
        self._diagrams = self._find_diagrams()
        if not self._diagrams and self.p[0].spin != 0.5:
            raise ValueError(f"no tree diagram for {a} {b} → {c} {d}")
        self._colour = self._colour_matrix()

    def diagrams(self) -> list[_Diagram]:
        """The process's tree diagrams."""
        return self._diagrams

    # --- diagram finding --------------------------------------------------------------------------------
    def _find_diagrams(self) -> list[_Diagram]:
        m, n = self.model, self._incoming
        out = []
        for v, _ in m.find(list(n)):
            if v.kind == "FFFF":
                out += self._contractions(v, n)
                continue
            used = self._place(v, [0, 1, 2, 3], n)
            if used is not None:
                out.append(_Diagram("contact", (used,), chains=self._contact_chains(), sign=1))
        for x in m.particles.values():
            for kind, (i1, j1), (i2, j2) in (("s", (0, 1), (2, 3)), ("t", (0, 2), (1, 3)), ("u", (0, 3), (1, 2))):
                first, second = [n[i1], n[j1], x.conjugate], [x.name, n[i2], n[j2]]
                for v1, _ in m.find(first):
                    for v2, _ in m.find(second):
                        diagram = self._exchange(kind, x, v1, v2, (i1, j1), (i2, j2))
                        if diagram is not None:
                            out.append(diagram)
        return out

    def _contractions(self, v: Vertex, n: list[str]) -> list[_Diagram]:
        """Every Wick contraction of four external fermions with an FFFF vertex's slots (module docstring)."""
        if len(self._fermions) != 4:
            return []
        out, seen = [], set()
        for slots in permutations(range(4)):
            if any(v.legs[k] != n[slots[k]] for k in range(4)) or slots in seen:
                continue
            seen.add(slots)
            chains, reverse = [], []
            for leave, enter in ((0, 1), (2, 3)):
                start, end = _flow((slots[leave], slots[enter]))
                chains.append((start, end))
                reverse.append(start != slots[enter])
            sign = _parity(tuple(k for s, e in sorted(chains) for k in (e, s)))
            out.append(_Diagram("contact", (_Use(v, slots, reverse[0], reverse[1]),), chains=tuple(chains),
                                sign=sign))
        return out

    def _contact_chains(self) -> tuple:
        f = self._fermions
        return (_flow(f),) if len(f) == 2 else ()

    def _place(self, v: Vertex, edges: list, names: list[str], fermion_in=None, fermion_out=None) -> _Use | None:
        fermions = [e for e in edges if (self.p[e].spin if e != "x" else self._x_spin) == 0.5]
        if v.kind in FERMIONIC and fermion_in is None:
            if len(fermions) != 2:
                return None
            fermion_in, fermion_out = _flow(fermions)
        if v.kind not in FERMIONIC and fermions:
            return None
        found = _assign(v, edges, names, fermion_in, fermion_out)
        return None if found is None else _Use(v, found[0], found[1])

    def _exchange(self, kind: str, x: Particle, v1: Vertex, v2: Vertex, pair1, pair2) -> _Diagram | None:
        n = self._incoming
        self._x_spin = x.spin
        e1, e2 = [pair1[0], pair1[1], "x"], [pair2[0], pair2[1], "x"]
        names1, names2 = [n[pair1[0]], n[pair1[1]], x.conjugate], [n[pair2[0]], n[pair2[1]], x.name]
        f = self._fermions
        if x.spin == 0.5:
            start, end = _flow(f)
            if not ((start in pair1) ^ (end in pair1)):
                return None
            first_starts = start in pair1                         # the flow runs v1 → v2
            u1 = self._place(v1, e1, names1, *((start, "x") if first_starts else ("x", end)))
            u2 = self._place(v2, e2, names2, *(("x", end) if first_starts else (start, "x")))
            chains, sign = ((start, end),), 1
        else:
            u1, u2 = self._place(v1, e1, names1), self._place(v2, e2, names2)
            chains = tuple(sorted(_flow(p) for p in (pair1, pair2) if all(k in f for k in p)))
            sign = _parity(tuple(k for s, e in chains for k in (e, s))) if len(chains) == 2 else 1
        if u1 is None or u2 is None:
            return None
        return _Diagram(kind, (u1, u2), x, (pair1, pair2), chains, sign)

    # --- colour -------------------------------------------------------------------------------------------
    def _colour_matrix(self) -> np.ndarray:
        reps = [self.model.particles[n].representation for n in self._incoming]
        dims = [tree_colour.DIMENSION[r] for r in reps]
        tensors = []
        for d in self._diagrams:
            uses = []
            for use in d.uses:
                slot_reps = [self.model.particles[name].representation for name in use.vertex.legs]
                uses.append((tree_colour.vertex_tensor(use.vertex.colour, slot_reps), use.edges))
            tensors.append(tree_colour.diagram_tensor(uses, dims))
        self._initial_colours = dims[0] * dims[1]
        self._colour_dims, self._colour_tensors = dims, tensors
        return tree_colour.interference(tensors) if tensors else np.zeros((0, 0))

    def mass(self, i: int) -> float:
        """Leg i's mass: the particle's, or a final leg's off-shell mass while ``sigma`` integrates over it."""
        return self._final[i - 2] if self._final is not None and i >= 2 else self.p[i].mass

    # --- external states --------------------------------------------------------------------------------
    def _states(self, i: int, momentum: np.ndarray) -> list:
        particle, mass = self.p[i], self.mass(i)
        if particle.spin == 0:
            return [None]
        if particle.spin == 0.5:
            return [0, 1]
        if i < 2:
            states = _initial_polarisations(momentum, mass if mass > 0 else 1.0)
            return states if mass > 0 else states[:2]
        if np.all(np.asarray(mass) <= 0):         # a final leg's mass may be one per row (``sigma_offshell``)
            return _transverse(momentum)
        if conserved_current(self.model, self.names[i]):
            return _ward_polarisations(momentum, mass)
        return polarisations(momentum, mass)

    def _externals(self, momenta: list[np.ndarray]) -> tuple[dict, int]:
        """Every external state at once: arrays of shape (configurations × angles, 4)."""
        states = [self._states(i, momenta[i]) for i in range(4)]
        configs = list(product(*[range(len(s)) for s in states]))
        n = len(momenta[0])
        ext = {"q": [], "eps": [], "u": [], "v": []}
        for i in range(4):
            q = momenta[i] if i < 2 else -momenta[i]
            ext["q"].append(np.tile(q, (len(configs), 1)))
            eps = u = v = None
            if self.p[i].spin == 1:
                eps = np.concatenate([states[i][c[i]] for c in configs])
            elif self.p[i].spin == 0.5:
                spin = np.concatenate([np.tile(_BASIS[c[i]], (n, 1)) for c in configs])
                mass = self.mass(i)
                mass = np.tile(mass, len(configs)) if np.ndim(mass) else mass        # rows as the momenta's
                u = _spinors_u(np.tile(momenta[i][:, 1:], (len(configs), 1)), mass, spin)
                v = conjugate(u)
            ext["eps"].append(eps)
            ext["u"].append(u)
            ext["v"].append(v)
        ext["slash"] = [None if e is None else slash(e) for e in ext["eps"]]        # ε̸ of each external vector
        return ext, len(configs)

    # --- amplitudes ---------------------------------------------------------------------------------------
    def squared(self, s: float, cos_theta: np.ndarray) -> np.ndarray:
        """Σ|M|² summed over final and averaged over initial spins, polarisations and colours."""
        p1, p2, k1, k2, _, _ = frame(s, *(self.mass(i) for i in range(4)), cos_theta)
        ext, configs = self._externals([p1, p2, k1, k2])
        n = len(cos_theta)
        amps = np.array([self._amplitude(d, ext).reshape(configs, n) for d in self._diagrams])
        if not len(amps):
            return np.zeros(n)
        total = np.real(np.einsum("dcn,de,ecn->n", amps, self._colour, amps.conj()))
        average = np.prod([len(self._states(i, m)) for i, m in ((0, p1), (1, p2))]) * self._initial_colours
        return total / average

    def amplitudes(self, s: float, cos_theta: np.ndarray) -> np.ndarray:
        """M itself, with every external state explicit: shape (colour of legs 0–3, spin state of legs 0–3, angle).

        Legs 0, 1 are incoming along ±z and legs 2, 3 outgoing at angle θ in the x–z plane. A colour index is the
        particle's own (an outgoing particle's index is its colour). A fermion's spin label is its spin along z
        in its rest frame, for u and v = C ūᵀ alike (``_states``), so amplitudes of different processes with the
        same external particles interfere as written (G7's channel matrices)."""
        cos_theta = np.asarray(cos_theta, dtype=float)
        p1, p2, k1, k2, _, _ = frame(s, *(self.mass(i) for i in range(4)), cos_theta)
        momenta = [p1, p2, k1, k2]
        counts = [len(self._states(i, momenta[i])) for i in range(4)]
        n = len(cos_theta)
        if not self._diagrams:
            return np.zeros(self._colour_dims + counts + [n], dtype=complex)
        ext, configs = self._externals(momenta)
        amps = np.array([self._amplitude(d, ext).reshape(configs, n) for d in self._diagrams])
        tensors = np.array(self._colour_tensors)
        out = np.einsum("dpqrs,dkn->pqrskn", tensors, amps)
        return out.reshape(self._colour_dims + counts + [n])

    def _leg(self, edge, use_index: int, d: _Diagram, ext: dict) -> Leg:
        if edge != "x":
            return Leg(self._incoming[edge], ext["q"][edge], ext["eps"][edge])
        q = ext["q"][d.pairs[0][0]] + ext["q"][d.pairs[0][1]]
        return Leg(d.x.conjugate, -q) if use_index == 0 else Leg(d.x.name, q)

    def _boson_value(self, use: _Use, k: int, d: _Diagram, ext: dict, open_ok: bool = True):
        legs = [self._leg(e, k, d, ext) for e in use.edges]
        open_slot = use.edges.index("x") if (open_ok and d.x is not None and d.x.spin == 1 and "x" in use.edges) \
            else None
        return _vertex_value(use.vertex, legs, open_slot)

    def _spinors(self, start: int, end: int, ext: dict) -> tuple[np.ndarray, np.ndarray]:
        """ψ_start (u where the flow enters an incoming leg, v an outgoing one) and ψ̄_end."""
        psi = ext["u"][start] if start < 2 else ext["v"][start]
        psibar = bar(ext["v"][end]) if end < 2 else bar(ext["u"][end])
        return psi, psibar

    def _apply(self, use: _Use, d: _Diagram, ext: dict, k: int, spinor: np.ndarray) -> np.ndarray:
        """Γ ψ for a fermion vertex with every boson leg filled (an external polarisation): (N, 4), done as
        matrix–vector products along the line rather than by building Γ as N matrices."""
        v = use.vertex
        out = spinor @ _chiral(v, use.reverse).T
        if v.kind == "FFV":
            out = np.einsum("nij,nj->ni", ext["slash"][use.edges[2]], out)
        return out

    def _amplitude(self, d: _Diagram, ext: dict) -> np.ndarray:
        """M of one diagram for every external state at once."""
        if d.kind == "contact":
            use = d.uses[0]
            if use.vertex.kind == "FFFF":
                return d.sign * self._four_fermion(use, d, ext)
            if use.vertex.kind in FERMIONIC:
                start, end = d.chains[0]
                psi, psibar = self._spinors(start, end, ext)
                return d.sign * np.einsum("ni,ni->n", psibar, self._apply(use, d, ext, 0, psi))
            return self._boson_value(use, 0, d, ext, open_ok=False)
        if d.x.spin == 0.5:
            return -self._fermion_exchange(d, ext)
        values = [self._side(use, k, d, ext) for k, use in enumerate(d.uses)]
        q = ext["q"][d.pairs[0][0]] + ext["q"][d.pairs[0][1]]
        return -d.sign * _propagate(values[0], values[1], d.x, q)

    def _four_fermion(self, use: _Use, d: _Diagram, ext: dict) -> np.ndarray:
        """Σ_k c_k (ψ̄Γ_kψ)(ψ̄Γ'_kψ) of a four-fermion contraction, each line along its own flow."""
        lines = [(*self._spinors(start, end, ext), reverse)
                 for (start, end), reverse in zip(d.chains, (use.reverse, use.reverse2))]
        total = 0.0
        for first, second, c in use.vertex.structure:
            a, b = _bilinear(first, *lines[0]), _bilinear(second, *lines[1])
            if a.ndim != b.ndim:
                raise ValueError(f"the four-fermion structure {first} ⊗ {second} does not contract")
            total = total + c * (a * b if a.ndim == 1 else _dot(a, b) if a.ndim == 2 else _tensor_dot(a, b))
        return total

    def _side(self, use: _Use, k: int, d: _Diagram, ext: dict):
        """One end of a boson exchange: a bosonic vertex's value, or a fermion line's value or current."""
        if use.vertex.kind not in FERMIONIC:
            return self._boson_value(use, k, d, ext)
        start, end = next(c for c in d.chains if c[0] in use.edges)
        psi, psibar = self._spinors(start, end, ext)
        if use.vertex.kind == "FFV" and use.edges[2] == "x":
            chiral_psi = psi @ _chiral(use.vertex, use.reverse).T
            return np.einsum("ni,mij,nj->nm", psibar, GAMMA, chiral_psi)
        return np.einsum("ni,ni->n", psibar, self._apply(use, d, ext, k, psi))

    def _fermion_exchange(self, d: _Diagram, ext: dict) -> np.ndarray:
        """ψ̄_end Γ_B S(p) Γ_A ψ_start, the flow from the start leg's vertex A through x to vertex B."""
        start, end = d.chains[0]
        a = 0 if start in d.uses[0].edges else 1
        use_a, use_b = d.uses[a], d.uses[1 - a]
        q = ext["q"][d.pairs[0][0]] + ext["q"][d.pairs[0][1]]
        flow = q if a == 0 else -q
        x = d.x
        psi, psibar = self._spinors(start, end, ext)
        line = self._apply(use_a, d, ext, a, psi)
        line = (np.einsum("nij,nj->ni", slash(flow), line) + x.mass * line) / _denominator(x, flow)[:, None]
        line = self._apply(use_b, d, ext, 1 - a, line)
        return d.sign * np.einsum("ni,ni->n", psibar, line)

    def sigma(self, s: float, final_masses: tuple[float, float] | None = None) -> float:
        """σ(s) in GeV⁻² (½ for identical final particles); ``final_masses``: the final legs off shell."""
        self._final = final_masses
        try:
            masses = [self.mass(i) for i in range(4)]
            root = np.sqrt(s)
            if root <= max(masses[0] + masses[1], masses[2] + masses[3]) * (1.0 + 1e-12) or not self._diagrams:
                return 0.0
            x, w = gauss(self.points)
            _, _, _, _, p, k = frame(s, *masses, x)
            sq = self.squared(s, x)
        finally:
            self._final = None
        sigma = (k / p) / (32.0 * np.pi * s) * float(np.sum(w * sq))
        return 0.5 * sigma if self.names[2] == self.names[3] else sigma

    def sigma_offshell(self, s: float, final_masses: np.ndarray, rows: int = 200_000) -> np.ndarray:
        """``sigma(s, (m₃, m₄))`` at every pair of final masses (P, 2) at once (F2): the pairs' angles stacked as
        rows of one evaluation, in chunks of at most ``rows`` rows × external states. A pair below its threshold
        gives 0, as ``sigma``."""
        finals = np.asarray(final_masses, dtype=float).reshape(-1, 2)
        out = np.zeros(len(finals))
        m1, m2 = self.p[0].mass, self.p[1].mass
        root = np.sqrt(s)
        if not self._diagrams or root <= (m1 + m2) * (1.0 + 1e-12):
            return out
        x, w = gauss(self.points)
        n = len(x)
        half = 0.5 if self.names[2] == self.names[3] else 1.0
        states = int(np.prod([4 if self.p[i].spin == 1 else 2 if self.p[i].spin == 0.5 else 1 for i in range(4)]))
        size = max(1, rows // (n * states))
        open_ = root > finals.sum(axis=1) * (1.0 + 1e-12)
        massless = open_ & (finals <= 0).any(axis=1)            # a massless leg's states differ: one by one
        for k in np.flatnonzero(massless):
            out[k] = self.sigma(s, tuple(finals[k]))
        open_ = np.flatnonzero(open_ & ~massless)
        for start in range(0, len(open_), size):
            chunk = open_[start:start + size]
            m3, m4 = np.repeat(finals[chunk, 0], n), np.repeat(finals[chunk, 1], n)
            cos = np.tile(x, len(chunk))
            self._final = (m3, m4)
            try:
                _, _, _, _, p, k = frame(s, m1, m2, m3, m4, cos)
                sq = self.squared(s, cos).reshape(len(chunk), n)
            finally:
                self._final = None
            out[chunk] = half * (k.reshape(len(chunk), n)[:, 0] / p) / (32.0 * np.pi * s) * np.sum(w * sq, axis=1)
        return out
