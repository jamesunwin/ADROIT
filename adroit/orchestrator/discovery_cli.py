"""Model-driven constraint discovery at the command line (``adroit constraints …``; the owner's request, 2026-10-18).

``discover`` and ``resume`` are paid (one hard cap per session, at most $10, shown before every request); ``show``,
``decide``, ``coverage`` and ``raise-cap`` cost nothing. Reviewing, validating and binding a retrieved limit stay
with ``adroit experiments verify-source / validate-limit / bind-limit`` and the profile commands.
"""
from __future__ import annotations

import json
from pathlib import Path

import typer

from adroit.orchestrator.preflight import paid_command, record_requests, session_export

app = typer.Typer(pretty_exceptions_show_locals=False, help='Model-driven constraint discovery: relevant limits found, retrieved and drafted for your '
                       'review; nothing is signed or applied without you.')


def _axis(text: str) -> tuple[str, tuple[float, float]]:
    name, low, high = text.split(':')[:3]
    if name not in ('m_chi', 'm_med') or not 0 < float(low) < float(high):
        raise typer.BadParameter('a domain is m_chi:LOW:HIGH or m_med:LOW:HIGH in GeV')
    return name, (float(low), float(high))


REPORT_FILES = ('discovery.json', 'report.md')     # a discovery's export, beside its request record (DK-01)


def _report(service, session: str, out: Path | None) -> None:
    """The session's view and spending, and with ``out`` its export: ``discovery.json`` and ``report.md`` with the
    run's request record, under one hold of the folder (``preflight.session_export``; DJ-01, DK-01)."""
    from adroit.orchestrator.accounting import session_money
    view = service.show(session)
    typer.echo(json.dumps({k: view[k] for k in ('session', 'model', 'state', 'budget')}, indent=2))
    typer.echo('session spending: ' + session_money(service.budgets, session))
    for c in view['candidates']:
        typer.echo(f"- [{c['stage']}] {c['name']} ({c['reference']}): {c['category']}"
                   + (f"; missing: {c['missing']}" if c['missing'] else ''))
    if out:
        from adroit.evidence.version import as_found
        try:
            session_export(out, service.budgets, session, {
                'discovery.json': json.dumps(view, indent=2), 'report.md': report(view) + as_found(
                    f"It is the discovery session {view['session']} as it was read when this report was written; "
                    "the session can advance since.")})
        except (ValueError, OSError) as error:
            record_requests(out, service.budgets, session, REPORT_FILES)
            raise typer.BadParameter(str(error)) from None


def _money(status) -> str:
    """A view's budget status in words (``accounting.status_text``), or why it is not available."""
    from adroit.orchestrator.accounting import NOT_AVAILABLE, status_text
    try:
        return status_text(status)
    except (TypeError, KeyError, ValueError) as error:
        return f"{NOT_AVAILABLE} ({status.get('unavailable', error) if isinstance(status, dict) else error})"


def report(view: dict) -> str:
    """The session's Markdown report: what was searched, each candidate's stage and states, and the gaps."""
    lines = [f"# Constraint discovery for {view['domain']['name']}", '',
             f"Session `{view['session']}`; model `{view['model']}`; searched (UTC) {view['searched_at'] or 'not yet'}.",
             '', f"Session spending: {_money(view.get('budget'))}.", '', 'A dated, bounded survey: a constraint it did not find is not shown to be absent. Nothing here is '
             'signed, validated, bound or applied; those are your steps.', '',
             '| stage | result | category | source | review | validation | selection | missing |',
             '|---|---|---|---|---|---|---|---|']
    for c in view['candidates']:
        s = c['states']
        lines.append(f"| {c['stage']} | {c['name']} ({c['reference']}) | {c['category']} | {s['source']} | "
                     f"{_review_text(s)} | {s['validation']} | {s['selection']} | {c['missing'] or '—'} |")
    lines += ['', '## Gaps', ''] + [f'- {g}' for g in view['gaps'] or ['none recorded']]
    return '\n'.join(lines) + '\n'


@app.command('discover')
@paid_command
def discover(reference: str = typer.Argument(..., help='a personal model revision (catalog:MODEL@REVISION) or a '
                                                       'typed model YAML file'),
             budget: float = typer.Option(..., '--budget', min=0, max=10, help="the session's total hard cap in "
                                          'dollars (at most 10): the relevance request and every extraction step'),
             model: str = typer.Option('claude-opus-5-5', '--model', help='the language model'),
             domain: list[str] = typer.Option([], '--domain', help='the intended scan range, m_chi:LOW:HIGH or '
                                              'm_med:LOW:HIGH in GeV; repeatable'),
             refresh: bool = typer.Option(False, '--refresh', help="ask arXiv again instead of the shared "
                                          'literature cache'),
             max_sources: int = typer.Option(4, '--max-sources', min=0, max=8, help='the most papers retrieved'),
             vision: bool = typer.Option(False, '--vision', help='read figures: for a spin-independent limit with no '
                                         'data table, also send the pages whose captions name it as page images (at '
                                         'most three per paper; Anthropic models; larger requests, each '
                                         'bound reserved against the cap before it is sent)'),
             out: Path | None = typer.Option(None, '--out', help='folder for discovery.json and report.md')) -> None:
    """Find the limits relevant to a model, retrieve absent ones an existing adapter supports, and draft them for
    your review; paid (one cap). Network: arXiv and HEPData only."""
    from adroit.orchestrator.constraint_discovery import FIGURE_PAGES, Discovery, Options
    service = Discovery()
    session = ''
    try:
        from adroit.core.durable import not_a_study
        not_a_study(out)                        # before anything is spent (DJ-01)
        s = service.start(reference, Options(model=model, budget=budget, domain=dict(map(_axis, domain)),
                                         refresh=refresh, max_acquisitions=max_sources, vision=vision))
        session = s.session_id
        typer.echo(f'discovery session {s.session_id} for {s.model_reference}', err=True)
        if vision:
            typer.echo(f'reading figures: up to {FIGURE_PAGES} figure pages per paper go as images where an SI limit '
                       'has no data table; each request\'s bound, images included, is reserved before it is sent',
                       err=True)
        service.run(s.session_id)
    except BaseException as error:              # stopped: its request record, if it sent a request (DK-01)
        if session:
            record_requests(out, service.budgets, session, REPORT_FILES)
        if isinstance(error, (ValueError, OSError)):
            raise typer.BadParameter(str(error)) from None
        raise
    _report(service, s.session_id, out)         # with this run's own requests, apart from its session's


