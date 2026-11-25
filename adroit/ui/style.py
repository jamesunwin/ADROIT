"""The workbench's shared look (the UI clarity plan, 2026-10-15): one way to open a page, to label an input,
and to show a date, an amount or a reference.

- **Every page** opens with its title, one or two sentences on what it does and what comes out, and a row of facts
  (what it costs, how long it takes, what comes next); longer caveats sit in a "Details" expansion.
- **Inputs** carry their label above the field (never cut off), a width that fits it, and a hint line under the field
  saying what the input changes.
- **Values for people:** local dates ("15 Oct 2026, 20:14 BST", UTC on hover), durations, money ("$0.12 of $0.40"),
  and long references shortened with a copy button.
- **A glossary** gives each technical term one definition, shown on hover.
"""

from __future__ import annotations

from datetime import datetime, timezone

from nicegui import ui

# One definition per term, for the "?" hints (``term``).
GLOSSARY = {
    "Ωh²": "the dark matter's relic density today; the observed value is 0.120 ± 0.001 (Planck 2018)",
    "thermal contour": "the masses and couplings where freeze-out gives exactly the observed Ωh²",
    "background-only simulations": "simulated experiments with background only and no signal (\"toys\"); they correct "
                                   "the significance for the many masses and models tried. More give a more precise "
                                   "p-value, down to about 1 over their number, and take longer",
    "null searches": "experiments that saw no excess; a candidate that explains the signal must not be excluded by "
                     "them",
    "operator": "a non-relativistic effective interaction (O1, O4, …) between dark matter and nucleons; the library's "
                "interactions are combinations of them",
    "splitting": "the mass difference between the dark matter and a heavier partner it scatters into (inelastic "
                 "scattering), in keV",
    "profile": "your choice of which experimental results a run uses: the packaged ones, with your reviewed private "
               "limits added or substituted",
    "revision": "one saved, immutable version of a model; editing a model saves a new revision and keeps the old one",
    "route": "what computes a model: a validated library engine, or the generic route from its own Lagrangian",
    "verdict": "viable, viable pending, excluded, pending, overabundant or underabundant, judged on the thermal "
               "contour",
    "record": "a published constraint, transcribed from its paper and verified by a person before it is used",
    "dossier": "a structured reading of an experiment's paper: each value with its unit, status and source location",
    "eligibility": "whether a fitted point is also a physical model that survives the other constraints",
}

NAV_GROUPS = [("", [("Home", "/"), ("Studies", "/studies"), ("Batches", "/batches"), ("Open a bundle", "/bundle")]),
              ("Run", [("Constrain a model", "/new/track1"), ("Signal best fits", "/new/track2"),
                       ("Explain a signal", "/new/single")]),          # Native fit: withdrawn, 1.0.1 (JU1)
              ("Libraries", [("Model library", "/models"), ("Records", "/records")]),
              ("Add data", [("Add a limit", "/experiments"), ("Add a signal", "/new/anomaly")])]
CONTENT = "max-w-6xl mx-auto w-full"
# a report's Markdown inside a page: headings at reading size, below the page's own title
REPORT_CSS = (".nicegui-markdown h1{font-size:1.45rem;line-height:1.3;margin:.6em 0 .3em}"
              ".nicegui-markdown h2{font-size:1.25rem;line-height:1.3;margin:.6em 0 .3em}"
              ".nicegui-markdown h3{font-size:1.1rem;line-height:1.3;margin:.5em 0 .25em}"
              ".nicegui-markdown h4,.nicegui-markdown h5,.nicegui-markdown h6{font-size:1rem;margin:.4em 0 .2em}"
              ".q-uploader__subtitle{display:none}")             # the uploader's "0.0B / 0.00%"
FIELD = "min-w-[20rem]"

