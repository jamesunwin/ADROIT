"""Calculation inputs behind a link to a directory (a feature audit's IA-02, 2026-11-10; ``tree_identity``).

The auditor changed detector data behind ``diamx/diamx/data -> <a folder>``: the Track 1 dependency identity did not
change, and a resume returned the old result (1) where a fresh run gave the new one (9). Now a directory link's name,
its text and what it leads to are hashed; one that leads back into the tree, and a folder that cannot be listed, are
refused. A tree with no directory link hashes as before (``test_track1_identity.py``)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from adroit.orchestrator.track1_identity import InputUnreadable, tree_identity
from tests.orchestrator.test_track1_identity import reference


def _tool(tmp_path: Path) -> tuple[Path, Path]:
    """A tool folder whose data folder is a link to a folder elsewhere: (the tool, the data's file)."""
    tool, data = tmp_path / "tool", tmp_path / "elsewhere" / "detector_data"
    (tool / "pkg").mkdir(parents=True)
    data.mkdir(parents=True)
    (tool / "pkg/model.py").write_text("version = 1")
    (data / "events.csv").write_text("1")
    (tool / "pkg/data").symlink_to(data, target_is_directory=True)
    return tool, data / "events.csv"


def test_data_behind_a_directory_link_is_part_of_the_identity(tmp_path):
    """The auditor's case: the data changed behind the link changes the identity, as an ordinary file does; the link
    led to an identical copy elsewhere changes it too (its text is hashed), and back again restores it."""
    tool, events = _tool(tmp_path)
    first = tree_identity(tool)
    assert first != reference(tool)                              # the pin's walk passed the linked folder over
    assert tree_identity(tool) == first                          # stable
    events.write_text("9")
    changed = tree_identity(tool)
    assert changed != first
    events.write_text("1")
    assert tree_identity(tool) == first
    copy = tmp_path / "copy"
    shutil.copytree(events.parent, copy)
    (tool / "pkg/data").unlink()
    (tool / "pkg/data").symlink_to(copy, target_is_directory=True)
    assert tree_identity(tool) not in (first, changed)
    (tool / "pkg/data").unlink()
    (tool / "pkg/data").symlink_to(events.parent, target_is_directory=True)
    assert tree_identity(tool) == first
    (tool / "pkg/model.py").write_text("version = 2")            # the ordinary file: a positive control
    assert tree_identity(tool) != first


def test_a_tree_without_directory_links_hashes_as_before(tmp_path):
    tool, _ = _tool(tmp_path)
    (tool / "pkg/data").unlink()
    assert tree_identity(tool) == reference(tool)


def test_a_broken_directory_link_is_identified_by_its_text(tmp_path):
    """A link that leads nowhere is hashed by its name and its text (as before); its target appearing changes it."""
    tool, events = _tool(tmp_path)
    shutil.rmtree(events.parent)
    broken = tree_identity(tool)
    assert broken == reference(tool)
    (tool / "pkg/data").unlink()
    (tool / "pkg/data").symlink_to(tmp_path / "elsewhere" / "another", target_is_directory=True)
    assert tree_identity(tool) != broken
    (tool / "pkg/data").unlink()
    (tool / "pkg/data").symlink_to(events.parent, target_is_directory=True)
    events.parent.mkdir()
    events.write_text("1")
    assert tree_identity(tool) not in (broken, reference(tool))


@pytest.mark.parametrize("case", ["itself", "its tool", "above the tool", "two folders to each other"])
def test_a_directory_link_that_leads_back_into_itself_is_refused(tmp_path, case):
    tool, events = _tool(tmp_path)
    if case == "itself":
        (events.parent / "loop").symlink_to(events.parent, target_is_directory=True)
    elif case == "its tool":
        (events.parent / "loop").symlink_to(tool, target_is_directory=True)
    elif case == "above the tool":
        (tool / "pkg/up").symlink_to(tmp_path, target_is_directory=True)
    else:
        (tool / "a").mkdir()
        (tool / "b").mkdir()
        (tool / "a/to_b").symlink_to(tool / "b", target_is_directory=True)
        (tool / "b/to_a").symlink_to(tool / "a", target_is_directory=True)
    with pytest.raises(InputUnreadable, match="a folder it is already inside"):
        tree_identity(tool)


def test_a_link_to_a_folder_beside_it_is_not_a_cycle(tmp_path):
    """Two names for one folder, neither inside the other: both hashed, nothing refused."""
    tool, _ = _tool(tmp_path)
    (tool / "a").mkdir()
    (tool / "a/f").write_text("f")
    (tool / "b").symlink_to(tool / "a", target_is_directory=True)
    before = tree_identity(tool)
    (tool / "a/f").write_text("g")
    assert tree_identity(tool) != before


@pytest.mark.skipif(os.geteuid() == 0, reason="a folder's permissions do not bind the superuser")
@pytest.mark.parametrize("linked", [False, True])
def test_a_folder_that_cannot_be_listed_is_refused(tmp_path, linked):
    """Linked or not: os.walk had passed over a folder it could not list, as if it held nothing."""
    tool, events = _tool(tmp_path)
    closed = events.parent if linked else tool / "pkg"
    if not linked:
        (tool / "pkg/data").unlink()
    closed.chmod(0)
    try:
        with pytest.raises(InputUnreadable, match="cannot be listed"):
            tree_identity(tool)
    finally:
        closed.chmod(0o755)


def test_an_excluded_name_is_passed_over_linked_or_not(tmp_path):
    tool, events = _tool(tmp_path)
    before = tree_identity(tool)
    (tool / "work").symlink_to(events.parent, target_is_directory=True)
    assert tree_identity(tool) == before


def test_a_track1_resume_refuses_changed_data_behind_a_linked_folder(tmp_path, monkeypatch):
    """The auditor's journey through the real ``track1.run``, its dependency identity and its checkpoint, the numerical
    calculation alone replaced by a stand-in that reads the linked data: an unchanged resume reuses the result; changed
    data behind the link, the link led elsewhere (an identical copy), a link that leads nowhere and an ordinary source
    file each refuse a resume, and a fresh run reads the new data; a link back into the tool refuses the run itself."""
    from unittest.mock import patch

    from adroit.core.checkpoint import CheckpointMismatch
    from adroit.core.config import get_settings
    from adroit.core.model_spec import ModelSpec
    from adroit.model_building.audit import audit
    from adroit.orchestrator import track1
    from adroit.parameter_space.classes import Point
    tools = tmp_path / "tools"
    monkeypatch.setenv("ADROIT_TOOLS_DIR", str(tools))
    get_settings.cache_clear()
    try:
        tool = tools / "diamx"
        (tool / "diamx").mkdir(parents=True)
        data = tmp_path / "detector_data"
        data.mkdir()
        events = data / "events.csv"
        events.write_text("1")
        link = tool / "diamx/data"
        link.symlink_to(data, target_is_directory=True)
        spec = ModelSpec(name="fixture", fields=[{"name": "chi", "role": "dark_matter", "spin": .5,
                                                   "dark_parity": -1}])
        request = track1.Track1Request(spec=spec, literature=False, workers=1, halo="published",
                                       propagation="conservative")
        calls = []

        def numerical(request, folder, fetch, checkpoint):
            calls.append(float(events.read_text()))
            return track1.Track1Result(request=request, audit=audit(spec), fixed=Point(m_chi=calls[-1], m_med=30),
                                       class_name="a numerical stand-in")

        def relink(target: Path) -> None:
            link.unlink()
            link.symlink_to(target, target_is_directory=True)

        with patch.object(track1, "_run", numerical), patch("adroit.orchestrator.checklist.for_track1", lambda r: []):
            run = tmp_path / "run"
            assert track1.run(request, run).fixed.m_chi == 1
            assert track1.run(request, run, resume=True).fixed.m_chi == 1 and calls == [1]
            events.write_text("9")
            with pytest.raises(CheckpointMismatch, match="calculation data changed"):
                track1.run(request, run, resume=True)
            assert track1.run(request, tmp_path / "fresh").fixed.m_chi == 9
            events.write_text("1")
            assert track1.run(request, run, resume=True).fixed.m_chi == 1                # as it was: reused
            copy = tmp_path / "copy"
            shutil.copytree(data, copy)
            for target in (copy, tmp_path / "nowhere"):
                relink(target)
                with pytest.raises(CheckpointMismatch, match="calculation data changed"):
                    track1.run(request, run, resume=True)
            relink(data)
            (data / "loop").symlink_to(tool, target_is_directory=True)
            with pytest.raises(InputUnreadable, match="a folder it is already inside"):
                track1.run(request, run, resume=True)
            (data / "loop").unlink()
            (tool / "diamx/model.py").write_text("version = 2")
            with pytest.raises(CheckpointMismatch, match="calculation data changed"):
                track1.run(request, run, resume=True)
            assert calls == [1, 9]
    finally:
        get_settings.cache_clear()
