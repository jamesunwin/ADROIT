"""Project settings: environment variables."""

from __future__ import annotations


def test_env_reads_the_project_prefix_only(monkeypatch) -> None:
    from adroit.core.config import env
    monkeypatch.delenv("ADROIT_MAX_WORKERS", raising=False)
    assert env("MAX_WORKERS", "d") == "d"
    # the parent project's variables are not read: the two systems stay separate
    monkeypatch.setenv("NOMOTHETICA" + "_MAX_WORKERS", "3")
    assert env("MAX_WORKERS", "d") == "d"
    monkeypatch.setenv("ADROIT_MAX_WORKERS", "5")
    assert env("MAX_WORKERS") == "5"


def test_external_tools_are_built_in_a_path_without_spaces(monkeypatch) -> None:
    from adroit.core import config
    monkeypatch.delenv("ADROIT_TOOLS_DIR", raising=False)
    config.get_settings.cache_clear()
    assert " " not in config.get_settings().tools_dir.name
    assert config.get_settings().tools_dir.name == "agentic-dm-tools"
    monkeypatch.setenv("ADROIT_TOOLS_DIR", "/tmp/elsewhere")
    config.get_settings.cache_clear()
    assert str(config.get_settings().tools_dir) == "/tmp/elsewhere"
    config.get_settings.cache_clear()
