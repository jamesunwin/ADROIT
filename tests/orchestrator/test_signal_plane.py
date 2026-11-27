"""The physical signal requirement on Explain a signal's plane (the owner's plan of 2026-11-24, section 2).

The signal assessment at a point is the model's physical prediction there (``physical_fit.predict``: its actual
spectrum and accepted count, only the background profiled), never a fitted amplitude: the first tests use the real CDMS
II Si (2013) search and a vector model. The plane, its headline and its figure are then exercised on a stand-in Track 1
result, every decision through the production code (``single_idea.signal_plane``, ``_with_plane``, ``plots.plane``)."""
import math
from types import SimpleNamespace

import matplotlib
import pytest

from adroit.core.certificate import POLICY, Certificate, Check
from adroit.experiments import registry
from adroit.orchestrator import single_idea as idea
from adroit.parameter_space import assessment as A
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.halo_region import HaloPreset
from adroit.parameter_space.physical_fit import predict
from adroit.parameter_space.verdict import Crossing

matplotlib.use("Agg")
CDMS = "CDMS II Si (2013)"
COUPLINGS = [0.05 * 1.12 ** k for k in range(30)]          # 0.05 to 1.3


@pytest.fixture(scope="module")
def cdms():
    from adroit.inference import signal_fit
    import numpy as np
    module = registry.load_module(CDMS)
    events, _ = module.observations()
    null = float(signal_fit.profile_log_likelihood(0.0, np.zeros(len(events)), module.background_at(events),
                                                   module.background_rate())[0])
    return module, null


def _at(module, null, p) -> A.SignalAssessment:
    return A.signal_at(Spin1Class(), p, module, 0.5, null, experiment=CDMS, halo="the search's published halo")


# --- the signal at a point: the physical prediction, never a fitted amplitude ---------------------------------------

def test_a_good_free_amplitude_fit_does_not_lend_its_strength_to_a_weak_physical_coupling(cdms) -> None:
    """At 10 GeV the free-amplitude reference fit of CDMS II Si is strong (Z > 1); a coupling far too weak to produce
    the events fails the criterion: its own prediction is barely above the background."""
    module, null = cdms
    cls, weak = Spin1Class(), Point(m_chi=10, m_med=1000, g_chi=0.01, g_q=0.25)
    reference = idea._fit_at(module, cls, weak, 10.0, 0.5)
    assert reference.z_local > 1                               # the reference fit at this mass is good
    s = _at(module, null, weak)
    assert s.state == "fails" and s.predicted_events < 0.01 and abs(s.improvement) < 0.1


def test_a_prediction_far_above_the_observed_count_is_not_rescued(cdms) -> None:
    module, null = cdms
    strong = _at(module, null, Point(m_chi=10, m_med=1000, g_chi=2.2, g_q=0.25))     # 3 events seen
    assert strong.state == "fails" and strong.predicted_events > 50 and strong.improvement < -50


def test_a_coupling_near_the_physical_best_fit_meets_the_criterion(cdms) -> None:
    module, null = cdms
    best = max((_at(module, null, Point(m_chi=10, m_med=1000, g_chi=g, g_q=0.25)) for g in COUPLINGS),
               key=lambda s: s.improvement)
    assert best.state == "meets" and best.improvement >= 1 and 1 < best.predicted_events < 10


def test_the_actual_likelihood_decides_not_the_count_alone(cdms) -> None:
    """A heavy mass with its coupling tuned to the same accepted count as the 10 GeV best fit has another recoil
    shape: its assessment is its own likelihood (``predict``), which differs from the light mass's."""
    module, null = cdms
    light = max((_at(module, null, Point(m_chi=10, m_med=1000, g_chi=g, g_q=0.25)) for g in COUPLINGS),
                key=lambda s: s.improvement)
    target = light.predicted_events
    lo, hi = 1e-6, 10.0
    for _ in range(80):                                        # the heavy coupling with the same accepted count
        mid = math.sqrt(lo * hi)
        if predict(Spin1Class(), Point(m_chi=1000, m_med=1000, g_chi=mid, g_q=0.25), module, 0.5).signal_events < target:
            lo = mid
        else:
            hi = mid
    heavy_point = Point(m_chi=1000, m_med=1000, g_chi=math.sqrt(lo * hi), g_q=0.25)
    heavy = _at(module, null, heavy_point)
    assert heavy.predicted_events == pytest.approx(target, rel=1e-3)
    assert heavy.log_l == pytest.approx(predict(Spin1Class(), heavy_point, module, 0.5).log_l, rel=1e-12)
    assert light.state == "meets" and heavy.state == "fails"       # the shape enters: same count, another verdict


