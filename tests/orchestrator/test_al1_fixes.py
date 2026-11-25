"""The audit loop's first cycle (audit/claude_audit_2026-11-14_cycle1.md), its sixteen findings repaired.

- AL1-01: a channel whose prediction is not computable never enters the combined likelihood (``Outcome.combinable``).
- AL1-02: the one-event closed form only where one event was observed and can reach the observed maximum; 0σ is p = 1.
- AL1-03: the Yellin method a module uses, and the optimum interval's driver, among its inputs (``limit_tables``).
- AL1-04: a model's own "direct detection: … not computed" kept over the halo region.
- AL1-05: a stored table among its module's inputs; a limit and its tolerance of one reading.
- AL1-06: a single-kind comparison tests every module's tolerance.
- AL1-07: a thermal claim on an unverified relic target pending (or naming it); LHCb's theory inputs gated.
- AL1-08: a signature bound to nothing is not usable.
- AL1-09: a verifier's name written as a string, the records file read back before it is published.
- AL1-10: a provider's unbilled refusal settled at $0.
- AL1-11: a halo sample straddling at the strong end of a count ratio's margin is undecided.
- AL1-12: the tables' tolerance at or above the misses measured against direct DIAMX limits.
- AL1-13: a single-kind factor whose inputs keep changing leaves its module without a limit, with the reason.
- AL1-14: an unloadable tabulated module gives no limit with the reason; ``--masses`` gives a message.
- AL1-16: the tests fenced from the network (``tests/conftest.py``).

Synthetic limits, stand-in modules and temporary copies of the records; no detector calculation but where marked.
"""
from __future__ import annotations

import math
import socket
from types import SimpleNamespace

import numpy as np
import pytest
import typer
import yaml

from adroit.constraints import database, review
from adroit.constraints.review_identity import signature_status
from adroit.experiments import registry
from adroit.experiments.base import DataUnavailable
from adroit.inference import look_elsewhere
from adroit.orchestrator import cli, signal
from adroit.parameter_space import (dd_channels, halo_evaluation, halo_limits, halo_region, limit_tables, limits,
                                    searches)
from tests.orchestrator.test_dy_fixes import _compare, detector  # noqa: F401  (the DY round's stand-in DIAMX)

LZ, PICO = "LZ WS2022+WS2024", "PICO-60 C3F8 (2019)"


# --- AL1-02 ----------------------------------------------------------------------------------------------------

class _Window:
    """A 0–100 keV search with a fixed background expecting ``expected`` events, the events given, no resolution."""

    def __init__(self, events: list[float], expected: float) -> None:
        self.grid = np.linspace(0.0, 100.0, 401)
        self.events = np.asarray(events, dtype=float)
        self.background = np.full(self.grid.size, expected / 100.0)

    def resolution_on_grid(self) -> np.ndarray:
        return np.zeros(self.grid.size)

    def background_on_grid(self) -> np.ndarray:
        return self.background

    def background_rate(self) -> None:
        return None

    def observations(self) -> tuple[np.ndarray, np.ndarray]:
        return self.events, np.zeros(self.events.size)


def _narrow(grid: np.ndarray) -> np.ndarray:
    shape = np.exp(-0.5 * ((grid - 50.0) / 2.0) ** 2)
    return np.array([shape / np.trapezoid(shape, grid)])


def test_a_largest_local_significance_of_zero_is_p_one() -> None:
    """The audit's case: one event where no candidate predicts anything, a fixed background of 0.001 events. Every
    outcome reaches 0σ, the empty one included: p = 1, Z = 0 (the closed form had given 1 − e^(−B), Z ≈ 3.1)."""
    window = _Window([90.0], 0.001)
    p_toys, p_closed, z, method = signal._toy_significance(window, _narrow(window.grid), window.grid, 0.0, 2000)
    assert (p_toys, p_closed, z) == (1.0, None, 0.0) and "0σ" in method
    assert look_elsewhere.one_event_p_value(0.0, _narrow(window.grid), window.grid, window.background) == 1.0


