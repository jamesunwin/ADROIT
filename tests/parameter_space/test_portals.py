"""The portal library: its engine (Higgs width, coannihilation, exchange, amplitudes, kinetic mixing) and models."""

import math

import numpy as np
import pytest

from adroit.constraints import amplitudes, annihilation, exchange, higgs, kinetic_mixing as km, processes, relic, spin1
from adroit.parameter_space import library
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.higgs import HiggsPortalFermion, HiggsPortalScalar, HiggsPortalVector, SingletMixing
from adroit.parameter_space.portals.tchannel import TChannel
from adroit.parameter_space.portals.vector import ChargedZPrime, DarkPhoton, InelasticDarkPhoton, ZPortal
from adroit.parameter_space.scan import Axis, ScanRequest, _point_at, evaluate
from adroit.parameter_space.verdict import judge_point


def test_the_higgs_width_is_the_working_groups_at_its_mass():
    widths = higgs.partial_widths(higgs.M_H)
    assert sum(widths.values()) == pytest.approx(higgs.YR4_WIDTH_GEV, rel=1e-3)
    assert widths["b"] / sum(widths.values()) == pytest.approx(higgs.YR4_BR["b"], rel=1e-3)
    assert higgs.width(300.0) == pytest.approx(8.7, rel=0.05)          # the heavy SM-like Higgs (YR3: 8.43)


def test_the_coannihilation_solver_is_the_single_species_one_for_dirac_dark_matter():
    model = spin1.benchmark("V1", 1000.0)
    old = annihilation.omega_h2(model, 300.0)
    new = relic.omega_h2_single(lambda s: annihilation.total(s, model, 300.0), 300.0, 0.5, False,
                                [(1000.0, spin1.width(model, 300.0))])
    assert new == pytest.approx(old, rel=1e-3)


def test_interfering_vector_exchange_is_the_explicit_amplitude():
    x, w = np.polynomial.legendre.leggauss(24)
    meds, chi, f = [(91.19, 2.5), (60.0, 0.3)], [(0.02, 0.05), (0.7, 0.2)], [(-0.1, 0.18), (0.03, 0.01)]
    s, m, mf = 120.0 ** 2, 40.0, 4.7
    sq = amplitudes.s_channel_squared_many(s, m, mf, meds, chi, f, x)
    numeric = amplitudes.cross_section(sq, w, s, math.sqrt(s / 4 - m * m), math.sqrt(s / 4 - mf * mf), False) * 3
    analytic = exchange.vector_to_fermions(np.array([s]), m, "fermion", chi, mf, 3, f,
                                           [exchange.Mediator(*md) for md in meds])[0]
    assert analytic == pytest.approx(numeric, rel=1e-10)


def test_gauge_amplitudes_satisfy_the_ward_identity():
    xs = np.array([-0.6, 0.2, 0.8])
    p1, p2, k1, k2, _, _ = processes.frame(900.0 ** 2, 400.0, 400.0, 0, 0, xs)
    a1, a2 = processes.gauge_pair_amplitudes(p1, p2, k1, k2, k1, processes._transverse(k2)[0], 400.0)
    assert np.abs(a1).max() < 1e-9 and np.abs(a2).max() < 1e-9


@pytest.mark.parametrize("coloured, expected", [(False, lambda a, m: 2 * math.pi * a * a / m ** 2),
                                                (True, lambda a, m: 14 * math.pi * a * a / (27 * m * m))])
def test_partner_annihilation_into_gauge_bosons_at_threshold(coloured, expected):
    m, g = 500.0, 0.3
    s = 4 * m * m / (1 - 0.5e-3 ** 2)
    sv = processes.partners_to_gauge_bosons(s, m, g, coloured) * 1e-3
    assert sv == pytest.approx(expected(g * g / (4 * math.pi), m), rel=1e-4)


def test_t_channel_majorana_is_p_wave_and_dirac_s_wave():
    m, M, y = 500.0, 600.0, 1.0
    s = 4 * m * m / (1 - 0.5e-2 ** 2)
    dirac = processes.t_channel_to_fermions(s, m, 0.0, M, y, False) * 1e-2
    majorana = processes.t_channel_to_fermions(s, m, 0.0, M, y, True) * 1e-2
    assert dirac == pytest.approx(y ** 4 * m * m / (32 * math.pi * (m * m + M * M) ** 2), rel=1e-3)
    assert majorana == pytest.approx(y ** 4 * 1e-4 * m * m * (m ** 4 + M ** 4) / (48 * math.pi * (m * m + M * M) ** 4),
                                     rel=1e-3)


