"""Capture run identities without reading credentials or making network calls."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys

from pydantic import BaseModel

from adroit.core.config import PROJECT_ROOT
from adroit.core.evidence import (
    BackendEvidence, EvidenceContext, InputArtifact, SourceEvidence, content_hash,
)
from adroit.core.repro import code_state


def file_hash(path: Path) -> str:
    """Digest one explicitly selected input file."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _sources() -> list[SourceEvidence]:
    from adroit.constraints import database
    from adroit.constraints.review_identity import signature_status

    sources = []
    for record in database.records():
        payload = record.model_dump(mode="json")
        path = PROJECT_ROOT / record.data_file if record.data_file else None
        sources.append(SourceEvidence(
            id=record.id, reference=record.source, version=str(record.version),
            payload_sha256=content_hash(payload), data_path=record.data_file,
            data_sha256=file_hash(path) if path and path.is_file() else "",
            review="verified" if record.usable else "unreviewed",
            reviewed_by=record.verified_by, reviewed_on=record.verified_on,
            metadata=payload, verification_binding=signature_status(record).model_dump(mode="json"),
        ))
    return sources


def capture(user_files: list[Path] | None = None,
            experiments: list[str] | None = None,catalog_references: list[str] | None = None,
            private_limits: list[str] | None=None) -> EvidenceContext:
    """Capture the existing conservative calculation identity before a run.

    Args:
        user_files: explicitly selected anomaly/input files, never a directory.
    """
    from adroit.core.chronology import utc_now
    started=utc_now()
    from adroit.orchestrator.track1_identity import dependencies

    deps = dependencies()
    backends = _backends(deps)
    inputs = [InputArtifact(name=str(p.relative_to(PROJECT_ROOT)), location=str(p),
                            sha256=file_hash(p), role="package_input", redistribution="project")
              for p in _package_inputs()]
    for path in user_files or []:
        if not path.is_file() or path.is_symlink() or path.name.startswith(".env"):
            raise ValueError("user input must be a selected regular non-credential file")
        inputs.append(InputArtifact(name=path.name, location=str(path.resolve()), sha256=file_hash(path),
                                    role="user_input", redistribution="user_selected"))
    sha, dirty = code_state()
    sources = _sources() + _experiment_sources(experiments or [])
    if private_limits:
        limit_sources,limit_inputs=_private_limit_evidence(private_limits)
        sources+=limit_sources
        inputs+=limit_inputs
    inputs+=_module_inputs(experiments or [])
    if catalog_references:
        catalog_sources,catalog_inputs=_catalog_evidence(catalog_references)
        sources+=catalog_sources
        inputs+=catalog_inputs
    identity = content_hash({"dependencies": deps, "sources": [s.model_dump(mode="json") for s in sources],
                             "user_inputs": [i.model_dump(mode="json") for i in inputs if i.role in ("user_input","catalog_input")]})
    return EvidenceContext(origin="captured", identity=identity, python=deps["python"],
        versions=deps["versions"], code_sha256=deps["inputs"]["adroit"]["sha256"],
        git_sha=sha or "", git_dirty=dirty, sources=sources, backends=backends, inputs=inputs,
        command=list(sys.argv),calculation_started_at=started)


def _backends(deps: dict) -> list[BackendEvidence]:
    """Each pinned dependency input with its manifest entry, present or unavailable."""
    from adroit.external.manifest import load_manifest

    inventory = {item.name: item for item in load_manifest().items()}
    backends = []
    for name, row in deps["inputs"].items():
        item = inventory.get(name)
        backends.append(BackendEvidence(
            name=name, sha256=row["sha256"], location=row["path"],
            status="unavailable" if row["sha256"] == "missing" else "present",
            version=item.version if item else "", role=item.role if item else "runtime/input",
            licence=item.licence if item else "", reference=item.reference if item else "",
        ))
    return backends


