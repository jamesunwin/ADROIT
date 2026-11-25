"""Signal best fits' agent-led search (the owner, 2026-11-18, the signal best fits plan, phase C): the agent
chooses from a menu of deformations of the leaders, each fitted like any candidate and charged one more parameter;
the global significance is recomputed over everything tried; its interpretation keeps only numbers the result holds;
the fixed scan's ranking is unchanged. Offline: the toy searches of halo phase 1 and a fake model."""
from __future__ import annotations

from pathlib import Path

import pytest
import typer

from adroit.agents.budget import BudgetExceeded
from adroit.agents.llm import FakeLLMClient
from adroit.agents.signal_search import Interpretation, SEARCH_SYSTEM, SearchChoices, SearchPick
from adroit.orchestrator import signal, signal_search
from adroit.ui import engine, forms
from tests.orchestrator.test_halo_phase1 import _request, toys  # noqa: F401  (the fixture)


def _scan() -> signal.SignalResult:
    return signal.run(_request())


def test_a_round_fits_the_agent_s_pick_and_the_significance_counts_it(toys):  # noqa: F811
    fixed = _scan()
    fake = FakeLLMClient([SearchChoices(picks=[SearchPick(index=0, why="the other isospin weakens the null limit")]),
                          Interpretation(text="O1s@20 leads; its Z_signal is as given, and 9.87 is invented.")])
    result = signal_search.run(fixed, fake, signal_search.SearchSettings(rounds=1))
    search = result.agent_search
    assert fake.calls[0]["system"] == SEARCH_SYSTEM and "Menu:\n[0] O1s@20" in fake.calls[0]["messages"][0]["content"]
    assert search.tried == 1 and len(search.rounds) == 1 and search.rounds[0].tried[0].parent == "O1s@20"
    assert search.rounds[0].tried[0].why == "the other isospin weakens the null limit"
    assert search.global_method.startswith("over everything searched and tried (2 signal shapes")
    assert search.max_local_z >= fixed.max_local_z
    assert search.removed_numbers == ["9.87"] and "[a number not in the result]" in search.interpretation
    assert result.tournament == fixed.tournament                       # the fixed scan's ranking unchanged
    text = signal.report(result)
    assert "## The agent-led search" in text and "The agent's interpretation" in text


def test_picks_off_the_menu_are_discarded_and_a_stop_ends_the_search(toys):  # noqa: F811
    fixed = _scan()
    fake = FakeLLMClient([SearchChoices(picks=[SearchPick(index=999, why="invented")], stop=True,
                                        reason="nothing promising"),
                          Interpretation(text="The background alone explains the events.")])
    result = signal_search.run(fixed, fake, signal_search.SearchSettings(rounds=3))
    assert result.agent_search.tried == 0 and result.agent_search.stopped == "the agent stopped: nothing promising"
    options = signal_search.menu(fixed, signal.candidates_for(fixed.request, signal._checked(fixed.request)[1])
                                 and {c.label: c for c in fixed.engine_candidates}, ["O1s@20"], set())
    kept, discarded = signal_search.kept(SearchChoices(picks=[SearchPick(index=0, why="a"), SearchPick(index=0, why="b"),
                                                              SearchPick(index=999, why="c")]), options, 1)
    assert kept == {0: "a"} and discarded == ["0: chosen twice", "999: not on the menu"]
    assert any(o.deformation == "refine_mass" for o in options)


def test_a_spent_budget_stops_the_search_and_says_so(toys):  # noqa: F811
    class Spent(FakeLLMClient):
        def complete_structured(self, *a, **k):
            raise BudgetExceeded(0.9, 1.0, 0.2)
    result = signal_search.run(_scan(), Spent([]), signal_search.SearchSettings(rounds=2))
    assert result.agent_search.stopped.startswith("the budget") and "no interpretation" in result.agent_search.stopped


def test_only_numbers_the_result_holds_are_kept():
    text, removed = signal_search.checked_numbers("Z 2.31 for L12s@4000, ΔAIC −1.50, and 7 more", "2.31 L12s@4000 -1.50")
    assert text == "Z 2.31 for L12s@4000, ΔAIC −1.50, and [a number not in the result] more" and removed == ["7"]


