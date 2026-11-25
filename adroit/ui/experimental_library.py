"""Private experimental uploads and dated source/dossier views; no activation."""
from pathlib import Path
import base64
from urllib.parse import urlencode

from nicegui import ui

from adroit.core.experimental_input import ExperimentalDossier
from adroit.library.experimental import ExperimentalCatalog
from adroit.ui import engine,forms,submission


def catalog_page(root: Path) -> None:
    """List immutable drafts and upload paper/supplement/data files for ingestion."""
    from adroit.ui.pages import header
    header('Add a limit',"Upload an experiment's paper, its supplement, tables or figures. ADROIT keeps them as a private "
           "draft that you read, interpret (optionally with a language model) and review; a reviewed limit can then be "
           "selected in Constrain a model, and a reviewed signal in Signal best fits.",
           facts=('$0 to upload','interpreting with a language model is paid','nothing is used until you review it'),
           details=('An upload makes an inactive draft: no provider is called, nothing is approved, and no calculation '
                    'changes.','A search with events can also be written directly on Add a signal.'))
    catalog=ExperimentalCatalog()
    _upload_form(root,catalog)
    _draft_list(catalog)


def _upload_form(root: Path,catalog: ExperimentalCatalog) -> None:
    """The title, a written description, the files, and the ingestion ($0)."""
    from adroit.ui.pages import rel
    from adroit.ui.style import hint
    title=ui.input('Analysis title').classes('w-full')
    description=ui.textarea('Written experimental description (optional)').classes('w-full')
    previews=hint(ui.input('Preview PDF pages',value='1'),'physical page numbers, comma separated (up to 12), shown as images to read')
    uploads=[]
    async def upload(event):
        try:
            name=event.file.name
            role='paper' if Path(name).suffix.lower()=='.pdf' else 'data'
            asset=catalog.asset_bytes(name,await event.file.read(),role)
            if len(uploads)>=20:
                raise ValueError('select at most twenty files')
            uploads.append(asset)
            ui.notify('Stored private source: '+asset.name)
        except (ValueError,OSError) as error:
            ui.notify(str(error))
    ui.upload(label='Paper PDF, supplementary PDF, tables or images',on_upload=upload,auto_upload=True,
              max_file_size=25_000_000,multiple=True).props('accept=.pdf,.csv,.tsv,.json,.yaml,.yml,.txt,.png,.jpg,.jpeg,.webp')
    def begin():
        try:
            if (description.value or '').strip():
                asset=catalog.asset_bytes('description.txt',description.value.encode(),'data')
                if not any(a.sha256==asset.sha256 for a in uploads):
                    uploads.append(asset)
            if not uploads or not (title.value or '').strip():
                raise ValueError('give an analysis title and select source files')
            folder=forms.new_folder(root,'experimental_intake',title.value)
            cmd=['experiments','import',*[str(catalog.asset_path(a)) for a in uploads],
                 '--title',title.value,'--preview-pages',previews.value or '', '--out',str(folder)]
            for asset in uploads:
                cmd+=['--source-name',asset.name]
            job=engine.launch(cmd,folder,'Ingest experimental sources',confirmed_budget=0)
            submission.go('/live?path='+rel(root,job.folder))
        except (ValueError,OSError) as error:
            ui.notify(str(error))
    ui.button('Ingest sources ($0)',on_click=submission.once(begin)).props('color=primary')


def _draft_list(catalog: ExperimentalCatalog) -> None:
    """The saved drafts, searchable, each with its date and its draft badge."""
    from adroit.ui.style import term,when
    with ui.row().classes('items-center gap-2 mt-4'):
        ui.label('Your experimental drafts').classes('text-lg font-medium')
        term('dossier')
    query=ui.input('Find an experimental draft').classes('w-full')
    @ui.refreshable
    def rows():
        found,damaged=catalog.listing(query.value or '')
        from adroit.ui.pages import _damaged
        _damaged(None,'experimental revision(s)',damaged,'unreadable_revisions')      # CA-07
        if not found:
            ui.label('None yet: upload a paper above.').classes('text-gray-500')
        for revision in found:
            with ui.row().classes('items-baseline gap-2'):
                ui.link(revision.dossier.title,'/experiments/view?'+urlencode({'reference':revision.reference}))
                ui.label(f'saved {when(revision.created_at)}').classes('text-sm text-gray-600')
                with ui.badge('draft',color='grey'):
                    ui.tooltip('Not used by any run until its limit or signal is reviewed and selected').classes('text-sm')
    rows()
    query.on_value_change(lambda _:rows.refresh())


