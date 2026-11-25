"""The set-up command: state, fetching and building, manual instructions, licences (DM11)."""

import pytest
from typer.testing import CliRunner

from adroit.external import fetch, setup
from adroit.external.manifest import Manifest, load_manifest


def _manifest() -> Manifest:
    return Manifest.model_validate({
        "tools": [
            {"name": "gitty", "purpose": "p", "obtain": "git", "source": "https://example.org/gitty.git",
             "licence": "MIT", "build": ["echo built > built.txt"], "present_if": "built.txt"},
            {"name": "numpy-check", "purpose": "p", "obtain": "pip", "source": "numpy", "licence": "BSD"},
            {"name": "absent-pkg", "purpose": "p", "obtain": "pip", "source": "no-such-package-xyz",
             "required": False},
        ],
        "data": [
            {"name": "release", "purpose": "p", "obtain": "download", "source": "s", "folder": "rel",
             "files": ["https://example.org/a.txt"]},
            {"name": "by-hand", "purpose": "p", "obtain": "manual", "source": "s",
             "manual_steps": "Download it in a browser and put it in data/external/manual/by-hand."},
        ]})


@pytest.fixture
def tools(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "MANUAL_DIR", tmp_path / "manual")
    (tmp_path / "rel").mkdir()
    (tmp_path / "rel" / "a.txt").write_text("x")
    return tmp_path


def _by_name(statuses):
    return {s.name: s for s in statuses}


def test_it_reports_each_item_without_fetching_by_default(tools) -> None:
    out = _by_name(setup.run(_manifest(), tools_dir=tools))
    assert out["release"].present and out["numpy-check"].present
    assert not out["gitty"].present and "adroit setup --fetch" in out["gitty"].action
    assert not out["by-hand"].present and "browser" in out["by-hand"].action
    assert "uv add no-such-package-xyz" in out["absent-pkg"].action and not out["absent-pkg"].required


def test_fetch_then_build_with_the_folder_filled_in(tools, monkeypatch) -> None:
    def fake_fetch(name, manifest, tools_dir):
        folder = fetch.folder_of(manifest.item(name), tools_dir)
        folder.mkdir(parents=True)
        return folder
    monkeypatch.setattr(fetch, "fetch", fake_fetch)
    out = _by_name(setup.run(_manifest(), fetch_missing=True, tools_dir=tools))
    assert out["gitty"].present and out["gitty"].action == "fetched and built"
    assert (tools / "gitty" / "built.txt").read_text().strip() == "built"
    assert fetch.is_present(_manifest().item("gitty"), tools)                 # present_if is now met


def test_the_report_separates_what_is_needed_from_what_is_optional(tools) -> None:
    text = setup.report(setup.run(_manifest(), tools_dir=tools))
    assert "Required: 2 of 4 present." in text and "required item(s) missing" in text
    assert "## Still to do (required)" in text and "## Optional, not present" in text
    assert "not confirmed: read it before depending on the item" in text      # the manual item states no licence


def test_one_item_or_one_milestone(tools) -> None:
    assert [s.name for s in setup.run(_manifest(), only="release", tools_dir=tools)] == ["release"]
    with pytest.raises(KeyError):
        setup.run(_manifest(), only="nothing", tools_dir=tools)
    milestone = setup.run(load_manifest(), milestone="DM7", tools_dir=tools)
    assert milestone and all("DM7" in s.used_in for s in milestone)


def test_every_item_of_the_real_manifest_says_whether_it_is_needed() -> None:
    manifest = load_manifest()
    optional = {i.name for i in manifest.items() if not i.required}
    assert {"WIMpy_NREFT", "MadDM", "NEST"} <= optional
    assert {"DIAMX", "CDMSlite Run 2 data release (arXiv:1707.01632)"}.isdisjoint(optional)


def test_the_command_line(tools, monkeypatch) -> None:
    from adroit.orchestrator import cli
    monkeypatch.setattr(setup, "load_manifest", _manifest)
    monkeypatch.setattr(setup, "get_settings", lambda: type("S", (), {"tools_dir": tools})())
    monkeypatch.setattr(fetch, "get_settings", lambda: type("S", (), {"tools_dir": tools})())
    out = CliRunner().invoke(cli.app, ["setup", "--only", "release"])
    assert out.exit_code == 0 and "release" in out.output
    assert CliRunner().invoke(cli.app, ["setup", "--only", "nothing"]).exit_code != 0


