"""Halo phase 2 through the calculations: SHM++'s fixed benchmark reaching Track 2's fit, null limits, flags and verdicts
(the detector's table for recoils, the Sun's for capture) and Track 1's points (every module by its own procedure with
the table, no count ratio, the slow ones within the budget; capture with the Sun's table; the Galactic searches at its
density); what cannot use it named; continuations keeping it exactly; two requests interleaved keeping their own.
Offline: toy searches with real recoil rates, stubs where a whole calculation would be needed."""
from __future__ import annotations

import math
import threading
from functools import lru_cache
from types import SimpleNamespace

import pytest

from adroit.core import halo_choice
from adroit.halo_models import shm_plus_plus as shmpp
from adroit.orchestrator import signal
from adroit.parameter_space import halo_evaluation, halo_limits, halo_region
from adroit.parameter_space.classes import Point
from adroit.parameter_space.scan import PointResult
from tests.orchestrator.test_halo_phase1 import OlderNull, OlderToy, _request, toys  # noqa: F401 (a fixture)


@lru_cache(maxsize=1)
def plus() -> halo_choice.FixedHalo:
    return halo_choice.fixed("shm-plus-plus")


def test_shm_plus_plus_reaches_the_fit_the_null_limits_the_flags_and_the_verdicts(toys):  # noqa: F811
    fixed = plus()
    result = signal.run(_request(fixed))
    varied = {halo_choice.varied(fixed, change).model_dump_json() for change in signal.ALTERNATIVE_HALOS.values()}
    assert toys["signal"][0] == fixed.halo                                   # the fit: the detector's table
    assert {h.model_dump_json() for h in toys["signal"]} <= {fixed.halo.model_dump_json(), *varied}
    from adroit.halo_models.frames import frame_of
    assert all(frame_of(h) == "detector" for h in toys["signal"])
    assert toys["exclusion"] == [fixed.halo] and toys["judged"] == [fixed.sun]   # capture: the Sun's table
    module, c = OlderNull(), result.request.candidates[0]
    at = module.expected_signal(signal._particle(c), signal._interaction(module, c), fixed.halo,
                                module.conventions().nuclear_model)
    assert result.combinations[0].null_limits["older null"] == pytest.approx(math.sqrt(2.303 / at.total_events))
    assert result.halo_resolution == halo_choice.resolve(fixed, track="track2")
    flags = [f for row in result.tournament.ranking for f in row.flags if f.startswith("halo")]
    assert all("SHM++ generated again from the fixed benchmark" in f for f in flags)


def test_shm_plus_plus_and_the_shm_benchmark_fit_differently(toys):  # noqa: F811
    shm, plus_plus = signal.run(_request(halo_choice.fixed())), signal.run(_request(plus()))
    assert shm.fits[0].s_hat != plus_plus.fits[0].s_hat
    assert shm.combinations[0].null_limits != plus_plus.combinations[0].null_limits
    assert shm.halo_resolution.identity != plus_plus.halo_resolution.identity


def test_what_cannot_follow_shm_plus_plus_is_refused_with_its_reason():
    from adroit.parameter_space import native_joint
    with pytest.raises(ValueError, match="private-search:abc: a private search: not calculated with SHM\\+\\+: fixed"):
        signal.refuse_at_benchmark(plus(), ["older toy", "private-search:abc"])
    with halo_region.using(plus()):
        with pytest.raises(ValueError, match="native joint signal/null likelihood: not calculated with SHM\\+\\+"):
            native_joint.published_halo_only()


# --- Track 1 at SHM++ -------------------------------------------------------------------------------------------------


def _nominal(seen):
    def nominal():
        state = halo_limits.active()
        seen.append(state)
        return PointResult(point=Point(m_chi=100.0, m_med=1000.0), omega_h2=0.12, dd_kind="SI", dd_sigma_cm2=1e-46,
                           dd_limit_cm2=None, dd_ratio=0.5, excluded={"direct detection": False})
    return nominal


def test_a_track1_point_takes_the_tables_and_never_a_standard_halo():
    seen = []
    cls = SimpleNamespace(dd=lambda p: ("SI", 1e-46))
    from adroit.parameter_space import scan
    original = scan.dd_channels_of
    scan.dd_channels_of = lambda *a: ["a channel"]
    try:
        r = halo_evaluation.at_benchmark(cls, Point(m_chi=100.0, m_med=1000.0), plus(), _nominal(seen))
    finally:
        scan.dd_channels_of = original
    state = seen[0]
    assert state.table == plus().halo and state.sun == plus().sun and state.benchmark
    assert math.isnan(state.v0_km_s) and math.isnan(state.v_esc_km_s) and state.rho_gev_cm3 == 0.55
    assert state.key == halo_limits.tabulated(plus().halo)
    assert r.halo.treatment == "benchmark" and r.halo.region == halo_choice.resolve(plus()).label


