"""The shared point assessment (the owner's plan of 2026-11-24, section 1): four questions kept apart, and one decision
table for a joint thermal explanation of a signal (``assessment.joint``). The saved vector study's 20 pending thermal
points (``tests/fixtures/vector_dd_pending.json.gz``, a compact copy of
``runs/track1_higgs_portal_vector_20261120-085132_e25f459f``) are read through the production reader."""
import gzip
import json
from pathlib import Path

import pytest

from adroit.parameter_space import assessment as A
from adroit.parameter_space.verdict import Crossing

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _vector() -> list[Crossing]:
    data = json.load(gzip.open(FIXTURES / "vector_dd_pending.json.gz"))
    return [Crossing.model_validate(c) for c in data["pending_crossings"]]


def _assessment(signal="meets", thermal="satisfied", experimental="not_excluded", regional="allowed_throughout",
                by=("direct detection",)) -> A.PointAssessment:
    s = None if signal is None else A.judge_signal(*{"meets": (-10.0, -12.0), "fails": (-12.0, -12.0),
                                                     "unassessed": (None, -12.0)}[signal], 3.0, experiment="LZ",
                                                   halo="published")
    return A.PointAssessment(
        signal=s, thermal=A.ThermalAssessment(state=thermal),
        experimental=A.ExperimentalAssessment(state=experimental, halo=A.CENTRE,
                                              excluded_by=list(by) if experimental == "excluded" else []),
        regional=A.RegionalAssessment(state=regional, detail=regional))


# --- question 1 ---------------------------------------------------------------------------------------------------------

def test_the_signal_criterion_keeps_its_sign_and_its_missing_cases() -> None:
    meets = A.judge_signal(-10.0, -10.5, 4.0, experiment="LZ", halo="published")
    assert meets.state == "meets" and meets.improvement == pytest.approx(1.0)
    worse = A.judge_signal(-14.0, -10.0, 40.0, experiment="LZ", halo="published")
    assert worse.state == "fails" and worse.improvement == pytest.approx(-8.0)      # negative, retained
    for log_l in (None, float("nan"), float("inf")):
        missing = A.judge_signal(log_l, -10.0, None, experiment="LZ", halo="published")
        assert missing.state == "unassessed" and missing.improvement is None and missing.reason


# --- the decision table -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kwargs, same_halo, row", [
    (dict(signal=None), True, "unresolved_signal"),
    (dict(signal="unassessed"), True, "unresolved_signal"),
    (dict(signal="fails", experimental="excluded"), True, "does_not_explain"),     # failing the signal is not exclusion
    (dict(thermal="failed"), True, "not_thermal"),
    (dict(thermal="unknown"), True, "unresolved_thermal"),
    (dict(experimental="excluded", regional="incomplete"), True, "excluded"),
    (dict(experimental="undecided"), True, "unresolved_experiment"),
    (dict(regional="halo_sensitive"), True, "unresolved_halo"),
    (dict(regional="incomplete"), True, "unresolved_halo"),
    (dict(regional="one_halo"), True, "explains_one_halo"),
    (dict(regional="one_halo"), False, "unresolved_halo"),      # one halo for the constraints, another for the signal
    (dict(), True, "explains"),
    (dict(), False, "explains_published_halo"),                  # never silently a halo-robust joint claim
])
def test_every_row_of_the_decision_table(kwargs, same_halo, row) -> None:
    found, why = A.joint(_assessment(**kwargs), same_halo)
    assert found == row and why
    assert (found in A.EXPLAINS) == (row in ("explains", "explains_one_halo"))


def test_a_signal_and_relic_pass_but_a_search_excludes_names_the_search() -> None:
    row, why = A.joint(_assessment(experimental="excluded", regional="excluded_throughout"), True)
    assert row == "excluded" and why == "excluded by direct detection throughout the tested halo region"


# --- the saved vector study ---------------------------------------------------------------------------------------------

