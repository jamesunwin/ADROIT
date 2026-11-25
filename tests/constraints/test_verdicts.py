"""DM7: capture in the Sun, the curated database and the applicability verdicts."""

from __future__ import annotations

import math

import numpy as np
import pytest

from adroit.constraints import capture, database, spin1, verdicts
from adroit.core.dm_state import (Applicability, ConstraintClass, DarkMatterParticle, HaloModel,
                                  InteractionModel, OperatorCoefficient)
from adroit.physics import conventions

pytestmark = pytest.mark.skipif(capture.fetch.locate(capture.SOLAR_MODEL) is None,
                                reason="the B16 solar model has not been fetched")

DARKSUSY_HALO = HaloModel(rho_gev_cm3=0.3, v0_km_s=220.0, v_esc_km_s=2000.0,
                          v_lsr_km_s=(0.0, 220.0, 0.0), v_peculiar_km_s=(0.0, 0.0, 0.0))


def sd_proton(sigma: float, m: float) -> InteractionModel:
    c4 = conventions.c4_from_sigma_sd(sigma, m)
    return InteractionModel(name="SD-p", layer="nonrelativistic",
                            coefficients=[OperatorCoefficient(operator=4, proton=c4, neutron=0.0)])


# --- capture ---------------------------------------------------------------------------

def test_the_suns_escape_speed() -> None:
    sun = capture.solar_model()
    assert sun.escape_speed[-1] * conventions.C_KM_S == pytest.approx(618, rel=0.01)
    assert sun.escape_speed[0] * conventions.C_KM_S == pytest.approx(1380, rel=0.02)


def test_the_window_of_recoil_energies() -> None:
    """Elastic: 0 to 2μ²w²/m_T. Inelastic: closed below w² = 2δ/μ."""
    m_t, mu, w = 52.0, 49.0, np.array([4e-3])
    low, high = capture.recoil_window(w, m_t, mu, 0.0)
    assert low[0] == 0.0 and high[0] == pytest.approx(2 * mu ** 2 * w[0] ** 2 / m_t)
    delta = 300e-6
    low, high = capture.recoil_window(np.array([math.sqrt(2 * delta / mu) * 0.99]), m_t, mu, delta)
    assert high[0] == low[0] == 0.0
    low, high = capture.recoil_window(np.array([5e-3]), m_t, mu, delta)
    assert 0.0 < low[0] < high[0]


def test_capture_reproduces_icecubes_darksusy_benchmark() -> None:
    """arXiv:1601.00653, Table 1: m = 147.5 GeV, σ′_SD,p = 2.7e-40 cm², C = 3.2e22/s (docs/dm7)."""
    c = capture.capture_rate(DarkMatterParticle(mass_gev=147.5), sd_proton(2.7e-40, 147.5), DARKSUSY_HALO)
    assert c == pytest.approx(3.2e22, rel=0.1)


def test_capture_is_linear_in_the_cross_section() -> None:
    m = 200.0
    one = capture.capture_rate(DarkMatterParticle(mass_gev=m), sd_proton(1e-40, m))
    two = capture.capture_rate(DarkMatterParticle(mass_gev=m), sd_proton(2e-40, m))
    assert two == pytest.approx(2 * one, rel=1e-9)


def test_a_large_splitting_cannot_be_captured() -> None:
    """With δ = 2 MeV no solar nucleus can be upscattered: w² < 2δ/μ everywhere."""
    m = 1000.0
    c1 = conventions.coupling_gev2(1.0)
    o1 = InteractionModel(name="O1", layer="nonrelativistic",
                          coefficients=[OperatorCoefficient(operator=1, proton=c1, neutron=c1)])
    assert capture.capture_rate(DarkMatterParticle(mass_gev=m, mass_splitting_kev=2000.0), o1) == 0.0
    assert capture.capture_rate(DarkMatterParticle(mass_gev=m, mass_splitting_kev=100.0), o1) > 0.0


def test_equilibrium_fraction() -> None:
    assert capture.equilibrium_fraction(1e24, 3e-26, 100.0, self_conjugate=True) == pytest.approx(1.0, abs=1e-6)
    assert capture.equilibrium_fraction(1e14, 1e-30, 1000.0, self_conjugate=True) < 0.01
    assert capture.equilibrium_fraction(0.0, 3e-26, 100.0, self_conjugate=True) == 0.0


# --- the database ----------------------------------------------------------------------

