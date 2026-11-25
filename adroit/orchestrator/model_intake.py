"""Immutable reviewed intake steps with one durable session budget."""
from __future__ import annotations

from datetime import datetime,timezone
import json
import math
from pathlib import Path
import time
from uuid import uuid4

from pydantic import Field

from adroit.agents.budget import LedgerRequest, read_held, read_ledger, read_raised  # noqa: F401 - LedgerRequest: the ledger's rows
from adroit.core.checkpoint import atomic_json,run_lock
from adroit.core.durable import Held, absent, mark_of
from adroit.core.evidence import content_hash
from adroit.core.model_spec import ModelSpec
from adroit.core.model_preferences import StyleDeclaration
from adroit.core.state import StrictModel
from adroit.library.personal import Catalog,Asset,TOKEN,DIGEST,support,usable
from adroit.orchestrator.model_approval import SCHEMA_VERSION,ModelApproval,model_identity,verify_identity
from adroit.model_building.tex import render

class CapChange(StrictModel):
    """A researcher's confirmed increase of a session's cap (journalled in the session and its paid ledger)."""
    previous: float
    new: float
    at: str
    reason: str = ''

class Session(StrictModel):
    """A model-intake session: its budget cap in dollars (at most $10), language model, parent catalog revision, cap
    changes and integrity hash."""
    session_id: str
    budget: float = Field(ge=0,le=10,allow_inf_nan=False)
    model: str = 'claude-opus-5-5'
    parent_catalog_reference: str = ''
    cap_history: list[CapChange] = Field(default_factory=list)
    # its paid ledger was made with it (a paid session opened since 2026-10-25, a cap raised, or a session's first
    # paid account): a session without this field, from before, hashes as before (the auditor's consolidation audit, CO-05)
    journal: bool = Field(default=False, exclude_if=lambda v: not v)
    # how its cap was approved where a gate said (``ui.forms.BudgetCheck.approval``): "auto", by the workbench's
    # auto-approve setting with the default models chosen; "click", by the person's tick. A session without it, from
    # before 2026-11-18 or opened without a gate's word, hashes as before
    approval: str = Field(default='', exclude_if=lambda v: not v)
    integrity_sha256: str = ''

def session_identity(s:Session)->str:
    """The integrity hash of a session's configuration (a session without cap changes hashes as before they existed)."""
    data=s.model_dump(mode='json',exclude={'integrity_sha256'})
    if not data['cap_history']:
        data.pop('cap_history')
    return content_hash(data)

class DraftChoice(StrictModel):
    """One candidate model of an intake step: the typed model, its TeX, the explanation, the ambiguities to review
    and what the engines can compute for it."""
    spec: ModelSpec
    tex: str
    explanation: str = ''
    ambiguities: list[str] = Field(default_factory=list)
    applicability: dict = Field(default_factory=dict)
    # a simplified model's: what it leaves out of the larger theory it is part of; its name says "(simplified model)"
    # (``ideas.simplified_name``; the owner, 2026-11-17). Absent where it is not one, so a draft's stored content is
    # as before.
    simplified: str = Field(default='', exclude_if=lambda v: not v)

class Draft(StrictModel):
    """One immutable intake step, named by its content hash: the input, its transcription, the candidate models and
    the source assets."""
    step_id: str
    session_id: str
    parent_step: str = ''
    parent_candidate: int = 0
    created: str
    kind: str
    input_text: str
    transcription: str
    choices: list[DraftChoice]
    sources: list[Asset] = Field(default_factory=list)
    schema_version: int | None = None       # its models' schema era; None: written before 2026-10-16
    # the model builder's proposals not offered, each with why it cannot run as built (the owner, 2026-11-21: only
    # usable models are offered; ``library.personal.usable``). Absent where there are none, so a step stored before
    # is read as it was written.
    not_offered: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)

NOT_SAVED=('this model cannot run yet, so it is not saved (give its missing values in "Complete this model", or '
           'correct it, then save the new draft): ')


def offer(choices:list[DraftChoice])->tuple[list[DraftChoice],list[str]]:
    """(the candidates that are usable, why each other is not offered): the model builder offers only models that can
    run (the owner, 2026-11-21; ``library.personal.usable``), judged now, never from a stored applicability (the auditor's
    UM-07)."""
    offered,refused=[],[]
    for c in choices:
        verdict=usable(c.spec)
        if verdict.ok:
            offered.append(c)
        else:
            refused.append(f'{c.spec.name}: not offered, since it cannot run as built: '+'; '.join(verdict.blocking))
    return offered,refused

