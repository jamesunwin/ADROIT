"""1.0.1 (the owner, 2026-11-25): a spin-dependent limit and the correction that rescales a prediction onto it use the
same nuclear prescription and target. The xenon searches' SD limits use Klos et al.'s structure factors; their
proton–neutron correction (``dd_channels.single_kind_factor``) had used the conventions' shell model, which made it
about 25 times too large (PandaX-4T: ≈ 880–946 instead of ≈ 36 for equal couplings, 150–330 GeV)."""
import math

import pytest

from adroit.core.dm_state import CrossSectionKind as K
from adroit.core.dm_state import DarkMatterParticle, NuclearModel
from adroit.experiments import registry as modules
from adroit.library.interactions import registry
from adroit.parameter_space import dd_channels, limits

PANDAX = "PandaX-4T Run0+Run1"
XENONNT = "XENONnT SR0+SR1"


def _rate_ratio(module: str, kind: str, mass: float, other: float, model: NuclearModel) -> float:
    """Direct: rate with both O₄ couplings over the rate with this kind's coupling alone, in the module's published
    target, at its conventions' halo."""
    m = modules.load_module(module)
    target, halo = m.published_target(K(kind)), m.conventions().halo
    particle = DarkMatterParticle(mass_gev=mass)

    def events(c_p: float, c_n: float) -> float:
        interaction = registry.resolve("O4", particle, {"c_p": c_p, "c_n": c_n})
        return m.expected_signal(particle, interaction, halo, model, target).total_events
    both = events(1.0, other) if kind == "SD-proton" else events(other, 1.0)
    alone = events(1.0, 0.0) if kind == "SD-proton" else events(0.0, 1.0)
    return both / alone


@pytest.mark.needs("diamx")
@pytest.mark.parametrize("module", [PANDAX, XENONNT])
@pytest.mark.parametrize("mass", [149.0, 188.0, 250.0, 328.0, 340.0])
@pytest.mark.parametrize("other", [1.0, -1.0, 0.5])
def test_the_correction_uses_the_limits_klos_structure_factors(module, mass, other) -> None:
    """The regression (fails before 1.0.1): the factor is the direct Klos rate ratio, and far from the shell model's."""
    factor = dd_channels.single_kind_factor(module, "SD-proton", mass, other)
    assert factor == pytest.approx(_rate_ratio(module, "SD-proton", mass, other, NuclearModel.klos), rel=1e-9)
    if other == 1.0:
        assert 30 < factor < 40
        assert _rate_ratio(module, "SD-proton", mass, other, NuclearModel.shell_model) > 800   # what it had been


@pytest.mark.needs("diamx")
def test_every_module_rescales_with_the_model_its_limit_uses() -> None:
    """Each module's SD limit model is the one its correction and count ratio read (``limit_model``); the xenon
    searches' is Klos et al.'s, while their conventions keep the shell model for every other operator, and SI keeps
    its Helm form factor."""
    for name in (PANDAX, XENONNT, "LZ WS2022+WS2024"):
        m = modules.load_module(name)
        assert limits.limit_model(m, K.sd_proton) is limits.limit_model(m, K.sd_neutron) is NuclearModel.klos
        assert m.conventions().spin_dependent_model is NuclearModel.shell_model          # other operators unchanged
        assert limits.limit_model(m, K.si) is m.conventions().nuclear_model is NuclearModel.helm
    for name in ("PICO-60 C3F8 (2019)", "CDMSlite Run 2"):
        m = modules.load_module(name)
        assert limits.limit_model(m, K.sd_proton) is m.conventions().model_for(K.sd_proton)


@pytest.mark.needs("diamx")
@pytest.mark.parametrize("module", [PANDAX, XENONNT, "LZ WS2022+WS2024"])
def test_the_xenon_reference_limits_are_computed_with_klos(monkeypatch, module) -> None:
    """Both SD kinds, every xenon search (the independent audit's V1-05: a mutation giving SD-neutron the shell model
    had left every test passing): the real reference call's prescription, and the helper's agreement with it."""
    m = modules.load_module(module)
    seen = {}

    def limits_on(kind, masses, model=None, cl=0.9, target=None, **_):
        seen[kind] = model
        return [1e-40] * len(masses)
    monkeypatch.setattr(m, "limits_on", limits_on)
    for kind in (K.sd_proton, K.sd_neutron, K.si):
        m.reference_limits(kind, [200.0])
    assert seen[K.sd_proton] is seen[K.sd_neutron] is NuclearModel.klos and seen[K.si] is None   # SI: Helm
    for kind in (K.sd_proton, K.sd_neutron):
        assert limits.limit_model(m, kind) is seen[kind]                         # the helper agrees, each kind