def test_two_observed_events_are_judged_by_the_toys_and_never_infinite() -> None:
    """Two events on a fixed background of 0.09: no single event reaches their maximum, so the one-event form (p = 0,
    Z = ∞) does not hold; the toys decide, and Z is finite."""
    window = _Window([50.0, 50.4], 0.09)
    shapes = _narrow(window.grid)
    z_max = look_elsewhere.max_significance(shapes, window.grid, window.events, window.background)
    p_toys, p_closed, z, method = signal._toy_significance(window, shapes, window.grid, z_max, 20_000)
    assert z_max > 3.0 and p_closed is None and math.isfinite(z) and "toys" in method
    assert z == pytest.approx(look_elsewhere.p_to_z(p_toys)) if p_toys > 0 else z > 3.0


def test_two_observed_events_are_judged_by_the_toys_where_one_event_could_reach_their_maximum() -> None:
    """Two events, one far from where any candidate predicts: one event alone reaches about their maximum, so the
    one-event form would give a number, but it counts no outcome with two events: the toys decide."""
    window = _Window([50.0, 90.0], 0.09)
    shapes = _narrow(window.grid)
    z_max = look_elsewhere.max_significance(shapes, window.grid, window.events, window.background)
    assert 0.0 < look_elsewhere.one_event_p_value(z_max - 1e-9, shapes, window.grid, window.background) < 1.0
    p_toys, p_closed, z, method = signal._toy_significance(window, shapes, window.grid, z_max, 20_000)
    assert p_closed is None and "toys" in method and math.isfinite(z)


def test_one_observed_event_keeps_the_closed_form() -> None:
    """Off the shape's peak, where one event alone reaches the maximum (p ≈ 4 × 10⁻⁵, two events 5 × 10⁻⁷): at the
    peak itself a single event reaches it on a set of no measure (p ≈ 10⁻¹²), and the toys decide (AL3-06)."""
    window = _Window([52.0], 0.001)
    shapes = _narrow(window.grid)
    z_max = look_elsewhere.max_significance(shapes, window.grid, window.events, window.background)
    p_toys, p_closed, z, method = signal._toy_significance(window, shapes, window.grid, z_max, 2000)
    assert 0.0 < p_closed < 1.0 and z == pytest.approx(look_elsewhere.p_to_z(p_closed))
    assert method.startswith("one-event closed form")


# --- AL1-01 ----------------------------------------------------------------------------------------------------

def test_a_channel_not_computable_never_enters_the_combination() -> None:
    from adroit.parameter_space.scan import PointResult
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.likelihood import LikelihoodSettings
    from adroit.parameter_space.verdict import classify
    unreliable = dd_channels.ChannelOutcome(kind="SI", sigma_cm2=1e-40, ratio=1.8e11, unreliable="on shell")
    computable = dd_channels.ChannelOutcome(kind="SD-proton", sigma_cm2=1e-40, ratio=0.4, ratio_band=(0.3, 0.5))
    assert dd_channels.Outcome(channels=[unreliable], excluded=None, pending=[]).combinable is None
    assert dd_channels.Outcome(channels=[unreliable, computable], excluded=None, pending=[]).combinable == 0.3
    reason = "direct detection (SI): not computed here: on shell"
    row = PointResult(point=Point(m_chi=200.0, m_med=200.5, g_chi=1.0), omega_h2=0.12, dd_kind="SI",
                      dd_sigma_cm2=1e-40, dd_limit_cm2=1e-51, excluded={"direct detection": None}, pending=[reason],
                      model_pending=[], ratios={})
    combined = classify(None, row, LikelihoodSettings())
    assert combined.status == "pending" and reason in combined.pending and not combined.excluded_by


