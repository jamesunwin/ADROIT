"""The records of the batch plan's §6 (2026-10-20), each unverified until the owner signs it."""
import math

import numpy as np
import pytest

from adroit.constraints import searches as s
from adroit.parameter_space import library, searches
from tests.unsigned_records import as_unsigned


@pytest.fixture(autouse=True)
def before_signing(monkeypatch):
    """These tests are of the batch's records unsigned (each pending, naming itself), and read the real records,
    which the owner signs: they are read as they stood before."""
    as_unsigned(monkeypatch)


def _limit(rid: str, m: float) -> float:
    points = s._bundled(rid)["points"]
    return math.exp(float(np.interp(m, [x for x, _ in points], [math.log(y) for _, y in points])))


# --- Z → 4μ ------------------------------------------------------------------------------------------------------

def test_z_to_4mu_decides_by_the_stronger_record_and_waits_for_its_signature():
    """CMS's and ATLAS's limits each stand and the stronger decides (the owner, 2026-10-19), on g′ √(BR/BR_vanilla);
    unsigned, each record leaves the search pending."""
    m = 30.0
    strongest = min(_limit(rid, m) for rid in searches.FOUR_MU)
    assert _limit("atlas-2301.09342-4mu", m) < _limit("cms-1808.03684-4mu", m)          # ATLAS stronger near 30 GeV
    excluded = searches._z_to_4mu(m, 2 * strongest, 1e-4, 1 / 3, 1 / 3, True)
    assert excluded.excluded and excluded.ratio == pytest.approx(2.0, rel=1e-6)
    assert "ATLAS" in excluded.source
    allowed = searches._z_to_4mu(m, 0.5 * strongest, 1e-4, 1 / 3, 1 / 3, True)
    assert allowed.excluded is False and allowed.ratio == pytest.approx(0.5, rel=1e-6)
    diluted = searches._z_to_4mu(m, 2 * strongest, 1e-4, 1 / 27, 1 / 3, True)       # BR(μμ) a ninth of vanilla
    assert diluted.excluded is False and diluted.ratio == pytest.approx(2 / 3, rel=1e-6)
    waiting = searches._z_to_4mu(m, 2 * strongest, 1e-4, 1 / 3, 1 / 3, False)
    assert waiting.excluded is None and "verif" in waiting.why


def test_z_to_4mu_is_undecided_for_a_broad_zprime_and_absent_outside_its_masses():
    broad = searches._z_to_4mu(30.0, 0.05, 0.9, 1 / 3, 1 / 3, True)                   # Γ/m = 3%
    assert broad.excluded is None and "Γ/m" in broad.why
    only_atlas = searches._z_to_4mu(75.0, 1.0, 0.1, 1 / 3, 1 / 3, True)             # above CMS's 70 GeV
    assert only_atlas.excluded and "ATLAS" in only_atlas.source
    assert searches._z_to_4mu(100.0, 1.0, 0.1, 1 / 3, 1 / 3, True) is None
    assert searches._z_to_4mu(30.0, 1.5e-3, 1e-6, 1 / 3, 1 / 3, False) is None             # below both papers' reach


def test_the_library_lmu_minus_ltau_gets_its_z_to_4mu_outcome():
    e = library.entry("lmu_minus_ltau")
    p = e.point.model_copy(update={"m_med": 20.0, "m_chi": 30.0, "g_q": 0.02})       # no dark-matter decay
    outcome = next(o for o in searches.lmu_ltau(e.model_class, p, True) if o.name == searches.Z4MU)
    assert outcome.excluded and outcome.ratio == pytest.approx(0.02 / min(_limit(r, 20.0) for r in searches.FOUR_MU),
                                                               rel=2e-2)


# --- the 2HDM+a's flavour bounds -------------------------------------------------------------------------------------

