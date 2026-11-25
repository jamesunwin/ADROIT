"""G9: colliders for the generic engine (``portals.generic_lhc``)."""

import pytest

from adroit.constraints import lhc
from adroit.core.model_spec import ModelSpec
from adroit.evaluation import zoo
from adroit.parameter_space import searches
from adroit.parameter_space.portals.generic import GenericModel

needs_tables = pytest.mark.skipif(not lhc.table_available("wino_c1c1"), reason="the SUSY cross-section tables are "
                                                                               "not in the tools folder")


def _entry(entry_id: str, k: int = 0):
    e = next(x for x in zoo.entries() if x.id == entry_id)
    return zoo._generic(e, e.targets[k])


@needs_tables
def test_a_wino_like_multiplet_reads_the_electroweakino_tables():
    """The generic wino: χ⁰ and χ± split by 165 MeV, χ± → χ⁰π with the library's width, the three wino tables."""
    engine, thermal = _entry("wino_majorana_triplet_bottaro")
    p = thermal.model_copy(update={"m_chi": 600.0})          # inside the tables (the thermal 2.9 TeV is not)
    text, sigma, why = engine.lhc_spectrum(p)
    assert not why and sigma == pytest.approx(sum(lhc.cross_section_pb(k, p.m_chi) for k in
                                                  ("wino_c1c1", "wino_c1p_n", "wino_c1m_n")))
    assert "1000024" in text and f"{lhc.chargino_width(0.16544, 2.0):.3E}"[:4] in text


@needs_tables
def test_a_coloured_partner_reads_the_stop_table_as_a_lower_bound():
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
               "mass_gev": 300.0},
              {"name": "Phi", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 900.0,
               "charges": {"su3": "3", "hypercharge": 2 / 3}},
              {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R",
               "charges": {"su3": "3", "hypercharge": 2 / 3}}]
    terms = [{"fields": [{"field": "Phi", "conjugate": True}, {"field": "chi", "conjugate": True}, {"field": "uR"}],
              "lorentz": "chiral", "coupling": "y", "plus_hc": True}]
    spec = ModelSpec.model_validate({"name": "t", "phase": "unbroken", "fields": fields, "terms": terms,
                                     "couplings": [{"name": "y", "value": 1.0}]})
    engine = GenericModel.of(spec)
    p = engine.point()
    text, sigma, why = engine.lhc_spectrum(p)
    assert not why and sigma == pytest.approx(lhc.cross_section_pb("coloured", 900.0))
    assert searches._qcd_lower_bound(engine, p)


@pytest.mark.slow
def test_a_wino_beyond_the_tables_goes_to_madgraph():
    """At 2.86 TeV the electroweakino tables end: MadGraph's LO, with the one-loop splitting and χ± → χ⁰π."""
    engine, p = _entry("wino_majorana_triplet_bottaro")
    text, sigma, why = engine.lhc_spectrum(p)
    assert not why and sigma > 0 and "MG5LO" in text and "211" in text


@pytest.mark.slow
def test_a_partner_decaying_through_an_off_shell_w_reaches_smodels():
    """Choubey et al.'s charged triplet fermion lies 40 GeV above the dark matter: its decay goes through an
    off-shell W (three-body), so MadGraph's production reaches SModelS."""
    engine, p = _entry("singlet_triplet_fermion_choubey")
    text, sigma, why = engine.lhc_spectrum(p)
    assert not why and sigma > 1.0 and "MG5LO" in text


def test_the_higgs_signal_strength_is_the_singlet_mixing_engines():
    """Das et al.'s BP8 (sin θ = 0.13): μ = c⁴Γ_SM/(c²Γ_SM + Γ_new), as the library's singlet-mixing engine."""
    e = next(x for x in zoo.entries() if x.id == "singlet_fermion_scalar_mediator_das")
    engine, gp = zoo._generic(e, e.targets[2])
    mu = engine.higgs_mu(gp)
    assert mu == pytest.approx(0.13 ** 0 * (1 - 0.13 ** 2) ** 2 / (1 - 0.13 ** 2), rel=0.03)


