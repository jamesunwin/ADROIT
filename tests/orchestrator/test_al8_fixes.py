"""The auditor's cycle-7 findings, repaired (AL7-01..05, 2026-11-17; the AL8 repair record of 2026-11-17).

- AL7-01: the CMB's rate is σv = a + b v² from the two probes only where no annihilation pole's velocity scale lies
  below them; else where σv = a + b v² holds again on three speeds below every scale, or it is not computed.
- AL7-02: a published Ωh²'s fall to x → ∞, its tail bounded by the rate's slope, is within the relic density's theory
  uncertainty; a rate tabulated short of the window is refused.
- AL7-03: the generic route's threshold refusal reads the poles of a pair's own amplitudes.
- AL7-04: DM7's relic comparison returns its pending verdict on a refused Ωh².
- AL7-05: a final state closed at low speed gives the CMB a zero rate, not "not resolved".

Offline: no network, no key, no provider call.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from adroit.constraints import relic
from adroit.constraints import searches as core


def _model(b_couplings: dict[str, float], a_couplings: tuple[float, float] = (0.1, 0.3)):
    """χ (Dirac, 100 GeV); a pseudoscalar a (300 GeV) coupled to χ and to muons; a pseudoscalar b (200 GeV, at the χ χ̄
    threshold) coupled to the fermions named in ``b_couplings``."""
    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space.portals import generic

    def term(f: str, boson: str, c: str) -> dict:
        return dict(fields=[dict(field=f, conjugate=True), dict(field=f), dict(field=boson)], lorentz="pseudoscalar",
                    coupling=c, text=f"{c} {boson} {f}bar gamma5 {f}")
    couplings = [dict(name="ga", value=a_couplings[0]), dict(name="ya", value=a_couplings[1])]
    terms = [term("chi", "a", "ga"), term("mu", "a", "ya")]
    for f, value in b_couplings.items():
        couplings.append(dict(name=f"b_{f}", value=value))
        terms.append(term(f, "b", f"b_{f}"))
    spec = ModelSpec.model_validate(dict(
        name="two_pseudoscalars", phase="broken", stability="Z2",
        fields=[dict(name="chi", role="dark_matter", spin=0.5, mass_gev=100.0, dark_parity=-1),
                dict(name="a", role="mediator", spin=0, self_conjugate=True, mass_gev=300.0, dark_parity=1),
                dict(name="b", role="other", spin=0, self_conjugate=True, mass_gev=200.0, dark_parity=1),
                dict(name="mu", role="standard_model", spin=0.5, mass_gev=0.105658, charges={"electric_charge": -1})],
        couplings=couplings, terms=terms))
    engine = generic.GenericModel.of(spec)
    return engine, engine.point()


# --- AL7-01 ----------------------------------------------------------------------------------------------------

def test_a_second_narrower_pole_is_never_read_as_allowed() -> None:
    """The auditor's model: b (5 × 10⁻⁷ to χ, 4 × 10⁻⁵ to muons) beside a. σv = a + b v² held at 10⁻³ (6.6 × 10⁻²⁷) and the
    CMB allowed it (0.018), where σv is 170 times that below 10⁻⁵ and the CMB excludes it (3.06)."""
    from adroit.parameter_space import searches
    engine, p = _model({"chi": 5e-7, "mu": 4e-5})
    scales = core.velocity_scales(engine, p)
    assert scales[0] == pytest.approx(1.6e-5, rel=0.05)              # b's: √(MΓ)/m
    with pytest.raises(core.CMBUnresolved, match="velocity scale"):
        core.s_wave(engine, p)
    assert searches.cmb(engine, p, False).excluded is None


class _Fixture:
    """A rate by speed and the poles it declares, for the CMB's rule alone."""

    def __init__(self, rate, poles=()) -> None:
        self.rate, self.poles = rate, list(poles)

    def sigma_v_today(self, p, v: float) -> dict[str, float]:
        return {"b": self.rate(v)}

    def annihilation_poles(self, p) -> list[tuple[float, float]]:
        return self.poles


class _P:
    m_chi = 100.0