@pytest.fixture
def table_state(monkeypatch):
    from adroit.parameter_space import limits
    calls = []
    monkeypatch.setattr(halo_limits, "exact_at_table", lambda module, kind, mass, key: calls.append(
        (module, kind, mass, key)) or 4e-46)
    monkeypatch.setattr(halo_limits, "exact", lambda *a: pytest.fail("a standard halo was used for SHM++"))
    monkeypatch.setattr(halo_limits, "validated", lambda *a, **k: 0.01)       # a count ratio would be usable for the SHM
    monkeypatch.setattr(halo_limits, "scale", lambda *a: pytest.fail("a count ratio was used for SHM++"))
    monkeypatch.setattr(limits, "edge_floor", lambda module, kind, mass: 1e-45 if mass == 3.0 else None)
    state = halo_limits.at_tables(plus(), halo_limits.Budget(1))
    return state, calls


def test_every_module_takes_its_own_procedure_with_the_table(table_state):
    state, calls = table_state
    value, margin, how = halo_limits.module_limit(state, "CRESST-III 2019", "SI", 10.0, False)
    assert value == pytest.approx(4e-46 * halo_limits.RHO_REF / 0.55) and margin == 0.0
    assert how == "its own procedure at this halo" and calls[-1] == ("CRESST-III 2019", "SI", 10.0, state.key)
    value, _, how = halo_limits.module_limit(state, "LZ WS2022+WS2024", "SI", 50.0, False)    # the budget's one
    assert value == pytest.approx(4e-46 * halo_limits.RHO_REF / 0.55) and "count ratio" not in how
    assert state.spent[-1].startswith("LZ WS2022+WS2024 SI at 50 GeV, shmpp-1810.11468 v1 (tables ")
    value, _, how = halo_limits.module_limit(state, "XENONnT SR0+SR1", "SI", 50.0, False)
    assert value is None and "the point's budget is spent" in how and "no validated count ratio" in how
    value, _, how = halo_limits.module_limit(state, "CRESST-III 2019", "SI", 3.0, False)
    assert value is None and "edge clause" in how
    assert not halo_limits.own_halo("LZ WS2022+WS2024", state) and not state.approximate()


def test_an_infinite_limit_stands_only_where_the_table_gives_no_recoil(table_state, monkeypatch):
    state, _ = table_state
    monkeypatch.setattr(halo_limits, "exact_at_table", lambda *a: math.inf)
    monkeypatch.setattr(halo_limits, "blind_at_table", lambda *a: True)
    assert halo_limits.module_limit(state, "DEAP-3600 (2019)", "SI", 2.0, False)[0] == math.inf
    monkeypatch.setattr(halo_limits, "blind_at_table", lambda *a: False)
    value, _, how = halo_limits.module_limit(state, "DEAP-3600 (2019)", "SI", 2.0, False)
    assert value is None and "gave no valid limit" in how


def test_capture_the_galactic_searches_and_the_descriptions_take_the_benchmark(table_state, monkeypatch):
    from adroit.parameter_space import dd_channels
    state, _ = table_state
    factors = []
    monkeypatch.setattr(dd_channels, "_single_kind_factor", lambda *a: factors.append(a[4]) or 1.0)   # the velocities
    with halo_limits.using(state):
        assert halo_limits.capture_halo() == plus().sun
        rho = halo_limits.recorded_densities()
        record = next(iter(rho))
        assert halo_limits.density_scale(record) == pytest.approx((0.55 / rho[record]) ** 2)
        assert halo_limits.describe(state).startswith("at the generated benchmark shmpp-1810.11468 v1")
        assert halo_limits.velocities(state) == ("table", state.key)
        dd_channels.single_kind_factor("PICO-60 C3F8 (2019)", "SD-proton", 30.0, 0.5)
    assert factors == [("table", state.key)]             # the interference factor at the table, not at (v₀, v_esc)
    assert halo_limits.halo_at(("table", state.key)).speed_density == plus().halo.speed_density


def test_the_cache_keys_separate_the_mixture_and_the_frame():
    a = halo_limits.tabulated(plus().halo)
    eta = halo_choice._generated(plus().parameters.model_copy(update={"eta": 0.3}), plus().numerics, "SHM++")[0]
    assert halo_limits.tabulated(eta) != a
    assert halo_limits.tabulated(plus().halo.model_copy(update={"rho_gev_cm3": 0.3})) == a     # ρ₀ scales analytically
    with pytest.raises(ValueError, match="detector's frame"):
        halo_limits.tabulated(plus().sun)


