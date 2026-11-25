"""Running a pipeline into a folder: its result, its report and (Path 1) its plot (DM11).

Shared by the command line and the workbench, so that both run exactly the
same code. Each function writes ``result.json``, ``report.md`` and its study
record ``study.json`` (DM14: inputs, steps, cost, outputs, parent, children)
into the folder, with any plots, and returns the folder and the report. A
language model is called only where one is passed in (``llm``).
"""

from __future__ import annotations

import re
import os
import secrets
from pathlib import Path

from adroit.core.config import get_settings
from adroit.core.evidence import EvidenceContext
from adroit.evidence.runtime import capture_request

DEFAULT_NULLS = ["CRESST-III 2019", "CDMSlite Run 2", "PICO-60 C3F8 (2019)", "DEAP-3600 (2019)"]


def parse_list(text: str) -> list[str]:
    """Comma-separated items, stripped, empty ones dropped."""
    return [part.strip() for part in text.split(",") if part.strip()]


def parse_values(text: str) -> dict[str, float]:
    """``name=value,name=value`` as a dictionary.

    Raises:
        ValueError: if an item has no '=' or its value is not a number.
    """
    out = {}
    for pair in parse_list(text):
        name, sep, number = pair.partition("=")
        if not sep:
            raise ValueError(f"expected name=value, got {pair!r}")
        out[name.strip()] = float(number)
    return out


def slug(text: str) -> str:
    """A folder name made from free text."""
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_") or "run"


FOLDER_TRIES = 16
# a workbench job's own files in its run folder (``ui.engine``: its record, lock, log, cancel request and history)
JOB_FILES = frozenset({"job.json", ".job.lock", "log.txt", "control.json", "job_history.jsonl"})


def fresh(folder: Path) -> bool:
    """Whether ``folder`` is new, or empty but for a workbench job's own files (``JOB_FILES``) and its publication lock
    (``durable.PUBLICATION_LOCK``, which holds nothing): a command that writes only into a fresh folder can then run as
    a workbench job, whose record and log are in its folder before it starts (found 2026-10-23: ``experiments import``
    and ``reanalyse run`` refused every workbench launch), and claim it first (a reanalysis: DE-02)."""
    from adroit.core.durable import PUBLICATION_LOCK
    folder = Path(folder)
    if not folder.exists():
        return True
    return folder.is_dir() and all(p.name in JOB_FILES or p.name == PUBLICATION_LOCK for p in folder.iterdir())


def unique_folder(parent: Path, stem: str) -> Path:
    """A new, empty folder ``parent/stem_xxxxxxxx`` with a random suffix, created here with an exclusive create, so
    that two launches never share one, whatever their clock (the re-audit's R18-3, 2026-10-18: workbench runs named
    by the second overwrote each other); a clash retries with another suffix."""
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    for _ in range(FOLDER_TRIES):
        folder = parent / f"{stem}_{secrets.token_hex(4)}"
        try:
            folder.mkdir()
        except FileExistsError:
            continue
        return folder
    raise FileExistsError(f"no free run folder for {stem} in {FOLDER_TRIES} tries")


