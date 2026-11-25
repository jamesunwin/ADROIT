"""Recursion (DM14): a Track 2 candidate, or a degeneracy class, promoted to Track 1 studies.

A Path 2 run's candidate is a nucleon-level interaction at a mass. Promoting it
asks which full models produce it, and what the data then allow for each:
1. **The models:**
   - a user's model (a Path 2 candidate built from it) is itself;
   - a library card has the computable simplified models that produce it at
     tree level (``simplified.completions``);
   - optionally, the model builder (DM12's agent; paid, opt-in) proposes
     renormalizable completions. Each is built and audited by DM12, and
     enters a study only if DM13 can compute it.
2. **Each model's study** is a single-idea study (``single_idea``) against the
   parent's anomaly, over masses around the candidate's: the fit, the
   tension with the null experiments, the best-fit band and Track 1 around
   it.
3. **The record:** each child is written inside the parent's
   ``children/``, with its ``study.json`` naming the parent, and the
   parent's study lists its children (``studies``). A child can itself be
   promoted, since every study is a folder like any other.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from pydantic import Field

from adroit.core.chronology import dated_report, timed
from adroit.core.model_spec import ModelSpec
from adroit.core.state import StrictModel
from adroit.library.interactions import registry
from adroit.orchestrator import single_idea, studies
from adroit.orchestrator.runs import slug
from adroit.orchestrator.signal import Candidate, SignalResult
from adroit.parameter_space import simplified
from adroit.parameter_space.classify import Unsupported, classify

UV_PROMPT = ("Renormalizable models that generate, at tree level, the effective interaction {name} ({form}) "
             "between fermion dark matter of mass about {mass:g} GeV and nucleons, {isospin}. The dark matter is a "
             "thermal relic. Where a new field couples to one Standard Model fermion flavour (a t-channel partner of "
             "the u quark, say), list that flavour as its own field (role standard_model, generations 1) so that "
             "the model is computable; a new scalar that mixes with the Higgs needs a mixing angle and potential "
             "that a researcher must give, so say so in its assumptions.")
ISOSPIN_TEXT = {"s": "with equal couplings to protons and neutrons (isoscalar)",
                "v": "with opposite couplings to protons and neutrons (isovector)"}


class Child(StrictModel):
    """One promoted study: the candidate it came from, the model, its origin, its folder, and its level and summary."""
    label: str                           # the candidate it was promoted from
    model: str
    origin: str                          # "the user's model", "simplified completion", "model builder"
    folder: str
    level: str = ""
    summary: str = ""
    # the SHA-256 of the study's result as the promotion wrote it, which its export and verification require of the
    # study attached as this child (the auditor's CY recheck, CZ-01, 2026-11-01); absent in older records
    result_sha256: str = Field(default="", exclude_if=lambda v: not v)


class CompletionChoice(StrictModel):
    """A computable completion of a builder's proposal that needs the researcher's choice before it is studied."""
    label: str                          # the candidate
    proposal: str                       # the builder's model it completes
    model: str
    choices: list[str] = Field(default_factory=list)
    file: str = ""                      # the typed model
    # the request that studies it as a child of the candidate (``_child_request``, HC-02), which ``command`` runs as
    # saved; absent in older records, whose command named the model, the search and the masses alone
    request: str = Field(default="", exclude_if=lambda v: not v)
    request_sha256: str = Field(default="", exclude_if=lambda v: not v)    # the request's bytes as offered (HD-02)
    command: str = ""


class Promotion(StrictModel):
    """A promotion's record: the parent run, the candidates promoted, the child studies, what has no study and why,
    the cost, and the completions waiting for the researcher's choice."""
    parent: str
    labels: list[str]
    children: list[Child] = Field(default_factory=list)
    undetermined: dict[str, str] = Field(default_factory=dict)   # candidate or model → why it has no study
    cost_usd: float = 0.0                                        # the model builder's settled dollars
    # its requests whose bill is not known, still reserved (M2: the report had said "spent $0.00", settled cents
    # rounded away and the reservation left out); absent in older records and where there is none
    reserved_usd: float = Field(default=0.0, exclude_if=lambda v: not v)
    dropped: dict[str, str] = Field(default_factory=dict)        # class members left out, and why
    choices: list[CompletionChoice] = Field(default_factory=list)  # completions waiting for the researcher
    # the SHA-256 of the parent's result as the promotion read it: the version its candidates were taken from (the auditor's
    # CX recheck, CY-02, 2026-11-01); absent in older records
    parent_sha256: str = Field(default="", exclude_if=lambda v: not v)
    calculation_started_at: str = ""          # UTC, recorded by chronology.timed
    calculation_completed_at: str = ""


