"""Write the mediator cards (layer 3) of the interaction library.

Every mediator model is reduced onto the Lagrangians L1–L20 of arXiv:1308.6288
(Table 1) by exact identities, in that paper's conventions (Bjorken–Drell;
q = p' − p = k − k', P = p + p', K = k + k'):
- a heavy scalar exchanged between J = g χ̄Γχ + g_N N̄Γ'N gives +g g_N/m² (χ̄Γχ)(N̄Γ'N),
  a heavy vector −g g_N/m²; the propagator m²/(q² + m²) is kept (``mediator_mass``);
- the Gordon identities χ̄γ^μχ = [P^μ χ̄χ + χ̄iσ^{μν}q_νχ]/(2m_χ) and
  N̄γ_μN = [K_μ N̄N − N̄iσ_{μα}q^αN]/(2m_N) turn vector currents into L5, L6, L9, L10 (and
  L7, L11, L13, L14 with an axial partner);
- a nucleon vector current N̄[g_V γ_μ − g_T iσ_{μν}q^ν/(2m_N)]N (g_T the Pauli coupling,
  e κ_N for the photon) becomes [g_V K_μ N̄N − (g_V + g_T) N̄iσ_{μα}q^αN]/(2m_N);
- photon exchange gives −J_χ·J_N/q² (massless: ``q_power`` −2).

**A sign, corrected on 2026-10-01 (DM8).** The library's transcriptions of Table 1
for the six operators with one explicit factor q^α (L6, L9, L11, L12, L14, L18)
carry the opposite overall sign to an explicit reduction with q = p′ − p
(``adroit/library/interactions/nr_projection.py``; docs/dm8_lagrangians.md). On
its own a card's overall sign cancels in every rate; in a combination it does
not. The identities above are written with q = p′ − p, so these six cards enter
every combination with the opposite sign (``term``). Before the correction the
dipole, anapole and axial–vector cards had the wrong relative sign between
their spin-orbit-interfering terms: rates on ²³Na off by up to a factor 11, on
¹⁹F by up to 40%.

Nucleon inputs are DirectDM's (arXiv:1708.02678; num_input.py, "updated from PDG 2020 and
lattice results"). Run from the repository root:

    uv run python docs/dm4/make_mediator_cards.py
"""

from __future__ import annotations

import math
from pathlib import Path

import yaml

OUT = Path(__file__).resolve().parents[2] / "adroit/library/interactions/cards/mediators.yaml"
DIRECTDM = "DirectDM num_input.py (arXiv:1708.02678)"
M_V = 246.2

# DirectDM's inputs
ALPHA = 1.0 / 137.035999084
E = math.sqrt(4.0 * math.pi * ALPHA)
G_F, SW2, M_Z, M_H = 1.1663787e-5, 0.23121, 91.1876, 125.10
M_P, M_N = 0.938272081, 0.939565413
G_A, DU_PLUS_DD, DS = 1.2756, 0.440, -0.035
SIGMA_P = {"u": 17e-3, "d": 32e-3, "s": 52.9e-3}     # GeV: m_q <N|q̄q|N>
SIGMA_N = {"u": 15e-3, "d": 36e-3, "s": 52.9e-3}
MU_P, MU_N = 2.793, -1.913                           # nuclear magnetons


def f_nucleon(sigmas: dict[str, float], mass: float) -> float:
    """The Higgs–nucleon coupling f_N = Σ_q f_Tq + (2/9)(1 − Σ_q f_Tq) (three heavy quarks)."""
    light = sum(sigmas.values()) / mass
    return light + 2.0 / 9.0 * (1.0 - light)


DELTA_U, DELTA_D = (DU_PLUS_DD + G_A) / 2.0, (DU_PLUS_DD - G_A) / 2.0
CONSTANTS = {
    "e": (E, "1", "the proton charge, sqrt(4π α) with α = 1/137.035999084", DIRECTDM),
    "Q_p": (1.0, "1", "the proton charge in units of e", ""),
    "Q_n": (0.0, "1", "the neutron charge", ""),
    "kappa_p": (MU_P - 1.0, "1", "the proton's anomalous magnetic moment (μ_p − 1)", DIRECTDM),
    "kappa_n": (MU_N, "1", "the neutron's anomalous magnetic moment", DIRECTDM),
    "G_F": (G_F, "GeV^-2", "the Fermi constant", DIRECTDM),
}


