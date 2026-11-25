"""The audit loop's cycle 4 (``audit/claude_audit_2026-11-16_cycle4.md``): its severe and high findings, AL4-01 to
AL4-08, each at the place the auditor's control reached it (the AL4 repair record of 2026-11-16). Offline; fake keys."""
from __future__ import annotations

from types import SimpleNamespace as NS

import numpy as np
import pytest

from adroit.core.model_spec import ModelSpec
from tests.orchestrator.test_al3_addenda import FAKE_A, project  # noqa: F401 - the keys' fixture

U = dict(name="u", role="standard_model", spin=0.5, charges=dict(su3="3", electric_charge=2 / 3))


# --- AL4-01: the light-mediator rule at every halo sample ---------------------------------------------------------

def test_a_halo_sample_through_a_light_mediator_is_undecided_and_combines_no_ratio(monkeypatch) -> None:
    """A sample's contact comparison that excludes is undecided with the light mediator's reason, and no ratio enters
    a combination; an allowed one stands (the rule of the point's centre, ``scan.light_mediator_rule``)."""
    from adroit.parameter_space import dd_channels, halo_evaluation, halo_limits, scan
    state = halo_limits.State(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=0.4)
    for excluded, expected in ((True, None), (False, False)):
        found = NS(excluded=excluded, decisive=None, combined_channel=None,      # as dd_channels.Outcome (AL5-02)
                   combinable=300.0 if excluded else 0.1, pending=[])
        monkeypatch.setattr(dd_channels, "compare", lambda channels, m, found=found: found)
        outcome, reasons = halo_evaluation._dd(["a channel"], 100.0, state, light=True)
        assert outcome.excluded is expected and outcome.ratio is None
        assert (scan.LIGHT_MEDIATOR in reasons) is bool(excluded) and (scan.LIGHT_MEDIATOR in outcome.why) is bool(excluded)
        heavy, _ = halo_evaluation._dd(["a channel"], 100.0, state)
        assert heavy.excluded is excluded and heavy.ratio == found.combinable          # a heavy mediator: as before


def test_every_halo_sample_is_told_whether_the_mediator_is_light(monkeypatch) -> None:
    from adroit.parameter_space import halo_evaluation, halo_limits, scan
    from adroit.parameter_space.classes import Point, Spin1Class
    seen = []
    monkeypatch.setattr(halo_evaluation, "_dd", lambda channels, m, state, light=False: seen.append(light) or (None, []))
    budget = halo_limits.Budget(remaining=0)
    for m_med, light in ((0.005, True), (5.0, False)):
        halo_evaluation.at(Spin1Class(), Point(m_chi=100.0, m_med=m_med, g_chi=1e-6, g_q=1e-6),
                           (233.0, 528.0, 0.4, "centre"), ["a channel"], False, False, budget)
        assert seen[-1] is light and scan._light_mediator(Spin1Class(), Point(m_chi=100.0, m_med=m_med)) is light


# --- AL4-02: a UFO pole at the pair's threshold --------------------------------------------------------------------

@pytest.mark.parametrize("width", [0.2, 6.6e-3, 1.2e-3])
@pytest.mark.parametrize("mass", [200.0, 199.999, 200.0005])
def test_a_pole_at_or_just_below_threshold_is_resolved(width, mass) -> None:
    """The auditor's reconstruction: a Breit–Wigner with σ ∝ 1/β, its pole at, just below or just above 2m_χ = 200 GeV,
    thermally averaged at x = 20 from the table's nodes against exactly: within 1.5% (the old nodes gave up to 5.98)."""
    from adroit.constraints import relic
    from adroit.parameter_space.portals import ufo
    m = 100.0

    def f(s):
        return 1 / np.sqrt(1 - 4 * m * m / s) / ((s - mass * mass) ** 2 + (mass * width) ** 2)
    roots = ufo.table_roots(2 * m, [(mass, width)])
    u = np.union1d(relic.energy_grid(m, mass, width)[1:], np.geomspace(1.0000001e-9, 1.0, 40000))
    u = u[u > 1e-9]
    x = np.array([20.0])
    tabled = relic.thermal_average(u, np.exp(np.interp(2 * m * (1 + u), roots, np.log(f(roots ** 2)))), x)[0]
    exact = relic.thermal_average(u, f((2 * m * (1 + u)) ** 2), x)[0]
    assert tabled / exact == pytest.approx(1.0, abs=0.015)


