from adroit.agents.direct import DirectAnswer, DirectAgent
from adroit.agents.llm import CACHE_SPLIT, FakeLLMClient
from adroit.evaluation import baselines, injection
from tests.evaluation.conftest import TOY


def test_the_cases_are_the_first_injection_cases_in_their_own_halves(toy_target) -> None:
    cases = baselines.cases(per_point=2)
    assert len(cases) == 2 * 2 and all(c.inputs["index"] < 2 for c in cases)
    by_id = {c.id: c.half for c in injection.cases()}
    assert all(by_id[c.id] is c.half for c in cases)


def test_the_prompt_holds_the_candidates_and_the_events_but_not_the_answer(toy_target) -> None:
    case = baselines.cases(per_point=1)[0]
    k, events = injection.draw(case)
    text = baselines.case_text(case, events)
    assert f"{events.size} events observed" in text and "Toy search" in text and "target Toy" in text
    assert injection.table(TOY)[0][k] not in text
    legend = baselines.candidate_text(TOY)
    assert "O1s@5, O1v@5, O3s@50" in legend and "O3:" in legend


def test_a_scripted_model_is_scored_like_the_system(toy_target) -> None:
    cases = baselines.cases(per_point=3)
    answers = [DirectAnswer(best="O3s@50", plausible=["O3s@50", "O9s@1"]) for _ in cases]
    fake = FakeLLMClient(answers)
    suite = baselines.suite(DirectAgent(fake, model="fake"), per_point=3)
    assert suite.name == "direct_prompting_fake"
    results = [suite.run_case(c) for c in cases]
    for r in results:
        assert r.metrics["best"] == "O3s@50" and r.metrics["invented"] == 1 and r.metrics["top_set_size"] == 1
        assert r.metrics["exact"] is (r.metrics["injected"] == "O3s@50")
    assert CACHE_SPLIT in fake.calls[0]["messages"][0]["content"]
    assert "all, exact" in suite.summarise(results, cases)


def test_the_cases_interleave_so_a_partial_run_is_balanced(toy_target) -> None:
    cases = baselines.cases(per_point=3)
    assert [c.inputs["index"] for c in cases[:2]] == [0, 0] and {c.inputs["events"] for c in cases[:2]} == {5, 50}
