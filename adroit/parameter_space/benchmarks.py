"""Each standard-library model's complete numerical benchmark as a typed model, in its own notation (OB-11, the owner's
repair of 2026-11-24).

A library entry (``library.Entry``) names its engine and its benchmark point in the engine's slots (m_χ, m_med, g_χ,
g_q, g_ℓ). Its typed model, the one the model library shows and Explain a signal and Signal best fits run, had given a
value only to couplings named g_chi, g_q or g_l, so 17 of 27 entries could not run, and some that could did not reach
their own engine (the fermion and vector Higgs portals had no interaction term at all). Here each entry's typed model
is complete:

- ``couplings``: every coupling of the typed model, with its benchmark value and why (the paper's value, or a value
  derived from the benchmark's masses and angles, or one the engine holds);
- ``terms`` and ``fields``: the interactions the engine computes, written in the model's own notation, where the
  entry's own (``Entry.spec``, which the generic-route gates read and which is left as it is) is not that;
- ``assumptions``: what the benchmark sets to zero or leaves out, each stated (never a silent zero);
- ``fitted``: the typed coupling Explain a signal fits (the engine's g_χ slot), or None for a model with no free
  coupling, which is evaluated at its own couplings and never fitted;
- ``bind``: whether no general map (``classify``) computes this typed model with the entry's engine. A bound model is
  read by ``standard_binding`` when its structure is the entry's: ``slots`` give each engine slot as a formula of its
  couplings and field masses (``m_<field>``), ``ties`` the couplings that follow the fitted one, and ``held`` the
  couplings the engine holds fixed (an edited value is refused, never ignored);
- ``unsupported``: a model Explain a signal cannot compute, and what it would need (it stays listed in the library,
  with this reason);
- ``no_recoil``: a model whose engine computes its constraints and relic density but no recoil spectrum (its
  scattering is momentum-suppressed or loop-induced, and the engine's scattering keeps O₁ and O₄ only): the signal
  pages do not offer it, and say what it would need.

The numbers the formulas embed are the engines' own (m_h = 125.09 GeV, ``constraints.kinetic_mixing.COS_W``), not the
formula table's rounded constants, so the typed model and its engine agree exactly.
"""

from __future__ import annotations

import math

from pydantic import Field

from adroit.constraints import higgs as _higgs
from adroit.constraints import kinetic_mixing as _km
from adroit.core.state import StrictModel


class TypedBenchmark(StrictModel):
    """One entry's complete typed model at its benchmark (see the module docstring)."""
    couplings: list[dict]
    terms: list[dict] | None = None
    fields: list[dict] | None = None
    phase: str | None = None
    fitted: str | None
    assumptions: list[str] = Field(default_factory=list)
    bind: bool = False
    slots: dict[str, str] = Field(default_factory=dict)
    ties: list[tuple[str, str, str]] = Field(default_factory=list)      # (derived slot, source slot, factor formula)
    held: dict[str, float] = Field(default_factory=dict)
    unsupported: str = ""
    # computed (its constraints, its relic density), but no recoil spectrum: what a signal fit would need (OB-11)
    no_recoil: str = ""
    # the fitted slot's declared range (``ModelSpec.physical_fit``), where the default 0 ≤ g_χ ≤ √(4π) would let a
    # tied coupling leave its own perturbative range (g_BL = g_χ/n_χ)
    fit_range: tuple[float, float] | None = None


def _c(name: str, value: float, why: str, dimension: int = 0) -> dict:
    return {"name": name, "value": value, "mass_dimension": dimension, "justification": why}


def _t(fields: list[tuple[str, bool]], lorentz: str, coupling: str, text: str, hc: bool = False,
       indices: str = "") -> dict:
    return {"fields": [{"field": f, "conjugate": c} for f, c in fields], "lorentz": lorentz, "coupling": coupling,
            "text": text, "plus_hc": hc, "indices": indices}