def _two_scales(v: float) -> float:
    """A broad s-wave beside a narrow structure that shows only below v ≈ 10⁻⁴ (as the auditor's boundary fixture)."""
    return 1e-26 + 1e-22 * 1e-20 / ((v * v / 4) ** 2 + 1e-20)


def test_a_declared_narrow_pole_sends_the_rate_below_its_scale() -> None:
    """σv = a + b v² from the probes holds at 10⁻³ (within 0.2%), which AL6-02 took (10⁻²⁶); with the pole declared
    (M = 200 GeV, its velocity scale 2 × 10⁻⁵) the rate is read below it, where σv has flattened out at 10⁴ times
    that."""
    assert core._flat(_two_scales(1e-3), 1e-26)
    found = core.s_wave(_Fixture(_two_scales, [(200.0, 2e-8)]), _P())
    assert sum(found.values()) == pytest.approx(_two_scales(1e-8), rel=0.01) and sum(found.values()) > 9e-23


def test_an_early_flat_pair_with_a_rise_below_is_not_a_plateau() -> None:
    """The auditor's false descent: a v⁴ term fails the check at 10⁻³, and the descent's first flat pair is above a rise
    to 10⁻²¹; the lowest speed with a rate disagrees, so no plateau (AL6-02's descent took the first pair)."""
    def rate(v: float) -> float:
        return 1e-26 + 1e-18 * v ** 4 + 1e-21 * 1e-24 / ((v * v / 4) ** 2 + 1e-24)
    with pytest.raises(core.CMBUnresolved, match="not flattened out"):
        core.s_wave(_Fixture(rate), _P())


def test_a_flat_stretch_above_a_rise_below_is_not_the_rate() -> None:
    """Three speeds flat at 10⁻²⁶ (10⁻³ to 10⁻⁴) above a rise that appears only near 10⁻⁷ (to 10⁻²²): the lowest speed
    with a rate disagrees, so the stretch is not taken, and nothing below it is flat."""
    fixture = _Fixture(lambda v: 1e-26 + 1e-22 / (1 + (v / 3e-7) ** 4), [(200.0, 4.5e-4)])
    assert core.velocity_scales(fixture, _P())[0] == pytest.approx(3e-3, rel=0.01)
    with pytest.raises(core.CMBUnresolved, match="not flattened out"):
        core.s_wave(fixture, _P())


def test_a_pole_whose_scale_lies_below_the_descent_leaves_the_rate_undecided() -> None:
    """σv flat at 10⁻²⁶ down to 10⁻⁷, but a pole declared at the threshold with a velocity scale of 3 × 10⁻⁸: what
    happens below the descent is not seen, so no rate is taken."""
    fixture = _Fixture(lambda v: 1e-26, [(200.0, 4.5e-14)])
    assert core.velocity_scales(fixture, _P())[0] == pytest.approx(3e-8, rel=0.01)
    with pytest.raises(core.CMBUnresolved, match="velocity scale"):
        core.s_wave(fixture, _P())


@pytest.mark.parametrize("entry_id", ["b_minus_l", "alp_portal", "scalar_mediator", "dmwg_V1"])
def test_the_librarys_analytic_classes_declare_their_pole(entry_id) -> None:
    from adroit.parameter_space import library
    entry = library.entry(entry_id)
    p = entry.point.model_copy(update={"m_med": 2.0 * entry.point.m_chi})
    cls = entry.model_class
    poles = cls.annihilation_poles(p) if hasattr(cls, "annihilation_poles") else cls.resonances(p)
    mass, width = next((m, w) for m, w in poles if m == p.m_med)
    assert width > 0
    assert math.sqrt(mass * width) / p.m_chi == pytest.approx(min(core.velocity_scales(cls, p)))


def test_a_pole_far_from_the_threshold_keeps_the_two_probes_rate() -> None:
    fixture = _Fixture(lambda v: 3e-26 + 2e-24 * v * v, [(600.0, 10.0)])
    assert core.velocity_scales(fixture, _P()) == [pytest.approx(math.sqrt(600 ** 2 - 4e4) / 100)]
    assert sum(core.s_wave(fixture, _P()).values()) == pytest.approx(3e-26, rel=1e-9)


