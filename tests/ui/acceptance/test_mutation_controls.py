"""The gate's mutation controls (the auditor's consistency audit, section E; the consolidation plan's M4): each restores a
defect the audits found, and the journey that covers it must then fail at the invariant the defect breaks, although
every command still exits 0. A gate that passed with one of these in place would not be guarding what it claims to.

Each control (the auditor's consolidation audit, CO-08, 2026-10-25) first runs the journey as built and requires it to
pass: a journey that cannot run here (a missing prerequisite, a setup error) makes the control fail as "not
established", never a detected mutation. It then restores the defect and requires the journey to fail at its own
invariant: the AssertionError names the text the defect removes (the badge, the cost, the destination), or the page
fails with the defect's own error. Any other failure fails the control. ``test_each_control_fails_without_its_defect``
runs every control with its defect left out and requires the control itself to fail: a control that passed anyway
would be detecting nothing.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from nicegui.testing import User
from pydantic import ValidationError

from adroit.ui import engine
from tests.ui.acceptance.test_journeys import (inline, journey_settled_bill, journey_typed_intake_to_study,  # noqa: F401
                                               journey_uncertain_bill, provider)
from tests.ui.test_run_outcomes import IDEA_TOKENS, VALUES_TOKENS, dollars, usd

SUBSTITUTED = {"each control": "a monkeypatch restoring one defect in process; the journey is otherwise unchanged, "
                               "and is first run as built and required to pass"}
UNGUARDED = "the journey passed with the defect restored: the gate does not guard it"


async def guards(journey, restore, invariant) -> str:
    """The control: ``journey`` (a function making a fresh run of it) passes as built; after ``restore()`` it fails at
    ``invariant``: text its AssertionError must name, or a predicate on the error. Returns why it failed."""
    try:
        await journey()
    except Exception as error:                       # noqa: BLE001 - reported, never counted as a detection
        raise AssertionError(f"not established: the journey fails as built ({type(error).__name__}: "
                             f"{str(error)[:300]}); a missing prerequisite is never a detected mutation") from error
    restore()
    try:
        await journey()
    except Exception as error:                       # noqa: BLE001 - judged against the invariant below
        held = invariant(error) if callable(invariant) else (isinstance(error, AssertionError)
                                                             and invariant in str(error))
        if not held:
            raise AssertionError(f"the journey failed with the defect restored, but not at its invariant "
                                 f"({invariant if isinstance(invariant, str) else invariant.__doc__}): "
                                 f"{type(error).__name__}: {str(error)[:300]}") from error
        return f"{type(error).__name__}: {str(error)[:200]}"
    raise AssertionError(UNGUARDED)


def _not_led_to_the_draft(error: Exception) -> bool:
    """the intake's run page does not lead to its draft: its outcome ("Draft ready for review") or the draft itself
    ("Candidate 1: RealSinglet") is missing"""
    return isinstance(error, AssertionError) and any(
        f"content={words}" in str(error) for words in ("Draft ready for review", "Candidate 1: RealSinglet"))


async def control_study_viewer(user, tmp_path, monkeypatch, provider, inline, defect: bool = True):  # noqa: F811
    """The owner's report of 2026-10-23: an intake's run was read as a physics study, its primary button opening the
    study viewer. Invariant: the intake's run page leads to its draft."""
    from adroit.ui import outcomes
    from adroit.ui.app import build_pages
    build_pages(tmp_path / "runs")
    return await guards(lambda: journey_settled_bill(user, tmp_path / "runs", provider, inline),
                        lambda: defect and monkeypatch.setattr(outcomes, "kind_of", lambda job: "study"),
                        _not_led_to_the_draft)


async def control_tiny_settlement(user, tmp_path, monkeypatch, provider, inline, defect: bool = True):  # noqa: F811
    """The workflow audit's WA-03: a $0.0008 settlement shown as $0. Invariant: the run's own settled cost shown."""
    from adroit.orchestrator import accounting
    from adroit.ui.app import build_pages
    build_pages(tmp_path / "runs")
    original = accounting._from_receipt
    return await guards(lambda: journey_settled_bill(user, tmp_path / "runs", provider, inline),
                        lambda: defect and monkeypatch.setattr(accounting, "_from_receipt", lambda out, receipt,
                            requests: original(out, receipt, requests).model_copy(update={"run_usd": 0.0})),
                        f"This run: {usd(dollars('anthropic', IDEA_TOKENS) + dollars('anthropic', VALUES_TOKENS))}")


async def control_eos_prerequisite(user, tmp_path, monkeypatch, inline, defect: bool = True):  # noqa: F811
    """V1-01 and CA-01: a thermal claim certified without the equation-of-state tables. Invariant: without the tables
    the study's badge is VIABLE PENDING (the stored level), never VIABLE."""
    from adroit.parameter_space import certification, verdict
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    certify = certification.certify

    def restore():
        if defect:
            monkeypatch.setattr(verdict, "_awaiting_eos", lambda c, missing: c)
            monkeypatch.setattr(certification, "certify", lambda c, kind, scope, checks, **k: certify(
                c, kind, scope, [x for x in checks if x.name != "eos_band"], **k))
    return await guards(lambda: journey_typed_intake_to_study(user, root, monkeypatch, tables=False), restore,
                        "VIABLE PENDING")


