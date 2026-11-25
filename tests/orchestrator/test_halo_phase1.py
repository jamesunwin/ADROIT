"""Halo phase 1 through the calculations: the fixed common benchmark reaching Track 2's fit, null limits and verdicts
and Track 1's points; what it cannot calculate named while an independent exclusion stands; the default reading
unchanged; continuations (promotion, resume, reanalysis, replay) keeping or refusing a halo; and the request, result,
report and export of one run naming one resolution. Offline: toy searches with real recoil rates, stubs where a whole
calculation would be needed."""
from __future__ import annotations

import json
import math
from types import SimpleNamespace

import pytest

from adroit.core import halo_choice
from adroit.core.dm_state import HaloModel
from adroit.experiments import registry
from adroit.experiments.base import standard_halo
from adroit.orchestrator import exclusion, signal
from adroit.parameter_space import halo_evaluation, halo_limits, halo_region
from adroit.parameter_space.classes import Point
from adroit.parameter_space.halo_region import HaloPreset
from adroit.parameter_space.scan import PointResult
from tests.orchestrator.test_signal import ToyGermanium

OLDER = standard_halo(220.0, 232.0, 544.0)          # the older convention most modules publish with


class OlderToy(ToyGermanium):
    """The toy search, its published halo the older convention (not the benchmark): its fit and its limit move with
    the halo through its real recoil rates."""

    def conventions(self):
        return super().conventions().model_copy(update={"halo": OLDER})


class OlderNull(OlderToy):
    """The same toy as a null search (a Poisson limit on its expected events), validated wherever it is asked."""

    @property
    def info(self):
        return super().info.model_copy(update={"name": "older null"})

    def accepts_validation(self, particle, interaction, cl) -> bool:
        return True


def _bases(halo: HaloModel, flags: list[HaloModel]) -> set:
    """The halos a run may predict at: its own, and its halo flags' one-parameter changes."""
    return {halo.model_dump_json(), *(h.model_dump_json() for h in flags)}


@pytest.fixture
def toys(monkeypatch):
    seen = {"signal": [], "exclusion": [], "judged": []}
    monkeypatch.setitem(registry.SIGNAL_SEARCHES, "older toy", OlderToy)
    monkeypatch.setitem(registry.SIGNAL_SEARCHES, "older null", OlderNull)
    expected = OlderToy.expected_signal

    def spy(self, particle, interaction, halo, model, target=None):
        seen["signal"].append(halo)
        return expected(self, particle, interaction, halo, model, target)
    monkeypatch.setattr(OlderToy, "expected_signal", spy)
    run = exclusion.run

    def recorded(request):
        seen["exclusion"].append(request.halo)
        return run(request)
    monkeypatch.setattr(exclusion, "run", recorded)

    def judged(candidate, include_unverified=False, halo=None, certificates=None):
        seen["judged"].append(halo)
        return [], {}
    monkeypatch.setattr(signal.complementary, "judged", judged)
    return seen


def _request(halo=None) -> signal.SignalRequest:
    return signal.SignalRequest(experiment="older toy", null_modules=["older null"], toys=20, leaders=1, workers=1,
                                candidates=[signal.Candidate(label="O1s@20", card_id="O1", isospin="s", mass_gev=20.0)],
                                halo=halo)


def test_the_fixed_benchmark_reaches_the_fit_the_null_limits_and_the_verdicts(toys):
    fixed = halo_choice.fixed()
    result = signal.run(_request(fixed))
    flags = [fixed.halo.model_copy(update=change) for change in signal.ALTERNATIVE_HALOS.values()]
    assert toys["signal"][0] == fixed.halo                                       # the fit at the benchmark
    assert {h.model_dump_json() for h in toys["signal"]} <= _bases(fixed.halo, flags)   # fit, toys, null, flags
    assert toys["exclusion"] == [fixed.halo] and toys["judged"] == [fixed.halo]
    module, c = OlderNull(), result.request.candidates[0]
    at = module.expected_signal(signal._particle(c), signal._interaction(module, c), fixed.halo,
                                module.conventions().nuclear_model)
    assert result.combinations[0].null_limits["older null"] == pytest.approx(math.sqrt(2.303 / at.total_events))
    assert "halo mismatch" not in result.combinations[0].note
    assert result.halo_resolution.treatment.value == "benchmark"
    assert result.halo_resolution == halo_choice.resolve(fixed, track="track2")
    flags = result.tournament.ranking[0].flags if result.tournament.ranking else []
    assert not any(f.startswith("halo (v0") for f in flags)   # any halo flag is the benchmark's, and says so


