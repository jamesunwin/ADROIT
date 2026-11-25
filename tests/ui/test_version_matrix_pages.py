"""The version handle's acceptance matrix: the rows that are pages (``tests/version_matrix.py`` fixes their cells;
``tests/evidence/test_version_matrix.py`` runs the others), rendered through the workbench. Each study is written by the
production writers; nothing is calculated."""
from __future__ import annotations

import json
from urllib.parse import urlencode

import pytest
from nicegui.testing import User

from tests import version_matrix as vm

PAGES = [pytest.param(row, case, id=f"{row}-{case}") for row, case, _ in vm.cells() if vm.BY_ID[row].page]


def page_text(user: User) -> tuple[str, list[str]]:
    """Everything the page shows (each element's text, content, value, rows and properties, figures decoded), and its
    elements' texts alone, in order."""
    from nicegui import ElementFilter
    parts, texts = [], []
    with user:
        for element in ElementFilter():
            for name in ("text", "content", "value"):
                value = getattr(element, name, None)
                if isinstance(value, str):
                    parts.append(value)
                    if value.strip():
                        texts.append(value)
            parts.append(json.dumps(getattr(element, "props", {}), default=str))
            if isinstance(getattr(element, "rows", None), list):
                parts.append(json.dumps(element.rows, default=str))
    return vm.text_of("\n".join(parts)), texts


REFUSALS = {"Point unavailable": 2, "Review packet unavailable": 1}     # its words, and the texts that say why


def _output(user: User) -> vm.Output:
    text, texts = page_text(user)
    for word, count in REFUSALS.items():
        found = next((i for i, value in enumerate(texts) if value.startswith(word)), None)
        if found is not None:
            return vm.Output(refused=" ".join(texts[found:found + count]))
    return vm.Output(text)


def _link(world: vm.World, row_id: str) -> str:
    """The link a page offered from its version of A (the point table's; the review queue's task's)."""
    from adroit.constraints.review_queue import build_queue, load_selected
    from adroit.evidence.version import Token, resolve
    held = resolve(world.folder, presentation=True)
    token = held.token()
    shown = Token(token.path, result=token.result, evidence=token.evidence).query(world.root)
    if row_id == "point.page":
        return "/study/point?" + urlencode({**shown, "point": "grid:0"})
    from adroit.constraints.database import records
    task = next((t for t in build_queue(load_selected(held)).tasks if t.record_id), None)
    record = task.record_id if task else records()[0].id
    return "/record?" + urlencode({"id": record, "study": "study", "task": task.id if task else "",
                                   "sha256": shown["sha256"], "evidence": shown["evidence"]})


FIELDED = {"study.page": True, "point.table": False}     # rows whose page's fields are compared (DE-03): with a summary


def _fields(user: User, summary: bool) -> dict:
    """The page's fields (``vm.fields``): its point table's rows as shown, its interactive plane (``vm.chart_of``;
    the auditor's DF recheck, DG-03), and, with ``summary``, the study summary's verdict (with its certification), its
    certification's line, its cost, the time it was calculated (its exact UTC value) and how long it took (the auditor's DD
    recheck, DE-03)."""
    from nicegui import ElementFilter
    with user:
        tables = list(ElementFilter(marker="points"))
        rows = [dict(row) for table in tables for row in table.rows]
        heads = [{"columns": [dict(c) for c in table.columns],          # which header each field is under (DK-03)
                  "slots": {name: slot.template for name, slot in table.slots.items() if name != "default"},
                  "table": {k: v for k, v in table.props.items() if k not in ("rows", "columns")}}
                 for table in tables]
        charts = [vm.chart_of(chart.options) for chart in ElementFilter(marker="plane_chart")]
        marked = {name: [e.text for e in ElementFilter(marker=marker)]
                  for name, marker in (("verdict", "study_verdict"), ("certification", "study_certification"),
                                       ("cost", "study_cost"))}
    shown: dict = {"points": rows or None,
                   "chart": charts[0] if len(charts) == 1 else {"points": {"charts": len(charts)}} if charts else None}
    shown.update(heads[0] if len(heads) == 1 else dict.fromkeys(("columns", "slots", "table"),
                                                                 {"tables": len(heads)} if heads else None))
    if summary:
        texts = page_text(user)[1]
        stamps = [t for t in texts if t.startswith("UTC: ")]
        took = [t for t in texts if t.startswith("took ")]
        shown.update({name: " | ".join(found) if found else None for name, found in marked.items()})
        shown.update(calculated=" | ".join(stamps) if stamps else None, took=" | ".join(took) if took else None)
    return shown