def _private_limit_evidence(private_limits: list[str]) -> tuple[list[SourceEvidence], list[InputArtifact]]:
    """Each bound private limit as a verified source, with its catalogue files and external assets as inputs."""
    from adroit.constraints.experimental_review import load_bound
    from adroit.library.experimental import ExperimentalCatalog
    sources,inputs=[],[]
    catalog=ExperimentalCatalog()
    for reference in private_limits:
        bound=load_bound(reference,catalog)
        revision=catalog.load(bound.revision)
        sources.append(SourceEvidence(id=reference,reference=reference,payload_sha256=bound.limit_id,
            review='verified',reviewed_by=bound.review.researcher,reviewed_by_model=bound.review.checked_by_model,
            reviewed_on=__import__('datetime').date.fromisoformat(bound.review.reviewed_at[:10]),
            metadata=bound.model_dump(mode='json'),verification_binding={'scope':bound.scientific_sha256,'review_id':bound.review.review_id}))
        files=[catalog.path(f'limits/{bound.limit_id}.json'),catalog.path(f'reviews/{bound.review.review_id}.json'),
               catalog.path(f'validations/{bound.validation.validation_id}.json'),
               catalog.path(f'experiments/{revision.experiment_id}/{revision.revision_id}.json')]
        for path in files:
            inputs.append(InputArtifact(name=path.name,location=str(path),sha256=file_hash(path),
                                                     role='catalog_input',redistribution='user_selected'))
        for asset in revision.sources:
            inputs.append(InputArtifact(name=asset.name,location=str(catalog.asset_path(asset)),
            sha256=asset.sha256,role='external',redistribution='reference_only'))
    return sources,inputs


def _module_inputs(experiments: list[str]) -> list[InputArtifact]:
    """The input files and external assets of each anomaly or private-search module selected."""
    inputs=[]
    for name in experiments:
        if name.startswith(('anomaly:','private-search:')):
            from adroit.experiments.registry import load_module
            module=load_module(name)
            for path in module.input_files():
                inputs.append(InputArtifact(name=path.name,location=str(path),sha256=file_hash(path),
                                            role='catalog_input',redistribution='user_selected'))
            for asset in module.revision.sources:
                inputs.append(InputArtifact(name=asset.name,location=str(module.catalog.asset_path(asset)),
                                            sha256=asset.sha256,role='external',redistribution='reference_only'))
    return inputs


def _catalog_evidence(catalog_references: list[str]) -> tuple[list[SourceEvidence], list[InputArtifact]]:
    """Each personal-catalogue model revision as a source, with its revision file and assets as inputs."""
    from adroit.library.personal import Catalog
    sources,inputs=[],[]
    catalog=Catalog()
    for ref in sorted(set(catalog_references)):
        revision=catalog.load(ref)
        path=catalog.root/'models'/revision.model_id/'revisions'/f'{revision.revision_id}.json'
        inputs.append(InputArtifact(name=path.name,location=str(path),sha256=file_hash(path),role='catalog_input',redistribution='user_selected'))
        for asset in revision.sources:
            source=catalog.asset_path(asset)
            inputs.append(InputArtifact(name=asset.name,location=str(source),sha256=asset.sha256,role='catalog_input',redistribution='user_selected'))
        sources.append(SourceEvidence(id=ref,reference=ref,payload_sha256=revision.revision_id,
            review='not_required',metadata=revision.model_dump(mode='json')))
    return sources,inputs


def _package_inputs() -> list[Path]:
    """Only distributed physics/config data and reproduction/citation manifests."""
    suffixes = {".yaml", ".yml", ".json", ".csv", ".dat", ".txt", ".bib"}
    allowed = {"physics", "constraints", "experiments", "library", "parameter_space", "external"}
    paths = [p for p in (PROJECT_ROOT / "adroit").rglob("*")
             if p.is_file() and not p.is_symlink() and p.suffix in suffixes
             and "__pycache__" not in p.parts and p.relative_to(PROJECT_ROOT / "adroit").parts[0] in allowed]
    paths += [PROJECT_ROOT / name for name in (
        "pyproject.toml", "uv.lock", "docs/dm3/validation_results.json",
        "docs/dependencies.bib", "docs/citations.md") if (PROJECT_ROOT / name).is_file()]
    return sorted(paths)


