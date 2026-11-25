"""The auditor's EOS review (2026-11-23): the low-temperature comparison (``relic.thermal_history_reason``) replaced the
equation of state in force with the nominal one above 1 MeV as well, so it attributed a change of table to the
history below 1 MeV. The owner's synthetic control: nominal g_eff = 10, the table in force g_eff = 12, an observable
that reads only T = 0.1 GeV, 0.12 × 12 / g_eff(0.1): 0.12 as computed, 0.144 in the comparison, a false 20%."""
import pytest

from adroit.constraints import relic


def flat(value: float):
    def dof(temperature: float) -> tuple[float, float, float]:
        return value, value, value ** 0.5
    return dof


@pytest.fixture
def nominal_ten(monkeypatch):
    monkeypatch.setattr(relic, "degrees_of_freedom", flat(10.0))


def at_100_mev() -> float:
    return 0.12 * 12.0 / relic._dof(0.1)[0]


def test_the_table_in_force_is_kept_above_1_mev(nominal_ten) -> None:
    with relic.equation_of_state(flat(12.0), label="synthetic-12"):
        assert at_100_mev() == pytest.approx(0.12)
        with relic.low_temperature_history():
            assert at_100_mev() == pytest.approx(0.12)              # was 0.144: the nominal g_eff = 10 above 1 MeV
            assert relic.current_eos() == "synthetic-12+decoupled-neutrinos"
        assert relic.thermal_history_reason(at_100_mev, m=1.0) == ""      # was a 20% "below 1 MeV" warning
        assert relic.current_eos() == "synthetic-12"
    assert relic.current_eos() == ""


def test_a_genuinely_low_temperature_observable_still_warns(nominal_ten) -> None:
    def at_10_kev() -> float:
        return 0.12 * relic._dof(1e-5)[0] / 12.0                   # reads only below 1 MeV
    with relic.equation_of_state(flat(12.0), label="synthetic-12"):
        why = relic.thermal_history_reason(at_10_kev, m=1.0)
    assert "below 1 MeV" in why


def test_the_nominal_comparison_is_as_before_and_contexts_are_restored(nominal_ten) -> None:
    with relic.low_temperature_history():
        assert relic.current_eos() == "decoupled-neutrinos"          # the label on the nominal, as before
        assert relic._dof(0.1)[0] == 10.0 and relic._dof(1e-5)[0] < 4.0
        with relic.equation_of_state(flat(12.0), label="inner"), relic.low_temperature_history():
            assert relic.current_eos() == "inner+decoupled-neutrinos" and relic._dof(0.1)[0] == 12.0
        assert relic.current_eos() == "decoupled-neutrinos"
    with pytest.raises(RuntimeError):
        with relic.equation_of_state(flat(12.0), label="raising"), relic.low_temperature_history():
            raise RuntimeError("inside")
    assert relic.current_eos() == "" and relic._dof(0.1)[0] == 10.0
