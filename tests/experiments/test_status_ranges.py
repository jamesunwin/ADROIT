"""Validated ranges (experiments.status): a module validated structure by structure has an SI range from its
elastic isoscalar O₁ table, and no SD range without an elastic O₄ one (minor after R6)."""

from adroit.experiments import status


def test_the_extended_window_takes_its_si_range_from_its_validated_o1_table() -> None:
    assert status.validated_range("LZ extended window (2026)", "SI") == (400.0, 4000.0)
    assert status.validated_range("LZ extended window (2026)", "SD-proton") is None
    assert status.validated_range("LZ WS2022+WS2024", "SI") == (8.8716, 92.0743)       # an SI entry still decides
    assert status.structure_range("LZ WS2022+WS2024", "SI") is None                     # another module's structures
