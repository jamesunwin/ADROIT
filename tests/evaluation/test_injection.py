import numpy as np

from adroit.evaluation import core, injection
from tests.evaluation.conftest import TOY


def test_cases_cover_each_target_and_number_of_events(toy_target) -> None:
    cases = injection.cases()
    assert len(cases) == 2 * 6 and {c.inputs["events"] for c in cases} == {5, 50}


def test_a_case_draws_the_same_events_every_time(toy_target) -> None:
    case = injection.cases()[0]
    k1, e1 = injection.draw(case)
    k2, e2 = injection.draw(case)
    assert k1 == k2 and np.array_equal(e1, e2)
    assert e1.size >= case.inputs["events"]


def test_identical_shapes_share_a_class_and_count_as_recovered(toy_target) -> None:
    classes = injection.classes(TOY, 50)
    assert classes["O1s@5"] == classes["O1v@5"] != classes["O3s@50"]
    for case in injection.cases():
        r = injection.run_case(case)
        if r.metrics["injected"] in ("O1s@5", "O1v@5"):
            assert r.metrics["same_class"] and r.passed      # the two cannot be told apart at any N
            assert r.metrics["in_top_set"] and r.metrics["top_set_size"] >= 2


def test_a_distinct_shape_is_recovered_with_many_events(toy_target) -> None:
    results = [injection.run_case(c) for c in injection.cases() if c.inputs["events"] == 50]
    rising = [r for r in results if r.metrics["injected"] == "O3s@50"]
    assert rising and all(r.metrics["exact"] for r in rising)


def test_the_summary_gives_every_reading(toy_target) -> None:
    cases = injection.cases()
    out = injection.summarise([injection.run_case(c) for c in cases], cases)
    assert {"all, pairwise", "all, class", "all, exact", "all, ΔAIC set"} <= set(out)
    assert any(k.startswith(f"{TOY}, N = 5") for k in out)


def test_the_suite_runs_through_the_harness(toy_target, store) -> None:
    out = core.run(injection.SUITE, store=False)
    assert out.results and all(r.passed is not None for r in out.results)
