"""Immutable personal selections with explicit atomic activation and rollback."""
import json
from pydantic import Field
from adroit.core.state import StrictModel
from adroit.core.evidence import content_hash
from adroit.core.chronology import utc_now
from adroit.core.checkpoint import atomic_json,run_lock
from adroit.library.experimental import ExperimentalCatalog,SHA

class Profile(StrictModel):
    """A pinned selection of reviewed inputs (private limits, a signal search, null searches) and who reviewed it;
    its id is the hash of its content."""
    profile_id: str
    name: str = Field(min_length=1)
    created_at: str
    parent: str = ''
    limits: list[str] = Field(default_factory=list)
    signal: str = ''
    null_modules: list[str] = Field(default_factory=list)
    researcher: str = Field(min_length=1)
    independence_confirmed: bool
    scope: str = 'Exact selected datasets/replacements; activation applies to fresh CLI/workbench runs, never historical studies.'

    @property
    def reference(self):
        """``profile:<id>``, the profile's pinned reference."""
        return 'profile:'+self.profile_id

def review_selection(limits,signal,nulls,catalog=None):
    """Check a selection of limits, a signal and nulls (no duplicates, no overlapping datasets or replacements, no
    superseded input still selected) and return what the reviewer confirms, with its hash."""
    catalog=catalog or ExperimentalCatalog()
    from adroit.constraints.experimental_review import load_bound as limit
    from adroit.constraints.experimental_search_review import load_bound as search
    from adroit.experiments.registry import MODULES,SIGNAL_SEARCHES
    if len(set(limits))!=len(limits) or len(set(nulls))!=len(nulls):
        raise ValueError('duplicate selected input')
    if signal and signal in nulls:
        raise ValueError('signal dataset cannot also be an independent null')
    contracts=[]
    rows=[]
    for name in limits:
        bound=limit(name,catalog)
        contracts.append(bound.contract)
        rows.append({'reference':name,'role':'limit','contract':bound.contract.model_dump(mode='json')})
    for name,role in [(signal,'signal'),*((n,'null') for n in nulls)]:
        if not name:
            continue
        if name.startswith('private-search:'):
            bound=search(name,catalog)
            if bound.contract.role!=role:
                raise ValueError('private search selected in the wrong signal/null role')
            contracts.append(bound.contract)
            rows.append({'reference':name,'role':role,'contract':bound.contract.model_dump(mode='json')})
        elif name not in (SIGNAL_SEARCHES if role=='signal' else MODULES):
            raise ValueError('profile selections require known packaged or validated private searches')
        else:
            rows.append({'reference':name,'role':role,'packaged':True})
    datasets=[c.dataset_id for c in contracts]
    if len(set(datasets))!=len(datasets):
        raise ValueError('overlapping/repeated private dataset identities cannot be combined')
    targets=[t for c in contracts for t in c.supersedes]
    if len(set(targets))!=len(targets):
        raise ValueError('multiple replacements for the same input')
    if set(targets)&set([signal,*nulls,*limits]):
        raise ValueError('superseded input remains selected; remove it explicitly')
    if any(c.overlap=='unknown' for c in contracts):
        raise ValueError('unknown dataset overlap blocks a selection profile')
    from adroit.constraints.database import records
    known=set(MODULES)|set(SIGNAL_SEARCHES)|{r.id for r in records()}
    if any(t not in known and not t.startswith(('private-search:','private-limit:')) for t in targets):
        raise ValueError('unknown replacement target')
    for target in targets:
        if target.startswith('private-search:'):
            search(target,catalog)
        elif target.startswith('private-limit:'):
            limit(target,catalog)
    return {'limits':limits,'signal':signal,'null_modules':nulls,'inputs':rows,
            'track1_policy':'Packaged constraints remain active except explicit replacements; private nulls add native-95 cuts.',
            'track2_policy':'Exact reviewed signal/null selection; private published limits pass to physical child studies (NR eligibility filtering remains M38).',
            'required_assertion':'I reviewed these exact datasets, independence, replacements and adapter/source scopes.',
            'review_sha256':content_hash({'limits':limits,'signal':signal,'null_modules':nulls,'inputs':rows})}

def create(name,limits,signal,nulls,expected_hash,researcher,*,confirmed,independence_confirmed,parent='',catalog=None):
    """Write a new profile once the reviewer has confirmed the selection and its independence, and the selection
    still has the reviewed hash."""
    catalog=catalog or ExperimentalCatalog()
    review=review_selection(limits,signal,nulls,catalog)
    if parent:
        load(parent,catalog)
    if not confirmed or not independence_confirmed or not researcher.strip():
        raise ValueError('reviewer, explicit selection/independence review and confirmation required')
    if review['review_sha256']!=expected_hash:
        raise ValueError('selection changed since review')
    profile=Profile(profile_id='0'*64,name=name,created_at=utc_now(),parent=parent,limits=limits,signal=signal,
                    null_modules=nulls,researcher=researcher.strip(),independence_confirmed=True)
    profile.profile_id=content_hash(profile.model_dump(mode='json',exclude={'profile_id'}))
    with run_lock(catalog.root):
        atomic_json(catalog.path(f'profiles/{profile.profile_id}.json'),profile.model_dump(mode='json'))
    return profile

