"""The manifest of external tools and data."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from adroit.external.manifest import (
    ExternalItem,
    Manifest,
    Obtain,
    load_manifest,
    manual_instructions,
)


def test_the_shipped_manifest_loads_and_is_complete() -> None:
    manifest = load_manifest()
    names = {item.name for item in manifest.items()}
    assert {"WimPyDD", "DirectDM", "DIAMX", "NEST"} <= names
    for item in manifest.items():
        assert item.purpose and item.source and item.used_in, item.name
    # the two sources that block automated downloads are fetched by the user
    assert {item.name for item in manifest.manual()} == {
        "WimPyDD", "LZ extended window (arXiv:2609.02823)"}
    assert {item.name for item in manifest.for_milestone("DM7")} == {
        "Capt'n General", "B16 standard solar model (AGSS09)"}


def test_identical_contents_reuse_parse_without_sharing_mutations(tmp_path, monkeypatch) -> None:
    from adroit.external import manifest as module
    module._parse_manifest.cache_clear()
    original, calls = module.yaml.safe_load, []
    def parse(contents):
        calls.append(contents)
        return original(contents)
    monkeypatch.setattr(module.yaml, "safe_load", parse)
    path = tmp_path / "tools.yaml"
    path.write_text("tools: [{name: a, purpose: p, obtain: pip, source: s, used_in: [DM3]}]\n")
    first = load_manifest(path)
    first.tools[0].used_in.append("mutated")
    first.tools.clear()
    second = load_manifest(path)
    assert second.item("a").used_in == ["DM3"]
    assert len(calls) == 1


def test_manifest_changes_are_read_even_with_same_size_and_timestamp(tmp_path) -> None:
    import os
    path = tmp_path / "tools.yaml"
    path.write_text("tools: [{name: a, purpose: p, obtain: pip, source: s}]\n")
    before = path.stat()
    assert load_manifest(path).item("a").source == "s"
    path.write_text("tools: [{name: b, purpose: p, obtain: pip, source: s}]\n")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert load_manifest(path).item("b").source == "s"
    path.write_text("tools: [{name: b, purpose: p, obtain: manual, source: s}]\n")
    with pytest.raises(ValidationError, match="manual_steps"):
        load_manifest(path)


def test_manifest_reuse_does_not_cache_backend_availability(tmp_path) -> None:
    from adroit.external.fetch import locate
    path = tmp_path / "tools.yaml"
    path.write_text("tools: [{name: a, purpose: p, obtain: git, source: s, folder: a}]\n")
    assert locate("a", load_manifest(path), tmp_path) is None
    (tmp_path / "a").mkdir()
    (tmp_path / "a/ready").write_text("ready")
    assert locate("a", load_manifest(path), tmp_path) == tmp_path / "a"
    (tmp_path / "a/ready").unlink()
    assert locate("a", load_manifest(path), tmp_path) is None


def test_every_item_records_its_terms_of_use() -> None:
    assert [i.name for i in load_manifest().items() if not i.licence_confirmed] == []
    wimpydd = next(i for i in load_manifest().tools if i.name == "WimPyDD")
    assert "citation" in wimpydd.licence and "not redistributed" in wimpydd.licence


def test_the_user_is_told_what_to_download_by_hand() -> None:
    text = manual_instructions(load_manifest())
    assert "https://wimpydd.hepforge.org" in text and "data/external/manual/WimPyDD" in text
    assert "https://www.hepdata.net/record/ins3199115" in text
    assert manual_instructions(Manifest()) == ""


def test_a_manual_item_must_say_what_to_do(tmp_path) -> None:
    with pytest.raises(ValidationError, match="manual_steps"):
        ExternalItem(name="x", purpose="p", obtain=Obtain.manual, source="s")
    assert ExternalItem(name="x", purpose="p", obtain=Obtain.pip, source="s").automatic
    twice = tmp_path / "tools.yaml"
    twice.write_text("tools:\n" + 2 * "  - {name: a, purpose: p, obtain: pip, source: s}\n",
                     encoding="utf-8")
    with pytest.raises(ValueError, match="twice"):
        load_manifest(twice)


def test_a_download_item_lists_its_files() -> None:
    with pytest.raises(ValidationError, match="files"):
        ExternalItem(name="x", purpose="p", obtain=Obtain.download, source="s")
    releases = [i for i in load_manifest().items() if i.obtain is Obtain.download]
    assert {i.name for i in releases} >= {"CRESST-III data release (arXiv:1905.07335)",
                                          "CDMSlite Run 2 data release (arXiv:1707.01632)"}
    assert all(i.files and i.folder for i in releases)
    assert load_manifest().item("DIAMX").folder == "diamx"
    with pytest.raises(KeyError):
        load_manifest().item("nothing")


def test_every_git_items_version_is_a_ref_git_can_check_out() -> None:
    """The clean-machine install test (2026-10-12): MadDM's version read 'rc/3.3 at 6570bb5 (MadDM v3.3.0 release
    candidate)', which git checkout refused; descriptions belong in a comment or the note."""
    import re
    from adroit.external.manifest import Obtain, load_manifest
    for item in load_manifest().items():
        if item.obtain is Obtain.git and item.version:
            assert re.fullmatch(r"[\w./-]+", item.version), (item.name, item.version)


def test_every_build_command_quotes_its_paths():
    """A repository or tools path with spaces and parentheses ("My Mac (James’s MacBook Pro)") must stay one word:
    two build commands broke on it when the CERN twiki came back (2026-10-13)."""
    import shlex
    import subprocess

    from adroit.external.manifest import load_manifest
    odd = "/tmp/a b (c)/x"
    fill = {k: f"{odd}/{k}" for k in ("tools", "folder", "repo", "python")} | {"arch": "arm64",
                                                                              "fortran_python": "3.12"}
    for item in load_manifest().items():
        for template in item.build:
            command = template.format(**fill)
            assert subprocess.run(["sh", "-n", "-c", command], capture_output=True).returncode == 0, command
            lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            for token in lexer:
                assert "(c)" not in token or "a b (c)" in token, (item.name, command)


def test_the_susy_tables_fetch_every_page_their_builder_reads():
    """A fresh install fetched four of the nine twiki pages scripts/build_xsec_tables.py reads (2026-10-13)."""
    import re

    from adroit.core.config import PROJECT_ROOT
    from adroit.external.manifest import load_manifest
    needed = set(re.findall(r"SUSYCrossSections[0-9x]*TeV[a-z0-9]*",
                            (PROJECT_ROOT / "scripts" / "build_xsec_tables.py").read_text()))
    item = next(i for i in load_manifest().items() if i.name == "LHC SUSY cross sections")
    assert needed <= {url.rsplit("/", 1)[-1] for url in item.files}