def candidates_of(result: SignalResult) -> dict[str, Candidate]:
    """Every candidate of a Path 2 run by label (the library's are rebuilt as the run built them)."""
    from adroit.orchestrator import variants
    return variants.candidates_of(result)


def labels_of(result: SignalResult, which: str,include_excluded:bool=False) -> list[str]:
    """A candidate's label, or ``class:N`` for every member of degeneracy class N."""
    if which.startswith("class:"):
        n = int(which.removeprefix("class:"))
        return sorted(label for label, k in result.classes.items() if k == n and
            (include_excluded or label not in result.eligibility or result.eligibility[label].status!='excluded_point'))
    if which not in result.classes:
        raise KeyError(f"no candidate {which!r} in this run")
    if not include_excluded and which in result.eligibility and result.eligibility[which].status=='excluded_point':
        raise KeyError('fitted point is excluded; use --include-excluded only for explicit alternative-branch follow-up')
    return [which]


def completion_refusal(c: Candidate) -> str:
    """Why the simplified completions would not reproduce a library candidate ('' if they would; audit M7).

    They are elastic, isoscalar mediators with the card's own couplings: an inelastic splitting, an isovector
    candidate or a variant's values would be replaced by a different candidate under the same label."""
    if c.model:
        return ""
    if c.splitting_kev:
        return (f"inelastic (δ = {c.splitting_kev:g} keV): the simplified completions are elastic, so they would "
                "replace this candidate with a different one")
    if c.isospin == "v":
        return "isovector: no computable simplified completion produces it at tree level"
    if c.values:
        return (f"a variant ({', '.join(f'{k} = {v:g}' for k, v in sorted(c.values.items()))}): the simplified "
                "completions fix the card's own couplings")
    return ""


def models_for(result: SignalResult, c: Candidate) -> list[tuple[str, ModelSpec]]:
    """(origin, model) for every computable model that produces the candidate; none for a candidate the
    completions would not reproduce (``completion_refusal``)."""
    if not c.model and completion_refusal(c):
        return []
    if c.model:
        return [("the user's model", um.spec) for um in result.request.user_models
                if (um.catalog_reference or um.spec.name)==c.model]
    return [("simplified completion", simplified.model(kind, m_chi=c.mass_gev, m_med=1000.0,
                                                       name=f"{kind}_mediator_for_{c.card_id}"))
            for kind in simplified.completions(c.card_id, c.isospin)]