# The workbench's appearance (the owner's static appearance pass, 2026-11-08): typography, a pale warm page, white
# surfaces with thin borders, and one muted accent for links, the buttons already marked as primary and the file
# uploader's header. Static presentation only, scoped to the workbench's pages (``body.adroit-workbench``). Left as
# they are: every badge and status colour (a verdict, a run's state, an accounting state keeps its own), form fields'
# focus, error and disabled states, plots and figures, and every layout, display, position and overflow rule.
WORKBENCH_CSS = """
body.adroit-workbench {
  --adroit-page: #F7F7F4; --adroit-surface: #FFFFFF; --adroit-ink: #24303B; --adroit-ink-2: #53616E;
  --adroit-border: #D8DDE1; --adroit-accent: #355C73; --adroit-accent-hover: #29495C; --adroit-link: #315B75;
  --adroit-head: #F1F2EF;
  background: var(--adroit-page); color: var(--adroit-ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 15px; line-height: 1.5;
}
body.adroit-workbench .adroit-nav {
  background: var(--adroit-surface); padding: 0.5rem 0.75rem; border-radius: 4px 4px 0 0; font-size: 14px;
}
body.adroit-workbench .adroit-nav-rule {
  background: var(--adroit-border); margin-top: calc(-1 * var(--nicegui-default-gap));
}
body.adroit-workbench .adroit-wordmark { color: var(--adroit-ink); font-weight: 650; letter-spacing: 0.08em; }
body.adroit-workbench .adroit-nav-group { color: var(--adroit-ink-2); letter-spacing: 0.1em; }
body.adroit-workbench .adroit-nav-link { color: var(--adroit-link); }
body.adroit-workbench .adroit-nav-link:hover {
  color: var(--adroit-accent-hover); text-decoration-line: underline; opacity: 1;
}
body.adroit-workbench .adroit-nav-current {
  color: var(--adroit-ink); text-underline-offset: 5px; text-decoration-thickness: 2px;
}
body.adroit-workbench .adroit-page-title { color: var(--adroit-ink); font-size: 24px; font-weight: 600; }
body.adroit-workbench .adroit-section-title { color: var(--adroit-ink); font-size: 18px; font-weight: 600; }
:where(body.adroit-workbench) .nicegui-link:not(.text-gray-400) { color: var(--adroit-link); }
body.adroit-workbench .nicegui-markdown a { color: var(--adroit-link); }
body.adroit-workbench .nicegui-markdown a:hover { color: var(--adroit-accent-hover); }
body.adroit-workbench .q-card {
  border: 1px solid var(--adroit-border); border-radius: 4px; box-shadow: 0 1px 2px rgba(24, 39, 51, 0.06);
}
body.adroit-workbench .q-btn { --q-primary: var(--adroit-accent); text-transform: none; border-radius: 4px; }
body.adroit-workbench .q-uploader { --q-primary: var(--adroit-accent); border-radius: 4px; }
body.adroit-workbench .q-btn.bg-primary { box-shadow: 0 1px 2px rgba(24, 39, 51, 0.16); }
body.adroit-workbench .q-btn.bg-primary:not(.disabled):hover { --q-primary: var(--adroit-accent-hover); }
body.adroit-workbench .nicegui-markdown th, body.adroit-workbench .nicegui-markdown td {
  border: 1px solid var(--adroit-border); padding: 0.375rem 0.625rem;
}
body.adroit-workbench .nicegui-markdown th {
  background: var(--adroit-head); color: var(--adroit-ink); font-weight: 600;
}
body.adroit-workbench .nicegui-markdown td { font-variant-numeric: tabular-nums; }
body.adroit-workbench .q-table__card { box-shadow: none; border: 1px solid var(--adroit-border); border-radius: 4px; }
body.adroit-workbench .q-table thead th {
  background: var(--adroit-head); color: var(--adroit-ink); font-size: 13px; font-weight: 600;
}
body.adroit-workbench .q-table thead tr, body.adroit-workbench .q-table tbody td {
  border-color: var(--adroit-border);
}
body.adroit-workbench .q-table tbody td { font-variant-numeric: tabular-nums; }
"""


def apply_defaults() -> None:
    """Labels above the field and a width that fits them, for every input the workbench makes (once, before the
    pages are built)."""
    for element in (ui.input, ui.number, ui.select):
        element.default_props("stack-label")
        element.default_classes(FIELD)


def _current() -> str:
    try:
        return ui.context.client.page.path
    except (AttributeError, RuntimeError):
        return ""