def test_the_vectors_central_exclusions_are_read_and_qualified() -> None:
    """17 of the 20 pending thermal points are excluded by direct detection at the region's centre; 12 with the halo
    coverage incomplete and 5 halo-sensitive. Each keeps its central exclusion, qualified, never a robust one."""
    found = [(c, A.from_crossing(c)) for c in _vector()]
    assert len(found) == 20
    central = [(c, a) for c, a in found if a.experimental.state == "excluded"]
    assert len(central) == 17 and all("direct detection" in a.experimental.excluded_by for _, a in central)
    regions = [a.regional.state for _, a in central]
    assert regions.count("incomplete") == 12 and regions.count("halo_sensitive") == 5
    for c, a in central:
        words = A.experimental_words(a)
        assert words.startswith("excluded at the central SHM by ") and "direct detection" in words
        assert ("halo robustness incomplete" in words) == (a.regional.state == "incomplete")
        assert c.status == "pending" and a.thermal.state == "satisfied"      # the stored status is as saved
    rest = [(c, a) for c, a in found if a.experimental.state != "excluded"]
    assert sorted(round(c.point.m_chi, 2) for c, _ in rest) == [60.87, 61.58, 10000.0]
    assert all(A.experimental_words(a) == "" for _, a in rest)


def test_the_88_gev_point_is_excluded_at_the_centre_not_thereby_throughout() -> None:
    c = next(c for c in _vector() if abs(c.point.m_chi - 88.59) < 0.01)
    a = A.from_crossing(c)
    assert a.experimental.state == "excluded" and a.regional.state == "incomplete"
    assert c.evaluation.ratios["direct detection"] == pytest.approx(1111.33, rel=1e-4)
    assert A.joint(a.model_copy(update={"signal": A.judge_signal(-1.0, -2.0, 1.0, experiment="x", halo="y")}),
                   True)[0] == "excluded"


# --- R9-01 (the signal/DD audit): an open experimental prerequisite is never read as a joint explanation -------------

def _certified(excluded: bool, region: str = ""):
    """A thermal point certified by the production certifier with a record whose saved version is unknown (the
    audit's Fermi-LAT dwarf case): the certificate leaves it pending."""
    from adroit.core.certificate import Check, nominal_eos_check
    from adroit.parameter_space import certification as C
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.scan import PointResult
    p = Point(m_chi=100, m_med=1000, g_chi=.1, g_q=.1)
    ev = PointResult(point=p, omega_h2=.12, dd_kind="SI", dd_sigma_cm2=1e-46, dd_limit_cm2=1e-45,
                     excluded={"direct detection": excluded, "Fermi-LAT dwarf galaxies": False},
                     records={"fermi-1503.02641-dsph": ""})
    c = Crossing(point=p, status="excluded" if excluded else "viable", kind="contour", evaluation=ev, halo=region,
                 nominal_status="excluded" if excluded else "viable", converged=True,
                 nominal_excluded_by=["direct detection"] if excluded else [],
                 excluded_by=["direct detection"] if excluded else [])
    return C.certify(c, "thermal_solution", "control", [Check(name="root", state="satisfied"),
                                                        Check(name="thermal_history", state="satisfied"),
                                                        nominal_eos_check()])


def test_a_certificate_blocked_point_is_not_a_joint_explanation() -> None:
    from adroit.orchestrator.single_idea import _with_plane
    c = _certified(excluded=False)
    assert c.status == "pending" and c.certificate.computed_status == "viable"
    a = A.from_crossing(c, A.judge_signal(-1, -2, 1, experiment="control", halo="fixed"))
    assert a.experimental.state == "undecided" and a.experimental.qualifications
    row, why = A.joint(a, True)
    assert row == "unresolved_experiment" and "version" in why                 # the blocking reason, shown
    plane = A.SignalPlane(experiment="control", halo="fixed", constraints_halo="fixed", same_halo=True, null_log_l=-2,
                          grid=[], crossings=[a], joint=[row])
    assert _with_plane("undetermined", "fixture", plane) != "viable"