def test_a_point_outside_the_models_domain_is_unassessed_with_why(cdms) -> None:
    module, null = cdms
    s = _at(module, null, Point(m_chi=10, m_med=1000, g_chi=9.0, g_q=0.25))
    assert s.state == "unassessed" and "perturbative" in s.reason and s.improvement is None


# --- the plane, its headline and its figure (a stand-in Track 1 result) --------------------------------------------

def _certificate(status: str) -> Certificate:
    return Certificate(claim_kind="thermal_solution", scope="s", computed_status=status, policy=POLICY,
                       checks=[Check(name="root", state="satisfied"), Check(name="thermal_history", state="satisfied"),
                               Check(name="eos_band", state="not_applicable")])


def _t1(halo_label: str):
    """A 3 × 3 plane in (g_chi, m_chi) with two allowed contour roots at 10 GeV: g = 0.37, whose physical prediction
    makes the three events (2ΔlnL ≈ +9), and g = 2.2, which predicts some 77."""
    xs, ys = [0.01, 0.37, 2.2], [5.0, 10.0, 20.0]
    rows = [SimpleNamespace(point=Point(m_chi=y, m_med=1000, g_chi=x, g_q=0.25), excluded={}, omega_h2=0.1)
            for y in ys for x in xs]
    from adroit.parameter_space.scan import PointResult

    def root(g):         # its saved comparisons: one, halo-independent (the dwarfs' J-factors are their own)
        p = Point(m_chi=10, m_med=1000, g_chi=g, g_q=0.25)
        return Crossing(point=p, status="viable", kind="contour", converged=True, halo=halo_label,
                        nominal_status="viable", certificate=_certificate("viable"),
                        evaluation=PointResult(point=p, omega_h2=0.12, dd_kind="none", dd_sigma_cm2=0.0, dd_limit_cm2=None,
                                               excluded={"gamma rays (Fermi-LAT dwarfs)": False}))
    roots = [root(g) for g in (0.37, 2.2)]
    request = SimpleNamespace(x=SimpleNamespace(parameter="g_chi", log=True), y=SimpleNamespace(parameter="m_chi",
                              log=True), model_class=Spin1Class())
    scan = SimpleNamespace(points=rows, xs=xs, ys=ys, request=request)
    verdict = SimpleNamespace(crossings=roots, target=0.12)
    return SimpleNamespace(scan=scan, verdict=verdict)


def _request(halo, relic_fraction=1.0):
    return SimpleNamespace(experiment=CDMS, halo=halo, spec=SimpleNamespace(name="toy", relic_fraction=relic_fraction))


@pytest.mark.parametrize("halo, label, row", [
    ("benchmark", "", "explains_one_halo"),
    ("published", "", "explains_one_halo"),
    (HaloPreset(), "allowed throughout the tested halo region", "explains_published_halo"),
])
def test_a_known_thermal_intersection_is_recovered_with_its_halo_assignment(cdms, halo, label, row) -> None:
    """The positive control: the root whose physical coupling makes the events meets the criterion and survives,
    so the plane recovers a joint explanation; the strong root over-predicts and does not explain the signal. Over
    the halo region the signal (at the published halo) and the constraints rest on different halos: qualified."""
    from adroit.core import halo_choice
    module, _ = cdms
    halo = halo_choice.fixed() if halo == "benchmark" else halo
    plane = idea.signal_plane(_request(halo), Spin1Class(), module, 0.5, _t1(label))
    assert [a.signal.state for a in plane.crossings] == ["meets", "fails"]
    assert plane.joint == [row, "does_not_explain"]
    level, text = idea._with_plane("undetermined", "the band's fits are unresolved", plane)
    assert level == ("viable" if row == "explains_one_halo" else "viable_pending")
    assert "1 of 2 thermal crossings meets the signal criterion" in text