def _links(user: User) -> vm.Output:
    """The links the study page's point table offers (``points_panel``: each names the version it was chosen from);
    the page's own output where it shows no table (a refusal)."""
    from nicegui import ElementFilter
    with user:
        rows = [row for table in ElementFilter(marker="points") for row in table.rows]
    return vm.Output("\n".join(row.get("open") or "" for row in rows)) if rows else _output(user)


@pytest.mark.parametrize("row_id, case", PAGES)
async def test_a_page_row(user: User, tmp_path, monkeypatch, row_id, case):
    from adroit.ui.app import build_pages
    from tests.version_events import after_resolution, during_resolution
    row = vm.BY_ID[row_id]
    wanted = vm.expected(row, case)
    if wanted.startswith("N/A"):
        pytest.skip(wanted)
    if row.kind == "packet":            # the review page: its images as its rendering wrote them (DI-01)
        from tests.ui.test_di_review_page import review_page
        found = await review_page(user, tmp_path, monkeypatch, case)
        assert found == wanted, f"{row_id} × {case}: expected {wanted}, observed {found}"
        return
    if row.kind == "curated":           # a curated record's page: its figure, state and binding one reading (DL-01)
        from tests.ui.test_dl_record_page import record_page
        found = await record_page(user, tmp_path, monkeypatch, case)
        assert found == wanted, f"{row_id} × {case}: expected {wanted}, observed {found}"
        return
    world = vm.world_for(row_id, tmp_path, legacy=case == "L")
    build_pages(world.root)
    if row.kind == "archive":
        found = await _bundle(user, world, tmp_path, case)
    elif row_id == "approve.idea":
        found = await _approve(user, world, case, monkeypatch)
    elif row.kind == "held":
        page = "/studies" if row_id == "history.row" else "/study?" + urlencode({"path": "study"})
        with vm.at(world, case):
            await user.open(page)
        shown = _links(user) if row_id == "point.table" else _output(user)
        found = vm.outcome(world, shown, vm.required(row, case), exact=case == "B")
        if row_id in FIELDED:           # and every field it shows, whole (DE-03)
            fielded = vm.fields(world, _fields(user, FIELDED[row_id]))
            assert vm.fields_agree(fielded, wanted), f"{row_id} × {case}: fields {fielded}, expected {wanted}"
    else:
        link = _link(world, row_id)
        if case == "ABA":
            found = await _aba(user, world, link, row)
        else:
            if case in vm.CHANGED:
                vm.change(world, case)
            context = (during_resolution("result.json", lambda: vm.publish(world, "B")) if case == "T1" else
                       after_resolution(lambda: vm.publish(world, "B")) if case == "T2" else
                       vm.always(world) if case == "T3" else _Nothing())
            with context:
                await user.open(link)
            found = vm.outcome(world, _output(user), vm.required(row, case), exact=case == "B")
    assert vm.agrees(found, wanted), f"{row_id} × {case}: expected {wanted}, observed {found}"


