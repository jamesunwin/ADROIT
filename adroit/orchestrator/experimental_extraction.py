"""Durable bounded experimental extraction, independent of experiment activation."""
from __future__ import annotations
import json
import math
import re
from pathlib import Path
from typing import Any

from adroit.core.checkpoint import atomic_json,run_lock
from adroit.core.chronology import utc_now
from adroit.core.quotes import contains
from adroit.core.evidence import content_hash
from adroit.core.experimental_input import ExperimentalClaim,ExperimentalDossier
from adroit.core.experimental_extraction import SourceUnit,ExtractionScope,ExtractionStep
from adroit.library.experimental import ExperimentalCatalog
from adroit.library.personal import Catalog
from adroit.orchestrator.model_intake import Intake
from adroit.retrieval.experimental_ingestion import render_page,finite_json


def source_units(catalog: ExperimentalCatalog,reference: str,vision: bool=True) -> list[SourceUnit]:
    """Inventory every source chunk; nothing is silently sent/truncated."""
    revision=catalog.load(reference)
    units=[]
    for asset in revision.ingestions:
        item=catalog.ingestion(asset)
        original=next(a for a in revision.sources if a.sha256==item.source_sha256)
        base=dict(asset_sha256=original.sha256,source_name=original.name)
        if item.kind=='pdf':
            for page in item.pages:
                text=page.text
                for offset in range(0,max(1,len(text)),35000):
                    units.append(SourceUnit(unit_id=f'{original.sha256}:page:{page.page}:part:{offset//35000}',
                        **base,page=page.page,text=text[offset:offset+35000],vision=vision or page.status!='text_extracted',
                        image=page.preview if vision or page.status!='text_extracted' else None,bounds=page.media_box,
                        notes=['Text positions/figure interpretation require original-page checking.']))
        elif item.table:
            for low in range(0,len(item.table.rows),40):
                rows=item.table.rows[low:low+40]
                text=json.dumps({'columns':item.table.columns,'first_data_row':low+1,'rows':rows},ensure_ascii=False)
                if len(text)>45000:
                    raise ValueError('table chunk too wide; split the selected table')
                units.append(SourceUnit(unit_id=f'{original.sha256}:rows:{low+1}-{low+len(rows)}',**base,
                    row_low=low+1,row_high=low+len(rows),text=text))
        elif item.kind=='image':
            units.append(SourceUnit(unit_id=original.sha256+':image',**base,image=original,vision=True))
        else:
            text=catalog.read_asset(original).decode('utf-8-sig')       # one checked read (NA15-08)
            for offset in range(0,max(1,len(text)),35000):
                units.append(SourceUnit(unit_id=f'{original.sha256}:text:{offset//35000}',**base,text=text[offset:offset+35000]))
    if len(units)>2400:
        raise ValueError('source inventory exceeds 2400 units; split this study')
    return units


def batches(units: list[SourceUnit]) -> list[list[str]]:
    """Partition explicit units into bounded requests; no unread content disappears."""
    result=[]
    batch=[]
    size=images=0
    for unit in units:
        count=int(unit.vision)
        if batch and (size+len(unit.text)>45000 or images+count>4 or len(batch)>=12):
            result.append(batch)
            batch=[]
            size=images=0
        batch.append(unit.unit_id)
        size+=len(unit.text)
        images+=count
    if batch:
        result.append(batch)
    return result


def numeric_leaves(value: Any) -> list[float]:
    """Published numerical leaves, including zero; labels are not numbers."""
    if isinstance(value,bool):
        return []
    if isinstance(value,(int,float)):
        return [float(value)]
    if isinstance(value,dict):
        return [n for child in value.values() for n in numeric_leaves(child)]
    if isinstance(value,list):
        return [n for child in value for n in numeric_leaves(child)]
    return []


def _rounding(mantissa: str) -> float:
    """Half a unit in the last printed digit of ``mantissa``, relative to its magnitude ("1.1" gives 0.05/1.1)."""
    digits=mantissa.replace('−','-').lstrip('+-')
    size=abs(float(digits))
    return .5*10.**-(len(digits.split('.')[1]) if '.' in digits else 0)/size if size else math.inf