def test_a_plane_without_a_physical_signal_resolves_no_joint_explanation(cdms, monkeypatch) -> None:
    """The negative control: every point's physical prediction fails the criterion (the coupling range is too weak,
    whatever the free-amplitude fit says): no joint explanation, the headline unchanged but for the plane's words."""
    module, _ = cdms
    monkeypatch.setattr(A, "signal_at", lambda *a, **k: A.judge_signal(-10.0, -10.0, 1e-9, experiment=CDMS, halo="h"))
    plane = idea.signal_plane(_request("published"), Spin1Class(), module, 0.5, _t1(""))
    assert set(plane.joint) == {"does_not_explain"} and {g.state for g in plane.grid} == {"fails"}
    level, text = idea._with_plane("undetermined", "the band's fits are unresolved", plane)
    assert level == "undetermined" and text.endswith("no joint thermal explanation was resolved there")


def test_a_fraction_of_the_dark_matter_is_not_silently_joined_to_an_all_dark_matter_fit(cdms) -> None:
    module, _ = cdms
    plane = idea.signal_plane(_request("published", relic_fraction=0.5), Spin1Class(), module, 0.5, _t1(""))
    assert not plane.same_halo and "fraction" in plane.assignment
    assert plane.joint[0] == "unresolved_halo"                  # one halo, but not the signal's density assignment


def test_the_figure_draws_the_signal_and_the_joint_readings_from_the_stored_plane(cdms, tmp_path, monkeypatch) -> None:
    from adroit.parameter_space import plots
    import matplotlib.axes
    module, _ = cdms
    t1 = _t1("")
    plane = idea.signal_plane(_request("published"), Spin1Class(), module, 0.5, t1)
    labels = []
    real = matplotlib.axes.Axes.legend
    monkeypatch.setattr(matplotlib.axes.Axes, "legend", lambda self, handles=(), **k: (
        labels.extend(h.get_label() for h in handles), real(self, handles=handles, **k))[1])
    stored = SimpleNamespace(band=[], signal_plane=plane)
    plots.plane(t1.scan, t1.verdict, tmp_path / "plane.png", **idea.plane_overlays(stored))
    assert (tmp_path / "plane.png").exists()
    assert not any(label.startswith("meets the signal criterion") for label in labels)   # off by default (2026-11-26)
    labels.clear()
    plots.plane(t1.scan, t1.verdict, tmp_path / "plane.png", signal_region=True, **idea.plane_overlays(stored))
    assert any(label.startswith("meets the signal criterion") for label in labels)
    assert "relic contour: a joint thermal explanation of the signal" in labels
    assert "relic contour: does not explain the signal" in labels


# --- R9-05 (the signal/DD audit): "each search's published halo" is one halo only where the halos are the same --------

@pytest.mark.parametrize("decided_by, same", [("LZ WS2022+WS2024", False), (CDMS, True)])
def test_published_halos_are_compared_not_assumed_equal(cdms, decided_by, same) -> None:
    """CDMS II Si (v₀ 220 km/s) and LZ (v₀ 238 km/s) publish different halos: a plane whose points LZ decided is not
    "the signal and the constraints at the same single halo"; one decided by the signal search itself is."""
    module, _ = cdms
    t1 = _t1("")
    evaluation = SimpleNamespace(dd_channels=[SimpleNamespace(limit=SimpleNamespace(source=decided_by))],
                                 excluded={})
    t1.verdict.crossings = [c.model_copy(update={"evaluation": None}) for c in t1.verdict.crossings]
    for c in t1.verdict.crossings:
        object.__setattr__(c, "evaluation", evaluation)
    plane = idea.signal_plane(_request("published"), Spin1Class(), module, 0.5, t1)
    assert plane.same_halo is same
    assert plane.joint[0] == ("explains_one_halo" if same else "unresolved_halo")
    if not same:
        assert "LZ WS2022+WS2024" in plane.constraints_halo and "differ" in plane.constraints_halo



# --- RA-04 (the repairs audit): every halo-dependent comparison counts, not only direct detection's -----------------

def _with_compared(t1, compared: dict | None):
    """The stand-in study's roots with their saved comparisons replaced (None: saved without them)."""
    from adroit.parameter_space.scan import PointResult
    t1.verdict.crossings = [c.model_copy(update={"evaluation": None if compared is None else PointResult(
        point=c.point, omega_h2=0.12, dd_kind="none", dd_sigma_cm2=0.0, dd_limit_cm2=None, excluded=compared)})
        for c in t1.verdict.crossings]
    return t1


