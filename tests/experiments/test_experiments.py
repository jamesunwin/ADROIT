"""The experiment interface, its shared tools, and each module's reproduction of its limit."""

from __future__ import annotations

import math

import numpy as np
import pytest
from pydantic import ValidationError

from adroit.core.dm_state import (CrossSectionKind, DarkMatterParticle, ExperimentInfo,
                                      Fidelity, LimitCurve, NuclearModel, PublishedConventions,
                                      ValidationResult)
from adroit.experiments import base, diamx_driver, status, validation, xenon
from adroit.experiments.cdmslite import electron_equivalent, lindhard_yield, nuclear_recoil
from adroit.external import fetch
from adroit.physics import conventions as cv
from adroit.physics import rates, targets


def _fetched(item: str) -> bool:
    return fetch.locate(item) is not None


# --- shared tools --------------------------------------------------------------------


def test_a_reference_interaction_has_the_requested_cross_section() -> None:
    si = base.reference_interaction(CrossSectionKind.si, 1e-45, 50.0)
    (c,) = si.coefficients
    assert c.operator == 1 and c.proton == c.neutron
    assert cv.sigma_si_cm2(c.proton, 50.0) == pytest.approx(1e-45, rel=1e-6, abs=0)
    sdn = base.reference_interaction(CrossSectionKind.sd_neutron, 1e-40, 50.0)
    (c,) = sdn.coefficients
    assert c.operator == 4 and c.proton == 0.0
    assert cv.sigma_sd_cm2(c.neutron, 50.0) == pytest.approx(1e-40, rel=1e-6, abs=0)


def test_the_spin_dependent_convention_matches_the_rate_on_a_free_nucleon() -> None:
    # A spin-1/2 "nucleus" with <S_p> = 1/2 is a free proton: the rate code's SD
    # normalisation, ρ j(j+1)(J+1)/(6πJ) (c S)², must equal ρ σ/(2 μ² m) for σ = 3c²μ²/(16π).
    c, mass, j_n = 1e-3, 30.0, 0.5
    via_rate = 0.3 / mass * 0.75 * (j_n + 1) / (6 * math.pi * j_n) * (c * 0.5) ** 2
    mu = cv.reduced_mass(mass, cv.M_NUCLEON_GEV)
    via_sigma = 0.3 * (cv.sigma_sd_cm2(c, mass) / cv.HBARC_GEV_CM ** 2) / (2 * mu ** 2 * mass)
    assert via_rate == pytest.approx(via_sigma, rel=1e-12)


def test_smearing_is_exact_for_a_linear_density_on_any_grid() -> None:
    coarse = np.linspace(0.0, 10.0, 11)
    reco = np.array([2.3, 5.05, 7.7])
    assert base.smear(coarse, 1.0 + 0.3 * coarse, reco, 0.004) == pytest.approx(1.0 + 0.3 * reco)
    # and a peak is broadened, not moved: a narrow spike smeared by σ keeps its mean
    fine = np.linspace(0.0, 2.0, 4001)
    spike = np.exp(-0.5 * ((fine - 1.0) / 0.001) ** 2)
    reco = np.linspace(0.8, 1.2, 801)
    out = base.smear(fine, spike, reco, 0.02)
    assert np.trapezoid(out * reco, reco) / np.trapezoid(out, reco) == pytest.approx(1.0, abs=1e-6)


def test_element_rates_add_up_to_the_target_rate() -> None:
    energies = np.array([1.0, 5.0, 20.0])
    particle = DarkMatterParticle(mass_gev=60.0)
    interaction = base.reference_interaction(CrossSectionKind.si, 1e-45, 60.0)
    cawo4 = targets.target("CaWO4")
    parts = base.element_rates(energies, particle, interaction, cawo4, base.standard_halo(
        220, 232, 544), NuclearModel.helm)
    total = rates.differential_rate(energies, particle, interaction, cawo4,
                                    halo=base.standard_halo(220, 232, 544),
                                    model=NuclearModel.helm).rate
    assert set(parts) == {"Ca", "W", "O"}
    assert sum(parts.values()) == pytest.approx(total)


def test_the_older_halo_convention() -> None:
    halo = base.standard_halo(220.0, 232.0, 544.0)
    assert halo.v_lab_km_s == pytest.approx(232.0) and halo.v0_km_s == 220.0


def test_reading_tables(tmp_path) -> None:
    table = tmp_path / "t.dat"
    table.write_text("# comment\n1 2\n3 4 5\n\n6, 7\n")
    assert base.read_columns(table).tolist() == [[1, 2], [3, 4], [6, 7]]