async def _approve(user: User, world: vm.World, case: str, monkeypatch) -> str:
    """An idea study's approval (``approve_panel``): the page opened on A, the case's change made, then "Constrain the
    approved models" clicked; what it launched (its command and the approved model it wrote), or what it said."""
    from pathlib import Path
    from types import SimpleNamespace
    from adroit.core.durable import write_atomic
    from adroit.orchestrator import studies
    from adroit.ui import engine
    from tests.version_events import after_resolution, during_resolution
    calls = []
    monkeypatch.setattr(engine, "launch", lambda command, folder, title, **kw: calls.append(command) or
                        SimpleNamespace(folder=str(folder)))

    async def click(context=None) -> str:
        calls.clear()
        user.notify.messages.clear()
        with context or _Nothing():
            user.find("Constrain the approved models").click()
        said = user.notify.messages
        if calls:
            return vm.outcome(world, vm.Output(vm.text_of([calls[-1], Path(calls[-1][1]).read_text()])),
                              vm.required(vm.BY_ID["approve.idea"], case), exact=case == "B")
        return vm.outcome(world, vm.Output(refused=said[-1]) if said else vm.Output(), ("result",))
    page = "/study?" + urlencode({"path": "study"})
    await user.open(page)
    if case == "ABA":
        kept = {p.name: p.read_bytes() for p in world.folder.iterdir() if p.is_file()}
        vm.publish(world, "B")
        for name, data in kept.items():
            write_atomic(world.folder / name, data)
        first = await click()
        record = studies.load(world.folder)
        studies.save(record.model_copy(update={"created": "2026-11-05T00:00:00+00:00"}))
        await user.open(page)
        second = await click()
        return first if first == second else f"{first}, then {second}"
    if case in vm.CHANGED:
        vm.change(world, case)
    return await click(during_resolution("result.json", lambda: vm.publish(world, "B")) if case == "T1" else
                       after_resolution(lambda: vm.publish(world, "B")) if case == "T2" else
                       vm.always(world) if case == "T3" else None)


async def _bundle(user: User, world: vm.World, tmp, case: str) -> str:
    """Open a bundle (``_show_bundle``): A's exported bundle, B's saved over its file once its bytes are held (R, T1);
    the page must show A's verification whole, as A's bundle alone gives it (its digest, each node's decisions)."""
    from unittest.mock import patch
    from adroit.evidence import archive
    bundle_a, bundle_b, selected, alone = (tmp / f"{n}.zip" for n in ("a", "b", "selected", "alone"))
    archive.export_run(world.folder, bundle_a)
    vm.publish(world, "B")
    archive.export_run(world.folder, bundle_b)
    selected.write_bytes(bundle_a.read_bytes())
    alone.write_bytes(bundle_a.read_bytes())

    async def shown(path) -> list[str]:
        await user.open("/bundle?" + urlencode({"path": str(path)}))
        return [text.replace(str(path), "<bundle>") for text in page_text(user)[1]]
    expected = await shown(alone)
    real = archive.held_bundle

    def replaced(where):
        data = real(where)
        if case in ("R", "T1") and str(where) == str(selected):
            selected.write_bytes(bundle_b.read_bytes())
        return data
    with patch.object(archive, "held_bundle", replaced):
        found = await shown(selected)
    return "A" if found == expected else f"not A's whole: {sorted(set(found) ^ set(expected))[:6]}"


async def test_the_page_harness_detects_a_headline_of_another_version(user: User, tmp_path):
    """DD-03, the auditor's page mutant: the Studies page with B's verdict beside A's record (a headline read from the study
    as saved now) is caught by its cell (it had passed: the row declared only its record)."""
    from unittest.mock import patch
    from adroit.evidence import version
    from adroit.ui.app import build_pages
    from tests.evidence.test_version_matrix import _latest_headline
    world = vm.make(tmp_path)
    build_pages(world.root)
    with patch.object(version.Version, "headline", _latest_headline(version.Version.headline)), vm.at(world, "R"):
        await user.open("/studies")
    found = vm.outcome(world, _output(user), vm.BY_ID["history.row"].shows)
    assert found.startswith("mixed"), found


def _decision_of_the_saved_study(world: vm.World):
    """The auditor's planted fault (its DD recheck, DE-03): the point table's rows keep the held version's points and
    coordinates, their status and first reason read from the study as saved now."""
    from unittest.mock import patch
    from adroit.evidence import points, version
    real = points.points

    def mixed(workflow, result):
        rows = real(workflow, result)
        if workflow != "track1":
            return rows
        now = {r.point_id: r for r in real(workflow, version.resolve(world.folder).typed())}
        return [r.model_copy(update={"status": now.get(r.point_id, r).status, "reason": now.get(r.point_id, r).reason})
                for r in rows]
    return patch.object(points, "points", mixed)


def _dates_of_the_saved_record(world: vm.World):
    """A planted fault (DE-03): the summary's record dates (when it was calculated, how long it took) read from the
    study's record as saved now, beside the rest of the version the page holds."""
    from unittest.mock import patch
    from adroit.orchestrator import studies
    from adroit.ui import pages
    real = pages._summary

    def summary(root, version, s, read):
        now = studies.load(world.folder)
        return real(root, version, s.model_copy(update={"calculation_started_at": now.calculation_started_at,
                                                        "calculation_completed_at": now.calculation_completed_at}), read)
    return patch.object(pages, "_summary", summary)


