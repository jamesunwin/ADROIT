"""SHM++ in capture by the Sun (halo phase 2; ``expectations.md`` items 16–17, declared before the results): the Sun-frame
table against an independent Monte Carlo of the Galactic distribution boosted by the Sun's velocity, through the same
capture kernel; its slow tail against an independent angular rule; and the capture-annihilation evolution out of
equilibrium, where the annihilation rate goes as the square of the capture rate, not linearly with the density."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import pytest
from scipy.stats import norm, qmc

from adroit.constraints import capture
from adroit.core.dm_state import DarkMatterParticle, HaloModel, InteractionModel, OperatorCoefficient
from adroit.halo_models import shm_plus_plus as shmpp
from adroit.physics.conventions import C_KM_S
from tests.halo_models import references as ref

pytestmark = pytest.mark.skipif(capture.fetch.locate(capture.SOLAR_MODEL) is None,
                                reason="the B16 solar model is not in the tools folder (adroit setup --fetch)")
P = shmpp.BENCHMARK


@lru_cache(maxsize=None)
def sun_table() -> HaloModel:
    return shmpp.table(P, "sun")


def interaction(operator: int, value: float) -> InteractionModel:
    return InteractionModel(name=f"O{operator}", layer="nonrelativistic",
                            coefficients=[OperatorCoefficient(operator=operator, proton=value,
                                                              neutron=value if operator == 1 else 0.0)])


def monte_carlo_flux(particle: DarkMatterParticle, points: int = 2 ** 20) -> tuple[np.ndarray, np.ndarray]:
    """(u in c, n_χ f(u) du) in ``capture.halo_flux``'s bins, from Galactic samples boosted by v_⊙ (independent)."""
    top = sun_table().speeds_km_s[-1]
    edges = np.linspace(0.0, top, 401)
    counts = np.zeros(400)
    for component, weight, seed in (("round", 1.0 - P.eta, 3), ("sausage", P.eta, 4)):
        z = norm.ppf(qmc.Sobol(3, scramble=True, seed=seed).random(points))
        v = z * ref.sigmas(P.v0_km_s, P.beta, component)
        inside = np.sum(v * v, axis=1) < P.v_esc_km_s ** 2
        speed = np.linalg.norm(v[inside] - P.v_sun(), axis=1)
        counts += weight * np.histogram(speed, bins=edges)[0] / inside.sum()
    centres = 0.5 * (edges[1:] + edges[:-1])
    return centres / C_KM_S, P.rho_gev_cm3 / particle.mass_gev * counts


@pytest.mark.parametrize("mass, operator, value", [(100.0, 4, 1e-3), (10.0, 1, 1e-4)])
def test_the_sun_table_captures_as_an_independent_monte_carlo(mass, operator, value):
    particle = DarkMatterParticle(mass_gev=mass)
    sun = capture.solar_model()
    model = capture.NuclearModel.shell_model
    speeds, flux = capture.halo_flux(particle, sun_table())
    mc_speeds, mc_flux = monte_carlo_flux(particle)
    assert np.allclose(speeds, mc_speeds, rtol=1e-12)
    mine = sum(capture.isotope_capture(i, particle, interaction(operator, value), sun, speeds, flux, model)
               for i in capture.isotopes())
    independent = sum(capture.isotope_capture(i, particle, interaction(operator, value), sun, mc_speeds, mc_flux,
                                              model) for i in capture.isotopes())
    assert mine > 0.0 and abs(mine / independent - 1.0) <= 1e-2
    assert capture.capture_rate(particle, interaction(operator, value), sun_table()) == pytest.approx(mine, rel=1e-12)


def test_the_slow_tail_matches_an_independent_angular_rule():
    table = sun_table()
    nodes, weights = np.polynomial.legendre.leggauss(32)
    for top in (50.0, 100.0, 150.0):
        grid = np.linspace(0.0, top, 4001)
        mine = np.trapezoid(np.interp(grid, table.speeds_km_s, table.speed_density), grid)
        u = top * (nodes + 1.0) / 2.0
        lattice = ref.lattice_speed(u, P.v_sun(), P.v0_km_s, P.v_esc_km_s, P.beta, P.eta)
        independent = float(np.sum(weights * lattice) * top / 2.0)
        assert abs(mine / independent - 1.0) <= 1e-4, (top, mine / independent - 1.0)


def test_out_of_equilibrium_annihilation_goes_as_the_capture_rate_squared():
    particle = DarkMatterParticle(mass_gev=100.0)
    sd = interaction(4, 1e-3)
    shm_rate = capture.capture_rate(particle, sd, HaloModel())
    plus_rate = capture.capture_rate(particle, sd, sun_table())
    ratio = plus_rate / shm_rate
    assert abs(ratio - 1.0) > 0.05                        # the two halos differ enough to tell the laws apart

    def annihilation(rate: float, sigma_v: float) -> float:
        return rate / 2.0 * capture.equilibrium_fraction(rate, sigma_v, particle.mass_gev,
                                                         self_conjugate=particle.self_conjugate)
    faint = 1e-40                                         # tanh²(t⊙/τ) ≪ 1
    assert capture.equilibrium_fraction(plus_rate, faint, 100.0, self_conjugate=True) < 1e-3
    assert annihilation(plus_rate, faint) / annihilation(shm_rate, faint) == pytest.approx(ratio ** 2, rel=1e-2)
    strong = 3e-26
    assert capture.equilibrium_fraction(plus_rate, strong, 100.0, self_conjugate=True) > 0.999
    assert annihilation(plus_rate, strong) / annihilation(shm_rate, strong) == pytest.approx(ratio, rel=1e-2)
    assert math.isfinite(ratio)


def test_capture_never_takes_a_detector_table():
    with pytest.raises(ValueError, match="Sun-frame table"):
        capture.capture_rate(DarkMatterParticle(mass_gev=100.0), interaction(4, 1e-3), shmpp.table(P, "detector"))