def test_an_exclusion_with_an_unrelated_open_record_stays_excluded_and_says_so() -> None:
    """The positive control: an independently supported direct-detection exclusion is not erased by an incomplete
    gamma-ray record, but its words carry the open prerequisite."""
    c = _certified(excluded=True)
    a = A.from_crossing(c, A.judge_signal(-1, -2, 1, experiment="control", halo="fixed"))
    row, why = A.joint(a, True)
    assert a.experimental.state == "excluded" and row == "excluded"
    assert "direct detection" in why and "open:" in why


def test_a_certificate_without_its_thermal_checks_is_not_thermal() -> None:
    from adroit.core.certificate import POLICY, Certificate
    from adroit.parameter_space.classes import Point
    c = Crossing(point=Point(m_chi=100, m_med=1000, g_chi=.1, g_q=.1), status="viable", kind="contour",
                 certificate=Certificate(claim_kind="thermal_solution", scope="one point", policy=POLICY,
                                         computed_status="viable", checks=[]))
    a = A.from_crossing(c, A.judge_signal(-1, -2, 1, experiment="control", halo="fixed"))
    assert a.thermal.state == "unknown" and any("root" in r for r in a.thermal.reasons)
    assert A.joint(a, True)[0] == "unresolved_thermal"


# --- RA-01 (the repairs audit): an exclusion stands only on a deciding comparison whose records are established -------

def _decided_by(deciders: dict[str, bool], records: dict[str, str], region: str = ""):
    """A thermal point certified by the production certifier, excluded at its reference halo by ``deciders`` (constraint
    -> excluded), having read ``records`` (id -> version; "" not known)."""
    from adroit.core.certificate import Check, nominal_eos_check
    from adroit.parameter_space import certification as C
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.scan import PointResult
    p = Point(m_chi=100, m_med=1000, g_chi=.1, g_q=.1)
    by = [k for k, v in deciders.items() if v]
    ev = PointResult(point=p, omega_h2=.12, dd_kind="SI", dd_sigma_cm2=1e-46, dd_limit_cm2=1e-45,
                     excluded={"direct detection": False, **deciders}, ratios={k: 2.0 for k in by}, records=records)
    c = Crossing(point=p, status="excluded", kind="contour", evaluation=ev, halo=region, nominal_status="excluded",
                 nominal_excluded_by=by, excluded_by=by, converged=True)
    return C.certify(c, "thermal_solution", "control", [Check(name="root", state="satisfied"),
                                                        Check(name="thermal_history", state="satisfied"),
                                                        nominal_eos_check()])


def _signal():
    return A.judge_signal(-1, -2, 1, experiment="control", halo="fixed")


@pytest.mark.parametrize("region", ["", "halo coverage incomplete"])
def test_an_exclusion_decided_only_by_an_unknown_record_is_undecided_everywhere(region, tmp_path, monkeypatch) -> None:
    """The audit's case: Fermi-LAT dwarfs alone exclude (ratio 2) and their record's version is not known. The point
    must not read excluded in the assessment, the joint reading, the point's status words, or the plane's markers."""
    import matplotlib
    import matplotlib.axes
    from types import SimpleNamespace
    from adroit.parameter_space import certification as C
    from adroit.parameter_space import plots
    c = _decided_by({"gamma rays (Fermi-LAT dwarfs)": True}, {"fermi-1503.02641-dsph": ""}, region)
    assert c.status == "pending" and c.certificate.computed_status == "excluded"
    a = A.from_crossing(c, _signal())
    assert a.experimental.state == "undecided" and not a.experimental.excluded_by
    assert "fermi-1503.02641-dsph" in a.experimental.qualifications[0]
    row, why = A.joint(a, True)
    assert row == "unresolved_experiment" and "fermi-1503.02641-dsph" in why
    assert A.experimental_words(a) == "" and C.central_exclusion(c) == ""
    assert "excluded" not in C.status_words(c).split(" (")[0]
    labels = []
    real = matplotlib.axes.Axes.legend
    monkeypatch.setattr(matplotlib.axes.Axes, "legend", lambda self, handles=(), **k: (
        labels.extend(h.get_label() for h in handles), real(self, handles=handles, **k))[1])
    request = SimpleNamespace(x=SimpleNamespace(parameter="m_chi", log=True),
                              y=SimpleNamespace(parameter="g_chi", log=True), model_class=SimpleNamespace(name="x"))
    scan = SimpleNamespace(points=[SimpleNamespace(excluded={}, omega_h2=None) for _ in range(9)],
                           xs=[50.0, 100.0, 300.0], ys=[0.01, 0.1, 1.0], request=request)
    plots.plane(scan, SimpleNamespace(crossings=[c], target=0.12), tmp_path / "p.png")
    assert not any("excluded at" in x for x in labels)


