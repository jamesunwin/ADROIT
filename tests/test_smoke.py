"""Smoke test: the package and every subpackage import cleanly."""

import importlib

import adroit


def test_package_imports() -> None:
    assert adroit.__version__


def test_the_version_and_licence_are_stated_once_and_agree() -> None:
    import tomllib
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    assert adroit.__version__ == project["version"]
    assert project["license"] == "BSD-3-Clause" and (root / "LICENSE").read_text().startswith("BSD 3-Clause License")


def test_subpackages_import() -> None:
    for sub in [
        "core", "physics", "experiments", "statistics", "external", "library",
        "library.interactions", "inference", "constraints", "retrieval", "agents",
        "orchestrator",
    ]:
        importlib.import_module(f"adroit.{sub}")


def test_settings_load_without_env_file() -> None:
    from adroit.core.config import get_settings

    settings = get_settings()
    assert settings.data_dir.name == "data"