def param(name, default, unit, description, prior="fixed", low=None, high=None, source=""):
    entry = {"name": name, "unit": unit, "default": float(default), "description": description,
             "prior": prior}
    if prior != "fixed":
        entry.update(low=float(low), high=float(high))
    if source:
        entry["source"] = source
    return entry


def constant(name):
    value, unit, description, source = CONSTANTS[name]
    return param(name, value, unit, description, source=source)


def coupling(name, description, default=1.0):
    return param(name, default, "1", description, "log_uniform", 1e-6, 4.0 * math.pi)


def mediator_mass(default=1000.0):
    return param("m_med", default, "GeV", "the mediator mass", "log_uniform", 1e-3, 1e4)


M_M = param("m_M", M_V, "GeV", "the scale of the L_j (cancels in every result)")


ONE_Q = {"L06", "L09", "L11", "L12", "L14", "L18"}     # see the module docstring


def term(target, factor, couplings, powers, q_power=0):
    sign = -1.0 if target in ONE_Q else 1.0
    return {"target": target, "factor": sign * float(factor), "couplings": couplings,
            "powers": powers, "q_power": q_power}


def vector_nucleon(prefix, lagr, couplings_v, couplings_t, powers, sign, q_power=0):
    """sign × [g_V L_a − (g_V + g_T) L_b]: the nucleon side of a vector current (Gordon)."""
    a, b = lagr
    out = [term(a, sign, couplings_v, powers, q_power),
           term(b, -sign, couplings_v, powers, q_power)]
    if couplings_t:
        out.append(term(b, -sign, couplings_t, powers, q_power))
    return out


def vector_vector(chi, nv, nt, extra_powers, sign):
    """sign × (χ̄γ^μχ)(N̄Γ_μN) = sign m_M²/(4 m_χ m_N) [g_V L5 − (g_V+g_T) L6 + g_V L9 − (g_V+g_T) L10],
    plus the spin–orbit term of the nucleon density that Table 1's leading-order L5 leaves out.

    Table 1 reduces L5 to O1 alone. The scalar density N̄N also carries a spin–orbit
    term of the same order as O3, so the explicit reduction gives
    c3 = g_T + g_V/2 (the Thomas-precession combination; nr_projection.py), where the
    L-cards alone give g_T + g_V. The direct O3 term removes the extra g_V/2.
    """
    powers = {"m_M": 2, "m_chi": -1, "m_N": -1, **extra_powers}
    s = sign / 4.0
    spin_orbit = [term("O3", -2.0 * s, chi + [nv], dict(extra_powers))]
    return (vector_nucleon("", ("L05", "L06"), chi + [nv], chi + [nt] if nt else [], powers, s)
            + vector_nucleon("", ("L09", "L10"), chi + [nv], chi + [nt] if nt else [], powers, s)
            + spin_orbit)


def card(id_, name, description, interaction, parameters, terms, **extra):
    base = {"id": id_, "name": name, "layer": "mediator", "description": description,
            "interaction": interaction, "parameters": parameters, "terms": terms,
            "isospin_variants": False, "kinematics": ["elastic", "inelastic", "exothermic"],
            "constraint_tiers": [1, 2, 3], "references": ["arXiv:1308.6288"]}
    base.update(extra)
    return base