PORTAL_LIBRARY_2 = {"planck-2018-pann", "darkcast-dark-photon", "flavour-b-to-k-invisible", "atlas-1903.06248-dilepton",
                    "lep-contact-bl", "atlas-2010.14293-squark", "muon-g2-2025", "lmu-ltau-babar-belle2",
                    "lep-inert-doublet", "atlas-2306.00641-2hdma",
                    "smodels-3.2.1", "sabti-1910.01649-bbn", "ccfr-1406.2332-trident",          # part 3
                    "atlas-2207.00092-higgs-mu", "fermi-lat-1506.00013-lines", "hess-1805.05741-lines",
                    "hess-2608.07234-lines", "calore-2202.03076-pbar", "atlas-2009.14791-zz", "atlas-2004.14636-ww",
                    "cms-2107.13021-monojet-spin0",                                               # part 4
                    "cms-1806.00843-dijet", "atlas-1910.08447-dijet-gaussian", "cms-1908.01115-ttbar",
                    "atlas-2108.13391-monoh", "atlas-2111.08372-monoz"}                           # part 5


def test_every_record_loads_and_all_but_the_newest_are_verified() -> None:
    records = database.records()
    assert {r.constraint_class for r in records} >= {ConstraintClass.relic_density, ConstraintClass.collider,
                                                      ConstraintClass.solar_capture,
                                                      ConstraintClass.indirect_detection, ConstraintClass.cosmology,
                                                      ConstraintClass.beam_dump, ConstraintClass.flavour}
    # the portal library's parts 2–5 await verification; the records verified up to 2026-10-03 count once their
    # signatures match their content (R9 re-signs the corrected ones)
    unverified = {r.id for r in records if not r.usable}
    from adroit.constraints.review_identity import signature_status
    # each awaits verification, or the owner has since signed it with a seal bound to its current content (R9)
    for r in records:
        if r.id in PORTAL_LIBRARY_2 | {'planck-2018-omega', 'fermi-2311.04982-spectral'}:
            assert r.id in unverified or signature_status(r).state == "current", r.id
    assert all(signature_status(r).state in ("stale", "unreviewed") for r in records if r.id in unverified)
    for r in records:
        if r.data_file:
            assert database.data(r.id)


def test_an_unverified_record_is_not_used(monkeypatch) -> None:
    """A person verifies each record before it is used (build plan, DM7)."""
    proposed = database.record("planck-2018-omega").model_copy(
        update={"id": "proposed", "verified_on": None, "verified_by": ""})
    shipped = database.records()
    monkeypatch.setattr(database, "records", lambda: (*shipped, proposed))
    assert "proposed" not in {r.id for r in database.usable()}
    assert "proposed" in {r.id for r in database.usable(include_unverified=True)}


def test_limits_interpolate_in_log_space() -> None:
    points = [[10.0, 1e-40], [1000.0, 1e-38]]
    assert database.interpolate_limit(points, 100.0) == pytest.approx(1e-39, rel=1e-6, abs=0)
    assert database.interpolate_limit(points, 5.0) is None


def test_the_digitised_fermi_limit_matches_the_papers_statement() -> None:
    """Fermi-LAT excludes the thermal 2.2e-26 cm³/s below 100 GeV for b b̄ (arXiv:1503.02641)."""
    bb = database.data("fermi-1503.02641-dsph")["limits"]["bb"]["limit_cm3_s"]
    assert database.interpolate_limit(bb, 100.0) == pytest.approx(2.2e-26, rel=0.05)


# --- verdicts --------------------------------------------------------------------------

def candidate(name: str, m_med: float, m_dm: float) -> verdicts.Candidate:
    completion = spin1.benchmark(name, m_med)
    return verdicts.Candidate(label=f"{name}", particle=DarkMatterParticle(mass_gev=m_dm),
                              interaction=spin1.interaction(completion, m_dm), completion=completion)


@pytest.mark.parametrize("m_med,m_dm,excluded", [(1000.0, 100.0, True), (5000.0, 100.0, False),
                                                  (500.0, 1000.0, True)])
def test_the_collider_summary_on_its_own_benchmark(m_med, m_dm, excluded) -> None:
    v = verdicts.collider(candidate("V1", m_med, m_dm), database.record("cms-2405.13778-V1"))
    assert v.applicability is Applicability.applies and v.excluded is excluded


def test_a_summary_needs_a_recast_for_another_model() -> None:
    v = verdicts.collider(candidate("A1", 1000.0, 100.0), database.record("cms-2405.13778-V1"))
    assert v.applicability is Applicability.needs_calculation and v.excluded is None
    assert "recast" in v.needed_calculation


def test_tier_three_needs_a_completion() -> None:
    bare = candidate("V1", 1000.0, 100.0).model_copy(update={"completion": None})
    for record_id in ("planck-2018-omega", "cms-2405.13778-V1", "fermi-1503.02641-dsph"):
        v = verdicts.verdict(bare, database.record(record_id))
        assert v.applicability is Applicability.needs_calculation
        assert "completion" in v.needed_calculation


