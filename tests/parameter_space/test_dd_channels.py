"""R2: every non-zero direct-detection channel is compared; none is dropped silently (audit M1, M13 and minors)."""

import math

import pytest

from adroit.parameter_space import dd_channels, limits, likelihood
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.portals.base import Nucleon, Portal
from adroit.physics import conventions

LZ, DEAP, PICO, CRESST = "LZ WS2022+WS2024", "DEAP-3600 (2019)", "PICO-60 C3F8 (2019)", "CRESST-III 2019"


@pytest.fixture
def module_limits(monkeypatch):
    """Synthetic per-module 95% limits, recorded with the modules each call left out."""
    table: dict[str, dict[str, float]] = {}
    calls = []

    def per_module95(kind, mass, excluded_modules=()):
        calls.append((kind, tuple(excluded_modules)))
        found = tuple((m, v) for m, v in table.get(kind, {}).items() if m not in excluded_modules)
        return found, ()
    limits.clear_cache()
    monkeypatch.setattr(limits, "per_module95", per_module95)
    yield table, calls
    monkeypatch.undo()
    limits.clear_cache()


class _Couplings(Portal):
    """A portal with fixed nucleon couplings."""

    c1_p: float = 0.0
    c1_n: float = 0.0
    c4_p: float = 0.0
    c4_n: float = 0.0

    def channels(self, s, p):
        return {}

    def nucleon(self, p):
        return Nucleon(c1_p=self.c1_p, c1_n=self.c1_n, c4_p=self.c4_p, c4_n=self.c4_n)


def test_the_audits_majorana_z_portal_is_pending_with_sd_neutron_named(module_limits) -> None:
    from adroit.parameter_space import scan
    from adroit.parameter_space.portals.vector import ZPortal
    table, _ = module_limits
    table["SD-proton"] = {PICO: 1.35e-40}                 # the audit's numbers; no validated SD-neutron at 300 GeV
    cls, p = ZPortal(coupling="axial", majorana=True), Point(m_chi=300.0, m_med=91.19, g_chi=0.01)
    n = cls.nucleon(p)
    assert n.c4_p < 0 < n.c4_n                            # c₄ᵖ ≈ −1.22e-6, c₄ⁿ ≈ +1.05e-6
    d = scan.direct_detection(cls, p)
    assert d.excluded is None and {c.kind for c in d.channels} == {"SD-proton", "SD-neutron"}
    assert any("SD-neutron" in reason and "no validated limit" in reason for reason in d.pending)
    factor = dd_channels.single_kind_factor(PICO, "SD-proton", 300.0, float(f"{n.c4_n / n.c4_p:.6g}"))
    assert 1.0 < factor < 1.06                            # fluorine's own rate ratio with the neutron coupling
    assert d.kind == "SD-proton" and d.ratio == pytest.approx(factor * conventions.sigma_sd_cm2(n.c4_p, 300.0) / 1.35e-40)


def test_a_pure_neutron_spin_dependent_model_is_pending(module_limits) -> None:
    from adroit.parameter_space import scan
    table, _ = module_limits
    table["SD-proton"] = {PICO: 1e-40}
    d = scan.direct_detection(_Couplings(c4_n=1e-6), Point(m_chi=300.0, m_med=1000.0))
    assert d.excluded is None and d.kind == "SD-neutron" and "SD-neutron" in d.pending[0]


def test_any_channel_that_exceeds_its_limit_excludes(module_limits) -> None:
    from adroit.parameter_space import scan
    table, _ = module_limits
    table["SD-proton"] = {PICO: 1e-45}                    # SD-proton excludes; SD-neutron has no limit
    d = scan.direct_detection(_Couplings(c4_p=1e-6, c4_n=1e-6), Point(m_chi=300.0, m_med=1000.0))
    assert d.excluded is True and d.kind == "SD-proton" and d.ratio > 1