def test_a_pole_far_from_threshold_adds_no_threshold_ladder() -> None:
    from adroit.parameter_space.portals import ufo
    plain = ufo.table_roots(200.0, [])
    assert len(ufo.table_roots(200.0, [(150.0, 1e-3)])) == len(plain)                # far below: not reached
    above = ufo.table_roots(200.0, [(260.0, 1e-3)]) / 200.0 - 1
    assert not ((above > 2 * ufo.U_FIRST) & (above < 0.99 * ufo.U_BASE)).any()                 # far above: its own nodes only


# --- AL4-03: the anapole of every lepton vertex --------------------------------------------------------------------

def test_a_majorana_lepton_portals_anapole_sums_every_lepton_vertex() -> None:
    from adroit.constraints import loops
    from adroit.parameter_space.portals import generic_dd
    mb = NS(spectrum=NS(dark_matter=lambda: NS(kind="majorana", name="chi0", mass_gev=300.0)))
    phi = NS(name="phi+", anti="phi+~", parity=-1, spin=0, colour="1", mass=400.0)
    vertices = [NS(kind="FFS", legs=("chi0", lepton, "phi+~"), c=1.0, c2=0.0) for lepton in ("e", "mu", "tau")]
    found = generic_dd._lepton_partner(mb, NS(particles=[phi], vertices=vertices))
    each = [loops.anapole_moment(300.0, 400.0, 1.0, generic_dd.LEPTONS[x]) for x in ("e", "mu", "tau")]
    assert found.structure == "anapole" and found.scale == pytest.approx(sum(each), rel=1e-12)
    assert found.scale / each[0] == pytest.approx(1.90, abs=0.01)          # the electron's alone had been taken
    twice = generic_dd._lepton_partner(mb, NS(particles=[phi], vertices=vertices + vertices[:1]))
    assert twice.scale == pytest.approx(sum(each), rel=1e-12)            # a vertex and its conjugate: one loop


# --- AL4-04: a term the generic route has no rule for ---------------------------------------------------------------

def _contact_spec(lorentz: str = "scalar", dark: dict | None = None, coupling: float = 1e-3) -> ModelSpec:
    dark = dark or dict(name="S", role="dark_matter", spin=0, self_conjugate=True, mass_gev=100.0, dark_parity=-1)
    name = dark["name"]
    occ = ([dict(field=name), dict(field=name)] if dark["spin"] == 0 else
           [dict(field=name, conjugate=True), dict(field=name)])
    return ModelSpec.model_validate(dict(
        name="contact", phase="broken", stability="Z2", fields=[dark, U],
        couplings=[dict(name="c", value=coupling, mass_dimension=-1 if dark["spin"] == 0 else -2)],
        terms=[dict(fields=[*occ, dict(field="u", conjugate=True), dict(field="u")], lorentz=lorentz, coupling="c",
                    text=f"c {name} {name} ubar u")]))


def test_two_dark_bosons_with_a_quark_pair_are_refused_by_name_not_dropped() -> None:
    from adroit.model_building import feynman, gauge_basis, spectrum
    with pytest.raises(gauge_basis.GaugeBasisError, match=r"c S S ubar u: a term of a fermion pair with a Standard "
                                                          r"Model fermion and 2 bosons"):
        feynman.feynman_rules(spectrum.compute(_contact_spec()))


# --- AL4-05: a key the parent was told not to use -------------------------------------------------------------------

def test_a_run_started_from_the_workbench_keeps_its_parents_empty_key(project, monkeypatch) -> None:  # noqa: F811
    """A key in .env, the parent's variable exported empty: the run's environment carries the variable present and
    empty, so the child's settings hold no key (it had read the key from .env)."""
    from adroit.core import config
    project(f"ANTHROPIC_API_KEY={FAKE_A}\n")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert config.get_settings().anthropic_api_key.get_secret_value() == ""
    run = config.run_environment({"ADROIT_JOB_FOLDER": "f"})
    assert run["ANTHROPIC_API_KEY"] == "" and FAKE_A not in run.values()
    monkeypatch.setattr(config.os, "environ", {**run})                      # the child's view, its .env the same
    config.get_settings.cache_clear()
    assert config.get_settings().anthropic_api_key.get_secret_value() == ""