_MANTISSA = r'[+\-−]?(?:\d+(?:\.\d*)?|\.\d+)'
# an exponent written as one: after "^", inside braces or parentheses, or with a typographic minus (the superscript
# a PDF's text extraction flattens); an ASCII hyphen after "10" may be a range ("bins 10-46") and is not taken as one
_EXPONENT = r'(?:\^\s*[{(]?\s*([+\-−]?\d+)(?:\s*[})])?|[{(]\s*([+\-−]?\d+)\s*[})]|(−\d+))'
_TOKENS = (                         # in priority order: a complete scientific number before its parts (FA-03)
    ('times', re.compile(r'(?<![\w.])(' + _MANTISSA + r')\s*(?:×|\\times|\*)\s*10\s*(?:\^\s*)?[{(]?\s*([+\-−]?\d+)(?:\s*[})])?')),
    ('dropped', re.compile(r'(?<![\w.])(' + _MANTISSA + r')\s+10\s*' + _EXPONENT)),
    ('percent', re.compile(r'(?<![\w.])(\d+(?:\.\d*)?|\.\d+)\s*(?:\\?%|percent\b|per cent\b)', re.I)),
    ('power', re.compile(r'(?<![\w.])10\s*' + _EXPONENT)),
    ('plain', re.compile(r'(?<![\w.])(' + _MANTISSA + r'(?:[eE][+\-−]?\d+)?)')),
)


def _number(text: str) -> float:
    return float(text.replace('−', '-'))


def printed_tokens(text: str) -> list[tuple[float, float, int, int]]:
    """(value, relative rounding, start, end) of each number the text prints, each span read once, a complete
    scientific number before its parts (the focused audit's FA-03: the power inside "2.2 × 10−46" is never also an
    alternative "1 × 10−46", and "10-46" in "bins 10-46" is a range, not a power). The notations: plain or E notation,
    "2.2 × 10−46" (×, \\times or *), a mantissa and power of ten whose "×" the text extraction dropped ("2.2 10−46",
    the exponent written as one), a bare power of ten (rounding ½), and a percentage, which is read as the printed
    number and as its fraction ("95%" is 95 and 0.95). Nothing is computed beyond the notation."""
    taken: list[tuple[int, int]] = []
    out: list[tuple[float, float, int, int]] = []
    for kind, pattern in _TOKENS:
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(start < b and a < end for a, b in taken):
                continue
            groups = match.groups()
            try:
                if kind == 'times':
                    values = [(_number(groups[0]) * 10. ** int(_number(groups[1])), _rounding(groups[0]))]
                elif kind == 'dropped':
                    power = next(g for g in groups[1:] if g)
                    values = [(_number(groups[0]) * 10. ** int(_number(power)), _rounding(groups[0]))]
                elif kind == 'percent':
                    values = [(float(groups[0]), _rounding(groups[0])), (float(groups[0]) / 100, _rounding(groups[0]))]
                elif kind == 'power':
                    power = int(_number(next(g for g in groups if g)))
                    if abs(power) >= 300:
                        continue
                    values = [(10. ** power, .5)]
                else:
                    values = [(_number(groups[0]), _rounding(re.split('[eE]', groups[0].replace('−', '-'))[0]))]
            except (OverflowError, ValueError):
                continue
            taken.append((start, end))
            out += [(v, r, start, end) for v, r in values]
    return sorted(out, key=lambda t: t[2])


def printed_values(text: str) -> list[tuple[float,float]]:
    """(value, relative rounding) of each number a text prints (``printed_tokens``)."""
    return [(value, rounding) for value, rounding, _, _ in printed_tokens(text)]


def printed_numbers(text: str) -> list[float]:
    """The numbers a text prints, in each notation it may use for them (``printed_values``)."""
    return [value for value,_ in printed_values(text)]


