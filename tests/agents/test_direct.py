from adroit.agents.direct import MAX_PLAUSIBLE, DirectAgent, DirectAnswer, clean
from adroit.agents.llm import FakeLLMClient


def test_the_agent_asks_once_with_the_candidates_as_a_cached_prefix() -> None:
    fake = FakeLLMClient([DirectAnswer(best="O1s@5", plausible=["O1s@5"])])
    answer = DirectAgent(fake, model="m").run("the candidates", "the events")
    assert answer.best == "O1s@5" and fake.call_count == 1
    content = fake.calls[0]["messages"][0]["content"]
    assert content.startswith("the candidates") and content.endswith("the events")


def test_clean_keeps_the_answer_to_the_list() -> None:
    labels = ["A", "B", "C"]
    best, plausible, invented = clean(DirectAnswer(best="B", plausible=["C", "Z", "B"]), labels)
    assert best == "B" and plausible == ["B", "C"] and invented == ["Z"]
    best, plausible, invented = clean(DirectAnswer(best="Q", plausible=["A"]), labels)
    assert best is None and plausible == ["A"] and invented == ["Q"]


def test_clean_caps_the_plausible_set() -> None:
    labels = [f"L{i}" for i in range(100)]
    _, plausible, _ = clean(DirectAnswer(best="L0", plausible=labels), labels)
    assert len(plausible) == MAX_PLAUSIBLE and plausible[0] == "L0"
