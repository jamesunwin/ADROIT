"""Path 1 (DM5): a card through experiment modules to exclusion limits."""

from __future__ import annotations

import math

import numpy as np
import pytest

from adroit.core.dm_state import (CrossSectionKind, DarkMatterParticle, ExpectedSignal,
                                  ExperimentInfo, Fidelity, HaloModel, InteractionModel,
                                  LimitCurve, NuclearModel, PublishedConventions, Target)
from adroit.experiments.base import REFERENCE_SIGMA_CM2, ExperimentModule, standard_halo
from adroit.library.interactions import registry
from adroit.orchestrator import exclusion
from adroit.physics import targets


class _Fake(ExperimentModule):
    """Limits a fixed number of signal events; reference limits at 4 × the reference σ."""

    @property
    def info(self) -> ExperimentInfo:
        return ExperimentInfo(name="fake", target="Xe", exposure_kg_day=1.0,
                              energy_window_kev=(1.0, 100.0), fidelity=Fidelity.B)

    def target(self) -> Target:
        return targets.target("Xe")

    def conventions(self) -> PublishedConventions:
        return PublishedConventions(halo=standard_halo(220.0, 232.0, 544.0),
                                    nuclear_model=NuclearModel.helm)

    def published_limits(self) -> list[LimitCurve]:
        return []

    def expected_signal(self, particle: DarkMatterParticle, interaction: InteractionModel,
                        halo: HaloModel, model: NuclearModel,
                        target: Target | None = None) -> ExpectedSignal:
        total = 1e12 * sum(c.proton ** 2 + c.neutron ** 2 for c in interaction.coefficients)
        return ExpectedSignal(experiment="fake", particle=particle, total_events=total)

    def upper_limit(self, signal: ExpectedSignal, cl: float = 0.9) -> float:
        return 2.3 / signal.total_events

    def reference_limits(self, kind: CrossSectionKind, masses_gev: list[float],
                         workers: int = 1) -> list[float]:
        return [4.0 * REFERENCE_SIGMA_CM2] * len(masses_gev)


def test_the_reference_route_finds_proportional_interactions() -> None:
    p = DarkMatterParticle(mass_gev=50.0)
    si = registry.resolve("O1", p, registry.isospin_values("O1", "s", 3e-6))
    kind, factor = exclusion._reference_route(si, 50.0)
    assert kind is CrossSectionKind.si and factor > 0
    assert exclusion._reference_route(registry.resolve(
        "O1", p, registry.isospin_values("O1", "v", 3e-6)), 50.0) is None     # isovector: no
    sd_p = registry.resolve("O4", p, {"c_p": 1e-5, "c_n": 0.0})
    assert exclusion._reference_route(sd_p, 50.0)[0] is CrossSectionKind.sd_proton


def test_module_limits_by_both_routes() -> None:
    module = _Fake()
    reference = exclusion.ExclusionRequest(card_id="O1", values={"c_p": 2e-6, "c_n": 2e-6})
    limits = exclusion._module_limits(module, reference, [10.0, 100.0])
    assert limits.route == "reference SI"
    for mass, mu in zip(limits.masses_gev, limits.mu_up):
        _, factor = exclusion._reference_route(
            registry.resolve("O1", DarkMatterParticle(mass_gev=mass), reference.values), mass)
        assert mu == pytest.approx(2.0 / factor)          # √(4σ_ref/σ_ref)/λ
    direct = exclusion.ExclusionRequest(card_id="L10", values={"d_p": 1e-3, "d_n": 1e-3})
    limits = exclusion._module_limits(module, direct, [100.0])
    assert limits.route == "direct"
    interaction = registry.resolve("L10", DarkMatterParticle(mass_gev=100.0), direct.values)
    total = 1e12 * sum(c.proton ** 2 + c.neutron ** 2 for c in interaction.coefficients)
    assert limits.mu_up[0] == pytest.approx(math.sqrt(2.3 / total))


def test_the_envelope_takes_the_strongest_validated_limit() -> None:
    request = exclusion.ExclusionRequest(card_id="O1")
    a = exclusion.ModuleLimits(experiment="a", masses_gev=[1.0, 10.0, 100.0], mu_up=[1.0, 0.1, 0.5],
                               validated=[True, True, True], route="direct", fidelity="B")
    b = exclusion.ModuleLimits(experiment="b", masses_gev=[1.0, 10.0, 100.0], mu_up=[2.0, 0.01, 0.2],
                               validated=[True, False, True], route="direct", fidelity="B")
    result = exclusion.ExclusionResult(request=request, interaction_name="t", per_module=[a, b])
    grid, best, source = result.envelope([1.0, 10.0, 100.0])
    assert best.tolist() == pytest.approx([1.0, 0.1, 0.2]) and source == ["a", "a", "b"]
    _, loose, _ = result.envelope([10.0], validated_only=False)
    assert loose[0] == pytest.approx(0.01)
    assert "envelope" in exclusion.report(result)
    assert np.all(np.isfinite(best))


def test_the_direct_route_uses_the_spin_dependent_nuclear_model() -> None:
    conventions = _Fake().conventions()
    p = DarkMatterParticle(mass_gev=100.0)
    o1 = registry.resolve("O1", p, {"c_p": 1e-5, "c_n": 1e-5})
    l10 = registry.resolve("L10", p, {"d_p": 1e-5, "d_n": 1e-5})
    assert exclusion._direct_model(conventions, o1) is NuclearModel.helm
    assert exclusion._direct_model(conventions, l10) is conventions.spin_dependent_model


@pytest.mark.usefixtures("resigned")
def test_neutrino_telescopes_bound_the_strength_through_capture() -> None:
    """Tier 2 (DM7): C ∝ μ² gives μ_up = √(C_allowed/C), from the verified telescope records."""
    from adroit.constraints import capture
    if capture.fetch.locate(capture.SOLAR_MODEL) is None:
        return
    request = exclusion.ExclusionRequest(card_id="O1", values={"c_p": 1e-8, "c_n": 1e-8},
                                         masses_gev=[10.0, 100.0, 1000.0], modules=["DEAP-3600 (2019)"])
    limits = exclusion.telescope_limits(request)
    assert {(t.record_id, t.channel) for t in limits} >= {("icecube-1612.05949-sd", "bb")}
    sd_bb = next(t for t in limits if t.record_id.endswith("-sd") and t.channel == "bb")
    assert math.isnan(sd_bb.mu_up[0])                          # b b̄ starts at 35 GeV
    assert 0.0 < sd_bb.mu_up[1] < math.inf and sd_bb.verified
