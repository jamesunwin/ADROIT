"""Detector targets."""

from __future__ import annotations

import pytest

from adroit.physics import nuclear, targets


@pytest.mark.parametrize("name", targets.available_targets())
def test_every_target_is_well_formed(name: str) -> None:
    target = targets.target(name)                 # the Target model checks the fractions
    assert target.name == name and len(target.isotopes) >= 1


def test_every_element_has_abundances_summing_to_one() -> None:
    for symbol, element in targets.isotope_data()["elements"].items():
        total = sum(abundance for abundance, _spin in element["isotopes"].values())
        assert total == pytest.approx(1.0, abs=2e-4), symbol


def test_a_compound_is_weighted_by_mass() -> None:
    nai = targets.target("NaI")
    sodium = sum(i.mass_fraction for i in nai.isotopes if i.element == "Na")
    assert sodium == pytest.approx(23 / (23 + 127), rel=1e-6)
    cawo4 = targets.target("CaWO4")
    oxygen = sum(i.mass_fraction for i in cawo4.isotopes if i.element == "O")
    # abundance-weighted mass numbers: Ca 40.116, W 183.891, O 16.004
    assert oxygen == pytest.approx(4 * 16.0045 / (40.1156 + 183.8907 + 4 * 16.0045), rel=1e-4)


def test_the_spins_agree_with_the_shell_model_table() -> None:
    for name in targets.available_targets():
        for isotope in targets.target(name).isotopes:
            if nuclear.has_shell_model(isotope):
                assert isotope.spin == nuclear.shell_model_table()[isotope.name]["spin"]


def test_a_single_isotope_target() -> None:
    xe131 = targets.single_isotope("Xe131")
    assert xe131.isotopes[0].spin == 1.5 and xe131.isotopes[0].mass_fraction == 1.0
    with pytest.raises(ValueError, match="no data"):
        targets.single_isotope("Xe133")
    with pytest.raises(ValueError, match="symbol then mass number"):
        targets.single_isotope("xenon")
    with pytest.raises(ValueError, match="unknown target"):
        targets.target("Unobtainium")


def test_spin_expectations_are_listed_only_where_cited() -> None:
    assert targets.spin_expectations(targets.single_isotope("O17").isotopes[0]) == (0.0, 0.5)
    # 183W is left without a spin response by decision (isotopes.yaml), as are 29Si and 43Ca
    for name in ("W183", "Si29", "Ca43"):
        assert targets.spin_expectations(targets.single_isotope(name).isotopes[0]) is None