def test_kinetic_mixing_gives_a_massless_photon_and_an_epsilon_e_q_dark_photon():
    masses, r = km.eigenstates(1.0, 1e-3)
    assert masses[0] == pytest.approx(0.0, abs=1e-6) and masses[1] == pytest.approx(km.M_Z, rel=1e-4)
    photon = km.fermion_couplings("e", r[:, 0])
    assert abs(photon[0]) == pytest.approx(km.E, rel=1e-9) and abs(photon[1]) < 1e-12 and abs(r[2, 0]) < 1e-12
    dark = km.couplings(1.0, 1e-3, 1.0)["A'"]["fermions"]["e"]
    assert abs(dark[0]) == pytest.approx(1e-3 * km.E_THOMSON, rel=1e-3)        # DarkCast's ε: ε e(0) Q (D29)
    assert km.E_THOMSON == pytest.approx(0.302822, abs=1e-6)                   # DarkCast's ge


XENON, SUN = pytest.mark.needs("diamx", "solar_model"), pytest.mark.needs("solar_model")   # what each point uses
GERMANIUM = pytest.mark.needs("diamx", "cdmslite", "solar_model")


@pytest.mark.parametrize("cls, point", [
    pytest.param(HiggsPortalScalar(), Point(m_chi=1000.0, m_med=125.09, g_chi=0.3), marks=XENON),
    pytest.param(HiggsPortalFermion(xi=math.pi / 2), Point(m_chi=200.0, m_med=125.09, g_chi=1e-3), marks=SUN),
    pytest.param(HiggsPortalVector(), Point(m_chi=500.0, m_med=125.09, g_chi=0.3), marks=XENON),
    pytest.param(SingletMixing(), Point(m_chi=200.0, m_med=500.0, g_chi=0.5, g_q=0.2), marks=XENON),
    pytest.param(DarkPhoton(), Point(m_chi=10.0, m_med=30.0, g_chi=2.5, g_q=1e-3), marks=GERMANIUM),
    pytest.param(DarkPhoton(scalar_dm=True), Point(m_chi=10.0, m_med=30.0, g_chi=2.5, g_q=1e-3), marks=GERMANIUM),
    pytest.param(InelasticDarkPhoton(), Point(m_chi=5.0, m_med=15.0, g_chi=1.1, g_q=1e-3, g_l=0.1),
                 marks=pytest.mark.needs("pdg_r_ratio")),
    pytest.param(ZPortal(coupling="axial"), Point(m_chi=300.0, m_med=91.19, g_chi=0.1), marks=XENON),
    pytest.param(ChargedZPrime(), Point(m_chi=1000.0, m_med=2000.0, g_chi=0.033, g_q=0.1), marks=XENON),
    pytest.param(ChargedZPrime(charges="Lmu-Ltau"), Point(m_chi=0.5, m_med=1.5, g_chi=1e-3, g_q=1e-3),
                 marks=pytest.mark.needs("solar_model", "pdg_r_ratio")),
])
def test_every_portal_gives_a_relic_density_and_a_scan_point(cls, point):
    omega = cls.omega_h2(point)
    assert omega is not None and 0 < omega < 1e8
    r = evaluate(cls, point)
    assert set(r.excluded) >= {"direct detection", "gamma rays (Fermi-LAT dwarfs)", "perturbativity"}


def test_the_scalar_singlet_matches_the_known_relic_line_at_one_tev():
    assert HiggsPortalScalar().omega_h2(Point(m_chi=1000.0, m_med=125.09, g_chi=0.3)) == pytest.approx(0.12, rel=0.15)


def test_invisible_widths_are_the_literatures_formulas():
    p = Point(m_chi=30.0, m_med=125.09, g_chi=0.01)
    beta = math.sqrt(1 - 4 * 30.0 ** 2 / higgs.M_H ** 2)
    expected = 0.01 ** 2 * higgs.V_HIGGS ** 2 * beta / (32 * math.pi * higgs.M_H)
    assert HiggsPortalScalar().invisible(p)["h"] == pytest.approx(expected)
    z = ZPortal(coupling="axial", majorana=True).invisible(Point(m_chi=30.0, m_med=91.19, g_chi=0.1))["Z"]
    b = math.sqrt(1 - 4 * 30.0 ** 2 / km.M_Z ** 2)
    assert z == pytest.approx(0.5 * km.M_Z / (12 * math.pi) * b * 0.1 ** 2 * b * b)     # Escudero et al. eq. 2.2


@pytest.mark.needs("diamx", "solar_model")
def test_the_invisible_higgs_width_excludes_a_large_portal_coupling(monkeypatch):
    p = Point(m_chi=30.0, m_med=125.09, g_chi=0.02)                       # BR(h → SS) ≈ 0.29
    r = evaluate(HiggsPortalScalar(), p)
    assert r.excluded["invisible Higgs width (ATLAS)"] is True and r.values["BR(h → invisible)"] > 0.107
    assert evaluate(HiggsPortalScalar(), p.model_copy(update={"g_chi": 0.005})).excluded[
        "invisible Higgs width (ATLAS)"] is False
    from adroit.constraints import database
    record, read = database.record("atlas-2301.10731-hinv"), database.record
    monkeypatch.setattr(database, "record", lambda rid: record.model_copy(update={"verified_on": None})
                        if rid == record.id else read(rid))      # that record alone (every other read as it is)
    assert any("awaits a person's verification" in x for x in judge_point(HiggsPortalScalar(), p).pending)