def test_the_2hdma_benchmark_is_excluded_by_bs_mumu_and_allowed_by_bsgamma():
    """The owner (2026-10-19): both bounds exclude. The library's benchmark (tan β = 1, M_H± = 1 TeV) lies in B_s → μμ's
    lower region (tan β < 1.29 at 1 TeV; the paper: 1.3) and above b → sγ's 800 GeV; unsigned, both pending."""
    e = library.entry("two_hdm_a")
    gamma, mumu = searches.two_hdm_flavour(e.model_class, e.point, True)
    assert gamma.name == searches.BSGAMMA and gamma.excluded is False
    assert mumu.name == searches.BSMUMU and mumu.excluded is True and "1.29" in mumu.why
    assert all(o.excluded is None and "verif" in o.why for o in searches.two_hdm_flavour(e.model_class, e.point, False))
    assert searches._bsmumu(1000.0, 5.0, True).excluded is False and searches._bsmumu(1000.0, 25.0, True).excluded
    assert searches._bsgamma(700.0, 3.0, True).excluded and searches._bsgamma(900.0, 3.0, True).excluded is False
    assert searches._bsgamma(700.0, 0.3, True).excluded is None                     # below the record's tan β
    assert searches._bsmumu(1800.0, 5.0, True).excluded is None                     # beyond the figure's 1500 GeV


@pytest.mark.needs("ufo_models")
def test_a_generic_2hdma_gets_the_flavour_bounds_through_its_match():
    from adroit.parameter_space.portals import generic_2hdma
    from adroit.parameter_space.portals.generic import GenericModel
    x = {"MXd": 160.0, "mh1": 125.09, "mh2": 1000.0, "mh3": 1000.0, "mh4": 400.0, "mhc": 1000.0, "sinp": 0.35,
         "tanbeta": 1.0, "sinbma": 1.0, "gPXd": 1.0, "lam3": 3.0, "laP1": 3.0, "laP2": 3.0}
    engine = GenericModel.for_spec(generic_2hdma.spec(x))
    ours = searches.two_hdm_flavour(engine, engine.point(), True)
    e = library.entry("two_hdm_a")
    theirs = searches.two_hdm_flavour(e.model_class, e.point, True)
    assert [(o.name, o.excluded) for o in ours] == [(o.name, o.excluded) for o in theirs]
    assert searches.two_hdm_flavour(library.entry("inert_doublet").model_class, library.entry("inert_doublet").point,
                                    True) is None


# --- N_eff for a light L_μ − L_τ Z′ ----------------------------------------------------------------------------------

@pytest.mark.parametrize("m_mev, g, expected", [
    (0.2, 1e-7, True),               # inside ΔN_eff = 0.5 (thermalised early, decays after neutrino decoupling)
    (5.0, 5e-8, None),               # the paper's Fig. 4: N_eff = 3.4, in the 0.2–0.5 band
    (13.0, 5e-4, None),              # Fig. 4: N_eff = 3.4
    (30.0, 1e-6, False),             # to the right of every contour
])
def test_neff_excludes_inside_half_and_leaves_the_band_undecided(m_mev, g, expected):
    """The owner (2026-10-19): Planck 2018 excludes inside the ΔN_eff = 0.5 contour, the 0.2–0.5 band is undecided,
    ACT only flags; the library's L_μ − L_τ (natural kinetic mixing, the figure's bottom frame)."""
    outcome = searches._lmu_neff(g, m_mev / 1e3, 0.0, "natural_mixing", True)
    assert outcome.excluded is expected


@pytest.mark.needs("pdg_r_ratio")
def test_neff_reach_dark_matter_decays_flags_and_the_signature():
    assert searches._lmu_neff(1e-10, 5e-3, 0.0, "natural_mixing", True) is None      # below equilibration (Fig. 4: 4.39)
    assert searches._lmu_neff(1e-6, 50e-3, 0.0, "natural_mixing", True) is None      # decays before decoupling
    flagged = searches._lmu_neff(1e-9, 13e-3, 0.0, "natural_mixing", True)
    assert flagged.excluded is False and searches.ACT_FLAG in flagged.flags
    assert "dark matter" in searches._lmu_neff(1e-7, 0.2e-3, 0.3, "natural_mixing", True).why
    assert "verif" in searches._lmu_neff(1e-7, 0.2e-3, 0.0, "natural_mixing", False).why
    e = library.entry("lmu_minus_ltau")
    p = e.point.model_copy(update={"m_med": 2e-4, "m_chi": 1.0, "g_q": 1e-7})       # no decay to dark matter
    assert searches.neff(e.model_class, p, True).excluded is True


