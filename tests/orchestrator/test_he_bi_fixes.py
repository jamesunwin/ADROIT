"""The auditor's merge-round audit (the independent audit of 2026-11-12 (merge round)) and bounded-interfaces audit
(the independent audit of 2026-11-12 (bounded interfaces)), their findings repaired (the DX repair record of 2026-11-12).

- HE-01: a publication's mark is its own output's, removed only once that publication has written every part.
- HE-02: a promoted child, a model builder's proposals and a native fit are marked through their study record.
- BI-01: a binned background shape is spread by one rule, inline or digitised: its exact integral over the window is
  the record's count.
- BI-02: a production table replaced in a warm process is read again; a call reads one version.

The publications are real (the writers, the readers, the exports and their verification); the numerical results are
typed fixtures, as in the auditor's controls."""

from __future__ import annotations

import errno
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from adroit.core import durable
from adroit.evidence import archive, build, runtime, version
from adroit.orchestrator import ideas, promote, runs, signal, single_idea
from adroit.ui import pages


def _result() -> signal.SignalResult:
    from adroit.inference.dm_tournament import TournamentResult
    return signal.SignalResult(
        request=signal.SignalRequest(experiment="CDMS II Si (2013)", null_modules=[]), fits=[], classes={},
        n_classes=0, max_local_z=0, global_p_toys=1, global_p_closed_form=None, global_z=0, combinations=[],
        tournament=TournamentResult(ranking=[], indistinguishable=[], classes_in_top_set=[], signal_fit_leader="",
                                    null_rank=0), separations=[])


def _dated(result, day: int):
    ctx = runtime.capture_request(result.request, experiments=False)
    return ctx.model_copy(update={"calculation_started_at": f"2026-11-{day:02d}T10:00:00Z",
                                  "calculation_completed_at": f"2026-11-{day:02d}T10:01:00Z"})


def _failing_record():
    """``durable.write_atomic`` failing at a study record (ENOSPC), as the auditor's controls inject it."""
    write = durable.write_atomic

    def fail(path, data, **kwargs):
        if Path(path).name == "study.json":
            raise OSError(errno.ENOSPC, "SIMULATED study record failure")
        return write(path, data, **kwargs)
    return patch.object(durable, "write_atomic", fail)


def _seen(folder: Path, tmp: Path) -> dict:
    """What a person and an export see of the folder's study: interrupted or not, its record's state, its cost, its
    bundle's warnings."""
    held = version.resolve(folder, presentation=True)
    target = tmp / f"{folder.name}-{len(list(tmp.glob('*.zip')))}.zip"
    archive.export_run(held, target)
    manifest, _ = archive.read_bundle(target)
    return {"interrupted": held.interrupted, "record": held.record_state, "cost": pages.study_cost(held),
            "warnings": manifest.warnings, "valid": archive.verify_bundle(target).valid}


def _interrupted(folder: Path) -> None:
    """Publication A whole ($0.08, 8 November), then B with the same result bytes stopped at its study record."""
    result = _result()
    runs._write(folder, result, "# A report\n", "signal", "Publication A", cost_usd=.08,
                evidence_context=_dated(result, 8))
    with _failing_record(), pytest.raises(OSError):
        runs._write(folder, result, "# B report\n", "signal", "Publication B", cost_usd=.09,
                    evidence_context=_dated(result, 9))


# --- HE-01 -------------------------------------------------------------------------------------------------------------

def test_a_promotion_published_beside_an_interrupted_study_leaves_the_study_interrupted(tmp_path):
    """The auditor's separately named output: a promotion's record published into the folder of a study whose own
    publication was interrupted. At the pin it removed the study's mark: the study read bound, A's $0.08 and dates
    beside B's evidence, and its bundle verified with no warning."""
    folder = tmp_path / "parent"
    _interrupted(folder)
    before = _seen(folder, tmp_path)
    assert before["interrupted"] and before["record"] == "interrupted"
    promotion = promote.Promotion(parent=str(folder), labels=["fixture"], undetermined={"fixture": "no child"},
                                  parent_sha256=hashlib.sha256((folder / "result.json").read_bytes()).hexdigest())
    with patch.object(promote, "promote", return_value=promotion):
        runs.promote(folder, ["fixture"])
    after = _seen(folder, tmp_path)
    assert (folder / build.MARK).exists() and after["interrupted"] and after["record"] == "interrupted"
    assert "0.08" not in after["cost"] and after["warnings"] and after == before
    assert not build.mark_path(folder / "promotion_fixture.json").exists()          # the promotion, whole


