"""DM9: the agents on finished results, offline (fake agents, fake literature, fake reference service)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adroit.agents import audit as audit_agent
from adroit.agents.audit import AuditEntry, AuditReport
from adroit.agents.llm import FakeLLMClient
from adroit.agents.scout import ProposedConstraint, ScoutReport
from adroit.agents.variants import VariantChoices, VariantPick
from adroit.orchestrator import agents, assumptions, lagrangian, signal
from adroit.retrieval import literature
from adroit.retrieval import references as refs

DOCS = Path(__file__).resolve().parents[2] / "docs"
TITLE = "Implications of unitarity and gauge invariance for simplified dark matter models"
KNOWN = {"1510.02110": refs.Reference(kind="arxiv", id="1510.02110", title=TITLE, year=2015, verified=True),
         **{i: refs.Reference(kind="arxiv", id=i, title="a real paper ADROIT's code cites", verified=True)
            for i in ("2105.00599", "1612.05949", "2405.13778", "1503.02641", "2301.10731", "2202.03076", "1806.00843")}}


def tools(tmp_path: Path) -> agents.Tools:
    def fetch(q, n):
        return [literature.Abstract(arxiv_id="1510.02110", title=TITLE, year=2015, text="...", query=q)]
    return agents.Tools(resolver=lambda asked: {a.id: KNOWN[a.id] for a in asked if a.id in KNOWN},
                        fetch=fetch, literature_cache=tmp_path / "lit.json")


def scout_report() -> ScoutReport:
    return ScoutReport(proposals=[
        ProposedConstraint(name="unitarity", constraint_class="collider", reference="1510.02110", title=TITLE,
                           applicability="applies_with_assumptions", assumptions=["a Z′ completion, Smith et al. 2019"]),
        ProposedConstraint(name="invented", constraint_class="relic_density", reference="2612.99999", title="Nothing",
                           applicability="needs_calculation", needed_calculation="x")])


def full_audit(inv: assumptions.Inventory) -> AuditReport:
    return AuditReport(entries=[AuditEntry(id=i.id, impact="material", effect="moves the limit (see 9999.12345)")
                                for i in inv.items], additional=["the local density"])


@pytest.mark.needs("diamx", "cresst")
def test_path1_the_report_carries_no_unconfirmed_reference(tmp_path) -> None:
    r = lagrangian.LagrangianResult.model_validate_json((DOCS / "dm8/majorana_scalar/result.json").read_text())
    inv = assumptions.path1(r)
    out = agents.run_path1(r, FakeLLMClient([scout_report(), full_audit(inv)]), tools=tools(tmp_path))
    text = agents.report(out)
    assert out.report_unverified == [] and "9999.12345" not in text and "Smith" not in text
    assert len(out.proposed_records) == 1 and not out.proposed_records[0].usable
    assert out.audit_missing == [] and "Added by the audit agent" in text


@pytest.mark.needs("cresst", "cdmslite")
def test_path2_variants_scout_and_audit(tmp_path) -> None:
    r = signal.SignalResult.model_validate_json((DOCS / "dm6/lz_case.json").read_text())
    inv = assumptions.path2(r)
    picks = VariantChoices(picks=[VariantPick(index=99, rationale="off the menu")])
    llm = FakeLLMClient([picks, scout_report(), full_audit(inv)])
    out = agents.run_path2(r, llm, agents.AgentRequest(scout_leaders=1), tools(tmp_path))
    assert set(out.triggers) == {"L12s@4000", "L12v@4000"} and out.variants == []
    assert out.discarded_picks == ["99: not on the menu"]
    assert len(out.scouting) == 1 and out.report_unverified == []
    assert "## Variants (DM9)" in agents.report(out)


@pytest.mark.needs("cresst", "cdmslite")
def test_the_inventory_is_complete_and_grouped() -> None:
    r = signal.SignalResult.model_validate_json((DOCS / "dm6/lz_case.json").read_text())
    inv = assumptions.path2(r)
    statements = assumptions.text(inv)
    assert len(inv.items) < 80 and "AIC = −Z_joint² + 2k" in statements and "no priors" in statements   # R6: all class members
    assert "(for O01s@1000,d=350" in statements or "O01s@1000,d=350)" in statements
    missing, unknown = audit_agent.complete(AuditReport(entries=[AuditEntry(id="A1", impact="minor", effect="e"),
                                                                 AuditEntry(id="Z9", impact="minor", effect="e")]),
                                            [i.id for i in inv.items])
    assert "A2" in missing and unknown == ["Z9"]


def test_the_literature_queries_and_their_cache(tmp_path) -> None:
    sketch = literature.CandidateSketch(label="x", interaction="anapole", mass_gev=5.0, splitting_kev=100.0,
                                        mediator="a 1 GeV vector", keywords=["anapole"])
    qs = literature.queries(sketch)
    assert qs[0] == 'abs:"dark matter" AND abs:"anapole"' and any("inelastic" in q for q in qs)
    assert any("light dark matter" in q for q in qs)
    calls = []

    def fetch(q, n):
        calls.append(q)
        return [literature.Abstract(arxiv_id="1510.02110", title=TITLE, query=q)]
    found = literature.search(sketch, fetch, tmp_path / "c.json")
    again = literature.search(sketch, fetch, tmp_path / "c.json")
    assert [a.arxiv_id for a in found] == ["1510.02110"] == [a.arxiv_id for a in again]
    assert len(calls) == len(qs)                                    # the second search used the cache


@pytest.mark.parametrize("agent,needle", [("variants", "Choose only from the numbered menu"),
                                          ("scout", "Never cite by author and year alone"),
                                          ("audit", "Address every inventory item by its id")])
def test_the_prompts_hold_their_rules(agent, needle) -> None:
    from adroit.agents import audit, scout, variants
    system = {"variants": variants.VARIANT_SYSTEM, "scout": scout.SCOUT_SYSTEM, "audit": audit.AUDIT_SYSTEM}[agent]
    assert needle in system


def test_search_keywords_for_cards_and_models() -> None:
    assert agents.card_keywords("M_anapole") == ["anapole"]
    assert agents.card_keywords("O1") == ["spin-independent", "non-relativistic effective"]
    assert "spin-dependent" in agents.card_keywords("O10") and "velocity-dependent" in agents.card_keywords("O8")
    assert "spin-dependent" in agents.card_keywords("L15")                  # through its terms' operators
    r = lagrangian.LagrangianResult.model_validate_json((DOCS / "dm8/majorana_scalar/result.json").read_text())
    assert agents.model_keywords(r.spec) == ["scalar mediator", "Majorana"]


def test_track1_scout_and_audit(tmp_path) -> None:
    """R7 item 9: the agents take a Track 1 result (the scout and the audit; variants are Path 2's)."""
    import json
    kind, r = agents.read_result(json.loads((DOCS / "dm13/reports/vector_mediator/result.json").read_text()))
    assert kind == "track1"
    inv = assumptions.track1(r)
    assert any(i.statement.startswith("constraints compared: ") for i in inv.items)
    assert any(i.category == "prior" for i in inv.items) and any("propagation" in i.statement for i in inv.items)
    llm = FakeLLMClient([scout_report(), full_audit(inv)])
    out = agents.run_track1(r, llm, tools=tools(tmp_path))
    assert out.subject.startswith("Track 1 for ") and list(out.scouting) == [r.request.spec.name]
    assert out.audit_missing == [] and out.report_unverified == [] and out.calculation_started_at
    assert "verdict" in llm.calls[1]["messages"][0]["content"]
    text = agents.report(out)
    assert "## Assumption audit (DM9)" in text and "## Variants" not in text


@pytest.mark.needs("cresst", "cdmslite")
def test_single_idea_scout_and_audit(tmp_path) -> None:
    import json
    kind, r = agents.read_result(json.loads((DOCS / "dm14/single_idea_vector_cdms_si/result.json").read_text()))
    assert kind == "single_idea"
    inv = assumptions.single_idea(r)
    assert any(i.statement.startswith("The search: CDMS II Si") for i in inv.items)
    assert any(i.statement.startswith("Track 1: ") for i in inv.items)
    out = agents.run_single_idea(r, FakeLLMClient([scout_report(), full_audit(inv)]), tools=tools(tmp_path))
    assert out.audit_missing == [] and len(out.scouting) == 1 and out.report_unverified == []


def test_the_command_takes_every_result_kind(tmp_path, monkeypatch) -> None:
    import json
    from typer.testing import CliRunner
    from adroit.orchestrator import cli
    seen = []
    for kind in ("signal", "lagrangian", "track1", "single_idea"):
        monkeypatch.setitem(agents.RUNNERS, kind, lambda r, llm, *a, k=kind: seen.append(
            (k, type(r).__name__, type(llm).__name__)) or agents.AgentResult(subject=k))
    sources = {"signal": "dm6/lz_case.json", "lagrangian": "dm8/majorana_scalar/result.json",
               "track1": "dm13/reports/vector_mediator/result.json",
               "single_idea": "dm14/single_idea_vector_cdms_si/result.json"}
    import hashlib
    for kind, source in sources.items():
        out = CliRunner().invoke(cli.app, ["agents", str(DOCS / source), "--budget", "0.1", "--out", str(tmp_path / kind)])
        assert out.exit_code == 0, out.output
        report = (tmp_path / kind / "report.md").read_text()       # advisory, read as found, naming what it read
        assert "*Read as found.*" in report and hashlib.sha256((DOCS / source).read_bytes()).hexdigest() in report
    expected = [("signal", "SignalResult"), ("lagrangian", "LagrangianResult"), ("track1", "Track1Result"),
                ("single_idea", "SingleIdeaResult")]
    assert seen == [(k, r, client) for k, r in expected for client in ("Rehearsal", "BudgetedLLMClient")]
    promotion = tmp_path / "promotion.json"
    promotion.write_text(json.dumps({"parent": "p", "labels": [], "children": []}))
    out = CliRunner().invoke(cli.app, ["agents", str(promotion), "--budget", "0.1", "--out", str(tmp_path / "p")])
    assert out.exit_code == 2 and "not promotion" in out.output


@pytest.mark.needs("cresst", "cdmslite")
def test_the_agents_are_rehearsed_before_any_request(tmp_path) -> None:
    """G12's live check L7: each agent's reservation is known, at $0, before the first paid request."""
    r = signal.SignalResult.model_validate_json((DOCS / "dm6/lz_case.json").read_text())
    rehearsal = agents.rehearse("signal", r, "claude-opus-5-5", agents.AgentRequest(scout_leaders=1), tools(tmp_path))
    assert [a for a, _ in rehearsal.requests] == ["variant_agent", "constraint_scout", "assumption_audit"]
    assert all(usd > 0 for _, usd in rehearsal.requests)
    text = agents.plan_text(rehearsal, 0.3)
    assert f"Below ${rehearsal.largest:.2f} the run cannot finish" in text and "The cap given: $0.30" in text


class StopsAfter:
    """A fake client whose budget runs out after ``n`` replies."""

    def __init__(self, replies, n: int) -> None:
        self.inner, self.n = FakeLLMClient(replies), n

    def complete_structured(self, *args, **kwargs):
        from adroit.agents.llm import BudgetExceeded
        if self.n == 0:
            raise BudgetExceeded(0.2, 0.3, 0.49)
        self.n -= 1
        return self.inner.complete_structured(*args, **kwargs)


@pytest.mark.needs("cresst", "cdmslite")
def test_a_budget_stop_keeps_the_agents_that_finished(tmp_path) -> None:
    """G12's live check L7: a stop had left the finished agents' replies only in the paid-response journal."""
    r = signal.SignalResult.model_validate_json((DOCS / "dm6/lz_case.json").read_text())
    picks = VariantChoices(picks=[VariantPick(index=99, rationale="off the menu")])
    out = agents.run_path2(r, StopsAfter([picks, scout_report()], 2), agents.AgentRequest(scout_leaders=1),
                           tools(tmp_path))
    assert out.stopped.startswith("LLM budget stopped") and out.not_run == ["audit"]
    assert len(out.scouting) == 1 and out.discarded_picks == ["99: not on the menu"]
    text = agents.report(out)
    assert "## Stopped by the budget" in text and "Not run: audit" in text and "## Variants (DM9)" in text


def test_a_cap_below_the_largest_request_is_refused_before_any_is_sent(tmp_path, monkeypatch) -> None:
    from typer.testing import CliRunner
    from adroit.agents.rehearsal import Rehearsal
    from adroit.orchestrator import cli
    planned = Rehearsal("claude-opus-5-5")
    planned.requests = [("variant_agent", 0.49), ("assumption_audit", 0.76)]
    monkeypatch.setattr(agents, "rehearse", lambda *a, **k: planned)
    monkeypatch.setitem(agents.RUNNERS, "signal", lambda *a: pytest.fail("a request was sent"))
    out = CliRunner().invoke(cli.app, ["agents", str(DOCS / "dm6/lz_case.json"), "--budget", "0.30",
                                       "--out", str(tmp_path / "a")])
    assert out.exit_code == 3 and "Not started, $0 spent" in out.output and "$0.76" in out.output
