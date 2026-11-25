"""Reference programs must preserve conventions and reject stale successful exits."""
from __future__ import annotations

from pathlib import Path
import subprocess

import numpy as np
import pytest

from adroit.external.reference_rates import dmscatter


def test_reference_rate_units_and_fresh_output(tmp_path, monkeypatch) -> None:
    """A failed Fortran STOP cannot reuse the preceding successful spectrum."""
    source = tmp_path / "target with spaces.dres"
    source.write_text("nuclear density")
    attempts: list[Path] = []

    def run(argv, *, input, text, cwd, stdout, stderr, check, timeout, env):
        from adroit.core import config
        assert not [k for k in env if config.CREDENTIAL.search(k) or k in config.PROVIDER_VARIABLES]   # AL3-27
        attempt = Path(cwd)
        attempts.append(attempt)
        assert (attempt / "target.dres").read_text() == "nuclear density"
        assert input.splitlines()[4] == "target"
        settings = (attempt / "case.control").read_text()
        assert "coefnonrel 1 p 1.0" in settings
        if len(attempts) == 1:
            (attempt / "eventrate_spectra.dat").write_text("1 2000000\n2 3000000\n")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", run)
    args = (tmp_path, tmp_path / "work", source, 14, 29, {1: (1 / 246.2**2, 0.)})
    energy, rate = dmscatter(*args)
    np.testing.assert_array_equal(energy, [1., 2.])
    np.testing.assert_array_equal(rate, [2., 3.])
    with pytest.raises(FileNotFoundError):
        dmscatter(*args)
    assert attempts[0] != attempts[1]


def test_dmscatter_manifest_build_handles_repository_spaces(tmp_path, monkeypatch) -> None:
    """The shipped build command reaches its script and folder as whole arguments."""
    from adroit.core import config
    from adroit.external import setup
    from adroit.external.manifest import load_manifest

    repo = tmp_path / "repo with spaces"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "build_reference_backends.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        "assert sys.argv[1] == 'dmscatter'\n"
        "Path(sys.argv[2], 'reached.txt').write_text('built')\n")
    tools = tmp_path / "tools with spaces"
    folder = tools / "dmscatter"
    folder.mkdir(parents=True)
    monkeypatch.setattr(config, "PROJECT_ROOT", repo)
    setup.build(load_manifest().item("dmscatter"), tools)
    assert (folder / "reached.txt").read_text() == "built"


def test_reference_driver_rejects_an_unpinned_checkout(tmp_path, monkeypatch) -> None:
    """A different engine version cannot be labelled as the pinned comparison."""
    import importlib.util
    from adroit.external import fetch
    from adroit.external.manifest import load_manifest
    path = Path(__file__).resolve().parents[2]/'scripts/validate_optional_backends.py'
    spec = importlib.util.spec_from_file_location('reference_driver',path)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    driver.OUT = tmp_path/'evidence'
    monkeypatch.setattr(fetch,'locate',lambda name:tmp_path/'installed')
    monkeypatch.setattr(subprocess,'run',lambda argv,**kwargs:
                        subprocess.CompletedProcess(argv,0,stdout='0'*40+'\n'))
    with pytest.raises(RuntimeError,match='differs from pinned'):
        driver.checked_reference("Capt'n General")
    assert not driver.OUT.exists()
    pin = load_manifest().item("Capt'n General").version
    monkeypatch.setattr(subprocess,'run',lambda argv,**kwargs:
                        subprocess.CompletedProcess(argv,0,stdout=pin+'\n'))
    assert driver.checked_reference("Capt'n General")==tmp_path/'installed'
    import json
    evidence = json.loads((driver.OUT/'reference_revisions.json').read_text())
    assert evidence["Capt'n General"]['actual_commit']==pin
