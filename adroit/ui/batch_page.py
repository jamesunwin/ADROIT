"""The workbench's batch queue and bundle viewer pages (the batch plan's §7).

- **Batches** (``/batches``): the draft (requests added from the wizards, each removable), started as one batch with its
  total budget confirmed, and every batch with each request's status and live view; a running batch can be cancelled.
- **Open a bundle** (``/bundle``): an exported evidence bundle (``evidence.archive.export_run``) checked read-only by
  ``verify_bundle``: whether its hashes agree, what that does and does not show, its saved decisions and any issue.
  Nothing is run or written.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from nicegui import ui

STATUS = {"queued": "grey", "running": "blue", "completed": "green", "budget_stopped": "orange", "failed": "red",
          "cancelled": "grey", "interrupted": "orange", "refused": "red"}


def batches_page(root: Path) -> None:
    """The draft and the batches (module docstring)."""
    from adroit.ui import batch
    from adroit.ui.pages import header
    from adroit.ui.style import section
    header("Batches", "Several requests run one after another, each as its own run with its own folder, log and "
           "budget. Add requests from the wizards (the \"Add to the batch\" switch), then start them here.",
           facts=("one request at a time", "a paid request keeps the budget you confirmed for it"))
    items, unreadable = batch.draft_listing(root)
    with section("The draft", "Requests waiting to be started together."):
        if unreadable:                       # named; nothing to start, and nothing added over it (M3)
            ui.label(unreadable).classes("text-sm text-orange-800").mark("unreadable_draft")
        elif not items:
            ui.label("Empty: turn on \"Add to the batch\" on a wizard's page, then prepare a request as usual.") \
                .classes("text-gray-500")
        for item in items:
            with ui.row().classes("items-center gap-2"):
                ui.label(item.title).classes("font-medium")
                ui.label(" ".join(item.command)[:120]).classes("text-xs font-mono text-gray-600")
                if item.budget_usd:
                    ui.badge(f"${item.budget_usd:.2f}", color="orange")
                ui.button("Remove", on_click=lambda it=item: _remove(root, it)).props("flat dense")
        if items:
            _start_form(root, items)
    found, damaged = batch.listing(root)
    with section("Batches", "Newest first; each request opens its live view."):
        from adroit.ui.pages import _damaged
        _damaged(root, "batch record(s)", damaged, "unreadable_batches")    # CA-07: named; the rest are listed
        if not found:
            ui.label("No batches yet.").classes("text-gray-500")
        for b in found[:30]:
            _batch_card(root, b)


def _remove(root: Path, item) -> None:
    """Remove the request this page shows (by its identity, NP17-02), then show the draft as it is now."""
    from adroit.ui import batch
    try:
        batch.remove_from_draft(root, item)
    except (ValueError, OSError) as error:
        ui.notify(str(error))
    ui.navigate.to("/batches")


def _start_form(root: Path, items) -> None:
    from adroit.ui import batch, engine, submission
    shown = batch.draft_digest(items)                 # the requests this page shows, bound to its Start (NP17-02)
    total = sum(x.budget_usd for x in items)
    title = ui.input("The batch's name", value=f"{len(items)} requests").mark("batch_title")
    confirm = ui.number(f"Confirm the batch's total budget ($): {total:.2f}", value=0.0, min=0.0, format="%.2f") \
        .mark("batch_budget") if total > 0 else None

    def go() -> None:
        try:
            batch.start(root, title.value or "batch", float(confirm.value or 0.0) if confirm else 0.0, shown=shown)
        except batch.DraftChanged as error:               # kept: shown again as it is now, to be confirmed again
            ui.notify(str(error), multi_line=True)
            ui.navigate.to("/batches")
            return
        except (ValueError, engine.BudgetNotConfirmed) as error:
            ui.notify(str(error))
            return
        submission.go("/batches")
    ui.button("Start the batch", on_click=submission.once(go)).mark("start_batch")


def _batch_card(root: Path, b) -> None:
    """A batch: its status, approved budget, its items each with its run's cost, and the batch's spending in all
    (``accounting.total``: settled, reserved and unavailable apart; M2: the page had shown budgets alone)."""
    from adroit.orchestrator import accounting
    from adroit.ui import batch
    from adroit.ui.pages import rel
    with ui.card().classes("w-full").mark("batch"):
        with ui.row().classes("items-center gap-2"):
            ui.badge(b.status, color=STATUS.get(b.status, "grey"))
            ui.label(b.title).classes("font-medium")
            ui.label(b.created).classes("text-xs text-gray-500")
            if b.budget_usd:
                ui.label(f"approved budget {accounting.usd(b.budget_usd)}").classes("text-xs")
            if b.status == "running":
                ui.button("Cancel", on_click=lambda f=b.folder: (batch.cancel(Path(f)), ui.notify(
                    "cancelling: the running request stops, the rest will not start"))).props("outline dense")
            if b.status in ("interrupted", "refused"):
                _resume_form(b)
        if b.approval_sha256:
            ui.label(f"approval {b.approval_sha256[:12]}… (the requests and budgets confirmed)").classes(
                "text-xs font-mono text-gray-500")
        costs = []
        for item in b.items:
            c = _item_cost(item)
            costs.append(c)
            with ui.row().classes("items-center gap-2"):
                ui.badge(item.status, color=STATUS.get(item.status, "grey"))
                ui.link(item.title, "/live?" + urlencode({"path": rel(root, item.folder)}))
                shown = accounting.short_line(c) if c is not None else "not started"
                if shown:
                    ui.label(shown).classes("text-xs text-gray-600").mark("item_cost")
                if item.error:
                    ui.label(item.error[:160]).classes("text-xs text-red-600")
        started = [c for c in costs if c is not None]
        if any(c.paid for c in started):
            ui.label("spent: " + accounting.total_text(accounting.total(started))).classes("text-xs").mark("batch_cost")


def _item_cost(item):
    """A batch item's run's cost (``accounting.study_cost``: its run's records, the run page's figure), None for an
    item whose run has not started (no run record in its folder at all: one that leads nowhere is its run's, damaged,
    DN-01)."""
    from adroit.core.durable import absent
    from adroit.orchestrator import accounting
    folder = Path(item.folder)
    if absent(folder / accounting.JOB):
        return None
    return accounting.study_cost(folder)


def _resume_form(b) -> None:
    """Resume a stopped batch with a new confirmation of its total (``batch.resume``)."""
    from adroit.ui import batch, engine, submission
    total = sum(engine.paid(i.command) for i in b.items)
    confirm = ui.number(f"Confirm the total again ($): {total:.2f}", value=0.0, min=0.0, format="%.2f").props("dense") \
        if total > 0 else None

    def go() -> None:
        try:
            batch.resume(Path(b.folder), float(confirm.value or 0.0) if confirm else 0.0)
        except (ValueError, engine.BudgetNotConfirmed) as error:
            ui.notify(str(error))
            return
        submission.go("/batches")
    ui.button("Resume", on_click=submission.once(go)).props("outline dense")


def bundle_page(path: str = "") -> None:
    """An exported bundle, checked read-only (module docstring)."""
    from adroit.ui.pages import header
    header("Open a bundle", "Check an exported evidence bundle: whether its files agree with their recorded hashes, "
           "and the decisions it holds. Nothing is run or written.",
           facts=("read-only", "agreement of hashes, not authorship"))
    where = ui.input("The bundle's folder or file", value=path).classes("w-full").mark("bundle_path")
    results = ui.column().classes("w-full")

    def check() -> None:
        results.clear()
        with results:
            _show_bundle(Path(where.value).expanduser())
    ui.button("Check", on_click=check).mark("check_bundle")
    if path:
        with results:
            _show_bundle(Path(path).expanduser())


def _show_bundle(path: Path) -> None:
    from adroit.evidence.archive import verify_bundle
    if not path.exists():
        ui.label(f"Not found: {path}").classes("text-red-600")
        return
    try:
        checked = verify_bundle(path)
    except (OSError, ValueError) as error:
        ui.label(f"Not a bundle ADROIT can read: {error}").classes("text-red-600")
        return
    with ui.row().classes("items-center gap-2"):
        ui.badge("hashes agree" if checked.valid else "does not verify", color="green" if checked.valid else "red") \
            .mark("bundle_verdict")
        ui.label(f"archive sha256 {checked.archive_sha256[:16]}…").classes("text-xs font-mono")
    ui.label(checked.assurance).classes("text-sm text-gray-600")
    for issue in checked.issues:
        ui.label(issue).classes("text-sm text-red-600")
    if checked.nodes:
        ui.label(f"Saved decisions ({len(checked.nodes)})").classes("font-medium mt-2")
        for node in checked.nodes:
            with ui.expansion(f"{node.workflow}: {node.id}").classes("w-full"):
                ui.label(f"evidence {node.evidence_identity[:16]}…; {node.provenance}").classes("text-xs font-mono")
                scope = ""
                if node.workflow == "signal":          # the widest search's significance first, declared (PT-01)
                    from adroit.orchestrator.signal import scope_text
                    scope = scope_text(node.summary.get("agent_search"), node.summary.get("halo_scan"))
                    if scope:
                        ui.label(scope).classes("text-sm font-medium").mark("bundle_scope")
                for key, value in node.summary.items():
                    shown = "its significance is given above" if scope and key in ("agent_search", "halo_scan") \
                        else str(value)[:200]
                    ui.label(f"{key}: {shown}").classes("text-sm")
    ui.label(f"Reproduction: {checked.reproduction_status}"
             + (f" ({'; '.join(checked.reproduction_reasons)})" if checked.reproduction_reasons else "")) \
        .classes("text-sm")
