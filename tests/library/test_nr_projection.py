"""DM8: the nonrelativistic reduction by explicit spinors, and the mediator cards checked against it."""

from __future__ import annotations

import numpy as np
import pytest

from adroit.core.dm_state import DarkMatterParticle
from adroit.library.interactions import nr_projection as nr
from adroit.library.interactions import registry
from adroit.physics.conventions import OPERATOR_MASS_GEV

M_CHI, M_N, SPEED = 100.0, OPERATOR_MASS_GEV, 3e-3


def test_the_two_textbook_reductions() -> None:
    """Anand et al. Eqs. (6) and (8): χ̄χN̄N → O1; χ̄γ^μγ⁵χ N̄γ_μγ⁵N → −4 O4."""
    scalar, _ = nr.project(nr.scalar, nr.scalar, M_CHI, M_N, (1, 4))
    assert scalar[1] == pytest.approx(1.0, rel=1e-5) and abs(scalar[4]) < 1e-9
    axial, _ = nr.project(nr.axial, nr.axial, M_CHI, M_N, (1, 4))
    assert axial[4] == pytest.approx(-4.0, rel=1e-5)


def test_an_axial_current_on_a_pointlike_nucleon() -> None:
    """χ̄γ^μγ⁵χ N̄γ_μN → 2 O8 + 2 O9: the same sign, as DirectDM also has (c8 = 2F₁, c9 = 2(F₁+F₂))."""
    c, rest = nr.project(nr.axial, nr.vector, M_CHI, M_N, (8, 9))
    assert c[8] == pytest.approx(2.0, rel=1e-6) and c[9] == pytest.approx(2.0, rel=1e-6) and rest < 1e-6


def test_the_spin_orbit_term_of_a_vector_current() -> None:
    """c3 = F₂ + F₁(1 + μ_N/m_χ)/2: the nucleon's Thomas-precession combination."""
    mu = M_CHI * M_N / (M_CHI + M_N)
    for f1, f2 in ((1.0, 0.0), (0.0, 1.0)):
        c, _ = nr.project(nr.vector, nr.nucleon_electromagnetic(f1, f2, M_N), M_CHI, M_N, (1, 3, 4, 5, 6),
                          speed=SPEED)
        assert c[3] == pytest.approx(f2 + f1 * (1 + mu / M_CHI) / 2, rel=1e-3)


def _card(card_id: str, values: dict, q: float) -> dict[int, float]:
    resolved = registry.resolve(card_id, DarkMatterParticle(mass_gev=M_CHI), values)
    out: dict[int, float] = {}
    for c in resolved.coefficients:
        out[c.operator] = out.get(c.operator, 0.0) + c.proton * float(c.q_factor(np.array([q]))[0])
    return out


def _dipole(bar_out, u_in, k_in, k_out):
    return nr.tensor_q(k_out - k_in, 1.0)(bar_out, u_in, k_in, k_out)


BIG = 1e5          # a mediator in the contact limit
CARDS = [
    ("M_vector", dict(g_chi=1.0, m_med=BIG, gV_p=1.0, gV_n=1.0, gT_p=0.7, gT_n=0.7),
     nr.vector, nr.nucleon_electromagnetic(1.0, 0.7, M_N), lambda q: -1 / BIG ** 2, (1, 3, 4, 5, 6)),
    ("M_axial_vector", dict(g_chi=1.0, m_med=BIG, gV_p=1.0, gV_n=1.0, gT_p=0.7, gT_n=0.7),
     nr.axial, nr.nucleon_electromagnetic(1.0, 0.7, M_N), lambda q: -1 / BIG ** 2, (8, 9)),
    ("M_vector_axial", dict(g_chi=1.0, m_med=BIG, gA_p=1.0, gA_n=1.0),
     nr.vector, nr.axial, lambda q: -1 / BIG ** 2, (7, 9)),
    ("M_magnetic_dipole", dict(mu_chi=1e-3), _dipole, nr.nucleon_electromagnetic(1.0, 1.793, M_N),
     lambda q: 0.30282212087175264 * 1e-3 / q ** 2, (1, 4, 5, 6)),
    ("M_anapole", dict(anapole=1e-5), nr.axial, nr.nucleon_electromagnetic(1.0, 1.793, M_N),
     lambda q: 0.30282212087175264 * 1e-5, (8, 9)),
    ("M_charge_radius", dict(b_chi=1e-5), nr.vector, nr.nucleon_electromagnetic(1.0, 1.793, M_N),
     lambda q: 0.30282212087175264 * 1e-5, (1, 3, 4, 5, 6)),
]