def _child_request(parent_request, c: Candidate, spec: ModelSpec, options: dict, global_z: float | None):
    """A model's single-idea request as a child of the candidate ``c`` of the Path 2 run that ``parent_request`` made
    (its global significance ``global_z``), as it is calculated and saved: at its parent's halo, a parent's fixed common
    benchmark (its whole snapshot) the child's, for its fit, nulls, band and plane alike (halo phase 1); a parent with
    each search's published halo leaves the child its own default (its fit at the published halos, as the parent's
    was, its constraints and plane over the region the setting names). Its defaults are resolved now
    (``single_idea.prepared``), before its capture, as the single idea's (DG-04). One construction for a child studied
    now (``_study``) and for one offered for the researcher's choice (``_offer``: HC-02)."""
    span, n = options.get("span", 4.0), options.get("masses", 9)
    request = single_idea.SingleIdeaRequest(
        experiment=parent_request.experiment, spec=spec,
        masses_gev=np.geomspace(c.mass_gev / span, c.mass_gev * span, n).tolist(),
        null_modules=parent_request.null_modules, toys=options.get("toys", 20_000), grid=options.get("grid", 16),
        literature=options.get("literature", False), workers=options.get("workers", 2),
        unverified_records=parent_request.unverified_records,experimental_profile=parent_request.experimental_profile,
        parent_global_z=global_z, halo=parent_request.halo)
    selected=next((u for u in parent_request.user_models if (u.catalog_reference or u.spec.name)==c.model),None)
    if selected:
        request=request.model_copy(update={'catalog_reference':selected.catalog_reference,'derivation':selected.derivation})
    if options.get("native_joint"):
        from adroit.parameter_space.native_joint import JointSettings
        request = request.model_copy(update={
            "native_joint": JointSettings.model_validate(options["native_joint"])
        })
    return single_idea.prepared(request)


def _study(parent: Path, result: SignalResult, c: Candidate, origin: str, spec: ModelSpec,
           options: dict, fetch=None, under: Path | None = None) -> Child:
    """One model's single-idea study, written inside the parent's (or ``under``'s) children, at its parent's halo
    (``_child_request``)."""
    request = _child_request(result.request, c, spec, options, result.global_z)
    home = under or parent
    folder = home / "children" / slug(f"{spec.name}_{c.label}")
    import hashlib
    from adroit.evidence.runtime import capture_request
    from adroit.evidence.build import publish
    evidence_context = capture_request(request)
    from adroit.core.durable import publishing
    # its calculation, its parts and its record under one hold of its folder, from its first file (the auditor's DD recheck,
    # DE-02; its DE recheck, DF-01: a child refused at its record had first drawn into the folder)
    from adroit.evidence.build import incomplete
    with publishing(folder) as held:
        r = single_idea.run(request, folder, fetch, claim=held)
        content = r.model_dump_json(indent=1).encode()          # each whole (M3), of one serialization (CZ-02)
        # marked from its first part to its record, its last (the auditor's merge-round audit, HE-02, 2026-11-12)
        with incomplete(folder / "result.json", hashlib.sha256(content).hexdigest()):
            publish(folder / "result.json", content, r, lambda envelope: _dated(single_idea.report(r), r, envelope),
                    workflow="single_idea", context=evidence_context, claim=held, marked=True)
            studies.record(folder, "single_idea", f"{spec.name} for {result.request.experiment}",
                           inputs={"experiment": result.request.experiment, "model": spec.name,
                                   "promoted_from": c.label, "origin": origin},
                           steps=["fit at each mass", "global significance", "combination with the null experiments",
                                  "best-fit band", "the plane around the band, signal-qualified"], parent=home,
                           result_sha256=hashlib.sha256(content).hexdigest(), claim=held)    # of the bytes published
    return Child(label=c.label, model=spec.name, origin=origin, folder=str(folder), level=r.level, summary=r.summary,
                 result_sha256=hashlib.sha256(content).hexdigest())


def _dated(report: str, result, envelope) -> str:
    """A child's report, dated with its evidence's calculation context; ``build.publish`` binds it to the result's
    bytes and its figures (``evidence.bindings``: the auditor's CX recheck, CY-03; its CY recheck, CZ-02)."""
    from adroit.core.chronology import analysis_report, model_references
    if envelope is not None and envelope.context.calculation_started_at:
        report = analysis_report(report, context=envelope.context, references=model_references(result))
    return report