def test_an_independently_supported_exclusion_stands_on_its_own_decider() -> None:
    """Direct detection (records established) and Fermi-LAT dwarfs (record unknown) both exclude: the point stays
    excluded, by direct detection only, with the open record named."""
    c = _decided_by({"gamma rays (Fermi-LAT dwarfs)": True, "LHC dijet resonances (CMS, ATLAS)": True},
                    {"fermi-1503.02641-dsph": "", "cms-1806.00843-dijet": "abc"})
    a = A.from_crossing(c, _signal())
    assert a.experimental.state == "excluded"
    assert a.experimental.excluded_by == ["LHC dijet resonances (CMS, ATLAS)"]
    assert "fermi-1503.02641-dsph" in A.experimental_words(a)


def test_a_record_the_table_cannot_place_qualifies_every_comparison() -> None:
    c = _decided_by({"LHC dijet resonances (CMS, ATLAS)": True}, {"a-personal-record": ""})
    assert A.from_crossing(c, _signal()).experimental.state == "undecided"


def test_every_record_is_placed_with_comparisons_a_scan_reports() -> None:
    """The table (``constraints.record_constraints``) lists every record in ``records.yaml``, by the constraint names a
    scan reports (``checklist.ITEM_OF``)."""
    import yaml
    from pathlib import Path
    import adroit
    from adroit.constraints.record_constraints import COMPARISONS, NOT_A_COMPARISON
    from adroit.orchestrator.checklist import ITEM_OF
    data = yaml.safe_load((Path(adroit.__file__).parent / "constraints/data/records.yaml").read_text())
    ids = {r["id"] for r in (data["records"] if isinstance(data, dict) else data)}
    assert ids == set(COMPARISONS) | set(NOT_A_COMPARISON), sorted(ids ^ (set(COMPARISONS) | set(NOT_A_COMPARISON)))
    assert {n for names in COMPARISONS.values() for n in names} <= set(ITEM_OF)


# --- RB-01 (the recheck): the combined decider, a shared theory record, grid rows, plot shading, saved planes --------

def _evaluation(excluded: dict, ratios: dict, records: dict):
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.scan import PointResult
    return PointResult(point=Point(m_chi=100, m_med=1000, g_chi=.1, g_q=.1), omega_h2=.12, dd_kind="SI",
                       dd_sigma_cm2=1e-46, dd_limit_cm2=1e-45, excluded=excluded, ratios=ratios, records=records)


@pytest.mark.parametrize("mode", ["cuts", "combined"])
def test_a_comparison_on_an_unknown_record_decides_nothing_in_either_mode(mode) -> None:
    """The recheck's combined case: Fermi-LAT dwarfs alone, ratio 2, record version unknown. In cut mode it had been
    left to the certificate; in combined mode the combination named "the combined likelihood (r = 2.00)" excluded.
    Now neither excludes: the point is pending, the record named."""
    from adroit.parameter_space import verdict as V
    from adroit.parameter_space.likelihood import LikelihoodSettings
    r = _evaluation({"gamma rays (Fermi-LAT dwarfs)": True}, {"gamma rays (Fermi-LAT dwarfs)": 2.0},
                    {"fermi-1503.02641-dsph": ""})
    c = V.classify(None, r, LikelihoodSettings() if mode == "combined" else None)
    assert c.status != "excluded" and not c.excluded_by
    assert any("fermi-1503.02641-dsph" in p for p in c.pending)
    assert V.established_exclusions(r) == {"gamma rays (Fermi-LAT dwarfs)": None}       # what a plot may shade


