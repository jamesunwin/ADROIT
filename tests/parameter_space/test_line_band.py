"""The theory band of a resummed γ-ray line rate in the line decision (decision D30, G12: the owner's points 2, 4 and
5): NLL against NLL′, bound states' line photons, and DMγSpec's drift above 13 TeV."""

import pytest

from adroit.constraints import endpoint_nll, resummed_lines
from adroit.parameter_space import searches
from adroit.parameter_space.classes import Point


class _Lines:
    """A self-conjugate dark matter whose only computed annihilation today is a resummed line."""

    def __init__(self, rate: float, band: tuple[float, float, str] = (1.0, 1.0, "")) -> None:
        self.rate, self.band = rate, band

    def self_conjugate(self) -> bool:
        return True

    def resummed_lines(self, p: Point) -> dict[str, float]:
        return {"gamma": self.rate}

    def line_band(self, p: Point) -> tuple[float, float, str]:
        return self.band


P = Point(m_chi=2000.0, m_med=0.0, g_chi=1.0, g_q=0.0, g_l=0.0)


def _at(ratio: float, band=(1.0, 1.0, "")):
    """The outcome for a rate at ``ratio`` times the strongest limit at 2 TeV."""
    unit = searches.lines(_Lines(1e-27), P, True).ratio
    return searches.lines(_Lines(1e-27 * ratio / unit, band), P, True)


def test_the_bands():
    assert endpoint_nll.theory_band(3)[:2] == pytest.approx((0.95, 1.05))
    low, high, why = endpoint_nll.theory_band(5)
    assert low == pytest.approx(0.95) and high == float("inf") and "bound states" in why   # D32: no upper edge
    assert endpoint_nll.theory_band(7)[1] == float("inf")
    assert resummed_lines.theory_band(12000.0) == (1.0, 1.0, "")
    assert resummed_lines.theory_band(20000.0)[:2] == pytest.approx((0.75, 1.25))


def test_a_rate_whose_band_straddles_the_limit_is_undecided():
    band = endpoint_nll.theory_band(3)
    assert _at(1.02).excluded is True
    straddling = _at(1.02, band)
    assert straddling.excluded is None and "theory band straddles" in straddling.why
    assert _at(0.90, band).excluded is False and "theory band ×0.95–1.05" in _at(0.90, band).why
    assert _at(1.06, band).excluded is True                   # 1.06 × 0.95 > 1


@pytest.mark.parametrize("ratio", [0.8, 0.5, 0.1])
def test_an_n_of_five_or_more_is_never_allowed_by_its_central_rate(ratio):
    """The external audit's A05 (decision D32): bound states' line photons are not computed and can lead at isolated
    masses near the Sommerfeld peaks (arXiv:2309.11562, Fig. 7), so a rate below the limit is pending, not allowed;
    the audit's control had a central ratio of 0.8 returning allowed."""
    outcome = _at(ratio, endpoint_nll.theory_band(5))
    assert outcome.excluded is None and "no upper edge" in outcome.why


def test_an_n_of_five_or_more_is_still_excluded_by_its_lower_edge():
    """Bound states only add photons: an exclusion by the direct rate's lower edge stands (the audit's 1.06 control)."""
    assert _at(1.06, endpoint_nll.theory_band(5)).excluded is True
    assert _at(1.0, endpoint_nll.theory_band(5)).excluded is None                  # 1.0 × 0.95 < 1