def test_a_halo_samples_ratio_is_never_a_channel_not_computable(monkeypatch) -> None:
    unreliable = dd_channels.ChannelOutcome(kind="SI", sigma_cm2=1e-40, ratio=1.8e11, unreliable="on shell")
    monkeypatch.setattr(dd_channels, "compare", lambda channels, mass, *a: dd_channels.Outcome(
        channels=[unreliable], excluded=None, pending=["direct detection (SI): not computed here: on shell"]))
    state = halo_limits.State(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=0.4, defer=True)
    channel = dd_channels.Channel(kind="SI", sigma_cm2=1e-40, unreliable="on shell")
    found, pending = halo_evaluation._dd([channel], 200.0, state)
    assert found.ratio is None and found.excluded is None and pending


# --- AL1-03 ----------------------------------------------------------------------------------------------------

class _Interval:
    """A module whose limits use Yellin's code, its method declared as ``interval_method`` gives it now."""
    folder = None

    @property
    def info(self):
        from adroit.experiments.base import interval_method
        return SimpleNamespace(statistical_method=interval_method())


def test_the_yellin_method_and_its_driver_are_among_a_modules_inputs(tmp_path, monkeypatch) -> None:
    from adroit.statistics import optimum_interval
    there = {"now": False}
    monkeypatch.setattr(optimum_interval, "available", lambda: there["now"])
    monkeypatch.setattr(optimum_interval, "code_folder", lambda: tmp_path)
    monkeypatch.setattr(registry, "load_module", lambda name: _Interval())
    limits.clear_cache()
    gap = limit_tables.inputs("an interval search")
    gap_print = limit_tables._digest("an interval search", limit_tables._content)
    there["now"] = True                                       # the optimum interval installed under a warm process
    optimum = limit_tables.inputs("an interval search")
    assert optimum != gap
    assert limit_tables._digest("an interval search", limit_tables._content) != gap_print
    (tmp_path / optimum_interval.EXECUTABLE).write_text("rebuilt")       # its driver rebuilt: another version
    assert limit_tables.inputs("an interval search") not in (gap, optimum)
    limits.clear_cache()


@pytest.mark.needs("cresst", "optimum_interval")
def test_a_warm_limit_follows_the_optimum_interval_installed(monkeypatch) -> None:
    """The audit's dy01_yellin on CRESST-III at 0.5 GeV: taken by the maximum gap (flagged: it excludes only), then the
    optimum interval made available without clearing anything: the limit is the optimum interval's, as a fresh
    process gives it, and no longer flagged."""
    from adroit.statistics import optimum_interval
    cresst = "CRESST-III 2019"
    real = optimum_interval.available
    monkeypatch.setattr(optimum_interval, "available", lambda: False)
    limits.clear_cache()
    gap, _ = limits.reference_limit(cresst, "SI", 0.5, False)
    assert limits.fallback(cresst) == limits.MAXIMUM_GAP_FALLBACK
    monkeypatch.setattr(optimum_interval, "available", real)
    warm, _ = limits.reference_limit(cresst, "SI", 0.5, False)
    limits.clear_cache()
    fresh, _ = limits.reference_limit(cresst, "SI", 0.5, False)
    assert warm == pytest.approx(fresh, rel=1e-9, abs=0) and warm < gap and limits.fallback(cresst) == ""


# --- AL1-04 ----------------------------------------------------------------------------------------------------

CAVEAT = ("direct detection: the Dirac χ's magnetic-dipole scattering (1/q², O₄–O₆) and anapole are not computed; "
          "the charge radius alone is a lower bound")


def test_a_models_own_direct_detection_caveat_is_kept_over_the_halo_region() -> None:
    """The audit's DD-1: allowed at every sample, the model's own caveat its only pending reason: pending, with it."""
    from adroit.parameter_space.verdict import classify
    from tests.parameter_space.test_halo_region import _point, _sample
    row = _point([_sample(False), _sample(False, rho=1.0)], pending=[CAVEAT], nominal_pending=[CAVEAT])
    region = classify(None, row.model_copy(update={"model_pending": [CAVEAT]}))
    assert region.status == "pending" and CAVEAT in region.pending and region.halo != halo_region.ALLOWED
    sampled = "direct detection (LZ WS2022+WS2024): halo: no limit"
    assert halo_evaluation.recomputed([CAVEAT, sampled, "colliders (CMS): x"], [CAVEAT], True) == [sampled]
    assert halo_evaluation.recomputed([sampled], [], False) == []      # no channel a sample compares