def test_the_germanium_energy_scale() -> None:
    # a nuclear recoil reads low in electron-equivalent energy, and the conversion inverts
    assert 0.1 < float(lindhard_yield(np.array([1.0]))[0]) < 0.3
    for kevee in (0.056, 0.3, 2.0):
        e_nr = nuclear_recoil(kevee)
        assert e_nr > kevee
        assert float(electron_equivalent(np.array([e_nr]))[0]) == pytest.approx(kevee, rel=1e-10)


def test_the_xenon_bridge_labels_and_configures() -> None:
    a = np.array([1.0, 2.0, 3.0])
    assert xenon.spectrum_label(a) == xenon.spectrum_label(a.copy())
    assert xenon.spectrum_label(a) != xenon.spectrum_label(a * 1.000001)
    config = {"experiments": [{"bkgs": [{"args": {"batch_size": 5}}, {"args": {}}],
                               "shaped_bkgs": [{"args": {"batch_size": 5}}],
                               "eff": {"args": {"batch_size": 5}}}],
              "signal": {"parameter_range": "range(3)", "args": {"batch_size": 5}}}
    new = diamx_driver.configure(config, [7, 9], "/spectra", 1000)
    assert new["signal"]["parameter_range"] == [7, 9]
    assert new["signal"]["args"]["signal_spectrum_path"] == "/spectra/wimp_{mass:d}GeV.csv"
    assert new["experiments"][0]["bkgs"][0]["args"]["batch_size"] == 1000
    assert "batch_size" not in new["experiments"][0]["bkgs"][1]["args"]
    assert config["signal"]["parameter_range"] == "range(3)"         # the input is untouched


# --- validation ----------------------------------------------------------------------


def test_the_validation_rule() -> None:
    result = ValidationResult(experiment="x", kind=CrossSectionKind.si, masses_gev=[1, 2, 3],
                              published_cm2=[1.0, 1.0, 1.0], reproduced_cm2=[1.29, 0.78, 1.0])
    assert result.passed and result.ratios == pytest.approx([1.29, 0.78, 1.0])
    assert not result.model_copy(update={"reproduced_cm2": [1.31, 1.0, 1.0]}).passed
    curve = LimitCurve(experiment="x", kind=CrossSectionKind.si, masses_gev=[1.0, 100.0],
                       cross_sections_cm2=[1e-40, 1e-44])
    assert validation.published_at(curve, np.array([10.0]))[0] == pytest.approx(1e-42, rel=1e-6, abs=0)
    assert validation.trial_masses(curve, 3).tolist() == pytest.approx([1.0, 10.0, 100.0])
    with pytest.raises(ValidationError):
        LimitCurve(experiment="x", kind=CrossSectionKind.si, masses_gev=[1.0, 2.0],
                   cross_sections_cm2=[1e-40, math.inf])


def test_a_point_at_a_steep_edge_passes_by_a_small_shift_in_mass() -> None:
    result = ValidationResult(experiment="x", kind=CrossSectionKind.si, masses_gev=[1, 2, 3],
                              published_cm2=[1.0, 1.0, 1.0], reproduced_cm2=[0.5, 1.0, 1.0],
                              edge_passes=[True, False, False])
    assert result.point_passes == [True, True, True] and result.passed
    assert not result.model_copy(update={"edge_passes": []}).passed


def test_the_validated_range_surrounds_the_strongest_published_limit() -> None:
    masses = [1.0, 2.0, 5.0, 10.0, 20.0, 50.0]
    result = ValidationResult(experiment="x", kind=CrossSectionKind.si, masses_gev=masses,
                              published_cm2=[1e-38, 1e-40, 1e-42, 1e-43, 2e-43, 5e-43],
                              reproduced_cm2=[5e-38, 1.1e-40, 1e-42, 1e-43, 2e-43, 5e-43])
    assert not result.passed and result.validated_range == (2.0, 50.0)
    assert result.counts_for_gate                                  # 50/2 ≥ 10
    short = result.model_copy(update={"reproduced_cm2": [1e-38, 1e-40, 3e-42, 1e-43, 2e-43, 1e-42]})
    assert short.validated_range == (10.0, 20.0) and not short.counts_for_gate
    # failing where the published limit is strongest (10 GeV): the widest passing run is
    # validated, but the module does not count for the gate
    worst = result.model_copy(update={"reproduced_cm2": [1e-38, 1e-40, 1e-42, 1e-42, 2e-43, 5e-43]})
    assert worst.strongest_mass_gev == 10.0 and worst.validated_range == (1.0, 5.0)
    assert not worst.counts_for_gate
    wide = ValidationResult(experiment="x", kind=CrossSectionKind.si,
                            masses_gev=[1.0, 10.0, 100.0, 1000.0, 10000.0],
                            published_cm2=[1e-40, 1e-44, 2e-44, 1e-43, 1e-42],
                            reproduced_cm2=[1e-40, 3e-44, 2e-44, 1e-43, 1e-42])
    assert wide.validated_range == (100.0, 10000.0) and not wide.counts_for_gate
    nothing = wide.model_copy(update={"reproduced_cm2": [1e-39] * 5})
    assert nothing.validated_range is None and not nothing.counts_for_gate


