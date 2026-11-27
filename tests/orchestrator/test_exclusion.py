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


# --- V1-02 (the independent audit of 1.0.1): stating the module's own halo keeps its SD prescription and validation ---

@pytest.mark.needs("diamx")
@pytest.mark.parametrize("halo", ["omitted", "stated, identical"])
def test_stating_the_published_halo_keeps_the_reference_route(monkeypatch, halo) -> None:
    """PandaX-4T, pure-proton O4 at 250 GeV: omitting the halo and stating the module's identical published halo take
    the same reference SD-proton route (Klos et al.'s responses); no spectrum is computed with the shell model."""
    from adroit.experiments import registry
    module = registry.load_module("PandaX-4T Run0+Run1")
    asked, spectra = [], []
    monkeypatch.setattr(type(module), "reference_limits",
                        lambda self, kind, masses, **k: (asked.append(kind), [1e-41] * len(masses))[1])
    monkeypatch.setattr(type(module), "expected_signal", lambda self, *a, **k: spectra.append(a) or (_ for _ in ()).throw(
        AssertionError("no direct spectrum should be computed")))
    request = exclusion.ExclusionRequest(card_id="O4", values={"c_p": 1e-6, "c_n": 0.0}, masses_gev=[250.0],
                                         modules=["PandaX-4T Run0+Run1"],
                                         halo=None if halo == "omitted" else module.conventions().halo)
    limits = exclusion._module_limits(module, request, [250.0])
    assert limits.route == "reference SD-proton" and [k.value for k in asked] == ["SD-proton"] and not spectra


@pytest.mark.needs("diamx")
def test_a_direct_limit_with_another_prescription_is_not_marked_validated() -> None:
    from adroit.core.dm_state import DarkMatterParticle, NuclearModel
    from adroit.experiments import registry
    module = registry.load_module("PandaX-4T Run0+Run1")
    particle = DarkMatterParticle(mass_gev=250.0)
    interaction = exclusion.library.resolve("O4", particle, {"c_p": 1e-6, "c_n": 0.0})
    assert exclusion.direct_validation(module, interaction, particle, NuclearModel.klos) == ""
    why = exclusion.direct_validation(module, interaction, particle, NuclearModel.shell_model)
    assert why.startswith("unvalidated") and "klos" in why and "shell_model" in why


# --- RA-03 (the repairs audit): a halo's identity is physical, and the prescription does not follow the route -------

@pytest.mark.needs("diamx")
def test_a_label_alone_keeps_the_route_and_a_physical_change_keeps_the_prescription(monkeypatch) -> None:
    """PandaX-4T, pure-proton O4 at 250 GeV. Only the label changed: the reference route. v0 changed by one ULP: a
    different halo, so the direct route, but computed with the limit's own Klos prescription and so validated."""
    import math as _math
    from adroit.experiments import registry
    from adroit.core.dm_state import NuclearModel
    module = registry.load_module("PandaX-4T Run0+Run1")
    published = module.conventions().halo
    seen = []
    monkeypatch.setattr(type(module), "reference_limits", lambda self, kind, masses, **k: [1e-41] * len(masses))
    monkeypatch.setattr(type(module), "expected_signal", lambda self, p, i, halo, model, *a: (
        seen.append(model), ExpectedSignal(experiment="x", interaction_id="i", particle=p, total_events=3.0,
                                           observable=[1.0], density=[1.0]))[1])
    monkeypatch.setattr(type(module), "upper_limits", lambda self, signals, cl=0.9: [1.0] * len(signals))

    def run(halo):
        request = exclusion.ExclusionRequest(card_id="O4", values={"c_p": 1e-6, "c_n": 0.0}, masses_gev=[250.0],
                                             modules=["PandaX-4T Run0+Run1"], halo=halo)
        return exclusion._module_limits(module, request, [250.0])
    relabelled = run(published.model_copy(update={"label": "renamed"}))
    assert relabelled.route == "reference SD-proton" and not seen
    nudged = run(published.model_copy(update={"v0_km_s": _math.nextafter(published.v0_km_s, 1e9)}))
    assert nudged.route == "direct" and set(seen) == {NuclearModel.klos}
    assert nudged.nuclear_models == {repr(250.0): "klos"}


def test_a_saved_result_is_revalidated_with_the_prescription_it_was_computed_with(monkeypatch) -> None:
    """A recorded prescription is the one judged; an older result without one is judged with the prescription its
    direct route used then (``_direct_model``), never credited with today's."""
    from adroit.core.dm_state import NuclearModel
    judged = []
    monkeypatch.setattr(exclusion, "direct_validation", lambda module, i, p, model: judged.append(model) or "")
    monkeypatch.setattr(exclusion, "modules_load", lambda name: type("M", (), {"conventions": lambda self: type(
        "C", (), {"nuclear_model": NuclearModel.helm, "spin_dependent_model": NuclearModel.shell_model})()})())
    request = exclusion.ExclusionRequest(card_id="O4", values={"c_p": 1e-6, "c_n": 0.0}, masses_gev=[250.0])
    row = exclusion.ModuleLimits(experiment="x", masses_gev=[250.0], mu_up=[1.0], validated=[True], route="direct",
                                 fidelity="A")
    def saved(module_row):
        return type("Saved", (), {"per_module": [module_row], "request": request,
                                   "model_copy": lambda self, update: update})()
    exclusion.revalidate(saved(row))                                                  # older: no prescription recorded
    exclusion.revalidate(saved(row.model_copy(update={"nuclear_models": {repr(250.0): "klos"}})))
    assert judged == [NuclearModel.shell_model, NuclearModel.klos]
