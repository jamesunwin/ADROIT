"""Which ADROIT the workbench is running (the owner's report of 2026-10-23: testing an old checkout must be apparent).

The version, the git revision, the branch and whether the checkout had uncommitted changes are read once, when the
workbench starts (``app.build_pages``), so the page shows the code that was loaded, not a checkout changed since. The
revision is read locally: ``git`` with optional locks off (nothing is written, nothing is fetched), else the
repository's own files (``HEAD``, its ref, ``packed-refs``); without either it says the revision is unknown. Shown in
small type at the end of every page's menu and in full on ``/about``.
"""
from __future__ import annotations

import functools
import platform
import subprocess
from pathlib import Path

from nicegui import ui

from adroit.core.config import PROJECT_ROOT
from adroit.core.state import StrictModel

UNKNOWN = "unknown"
GIT_TIMEOUT_S = 3.0


class BuildInfo(StrictModel):
    """The running application: its version, its checkout and the revision read when it started."""
    version: str
    revision: str = ""                 # the full commit hash; "" when unknown
    branch: str = ""                   # "" on a detached head or when unknown
    committed: str = ""                # the commit's date (ISO), when git could say
    dirty: bool | None = None          # uncommitted changes to tracked files; None when not known
    checkout: str
    python: str
    source: str                        # "git", "repository files" or "none"
    note: str = ""                     # why the revision is unknown or incomplete

    @property
    def short(self) -> str:
        """The revision's first 7 characters, "+changes" when the checkout was edited; "unknown" without one."""
        if not self.revision:
            return UNKNOWN
        return self.revision[:7] + ("+changes" if self.dirty else "")


def _git(root: Path, *args: str) -> str:
    """One read-only git query in ``root`` (optional locks off, no prompt); raises OSError or CalledProcessError."""
    from adroit.core.config import child_environment
    env = child_environment({"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"})   # no credential (AL3-27)
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=GIT_TIMEOUT_S,
                          env=env, check=True)
    return done.stdout.strip()


def _from_git(root: Path) -> dict | None:
    """The revision, branch, date and dirtiness from git; None if git is missing or ``root`` is not a checkout."""
    try:
        revision = _git(root, "rev-parse", "HEAD")
    except (OSError, subprocess.SubprocessError):
        return None
    found = {"revision": revision, "source": "git"}
    for key, args in (("branch", ("symbolic-ref", "--short", "-q", "HEAD")),
                      ("committed", ("log", "-1", "--format=%cI", "HEAD"))):
        try:
            found[key] = _git(root, *args)
        except (OSError, subprocess.SubprocessError):
            found[key] = ""
    try:
        found["dirty"] = bool(_git(root, "status", "--porcelain", "--untracked-files=no"))
    except (OSError, subprocess.SubprocessError):
        found["note"] = "whether the checkout has uncommitted changes could not be read"
    return found


def _git_dir(root: Path) -> Path | None:
    """The checkout's git directory: ``.git`` itself, or the folder a worktree's ``.git`` file names."""
    marker = root / ".git"
    if marker.is_dir():
        return marker
    if marker.is_file():
        text = marker.read_text(errors="replace").strip()
        if text.startswith("gitdir:"):
            path = Path(text.split(":", 1)[1].strip())
            return path if path.is_absolute() else (root / path).resolve()
    return None


def _from_files(root: Path) -> dict | None:
    """The revision and branch from the repository's files (no git needed); None if they cannot be read."""
    try:
        git_dir = _git_dir(root)
        if git_dir is None:
            return None
        head = (git_dir / "HEAD").read_text().strip()
        common = git_dir
        if (git_dir / "commondir").is_file():
            common = (git_dir / (git_dir / "commondir").read_text().strip()).resolve()
        if not head.startswith("ref:"):
            return {"revision": head, "source": "repository files"}
        ref = head.split(":", 1)[1].strip()
        for base in (git_dir, common):
            if (base / ref).is_file():
                return {"revision": (base / ref).read_text().strip(), "branch": ref.removeprefix("refs/heads/"),
                        "source": "repository files"}
        packed = common / "packed-refs"
        for line in packed.read_text().splitlines() if packed.is_file() else []:
            if line.endswith(" " + ref):
                return {"revision": line.split()[0], "branch": ref.removeprefix("refs/heads/"),
                        "source": "repository files"}
    except OSError:
        return None
    return None


def read_build(root: Path = PROJECT_ROOT) -> BuildInfo:
    """What is running from ``root``: the version, and the revision from git, else from the repository's files,
    else none (the note says why)."""
    from adroit import __version__
    found = _from_git(root) or _from_files(root)
    if found is None:
        found = {"source": "none", "note": "no git revision: git is unavailable and the folder holds no readable "
                                           "repository"}
    elif found["source"] == "repository files":
        found.setdefault("note", "read from the repository's files (git unavailable); uncommitted changes unknown")
    return BuildInfo(version=__version__, checkout=str(root), python=platform.python_version(), **found)


@functools.cache
def build() -> BuildInfo:
    """The running application's build, read once (``app.build_pages`` reads it when the workbench starts)."""
    return read_build()


def footer_tag() -> None:
    """The menu's small "ADROIT 1.0.0 · 3012843" link to ``/about``, with the checkout on hover."""
    info = build()
    with ui.link(f"v{info.version} · {info.short}", "/about").classes("text-xs text-gray-400 no-underline") \
            .mark("build_tag"):
        ui.tooltip(f"running from {info.checkout}")


def page() -> None:
    """``/about``: the version, revision, branch, date, uncommitted changes and checkout of the running workbench."""
    from adroit.ui.pages import header
    info = build()
    header("About this workbench", "Which ADROIT is running: its version and the git revision of the checkout it was "
           "started from (read when it started). Compare it with the revision you mean to test.")
    changes = {True: "yes (tracked files differ from the commit)", False: "no", None: "not known"}[info.dirty]
    rows = [("Version", info.version), ("Revision", info.revision or UNKNOWN), ("Branch", info.branch or "—"),
            ("Committed", info.committed or "—"), ("Uncommitted changes", changes),
            ("Checkout", info.checkout), ("Python", info.python), ("Read from", info.source)]
    with ui.card().classes("w-full").mark("about"):
        for name, value in rows:
            with ui.row().classes("items-baseline gap-3 no-wrap"):
                ui.label(name).classes("w-48 text-gray-600")
                ui.label(value).classes("font-mono text-sm break-all")
        if info.note:
            ui.label(info.note).classes("text-sm text-amber-800")