def scalar_family() -> list[dict]:
    out = []
    shapes = [("M_scalar", "scalar", "χ̄χ", "N̄N", "L01", 1.0, "gS"),
              ("M_pseudoscalar", "pseudoscalar", "iχ̄γ⁵χ", "iN̄γ⁵N", "L04", -1.0, "gP"),
              ("M_scalar_pseudoscalar", "scalar–pseudoscalar", "χ̄χ", "iN̄γ⁵N", "L02", 1.0, "gP"),
              ("M_pseudoscalar_scalar", "pseudoscalar–scalar", "iχ̄γ⁵χ", "N̄N", "L03", 1.0, "gS")]
    for id_, what, chi, nuc, target, sign, g in shapes:
        dropped = (["the pion- and eta-pole momentum dependence of a quark-level pseudoscalar "
                    "coupling; g_N is an effective nucleon coupling"] if "iN̄γ⁵N" in nuc else [])
        out.append(card(
            id_, f"A {what} mediator",
            f"A spin-0 mediator φ of mass m_med coupling as g_χ φ {chi} and g_N φ {nuc}. Its "
            f"exchange gives {'−' if sign < 0 else '+'}g_χ g_N/m_med² × {target} with the "
            "propagator m_med²/(q² + m_med²), so a light mediator makes the interaction "
            "long-range.",
            f"g_χ φ {chi} + g_N φ {nuc}",
            [coupling("g_chi", "the dark matter coupling"),
             coupling(f"{g}_p", "the proton coupling", 1e-3),
             coupling(f"{g}_n", "the neutron coupling", 1e-3), mediator_mass(), M_M],
            [term(target, sign, ["g_chi", f"{g}_{{N}}"], {"m_med": -2})],
            mediator_mass="m_med", dropped=dropped,
            validity=[{"kind": "spin_half", "note": "spin-1/2 dark matter"},
                      {"kind": "perturbative", "note": "couplings below 4π"}]))
    return out


def vector_family() -> list[dict]:
    chi = ["g_chi"]
    med = {"m_med": -2}
    common = [coupling("g_chi", "the dark matter coupling"), mediator_mass(), M_M]
    vector_params = [coupling("gV_p", "the proton vector coupling", 1e-3),
                     coupling("gV_n", "the neutron vector coupling", 1e-3),
                     param("gT_p", 0.0, "1", "the proton Pauli (tensor) coupling"),
                     param("gT_n", 0.0, "1", "the neutron Pauli (tensor) coupling")]
    axial_params = [coupling("gA_p", "the proton axial coupling", 1e-3),
                    coupling("gA_n", "the neutron axial coupling", 1e-3)]
    validity = [{"kind": "spin_half", "note": "spin-1/2 dark matter"},
                {"kind": "perturbative", "note": "couplings below 4π"}]
    out = [
        card("M_vector", "A vector mediator",
             "A spin-1 mediator V coupling to the dark matter's vector current and to the "
             "nucleon's vector current, with an optional Pauli coupling. Its exchange gives "
             "−(χ̄γ^μχ)(N̄Γ_μN)/m_med², reduced by the Gordon identities to L5, L6, L9 and L10; "
             "at leading order c1 = −g_χ g_V/m_med².",
             "g_χ V_μ χ̄γ^μχ + V^μ N̄[g_V γ_μ − g_T iσ_μν q^ν/(2m_N)]N",
             common + vector_params,
             vector_vector(chi, "gV_{N}", "gT_{N}", med, -1.0), mediator_mass="m_med",
             validity=validity + [{"kind": "dirac_only",
                                   "note": "a Majorana particle has no vector current"}]),
        card("M_axial", "An axial-vector mediator",
             "A spin-1 mediator coupling to the axial currents of dark matter and nucleon; its "
             "exchange gives −g_χ g_A/m_med² × L15, the standard spin-dependent interaction "
             "(c4 = 4 g_χ g_A/m_med²).",
             "g_χ A_μ χ̄γ^μγ⁵χ + g_A A^μ N̄γ_μγ⁵N", common + axial_params,
             [term("L15", -1.0, ["g_chi", "gA_{N}"], med)], mediator_mass="m_med",
             dropped=["the longitudinal part q^μq^ν/m_med² of the massive propagator",
                      "the induced pseudoscalar (pion-pole) term of the nucleon axial current"],
             validity=validity),
        card("M_vector_axial", "A mediator with vector dark matter and axial nucleon couplings",
             "Its exchange gives −(g_χ g_A/m_med²)(m_M/2m_χ)(L7 + L11): O7 and O9 at leading "
             "order.",
             "g_χ V_μ χ̄γ^μχ + g_A V^μ N̄γ_μγ⁵N", common + axial_params,
             [term(t, -0.5, ["g_chi", "gA_{N}"], {"m_M": 1, "m_chi": -1, **med})
              for t in ("L07", "L11")], mediator_mass="m_med",
             dropped=["the induced pseudoscalar (pion-pole) term of the nucleon axial current"],
             validity=validity + [{"kind": "dirac_only",
                                   "note": "a Majorana particle has no vector current"}]),
        card("M_axial_vector", "A mediator with axial dark matter and vector nucleon couplings",
             "Its exchange gives −(g_χ/m_med²)(m_M/2m_N)[g_V L13 − (g_V + g_T) L14]: O8 and O9 "
             "at leading order.",
             "g_χ V_μ χ̄γ^μγ⁵χ + V^μ N̄[g_V γ_μ − g_T iσ_μν q^ν/(2m_N)]N",
             common + vector_params,
             vector_nucleon("", ("L13", "L14"), ["g_chi", "gV_{N}"], ["g_chi", "gT_{N}"],
                            {"m_M": 1, "m_N": -1, **med}, -0.5), mediator_mass="m_med",
             validity=validity),
    ]
    pseudo_dirac = dict(out[0])
    pseudo_dirac.update(
        id="M_pseudo_dirac_vector", name="Pseudo-Dirac dark matter with a vector mediator",
        description="Two Majorana states split by δ, coupled off-diagonally to a vector "
                    "mediator: χ₁ scatters into χ₂. The nonrelativistic reduction is that of "
                    "the vector mediator; the splitting enters through v_min (inelastic "
                    "scattering, or exothermic for a populated heavier state).",
        interaction="g_χ V_μ χ̄₂γ^μχ₁ + h.c. + V^μ N̄Γ_μN",
        kinematics=["inelastic", "exothermic"],
        validity=validity + [{"kind": "inelastic_only", "note": "needs δ ≠ 0"}])
    return out + [pseudo_dirac]


