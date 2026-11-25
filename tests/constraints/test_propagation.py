"""Propagation models for charged cosmic-ray bounds (constraints.propagation): the three declared models, the
choice, and the antiproton verdict that decides by the chosen model and only flags the stronger ones."""

import math
from types import SimpleNamespace

import pytest
import yaml

from adroit.constraints import propagation
from adroit.parameter_space.classes import Point

RECORD = "calore-2202.03076-pbar"


def test_three_models_with_relaxed_as_another_name_for_aggressive() -> None:
    assert propagation.MODELS == ("conservative", "central", "aggressive")
    assert propagation.normalise("Relaxed") == "aggressive" and propagation.normalise(" central ") == "central"
    with pytest.raises(ValueError, match="unknown propagation model"):
        propagation.normalise("optimistic")
    assert propagation.stronger("conservative") == ["central", "aggressive"]
    assert propagation.stronger("aggressive") == []


def test_the_conservative_bound_is_never_stronger_and_the_aggressive_never_weaker() -> None:
    table = propagation.load(RECORD)["factors"]
    for m in table["mass_gev"]:
        assert propagation.factor(RECORD, "central", m) == 1.0
        assert propagation.factor(RECORD, "conservative", m) >= 1.0 >= propagation.factor(RECORD, "aggressive", m)
    assert propagation.factor(RECORD, "conservative", 5e4) == pytest.approx(max(table["conservative"]))
    assert propagation.factor(RECORD, "aggressive", 5e4) == pytest.approx(min(table["aggressive"]))
    assert propagation.factor("no-such-record", "conservative", 100.0) == 1.0


def test_the_digitised_figure_is_anchored_and_physically_ordered() -> None:
    data = propagation.load(RECORD)
    assert all(v < 0.01 for v in data["calibration"]["max residual dex"].values())
    assert all(data["checks"].values())
    assert set(data["curves"]) == {"profiles", "schemes"}
    assert set(data["curves"]["schemes"]) == {"BIG", "SLIM", "QUAINT"}


def test_a_run_chooses_the_model_and_the_setting_supplies_the_default(monkeypatch) -> None:
    from adroit.core import config
    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(cr_propagation="central"))
    assert propagation.chosen() == "central"
    with propagation.using("relaxed"):
        assert propagation.chosen() == "aggressive"
        with propagation.using(None):
            assert propagation.chosen() == "aggressive"
    assert propagation.chosen() == "central"


class _Annihilating:
    def __init__(self, rates: dict[str, float]) -> None:
        self.rates = rates

    def sigma_v_today(self, p, v):
        return dict(self.rates)


def _bb_at_ratio(ratio: float, mass: float) -> _Annihilating:
    """b b̄ annihilation at a given ratio to the central curve (a Dirac pair: compared at half the rate)."""
    from adroit.constraints import searches as s
    limit = s.interpolate(s._bundled(RECORD)["limits"]["bb"], mass)
    return _Annihilating({"b": 2 * ratio * limit})


def test_only_the_chosen_model_excludes_and_a_stronger_one_is_flagged() -> None:
    from adroit.parameter_space import searches
    mass = 1000.0
    cls, p = _bb_at_ratio(1.2, mass), Point(m_chi=mass, m_med=1.0)
    with propagation.using("conservative"):
        lenient = searches.antiprotons(cls, p, True)
    with propagation.using("central"):
        central = searches.antiprotons(cls, p, True)
    with propagation.using("aggressive"):
        harsh = searches.antiprotons(cls, p, True)
    assert lenient.excluded is False and lenient.ratio == pytest.approx(1.2 / propagation.factor(RECORD,
                                                                                                  "conservative", mass))
    assert len(lenient.flags) == 2 and all("not counted as an exclusion" in f for f in lenient.flags)
    assert {f.split("the ")[1].split(" propagation")[0] for f in lenient.flags} == {"central", "aggressive"}
    assert central.excluded is True and central.ratio == pytest.approx(1.2) and central.flags == []
    assert harsh.excluded is True and "aggressive propagation" in harsh.source


