"""Two resolved 0.6-ratio Fermi lines are not a 1.2-ratio exclusion."""
import pytest

from adroit.constraints import searches as data
from adroit.parameter_space import searches
from adroit.parameter_space.classes import Point


class Lines:
    def __init__(self, gg, zg, self_conjugate=True):
        self.gg, self.zg, self.majorana = gg, zg, self_conjugate
    def self_conjugate(self):
        return self.majorana
    def line_sigma_v(self, p):
        return {"gamma": self.gg, "Zgamma": self.zg}


def test_audit_two_resolved_lines_are_separate_cuts(monkeypatch):
    # Fermi's rule alone: DAMPE (staged) leaves this pair pending, since both lines fall in its fitting window
    monkeypatch.setattr(searches, "LINE_RECORDS", tuple(r for r in searches.LINE_RECORDS if not r.startswith("dampe")))
    mass = 100
    energy = mass - searches.M_Z ** 2 / (4 * mass)
    assert energy == pytest.approx(79.2120540156)
    curve = data._bundled("fermi-lat-1506.00013-lines")["limit"]
    gg = .6 * data.interpolate(curve, mass)
    zg = .6 * 2 * (mass / energy) ** 2 * data.interpolate(curve, energy)
    assert gg == pytest.approx(7.31282662881262e-28, rel=1e-6, abs=0)
    assert zg == pytest.approx(9.135061516604565e-28, rel=1e-6, abs=0)
    result = searches.lines(Lines(gg, zg), Point(m_chi=mass, m_med=1), True)
    assert result.excluded is False and result.ratio == pytest.approx(.6)
    assert searches.lines(Lines(gg, zg, False), Point(m_chi=mass, m_med=1), True).ratio == pytest.approx(.3)


def test_overlap_is_pending_and_hess_source_combination_is_kept():
    result = searches.lines(Lines(1e-28, 1e-28), Point(m_chi=150, m_med=1), True)
    assert result.excluded is None and "two-line" in result.why
    assert searches._line_ratio("fermi-lat-1506.00013-lines", 0, 1e-28, 40) is None
    for record in ("hess-1805.05741-lines", "hess-2608.07234-lines"):
        curve = data._bundled(record)["limit"]
        assert searches._line_ratio(record, 1e-28, 2e-28, 1000) == pytest.approx(
            2e-28 / data.interpolate(curve, 1000))