def portals() -> list[dict]:
    f_p, f_n = f_nucleon(SIGMA_P, M_P), f_nucleon(SIGMA_N, M_N)
    v_h = (math.sqrt(2.0) * G_F) ** -0.5
    ga_p = (DELTA_U - DELTA_D - DS) / 2.0
    ga_n = (DELTA_D - DELTA_U - DS) / 2.0
    root2 = math.sqrt(2.0)
    zc = ["G_F"]
    z_terms = (vector_vector(zc + ["gV_chi"], "gV_{N}", "", {}, -root2)
               + [term(t, root2 / 2.0, zc + ["gV_chi", "gA_{N}"], {"m_M": 1, "m_chi": -1})
                  for t in ("L07", "L11")]
               + [term("L13", root2 / 2.0, zc + ["gA_chi", "gV_{N}"], {"m_M": 1, "m_N": -1}),
                  term("L14", -root2 / 2.0, zc + ["gA_chi", "gV_{N}"], {"m_M": 1, "m_N": -1}),
                  term("L15", -root2, zc + ["gA_chi", "gA_{N}"], {})])
    return [
        card("M_higgs_portal", "The Higgs portal (fermion dark matter)",
             "Dark matter coupling to the Higgs boson as y_χ h χ̄χ (for a singlet, from "
             "(H†H)χ̄χ/Λ with y_χ = v/Λ). The Higgs couples to nucleons as f_N m_N/v, with f_N "
             "from the light-quark σ-terms and the heavy-quark (gluon) contribution. Its "
             "exchange gives y_χ f_N m_N/(v m_h²) × L1.",
             "y_χ h χ̄χ + (f_N m_N/v) h N̄N",
             [param("y_chi", 0.1, "1", "the dark matter–Higgs coupling", "log_uniform", 1e-6, 1.0),
              param("fN_p", f_p, "1", "the Higgs–proton coupling f_p", source=DIRECTDM
                    + ": σ_u, σ_d, σ_s of the proton; f_N = Σ f_Tq + (2/9)(1 − Σ f_Tq)"),
              param("fN_n", f_n, "1", "the Higgs–neutron coupling f_n", source=DIRECTDM),
              param("m_nucleon", 0.5 * (M_P + M_N), "GeV", "the nucleon mass", source=DIRECTDM),
              param("v_h", v_h, "GeV", "the Higgs vacuum value (√2 G_F)^(−1/2)", source=DIRECTDM),
              param("m_h", M_H, "GeV", "the Higgs mass", source=DIRECTDM), M_M],
             [term("L01", 1.0, ["y_chi", "fN_{N}"], {"m_nucleon": 1, "v_h": -1, "m_h": -2})],
             mediator_mass="m_h",
             validity=[{"kind": "spin_half", "note": "spin-1/2 dark matter"}],
             neighbours=[]),
        card("M_z_portal", "The Z portal (Dirac fermion dark matter)",
             "Dark matter coupling to the Z as (g/2c_W) Z_μ χ̄γ^μ(g_V − g_A γ⁵)χ, exchanging a Z "
             "with nucleons: L_eff = −√2 G_F [χ̄γ^μ(g_V − g_Aγ⁵)χ][N̄γ_μ(g_V^N − g_A^N γ⁵)N]. "
             "g_V^p = 1/2 − 2 s_W², g_V^n = −1/2; g_A^N from the quark spin fractions Δq.",
             "(g/2c_W) Z_μ χ̄γ^μ(g_V − g_A γ⁵)χ",
             [param("gV_chi", 0.5, "1", "the dark matter's vector Z charge", "uniform", -1.0, 1.0),
              param("gA_chi", 0.5, "1", "the dark matter's axial Z charge", "uniform", -1.0, 1.0),
              param("gV_p", 0.5 - 2.0 * SW2, "1", "the proton's vector Z charge, 1/2 − 2 s_W²",
                    source=DIRECTDM + ": s_W² = 0.23121 (MS-bar at m_Z)"),
              param("gV_n", -0.5, "1", "the neutron's vector Z charge"),
              param("gA_p", ga_p, "1", "the proton's axial Z charge, (Δu − Δd − Δs)/2",
                    source=DIRECTDM + ": g_A = 1.2756, Δu + Δd = 0.440, Δs = −0.035"),
              param("gA_n", ga_n, "1", "the neutron's axial Z charge, (Δd − Δu − Δs)/2",
                    source=DIRECTDM),
              constant("G_F"), param("m_Z", M_Z, "GeV", "the Z mass", source=DIRECTDM), M_M],
             z_terms, mediator_mass="m_Z",
             dropped=["the nucleon's weak magnetic moment (Pauli terms of the Z current)",
                      "the induced pseudoscalar (pion-pole) term of the nucleon axial current",
                      "the running of s_W² from m_Z to the momentum transfer"],
             validity=[{"kind": "spin_half", "note": "spin-1/2 dark matter"},
                       {"kind": "dirac_only",
                        "note": "a Majorana particle keeps only the axial coupling: set g_V = 0"}]),
    ]


