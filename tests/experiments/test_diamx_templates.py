"""What DIAMX derives from its inputs lives in a work folder named by them (the auditor's DV–IE recheck, DW-01, 2026-11-11;
``xenon.DiamxXenon._inputs``).

DIAMX keys its generated templates by their arguments, an input's path among them, not its bytes. Its work folder had
been named by the configuration and batch size alone, so after a detector input changed its bytes at the same path,
the result cache missed (its identity holds the input, IA-01) but DIAMX reused the template made from the old bytes:
the auditor's control read 3 before the change, 3 after it, and 8 only once the templates were removed by hand.

The first two tests use a stand-in DIAMX that keeps templates as DIAMX does (in the work folder, keyed by the input's
path); the last calls DIAMX's own installed selector (``diamx.experiment.process_bkg_template``) in DIAMX's own
environment, its template's generation and the inference a scalar, as the auditor's control did."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from adroit.core.dm_state import DarkMatterParticle, ExpectedSignal
from adroit.experiments import xenon
from tests.experiments.test_diamx_inputs import _Diamx


class _Templating(_Diamx):
    """A DIAMX whose answer is a template generated once per input path in its work folder's ``templates`` (as DIAMX's
    ``process_bkg_template`` keeps them), plus one."""

    def _backend(self, command, **kwargs):
        request = json.loads(Path(command[2]).read_text())
        templates = Path(request["work_dir"]) / "templates"
        templates.mkdir(exist_ok=True)
        data = self.copied(command, self.data)                         # DIAMX reads the generation's copy
        template = templates / f"bkg_{hashlib.sha256(str(data).encode()).hexdigest()[:12]}.txt"
        if not template.exists():                                      # keyed by the path: made once
            template.write_text(data.read_text())
        value = float(template.read_text()) + 1
        self.calls.append(value)
        Path(command[3]).write_text(json.dumps([{"label": label, "upper": value} for label in request["labels"]]))

    def clean(self) -> float:
        """The limit with every work folder removed: what DIAMX derives from the inputs as they are."""
        import shutil
        shutil.rmtree(self.tools / "diamx-work", ignore_errors=True)
        return self.limit()


@pytest.fixture
def templating(tmp_path, monkeypatch):
    return _Templating(tmp_path, monkeypatch)


def _folders(diamx) -> list[str]:
    return sorted(p.name for p in (diamx.tools / "diamx-work").iterdir())


def test_a_changed_input_is_never_read_through_a_template_made_from_its_old_bytes(templating):
    """The auditor's control with the stand-in: warm after the data changed equals clean, and the work folders differ."""
    assert templating.limit() == 3
    first = _folders(templating)
    templating.data.write_text("7\n")                                  # the same path, other bytes
    warm = templating.limit()
    assert warm == 8 and len(_folders(templating)) == 2 and first[0] in _folders(templating)
    assert warm == templating.clean()


@pytest.mark.parametrize("change", ["interpreter", "runtime library", "source", "configuration"])
def test_every_input_names_its_own_work_folder(templating, change):
    templating.limit()
    if change == "interpreter":
        templating.python.write_text("runtime 5")
    elif change == "runtime library":
        templating.library.write_text("4")
    elif change == "source":
        templating.source.write_text("version = 2\n")
    else:
        templating.config.write_text('{"changed": true}')
    templating.limit()
    assert len(_folders(templating)) == 2


def test_spectra_with_the_same_inputs_share_their_work_folder(templating):
    """Two masses, one folder: its templates made once, each spectrum its own result."""
    other = ExpectedSignal(experiment=templating.module.search, particle=DarkMatterParticle(mass_gev=50),
                           interaction_id="fixture", total_events=100, observable=xenon.ENERGIES_KEV.tolist(),
                           density=[1.0 + i for i in range(len(xenon.ENERGIES_KEV))])
    templating.limit()
    templating.module.upper_limit(other)
    folder = _folders(templating)
    assert len(folder) == 1 and folder[0].startswith(f"{templating.module.spec['config']}-100-")
    assert len(list((templating.tools / "diamx-work" / folder[0] / "templates").iterdir())) == 1
    assert len(list((templating.tools / "diamx-work" / folder[0]).glob("result-*.json"))) == 2


def test_two_checkouts_of_the_same_code_share_a_work_folder(templating, tmp_path, monkeypatch):
    """The driver and DIAMX's sources by their names and bytes, not their paths: a second checkout of the same code
    (the driver elsewhere) reads the templates the first made; a driver of other bytes has its own folder."""
    templating.limit()
    elsewhere = tmp_path / "another checkout" / xenon.DRIVER.name
    elsewhere.parent.mkdir()
    elsewhere.write_bytes(xenon.DRIVER.read_bytes())
    monkeypatch.setattr(xenon, "DRIVER", elsewhere)
    templating.limit()
    assert len(_folders(templating)) == 1 and len(templating.calls) == 1        # the same folder, its result reused
    elsewhere.write_bytes(xenon.DRIVER.read_bytes() + b"\n# changed\n")
    templating.limit()
    assert len(_folders(templating)) == 2


HELPER = '''
import json, sys
from pathlib import Path
from diamx.experiment import process_bkg_template
request = json.loads(Path(sys.argv[1]).read_text())
out = Path(request["work_dir"])
(out / "templates").mkdir(exist_ok=True)
data = Path(sys.argv[3])

def generate(name, rate, path, **kwargs):
    Path(path).write_text(data.read_text())

path = process_bkg_template({"bkg_name": "fixture", "rate_nominal": 1, "args": {"template_path": str(data)}},
                            {"roi": {"x": [0, 1]}}, "AUDIT", str(out), "templates", generate)
value = float(Path(path).read_text()) + 1
Path(sys.argv[2]).write_text(json.dumps([{"label": label, "upper": value} for label in request["labels"]]))
'''


@pytest.mark.needs("diamx")
def test_diamx_s_own_template_selector_never_serves_a_template_of_an_input_s_old_bytes(tmp_path, monkeypatch):
    """The auditor's control: DIAMX's installed ``process_bkg_template``, in DIAMX's environment, decides whether a
    template is made or reused; only the template's contents (the detector data's value) and the inference (that value
    plus one) are a stand-in. Nothing is written in the tools folder: the work folders are the test's."""
    real = xenon.DiamxXenon("LZ WS2022+WS2024")
    helper = tmp_path / "helper.py"
    helper.write_text(HELPER)
    run = subprocess.run                                               # before the fixture replaces it
    diamx = _Diamx(tmp_path, monkeypatch)

    def selector(command, **kwargs):
        run([str(real.python), str(helper), command[2], command[3], str(diamx.copied(command, diamx.data))],
            check=True, capture_output=True,
            env={**xenon.capped_environment(), "PYTHONPATH": str(real.folder), "PYTHONDONTWRITEBYTECODE": "1"},
            timeout=300)
    monkeypatch.setattr(xenon.subprocess, "run", selector)
    assert diamx.limit() == 3
    diamx.data.write_text("7\n")
    assert diamx.limit() == 8                                          # 3 at the pin: the old template reused
    for folder in (diamx.tools / "diamx-work").iterdir():
        assert len(list((folder / "templates").iterdir())) == 1
    assert len(list((diamx.tools / "diamx-work").iterdir())) == 2
