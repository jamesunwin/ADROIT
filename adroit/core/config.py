"""Project configuration loaded from environment variables / .env file.

Read here: ``ANTHROPIC_API_KEY``, ``ANTHROPIC_MODEL`` / ``ANTHROPIC_MODEL_HARD``
(the default and hard-step models), ``ADROIT_EMBEDDINGS`` (``hash`` or
``st``), and the directory overrides ``ADROIT_RUNS_DIR``,
``ADROIT_DATA_DIR`` and ``ADROIT_PROJECTS_DIR`` (used by drills and demos
to point a whole process at scratch directories), and ``ADROIT_TOOLS_DIR``
(where compiled external tools are built; default ``~/agentic-dm-tools``).

Every project variable is read through :func:`env`: the process environment first, then the project's ``.env``,
which is read and never exported (``dotenv_file``).

**Credentials** (the security addendum to the audit loop's cycle 3, 2026-11-16: AL3-25, AL3-27, AL3-29). The two
provider keys and the two provider endpoints (``PROVIDER_VARIABLES``) are read once, by :func:`get_settings`, from the
environment or ``.env``; a key is stripped of surrounding whitespace and kept as a ``SecretStr``. Then every
credential-named variable (``CREDENTIAL``) and the endpoints are removed from this process's environment, so that no
program ADROIT starts (a solver, a build, a fetched package's script) inherits them; ADROIT's own runs started by
the workbench are given them back explicitly (:func:`provider_environment`), and every launch site passes
:func:`child_environment`, which holds none of them.

A directory setting (``DIRECTORIES``) is read once, as an absolute path: a
relative one against the folder the process was started in. A run the process
launches is given those absolute paths (:func:`launched`), since it starts in
another folder, and keeps them when it is resumed (an operating-conditions
audit's IE-01, 2026-11-10: a relative directory had named one folder in the
workbench and another in the run it launched).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import os
import re

from dotenv import dotenv_values
from pydantic import BaseModel, SecretStr

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PREFIX = "ADROIT_"


# a variable whose name says it holds a credential: never given to a program ADROIT starts
CREDENTIAL = re.compile(r"API_KEY|(^|_)TOKEN$|SECRET|PASSWORD|CREDENTIAL", re.I)
# the providers' keys and endpoints: read once into the settings, then kept out of the environment
PROVIDER_VARIABLES = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_BASE_URL", "OPENAI_BASE_URL")


def dotenv_file() -> dict[str, str]:
    """The project's ``.env`` (``PROJECT_ROOT / ".env"``), read and never exported: its lines reach ADROIT's settings
    and no program it starts (AL3-27: ``load_dotenv`` had put every line, keys included, in the environment)."""
    return dict(_dotenv_at(str(PROJECT_ROOT / ".env")))


@lru_cache(maxsize=4)
def _dotenv_at(path: str) -> tuple[tuple[str, str], ...]:
    found = dotenv_values(path) if Path(path).is_file() else {}
    return tuple((k, v) for k, v in found.items() if v is not None)


def variable(name: str) -> str | None:
    """A variable from the environment, else from the project's ``.env`` (the environment wins, as before)."""
    value = os.environ.get(name)
    return dotenv_file().get(name) if value is None else value


def env(name: str, default: str = "") -> str:
    """Read ``ADROIT_<name>``: the environment first, then the project's ``.env``.

    Args:
        name: the variable without its prefix, e.g. ``"RUNS_DIR"``.
        default: returned when the variable is not set.
    """
    value = variable(ENV_PREFIX + name)
    return default if value is None else value


