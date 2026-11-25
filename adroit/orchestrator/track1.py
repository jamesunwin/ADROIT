"""Track 1 (DM13): is a model consistent, and what do the data allow? The full report.

1. **Validity** (DM12's audit): Lorentz and gauge invariance, spins,
   hermiticity, dimension.
2. **The class**: whether the scan can compute the model's whole picture
   (``classify``), and its parameter point.
3. **The scan** over two parameters, every computed constraint at each point.
4. **The verdict** on the thermal-relic contour (``verdict``).
5. **The plots**: the plane, and direct detection along the contour.
6. **The literature**:
   - the curated sources and each constraint's record-verification policy;
   - prior work on the model from an arXiv search, with titles as arXiv
     returns them (free; skipped without a network).

A model the scan cannot compute keeps its validity verdict, and the report
says what is missing.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import time
import hashlib
from typing import Literal

from pydantic import Field, field_validator

from adroit.constraints.viability import Entry as ViabilityEntry
from adroit.core.constraint_discovery import DiscoveryCoverage
from adroit.core.halo_choice import FixedHalo, Resolution
from adroit.core.model_spec import ModelSpec
from adroit.core.state import StrictModel
from adroit.core.checkpoint import Checkpoint, CheckpointMismatch, Manifest, run_lock
from adroit.parameter_space.coverage import CoverageSettings, CoverageDiagnostic, diagnose
from adroit.model_building.audit import AuditReport, audit
from adroit.parameter_space import halo_region, plots, relations
from adroit.parameter_space.classes import Point, ScalarClass, Spin1Class
from adroit.parameter_space.classify import Unsupported, classify
from adroit.parameter_space.scan import Axis, ModelClass, ScanRequest, ScanResult, run as scan, worker_count
from adroit.parameter_space.likelihood import LikelihoodSettings
from adroit.parameter_space.verdict import Verdict, verdict_pair
from adroit.core.chronology import dated_report

QUERY = {"higgs_portal_scalar": "scalar singlet", "higgs_portal_fermion": "Higgs portal",
         "higgs_portal_vector": "vector dark matter", "singlet_mixing": "singlet fermion",
         "dark_photon": "dark photon", "inelastic_dark_photon": "inelastic dark matter", "z_portal": "Z portal",
         "charged_zprime": "Z'", "t_channel": "t-channel"}

CURATED = [
    ("Planck 2018", "arXiv:1807.06209", "Ωh² = 0.1200 ± 0.0012: Table 2, TT,TE,EE+lowE+lensing"),
    ("LHC Dark Matter Working Group", "arXiv:1603.04156, 1703.05703", "the spin-1 simplified models and their widths"),
    ("CMS summary of mediator searches", "arXiv:2405.13778", "collider exclusions of the Working Group's benchmarks"),
    ("Fermi-LAT, 15 dwarf galaxies", "arXiv:1503.02641", "⟨σv⟩ limits by final state"),
    ("IceCube, the Sun", "arXiv:1612.05949", "limits on capture and annihilation in the Sun"),
    ("The direct-detection modules", "docs/dm3_experiments.md", "CRESST-III, CDMSlite, PICO-60, DEAP-3600, LZ, "
                                                                "XENONnT, PandaX-4T, each within its validated range"),
]


class Track1Request(StrictModel):
    """A Track 1 run: the model, its class and point (or read from the model), the scan's axes or portal plane, and
    the settings of the constraints and the likelihood."""
    spec: ModelSpec
    model_class: ModelClass | None = None                  # None: read from the model (``classify``)
    fixed: Point | None = None
    approved_model_sha256: str = Field(default="",pattern=r"^(?:[a-f0-9]{64})?$")
    reviewed_scan_sha256: str = Field(default="",pattern=r"^(?:[a-f0-9]{64})?$")
    catalog_reference: str = ''
    private_limits: list[str] = Field(default_factory=list)
    experimental_profile: str = ''
    x: Axis | None = None                                  # None: the portal's plane, else m_med 10 GeV–10 TeV
    y: Axis | None = None                                  # None: the portal's plane, else m_χ 1 GeV–2 TeV
    portal: str = ""                                       # an entry of the portal library (``library``)
    mediator_ratio: float | None = None                    # m_med = ratio × m_χ at every point
    literature: bool = False                               # arXiv's prior work: a network request, only if asked
    workers: int = Field(default=2, ge=1, le=2)
    unverified_records: bool = False
    likelihood: LikelihoodSettings | None = None           # also the combined-likelihood verdict (``likelihood``)
    # every direct-detection limit by the module's own procedure, no precomputed table (R10, ``limit_tables``); the
    # combined likelihood always uses exact limits. Unset requests keep their earlier identity.
    exact_limits: bool = Field(default=False, exclude_if=lambda v: not v)
    coverage: CoverageSettings | None = None               # opt-in bounded relic resolution check
    # the propagation model for charged cosmic-ray bounds: conservative, central or aggressive (alias relaxed); None:
    # the setting ADROIT_CR_PROPAGATION, resolved when the run starts. Unset requests keep their earlier identity.
    propagation: str | None = Field(default=None, exclude_if=lambda v: v is None)
    # the halo region every point is evaluated over (``halo_region``), "published" (each experiment's published
    # halo, the reproduction mode), or a fixed common benchmark (``halo_choice.FixedHalo``: every point at that one
    # halo); None: the setting ADROIT_HALO_REGION (the preset unless it says published), resolved when the run starts.
    # Unset requests keep their earlier identity.
    halo: halo_region.HaloPreset | Literal["published"] | FixedHalo | None = Field(default=None,
                                                                                 exclude_if=lambda v: v is None)
    # a frozen constraint-discovery assessment (discovery:<session>@<hash>): its unresolved relevant constraints keep
    # allowed points pending (``orchestrator.constraint_discovery.qualify``). Unset requests keep their identity.
    discovery: str = Field(default="", exclude_if=lambda v: not v)

    @field_validator("propagation")
    @classmethod
    def _known_propagation(cls, value: str | None) -> str | None:
        from adroit.constraints.propagation import normalise
        return None if value is None else normalise(value)


class Paper(StrictModel):
    """Prior work on the model from the arXiv search: identifier, title as arXiv gives it, and year."""
    arxiv_id: str
    title: str
    year: int | None = None


class Track1Result(StrictModel):
    """Track 1's report: the audit, the class and point, the scan and its verdicts, the plots, the literature and the
    viability checklist."""
    request: Track1Request
    audit: AuditReport
    likelihood_verdict: Verdict | None = None
    class_name: str = ""
    fixed: Point | None = None
    unsupported: str = ""
    notes: list[str] = Field(default_factory=list)
    scan: ScanResult | None = None
    verdict: Verdict | None = None
    plots: list[str] = Field(default_factory=list)
    papers: list[Paper] = Field(default_factory=list)
    literature_note: str = ""
    created: str = Field(default_factory=lambda: str(date.today()))
    coverage: CoverageDiagnostic | None = None
    viability: list[ViabilityEntry] = Field(default_factory=list)   # the 28-item checklist (R8; empty in older results)
    # the pinned discovery assessment, embedded so that the result reads without the personal library
    discovery_coverage: DiscoveryCoverage | None = Field(default=None, exclude_if=lambda v: v is None)
    # the halo as the run resolved it (``halo_choice.resolve``), with the halo data files' identities as read; absent
    # in older results (read from their request when shown)
    halo_resolution: Resolution | None = Field(default=None, exclude_if=lambda v: v is None)


class _Artifacts(StrictModel):
    """A finished result's figures: each one's SHA-256."""
    hashes: dict[str, str]
    # the digests are of the bytes as drawn (``bindings.drawn_digest``), never of the files as read after (the auditor's CZ
    # recheck, DA-01, 2026-11-02); False in older checkpoints, whose digests were read back from the files
    drawn: bool = Field(default=False, exclude_if=lambda v: not v)


def _as_drawn(folder: Path, names: list[str]) -> _Artifacts:
    """The figures ``names`` in ``folder`` as this process drew them (``bindings.drawn_digest``), not as read back:
    a figure replaced after it was drawn keeps the digest of the draw, and every reader withholds the replacement
    (the auditor's CZ recheck, DA-01, 2026-11-02: the checkpoint had read the replacement back, and a resumed run had then
    bound it as the figure drawn). A figure this process did not draw is left out, and a resume draws it again."""
    from adroit.evidence.bindings import drawn_digest
    return _Artifacts(hashes={name: digest for name in names if (digest := drawn_digest(folder / name))}, drawn=True)


def _kept_figures(cached: Track1Result, folder: Path, checkpoint: Checkpoint) -> None:
    """A finished result's figures on resume: kept where the files still have the bytes its checkpoint records as
    drawn (those digests held for the report's binding, ``bindings.drawn``), and drawn again from the result where they
    do not, or where an older checkpoint recorded them as read back rather than as drawn (DA-01). Never the files as
    they are now taken as the draw: a replacement is drawn over, or withheld by every reader."""
    from adroit.evidence.bindings import drawn
    artifacts = checkpoint.load("finished", "artifacts", _Artifacts)
    held = artifacts.hashes if artifacts is not None and artifacts.drawn else None
    current = {name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
               for name in cached.plots if (folder / name).exists()}
    if cached.scan is not None and held != current:
        _plots(cached.scan, cached.verdict, folder, cached.request.spec.name)
        checkpoint.save("finished", "artifacts", _as_drawn(folder, cached.plots))
    elif held is not None:
        for name, digest in held.items():
            drawn(folder / name, digest)


def _query(spec: ModelSpec, cls) -> str:
    if isinstance(cls, Spin1Class):
        what = "vector mediator" if cls.kind.value == "vector" else "axial-vector mediator"
    elif isinstance(cls, ScalarClass):
        what = "pseudoscalar mediator" if cls.dm_pseudoscalar else "scalar mediator"
    else:
        what = QUERY.get(getattr(cls, "family", ""), spec.name.replace("_", " "))
    return f'abs:"dark matter" AND abs:"{what}" AND abs:"relic"'


def literature(spec: ModelSpec, cls, fetch=None, n: int = 8) -> tuple[list[Paper], str]:
    """Prior work on the model from arXiv (titles as arXiv returns them), or why none was found."""
    from adroit.retrieval.literature import fetch_arxiv_abstracts
    query = _query(spec, cls)
    try:
        found = (fetch or fetch_arxiv_abstracts)(query, n)
    except Exception as error:  # noqa: BLE001 - no network or a refused request: the report says so
        return [], f"the arXiv search ({query}) could not be made: {type(error).__name__}"
    return [Paper(arxiv_id=a.arxiv_id, title=a.title, year=a.year) for a in found], f"arXiv search: {query}"


def for_portal(entry_id: str, **changes) -> Track1Request:
    """A Track 1 request for an entry of the portal library, at its benchmark and in its plane."""
    from adroit.parameter_space import library
    e = library.entry(entry_id)
    return Track1Request(spec=e.spec(), model_class=e.model_class, fixed=e.point, x=e.x, y=e.y, portal=e.id,
                         mediator_ratio=e.mediator_ratio).model_copy(update=changes)


MISMATCH = ("the saved model class differs from the one the installed code builds from the typed model; "
            "a saved class is never run as given")


def rebuilt_class(request: Track1Request) -> ModelClass:
    """The class the installed code builds for a request: the library entry's for a portal run, else the
    typed model's (``classify``). Raises ValueError when neither can be built."""
    if request.portal:
        from adroit.parameter_space import library
        try:
            return library.entry(request.portal).model_class
        except KeyError:
            raise ValueError(f"no portal {request.portal!r} in the installed library") from None
    try:
        return classify(request.spec)[0]
    except Unsupported as error:
        raise ValueError(f"the installed code cannot map the typed model: {error}") from None


def checked_class(request: Track1Request, stored: ModelClass | None) -> ModelClass:
    """The rebuilt class; refuses a stored class (read from a file) that differs from it."""
    rebuilt = rebuilt_class(request)
    if stored is not None and stored != rebuilt:
        raise ValueError(MISMATCH)
    return rebuilt


def saved_request(folder: Path) -> Track1Request:
    """Read the original request for an explicit resume; execution still verifies its identity. A saved
    model class must equal the one rebuilt from the typed model."""
    manifest = Manifest.model_validate_json((folder / ".track1-checkpoint/manifest.json").read_text())
    request = Track1Request.model_validate(manifest.inputs)
    checked_class(request, request.model_class)
    return request


def run(request: Track1Request, folder: Path, fetch=None, *, resume: bool = False,
        context: dict | None = None, held: dict | None = None, claim=None) -> Track1Result:
    """The whole of Track 1 for one model; plots are written into ``folder``. ``context``: the run's own, kept in its
    checkpoint's manifest; with ``calculation_started_at``, the finished result is saved with when its calculation
    started (its checkpoint's first run's start, else this one's) and completed (the auditor's version-identity audit, VI-05,
    2026-11-03). ``held``: given, it receives, as ``chronology``, the dates of the result returned as this run holds
    them (``Checkpoint.chronology``: read back with it, or saved with it), which its publication is dated with (the auditor's
    DB/VI recheck, DC-03, 2026-11-03). ``claim``: its writer's hold of the folder (``durable.publishing``), taken here
    where none is given, before anything is written into it: a run is never drawn, nor checkpointed, into a folder
    another writer holds (the auditor's DE recheck, DF-01, 2026-11-05)."""
    from adroit.orchestrator.track1_identity import dependencies
    from adroit.orchestrator.model_approval import verify_request
    verify_request(request)
    if request.experimental_profile:          # the final selection first, then its checks, whatever the route (S18-02)
        from adroit.library.experimental_profiles import load
        profile=load(request.experimental_profile)
        if request.private_limits and request.private_limits!=profile.limits:
            raise ValueError('explicit limit selection differs from the pinned profile')
        request=request.model_copy(update={'private_limits':profile.limits})
    if request.private_limits:
        from adroit.constraints.experimental_review import load_bound
        from adroit.parameter_space.private_limits import check_applicability
        check_applicability(request.spec,[load_bound(ref) for ref in request.private_limits])
    if request.catalog_reference:
        from adroit.library.personal import Catalog
        Catalog().verify_calculation(request.catalog_reference,request.spec,'track1')
    if request.discovery:
        from adroit.orchestrator.constraint_discovery import check_model, load_coverage
        check_model(load_coverage(request.discovery), request.spec)
    from adroit.constraints import propagation
    from adroit.core import halo_choice
    request = halo_region.resolved(propagation.resolved(request)).model_copy(deep=True)   # its own (HA-05)
    resolution = halo_choice.resolve(halo_region.checked(request.halo))     # resolved once, before anything is written
    folder.mkdir(parents=True, exist_ok=True)
    from adroit.core.durable import publishing
    with publishing(folder, claim), run_lock(folder), propagation.using(request.propagation), \
            halo_region.using(halo_region.of(request.halo)), halo_choice.holding(resolution.data):
        print("Track 1: checking calculation inputs and software identity", flush=True)
        identity = dependencies()
        checkpoint = Checkpoint(folder, request.model_dump(mode="json"), identity, resume, context)
        try:
            cached = checkpoint.load("finished", "result", Track1Result)
            if cached is not None:
                _kept_figures(cached, folder, checkpoint)
                checkpoint.update("completed", status="completed", detail="complete saved result verified")
                if held is not None:
                    held["chronology"] = checkpoint.chronology("finished", "result", cached)
                return cached
            from adroit.parameter_space import limits
            with limits.exact_environment(request.exact_limits or request.likelihood is not None):
                result = _run(request, folder, fetch, checkpoint)
            from adroit.orchestrator import checklist
            result = result.model_copy(update={"viability": checklist.for_track1(result),
                                               "halo_resolution": resolution})
            verify_request(request)
            if dependencies() != identity:
                checkpoint.invalidate()
                raise CheckpointMismatch("Software or calculation data changed during the run")
            halo_choice.intact(resolution, request.halo)          # the halo it ran with is the one resolved (HA-05)
            halo_choice.unchanged(resolution)
            from adroit.core.chronology import utc_now
            started = checkpoint.started((context or {}).get("calculation_started_at", ""))
            checkpoint.save("finished", "result", result, dates=(started, utc_now()) if started else None)
            checkpoint.save("finished", "artifacts", _as_drawn(folder, result.plots))
            if held is not None:
                held["chronology"] = checkpoint.chronology("finished", "result", result)
            checkpoint.update("completed", status="completed", detail="scientific result saved")
            return result
        except BaseException as error:
            checkpoint.update(checkpoint.progress.phase, checkpoint.progress.completed, checkpoint.progress.total,
                              str(error), status="failed")
            raise


STAGE_NAMES = {"scan": "scan the parameter plane (points)", "coverage": "search for missed relic solutions",
               "refinement": "refine the thermal brackets", "cuts-points": "check the thermal points against every "
               "constraint", "likelihood-points": "check them in the combined likelihood", "plots": "draw the plots",
               "literature": "search the literature"}


def stage_plan(request: "Track1Request") -> list[str]:
    """The stages a Track 1 run goes through, in order, from its request: the scan, the coverage search if asked for,
    the thermal refinement, the constraints at each thermal point (and in the combined likelihood if asked for), the
    plots, and the literature if asked for (``STAGE_NAMES`` says each in words)."""
    return ["scan", *(["coverage"] if request.coverage else []), "refinement", "cuts-points",
            *(["likelihood-points"] if request.likelihood is not None else []), "plots",
            *(["literature"] if request.literature else [])]


def _stage(checkpoint: Checkpoint, phase: str, model, call):
    cached = checkpoint.load("stages", phase, model)
    if cached is not None:
        return cached
    checkpoint.update(phase, detail=f"{phase} in progress")
    started = time.perf_counter()
    value = call()
    checkpoint.save("stages", phase, value)
    checkpoint.progress.durations_s[phase] = time.perf_counter() - started
    return value


def _plots(scan_result: ScanResult, v: Verdict, folder: Path, title: str) -> list[str]:
    paths = [str(plots.plane(scan_result, v, folder / "parameter_plane.png", title=title))]
    dd = plots.direct_detection(scan_result, v, folder / "direct_detection.png")
    if dd:
        paths.append(str(dd))
    return [Path(path).name for path in paths]


def _fallback(spec, cls):
    """The generic route for a typed model class with a domain (the owner, 2026-10-15): the same model from its own
    Lagrangian, with m_χ the dark matter's mass and m_med the single mediator's; None where that does not apply."""
    from adroit.parameter_space.portals.generic import GenericModel
    if isinstance(cls, GenericModel) or not hasattr(cls, "domain") or spec is None:
        return None
    try:
        engine = GenericModel.for_spec(spec)
        if not engine.tied:
            return None
        engine.at(engine.point())
    except (ValueError, KeyError):
        return None
    return engine


def _run(request: Track1Request, folder: Path, fetch, checkpoint: Checkpoint) -> Track1Result:
    result = Track1Result(request=request, audit=audit(request.spec))
    cls, fixed, notes = request.model_class, request.fixed, []
    if cls is None or fixed is None:
        try:
            found, point, notes = classify(request.spec)
        except Unsupported as error:
            return result.model_copy(update={"unsupported": str(error)})
        cls, fixed = cls or found, fixed or point
    from adroit.parameter_space.scan_setup import model_relations,preview,setup_identity
    try:
        ties=model_relations(None if request.portal else request.spec,request.portal,request.x,request.y)
    except Unsupported as error:
        return result.model_copy(update={"unsupported": str(error)})
    setup=preview(cls,fixed,request.x,request.y,request.mediator_ratio,notes=notes,coupling_relations=ties)
    if request.reviewed_scan_sha256 and setup_identity(request.spec,cls,fixed,setup)!=request.reviewed_scan_sha256:
        raise ValueError("numerical mapping or scan setup changed since review; review it before running")
    x,y=Axis.model_validate(setup.x),Axis.model_validate(setup.y)
    scan_request = ScanRequest(model_class=cls, fixed=fixed, x=x, y=y, mediator_ratio=request.mediator_ratio,
                               fallback_class=_fallback(request.spec, cls),
                               relic_fraction=request.spec.relic_fraction, workers=worker_count(request.workers),
                               unverified_records=request.unverified_records, propagation=request.propagation,
                               halo=halo_region.of(request.halo),
                               coupling_relations=relations.orient(ties,(x.parameter,y.parameter)))
    if request.private_limits:
        from adroit.constraints.experimental_review import load_bound
        scan_request.private_limits=[load_bound(ref) for ref in request.private_limits]
    if request.experimental_profile:
        from adroit.library.experimental_profiles import load
        from adroit.constraints.experimental_search_review import load_bound as load_search
        profile=load(request.experimental_profile)
        scan_request.private_searches=[load_search(n) for n in profile.null_modules if n.startswith('private-search:')]
    if scan_request.halo is not None:
        halo_region.check_inputs(scan_request)
    if request.discovery:                      # a pointwise input to the verdict, before any aggregate (S18-03)
        from adroit.orchestrator.constraint_discovery import load_coverage, pending_spans
        scan_request.discovery=pending_spans(load_coverage(request.discovery),request.private_limits)
    checkpoint.declare(stage_plan(request))                # the live page's checklist (the owner, 2026-11-23)
    scan_result = _stage(checkpoint, "scan", ScanResult, lambda: scan(scan_request, checkpoint))
    coverage = _stage(checkpoint, "coverage", CoverageDiagnostic,
                      lambda: diagnose(scan_request, request.coverage, checkpoint)) if request.coverage else None
    checkpoint.update("verdict", detail="refining and checking thermal solutions")
    v, combined = verdict_pair(scan_result, likelihood=request.likelihood, coverage=coverage, checkpoint=checkpoint)
    checkpoint.update("plots", detail="writing parameter-space plots")
    paths = _plots(scan_result, v, folder, request.spec.name)
    checkpoint.update("literature", detail="collecting source references")
    papers, note = literature(request.spec, cls, fetch) if request.literature else ([], "literature search not asked for")
    discovered = None
    if request.discovery:
        from adroit.orchestrator.constraint_discovery import load_coverage, qualify
        discovered = load_coverage(request.discovery)
        v, combined = (qualify(view, discovered, request.private_limits) for view in (v, combined))
    return result.model_copy(update={"discovery_coverage": discovered, "class_name": cls.name, "fixed": fixed, "notes": notes + scan_result.notes,
                                     "scan": scan_result, "verdict": v, "plots": paths,
                                     "papers": papers, "literature_note": note, "likelihood_verdict": combined,
                                     "coverage": coverage})


LEVELS = {"pending": "THERMAL CALCULATION PENDING", "viable": "VIABLE", "viable_pending": "VIABLE, PENDING A CALCULATION", "excluded": "EXCLUDED",
          "overabundant": "NO RESOLVED THERMAL ROOT (samples overabundant)",
          "underabundant": "NO RESOLVED THERMAL ROOT (samples underabundant)"}


FOUND_EXCLUDED = "EVERY THERMAL SOLUTION FOUND IS EXCLUDED (COVERAGE INCOMPLETE)"


def level_label(v: Verdict) -> str:
    """A verdict's level in the report's words; a pending one whose every thermal solution found is excluded says so
    (``verdict.all_found_excluded``: the owner, 2026-11-23)."""
    from adroit.parameter_space.verdict import all_found_excluded
    return FOUND_EXCLUDED if all_found_excluded(v.crossings, v.level) else LEVELS[v.level]


def _contour_table(v: Verdict, x: str, y: str) -> list[str]:
    combined = v.mode == "likelihood"
    lines = [f"| {x} | {y} | kind; Ωh²; relative residual | status |{' r |' if combined else ''} excluded by | still to compute |",
             "|---|---|---|---|" + ("---|" if combined else "") + "---|---|"]
    from adroit.parameter_space.certification import status_words, summary_lines
    for c in sorted(v.crossings, key=lambda c: getattr(c.point, y))[:40]:
        status = f"{status_words(c)} ⚠" if c.flags else status_words(c)
        r = f" {c.r_combined:.2f} |" if combined and c.r_combined is not None else (" — |" if combined else "")
        certificate = f"{c.kind}; {c.omega_h2:.6g}; {c.relative_residual:.3g}" if c.omega_h2 is not None and c.relative_residual is not None else c.kind
        lines.append(f"| {getattr(c.point, x):.4g} | {getattr(c.point, y):.4g} | {certificate} | {status} |{r} "
                     f"{', '.join(c.excluded_by) or '—'} | {'; '.join(c.pending) or '—'} |")
    notes = sorted({f for c in v.crossings for f in c.flags})
    if notes:
        lines += [""] + [f"⚠ {n}." for n in notes]
    roots = summary_lines(v.table_roots, "roots only a table has, which an excluded conclusion also rests on"
                          if v.level == "excluded" else "roots only a table has")
    return lines + [""] + summary_lines(v.crossings) + roots


def _portal_section(entry_id: str) -> list[str]:
    if not entry_id:
        return []
    from adroit.parameter_space import library
    e = library.entry(entry_id)
    lines = [f"**From the portal library: {e.title}** (`{e.id}`, {e.family}).", "",
             f"- Lagrangian: {e.lagrangian}", f"- Dark matter: {e.dark_matter}", f"- Parameters: {e.parameters}",
             f"- Benchmark: {e.benchmark}"]
    if e.literature:
        lines.append(f"- The literature's result, to compare with: {e.literature}")
    if e.not_computed:
        lines.append(f"- Not computed for this model: {'; '.join(e.not_computed)}")
    lines += [f"- {r}" for r in e.references]
    return lines + [""]




def halo_line(preset: halo_region.HaloPreset | FixedHalo | None) -> str:
    """The report's statement of the halo the points were evaluated over."""
    if preset is None:
        return ("Halo: each experiment's published halo (the published-halo reproduction); experiments may use "
                "different numerical assumptions, and the halo's uncertainty is not varied.")
    if isinstance(preset, FixedHalo):
        from adroit.core.halo_choice import GALACTIC, resolve
        r = resolve(preset)
        return (f"Halo: every point at one fixed common benchmark, {r.summary} A comparison that cannot use it (a "
                f"structure compared through Path 1, a flavour-vector model's own limit) is pending and named; "
                f"{GALACTIC}. A fixed benchmark: the halo's uncertainty is not propagated.")
    return (f"Halo: every point over {halo_region.describe(preset)}. A point is excluded or allowed only if it is so "
            "throughout the region; otherwise pending: halo-sensitive (the region's centre shown as nominal), or halo "
            "coverage incomplete where a search could not be computed at every halo (docs/halo_region.md). An "
            "envelope over the region, not a profile likelihood; shape changes, streams and the LMC are not covered.")


def propagation_line(model: str | None) -> str:
    """The report's statement of the propagation model behind the charged cosmic-ray (antiproton) bounds."""
    from adroit.constraints import propagation
    model = propagation.normalise(model or "central")
    stronger = propagation.stronger(model)
    default = " (ADROIT's default, applied unless a run chooses another)" if model == "conservative" else ""
    return (f"Charged cosmic rays (AMS-02 antiprotons): the **{model}** propagation model decides{default} "
            f"({propagation.describe('calore-2202.03076-pbar', model)})"
            + (f"; points that only the {' or '.join(stronger)} model excludes are flagged, not excluded."
               if stronger else "."))


def discovery_section(coverage: DiscoveryCoverage, selected: list[str]) -> list[str]:
    """The report's account of a pinned discovery assessment: its date, its scope and every relevant constraint left
    unresolved for this run."""
    open_ = [r for r in coverage.requirements if not set(r.resolved_by) & set(selected)]
    when = coverage.searched_at or 'an unrecorded date'
    span = coverage.domain.get('m_chi')
    lines = ['## Constraint-discovery coverage', '', f'`{coverage.reference}` (survey of {when}'
             + (f', m_chi = {span[0]:g}–{span[1]:g} GeV; points outside it are pending' if span else '') + f'). '
             f'{coverage.scope}', '']
    if not coverage.complete:
        lines += ['**The assessment is incomplete** (' + ', '.join(f'{k}: {v}' for k, v in coverage.stages.items()
                                                                 if v != 'done') + '): every allowed point is pending.', '']
    lines += [f'- unresolved: {r.name} ({r.reference}): {r.reason}' for r in open_] or ['- none unresolved for this run']
    lines += [f'- gap in the survey: {g}' for g in coverage.gaps]
    return lines + ['']


def _model_section(result: Track1Result) -> list[str]:
    """Section 1: the fields, any selected private limits, and the audit of the Lagrangian."""
    from adroit.orchestrator.ideas import _fields_table
    spec, a = result.request.spec, result.audit
    from adroit.model_building import yukawa
    lines = [f"# Track 1: {spec.name}", "", "## 1. The model", ""] + _fields_table(spec) + [""]
    lines += [f"Yukawa inputs of the stated couplings (the masses m_f in g m_f/v): {yukawa.describe(spec.yukawa)}. "
              "The kinematic masses, explicitly stated couplings and the Higgs boson's own Yukawas do not depend on "
              "them.", ""]
    if result.request.private_limits:
        lines += ['## Selected private published limits','',
            'Exact reviewed/validated inputs for this dated analysis. Additions/replacements are explicit; '
            'published curves remain hard cuts and are not inferred likelihood terms.','']
        lines += ['- '+ref for ref in result.request.private_limits]+['']
    if result.discovery_coverage is not None:
        lines += discovery_section(result.discovery_coverage, result.request.private_limits)
    lines += [("**Valid**" if a.valid else f"**Not valid** ({len(a.problems)} problem(s))") +
              ": Lorentz and gauge invariance, matching spins, hermiticity and dimension.", ""]
    lines += [f"- {p.check}: {p.term + ': ' if p.term else ''}{p.message}" for p in a.problems]
    lines += [f"- missing term: {t.text} ({t.lorentz})" for t in a.missing]
    lines += [f"- flag: {f}" for f in a.flags]
    return lines


def _scan_summary(result: Track1Result) -> list[str]:
    """The verdict's headline and the plane scanned: the class, the fixed values, the relations and the ranges."""
    v, s = result.verdict, result.scan
    x, y = s.request.x.parameter, s.request.y.parameter
    cls = s.request.model_class
    name = (lambda k: cls.label(k)) if hasattr(cls, "label") else (lambda k: k)          # noqa: E731
    tied = ({"m_med"} if s.request.mediator_ratio else set()) | {r.derived for r in s.request.coupling_relations}
    used = getattr(cls, "LABELS", None) or result.fixed.model_dump()            # a portal names the slots it uses
    fixed = ", ".join(f"{name(k)} = {val:g}" for k, val in result.fixed.model_dump().items()
                      if k not in (x, y) and k not in tied and k in used)
    ratio = f"; {name('m_med')} = {s.request.mediator_ratio:g} × {name('m_chi')}" if s.request.mediator_ratio else ""
    ratio += "".join(f"; {r.text(name)}" for r in s.request.coupling_relations)
    return [f"**{level_label(v)}**: {v.summary}.", "",
            f"Class: {result.class_name} ({type(cls).__name__}); fixed at {fixed}{ratio}; scanned {name(x)} over "
            f"{s.xs[0]:.3g}–{s.xs[-1]:.3g} and {name(y)} over {s.ys[0]:.3g}–{s.ys[-1]:.3g} "
            f"({len(s.xs)} × {len(s.ys)} points).", "", *eos_policy_lines(v)]


def eos_policy_lines(v: Verdict) -> list[str]:
    """The equation-of-state policy, once, where the verdict's certificates record the nominal one
    (``certificate.EOS_NOT_ASSESSED``): a result made under another policy says what its certificates say."""
    from adroit.core.certificate import EOS_NOT_ASSESSED
    checks = [c.certificate.check("eos_band") for c in v.crossings if c.certificate is not None]
    if not any(x is not None and x.reason == EOS_NOT_ASSESSED for x in checks):
        return []
    return ["Equation of state: Ωh² is computed with ADROIT's nominal equation of state, Saikawa & Shirai's 2018 fit "
            "(arXiv:1803.01038), and each thermal solution is decided on it. The uncertainty of the equation of "
            "state (Saikawa & Shirai's 2020 upper and lower tables) is not propagated in ADROIT 1.0: it is deferred "
            "to 1.0.2, so no claim here is one of robustness across equations of state.", ""]


def _coverage_section(c: CoverageDiagnostic) -> list[str]:
    """The optional resolution check: its samples, its budget and its adaptive cell decisions."""
    count = sum(root.converged for root in c.root_attempts)
    samples = (f"{len(c.samples)}/{c.planned_samples} fresh samples" if c.settings.strategy == "uniform" else
               f"{len(c.samples)} adaptively sampled locations ({c.planned_samples} at full uniform depth)")
    lines = ["### Optional resolution check", "",
             f"{samples}; {c.evaluations}/{c.settings.max_evaluations} "
             f"relic-search evaluations; {count} certified sample points; {c.status}.",
             "Certified roots from this check receive the same constraint and final-density checks in the verdict above. "
             "The search budget covers density sampling/refinement; normal constraint evaluation is additional. "
             "Finite probes cannot rule out narrower unsampled features.", ""]
    if c.cells:
        decisions = {name: sum(cell.decision == name for cell in c.cells)
                     for name in ("split", "maximum_depth", "not_selected", "unresolved", "not_sampled")}
        lines += [f"Adaptive cell decisions: {decisions}. Unselected cells retain coarser resolution; "
                  "the diagnostic records every cell's bounds, depth and reason.", ""]
    return lines


def _theory_sections(result: Track1Result) -> list[str]:
    """The vacuum, unitarity, running and chemical-equilibrium certificates of the grid and the contour."""
    v, s = result.verdict, result.scan
    from adroit.theory.report import study_section
    theory_rows=[row.vacuum_certificate for row in s.points if row.vacuum_certificate is not None]
    theory_rows += [c.evaluation.vacuum_certificate for c in v.crossings if c.evaluation and c.evaluation.vacuum_certificate]
    lines: list[str] = []
    lines += study_section(theory_rows)
    from adroit.theory.unitarity_report import study_section as unitarity_section
    unitarity_rows=[row.unitarity_certificate for row in s.points if row.unitarity_certificate is not None]
    unitarity_rows += [c.evaluation.unitarity_certificate for c in v.crossings if c.evaluation and c.evaluation.unitarity_certificate]
    lines += unitarity_section(unitarity_rows)
    from adroit.theory.running_report import study_section as running_section
    running_rows=[p.running_certificate for p in (result.scan.points if result.scan else []) if p.running_certificate]
    running_rows += [c.evaluation.running_certificate for c in result.verdict.crossings
        if c.evaluation and c.evaluation.running_certificate] if result.verdict else []
    lines += running_section(running_rows)
    from adroit.theory.chemical_report import study_section as chemical_section
    chemical_rows=[p.chemical_certificate for p in s.points if p.chemical_certificate]
    chemical_rows += [c.evaluation.chemical_certificate for c in v.crossings if c.evaluation and c.evaluation.chemical_certificate]
    lines += chemical_section(chemical_rows)
    return lines


def _native_section(s: ScanResult) -> list[str]:
    """The native confidence-level comparisons, reported beside (never in) the 95% cuts (first 20)."""
    lines = []
    native_rows = [(row, name, outcome) for row in s.points for name, outcome in row.native_constraints.items()
                   if outcome.native_ratio is not None or outcome.native_excluded is not None]
    if native_rows:
        lines += ["Native confidence-level comparisons (not used as 95% cuts or in the combined likelihood; first 20):", "",
                  "| mass (GeV) | constraint | native CL | native ratio | native excluded | source |",
                  "|---|---|---|---|---|---|"]
        for row, name, o in native_rows[:20]:
            cl = f"{100 * o.confidence_level:g}%" if o.confidence_level is not None else "mixed/unspecified"
            ratio_native = f"{o.native_ratio:.4g}" if o.native_ratio is not None else "—"
            lines.append(f"| {row.point.m_chi:.6g} | {name} | {cl} | {ratio_native} | {o.native_excluded} | {o.source} |")
        lines += [""]
    return lines


def _literature_section(result: Track1Result) -> list[str]:
    """Section 5: the density record's status, the curated records, and prior work from arXiv."""
    from adroit.constraints import database
    density_record = database.record('planck-2018-omega')
    density_status = (f"verified by {density_record.verified_by} on {density_record.verified_on}"
                      if density_record.usable else "awaits a person's verification")
    lines = ["## 5. Literature", "", "Curated records and sources:",
             f"Planck density record: {density_status}. Other record status is shown in Records; "
             "unverified constraints stay pending unless explicitly requested.", ""]
    lines += [f"- {name}, {ref}: {what}" for name, ref, what in CURATED]
    lines += ["", f"Prior work ({result.literature_note}; titles as arXiv returns them):", ""]
    lines += [f"- arXiv:{p.arxiv_id} ({p.year or '—'}): {p.title}" for p in result.papers] or ["- none found"]
    return lines


@dated_report
def report(result: Track1Result) -> str:
    """Track 1's report in Markdown (plots referenced by file name, beside the report)."""
    lines = _model_section(result)
    lines += ["", "## 2. The verdict (thermal freeze-out)", ""]
    if result.unsupported:
        lines += [f"**UNDETERMINED.** The parameter-space scan cannot compute this model's whole picture: "
                  f"{result.unsupported}. Its validity stands; its direct-detection limits are available from "
                  "Path 1 (`adroit lagrangian`).", ""]
        return "\n".join(lines) + "\n"
    v, s = result.verdict, result.scan
    x, y = s.request.x.parameter, s.request.y.parameter
    lines += _scan_summary(result)
    from adroit.evidence.halo import identity_note
    lines += [propagation_line(s.request.propagation), "", halo_line(s.request.halo) + identity_note("track1", result),
              ""]
    if result.likelihood_verdict is not None:
        c = result.likelihood_verdict
        lines += [f"**With the constraints combined, {level_label(c)}**: {c.summary}.", ""]
    lines += [f"- Thermal coverage pending: {reason}" for reason in v.unresolved] + [""]
    if result.coverage is not None:
        lines += _coverage_section(result.coverage)
    lines += _theory_sections(result)
    lines += _portal_section(result.request.portal)
    lines += ["## 3. Parameter space", ""] + [f"![{p}]({p})" for p in result.plots] + [""]
    if v.crossings:
        lines += ["Points on the thermal-relic contour:", ""] + _contour_table(v, x, y) + [""]
    if result.likelihood_verdict is not None and result.likelihood_verdict.crossings:
        lines += ["Points in the thermal-relic band, the constraints combined (r = the combined ratio; "
                  "excluded above 1):", ""] + _contour_table(result.likelihood_verdict, x, y) + [""]
    lines += ["## 4. What was computed, and what was not", "",
              "Item by item in the viability checklist (section 6): each constraint compared, with its verdict over the "
              "grid and on the thermal contour; what applies but is not computed; and what does not apply.", ""]
    lines += [f"- {n}" for n in result.notes] + [""]
    lines += _native_section(s)
    lines += _literature_section(result)
    return "\n".join(lines) + "\n\n" + checklist_section(result)


def checklist_section(result: Track1Result) -> str:
    """Section 6: the viability checklist (computed afresh for an older result that did not store it)."""
    from adroit.constraints import viability
    from adroit.orchestrator import checklist
    entries = result.viability or checklist.for_track1(result)
    return viability.report(entries).replace("## Viability checklist (thermal freeze-out)",
                                             "## 6. Viability checklist (thermal freeze-out)", 1)


def reassessed(result: "Track1Result", budget: int, folder: Path | None = None) -> tuple["Track1Result", list[dict]]:
    """The saved study with each incomplete thermal point's halo work done again (``orchestrator.reassess``; the
    owner's plan of 2026-11-24, section 3): over its own halo region, with the count ratio's validations now in force
    and at most ``budget`` full calculations per point, the point's saved nominal evaluation reused as saved
    (``halo_evaluation.evaluate``'s ``nominal``: its relic density and halo-independent comparisons are not computed
    again). The point is then classified (``verdict.classify_saved``: no model is called) and certified under the
    present policy; every other point keeps what it saved. Each view (the cuts and, where saved, the combined) is
    reassessed and aggregated as a fresh verdict is (``verdict.aggregate``). ``folder``: where its figures are drawn.
    Returns the result and what was calculated, point by point."""
    from adroit.core.certificate import Check, nominal_eos_check
    from adroit.core.halo_choice import HALO_DATA, data_identity, holding
    from adroit.parameter_space import halo_evaluation, halo_region
    from adroit.parameter_space import verdict as V
    scan = result.scan
    region = halo_region.of(scan.request.halo) if scan is not None else None
    if not isinstance(region, halo_region.HaloPreset):
        raise ValueError("only a study over the halo region has halo coverage to complete")
    preset = region.model_copy(update={"full_calculations": budget})
    steps: list[dict] = []

    def view(v: "Verdict | None", likelihood) -> "Verdict | None":
        if v is None:
            return None
        crossings = list(v.crossings)
        for i, c in enumerate(crossings):
            if c.halo != halo_region.INCOMPLETE or c.evaluation is None or c.kind != "contour":
                continue
            cls = V._engine(scan, c.point)
            saved = c.evaluation.model_copy(update={"halo": None})
            started = time.perf_counter()
            r = halo_evaluation.evaluate(cls, c.point, preset, lambda saved=saved: saved,
                                         scan.request.unverified_records)
            judged = V.discovered(V.classify_saved(scan, r, likelihood), scan.request.discovery)
            judged = judged.model_copy(update={"target": c.target, "relative_residual": c.relative_residual,
                                               "converged": True, "kind": "contour"})
            root = Check(name="root", state="satisfied", reason=f"refined in its cell; its own Ωh² within "
                         f"{V.FINAL_RESIDUAL:.0%} of the target when judged (the saved evaluation, reused)")
            new = V._certified(scan, judged, "thermal_solution", (judged.status, list(judged.excluded_by)),
                               [root, nominal_eos_check()])
            crossings[i] = new
            steps.append({"view": "combined" if likelihood else "cuts", "index": i,
                          "point": {k: v for k, v in c.point.model_dump().items() if v},
                          "before": {"status": c.status, "halo": c.halo, "nominal": c.nominal_status},
                          "after": {"status": new.status, "halo": new.halo, "nominal": new.nominal_status,
                                    "reading": certification_words(new)},
                          "full_calculations": list(r.halo.full_calculations),
                          "seconds": round(time.perf_counter() - started, 1)})
        return V.aggregate(scan, crossings, list(v.unresolved), likelihood, v.target, list(v.root_attempts),
                           v.omitted_candidates, list(v.table_roots))
    with halo_region.using(region), holding(data_identity(tuple(HALO_DATA))):
        cuts = view(result.verdict, None)
        combined = view(result.likelihood_verdict, result.request.likelihood) if result.likelihood_verdict else None
    new = result.model_copy(update={"verdict": cuts, "likelihood_verdict": combined})
    if folder is not None:
        paths = [plots.plane(scan, cuts, Path(folder) / "parameter_plane.png", title=result.request.spec.name)]
        if dd := plots.direct_detection_saved(cuts, Path(folder) / "direct_detection.png"):
            paths.append(dd)
        new = new.model_copy(update={"plots": [Path(p).name for p in paths]})
    from adroit.orchestrator import checklist
    return new.model_copy(update={"viability": checklist.for_track1(new)}), steps


def certification_words(c) -> str:
    """A reassessed point in the report's words (``certification.status_words``)."""
    from adroit.parameter_space.certification import status_words
    return status_words(c)
