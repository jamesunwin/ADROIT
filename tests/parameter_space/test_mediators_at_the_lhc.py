"""s-channel mediators at the LHC: production tables, their spectra for SModelS, the Higgs signal strength."""

import json

import pytest

from adroit.constraints import production
from adroit.parameter_space import searches as ps
from adroit.parameter_space.classes import Point, ScalarClass, Spin1Class
from adroit.parameter_space.portals.higgs import SingletMixing


@pytest.fixture
def tables(tmp_path, monkeypatch):
    folder = tmp_path / "madgraph-xsec"
    folder.mkdir()
    masses = (50.0, 100.0, 500.0, 1000.0, 3000.0)
    for name, scale in (("zprime_spin1_vector_13TeV_LO", 1.0), ("zprime_spin1_axial_13TeV_LO", 0.9),
                        ("zprime_spin1_BminusL_13TeV_LO", 1.0 / 9.0), ("ggS_spin0_S_tb_13TeV_LO", 0.1),
                        ("ggS_spin0_P_tb_13TeV_LO", 0.2), ("ggS_spin0_S_t_13TeV_LO", 0.09),
                        ("ggS_spin0_S_b_13TeV_LO", 0.002), ("ggS_spin0_P_t_13TeV_LO", 0.18),
                        ("ggS_spin0_P_b_13TeV_LO", 0.003)):
        rows = [[m, scale * 1e3 * (100.0 / m) ** 4, 0.0, 1.0] for m in masses]
        (folder / f"{name}.json").write_text(json.dumps({"columns": ["mass_gev", "sigma_pb", "sigma_err_pb", "seconds"],
                                                         "data": rows}))
    k_rows = [[m, 2.5, 0.5 * 1e3 * (100.0 / m) ** 4] for m in masses]
    (folder / "ggS_kfactors_13TeV.json").write_text(json.dumps(
        {"columns": ["mass_gev", "K_loop", "sigma_HXSWG_quarkloop_NNLO_NNLL_pb"], "data": k_rows}))
    for pair, scale in (("H0A0", 10.0), ("HpmH0", 6.0), ("HpmA0", 4.0), ("HpHm", 3.0)):
        idm = [[m, m, m, scale * (100.0 / m) ** 4, 0.0, 1.0] for m in masses]
        (folder / f"idm_{pair}_equal_masses_13TeV_LO.json").write_text(json.dumps(
            {"columns": ["mH0_gev", "mA0_gev", "mHpm_gev", "sigma_pb", "sigma_err_pb", "seconds"], "data": idm}))
    monkeypatch.setattr(production, "folder", lambda: folder)
    production._read.cache_clear()
    yield folder
    production._read.cache_clear()


def test_a_table_is_interpolated_in_log_log_and_refuses_outside(tables):
    name = "zprime_spin1_vector_13TeV_LO"
    assert production.sigma_pb(name, 100.0) == pytest.approx(1e3)
    assert production.sigma_pb(name, 200.0) == pytest.approx(1e3 / 16.0)
    assert production.sigma_pb(name, 5000.0) is None
    assert production.sigma_pb("nothing", 100.0) is None
    assert production.gluon_fusion_k(300.0) == pytest.approx(2.5)
    assert production.heavy_higgs_pb(100.0) == pytest.approx(500.0)


def test_mediator_spectra_scale_with_the_couplings_and_carry_their_decays(tables):
    v1 = Spin1Class(name="V")
    text, sigma = ps.mediator_spectrum(v1, Point(m_chi=100.0, m_med=1000.0, g_chi=1.0, g_q=0.25, g_l=0.0))
    assert sigma == pytest.approx(0.25 ** 2 * 1e3 * 1e-4)
    assert "XSECTION  1.30E+04  2212 2212  1  55" in text and "57   -57" in text
    s_text, s_sigma = ps.mediator_spectrum(ScalarClass(), Point(m_chi=100.0, m_med=500.0, g_chi=1.0, g_q=1.0))
    g_t = 172.0 / 172.5          # the DMsimp card's top Yukawa in the tables' units (the owner's decision #2); b 4.7
    lo = (g_t ** 2 * 0.09 + 0.002 + g_t * (0.1 - 0.09 - 0.002)) * 1e3 * (100 / 500) ** 4      # t, b and their interference
    assert s_sigma == pytest.approx(2.5 * lo) and "54" in s_text     # LO × K
    h_text, h_sigma = ps.mediator_spectrum(SingletMixing(), Point(m_chi=100.0, m_med=500.0, g_chi=1.0, g_q=0.2))
    assert h_sigma == pytest.approx(0.04 * 0.5 * 1e3 * (100 / 500) ** 4) and "  24  -24" in h_text.replace("   ", "  ")


