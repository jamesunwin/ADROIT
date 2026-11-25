"""Kinetic mixing of a dark U(1) with hypercharge: the couplings of the photon, the Z and the dark photon.

L ⊃ −¼ B_μνB^μν − ¼ X_μνX^μν − (ε/2c_W) B_μν X^μν + ½ m_X² X_μX^μ + (electroweak symmetry
breaking), with the dark matter charged under X with coupling g_D. At low energy the
dark photon couples to the electromagnetic current as ε e Q (the convention of the dark
photon literature, e.g. arXiv:2005.01515), with e = e(0) = √(4πα(0)), DarkCast's (its
ge = 0.302822): so ε is the ε of every published limit, and a sub-GeV dark sector's couplings
take the Thomson-limit charge its processes see (decision D29, G12). The mixing is therefore
η = (ε/c_W)·e(0)/e(m_Z) against this module's B, whose coupling is at α(m_Z) (the Z's own
couplings keep α(m_Z)). Rather than expanding in ε, the three neutral
bosons (B, W³, X) are diagonalised exactly at tree level:
1. the kinetic matrix K = L Lᵀ (Cholesky) is made canonical by V = L⁻ᵀ V′;
2. the mass matrix in that basis, L⁻¹ M² L⁻ᵀ = O D Oᵀ, is diagonalised;
3. each mass eigenstate couples to Σ_k R_ki J_k with R = L⁻ᵀ O, J = (g′J_Y, gJ₃, g_D J_D).

So the couplings hold for any m_X, including near the Z pole where the Z and the
dark photon mix strongly, and the photon stays massless and couples to eQ alone.
Couplings are returned as (a, b) in −V_μ f̄γ^μ(a + bγ⁵)f, as in ``exchange``.
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

from adroit.constraints.spin1 import FERMIONS

ALPHA_MZ = 1.0 / 127.95
ALPHA_0 = 1.0 / 137.035999084           # the Thomson limit
SIN2_W = 0.2312
M_Z = 91.1876
GAMMA_Z = 2.4952
E = math.sqrt(4.0 * math.pi * ALPHA_MZ)
E_THOMSON = math.sqrt(4.0 * math.pi * ALPHA_0)   # e(0): the dark photon's ε e Q (module docstring)
SIN_W, COS_W = math.sqrt(SIN2_W), math.sqrt(1.0 - SIN2_W)
G, G_PRIME = E / SIN_W, E / COS_W
V_EFF = 2.0 * M_Z / math.sqrt(G ** 2 + G_PRIME ** 2)      # fixes m_Z at ε = 0

# (T3 of the left-handed field, Y_L, Y_R) with Q = T3 + Y; neutrinos have no right-handed field
QUANTUM_NUMBERS = {"up": (0.5, 1 / 6, 2 / 3), "down": (-0.5, 1 / 6, -1 / 3), "lepton": (-0.5, -0.5, -1.0),
                   "neutrino": (0.5, -0.5, None)}
KIND = {"u": "up", "c": "up", "t": "up", "d": "down", "s": "down", "b": "down", "e": "lepton", "mu": "lepton",
        "tau": "lepton", "nu_e": "neutrino", "nu_mu": "neutrino", "nu_tau": "neutrino"}


@lru_cache(maxsize=4096)
def eigenstates(m_x: float, epsilon: float) -> tuple[np.ndarray, np.ndarray]:
    """(masses of γ, Z, A′ in that order; R with rows B, W³, X and columns the same eigenstates), for DarkCast's ε
    (module docstring)."""
    eta = epsilon * E_THOMSON / E / COS_W
    kinetic = np.array([[1.0, 0.0, eta], [0.0, 1.0, 0.0], [eta, 0.0, 1.0]])
    mass2 = V_EFF ** 2 / 4.0 * np.array([[G_PRIME ** 2, -G * G_PRIME, 0.0], [-G * G_PRIME, G ** 2, 0.0],
                                         [0.0, 0.0, 0.0]])
    mass2[2, 2] += m_x ** 2
    chol = np.linalg.cholesky(kinetic)
    inv_t = np.linalg.inv(chol).T
    values, o = np.linalg.eigh(inv_t.T @ mass2 @ inv_t)
    r = inv_t @ o
    order = np.argsort(values)                      # photon first
    values, r = values[order], r[:, order]
    if abs(r[2, 1]) > abs(r[2, 2]):                 # the dark photon is the state made mostly of X
        values, r = values[[0, 2, 1]], r[:, [0, 2, 1]]
    return np.sqrt(np.clip(values, 0.0, None)), r


def fermion_couplings(name: str, column: np.ndarray) -> tuple[float, float]:
    """(a, b) of a Standard Model fermion to the eigenstate whose column of R is given."""
    t3, y_l, y_r = QUANTUM_NUMBERS[KIND[name]]
    c_left = G_PRIME * column[0] * y_l + G * column[1] * t3
    c_right = G_PRIME * column[0] * y_r if y_r is not None else 0.0
    return 0.5 * (c_left + c_right), 0.5 * (c_right - c_left)


def couplings(m_x: float, epsilon: float, g_dark: float) -> dict[str, dict]:
    """For the Z and the dark photon: their masses, the dark current's coupling and every fermion's (a, b)."""
    # 12 significant figures, for cache hits; 12 decimals erased a small ε (release audit minor)
    masses, r = eigenstates(float(f"{m_x:.12g}"), float(f"{epsilon:.12g}"))
    out = {}
    for label, i in (("Z", 1), ("A'", 2)):
        out[label] = {"mass": float(masses[i]), "dark": g_dark * float(r[2, i]),
                      "fermions": {f.name: fermion_couplings(f.name, r[:, i]) for f in FERMIONS}}
    return out


def nucleon_vector(fermions: dict[str, tuple[float, float]]) -> tuple[float, float]:
    """The vector couplings to the proton (2u + d) and the neutron (u + 2d)."""
    a_u, a_d = fermions["u"][0], fermions["d"][0]
    return 2.0 * a_u + a_d, a_u + 2.0 * a_d
