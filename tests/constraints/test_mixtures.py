"""The conservative mixture rules (constraints.mixtures): their bounds, their declared proxies, and a check
against an exact convex likelihood."""

import math

import numpy as np
import pytest

from adroit.constraints import mixtures, spectra
from adroit.external.fetch import locate

ICECUBE, FERMI, PBAR = "icecube-1612.05949-sd", "fermi-1503.02641-dsph", "calore-2202.03076-pbar"
needs_pppc = pytest.mark.skipif(locate(spectra.PPPC_ITEM) is None, reason="install the optional PPPC tables")


def per(values: dict[str, float]):
    return lambda curve: values.get(curve)


ICE = per({"bb": 0.1, "WW": 0.3, "tautau": 0.6})


def test_published_channels_add_and_a_mixture_below_one_is_allowed() -> None:
    found = mixtures.bound(ICECUBE, {"b": 1.0, "W": 1.0}, 500.0, ICE)
    assert found.upper == pytest.approx(0.4) and found.lower == pytest.approx(0.3)
    assert found.excluded is False and found.ratio == pytest.approx(0.3)     # the lower bound combines (AL4-07)


def test_one_published_channel_alone_above_its_curve_excludes() -> None:
    found = mixtures.bound(ICECUBE, {"W": 4.0, "b": 1.0}, 500.0, ICE)
    assert found.lower == pytest.approx(1.2) and found.excluded is True and found.ratio == pytest.approx(1.2)


def test_bounds_that_straddle_one_leave_the_search_undecided() -> None:
    found = mixtures.bound(ICECUBE, {"W": 2.0, "Z": 1.0}, 500.0, ICE)       # Z ≤ the strongest curve (τ⁺τ⁻)
    assert found.upper == pytest.approx(1.2) and found.lower == pytest.approx(0.6)
    assert found.excluded is None and found.ratio is None and "exceeds 1" in found.why()


def test_channels_without_neutrinos_add_nothing_and_any_other_is_at_most_a_neutrino_line() -> None:
    assert mixtures.bound(ICECUBE, {"u": 5.0, "g": 5.0, "b": 1.0}, 500.0, ICE).upper == pytest.approx(0.1)
    other = mixtures.bound(ICECUBE, {"XX": 1e-3, "b": 1.0}, 500.0, ICE)
    assert other.upper == pytest.approx(0.1 + 100 * 0.6 * 1e-3) and other.excluded is False


def test_without_a_default_an_unknown_channel_leaves_no_upper_bound() -> None:
    curves = per({"mumu": 1e-4, "qq": 0.5, "bb": 0.3, "WW": 0.2, "hh": 0.25})
    unknown = mixtures.bound(PBAR, {"XX": 1.0, "b": 1.0}, 500.0, curves)
    assert unknown.upper is None and unknown.excluded is None and "XX" in unknown.why()
    assert mixtures.bound(PBAR, {"XX": 1.0, "b": 4.0}, 500.0, curves).excluded is True


def test_a_neutrino_line_is_bounded_by_a_hundred_times_the_hardest_channel() -> None:
    assert mixtures.bound(ICECUBE, {"nu": 1e-3}, 500.0, ICE).upper == pytest.approx(100 * 0.6 * 1e-3)


def test_a_curve_outside_its_mass_range_is_not_used() -> None:
    found = mixtures.bound(ICECUBE, {"W": 1.0, "Z": 1.0}, 50.0, per({"bb": 0.1, "tautau": 0.6}))
    assert not found.terms[0].own and found.terms[0].how.startswith("≤ 100")      # W falls to the default
    assert mixtures.bound(PBAR, {"tau": 1.0}, 60.0, per({"qq": 0.5})).terms[0].how == "mumu does not cover this mass"


@needs_pppc
def test_a_channel_without_a_spectrum_is_bounded_by_the_energy_budget() -> None:
    dominance = mixtures.photon_dominance(FERMI, 300.0)
    assert math.isfinite(dominance("SS", "bb")) and dominance("SS", "bb") > dominance("b", "bb")
    edges = np.geomspace(0.5, 500.0, 25)
    assert mixtures.energy_budget(300.0, edges)[0] == pytest.approx(1200.0)
    assert mixtures.energy_budget(300.0, edges)[-1] == 0.0


def test_leptons_give_no_antiprotons_below_the_w_threshold_and_twice_mumu_above() -> None:
    curves = per({"mumu": 1e-4, "qq": 0.5, "bb": 0.3, "WW": 0.2, "hh": 0.25})
    assert mixtures.bound(PBAR, {"tau": 1.0, "e": 1.0}, 30.0, curves).upper == 0.0
    assert mixtures.bound(PBAR, {"tau": 1.0}, 200.0, curves).upper == pytest.approx(2e-4)
    assert mixtures.bound(PBAR, {"tau": 1.0}, 60.0, per({"qq": 0.5})).upper is None   # μμ curve starts at 100 GeV


def test_antiproton_proxies_follow_the_declared_rules() -> None:
    curves = per({"mumu": 1e-4, "qq": 0.5, "bb": 0.3, "WW": 0.2, "hh": 0.25})
    one = lambda channel: mixtures.bound(PBAR, {channel: 1.0}, 500.0, curves).upper  # noqa: E731
    assert one("Z") == pytest.approx(1.25 * 0.2)
    assert one("Zh") == pytest.approx(0.625 * 0.2 + 0.5 * 0.25)
    assert one("t") == pytest.approx(0.3 + 0.2)
    assert one("c") == pytest.approx(0.5) and one("g") == pytest.approx(2.25 * 0.5)