def test_a_p_wave_rate_near_a_pole_falls_to_zero_and_is_not_unresolved() -> None:
    """σv ∝ v² below a pole's scale has no plateau, but σv = a + b v² holds with a = 0: the s-wave rate is zero, where
    AL6-02's descent had found no flat pair and left the CMB undecided."""
    found = core.s_wave(_Fixture(lambda v: 1e-20 * v * v / (1 + (v / 1e-3) ** 2), [(200.0, 0.02)]), _P())
    assert sum(found.values()) == pytest.approx(0.0, abs=1e-30)


# --- AL7-02 ----------------------------------------------------------------------------------------------------

def _nodes_rising(power: float, last: float = 1e8) -> tuple[np.ndarray, np.ndarray]:
    nodes = np.geomspace(1.0, last, 450)
    return nodes, 1e-9 * np.maximum(nodes / 20.0, 1.0) ** power


def test_a_rate_still_rising_beyond_the_window_is_refused() -> None:
    """The auditor's: ⟨σv⟩ ∝ x^0.8 falls by 2.4% in the window (passing AL6-01's test) and by a further 13.6% to x = 10⁸."""
    nodes, rates = _nodes_rising(0.8)
    y = relic.freeze_out(100.0, nodes, rates, settled=False)
    window = relic.late_change(100.0, nodes, rates, y, 1e4, True, None)
    assert 0.02 < window < relic.LATE_TOLERANCE
    rest, slope = relic.remainder_change(100.0, nodes, rates, y, 1e4, True, None)
    there = relic.freeze_out(100.0, nodes, rates, x_end=1e8, settled=False)
    assert slope == pytest.approx(0.8, abs=0.01) and rest > 1.0 - there / y > 0.13
    with pytest.raises(relic.RelicUnresolved, match=r"still rises as x\^0\.8"):
        relic.freeze_out(100.0, nodes, rates)


def test_a_constant_rate_is_published_with_its_bounded_remainder() -> None:
    nodes = np.geomspace(1.0, 2e4, 140)
    rates = np.full_like(nodes, 2e-9)
    y = relic.freeze_out(100.0, nodes, rates)
    window = relic.late_change(100.0, nodes, rates, y, 1e4, True, None)
    rest, slope = relic.remainder_change(100.0, nodes, rates, y, 1e4, True, None)
    assert abs(slope) < 1e-9 and rest == pytest.approx(2.0 * window, rel=0.05) and rest < 1e-3


@pytest.mark.parametrize("last", [5e3, 1.5e4])
def test_a_rate_tabulated_short_of_the_window_is_refused(last) -> None:
    """A table ending at 5 × 10³ (before the endpoint) or 1.5 × 10⁴ (inside the window) had given no change."""
    nodes, rates = _nodes_rising(0.6, last)
    with pytest.raises(relic.RelicUnresolved, match="tabulated only to"):
        relic.freeze_out(100.0, nodes, rates)


def test_the_remainder_tolerance_is_the_relic_densitys_theory_uncertainty() -> None:
    from adroit.parameter_space.likelihood import LikelihoodSettings
    assert relic.REMAINDER_TOLERANCE == LikelihoodSettings().relic_theory == 0.10


def test_a_slope_of_one_or_more_has_no_bound() -> None:
    nodes, rates = _nodes_rising(1.2, 2e4)
    assert relic.remainder_change(100.0, nodes, rates, 1e-12, 1e4, True, None) == (1.0, pytest.approx(1.2))


def test_the_wino_stays_published() -> None:
    """The validated multiplets rise as x^0.5 at the table's end: bounded at 3.5% (the wino) to 5.5% (the quintuplet),
    within the 10%."""
    from adroit.parameter_space import library
    entry = library.entry("wino")
    assert entry.model_class.omega_h2(entry.point) is not None


# --- AL7-03 ----------------------------------------------------------------------------------------------------

