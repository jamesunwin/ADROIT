"""The model builder (DM12): an idea in words → candidate field contents. Opt-in.

The agent proposes the fields of a few distinct models that realise the idea,
with a reason for each. It writes no interaction terms: the generator
(``model_building.lagrangian``) writes every term the proposed charges and
parity allow, and the audit checks the result. Literature is named only as
keywords for a later search, never as references, so that nothing unverified
enters a report.
"""

from __future__ import annotations

import re

from pydantic import Field

from adroit.agents.lagrangian import DEFAULT_DERIVER
from adroit.agents.llm import StructuredLLM
from adroit.core.model_spec import ModelField
from adroit.core.prompts import TERSE_CLAUSE
from adroit.core.state import StrictModel

MAX_MODELS = 6

IDEA_SYSTEM = """You propose concrete dark matter models that realise an idea given in words. Return JSON for the
ModelProposals schema.

Rules:
- Propose up to the number of models asked for: the minimal field content that realises the idea first, then
  well-motivated alternatives that differ in field content (not only in parameter values).
- List ONLY the fields beyond the Standard Model; the Standard Model is always present. One exception: when a new
  field couples to one particular Standard Model fermion flavour (a t-channel partner of the b quark or of the muon,
  a mediator coupling only to the tau, say), also list that flavour as a field with role standard_model, generations
  1, its chirality and its charges, named as ADROIT names it: a lepton doublet Le, Lmu or Ltau (chirality "L", su2 2,
  Y = -1/2), a right-handed lepton eR, muR or tauR (chirality "R", Y = -1), a right-handed quark such as bR (su3 "3",
  Y = -1/3). Otherwise every generation is taken, with one coupling.
- A second exception: when Standard Model fermions carry charge under a new gauged U(1) (B - L, U(1)_B, U(1)_L),
  list each Standard Model fermion multiplet that carries it, with its charge in extra: Q (su3 "3", su2 2, Y = 1/6,
  chirality "L"), uR (su3 "3", Y = 2/3, "R"), dR (su3 "3", Y = -1/3, "R"), L (su2 2, Y = -1/2, "L") and eR (Y = -1,
  "R"), each with generations 3 and role standard_model (B - L: 1/3 for quarks, -1 for leptons). Unlisted, they carry
  no charge, the U(1) reaches nothing of the Standard Model, and the model is not offered.
- A new scalar that mixes with the Higgs needs a mixing angle and a scalar potential that a field content cannot
  state: say so in "assumptions".
- Each field: name (a short identifier, letters and digits), role (dark_matter, mediator, other), spin (0, 0.5 or 1),
  self_conjugate (real scalar, Majorana fermion, real vector), chirality ("" for a Dirac or Majorana fermion, "L" or
  "R" for a single Weyl fermion), generations (1 unless the idea needs more), mass_gev (a representative numerical
  value for every new field, never null: the idea's own value, else a benchmark such as the thermal-relic mass where
  known) with mass_justification, and charges written above electroweak symmetry breaking: su3 ("1", "3", "3bar" or
  "8"), su2 (the multiplet's dimension), hypercharge Y with Q = T3 + Y, electric_charge 0, and extra: charges under
  new U(1) groups, by the group's name. A spin-1 field whose name equals a new U(1)'s name is that U(1)'s gauge
  boson; any other spin-1 field is a neutral massive vector.
- A vector mediator: make it a U(1)'s gauge boson only when the idea is a gauged U(1) (B - L, L_mu - L_tau, a dark
  photon's U(1)); its couplings then follow the charges. For a simplified model whose vector couples to chosen fields
  with independent strengths, make it a neutral massive vector and give no field a charge under it: the system then
  writes a separate coupling to each field.
- dark_parity: −1 for fields odd under the symmetry that keeps the dark matter stable, +1 for even fields. The dark
  matter is a thermal freeze-out relic. Use a Z2 under which it is odd unless the idea's own structure stabilises it
  (for example an electroweak multiplet whose decays are forbidden by its quantum numbers); say which in
  "stability".
- Do not write interaction terms: the system generates every term the symmetries allow (renormalizable, dimension
  at most 4), and asks you afterwards for the values of the couplings the idea calls for.
- not_encoded: every part of the idea this field content cannot hold (an operator above dimension 4, a state left
  out, a loop effect), each in a few words with what it means for a calculation where you know; empty if none.
- simplified: If the model keeps only part of a larger theory (for example the superpartners a supersymmetric model
  needs here and not the others, or one mediator of a fuller model), set simplified to what it leaves out, in a few
  words, and end its name with "(simplified model)"; leave simplified empty for a model complete as given.
- rationale: one or two sentences on how the model realises the idea. keywords: three to six search phrases a
  literature search should use (model names, mechanisms), never paper identifiers or author names.
- Return only the JSON object.""" + TERSE_CLAUSE


