"""Nuclear response functions."""

from __future__ import annotations

import math

import numpy as np
import pytest

from adroit.physics import nuclear, targets
from adroit.physics.nuclear import NuclearModel


def _isotope(name: str):
    return targets.single_isotope(name).isotopes[0]


def test_the_shell_model_covers_the_first_targets() -> None:
    names = ["Xe128", "Xe129", "Xe130", "Xe131", "Xe132", "Xe134", "Xe136", "Ge70", "Ge72",
             "Ge73", "Ge74", "Ge76", "Na23", "I127", "F19", "Ar40", "Si28", "O16", "Ca40", "C12"]
    assert all(nuclear.has_shell_model(_isotope(n)) for n in names)
    assert not nuclear.has_shell_model(_isotope("W183"))


@pytest.mark.parametrize("name", ["Xe131", "Xe132", "Ge73", "I127", "Na23", "F19", "Ar40"])
def test_the_charge_response_at_zero_momentum_counts_nucleons(name: str) -> None:
    # W_M^{ττ'}(0) = (2J+1)/(16π) N^τ N^τ', N = (A, 2Z − A): the normalisation the rate assumes.
    iso = _isotope(name)
    w = nuclear.responses(iso, np.array([0.0]), NuclearModel.shell_model)[0, :, :, 0]
    charges = np.array([iso.mass_number, 2 * iso.atomic_number - iso.mass_number])
    expected = (2 * iso.spin + 1) / (16 * math.pi) * np.outer(charges, charges)
    assert w == pytest.approx(expected, rel=2e-3)


def test_the_spin_approximation_matches_the_shell_model_at_zero_momentum() -> None:
    # 19F with the USD spin values <S_p> = 0.4751, <S_n> = -0.0087 (Divari et al., Phys. Rev.
    # C 61 (2000) 054612). This fixes the 1/(3π) normalisation of the approximation.
    shell = nuclear.responses(_isotope("F19"), np.array([0.0]), NuclearModel.shell_model)
    j, sp, sn = 0.5, 0.4751, -0.0087
    s = np.array([sp + sn, sp - sn]) / 2
    approx = (2 * j + 1) * (j + 1) / (3 * math.pi * j) * np.outer(s, s)
    assert shell[1, :, :, 0] == pytest.approx(approx, rel=3e-3)       # Σ''
    assert shell[2, :, :, 0] == pytest.approx(2 * approx, rel=3e-3)   # Σ' = 2 Σ'' at q = 0


def test_the_helm_form_factor() -> None:
    assert nuclear.helm_form_factor(np.array([0.0]), 131)[0] == pytest.approx(1.0)
    # its first zero is at q r_n = 4.4934, the first root of tan x = x
    c = 1.23 * 131 ** (1 / 3) - 0.60
    r_n = math.sqrt(c * c + 7 / 3 * math.pi ** 2 * 0.52 ** 2 - 5 * 0.81)
    q_zero = 4.4934095 * 0.1973269804 / r_n
    assert abs(nuclear.helm_form_factor(np.array([q_zero]), 131)[0]) < 1e-6


def test_an_uncovered_isotope_falls_back_to_the_approximation() -> None:
    q = np.array([0.0, 0.1])
    o17 = nuclear.responses(_isotope("O17"), q, NuclearModel.shell_model)
    assert np.all(o17[0, 0, 0] > 0) and np.all(o17[1, 0, 0] > 0)      # M and Σ''
    assert np.all(o17[3:] == 0.0)                                     # no Φ'', Φ̃', Δ, ...
    w183 = nuclear.responses(_isotope("W183"), q, NuclearModel.shell_model)
    assert np.all(w183[0, 0, 0] > 0) and np.all(w183[0, 0, 1] < 0)    # M; 2Z − A < 0 for tungsten
    assert np.all(w183[1:] == 0.0)          # no spin response: left out by decision (isotopes.yaml)
    w184 = nuclear.responses(_isotope("W184"), q, NuclearModel.shell_model)
    assert np.all(w184[1:] == 0.0)                                    # spin 0: M only


def test_the_helm_model_replaces_the_shell_model_everywhere() -> None:
    q = np.array([0.05])
    helm = nuclear.responses(_isotope("Xe131"), q, NuclearModel.helm)
    assert np.all(helm[3:] == 0.0)
    assert helm[0, 0, 0, 0] == pytest.approx(
        4 / (16 * math.pi) * 131 ** 2 * nuclear.helm_form_factor(q, 131)[0] ** 2)


