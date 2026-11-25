"""Mass identities survive close spacing and JSON serialization without rounding."""
import numpy as np
import pytest

from adroit.core.dm_state import DarkMatterParticle
from adroit.orchestrator import exclusion, signal, user_models
from adroit.parameter_space import simplified


def test_distinct_masses_with_identical_display_labels():
    masses = [10.650410894399627, 10.650410894399629]
    rows = user_models.candidates(simplified.model("vector", 10, 1000), masses)
    assert rows[0].label != rows[1].label
    assert rows[0].display_label == rows[1].display_label
    request = exclusion.ExclusionRequest(bespoke={repr(c.mass_gev): c.interaction for c in rows})
    request = exclusion.ExclusionRequest.model_validate_json(request.model_dump_json())
    for c in rows:
        assert exclusion.interaction_at(request, DarkMatterParticle(mass_gev=c.mass_gev)) == c.interaction
    with pytest.raises(KeyError, match="exact"):
        exclusion.interaction_at(request, DarkMatterParticle(mass_gev=10.6504))
    with pytest.raises(ValueError, match="unique"):
        exclusion.ExclusionRequest(bespoke={"10": rows[0].interaction, "10.0": rows[1].interaction})


def test_audit_twelve_mass_user_model_grid_completes():
    request = signal.SignalRequest(experiment="CDMS II Si (2013)",
        user_models=[signal.UserModel(spec=simplified.model("vector", 10, 1000),
                                    masses_gev=np.geomspace(5, 40, 12).tolist())],
        null_modules=["DEAP-3600 (2019)"], leaders=12, toys=40, complementary=False)
    result = signal.run(request)
    assert len(result.fits) == 12 and not result.candidate_failures
    assert result.combinations
    restored = signal.SignalResult.model_validate_json(result.model_dump_json())
    assert restored.classes == result.classes


def test_failure_of_one_null_calculation_preserves_the_fits(monkeypatch):
    def fail(_):
        raise KeyError("missing exact mass")
    monkeypatch.setattr(exclusion, "run", fail)
    request = signal.SignalRequest(experiment="CDMS II Si (2013)",
        candidates=[signal.Candidate(label="O1s@10", card_id="O1", isospin="s", mass_gev=10)],
        null_modules=["DEAP-3600 (2019)"], toys=20, complementary=False)
    result = signal.run(request)
    assert result.fits and "O1s@10" in result.candidate_failures
    assert result.combinations[0].null_coverage == "none"
    assert any("pending" in flag for row in result.tournament.ranking for flag in row.flags)
    assert "missing exact mass" in signal.report(result)


def test_failure_of_one_signal_preserves_other_candidates(monkeypatch):
    original = signal._signal
    def predict(module, candidate, *a, **kw):
        if candidate.label == "failed":
            raise ValueError("bad spectrum")
        return original(module, candidate, *a, **kw)
    monkeypatch.setattr(signal, "_signal", predict)
    request = signal.SignalRequest(experiment="CDMS II Si (2013)", null_modules=[], toys=20, complementary=False,
        candidates=[signal.Candidate(label=name, card_id="O1", isospin="s", mass_gev=mass)
                    for name, mass in [("failed", 9), ("completed", 10)]])
    result = signal.run(request)
    assert [f.label for f in result.fits] == ["completed"]
    assert result.candidate_failures == {"failed": "signal fit failed: ValueError: bad spectrum"}
    assert "conditional on completed" in result.global_method


def test_library_identifiers_also_preserve_close_masses():
    masses = [10.650410894399627, 10.650410894399629]
    candidates = signal.library_model_space(masses)
    assert len({c.label for c in candidates}) == len(candidates)
