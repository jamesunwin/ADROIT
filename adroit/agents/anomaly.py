"""The anomaly drafter (DM14): a paper's text → a draft anomaly record, for a person to verify. Opt-in.

The agent reads a search's paper and fills in the record's numbers, quoting
the sentence each one comes from. It never invents a number: what the text
does not give (typically the efficiency, which is a figure) is listed for a
person instead. Every quote is then checked, character for character up to
whitespace, against the text (``unquoted``). The draft is written with an
empty ``verified_by``, so Path 2 refuses it until a person has checked it.
"""

from __future__ import annotations


import yaml
from pydantic import Field

from adroit.agents.lagrangian import DEFAULT_DERIVER
from adroit.agents.llm import StructuredLLM
from adroit.core.prompts import TERSE_CLAUSE
from adroit.core.quotes import contains
from adroit.core.state import StrictModel
from adroit.experiments.anomaly import Curve, Halo

TEXT_LIMIT = 60_000

DRAFT_SYSTEM = """You read a direct-detection dark matter search's paper and draft the record of its events for a
statistical re-analysis. Return JSON for the AnomalyDraft schema.

Rules:
- Copy numbers exactly as the text states them. Never compute, estimate or invent a number; if the text does not
  state a quantity, leave it null (or empty) and add the field's name, with what a person must do, to needs_person
  (for example "efficiency: digitise Fig. 1, the final-selection curve").
- target: the detector material as an element or compound symbol (Xe, Ar, Ge, Si, CaWO4, C3F8).
- exposure_kg_day: the exposure in kg·days before the final candidate selection, if the text gives it so; convert
  only units (tonne·year = 365250 kg·days) and say so in the source.
- window_kev: the nuclear-recoil energy window [low, high] of the signal region in keV.
- events_kev: the recoil energy of each candidate event, in keV, as listed.
- resolution_kev: only if stated.
- background_events: the expected background count in the signal region; background_plus and background_minus:
  its uncertainties in events, one entry per source (statistical, systematic), as stated.
- efficiency_points: only if the text gives efficiency values at stated energies; otherwise name the figure in
  efficiency_figure and add "efficiency" to needs_person.
- halo: the halo parameters the paper used, if stated.
- sources: for every field you filled, the shortest verbatim quote from the text that states it (copy it exactly).
- collaboration_result: one sentence on what the collaboration concluded, quoted where possible.
- Return only the JSON object.""" + TERSE_CLAUSE


class AnomalyDraft(StrictModel):
    """A draft anomaly record as read from a paper: its numbers, the verbatim quote for each, and what a person must
    still supply."""
    name: str
    target: str = ""
    references: list[str] = Field(default_factory=list)
    exposure_kg_day: float | None = None
    window_kev: list[float] = Field(default_factory=list)
    events_kev: list[float] = Field(default_factory=list)
    resolution_kev: float | None = None
    background_events: float | None = None
    background_plus: list[float] = Field(default_factory=list)
    background_minus: list[float] = Field(default_factory=list)
    efficiency_points: Curve | None = None
    efficiency_figure: str = ""
    halo: Halo | None = None
    sources: dict[str, str] = Field(default_factory=dict)
    needs_person: list[str] = Field(default_factory=list)
    collaboration_result: str = ""


def unquoted(draft: AnomalyDraft, text: str) -> list[str]:
    """The fields whose quoted source is not in the text, up to typesetting: white space, case, line-break
    hyphenation, soft hyphens, ligatures, and Unicode dashes and minus signs (``core.quotes``)."""
    return [field for field, quote in draft.sources.items() if quote.strip() and not contains(text, quote)]


class AnomalyDrafter:
    """A paper's text → a draft record."""

    def __init__(self, llm: StructuredLLM, model: str = DEFAULT_DERIVER) -> None:
        self.llm, self.model = llm, model

    def run(self, text: str, reference: str, run_id: str | None = None) -> AnomalyDraft:
        """The draft for a paper's text, with each field whose quote is not in the text added to ``needs_person``."""
        draft = self.llm.complete_structured(
            DRAFT_SYSTEM, [{"role": "user", "content": f"Paper {reference}:\n\n{text[:TEXT_LIMIT]}"}],
            AnomalyDraft, model=self.model, run_id=run_id, actor="anomaly_drafter")
        missing = unquoted(draft, text)
        notes = [f"{field}: its quoted source is not in the paper's text; check it" for field in missing]
        refs = draft.references or [reference]
        return draft.model_copy(update={"needs_person": draft.needs_person + notes, "references": refs})


REQUIRED = ("target", "exposure_kg_day", "window_kev", "events_kev", "resolution_kev", "background_events")


def missing(draft: AnomalyDraft) -> list[str]:
    """The record's required fields the draft leaves empty: a person must give (or declare) each."""
    return [f"{name}: not stated in the text; give it, or declare a value in a note"
            for name in REQUIRED if getattr(draft, name) in (None, "", [])]


def to_yaml(draft: AnomalyDraft) -> str:
    """The draft as a record file, unverified, with what a person must still do at the top.

    A required number the text does not give is written as ``null``, a visible placeholder: the file is valid
    YAML but does not load as a record until a person has filled it in (``missing``), and ``adroit anomaly
    check`` names each such field in plain language.
    """
    named = {item.split(":", 1)[0].strip() for item in draft.needs_person}
    draft = draft.model_copy(update={"needs_person": draft.needs_person + [
        m for m in missing(draft) if m.split(":", 1)[0] not in named]})
    efficiency = ({"points": draft.efficiency_points.model_dump()} if draft.efficiency_points is not None
                  else {"csv": "efficiency.csv"})
    record = {
        "name": draft.name, "target": draft.target, "references": draft.references,
        "exposure_kg_day": draft.exposure_kg_day, "window_kev": draft.window_kev, "events_kev": draft.events_kev,
        "resolution_kev": draft.resolution_kev, "background_events": draft.background_events,
        "background_uncertainty": ({"plus": draft.background_plus, "minus": draft.background_minus}
                                   if draft.background_plus and draft.background_minus else None),
        "efficiency": efficiency,
        "halo": (draft.halo or Halo()).model_dump(),
        "collaboration_result": draft.collaboration_result,
        "sources": draft.sources, "needs_person": draft.needs_person, "verified_by": "",
    }
    head = ["# A DRAFT anomaly record, written by the anomaly drafter (a language model) from the paper's text.",
            "# A person must check every number against the paper, do what needs_person lists, and then set",
            "# verified_by. Until then Path 2 refuses it. Check it with: adroit anomaly check THIS.yaml"]
    if draft.efficiency_points is None:
        head.append(f"# The efficiency: digitise {draft.efficiency_figure or 'the paper figure'} into efficiency.csv "
                    "(two columns: keV, efficiency) beside this file.")
    if draft.halo is None:
        head.append("# The halo: not stated in the text; the standard halo is filled in. Check it.")
    return "\n".join(head) + "\n" + yaml.safe_dump({k: v for k, v in record.items() if v is not None or k in REQUIRED},
                                                  sort_keys=False, allow_unicode=True)