def test_a_promotion_s_own_interruption_marks_only_itself(tmp_path):
    folder = tmp_path / "parent"
    result = _result()
    runs._write(folder, result, "# A report\n", "signal", "Publication A", evidence_context=_dated(result, 8))
    promotion = promote.Promotion(parent=str(folder), labels=["fixture"], undetermined={"fixture": "no child"},
                                  parent_sha256=hashlib.sha256((folder / "result.json").read_bytes()).hexdigest())
    from adroit.evidence import bindings
    write = durable.write_atomic

    def fail(path, data, **kwargs):
        if Path(path) == bindings.report_path(folder / "promotion_fixture.json"):
            raise OSError(errno.ENOSPC, "SIMULATED promotion report failure")
        return write(path, data, **kwargs)
    with patch.object(promote, "promote", return_value=promotion), patch.object(durable, "write_atomic", fail), \
            pytest.raises(OSError):
        runs.promote(folder, ["fixture"])
    assert build.mark_path(folder / "promotion_fixture.json").exists() and not (folder / build.MARK).exists()
    assert version.resolve(folder / "promotion_fixture.json", presentation=True).interrupted
    assert not version.resolve(folder, presentation=True).interrupted


def test_evidence_replaced_from_outside_keeps_the_mark(tmp_path):
    """The auditor's partial replacement: only the evidence replaced from outside after the writer saved it. The
    writer stops (``Replaced``), as before; at the pin it then removed its mark, and the old record and report read
    bound to the other evidence (10 November) with A's cost."""
    folder = tmp_path / "partial"
    result = _result()
    runs._write(folder, result, "# A report\n", "signal", "Publication A", cost_usd=.08,
                evidence_context=_dated(result, 8))
    other = build.build("signal", result, hashlib.sha256((folder / "result.json").read_bytes()).hexdigest(),
                        _dated(result, 10))
    save = build.save

    def replaced(*args, **kwargs):
        envelope = save(*args, **kwargs)
        durable.write_atomic(build.sidecar_path(Path(args[0])), json.dumps(
            other.model_dump(mode="json"), ensure_ascii=False, allow_nan=True).encode())
        return envelope
    with patch.object(build, "save", replaced), pytest.raises(build.Replaced):
        runs._write(folder, result, "# B report\n", "signal", "Publication B", cost_usd=.09,
                    evidence_context=_dated(result, 9))
    seen = _seen(folder, tmp_path)
    assert (folder / build.MARK).exists() and seen["interrupted"] and "0.08" not in seen["cost"] and seen["warnings"]
    runs._write(folder, result, "# C report\n", "signal", "Publication C", evidence_context=_dated(result, 11))
    assert not (folder / build.MARK).exists() and not _seen(folder, tmp_path)["interrupted"]    # whole: unmarked


def test_each_output_has_its_own_mark():
    folder = Path("/study")
    assert build.mark_path(folder / "result.json") == folder / build.MARK
    assert build.mark_path(folder / "promotion_a_b.json") == folder / f"promotion_a_b.{build.MARK}"


# --- HE-02 -------------------------------------------------------------------------------------------------------------

def _child_request(folder: Path):
    from adroit.parameter_space import simplified
    req = signal.SignalRequest(experiment="CDMS II Si (2013)", null_modules=[], halo=None)
    parent = SimpleNamespace(request=req, global_z=0.0)
    candidate = signal.Candidate(label="fixture@10", card_id="O1", isospin="s", mass_gev=10)
    spec = simplified.model("vector", 10, 1000)
    child = single_idea.SingleIdeaResult(request=promote._child_request(req, candidate, spec,
                                                                        {"masses": 3, "grid": 4, "toys": 2}, None),
                                         level="undetermined", summary="SIMULATED numerical result")
    return parent, candidate, spec, child