@pytest.mark.needs("diamx")
def test_a_coupling_near_xenons_cancellation_keeps_its_isotopes(module_limits) -> None:
    """c_n/c_p = −0.7: xenon's isotopes leave it 1.3 × 10⁻⁴ of its rate (one Z/A per element had left 6 × 10⁻⁷, and
    argon had decided: the addendum's AL3-31); with these limits xenon decides, by its isotopes' weighted coupling."""
    table, _ = module_limits
    table["SI"] = {LZ: 1e-47, DEAP: 1e-45}
    c_p = 1e-8
    channel = dd_channels.channels_of(c_p, -0.7 * c_p, 0.0, 0.0, 100.0)
    result = dd_channels.compare(channel, 100.0).decisive
    def ratio(symbol: str, limit: float) -> float:
        return conventions.sigma_si_cm2(math.sqrt(dd_channels.element_coupling_squared(symbol, c_p, -0.7 * c_p, 100.0)),
                                        100.0) / limit
    xenon, argon = ratio("Xe", 1e-47), ratio("Ar", 1e-45)
    assert xenon > argon and dd_channels.element_coupling_squared("Xe", 1.0, -0.7, 100.0) == pytest.approx(1.32e-4, rel=0.05)
    assert result.limit.source == LZ and result.ratio == pytest.approx(xenon)


def test_a_private_si_limit_leaves_the_spin_dependent_comparisons_alone(module_limits) -> None:
    table, calls = module_limits
    table.update({"SI": {LZ: 1e-47, DEAP: 1e-45}, "SD-neutron": {LZ: 1e-41}})
    channels = dd_channels.channels_of(1e-9, 1e-9, 0.0, 1e-6, 50.0)
    dd_channels.compare(channels, 50.0, si_excluded_modules=(LZ,))
    assert ("SI", (LZ,)) in calls and ("SD-neutron", ()) in calls
    assert not any(kind.startswith("SD") and excluded for kind, excluded in calls)


def _si_limit_for_ratio(cls, p, ratio: float, table: dict) -> float:
    """The (xenon) SI limit that gives the central ratio ``ratio``: the compared σ is xenon's isoscalar equivalent."""
    table["SI"] = {LZ: 1.0}
    si = next(c for c in cls.dd_channels(p) if c.kind == "SI")
    return dd_channels.compare([si], p.m_chi).channels[0].ratio / ratio


@pytest.mark.needs("diamx")
def test_near_degeneracy_the_amplitude_uncertainty_decides(module_limits) -> None:
    """A coloured partner: the band [r(1 − δ)², r(1 + δ)²] from the propagator's expansion, δ = ε/(1 − ε); for a
    Majorana χ the twist-2 part's remainder is bounded by ⟨x²⟩/⟨x⟩ (2026-10-12), δ = w ε/(1 − ε)."""
    from adroit.constraints import loops
    from adroit.parameter_space import scan
    from adroit.parameter_space.portals.tchannel import TChannel, degeneracy
    table, _ = module_limits
    table["SD-proton"], table["SD-neutron"] = {PICO: 1.0}, {LZ: 1.0}
    cls = TChannel(partner="uR", majorana=True)
    close, far = Point(m_chi=200.0, m_med=205.0, g_chi=1.0), Point(m_chi=200.0, m_med=260.0, g_chi=1.0)
    eps, delta = degeneracy(200.0, 205.0)
    assert eps == pytest.approx(2 * 200.0 * 0.938918747 / (205.0 ** 2 - 200.0 ** 2)) and delta == pytest.approx(eps / (1 - eps))
    delta *= loops.coloured_partner_weight(200.0, 205.0, "u")
    table["SI"] = {LZ: _si_limit_for_ratio(cls, close, 1.0, table)}        # band ≈ 0.91–1.10: straddles
    d = scan.direct_detection(cls, close)
    assert d.excluded is None and any("straddles" in r and "near degeneracy" in r for r in d.pending)
    si = next(c for c in d.channels if c.kind == "SI")
    assert si.ratio_band == pytest.approx((1.0 * (1 - delta) ** 2, 1.0 * (1 + delta) ** 2))
    table["SI"] = {LZ: _si_limit_for_ratio(cls, close, 1.2, table)}        # under the x = 1 bound it straddled
    assert scan.direct_detection(cls, close).excluded is True
    table["SI"] = {LZ: _si_limit_for_ratio(cls, close, 2.4e4, table)}      # the Dirac benchmark's size: excluded
    assert scan.direct_detection(cls, close).excluded is True
    table["SI"] = {LZ: _si_limit_for_ratio(cls, far, 1.2, table)}          # far from degeneracy δ ≈ 1.6%: excluded
    assert scan.direct_detection(cls, far).excluded is True
    table["SI"] = {LZ: _si_limit_for_ratio(cls, close, 0.5, table)}        # band ≈ 0.30–0.76: allowed
    assert scan.direct_detection(cls, close).excluded is False


