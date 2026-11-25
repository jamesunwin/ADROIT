"""SHM++ (halo phase 2): the generator against the paper, the authors' tables and independent references
(``references.py``). The tolerances were declared before the results (``scratch_evidence/halo_phase2_2026-11-10/
expectations.md``, items 1–12; items 1, 2 and 7 after the prototype had shown them, as that file says)."""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from adroit.core.dm_state import HaloModel
from adroit.halo_models import shm_plus_plus as shmpp
from adroit.physics import halo as physics_halo
from tests.halo_models import references as ref

DATA = Path(__file__).parent / "data" / "shmpp_authors"
P = shmpp.BENCHMARK
V0, VESC, BETA, ETA = P.v0_km_s, P.v_esc_km_s, P.beta, P.eta


@lru_cache(maxsize=None)
def tables(eta: float = ETA) -> tuple[HaloModel, HaloModel]:
    return shmpp.tables(P.model_copy(update={"eta": eta}))


def closed_form(frame: str) -> HaloModel:
    """The SHM at SHM++'s v₀, v_esc and boosts, in closed form (``physics.halo``)."""
    return HaloModel(rho_gev_cm3=P.rho_gev_cm3, v0_km_s=V0, v_esc_km_s=VESC, v_lsr_km_s=(0.0, V0, 0.0),
                     v_peculiar_km_s=P.v_peculiar_km_s,
                     v_earth_km_s=P.v_earth_km_s if frame == "detector" else (0.0, 0.0, 0.0))


def test_the_normalisations_are_the_papers():
    sigma_r, sigma_t = shmpp.dispersions(P)
    assert abs((2 * math.pi) ** 1.5 * (V0 / math.sqrt(2)) ** 3 * shmpp.n_round(P) / V0 ** 3 - 5.47699) < 1e-5
    assert abs((2 * math.pi) ** 1.5 * sigma_r * sigma_t ** 2 * shmpp.n_sausage(P) / V0 ** 3 - 2.09443) < 1e-5
    assert shmpp.n_sausage(P) == pytest.approx(ref.normalisation(V0, VESC, BETA, "sausage"), rel=1e-12)


@pytest.mark.parametrize("frame", ["detector", "sun"])
def test_the_round_component_through_the_angular_integration_is_the_shm_closed_form(frame):
    speeds = np.array(tables()[0 if frame == "detector" else 1].speeds_km_s)
    numeric = shmpp.speed_distribution(speeds, P.boost(frame), P, "round")
    exact = physics_halo.speed_distribution(speeds, closed_form(frame))
    assert np.max(np.abs(numeric - exact)) <= 1e-9 * exact.max()


def test_the_isotropic_limit_of_the_sausage_is_the_round_component():
    speeds = np.linspace(1.0, 770.0, 200)
    boost = P.v_detector()
    round_ = shmpp.speed_distribution(speeds, boost, P, "round")
    isotropic = shmpp.speed_distribution(speeds, boost, P.model_copy(update={"beta": 0.0}), "sausage")
    nearly = shmpp.speed_distribution(speeds, boost, P.model_copy(update={"beta": 1e-6}), "sausage")
    assert np.max(np.abs(isotropic - round_)) <= 1e-12 * round_.max()
    assert np.max(np.abs(nearly - round_)) <= 1e-5 * round_.max()


@pytest.mark.parametrize("frame", ["detector", "sun"])
def test_with_no_sausage_the_tables_are_the_shm_at_the_same_parameters(frame):
    """η = 0 against the SHM at the same v₀, v_esc and boosts: the generated table equals the closed form tabulated on
    the same grid (1e-9: the generator), and the exact closed form within 2e-5 (the table's linear interpolation at
    1,601 speeds). The 1e-6 first declared for the second failed (1.2e-5 for η, 1.8e-5 for η⊥, falling as the grid
    spacing squared; ``scratch_evidence/halo_phase2_2026-11-10/validation/item4_failed_tolerance.md``): 2e-5 was set
    after that observation."""
    table = tables(0.0)[0 if frame == "detector" else 1]
    v_min = np.linspace(0.0, table.speeds_km_s[-1] - 50.0, 60)
    eta, perp = physics_halo.velocity_integrals(v_min, table)
    same_grid = physics_halo.tabulate(closed_form(frame), len(table.speeds_km_s))
    eta_grid, perp_grid = physics_halo.velocity_integrals(v_min, same_grid)
    assert np.max(np.abs(eta / eta_grid - 1)) <= 1e-9 and np.max(np.abs(perp / perp_grid - 1)) <= 1e-9
    eta_shm, perp_shm = physics_halo.velocity_integrals(v_min, closed_form(frame))
    assert np.max(np.abs(eta / eta_shm - 1)) <= 2e-5 and np.max(np.abs(perp / perp_shm - 1)) <= 2e-5