def test_the_combination_stands_on_its_established_comparisons() -> None:
    """Combined, a dijet ratio of 3 (record known) excludes whatever the unknown Fermi record's ratio; the combined
    decider is then the combination without Fermi."""
    from adroit.parameter_space import verdict as V
    from adroit.parameter_space.likelihood import LikelihoodSettings
    r = _evaluation({"gamma rays (Fermi-LAT dwarfs)": True, "LHC dijet resonances (CMS, ATLAS)": True},
                    {"gamma rays (Fermi-LAT dwarfs)": 2.0, "LHC dijet resonances (CMS, ATLAS)": 3.0},
                    {"fermi-1503.02641-dsph": "", "cms-1806.00843-dijet": "abc"})
    c = V.classify(None, r, LikelihoodSettings())
    assert c.status == "excluded" and "without gamma rays (Fermi-LAT dwarfs)" in c.excluded_by[0]


def test_a_saved_combined_decider_on_an_unknown_record_is_undecided() -> None:
    """A crossing saved with "the combined likelihood (r = 2.00)" as its decider, its only comparison reading a record
    of unknown version: the reader no longer accepts the aggregate as an independent experiment."""
    c = _decided_by({"gamma rays (Fermi-LAT dwarfs)": True}, {"fermi-1503.02641-dsph": ""}, "halo coverage incomplete")
    c = c.model_copy(update={"nominal_excluded_by": ["the combined likelihood (r = 2.00)"],
                             "excluded_by": ["the combined likelihood (r = 2.00)"]})
    from adroit.parameter_space import certification as C
    a = A.from_crossing(c, _signal())
    assert a.experimental.state == "undecided" and C.central_exclusion(c) == ""
    assert A.joint(a, True)[0] == "unresolved_experiment"


def test_a_shared_theory_record_qualifies_both_comparisons_that_read_it() -> None:
    """LHCb's B → K a (a → μμ) comparison reads the invisible decay's record for its form factors: that record's
    unknown version leaves it undecided too (it had been tied to the invisible comparison only)."""
    from adroit.parameter_space import verdict as V
    name = "flavour (B → K a, a → μμ)"
    r = _evaluation({name: True}, {name: 164.3}, {"lhcb-1612.07818-b-to-k-mumu": "abc", "flavour-b-to-k-invisible": ""})
    assert V.classify(None, r).status != "excluded"
    c = _decided_by({name: True}, {"lhcb-1612.07818-b-to-k-mumu": "abc", "flavour-b-to-k-invisible": ""})
    assert A.from_crossing(c, _signal()).experimental.state == "undecided"


def test_an_independent_exclusion_reads_excluded_in_the_status_words_too() -> None:
    """The safe opposite inconsistency: no halo region, dijet (record known) excludes, Fermi's record unknown. The
    assessment says excluded by dijet; the status words had said "pending (computed: excluded)"."""
    from adroit.parameter_space import certification as C
    c = _decided_by({"gamma rays (Fermi-LAT dwarfs)": True, "LHC dijet resonances (CMS, ATLAS)": True},
                    {"fermi-1503.02641-dsph": "", "cms-1806.00843-dijet": "abc"})
    assert c.status == "pending"
    words = C.status_words(c)
    assert words.startswith("excluded by LHC dijet") and "fermi-1503.02641-dsph" in words
    assert C.experimental_exclusion(c) == ["LHC dijet resonances (CMS, ATLAS)"]


