"""The browser journeys assert what they claim (the signal/DD audit's R9-07): the standard-models journey's line "named
under the picker, each with why" had passed on a page naming the models without any reason. A simulated page (no
browser) drives the journey's own code up to that assertion: reasons absent, it fails; present, it passes."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from adroit.parameter_space import library

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))
import browser_journeys as journeys  # noqa: E402


class _Bench:
    def __init__(self, root, **_):
        self.root, self.url = root, "http://127.0.0.1:1"
        root.mkdir(parents=True, exist_ok=True)

    def start(self):
        pass

    def stop(self, **_):
        pass


class _Reached(Exception):
    """The journey got past the refusal-reason assertion (the rest is the real browser's)."""


def _page(with_reasons: bool):
    refused = [e for e in library.ENTRIES if e.typed.unsupported or e.typed.no_recoil]
    rows = [f"{e.title}: {e.typed.unsupported or e.typed.no_recoil}" if with_reasons else e.title for e in refused]

    class Page:
        def goto(self, url):
            pass

        def text(self):
            return "Not offered: " + "; ".join(rows) + "."

        def wait_text(self, text):
            assert text in self.text()

        def choose(self, *a):
            raise _Reached
    return Page()


@pytest.mark.parametrize("with_reasons", [False, True])
def test_the_journey_fails_without_the_refusal_reasons(monkeypatch, tmp_path, with_reasons) -> None:
    monkeypatch.setattr(journeys, "Workbench", _Bench)
    browser = SimpleNamespace(page=lambda: _page(with_reasons))
    if with_reasons:
        with pytest.raises(_Reached):
            journeys.journey_standard_models(browser, tmp_path)
    else:
        with pytest.raises(AssertionError, match="with its reason"):
            journeys.journey_standard_models(browser, tmp_path)