@pytest.mark.parametrize("compared, same", [
    ({"capture in the Sun (IceCube)": False}, False),            # the audit's case: capture at the default halo
    ({"γ-ray lines (Fermi-LAT, H.E.S.S.)": False}, False),       # a published Galactic profile, not the local halo
    ({"gamma rays (Fermi-LAT dwarfs)": False, "colliders (CMS)": None}, True),   # nothing halo-dependent
    ({"direct detection": False}, False),                       # RB-03: compared, its limits' sources not saved
    (None, False),                                               # saved without its comparisons: nothing shown
])
def test_every_halo_dependent_comparison_is_compared(cdms, compared, same) -> None:
    module, _ = cdms
    plane = idea.signal_plane(_request("published"), Spin1Class(), module, 0.5, _with_compared(_t1(""), compared))
    assert plane.same_halo is same
    assert plane.joint[0] == ("explains_one_halo" if same else "unresolved_halo")


# --- RB-01: a saved plane is shown with today's reading of its stored points, the change said -------------------------

def test_a_saved_plane_is_read_again_and_the_change_is_said(cdms, monkeypatch) -> None:
    """A plane saved when its first crossing read "excluded", that crossing decided only by a record whose version is
    not known: the report and the plot read it as undecided now, keep its saved signal assessment, and say so."""
    from tests.parameter_space.test_point_assessment import _decided_by
    module, _ = cdms
    t1 = _t1("")
    plane = idea.signal_plane(_request("published"), Spin1Class(), module, 0.5, t1)
    held = _decided_by({"gamma rays (Fermi-LAT dwarfs)": True}, {"fermi-1503.02641-dsph": ""})
    t1.verdict.crossings = [held.model_copy(update={"point": t1.verdict.crossings[0].point}), t1.verdict.crossings[1]]
    old = plane.crossings[0].model_copy(update={"experimental": plane.crossings[0].experimental.model_copy(
        update={"state": "excluded", "excluded_by": ["gamma rays (Fermi-LAT dwarfs)"]})})
    saved = plane.model_copy(update={"crossings": [old, plane.crossings[1]], "joint": ["excluded", plane.joint[1]]})
    result = SimpleNamespace(signal_plane=saved, track1=t1, band=[], request=SimpleNamespace(experiment=CDMS))
    assert idea.plane_overlays(result)["joint"][0] == "unresolved_experiment"     # what the plot draws
    assert any("Read again with the current reader" in line for line in idea.signal_plane_section(result))
    text = "\n".join(idea.signal_plane_section(result))     # RE-04: the hatching it describes is what is drawn
    assert "hatched region is where" not in text and "experimental exclusions" in text
    now, changed = idea.current_plane(result)
    assert changed == [0] and now.joint[0] == "unresolved_experiment"
    assert now.crossings[0].signal == saved.crossings[0].signal                   # the saved calculation, kept


@pytest.mark.parametrize("compared, same", [
    ({"direct detection": False}, False),                  # legacy DD, its limits' sources not saved
    ({"capture in the Sun (IceCube)": False}, False),       # an older capture plane
    ({"gamma rays (Fermi-LAT dwarfs)": False}, True),       # halo-independent: the saved flag stands
])
def test_a_saved_planes_common_halo_is_established_again_from_its_points(cdms, compared, same) -> None:
    """RC-04 (the second recheck): a plane saved with "the same single halo" whose points' evidence does not establish
    it had kept the flag, and its regenerated report said "a thermal explanation ... at the same single halo"."""
    module, _ = cdms
    t1 = _t1("")
    saved = idea.signal_plane(_request("published"), Spin1Class(), module, 0.5, t1)
    assert saved.same_halo and saved.joint[0] == "explains_one_halo"           # as it was saved
    result = SimpleNamespace(signal_plane=saved, track1=_with_compared(t1, compared), band=[],
                             request=SimpleNamespace(experiment=CDMS))
    now, changed = idea.current_plane(result)
    assert now.same_halo is same
    assert now.joint[0] == ("explains_one_halo" if same else "unresolved_halo") and (changed == [] if same else 0 in changed)
    text = "\n".join(idea.signal_plane_section(result))
    assert ("at the same single halo" in text) is same