def _completed(spec: ModelSpec, error: Unsupported, c: Candidate) -> tuple[list[ModelSpec], list, str]:
    """For a proposal DM13 refuses: (completions to study now, completions that need the researcher's choice, why).
    A completion is studied now only when it is the one completion that reproduces the candidate and its only
    choice is the flavour (the candidate's nucleon couplings then fix it)."""
    from adroit.orchestrator.completions import completions, mixing_choice
    computable = completions(spec)
    found = [o for o in computable if _reproduces(o.spec, c)]
    now = found if len(found) == 1 and found[0].flavour_only else []
    offered = [o for o in found if o not in now]
    why = f"proposed by the model builder; not computable by DM13 as proposed: {error}"
    if now:
        why += f"; studied with {now[0].choices[0]}, the one flavour that reproduces {c.label}"
    elif offered:
        why += f"; {len(offered)} computable completion(s) wait for your choice (below)"
    elif computable:
        flavours = sorted({x.split(":")[1].split("(")[0].strip() for o in computable for x in o.choices
                           if x.startswith("one flavour")})
        why += (f"; computable with an explicit choice ({len(computable)} completion(s)"
                + (f": flavours {', '.join(flavours)}" if flavours else "") + "), but none has nucleon couplings at "
                f"{c.mass_gev:g} GeV proportional to {c.label}'s (one flavour fixes the proton-to-neutron ratio)")
    if mixing_choice(str(error)):
        why += f"; to compute it, {mixing_choice(str(error))}"
    return [o.spec for o in now], offered, why


def _offer(folder: Path, result_request, c: Candidate, proposal: str, offered: list, options: dict | None = None,
           global_z: float | None = None) -> list[CompletionChoice]:
    """Each completion that needs a choice, written as a typed model file and as the request that studies it as a
    child of the candidate is studied (``_child_request``: its parent's halo snapshot, searches, records, profile,
    significance and the promotion's options), with the command that runs that request as saved (``adroit single-idea
    --request``). The auditor's HB recheck, HC-02, 2026-11-11: the command had named the model, the search and the masses
    alone, so a study of a parent at SHM++ ran at the current default halo, and its other settings at their defaults.

    Each offer's files are its own: named by the completion and the SHA-256 of the request it saves, never written
    over another's (``_written_once``), and its command names that SHA-256 (``--request-sha256``), so that it runs
    the request offered or refuses. The auditor's HC recheck (HD-02, 2026-11-12) had found a second candidate's offer of the
    same completion written over the first's, whose command then studied the second candidate's masses."""
    import hashlib
    import shlex
    import yaml
    out = []
    for o in offered:
        name = slug(f"{o.spec.name}_{'_'.join(x.split(':')[1].split('(')[0] for x in o.choices if x.startswith('one flavour'))}")
        data = _child_request(result_request, c, o.spec, options or {}, global_z).model_dump_json(indent=1).encode()
        digest = hashlib.sha256(data).hexdigest()
        path = folder / "choices" / f"{name or slug(o.spec.name)}_{digest[:12]}.yaml"
        request = path.with_suffix(".request.json")
        _written_once(path, yaml.safe_dump(o.spec.model_dump(mode="json"), sort_keys=False,
                                           allow_unicode=True).encode())
        _written_once(request, data)
        out.append(CompletionChoice(label=c.label, proposal=proposal, model=o.spec.name, choices=o.choices,
                                    file=str(path), request=str(request), request_sha256=digest,
                                    command=f"adroit single-idea --request {shlex.quote(str(request))} "
                                            f"--request-sha256 {digest}"))
    return out


def _written_once(path: Path, data: bytes) -> None:
    """``data`` as ``path``, written whole; where the file is there already, it must hold the same bytes (the same
    offer made again), else ``ValueError``: an offer is never written over another (HD-02)."""
    from adroit.core.durable import write_atomic
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"{path} holds another offer; it is not written over")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(path, data)