def test_unset_track2_keeps_each_searchs_published_halo(toys):
    result = signal.run(_request())
    flags = [OLDER.model_copy(update=change) for change in signal.ALTERNATIVE_HALOS.values()]   # the search's own
    # halo, one parameter changed (AL3-35: the default SHM's had been changed)
    assert toys["signal"][0] == OLDER and toys["exclusion"] == [None]
    assert {h.model_dump_json() for h in toys["signal"]} <= _bases(OLDER, flags)
    assert toys["judged"] == [None] and result.halo_resolution.label == "Published halos (reproduction)"
    assert "halo" not in result.request.model_dump(mode="json")


def test_the_benchmark_and_the_published_fits_differ_where_the_halos_do(toys):
    published, benchmark = signal.run(_request()), signal.run(_request(halo_choice.fixed()))
    assert published.fits[0].s_hat != benchmark.fits[0].s_hat or published.fits[0].z_local != benchmark.fits[0].z_local
    assert published.combinations[0].null_limits != benchmark.combinations[0].null_limits


def test_a_private_search_is_refused_at_the_benchmark_and_nothing_runs(toys):
    with pytest.raises(ValueError, match="private-search:abc: a private search: not calculated with SHM: fixed"):
        signal.refuse_at_benchmark(halo_choice.fixed(), ["older toy", "private-search:abc"])
    signal.refuse_at_benchmark(halo_choice.fixed(), ["older toy", "older null"])


def test_one_request_result_report_and_export_name_one_resolution(toys, tmp_path):
    from adroit.evidence import exports
    from adroit.evidence.build import save
    result = signal.run(_request(halo_choice.fixed()))
    folder = tmp_path / "run"
    folder.mkdir()
    (folder / "result.json").write_text(result.model_dump_json())
    save(folder / "result.json", "signal")
    identity = result.halo_resolution.identity
    assert json.loads((folder / "result.json").read_text())["request"]["halo"]["benchmark"] == "shm-2105.00599"
    assert identity[:12] in signal.report(result)
    halo = json.loads(exports.tables(folder / "result.json")["halo.json"])
    assert halo["resolution"]["identity"] == identity and halo["how"] == "recorded with the result"


# --- Track 1 at the benchmark ------------------------------------------------------------------------------------


def _nominal(seen, **excluded):
    def nominal():
        state = halo_limits.active()
        seen.append((state.v0_km_s, state.v_esc_km_s, state.rho_gev_cm3, state.benchmark))
        return PointResult(point=Point(m_chi=100.0, m_med=1000.0), omega_h2=0.12, dd_kind="anapole",
                           dd_sigma_cm2=1e-40, dd_limit_cm2=None, dd_ratio=2.0,
                           excluded={"direct detection": True, **excluded}, ratios={"direct detection": 2.0},
                           ratio_confidence_levels={"direct detection": 0.95})
    return nominal


ANAPOLE = SimpleNamespace(dd=lambda p: ("anapole", 1e-40))      # a structure compared through Path 1


