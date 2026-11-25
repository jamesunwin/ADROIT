"""Private immutable model revisions and content-bound source assets."""
from __future__ import annotations

from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from pydantic import Field

from adroit.core.checkpoint import atomic_json,run_lock
from adroit.core.evidence import content_hash
from adroit.core.model_spec import ModelSpec
from adroit.core.state import StrictModel
from adroit.library.interactions.derivation import Derivation
from adroit.orchestrator.model_approval import SCHEMA_VERSION,ModelApproval,model_identity,verify_identity

TOKEN=re.compile(r'^[a-f0-9]{32}$')
DIGEST=re.compile(r'^[a-f0-9]{64}$')
SOURCE_TYPES={'.tex','.txt','.yaml','.yml','.json','.png','.jpg','.jpeg','.webp','.gif','.pdf'}


def root() -> Path:
    """The personal model library's folder (``model_library_dir`` in the settings)."""
    from adroit.core.config import get_settings
    return get_settings().model_library_dir.resolve()


class Asset(StrictModel):
    """A source file stored in the catalog under its SHA-256: its name, suffix, size and role."""
    name: str
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    suffix: str
    size_bytes: int = Field(ge=0,le=25_000_000)
    role: str = 'user_source'


class ModelRevision(StrictModel):
    """One immutable revision of a personal model: the spec, its approval, TeX, sources, matching and provenance; its
    id is the hash of its content."""
    model_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    revision_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    parent_revision: str = ''
    created: str
    spec: ModelSpec
    model_sha256: str
    approval: ModelApproval
    tex: str = ''
    sources: list[Asset] = Field(default_factory=list)
    derivation: Derivation | None = None
    provenance: dict = Field(default_factory=dict)
    applicability: dict = Field(default_factory=dict)
    schema_version: int | None = None       # its model's schema era; None: written before 2026-10-16

    @property
    def reference(self):
        """``catalog:<model_id>@<revision_id>``, the revision's pinned reference."""
        return f'catalog:{self.model_id}@{self.revision_id}'


def support(spec: ModelSpec,derivation=None) -> dict:
    """What the engines can do with a model: the structural audit, the parameters still missing, and whether a portal
    class covers it (Tracks 1 and 2) or only a supplied matching (Track 2)."""
    from adroit.model_building.audit import audit
    from adroit.parameter_space.classify import classify,Unsupported
    # a mass the model's scalar-potential contract determines (its validator requires its basis complete) is given
    # (2026-11-21: the example complete_scalar_running.yaml had been called incomplete, and refused at its run)
    contracted={spec.scalar_potential.singlet_field} if spec.scalar_potential is not None else set()
    # a scalar with a vacuum value takes its mass from the potential, and a vector it Higgses from g q v (G1's
    # convention; L-2, 2026-11-21: both had been called missing, so a dark Higgs's mass had to be stated, then ignored)
    contracted|=vacuum_given(spec)
    missing=[f'mass of {f.name}' for f in spec.fields
             if f.role.value!='standard_model' and f.mass_gev is None and not f.masses_gev     # per generation (L-10)
             and f.name not in contracted]
    missing += [f'coefficient {c.name}' for c in spec.couplings if c.value is None]
    a=audit(spec)
    data={'structural_valid':a.valid,'track1_engine':False,'track2_engine':False,
        'missing_parameters':missing,'numerically_declared':not missing,
        'scope':'engine mapping and its relic domain at the reference point; backend availability and constraints '
                'checked at execution',
        'problems':[p.model_dump(mode='json') for p in a.problems]}
    try:
        cls,p,notes=classify(spec)
        data.update(track1_engine=True,track2_engine=True,engine=cls.model_dump(mode='json'),
                    reference_point=p.model_dump(mode='json'),notes=notes)
    except Unsupported as error:
        data.update(reason=str(error),track2_engine=derivation is not None)
        return data
    if not missing:
        data['reference_domain']=_reference_domain(cls,p)
    return data


