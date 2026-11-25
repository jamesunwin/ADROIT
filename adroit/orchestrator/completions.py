"""Computable completions of a model the builder proposed but DM13 cannot compute as it stands (live check L9).

A field content's most general Lagrangian is usually not one of DM13's computed classes, for two reasons a
researcher can settle with an explicit choice:

- **a flavour:** the generator couples a new field to a Standard Model generation multiplet (uR, dR or eR, every
  generation with one coupling), but the t-channel portals are computed for one explicit flavour: u, d or b; e, μ
  or τ. Each flavour with the multiplet's quantum numbers is one completion.
- **terms the computed class does not represent:** a mediator's Higgs-portal quartic λ φ†φ H†H, say. Setting such
  a coupling to zero is a benchmark choice. It is stated in the completion's assumptions, never made silently.

Scalar mixing with the Higgs needs a mixing angle and the scalar potential, which a field content cannot state;
it is named as the researcher's choice (``mixing_choice``). Nothing here runs a calculation.
"""

from __future__ import annotations

import re

from pydantic import Field

from adroit.core.model_spec import ModelSpec
from adroit.core.state import StrictModel
from adroit.parameter_space.classify import Unsupported, classify
from adroit.parameter_space.portals.tchannel import PARTNERS

MULTIPLETS = {"uR": ("uR",), "dR": ("dR", "bR"), "eR": ("eR", "muR", "tauR")}     # generator field → flavours
_UNREPRESENTED = re.compile(r"additional interaction (['\"])(.*)\1 is not represented")
MIXING = "singlet scalar mixing needs an explicit mass-eigenstate/potential matching"
RELABELLED = "relabelled:"
CONJUGATE_SU3 = {"3": "3bar", "3bar": "3"}


class Completion(StrictModel):
    """A computable version of a proposed model, and the choices that make it so."""

    spec: ModelSpec
    choices: list[str] = Field(default_factory=list)     # each a stated choice; empty: the model as proposed

    @property
    def flavour_only(self) -> bool:
        """Whether the only choices are flavours (no coupling set to zero)."""
        return (any(c.startswith("one flavour:") for c in self.choices)
                and all(c.startswith(("one flavour:", RELABELLED)) for c in self.choices))


