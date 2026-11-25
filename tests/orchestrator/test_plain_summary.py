"""The "Explain a signal" report's plain summary (OB-09) and its best physical fit (OB-10), the owner's items of
2026-11-19: every sentence read from the result's own fields, and no best fit named where no mass has one; and the auditor's
audit of them (MF-06 to MF-09): the summary says the study's own assessment of its fits, over the same fits, never a
universal claim from the absence of a row; a promoted study's significance with its parent's bound; masses by row; and
no best fit without a finite statistic."""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from adroit.orchestrator import plain_summary, single_idea
from adroit.orchestrator.plain_summary import FIT_LEAD, mass, masses


def _fit(resolved=True, identifiable=True, edge=False, q0=0.0):
    return SimpleNamespace(resolved=resolved, identifiable=identifiable, at_boundary=edge, q0=q0)


def _point(m, z=0.0, fit=None, point=True, status="pending", excluded_by=(), pending=("muon g−2: not computed",)):
    return SimpleNamespace(m_chi=m, z_local=z, physical_fit=fit, point=object() if point else None,
                           fitted_parameter="g_chi", status=status, excluded_by=list(excluded_by),
                           pending=list(pending))


def _thermal(m, q0, status="viable"):
    """A certified relic point (``single_idea._certified``), refitted at its own mass."""
    return SimpleNamespace(**vars(_point(m, z=math.sqrt(q0), fit=_fit(q0=q0), status=status, pending=())),
                           converged=True, relative_residual=0.001, omega_h2=0.12)


def _result(band, thermal=(), thermal_pending=(), level="undetermined", summary="a reason", global_z=3.0283,
            unsupported="", tables=None, parent=None, fit_quality=None):
    """A result whose fit assessment is the study's own (``single_idea._fit_quality``) over the fits given."""
    tables = tables or {}
    quality = fit_quality if fit_quality is not None else single_idea._fit_quality(band, list(thermal), tables)
    return SimpleNamespace(band=band, thermal=list(thermal), thermal_pending=list(thermal_pending), level=level,
                           summary=summary, global_z=global_z, unsupported=unsupported, eos_thermal=tables,
                           fit_quality=quality, request=SimpleNamespace(parent_global_z=parent))


def _text(result) -> str:
    return "\n".join(plain_summary.single_idea(result))


def _the_saved_study():
    """The shape of the owner's alp_portal run of 2026-11-19: no excess below 84 GeV, the fit unresolved at 84 GeV and
    above 243 GeV (no model point there), at its range's edge at 120 and 171 GeV."""
    band = [_point(m) for m in (5.0, 7.11823, 10.1338, 14.427, 20.5389, 29.2402, 41.6277, 59.2631)]
    band += [_point(84.3696, z=2.36, fit=_fit(resolved=False), point=False)]
    band += [_point(120.112, z=2.93, fit=_fit(edge=True, q0=2.6e-05), status="excluded",
                    excluded_by=["gamma rays (Fermi-LAT dwarfs)"], pending=()),
             _point(170.998, z=3.12, fit=_fit(edge=True, q0=2.9e-05), pending=("halo: sensitive",))]
    band += [_point(m, z=3.3, fit=_fit(resolved=False), point=False) for m in (243.44, 346.572, 493.396, 702.422)]
    band += [_point(1000.0, z=3.31, fit=_fit(resolved=False), point=False)]
    return _result(band, thermal_pending=["a", "b", "c", "d"], summary="bounded physical fit coverage remains unresolved")


def test_a_mass_has_three_figures_and_no_exponent() -> None:
    assert [mass(v) for v in (1000.0, 84.3696, 7.11823, 5.0, 0.0315)] == ["1000", "84.4", "7.12", "5", "0.0315"]


def test_masses_are_said_as_runs_of_neighbouring_rows() -> None:
    every = [5.0, 7.0, 10.0, 84.0, 120.0, 171.0, 243.0, 347.0, 1000.0]
    assert masses(every, [0, 1, 2]) == "5–10 GeV (3 masses)"
    assert masses(every, [4, 5]) == "120 and 171 GeV"
    assert masses(every, [3, 6, 7, 8]) == "84 GeV and 243–1000 GeV (3 masses)"
    assert masses(every, [0, 3, 8]) == "5 GeV, 84 GeV and 1000 GeV"


