"""The audit loop's cycle 6 (the auditor, the independent audit of 2026-11-17 (cycle6)): its three severe findings, AL6-01 to AL6-03,
at the points the auditor's controls reached them (the AL6 repair record of 2026-11-17). Offline."""
from __future__ import annotations

import numpy as np
import pytest

from adroit.constraints import relic
from adroit.constraints import searches as core

X_NODES = np.geomspace(1.0, 2e4, 140)


# --- AL6-01: the relic solve published a yield still falling at its endpoint ------------------------------------------

def _rising(n: float, scale: float = 1e-9) -> np.ndarray:
    """⟨σv⟩ in GeV⁻², constant to x = 20 and ∝ (x/20)ⁿ beyond: a rate that keeps rising as T falls (as near a narrow pole
    at the threshold) for n > 0."""
    return scale * np.maximum(X_NODES / 20.0, 1.0) ** n


def test_a_constant_rate_has_settled_by_the_endpoint() -> None:
    """The auditor's positive control: a constant ⟨σv⟩ falls by about 0.1% more from x = 10⁴ to 2 × 10⁴; it is published."""
    y = relic.freeze_out(100.0, X_NODES, _rising(0.0))
    assert 0.0 < relic.late_change(100.0, X_NODES, _rising(0.0), y, 1e4, True, None) < 2e-3


@pytest.mark.parametrize("n", [0.0, 0.5, 1.0])
def test_the_late_change_is_the_fall_of_the_yield_to_twice_the_endpoint(n) -> None:
    """``late_change`` (from ∫λ dx, the equilibrium yield negligible) against the solve itself carried to x = 2 × 10⁴."""
    here = relic.freeze_out(100.0, X_NODES, _rising(n), settled=False)
    there = relic.freeze_out(100.0, X_NODES, _rising(n), x_end=2e4, settled=False)
    late = relic.late_change(100.0, X_NODES, _rising(n), here, 1e4, True, None)
    assert late == pytest.approx(1.0 - there / here, rel=0.02)


def test_a_rate_still_rising_at_the_endpoint_is_not_published() -> None:
    """∝ x beyond x = 20: the yield still falls by more than 5% from x = 10⁴ to 2 × 10⁴. Refused with the reason, never
    the yield at 10⁴; an estimate that is not published (``settled=False``) still gets it."""
    with pytest.raises(relic.RelicUnresolved, match=r"annihilation has not stopped by x = m/T = 10000"):
        relic.freeze_out(100.0, X_NODES, _rising(1.0))
    assert relic.freeze_out(100.0, X_NODES, _rising(1.0), settled=False) > 0.0


def test_the_late_tolerance_is_half_the_relic_theory_uncertainty() -> None:
    from adroit.parameter_space.likelihood import LikelihoodSettings
    assert relic.LATE_TOLERANCE == 0.5 * LikelihoodSettings().relic_theory == 0.05


@pytest.mark.needs("ufo_models")
def test_the_2hdma_thermal_root_at_its_threshold_pole_is_pending() -> None:
    """The auditor's point (m_χ = 100, m_a = 200 GeV, g_q = 0.001, g_χ = 0.0594782751231143): Ωh² 0.1200 at x = 10⁴, 0.0926 at
    2 × 10⁴. The scan's relic is pending with the reason, not the number."""
    from adroit.parameter_space import library, scan
    from adroit.parameter_space.portals import ufo
    entry = library.entry("two_hdm_a")
    p = entry.point.model_copy(update={"m_chi": 100.0, "m_med": 200.0, "g_q": 0.001, "g_chi": 0.0594782751231143})
    ufo._SIGMA.clear()
    omega, why = scan._relic_at(entry.model_class, p)
    ufo._SIGMA.clear()
    assert omega is None and "annihilation has not stopped" in why


def test_the_analytic_alp_at_its_threshold_pole_is_pending() -> None:
    """The auditor's analytic control, no UFO table: the ALP portal at m_a = 2m_χ = 200 GeV, g_q = g_ℓ = 0.01, at its thermal
    root (g_χ = 0.018842515125060254): Ωh² 0.1526, 0.1200 and 0.0928 at x = 5000, 10⁴ and 2 × 10⁴."""
    from adroit.parameter_space import library
    entry = library.entry("alp_portal")
    p = entry.point.model_copy(update={"m_chi": 100.0, "m_med": 200.0, "g_chi": 0.018842515125060254, "g_q": 0.01,
                                       "g_l": 0.01})
    with pytest.raises(relic.RelicUnresolved, match="annihilation has not stopped"):
        entry.model_class.omega_h2(p)


# --- AL6-02: the CMB's rate from two speeds near a narrow pole ---------------------------------------------------------

def _alp(**update):
    from adroit.parameter_space import library
    entry = library.entry("alp_portal")
    base = {"m_chi": 100.0, "m_med": 200.0, "g_chi": 0.001, "g_q": 0.01, "g_l": 0.01}
    return entry.model_class, entry.point.model_copy(update={**base, **update})


