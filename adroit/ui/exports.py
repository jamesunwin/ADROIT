"""The study page's downloads (``evidence.exports``; the owner's workbench plan of 2026-10-18, §D): the evidence
bundle, numerical tables, figures, and the references with the exact request. Each is built in a temporary place and
sent to the browser; the study folder is never written."""
from __future__ import annotations

import tempfile
from pathlib import Path

from nicegui import ui

CHOICES = (('bundle', 'Evidence bundle (verified ZIP)'), ('tables', 'Numerical tables (CSV, JSON, column guide)'),
           ('figures', 'Figures (PNG, PDF, SVG)'), ('references', 'References and the exact request'))


def files(kind: str, token) -> tuple[str, bytes]:
    """(file name, bytes) of one download, of the version its page showed (``token``: ``evidence.version.Token``), with
    the parts that download is made of required as the page read them (``exports.needed``): another version's result,
    evidence, report or study record is refused, naming it, and nothing is sent (the auditor's CX recheck, CY-03, 2026-11-01;
    its version-identity audit, VI-03, 2026-11-03: the same result's replaced evidence, report and figures had been
    downloaded as the page's). Each download is made of one resolution of that version. A result file in place of a
    token is the version saved now (a fresh selection)."""
    from adroit.evidence import exports
    from adroit.evidence.version import Token
    token = token if isinstance(token, Token) else Token(str(token))
    stem = Path(token.path).parent.name
    found = exports.held(exports.needed(token, kind), presentation=kind in ('figures', 'bundle'))
    if kind == 'bundle':
        with tempfile.TemporaryDirectory(prefix='adroit-bundle-') as folder:
            path = exports.bundle(found, Path(folder) / f'{stem}_evidence.zip')
            return path.name, path.read_bytes()
    if kind == 'tables':
        return f'{stem}_tables.zip', exports.archive(exports.tables(found))
    if kind == 'figures':
        return f'{stem}_figures.zip', exports.archive(exports.figures(found))
    if kind == 'references':
        return f'{stem}_references.zip', exports.archive({**exports.references(found), **exports.request(found)})
    raise ValueError(f'unknown download {kind!r}')


def download_menu(version) -> None:
    """The Download menu of a study with a saved result, of its page's version (``version``): each download requires
    the parts of that version it is made of (``files``)."""
    if version.result_state != 'held':
        return
    token = version.token()

    def send(kind: str) -> None:
        try:
            name, data = files(kind, token)
        except (ValueError, OSError) as error:
            ui.notify(f'download unavailable: {error}')
            return
        ui.download(data, name)

    with ui.dropdown_button('Download', auto_close=True).props('outline').mark('downloads'):
        for kind, label in CHOICES:
            ui.item(label, on_click=lambda kind=kind: send(kind))
