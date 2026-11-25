"""OB-11 (the owner's repair of 2026-11-24): every standard-library model has a complete numerical benchmark as its
typed model, in its own notation, and that typed model is computed with the entry's own engine at the entry's own
point, or refused with a specific reason. ``parameter_space.benchmarks``, ``standard_binding``."""
import math

import numpy as np
import pytest

from adroit.library.personal import support
from adroit.parameter_space import library, standard_binding
from adroit.parameter_space.classify import Unsupported, classify, coupling_relations
from adroit.parameter_space.portals.higgs import HiggsPortalScalar
from adroit.parameter_space.portals.tchannel import TChannel

ENTRIES = library.ENTRIES
COMPUTED = [e for e in ENTRIES if not e.typed.unsupported]
FITTED = [e for e in COMPUTED if e.typed.fitted and not e.typed.no_recoil]


def _cases(entries):
    """The entries as test cases; a UFO model's engine reads its model from the tools folder (``needs``)."""
    from adroit.parameter_space.portals.ufo import UFOPortal
    return [pytest.param(e, id=e.id, marks=[pytest.mark.needs("ufo_models")] if isinstance(e.model_class, UFOPortal)
                         else []) for e in entries]
V = 246.22


def _with(spec, **values):
    """The typed model with some couplings' values replaced."""
    return spec.model_copy(update={"couplings": [c.model_copy(update={"value": values[c.name]}) if c.name in values
                                                 else c for c in spec.couplings]})


def _read_slots(engine) -> tuple[str, ...]:
    """The point slots an engine reads (the scalar Higgs portal and the t-channel portals read no g_q or g_ℓ)."""
    return ("m_chi", "m_med", "g_chi") if isinstance(engine, (HiggsPortalScalar, TChannel)) else \
        ("m_chi", "m_med", "g_chi", "g_q", "g_l")


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e.id)
def test_every_benchmark_is_complete_and_structurally_valid(entry) -> None:
    spec = entry.benchmark_spec()
    assert all(c.value is not None and math.isfinite(c.value) for c in spec.couplings), spec.couplings
    assert all(c.justification for c in spec.couplings)                    # each value says where it comes from
    found = support(spec)
    assert found["numerically_declared"] and found["structural_valid"] and not found["problems"]
    assert spec.name == entry.id


@pytest.mark.parametrize("entry", _cases(COMPUTED))
def test_the_typed_benchmark_runs_on_the_entrys_own_engine_at_its_point(entry) -> None:
    engine, point, _ = classify(entry.benchmark_spec())
    want = entry.model_class
    assert type(engine) is type(want)
    assert {k: v for k, v in engine.model_dump().items() if k != "name"} == \
        {k: v for k, v in want.model_dump().items() if k != "name"}
    for slot in _read_slots(want):
        assert getattr(point, slot) == pytest.approx(getattr(entry.point, slot), rel=1e-12, abs=1e-15), slot
    a, b = engine.interaction(point), want.interaction(entry.point)          # the same scattering, coefficient by coefficient
    assert [(c.operator, c.proton, c.neutron) for c in a.coefficients] == \
        pytest.approx([(c.operator, c.proton, c.neutron) for c in b.coefficients])


def test_the_inelastic_dark_photon_is_refused_with_what_it_needs() -> None:
    entry = library.entry("inelastic_dark_photon")
    with pytest.raises(Unsupported, match="inelastic.*elastic recoils only"):
        classify(entry.benchmark_spec())
    ready, why = standard_binding.availability(entry)
    assert not ready and "splitting" in why


@pytest.mark.parametrize("entry", _cases(FITTED))
def test_the_fitted_coupling_is_the_engines_fitted_slot(entry) -> None:
    """Doubling the typed coupling the fit varies doubles the engine's g_χ (or its tied form) and changes the
    scattering: the fit moves the intended physical coupling, never a placeholder."""
    spec = entry.benchmark_spec()
    name = entry.typed.fitted
    value = next(c.value for c in spec.couplings if c.name == name)
    _, p1, _ = classify(spec)
    engine, p2, _ = classify(_with(spec, **{name: 2 * value}))
    assert p2.g_chi == pytest.approx(2 * p1.g_chi)
    if engine.interaction(p1).coefficients:
        assert engine.interaction(p1).coefficients != engine.interaction(p2).coefficients


@pytest.mark.parametrize("entry_id, name", [("higgs_portal_dirac", "lam_hchi"), ("z_portal_axial", "g_A"),
                                            ("b_minus_l", "g_BL"), ("dmwg_A1", "g_DM"), ("two_hdm_a", "y_chi"),
                                            ("dark_photon_dirac", "eps"), ("alp_portal", "g_chi")])
def test_a_missing_value_is_refused_by_name(entry_id, name) -> None:
    spec = _with(library.entry(entry_id).benchmark_spec(), **{name: None})
    assert name in ", ".join(support(spec)["missing_parameters"])
    with pytest.raises(Unsupported):
        classify(spec)