def test_a_track1_point_is_calculated_at_the_benchmark_and_what_cannot_use_it_is_named():
    from adroit.parameter_space.verdict import classify
    seen = []
    r = halo_evaluation.at_benchmark(ANAPOLE, Point(m_chi=100.0, m_med=1000.0), halo_choice.fixed(),
                                     _nominal(seen, **{"colliders (CMS)": False}))
    assert seen == [(238.0, 544.0, 0.3, True)]                   # every halo-dependent comparison at the benchmark
    assert r.excluded["direct detection"] is None and "direct detection" not in r.ratios
    reason = next(p for p in r.pending if p.startswith("direct detection (anapole)"))
    assert "not calculated with SHM: fixed benchmark" in reason and "operator_limits" in reason
    c = classify(None, r)
    assert c.status == "pending" and c.halo == halo_region.AT_BENCHMARK and reason in c.pending
    alone = halo_evaluation.at_benchmark(ANAPOLE, Point(m_chi=100.0, m_med=1000.0), halo_choice.fixed(),
                                         _nominal([], **{"colliders (CMS)": True}))
    assert classify(None, alone).status == "excluded" and classify(None, alone).excluded_by == ["colliders (CMS)"]


def test_the_scan_dispatches_on_the_halo_in_force(monkeypatch):
    from adroit.parameter_space import scan
    calls = []
    monkeypatch.setattr(scan, "_evaluate", lambda *a, **k: calls.append("nominal") or "published")
    monkeypatch.setattr(halo_evaluation, "at_benchmark", lambda cls, p, fixed, nominal: calls.append(fixed) or "b")
    monkeypatch.setattr(halo_evaluation, "evaluate", lambda cls, p, preset, nominal, u: calls.append(preset) or "r")
    monkeypatch.setattr(scan, "unverified_used", __import__("contextlib").nullcontext)
    monkeypatch.setattr(scan, "records_used", __import__("contextlib").nullcontext)
    fixed, preset = halo_choice.fixed(), HaloPreset()
    with halo_region.using(fixed):
        assert scan.evaluate(None, None) == "b"
    with halo_region.using(preset):
        assert scan.evaluate(None, None) == "r"
    assert scan.evaluate(None, None) == "published" and calls == [fixed, preset, "nominal"]


@pytest.mark.needs("diamx")            # a xenon module is loaded for its own halo
def test_a_module_whose_published_halo_is_the_benchmark_keeps_its_own_procedure(monkeypatch):
    from adroit.parameter_space import limits
    monkeypatch.setattr(limits, "reference_limit", lambda name, kind, mass, use: (1e-46, ""))
    monkeypatch.setattr(limits, "reference_tolerance", lambda name, kind, mass: 0.01)
    monkeypatch.setattr(halo_limits, "exact", lambda *a: 3e-46)
    at = halo_limits.State(v0_km_s=238.0, v_esc_km_s=544.0, rho_gev_cm3=0.3, benchmark=True)
    assert halo_limits.own_halo("LZ WS2022+WS2024", at) and not halo_limits.own_halo("CRESST-III 2019", at)
    value, margin, how = halo_limits.module_limit(at, "LZ WS2022+WS2024", "SI", 50.0, False)
    assert (value, margin) == (pytest.approx(1e-46, rel=1e-6, abs=0), 0.01) and "its own published procedure" in how
    value, _, how = halo_limits.module_limit(at, "CRESST-III 2019", "SI", 10.0, False)
    assert value == pytest.approx(3e-46 * 0.4 / 0.3) and how == "its own procedure at this halo"
    sample = halo_limits.State(v0_km_s=238.0, v_esc_km_s=544.0, rho_gev_cm3=0.3)      # a region's sample: unchanged
    monkeypatch.setattr(halo_limits, "validated", lambda *a, **k: None)
    _, _, how = halo_limits.module_limit(sample, "LZ WS2022+WS2024", "SI", 50.0, False)
    assert "budget is spent" in how


# --- continuations ------------------------------------------------------------------------------------------------


def test_a_promoted_child_takes_its_parents_benchmark(monkeypatch, tmp_path):
    from adroit.orchestrator import promote, single_idea
    from adroit.parameter_space import simplified
    seen = []

    def stop(request):
        seen.append(request.halo)
        raise RuntimeError("stopped")
    monkeypatch.setattr(single_idea, "prepared", stop)
    for halo in (halo_choice.fixed(), None):
        parent = SimpleNamespace(request=_request(halo), global_z=1.0)
        with pytest.raises(RuntimeError, match="stopped"):
            promote._study(tmp_path, parent, parent.request.candidates[0], "simplified completion",
                           simplified.model("vector", 20, 1000), {"toys": 10, "grid": 4, "masses": 2})
    assert seen == [halo_choice.fixed(), None]