REQUESTS='paid_requests.json'     # in a command's output folder: its own requests in its session's paid ledger

class RunRequests(StrictModel):
    """One command's own paid requests (``REQUESTS`` in its output folder; the owner's report of 2026-10-23: the
    workbench had shown an intake's $0.05 as $0): the session's paid-ledger identifiers that this command's budgeted
    clients reserved, so its cost is read from the ledger itself, apart from the session's earlier and later requests
    (a refinement never counts its parents' spending again). An empty list: no request was sent. ``attempt``: the
    workbench run that wrote it (``preflight.run_attempt``; "" outside one, or from before): a study's cost reads it
    only as its own run's (the auditor's DD recheck, DE-01, 2026-11-05)."""
    session_id: str
    request_ids: list[str] = Field(default_factory=list)
    attempt: str = ""


def _kind(path:Path)->str|None:
    """A step record's kind, read without checking it (None where it cannot be read, a link leading nowhere among them:
    it may be a paid step's, DN-01): the evidence of a paid step."""
    try:
        return str(json.loads(path.read_text()).get('kind',''))
    except (OSError,ValueError,AttributeError):
        return None

def _names(path:Path,session_id:str)->bool|None:
    """Whether a run's request record names requests of a session (None where it cannot be read: it may)."""
    try:
        raw=json.loads(path.read_text())
        return raw.get('session_id')==session_id and bool(raw.get('request_ids'))
    except (OSError,ValueError,AttributeError):
        return None


SETTLING = (0.01, 0.02, 0.05, 0.1, 0.2, 0.5)   # the pauses between readings of a session being changed (``snapshot``)


class UnsettledSession(ValueError):
    """A session's record and its paid ledger could not be read as one state of the session (``Intake.snapshot``)."""


def _disagreement(s, raised: list[dict]) -> str:
    """Why a session's record and the cap raises its paid ledger journals (``read_raised``) are not of one state of
    the session, or "". ``raise_cap`` journals a raise in the ledger, then writes the record: a ledger with a raise its
    record lacks is read while a raise is being made (or one was interrupted, or the record was restored)."""
    try:
        journalled = [CapChange.model_validate(r) for r in raised]
    except ValueError:
        return 'its paid ledger journals a cap raise that cannot be read'
    if journalled == s.cap_history:
        return ''
    if journalled[:len(s.cap_history)] == s.cap_history:
        last = journalled[-1]
        return (f'its paid ledger journals a cap raise to ${last.new:.2f} (at {last.at}) that its record does not '
                f'have: a raise being made, or one interrupted, or its record restored')
    return 'its record\'s cap raises are not those its paid ledger journals'


