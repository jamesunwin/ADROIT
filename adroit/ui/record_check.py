"""A record's review, by a person (recommended) or by a language model's check (the owner, 2026-11-18,
the post-review changes item 2; ``orchestrator.record_check``). Shown at each result's review: the choice is
always the researcher's, even with the auto-approve setting on, which covers only the check's spend."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from nicegui import ui

PERSON_FIRST = ("A person's inspection of this record is recommended, as a safeguard: review it yourself with the form "
                "below. Alternatively, a language model can check it (paid).")
AI_RISK = ("A model can make errors, which you then accept. Its check asks whether this is the correct, current and "
           "relevant limit (a literature comparison) and whether it was imported correctly with its conditions stated; "
           "after a major defect the record assistant re-reads the record and it is checked again (at most twice), "
           "then it comes back to you. An approved record says it was checked by the model, not by a person.")
CONSENT = "I choose a model's check instead of a person's review, and accept that it can make errors"
STATUS = {"approved": "approved by the model's check", "needs_you": "back to you: no agreement",
          "stopped": "stopped"}


def drafter(catalog, revision) -> str:
    """The model that drafted this revision (its assisted-extraction session's), or ""."""
    from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
    session = (revision.provenance or {}).get("extraction_session", "")
    if not session:
        return ""
    try:
        return ExperimentalExtraction(catalog).budgets.session(session).model
    except (ValueError, OSError):
        return ""


def _launch(root: Path, run, budget: float, approval: str) -> None:
    """Start the check session's run as a workbench job, and follow it."""
    from adroit.ui import engine, forms, submission
    from adroit.ui.pages import rel
    folder = forms.new_folder(root, "record_check", run.result_id)
    command = ["experiments", "check", run.session_id, "--budget", f"{budget:g}", "--out", str(folder)]
    job = engine.launch(command, folder, f"Record check: {run.result_id}", confirmed_budget=budget,
                        approval=approval)
    submission.go(f"/live?path={rel(root, job.folder)}")


def model_check_tools(root: Path, catalog, revision, item) -> None:
    """The person-first notice, the model check's form, and this result's earlier checks with what each left."""
    from adroit.core.pricing import CHECKER_MODELS, DEFAULT_CHECKER, model_name
    from adroit.ui.pages import budget_form, model_select
    ui.label(PERSON_FIRST).classes("text-sm font-medium").mark("person_first")
    with ui.expansion("Or have a language model check it instead (paid)").classes("w-full").mark("model_check"):
        ui.label(AI_RISK).classes("text-sm text-orange-800").mark("ai_risk")
        checker = model_select("the checking model", CHECKER_MODELS, DEFAULT_CHECKER, default=DEFAULT_CHECKER)
        same = ui.label("").classes("text-sm text-orange-800").mark("same_model")
        made_by = drafter(catalog, revision)

        def warn(_event=None) -> None:
            same.text = (f"{model_name(made_by)} drafted this record: its check is not a second model's reading."
                         if made_by and made_by == checker.value else "")
        checker.on_value_change(warn)
        warn()
        gate = budget_form("the most the check and its re-readings may spend in all ($)", models=(checker,))
        consent = ui.checkbox(CONSENT).mark("model_check_consent")

        def start() -> None:
            from adroit.orchestrator.record_check import RecordChecker
            verdict = gate()
            if not verdict.ok:
                ui.notify(verdict.message)
                return
            if not consent.value:
                ui.notify("tick that you choose the model's check and accept that it can make errors")
                return
            try:
                run = RecordChecker(catalog).start(revision.reference, item.result_id, verdict.amount, checker.value,
                                                   approval=verdict.approval)
                _launch(root, run, verdict.amount, verdict.approval)
            except (ValueError, OSError) as error:
                ui.notify(str(error))
        ui.button("Check it with the model", on_click=start).props("color=primary").mark("start_model_check")
    _earlier(root, catalog, revision, item)


def _earlier(root: Path, catalog, revision, item) -> None:
    """This result's check sessions, newest first: an approval's review, or the mismatches and the two ways on."""
    from adroit.core.pricing import model_name
    from adroit.orchestrator.record_check import RecordChecker
    try:
        found = RecordChecker(catalog).sessions(revision.reference, item.result_id)
    except (ValueError, OSError):
        return
    for run, outcome in found[:3]:
        with ui.card().classes("w-full").mark("check_outcome"):
            state = STATUS.get(outcome.status, outcome.status) if outcome else "running or not finished"
            ui.label(f"Check by {model_name(run.model)}, {run.created_at[:16]}: {state}").classes("font-medium")
            if outcome is None:
                continue
            if outcome.final_revision != revision.reference:
                ui.link("its last revision of the record", "/experiments/view?" + urlencode(
                    {"reference": outcome.final_revision}))
            if outcome.status == "approved":
                ui.label(f"Review {outcome.review_id}: give it as the source review receipt below to validate and "
                         "bind the limit; it says it was the model's check, not a person's.").classes("text-sm")
            for line in outcome.mismatches:
                ui.label("mismatch: " + line).classes("text-sm text-red-800").mark("mismatch")
            for line in outcome.notes:
                ui.label("note: " + line).classes("text-sm text-gray-700")
            if outcome.why and outcome.status != "approved":
                ui.label(outcome.why).classes("text-sm text-gray-700")
            if outcome.status == "needs_you":
                _ways_on(root, catalog, outcome, run)


def _ways_on(root: Path, catalog, outcome, run) -> None:
    """After no agreement: approve the record yourself (the form above, a person's review), or suggest another route,
    which the record assistant applies as a new revision, checked once more."""
    from adroit.ui.pages import budget_form, model_select
    ui.label("Approve the record yourself with the review form above (a person's review), or suggest another route: "
             "the record assistant applies it as a new revision, and the model checks it again.").classes("text-sm")
    with ui.expansion("Suggest another route (paid)").classes("w-full").mark("suggest_route"):
        text = ui.textarea("Your suggestion (another table or figure, how a condition should read, a newer paper)") \
            .classes("w-full").props("rows=3").mark("suggestion")
        from adroit.core.pricing import CHECKER_MODELS, DEFAULT_CHECKER
        # the earlier check's model chosen, the system's default kept apart: only Fable's spend is auto-approved (PR-01)
        checker = model_select("the checking model", CHECKER_MODELS, run.model, default=DEFAULT_CHECKER)
        gate = budget_form("the most it may spend in all ($)", models=(checker,))

        def go() -> None:
            from adroit.orchestrator.record_check import RecordChecker
            verdict = gate()
            if not verdict.ok:
                ui.notify(verdict.message)
                return
            if not (text.value or "").strip():
                ui.notify("write your suggestion first")
                return
            try:
                again = RecordChecker(catalog).start(outcome.final_revision, run.result_id, verdict.amount,
                                                     checker.value, run.reanalysis_model, retries=0,
                                                     instruction=text.value, approval=verdict.approval)
                _launch(root, again, verdict.amount, verdict.approval)
            except (ValueError, OSError) as error:
                ui.notify(str(error))
        ui.button("Apply my suggestion and check again", on_click=go).mark("apply_suggestion")