@needs_tables
def test_the_higgsino_spectrum_is_the_librarys():
    from adroit.parameter_space import library, searches
    engine, thermal = _entry("higgsino_dirac_doublet_bottaro")
    held = library.entry("higgsino")
    _, sigma, why = engine.lhc_spectrum(thermal.model_copy(update={"m_chi": 600.0}))
    assert not why and sigma == pytest.approx(searches.lhc_spectrum(held.model_class,
                                                                    held.point.model_copy(update={"m_chi": 600.0}))[1])


def test_a_mixed_dark_matter_state_does_not_read_the_pure_tables():
    """Dedes & Karamitros's dark matter is a 50% doublet–triplet mixture: not a pure higgsino (it goes to MadGraph)."""
    from adroit.parameter_space.portals import generic_lhc
    engine, p = _entry("doublet_triplet_fermion_dedes")
    mb, rules, _ = engine.at(p)
    assert generic_lhc.pure_dark_kind(mb, rules) == ""


def test_a_partner_without_a_decay_is_named():
    engine, p = _entry("coloured_coannihilation_scalar_triplet_desimone")
    why = engine.lhc_spectrum(p)[2]
    assert why.startswith("the partner chi_prime has no two-body decay") and "outside" not in why


def _slepton_partner(mass: float):
    """A Majorana singlet dark matter and one slepton-like partner Pe that decays to it and a right-handed electron."""
    from adroit.core.model_spec import ModelSpec
    charges = {"hypercharge": -1.0}
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
               "mass_gev": 100.0},
              {"name": "Pe", "role": "other", "spin": 0, "dark_parity": -1, "mass_gev": mass, "charges": charges},
              {"name": "eR", "role": "standard_model", "spin": 0.5, "chirality": "R", "charges": charges}]
    terms = [{"fields": [{"field": "Pe", "conjugate": True}, {"field": "chi", "conjugate": True}, {"field": "eR"}],
              "lorentz": "chiral", "coupling": "0.5", "plus_hc": True}]
    engine = GenericModel.of(ModelSpec.model_validate({"name": "slepton_partner", "phase": "unbroken",
                                                       "fields": fields, "terms": terms}))
    return engine.at(engine.point())[:2]


@pytest.mark.skipif(not lhc.table_available("slepton"), reason="the SUSY cross-section tables are not in the tools "
                                                                "folder")
def test_a_partner_outside_its_production_table_is_named_as_such():
    """The fallback review's D5: a partner that decays but lies outside its table was told "no two-body decay"."""
    from adroit.parameter_space.portals import generic_lhc
    low, high = lhc.table_range("slepton")
    inside = generic_lhc.lhc_spectrum(*_slepton_partner(0.5 * (low + high)))
    assert inside[1] is not None and not inside[2]
    text, sigma, why = generic_lhc.lhc_spectrum(*_slepton_partner(1.5 * high))
    assert sigma is None and not text
    assert why == (f"the partner Pe's mass, {1.5 * high:g} GeV, is outside the slepton production table "
                   f"({low:g}–{high:g} GeV), so its pair production has no cross-section here")
    assert "two-body decay" not in why


def test_a_partner_whose_table_is_not_installed_is_named_as_such(monkeypatch):
    from adroit.parameter_space.portals import generic_lhc
    monkeypatch.setattr(lhc, "table_available", lambda kind: False)
    assert lhc.table_range("slepton") is None
    _, sigma, why = generic_lhc.lhc_spectrum(*_slepton_partner(500.0))
    assert sigma is None and why == ("the partner Pe's pair production needs the slepton production table, which is "
                                     "not in the tools folder (`adroit setup --fetch`)")