M_H = _higgs.M_H                                      # 125.09 GeV, the engines' Higgs mass
TWO_COS_W = repr(2 * _km.COS_W)                       # the dark-photon engine's 2 cos θ_W
ALPHA_D_HALF = math.sqrt(4.0 * math.pi * 0.5)
ALPHA_D_TENTH = math.sqrt(4.0 * math.pi * 0.1)

DM = {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1}
DM_MAJORANA = {**DM, "self_conjugate": True}
HIGGS = {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}
B_FIELD = {"name": "B", "role": "standard_model", "spin": 1, "self_conjugate": True}
XD = {"name": "Xd", "role": "mediator", "spin": 1, "self_conjugate": True}

HIGGS_MEDIATOR = ("the mediator is the Higgs, m_h = 125.09 GeV; m_χ is the physical mass after electroweak breaking "
                  "(the λ v²/2 shift is included in it)")
NO_FREE_COUPLING = ("only gauge interactions: the model has no free coupling, so Explain a signal evaluates it at its "
                    "own couplings and fits none")


def _higgs_fermion(cpv: bool = False, majorana: bool = False) -> TypedBenchmark:
    lorentz, text = ("pseudoscalar", "−(λ_hχ/Λ) χ̄ iγ⁵χ H†H") if cpv else ("scalar", "−(λ_hχ/Λ) χ̄χ H†H")
    fields = [("chi", False), ("chi", False)] if majorana else [("chi", True), ("chi", False)]
    return TypedBenchmark(
        fields=[DM_MAJORANA if majorana else DM, HIGGS],
        terms=[_t([*fields, ("H", False), ("H", True)], lorentz, "-lam_hchi/2" if majorana else "-lam_hchi",
                  ("−½" + text[1:]) if majorana else text)],
        couplings=[_c("lam_hchi", 1e-3, "λ_hχ/Λ in GeV⁻¹: GAMBIT's fermion Higgs portal (arXiv:1808.10465)"
                      + ("; the Feynman-rule coupling, the ½ of a Majorana field written in L" if majorana else ""),
                      -1)],
        fitted="lam_hchi", bind=True, slots={"g_chi": "lam_hchi"},
        assumptions=[HIGGS_MEDIATOR, "the effective theory holds for λ_hχ·2m_χ < 4π"],
        no_recoil=("its scattering is the momentum-suppressed O₁₁ (q/m_χ), which the Higgs-portal engine does not "
                   "compute (it keeps O₁ and O₄), so it predicts no recoils; a signal fit needs O₁₁ in the engine's "
                   "scattering") if cpv else "")


