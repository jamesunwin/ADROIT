import pytest

from adroit.model_building.groups import Rep, invariants, su2_weights, su3_rep, su3_weights


@pytest.mark.parametrize("name, dim", [("1", 1), ("3", 3), ("3bar", 3), ("8", 8), ("6", 6), ("10", 10)])
def test_su3_dimensions(name: str, dim: int) -> None:
    assert len(su3_weights(*su3_rep(name))) == dim


def test_su2_weights() -> None:
    assert su2_weights(3) == (2, 0, -2) and su2_weights(1) == (0,)


def test_textbook_invariants() -> None:
    d, t, tb, o = Rep("1", 2), Rep("3"), Rep("3", conjugate=True), Rep("8")
    assert invariants([(d, 1, True), (d, 1, True)]) == 1              # ε contraction of two doublets
    assert invariants([(d, 2, True)]) == 0 and invariants([(d, 2, False)]) == 1
    assert invariants([(t, 1, True), (tb, 1, True)]) == 1
    assert invariants([(t, 3, True)]) == 0 and invariants([(t, 3, False)]) == 1   # ε_abc is antisymmetric
    assert invariants([(o, 1, True)] * 3) == 2                         # d and f
    assert invariants([(o, 3, True)]) == 1 and invariants([(o, 3, False)]) == 1
    assert invariants([(Rep("1", 3), 3, True)]) == 0 and invariants([(Rep("1", 3), 4, True)]) == 1
    assert invariants([(Rep("1", 5), 1, True), (d, 1, True), (d, 1, True)]) == 0   # no quintuplet Yukawa


def test_flavour_counts_independent_couplings() -> None:
    lepton = Rep("1", 2, flavours=3)
    triplet = Rep("1", 3)
    assert invariants([(lepton, 2, True), (triplet, 1, True)]) == 6   # L L Δ: a symmetric 3×3


def test_unknown_representation() -> None:
    with pytest.raises(ValueError):
        su3_rep("27")
