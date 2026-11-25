"""The HB recheck's findings, repaired (the independent audit of 2026-11-11 (hb recheck); the record
the HC repair record of 2026-11-11):

- HC-01: a point over the region or at a benchmark saves the halo data files it was calculated with, and its claim is
  certified against them, never against the files in force or as they are when its verdict is taken again; a point
  saved without them is not certified.
- HC-02: a promotion's completion that waits for the researcher's choice is offered as the request a child of the
  candidate is studied with (its parent's halo snapshot and every setting), and its command runs that request as saved.
- HC-03: a promotion refuses a halo its children's fresh run would refuse before it records, requests or calculates
  anything.

Offline: toy searches with real recoil rates (``test_halo_phase1``'s), the halo data files copied to a folder of the
test's, the model builder a spy at the provider boundary ($0)."""
from __future__ import annotations

import hashlib
import shlex
from types import SimpleNamespace

import pytest
import yaml
from typer.testing import CliRunner

from adroit.agents.llm import FakeLLMClient
from adroit.core import halo_choice
from adroit.core.certificate import reading
from adroit.orchestrator import cli, promote, runs, signal, single_idea
from adroit.orchestrator.completions import Completion
from adroit.parameter_space import certification, halo_evaluation, halo_limits, halo_region, simplified
from adroit.parameter_space import verdict as v
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.halo_region import HaloEvaluation, HaloPreset
from adroit.parameter_space.likelihood import LikelihoodSettings
from adroit.parameter_space.scan import Axis, PointResult, ScanRequest, ScanResult
from tests.orchestrator.test_halo_phase1 import _request, toys  # noqa: F401 (a fixture)
from tests.orchestrator.test_hb_fixes import REFUSED, _as_saved, files, plus  # noqa: F401 (a fixture)

LINES = "fermi-lat-1506.00013-lines"


# --- HC-01: a point's certificate is bound to the halo data it was calculated with -------------------------------------

def _row(point: Point, evaluation: HaloEvaluation | None = None) -> PointResult:
    """A point whose γ-ray line comparison is scaled by the local density it reads (the auditor's control's)."""
    ratio = halo_limits.density_scale(LINES)
    return PointResult(point=point, omega_h2=0.12, dd_kind="SI", dd_sigma_cm2=0, dd_limit_cm2=1,
                       excluded={"gamma-ray lines": ratio > 1}, ratios={"gamma-ray lines": ratio},
                       ratio_confidence_levels={"gamma-ray lines": 0.95},
                       ratio_sidedness={"gamma-ray lines": "one-sided"}, model_pending=[], halo=evaluation)


def _calculated(point: Point) -> PointResult:
    """The point calculated at SHM++ by its halo evaluation (``halo_evaluation.at_benchmark``)."""
    return halo_evaluation.at_benchmark(Spin1Class(), point, plus(), lambda: _row(point))


def _saved(row: PointResult) -> ScanResult:
    request = ScanRequest(model_class=Spin1Class(), fixed=row.point, x=Axis(parameter="m_med", low=900, high=1100, n=2),
                          y=Axis(parameter="m_chi", low=90, high=110, n=2), halo=plus())
    return ScanResult(request=request, xs=[900, 1100], ys=[90, 110], points=[row])


@pytest.fixture
def band(monkeypatch):
    """The saved point's theory-band claim from both public verdict entry points; roots, the equation of state's band
    and the unresolved list are deterministic stand-ins (the auditor's), classification and certification real."""
    from adroit.core.certificate import Check
    monkeypatch.setattr(v, "_thermal_roots", lambda *a, **k: ([], 0))
    monkeypatch.setattr(v, "_eos_new_roots", lambda *a, **k: [])
    monkeypatch.setattr(v, "_eos_missing", lambda: "")
    monkeypatch.setattr(v, "_band_membership", lambda *a, **k: Check(name="eos_band", state="satisfied"))
    monkeypatch.setattr(v, "_unresolved", lambda *a, **k: [])

    def claims(saved: ScanResult) -> list:
        found = [v.verdict(saved, likelihood=LikelihoodSettings()),
                 v.verdict_pair(saved, likelihood=LikelihoodSettings())[1]]
        return [next(c for c in f.crossings if c.kind == "theory_band") for f in found]
    return claims


def _now(certificate) -> str:
    return reading(certificate, certification.current_bound(certificate))