class Settings(BaseModel):
    """Runtime settings for adroit.

    Values are read from a `.env` file at the project root (never
    committed to git) or from process environment variables.
    """

    anthropic_api_key: SecretStr = SecretStr("")      # read with .get_secret_value() where a client is built (AL3-29)
    openai_api_key: SecretStr = SecretStr("")
    anthropic_base_url: str = ""                      # the endpoint a variable names ("": the provider's own; AL3-26)
    openai_base_url: str = ""
    data_dir: Path = PROJECT_ROOT / "data"
    runs_dir: Path = PROJECT_ROOT / "runs"
    # Default LLM (Sonnet-class); hard steps may override to the Opus-class model.
    # Confirmed with the collaborator 2026-07: claude-sonnet-5 ($3/$15 per 1M,
    # intro $2/$10 through 2026-08-31) and claude-opus-4-8 ($5/$25 per 1M).
    llm_model: str = "claude-sonnet-5"
    llm_model_hard: str = "claude-opus-4-8"
    llm_cache_path: Path = PROJECT_ROOT / "runs" / "llm_cache.sqlite"
    # Literature-index embedding backend: "hash" (deterministic, offline, the CI
    # default) or "st" (local sentence-transformers; optional extras).
    embedding_backend: str = "hash"
    # Workbench project store (gitignored, like runs/).
    projects_dir: Path = PROJECT_ROOT / "projects"
    model_library_dir: Path = PROJECT_ROOT / "projects" / "model_library"
    experimental_library_dir: Path = PROJECT_ROOT / "projects" / "experimental_library"
    # Where compiled external tools are built. It must be a path without
    # spaces: Makefile-based tools fail otherwise (docs/dm0_tool_audit.md).
    tools_dir: Path = Path.home() / "agentic-dm-tools"
    # threads each numerical subprocess (DIAMX's JAX/BLAS stack) may use; its pools obey only their own variables
    numerical_threads: int = 2
    # the propagation model for charged cosmic-ray bounds (constraints.propagation): conservative, central or aggressive
    cr_propagation: str = "conservative"
    # the halo every Track 1 point is evaluated over (parameter_space.halo_region): "preset", the owner's working
    # region (the default), or "published", each experiment's published halo (the reproduction mode)
    halo_region: str = "preset"
    # worker processes for a Track 1 scan's points (``ADROIT_SCAN_WORKERS``; default: this machine's cores less two, at
    # least one). The owner, 2026-11-22: scans had been capped at two, leaving most cores idle
    scan_workers: int = 1


def _scan_workers() -> int:
    """``ADROIT_SCAN_WORKERS`` as a positive integer, else this machine's cores less two (at least one)."""
    value = env("SCAN_WORKERS", "").strip()
    if not value:
        return max(1, (os.cpu_count() or 2) - 2)
    try:
        workers = int(value)
    except ValueError:
        raise ValueError(f"ADROIT_SCAN_WORKERS must be a positive whole number, not {value!r}") from None
    if workers < 1:
        raise ValueError(f"ADROIT_SCAN_WORKERS must be at least 1, not {workers}")
    return workers


# the directory settings, by their variable (``ADROIT_<name>``) and their field (module docstring)
DIRECTORIES = {"PROJECTS_DIR": "projects_dir", "MODEL_LIBRARY_DIR": "model_library_dir",
               "EXPERIMENTAL_LIBRARY_DIR": "experimental_library_dir", "TOOLS_DIR": "tools_dir",
               "RUNS_DIR": "runs_dir", "DATA_DIR": "data_dir"}


