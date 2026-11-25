"""The workbench's pages, as pure functions of their data (HTML, escaped)."""

from __future__ import annotations

import html
import re
from pathlib import Path

from markdown_it import MarkdownIt

from adroit.workbench.jobs import KINDS, Job

_MD = MarkdownIt("commonmark", {"html": False}).enable("table")
STYLE = """
body { font-family: -apple-system, 'Segoe UI', Helvetica, sans-serif; margin: 0; color: #1d1d1f; background: #fafafa; }
header { background: #1f3b57; color: white; padding: 10px 24px; }
header a { color: white; margin-right: 18px; text-decoration: none; font-weight: 500; }
main { max-width: 1100px; margin: 0 auto; padding: 16px 24px 48px; }
table { border-collapse: collapse; margin: 10px 0; font-size: 14px; }
th, td { border: 1px solid #d0d0d5; padding: 4px 8px; text-align: left; vertical-align: top; }
th { background: #eef1f5; }
.status-done { color: #1a7f37; } .status-failed { color: #b42318; } .status-running, .status-queued { color: #9a6700; }
form label { display: block; margin-top: 10px; font-weight: 500; }
input[type=text], input[type=number], select, textarea { width: 100%; max-width: 640px; padding: 4px; font-size: 14px; }
.checks label { display: inline-block; font-weight: normal; margin-right: 14px; }
button { margin-top: 14px; padding: 6px 16px; font-size: 14px; }
.note { color: #555; font-size: 13px; }
pre { background: #f0f0f3; padding: 8px; overflow-x: auto; }
img { max-width: 100%; }
"""


def esc(text: object) -> str:
    """Text escaped for HTML."""
    return html.escape(str(text), quote=True)


def markdown(text: str) -> str:
    """A report's Markdown as HTML (raw HTML in the text is escaped, not passed through)."""
    return _MD.render(text)


def layout(title: str, body: str, refresh_s: int | None = None) -> str:
    """A page: the navigation, then the body."""
    refresh = f'<meta http-equiv="refresh" content="{refresh_s}">' if refresh_s else ""
    nav = "".join(f'<a href="{href}">{name}</a>' for href, name in [
        ("/", "Runs"), ("/new/exclusion", "Path 1: library card"), ("/new/lagrangian", "Path 1: bespoke model"),
        ("/new/signal", "Path 2: a signal"), ("/evaluation", "Evaluation"), ("/tools", "Tools")])
    return (f"<!doctype html><html><head><meta charset='utf-8'>{refresh}<title>ADROIT: {esc(title)}</title>"
            f"<style>{STYLE}</style></head><body><header><strong>ADROIT</strong> &nbsp; {nav}</header>"
            f"<main><h1>{esc(title)}</h1>{body}</main></body></html>")


def runs_page(jobs: list[Job]) -> str:
    """Every run, newest first, with its state and a link to its report."""
    if not jobs:
        return layout("Runs", "<p>No runs yet. Start one from the menu above.</p>")
    rows = "".join(
        f"<tr><td><a href='/job/{esc(j.id)}'>{esc(j.title)}</a></td><td>{esc(KINDS.get(j.kind, j.kind))}</td>"
        f"<td class='status-{esc(j.status)}'>{esc(j.status)}</td><td>{esc(j.created)}</td>"
        f"<td>{esc(j.finished)}</td></tr>" for j in jobs)
    return layout("Runs", "<table><tr><th>run</th><th>pipeline</th><th>state</th><th>started</th>"
                          f"<th>finished</th></tr>{rows}</table>")


def _checks(name: str, options: list[str], checked: set[str]) -> str:
    return "<div class='checks'>" + "".join(
        f"<label><input type='checkbox' name='{esc(name)}' value='{esc(o)}'"
        f"{' checked' if o in checked else ''}> {esc(o)}</label>" for o in options) + "</div>"


def exclusion_form(cards: dict[str, str], modules: list[str]) -> str:
    """Path 1 for a library card: its couplings, the masses and the modules."""
    options = "".join(f"<option value='{esc(k)}'>{esc(k)}: {esc(v)}</option>" for k, v in cards.items())
    body = f"""<form method='post' action='/run/exclusion'>
<label>Card</label><select name='card'>{options}</select>
<label>Isospin, at unit coupling 1/m_v² (operator and Lagrangian cards)</label>
<select name='isospin'><option value=''>none: give the parameters below</option><option value='s'>s (isoscalar)</option><option value='v'>v (isovector)</option></select>
<label>Parameters, name=value, comma-separated (optional)</label><input type='text' name='values' placeholder='c1_s=1e-6'>
<label>Masses (GeV), comma-separated</label><input type='text' name='masses' value='10,30,100,300,1000'>
<label>Mass splitting δ (keV)</label><input type='number' step='any' name='splitting' value='0'>
<label>Experiment modules (none ticked: all)</label>{_checks('modules', modules, set())}
<button type='submit'>Run Path 1</button></form>
<p class='note'>Free. The xenon modules use DIAMX and take minutes per mass.</p>"""
    return layout("Path 1: a library card", body)


