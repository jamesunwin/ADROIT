"""Quote matching up to typesetting (core.quotes): live check L5's genuine quotes match; changed ones never do."""

import pytest

from adroit.core.quotes import contains, normalise

PAGE = ("Three WIMP-candidate events were ob-\nserved, with recoil energies of 8.2, 9.5, and 12.3 keV. The ﬁnal\n"
        "surface-event background estimate is 0.41 +0.20 −0.08(stat.) events. The dark-\nmatter halo is "
        "the stan­dard one, with a total exposure of 140.2 kg–days.")


@pytest.mark.parametrize("quote", [
    "Three WIMP-candidate events were observed",                        # line-break hyphenation joined
    "were ob- served",                                                  # the broken form, as extracted
    "The final surface-event background",                               # ligature ﬁ
    "0.41 +0.20 -0.08(stat.)",                                          # thin space, Unicode minus
    "The dark-matter halo",                                             # a hyphenated word broken at its hyphen
    "the standard one",                                                 # soft hyphen
    "140.2 kg-days",                                                    # en dash
    "THREE wimp-candidate EVENTS",                                      # case
])
def test_genuine_quotes_match_up_to_typesetting(quote: str) -> None:
    assert contains(PAGE, quote)


@pytest.mark.parametrize("quote", ["recoil energies of 8.3", "0.41 +0.20 -0.09", "140.2 kg-years", "", "   ",
                                   "The darkmatter halo is a different one"])
def test_changed_numbers_and_words_never_match(quote: str) -> None:
    assert not contains(PAGE, quote)


def test_case_sensitive_matching_for_source_values() -> None:
    assert contains("threshold 7 keV", "7 keV", case_sensitive=True)
    assert not contains("threshold 7 keV", "7 KEV", case_sensitive=True) and contains("threshold 7 keV", "7 KEV")


def test_normalise_spells_out_and_collapses() -> None:
    assert normalise("ﬂux − 1\n\n e­x- \n periment") == "flux - 1 experiment"
    assert normalise("dark- matter", join_broken_words=False) == "dark-matter"
    assert normalise("10⁻⁴⁵ cm²") == "10⁻⁴⁵ cm²"                       # superscripts are kept: not typesetting


def test_the_anomaly_drafter_and_excerpt_checks_use_it() -> None:
    from adroit.agents.anomaly import AnomalyDraft, unquoted
    draft = AnomalyDraft(name="x", sources={"events_kev": "Three WIMP-candidate events were observed",
                                            "exposure_kg_day": "140.2 kg-days", "target": "a xenon target"})
    assert unquoted(draft, PAGE) == ["target"]
