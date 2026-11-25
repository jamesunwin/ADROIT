"""Each DarkCast search with its own paper's confidence level and mass resolution (the owner's record review,
2026-10-13), in place of one 10% width cut and the record's CL for all of them. DarkCast's limits are replaced by
stubs, so these run without the tools folder."""

import math

import pytest

from adroit.constraints import searches as s
from adroit.parameter_space import searches as ps
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.vector import DarkPhoton

MINIMAL = Point(m_chi=5.0, m_med=0.1, g_chi=0.1, g_q=1e-3)          # A′ → χχ̄ closed: Γ ∝ ε², far below any resolution
NARROW_OPEN = Point(m_chi=1.0, m_med=5.0, g_chi=0.01, g_q=1e-3)     # A′ → χχ̄ open, Γ ≈ 10 keV
BROAD = Point(m_chi=1.0, m_med=5.0, g_chi=1.0, g_q=1e-3)            # Γ ≈ 0.12 GeV


def _only(monkeypatch, excluding: set[str], covering: set[str] | None = None) -> None:
    """DarkCast stubs: the searches in ``excluding`` exclude (ratio 2), the rest of ``covering`` (default: all) allow."""
    tool = s._tool
    monkeypatch.setattr(s, "_tool", lambda name: "DarkCast" if name == "DarkCast" else tool(name))
    monkeypatch.setattr(s, "darkcast_excludes",
                        lambda stem, m, c: True if stem in excluding else (None if covering and stem not in covering
                                                                          else False))
    monkeypatch.setattr(s, "darkcast_ratio", lambda stem, m, c: 2.0 if stem in excluding else 0.5)


def test_every_search_has_its_papers_cl_and_resolution_on_record() -> None:
    for stem in ps.VISIBLE_PROMPT + ps.VISIBLE_DISPLACED + ps.INVISIBLE:
        info = s.darkcast_info(stem)
        assert info["name"] and info["reference"] and info["cl"] in (0.90, 0.95, None)
        assert info["signal"] in ("bump hunt", "beam dump", "missing mass", "missing energy")
        assert info["cl_quote"] or info["cl"] is None
        if info["signal"] == "bump hunt":                                  # every one has a resolution (2026-10-13)
            assert ps._darkcast_resolution(info, 1.0) is not None and info["resolution_quote"]
    assert s.darkcast_info("A1_Merkel2014avp")["cl"] == 0.95 and s.darkcast_info("BaBar_Lees2014xha")["cl"] == 0.90
    assert s.darkcast_info("CHARM_Tsai2019mtm")["cl"] is None


def test_hps_2018_is_a_prompt_search() -> None:
    assert "HPS_Adrian2018scb" in ps.VISIBLE_PROMPT and "HPS_Adrian2018scb" not in ps.VISIBLE_DISPLACED


@pytest.mark.needs("pdg_r_ratio")
def test_a_95_percent_exclusion_stands_at_95_percent(monkeypatch) -> None:
    _only(monkeypatch, {"A1_Merkel2014avp"})
    out = ps.dark_photon(DarkPhoton(), MINIMAL, True)
    assert out.excluded is True and out.confidence_level == 0.95 and out.why.startswith("A1_Merkel2014avp")


@pytest.mark.parametrize("stem", ["BaBar_Lees2014xha", "CHARM_Tsai2019mtm"])     # 90%; CL unstated, taken as 90%
@pytest.mark.needs("pdg_r_ratio")
def test_a_90_percent_exclusion_is_native_and_pending_at_95_percent(monkeypatch, stem) -> None:
    _only(monkeypatch, {stem})
    native = ps._dark_photon_native(DarkPhoton(), MINIMAL, True)
    assert native.excluded is True and native.confidence_level == 0.90
    out = ps.dark_photon(DarkPhoton(), MINIMAL, True)
    assert out.native_excluded is True and out.excluded is None and "native 90%" in out.why


@pytest.mark.needs("pdg_r_ratio")
def test_the_highest_cl_exclusion_decides(monkeypatch) -> None:
    _only(monkeypatch, {"BaBar_Lees2014xha", "E137_Andreas2012mt"})
    out = ps.dark_photon(DarkPhoton(), MINIMAL, True)
    assert out.excluded is True and out.why.startswith("E137_Andreas2012mt")


@pytest.mark.needs("pdg_r_ratio")
def test_allowed_by_90_percent_searches_carries_over_to_95_percent(monkeypatch) -> None:
    _only(monkeypatch, set())
    out = ps.dark_photon(DarkPhoton(), MINIMAL, True)
    assert out.excluded is False and out.native_excluded is False and "hence at 95%" in out.why


def test_a_bump_hunt_applies_only_below_its_mass_resolution(monkeypatch) -> None:
    """BaBar 2014 (σ_m ≥ 1.5 MeV) for an A′ that decays to dark matter: below its resolution it excludes, above it
    the point is undecided, never excluded under DarkCast's narrow-peak assumption."""
    _only(monkeypatch, {"BaBar_Lees2014xha"})
    assert DarkPhoton().bosons(NARROW_OPEN)[0][1].width < 1.5e-3 < DarkPhoton().bosons(BROAD)[0][1].width
    assert ps._dark_photon_native(DarkPhoton(), NARROW_OPEN, True).excluded is True
    broad = ps._dark_photon_native(DarkPhoton(), BROAD, True)
    assert broad.excluded is None and "BaBar 2014" in broad.why and "1.5 MeV" in broad.why