# --- AL1-05 ----------------------------------------------------------------------------------------------------

def _table(detector, value: float, accuracy: float) -> None:  # noqa: F811
    search = detector.module.search
    (limit_tables.TABLES / f"{limit_tables.slug(search, 'SI')}.yaml").write_text(yaml.safe_dump(dict(
        module=search, kind="SI", fingerprint=limit_tables.fingerprint(search), masses_gev=[1.0, 100.0],
        limits_cm2=[value, value], interpolation_accuracy=accuracy)))


def _at(sigma: float):
    return dd_channels.compare([dd_channels.Channel(kind="SI", sigma_cm2=sigma)], 10.0)


def test_a_stored_table_replaced_alone_is_followed(detector) -> None:  # noqa: F811
    """The table (3e-45, η 1%) excludes 4e-45; replaced by a current one of 5e-45 (η 4%), nothing cleared: the next
    comparison takes 5e-45 and its tolerance, as an uncached one does."""
    assert _compare().excluded
    _table(detector, 5e-45, 0.02)
    warm = _compare()
    assert not warm.excluded and warm.channels[0].limit.value == pytest.approx(5e-45, rel=1e-9, abs=0)
    assert limits.tolerance(detector.module.search, "SI", 10.0) == pytest.approx(0.04)
    assert "±4.0%" in warm.channels[0].limit.construction


def test_a_stored_table_removed_or_written_alone_is_followed(detector) -> None:  # noqa: F811
    search = detector.module.search
    table = limit_tables.TABLES / f"{limit_tables.slug(search, 'SI')}.yaml"
    _table(detector, 2e-45, 0.001)
    assert _at(2.5e-45).excluded                                       # by the table
    table.unlink()
    removed = _at(2.5e-45)                                             # the module's own, 3e-45
    assert not removed.excluded and removed.channels[0].limit.value == pytest.approx(3e-45, rel=1e-9, abs=0)
    assert "interpolated" not in removed.channels[0].limit.construction
    assert limits.tolerance(search, "SI", 10.0) == 0.0
    assert _compare().excluded                                         # 4e-45 against the module's own 3e-45
    _table(detector, 5e-45, 0.001)
    written = _compare()
    assert not written.excluded and "interpolated" in written.channels[0].limit.construction


def test_a_limit_and_its_tolerance_are_of_one_reading(detector) -> None:  # noqa: F811
    """Inside one reading the limit kept and its tolerance are those of the table it was taken from, though the
    table is replaced meanwhile; the next reading takes the new one's."""
    search = detector.module.search
    with limit_tables.reading():
        value, _ = limits.reference_limit(search, "SI", 10.0, True)
        _table(detector, 5e-45, 0.02)
        assert limits.reference_tolerance(search, "SI", 10.0) == pytest.approx(0.01)
    assert value == pytest.approx(3e-45, rel=1e-9, abs=0)
    assert limits.reference_tolerance(search, "SI", 10.0) == pytest.approx(0.04)
    assert limits.reference_limit(search, "SI", 10.0, True)[0] == pytest.approx(5e-45, rel=1e-9, abs=0)


# --- AL1-06 ----------------------------------------------------------------------------------------------------

