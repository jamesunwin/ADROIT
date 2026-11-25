"""The set-up command for the public release (DM11): every external tool and data set, its state and licence.

For each item of the manifest (``tools.yaml``):
- whether it is present (``fetch.is_present``; a pip item by its installed version);
- with ``fetch_missing``, a missing automatic item (git, download) is fetched, then
  built if the manifest gives build commands (``build``); otherwise its build
  notes are shown for the user to follow;
- a manual item (a source that blocks automated downloads) is described: what
  to download, and where to put it. The command checks whether it has arrived;
- its licence, or that its licence has not been confirmed.

Nothing fetched is ever committed: automatic items live in the tools folder,
manual ones in ``external/manual`` of the data folder (``ADROIT_DATA_DIR``; owner's rules, 2026-09-29).
"""

from __future__ import annotations

import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from pydantic import Field

from adroit.core.config import child_environment
from adroit.core.config import get_settings
from adroit.core.state import StrictModel
from adroit.external import fetch
from adroit.external.manifest import ExternalItem, Manifest, Obtain, load_manifest


class ItemStatus(StrictModel):
    """One item's state after the set-up command has looked at it."""

    name: str
    kind: str                       # "tool" or "data"
    obtain: Obtain
    present: bool
    required: bool = True
    folder: str = ""
    licence: str = ""
    used_in: list[str] = Field(default_factory=list)
    role: str = ""
    action: str = ""                # what was done, or what the user must do


def _installed(item: ExternalItem) -> bool:
    try:
        metadata.version(item.source)
    except metadata.PackageNotFoundError:
        return False
    return True


def _present(item: ExternalItem, tools_dir: Path | None) -> bool:
    return _installed(item) if item.obtain is Obtain.pip else fetch.is_present(item, tools_dir)


def fortran_python() -> str:
    """A uv Python request with the architecture gfortran compiles for, since a Fortran extension must match its
    interpreter (an Intel Homebrew gfortran on Apple Silicon targets x86_64): on macOS
    cpython-3.12-macos-<arch>-none, elsewhere 3.12."""
    if sys.platform != "darwin":
        return "3.12"
    target = subprocess.run(["gfortran", "-dumpmachine"], capture_output=True, text=True, check=True,
                            env=child_environment()).stdout
    return f"cpython-3.12-macos-{'aarch64' if target.startswith(('aarch64', 'arm64')) else 'x86_64'}-none"


def build(item: ExternalItem, tools_dir: Path | None = None) -> list[str]:
    """Run the item's build commands in its folder; returns them. Filled in: {tools}, {folder}, {repo}; {python},
    ADROIT's own interpreter, and {arch}, its architecture, so that a tool's environment and compiled code match it;
    {fortran_python} (``fortran_python``) for an environment with a Fortran extension.

    Raises:
        subprocess.CalledProcessError: if a command fails.
    """
    tools = tools_dir or get_settings().tools_dir
    folder = fetch.folder_of(item, tools_dir)
    from adroit.core.config import PROJECT_ROOT
    fill = {"tools": tools, "folder": folder, "repo": PROJECT_ROOT, "python": sys.executable,
            "arch": platform.machine()}
    if any("{fortran_python}" in c for c in item.build):
        fill["fortran_python"] = fortran_python()
    commands = [c.format(**fill) for c in item.build]
    for command in commands:
        subprocess.run(command, shell=True, cwd=folder, check=True, env=child_environment())   # no credential (AL3-27)
    return commands


def _act(item: ExternalItem, present: bool, fetch_missing: bool, tools_dir: Path | None) -> tuple[bool, str]:
    """(present afterwards, what was done or must be done) for one item."""
    if present:
        return True, "present"
    if item.obtain is Obtain.pip:
        return False, f"install the Python package {item.source} into the environment (uv add {item.source})"
    if item.obtain is Obtain.manual:                 # its folder as configured (ADROIT_DATA_DIR: PR23-01)
        return False, f"{' '.join(item.manual_steps.split())} With this configuration the folder is " \
                      f"{fetch.folder_of(item, tools_dir)}."
    if not fetch_missing:
        return False, "missing: run `adroit setup --fetch`"
    try:                                         # one item's failure must not stop the others being fetched
        fetch.fetch(item.name, Manifest(tools=[item]), tools_dir)
        if item.build:
            build(item, tools_dir)
            return True, "fetched and built"
    except (subprocess.CalledProcessError, OSError, RuntimeError, ValueError) as error:
        return False, (f"fetching or building failed ({type(error).__name__}: {' '.join(str(error).split())[:300]}); "
                       "see the output above, then rerun `adroit setup --fetch`")
    notes = " ".join(item.note.split())
    return True, "fetched" + (f"; build by hand: {notes}" if notes else "")