def test_a_failed_build_marks_its_item_missing_and_the_others_are_still_fetched(tools, monkeypatch) -> None:
    """The clean-machine install test (2026-10-12): one optional backend's failed build stopped every later fetch."""
    manifest = Manifest.model_validate({"tools": [
        {"name": "broken", "purpose": "p", "obtain": "git", "source": "https://example.org/broken.git",
         "build": ["exit 3"], "present_if": "built.txt", "required": False},
        {"name": "fine", "purpose": "p", "obtain": "git", "source": "https://example.org/fine.git",
         "build": ["echo built > built.txt"], "present_if": "built.txt"}]})

    def fake_fetch(name, manifest, tools_dir):
        folder = fetch.folder_of(manifest.item(name), tools_dir)
        folder.mkdir(parents=True, exist_ok=True)
        return folder
    monkeypatch.setattr(fetch, "fetch", fake_fetch)
    out = _by_name(setup.run(manifest, fetch_missing=True, tools_dir=tools))
    assert not out["broken"].present and "CalledProcessError" in out["broken"].action
    assert "rerun `adroit setup --fetch`" in out["broken"].action
    assert out["fine"].present and out["fine"].action == "fetched and built"


def test_a_clone_left_by_a_failed_build_is_reused(tmp_path, monkeypatch) -> None:
    item = Manifest.model_validate({"tools": [{"name": "g", "purpose": "p", "obtain": "git", "version": "abc123",
                                               "source": "https://example.org/g.git"}]}).item("g")
    calls = []
    monkeypatch.setattr(fetch.subprocess, "run", lambda command, check, env: calls.append(command))   # env: AL3-27
    (tmp_path / "g" / ".git").mkdir(parents=True)
    fetch._clone(item, tmp_path / "g")
    assert calls == [["git", "-C", str(tmp_path / "g"), "checkout", "--quiet", "abc123"]]
    fetch._clone(item, tmp_path / "fresh")
    assert calls[1][:2] == ["git", "clone"]


def test_dmscatters_build_adds_orbitals_missing_dependency_on_main(tmp_path, monkeypatch) -> None:
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "scripts" / "build_reference_backends.py"
    spec = importlib.util.spec_from_file_location("build_reference_backends", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "src").mkdir()
    (tmp_path / "make").mkdir()
    (tmp_path / "src" / "parameters.f90").write_text("format(I2,2X,4E11.4)\n")
    (tmp_path / "make" / "Makefile").write_text("main.o:             types.o\norbitals.o:         \nx.o: y.o\n")
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: None)
    module.build_dmscatter(tmp_path)
    module.build_dmscatter(tmp_path)                                          # idempotent
    assert (tmp_path / "make" / "Makefile").read_text().split("\n")[1] == "orbitals.o: main.o"


def test_build_fills_adroits_python_its_architecture_and_gfortrans_only_when_asked(tools, monkeypatch) -> None:
    import platform
    import sys
    manifest = Manifest.model_validate({"tools": [
        {"name": "env", "purpose": "p", "obtain": "git", "source": "s", "build": ["printf '%s|%s' \"{python}\" \"{arch}\" > out.txt"]},
        {"name": "fortran", "purpose": "p", "obtain": "git", "source": "s", "build": ["echo {fortran_python} > out.txt"]}]})
    (tools / "env").mkdir()
    (tools / "fortran").mkdir()
    asked = []
    monkeypatch.setattr(setup, "fortran_python", lambda: asked.append(1) or "cpython-3.12-macos-x86_64-none")
    setup.build(manifest.item("env"), tools)
    assert (tools / "env" / "out.txt").read_text().split("|") == [sys.executable, platform.machine()] and not asked
    setup.build(manifest.item("fortran"), tools)
    assert (tools / "fortran" / "out.txt").read_text().strip() == "cpython-3.12-macos-x86_64-none" and asked