def test_a_weaker_tabulated_modules_tolerance_is_tested(monkeypatch) -> None:
    """The audit's DD-3: A direct at 1.0e-39; B tabulated at 1.1e-39 with η 50%, its direct limit 0.8e-39; σ =
    0.9e-39 lies within B's tolerance, so the comparison is recomputed directly, and B excludes, as directly."""
    a, b = "CRESST-III 2019", "CDMSlite Run 2"

    def per_module95(kind, mass, excluded=()):
        return ((a, 1.0e-39), (b, 0.8e-39 if limits.exact_requested() else 1.1e-39)), ()
    monkeypatch.setattr(limits, "per_module95", per_module95)
    monkeypatch.setattr(limits, "tolerance", lambda m, k, x: 0.0 if limits.exact_requested() else {b: 0.5}.get(m, 0.0))
    limits.clear_cache()
    channel = [dd_channels.Channel(kind="SI", sigma_cm2=0.9e-39)]
    tabulated = dd_channels.compare(channel, 1.7)
    with limits.exact():
        direct = dd_channels.compare(channel, 1.7)
    assert direct.excluded is True and tabulated.excluded is True
    assert tabulated.channels[0].limit.source == b
    limits.clear_cache()


# --- AL1-07 ----------------------------------------------------------------------------------------------------

def _thermal_claim(monkeypatch, usable: bool, enabled: bool):
    from adroit.core.certificate import Check
    from adroit.parameter_space import certification, likelihood
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.verdict import Crossing
    monkeypatch.setattr(likelihood, "DENSITY_USABLE", usable)
    c = Crossing(point=Point(m_chi=100.0, m_med=1000.0), status="viable")
    return certification.certify(c, "thermal_solution", "a root", [Check(name="root", state="satisfied")],
                                 enabled=enabled).certificate


def test_a_thermal_claim_on_an_unverified_relic_target_is_pending_or_names_it(monkeypatch) -> None:
    from adroit.constraints.planck import ID
    assert _thermal_claim(monkeypatch, True, False).check("relic target") is None
    waiting = _thermal_claim(monkeypatch, False, False)
    assert waiting.check("relic target").state == "failed" and ID in waiting.check("relic target").reason
    assert not waiting.decided
    enabled = _thermal_claim(monkeypatch, False, True)
    assert enabled.check("relic target") is None and ID in enabled.bound.unverified_records
    assert f"depends on unverified records: {ID}" in enabled.qualifiers


def test_lhcbs_theory_inputs_are_gated_by_their_own_record(awaiting) -> None:
    args = (0.30, 1.0, 1.0, searches.HBAR_GEV_PS / 10.0)
    assert searches._lhcb_mumu(*args, False).excluded is not None          # both records signed: decided
    awaiting("flavour-b-to-k-invisible")
    gated = searches._lhcb_mumu(*args, False)
    assert gated.excluded is None and "flavour-b-to-k-invisible" in gated.why
    assert searches._lhcb_mumu(*args, True).excluded is not None


# --- AL1-08 and AL1-09 -----------------------------------------------------------------------------------------

def test_a_signature_bound_to_nothing_is_not_usable() -> None:
    record = database.record("lep-contact-bl").model_copy(update={"verification_sha256": ""})
    status = signature_status(record)
    assert status.state == "legacy_unbound" and not status.usable


@pytest.mark.parametrize("name", ["No", "NO", "On", "123", "1.5", "Null", "J. Unwin", "Ünwin, J."])
def test_any_verifiers_name_is_written_as_given_and_the_records_still_load(awaiting, name) -> None:
    awaiting("lep-contact-bl")
    assert not database.record("lep-contact-bl").usable
    review.verify("lep-contact-bl", name)
    database.records.cache_clear()
    record = database.record("lep-contact-bl")
    assert record.verified_by == name and record.usable and len(database.records()) >= 48


def test_a_signature_that_would_not_read_back_is_refused_and_nothing_written(awaiting, monkeypatch) -> None:
    awaiting("lep-contact-bl")
    before = database.RECORDS.read_bytes()

    def unreadable(*args):
        raise ValueError("unreadable")
    monkeypatch.setattr(review, "_signed_as_written", unreadable)
    with pytest.raises(ValueError, match="unreadable"):
        review.verify("lep-contact-bl", "No")
    assert database.RECORDS.read_bytes() == before