def test_unsorted_or_repeated_masses_are_said_by_row_never_as_an_interval() -> None:
    """MF-08: rows (10, fits), (10, below), (20, fits) had been said "10–20 GeV (3 masses)" and "10 and 10 GeV"; rows
    at 100, 10, 50 GeV as "100–50 GeV"."""
    assert masses([100.0, 10.0, 50.0], [0, 1, 2]) == "100 GeV, 10 GeV and 50 GeV"
    assert masses([10.0, 10.0, 20.0], [0, 2]) == "10 GeV and 20 GeV"
    assert masses([10.0, 10.0, 20.0], [1]) == "10 GeV"
    assert masses([10.0, 10.0, 20.0], [0, 1]) == "10 GeV (2 points)"
    assert masses([5.0, 10.0, 10.0, 20.0, 30.0], [0, 1, 2, 3]) == "5 GeV, 10 GeV (2 points) and 20 GeV"
    band = [_point(10.0, z=2.0, fit=_fit(q0=4.0)), _point(10.0, z=0.2, fit=_fit(q0=0.04)),
            _point(20.0, z=2.0, fit=_fit(q0=4.0))]
    text = _text(_result(band, global_z=1.5))
    assert ("the fit matches the events at least 1σ better than background alone at 10 GeV and 20 GeV; it is less "
            "than 1σ better than background alone at 10 GeV.") in text
    assert "Allowing for the 2 masses tried" in text and "Of the 3 points with a model point" in text


def test_the_saved_study_is_said_as_its_result_says() -> None:
    result = _the_saved_study()
    assert result.fit_quality == "undetermined"                     # as the owner's saved result has it
    text = _text(result)
    assert text.startswith("## In brief")
    assert ("matches the events best at m_χ = 1000 GeV. Allowing for the 16 masses tried, its significance is 3.0σ"
            in text)
    assert ("whether any fit meets the anomaly-fit criterion (at least 1σ better than background alone) is not "
            "established. At the sampled masses, the fit is less than 1σ better than background alone at 5–59.3 GeV "
            "(8 masses); it runs to the edge of g_chi's allowed range at 120 and 171 GeV; it does not settle at 84.4 "
            "GeV and 243–1000 GeV (5 masses).") in text
    assert "no mass" not in text and "no fit meets" not in text                       # MF-06
    assert ("Of the 10 masses with a model point, 1 is excluded, by gamma rays (Fermi-LAT dwarfs); 9 are undecided; "
            "none is allowed. Most often undecided: muon g−2 at 8 masses, halo at 1 mass.") in text
    assert "section 1 lists 4 open items that bear on it" in text and "calculation" not in text
    assert ("**Overall.** Whether the model explains the signal is not yet decided. The headline's reason: bounded "
            "physical fit coverage remains unresolved.") in text


def test_a_refined_relic_point_that_fits_is_said_beside_coarse_masses_that_do_not() -> None:
    """MF-06: coarse masses below the criterion and a certified relic point between them that meets it, viable; the
    summary had said "no mass gives a fit that could explain the signal" beside a viable headline."""
    band = [_point(10.0, z=0.2, fit=_fit(q0=0.04)), _point(30.0, z=0.3, fit=_fit(q0=0.09))]
    result = _result(band, thermal=[_thermal(20.0, 4.0)], level="viable")
    assert result.fit_quality == "fits"
    text = _text(result)
    assert "at least one fit meets the anomaly-fit criterion" in text
    assert "At the sampled masses, the fit is less than 1σ better than background alone at 10 and 30 GeV." in text
    assert ("At the refined points where the relic density is right, it matches the events at least 1σ better than "
            "background alone at 20 GeV.") in text
    assert "no fit" not in text.lower() and "no mass" not in text


def test_an_equation_of_state_table_refit_counts_as_the_assessment_does() -> None:
    band = [_point(10.0, z=0.2, fit=_fit(q0=0.04))]
    result = _result(band, tables={"upper": [_thermal(15.0, 2.25)]}, level="no_thermal")
    assert result.fit_quality == "fits"
    text = _text(result)
    assert "at least one fit meets" in text and "matches the events at least 1σ better than background alone at 15 GeV" in text


def test_an_uncertified_relic_point_is_not_said_as_one_the_assessment_counts() -> None:
    band = [_point(10.0, z=0.2, fit=_fit(q0=0.04))]
    loose = SimpleNamespace(**{**vars(_thermal(20.0, 4.0)), "converged": False})
    result = _result(band, thermal=[loose], level="no_fit")
    assert result.fit_quality == "no_fit"
    assert "refined points" not in _text(result)