def test_fortran_python_follows_the_architecture_gfortran_compiles_for(monkeypatch) -> None:
    import types
    monkeypatch.setattr(setup.sys, "platform", "darwin")
    for target, arch in (("x86_64-apple-darwin23\n", "x86_64"), ("aarch64-apple-darwin24\n", "aarch64"),
                         ("arm64-apple-darwin24\n", "aarch64")):
        monkeypatch.setattr(setup.subprocess, "run", lambda *a, **k: types.SimpleNamespace(stdout=target))
        assert setup.fortran_python() == f"cpython-3.12-macos-{arch}-none"
    monkeypatch.setattr(setup.sys, "platform", "linux")
    assert setup.fortran_python() == "3.12"


def test_the_tools_with_their_own_environments_are_built_by_setup_and_pinned() -> None:
    """R11 (the owner, 2026-10-12): adroit setup --fetch builds them; present only once built (present_if)."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    manifest = load_manifest()
    for name, pins in (("DIAMX", "diamx"), ("DirectDM", "directdm"),
                       ("Mu2e nuclear-response scripts (Berkeley-Electroweak-Physics)", "mu2e"),
                       ("MadGraph5_aMC@NLO", "mg5")):
        item = manifest.item(name)
        assert item.build and item.present_if, name
        assert any(f"constraints/{pins}.txt" in command for command in item.build), name
        assert (root / "adroit" / "external" / "constraints" / f"{pins}.txt").is_file()


def test_madgraph_is_configured_from_its_default(tmp_path, monkeypatch) -> None:
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "scripts" / "build_reference_backends.py"
    spec = importlib.util.spec_from_file_location("build_reference_backends", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "input").mkdir()
    (tmp_path / "input" / ".mg5_configuration_default.txt").write_text(
        "# fortran_compiler = None\nother = 1\n# auto_update = 7\n")
    monkeypatch.setattr(module.shutil, "which", lambda name: "/opt/bin/gfortran")
    module.configure_madgraph(tmp_path)
    assert (tmp_path / "input" / "mg5_configuration.txt").read_text().split("\n") == [
        "fortran_compiler = /opt/bin/gfortran", "other = 1", "auto_update = 0", ""]


def test_setup_warns_when_its_python_runs_under_rosetta(tools, monkeypatch) -> None:
    """The x86_64 clean install on Apple Silicon (2026-10-12): DIAMX's jaxlib needs AVX, which Rosetta lacks."""
    statuses, under_rosetta = setup.run(_manifest(), tools_dir=tools), setup.under_rosetta
    monkeypatch.setattr(setup, "under_rosetta", lambda: True)
    assert "runs under Rosetta" in setup.report(statuses)
    monkeypatch.setattr(setup, "under_rosetta", lambda: False)
    assert "Rosetta" not in setup.report(statuses)
    monkeypatch.setattr(setup.sys, "platform", "linux")
    assert under_rosetta() is False                                      # only macOS translates


def test_a_native_python_is_never_said_to_run_under_rosetta(monkeypatch) -> None:
    """The auditor's CO recheck, CR-07 (2026-10-26): the warning had come from a ``sysctl`` child launched as x86_64 (a
    universal binary), although ADROIT's own Python was native arm64. A native interpreter, whatever a child would
    say, gets no warning; an x86_64 one translated still does; the question is asked of this process, not a child."""
    monkeypatch.setattr(setup.sys, "platform", "darwin")
    monkeypatch.setattr(setup.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a child")))
    monkeypatch.setattr(setup.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(setup, "_translated", lambda: True)               # what a translated child would report
    assert setup.under_rosetta() is False
    monkeypatch.setattr(setup.platform, "machine", lambda: "x86_64")
    assert setup.under_rosetta() is True
    monkeypatch.setattr(setup, "_translated", lambda: False)              # an Intel Mac
    assert setup.under_rosetta() is False


def test_this_processs_translation_is_read_in_process() -> None:
    """On this machine's own interpreter: a native arm64 Python on macOS is not translated, read in process."""
    import platform
    import sys
    if sys.platform == "darwin" and platform.machine() == "arm64":
        assert setup._translated() is False and setup.under_rosetta() is False
    else:
        assert setup.under_rosetta() is (sys.platform == "darwin" and setup._translated())
