"""The post-review audit's PR-09: discovery read any current review as "signed", so a record a language model had
checked read "Verified; it still needs validating and binding". A model's check is "checked", with the model named,
bound and unbound; a person's review is "signed" as before."""
from types import SimpleNamespace

import pytest

from adroit.constraints import experimental_review
from adroit.core.pricing import model_name
from adroit.orchestrator import constraint_discovery as cd
from adroit.orchestrator.discovery_cli import _review_text
from adroit.ui.discovery import guidance

MODEL = "claude-fable-5-1"


def candidate():
    return SimpleNamespace(category="missing_supported", acquisition=SimpleNamespace(status="retrieved", revision=""),
                           draft="exp:draft@1", result_id="r1")


@pytest.mark.parametrize("by_model", [False, True])
@pytest.mark.parametrize("bound", [False, True])
def test_a_models_check_is_named_and_a_persons_review_is_signed(monkeypatch, by_model, bound):
    review = SimpleNamespace(checked_by_model=MODEL if by_model else "")
    monkeypatch.setattr(experimental_review, "current_review", lambda *a, **k: review)
    service = cd.Discovery.__new__(cd.Discovery)
    service.catalog = None
    monkeypatch.setattr(cd.Discovery, "bindings", lambda self, c: ["binding"] if bound else [])
    states = service.states(candidate())
    assert states["review"] == ("checked" if by_model else "signed")
    assert states["review_by"] == (MODEL if by_model else "")
    said, _ = guidance({"category": "missing_supported", "states": states,
                        "acquisition": {"status": "retrieved", "reason": ""}, "missing": ""})
    if by_model:
        assert f"checked by {model_name(MODEL)}, not by a person".lower() in said.lower()
        assert _review_text(states) == f"checked by {model_name(MODEL)}, not by a person"
    else:
        assert "not by a person" not in said and _review_text(states) == "signed"