TYPED: dict[str, TypedBenchmark] = {
    # --- Higgs portals ---------------------------------------------------------------------------------------------
    "higgs_portal_scalar": TypedBenchmark(
        fields=[{"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True, "dark_parity": -1}, HIGGS],
        terms=[_t([("H", False), ("H", True), ("S", False), ("S", False)], "scalar", "-lam_hs/2", "−½ λ_hs S² H†H")],
        couplings=[_c("lam_hs", 2.9e-4, "GAMBIT's best fit at the resonance (arXiv:1705.07931, sec. 4.3)")],
        fitted="lam_hs",
        assumptions=["m_S is the physical mass (μ_S² = m_S² − λ_hs v²/2)",
                     "λ_S, the S⁴ self-coupling, is left out: it enters neither tree-level annihilation into other "
                     "particles nor scattering"]),
    "higgs_portal_dirac": _higgs_fermion(),
    "higgs_portal_dirac_cpv": _higgs_fermion(cpv=True),
    "higgs_portal_majorana": _higgs_fermion(majorana=True),
    "higgs_portal_vector": TypedBenchmark(
        phase="unbroken",
        fields=[{"name": "V", "role": "dark_matter", "spin": 1, "self_conjugate": True, "dark_parity": -1}, HIGGS],
        terms=[_t([("V", False), ("V", False), ("H", False), ("H", True)], "scalar", "lam_hV/2",
                  "½ λ_hV V_μV^μ H†H")],
        couplings=[_c("lam_hV", 0.5, "GAMBIT's vector Higgs portal (arXiv:1808.10465), λ_hV < 10")],
        fitted="lam_hV", bind=True, slots={"g_chi": "lam_hV"},
        assumptions=[HIGGS_MEDIATOR.replace("m_χ", "m_V"), "λ_V, the V⁴ self-coupling, is left out"]),
    "singlet_scalar_mixing": TypedBenchmark(
        fields=[DM, {"name": "S", "role": "mediator", "spin": 0, "self_conjugate": True}, HIGGS],
        terms=[_t([("chi", True), ("chi", False), ("S", False)], "scalar", "-y", "−y χ̄χ s"),
               _t([("H", False), ("H", True), ("S", False)], "scalar",
                  f"(m_S**2 - {M_H!r}**2)*sin(theta)*cos(theta)/v",
                  "−μ s|H|², μ = −(m₂² − m₁²) sin θ cos θ / v")],
        couplings=[_c("y", 1.0, "Albert et al. (arXiv:1607.06680, sec. 2): y = 1"),
                   _c("theta", 0.2, "the mixing angle θ = 0.2 (Albert et al.); h₁ = cos θ h + sin θ s")],
        fitted="y", bind=True, slots={"g_chi": "y", "g_q": "sin(theta)"},
        assumptions=["S's mass is the heavy eigenstate's, m₂; the light one is the Higgs, m₁ = 125.09 GeV",
                     "λ_Hs = μ_s = 0: the h–s–s and s³ trilinears are zero, as the engine computes them",
                     "the s mass parameter and the Higgs quartic are fixed by m₁, m₂ and θ (μ above, from the mass "
                     "matrix); λ_s, the s⁴ self-coupling, is left out"]),
    # --- vector portals ------------------------------------------------------------------------------------------
    "dark_photon_dirac": TypedBenchmark(
        phase="unbroken", fields=[{**DM, "charges": {"extra": {"Xd": 1.0}}}, XD, B_FIELD],
        terms=[_t([("Xd", False), ("B", False)], "kinetic_mixing", f"-eps/{TWO_COS_W}", "−(ε/2c_W) X_μν B^μν"),
               _t([("chi", True), ("chi", False), ("Xd", False)], "vector", "g_D", "g_D X_μ χ̄γ^μχ")],
        couplings=[_c("eps", 1e-4, "the kinetic mixing ε (the thermal-target plane's axis)"),
                   _c("g_D", ALPHA_D_HALF, "α_D = g_D²/4π = 0.5 (arXiv:1505.00011)")],
        fitted="g_D",
        assumptions=["m_A′ = 3m_χ at the benchmark (the thermal-target convention)",
                     "the A′ mass is a Stueckelberg-like mass term: no dark Higgs"]),
    "dark_photon_scalar": TypedBenchmark(
        phase="unbroken",
        fields=[{"name": "phi", "role": "dark_matter", "spin": 0, "dark_parity": -1, "charges": {"extra": {"Xd": 1.0}}},
                XD, B_FIELD],
        terms=[_t([("Xd", False), ("B", False)], "kinetic_mixing", f"-eps/{TWO_COS_W}", "−(ε/2c_W) X_μν B^μν"),
               _t([("phi", True), ("phi", False), ("Xd", False)], "scalar_current", "g_D",
                  "i g_D X^μ (φ*∂_μφ − φ∂_μφ*)"),
               _t([("phi", False), ("phi", True), ("Xd", False), ("Xd", False)], "scalar", "g_D**2",
                  "g_D² X_μX^μ |φ|²")],
        couplings=[_c("eps", 1e-4, "the kinetic mixing ε"),
                   _c("g_D", ALPHA_D_HALF, "α_D = 0.5 (arXiv:2207.00597)")],
        fitted="g_D",
        assumptions=["m_A′ = 3m_φ at the benchmark",
                     "λ_Hφ = 0: the benchmark has no Higgs portal; λ_φ, the |φ|⁴ self-coupling, is left out"]),
    "inelastic_dark_photon": TypedBenchmark(
        phase="unbroken", fields=[{**DM, "charges": {"extra": {"Xd": 1.0}}}, XD, B_FIELD],
        terms=[_t([("Xd", False), ("B", False)], "kinetic_mixing", f"-eps/{TWO_COS_W}", "−(ε/2c_W) X_μν B^μν"),
               _t([("chi", True), ("chi", False), ("Xd", False)], "vector", "g_D",
                  "g_D X_μ χ̄₂γ^μχ₁ + h.c. (the Dirac current, split by a Majorana mass)")],
        couplings=[_c("eps", 1e-3, "ε = 10⁻³ (arXiv:1810.01879 Fig. 3)"),
                   _c("g_D", ALPHA_D_TENTH, "α_D = 0.1 (arXiv:1508.03050)"),
                   _c("Delta", 0.1, "the fractional splitting Δ = (m₂ − m₁)/m₁ = 0.1")],
        fitted="g_D", bind=True, slots={"g_chi": "g_D", "g_q": "eps", "g_l": "Delta"},
        assumptions=["m_A′ = 3m₁ at the benchmark"],
        unsupported=("its scattering is inelastic (χ₁N → χ₂N, δ = Δ m₁ = 0.5 GeV at the benchmark), and Explain a "
                     "signal's physical fit predicts elastic recoils only: the engine has no inelastic interaction "
                     "(its direct detection is compared through Signal best fits' inelastic hypotheses). It needs the "
                     "splitting δ in the engine's interaction and in the physical fit's prediction")),
    "z_portal_vector": TypedBenchmark(
        couplings=[_c("g_V", 0.01, "Escudero et al. (arXiv:1609.09079): the Z portal's vector coupling")],
        fitted="g_V", bind=True, slots={"g_chi": "g_V"},
        assumptions=["the Z's couplings to the Standard Model are its own; m_Z = 91.19 GeV", "g_A = 0"]),
    "z_portal_axial": TypedBenchmark(
        couplings=[_c("g_A", 0.1, "Escudero et al. (arXiv:1609.09079): the Z portal's axial coupling")],
        fitted="g_A", bind=True, slots={"g_chi": "g_A"},
        assumptions=["the Z's couplings to the Standard Model are its own; m_Z = 91.19 GeV", "g_V = 0"]),
    "z_portal_majorana": TypedBenchmark(
        couplings=[_c("g_A", 0.1, "Escudero et al. (arXiv:1609.09079), with a = ½ for Majorana dark matter")],
        fitted="g_A", bind=True, slots={"g_chi": "g_A"},
        assumptions=["the Z's couplings to the Standard Model are its own; m_Z = 91.19 GeV",
                     "a Majorana fermion has no vector current"]),
    "b_minus_l": TypedBenchmark(
        terms=[_t([("chi", True), ("chi", False), ("Zp", False)], "vector", "n_chi*g_BL", "−g_BL n_χ Z′_μ χ̄γ^μχ"),
               _t([("q", True), ("q", False), ("Zp", False)], "vector", "g_BL/3", "−(g_BL/3) Z′_μ q̄γ^μq"),
               _t([("l", True), ("l", False), ("Zp", False)], "vector", "-g_BL", "+g_BL Z′_μ ℓ̄γ^μℓ"),
               _t([("nu", True), ("nu", False), ("Zp", False)], "vector", "-g_BL", "+g_BL Z′_μ ν̄γ^μν")],
        couplings=[_c("g_BL", 0.1, "Klasen et al. (arXiv:1607.06468): g_BL = 0.1"),
                   _c("n_chi", 1 / 3, "the dark matter's B − L charge n_χ = 1/3 (Klasen et al.)")],
        fitted="g_BL", bind=True, slots={"g_chi": "n_chi*g_BL", "g_q": "g_BL"}, ties=[("g_chi", "g_q", "n_chi")],
        fit_range=(0.0, math.sqrt(4 * math.pi) / 3),          # g_BL ≤ √(4π): g_χ = n_χ g_BL ≤ √(4π)/3
        assumptions=["no kinetic mixing with the photon (the loop-induced mixing is not computed)",
                     "quarks carry B − L charge 1/3 and leptons −1, left-handed neutrinos included"]),
    "lmu_minus_ltau": TypedBenchmark(
        terms=[_t([("chi", True), ("chi", False), ("Zp", False)], "vector", "q_chi*g_mt", "g′ q_χ Z′_μ χ̄γ^μχ"),
               _t([("mu", True), ("mu", False), ("Zp", False)], "vector", "g_mt", "g′ Z′_μ μ̄γ^μμ"),
               _t([("tau", True), ("tau", False), ("Zp", False)], "vector", "-g_mt", "−g′ Z′_μ τ̄γ^μτ"),
               _t([("nu_mu", True), ("nu_mu", False), ("Zp", False)], "vector", "g_mt", "g′ Z′_μ ν̄_μγ^μP_Lν_μ"),
               _t([("nu_tau", True), ("nu_tau", False), ("Zp", False)], "vector", "-g_mt",
                  "−g′ Z′_μ ν̄_τγ^μP_Lν_τ")],
        couplings=[_c("g_mt", 1e-3, "the L_μ − L_τ gauge coupling g′ (Holst, Hooper & Krnjaic, arXiv:2107.09067)"),
                   _c("q_chi", 1.0, "the dark matter's unit L_μ − L_τ charge")],
        fitted="g_mt", bind=True, slots={"g_chi": "q_chi*g_mt", "g_q": "g_mt"}, ties=[("g_chi", "g_q", "q_chi")],
        assumptions=["m_Z′ = 3m_χ at the benchmark",
                     "the kinetic mixing ε ≈ −g′/70 is the μ and τ loops', computed by the engine, not a free "
                     "parameter"]),
    # --- pseudoscalar and scalar mediators -----------------------------------------------------------------------
    "alp_portal": TypedBenchmark(
        couplings=[_c("g_chi", 0.5, "Coy dark matter (arXiv:1401.6458)"),
                   _c("g_l", 1.0, "one Yukawa-like factor for leptons and quarks (Dolan et al.'s √2 g_Y)"),
                   _c("g_q", 1.0, "one Yukawa-like factor for leptons and quarks (Dolan et al.'s √2 g_Y)")],
        fitted="g_chi",
        assumptions=["the ALP's gluon and photon couplings are not included"]),
    "scalar_mediator": TypedBenchmark(
        couplings=[_c("g_chi", 1.0, "the LHC DM Working Group's spin-0 benchmark (arXiv:1703.05703)"),
                   _c("g_q", 1.0, "g_q = 1 with Yukawa scaling (arXiv:1703.05703)")],
        fitted="g_chi", assumptions=["no lepton coupling"]),
    # --- t-channel --------------------------------------------------------------------------------------------------
    **{entry_id: TypedBenchmark(
        phase="unbroken",
        fields=[DM_MAJORANA if majorana else DM,
                {"name": "phi", "role": "mediator", "spin": 0, "dark_parity": -1,
                 "charges": {"su3": "3" if coloured else "1", "hypercharge": charge}},
                {"name": flavour, "role": "standard_model", "spin": 0.5, "chirality": "R", "generations": 1,
                 "charges": {"su3": "3" if coloured else "1", "hypercharge": charge}}],
        terms=[_t([(flavour, True), ("chi", False), ("phi", False)], "chiral", "y",
                  f"y φ* χ̄ P_R {'u' if coloured else 'μ'} + h.c.", hc=True)],
        couplings=[_c("y", 1.0, why)], fitted="y",
        no_recoil="" if coloured else ("it scatters on nuclei only through loops (the muon's charge radius, anapole "
                                       "and magnetic moment), which the t-channel engine does not compute (it keeps "
                                       "the tree-level O₁ and O₄), so it predicts no recoils; a signal fit needs "
                                       "those loop operators"),
        assumptions=["λ_Hφ = λ_φ = 0: the benchmark's parameters are the two masses and y only",
                     *(["the χᶜ coupling y′ = 0 (absent in S3D_uR)"] if not majorana else [])])
      for entry_id, majorana, flavour, coloured, charge, why in (
          ("tchannel_uR_majorana", True, "uR", True, 2 / 3, "the S3M_uR coupling λ (arXiv:2504.10597)"),
          ("tchannel_uR_dirac", False, "uR", True, 2 / 3, "the S3D_uR coupling λ (arXiv:2504.10597)"),
          ("lepton_portal_muR", True, "muR", False, -1.0, "Bai & Berger (arXiv:1402.6696)"))},
    # --- the LHC DM Working Group's spin-1 benchmarks ------------------------------------------------------------
    "dmwg_V1": TypedBenchmark(
        couplings=[_c("g_DM", 1.0, "V1 (arXiv:1703.05703, sec. 2.3.1)"), _c("g_q", 0.25, "V1"),],
        fitted="g_DM", assumptions=["V1 has no lepton coupling (g_ℓ = 0)"]),
    "dmwg_A1": TypedBenchmark(
        couplings=[_c("g_DM", 1.0, "A1 as published (arXiv:1703.05703, sec. 2.3.1)"), _c("g_q", 0.25, "A1")],
        fitted="g_DM", assumptions=["A1 has no lepton coupling (g_ℓ = 0)"]),
    # --- extended scalar sectors (UFO models) ------------------------------------------------------------------
    "inert_doublet": TypedBenchmark(
        fields=[{"name": "H2", "role": "dark_matter", "spin": 0, "dark_parity": -1,
                 "charges": {"su2": 2, "hypercharge": 0.5}}, HIGGS],
        terms=[_t([("H", True), ("H", False), ("H2", True), ("H2", False)], "scalar",
                  "-(lam345 + 2*(M_Hpm**2 - m_H2**2)/v**2)", "−λ₃ |H|²|H₂|²", indices="H*[i] H[i] H2*[j] H2[j]"),
               _t([("H", True), ("H", False), ("H2", True), ("H2", False)], "scalar",
                  "-(m_H2**2 + M_A0**2 - 2*M_Hpm**2)/v**2", "−λ₄ |H†H₂|²", indices="H*[i] H2[i] H2*[j] H[j]"),
               _t([("H", True), ("H", True), ("H2", False), ("H2", False)], "scalar",
                  "-(m_H2**2 - M_A0**2)/(2*v**2)", "−(λ₅/2)(H†H₂)² + h.c.", hc=True,
                  indices="H*[i] H2[i] H*[j] H2[j]"),
               _t([("H2", True), ("H2", False), ("H2", True), ("H2", False)], "scalar", "-lam2", "−λ₂ |H₂|⁴")],
        couplings=[_c("lam345", -0.051, "λ₃₄₅ = λ₃ + λ₄ + λ₅ of HP10 (arXiv:1809.07712)"),
                   _c("M_A0", 992.36, "M_A₀ of HP10 (GeV)", 1), _c("M_Hpm", 998.12, "M_H± of HP10 (GeV)", 1),
                   _c("lam2", 0.0005, "the dark self-coupling: the UFO's value, which the engine holds (it enters "
                                      "no 2 → 2 annihilation into Standard Model states, nor scattering)")],
        fitted="lam345", bind=True, held={"lam2": 0.0005},
        slots={"g_chi": "lam345", "m_med": "M_Hpm", "g_q": "M_A0 - m_H2"},
        assumptions=["H₂'s mass is M_H₀, the dark matter's; λ₃, λ₄ and λ₅ follow from λ₃₄₅ and the three masses "
                     "(M_H±² − M_H₀² = (λ₃ − λ₃₄₅)v²/2, M_A₀² − M_H₀² = −λ₅v²), and μ₂² = M_H₀² − λ₃₄₅v²/2",
                     "the Lagrangian computed is Goudelis, Herrmann & Stål's UFO (FeynRules)"]),
    "two_hdm_a": TypedBenchmark(
        phase="broken",
        fields=[DM, {"name": "a", "role": "mediator", "spin": 0, "self_conjugate": True}],
        terms=[_t([("chi", True), ("chi", False), ("a", False)], "pseudoscalar", "y_chi*sqrt(1 - sin_theta**2)",
                  "−i y_χ cos θ a χ̄γ⁵χ (and −i y_χ sin θ A χ̄γ⁵χ)")],
        couplings=[_c("y_chi", 1.0, "y_χ = 1 (arXiv:1810.09420)"),
                   _c("sin_theta", 0.35, "sin θ = 0.35 (ATLAS scenario 5, arXiv:2306.00641)"),
                   _c("tan_beta", 1.0, "tan β = 1 (arXiv:1810.09420)"),
                   _c("M_A", 1000.0, "M_A = M_H = M_H± = 1 TeV, which the engine holds", 1),
                   _c("M_H", 1000.0, "held by the engine", 1), _c("M_Hpm", 1000.0, "held by the engine", 1),
                   _c("lam3", 3.0, "λ₃ = λ_P1 = λ_P2 = 3 (arXiv:1810.09420 eq. (4.5)), held by the engine"),
                   _c("lam_P1", 3.0, "held by the engine"), _c("lam_P2", 3.0, "held by the engine"),
                   _c("sin_beta_alpha", 1.0, "the alignment limit sin(β − α) = 1, held by the engine")],
        fitted="y_chi", bind=True,
        held={"M_A": 1000.0, "M_H": 1000.0, "M_Hpm": 1000.0, "lam3": 3.0, "lam_P1": 3.0, "lam_P2": 3.0,
              "sin_beta_alpha": 1.0},
        slots={"g_chi": "y_chi", "g_q": "sin_theta", "g_l": "tan_beta"},
        assumptions=["the Lagrangian computed is the LHC DM Working Group's Pseudoscalar_2HDM UFO (type II): the "
                     "term shown is the dark matter's coupling to the light pseudoscalar a (mass M_a); the heavy "
                     "states, the potential and the Yukawas are the UFO's, set by the parameters listed"]),
    # --- electroweak multiplets ---------------------------------------------------------------------------------
    "wino": TypedBenchmark(couplings=[], fitted=None,
                           assumptions=[NO_FREE_COUPLING, "the charged states are 165 MeV heavier (radiative)"]),
    "higgsino": TypedBenchmark(couplings=[], fitted=None,
                               assumptions=[NO_FREE_COUPLING, "the charged state is 341 MeV heavier (radiative)"]),
    "quintuplet": TypedBenchmark(couplings=[], fitted=None, assumptions=[NO_FREE_COUPLING]),
    "quintuplet_dirac": TypedBenchmark(
        couplings=[_c("delta_m0", 2.2e-4, "the neutral splitting δm₀ in GeV from the dimension-7 operator "
                                          "(Bottaro et al., arXiv:2205.04486, allow 0.21–3 MeV)", 1)],
        fitted=None, bind=True, slots={"g_q": "delta_m0"},
        assumptions=[NO_FREE_COUPLING, "the dimension-7 operator (y₀/Λ³)O₀ enters only through δm₀"]),
}