def test_the_command_and_the_form_ask_for_a_budget():
    from adroit.orchestrator.cli import _agent_search
    with pytest.raises(typer.BadParameter, match="needs --budget"):
        _agent_search(True, 3, "", 0.0)
    with pytest.raises(typer.BadParameter, match="give --agent"):
        _agent_search(False, 3, "", 1.0)
    with pytest.raises(typer.BadParameter, match="--agent-model"):
        _agent_search(True, 3, "claude-fable-5-1", 1.0)
    with pytest.raises(ValueError, match="needs a budget"):
        forms.signal_command("CDMS II Si (2013)", "out", agent=True)
    command = forms.signal_command("CDMS II Si (2013)", "out", agent=True, agent_rounds=2, budget=2.0)
    assert command[command.index("--agent-rounds") + 1] == "2" and engine.paid(command) == 2.0


# --- the auditor's post-review recheck (2026-11-18): the agent search's blockers ----------------------------------------

def _compared_second_wins():
    """A comparison of the SHM and SHM++ ordered so that the second halo's largest local significance is the larger."""
    from adroit.core import halo_choice
    shm, shmpp = halo_choice.fixed("shm"), halo_choice.fixed("shm-plus-plus")
    for halos in ([shm, shmpp], [shmpp, shm]):
        result = signal.run(_request().model_copy(update={"halos": halos, "halo": halos[0]}))
        runs = result.halo_scan.runs
        if runs[1].max_local_z > runs[0].max_local_z:
            return result
    pytest.skip("the two halos give the same largest local significance here")


def test_a_stop_keeps_the_comparison_s_maximum_and_significance(toys):  # noqa: F811
    """PS-01: with the halo models compared, the agent search's observed maximum is the whole comparison's, and a
    search that fits nothing reproduces its significance exactly."""
    result = _compared_second_wins()
    fake = FakeLLMClient([SearchChoices(stop=True, reason="nothing to add"), Interpretation(text="As given.")])
    search = signal_search.run(result, fake, signal_search.SearchSettings(rounds=1)).agent_search
    scan = result.halo_scan
    assert search.tried == 0 and search.max_local_z == scan.max_local_z > result.max_local_z
    assert (search.global_z, search.global_p_toys) == (scan.global_z, scan.global_p_toys)


def test_the_page_and_the_report_lead_with_the_widest_scope(toys):  # noqa: F811
    """PS-02: the study page's and the report's first significance is the agent search's, declared; the fixed scan's
    follows, said to be over its own candidates."""
    from adroit.ui.pages import global_significance
    fixed = _scan()
    search = signal_search.run(fixed, FakeLLMClient([SearchChoices(stop=True, reason="done"),
                                                      Interpretation(text="As given.")]),
                               signal_search.SearchSettings(rounds=1))
    widened = search.model_copy(update={"agent_search": search.agent_search.model_copy(
        update={"global_z": 0.42, "global_p_toys": 0.34})})                   # a wider search, a weaker significance
    text = global_significance(widened)
    assert text.startswith("Global significance over everything searched and tried, the agent-led search's variants "
                           "included: 0.42σ (p = 0.34")
    assert f"of the fixed scan, over which alone: {fixed.global_z:.2f}σ" in text
    assert "**Global significance over everything searched and tried" in signal.report(widened)


def test_the_saved_spending_counts_the_interpretation_too(toys):  # noqa: F811
    """PS-03: the search's spending is read from its account after its last request, the interpretation included."""
    from adroit.agents.budget import BudgetAccount

    class Billed(FakeLLMClient):
        def __init__(self, responses):
            super().__init__(responses)
            self.account = BudgetAccount(cap=1.0)

        def complete_structured(self, *a, **k):
            self.account.spent[f"r{len(self.calls)}"] = 0.0008          # each request's settled bill (simulated)
            return super().complete_structured(*a, **k)
    billed = Billed([SearchChoices(stop=True, reason="done"), Interpretation(text="As given.")])
    search = signal_search.run(_scan(), billed, signal_search.SearchSettings(rounds=1)).agent_search
    assert billed.call_count == 2 and search.spent_usd == pytest.approx(0.0016) and search.uncertain_usd == 0
    assert "$0.0016 settled" in signal.report(_scan().model_copy(update={"agent_search": search}))