def test_a_spectator_at_the_threshold_does_not_refuse_the_relic() -> None:
    """The auditor's: b at 200 GeV coupled only to muons (6 × 10⁻⁶) is in no diagram of χ χ̄; it had refused Ωh²."""
    engine, p = _model({"mu": 6e-6}, a_couplings=(0.1, 0.1))
    assert engine.domain(p) == ""
    assert 200.0 not in [m for m, _ in engine.annihilation_poles(p)]


def test_a_narrow_pole_in_the_pairs_amplitudes_is_still_refused() -> None:
    engine, p = _model({"chi": 6e-6, "mu": 6e-6}, a_couplings=(0.1, 0.1))
    assert "closer than the tree amplitudes resolve" in engine.domain(p)
    assert 200.0 in [m for m, _ in engine.annihilation_poles(p)]


# --- AL7-04 ----------------------------------------------------------------------------------------------------

def _dm7(g: float):
    from adroit.constraints import database, spin1, verdicts
    from adroit.core.dm_state import DarkMatterParticle, InteractionModel, OperatorCoefficient
    model = spin1.Spin1Model(kind="vector", m_med_gev=200.0, g_dm=0.1, g_q=g, g_l=g)
    candidate = verdicts.Candidate(
        label="narrow-threshold", particle=DarkMatterParticle(mass_gev=100.0),
        interaction=InteractionModel(name="O1", layer="nonrelativistic",
                                     coefficients=[OperatorCoefficient(operator=1, proton=1e-8, neutron=1e-8)]),
        completion=model)
    return verdicts.relic_judged(candidate, database.record("planck-2018-omega"))


@pytest.mark.parametrize("g", [0.001, 0.006, 0.01])
def test_dm7s_relic_comparison_is_pending_on_a_refused_density(g) -> None:
    from adroit.core.dm_state import Applicability
    verdict, certificate = _dm7(g)
    assert verdict.applicability == Applicability.needs_calculation and verdict.excluded is None
    assert "refused here: annihilation has not stopped" in verdict.needed_calculation
    assert [(c.name, c.state) for c in certificate.checks] == [("finite_comparisons", "unknown")]


@pytest.mark.needs("eos")
def test_dm7s_relic_comparison_is_unchanged_at_a_regular_point() -> None:
    from adroit.core.dm_state import Applicability
    verdict, certificate = _dm7(0.3)
    assert verdict.applicability == Applicability.applies_with_assumptions and verdict.excluded is False
    assert ("finite_comparisons", "satisfied") in [(c.name, c.state) for c in certificate.checks]


# --- AL7-05 ----------------------------------------------------------------------------------------------------

def _muons(m_chi_over_m_mu: float):
    from adroit.core.model_contracts import VECTOR_FLAVOURS
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.flavour_vector import FlavourVectorClass
    cls = FlavourVectorClass(flavour_couplings={n: 1.0 if n == "mu" else 0.0 for n in VECTOR_FLAVOURS})
    p = Point(m_chi=1.0, m_med=10.0, g_chi=0.5, g_q=0.0, g_l=0.0)
    mass = next(f.mass_gev for f in cls.model(p).fermions() if f.name == "mu")
    return cls, p.model_copy(update={"m_chi": mass * m_chi_over_m_mu})


@pytest.mark.parametrize("ratio", [1 - 1e-6, 1 - 1e-5])
def test_a_channel_closed_at_low_speed_gives_no_cmb_rate(ratio) -> None:
    """The auditor's: m_χ just below m_μ, the muon channel open at v = 0.01 and closed from 10⁻³ down. It had been "not
    resolved" (the descent compared zeros); the rate during recombination is zero, so the CMB does not apply."""
    from adroit.parameter_space import searches
    cls, p = _muons(ratio)
    assert core.s_wave(cls, p) == {}
    assert searches.cmb(cls, p, False) is None


@pytest.mark.needs("f_eff")
def test_an_open_channel_beside_it_keeps_its_cmb_rate() -> None:
    from adroit.parameter_space import searches
    cls, p = _muons(1 + 1e-3)
    assert sum(core.s_wave(cls, p).values()) > 0
    assert searches.cmb(cls, p, False).excluded is True