def test_a_splitting_scan_counts_by_half_its_range() -> None:
    result = ValidationResult(experiment="x", model="O01s@1000GeV", variable="splitting (keV)",
                              quantity="coupling", masses_gev=[0.0, 100.0, 200.0, 300.0],
                              published_cm2=[1.0, 2.0, 3.0, 4.0],
                              reproduced_cm2=[1.0, 2.0, 3.0, 9.0])
    assert result.key == "O01s@1000GeV" and result.validated_range == (0.0, 200.0)
    assert result.counts_for_gate                       # 200 of 300 keV, holding δ = 0
    with pytest.raises(ValidationError):
        ValidationResult(experiment="x", masses_gev=[1.0], published_cm2=[1.0],
                         reproduced_cm2=[1.0])           # neither a kind nor a model


class _Stepped:
    """A module whose limit is a step: 1e-40 below 10 GeV, 1e-44 at and above it."""

    info = ExperimentInfo(name="stepped", target="Xe", exposure_kg_day=1.0,
                          energy_window_kev=(1.0, 10.0), fidelity=Fidelity.B,
                          statistical_method="none")

    def published_target(self, kind: CrossSectionKind) -> None:
        return None

    def limits_on(self, kind: CrossSectionKind, masses: list[float], target: object = None) -> list:
        return [1e-40 if m < 10.0 else 1e-44 for m in masses]


def test_the_edge_clause_checks_both_sides_of_a_steep_limit() -> None:
    # published: a wall at 10 GeV reached smoothly between 9.8 and 10.2 GeV
    curve = LimitCurve(experiment="x", kind=CrossSectionKind.si, masses_gev=[9.8, 10.2, 100.0],
                       cross_sections_cm2=[1e-40, 1e-44, 1e-44])
    result = validation.validate(_Stepped(), curve, [10.0, 50.0])      # type: ignore[arg-type]
    assert result.ratios[0] > 1.3 or result.ratios[0] < 1 / 1.3
    assert abs(validation.published_slope(curve, 10.0)) > validation.EDGE_SLOPE
    assert result.edge_passes == [True, False] and result.passed
    # a limit wrong by a shift of more than 3% in mass fails
    late = curve.model_copy(update={"masses_gev": [9.0, 9.4, 100.0]})
    shifted = validation.validate(_Stepped(), late, [9.2])            # type: ignore[arg-type]
    assert shifted.edge_passes == [False] and not shifted.passed


def test_the_status_record_of_a_comparison() -> None:
    result = ValidationResult(experiment="x", kind=CrossSectionKind.sd_neutron,
                              masses_gev=[1.0, 3.0, 30.0], published_cm2=[1e-36, 1e-38, 1e-39],
                              reproduced_cm2=[5e-36, 1.2e-38, 0.9e-39],
                              edge_passes=[False, False, False])
    record = status.entry(result)
    assert record["validated_gev"] == [3.0, 30.0] and record["counts_for_gate"]
    assert record["ratio_range_inside"] == [0.9, 1.2] and not record["every_mass_passes"]
    assert status.validated_range("no such module", CrossSectionKind.si) is None


def test_modules_report_the_validated_range_of_the_last_run() -> None:
    recorded = status.validated_ranges().get("modules", {})
    if "PICO-60 C3F8 (2019)" not in recorded:
        pytest.skip("no validation run recorded")
    from adroit.experiments.pico60 import Pico60
    low, high = Pico60().validated_range(CrossSectionKind.sd_proton)
    assert low < 5.0 and high > 500.0


def test_published_conventions_choose_the_nuclear_input_by_kind() -> None:
    conventions = PublishedConventions(halo=base.standard_halo(220, 232, 544))
    assert conventions.model_for(CrossSectionKind.si) is NuclearModel.helm
    assert conventions.model_for(CrossSectionKind.sd_proton) is NuclearModel.shell_model