def test_a_search_outside_its_gate_neither_excludes_nor_allows(monkeypatch) -> None:
    """The owner (2026-10-13): a broader signal samples other masses, backgrounds and efficiencies, so a narrow
    search's 'allowed' is not established outside its gate either: the point is undecided, with the reason."""
    _only(monkeypatch, set(), covering={"BaBar_Lees2014xha"})
    out = ps._dark_photon_native(DarkPhoton(), BROAD, True)
    assert out.excluded is None and "BaBar 2014" in out.why and "mass resolution" in out.why


def test_an_applicable_exclusion_stands_beside_a_gated_search(monkeypatch) -> None:
    _only(monkeypatch, {"NA64_NA642019imj"}, covering={"BaBar_Lees2014xha", "NA64_NA642019imj"})
    out = ps._dark_photon_native(DarkPhoton(), BROAD, True)                # NA64: Γ/m = 2.4%, within its gate
    assert out.excluded is True and out.why == "NA64_NA642019imj"


@pytest.mark.skipif(s._tool("DarkCast") is None, reason="DarkCast is not in the tools folder")
def test_the_owners_broad_dark_photon_is_undecided() -> None:
    """m_A′ = 5 GeV, m_χ = 1 GeV, g_D = 3, ε = 10⁻⁶: Γ = 1.182 GeV (23.6%); ADROIT had returned "allowed" though
    every search covering 5 GeV fails its width gate."""
    point = Point(m_chi=1.0, m_med=5.0, g_chi=3.0, g_q=1e-6)
    assert DarkPhoton().bosons(point)[0][1].width == pytest.approx(1.182, abs=1e-3)
    out = ps.dark_photon(DarkPhoton(), point, True)
    assert out.excluded is None and out.native_excluded is None and "mass resolution" in out.why


def test_resolutions_taken_from_the_collaborations_other_papers() -> None:
    """LHCb, CMS and HPS state no number for their own search (the owner, 2026-10-13): the same collaboration's value
    for the same data, always the smaller, with its source and derivation."""
    lhcb, cms, hps = (s.darkcast_info(k) for k in ("LHCb_Aaij2019bvg_prompt", "CMS_CMS2019kiy", "HPS_Adrian2018scb"))
    assert ps._darkcast_resolution(lhcb, 0.214) == pytest.approx(2.57e-4, rel=1e-2)   # below ~0.3 MeV at threshold
    assert ps._darkcast_resolution(lhcb, 60.0) == pytest.approx(0.072)                  # stated: 0.6 GeV at 60 GeV
    assert ps._darkcast_resolution(cms, 25.0) == pytest.approx(0.175)                   # its barrel window: 0.22 GeV
    assert ps._darkcast_resolution(hps, 0.034) == 0.00085 < 1.55e-3                     # its Møller point: 1.55 MeV
    for info in (lhcb, cms, hps):
        assert info["resolution_source"] and "DERIVED" in info["resolution_derivation"]


@pytest.mark.needs("pdg_r_ratio")
def test_an_unstated_resolution_applies_only_to_the_minimal_dark_photon(monkeypatch) -> None:
    info = s.darkcast_info
    stripped = {k: v for k, v in info("LHCb_Aaij2019bvg_prompt").items() if not k.startswith("resolution_")}
    monkeypatch.setattr(s, "darkcast_info", lambda stem: stripped if stem == "LHCb_Aaij2019bvg_prompt" else info(stem))
    _only(monkeypatch, {"LHCb_Aaij2019bvg_prompt"})
    assert ps._dark_photon_native(DarkPhoton(), MINIMAL, True).excluded is True
    out = ps._dark_photon_native(DarkPhoton(), NARROW_OPEN, True)
    assert out.excluded is None and "LHCb 2019 prompt: its mass resolution is not stated" in out.why


def test_missing_mass_and_missing_energy_gates() -> None:
    babar = s.darkcast_info("BaBar_Lees2017lec")                          # σ(M²) = 0.7 GeV²
    assert ps._darkcast_resolution(babar, 5.0) == pytest.approx(0.07)      # σ(M²)/(2m)
    assert ps._darkcast_resolution(babar, 1.0) == pytest.approx(0.1)       # at most 10% of m
    assert ps._darkcast_width_gate("BaBar_Lees2017lec", 0.05, 5.0, minimal=False) == ""
    assert "70 MeV" in ps._darkcast_width_gate("BaBar_Lees2017lec", 0.12, 5.0, minimal=False)
    assert ps._darkcast_width_gate("NA64_NA642019imj", 0.09, 1.0, minimal=False) == ""
    assert "11%" in ps._darkcast_width_gate("NA64_NA642019imj", 0.11, 1.0, minimal=False)
    na48 = s.darkcast_info("NA48_Batley2015lha")                           # σ = 6.7e-5 + 0.0105 m (GeV)
    assert ps._darkcast_resolution(na48, 0.1) == pytest.approx(6.7e-5 + 1.05e-3)


def test_a_search_that_does_not_cover_the_mass_is_ignored(monkeypatch) -> None:
    _only(monkeypatch, set(), covering={"NA64_NA642019imj"})
    out = ps._dark_photon_native(DarkPhoton(), BROAD, True)
    assert out.excluded is False and math.isclose(out.confidence_level, 0.90)
    _only(monkeypatch, set(), covering={"nothing"})
    assert "no recorded search covers" in ps._dark_photon_native(DarkPhoton(), BROAD, True).why