class Intake:
    """Model intake as reviewed, immutable steps, with one durable budget per session."""
    def __init__(self,catalog:Catalog|None=None):
        self.catalog=catalog or Catalog()
        self.clients:list=[]          # the budgeted clients this service made: their journals name its own requests
    def request_ids(self)->list[str]:
        """The paid-ledger identifiers of the requests this service's budgeted clients reserved, in order."""
        return [e['id'] for c in self.clients for e in getattr(c,'ledger',[]) if e.get('state')=='reserved']
    def requests(self,session_id)->dict[str,LedgerRequest]:
        """Every request of a session's paid ledger by its identifier (read-only, ``journal``); for an identifier with
        no session record, its ledger as it stands (none: no request)."""
        if absent(self.folder(session_id)/'session.json'):         # a record there that cannot be read raises (DN-01)
            return read_ledger(self.folder(session_id)/'paid.jsonl')
        return self.journal(self.session(session_id))
    def journal(self,s)->dict[str,LedgerRequest]:
        """A session's paid ledger as ``read_ledger`` reads it (read-only). A missing ledger is an empty one only for a
        session that shows no sign of ever having had one (``spending_evidence``); otherwise ``MissingJournal``: its
        spending cannot be known, so its budget is blocked until the original is restored (the auditor's consolidation
        audit, CO-05, 2026-10-25: a lost ledger had restored the session's whole approved cap). A ledger that is there
        but cannot be read, a link to a missing file among them, is not missing but damaged (``budget.read_raised``
        raises): the budget is blocked either way, and no ledger is made in its place (the auditor's DM recheck, DN-01)."""
        return self._journal(s)[0]
    def _journal(self,s)->tuple[dict[str,LedgerRequest],list[dict],Held|None]:
        """(``journal``, the cap raises the ledger journals, what it held as read: ``budget.read_held``; None where
        nothing is there), of one reading of the ledger."""
        from adroit.agents.budget import MissingJournal
        path=self.folder(s.session_id)/'paid.jsonl'
        if not absent(path):
            return read_held(path)
        if evidence:=self.spending_evidence(s):
            raise MissingJournal(path,evidence)
        return {},[],None
    def spending_evidence(self,s)->list[str]:
        """Why a session must have a paid ledger (``journal``): it was opened with one, or made one when it first paid;
        its cap was raised (a change journalled there); a recovered ledger's original bytes are kept beside it; it holds
        an interpreted step, an extraction or an answer awaiting its receipt, each from a paid request; or a run's
        request record names its requests. A step or a run's request record that cannot be read may be one of those,
        so it is evidence too, named (the auditor's DM recheck, DN-01, 2026-11-08: one that could not be read, a link leading
        nowhere among them, had read as no evidence, and a lost ledger as one never had: the session's whole cap
        restored). [] for a session that never had one."""
        from adroit.core.config import get_settings
        folder=self.folder(s.session_id)
        found=[]
        if s.journal:
            found.append('the session was opened with a paid ledger')
        if s.cap_history:
            found.append('its cap was raised, a change journalled in that ledger')
        if any(folder.glob('paid.jsonl.torn-*')):
            found.append('a recovered ledger\'s original bytes are kept beside it')
        if not absent(mark_of(folder/'paid.jsonl')):
            found.append(f'the mark beside it ({mark_of(folder/"paid.jsonl").name}) records what was written to it')
        kinds={p:_kind(p) for p in sorted((folder/'steps').glob('*.json'))}
        paid=[p for p,kind in kinds.items() if kind in ('idea','tex','image','refine','paper')]
        if paid:
            found.append(f'it holds {len(paid)} interpreted step(s), each from a paid request')
        if unread:=[p for p,kind in kinds.items() if kind is None]:
            found.append(f'it holds {len(unread)} step(s) that cannot be read (first: {unread[0].name}), each perhaps '
                         'from a paid request')
        made=list((folder/'extractions').glob('*.json'))+list((folder/'pending').glob('*.json'))
        if made:
            found.append(f'it holds {len(made)} extraction(s) or answer(s), each from a paid request')
        runs=get_settings().runs_dir
        records={r:_names(r,s.session_id) for r in (runs.rglob(REQUESTS) if s.budget>0 and runs.is_dir() and not found
                                                    else [])}
        if named:=[r for r,names in records.items() if names]:
            found.append(f'{len(named)} run(s) recorded paid requests of this session (first: {named[0].parent})')
        if unread:=[r for r,names in records.items() if names is None]:
            found.append(f'{len(unread)} run request record(s) cannot be read, each perhaps of this session (first: '
                         f'{unread[0].parent})')
        return found
    def folder(self,session_id):
        """A session's folder in the catalog (the identifier must be a valid token)."""
        if not TOKEN.fullmatch(session_id):
            raise ValueError('invalid intake session identifier')
        return self.catalog.root/'intake'/session_id
    def session(self,session_id):
        """A session's stored configuration, checked against its integrity hash."""
        return self._record(session_id)[1]
    def _record(self,session_id):
        """(the bytes of a session's record, ``session`` of those bytes)."""
        raw=(self.folder(session_id)/'session.json').read_bytes()
        s=Session.model_validate_json(raw)
        if s.session_id!=session_id or session_identity(s)!=s.integrity_sha256:
            raise ValueError('intake session configuration was modified; begin a new approved session')
        return raw,s
    def start(self,budget:float=0,model='claude-opus-5-5',parent='',approval:str=''):
        """Open a session with its budget and model (optionally from a catalog revision, which becomes its first
        step); ``approval``: how its budget was approved (``Session.approval``), kept with a paid session only."""
        if parent:
            self.catalog.load(parent)
        if budget:
            from adroit.core.pricing import bounded_price
            bounded_price(model)
            if not model.startswith(('claude-','gpt-')):
                raise ValueError('session model needs a supported paid provider')
        s=Session(session_id=uuid4().hex,budget=budget,model=model,parent_catalog_reference=parent,journal=budget>0,
                  approval=approval if budget>0 else '')
        s.integrity_sha256=session_identity(s)
        if s.journal:                         # its paid ledger first: a session record never claims one not made
            from adroit.core.durable import write_atomic
            write_atomic(self.folder(s.session_id)/'paid.jsonl','')
        atomic_json(self.folder(s.session_id)/'session.json',s.model_dump(mode='json'))
        if parent:
            r=self.catalog.load(parent)
            self._save(s,'catalog','',r.tex,[self.choice(r.spec)],r.sources,'')
        return s
    def raise_cap(self,session_id,budget:float,*,confirmed:bool,reason:str='')->Session:
        """Raise a session's cap to ``budget`` after the researcher's explicit confirmation; the change is kept in the
        session (under its integrity hash) and journalled in its paid ledger. A cap is never lowered here, nor raised
        past a ledger whose cap raises are not its record's (DQ-03)."""
        from adroit.agents.budget import SESSION_CAP_LIMIT
        from adroit.core.chronology import utc_now
        from adroit.core.pricing import bounded_price
        if not confirmed:
            raise ValueError('a cap increase needs the researcher\'s explicit confirmation (--confirmed)')
        with run_lock(self.folder(session_id)):
            s=self.session(session_id)
            if not (math.isfinite(budget) and s.budget<budget<=SESSION_CAP_LIMIT):
                raise ValueError(f'the new cap must exceed the current ${s.budget:.2f} and be at most '
                                 f'${SESSION_CAP_LIMIT:g}')
            bounded_price(s.model)
            if not s.model.startswith(('claude-','gpt-')):
                raise ValueError('session model needs a supported paid provider')
            change=CapChange(previous=s.budget,new=budget,at=utc_now(),reason=reason)
            _,raised,held=self._journal(s)         # a lost or damaged ledger is not raised past (CO-05, DN-01)
            self._agreed(s,raised,'its cap is not raised past them')
            s=s.model_copy(update={'budget':budget,'cap_history':[*s.cap_history,change],'journal':True})
            s.integrity_sha256=session_identity(s)
            # the ledger first, then the record: a session record never claims a ledger that was not made (CO-05);
            # appended only to the ledger as read, never to one put in its place or made anew meanwhile (DO-01), nor
            # after a torn or damaged line (DP-01)
            from adroit.agents.budget import journal_whole
            from adroit.core.durable import append_held
            append_held(self.folder(session_id)/'paid.jsonl',
                        (json.dumps({'state':'cap_raised',**change.model_dump(mode='json')})+'\n').encode(),held,
                        whole=journal_whole)
            atomic_json(self.folder(session_id)/'session.json',s.model_dump(mode='json'))
            return s
    def completion_choices(self,spec)->tuple[list[DraftChoice],list[str]]:
        """For a proposal the engines cannot compute as it stands: (its computable completions as further choices,
        each naming the flavour or zeroed coupling it chooses; the choice the proposal itself still needs, such as a
        scalar mixing angle), for the researcher to take or leave (live check L9)."""
        from adroit.orchestrator.completions import completions,mixing_choice
        from adroit.parameter_space.classify import Unsupported,classify
        try:
            classify(spec,generic_route=False)          # completions point to the library's validated classes
            return [],[]
        except Unsupported as error:
            refusal=str(error)
        try:
            classify(spec)
            as_proposed='which as proposed only the generic route computes'
        except Unsupported:
            as_proposed='which as proposed is not computed'
        def label(o):
            return '; '.join(x.split(':')[1].split('(')[0].strip() for x in o.choices if x.startswith('one flavour')) or 'chosen couplings'
        out=[self.choice(o.spec.model_copy(update={'name':f'{spec.name} ({label(o)})'}),
                         f'A completion of {spec.name} that the library\'s classes compute, {as_proposed} ({refusal}).',
                         o.choices) for o in completions(spec)]
        return out,(['To compute it, '+mixing_choice(refusal)] if mixing_choice(refusal) else [])
    def choice(self,spec,explanation='',ambiguities=None,simplified=''):
        """A model as a draft choice, with its TeX and what the engines support for it; a simplified model
        (``simplified``: what it leaves out) named so (``ideas.simplified_name``)."""
        from adroit.orchestrator.ideas import simplified_name
        simplified=(simplified or '').strip()
        if simplified:
            spec=spec.model_copy(update={'name':simplified_name(spec.name)})
        return DraftChoice(spec=spec,tex=render(spec),explanation=explanation,
                           ambiguities=ambiguities or [],applicability=support(spec),simplified=simplified)
    def _save(self,s,kind,text,transcription,choices,sources,parent,parent_candidate=0,not_offered=()):
        body=dict(session_id=s.session_id,parent_step=parent,parent_candidate=parent_candidate,created=datetime.now(timezone.utc).isoformat(),
            kind=kind,input_text=text,transcription=transcription,
            choices=[c.model_dump(mode='json') for c in choices],sources=[a.model_dump(mode='json') for a in sources],
            schema_version=SCHEMA_VERSION,**({'not_offered':list(not_offered)} if not_offered else {}))
        key=content_hash(body)
        draft=Draft(step_id=key,**body)
        path=self.folder(s.session_id)/'steps'/f'{key}.json'
        if path.exists():
            raise ValueError('intake steps cannot be overwritten')
        atomic_json(path,draft.model_dump(mode='json'))
        return draft
    def load(self,session_id,step_id):
        """A pinned intake step, checked against its content hash and its source assets."""
        if not DIGEST.fullmatch(step_id):
            raise ValueError('a pinned intake step is required')
        p=self.folder(session_id)/'steps'/f'{step_id}.json'
        if p.is_symlink():
            raise ValueError('intake step must not be a symlink')
        raw=json.loads(p.read_text())
        d=Draft.model_validate(raw)
        # the stored content as written (a schema field added since would change a re-serialised hash)
        if d.session_id!=session_id or d.step_id!=step_id or content_hash({k:v for k,v in raw.items() if k!='step_id'})!=step_id:
            raise ValueError('intake step integrity mismatch')
        for asset in d.sources:
            self.catalog.asset_path(asset)
        return d
    def steps(self,session_id):
        """Every step of a session, in order of creation; a damaged one raises (a refinement's parent is the last
        step: ``listing`` names a damaged one instead, for the session's page)."""
        return sorted((self.load(session_id,p.stem) for p in (self.folder(session_id)/'steps').glob('*.json')),key=lambda d:(d.created,d.step_id))
    def listing(self,session_id):
        """(the session's steps that can be read, in order of creation; each step file that cannot be read, named with
        why: ``durable.read_each``; the consistency audit's CA-07, 2026-10-24)."""
        from adroit.core.durable import read_each
        found,damaged=read_each(sorted((self.folder(session_id)/'steps').glob('*.json')),
                                lambda p:self.load(session_id,p.stem))
        return sorted(found,key=lambda d:(d.created,d.step_id)),damaged
    def account(self,s):
        """The session's budget account for spending, rebuilt from its paid ledger as ``read_ledger`` reads it (the
        consistency audit's CA-06, 2026-10-24: a parser of its own here had read a settled request later marked
        uncertain as an ordinary settlement, which the run pages call damaged): settled costs, open reservations and
        frozen provider caps, in settlement order. A lost ledger refuses before anything is reserved
        (``journal``, CO-05); a paid session from before 2026-10-25 that never had one makes its empty ledger now and
        records that it has one, so that its loss is known later. Called under the session's run lock. The account
        names its ledger and what the ledger held as read (``BudgetAccount.journal``, ``held``), of the same reading as
        its money: a client appending to it later appends only to that ledger (``BudgetedLLMClient._journal``; the auditor's
        DN recheck, DO-01, 2026-11-08). Its record is read again here, under that lock (which a cap raise holds too),
        and the cap raises its ledger journals must be its record's (``_disagreement``), as its budget's reading
        requires (``snapshot``): otherwise nothing is reserved (``UnsettledSession``); and each append of its clients
        to its ledger checks so again, with the whole ledger (``BudgetAccount.whole``, ``_spending_whole``; the auditor's DP
        recheck, DQ-03, 2026-11-09: an account had been rebuilt, and its client spent on, from a ledger journalling a
        raise its record did not have, while the session's budget reading refused it)."""
        s=self.session(s.session_id)
        requests,raised,held=self._journal(s)
        self._agreed(s,raised,'nothing is reserved or sent under its budget')
        if s.budget>0 and not s.journal and held is None:
            held=self._open_journal(s)
        account=self._account(s,requests)
        account.journal,account.held=self.folder(s.session_id)/'paid.jsonl',held
        account.whole=self._spending_whole(s.session_id)
        return account
    def _spending_whole(self,session_id):
        """The whole-ledger check a session's clients append to its ledger under (``BudgetAccount.whole``): its
        writers' rules (``budget.journal_raises``, as ``journal_whole``), and the cap raises it journals its record's,
        the record read at each append (``_disagreement``)."""
        from adroit.agents.budget import journal_raises
        def whole(data,path):
            self._agreed(self.session(session_id),journal_raises(data,path),'nothing is written to it')
        return whole
    def _agreed(self,s,raised,refused):
        """``UnsettledSession`` where the cap raises a session's paid ledger journals are not its record's
        (``_disagreement``): what its spending (``account``, ``_spending_whole``) and its raises (``raise_cap``) refuse,
        as its budget's reading does (``snapshot``; DQ-03)."""
        if why:=_disagreement(s,raised):
            raise UnsettledSession(f'{why}: its record and its paid ledger are not of one state, so {refused}')
    def _open_journal(self,s):
        """An older paid session's first paid account: its empty ledger made where nothing is (never over an entry
        made meanwhile, nor through a link: ``durable.append_held``), then its record marked as having one; what the
        ledger holds, returned."""
        from adroit.agents.budget import journal_whole
        from adroit.core.durable import append_held
        held=append_held(self.folder(s.session_id)/'paid.jsonl',b'',None,whole=journal_whole)
        marked=s.model_copy(update={'journal':True})
        marked.integrity_sha256=session_identity(marked)
        atomic_json(self.folder(s.session_id)/'session.json',marked.model_dump(mode='json'))
        return held
    def _account(self,s,requests):
        """A budget account from a session's ledger requests (``account``, ``budget_status``)."""
        from adroit.agents.budget import BudgetAccount
        account=BudgetAccount(s.budget)
        if any(r.provider not in ('anthropic','openai') for r in requests.values()):
            raise ValueError('invalid request reservation in session budget journal')
        spent,frozen={},{}
        for r in sorted((r for r in requests.values() if r.state=='settled'),key=lambda r:r.settled_line):
            spent[r.provider]=spent.get(r.provider,0)+r.cost_usd
            if r.bound_exceeded:
                frozen[r.provider]=spent[r.provider]
        account.spent=spent
        account.reservations={k:(r.provider,r.reserved_usd) for k,r in requests.items() if r.state!='settled'}
        account.provider_caps=frozen
        return account
    def budget_status(self,session_id):
        """The session's cap, spent, still-reserved and remaining dollars, of one state of the session
        (``snapshot``)."""
        return self.snapshot(session_id)[0]       # read-only: a lost ledger is never an empty one (CO-05)
    def snapshot(self,session_id):
        """(``budget_status``, ``requests``) of one state of the session: its cap, its spending, its reserved and
        remaining dollars, and the requests they are of, all of one reading of its paid ledger (the auditor's DE recheck,
        DF-02, 2026-11-05: its status and its requests read apart, a request settled between the two readings had been
        in a cost's requests and its total, not in its spending or remaining dollars), and its cap of the record that
        stood while that ledger was read (the auditor's DF recheck, DG-01, 2026-11-06: the record read first, a cap raised
        and spent under before the ledger's reading had shown the old cap with the new spending). A reading is of one
        state where the record's bytes are the same after the ledger's reading as before it, and the cap raises the
        ledger journals are the record's; otherwise the session is read again after a short pause (``SETTLING``, about
        a second in all), and then ``UnsettledSession`` names why. Takes no lock: a page's reading never waits on a
        paid request in flight, nor writes anything."""
        why=''
        for pause in (*SETTLING,None):
            raw,s=self._record(session_id)
            requests,raised,_=self._journal(s)
            same=(self.folder(session_id)/'session.json').read_bytes()==raw
            why=_disagreement(s,raised) if same else 'its record changed while its paid ledger was read'
            if not why:
                return self._status(s,requests),requests
            if pause is not None:
                time.sleep(pause)
        raise UnsettledSession(f'its record and its paid ledger were not of one state at any of {len(SETTLING)+1} '
                               f'readings: {why}')
    def _status(self,s,requests):
        """``budget_status`` of a session's record and its ledger's requests as read."""
        a=self._account(s,requests)
        paid=sum(a.spent.values())
        pending=sum(v for _,v in a.reservations.values())
        return {'cap':s.budget,'spent':paid,'reserved_uncertain':pending,'remaining':max(0,s.budget-paid-pending)}
    def step(self,session_id,kind,text='',*,parent_step='',candidate=0,source:Path|None=None,llm=None,models=2,source_name=''):
        """One intake step: a typed model or field content is read directly ($0); an idea, TeX, screenshot or
        refinement is interpreted by the language model under the session budget."""
        from adroit.agents.model_intake import interpret
        from adroit.orchestrator import ideas
        import yaml
        s=self.session(session_id)
        prior=self.load(session_id,parent_step) if parent_step else None
        previous=prior.choices[candidate].spec if prior else None
        text,sources,image=self._inputs(kind,text,prior,source,source_name)
        with run_lock(self.folder(session_id)):
            if kind in ('fields','typed'):
                from adroit.orchestrator.model_approval import read_model
                spec=read_model(yaml.safe_load(text))
                if kind=='fields':
                    if spec.terms or spec.couplings or spec.scalar_potential or spec.vector_currents:
                        raise ValueError('field-content intake cannot discard terms or coefficients; use typed model intake')
                    spec=ideas.from_fields(spec).general
                return self._save(s,kind,text,render(spec),[self.choice(spec)],sources,parent_step,candidate)
            llm=self._session_llm(session_id,s,image,llm)
            if kind=='idea' and prior is None:
                result=ideas.run(ideas.IdeaRequest(text=text,models=models),llm)
                choices=[]
                for m in result.models:
                    extra,needed=self.completion_choices(m.general or m.spec)
                    choices+=[self.choice(m.general or m.spec,m.rationale,needed,m.simplified),*extra]
                if not choices and not result.dropped:
                    raise ValueError('no structurally interpretable model proposals returned')
                offered,not_offered=offer(choices)
                return self._save(s,kind,text,text,offered,sources,parent_step,
                                  not_offered=[*result.dropped,*not_offered])
            result=interpret(llm,text,previous=previous,images=[image] if image else None,model=s.model)
            field_only=result.representation=='field_content'
            mixed=bool(result.spec.terms or result.spec.couplings or result.spec.scalar_potential or result.spec.vector_currents)
            if field_only and mixed:
                result.ambiguities.append('Field-content interpretation also supplied interactions/coefficients; retained exactly. Review the intended representation.')
            generated=field_only and not mixed
            spec=ideas.from_fields(result.spec).general if generated else result.spec
            return self._save(s,kind,text,result.transcription,
                [self.choice(spec,result.explanation+(' Deterministic general Lagrangian generated from field content; coefficients remain unspecified.'
                    if generated else ''),result.ambiguities,result.simplified)],sources,parent_step,candidate)
    def _inputs(self,kind,text,prior,source,source_name):
        """A step's input text, its source assets (its parent's first) and its screenshot, checked for its kind."""
        sources=list(prior.sources) if prior else []
        image=None
        if source is not None:
            asset=self.catalog.asset(source,'image' if kind=='image' else 'user_source')
            sources.append(asset)
            if source_name:
                if Path(source_name).name.startswith('.env'):
                    raise ValueError('credential source refused')
                asset=asset.model_copy(update={'name':Path(source_name).name})
                sources[-1]=asset
            if kind=='image':
                image=self.catalog.asset_path(asset)
            elif not text:
                text=self.catalog.asset_path(asset).read_text()
        if kind=='image' and image is None:
            raise ValueError('image intake requires a selected screenshot')
        if kind not in ('idea','tex','image','fields','typed','refine'):
            raise ValueError('unsupported model intake kind')
        if kind!='image' and not text.strip():
            raise ValueError('nonempty model input required')
        if text:
            sources.append(self.catalog.asset_bytes('input.tex' if kind=='tex' else 'input.txt',text.encode(),'typed_input'))
        return text,sources,image
    def _session_llm(self,session_id,s,image,llm):
        """The session's budgeted language model, or the explicit offline fake; none without an up-front budget."""
        from adroit.agents.llm import LLMClient,BudgetedLLMClient,FakeLLMClient
        if s.budget<=0:
            raise ValueError('LLM interpretation needs an up-front session budget')
        account=self.account(s)
        if llm is None:
            from adroit.agents.llm import OpenAIClient
            if image and not s.model.startswith('claude-'):
                raise ValueError('this screenshot workflow requires Anthropic vision')
            client=OpenAIClient if s.model.startswith('gpt-') else LLMClient
            llm=BudgetedLLMClient(client(model=s.model,max_tokens=8192),account=account,
                                  ledger_path=self.folder(session_id)/'paid.jsonl')
            self.clients.append(llm)
        elif not isinstance(llm,FakeLLMClient):
            raise ValueError('only the explicit offline fake can be injected; live calls use the session budget')
        return llm
    def approve(self,session_id,step_id,candidate,*,confirmed:bool,expected_model_hash:str,tex:str,
                style_declarations:list[StyleDeclaration]|None=None):
        """Save a step's candidate to the catalog after the researcher's explicit confirmation, with the model hash
        and TeX unchanged and its structural audit passed; an approval already saved is returned as it is."""
        from adroit.model_building.audit import audit
        if not confirmed:
            raise ValueError('review the transcription, assumptions and canonical model before saving')
        d=self.load(session_id,step_id)
        s=self.session(session_id)
        choice=d.choices[candidate]
        try:      # the hash as the step's era showed it, or as this code shows it
            verify_identity(choice.spec,expected_model_hash,None if expected_model_hash==model_identity(choice.spec)
                            else d.schema_version)
        except ValueError:
            raise ValueError('edited model or TeX requires a new interpretation/typed correction before approval') from None
        if tex!=choice.tex:
            raise ValueError('edited model or TeX requires a new interpretation/typed correction before approval')
        if not audit(choice.spec).valid:
            raise ValueError('structural audit failed; correct the model before approval')
        verdict=usable(choice.spec,self.inherited_matching(session_id,d,choice))
        if not verdict.ok:
            raise ValueError(NOT_SAVED+'; '.join(verdict.blocking))
        identity=model_identity(choice.spec)
        approval=ModelApproval(model_sha256=identity,source_model_sha256=identity,choice='supplied',
                               schema_version=SCHEMA_VERSION)
        with run_lock(self.folder(session_id)):
            p=self.folder(session_id)/'approved'/f'{step_id}_{candidate}.json'
            if p.exists():
                ref=json.loads(p.read_text())['reference']
                saved=self.catalog.load(ref)
                if style_declarations is not None and saved.provenance.get('model_styles',[])!=[x.model_dump(mode='json') for x in style_declarations]:
                    raise ValueError('changed style declarations require a new draft/revision')
                return saved
            parent_ref=self._approved_parent(session_id,d,s.parent_catalog_reference)
            previous=self.catalog.load(parent_ref) if parent_ref else None
            same=previous is not None and previous.spec==choice.spec        # the same model, whatever its era
            derivation=previous.derivation if same else None                 # = inherited_matching's answer
            styles=([x.model_dump(mode='json') for x in style_declarations] if style_declarations is not None
                    else previous.provenance.get('model_styles',[]) if same else [])
            if len({x['property'] for x in styles})!=len(styles):
                raise ValueError('duplicate model style declarations')
            paper_scopes=self._paper_scopes(session_id,d)
            r=self.catalog.save(choice.spec,approval,parent=parent_ref,tex=choice.tex,sources=d.sources,
                derivation=derivation,
                provenance={'session_id':session_id,'step_id':step_id,'input_kind':d.kind,
                            'interpretation_model':s.model,
                            'transcription':d.transcription,'ambiguities_reviewed':choice.ambiguities,
                            'model_styles':styles,'paper_equations':paper_scopes,
                            'budget':self.budget_status(session_id),'review':'explicit researcher approval'})
            atomic_json(p,{'reference':r.reference})
            return r
    def inherited_matching(self,session_id,d,choice):
        """The supplied matching (Track 2) a candidate keeps from its parent revision: the parent's, where the candidate
        is the same model, else None (the auditor's UO-03: an unchanged Track 2 model had been judged without its matching, so
        its review disabled Save and approval refused it). An edited model never keeps a matching: it must be derived
        again. The page's Save and ``approve`` both judge with this one answer."""
        s=self.session(session_id)
        try:
            parent_ref=self._approved_parent(session_id,d,s.parent_catalog_reference)
            previous=self.catalog.load(parent_ref) if parent_ref else None
        except (ValueError,OSError,KeyError):
            return None                                   # an unreadable parent brings nothing; save checks it again
        return previous.derivation if previous is not None and previous.spec==choice.spec else None
    def _approved_parent(self,session_id,d,parent_ref):
        """The catalog reference of a step's nearest approved ancestor, else the session's parent revision."""
        ancestor=d
        while ancestor.parent_step:
            saved=self.folder(session_id)/'approved'/f'{ancestor.parent_step}_{ancestor.parent_candidate}.json'
            if saved.exists():
                parent_ref=json.loads(saved.read_text())['reference']
                break
            ancestor=self.load(session_id,ancestor.parent_step)
        return parent_ref
    def _paper_scopes(self,session_id,d):
        """The paper scopes along a step's chain of parents, the step's own first."""
        paper_scopes=[]
        cursor=d
        while True:
            if cursor.kind=='paper':
                paper_scopes.append(json.loads(cursor.input_text))
            if not cursor.parent_step:
                break
            cursor=self.load(session_id,cursor.parent_step)
        return paper_scopes