# --- LHCb's B⁺ → K⁺a(→ μμ) -------------------------------------------------------------------------------------------

def _alp(m_a: float, g: float):
    e = library.entry("alp_portal")
    return e, e.point.model_copy(update={"m_med": m_a, "g_q": g, "g_l": g, "g_chi": 1e-3, "m_chi": 1.0})  # no a → χχ̄


def test_lhcb_b_to_k_mumu_on_a_light_alp():
    """BR(B → K a) × BR(a → μμ) against LHCb's map at (m_a, τ_a): a 300 MeV ALP with g = 10⁻³ (τ ≈ 540 ps) is
    excluded; with 10⁻⁴ (τ ≈ 4 × 10⁴ ps) it is beyond the map, undecided; outside 250–410 MeV no outcome; unsigned,
    pending."""
    e, p = _alp(0.3, 1e-3)
    outcome = searches.b_to_k_mumu(e.model_class, p, True)
    assert outcome.excluded and outcome.ratio > 1
    e, p = _alp(0.3, 1e-4)
    assert "outside LHCb's" in searches.b_to_k_mumu(e.model_class, p, True).why
    assert searches.b_to_k_mumu(*_alp(0.5, 1e-3)[0:1], _alp(0.5, 1e-3)[1], True) is None
    assert searches.b_to_k_mumu(*_alp(0.2, 1e-3)[0:1], _alp(0.2, 1e-3)[1], True) is None
    e, p = _alp(0.3, 1e-3)
    assert "verif" in searches.b_to_k_mumu(e.model_class, p, False).why


def test_lhcb_b_to_k_mumu_through_the_generic_route():
    from tests.parameter_space.test_generic_portrait import _generic_at
    e, p = _alp(0.3, 1e-3)
    engine, q = _generic_at("alp_portal", p)
    ours, theirs = searches.b_to_k_mumu(engine, q, True), searches.b_to_k_mumu(e.model_class, p, True)
    assert ours.excluded == theirs.excluded and ours.ratio == pytest.approx(theirs.ratio, rel=5e-2)


# --- electroweak precision (S, T) ------------------------------------------------------------------------------------

@pytest.mark.needs("ufo_models")
def test_electroweak_precision_on_the_inert_doublet_and_the_2hdma():
    """χ² of (S, T) against PDG 2024's U = 0 fit: Kalinowski et al.'s HP10 and the custodial 2HDM+a benchmark allowed,
    a light doublet with a large splitting and a 2HDM+a with M_H± ≠ M_H excluded; unsigned, pending."""
    e = library.entry("inert_doublet")
    assert searches.electroweak_precision(e.model_class, e.point, True).excluded is False
    split = e.point.model_copy(update={"m_chi": 60.0, "m_med": 400.0, "g_q": 40.0})            # H±: 400 GeV
    assert searches.electroweak_precision(e.model_class, split, True).excluded is True
    assert "verif" in searches.electroweak_precision(e.model_class, e.point, False).why
    from adroit.parameter_space.portals import generic_2hdma
    benchmark = generic_2hdma.Match(values={"MXd": 160.0, "mh1": 125.09, "mh2": 1000.0, "mh3": 1000.0, "mh4": 400.0,
                                            "mhc": 1000.0, "sinp": 0.35, "tanbeta": 1.0, "sinbma": 1.0, "gPXd": 1.0,
                                            "lam3": 3.0, "laP1": 3.0, "laP2": 3.0}, names={})
    cls, p = benchmark.portal()
    assert searches.electroweak_precision(cls, p, True).excluded is False
    split = benchmark.model_copy(update={"values": {**benchmark.values, "mhc": 800.0}})
    cls, p = split.portal()
    assert searches.electroweak_precision(cls, p, True).excluded is True