def test_a_saved_point_is_certified_against_the_data_it_was_calculated_with_never_the_files_now(files, band):  # noqa: F811
    """The auditor's control, the point calculated by the halo evaluation: with A (ρ = 0.4) its comparison is 1.89; the
    file then reads B (0.8, which would give 0.47). Its verdict taken again from the saved result is bound to A by
    both entry points and reads stale against B; with A restored (A → B → A), certified."""
    files.write(0.4)
    a = hashlib.sha256(files.densities.read_bytes()).hexdigest()
    row = _calculated(Point(m_chi=100, m_med=1000))
    assert row.halo.data["local densities"] == a and row.ratios["gamma-ray lines"] == pytest.approx((0.55 / 0.4) ** 2)
    saved = _saved(row)
    files.write(0.8)                                                       # B published after the point was saved
    for claim in band(saved):
        assert claim.certificate.bound.halo_data["local densities"] == a  # 1.89, read from A: bound to A
        assert claim.status == "excluded" and claim.certificate.decided
        assert _now(claim.certificate) == ("stale: the halo data file (local densities) changed since it was "
                                           "certified")
    files.write(0.4)                                                       # A again
    assert all(_now(claim.certificate).startswith("certified") for claim in band(saved))


def test_a_point_saved_without_its_halo_data_is_not_certified(files, band):  # noqa: F811
    """The auditor's own construction: a saved point with no record of the data it read is not certified against
    whatever is current; the exclusion it computed waits, the reason naming what to do."""
    files.write(0.4)
    with halo_limits.using(halo_limits.at_tables(plus(), halo_limits.Budget(0))):
        row = _row(Point(m_chi=100, m_med=1000), HaloEvaluation(region="SHM++", treatment="benchmark"))
    files.write(0.8)
    for claim in band(_saved(row)):
        assert not claim.certificate.decided and claim.status == "pending"
        assert claim.certificate.check("halo_data").state == "unknown"
        assert "run it again to certify" in claim.certificate.check("halo_data").reason
        assert claim.certificate.bound.halo_data == {name: "" for name in halo_choice.HALO_DATA}
        assert claim.certificate.computed_status == "excluded"


def test_a_point_records_its_runs_files_even_when_they_change_during_the_run(files):  # noqa: F811
    """In a run, the files its resolution read (held, HB-03), whatever is written meanwhile; a calculation outside any
    run, the files as they were when it began, held to its end."""
    files.write(0.4)
    resolution = halo_choice.resolve(plus())
    with halo_choice.holding(resolution.data):
        files.write(0.8)
        assert _calculated(Point(m_chi=100, m_med=1000)).halo.data == resolution.data
    files.write(0.8)
    b = halo_choice.data_identity(tuple(halo_choice.HALO_DATA))
    real = halo_limits.density_scale

    def edited_meanwhile(record):
        files.write(0.2)                                                   # edited while the point is calculated
        return real(record)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(halo_limits, "density_scale", edited_meanwhile)
        row = _calculated(Point(m_chi=100, m_med=1000))
    assert row.halo.data == b and row.ratios["gamma-ray lines"] == pytest.approx((0.55 / 0.8) ** 2)


def test_a_point_over_the_region_records_the_files_it_read(files, monkeypatch):  # noqa: F811
    """The region's evaluation (``halo_evaluation.evaluate``) records them as the benchmark's does; its samples' own
    calculation stands in here (it is ``at``'s, unchanged)."""
    sample = halo_region.HaloPointSample(v0_km_s=238, v_esc_km_s=544, rho_gev_cm3=0.3, where="centre")
    monkeypatch.setattr(halo_evaluation, "at", lambda *a, **k: sample)
    point = Point(m_chi=100, m_med=1000)
    row = halo_evaluation.evaluate(Spin1Class(), point, HaloPreset(), lambda: _row(point), False)
    assert row.halo.data == halo_choice.data_identity(tuple(halo_choice.HALO_DATA)) and row.halo.samples


def test_a_point_in_the_published_halos_binds_no_halo_data():
    row = PointResult(point=Point(m_chi=100, m_med=1000), omega_h2=0.12, dd_kind="SI", dd_sigma_cm2=0,
                      dd_limit_cm2=1, excluded={}, model_pending=[])
    assert certification._halo_data(row) == {} and certification.halo_data_check(row) == []


# --- HC-02: an offered completion is studied as its parent's child -----------------------------------------------------

OPTIONS = {"span": 2.0, "masses": 5, "toys": 500, "grid": 8, "literature": False}
PARENTS = {
    "SHM++ with its own budget": lambda: signal.SignalRequest(
        experiment="CDMS II Si (2013)", null_modules=["CDMSlite Run 2"], unverified_records=True,
        halo=plus().model_copy(update={"full_calculations": 3})),
    "the SHM benchmark with its own budget": lambda: signal.SignalRequest(
        experiment="CDMS II Si (2013)", null_modules=["CDMSlite Run 2"],
        halo=halo_choice.fixed().model_copy(update={"full_calculations": 2})),
    "the published halos (the child's region)": lambda: signal.SignalRequest(
        experiment="CDMS II Si (2013)", null_modules=["CDMSlite Run 2"]),
}


