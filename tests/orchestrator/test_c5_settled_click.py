"""The browser gate clicks an element once its place has settled (cycle 5's checks, 2026-11-16): Track 1's "1. Review
scan setup", clicked just after "Advanced: axis strings" opened, had been measured mid-transition and the click had
ticked the coverage box above it, so the halo journeys failed on code that works. Offline: the tab's answers simulated."""
from __future__ import annotations

from tests.orchestrator.test_browser_layer import _load


def _page(places: list, monkeypatch):
    browser = _load("browser")
    monkeypatch.setattr(browser.time, "sleep", lambda seconds: None)
    page = object.__new__(browser.Page)
    answers = iter(places)
    clicks: list = []
    page.evaluate = lambda script: next(answers)
    page.mouse_click = lambda x, y, hold=0.0: clicks.append((x, y))
    return page, clicks


def test_a_moving_element_is_clicked_where_it_comes_to_rest(monkeypatch) -> None:
    page, clicks = _page([[100.0, 500.0], [100.0, 540.0], [100.0, 562.0], [100.0, 562.0]], monkeypatch)
    page._click_found("() => null", "a button")
    assert clicks == [(100.0, 562.0)]                        # not where it was first measured (500: its neighbour)


def test_a_still_element_is_clicked_at_once(monkeypatch) -> None:
    page, clicks = _page([[10.0, 20.0], [10.0, 20.2]], monkeypatch)
    page._click_found("() => null", "a button")
    assert clicks == [(10.0, 20.0)]                          # unmoved (within half a pixel): clicked there