def electromagnetic() -> list[dict]:
    em = [constant("e"), constant("Q_p"), constant("Q_n"), constant("kappa_p"),
          constant("kappa_n"), M_M]
    dipole_powers = {"m_M": 2, "m_N": -1}
    return [
        card("M_magnetic_dipole", "Magnetic dipole dark matter",
             "A neutral Dirac particle with magnetic moment μ_χ, (μ_χ/2) χ̄σ^μν χ F_μν, "
             "exchanging a photon with the nucleon's charge and magnetic moment: "
             "−(e μ_χ m_M²/(2 m_N q²)) [Q L9 − (Q + κ) L10]. At leading order c1 = e μ_χ Q/(2m_χ), "
             "c5 = −2 e μ_χ Q m_N/q², c4 = 2 e μ_χ (Q + κ)/m_N, c6 = −2 e μ_χ (Q + κ) m_N/q² (up to one overall sign); "
             "the charge terms reproduce Z²[1/E_R − (1/v²)(1/(2m_T) + 1/m_χ)].",
             "(μ_χ/2) χ̄σ^μν χ F_μν",
             [param("mu_chi", 1.5e-8, "GeV^-1", "the magnetic moment (1.5e-8 GeV⁻¹ ≈ 1e-21 e cm)",
                    "log_uniform", 1e-14, 1e-4)] + em,
             [term("L09", -0.5, ["e", "mu_chi", "Q_{N}"], dipole_powers, -2),
              term("L10", 0.5, ["e", "mu_chi", "Q_{N}"], dipole_powers, -2),
              term("L10", 0.5, ["e", "mu_chi", "kappa_{N}"], dipole_powers, -2)],
             validity=[{"kind": "spin_half", "note": "spin-1/2 dark matter"},
                       {"kind": "dirac_only", "note": "a Majorana particle has no magnetic moment"}],
             references=["arXiv:1308.6288", "arXiv:2104.12785"]),
        card("M_anapole", "Anapole dark matter",
             "An anapole moment 𝒜, 𝒜 χ̄γ^μγ⁵χ ∂^νF_μν, a contact coupling of the axial current "
             "to the nucleon's electromagnetic current: (e 𝒜 m_M/(2m_N)) [Q L13 − (Q + κ) L14], "
             "giving c8 = 2 e Q 𝒜 and c9 = 2 e (Q + κ) 𝒜.",
             "𝒜 χ̄γ^μγ⁵χ ∂^ν F_μν",
             [param("anapole", 1e-5, "GeV^-2", "the anapole moment 𝒜", "log_uniform", 1e-12,
                    1e-1)] + em,
             [term("L13", 0.5, ["anapole", "e", "Q_{N}"], {"m_M": 1, "m_N": -1}),
              term("L14", -0.5, ["anapole", "e", "Q_{N}"], {"m_M": 1, "m_N": -1}),
              term("L14", -0.5, ["anapole", "e", "kappa_{N}"], {"m_M": 1, "m_N": -1})],
             validity=[{"kind": "spin_half", "note": "spin-1/2 dark matter; allowed for Majorana"}],
             references=["arXiv:1308.6288", "arXiv:2104.12785"]),
        card("M_charge_radius", "Charge-radius dark matter",
             "A charge-radius coupling b χ̄γ^μχ ∂^νF_μν: a contact coupling of the vector current "
             "to the nucleon's electromagnetic current, reduced like a vector mediator; at leading "
             "order c1 = e b Q.",
             "b χ̄γ^μχ ∂^ν F_μν",
             [param("b_chi", 1e-5, "GeV^-2", "the charge-radius coupling b", "log_uniform", 1e-12,
                    1e-1)] + em,
             vector_vector(["b_chi", "e"], "Q_{N}", "kappa_{N}", {}, 1.0),
             validity=[{"kind": "spin_half", "note": "spin-1/2 dark matter"},
                       {"kind": "dirac_only", "note": "a Majorana particle has no vector current"}],
             references=["arXiv:1308.6288", "arXiv:2104.12785"]),
    ]


