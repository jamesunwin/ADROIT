"""A targeted reassessment of a saved study (the owner's plan of 2026-11-24, "signal-qualified planes and decisive DD
exclusions", section 4): what the saved study lacks is calculated, and nothing else.

- **Explain a signal** (``single_idea``): the signal requirement imposed on its saved plane (``single_idea.signal_
  plane``: the model's physical prediction at every grid point and thermal crossing) and its headline read with it.
  No fit, scan or constraint is computed again.
- **Constrain a model** (``track1``): the halo work of every thermal point whose halo coverage is incomplete, done
  again with the count ratio's validations now in force (the original and the targeted one) and an explicit, bounded
  budget of full calculations per point (``budget``). Each point's saved nominal evaluation, its relic density and
  every halo-independent comparison, is reused as it was saved (``halo_evaluation.evaluate``'s ``nominal``), never
  recomputed. A point halo-sensitive or decided is left as it was saved: nothing forces it robust.

The result is a new study, its parent the saved one, written through the same writer as any run (``runs._write``): its
lineage (``reassessment.json``, and in its evidence) names the original's result and evidence digests, what was
calculated (each point, before and after, its full calculations and its time), the halo data and policy in force, and
the budget. The original's files are not changed (only its study record gains the child, as for any child study), and
nothing of it is certified again on viewing: the points left as saved keep their certificates, earlier policy and all.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from adroit.core.chronology import utc_now

DEFAULT_BUDGET = 12          # full calculations per reassessed point (``HaloPreset.full_calculations``; at most 64)


def reassess(source: Path, out: Path, budget: int = DEFAULT_BUDGET) -> tuple[Path, str]:
    """Reassess the saved study at ``source`` (its folder) into the new folder ``out``: (the folder, its report)."""
    from adroit.evidence.version import resolve
    from adroit.orchestrator import runs
    source = Path(source)
    found = resolve(source / "result.json")
    snapshot = found.saved()
    workflow, result = snapshot.workflow, snapshot.result
    if not 1 <= budget <= 64:
        raise ValueError(f"budget: give 1 to 64 full calculations per point, not {budget}")
    started = time.perf_counter()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if workflow == "single_idea":
        new, steps = _single_idea(result, out)
    elif workflow == "track1":
        new, steps = _track1(result, budget, out)
    else:
        raise ValueError(f"a {workflow} study has nothing this reassessment calculates")
    lineage = {"kind": "reassessment", "source": str(source.resolve()), "source_result_sha256": found.result_sha256,
               "source_evidence_sha256": found.identity("evidence"), "workflow": workflow,
               "reassessed_at": utc_now(), "seconds": round(time.perf_counter() - started, 1),
               "policy": _policy(), "budget_per_point": budget if workflow == "track1" else None,
               "calculated": steps,
               "not_recalculated": "every fit, scan, relic density and halo-independent comparison is the original's"}
    beside = {"reassessment.json": lineage}
    title = f"Reassessment: {_title(result, workflow)}"
    report = _report(new, workflow, lineage)
    runs._write(out, new, report, workflow, title, parent=source.resolve(), certify=lambda digest: {
        "reassessment_lineage": lineage}, beside=beside)
    return out, report


def _policy() -> dict:
    """What decided the reassessed points: the certificate policy, the equation-of-state policy, and the halo data
    files' identities as they are now (the count ratio's validations among them)."""
    from adroit.core.certificate import EOS_POLICY, POLICY
    from adroit.core.halo_choice import HALO_DATA, data_identity
    return {"certificate_policy": POLICY, "eos_policy": EOS_POLICY, "halo_data": data_identity(tuple(HALO_DATA))}


def _title(result, workflow: str) -> str:
    request = result.request
    return f"{request.spec.name} for {request.experiment}" if workflow == "single_idea" else request.spec.name


def _single_idea(result, folder: Path) -> tuple[object, list[dict]]:
    """The saved Explain a signal study with its plane's signal requirement imposed (``single_idea.reassessed``)."""
    from adroit.orchestrator import single_idea
    new = single_idea.reassessed(result, folder)
    plane = new.signal_plane
    steps = [{"what": "the signal assessment at every grid point and thermal crossing of the saved plane",
              "grid_points": len(plane.grid) if plane else 0, "crossings": len(plane.crossings) if plane else 0,
              "rows": plane.counts() if plane else {}, "level_before": result.level, "level_after": new.level}]
    return new, steps


def _track1(result, budget: int, folder: Path) -> tuple[object, list[dict]]:
    """The saved Constrain a model study with each incomplete thermal point's halo work done again
    (``track1.reassessed``)."""
    from adroit.orchestrator import track1
    return track1.reassessed(result, budget, folder)


def _report(result, workflow: str, lineage: dict) -> str:
    """The new study's report: what was reassessed, then the study's own report of the reassessed result."""
    from adroit.orchestrator import single_idea, track1
    head = ["# Reassessment", "",
            f"A targeted reassessment of the saved study at `{lineage['source']}` (its result's SHA-256 "
            f"`{lineage['source_result_sha256']}`), on {lineage['reassessed_at']}: "
            + ("the signal requirement imposed on its saved plane." if workflow == "single_idea" else
               f"the halo work of each thermal point whose halo coverage was incomplete, done again with at most "
               f"{lineage['budget_per_point']} full calculations per point.")
            + " " + lineage["not_recalculated"][0].upper() + lineage["not_recalculated"][1:]
            + ". Its lineage is in `reassessment.json`.", ""]
    for step in lineage["calculated"]:
        head.append("- " + json.dumps(step, ensure_ascii=False)[:400])
    body = single_idea.report(result) if workflow == "single_idea" else track1.report(result)
    return "\n".join(head) + "\n\n" + body


def digest(path: Path) -> str:
    """A file's SHA-256 (for the tests' and the owner's checks that an original is unchanged)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