# --- AL1-10 ----------------------------------------------------------------------------------------------------

class _Refused(Exception):
    """A provider's refusal before any generation (as the SDKs' APIStatusError carries it)."""
    status_code = 401


def test_a_refusal_the_provider_does_not_bill_releases_its_reservation(tmp_path) -> None:
    from tests.agents.test_budget_reservations import ask, client
    replies = iter([_Refused("SIMULATED 401"), _Refused("SIMULATED 401"), None])

    def send(**kw):
        error = next(replies)
        if error is not None:
            raise error
        return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"value":4}')],
                               usage=SimpleNamespace(input_tokens=100, output_tokens=20))
    llm, calls = client(tmp_path, send=send, cap=0.05)
    for _ in range(2):
        with pytest.raises(_Refused):
            ask(llm)
        assert not llm.account.reservations and llm.account.committed() == 0.0
    assert ask(llm).value == 4 and len(calls) == 3
    assert llm.account.committed() == pytest.approx(0.0008)
    states = [(e["state"], e.get("refused")) for e in map(__import__("json").loads,
                                                            llm.ledger_path.read_text().splitlines())]
    assert states[:4] == [("reserved", None), ("settled", 401), ("reserved", None), ("settled", 401)]


@pytest.mark.parametrize("status", [500, 529, 408])
def test_a_refusal_whose_bill_is_not_known_keeps_its_reservation(tmp_path, status) -> None:
    from tests.agents.test_budget_reservations import ask, client
    error = type("Degraded", (Exception,), {"status_code": status})

    def send(**kw):
        raise error("SIMULATED")
    llm, _ = client(tmp_path, send=send, cap=0.05)
    with pytest.raises(error):
        ask(llm)
    assert len(llm.account.reservations) == 1


# --- AL1-11 ----------------------------------------------------------------------------------------------------

def test_a_straddle_at_the_strong_end_of_a_count_ratios_margin_is_undecided(monkeypatch) -> None:
    """The audit's DD-4: a count-ratio limit with an 11% margin, a channel with a 10% amplitude uncertainty, allowed
    at the margin's weak end and straddling at its strong end: undecided, the comparison left fragile."""
    monkeypatch.setattr(halo_limits, "validated", lambda *a, **k: 0.05)
    monkeypatch.setattr(halo_limits, "scale", lambda *a: 1.0)
    monkeypatch.setattr(halo_limits, "_reference", lambda *a: (1e-46, ""))
    monkeypatch.setattr(limits, "reference_tolerance", lambda *a: 0.01)
    monkeypatch.setattr(limits, "eligible", lambda *a, **k: ["XENONnT SR0+SR1"])
    monkeypatch.setattr(limits, "fallback", lambda name: "")
    limits.clear_cache()
    state = halo_limits.State(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=0.4, defer=True)
    channel = [dd_channels.Channel(kind="SI", sigma_cm2=0.95e-46 / 1.21, amplitude_uncertainty=0.1)]
    with halo_limits.using(state):
        found, _ = halo_evaluation._dd(channel, 100.0, state)
        assert found.excluded is None and state.fragile
        state.bias = -1
        assert dd_channels.compare(channel, 100.0).excluded is None      # straddling at the strong end
    limits.clear_cache()


# --- AL1-12 ----------------------------------------------------------------------------------------------------

# Direct single-mass DIAMX limits against the stored SI tables (the audit's table_spots.json and the coder's
# real_diamx/against_the_table.txt, 2026-11-13/14): (search, mass in GeV, direct/table − 1)
SPOTS = [(LZ, 30.4997, 0.000182), (LZ, 45.0456, 0.001954), ("XENONnT SR0+SR1", 813.3106, 0.003366),
         ("XENONnT SR0+SR1", 408.4239, -0.002542), ("PandaX-4T Run0+Run1", 418.0933, -0.006745),
         ("PandaX-4T Run0+Run1", 1471.409, 0.001294), ("PandaX-4T Run0+Run1", 150.5, -0.0007),
         ("PandaX-4T Run0+Run1", 260.3, 0.0168), ("PandaX-4T Run0+Run1", 410.7, -0.0091)]


