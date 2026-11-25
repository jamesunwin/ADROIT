"""G8: the resummed γ-ray lines of a pure wino or higgsino, from DMγSpec's table (``constraints.resummed_lines``)."""

import pytest

from adroit.constraints import resummed_lines as rl
from adroit.core.model_spec import ModelSpec
from adroit.evaluation import zoo
from adroit.parameter_space.portals import generic as gm
from adroit.parameter_space.portals import generic_lhc

needs_table = pytest.mark.skipif(not rl.available(), reason="DMγSpec's table is not in the tools folder")


def _multiplet(n: int, y: float, m: float, sommerfeld: bool = True) -> gm.GenericModel:
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": m,
               "self_conjugate": y == 0, "charges": {"su2": n, "hypercharge": y}},
              {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}]
    return gm.GenericModel.of(ModelSpec.model_validate({"name": f"m{n}", "phase": "unbroken", "fields": fields}),
                              sommerfeld=sommerfeld)


def test_no_value_outside_the_table_or_for_another_model():
    assert rl.line_sigma_v("quintuplet", 2000.0) is None
    assert rl.line_sigma_v("wino", 100.0) is None and rl.line_sigma_v("wino", 2e5) is None


@needs_table
def test_a_pure_wino_takes_the_resummed_rate_and_is_no_longer_an_upper_bound():
    e = next(x for x in zoo.entries() if x.id == "wino_majorana_triplet_bottaro")
    wino = gm.GenericModel.of(zoo._spec(e, e.targets[0]), sommerfeld=True)
    p = wino.point().model_copy(update={"m_chi": 1000.0})
    assert wino.line_sigma_v(p) == {"gamma": pytest.approx(rl.line_sigma_v("wino", 1000.0))}
    assert wino.lines_upper_bound(p) == ""
    perturbative = wino.model_copy(update={"sommerfeld": False})
    assert perturbative.resummed_line(p) == ("", None)


@needs_table
def test_a_dirac_higgsino_is_doubled_against_the_searches_halving():
    """As the library's: its neutral states are split into Majorana states today."""
    h = _multiplet(2, 0.5, 1100.0)
    assert h.line_sigma_v(h.point())["gamma"] == pytest.approx(2.0 * rl.line_sigma_v("higgsino", 1100.0))


def test_a_quintuplet_is_not_in_the_table():
    """DMγSpec has no quintuplet: its lines are the general n-plet's NLL rate (``endpoint_nll``, the owner's
    decision of 2026-10-15), not the table's."""
    from adroit.constraints import endpoint_nll
    five = _multiplet(5, 0.0, 3000.0)
    mb, rules, _ = five.at(five.point())
    assert generic_lhc.pure_dark_kind(mb, rules) == ""
    assert five.resummed_line(five.point()) == ("nplet5", pytest.approx(endpoint_nll.line_sigma_v(5, 3000.0)))
