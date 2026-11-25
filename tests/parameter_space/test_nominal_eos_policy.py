"""The nominal equation-of-state policy (the owner's decision of 2026-11-23, for 1.0.0; ``core.certificate.EOS_POLICY``):
Ωh² is computed with the nominal equation of state, Saikawa & Shirai's 2018 fit, as before, and a thermal claim is
decided on it; the band across their 2020 upper and lower tables is not assessed (deferred to 1.0.2). Each thermal
claim's ``eos_band`` check is not applicable, with the policy's reason, never satisfied; no claim reads or binds the
tables. Every other check stays.

The sections follow the owner's acceptance list: A policy consistency, B numerical preservation, C the six pending
points of the B−L run (from a compact fixture of its saved verdict: ``tests/fixtures/bl_eos_verdict.json``, each
crossing's evaluation left out), E rendering and counts, F legacy and evidence. D, the thermal-history comparison, is
``tests/constraints/test_low_temperature_comparison.py``. These are headless tests on toys and saved values; nothing
here recalculates the B−L run."""
import hashlib
import json
from pathlib import Path

import pytest

from adroit.constraints import relic
from adroit.core import certificate
from adroit.core.certificate import EOS_NOT_ASSESSED, OPEN, POLICY, Check, reading
from adroit.parameter_space import certification
from adroit.parameter_space.verdict import Verdict
from tests.parameter_space.test_eos_verdict import _grid, toy, v  # noqa: F401  (the toy fixture)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "bl_eos_verdict.json"


def _bl() -> Verdict:
    return Verdict.model_validate(json.loads(FIXTURE.read_text())["verdict"])


@pytest.fixture
def no_tables(monkeypatch):
    """The 2020 tables not installed, and any read of one an error: nothing on the nominal path may need them."""
    monkeypatch.setattr(relic, "eos_folder", lambda: None)

    def refused(*args, **kwargs):
        raise AssertionError("a deferred equation-of-state variation was computed")
    monkeypatch.setattr(relic, "eos_variant", refused)
    monkeypatch.setattr(relic, "band_values", refused)
    monkeypatch.setattr(v, "_eos_root", refused)
    monkeypatch.setattr(v, "_eos_new_roots", refused)


def _nominal(check: Check | None) -> bool:
    return check is not None and check.state == "not_applicable" and check.reason == EOS_NOT_ASSESSED


# --- A. policy consistency --------------------------------------------------------------------------------------------

def test_the_policy_is_nominal_and_its_check_is_not_applicable_never_satisfied() -> None:
    assert certificate.EOS_POLICY == "nominal" and not certificate.eos_band_assessed()
    check = certificate.nominal_eos_check()
    assert check.state == "not_applicable" and "not assessed" in check.reason and "1.0.2" in check.reason
    assert POLICY != "consistency-hd-2026-11-12"                  # the prerequisites changed: a new policy identity


@pytest.mark.parametrize("threshold, status", [(25.0, "viable"), (15.0, "excluded")])
def test_a_plane_root_is_decided_on_the_nominal_without_the_tables(toy, no_tables, threshold, status):  # noqa: F811
    """A: the same nominal evidence, viable or excluded, is decided with the tables missing and their variations
    never computed (``no_tables`` raises on any); its band check is the policy's, and it binds no table."""
    toy["threshold"] = threshold
    verdict = v.verdict(_grid())
    assert verdict.crossings and all(c.status == status for c in verdict.crossings)
    assert verdict.level == status and not verdict.unresolved and not verdict.table_roots
    for c in verdict.crossings:
        assert _nominal(c.certificate.check("eos_band")) and c.certificate.decided
        assert c.certificate.bound.eos_tables == {} and c.certificate.policy == POLICY


def test_every_thermal_producer_gives_the_same_check(toy, no_tables, monkeypatch):  # noqa: F811
    """A: the plane's roots and theory-band points, Path 2's eligibility, the complementary relic comparison and the
    single-idea thermal points give the one check (``nominal_eos_check``)."""
    from types import SimpleNamespace
    from adroit.constraints import verdicts
    from adroit.orchestrator import physical_eligibility, single_idea
    from adroit.parameter_space.likelihood import LikelihoodSettings
    toy["threshold"] = 25.0
    combined = v.verdict(_grid(), likelihood=LikelihoodSettings())
    assert all(_nominal(c.certificate.check("eos_band")) for c in combined.crossings)
    reasons, check = physical_eligibility._eos_checked(None, None, 0.12, SimpleNamespace(assumptions=[]))
    assert reasons == [] and _nominal(check)
    band, why, check = verdicts._relic_band(None, 0.12, 0.124)
    assert why == "" and _nominal(check) and "nominal equation of state" in band
    point = SimpleNamespace(m_chi=20.0, status="excluded", excluded_by=["toy"], pending=[], certificate=None,
                            point=None, omega_h2=0.12, relative_residual=0.0)
    monkeypatch.setattr(single_idea, "_with_eos", lambda t, n, state, reason, *a: (state, reason))
    thermal, added, unresolved, tables, *_ = single_idea._eos_band(None, None, [], [point], 0.12, None, 0.5)
    assert thermal == [("not_applicable", EOS_NOT_ASSESSED)] and added == unresolved == [] and tables == {}