# --- the modules against their published limits (need fetched data) ------------------


@pytest.mark.skipif(not _fetched("CRESST-III data release (arXiv:1905.07335)"),
                    reason="CRESST-III release not fetched")
def test_cresst_iii_reproduces_its_spin_independent_limit() -> None:
    from adroit.experiments.cresst_iii import CresstIII2019
    module = CresstIII2019()
    assert len(module.events) == 441
    si = next(c for c in module.published_limits() if c.kind is CrossSectionKind.si)
    result = validation.validate(module, si, si.masses_gev)
    # the cut survival in true energy (the owner's reading) validates from 0.35 GeV up
    low, high = result.validated_range
    assert low < 0.4 and high > 100.0 and result.counts_for_gate, result.ratios


@pytest.mark.skipif(not _fetched("CDMSlite Run 2 data release (arXiv:1707.01632)"),
                    reason="CDMSlite release not fetched")
def test_cdmslite_reproduces_the_release_best_fit_limit_away_from_threshold() -> None:
    from adroit.experiments.cdmslite import CdmsliteRun2
    module = CdmsliteRun2()
    assert len(module.events) == 318
    table = base.read_columns(module.folder / "limits_SI_GeVc2_cm2.txt", columns=2)
    table = table[np.isfinite(table[:, 1]) & (table[:, 0] > 1.5)][::10]
    ours = module.limits_on(CrossSectionKind.si, table[:, 0].tolist())
    assert np.array(ours) / table[:, 1] == pytest.approx(1.0, abs=0.03)


@pytest.mark.skipif(not _fetched("CDMSlite Run 2 data release (arXiv:1707.01632)"),
                    reason="CDMSlite release not fetched")
def test_cdmslite_official_limits_do_not_depend_on_the_number_of_processes() -> None:
    from adroit.experiments.cdmslite import CdmsliteRun2
    module = CdmsliteRun2()
    masses = [3.0, 10.0]
    serial = module.official_limits(CrossSectionKind.sd_neutron, masses, realisations=4)
    assert serial == [module.official_limit(CrossSectionKind.sd_neutron, m, 4) for m in masses]
    assert module.official_limits(CrossSectionKind.sd_neutron, masses, realisations=4,
                                  workers=2) == serial


def test_pico60_reproduces_its_spin_dependent_limit_away_from_threshold() -> None:
    from adroit.experiments.pico60 import Pico60
    module = Pico60()
    (curve,) = module.published_limits()
    result = validation.validate(module, curve, np.geomspace(6.0, 900.0, 5))
    assert result.passed, result.ratios


def test_deap3600_reproduces_its_limit_at_high_mass() -> None:
    from adroit.experiments.deap3600 import Deap3600
    module = Deap3600()
    (curve,) = module.published_limits()
    result = validation.validate(module, curve, np.geomspace(100.0, 9000.0, 4))
    assert result.passed, result.ratios


def test_the_digitised_figures_match_the_papers_quoted_numbers() -> None:
    from adroit.experiments import digitised
    pico = digitised.load("pico60_2019_fig6_fig7")["limit_sd_proton"]
    deap = digitised.load("deap3600_2019_fig24")["deap3600_this_work"]

    def at(curve: dict, mass: float) -> float:
        return float(np.exp(np.interp(np.log(mass), np.log(curve["mass_gev"]),
                                      np.log(curve["cross_section_cm2"]))))

    assert at(pico, 25.0) == pytest.approx(2.5e-41, rel=0.03)      # arXiv:1902.04031, abstract
    assert at(deap, 100.0) == pytest.approx(3.9e-45, rel=0.03)     # arXiv:1902.04048, abstract
    assert at(deap, 1000.0) == pytest.approx(1.5e-44, rel=0.03)
    fig3 = digitised.load("pico60_2019_fig3")
    assert fig3["threshold_2.45_keV"]["seitz_line_kev"] == pytest.approx(2.45, abs=0.005)
    assert fig3["threshold_3.29_keV"]["seitz_line_kev"] == pytest.approx(3.29, abs=0.005)


def test_the_registry_knows_every_module() -> None:
    from adroit.experiments import registry
    assert "CRESST-III 2019" in registry.module_names()
    assert "LZ WS2022+WS2024" in registry.module_names()
    with pytest.raises(KeyError):
        registry.load_module("no such search")


@pytest.mark.skipif(not _fetched("CDMSlite Run 2 data release (arXiv:1707.01632)"),
                    reason="CDMSlite release not fetched")