def _experiment_sources(names: list[str]) -> list[SourceEvidence]:
    from adroit.experiments.registry import load_module
    from adroit.experiments.base import DataUnavailable

    sources = []
    for name in sorted(set(names)):
        signed=None
        try:
            module = load_module(name)
            payload = {"info": module.info.model_dump(mode="json"),
                       "conventions": module.conventions().model_dump(mode="json")}
            if hasattr(module,'evidence'):
                payload['personal_interpretation']=module.evidence()
            review = "unreviewed" if getattr(module, "verified", True) is False else "not_required"
            signed=getattr(module,'review',None)
            if signed:
                review='verified'
        except (KeyError, ValueError, OSError, RuntimeError, DataUnavailable) as error:
            payload, review = {"unavailable": str(error)}, "legacy_unknown"
        sources.append(SourceEvidence(id=f"experiment:{name}", reference=name,
                                      reviewed_by=signed.researcher if signed else '',
                                      reviewed_by_model=signed.checked_by_model if signed else '',
                                      reviewed_on=__import__('datetime').date.fromisoformat(signed.reviewed_at[:10]) if signed else None,
                                      payload_sha256=content_hash(payload), review=review, metadata=payload))
    return sources


def finish(context: EvidenceContext, read: dict[str, str] | None = None,
           consumed: dict[str, str] | None = None) -> EvidenceContext:
    """Mark changed calculation dependencies; never relabel a result with fresh sources.

    ``read``: the version of each curated record the calculation read, as its result keeps it
    (``evidence.results.records_read``). A start and an end capture alike say nothing of what was read between them
    (the auditor's CV recheck, CW-02, 2026-10-30: a telescope limit computed from a curve read as B, between A at both ends,
    kept the captured context). A record read in two versions (""), or in another version than ``context`` captured,
    leaves the context changed, naming it. The captured version is the context's own (``_read_otherwise``), never a
    later read of the library (the auditor's CW recheck, CX-01, 2026-10-31).

    ``consumed``: the same of each selected input file (location: the SHA-256 of the bytes consumed), as the result
    keeps it (``evidence.results.inputs_read``): one consumed in two versions, in another than the context captured, or
    not captured at all, leaves the context changed, naming it (the auditor's CX recheck, CY-01, 2026-11-01: a saved Track 1
    point reused as B, between A at both captures, had left a signal study "captured", naming A)."""
    if context.origin != "captured":
        return context
    files = [Path(i.location) for i in context.inputs if i.role == "user_input"]
    names = [s.id.removeprefix("experiment:") for s in context.sources if s.id.startswith("experiment:")]
    refs=[s.id for s in context.sources if s.id.startswith('catalog:')]
    personal=[s.id for s in context.sources if s.id.startswith('private-limit:')]
    current = capture(files,names,refs,personal) if personal else capture(files, names,refs) if refs else capture(files,names)
    profiles=[s.id for s in context.sources if s.id.startswith('profile:')]
    for profile in profiles:
        current=_profile_context(current,profile)
    from adroit.core.chronology import utc_now
    dates={'calculation_completed_at':context.calculation_completed_at or utc_now()} if context.calculation_started_at else {}
    otherwise = _read_otherwise(context, read or {})
    elsewhere = _consumed_otherwise(context, consumed or {})
    if current.identity == context.identity and not otherwise and not elsewhere:
        return context.model_copy(update=dates)
    notes = [*context.notes] + (["calculation dependencies changed during execution; provenance cannot certify reuse"]
                                if current.identity != context.identity else [])
    notes += [f"the calculation read {rid} in two versions, or in another than the run's sources name; provenance "
              "cannot certify the numbers resting on it" for rid in otherwise]
    notes += [f"the calculation consumed {where} in two versions, or in another than the run captured as its input; "
              "provenance cannot certify the numbers resting on it" for where in elsewhere]
    return context.model_copy(update={**dates, "origin": "changed_during_run", "notes": notes})


def _consumed_otherwise(context: EvidenceContext, consumed: dict[str, str]) -> list[str]:
    """The input files of ``consumed`` (location: the digest of the bytes consumed) consumed in two versions (""), or
    in another version than ``context`` captured as a selected input, or not captured at all."""
    held = {i.location: i.sha256 for i in context.inputs if i.role == "user_input"}
    return [where for where, digest in sorted(consumed.items()) if not digest or held.get(where) != digest]