def printed_precision(text: str,value: float) -> float | None:
    """The relative rounding with which ``text`` prints ``value`` (the finest, if printed more than once), or None if
    it does not print it."""
    found=[r for v,r in printed_values(text) if abs(v-value)<=1e-12*max(abs(v),abs(value),1e-300)]
    return min(found) if found else None


def convert(claim: ExperimentalClaim) -> ExperimentalClaim:
    """Only explicit fixed unit conversions; never keVee -> keVnr or CL recasts. A conversion is a recipe, not a basis:
    an assumed value stays assumed, its recipe and original units in its note, so that it still needs the researcher's
    acceptance as its canonical twin does; a value read from a source becomes ``converted``, its sources kept. The auditor's
    input-boundary audit (IB-03, 2026-11-10) had found every converted value marked ``converted``: an assumed exposure
    in tonne days lost its required acknowledgement, and one with no locator failed publication."""
    target=claim.requested_unit
    if not target or target==claim.units:
        return claim.model_copy(update={'requested_unit':''})
    factors={('tonne year','kg day'):365250.,('kg year','kg day'):365.25,('tonne day','kg day'):1000.,
             ('eVnr','keVnr'):.001,('GeVnr','keVnr'):1e6,('MeVnr','keVnr'):1000.,('percent','fraction'):.01,
             ('pb','cm2'):1e-36,('fb','cm2'):1e-39}
    if (claim.units,target) not in factors:
        raise ValueError('unsupported/ambiguous conversion '+claim.units+' -> '+target)
    factor=factors[claim.units,target]
    def scale(value):
        if isinstance(value,bool) or not isinstance(value,(int,float,list)):
            raise ValueError('unit conversion needs numerical values')
        return [scale(v) for v in value] if isinstance(value,list) else value*factor
    value=scale(claim.value)
    finite_json(value)
    basis='assumed' if claim.status=='assumed' else 'converted'      # the recipe never changes the basis (IB-03)
    return claim.model_copy(update={'value':value,'units':target,'status':basis,'requested_unit':'',
        'note':claim.note+f' Deterministic conversion from {claim.value!r} {claim.units}, factor {factor}; year=365.25 days.'})


def checked_claim(catalog: ExperimentalCatalog,revision,claim: ExperimentalClaim,units: list[SourceUnit]) -> tuple[ExperimentalClaim,list[str]]:
    """Check selected source positions and numerical copying, not scientific entailment."""
    problems=[]
    original=claim.model_copy(deep=True)
    try:
        if claim.status=='converted':
            raise ValueError('agent returned computed/converted values instead of raw source values')
        if claim.status=='not_reported':
            raise ValueError('absence in a batch is not global nonpublication')
        for loc in claim.sources:
            matches=[u for u in units if u.asset_sha256==loc.asset_sha256 and (loc.page is None or u.page==loc.page)]
            if not matches:
                raise ValueError('claim cites a source/page outside this request')
            if loc.method=='visual' and not any(u.vision for u in matches):
                raise ValueError('visual claim cites a page not viewed')
            if loc.row is not None and not any(u.row_low is not None and u.row_low<=loc.row<=u.row_high for u in matches):
                raise ValueError('claim cites a table row outside this request')
            if loc.excerpt and loc.method!='visual' and not any(contains(u.text,loc.excerpt,case_sensitive=True) for u in matches):
                # JSON-escaped table/text content is checked against original bytes below.
                source=next(a for a in revision.sources if a.sha256==loc.asset_sha256)
                if source.suffix=='.pdf' or not contains(catalog.asset_path(source).read_text(encoding='utf-8-sig'),loc.excerpt,case_sensitive=True):
                    raise ValueError('literal excerpt not present in selected source')
        if claim.status in ('sourced','digitised'):
            if not claim.sources:
                raise ValueError('no evidence locator')
            corpus=' '.join(loc.excerpt for loc in claim.sources if loc.method!='visual')
            for loc in claim.sources:
                if loc.method=='table':
                    if claim.key=='events' and any(term in loc.column.casefold() for term in ('bin','centre','center')):
                        raise ValueError('histogram bin positions are not unbinned event energies')
                    item=next(catalog.ingestion(a) for a in revision.ingestions if catalog.ingestion(a).source_sha256==loc.asset_sha256)
                    if loc.row is None or not loc.column:
                        raise ValueError('machine evidence needs exact row and column')
                    corpus+=' '+item.table.rows[loc.row-1][item.table.columns.index(loc.column)]
            if not any(loc.method=='visual' for loc in claim.sources):
                numbers=printed_numbers(corpus)
                # A validation reference's declared result is matched against the curve's contract, its lineage (a
                # page, a row) bound to its locators and its tolerance is the comparison's: none is a quoted value.
                copied=({k:v for k,v in claim.value.items() if k not in ('result','lineage','tolerance')}
                        if claim.key=='validation_reference' and isinstance(claim.value,dict) else claim.value)
                if any(not any(abs(n-v)<=1e-12*max(abs(n),abs(v),1e-300) for v in numbers) for n in numeric_leaves(copied)):
                    raise ValueError('numerical value absent from cited raw evidence')
        candidate=ExperimentalDossier(title='source check',claims=[claim])
        catalog.validate_sources(candidate,revision.sources,revision.ingestions)
        result=convert(claim)
        if any(loc.method=='visual' for loc in claim.sources):
            result=result.model_copy(update={'note':result.note+' Visual transcription: researcher must check original image.'})
        return result,problems
    except (ValueError,StopIteration,IndexError) as error:
        problems.append(claim.key+': '+str(error))
        # Failed proposed values remain in the step's raw answer, never trusted in the dossier.
        return original.model_copy(update={'status':'unextracted','value':None,'sources':[],
                                           'requested_unit':'','note':'Evidence check failed: '+str(error)}),problems