def test_a_promoted_child_stopped_at_its_record_stays_interrupted(tmp_path):
    """The auditor's ``promoted-child-record-failure``: the same child published again with another origin, stopped at
    its study record. At the pin its mark had gone with its parts: the old record (``first origin``) read bound beside
    the new evidence, its bundle with no warning."""
    folder = tmp_path / "parent"
    parent, candidate, spec, child = _child_request(folder)
    with patch.object(single_idea, "run", return_value=child):
        first = promote._study(folder, parent, candidate, "first origin", spec, {"masses": 3, "grid": 4, "toys": 2})
        with _failing_record(), pytest.raises(OSError):
            promote._study(folder, parent, candidate, "second origin", spec, {"masses": 3, "grid": 4, "toys": 2})
    seen = _seen(Path(first.folder), tmp_path)
    assert (Path(first.folder) / build.MARK).exists() and seen["interrupted"] and seen["record"] == "interrupted"
    assert seen["warnings"]


def test_a_model_builder_s_proposals_stopped_at_their_record_stay_interrupted(tmp_path):
    """The auditor's ``proposal_publication``: a second simulated $0.09 publication stopped at its record. At the pin it
    read bound with the first's $0.08, its bundle with no warning."""
    llm, charge = SimpleNamespace(spent=0.0), [0.08]
    result = ideas.IdeaResult(request=ideas.IdeaRequest(text="SIMULATED proposal"), dropped=["no calculation"])

    def fake(*args, **kwargs):
        llm.spent += charge[0]
        return result
    candidate = signal.Candidate(label="O1@10", card_id="O1", isospin="s", mass_gev=10)
    with patch.object(ideas, "run", fake):
        folder, *_ = promote._proposals(tmp_path, candidate, llm, 1)
        charge[0] = 0.09
        with _failing_record(), pytest.raises(OSError):
            promote._proposals(tmp_path, candidate, llm, 1)
    seen = _seen(folder, tmp_path)
    assert (folder / build.MARK).exists() and seen["interrupted"] and "0.08" not in seen["cost"] and seen["warnings"]


def test_a_native_fit_stopped_at_its_record_stays_interrupted(tmp_path):
    """The auditor's ``native_publication``: the fit published on 8 November, then again on 9 November stopped at its
    record. At the pin the record dated it 8 November beside 9 November's evidence, with no warning."""
    from adroit.core.evidence import EvidenceContext
    from adroit.orchestrator import native_fit, track1_identity
    from adroit.parameter_space import native_joint, simplified
    from tests.orchestrator.test_db_recheck import _native_fit
    fitted, _ = _native_fit(tmp_path)
    fitted.complete = False
    request = native_fit.NativeFitRequest(spec=simplified.model("vector", 60, 125), masses_gev=[60],
                                          settings=fitted.settings)
    folder, day = tmp_path / "study", [8]

    def context(*args, **kwargs):
        return EvidenceContext(calculation_started_at=f"2026-11-{day[0]:02d}T10:00:00Z",
                               calculation_completed_at=f"2026-11-{day[0]:02d}T10:01:00Z")
    with patch.object(track1_identity, "dependencies", return_value={}), \
            patch.object(runtime, "capture_request", context), \
            patch.object(runtime, "finish", side_effect=lambda c, **kwargs: c), \
            patch.object(native_joint, "run", lambda *a, **k: fitted):
        native_fit.run_reported(request, folder)
        day[0] = 9
        with _failing_record(), pytest.raises(OSError):
            native_fit.run_reported(request, folder)
    seen = _seen(folder, tmp_path)
    assert (folder / build.MARK).exists() and seen["interrupted"] and seen["record"] == "interrupted"
    assert seen["warnings"]


