"""Loss-conscious adapters from existing calculations to common observations."""

from __future__ import annotations

import math

from pydantic import JsonValue

from adroit.core.evidence import (
    EvidenceContext, EvidenceObservation, physical_identity,
)
from adroit.parameter_space.scan import PointResult


def _finite(value: float | None) -> float | None:
    return value if value is not None and math.isfinite(value) else None


def _source_ids(reference: str, context: EvidenceContext) -> list[str]:
    references = reference.split("; ")
    return [s.id for s in context.sources if reference and any(r in (s.id, s.reference) for r in references)]


def review_label(review: str, ids: list[str], context: EvidenceContext | None) -> str:
    """A review state as people read it: a verified one whose sources a language model checked instead of a person
    names the model and says so (``SourceEvidence.reviewed_by_model``; the owner, 2026-11-18)."""
    from adroit.core.pricing import model_name
    models = sorted({s.reviewed_by_model for s in (context.sources if context else []) if s.id in ids
                     and s.reviewed_by_model})
    if review == "verified" and models:
        return f"verified: checked by {', '.join(model_name(m) for m in models)}, not by a person"
    return review


def _review(ids: list[str], context: EvidenceContext) -> str:
    sources = [s for s in context.sources if s.id in ids]
    if not sources:
        return "legacy_unknown"
    if any(s.review == "unreviewed" for s in sources):
        return "unreviewed"
    if any(s.review == "legacy_unknown" for s in sources):
        return "legacy_unknown"
    return "verified" if any(s.review == "verified" for s in sources) else "not_required"


def _calculation(value: float | None, excluded: bool | None, reasons: list[str],
                 review: str, context: EvidenceContext) -> str:
    if value is not None or excluded is not None:
        return "computed"
    text = " ".join(reasons).lower()
    if any(word in text for word in ("not in the tools", "backend unavailable", "not installed")):
        return "unavailable_backend"
    if review == "unreviewed":
        return "not_calculated"
    if context.origin == "legacy_unknown":
        return "legacy_unknown"
    return "unresolved"


def point_observations(row: PointResult, engine: dict[str, JsonValue],
                       context: EvidenceContext) -> list[EvidenceObservation]:
    """Preserve comparisons from a physical point without deciding new eligibility."""
    point = row.point.model_dump(mode="json")
    subject = physical_identity(engine, point)
    omega_ids = [s.id for s in context.sources if s.id == "planck-2018-omega"]
    observations = [EvidenceObservation(
        subject_id=subject, physical_input=point, observable="omega_h2", value=_finite(row.omega_h2),
        units="dimensionless", calculation="computed" if _finite(row.omega_h2) is not None else "unresolved",
        applicability="applicable", review=_review(omega_ids, context), source_ids=omega_ids,
        construction="model thermal-relic solver; prediction, not a source-review decision",
        reasons=[] if row.omega_h2 is not None else ["saved relic calculation unavailable"],
    )]
    for name, excluded in row.excluded.items():
        observations.append(_comparison(row, name, excluded, subject, point, context))
    observations.append(EvidenceObservation(subject_id=subject, physical_input=point,
        observable="direct_detection_prediction", value=_finite(row.dd_sigma_cm2), units="cm^2",
        calculation="computed" if _finite(row.dd_sigma_cm2) is not None else "unresolved",
        applicability="applicable", review="not_required", construction=f"model {row.dd_kind} scattering prediction",
        details={"kind": row.dd_kind, "limit_cm2": row.dd_limit_cm2, "operator_ratio": row.dd_ratio}))
    observations += _certificates(row, subject, point)
    return observations


