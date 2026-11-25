"""What a workbench run produced, where it is reviewed, and what it cost (the owner's report of 2026-10-23).

A run's live view had treated every run as a physics study: "Open the results" went to ``/study`` whenever a report
existed, and the spend was read only from ``study.json`` or a "spent $x" line in the log. A model intake (a language
model's interpretation, reviewed as a draft, its spending in its session's ``paid.jsonl``) therefore showed $0, and
its button led to a page that said "Not a study ... the run may still be going". Here the output decides:

- **the outcome** (``outcome``): what the run made, by its command (``kind_of``): a study, a model draft, an
  experimental source draft, a source interpretation, a discovery survey, a signal-record draft, promoted studies. A
  headline in plain words ("Draft ready for review" is not "Study complete"), the primary action that opens the page
  where that output is reviewed, and after a stop the next action;
- **the cost** (``cost``): read by ``orchestrator.accounting``, the one interpretation of money (the consolidation
  plan's M2), whose names this module re-exports for the pages.

Reading here is $0: no request is made, and nothing is written.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlencode

from pydantic import Field

from adroit.core.durable import INCOMPLETE, interrupted
from adroit.core.state import StrictModel
from adroit.orchestrator.accounting import (  # noqa: F401 - the pages' names for the one interpretation of money
    KINDS, NOT_AVAILABLE, PARTIAL, PREFLIGHT, RESERVED, SPENT_LINE, SPLIT_TOLERANCE, Cost, JobFacts, RequestFact,
    Total, _argument, _budgets, _option, _read_json, _recorded_spend, _stop_facts, cost, cost_lines, discovery_session,
    job_ledger_cost, kind_of, ledger_session, live_text, run_line, session_cost, session_money, session_text,
    short_line, status_text, study_cost, total, total_text, usd)
from adroit.orchestrator.preflight import JOB_OUTPUT
from adroit.ui import engine


class Link(StrictModel):
    """A labelled page of the workbench."""
    label: str
    target: str


class Outcome(StrictModel):
    """What a run produced and what to do next: the kind of output, a headline, a sentence, the primary action and
    the others."""
    output: str                              # study, model_draft, source_draft, source_interpretation, discovery,
    headline: str                            # signal_draft, promotion, report or none
    detail: str = ""
    primary: Link | None = None
    links: list[Link] = Field(default_factory=list)


# --- outcome ----------------------------------------------------------------------------------------------------

def outcome(root: Path, folder: Path, job: engine.Job) -> Outcome:
    """What the run produced and the primary action (module docstring), by what its command makes."""
    folder, kind = Path(folder), kind_of(job)
    if kind in EXPORTS and job.status != "running" and interrupted(folder):
        return incomplete(job)
    make = {"model_intake": model_outcome, "source_interpretation": extraction_outcome,
            "source_import": source_draft_outcome, "discovery": discovery_outcome, "signal_draft": signal_draft_outcome,
            "promotion": promotion_outcome}.get(kind, study_outcome)
    return make(root, folder, job)


EXPORTS = ("model_intake", "source_interpretation", "source_import", "discovery")   # written by ``durable.export``


def incomplete(job: engine.Job | None = None) -> Outcome:
    """A run's folder whose export was interrupted (``durable.interrupted``): its draft, report and request record may
    be of two exports, so none of them is offered as this run's (the auditor's DJ recheck, DK-05, 2026-11-07)."""
    after = f" The run ended {job.status}." if job is not None and job.status not in ("completed", "running") else ""
    return Outcome(output="none", headline="Its output is incomplete",
                   detail=f"Its files were being replaced when their writer stopped ({INCOMPLETE} in its folder), so "
                          "they may be from two runs; none is shown as this run's. The session keeps every draft and "
                          "paid request; run it again into a new folder." + after)


def page_of(root: Path, folder: str | Path) -> str:
    """A folder's path relative to the runs directory, "" if it lies outside it."""
    try:
        return str(Path(folder).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return ""


def _stop_line(job: engine.Job) -> str:
    """The line in which the command said why it stopped, if it said; where its log cannot be read, that, named as
    such, never read as a line the command wrote (the auditor's DO recheck, DP-03, 2026-11-09)."""
    lines, unreadable = engine.read_log(Path(job.folder), 80)
    if unreadable:
        return f"{unreadable[:1].upper()}{unreadable[1:]}, so why it stopped is not known here."
    return next((line.strip() for line in reversed(lines)
                 if re.search(r"stopped|exceeds|Invalid value|Error:|refused", line)), "")


def unfinished(job: engine.Job, what: str) -> tuple[str, str]:
    """A headline and a sentence for a run that has not completed, from its status and its log's stop line."""
    said = _stop_line(job)
    left = engine.left_running(job)
    if left:                                  # its run ended, its calculation not (ID-01): never said to be stopped
        return f"{what}: {job.status}, its calculation still running", left
    if job.status == "running":
        return f"{what}: running", "This page refreshes every second; you can leave it and the run continues."
    if job.status == "budget_stopped":
        return ("Stopped at the cap before a paid request",
                f"Nothing beyond the approved cap was sent, and what was done is kept. {said}".strip())
    if job.status == "cancelled":
        return "Cancelled", "The run was stopped on request; what was done is kept."
    return f"{what}: failed", (said or job.note or "The log below shows why.").strip()


def study_outcome(root: Path, folder: Path, job: engine.Job) -> Outcome:
    """A physics study (Track 1, an idea, a derivation, Signal best fits, Explain a signal, a native fit, a
    reanalysis): its study page once it has written its study record."""
    from adroit.orchestrator import studies
    if (folder / studies.FILE).exists():
        done = job.status == "completed"
        return Outcome(output="study", headline="Study complete" if done else unfinished(job, "The run")[0],
                       detail="Its verdict, report and plots are on the study's page." if done else
                       "A study record was written before the run ended: open it to see what was done.",
                       primary=Link(label="Open the study", target="/study?" + urlencode(
                           {"path": page_of(root, folder)})))
    headline, detail = unfinished(job, "The run")
    if job.status == "completed":
        headline, detail = "Finished without a study record", "The log below shows what the run did."
    if (folder / "report.md").exists() and job.status != "running":
        detail += " Its report is below."
    return Outcome(output="report" if (folder / "report.md").exists() else "none", headline=headline, detail=detail)


def _draft(folder: Path):
    """(the intake draft the run recorded, verified against the model library, or None; why not)."""
    from adroit.orchestrator.model_intake import Draft, Intake
    path = folder / "intake.json"
    if not path.exists():
        return None, "its draft record (intake.json) was not written"
    try:
        recorded = Draft.model_validate_json(path.read_text())
        return Intake().load(recorded.session_id, recorded.step_id), ""
    except (OSError, ValueError) as error:
        return None, f"its draft record could not be verified against the model library ({error})"


def review_link(session: str, step: str = "") -> str:
    """The model-intake page of a session, at a pinned draft of it."""
    return "/models/intake?" + urlencode({"session": session, **({"step": step} if step else {})})


def draft_ready(draft, job: engine.Job) -> Outcome:
    """A saved model draft: the interpretation is complete, the physics is not begun."""
    n = len(draft.choices)
    after = "" if job.status in ("completed", "running") else f" The run then ended {job.status}; see its log."
    return Outcome(output="model_draft", headline="Draft ready for review",
                   detail=f"Interpretation complete: {n} candidate model{'s' if n != 1 else ''} to review. No physics "
                          "calculation was run; nothing is saved to your library until you approve a candidate." + after,
                   primary=Link(label="Review model draft", target=review_link(draft.session_id, draft.step_id)))


def draft_outside_job(folder: Path) -> Outcome | None:
    """The outcome of a folder holding a model draft but no workbench job (``adroit models step --out`` from the
    command line), None if it holds no verified draft; an interrupted export's folder is incomplete (DK-05)."""
    if interrupted(folder) and (Path(folder) / "intake.json").exists():
        return incomplete()
    draft, _ = _draft(Path(folder))
    if draft is None:
        return None
    return draft_ready(draft, engine.Job(title="", kind="models", command=["models"], folder=str(folder),
                                         status="completed"))


def model_outcome(root: Path, folder: Path, job: engine.Job) -> Outcome:
    """A model-intake run: its draft to review, or why there is none and where to continue."""
    draft, why = _draft(folder)
    if draft is not None:
        return draft_ready(draft, job)
    session, parent = _argument(job), _option(job.command, "--parent-step")
    back = Link(label="Back to the draft it refines" if parent else "Open the intake session",
                target=review_link(session, parent)) if session else None
    again = Link(label="Start a new model intake", target="/models/intake")
    if job.status == "completed":
        return Outcome(output="none", headline="Finished, but the draft is not available",
                       detail=f"The run ended normally, but {why}. The session keeps every draft that was saved.",
                       primary=back or again, links=[again] if back else [])
    headline, detail = unfinished(job, "Interpretation")
    if job.status == "running":
        return Outcome(output="none", headline=headline, detail=detail)
    if job.status == "budget_stopped":
        detail += (" Raise the session's cap on the draft's page (the change is recorded), then refine again."
                   if parent else " Start again with a higher session budget.")
    return Outcome(output="none", headline=headline, detail=detail,
                   primary=(back if parent else again) or again, links=[again] if parent and back else [])


def source_draft_outcome(root: Path, folder: Path, job: engine.Job) -> Outcome:
    """An experimental source import: the draft revision it saved, for review."""
    from adroit.core.experimental_input import ExperimentalRevision
    library = Link(label="Open the experimental library", target="/experiments")
    path = folder / "experimental.json"
    if not path.exists():
        headline, detail = unfinished(job, "Import")
        if job.status == "completed":
            headline, detail = "Finished, but the source draft is not available", "Its record was not written."
        return Outcome(output="none", headline=headline, detail=detail,
                       primary=None if job.status == "running" else library)
    try:
        revision = ExperimentalRevision.model_validate_json(path.read_text())
    except (OSError, ValueError) as error:
        return Outcome(output="none", headline="Finished, but the source draft is not available",
                       detail=f"Its record could not be read ({error}).", primary=library)
    return Outcome(output="source_draft", headline="Source draft ready for review",
                   detail="The sources are stored as a draft revision. Nothing is calculated or used as a limit "
                          "until you review it.",
                   primary=Link(label="Review experimental source draft",
                                target="/experiments/view?" + urlencode({"reference": revision.reference})))


def extraction_outcome(root: Path, folder: Path, job: engine.Job) -> Outcome:
    """A source interpretation batch: the interpreted revision to review, and its session to continue."""
    from adroit.core.experimental_extraction import ExtractionStep
    session = _argument(job)
    resume = [Link(label="Continue source interpretation",
                   target="/experiments/session?" + urlencode({"session": session}))] if session else []
    try:
        step = ExtractionStep.model_validate_json((folder / "extraction.json").read_text())
    except (OSError, ValueError):
        step = None
    if step is not None:
        return Outcome(output="source_interpretation", headline="Interpretation ready for review",
                       detail="The language model's reading of the selected sources is saved as a new draft revision. "
                              "No physics calculation was run; every value it proposes stays unreviewed until you "
                              "review it.",
                       primary=Link(label="Review extracted interpretation",
                                    target="/experiments/view?" + urlencode({"reference": step.output_revision})),
                       links=resume)
    headline, detail = unfinished(job, "Interpretation")
    if job.status == "completed":
        headline, detail = ("Finished, but the interpretation is not available",
                            "The run ended normally, but its record (extraction.json) is missing or unreadable.")
    return Outcome(output="none", headline=headline, detail=detail,
                   primary=resume[0] if resume and job.status != "running" else None)


def discovery_outcome(root: Path, folder: Path, job: engine.Job) -> Outcome:
    """A constraint discovery (``constraints discover`` or ``resume``): its session's page, with the stages done and
    those that stopped."""
    session = ledger_session(folder, job)[0]
    view = _read_json(folder / "discovery.json")
    primary = Link(label="Review the discovery session",
                   target="/constraints/discovery?" + urlencode({"session": session})) if session else None
    if view is None:
        headline, detail = unfinished(job, "Discovery")
        return Outcome(output="none", headline=headline, detail=detail,
                       primary=None if job.status == "running" else primary)
    state = view.get("state") or {}
    done = [name for name, row in state.items() if isinstance(row, dict) and row.get("status") == "done"]
    other = [f"{name}: {row.get('status')}" for name, row in state.items()
             if isinstance(row, dict) and row.get("status") != "done"]
    return Outcome(output="discovery", headline="Survey ready for review" if not other else
                   "Survey finished with stages not done",
                   detail=f"{len(done)} stage(s) done" + (f"; not done: {', '.join(other)}" if other else "") +
                          ". Drafted limits wait for your review; nothing is signed, validated or bound.",
                   primary=primary)


def written_output(folder: Path, record: str) -> tuple[bool, str]:
    """(whether a run's file output is still what the run wrote, why not): its identity kept in the job's folder
    (``preflight.JOB_OUTPUT``: path and sha256) against the file now (WA-05: a later run's draft had replaced the
    first's file, and the first run's page then opened it). A run from before the identity was kept: the file as it
    is, said to be unverified."""
    import hashlib
    kept = _read_json(Path(folder) / JOB_OUTPUT)
    if kept is None:
        return True, "unverified"
    try:
        same = (Path(kept.get("path", "")).resolve() == Path(record).resolve() and
                hashlib.sha256(Path(record).read_bytes()).hexdigest() == kept.get("sha256"))
    except OSError:
        same = False
    return same, "" if same else "the file has changed since this run wrote it"


def signal_draft_outcome(root: Path, folder: Path, job: engine.Job) -> Outcome:
    """A signal record drafted from a paper: the record file, to check and verify on Add a signal, while it is still
    the draft this run wrote."""
    record = _option(job.command, "--out")
    if job.status == "completed" and record and Path(record).is_file():
        same, why = written_output(folder, record)
        if not same:
            return Outcome(output="none", headline="Finished, but its draft record has been replaced",
                           detail=f"{record}: {why}, so it is not this run's draft. This run's paid answer is kept "
                                  "in its paid ledger.",
                           primary=Link(label="Back to Add a signal", target="/new/anomaly"))
        older = (" This run is from before a run kept its file's identity: check that the file is still its draft."
                 if why == "unverified" else "")
        return Outcome(output="signal_draft", headline="Signal record draft ready for review",
                       detail=f"Written to {record}. A person must verify every number against the paper before "
                              "Signal best fits or Explain a signal uses it." + older,
                       primary=Link(label="Check the draft record",
                                    target="/new/anomaly?" + urlencode({"record": record})))
    headline, detail = unfinished(job, "Drafting")
    if job.status == "completed":
        headline, detail = "Finished, but the draft record is not available", f"{record or 'Its file'} was not found."
    return Outcome(output="none", headline=headline, detail=detail,
                   primary=None if job.status == "running" else Link(label="Back to Add a signal",
                                                                     target="/new/anomaly"))


def promotion_outcome(root: Path, folder: Path, job: engine.Job) -> Outcome:
    """A promotion: what it made, read from its record (``promoted``): how many studies, listed under the signal study,
    and each candidate or model left without one, with why; a promotion that made none says so (the owner, 2026-11-19:
    "Promotion complete. Each promoted model is its own study" had been shown where none was made)."""
    parent = page_of(root, job.command[1]) if len(job.command) > 1 else ""
    target = "/study?" + urlencode({"path": parent}) if parent else ""
    if job.status != "completed":
        headline, detail = unfinished(job, "Promotion")
        primary = Link(label="Open the signal study", target=target) if target and job.status != "running" else None
        return Outcome(output="none", headline=headline, detail=detail, primary=primary)
    made, without, why = promoted(folder)
    if made is None:
        return Outcome(output="promotion", headline="Promotion complete",
                       detail=f"What it made cannot be read here ({why}); this run's log lists its studies and why any "
                              "candidate has none.",
                       primary=Link(label="Open the signal study", target=target) if target else None)
    reasons = "; ".join(f"{k}: {v}" for k, v in list(without.items())[:3]) + (
        f"; and {len(without) - 3} more" if len(without) > 3 else "")
    if not made:
        return Outcome(output="none", headline="Promotion complete: no study was made",
                       detail=f"No candidate could be studied. {reasons}.",
                       primary=Link(label="Back to the signal study", target=target) if target else None)
    detail = (f"{made} stud{'y' if made == 1 else 'ies'}, each listed under the signal study."
              + (f" Without a study: {reasons}." if without else ""))
    return Outcome(output="promotion", headline=f"Promotion complete: {made} stud{'y' if made == 1 else 'ies'} made",
                   detail=detail, primary=Link(label="Open the signal study and its promoted studies", target=target)
                   if target else None)


def promoted(folder: Path) -> tuple[int | None, dict[str, str], str]:
    """(the studies a promotion made, each candidate or model left without one with why, ""), read from the record its
    job points to (``preflight.JOB_OUTPUT``, checked by its SHA-256: ``written_output``); (None, {}, why) where that
    record is not named, has changed, or cannot be read."""
    from adroit.orchestrator.promote import Promotion
    kept = _read_json(Path(folder) / JOB_OUTPUT)
    if not kept or not kept.get("path"):
        return None, {}, "this run named no record of what it made"
    same, _ = written_output(folder, kept["path"])
    if not same:
        return None, {}, "its record has changed since this run wrote it"
    try:
        record = Promotion.model_validate_json(Path(kept["path"]).read_bytes())
    except (OSError, ValueError) as error:
        return None, {}, f"its record cannot be read: {type(error).__name__}"
    return len(record.children), dict(record.undetermined), ""
