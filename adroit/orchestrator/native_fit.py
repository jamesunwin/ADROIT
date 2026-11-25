"""Free, source-bound, resumable native multiparameter fits in the existing run system."""
from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator

from adroit.core.checkpoint import Checkpoint, CheckpointMismatch, run_lock, atomic_json
from adroit.core.model_spec import ModelSpec, PhysicalFitRange
from adroit.core.state import StrictModel
from adroit.parameter_space.classify import classify
from adroit.parameter_space.native_joint import JointSettings, JointResult, SIGNAL
from adroit.parameter_space.physical_fit import FitSettings


class NativeFitRequest(StrictModel):
    """A native multiparameter fit: the model, the signal experiment, the masses and the joint-fit settings, which
    must name a physical domain."""
    spec: ModelSpec
    signal_experiment: str = SIGNAL
    masses_gev: list[float] = Field(min_length=1)
    settings: JointSettings

    @property
    def null_experiment(self):
        """The null experiment of the joint-fit settings."""
        return self.settings.null_experiment

    @model_validator(mode="after")
    def declared_domain(self):
        """Refuse settings without a named physical domain."""
        if self.settings.domain is None:
            raise ValueError("native-fit requires a named physical domain")
        return self


def run(request: NativeFitRequest, folder: Path, *, resume: bool = False, claim=None) -> JointResult:
    """Run (or resume) a native joint fit in a folder, writing the request, the result with its evidence envelope and
    the report."""
    return run_reported(request, folder, resume=resume, claim=claim)[0]


def run_reported(request: NativeFitRequest, folder: Path, *, resume: bool = False,
                 claim=None) -> tuple[JointResult, str]:
    """``run``, with the report as it wrote it, of the result it holds: what the command prints, never the file read
    again (the auditor's DA recheck, DB-02, 2026-11-03: another result's report, published there since, had been printed).
    The folder held (``durable.publishing``; ``claim``, its writer's own) from before its first file, its checkpoint
    and its request, to its record: a fit refused writes nothing (the auditor's DE recheck, DF-01, 2026-11-05: refused at its
    publication, it had written its request and working state first)."""
    from adroit.core.durable import publishing
    from adroit.evidence.runtime import capture_request, finish
    from adroit.evidence.build import publish
    from adroit.orchestrator.track1_identity import dependencies
    from adroit.parameter_space.native_joint import published_halo_only, run as joint_run
    from adroit.orchestrator.single_idea import _native_report
    published_halo_only()                  # no native fit at a fixed benchmark halo, before anything is written
    folder.mkdir(parents=True,exist_ok=True)
    with publishing(folder, claim) as owned, run_lock(folder):
        context = capture_request(request)
        identity = dependencies()
        checkpoint = Checkpoint(folder,request.model_dump(mode="json"),identity,resume,
                                {"calculation_started_at": context.calculation_started_at})
        result = checkpoint.load("finished","native",JointResult)
        if result is None:
            cls, point, _ = classify(request.spec)
            bounds = request.spec.physical_fit or PhysicalFitRange.perturbative_branch(point.g_chi)
            result = joint_run(cls,point,request.masses_gev,bounds,request.settings,FitSettings(),
                               request.spec.dark_matter.spin,request.signal_experiment,checkpoint)
            if dependencies() != identity:
                checkpoint.invalidate()
                raise CheckpointMismatch("native fit dependencies changed during execution")
            if result.complete:
                from adroit.core.chronology import utc_now
                checkpoint.save("finished","native",result,
                                dates=(checkpoint.started(context.calculation_started_at),utc_now()))
        # the dates of the result held, as its checkpoint holds them in this run: read back or saved with it, else, an
        # incomplete result this run computed, from its checkpoint's first run's start (the auditor's DB/VI recheck, DC-03)
        from adroit.core.checkpoint import Chronology
        held = checkpoint.chronology("finished","native",result) \
            or Chronology(checkpoint.started(context.calculation_started_at),"",False)
        atomic_json(folder/'request.json',request.model_dump(mode="json"))
        import json
        from adroit.core.chronology import analysis_report
        from adroit.orchestrator.runs import restored_dates
        # the result, its evidence and its report, bound to it, of one serialization (the auditor's CX recheck, CY-03; its
        # CY recheck, CZ-02: the report had been bound to the file read again)
        content=json.dumps(result.model_dump(mode="json"),ensure_ascii=False,allow_nan=True).encode()
        if resume:      # dated as the calculation it restores or completes, never another publication (VI-05, DC-03)
            context=restored_dates(context,folder,result,held)
        from adroit.orchestrator import studies
        from adroit.evidence.build import incomplete
        import hashlib
        # its parts and its record under its hold of the folder (the auditor's DD recheck, DE-02; its DE recheck, DF-01),
        # marked from its first part to its record, its last (the auditor's merge-round audit, HE-02, 2026-11-12)
        with incomplete(folder/'result.json', hashlib.sha256(content).hexdigest()):
            envelope,text=publish(folder/'result.json',content,result,
                                  lambda envelope: analysis_report('\n'.join(_native_report(result))+'\n',context=envelope.context),
                                  workflow='native_joint',context=finish(context),original_inputs=request.model_dump(mode="json"),
                                  claim=owned,marked=True)
            checkpoint.update("native_fit",status="completed" if result.complete else "unresolved",
                              detail=result.domain_fit.reason if result.domain_fit else str(result.omitted))
            studies.record(folder,'native_joint',f'Native fit: {request.spec.name}',
                           calculation_started_at=envelope.context.calculation_started_at or '',
                           calculation_completed_at=envelope.context.calculation_completed_at or '',
                           result_sha256=envelope.result_sha256,claim=owned)      # of the bytes published (VI-01)
        return result, text
