"""G11's benchmark agent: extracted targets and their deterministic quote check (``agents.benchmarks``)."""

import pytest

from adroit.agents import benchmarks as bm
from adroit.agents.llm import FakeLLMClient

PAGES = ["Introduction. Nothing here.",
         "Table 2: benchmark points. BP1 m = 500 GeV, Omega h2 = 0.1198, sigma = 2.1 ×10−12 pb.",
         "the scattering cross-section on a proton amounts to 8.45 10−46 cm2, and the ratio is of order 6% there."]


def _target(**kw) -> bm.BenchmarkTarget:
    base = dict(quantity="omega_h2", value=0.1198, page=2, quote="BP1 m = 500 GeV, Omega h2 = 0.1198")
    return bm.BenchmarkTarget(**(base | kw))


def test_numbers_read_every_printed_form_of_scientific_notation():
    assert 2.1e-12 in bm.numbers("2.1 ×10−12 pb")
    assert 8.45e-46 in bm.numbers("8.45 10−46 cm2")                 # the × lost in the text extraction
    assert 1.2e-3 in bm.numbers("1.2 × 10^{-3}")


def test_paged_text_marks_each_page():
    assert bm.paged_text(["a", "b"]) == "=== page 1 ===\na\n=== page 2 ===\nb"


def test_a_quote_printed_on_its_page_passes():
    assert bm.quote_check(_target(), PAGES) == ""
    assert bm.quote_check(_target(quantity="sigma_si_cm2", value=8.45e-46, unit="cm2", page=3,
                                  quote="amounts to 8.45 10−46 cm2"), PAGES) == ""


def test_a_neighbouring_page_is_accepted_for_a_table_split_by_the_extraction():
    assert bm.quote_check(_target(page=3), PAGES) == ""


def test_a_quote_not_on_its_page_fails():
    assert "not on page" in bm.quote_check(_target(quote="Omega h2 = 0.1205"), PAGES)
    assert "not in the paper" in bm.quote_check(_target(page=9), PAGES)


def test_a_value_not_in_its_quote_fails():
    assert "not among the quote's numbers" in bm.quote_check(_target(value=0.12), PAGES)


def test_a_percentage_passes_as_printed_with_its_unit_or_as_a_dimensionless_fraction():
    """The audit's AG-3 (G12): 0.06 with the unit "%" had passed and then been divided by 100 again."""
    quote = dict(quantity="thermal_splitting", page=3, quote="the ratio is of order 6% there")
    assert bm.quote_check(_target(value=6.0, unit="%", **quote), PAGES) == ""
    assert bm.quote_check(_target(value=0.06, unit="", **quote), PAGES) == ""
    assert "not among the quote's numbers" in bm.quote_check(_target(value=0.06, unit="%", **quote), PAGES)


def test_a_tiny_number_is_not_matched_by_a_printed_zero():
    """The audit's AG-2 (G12): an absolute tolerance let any number below 10⁻⁹ match a "0" on the page."""
    pages = ["theta = 0 here", "nothing", "nothing", "sigma_SI = 8.0e-47 cm2, three pages on"]
    target = _target(quantity="sigma_si_cm2", value=8.0e-47, unit="cm2", page=1, quote="theta = 0")
    assert "not among the quote's numbers" in bm.quote_check(target, pages)
    invented = _target(quantity="sigma_si_cm2", value=8.0e-47, unit="cm2", page=1, quote="sigma_SI = 8.0e-47 cm2")
    assert "not on page" in bm.quote_check(invented, pages)


def test_an_invented_quote_built_from_numbers_on_the_page_is_refused():
    """The audit's AG-2: "Omega h2 = 500" passed because 500 (a mass) is printed on the page."""
    assert "quote is not on page" in bm.quote_check(_target(value=500.0, quote="Omega h2 = 500"), PAGES)


def test_the_parameter_points_numbers_must_be_printed_in_the_paper():
    """Anywhere in it: a benchmark is often defined in one table and its results printed in another."""
    assert bm.quote_check(_target(at={"m_chi": 500.0}), PAGES) == ""
    assert bm.quote_check(_target(at={"ratio": 6.0}), PAGES) == ""
    assert bm.quote_check(_target(at={"sigma": 2.1e-12}), PAGES) == ""       # printed as 2.1 ×10−12
    assert "parameter point's m_chi" in bm.quote_check(_target(at={"m_chi": 750.0}), PAGES)


def test_a_table_rows_numbers_in_their_order_pass_where_the_text_is_not_verbatim():
    pages = ["Table 3. Model Omega h2 sigma\nBP1\n0.119\n6.96 x 10-50\n7.10 x 10-50\nBP2"]
    row = _target(quantity="omega_h2", value=0.119, page=1, quote="BP1 0.119 6.96 × 10−50 7.10 × 10−50")
    assert bm.quote_check(row, pages) == ""
    swapped = _target(quantity="omega_h2", value=0.119, page=1, quote="BP1 7.10 × 10−50 0.119")
    assert "quote is not on page" in bm.quote_check(swapped, pages)


def test_an_unknown_unit_is_refused_and_mev_is_converted():
    assert "not understood" in bm.quote_check(_target(unit="furlongs"), PAGES)
    with pytest.raises(ValueError, match="not understood"):
        bm.in_adroit_units(_target(unit="furlongs"))
    assert bm.in_adroit_units(_target(value=33.0, unit="MeV")) == pytest.approx(0.033)


@pytest.mark.parametrize(("value", "unit", "expected"), [(2.1e-12, "pb", 2.1e-48), (1.5, "TeV", 1500.0),
                                                         (6.0, "%", 0.06), (0.1198, "", 0.1198)])
def test_values_are_converted_to_the_zoos_units(value, unit, expected):
    assert bm.in_adroit_units(_target(value=value, unit=unit)) == pytest.approx(expected)


def test_the_agent_keeps_what_passes_and_drops_the_rest_with_its_reason():
    good, bad = _target(), _target(value=0.13, quote="Omega h2 = 0.13")
    other = _target(quantity="relic_temperature")
    agent = bm.BenchmarkAgent(FakeLLMClient([bm.Benchmarks(targets=[good, bad, other])]), "fake-model")
    kept, dropped = agent.run("a model", PAGES)
    assert kept == [good]
    assert [t for t, _ in dropped] == [bad, other]
    assert "not on page" in dropped[0][1] and dropped[1][1] == "relic_temperature is not compared"
