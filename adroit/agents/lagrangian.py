"""The two language-model agents of Path 1 for arbitrary Lagrangians (DM8). Opt-in.

- **Intake** turns a user's description (a Lagrangian, or a particle
  content) into a typed ``ModelSpec``.
- **Derivation** matches a ``ModelSpec`` at tree level onto DirectDM's
  quark-level operators, as formulas in the model's own symbols
  (``derivation.Derivation``). Run twice with different models, the two
  derivations are compared numerically (``derivation.compare``); a
  disagreement stops the run at a human gate.

The agents write formulas and structure, never numbers: every value is
evaluated afterwards by deterministic code against a closed symbol table,
behind a tokenizer that admits only arithmetic and known symbols.
"""

from __future__ import annotations

import json

from adroit.agents.llm import StructuredLLM
from adroit.core.model_spec import ModelSpec
from adroit.core.prompts import TERSE_CLAUSE
from adroit.library.interactions import derivation as dv
from adroit.library.interactions import registry

DEFAULT_DERIVER = "claude-opus-5-5"
DEFAULT_CHECKER = "gpt-5.6-sol"

INTAKE_SYSTEM = """You turn a dark matter model, given in words or as a Lagrangian, into JSON for the ModelSpec schema.

Rules:
- One entry per field: role (dark_matter, mediator, standard_model, other), spin, self_conjugate
  (real scalar, Majorana fermion, real vector), chirality (L or R for a Weyl fermion, else ""),
  generations, mass_gev (null for massless or Standard Model fields unless it matters), and a
  mass_justification. Charges: su3 ("1", "3", "3bar", "8"), su2 (multiplet dimension), hypercharge
  (Q = T3 + Y) if the model is written above electroweak symmetry breaking (phase "unbroken");
  otherwise electric_charge (phase "broken"). Charges under new U(1)s go in "extra".
- Standard Model fermions coupling with one universal coupling may be one field (e.g. "q" for all
  quarks); say so in assumptions.
- One entry per coupling, with its value if the user gives one, its mass_dimension, and a
  justification. If the user gives no value, leave value null and say so.
- One entry per interaction term: its fields in order, each with conjugate true for ψ̄, ψ† or φ*;
  lorentz (scalar, pseudoscalar, vector, axial, chiral, tensor, dipole, anapole, charge_radius, other;
  pseudoscalar means ψ̄ iγ5 ψ; a coupling to a photon or gluon through its field strength is dipole
  (ψ̄σ^{μν}ψ F_μν, or with iγ5), anapole (ψ̄γ^μγ5ψ ∂^νF_μν) or charge_radius (ψ̄γ^μψ ∂^νF_μν), never vector or
  axial, which mean A_μ itself and need a charged field); coupling: the term's FULL coefficient in L, sign and numerical factors included, as an
  expression in the couplings, the masses m_<field name> (m_q for each quark's own mass when q stands
  for several flavours) and v, e, pi, m_h, m_Z, m_W, in Python syntax; e.g. the term g_q (m_q/v) φ q̄q
  has coupling "g_q*m_q/v", and −(λ v/2) h S S has coupling "-lam_hs*v/2"; plus_hc if the user writes
  "+ h.c."; text (the term in conventional notation).
- Put in "dropped" every part of the user's model you leave out (other interactions, loops, extra
  states), and in "assumptions" every choice you made that the user did not state.
- The dark matter is a thermal freeze-out relic. Give every field its dark_parity under the symmetry
  that keeps the dark matter stable (−1 odd, +1 even; Standard Model fields +1), and name the symmetry in
  "stability" (e.g. "Z2: chi → −chi"). If the user states none, give the minimal Z2 under which the dark
  matter is odd and every term even, and say so in assumptions. "relic_fraction" is the fraction of
  Ωh² = 0.12 the user means the model to supply (1 unless stated); "cosmology" keeps its default unless
  the user states a non-standard history (reheating temperature, early matter domination, entropy release).
- Name Standard Model fields: q (every quark, one coupling), u d s c b t, l (every charged lepton),
  e mu tau, nu, h, A (photon), Z, W, G (gluon).
- Never invent couplings or fields the user did not imply. Return only the JSON object.""" + TERSE_CLAUSE