def _certification_of_the_saved_study(world: vm.World):
    """A planted fault (DE-03): the summary's certification line of the study's result as saved now, beside the rest of
    the version the page holds."""
    import json
    from unittest.mock import patch
    from adroit.evidence.version import resolve
    from adroit.ui import pages
    real = pages._certification_line

    def line(found, data):
        now = resolve(world.folder)
        return real(now.headline(), json.loads(now.content))
    return patch.object(pages, "_certification_line", line)


def _link_to_another_point(world: vm.World):
    """The auditor's planted fault (its DE recheck, DF-03): grid:0's row links to grid:1, naming the held version's own
    result and evidence."""
    from unittest.mock import patch
    from adroit.ui import points
    real = points.point_link
    return patch.object(points, "point_link", lambda chosen, point: real(chosen, "grid:1" if point == "grid:0" else point))


def _link_to_another_study(world: vm.World):
    """The auditor's planted fault (DF-03): each row's link names another study, with the held version's own result and
    evidence."""
    from unittest.mock import patch
    from adroit.ui import points
    real = points.point_link
    return patch.object(points, "point_link", lambda chosen, point: real({**chosen, "path": "other-study"}, point))


def _certification_with_more_words(world: vm.World):
    """The auditor's planted fault (DF-03): the held version's own certification line, with words that contradict it."""
    from unittest.mock import patch
    from adroit.ui import pages
    real = pages._stale_on
    return patch.object(pages, "_stale_on", lambda data: real(data) + "; certified under the current policy")


def _link_of_another_origin(world: vm.World):
    """The auditor's planted fault (its DF recheck, DG-03): each row's link the point's page of another site, its path and
    query exact."""
    from unittest.mock import patch
    from adroit.ui import points
    real = points.point_link
    return patch.object(points, "point_link", lambda chosen, point: "https://wrong-study.invalid" + real(chosen, point))


def _chart_status_relabelled(world: vm.World):
    """The auditor's planted fault (DG-03): the plane draws the excluded points as allowed, in the allowed colour; its
    table unchanged."""
    from unittest.mock import patch
    from adroit.ui import points
    real = points.chart_options

    def options(*args, **kwargs):
        found = real(*args, **kwargs)
        for series in (found or {}).get("series", []):
            if series["name"] == "excluded":
                series.update(name="allowed", itemStyle={"color": points.COLOURS["allowed"]})
        return found
    return patch.object(points, "chart_options", options)


def _chart_options_changed(change):
    """A planted fault: the plane's options as ``chart_options`` gives them, then changed by ``change``."""
    from unittest.mock import patch
    from adroit.ui import points
    real = points.chart_options

    def options(*args, **kwargs):
        found = real(*args, **kwargs)
        if found:
            change(found)
        return found
    return patch.object(points, "chart_options", options)


def _columns_changed(change, slot: tuple[str, str] | None = None):
    """A planted fault (the auditor's DJ recheck, DK-03): the columns passed to the point table's real table changed by
    ``change``, or a cell slot added to it (``slot``: its name and template), its rows as the page built them."""
    from unittest.mock import patch
    from nicegui import ui
    real = ui.table

    def table(*args, columns=None, **kwargs):
        ours = bool(columns) and any(c.get("name") == "omega" for c in columns)
        if ours and change is not None:
            columns = [dict(c) for c in columns]
            change(columns)
        made = real(*args, columns=columns, **kwargs)
        if ours and slot is not None:
            made.add_slot(*slot)
        return made
    return patch.object(ui, "table", table)


def _column(name: str, **changed):
    return lambda world: _columns_changed(lambda columns: next(c for c in columns if c["name"] == name).update(changed))


def _own(**drawn):
    """The auditor's planted fault (its DG recheck, DH-02): each excluded point given its own appearance (``drawn``: its
    colour, symbol or size), its series unchanged."""
    def change(options):
        for series in options["series"]:
            if series["name"] == "excluded":
                for item in series["data"]:
                    item.update(drawn)
    return lambda world: _chart_options_changed(change)