@pytest.mark.needs("f_eff")
@pytest.mark.parametrize(("m_med", "plateau"), [(200.0, 5.99e-20), (200.0 * (1 + 1e-7), None), (200.0 * (1 - 1e-7), None)])
def test_the_cmb_reads_the_low_speed_plateau_near_a_threshold_pole(m_med, plateau) -> None:
    """The auditor's ALP (m_χ = 100 GeV, g_χ = 0.001, g_q = g_ℓ = 0.01): a + b v² gave 4.8 × 10⁻²⁶ cm³/s and allowed (0.153);
    σv flattens out at 6.0 × 10⁻²⁰ below v = 10⁻⁵, which Planck excludes. Detuned by ±10⁻⁷ the same."""
    from adroit.parameter_space import searches
    cls, p = _alp(m_med=m_med)
    rates = core.s_wave(cls, p)
    low = sum(cls.sigma_v_today(p, 1e-6).values())
    assert sum(rates.values()) == pytest.approx(low, rel=0.01)
    if plateau is not None:
        assert sum(rates.values()) == pytest.approx(plateau, rel=0.01)
    assert searches.cmb(cls, p, False).excluded is True


@pytest.mark.needs("f_eff")
def test_a_narrower_coupling_reaches_its_plateau_lower_down() -> None:
    """g_q = 0.001, g_χ = 10⁻⁶: σv rises as v⁻⁴ to v = 10⁻⁴ and flattens between 3 × 10⁻⁶ and 10⁻⁶ (production had
    left the CMB out, its rate below the reach; excluded at the plateau)."""
    from adroit.parameter_space import searches
    cls, p = _alp(g_chi=1e-6, g_q=0.001, g_l=0.001)
    assert sum(core.s_wave(cls, p).values()) == pytest.approx(sum(cls.sigma_v_today(p, 1e-6).values()), rel=0.01)
    assert searches.cmb(cls, p, False).excluded is True


@pytest.mark.parametrize("m_med", [600.0, 50.0])
def test_a_rate_that_obeys_a_plus_b_v_squared_is_unchanged(m_med) -> None:
    """A pole far from the threshold (m_a = 600 or 50 GeV): the check at v = 10⁻³ holds, and the rate is the two speeds'
    a, as before."""
    cls, p = _alp(m_med=m_med, g_chi=0.5, g_q=1.0, g_l=1.0)
    fast, slow = (cls.sigma_v_today(p, v) for v in core.CMB_SPEEDS)
    expected = {k: (4.0 * slow[k] - fast[k]) / 3.0 for k in fast if (4.0 * slow[k] - fast[k]) / 3.0 > 1e-3 * fast[k]}
    assert core.s_wave(cls, p) == pytest.approx(expected, rel=1e-12)


def test_a_wider_pole_at_the_threshold_takes_its_plateau_too() -> None:
    """g_χ = 0.5, g_q = g_ℓ = 1 at m_a = 2m_χ: a + b v² was 4.8% above σv at v = 10⁻³ (it misses the v⁴ terms there);
    the rate is now σv's plateau, 1.497 × 10⁻¹⁸ cm³/s."""
    cls, p = _alp(g_chi=0.5, g_q=1.0, g_l=1.0)
    assert sum(core.s_wave(cls, p).values()) == pytest.approx(sum(cls.sigma_v_today(p, 1e-4).values()), rel=0.01)


class _Rising:
    """σv ∝ v⁻² down to ``floor`` and zero below it (a tree route's amplitudes vanish within 10⁻¹² of threshold)."""

    def __init__(self, floor: float = 0.0) -> None:
        self.floor = floor

    def sigma_v_today(self, p, v: float) -> dict[str, float]:
        return {"b": 1e-26 / v ** 2 if v > self.floor else 0.0}


@pytest.mark.parametrize("floor", [0.0, 2.83e-6])
def test_a_rate_that_has_not_flattened_is_not_computed(floor) -> None:
    """No plateau by v = 10⁻⁶, or the descent reaching a tree floor's zero: CMBUnresolved, never the floor's zero or
    the two speeds' extrapolation."""
    with pytest.raises(core.CMBUnresolved, match="has not flattened out"):
        core.s_wave(_Rising(floor), None)


def test_an_unresolved_rate_leaves_the_cmb_undecided(monkeypatch) -> None:
    from adroit.parameter_space import searches
    cls, p = _alp()

    def unresolved(*_):
        raise core.CMBUnresolved("σv near v = 0 is not resolved: test")
    monkeypatch.setattr(core, "s_wave", unresolved)
    found = searches.cmb(cls, p, False)
    assert found.excluded is None and "not resolved" in found.why


# --- AL6-03: the generic route and the amplitudes' floor ---------------------------------------------------------------