def links(cards: list[dict]) -> None:
    """The declared neighbour links between mediator cards."""
    declared = {
        "M_scalar": [("M_higgs_portal", "specialise_couplings"),
                     ("M_pseudoscalar", "change_lorentz_structure"),
                     ("M_scalar_pseudoscalar", "change_lorentz_structure"),
                     ("M_pseudoscalar_scalar", "change_lorentz_structure")],
        "M_vector": [("M_z_portal", "specialise_couplings"),
                     ("M_charge_radius", "specialise_couplings"),
                     ("M_pseudo_dirac_vector", "add_mass_splitting"),
                     ("M_axial", "change_lorentz_structure"),
                     ("M_vector_axial", "change_lorentz_structure"),
                     ("M_axial_vector", "change_lorentz_structure"),
                     ("M_magnetic_dipole", "change_lorentz_structure")],
        "M_axial": [("M_z_portal", "specialise_couplings")],
        "M_axial_vector": [("M_anapole", "specialise_couplings")],
    }
    for c in cards:
        c["neighbours"] = [{"target": t, "deformation": d} for t, d in declared.get(c["id"], [])]


def main() -> None:
    cards = scalar_family() + vector_family() + portals() + electromagnetic()
    links(cards)
    header = ("# Layer 3: mediator models, reduced onto L1–L20 (arXiv:1308.6288, Table 1).\n"
              "# Generated by docs/dm4/make_mediator_cards.py, which records the identities used.\n")
    OUT.write_text(header + yaml.safe_dump(cards, sort_keys=False, allow_unicode=True, width=100))
    print(f"wrote {len(cards)} cards to {OUT}")


if __name__ == "__main__":
    main()