def _chart_of_the_saved_study(world: vm.World):
    """A planted fault (DG-03): the plane drawn from the study as saved now, beside the table of the version the page
    holds."""
    from unittest.mock import patch
    from adroit.evidence import points as found
    from adroit.evidence.version import resolve
    from adroit.ui import points
    real = points.chart_options

    def options(workflow, result, rows):
        now = resolve(world.folder).typed()
        return real(workflow, now, found.points(workflow, now))
    return patch.object(points, "chart_options", options)


def _chart_left_out(world: vm.World):
    """A planted fault (DG-03): the points panel without its plane."""
    from unittest.mock import patch
    from adroit.ui import points
    return patch.object(points, "plane_chart", lambda *args, **kwargs: None)


def _duration_left_out(world: vm.World):
    """The auditor's planted fault (DF-03): the summary without how long its calculation took."""
    from unittest.mock import patch
    from adroit.ui import style
    return patch.object(style, "duration", lambda start, end: "")


FAULTS = {"decision": _decision_of_the_saved_study, "dates": _dates_of_the_saved_record,
          "certification": _certification_of_the_saved_study, "another point": _link_to_another_point,
          "another study": _link_to_another_study, "more words": _certification_with_more_words,
          "no duration": _duration_left_out, "another origin": _link_of_another_origin,
          "chart relabelled": _chart_status_relabelled, "chart of the saved study": _chart_of_the_saved_study,
          "no chart": _chart_left_out, "a point's own colour": _own(itemStyle={"color": "#2e7d32"}),
          "a point's own symbol": _own(symbol="diamond"), "a point's own size": _own(symbolSize=14),
          "an axis inverted": lambda world: _chart_options_changed(lambda o: o["xAxis"].update(inverse=True)),
          "a visual map": lambda world: _chart_options_changed(lambda o: o.update(visualMap={
              "type": "piecewise", "pieces": [{"min": 0, "color": "#2e7d32"}]})),
          "a legend hiding the excluded": lambda world: _chart_options_changed(lambda o: o["legend"].update(
              selected={"excluded": False, "excluded (thermal roots)": False})),
          "a tooltip's own words": lambda world: _chart_options_changed(lambda o: o.update(
              tooltip={"formatter": "Allowed; Ωh² = 0.120000; no pending checks"})),
          "no legend": lambda world: _chart_options_changed(lambda o: o["legend"].update(show=False)),
          "an axis name moved away": lambda world: _chart_options_changed(lambda o: o["yAxis"].update(nameGap=400)),
          "an empty series' false label": lambda world: _chart_options_changed(lambda o: o["series"].append({
              "type": "scatter", "name": "ALL POINTS ALLOWED; NO PENDING CHECKS", "data": [], "symbol": "circle",
              "symbolSize": 7, "itemStyle": {"color": "#2e7d32"}})),
          "Ωh² headed as a cross section": _column("omega", label="σ_SI (cm²)"),
          "the status column showing Ωh²": _column("status", field="omega"),
          "a status cell drawn from Ωh²": lambda world: _columns_changed(None, (
              "body-cell-status", '<q-td :props="props">{{ props.row.omega }}</q-td>'))}