@pytest.mark.needs("diamx")
def test_where_the_expansion_fails_direct_detection_is_not_computed(module_limits) -> None:
    from adroit.parameter_space import scan
    from adroit.parameter_space.portals.tchannel import TChannel, degeneracy
    table, _ = module_limits
    table.update({"SI": {LZ: 1e-60}, "SD-proton": {PICO: 1.0}, "SD-neutron": {LZ: 1.0}})
    assert degeneracy(200.0, 200.5) is None
    d = scan.direct_detection(TChannel(partner="uR", majorana=True), Point(m_chi=200.0, m_med=200.5, g_chi=1.0))
    assert d.excluded is None and any("not computed here" in r and "on shell" in r for r in d.pending)
    assert d.ratio is None                       # never in the combined likelihood (the audit loop's AL1-01)
    lepton = scan.direct_detection(TChannel(partner="muR", majorana=False), Point(m_chi=200.0, m_med=200.5, g_chi=1.0))
    assert not any("on shell" in r for r in lepton.pending)          # lepton partners have no quark propagator


def test_the_axial_class_compares_both_spin_dependent_channels() -> None:
    from adroit.constraints import spin1
    kinds = [c.kind for c in Spin1Class(kind=spin1.Spin1Kind.axial).dd_channels(Point(m_chi=100.0, m_med=1000.0))]
    assert kinds == ["SD-proton", "SD-neutron"]
    assert [c.kind for c in Spin1Class().dd_channels(Point(m_chi=100.0, m_med=1000.0))] == ["SI"]


def test_an_edge_clause_mass_is_floored_at_the_published_curve() -> None:
    limits.clear_cache()
    floor = limits.edge_floor(PICO, "SD-proton", 3.02)
    assert floor is not None and floor > 0                # validated by the edge clause only
    assert limits.edge_floor(PICO, "SD-proton", 50.0) is None    # validated by the ratio rule


def test_sidedness_is_recorded_and_used_by_the_combination() -> None:
    assert limits.sidedness(LZ) == "two-sided" and limits.sidedness(PICO) == "one-sided"
    assert limits.sidedness("") == "unknown"
    one = likelihood.combined({"x": 1.0}, {}, sidedness={"x": "one-sided"})
    two = likelihood.combined({"x": 1.0}, {}, sidedness={"x": "two-sided"})
    assert one == pytest.approx(1.645 ** 2) and two == pytest.approx(1.959964 ** 2)
    assert likelihood.combined({"x": 1.0}, {}) == pytest.approx(one)          # saved results: one-sided as before
    with pytest.raises(ValueError, match="construction"):
        likelihood.combined({"x": 1.0}, {}, sidedness={"x": "unknown"})


def test_ratio_levels_come_from_each_limit_not_a_constant() -> None:
    from adroit.constraints.searches import Outcome
    from adroit.parameter_space import scan
    stats = {"direct detection": limits.StatisticalLimit(value=1.0, confidence_level=0.95, sidedness="two-sided",
                                                         construction="x")}
    found = [Outcome(name="a search", excluded=False, ratio=0.5, confidence_level=0.95)]
    assert scan._ratio_level("direct detection", stats, found) == 0.95
    assert scan._ratio_level("a search", stats, found) == 0.95
    assert scan._ratio_level("unknown", stats, found) is None
    assert scan._ratio_sidedness("direct detection", stats) == "two-sided"
    assert scan._ratio_sidedness("a search", stats) == "one-sided"


