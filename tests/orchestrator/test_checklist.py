"""R8: the 28-item viability checklist from what a run computed (orchestrator.checklist)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adroit.constraints import viability
from adroit.constraints.viability import Status
from adroit.orchestrator import checklist, track1

DOCS = Path(__file__).resolve().parents[2] / "docs"


def test_every_constraint_a_scan_can_report_has_an_item() -> None:
    from adroit.parameter_space import resonances, scan, searches
    names = [searches.CMB, searches.DARK_PHOTON, searches.FLAVOUR, searches.DILEPTON, searches.LEP_CONTACT,
             searches.SQUARK, searches.G2, searches.LMU, searches.IDM_LEP, searches.TWO_HDMA, searches.BBN,
             searches.LHC, searches.HIGGS_MU, searches.HEAVY_SCALAR, searches.MONOJET, searches.LINES,
             searches.PBAR, resonances.DIJET, resonances.TTBAR, resonances.MONOH, resonances.MONOZ,
             scan.INVISIBLE_H, scan.INVISIBLE_Z, "direct detection", "colliders (CMS)", "perturbativity",
             "gamma rays (Fermi-LAT dwarfs)", "capture in the Sun (IceCube)", "L_μ − L_τ (Z → 4μ)",
             "L_μ − L_τ (BaBar/Belle II)", "private: a curve / limit", "private-search:abc"]
    items = {i.id for i in viability.items()}
    assert all(checklist.item_of(n) in items for n in names), [n for n in names if checklist.item_of(n) not in items]


def _portal_result(portal: str) -> track1.Track1Result:
    """A Track 1 result for one library portal at its benchmark point (one evaluated point, no thermal roots)."""
    from adroit.model_building.audit import audit
    from adroit.parameter_space import scan
    from adroit.parameter_space.library import entry
    from adroit.parameter_space.scan import ScanRequest, ScanResult
    e = entry(portal)
    point = scan.evaluate(e.model_class, e.point, True)
    request = ScanRequest(model_class=e.model_class, fixed=e.point, x=e.x, y=e.y)
    spec = e.spec()
    return track1.Track1Result(request=track1.Track1Request(spec=spec, portal=portal), audit=audit(spec),
                               fixed=e.point, scan=ScanResult(request=request, xs=[0.0], ys=[0.0], points=[point]))


@pytest.mark.parametrize("portal,item", [
    pytest.param("dark_photon_dirac", "beam_dumps", marks=pytest.mark.needs("diamx", "cdmslite", "solar_model")),
    pytest.param("higgs_portal_scalar", "precision", marks=pytest.mark.needs("diamx", "solar_model")),
    pytest.param("b_minus_l", "cmb_annihilation", marks=pytest.mark.needs("diamx", "solar_model"))])
def test_the_checklist_matches_the_constraints_computed_for_three_portals(portal: str, item: str) -> None:
    result = _portal_result(portal)
    entries = {e.id: e for e in checklist.for_track1(result)}
    compared = result.scan.points[0].excluded
    for name in compared:
        entry = entries[checklist.item_of(name)]
        assert entry.status in (Status.computed, Status.undecided) and name in entry.detail, (name, entry)
        decided = any(compared_name in entry.detail and result.scan.points[0].excluded[compared_name] is not None
                      for compared_name in compared if checklist.item_of(compared_name) == entry.id)
        assert (entry.status is Status.computed) == decided, entry           # undecided: no verdict anywhere
    assert entries[item].status in (Status.computed, Status.undecided)
    for e in entries.values():
        assert not (e.status in (Status.computed, Status.undecided) and e.planned), e   # nothing "to be built"
        if e.status is Status.computed and e.id != "relic_abundance":
            assert any(n in e.detail for n in compared) or "certificate" in e.detail or "species" in e.detail \
                or "pole" in e.detail or "Sommerfeld" in e.detail, e
    assert "unmapped" not in entries


def test_a_track1_report_carries_the_checklist_with_the_thermal_roots() -> None:
    result = track1.Track1Result.model_validate_json((DOCS / "dm13/reports/vector_mediator/result.json").read_text())
    entries = {e.id: e for e in checklist.for_track1(result)}
    relic = entries["relic_abundance"]
    assert relic.status is Status.computed and relic.detail.startswith("thermal roots of Ωh² = 0.12: excluded")
    assert "on the thermal contour: excluded at 28 of 28 root(s)" in entries["direct_detection"].detail
    assert "run Path 1's exclusion" not in entries["direct_detection"].detail          # an instruction, now done
    text = track1.report(result)
    assert text.count("## 6. Viability checklist") == 1 and "| Relic abundance | computed |" in text


def test_a_root_where_a_constraint_does_not_apply_is_not_counted() -> None:
    from types import SimpleNamespace as NS
    roots = [NS(evaluation=NS(excluded={"invisible Higgs width (ATLAS)": False}), excluded_by=[], pending=[]),
             NS(evaluation=NS(excluded={}), excluded_by=[], pending=[])]
    assert checklist._contour("invisible Higgs width (ATLAS)", roots) == "; on the thermal contour: allowed at all 1 root(s)"
    legacy = [NS(evaluation=None, excluded_by=["CMB (Planck)"], pending=[]),
              NS(evaluation=None, excluded_by=[], pending=["CMB (Planck): f_eff"])]
    assert checklist._contour("CMB (Planck)", legacy) == "; on the thermal contour: excluded at 1, undecided at 1 of 2 root(s)"


def test_a_single_idea_checklist_counts_the_fit_as_direct_detection() -> None:
    from adroit.orchestrator import single_idea
    result = single_idea.SingleIdeaResult.model_validate_json(
        (DOCS / "dm14/single_idea_vector_cdms_si/result.json").read_text())
    entries = {e.id: e for e in checklist.for_single_idea(result)}
    assert entries["direct_detection"].detail.startswith("the fit to CDMS II Si (2013) at 12 masses")
    text = single_idea.report(result)
    assert text.count("Viability checklist") == 1 and "## 4. Viability checklist" in text


def test_path1_uses_the_same_mapping() -> None:
    from adroit.orchestrator import lagrangian
    result = lagrangian.LagrangianResult.model_validate_json((DOCS / "dm8/majorana_scalar/result.json").read_text())
    evidence = checklist.lagrangian_evidence(result)
    entries = {e.id: e for e in checklist.apply(viability.assess(result.spec, result.checks), evidence)}
    assert entries["direct_detection"].status is Status.computed and "module(s)" in entries["direct_detection"].detail


def test_relic_physics_names_poles_partners_and_long_range_effects() -> None:
    from adroit.parameter_space.library import entry
    t = entry("tchannel_uR_majorana")
    physics = checklist.relic_physics(t.model_class, t.point)
    assert "species in the bath" in physics.get("coannihilation", "") and "Sommerfeld" in physics.get("long_range", "")
    h = entry("higgs_portal_scalar")
    assert "pole" in checklist.relic_physics(h.model_class, h.point).get("resonances", "")


def test_no_built_text_still_says_not_built_for_what_runs_compute() -> None:
    items = {i.id: i for i in viability.items()}
    for computed in ("relic_abundance", "direct_detection", "indirect_detection", "colliders", "beam_dumps",
                     "rare_meson_decays", "neutrino_fluxes", "precision", "bbn_neff", "cmb_annihilation",
                     "sommerfeld_bound_states", "vacuum_structure"):
        assert not items[computed].built.startswith("Not built"), computed


def test_the_evidence_summary_carries_the_checklist_only_when_stored() -> None:
    from adroit.evidence.results import summary
    result = track1.Track1Result.model_validate_json((DOCS / "dm13/reports/vector_mediator/result.json").read_text())
    assert "viability" not in summary("track1", result)                     # older results verify as before
    stored = result.model_copy(update={"viability": checklist.for_track1(result)})
    assert summary("track1", stored)["viability"][0]["id"] == "relic_abundance"


def test_certificates_count_by_their_outcome_including_the_vacuum_classification() -> None:
    """The vacuum certificate records its classification (`vacuum`), not a `status` (the R8 release checks)."""
    from types import SimpleNamespace as NS
    from adroit.core.theory import ScalarVacuumCertificate
    points = [NS(vacuum_certificate=ScalarVacuumCertificate(vacuum="metastable", passed=True),
                 unitarity_certificate=NS(status="passed"), running_certificate=None, chemical_certificate=None),
              NS(vacuum_certificate=ScalarVacuumCertificate(vacuum="global", passed=True),
                 unitarity_certificate=NS(status="failed"), running_certificate=None, chemical_certificate=None)]
    found = checklist._certificates(points)
    assert "metastable at 1" in found["vacuum_structure"][0] and "global at 1" in found["vacuum_structure"][0]
    assert "passed at 1" in found["unitarity"][0] and "failed at 1" in found["unitarity"][0]
    assert checklist._state(NS(passed=None)) == "unresolved"


def test_an_item_compared_without_any_verdict_is_undecided_with_its_reasons() -> None:
    """The owner (2026-10-12): "computed" only where a verdict was reached; otherwise "undecided", with why."""
    from types import SimpleNamespace as NS
    points = [NS(excluded={"colliders (CMS)": None, "direct detection": True}, pending=[]),
              NS(excluded={"colliders (CMS)": None, "direct detection": False}, pending=[])]
    scan = NS(points=points)
    evidence, unmapped, decided = checklist.scan_evidence(scan, [], ["colliders: CMS's limits apply to its benchmarks"])
    assert decided == {"direct_detection"} and "why: CMS's limits apply to its benchmarks" in evidence["colliders"][0]
    base = [viability.Entry(id=i, group="searches", title=i, status=Status.applies, detail="x", planned="later")
            for i in ("colliders", "direct_detection")]
    entries = {e.id: e for e in checklist.apply(base, evidence, undecided={"colliders"})}
    assert entries["colliders"].status is Status.undecided and entries["direct_detection"].status is Status.computed
    assert not entries["colliders"].planned
    assert "undecided (compared by the run, but no verdict anywhere" in viability.report(list(entries.values()))