def load(reference,catalog=None):
    """A profile from its pinned reference, refused if its content no longer matches its hash or its selection no
    longer passes review."""
    catalog=catalog or ExperimentalCatalog()
    key=reference.removeprefix('profile:')
    if not reference.startswith('profile:') or not SHA.fullmatch(key):
        raise ValueError('pinned profile identifier required')
    raw=json.loads(catalog.path(f'profiles/{key}.json').read_text())
    if raw['profile_id']!=key or content_hash({k:v for k,v in raw.items() if k!='profile_id'})!=key:
        raise ValueError('profile content modified')
    profile=Profile.model_validate(raw)
    if not profile.independence_confirmed:
        raise ValueError('profile independence was not reviewed')
    review_selection(profile.limits,profile.signal,profile.null_modules,catalog)
    return profile

DAMAGED='damaged'      # the active selection as seen when its record cannot be read (``current``, ``activate``)
REPAIR=('activate a profile, or the packaged defaults, again (the profiles page, or `adroit experiments '
        'profile-activate REFERENCE --expected-current damaged --confirmed`)')

def active(catalog=None):
    """The active profile's reference, checked on reading ('' when none is active). A record of the active selection
    that cannot be read, or that names a profile that cannot be loaded, stops whatever asked: ``DamagedRecord``, with
    what to do, never the packaged defaults in its place (the consolidation plan's M3: a run must not silently use
    other data than the selection made)."""
    from adroit.core.durable import DamagedRecord,reason
    catalog=catalog or ExperimentalCatalog()
    path=catalog.path('active_profile.json')
    if not path.exists():
        return ''
    try:
        reference=json.loads(path.read_text())['reference']
        if not isinstance(reference,str):
            raise ValueError('its reference is not a profile reference')
    except (OSError,ValueError,KeyError,TypeError) as error:
        raise DamagedRecord(path,reason(error),REPAIR) from None
    if reference:
        try:
            load(reference,catalog)
        except (OSError,ValueError,KeyError,TypeError) as error:
            raise DamagedRecord(path,f'the active profile, {reference}, cannot be used ({reason(error)})',REPAIR) from None
    return reference

def current(catalog=None):
    """The active selection as a person sees it: its reference, '' for the packaged defaults, or ``DAMAGED`` where
    its record cannot be read (``active`` says why)."""
    from adroit.core.durable import DamagedRecord
    try:
        return active(catalog)
    except DamagedRecord:
        return DAMAGED

def activate(reference,expected_current,*,confirmed,catalog=None):
    """Make a profile the active one for fresh runs ('' for none), if the active one is still the one reviewed
    (``DAMAGED``: its record, seen as unreadable, is replaced; its bytes are kept beside it)."""
    catalog=catalog or ExperimentalCatalog()
    if not confirmed:
        raise ValueError('explicit fresh-run activation/rollback confirmation required')
    if reference:
        load(reference,catalog)
    path=catalog.path('active_profile.json')
    with run_lock(catalog.root):
        if current(catalog)!=expected_current:
            raise ValueError('active selection changed since review')
        if expected_current==DAMAGED:
            from adroit.core.durable import write_atomic
            write_atomic(path.with_name(f'active_profile.json.damaged-{utc_now().replace(":","")}'),path.read_bytes())
        atomic_json(path,{'reference':reference,'activated_at':utc_now(),'previous':expected_current})
    return reference

def selected(reference,catalog=None):
    """Resolve active once at CLI/UI request creation; 'none' requests packaged defaults explicitly. With the active
    selection's record damaged, '' stops with the reason (``active``); it is never read as the defaults."""
    return '' if reference=='none' else reference or active(catalog)

def listing(catalog=None):
    """(the saved profiles that load, by reference; each profile file that cannot be loaded, named with why:
    ``durable.read_each``; the consolidation plan's M3: they had been left out without a word)."""
    from adroit.core.durable import read_each
    catalog=catalog or ExperimentalCatalog()
    folder=catalog.path('profiles')
    found,damaged=read_each(sorted(folder.glob('*.json')) if folder.is_dir() else [],
                            lambda path:load('profile:'+path.stem,catalog))
    return {p.reference:p for p in found},damaged

def apply_signal(request,catalog=None):
    """A Track 2 request with the profile's null searches; refused if its signal differs from the profile's."""
    profile=load(request.experimental_profile,catalog)
    if profile.signal and request.experiment!=profile.signal:
        raise ValueError('signal differs from the reviewed profile; create/select a profile for this signal')
    return request.model_copy(update={'null_modules':profile.null_modules})

def apply_track1(request,catalog=None):
    """A Track 1 request with the profile's private limits; refused if it names different ones."""
    profile=load(request.experimental_profile,catalog)
    if request.private_limits and request.private_limits!=profile.limits:
        raise ValueError('explicit limit selection differs from the pinned profile')
    return request.model_copy(update={'private_limits':profile.limits})
