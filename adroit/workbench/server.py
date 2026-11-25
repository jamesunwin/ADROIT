"""The workbench's web server: routes, forms → jobs, and files, on this machine only (127.0.0.1)."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from adroit.orchestrator import runs
from adroit.workbench import pages
from adroit.workbench.jobs import Board, list_runs

HOST = "127.0.0.1"
EVALUATION = Path(__file__).resolve().parents[2] / "docs" / "dm10"


def cards() -> dict[str, str]:
    """The library's interaction cards, by identifier: their names."""
    from adroit.library.interactions import registry
    return {card_id: card.name for card_id, card in registry.cards().items()}


def modules() -> tuple[list[str], list[str]]:
    """(the null searches, the searches with events)."""
    from adroit.experiments import registry
    return registry.module_names(), registry.signal_search_names()


def evaluation() -> tuple[str | None, dict[str, dict[str, dict]]]:
    """DM10's gate report and each suite's latest run in each half."""
    gate = EVALUATION / "gate.md"
    out: dict[str, dict[str, dict]] = {}
    for store in sorted((EVALUATION / "results").glob("*.jsonl")):
        runs_ = [json.loads(line) for line in store.read_text().splitlines() if line.strip()]
        out[store.stem] = {half: [r for r in runs_ if r["half"] == half][-1]
                           for half in ("development", "held_out") if any(r["half"] == half for r in runs_)}
    return (gate.read_text() if gate.is_file() else None), out


def tools() -> str:
    """The setup report of the external tools and data (looked at, not fetched)."""
    from adroit.external import setup
    return setup.report(setup.run())


def _form(fields: dict[str, list[str]], name: str, default: str = "") -> str:
    return fields.get(name, [default])[0].strip()


def submit(board: Board, kind: str, fields: dict[str, list[str]]):
    """A form's job, queued on the board.

    Raises:
        ValueError: for an unknown pipeline or a field that does not parse.
    """
    if kind == "exclusion":
        card, isospin = _form(fields, "card"), _form(fields, "isospin")
        values, masses = runs.parse_values(_form(fields, "values")), [float(m) for m in runs.parse_list(_form(fields, "masses"))]
        splitting, chosen = float(_form(fields, "splitting", "0") or 0), fields.get("modules", [])
        inputs = {"card": card, "isospin": isospin, "values": values, "masses_gev": masses,
                  "splitting_kev": splitting, "modules": chosen or "all"}
        return board.submit(kind, f"{card}{isospin}", inputs, lambda folder: runs.exclusion(
            card, isospin, values, masses, splitting, chosen, folder))
    if kind == "signal":
        experiment, nulls = _form(fields, "experiment"), fields.get("null", [])
        leaders, toys = int(_form(fields, "leaders", "8")), int(_form(fields, "toys", "200000"))
        inputs = {"experiment": experiment, "null_modules": nulls, "leaders": leaders, "toys": toys}
        return board.submit(kind, experiment, inputs, lambda folder: runs.signal(experiment, nulls, leaders, toys, folder))
    if kind == "lagrangian":
        text, check = _form(fields, "model"), bool(fields.get("numerical_check"))
        if not text:
            raise ValueError("paste a model and its derivation")
        return board.submit(kind, "bespoke model", {"numerical_check": check, "yaml_lines": len(text.splitlines())},
                            lambda folder: runs.lagrangian(text, check, folder))
    raise ValueError(f"no pipeline {kind!r}")


