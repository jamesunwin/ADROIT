"""The owner's review of the unsigned records (2026-11-06), before signing: Escudero et al.'s N_eff contours held what
the PDF draws only inside its frames; LHCb's map holds 41 lifetimes, 0.1–1000 ps, not bands to 1260 ps, is shown on
the record's page, and the a's lifetime and BR(μμ) count its photon width; the type-II charged Higgs's B → X_s γ bound
is re-sourced to arXiv:2412.04572. Offline, $0."""
from __future__ import annotations

import math

import pytest

from adroit.constraints import database, review
from adroit.constraints import searches as constraint_searches
from adroit.parameter_space import library, searches

NEFF, LHCB, BSGAMMA = "escudero-1901.02010-neff", "lhcb-1612.07818-b-to-k-mumu", "li-2412.04572-bsgamma"


# --- N_eff: only what the frames show -------------------------------------------------------------------------------

def test_the_neff_contours_lie_inside_the_figure_s_frames():
    """Each contour is the PDF's path clipped to its frame (log₁₀(m/MeV) −6.155 to 2.602, log₁₀ g −13.097 to −2.398):
    before, the paths ran on under the frame's clip, to log₁₀ m = −14.24 and log₁₀ g = −0.35. Each now starts on the
    frame's left or lower edge and ends on its upper one."""
    d = database.data(NEFF)
    (m0, m1), (g0, g1) = d["mass_range_log10_mev"], d["coupling_range_log10"]
    assert (m0, m1, g0, g1) == (-6.155, 2.602, -13.097, -2.398)
    for frame in ("no_mixing", "natural_mixing"):
        for level in ("0.5", "0.2", "0.1"):
            c = d[frame][level]
            assert all(m0 <= x <= m1 + 1e-4 and g0 - 1e-4 <= y <= g1 + 1e-4 for x, y in c), (frame, level)
            assert abs(c[0][0] - m0) < 1e-3 or abs(c[0][1] - g0) < 1e-3, (frame, level, c[0])
            assert abs(c[-1][1] - g1) < 1e-3, (frame, level, c[-1])


def test_neff_says_nothing_outside_the_frames():
    """A coupling above the frame's top has no N_eff outcome (it had been read from the contours' paths past the
    frame, or their closure); just inside it, a Z′ left of the 0.5 contour is excluded, as before."""
    assert searches._lmu_neff(1e-2, 1e-3, 0.0, "natural_mixing", True) is None          # log₁₀ g = −2, above the frame
    assert searches._lmu_neff(1e-3, 1e-3, 0.0, "natural_mixing", True).excluded is True
    assert searches._lmu_neff(1e-3, 1e-3, 0.0, "no_mixing", True).excluded is True


def test_the_neff_figure_names_the_source_s_axes():
    """The record's figure: one panel per frame, its axes log₁₀(m_Z′/MeV) and log₁₀ g_μ−τ, its curves named by their
    ΔN_eff (the owner's review: the plot had both frames on one unnamed axis)."""
    record = database.record(NEFF)
    groups = review.panels(record)
    assert [label for label, _, _ in groups] == ["log₁₀ g_μ−τ: no kinetic mixing (Fig. 2, top)",
                                                 "log₁₀ g_μ−τ: ε = g_μ−τ/70 (Fig. 2, bottom)"]
    assert review.PANELS[NEFF][0] == "log₁₀(m_Z′/MeV)"
    assert {review.LEGEND[c.label] for _, group, _ in groups for c in group} == {"ΔN_eff = 0.5", "ΔN_eff = 0.2",
                                                                                 "ΔN_eff = 0.1"}
    assert review.figure(record)[:8] == b"\x89PNG\r\n\x1a\n"


# --- LHCb: 41 lifetimes, its grid shown, the a's photons counted -----------------------------------------------------

def test_lhcb_s_rows_are_its_41_lifetimes_from_01_to_1000_ps():
    """Each row is LHCb's limit at one lifetime, 10⁻¹ … 10³ ps a tenth of a decade apart (the paper's 0.1 < τ < 1000
    ps): the figure draws each from its value up one row, so its top row reaches 10³·¹ ≈ 1260 ps, a cell edge."""
    grid = [r["log10_tau_ps"] for r in database.data(LHCB)["rows"]]
    assert len(grid) == 41 and grid[0] == -1.0 and grid[-1] == 3.0
    assert all(abs(b - a - 0.1) < 1e-9 for a, b in zip(grid, grid[1:]))
    assert searches.LHCB_TAU_PS == (0.1, 1000.0)


def _segment(row: dict, m_mev: float) -> float:
    return next(v for lo, hi, v in row["segments"] if lo <= m_mev <= hi)


def test_lhcb_s_limit_between_two_lifetimes_is_the_weaker():
    """At one of LHCb's lifetimes its own limit; between two, the weaker of theirs (the limit between them is not
    shown); at 1000 ps the top row; past it, none."""
    rows = database.data(LHCB)["rows"]
    m = 300.0
    assert searches.lhcb_limit(rows, m, 1.0) == pytest.approx(10 ** _segment(rows[20], m))
    between = searches.lhcb_limit(rows, m, 1.05)
    assert between == pytest.approx(10 ** max(_segment(rows[20], m), _segment(rows[21], m)))
    assert searches.lhcb_limit(rows, m, 3.0) == pytest.approx(10 ** _segment(rows[40], m))
    assert searches.lhcb_limit(rows, m, 2.95) == pytest.approx(10 ** max(_segment(rows[39], m), _segment(rows[40], m)))
    assert searches.lhcb_limit(rows, m, 3.05) is None and searches.lhcb_limit(rows, m, -1.05) is None


