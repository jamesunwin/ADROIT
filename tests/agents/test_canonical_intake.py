"""G10's intake agent with the offline fake (``agents.canonical_intake``)."""

import json

from adroit.agents.canonical_intake import CanonicalIntake, PaperModel, source_message
from adroit.agents.llm import FakeLLMClient
from adroit.core.model_spec import ModelSpec
from adroit.evaluation import zoo


def _wino() -> ModelSpec:
    e = next(x for x in zoo.entries() if x.id == "wino_majorana_triplet_bottaro")
    return zoo._spec(e, e.targets[0])


def test_the_message_carries_the_papers_lagrangian_text_and_benchmark():
    text = source_message("A paper", r"\mathcal{L} = …", "(2)", "page text", {"M": 2860})
    assert "equation (2)" in text and "page text" in text and json.dumps({"M": 2860}) in text


def test_a_model_g1_refuses_goes_back_once_with_g1s_reason():
    data = json.loads(_wino().model_dump_json())
    data["fields"][0]["charges"]["hypercharge"] = 0.5            # a Majorana field with hypercharge: refused
    bad = PaperModel(spec=ModelSpec.model_validate(data))
    llm = FakeLLMClient([bad, PaperModel(spec=_wino(), conventions=["Q = T3 + Y/2 halved"])])
    found, refusals = CanonicalIntake(llm).run("the model")
    assert len(refusals) == 1 and found.conventions == ["Q = T3 + Y/2 halved"]
    assert "G1 refuses" in llm.calls[1]["messages"][-1]["content"]