@pytest.mark.parametrize("search, mass, miss", SPOTS)
def test_every_measured_miss_of_a_table_is_within_its_tolerance(search, mass, miss) -> None:
    data = yaml.safe_load((limit_tables.TABLES / f"{limit_tables.slug(search, 'SI')}.yaml").read_text())
    assert abs(miss) <= limit_tables.tolerance(data, mass)


# --- AL1-13 and AL1-14 -----------------------------------------------------------------------------------------

def test_a_single_kind_factor_whose_inputs_keep_changing_leaves_no_limit_with_its_reason(monkeypatch) -> None:
    """The audit's DD-5: PICO validated for SD-proton only, both SD couplings; the factor's inputs changing at each
    attempt: PICO gives no limit, with the reason, and the point is not decided without it."""
    monkeypatch.setattr(limits, "per_module95", lambda kind, mass, excluded=():
                        (((PICO, 1e-40),), ()) if kind == "SD-proton" else ((), ()))
    monkeypatch.setattr(limits, "tolerance", lambda *a: 0.0)
    limits.clear_cache()

    def changing(*a):
        raise limit_tables.InputsChanging("SIMULATED: inputs changed each time")
    monkeypatch.setattr(dd_channels, "_single_kind_factor", changing)
    found = dd_channels.compare(dd_channels.channels_of(0.0, 0.0, 1.0, 5.0, 100.0), 100.0)
    assert any(r.startswith(f"direct detection ({PICO}): its rate ratio") and "SIMULATED" in r for r in found.pending)
    assert found.excluded is not False
    limits.clear_cache()


def test_an_unloadable_tabulated_module_gives_no_limit_with_its_reason(monkeypatch) -> None:
    """The audit's DD-6: with the tables on, as with them off: (None, why), and the comparison pending on it."""
    def absent(name):
        raise DataUnavailable("SIMULATED: fetch the data first")
    monkeypatch.setattr(registry, "load_module", absent)
    limits.clear_cache()
    for use_tables in (False, True):
        value, why = limits.reference_limit(LZ, "SI", 30.0, use_tables)
        assert value is None and "fetch the data first" in why
    found = dd_channels.compare([dd_channels.Channel(kind="SI", sigma_cm2=1e-47)], 30.0)
    assert any("fetch the data first" in r for r in found.pending)
    limits.clear_cache()


def test_masses_are_given_as_a_range_or_a_list_or_refused_with_a_message() -> None:
    assert cli._masses("10:60:6") == pytest.approx(np.geomspace(10.0, 60.0, 6).tolist())
    assert cli._masses("10, 30") == [10.0, 30.0] and cli._masses("") == []
    for bad in ("10:60", "ten", "10:60:x", "-5", "nan"):
        with pytest.raises(typer.BadParameter):
            cli._masses(bad)


# --- AL1-16 ----------------------------------------------------------------------------------------------------

def test_a_test_that_reaches_for_the_network_is_refused_and_named(_no_network) -> None:
    """The fence (``tests/conftest.py``): a lookup of another host, and a connection to one, refused as a machine
    without a network refuses them, each noted for the test's failure; this machine's own addresses pass."""
    with pytest.raises(OSError, match="fenced"):
        socket.getaddrinfo("export.arxiv.org", 443)
    with pytest.raises(OSError, match="fenced"):
        socket.socket().connect(("192.0.2.1", 80))                   # TEST-NET-1: never routed
    assert len(_no_network) == 2 and _no_network[0].startswith("export.arxiv.org")
    _no_network.clear()                                              # this test's own attempts: not its failure
    assert socket.getaddrinfo("localhost", 80)