@pytest.mark.needs("diamx")
@pytest.mark.parametrize("mass, proton_valid, neutron_valid", [(147.0, False, False), (149.0, True, False),
                                                               (340.0, True, False), (342.0, True, True)])
@pytest.mark.parametrize("couplings", [(1.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, -1.0)],
                         ids=["proton", "neutron", "equal", "opposite"])
def test_pandax_around_its_validation_boundaries(monkeypatch, mass, proton_valid, neutron_valid, couplings) -> None:
    """PandaX-4T alone, at its own SD validation boundaries (proton from 147.85 GeV, neutron from 341.11 GeV): below
    the proton boundary it gives nothing; between them, one kind only, the ratio is σ_p/L_p × the Klos factor, which is
    the model's direct rate over the rate the limit corresponds to; above both, Tovey et al.'s band, which brackets it.
    The step at 341.11 GeV is the change from the rate-ratio interference (approximate at detector level, V1-03) to a
    bracketing band, not smoothed away."""
    m = modules.load_module(PANDAX)
    lo_p, lo_n = m.validated_range(K.sd_proton)[0], m.validated_range(K.sd_neutron)[0]
    assert (lo_p < mass) is proton_valid and (lo_n < mass) is neutron_valid
    L = {"SD-proton": 1e-41, "SD-neutron": 3e-42}
    valid = {"SD-proton": proton_valid, "SD-neutron": neutron_valid}
    monkeypatch.setattr(limits, "per_module95", lambda kind, mass_gev, excluded=(): (
        ((PANDAX, L[kind]),) if valid[kind] else (), ()))
    monkeypatch.setattr(limits, "tolerance", lambda *a: 0.0)
    c_p, c_n = couplings
    sigma_p, sigma_n = 2e-42 * c_p ** 2, 2e-42 * c_n ** 2          # σ ∝ c², the same normalisation for both kinds
    channels = [dd_channels.Channel(kind="SD-proton", sigma_cm2=sigma_p, sd_p=c_p, sd_n=c_n),
                dd_channels.Channel(kind="SD-neutron", sigma_cm2=sigma_n, sd_p=c_p, sd_n=c_n)]
    if c_p == 0 or c_n == 0:                # one coupling: the plain single-channel comparison, asserted (V1-05)
        kind = "SD-proton" if c_n == 0 else "SD-neutron"
        sigma = sigma_p or sigma_n
        outcome = dd_channels.compare([dd_channels.Channel(kind=kind, sigma_cm2=sigma, sd_p=c_p, sd_n=c_n)], mass)
        [row] = outcome.channels
        if valid[kind]:
            assert row.ratio == pytest.approx(sigma / L[kind]) and row.rate_factor is None and outcome.excluded is False
        else:
            assert row.ratio is None and outcome.excluded is None      # no validated limit: undecided, named
        return
    out = dd_channels._sd_with_interference(channels[0], channels[1], mass)
    if not proton_valid:
        assert out is None
        return
    r, s = sigma_p / L["SD-proton"], sigma_n / L["SD-neutron"]
    if not neutron_valid:
        direct = r * _rate_ratio(PANDAX, "SD-proton", mass, c_n / c_p, NuclearModel.klos)
        assert out.ratio == pytest.approx(direct, rel=1e-9) and out.ratio_band is None
    else:
        low, high = (math.sqrt(r) - math.sqrt(s)) ** 2, (math.sqrt(r) + math.sqrt(s)) ** 2
        assert out.ratio_band == pytest.approx((low, high)) and out.ratio == pytest.approx(high)


@pytest.mark.needs("diamx")
def test_the_outcome_keeps_the_models_own_cross_section(monkeypatch) -> None:
    """The single-kind path's ratio includes F, but the outcome's σ is the model's own, with F recorded beside it: a
    rate-equivalent σ × F had been stored and shown as the point's SD cross section."""
    monkeypatch.setattr(limits, "per_module95", lambda kind, mass_gev, excluded=(): (
        ((PANDAX, 1e-41),) if kind == "SD-proton" else (), ()))
    monkeypatch.setattr(limits, "tolerance", lambda *a: 0.0)
    proton = dd_channels.Channel(kind="SD-proton", sigma_cm2=2e-42, sd_p=1.0, sd_n=1.0)
    neutron = dd_channels.Channel(kind="SD-neutron", sigma_cm2=2e-42, sd_p=1.0, sd_n=1.0)
    out = dd_channels._sd_with_interference(proton, neutron, 250.0)
    factor = dd_channels.single_kind_factor(PANDAX, "SD-proton", 250.0, 1.0)
    assert out.sigma_cm2 == 2e-42 and out.rate_factor == pytest.approx(factor)
    assert out.ratio == pytest.approx(0.2 * factor) and "F = " in out.limit.construction
