"""Width-dependent applicability of CMS's spin-0 NWA rescaling."""
import pytest

from adroit.parameter_space.classes import Point, ScalarClass
from adroit.parameter_space.searches import monojet_spin0


def test_audit_broad_point_is_pending_and_narrow_point_retained():
    """The widths with the DMsimp card's Yukawas (its top 172 GeV: the owner's decision #2, 2026-10-20)."""
    cls = ScalarClass(dm_pseudoscalar=True, sm_pseudoscalar=True)
    p = Point(m_chi=100, m_med=500, g_chi=1, g_q=1)
    narrow = monojet_spin0(cls, p, True)
    broad = monojet_spin0(cls, p.model_copy(update={"g_chi": 3, "g_q": 3}), True)
    assert narrow.width_ratio == pytest.approx(0.0786751, rel=1e-5)
    assert narrow.excluded is False and narrow.ratio == pytest.approx(0.791396, rel=1e-5)
    assert broad.width_ratio == pytest.approx(0.7080763, rel=1e-5)
    assert broad.excluded is None and broad.ratio is None and "Γ/M" in broad.why


@pytest.mark.parametrize("pseudo", [False, True])
def test_benchmark_width_boundary_and_closed_decay(pseudo):
    cls = ScalarClass(dm_pseudoscalar=pseudo, sm_pseudoscalar=pseudo)
    p = Point(m_chi=1, m_med=500, g_chi=1, g_q=1)
    at = monojet_spin0(cls, p, True)
    assert at.width_ratio == pytest.approx(at.reference_width_ratio) and at.ratio is not None
    above = monojet_spin0(cls, p.model_copy(update={"g_chi": 1.001, "g_q": 1.001}), True)
    assert above.excluded is None
    below = monojet_spin0(cls, p.model_copy(update={"g_chi": .99, "g_q": .99}), True)
    assert below.ratio is not None
    closed = monojet_spin0(cls, p.model_copy(update={"m_chi": 250}), True)
    assert closed.excluded is None and "closed" in closed.why


def test_a_point_within_a_few_widths_of_the_invisible_threshold_is_pending():
    """The external audit's A07 (2026-10-16): M = 350 GeV, m_χ = 174 GeV, g_χ = 2, g_q = 1 (pseudoscalar) passes the
    width gate (Γ/M 0.0269 against the benchmark's 0.0497) only 2 GeV above threshold with Γ = 9.42 GeV, and had been
    excluded (μ/limit 2.19). Within 5Γ of m_med = 2m_χ the narrow-width rescaling does not hold: pending. (Γ = 9.40 GeV
    with the DMsimp card's top Yukawa, 172 GeV: the owner's decision #2.)"""
    cls = ScalarClass(dm_pseudoscalar=True, sm_pseudoscalar=True)
    p = Point(m_chi=174, m_med=350, g_chi=2, g_q=1)
    assert cls.width(p) == pytest.approx(9.39661, rel=1e-5)
    near = monojet_spin0(cls, p, True)
    assert near.excluded is None and near.ratio is None and "invisible-decay threshold" in near.why
    far = monojet_spin0(cls, Point(m_chi=100, m_med=500, g_chi=1, g_q=1), True)   # 300 GeV above, 5Γ = 197 GeV
    assert far.excluded is False and far.ratio == pytest.approx(0.791396, rel=1e-5)


def test_the_threshold_rule_is_the_line_shapes_tail():
    from adroit.parameter_space.searches import THRESHOLD_WIDTHS, _threshold
    assert _threshold(500.0, 200.0, 100.0 / THRESHOLD_WIDTHS) == ""            # exactly 5Γ: allowed to decide
    assert _threshold(500.0, 200.0, 100.0 / THRESHOLD_WIDTHS * 1.01) != ""