def test_a_coupling_the_engine_holds_cannot_be_edited_silently() -> None:
    spec = library.entry("inert_doublet").benchmark_spec()
    with pytest.raises(Unsupported, match="holds lam2"):
        classify(_with(spec, lam2=0.1))
    spec = library.entry("two_hdm_a").benchmark_spec()
    with pytest.raises(Unsupported, match="holds M_A"):
        classify(_with(spec, M_A=1500.0))


def test_an_edited_lagrangian_is_not_read_as_the_entry() -> None:
    spec = library.entry("z_portal_axial").benchmark_spec()
    edited = spec.model_copy(update={"terms": [spec.terms[0].model_copy(update={"lorentz": "vector"})]})
    assert standard_binding.is_entry(spec) and not standard_binding.is_entry(edited)
    renamed = spec.model_copy(update={"name": "my_z_portal"})
    assert not standard_binding.is_entry(renamed)


@pytest.mark.parametrize("entry_id, coupling, factor", [("b_minus_l", "n_chi", 1 / 3), ("lmu_minus_ltau", "q_chi", 1.0)])
def test_the_gauge_relations_hold_as_the_fit_moves(entry_id, coupling, factor) -> None:
    """g_χ = n_χ g_BL (q_χ g′): the fit's g_χ moves the gauge coupling with it (``fit_inversion.tied``)."""
    from adroit.parameter_space.fit_inversion import tied
    spec = library.entry(entry_id).benchmark_spec()
    [relation] = coupling_relations(spec)
    assert (relation.derived, relation.source, relation.factor) == ("g_chi", "g_q", pytest.approx(factor))
    _, p, _ = classify(spec)
    moved = tied(p.model_copy(update={"g_chi": 0.02}), [relation])
    assert moved.g_q == pytest.approx(0.02 / factor) and moved.g_chi == pytest.approx(0.02)
    [half] = coupling_relations(_with(spec, **{coupling: 0.5}))      # an edited charge changes the tie
    assert half.factor == pytest.approx(0.5)


def test_the_published_a1_and_the_z_portal_axial_are_preserved() -> None:
    """The owner (2026-11-24): A1 as published (g_DM = 1), and the Z portal's axial benchmark (Dirac χ coupled axially
    to the Standard Model Z, m_χ = 500 GeV, g_A = 0.1), selectable without changing its physics: its engine is the
    library's ZPortal at the entry's own point."""
    a1 = library.entry("dmwg_A1").benchmark_spec()
    assert {c.name: c.value for c in a1.couplings} == {"g_DM": 1.0, "g_q": 0.25}
    assert "dmwg_A1_gdm01" not in library.BY_ID
    z = library.entry("z_portal_axial")
    spec = z.benchmark_spec()
    assert {c.name: c.value for c in spec.couplings} == {"g_A": 0.1} and spec.dark_matter.mass_gev == 500.0
    assert not spec.dark_matter.self_conjugate and [t.lorentz for t in spec.terms] == ["axial"]
    assert spec.field("Z").role.value == "standard_model"
    engine, point, _ = classify(spec)
    assert engine == z.model_class and point == z.point


def test_cms_a1_contours_apply_to_the_published_couplings_only() -> None:
    """The CMS A1 summary holds for g_DM = 1, g_q = 0.25, g_ℓ = 0 exactly (``verdicts.benchmark_of``); an A1 typed model
    with another g_DM is not called A1."""
    from adroit.constraints import spin1
    from adroit.constraints.verdicts import benchmark_of
    spec = library.entry("dmwg_A1").benchmark_spec()
    for g_dm, name in ((1.0, "A1"), (0.1, None)):
        _, p, _ = classify(_with(spec, g_DM=g_dm))
        model = spin1.Spin1Model(kind=spin1.Spin1Kind.axial, m_med_gev=p.m_med, g_dm=p.g_chi, g_q=p.g_q, g_l=p.g_l)
        assert benchmark_of(model) == name


def test_the_higgs_portals_now_carry_their_portal_term() -> None:
    """Before OB-11 the fermion and vector Higgs portals reached Explain a signal with no interaction at all (no Higgs
    field, no term), computed by the generic route as a free particle."""
    for entry_id in ("higgs_portal_dirac", "higgs_portal_dirac_cpv", "higgs_portal_majorana", "higgs_portal_vector"):
        spec = library.entry(entry_id).benchmark_spec()
        assert [f.name for f in spec.fields if f.role.value == "standard_model"] == ["H"] and len(spec.terms) == 1
        engine, _, _ = classify(spec)
        assert type(engine).__name__ != "GenericModel"