def _directory(name: str, default: Path) -> Path:
    """``ADROIT_<name>`` (else ``default``) as an absolute path: a relative one is joined to this process's working
    folder, as the operating system would read it here (module docstring)."""
    return Path(env(name, str(default))).absolute()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once and cache them for the process lifetime; then keep the credentials out of the environment
    (module docstring)."""
    projects = _directory("PROJECTS_DIR", PROJECT_ROOT / "projects")
    settings = Settings(
        anthropic_api_key=SecretStr((variable("ANTHROPIC_API_KEY") or "").strip()),
        openai_api_key=SecretStr((variable("OPENAI_API_KEY") or "").strip()),
        anthropic_base_url=(variable("ANTHROPIC_BASE_URL") or "").strip(),
        openai_base_url=(variable("OPENAI_BASE_URL") or "").strip(),
        llm_model=variable("ANTHROPIC_MODEL") or "claude-sonnet-5",
        llm_model_hard=variable("ANTHROPIC_MODEL_HARD") or "claude-opus-4-8",
        embedding_backend=env("EMBEDDINGS", "hash"),
        projects_dir=projects,
        model_library_dir=_directory("MODEL_LIBRARY_DIR", projects / "model_library"),
        experimental_library_dir=_directory("EXPERIMENTAL_LIBRARY_DIR", projects / "experimental_library"),
        tools_dir=_directory("TOOLS_DIR", Path.home() / "agentic-dm-tools"),
        # Drills and demos point a whole process at scratch runs/data directories.
        runs_dir=_directory("RUNS_DIR", PROJECT_ROOT / "runs"),
        data_dir=_directory("DATA_DIR", PROJECT_ROOT / "data"),
        cr_propagation=env("CR_PROPAGATION", "conservative"),
        halo_region=env("HALO_REGION", "preset"),
        scan_workers=_scan_workers(),
    )
    scrub()
    return settings


def scrub() -> None:
    """Remove every credential-named variable and the provider endpoints from this process's environment, so that no
    program it starts inherits them (AL3-27: every child had, 32 launch sites, some of them in files whose bytes the
    limit tables fingerprint). The settings have read them first."""
    for name in [n for n in os.environ if CREDENTIAL.search(n) or n in PROVIDER_VARIABLES]:
        os.environ.pop(name, None)


def child_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The environment for a program ADROIT starts: this process's with ``extra`` added, then without credentials or
    provider endpoints, whatever ``extra`` held (AL3-27). ADROIT's own runs that the workbench starts, which may make
    paid requests, add :func:`provider_environment` after it."""
    merged = {**os.environ, **(extra or {})}
    return {k: v for k, v in merged.items() if not CREDENTIAL.search(k) and k not in PROVIDER_VARIABLES}


def run_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The environment of an ADROIT run the workbench starts (a command, its runner, a batch): without credentials,
    then the providers' keys and endpoints given back explicitly, since such a run may make paid requests (AL3-27)."""
    return {**child_environment(extra), **provider_environment()}


def provider_environment() -> dict[str, str]:
    """The providers' keys and endpoints, for ADROIT's own runs that the workbench starts and that may make paid
    requests: the only children given them (AL3-27). Each is given as this process holds it, an empty one too: the
    child's environment then wins over the project's ``.env`` (``variable``), so a key its parent was told not to use
    (exported empty) never reaches it from that file (the audit loop's AL4-05, 2026-11-16)."""
    settings = get_settings()
    return {"ANTHROPIC_API_KEY": settings.anthropic_api_key.get_secret_value(),
            "OPENAI_API_KEY": settings.openai_api_key.get_secret_value(),
            "ANTHROPIC_BASE_URL": settings.anthropic_base_url, "OPENAI_BASE_URL": settings.openai_base_url}


def secrets() -> list[tuple[str, str]]:
    """(variable, value) of every configured provider key, for redacting them from what a command prints (AL3-25)."""
    settings = get_settings()
    found = [("ANTHROPIC_API_KEY", settings.anthropic_api_key.get_secret_value()),
             ("OPENAI_API_KEY", settings.openai_api_key.get_secret_value())]
    return [(name, value) for name, value in found if len(value) >= 8]


def redacted(text: str) -> str:
    """``text`` with every configured key replaced by its variable's name (AL3-25)."""
    for name, value in secrets():
        text = text.replace(value, f"<{name}>")
    return text


def launched() -> dict[str, str]:
    """The directory settings a launched run is given, as ``ADROIT_<name>`` variables: this process's own, as absolute
    paths (module docstring)."""
    settings = get_settings()
    return {ENV_PREFIX + name: str(Path(getattr(settings, field)).absolute()) for name, field in DIRECTORIES.items()}