@pytest.mark.needs("ufo_models")
def test_electroweak_precision_through_the_generic_inert_doublet():
    from tests.parameter_space.test_generic_p5 import _inert_at
    engine = _inert_at(60.0, 100.0, 400.0, 0.01)
    outcome = searches.electroweak_precision(engine, engine.point(), True)
    e = library.entry("inert_doublet")
    p = e.point.model_copy(update={"m_chi": 60.0, "m_med": 400.0, "g_chi": 0.01, "g_q": 40.0})
    assert outcome.excluded == searches.electroweak_precision(e.model_class, p, True).excluded is True


# --- LEP's charged partners ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind, mass, split, expected", [
    ("chargino", 85.0, 0.5, True),       # ALEPH: below 88 GeV at any splitting
    ("chargino", 95.0, 0.5, False),      # above ALEPH's 88, splitting below DELPHI's 3 GeV
    ("chargino", 95.0, 4.0, True),       # DELPHI: 97.1 GeV from 3 GeV
    ("chargino", 102.0, 6.0, False),     # DELPHI: 101.7 GeV from 5 GeV
    ("chargino", 102.0, 12.0, True),     # DELPHI: 102.7 GeV from 10 GeV
    ("wino", 103.0, 12.0, True),         # a triplet's: 103.4 GeV
    ("slepton", 92.0, 10.0, True),       # μ̃_R: 94.0 GeV from 4 GeV
    ("slepton", 92.0, 2.0, None),        # below OPAL's 4 GeV splitting
])
def test_lep_charged_partners(kind, mass, split, expected):
    assert searches._lep_state(kind, "mu", mass, split, True).excluded is expected


def test_lep_on_the_library_lepton_partner_and_a_generic_light_doublet():
    """The library's t-channel μ_R partner below 94 GeV is excluded (unsigned: pending); above LEP's reach, no outcome;
    an inert doublet's charged state is left to LEP's inert-doublet limit."""
    from adroit.parameter_space.portals.tchannel import TChannel
    from adroit.parameter_space.classes import Point
    partner = TChannel(partner="muR")
    assert searches.lep_charged(partner, Point(m_chi=50.0, m_med=90.0, g_chi=1.0), True).excluded is True
    assert "verif" in searches.lep_charged(partner, Point(m_chi=50.0, m_med=90.0, g_chi=1.0), False).why
    assert searches.lep_charged(partner, Point(m_chi=50.0, m_med=150.0, g_chi=1.0), True) is None
    from tests.parameter_space.test_generic_p5 import _inert_at
    engine = _inert_at(60.0, 70.0, 80.0, 0.01)          # an inert doublet's H± is left to LEP's inert-doublet limit
    assert searches.lep_charged(engine, engine.point(), True) is None
    assert searches.inert_doublet(engine, engine.point(), True) is not None


DOUBLET = {"name": "F", "spin": 0.5, "dark_parity": -1, "mass_gev": 80.0, "charges": {"su2": 2, "hypercharge": -0.5}}


def test_lep_bounds_a_generic_chargino_only_through_its_decay_to_the_dark_matter():
    """The tactical audit's T20-07: a doublet whose W partner is the dark matter is a chargino (ALEPH: excluded below
    88 GeV at any splitting); with a decoupled singlet as the dark matter, its splitting is not the singlet's mass
    difference, whatever that is: pending."""
    from tests.parameter_space.test_generic_lhc import _engine
    engine, p = _engine([{**DOUBLET, "role": "dark_matter"}])
    assert searches.lep_charged(engine, p, True).excluded is True
    for spectator in (50.0, 79.0):
        engine, p = _engine([{"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True,
                              "dark_parity": -1, "mass_gev": spectator}, {**DOUBLET, "role": "mediator"}])
        outcome = searches.lep_charged(engine, p, True)
        assert outcome.excluded is None and "W partners (F0) do not include the dark matter S0" in outcome.why


