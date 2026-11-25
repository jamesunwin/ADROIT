"""The auditor's input-boundary and portability audits, repaired (the independent audit of 2026-11-10 (input boundaries),
The independent audit of 2026-11-10 (portability publication); the IB/IC repair record of 2026-11-12):

- IB-01: an anomaly record's numbers are checked where they are calculated with: a record ``anomaly check`` passes is
  one a run accepts, and one it refuses is never fitted (negative, infinite and not-a-number values).
- IB-02: a digitiser's CSV is read as written: a step kept, a malformed row named by its line, never skipped.
- IB-03: a unit conversion keeps an assumed value assumed, with its acknowledgement required.
- IC-01: a publication stopped between its parts leaves its folder marked, and its report and study record read as
  interrupted, never as its result's: not shown, counted, listed or exported as the result's.

Offline: real anomaly records and recoil rates (Si, O1); the provider a ``FakeLLMClient`` ($0); write failures injected
at the publisher's writer (``durable.write_atomic``)."""
from __future__ import annotations

import errno
import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from adroit.agents.llm import FakeLLMClient
from adroit.core import durable
from adroit.core.dm_state import DarkMatterParticle
from adroit.evidence import archive, build, runtime, version
from adroit.experiments import anomaly
from adroit.library.interactions import registry as cards
from adroit.orchestrator import cli, ideas, runs, signal, study_headline
from adroit.ui import pages


def _record(**change) -> dict:
    """A small Si search with three events, an inline efficiency and a background with its uncertainty."""
    data = {"name": "A test search", "target": "Si", "references": ["arXiv:0000.00000"], "exposure_kg_day": 140.0,
            "window_kev": [7.0, 100.0], "events_kev": [8.2, 9.5, 12.3], "resolution_kev": 0.5,
            "background_events": 0.41, "background_uncertainty": {"plus": [0.2], "minus": [0.1]},
            "efficiency": {"points": {"recoil_energy_kev": [7.0, 20.0, 100.0], "efficiency": [0.3, 0.5, 0.5]}}}
    data.update(change)
    return data


def _written(folder: Path, data: dict, name: str = "search.yaml") -> Path:
    path = folder / name
    path.write_text(yaml.safe_dump(data))
    return path


def _request(path: Path) -> signal.SignalRequest:
    return signal.SignalRequest(experiment=f"record:{path}", null_modules=[], toys=2, leaders=1, workers=1,
                                complementary=False, unverified_records=True,
                                candidates=[signal.Candidate(label="O1s@20", card_id="O1", isospin="s",
                                                             mass_gev=20.0)])


# --- IB-01: what the checker passes, a run accepts; what it refuses is never fitted -------------------------------------

MALFORMED = {
    "a negative upward uncertainty": {"background_uncertainty": {"plus": [-0.2], "minus": [0.1]}},
    "an infinite upward uncertainty": {"background_uncertainty": {"plus": [float("inf")], "minus": [0.1]}},
    "a not-a-number upward uncertainty": {"background_uncertainty": {"plus": [float("nan")], "minus": [0.1]}},
    "a negative downward uncertainty": {"background_uncertainty": {"plus": [0.2], "minus": [-0.1]}},
    "an infinite exposure": {"exposure_kg_day": float("inf")},
    "an infinite background": {"background_events": float("inf")},
    "a not-a-number event": {"events_kev": [8.2, float("nan")]},
    "an infinite efficiency energy": {"efficiency": {"points": {"recoil_energy_kev": [7.0, 20.0, float("inf")],
                                                                "efficiency": [0.3, 0.5, 0.5]}}},
    "a not-a-number efficiency": {"efficiency": {"points": {"recoil_energy_kev": [7.0, 20.0, 100.0],
                                                            "efficiency": [0.3, float("nan"), 0.5]}}},
    "a not-a-number background bin": {"background_shape": {"points": {"edges_kev": [0.0, 50.0, 200.0],
                                                                      "counts": [3.0, float("nan")]}}},
    "an infinite halo speed": {"halo": {"v0_km_s": float("inf")}},
}


@pytest.mark.parametrize("case", list(MALFORMED))
def test_a_malformed_record_is_refused_by_the_checker_and_by_every_calculation(case, tmp_path):
    path = _written(tmp_path, _record(**MALFORMED[case]))
    record, problems = anomaly.read(path)
    assert problems or anomaly.check(record, tmp_path)                       # the checker says so
    with pytest.raises(ValueError):                                          # and the adapter every run builds refuses
        anomaly.RecordSearch.from_name(f"record:{path}")


