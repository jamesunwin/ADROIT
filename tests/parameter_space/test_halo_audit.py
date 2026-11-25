"""The audit of 2026-10-19 (the independent audit of 2026-10-19 (physics extensions)): PX-01–PX-06, each through the evaluation
path it found broken, with the numerical backends stubbed (no DIAMX)."""
import copy
import math
from types import SimpleNamespace

import pytest
import yaml

from adroit.parameter_space import dd_channels, halo_evaluation, halo_limits, halo_region, limits, searches
from adroit.parameter_space.classes import Point

XENON = "XENONnT SR0+SR1"
CRESST = halo_limits.FAST[0]
P = Point(m_chi=100.0, m_med=1000.0)
CENTRE = (233.0, 528.0, 0.4, "centre")


@pytest.fixture
def stubs(monkeypatch):
    """One module, no edge floor, no Galactic searches; the test sets what the module returns."""
    monkeypatch.setattr(limits, "edge_floor", lambda *a: None)
    monkeypatch.setattr(limits, "reference_tolerance", lambda *a: 0.0)
    monkeypatch.setattr(searches, "dm_mass", lambda cls, p: 100.0)
    monkeypatch.setattr(searches, "lines", lambda *a: None)
    monkeypatch.setattr(searches, "antiprotons", lambda *a: None)
    return monkeypatch


def _sample(sigma: float, budget: int = 0, full: bool = False):
    channels = [dd_channels.Channel(kind="SI", sigma_cm2=sigma)]
    cls = SimpleNamespace(dd=lambda p: ("SI", sigma))
    return halo_evaluation.at(cls, P, CENTRE, channels, False, False, halo_limits.Budget(budget), full)


def _count_ratio(stubs, error: float = 0.1):
    """XENONnT through a validated count ratio of error e (margin 2e), at 1e-46 cm² here."""
    stubs.setattr(limits, "eligible", lambda kind, mass, excluded=(): [XENON])
    stubs.setattr(halo_limits, "validated", lambda module, kind, mass, state=None: error)
    stubs.setattr(halo_limits, "_reference", lambda state, module, kind, mass: (1e-46, ""))
    stubs.setattr(halo_limits, "scale", lambda module, kind, mass, state: 1.0)
    stubs.setattr(halo_limits, "exact", lambda *a: 1.3e-46)


# --- PX-01: a count ratio decides a halo only if it holds at both ends of its margin --------------------------------

@pytest.mark.parametrize("sigma, excluded, unresolved", [
    (1.05e-46, None, True),          # inside the 20% margin: undecided, whatever the central value says
    (1.5e-46, True, False),          # excluded even with the limit 20% weaker
    (0.7e-46, False, False),         # not excluded even with the limit 20% stronger
])
def test_a_count_ratio_within_its_margin_decides_nothing(stubs, sigma, excluded, unresolved):
    _count_ratio(stubs)
    s = _sample(sigma)
    assert s.outcomes["direct detection"].excluded is excluded and bool(s.unresolved) is unresolved
    assert not s.outcomes["direct detection"].exact


def test_marginal_samples_never_make_a_point_excluded_throughout(stubs):
    """The audit's control: every count-ratio comparison marginal at the region's samples, the doubled samples
    clearly excluding. The point is not excluded throughout; the full calculations the budget allows decide."""
    from adroit.parameter_space.scan import PointResult
    from adroit.parameter_space.verdict import classify
    _count_ratio(stubs)
    preset = halo_region.HaloPreset()
    doubled = {(s.v0_km_s, s.v_esc_km_s) for s in halo_region.doubled(preset)}
    stubs.setattr(halo_limits, "scale", lambda module, kind, mass, state:
                  0.5 if (state.v0_km_s, state.v_esc_km_s) in doubled else 1.0)
    sigma = 1.05e-46
    cls = SimpleNamespace(dd=lambda p: ("SI", sigma))
    stubs.setattr("adroit.parameter_space.scan.dd_channels_of", lambda cls, p, kind, s:
                  [dd_channels.Channel(kind="SI", sigma_cm2=sigma)])

    def nominal():
        return PointResult(point=P, omega_h2=0.12, dd_kind="SI", dd_sigma_cm2=sigma, dd_limit_cm2=1.3e-46,
                           dd_ratio=sigma / 1.3e-46, excluded={"direct detection": False}, model_pending=[])
    r = halo_evaluation.evaluate(cls, P, preset, nominal, False)
    c = classify(cls, r)
    assert c.halo != halo_region.EXCLUDED and c.status == "pending"
    assert len(r.halo.full_calculations) == preset.full_calculations


