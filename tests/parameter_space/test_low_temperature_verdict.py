"""A06's low-temperature relic state reaches the scan's verdict (the external audit of 2026-10-17, R17-4).

The relic solver holds the bath's degrees of freedom fixed below 1 MeV; for a light relic A06 compares a decoupled-
neutrino history and leaves a point pending where Ωh² moves by more than 5%. The no-root branch of the verdict had
read only missing values, so a scan of such points was called underabundant although the alternative history puts
every one above the target. Real Boltzmann results; the scan record is synthetic, to isolate the propagation."""

from __future__ import annotations

import numpy as np
import pytest

from adroit.constraints import relic
from adroit.parameter_space import searches
from adroit.parameter_space import verdict as v
from adroit.parameter_space.classes import Point, ScalarClass
from adroit.parameter_space.scan import RELIC_PENDING, Axis, PointResult, ScanRequest, ScanResult

RATE = 3e-9          # GeV⁻², a constant ⟨σv⟩ for a self-conjugate scalar


def _omega(m: float) -> float:
    return relic.omega_h2_rate(relic.dark_matter(m, 0.0, True), lambda T: np.full_like(T, RATE))


def _scan(masses, omegas, *, pending=lambda m: [], validity=lambda m: []) -> ScanResult:
    # the carrier's mediator above the hadronic window (``hadronic_window``), where its domain refuses nothing
    request = ScanRequest(model_class=ScalarClass(), fixed=Point(m_chi=masses[0], m_med=10.0),
                          x=Axis(parameter="m_chi", low=masses[0], high=masses[-1], n=len(masses)),
                          y=Axis(parameter="m_med", low=10.0, high=20.0, n=2))
    rows = [PointResult(point=Point(m_chi=m, m_med=med), omega_h2=o, dd_kind="SI", dd_sigma_cm2=0.0, dd_limit_cm2=1.0,
                        excluded={}, pending=pending(m), relic_validity=validity(m))
            for med in request.y.values() for m, o in zip(request.x.values(), omegas)]
    return ScanResult(request=request, xs=request.x.values(), ys=request.y.values(), points=rows)


@pytest.fixture(scope="module")
def light() -> list[tuple[float, float, str]]:
    """(m, Ωh² held at 1 MeV, A06's reason) at 200 and 300 keV: 0.0884 and 0.0917, against 0.143 and 0.148 with the
    neutrinos decoupled."""
    out = []
    for m in (2e-4, 3e-4):
        held = _omega(m)
        with relic.low_temperature_history():
            decoupled = _omega(m)
        assert held < 0.12 < decoupled
        out.append((m, held, relic.thermal_history_reason(lambda: _omega(m), m, held)))
    assert all(why for _, _, why in out)
    return out


def test_points_outside_the_supported_history_do_not_decide_an_abundance(light) -> None:
    masses, omegas, reasons = zip(*light)
    why = dict(zip(masses, reasons))
    for scan in (_scan(masses, omegas, pending=lambda m: [RELIC_PENDING + why[m]], validity=lambda m: [why[m]]),
                 _scan(masses, omegas, pending=lambda m: [RELIC_PENDING + why[m]])):      # stored before the field
        found = v.verdict(scan)
        assert found.level == "pending" and any("outside the supported thermal history" in u for u in found.unresolved)


@pytest.mark.needs("eos")
def test_an_undecided_search_does_not_suppress_an_abundance(light) -> None:
    masses, omegas, _ = zip(*light)
    found = v.verdict(_scan(masses, omegas, pending=lambda m: ["colliders: a recast of the LHC searches to this model"]))
    assert found.level == "underabundant" and not found.unresolved


def test_heavy_relics_are_unaffected() -> None:
    assert relic.thermal_history_reason(lambda: _omega(1.0), 1.0, _omega(1.0)) == ""


@pytest.mark.needs("eos")
def test_an_excluded_contour_on_such_points_is_pending(monkeypatch) -> None:
    """Root certification: roots whose Ωh² rests on the unsupported history do not certify an exclusion."""
    monkeypatch.setattr(ScalarClass, "omega_h2", lambda self, p: 0.12 * p.m_chi / 2.5e-4, raising=False)
    monkeypatch.setattr(searches, "prefetch_lhc", lambda cls, ps, *a: [None] * len(ps))

    def judge(cls, p, *args, **kwargs):
        row = PointResult(point=p, omega_h2=cls.omega_h2(p), dd_kind="SI", dd_sigma_cm2=0.0, dd_limit_cm2=1.0,
                          excluded={"synthetic": True}, relic_validity=["Ωh² moves by 62% with the neutrinos decoupled"])
        return v.classify(cls, row)
    monkeypatch.setattr(v, "judge_point", judge)
    masses = [2e-4, 3e-4]
    found = v.verdict(_scan(masses, [0.12 * m / 2.5e-4 for m in masses]))
    assert found.crossings and found.level == "pending"
    assert any(u.startswith("the thermal roots:") for u in found.unresolved)


def test_explain_a_signal_does_not_decide_on_such_points() -> None:
    """``single_idea._level``: no thermal intersection (or an excluded one) on Ωh² from the unsupported history is
    undetermined; the same band without it keeps its level."""
    from adroit.orchestrator.single_idea import BandPoint, _level
    row = PointResult(point=Point(m_chi=2e-4, m_med=10.0), omega_h2=0.09, dd_kind="SI", dd_sigma_cm2=0.0,
                      dd_limit_cm2=1.0, excluded={}, relic_validity=["Ωh² moves by 62% with the neutrinos decoupled"])
    band = BandPoint(m_chi=2e-4, s_hat=1.0, events_at_unit=1.0, mu_hat=1.0, mu_68=(0.5, 1.5), z_local=2.0,
                     point=row.point, omega_h2=0.09, status="pending", evaluation=row)
    level, text = _level([band], [], computed=True)
    assert level == "undetermined" and "outside the supported thermal history" in text
    clean = band.model_copy(update={"evaluation": row.model_copy(update={"relic_validity": []})})
    assert _level([clean], [], computed=True)[0] == "no_thermal"