def merge_claims(old: list[ExperimentalClaim],new: list[ExperimentalClaim],refine: bool=False) -> list[ExperimentalClaim]:
    """Retain disagreements; only explicit refinement replaces an interpretation."""
    values={c.key:c for c in old}
    for c in new:
        prior=values.get(c.key)
        if prior and prior.value is not None and c.status=='unextracted':
            continue
        if prior and prior.value is not None and c.value is not None and prior.value!=c.value and not refine:
            c=c.model_copy(update={'status':'conflicting','value':{'previous':prior.value,'proposal':c.value},
                'sources':[*prior.sources,*c.sources],'note':'Source disagreement; refine explicitly before calculating.'})
        values[c.key]=c
    return list(values.values())


class ExperimentalExtraction:
    """Reuse the model intake's persistent account/journal for source interpretation."""
    def __init__(self,catalog: ExperimentalCatalog | None=None):
        self.catalog=catalog or ExperimentalCatalog()
        self.budgets=Intake(Catalog(self.catalog.root))

    def scope(self,session: str) -> ExtractionScope:
        """A session's stored extraction scope, checked against its integrity hash, with its source revision loaded."""
        self.budgets.session(session)
        raw=json.loads((self.budgets.folder(session)/'experimental_scope.json').read_text())
        result=ExtractionScope.model_validate(raw)
        if result.session_id!=session or content_hash({k:v for k,v in raw.items() if k!='integrity_sha256'})!=result.integrity_sha256:
            raise ValueError('experimental session scope was modified')
        self.catalog.load(result.revision)
        return result

    def start(self,reference: str,budget: float,model: str='claude-opus-5-5',vision: bool=True,
              selected: list[str] | None=None,budget_session: str='',visual: list[str] | None=None,
              approval: str='',own_model: bool=False) -> ExtractionScope:
        """Open a budgeted session over the selected source units of a revision and store its batched scope; image
        units need an Anthropic model. ``budget_session``: an existing session whose cap and ledger its steps use
        instead of their own (a discovery session's one cap over every paper), with the same model. ``visual``: PDF
        page units sent also as page images (rendered at request time), the rest as ``vision`` says. ``approval``: how the budget was approved
        (``Session.approval``). ``own_model``: a shared-cap extraction with a model of its own (a record check's
        re-reading by the record assistant's model, under the check's cap: ``record_check``)."""
        if budget_session:
            owner=self.budgets.session(budget_session)
            if (owner.model!=model and not own_model) or budget:
                raise ValueError('a shared-cap extraction uses its budget session\'s model and no cap of its own')
        units=source_units(self.catalog,reference,vision)
        if visual:
            pages={u.unit_id for u in units if u.page is not None}
            if not set(visual)<=pages:
                raise ValueError('a unit sent as an image must be a PDF page of this revision')
            units=[u.model_copy(update={'vision':True,'notes':[*u.notes,'Sent as a page image: its figure may hold '
                                        'the result.']}) if u.unit_id in visual and not u.vision else u for u in units]
        chosen=[u for u in units if selected is None or u.unit_id in selected]
        if selected and len(chosen)!=len(set(selected)):
            raise ValueError('unknown selected source unit')
        if not chosen:
            raise ValueError('select source material')
        if model.startswith('gpt-') and any(u.vision for u in chosen):
            raise ValueError('image extraction requires Anthropic')
        s=self.budgets.start(budget,model,approval=approval)
        scope=ExtractionScope(session_id=s.session_id,revision=reference,created_at=utc_now(),units=units,batches=batches(chosen),
                              budget_session=budget_session)
        scope.integrity_sha256=content_hash(scope.model_dump(mode='json',exclude={'integrity_sha256'}))
        atomic_json(self.budgets.folder(s.session_id)/'experimental_scope.json',scope.model_dump(mode='json'))
        return scope

    def budget_owner(self,session: str) -> str:
        """The session whose cap and ledger this extraction's steps use: its scope's budget session, or itself."""
        return self.scope(session).budget_session or session

    def steps(self,session: str) -> list[ExtractionStep]:
        """A session's extraction steps in time order, each receipt checked against its content hash; a damaged one
        raises (what is read next and the trimmed request depend on every step: ``step_listing`` names it instead,
        for the session's page)."""
        self.scope(session)
        return sorted((self._step(session,path) for path in (self.budgets.folder(session)/'extractions').glob('*.json')),
                      key=lambda s:s.created_at)

    def step_listing(self,session: str):
        """(the session's steps that can be read, in time order; each step file that cannot be read, named with why:
        ``durable.read_each``; the consolidation plan's M3)."""
        from adroit.core.durable import read_each
        self.scope(session)
        found,damaged=read_each(sorted((self.budgets.folder(session)/'extractions').glob('*.json')),
                                lambda path:self._step(session,path))
        return sorted(found,key=lambda s:s.created_at),damaged

    def _step(self,session: str,path: Path) -> ExtractionStep:
        """One extraction receipt, checked against its content hash, its output revision and its page images."""
        raw=json.loads(path.read_text())
        step=ExtractionStep.model_validate(raw)
        if path.stem!=step.step_id or step.session_id!=session or content_hash({k:v for k,v in raw.items() if k!='step_id'})!=step.step_id:
            raise ValueError('extraction receipt integrity mismatch')
        self.catalog.load(step.output_revision)
        for u in step.read_units:
            if u.image:
                self.catalog.asset_path(u.image)
        return step

    def prepare(self,session: str,batch: int) -> list[SourceUnit]:
        """The source units of one batch of the scope, with a page image rendered for each vision unit that lacks
        one."""
        scope=self.scope(session)
        if not 0<=batch<len(scope.batches):
            raise ValueError('batch outside selected source scope')
        units=[u.model_copy(deep=True) for u in scope.units if u.unit_id in scope.batches[batch]]
        revision=self.catalog.load(scope.revision)
        for unit in units:
            if unit.vision and unit.image is None:
                source=next(a for a in revision.sources if a.sha256==unit.asset_sha256)
                data=render_page(self.catalog.asset_path(source),unit.page)
                unit.image=self.catalog.asset_bytes(f'page-{unit.page}.png',data,'page_preview')
        return units

    def preview(self,session: str,batch: int=0,instructions: str='') -> dict:
        """The next request's reservation, in full and with the compacted prior (``--trim``), and the budget. $0."""
        from adroit.agents.experimental_extraction import estimate
        steps=self.steps(session)
        scope=self.scope(session)
        s=self.budgets.session(session)
        owner=scope.budget_session or session
        revision=self.catalog.load(steps[-1].output_revision if steps else scope.revision)
        units=self.prepare(session,batch)
        args=(s.model,[u.model_dump(mode='json',exclude={'image'}) for u in units],revision.dossier.model_dump(mode='json'),
              [self.catalog.asset_path(u.image) for u in units if u.image],instructions)
        bound,trimmed=estimate(*args),estimate(*args,trimmed=True)
        read={i for step in steps for i in step.unit_ids}
        selected={i for b in scope.batches for i in b}
        return {'session':session,'batch':batch,'batch_count':len(scope.batches),'request_bound_usd':bound,
            'trimmed_request_bound_usd':trimmed,
            'budget':self.budgets.budget_status(owner),'read':sorted(read),'unread':sorted(selected-read),
            'not_selected':[u.unit_id for u in scope.units if u.unit_id not in selected],
            'revision':revision.reference,'units':[u.model_dump(mode='json') for u in units]}

    def step(self,session: str,batch: int=0,instructions: str='',llm=None,trimmed: bool=False) -> ExtractionStep:
        """Interpret one batch under the session budget: every proposed claim is checked against its cited raw
        evidence and merged into a new dossier revision, and the step's receipt is stored. The answer is saved before
        anything is published, and a step interrupted after its answer arrived finishes from it without asking again
        (the fresh audit's F19-05): from the saved answer, else from the response the paid journal holds."""
        from adroit.agents.llm import LLMClient,OpenAIClient,BudgetedLLMClient,FakeLLMClient
        from adroit.agents.experimental_extraction import MAX_OUTPUT,extract
        scope=self.scope(session)
        owner=scope.budget_session or session
        s=self.budgets.session(owner)
        model=self.budgets.session(session).model if owner!=session else s.model     # its own (``own_model``)
        units=self.prepare(session,batch)
        from contextlib import ExitStack
        with ExitStack() as locks:
            locks.enter_context(run_lock(self.budgets.folder(session)))
            if owner!=session:                  # the shared cap's reservations are serialised across its children
                locks.enter_context(run_lock(self.budgets.folder(owner)))
            steps=self.steps(session)
            prior=self.catalog.load(steps[-1].output_revision if steps else scope.revision)
            if not instructions and any(set(step.unit_ids)=={u.unit_id for u in units} for step in steps):
                raise ValueError('batch already interpreted; use explicit refinement or an unread batch')
            invocation=content_hash({'session':session,'units':[u.unit_id for u in units],'instructions':instructions,
                                     'prior':prior.reference,'trimmed':trimmed})[:32]
            answer=self._recovered(session,owner,invocation)
            if answer is None:
                if llm is None:
                    client=OpenAIClient if model.startswith('gpt-') else LLMClient
                    llm=BudgetedLLMClient(client(model=model,max_tokens=MAX_OUTPUT),account=self.budgets.account(s),
                        ledger_path=self.budgets.folder(owner)/'paid.jsonl')
                    self.budgets.clients.append(llm)       # its requests: the run's own (``RunRequests``)
                elif not isinstance(llm,FakeLLMClient):
                    raise ValueError('live interpretation must use the session budget')
                if s.budget<=0:
                    raise ValueError('interpretation needs an up-front session budget')
                if hasattr(llm,'invocation'):
                    llm.invocation=invocation
                answer=extract(llm,model,[u.model_dump(mode='json',exclude={'image'}) for u in units],
                               prior.dossier.model_dump(mode='json'),[self.catalog.asset_path(u.image) for u in units if u.image],
                               instructions,trimmed)
                atomic_json(self._pending(session,invocation),answer.model_dump(mode='json'))
            step=self._publish(session,prior,steps,units,answer,instructions,trimmed)
            self._pending(session,invocation).unlink(missing_ok=True)
            return step

    def _pending(self,session: str,invocation: str):
        """Where an answer waits between its arrival and its receipt."""
        return self.budgets.folder(session)/'pending'/f'{invocation}.json'

    def _recovered(self,session: str,owner: str,invocation: str):
        """An answer already paid for and not yet receipted: the saved one, else the last response the paid journal
        received for this invocation that parses as an answer; None if there is none."""
        from adroit.agents.experimental_extraction import ExtractionAnswer
        from adroit.agents.llm import _extract_json, journalled_text
        from adroit.agents.budget import ledger_text
        from adroit.core.durable import absent
        saved=self._pending(session,invocation)
        if not absent(saved):
            try:
                return ExtractionAnswer.model_validate_json(saved.read_text())
            except (OSError,ValueError):
                pass
        journal=self.budgets.folder(owner)/'paid.jsonl'
        if absent(journal):         # a journal there that cannot be read is damaged, never none (DN-01)
            return None
        rows=[json.loads(line) for line in ledger_text(journal).splitlines() if line.strip()]
        mine={r['id'] for r in rows if r.get('state')=='reserved' and r.get('invocation')==invocation}
        for row in reversed(rows):
            if row.get('id') not in mine or row.get('state')!='received':
                continue
            text=journalled_text(row.get('response'))         # either provider's answer (NA15-02)
            try:
                return ExtractionAnswer.model_validate_json(_extract_json(text)) if text else None
            except ValueError:
                continue
        return None

    def _publish(self,session: str,prior,steps,units,answer,instructions: str,trimmed: bool) -> ExtractionStep:
        """Check and merge an answer into a new dossier revision (or the one a previous attempt already published for
        this very answer) and store the step's receipt."""
        content=prior.dossier.model_copy(deep=True)
        problems=[]
        def check(claims):
            checked=[]
            for claim in claims:
                c,issues=checked_claim(self.catalog,prior,claim,units)
                checked.append(c)
                problems.extend(issues)
            return checked
        content.claims=merge_claims(content.claims,check(answer.claims),bool(instructions))
        results={r.result_id:r for r in content.results}
        for r in answer.results:
            previous=results.get(r.result_id)
            claims=merge_claims(previous.claims if previous else [],check(r.claims),bool(instructions))
            if previous and previous.kind!=r.kind and not instructions:
                problems.append(r.result_id+': conflicting observation classification')
                continue
            results[r.result_id]=r.model_copy(update={'claims':claims})
        content.results=list(results.values())
        content.notes=list(dict.fromkeys([*content.notes,*answer.ambiguities,*problems]))
        provenance={'extraction_session':session,'read_unit_ids':[u.unit_id for u in units],
                    'raw_answer_sha256':content_hash(answer.model_dump(mode='json'))}
        output=self._published(prior,provenance) or self.catalog.save(content,prior.sources,prior.ingestions,
                                                                      prior.reference,provenance=provenance)
        body=dict(session_id=session,created_at=utc_now(),parent_step=steps[-1].step_id if steps else '',
            input_revision=prior.reference,output_revision=output.reference,unit_ids=[u.unit_id for u in units],
            explanation=answer.explanation,ambiguities=answer.ambiguities,evidence_problems=problems,
            raw_answer=answer.model_dump(mode='json'),instructions=instructions,read_units=[u.model_dump(mode='json') for u in units])
        if trimmed:
            body['trimmed_prior']=True
        step=ExtractionStep(step_id=content_hash(body),**body)
        atomic_json(self.budgets.folder(session)/'extractions'/f'{step.step_id}.json',
                    step.model_dump(mode='json',exclude=None if trimmed else {'trimmed_prior'}))
        return step

    def _published(self,prior,provenance: dict):
        """A revision a previous attempt already published from this prior for this very answer, or None."""
        for revision in self.catalog.list():
            if revision.parent_revision and revision.experiment_id==prior.experiment_id \
                    and f'experimental:{revision.experiment_id}@{revision.parent_revision}'==prior.reference \
                    and all(revision.provenance.get(k)==v for k,v in provenance.items()):
                return revision
        return None