def _comparison(row: PointResult, name: str, excluded: bool | None, subject: str,
                point: dict[str, JsonValue], context: EvidenceContext) -> EvidenceObservation:
    """One saved comparison with its sources, review and reasons, as the evaluator left it."""
    stat = row.statistical_limits.get(name)
    native = row.native_constraints.get(name)
    from adroit.parameter_space.searches import strongest
    outcome = strongest([o for o in row.search_results if o.name == name]) or native    # the verdict's own (AL3-14)
    reference = stat.source if stat else outcome.source if outcome else ""
    ids = _source_ids(reference, context)
    if stat and stat.source and not ids:
        ids = _source_ids(f"experiment:{stat.source}", context)
    reasons = [p for p in row.pending if name in p or any(sid in p for sid in ids)]
    if outcome and outcome.why:
        reasons.append(outcome.why)
    if excluded is None and not reasons:
        reasons = ["saved evaluator has no eligible comparison; applicability not established"]
    value = _finite(row.ratios.get(name))
    source_rows = [s.metadata for s in context.sources if s.id in ids]
    review = "not_required" if name == "perturbativity" else _review(ids, context)
    return EvidenceObservation(
        subject_id=subject, physical_input=point, observable=name, value=value, units="prediction/limit ratio",
        calculation=_calculation(value, excluded, reasons, review, context),
        applicability=(outcome.coverage.get('applicability','applicable' if excluded is not None else 'unknown') if outcome else
                       'applicable' if excluded is not None else 'unknown'), review=review,
        excluded=excluded, source_ids=ids, reasons=list(dict.fromkeys(reasons)),
        native_confidence_level=stat.confidence_level if stat else outcome.confidence_level if outcome else None,
        required_confidence_level=None if name == "perturbativity" else .95,
        construction=stat.construction if stat else outcome.statistical_construction if outcome else "saved evaluator",
        domain={"mass_gev": row.point.m_chi, "source_assumptions": source_rows,
                "coverage": outcome.coverage if outcome else {}},
        uncertainties={"status": "see saved flags/likelihood certificate; no uncertainty invented",
                       "flags": row.flags},
        details={"comparison": row.values.get(name), "statistical_limit": stat.model_dump(mode="json") if stat else None,
                 "outcome": outcome.model_dump(mode="json") if outcome else None,
                 "flags": row.flags, "ratio_confidence_level": row.ratio_confidence_levels.get(name),
                 "model_contract":row.model_contract},
    )


def _certificates(row: PointResult, subject: str, point: dict[str, JsonValue]) -> list[EvidenceObservation]:
    """The saved vacuum, unitarity, running and chemical certificates, each as its own observation."""
    observations = []
    if row.vacuum_certificate is not None:
        certificate=row.vacuum_certificate
        observations.append(EvidenceObservation(subject_id=subject,physical_input=point,
            observable="scalar_tree_vacuum",calculation="computed" if certificate.complete else "unresolved",
            applicability="applicable",review="not_required",construction=certificate.scope,
            domain={"tested_domain":certificate.domain,"scale_gev":certificate.inputs.scale_gev if certificate.inputs else None},
            reasons=certificate.reasons,details=certificate.model_dump(mode="json")))
    if row.unitarity_certificate is not None:
        certificate=row.unitarity_certificate
        observations.append(EvidenceObservation(subject_id=subject,physical_input=point,
            observable="scalar_high_energy_unitarity",calculation="computed" if certificate.complete else "unresolved",
            applicability="applicable",review="not_required",construction=certificate.scope,
            domain={"tested_domain":certificate.domain,"scale_gev":certificate.inputs.scale_gev if certificate.inputs else None},
            reasons=certificate.reasons,details=certificate.model_dump(mode="json")))
    if row.running_certificate is not None:
        certificate=row.running_certificate
        observations.append(EvidenceObservation(subject_id=subject,physical_input=point,
            observable=certificate.kind,calculation="computed" if certificate.complete else "unresolved",
            applicability="applicable",review="not_required",construction=certificate.scope,
            domain={"upper_scale_gev":certificate.request.upper_scale_gev if certificate.request else None},
            reasons=certificate.reasons,details=certificate.model_dump(mode="json")))
    if row.chemical_certificate is not None:
        certificate=row.chemical_certificate
        observations.append(EvidenceObservation(subject_id=subject,physical_input=point,
            observable=certificate.kind,calculation="computed" if certificate.complete else "unresolved",
            applicability="applicable",review="not_required",construction=certificate.scope,
            reasons=certificate.reasons,details=certificate.model_dump(mode="json")))
    return observations


def constraint_observation(verdict: dict[str, JsonValue], subject: str,
                           context: EvidenceContext) -> EvidenceObservation:
    """Expose a Track 2 complementary verdict with the same source/review semantics."""
    ids = [str(verdict["constraint_id"])]
    reason = str(verdict.get("needed_calculation") or verdict.get("note") or "")
    applicability = "applicable" if verdict["applicability"] != "needs_calculation" else "unknown"
    return EvidenceObservation(subject_id=subject, physical_input={}, observable=ids[0],
        source_ids=ids, review=_review(ids, context), applicability=applicability,
        calculation=_calculation(None, verdict.get("excluded"), [reason], _review(ids, context), context),
        excluded=verdict.get("excluded"), native_confidence_level=verdict.get("confidence_level"),
        required_confidence_level=.95, reasons=[reason] if reason else [], details=verdict,
        construction="saved complementary evaluator; see source and assumptions")