@pytest.mark.parametrize("band", [
    [_point(10.0, z=0.2, fit=_fit(q0=0.04)), _point(20.0, z=2.0, fit=_fit(resolved=False))],
    [_point(10.0, z=0.2, fit=_fit(q0=0.04)), _point(20.0, z=2.0, fit=_fit(identifiable=False))],
    [_point(10.0, z=0.2, fit=_fit(q0=0.04)), _point(20.0, z=2.0, fit=_fit(edge=True, q0=4.0))],
    [_point(10.0, z=0.2, fit=_fit(q0=0.04)), _point(20.0, z=2.0, fit=_fit(q0=None))],
    [_point(10.0, z=0.2, fit=_fit(q0=0.04)), _point(20.0, z=0.3, fit=_fit(q0=0.09))],
    [_point(10.0, z=0.2, fit=_fit(q0=0.04)), _point(20.0, z=2.0, fit=_fit(q0=4.0))],
], ids=["unresolved", "unidentifiable", "edge", "no statistic", "below", "fits"])
def test_the_summary_says_the_studys_own_assessment(band) -> None:
    """The opening's verdict on the fit is the stored assessment, whatever rows lie behind it (MF-06)."""
    result = _result(band)
    text = _text(result)
    assert FIT_LEAD[result.fit_quality] in text
    assert ("no fit meets" in text) == (result.fit_quality == "no_fit")
    assert ("at least one fit meets" in text) == (result.fit_quality == "fits")


def test_an_older_result_without_an_assessment_makes_no_claim_of_one() -> None:
    text = _text(_result([_point(10.0, z=0.2, fit=_fit(q0=0.04))], fit_quality=""))
    assert not any(lead in text for lead in FIT_LEAD.values())
    assert "At the sampled masses, the fit is less than 1σ better than background alone at 10 GeV." in text


def test_improvements_below_the_criterion_keep_its_threshold() -> None:
    """MF-06: improvements of 0.2σ and 0.3σ had been said "no better than background alone"."""
    band = [_point(10.0, z=0.2, fit=_fit(q0=0.04)), _point(20.0, z=0.3, fit=_fit(q0=0.09))]
    text = _text(_result(band, level="no_fit", global_z=0.1))
    assert "no fit meets the anomaly-fit criterion: every one is less than 1σ better than background alone" in text
    assert "less than 1σ better than background alone at 10 and 20 GeV" in text
    assert "no better than background alone" not in text


def test_a_rootless_search_keeps_its_finite_sampling() -> None:
    """MF-06: "No point of the band reaches the observed relic density over the masses searched" had dropped the
    reason's "features between samples are not ruled out"."""
    band = [_point(10.0, z=2.0, fit=_fit(q0=4.0))]
    text = _text(_result(band, level="no_thermal"))
    assert ("No point where the relic density is right was resolved among the masses searched; features between the "
            "sampled masses are not ruled out.") in text
    assert "not ruled out" in plain_summary.LEVEL_PLAIN["no_thermal"]
    assert "reaches the observed relic density" not in text


@pytest.mark.parametrize("own,parent", [(2.4, 0.4), (2.4, 3.0)])
def test_a_promoted_studys_significance_carries_its_parents_bound(own, parent) -> None:
    """MF-07: a value capped at the library-wide search's 0.4σ had been said as allowing for the child's 2 masses."""
    band = [_point(10.0, z=2.5, fit=_fit(q0=6.25)), _point(20.0, z=1.0, fit=_fit(q0=1.0))]
    text = _text(_result(band, global_z=min(own, parent), parent=parent))
    assert (f"Its significance is {min(own, parent):.1f}σ: the smaller of this study's own, over its 2 masses, and "
            "that of the library-wide search it was promoted from") in text
    assert "Allowing for the 2 masses tried" not in text
    assert "MF-" not in text and "OB-" not in text                   # no audit label in what the reader sees


def test_the_detailed_report_keeps_the_parents_bound(monkeypatch) -> None:
    monkeypatch.setattr(single_idea, "_band_table", lambda rows: [])
    band = [SimpleNamespace(m_chi=7.5, status="pending", physical_fit=None, inversion_reason="")]
    method = "two mass reference trials; promoted from a library-wide search whose global significance is 0.40σ"
    result = SimpleNamespace(best="L01s@7.5", band=band, global_z=0.4, global_method=method,
                             physical_significance_note="", physical_best_mass_gev=None,
                             constraint_compatibility="undetermined", thermal_viability="", level="undetermined",
                             thermal_pending=[])
    assert any(method in line for line in single_idea._fit_section(result))