def test_a_damaged_unused_table_does_not_block_and_a_used_input_still_does(toy, monkeypatch):  # noqa: F811
    """A: an unused table not as published decides nothing; a relic density outside the supported thermal history,
    which the claim rests on, still leaves it pending, with its own reason (B: no unrelated pending reason is
    removed)."""
    monkeypatch.setattr(relic, "eos_unavailable", lambda: "the upper table is not as published")
    toy["threshold"] = 15.0
    assert all(c.status == "excluded" for c in v.verdict(_grid()).crossings)
    real = v.evaluate

    def outside(cls, p, *args):
        return real(cls, p, *args).model_copy(update={"relic_validity": ["outside the supported thermal history"]})
    monkeypatch.setattr(v, "evaluate", outside)
    verdict = v.verdict(_grid())
    assert verdict.crossings and all(c.status == "pending" for c in verdict.crossings)
    assert all(c.certificate is not None and not c.certificate.decided for c in verdict.crossings)
    assert all(_nominal(c.certificate.check("eos_band")) for c in verdict.crossings)


# --- B. numerical preservation ----------------------------------------------------------------------------------------

@pytest.mark.needs("eos")
def test_the_nominal_values_are_those_the_band_mode_computes(toy, monkeypatch):  # noqa: F811
    """B: the roots' places, their Ωh², statuses and the constraints deciding them are the same with the band
    assessed (where it holds) and not; only the band check differs."""
    toy["threshold"] = 15.0
    nominal = v.verdict(_grid())
    monkeypatch.setattr(certificate, "EOS_BAND_ASSESSED", True)
    banded = v.verdict(_grid())
    assert [(c.point, c.omega_h2, c.status, c.excluded_by, c.relative_residual) for c in nominal.crossings] == \
        [(c.point, c.omega_h2, c.status, c.excluded_by, c.relative_residual) for c in banded.crossings]
    assert banded.crossings[0].certificate.check("eos_band").state == "satisfied"
    assert _nominal(nominal.crossings[0].certificate.check("eos_band"))


def test_a_library_relic_density_is_unchanged() -> None:
    """B: the nominal relic calculation itself is untouched: the degrees of freedom in force outside every block are
    the 2018 fit's, as before."""
    assert relic.current_eos() == "" and relic._dof(1.0) == relic.degrees_of_freedom(1.0)
    g, h, _ = relic.degrees_of_freedom(1.0)
    assert 60 < g < 80 and 60 < h < 80


# --- C. the six pending points of the B−L run (saved values) ------------------------------------------------------------

def test_the_six_wait_on_the_band_alone_and_are_excluded_by_their_comparisons() -> None:
    verdict = _bl()
    assert len(verdict.crossings) == 48 and verdict.level == "pending"
    waiting = [c for c in verdict.crossings if c.status == "pending"]
    assert len(waiting) == 6 and all(c.certificate.computed_status == "excluded" for c in verdict.crossings)
    for c in waiting:
        assert [x.name for x in c.certificate.checks if x.state in OPEN] == ["eos_band"]
        assert "direct detection" in certification.experimental_exclusion(c)
        assert certification.status_words(c).startswith("excluded by ")


def test_under_the_policy_the_six_are_excluded_but_the_coverage_gap_keeps_the_region_open() -> None:
    """The six read as the nominal policy would make them: their band check is the policy's, every other check as
    stored. All 48 are then excluded; the 20 grid points without a relic density still leave the headline pending
    (C: no complete-region claim), its words leading with what was found."""
    verdict = _bl()
    judged = []
    for c in verdict.crossings:
        cert = c.certificate
        if c.status == "pending":
            cert = cert.model_copy(update={"policy": POLICY, "checks": [
                certificate.nominal_eos_check() if x.name == "eos_band" else x for x in cert.checks]})
            assert cert.decided
            c = c.model_copy(update={"status": "excluded", "excluded_by": list(c.certificate.computed_excluded_by),
                                     "certificate": cert})
        judged.append(c)
    assert verdict.unresolved == ["20 grid points have unavailable/invalid relic calculations"]
    level, words, _ = v.headline(judged, bool(verdict.unresolved))
    assert level == "pending" and v.all_found_excluded(judged, level)
    assert words.startswith("all 48 nominal thermal-relic crossings identified in this scan are excluded;")
    assert "no surviving thermal solution was found, but the relic-density coverage is incomplete" in words
    assert "each by" not in words                              # 3 of the 48 are not excluded by direct detection
    assert v.headline(judged, False)[0] == "excluded"          # the control: only the gap holds the region open


