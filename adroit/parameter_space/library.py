"""The portal library: benchmark models of thermal dark matter, each runnable as a Track 1 study.

Each entry names a model from the literature and holds:
- its computable class (``portals`` or DM13's ``classes``) and benchmark point;
- the parameter plane the literature plots, with any fixed mass ratio;
- the Lagrangian;
- the references, every one opened on arXiv when the library was built
  (2026-10-03; the literature survey in docs/portal_library.md);
- the literature's statement of the result, to compare with;
- what is computed and what is not.

``adroit portals`` lists the entries, and ``adroit track1 --portal ID`` runs one.
Benchmarks quoted from papers that predate LZ (2022–2024) are starting points, not claims
of viability.
"""

from __future__ import annotations

import math

from pydantic import Field

from adroit.constraints import higgs as _higgs
from adroit.constraints import spin1
from adroit.core.model_spec import ModelSpec
from adroit.core.state import StrictModel
from adroit.parameter_space.classes import Point, ScalarClass, Spin1Class
from adroit.parameter_space.portals.higgs import HiggsPortalFermion, HiggsPortalScalar, HiggsPortalVector, SingletMixing
from adroit.parameter_space.portals.multiplet import ElectroweakMultiplet
from adroit.parameter_space.portals.nplet import ElectroweakNplet
from adroit.parameter_space.portals.tchannel import TChannel
from adroit.parameter_space.portals.ufo import UFOPortal
from adroit.parameter_space.portals.vector import ChargedZPrime, DarkPhoton, InelasticDarkPhoton, ZPortal
from adroit.parameter_space.relations import CouplingRelation
from adroit.parameter_space.scan import Axis, ModelClass

ALPHA_D_HALF = math.sqrt(4.0 * math.pi * 0.5)      # g_D for α_D = 0.5
ALPHA_D_TENTH = math.sqrt(4.0 * math.pi * 0.1)     # g_D for α_D = 0.1


class Entry(StrictModel):
    """One portal-library entry: the computable class and benchmark point, the literature's plane, the Lagrangian,
    the references, and what is and is not computed."""
    id: str
    title: str
    family: str                                    # Higgs portal, vector portal, pseudoscalar portal, t-channel, ...
    model_class: ModelClass
    point: Point
    x: Axis
    y: Axis
    mediator_ratio: float | None = None
    coupling_relations: list[CouplingRelation] = Field(default_factory=list)   # couplings the model ties (M9)
    dark_matter: str
    lagrangian: str
    parameters: str                                # what the slots mean
    benchmark: str
    references: list[str] = Field(default_factory=list)
    literature: str = ""                           # the literature's statement of the result
    not_computed: list[str] = Field(default_factory=list)
    fields: list[dict] = Field(default_factory=list)
    phase: str = "unbroken"
    terms: list[dict] = Field(default_factory=list)  # for a model written below electroweak breaking
    yukawa: str = "sm"                               # its spec's Yukawa convention (``model_building.yukawa``)

    def spec(self) -> ModelSpec:
        """The typed model: DM12's most general Lagrangian of the fields, or the terms as written."""
        point_masses = {"dark_matter": self.point.m_chi, "mediator": self.point.m_med}
        fields = [{**f, "mass_gev": point_masses.get(f.get("role"))} if f.get("role") in point_masses else f
                  for f in self.fields]
        if self.phase == "unbroken" and not self.terms:
            from adroit.orchestrator.ideas import from_fields
            spec = ModelSpec.model_validate({"name": self.id, "phase": "unbroken", "fields": fields,
                                             "yukawa": self.yukawa})
            return from_fields(spec).general.model_copy(update={"name": self.id, "yukawa": self.yukawa})
        couplings = sorted({c for t in self.terms for c in _symbols(t["coupling"])})
        return ModelSpec.model_validate({"name": self.id, "phase": self.phase, "fields": fields, "terms": self.terms,
                                         "couplings": [{"name": c} for c in couplings], "yukawa": self.yukawa})

    @property
    def typed(self):
        """The entry's complete typed benchmark (``benchmarks.TYPED``)."""
        from adroit.parameter_space.benchmarks import TYPED
        return TYPED[self.id]

    def benchmark_spec(self) -> ModelSpec:
        """The typed model at the benchmark, complete: every coupling given its value and why, in the model's own
        notation, with the benchmark's assumptions stated (OB-11). What the model library shows and Explain a signal
        and Signal best fits run. ``spec`` (the field content, read by the generic route's gates) is unchanged."""
        typed = self.typed
        point_masses = {"dark_matter": self.point.m_chi, "mediator": self.point.m_med}
        fields = [{**f, "mass_gev": point_masses[f["role"]]} if f.get("role") in point_masses else f
                  for f in (typed.fields if typed.fields is not None else self.fields)]
        base = self.spec() if typed.terms is None and typed.fields is None else None
        terms = typed.terms if typed.terms is not None else ([t.model_dump(mode="json") for t in base.terms]
                                                             if base is not None else self.terms)
        phase = typed.phase or self.phase
        if base is not None:
            fields = [f.model_dump(mode="json") for f in base.fields]
        fit = {"physical_fit": {"low": typed.fit_range[0], "high": typed.fit_range[1]}} if typed.fit_range else {}
        return ModelSpec.model_validate({"name": self.id, "phase": phase, "fields": fields, "terms": terms,
                                         "couplings": typed.couplings, "yukawa": self.yukawa,
                                         "assumptions": typed.assumptions, **fit})


