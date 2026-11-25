"""The audit loop's cycle 5 (the auditor, the independent audit of 2026-11-17 (cycle5)): its severe finding, AL5-01, at the place
The auditor's controls reached it (the AL5 repair record of 2026-11-17). Offline."""
from __future__ import annotations

import numpy as np
import pytest

from adroit.constraints import relic

M_DM = 100.0
START = 2 * M_DM
X = np.array([20.0, 200.0])


# --- AL5-01: a narrow pole near a UFO pair's threshold ---------------------------------------------------------------

def _sigma(s, mass, width, floor=True):
    """σ ∝ 1/β × a Breit–Wigner, zero within 10⁻¹² of the threshold where ``floor`` (the tree amplitudes' own)."""
    beta = np.sqrt(np.clip(1 - START ** 2 / s, 0, None))
    with np.errstate(divide="ignore", over="ignore"):
        out = np.where(beta > 0, 1 / np.maximum(beta, 1e-300) / ((s - mass * mass) ** 2 + (mass * width) ** 2), 0.0)
    return np.where(np.sqrt(s) > START * (1 + 1e-12), out, 0.0) if floor else out


def _production_over_exact(mass: float, width: float) -> np.ndarray:
    """⟨σv⟩ at x = 20 and 200 as the UFO route has it (σ read from the pair's table, ``ufo.table_roots``, integrated on
    the relic's grid, ``relic.energy_grid``) over the exact σ integrated on a far finer grid."""
    from adroit.parameter_space.portals import ufo
    roots = ufo.table_roots(START, [(mass, width)])
    logs = np.log(np.maximum(_sigma(roots ** 2, mass, width), 1e-300))

    def read(u):
        root = START * (1 + u)
        tabled = np.exp(np.interp(root, roots, logs))
        return np.where((root > roots[0]) & (tabled > 1e-299), tabled, 0.0)
    u_r, w = mass / START - 1, width / (2 * START)
    fine = np.union1d(relic.energy_grid(M_DM, mass, width)[1:], np.geomspace(1e-16, 3.0, 60000))
    fine = np.union1d(fine, u_r + w * np.concatenate([-np.geomspace(1e-4, 1e4, 6000), [0.0], np.geomspace(1e-4, 1e4, 6000)]))
    fine = fine[fine > 0]
    grid = relic.energy_grid(M_DM, mass, width)
    exact = relic.thermal_average(fine, _sigma((START * (1 + fine)) ** 2, mass, width, floor=False), X)
    return relic.thermal_average(grid, read(grid), X) / exact


def _centre(ratio: float, where: str) -> float:
    """The pole's mass: ``where`` a number of widths from the threshold ("+8w"), or a distance in u ("u=-1e-4")."""
    return START * (1 + float(where[2:])) if where.startswith("u=") else START + float(where[:-1]) * ratio * START


NEAR = ["-64w", "-8w", "-1w", "+0w", "+1w", "+8w", "+64w", "+300w", "u=-1e-4", "u=-1e-6", "u=-1e-8", "u=+1e-7"]
REFUSED = [(3e-11, "+0w"), (1e-11, "+0w"), (1e-12, "-8w"), (1e-13, "+64w"), (1e-12, "u=+1e-11")]


@pytest.mark.parametrize(("ratio", "where"), [(r, w) for r in (3e-3, 1e-6, 1e-9, 1e-10, 3e-11) for w in NEAR
                                              if (r, w) not in REFUSED])
def test_a_narrow_pole_near_the_threshold_is_resolved_by_the_table_and_the_grid(ratio, where) -> None:
    """The auditor's reconstruction widened: Γ/M from 3 × 10⁻³ to 3 × 10⁻¹¹, the pole at, below or above the threshold: within
    2% (the old nodes gave from 0.007 to 4 × 10⁴ times; the auditor's case, Γ/M = 10⁻⁹ at the threshold, 0.62)."""
    assert _production_over_exact(_centre(ratio, where), ratio * START) == pytest.approx([1.0, 1.0], abs=0.02)


@pytest.mark.parametrize(("ratio", "where"), REFUSED)
def test_a_pole_closer_to_the_threshold_than_the_amplitudes_resolve_is_not_resolved(ratio, where) -> None:
    """Within 2 × 10⁻¹¹ (in √s/threshold − 1) the amplitudes' floor at 10⁻¹² loses a material part of the pole: its
    scale is below ``SCALE_RESOLVED`` (``domain`` refuses Ωh² there: the test of the real model below)."""
    from adroit.parameter_space.portals import ufo
    assert ufo.threshold_scale(START, _centre(ratio, where), ratio * START) < ufo.SCALE_RESOLVED