def test_a_compressed_coloured_partner_is_flagged_only_without_the_long_range_effects():
    t = TChannel()
    far, near = Point(m_chi=500.0, m_med=1500.0, g_chi=0.5), Point(m_chi=500.0, m_med=520.0, g_chi=0.5)
    assert not any("unreliable" in f for f in [*t.flags(near),*t.flags(far)])
    assert all(any("chemical equilibrium" in f for f in t.flags(p)) for p in (near,far))
    assert any("Sommerfeld" in f for f in TChannel(sommerfeld=False, bound_states=False).flags(near))
    assert t.omega_h2(near) < t.omega_h2(far)


def test_the_sommerfeld_effect_and_bound_states_raise_the_thermal_mass_of_a_coloured_partner():
    def omega(se: bool, bsf: bool) -> float:
        return TChannel(sommerfeld=se, bound_states=bsf).omega_h2(Point(m_chi=2000.0, m_med=2002.0, g_chi=0.01))
    none, se, both = omega(False, False), omega(True, False), omega(True, True)
    assert both < se < none
    assert 0.1 < both / none < 0.3                  # the thermal mass rises by ×2.3 (module docstring)


def test_a_mediator_ratio_ties_the_mediator_to_the_dark_matter():
    request = ScanRequest(model_class=DarkPhoton(), fixed=Point(m_chi=10.0, m_med=1.0, g_chi=2.5, g_q=1e-3),
                          x=Axis(parameter="m_chi", low=1, high=10, n=2), y=Axis(parameter="g_q", low=1e-5, high=1e-3, n=2),
                          mediator_ratio=3.0)
    assert _point_at(request, 7.0, 1e-4).m_med == pytest.approx(21.0)


def test_the_library_lists_its_portals_and_three_dm13_models():
    families = [e.family for e in library.ENTRIES]
    assert len(library.ENTRIES) == 27 and families.count("s-channel mediator") == 3
    assert families.count("electroweak multiplet") == 4      # the wino, the higgsino and two 5-plets (2026-10-13) and families.count("extended scalar sector") == 2
    assert all(e.references and all(" — " in r for r in e.references) for e in library.ENTRIES)
    assert "higgs_portal_scalar" in library.listing()
    with pytest.raises(KeyError):
        library.entry("nonsense")


def test_charges_written_to_a_few_decimals_are_read_as_fractions():
    from adroit.model_building.content import snap
    assert snap(0.6666667) == pytest.approx(2 / 3, abs=1e-15) and snap(-0.3333333) == pytest.approx(-1 / 3, abs=1e-15)
    assert snap(0.123456) == 0.123456


def test_dm12_generation_multiplet_is_not_silently_an_up_only_portal():
    from adroit.core.model_spec import ModelSpec
    from adroit.orchestrator.ideas import from_fields
    from adroit.parameter_space.classify import Unsupported, classify
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1},
              {"name": "phi", "role": "mediator", "spin": 0, "dark_parity": -1,
               "charges": {"su3": "3", "hypercharge": 0.6666667}}]
    general = from_fields(ModelSpec.model_validate({"name": "t", "phase": "unbroken", "fields": fields})).general
    with pytest.raises(Unsupported, match="flavour|generation"):
        classify(general)


def test_track1_runs_a_portal_from_the_command_line(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from adroit.orchestrator import cli, runs
    seen = {}
    monkeypatch.setattr(runs, "track1", lambda request, *a, **k: seen.setdefault("r", request) and (tmp_path, "ok"))
    out = CliRunner().invoke(cli.app, ["track1", "--portal", "dark_photon_dirac", "--no-literature"])
    assert out.exit_code == 0, out.output
    assert seen["r"].portal == "dark_photon_dirac" and seen["r"].mediator_ratio == 3.0
    assert CliRunner().invoke(cli.app, ["track1", "--portal", "nonsense"]).exit_code != 0


@pytest.mark.needs("diamx", "solar_model")
def test_points_at_the_higgs_resonance_are_flagged_unreliable():
    near, far = Point(m_chi=62.0, m_med=125.09, g_chi=1e-3), Point(m_chi=70.0, m_med=125.09, g_chi=1e-3)
    for cls in (HiggsPortalScalar(), HiggsPortalFermion(), HiggsPortalVector()):
        assert cls.flags(near) and not cls.flags(far)
    assert any("Higgs resonance" in f for f in evaluate(HiggsPortalScalar(), near).flags)