def _proposals(parent: Path, c: Candidate, llm, n: int, result_request=None, options: dict | None = None,
               global_z: float | None = None
               ) -> tuple[Path, list[ModelSpec], dict[str, str], float, list[CompletionChoice]]:
    """The model builder's completions of a card, as an idea study; the computable ones, why the rest are not, and
    computable completions of refused proposals that wait for the researcher's choice (``completions``)."""
    from adroit.orchestrator import ideas
    card = registry.card(c.card_id)
    text = UV_PROMPT.format(name=card.name, form=card.interaction, mass=c.mass_gev,
                            isospin=ISOSPIN_TEXT.get(c.isospin, "with the card's own nucleon couplings"))
    before = getattr(llm, "spent", 0.0)
    result = ideas.run(ideas.IdeaRequest(text=text, models=n), llm)
    folder = parent / "children" / slug(f"completions_{c.card_id}_{c.label}")      # the candidate's own (HD-02)
    folder.mkdir(parents=True, exist_ok=True)
    import hashlib
    from adroit.core.durable import publishing
    from adroit.evidence.build import incomplete, publish
    content = result.model_dump_json(indent=1).encode()
    cost = getattr(llm, "spent", 0.0) - before
    # its parts, its record and its choices under one hold (DE-02, DF-01), marked from the first to the last (HE-02)
    with publishing(folder) as held, incomplete(folder / "result.json", hashlib.sha256(content).hexdigest()):
        publish(folder / "result.json", content, result, lambda envelope: ideas.report(result), evidence=False,
                claim=held, marked=True)  # M3
        studies.record(folder, "idea", f"completions of {c.card_id} ({c.label})", inputs={"text": text},
                       steps=["the model builder's proposals", "DM12's general Lagrangian", "DM12's audit"],
                       cost_usd=cost, parent=parent, result_sha256=hashlib.sha256(content).hexdigest(), claim=held)
        ready, why, offered = [], {}, []
        for d in result.dropped:                     # a proposal not offered, with why (the owner, 2026-11-21)
            name, _, reason = d.partition(": ")
            why.setdefault(name, f"proposed by the model builder; {reason}")
        for m in result.models:
            spec = m.general or m.spec
            try:
                classify(spec)
            except Unsupported as error:
                now, waiting, why[m.spec.name] = _completed(spec, error, c)
                ready += now
                if waiting and result_request is not None:
                    offered += _offer(folder, result_request, c, m.spec.name, waiting, options, global_z)
                continue
            if not _reproduces(spec, c):                 # mini audit: a proposal must give the candidate's interaction
                why[m.spec.name] = ("proposed by the model builder; its nucleon-level interaction at "
                                    f"{c.mass_gev:g} GeV is not proportional to {c.label}'s")
                continue
            ready.append(spec)
    return folder, ready, why, cost, offered


def _reproduces(spec: ModelSpec, c: Candidate) -> bool:
    """Whether a model's nucleon couplings at the candidate's mass reproduce the candidate's: each of the card's
    operators present with the same proton/neutron ratio, up to one common factor. Velocity- or
    momentum-suppressed operators a full model adds beside them are allowed; an extra O₁ or O₄ is not."""
    from adroit.core.dm_state import DarkMatterParticle
    from adroit.orchestrator import user_models
    try:
        own = user_models.interaction(spec, c.mass_gev)
        particle = DarkMatterParticle(mass_gev=c.mass_gev, mass_splitting_kev=c.splitting_kev)
        target = registry.resolve(c.card_id, particle, c.values or registry.isospin_values(c.card_id, c.isospin or "s", 1.0))
    except (Unsupported, KeyError, ValueError):
        return False
    mine, theirs = _contact_couplings(own), _contact_couplings(target)
    # the card's operators must all be there; an extra O₁ or O₄ (unsuppressed) would dominate the rate
    if not theirs or not set(theirs) <= set(mine) or (set(mine) - set(theirs)) & {1, 4}:
        return False
    (operator, reference), *_ = theirs.items()
    scale = (mine[operator][0] / reference[0]) if reference[0] else (mine[operator][1] / reference[1])
    return scale != 0 and all(np.allclose(np.array(mine[o]), scale * np.array(v), rtol=1e-6, atol=0) for o, v in theirs.items())


