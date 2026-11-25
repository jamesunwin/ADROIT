"""G10's intake: a paper's Lagrangian, in its own conventions, → a ``ModelSpec`` that G1 builds (paid; opt-in).

The agent reads the paper's text around its Lagrangian and the benchmark's inputs, and writes the model in ADROIT's
conventions: the unbroken phase with the Higgs doublet, Q = T₃ + Y, explicit SU(2) contractions, Lagrangian masses.
It writes structure and formulas, never numbers it computed: each of the paper's benchmark inputs is a coupling with
its value, and every derived mass or coupling is a formula in them, which deterministic code evaluates
(``derivation.evaluate_expression``).

**Checked, not trusted.** G1 must build the model (gauge invariance, a stationary vacuum); if it refuses, the agent
sees G1's reason once and may correct the model. The model it returns is then compared with a reference by
``model_building.equivalence`` (G10's gate: the zoo's hand-written models).
"""

from __future__ import annotations

import json

from pydantic import Field

from adroit.agents.llm import StructuredLLM
from adroit.core.model_spec import ModelSpec
from adroit.core.state import StrictModel

DEFAULT_MODEL = "claude-opus-5-5"

GUIDE = """You write a dark matter model from a paper as JSON for ADROIT's ModelSpec, in ADROIT's conventions, so
that its mass-basis calculation (G1) reproduces the paper's spectrum and couplings at the paper's benchmark point.

THE SPEC
- name; phase: "unbroken" (always: write the model above electroweak symmetry breaking with the Higgs doublet H).
- fields: each {name, role (dark_matter | mediator | standard_model | other), spin (0, 0.5, 1),
  self_conjugate (true for a real scalar, a Majorana fermion, a real vector), chirality ("L"/"R" for a Weyl
  fermion, "" otherwise), mass_gev (the Lagrangian mass, see MASSES; null for a field whose mass comes from
  explicit terms or a vev), mass_justification, charges {su3: "1"|"3"|"3bar"|"8", su2: dimension n,
  hypercharge: Y with Q = T3 + Y, extra: {name of a new U(1): charge}}, dark_parity (−1 for the Z2-odd dark
  sector, +1 otherwise), vev_gev (only for a new scalar with a vacuum value)}. Include the Higgs doublet as
  {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}} whenever the
  model couples to it or has electroweak multiplets. Do not list other Standard Model fields unless a term
  couples to them (then e.g. a right-handed up quark uR: spin 0.5, chirality "R", su3 "3", hypercharge 2/3;
  leptons eR: hypercharge −1, chirality "R"; a left-handed doublet lL: su2 2, hypercharge −1/2, chirality "L").
  Standard Model fermions are named as G2 knows them: by flavour (u, d, s, c, b, t, e, mu, tau, nu_e, nu_mu,
  nu_tau: both chiralities); right-handed uR, dR, eR (generations 1: the first flavour; 3: all three), muR, tauR;
  left-handed doublets qL or QL (all quarks), lL or L (all leptons), and one lepton family's doublet Le, Lmu, Ltau;
  all flavours of both chiralities q, l, nu. No other name is a Standard Model fermion. A new vector must not
  take a Standard Model boson's name (A, Z, W, g): name a dark photon e.g. Ad.
- couplings: each {name, value, mass_dimension, justification}. Put EVERY input of the paper's benchmark here
  with its value (masses with mass_dimension 1, mixing angles, couplings), named as the paper names them.
- terms: each {fields: [{field, conjugate}], lorentz, coupling, plus_hc, text, indices}. The term adds
  coupling × (the operator) to L. lorentz: "scalar" (no γ matrices; also for scalar potentials and mass
  terms), "pseudoscalar" (ψ̄ iγ5 ψ), "vector", "axial", "chiral" (ψ̄_a P_R ψ_b: write the left-handed
  partner's term through its hermitian conjugate), "scalar_current" (φ* i∂_μ φ V^μ, i.e. a scalar's gauge-like
  current), "kinetic_mixing" (V_μν X^μν of two vectors: the coupling is the coefficient of V_μν X^μν, e.g.
  −ε/2 for −(ε/2) V_μν F^μν; X is the photon A, declared with role "standard_model", spin 1, self_conjugate true,
  in phase "broken", or the hypercharge boson B in phase "unbroken"). conjugate is true for ψ̄, φ†, φ*. plus_hc: true when the paper writes "+ h.c." for a term that is
  not its own conjugate. coupling is a FORMULA (Python syntax) in the couplings' names, the field masses
  m_<field>, and v (246.22 GeV), pi, m_h, m_Z, m_W, e; functions sqrt, sin, cos, tan, atan, exp, log; I is the
  imaginary unit (e.g. "I*B" for i B a₀H†H₂ + h.c., with plus_hc true). A coupling of SM fermions may use m_q, m_l or
  m_f, each flavour's own mass. A second Higgs doublet Φ (Y = ½, role "other") couples to SM fermions as
  Q̄Φd_R, L̄Φe_R or Q̄Φ̃u_R (fields [qL*, Phi, dR], [lL*, Phi, eR], [qL*, Phi*, uR] with indices "qL*[i,c] Phi[i]
  dR[c]", "lL*[i] Phi[i] eR", "eps[i,j] qL*[i,c] Phi*[j] uR[c]"), in the Higgs basis where H takes the whole vacuum
  value.

CONVENTIONS TO CONVERT
- Hypercharge: ADROIT uses Q = T3 + Y. A paper with Q = T3 + Y/2 has Y twice ADROIT's: halve it.
- The vev: ADROIT's ⟨H⁰⟩ = v/√2 with v = 246.22 GeV. A paper with ⟨H⁰⟩ = v with v ≃ 174 GeV has v_paper = v/√2:
  rewrite its Yukawas and masses accordingly (a mass y v_paper is y v/√2 here).
- Signs and factors: the coupling is the term's full coefficient in L, sign included. A potential V enters L as
  −V. A Majorana mass is −½ M χ̄χ; a Dirac mass −M ψ̄ψ; a real scalar mass −½ m² S²; a complex one −m²|φ|².
- Weyl fields: a vector-like (Dirac) fermion written as two Weyl fields may be one Dirac field (chirality "");
  a Majorana fermion is one self-conjugate field. Keep the paper's Weyl fields where its couplings are chiral.
- A Majorana fermion N made of a right-handed Weyl field (N = N_R + N_R^c): its vector current vanishes and
  N̄_R γ^μ N_R = N̄ γ^μ P_R N = +½ N̄ γ^μ γ5 N (P_R = (1 + γ5)/2; the sign is plus). So a gauge coupling
  g q_N N̄_R γ^μ N_R V_μ is the axial term with coupling +g q_N/2, written in the same sign convention as every
  other field's g q_f f̄ γ^μ f V_μ (one covariant derivative for all fields).
- Kinetic mixing that the paper writes (−(ε/2) F′_μν F^μν, κ V_ν ∂_μF^μν = −(κ/2) V_μν F^μν, or with the
  hypercharge field strength) is one kinetic_mixing term, never its O(ε) currents ε e Q_f f̄γf V written out
  (those leave out the mixing's other couplings, such as V W⁺W⁻). Keep the paper's field strength: mixing with the
  photon's F is with A (phase "broken"), mixing with hypercharge's B is with B (phase "unbroken"). Never convert
  one into the other: −(ε/2c_W) V_μν B^μν is −(ε/2) V_μν F^μν plus a Z mixing (ε t_W/2) V_μν Z^μν. A dark photon given in the mass basis with only
  a coupling ε e Q_f to Standard Model fermions: write that coupling as stated (vector terms to the fermions it
  couples to).
- Never compute a number yourself. If the paper's benchmark gives physical masses or mixing angles, put them as
  couplings and write the Lagrangian masses and couplings as formulas in them (explicit mass terms, below).
  For a scalar sector this means every parameter of the potential (masses, trilinears, quartics, vacuum values)
  as a formula in the stated masses and angles, inverting its mass matrix; never omit a quartic to simplify.
- One mixing sector of fermions is written all in Weyl fields (chirality "L"/"R") or all in four-component
  fields (chirality ""): never a Weyl field and a four-component field in one bilinear or Yukawa term.

KEEP EVERY TERM
- Write every portal of the paper's Lagrangian, a term joining new fields to Standard Model ones: kinetic mixing,
  couplings to Standard Model fermions, Higgs portals. If the benchmark does not fix a portal's value, take the
  value the paper uses or states as typical and list it in "assumptions"; never drop a portal.
- A self-coupling of the new fields alone (a dark quartic) that the benchmark does not fix: leave it out and say
  so in "assumptions"; never invent its value.
- A current such as ε e Q_f J_em, where the paper states it as such, couples to every charged Standard Model
  fermion: write it for all of them (q and l, or flavour by flavour), not only for those open at the benchmark's
  mass.
- The Standard Model's own terms are G1's: its Higgs potential (μ² and λ of H alone, M_h = 125.09 GeV) and its
  fermions' Yukawa couplings to H (their masses). Never write the fermions' Yukawas. Do not write H's own potential
  either, unless a new scalar mixes with H: then the benchmark's physical masses and mixing angle fix the whole
  scalar potential, H's μ² and λ included, and every one of its parameters is a formula in the stated masses (the
  stated h mass included).
- Use every input the benchmark gives: the dark matter's mass, a partner's relative splitting, values marked
  "chosen by the zoo" (where the paper leaves a value free and the reference fixes it), and leave out the terms it
  lists as "left out by the reference".

MASSES
- mass_gev is the Lagrangian mass of a field with no explicit two-field term: for a scalar the m in m²|φ|² (or
  ½ m² φ² if real), for a Dirac fermion M in M ψ̄ψ, for a Majorana fermion M in ½ M χ̄χ.
- A mass that is a formula, or a mass term between two different fields, is an explicit term instead (e.g.
  fields [ψ̄, ψ] lorentz "scalar" coupling "-(M1*cos(theta)**2 + M2*sin(theta)**2)"), and the field's mass_gev
  is null.

SU(2) CONTRACTIONS (indices)
- Multiplets are in the spherical basis, components m = j, j−1, …, −j; for a doublet (φ⁺, φ⁰) with Y = ½.
- Without "indices" a term pairs each field with its conjugate (δ), or two real or identical fields with the
  invariant bilinear. State "indices" whenever a term has more than one possible pairing, or pairs two different
  fields through anything other than δ: a product of factors, each a field (name, * for its conjugate) with its
  SU(2) index then its colour index in brackets, or an invariant tensor; repeated indices are summed. Tensors:
  delta[i,j]; eps[i,j] (doublets, ε₁₂ = +1); metric[m,n] (the invariant bilinear of any dimension); sigma[A,i,j]
  (Pauli); T[A,m,n] (the generator of the field carrying m); cart[A,m] (a triplet's Cartesian component A from
  its spherical ones; cartc for a conjugated triplet); colour delta[c,d], lam[a,c,d], f[a,b,c], eps3[c,d,e].
  Examples: "H*[i] phi[i] phi*[j] H[j]" is (H†φ)(φ†H); "eps[i,j] D[i] H[j] S" is ε^{ij} D_i H_j S;
  "H*[i] sigma[A,i,j] H[j] cart[A,m] Delta[m]" is (H†σ^A H)Δ^A for a real triplet Δ; H̃ = iσ₂H* is
  "eps[i,j] ... H*[j]".
- Every term must be gauge invariant: G1 checks it and refuses one that is not.

EXAMPLE (not from the paper): a complex scalar doublet D (Y = ½, dark, m_D = 500 GeV) with a real singlet S
(dark, m_S = 300 GeV) and L ⊃ −A (D†H) S + h.c. − λ (D†H)(H†D):
{"name": "doublet_singlet", "phase": "unbroken",
 "fields": [{"name": "D", "role": "dark_matter", "spin": 0, "mass_gev": 500, "charges": {"su2": 2, "hypercharge": 0.5}, "dark_parity": -1},
            {"name": "S", "role": "mediator", "spin": 0, "self_conjugate": true, "mass_gev": 300, "dark_parity": -1},
            {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}],
 "couplings": [{"name": "A", "value": 20.0, "mass_dimension": 1}, {"name": "lam", "value": 0.1}],
 "terms": [{"fields": [{"field": "D", "conjugate": true}, {"field": "H"}, {"field": "S"}], "lorentz": "scalar",
            "coupling": "-A", "plus_hc": true, "indices": "D*[i] H[i] S", "text": "−A (D†H) S + h.c."},
           {"fields": [{"field": "D", "conjugate": true}, {"field": "H"}, {"field": "H", "conjugate": true}, {"field": "D"}],
            "lorentz": "scalar", "coupling": "-lam", "indices": "D*[i] H[i] H*[j] D[j]", "text": "−λ (D†H)(H†D)"}]}

Also return "conventions": every conversion you made from the paper's conventions, and "assumptions": every choice
the paper did not state. Return only the JSON object."""