def test_lep_bounds_a_generic_smuon_only_through_its_decay_to_the_muon_and_the_dark_matter():
    from tests.parameter_space.test_generic_lhc import _engine
    charges = {"hypercharge": -1.0}
    chi = {"name": "chi", "spin": 0.5, "self_conjugate": True, "dark_parity": -1, "mass_gev": 50.0}
    smuon = {"name": "Pl", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 90.0, "charges": charges}
    mu = {"name": "muR", "role": "standard_model", "spin": 0.5, "chirality": "R", "charges": charges}
    term = {"fields": [{"field": "Pl", "conjugate": True}, {"field": "chi", "conjugate": True}, {"field": "muR"}],
            "lorentz": "chiral", "coupling": "0.5", "plus_hc": True}
    engine, p = _engine([{**chi, "role": "dark_matter"}, smuon, mu], [term])
    assert searches.lep_charged(engine, p, True).excluded is True              # OPAL: 94 GeV from a 4 GeV splitting
    lighter = {"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True, "dark_parity": -1,
               "mass_gev": 30.0}
    engine, p = _engine([lighter, {**chi, "role": "mediator"}, smuon, mu], [term])
    outcome = searches.lep_charged(engine, p, True)
    assert outcome.excluded is None and "no vertex joins it to the mu and the dark matter S0" in outcome.why


@pytest.mark.parametrize("m_med, g", [(0.0002, 1e-7), (0.03, 1e-6)])
@pytest.mark.needs("pdg_r_ratio")
def test_neff_waits_when_the_z_prime_decays_to_the_dark_matter_below_the_muon_threshold(m_med, g):
    """The tactical audit's T20-06: the dark matter's share was read from the muons' branching, zero below their
    threshold, where the whole N_eff reach lies."""
    e = library.entry("lmu_minus_ltau")
    p = e.point.model_copy(update={"m_chi": m_med / 4, "m_med": m_med, "g_q": g, "g_chi": 0.1})
    outcome = searches.neff(e.model_class, p, True)
    assert outcome.excluded is None and "decays to the dark matter (100% of its width)" in outcome.why


def test_b_to_k_invisible_is_judged_at_both_assignments_and_lhcbs_muons_at_their_own_width(monkeypatch):
    """The tactical audit's T20-03 with the owner's decision #7: a light CP-odd scalar decaying to other new states is
    judged by BaBar's B → K + invisible at both extreme assignments of BR(invisible), and decided only where they
    agree; BR(μμ) is still its own width's, so LHCb's search runs."""
    seen = []
    def b_to_k(m_a, g_q, invisible, unverified):
        seen.append(invisible)
        return searches.Outcome(name=searches.FLAVOUR, excluded=invisible > .5, ratio=2 * invisible)
    monkeypatch.setattr(searches, "_b_to_k", b_to_k)
    monkeypatch.setattr(searches, "_generic_flavour", lambda cls, p: [(1.0, 1e-3, (.2, .9), 0.2, 1e-9, "a decays", 0.0)])
    outcome = searches._flavour_native(object(), None, True)
    assert seen == [.2, .9] and outcome.excluded is None and outcome.why.startswith("a decays")
    monkeypatch.setattr(searches, "_generic_flavour", lambda cls, p: [(1.0, 1e-3, (.6, .9), 0.2, 1e-9, "a decays", 0.0)])
    assert searches._flavour_native(object(), None, True).excluded is True
    lhcb = []
    monkeypatch.setattr(searches, "_lhcb_mumu", lambda *args: lhcb.append(args) or None)
    searches.b_to_k_mumu(object(), None, True)
    assert lhcb and lhcb[0][2] == 0.2


UNSIGNED = ["cms-1808.03684-4mu", "atlas-2301.09342-4mu", "lhcb-1612.07818-b-to-k-mumu", "li-2412.04572-bsgamma",
            "dmwg-1810.09420-bsmumu", "pdg-2024-electroweak-st", "lep-charginos", "opal-hep-ex-0309014-sleptons",
            "escudero-1901.02010-neff"]


