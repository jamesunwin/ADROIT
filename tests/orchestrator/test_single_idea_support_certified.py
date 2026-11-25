"""The auditor's consolidation audit (2026-10-25) on the single-idea study: CO-02 (a discovery requirement at a table's
thermal point had arrived after the tables' comparison, leaving a certified headline where the plane is pending),
and CO-01 and CO-03 at a table's point (its own thermal history; its records the nominal claim's). The fit, the
density and the constraints are ``test_single_idea_eos``'s toy; the refinement, the tables, discovery's
qualification, the certificates and the headline are the workflow's own."""
from unittest.mock import patch

import numpy as np
import pytest

from adroit.constraints import relic
from adroit.core.constraint_discovery import DiscoveryCoverage, Requirement
from adroit.orchestrator import constraint_discovery as cd
from adroit.orchestrator import single_idea as si
from adroit.parameter_space.scan import PointResult
from tests.orchestrator import test_single_idea_eos as fixture

RECORD = "dampe-2112.08860-lines"
OUTSIDE = "Ωh² from a freeze-out outside the supported thermal history (toy)"


def _coverage(low: float, high: float) -> DiscoveryCoverage:
    """A discovery assessment with one unresolved relevant constraint over m_χ ∈ [low, high] GeV."""
    return DiscoveryCoverage(session_id="test", assessment_sha256="a" * 64, model_sha256="b" * 64,
                             model_reference="test", searched_at="2026-10-25", requirements=[Requirement(
                                 candidate_id="missing", name="a missing comparison", reference="test:fixture",
                                 constraint_class="indirect", reason="needs a calculation here",
                                 domain={"m_chi": (low, high)})])


def _with_discovery(coverage: DiscoveryCoverage):
    return patch.object(si, "_discovery", lambda *a: (coverage, lambda points: cd.qualify_points(points, coverage, [])))


@pytest.mark.eos_band
@pytest.mark.needs("eos")
@pytest.mark.parametrize("low, high, where", [(19.9, 20.1, "the nominal point"), (20.7, 20.9, "the upper table's"),
                                              (19.1, 19.3, "the lower table's")])
def test_a_discovery_requirement_at_any_supporting_point_keeps_the_headline_pending(tmp_path, low, high, where):
    """CO-02: the nominal point at 20 GeV, the upper table's at 20.83, the lower's at 19.23, all viable and fitting.
    A requirement covering any one of them leaves the nominal claim uncertified and the headline viable pending, as
    the plane has it; the saved pending reasons name it."""
    with _with_discovery(_coverage(low, high)):
        result = fixture._study(tmp_path, excluded_above=100)
    (thermal,) = result.thermal
    assert thermal.status == "pending" and not thermal.certificate.decided, where
    assert result.level == "viable_pending", (where, result.level, result.summary)
    assert any("a missing comparison" in r for r in result.thermal_pending), result.thermal_pending


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_requirement_at_a_table_only_point_is_saved_with_it(tmp_path):
    """CO-02 for a point only a table has (Ωh² = 0.0029 m_χ: the lower table's at 39.8 GeV): qualified by discovery
    before it is added, so the headline's reason says it waits."""
    with _with_discovery(_coverage(39.5, 40.0)):
        result = fixture._study(tmp_path, excluded_above=100, scale=0.0029)
    assert result.level == "undetermined" and "the lower table has a thermal point" in result.summary
    assert "(pending;" in result.summary
    assert result.eos_thermal["lower"][0].status == "pending"


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_an_independent_certified_viable_point_still_establishes_viability(tmp_path):
    """CO-02's control: two nominal thermal points (20 and 40 GeV); a requirement at the first's upper-table point
    (21.25 GeV) leaves it pending, and the second, certified at all three tables, keeps the headline viable."""
    with _with_discovery(_coverage(21.0, 21.5)):
        result = fixture._study(tmp_path, excluded_above=100, masses=(10, 30, 50),
                                nominal=lambda m: float(np.interp(m, [10, 30, 50], [.08, .16, .08])))
    first, second = sorted(result.thermal, key=lambda t: t.m_chi)
    assert first.status == "pending" and second.status == "viable" and second.certificate.decided
    assert result.level == "viable"


def _table_evaluations(monkeypatch, **extra):
    """The toy's evaluations, with ``extra`` fields at every table's point (``relic.current_eos()`` set)."""
    def made(**kwargs):
        return PointResult(**kwargs, **(extra if relic.current_eos() else {}))
    monkeypatch.setattr(fixture, "PointResult", made)


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_table_point_outside_the_supported_history_supports_nothing(tmp_path, monkeypatch):
    """CO-01 here: every table's point has its relic calculation outside the supported thermal history. The nominal
    viable point is not certified across the band (failed), and the headline is viable pending."""
    _table_evaluations(monkeypatch, relic_validity=[OUTSIDE])
    result = fixture._study(tmp_path, excluded_above=100)
    (thermal,) = result.thermal
    eos = thermal.certificate.check("eos_band")
    assert thermal.status == "pending" and eos.state == "failed" and OUTSIDE in eos.reason
    assert result.level == "viable_pending"


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_a_record_used_only_at_the_table_points_is_the_claims_dependency(tmp_path, monkeypatch):
    """CO-03 here: the tables' points used an unverified record, the nominal one did not; the band rests on them, so
    the nominal claim's certificate names the record (with its fingerprint) and says it depends on it."""
    from tests.unsigned_records import used
    _table_evaluations(monkeypatch, unverified_records=[RECORD], records=used(RECORD))
    result = fixture._study(tmp_path, excluded_above=100)
    (thermal,) = result.thermal
    assert thermal.status == "viable" and thermal.certificate.bound.unverified_records == [RECORD]
    assert RECORD in thermal.certificate.bound.records
    assert thermal.certificate.qualifiers == [f"depends on unverified records: {RECORD}"]


def _witness(tmp_path, excluded_above: float = 100):
    """The auditor's CO recheck, CR-04 (2026-10-26): thermal points at 20 and 40 GeV (Ωh² peaked at 30 GeV); a discovery
    requirement at 21–21.5 GeV, where a table's point for the 20 GeV one lies, leaves that one waiting."""
    with _with_discovery(_coverage(21., 21.5)):
        return fixture._study(tmp_path, excluded_above=excluded_above, masses=(10, 30, 50),
                              nominal=lambda m: float(np.interp(m, [10, 30, 50], [.08, .16, .08])))


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_an_independent_certified_witness_is_a_certified_viable_headline(tmp_path):
    """CR-04: one independent, certified viable point establishes the existential claim; the waiting one stays
    visible as waiting but does not un-certify it. The headline's support is saved with it and the history reads
    exactly that."""
    from adroit.orchestrator import study_headline
    from adroit.parameter_space import certification
    result = _witness(tmp_path)
    assert result.level == "viable" and result.rests_on == [1]
    assert [(round(t.m_chi), t.status, t.certificate.decided) for t in result.thermal] == [
        (20, "pending", False), (40, "viable", True)]
    assert study_headline.headline(result.model_dump(mode="json")) == ("VIABLE", "viable", "certified", "")
    assert certification.reading(result.thermal[0].certificate).startswith("not certified: ")


@pytest.mark.needs("eos")
def test_an_excluded_headline_rests_on_every_point_it_decided_on(tmp_path):
    """CR-04's other side: every thermal point excluded (the toy constraint everywhere above 5 GeV); the exclusion
    rests on all of them, so each one's certification counts."""
    result = _witness(tmp_path, excluded_above=5)
    assert result.level == "excluded" and result.rests_on == list(range(len(result.thermal))) == [0, 1]
