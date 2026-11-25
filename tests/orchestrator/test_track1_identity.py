"""The faster traversal preserves the original content identity exactly."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from adroit.orchestrator.track1_identity import EXCLUDE, tree_identity


def reference(root: Path) -> str:
    """Independent uncached traversal with the original naming/order rules."""
    if not root.exists():
        return "missing"
    digest = hashlib.sha256()
    paths = [root] if root.is_file() else []
    if root.is_dir():
        for directory, subdirs, files in os.walk(root):
            subdirs[:] = sorted(name for name in subdirs if name not in EXCLUDE)
            paths.extend(Path(directory) / name for name in sorted(files) if name != ".env"
                         and Path(name).suffix not in {".pyc", ".nbc", ".nbi"})
    for path in paths:
        digest.update(str(path.relative_to(root) if root.is_dir() else path.name).encode())
        if path.is_symlink() and not path.exists():
            digest.update(os.readlink(path).encode())
        else:
            digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
    return digest.hexdigest()


def test_tree_identity_matches_reference_with_aliases_and_exclusions(tmp_path) -> None:
    """With no link to a directory in it (IA-02 changed only those: ``test_track1_linked_inputs.py``), a tree hashes as
    the reference does."""
    root = tmp_path / "source"
    (root / "nested").mkdir(parents=True)
    (root / "a").write_text("a")
    (root / "nested/b").write_text("b")
    (root / "leaf_alias").symlink_to(root / "a")
    (root / "broken").symlink_to(root / "absent")
    (root / "work").mkdir()
    (root / "work/generated").write_text("ignored")
    (root / ".env").write_text("ignored fixture")
    (root / "compiled.pyc").write_bytes(b"ignored")
    alias = tmp_path / "root_alias"
    alias.symlink_to(root, target_is_directory=True)
    for path in (root, alias, root / "a", root / "leaf_alias", root / "absent", root / "broken"):
        assert tree_identity(path) == reference(path)
    before = tree_identity(alias)
    (root / "nested/b").write_text("changed")
    assert tree_identity(alias) == reference(alias) != before
    (root / "leaf_alias").unlink()
    (root / "leaf_alias").symlink_to(root / "nested/b")
    assert tree_identity(alias) == reference(alias)


def test_tree_identity_resolves_parent_once_per_directory(tmp_path, monkeypatch) -> None:
    for i in range(20):
        (tmp_path / str(i)).write_text(str(i))
    original, calls = Path.resolve, []
    def resolve(path, *args, **kwargs):
        calls.append(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", resolve)
    assert tree_identity(tmp_path) == reference(tmp_path)
    assert calls == [tmp_path]


def test_derivation_data_such_as_parton_grids_is_not_part_of_a_runs_identity(monkeypatch) -> None:
    """The PDF grids feed record derivations only; hashing them would cost every run ~40 MB of reading for nothing."""
    from adroit.orchestrator import track1_identity
    monkeypatch.setattr(track1_identity, "tree_identity", lambda path: "stub")
    inputs = track1_identity.dependencies()["inputs"]
    assert "DIAMX" in inputs
    assert not any("LHAPDF grid" in name for name in inputs)
