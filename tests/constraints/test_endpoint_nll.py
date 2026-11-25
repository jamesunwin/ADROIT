"""The resummed line and endpoint of a pure odd n-plet (``constraints.endpoint_nll``): the structures against the
published wino and quintuplet formulas, the exclusive limit, the phases, and the quintuplet's line against its
paper."""

import cmath
import math
import random

import pytest

from adroit.constraints import endpoint_nll as nll

SQ2 = math.sqrt(2.0)


def _random_s(rng: random.Random, charges: int) -> dict[int, complex]:
    return {q: complex(rng.uniform(-3, 3), rng.uniform(-3, 3)) for q in range(charges + 1)}


def test_a_and_b_are_the_published_combinations():
    """The wino: a = s₀± + √2 s₀₀, b = s₀± (arXiv:1808.08956); the quintuplet: a = 2s₀±± + 5s₀± + 3√2 s₀₀,
    b = 4s₀±± + s₀± (arXiv:2309.11562 eq. (2.24))."""
    rng = random.Random(1)
    s = _random_s(rng, 1)
    assert nll.ab(3, s) == pytest.approx((s[1] + SQ2 * s[0], s[1]))
    s = _random_s(rng, 2)
    assert nll.ab(5, s) == pytest.approx((2 * s[2] + 5 * s[1] + 3 * SQ2 * s[0], 4 * s[2] + s[1]))
    with pytest.raises(ValueError):
        nll.ab(4, s)


@pytest.mark.parametrize("n", [3, 5, 7, 9])
def test_an_su2_singlet_has_a_equal_to_2b(n):
    """M^{ab} ∝ δ^{ab} (A = B) is s₀Q = √2 s₀₀ for every Q in the formulas' phases, and then a = 2b."""
    j = (n - 1) // 2
    a, b = nll.ab(n, {0: 1.0, **{q: SQ2 for q in range(1, j + 1)}})
    assert abs(a - 2 * b) < 1e-12 * abs(b)


def test_the_structures_are_the_winos_published_nll_spectrum():
    """𝓕₀ and 𝓕₁ of arXiv:1808.08956 eq. (4.7), coefficient by coefficient, at random s, Λ and r."""
    rng = random.Random(2)
    for _ in range(5):
        s = _random_s(rng, 1)
        lam = tuple(rng.uniform(0.5, 1.5) for _ in range(4))
        r_h, r_hs = rng.uniform(0.6, 1.0), rng.uniform(0.7, 1.0)
        f0, f1 = nll.structures(*nll.ab(3, s), lam, r_h, r_hs)
        la, lb, lc, ld = lam
        s00, spm = s[0], s[1]
        re, im = (s00 * spm.conjugate()).real, (s00 * spm.conjugate()).imag
        r12, r6 = r_hs ** (12 / nll.BETA0), r_hs ** (6 / nll.BETA0)
        phase = 6 * math.pi / nll.BETA0 * math.log(r_h)
        c_h, s_h = math.cos(phase), math.sin(phase)
        paper0 = (abs(s00) ** 2 * (4 * ld + 2 * r12 * lc) + abs(spm) ** 2 * (8 * ld + r12 * lc)
                  + SQ2 * re * (8 * ld - 2 * r12 * lc))
        paper1 = r_h ** (6 / nll.BETA0) * (abs(s00) ** 2 * (2 * r6 * la - 8 * c_h * lb)
                                           + abs(spm) ** 2 * (r6 * la + 8 * c_h * lb)
                                           + SQ2 * re * (-2 * r6 * la - 4 * c_h * lb) + SQ2 * im * (-12 * s_h * lb))
        assert f0 == pytest.approx(paper0, rel=1e-12) and f1 == pytest.approx(paper1, rel=1e-12)


