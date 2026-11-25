"""Hard rule 6: before each paid dispatch, the model, the hard cap and the reserved (largest possible) cost."""

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from adroit.agents.llm import BudgetedLLMClient, BudgetExceeded, LLMClient, preflight, preflight_line


class Answer(BaseModel):
    value: int


def _client(tmp_path, cap: float, sent: list):
    def create(**kw):
        sent.append(kw)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"value": 4}')],
                               usage=SimpleNamespace(input_tokens=100, output_tokens=20))
    raw = LLMClient(model="claude-opus-5-5", max_tokens=128, client=SimpleNamespace(messages=SimpleNamespace(create=create)))
    return BudgetedLLMClient(raw, dollar_budget=cap, ledger_path=tmp_path / "calls.jsonl")


def _ask(llm):
    return llm.complete_structured("Calculate.", [{"role": "user", "content": "2+2"}], Answer)


def test_each_paid_request_is_shown_before_it_is_sent(tmp_path) -> None:
    lines, sent = [], []
    with preflight(lambda line: lines.append((line, len(sent)))):
        llm = _client(tmp_path, 0.25, sent)
    assert _ask(llm).value == 4 and _ask(llm).value == 4
    assert [n for _, n in lines] == [0, 1]                       # each line came before its dispatch
    first, second = (line for line, _ in lines)
    assert first.startswith("paid request: claude-opus-5-5 at api.anthropic.com; reserving up to $")   # the host (AL3-26)
    assert "of the $0.25 hard cap" in first
    assert "committed $0.0000" in first and "committed $0.0000" not in second
    assert "not sent" not in first


def test_a_request_beyond_the_cap_is_shown_as_not_sent_and_is_not_sent(tmp_path) -> None:
    lines, sent = [], []
    with preflight(lines.append):
        llm = _client(tmp_path, 1e-6, sent)
    with pytest.raises(BudgetExceeded):
        _ask(llm)
    assert not sent and lines and lines[0].endswith("this exceeds the cap, so it is not sent")


def test_clients_made_outside_a_preflight_block_show_nothing(tmp_path) -> None:
    sent = []
    llm = _client(tmp_path, 0.25, sent)
    assert llm.announce is None and _ask(llm).value == 4


def test_the_line_states_model_reservation_and_cap() -> None:
    assert preflight_line("m", 0.01234, 0.1, None).endswith("committed $0.1000 of no cap")
    assert "reserving up to $0.0123" in preflight_line("m", 0.01234, 0.0, 1.0)


def test_paid_commands_show_their_start_line_and_preflight(tmp_path, monkeypatch) -> None:
    from typer.testing import CliRunner
    from adroit.agents import llm as llm_module
    from adroit.orchestrator import cli
    from adroit.retrieval import corpus
    sent = []

    def offline(model, max_tokens):
        def create(**kw):
            sent.append(kw)
            return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"name": "x"}')],
                                   usage=SimpleNamespace(input_tokens=100, output_tokens=20))
        return LLMClient(model=model, max_tokens=max_tokens, client=SimpleNamespace(messages=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm_module, "LLMClient", offline)
    monkeypatch.setattr(corpus, "extract_pdf_text", lambda path: "A paper.")
    settings = llm_module.get_settings().model_copy(update={"runs_dir": tmp_path})      # the paid-response ledger
    monkeypatch.setattr(llm_module, "get_settings", lambda: settings)
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF")
    out = CliRunner().invoke(cli.app, ["anomaly", "draft", "--pdf", str(pdf), "--out", str(tmp_path / "d.yaml"),
                                       "--budget", "0.5"])
    assert out.exit_code == 0, out.output
    assert "Opt-in paid command: claude-opus-5-5; hard cap $0.50" in out.output
    assert "AI can make mistakes." in out.output
    assert out.output.index("paid request: claude-opus-5-5 at api.anthropic.com; reserving up to $") < \
        out.output.index("written to")
    assert len(sent) == 1
