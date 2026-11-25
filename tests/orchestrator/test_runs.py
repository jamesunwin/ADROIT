import pytest

from adroit.orchestrator import runs


def test_lists_and_values_parse() -> None:
    assert runs.parse_list(" a, b ,,c ") == ["a", "b", "c"]
    assert runs.parse_values("c1_s=1e-6, m_med = 100") == {"c1_s": 1e-6, "m_med": 100.0}
    with pytest.raises(ValueError):
        runs.parse_values("c1_s")
    with pytest.raises(ValueError):
        runs.parse_values("c1_s=big")


def test_a_slug_is_a_safe_folder_name() -> None:
    assert runs.slug("LZ extended window (2026)") == "LZ_extended_window_2026"
    assert runs.slug("///") == "run"