def test_a_missing_k_factor_leaves_gluon_fusion_undecided(tables, monkeypatch):
    """The subagent's D2 (2026-10-20): without the K-factor at the mass, gg → S had been the LO σ (K taken as 1, about
    2.5 times low, which could allow a point); it is now not computed, and the LHC search undecided."""
    monkeypatch.setattr(production, "gluon_fusion_k", lambda mass: None)
    assert ps.gluon_fusion_pb("S", 1.0, 1.0, 500.0) is None
    text, sigma = ps.mediator_spectrum(ScalarClass(), Point(m_chi=100.0, m_med=500.0, g_chi=1.0, g_q=1.0))
    assert sigma is None and text == ""


def test_b_minus_l_uses_its_own_table(tables):
    from adroit.parameter_space.portals.vector import ChargedZPrime
    text, sigma = ps.mediator_spectrum(ChargedZPrime(name="B − L"), Point(m_chi=100.0, m_med=1000.0, g_chi=0.1, g_q=0.3))
    assert sigma == pytest.approx(0.09 * 1e3 * 1e-4 / 9.0)
    assert "  11   -11" in text.replace("   ", "  ") or "11   -11" in text


def test_the_inert_doublet_pairs_decay_through_off_shell_bosons(tables, monkeypatch):
    from types import SimpleNamespace

    from adroit.parameter_space.library import INERT_DOUBLET
    particles = {"~H0": SimpleNamespace(mass=70.0, width=0.0), "~A0": SimpleNamespace(mass=130.0, width=0.0),
                 "~H+": SimpleNamespace(mass=130.0, width=0.0)}
    monkeypatch.setattr(type(INERT_DOUBLET), "model", lambda self, p: SimpleNamespace(particles=particles))
    text, sigma = ps.mediator_spectrum(INERT_DOUBLET, Point(m_chi=70.0, m_med=130.0, g_chi=0.01, g_q=60.0))
    mean = lambda a, b: (100.0 / (0.5 * (a + b))) ** 4 * 2 * (a * b) ** 0.5 / (a + b)     # noqa: E731
    assert sigma == pytest.approx(10.0 * mean(70, 130) + 6.0 * mean(130, 70) + 4.0 * mean(130, 130)
                                  + 3.0 * mean(130, 130))
    assert "2  9000103 -9000103" in text                                        # H⁺H⁻
    assert "9000101   11   -11" in text and "9000101   23" not in text          # A₀ → H₀ Z* → H₀ e⁺e⁻
    assert "9000101   -11   12" in text and "2  -9000103 9000101" in text          # H± → H₀ W*, both charges
    particles["~A0"] = SimpleNamespace(mass=300.0, width=1.0)
    text, _ = ps.mediator_spectrum(INERT_DOUBLET, Point(m_chi=70.0, m_med=130.0, g_chi=0.01, g_q=230.0))
    assert "9000101   23" in text


def test_the_higgs_signal_strength_bounds_the_mixing():
    sm = SingletMixing()
    assert ps.higgs_signal(sm, Point(m_chi=200.0, m_med=500.0, g_chi=0.5, g_q=0.1), True).excluded is False
    out = ps.higgs_signal(sm, Point(m_chi=200.0, m_med=500.0, g_chi=0.5, g_q=0.3), True)
    assert out.excluded is True and out.value == pytest.approx(0.91, abs=0.01) and out.delta_chi2 > 0
    assert ps.higgs_signal(ScalarClass(), Point(m_chi=200.0, m_med=500.0), True) is None


def test_the_singlets_heavy_scalar_meets_the_zz_and_ww_searches(tables, awaiting):
    from adroit.constraints import searches as s
    sm, p = SingletMixing(), Point(m_chi=200.0, m_med=300.0, g_chi=0.0, g_q=0.05)     # narrow: Γ/m below 0.5%
    sigma, _, _, widths = ps._scalar(sm, p)
    total = sum(widths.values())
    assert 100.0 * total / 300.0 < 0.5
    zz = sigma * widths[(23, 23)] / total / s.interpolate(s._bundled("atlas-2009.14791-zz")["limit"], 300.0)
    ww = sigma * widths[(24, -24)] / total / s.interpolate(s._bundled("atlas-2004.14636-ww")["limit"], 300.0)
    out = ps.heavy_scalar(sm, p, True)
    assert out.ratio == pytest.approx(max(zz, ww)) and out.excluded == (max(zz, ww) > 1.0)
    assert ps.heavy_scalar(ScalarClass(), p, True) is None
    awaiting("atlas-2009.14791-zz", "atlas-2004.14636-ww")
    assert ps.heavy_scalar(sm, p, False).excluded is None                      # records awaiting verification


