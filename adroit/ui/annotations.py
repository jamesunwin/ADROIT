"""Study organisation in the workbench (``orchestrator.annotations``; the owner's workbench plan of 2026-10-18, part 2
§G): filters on the studies page and an annotation card on each study. Annotations are kept apart from the studies."""
from __future__ import annotations

from pathlib import Path

from nicegui import ui

FILTERS = (('project', 'project'), ('tag', 'tag'), ('model', 'model revision'), ('dataset', 'dataset or profile'),
           ('verdict', 'verdict'), ('certification', 'certification'), ('status', 'status'))


def filter_bar(rows, on_change) -> dict:
    """The filter controls; returns their live values (read them in ``on_change``)."""
    from adroit.orchestrator.annotations import choices
    options = choices(rows)
    controls: dict = {}
    with ui.row().classes('items-end gap-2 flex-wrap').mark('study_filters'):
        controls['text'] = ui.input('Find a study', placeholder='a title, label, project, tag or note') \
            .classes('w-72').on_value_change(lambda _: on_change())
        for name, label in FILTERS:
            if options[name]:
                controls[name] = ui.select({'': f'any {label}', **{v: v for v in options[name]}}, value='',
                                           label=label).classes('w-56').mark(f'filter_{name}') \
                    .on_value_change(lambda _: on_change())
        controls['favourite'] = ui.checkbox('favourites only').on_value_change(lambda _: on_change())
    return controls


def values(controls: dict) -> dict:
    """The filters' current values for ``annotations.select``."""
    return {k: (c.value or ('' if k != 'favourite' else False)) for k, c in controls.items()}


def badges(annotation) -> None:
    """A study's project, tags and favourite, beside its title."""
    if annotation is None:
        return
    if annotation.favourite:
        ui.label('★').classes('text-amber-600')
    if annotation.project:
        ui.badge(annotation.project, color='teal').props('outline')
    for tag in annotation.tags:
        ui.badge(tag, color='grey-6').props('outline')


def annotation_card(root: Path, folder: Path) -> None:
    """On a study page: its label, project, tags, favourite flag and note, saved apart from the study."""
    from adroit.orchestrator import annotations as an
    current = an.load(root).get(an.key(root, folder)) or an.Annotation()
    with ui.expansion('Label, project, tags and notes' + (f' ({current.project})' if current.project else ''),
                      value=bool(current.note)).classes('w-full').mark('annotation'):
        ui.label('Kept apart from the study: labelling or filing it changes neither its results nor its evidence.') \
            .classes('text-sm text-gray-600')
        with ui.row().classes('items-end gap-2'):
            label = ui.input('display label', value=current.label).classes('w-72').mark('annotation_label')
            project = ui.input('project', value=current.project,
                               placeholder='Paper A / vector mediator / final figures').classes('w-96') \
                .mark('annotation_project')
            favourite = ui.checkbox('favourite', value=current.favourite)
        tags = ui.input('tags (comma-separated)', value=', '.join(current.tags)).classes('w-full') \
            .mark('annotation_tags')
        note = ui.textarea('note', value=current.note).classes('w-full').props('rows=3')

        def save() -> None:
            an.save(root, folder, an.Annotation(label=label.value or '', project=project.value or '',
                                                tags=(tags.value or '').split(','), favourite=bool(favourite.value),
                                                note=note.value or ''))
            ui.notify('saved')
        ui.button('Save', on_click=save).props('outline').mark('save_annotation')
