"""The physical spectrum of a typed model (G1): its vacuum, mass matrices and mass eigenstates.

From the gauge basis (``gauge_basis.build``):

1. **The vacuum.** The stated vacuum values are put in the neutral components; H has v = 246.22 GeV. Each field
   with a vacuum value has its m² fixed by its tadpole condition ∂V/∂x = 0 along its vev. A real gauge singlet
   with zero vacuum value takes an implicit linear term that cancels its tadpole. Every other direction must be
   stationary, or the model is refused: the stated vacuum is not a vacuum.
2. **Unbroken charges.** The states are sorted by the charges the vacuum keeps:
   - the electric charge;
   - every U(1) acting on whole fields that the model's terms conserve and no vacuum value breaks. These are
     found as the null space of the terms' charge sums, so they include a dark-fermion number that keeps a
     vectorlike state Dirac.

   A state with nonzero charges is complex (scalars) or Dirac (fermions). A neutral one is real or Majorana.
3. **Mass matrices:**
   - **Scalars:** the Hessian of V at the vacuum. It is real symmetric in the neutral sector and Hermitian,
     M²_ab = u_a† H u_b, in a charged one. The would-be Goldstone directions t^V v of the massive gauge bosons are
     removed (unitary gauge), and the Goldstone theorem M² t^V v = 0 is checked.
   - **Fermions:** M_ij at the vacuum, from L ⊃ −½ M_ij ψ_iψ_j + h.c. A neutral block takes a Takagi
     factorisation, Uᵀ M U = diag(m ≥ 0), so its states are Majorana. A charged block between charges c and −c
     takes a singular-value decomposition, so its states are Dirac.
   - **Vectors:** from the vacuum (½ m²_VW V W), stated masses and kinetic mixing. The kinetic matrix is brought
     to unity first (Cholesky), then the mass matrix is diagonalised. W± are formed from W¹, W².
4. **The output.** The states, each with its mass, spin, charge, colour, Z₂ parity and composition, and the
   rotations, which G2 needs for the vertices.
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from adroit.core.model_spec import FieldRole, ModelSpec
from adroit.core.state import StrictModel
from adroit.model_building import gauge_basis as gbm
from adroit.model_building.gauge_basis import GaugeBasis, GaugeBasisError

TOLERANCE = 1e-7           # relative: stationarity, degeneracy, Goldstone checks


class State(StrictModel):
    """One physical state."""

    name: str
    spin: float
    kind: Literal["real", "complex", "majorana", "dirac", "vector", "charged_vector", "goldstone"]
    mass_gev: float
    charge: float                                  # electric charge (of the particle; its antiparticle has −)
    colour: str = "1"
    parity: int = 1                                # under the stabilising Z₂
    composition: dict[str, float] = Field(default_factory=dict)   # |amplitude|² on the gauge-basis components


class Spectrum(StrictModel):
    """The physical states, lightest first within each spin, and what was solved or assumed."""

    states: list[State]
    solved: dict[str, float] = Field(default_factory=dict)        # m² of fields fixed by the vacuum (GeV²)
    linear_terms: dict[str, float] = Field(default_factory=dict)  # implicit tadpole terms of real singlets
    notes: list[str] = Field(default_factory=list)

    def state(self, name: str) -> State:
        """One state by name."""
        return next(s for s in self.states if s.name == name)

    def dark_matter(self) -> State:
        """The lightest Z₂-odd state with no electric charge and no colour."""
        odd = [s for s in self.states if s.parity == -1 and s.charge == 0 and s.colour == "1"
               and s.kind != "goldstone"]
        if not odd:
            raise GaugeBasisError("no neutral, colourless Z₂-odd state: the model has no dark matter candidate")
        return min(odd, key=lambda s: s.mass_gev)


class MassBasis(BaseModel):
    """The rotations from the gauge basis to the states (for G2), with the vacuum and the shifted Lagrangian."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    gauge: GaugeBasis
    spectrum: Spectrum
    vacuum: np.ndarray                             # v on the real coordinates
    scalar_states: list[tuple[str, np.ndarray]]    # (state name, its complex vector u on the coordinates)
    fermion_states: list[tuple[str, np.ndarray, np.ndarray | None]]   # (name, left vector, partner vector)
    vector_states: list[tuple[str, dict[str, complex]]]               # (name, gauge vector → amplitude)
    potential: gbm.Poly                            # V(v + y), mass parameters and linear terms included