def test_each_writer_whose_last_part_follows_its_publication_holds_the_mark_through_it():
    """Every ``build.publish`` caller that writes a part of its publication after it (its study record, its offers)
    marks the whole: ``runs._write``, ``promote._study``, ``promote._proposals``, ``native_fit.run_reported``."""
    import inspect
    from adroit.orchestrator import native_fit
    for function in (runs._write, promote._study, promote._proposals, native_fit.run_reported):
        source = inspect.getsource(function)
        assert "incomplete(" in source and "marked=True" in source, function.__qualname__
        assert source.index("incomplete(") < source.index("publish(") < source.index("record(")


# --- BI-01 -------------------------------------------------------------------------------------------------------------

def _historical(tmp_path, monkeypatch, window, edges, counts, total=8.0):
    from adroit.experiments import digitised, historical
    module = object.__new__(historical.HistoricalSearch)
    module.record = {"window_kev": list(window), "background_events": total,
                     "background_shape": {"digitised": "fixture", "counts": "counts"}}
    module.grid = np.linspace(window[0], window[1], 800)
    monkeypatch.setattr(digitised, "load", lambda name: {"edges_kev": list(edges), "counts": list(counts)})
    return module


@pytest.mark.parametrize("edges,counts", [([5, 15], [10]),                           # the window's own bin
                                          ([0, 5, 15, 20], [5, 10, 5]),              # wider than the window
                                          ([0, 7, 15, 20], [7, 16, 5]),              # not aligned with it
                                          ([0, 6, 10, 20], [3, 8, 4])])              # unequal widths
def test_a_digitised_and_an_inline_shape_put_the_record_s_count_in_the_window(tmp_path, monkeypatch, edges, counts):
    """The auditor's ``transformations``: the same bins inline and digitised. At the pin, with bins wider than the
    window, the digitised shape put 4 of the record's 8 events in it (and 5.24 with unequal widths)."""
    from adroit.experiments import historical
    module = _historical(tmp_path, monkeypatch, (5, 15), edges, counts)
    inline = historical.shape_on_grid(edges, counts, 8.0, (5, 15), module.grid)
    assert np.array_equal(module.background_on_grid(), inline)
    edges_a, counts_a = np.asarray(edges, float), np.asarray(counts, float)
    per_kev = counts_a / np.diff(edges_a)
    overlap = np.clip(np.minimum(edges_a[1:], 15) - np.maximum(edges_a[:-1], 5), 0, None)
    expected = 8.0 * per_kev / np.sum(per_kev * overlap)                   # the shape, its window integral 8
    assert np.sum(expected * overlap) == pytest.approx(8.0)
    at = np.minimum(module.grid, np.nextafter(15.0, 5.0))                   # the window's top, read within it
    index = np.clip(np.searchsorted(edges_a, at, side="right") - 1, 0, len(counts) - 1)
    assert np.allclose(inline, expected[index])
    assert np.trapezoid(inline, module.grid) == pytest.approx(8.0, rel=2e-3)        # the grid's smoothing of steps
    rescaled = historical.shape_on_grid(edges, 3 * counts_a, 8.0, (5, 15), module.grid)
    assert np.allclose(rescaled, inline)                                            # a shape, not a count


def test_the_auditor_s_record_fits_alike_inline_and_digitised(tmp_path, monkeypatch):
    """Ten events between 6 and 14 keV over a background of 8 in [5, 15] keV, the bins [0, 5, 15, 20] keV, and a
    uniform signal (0.1 per keV): the fitted signal is N − B = 2 through both (at the pin 2 inline, 6 digitised, with
    local significances of 0.68σ and 2.5σ)."""
    from adroit.experiments import historical
    from adroit.inference import signal_fit
    module = _historical(tmp_path, monkeypatch, (5, 15), [0, 5, 15, 20], [5, 10, 5])
    events = np.linspace(6, 14, 10)
    f = np.full(events.size, 0.1)
    fits = [signal_fit.fit("uniform", f, np.interp(events, module.grid, density))
            for density in (module.background_on_grid(),
                            historical.shape_on_grid([0, 5, 15, 20], [5, 10, 5], 8.0, (5, 15), module.grid))]
    assert [fit.s_hat for fit in fits] == pytest.approx([2.0, 2.0], abs=1e-6)
    assert fits[0].z_local == pytest.approx(fits[1].z_local) == pytest.approx(0.6803462547, rel=1e-6)


