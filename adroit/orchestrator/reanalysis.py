"""Reopen immutable inputs and launch a reviewed fresh child analysis."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any,TYPE_CHECKING
from pydantic import JsonValue,ValidationError
from adroit.core.reanalysis import ReanalysisDraft
from adroit.core.evidence import content_hash
from adroit.core.chronology import utc_now
from adroit.core.checkpoint import atomic_json,run_lock
from adroit.library.personal import Catalog,DIGEST
if TYPE_CHECKING:
    from adroit.orchestrator.track1 import Track1Request
    from adroit.orchestrator.signal import SignalRequest
    from adroit.orchestrator.single_idea import SingleIdeaRequest

def _converted_halo(kind: str, request: dict, target: str) -> dict:
    """The saved study's halo carried into a draft for another track, where the target has it (halo phase 1; before it,
    a converted draft dropped the halo and took the setting when run):
    - a fixed common benchmark is carried as it is, to either track;
    - into Track 1: an Explain a signal study's region or published halos (its plane's) as they are; a Track 2 run's
      each-search's-published halos, or a study saved before the choice existed, as "published";
    - into Track 2: no field (each search's published halo), the only treatment it has besides a benchmark; a Track 1
      or Explain a signal region has no Track 2 form, so the draft names none and the person edits it if wanted.
    The draft shows the halo it will run with, editable, before it is run."""
    value = request.get('halo')
    if isinstance(value, dict) and value.get('treatment') == 'benchmark':
        return {'halo': value}
    if target != 'track1':
        return {}
    if kind == 'single_idea' and value is not None:
        return {'halo': value}
    return {'halo': 'published'}



def refused(error: ValidationError) -> str:
    """An edited request's refusal for people: each reason its validators gave, by the field it concerns. Where a field
    may take several forms (a union), the forms it was not are left out, and the reason its own form's validator gave
    kept."""
    def branch(part) -> bool:                # a union's form, named in the error's location ('FixedHalo', "literal[…]")
        return not isinstance(part, int) and not (str(part).isidentifier() and not str(part)[:1].isupper())
    fields: dict = {}
    for e in error.errors(include_url=False, include_input=False):
        fields.setdefault(e['loc'][:1], []).append(e)
    kept = [e for errors in fields.values() for e in [e for e in errors if e['type'] == 'value_error']
            or [e for e in errors if not any(branch(x) for x in e['loc'])] or errors]
    return 'the edited request is refused: ' + '; '.join(
        f"{'.'.join(str(x) for x in e['loc'] if not branch(x))}: {e['msg'].removeprefix('Value error, ')}" for e in kept)

class Reanalysis:
    """Manage pinned reanalysis drafts and reviewed fresh child calculations."""
    def __init__(self,catalog:Catalog|None=None)->None:
        self.catalog=catalog or Catalog()
        self.root=self.catalog.root/'reanalysis'

    def _source(self,source:str,token=None)->tuple[str,str,str,str,dict[str,JsonValue]]:
        """(kind, its identity, its evidence's, its workflow, its request) of a source: a catalog model, a confirmed
        anomaly, or a saved study, its version read once (``evidence.version``): with ``token``, the version a page
        showed, each part it names checked (``evidence.version.Changed``)."""
        if source.startswith('catalog:'):
            r=self.catalog.load(source)
            from adroit.orchestrator.track1 import Track1Request
            req=Track1Request(spec=r.spec,catalog_reference=r.reference,approved_model_sha256=r.model_sha256)
            return 'catalog',r.revision_id,'','track1',req.model_dump(mode='json')
        if source.startswith(('anomaly:','private-search:')):
            from adroit.experiments.registry import load_module
            from adroit.orchestrator.signal import SignalRequest
            module=load_module(source)
            body=module.evidence()
            return 'anomaly',content_hash(body),'','signal',SignalRequest(experiment=source).model_dump(mode='json')
        from adroit.evidence.version import Token,resolve
        path=Path(source)
        if path.is_dir():
            path=path/'result.json'
        if path.is_symlink() or not path.is_file() or path.name.startswith('.env'):
            raise ValueError('select a regular saved result, catalog model or confirmed anomaly')
        # refuses a tampered or unreadable envelope; the request and both digests are of one version (CX-02)
        found=resolve(Token(str(path),**({} if token is None else {'result':token.result,'evidence':token.evidence})))
        snapshot=found.saved()
        kind,result=snapshot.workflow,snapshot.result
        if kind not in ('track1','signal','single_idea'):
            raise ValueError('this saved workflow has no supported reanalysis request')
        return ('study',found.result_sha256,snapshot.sidecar_sha256,kind,result.request.model_dump(mode='json'))

    def _held(self,draft:ReanalysisDraft)->None:
        """``ValueError`` where a draft's saved source is no longer the version it was drafted from: its result and its
        evidence, as the draft records them (``evidence.version.Changed``)."""
        if draft.source_kind!='study':
            self._source(draft.source)
            return
        from adroit.evidence.build import NO_EVIDENCE
        from adroit.evidence.version import Changed,Token
        try:
            self._source(draft.source,Token(draft.source,draft.source_sha256,
                                            draft.source_evidence_sha256 or NO_EVIDENCE))
        except Changed as changed:
            raise ValueError(f"the parent study's {changed.part} has changed since reopening") from None

    def _save(self,**body:Any)->ReanalysisDraft:
        draft=ReanalysisDraft(draft_id=content_hash(body),**body)
        with run_lock(self.root):
            atomic_json(self.root/'drafts'/f'{draft.draft_id}.json',draft.model_dump(mode='json'))
        return draft

    def load(self,reference:str)->ReanalysisDraft:
        """Read a pinned draft and reject edits to its stored content."""
        key=reference.removeprefix('reanalysis:')
        if not reference.startswith('reanalysis:') or not DIGEST.fullmatch(key):
            raise ValueError('pinned reanalysis draft required')
        path=self.root/'drafts'/f'{key}.json'
        if path.is_symlink():
            raise ValueError('reanalysis draft must not be a symlink')
        raw=json.loads(path.read_text())
        if raw['draft_id']!=key or content_hash({k:v for k,v in raw.items() if k!='draft_id'})!=key:
            raise ValueError('reanalysis draft modified')
        return ReanalysisDraft.model_validate(raw)

    def _convert(self,kind:str,request:dict[str,JsonValue],target:str,index:int)->dict[str,JsonValue]:
        from adroit.orchestrator.track1 import Track1Request
        from adroit.orchestrator.signal import SignalRequest,UserModel
        if target==kind:
            return request
        if target not in ('track1','signal'):
            raise ValueError('cross-track reanalysis supports Track1 or signal targets')
        halo=_converted_halo(kind,request,target)
        if kind=='track1':
            model=UserModel(spec=request['spec'],catalog_reference=request.get('catalog_reference',''))
            return SignalRequest(experiment='',user_models=[model],experimental_profile=request.get('experimental_profile',''),**halo).model_dump(mode='json')
        models=request.get('user_models',[]) if kind=='signal' else [{'spec':request['spec'],'catalog_reference':request.get('catalog_reference','')}]
        if not 0<=index<len(models):
            raise ValueError('select an exact saved physical model; a bare NR card is not a unique completion')
        model=models[index]
        if target=='track1':
            return Track1Request(spec=model['spec'],catalog_reference=model.get('catalog_reference',''),
            experimental_profile=request.get('experimental_profile',''),**halo).model_dump(mode='json')
        if target=='signal':
            return SignalRequest(experiment=request['experiment'],user_models=[UserModel(**model)],
            experimental_profile=request.get('experimental_profile',''),null_modules=request.get('null_modules',[]),**halo).model_dump(mode='json')
        raise ValueError('cross-track reanalysis supports Track1 or signal targets')

    def open(self,source:str,target:str='',model_index:int=0,token=None)->ReanalysisDraft:
        """Snapshot saved scientific inputs, optionally selecting another track; with ``token`` (the version of a saved
        study its page showed, ``evidence.version.Token``: its result's digest and its evidence's identity), only that
        version (the auditor's CX recheck, CY-03, 2026-11-01: a continuation from a page carries the identity of the result
        it showed; its version-identity audit, VI-03, 2026-11-03: evidence replaced beside the same result had been
        drafted from)."""
        from adroit.evidence.version import Changed
        try:
            kind,sha,evidence_sha,workflow,original=self._source(source,token)
        except Changed as changed:
            if changed.part=='result':
                raise ValueError("this study's result has changed since its page was opened (shown: "
                                 f"{changed.expected[:12]}…, now {changed.found[:12]}…); nothing was drafted: reopen "
                                 "the study") from None
            raise ValueError("this study's evidence has changed since its page was opened (its result is the same); "
                             "nothing was drafted: reopen the study") from None
        target=target or workflow
        if target not in ('track1','signal','single_idea'):
            raise ValueError('choose track1, signal or the original single_idea workflow')
        req=self._convert(workflow,original,target,model_index)
        if kind=='study':
            path=Path(source)
            source=str((path/'result.json' if path.is_dir() else path).resolve())
        return self._save(created_at=utc_now(),parent_draft='',source=source,source_kind=kind,source_sha256=sha,
            source_evidence_sha256=evidence_sha,workflow=target,original_request=original,request=req,model_index=model_index)

    def revise(self,reference:str,request:dict[str,JsonValue])->ReanalysisDraft:
        """Validate edited inputs and retain a new linked immutable draft."""
        old=self.load(reference)
        from adroit.evidence.results import result_type
        try:
            req=result_type(old.workflow).model_fields['request'].annotation.model_validate(request)
        except ValidationError as error:     # refused in its own words, not with the input echoed: since a halo snapshot
            raise ValueError(refused(error)) from None    # not of its family's form is refused as read (HB-01)
        return self._save(**{**old.model_dump(mode='json',exclude={'draft_id'}),'created_at':utc_now(),
            'parent_draft':old.draft_id,'request':req.model_dump(mode='json')})

    def choose_model(self,reference:str,model_reference:str,index:int=0)->ReanalysisDraft:
        """Replace one exact model slot with a selected approved revision."""
        draft=self.load(reference)
        revision=self.catalog.load(model_reference)
        req=dict(draft.request)
        if draft.workflow in ('track1','single_idea'):
            req.update(spec=revision.spec.model_dump(mode='json'),catalog_reference=revision.reference)
            if draft.workflow=='track1':
                req.update(model_class=None,fixed=None,approved_model_sha256='',reviewed_scan_sha256='')
            else:
                req['derivation']=revision.derivation.model_dump(mode='json') if revision.derivation else None
        else:
            if not 0<=index<len(req['user_models']):
                raise ValueError('select an existing model slot')
            models=list(req['user_models'])
            previous=dict(models[index])
            previous.update(spec=revision.spec.model_dump(mode='json'),catalog_reference=revision.reference,
                derivation=revision.derivation.model_dump(mode='json') if revision.derivation else None)
            models[index]=previous
            req['user_models']=models
        return self.revise(reference,req)

    def preview(self,reference:str)->dict[str,Any]:
        """Report input differences, mapping and blockers without calculation."""
        draft=self.load(reference)
        blockers=[]
        mapping={}
        from adroit.orchestrator.model_approval import _changes
        try:
            self._held(draft)
            from adroit.evidence.results import result_type
            request=result_type(draft.workflow).model_fields['request'].annotation.model_validate(draft.request)
            from adroit.parameter_space import halo_region
            halo_region.checked(getattr(request,'halo',None))    # its halo snapshot, refused before any calculation
            models=request.user_models if draft.workflow=='signal' else [request]
            for model in models:
                from adroit.library.personal import support
                from adroit.model_building.audit import audit
                if not audit(model.spec).valid:
                    raise ValueError('canonical model structural checks failed')
                current=support(model.spec,getattr(model,'derivation',None))
                if not current['numerically_declared'] or not current['track1_engine' if draft.workflow=='track1' else 'track2_engine']:
                    raise ValueError('selected model lacks supported numerical parameters/backend mapping: '+str(current))
                if model.catalog_reference:
                    self.catalog.verify_calculation(model.catalog_reference,model.spec,'track1' if draft.workflow=='track1' else 'track2',getattr(model,'derivation',None))
            if draft.workflow=='track1':
                from adroit.parameter_space.classify import classify
                from adroit.parameter_space.scan_setup import model_relations,preview
                cls,point,notes=classify(request.spec)
                if request.model_class is not None and request.model_class!=cls or request.fixed is not None and request.fixed!=point:
                    raise ValueError('engine/fixed overrides differ from the reviewed model')
                mapping=preview(cls,point,request.x,request.y,request.mediator_ratio,notes=notes,
                                coupling_relations=model_relations(request.spec,"",request.x,request.y)).model_dump(mode='json')
            else:
                from adroit.experiments.registry import load_module
                if not request.experiment:
                    raise ValueError('select the signal/anomaly for this new Track2 analysis')
                module=load_module(request.experiment)
                if getattr(module,'verified',True) is False and not request.unverified_records and not getattr(module,'interpretation_confirmed',False):
                    raise ValueError('experimental input needs source review or explicit confirmed exploratory interpretation')
            if request.experimental_profile:
                from adroit.library.experimental_profiles import apply_signal,apply_track1
                apply_track1(request) if draft.workflow=='track1' else apply_signal(request)
        except (ValueError,OSError,KeyError,RuntimeError) as error:
            blockers.append(str(error))
        return {'reference':reference,'source':draft.source,'source_sha256':draft.source_sha256,
            'source_evidence_sha256':draft.source_evidence_sha256,'workflow':draft.workflow,'request':draft.request,
            'differences':_changes(draft.original_request,draft.request),'mapping':mapping,'blockers':blockers,
            'review_sha256':content_hash({'draft':draft.model_dump(mode='json'),'mapping':mapping,'blockers':blockers}),
            'reuse_policy':'Fresh child calculation. No old checkpoint reuse; only exact current M38 point evidence may be selected explicitly.'}

    def _catalogue_models(self,request:Track1Request|SignalRequest|SingleIdeaRequest,draft:ReanalysisDraft,
                         reviewer:str)->Track1Request|SignalRequest|SingleIdeaRequest:
        """Store reviewed inline models as linked private revisions before calculation."""
        from adroit.orchestrator.model_approval import SCHEMA_VERSION,ModelApproval,model_identity
        from adroit.model_building.tex import render
        models=request.user_models if draft.workflow=='signal' else [request]
        original=draft.original_request.get('user_models',[]) or [draft.original_request]
        updated=[]
        for index,model in enumerate(models):
            if model.catalog_reference:
                updated.append(model)
                continue
            old=original[min(index if draft.workflow=='signal' else draft.model_index,len(original)-1)]
            parent=old.get('catalog_reference','')
            sha=model_identity(model.spec)
            approval=ModelApproval(model_sha256=sha,source_model_sha256=sha,choice='supplied',schema_version=SCHEMA_VERSION)
            r=self.catalog.save(model.spec,approval,parent=parent,tex=render(model.spec),derivation=getattr(model,'derivation',None),
                provenance={'origin':'explicit reviewed reanalysis model','reanalysis':draft.reference,'source':draft.source,
                    'source_sha256':draft.source_sha256,'reviewer':reviewer})
            updated.append(model.model_copy(update={'catalog_reference':r.reference}))
        return request.model_copy(update={'user_models':updated}) if draft.workflow=='signal' else updated[0]

    def run(self,reference:str,out:Path,expected_hash:str,*,confirmed:bool,reviewer:str)->tuple[Path,str]:
        """Execute a reviewed draft in a fresh exportable child study. The child's folder is the run's from its start to
        its return: its publication lock (``durable.publishing``) taken at once, or refused where another process holds
        it (another reanalysis, say), and held through the calculation, the publication and the check of what was
        published, so that of two reanalyses into one folder exactly one runs, and no other writer of ADROIT's writes
        there meanwhile (the auditor's DD recheck, DE-02, 2026-11-05: two had both succeeded, the first's result lost)."""
        from contextlib import ExitStack
        from adroit.core.durable import Busy,publishing
        draft=self.load(reference)
        review=self.preview(reference)
        if not confirmed or not reviewer.strip():
            raise ValueError('explicit review of model, source/profile and numerical changes is required')
        if review['review_sha256']!=expected_hash or review['blockers']:
            raise ValueError('review changed or calculation blocked: '+str(review['blockers']))
        out=Path(out).resolve()
        parent=Path(draft.source).parent if draft.source_kind=='study' else None
        from adroit.orchestrator.runs import fresh
        if not fresh(out):                          # before anything is made there; again once it is held
            raise ValueError('reanalysis requires a fresh empty output folder')
        if parent and (out==parent or not out.is_relative_to(parent.resolve())):
            raise ValueError('a reanalysis child must be inside its source study so the complete study can be exported')
        with ExitStack() as stack:
            try:
                claim=stack.enter_context(publishing(out,wait=0))
            except Busy:
                raise ValueError('another process is writing into this folder (another reanalysis, say): a reanalysis '
                                 'needs a fresh folder of its own; choose a new one') from None
            return self._run(draft,out,parent,expected_hash,reviewer,claim)

    def _run(self,draft:ReanalysisDraft,out:Path,parent:Path|None,expected_hash:str,reviewer:str,
             claim)->tuple[Path,str]:
        """``run``'s calculation and publication, its child's folder held (``claim``)."""
        from adroit.orchestrator.runs import fresh
        if not fresh(out):                          # a workbench job's own record and log aside
            raise ValueError('reanalysis requires a fresh empty output folder')
        from adroit.evidence.results import result_type
        request=result_type(draft.workflow).model_fields['request'].annotation.model_validate(draft.request)
        request=self._catalogue_models(request,draft,reviewer.strip())
        from adroit.orchestrator import runs
        lineage:dict={}
        beside:dict={}

        def certify(_child_sha256:str)->dict:
            # the calculation done, nothing of it written yet: no publication in its folder (none of ADROIT's writers
            # writes there while it is held: a process outside them may have), its parent checked unchanged, and its
            # lineage put into the evidence it is first published with (the auditor's version-handle audit, DD-01, 2026-11-04:
            # added after publication, it had gone to whatever the folder then held)
            there=[name for name in PUBLISHED if (out/name).exists()]
            if there:
                raise ValueError(f"while it calculated, {', '.join(there)} appeared in the new study's folder: another "
                                 "process, outside ADROIT's writers, published there. Nothing of this reanalysis was "
                                 "written, and the folder is as that process left it. Run it again into a new folder")
            try:
                self._held(draft)
            except ValueError:
                raise ValueError('parent input changed during calculation; the new result cannot certify this '
                                 'lineage') from None
            lineage.update({'draft':draft.model_dump(mode='json'),'review_sha256':expected_hash,
                'reviewer':reviewer.strip(),'reviewed_at':utc_now(),'source_result_sha256':draft.source_sha256,
                'source_evidence_sha256':draft.source_evidence_sha256,'fresh_run':True})
            beside['reanalysis.json']=lineage       # written once its parts are, before its record (DE-02)
            return {'reanalysis_lineage':lineage}
        published:dict={}
        from adroit.evidence.build import Replaced
        try:
            if draft.workflow=='track1':
                from adroit.orchestrator.model_approval import model_identity
                from adroit.parameter_space.classify import classify
                from adroit.parameter_space.scan_setup import model_relations,preview,setup_identity
                cls,point,notes=classify(request.spec)
                setup=preview(cls,point,request.x,request.y,request.mediator_ratio,notes=notes,
                    coupling_relations=model_relations(request.spec,"",request.x,request.y))
                request=request.model_copy(update={'approved_model_sha256':model_identity(request.spec),
                    'reviewed_scan_sha256':setup_identity(request.spec,cls,point,setup)})
                folder,report=runs.track1(request,out,parent=parent,certify=certify,published=published,claim=claim,
                                          beside=beside)
            elif draft.workflow=='single_idea':
                folder,report=runs.single_idea(request,out,parent=parent,certify=certify,published=published,
                                               claim=claim,beside=beside)
            else:
                from adroit.orchestrator import signal
                from adroit.evidence.runtime import capture_request
                if request.experimental_profile:
                    from adroit.library.experimental_profiles import apply_signal
                    request=apply_signal(request)
                context=capture_request(request)
                result=signal.run(request)
                out.mkdir(parents=True,exist_ok=True)
                report=runs._write(out,result,signal.report(result),'signal',f'Reanalysis: {request.experiment}',
                    parent=parent,evidence_context=context,certify=certify,published=published,claim=claim,
                    beside=beside)
                folder=out
        except Replaced as replaced:
            wrote=', '.join(replaced.wrote or ('result','evidence','report'))
            raise ValueError("the new study's result was replaced by another process while it was published, so "
                             f"nothing certifies what its folder holds: this reanalysis had written its {wrote}, and "
                             "wrote nothing more. Run it again into a new folder") from None
        if 'token' not in published:
            raise ValueError('its writer recorded no publication: nothing certifies what the new study\'s folder '
                             'holds')
        _still(published['token'])
        return folder,report


PART_WORDS={'result':'result','evidence':'evidence','presentation':'report','record':'record'}
PUBLISHED=('result.json','result.evidence.json','report.md','study.json')     # a publication's parts, by name


def _still(token)->None:
    """The child as its writer published it, still in its folder (``token``: ``runs._write``'s): else ``ValueError``
    naming the part another process replaced after the publication. Nothing is written either way: its lineage is in
    the evidence it was published with (the auditor's version-handle audit, DD-01). Checked with the folder still held
    (``run``), so that another process that changed it is outside ADROIT's writers (DE-02)."""
    from adroit.evidence.version import Changed,resolve
    try:
        resolve(token,presentation=True)
    except Changed as changed:
        raise ValueError(f"the new study's {PART_WORDS[changed.part]} was replaced by another process, outside "
                         "ADROIT's writers, after it was published: this reanalysis does not describe what its folder "
                         "now holds, and wrote nothing after its publication. Run it again into a new "
                         "folder") from None
    except OSError as error:
        raise ValueError(f"the new study, read after it was published, {error}: this reanalysis does not describe "
                         "what its folder now holds. Run it again into a new folder") from None