# --- the vacuum ------------------------------------------------------------------------------------

def vacuum(gb: GaugeBasis) -> np.ndarray:
    """v on the real coordinates: each stated vacuum value in its field's neutral component."""
    v = np.zeros(len(gb.comp.coordinates))
    for name, value in gb.vevs.items():
        found = [k for k, c in enumerate(gb.comp.coordinates)
                 if c.field == name and c.part in ("re", "r") and abs(c.charge) < 1e-12]
        if not found:
            raise GaugeBasisError(f"{name} has a vacuum value but no neutral component (Q = T₃ + Y = 0)")
        v[found[0]] = value
    return v


def _norm_poly(gb: GaugeBasis, name: str) -> gbm.Poly:
    """N_F = ½ Σ x_k² over F's coordinates, so that m² N_F is m²|F|² (or ½m²F² for a real field)."""
    return {(k, k): 0.5 for k, c in enumerate(gb.comp.coordinates) if c.field == name}


def _real_singlet(gb: GaugeBasis, name: str) -> bool:
    f = gb.spec.field(name)
    return f.self_conjugate and f.charges.su2 == 1 and f.charges.su3 == "1" and f.charges.hypercharge == 0 \
        and not any(f.charges.extra.values())


def solve_vacuum(gb: GaugeBasis, v: np.ndarray) -> tuple[gbm.Poly, dict[str, float], dict[str, float]]:
    """(V(v + y) with the solved terms, the solved m² by field, the implicit linear terms by field)."""
    potential = dict(gb.potential)
    for name, m2 in gb.quadratic.items():
        if m2 is not None:
            potential = gbm.poly_add(potential, _norm_poly(gb, name), m2)
    shifted = gbm.shift(potential, v)
    g = gbm.gradient(shifted, len(v)).real
    solved, linear = {}, {}
    for name, value in gb.vevs.items():
        k = int(np.flatnonzero((v != 0) & np.array([c.field == name for c in gb.comp.coordinates]))[0]) \
            if value else None
        if value == 0 or k is None:
            continue
        mu2 = -g[k] / value
        solved[name] = mu2
        shifted = gbm.poly_add(shifted, gbm.shift(_norm_poly(gb, name), v), mu2)
    g = gbm.gradient(shifted, len(v)).real
    for k, c in enumerate(gb.comp.coordinates):
        if abs(g[k]) > 0 and v[k] == 0 and _real_singlet(gb, c.field):
            linear[c.field] = -g[k]
            shifted = gbm.poly_add(shifted, {(k,): -g[k]})
    g = gbm.gradient(shifted, len(v)).real
    if not len(v):                                       # no scalar coordinates (a broken-phase model of fermions)
        return shifted, solved, linear
    scale = max(1.0, float(np.max(np.abs(gbm.hessian(shifted, len(v))))) * max(1.0, float(np.max(np.abs(v)))))
    bad = [k for k in range(len(v)) if abs(g[k]) > TOLERANCE * scale]
    if bad:
        c = gb.comp.coordinates[bad[0]]
        raise GaugeBasisError(f"the stated vacuum is not stationary: ∂V/∂{c.field}[m={c.m:g}, {c.part}] = "
                              f"{g[bad[0]]:.3g} GeV³")
    return shifted, solved, linear


# --- unbroken charges ------------------------------------------------------------------------------

