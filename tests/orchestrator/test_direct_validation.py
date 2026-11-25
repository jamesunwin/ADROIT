"""R6 (audit M8): a direct-route limit is validated by its response structure, not by the union of a module's
SI and SD ranges."""

import pytest

from adroit.core.dm_state import DarkMatterParticle, NuclearModel
from adroit.experiments import registry as modules
from adroit.library.interactions import registry
from adroit.orchestrator.exclusion import direct_validation


def _at(card: str, isospin: str, mass: float, splitting: float = 0.0):
    particle = DarkMatterParticle(mass_gev=mass, mass_splitting_kev=splitting)
    return registry.resolve(card, particle, registry.isospin_values(card, isospin, 1e-6)), particle


def test_pico_is_no_longer_validated_for_isovector_o1() -> None:
    """PICO-60 is validated for SD-proton only; isovector O₁ uses the spin-independent response."""
    pico = modules.load_module("PICO-60 C3F8 (2019)")
    interaction, particle = _at("O1", "v", 30.0)
    why = direct_validation(pico, interaction, particle, NuclearModel.helm)
    assert why and "spin-independent" in why


def test_isovector_o1_is_validated_where_the_spin_independent_range_is() -> None:
    deap = modules.load_module("DEAP-3600 (2019)")
    interaction, particle = _at("O1", "v", 300.0)
    assert direct_validation(deap, interaction, particle, NuclearModel.helm) == ""


@pytest.mark.parametrize("module", ["DEAP-3600 (2019)", "PICO-60 C3F8 (2019)"])
def test_an_inelastic_splitting_is_not_validated_by_elastic_ranges(module) -> None:
    """The audit's δ = 150 keV at 1 TeV was 'validated' for DEAP and PICO."""
    m = modules.load_module(module)
    interaction, particle = _at("O1", "s", 1000.0, 150.0)
    assert direct_validation(m, interaction, particle, NuclearModel.helm).startswith("unvalidated")


@pytest.mark.needs("diamx")
def test_a_structure_validated_on_xenon_with_haxton_responses_does_not_transfer_to_shell_model() -> None:
    from adroit.experiments import lz_extended_window as lz, structures
    entry = structures.load()["structures"]["L10s"]
    lzws = modules.load_module("LZ WS2022+WS2024")
    particle = DarkMatterParticle(mass_gev=1000.0)
    interaction = registry.resolve("L10", particle, lz.lz_values("L10", "s"))
    why = direct_validation(lzws, interaction, particle, NuclearModel.shell_model)
    assert structures.validated_at(entry, 1000.0) and "haxton_2022" in why and "shell_model" in why


@pytest.mark.needs("cdmslite")
def test_spin_dependent_on_both_nucleons_needs_both_ranges() -> None:
    cdmslite = modules.load_module("CDMSlite Run 2")
    particle = DarkMatterParticle(mass_gev=10.0)
    both = registry.resolve("O4", particle, registry.isospin_values("O4", "s", 1e-6))
    why = direct_validation(cdmslite, both, particle, NuclearModel.klos)
    from adroit.experiments import status
    from adroit.core.dm_state import CrossSectionKind
    has_p = status.validated_range("CDMSlite Run 2", CrossSectionKind.sd_proton) is not None
    assert (why == "") is has_p and (has_p or "SD-proton" in why)


@pytest.mark.needs("cresst")
def test_a_rate_carried_by_contact_o1_is_validated_by_the_si_range() -> None:
    """Mini audit regression: a vector mediator's small momentum-dependent terms (O₃, O₅, O₆, q²O₁) made its
    O₁-dominated rate "unvalidated", so its nulls were dropped and its joint significance rose."""
    from adroit.orchestrator import exclusion, user_models
    from adroit.parameter_space import simplified
    interaction = user_models.interaction(simplified.model("vector", 10.0, 1000.0), 10.0)
    assert exclusion.contact_part(interaction) is not None
    request = exclusion.ExclusionRequest(bespoke={"10.0": interaction}, masses_gev=[10.0], telescopes=False,
                                         modules=["CRESST-III 2019", "PICO-60 C3F8 (2019)"])
    rows = {row.experiment: row for row in exclusion.run(request).per_module}
    assert rows["CRESST-III 2019"].validated == [True]
    assert rows["PICO-60 C3F8 (2019)"].validated == [False]          # no SI range, whatever dominates