def _symbols(expression: str) -> list[str]:
    import re
    known = {"m_q", "m_l", "v", "e", "pi", "sqrt"}
    return [w for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", expression) if w not in known]


def _axis(parameter: str, low: float, high: float, n: int = 20, log: bool = True) -> Axis:
    return Axis(parameter=parameter, low=low, high=high, n=n, log=log)


DM_FERMION = {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1}
DM_MAJORANA = {**DM_FERMION, "self_conjugate": True}

ENTRIES: list[Entry] = [
    # --- Higgs portals ---------------------------------------------------------------------------------
    Entry(id="higgs_portal_scalar", title="Real scalar singlet (Higgs portal)", family="Higgs portal",
          model_class=HiggsPortalScalar(name="scalar singlet"),
          point=Point(m_chi=62.27, m_med=125.09, g_chi=2.9e-4),
          x=_axis("m_chi", 10.0, 10000.0), y=_axis("g_chi", 1e-5, 10.0), dark_matter="real scalar S (Z2-odd)",
          lagrangian="V ⊃ ½ μ_S² S² + ½ λ_hs S² H†H + ¼ λ_S S⁴",
          parameters="m_χ = m_S; g_χ = λ_hs",
          benchmark="GAMBIT's best fit with the full relic density: λ_hs = 2.9×10⁻⁴, m_S = 62.27 GeV; and at high mass "
                    "λ_hs = 3.1, m_S = 9.79 TeV (arXiv:1705.07931, sec. 4.3)",
          references=["arXiv:1705.07931 (GAMBIT, Status of the scalar singlet dark matter model)",
                      "arXiv:1306.4710 (Cline et al., Update on scalar singlet dark matter)",
                      "arXiv:hep-ph/0702143 (McDonald, Gauge singlet scalars as cold dark matter)",
                      "arXiv:2410.21089 (Yu et al., New constraints on singlet scalar dark matter ...)"],
          literature="GAMBIT: viable at the resonance m_S ≈ m_h/2 and, as all of the dark matter, above ~1 TeV; "
                     "Yu et al. (with LZ): the region m_S > 110 GeV is excluded below 1 TeV",
          fields=[{"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True, "dark_parity": -1}]),
    Entry(id="higgs_portal_dirac", title="Dirac fermion Higgs portal (CP-conserving)", family="Higgs portal",
          model_class=HiggsPortalFermion(name="Dirac Higgs portal", xi=0.0),
          point=Point(m_chi=500.0, m_med=125.09, g_chi=1e-3),
          x=_axis("m_chi", 10.0, 10000.0), y=_axis("g_chi", 1e-6, 1.0), dark_matter="Dirac fermion χ (Z2-odd)",
          lagrangian="L ⊃ −(λ_hχ/Λ) χ̄(cos ξ + i sin ξ γ⁵)χ H†H, ξ = 0",
          parameters="m_χ; g_χ = λ_hχ/Λ (GeV⁻¹); the EFT holds for g_χ·2m_χ < 4π",
          benchmark="GAMBIT's fermion Higgs portal (arXiv:1808.10465), CP-conserving",
          references=["arXiv:1808.10465 (GAMBIT, Global analyses of Higgs portal singlet dark matter models)",
                      "arXiv:1404.2283 (Fedderke et al., The fermionic dark matter Higgs portal)",
                      "arXiv:1609.09079 (Escudero et al., Toward (finally!) ruling out Z and Higgs mediated DM)"],
          literature="Escudero et al.: with a scalar (CP-conserving) coupling the fermion Higgs portal is excluded",
          fields=[DM_FERMION]),
    Entry(id="higgs_portal_dirac_cpv", title="Dirac fermion Higgs portal (pseudoscalar, maximal CP violation)",
          family="Higgs portal", model_class=HiggsPortalFermion(name="Dirac Higgs portal, ξ = π/2", xi=math.pi / 2),
          point=Point(m_chi=500.0, m_med=125.09, g_chi=1e-3),
          x=_axis("m_chi", 10.0, 10000.0), y=_axis("g_chi", 1e-6, 1.0), dark_matter="Dirac fermion χ (Z2-odd)",
          lagrangian="L ⊃ −(λ_hχ/Λ) χ̄ iγ⁵ χ H†H (ξ = π/2)",
          parameters="m_χ; g_χ = λ_hχ/Λ (GeV⁻¹)",
          benchmark="GAMBIT (arXiv:1808.10465): CP violation preferred about 100:1, since direct detection is then "
                    "momentum-suppressed",
          references=["arXiv:1808.10465 (GAMBIT)", "arXiv:1609.09079 (Escudero et al.)"],
          literature="Escudero et al.: a fermion with a pseudoscalar (CP-violating) Higgs coupling is not excluded",
          fields=[DM_FERMION]),
    Entry(id="higgs_portal_majorana", title="Majorana fermion Higgs portal (CP-conserving)", family="Higgs portal",
          model_class=HiggsPortalFermion(name="Majorana Higgs portal", majorana=True),
          point=Point(m_chi=500.0, m_med=125.09, g_chi=1e-3),
          x=_axis("m_chi", 10.0, 10000.0), y=_axis("g_chi", 1e-6, 1.0), dark_matter="Majorana fermion χ",
          lagrangian="L ⊃ −½ (λ_hχ/Λ) χ̄χ H†H",
          parameters="m_χ; g_χ = λ_hχ/Λ (GeV⁻¹), the Feynman-rule coupling (the ½ of a Majorana field included)",
          benchmark="GAMBIT (arXiv:1808.10465), Majorana case",
          references=["arXiv:1808.10465 (GAMBIT)"], fields=[DM_MAJORANA]),
    Entry(id="higgs_portal_vector", title="Vector dark matter (Higgs portal)", family="Higgs portal",
          model_class=HiggsPortalVector(name="vector Higgs portal"),
          point=Point(m_chi=1000.0, m_med=125.09, g_chi=0.5),
          x=_axis("m_chi", 10.0, 10000.0), y=_axis("g_chi", 1e-5, 10.0), dark_matter="real vector V_μ (Z2-odd)",
          lagrangian="L ⊃ ½ μ_V² V_μV^μ + ½ λ_hV V_μV^μ H†H",
          parameters="m_χ = m_V; g_χ = λ_hV (GAMBIT requires λ_hV < 10)",
          benchmark="GAMBIT (arXiv:1808.10465), the vector Higgs portal",
          references=["arXiv:1808.10465 (GAMBIT)", "arXiv:1609.09079 (Escudero et al.)"],
          literature="Escudero et al.: a vector heavier than 1160 GeV with a Higgs-portal coupling is not excluded",
          phase="broken", terms=[],
          fields=[{"name": "V", "role": "dark_matter", "spin": 1, "self_conjugate": True, "dark_parity": -1},
                  {"name": "h", "role": "standard_model", "spin": 0, "self_conjugate": True}]),
    Entry(id="singlet_scalar_mixing", title="Singlet fermion with a scalar mediator mixing with the Higgs",
          family="Higgs portal", model_class=SingletMixing(name="singlet mixing"),
          point=Point(m_chi=100.0, m_med=500.0, g_chi=1.0, g_q=math.sin(0.2)),
          x=_axis("m_med", 10.0, 5000.0), y=_axis("m_chi", 10.0, 2000.0), dark_matter="Dirac fermion χ",
          lagrangian="L ⊃ −y χ̄χ s − μ s |H|² − ...; h₁ = cos θ h + sin θ s, h₂ = −sin θ h + cos θ s",
          parameters="m_χ; m_med = m₂; g_χ = y; g_q = sin θ",
          benchmark="Albert et al. (arXiv:1607.06680, sec. 2): θ = 0.2 with y = 1; scenario A has m₂ > 2m_χ > m₁",
          references=["arXiv:0803.2932 (Kim, Lee & Shin, Singlet fermionic dark matter)",
                      "arXiv:1112.1847 (Baek, Ko & Park)",
                      "arXiv:1607.06680 (Albert et al., Towards the next generation of simplified DM models)",
                      "arXiv:2601.13147 (Das et al., Revisiting singlet fermion dark matter with a scalar portal)"],
          literature="Das et al.: Higgs signal strengths give sin θ ≲ 0.24 (95% CL), independent of m₂",
          not_computed=["the scalar potential's trilinear couplings (set to zero)"],
          fields=[DM_FERMION, {"name": "s", "role": "mediator", "spin": 0, "self_conjugate": True}]),
    # --- vector portals --------------------------------------------------------------------------------
    Entry(id="dark_photon_dirac", title="Dirac fermion with a dark photon", family="vector portal",
          model_class=DarkPhoton(name="dark photon, Dirac"),
          point=Point(m_chi=10.0, m_med=30.0, g_chi=ALPHA_D_HALF, g_q=1e-4),
          x=_axis("m_chi", 1.0, 300.0), y=_axis("g_q", 1e-7, 0.1), mediator_ratio=3.0,
          dark_matter="Dirac fermion χ, charge 1 under the dark U(1)",
          lagrangian="L ⊃ −(ε/2c_W) B_μν X^μν + ½ m_A′² X_μX^μ + g_D X_μ χ̄γ^μχ",
          parameters="m_χ; m_med = m_A′ (= 3m_χ in the plane); g_χ = g_D (α_D = 0.5); g_q = ε",
          benchmark="the thermal-target convention m_A′ = 3m_χ, α_D = 0.5 (arXiv:1505.00011; 2207.00597; 1707.04591)",
          references=["arXiv:1505.00011 (Izaguirre, Krnjaic, Schuster & Toro)",
                      "arXiv:2207.00597 (Snowmass: dark matter production at intensity-frontier experiments)",
                      "arXiv:1707.04591 (US Cosmic Visions)", "arXiv:1712.03974 (Evans, Gori & Shelton, "
                                                                 "Looking for the WIMP next door)"],
          literature="Izaguirre et al.: Dirac fermion thermal-relic dark matter (sub-GeV) is excluded by the CMB; "
                     "Evans et al.: s-wave WIMPs next door below ~10 GeV are excluded by the CMB",
          not_computed=["above m_A′ = 200 GeV, the LHC's dilepton and electroweak-precision limits on the A′: not yet records, so undecided there"],
          fields=[{**DM_FERMION, "charges": {"extra": {"Xd": 1.0}}},
                  {"name": "Xd", "role": "mediator", "spin": 1, "self_conjugate": True}]),
    Entry(id="dark_photon_scalar", title="Complex scalar with a dark photon", family="vector portal",
          model_class=DarkPhoton(name="dark photon, complex scalar", scalar_dm=True),
          point=Point(m_chi=10.0, m_med=30.0, g_chi=ALPHA_D_HALF, g_q=1e-4),
          x=_axis("m_chi", 1.0, 300.0), y=_axis("g_q", 1e-7, 0.1), mediator_ratio=3.0,
          dark_matter="complex scalar φ, charge 1 under the dark U(1)",
          lagrangian="L ⊃ |D_μφ|² with D = ∂ + i g_D X, kinetic mixing ε",
          parameters="m_χ = m_φ; m_med = m_A′ (= 3m_χ); g_χ = g_D (α_D = 0.5); g_q = ε",
          benchmark="m_A′ = 3m_χ, α_D = 0.5 (arXiv:2207.00597): annihilation is p-wave, so the CMB does not bound it",
          references=["arXiv:2207.00597 (Snowmass)", "arXiv:1505.00011 (Izaguirre et al.)"],
          not_computed=["above m_A′ = 200 GeV, the LHC's dilepton and electroweak-precision limits on the A′: not yet records, so undecided there"],
          fields=[{"name": "phi", "role": "dark_matter", "spin": 0, "dark_parity": -1,
                   "charges": {"extra": {"Xd": 1.0}}},
                  {"name": "Xd", "role": "mediator", "spin": 1, "self_conjugate": True}]),
    Entry(id="inelastic_dark_photon", title="Inelastic (pseudo-Dirac) dark matter with a dark photon",
          family="vector portal", model_class=InelasticDarkPhoton(name="inelastic dark photon"),
          point=Point(m_chi=5.0, m_med=15.0, g_chi=ALPHA_D_TENTH, g_q=1e-3, g_l=0.1),
          x=_axis("m_chi", 1.0, 100.0), y=_axis("g_q", 1e-6, 0.1), mediator_ratio=3.0,
          dark_matter="pseudo-Dirac pair χ₁, χ₂ = χ₁(1 + Δ)", lagrangian="L ⊃ g_D X_μ χ̄₂γ^μχ₁ + h.c., kinetic mixing ε",
          parameters="m_χ = m₁; m_med = m_A′ (= 3m₁); g_χ = g_D (α_D = 0.1); g_q = ε; g_ℓ = Δ = 0.1",
          benchmark="m_A′ = 3m₁, Δ = 0.1, α_D = 0.1 (arXiv:1508.03050 Fig. 2; 1810.01879 Fig. 3 with ε = 10⁻³)",
          references=["arXiv:1508.03050 (Izaguirre, Krnjaic & Shuve)", "arXiv:1810.01879 (Berlin & Kling)",
                      "arXiv:hep-ph/0101138 (Tucker-Smith & Weiner, Inelastic dark matter)"],
          literature="Izaguirre et al.: thermal scenarios with larger masses or splittings are largely ruled out",
          not_computed=["displaced-vertex and long-lived-particle searches", "direct detection (inelastic: Path 1)"],
          fields=[{**DM_FERMION, "charges": {"extra": {"Xd": 1.0}}},
                  {"name": "Xd", "role": "mediator", "spin": 1, "self_conjugate": True}]),
    Entry(id="z_portal_vector", title="Dirac fermion coupling to the Z (vector)", family="vector portal",
          model_class=ZPortal(name="Z portal, vector"), point=Point(m_chi=45.0, m_med=91.19, g_chi=0.01),
          x=_axis("m_chi", 1.0, 10000.0), y=_axis("g_chi", 1e-5, 1.0), dark_matter="Dirac fermion χ",
          lagrangian="L ⊃ −Z_μ χ̄γ^μ(g_V + g_A γ⁵)χ, g_A = 0", parameters="m_χ; g_χ = g_V",
          benchmark="Escudero et al. (arXiv:1609.09079), the Z portal; Arcadi, Mambrini & Richard (arXiv:1411.2985)",
          references=["arXiv:1411.2985 (Arcadi, Mambrini & Richard, Z-portal dark matter)",
                      "arXiv:1609.09079 (Escudero et al.)"],
          literature="Escudero et al.: a vector coupling survives only with m_DM > 6 TeV",
          not_computed=["the growth of χχ̄ → W⁺W⁻ with energy (no gauge completion) is kept as is"],
          phase="broken", fields=[DM_FERMION, {"name": "Z", "role": "standard_model", "spin": 1, "self_conjugate": True}],
          terms=[{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Z"}],
                  "lorentz": "vector", "coupling": "g_V"}]),
    Entry(id="z_portal_axial", title="Dirac fermion coupling to the Z (axial)", family="vector portal",
          model_class=ZPortal(name="Z portal, axial", coupling="axial"), point=Point(m_chi=500.0, m_med=91.19, g_chi=0.1),
          x=_axis("m_chi", 1.0, 10000.0), y=_axis("g_chi", 1e-5, 1.0), dark_matter="Dirac fermion χ",
          lagrangian="L ⊃ −Z_μ χ̄γ^μγ⁵χ g_A", parameters="m_χ; g_χ = g_A",
          benchmark="Escudero et al. (arXiv:1609.09079)",
          references=["arXiv:1411.2985 (Arcadi et al.)", "arXiv:1609.09079 (Escudero et al.)"],
          literature="Escudero et al.: an axial coupling survives within a few GeV of m_Z/2 or above 200 GeV",
          phase="broken", fields=[DM_FERMION, {"name": "Z", "role": "standard_model", "spin": 1, "self_conjugate": True}],
          terms=[{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Z"}],
                  "lorentz": "axial", "coupling": "g_A"}]),
    Entry(id="z_portal_majorana", title="Majorana fermion coupling to the Z", family="vector portal",
          model_class=ZPortal(name="Z portal, Majorana", coupling="axial", majorana=True),
          point=Point(m_chi=500.0, m_med=91.19, g_chi=0.1),
          x=_axis("m_chi", 1.0, 10000.0), y=_axis("g_chi", 1e-5, 1.0), dark_matter="Majorana fermion χ",
          lagrangian="L ⊃ −½ Z_μ χ̄γ^μγ⁵χ g_A", parameters="m_χ; g_χ = g_A (the Feynman-rule coupling)",
          benchmark="Escudero et al. (arXiv:1609.09079), with a = ½ for Majorana dark matter",
          references=["arXiv:1609.09079 (Escudero et al.)"],
          phase="broken", fields=[DM_MAJORANA, {"name": "Z", "role": "standard_model", "spin": 1, "self_conjugate": True}],
          terms=[{"fields": [{"field": "chi"}, {"field": "chi"}, {"field": "Z"}], "lorentz": "axial",
                  "coupling": "g_A/2"}]),
    Entry(id="b_minus_l", title="Gauged B − L with Dirac dark matter", family="vector portal",
          model_class=ChargedZPrime(name="B − L"), point=Point(m_chi=1000.0, m_med=2000.0, g_chi=0.1 / 3, g_q=0.1),
          coupling_relations=[CouplingRelation(derived="g_chi", source="g_q", factor=1 / 3)],     # n_χ = 1/3
          x=_axis("m_med", 100.0, 10000.0), y=_axis("m_chi", 10.0, 5000.0), dark_matter="Dirac fermion χ, B − L charge 1/3",
          lagrangian="L ⊃ −g_BL Z′_μ (Σ_f q_f f̄γ^μf + n_χ χ̄γ^μχ), q = 1/3 (quarks), −1 (leptons)",
          parameters="m_χ; m_med = m_Z′; g_χ = n_χ g_BL; g_q = g_BL",
          benchmark="Klasen et al. (arXiv:1607.06468): n_χ = 1/3, g_BL = 0.1, 0.4, 0.8, M_Z′ = 2, 4, 6 TeV",
          references=["arXiv:1607.06468 (Klasen et al., NLO+NLL collider bounds, Dirac fermion and scalar DM "
                      "in the B−L model)", "arXiv:1806.02823 (Escudero, Witte & Rius)",
                      "arXiv:1903.06248 (ATLAS high-mass dilepton resonances, 139 fb⁻¹)"],
          literature="Klasen et al.: viable only in the Z′ resonance region; LEP requires M_Z′/g_BL ≳ 7 TeV",
          not_computed=["loop-induced kinetic mixing"],
          phase="broken", fields=[DM_FERMION, {"name": "Zp", "role": "mediator", "spin": 1, "self_conjugate": True},
                                  {"name": "q", "role": "standard_model", "spin": 0.5},
                                  {"name": "l", "role": "standard_model", "spin": 0.5},
                                  {"name": "nu", "role": "standard_model", "spin": 0.5}],
          terms=[{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Zp"}],
                  "lorentz": "vector", "coupling": "g_chi"},
                 {"fields": [{"field": "q", "conjugate": True}, {"field": "q"}, {"field": "Zp"}],
                  "lorentz": "vector", "coupling": "g_BL/3"},
                 {"fields": [{"field": "l", "conjugate": True}, {"field": "l"}, {"field": "Zp"}],
                  "lorentz": "vector", "coupling": "-g_BL"},
                 # the left-handed neutrinos carry L too (P1's gate found them missing: the generic B − L's width
                 # lacked its three ν ν̄ channels, 0.80 of 3.45 GeV at the benchmark)
                 {"fields": [{"field": "nu", "conjugate": True}, {"field": "nu"}, {"field": "Zp"}],
                  "lorentz": "vector", "coupling": "-g_BL"}]),
    Entry(id="lmu_minus_ltau", title="Gauged L_μ − L_τ with Dirac dark matter", family="vector portal",
          model_class=ChargedZPrime(name="L_μ − L_τ", charges="Lmu-Ltau"),
          point=Point(m_chi=0.5, m_med=1.5, g_chi=1e-3, g_q=1e-3),
          x=_axis("m_chi", 0.3, 30.0), y=_axis("g_q", 1e-5, 0.1), mediator_ratio=3.0,
          coupling_relations=[CouplingRelation(derived="g_chi", source="g_q", factor=1.0)],       # unit charge
          dark_matter="Dirac fermion χ, unit charge", lagrangian="L ⊃ g′ Z′_μ (μ̄γμ + ν̄_μγP_Lν_μ − τ̄γτ − ν̄_τγP_Lν_τ "
                                                                 "+ χ̄γχ)",
          parameters="m_χ; m_med = m_Z′ (= 3m_χ); g_χ = g_q = g′ (unit charge); ε ≈ −g′/70 from the loop",
          benchmark="Holst, Hooper & Krnjaic (arXiv:2107.09067); Foldenauer (arXiv:1808.03647): m_Z′ = 3m_χ",
          references=["arXiv:2107.09067 (Holst, Hooper & Krnjaic)", "arXiv:1808.03647 (Foldenauer)",
                      "arXiv:1901.02010 (Escudero, Hooper, Krnjaic & Pierre)"],
          literature="Foldenauer: m_Z′ = 3m_χ with unit charges is ruled out; the near-resonance region survives. "
                     "The muon g−2 (2025 SM update, arXiv:2505.21476) no longer shows a tension: an upper bound only",
          phase="broken", fields=[DM_FERMION, {"name": "Zp", "role": "mediator", "spin": 1, "self_conjugate": True},
                                  {"name": "mu", "role": "standard_model", "spin": 0.5},
                                  {"name": "tau", "role": "standard_model", "spin": 0.5},
                                  {"name": "nu_mu", "role": "standard_model", "spin": 0.5},
                                  {"name": "nu_tau", "role": "standard_model", "spin": 0.5}],
          terms=[{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Zp"}],
                  "lorentz": "vector", "coupling": "g_chi"},
                 {"fields": [{"field": "mu", "conjugate": True}, {"field": "mu"}, {"field": "Zp"}],
                  "lorentz": "vector", "coupling": "g_mt"},
                 {"fields": [{"field": "tau", "conjugate": True}, {"field": "tau"}, {"field": "Zp"}],
                  "lorentz": "vector", "coupling": "-g_mt"},
                 {"fields": [{"field": "nu_mu", "conjugate": True}, {"field": "nu_mu"}, {"field": "Zp"}],
                  "lorentz": "vector", "coupling": "g_mt"},                    # as the Lagrangian above (P1)
                 {"fields": [{"field": "nu_tau", "conjugate": True}, {"field": "nu_tau"}, {"field": "Zp"}],
                  "lorentz": "vector", "coupling": "-g_mt"}]),
    # --- pseudoscalar portal -----------------------------------------------------------------------------
    Entry(id="alp_portal", title="Pseudoscalar (ALP-like) mediator with Yukawa-like couplings (Coy dark matter)",
          family="pseudoscalar portal", model_class=ScalarClass(name="pseudoscalar mediator", dm_pseudoscalar=True,
                                                                sm_pseudoscalar=True, yukawa="DMsimp_s_spin0_MD"),
          yukawa="DMsimp_s_spin0_MD",
          point=Point(m_chi=30.0, m_med=100.0, g_chi=0.5, g_q=1.0, g_l=1.0),
          coupling_relations=[CouplingRelation(derived="g_l", source="g_q", factor=1.0)],         # one Yukawa factor
          x=_axis("m_med", 1.0, 1000.0), y=_axis("m_chi", 1.0, 1000.0), dark_matter="Dirac fermion χ",
          lagrangian="L ⊃ −i g_χ a χ̄γ⁵χ − i g_q Σ_f (m_f/v) a f̄γ⁵f",
          parameters="m_χ; m_med = m_a; g_χ; g_q = g_ℓ: the Yukawa-like factor (Dolan et al.'s √2 g_Y)",
          benchmark="Coy dark matter (arXiv:1401.6458): m_DM ≈ 30 GeV annihilating to b b̄; Dolan et al. (arXiv:1412.5174)",
          references=["arXiv:1412.5174 (Dolan, Kahlhoefer, McCabe & Schmidt-Hoberg, A taste of dark matter)",
                      "arXiv:0810.5397 (Nomura & Thaler, Dark matter through the axion portal)",
                      "arXiv:1401.6458 (Boehm et al., Extended gamma-ray emission from Coy dark matter)",
                      "arXiv:2405.02403 (Allen et al., Electroweak axion portal to dark matter)"],
          literature="Dolan et al.: a pseudoscalar mediator explains the Galactic Centre excess only if heavier than "
                     "the B mesons (flavour constraints)",
          not_computed=["K → π a, beam dumps, and the ALP's gluon and photon couplings (B → K a is computed below "
                        "m_B − m_K)"],
          phase="broken", fields=[DM_FERMION, {"name": "a", "role": "mediator", "spin": 0, "self_conjugate": True},
                                  {"name": "q", "role": "standard_model", "spin": 0.5},
                                  {"name": "l", "role": "standard_model", "spin": 0.5}],
          terms=[{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "a"}],
                  "lorentz": "pseudoscalar", "coupling": "g_chi"},
                 {"fields": [{"field": "q", "conjugate": True}, {"field": "q"}, {"field": "a"}],
                  "lorentz": "pseudoscalar", "coupling": "g_q*m_q/v"},
                 {"fields": [{"field": "l", "conjugate": True}, {"field": "l"}, {"field": "a"}],
                  "lorentz": "pseudoscalar", "coupling": "g_l*m_l/v"}]),      # Σ_f, as above (P1)
    # --- t-channel ---------------------------------------------------------------------------------------
    Entry(id="tchannel_uR_majorana", title="Majorana dark matter with a coloured partner of u_R (S3M_uR)",
          family="t-channel", model_class=TChannel(name="t-channel u_R, Majorana"),
          point=Point(m_chi=500.0, m_med=600.0, g_chi=1.0),
          x=_axis("m_med", 100.0, 3000.0), y=_axis("m_chi", 10.0, 2500.0), dark_matter="Majorana fermion χ",
          lagrangian="L ⊃ y φ* χ̄ P_R u + h.c., φ ~ (3, 1, 2/3)",
          parameters="m_χ = M_X; m_med = m_φ = M_Y; g_χ = y (λ)",
          benchmark="the LHC DM Working Group's S3M_uR (arXiv:2504.10597): parameters M_X, M_Y, λ; bino-like "
                    "y ≈ 0.33 (Garny et al., arXiv:1503.01500)",
          references=["arXiv:2504.10597 (t-channel dark matter at the LHC: a whitepaper)",
                      "arXiv:1503.01500 (Garny, Ibarra & Vogl)", "arXiv:2010.07559 (Arina et al., Closing in on "
                                                                 "t-channel simplified dark matter models)",
                      "arXiv:2203.04326 (Becker et al., Sommerfeld effect and bound states in t-channel models)"],
          literature="Arina et al.: thermal dark matter is largely probed (and disfavoured) by direct and indirect "
                     "detection; Garny et al.: for m_φ/m_χ ≈ 1.1, m_χ ≳ 200 GeV",
          not_computed=["excited bound states and thermal masses (the Sommerfeld effect and the ground bound state are "
                        "computed)", "LHC production beyond QCD pair production: χ exchange adds to it, so outside "
                        "ATLAS's one-squark contour a point is undecided", "LEP's searches for the charged partner "
                        "below 110 GeV: not yet a record"],
          fields=[DM_MAJORANA, {"name": "phi", "role": "mediator", "spin": 0, "dark_parity": -1,
                                "charges": {"su3": "3", "hypercharge": 2 / 3}}]),
    Entry(id="tchannel_uR_dirac", title="Dirac dark matter with a coloured partner of u_R (S3D_uR)",
          family="t-channel", model_class=TChannel(name="t-channel u_R, Dirac", majorana=False),
          point=Point(m_chi=500.0, m_med=600.0, g_chi=1.0),
          x=_axis("m_med", 100.0, 3000.0), y=_axis("m_chi", 10.0, 2500.0), dark_matter="Dirac fermion χ",
          lagrangian="L ⊃ y φ* χ̄ P_R u + h.c., φ ~ (3, 1, 2/3)", parameters="m_χ; m_med = m_φ; g_χ = y",
          benchmark="the LHC DM Working Group's S3D_uR (arXiv:2504.10597)",
          references=["arXiv:2504.10597 (t-channel whitepaper)", "arXiv:2010.07559 (Arina et al.)"],
          not_computed=["excited bound states and thermal masses (the Sommerfeld effect and the ground bound state are "
                        "computed)", "LHC production beyond QCD pair production: χ exchange adds to it, so outside "
                        "ATLAS's one-squark contour a point is undecided", "LEP's searches for the charged partner "
                        "below 110 GeV: not yet a record"],
          fields=[DM_FERMION, {"name": "phi", "role": "mediator", "spin": 0, "dark_parity": -1,
                               "charges": {"su3": "3", "hypercharge": 2 / 3}}]),
    Entry(id="lepton_portal_muR", title="Majorana dark matter with a partner of μ_R (lepton portal)",
          family="t-channel", model_class=TChannel(name="lepton portal μ_R, Majorana", partner="muR"),
          point=Point(m_chi=300.0, m_med=400.0, g_chi=1.0),
          x=_axis("m_med", 200.0, 3000.0), y=_axis("m_chi", 10.0, 2500.0), dark_matter="Majorana fermion χ",
          lagrangian="L ⊃ y φ* χ̄ P_R μ + h.c., φ ~ (1, 1, −1)", parameters="m_χ; m_med = m_φ; g_χ = y",
          benchmark="Bai & Berger (arXiv:1402.6696); bino-like y ≈ 0.48 for ℓ_R (Garny et al.)",
          references=["arXiv:1402.6696 (Bai & Berger, Lepton portal dark matter)",
                      "arXiv:1503.01500 (Garny, Ibarra & Vogl)"],
          literature="Garny et al.: for m_φ/m_χ ≈ 1.1, m_χ ≳ 50 GeV for dark matter coupling to leptons",
          not_computed=[],
          fields=[DM_MAJORANA, {"name": "phi", "role": "mediator", "spin": 0, "dark_parity": -1,
                                "charges": {"hypercharge": -1.0}}]),
]

# DM13's classes, listed beside the portals (the LHC DM Working Group's simplified models)
ENTRIES += [
    Entry(id=f"dmwg_{name}", title=f"LHC DM Working Group {name} (spin-1 s-channel)", family="s-channel mediator",
          model_class=Spin1Class(name=name, kind=spin1.BENCHMARKS[name][0]),
          point=Point(m_chi=100.0, m_med=1000.0, g_chi=1.0, g_q=spin1.BENCHMARKS[name][1], g_l=spin1.BENCHMARKS[name][2]),
          x=_axis("m_med", 10.0, 10000.0), y=_axis("m_chi", 1.0, 2000.0), dark_matter="Dirac fermion χ",
          lagrangian="−Z′_μ[g_DM χ̄Γχ + g_q Σ q̄Γq + g_ℓ Σ ℓ̄Γℓ], Γ = γ^μ or γ^μγ⁵",
          parameters="m_χ; m_med; g_χ = g_DM; g_q; g_ℓ",
          benchmark=f"{name} (arXiv:1703.05703, sec. 2.3.1); CMS's summary (arXiv:2405.13778) applies",
          references=["arXiv:1703.05703 (LHC DM Working Group)", "arXiv:2405.13778 (CMS summary)"],
          fields=[DM_FERMION, {"name": "Zp", "role": "mediator", "spin": 1, "self_conjugate": True},
                  {"name": "q", "role": "standard_model", "spin": 0.5}],
          phase="broken", terms=[{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Zp"}],
                                  "lorentz": spin1.BENCHMARKS[name][0].value, "coupling": "g_DM"},
                                 {"fields": [{"field": "q", "conjugate": True}, {"field": "q"}, {"field": "Zp"}],
                                  "lorentz": spin1.BENCHMARKS[name][0].value, "coupling": "g_q"}])
    for name in ("V1", "A1")
]
ENTRIES += [
    Entry(id="scalar_mediator", title="Scalar mediator with Yukawa-like couplings", family="s-channel mediator",
          model_class=ScalarClass(name="scalar mediator", yukawa="DMsimp_s_spin0_MD"), yukawa="DMsimp_s_spin0_MD",
          point=Point(m_chi=100.0, m_med=500.0, g_chi=1.0, g_q=1.0),
          x=_axis("m_med", 10.0, 10000.0), y=_axis("m_chi", 1.0, 2000.0), dark_matter="Dirac fermion χ",
          lagrangian="L ⊃ −g_χ S χ̄χ − g_q Σ_f (m_f/v) S f̄f", parameters="m_χ; m_med = m_S; g_χ; g_q",
          benchmark="the LHC DM Working Group's spin-0 couplings, g_q = 1 with Yukawa scaling (arXiv:1703.05703)",
          references=["arXiv:1703.05703 (LHC DM Working Group)"],
          fields=[DM_FERMION, {"name": "S", "role": "mediator", "spin": 0, "self_conjugate": True},
                  {"name": "q", "role": "standard_model", "spin": 0.5}],
          phase="broken", terms=[{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "S"}],
                                  "lorentz": "scalar", "coupling": "g_chi"},
                                 {"fields": [{"field": "q", "conjugate": True}, {"field": "q"}, {"field": "S"}],
                                  "lorentz": "scalar", "coupling": "g_q*m_q/v"}]),
]

