"""R3 (audit M4): a native-CL outcome carries over to 95% where the logic of upper limits allows, so "viable" is
reachable; IceCube is pending only where it applies and cannot decide."""

import pytest

from adroit.constraints.searches import Outcome
from adroit.parameter_space.classes import Point


def test_allowed_at_a_native_90_percent_is_allowed_at_95() -> None:
    allowed = Outcome(name="x", excluded=False, ratio=0.5, confidence_level=0.9).at95()
    assert allowed.excluded is False and allowed.ratio is None and allowed.native_ratio == 0.5
    assert "hence at 95%" in allowed.why


def test_a_native_90_percent_exclusion_needs_the_source_likelihood() -> None:
    excluded = Outcome(name="x", excluded=True, ratio=2.0, confidence_level=0.9).at95()
    assert excluded.excluded is None and excluded.native_excluded is True and "source likelihood" in excluded.why


def test_bbn_at_95_4_percent_excludes_and_its_allowed_needs_the_likelihood() -> None:
    assert Outcome(name="BBN", excluded=True, confidence_level=0.954).at95().excluded is True
    assert Outcome(name="BBN", excluded=False, confidence_level=0.954).at95().excluded is None


def test_mixed_sources_carry_an_allowed_only_up_to_their_highest_cl() -> None:
    mixed = dict(name="DarkCast", confidence_level=None, highest_confidence_level=0.95)
    assert Outcome(excluded=False, **mixed).at95().excluded is False
    assert Outcome(excluded=True, **mixed).at95().excluded is None
    assert Outcome(name="u", excluded=False, confidence_level=None).at95().excluded is None


def test_the_conversion_happens_once() -> None:
    once = Outcome(name="x", excluded=False, ratio=0.5, confidence_level=0.9).at95()
    assert once.at95() == once


def test_the_lep_inert_doublet_record_states_its_cl() -> None:
    from adroit.constraints import database
    assert database.record("lep-inert-doublet").confidence_level == 0.95


class _Sun:
    """A model with chosen annihilation channels today."""

    def __init__(self, rates: dict[str, float]) -> None:
        self.rates = rates

    def sigma_v_today(self, p, v):
        return dict(self.rates)


@pytest.mark.parametrize("rates,mass,applies", [
    ({"b": 1e-26}, 100.0, True), ({"b": 1e-26}, 10.0, False),          # below IceCube's curves
    ({"u": 1e-26, "mu": 1e-26}, 100.0, False),                          # no neutrinos above threshold
    ({"b": 1e-26, "W": 1e-26}, 300.0, True), ({}, 100.0, False), ({"b": 0.0}, 100.0, False)])
def test_icecube_applies_only_with_hard_neutrinos_in_its_mass_range(rates, mass, applies) -> None:
    from adroit.parameter_space import scan
    assert scan._icecube_applies(_Sun(rates), Point(m_chi=mass, m_med=1000.0)) is applies


def test_the_dilepton_search_beyond_its_reach_leaves_no_pending() -> None:
    from adroit.parameter_space import searches
    from adroit.parameter_space.library import entry
    e = entry("b_minus_l")
    found = searches.dilepton(e.model_class, e.point.model_copy(update={"m_med": 9000.0, "m_chi": 3000.0}), True)
    assert not any(o.name == searches.DILEPTON for o in found)


@pytest.mark.parametrize("mass", [1.0, 5.0, 9.0])
def test_antiprotons_give_no_outcome_below_the_records_masses(mass: float) -> None:
    from adroit.parameter_space import searches
    assert searches.antiprotons(_Sun({"mu": 1e-26, "c": 1e-26}), Point(m_chi=mass, m_med=1000.0), True) is None


def test_antiprotons_decide_a_boson_mixture_by_the_mixture_rule() -> None:
    from adroit.parameter_space import searches
    found = searches.antiprotons(_Sun({"W": 2e-26, "Z": 1e-26, "hh": 1e-27}), Point(m_chi=1100.0, m_med=1000.0), True)
    assert found.excluded is False and 0 < found.ratio < 1 and "mixture bound" in found.why and "approximation" in found.why
    heavy = searches.antiprotons(_Sun({"W": 2e-24, "Z": 1e-26}), Point(m_chi=1100.0, m_med=1000.0), True)
    assert heavy.excluded is True


@pytest.mark.needs("solar_model")
def test_icecube_decides_a_boson_mixture_and_names_what_it_cannot_bound() -> None:
    from adroit.parameter_space import scan
    from adroit.parameter_space.library import entry
    e = entry("higgs_portal_scalar")
    p = e.point.model_copy(update={"m_chi": 3727.6, "g_chi": 1.136})
    excluded, ratio, why = scan._icecube(e.model_class, p)
    assert excluded is False and ratio is not None and ratio < 1 and "an approximation" in why   # NA15-07


@pytest.mark.slow
@pytest.mark.skipif(__import__("adroit.external.fetch", fromlist=["locate"]).locate("PPPC photon spectra") is None,
                    reason="install the optional PPPC tables")
def test_a_library_point_on_the_relic_contour_is_judged_viable(awaiting) -> None:
    """R3's end-to-end test: the scalar Higgs portal's 3.73 TeV thermal crossing (R3's acceptance), with no
    monkeypatching. Fermi's dwarfs, IceCube and AMS-02 decide its W⁺W⁻/ZZ/hh/tt̄ mixture by the conservative
    mixture rules. Under the defaults it stays pending only on records awaiting verification (R9)."""
    from adroit.parameter_space.library import entry
    from adroit.parameter_space.verdict import judge_point
    e = entry("higgs_portal_scalar")
    p = e.point.model_copy(update={"m_chi": 3727.6, "g_chi": 1.1359783199142341})
    allowed = judge_point(e.model_class, p, unverified=True)
    assert allowed.status == "viable" and not allowed.pending and not allowed.excluded_by
    from adroit.constraints import database
    awaiting(*(r.id for r in database.records()))   # R3's premise: before the signatures (R9 met it: viable)
    default = judge_point(e.model_class, p)
    assert default.status == "pending" and all("awaits a person's verification" in r for r in default.pending)