def test_a_pole_far_from_the_threshold_adds_no_ladder() -> None:
    """Between the base ladder's first nodes (u = 10⁻⁹ and 10⁻⁵) a pole far from the threshold adds nothing, nor does a
    wide one at it (its threshold scale above 10⁻³: the base ladder resolves it)."""
    from adroit.parameter_space.portals import ufo
    plain = ufo.table_roots(START, [])
    assert np.array_equal(ufo.table_roots(START, [(150.0, 1e-3)]), plain)              # far below: not reached
    for mass, width in ((260.0, 1e-3), (START, 1.0), (2 * START, 30.0)):
        u = ufo.table_roots(START, [(mass, width)]) / START - 1
        assert not ((u > 2e-9) & (u < 0.99e-5)).any(), (mass, width)


def test_the_relic_grid_resolves_a_narrow_pole_just_below_the_threshold() -> None:
    """Its own nodes all below the threshold, the pole 10⁻⁹ below it was integrated across the grid's first cell (from
    0 to 10⁻⁹): 0.90 times its thermal average; now from a hundredth of its distance."""
    mass, width = START * (1 - 1e-9), 1e-12 * START
    grid = relic.energy_grid(M_DM, mass, width)
    fine = np.union1d(grid[1:], np.geomspace(1e-16, 3.0, 60000))
    exact = relic.thermal_average(fine, _sigma((START * (1 + fine)) ** 2, mass, width, floor=False), X)
    found = relic.thermal_average(grid, _sigma((START * (1 + grid)) ** 2, mass, width, floor=False), X)
    assert found / exact == pytest.approx([1.0, 1.0], abs=0.01)
    assert ((grid > 0) & (grid < 1e-9)).sum() >= 2 * relic.THRESHOLD_PER_DECADE


def test_the_relic_grid_is_unchanged_for_a_pole_away_from_the_threshold() -> None:
    for mass, width in ((START * 1.001, 1e-3), (START * 0.999, 1e-6), (START * (1 + 1e-6), 1e-4)):
        grid = relic.energy_grid(M_DM, mass, width)
        u_r, w = mass / START - 1, max(width / (4 * M_DM), relic.POLE_FLOOR)
        own = u_r + w * np.concatenate([-np.geomspace(60, 1e-3, 150), [0.0], np.geomspace(1e-3, 60, 150)])
        below = grid[(grid > 0) & (grid < 1e-9)]
        assert np.isin(below, own).all()                    # below the base nodes only the pole's own


@pytest.mark.needs("ufo_models")
def test_the_2hdma_at_its_threshold_pole_is_resolved_or_refused() -> None:
    """The auditor's points (m_χ = 100, m_a = 200 GeV): at g_q = 0.001 (Γ/M = 4.9 × 10⁻¹¹) and the auditor's thermal root there
    (g_χ = 0.15544), Ωh² within 1% of a reference with the table and the grid made far denser in memory (it had been
    6.8 times that); at g_q = 10⁻⁴ (Γ/M = 4.9 × 10⁻¹³) refused with its reason, not a number. The table's accuracy is
    compared with the late-annihilation test off: at this pole the yield is still falling at x = 10⁴, so the published
    Ωh² is refused (AL6-01, ``test_al6_fixes``)."""
    import math
    from unittest.mock import patch

    from adroit.parameter_space import library
    from adroit.parameter_space.portals import ufo
    entry = library.entry("two_hdm_a")
    cls = entry.model_class
    roots, grid = ufo.table_roots, relic.energy_grid

    def dense_roots(start, poles):
        return np.union1d(roots(start, poles), start * (1 + np.geomspace(1.25e-12, 1e-3, 2000)))

    def dense_grid(m, resonance_gev=None, width_gev=0.0):
        return np.union1d(grid(m, resonance_gev, width_gev), np.geomspace(1e-14, 1e-6, 1000))
    p = entry.point.model_copy(update={"m_chi": 100.0, "m_med": 200.0, "g_q": 0.001, "g_chi": 0.15544174657146054})
    ufo._SIGMA.clear()
    with patch.object(relic, "LATE_TOLERANCE", math.inf), patch.object(relic, "REMAINDER_TOLERANCE", math.inf):
        found = cls.omega_h2(p)
        ufo._SIGMA.clear()
        with patch.object(ufo, "table_roots", dense_roots), patch.object(relic, "energy_grid", dense_grid):
            reference = cls.omega_h2(p)
    ufo._SIGMA.clear()
    assert found == pytest.approx(reference, rel=0.01) and found < 0.03          # the old table: 0.1200
    with pytest.raises(relic.RelicUnresolved, match="annihilation has not stopped"):
        cls.omega_h2(p)
    narrower = p.model_copy(update={"g_q": 1e-4})
    assert "closer than the tree amplitudes resolve" in cls.domain(narrower)
    assert cls.omega_h2(narrower) is None
