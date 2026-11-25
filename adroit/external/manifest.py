"""The manifest of external tools and data: what is needed, and how it is obtained.

The manifest (``tools.yaml``) is the single list of everything the system
uses that it does not contain. Each entry says how it is obtained:

- ``pip`` or ``git``: the system can fetch it;
- ``download``: the system downloads the listed ``files`` (URLs), for data
  releases that are plain files;
- ``manual``: the source blocks automated downloads, so the user is told what
  to download and where to put it (``manual_steps``).

Fetched items live in the tools directory (``Settings.tools_dir``), each in
its own ``folder``; manual ones in ``external/manual/<folder>`` of the data folder
(``ADROIT_DATA_DIR``; by default the checkout's ``data/``).
:mod:`adroit.external.fetch` finds and fetches them.

The set-up command of the public release reads this manifest (build plan,
DM11). Until then it is the record of what was installed by hand.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field, model_validator

from adroit.core.state import StrictModel

MANIFEST = Path(__file__).with_name("tools.yaml")


class Obtain(str, Enum):
    """How an external tool or data set is obtained."""

    pip = "pip"
    git = "git"
    download = "download"
    manual = "manual"


class ExternalItem(StrictModel):
    """One external tool or data set (see the module docstring)."""

    name: str
    purpose: str
    obtain: Obtain
    source: str
    version: str = ""
    licence: str = ""
    reference: str = ""
    used_in: list[str] = Field(default_factory=list)
    role: str = ""
    note: str = ""
    manual_steps: str = ""
    folder: str = ""                                  # where it lives once fetched
    repo_folder: str = ""                              # an existing legacy checkout, if tools is absent
    files: list[str] = Field(default_factory=list)    # the URLs of a download item
    build: list[str] = Field(default_factory=list)    # shell commands run in its folder after fetching
    present_if: str = ""                              # a glob in its folder that shows it is built
    user_agent: str = ""                              # for a server that refuses ADROIT's own (HEPData's front end)
    required: bool = True                             # False: a test reference, cross-check or opt-in extra

    @model_validator(mode="after")
    def _an_item_says_how_to_get_it(self) -> "ExternalItem":
        if self.obtain is Obtain.manual and not self.manual_steps.strip():
            raise ValueError(f"{self.name}: a manual item needs manual_steps")
        if self.obtain is Obtain.download and not self.files:
            raise ValueError(f"{self.name}: a download item needs files")
        return self

    @property
    def automatic(self) -> bool:
        """Whether the system can fetch the item without the user."""
        return self.obtain is not Obtain.manual

    @property
    def licence_confirmed(self) -> bool:
        """Whether the item's licence has been read and recorded."""
        return bool(self.licence.strip())


class Manifest(StrictModel):
    """Every external tool and data set."""

    tools: list[ExternalItem] = Field(default_factory=list)
    data: list[ExternalItem] = Field(default_factory=list)

    def items(self) -> list[ExternalItem]:
        """Tools, then data."""
        return [*self.tools, *self.data]

    def manual(self) -> list[ExternalItem]:
        """The items the user must fetch by hand."""
        return [item for item in self.items() if not item.automatic]

    def item(self, name: str) -> ExternalItem:
        """The item called ``name``.

        Raises:
            KeyError: if there is none.
        """
        for item in self.items():
            if item.name == name:
                return item
        raise KeyError(f"no item {name!r} in the manifest")

    def for_milestone(self, milestone: str) -> list[ExternalItem]:
        """The items a milestone uses, e.g. ``"DM3"``."""
        return [item for item in self.items() if milestone in item.used_in]


def load_manifest(path: str | Path = MANIFEST) -> Manifest:
    """Read and validate the manifest.

    The file is read on every call so edits are visible immediately. Only the
    validated parse of identical contents is reused; callers receive a deep copy.

    Raises:
        ValueError: if two items share a name.
    """
    return _parse_manifest(Path(path).read_text(encoding="utf-8")).model_copy(deep=True)


@lru_cache(maxsize=8)
def _parse_manifest(contents: str) -> Manifest:
    """Validate one exact manifest content, independently of its location."""
    manifest = Manifest.model_validate(yaml.safe_load(contents))
    names = [item.name for item in manifest.items()]
    repeated = sorted({n for n in names if names.count(n) > 1})
    if repeated:
        raise ValueError(f"items appear twice in the manifest: {repeated}")
    return manifest


def manual_instructions(manifest: Manifest) -> str:
    """What the user is asked to download by hand, as plain text (empty if nothing)."""
    lines = []
    for item in manifest.manual():
        lines.append(f"{item.name}: {' '.join(item.manual_steps.split())}")
    return "\n".join(lines)