def test_a_resume_with_another_halo_is_refused_naming_it(tmp_path):
    from adroit.core.checkpoint import Checkpoint, CheckpointMismatch
    inputs = {"spec": "x", "halo": "published"}
    Checkpoint(tmp_path, inputs, {"code": "1"})
    with pytest.raises(CheckpointMismatch, match="the halo differs from the one its checkpoint was calculated with"):
        Checkpoint(tmp_path, {**inputs, "halo": halo_choice.fixed().model_dump(mode="json")}, {"code": "1"}, resume=True)
    Checkpoint(tmp_path, inputs, {"code": "1"}, resume=True)


@pytest.mark.parametrize("kind, saved, target, expected", [
    ("track1", {"halo": "BENCH"}, "signal", "BENCH"), ("signal", {"halo": "BENCH"}, "track1", "BENCH"),
    ("signal", {}, "track1", "published"), ("single_idea", {"halo": "PRESET"}, "track1", "PRESET"),
    ("single_idea", {}, "track1", "published"), ("track1", {"halo": "PRESET"}, "signal", None),
    ("single_idea", {"halo": "published"}, "signal", None)])
def test_a_reanalysis_in_another_track_carries_the_halo_it_can(kind, saved, target, expected):
    from adroit.orchestrator.reanalysis import _converted_halo
    values = {"BENCH": halo_choice.fixed().model_dump(mode="json"), "PRESET": HaloPreset().model_dump(mode="json")}
    request = {k: values.get(v, v) for k, v in saved.items()}
    found = _converted_halo(kind, request, target)
    assert found.get("halo") == values.get(expected, expected)


def test_a_replay_takes_the_halo_its_result_was_calculated_with():
    from adroit.evidence.replay import _recorded_halo
    fixed = halo_choice.fixed()
    assert _recorded_halo(SimpleNamespace(request=SimpleNamespace(halo=HaloPreset()))) == HaloPreset()
    assert _recorded_halo(SimpleNamespace(request=SimpleNamespace(halo=fixed))) == fixed
    assert _recorded_halo(SimpleNamespace(request=SimpleNamespace(halo="published"))) is None


def test_a_saved_track1_point_is_reused_only_at_the_same_halo():
    from adroit.orchestrator.physical_eligibility import _other_halo
    fixed = halo_choice.fixed()
    assert _other_halo(SimpleNamespace(halo="published"), _request()) == ""
    assert _other_halo(SimpleNamespace(halo=None), _request()) == ""      # saved before the choice: published
    assert _other_halo(SimpleNamespace(halo=fixed), _request(fixed)) == ""
    assert "SHM: uncertainty region" in _other_halo(SimpleNamespace(halo=HaloPreset()), _request())
    assert "Published halos" in _other_halo(SimpleNamespace(halo="published"), _request(fixed))


def test_the_native_joint_fit_and_private_inputs_are_refused_where_they_cannot_follow(monkeypatch):
    from adroit.orchestrator import single_idea
    from adroit.parameter_space import native_joint, simplified
    with halo_region.using(halo_choice.fixed()):
        with pytest.raises(ValueError, match="native joint signal/null likelihood: not calculated with SHM: fixed"):
            native_joint.published_halo_only()
    with halo_region.using(HaloPreset()):
        native_joint.published_halo_only()                          # over the region: its own, as before
    curve = SimpleNamespace(name="a private SI curve", contract=SimpleNamespace(adapter="si_isoscalar_curve"))
    monkeypatch.setattr("adroit.constraints.experimental_review.load_bound", lambda name: curve)
    monkeypatch.setattr("adroit.parameter_space.private_limits.check_applicability", lambda spec, limits: None)
    profile = SimpleNamespace(limits=["limit:x"], null_modules=[])
    request = single_idea.SingleIdeaRequest(experiment="older toy", spec=simplified.model("vector", 10, 1000),
                                            halo=HaloPreset())
    with pytest.raises(ValueError, match="a private SI curve: a private direct-detection input has no halo variation"):
        single_idea._fit_options(request, profile)
    assert single_idea._fit_options(request.model_copy(update={"halo": "published"}), profile)["private_limits"]


