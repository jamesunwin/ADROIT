"""Typed result loading and summaries; no calculation occurs on this path."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, JsonValue


def result_type(workflow: str) -> type[BaseModel]:
    """Return the existing schema for a supported evidence workflow."""
    from adroit.orchestrator.track1 import Track1Result
    from adroit.orchestrator.signal import SignalResult
    from adroit.orchestrator.single_idea import SingleIdeaResult
    from adroit.orchestrator.promote import Promotion
    from adroit.orchestrator.exclusion import ExclusionResult
    from adroit.parameter_space.native_joint import JointResult
    from adroit.parameter_space.native_coverage import CoverageResult
    from adroit.orchestrator.ideas import IdeaResult
    from adroit.orchestrator.lagrangian import LagrangianResult

    known = {"track1": Track1Result, "signal": SignalResult, "single_idea": SingleIdeaResult,
             "promotion": Promotion, "native_joint": JointResult, "native_coverage": CoverageResult,
             "exclusion": ExclusionResult, "idea": IdeaResult, "lagrangian": LagrangianResult}
    if workflow not in known:
        raise ValueError(f"unsupported evidence workflow: {workflow}")
    return known[workflow]


def load_result(path: Path, workflow: str = "") -> tuple[str, BaseModel]:
    """Read an existing typed result, including pre-evidence legacy files. A file that is not a JSON object raises
    ``ValueError`` naming what it holds (the auditor's CO recheck, CR-06, 2026-10-26: ``null`` or a list had raised a
    ``TypeError`` that no page caught); a missing one, ``FileNotFoundError``."""
    from adroit.core.durable import read_object
    data, why = read_object(path)
    if why:
        raise ValueError(f"{Path(path).name} {why}")
    if data is None:
        raise FileNotFoundError(f"{path}: no saved result")
    return typed(data, workflow)


def typed(data: dict[str, Any], workflow: str = "") -> tuple[str, BaseModel]:
    """A result's JSON object as its workflow's typed result (``workflow``, else the one its fields name), as
    ``load_result`` reads a file: for a page that has read the file once (``study_headline.snapshot``)."""
    kind = workflow or _detect(data)
    return kind, result_type(kind).model_validate(data)


def records_read(workflow: str, result: BaseModel) -> dict[str, str]:
    """The version of each curated record a result's calculation read outside the scan, as the result keeps it: an
    exclusion's telescope limits (a Lagrangian's exclusion's too) and a signal study's complementary verdicts; "" for a
    record read in two versions, within one part or across them (the auditor's CV recheck, CW-02, 2026-10-30). A result saved
    before keeps none. The scan's claims are bound claim by claim, in their certificates."""
    pairs: list[tuple[str, str]] = []
    exclusion = result if workflow == "exclusion" else getattr(result, "exclusion", None) if workflow == "lagrangian" \
        else None
    if exclusion is not None:
        pairs += [(t.record_id, t.record_version) for t in exclusion.telescopes if t.record_version is not None]
    if workflow == "signal":
        pairs += [pair for read in result.verdict_records.values() for pair in read.items()]
    out: dict[str, str] = {}
    for rid, held in pairs:
        out[rid] = held if out.get(rid, held) == held else ""
    return out


def inputs_read(workflow: str, result: BaseModel) -> dict[str, str]:
    """The version of each selected input file a result's calculation consumed, as the result keeps it (location: its
    SHA-256): a signal study's saved Track 1 results reused for physical eligibility, each with its evidence; "" for a
    file consumed in two versions. The auditor's CX recheck, CY-01 (2026-11-01): a run captures its selected inputs at its
    start and its end, and B consumed between A at both had left it "captured". A result saved before keeps only the
    path it reused, and none here: no version is made up for it by reading the path now."""
    from adroit.evidence.build import sidecar_path
    pairs: list[tuple[str, str]] = []
    if workflow == "signal":
        for row in result.eligibility.values():
            if row.constraints_origin == "saved_exact_track1_point" and row.reused_result and row.reused_result_sha256:
                pairs += [(row.reused_result, row.reused_result_sha256),
                          (str(sidecar_path(Path(row.reused_result))), row.reused_evidence_sha256)]
    out: dict[str, str] = {}
    for location, held in pairs:
        out[location] = held if out.get(location, held) == held else ""
    return out


def _detect(data: dict[str, Any]) -> str:
    if "audit" in data and "request" in data:
        return "track1"
    if "tournament" in data and "fits" in data:
        return "signal"
    if "band" in data and "level" in data:
        return "single_idea"
    if "parent" in data and "labels" in data and "children" in data:
        return "promotion"
    if "signal_experiment" in data and "settings" in data and "fits" in data:
        return "native_joint"
    if "cases" in data and "construction" in data:
        return "native_coverage"
    if "per_module" in data and "interaction_name" in data:
        return "exclusion"
    if "models" in data and "dropped" in data and "request" in data:
        return "idea"
    if "contract" in data and "derivation" in data and "matches" in data:
        return "lagrangian"
    raise ValueError("result does not match a supported evidence workflow")


def summary(workflow: str, result: BaseModel) -> dict[str, JsonValue]:
    """Copy all decision/omission fields needed to reconstruct a saved conclusion."""
    payload = result.model_dump(mode="json")
    fields = {
        "track1": ("unsupported", "notes", "audit", "verdict", "likelihood_verdict", "coverage"),
        "signal": ("tournament", "global_z", "global_method", "global_p_toys", "verdicts",
                   "combinations", "candidate_failures", "classes", "separations"),
        "single_idea": ("level", "summary", "verified", "unsupported", "fit_quality",
                        "constraint_compatibility", "thermal_viability", "thermal_pending", "eos_thermal",
                        "physical_significance_note", "combination", "global_z", "global_method"),
        "promotion": ("labels", "children", "undetermined", "cost_usd"),
        "native_joint": ("complete", "omitted", "assumptions", "calibration", "best_point",
                         "observed_max_q0", "log_l_components", "background_theta", "null_backgrounds"),
        "native_coverage": ("complete", "conclusion", "construction", "fits", "cases"),
        "exclusion": ("per_module", "skipped", "flags", "telescopes"),
        "idea": ("models", "dropped"),
        "lagrangian": ("status", "checks", "dimension_problems", "comparison", "numerical", "matches",
                       "exclusion", "viability", "contract"),
    }
    result_summary = {key: payload[key] for key in fields[workflow] if key in payload}
    if workflow=='signal' and payload.get('eligible_tournament') is not None:
        for key in ('eligibility','eligible_tournament','unresolved_tournament','eligibility_combinations'):
            result_summary[key]=payload[key]
    if workflow == "signal":       # the wider searches' significances (the auditor's post-review recheck 2, PT-01): only
        for key in ("halo_scan", "agent_search"):      # where present, so an earlier summary is unchanged
            if payload.get(key) is not None:
                result_summary[key] = payload[key]
    if workflow in ("signal", "single_idea") and payload.get("global_p_interval") is not None:
        result_summary["global_toys"], result_summary["global_p_interval"] = payload["global_toys"], payload["global_p_interval"]
    if workflow in ("track1", "single_idea") and payload.get("viability"):
        result_summary["viability"] = payload["viability"]                 # R8; absent from older results
    if workflow == "native_joint" and payload.get("domain_fit") is not None:
        result_summary["domain_fit"] = payload["domain_fit"]
    return result_summary


def _canonical(model: BaseModel) -> str:
    """A typed result as canonical JSON: the comparison ``summary_matches`` and ``copies_match`` make. A NaN (a
    missing or unestablished statistic) is written NaN on both sides, so it equals itself and differs from any number
    and from null; model equality had compared two parses' NaNs as unequal (the RY23 audit's RZ23-02, 2026-10-23: an
    unchanged pending result with a NaN fit was refused as a "decision mismatch")."""
    return json.dumps(model.model_dump(mode="json"), sort_keys=True, allow_nan=True)


def summary_matches(workflow: str, stored: dict[str, JsonValue], result: BaseModel) -> bool:
    """Validate saved conclusions through additive typed defaults, retaining their original representation."""
    current = summary(workflow,result)
    if stored.keys() != current.keys():
        return False
    try:
        reconstructed = type(result).model_validate({**result.model_dump(mode="json"),**stored})
    except ValueError:
        return False
    return _canonical(reconstructed) == _canonical(result)


# The scientific fields an envelope copies from its result: (where in the envelope, the copy's key, the result's field,
# dotted for a nested one; None for the whole result). A copy must say what the result says (the batch audit's
# B20-03: a Lagrangian's Wilson coefficients changed in the result had left its certificate's copy behind, verified).
COPIES: dict[str, list[tuple[str, str, str | None]]] = {
    "track1": [("certificates", "audit", "audit"), ("certificates", "coverage", "coverage"),
               ("certificates", "cuts", "verdict"), ("certificates", "likelihood", "likelihood_verdict")],
    "single_idea": [("certificates", "audit", "track1.audit"), ("certificates", "coverage", "track1.coverage"),
                    ("certificates", "cuts", "track1.verdict"), ("certificates", "likelihood", "track1.likelihood_verdict"),
                    ("certificates", "thermal", "thermal"), ("certificates", "native_joint", "native_joint")],
    "signal": [("certificates", "fits", "fits"), ("certificates", "null_comparisons", "combinations"),
               ("certificates", "physical_eligibility", "eligibility")],
    "native_joint": [("certificates", "fits", "fits"), ("certificates", "calibration", "calibration"),
                     ("certificates", "omitted", "omitted"), ("certificates", "multiparameter_fit", "domain_fit")],
    "exclusion": [("certificates", "exclusion", None)],
    "lagrangian": [("engine_mapping", "interactions", "interactions"), ("engine_mapping", "card_matches", "matches"),
                   *[("certificates", k, k) for k in ("checks", "derivation", "second", "comparison", "numerical",
                                                      "contract", "exclusion")]],
}


def copies_match(workflow: str, envelope, result: BaseModel) -> bool:
    """Whether every scientific copy the envelope holds (``COPIES``; the idea's audits and model names) says what the
    typed result says, through its schema's additive defaults as ``summary_matches`` does; no physics is rerun. A copy
    an older envelope does not hold is not checked."""
    payload = result.model_dump(mode="json")
    overlay = json.loads(json.dumps(payload))
    for where, key, field in COPIES.get(workflow, []):
        stored = getattr(envelope, where)
        if key not in stored:
            continue
        if field is None:
            overlay = stored[key]
            continue
        *parents, last = field.split(".")
        target = overlay
        for name in parents:
            target = target.get(name) if isinstance(target, dict) else None
        if not isinstance(target, dict):
            return False
        target[last] = stored[key]
    if workflow == "idea" and not _idea_copies(envelope, payload, overlay):
        return False
    try:
        return _canonical(type(result).model_validate(overlay)) == _canonical(result)
    except ValueError:
        return False


def _idea_copies(envelope, payload: dict, overlay: dict) -> bool:
    """An idea's copies: each model's name and source (the engine mapping) and audit, and the dropped proposals."""
    models = envelope.engine_mapping.get("models")
    audits = envelope.certificates.get("audits")
    if models is not None and models != [{"name": m["spec"]["name"], "source": m["source"]} for m in payload["models"]]:
        return False
    if audits is not None:
        if len(audits) != len(payload["models"]):
            return False
        for model, audit in zip(overlay["models"], audits):
            model["audit"] = audit
    if "dropped" in envelope.certificates:
        overlay["dropped"] = envelope.certificates["dropped"]
    return True