def _renamed(spec: ModelSpec, old: str, new: str, right_handed: bool = False) -> ModelSpec:
    field = spec.field(old).model_copy(update={"name": new, "generations": 1, **({"chirality": "R"} if right_handed else {})})
    terms = [t.model_copy(update={
        "fields": [o.model_copy(update={"field": new}) if o.field == old else o for o in t.fields],
        "text": re.sub(rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])", new, t.text)}) for t in spec.terms]
    return spec.model_copy(update={"fields": [field if f.name == old else f for f in spec.fields], "terms": terms})


def single_flavours(spec: ModelSpec) -> list[tuple[ModelSpec, str]]:
    """(model, choice) for each explicit flavour of each Standard Model generation multiplet the model's terms use."""
    used = {o.field for t in spec.terms for o in t.fields}
    out = []
    for multiplet, partners in MULTIPLETS.items():
        if multiplet in used and multiplet in {f.name for f in spec.fields} and spec.field(multiplet).generations > 1:
            for partner in partners:
                flavour = PARTNERS[partner][0]
                out.append((_renamed(spec, multiplet, flavour),
                            f"one flavour: {flavour} (right-handed, {partner}) for the generator's {multiplet}, "
                            "which stands for every generation"))
    return out


GENERIC = {("1", -1.0): ("eR", "muR", "tauR"), ("3", 2 / 3): ("uR",), ("3", -1 / 3): ("dR", "bR")}


def generic_flavours(spec: ModelSpec) -> list[tuple[ModelSpec, str]]:
    """(model, choice) for each explicit flavour of a Standard Model fermion the model names only generically (a
    paper's charged lepton ``l``, say): a single-generation spin-½ field whose name states no flavour, matched by
    its colour and charge (the electric charge below electroweak breaking, else the hypercharge of a
    right-handed field). The flavour, and taking it right-handed as the computed t-channel portals do, are stated."""
    from adroit.model_building.spec import SM_FIELDS, generation
    out = []
    for f in spec.fields:
        if (f.role.value != "standard_model" or f.spin != 0.5 or f.generations != 1 or f.name in SM_FIELDS
                or f.name in PARTNERS or generation(f.name) is not None or f.chirality == "L"):
            continue
        broken = spec.phase.value == "broken"
        charge = f.charges.electric_charge if broken else f.charges.hypercharge
        if not broken and f.chirality != "R":
            continue
        partners = next((v for (su3, q), v in GENERIC.items() if su3 == f.charges.su3 and abs(charge - q) < 1e-6), ())
        for partner in partners:
            flavour = PARTNERS[partner][0]
            out.append((_renamed(spec, f.name, flavour, right_handed=True),
                        f"one flavour: {flavour} (right-handed, {partner}) for the model's generic {f.name}; taken "
                        "right-handed, as the computed t-channel portals are: check against the source"))
    return out


def conjugate_mediators(spec: ModelSpec) -> tuple[ModelSpec, list[str]]:
    """The model with each complex scalar mediator written as its conjugate (φ ↔ φ*) when its charges are opposite
    to those of the Standard Model fermion it couples to: the same model, in the computed portals' convention (φ
    carries the fermion's charges). Not a choice; the relabelling is stated."""
    notes = []
    broken = spec.phase.value == "broken"
    for med in [f for f in spec.fields if f.role.value == "mediator" and f.spin == 0 and not f.self_conjugate]:
        for t in spec.terms:
            names = [o.field for o in t.fields]
            sm = [spec.field(n) for n in names if spec.field(n).role.value == "standard_model" and spec.field(n).spin == 0.5]
            if med.name not in names or len(names) != 3 or len(sm) != 1:
                continue
            f, c = sm[0], med.charges
            q_med, q_f = (c.electric_charge, f.charges.electric_charge) if broken else (c.hypercharge, f.charges.hypercharge)
            if not (q_f and abs(q_med + q_f) < 1e-6 and c.su3 == CONJUGATE_SU3.get(f.charges.su3, f.charges.su3)):
                continue
            charges = c.model_copy(update={"hypercharge": -c.hypercharge, "electric_charge": -c.electric_charge,
                                           "su3": CONJUGATE_SU3.get(c.su3, c.su3),
                                           "extra": {k: -v for k, v in c.extra.items()}})
            fields = [x.model_copy(update={"charges": charges}) if x.name == med.name else x for x in spec.fields]
            terms = [x.model_copy(update={"fields": [o.model_copy(update={"conjugate": not o.conjugate})
                                                      if o.field == med.name else o for o in x.fields]})
                     for x in spec.terms]
            spec = spec.model_copy(update={"fields": fields, "terms": terms})
            notes.append(f"{RELABELLED} {med.name} ↔ {med.name}* (its charges were written opposite to {f.name}'s; "
                         "the same model in the computed portal's convention)")
            break
    return spec, notes


def zero_unrepresented(spec: ModelSpec) -> tuple[ModelSpec, list[str]]:
    """The model with each coupling the computed class does not represent set to zero, and the stated choices; the
    model unchanged (no choices) if it is computable or refused for another reason."""
    choices: list[str] = []
    for _ in range(len(spec.terms)):
        try:
            classify(spec, generic_route=False)          # a completion is for the library's validated classes
            return spec, choices
        except Unsupported as error:
            found = _UNREPRESENTED.search(str(error))
            term = next((t for t in spec.terms if found and found.group(2) in (t.text, t.coupling)), None)
            if term is None or not term.coupling.isidentifier():
                return spec, choices
            couplings = [c.model_copy(update={"value": 0.0}) if c.name == term.coupling else c for c in spec.couplings]
            choice = (f"{term.coupling} = 0 for {term.text or term.coupling}: a benchmark choice, since the computed "
                      "class does not represent this term; technically natural only if a symmetry protects this zero "
                      "(otherwise loops regenerate the term)")
            spec = spec.model_copy(update={"couplings": couplings, "assumptions": [*spec.assumptions, choice]})
            choices.append(choice)
    return spec, choices


def completions(spec: ModelSpec) -> list[Completion]:
    """Every computable completion: the model itself, or each single-flavour version, with any unrepresented
    couplings set to zero (each a stated choice). Empty when no such choice makes it computable."""
    out = []
    for candidate, flavour in [(spec, ""), *single_flavours(spec), *generic_flavours(spec)]:
        candidate, relabelled = conjugate_mediators(candidate)
        model, zeroed = zero_unrepresented(candidate)
        try:
            classify(model, generic_route=False)
        except Unsupported:
            continue
        choices = [flavour] * bool(flavour) + relabelled + zeroed
        if choices:
            model = model.model_copy(update={"assumptions": list(dict.fromkeys([*model.assumptions, *choices]))})
        out.append(Completion(spec=model, choices=choices))
    return out


def mixing_choice(error: str) -> str:
    """The researcher's choice a scalar-mixing refusal asks for ('' for another refusal)."""
    if MIXING not in error:
        return ""
    return ("give the scalar's mixing angle θ with the Higgs and the scalar potential (a typed scalar_potential), or "
            "compute the simplified scalar mediator (docs/dm13/scalar_mediator.yaml) with quark couplings g_q = sin θ")
