"""Find and fetch the items of the manifest: the only place that downloads them.

An automatic item (``git`` or ``download``) lives in its own folder in the
tools directory (``Settings.tools_dir``, outside the repository). A manual
item lives in ``external/manual/<folder>`` of the data folder
(``Settings.data_dir``: the checkout's ``data/`` unless ``ADROIT_DATA_DIR``
moves it), where the user puts it. Nothing fetched here is ever committed
(owner's decisions of 2026-09-29).
"""

from __future__ import annotations

import ssl
import subprocess
import time
from functools import cache
from pathlib import Path

import requests
import truststore
from requests.adapters import HTTPAdapter

from adroit.core.config import child_environment
from adroit.core.config import PROJECT_ROOT, get_settings
from adroit.external.manifest import ExternalItem, Manifest, Obtain, load_manifest

MANUAL_DIR = PROJECT_ROOT / "data" / "external" / "manual"   # the checkout's: the default, and a legacy lookup
USER_AGENT = "adroit (research software; fetches public data releases)"
PAUSE_S = 3.0                      # between requests to one server
RETRY_CODES = (406, 429, 503)


def manual_dir() -> Path:
    """Where manual items live: ``external/manual`` in the configured data folder, so that ``ADROIT_DATA_DIR`` moves
    them with the rest of the data (the release audit's PR23-01, 2026-10-23: they stayed in the checkout's)."""
    data = get_settings().data_dir
    return MANUAL_DIR if data == PROJECT_ROOT / "data" else data / "external" / "manual"


def folder_of(item: ExternalItem, tools_dir: Path | None = None) -> Path:
    """Where the item lives: its folder in the tools directory, or in the manual folder (``manual_dir``; where the data
    folder is moved and an item is still in the checkout's manual folder only, there)."""
    name = item.folder or item.name
    if item.obtain is Obtain.manual:
        preferred, legacy = manual_dir() / name, MANUAL_DIR / name
        return legacy if preferred != legacy and not preferred.exists() and legacy.is_dir() else preferred
    preferred = (tools_dir or get_settings().tools_dir) / name
    if tools_dir is None and not preferred.exists() and item.repo_folder:
        legacy = PROJECT_ROOT / item.repo_folder
        if legacy.is_dir():
            return legacy
    return preferred


class MissingInput(RuntimeError):
    """An external input (a data release, a tool) that is not installed. Its message says what is missing and how to
    obtain it (``how_to_get``); the command line reports it without a traceback (the release audit's PR23-02,
    2026-10-23)."""


def how_to_get(name: str, manifest: Manifest | None = None) -> str:
    """How to obtain the manifest item ``name``: the setup command that fetches (and builds) it, or its manual steps
    and the folder they go in."""
    item = (manifest or load_manifest()).item(name)
    if item.obtain is Obtain.manual:
        return f"{' '.join(item.manual_steps.split())} With this configuration the folder is {folder_of(item)}."
    if item.obtain is Obtain.pip:
        return f"install the Python package {item.source} into the environment (uv add {item.source})"
    return f"run `adroit setup --fetch --only '{name}'`" + (" (it fetches and builds it)" if item.build else "")


def local_name(url: str) -> str:
    """The path a downloaded file takes in its folder.

    Files of an arXiv data release keep their path below ``anc/``; a URL with a
    fragment (``…/csv#lz_sdn.csv``) takes the fragment's name (the fragment is
    never sent to the server); any other file keeps its base name.
    """
    if "#" in url:
        return url.rsplit("#", 1)[1]
    return url.split("/anc/", 1)[1] if "/anc/" in url else url.rstrip("/").rsplit("/", 1)[-1]


def is_present(item: ExternalItem, tools_dir: Path | None = None) -> bool:
    """Whether the item has been fetched (every file, for a download item; its ``present_if``, if given)."""
    folder = folder_of(item, tools_dir)
    if item.present_if:
        return any(folder.glob(item.present_if))
    if item.obtain is Obtain.download:
        return all((folder / local_name(url)).is_file() for url in item.files)
    return folder.is_dir() and any(folder.iterdir())


def locate(name: str, manifest: Manifest | None = None, tools_dir: Path | None = None) -> Path | None:
    """The folder of the item called ``name``, or None if it has not been fetched."""
    item = (manifest or load_manifest()).item(name)
    return folder_of(item, tools_dir) if is_present(item, tools_dir) else None


class _SystemTrust(HTTPAdapter):
    """HTTPS verified against the operating system's trust store (``truststore``), as a browser or curl does, not
    certifi's bundle: a server that omits its intermediate certificate (Harvard's f_eff host, 2026-10-12) then
    still verifies where the system can complete the chain."""

    def init_poolmanager(self, *args, **kwargs):
        """The pool's TLS context is the system's."""
        kwargs["ssl_context"] = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        return super().init_poolmanager(*args, **kwargs)


@cache
def _session() -> requests.Session:
    session = requests.Session()
    session.mount("https://", _SystemTrust())
    return session


def _get(url: str, target: Path, attempts: int = 5, user_agent: str = "") -> None:
    """Download one file, waiting and retrying when the server asks for a slower pace.

    arXiv asks for at most one request every three seconds and answers a
    client it does not accept with HTTP 406 (it refuses Python's urllib even
    when ``requests`` succeeds), or a fast one with 429 or 503.
    """
    for attempt in range(attempts):
        response = _session().get(url.split("#", 1)[0], headers={"User-Agent": user_agent or USER_AGENT}, timeout=60)
        if response.status_code == 200:
            target.write_bytes(response.content)
            return
        if response.status_code not in RETRY_CODES or attempt == attempts - 1:
            response.raise_for_status()
            raise RuntimeError(f"{url}: HTTP {response.status_code}")
        time.sleep(PAUSE_S * 2 ** attempt)


def _download(item: ExternalItem, folder: Path) -> None:
    """Download each missing file of a download item, one every few seconds."""
    for url in item.files:
        target = folder / local_name(url)
        if target.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        _get(url, target, user_agent=item.user_agent)
        time.sleep(PAUSE_S)


def _clone(item: ExternalItem, folder: Path) -> None:
    """Clone a git item, at its recorded version if it has one. A clone already there (whose build failed, so the
    item is not yet present) is reused."""
    if not (folder / ".git").is_dir():
        subprocess.run(["git", "clone", "--quiet", item.source, str(folder)], check=True, env=child_environment())
    if item.version:
        subprocess.run(["git", "-C", str(folder), "checkout", "--quiet", item.version], check=True,
                       env=child_environment())


def fetch(name: str, manifest: Manifest | None = None, tools_dir: Path | None = None) -> Path:
    """Fetch the item called ``name`` if it is not already present, and return its folder.

    Raises:
        ValueError: for a pip item (installed with the environment) or a manual
            item (the user must fetch it; the message says how).
    """
    item = (manifest or load_manifest()).item(name)
    folder = folder_of(item, tools_dir)
    if is_present(item, tools_dir):
        return folder
    if item.obtain is Obtain.download:
        _download(item, folder)
    elif item.obtain is Obtain.git:
        _clone(item, folder)
    elif item.obtain is Obtain.pip:
        raise ValueError(f"{name} is a Python package: install {item.source} into the environment")
    else:
        raise ValueError(f"{name} must be fetched by hand: {' '.join(item.manual_steps.split())}")
    return folder
