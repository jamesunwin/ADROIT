"""Private immutable experimental drafts; no packaged-record mutations."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from adroit.core.checkpoint import atomic_json, run_lock
from adroit.core.evidence import content_hash
from adroit.core.quotes import contains
from adroit.core.experimental_input import ExperimentalAsset, ExperimentalDossier, ExperimentalRevision
from adroit.retrieval.experimental_ingestion import Ingestion, ingest

SUFFIXES={'.pdf','.csv','.tsv','.json','.yaml','.yml','.txt','.png','.jpg','.jpeg','.webp'}
TOKEN=re.compile(r'^[a-f0-9]{32}$')
SHA=re.compile(r'^[a-f0-9]{64}$')


class ExperimentalCatalog:
    """Content-bound uploads and linked, inactive dossier revisions."""
    def __init__(self,folder: Path | None=None):
        from adroit.core.config import get_settings
        self.root=Path(folder or get_settings().experimental_library_dir).absolute()

    def path(self,relative: str) -> Path:
        """Refuse redirected library paths, including symlinked ancestors."""
        if Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('invalid private catalog path')
        path=self.root/relative
        if self.root not in path.parents:
            raise ValueError('invalid private catalog path')
        for parent in (path,*path.parents):
            if parent.is_symlink():
                raise ValueError('private catalog paths must not be symlinks')
        return path

    def asset_bytes(self,name: str,data: bytes,role: str) -> ExperimentalAsset:
        """Store explicitly selected bytes without interpreting or executing them."""
        name=Path(name).name
        suffix=Path(name).suffix.lower()
        if name.startswith('.env') or suffix not in SUFFIXES or len(data)>25_000_000:
            raise ValueError('unsupported, credential or oversized experimental input')
        if suffix=='.pdf' and not data.startswith(b'%PDF-'):
            raise ValueError('invalid PDF header')
        if suffix in {'.png','.jpg','.jpeg','.webp'}:
            from adroit.core.images import opened
            with opened(data,'image format or dimensions exceed supported limits') as image:
                expected={'.png':'PNG','.jpg':'JPEG','.jpeg':'JPEG','.webp':'WEBP'}[suffix]
                if image.format!=expected or max(image.size)>8000 or image.width*image.height>16_000_000:
                    raise ValueError('image format or dimensions exceed supported limits')
                image.verify()
        asset=ExperimentalAsset(name=name,sha256=hashlib.sha256(data).hexdigest(),suffix=suffix,size_bytes=len(data),role=role)
        path=self.path(f'assets/{asset.sha256}{suffix}')
        with run_lock(self.root):
            path.parent.mkdir(exist_ok=True)
            if path.exists():
                self.asset_path(asset)
            else:
                path.write_bytes(data)
        return asset

    def asset(self,path: Path,role: str) -> ExperimentalAsset:
        """Import a bounded regular file; credentials/directories/links are refused."""
        path=Path(path)
        if path.is_symlink() or not path.is_file() or path.name.startswith('.env') or path.suffix.lower() not in SUFFIXES:
            raise ValueError('select a supported regular experimental file')
        if path.stat().st_size>25_000_000:
            raise ValueError('input exceeds 25 MB cap')
        with path.open('rb') as stream:
            data=stream.read(25_000_001)
        return self.asset_bytes(path.name,data,role)

    def asset_path(self,asset: ExperimentalAsset) -> Path:
        """Check exact stored bytes before using an original or derived artifact."""
        if asset.suffix not in SUFFIXES:
            raise ValueError('unsupported stored asset suffix')
        path=self.path(f'assets/{asset.sha256}{asset.suffix}')
        if not path.is_file() or path.stat().st_size!=asset.size_bytes:
            raise ValueError('experimental source missing or size changed')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=asset.sha256:
            raise ValueError('experimental source integrity mismatch')
        return path

    def read_asset(self,asset: ExperimentalAsset) -> bytes:
        """A stored asset's bytes, read once and checked against its digest: what is checked is what is used (the auditor's
        independent audit, NA15-08, 2026-11-16: ``asset_path`` checked A and the parser then read the file again, and
        a file replaced by B and put back saved B's numbers under A's digest)."""
        if asset.suffix not in SUFFIXES:
            raise ValueError('unsupported stored asset suffix')
        path=self.path(f'assets/{asset.sha256}{asset.suffix}')
        if path.is_symlink() or not path.is_file():
            raise ValueError('experimental source missing or size changed')
        with path.open('rb') as stream:
            data=stream.read(asset.size_bytes+1)
        if len(data)!=asset.size_bytes:
            raise ValueError('experimental source missing or size changed')
        if hashlib.sha256(data).hexdigest()!=asset.sha256:
            raise ValueError('experimental source integrity mismatch')
        return data

    def ingestion(self,asset: ExperimentalAsset) -> Ingestion:
        """Read a hashed ingestion record (one checked read, ``read_asset``) and verify its page previews."""
        if asset.role!='ingestion':
            raise ValueError('selected artifact is not an ingestion record')
        result=Ingestion.model_validate_json(self.read_asset(asset).decode())
        for page in result.pages:
            if page.preview:
                self.asset_path(page.preview)
        return result

    def load(self,reference: str) -> ExperimentalRevision:
        """Resolve an exact experiment/revision; never select an implicit latest."""
        if not reference.startswith('experimental:'):
            raise ValueError('a pinned experimental reference is required')
        key,sep,revision=reference.removeprefix('experimental:').partition('@')
        if not sep or not TOKEN.fullmatch(key) or not SHA.fullmatch(revision):
            raise ValueError('invalid experimental reference')
        from adroit.core.durable import DamagedRecord,reason
        path=self.path(f'experiments/{key}/{revision}.json')
        text=path.read_text()
        try:
            raw=json.loads(text)
            result=ExperimentalRevision.model_validate(raw)
        except ValueError as error:            # damaged: it stops what uses it, named (M3)
            raise DamagedRecord(path,reason(error),'repair or move it, or choose another revision') from None
        # Additive schema defaults must not change historical content identities.
        if result.experiment_id!=key or result.revision_id!=revision or content_hash({k:v for k,v in raw.items() if k!='revision_id'})!=revision:
            raise DamagedRecord(path,'experimental revision integrity mismatch','choose another revision')
        self.validate_sources(result.dossier,result.sources,result.ingestions)
        return result

    def validate_sources(self,dossier: ExperimentalDossier,sources: list[ExperimentalAsset],ingestions: list[ExperimentalAsset]) -> None:
        """Validate file/page/table locators without asserting scientific entailment."""
        originals={a.sha256:a for a in sources}
        for asset in sources:
            self.asset_path(asset)
        parsed={}
        for asset in ingestions:
            item=self.ingestion(asset)
            if item.source_sha256 not in originals:
                raise ValueError('ingestion refers to an unselected source')
            parsed[item.source_sha256]=item
        for claim in [*dossier.claims,*(c for r in dossier.results for c in r.claims)]:
            for loc in claim.sources:
                if loc.asset_sha256 not in originals:
                    raise ValueError('claim refers to an unselected source')
                item=parsed.get(loc.asset_sha256)
                if item and item.kind=='pdf' and claim.status in ('sourced','converted','digitised') and loc.page is None:
                    raise ValueError('extracted PDF evidence needs a physical page')
                if loc.page is not None:
                    if not item or item.kind!='pdf' or loc.page>item.page_count:
                        raise ValueError('claim page not in selected document')
                    page=item.pages[loc.page-1]
                    box=page.media_box or (0,0,page.width_pt,page.height_pt)
                    if loc.region and not (box[0]<=loc.region[0]<loc.region[2]<=box[2] and box[1]<=loc.region[1]<loc.region[3]<=box[3]):
                        raise ValueError('claim region outside PDF page')
                    if loc.method!='visual' and loc.excerpt and not contains(page.text,loc.excerpt,case_sensitive=True):
                        raise ValueError('claim excerpt absent from selected page text')
                if loc.method=='visual':
                    if loc.page is None and (not item or item.kind!='image'):
                        raise ValueError('visual evidence needs a selected PDF page or original image')
                    if loc.region is None and loc.page is not None:
                        raise ValueError('visual PDF evidence needs a page region')
                if loc.row is not None and (not item or not item.table or loc.row>len(item.table.rows)):
                    raise ValueError('claim row not in selected machine table')
                if loc.column and (not item or not item.table or loc.column not in item.table.columns):
                    raise ValueError('claim column not in selected machine table')

    def save(self,dossier: ExperimentalDossier,sources: list[ExperimentalAsset],ingestions: list[ExperimentalAsset],
             parent: str='',provenance: dict | None=None) -> ExperimentalRevision:
        """Create an inactive unreviewed revision; no approval/activation entry point."""
        dossier=ExperimentalDossier.model_validate(dossier.model_dump(mode='json'))
        self.validate_sources(dossier,sources,ingestions)
        prior=self.load(parent) if parent else None
        from adroit.core.config import PROJECT_ROOT
        from adroit.orchestrator.track1_identity import tree_identity
        body=dict(experiment_id=prior.experiment_id if prior else uuid4().hex,
                  parent_revision=prior.revision_id if prior else '',created_at=datetime.now(timezone.utc),
                  dossier=dossier,sources=sources,ingestions=ingestions,
                  provenance={**(provenance or {}),'code_sha256':tree_identity(PROJECT_ROOT/'adroit'),
                              'origin':'explicit private experimental draft'})
        result=ExperimentalRevision(revision_id='0'*64,**body)
        result.revision_id=content_hash(result.model_dump(mode='json',exclude={'revision_id'}))
        path=self.path(f'experiments/{result.experiment_id}/{result.revision_id}.json')
        with run_lock(self.root):
            if path.exists():
                raise ValueError('experimental revisions cannot be overwritten')
            atomic_json(path,result.model_dump(mode='json'))
        return result

    def import_files(self,paths: list[Path],title: str,*,parent: str='',preview_pages: list[int] | None=None,
                     dossier: ExperimentalDossier | None=None,names: list[str] | None=None,
                     provenance: dict | None=None) -> ExperimentalRevision:
        """Import paper/supplements/data as one bounded, reviewable draft revision (``provenance``: where the files
        came from, e.g. a discovery session's retrieval)."""
        if not 1<=len(paths)<=20:
            raise ValueError('select one to twenty input files')
        if names and len(names)!=len(paths):
            raise ValueError('source names must match selected files')
        prior=self.load(parent) if parent else None
        sources=list(prior.sources) if prior else []
        ingestions=list(prior.ingestions) if prior else []
        for index,path in enumerate(paths):
            suffix=path.suffix.lower()
            role=('supplement' if any(a.role=='paper' for a in sources) else 'paper') if suffix=='.pdf' else (
                 'image' if suffix in {'.png','.jpg','.jpeg','.webp'} else 'data')
            asset=self.asset(path,role)
            if names:
                name=Path(names[index]).name
                if name.startswith('.env') or Path(name).suffix.lower()!=asset.suffix:
                    raise ValueError('invalid source display name')
                asset=asset.model_copy(update={'name':name})
            same=next((a for a in sources if a.sha256==asset.sha256),None)
            if same:
                if same.suffix!=asset.suffix:
                    raise ValueError('identical source bytes have conflicting declared formats')
                continue
            item=self._ingested(asset,preview_pages)
            parsed=self.asset_bytes(asset.sha256+'.json',item.model_dump_json().encode(),'ingestion')
            sources.append(asset)
            ingestions.append(parsed)
        content=dossier or (prior.dossier.model_copy(deep=True,update={'title':title}) if prior else ExperimentalDossier(title=title))
        return self.save(content,sources,ingestions,parent,provenance)

    def _ingested(self,asset: ExperimentalAsset,preview_pages: list[int] | None) -> Ingestion:
        """The asset ingested from one checked read of its bytes (``read_asset``), put in a private folder for the
        parsers that take a path (a PDF's text and pages): nothing else can replace it there (NA15-08)."""
        import tempfile
        data=self.read_asset(asset)
        with tempfile.TemporaryDirectory(prefix='adroit-ingest-') as folder:
            snapshot=Path(folder)/f'source{asset.suffix}'
            snapshot.write_bytes(data)
            return ingest(snapshot,asset,preview_pages,self.asset_bytes)

    def list(self,query: str='') -> list[ExperimentalRevision]:
        """List every immutable revision matching a title/analysis query; a damaged one raises (``listing`` names it
        instead, for a page or a list; a calculation over the library stops on it)."""
        folder=self.path('experiments')
        results=[self.load(f'experimental:{p.parent.name}@{p.stem}') for p in folder.glob('*/*.json')]
        return sorted((r for r in results if query.lower() in (r.dossier.title+' '+r.dossier.analysis).lower()),key=lambda r:r.created_at)

    def listing(self,query: str=''):
        """(``list``'s revisions that can be read, in its order; each revision file that cannot be read, named with
        why: ``durable.read_each``). For browsing (the consistency audit's CA-07, 2026-10-24: one damaged revision
        had stopped the library's page). Loading a revision (``load``) stays strict."""
        from adroit.core.durable import read_each
        found,damaged=read_each(sorted(self.path('experiments').glob('*/*.json')),
                                lambda p:self.load(f'experimental:{p.parent.name}@{p.stem}'))
        return sorted((r for r in found if query.lower() in (r.dossier.title+' '+r.dossier.analysis).lower()),
                      key=lambda r:r.created_at),damaged

    def report(self,reference: str) -> str:
        """Dated ingestion coverage report; never call a draft a current limit."""
        result=self.load(reference)
        lines=[f'# Experimental draft: {result.dossier.title}', '',f'Revision saved (UTC): {result.created_at.isoformat()}',
               f'Reference: `{result.reference}`',f'Parent: `{result.parent_revision or "none"}`','',
               '**Unreviewed; adapter not validated; inactive. No physics calculation performed.**',
               'This dated revision is historical input evidence, not a statement of today’s limits.','',
               '| Source | Type | Coverage |','|---|---|---|']
        for asset in result.ingestions:
            item=self.ingestion(asset)
            summary=f'{item.page_count} pages; '+str(sum(p.status!='text_extracted' for p in item.pages))+' require visual review' if item.kind=='pdf' else (
                    f'{len(item.table.rows)} literal rows' if item.table else 'stored; interpretation pending')
            lines.append(f'| `{item.source_sha256}` | {item.kind} | {summary} |')
        lines+=['','## Completeness','']+[f'- {c.category}/{c.key}: {c.status}' for c in result.dossier.claims]
        return '\n'.join(lines)+'\n'