def test_every_rule_names_its_reasons_and_known_curves() -> None:
    for record_id, spec in mixtures.rules().items():
        curves = set(spec["own"].values())
        for entry in spec.get("bounded", []):
            assert entry["reason"] and entry["channels"]
            by = entry["by"]
            named = set(by) if isinstance(by, dict) else {by} - {"strongest", "dominance"}
            assert named <= curves, record_id
            assert set(entry.get("among", [])) <= curves
        assert not set(spec["own"]) & set(spec.get("none", {}).get("channels", [])) or "below_gev" in spec["none"]


def test_the_scan_reads_icecubes_soft_channels_from_the_rule() -> None:
    from adroit.parameter_space import scan
    assert scan.SOFT_NEUTRINOS == frozenset(mixtures.rule(ICECUBE)["none"]["channels"])


@pytest.mark.parametrize("seed", range(5))
def test_the_bound_never_contradicts_an_exact_convex_likelihood(seed: int, monkeypatch) -> None:
    """A three-bin Gaussian likelihood (a convex χ², monotone for non-negative signal): every mixture the rule
    allows is allowed by the likelihood, and every one it excludes is excluded."""
    rng = np.random.default_rng(seed)
    yields = {name: rng.uniform(0.0, 1.0, 3) for name in ("a", "b", "c")}
    sigma, threshold = rng.uniform(0.5, 2.0, 3), 3.84

    def chi2(s: np.ndarray) -> float:
        return float(np.sum((s / sigma) ** 2))

    limit = {name: math.sqrt(threshold / chi2(y)) for name, y in yields.items()}  # rate at which χ² = 3.84
    rule = {"toy": {"own": {"a": "A", "b": "B"},
                    "bounded": [{"channels": ["c"], "by": "A", "factor": float(np.max(yields["c"] / yields["a"])),
                                 "reason": "toy dominance"}]}}
    monkeypatch.setattr(mixtures, "rules", lambda: rule)
    for _ in range(200):
        rates = dict(zip("abc", rng.uniform(0.0, 1.5, 3) * np.array([limit["a"], limit["b"], limit["c"]])))
        found = mixtures.bound("toy", rates, 1.0, per({"A": 1 / limit["a"], "B": 1 / limit["b"]}))
        excluded = chi2(sum(rate * yields[name] for name, rate in rates.items())) > threshold
        if found.excluded is not None:
            assert found.excluded == excluded


@needs_pppc
def test_light_quarks_share_one_shower_and_heavy_bosons_are_dominated_within_a_few() -> None:
    dominance = mixtures.photon_dominance(FERMI, 1000.0)
    assert dominance("d", "uu") == pytest.approx(1.0)
    assert 0.5 < dominance("Z", "WW") < 2.0
    assert dominance("t", "bb") < 2.0 and dominance("hh", "uu") < 2.0


@needs_pppc
def test_the_gamma_gamma_line_lands_in_its_bin_and_two_boson_states_need_a_heavy_mass() -> None:
    data = spectra.table()
    edges = np.geomspace(0.5, 500.0, 25)
    counts = spectra.binned(100.0, "gamma", edges, data)
    top = int(np.searchsorted(edges, 100.0)) - 1
    assert counts[top] >= 2.0 and counts.sum() == pytest.approx(2.0, abs=0.5)
    assert spectra.binned(1000.0, "gamma", edges, data).sum() < 2.0            # its line lies above 500 GeV
    with pytest.raises(spectra.SpectrumUnavailable):
        spectra.binned(200.0, "Zh", edges, data)
    nu = spectra.binned(1000.0, "nu", edges, data)
    assert (nu >= spectra.binned(1000.0, "nu_mu", edges, data)).all()


@needs_pppc
def test_the_fermi_2015_curves_decide_a_heavy_boson_mixture() -> None:
    from adroit.constraints import database
    from adroit.constraints.indirect import fermi_mixture
    curves = {k: v["limit_cm3_s"] for k, v in database.data(FERMI)["limits"].items()}
    rates = {"W": 1.1e-26, "Z": 5.4e-27, "hh": 5.4e-27, "t": 3e-29}
    found = fermi_mixture(rates, 3727.6, curves, self_conjugate=True)
    assert found.excluded is False and 0 < found.upper < 1
    assert {t.channel: t.own for t in found.terms} == {"W": True, "Z": False, "hh": False, "t": False}


def test_a_rate_that_is_not_a_number_leaves_the_mixture_undecided() -> None:
    """The audit loop's AL4-11: a NaN rate had dropped out of the mixture (it fails ``v > 0``), and the rest read
    "allowed". It is a term with no ratio now, naming its channel."""
    for bad in (math.nan, math.inf):
        found = mixtures.bound(ICECUBE, {"b": bad, "W": 1e-30}, 500.0, ICE)
        assert found.excluded is None and found.upper is None
        assert any(t.channel == "b" and "not a finite number" in t.how for t in found.terms)
    assert mixtures.bound(ICECUBE, {"b": 1e-30, "W": 1e-30}, 500.0, ICE).excluded is False   # the finite case unchanged


def test_the_dwarfs_2015_mixture_states_its_rule_when_it_decides(monkeypatch) -> None:
    """The audit loop's AL4-12: where the 2015 curves decide by the mixture rule, the outcome's ``why`` was empty."""
    from adroit.parameter_space import scan as scan_module
    decided = mixtures.MixtureBound(record_id=FERMI, upper=0.2, lower=0.1, terms=[])
    monkeypatch.setattr(scan_module, "fermi_mixture", lambda *a, **k: decided)
    monkeypatch.setattr(scan_module, "_fermi_limits", lambda: {})
    monkeypatch.setattr(scan_module.searches, "dm_mass", lambda cls, p: 100.0)
    ratio, comparison = scan_module._fermi_mixture(object(), None, {"b": 1.0}, False)
    assert ratio == decided.ratio and comparison.why == decided.why() and comparison.why