def _read_otherwise(context: EvidenceContext, read: dict[str, str]) -> list[str]:
    """The records of ``read`` (id: the version read) read in two versions (""), or in another version than
    ``context`` captured: each record's version from what the context holds of it, its metadata and the data its
    ``data_sha256`` names (``review_identity.captured_version``). The auditor's CW recheck, CX-01 (2026-10-31): compared with
    the library read once more after the end capture, a record put back to B in between had made B's numbers read as
    the captured A's."""
    from adroit.constraints.review_identity import captured_version
    held = {s.id: s for s in context.sources if not s.id.startswith(("experiment:", "catalog:", "private-limit:",
                                                                       "profile:"))}
    return [rid for rid, version in sorted(read.items())
            if not version or rid not in held or captured_version(held[rid].metadata, held[rid].data_sha256) != version]


def capture_request(request: BaseModel, experiments: bool = True) -> EvidenceContext:
    """Capture only explicitly requested user files and the relevant experiment metadata (none when
    ``experiments`` is False: a request that consults no experiment, such as building models from an idea)."""
    from adroit.experiments.registry import module_names

    names = [getattr(request, "experiment", "") or getattr(request, "signal_experiment", "")]
    names += getattr(request, "null_modules", [])
    profile_reference=getattr(request,'experimental_profile','')
    profile=None
    if profile_reference:
        from adroit.library.experimental_profiles import load
        profile=load(profile_reference)
        names += [profile.signal,*profile.null_modules]
    if not names[0] and experiments:
        names += getattr(request, "modules", []) or module_names()
    if getattr(request, "null_experiment", ""):
        names.append(request.null_experiment)
    files = [Path(n.removeprefix("record:")) for n in names if n.startswith("record:")]
    for supplied in getattr(request,'track1_results',[]):
        path=Path(supplied)
        files.append(path)
        sidecar=path.with_name(path.stem+'.evidence.json')
        if sidecar.is_file():
            files.append(sidecar)
    references=[getattr(request,'catalog_reference','')]
    references += [getattr(m,'catalog_reference','') for m in getattr(request,'user_models',[])]
    refs=[r for r in references if r]
    personal=getattr(request,'private_limits',[])
    if profile:
        personal=profile.limits
    context = capture(files,[n for n in names if n],refs,personal) if personal else capture(files,[n for n in names if n],refs) if refs else capture(files,[n for n in names if n])
    if profile:
        context=_profile_context(context,profile_reference)
    if getattr(request,'discovery',''):
        context=_discovery_context(context,request.discovery)
    return context.model_copy(update={"request_sha256": content_hash(request.model_dump(mode="json"))})

def _discovery_context(context,reference):
    """The pinned discovery assessment as an input of the run (its file, and its content as a source)."""
    from adroit.orchestrator.constraint_discovery import Discovery
    service=Discovery()
    coverage=service.load_coverage(reference)
    path=service.folder(coverage.session_id)/'assessments'/f'{coverage.assessment_sha256}.json'
    source=SourceEvidence(id=reference,reference=reference,payload_sha256=coverage.assessment_sha256,review='not_required',
        metadata=coverage.model_dump(mode='json'))
    artifact=InputArtifact(name=path.name,location=str(path),sha256=file_hash(path),role='catalog_input',redistribution='user_selected')
    return context.model_copy(update={'identity':content_hash({'base':context.identity,'discovery':coverage.model_dump(mode='json')}),
                                      'sources':[*context.sources,source],'inputs':[*context.inputs,artifact]})

def _profile_context(context,reference):
    from adroit.library.experimental_profiles import load
    from adroit.library.experimental import ExperimentalCatalog
    catalog=ExperimentalCatalog()
    profile=load(reference,catalog)
    path=catalog.path(f'profiles/{profile.profile_id}.json')
    source=SourceEvidence(id=reference,reference=reference,payload_sha256=profile.profile_id,review='not_required',
        metadata=profile.model_dump(mode='json'))
    artifact=InputArtifact(name=path.name,location=str(path),sha256=file_hash(path),role='catalog_input',redistribution='user_selected')
    return context.model_copy(update={'identity':content_hash({'base':context.identity,'profile':profile.model_dump(mode='json')}),
                                      'sources':[*context.sources,source],'inputs':[*context.inputs,artifact]})
