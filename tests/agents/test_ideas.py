from adroit.agents.ideas import MAX_MODELS, IdeaAgent, ModelProposals
from adroit.agents.llm import FakeLLMClient


def test_the_builder_asks_once_for_a_bounded_number_of_models() -> None:
    fake = FakeLLMClient([ModelProposals()])
    IdeaAgent(fake, model="m").run("an idea", n=50)
    content = fake.calls[0]["messages"][0]["content"]
    assert f"up to {MAX_MODELS} models" in content and "an idea" in content
    assert "Do not write interaction terms" in fake.calls[0]["system"]