def field_charges(gb: GaugeBasis) -> dict[str, np.ndarray]:
    """Each new field's charges under every U(1) acting on whole fields that the terms conserve and no vacuum
    value breaks (the null space of the terms' charge sums); Majorana and real fields carry none."""
    spec = gb.spec
    names = [f.name for f in spec.fields if f.spin in (0, 0.5) and f.role is not FieldRole.standard_model]
    if not names:
        return {}
    col = {n: k for k, n in enumerate(names)}
    rows = []
    for t in spec.terms:
        row = np.zeros(len(names))
        for o in t.fields:
            if o.field in col:
                row[col[o.field]] += -1.0 if o.conjugate else 1.0
        if np.any(row):
            rows.append(row)
    for n in names:
        f = spec.field(n)
        if f.self_conjugate or n in gb.vevs or (f.spin == 0.5 and f.chirality and gbm._real_multiplet(
                f.model_copy(update={"self_conjugate": True})) and _has_majorana_mass(gb, n)):
            row = np.zeros(len(names))
            row[col[n]] = 1.0
            rows.append(row)
    matrix = np.array(rows) if rows else np.zeros((0, len(names)))
    _, s, vt = np.linalg.svd(np.vstack([matrix, np.zeros((1, len(names)))]))
    rank = int(np.sum(s > 1e-9))
    basis = vt[rank:]                                    # each row: one conserved U(1), charges by field
    return {n: basis[:, col[n]].copy() for n in names}


def _has_majorana_mass(gb: GaugeBasis, name: str) -> bool:
    """A Weyl field in a real representation with a mass of its own (a stated mass or a ψψ term)."""
    f = gb.spec.field(name)
    return f.mass_gev is not None or any(len(t.fields) == 2 and all(o.field == name for o in t.fields)
                                         for t in gb.spec.terms)


def _key(q: np.ndarray) -> tuple:
    return tuple(np.round(q, 6) + 0.0)


def _positive(q: np.ndarray) -> bool:
    """Whether a charge vector (Q, u₁, u₂, …) is the particle side: the conserved field charges (a dark-fermion
    number, say) decide first, so that the particle carries them positively; the electric charge Q decides only
    when there are none."""
    dark = q[1:][np.abs(q[1:]) > 1e-9]
    if dark.size:
        return bool(dark[0] > 0)
    return bool(abs(q[0]) > 1e-9 and q[0] > 0)


# --- scalars ---------------------------------------------------------------------------------------

def _complex_components(gb: GaugeBasis, charges: dict[str, np.ndarray]) -> tuple[list, list[int]]:
    """(charged components [(w, q, label)], neutral real coordinates): w gives F = w·x."""
    charged, neutral = [], set()
    width = len(next(iter(charges.values()))) if charges else 0
    for name, forms in gb.comp.scalar_forms.items():
        f = gb.spec.field(name)
        u = charges.get(name, np.zeros(width))
        real = gbm._real_multiplet(f)
        for k, (form, m) in enumerate(zip(forms, gbm._m_values(f.charges.su2))):
            q_em = gbm._charge(f, m, gb.spec.phase)
            q = np.concatenate([[q_em], np.zeros(width) if real else u])
            coords = list(form)
            if real and m < 0:
                continue                                   # the conjugate of the +m component
            if np.allclose(q, 0):
                neutral.update(coords)
                continue
            w = np.zeros(len(gb.comp.coordinates), dtype=complex)
            for c, a in form.items():
                w[c] = a
            if not _positive(q):
                w, q = w.conj(), -q
            charged.append((w, q, f"{name}[m={m:g}]"))
    return charged, sorted(neutral)