def test_the_reference_route_is_used_only_with_the_modules_own_conventions() -> None:
    from adroit.core.dm_state import HaloModel
    from adroit.orchestrator import exclusion
    used = []

    class Module:
        info = type("Info", (), {"name": "stub", "fidelity": type("F", (), {"value": "A"})()})()

        def reference_limits(self, kind, masses, workers=1, **kw):
            used.append("reference")
            return [1e-46 for _ in masses]

        def conventions(self):
            return type("C", (), {"halo": HaloModel(), "nuclear_model": None, "spin_dependent_model": None,
                                  "model_for": lambda self, kind: None})()

        def expected_signal(self, p, i, halo, nuclear):
            used.append(("direct", halo.v0_km_s))
            return type("S", (), {"total_events": 0.0})()

        def upper_limits(self, signals, cl=0.9):
            return []
    base = dict(card_id="O1", values={"c_p": 1e-8, "c_n": 1e-8}, masses_gev=[100.0])
    # a different halo (v0 220, not the module's 238) or spin: the direct route, which honours them
    for request in (exclusion.ExclusionRequest(**base, halo=HaloModel(v0_km_s=220.0)),
                    exclusion.ExclusionRequest(**base, spin=0.0)):
        used.clear()
        exclusion._module_limits(Module(), request, [100.0])
        assert used and "reference" not in used
    # none stated, the module's own stated explicitly, or only its label changed: the reference route (V1-02, RA-03)
    for request in (exclusion.ExclusionRequest(**base), exclusion.ExclusionRequest(**base, halo=HaloModel()),
                    exclusion.ExclusionRequest(**base, halo=HaloModel(label="the SHM, renamed"))):
        used.clear()
        exclusion._module_limits(Module(), request, [100.0])
        assert used == ["reference"]


def test_the_anapole_cards_description_has_the_sign_its_terms_give() -> None:
    from adroit.core.dm_state import DarkMatterParticle
    from adroit.library.interactions import registry
    card = registry.card("M_anapole")
    assert "[Q L13 + (Q + κ) L14]" in card.description
    c = {t.operator: t.proton for t in registry.resolve("M_anapole", DarkMatterParticle(mass_gev=100.0),
                                                         {"anapole": 1e-5}).coefficients}
    assert c[8] > 0 and c[9] > 0 and math.isclose(c[9] / c[8], 1 + 1.792847, rel_tol=1e-3)


def test_replay_compares_a_legacy_point_without_the_new_records() -> None:
    from adroit.evidence.replay import _legacy_direct_detection
    saved = {"dd_channels": [], "ratio_sidedness": {}, "excluded": {"direct detection": None}, "pending": [],
             "statistical_limits": {"direct detection": {"construction": "module procedure evaluated at CL=0.95",
                                                         "sidedness": "unknown"}}}
    now = {"dd_channels": [{"kind": "SI"}], "ratio_sidedness": {"direct detection": "two-sided"},
           "excluded": {"direct detection": None},
           "pending": ["direct detection (SD-neutron): no validated limit at m_χ = 300 GeV", "other"],
           "statistical_limits": {"direct detection": {"construction": "module procedure evaluated at CL=0.95 "
                                                       "(two-sided)", "sidedness": "two-sided"}}}
    left, right = dict(saved), dict(now)
    notes = _legacy_direct_detection(saved, left, right)
    assert len(notes) == 4 and "dd_channels" not in right and right["pending"] == ["other"]
    assert right["statistical_limits"] == saved["statistical_limits"]
    changed = dict(now, excluded={"direct detection": False})
    left, right = dict(saved), dict(changed)
    _legacy_direct_detection(saved, left, right)
    assert len(right["pending"]) == 2                    # a changed verdict keeps its new reason


def test_a_compound_target_brackets_an_isospin_violating_coupling(module_limits) -> None:
    """Mini audit: CaWO₄ was given Z/A = 0.5; at c_n = −c_p calcium and oxygen are nearly blind (their N = Z isotopes
    blind, the rest, a few per cent of them, not: AL3-31) but tungsten is not."""
    table, _ = module_limits
    c_p = 1e-8
    tungsten = conventions.sigma_si_cm2(math.sqrt(dd_channels.element_coupling_squared("W", c_p, -c_p, 100.0)), 100.0)
    table["SI"] = {CRESST: tungsten / 2.0}                           # tungsten alone would exceed by 2
    out = dd_channels.compare(dd_channels.channels_of(c_p, -c_p, 0.0, 0.0, 100.0), 100.0)
    (si,) = out.channels
    assert si.ratio_band[0] < 1e-2 and si.ratio_band[1] == pytest.approx(2.0)          # Ca, O near-blind; W exceeds
    assert out.excluded is None and "straddles" in out.pending[0]