def signal_form(searches: list[str], modules: list[str], default_nulls: list[str]) -> str:
    """Path 2: the search with events, the null searches, and the size of the run."""
    options = "".join(f"<option>{esc(s)}</option>" for s in searches)
    body = f"""<form method='post' action='/run/signal'>
<label>The search whose events to explain</label><select name='experiment'>{options}</select>
<label>Null searches to combine with</label>{_checks('null', modules, set(default_nulls))}
<label>Degeneracy classes carried forward</label><input type='number' name='leaders' value='8' min='1'>
<label>Background-only toys (for the global significance)</label><input type='number' name='toys' value='200000' min='1000'>
<button type='submit'>Run Path 2</button></form>
<p class='note'>Free. With xenon null searches a run takes tens of minutes.</p>"""
    return layout("Path 2: a signal", body)


def lagrangian_form() -> str:
    """Path 1 for a bespoke model: the YAML of a model and its derivation (DM8)."""
    body = """<form method='post' action='/run/lagrangian'>
<label>Model and derivation (YAML: <code>spec</code>, <code>derivation</code>; optional <code>masses_gev</code>, <code>modules</code>)</label>
<textarea name='model' rows='22' placeholder='See docs/dm8/majorana_scalar.yaml for an example'></textarea>
<label><input type='checkbox' name='numerical_check' value='1'> Check the derivation against MadDM (installed in the tools folder)</label>
<button type='submit'>Run Path 1</button></form>
<p class='note'>Free: the model and its derivation are given. The language-model intake and derivation (paid) are not run from here.</p>"""
    return layout("Path 1: a bespoke model", body)


def job_page(job: Job, report: str | None, images: list[str], note: str = "",
             embedded: dict[str, bytes] | None = None, held: str = "") -> str:
    """A run: its state and inputs, and when it is done, its report and plots: ``images`` served from its folder,
    ``embedded`` drawn from the bytes given (a bound report's, as checked: ``server.report_view``), and ``note``, why
    any is not shown. Its link to the result names the version read with the report (``held``, its digest), which the
    file route then requires (the auditor's version-identity audit, VI-02, 2026-11-03)."""
    from urllib.parse import quote
    import base64
    parts = [f"<p>{esc(KINDS.get(job.kind, job.kind))}. State: <span class='status-{esc(job.status)}'>"
             f"<strong>{esc(job.status)}</strong></span>. Started {esc(job.created)}"
             + (f", finished {esc(job.finished)}" if job.finished else "") + ".</p>"]
    if job.inputs:
        parts.append("<details><summary>Inputs</summary><pre>" + esc(
            "\n".join(f"{k}: {v}" for k, v in job.inputs.items())) + "</pre></details>")
    if job.error:
        parts.append(f"<p class='status-failed'>The run failed:</p><pre>{esc(job.error)}</pre>")
    parts += [f"<img src='/file/{esc(job.id)}/{esc(name)}' alt='{esc(name)}'>" for name in images]
    parts += [f"<img src='data:image/png;base64,{base64.b64encode(data).decode()}' alt='{esc(name)}'>"
              for name, data in (embedded or {}).items()]
    if note:
        parts.append(f"<p class='note'>{esc(note)}</p>")
    if report:
        parts.append(markdown(report))
    version = f"?sha256={quote(held)}" if held else ""
    parts.append(f"<p class='note'>Folder: runs/{esc(job.id)} (<a href='/file/{esc(job.id)}/result.json{esc(version)}'>"
                 "result.json</a>)</p>" if report else "")
    running = job.status in ("queued", "running")
    return layout(job.title, "".join(parts) + ("<p class='note'>This page refreshes every 5 s.</p>" if running else ""),
                  refresh_s=5 if running else None)


def evaluation_page(gate: str | None, summaries: dict[str, dict[str, dict]]) -> str:
    """DM10: the gate's result, then each suite's latest development and held-out summaries."""
    parts = [markdown(gate) if gate else "<p>No gate has been run.</p>"]
    for suite, halves in summaries.items():
        parts.append(f"<h2>{esc(suite)}</h2>")
        for half, run in halves.items():
            rows = "".join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in run["summary"].items())
            parts.append(f"<p><strong>{esc(half.replace('_', '-'))} half</strong>, commit {esc(run['commit'])}, "
                         f"{esc(run['date'])}</p><table>{rows}</table>")
    return layout("Evaluation (DM10)", "".join(parts))


def tools_page(report: str) -> str:
    """The external tools and data: their setup report."""
    return layout("External tools and data", markdown(re.sub(r"^# .*\n", "", report)))


def safe_file(runs_dir: Path, job_id: str, name: str) -> Path | None:
    """A file inside one run's folder, or None if the path would leave it."""
    folder = (runs_dir / job_id).resolve()
    path = (folder / name).resolve()
    return path if folder in path.parents and path.is_file() and folder.parent == runs_dir.resolve() else None