def scalar_states(gb: GaugeBasis, hess: np.ndarray, goldstones: np.ndarray,
                  charges: dict[str, np.ndarray]) -> list[tuple[str, np.ndarray, float, float, int, str]]:
    """(label, u, m², Q, parity, colour) of every physical scalar: the Hessian with the Goldstone directions projected
    out, diagonalised sector by sector (u is the complex vector with x ⊃ u F + c.c., or a real unit vector)."""
    size = hess.shape[0]
    project = np.eye(size) - goldstones @ goldstones.T
    h = project @ hess @ project
    charged, neutral = _complex_components(gb, charges)
    out = []
    if neutral:
        sub = h[np.ix_(neutral, neutral)]
        values, vectors = np.linalg.eigh(sub)
        vectors = vectors * np.sign(vectors[np.argmax(np.abs(vectors), axis=0), range(len(values))])[None, :]
        keep = _drop_goldstones(values, vectors, neutral, goldstones, size)
        for k in keep:
            u = np.zeros(size, dtype=complex)
            u[neutral] = vectors[:, k]
            out.append((_label(gb, u), u, values[k], 0.0, _parity(gb, u), _colour(gb, u)))
    sectors: dict[tuple, list] = {}
    for w, q, label in charged:
        sectors.setdefault(_key(q), []).append(w)
    for q, ws in sectors.items():
        us = [w.conj() for w in ws]                        # x ⊃ u_a F_a + c.c. with u_a = w_a*
        m2 = np.array([[ua.conj() @ h @ ub for ub in us] for ua in us])
        values, vectors = np.linalg.eigh(m2)
        for k in range(len(values)):
            u = sum(vectors[a, k] * us[a] for a in range(len(us)))
            if _is_goldstone(u, goldstones):
                continue
            out.append((_label(gb, u), u, values[k], q[0], _parity(gb, u), _colour(gb, u)))
    return out


def _is_goldstone(u: np.ndarray, goldstones: np.ndarray) -> bool:
    """True if the mode u (real or complex, on the coordinates) lies mostly in the Goldstone span."""
    if not goldstones.size:
        return False
    rest = u - goldstones @ (goldstones.T @ u)
    return float(np.linalg.norm(rest)) < 0.5 * float(np.linalg.norm(u))


def _drop_goldstones(values, vectors, coords, goldstones, size) -> list[int]:
    """The eigenvectors that are not would-be Goldstone directions."""
    keep = []
    for k in range(len(values)):
        u = np.zeros(size)
        u[coords] = vectors[:, k]
        if not _is_goldstone(u, goldstones):
            keep.append(k)
    return keep


def _label(gb: GaugeBasis, u: np.ndarray) -> str:
    weights: dict[str, float] = {}
    for k, a in enumerate(u):
        if abs(a) > 0:
            name = gb.comp.coordinates[k].field
            weights[name] = weights.get(name, 0.0) + abs(a) ** 2
    return max(weights, key=weights.get)


def _parity(gb: GaugeBasis, u: np.ndarray) -> int:
    k = int(np.argmax(np.abs(u)))
    return gb.comp.coordinates[k].parity


def _colour(gb: GaugeBasis, u: np.ndarray) -> str:
    k = int(np.argmax(np.abs(u)))
    return gb.comp.coordinates[k].colour


def goldstone_basis(gb: GaugeBasis, v: np.ndarray, hess: np.ndarray, notes: list[str]) -> np.ndarray:
    """An orthonormal basis (columns) of the would-be Goldstone directions t^V v; checks M² t^V v = 0."""
    directions = []
    scale = max(1.0, float(np.max(np.abs(hess)))) if hess.size else 1.0
    for name, t in gb.gauge.items():
        g = t @ v
        if np.linalg.norm(g) < 1e-9 * max(1.0, float(np.linalg.norm(v))):
            continue
        residual = np.linalg.norm(hess @ g) / (scale * np.linalg.norm(g))
        if residual > 1e-6:
            message = f"the Goldstone direction of {name} is not massless (|M² t v|/|M²||t v| = {residual:.2g})"
            if name in gb.explicit_vectors:
                notes.append(message + ": its couplings are not those of a gauge boson")
            else:
                raise GaugeBasisError(message)
        directions.append(g / np.linalg.norm(g))
    if not directions:
        return np.zeros((len(v), 0))
    u, s, _ = np.linalg.svd(np.array(directions).T, full_matrices=False)
    return u[:, : int(np.sum(s > 1e-9 * s[0]))]


# --- fermions --------------------------------------------------------------------------------------

