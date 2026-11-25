"""The single-idea study's thermal points carry the same certificate as the plane's roots (the consolidation plan's
M1, 2026-10-25), and its headline follows D-2: a waiting thermal point that its computed constraints exclude does not
make the headline "viable, pending"."""
import pytest

from adroit.constraints import relic
from tests.orchestrator.test_single_idea_eos import _study


@pytest.mark.eos_band
@pytest.mark.parametrize("excluded_above, level", [(1.0, "undetermined"), (100.0, "viable_pending")])
def test_without_the_tables_the_headline_rests_on_what_the_waiting_points_constraints_gave(tmp_path, monkeypatch,
                                                                                           excluded_above, level):
    monkeypatch.setattr(relic, "eos_folder", lambda: None)
    result = _study(tmp_path, excluded_above=excluded_above)
    assert result.thermal and all(t.status == "pending" for t in result.thermal)
    assert result.level == level
    computed = "excluded" if excluded_above < 20 else "viable"
    for t in result.thermal:
        assert t.certificate.claim_kind == "thermal_solution" and t.certificate.computed_status == computed
        assert t.certificate.check("eos_band").state == "unknown" and "adroit setup --fetch" in t.certificate.check(
            "eos_band").reason
    if level == "undetermined":
        assert "excluded by its computed constraints" in result.summary
        assert all(t.certificate.computed_excluded_by == ["toy"] for t in result.thermal)


@pytest.mark.eos_band
@pytest.mark.needs("eos")
def test_with_the_tables_agreeing_a_thermal_point_is_certified(tmp_path):
    result = _study(tmp_path, excluded_above=100.0)
    assert [t.status for t in result.thermal] == ["viable"] and result.level == "viable"
    certificate = result.thermal[0].certificate
    assert certificate.decided and certificate.check("eos_band").state == "satisfied"
    assert [c.name for c in certificate.checks] == ["root", "eos_band", "thermal_history", "finite_comparisons",
                                                    "records", "discovery", "halo"]
    assert certificate.check("discovery").state == "not_applicable"