@pytest.mark.parametrize("fault, row_id, said, caught", [
    ("decision", "study.page", "grid:0 status", "mixed fields"), ("decision", "point.table", "grid:0 reason",
                                                                  "mixed fields"),
    ("dates", "study.page", "calculated", "mixed fields"), ("certification", "study.page", "certification",
                                                            "mixed fields"),
    ("another point", "study.page", "grid:0 link's point", "fields of neither"),
    ("another point", "point.table", "grid:0 link's point", "fields of neither"),
    ("another study", "study.page", "link's study", "fields of neither"),
    ("another study", "point.table", "link's study", "fields of neither"),
    ("more words", "study.page", "certification", "fields of neither"),
    ("no duration", "study.page", "took", "missing fields"),
    ("another origin", "study.page", "grid:0 link's origin", "fields of neither"),
    ("another origin", "point.table", "grid:0 link's origin", "fields of neither"),
    ("chart relabelled", "study.page", "grid:0 on the chart", "fields of neither"),
    ("chart relabelled", "point.table", "grid:0 on the chart", "fields of neither"),
    ("chart of the saved study", "study.page", "on the chart", "mixed fields"),
    ("chart of the saved study", "point.table", "on the chart", "mixed fields"),
    ("no chart", "study.page", "chart", "missing fields"), ("no chart", "point.table", "chart", "missing fields"),
    ("a point's own colour", "study.page", "grid:0 on the chart", "fields of neither"),
    ("a point's own colour", "point.table", "grid:0 on the chart", "fields of neither"),
    ("a point's own symbol", "study.page", "grid:0 on the chart", "fields of neither"),
    ("a point's own symbol", "point.table", "grid:0 on the chart", "fields of neither"),
    ("a point's own size", "study.page", "grid:0 on the chart", "fields of neither"),
    ("a point's own size", "point.table", "grid:0 on the chart", "fields of neither"),
    ("an axis inverted", "study.page", "xAxis\\'s inverse", "fields of neither"),
    ("a visual map", "study.page", "plane\\'s visualMap", "fields of neither"),
    ("a legend hiding the excluded", "study.page", "legend\\'s selected", "fields of neither"),
    ("a legend hiding the excluded", "point.table", "legend\\'s selected", "fields of neither"),
    ("a tooltip's own words", "study.page", "tooltip\\'s formatter", "fields of neither"),
    ("a tooltip's own words", "point.table", "tooltip\\'s formatter", "fields of neither"),
    ("no legend", "study.page", "legend\\'s show", "fields of neither"),
    ("no legend", "point.table", "legend\\'s show", "fields of neither"),
    ("an axis name moved away", "study.page", "yAxis\\'s nameGap", "fields of neither"),
    ("an axis name moved away", "point.table", "yAxis\\'s nameGap", "fields of neither"),
    ("an empty series' false label", "study.page", "the chart's series", "fields of neither"),
    ("an empty series' false label", "point.table", "the chart's series", "fields of neither"),
    ("Ωh² headed as a cross section", "study.page", "the table's columns", "fields of neither"),
    ("Ωh² headed as a cross section", "point.table", "the table's columns", "fields of neither"),
    ("the status column showing Ωh²", "study.page", "the table's columns", "fields of neither"),
    ("the status column showing Ωh²", "point.table", "the table's columns", "fields of neither"),
    ("a status cell drawn from Ωh²", "study.page", "the table\\'s cell slots", "fields of neither"),
    ("a status cell drawn from Ωh²", "point.table", "the table\\'s cell slots", "fields of neither")])
async def test_the_page_harness_detects_a_field_of_another_version(user: User, tmp_path, fault, row_id, said,
                                                                   caught):
    """DE-03, the auditor's planted point-decision fault (and the dates' and certification's like it): the study page's point
    table showing A's points with B's status and reason, or its summary A's version with B's record dates or B's
    certification, passes the text oracle (no mark of B is shown) and is caught by the cell's field assertion, at the
    field. And DF-03, the auditor's four more: a row linking to another point, or to another study, with A's own identities; A's
    certification line with contradicting words more; the summary without its duration: each caught at its field. And
    DG-03, the auditor's two more: each link to another site, its path and query A's; the plane drawing A's excluded point as
    allowed, its table A's; and the plane of the study as saved now (B's) beside A's table, and no plane: each caught at
    its field. And DH-02, the auditor's: A's excluded point given its own colour (the allowed green), symbol or size, its
    series unchanged; and an axis inverted, and a visual map recolouring the points, beyond the plane's contract. And
    DI-02, the auditor's two more (its DH recheck): a legend hiding the excluded series, and a tooltip of its own words (every
    point allowed); and a legend hidden, and an axis's name moved away from it: each what the plane says of itself, read
    whole (``PLANE``'s ``said``). And DJ-02, the auditor's (its DI recheck): an empty series more, its name a false statement
    ("ALL POINTS ALLOWED; NO PENDING CHECKS") that ECharts' legend shows, no point changed: caught at the chart's series,
    read whole. And DK-03, the auditor's two (its DJ recheck), the point table's rows unchanged: the Ωh² column headed as a
    cross section (σ_SI), and the status column showing Ωh²; and a status cell drawn from Ωh² by a cell slot: each caught
    at the table's columns or cell slots, read whole (``vm.COLUMNS``, ``vm.CELL_SLOTS``)."""
    from adroit.ui.app import build_pages
    world = vm.make(tmp_path)
    build_pages(world.root)
    with FAULTS[fault](world), vm.at(world, "R"):
        await user.open("/study?" + urlencode({"path": "study"}))
    row = vm.BY_ID[row_id]
    text = vm.outcome(world, _links(user) if row_id == "point.table" else _output(user), vm.required(row, "R"))
    found = vm.fields(world, _fields(user, FIELDED[row_id]))
    assert vm.agrees(text, vm.expected(row, "R")), text            # the marks alone pass it
    assert not vm.fields_agree(found, vm.expected(row, "R")) and caught in found, found
    assert said in found, found