def takagi(m: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(σ, U) with M = U diag(σ) Uᵀ, U unitary, σ ≥ 0, for a complex symmetric M: the Takagi vectors are
    v = x + iy from the eigenvectors (x; y) of [[Re M, Im M], [Im M, −Re M]] with positive eigenvalue σ (M v* = σ v);
    the null space of M gives the massless ones."""
    n = m.shape[0]
    a, b = m.real, m.imag
    values, vectors = np.linalg.eigh(np.block([[a, b], [b, -a]]))
    scale = max(1.0, float(np.max(np.abs(m)))) if m.size else 1.0
    positive = [k for k in range(2 * n) if values[k] > TOLERANCE * scale]
    columns = [vectors[:n, k] + 1j * vectors[n:, k] for k in positive]
    sigma = [values[k] for k in positive]
    if len(columns) < n:
        _, s, vh = np.linalg.svd(m)
        null = vh[len(columns):].conj().T                 # M x = 0 for these x; v = x* has M v* = 0
        for k in range(null.shape[1]):
            columns.append(null[:, k].conj())
            sigma.append(0.0)
    u = np.array(columns).T
    q, _ = np.linalg.qr(u)                                # re-orthonormalise (exact up to phases already)
    u = q * np.exp(1j * np.angle(np.diag(q.conj().T @ u)))[None, :]
    return np.array(sigma), u


def fermion_matrix(gb: GaugeBasis, v: np.ndarray) -> np.ndarray:
    """M_ij at the vacuum, from L ⊃ −½ M_ij ψ_iψ_j: M_ij = −h_ij (i ≠ j), M_ii = −2h_ii, h the bilinear's
    coefficient in L."""
    n = len(gb.comp.weyl)
    out = np.zeros((n, n), dtype=complex)
    for (i, j), poly in gb.fermion.items():
        value = sum(c * np.prod([v[k] for k in key]) for key, c in poly.items())
        if i == j:
            out[i, i] += -2 * value
        else:
            out[i, j] += -value
            out[j, i] += -value
    return out


def fermion_states(gb: GaugeBasis, v: np.ndarray, charges: dict[str, np.ndarray]) -> list[tuple]:
    """(label, left vector, partner vector or None, mass, Q, parity, colour): Majorana states of the neutral sector
    (ψ = U* λ) and Dirac states (ψ⁽ᶜ⁾ = W* χ, ψ⁽⁻ᶜ⁾ = Z ζ for M_c = W Σ Z†) of each charged pair of sectors."""
    m = fermion_matrix(gb, v)
    width = len(next(iter(charges.values()))) if charges else 0
    q = []
    for w in gb.comp.weyl:
        u = charges.get(w.field, np.zeros(width)) * (1 if w.block == "xi" else -1)
        f = gb.spec.field(w.field)
        if f.self_conjugate:
            u = np.zeros(width)
        q.append(np.concatenate([[w.charge], u]))
    scale = max(1.0, float(np.max(np.abs(m)))) if m.size else 1.0
    for i, j in zip(*np.nonzero(np.abs(m) > TOLERANCE * scale)):
        if not np.allclose(q[i] + q[j], 0, atol=1e-6):
            raise GaugeBasisError(f"a fermion mass term joins {gb.comp.weyl[i].field} and {gb.comp.weyl[j].field} "
                                  "across unbroken charges: a term is not invariant")
    neutral = [i for i, x in enumerate(q) if np.allclose(x, 0)]
    out = []
    if neutral:
        sigma, u = takagi(m[np.ix_(neutral, neutral)])
        for k in range(len(sigma)):
            vec = np.zeros(len(q), dtype=complex)
            vec[neutral] = u[:, k].conj()
            out.append((_fermion_label(gb, vec), vec, None, sigma[k], 0.0, _fparity(gb, vec), _fcolour(gb, vec)))
    keys = {_key(x) for x in q if _positive(x)}
    for key in sorted(keys):
        rows = [i for i, x in enumerate(q) if _key(x) == key]
        cols = [i for i, x in enumerate(q) if _key(-x) == key]
        if len(rows) != len(cols):
            raise GaugeBasisError(f"charge sector {key} has {len(rows)} left-handed states but {len(cols)} partners: "
                                  "a massless chiral fermion")
        w_, s, zh = np.linalg.svd(m[np.ix_(rows, cols)])
        for k in range(len(s)):
            left = np.zeros(len(q), dtype=complex)
            right = np.zeros(len(q), dtype=complex)
            left[rows] = w_[:, k].conj()
            right[cols] = zh.conj().T[:, k]
            out.append((_fermion_label(gb, left), left, right, s[k], key[0], _fparity(gb, left), _fcolour(gb, left)))
    return out


def _fermion_label(gb: GaugeBasis, vec: np.ndarray) -> str:
    weights: dict[str, float] = {}
    for i, a in enumerate(vec):
        weights[gb.comp.weyl[i].field] = weights.get(gb.comp.weyl[i].field, 0.0) + abs(a) ** 2
    return max(weights, key=weights.get)


def _fparity(gb: GaugeBasis, vec: np.ndarray) -> int:
    return gb.comp.weyl[int(np.argmax(np.abs(vec)))].parity


def _fcolour(gb: GaugeBasis, vec: np.ndarray) -> str:
    return gb.comp.weyl[int(np.argmax(np.abs(vec)))].colour


# --- vectors ---------------------------------------------------------------------------------------

def _vector_mass(gb: GaugeBasis, v: np.ndarray, notes: list[str]) -> dict[tuple[str, str], float]:
    """m²_VW: (t^V v)·(t^W v) from the covariant derivative for the Standard Model's gauge bosons (and a new vector
    with a current but no stated seagull), plus the stated masses and seagulls at the vacuum."""
    out: dict[tuple[str, str], float] = {}
    seagulled = {a for (a, b), p in gb.vector_mass.items() for k in p if k} | \
        {b for (a, b), p in gb.vector_mass.items() for k in p if k}
    derived = [n for n in gb.gauge if n not in gb.explicit_vectors or n not in seagulled]
    for a in derived:
        for b in derived:
            out[(a, b)] = float((gb.gauge[a] @ v) @ (gb.gauge[b] @ v))
    for (a, b), poly in gb.vector_mass.items():
        value = float(np.real(sum(c * np.prod([v[k] for k in key]) for key, c in poly.items())))
        out[(a, b)] = out.get((a, b), 0.0) + value
        if a != b:
            out[(b, a)] = out.get((b, a), 0.0) + value
    for n in gb.explicit_vectors & set(gb.gauge):
        if n not in seagulled and np.linalg.norm(gb.gauge[n] @ v) > 0:
            notes.append(f"{n}: its mass from the vacuum uses the seagull its current implies (none is stated)")
    return out


def _broken_kinetic(gb: GaugeBasis) -> dict[tuple[str, str], float]:
    """Below electroweak breaking a mixing with B is a mixing with c_W A − s_W Z."""
    c_w = gbm.M_W / gbm.M_Z
    s_w = math.sqrt(1 - c_w ** 2)
    out: dict[tuple[str, str], float] = {}
    for (a, b), k in gb.kinetic.items():
        if "B" in (a, b):
            x = b if a == "B" else a
            for partner, factor in (("A", c_w), ("Z", -s_w)):
                key = tuple(sorted((x, partner)))
                out[key] = out.get(key, 0.0) + factor * k
        else:
            out[(a, b)] = out.get((a, b), 0.0) + k
    return out


def vector_states(gb: GaugeBasis, v: np.ndarray, notes: list[str]) -> list[tuple[str, dict[str, complex], float,
                                                                               float]]:
    """(name, gauge vector → amplitude, m², Q): W± from W¹, W² (or the given W), and the neutral vectors from
    K⁻¹ᐟ² M² K⁻¹ᐟ² (Cholesky K = L Lᵀ, V = L⁻ᵀ O E)."""
    m2 = _vector_mass(gb, v, notes)
    out = []
    broken = gb.spec.phase.value == "broken"
    if broken:
        out.append(("W", {"W": 1.0}, m2.get(("W", "W"), gbm.M_W ** 2), 1.0))
        neutral = ["A", "Z"] + [n for n in gb.comp.vectors if n not in ("A", "Z", "W")]
        kinetic = _broken_kinetic(gb)
    else:
        mw2 = m2.get(("W1", "W1"), 0.0)
        out.append(("W", {"W1": 1 / math.sqrt(2), "W2": -1j / math.sqrt(2)}, mw2, 1.0))
        neutral = ["W3", "B"] + [n for n in gb.comp.vectors if n not in ("B", "W1", "W2", "W3")]
        kinetic = dict(gb.kinetic)
    n = len(neutral)
    k = np.eye(n)
    mass = np.array([[m2.get((a, b), 0.0) for b in neutral] for a in neutral])
    for (a, b), value in kinetic.items():
        if a in neutral and b in neutral:
            i, j = neutral.index(a), neutral.index(b)
            k[i, j] += value
            k[j, i] += value
    lower = np.linalg.cholesky(k)
    inverse = np.linalg.inv(lower)
    values, o = np.linalg.eigh(inverse @ mass @ inverse.T)
    rounding = 1e-14 * n * max(np.abs(values).max(), 1.0)          # eigh's own error: a massless vector is exact 0
    values = np.where(np.abs(values) < rounding, 0.0, values)
    for f in gb.spec.fields:                                        # below that error a stated mass would read as 0
        if f.spin == 1 and f.mass_gev and f.mass_gev ** 2 < 10 * rounding:   # (the audit's G1-13, G12)
            raise GaugeBasisError(f"{f.name}: a vector mass of {f.mass_gev:g} GeV is below the resolution "
                                  f"({math.sqrt(10 * rounding):.1g} GeV) of the neutral vectors' mass matrix")
    rotation = inverse.T @ o
    rotation = rotation * np.sign(rotation[np.argmax(np.abs(rotation), axis=0), range(n)])[None, :]   # a sign convention
    for idx in range(n):
        amplitudes = {neutral[a]: complex(rotation[a, idx]) for a in range(n) if abs(rotation[a, idx]) > 1e-12}
        out.append((_vector_name(values[idx], amplitudes, [x[0] for x in out]), amplitudes, values[idx], 0.0))
    return out


def _vector_name(m2: float, amplitudes: dict[str, complex], taken: list[str]) -> str:
    """A for the massless photon-like state, Z for the one nearest m_Z with W³ (or Z) in it, else the dominant
    new vector's name."""
    sm_share = sum(abs(amplitudes.get(x, 0)) ** 2 for x in ("W3", "B", "A"))
    if abs(m2) < 1e-6 and "A" not in taken and sm_share > 0.5:       # a massless dark photon is not the photon
        return "A"                                                    # (the audit's G1-8, G12)
    if "Z" not in taken and (abs(amplitudes.get("W3", 0)) > 0.5 or abs(amplitudes.get("Z", 0)) > 0.5):
        return "Z"
    dominant = max(amplitudes, key=lambda x: abs(amplitudes[x]))
    name = dominant if dominant not in ("W3", "B", "A", "Z") else "V"
    while name in taken:
        name += "'"
    return name