def vacuum_given(spec: ModelSpec) -> set[str]:
    """The new fields whose mass the vacuum gives: scalars with a vacuum value, and the vectors their currents join."""
    with_vev={f.name for f in spec.fields if f.spin==0 and f.vev_gev}
    higgsed={o.field for t in spec.terms if t.lorentz=='scalar_current' and any(o.field in with_vev for o in t.fields)
             for o in t.fields if spec.field(o.field).spin==1}
    return {n for n in with_vev|higgsed if spec.field(n).role.value!='standard_model'}


def _reference_domain(engine,point) -> str:
    """Why the engine does not compute Ωh² at the model's own values ("" where it does): its ``domain`` (no
    annihilation channel, a partner lighter than the dark matter, a mass outside the validated range, a coupling below
    the route's resolution; the auditor's UM-01, 2026-11-21: a mapped model had been called runnable without this)."""
    try:
        return engine.domain(point)
    except (ValueError,ArithmeticError,RuntimeError,KeyError) as error:
        return f'its engine could not check the stated point: {error}'


def _silent(derivation,spec) -> str:
    """Why a model's own matching predicts no signal ("" where it predicts one): every quark-level coefficient it gives
    is zero at the model's stated values (the owner, 2026-11-21: a Track 2 model needs no Track 1 engine, but a dark
    sector its couplings leave joined to nothing cannot run on any track). A formula that cannot be evaluated is left
    to ``Catalog.save``'s own checks, which name its problem."""
    from adroit.library.interactions.derivation import NotFinite,evaluate
    try:
        coefficients=evaluate(derivation,spec).coefficients
    except NotFinite as error:          # the auditor's UO-02: a pole, 0/0 or an overflow had been saved as a signal
        return f'its own matching has no finite value at the stated values: {error}'
    except (ValueError,ArithmeticError,TypeError,KeyError,AttributeError):
        return ''
    if any(v!=0 for v in coefficients.values()):
        return ''
    named=', '.join(coefficients) or 'it gives none'
    return (f'its own matching gives every quark-level coefficient as zero at the stated values ({named}), so it '
            'predicts no signal: give a non-zero value to a coupling that joins the dark matter to the quarks')


NOT_SAVED='this model cannot run yet, so it is not saved: '


class Usability(StrictModel):
    """Whether a model can be offered and saved by the model-building step (the owner, 2026-11-21: "it is acceptable
    to present a model that cannot run because of a missing constraint, but not one that cannot run because of a
    missing coupling or parameter"; the usable models plan): ``blocking`` says why not, in plain words."""
    ok: bool
    blocking: list[str] = Field(default_factory=list)


def usable(spec: ModelSpec, derivation=None, ready: dict | None = None, track1: bool | None = None) -> Usability:
    """A model is usable when its structural audit passes, every mass and coupling has a value, and an engine computes
    it for Constrain a model (a class, a portal, a contract or the generic route) at its own values: the engine's
    relic domain at the reference point (``support``'s ``reference_domain``; the auditor's UM-01). A search that will be
    undecided at execution does not block it.

    Args:
        ready: ``support``'s answer, if computed now (never a stored one: an older draft's lacks the domain).
        track1: whether Constrain a model is required; by default it is unless the model brings its own matching
            (``derivation``: a Track 2 model, kept in the library as before; the owner confirmed this, 2026-11-21).
            A missing value always blocks, and so does a matching whose every coefficient is zero at the stated values.
    """
    ready = support(spec, derivation) if ready is None else ready
    track1 = derivation is None if track1 is None else track1
    blocking = [f'no value for the {p}' for p in ready['missing_parameters']]
    if not ready['structural_valid']:
        blocking.append('the structural audit found problems: '
                        + '; '.join(p.get('message', str(p)) for p in ready['problems']))
    if track1 and not ready['missing_parameters']:
        from adroit.model_building.usable_models import unreachable
        if not ready['track1_engine']:
            blocking.append('no engine computes it: ' + (ready.get('reason') or 'no route'))
        elif 'reference_domain' not in ready:
            blocking.append('its engine has not checked the stated point (an older record: check it again)')
        elif ready['reference_domain']:
            blocking.append('its engine does not compute it at the stated values: ' + ready['reference_domain'])
        if lost := unreachable(spec):            # a zero-valued current is not a coupling (the auditor's UM-01)
            blocking.append(lost)
    if derivation is not None and not ready['missing_parameters'] and (silent := _silent(derivation, spec)):
        blocking.append(silent)                  # Track 2's own matching, all zero (the owner, 2026-11-21)
    return Usability(ok=not blocking, blocking=blocking)


