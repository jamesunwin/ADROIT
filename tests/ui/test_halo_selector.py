"""The one halo component in the workbench (``adroit.ui.halo``; halo phases 1 and 2): offered wherever a model is defined
or chosen for a calculation, the SHM by default, SHM++ as a fixed benchmark only, the planned family listed but disabled,
the treatment each track has, the resolution shown before launch, and the command it launches agreeing with the choice.
Offline."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from nicegui.testing import User
from typer.testing import CliRunner

from adroit.orchestrator import cli
from adroit.ui import forms
from adroit.ui.app import build_pages
from tests.ui.test_model_approval import launches, workspace


def test_the_command_options_follow_the_choice_and_refuse_what_cannot_launch():
    assert forms.halo_flags("track1") == [] and forms.halo_flags("track1", "preset") == ["--halo", "preset"]
    assert forms.halo_flags("track1", "benchmark") == ["--halo", "benchmark"]
    assert forms.halo_flags("track1", "benchmark", "shm") == ["--halo", "benchmark"]
    assert forms.halo_flags("track2", "benchmark") == ["--halo", "benchmark"] and forms.halo_flags("track2") == []
    with pytest.raises(ValueError, match="here, not 'preset'"):
        forms.halo_flags("track2", "preset")                       # Track 2 has no region
    with pytest.raises(ValueError, match="not implemented yet"):
        forms.halo_flags("track1", "benchmark", "shm-lmc")
    with pytest.raises(ValueError, match="not implemented yet"):
        forms.advanced_options({"halo": "benchmark", "halo_family": "shm-lmc"})
    for track in ("track1", "single_idea", "track2"):                # SHM++: a fixed benchmark, in every track
        assert forms.halo_flags(track, "benchmark", "shm-plus-plus") == ["--halo", "benchmark", "--halo-family",
                                                                         "shm-plus-plus"]
    for treatment in ("", "preset", "published"):                    # never the SHM's region or the published halos
        with pytest.raises(ValueError, match="SHM\\+\\+ family applies to a fixed benchmark only"):
            forms.halo_flags("track1", treatment, "shm-plus-plus")
    resolution, why = forms.halo_preview("track1", "benchmark")
    assert why == "" and resolution.treatment.value == "benchmark"
    assert forms.halo_preview("track1")[0].treatment.value == "published"     # the tests' setting: published
    assert forms.halo_preview("track2")[0].summary.startswith("Each experiment's own published halo")
    assert forms.halo_preview("track1", "benchmark", "shm-lmc") == (None, forms.halo_preview(
        "track1", "benchmark", "shm-lmc")[1]) and "SHM + LMC" in forms.halo_preview("track1", "benchmark", "shm-lmc")[1]


@pytest.mark.parametrize("command", [
    forms.track1_command(Path("m.yaml"), Path("out"), halo="benchmark", halo_family="shm"),
    forms.portal_command("higgs_portal_scalar", Path("out"), halo="published"),
    forms.signal_command("CDMS II Si (2013)", Path("out"), halo="benchmark"),
    forms.single_idea_command(Path("m.yaml"), "LZ", Path("out"), advanced={"halo": "benchmark"})])
def test_each_command_with_a_halo_is_one_the_command_line_accepts(command):
    result = CliRunner().invoke(cli.app, [command[0], "--help"])
    assert result.exit_code == 0
    for option in [a for a in command if a.startswith("--")] + ["--halo-family"]:
        assert option in result.output, option


def test_the_command_line_reads_the_benchmark_and_refuses_a_planned_family():
    import typer
    from adroit.core import halo_choice
    assert cli._halo_option("benchmark") == halo_choice.fixed()
    assert cli._track2_halo("published") is None and cli._track2_halo("benchmark") == halo_choice.fixed()
    with pytest.raises(typer.BadParameter, match="Track 2 has no halo region"):
        cli._track2_halo("preset")
    with pytest.raises(typer.BadParameter, match="SHM \\+ LMC \\(shm-lmc\\) is not implemented yet"):
        cli._halo_option("benchmark", "shm-lmc")
    assert cli._halo_option("benchmark", "shm-plus-plus") == halo_choice.fixed("shm-plus-plus")
    assert cli._track2_halo("benchmark", "shm-plus-plus") == halo_choice.fixed("shm-plus-plus")
    with pytest.raises(typer.BadParameter, match="applies to --halo benchmark"):
        cli._halo_option("preset", "shm-plus-plus")
    assert "halo_family" in cli._TRACK1_SETTINGS                     # a resume keeps its saved halo


def _select(user: User, marker: str):
    return user.find(marker=marker).elements.pop()


async def test_explain_a_signal_offers_the_families_and_launches_the_benchmark(user: User, tmp_path, monkeypatch):
    root, folder, spec = workspace(tmp_path)
    calls = launches(monkeypatch)
    build_pages(root)
    await user.open("/new/single")
    user.find("the model (YAML, with coupling values)").elements.pop().value = yaml.safe_dump(spec.model_dump(mode="json"))
    family = _select(user, "halo-family")
    assert family.value == "shm" and list(family.options) == ["shm", "shm-plus-plus", "shm-lmc"]
    disabled = {o["label"].split(" (")[0]: o.get("disable", False) for o in family.props["options"]}
    assert disabled == {"SHM": False, "SHM++": False, "SHM + LMC": True}
    assert all("not available: not implemented yet" in o["label"] for o in family.props["options"] if o.get("disable"))
    await user.should_see("Published halos")                                # the tests' setting, resolved now
    _select(user, "halo-treatment").value = "benchmark"
    await user.should_see("a fixed common benchmark")
    await user.should_see("Halo uncertainty not propagated")
    user.find("Run the study").click()
    await user.should_see("Run:")
    command = calls[0][0]
    assert command[command.index("--halo") + 1] == "benchmark" and "--halo-family" not in command


async def test_a_planned_family_set_behind_the_form_is_refused_not_launched(user: User, tmp_path, monkeypatch):
    root, folder, spec = workspace(tmp_path)
    calls = launches(monkeypatch)
    build_pages(root)
    await user.open("/new/single")
    user.find("the model (YAML, with coupling values)").elements.pop().value = yaml.safe_dump(spec.model_dump(mode="json"))
    _select(user, "halo-treatment").value = "benchmark"
    _select(user, "halo-family").value = "shm-lmc"                 # disabled in the page; forced here
    await user.should_see("Cannot launch: SHM + LMC (shm-lmc) is not implemented yet")
    user.find("Run the study").click()
    await user.should_see("not implemented yet")
    assert calls == []


async def test_track2_offers_the_published_halos_or_the_benchmark(user: User, tmp_path, monkeypatch):
    calls = launches(monkeypatch)
    build_pages(tmp_path / "runs")
    await user.open("/new/track2")
    treatment = _select(user, "halo-treatment")
    assert list(treatment.options) == ["", "benchmark", "compare"] and treatment.value == ""   # compare: phase B
    await user.should_see("signal search's for its fit")
    treatment.value = "benchmark"
    user.find("Fit, combine and rank").click()
    await user.should_see("Run:")
    command = calls[0][0]
    assert command[0] == "signal" and command[command.index("--halo") + 1] == "benchmark"


async def test_the_portal_and_the_typed_model_take_the_halo_chosen_beside_them(user: User, tmp_path, monkeypatch):
    calls = launches(monkeypatch)
    build_pages(tmp_path / "runs")
    await user.open("/new/track1")
    _select(user, "portal-halo-treatment").value = "published"
    user.find("Scan the portal").click()
    await user.should_see("Run:")
    command = calls[0][0]
    assert command[:2] == ["track1", "--portal"] and command[command.index("--halo") + 1] == "published"


async def test_choosing_shm_plus_plus_takes_its_fixed_benchmark_and_launches_it(user: User, tmp_path, monkeypatch):
    root, folder, spec = workspace(tmp_path)
    calls = launches(monkeypatch)
    build_pages(root)
    await user.open("/new/single")
    user.find("the model (YAML, with coupling values)").elements.pop().value = yaml.safe_dump(spec.model_dump(mode="json"))
    family, treatment = _select(user, "halo-family"), _select(user, "halo-treatment")
    family.value = "shm-plus-plus"
    assert treatment.value == "benchmark" and list(treatment.options) == ["benchmark"]   # never the SHM's region
    family.value = "shm"                       # back to the SHM: its treatments again, the benchmark kept (no region)
    assert treatment.value == "benchmark" and list(treatment.options) == list(forms.HALO_TRACKS["single_idea"])
    family.value = "shm-plus-plus"
    await user.should_see("SHM++, fixed benchmark; halo uncertainty not propagated")
    details = _select(user, "halo-details-text").content
    assert "β = 0.9 and share η = 0.2" in details and "1601 speeds, 64 × 64 angular nodes" in details
    assert "no accepted-count ratio" in details
    user.find("Run the study").click()
    await user.should_see("Run:")
    command = calls[0][0]
    assert command[command.index("--halo") + 1] == "benchmark"
    assert command[command.index("--halo-family") + 1] == "shm-plus-plus"