# --- PX-02: a limit must be a number ---------------------------------------------------------------------------------

@pytest.mark.parametrize("value", [math.nan, -1e-40, 0.0, math.inf, RuntimeError("DIAMX returned nothing")])
def test_an_invalid_or_failed_limit_leaves_the_halo_unresolved(stubs, value):
    stubs.setattr(limits, "eligible", lambda kind, mass, excluded=(): [CRESST])

    def exact(*a):
        if isinstance(value, Exception):
            raise value
        return value
    stubs.setattr(halo_limits, "exact", exact)
    s = _sample(1e-50)
    assert s.unresolved and s.outcomes["direct detection"].excluded is not True
    assert "halo:" in s.unresolved[0]


def test_an_analysis_that_accepts_nothing_at_a_halo_is_insensitive_not_unresolved(stubs):
    """Zero accepted counts (the spectrum entirely below threshold at this halo) is an established infinite limit."""
    _count_ratio(stubs)
    stubs.setattr(halo_limits, "accepted", lambda *a: 0.0)
    stubs.setattr(halo_limits, "scale", lambda module, kind, mass, state: math.inf)
    s = _sample(1e-40)
    assert not s.unresolved and s.outcomes["direct detection"].excluded is not True


def test_non_finite_accepted_counts_are_an_error_not_an_infinite_limit():
    state = halo_limits.State(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=0.4)
    with pytest.MonkeyPatch.context() as m:
        m.setattr(halo_limits, "accepted", lambda module, kind, mass, v0, ve: math.nan if v0 else 1.0)
        with pytest.raises(ArithmeticError):
            halo_limits.scale(XENON, "SI", 100.0, state)


# --- PX-03: one interaction's construction never stands for another's ----------------------------------------------

def test_an_exact_sd_limit_does_not_make_the_si_count_ratio_exact(stubs):
    stubs.setattr(limits, "eligible", lambda kind, mass, excluded=(): [XENON])
    stubs.setattr(halo_limits, "validated", lambda module, kind, mass, state=None: 0.02 if kind == "SI" else None)
    stubs.setattr(halo_limits, "_reference", lambda state, module, kind, mass: (1e-46, ""))
    stubs.setattr(halo_limits, "scale", lambda *a: 1.0)
    stubs.setattr(halo_limits, "exact", lambda *a: 1e-40)
    state = halo_limits.State(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=0.4, budget=halo_limits.Budget(2),
                              defer=True)
    channels = [dd_channels.Channel(kind="SI", sigma_cm2=0.8e-46), dd_channels.Channel(kind="SD-proton",
                                                                                          sigma_cm2=1e-42)]
    with halo_limits.using(state):
        outcome, _ = halo_evaluation._dd(channels, 100.0, state)
    assert not outcome.exact
    assert state.constructions[XENON, "SI", 100.0].startswith("count ratio")
    assert state.constructions[XENON, "SD-proton", 100.0] == "its own procedure at this halo"


# --- PX-05: the budget bounds the expensive work, and charges a calculation once --------------------------------------

def test_the_same_full_calculation_is_charged_once_per_point(stubs):
    stubs.setattr(halo_limits, "validated", lambda *a, **k: None)
    stubs.setattr(halo_limits, "exact", lambda *a: 1e-46)
    budget = halo_limits.Budget(1)
    for rho in (0.2, 0.8):                                    # both ends of one velocity sample's density interval
        state = halo_limits.State(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=rho, budget=budget)
        value, _, how = halo_limits.module_limit(state, XENON, "SI", 100.0, False)
        assert value == pytest.approx(1e-46 * 0.4 / rho) and "own procedure" in how
    assert budget.remaining == 0 and len(budget.spent) == 1


def test_a_reference_limit_without_a_table_is_a_budgeted_full_calculation(stubs):
    from adroit.parameter_space import limit_tables
    calls = []
    stubs.setattr(halo_limits, "validated", lambda *a, **k: 0.05)
    stubs.setattr(halo_limits, "scale", lambda *a: 1.0)
    stubs.setattr(limit_tables, "lookup", lambda *a: None)
    stubs.setattr(limits, "reference_limit", lambda *a: calls.append(a) or (1e-46, ""))
    state = halo_limits.State(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=0.4, budget=halo_limits.Budget(0))
    value, _, how = halo_limits.module_limit(state, XENON, "SI", 100.0, False)
    assert value is None and "budget is spent" in how and not calls
    state.budget = halo_limits.Budget(1)
    value, _, how = halo_limits.module_limit(state, XENON, "SI", 100.0, False)
    assert value == pytest.approx(1e-46, rel=1e-6, abs=0) and len(calls) == 1 and state.budget.remaining == 0