def _offered(folder, parent_request) -> promote.CompletionChoice:
    c = signal.Candidate(label="O1s@10", card_id="O1", isospin="s", mass_gev=10.0)
    choice = Completion(spec=simplified.model("vector", 10, 1000), choices=["one flavour: u"])
    return promote._offer(folder, parent_request, c, "a proposal", [choice], OPTIONS, global_z=1.7)[0]


@pytest.mark.parametrize("case", list(PARENTS))
def test_the_offered_command_studies_the_completion_at_its_parents_halo_with_every_setting(case, tmp_path,
                                                                                         monkeypatch):
    """The auditor's control: the command the promotion writes, parsed by the command line itself; only the study's
    calculation is intercepted. What it runs is the request an automatic child gets, its halo the parent's snapshot
    (a benchmark's tables and numerics, its budget) or the region resolved at the promotion, never re-resolved after a
    change of setting."""
    parent = PARENTS[case]()
    folder = tmp_path / "a run’s folder (with spaces)"
    monkeypatch.setattr(halo_region, "default", lambda: "preset")          # the setting at the promotion
    offer = _offered(folder, parent)
    child = promote._child_request(parent, signal.Candidate(label="O1s@10", card_id="O1", isospin="s", mass_gev=10.0),
                                   simplified.model("vector", 10, 1000), OPTIONS, 1.7)   # a child studied then
    monkeypatch.setattr(halo_region, "default", lambda: "published")       # the setting changed since
    seen = []
    monkeypatch.setattr(runs, "single_idea", lambda request, *a: seen.append(request) or (folder, "simulated"))
    out = CliRunner().invoke(cli.app, shlex.split(offer.command)[1:])
    assert out.exit_code == 0, out.output
    assert seen == [child]
    got = single_idea.prepared(seen[0])
    if parent.halo is not None:
        assert got.halo == parent.halo
        assert halo_choice.resolve(got.halo).identity == halo_choice.resolve(parent.halo).identity
    else:
        assert got.halo == HaloPreset()                                    # the region, as at the promotion
    assert (got.null_modules, got.unverified_records, got.parent_global_z, got.toys, got.grid) == \
        (parent.null_modules, parent.unverified_records, 1.7, 500, 8)
    assert len(got.masses_gev) == 5 and got.masses_gev[0] == pytest.approx(5.0)


def test_a_saved_request_is_run_as_saved_and_a_setting_given_with_it_is_refused(tmp_path, monkeypatch):
    offer = _offered(tmp_path, PARENTS["SHM++ with its own budget"]())
    ran = []
    monkeypatch.setattr(runs, "single_idea", lambda request, out, parent: ran.append((out, parent)) or (tmp_path, ""))
    for extra in (["--halo", "published"], ["--masses", "1:2:3"], ["--experiment", "CDMS II Si (2013)"],
                  [offer.file]):
        out = CliRunner().invoke(cli.app, ["single-idea", "--request", offer.request, *extra])
        assert out.exit_code == 2 and "run as saved" in " ".join(out.output.replace("│", " ").split())
    assert ran == []
    out = CliRunner().invoke(cli.app, ["single-idea", "--request", offer.request, "--out", str(tmp_path / "o"),
                                       "--parent", str(tmp_path)])
    assert out.exit_code == 0 and ran == [(tmp_path / "o", tmp_path)]


def test_a_saved_request_out_of_its_halos_form_is_refused_in_words_and_nothing_runs(tmp_path, monkeypatch):
    offer = _offered(tmp_path, PARENTS["SHM++ with its own budget"]())
    raw = yaml.safe_load(open(offer.request).read())
    del raw["halo"]["sun"]                                                  # SHM++ without its Sun-frame table
    import json
    open(offer.request, "w").write(json.dumps(raw))
    monkeypatch.setattr(runs, "single_idea", lambda *a: pytest.fail("ran"))
    out = CliRunner().invoke(cli.app, ["single-idea", "--request", offer.request])
    words = " ".join(out.output.replace("│", " ").split())
    assert out.exit_code == 2 and "without its Sun-frame table" in words and "{" not in words


def test_a_model_still_needs_its_search(tmp_path):
    out = CliRunner().invoke(cli.app, ["single-idea", str(tmp_path / "m.yaml")])
    assert out.exit_code == 2 and "--experiment" in out.output
    out = CliRunner().invoke(cli.app, ["single-idea", "--experiment", "CDMS II Si (2013)"])
    assert out.exit_code == 2 and "give a model file" in " ".join(out.output.replace("│", " ").split())


