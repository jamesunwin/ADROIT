from adroit.evaluation import limits, lz_tables
from adroit.evaluation.core import CaseResult, Half
from adroit.evaluation.suites import suites


def test_every_suite_is_registered_by_its_name() -> None:
    available = suites()
    assert set(available) == {"injection", "lz_tables", "limits", "historical", "model_zoo"}
    assert all(name == s.name for name, s in available.items())


def test_lz_tables_holds_all_612_entries_split_in_two() -> None:
    cases = lz_tables.cases()
    assert len(cases) == 612 and len({c.id for c in cases}) == 612
    development = sum(c.half is Half.development for c in cases)
    assert 250 < development < 362


def test_lz_tables_summary() -> None:
    results = [CaseResult(case_id="a", passed=True, metrics={"delta": 0.1}),
               CaseResult(case_id="b", passed=False, metrics={"delta": -0.5})]
    out = lz_tables.summarise(results, [])
    assert out["within 0.3σ"] == 0.5 and out["entries"] == 2


def test_limits_trial_masses_keep_the_last_mass() -> None:
    assert limits._every([1.0, 2.0, 3.0, 4.0, 5.0], 2) == [1.0, 3.0, 5.0]
    assert limits._every([1.0, 2.0, 3.0, 4.0], 3) == [1.0, 4.0]