def _folder(folder: Path | None, default: str) -> Path:
    path = folder or get_settings().runs_dir / default
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write(out: Path, result, report: str, kind: str, title: str, inputs: dict | None = None,
           cost_usd: float = 0.0, parent: Path | None = None,
           evidence_context: EvidenceContext | None = None, *, certify=None, published: dict | None = None,
           claim=None, beside: dict | None = None) -> str:
    """The result, the report and the study record (DM14), each written whole (``durable.write_atomic``: M3); the
    evidence and the report of the one serialization of the result (``build.publish``: the auditor's CY recheck, CZ-02), the
    report bound to it and its figures (``evidence.bindings``: the auditor's CX recheck, CY-03, 2026-11-01), and the study
    record naming that serialization's digest (``studies.Study.result_sha256``: the auditor's version-identity audit, VI-01,
    2026-11-03).

    ``certify``: called with that digest once the result is computed and before anything of it is written, it returns
    what its writer certifies of it, in its evidence from the first publication (a reanalysis's lineage), or refuses
    (ValueError), and nothing is written. ``published``: given, it receives the version as written (``token``, an
    ``evidence.version.Token`` naming each part by the identity it was written with), for what follows the publication
    to require (the auditor's version-handle audit, DD-01, 2026-11-04: a reanalysis had added its lineage, after
    publication, to whatever the folder then held).

    All of it, from ``certify`` to the record, under the folder's publication lock (``durable.publishing``; ``claim``,
    its writer's own, held already: a reanalysis holds its child's from its start), so that no other publication's part
    is written between its parts; each part written only where those before it are still its own, else ``Replaced``,
    naming what it wrote (the auditor's DD recheck, DE-02, 2026-11-05). ``beside``: files its writer puts beside its parts
    (name: a JSON object; a reanalysis's lineage, given by its ``certify``), written once its parts are written and
    checked, before its record, which lists them: never beside another publication's parts."""
    import hashlib
    from adroit.core.chronology import analysis_report,model_references
    from adroit.core.durable import publishing
    from adroit.evidence.build import incomplete, kept_parts, publish
    from adroit.orchestrator import studies
    content = result.model_dump_json(indent=1).encode()
    recorded=str(getattr(result,'created','')) if 'created' in getattr(result,'model_fields_set',set()) else ''
    refs=model_references(result)
    own=evidence_context or (result if getattr(result,'calculation_started_at','') else None)
    written: dict[str, str] = {}
    evidence = kind in ("track1", "signal", "single_idea", "exclusion", "idea", "lagrangian")

    def dated(envelope):         # without a captured context, the result's own dates
        return analysis_report(report,recorded,envelope.context if envelope and evidence_context else own,refs)
    with publishing(out, claim) as held:
        certified=certify(hashlib.sha256(content).hexdigest()) if certify is not None else None
        with incomplete(out / "result.json", hashlib.sha256(content).hexdigest()):   # from its first part to its record
            envelope,text=publish(out / "result.json",content,result,dated,workflow=kind,context=evidence_context,
                                 evidence=evidence,certificates=certified,written=written,claim=held,marked=True)
            kept_parts(out / "result.json", content, ("result", "evidence", "report") if evidence else
                        ("result", "report"), written["evidence"], written["presentation"])     # before its record
            from adroit.core.checkpoint import atomic_json
            for name, data in (beside or {}).items():
                atomic_json(out / name, data)
            ctx=envelope.context if envelope and evidence_context else own
            study=studies.record(out, kind, title, inputs=inputs, cost_usd=cost_usd, parent=parent,
                                 calculation_started_at=getattr(ctx,'calculation_started_at',''),
                                 calculation_completed_at=getattr(ctx,'calculation_completed_at',''),
                                 model_references=refs, result_sha256=hashlib.sha256(content).hexdigest(),claim=held)
            parts = ("result", "evidence", "report") if evidence else ("result", "report")
            kept_parts(out / "result.json", content, parts, written["evidence"], written["presentation"],
                       said=(*parts, *(f"{name} beside them" for name in beside or {}), "record"))  # after its record
    if published is not None:
        from adroit.evidence.version import Token
        published["token"]=Token(str(out / "result.json"),record=studies.identity(study),**written)
    return text