# --- HC-03: a promotion refuses an incalculable halo before anything ---------------------------------------------------

class Provider(FakeLLMClient):
    """The provider boundary: counts each request, sends none ($0)."""

    def __init__(self):
        super().__init__([])
        self.sent = 0

    def complete_structured(self, *args, **kwargs):
        self.sent += 1
        raise RuntimeError("SIMULATED provider boundary reached")


@pytest.fixture(scope="module")
def isovector():
    """A Track 2 result at SHM++ whose one candidate is isovector (only the model builder completes it)."""
    with pytest.MonkeyPatch.context() as mp:
        toys.__wrapped__(mp)
        request = _request(plus())
        candidate = request.candidates[0].model_copy(update={"isospin": "v"})
        return signal.run(request.model_copy(update={"candidates": [candidate]}))


def _parent(folder, result):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "result.json").write_text(result.model_dump_json())
    return folder


def test_a_healthy_parent_reaches_the_model_builder(isovector, toys, tmp_path):  # noqa: F811
    """The control: with a halo it can calculate, the builder-only candidate's promotion sends its request."""
    client = Provider()
    with pytest.raises(RuntimeError, match="SIMULATED"):
        promote.promote(_parent(tmp_path / "run", isovector), [isovector.request.candidates[0].label], llm=client)
    assert client.sent == 1


@pytest.mark.parametrize("case", [c for c in REFUSED if c != "SHM++ holding a standard halo"])
def test_a_promotion_refuses_what_its_childrens_fresh_run_refuses_before_any_request(case, isovector, toys, tmp_path):  # noqa: F811
    """The auditor's control (a newer generator), with an edited table, an unavailable family, another family's
    benchmark and a halo the machinery does not take: the fresh run's refusal, no request, nothing recorded. The toy
    searches stay registered throughout (``toys``), so that without the refusal the promotion reaches the builder and
    fails here, at the provider, not at a module it cannot load (the auditor's HC recheck, HD-04, 2026-11-12)."""
    halo = REFUSED[case]()
    with pytest.raises(ValueError) as fresh:
        single_idea.refuse_halo(halo, "older toy", ["older null"])
    folder = _parent(tmp_path / "run", _as_saved(isovector, halo))
    before = sorted(p.name for p in folder.iterdir())
    client = Provider()
    with pytest.raises(ValueError) as refused:
        promote.promote(folder, [isovector.request.candidates[0].label], llm=client)
    assert str(refused.value) == str(fresh.value) and client.sent == 0
    assert sorted(p.name for p in folder.iterdir()) == before                # no record, child or choice


def test_the_promote_command_refuses_before_any_provider_is_made(isovector, tmp_path, monkeypatch):
    from adroit.agents import llm
    folder = _parent(tmp_path / "run", _as_saved(isovector, REFUSED["a newer generator"]()))
    monkeypatch.setattr(llm, "client_for", lambda *a, **k: pytest.fail("a provider client was made"))
    out = CliRunner().invoke(cli.app, ["promote", str(folder), isovector.request.candidates[0].label,
                                       "--budget", "1"])
    words = " ".join(out.output.replace("│", " ").split())
    assert out.exit_code == 2 and "nothing is calculated" in words
    assert sorted(p.name for p in folder.iterdir()) == ["result.json"]


def test_a_benchmark_promotion_with_a_native_joint_fit_is_refused_first(isovector, toys, tmp_path):  # noqa: F811
    """With the toy searches registered throughout (HD-04): without the refusal, the builder would be reached."""
    folder = _parent(tmp_path / "run", isovector)
    client = Provider()
    with pytest.raises(ValueError, match="native-joint|native joint"):
        promote.promote(folder, [isovector.request.candidates[0].label], {"native_joint": {"null_experiment": "x"}},
                        llm=client)
    assert client.sent == 0 and sorted(p.name for p in folder.iterdir()) == ["result.json"]


def test_the_childs_own_check_is_the_promotions(isovector):
    """One refusal for both: the child's fresh run (``single_idea._halo_checked``) asks ``refuse_halo``."""
    seen = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(single_idea, "refuse_halo", lambda *a: seen.append(a))
        single_idea._halo_checked(SimpleNamespace(halo=plus(), experiment="older toy", null_modules=["older null"],
                                                  native_joint=None), None)
        promote.refuse_halo(isovector, {})
    assert seen == [(plus(), "older toy", ["older null"], False)] * 2
