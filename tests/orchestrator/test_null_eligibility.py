"""The audit's out-of-domain DEAP number cannot suppress a signal."""
import pytest

from adroit.inference import dm_tournament
from adroit.orchestrator import signal


def test_audit_deap_point_is_omitted_with_evidence():
    candidate = signal.Candidate(label="O1s@30", card_id="O1", isospin="s", mass_gev=30)
    request = signal.SignalRequest(experiment="CDMS II Si (2013)", null_modules=["DEAP-3600 (2019)"])
    result = signal.combine(request, candidate)
    # 1.6764 before the audit's A09; 1.684063 before R17-3 (2026-10-17), whose exact smearing moved it by 3·10⁻⁵
    assert result.z_signal == pytest.approx(1.6840074749697722, rel=1e-5)
    assert result.z_joint == pytest.approx(result.z_signal, rel=1e-6)
    assert not result.null_limits and result.null_coverage == "none"
    assert "validated" in result.omitted_nulls["DEAP-3600 (2019)"]
    ranking = dm_tournament.run([result])
    row = next(r for r in ranking.ranking if r.label == candidate.label)
    assert row.null_coverage == "none" and row.omitted_nulls == result.omitted_nulls
    assert "pending" in row.flags[0]


def test_valid_deap_limit_still_contributes():
    candidate = signal.Candidate(label="O1s@100", card_id="O1", isospin="s", mass_gev=100)
    result = signal.combine(signal.SignalRequest(experiment="CDMS II Si (2013)",
                            null_modules=["DEAP-3600 (2019)"]), candidate)
    assert result.null_limits["DEAP-3600 (2019)"] > 0
    assert result.null_coverage == "complete" and not result.omitted_nulls
    assert result.z_joint < result.z_signal
