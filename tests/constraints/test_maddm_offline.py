"""MadGraph and MadDM run with the network denied (``maddm.offline``): MadDM's output can fall back to installing
tools from the web when a generation comes out empty."""

import shutil
import subprocess

import pytest

from adroit.constraints import maddm


@pytest.mark.skipif(not shutil.which("sandbox-exec"), reason="macOS's sandbox-exec is not available")
def test_the_command_runs_in_a_sandbox_that_denies_the_network():
    command = maddm.offline(["/bin/echo", "ok"])
    assert command[:2] == ["sandbox-exec", "-p"] and "(deny network*)" in command[2]
    assert subprocess.run(command, capture_output=True, text=True).stdout.strip() == "ok"


def test_a_command_is_left_alone_where_no_sandbox_exists(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert maddm.offline(["true"]) == ["true"]