def test_a_broader_heavy_scalar_is_pending_where_atlas_zz_does_not_apply(tables):
    """Γ/m above 0.5%: not ATLAS's narrow ZZ limit (§9.1.1), and not its large-width limits, whose interference
    modelling the singlet does not match; undecided unless WW alone excludes."""
    sm, p = SingletMixing(), Point(m_chi=100.0, m_med=300.0, g_chi=1.0, g_q=0.3)
    width = 100.0 * sum(ps._scalar(sm, p)[3].values()) / 300.0
    assert width > 0.5
    out = ps.heavy_scalar(sm, p, True)
    assert "0.5%" in out.why and (out.excluded is True or out.excluded is None)
    assert "cot²θ" in ps._lwa_mismatch(sm, p)


def test_the_monojet_recast_scales_with_the_coupling_and_the_invisible_fraction():
    scalar = ScalarClass()
    out = ps.monojet_spin0(scalar, Point(m_chi=10.0, m_med=100.0, g_chi=1.0, g_q=1.0), True)
    assert out.value == pytest.approx(1.0, abs=1e-3) and out.ratio == pytest.approx(1.0 / 1.5364, rel=1e-3)
    half = ps.monojet_spin0(scalar, Point(m_chi=10.0, m_med=100.0, g_chi=1.0, g_q=0.5), True)
    assert half.value == pytest.approx(0.25, rel=0.01)
    alp = ps.monojet_spin0(ScalarClass(dm_pseudoscalar=True, sm_pseudoscalar=True),
                           Point(m_chi=10.0, m_med=100.0, g_chi=1.0, g_q=1.0), True)
    assert alp.excluded is True                                    # the pseudoscalar table: μ₉₅ < 1 at 100 GeV
    assert ps.monojet_spin0(scalar, Point(m_chi=60.0, m_med=100.0, g_chi=1.0, g_q=1.0), True).excluded is None


@pytest.mark.slow
def test_smodels_excludes_a_z_prime_from_madgraphs_cross_section_as_cms_does():
    from adroit.constraints import lhc
    if not (lhc.available() and production.available("zprime_spin1_vector_13TeV_LO")):
        pytest.skip("SModelS or MadGraph's tables are not in the tools folder")
    v1 = Spin1Class(name="V1")
    near = ps.lhc_search(v1, Point(m_chi=1000.0, m_med=2000.0, g_chi=1.0, g_q=0.25, g_l=0.0), True)
    far = ps.lhc_search(v1, Point(m_chi=1000.0, m_med=4000.0, g_chi=1.0, g_q=0.25, g_l=0.0), True)
    assert near.excluded is True and 1.5 < near.ratio < 3.0
    # The 4 TeV covered contribution does not exclude, but MET and ttbar
    # contributions lie outside the database grids. M09 must preserve pending.
    assert far.excluded is None and far.ratio is None
    assert 'coverage remains' in far.why
    assert any(entry['total_xsec_fb'] > 0 for entry in far.coverage.values())


def test_gluon_fusion_combines_the_top_and_bottom_loops_with_their_interference(tables):
    shape = 1e3 * (100.0 / 500.0) ** 4
    assert ps.gluon_fusion_pb("S", 1.0, 1.0, 500.0) == pytest.approx(2.5 * 0.1 * shape)
    assert ps.gluon_fusion_pb("S", -1.0, 1.0, 500.0) == pytest.approx(2.5 * (2 * 0.09 + 2 * 0.002 - 0.1) * shape)
    assert ps.gluon_fusion_pb("P", 0.35, 0.0, 500.0) == pytest.approx(2.5 * 0.35 ** 2 * 0.18 * shape)


def test_the_same_data_enter_the_combined_likelihood_once():
    from adroit.constraints.searches import Outcome
    from adroit.parameter_space.scan import _same_data
    lhc = Outcome(name=ps.LHC, excluded=False, ratio=0.5, why="CMS-EXO-20-004")
    ratios = {ps.LHC: 0.5, ps.MONOJET: 0.6}
    _same_data([lhc], ratios)
    assert ratios == {ps.MONOJET: 0.6}
    other = {ps.LHC: 0.5, ps.MONOJET: 0.6}
    _same_data([lhc.model_copy(update={"why": "ATLAS-EXOT-2018-06"})], other)
    assert ps.LHC in other


@pytest.mark.slow
def test_the_2hdma_spectrum_carries_its_cascades():
    from adroit.parameter_space.library import TWO_HDM_A
    if not production.available("ggS_spin0_P_tb_13TeV_LO"):
        pytest.skip("MadGraph's tables are not in the tools folder")
    text, sigma = ps.mediator_spectrum(TWO_HDM_A, Point(m_chi=10.0, m_med=250.0, g_chi=1.0, g_q=0.35, g_l=1.0))
    assert "XSECTION  1.30E+04  2212 2212  1  55" in text and "2   25   55" in text and "2   23   55" in text
    assert 3.0 < sigma < 6.0                       # a dominates: sin²θ × σ_P(250 GeV) × K
