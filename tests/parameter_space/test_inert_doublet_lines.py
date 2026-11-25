"""The audit loop's AL4-10: the inert doublet's γ-ray line searches read "allowed" on the Higgs's loop alone (a ratio
of 6.6 × 10⁻⁶), though H₀H₀ → γγ and Zγ run mainly through the W and charged-scalar loops, which are not computed. They
are undecided now, with that reason, and the entry says the lines are not computed."""
from adroit.parameter_space import library, searches


def test_the_inert_doublets_line_searches_are_undecided_and_say_why() -> None:
    entry = library.entry("inert_doublet")
    outcome = searches.lines(entry.model_class, entry.point, False)
    assert outcome is not None and outcome.name == searches.LINES and outcome.excluded is None
    assert "W and charged-scalar loops" in outcome.why
    assert any("γ-ray line" in item for item in entry.model_class.not_computed)


def test_a_portal_with_its_own_line_rate_is_not_affected() -> None:
    assert library.entry("two_hdm_a").model_class.partial_lines == ""