def test_cdmslite_official_procedure_reproduces_the_official_median() -> None:
    from adroit.experiments.cdmslite import CdmsliteRun2
    module = CdmsliteRun2()
    si = module.published_limits()[0]
    ours = module.official_limit(CrossSectionKind.si, 5.0, realisations=40)
    assert ours / validation.published_at(si, np.array([5.0]))[0] == pytest.approx(1.0, abs=0.1)


@pytest.mark.skipif(not _fetched("LZ extended window (arXiv:2609.02823)"),
                    reason="the LZ record is a manual download")
def test_the_lz_extended_window_tables_and_samples() -> None:
    from adroit.experiments import lz_extended_window as lz
    tables = lz.model_tables()
    assert len(tables) == 43 and {"L01s", "L20v", "O01s", "O01v", "O04s"} <= set(tables)
    # the paper's largest local significance, 3.4σ, is in the tables
    assert max(max(t.local_significance) for t in tables.values()) == pytest.approx(3.4)
    assert tables["O04s"].splitting_kev and not tables["L01s"].splitting_kev
    assert lz.event_sample("Science").shape == (1710, 2)
    with pytest.raises(ValueError):
        lz.event_sample("Calibration")


@pytest.mark.slow
@pytest.mark.skipif(not _fetched("DIAMX"), reason="DIAMX not built")
def test_the_xenon_bridge_sets_an_lz_limit() -> None:
    """One DIAMX run at 40 GeV (minutes): the limit lies near LZ's published one."""
    module = xenon.DiamxXenon("LZ WS2022+WS2024")
    curve = next(c for c in module.published_limits() if c.kind is CrossSectionKind.si)   # SD curves too since R2
    ours = module.limit_on(CrossSectionKind.si, 40.0)
    assert ours / validation.published_at(curve, np.array([40.0]))[0] == pytest.approx(1.2, abs=0.15)


def test_our_rate_matches_lz_own_spectrum_and_coupling_convention() -> None:
    """LZ's Fig. 1 (elastic O1s, 1 TeV, c^s = 1/m_v²) at low recoil energy, where it is smooth."""
    from adroit.core.dm_state import InteractionModel, ModelLayer, OperatorCoefficient
    from adroit.experiments import digitised
    spectrum = digitised.load("lz_2026_fig1")["spectra"]["O1s_delta_0_keV_m_1000"]
    energies = np.array(spectrum["energy_kev"])
    reference = np.array(spectrum["rate_per_tonne_year_kev"])
    low = energies < 20.0
    c = cv.coupling_gev2(1.0)
    interaction = InteractionModel(name="O1s", layer=ModelLayer.nonrelativistic,
                                   coefficients=[OperatorCoefficient(operator=1, proton=c, neutron=c)])
    ours = np.array(rates.differential_rate(energies[low], DarkMatterParticle(mass_gev=1000.0),
                                            interaction, targets.target("Xe")).rate) * 365_250.0
    assert ours == pytest.approx(reference[low], rel=0.05)


def test_the_lz_efficiency_crosses_one_half_where_the_paper_says() -> None:
    from adroit.experiments import digitised
    figure = digitised.load("lz_2026_figS2")
    energies, efficiency = np.array(figure["energy_kev"]), np.array(figure["efficiency"])
    tail = energies > 250.0
    assert np.interp(0.5, efficiency[tail][::-1], energies[tail][::-1]) == pytest.approx(269.9, abs=0.5)
    rise = energies < 50.0
    assert np.interp(0.5, efficiency[rise], energies[rise]) == pytest.approx(5.4, abs=0.5)


def test_a_spectrum_diamx_cannot_use_gets_no_limit(monkeypatch) -> None:
    # DIAMX returns nothing for a spectrum with no events in its region of interest
    module = xenon.DiamxXenon.__new__(xenon.DiamxXenon)
    module.search = "XENONnT SR0+SR1"
    module.spec = xenon.SEARCHES["XENONnT SR0+SR1"]
    monkeypatch.setattr(xenon.DiamxXenon, "run", lambda self, signals, cl=0.9: {})
    monkeypatch.setattr(xenon.DiamxXenon, "info", property(lambda self: type(
        "Info", (), {"name": "XENONnT SR0+SR1"})()))
    signal = base.ExpectedSignal(experiment="x", particle=DarkMatterParticle(mass_gev=1000.0),
                                 total_events=1e-3, observable=[1.0, 2.0], density=[1e-3, 1e-3])
    with pytest.warns(UserWarning, match="no limit"):
        assert module.upper_limits([signal]) == [math.inf]