def test_capture_in_a_track1_point_takes_the_suns_table(monkeypatch):
    from adroit.constraints import capture
    from adroit.parameter_space import scan
    seen = []
    monkeypatch.setattr(capture, "capture_rate", lambda particle, interaction, halo=None, **k: seen.append(halo) or 1.0)
    monkeypatch.setattr(capture, "available", lambda: True)
    monkeypatch.setattr(scan.searches, "today_unknown", lambda cls, p: "")
    cls = SimpleNamespace(sigma_v_today=lambda p, speed: {"b": 1e-26}, interaction=lambda p: None)
    monkeypatch.setattr("adroit.constraints.mixtures.bound",
                        lambda *a: SimpleNamespace(excluded=None, ratio=None, why=lambda: "stub"))
    with halo_limits.using(halo_limits.at_tables(plus(), halo_limits.Budget(0))):
        assert scan._icecube(cls, Point(m_chi=100.0, m_med=1000.0)) == (None, None, "stub")
    assert seen == [plus().sun]


# --- continuations and interleaving ----------------------------------------------------------------------------------


def test_two_requests_interleaved_keep_their_own_halo(toys):  # noqa: F811
    a, b = plus(), halo_choice.fixed()
    barrier, seen = threading.Barrier(2), {}
    module, c = OlderToy(), signal.Candidate(label="O1s@20", card_id="O1", isospin="s", mass_gev=20.0)
    alone = {}
    for name, value in (("a", a), ("b", b)):
        with halo_region.using(value):
            alone[name] = signal._signal(module, c).density

    def run(name, value):
        with halo_region.using(value):
            barrier.wait()
            first = signal._signal(module, c).density
            barrier.wait()
            seen[name] = (first, signal._signal(module, c).density, signal.fixed_halo())
    threads = [threading.Thread(target=run, args=("a", a)), threading.Thread(target=run, args=("b", b))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert seen["a"] == (alone["a"], alone["a"], a) and seen["b"] == (alone["b"], alone["b"], b)
    assert alone["a"] != alone["b"]


def test_promotion_reanalysis_replay_and_reuse_keep_the_benchmark_exactly(monkeypatch, tmp_path):
    from adroit.evidence.replay import _recorded_halo
    from adroit.orchestrator import promote, single_idea
    from adroit.orchestrator.physical_eligibility import _other_halo
    from adroit.orchestrator.reanalysis import _converted_halo
    from adroit.parameter_space import simplified
    fixed = plus()
    seen = []
    monkeypatch.setattr(single_idea, "prepared", lambda request: seen.append(request.halo) or (_ for _ in ()).throw(
        RuntimeError("stopped")))
    parent = SimpleNamespace(request=_request(fixed), global_z=1.0)
    with pytest.raises(RuntimeError, match="stopped"):
        promote._study(tmp_path, parent, parent.request.candidates[0], "simplified completion",
                       simplified.model("vector", 20, 1000), {"toys": 10, "grid": 4, "masses": 2})
    assert seen == [fixed] and seen[0].halo.speed_density == fixed.halo.speed_density
    saved = fixed.model_dump(mode="json")
    for kind, target in (("signal", "track1"), ("track1", "signal"), ("single_idea", "signal")):
        assert _converted_halo(kind, {"halo": saved}, target)["halo"] == saved
    assert _recorded_halo(SimpleNamespace(request=SimpleNamespace(halo=fixed))) == fixed
    assert _other_halo(SimpleNamespace(halo=fixed), _request(fixed)) == ""
    assert "SHM: fixed benchmark" in _other_halo(SimpleNamespace(halo=halo_choice.fixed()), _request(fixed))


def test_the_result_report_and_export_name_its_resolution(toys, tmp_path):  # noqa: F811
    import json

    from adroit.evidence import exports
    from adroit.evidence.build import save
    result = signal.run(_request(plus()))
    folder = tmp_path / "run"
    folder.mkdir()
    (folder / "result.json").write_text(result.model_dump_json())
    save(folder / "result.json", "signal")
    identity = result.halo_resolution.identity
    saved = json.loads((folder / "result.json").read_text())
    assert saved["request"]["halo"]["benchmark"] == "shmpp-1810.11468"
    assert saved["request"]["halo"]["tables"] == plus().tables
    assert identity[:12] in signal.report(result) and "SHM++" in signal.report(result)
    halo = json.loads(exports.tables(folder / "result.json")["halo.json"])
    assert halo["resolution"]["identity"] == identity and halo["resolution"]["tables"] == plus().tables
    assert shmpp.GENERATOR == halo["resolution"]["numerics"]["generator"]