class ModelProposal(StrictModel):
    """A proposed model: its field content, how it realises the idea, what keeps the dark matter stable, its
    assumptions and search keywords."""
    name: str
    rationale: str = ""
    simplified: str = ""                # what a simplified model leaves out of its larger theory ("" if none)
    fields: list[ModelField]
    stability: str = ""
    assumptions: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    not_encoded: list[str] = Field(default_factory=list)   # what of the idea this field content cannot hold


class ModelProposals(StrictModel):
    """The agent's proposed models for one idea."""
    proposals: list[ModelProposal] = Field(default_factory=list)


VALUES_SYSTEM = """You complete dark matter models so that they can be computed. You are given an idea in words and
models built for it: each model's fields with their masses, and its couplings, each with the term it multiplies and
its mass dimension. Return JSON for the ModelValues schema.

Rules:
- For each model (by its number), give a representative numerical value and a one-line reason for every coupling the
  idea calls for: the interactions that realise it. A dimensionless coupling must satisfy |g| <= sqrt(4 pi), about
  3.5; a coupling of mass dimension 1 is in GeV.
- Leave out every coupling the idea does not call for (a kinetic mixing the idea excludes, a Higgs-portal term it does
  not mention, couplings to fields it does not name): it is set to zero and its term left out, which the model states.
- Flavour: a coupling's numeric suffix (_1, _2) numbers the term, never a generation. A term marked "all 3 generations"
  has one coupling that applies alike to every generation of those fields (u, c and t for uR). Give it a value that
  is right for all of them; never one sized for a single flavour (a top-sized Yukawa near 1 would give the up and charm
  quarks the same coupling). If the idea needs one flavour only, or couplings in proportion to the Yukawas, and the
  model cannot single them out, leave the coupling out or give a value valid for all generations, and say which in
  not_encoded.
- The dark matter must reach the Standard Model: a model in which no remaining term joins the dark sector to a
  Standard Model field (every portal of its mediator left out) is not offered. Keep the coupling that realises the
  idea's link.
- Signs: a coupling marked "in V" is the coefficient of its term in the scalar potential V, as potentials are quoted
  (V ⊃ lam × term: a positive quartic is repulsive, a positive mass term raises the mass). Every other coupling is its
  term's coefficient in the Lagrangian. Where a term's SU(2) indices are given, its coupling multiplies exactly that
  pairing: H[i] H*[j] H2[j] H2*[i] is |H†H2|², H[i] H*[i] H2[j] H2*[j] is |H|²|H2|².
- The dark matter's stated mass is its physical mass: the Higgs's contributions to it are accounted for when the model
  is computed, so choose the potential's couplings for the spectrum the idea needs, not to adjust that mass.
- A term marked "breaks X's number" splits a complex field X into separate real (or Majorana) particles of different
  masses, which no interaction need join: two stable relics. Give it a value only if the idea calls for that
  splitting (an inelastic or pseudo-Dirac model, or an inert doublet's λ5, H H X* X*, which splits its neutral scalars
  so that Z exchange cannot scatter them). A Higgs portal to a complex scalar X is the term with both X and X*
  (H H* X X*), never H H* X X.
- not_encoded: anything the idea needs that is not among the model's terms (an operator above dimension 4, a coupling
  to a flavour the model cannot single out, a state left out), each in a few words with what it means for a
  calculation where you know (a mass splitting that enters as a parameter, say); empty if none. Never repeat what a
  model lists as "Already noted as left out", in other words or the same.
- Never change the fields, the masses or the terms. Return only the JSON object.""" + TERSE_CLAUSE


class CouplingValue(StrictModel):
    """One coupling's proposed value and why."""
    name: str
    value: float
    reason: str = ""


class ModelValues(StrictModel):
    """The proposed values for one model (``model``: its number, from 1), and what of the idea it cannot hold."""
    model: int
    couplings: list[CouplingValue] = Field(default_factory=list)
    not_encoded: list[str] = Field(default_factory=list)


class ValueProposals(StrictModel):
    """The proposed values for the models of one idea."""
    models: list[ModelValues] = Field(default_factory=list)