def exclusion(card: str, isospin: str = "", values: dict[str, float] | None = None,
              masses_gev: list[float] | None = None, splitting_kev: float = 0.0,
              modules: list[str] | None = None, folder: Path | None = None) -> tuple[Path, str]:
    """Path 1 (DM5) for a library card: limits in every chosen module, a plot and a report."""
    from adroit.library.interactions import registry as library
    from adroit.orchestrator import exclusion as path1
    params = library.isospin_values(card, isospin, 1.0 / 246.2 ** 2) if isospin else {}
    params.update(values or {})
    request = path1.ExclusionRequest(card_id=card, values=params, masses_gev=masses_gev or [10, 30, 100, 300, 1000],
                                     splitting_kev=splitting_kev, modules=modules or [])
    evidence_context = capture_request(request)
    result = path1.run(request)
    out = _folder(folder, f"exclusion_{slug(card)}")
    from adroit.core.durable import publishing
    with publishing(out) as owned:          # its plots and its publication, the folder its own (DF-01)
        report = path1.report(result)
        path1.plot(result, out / "exclusion.png")
        table, why = path1.si_table(result)
        if table:
            path1.sigma_plot(result, out / "exclusion_sigma_si.png", table)
            report += path1.fog_section(result, [table[m] for m in result.request.masses_gev])
            if why:
                report += f"\nIn the σ view, {why}.\n"
        else:
            report += f"\nNo σ_SI view of these limits: {why}.\n"
        report=_write(out, result, report, "exclusion", f"Path 1: {card}", {"card": card, "isospin": isospin},
               evidence_context=evidence_context, claim=owned)
    return out, report


def signal(experiment: str, null_modules: list[str] | None = None, leaders: int = 8, toys: int = 200_000,
           folder: Path | None = None, user_models: list | None = None, with_library: bool = False,
           unverified: bool = False, model_preferences: list | None = None,
           splittings_kev: list[float]|None=None,experimental_profile:str='',track1_results:list[str]|None=None,
           eligibility_settings=None, halo=None, halos=None, search=None) -> tuple[Path, str]:
    """Path 2 (DM6): fit a model space (the library's, or users' models; DM14) to a search's events,
    combine, rank and report; ``halo``: a fixed common benchmark (``halo_choice.FixedHalo``), else each search's own
    published halo; ``halos``: the halo models compared (``signal.compared``), the first the run the study shows;
    ``search``: (settings, budgeted client) of the agent-led search after the fixed scan (``signal_search``)."""
    from adroit.orchestrator import signal as path2
    request = path2.SignalRequest(experiment=experiment,
                                  null_modules=DEFAULT_NULLS if null_modules is None else null_modules,
                                  leaders=leaders, toys=toys, user_models=user_models or [],
                                  with_library=with_library, unverified_records=unverified,
                                  model_preferences=model_preferences or [],splittings_kev=splittings_kev or [0.0],experimental_profile=experimental_profile,
                                  halo=halos[0] if halos else halo, halos=list(halos or []))
    request.track1_results=track1_results or []
    if eligibility_settings is not None:
        request.eligibility_settings=eligibility_settings
    if experimental_profile:
        from adroit.library.experimental_profiles import apply_signal
        request=apply_signal(request)
    evidence_context = capture_request(request)
    result = path2.run(request)
    if search is not None:
        from adroit.orchestrator import signal_search
        result = signal_search.run(result, search[1], search[0])
    out = _folder(folder, f"signal_{slug(experiment)}")
    report = path2.report(result)
    report=_write(out, result, report, "signal", f"Signal best fits: {experiment}",
           {"experiment": experiment, "user_models": [um.spec.name for um in request.user_models],
            "with_library": with_library}, evidence_context=evidence_context)
    return out, report