# --- AL4-06: Path 2's eligibility keeps the model's ties ------------------------------------------------------------

TIED = dict(name="one_coupling", stability="Z2", fields=[
    dict(name="chi", role="dark_matter", dark_parity=-1, spin=0.5, mass_gev=100.0),
    dict(name="Zp", role="mediator", dark_parity=1, spin=1.0, self_conjugate=True, mass_gev=2000.0),
    dict(name="q", role="standard_model", spin=0.5)], couplings=[dict(name="g", value=1.0)], terms=[
    dict(fields=[dict(field="chi", conjugate=True), dict(field="chi"), dict(field="Zp")], lorentz="vector", coupling="g"),
    dict(fields=[dict(field="q", conjugate=True), dict(field="q"), dict(field="Zp")], lorentz="vector", coupling="g")])


def test_the_eligibilitys_inversion_moves_every_tied_coupling() -> None:
    from adroit.orchestrator import physical_eligibility
    from adroit.parameter_space.classify import classify
    from adroit.parameter_space.fit_inversion import invert
    spec = ModelSpec.model_validate(TIED)
    ties = physical_eligibility._ties(spec)
    cls, reference, _ = classify(spec)
    point = invert(cls, reference.model_copy(update={"m_chi": 11.5}), 0.3283705831809782, ties)
    assert ties and point.g_chi == pytest.approx(point.g_q) and point.g_chi * point.g_q == pytest.approx(0.32837, rel=1e-4)
    assert physical_eligibility._ties(ModelSpec.model_validate({**TIED, "couplings": [dict(name="g", value=1.0),
                                                                                      dict(name="h", value=1.0)],
                                                                "terms": [TIED["terms"][0], {**TIED["terms"][1],
                                                                                             "coupling": "h"}]})) == ()


# --- AL4-07: a mixture's bound in the combined likelihood ------------------------------------------------------------

def test_an_allowed_mixture_combines_by_its_lower_bound() -> None:
    from adroit.constraints import mixtures
    from adroit.parameter_space import likelihood
    b = mixtures.bound("calore-2202.03076-pbar", {"b": 0.5, "Z": 0.3}, 100.0, lambda c: {"bb": 1.0, "WW": 1.0}.get(c))
    assert (b.lower, b.upper, b.excluded) == (pytest.approx(0.5), pytest.approx(0.875), False)
    assert b.ratio == pytest.approx(b.lower) and "0.875" in b.why()
    side = {"antiprotons (AMS-02)": "one-sided", "direct detection": "one-sided"}
    level = {"antiprotons (AMS-02)": .95, "direct detection": .95}
    q = likelihood.combined({"antiprotons (AMS-02)": b.ratio, "direct detection": 0.5}, {}, confidence_levels=level,
                            sidedness=side)
    assert q < likelihood.Q_95                                   # 2.748 with the upper bound: excluded


# --- AL4-08: a Majorana particle's vector or tensor contact ----------------------------------------------------------

@pytest.mark.parametrize("lorentz", ["VV", "VA", "TT"])
def test_a_majorana_vector_or_tensor_contact_is_refused_as_vanishing(lorentz) -> None:
    from adroit.model_building import audit
    chi = dict(name="chi", role="dark_matter", spin=0.5, self_conjugate=True, mass_gev=100.0, dark_parity=-1)
    found = audit.audit(_contact_spec(lorentz, chi, 1e-6))
    assert not found.valid and any(p.check == "identity" and "vanishes identically" in p.message for p in found.problems)
    dirac = audit.audit(_contact_spec(lorentz, {**chi, "self_conjugate": False}, 1e-6))
    assert not any(p.check == "identity" for p in dirac.problems)
    for kept in ("AV", "AA", "SS"):                              # the axial and scalar bilinears do not vanish
        assert not any(p.check == "identity" for p in audit.audit(_contact_spec(kept, chi, 1e-6)).problems)
