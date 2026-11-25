"""The LHC recast through SModelS (constraints.lhc; parameter_space.searches.lhc_search)."""

import pytest

from adroit.constraints import lhc
from adroit.parameter_space import searches as ps
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.multiplet import ElectroweakMultiplet
from adroit.parameter_space.portals.tchannel import TChannel

needs_smodels = pytest.mark.skipif(not lhc.available(), reason="SModelS, its database or the tables are not fetched")


def test_a_wino_chargino_lives_about_six_centimetres():
    ctau = lhc.HBAR_C_GEV_M / lhc.chargino_width(0.164, 2.0)
    assert ctau == pytest.approx(0.06, rel=0.1)
    assert lhc.chargino_width(0.1, 2.0) < lhc.chargino_width(0.164, 2.0)          # below m_π: leptons only


def test_an_slha_file_holds_quantum_numbers_masses_decays_and_cross_sections():
    text = lhc.slha([dict(pdg=2000002, label="phi", charge3=2, spin_states=1, colour=3, distinct=True, mass=900.0),
                     dict(pdg=52, label="chi", charge3=0, spin_states=2, colour=1, distinct=False, mass=100.0)],
                    {2000002: (1.0, [(1.0, [52, 2])])}, [((2000002, -2000002), 0.0156)])
    assert "BLOCK QNUMBERS 2000002" in text and "# 3 times electric charge" in text
    assert "XSECTION  1.30E+04  2212 2212  2  2000002 -2000002" in text and "1.560000E-02" in text
    assert "DECAY   52   0.000000E+00" in text


@needs_smodels
def test_cross_sections_come_from_the_working_groups_tables():
    assert lhc.cross_section_pb("coloured", 1000.0) == pytest.approx(7.395e-3, rel=0.01)       # 2024 NNLL-fast
    assert lhc.cross_section_pb("coloured", 5000.0) is None


def test_spectra_are_written_for_partners_and_multiplets_only():
    from adroit.parameter_space.portals.vector import DarkPhoton
    assert ps.lhc_spectrum(DarkPhoton(), Point(m_chi=10.0, m_med=30.0)) is None
    if lhc.available() and not lhc.unavailable(*lhc.TABLES):            # SModelS and the production tables
        assert ps.lhc_spectrum(TChannel(partner="muR"), Point(m_chi=100.0, m_med=400.0, g_chi=1.0)) is not None
        text, sigma = ps.lhc_spectrum(ElectroweakMultiplet(multiplet="wino"), Point(m_chi=500.0, m_med=1.0, g_q=0.0))
        assert "1000024" in text and sigma > 0


@pytest.mark.slow
@needs_smodels
def test_smodels_reproduces_the_install_checks(awaiting):
    """r ≥ 1 excludes. A coloured partner is undecided at any r, its production being QCD's alone, not established
    as a lower bound (decision D33, the external audit's R20); r stays in ``value``, out of the combination's
    ``ratio``."""
    cases = [(TChannel(partner="uR"), Point(m_chi=100.0, m_med=900.0, g_chi=1.0), None),
             (TChannel(partner="uR"), Point(m_chi=100.0, m_med=1500.0, g_chi=1.0), None),
             (ElectroweakMultiplet(multiplet="wino"), Point(m_chi=500.0, m_med=1.0, g_q=0.0), True)]
    for cls, p, excluded in cases:
        outcome = ps.lhc_search(cls, p, True)
        assert outcome.excluded is excluded and outcome.value is not None
        assert (outcome.ratio is not None) is (excluded is not None)
    awaiting("smodels-3.2.1")                       # the default path while its record awaits a signature
    assert "awaits" in ps.lhc_search(*cases[0][:2], False).why
