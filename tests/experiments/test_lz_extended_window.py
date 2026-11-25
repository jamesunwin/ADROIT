"""LZ's extended window at fidelity B: the one-event likelihood (DM5)."""

from __future__ import annotations

import pytest

from adroit.experiments import lz_extended_window as lz
from adroit.external import fetch


def test_one_event_on_no_background() -> None:
    low, best, high = lz.interval_counts(1.0, 1e-9)
    # q(s) = 2(s − 1 − ln s) = 2.706: the asymptotic two-sided interval for one event
    assert (low, best, high) == pytest.approx((0.10571, 1.0, 3.64655), rel=1e-4)
    # a signal that cannot make the event: the limit of no events, q = 2s
    assert lz.interval_counts(1e-12, 1e-6) == pytest.approx((0.0, 0.0, 1.35277), abs=1e-4)


def test_the_significance_calibration_inverts() -> None:
    r = lz.ratio_for_significance(3.4)
    assert 0.0 < r < 0.01
    assert lz.local_significance(1.0, r) == pytest.approx(3.4, rel=1e-9)
    assert lz.local_significance(1.0, 2.0) == 0.0


@pytest.mark.skipif(fetch.locate(lz.ITEM) is None, reason="LZ's HEPData record not present")
@pytest.mark.needs("revised_xenon")      # LZ's own responses (the shell model's give d_up 2.0 times LZ's)
def test_lz_l10_at_1000_gev_is_reproduced() -> None:
    from adroit.core.dm_state import DarkMatterParticle
    from adroit.library.interactions import registry
    module = lz.LzExtendedWindow()
    conventions = module.conventions()
    particle = DarkMatterParticle(mass_gev=1000.0)
    signal = module.expected_signal(particle, registry.resolve("L10", particle,
                                                              lz.lz_values("L10", "s")),
                                    conventions.halo, conventions.nuclear_model)
    published = lz.model_tables()["L10s"]
    d_up = module.upper_limit(signal) ** 0.5
    assert d_up / published.upper[published.masses_gev.index(1000.0)] == pytest.approx(1.0, abs=0.3)
    assert module.significance(signal) == pytest.approx(3.4, abs=0.05)     # the calibration point


def _l12_script():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "docs" / "dm6" / "lz_l12_conventions.py"
    spec = importlib.util.spec_from_file_location("lz_l12_conventions", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_l12_conventions_cancel_only_with_one_nucleon_mass() -> None:
    """The scan's ADROIT variant keeps c12 − (q/m_N)² c15 = 0; another nucleon mass in O15 detunes it by 1.5–1.7%."""
    script = _l12_script()
    for name, mass in script.NUCLEON_MASSES.items():
        terms = {o: c for o, c, _ in script.terms(100.0, mass, script.O10["c10 as Anand et al."], 1.0)}
        detuning = terms[12] * script.M_N ** 2 / terms[15] - 1.0
        assert detuning == pytest.approx(0.0, abs=1e-12) if mass == script.M_N else 0.014 < detuning < 0.018


def test_l12_scan_records_that_no_discrete_convention_matches_lz() -> None:
    """docs/notes/lz_model_cards.html states the result; the stored scan must agree with it."""
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).resolve().parents[2] / "docs" / "dm6" / "lz_l12_conventions.json").read_text())
    assert len(data["variants"]) == 80 and max(v["matched"] for v in data["variants"]) == 1
    assert max(v["matched"] for v in data["tuned_for_scale_only"]) < 26