# The portal library, part 2 (2026-10-03): models read from published UFO files, and electroweak multiplets
# the b and c masses of the Higgs's couplings are those whose tree-level widths at m_h are the Working Group's: the
# MS-bar mass run to m_h times the square root of ``constraints.higgs``'s higher-order factor (its anchor), so the
# model's h → b b̄ and c c̄ are the widths the Higgs module computes (3.12 and 0.69 GeV). With the UFO file's 4.23 and
# 1.2 GeV the model's own h → b b̄ (4.4 MeV) exceeded the measured total width in its propagator, and Ωh² in the Higgs
# funnel was 17–31% low (the audit loop's AL3-05, 2026-11-15); the Higgs's loop-induced final states are the portal's
# (``ufo.higgs_loops``)
_HIGGS_YUKAWA_MASSES = {f"MM{q.upper()}": f"{_higgs.running_mass(q, 125.09) * math.sqrt(_higgs.anchor(q, 125.09)):.6g}"
                        for q in ("b", "c")}
INERT_DOUBLET = UFOPortal(
    name="inert doublet", model_dir="ufo/InertDoublet_UFO", dm="~H0", partners=["~A0", "~H+"],
    parameters={"mmH0": "m_chi", "mmHch": "m_med", "lamL": "g_chi/2", "mmA0": "m_chi + g_q", "mmh": "125.09",
                "Wh": "0.0041", **_HIGGS_YUKAWA_MASSES},
    width_of={"WA0": "~A0", "WHch": "~H+"}, couplings=["g_chi"], searches=["lep_inert_doublet"],
    labels={"m_chi": "M_H₀ (GeV)", "m_med": "M_H± (GeV)", "g_chi": "λ₃₄₅", "g_q": "M_A₀ − M_H₀ (GeV)"},
    # its H₀H₀ → γγ, Zγ runs mainly through W and charged-scalar loops, which are not computed; the Higgs's loop alone
    # had made the line searches "allowed" (the audit loop's AL4-10, ratio 6.6 × 10⁻⁶): undecided, with why
    partial_lines=("the γ-ray lines are not computed: H₀H₀ → γγ and Zγ run mainly through the W and charged-scalar "
                   "loops, and only the Higgs's loop is in the model's rate"),
    not_computed=["γ-ray line searches (H₀H₀ → γγ, Zγ through the W and charged-scalar loops)"])
