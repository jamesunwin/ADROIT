"""The halo region wired through the calculation: the command line's choice, the inputs it refuses, a comparison the
count ratio cannot decide, the Galactic searches' density scaling and the replay's recorded region."""
from types import SimpleNamespace

import pytest
import typer

from adroit.parameter_space import halo_limits, halo_region
from adroit.parameter_space.classes import Point
from adroit.parameter_space.halo_region import HaloPreset


def test_the_command_line_names_the_region_or_the_published_halos():
    from adroit.orchestrator.cli import _halo_option
    assert _halo_option("preset") == HaloPreset() and _halo_option("Published") == halo_region.PUBLISHED
    with pytest.raises(typer.BadParameter):
        _halo_option("einasto")


def test_a_track1_request_keeps_its_identity_until_a_region_is_named():
    from adroit.orchestrator.track1 import Track1Request
    from adroit.core.model_spec import ModelSpec
    import yaml
    from pathlib import Path
    docs = Path(__file__).resolve().parents[2] / "docs"
    data = yaml.safe_load((docs / "dm13" / "vector_mediator.yaml").read_text())
    request = Track1Request(spec=ModelSpec.model_validate(data.get("spec") or data))
    assert "halo" not in request.model_dump(mode="json")
    assert request.model_copy(update={"halo": "published"}).model_dump(mode="json")["halo"] == "published"
    assert halo_region.of(halo_region.resolved(request).halo) is None              # the tests' setting: published


def test_a_private_spin_independent_curve_is_refused_over_the_region():
    curve = SimpleNamespace(name="a private SI curve", contract=SimpleNamespace(adapter="si_isoscalar_curve"))
    higgs = SimpleNamespace(name="a private BR(h → inv) bound", contract=SimpleNamespace(adapter="sm_higgs_invisible"))
    halo_region.check_inputs(SimpleNamespace(private_limits=[higgs], private_searches=[]))
    with pytest.raises(ValueError, match="no halo variation"):
        halo_region.check_inputs(SimpleNamespace(private_limits=[curve, higgs], private_searches=[]))
    with pytest.raises(ValueError, match="private-search:x"):
        halo_region.check_inputs(SimpleNamespace(private_limits=[], private_searches=[SimpleNamespace(
            search_id="private-search:x")]))


def test_a_comparison_the_count_ratio_cannot_decide_is_noted_not_recomputed(monkeypatch):
    """Inside a sample (``defer``) a ratio within the margin is left to the region's evaluation; outside one the
    direct calculation runs as before."""
    from adroit.parameter_space import dd_channels, limits

    def refuse():
        raise AssertionError("recomputed directly")
    monkeypatch.setattr(halo_limits, "per_module95", lambda state, kind, mass, excluded: (
        state.margins.update({("XENONnT SR0+SR1", kind, mass): 0.2}) or ((("XENONnT SR0+SR1", 1e-46),), ())))
    monkeypatch.setattr(limits, "exact", refuse)
    state = halo_limits.State(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=0.4, defer=True)
    with halo_limits.using(state):
        out = dd_channels.compare([dd_channels.Channel(kind="SI", sigma_cm2=1.05e-46)], 100.0)
    assert out.excluded is True and state.fragile == ["SI (XENONnT SR0+SR1)"]
    clear = halo_limits.State(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=0.4, defer=True)
    with halo_limits.using(clear):
        assert dd_channels.compare([dd_channels.Channel(kind="SI", sigma_cm2=5e-46)], 100.0).excluded is True
    assert clear.fragile == []


def test_the_antiproton_limit_moves_as_the_local_density_squared():
    from adroit.parameter_space import searches
    from adroit.parameter_space.classes import Spin1Class
    cls, p = Spin1Class(), Point(m_chi=200.0, m_med=1000.0, g_chi=1.0, g_q=0.25)
    published = searches.antiprotons(cls, p, False)
    assert published is not None and published.ratio is not None
    with halo_limits.using(halo_limits.State(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=0.77)):
        doubled = searches.antiprotons(cls, p, False)
    assert doubled.ratio == pytest.approx(published.ratio * (0.77 / 0.385) ** 2, rel=1e-9)


def test_capture_in_the_sun_is_computed_in_the_samples_halo():
    halo = halo_limits.velocity_halo(200.0, 480.0, 0.6)
    with halo_limits.using(halo_limits.State(v0_km_s=200.0, v_esc_km_s=480.0, rho_gev_cm3=0.6)):
        assert halo_limits.capture_halo() == halo


def test_a_replay_takes_the_saved_region():
    from adroit.evidence.replay import _recorded_halo
    saved = SimpleNamespace(scan=SimpleNamespace(request=SimpleNamespace(halo=HaloPreset())))
    assert _recorded_halo(saved) == HaloPreset()
    assert _recorded_halo(SimpleNamespace(scan=SimpleNamespace(request=SimpleNamespace(halo=None)))) is None
    assert _recorded_halo(SimpleNamespace()) is None


def test_a_module_left_without_a_limit_at_a_halo_leaves_that_halo_unresolved(monkeypatch):
    """A slow module the count ratio does not cover and the budget cannot compute leaves that halo unresolved (halo
    coverage incomplete), not merely pending."""
    from adroit.parameter_space import dd_channels, halo_evaluation, limits
    monkeypatch.setattr(limits, "eligible", lambda kind, mass, excluded=(): ["CDMSlite Run 2"])
    monkeypatch.setattr(halo_limits, "validated", lambda module, kind, mass, state=None: None)
    channels = [dd_channels.Channel(kind="SI", sigma_cm2=1e-42)]
    cls = SimpleNamespace(dd=lambda p: ("SI", 1e-42))
    monkeypatch.setattr(halo_evaluation, "_outcome", lambda o: None)
    from adroit.parameter_space import searches
    monkeypatch.setattr(searches, "dm_mass", lambda cls, p: 5.0)
    monkeypatch.setattr(searches, "lines", lambda cls, p, unverified: None)
    monkeypatch.setattr(searches, "antiprotons", lambda cls, p, unverified: None)
    sample = halo_evaluation.at(cls, Point(m_chi=5.0, m_med=100.0), (233.0, 528.0, 0.4, "centre"), channels, False,
                                False, halo_limits.Budget(0))
    assert sample.unresolved and "budget is spent" in sample.unresolved[0]