def test_two_record_files_with_the_same_bins_inline_and_digitised_give_one_background(tmp_path, monkeypatch):
    """Through the records' own modules (``record:`` files, ``anomaly.RecordSearch``): CDMS II Si's record with bins
    wider than its window (0–7–100–200 keV), once inline and once as a digitised table. Both are valid records
    (``anomaly.check``); their backgrounds on the grid are one, with the record's count in the window."""
    import yaml
    from adroit.experiments import anomaly, digitised, historical, registry
    real = digitised.load
    table = {"edges_kev": [0.0, 7.0, 100.0, 200.0], "counts": [5.0, 10.0, 5.0]}
    monkeypatch.setattr(digitised, "load", lambda name: table if name == "fixture_bins" else real(name))
    modules = []
    for name, shape in (("inline", {"points": {"edges_kev": table["edges_kev"], "counts": table["counts"]}}),
                        ("digitised", {"digitised": "fixture_bins", "counts": "counts"})):
        data = dict(historical.record("cdms_ii_si_2013"))
        efficiency = digitised.load(data["efficiency"]["digitised"])
        (tmp_path / f"{name}.csv").write_text("\n".join(f"{e},{x}" for e, x in zip(efficiency["recoil_energy_kev"],
                                                                                   efficiency["efficiency"])))
        data.update(efficiency={"csv": f"{name}.csv"}, verified_by="a person", background_shape=shape)
        (tmp_path / f"{name}.yaml").write_text(yaml.safe_dump(data))
        assert anomaly.check(anomaly.load(tmp_path / f"{name}.yaml"), tmp_path) == []
        modules.append(registry.load_module(f"record:{tmp_path / f'{name}.yaml'}"))
    inline, from_table = (m.background_on_grid() for m in modules)
    assert np.array_equal(inline, from_table)
    assert np.allclose(inline, 0.41 / 93.0)                                 # 0.41 events over 7–100 keV, flat
    assert modules[0].background_rate().total == modules[1].background_rate().total


def test_cdms_ii_si_s_background_is_spread_as_before_bit_for_bit():
    """CDMS II Si's three bins lie in its window: the shared rule gives its density as the pin's did, every value."""
    from adroit.experiments import digitised, registry
    module = registry.load_module("CDMS II Si (2013)")
    spec, total = module.record["background_shape"], module.record["background_events"]
    table = digitised.load(spec["digitised"])
    edges, counts = np.asarray(table["edges_kev"], float), np.asarray(table[spec["counts"]], float)
    pin = total * counts / counts.sum() / np.diff(edges)
    index = np.clip(np.searchsorted(edges, module.grid, side="right") - 1, 0, len(counts) - 1)
    assert np.array_equal(module.background_on_grid(), pin[index])


def test_a_shape_that_does_not_cover_the_window_is_refused():
    from adroit.experiments import historical
    with pytest.raises(ValueError, match="do not cover the window"):
        historical.shape_on_grid([6, 15], [1], 8.0, (5, 15), np.linspace(5, 15, 10))
    with pytest.raises(ValueError, match="puts nothing in the window"):
        historical.shape_on_grid([0, 5, 15], [1, 0], 8.0, (5, 15), np.linspace(5, 15, 10))


# --- BI-02 -------------------------------------------------------------------------------------------------------------

def _tools(tmp_path, monkeypatch):
    from adroit.constraints import lhc, production
    tools = tmp_path / "tools"
    monkeypatch.setattr(production, "get_settings", lambda: SimpleNamespace(tools_dir=tools))
    monkeypatch.setattr(lhc, "get_settings", lambda: SimpleNamespace(tools_dir=tools))
    (tools / "madgraph-xsec").mkdir(parents=True)
    (tools / "susy-xsec" / "tables").mkdir(parents=True)
    return tools