@app.command('resume')
@paid_command
def resume(session: str, budget: float = typer.Option(..., '--budget', min=0, max=10, help="the session's cap as "
                                                      'started or last raised'),
           out: Path | None = typer.Option(None, '--out', help='folder for discovery.json and report.md')) -> None:
    """Continue a stopped or failed session with its pinned inputs and remaining cap; finished stages and batches
    are not repeated. Paid."""
    from adroit.orchestrator.constraint_discovery import Discovery
    service = Discovery()
    try:
        from adroit.core.durable import not_a_study
        not_a_study(out)                        # before anything is spent (DJ-01)
        if service.budgets.session(session).budget != budget:
            raise ValueError('supply the originally approved session budget (or the cap as last raised)')
        service.run(session)
    except BaseException as error:              # stopped: its request record, if it sent a request (DK-01)
        record_requests(out, service.budgets, session, REPORT_FILES)
        if isinstance(error, (ValueError, OSError)):
            raise typer.BadParameter(str(error)) from None
        raise
    _report(service, session, out)              # with this run's own requests, apart from its session's


@app.command('show')
def show(session: str) -> None:
    """A session's stages, candidates (each with its stage and separate states), decisions and gaps. Read-only, $0."""
    from adroit.orchestrator.constraint_discovery import Discovery
    try:
        typer.echo(json.dumps(Discovery().show(session), indent=2))
    except (ValueError, OSError) as error:
        raise typer.BadParameter(str(error)) from None


@app.command('decide')
def decide(session: str, candidate: str,
           inapplicable: str = typer.Option('', '--inapplicable', help='why the result cannot apply to this model'),
           omit: str = typer.Option('', '--omit', help="why it is left out of this study's scope (it stays listed)"),
           superseded_by: str = typer.Option('', '--superseded-by', help='confirm the relevance step\'s mark: the '
                                             'newer result (as proposed) replaces it over its whole domain'),
           reason: str = typer.Option('', '--reason', help='why, with --superseded-by'),
           researcher: str = typer.Option(..., '--by', help='your name, recorded with the decision')) -> None:
    """Record a candidate as inapplicable (it drops out of the coverage), omitted from the study (it stays, as an
    omission, and keeps an allowed point pending), or confirmed as superseded by the newer result proposed for it
    (until then a superseded result stays a requirement). $0."""
    from adroit.orchestrator.constraint_discovery import Discovery
    if sum(map(bool, (inapplicable, omit, superseded_by))) != 1:
        raise typer.BadParameter('give one of --inapplicable, --omit (each with the reason) or --superseded-by')
    if superseded_by and not reason:
        raise typer.BadParameter('give --reason with --superseded-by: why the newer result replaces it everywhere')
    kind = 'inapplicable' if inapplicable else 'omitted' if omit else 'superseded'
    try:
        d = Discovery().decide(session, candidate, kind, inapplicable or omit or reason, researcher,
                               replacement=superseded_by)
    except (ValueError, OSError) as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(d.model_dump_json(indent=2))


@app.command('coverage')
def coverage(session: str,
             incomplete: bool = typer.Option(False, '--incomplete', help='freeze a session whose stages did not all '
                                             'finish; every allowed point of a run that pins it stays pending')) -> None:
    """Freeze the session's assessment and print its pin, discovery:SESSION@HASH, for track1 / single-idea
    --discovery. Refused while a stage is unfinished, unless --incomplete. $0."""
    from adroit.orchestrator.constraint_discovery import Discovery
    try:
        c = Discovery().coverage(session, incomplete=incomplete)
    except (ValueError, OSError) as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(c.reference)
    for r in c.requirements:
        typer.echo(f'- unresolved: {r.name} ({r.reference}): {r.reason}', err=True)


@app.command('raise-cap')
def raise_cap(session: str, budget: float = typer.Option(..., '--budget', min=0, max=10, help='the new cap'),
              confirmed: bool = typer.Option(False, '--confirmed', help='confirm the increase (required)'),
              reason: str = typer.Option('', '--reason', help='why; kept with the session')) -> None:
    """Raise a discovery session's cap, with your confirmation; recorded. $0."""
    from adroit.orchestrator.constraint_discovery import Discovery
    from adroit.orchestrator.preflight import raise_cap_command
    raise_cap_command(Discovery().budgets, session, budget, confirmed, reason)


def _review_text(states: dict) -> str:
    """The review state, with the model named where a language model checked the source (PR-09)."""
    from adroit.core.pricing import model_name
    if states.get('review') == 'checked' and states.get('review_by'):
        return f"checked by {model_name(states['review_by'])}, not by a person"
    return states['review']