async def control_erased_reservation(user, tmp_path, monkeypatch, provider, inline, defect: bool = True):  # noqa: F811
    """WA-03 and CA-05: a request whose bill is unknown read as if nothing were reserved. Invariant: the run page
    shows the reservation."""
    from adroit.agents import budget
    from adroit.orchestrator import model_intake
    from adroit.ui.app import build_pages
    build_pages(tmp_path / "runs")
    read, raised, held = budget.read_ledger, budget.read_raised, budget.read_held

    def erase(requests):
        return {k: (r.model_copy(update={"state": "settled", "cost_usd": 0.0, "settled_line": 0})
                    if r.state != "settled" else r) for k, r in requests.items()}

    def erased(path):
        return erase(read(path))

    def erased_with_raises(path):          # a session's reading of its requests and cap raises (DG-01)
        found = raised(path)
        return erase(found[0]), found[1]

    def erased_as_held(path):              # and what its ledger held (the auditor's DN recheck, DO-01)
        found = held(path)
        return erase(found[0]), found[1], found[2]

    def restore():
        if defect:
            monkeypatch.setattr(budget, "read_ledger", erased)
            monkeypatch.setattr(model_intake, "read_ledger", erased)
            monkeypatch.setattr(budget, "read_raised", erased_with_raises)
            monkeypatch.setattr(model_intake, "read_raised", erased_with_raises)
            monkeypatch.setattr(budget, "read_held", erased_as_held)
            monkeypatch.setattr(model_intake, "read_held", erased_as_held)
    return await guards(lambda: journey_uncertain_bill(user, tmp_path / "runs", provider), restore,
                        "reserved whose bill is not yet known")


def _the_job_record_breaks_the_page(error: Exception) -> bool:
    """the Studies page fails on the malformed job record's validation, or no longer lists the healthy study"""
    return (isinstance(error, ValidationError) and "Job" in str(error)
            or isinstance(error, AssertionError) and "a healthy study" in str(error))


async def control_malformed_job(user, tmp_path, monkeypatch, caplog, defect: bool = True):
    """CA-07: one {} job record beside a valid study made the Studies page fail. Invariant: the healthy study listed."""
    from adroit.orchestrator import studies
    from adroit.ui.app import build_pages
    root = build_pages(tmp_path / "runs")
    healthy = root / "healthy"
    healthy.mkdir(parents=True)
    engine.save(engine.Job(title="a healthy run", kind="track1", folder=str(healthy), command=["track1"],
                           status="completed", returncode=0))
    studies.record(healthy, "track1", "a healthy study")
    (root / "broken").mkdir()
    (root / "broken" / engine.JOB).write_text("{}")

    async def journey():
        await user.open("/studies")
        await user.should_see("a healthy study")
    try:
        return await guards(journey, lambda: defect and monkeypatch.setattr(
            engine, "listing", lambda r: ([engine.load(p.parent) for p in Path(r).rglob(engine.JOB)], [])),
            _the_job_record_breaks_the_page)
    finally:
        caplog.clear()                                # the page's error is the restored defect's, expected here


async def test_the_study_viewer_for_an_intake_folder_fails_journey_1(user: User, tmp_path, monkeypatch, provider,  # noqa: F811
                                                                      inline):  # noqa: F811
    assert await control_study_viewer(user, tmp_path, monkeypatch, provider, inline)


async def test_a_tiny_settlement_shown_as_zero_fails_journey_1(user: User, tmp_path, monkeypatch, provider,  # noqa: F811
                                                                inline):  # noqa: F811
    assert await control_tiny_settlement(user, tmp_path, monkeypatch, provider, inline)


@pytest.mark.eos_band
async def test_an_eos_prerequisite_removed_from_the_certificate_fails_journey_1(user: User, tmp_path, monkeypatch,
                                                                                 inline):  # noqa: F811
    assert await control_eos_prerequisite(user, tmp_path, monkeypatch, inline)


async def test_an_erased_reservation_fails_journey_1(user: User, tmp_path, monkeypatch, provider, inline):  # noqa: F811
    assert await control_erased_reservation(user, tmp_path, monkeypatch, provider, inline)


async def test_a_malformed_job_breaking_the_listing_fails_journey_6(user: User, tmp_path, monkeypatch, caplog):
    assert await control_malformed_job(user, tmp_path, monkeypatch, caplog)


@pytest.mark.parametrize("control", ["study_viewer", "tiny_settlement",
                                     pytest.param("eos_prerequisite", marks=pytest.mark.eos_band),
                                     "erased_reservation", "malformed_job"])
async def test_each_control_fails_without_its_defect(user: User, tmp_path, monkeypatch, provider, inline, caplog,  # noqa: F811
                                                     control):
    """CO-08's negative control: with its defect left out, each control must fail (the journey passes twice), so that a
    green control means its defect was detected, at its invariant."""
    run = {"study_viewer": lambda: control_study_viewer(user, tmp_path, monkeypatch, provider, inline, defect=False),
           "tiny_settlement": lambda: control_tiny_settlement(user, tmp_path, monkeypatch, provider, inline,
                                                              defect=False),
           "eos_prerequisite": lambda: control_eos_prerequisite(user, tmp_path, monkeypatch, inline, defect=False),
           "erased_reservation": lambda: control_erased_reservation(user, tmp_path, monkeypatch, provider, inline,
                                                                    defect=False),
           "malformed_job": lambda: control_malformed_job(user, tmp_path, monkeypatch, caplog, defect=False)}[control]
    with pytest.raises(AssertionError, match=UNGUARDED):
        await run()
