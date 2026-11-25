"""The restructured Signal best fits page (the owner, 2026-11-18, the signal best fits plan): the signal its one
needed input; what will be searched, said; the halo models (compared too); the agent-led search as a paid choice;
your own models folded; and Explain a signal's halo choice in sight. No paid call: the launcher is replaced."""
from __future__ import annotations

from nicegui import ui
from nicegui.testing import User

from adroit.ui.app import build_pages
from adroit.ui.wizards import searched_space
from tests.ui.test_auto_approve import capture


def test_the_space_is_said_for_a_search_without_its_own():
    text = searched_space("CDMS II Si (2013)")
    assert text.startswith("748 candidates: the library's 14 non-relativistic operators (O1, O3–O15) and 20 "
                           "Lagrangians (L01–L20), each isoscalar and isovector, at 11 masses from 5 GeV to 5 TeV")


async def test_the_page_says_what_it_searches_and_folds_your_own_models(user: User, tmp_path):
    build_pages(tmp_path / "runs")
    await user.open("/new/track2")
    await user.should_see("2. What will be searched")
    await user.should_see(marker="searched_space")
    await user.should_see("How to search")
    await user.should_see("Also compare your own models (optional)")
    treatments = next(e for e in user.find(kind=ui.select).elements if e.props.get("label") == "halo treatment")
    assert "compare" in treatments.options


async def test_the_agent_led_search_is_a_paid_choice_with_its_own_gate(user: User, tmp_path, monkeypatch):
    calls = capture(monkeypatch)
    build_pages(tmp_path / "runs")
    await user.open("/new/track2")
    user.find(marker="agent_search").click()
    user.find("Fit, combine and rank").click()
    assert calls == []                                       # its spend not approved: nothing starts
    user.find("I approve this spend").click()
    user.find("Fit, combine and rank").click()
    await user.should_see("Run:")
    command = calls[0]["command"]
    assert "--agent" in command and command[command.index("--budget") + 1] == "1"
    assert calls[0]["confirmed_budget"] == 1.0 and calls[0]["approval"] == "click"


async def test_a_fixed_scan_is_free(user: User, tmp_path, monkeypatch):
    calls = capture(monkeypatch)
    build_pages(tmp_path / "runs")
    await user.open("/new/track2")
    user.find("Fit, combine and rank").click()
    await user.should_see("Run:")
    assert "--agent" not in calls[0]["command"] and "--budget" not in calls[0]["command"]


async def test_explain_a_signal_shows_its_halo_choice(user: User, tmp_path):
    build_pages(tmp_path / "runs")
    await user.open("/new/single")
    await user.should_see("The halo")
    family = next(e for e in user.find(kind=ui.select).elements if e.props.get("label") == "halo family")
    advanced = next(iter(user.find(marker="advanced").elements))
    assert family not in advanced.descendants()              # above the folded options, not inside them