def test_every_record_edge_the_code_declares_is_in_the_table() -> None:
    """Each ``_blocked(name, record)`` gate in the searches and ``searches.outcomes``' record map is an edge of the
    table (RB-01: the shared form-factor record's second edge had been missing; an id check could not see it)."""
    import ast
    import inspect
    from pathlib import Path
    import adroit
    from adroit.constraints.record_constraints import COMPARISONS
    from adroit.parameter_space import resonances, searches
    names = {**{k: v for k, v in vars(searches).items() if isinstance(v, str)},
             **{f"resonances.{k}": v for k, v in vars(resonances).items() if isinstance(v, str)},
             **{k: v for k, v in vars(resonances).items() if isinstance(v, str)}}

    def text(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        key = ast.unparse(node)
        return names.get(key)
    edges = set()
    for path in sorted((Path(adroit.__file__).parent / "parameter_space").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and (getattr(node.func, "attr", None) or getattr(node.func, "id", None)) \
                    == "_blocked" and len(node.args) >= 2:
                name, record = text(node.args[0]), text(node.args[1])
                if name and record:
                    edges.add((name, record))
    tree = ast.parse(inspect.getsource(searches.outcomes))
    mapping = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
                   and getattr(n.targets[0], "id", "") == "records")
    for key, value in zip(mapping.keys, mapping.values):
        name = text(key)
        if isinstance(value, ast.List):
            edges |= {(name, text(v)) for v in value.elts if text(v)}
        else:                                      # list(FOUR_MU), list(LINE_RECORDS)
            edges |= {(name, rid) for rid in eval(ast.unparse(value), vars(searches))}
    missing = sorted((n, r) for n, r in edges if n and n not in COMPARISONS.get(r, ()))
    assert len(edges) > 30 and not missing, missing


# --- RC-01 and RC-02 (the second recheck): every halo sample, and an exclusion kept only in the certificate ----------

def _over_region(excluded: dict, ratios: dict, records: dict, sample_outcomes: dict):
    """An evaluation over the halo region: two samples, each with ``sample_outcomes`` (name -> (excluded, ratio))."""
    from adroit.parameter_space import halo_region
    r = _evaluation(excluded, ratios, records)
    samples = [halo_region.HaloPointSample(v0_km_s=v, v_esc_km_s=528.0, rho_gev_cm3=0.4, where="sample",
                                           outcomes={k: halo_region.HaloOutcome(excluded=e, ratio=q)
                                                     for k, (e, q) in sample_outcomes.items()})
               for v in (213.0, 253.0)]
    return r.model_copy(update={"halo": halo_region.HaloEvaluation(region="the tested region", samples=samples,
                                                                   converged=True)})


@pytest.mark.parametrize("mode", ["cuts", "combined"])
@pytest.mark.parametrize("name, record", [("capture in the Sun (IceCube)", "icecube-1612.05949-sd"),
                                          ("gamma rays (Fermi-LAT dwarfs)", "fermi-1503.02641-dsph")])
def test_a_record_of_unknown_version_decides_nothing_at_any_halo(mode, name, record) -> None:
    """The recheck's cases: the comparison repeated at every halo sample had made the point "excluded throughout the
    tested halo region" although its record's version is not known (grid rows, filters, point page, export)."""
    from adroit.parameter_space import verdict as V
    from adroit.parameter_space.likelihood import LikelihoodSettings
    r = _over_region({name: True}, {name: 2.0}, {record: ""}, {name: (True, 2.0)} if "IceCube" in name else {})
    c = V.classify(None, r, LikelihoodSettings() if mode == "combined" else None)
    assert c.status != "excluded" and c.halo != "excluded throughout the tested halo region"
    assert any(record in p for p in c.pending)


def test_a_known_record_still_excludes_throughout_the_region() -> None:
    from adroit.parameter_space import verdict as V
    name = "capture in the Sun (IceCube)"
    r = _over_region({name: True}, {name: 2.0}, {"icecube-1612.05949-sd": "abc"}, {name: (True, 2.0)})
    c = V.classify(None, r)
    assert c.status == "excluded" and c.halo == "excluded throughout the tested halo region"


def _gated_combined(ratios: dict, records: dict, decider: str):
    """A crossing saved as the old producer wrote a gated combined exclusion: every individual cut false, the crossing
    pending with no decider of its own, the combined decider kept only in its certificate."""
    from adroit.core.certificate import Check, nominal_eos_check
    from adroit.parameter_space import certification as C
    from adroit.parameter_space.classes import Point
    ev = _evaluation({k: False for k in ratios}, ratios, records)
    c = Crossing(point=Point(m_chi=100, m_med=1000, g_chi=.1, g_q=.1), status="excluded", kind="contour",
                 evaluation=ev, excluded_by=[decider], converged=True)
    c = C.certify(c, "thermal_solution", "control", [Check(name="root", state="satisfied"),
                                                     Check(name="thermal_history", state="satisfied"),
                                                     nominal_eos_check()])
    assert c.status == "pending" and c.certificate.computed_excluded_by == [decider]
    return c.model_copy(update={"excluded_by": []})


def test_a_saved_combined_exclusion_kept_only_in_its_certificate_is_qualified() -> None:
    """The recheck's RC-02: Fermi and dijet at 0.9 each, Fermi's record unknown; the old combination excluded at
    r = 1.27 and certification moved that decider into the certificate. The reader had read "excluded" with no
    decider and skipped its record check."""
    c = _gated_combined({"gamma rays (Fermi-LAT dwarfs)": 0.9, "LHC dijet resonances (CMS, ATLAS)": 0.9},
                        {"fermi-1503.02641-dsph": "", "cms-1806.00843-dijet": "abc"},
                        "the combined likelihood (r = 1.27)")
    a = A.from_crossing(c, _signal())
    assert a.experimental.state == "undecided" and A.joint(a, True)[0] == "unresolved_experiment"
    assert "fermi-1503.02641-dsph" in a.experimental.qualifications[0]


def test_a_combination_that_left_the_unknown_record_out_stands_and_is_named() -> None:
    """The safe opposite case: two known ratios of 0.9 combine to exclude once the unknown one (0.2) is left out; the
    decider names what it left out, and the reader keeps it, named, in the assessment and the status words alike."""
    from adroit.parameter_space import certification as C
    decider = "the combined likelihood (r = 1.27 without gamma rays (Fermi-LAT dwarfs))"
    c = _gated_combined({"gamma rays (Fermi-LAT dwarfs)": 0.2, "LHC dijet resonances (CMS, ATLAS)": 0.9,
                         "LHC dilepton resonances (ATLAS)": 0.9},
                        {"fermi-1503.02641-dsph": "", "cms-1806.00843-dijet": "a", "atlas-1903.06248-dilepton": "b"},
                        decider)
    a = A.from_crossing(c, _signal())
    assert a.experimental.state == "excluded" and a.experimental.excluded_by == [decider]
    assert C.status_words(c).startswith("excluded by the combined likelihood")


# --- RD-04 (the third recheck): a comparison only the halo samples hold ------------------------------------------------

@pytest.mark.parametrize("mode", ["cuts", "combined"])
def test_a_sample_only_comparison_on_an_unknown_record_decides_nothing(mode) -> None:
    """Central direct detection allows; only the samples hold γ-ray lines, excluding at ratio 2, its record's version
    unknown. Round-tripped through JSON, the point had read "excluded throughout the tested halo region"."""
    from adroit.parameter_space import verdict as V
    from adroit.parameter_space.likelihood import LikelihoodSettings
    from adroit.parameter_space.scan import PointResult
    lines = "γ-ray lines (Fermi-LAT, H.E.S.S.)"
    r = _over_region({"direct detection": False}, {"direct detection": 0.3}, {"fermi-lat-1506.00013-lines": ""},
                     {lines: (True, 2.0)})
    r = PointResult.model_validate_json(r.model_dump_json())
    assert lines in V.unestablished(r)
    c = V.classify(None, r, LikelihoodSettings() if mode == "combined" else None)
    assert c.status != "excluded" and c.halo != "excluded throughout the tested halo region"
    assert any("fermi-lat-1506.00013-lines" in p for p in c.pending)
    known = r.model_copy(update={"records": {"fermi-lat-1506.00013-lines": "abc"}})
    assert V.classify(None, known).halo == "excluded throughout the tested halo region"      # the positive control