def _contact_couplings(interaction) -> dict[int, tuple[float, float]]:
    """(c_p, c_n) of each operator's contact (q⁰) terms, summed."""
    out: dict[int, list[float]] = {}
    for coefficient in interaction.coefficients:
        if coefficient.q_power == 0 and (coefficient.proton or coefficient.neutron):
            row = out.setdefault(coefficient.operator, [0.0, 0.0])
            row[0] += coefficient.proton
            row[1] += coefficient.neutron
    return {o: (p, n) for o, (p, n) in out.items() if p or n}


def refuse_halo(result: SignalResult, options: dict) -> None:
    """The halo its children would be calculated at (its parent's: ``_child_request``) refused as their fresh run
    refuses it (``single_idea.refuse_halo``), with the parent's searches, its profile's and the native joint fit if
    asked, before a promotion records, requests or calculates anything (the auditor's HB recheck, HC-03, 2026-11-11: a
    promotion whose parent held an SHM++ snapshot this version cannot calculate had sent the model builder its request,
    and each child would have been refused only after it). The halo is the children's as their run states it, and their
    profile's private inputs are refused at it as their fit refuses them (the auditor's HC recheck, HD-03, 2026-11-12)."""
    from adroit.parameter_space import halo_region
    request = result.request
    profile = None
    if request.experimental_profile:
        from adroit.library.experimental_profiles import load
        profile = load(request.experimental_profile)
    nulls = [*request.null_modules, *(profile.null_modules if profile else [])]
    halo = halo_region.stated(request.halo)           # as the children's run states it (``single_idea.prepared``)
    single_idea.refuse_halo(halo, request.experiment, nulls, bool(options.get("native_joint")))
    single_idea.refuse_profile(halo, profile)         # its private inputs at that halo, as their fit refuses (HD-03)


class ParentChanged(ValueError):
    """The parent's result is not the version its candidates were selected from."""


def parent_result(parent: Path, expected_sha256: str = "") -> tuple[SignalResult, str]:
    """The parent's Path 2 result, read once, and the SHA-256 of its bytes; with ``expected_sha256`` (the version the
    candidates were selected from, as the study page showed it), ``ParentChanged`` for another. The auditor's CX recheck,
    CY-02 (2026-11-01): class 0 selected on a page showing A, with B published before the click, had been promoted as
    B's class 0, a candidate never shown."""
    from adroit.evidence.version import Changed, Token, resolve
    try:                                    # the parent's result, its version read once (``evidence.version``)
        found = resolve(Token(str(Path(parent) / "result.json"), result=expected_sha256), evidence=False)
    except Changed as changed:
        raise ParentChanged(f"the parent study's result has changed since its candidates were selected (selected from "
                            f"{expected_sha256[:12]}…, now {changed.found[:12]}…); nothing was promoted: reopen the study "
                            "and choose again") from None
    if found.content is None:
        raise FileNotFoundError(f"{found.path}: no saved result") if found.result_state == "absent" else \
            OSError(f"{found.path}: its result cannot be read")
    return SignalResult.model_validate_json(found.content), found.result_sha256