def test_the_description_names_every_fallback() -> None:
    text = nuclear.describe(targets.target("Xe"), NuclearModel.shell_model)
    assert "shell model" in text and "Xe124, Xe126" in text and "0.18%" in text
    cawo4 = nuclear.describe(targets.target("CaWO4"), NuclearModel.shell_model)
    assert "approximate spin responses for O17" in cawo4
    assert "spin responses omitted for Ca43, W183" in cawo4


# --- Klos et al. structure factors (arXiv:1304.7684v4, Appendix D) --------------------

KLOS_ISOTOPES = ["Xe129", "Xe131", "Ge73", "I127", "F19", "Na23", "Si29"]


@pytest.mark.parametrize("name", KLOS_ISOTOPES)
def test_the_klos_isospin_fits_agree_with_their_proton_and_neutron_fits(name: str) -> None:
    # The paper fits S00, S01, S11 and S_p, S_n separately; S_p = S00 + S01 + S11 and
    # S_n = S00 − S01 + S11 at each edge of the two-body band check the transcription, to
    # 1% of the larger of S_p(0), S_n(0) (the smaller one is a near-cancellation).
    iso = _isotope(name)
    entry = nuclear.klos_table()[name]
    q = np.array([1e-6, 0.03, 0.08, 0.15])
    u = 0.5 * (q * entry["b_fm"] / 0.1973269804) ** 2

    def fit(key: str) -> np.ndarray:
        return np.polynomial.polynomial.polyval(u, entry["coefficients"][key]) * np.exp(-u)

    for band in ("isovector_low", "isovector_high"):
        s = nuclear.klos_structure_factors(iso, q, band)
        proton, neutron = s.sum(axis=(0, 1)), s[0, 0] - 2 * s[0, 1] + s[1, 1]
        scale = max(proton[0], neutron[0])
        assert min(np.max(abs(proton - fit(k))) for k in ("Sp_min", "Sp_max")) < 0.01 * scale
        assert min(np.max(abs(neutron - fit(k))) for k in ("Sn_min", "Sn_max")) < 0.01 * scale


def test_the_klos_band_brackets_its_centre() -> None:
    ge73, q = _isotope("Ge73"), np.array([0.0, 0.04])
    bands = [nuclear.klos_structure_factors(ge73, q, b) for b in
             ("isovector_low", "central", "isovector_high")]
    proton = [b.sum(axis=(0, 1)) for b in bands]
    assert proton[1] == pytest.approx((proton[0] + proton[2]) / 2)
    # the paper's S_p(0) range for 73Ge: 0.0138 to 0.0367, from two-body currents
    assert sorted([proton[0][0], proton[2][0]]) == pytest.approx([0.0138433, 0.0366954], rel=3e-3)


def test_the_klos_model_replaces_only_the_spin_responses() -> None:
    ge73, q = _isotope("Ge73"), np.array([0.0, 0.05])
    klos = nuclear.responses(ge73, q, NuclearModel.klos)
    shell = nuclear.responses(ge73, q, NuclearModel.shell_model)
    assert np.array_equal(klos[0], shell[0]) and np.array_equal(klos[3:], shell[3:])
    total = nuclear.klos_structure_factors(ge73, q)
    assert klos[1] + klos[2] == pytest.approx(total) and klos[2] == pytest.approx(2 * klos[1])
    # the neutron-only O4 response: Σ C^τ C^τ' (W_Σ'' + W_Σ') with C = (1, −1) is S_n(q)
    neutron = np.einsum("t,u,tun->n", [1, -1], [1, -1], klos[1] + klos[2])
    assert neutron[0] == pytest.approx((0.543270 + 0.657509) / 2, rel=1e-3)
    # beyond u = 5 (the paper's plotted range) the fits are not used
    far = 2.0 * 0.1973269804 * math.sqrt(2 * 5.5) / 2.1058
    assert np.all(nuclear.klos_structure_factors(ge73, np.array([far])) == 0.0)
    # isotopes the paper does not cover keep the shell model
    xe132 = _isotope("Xe132")
    assert np.array_equal(nuclear.responses(xe132, q, NuclearModel.klos),
                          nuclear.responses(xe132, q, NuclearModel.shell_model))
    assert "Klos et al." in nuclear.describe(targets.target("Ge"), NuclearModel.klos)