def _write_tables(tools: Path, factor: float, top: float, edition: int) -> None:
    from adroit.constraints import lhc
    masses = [100.0, 200.0, 300.0, top]
    (tools / "madgraph-xsec" / "fixture_vector.json").write_text(json.dumps(
        {"columns": ["mass_gev", "sigma_pb"], "data": [[m, factor * 2.0 * (200.0 / m) ** 2] for m in masses],
         "edition": edition}))
    (tools / "susy-xsec" / "tables" / f"{lhc.TABLES['slepton']}.json").write_text(json.dumps(
        {"data": [[m, factor * 2.0 * (200.0 / m) ** 2] for m in masses]}))


@pytest.mark.skipif("slepton" not in __import__("adroit.constraints.lhc", fromlist=["TABLES"]).TABLES,
                    reason="no slepton table named")
def test_a_production_table_replaced_in_a_warm_process_is_read_again(tmp_path, monkeypatch):
    """The auditor's ``cache_inputs``: the tables read, then replaced (σ tripled, the top mass 400 → 500 GeV, a new
    edition). At the pin the warm process kept 2 pb, 400 GeV and edition 1 while a fresh one read 6 pb, 500 GeV and 3."""
    from adroit.constraints import lhc, production
    tools = _tools(tmp_path, monkeypatch)
    _write_tables(tools, 1.0, 400.0, 1)
    assert production.sigma_pb("fixture_vector", 200.0) == pytest.approx(2.0)
    assert production.mass_range("fixture_vector") == (100.0, 400.0)
    assert lhc.cross_section_pb("slepton", 200.0) == pytest.approx(2.0) and lhc.table_range("slepton")[1] == 400.0
    _write_tables(tools, 3.0, 500.0, 3)
    assert production.sigma_pb("fixture_vector", 200.0) == pytest.approx(6.0)
    assert production.sigma_pb_grid("fixture_vector", np.array([200.0]))[0] == pytest.approx(6.0)
    assert production.mass_range("fixture_vector") == (100.0, 500.0)
    assert production.describe("fixture_vector")["edition"] == 3
    assert lhc.cross_section_pb("slepton", 200.0) == pytest.approx(6.0) and lhc.table_range("slepton")[1] == 500.0


def test_a_stable_table_stays_cached_and_another_tools_folder_is_its_own(tmp_path, monkeypatch):
    from adroit.constraints import production
    tools = _tools(tmp_path, monkeypatch)
    _write_tables(tools, 1.0, 400.0, 1)
    production._read.cache_clear()
    production.sigma_pb("fixture_vector", 200.0)
    production.sigma_pb("fixture_vector", 250.0)
    assert production._read.cache_info().misses == 1                       # one reading of an unchanged table
    other = tmp_path / "other"
    (other / "madgraph-xsec").mkdir(parents=True)
    (other / "susy-xsec" / "tables").mkdir(parents=True)
    _write_tables(other, 5.0, 400.0, 2)
    monkeypatch.setattr(production, "get_settings", lambda: SimpleNamespace(tools_dir=other))
    assert production.sigma_pb("fixture_vector", 200.0) == pytest.approx(10.0)      # the same name, another table


def test_one_call_reads_one_version_of_its_table(tmp_path, monkeypatch):
    """A table replaced once a call has read it: the call's range and spline are of the values it read (one reading,
    ``production.table``; DY-02 since, which ``tests/orchestrator/test_dy_fixes.py`` tests with the cache evicted)."""
    from adroit.constraints import production
    tools = _tools(tmp_path, monkeypatch)
    _write_tables(tools, 1.0, 400.0, 1)
    real = production._read

    def replaced_after(path, version, column):
        out = real(path, version, column)
        _write_tables(tools, 3.0, 400.0, 3)          # replaced once the values are read
        return out
    monkeypatch.setattr(production, "_read", replaced_after)
    assert production.sigma_pb("fixture_vector", 250.0) == pytest.approx(2.0 * (200.0 / 250.0) ** 2, rel=1e-3)


