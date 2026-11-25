"""DM14: anomaly records — the schema, the consistency check, digitiser files and the module they make."""

import numpy as np
import pytest
import yaml

from adroit.core.dm_state import DarkMatterParticle
from adroit.experiments import anomaly, historical, registry
from adroit.library.interactions import registry as cards
from adroit.orchestrator import signal

SEEDED = {
    "an event outside the window": lambda r: r.update(events_kev=[*r["events_kev"], 150.0]),
    "an efficiency above one": lambda r: r["efficiency"]["points"].update(efficiency=[0.2, 1.4, 0.5]),
    "a reversed window": lambda r: r.update(window_kev=[50.0, 5.0]),
    "an unknown target": lambda r: r.update(target="Unobtainium"),
    "a halo in m/s": lambda r: r["halo"].update(v0_km_s=220000.0),
    "decreasing efficiency energies": lambda r: r["efficiency"]["points"].update(recoil_energy_kev=[50.0, 10.0, 5.0]),
    "a downward error above the background": lambda r: r["background_uncertainty"].update(minus=[0.9]),
    "no references": lambda r: r.update(references=[]),
}


def template() -> dict:
    return yaml.safe_load(anomaly.template())


@pytest.mark.parametrize("key", historical.records())
def test_the_historical_records_are_valid_records_with_no_problems(key: str) -> None:
    assert anomaly.check(anomaly.AnomalyRecord.model_validate(historical.record(key))) == []


def test_the_template_is_a_valid_draft() -> None:
    record = anomaly.AnomalyRecord.model_validate(template())
    assert anomaly.check(record) == [] and record.verified_by == ""


@pytest.mark.parametrize("error", sorted(SEEDED))
def test_each_seeded_error_is_caught(error: str) -> None:
    data = template()
    SEEDED[error](data)
    assert anomaly.check(anomaly.AnomalyRecord.model_validate(data)), error


def test_the_efficiency_is_given_exactly_one_way() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        anomaly.Efficiency(digitised="a", csv="b.csv")


def test_a_digitiser_csv_is_read_sorted_without_headers_or_duplicates(tmp_path) -> None:
    path = tmp_path / "eff.csv"
    path.write_text("x,y\n20, 0.5\n5,0.1\n10,0.3\n10,0.3\n")
    curve = anomaly.read_curve(path)
    assert curve.recoil_energy_kev == [5.0, 10.0, 20.0] and curve.efficiency == [0.1, 0.3, 0.5]


def _copy_of_cdms_si(tmp_path, verified: str = "a person") -> str:
    """The built-in CDMS II Si record, rewritten as a user's file with its efficiency as a CSV."""
    data = dict(historical.record("cdms_ii_si_2013"))
    table = historical.digitised.load(data["efficiency"]["digitised"])
    rows = "\n".join(f"{e},{x}" for e, x in zip(table["recoil_energy_kev"], table["efficiency"]))
    (tmp_path / "efficiency.csv").write_text(rows)
    data.update(efficiency={"csv": "efficiency.csv"}, verified_by=verified)
    path = tmp_path / "cdms_si.yaml"
    path.write_text(yaml.safe_dump(data))
    return f"record:{path}"


def test_a_record_file_gives_the_same_signal_as_the_built_in_module(tmp_path) -> None:
    user = registry.load_module(_copy_of_cdms_si(tmp_path))
    built_in = registry.load_module("CDMS II Si (2013)")
    particle = DarkMatterParticle(mass_gev=8.6)
    interaction = cards.resolve("O1", particle, {"c_p": 1e-8, "c_n": 1e-8})
    a = user.expected_signal(particle, interaction, user.conventions().halo, user.conventions().nuclear_model)
    b = built_in.expected_signal(particle, interaction, built_in.conventions().halo,
                                 built_in.conventions().nuclear_model)
    assert a.total_events == pytest.approx(b.total_events, rel=1e-3)
    assert np.array_equal(user.observations()[0], built_in.observations()[0])
    assert user.background_rate().total == pytest.approx(built_in.background_rate().total)
    assert user.verified


def test_path_two_refuses_an_unverified_record(tmp_path) -> None:
    name = _copy_of_cdms_si(tmp_path, verified="")
    with pytest.raises(ValueError, match="not been verified"):
        signal.run(signal.SignalRequest(experiment=name, null_modules=[]))


@pytest.mark.parametrize("edges,counts,ok", [([0.0, 20.0, 200.0], [3.0, 1.0], True),
                                             ([10.0, 20.0, 40.0], [3.0, 1.0], False),       # misses the window
                                             ([0.0, 20.0, 200.0], [3.0, 0.0], False),       # a zero count
                                             ([0.0, 200.0, 20.0], [3.0, 1.0], False)])      # not increasing
def test_a_records_inline_background_bins_are_checked_as_the_intake_checks_them(edges, counts, ok) -> None:
    """Release audit minor: a record: file's bins were extended flat and zero counts allowed."""
    data = template()
    data["background_shape"] = {"points": {"edges_kev": edges, "counts": counts}}
    if ok:
        anomaly.AnomalyRecord.model_validate(data)
    else:
        with pytest.raises(ValueError, match="background"):
            anomaly.AnomalyRecord.model_validate(data)