@pytest.mark.parametrize("rid", UNSIGNED)
def test_an_unsigned_records_pending_outcome_names_it_for_the_review_queue(rid):
    """The batch audit's B20-11: a blocked outcome had the record's id in its prose only, so its evidence had no
    source and the review queue asked for a calculation. Its source is now the record, and the task is to verify it."""
    from adroit.constraints.review_queue import SelectedEvidence, build_queue
    from adroit.core.evidence import EvidenceContext, EvidenceEnvelope
    from adroit.evidence.observations import point_observations
    from adroit.evidence.runtime import _sources
    from adroit.parameter_space import verdict
    from tests.parameter_space.test_halo_region import _point, _sample
    blocked = s._blocked("a search", rid, False)
    assert blocked is not None and blocked.source == rid
    context = EvidenceContext(origin="captured", sources=_sources())
    row = _point([_sample(False)], excluded={blocked.name: None}, pending=[f"{blocked.name}: {blocked.why}"])
    row.search_results = [blocked]
    crossing = verdict.classify(None, row)
    observations = point_observations(row, {}, context)
    found = next(o for o in observations if o.observable == blocked.name)
    assert found.source_ids == [rid] and found.review == "unreviewed"
    envelope = EvidenceEnvelope(workflow="track1", result_sha256="x", input_sha256="x", context=context,
                                observations=observations)
    queue = build_queue([SelectedEvidence(envelope=envelope, result={"verdict": {"crossings": [
        crossing.model_dump(mode="json")]}})])
    assert [(t.kind, t.record_id) for t in queue.tasks] == [("source_verification", rid)]


def test_z_to_4mu_with_both_records_unsigned_names_both():
    outcome = searches._z_to_4mu(30.0, 1e-2, 1e-4, 1 / 3, 1 / 3, False)
    assert outcome.excluded is None and outcome.source.split("; ") == list(searches.FOUR_MU)


@pytest.mark.parametrize("reviewed, excluded", [("cms-1808.03684-4mu", None), ("atlas-2301.09342-4mu", True)])
def test_z_to_4mu_with_one_record_reviewed_decides_only_by_an_exclusion(monkeypatch, reviewed, excluded):
    """The recheck's RB20-04 (2026-10-20), its control: at m = 30 GeV, g′ = 0.01, CMS's limit allows (ratio 0.85) and
    ATLAS's excludes (1.38). With only CMS reviewed, its allowed outcome had hidden ATLAS's unsigned record: now
    pending, naming ATLAS's record and CMS's allowing. With only ATLAS reviewed, its exclusion decides."""
    blocked = s._blocked
    monkeypatch.setattr(s, "_blocked", lambda name, rid, unverified: None if rid == reviewed else
                        blocked(name, rid, False))
    outcome = searches._z_to_4mu(30.0, 1e-2, 1e-4, 1 / 3, 1 / 3, False)
    assert outcome.excluded is excluded
    if excluded is None:
        other = next(r for r in searches.FOUR_MU if r != reviewed)
        assert outcome.source == other and "allows (ratio 0.852) but does not decide alone" in outcome.why
    else:
        assert outcome.ratio == pytest.approx(1.378, rel=1e-3)


def test_a_model_with_the_2hdmas_fields_not_read_as_it_keeps_its_flavour_searches_pending(monkeypatch):
    """B20-10: the flavour dispatcher had returned nothing for a failed match; it is undecided, with why."""
    from adroit.parameter_space.portals import generic_2hdma
    monkeypatch.setattr(generic_2hdma, "match", lambda cls, p: "its new scalars are not one CP-even and two CP-odd")
    found = searches.two_hdm_flavour(object(), None, True)
    assert [o.name for o in found] == [searches.BSGAMMA, searches.BSMUMU]
    assert all(o.excluded is None and "not read as it" in o.why for o in found)