# --- BI-02: every reader of a tools file, by what the file is ------------------------------------------------------

def _rewritten(path: Path) -> None:
    """The same bytes written again: a write a cache kept by the file's name had not seen."""
    path.write_bytes(path.read_bytes())


def test_slatyer_s_f_eff_table_replaced_is_read_again(tmp_path, monkeypatch):
    from adroit.constraints import searches
    folder = tmp_path / "feff"
    folder.mkdir()
    table = folder / "feff_3keV.dat"
    table.write_text("logE f_e f_gamma\n1 0.1 0.2\n2 0.3 0.4\n")
    monkeypatch.setattr(searches, "_tool", lambda name: folder)
    assert searches._injection_table()[1].tolist() == [0.1, 0.3]
    table.write_text("logE f_e f_gamma\n1 0.5 0.2\n2 0.6 0.4\n")
    assert searches._injection_table()[1].tolist() == [0.5, 0.6]


def test_the_pdg_s_r_ratio_replaced_is_read_again(tmp_path, monkeypatch):
    from adroit.constraints import hadrons, searches
    folder = tmp_path / "pdg"
    folder.mkdir()
    table = folder / "rpp2022-hadronicrpp_page1001.dat"
    table.write_text("* the PDG's compilation\n1.0 0 0 2.0 EXCLSUM\n2.0 0 0 3.0 EXCLSUM\n")
    monkeypatch.setattr(searches, "_tool", lambda name: folder)
    assert hadrons._pdg_table()[1].tolist() == [2.0, 3.0]
    table.write_text("* the PDG's compilation\n1.0 0 0 4.0 EXCLSUM\n2.0 0 0 5.0 EXCLSUM\n")
    assert hadrons._pdg_table()[1].tolist() == [4.0, 5.0]


def test_the_resummed_lines_rebuilt_are_read_again(tmp_path, monkeypatch):
    from adroit.constraints import resummed_lines
    monkeypatch.setattr(resummed_lines, "get_settings", lambda: SimpleNamespace(tools_dir=tmp_path))
    (tmp_path / "dmyspec").mkdir()
    resummed_lines.path().write_text(json.dumps({"tables": {"wino": [1]}}))
    assert resummed_lines._tables() == {"wino": [1]}
    resummed_lines.path().write_text(json.dumps({"tables": {"wino": [2]}}))
    assert resummed_lines._tables() == {"wino": [2]}


@pytest.mark.needs("solar_model")
def test_the_solar_model_replaced_is_read_again_and_an_unchanged_one_is_not(tmp_path, monkeypatch):
    import shutil as copying
    from adroit.constraints import capture
    real = capture.fetch.locate(capture.SOLAR_MODEL)
    folder = tmp_path / "solar"
    copying.copytree(real, folder)
    monkeypatch.setattr(capture.fetch, "locate", lambda item: folder)
    reads, read = [], capture._read_b16
    monkeypatch.setattr(capture, "_read_b16", lambda path: reads.append(path) or read(path))
    capture.solar_model.cache_clear()
    first = capture.solar_model()
    assert capture.solar_model() is first and len(reads) == 1
    _rewritten(folder / capture.SOLAR_FILE)
    capture.solar_model()
    assert len(reads) == 2
    capture.solar_model.cache_clear()


def test_the_lz_window_s_background_density_follows_its_record_s_files(tmp_path, monkeypatch):
    from functools import lru_cache
    from adroit.experiments import lz_extended_window as lz
    folder = tmp_path / "lz"
    folder.mkdir()
    (folder / "L10s.yaml").write_text("a: 1\n")
    computed = []
    monkeypatch.setattr(lz, "data_folder", lambda item: folder)
    monkeypatch.setattr(lz, "_background_density", lru_cache(maxsize=2)(lambda files: computed.append(files) or 1.0))
    lz.background_density()
    lz.background_density()
    assert len(computed) == 1
    _rewritten(folder / "L10s.yaml")
    lz.background_density()
    assert len(computed) == 2