def test_the_weights_are_applied_once():
    mixed, none, only = tables()[0], tables(0.0)[0], tables(1.0)[0]
    combined = 0.8 * np.array(none.speed_density) + 0.2 * np.array(only.speed_density)
    assert np.max(np.abs(combined - mixed.speed_density)) <= 1e-12 * max(mixed.speed_density)
    assert only.speed_density != none.speed_density


@pytest.mark.parametrize("frame", ["detector", "sun"])
def test_each_component_and_the_mixture_are_normalised_finite_and_nonnegative(frame):
    boost = P.boost(frame)
    table = tables()[0 if frame == "detector" else 1]
    speeds = np.array(table.speeds_km_s)
    for component in ("round", "sausage"):
        f = shmpp.speed_distribution(speeds, boost, P, component)
        assert abs(np.trapezoid(f, speeds) - 1.0) <= 1e-6
        assert np.all(np.isfinite(f)) and np.all(f >= 0.0)
    f = np.array(table.speed_density)
    assert abs(np.trapezoid(f, speeds) - 1.0) <= 1e-6 and f[0] == 0.0 and f[-1] == 0.0 and f[-2] > 0.0
    above = shmpp.mixture(np.array([speeds[-1], speeds[-1] + 1.0, 2000.0]), boost, P)
    assert np.all(above == 0.0)


@pytest.mark.parametrize("frame", ["detector", "sun"])
def test_the_tables_moments_match_an_independent_cubature_in_the_galactic_frame(frame):
    table = tables()[0 if frame == "detector" else 1]
    v_min = np.array([0.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0])
    eta, perp = physics_halo.velocity_integrals(v_min, table)
    runs = [ref.cubature(v_min, P.boost(frame), V0, VESC, BETA, ETA, seed=s) for s in (11, 29)]
    for k, mine in ((0, eta), (1, perp)):
        a, b = runs[0][k], runs[1][k]
        reference, sigma = (a + b) / 2.0, np.abs(a - b) / math.sqrt(2.0)
        relative = np.abs(mine / reference - 1.0)
        allowed = np.maximum(np.where(v_min <= 600.0, 5e-3, 2e-2), 4.0 * sigma / reference)
        assert np.all(relative <= allowed), (k, relative, allowed)


def test_g_and_h_match_the_authors_monte_carlo_tables():
    g_ref, h_ref = np.loadtxt(DATA / "gvmin_SHMpp.dat"), np.loadtxt(DATA / "hvmin_SHMpp.dat")
    v_min = g_ref[:, 0]
    assert np.array_equal(v_min, h_ref[:, 0])
    eta, perp = physics_halo.velocity_integrals(v_min, tables()[0])
    h = perp + v_min ** 2 * eta
    for low, high, tolerance in ((0.0, 500.0, 5e-3), (500.0, 700.0, 3e-2)):
        sel = (v_min > low if low else v_min >= low) & (v_min <= high)
        assert np.max(np.abs(eta[sel] / g_ref[sel, 1] - 1)) <= tolerance
        assert np.max(np.abs(h[sel] / h_ref[sel, 1] - 1)) <= tolerance


@pytest.mark.parametrize("frame", ["detector", "sun"])
def test_the_speed_distribution_matches_an_angular_lattice_not_aligned_with_the_boost(frame):
    boost = P.boost(frame)
    for speeds, tolerance in (([20.0, 50.0, 100.0, 200.0], 1e-5), ([300.0, 400.0, 500.0, 600.0], 3e-3)):
        mine = shmpp.mixture(np.array(speeds), boost, P)
        lattice = ref.lattice_speed(np.array(speeds), boost, V0, VESC, BETA, ETA)
        assert np.max(np.abs(mine / lattice - 1.0)) <= tolerance, (speeds, mine / lattice - 1.0)


def test_doubling_the_angular_nodes_changes_nothing_that_matters():
    speeds = np.linspace(5.0, 770.0, 40)
    for frame in ("detector", "sun"):
        coarse = shmpp.mixture(speeds, P.boost(frame), P)
        fine = shmpp.mixture(speeds, P.boost(frame), P, shmpp.Numerics(polar=128, azimuth=128))
        assert np.max(np.abs(fine - coarse)) <= 1e-9 * coarse.max()