def test_a_point_allowed_by_every_model_carries_no_flag() -> None:
    from adroit.parameter_space import searches
    with propagation.using("conservative"):
        found = searches.antiprotons(_bb_at_ratio(0.3, 1000.0), Point(m_chi=1000.0, m_med=1.0), True)
    assert found.excluded is False and found.flags == []


def test_a_mixture_is_rescaled_with_its_bound() -> None:
    from adroit.parameter_space import searches
    from adroit.constraints import searches as s
    limits = s._bundled(RECORD)["limits"]
    ww = s.interpolate(limits["WW"], 1100.0)
    cls, p = _Annihilating({"W": 2 * 0.7 * ww, "Z": 2 * 0.2 * ww}), Point(m_chi=1100.0, m_med=1.0)
    with propagation.using("central"):
        central = searches.antiprotons(cls, p, True)
    with propagation.using("conservative"):
        lenient = searches.antiprotons(cls, p, True)
    assert central.excluded is False and central.ratio == pytest.approx(0.7)       # its lower bound (AL4-07)
    assert "0.95" in central.why                                                   # the upper, 0.7 + 1.25 × 0.2
    assert lenient.ratio == pytest.approx(central.ratio / propagation.factor(RECORD, "conservative", 1100.0))


def test_requests_record_the_model_and_keep_their_identity_when_unset() -> None:
    from adroit.parameter_space.library import entry
    from adroit.parameter_space.scan import ScanRequest
    from adroit.orchestrator.track1 import for_portal, propagation_line
    e = entry("higgs_portal_scalar")
    request = ScanRequest(model_class=e.model_class, fixed=e.point, x=e.x, y=e.y)
    assert "propagation" not in request.model_dump(mode="json")
    assert ScanRequest(model_class=e.model_class, fixed=e.point, x=e.x, y=e.y, propagation="relaxed").propagation \
        == "aggressive"
    assert for_portal("higgs_portal_scalar", propagation="central").propagation == "central"
    assert propagation.resolved(for_portal("higgs_portal_scalar")).propagation == propagation.chosen()
    text = propagation_line("conservative")
    assert "**conservative**" in text and "flagged, not excluded" in text
    assert "flagged" not in propagation_line("aggressive") and "**central**" in propagation_line(None)


def test_replay_uses_the_recorded_model_and_central_for_older_results() -> None:
    from adroit.evidence.replay import _recorded_propagation
    old = SimpleNamespace(scan=SimpleNamespace(request=SimpleNamespace()), request=SimpleNamespace())
    assert _recorded_propagation(old) == "central"
    new = SimpleNamespace(scan=SimpleNamespace(request=SimpleNamespace(propagation="aggressive")), request=None)
    assert _recorded_propagation(new) == "aggressive"


def test_the_record_states_its_propagation_models() -> None:
    from pathlib import Path
    records = yaml.safe_load(Path("adroit/constraints/data/records.yaml").read_text())
    entry = next(r for r in records["records"] if r["id"] == RECORD)
    assert any("propagation" in a and "conservative" in a for a in entry["assumptions"])
    assert math.isfinite(propagation.factor(RECORD, "conservative", 10.0))


@pytest.mark.needs("diamx", "solar_model")
def test_the_scan_carries_outcome_flags_onto_the_point(monkeypatch) -> None:
    from adroit.constraints.searches import Outcome
    from adroit.parameter_space import scan
    from adroit.parameter_space.library import entry
    monkeypatch.setattr(scan.searches, "outcomes", lambda *a, **k: [Outcome(name="x", excluded=False,
                                                                            flags=["a stronger model excludes"])])
    e = entry("higgs_portal_scalar")
    assert "a stronger model excludes" in scan.evaluate(e.model_class, e.point, True).flags