TWO_HDM_A = UFOPortal(
    name="2HDM+a", model_dir="ufo/Pseudoscalar_2HDM", dm="Xd", spin_dm=0.5, self_conjugate_dm=False,
    parameters={"MXd": "m_chi", "mh4": "m_med", "gPXd": "g_chi", "sinp": "g_q", "tanbeta": "g_l", "sinbma": "1.0",
                "lam3": "3.0", "laP1": "3.0", "laP2": "3.0", "mh1": "125.09", "Wh1": "0.0041", "mh2": "1000.0",
                "mh3": "1000.0", "mhc": "1000.0"},
    width_of={"Wh2": "h2", "Wh3": "h3", "Wh4": "h4", "whc": "h+"}, couplings=["g_chi"], searches=["atlas_2hdma"],
    labels={"m_chi": "m_χ (GeV)", "m_med": "M_a (GeV)", "g_chi": "y_χ", "g_q": "sin θ", "g_l": "tan β"},
    loop_dd="2hdma",
    not_computed=[])
ENTRIES += [
    Entry(id="inert_doublet", title="Inert doublet model (high-mass, nearly degenerate scalars)", family="extended scalar sector",
          model_class=INERT_DOUBLET, point=Point(m_chi=990.0, m_med=998.12, g_chi=-0.051, g_q=2.36),
          x=_axis("m_chi", 500.0, 2000.0, n=16), y=_axis("g_chi", -0.5, 0.5, n=11, log=False), mediator_ratio=1.0082,
          dark_matter="the neutral scalar H₀ of a second, Z₂-odd Higgs doublet",
          lagrangian="V ⊃ μ₂²|H₂|² + λ₂|H₂|⁴ + λ₃|H₁|²|H₂|² + λ₄|H₁†H₂|² + (λ₅/2)[(H₁†H₂)² + h.c.]; the UFO of "
                     "Goudelis, Herrmann & Stål (FeynRules)",
          parameters="m_χ = M_H₀; m_med = M_H± (= 1.0082 M_H₀ in the scan); g_χ = λ₃₄₅ = λ₃ + λ₄ + λ₅; "
                     "g_q = M_A₀ − M_H₀ (GeV)",
          benchmark="Kalinowski et al. HP10 (arXiv:1809.07712): M_H₀ = 990, M_A₀ = 992.36, M_H± = 998.12 GeV, "
                    "λ₃₄₅ = −0.051, Ωh² = 0.12478 (micrOMEGAs)",
          references=["arXiv:1809.07712 (Kalinowski et al., benchmarks)", "arXiv:1612.00511 (Belyaev et al.)",
                      "arXiv:hep-ph/0612275 (Lopez Honorez et al.)", "arXiv:0810.3924 (Lundström et al., LEP II)",
                      "arXiv:1303.3010 (Goudelis et al., the FeynRules model)"],
          literature="Kalinowski et al.: HP10 gives the observed density at M_H₀ ≈ 1 TeV with near-degenerate "
                     "scalars; the low-mass region (M_H₀ ≈ 55–75 GeV) needs off-shell WW*, which a 2 → 2 code omits",
          not_computed=["the Sommerfeld effect of the nearly degenerate scalars (a few per cent above 500 GeV)",
                        "LHC dilepton and monojet searches outside SModelS's database"],
          fields=[{"name": "H2", "role": "dark_matter", "spin": 0, "dark_parity": -1,
                   "charges": {"su2": 2, "hypercharge": 0.5}}]),
    Entry(id="two_hdm_a", title="2HDM+a: two Higgs doublets and a pseudoscalar mediator (Dirac dark matter)",
          family="extended scalar sector", model_class=TWO_HDM_A,
          point=Point(m_chi=160.0, m_med=400.0, g_chi=1.0, g_q=0.35, g_l=1.0),
          x=_axis("m_med", 100.0, 1000.0, n=14), y=_axis("m_chi", 10.0, 1000.0, n=14),
          dark_matter="Dirac fermion χ coupling to the pseudoscalar P, which mixes with the doublets' A (angle θ)",
          lagrangian="L ⊃ −i y_χ P χ̄γ⁵χ + V(H₁, H₂, P) with P(i b_P H₁†H₂ + h.c.) (type II, alignment); the UFO of "
                     "the LHC DM Working Group (Pseudoscalar_2HDM)",
          parameters="m_χ; m_med = M_a; g_χ = y_χ; g_q = sin θ; g_l = tan β; M_A = M_H = M_H± = 1 TeV, "
                     "λ₃ = λ_P1 = λ_P2 = 3",
          benchmark="the LHC DM Working Group's 2HDM+a (arXiv:1810.09420 eq. (4.5)) with ATLAS's scenario 5 heavy "
                    "masses (arXiv:2306.00641: M_A = 1 TeV, M_a = 400 GeV, sin θ = 0.35)",
          references=["arXiv:1810.09420 (LHC DM Working Group, spin-0 models)", "arXiv:1701.07427 (Bauer, Haisch & "
                      "Kahlhoefer)", "arXiv:2306.00641 (ATLAS combination)"],
          literature="DMWG Fig. 27: Ωh² = 0.12 only near m_χ ≈ M_a/2, (M_a + m_h)/2, or m_χ ≈ m_t (ATLAS: m_χ ≈ 170 GeV "
                     "at M_a = 400 GeV); ATLAS excludes "
                     "M_A ≲ 1.5 TeV for M_a ≈ 150–250 GeV in scenario 1a",
          not_computed=["the box diagrams of the loop-induced scattering (≲ 10% for tan β ≲ 10; the h and H "
                        "triangles are computed)",
                        "χχ̄ → a*, A* → gg through the top and bottom loops, in Ωh² and in today's rate, and a, A → gg in "
                        "their widths: the UFO route reads no gluon vertex (for m_b ≪ m_χ < m_t and tan β near 1 it "
                        "may be comparable to b b̄; AL3-15)"],
          fields=[{"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1},
                  {"name": "H2", "role": "mediator", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}},
                  {"name": "P", "role": "mediator", "spin": 0, "self_conjugate": True}]),
    Entry(id="wino", title="Wino-like dark matter (a Majorana SU(2) triplet)", family="electroweak multiplet",
          model_class=ElectroweakMultiplet(name="wino", multiplet="wino"), point=Point(m_chi=2900.0, m_med=1.0, g_q=0.0),
          x=_axis("m_chi", 1000.0, 5000.0, n=12), y=_axis("g_q", 0.1, 0.4, n=2),
          dark_matter="the neutral member of a Majorana SU(2) triplet with Y = 0",
          lagrangian="L = ½ χ̄ᵃ(i D̸ − M)χᵃ, a = 1, 2, 3; the charged states 165 MeV heavier (radiative)",
          parameters="m_χ = M; g_q = the charged–neutral splitting δ (GeV; 0 = 165 MeV)",
          benchmark="the thermal wino: M = 2.88 TeV with the Sommerfeld effect (Beneke et al. arXiv:1601.04718), "
                    "2.86 TeV with bound states (Bottaro et al. arXiv:2107.09688)",
          references=["arXiv:1601.04718 (Beneke et al.)", "arXiv:hep-ph/0610249 (Hisano et al.)",
                      "arXiv:0706.4071 (Cirelli, Strumia & Tamburini)", "arXiv:1702.01141 (Mitridate et al.)",
                      "arXiv:2107.09688 (Bottaro et al.)", "arXiv:1504.00915 (Hisano, Ishiwata & Nagata, direct "
                                                            "detection)"],
          literature="the thermal wino (≈2.9 TeV) is probed by H.E.S.S.'s Galactic Centre lines for cuspy profiles; "
                     "σ_SI ≈ 2.3 × 10⁻⁴⁷ cm², near the neutrino floor",
          not_computed=[],
          fields=[{"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
                   "charges": {"su2": 3}}]),
    Entry(id="quintuplet", title="The minimal dark matter quintuplet (a Majorana SU(2) 5-plet, Y = 0)",
          family="electroweak multiplet",
          model_class=ElectroweakNplet(name="quintuplet", n=5, hypercharge=0.0),
          point=Point(m_chi=13600.0, m_med=1.0, g_q=0.0),
          x=_axis("m_chi", 3000.0, 30000.0, n=12), y=_axis("g_q", 0.1, 0.4, n=2),
          dark_matter="the neutral member of a Majorana SU(2) 5-plet with Y = 0, accidentally stable",
          lagrangian="L = ½ χ̄ᵃ(i D̸ − M)χᵃ, a = 1…5 (Cirelli, Fornengo & Strumia)",
          parameters="m_χ = M; g_q is unused (the plane's second axis repeats the first)",
          benchmark="Bottaro et al. (arXiv:2107.09688 Table I): M = 13.6 ± 0.8 TeV with the Sommerfeld effect and bound "
                    "states; ADROIT's symmetric-limit engine gives 15.5 TeV (13.5–16.3 TeV as the potentials' coupling "
                    "scale runs from M to m_Z)",
          references=["arXiv:hep-ph/0512090 (Cirelli, Fornengo & Strumia)", "arXiv:0706.4071 (Cirelli, Strumia & "
                      "Tamburini)", "arXiv:1702.01141 (Mitridate, Redi, Smirnov & Strumia)", "arXiv:2107.09688 "
                      "(Bottaro et al.)"],
          literature="the thermal quintuplet (13.6 TeV) has σ_SI ≈ 10⁻⁴⁶ cm², within reach of large xenon detectors; "
                     "its γ-ray lines are probed by H.E.S.S. and CTA",
          not_computed=["today's annihilation (γ rays, lines, the CMB, antiprotons, the Sun): it needs the broken-phase "
                        "Sommerfeld effect, so these searches are undecided", "the LHC (out of reach at these masses)",
                        "2p bound states"],
          fields=[{"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
                   "charges": {"su2": 5}}]),
    Entry(id="quintuplet_dirac", title="A Dirac SU(2) 5-plet with Y = 1 (a complex WIMP)",
          family="electroweak multiplet",
          model_class=ElectroweakNplet(name="quintuplet_dirac", n=5, hypercharge=1.0),
          point=Point(m_chi=9900.0, m_med=1.0, g_q=2.2e-4),
          x=_axis("m_chi", 3000.0, 30000.0, n=12), y=_axis("g_q", 2.1e-4, 3e-3, n=4),
          dark_matter="the lighter Majorana state of the neutral Dirac member (T₃ = −1), split by δm₀ from a "
                      "dimension-7 operator",
          lagrangian="L = χ̄(i D̸ − M)χ + (y₀/Λ³) O₀ + h.c., O₀ ∝ χ̄(Tᵃ)²χᶜ (H^c† σᵃ H/2)² (Bottaro et al. "
                     "arXiv:2205.04486 eq. (1))",
          parameters="m_χ = M; g_q = the neutral splitting δm₀ (GeV); Bottaro et al. allow 0.21–3 MeV",
          benchmark="Bottaro et al. (arXiv:2205.04486 Table I): M = 9.9 ± 0.7 TeV with the Sommerfeld effect and bound "
                    "states, δm₀ = 0.21–3 MeV; ADROIT's symmetric-limit engine gives 10.7 TeV (9.6–11.5 TeV as the "
                    "potentials' coupling scale runs from M to m_Z)",
          references=["arXiv:2205.04486 (Bottaro et al.)", "arXiv:1702.01141 (Mitridate, Redi, Smirnov & Strumia)",
                      "arXiv:0706.4071 (Cirelli, Strumia & Tamburini)"],
          literature="the thermal 5₁ (9.9 TeV) has σ_SI ≈ 10⁻⁴⁷ cm², reduced by a partial cancellation between the Z "
                     "and W loops",
          not_computed=["today's annihilation (γ rays, lines, the CMB, antiprotons, the Sun): it needs the broken-phase "
                        "Sommerfeld effect, so these searches are undecided", "the LHC (out of reach at these masses)",
                        "2p bound states", "Z-mediated inelastic scattering for δm₀ below xenon's 450 keV reach "
                        "(undecided there)"],
          fields=[{"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1,
                   "charges": {"su2": 5, "hypercharge": 1.0}}]),
    Entry(id="higgsino", title="Higgsino-like dark matter (a Dirac SU(2) doublet, Y = ½)", family="electroweak multiplet",
          model_class=ElectroweakMultiplet(name="higgsino", multiplet="higgsino"), point=Point(m_chi=1100.0, m_med=1.0, g_q=0.0),
          x=_axis("m_chi", 300.0, 3000.0, n=12), y=_axis("g_q", 0.2, 0.6, n=2),
          dark_matter="the neutral member of a Dirac SU(2) doublet with Y = ½ (neutral states split by ≳ 200 keV)",
          lagrangian="L = ψ̄(i D̸ − M)ψ, ψ ~ (1, 2, ½); the charged state 341 MeV heavier (radiative)",
          parameters="m_χ = M; g_q = the charged–neutral splitting δ (GeV; 0 = 341 MeV)",
          benchmark="the thermal higgsino: M ≈ 1.1 TeV (Cirelli et al.); 1.08 TeV with bound states (Bottaro et al. "
                    "arXiv:2205.04486)",
          references=["arXiv:hep-ph/0512090 (Cirelli, Fornengo & Strumia)", "arXiv:0706.4071 (Cirelli et al.)",
                      "arXiv:2205.04486 (Bottaro et al.)", "arXiv:hep-ph/0412403 (Hisano et al.)"],
          literature="the Sommerfeld effect changes the higgsino's density by a few per cent at most",
          not_computed=["bound states", "inelastic scattering through the Z"],
          fields=[{"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1,
                   "charges": {"su2": 2, "hypercharge": 0.5}}]),
]


def _cited(reference: str) -> str:
    """'arXiv:ID (any note)' → 'arXiv:ID — First Author, "exact title"' from ``references``."""
    import re
    from adroit.parameter_space.references import REFERENCES
    found = re.match(r"arXiv:(\S+)", reference)
    if not found or found.group(1) not in REFERENCES:
        return reference
    title, author = REFERENCES[found.group(1)]
    return f"arXiv:{found.group(1)} — {author}, \"{title}\""


for _e in ENTRIES:
    _e.references = [_cited(r) for r in _e.references]

BY_ID = {e.id: e for e in ENTRIES}


def entry(entry_id: str) -> Entry:
    """The library entry with this id; KeyError naming the known ids otherwise."""
    if entry_id not in BY_ID:
        raise KeyError(f"no portal {entry_id!r}; known: {', '.join(BY_ID)}")
    return BY_ID[entry_id]


def listing() -> str:
    """The library as a Markdown table."""
    lines = ["| id | model | family | dark matter | benchmark |", "|---|---|---|---|---|"]
    lines += [f"| `{e.id}` | {e.title} | {e.family} | {e.dark_matter} | {e.benchmark} |" for e in ENTRIES]
    return "\n".join(lines) + "\n"
