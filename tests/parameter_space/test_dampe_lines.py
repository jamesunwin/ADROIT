"""DAMPE's γ-ray line search (arXiv:2112.08860, Tables S1–S2), staged for the owner's review (branch dampe-record)."""
import pytest

from adroit.constraints import searches as data
from adroit.parameter_space import searches
from adroit.parameter_space.classes import Point
from tests.parameter_space.test_line_energies import Lines
from tests.unsigned_records import as_unsigned

RECORD = "dampe-2112.08860-lines"


def test_the_record_is_the_printed_tables_weakest_profile_at_each_energy():
    d = data._bundled(RECORD)
    assert len(d["limit"]) == 72 and d["limit"][0] == [10.0, 7.9e-29] and d["limit"][-1] == [300.0, 3.6e-27]
    for profile in ("limit_einasto", "limit_nfw", "limit_isothermal"):
        own = dict(map(tuple, d[profile]))
        assert all(limit >= own[e] for e, limit in d["limit"] if e in own)
    hundred = {name: dict(map(tuple, d[name]))[100.0] for name in ("limit_einasto", "limit_nfw", "limit_isothermal")}
    assert hundred == {"limit_einasto": 2.0e-28, "limit_nfw": 5.0e-28, "limit_isothermal": 7.2e-28}
    assert dict(map(tuple, d["limit"]))[100.0] == 7.2e-28 and max(e for e, _ in d["limit_einasto"]) == 206.0


def test_unsigned_it_leaves_the_lines_it_covers_pending_and_none_outside(monkeypatch):
    as_unsigned(monkeypatch, (RECORD,))                    # as before the owner signs it
    assert not data._record(RECORD).usable
    result = searches.lines(Lines(1e-29, 0.0), Point(m_chi=50.0, m_med=1.0), False)
    assert result.excluded is None and RECORD in result.why
    curve = data._bundled(RECORD)["limit"]
    assert searches._line_comparison(RECORD, 1e-28, 0.0, 400.0) == (None, "outside the DAMPE curve")
    assert searches._line_ratio(RECORD, 2 * data.interpolate(curve, 50.0), 0.0, 50.0) == pytest.approx(2.0)


def test_a_z_gamma_line_is_one_photon_and_two_lines_in_one_window_wait():
    """A Zγ line at E = m − m_Z²/4m counts as 2(m/E)² times the γγ limit at E; two lines within the nominal fit
    window's half-width, 0.5 (0.5–1.5 E_line: m above m_Z/√2 = 64.5 GeV), are left to a joint likelihood. The
    recheck's RB20-06 (2026-10-20), its control: at m = 75 GeV the Zγ line (47.3 GeV) is 37% below the γγ line,
    inside the 75 GeV window [37.5, 112.5]; the 30% guard, from the systematic check's 0.7–1.3 window, had let the
    single-line comparison apply."""
    curve = data._bundled(RECORD)["limit"]
    m = 300.0
    energy = m - searches.M_Z ** 2 / (4 * m)
    expected = 1e-27 * 0.5 * (energy / m) ** 2 / data.interpolate(curve, energy)
    assert searches._line_ratio(RECORD, 0.0, 1e-27, m) == pytest.approx(expected)
    for m in (100.0, 75.0, 65.0):
        ratio, why = searches._line_comparison(RECORD, 1e-28, 1e-28, m)
        assert ratio is None and "overlapping DAMPE lines" in why, m
    assert searches.DAMPE_LINE_SEPARATION == 0.5
    ratio, why = searches._line_comparison(RECORD, 1e-28, 1e-28, 64.0)             # 50.6% apart: one line each
    assert ratio is not None and why == ""


def test_a_dirac_pair_and_the_halo_regions_density_scale_as_the_other_line_records():
    from adroit.parameter_space import halo_limits
    assert halo_limits.recorded_densities()[RECORD] == 0.4
    curve = data._bundled(RECORD)["limit"]
    gg = 0.9 * data.interpolate(curve, 40.0)
    majorana = searches.lines(Lines(gg, 0.0), Point(m_chi=40.0, m_med=1.0), True)
    dirac = searches.lines(Lines(gg, 0.0, self_conjugate=False), Point(m_chi=40.0, m_med=1.0), True)
    assert dirac.ratio == pytest.approx(majorana.ratio / 2)


def test_a_z_gamma_line_below_dampes_range_is_fermis_not_a_gap():
    """At m = 50 GeV the Zγ line is at 8.4 GeV, below DAMPE's 10 GeV: DAMPE judges the γγ line alone and leaves the
    Zγ one to Fermi-LAT, whose curve covers it (no pending reason from DAMPE)."""
    curve = data._bundled(RECORD)["limit"]
    ratio, why = searches._line_comparison(RECORD, 1e-29, 1e-29, 50.0)
    assert why == "" and ratio == pytest.approx(1e-29 / data.interpolate(curve, 50.0))


@pytest.mark.parametrize("record_id, prefix", [(RECORD, "dampe"), ("fermi-lat-1506.00013-lines", "fermi")])
def test_the_record_offered_for_review_states_the_guard_the_evaluator_applies(record_id, prefix):
    """The consistency audit's CA-09 (2026-10-24): DAMPE's record, offered for the owner's signature, said 30%
    (0.7–1.3 E_line) while the evaluator applies 50% (0.5–1.5 E_line) since RB20-06; at m = 75 GeV (37% apart) the
    record described a single-line comparison the evaluator leaves pending. The record's text is what is signed."""
    from adroit.constraints import database
    _, guard, _ = searches.RESOLVED_LINES[prefix]
    text = " ".join(database.record(record_id).assumptions)
    assert f"at most {guard:.0%}" in text
    if prefix == "dampe":
        assert f"{1 - guard:.1f}–{1 + guard:.1f} E_line, in which the background is fitted" in text
        assert "at most 30%" not in text