def _images_by_path(root):
    """The auditor's DI-01 defect restored: each image of the review page named by the path of the file it was written to
    (``/files/...``, as its rendering's report names it), for the browser to read later."""
    from contextlib import ExitStack
    from pathlib import Path
    from unittest.mock import patch
    from adroit.ui import experimental_review as page
    real = page.rendered_packet

    def rendered(*args, **kwargs):
        report, images = real(*args, **kwargs)
        return report, {k: None if v is None else report[k].encode() for k, v in images.items()}

    def named(path: bytes, media: str = "image/png") -> str:
        return "/files/" + str(Path(path.decode()).resolve().relative_to(root.resolve()))
    stack = ExitStack()
    stack.enter_context(patch.object(page, "rendered_packet", rendered))
    stack.enter_context(patch.object(page, "embedded", named))
    return stack


def _shown_unbound(root):
    """A planted fault: the page's figure verification not bound to the packet it showed (``shown`` dropped)."""
    from unittest.mock import patch
    from adroit.ui import experimental_review as page
    real = page.verify_figure
    return patch.object(page, "verify_figure", lambda *a, shown=None, **k: real(*a, **k))


REVIEW_CONTROLS = {"images named by their paths": ("T1", _images_by_path, "shown: A's text True, B's False"),
                   "the packet shown not bound": ("T2", _shown_unbound, "A")}


@pytest.mark.parametrize("name", REVIEW_CONTROLS)
async def test_the_review_page_harness_detects_each_defect(user: User, tmp_path, monkeypatch, name):
    """Negative controls of the row ``review.page`` (DI-01): the page naming its images by their paths (the auditor's
    defect), caught at T1, where the browser reads B's plots beside A's text; and its verification not bound to the
    packet it showed, caught at T2, where A's source's packet drawn otherwise is verified though the researcher never
    saw it."""
    from tests.ui.test_di_review_page import review_page
    case, fault, said = REVIEW_CONTROLS[name]
    with fault(tmp_path / "runs"):
        found = await review_page(user, tmp_path, monkeypatch, case)
    assert found != vm.expected(vm.BY_ID["review.page"], case) and found.startswith(said), f"{name}: {found}"


async def test_the_record_page_harness_detects_its_state_read_apart(user: User, tmp_path, monkeypatch):
    """DL-01's defect restored, the negative control of the row ``records.page``: the page's signature state read
    again from the records and the data file as they then stand (as the pin read it), not from its reading. Its T1
    cell fails: A's figure is shown beside B's stale state."""
    from adroit.constraints import database
    from adroit.constraints.review_identity import signature_status
    from adroit.ui import records
    monkeypatch.setattr(records, "signature_status", lambda record, version_of=None: signature_status(
        next(x for x in database.records() if x.id == record.id)))
    with pytest.raises(AssertionError, match="records.page × T1"):
        await test_a_page_row(user, tmp_path, monkeypatch, "records.page", "T1")


async def _aba(user: User, world: vm.World, link: str, row: vm.Row) -> str:
    from adroit.core.durable import write_atomic
    from adroit.orchestrator import studies
    kept = {p.name: p.read_bytes() for p in world.folder.iterdir() if p.is_file()}
    vm.publish(world, "B")
    for name, data in kept.items():
        write_atomic(world.folder / name, data)
    await user.open(link)
    first = vm.outcome(world, _output(user), row.shows)
    record = studies.load(world.folder)
    studies.save(record.model_copy(update={"created": "2026-11-05T00:00:00+00:00"}))
    await user.open(link)
    second = vm.outcome(world, _output(user), row.shows)
    if first.startswith("A") and second.startswith("refused"):
        return "A then refused"
    return first if first == second else f"{first}, then {second}"


class _Nothing:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False
