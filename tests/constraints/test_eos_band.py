"""The equation of state's band (the owner's decision #3, 2026-10-20): Saikawa & Shirai's 2020 tables, fetched by
``adroit setup --fetch`` and checked against their published hashes (not shipped: the release audit's PR23-05), and
the labelled context the relic solves and their caches read (``relic.eos_variant``)."""
import shutil

import pytest

from adroit.constraints import relic
from adroit.parameter_space import library



@pytest.mark.needs("eos")
def test_the_three_tables_are_the_published_files_and_a_changed_one_is_refused(tmp_path, monkeypatch):
    for name in relic.EOS_TABLES:
        g, h, root_g = relic.eos_table(name)(0.15)            # near the QCD transition
        assert 10 < g < 80 and 10 < h < 80 and root_g > 0
    for name, (file, _) in relic.EOS_TABLES.items():
        shutil.copyfile(relic.eos_folder() / file, tmp_path / file)
    (tmp_path / "eos2020_err1.dat").write_text((tmp_path / "eos2020_err1.dat").read_text().replace("3.93487", "3.9349"))
    monkeypatch.setattr(relic, "eos_folder", lambda: tmp_path)
    relic.eos_table.cache_clear()
    try:
        assert relic.eos_table("lower")(1.0)
        with pytest.raises(ValueError, match="sha256 differs"):
            relic.eos_table("upper")
    finally:
        relic.eos_table.cache_clear()


@pytest.mark.needs("eos")
def test_the_label_follows_the_table_in_use_and_is_restored():
    assert relic.current_eos() == ""
    with relic.eos_variant("upper"):
        assert relic.current_eos() == "ss2020-upper"
        with relic.low_temperature_history():
            assert relic.current_eos() == "ss2020-upper+decoupled-neutrinos"     # its table kept above 1 MeV
        assert relic.current_eos() == "ss2020-upper"
    assert relic.current_eos() == ""


@pytest.mark.needs("eos")
def test_the_band_moves_a_library_relic_as_the_study_found():
    """The study at the 256 crossings (2026-10-20): the upper table lowers Ωh² by 1–5.5%, the lower raises it by
    1–6.5%; the 2020 central table is within 1% of the 2018 fit ADROIT keeps as nominal."""
    e = library.entry("dmwg_V1")
    nominal = e.model_class.omega_h2(e.point)
    shifted = {}
    for name in relic.EOS_TABLES:
        with relic.eos_variant(name):
            shifted[name] = e.model_class.omega_h2(e.point) / nominal - 1
    assert -0.06 < shifted["upper"] < -0.01 and 0.01 < shifted["lower"] < 0.07 and abs(shifted["central"]) < 0.01


@pytest.mark.needs("eos")
def test_the_generic_routes_freeze_out_is_cached_per_table():
    from adroit.parameter_space.portals import generic
    from tests.parameter_space.test_generic_generations import MIXED, _model
    engine = _model([100.0, 130.0], MIXED)
    p = engine.point()
    args = (engine.spec_json, engine.scan, engine.tied, p.m_chi, p.m_med)
    nominal = generic._freeze_out(*args)
    with relic.eos_variant("lower"):
        lower = generic._freeze_out(*args)
    assert nominal is not None and lower is not None and lower != nominal
    assert generic._freeze_out(*args) == nominal


def test_without_the_tables_the_band_is_named_not_computed(monkeypatch):
    """The release audit's PR23-05 (2026-10-23; the owner's decision): the tables are fetched, not shipped, since their
    page states no redistribution terms. Without them a table is refused with how to get it, and the band's
    reason names the setup command, so a decided crossing waits for it rather than standing on the nominal alone."""
    from adroit.parameter_space import verdict
    monkeypatch.setattr(relic, "eos_folder", lambda: None)
    relic.eos_table.cache_clear()
    try:
        with pytest.raises(relic.EosUnavailable, match="adroit setup --fetch --only 'Saikawa-Shirai relic"):
            relic.eos_table("upper")
        assert "not computed" in verdict._eos_missing() and "adroit setup --fetch" in verdict._eos_missing()
    finally:
        relic.eos_table.cache_clear()
    assert not (relic.Path(relic.__file__).parent / "data" / "eos").exists()
