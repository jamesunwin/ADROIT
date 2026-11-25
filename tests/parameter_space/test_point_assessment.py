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
