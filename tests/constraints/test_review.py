"""The review of constraint records: curves, plots and the written verification (constraints.review)."""

from datetime import date

import pytest

from adroit.constraints import database, review


@pytest.fixture
def copy(tmp_path, monkeypatch):
    path = tmp_path / "records.yaml"
    path.write_text(database.RECORDS.read_text())
    monkeypatch.setattr(database, "RECORDS", path)
    database.records.cache_clear()
    yield path
    database.records.cache_clear()


def test_each_record_shows_only_its_own_curves():
    v1 = review.curves(database.record("cms-2405.13778-V1"))
    assert v1 and all("V1" in c.label for c in v1)
    sd = review.curves(database.record("icecube-1612.05949-sd"))
    assert len(sd) == 3 and all("SD" in c.label for c in sd)
    squark = review.curves(database.record("atlas-2010.14293-squark"))
    assert squark[0].x[0] == 1220.0 and "m_lsp" in squark[0].label
    assert review.curves(database.record("lep-contact-bl")) == []


def test_every_record_names_the_figure_to_compare_with():
    assert all(r.figure is not None and r.figure.page >= 1 for r in database.records())


def test_a_plot_is_drawn_for_a_record_with_curves(tmp_path):
    assert review.plot(database.record("fermi-1503.02641-dsph"), tmp_path / "f.png").stat().st_size > 1000
    assert review.plot(database.record("muon-g2-2025"), tmp_path / "g.png") is None


def test_a_verification_is_written_into_the_record_and_only_once(copy):
    """On a record that carries no signature yet: which ones do depends on the owner's signing, not on this test."""
    target = next((r.id for r in database.records() if not r.verified_by and r.id != "muon-g2-2025"), None)
    if target is None:
        pytest.skip("every record is signed")
    before = copy.read_text()
    review.verify(target, "A. Physicist", on=date(2026, 10, 4))
    after = copy.read_text()
    assert after.count("\n") == before.count("\n") + 3
    assert database.record(target).verification_sha256
    assert database.record(target).usable and database.record(target).verified_by == "A. Physicist"
    with pytest.raises(ValueError):
        review.verify(target, "Someone else")
    with pytest.raises(ValueError):
        review.verify("muon-g2-2025", "  ")
    with pytest.raises(ValueError):
        review.verify("no-such-record", "A. Physicist")


@pytest.mark.parametrize("record_id,first,second", [
    ("atlas-1910.08447-dijet-gaussian", "gaussian_limits", "zprime_acceptance"),
    ("atlas-1903.06248-dilepton", "limit_fb", "sigma_"),
    pytest.param("lmu-ltau-babar-belle2", "g_prime", "BaBar_", marks=pytest.mark.needs("darkcast"))])   # its BaBar curve
def test_different_quantities_are_drawn_on_separate_panels(record_id, first, second, tmp_path):
    """The owner's data audit (2026-10-12): a limit and an acceptance (or a prediction, or another coupling) never share
    an axis, and no curve is dropped."""
    record = database.record(record_id)
    groups = review.panels(record)
    assert all(c.label.startswith(first) for c in groups[0][1]) and all(c.label.startswith(second) for c in groups[1][1])
    plotted = {c.label for _, group, _ in groups for c in group}
    assert {c.label for c in review.curves(record)} <= plotted
    assert review.plot(record, tmp_path / "p.png").stat().st_size > 1000


def test_the_acceptance_axis_is_linear_and_the_dilepton_correction_is_shown_beside_its_ratio():
    dijet = review.panels(database.record("atlas-1910.08447-dijet-gaussian"))
    assert [log for _, _, log in dijet] == [True, False] and "dimensionless" in dijet[1][0]
    label, ratio, log = review.panels(database.record("atlas-1903.06248-dilepton"))[-1]
    assert label.startswith("derived") and not log and ratio[1].y == [1.087, 1.087]
    assert ratio[0].y[-1] == pytest.approx(0.578, abs=0.01)                    # at 6 TeV


def test_a_record_of_one_quantity_keeps_one_panel():
    assert len(review.panels(database.record("fermi-1503.02641-dsph"))) == 1


def test_the_f_eff_plot_draws_only_tabulated_masses():
    """Slatyer's zeros below a channel's threshold mean "not computed": the record's plot leaves them out."""
    from adroit.constraints import searches
    if searches.f_eff_table() is None:
        pytest.skip("Slatyer's f_eff tables are not in the tools folder")
    curves = {c.label: c for c in review.curves(database.record("planck-2018-pann"))}
    ww = curves["f_eff W^+W^-"]
    assert min(ww.x) == 90.0 and min(ww.y) > 0
    assert all(min(c.y) > 0 for label, c in curves.items() if label.startswith("f_eff"))


def test_a_value_is_quoted_to_its_uncertaintys_decimal_place():
    """The owner (2026-10-13): Planck's Ω_c h² showed as 0.12 beside 0.0012 (YAML keeps no trailing zeros)."""
    assert review.quoted({"value": 0.12, "sigma": 0.0012}) == ["value = 0.1200 ± 0.0012"]
    assert review.quoted({"value": 0.11933, "sigma": 0.00091}) == ["value = 0.11933 ± 0.00091"]
    assert review.quoted({"delta": 38.0, "delta_sigma": 63.0, "limit": 3.2e-28}) == ["delta = 38 ± 63", "limit = 3.2e-28"]


def test_a_curve_the_tools_folder_cannot_supply_is_named_not_dropped(monkeypatch, tmp_path):
    """The fallback review's D4: without DarkCast, L_μ − L_τ's figure lost BaBar's curve without a word."""
    import matplotlib.figure

    from adroit.constraints import searches
    monkeypatch.setattr(searches, "_tool", lambda name: None)
    lmu = database.record("lmu-ltau-babar-belle2")
    assert review.missing_curves(lmu) == [
        "BaBar's curve (from DarkCast, which is not in the tools folder: `adroit setup --fetch`)"]
    assert not any(c.label.startswith("BaBar_") for c in review.curves(lmu))
    seen = []
    text = matplotlib.figure.Figure.text
    monkeypatch.setattr(matplotlib.figure.Figure, "text",
                        lambda self, x, y, s, *a, **k: seen.append(s) or text(self, x, y, s, *a, **k))
    assert review.plot(lmu, tmp_path / "lmu.png") is not None             # Belle II's curve, with the note under it
    assert seen == ["Not shown: BaBar's curve (from DarkCast, which is not in the tools folder: "
                    "`adroit setup --fetch`)"]
    assert review.missing_curves(database.record("darkcast-dark-photon"))[0].startswith(
        "every search's excluded region (from DarkCast")
    assert review.missing_curves(database.record("planck-2018-pann"))[0].startswith("the f_eff curves")
    assert review.missing_curves(database.record("fermi-1503.02641-dsph")) == []


@pytest.mark.needs("darkcast")
def test_with_darkcast_installed_no_curve_is_missing():
    assert review.missing_curves(database.record("lmu-ltau-babar-belle2")) == []
    assert review.missing_curves(database.record("darkcast-dark-photon")) == []