@pytest.mark.parametrize("card_id,values,chi,nucleon,factor,ops", CARDS, ids=[c[0] for c in CARDS])
def test_mediator_cards_agree_with_the_explicit_reduction(card_id, values, chi, nucleon, factor, ops) -> None:
    """Every operator of the card in the same ratio to the explicit reduction (one overall sign allowed).

    The cards combining Table 1's one-q operators with others had wrong relative signs
    before 2026-10-01; the tolerance allows the recoil corrections (μ_N/m_χ ≈ 1%).
    """
    q = float(np.linalg.norm(nr.kinematics(M_CHI, M_N, SPEED, 1)["q"]))
    explicit, rest = nr.project(chi, nucleon, M_CHI, M_N, ops, speed=SPEED)
    card = _card(card_id, values, q)
    ratios = [card.get(i, 0.0) / (factor(q) * explicit[i]) for i in ops
              if abs(explicit[i]) > 1e-9 * max(abs(v) for v in explicit.values())]
    assert rest < 1e-5
    assert all(r == pytest.approx(ratios[0], rel=0.01) for r in ratios) and abs(ratios[0]) == pytest.approx(1.0, rel=0.01)


def _with_momentum(current):
    """(P^μ or K^μ)/m_M × a scalar bilinear, with m_M = m_N as LZ sets it."""
    return lambda bar_out, u_in, k_in, k_out: (k_in + k_out) / M_N * current(bar_out, u_in, k_in, k_out)


LZ_FORMS = [            # card, its Lagrangian's two currents, the operators it carries
    ("L05_LZ", nr.vector, nr.vector, (1,)),
    ("L07_LZ", nr.vector, nr.axial, (7, 9)),
    ("L08_LZ", nr.vector, _with_momentum(nr.pseudoscalar), (10,)),
    ("L13_LZ", nr.axial, nr.vector, (8, 9)),
    ("L17_LZ", _with_momentum(nr.pseudoscalar), nr.vector, (11,)),
]


@pytest.mark.parametrize("card_id,chi,nucleon,ops", LZ_FORMS, ids=[c[0] for c in LZ_FORMS])
def test_lz_cards_carry_the_leading_terms_of_their_lagrangians(card_id, chi, nucleon, ops) -> None:
    """Each card's operators equal the explicit reduction of its vector-current Lagrangian (m_M = m_N), signs
    included; the full reduction's further terms are suppressed by q or v⊥ (under 0.1% in LZ's xenon limits)."""
    from adroit.experiments.lz_extended_window import lz_values
    explicit, _ = nr.project(chi, nucleon, M_CHI, M_N, ops, speed=SPEED)
    resolved = registry.resolve(card_id, DarkMatterParticle(mass_gev=M_CHI), lz_values(card_id, "s"))
    card = {c.operator: c.proton / resolved.parameters["d_p"] for c in resolved.coefficients}
    assert set(card) == set(ops)
    for i in ops:
        assert card[i] == pytest.approx(explicit[i], rel=2e-3), (card_id, i)


def test_lzs_l6_is_its_lagrangian_with_the_o3_term_reversed() -> None:
    """L06_LZ: LZ's table and the explicit reduction agree on every term; LZ's limits need O3 reversed (the only
    term odd in v⊥), and the card carries that, for comparisons with LZ."""
    from adroit.experiments.lz_extended_window import lz_values
    tensor = lambda bar_out, u_in, k_in, k_out: nr.tensor_q(k_in - k_out, M_N)(bar_out, u_in, k_in, k_out)  # noqa: E731
    explicit, rest = nr.project(nr.vector, tensor, M_CHI, M_N, (1, 3, 4, 6), speed=SPEED)
    q = float(np.linalg.norm(nr.kinematics(M_CHI, M_N, SPEED, 1)["q"]))
    card = _card("L06_LZ", lz_values("L06_LZ", "s"), q)
    d = lz_values("L06_LZ", "s")["d_p"]
    assert rest < 1e-6
    for i, sign in ((1, 1), (3, -1), (4, 1), (6, 1)):
        assert card[i] / d == pytest.approx(sign * explicit[i], rel=2e-3), i