def test_a_model_with_two_partners_sends_every_odd_state_to_madgraph(monkeypatch):
    """The audit's G9-1 (G12): with a slepton-like and a coloured partner, only the slepton reached SModelS (r = 0.07,
    "allowed") while the coloured one alone gives r = 3. A table covers one sector; two go through MadGraph together."""
    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space.portals import generic_lhc
    from adroit.parameter_space.portals.generic import GenericModel
    charges = {"uR": {"su3": "3", "hypercharge": 2 / 3}, "eR": {"hypercharge": -1.0}}
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
               "mass_gev": 100.0}]
    terms = []
    for partner, mass, sm in (("Pe", 600.0, "eR"), ("Pu", 800.0, "uR")):
        fields += [{"name": partner, "role": "other", "spin": 0, "dark_parity": -1, "mass_gev": mass,
                    "charges": charges[sm]},
                   {"name": sm, "role": "standard_model", "spin": 0.5, "chirality": "R", "charges": charges[sm]}]
        terms.append({"fields": [{"field": partner, "conjugate": True}, {"field": "chi", "conjugate": True},
                                 {"field": sm}], "lorentz": "chiral", "coupling": "0.5", "plus_hc": True})
    engine = GenericModel.of(ModelSpec.model_validate({"name": "two", "phase": "unbroken", "fields": fields,
                                                       "terms": terms}))
    mb, rules, _ = engine.at(engine.point())
    called = []
    monkeypatch.setattr(generic_lhc, "madgraph_spectrum", lambda mb, rules: called.append(True) or ("slha", 1.0, ""))
    assert generic_lhc.lhc_spectrum(mb, rules) == ("slha", 1.0, "") and called


def _engine(fields, terms=(), couplings=()):
    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space.portals.generic import GenericModel
    spec = ModelSpec.model_validate({"name": "m", "phase": "unbroken", "fields": list(fields), "terms": list(terms),
                                     "couplings": list(couplings)})
    engine = GenericModel.of(spec, sommerfeld=False)
    return engine, engine.point()


HIGGS = {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}


def test_a_dirac_triplet_is_not_read_as_the_majorana_wino():
    """The audit's G9-3 (G12): a Dirac Y = 0 triplet took the Majorana wino's tables (σ half its own)."""
    from adroit.parameter_space.portals import generic_lhc
    engine, p = _engine([{"name": "T", "role": "dark_matter", "spin": 0.5, "mass_gev": 600.0, "dark_parity": -1,
                          "charges": {"su2": 3, "hypercharge": 0}}, HIGGS])
    mb, rules, _ = engine.at(p)
    assert generic_lhc.pure_dark_kind(mb, rules) == ""


@pytest.mark.parametrize("y", [0.5, -0.5])
def test_a_dirac_doublets_charged_state_is_split_above_the_neutral_one(y):
    """The audit's G9-4: the anti-multiplet's pass overwrote the shift with q·Y's sign flipped (−22 MeV)."""
    from adroit.parameter_space.portals import generic_lhc
    from adroit.parameter_space.portals.generic_today import splitting
    from adroit.parameter_space.portals.multiplet import ALPHA_2_MZ, M_W, M_Z
    engine, p = _engine([{"name": "N", "role": "dark_matter", "spin": 0.5, "mass_gev": 2000.0, "dark_parity": -1,
                          "charges": {"su2": 2, "hypercharge": y}}, HIGGS])
    mb, rules, _ = engine.at(p)
    split = generic_lhc.with_loop_splittings(mb, rules)
    charged = next(x for x in split.particles if x.parity == -1 and x.charge)
    neutral = next(x for x in split.particles if x.parity == -1 and not x.charge)
    assert charged.mass - neutral.mass == pytest.approx(splitting(2, 0.5, 1, M_W, M_Z, ALPHA_2_MZ), abs=1e-6)


