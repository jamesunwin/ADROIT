"""The nuclear side of the rate: the response functions W_k^{ττ'}(q) of each isotope.

A nucleus responds to dark matter through eight response functions (Anand et
al., arXiv:1308.6288), each a matrix in the isospin labels τ, τ' = 0, 1:

| response   | what it measures                                   |
|------------|----------------------------------------------------|
| M          | the nucleon density: the spin-independent response |
| Σ'', Σ'    | the nucleon spin, along and across q                |
| Φ''        | the spin-orbit coupling                            |
| Φ̃'         | a tensor spin-orbit response                       |
| Δ          | the orbital angular momentum                       |
| Φ''M, ΔΣ'  | the interferences of Φ'' with M and of Δ with Σ'   |

**Normalisation.** τ = 0 multiplies c^p + c^n and τ = 1 multiplies c^p − c^n,
twice the isospin coefficients of :mod:`conventions`; this is the
normalisation of the published tables.

**Four nuclear models** (``NuclearModel``):
- ``shell_model``: the published shell-model responses (Anand et al.; Catena &
  Schwabe, arXiv:1501.03729) for the 30 isotopes they cover. Any other isotope
  falls back to the approximation below, and ``describe`` says so.
- ``helm``: the approximation for every isotope. M is the Helm form factor
  (Lewin & Smith, Astropart. Phys. 6 (1996) 87), which experiments use for
  spin-independent limits. Σ'' and Σ' follow from the spin expectation values
  ⟨S_p⟩, ⟨S_n⟩ with a Gaussian form factor (arXiv:1505.01926, App. C), where
  those values are known. The other five responses are absent.
- ``klos``: for spin-dependent limits only. The shell model, except that the
  spin responses Σ'' and Σ' of the eight isotopes Klos et al. cover are
  replaced by their structure factors with two-body currents
  (arXiv:1304.7684v4, Appendix D), which several experiments use. Klos et
  al. give S_A(q) = Σ a_τ a_τ' S_ττ'(q), the sum of the longitudinal (Σ'')
  and transverse (Σ') parts; the O₄ rate needs only that sum, and the split
  W_Σ'' : W_Σ' = 1 : 2 of long wavelengths is used to distribute it. Other
  operators that see Σ'' and Σ' separately (O₆, O₇, O₉, O₁₀) therefore get
  only an approximation under this model. The fits are used up to
  u = q²b²/2 = 5, the range of the paper's figures, and are zero beyond
  (recoils of hundreds of keV at least).
- ``haxton_2022``: all eight responses computed from the revised one-body
  density matrices of Haxton & McElvain, which LZ uses since 2023
  (arXiv:2312.02030), with the multipole matrix elements of their Mu2e
  scripts (``haxton``). Where no revised matrix exists the shell model is
  used, and ``describe`` says so. For xenon the spin responses are about
  twice the published ones at low momentum transfer.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from importlib import resources

import numpy as np
import yaml

from adroit.core.dm_state import Isotope, NuclearModel, Target
from adroit.physics import haxton
from adroit.physics.conventions import HBARC_GEV_FM
from adroit.physics.targets import spin_expectations

__all__ = ["NuclearModel", "RESPONSES", "describe", "klos_structure_factors", "responses"]

RESPONSES = ("M", "Sigma''", "Sigma'", "Phi''", "PhiTilde'", "Delta", "Phi''M", "DeltaSigma'")
SHELL_MODEL_SOURCES = "arXiv:1308.6288, arXiv:1501.03729"
KLOS_SOURCE = "arXiv:1304.7684v4"
KLOS_MAX_U = 5.0


@lru_cache(maxsize=1)
def shell_model_table() -> dict[str, dict]:
    """The shell-model responses, keyed by isotope name ('Xe131'), from the data file."""
    text = resources.files("adroit.physics").joinpath(
        "data/shell_model_responses.json").read_text()
    isotopes = json.loads(text)["isotopes"]
    return {("H1" if name == "H" else name): entry for name, entry in isotopes.items()}


def has_shell_model(isotope: Isotope) -> bool:
    """Whether the shell-model table covers the isotope."""
    return isotope.name in shell_model_table()


def oscillator_length_fm(mass_number: int) -> float:
    """The harmonic-oscillator length b of the shell-model fits, in fm."""
    a = float(mass_number)
    return math.sqrt(41.467 / (45.0 * a ** (-1.0 / 3.0) - 25.0 * a ** (-2.0 / 3.0)))


def helm_form_factor(q_gev: np.ndarray, mass_number: int) -> np.ndarray:
    """The Helm form factor F(q), with the parameters of Lewin & Smith (F(0) = 1)."""
    c = 1.23 * mass_number ** (1.0 / 3.0) - 0.60
    a, s = 0.52, 0.9
    r_n = math.sqrt(c * c + 7.0 / 3.0 * math.pi ** 2 * a * a - 5.0 * s * s)
    x = np.asarray(q_gev, dtype=float) * r_n / HBARC_GEV_FM
    safe = np.where(x < 1e-4, 1.0, x)
    bessel = 3.0 * (np.sin(safe) - safe * np.cos(safe)) / safe ** 3
    bessel = np.where(x < 1e-4, 1.0 - x * x / 10.0, bessel)
    return bessel * np.exp(-0.5 * (np.asarray(q_gev) * s / HBARC_GEV_FM) ** 2)


def _shell_model(isotope: Isotope, q: np.ndarray) -> np.ndarray:
    """W^{ττ'}_k(q) from the shell-model polynomials, shape (8, 2, 2, n)."""
    y = (q * oscillator_length_fm(isotope.mass_number) / (2.0 * HBARC_GEV_FM)) ** 2
    damping = np.exp(-2.0 * y)
    out = np.zeros((len(RESPONSES), 2, 2, q.size))
    for k, name in enumerate(RESPONSES):
        grid = shell_model_table()[isotope.name]["responses"].get(name)
        if grid is None:
            continue
        for t in (0, 1):
            for u in (0, 1):
                if grid[t][u]:
                    out[k, t, u] = np.polynomial.polynomial.polyval(y, grid[t][u]) * damping
    return out


def _spin_radius_fm(mass_number: int) -> float:
    """The radius of the Gaussian spin form factor (arXiv:1505.01926, App. C), in fm."""
    a3 = mass_number ** (1.0 / 3.0)
    return 0.92 * a3 + 2.68 - 0.78 * math.sqrt((a3 - 3.8) ** 2 + 0.2)


def _approximate(isotope: Isotope, q: np.ndarray) -> np.ndarray:
    """Helm M, and Σ'', Σ' from ⟨S_p⟩, ⟨S_n⟩ where known; shape (8, 2, 2, n).

    With s = ((⟨S_p⟩ + ⟨S_n⟩)/2, (⟨S_p⟩ − ⟨S_n⟩)/2),

        W_M^{ττ'}   = (2J+1)/(16π) N^τ N^τ' F²(q),   N = (A, 2Z − A),
        W_Σ''^{ττ'} = (2J+1)(J+1)/(3πJ) s^τ s^τ' G(q),   W_Σ' = 2 W_Σ'',

    with G(q) = exp(−q² r²/4ħ²). These reproduce the shell-model tables at
    q = 0 (tests/physics/test_nuclear.py). WimPyDD's version of the Σ'' formula
    carries 4/(3π) in place of 1/(3π), four times this normalisation
    (docs/dm2_forward_model.md).
    """
    a, z, j = isotope.mass_number, isotope.atomic_number, isotope.spin
    out = np.zeros((len(RESPONSES), 2, 2, q.size))
    charges = np.array([a, 2 * z - a], dtype=float)
    form = helm_form_factor(q, a) ** 2
    out[0] = (2 * j + 1) / (16 * math.pi) * np.einsum("t,u,n->tun", charges, charges, form)
    spins = spin_expectations(isotope)
    if j > 0 and spins is not None:
        s = np.array([spins[0] + spins[1], spins[0] - spins[1]]) / 2.0
        gauss = np.exp(-0.25 * (q * _spin_radius_fm(a) / HBARC_GEV_FM) ** 2)
        out[1] = (2 * j + 1) * (j + 1) / (3 * math.pi * j) * np.einsum("t,u,n->tun", s, s, gauss)
        out[2] = 2.0 * out[1]
    return out


@lru_cache(maxsize=1)
def klos_table() -> dict[str, dict]:
    """Klos et al.'s structure-factor fits, keyed by isotope name ('Ge73')."""
    text = resources.files("adroit.physics").joinpath(
        "data/klos2013_structure_factors.yaml").read_text()
    return yaml.safe_load(text)["isotopes"]


def has_klos(isotope: Isotope) -> bool:
    """Whether Klos et al. give structure factors for the isotope."""
    return isotope.name in klos_table()


def klos_structure_factors(isotope: Isotope, q_gev: np.ndarray,
                           band: str = "central") -> np.ndarray:
    """Klos et al.'s S_ττ'(q) in the normalisation of W_k, shape (2, 2, len(q)).

    With the couplings C^τ of this module, Σ C^τ C^τ' S^{ττ'} is their
    S_A(q) = a₀² S₀₀ + a₀a₁ S₀₁ + a₁² S₁₁, so the diagonal entries are S₀₀
    and S₁₁ and the off-diagonal ones S₀₁/2.

    Args:
        isotope: one of the eight isotopes of the paper (``has_klos``).
        q_gev: momentum transfers.
        band: "central" (the middle of the two-body-current band) or one of
            its edges, "isovector_low" or "isovector_high" (the smaller or
            larger isovector coupling a₁(1 + δa₁)): S₁₁ and |S₀₁| move together.
    """
    entry = klos_table()[isotope.name]
    fits = entry["coefficients"]
    u = 0.5 * (np.atleast_1d(np.asarray(q_gev, dtype=float)) * entry["b_fm"] / HBARC_GEV_FM) ** 2
    small, large = sorted(("S01_min", "S01_max"), key=lambda name: abs(fits[name][0]))
    pairs = {"isovector_low": [("S11_min", small)], "isovector_high": [("S11_max", large)],
             "central": [("S11_min", small), ("S11_max", large)]}[band]

    def fit(name: str) -> np.ndarray:
        return np.polynomial.polynomial.polyval(u, fits[name]) * np.exp(-u) * (u <= KLOS_MAX_U)

    s11 = sum(fit(a) for a, _ in pairs) / len(pairs)
    s01 = sum(fit(b) for _, b in pairs) / len(pairs)
    return np.array([[fit("S00"), s01 / 2.0], [s01 / 2.0, s11]])


def _klos(isotope: Isotope, q: np.ndarray) -> np.ndarray:
    """The shell model (or the approximation), with Klos et al.'s Σ'' and Σ'."""
    out = _shell_model(isotope, q) if has_shell_model(isotope) else _approximate(isotope, q)
    if has_klos(isotope):
        total = klos_structure_factors(isotope, q)
        out[1], out[2] = total / 3.0, 2.0 * total / 3.0
    return out


def responses(isotope: Isotope, q_gev: np.ndarray, model: NuclearModel) -> np.ndarray:
    """The eight responses W_k^{ττ'}(q) of an isotope, shape (8, 2, 2, len(q))."""
    q = np.atleast_1d(np.asarray(q_gev, dtype=float))
    if model is NuclearModel.klos:
        return _klos(isotope, q)
    if model is NuclearModel.haxton_2022 and haxton.density_matrix_file(isotope) is not None:
        return haxton.responses(isotope, q, oscillator_length_fm(isotope.mass_number))
    if model is NuclearModel.haxton_2022:
        return responses(isotope, q, NuclearModel.shell_model)
    if model is NuclearModel.shell_model and has_shell_model(isotope):
        return _shell_model(isotope, q)
    return _approximate(isotope, q)


def describe(target: Target, model: NuclearModel) -> str:
    """The nuclear input of a rate on ``target``, in words, for the spectrum's record."""
    revised = [i for i in target.isotopes
               if model is NuclearModel.haxton_2022 and haxton.density_matrix_file(i) is not None]
    shell = model in (NuclearModel.shell_model, NuclearModel.klos, NuclearModel.haxton_2022)
    exact = [i for i in target.isotopes if shell and has_shell_model(i) and i not in revised]
    rest = [i for i in target.isotopes if i not in exact and i not in revised]
    parts = []
    if revised:
        parts.append("revised density matrices of Haxton & McElvain (github.com/Berkeley-"
                     f"Electroweak-Physics/Elastic) for {', '.join(i.name for i in revised)}")
    klos = [i.name for i in target.isotopes if model is NuclearModel.klos and has_klos(i)]
    if klos:
        parts.append(f"spin structure factors of Klos et al. ({KLOS_SOURCE}, middle of the "
                     f"two-body band) for {', '.join(klos)}")
    if exact:
        parts.append(f"shell model ({SHELL_MODEL_SOURCES}) for "
                     + ", ".join(i.name for i in exact))
    if rest:
        share = 100.0 * sum(i.mass_fraction for i in rest)
        with_spin = [i.name for i in rest if i.spin > 0 and spin_expectations(i) is not None]
        without = [i.name for i in rest if i.spin > 0 and spin_expectations(i) is None]
        text = (f"Helm form factor for {', '.join(i.name for i in rest)} "
                f"({share:.2f}% of the target by mass)")
        if with_spin:
            text += f"; approximate spin responses for {', '.join(with_spin)}"
        if without:
            text += f"; spin responses omitted for {', '.join(without)}"
        parts.append(text)
    return "; ".join(parts)
