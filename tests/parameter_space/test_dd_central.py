"""Supported direct-detection exclusions retained and shown, qualified (the owner's plan of 2026-11-24, section 3).

A point excluded at the halo region's centre whose exclusion is not established throughout the region keeps it:
stored (``Crossing.nominal_excluded_by``), worded ("excluded at the central SHM by direct detection; halo robustness
incomplete"), drawn excluded with a distinct outline, and listed with its own status, never as plain pending, never as
robust. The saved vector study's points (``tests/fixtures/vector_dd_pending.json.gz``) go through the production
classification (``verdict._over_region``, ``_sample_status``)."""
import gzip
import json
from pathlib import Path

import pytest

from adroit.parameter_space import certification, halo_region, verdict
from adroit.parameter_space.halo_region import HaloOutcome, HaloPointSample
from adroit.parameter_space.scan import PointResult
from adroit.parameter_space.verdict import Crossing

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _vector() -> list[dict]:
    return json.load(gzip.open(FIXTURES / "vector_dd_pending.json.gz"))["pending_crossings"]


def _at(m: float) -> dict:
    return next(c for c in _vector() if abs(c["point"]["m_chi"] - m) < 0.01)


def _reclassified(saved: dict) -> Crossing:
    """The saved point classified over its region again by the production code, from its centre's outcome (the
    nominal classification: excluded by the constraints that excluded it there)."""
    r = PointResult.model_validate(saved["evaluation"])
    nominal = [k for k, v in r.excluded.items() if v]
    c = Crossing(point=r.point, status="excluded" if nominal else "pending", excluded_by=nominal, kind="contour",
                 converged=True, evaluation=r)
    return verdict._over_region(c, r, None)


def test_a_budget_spent_after_the_central_exclusion_keeps_it_qualified() -> None:
    """88.59 GeV: excluded 1,111 times over at the centre; the point's two full calculations spent there, so the xenon
    searches are undecided at the other halos. The region leaves it pending with its coverage incomplete, and the
    central exclusion is kept and said, never erased and never robust."""
    c = _reclassified(_at(88.59))
    assert c.status == "pending" and c.halo == halo_region.INCOMPLETE
    assert c.nominal_status == "excluded" and c.nominal_excluded_by == ["direct detection"]
    words = certification.status_words(c)
    assert words == "excluded at the central SHM by direct detection; halo robustness incomplete"


def test_halo_samples_on_both_sides_of_the_limit_are_halo_sensitive_never_robust() -> None:
    c = _reclassified(_at(4376.6))
    assert c.halo == halo_region.SENSITIVE and c.status == "pending"
    assert certification.status_words(c) == ("excluded at the central SHM by direct detection; halo-sensitive "
                                             "across the tested region")


def test_one_supported_exclusion_decides_a_sample_whatever_else_is_undecided_there() -> None:
    """Cuts mode: at one halo, a supported direct-detection exclusion is sufficient; an unrelated search left undecided
    there does not undo it. Across the region every sample needs its own witness."""
    saved = _at(88.59)
    r = PointResult.model_validate(saved["evaluation"])
    sample = HaloPointSample(v0_km_s=233, v_esc_km_s=528, rho_gev_cm3=0.4, where="centre",
                             outcomes={"direct detection": HaloOutcome(excluded=True, ratio=3.0)},
                             unresolved=["capture in the Sun (IceCube): undecided here"])
    status, excluded, _ = verdict._sample_status(r, sample, [], [], None)
    assert status == "excluded" and excluded == ["direct detection"]
    assert halo_region.over(["excluded", "excluded"], [True, False]) == halo_region.EXCLUDED
    assert halo_region.over(["excluded", "viable"], [False, True]) == halo_region.INCOMPLETE


def test_the_rows_plot_and_report_words_agree_on_the_vector(tmp_path, monkeypatch) -> None:
    """The 17 central exclusions: the report's status words, the point list's status and the plot's markers all read
    the one stored assessment."""
    from types import SimpleNamespace
    import matplotlib
    import matplotlib.axes
    matplotlib.use("Agg")
    from adroit.evidence import points
    from adroit.parameter_space import plots
    from adroit.ui import points as ui_points
    assert ui_points.CENTRAL == points.CENTRAL
    crossings = [Crossing.model_validate(c | {"kind": "contour", "converged": True}) for c in _vector()]
    words = [certification.status_words(c) for c in crossings]
    central = [w for w in words if w.startswith("excluded at the central SHM by direct detection")]
    assert len(central) == 17
    assert sum(points.central_exclusion(c) != "" for c in crossings) == 17
    labels = []
    real = matplotlib.axes.Axes.legend
    monkeypatch.setattr(matplotlib.axes.Axes, "legend", lambda self, handles=(), **k: (
        labels.extend(h.get_label() for h in handles), real(self, handles=handles, **k))[1])
    request = SimpleNamespace(x=SimpleNamespace(parameter="m_chi", log=True),
                              y=SimpleNamespace(parameter="g_chi", log=True))
    request.model_class = SimpleNamespace(name="vector")
    xs = sorted({c.point.m_chi for c in crossings})[:3]
    scan = SimpleNamespace(points=[SimpleNamespace(excluded={}, omega_h2=None) for _ in range(9)], xs=xs,
                           ys=[0.01, 0.1, 1.0], request=request)
    plots.plane(scan, SimpleNamespace(crossings=crossings, target=0.12), tmp_path / "p.png")
    assert any(label.startswith("relic contour: excluded at the central SHM") for label in labels)
    assert "relic contour: pending" in labels                       # the three the centre does not exclude


@pytest.mark.parametrize("m", [60.87, 61.58, 10000.0])
def test_a_point_the_centre_does_not_exclude_is_not_called_excluded(m) -> None:
    c = Crossing.model_validate({k: v for k, v in _at(m).items() if k != "evaluation"})
    assert certification.central_exclusion(c) == "" and not certification.status_words(c).startswith("excluded")
