"""The nonrelativistic reduction of a relativistic interaction, by explicit spinors (DM8).

A deterministic check that needs no table and no sign bookkeeping: the matrix
element of an effective Lagrangian (dark matter bilinear) × (nucleon
bilinear) is computed with explicit Dirac spinors, in the conventions of
Anand et al. (arXiv:1308.6288, section 2):
- Bjorken–Drell γ matrices; spinors normalised to ūu = 1;
- q = p′ − p = k − k′, the momentum the dark matter gains;
- v⊥ = ½(p/m_χ + p′/m_χ − k/m_N − k′/m_N);
- the operators O_i of their Eqs. (12)–(13), with S = σ/2.

The amplitude for all sixteen spin combinations is then projected onto the
O_i, evaluated between Pauli spinors, by least squares, at elastic
centre-of-mass kinematics with speeds ~10⁻³. The coefficient of
c ψ̄_χψ_χ ψ̄_Nψ_N is c in front of O_1, and of c (χ̄γ^μγ⁵χ)(N̄γ_μγ⁵N) it is −4c
in front of O_4: both are reproduced (tests/library/test_nr_projection.py).

**Currents.** A current is a function (ψ̄′, ψ, p, p′) → its four
components with upper index (or a scalar), built from the helpers here. The
physical nucleon currents take k′ − k = −q where a form factor multiplies
σ^{μν}(k′ − k)_ν/(2m_N), as in the standard parametrisation.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable

import numpy as np

_I2 = np.eye(2, dtype=complex)
_Z2 = np.zeros((2, 2), dtype=complex)
PAULI = [np.array([[0, 1], [1, 0]], dtype=complex), np.array([[0, -1j], [1j, 0]], dtype=complex),
         np.array([[1, 0], [0, -1]], dtype=complex)]
GAMMA = [np.block([[_I2, _Z2], [_Z2, -_I2]])] + [np.block([[_Z2, s], [-s, _Z2]]) for s in PAULI]
GAMMA5 = np.block([[_Z2, _I2], [_I2, _Z2]])
METRIC = np.diag([1.0, -1.0, -1.0, -1.0])
_XI = [np.array([1, 0], dtype=complex), np.array([0, 1], dtype=complex)]
OPERATORS = (1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)

Current = Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], np.ndarray]


def spinor(p3: np.ndarray, mass: float, xi: np.ndarray) -> np.ndarray:
    """u(p) = √((E+m)/(2m)) (ξ, σ·p ξ/(E+m)), normalised to ūu = 1 (Anand et al., Eq. 5)."""
    energy = np.sqrt(mass * mass + p3 @ p3)
    sigma_p = sum(p3[i] * PAULI[i] for i in range(3))
    return np.sqrt((energy + mass) / (2 * mass)) * np.concatenate([xi, sigma_p @ xi / (energy + mass)])


def four(p3: np.ndarray, mass: float) -> np.ndarray:
    """The four-momentum (E, p) of a particle of the given mass and three-momentum, upper index."""
    return np.concatenate([[np.sqrt(mass * mass + p3 @ p3)], p3])


def sigma(mu: int, nu: int) -> np.ndarray:
    """σ^{μν} = (i/2)[γ^μ, γ^ν]."""
    return 0.5j * (GAMMA[mu] @ GAMMA[nu] - GAMMA[nu] @ GAMMA[mu])


# --- currents: (ψ̄′, ψ, momentum in, momentum out) → components, upper index ----------------

def scalar(bar_out, u_in, k_in, k_out) -> np.ndarray:
    """ψ̄ψ."""
    return np.array(bar_out @ u_in)


def pseudoscalar(bar_out, u_in, k_in, k_out) -> np.ndarray:
    """ψ̄ iγ⁵ ψ."""
    return np.array(bar_out @ (1j * GAMMA5) @ u_in)


def vector(bar_out, u_in, k_in, k_out) -> np.ndarray:
    """ψ̄γ^μψ, upper index."""
    return np.array([bar_out @ GAMMA[mu] @ u_in for mu in range(4)])


def axial(bar_out, u_in, k_in, k_out) -> np.ndarray:
    """ψ̄γ^μγ⁵ψ, upper index."""
    return np.array([bar_out @ GAMMA[mu] @ GAMMA5 @ u_in for mu in range(4)])


def tensor_q(transfer: np.ndarray, scale: float) -> Current:
    """ψ̄ iσ^{μν} t_ν ψ / scale for a fixed four-vector t (upper index)."""
    t_low = METRIC @ transfer
    return lambda bar_out, u_in, k_in, k_out: np.array(
        [sum(bar_out @ (1j * sigma(mu, nu)) @ u_in * t_low[nu] for nu in range(4)) for mu in range(4)]) / scale


def nucleon_electromagnetic(charge: float, kappa: float, m_n: float) -> Current:
    """N̄[F₁γ^μ + F₂ iσ^{μν}(k′−k)_ν/(2m_N)]N, F₁ = charge, F₂ = κ (the standard parametrisation)."""
    def current(bar_out, u_in, k_in, k_out):
        pauli = tensor_q(k_out - k_in, 2 * m_n)(bar_out, u_in, k_in, k_out)
        return charge * vector(bar_out, u_in, k_in, k_out) + kappa * pauli
    return current


# --- the nonrelativistic side ------------------------------------------------------------------

def kinematics(m_chi: float, m_n: float, speed: float = 1e-3, seed: int = 1,
               angle: float = np.pi / 2) -> dict:
    """Elastic centre-of-mass kinematics: p = −k = P, p′ = −k′ = P′, |P′| = |P|.

    P has the given relative speed (|P| = μ v); P′ is P turned by ``angle`` about a random
    axis, so every seed has the same |q| = 2|P| sin(angle/2).
    """
    rng = np.random.default_rng(seed)
    mu = m_chi * m_n / (m_chi + m_n)
    big_p = rng.normal(size=3)
    big_p *= speed * mu / np.linalg.norm(big_p)
    axis = np.cross(big_p, rng.normal(size=3))
    axis /= np.linalg.norm(axis)
    big_pp = big_p * np.cos(angle) + np.cross(axis, big_p) * np.sin(angle)
    p, pp, k, kp = big_p, big_pp, -big_p, -big_pp
    return {"p": p, "pp": pp, "k": k, "kp": kp, "q": pp - p,
            "vperp": 0.5 * (p / m_chi + pp / m_chi - k / m_n - kp / m_n)}


LEVI_CIVITA = np.zeros((3, 3, 3))
for _i, _j, _k in itertools.permutations(range(3)):
    LEVI_CIVITA[_i, _j, _k] = np.linalg.det(np.eye(3)[[_i, _j, _k]])


def operators(q: np.ndarray, vperp: np.ndarray, m_n: float) -> dict[int, np.ndarray]:
    """O_i on (χ spin) ⊗ (nucleon spin), Anand et al. Eqs. (12)–(13)."""
    half = [s / 2 for s in PAULI]
    s_chi = [np.kron(s, _I2) for s in half]
    s_n = [np.kron(_I2, s) for s in half]
    one = np.kron(_I2, _I2)
    qm = q / m_n

    def dot(vec, ops):
        return sum(vec[i] * ops[i] for i in range(3))

    def triple(ops_a, ops_b, vec):       # ops_a · (ops_b × vec)
        return sum(LEVI_CIVITA[i, j, k] * ops_a[i] @ ops_b[j] * vec[k]
                   for i, j, k in itertools.product(range(3), repeat=3) if LEVI_CIVITA[i, j, k])
    s_n_cross_v = [sum(LEVI_CIVITA[i, j, k] * s_n[j] * vperp[k] for j in range(3) for k in range(3))
                   for i in range(3)]
    return {
        1: one,
        3: 1j * dot(np.cross(qm, vperp), s_n),
        4: sum(s_chi[i] @ s_n[i] for i in range(3)),
        5: 1j * dot(np.cross(qm, vperp), s_chi),
        6: dot(qm, s_chi) @ dot(qm, s_n),
        7: dot(vperp, s_n),
        8: dot(vperp, s_chi),
        9: 1j * triple(s_chi, s_n, qm),
        10: 1j * dot(qm, s_n),
        11: 1j * dot(qm, s_chi),
        12: triple(s_chi, s_n, vperp),
        13: 1j * dot(vperp, s_chi) @ dot(qm, s_n),
        14: 1j * dot(qm, s_chi) @ dot(vperp, s_n),
        15: -dot(qm, s_chi) @ dot(qm, s_n_cross_v),
    }


def amplitude(chi_current: Current, nucleon_current: Current, m_chi: float, m_n: float,
              kin: dict) -> np.ndarray:
    """⟨χ′N′| (χ̄Γχ)(N̄ΓN) |χN⟩ for the sixteen spin states, rows (χ′, N′), columns (χ, N)."""
    p4, pp4, k4, kp4 = (four(kin[a], m) for a, m in (("p", m_chi), ("pp", m_chi), ("k", m_n), ("kp", m_n)))
    out = np.zeros((4, 4), dtype=complex)
    for a, b, c, d in itertools.product(range(2), repeat=4):
        chi = chi_current(spinor(kin["pp"], m_chi, _XI[a]).conj() @ GAMMA[0],
                          spinor(kin["p"], m_chi, _XI[c]), p4, pp4)
        nuc = nucleon_current(spinor(kin["kp"], m_n, _XI[b]).conj() @ GAMMA[0],
                              spinor(kin["k"], m_n, _XI[d]), k4, kp4)
        out[2 * a + b, 2 * c + d] = chi @ METRIC @ nuc if chi.ndim else chi * nuc
    return out


def project(chi_current: Current, nucleon_current: Current, m_chi: float, m_n: float,
            which: tuple[int, ...] = OPERATORS, speed: float = 1e-3, seeds: tuple[int, ...] = (1, 2, 3)) -> tuple[dict[int, float], float]:
    """({i: c_i}, relative residual): the coefficients that reproduce the amplitude.

    Several kinematic points at the same speed (hence the same |q|) are fitted together;
    a coefficient that depends on q is obtained at that |q|.
    """
    rows, target = [], []
    for seed in seeds:
        kin = kinematics(m_chi, m_n, speed, seed)
        ops = operators(kin["q"], kin["vperp"], m_n)
        rows.append(np.array([ops[i].ravel() for i in which]).T)
        target.append(amplitude(chi_current, nucleon_current, m_chi, m_n, kin).ravel())
    design, values = np.vstack(rows), np.concatenate(target)
    coefficients, *_ = np.linalg.lstsq(design, values, rcond=None)
    rest = np.linalg.norm(values - design @ coefficients) / max(np.linalg.norm(values), 1e-300)
    return {i: float(c.real) for i, c in zip(which, coefficients)}, float(rest)