RUNS_ROOT: list = []                # the workbench's runs folder, set by ``app.build_pages`` (the activity count)

# A page that takes seconds to answer (a study reads its result, tens of megabytes, as one checked version) gave no
# sign that its link had been followed (the owner, 2026-11-19: "clicking on a study does nothing"). Every page now
# shows "Loading…" from the click on one of the workbench's own links until the next page is shown: links that open
# elsewhere, download or are followed with a modifier key are left alone, and the sign is taken down when a page is
# shown again (the browser's back) and, at the latest, after a minute.
LOADING_ID = "adroit-loading"
LOADING_HTML = """<style>#adroit-loading{display:none;position:fixed;top:8px;left:50%;transform:translateX(-50%);
z-index:9999;padding:4px 14px;border-radius:12px;background:#1d4ed8;color:#fff;font-size:13px;
box-shadow:0 1px 4px rgba(0,0,0,.25)}</style>
<script>
(function () {
  if (window.adroitLoading) { return; }
  window.adroitLoading = true;
  function sign() { return document.getElementById('adroit-loading'); }
  function hide() { var s = sign(); if (s) { s.style.display = 'none'; } }
  document.addEventListener('click', function (event) {
    var link = event.target && event.target.closest ? event.target.closest('a[href]') : null;
    if (!link || event.defaultPrevented || event.button || event.metaKey || event.ctrlKey || event.shiftKey ||
        event.altKey || link.target === '_blank' || link.hasAttribute('download')) { return; }
    var url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin || url.pathname.indexOf('/files/') === 0 ||
        (url.pathname === window.location.pathname && url.search === window.location.search)) { return; }
    var s = sign();
    if (!s) { s = document.createElement('div'); s.id = 'adroit-loading'; s.textContent = 'Loading\u2026';
              s.setAttribute('role', 'status'); document.body.appendChild(s); }
    s.style.display = 'block';
    window.setTimeout(hide, 60000);
  });
  window.addEventListener('pageshow', hide);
})();
</script>"""


def nav() -> None:
    """The menu, grouped (run, libraries, add data), the current page underlined, and the activity indicator. The
    current page's link keeps the others' weight, so no link moves as the pages change (the owner's JU1, 2026-11-16)."""
    current = _current()
    with ui.row().classes("items-center gap-x-5 gap-y-1 w-full flex-wrap adroit-nav"):
        ui.label("ADROIT").classes("text-lg font-bold mr-2 adroit-wordmark")
        for group, links in NAV_GROUPS:
            with ui.row().classes("items-center gap-3"):
                if group:
                    ui.label(group.upper()).classes("text-xs text-gray-400 tracking-wider adroit-nav-group")
                for name, target in links:
                    link = ui.link(name, target).classes("no-underline text-blue-700 adroit-nav-link")
                    if target == current or (target != "/" and current.startswith(target + "/")):
                        link.classes("underline adroit-nav-current")   # never bold: its width would move the rest (JU1)
        if RUNS_ROOT:
            activity()
        from adroit.ui.about import footer_tag
        footer_tag()


def activity() -> None:
    """The menu's activity link: how many runs are running and how many recent ones need attention."""
    from adroit.orchestrator.recovery import summary
    try:
        counts = summary(RUNS_ROOT[0])
    except (OSError, ValueError):
        counts = {'running': 0, 'attention': 0}
    with ui.row().classes("items-center gap-1").mark("activity"):
        ui.link("Activity", "/activity").classes("no-underline text-blue-700 adroit-nav-link")
        if counts['running']:
            ui.badge(f"{counts['running']} running", color="blue")
        if counts['attention']:
            ui.badge(f"{counts['attention']} need attention", color="red")


