"""R10: precomputed direct-detection limits, their currency, and verdicts identical to the direct calculation."""

import math
from types import SimpleNamespace

import pytest
import yaml

from adroit.parameter_space import dd_channels, limit_tables, limits

XENONNT = "XENONnT SR0+SR1"


@pytest.fixture
def tables(tmp_path, monkeypatch):
    """A folder of synthetic tables, current against a fixed fingerprint."""
    limits.clear_cache()
    monkeypatch.setattr(limit_tables, "TABLES", tmp_path)
    monkeypatch.setattr(limit_tables, "fingerprint", lambda module: "f" * 64)

    def write(module, kind, masses, values, accuracy=0.001, fingerprint="f" * 64):
        (tmp_path / f"{limit_tables.slug(module, kind)}.yaml").write_text(yaml.safe_dump(
            {"module": module, "kind": kind, "masses_gev": masses, "limits_cm2": values,
             "interpolation_accuracy": accuracy, "fingerprint": fingerprint}))
        limit_tables._stored_at.cache_clear()
    yield write
    monkeypatch.undo()
    limits.clear_cache()


def _clear_patched() -> None:
    limits._per_module95.cache_clear()
    limits._at95.cache_clear()
    limit_tables._stored_at.cache_clear()


def test_a_table_is_interpolated_in_log_mass_and_log_limit(tables):
    tables(XENONNT, "SI", [10.0, 1000.0], [1e-46, 1e-44])
    value, eta = limit_tables.lookup(XENONNT, "SI", 100.0)
    assert value == pytest.approx(1e-45, rel=1e-9) and eta == limit_tables.TOLERANCE_FLOOR
    assert limit_tables.lookup(XENONNT, "SI", 5.0) is None and limit_tables.lookup(XENONNT, "SD-proton", 100.0) is None
    tables(XENONNT, "SD-proton", [10.0, 1000.0], [1e-41, 1e-39], accuracy=0.01)
    assert limit_tables.lookup(XENONNT, "SD-proton", 100.0)[1] == pytest.approx(0.02)       # η = 2ε


def test_a_stale_table_is_never_used(tables):
    tables(XENONNT, "SI", [10.0, 1000.0], [1e-46, 1e-44], fingerprint="0" * 64)
    assert limit_tables.table(XENONNT, "SI") is None and limit_tables.lookup(XENONNT, "SI", 100.0) is None
    assert limit_tables.current() == []


@pytest.mark.needs("diamx")
def test_the_fingerprint_covers_the_rate_code_and_diamx():
    from adroit.experiments import registry
    limit_tables.fingerprint.cache_clear()
    assert len(limit_tables.fingerprint(XENONNT)) == 64
    assert limit_tables.ROOT / "physics" in limit_tables.CODE
    assert getattr(registry.load_module(XENONNT), "folder", None) is not None
    limit_tables.fingerprint.cache_clear()


def test_per_module_limits_come_from_a_table_unless_exact_limits_are_asked_for(tables, monkeypatch):
    from adroit.experiments import registry
    tables(XENONNT, "SI", [10.0, 1000.0], [1e-46, 1e-44])
    _clear_patched()
    direct = SimpleNamespace(reference_limits=lambda kind, masses, workers=1, cl=0.9: [1e-40])
    monkeypatch.setattr(registry, "load_module", lambda name: direct)
    tabulated = dict(limits.per_module95("SI", 100.0)[0])
    assert tabulated[XENONNT] == pytest.approx(1e-45, rel=1e-6)
    with limits.exact():
        assert dict(limits.per_module95("SI", 100.0)[0])[XENONNT] == 1e-40
        assert limits.tolerance(XENONNT, "SI", 100.0) == 0.0
    with limits.exact_environment():
        assert not limits.tabulated()
    assert limits.tabulated() and "precomputed table" in limits.at95("SI", 100.0).construction


@pytest.fixture
def two_limits(monkeypatch):
    """One module whose tabulated SI limit differs from its direct one by 1%; counts the direct comparisons."""
    calls = []

    def per_module95(kind, mass, excluded_modules=()):
        calls.append(limits.tabulated())
        return ((XENONNT, 1.0e-45 if limits.tabulated() else 1.01e-45),), ()
    limits.clear_cache()
    monkeypatch.setattr(limits, "per_module95", per_module95)
    monkeypatch.setattr(limits, "tolerance", lambda module, kind, mass: 0.02 if limits.tabulated() else 0.0)
    yield calls
    monkeypatch.undo()
    limits.clear_cache()


def test_a_point_near_the_limit_is_compared_again_directly(two_limits):
    """σ/limit is 1.005 with the table and 0.995 directly: the verdict is the direct one (allowed)."""
    channel = dd_channels.Channel(kind="SI", sigma_cm2=1.005e-45)
    outcome = dd_channels.compare([channel], 100.0)
    assert outcome.excluded is False and False in two_limits


