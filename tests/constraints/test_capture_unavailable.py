"""The fallback review's D3: a calculation never downloads the solar model; without it, capture in the Sun is
undecided, and every consumer says why (``capture.UNAVAILABLE``)."""

from __future__ import annotations

import pytest

from adroit.constraints import capture, database, verdicts
from adroit.core.dm_state import (Applicability, DarkMatterParticle, InteractionModel, OperatorCoefficient)
from adroit.physics import conventions


@pytest.fixture
def no_solar_model(monkeypatch):
    """The tools folder without the solar model, and any download an error."""
    original = capture.fetch.locate

    def refuse(*args, **kwargs):
        raise AssertionError("a calculation tried to download the solar model")

    monkeypatch.setattr(capture.fetch, "locate",
                        lambda name, *a, **k: None if name == capture.SOLAR_MODEL else original(name, *a, **k))
    monkeypatch.setattr(capture.fetch, "fetch", refuse)
    capture.solar_model.cache_clear()
    yield
    capture.solar_model.cache_clear()


def test_the_solar_model_is_not_downloaded_by_a_calculation(no_solar_model) -> None:
    assert not capture.available()
    with pytest.raises(capture.SolarModelUnavailable, match="adroit setup --fetch"):
        capture.solar_model()


def test_a_telescope_verdict_without_the_solar_model_is_undecided_and_says_why(no_solar_model) -> None:
    m = 100.0
    sd = InteractionModel(name="SD-p", layer="nonrelativistic", coefficients=[
        OperatorCoefficient(operator=4, proton=conventions.c4_from_sigma_sd(1e-39, m), neutron=0.0)])
    bare = verdicts.Candidate(label="sd", particle=DarkMatterParticle(mass_gev=m), interaction=sd)
    v = verdicts.verdict(bare, database.record("icecube-1612.05949-sd"))
    assert v.applicability is Applicability.needs_calculation
    assert v.needed_calculation == capture.UNAVAILABLE
    assert v.excluded is None and v.native_excluded is None


def test_the_scans_icecube_without_the_solar_model_is_undecided_and_says_why(no_solar_model) -> None:
    from adroit.parameter_space import scan
    from adroit.parameter_space.library import entry
    e = entry("higgs_portal_scalar")
    p = e.point.model_copy(update={"m_chi": 3727.6, "g_chi": 1.136})
    assert scan._icecube(e.model_class, p) == (None, None, capture.UNAVAILABLE)


def test_an_exclusion_asking_for_telescopes_names_the_missing_solar_model(no_solar_model) -> None:
    from adroit.orchestrator import exclusion
    request = exclusion.ExclusionRequest(card_id="O1", values={"c_p": 1e-8, "c_n": 1e-8}, masses_gev=[100.0],
                                         modules=["no such module"], unverified_records=True)
    result = exclusion.run(request)
    assert result.telescopes == []
    assert result.skipped["neutrino telescopes (capture in the Sun)"] == capture.UNAVAILABLE
    assert f"neutrino telescopes (capture in the Sun) ({capture.UNAVAILABLE})" in exclusion.report(result)