def test_the_inert_doublets_potential_gives_its_three_masses() -> None:
    """Hand check: the typed potential's λ₃, λ₄, λ₅ (formulas of λ₃₄₅ and the masses) give back M_H₀, M_A₀ and M_H±
    through M² = μ₂² + (…)v²/2, with μ₂² = M_H₀² − λ₃₄₅v²/2."""
    from adroit.library.interactions import derivation
    spec = library.entry("inert_doublet").benchmark_spec()
    table = derivation.symbol_table(spec)
    coefficient = [derivation.evaluate_expression(t.coupling, table) for t in spec.terms]
    lam3, lam4, lam5 = -coefficient[0], -coefficient[1], -2 * coefficient[2]
    m0, lam345 = spec.dark_matter.mass_gev, table["lam345"][0]
    mu2 = m0 ** 2 - lam345 * V ** 2 / 2
    assert lam3 + lam4 + lam5 == pytest.approx(lam345)
    assert math.sqrt(mu2 + lam3 * V ** 2 / 2) == pytest.approx(998.12)              # M_H±
    assert math.sqrt(mu2 + (lam3 + lam4 - lam5) * V ** 2 / 2) == pytest.approx(992.36)    # M_A₀
    assert math.sqrt(mu2 + lam345 * V ** 2 / 2) == pytest.approx(990.0)             # M_H₀


def test_the_singlet_mixing_potential_gives_its_angle_and_masses() -> None:
    """Hand check: the typed s|H|² coefficient C gives the (h, s) mass matrix's off-diagonal −C v; with the diagonal
    entries the potential's other parameters fix, its eigenvalues are m_h and m₂ and its angle is θ."""
    from adroit.library.interactions import derivation
    spec = library.entry("singlet_scalar_mixing").benchmark_spec()
    table = derivation.symbol_table(spec)
    c = derivation.evaluate_expression(spec.terms[1].coupling, table)
    theta, m1, m2 = table["theta"][0], 125.09, spec.field("S").mass_gev
    s, co = math.sin(theta), math.cos(theta)
    matrix = np.array([[m1 ** 2 * co ** 2 + m2 ** 2 * s ** 2, -c * V], [-c * V, m1 ** 2 * s ** 2 + m2 ** 2 * co ** 2]])
    values, vectors = np.linalg.eigh(matrix)
    assert np.sqrt(values) == pytest.approx([m1, m2])
    assert abs(vectors[1, 0]) == pytest.approx(s)                    # h₁ = cos θ h + sin θ s
    _, point, _ = classify(spec)
    assert point.g_q == pytest.approx(s) and point.m_med == m2


def test_the_normalisations_map_back_exactly() -> None:
    """The typed coefficients in L give the engines' parameters by the conventions the maps state: −½λ_hs S²H†H gives
    λ_hs; −(ε/2c_W) X_μνB^μν gives ε; a Majorana −½λ χ̄χH†H gives the Feynman-rule λ."""
    _, p, _ = classify(library.entry("higgs_portal_scalar").benchmark_spec())
    assert p.g_chi == pytest.approx(2.9e-4)
    _, p, _ = classify(library.entry("dark_photon_dirac").benchmark_spec())
    assert p.g_q == pytest.approx(1e-4, rel=1e-12) and p.g_chi == pytest.approx(math.sqrt(2 * math.pi))
    _, p, _ = classify(library.entry("higgs_portal_majorana").benchmark_spec())
    assert p.g_chi == pytest.approx(1e-3)


def test_the_dirac_5plet_keeps_its_splitting() -> None:
    """Its benchmark δm₀ = 0.22 MeV had been dropped (the n-plet map gives δm₀ = 0, "not stated")."""
    _, p, _ = classify(library.entry("quintuplet_dirac").benchmark_spec())
    assert p.g_q == pytest.approx(2.2e-4)


@pytest.mark.parametrize("entry_id", ["wino", "higgsino", "quintuplet", "quintuplet_dirac"])
def test_a_model_with_no_free_coupling_is_never_fitted(entry_id) -> None:
    engine, _, _ = classify(library.entry(entry_id).benchmark_spec())
    assert not standard_binding.free_coupling(engine) and library.entry(entry_id).typed.fitted is None


def test_the_lepton_portal_couples_to_the_muon() -> None:
    """Its typed form had coupled to e_R, while its engine is the μ_R portal."""
    spec = library.entry("lepton_portal_muR").benchmark_spec()
    engine, _, _ = classify(spec)
    assert engine.partner == "muR" and "muR" in [f.name for f in spec.fields]


def test_a_model_whose_engine_computes_no_recoil_is_not_offered_for_a_signal() -> None:
    """The CP-violating Higgs portal (O₁₁) and the μ_R lepton portal (loops) have no recoil spectrum in their engines:
    their fitted coupling would move nothing, so the signal pages name them instead of offering them."""
    from adroit.ui.model_library import STANDARD, standard_options, standard_unsupported
    for entry_id in ("higgs_portal_dirac_cpv", "lepton_portal_muR"):
        entry = library.entry(entry_id)
        engine, point, _ = classify(entry.benchmark_spec())          # still computed (Track 1 and its constraints)
        assert all(c.proton == c.neutron == 0 for c in engine.interaction(point).coefficients)
        assert entry.typed.no_recoil and STANDARD + entry_id not in standard_options("track1")
        assert entry.title in standard_unsupported()
    assert library.entry("inelastic_dark_photon").title in standard_unsupported()