@pytest.mark.needs("diamx")
def test_both_sd_couplings_bracket_their_interference_in_one_target(module_limits) -> None:
    """Mini audit: at the audit's own point XENONnT's SD-neutron ratio was 1.018 with c₄ᵖ/c₄ⁿ = −1.16; the
    proton coupling interferes in xenon, so Tovey's band [(√r_n − √r_p)², (√r_n + √r_p)²] straddles 1."""
    table, _ = module_limits
    xenon = "XENONnT SR0+SR1"
    c4_n = 1e-6
    sigma_n = conventions.sigma_sd_cm2(c4_n, 300.0)
    sigma_p = conventions.sigma_sd_cm2(-1.16 * c4_n, 300.0)
    table["SD-neutron"] = {xenon: sigma_n / 1.018}
    table["SD-proton"] = {xenon: sigma_p / 0.046}                     # xenon's proton limit is much weaker
    out = dd_channels.compare(dd_channels.channels_of(0.0, 0.0, -1.16 * c4_n, c4_n, 300.0), 300.0)
    low, high = out.channels[0].ratio_band
    assert low == pytest.approx((1.018 ** 0.5 - 0.046 ** 0.5) ** 2) and high == pytest.approx((1.018 ** 0.5 + 0.046 ** 0.5) ** 2)
    assert out.excluded is None and any("interference" in reason for reason in out.pending)
    table["SD-neutron"] = {xenon: sigma_n / 5.0}                      # far above the limit: excluded even so
    assert dd_channels.compare(dd_channels.channels_of(0.0, 0.0, -1.16 * c4_n, c4_n, 300.0), 300.0).excluded is True


def test_the_twist2_remainder_is_bounded_by_the_quark_moments():
    """The owner (2026-10-12): a quick bound instead of the full resummation; ⟨x²⟩/⟨x⟩ < 1 tightens ε/(1 − ε)."""
    from adroit.constraints import loops
    from adroit.parameter_space.portals.tchannel import degeneracy
    assert loops.TWIST2_RATIO["u"] == 0.183 and all(0 < r < 1 for r in loops.TWIST2_RATIO.values())
    for gap, upper in ((10.0, 0.025), (2.0, 0.2)):
        eps, delta = degeneracy(1000.0, 1000.0 + gap)
        w = loops.coloured_partner_weight(1000.0, 1000.0 + gap, "u")
        assert 0.18 < w < 0.25 and w * delta < upper < delta
    assert loops.coloured_partner_weight(1000.0, 1010.0, "b") > loops.coloured_partner_weight(1000.0, 1010.0, "u")
    f_p, f_n = loops.coloured_partner_si(1000.0, 1010.0, 1.0, "u")
    assert f_p > f_n > 0                                         # unchanged by the refactoring: u is more in protons


def test_a_majorana_partner_carries_the_tighter_band_and_a_dirac_one_the_old():
    from adroit.parameter_space.library import entry
    for name, factor in (("tchannel_uR_majorana", 0.25), ("tchannel_uR_dirac", 1.0)):
        e = entry(name)
        p = e.point.model_copy(update={"m_med": e.point.m_chi + 10.0})
        notes = " ".join(c.uncertainty_note for c in e.model_class.dd_channels(p))
        assert ("⟨x²⟩/⟨x⟩" in notes) == (factor < 1)