@timed
def promote(parent: Path, which: list[str], options: dict | None = None, llm=None, uv_models: int = 3,
            fetch=None, parent_sha256: str = "") -> Promotion:
    """Promote candidates (labels, or ``class:N``) of the Path 2 run in ``parent`` to studies: of its result read once
    (``parent_result``), and with ``parent_sha256``, only of that version."""
    parent = Path(parent).resolve()
    result, digest = parent_result(parent, parent_sha256)
    refuse_halo(result, options or {})               # before anything is recorded, requested or calculated (HC-03)
    if not (parent / studies.FILE).exists():
        studies.record(parent, "signal", f"Signal best fits: {result.request.experiment}", result_sha256=digest)
    include = (options or {}).get('include_excluded', False)
    labels = [label for w in which for label in labels_of(result, w, include)]
    pool, options = candidates_of(result), options or {}
    out = Promotion(parent=str(parent), labels=labels, parent_sha256=digest)
    for w in which:                                       # say which class members were left out (audit minor)
        if w.startswith("class:") and not include:
            out.dropped.update({label: "its fitted point is excluded (--include-excluded to follow it up)"
                                for label in sorted(set(labels_of(result, w, True)) - set(labels))})
    done: dict[str, tuple[str, float, float]] = {}         # model → (the candidate it was built for, its mass window)
    span = options.get("span", 4.0)
    for label in labels:
        c = pool[label]
        refusal = completion_refusal(c)
        elastic_isovector = c.isospin == "v" and not c.splitting_kev and not c.values
        builder = llm is not None and bool(c.card_id) and (not refusal or elastic_isovector)
        candidates = models_for(result, c)
        # a model already studied counts only if that study's mass window holds this candidate's mass
        found = [(o, s) for o, s in candidates
                 if s.name not in done or not done[s.name][1] <= c.mass_gev <= done[s.name][2]]
        if refusal and not builder:
            out.undetermined[label] = refusal + ("; the model builder can propose isovector completions"
                                                 if elastic_isovector else "") + (
                "; the model builder was not asked: it is asked only for an elastic candidate with the card's own "
                "couplings" if llm is not None else "")       # said, where a budget was given (the owner, 2026-11-19)
        elif not found and candidates:
            out.undetermined[label] = ("its completions were already studied for "
                                       + ", ".join(sorted({done[s.name][0] for _, s in candidates}))
                                       + f", whose mass window holds {c.mass_gev:g} GeV")
        elif not found and not builder:
            out.undetermined[label] = ("no computable model produces this card at tree level (a structure outside "
                                       "DM13's classes); the model builder can propose some")
        for origin, spec in found:
            done[spec.name] = (label, c.mass_gev / span, c.mass_gev * span)
            out.children.append(_study(parent, result, c, origin, spec, options, fetch))
        if builder:
            folder, ready, why, cost, offered = _proposals(parent, c, llm, uv_models, result.request, options,
                                                           result.global_z)
            out.undetermined.update(why)
            out.choices += offered
            out.cost_usd += cost
            for spec in ready:
                out.children.append(_study(parent, result, c, "model builder", spec, options, fetch, under=folder))
    account = getattr(llm, "account", None)
    if account is not None:                  # the builder's open or uncertain reservations, as its account holds them
        out.reserved_usd = sum(v for _, v in account.reservations.values())
    return out




@dated_report
def report(p: Promotion) -> str:
    """The promotion's summary in Markdown."""
    from adroit.orchestrator.accounting import live_text
    lines = [f"# Promotion of {', '.join(p.labels)}", "",
             f"Parent: `{Path(p.parent).name}`; " + (f"the model builder {live_text(p.cost_usd, p.reserved_usd)}"
                                                     if p.cost_usd or p.reserved_usd
                                                     else "no settled or reserved dollars recorded") + ".", "",
             *([f"Promoted from the parent's result as read: SHA-256 `{p.parent_sha256}`.", ""] if p.parent_sha256
               else []),
             "| candidate | model | origin | verdict | study |", "|---|---|---|---|---|"]
    lines += [f"| {c.label} | {c.model} | {c.origin} | {single_idea.LEVELS.get(c.level, c.level)} | "
              f"`{Path(c.folder).relative_to(p.parent)}` |" for c in p.children]
    if p.undetermined:
        lines += ["", "Without a study:", ""] + [f"- {k}: {v}" for k, v in p.undetermined.items()]
    if p.dropped:
        lines += ["", "Left out of the class:", ""] + [f"- {k}: {v}" for k, v in p.dropped.items()]
    if p.choices:
        lines += ["", "## Computable completions that need your choice", "",
                  "Each is a builder's proposal made computable by the choices listed; none is studied until you "
                  "choose it.", ""]
        for x in p.choices:
            lines += [f"- {x.label}, from {x.proposal}: `{Path(x.file).relative_to(p.parent)}`",
                      *(f"  - {choice}" for choice in x.choices), f"  - to study it: `{x.command}`"]
    return "\n".join(lines) + "\n"