# --- the spectrum ----------------------------------------------------------------------------------

def _charge_symbol(q: float) -> str:
    if abs(q) < 1e-9:
        return "0"
    if abs(q - round(q)) < 1e-9:
        return ("+" if q > 0 else "-") * abs(round(q))
    return f"({q:+.3g})"


def _names(raw: list[tuple[str, float, float]]) -> list[str]:
    """Unique state names: field, charge symbol and, where several share them, an index in order of mass."""
    base = [f"{label}{_charge_symbol(q)}" for label, q, _ in raw]
    out = list(base)
    for name in set(base):
        idx = sorted([k for k, b in enumerate(base) if b == name], key=lambda k: raw[k][2])
        if len(idx) > 1:
            for n, k in enumerate(idx, start=1):
                out[k] = f"{name}_{n}"
    return out


def _composition(labels: list[str], vec: np.ndarray) -> dict[str, float]:
    weights: dict[str, float] = {}
    for label, a in zip(labels, vec):
        if abs(a) ** 2 > 1e-6:
            weights[label] = weights.get(label, 0.0) + float(abs(a) ** 2)
    return weights


# The Standard Model's vectors. A vector state keeps its field's name (scalars and fermions take a charge suffix:
# s → s0), so a new vector with one of these names would be merged with the SM boson (a dark vector named "A"
# became the photon, 2026-10-15). G1 refuses it.
SM_VECTOR_NAMES = frozenset({"A", "Z", "W", "g", "B", "W1", "W2", "W3"})   # B, W¹–W³ added by the audit (G1-8, G12)