@pytest.mark.needs("cdmslite")
def test_a_module_validated_for_one_sd_kind_scales_by_its_own_rate_ratio(module_limits) -> None:
    """The owner (2026-10-12): CDMSlite publishes a neutron limit only, so a model with both SD couplings has its
    ratio scaled by germanium's own rate ratio, rate(c₄ᵖ, c₄ⁿ)/rate(c₄ⁿ alone): constructive above 1, destructive
    below, and 1 with no proton coupling."""
    table, _ = module_limits
    cdms, mass, c4_n = "CDMSlite Run 2", 5.0, 1e-4
    same = dd_channels.single_kind_factor(cdms, "SD-neutron", mass, 1.0)
    opposite = dd_channels.single_kind_factor(cdms, "SD-neutron", mass, -1.0)
    assert same > 1.2 and opposite < 0.8 and dd_channels.single_kind_factor(cdms, "SD-neutron", mass, 0.0) == pytest.approx(1.0)
    pico = dd_channels.single_kind_factor("PICO-60 C3F8 (2019)", "SD-proton", 50.0, 1.0)
    assert 0.9 < pico < 1.0                                           # fluorine: a few percent
    sigma_n = conventions.sigma_sd_cm2(c4_n, mass)
    table["SD-neutron"] = {cdms: sigma_n / 0.9}                       # alone: allowed (r = 0.9)
    table["SD-proton"] = {}
    for sign, excluded in ((1.0, True), (-1.0, False)):
        out = dd_channels.compare(dd_channels.channels_of(0.0, 0.0, sign * c4_n, c4_n, mass), mass)
        sd_n = next(c for c in out.channels if c.kind == "SD-neutron")
        assert sd_n.ratio == pytest.approx(0.9 * (same if sign > 0 else opposite))
        assert (out.excluded is True) == excluded


@pytest.mark.needs("cresst")
def test_a_maximum_gap_limit_excludes_but_never_allows(monkeypatch):
    """The fallback review's D1 (the owner's decision, 2026-10-20): without Yellin's optimum-interval code an interval
    search's limit is the maximum gap's, never stronger (CDMS II Si's at 10 GeV had been 1.94 times weaker, named only
    in the module's statistical method). Its exclusions stand; a point it would allow is undecided, the method named."""
    from adroit.statistics import optimum_interval
    monkeypatch.setattr(optimum_interval, "available", lambda: False)
    monkeypatch.setattr(limits, "eligible", lambda kind, mass, excluded_modules=(): [CRESST])
    limits.clear_cache()
    try:
        found, omitted = limits.per_module95("SI", 5.0)
        ((name, value),) = found
        assert name == CRESST and dict(omitted)[CRESST] == limits.MAXIMUM_GAP_FALLBACK
        above = dd_channels.compare([dd_channels.Channel(kind="SI", sigma_cm2=3.0 * value)], 5.0)
        below = dd_channels.compare([dd_channels.Channel(kind="SI", sigma_cm2=value / 3.0)], 5.0)
        assert above.excluded is True
        assert below.excluded is None and any("maximum gap" in reason for reason in below.pending)
    finally:
        monkeypatch.undo()
        limits.clear_cache()
    assert limits.fallback(CRESST) == ""                       # with the code: the optimum interval, no fallback


@pytest.mark.needs("cresst")
def test_a_maximum_gap_limit_through_path_1_never_allows_either(monkeypatch):
    """C21-04 (the candidate audit, 2026-10-21): D1 reaches the limits set through Path 1's rows too, which carry the
    method (``ModuleLimits.excludes_only``): a flavour-vector current's amplitude limit and an operator structure's
    exclude above them and are undecided below them, the method named; the signal workflow's null coverage with such
    a limit is partial, never complete."""
    from adroit.core.model_contracts import VECTOR_FLAVOURS
    from adroit.experiments import registry
    from adroit.orchestrator import signal
    from adroit.parameter_space import flavour_limits, operator_limits, scan
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.flavour_vector import FlavourVectorClass
    from adroit.statistics import optimum_interval
    monkeypatch.setattr(optimum_interval, "available", lambda: False)
    monkeypatch.setattr(registry, "module_names", lambda: [CRESST])
    for cache in (flavour_limits.limit95, operator_limits.limit95):
        cache.cache_clear()
    limits.clear_cache()
    try:
        u_only = FlavourVectorClass(flavour_couplings={n: 1.0 if n == "u" else 0.0 for n in VECTOR_FLAVOURS})
        unit = flavour_limits.limit95(5.0, 100.0, 2.0, 1.0)
        assert unit.omitted[CRESST] == limits.MAXIMUM_GAP_FALLBACK
        below = scan.direct_detection(u_only, Point(m_chi=5.0, m_med=100.0, g_chi=unit.value / 4, g_q=0, g_l=0))
        above = scan.direct_detection(u_only, Point(m_chi=5.0, m_med=100.0, g_chi=unit.value * 4, g_q=0, g_l=0))
        assert below.dd_ratio == pytest.approx(1 / 16) and below.excluded is None
        assert any("maximum gap" in reason for reason in below.pending)
        assert above.excluded is True
        candidate = signal.Candidate(label="O1s@5", card_id="O1", isospin="s", mass_gev=5.0)
        result = signal.combine(signal.SignalRequest(experiment="CDMS II Si (2013)", null_modules=[CRESST]), candidate)
        assert result.null_limits[CRESST] > 0 and result.null_coverage == "partial"
        assert result.omitted_nulls[CRESST] == limits.MAXIMUM_GAP_FALLBACK and CRESST not in result.insensitive_nulls
    finally:
        monkeypatch.undo()
        for cache in (flavour_limits.limit95, operator_limits.limit95):
            cache.cache_clear()
        limits.clear_cache()