def run(manifest: Manifest | None = None, fetch_missing: bool = False, only: str | None = None,
        milestone: str | None = None, tools_dir: Path | None = None) -> list[ItemStatus]:
    """Look at (and, with ``fetch_missing``, fetch) every item, or the one named, or a milestone's."""
    manifest = manifest or load_manifest()
    kinds = {item.name: "tool" for item in manifest.tools} | {item.name: "data" for item in manifest.data}
    items = [i for i in manifest.items() if (only is None or i.name == only)
             and (milestone is None or milestone in i.used_in)]
    if only is not None and not items:
        raise KeyError(f"no item {only!r} in the manifest")
    out = []
    for item in items:
        present, action = _act(item, _present(item, tools_dir), fetch_missing, tools_dir)
        folder = "" if item.obtain is Obtain.pip else str(fetch.folder_of(item, tools_dir))
        out.append(ItemStatus(name=item.name, kind=kinds[item.name], obtain=item.obtain, present=present,
                              required=item.required, folder=folder, licence=item.licence, used_in=item.used_in, role=item.role,
                              action=action))
    return out


ROSETTA = ("**Warning: ADROIT's Python runs under Rosetta** (x86_64 on Apple Silicon). DIAMX's JAX needs AVX "
           "instructions, which Rosetta does not provide, so the xenon likelihoods cannot run; use a native arm64 "
           "Python (docs/installation.md: an x86_64 uv chooses an x86_64 Python).")


def under_rosetta() -> bool:
    """Whether this process is x86_64 code translated by Rosetta on Apple Silicon: the interpreter's own architecture
    first (an arm64 Python is native), then macOS's ``sysctl.proc_translated`` asked from this process
    (``_translated``). The auditor's CO recheck, CR-07 (2026-10-26): it had been asked of a ``sysctl`` child, whose own
    translation (a universal binary launched as x86_64) was taken for the native parent's."""
    if sys.platform != "darwin" or platform.machine() == "arm64":
        return False
    return _translated()


def _translated() -> bool:
    """``sysctl.proc_translated`` of this process (``sysctlbyname``); False where it cannot be read (an Intel Mac
    has no such key: nothing is translated there)."""
    import ctypes
    import ctypes.util
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c"))
        value, size = ctypes.c_int(0), ctypes.c_size_t(ctypes.sizeof(ctypes.c_int))
        if libc.sysctlbyname(b"sysctl.proc_translated", ctypes.byref(value), ctypes.byref(size), None, 0) != 0:
            return False
    except (OSError, AttributeError, TypeError):
        return False
    return value.value == 1


TRUST = ("**Trust:** everything in the tools folder is run as code: external programs are executed and UFO "
         "models are imported by Python. Install items only from the sources listed here.")


def report(statuses: list[ItemStatus]) -> str:
    """The state of every item, what the user must still do, and every licence.

    Required items are needed to run ADROIT; optional ones are test references,
    cross-checks and opt-in extras (DM8's numerical cross-check).
    """
    needed = [s for s in statuses if s.required]
    missing = [s for s in needed if not s.present]
    optional = [s for s in statuses if not s.required and not s.present]
    verdict = "ADROIT has everything it needs." if not missing else f"{len(missing)} required item(s) missing."
    lines = ["# ADROIT's external tools and data", "",
             f"Required: {len(needed) - len(missing)} of {len(needed)} present. {verdict} "
             f"Optional: {sum(s.present for s in statuses if not s.required)} of "
             f"{len(statuses) - len(needed)} present.", "", *([ROSETTA, ""] if under_rosetta() else []), TRUST, "",
             "| item | kind | how | needed | state | used in | licence |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {s.name} | {s.kind} | {s.obtain.value} | {'yes' if s.required else 'optional'} | "
              f"{'present' if s.present else 'MISSING'} | {', '.join(s.used_in)} | "
              f"{s.licence or 'not confirmed: read it before depending on the item'} |" for s in statuses]
    if missing:
        lines += ["", "## Still to do (required)", ""] + [f"- **{s.name}**: {s.action}" for s in missing]
    if optional:
        lines += ["", "## Optional, not present", ""] + [f"- **{s.name}**: {s.action}" for s in optional]
    built = [s for s in statuses if s.action.startswith("fetched")]
    if built:
        lines += ["", "## Fetched in this run", ""] + [f"- **{s.name}** ({s.folder}): {s.action}" for s in built]
    return "\n".join(lines) + "\n"