def handler_for(board: Board) -> type[BaseHTTPRequestHandler]:
    """The request handler of one workbench."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:          # quiet: the terminal stays readable
            pass

        def _send(self, body: str | bytes, status: HTTPStatus = HTTPStatus.OK, kind: str = "text/html") -> None:
            data = body.encode() if isinstance(body, str) else body
            self.send_response(status)
            self.send_header("Content-Type", f"{kind}; charset=utf-8" if kind.startswith("text") else kind)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _foreign(self) -> str:
            """Why this server will not act on the request, or "": its Host must be this server's own (a name of this
            machine at its port: a page of another site reaching it through its own name, DNS rebinding, is refused),
            and a POST's Origin, where the browser sends one, this server's (another site's page open beside it could
            otherwise start jobs with inputs of its choosing: AL2-12)."""
            port = self.server.server_address[1]
            own = {f"{name}:{port}" for name in ("127.0.0.1", "localhost", "[::1]")}
            if self.headers.get("Host", "") not in own:
                return "this workbench answers only requests addressed to it on this machine"
            origin = self.headers.get("Origin")
            if self.command == "POST" and origin is not None and origin not in {f"http://{h}" for h in own}:
                return "this workbench starts runs only from its own pages"
            return ""

        def _refuse(self, why: str) -> None:
            self._send(pages.layout("Refused", f"<p>{pages.esc(why)}</p>"), HTTPStatus.FORBIDDEN)

        def do_GET(self) -> None:  # noqa: N802 - the standard library's name
            if why := self._foreign():
                self._refuse(why)
                return
            try:
                self._send(*route(board, self.path))            # the path and its query, as asked
            except FileNotFoundError:
                self._send(pages.layout("Not found", f"<p>{pages.esc(unquote(urlparse(self.path).path))}</p>"),
                           HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            if why := self._foreign():
                self._refuse(why)
                return
            length = int(self.headers.get("Content-Length", 0))
            fields = parse_qs(self.rfile.read(length).decode(), keep_blank_values=True)
            kind = urlparse(self.path).path.removeprefix("/run/")
            try:
                job = submit(board, kind, fields)
            except ValueError as error:
                self._send(pages.layout("Not started", f"<p>{pages.esc(error)}</p>"), HTTPStatus.BAD_REQUEST)
                return
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", f"/job/{job.id}")
            self.end_headers()

    return Handler


def route(board: Board, path: str) -> tuple[str | bytes, HTTPStatus, str]:
    """(body, status, content type) for a GET (``path``, with its query). A run's file asked for as a version of its
    result (``?sha256=``: the run page's link to the result it showed) is sent only as that version: another is refused
    with 409 Conflict, saying so (the auditor's version-identity audit, VI-02, 2026-11-03: a page showing A's report had
    downloaded B).

    Raises:
        FileNotFoundError: for an unknown page, run or file.
    """
    ok = HTTPStatus.OK
    target = urlparse(path)
    path, query = unquote(target.path), parse_qs(target.query)
    if path == "/":
        return pages.runs_page(list_runs(board.runs_dir)), ok, "text/html"
    if path == "/new/exclusion":
        return pages.exclusion_form(cards(), modules()[0]), ok, "text/html"
    if path == "/new/signal":
        nulls, searches = modules()
        return pages.signal_form(searches, nulls, runs.DEFAULT_NULLS), ok, "text/html"
    if path == "/new/lagrangian":
        return pages.lagrangian_form(), ok, "text/html"
    if path == "/evaluation":
        return pages.evaluation_page(*evaluation()), ok, "text/html"
    if path == "/tools":
        return pages.tools_page(tools()), ok, "text/html"
    if path.startswith("/job/"):
        job = board.get(path.removeprefix("/job/"))
        if job is None:
            raise FileNotFoundError(path)
        folder = board.runs_dir / job.id
        return pages.job_page(job, *report_view(folder)), ok, "text/html"
    if path.startswith("/file/"):
        job_id, _, name = path.removeprefix("/file/").partition("/")
        file = pages.safe_file(board.runs_dir, job_id, name)
        if file is None:
            raise FileNotFoundError(path)
        data = file.read_bytes()                        # read once: what is checked is what is sent
        if query.get("sha256") and hashlib.sha256(data).hexdigest() != query["sha256"][0]:
            return (pages.layout("Changed since shown", "<p>This run's result has changed since its page was shown, so "
                                 "the version that page showed is no longer saved here; nothing was sent. Reload the "
                                 "run's page for the version now saved.</p>"), HTTPStatus.CONFLICT, "text/html")
        return data, ok, mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    raise FileNotFoundError(path)


def report_view(folder: Path) -> tuple[str | None, list[str], str, dict[str, bytes], str]:
    """What a run's page shows of its report and plots (``pages.job_page``'s ``report``, ``images``, ``note``,
    ``embedded`` and ``held``), of one version of the run's output (``evidence.version.resolve``: its result, report
    and figures read as one checked transaction; the version handle, the owner, 2026-11-03): a report of that result is
    shown with its figures as read and checked, embedded; one of another version is withheld with its figures, saying
    so; one recording no link (written before ADROIT recorded one), or beside no result, is shown as found with the
    folder's plots (the auditor's CZ recheck, DA-02, 2026-11-02). ``held``: the digest of the result read ("" without one),
    which the page's link to the result requires (VI-02)."""
    from adroit.evidence.bindings import unbound
    from adroit.evidence.version import Unsettled, resolve
    loose = sorted(p.name for p in folder.glob("*.png"))
    try:
        found = resolve(folder, presentation=True, evidence=False)
    except Unsettled:
        return None, [], "This run's output changed each time this page read it; reload the page.", {}, ""
    held = found.result_sha256 or None
    report = found.report()
    if report.state in ("absent", "unreadable"):
        return None, loose, "" if report.state == "absent" else "This run's report cannot be read.", {}, held or ""
    if report.state == "other" and held is not None:
        return None, [], ("This run's report is of another version of its result (the result was replaced while the "
                          "report was written, or since); it and its plots are not shown."), {}, held
    if report.state == "interrupted":                   # the auditor's portability audit, IC-01
        return None, [], ("This run's last publication was interrupted while it wrote its parts, so its report may be "
                          "an earlier publication's; it and its plots are not shown. Run it again to publish it "
                          "whole."), {}, held or ""
    if report.state == "bound" and report.binding is not None:
        embedded = {name: data for name in sorted(report.binding.figures)
                    if (data := found.figure(name)) is not None}
        missing = sorted(set(report.binding.figures) - set(embedded))
        return unbound(report.text), [], ("Not shown, not the plots this report was written with: " + ", ".join(missing)
                                          if missing else ""), embedded, held or ""
    return unbound(report.text), loose, ("This report records no link to the run's result (written before ADROIT "
                                         "recorded one); it and the plots are shown as found." if held is not None else
                                         ""), {}, held or ""


def serve(runs_dir: Path, port: int = 8765, open_browser: bool = True) -> None:
    """Serve the workbench until interrupted."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, port), handler_for(Board(runs_dir)))
    url = f"http://{HOST}:{port}/"
    print(f"ADROIT workbench at {url} (Ctrl-C to stop); runs in {runs_dir}", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