def test_an_operator_structures_limit_keeps_the_fallback_of_its_rows(monkeypatch):
    """C21-04's operator path: ``operator_limits.limit95`` takes the strongest of Path 1's rows; a row whose module fell
    back to the maximum gap stays named in ``omitted``, so the scan's comparison below it is undecided."""
    from types import SimpleNamespace
    from adroit.experiments import registry
    from adroit.orchestrator import exclusion
    from adroit.parameter_space import operator_limits
    row = exclusion.ModuleLimits(experiment=CRESST, masses_gev=[5.0], mu_up=[2.0], validated=[True], route="direct",
                                 fidelity="B", excludes_only=limits.MAXIMUM_GAP_FALLBACK)
    monkeypatch.setattr(registry, "module_names", lambda: [CRESST])
    monkeypatch.setattr(exclusion, "_validated", lambda name, kind, mass: True)
    monkeypatch.setattr(exclusion, "run", lambda request: SimpleNamespace(per_module=[row], skipped={}))
    operator_limits.limit95.cache_clear()
    try:
        found = operator_limits.limit95("anapole", 5.0)
        assert found.value == 2.0 and found.omitted == {CRESST: limits.MAXIMUM_GAP_FALLBACK}
        assert limits.excludes_only(found)
        assert row.model_dump().get("excludes_only") and "excludes_only" not in row.model_copy(
            update={"excludes_only": ""}).model_dump()                  # absent from the serialised form when empty
    finally:
        monkeypatch.undo()
        operator_limits.limit95.cache_clear()


@pytest.mark.needs("cresst")
def test_revalidation_keeps_a_dominant_contact_parts_validation(monkeypatch):
    """RB-04 (the recheck): CRESST-III's flavour-vector limit at 5 GeV is validated by its dominant contact O1 part;
    after a JSON round trip, revalidation had judged only the full structure (O1, O3, O4, O5, O6) and lost it. Now the
    saved basis is judged again against the status files, with no new physics: unchanged status, still validated."""
    from adroit.core.dm_state import DarkMatterParticle
    from adroit.experiments import registry
    from adroit.orchestrator import exclusion
    from adroit.library.interactions import registry as cards
    monkeypatch.setattr(registry, "module_names", lambda: [CRESST])
    particle = DarkMatterParticle(mass_gev=5.0)
    interaction = cards.resolve("M_vector", particle, {"g_chi": 1.0, "m_med": 100.0, "gV_p": 2.0, "gV_n": 1.0})
    request = exclusion.ExclusionRequest(bespoke={repr(5.0): interaction}, masses_gev=[5.0], modules=[CRESST],
                                         telescopes=False, confidence_level=0.95, workers=1)
    result = exclusion.run(request)
    [row] = result.per_module
    again = exclusion.revalidate(type(result).model_validate_json(result.model_dump_json()))
    assert row.validated == [True] and again.per_module[0].validated == [True]
    assert row.validation_basis[repr(5.0)]["part"] == "contact"
    expected_signals = []
    monkeypatch.setattr(type(registry.load_module(CRESST)), "expected_signal",
                        lambda *a, **k: expected_signals.append(a))
    exclusion.revalidate(result)
    assert not expected_signals                          # revalidation computes no physics
