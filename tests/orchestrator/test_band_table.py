"""The single-idea table's physical √q0 (the re-audit's R18-5, 2026-10-18): the stored statistic, labelled where the
headline policy cannot use it, never the policy's zero. The three range-edge rows are those of the documented vector
example rerun by the auditor (q0 0.2514, 4.1513 and 9.13 at 5, 6.04 and 7.30 GeV)."""

from __future__ import annotations

import math

import pytest

from adroit.core.model_spec import PhysicalFitRange
from adroit.orchestrator.single_idea import BandPoint, _band_table, _fit_z
from adroit.parameter_space.physical_fit import FitSettings, PhysicalFit


def _row(m: float, q0: float | None, **fit) -> BandPoint:
    physical = PhysicalFit(bounds=PhysicalFitRange(low=0.0, high=3.54), settings=FitSettings(), q0=q0,
                           **{"resolved": True, "identifiable": True, **fit})
    return BandPoint(m_chi=m, s_hat=1.0, events_at_unit=1.0, mu_hat=1.0, mu_68=(0.5, 1.5), z_local=1.77,
                     physical_fit=physical)


def _shown(b: BandPoint) -> str:
    return _band_table([b])[-1].split("|")[2].strip()


@pytest.mark.parametrize("m, q0", [(5.0, 0.25140422443657684), (6.040447222022237, 4.151269081966365),
                                   (7.2974005284072305, 9.13)])
def test_a_range_edge_fit_shows_its_stored_statistic_marked_ineligible(m, q0) -> None:
    b = _row(m, q0, at_boundary=True)
    assert _fit_z(b) == 0.0                                   # the headline policy is unchanged
    assert _shown(b) == f"1.77 / {math.sqrt(q0):.2f} (at its range's edge; not eligible)"


def test_the_other_states_are_labelled_and_an_eligible_fit_is_plain() -> None:
    assert _shown(_row(9.0, 4.0)) == "1.77 / 2.00"
    assert _shown(_row(9.0, 0.25)) == "1.77 / 0.50"            # below the threshold: a valid statistic, shown plainly
    assert _shown(_row(9.0, None, resolved=False)) == "1.77 / — (unresolved; not eligible)"
    assert _shown(_row(9.0, 6.25, identifiable=False)) == "1.77 / 2.50 (unidentifiable; not eligible)"