def _check_names(spec: ModelSpec) -> None:
    for f in spec.fields:
        if f.role.value != "standard_model" and f.spin == 1 and f.name in SM_VECTOR_NAMES:
            raise gbm.GaugeBasisError(f"{f.name}: the name of a Standard Model particle, which the new field would be "
                                      "merged with; give it another name")


def compute(spec: ModelSpec) -> MassBasis:
    """The model's physical spectrum and the rotations to it (module docstring). Raises GaugeBasisError (or
    IndexError_) with the reason when the model cannot be put in the mass basis."""
    _check_names(spec)
    gb = gbm.build(spec)
    v = vacuum(gb)
    shifted, solved, linear = solve_vacuum(gb, v)
    hess = gbm.hessian(shifted, len(v)).real
    notes = list(gb.notes)
    goldstones = goldstone_basis(gb, v, hess, notes)
    charges = field_charges(gb)
    scalars = scalar_states(gb, hess, goldstones, charges)
    fermions = fermion_states(gb, v, charges)
    vectors = vector_states(gb, v, notes)
    coord_labels = [f"{c.field}[m={c.m:g},{c.part}]" for c in gb.comp.coordinates]
    weyl_labels = [f"{w.field}.{w.block}[m={w.m:g}]" for w in gb.comp.weyl]
    states, scalar_out, fermion_out, vector_out = [], [], [], []
    for (label, u, m2, q, parity, colour), name in zip(scalars, _names([(s[0], s[3], s[2]) for s in scalars])):
        if m2 < -TOLERANCE * max(1.0, abs(m2)):
            raise GaugeBasisError(f"the scalar {name} has m² = {m2:.4g} GeV² < 0: the stated vacuum is a saddle")
        name = "h" if label in ("H", "h") and abs(q) < 1e-9 and "h" not in [s.name for s in states] else name
        kind = "real" if abs(q) < 1e-9 and np.allclose(u.imag, 0) else "complex"
        states.append(State(name=name, spin=0, kind=kind, mass_gev=math.sqrt(max(m2, 0.0)), charge=q, colour=colour,
                            parity=parity, composition=_composition(coord_labels, u)))
        scalar_out.append((name, u))
    for (label, left, right, m, q, parity, colour), name in zip(
            fermions, _names([(f[0], f[4], f[3]) for f in fermions])):
        comp = _composition(weyl_labels, left) | (_composition(weyl_labels, right) if right is not None else {})
        states.append(State(name=name, spin=0.5, kind="dirac" if right is not None else "majorana", mass_gev=m,
                            charge=q, colour=colour, parity=parity, composition=comp))
        fermion_out.append((name, left, right))
    fields = {f.name: f for f in gb.spec.fields}
    for name, amplitudes, m2, q in vectors:
        dominant = max(amplitudes, key=lambda x: abs(amplitudes[x]))
        parity = fields[dominant].dark_parity or 1 if dominant in fields else 1
        states.append(State(name=name, spin=1, kind="charged_vector" if q else "vector",
                            mass_gev=math.sqrt(max(m2, 0.0)), charge=q, parity=parity,
                            composition={k: float(abs(a) ** 2) for k, a in amplitudes.items()}))
        vector_out.append((name, amplitudes))
    states.sort(key=lambda s: (s.spin, s.mass_gev))
    spectrum = Spectrum(states=states, solved=solved, linear_terms=linear, notes=notes)
    return MassBasis(gauge=gb, spectrum=spectrum, vacuum=v, scalar_states=scalar_out, fermion_states=fermion_out,
                     vector_states=vector_out, potential=shifted)


def spectrum(spec: ModelSpec) -> Spectrum:
    """The physical spectrum of a typed model (``compute`` without the rotations)."""
    return compute(spec).spectrum
