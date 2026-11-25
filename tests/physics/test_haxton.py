"""Nuclear responses from the revised Haxton–McElvain density matrices (DM5)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from adroit.physics import haxton, nuclear, targets
from adroit.physics.conventions import HBARC_GEV_FM
from adroit.physics.nuclear import NuclearModel


def _available() -> bool:
    try:
        haxton._paths()
    except haxton.ResponsesUnavailable:
        return False
    return True


needs_tools = pytest.mark.skipif(not _available(),
                                 reason="density matrices, Mu2e scripts or their environment missing")


def _isotope(name: str):
    return targets.single_isotope(name).isotopes[0]


@needs_tools
def test_the_charge_form_factor_counts_nucleons() -> None:
    # F_M(J=0; τ) at y = 0 is N^τ √(2J+1)/√(4π), N = (A, Z − N), with τ₃ = +1 on protons (to the
    # eight figures of the density matrices)
    f = haxton.form_factors(_isotope("F19"), "bw")
    assert f["M|0|0"][0] == pytest.approx(19 * math.sqrt(2) / math.sqrt(4 * math.pi), rel=1e-6)
    assert f["M|0|1"][0] == pytest.approx(-1 * math.sqrt(2) / math.sqrt(4 * math.pi), rel=1e-6)


@needs_tools
@pytest.mark.parametrize("name", ["F19", "Na23"])
def test_the_published_tables_come_back_from_their_own_density_matrices(name: str) -> None:
    # The USD ("bw") density matrices are those behind the published responses: all eight
    # responses, all isospin combinations, interference signs included, must agree.
    iso = _isotope(name)
    b = nuclear.oscillator_length_fm(iso.mass_number)
    idx = [0, 10, 25, 50]
    q = 2.0 * HBARC_GEV_FM * np.sqrt(haxton.Y_GRID[idx]) / b
    new = haxton.responses_on_grid(iso, "bw")[..., idx]
    old = nuclear.responses(iso, q, NuclearModel.shell_model)
    scale = np.abs(old).max(axis=-1, keepdims=True) + 1e-12
    assert np.max(np.abs(new - old) / scale) < 1e-4


@needs_tools
def test_the_revised_xenon_spin_responses_are_about_twice_the_published() -> None:
    xe129 = _isotope("Xe129")
    q = np.array([1e-4])
    new = nuclear.responses(xe129, q, NuclearModel.haxton_2022)
    old = nuclear.responses(xe129, q, NuclearModel.shell_model)
    assert new[0, 0, 0, 0] == pytest.approx(old[0, 0, 0, 0], rel=1e-3)      # the charge: unchanged
    assert 1.8 < new[1, 0, 0, 0] / old[1, 0, 0, 0] < 2.4                     # Σ'': about ×2
    # isotopes without a revised matrix keep the shell model (or its fallback)
    xe124 = _isotope("Xe124")
    assert np.array_equal(nuclear.responses(xe124, q, NuclearModel.haxton_2022),
                          nuclear.responses(xe124, q, NuclearModel.shell_model))
    assert "Haxton & McElvain" in nuclear.describe(targets.target("Xe"), NuclearModel.haxton_2022)