def lagrangian(model_yaml: str, numerical_check: bool = False, folder: Path | None = None,
               name: str = "model", *, description: str = "", primary=None, checker=None,
               deriver: str = "", checker_model: str = "") -> tuple[Path, str]:
    """Path 1 for a bespoke model (DM8), from the YAML text of a model and its derivation; or, with a language
    model (``primary``, paid), the derivation of its Wilson coefficients, checked by an independent second
    derivation (``checker``) that must agree at the nucleon level. ``description``: the model in words, typed
    first by the intake agent."""
    import yaml
    from adroit.orchestrator import lagrangian as bespoke
    data = (yaml.safe_load(model_yaml) if model_yaml else None) or {}
    if primary is not None:
        if data.get("derivation"):
            raise ValueError("the model already has a derivation; derive only a model without one")
        data.update(use_language_models=True, second_derivation=checker is not None,
                    **({"description": description} if description else {}),
                    **({"deriver": deriver} if deriver else {}), **({"checker": checker_model} if checker_model else {}))
    request = bespoke.LagrangianRequest.model_validate(data)
    if numerical_check:
        request = request.model_copy(update={"numerical_check": True})
    before = sum(getattr(c, "spent", 0.0) for c in (primary, checker) if c is not None)
    evidence_context = capture_request(request, experiments=request.run_exclusion)
    result = bespoke.run(request, primary, checker)
    spent = sum(getattr(c, "spent", 0.0) for c in (primary, checker) if c is not None) - before
    out = _folder(folder, f"lagrangian_{slug(result.spec.name if result.spec else name)}")
    report = bespoke.report(result)
    report=_write(out, result, report, "lagrangian", f"Path 1: {result.spec.name if result.spec else name}",
                  cost_usd=spent, evidence_context=evidence_context)
    return out, report


def write_models(out: Path, result, catalog_draft: bool = False) -> list[str]:
    """Each valid model of an idea run as a typed model file that ``adroit track1`` reads (``models/<name>.yaml``,
    with its approval digest), and, on request, an unapproved catalog draft for a person to review. Returns the
    report's lines."""
    import yaml
    from adroit.orchestrator.model_approval import select_model, write_approved
    lines, ready = [], []
    for m in result.models:
        try:
            spec, approval = select_model(m)
        except ValueError as error:
            lines.append(f"- {m.spec.name}: no model file ({error})")
            continue
        path = out / "models" / f"{slug(spec.name)}.yaml"
        n = 2
        while path.exists() and yaml.safe_load(path.read_text()).get("spec") != spec.model_dump(mode="json"):
            path, n = out / "models" / f"{slug(spec.name)}_{n}.yaml", n + 1
        write_approved(path, spec, approval)
        ready.append(spec)
        lines.append(f"- {spec.name}: `models/{path.name}`; run it with `adroit track1 {path}`")
        lines += _computability(out, spec, path.stem)
    if catalog_draft and ready:
        from adroit.orchestrator.model_intake import Intake
        intake = Intake()
        session = intake.start(0)
        for spec in ready:
            intake.step(session.session_id, "typed", yaml.safe_dump(spec.model_dump(mode="json"), allow_unicode=True))
        lines.append(f"- catalog drafts (unapproved) in intake session {session.session_id}: review at "
                     f"/models/intake?session={session.session_id}, or `adroit models draft {session.session_id} STEP`")
    return ["## Runnable models", "", *(lines or ["No valid model to write."]), ""]


def _computability(out: Path, spec, stem: str) -> list[str]:
    """Report lines saying whether a written model is computed as it stands; if not, each computable completion
    (``completions``) is written beside it, its stated choices in its assumptions, for the researcher to review."""
    import yaml
    from adroit.orchestrator.completions import completions, mixing_choice
    from adroit.parameter_space.classify import Unsupported, classify
    try:
        classify(spec)
        return ["  - computed by Track 1 as it stands"]
    except Unsupported as error:
        refusal = str(error)
    lines = [f"  - not computed as it stands: {refusal}"]
    for k, o in enumerate(completions(spec), 1):
        path = out / "models" / f"{stem}_completion_{k}.yaml"
        path.write_text(f"# A computable completion of {spec.name}: review its stated choices before use.\n"
                        + yaml.safe_dump(o.spec.model_dump(mode="json"), sort_keys=False, allow_unicode=True))
        lines.append(f"  - computable completion {k} (`models/{path.name}`): " + "; ".join(o.choices))
    if mixing_choice(refusal):
        lines.append(f"  - to compute it, {mixing_choice(refusal)}")
    return lines