def page_header(title: str, description: str = "", facts: tuple[str, ...] | list[str] = (),
                details: tuple[str, ...] | list[str] = (), subtitle: str = "") -> None:
    """The menu, then the page's title, its description (what the page does and what comes out), a row of facts
    (cost, time, next step) and the longer caveats folded into "Details"."""
    ui.query(".nicegui-content").classes(CONTENT)
    ui.query("body").classes("adroit-workbench")
    ui.add_css(REPORT_CSS)
    ui.add_css(WORKBENCH_CSS)
    ui.add_head_html(LOADING_HTML)
    nav()
    ui.separator().classes("adroit-nav-rule")
    if title:
        with ui.row().classes("items-baseline gap-3"):
            ui.label(title).classes("text-2xl font-medium adroit-page-title")
            if subtitle:
                ui.label(subtitle).classes("text-sm text-gray-500")
    if description:
        ui.label(description).classes("text-base text-gray-700 max-w-4xl")
    if facts:
        with ui.row().classes("gap-2"):
            for fact in facts:
                ui.badge(fact, color="grey-3").props("text-color=grey-9").classes("text-sm font-normal px-2 py-1")
    if details:
        with ui.expansion("Details and assumptions").classes("w-full text-sm text-gray-700"):
            for line in details:
                ui.label(line)


def section(title: str, note: str = ""):
    """A titled card for one step of a form."""
    card = ui.card().classes("w-full")
    with card:
        ui.label(title).classes("text-lg font-medium adroit-section-title")
        if note:
            ui.label(note).classes("text-sm text-gray-600")
    return card


def hint(element, text: str):
    """A hint line under an input (what it changes, its default's meaning, its cost or time)."""
    return element.props(f'hint="{_attr(text)}" bottom-slots')


def _attr(text: str) -> str:
    return text.replace('"', "&quot;")


def term(name: str) -> None:
    """A small "?" with the term's definition on hover."""
    with ui.icon("help_outline").classes("text-gray-400 text-sm cursor-help"):
        ui.tooltip(f"{name}: {GLOSSARY[name]}").classes("text-sm max-w-xs")


def when(stamp: str | datetime | None) -> str:
    """A time for people: "15 Oct 2026, 20:14 BST" in this machine's zone; "" if none."""
    if not stamp:
        return ""
    try:
        moment = stamp if isinstance(stamp, datetime) else datetime.fromisoformat(str(stamp))
    except ValueError:
        return str(stamp)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone().strftime("%d %b %Y, %H:%M %Z").lstrip("0")


def show_when(label: str, stamp) -> None:
    """A labelled time, with its exact UTC value on hover."""
    with ui.label(f"{label} {when(stamp)}" if label else when(stamp)).classes("text-gray-600"):
        ui.tooltip(f"UTC: {stamp}")


def duration(start, end) -> str:
    """The time between two stamps: "10 min 38 s"; "" if either is missing."""
    try:
        seconds = (datetime.fromisoformat(str(end)) - datetime.fromisoformat(str(start))).total_seconds()
    except (TypeError, ValueError):
        return ""
    return seconds_text(seconds)


def seconds_text(seconds: float) -> str:
    """"42 s", "10 min 38 s" or "2 h 05 min"."""
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{seconds:.0f} s"
    if seconds < 3600:
        return f"{int(seconds // 60)} min {int(seconds % 60):02d} s"
    return f"{int(seconds // 3600)} h {int(seconds % 3600 // 60):02d} min"


def embedded(data: bytes, media: str = "image/png") -> str:
    """An image's bytes as the page's own (a data URL): a figure shown as it was drawn for the page, never a file named
    for the browser to read later, when it may be another's (the auditor's DH recheck, DI-01, 2026-11-06)."""
    import base64
    return f"data:{media};base64,{base64.b64encode(data).decode()}"


def short_ref(reference: str, label: str = "") -> None:
    """A long reference as a short chip, with its full value on hover and a copy button."""
    tail = reference.split("@")[-1].split(":")[-1]
    with ui.row().classes("items-center gap-1"):
        if label:
            ui.label(label).classes("text-sm text-gray-600")
        with ui.label(f"{tail[:10]}…" if len(tail) > 12 else tail).classes("font-mono text-sm bg-gray-100 px-1 rounded"):
            ui.tooltip(reference)
        ui.button(icon="content_copy", on_click=lambda: (ui.clipboard.write(reference), ui.notify("copied"))) \
            .props("flat dense size=sm").tooltip("copy the full reference")