def test_a_point_far_from_the_limit_keeps_the_tabulated_comparison(two_limits):
    outcome = dd_channels.compare([dd_channels.Channel(kind="SI", sigma_cm2=3e-45)], 100.0)
    assert outcome.excluded is True and all(two_limits)


def test_tovey_s_difference_is_clear_only_if_its_whole_range_is_on_one_side():
    assert dd_channels._clear_difference(9.0, 1.0, 0.01, 0.01, 1.0)                     # √r − √s = 2
    assert not dd_channels._clear_difference(4.0, 1.0, 0.05, 0.05, 1.0)                 # = 1, on the threshold
    assert dd_channels._clear_difference(1.0, 1.0, 0.05, 0.05, 1.0)                     # near 0: |d| < 1 throughout
    assert dd_channels._clear(1.03, 0.02) and not dd_channels._clear(1.01, 0.02) and dd_channels._clear(0.97, 0.02)
    assert not math.isnan(limit_tables.TOLERANCE_FLOOR)


def test_exact_limits_leave_an_unset_request_s_identity_unchanged():
    from adroit.orchestrator.track1 import for_portal
    request = for_portal("higgs_portal_scalar")
    assert "exact_limits" not in request.model_dump(mode="json")
    assert request.model_copy(update={"exact_limits": True}).model_dump(mode="json")["exact_limits"] is True


def test_the_spline_reproduces_a_smooth_curve_and_its_accuracy_is_measured_by_leaving_masses_out():
    masses = [10.0 * 1.33 ** k for k in range(12)]
    values = [1e-46 * (m / 10.0) ** 1.2 * (1 + (12.0 / m) ** 3) for m in masses]
    errors = limit_tables.leave_one_out(masses, values)
    assert len(errors) == 10 and max(abs(e) for e in errors) < 0.02
    curve = limit_tables.spline(masses, values)
    exact = 1e-46 * (50.0 / 10.0) ** 1.2 * (1 + (12.0 / 50.0) ** 3)
    assert math.exp(curve(math.log(50.0))) == pytest.approx(exact, rel=max(abs(e) for e in errors))


@pytest.mark.needs("diamx", "cdmslite")
def test_every_stored_table_is_current_and_accurate():
    """The tables in the package match the installed code (else they are ignored); the spline predicts each left-out
    mass to 5% except where the limit is steep, |d ln σ / d ln m| > 5 (a kinematic threshold, where the local tolerance
    sends the point to the exact calculation)."""
    limit_tables.clear_cache()
    for path in sorted(limit_tables.TABLES.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        assert limit_tables.table(data["module"], data["kind"]) is not None, f"{path.name} is stale: retabulate"
        masses, limits, errors = data["masses_gev"], data["limits_cm2"], data["leave_one_out"]
        assert len(masses) == len(limits) == len(errors) + 2 >= 5 and data["batch_vs_single_run"] < 1e-6
        assert data["interpolation_accuracy"] == pytest.approx(max(abs(e) for e in errors), abs=1e-4)
        for i, error in enumerate(errors, 1):
            slope = abs(math.log(limits[i + 1] / limits[i - 1]) / math.log(masses[i + 1] / masses[i - 1]))
            assert abs(error) < 0.05 or slope > 5, f"{path.name}: {error:.1%} at {masses[i]} GeV"


def test_the_tolerance_is_local_so_a_steep_threshold_costs_exact_calculations_only_there():
    data = {"masses_gev": [1.0, 2.0, 3.0, 4.0, 5.0], "leave_one_out": [0.9, 0.01, 0.002],
            "interpolation_accuracy": 0.9}
    assert limit_tables.tolerance(data, 1.5) == pytest.approx(1.8)            # next to the badly predicted mass
    assert limit_tables.tolerance(data, 3.5) == pytest.approx(0.02)
    assert limit_tables.tolerance(data, 4.5) == limit_tables.TOLERANCE_FLOOR   # 2 × 0.002 is below the floor
    assert limit_tables.tolerance(data) == pytest.approx(1.8)                  # without a mass: the largest


def test_the_native_certificate_is_not_an_input_so_its_reissue_leaves_the_tables_current():
    """The native likelihood's certificate holds byte hashes of rates.py, halo.py, pico60.py, …, so a docstring edit
    there re-issues it (2026-10-12). No tabulated limit reads it; were it fingerprinted, every table would go stale."""
    assert limit_tables.NOT_INPUTS == ("native_pico_si_validation.yaml",)

    def altered(path):
        return b"re-issued" if path.name in limit_tables.NOT_INPUTS else limit_tables._content(path)
    module = "PICO-60 C3F8 (2019)"
    assert limit_tables._digest(module, altered) == limit_tables._digest(module, limit_tables._content)
