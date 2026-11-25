"""R5 (audit M10): a failed theory certificate excludes a point, and an unresolved one leaves it pending."""

from pathlib import Path

import pytest
import yaml

from adroit.core.model_spec import ModelSpec
from adroit.parameter_space.classify import classify
from adroit.parameter_space.verdict import judge_point

EXAMPLE = Path(__file__).resolve().parents[2] / "docs" / "examples" / "complete_scalar_singlet.yaml"


def _complete_scalar(lambda_s: float):
    data = yaml.safe_load(EXAMPLE.read_text())
    data["scalar_potential"]["lambda_s"] = lambda_s
    return classify(ModelSpec.model_validate(data))[:2]


@pytest.mark.parametrize("lambda_s,failing", [(-0.1, "the tree-level vacuum fails (local)"),
                                              (10.0, "tree-level scalar unitarity fails (failed)")])
@pytest.mark.needs("diamx", "solar_model")
def test_a_point_whose_theory_certificate_fails_is_not_viable(lambda_s, failing) -> None:
    cls, p = _complete_scalar(lambda_s)
    crossing = judge_point(cls, p)
    assert crossing.status == "excluded"
    assert any(failing in reason and "invalid model point" in reason for reason in crossing.excluded_by)


@pytest.mark.needs("diamx", "solar_model")
def test_the_example_point_passes_its_certificates() -> None:
    cls, p = _complete_scalar(0.2)
    crossing = judge_point(cls, p)
    assert not any(r.startswith("theory:") for r in crossing.excluded_by + crossing.pending)
    assert any(f.startswith("tree-level scalar unitarity: passed") for f in crossing.flags)


def test_an_exactly_degenerate_vacuum_is_pending_not_a_pass() -> None:
    from adroit.core.theory import ScalarVacuumCertificate
    from adroit.parameter_space.scan import PointResult
    from adroit.parameter_space.verdict import theory_status
    from adroit.parameter_space.classes import Point
    tie = ScalarVacuumCertificate(complete=True, passed=None, vacuum="degenerate", reasons=["exactly degenerate"])
    row = PointResult(point=Point(m_chi=100.0, m_med=125.09), omega_h2=0.12, dd_kind="SI", dd_sigma_cm2=0.0,
                      dd_limit_cm2=None, excluded={}, vacuum_certificate=tie)
    assert theory_status(row) == ([], ["theory: the tree-level vacuum is unresolved (degenerate: exactly degenerate)"])


def test_a_small_kinetic_mixing_keeps_its_value() -> None:
    """Audit minor: ε was rounded to 12 decimals, so ε = 3e-13 had no mixing and 1.23456e-10 became 1.23e-10."""
    from adroit.constraints import kinetic_mixing as km
    tiny, small = km.couplings(10.0, 3e-13, 1.0), km.couplings(10.0, 1.23456e-10, 1.0)
    assert tiny["A'"]["fermions"]["e"][0] != 0.0
    ratio = small["A'"]["fermions"]["e"][0] / km.couplings(10.0, 1.23e-10, 1.0)["A'"]["fermions"]["e"][0]
    assert ratio == pytest.approx(1.23456 / 1.23, rel=1e-6)


def test_a_cached_rate_never_crosses_from_dirac_to_majorana_dark_matter() -> None:
    """Audit minor: the hh table's key left out ``majorana``, which changes the Higgs width below m_h/2."""
    import numpy as np
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.portals import base
    from adroit.parameter_space.portals.higgs import HiggsPortalFermion
    p, s = Point(m_chi=50.0, m_med=125.09, g_chi=1e-3), np.array([300.0 ** 2])
    base._TABLES.clear()
    fresh = HiggsPortalFermion(majorana=True).channels(s, p)["hh"]
    base._TABLES.clear()
    HiggsPortalFermion(majorana=False).channels(s, p)
    assert HiggsPortalFermion(majorana=True).channels(s, p)["hh"] == pytest.approx(fresh, rel=1e-12)


def test_a_ufo_models_cache_identity_holds_its_dark_sector() -> None:
    from adroit.parameter_space.library import TWO_HDM_A
    other = TWO_HDM_A.model_copy(update={"partners": ["h3"]})
    assert TWO_HDM_A._identity() != other._identity()
    assert TWO_HDM_A._identity() != TWO_HDM_A.model_copy(update={"width_of": {}})._identity()