class PaperModel(StrictModel):
    """The agent's model, and what it converted and assumed."""
    spec: ModelSpec
    conventions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


def source_message(title: str, latex: str, equation: str, excerpt: str, benchmark: dict) -> str:
    """The user message: the paper's Lagrangian, its text around it, and the benchmark's inputs."""
    return (f"Paper: {title}\n\nIts Lagrangian, equation {equation}:\n{latex}\n\n"
            f"The paper's text around it:\n{excerpt}\n\n"
            f"The benchmark point (the paper's own inputs, in the paper's conventions):\n{json.dumps(benchmark)}")


class CanonicalIntake:
    """A paper's model → ``PaperModel``, built by G1 or corrected once from G1's reason (module docstring)."""

    def __init__(self, llm: StructuredLLM, model: str = DEFAULT_MODEL) -> None:
        self.llm, self.model = llm, model

    def ask(self, messages: list[dict], run_id: str | None = None) -> PaperModel:
        return self.llm.complete_structured(GUIDE, messages, PaperModel, model=self.model, run_id=run_id,
                                            actor="canonical_intake")

    def run(self, message: str, run_id: str | None = None, retries: int = 1) -> tuple[PaperModel | None, list[str]]:
        """The model and every G1 refusal on the way (an empty list if the first answer builds)."""
        from adroit.model_building import spectrum
        messages = [{"role": "user", "content": message}]
        refusals: list[str] = []
        for attempt in range(retries + 1):
            found = self.ask(messages, run_id)
            try:
                spectrum.compute(found.spec)
                return found, refusals
            except Exception as error:                # noqa: BLE001 - G1's refusal goes back to the agent
                refusals.append(str(error))
                if attempt == retries:
                    return found, refusals
                messages = messages + [
                    {"role": "assistant", "content": found.model_dump_json()},
                    {"role": "user", "content": f"ADROIT's G1 refuses this model: {error}. Correct it and return the "
                                                "whole JSON object again."}]
        return None, refusals
