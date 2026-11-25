"""The viability checklist for thermal freeze-out dark matter (the owner's list, 2026-10-01)."""

from __future__ import annotations

from adroit.constraints import viability as v
from adroit.core.model_spec import FieldRole, ModelCoupling, ModelField, ModelSpec, ModelTerm, Occurrence

GROUPS = {"thermal": 7, "searches": 9, "cosmology": 6, "theory": 6}


def scalar_mediator(m_dm: float, m_med: float, g: float = 1.0, sm: str = "q", cosmology: str = "") -> ModelSpec:
    chi = ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, mass_gev=m_dm, dark_parity=-1)
    phi = ModelField(name="phi", role=FieldRole.mediator, spin=0.0, self_conjugate=True, mass_gev=m_med,
                     dark_parity=1)
    f = ModelField(name=sm, role=FieldRole.standard_model, spin=0.0 if sm == "h" else 0.5)
    terms = [ModelTerm(fields=[Occurrence(field="chi", conjugate=True), Occurrence(field="chi"),
                               Occurrence(field="phi")], lorentz="scalar", coupling="g"),
             ModelTerm(fields=[Occurrence(field=sm, conjugate=True), Occurrence(field=sm),
                               Occurrence(field="phi")], lorentz="scalar", coupling="g")]
    extra = {"cosmology": cosmology} if cosmology else {}
    return ModelSpec(name="s", fields=[chi, phi, f], terms=terms, stability="Z2",
                     couplings=[ModelCoupling(name="g", value=g)], **extra)


def by_id(entries: list[v.Entry]) -> dict[str, v.Entry]:
    return {e.id: e for e in entries}


def test_the_owner_s_list_is_complete_and_every_item_has_a_rule() -> None:
    items = v.items()
    assert len(items) == 28 and len({i.id for i in items}) == 28
    assert {g: sum(i.group == g for i in items) for g in GROUPS} == GROUPS and set(v.groups()) == set(GROUPS)
    assert set(v.RULES) == {i.id for i in items}
    assert all(i.built and i.planned for i in items)


def test_a_heavy_weak_scale_model() -> None:
    e = by_id(v.assess(scalar_mediator(100.0, 1000.0), done={"direct_detection", "neutrino_fluxes"}))
    assert e["direct_detection"].status is v.Status.checked and e["neutrino_fluxes"].status is v.Status.checked
    assert e["relic_abundance"].status is v.Status.applies and "UFO" in e["relic_abundance"].planned
    assert e["cosmological_history"].status is v.Status.assumed
    for light in ("beam_dumps", "rare_meson_decays", "stellar_cooling", "bbn_neff", "free_streaming",
                  "self_interactions", "plasma_scattering", "sommerfeld_bound_states", "secluded_sector"):
        assert e[light].status is v.Status.not_applicable, light
    assert e["stability_mechanism"].status is v.Status.checked and e["eft_validity"].status is v.Status.checked


def test_a_light_mediator_turns_on_the_light_sector_checks() -> None:
    e = by_id(v.assess(scalar_mediator(10.0, 0.01)))
    for item in ("beam_dumps", "rare_meson_decays", "stellar_cooling", "bbn_neff", "self_interactions",
                 "sommerfeld_bound_states", "secluded_sector", "kinetic_equilibrium"):
        assert e[item].status is v.Status.applies, item
    assert e["eft_validity"].status is v.Status.flagged
    assert e["plasma_scattering"].status is v.Status.not_applicable       # 10 MeV: a contact at recombination
    assert by_id(v.assess(scalar_mediator(0.5, 0.01)))["plasma_scattering"].status is v.Status.applies


def test_a_resonance_and_the_invisible_higgs() -> None:
    resonant = by_id(v.assess(scalar_mediator(100.0, 210.0)))
    assert "resonance" in resonant["coannihilation_resonance_threshold"].detail
    assert resonant["kinetic_equilibrium"].status is v.Status.applies
    higgs = by_id(v.assess(scalar_mediator(40.0, 1000.0, sm="h")))
    assert "invisible Higgs" in higgs["precision"].detail


def test_a_stated_non_standard_history_is_not_assumed_away() -> None:
    e = by_id(v.assess(scalar_mediator(100.0, 1000.0, cosmology="early matter domination until 10 GeV")))
    assert e["cosmological_history"].status is v.Status.applies


def test_the_report_lists_every_item() -> None:
    entries = v.assess(scalar_mediator(100.0, 1000.0))
    text = v.report(entries)
    assert all(i.title in text for i in v.items()) and "Totals:" in text