def idea(request, llm=None, folder: Path | None = None, name: str = "idea",
         catalog_draft: bool = False) -> tuple[Path, str]:
    """Track 1's front end (DM12): models from a field content, a Lagrangian or an idea, each audited, and each
    valid one written as a typed model file for ``adroit track1`` (``write_models``)."""
    from adroit.orchestrator import ideas
    before = getattr(llm, "spent", 0.0)
    evidence_context = capture_request(request, experiments=False)        # no experiment is consulted
    result = ideas.run(request, llm)
    out = _folder(folder, f"idea_{slug(name)}")
    from adroit.core.durable import publishing
    with publishing(out) as owned:          # its model files and its publication, the folder its own (DF-01)
        report = ideas.report(result).rstrip("\n") + "\n\n" + "\n".join(write_models(out, result, catalog_draft))
        report=_write(out, result, report, "idea", f"Track 1's front end: {name}",
                      cost_usd=getattr(llm, "spent", 0.0) - before, evidence_context=evidence_context, claim=owned)
    return out, report


def track1(request, folder: Path | None = None, name: str = "model", parent: Path | None = None,
           resume: bool = False, *, certify=None, published: dict | None = None, claim=None,
           beside: dict | None = None) -> tuple[Path, str]:
    """Track 1 (DM13): validity, the parameter scan, the verdict, the plots and the literature of one model
    (``certify``, ``published``, ``claim``, ``beside``: ``_write``'s). The folder is held (``durable.publishing``;
    ``claim``, its writer's own) from before the run writes anything into it, its checkpoint and its plots, to its
    record: a run refused writes nothing (the auditor's DE recheck, DF-01, 2026-11-05: a run refused only at its record had
    first drawn its plane over the holder's, and the holder's report had bound it)."""
    from adroit.orchestrator import track1 as t1
    if request.experimental_profile:
        from adroit.library.experimental_profiles import apply_track1
        request=apply_track1(request)
    from adroit.constraints.propagation import resolved
    from adroit.parameter_space import halo_region
    request = halo_region.resolved(resolved(request))  # the propagation model and the halo are part of the captured request
    out = _folder(folder, f"track1_{slug(name)}")
    from adroit.core.durable import publishing
    with publishing(out, claim) as owned:
        evidence_context = capture_request(request)
        context = {"name": name, "parent": os.path.relpath(parent.resolve(), out.resolve()) if parent else "",
                   "calculation_started_at": evidence_context.calculation_started_at}
        held = {}
        result = t1.run(request, out, resume=resume, context=context, held=held, claim=owned)
        # the dates of the result restored or computed, as its checkpoint holds them in this run; never another
        # publication's, nor the file read again (the auditor's version-identity audit, VI-05; its DB/VI recheck, DC-03)
        evidence_context = restored_dates(evidence_context, out, result, held.get("chronology")) if resume \
            else evidence_context
        if resume:
            from adroit.core.checkpoint import Manifest
            saved = Manifest.model_validate_json((out / ".track1-checkpoint/manifest.json").read_text()).context
            if saved.get("parent"):
                restored = (out / saved["parent"]).resolve()
                if parent is not None and parent.resolve() != restored:
                    raise ValueError("Resume cannot change the study's original parent")
                parent = restored
        report = t1.report(result)
        report=_write(out, result, report, "track1", f"Track 1: {request.spec.name}", {"model": request.spec.name},
                      parent=parent, evidence_context=evidence_context, certify=certify, published=published,
                      claim=owned, beside=beside)
    return out, report