@pytest.mark.parametrize("case", ["a negative upward uncertainty", "an infinite upward uncertainty"])
def test_the_auditors_records_are_refused_by_the_command_and_never_fitted(case, tmp_path, monkeypatch):
    """At ``5eb3b37``: the negative one was fitted as its absolute value (the checker refused it), the infinite one
    fitted and reported as "+inf%" (the checker passed it)."""
    path = _written(tmp_path, _record(**MALFORMED[case]))
    checked = CliRunner().invoke(cli.app, ["anomaly", "check", str(path)])
    assert checked.exit_code == 1 and re.search(r"background.uncertainty", checked.output)
    fitted = []
    monkeypatch.setattr(signal, "_fit_all", lambda *a, **k: fitted.append(a))
    with pytest.raises(ValueError, match="cannot be calculated with: background_uncertainty|cannot be calculated "
                                         "with: background uncertainty"):
        signal.run(_request(path))
    assert fitted == []


def test_a_valid_record_is_fitted_as_before(tmp_path):
    path = _written(tmp_path, _record())
    record, problems = anomaly.read(path)
    assert not problems and not anomaly.numerical_problems(record, record.efficiency.points)
    result = signal.run(_request(path))
    assert result.fits and result.fits[0].label == "O1s@20"


# --- IB-02: a digitiser's CSV is read as written ----------------------------------------------------------------------

STEP = {"recoil_energy_kev": [5.0, 20.0, 20.0, 50.0], "efficiency": [0.0, 0.0, 1.0, 1.0]}


def _events(folder: Path, efficiency: dict) -> float:
    data = _record(window_kev=[5.0, 50.0], efficiency=efficiency)
    module = anomaly.RecordSearch(anomaly.AnomalyRecord.model_validate(data), folder)
    particle = DarkMatterParticle(mass_gev=20.0)
    interaction = cards.resolve("O1", particle, {"c_p": 1e-8, "c_n": 1e-8})
    conventions = module.conventions()
    return module.expected_signal(particle, interaction, conventions.halo, conventions.nuclear_model).total_events


@pytest.mark.parametrize("csv", ["energy_keV,efficiency\n5,0\n20,0\n20,1\n50,1\n",       # the auditor's step
                                 "5,0\n20,0\n20,1\n50,1\n",                               # no header
                                 "energy,eff\n20,0\n5,0\n20,1\n50,1\n50,1\n\n",           # unsorted, a repeat, a gap
                                 "5\t0\n20\t0\n20\t1\n50\t1\n"])                          # tab-separated
def test_a_csv_step_reads_and_calculates_as_its_inline_twin(csv, tmp_path):
    """At ``5eb3b37`` the CSV lost the step's left side: 2,918.9 events against the inline step's 957.4."""
    (tmp_path / "eff.csv").write_text(csv)
    assert anomaly.read_curve(tmp_path / "eff.csv").model_dump() == STEP
    assert _events(tmp_path, {"csv": "eff.csv"}) == _events(tmp_path, {"points": STEP})


def test_a_step_at_the_windows_edge_is_kept(tmp_path):
    (tmp_path / "eff.csv").write_text("5,0\n5,1\n50,1\n")
    assert anomaly.read_curve(tmp_path / "eff.csv").model_dump() == {"recoil_energy_kev": [5.0, 5.0, 50.0],
                                                                     "efficiency": [0.0, 1.0, 1.0]}


@pytest.mark.parametrize("csv,line", [("5,0\n20,broken\n50,1\n", 2),                   # the auditor's row
                                      ("energy,eff\n5,0\n20,broken\n50,1\n", 3),
                                      ("5,0\n20\n50,1\n", 2),                            # a missing column
                                      ("5,0\n20,0.5,1\n50,1\n", 2),                      # an extra one
                                      ("5,0\n,0.5\n50,1\n", 2)])                         # an empty one
def test_a_malformed_csv_row_is_named_and_nothing_is_calculated(csv, line, tmp_path):
    (tmp_path / "eff.csv").write_text(csv)
    with pytest.raises(ValueError, match=f"eff.csv, line {line}:"):
        anomaly.read_curve(tmp_path / "eff.csv")
    path = _written(tmp_path, _record(window_kev=[5.0, 50.0], efficiency={"csv": "eff.csv"}))
    record, _ = anomaly.read(path)
    assert any(f"line {line}" in p for p in anomaly.check(record, tmp_path))
    with pytest.raises(ValueError, match=f"line {line}"):
        anomaly.RecordSearch.from_name(f"record:{path}")


# --- IB-03: a conversion keeps an assumption an assumption ------------------------------------------------------------

