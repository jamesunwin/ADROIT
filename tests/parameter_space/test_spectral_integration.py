"""Spectral verdict integration preserves source gates and avoids dwarf double counts."""

import pytest

from adroit.constraints import database, dwarf_likelihood as dl, indirect, spin1, verdicts
from adroit.core.dm_state import DarkMatterParticle
from adroit.parameter_space import scan
from adroit.parameter_space.classes import Point, ScalarClass


@pytest.fixture
def isolated_scan(monkeypatch):
    monkeypatch.setattr(ScalarClass, "omega_h2", lambda *_: 0.12)
    monkeypatch.setattr(ScalarClass, "dd", lambda *_: ("momentum-suppressed", 0.0))
    monkeypatch.setattr(ScalarClass, "sigma_v_today", lambda *_: {"b": 2e-26, "c": 2e-26})
    monkeypatch.setattr(scan.searches, "outcomes", lambda *_: [])
    monkeypatch.setattr(scan, "_icecube", lambda *_: (None, None, ""))
    return ScalarClass(), Point(m_chi=100.0, m_med=400.0)


def test_scan_gate_and_spectral_source_provenance(isolated_scan, monkeypatch, awaiting):
    awaiting("fermi-2311.04982-spectral")                                   # held unverified, whatever the owner has signed
    cls, point = isolated_scan
    result = scan.evaluate(cls, point)
    assert result.photon_limit is None and result.excluded["gamma rays (Fermi-LAT dwarfs)"] is None
    assert any("verification" in reason for reason in result.pending)
    limit = dl.SpectralLimit(
        upper95_cm3_s=3e-26,
        best_fit_cm3_s=1e-26,
        dwarfs=42,
        self_conjugate=False,
        density_fraction=1.0,
    )
    monkeypatch.setattr(
        scan,
        "spectral_comparison",
        lambda *_: indirect.SpectralComparison(ratio=4 / 3, limit=limit),
    )
    result = scan.evaluate(cls, point, True)
    assert result.photon_limit == limit and result.excluded["gamma rays (Fermi-LAT dwarfs)"] is True
    assert not any("Fermi-LAT" in reason for reason in result.pending)
    assert "2311.04982" in result.statistical_limits["gamma rays (Fermi-LAT dwarfs)"].source
    assert result.ratios == {"gamma rays (Fermi-LAT dwarfs)": pytest.approx(4 / 3)}
    # Existing pure spectra retain precisely the old comparison, with no new calls.
    monkeypatch.setattr(ScalarClass, "sigma_v_today", lambda *_: {"b": 2e-26})
    monkeypatch.setattr(scan, "spectral_comparison", lambda *_: pytest.fail("duplicate likelihood"))
    result = scan.evaluate(cls, point, True)
    assert "1503.02641" in result.statistical_limits["gamma rays (Fermi-LAT dwarfs)"].source
    assert result.photon_limit is None


def test_track2_judgement_replaces_pending_old_record_only_after_a_recast(monkeypatch, awaiting):
    awaiting("fermi-2311.04982-spectral")                                   # held unverified, whatever the owner has signed
    model = spin1.benchmark("V1", 1000.0)
    candidate = verdicts.Candidate(
        label="mixed",
        particle=DarkMatterParticle(mass_gev=100.0),
        interaction=spin1.interaction(model, 100.0),
        completion=model,
    )
    records = [database.record("fermi-1503.02641-dsph"), database.record(dl.RECORD)]
    monkeypatch.setattr(database, "usable", lambda *_: records)
    monkeypatch.setattr(verdicts.annihilation, "sigma_v_today", lambda *_: {"b": 1e-26, "c": 1e-26})
    limit = dl.SpectralLimit(
        upper95_cm3_s=4e-26,
        best_fit_cm3_s=0.0,
        dwarfs=42,
        self_conjugate=False,
        density_fraction=1.0,
    )
    monkeypatch.setattr(
        indirect,
        "spectral_comparison",
        lambda *_, **kw: indirect.SpectralComparison(ratio=0.5, limit=limit),
    )
    results = verdicts.judge(candidate, True)
    assert len(results) == 1 and results[0].constraint_id == dl.RECORD
    assert results[0].excluded is False and "not yet verified" in results[0].note
    monkeypatch.setattr(verdicts.annihilation, "sigma_v_today", lambda *_: {"b": 1e-26})
    results = verdicts.judge(candidate, True)
    assert len(results) == 1 and results[0].constraint_id == "fermi-1503.02641-dsph"