def test_an_a_living_past_1000_ps_is_outside_lhcb_s_map(monkeypatch):
    """τ_a between 1000 and 1260 ps had been judged against the top row's cell; it is now outside the map."""
    monkeypatch.setattr(constraint_searches, "b_to_k_pseudoscalar", lambda *args: 1e-6)
    width = searches.HBAR_GEV_PS / 1100.0                          # τ = 1100 ps
    outcome = searches._lhcb_mumu(0.3, 1e-3, 1.0, width, True)
    assert outcome.excluded is None and "outside LHCb's 0.1–1000 ps" in outcome.why
    assert searches._lhcb_mumu(0.3, 1e-3, 1.0, searches.HBAR_GEV_PS / 900.0, True).excluded is not None


def test_lhcb_s_grid_is_shown_on_the_record_s_page():
    """The record page had said "holds single numbers": its grid is drawn as a map, as LHCb's Fig. 4."""
    record = database.record(LHCB)
    assert review.curves(record) == [] and len(review.grid(record)) == 41
    assert review.figure(record)[:8] == b"\x89PNG\r\n\x1a\n"


def test_the_pseudoscalar_loop_function():
    """Dolan et al. eq. (B.3): 2 for a heavy fermion, π²/2 at threshold, continuous there, and small for a light one."""
    assert constraint_searches.pseudoscalar_loop(1e-8) == pytest.approx(2.0)
    assert constraint_searches.pseudoscalar_loop(1.0) == pytest.approx(math.pi ** 2 / 2)
    assert abs(constraint_searches.pseudoscalar_loop(1.0 + 1e-9) - math.pi ** 2 / 2) < 1e-3
    assert abs(constraint_searches.pseudoscalar_loop(1e6)) < 1e-3


def _alp(m_a: float, g_q: float, g_l: float):
    e = library.entry("alp_portal")
    return e, e.point.model_copy(update={"m_med": m_a, "g_q": g_q, "g_l": g_l, "g_chi": 1e-3, "m_chi": 1.0})


@pytest.mark.parametrize("quarks_over_leptons, low, high", [(1.0, 1e-4, 1e-3), (10.0, 0.02, 0.05), (100.0, 2.0, 5.0)])
def test_the_a_s_photon_width_against_its_muons(quarks_over_leptons, low, high):
    """Γ(a → γγ)/Γ(a → μμ) for the library's ALP at 300 MeV: small for equal couplings, a few per cent for g_q = 10 g_ℓ,
    dominant for 100 g_ℓ (the owner's review: omitting the photons is an approximation, Dolan et al. §2.2)."""
    e, p = _alp(0.3, 1e-3 * quarks_over_leptons, 1e-3)
    _, fermions = e.model_class._couplings(p)
    photons = constraint_searches.pseudoscalar_photon_width(0.3, {f.name: g for f, _, g in fermions})
    muons = e.model_class._widths(p)[0]["mu"]
    assert low < photons / muons < high


def test_lhcb_counts_the_a_s_photons(monkeypatch):
    """The a's lifetime and BR(μμ) are from its whole width, photons included, on the library's route and the
    generic one alike."""
    seen = []
    monkeypatch.setattr(searches, "_lhcb_mumu", lambda m, g, mumu, width, unverified: seen.append((mumu, width)))
    e, p = _alp(0.3, 1e-1, 1e-3)
    searches.b_to_k_mumu(e.model_class, p, True)
    widths = e.model_class._widths(p)[0]
    _, fermions = e.model_class._couplings(p)
    photons = constraint_searches.pseudoscalar_photon_width(0.3, {f.name: g for f, _, g in fermions})
    total = sum(widths.values()) + photons
    assert seen[0] == pytest.approx((widths["mu"] / total, total))
    assert seen[0][0] < 0.35                                       # g_q = 100 g_ℓ: the photons dominate
    from tests.parameter_space.test_generic_portrait import _generic_at
    engine, q = _generic_at("alp_portal", p)
    searches.b_to_k_mumu(engine, q, True)
    assert seen[1] == pytest.approx(seen[0], rel=5e-2)


# --- B → X_s γ, re-sourced -----------------------------------------------------------------------------------------

def test_the_bsgamma_record_is_li_et_al_s(monkeypatch):
    """Re-sourced at the owner's request to Li, Song, Su & Su (arXiv:2412.04572), which states 'around 800 GeV' from
    R_γ with Misiak, Rehman & Steinhauser's method: the bound and its tan β reach are unchanged, and the search reads
    the new record, its own signature deciding (unsigned, it waits for it; the owner signed it on 2026-11-07)."""
    from tests.unsigned_records import as_unsigned
    record = database.record(BSGAMMA)
    assert record.figure.arxiv == "2412.04572" and record.data == {"m_charged_min_gev": 800.0, "tan_beta_min": 0.4}
    assert "misiak-2002.01548-bsgamma" not in {r.id for r in database.records()}
    assert searches._bsgamma(700.0, 3.0, True).excluded and searches._bsgamma(900.0, 3.0, True).excluded is False
    as_unsigned(monkeypatch, (BSGAMMA,))
    assert "verif" in searches._bsgamma(700.0, 3.0, False).why        # unsigned: blocked by its own record
