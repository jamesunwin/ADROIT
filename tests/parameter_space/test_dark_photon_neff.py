"""A freeze-in dark photon's N_eff (Ibe et al., arXiv:1912.12152 Fig. 4(a); the owner, 2026-10-13)."""

import pytest

from adroit.parameter_space import searches as ps
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.vector import DarkPhoton


def _bbn(m_mev: float, epsilon: float, m_chi: float = 1.0, unverified: bool = True):
    return ps.bbn(DarkPhoton(), Point(m_chi=m_chi, m_med=m_mev * 1e-3, g_chi=0.1, g_q=epsilon), unverified)


@pytest.mark.parametrize("m_mev,epsilon,excluded", [
    (4.0, 1e-9, True),            # inside Planck's region
    (9.0, 1e-9, True),            # its bulge past 8.5 MeV near ε ~ 10⁻⁹
    (4.0, 2e-10, False),          # below it (the blue region is Stage IV's forecast, not an exclusion)
    (12.0, 1e-9, False),          # to its right
    (4.0, 1e-12, False),          # below the figure: its outermost contour closes above 2 × 10⁻¹¹
])
def test_planck_excludes_the_red_region_of_figure_4a(m_mev, epsilon, excluded):
    assert _bbn(m_mev, epsilon).excluded is excluded


def test_the_region_is_applied_only_where_its_assumptions_hold(awaiting):
    assert _bbn(0.9, 1e-9).excluded is None                      # below the e⁺e⁻ threshold: three photons
    assert _bbn(4.0, 1e-9, m_chi=1e-4).excluded is None          # the A′ can decay to dark matter
    assert _bbn(4.0, 1e-7).excluded is True                       # thermalised: Sabti et al.'s 9.8 MeV bound
    assert _bbn(15.0, 1e-7).excluded is False
    awaiting(ps.NEFF_FREEZE_IN)
    assert "awaits" in (_bbn(4.0, 1e-9, unverified=False).why or "")


def test_the_digitised_region_matches_the_papers_statements():
    from adroit.constraints import searches as s
    data = s._bundled(ps.NEFF_FREEZE_IN)
    assert len(data["mass_mev"]) == len(data["epsilon"]) == 118
    assert 8.4 < max(m for m, e in zip(data["mass_mev"], data["epsilon"]) if e > 1e-7) < 8.6   # "m < 8.5 MeV excluded"
    assert min(data["epsilon"]) == pytest.approx(4.05e-10, rel=0.01)