def test_an_unresolved_root_or_an_invalid_nominal_calculation_stays_pending() -> None:
    verdict = _bl()
    c = next(c for c in verdict.crossings if c.status == "excluded")
    unresolved = c.certificate.model_copy(update={"checks": [
        Check(name="root", state="unknown", reason="not refined") if x.name == "root" else x
        for x in c.certificate.checks]})
    assert not unresolved.decided
    invalid = c.certificate.model_copy(update={"checks": [
        Check(name="thermal_history", state="failed", reason="outside the supported history")
        if x.name == "thermal_history" else x for x in c.certificate.checks]})
    assert not invalid.decided


# --- E. rendering and counts --------------------------------------------------------------------------------------------

def test_the_checklist_counts_evaluated_and_certified_apart() -> None:
    from adroit.orchestrator import checklist
    counts = checklist._root_counts(_bl())
    assert counts == ("48 evaluated crossings: 42 certified, 6 not certified; 4 more only an equation-of-state table "
                      "has")
    line = certification.summary_lines(_bl().crossings)[0]
    assert line.startswith("Certification of these 48 points: 42 certified; 6 not certified")
    assert "all made under an earlier policy (consistency-hd-2026-11-12), as stored, not re-assessed (stale)" in line


def test_an_experimentally_undecided_point_is_not_called_excluded() -> None:
    """E: a waiting point is "excluded by" only where its open checks are its thermal claim's own; an open
    comparison, record, halo or discovery check leaves its experimental exclusion unestablished."""
    c = next(c for c in _bl().crossings if c.status == "pending")
    for name in ("finite_comparisons", "records", "halo", "discovery"):
        cert = c.certificate.model_copy(update={"checks": [*c.certificate.checks,
                                                           Check(name=name, state="unknown", reason="missing")]})
        held = c.model_copy(update={"certificate": cert})
        assert certification.experimental_exclusion(held) == []
        assert certification.status_words(held) == "pending (computed: excluded)"


def test_the_report_label_and_the_badge_lead_with_what_was_found() -> None:
    from adroit.orchestrator import study_headline, track1
    verdict = _bl()
    all_excluded = verdict.model_copy(update={"crossings": [c.model_copy(update={"status": "excluded"})
                                                           for c in verdict.crossings]})
    assert track1.level_label(all_excluded) == track1.FOUND_EXCLUDED
    assert track1.level_label(verdict) == track1.LEVELS["pending"]          # the six still waiting: as before
    data = {"verdict": json.loads(all_excluded.model_dump_json())}
    assert study_headline.headline(data, "track1").words.startswith(study_headline.FOUND_EXCLUDED)


def test_the_report_states_the_policy_once_where_the_certificates_record_it(toy):  # noqa: F811
    from adroit.orchestrator import track1
    toy["threshold"] = 15.0
    assert track1.eos_policy_lines(v.verdict(_grid()))[0].startswith("Equation of state: Ωh² is computed with")
    assert track1.eos_policy_lines(_bl()) == []                 # an older result says what its certificates say


# --- F. legacy and evidence ---------------------------------------------------------------------------------------------

def test_reading_an_old_result_changes_no_bytes_and_upgrades_no_certificate(tmp_path) -> None:
    from adroit.orchestrator import checklist
    copy = tmp_path / "verdict.json"
    copy.write_bytes(FIXTURE.read_bytes())
    before = hashlib.sha256(copy.read_bytes()).hexdigest()
    verdict = Verdict.model_validate(json.loads(copy.read_text())["verdict"])
    checklist._root_counts(verdict)
    certification.summary_lines(verdict.crossings)
    [certification.status_words(c) for c in verdict.crossings]
    assert hashlib.sha256(copy.read_bytes()).hexdigest() == before
    for c in verdict.crossings:
        assert c.certificate.policy == "consistency-hd-2026-11-12"
        assert reading(c.certificate).startswith("stale: certified under policy consistency-hd-2026-11-12")
    old = next(c for c in verdict.crossings if c.status == "pending")
    assert old.certificate.check("eos_band").state in OPEN and old.status == "pending"    # as stored


def test_a_resumed_judgement_is_certified_under_the_present_policy(toy, tmp_path):  # noqa: F811
    """F: a checkpoint holds each root's judgement before its certificate; one saved with an earlier policy's
    certificate is certified again under the present one, so a resumed run cannot mix them."""
    from adroit.core.checkpoint import Checkpoint
    toy["threshold"] = 15.0
    result = _grid()
    point = Checkpoint(tmp_path, {"a": 1}, {"d": 1})
    first, _ = v.verdict_pair(result, checkpoint=point)
    saved = first.crossings[0].model_copy(update={"certificate": first.crossings[0].certificate.model_copy(
        update={"policy": "consistency-hd-2026-11-12"})})
    point.save("cuts-points", "0", saved)
    again, _ = v.verdict_pair(result, checkpoint=point)
    assert again.crossings and all(c.certificate.policy == POLICY for c in again.crossings)