@pytest.mark.slow
@pytest.mark.parametrize("frame", ["detector", "sun"])
def test_doubling_the_speeds_and_the_angles_together_converges(frame):
    coarse = tables()[0 if frame == "detector" else 1]
    fine = shmpp.table(P, frame, shmpp.Numerics(speeds=3201, polar=128, azimuth=128))
    v_min = np.linspace(0.0, coarse.speeds_km_s[-1] - 50.0, 80)
    for a, b in zip(physics_halo.velocity_integrals(v_min, coarse), physics_halo.velocity_integrals(v_min, fine)):
        assert np.max(np.abs(a / b - 1.0)) <= 1e-4
    assert abs(np.trapezoid(coarse.speed_density, coarse.speeds_km_s)
               - np.trapezoid(fine.speed_density, fine.speeds_km_s)) <= 1e-6


@pytest.mark.parametrize("change", [
    {"v0_km_s": float("nan")}, {"v_esc_km_s": float("inf")}, {"v0_km_s": 0.0}, {"v0_km_s": -233.0},
    {"beta": -0.1}, {"beta": 1.0}, {"eta": -0.01}, {"eta": 1.2}, {"rho_gev_cm3": 0.0},
    {"v_esc_km_s": 240.0}, {"v_earth_km_s": (float("nan"), 0.0, 0.0)}, {"v_peculiar_km_s": (0.0, float("inf"), 0.0)}])
def test_unphysical_parameters_are_refused(change):
    with pytest.raises(ValidationError):
        shmpp.Parameters(**{**P.model_dump(), **change})


@pytest.mark.parametrize("frame", ["detector", "sun"])
def test_the_support_ends_at_the_fastest_particle(frame):
    table = tables()[0 if frame == "detector" else 1]
    top = table.speeds_km_s[-1]
    assert top == pytest.approx(VESC + float(np.linalg.norm(P.boost(frame))), rel=1e-12)
    eta, perp = physics_halo.velocity_integrals(np.array([0.0, top - 1.0, top, top + 10.0]), table)
    assert eta[2] == eta[3] == perp[2] == perp[3] == 0.0
    assert 0.0 < eta[1] < 1e-6 * eta[0] and 0.0 < perp[1]


def test_the_frames_and_the_instant_are_the_benchmarks():
    """The boosts, the instant, and two frames told apart. The tables differ by 0.59% of the peak at most, not the
    "more than 1%" first declared (the Earth's velocity is nearly perpendicular to the Sun's at this instant;
    ``validation/item12_failed_expectation.md``): the thresholds below were set after that observation."""
    from adroit.constraints import capture
    from adroit.parameter_space import halo_limits
    assert np.allclose(P.v_detector(), (39.674, 243.187, 16.359), atol=2e-3)
    assert np.allclose(P.v_sun(), (11.1, 245.24, 7.25), atol=1e-12)
    assert float(np.linalg.norm(P.v_detector())) == pytest.approx(246.94, abs=0.01)
    year = np.linspace(shmpp.INSTANT - 182.625, shmpp.INSTANT + 182.625, 4000, endpoint=False)
    mean = np.mean([np.linalg.norm(P.v_sun() + np.array(shmpp.earth_velocity(n))) for n in year])
    assert mean == pytest.approx(247.19, abs=0.05)
    detector, sun = tables()
    from adroit.halo_models.frames import frame_of
    assert frame_of(detector) == "detector" and frame_of(sun) == "sun"
    assert np.max(np.abs(np.interp(sun.speeds_km_s, detector.speeds_km_s, detector.speed_density)
                         - np.array(sun.speed_density))) > 1e-3 * max(sun.speed_density)
    tail = [physics_halo.velocity_integrals(np.array([600.0]), t)[0][0] for t in (detector, sun)]
    assert tail[0] / tail[1] - 1.0 > 0.01
    with pytest.raises(ValueError, match="detector's frame is not the distribution the Sun sees"):
        capture.sun_frame(detector)
    assert capture.sun_frame(sun) is sun
    with pytest.raises(ValueError, match="detector's frame"):
        halo_limits.tabulated(sun)


def test_a_table_is_checked_against_its_generator():
    detector, sun = tables()
    numerics = shmpp.Numerics()
    assert shmpp.agrees(detector, P, "detector", numerics) == "" and shmpp.agrees(sun, P, "sun", numerics) == ""
    assert "frame" in shmpp.agrees(sun, P, "detector", numerics)
    nudged = detector.model_copy(update={"speed_density": [*detector.speed_density[:500],
                                                           detector.speed_density[500] * 1.001,
                                                           *detector.speed_density[501:]]})
    assert "differ from the generator's" in shmpp.agrees(nudged, P, "detector", numerics)
    assert "version" in shmpp.agrees(detector, P, "detector", numerics.model_copy(update={"generator": 99}))
    assert "density or boosts" in shmpp.agrees(detector, P.model_copy(update={"rho_gev_cm3": 0.4}), "detector",
                                               numerics)
    assert shmpp.sha256(detector) != shmpp.sha256(nudged) and shmpp.sha256(detector) != shmpp.sha256(sun)