def restored_dates(context: EvidenceContext, folder: Path, result, held) -> EvidenceContext:
    """A resumed run's evidence context, dated as the calculation of the result it publishes (``result``), as its
    checkpoint holds it in this run (``held``, ``Checkpoint.chronology``), never as read again from the file:
    - read back with the dates saved with it: those (the auditor's version-identity audit, VI-05, 2026-11-03: a resume
      restoring A beside a publication of B had dated A with B's dates);
    - computed, or completed, by this run: from its checkpoint's first run's start, where that run recorded it, else
      this run's, to its completion (the auditor's DB/VI recheck, DC-03, 2026-11-03: a native fit resumed part way, its
      result incomplete, had been dated from the restart);
    - read back from a checkpoint saved before ADROIT kept them: the dates of the publication beside it only where that
      publication holds this result, value for value (``payload_digest``); else none, saying so.
    None (a run holding no checkpoint, a calculation stood in for) leaves ``context`` as it is."""
    from adroit.core.checkpoint import payload_digest
    from adroit.evidence.version import resolve
    if held is None:
        return context
    if held.started or not held.restored:
        return context.model_copy(update={"calculation_started_at": held.started or context.calculation_started_at,
                                          "calculation_completed_at": held.completed})
    try:                                    # the publication beside it, one version (``evidence.version``)
        beside = resolve(Path(folder) / "result.json")
        previous = beside.saved() if beside.evidence_state == "bound" else None
    except (OSError, ValueError):
        previous = None
    if previous is not None and previous.envelope.context.calculation_started_at \
            and payload_digest(previous.result) == payload_digest(result):
        dated = previous.envelope.context
        return context.model_copy(update={"calculation_started_at": dated.calculation_started_at,
                                          "calculation_completed_at": dated.calculation_completed_at})
    return context.model_copy(update={"calculation_started_at": "", "calculation_completed_at": "", "notes": [
        *context.notes, "restored from a checkpoint saved without its calculation's dates (before ADROIT kept them); "
        "when it was calculated is not recorded"]})


def single_idea(request, folder: Path | None = None, parent: Path | None = None, *, certify=None,
                published: dict | None = None, claim=None, beside: dict | None = None) -> tuple[Path, str]:
    """DM14: one user's model as the explanation of an anomaly (Track 2 for one idea, Track 1 around its fit;
    ``certify``, ``published``, ``claim``, ``beside``: ``_write``'s), the folder held from before its first file
    (``track1``'s; DF-01)."""
    from adroit.orchestrator import single_idea as si
    request = si.prepared(request)               # the request calculated and saved, captured before it (DG-04)
    out = _folder(folder, f"single_idea_{slug(request.spec.name)}_{slug(request.experiment)[:40]}")
    evidence_context = capture_request(request)
    from adroit.core.durable import publishing
    with publishing(out, claim) as owned:
        result = si.run(request, out, claim=owned)
        report = si.report(result)
        report=_write(out, result, report, "single_idea", f"{request.spec.name} for {request.experiment}",
               {"experiment": request.experiment, "model": request.spec.name}, parent=parent,
               evidence_context=evidence_context, certify=certify, published=published, claim=owned, beside=beside)
    return out, report


def promote(parent: Path, which: list[str], options: dict | None = None, llm=None, uv_models: int = 3,
            parent_sha256: str = "") -> tuple[Path, str]:
    """DM14's recursion: candidates of a Path 2 run promoted to studies inside its folder (with ``parent_sha256``, only
    from that version of its result: ``promote.parent_result``)."""
    from adroit.orchestrator import promote as rec
    result = rec.promote(parent, which, options, llm, uv_models, parent_sha256=parent_sha256)
    report = rec.report(result)
    from adroit.evidence.build import publish
    # Promotion itself performs no new point calculation; each child has its own captured context. Its record, the
    # evidence and the report of one serialization (``build.publish``: the auditor's CY recheck, CZ-02).
    publish(promotion_record(parent, which), result.model_dump_json(indent=1).encode(), result,
            lambda envelope: report, workflow="promotion")
    return Path(parent), report


def promotion_record(parent: Path, which: list[str]) -> Path:
    """Where a promotion of ``which`` from the run in ``parent`` keeps its record (``promote.Promotion``)."""
    return Path(parent) / f"promotion_{slug('_'.join(which))[:60]}.json"