def revision_page(root: Path,reference: str) -> None:
    """Review original pages/literal data and save deterministic dossier edits."""
    from adroit.ui.pages import header
    catalog=ExperimentalCatalog()
    revision=catalog.load(reference)
    header(revision.dossier.title,"One saved reading of an experiment's sources: the pages and data as read, and the "
           "dossier (each value with its unit, status and source). Interpret it, correct it, then review a limit or a "
           "signal from it, which is what a run can use.",
           details=('This revision records the inputs available when it was saved; later experimental updates need a '
                    'new analysis.',))
    _status_strip(revision)
    for asset in revision.ingestions:
        _source_view(catalog,revision,asset)
    _claims_table(revision.dossier)
    content=_json_editor(catalog,revision,reference)
    from adroit.ui.experimental_assistance import revision_tools
    revision_tools(root,catalog,revision,content)
    from adroit.ui.experimental_review import review_tools
    review_tools(root,catalog,revision,content)


def _status_strip(revision) -> None:
    """The revision's reference and date, and where it stands: draft → interpreted → reviewed → selectable."""
    from adroit.ui.style import short_ref,when
    with ui.row().classes('items-center gap-4'):
        short_ref(revision.reference,'revision')
        ui.label(f'saved {when(revision.created_at)}'+('' if not revision.parent_revision else ' · refines an earlier '
                 'revision')).classes('text-gray-600')
    with ui.row().classes('items-center gap-1'):
        for n,(step,done) in enumerate((('Draft',True),('Interpreted',bool(revision.dossier.results)),
                                        ('Reviewed',False),('Selectable in a run',False))):
            if n:
                ui.icon('chevron_right').classes('text-gray-400')
            ui.badge(step,color='green' if done else 'grey-4').props('text-color='+('white' if done else 'grey-9'))
    ui.label('Review and validation happen per result, below; a reviewed result is then offered on the run pages.') \
        .classes('text-sm text-gray-600')


def _source_view(catalog: ExperimentalCatalog,revision,asset) -> None:
    """One source as read: its pages (image and text), its table or structured data, its text or its image."""
    item=catalog.ingestion(asset)
    original=next(a for a in revision.sources if a.sha256==item.source_sha256)
    with ui.expansion(f'Source: {original.name}').classes('w-full'):
        ui.label(f'file identity (SHA-256): {original.sha256}').classes('text-xs font-mono text-gray-500')
        for note in item.notes:
            ui.label(note)
        for page in item.pages:
            with ui.expansion(f'Physical page {page.page}: {page.status}').classes('w-full'):
                if page.preview:
                    ui.image('data:image/png;base64,'+base64.b64encode(catalog.read_asset(page.preview)).decode())
                ui.code(page.text or 'No readable text; visual interpretation required.').classes('w-full')
                for note in page.notes:
                    ui.label(note)
        if item.table:
            ui.code(item.table.model_dump_json(indent=2),language='json')
        elif item.kind=='structured':
            ui.code(item.model_dump_json(indent=2),language='json')
        elif item.kind=='text':
            ui.code(item.text)
        elif item.kind=='image':
            mime={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp'}[original.suffix]
            ui.image('data:'+mime+';base64,'+base64.b64encode(catalog.read_asset(original)).decode())


def _json_editor(catalog: ExperimentalCatalog,revision,reference: str):
    """The dossier as JSON, folded, saved as a new inactive draft revision; returns the editor."""
    def save():
        try:
            dossier=ExperimentalDossier.model_validate_json(content.value)
            updated=catalog.save(dossier,revision.sources,revision.ingestions,parent=reference)
            ui.navigate.to('/experiments/view?'+urlencode({'reference':updated.reference}))
        except (ValueError,OSError) as error:
            ui.notify(str(error))
    with ui.expansion('Edit the dossier as JSON').classes('w-full'):
        content=ui.textarea('Dossier JSON (scientific interpretation remains unreviewed)',
                            value=revision.dossier.model_dump_json(indent=2)).classes('w-full font-mono').props('rows=20')
        ui.button('Save as a new inactive draft revision',on_click=save)
    return content


def _locator(src) -> str:
    """Where a value comes from, in words: page, section, table, figure, row."""
    parts=[f'p.{src.page}' if src.page else '',src.section,src.table and 'table '+src.table,
           src.figure and 'fig. '+src.figure,src.row and f'row {src.row}']
    return ' '.join(p for p in parts if p)


def _claims_table(dossier) -> None:
    """The dossier's values as a table: each claim's key, value, unit, status and source location."""
    rows=[]
    for claim in dossier.claims:
        where='; '.join(_locator(src) for src in claim.sources)
        rows.append({'key':claim.key,'value':'' if claim.value is None else str(claim.value)[:80],'units':claim.units or '',
                     'status':claim.status,'source':where[:80]})
    if not rows:
        return
    ui.label('The values read').classes('text-lg font-medium mt-2')
    ui.table(columns=[{'name':k,'label':k,'field':k,'align':'left'} for k in ('key','value','units','status','source')],
             rows=rows,row_key='key').classes('w-full').props('dense')