def _converted(tmp_path, case: str) -> dict:
    """The auditor's control: an exposure through the real extraction step (the provider simulated), its saved dossier, its
    interpretation and the acknowledgements a confirmation needs."""
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.orchestrator.anomaly_intake import acknowledgements, interpretation
    from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
    from tests.experimental_extraction_fixtures import TEXT, answer
    folder = tmp_path / case
    folder.mkdir()
    source = folder / "source.txt"
    source.write_text(TEXT + "\nExposure alternative: 1 tonne day.\n")
    catalog = ExperimentalCatalog(folder / "library")
    revision = catalog.import_files([source], "Synthetic conversion")
    service = ExperimentalExtraction(catalog)
    session = service.start(revision.reference, 1.0, vision=False)
    reply = answer(revision.sources[0].sha256, text=source.read_text())
    claim = next(c for c in reply.results[0].claims if c.key == "exposure")
    claim.value, claim.units, claim.requested_unit = 1.0, "tonne day", "kg day"
    if case != "sourced":
        claim.status, claim.value = "assumed", 7.3
        claim.note = "Explicit investigator assumption; not established by source."
    if case == "assumed, no locator":
        claim.sources = []
    if case == "assumed, canonical":
        claim.value, claim.units, claim.requested_unit = 7300.0, "kg day", ""
    step = service.step(session.session_id, llm=FakeLLMClient([reply]))
    saved = catalog.load(step.output_revision)
    found = next(c for c in saved.dossier.results[0].claims if c.key == "exposure")
    return {"claim": found, "assumptions": interpretation(saved.reference, "signal", catalog).assumptions,
            "acknowledgements": acknowledgements(saved.reference, "signal", catalog)}


@pytest.mark.parametrize("case", ["assumed, no locator", "assumed, with a locator", "assumed, canonical"])
def test_an_assumed_value_needs_its_acceptance_in_any_units(case, tmp_path):
    """At ``5eb3b37`` the two converted assumptions became "converted": one lost its acknowledgement, the other failed
    publication (an extracted value needs sources)."""
    found = _converted(tmp_path, case)
    assert found["claim"].status == "assumed" and found["claim"].value == 7300.0 and found["claim"].units == "kg day"
    assert "exposure" in found["assumptions"] and "exposure=7300.0 kg day" in found["acknowledgements"]
    if case != "assumed, canonical":
        assert "Deterministic conversion from 7.3 tonne day" in found["claim"].note


def test_a_sourced_value_is_converted_as_before(tmp_path):
    found = _converted(tmp_path, "sourced")
    assert found["claim"].status == "converted" and found["claim"].value == 1000.0
    assert "exposure" not in found["assumptions"]


# --- IC-01: a publication stopped between its parts reads as interrupted ----------------------------------------------

def _published(folder: Path, stage: str):
    """The auditor's control: an undated idea published as A (8 November, $0.08), then the same bytes as B (9 November,
    $0.09), B's write of ``stage`` failing (ENOSPC); "none": B whole."""
    result = ideas.IdeaResult(request=ideas.IdeaRequest(text="Offline synthetic saved idea"),
                              dropped=["No model proposed in this deterministic fixture"])
    context = runtime.capture_request(result.request, experiments=False)

    def dated(day: int):
        return context.model_copy(update={"calculation_started_at": f"2026-11-{day:02d}T10:00:00Z",
                                          "calculation_completed_at": f"2026-11-{day:02d}T10:01:00Z"})
    folder.mkdir(parents=True)
    runs._write(folder, result, "# First report\n", "idea", "First publication", cost_usd=0.08,
                evidence_context=dated(8))
    assert not (folder / build.MARK).exists()
    real = durable.write_atomic

    def failing(path, data, **kwargs):
        if Path(path).name == stage:
            raise OSError(errno.ENOSPC, "simulated ENOSPC", str(path))
        return real(path, data, **kwargs)
    with patch.object(durable, "write_atomic", failing):
        if stage == "none":
            runs._write(folder, result, "# Second report\n", "idea", "Second publication", cost_usd=0.09,
                        evidence_context=dated(9))
        else:
            with pytest.raises(OSError, match="ENOSPC"):
                runs._write(folder, result, "# Second report\n", "idea", "Second publication", cost_usd=0.09,
                            evidence_context=dated(9))
    return version.resolve(folder, presentation=True)


@pytest.mark.parametrize("stage", ["report.md", "study.json"])
def test_a_publication_stopped_between_its_parts_reads_as_interrupted_everywhere(stage, tmp_path):
    """At ``5eb3b37`` both read as bound: A's report or record beside B's evidence, A's $0.08 counted, the bundle
    verifying with no warning."""
    held = _published(tmp_path / stage, stage)
    assert held.interrupted and (tmp_path / stage / build.MARK).exists()
    assert held.record_state == "interrupted" and held.report().state == "interrupted"
    assert held.saved().envelope.context.calculation_started_at.startswith("2026-11-09")    # B's evidence, kept
    assert held.record_state not in study_headline.SHOWN                    # the list and the command: not counted
    assert "interrupted" in study_headline.listed(held)
    assert "0.08" not in pages.study_cost(held) + pages.list_cost(held)     # nor its cost, wherever it is read
    bundle = tmp_path / f"{stage}.zip"
    archive.export_run(held, bundle)
    manifest, files = archive.read_bundle(bundle)
    assert not [name for name in files if name.endswith(("study.json", "report.md"))]
    assert any("interrupted" in w and "study.json" in w for w in manifest.warnings)
    assert any("interrupted" in w and "report.md" in w for w in manifest.warnings)
    assert archive.verify_bundle(bundle).valid