class MissingRevision(FileNotFoundError, ValueError):
    """A pinned revision that is not in the library (deleted, or never there): a ``ValueError`` too, so that every page
    and command that refuses a bad reference says so instead of failing."""


class Catalog:
    """The personal model library on disk: immutable model revisions and the source files they cite."""
    def __init__(self,folder: Path | None = None):self.root=Path(folder or root()).resolve()

    def asset(self,path: Path,role='user_source') -> Asset:
        """Store a regular source file (TeX, text, model, image or PDF, at most 25 MB) and return its record; links,
        folders and credentials are refused."""
        path=Path(path)
        if path.is_symlink() or not path.is_file() or path.name.startswith('.env') or path.suffix.lower() not in SOURCE_TYPES:
            raise ValueError('select a regular TeX/text/model/image source file; credentials and directories are refused')
        if path.stat().st_size>25_000_000:
            raise ValueError('source exceeds 25 MB cap')
        with path.open('rb') as stream:
            data=stream.read(25_000_001)
        return self.asset_bytes(path.name,data,role)

    def asset_bytes(self,name: str,data: bytes,role='user_source') -> Asset:
        """Store a source's bytes under their SHA-256, after checking the type, the size and, for an image, its
        encoding and dimensions."""
        name=Path(name).name
        suffix=Path(name).suffix.lower()
        if name.startswith('.env') or suffix not in SOURCE_TYPES or len(data)>(25_000_000 if suffix=='.pdf' else 8_000_000):
            raise ValueError('unsupported or oversized source asset')
        if suffix=='.pdf' and not data.startswith(b'%PDF-'):
            raise ValueError('invalid PDF header')
        if suffix in {'.png','.jpg','.jpeg','.webp','.gif'}:
            from adroit.core.images import opened
            with opened(data,'source image dimensions exceed supported limits') as im:
                if max(im.size)>8000 or im.width*im.height>64_000_000:
                    raise ValueError('source image dimensions exceed supported limits')
                expected={'.png':'PNG','.jpg':'JPEG','.jpeg':'JPEG','.webp':'WEBP','.gif':'GIF'}[suffix]
                if im.format!=expected:
                    raise ValueError('image encoding does not match its file suffix')
                im.verify()
        h=hashlib.sha256(data).hexdigest()
        p=self.root/'assets'/f'{h}{suffix}'
        with run_lock(self.root):
            p.parent.mkdir(exist_ok=True)
            if p.exists():
                if hashlib.sha256(p.read_bytes()).hexdigest()!=h:
                    raise ValueError('catalog source integrity mismatch')
            else:
                p.write_bytes(data)
        return Asset(name=name,sha256=h,suffix=suffix,size_bytes=len(data),role=role)

    def asset_path(self,asset: Asset) -> Path:
        """The stored file of an asset, refused if missing or no longer matching its hash."""
        if asset.suffix not in SOURCE_TYPES:
            raise ValueError('unsupported stored asset type')
        p=self.root/'assets'/f'{asset.sha256}{asset.suffix}'
        if p.is_symlink() or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=asset.sha256:
            raise ValueError('catalog source missing or modified')
        return p

    def load(self,reference: str) -> ModelRevision:
        """A revision from its pinned ``catalog:model_id@revision_id`` reference, with its hash, the model's identity
        and its sources checked."""
        model_id,sep,revision=reference.removeprefix('catalog:').partition('@')
        if not sep or not TOKEN.fullmatch(model_id) or not DIGEST.fullmatch(revision):
            raise ValueError('a pinned catalog:model_id@revision_id reference is required')
        p=self.root/'models'/model_id/'revisions'/f'{revision}.json'
        if p.is_symlink():
            raise ValueError('catalog revision must not be a symlink')
        if not p.exists():
            raise MissingRevision(f'{reference}: no such model revision in the personal library (it may have been '
                                  'deleted)')
        from adroit.core.durable import DamagedRecord,reason
        text=p.read_text()
        try:
            raw=json.loads(text)
            result=ModelRevision.model_validate(raw)
        except ValueError as error:            # damaged: it stops what uses it, named (M3)
            raise DamagedRecord(p,reason(error),'repair or move it, or choose another revision') from None
        # the stored content as written, not re-serialised through today's schema: a field added since (with its
        # default) had changed the hash of every earlier revision (the owner's 500 errors, 2026-10-15)
        if (result.model_id!=model_id or result.revision_id!=revision or
            content_hash({k:v for k,v in raw.items() if k!='revision_id'})!=revision):
            raise DamagedRecord(p,'catalog revision integrity mismatch','choose another revision')
        verify_identity(result.spec,result.model_sha256,result.schema_version)
        verify_identity(result.spec,result.approval.model_sha256,result.approval.schema_version)
        for asset in result.sources:
            self.asset_path(asset)
        return result

    def revisions(self,model_id: str) -> list[ModelRevision]:
        """A model's revisions, oldest first."""
        if not TOKEN.fullmatch(model_id):
            raise ValueError('invalid model identifier')
        return sorted((self.load(f'catalog:{model_id}@{p.stem}') for p in
                       (self.root/'models'/model_id/'revisions').glob('*.json')),key=lambda r:(r.created,r.revision_id))

    def list(self,query='') -> list[ModelRevision]:
        """Every revision whose model name, TeX or source contains the query (ignoring case); a damaged one raises
        (``listing`` names it instead, for a page or a list)."""
        revisions=[]
        for folder in sorted((self.root/'models').glob('*')):
            if folder.is_dir() and TOKEN.fullmatch(folder.name):
                revisions.extend(self.revisions(folder.name))
        return [r for r in revisions if query.lower() in (r.spec.name+' '+r.tex+' '+r.spec.source).lower()]

    def listing(self,query=''):
        """(``list``'s revisions that can be read, in its order; each revision file that cannot be read, named with
        why: ``durable.read_each``). For browsing: the consistency audit's CA-07 (2026-10-24): one damaged revision
        had stopped the whole library's page and its pickers. Loading a revision (``load``) stays strict."""
        from adroit.core.durable import read_each
        paths=[p for folder in sorted((self.root/'models').glob('*')) if folder.is_dir() and TOKEN.fullmatch(folder.name)
               for p in sorted((folder/'revisions').glob('*.json'))]
        found,damaged=read_each(paths,lambda p:self.load(f'catalog:{p.parent.parent.name}@{p.stem}'))
        found.sort(key=lambda r:(r.model_id,r.created,r.revision_id))
        return [r for r in found if query.lower() in (r.spec.name+' '+r.tex+' '+r.spec.source).lower()],damaged

    def save(self,spec:ModelSpec,approval:ModelApproval,*,parent:str='',tex:str='',sources=None,
             derivation=None,provenance=None) -> ModelRevision:
        """Write a new immutable revision of an approved, structurally audited model that can run (``usable``: every
        value given, and Constrain a model computing it unless it brings its own matching; the owner, 2026-11-21, and
        the auditor's UM-02: ``models import`` had saved models with missing couplings). A supplied matching is checked
        first. Older revisions that cannot run stay readable (``load``)."""
        from adroit.model_building.audit import audit
        verify_identity(spec,approval.model_sha256,approval.schema_version)
        if not audit(spec).valid:
            raise ValueError('only structurally audited models can be approved into the catalog')
        ready=support(spec,derivation)
        verdict=usable(spec,derivation,ready=ready)
        if not verdict.ok:
            raise ValueError(NOT_SAVED+'; '.join(verdict.blocking))
        if derivation is not None:
            from adroit.library.interactions.derivation import dimension_problems,evaluate
            problems=dimension_problems(derivation,spec)
            if problems:
                raise ValueError('provided matching has dimension/symbol problems: '+str(problems))
            evaluate(derivation,spec)
        prior=self.load(parent) if parent else None
        model_id=prior.model_id if prior else uuid4().hex
        assets=list(sources or [])
        for asset in assets:
            self.asset_path(asset)
        from adroit.core.config import PROJECT_ROOT
        from adroit.orchestrator.track1_identity import tree_identity
        origin={'tool_source_sha256':tree_identity(PROJECT_ROOT/'adroit'),**(provenance or {})}
        payload=dict(model_id=model_id,parent_revision=prior.revision_id if prior else '',
            created=datetime.now(timezone.utc).isoformat(),spec=spec.model_dump(mode='json'),
            # the revision's own identity in the current era, which its schema_version names; an older era's approval
            # is kept as written, its own version beside it (the external audit of 2026-10-17, I17-1: the approval's
            # era-1 hash had been stored under version 2, so the revision could not be loaded or listed)
            model_sha256=model_identity(spec),approval=approval.model_dump(mode='json'),tex=tex,
            sources=[a.model_dump(mode='json') for a in assets],
            derivation=derivation.model_dump(mode='json') if derivation else None,
            provenance=origin,applicability=ready,schema_version=SCHEMA_VERSION)
        revision=content_hash(payload)
        result=ModelRevision(revision_id=revision,**payload)
        p=self.root/'models'/model_id/'revisions'/f'{revision}.json'
        with run_lock(self.root):
            if p.exists():
                raise ValueError('immutable revision already exists')
            atomic_json(p,result.model_dump(mode='json'))
        return result

    def export_model(self,reference: str,path:Path) -> ModelRevision:
        """Write a revision's spec, approval, matching and catalog provenance to a new YAML file."""
        import yaml
        r=self.load(reference)
        payload={'spec':r.spec.model_dump(mode='json'),'approval':r.approval.model_dump(mode='json'),
            'catalog_reference':r.reference,'catalog_provenance':r.model_dump(mode='json',exclude={'spec','approval','derivation'})}
        if r.derivation:
            payload['derivation']=r.derivation.model_dump(mode='json')
        path=Path(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists() or path.is_symlink():
            raise ValueError('model export cannot overwrite an existing file')
        from adroit.core.durable import write_new   # its own new entry, never replacing one written since (DL-05)
        try:
            write_new(path,yaml.safe_dump(payload,sort_keys=False,allow_unicode=True))
        except FileExistsError:
            raise ValueError(f'model export cannot overwrite an existing file: {path} was written meanwhile') from None
        return r

    def verify_calculation(self,reference:str,spec:ModelSpec,track:str,derivation=None) -> ModelRevision:
        """The pinned revision, if the calculation's spec (and, for Track 2, its matching) is the revision's, every
        parameter is declared, and an engine supports the track."""
        r=self.load(reference)
        if r.spec!=spec or (track=='track2' and r.derivation!=derivation):
            raise ValueError('calculation inputs differ from the pinned catalog revision')
        current=support(spec,derivation)
        if not current['numerically_declared']:
            raise ValueError('catalog model has unresolved parameters: '+', '.join(current['missing_parameters']))
        if not current[f'{track}_engine']:
            raise ValueError(f'catalog model has no supported {track} engine: '+current.get('reason','matching unavailable'))
        return r
