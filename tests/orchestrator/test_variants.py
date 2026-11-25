"""DM9: variants of Path 2's leaders (deterministic half), on DM6's stored LZ result."""

from __future__ import annotations

from pathlib import Path

import pytest

from adroit.agents.variants import VariantChoices, VariantPick, choose
from adroit.orchestrator import signal, variants

LZ = Path(__file__).resolve().parents[2] / "docs" / "dm6" / "lz_case.json"


@pytest.fixture(scope="module")
def result() -> signal.SignalResult:
    return signal.SignalResult.model_validate_json(LZ.read_text())


def test_leaders_call_for_variants_when_their_fit_or_a_constraint_says_so(result) -> None:
    t = variants.triggers(result)
    # the receipt regenerated in R6 combines every member of the leading classes, and IceCube's native-90%
    # exclusion is no longer read as a 95% one, so the two L12 members at 4 TeV are the triggers
    assert set(t) == {"L12s@4000", "L12v@4000"}
    assert all("above 4π" in t[label][0] for label in t)


def test_the_menu_holds_only_one_step_deformations_of_triggered_leaders(result) -> None:
    menu = variants.menu(result, ["O01s@1000,d=350"])
    assert {o.parent for o in menu} == {"O01s@1000,d=350"} and [o.index for o in menu] == list(range(len(menu)))
    assert [o.description for o in menu] == ["isospin v", "splitting 200 keV", "splitting 250 keV",
                                             "splitting 300 keV", "splitting 400 keV", "splitting 450 keV"]
    assert variants._splittings(0.0) == [25.0, 50.0, 100.0, 150.0, 200.0]


def test_picks_off_the_menu_or_for_untriggered_leaders_are_discarded() -> None:
    picks = VariantChoices(picks=[VariantPick(index=i, rationale="r") for i in (0, 0, 1, 2, 7, 9)])
    parents = {0: "A", 1: "A", 2: "A", 9: "B"}
    kept, discarded = choose(picks, parents, {"A"})
    assert set(kept) == {0, 1} and len(discarded) == 4
    assert any("not on the menu" in d for d in discarded) and any("has no trigger" in d for d in discarded)


@pytest.mark.usefixtures("resigned")
@pytest.mark.needs("solar_model")
def test_a_variant_is_fitted_like_any_candidate_and_joins_only_if_it_improves(result) -> None:
    option = next(o for o in variants.menu(result, ["O01s@1000,d=350"]) if o.description == "splitting 400 keV")
    outcome = variants.evaluate(result, [option], {option.index: "suppress capture"})[0]
    assert outcome.rationale == "suppress capture" and outcome.combination is not None and not outcome.joined
    assert outcome.aic == pytest.approx(-outcome.combination.z_joint ** 2 + 4)
    capture = next(v for v in outcome.verdicts if v.constraint_id == "icecube-1612.05949-si")
    assert capture.native_excluded is False  # capture is suppressed at 400 keV at native 90%
    assert capture.excluded is None          # no justified 95% conversion
    better = outcome.model_copy(update={"joined": True, "combination": outcome.combination.model_copy(
        update={"z_joint": 6.0})})
    ranking = variants.with_variants(result, [better])
    entry = next(e for e in ranking.ranking if e.label == option.candidate.label)
    assert entry.aic == pytest.approx(-36.0 + 4.0)                  # charged one more parameter
