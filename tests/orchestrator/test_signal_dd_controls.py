"""The plan's three mutation controls (the owner's plan of 2026-11-24, section 5), headless (the owner, 2026-11-24: the
real-browser versions deferred to 1.0.1). Each invariant passes on the code as built (its baseline) and fails, at its
named invariant, with one defect restored in the production code:

(a) a fitted amplitude substituted for the physical count;
(b) the signal assessment omitted from the plane;
(c) a central exclusion erased where the halo coverage is incomplete.
"""
import gzip
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from adroit.experiments import registry
from adroit.orchestrator import single_idea as idea
from adroit.parameter_space import assessment as A
from adroit.parameter_space import certification
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.verdict import Crossing
from tests.orchestrator.test_signal_plane import CDMS, _request, _t1

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture(scope="module")
def cdms():
    import numpy as np
    from adroit.inference import signal_fit
    module = registry.load_module(CDMS)
    events, _ = module.observations()
    null = float(signal_fit.profile_log_likelihood(0.0, np.zeros(len(events)), module.background_at(events),
                                                   module.background_rate())[0])
    return module, null


# --- the invariants ---------------------------------------------------------------------------------------------------

def no_borrowed_amplitude(module, null) -> None:
    """(a) A coupling too weak to make the events does not meet the signal criterion, whatever the reference
    free-amplitude fit at its mass says."""
    weak = Point(m_chi=10, m_med=1000, g_chi=0.01, g_q=0.25)
    s = A.signal_at(Spin1Class(), weak, module, 0.5, null, experiment=CDMS, halo="published")
    assert s.state != "meets", "INVARIANT (a): a weak physical coupling borrowed the reference fit's strength"


def plane_carries_the_signal(module) -> None:
    """(b) The plane's headline and figure read a stored signal assessment."""
    plane = idea.signal_plane(_request("published"), Spin1Class(), module, 0.5, _t1(""))
    overlays = idea.plane_overlays(SimpleNamespace(band=[], signal_plane=plane))
    level, text = idea._with_plane("undetermined", "unresolved fits", plane)
    assert plane is not None and overlays["signal"] and "meets the signal criterion" in text, \
        "INVARIANT (b): the plane carries no signal assessment"


def central_exclusion_kept() -> None:
    """(c) The vector's 88.59 GeV point, excluded at the centre with its halo coverage incomplete, reads so."""
    saved = next(c for c in json.load(gzip.open(FIXTURES / "vector_dd_pending.json.gz"))["pending_crossings"]
                 if abs(c["point"]["m_chi"] - 88.59) < 0.01)
    c = Crossing.model_validate(saved | {"kind": "contour", "converged": True})
    assert certification.status_words(c).startswith("excluded at the central SHM by direct detection"), \
        "INVARIANT (c): a central exclusion was erased where the halo coverage is incomplete"


# --- each control: its baseline, then the defect restored -------------------------------------------------------------

def test_a_fitted_amplitude_substituted_for_the_physical_count_fails_at_its_invariant(cdms, monkeypatch) -> None:
    module, null = cdms
    no_borrowed_amplitude(module, null)                                 # the baseline passes

    def amplitude(cls, point, module, spin, null_log_l, **kwargs):     # the defect: the free-amplitude fit's strength
        fit = idea._fit_at(module, cls, point, point.m_chi, spin)
        return A.judge_signal(null_log_l + fit.z_local ** 2 / 2, null_log_l, fit.s_hat, **kwargs)
    monkeypatch.setattr(A, "signal_at", amplitude)
    with pytest.raises(AssertionError, match=r"INVARIANT \(a\)"):
        no_borrowed_amplitude(module, null)


def test_the_signal_assessment_omitted_from_the_plane_fails_at_its_invariant(cdms, monkeypatch) -> None:
    module, _ = cdms
    plane_carries_the_signal(module)
    monkeypatch.setattr(idea, "signal_plane", lambda *a, **k: None)     # the defect: a constraint plane only
    with pytest.raises(AssertionError, match=r"INVARIANT \(b\)"):
        plane_carries_the_signal(module)


def test_a_central_exclusion_erased_fails_at_its_invariant(monkeypatch) -> None:
    central_exclusion_kept()
    monkeypatch.setattr(certification, "central_exclusion", lambda point: "")   # the defect: plain pending
    with pytest.raises(AssertionError, match=r"INVARIANT \(c\)"):
        central_exclusion_kept()