# --- the auditor's post-review recheck 2 (2026-11-18): the bundle's saved decisions -------------------------------------

def _published(tmp_path, result) -> Path:
    from adroit.evidence.runtime import capture_request
    from adroit.orchestrator import runs
    folder = tmp_path / "runs" / "signal_toy"
    folder.mkdir(parents=True)
    runs._write(folder, result, signal.report(result), "signal", "Signal best fits: toy", {},
                evidence_context=capture_request(result.request))
    return folder


def test_the_saved_decisions_carry_the_widest_scope_and_an_older_summary_is_unchanged(toys):  # noqa: F811
    """PT-01: the evidence summary keeps the agent search (and a comparison) only where the result has one, and still
    matches the result; a fixed scan's summary has neither key."""
    from adroit.evidence.results import summary, summary_matches
    fixed = _scan()
    searched = signal_search.run(fixed, FakeLLMClient([SearchChoices(stop=True, reason="done"),
                                                        Interpretation(text="As given.")]),
                                 signal_search.SearchSettings(rounds=1))
    kept = summary("signal", searched)
    assert "agent_search" in kept and summary_matches("signal", kept, searched)
    assert "agent_search" not in summary("signal", fixed) and "halo_scan" not in summary("signal", fixed)
    assert signal.scope_text(kept["agent_search"], None).startswith(
        "Global significance over everything searched and tried, the agent-led search's variants included")


def test_a_number_with_a_unit_or_a_reversed_sign_is_checked_too():
    """The auditor's PS-06: a number written against a unit ("9.87σ", "20GeV", "15%") had gone unchecked, σ and letters
    being word characters, and "−2.31" passed for 2.31. Ordinals and candidate labels stay words."""
    text, removed = signal_search.checked_numbers(
        "Z 9.87σ, 2.31σ, −2.31, 20GeV, 20 GeV, 1st, L12s@4000, 15%", "2.31 20 L12s@4000")
    assert removed == ["9.87", "−2.31", "15"]
    assert text == ("Z [a number not in the result]σ, 2.31σ, [a number not in the result], 20GeV, 20 GeV, 1st, "
                    "L12s@4000, [a number not in the result]%")


def test_a_global_p_no_toy_reached_is_a_bound_in_the_report_and_on_the_page():
    """The post-review audit's PT-03: where no toy reached the observed maximum, the report's bold opening said
    "p = 0.00e+00" beside a Z that is a lower bound. Both now give the finite-toy bound and "≥"."""
    from adroit.orchestrator.signal import scope_text, significance_parts
    widest = {"global_z": 3.72, "global_p_toys": 0.0, "global_toys": 1000, "global_p_interval": [0.0, 0.0036]}
    text = scope_text(widest, None)
    assert "≥3.72σ (p < 0.0036: no toy of 1,000 reached it)" in text and "p = 0" not in text
    assert significance_parts(3.72, 0.0, 1000, None) == ("≥3.72σ", "p < 0.001: no toy of 1,000 reached it")
    assert significance_parts(2.0, 0.023, 1000, [0.015, 0.033], ".2g") == ("2.00σ", "p = 0.023")


def test_the_whole_report_bounds_a_p_no_toy_reached(toys):  # noqa: F811
    """The auditor's R7-04: the report's opening gave the finite-toy bound, but its agent-led search section (and the halo
    and header sentences) still wrote "p = 0.00e+00" beside an unqualified Z."""
    fixed = _scan()
    search = signal_search.run(fixed, FakeLLMClient([SearchChoices(stop=True, reason="done"),
                                                      Interpretation(text="As given.")]),
                               signal_search.SearchSettings(rounds=1))
    zero = search.model_copy(update={"agent_search": search.agent_search.model_copy(
        update={"global_z": 3.72, "global_p_toys": 0.0, "global_toys": 1000, "global_p_interval": [0.0, 0.0036]})})
    text = signal.report(zero)
    assert "p = 0.00e+00" not in text and "p = 0.0e+00" not in text
    assert text.count("≥3.72σ (p < 0.0036: no toy of 1,000 reached it") >= 2        # the opening and the section