@pytest.mark.needs("susy_tables")
def test_a_dirac_dark_matters_coloured_partner_finds_its_decay():
    """The audit's G9-5: a Dirac χ's vertices are (χ, u, Φ̄) and (χ̄, ū, Φ), so the partner's decay was not found."""
    charges = {"su3": "3", "hypercharge": 2 / 3}
    engine, p = _engine(
        [{"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 300.0},
         {"name": "Phi", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 1200.0, "charges": charges},
         {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R", "charges": charges}],
        [{"fields": [{"field": "Phi", "conjugate": True}, {"field": "chi", "conjugate": True}, {"field": "uR"}],
          "lorentz": "chiral", "coupling": "1.0", "plus_hc": True}])
    text, sigma, why = engine.lhc_spectrum(p)
    assert sigma is not None and sigma > 0 and why == ""


def test_the_monojet_recast_is_undecided_when_the_mediators_decays_are_unknown():
    """The audit's G9-6 (G12): a decay G6 cannot name (here s → χ χ₂) had set BR_inv = 0, so μ = 0 and "allowed"."""
    import math

    from adroit.parameter_space import searches
    v, m1, m2, st, y = 246.21965, 125.09, 200.0, 0.1, 0.3
    ct = math.sqrt(1 - st ** 2)
    mss, mhh, mhs = m2 ** 2 * ct ** 2 + m1 ** 2 * st ** 2, m1 ** 2 * ct ** 2 + m2 ** 2 * st ** 2, (m2 ** 2 - m1 ** 2) * st * ct

    def occ(*xs):
        return [{"field": f.rstrip("*"), "conjugate": f.endswith("*")} for f in xs]
    engine, p = _engine(
        [{"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
          "mass_gev": 50.0},
         {"name": "s", "role": "mediator", "spin": 0, "self_conjugate": True}, HIGGS,
         {"name": "chi2", "role": "other", "spin": 0.5, "self_conjugate": True, "dark_parity": -1, "mass_gev": 100.0}],
        [{"fields": occ("H", "H*", "s"), "lorentz": "scalar", "coupling": "-mu_hs"},
         {"fields": occ("s", "s"), "lorentz": "scalar", "coupling": "-mu_s2/2"},
         {"fields": occ("H", "H*", "H", "H*"), "lorentz": "scalar", "coupling": "-l_h"},
         {"fields": occ("chi*", "chi", "s"), "lorentz": "scalar", "coupling": "-y/2"},
         {"fields": occ("chi*", "chi2", "s"), "lorentz": "scalar", "coupling": "-y2", "plus_hc": True}],
        [{"name": "mu_hs", "value": mhs / v, "mass_dimension": 1}, {"name": "mu_s2", "value": mss, "mass_dimension": 2},
         {"name": "l_h", "value": mhh / (2 * v ** 2)}, {"name": "y", "value": y}, {"name": "y2", "value": 0.3}])
    outcome = searches.monojet_spin0(engine, p, True)
    assert outcome is not None and outcome.excluded is None and "invisible branching is unknown" in outcome.why


@pytest.mark.needs("susy_tables")
def test_a_partner_coupled_to_two_flavours_shares_its_decays():
    """The audit's G9-2 (G12): a partner coupled to e_R and μ_R was written as decaying to e alone."""
    import re
    charges = {"hypercharge": -1.0}
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
               "mass_gev": 100.0},
              {"name": "Pl", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 400.0, "charges": charges},
              {"name": "eR", "role": "standard_model", "spin": 0.5, "chirality": "R", "charges": charges},
              {"name": "muR", "role": "standard_model", "spin": 0.5, "chirality": "R", "charges": charges}]
    terms = [{"fields": [{"field": "Pl", "conjugate": True}, {"field": "chi", "conjugate": True}, {"field": sm}],
              "lorentz": "chiral", "coupling": "0.5", "plus_hc": True} for sm in ("eR", "muR")]
    engine, p = _engine(fields, terms)
    text, sigma, _ = engine.lhc_spectrum(p)
    branchings = [float(x) for x in re.findall(r"^\s+([0-9.E+-]+)\s+2\s+1000022", text, flags=re.M)]
    assert sigma and len(branchings) == 2 and sum(branchings) == pytest.approx(1.0, rel=1e-6)


def test_a_partners_decay_conserves_its_charge():
    """The audit's G9-7 (G12): a Y = −1 partner of charge +1 decays to χ e⁺ (−11), a 3̄ partner of charge −2/3 to
    χ ū (−2); a charge-−1 partner to χ e⁻ and a +2/3 one to χ u keep the particle's code."""
    from adroit.parameter_space.portals import generic_lhc
    assert [generic_lhc._conserving(11, q) for q in (1.0, -1.0)] == [-11, 11]
    assert [generic_lhc._conserving(2, q) for q in (-2 / 3, 2 / 3)] == [-2, 2]
    assert generic_lhc._conserving(12, 0.0) == 12
