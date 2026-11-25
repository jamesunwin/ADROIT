"""A stored certificate reads stale when its policy or its bound data have changed since (the auditor's consolidation audit,
2026-10-25, section D: ``Bound`` held the tables' hashes and the records' ids, but only the policy was compared), and
the history's one-word assessment of a headline's claims (CO-07)."""
from adroit.core.certificate import POLICY, Bound, Certificate, Check, assessment, reading, stale_reasons
from adroit.parameter_space.certification import current_bound, record_fingerprints

A, B = "a" * 64, "b" * 64


def _certificate(**bound) -> Certificate:
    return Certificate(claim_kind="thermal_solution", scope="a root", checks=[Check(name="eos_band", state="satisfied")],
                       bound=Bound(**bound), policy=POLICY)


def test_unchanged_data_and_policy_are_current():
    c = _certificate(eos_tables={"upper": A}, records={"r": "f1"})
    assert stale_reasons(c) == [] and stale_reasons(c, Bound(eos_tables={"upper": A}, records={"r": "f1"})) == []
    assert reading(c, Bound(eos_tables={"upper": A}, records={"r": "f1"})) == "certified"


def test_a_different_table_or_a_changed_record_reads_stale():
    c = _certificate(eos_tables={"upper": A}, records={"r": "f1"})
    assert "upper table is not the one it was certified with" in stale_reasons(
        c, Bound(eos_tables={"upper": B}, records={"r": "f1"}))[0]
    assert stale_reasons(c, Bound(eos_tables={"upper": A}, records={"r": "f2"})) == [
        "the record r changed since it was certified"]
    assert stale_reasons(c, Bound(eos_tables={"upper": A}, records={})) == [
        "the record r cannot be read since it was certified"]
    assert reading(c, Bound(eos_tables={"upper": B}, records={"r": "f1"})).startswith("stale: ")


def test_tables_missing_now_are_not_a_change_of_data():
    """The historical decision stands; the tables it used are named in its bound."""
    c = _certificate(eos_tables={"upper": A})
    assert stale_reasons(c, Bound(eos_tables={"upper": ""})) == []


def test_an_earlier_policy_reads_stale_whatever_the_data():
    c = _certificate().model_copy(update={"policy": "an-earlier-policy"})
    assert stale_reasons(c, Bound()) == ["certified under policy an-earlier-policy, not the current "
                                         f"{POLICY}"]


def test_the_assessment_of_a_headlines_claims():
    current, waiting = _certificate(), Certificate(claim_kind="thermal_solution", scope="a root",
                                                   checks=[Check(name="eos_band", state="unknown")], policy=POLICY)
    stale = current.model_copy(update={"policy": "an-earlier-policy"})
    assert assessment([current]) == "certified" and assessment([current, waiting]) == "not certified"
    assert assessment([current, stale]) == "stale" and assessment([current, None]) == "legacy"
    assert assessment([]) == "legacy"


def test_the_current_bound_reads_the_records_as_they_are():
    record = "dampe-2112.08860-lines"
    found = record_fingerprints([record, "no-such-record"])
    assert len(found[record]) == 64 and found["no-such-record"] == ""
    c = _certificate(records={record: found[record]})
    assert current_bound(c).records == {record: found[record]} and stale_reasons(c, current_bound(c)) == []