@pytest.mark.parametrize("n", [3, 5])
def test_at_leading_log_the_structures_are_the_papers_f0_and_f1(n):
    """With Λ = 1 and no running, 𝓕₀ and 𝓕₁ are 9/2 of the LL combinations F₀ = (4/3)|b|² + (2/3)|a|² and
    F₁ = (8/3)|b|² − (2/3)|a|² (arXiv:2309.11562 eq. (2.24)), the 9/2 being the prefactors' convention."""
    rng = random.Random(3)
    s = _random_s(rng, (n - 1) // 2)
    a, b = nll.ab(n, s)
    f0, f1 = nll.structures(a, b, (1.0, 1.0, 1.0, 1.0), 1.0, 1.0)
    assert f0 == pytest.approx(4.5 * (4 / 3 * abs(b) ** 2 + 2 / 3 * abs(a) ** 2), rel=1e-12)
    assert f1 == pytest.approx(4.5 * (8 / 3 * abs(b) ** 2 - 2 / 3 * abs(a) ** 2), rel=1e-12)


def test_without_running_the_line_is_the_tree_level_line():
    """𝓕₀ + 𝓕₁ at Λ = 1, r = 1 is 18|b|², so σv = πα₂²s_W²·18|b|²/(9M²) = 2πα₂²s_W²|b|²/M² (``tree_line``)."""
    rng = random.Random(4)
    s = _random_s(rng, 2)
    a, b = nll.ab(5, s)
    f0, f1 = nll.structures(a, b, (1.0, 1.0, 1.0, 1.0), 1.0, 1.0)
    assert f0 + f1 == pytest.approx(18 * abs(b) ** 2, rel=1e-12)


def test_the_exclusive_limit_is_the_winos_published_exclusive_line():
    """z_cut → 1 is σ_exc^NLL of arXiv:1808.08956 eq. (4.8), halved to the γγ-equivalent line."""
    rng = random.Random(5)
    s = _random_s(rng, 1)
    m = 3000.0
    a_h = nll.alpha_w(2 * m) / (4 * math.pi)
    r_h = nll._r(2 * m)
    u_h = r_h ** 2 * nll._evolution(r_h, a_h, -1.0, 2.0)
    r12, r6 = r_h ** (12 / nll.BETA0), r_h ** (6 / nll.BETA0)
    phase = 6 * math.pi / nll.BETA0 * math.log(r_h)
    c_h, s_h = math.cos(phase), math.sin(phase)
    s00, spm = s[0], s[1]
    x = s00 * spm.conjugate()
    braces = ((4 + 4 * r12 - 8 * r6 * c_h) * abs(s00) ** 2 + (8 + 2 * r12 + 8 * r6 * c_h) * abs(spm) ** 2
              + SQ2 * (8 - 4 * r12 - 4 * r6 * c_h) * x.real - 12 * SQ2 * r6 * s_h * x.imag)
    exclusive = math.pi * nll.alpha_w(2 * m) ** 2 * nll.SW2 / (9 * m * m) * u_h * braces * nll.GEV2_CM3_S
    assert nll.cumulative(m, 3, s, 1.0) == pytest.approx(exclusive, rel=1e-9)


def test_the_endpoint_adds_photons_below_the_line():
    """The rate grows as the window opens (more endpoint photons), and is the line at z_cut = 1."""
    s = {0: complex(1.5), 1: complex(2.0)}
    rates = [nll.cumulative(10000.0, 3, s, z) for z in (1.0, 0.99, 0.95, 0.9)]
    assert rates == sorted(rates) and rates[-1] > 1.1 * rates[0]


def test_the_winos_first_resonance_moves_up_at_nlo():
    """With Beneke et al.'s coupling, the wino's first Sommerfeld peak is at 2.255 TeV (LO) and 2.390 TeV (NLO):
    DMγSpec's are 2.282 and 2.421, the same 6% shift (single-particle speed 10⁻³)."""
    grid = [2200.0 + 10.0 * k for k in range(26)]
    for nlo, expected in ((False, 2255.0), (True, 2390.0)):
        values = [abs(nll.amplitudes(3, m, 2e-3, alpha2=nll.ALPHA2_BENEKE, nlo=nlo)[1]) for m in grid]
        assert abs(grid[values.index(max(values))] - expected) <= 10.0


def test_the_thermal_quintuplets_line_is_its_papers():
    """arXiv:2309.11562 Fig. 1 (left), digitised: the NLL line at 13.6 TeV is 8.62 × 10⁻²⁶ cm³/s, its band 8.26–8.89
    (v = 10⁻³ relative)."""
    s = nll.amplitudes(5, 13600.0, 1e-3)
    assert 8.26e-26 <= nll.cumulative(13600.0, 5, s, 1.0) <= 8.89e-26


def test_the_line_rate_is_computed_from_1_to_100_tev():
    assert nll.line_sigma_v(5, 800.0) is None and nll.line_sigma_v(5, 2e5) is None
    rate = nll.line_sigma_v(5, 13600.0)
    assert rate > nll.cumulative(13600.0, 5, nll.amplitudes(5, 13600.0, 1e-3), 1.0)
    assert cmath.isfinite(nll.line_sigma_v(5, 90000.0))


def test_the_two_loop_cusp_is_the_standard_one():
    """The audit's G8-6 (G12): Γ₁ = C_A(268/9 − 4π²/3) − (80/9)n_f T_F − 16/9 = 4(70/9 − 2π²/3) (arXiv:1808.08956
    eq. (3.7)); the quintuplet paper prints (8/9)(35 − π²), a typo, which had been copied."""
    assert nll.GAMMA1 == pytest.approx(2 * (268 / 9 - 4 * math.pi ** 2 / 3) - 80 / 9 * 6 * 0.5 - 16 / 9, rel=1e-12)