BASIS = """DirectDM's operator basis (arXiv:1708.02678). L_eff = Σ Ĉ Q, with Ĉ dimensionful (GeV^(4-d)).
Coefficient names: C<d><i><f>, e.g. C61u, C75b, C51; f in u, d, s, c, b, e, mu, tau where present.
Dirac fermion χ (dm_type "D"):
  d=5: C51: e/(8π²)(χ̄σ^{μν}χ)F_μν ; C52: e/(8π²)(χ̄σ^{μν}iγ5χ)F_μν
  d=6: C61f: (χ̄γ^μχ)(f̄γ_μf) ; C62f: (χ̄γ^μγ5χ)(f̄γ_μf) ; C63f: (χ̄γ^μχ)(f̄γ_μγ5f) ; C64f: (χ̄γ^μγ5χ)(f̄γ_μγ5f)
  d=7: C71: αs/(12π)(χ̄χ)GG ; C72: αs/(12π)(χ̄iγ5χ)GG ; C73: αs/(8π)(χ̄χ)GG̃ ; C74: αs/(8π)(χ̄iγ5χ)GG̃
       C75f: m_f(χ̄χ)(f̄f) ; C76f: m_f(χ̄iγ5χ)(f̄f) ; C77f: m_f(χ̄χ)(f̄iγ5f) ; C78f: m_f(χ̄iγ5χ)(f̄iγ5f)
       C79f: m_f(χ̄σ^{μν}χ)(f̄σ_{μν}f) ; C710f: m_f(χ̄iσ^{μν}γ5χ)(f̄σ_{μν}f)
Majorana fermion ("M"): only C62f, C64f, C71–C74, C75f–C78f, each operator with an extra factor 1/2
  (e.g. C64f: ½(χ̄γ^μγ5χ)(f̄γ_μγ5f); C71: αs/(24π)(χ̄χ)GG).
Complex scalar φ ("C"), d=6: C61f: (φ* i∂↔_μ φ)(f̄γ^μf) ; C62f: (φ* i∂↔_μ φ)(f̄γ^μγ5f) ;
  C63f: m_f(φ*φ)(f̄f) ; C64f: m_f(φ*φ)(f̄iγ5f) ; C65: αs/(12π)(φ*φ)GG ; C66: αs/(8π)(φ*φ)GG̃
Real scalar ("R"): C63f, C64f, C65, C66 with an extra factor 1/2 (C63f: (m_f/2)(φφ)(f̄f)).
Flavour scheme: "flavours" 5 means the coefficients are given at μ = m_Z (u,d,s,c,b,e,mu,tau), 4 at
m_b (no b), 3 at 2 GeV (u,d,s,e,mu,tau). Use 5 unless a mediator is lighter than m_Z."""

DERIVATION_SYSTEM = """You derive, at tree level, the coefficients of DirectDM's quark-level operators for a dark matter
model given as a ModelSpec. Return JSON for the Derivation schema.

""" + BASIS + """

Conventions:
- Integrate out each heavy mediator at zero momentum. For L ⊃ g1 S O1 + g2 S O2 (scalar S of mass M),
  L_eff ⊃ +(g1 g2/M²) O1 O2. For L ⊃ V_μ (g1 J1^μ + g2 J2^μ) (vector V of mass M), L_eff ⊃ −(g1 g2/M²) J1·J2.
  For a complex mediator or a t-channel exchange, Fierz-rearrange and state it in "justifications".
- A coupling to quarks proportional to their Yukawa coupling, y_q = √2 m_q/v, matches the m_f factor of
  the d=7 operators: e.g. (g_q m_q/v) S q̄q gives C75q = g_chi*g_q/(v*m_S**2).
- A quark heavier than the flavour scheme's scale (the top in the five-flavour scheme) is not in the basis:
  integrate it out onto the gluon operators, e.g. m_t t̄t → −(α_s/12π) G G, and state the relation and its
  sign convention in "justifications".
- A coupling to the photon (a dipole, an anapole, a charge radius, a kinetic mixing) reaches every charged
  fermion of the flavour scheme, leptons included, through the electromagnetic current e Σ_f Q_f f̄γ^μf
  (e > 0, Q_u = 2/3, Q_e = −1). The dipole operators C51 and C52 are already in the basis.
- Formulas may use only: the couplings of the ModelSpec by name, the masses m_<field name> of its fields,
  and these Standard Model constants: v, m_h, m_W, m_Z, G_F, e, alpha, s_w2, pi, m_u, m_d, m_s, m_c, m_b,
  m_t, m_e, m_mu, m_tau. Functions: sqrt, exp, log, abs. Write Python syntax (x**2, not x^2).
- Give one term per nonzero coefficient, per flavour. Omit zero coefficients.
- "library_card": if the model is exactly one of the library's mediator cards listed below, its id,
  and "library_values" the card's parameters as formulas; otherwise "".
- "dropped": every effect left out (loops, mediator propagation when the mediator is light, operators
  beyond the basis); "assumptions": every choice the model does not fix; "justifications": one line per
  coefficient saying how it arises.
- Return only the JSON object.""" + TERSE_CLAUSE


def library_menu() -> str:
    """The library's mediator cards, one line each, for the derivation prompt."""
    return "\n".join(f"- {c.id}: {c.interaction}" for c in registry.cards().values()
                     if c.layer.value == "mediator")


class IntakeAgent:
    """A model in words → ``ModelSpec``."""

    def __init__(self, llm: StructuredLLM, model: str = DEFAULT_DERIVER) -> None:
        self.llm, self.model = llm, model

    def run(self, description: str, run_id: str | None = None) -> ModelSpec:
        """The typed model the description states."""
        messages = [{"role": "user", "content": f"The model:\n\n{description}"}]
        return self.llm.complete_structured(INTAKE_SYSTEM, messages, ModelSpec, model=self.model,
                                            run_id=run_id, actor="lagrangian_intake")


class DerivationAgent:
    """A ``ModelSpec`` → DirectDM Wilson coefficients as formulas."""

    def __init__(self, llm: StructuredLLM, model: str = DEFAULT_DERIVER) -> None:
        self.llm, self.model = llm, model

    def run(self, spec: ModelSpec, run_id: str | None = None) -> dv.Derivation:
        """The tree-level matching, as a ``Derivation`` (its derived_by is this agent's model)."""
        content = ("The model (ModelSpec JSON):\n" + json.dumps(spec.model_dump(), indent=1)
                   + "\n\nThe library's mediator cards:\n" + library_menu())
        result = self.llm.complete_structured(DERIVATION_SYSTEM, [{"role": "user", "content": content}],
                                              dv.Derivation, model=self.model, run_id=run_id,
                                              actor="lagrangian_derivation")
        return result.model_copy(update={"derived_by": self.model})