def test_the_command_lists_an_interrupted_study_without_its_date_or_cost(tmp_path):
    _published(tmp_path / "runs" / "study", "study.json")
    listed = CliRunner().invoke(cli.app, ["studies", str(tmp_path / "runs")])
    assert "its last publication was interrupted" in listed.output and "0.08" not in listed.output


def test_a_publication_written_whole_is_bound_and_unmarked(tmp_path):
    held = _published(tmp_path / "whole", "none")
    assert not held.interrupted and not (tmp_path / "whole" / build.MARK).exists()
    assert held.record_state == "bound" and held.report().state == "bound"
    assert held.study().title == "Second publication" and pages.study_cost(held) == "cost $0.0900 settled"


def test_a_publication_refused_before_its_first_part_leaves_no_mark(tmp_path):
    folder = tmp_path / "refused"
    folder.mkdir()

    def refused(digest):
        raise ValueError("refused before anything is written")
    with pytest.raises(ValueError, match="refused before"):
        runs._write(folder, ideas.IdeaResult(request=ideas.IdeaRequest(text="x")), "# r\n", "idea", "t",
                    certify=refused)
    assert not (folder / build.MARK).exists() and not (folder / "result.json").exists()


def test_the_mark_is_written_before_the_first_part_and_removed_after_the_last(tmp_path):
    order = []
    real = durable.write_atomic

    def recorded(path, data, **kwargs):
        order.append((Path(path).name, (Path(path).parent / build.MARK).exists()))
        return real(path, data, **kwargs)
    folder = tmp_path / "ordered"
    folder.mkdir()
    with patch.object(durable, "write_atomic", recorded):
        runs._write(folder, ideas.IdeaResult(request=ideas.IdeaRequest(text="x")), "# r\n", "idea", "t")
    parts = [(name, marked) for name, marked in order if name != build.MARK]
    assert order[0][0] == build.MARK and parts and all(marked for _, marked in parts)
    assert [name for name, _ in parts][-1] == "study.json" and not (folder / build.MARK).exists()


def test_the_mark_is_read_with_the_other_parts(tmp_path):
    """The mark is one of the files a version reads together (one appearing while it is read makes it read again): a
    version holds what was there when it was read, never the folder read later."""
    held = _published(tmp_path / "read", "none")
    (tmp_path / "read" / build.MARK).write_text("interrupted\n")
    assert not held.interrupted and version.resolve(tmp_path / "read", presentation=True).interrupted
    assert json.loads(held.record_bytes)["title"] == "Second publication"


def test_a_publication_stopped_by_a_part_replaced_from_outside_keeps_its_mark(tmp_path):
    """Stopped because a part it wrote was replaced from outside ADROIT's writers (``Replaced``, DE-02), a publication
    keeps its mark, as any other stop does: the parts there are not one publication (the auditor's merge-round audit, HE-01,
    2026-11-12: this test had required the mark removed). A later publication written whole removes it."""
    folder = tmp_path / "replaced"
    folder.mkdir()
    result = ideas.IdeaResult(request=ideas.IdeaRequest(text="x"))
    other = ideas.IdeaResult(request=ideas.IdeaRequest(text="another writer's"))
    real = build.kept_parts

    def replaced(path, content, wrote, *args, **kwargs):
        if wrote == ("result",):
            durable.write_atomic(path, other.model_dump_json(indent=1).encode())     # another writer, meanwhile
        return real(path, content, wrote, *args, **kwargs)
    with patch.object(build, "kept_parts", replaced), pytest.raises(build.Replaced):
        runs._write(folder, result, "# r\n", "idea", "t")
    assert (folder / build.MARK).exists() and version.resolve(folder, presentation=True).interrupted
    runs._write(folder, result, "# r\n", "idea", "t")
    assert not (folder / build.MARK).exists() and not version.resolve(folder, presentation=True).interrupted


def test_the_classic_page_withholds_an_interrupted_report(tmp_path):
    from adroit.workbench.server import report_view
    _published(tmp_path / "classic", "study.json")
    report, images, note, embedded, _ = report_view(tmp_path / "classic")
    assert report is None and not images and not embedded and "interrupted" in note