def _model_text(i: int, spec, said: list[str] = ()) -> str:
    """One model as the values call reads it: its fields with their masses, its couplings with their terms, and which
    terms apply alike to all three generations (the live gate's L-4: the builder read ``_1`` as a generation)."""
    from adroit.core.model_spec import FieldRole
    from adroit.model_building.usable_models import breaks_number, potential_couplings, universal
    in_v = potential_couplings(spec)
    fields = "; ".join(f"{f.name} ({f.role.value}, spin {f.spin:g}, mass "
                       + (f"{f.mass_gev:g} GeV" if f.mass_gev is not None else "not given") + ")"
                       for f in spec.fields if f.role is not FieldRole.standard_model)
    terms = {}
    for t in spec.terms:
        flavours, moved = universal(spec, t), breaks_number(spec, t)
        terms.setdefault(t.coupling, ("in V: " if t.coupling.strip() in in_v else "") + (t.text or t.coupling)
                         + (f" (indices {t.indices})" if t.indices else "")
                         + (f" [all 3 generations of {' and '.join(flavours)} alike]" if flavours else "")
                         + (f" [breaks {moved}'s number: splits {moved} into separate particles]" if moved else ""))
    lines = [f"Model {i}: {spec.name}", f"Fields: {fields}", "Couplings (name: the term it multiplies; mass dimension):"]
    lines += [f"- {c.name}: " + next((text for k, text in terms.items() if c.name in re.findall(r"[A-Za-z_]\w*", k)),
                                     "(no term)") + f"; {c.mass_dimension}"
              for c in spec.couplings if c.value is None]
    if said:                                             # L-6: the proposal's own omissions, not to be said again
        lines.append("Already noted as left out: " + "; ".join(said))
    return "\n".join(lines)


REPAIR_INTRO = """These models could not run with the values given before. Each lists those values and why it cannot run.
For each, give the values of the couplings the idea calls for that let it run while still realising the idea, under
the same rules; a model's other couplings stay zero. If no values can make a model run, give it none and say why in
not_encoded."""


class ValuesAgent:
    """Generated models → the values of the couplings the idea calls for (one call for all of an idea's models)."""

    def __init__(self, llm: StructuredLLM, model: str = DEFAULT_DERIVER) -> None:
        self.llm, self.model = llm, model

    def run(self, idea: str, specs: list, run_id: str | None = None,
            said: list[list[str]] | None = None) -> ValueProposals:
        """The proposed values for ``specs`` (numbered from 1), for the idea in words; ``said``: what each model's
        proposal already notes as left out, which the reply is not to repeat (L-6)."""
        said = said or [[] for _ in specs]
        text = "\n\n".join(_model_text(i, s, n) for i, (s, n) in enumerate(zip(specs, said), 1))
        return self.llm.complete_structured(
            VALUES_SYSTEM, [{"role": "user", "content": f"The idea:\n\n{idea}\n\nThe models:\n\n{text}"}],
            ValueProposals, model=self.model, run_id=run_id, actor="model_builder")

    def repair(self, idea: str, specs: list, given: list[dict], reasons: list[list[str]],
               said: list[list[str]] | None = None, run_id: str | None = None) -> ValueProposals:
        """Phase C's one repair round (plan section 4.3): the models that could not run, each with the values given
        before and why, for new values (numbered from 1 in this call's own order)."""
        said = said or [[] for _ in specs]
        blocks = [_model_text(i, s, n) + "\nValues given before: "
                  + (", ".join(f"{k} = {v[0]:g}" for k, v in g.items()) or "none")
                  + "\nWhy it cannot run: " + "; ".join(r)
                  for i, (s, g, r, n) in enumerate(zip(specs, given, reasons, said), 1)]
        text = "\n\n".join(blocks)
        return self.llm.complete_structured(
            VALUES_SYSTEM, [{"role": "user",
                             "content": f"The idea:\n\n{idea}\n\n{REPAIR_INTRO}\n\nThe models:\n\n{text}"}],
            ValueProposals, model=self.model, run_id=run_id, actor="model_builder")


class IdeaAgent:
    """An idea in words → field contents that realise it."""

    def __init__(self, llm: StructuredLLM, model: str = DEFAULT_DERIVER) -> None:
        self.llm, self.model = llm, model

    def run(self, idea: str, n: int = 4, run_id: str | None = None) -> ModelProposals:
        """Up to ``n`` field contents that realise the idea (``n`` kept between 1 and ``MAX_MODELS``)."""
        n = max(1, min(n, MAX_MODELS))
        return self.llm.complete_structured(
            IDEA_SYSTEM, [{"role": "user", "content": f"Propose up to {n} models for this idea:\n\n{idea}"}],
            ModelProposals, model=self.model, run_id=run_id, actor="model_builder")
