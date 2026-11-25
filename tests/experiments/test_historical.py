import math

import numpy as np
import pytest

from adroit.experiments import historical, registry


def test_each_record_is_a_signal_search_and_not_a_default_null() -> None:
    names = {historical.record(k)["name"] for k in historical.records()}
    assert {"CDMS II Si (2013)", "CDMS II Ge (2009)"} <= names
    assert names <= set(registry.signal_search_names())
    assert not names & set(registry.module_names())


@pytest.mark.parametrize("name", ["CDMS II Si (2013)", "CDMS II Ge (2009)"])
def test_the_module_gives_what_path_two_needs(name: str) -> None:
    module = registry.load_module(name)
    events, sigma = module.observations()
    grid = module.signal_grid_kev()
    low, high = module.info.energy_window_kev
    assert np.all((events >= low) & (events <= high)) and sigma.shape == events.shape
    expected = np.trapezoid(module.background_on_grid(), grid)
    assert expected == pytest.approx(module.record["background_events"], rel=0.01)
    assert 0.0 <= module.efficiency.min() and module.efficiency.max() <= 1.0


@pytest.mark.parametrize("name, tolerance", [pytest.param("CDMS II Si (2013)", 1.1, marks=pytest.mark.needs("optimum_interval")),
                                             ("CDMS II Ge (2009)", 1.1)])
def test_the_module_reproduces_the_numbers_its_paper_quotes(name: str, tolerance: float) -> None:
    for check in registry.load_module(name).quoted_checks():
        assert 1 / tolerance <= check["ratio"] <= tolerance, check


def test_a_binned_background_shape_follows_its_counts() -> None:
    module = registry.load_module("CDMS II Si (2013)")
    shape = historical.digitised.load(module.record["background_shape"]["digitised"])
    counts = shape["surface_events_failing_timing"]
    b = module.background_at(np.array([10.0, 25.0, 60.0]))
    total = module.record["background_events"]
    assert b[0] == pytest.approx(total * counts[0] / sum(counts) / 13.0)
    assert b[1] == pytest.approx(total * counts[1] / sum(counts) / 10.0)
    assert b[2] == pytest.approx(total * counts[2] / sum(counts) / 70.0)
    assert shape["candidates_passing_timing"] == [3, 0, 0]       # the paper's three candidates


def test_a_record_without_a_shape_has_a_flat_background() -> None:
    module = registry.load_module("CDMS II Ge (2009)")
    b = module.background_on_grid()
    assert np.allclose(b, b[0])


def test_a_stated_background_uncertainty_becomes_a_rate() -> None:
    rate = registry.load_module("CDMS II Si (2013)").background_rate()
    assert rate.free and rate.total == pytest.approx(0.41, rel=0.01)
    assert rate.plus == pytest.approx(math.hypot(0.20, 0.28) / 0.41, rel=1e-6)
    assert rate.minus == pytest.approx(math.hypot(0.08, 0.24) / 0.41, rel=1e-6)
