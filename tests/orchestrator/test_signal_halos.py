"""Signal best fits comparing the halo models (the owner, 2026-11-18, the signal best fits plan, phase B): the
whole run at each available benchmark, every candidate at every halo ranked together, the global significance over
every candidate at every halo, and the first halo's run as the study. Offline: the toy searches of halo phase 1."""
from __future__ import annotations

import pytest
import typer

from adroit.core import halo_choice
from adroit.orchestrator import signal
from adroit.ui import forms
from tests.orchestrator.test_halo_phase1 import _request, toys  # noqa: F401  (the fixture)


def _compared() -> signal.SignalResult:
    halos = [halo_choice.fixed("shm"), halo_choice.fixed("shm-plus-plus")]
    return signal.run(_request().model_copy(update={"halos": halos, "halo": halos[0]}))


def test_every_halo_is_run_and_ranked_together(toys):  # noqa: F811
    result = _compared()
    scan = result.halo_scan
    assert [r.label for r in scan.runs] == ["SHM", "SHM++"] and scan.shapes == 2
    assert result.request.halo == halo_choice.fixed("shm") and len(result.request.halos) == 2
    assert {h.model_dump_json() for h in toys["signal"]} >= {halo_choice.fixed("shm").halo.model_dump_json(),
                                                             halo_choice.fixed("shm-plus-plus").halo.model_dump_json()}
    labels = [e.label for e in scan.ranking.ranking]
    assert "O1s@20 [SHM]" in labels and "O1s@20 [SHM++]" in labels
    assert scan.max_local_z == max(r.max_local_z for r in scan.runs)
    assert "over every candidate at each halo model (SHM, SHM++: 2 signal shapes)" in scan.global_method
    assert result.halo_resolution.label == scan.runs[0].resolution.label != scan.runs[1].resolution.label


def test_the_report_and_the_page_say_what_was_searched_and_the_halos_compared(toys):  # noqa: F811
    from adroit.ui.pages import global_significance
    result = _compared()
    text = signal.report(result)
    assert "## What was searched" in text and "ranked by AIC" in text and "## Halo models compared" in text
    assert "Global significance over every candidate at every halo" in text
    assert global_significance(result).startswith("Global significance over every candidate at every halo model "
                                                  "compared (SHM, SHM++)")
    assert "**Global significance over every candidate at every halo model compared (SHM, SHM++)" in text
    single = signal.run(_request(halo_choice.fixed()))
    assert single.halo_scan is None and "## Halo models compared" not in signal.report(single)
    assert "halos" not in single.request.model_dump(mode="json")          # an unset request keeps its identity


def test_a_comparison_needs_two_families_and_fixes_no_other_halo(toys):  # noqa: F811
    shm = halo_choice.fixed("shm")
    with pytest.raises(ValueError, match="two halo models"):
        signal.run(_request().model_copy(update={"halos": [shm, shm]}))
    with pytest.raises(ValueError, match="fixes no other halo"):
        signal.run(_request().model_copy(update={"halos": [shm, halo_choice.fixed("shm-plus-plus")],
                                                 "halo": halo_choice.fixed("shm-plus-plus")}))


def test_the_page_and_the_command_line_offer_the_comparison():
    from adroit.orchestrator.cli import _track2_halos
    assert forms.halo_flags("track2", "compare") == ["--halo", "compare"]
    with pytest.raises(ValueError, match="every available family"):
        forms.halo_flags("track2", "compare", "shm-plus-plus")
    chosen = _track2_halos("compare")["halos"]
    assert [h.family for h in chosen] == ["shm", "shm-plus-plus"]                 # the SHM's run first
    assert _track2_halos("benchmark", "shm-plus-plus")["halo"].family == "shm-plus-plus"
    with pytest.raises(typer.BadParameter):
        _track2_halos("compare", "shm-plus-plus")
    resolution, why = forms.halo_preview("track2", "compare")
    assert resolution is not None and not why
