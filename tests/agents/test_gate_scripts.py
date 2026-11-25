"""The G9–G11 gate scripts exit 0 when met, 1 when not, and 3 when stopped at the budget (the audit's AG-4, G12;
``core.receipts``), as every gate script must (the release plan)."""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name, runner", [("g10_intake_gate", "run"), ("g10_intake_gate", "rescore"),
                                          ("g11_benchmark_gate", "run"), ("g11_benchmark_gate", "recheck"),
                                          ("g9_collider_gate", "run")])
@pytest.mark.parametrize("summary, code", [({"gate": True}, 0), ({"gate": False}, 1),
                                           ({"gate": False, "budget_stopped": True}, 3)])
def test_a_gate_scripts_exit_code_says_whether_it_was_met(monkeypatch, tmp_path, name, runner, summary, code):
    module = _script(name)
    if name == "g9_collider_gate" and summary.get("budget_stopped"):
        pytest.skip("G9 is offline: it has no budget")
    monkeypatch.setattr(module, runner, lambda *args, **kwargs: dict(summary))
    flag = {"rescore": ["--rescore"], "recheck": ["--recheck"]}.get(runner, [])
    monkeypatch.setattr(sys, "argv", [name, "--out", str(tmp_path / "out.json"), *flag])
    assert module.main() == code
