"""The shared "number copied from evidence" check reads each printed number once (the focused audit's FA-03,
2026-10-19): a complete scientific number before its parts, and an ASCII hyphen after "10" as a range, not a power."""
import pytest

from adroit.core.experimental_input import ExperimentalClaim, SourceLocator
from adroit.library.experimental import ExperimentalCatalog
from adroit.orchestrator.experimental_extraction import checked_claim, printed_numbers, printed_tokens, source_units


@pytest.mark.parametrize("text, absent", [
    ("The upper limit is 2.2 × 10−46 cm2.", 1e-46),        # the power inside a complete number
    ("Exposure in bins 10-46 is measured.", 1e-46),         # a hyphenated range
    ("The rate is 2.2 10-46.", 1e-46),                      # ambiguous: no typographic minus, no ^ or braces
    ("The rate is 2.2 10-46.", 2.2e-46),
    ("The upper limit is 2.2 × 10−46 cm2.", 2.2),            # the mantissa alone was not printed
])
def test_a_number_inside_another_or_a_range_is_not_read_as_printed(text, absent):
    assert not any(abs(v - absent) <= 1e-12 * abs(absent) for v in printed_numbers(text))


@pytest.mark.parametrize("text, value", [
    ("The upper limit is 2.2 × 10−46 cm2.", 2.2e-46), ("a limit of 1.1 10−46 cm2", 1.1e-46),
    (r"$1.1 \times 10^{-46}$", 1.1e-46), ("2.2 10^{-46}", 2.2e-46), ("below 10−46 cm2", 1e-46),
    ("10^{-45}", 1e-45), ("2.2e-46", 2.2e-46), ("95% CL", 0.95), ("95% CL", 95.0), ("at 90 percent", 0.9),
    ("Exposure in bins 10-46 is measured.", 10.0), ("Exposure in bins 10-46 is measured.", 46.0),
])
def test_the_documented_notations_are_still_read(text, value):
    assert any(abs(v - value) <= 1e-12 * abs(value) for v in printed_numbers(text))


def test_each_span_is_read_once_with_its_offsets():
    text = "σ < 2.2 × 10−46 cm2 at 50 GeV"
    tokens = printed_tokens(text)
    assert [round(v, 60) for v, *_ in tokens] == [2.2e-46, 50.0]
    assert text[tokens[0][2]:tokens[0][3]] == "2.2 × 10−46" and text[tokens[1][2]:tokens[1][3]] == "50"


@pytest.mark.parametrize("sentence, claimed, accepted", [
    ("The upper limit is 2.2 × 10−46 cm2.", 1e-46, False),
    ("Exposure in bins 10-46 is measured.", 1e-46, False),
    ("The rate is 2.2 10-46.", 1e-46, False),
    ("The upper limit is 2.2 × 10−46 cm2.", 2.2e-46, True),
])
def test_the_whole_claim_check_refuses_a_number_that_was_not_printed(tmp_path, sentence, claimed, accepted):
    """Through ``checked_claim``, as a detector input copied from a text source."""
    catalog = ExperimentalCatalog(tmp_path / "private")
    source = tmp_path / "note.txt"
    source.write_text(f"Section 2. {sentence}\n")
    r = catalog.import_files([source], "A note")
    claim = ExperimentalClaim(key="background_rate", category="detector", value=claimed, units="events",
                              status="sourced", sources=[SourceLocator(asset_sha256=r.sources[0].sha256,
                                                                       method="text", excerpt=sentence)])
    result, issues = checked_claim(catalog, r, claim, source_units(catalog, r.reference, False))
    assert (not issues) == accepted, issues