def test_tier_two_applies_to_an_operator_alone() -> None:
    """Capture needs only the interaction; the channel and equilibrium are then assumed."""
    bare = candidate("V1", 1000.0, 100.0).model_copy(update={"completion": None})
    v = verdicts.verdict(bare, database.record("icecube-1612.05949-si"))
    assert v.applicability is Applicability.needs_calculation
    assert any("equilibrium" in a for a in v.assumptions)
    assert v.excluded is None and v.native_excluded is True  # native 90%: σ_SI ≈ 6e-41 cm² is far above IceCube's limit


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_overabundance_excludes_under_a_thermal_history() -> None:
    record = database.record("planck-2018-omega")
    over = verdicts.relic(candidate("V1", 5000.0, 100.0), record)
    assert over.excluded is True and any(a.startswith("the equation of state's band") for a in over.assumptions)
    under = verdicts.relic(candidate("V1", 500.0, 1000.0), record)
    assert under.excluded is False and "underabundant" in under.note


def _densities(monkeypatch, nominal, upper, lower):
    """Ωh² with the nominal degrees of freedom and with each of Saikawa & Shirai's tables, as given; the tables
    present."""
    from adroit.constraints import annihilation, relic
    monkeypatch.setattr(relic, "band_unavailable", lambda: "")
    values = {"": nominal, "ss2020-upper": upper, "ss2020-lower": lower}
    monkeypatch.setattr(relic, "eos_variant", lambda name: relic.equation_of_state(relic.degrees_of_freedom,
                                                                                   label=f"ss2020-{name}"))
    monkeypatch.setattr(annihilation, "omega_h2", lambda *a: values[relic.current_eos()])


@pytest.mark.parametrize("nominal, upper, lower, excluded", [
    (0.12, 0.114, 0.126, None),           # 0.126 is above the ceiling, 0.12 not: EOS-sensitive
    (0.12, 0.118, 0.121, False), (0.2, 0.19, 0.21, True), (0.05, 0.048, 0.052, False)])
@pytest.mark.eos_band
def test_the_relic_comparison_is_decided_only_alike_across_the_band(monkeypatch, nominal, upper, lower, excluded):
    """The consistency audit's CA-02 (2026-10-24): the complementary relic comparison (DM7) decided on the nominal
    degrees of freedom alone; it is now made with Saikawa & Shirai's tables too, and stands only alike at all
    three, as a crossing on the plane does."""
    _densities(monkeypatch, nominal, upper, lower)
    found: dict = {}
    v = verdicts.verdict(candidate("V1", 5000.0, 100.0), database.record("planck-2018-omega"), certificates=found)
    assert v.excluded is excluded
    if excluded is None:
        assert v.applicability is Applicability.needs_calculation
        assert v.needed_calculation.startswith("EOS-sensitive") and "0.126 with the lower table" in v.needed_calculation
    else:
        assert any(a.startswith("the equation of state's band: Ωh² = ") for a in v.assumptions)
    # M1: the comparison's certificate, kept beside the verdict by record id
    certificate = found["planck-2018-omega"]
    assert certificate.claim_kind == "relic_comparison"
    assert certificate.check("eos_band").state == ("failed" if excluded is None else "satisfied")
    assert certificate.decided is (excluded is not None)


@pytest.mark.eos_band
def test_without_the_tables_the_relic_comparison_waits(monkeypatch):
    """CA-02: Ωh² = 0.12 allowed and 0.13 excluded with the tables missing; both now wait, naming the setup."""
    from adroit.constraints import annihilation, relic
    monkeypatch.setattr(relic, "eos_folder", lambda: None)
    for omega in (0.12, 0.13):
        monkeypatch.setattr(annihilation, "omega_h2", lambda *a, omega=omega: omega)
        v = verdicts.relic(candidate("V1", 5000.0, 100.0), database.record("planck-2018-omega"))
        assert v.excluded is None and "adroit setup --fetch" in v.needed_calculation and f"{omega:.3g}" in v.note


@pytest.mark.parametrize("omega", [math.nan, math.inf, -0.1, None])
def test_a_relic_density_that_is_not_a_number_decides_nothing(monkeypatch, omega):
    """The consistency audit's CA-03 (2026-10-24): Ωh² = nan read as allowed (nan > ceiling is False)."""
    _densities(monkeypatch, omega, 0.12, 0.12)
    v = verdicts.relic(candidate("V1", 5000.0, 100.0), database.record("planck-2018-omega"))
    assert v.excluded is None and "did not compute" in v.needed_calculation


@pytest.mark.needs("eos")
def test_the_summary_line() -> None:
    record = database.record("planck-2018-omega")
    v = verdicts.relic(candidate("V1", 5000.0, 100.0), record)
    assert verdicts.summary([v]) == "excluded by planck-2018-omega"
    assert verdicts.summary([]) == "no usable record"
