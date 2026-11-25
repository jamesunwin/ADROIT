"""The halo of a saved result, as every page, table, export and command shows it (halo phase 1): read from the result,
never calculated again and never taken from today's defaults.

- A result saved since halo phase 1 holds its resolution (``halo_resolution``), as its run resolved it, with the
  identities of the halo data files it read: shown as recorded.
- An older result's is read from its saved request by the schema it was saved with (``halo_choice.resolve``): a region,
  ``published``, or, in a Track 1 or Explain a signal request saved before the choice existed, nothing, which was
  calculated with each experiment's published halo. Its halo data files' identities as read are not known, and it says
  so; today's files are never shown as its own.
- Each point's own qualification comes from its saved evaluation: its label over the region (excluded or allowed
  throughout, halo-sensitive, halo coverage incomplete), at the fixed benchmark, or the published halos.
"""
from __future__ import annotations

from adroit.core.halo_choice import Resolution, identity_of, resolve

WORKFLOWS = {"track1": "track1", "single_idea": "track1", "signal": "track2"}
RECORDED = "recorded with the result"
FROM_REQUEST = ("read from its saved request (an older result: the halo data files it read were not recorded with it, "
                "and today's are not shown as its own)")
# a saved resolution whose recorded values no longer give its identity: changed after it was saved, so neither describes
# the other (the auditor's halo phase 1 audit, HA-05, 2026-11-12)
ALTERED = ("recorded with the result, but its recorded values do not give that identity: the record was changed after "
           "it was saved")


def resolution_of(workflow: str, result) -> tuple[Resolution | None, str]:
    """(the halo a saved result was calculated with, how it is known), or (None, "") for a workflow with no halo."""
    if workflow not in WORKFLOWS:
        return None, ""
    saved = getattr(result, "halo_resolution", None)
    if saved is not None:
        return saved, RECORDED if identity_of(saved) == saved.identity else ALTERED
    value = getattr(getattr(result, "request", None), "halo", None)
    found = resolve(value, track=WORKFLOWS[workflow]).model_copy(update={"data": {}})
    return found.model_copy(update={"identity": identity_of(found)}), FROM_REQUEST


def line(workflow: str, result) -> str:
    """One line: the halo's label and summary, its identity, and how it is known ("" for a workflow with none)."""
    found, how = resolution_of(workflow, result)
    if found is None:
        return ""
    known = f"identity {found.identity[:12]}" if how != FROM_REQUEST else "identity not recorded"
    return f"Halo: {found.summary} ({known}; {how})"


def identity_note(workflow: str, result) -> str:
    """" (halo identity …, recorded with the result)", or, for an older result, that its identity was not recorded."""
    found, how = resolution_of(workflow, result)
    if found is None:
        return ""
    return f" (halo identity {found.identity[:12]}, {how})" if how != FROM_REQUEST else \
        " (its halo identity was not recorded: an older result)"


def point_label(evaluation, resolution: Resolution | None) -> str:
    """A point's halo qualification from its saved evaluation (``PointResult``): its label over the region, at the
    fixed benchmark, or the published halos ("" without an evaluation or a halo)."""
    if evaluation is None or resolution is None:
        return ""
    halo = getattr(evaluation, "halo", None)
    if halo is None:
        return resolution.label if resolution.treatment.value == "published" else \
            f"{resolution.label}: no halo evaluation saved with this point"
    if halo.treatment == "benchmark":
        from adroit.parameter_space.halo_region import AT_BENCHMARK
        return f"{AT_BENCHMARK} ({halo.region})"
    from adroit.parameter_space.verdict import classify
    return classify(None, evaluation).halo
