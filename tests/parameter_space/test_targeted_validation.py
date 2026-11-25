"""The targeted count-ratio validation of 2026-11-24 (``data/halo_validation_points_targeted.yaml``, declared in
c254dca before its calculations; ``data/halo_count_ratio_targeted.yaml``, its result) and the count ratio's place in
the combined likelihood (the owner's plan of 2026-11-24, section 3)."""
from types import SimpleNamespace

import pytest

from adroit.parameter_space import halo_evaluation, halo_limits


@pytest.mark.needs("diamx")
@pytest.mark.parametrize("module, inside, outside", [
    ("LZ WS2022+WS2024", (50.0, 56.0, 88.6, 90.0), (40.0, 49.9, 95.0)),
    ("XENONnT SR0+SR1", (90.0, 96.8, 497.0, 1000.0), (85.0, 1001.0, 1200.0)),
])
def test_a_targeted_entry_is_used_only_inside_its_declared_masses(module, inside, outside) -> None:
    declared, _ = halo_limits.targeted_declaration()
    masses = declared["modules"][module]["SI"]
    found = halo_limits._targeted(module, "SI")
    assert found is not None and found[1] == (min(masses), max(masses)) and found[0] <= 0.15
    assert all(halo_limits.validated(module, "SI", m) == pytest.approx(found[0]) for m in inside)
    assert all(halo_limits.validated(module, "SI", m) is None for m in outside)     # never extrapolated


@pytest.mark.needs("diamx")
def test_a_targeted_entry_against_another_declaration_is_not_used() -> None:
    """The entry is bound to its declaration's sha256: a declaration changed after the calculation leaves it unused."""
    values, sha = halo_limits.targeted_declaration()
    data = halo_limits.targeted_validation()
    assert halo_limits._entry("LZ WS2022+WS2024", "SI", data, values, sha) is not None      # as declared
    assert halo_limits._entry("LZ WS2022+WS2024", "SI", data, values, "0" * 64) is None


@pytest.mark.needs("diamx")
def test_the_original_entries_are_unchanged_by_the_targeted_one() -> None:
    """The original validation of 2026-11-13 still reads as it did: LZ's and XENONnT's SI entries failed and stay
    unused, PandaX-4T's passed (``_usable`` reads the original alone)."""
    assert halo_limits._usable("LZ WS2022+WS2024", "SI") is None
    assert halo_limits._usable("XENONnT SR0+SR1", "SI") is None
    assert halo_limits._usable("PandaX-4T Run0+Run1", "SI") is not None


def test_a_count_ratio_limit_never_enters_the_combined_likelihood() -> None:
    """A direct-detection ratio taken with a count-ratio limit at the region's centre is a cut only: it is dropped from
    the ratios the combined likelihood reads (``halo_evaluation._nominal_cuts``; the owner's condition 6)."""
    result = SimpleNamespace(statistical_limits={"direct detection": object()},
                             ratios={"direct detection": 3.0, "CMB (Planck)": 0.2},
                             ratio_confidence_levels={"direct detection": 0.95}, ratio_sidedness={"direct detection": "two-sided"})
    result.model_copy = lambda update: SimpleNamespace(**{**vars(result), **update})
    cut = halo_evaluation._nominal_cuts(result, SimpleNamespace(approximate=lambda: True))
    assert "direct detection" not in cut.ratios and cut.ratios["CMB (Planck)"] == 0.2
    exact = halo_evaluation._nominal_cuts(result, SimpleNamespace(approximate=lambda: False))
    assert exact.ratios["direct detection"] == 3.0


def test_the_budget_goes_first_to_the_experiment_that_decided_the_point() -> None:
    """The reassessment of 2026-11-24 found a point's whole budget spent on XENONnT below its validated masses while
    LZ, which decided the point at the centre and has no current table there, got none. The decisive experiments
    (``halo_evaluation.deciding``, from the saved evaluation) now come first, then the rest by their tables."""
    import gzip
    import json
    from pathlib import Path
    from adroit.parameter_space.scan import PointResult
    from adroit.parameter_space.halo_evaluation import deciding
    data = json.load(gzip.open(Path(__file__).parents[1] / "fixtures" / "vector_dd_pending.json.gz"))
    saved = next(c for c in data["pending_crossings"] if abs(c["point"]["m_chi"] - 88.59) < 0.01)
    prefer = deciding(PointResult.model_validate(saved["evaluation"]))
    assert prefer == ("LZ WS2022+WS2024",)
    names = ["CRESST-III 2019", "XENONnT SR0+SR1", "LZ WS2022+WS2024", "PandaX-4T Run0+Run1"]
    order = halo_limits.strongest_first(names, "SI", 88.59, prefer)
    assert order[0] == "CRESST-III 2019" and order[1] == "LZ WS2022+WS2024"          # the fast module needs no budget
    assert halo_limits.strongest_first(names, "SI", 88.59)[:1] == ["CRESST-III 2019"]
    assert halo_limits.Budget(3).prefer == ()