def test_thermal_points_are_counted_by_their_status() -> None:
    thermal = [SimpleNamespace(m_chi=40.0, status="excluded", converged=False, relative_residual=None, omega_h2=None),
               SimpleNamespace(m_chi=50.0, status="pending", converged=False, relative_residual=None, omega_h2=None)]
    band = [_point(40.0, z=2.0, fit=_fit(q0=4.0)), _point(50.0, z=2.0, fit=_fit(q0=4.0))]
    text = _text(_result(band, thermal=thermal, level="viable_pending"))
    assert ("at 2 points of the band, at 40 and 50 GeV: 1 excluded, 1 undecided, 0 allowed") in text
    assert "some searches are still undecided there" in text


def test_no_excess_is_said_as_none() -> None:
    text = _text(_result([_point(10.0), _point(20.0)], global_z=0.0))
    assert "fits the events no better than background alone at any of the masses tried" in text
    assert "significance" not in text


def test_a_model_that_is_not_computed_says_so_and_nothing_about_its_points() -> None:
    band = [_point(10.0, z=1.5, point=False)]
    text = _text(_result(band, unsupported="the model cannot be built", fit_quality="not_computed"))
    assert "**The model's own couplings** were not fitted: the model cannot be built." in text
    assert "other searches" not in text and "relic density" not in text


def test_no_band_has_no_summary() -> None:
    assert plain_summary.single_idea(_result([], fit_quality="")) == []


def test_every_headline_level_has_a_plain_sentence() -> None:
    from adroit.orchestrator.single_idea import LEVELS
    assert set(LEVELS) <= set(plain_summary.LEVEL_PLAIN)


# --- OB-10 and MF-09: a best physical fit only where a mass has one, with a finite statistic ------------------------

def test_no_best_physical_fit_where_every_mass_ranks_zero() -> None:
    assert single_idea.best_physical_fit(_the_saved_study().band) is None


def test_the_best_physical_fit_is_the_mass_with_the_largest_statistic() -> None:
    band = [_point(10.0, fit=_fit(q0=0.0)), _point(20.0, fit=_fit(q0=4.0)), _point(30.0, fit=_fit(q0=1.0)),
            _point(40.0, fit=_fit(edge=True, q0=9.0))]
    assert single_idea.best_physical_fit(band).m_chi == 20.0


@pytest.mark.parametrize("bad", [math.inf, -math.inf, math.nan, None, 0.0, -1.0])
def test_an_unusable_statistic_is_never_the_best_physical_fit(bad) -> None:
    """MF-09: a resolved fit with q0 = +∞ had been named "Best resolved physical-fit mass"; finite ones keep their
    ranking, a finite fit below the anomaly-fit criterion included."""
    best = single_idea.best_physical_fit
    assert best([_point(10.0, fit=_fit(q0=bad))]) is None
    assert best([_point(10.0, fit=_fit(q0=bad)), _point(20.0, fit=_fit(q0=0.25))]).m_chi == 20.0
    assert best([_point(10.0, z=bad if bad is not None else math.nan), _point(20.0, z=1.5)]).m_chi == 20.0


def test_the_report_says_plainly_when_no_mass_has_a_physical_fit(monkeypatch) -> None:
    band = [SimpleNamespace(m_chi=7.5, status="pending", physical_fit=None, inversion_reason="")]
    result = SimpleNamespace(best="L01s@7.5", band=band, global_z=2.0, global_method="toys",
                             physical_significance_note="note", physical_best_mass_gev=None,
                             constraint_compatibility="undetermined", thermal_viability="", level="undetermined",
                             thermal_pending=[])
    monkeypatch.setattr(single_idea, "_band_table", lambda rows: [])
    lines = single_idea._fit_section(result)
    assert any(line.startswith("No mass has a resolved physical fit") and "finite fit statistic" in line
               for line in lines)
    assert not any("Best resolved physical-fit mass" in line for line in lines)
    assert not any("of the best resolved physical fit" in line for line in lines)


def test_the_whole_report_opens_with_the_summary() -> None:
    from tests.orchestrator.test_research_assistance import request
    band = [single_idea.BandPoint(m_chi=m, s_hat=0.0, events_at_unit=1.0, mu_hat=0.0, mu_68=(0.0, 1.0), z_local=z)
            for m, z in ((10.0, 0.5), (20.0, 2.1), (30.0, 1.2))]
    result = single_idea.SingleIdeaResult(request=single_idea.prepared(request().study), band=band,
                                          best="O1s@20", global_z=1.6, global_method="toys", level="undetermined",
                                          summary="SIMULATED reason", fit_quality="undetermined",
                                          constraint_compatibility="undetermined", thermal_viability="undetermined",
                                          unsupported="SIMULATED: not computed")
    text = single_idea.report(result)
    assert "## In brief" in text and text.index("## In brief") < text.index("## 1. The fit")
    assert "matches the events best at m_χ = 20 GeV" in text and "its significance is 1.6σ" in text