def _generic(y: float):
    """The auditor's typed model: a Dirac χ (100 GeV), a pseudoscalar a (200 GeV) coupled to χ (0.1) and to muons (y)."""
    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space.portals import generic
    terms = [dict(fields=[dict(field=f, conjugate=True), dict(field=f), dict(field="a")], lorentz="pseudoscalar",
                  coupling=c, text=f"{c} a {f}bar gamma5 {f}") for f, c in (("chi", "g"), ("mu", "y"))]
    spec = ModelSpec.model_validate(dict(
        name="threshold_muon_pseudoscalar", phase="broken", stability="Z2",
        fields=[dict(name="chi", role="dark_matter", spin=0.5, mass_gev=100.0, dark_parity=-1),
                dict(name="a", role="mediator", spin=0, self_conjugate=True, mass_gev=200.0, dark_parity=1),
                dict(name="mu", role="standard_model", spin=0.5, mass_gev=0.105658, charges={"electric_charge": -1})],
        couplings=[dict(name="g", value=0.1), dict(name="y", value=y)], terms=terms))
    engine = generic.GenericModel.of(spec)
    return engine, engine.point()


@pytest.mark.parametrize("y", [6e-6, 1e-5])
def test_the_generic_route_refuses_a_pole_its_amplitudes_do_not_resolve(y) -> None:
    """Γ/M = 1.4 × 10⁻¹² (y = 6 × 10⁻⁶) and 4.0 × 10⁻¹² (10⁻⁵), above the old floor of 10⁻¹²: their thermal rate was
    0.67 and Ωh² 1.49 times its resolved value at the thermal root (10.9% at 10⁻⁵). Refused as the UFO route refuses
    them."""
    engine, p = _generic(y)
    assert "closer than the tree amplitudes resolve" in engine.domain(p)


def test_the_generic_route_keeps_a_pole_its_amplitudes_resolve() -> None:
    """y = 10⁻⁴ (Γ/M = 4.0 × 10⁻¹⁰, a threshold scale of 2 × 10⁻¹⁰): within 0.24% of the resolved rate; not refused for
    resolution."""
    engine, p = _generic(1e-4)
    assert "closer than the tree amplitudes resolve" not in engine.domain(p)


@pytest.mark.parametrize(("y", "refused"), [(6e-6, True), (1e-4, False)])
def test_a_coannihilating_pairs_threshold_pole_is_refused_too(y, refused) -> None:
    """A partner ψ (102 GeV) joined to χ (100 GeV) by a pseudoscalar of 202 GeV, at the χ ψ threshold (the χ χ̄
    threshold is 1% below it). At y = 6 × 10⁻⁶ (Γ = 2.9 × 10⁻¹⁰ GeV, a threshold scale of 7 × 10⁻¹³) the criterion
    refuses the pair's pole; at 10⁻⁴ (2 × 10⁻¹⁰) it does not. (``domain`` gives this model's thermal-history reason
    first: ψ converts too slowly; the criterion is read directly.)"""
    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space.portals import generic
    terms = [dict(fields=[dict(field="chi", conjugate=True), dict(field="psi"), dict(field="a")], lorentz="pseudoscalar",
                  coupling="g", text="g a chibar gamma5 psi + h.c."),
             dict(fields=[dict(field="mu", conjugate=True), dict(field="mu"), dict(field="a")], lorentz="pseudoscalar",
                  coupling="y", text="y a mubar gamma5 mu")]
    spec = ModelSpec.model_validate(dict(
        name="coannihilating_threshold", phase="broken", stability="Z2",
        fields=[dict(name="chi", role="dark_matter", spin=0.5, mass_gev=100.0, dark_parity=-1),
                dict(name="psi", role="other", spin=0.5, mass_gev=102.0, dark_parity=-1),
                dict(name="a", role="mediator", spin=0, self_conjugate=True, mass_gev=202.0, dark_parity=1),
                dict(name="mu", role="standard_model", spin=0.5, mass_gev=0.105658, charges={"electric_charge": -1})],
        couplings=[dict(name="g", value=0.1), dict(name="y", value=y)], terms=terms))
    engine = generic.GenericModel.of(spec)
    why = generic._unresolved_pole(*engine.at(engine.point()))
    assert ("threshold at 202 GeV" in why and "closer than the tree amplitudes resolve" in why) is refused
    assert refused or why == ""


def test_the_generic_and_ufo_routes_share_one_criterion() -> None:
    from adroit.parameter_space.portals import ufo
    assert ufo.SCALE_RESOLVED == 2e-11
    assert ufo.threshold_scale(200.0, 200.0, 2 * 200.0 * 1.9e-11) < ufo.SCALE_RESOLVED
    assert ufo.threshold_scale(200.0, 200.0, 2 * 200.0 * 2.1e-11) > ufo.SCALE_RESOLVED
