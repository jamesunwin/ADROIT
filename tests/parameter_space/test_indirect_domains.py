"""Cascades and mixed spectra cannot inherit pure-channel exclusion curves."""
from types import SimpleNamespace

import pytest

from adroit.constraints import database
from adroit.constraints.indirect import FERMI_CHANNELS, pure_ratio
from adroit.parameter_space import searches
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.base import fermi_ratio
from adroit.parameter_space.portals.ufo import channel_name
from adroit.parameter_space.portals.vector import DarkPhoton


@pytest.mark.needs("pdg_r_ratio")
def test_audit_light_dark_photon_has_no_invented_hadronic_spectrum():
    cls = DarkPhoton(name="dark photon")
    p = Point(m_chi=100, m_med=0.1, g_chi=0.35, g_q=1e-4)
    channels = cls.sigma_v_today(p, 1e-3)
    assert channels["A'A'"] > 1e-25 and channels["b"] < 1e-31
    assert fermi_ratio(channels, p.m_chi, database.data("fermi-1503.02641-dsph")["limits"], False) is None
    pbar = searches.antiprotons(cls, p, True)
    assert pbar.excluded is None and pbar.ratio is None and "cascade" in pbar.why


def test_pure_channel_thresholds_mixtures_and_dirac_factor():
    curves = {"bb": [[2, 1e-26], [1000, 1e-26]], "WW": [[2, 1e-26], [1000, 1e-26]]}
    assert pure_ratio({"b": 2e-26}, 100, curves, FERMI_CHANNELS, False) == pytest.approx(1)
    assert pure_ratio({"b": 2e-26}, 100, curves, FERMI_CHANNELS, True) == pytest.approx(2)
    for channels, mass in [({"b": 1e-26, "W": 1e-26}, 100), ({"W": 1e-26}, 50),
                           ({"SS": 1e-25}, 100), ({"b": 1e-26}, 3)]:
        assert pure_ratio(channels, mass, curves, FERMI_CHANNELS, True) is None


def test_ufo_new_bosons_keep_cascade_identity():
    a = SimpleNamespace(spin=1, pdg=9000001)
    b = SimpleNamespace(spin=0, pdg=9000002)
    assert channel_name(a, a).startswith("cascade")
    assert channel_name(a, b).startswith("cascade")
    assert channel_name(SimpleNamespace(spin=1, pdg=24), SimpleNamespace(spin=1, pdg=-24)) == "W"


def test_cmb_unknown_cascade_is_not_bounded_by_prompt_hadrons(monkeypatch):
    monkeypatch.setattr(searches, "_f_eff", lambda _: ({"bbbar": 0.3}, 0.2, 0.4))
    class Cascade:
        def sigma_v_today(self, p, v):
            return {"A'A'": 1e-23}
        def self_conjugate(self):
            return True
    result = searches.cmb(Cascade(), Point(m_chi=100, m_med=0.1), True)
    assert result.excluded is None and result.ratio is None
    assert "0 ≤ f_eff ≤ 1" in result.why
