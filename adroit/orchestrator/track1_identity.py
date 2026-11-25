"""Conservative content fingerprints of Track 1 physics and runtime inputs."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import importlib.metadata
import importlib.util
import os
from pathlib import Path
import sys

from adroit.core.config import PROJECT_ROOT, get_settings
from adroit.external.fetch import folder_of
from adroit.external.manifest import load_manifest

EXCLUDE = {".git", "__pycache__", ".pytest_cache", "build", "dist", "output", "outputs", "results", "work"}


@lru_cache(maxsize=100000)
def _digest(path: str, size: int, mtime: int, ctime: int) -> str:
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


class InputUnreadable(ValueError):
    """A calculation input whose identity cannot be established (``tree_identity``): never hashed as if absent."""


def tree_identity(root: Path) -> str:
    """Hash source, compiled runtime and static data; omit generated caches/output.

    A link to a directory is followed: its name and the text it holds are hashed, then the files it leads to under its
    name, as if they were in it (a feature audit's IA-02, 2026-11-10: ``os.walk`` had passed over linked directories,
    so data changed behind ``diamx/data -> <a folder>`` had left a Track 1 checkpoint's identity unchanged and the old
    result was resumed). A tree with no directory link hashes exactly as before. A link that leads nowhere is hashed by
    its name and its text, as before. A directory link that leads back into the tree it is in (to a folder the walk
    is inside), and a folder that cannot be listed, are refused (``InputUnreadable``), never passed over."""
    if not root.exists():
        return "missing"
    digest = hashlib.sha256()
    directory_root = root.is_dir()
    resolved_parents: dict[Path, Path] = {}
    relative_parents: dict[Path, Path] = {}
    for kind, path, text in _entries(root):
        if kind == "link":
            digest.update(b"\0directory link\0" + str(path.relative_to(root)).encode() + b"\0" + text.encode())
            continue
        symlink = path.is_symlink()
        if symlink and not path.exists():
            digest.update(str(path.relative_to(root)).encode())
            digest.update(os.readlink(path).encode())
            continue
        stat = path.stat()
        if directory_root:
            if path.parent not in relative_parents:
                relative_parents[path.parent] = path.parent.relative_to(root)
            name = str(relative_parents[path.parent] / path.name)
        else:
            name = path.name
        if path.parent not in resolved_parents:
            resolved_parents[path.parent] = path.parent.resolve()
        resolved = path.resolve() if symlink else resolved_parents[path.parent] / path.name
        digest.update(name.encode())
        digest.update(_digest(str(resolved), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns).encode())
    return digest.hexdigest()


def _entries(root: Path) -> list[tuple[str, Path, str]]:
    """What ``tree_identity`` hashes, in order: ("file", path, "") for each file, and ("link", path, its text) for each
    directory link, before what it leads to (its docstring)."""
    if root.is_file():
        return [("file", root, "")]
    entries: list[tuple[str, Path, str]] = []
    unreadable: list[OSError] = []
    within = {str(root): (os.path.realpath(root),)}           # the real folders each folder walked is inside
    for directory, subdirs, files in os.walk(root, onerror=unreadable.append, followlinks=True):
        subdirs[:] = sorted(name for name in subdirs if name not in EXCLUDE)
        entries.extend(("file", Path(directory) / name, "") for name in sorted(files) if name != ".env"
                       and Path(name).suffix not in {".pyc", ".nbc", ".nbi"})
        for name in subdirs:
            path = os.path.join(directory, name)
            if os.path.islink(path):
                real = os.path.realpath(path)
                if any(Path(inside).is_relative_to(real) for inside in within[directory]):
                    raise InputUnreadable(f"{path} links to {os.readlink(path)}, a folder it is already inside: a "
                                          "calculation input that leads back into itself has no identity")
                entries.append(("link", Path(path), os.readlink(path)))
            else:
                real = os.path.join(within[directory][-1], name)
            within[path] = (*within[directory], real)
    if unreadable:
        error = unreadable[0]
        raise InputUnreadable(f"{error.filename} cannot be listed ({error.strerror or error}): a calculation input "
                              "that cannot be read has no identity")
    return entries


def dependencies() -> dict:
    """The package/data, dependency runtimes, and external calculation releases."""
    tools = get_settings().tools_dir
    roots = {"adroit": PROJECT_ROOT / "adroit", "native_validation": PROJECT_ROOT / "docs/dm3/validation_results.json"}
    ignored = {"test reference", "cross-check", "optional dependency", "derivation data"}   # runs never read these
    for item in load_manifest().items():
        if item.role not in ignored and "cross-check" not in item.role and item.name not in {
                "Capt'n General", "RAPIDD (MadDM's vendored copy)", "GNU Scientific Library"}:
            roots[item.name] = folder_of(item)
    for module in ("numpy", "scipy", "sympy", "mpmath", "pydantic", "pydantic_core", "yaml", "networkx",
                   "matplotlib", "PIL", "contourpy", "astropy", "erfa"):
        spec = importlib.util.find_spec(module)
        if spec and spec.origin:
            roots[f"project-{module}"] = Path(spec.origin).parent
    for name in ("diamx", "smodels", "mg5", "mu2e", "directdm"):
        root = tools / f".venv-{name}"
        roots[f"runtime-{name}"] = root / "lib"
        roots[f"python-{name}"] = root / "bin/python"
    return {"python": sys.version, "tools_dir": str(tools.resolve()),
            "versions": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()
                         if d.metadata.get("Name")},
            "inputs": {name: {"path": str(path.resolve()), "sha256": tree_identity(path)} for name, path in roots.items()}}
