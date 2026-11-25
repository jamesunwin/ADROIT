"""SHM++ in the recoil rate (halo phase 2; ``expectations.md`` items 13–14, declared before the results): three operators
(O1, the spin-dependent O4 and the velocity-dependent O3), each elastic, endothermic and exothermic, from the detector
table against the same rate built from the independent cubature's η and η⊥ (the nuclear responses shared, the halo side
independent); the density and the component weights applied once. The comparison allows max(1%, 4σ), σ the
reference's own spread over two scramblings: the 1% first declared alone failed in the endothermic tail through the
reference's noise (``validation/item13_reference_noise.md``), and σ was added after that observation."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import pytest

from adroit.core.dm_state import DarkMatterParticle, InteractionModel, OperatorCoefficient
from adroit.halo_models import shm_plus_plus as shmpp
from adroit.physics import rates, targets
from adroit.physics.conventions import C_KM_S, KEV, nuclear_mass_gev, reduced_mass
from adroit.physics.nuclear import NuclearModel
from tests.halo_models import references as ref

P = shmpp.BENCHMARK
ENERGIES = np.geomspace(1.0, 300.0, 60)
GRID = np.linspace(0.0, 800.0, 401)            # v_min of the reference cubature, interpolated linearly


@lru_cache(maxsize=None)
def detector():
    return shmpp.table(P, "detector")


@lru_cache(maxsize=None)
def reference_moments(seed: int) -> tuple[np.ndarray, np.ndarray]:
    return ref.cubature(GRID, P.v_detector(), P.v0_km_s, P.v_esc_km_s, P.beta, P.eta, points=2 ** 18, seed=seed)


def interaction(operator: int) -> InteractionModel:
    return InteractionModel(name=f"O{operator}", layer="nonrelativistic",
                            coefficients=[OperatorCoefficient(operator=operator, proton=1e-3, neutron=1e-3)])


def reference_rate(particle: DarkMatterParticle, operator: int, seed: int) -> np.ndarray:
    """dR/dE_R on xenon with the cubature's η and η⊥ at each energy's v_min (kinematics written again here)."""
    eta_grid, perp_grid = reference_moments(seed)
    total = np.zeros(ENERGIES.size)
    for isotope in targets.target("Xe").isotopes:
        m_t = nuclear_mass_gev(isotope.mass_number)
        mu = reduced_mass(particle.mass_gev, m_t)
        q = np.sqrt(2.0 * m_t * ENERGIES * KEV)
        v_min = np.abs(m_t * ENERGIES * KEV / mu + particle.mass_splitting_kev * KEV) / q * C_KM_S
        eta = np.interp(v_min, GRID, eta_grid, right=0.0) * C_KM_S
        perp = np.interp(v_min, GRID, perp_grid, right=0.0) / C_KM_S
        plain, transverse = rates.response_terms(ENERGIES, particle, interaction(operator), isotope,
                                                 NuclearModel.shell_model)
        total += isotope.mass_fraction * P.rho_gev_cm3 / particle.mass_gev / (2 * math.pi) * \
            (plain * eta + transverse * perp) * rates.RATE_UNIT
    return total


@pytest.mark.parametrize("operator", [1, 3, 4])
@pytest.mark.parametrize("splitting_kev", [0.0, 50.0, -50.0])
def test_each_operator_and_kinematics_against_the_independent_moments(operator, splitting_kev):
    particle = DarkMatterParticle(mass_gev=100.0, mass_splitting_kev=splitting_kev)
    mine = np.array(rates.differential_rate(ENERGIES, particle, interaction(operator), targets.target("Xe"),
                                            detector(), NuclearModel.shell_model).rate)
    a, b = reference_rate(particle, operator, 7), reference_rate(particle, operator, 19)
    reference, sigma = (a + b) / 2.0, np.abs(a - b) / math.sqrt(2.0)
    assert mine.max() > 0.0
    seen = reference > 1e-3 * reference.max()
    assert seen.sum() >= 10
    allowed = np.maximum(1e-2, 4.0 * sigma[seen] / reference[seen])
    assert np.all(np.abs(mine[seen] / reference[seen] - 1.0) <= allowed)


def test_the_density_and_the_weights_enter_once():
    from adroit.constraints import capture
    particle = DarkMatterParticle(mass_gev=100.0)
    once, twice = detector(), detector().model_copy(update={"rho_gev_cm3": 2 * P.rho_gev_cm3})
    a = np.array(rates.differential_rate(ENERGIES, particle, interaction(1), targets.target("Xe"), once).rate)
    b = np.array(rates.differential_rate(ENERGIES, particle, interaction(1), targets.target("Xe"), twice).rate)
    assert np.max(np.abs(b / a - 2.0)) <= 1e-12
    sun = shmpp.table(P, "sun")
    u, flux = capture.halo_flux(particle, sun)
    u2, flux2 = capture.halo_flux(particle, sun.model_copy(update={"rho_gev_cm3": 2 * P.rho_gev_cm3}))
    assert np.array_equal(u, u2) and np.max(np.abs(flux2 / np.where(flux > 0, flux, 1) - 2.0)[flux > 0]) <= 1e-12
    assert flux.sum() == pytest.approx(P.rho_gev_cm3 / particle.mass_gev, rel=1e-6)
