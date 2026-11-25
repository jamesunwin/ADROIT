"""DM9: vetting the constraint scout (references checked, DM7's rules applied, records unverified)."""

from __future__ import annotations

from adroit.agents.scout import ProposedConstraint, ScoutReport
from adroit.constraints import scouting
from adroit.retrieval import references as refs

KNOWN = {"1510.02110": refs.Reference(kind="arxiv", id="1510.02110", year=2015, verified=True,
                                      title="Implications of unitarity and gauge invariance for simplified dark matter models")}


def resolver(asked):
    return {a.id: KNOWN[a.id] for a in asked if a.id in KNOWN}


def proposal(ref: str, title: str, cls: str = "collider", applicability: str = "applies", **extra) -> ProposedConstraint:
    return ProposedConstraint(name="bound", constraint_class=cls, reference=ref, title=title,
                              applicability=applicability, **extra)


def test_only_confirmed_references_survive() -> None:
    report = ScoutReport(proposals=[
        proposal("arXiv:1510.02110", "Implications of unitarity and gauge invariance for simplified dark matter models"),
        proposal("1510.02110", "A different paper altogether about neutrino oscillations"),
        proposal("2612.99999", "Invented"), proposal("Smith et al. 2019", "Unidentified")])
    vetted = scouting.vet(report, has_completion=True, resolver=resolver)
    assert [v.kept for v in vetted] == [True, False, False, False]
    assert "not this paper's" in vetted[1].reason and "not found" in vetted[2].reason
    text = scouting.report(vetted, "X")
    assert "arXiv:1510.02110 (2015)" in text and "2612.99999" not in text and "3 proposal(s) dropped" in text


def test_dm7_s_rules_are_enforced() -> None:
    t = "Implications of unitarity and gauge invariance for simplified dark matter models"
    report = ScoutReport(proposals=[proposal("1510.02110", t, "relic_density"),
                                    proposal("1510.02110", t, "solar_capture", "applies_with_assumptions"),
                                    proposal("1510.02110", t, "collider", "needs_calculation")])
    vetted = scouting.vet(report, has_completion=False, resolver=resolver)
    assert vetted[0].proposal.applicability.value == "needs_calculation" and "tier 3" in vetted[0].changes[0]
    assert vetted[1].proposal.applicability.value == "needs_calculation"        # assumptions not listed
    assert vetted[2].proposal.needed_calculation and vetted[2].changes


def test_kept_proposals_become_records_no_one_has_verified() -> None:
    t = "Implications of unitarity and gauge invariance for simplified dark matter models"
    vetted = scouting.vet(ScoutReport(proposals=[proposal("1510.02110", t, "collider", "applies_with_assumptions",
                                                          assumptions=["a Z′ completion"])]),
                          has_completion=True, resolver=resolver)
    record = scouting.proposed_records(vetted, "X")[0]
    assert record.source == "arXiv:1510.02110" and not record.usable and record.verified_on is None
    assert any("proposed by the constraint scout for X" in c for c in record.checks)