def test_a_claim_is_bound_to_the_halo_data_and_reads_stale_when_they_change(tmp_path, monkeypatch):
    from adroit.core.certificate import POLICY, Bound, Certificate, stale_reasons
    from adroit.parameter_space import certification
    with halo_evaluation._reading() as read:              # the files a point read, as it saves them (HC-01)
        evaluation = SimpleNamespace(halo=halo_region.HaloEvaluation(region="r", data=read))
    bound = certification._halo_data(evaluation)
    assert set(bound) == set(halo_choice.HALO_DATA) and all(bound.values())
    assert certification._halo_data(SimpleNamespace(halo=None)) == {}
    cert = Certificate(claim_kind="k", scope="s", bound=Bound(halo_data=bound), policy=POLICY)
    assert stale_reasons(cert, certification.current_bound(cert)) == []
    for path in halo_choice.HALO_DATA.values():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_bytes((halo_choice.PACKAGE / path).read_bytes())
    (tmp_path / halo_choice.HALO_DATA["local densities"]).write_text("records: {}\n")
    monkeypatch.setattr(halo_choice, "PACKAGE", tmp_path)
    assert stale_reasons(cert, certification.current_bound(cert)) == [
        "the halo data file (local densities) changed since it was certified"]
    assert "halo_data" not in Bound().model_dump(mode="json")                       # earlier certificates unchanged
    assert certification.halo_check(halo_region.AT_BENCHMARK).state == "not_applicable"


def test_the_benchmark_is_the_halo_the_single_idea_fit_uses(toys):
    fixed = halo_choice.fixed()
    module, c = OlderToy(), signal.Candidate(label="O1s@20", card_id="O1", isospin="s", mass_gev=20.0)
    with halo_region.using(fixed):
        at = signal._signal(module, c)
    with halo_region.using(HaloPreset()):
        region = signal._signal(module, c)                      # over the region the fit keeps its published halo
    published = signal._signal(module, c)
    assert region.density == published.density and at.density != published.density
    assert signal._null_halos(["older null"]) == [(None, ["older null"])]
    with halo_region.using(fixed):
        assert signal._null_halos(["older null"]) == [(fixed.halo, ["older null"])]
    assert HaloModel() == fixed.halo


@pytest.mark.needs("diamx")             # LZ's module is loaded for its published halo (AL3-16's check, cycle 4)
def test_a_null_whose_published_halo_is_the_benchmark_keeps_its_own(toys):
    fixed = halo_choice.fixed()
    with halo_region.using(fixed):
        assert signal._null_halos(["DEAP-3600 (2019)", "LZ WS2022+WS2024"]) == [
            (None, ["LZ WS2022+WS2024"]), (fixed.halo, ["DEAP-3600 (2019)"])]


def test_a_thermal_point_without_its_own_label_is_certified_with_its_evaluations_halo():
    from adroit.parameter_space import certification
    bench = PointResult(point=Point(m_chi=10.0, m_med=100.0), omega_h2=0.12, dd_kind="SI", dd_sigma_cm2=0,
                        dd_limit_cm2=1, excluded={"toy": False},
                        halo=halo_region.HaloEvaluation(region="SHM: fixed benchmark", treatment="benchmark"))
    assert certification._halo_label(bench) == halo_region.AT_BENCHMARK
    assert certification._halo_label(bench.model_copy(update={"halo": None})) == ""
    from adroit.orchestrator.single_idea import BandPoint
    point = BandPoint(m_chi=10.0, s_hat=1.0, events_at_unit=1.0, mu_hat=1.0, mu_68=(0.5, 1.5), z_local=1.0,
                      status="viable", evaluation=bench)
    found = certification.certify(point, "path2_thermal_eligibility", "s", [])
    assert found.certificate.check("halo").reason.startswith("one fixed benchmark halo")
    assert set(found.certificate.bound.halo_data) == set(halo_choice.HALO_DATA)