# --- PX-06: a validation entry is used only if all of it holds -------------------------------------------------------

def _entry(e: float = 0.05):
    declared, sha = halo_limits.declaration()
    masses = declared["modules"][XENON]["SI"]
    halos = {"centre": (233.0, 528.0), "v0_low": (177.0903, 528.0), "v0_high": (288.9097, 528.0),
             "v_esc_low": (233.0, 444.1355), "v_esc_high": (233.0, 611.8645), "both_low": (193.4659, 468.6988),
             "both_high": (272.5341, 587.3012)}
    points = [{"halo": h, "v0_km_s": v0, "v_esc_km_s": ve, "mass_gev": m, "reference_cm2": 1e-46,
               "full_cm2": 1e-46, "ratio_cm2": 1e-46 * (1 + e), "discrepancy": e}
              for h, (v0, ve) in halos.items() for m in masses]
    return {"declared_sha256": sha, "gate_max_discrepancy": declared["gate_max_discrepancy"], "modules": {XENON: {"SI": {
        "masses_gev": [min(masses), max(masses)], "max_discrepancy": e, "passed": True, "declared_sha256": sha,
        "inputs_sha256": "inputs", "points": points}}}}


@pytest.fixture
def entry(monkeypatch):
    data = _entry()
    monkeypatch.setattr(halo_limits, "validation", lambda: data)
    monkeypatch.setattr(halo_limits, "targeted_validation", lambda: {})    # the original entry's mechanics alone
    monkeypatch.setattr(halo_limits, "inputs_sha256", lambda module: "inputs")
    halo_limits._usable_at.cache_clear()
    halo_limits._targeted_at.cache_clear()
    yield data
    halo_limits._usable_at.cache_clear()
    halo_limits._targeted_at.cache_clear()


def _state(v0: float = 233.0, ve: float = 528.0):
    return halo_limits.State(v0_km_s=v0, v_esc_km_s=ve, rho_gev_cm3=0.4)


def test_a_complete_entry_is_used_inside_the_region_it_sampled(entry):
    assert halo_limits.validated(XENON, "SI", 100.0, _state()) == pytest.approx(0.05)
    for s in halo_region.samples(halo_region.HaloPreset()) + halo_region.doubled(halo_region.HaloPreset()):
        assert halo_limits.validated(XENON, "SI", 100.0, _state(s.v0_km_s, s.v_esc_km_s)) is not None
    assert halo_limits.validated(XENON, "SI", 100.0, _state(500.0, 1000.0)) is None       # far outside
    assert halo_limits.validated(XENON, "SI", 10.0, _state()) is None                     # below its masses


@pytest.mark.parametrize("spoil", [
    lambda d: d["modules"][XENON]["SI"].update(declared_sha256="another declaration"),
    lambda d: d["modules"][XENON]["SI"].update(inputs_sha256="other inputs"),
    lambda d: d["modules"][XENON]["SI"]["points"].pop(),
    lambda d: d["modules"][XENON]["SI"]["points"][-1].update(full_cm2=math.nan),
    lambda d: d["modules"][XENON]["SI"]["points"][0].update(ratio_cm2=1.46e-46),   # e = 46% with passed: true
    lambda d: d.update(gate_max_discrepancy=0.5),
])
def test_an_entry_missing_anything_is_not_used(entry, spoil):
    spoil(entry)
    halo_limits._usable_at.cache_clear()
    assert halo_limits.validated(XENON, "SI", 100.0, _state()) is None


def test_a_non_finite_checkpoint_fails_the_summary():
    points = _entry()["modules"][XENON]["SI"]["points"]
    assert halo_limits.summarise(points, 0.15) == (pytest.approx(0.05), True)
    points = copy.deepcopy(points)
    points[-1]["full_cm2"] = math.nan
    e, passed = halo_limits.summarise(points, 0.15)
    assert math.isnan(e) and not passed


@pytest.mark.needs("diamx", "cdmslite")
def test_the_validation_file_in_the_package_is_read_as_declared():
    """Every entry the package ships is either usable or recorded as failed: none passes on its flag alone."""
    data = halo_limits.validation()
    for module, kinds in data.get("modules", {}).items():
        for kind, entry in kinds.items():
            assert (halo_limits._usable(module, kind) is not None) == bool(entry["passed"]), (module, kind)
    if halo_limits.VALIDATION.is_file():
        assert yaml.safe_load(halo_limits.VALIDATION.read_text())["declared_sha256"] == halo_limits.declaration()[1]
