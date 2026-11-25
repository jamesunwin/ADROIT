"""The audit loop's second cycle, its findings repaired (AL2-01..21, 2026-11-14; the AL2 repair record of 2026-11-14).

- AL2-01: a narrow s-channel pole's nodes reach the base grid, so its thermal average is its narrow-width limit.
- AL2-02: the higgsino's annihilation today is its lightest Majorana state's (the spin-0 sector), in both routes.
- AL2-03: a spin-1 mediator's width in the searches is the model's, its neutrinos included.
- AL2-04: without DarkCast, BaBar's 4μ limit leaves L_μ − L_τ undecided, never allowed.
- AL2-05: two outcomes of one name: the strongest decides.
- AL2-06: the heavy scalar, and the rootless thermal levels, wait on a record awaiting verification.
- AL2-07: the combined likelihood's direct-detection ratio is the largest lower end.
- AL2-08: inside one reading, a limit's "excludes only" flag is that of the method its inputs were read with.
- AL1-10's repair narrowed (AL2-09): an error after the provider has accepted a request (an OpenAI background response
  queued, then a poll refused) leaves its bill unknown, never settled at $0.
- AL2-10: a missing propagation file leaves the antiprotons undecided.
- AL2-11: a coupling's name is an identifier, never written into source otherwise.
- AL2-12: the classic workbench answers only its own host and starts runs only from its own pages.
- AL2-13: LHCb's B → K μμ is decided at its own record's 95%.
- AL2-14: a search whose production table is missing or does not reach is undecided, never absent.
- AL2-15: the tt̄ recast is undecided above its figures' couplings.
- AL2-16: the classic workbench's status files are written whole and read without stopping its pages; a cut-short
  nuclear-response file is set aside.
- AL2-17: the archive refuses a key after a JSON escape or an underscore.
- AL2-18: the inert doublet's rate today has its off-shell W W*; the dwarfs and the Sun are read at the physical mass.
- AL2-19: the one-event closed form integrates its region to its edges.
- AL2-20: the tests' fence covers datagrams, reverse lookups, keywords and child processes, and allows this machine.
- AL2-21: a 0σ result stores no toys.

Stub transports and stand-ins; no network, no key, no provider call (every answer simulated).
"""
from __future__ import annotations

import json
import math
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from adroit.agents.llm import BudgetedLLMClient, OpenAIClient
from adroit.constraints import propagation, relic, spin1
from adroit.constraints import searches as s
from adroit.constraints.annihilation import GEV2_TO_CM3_S
from adroit.constraints.searches import Outcome
from adroit.core.model_spec import ModelSpec
from adroit.inference import look_elsewhere
from adroit.orchestrator import signal
from adroit.parameter_space import (certification, dd_channels, limit_tables, limits, resonances, scan, searches,
                                    verdict)
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.portals.multiplet import ElectroweakMultiplet, alpha_2, alpha_y
from tests.agents.test_budget_reservations import ask


# --- AL2-01 ----------------------------------------------------------------------------------------------------

def _narrow_limit(m: float, u_r: float, x: np.ndarray) -> float:
    """π times ``thermal_average``'s weight at the pole: its value for a Breit–Wigner of unit area as Γ → 0 (the
    package's own weight, read from a top-hat of unit integral in s at u_r)."""
    half = 1e-7
    u = np.array([u_r - 2 * half, u_r - half, u_r, u_r + half, u_r + 2 * half])
    hat = np.array([0.0, 1.0, 1.0, 1.0, 0.0]) / (8 * m * m * (1 + u_r) * 3 * half)
    return math.pi * float(relic.thermal_average(u, hat, x)[0])


@pytest.mark.parametrize("width", [1e-4, 1e-6, 1e-8])
def test_a_narrow_poles_thermal_average_is_its_narrow_width_limit(width) -> None:
    """M = 100 GeV, m = 45 GeV, x = 20: the shipped grid had given 1.23, 26 and more times the limit."""
    m, mass, x = 45.0, 100.0, np.array([20.0])
    u = relic.energy_grid(m, mass, width)
    sigma = mass * width / (((2 * m * (1 + u)) ** 2 - mass ** 2) ** 2 + (mass * width) ** 2)
    assert relic.thermal_average(u, sigma, x)[0] == pytest.approx(_narrow_limit(m, mass / (2 * m) - 1, x), rel=3e-3)


def test_a_wide_poles_nodes_are_as_before() -> None:
    m, mass, width = 45.0, 100.0, 5.0
    u_r, w = mass / (2 * m) - 1, width / (4 * m)
    peak = u_r + w * np.concatenate([-np.geomspace(60, 1e-3, 150), [0.0], np.geomspace(1e-3, 60, 150)])
    before = np.concatenate([[0.0], np.union1d(np.geomspace(1e-9, 80.0, 900), peak[(peak > 0) & (peak < 80.0)])])
    assert np.array_equal(relic.energy_grid(m, mass, width), before)


# --- AL2-02 ----------------------------------------------------------------------------------------------------

def test_the_higgsinos_rate_today_is_its_lightest_majorana_states() -> None:
    """At tree level, compared as a Dirac pair (halved): πα₂²(3 + 2t² + t⁴)/16M², the spin-0 sector's WW and ZZ; it
    had been the degenerate Dirac pair's, 2.4–3 times as large."""
    m = 369.8
    h = ElectroweakMultiplet(name="h", multiplet="higgsino", sommerfeld=False)
    t2 = alpha_y(2 * m) / alpha_2(2 * m)
    expected = math.pi * alpha_2(2 * m) ** 2 * (3 + 2 * t2 + t2 ** 2) / (16 * m * m) * GEV2_TO_CM3_S
    today = h.sigma_v_today(Point(m_chi=m, m_med=1.0, g_q=0.0), 1e-3)
    assert set(today) == {"W"} and not h.self_conjugate()
    assert 0.5 * today["W"] == pytest.approx(expected, rel=1e-9, abs=0.0)     # abs: approx's own is 1e-12
    assert h.cmb_sigma_v(Point(m_chi=m, m_med=1.0, g_q=0.0)) == {"W": today["W"]}


def test_the_generic_higgsino_waits_where_its_split_rate_is_not_computed(monkeypatch) -> None:
    """A higgsino-like Dirac doublet whose spin-0 rate G8 cannot compute has no rate today, with the reason (G6's tree
    level is the degenerate pair's); where G8 computes it, G8's is taken, long-range forces today or not."""
    from adroit.parameter_space.portals import generic
    from tests.parameter_space.test_generic_today import _higgsino
    engine, p = _higgsino(1000.0)
    monkeypatch.setattr(generic, "_today_long_range", lambda *args: "")
    monkeypatch.setattr(generic, "_enhanced_today", lambda *args: None)
    assert engine.today_unknown(p) == generic.SPLIT_REASON
    monkeypatch.setattr(generic, "_enhanced_today", lambda *args: (("W", 1.0e-26),))
    assert engine.today_unknown(p) == "" and engine.sigma_v_today(p, 1e-3) == {"W": 1.0e-26}


def test_the_winos_rate_today_is_unchanged() -> None:
    w = ElectroweakMultiplet(name="w", multiplet="wino", sommerfeld=False)
    m = 1000.0
    assert sum(w.sigma_v_today(Point(m_chi=m, m_med=1.0), 1e-3, with_lines=True).values()) == pytest.approx(
        2 * math.pi * alpha_2(2 * m) ** 2 / m ** 2 * GEV2_TO_CM3_S, rel=1e-9, abs=0.0)


# --- AL2-03 ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", [spin1.Spin1Kind.vector, spin1.Spin1Kind.axial])
def test_a_spin1_mediators_width_in_the_searches_is_the_models(kind) -> None:
    c, p = Spin1Class(kind=kind), Point(m_chi=2000.0, m_med=3000.0, g_chi=1.0, g_q=0.01, g_l=0.1)
    widths = searches._z_prime(c, p)[3]
    assert sum(widths.values()) == pytest.approx(spin1.width(c.model(p), p.m_chi), rel=1e-12)
    assert all(widths[(n, -n)] > 0 for n in (12, 14, 16))
    assert widths[(11, -11)] / sum(widths.values()) == pytest.approx(0.2137, abs=1e-3)


# --- AL2-04 ----------------------------------------------------------------------------------------------------

def test_without_darkcast_babar_leaves_lmu_ltau_undecided(monkeypatch) -> None:
    real = s._tool
    monkeypatch.setattr(s, "_tool", lambda name: None if name == "DarkCast" else real(name))
    found = searches._lmu_native_at(Point(m_chi=1.0, m_med=1.0, g_q=5e-3), 1e-6, 0.3, 1 / 3, 0.0, True)
    assert found.excluded is None and "DarkCast" in found.why
    far = searches._lmu_native_at(Point(m_chi=1.0, m_med=20.0, g_q=5e-3), 1e-6, 0.3, 1 / 3, 0.0, True)
    assert "DarkCast" not in far.why                                    # beyond BaBar's √s it never applied


# --- AL2-05 ----------------------------------------------------------------------------------------------------

def test_two_outcomes_of_one_name_keep_the_exclusion() -> None:
    excluded, ratios, pending = {}, {}, []
    scan._add_searches([Outcome(name=searches.DILEPTON, excluded=True, ratio=5.0),
                        Outcome(name=searches.DILEPTON, excluded=False, ratio=0.01)], {}, excluded, {}, pending, ratios)
    assert excluded == {searches.DILEPTON: True} and ratios == {searches.DILEPTON: 5.0} and not pending
    excluded, ratios, pending = {}, {}, []
    scan._add_searches([Outcome(name=searches.DILEPTON, excluded=None, why="one"),
                        Outcome(name=searches.DILEPTON, excluded=False, ratio=0.1),
                        Outcome(name=searches.DILEPTON, excluded=None, why="two")], {}, excluded, {}, pending, ratios)
    assert excluded == {searches.DILEPTON: None} and pending == [f"{searches.DILEPTON}: one; two"]


# --- AL2-06 ----------------------------------------------------------------------------------------------------

@pytest.mark.needs("production_tables")
def test_the_heavy_scalar_waits_on_a_record_awaiting_verification(monkeypatch) -> None:
    from adroit.parameter_space.portals.higgs import SingletMixing
    cls, p = SingletMixing(), Point(m_chi=200.0, m_med=300.0, g_chi=0.1, g_q=0.25)
    assert searches.heavy_scalar(cls, p, True).excluded is True              # ZZ excludes (ratio 2.2), WW does not
    real = s._blocked

    def blocked(name, record, unverified):
        if record == "atlas-2009.14791-zz":
            return Outcome(name=name, excluded=None, why="its record (atlas-2009.14791-zz) awaits a person's verification")
        return real(name, record, unverified)
    monkeypatch.setattr(s, "_blocked", blocked)
    found = searches.heavy_scalar(cls, p, False)
    assert found.excluded is None and "atlas-2009.14791-zz" in found.why


def _rootless_result(unverified: bool, omega: float):
    request = SimpleNamespace(unverified_records=unverified)
    return SimpleNamespace(request=request, points=[SimpleNamespace(omega_h2=omega)] * 4)


@pytest.mark.parametrize("usable", [True, False])
def test_a_rootless_level_waits_on_the_relic_targets_record(monkeypatch, usable) -> None:
    from adroit.parameter_space import likelihood
    monkeypatch.setattr(likelihood, "DENSITY_USABLE", usable)
    found = verdict._rootless(_rootless_result(False, 1.0), [], [], 0, "cuts", 0.12)
    assert found.level == ("overabundant" if usable else "pending")
    if not usable:
        assert any("awaits a person's verification" in u for u in found.unresolved)
        enabled = verdict._rootless(_rootless_result(True, 1.0), [], [], 0, "cuts", 0.12)
        assert enabled.level == "overabundant" and "planck" in enabled.qualifiers[0]


def test_the_single_ideas_no_thermal_waits_on_the_relic_targets_record(monkeypatch) -> None:
    from adroit.orchestrator import single_idea
    from adroit.parameter_space import likelihood
    monkeypatch.setattr(single_idea, "_fit_verdict", lambda fits: ("fits", ""))
    monkeypatch.setattr(single_idea, "_fits", lambda band, thermal: [])
    monkeypatch.setattr(single_idea, "_undecided_thermal", lambda thermal: [])
    monkeypatch.setattr(likelihood, "DENSITY_USABLE", False)
    assert single_idea._level([], [], computed=True)[0] == "undetermined"
    level, text = single_idea._level([], [], computed=True, unverified=True)
    assert level == "no_thermal" and "unverified records" in text
    monkeypatch.setattr(likelihood, "DENSITY_USABLE", True)
    assert single_idea._level([], [], computed=True)[0] == "no_thermal"


def test_the_relic_targets_rule_is_certifys() -> None:
    assert certification.relic_target(False)[0] == "" or "awaits" in certification.relic_target(False)[0]


# --- AL2-07 ----------------------------------------------------------------------------------------------------

def test_the_combined_ratio_is_the_largest_lower_end() -> None:
    found = dd_channels.Outcome(excluded=True, pending=[], channels=[
        dd_channels.ChannelOutcome(kind="SI", sigma_cm2=1e-45, ratio=1.25, ratio_band=(1.2, 1.25)),
        dd_channels.ChannelOutcome(kind="SD-neutron", sigma_cm2=1e-40, ratio=3.0, ratio_band=(0.2, 3.0))])
    assert found.combinable == 1.2


# --- AL2-08 ----------------------------------------------------------------------------------------------------

def test_inside_a_reading_the_flag_is_the_methods_its_inputs_were_read_with(monkeypatch) -> None:
    """The optimum interval installed after a module's inputs were first read in a reading: the limit those inputs
    keep is the maximum gap's, and so is its flag; outside the reading, as now."""
    now = {"method": "maximum gap (Yellin 2002)"}
    monkeypatch.setattr(limit_tables, "_inputs_now", lambda module: (f"v-{now['method']}", now["method"]))
    with limit_tables.reading():
        assert limits.fallback("CRESST-III 2019") == limits.MAXIMUM_GAP_FALLBACK
        now["method"] = "optimum interval (Yellin 2002)"
        assert limits.fallback("CRESST-III 2019") == limits.MAXIMUM_GAP_FALLBACK
    assert limits.fallback("CRESST-III 2019") == ""


# --- AL2-09 (AL1-10's repair narrowed) ----------------------------------------------------------------------------

class _RateLimited(Exception):
    """A provider's 429, as the SDKs' APIStatusError carries it (simulated)."""
    status_code = 429


def _background(tmp_path, create, retrieve) -> BudgetedLLMClient:
    raw = OpenAIClient(model="gpt-5.6-sol", max_tokens=128, background=True,
                       client=SimpleNamespace(responses=SimpleNamespace(create=create, retrieve=retrieve,
                                                                         cancel=lambda rid: None)))
    raw.poll_s = 0.0
    return BudgetedLLMClient(raw, dollar_budget=.25, ledger_path=tmp_path / "background.jsonl")


def _states(llm: BudgetedLLMClient) -> list[tuple[str, object]]:
    return [(e["state"], e.get("refused")) for e in map(json.loads, llm.ledger_path.read_text().splitlines())]


def test_a_poll_refused_after_the_provider_accepted_the_request_keeps_its_reservation(tmp_path) -> None:
    """Queued (in progress: billable), then the poll refused with 429: the bill is not known, so the reservation is
    kept and the request journalled as uncertain, never settled at $0."""
    queued = SimpleNamespace(id="queued", status="in_progress")

    def retrieve(response_id):
        raise _RateLimited("SIMULATED 429 while polling")
    llm = _background(tmp_path, lambda **kw: queued, retrieve)
    with pytest.raises(_RateLimited):
        ask(llm)
    assert llm.account.reservations and llm.account.committed() > 0.0
    assert ("billing_uncertain", None) in _states(llm) and not any(s == "settled" for s, _ in _states(llm))


def test_a_background_request_refused_before_it_is_accepted_is_settled_at_zero(tmp_path) -> None:
    def create(**kw):
        raise _RateLimited("SIMULATED 429 on submission")
    llm = _background(tmp_path, create, lambda rid: None)
    with pytest.raises(_RateLimited):
        ask(llm)
    assert not llm.account.reservations and llm.account.committed() == 0.0
    assert ("settled", 429) in _states(llm)


def test_the_next_request_is_judged_afresh(tmp_path) -> None:
    """An accepted request's mark does not outlive it: the client's next request, refused on submission, is settled
    at $0."""
    queued = SimpleNamespace(id="queued", status="in_progress")
    calls = []

    def create(**kw):
        calls.append(kw)
        if len(calls) == 1:
            return queued
        raise _RateLimited("SIMULATED 429 on submission")

    def retrieve(response_id):
        raise _RateLimited("SIMULATED 429 while polling")
    llm = _background(tmp_path, create, retrieve)
    for _ in range(2):
        with pytest.raises(_RateLimited):
            ask(llm)
    assert _states(llm)[-1] == ("settled", 429) and len(llm.account.reservations) == 1


# --- AL2-10 ----------------------------------------------------------------------------------------------------

class _Annihilating:
    def __init__(self, rates: dict[str, float]) -> None:
        self.rates = rates

    def sigma_v_today(self, p, v):
        return dict(self.rates)


def test_without_its_propagation_file_the_antiproton_bound_is_undecided(tmp_path, monkeypatch) -> None:
    record = "calore-2202.03076-pbar"
    limit = s.interpolate(s._bundled(record)["limits"]["bb"], 1000.0)
    cls, p = _Annihilating({"b": 2 * 1.2 * limit}), Point(m_chi=1000.0, m_med=1.0)
    monkeypatch.setattr(propagation, "DATA", tmp_path)
    propagation.load.cache_clear()
    try:
        assert "is missing" in propagation.unavailable(record)
        with pytest.raises(propagation.Unavailable):
            propagation.factor(record, "conservative", 100.0)
        assert "missing" in propagation.describe(record, "conservative")
        for model in propagation.MODELS:
            with propagation.using(model):
                found = searches.antiprotons(cls, p, True)
            assert found.excluded is None and "is missing" in found.why
        assert propagation.factor("no-such-record", "conservative", 100.0) == 1.0     # not from cosmic rays
    finally:
        propagation.load.cache_clear()


# --- AL2-11 ----------------------------------------------------------------------------------------------------

def _spec_with_coupling(name: str) -> dict:
    return {"name": "m", "fields": [{"name": "chi", "role": "dark_matter", "spin": 0.5, "mass_gev": 100.0}],
            "couplings": [{"name": name, "value": 0.1}]}


@pytest.mark.parametrize("name", ["x = 0\nimport os", "g'", "g q", "g-q", "λ", "1g", ""])
def test_a_coupling_name_that_is_not_an_identifier_is_refused(name) -> None:
    with pytest.raises(ValueError, match="cannot name a coupling"):
        ModelSpec.model_validate(_spec_with_coupling(name))


def test_an_identifier_names_a_coupling_and_the_ufo_writer_refuses_any_other() -> None:
    from adroit.library.interactions import ufo
    assert ModelSpec.model_validate(_spec_with_coupling("g_chi_2")).couplings[0].name == "g_chi_2"
    with pytest.raises(ValueError, match="not an identifier"):
        ufo._parameter_text(ufo.UfoParameter(name="dmc_x = 1\nimport os", value=1.0, block="DMINPUTS", code=1))


# --- AL2-12 ----------------------------------------------------------------------------------------------------

@pytest.fixture
def classic(tmp_path):
    from adroit.workbench import server
    from adroit.workbench.jobs import Board
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler_for(Board(tmp_path / "runs")))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield httpd, tmp_path / "runs"
    httpd.shutdown()


def _status(httpd, path: str, headers: dict, data: bytes | None = None) -> int:
    class Keep(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    request = urllib.request.Request(f"http://127.0.0.1:{httpd.server_port}{path}", data=data, headers=headers)
    try:
        return urllib.request.build_opener(Keep).open(request, timeout=10).status
    except urllib.error.HTTPError as error:
        return error.code


def test_the_classic_workbench_refuses_another_sites_request(classic) -> None:
    httpd, runs = classic
    form = b"card=NOPE&isospin=&values=&masses="
    own = f"127.0.0.1:{httpd.server_port}"
    assert _status(httpd, "/", {"Host": f"other.example:{httpd.server_port}"}) == 403
    assert _status(httpd, "/run/exclusion", {"Host": own, "Origin": "https://other.example"}, form) == 403
    assert not runs.exists() or not [p for p in runs.iterdir() if p.is_dir()]
    assert _status(httpd, "/", {"Host": own}) == 200
    assert _status(httpd, "/", {"Host": f"localhost:{httpd.server_port}"}) == 200


# --- AL2-13 ----------------------------------------------------------------------------------------------------

def test_lhcbs_search_is_decided_at_its_own_records_level(monkeypatch) -> None:
    decided = Outcome(name=searches.FLAVOUR_MUMU, excluded=True, ratio=2.0, value=1e-9)
    monkeypatch.setattr(searches, "EVALUATORS", (lambda cls, p, unverified: decided,))
    monkeypatch.setattr(resonances, "EVALUATORS", ())
    (found,) = searches.outcomes(None, Point(m_chi=1.0, m_med=1.0, g_chi=1.0))
    assert found.excluded is True and found.confidence_level == 0.95
    assert "1612.07818" in found.source or "LHCb" in found.source


# --- AL2-14 ----------------------------------------------------------------------------------------------------

def test_the_dilepton_recast_without_its_table_is_undecided(monkeypatch) -> None:
    from adroit.constraints import production
    monkeypatch.setattr(production, "sigma_pb", lambda *a, **k: None)
    found = searches._atlas_dilepton(1000.0, 1.0, 0.01, 0.1, True)
    assert found is not None and found.excluded is None and "zprime_spin1_BminusL" in found.why


def test_the_inert_doublets_pairs_without_their_tables_are_undecided(monkeypatch) -> None:
    from adroit.constraints import production
    state = lambda m: SimpleNamespace(mass=m, width=1e-3)                        # noqa: E731
    cls = SimpleNamespace(dm="~H0", model=lambda p: SimpleNamespace(particles={"~H0": state(80.0), "~A0": state(120.0),
                                                                               "~H+": state(130.0)}))
    monkeypatch.setattr(production, "unavailable", lambda *names: "MadGraph's production tables idm_… not in the "
                                                                  "tools folder (adroit setup --fetch)")
    assert searches._inert_pair(cls, Point(m_chi=80.0, m_med=1.0)) == ("", None)


@pytest.mark.needs("production_tables")
def test_the_cms_dijet_limit_without_its_table_is_undecided(monkeypatch) -> None:
    from adroit.constraints import production
    p = Point(m_chi=1000.0, m_med=1500.0, g_chi=1.0, g_q=0.1)
    assert resonances._cms_unknown(p) == ""
    monkeypatch.setattr(production, "sigma_pb", lambda *a, **k: None)
    assert "zprime_spin1_vector" in resonances._cms_unknown(p)
    assert resonances._cms_unknown(Point(m_chi=1.0, m_med=100.0)) == ""               # below CMS's masses


# --- AL2-15 ----------------------------------------------------------------------------------------------------

def test_the_ttbar_recast_is_undecided_above_its_figures_couplings() -> None:
    data = s._bundled("cms-1908.01115-ttbar")
    assert resonances._ttbar_state(data, "scalar", 400.0, 12.0, 5.0) is None
    assert resonances._excluded_at(data["borders"]["scalar"]["25.0"], 700.0, 10.0) is None
    assert resonances._ttbar_state(data, "scalar", 400.0, 12.0, 2.9) is True
    assert max(g for cp in data["borders"].values() for entry in cp.values() for curve in entry.values()
               for _, g in curve) <= resonances.TTBAR_G_REACH


# --- AL2-16 ----------------------------------------------------------------------------------------------------

def test_a_status_file_cut_short_does_not_stop_the_runs_page(tmp_path) -> None:
    from adroit.workbench import jobs
    folder = tmp_path / "20261114-120000_exclusion_x"
    folder.mkdir()
    (folder / jobs.STATUS_FILE).write_text('{"id": "20261114-120000_exclusion_x", "kind": "excl')
    (found,) = jobs.list_runs(tmp_path)
    assert found.status == "unreadable" and "cannot be read" in found.error and found.kind == "exclusion"


def test_a_jobs_status_file_is_replaced_whole(tmp_path, monkeypatch) -> None:
    from adroit.core import durable
    from adroit.workbench import jobs
    written, real = [], durable.write_atomic
    monkeypatch.setattr(durable, "write_atomic", lambda path, data, **kw: written.append(Path(path).name) or
                        real(path, data, **kw))
    board = jobs.Board(tmp_path)
    job = board.submit("exclusion", "t", {}, lambda folder: None)
    board.wait()
    folder = tmp_path / job.id
    assert written and set(written) == {jobs.STATUS_FILE}
    assert jobs.read(folder).status == "done" and sorted(p.name for p in folder.iterdir()) == [jobs.STATUS_FILE]


def test_loading_a_module_heals_the_responses_first(monkeypatch) -> None:
    from adroit.experiments import registry, response_cache
    seen = []
    monkeypatch.setattr(response_cache, "heal_now", lambda: seen.append(1) or ())
    try:
        registry.load_module(next(iter(registry.MODULES)))
    except Exception:  # noqa: BLE001 - its data may not be fetched: the healing comes first either way
        pass
    assert seen


def test_a_cut_short_nuclear_response_is_set_aside_once_settled(tmp_path, caplog) -> None:
    from adroit.experiments import response_cache
    folder = tmp_path / "nuclear-responses"
    folder.mkdir()
    (folder / "haxton_Xe131_GCN5082.json").write_text('{"F|0|0": [1.0, 0.9')
    (folder / "haxton_F19_bw.json").write_text('{"F|0|0": [1.0]}')
    (folder / "haxton_Ge70_GCN2850.json").write_text('{"F|0')                        # being written now
    old = time.time() - 2 * response_cache.SETTLED_S
    for name in ("haxton_Xe131_GCN5082.json", "haxton_F19_bw.json"):
        os.utime(folder / name, (old, old))
    done = response_cache.heal(tmp_path)
    assert len(done) == 1 and "haxton_Xe131_GCN5082.json" in done[0]
    names = sorted(p.name for p in folder.iterdir())
    assert "haxton_Xe131_GCN5082.json" not in names and any(n.startswith("haxton_Xe131_GCN5082.json.unreadable-")
                                                               for n in names)
    assert {"haxton_F19_bw.json", "haxton_Ge70_GCN2850.json"} <= set(names)
    assert any("haxton_Xe131_GCN5082.json" in r.getMessage() and r.levelname == "WARNING" for r in caplog.records)


# --- AL2-17 ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("before", [b"", b" ", b"\\n", b"\\t", b"_", b"\\u2028", b'\\"'])
def test_the_archive_refuses_a_keys_shape_after_an_escape(before) -> None:
    from adroit.evidence import archive
    with pytest.raises(ValueError, match="credential-like"):
        archive._put({}, "results/r.json", b'{"x": "' + before + b"sk-" + b"A" * 40 + b'"}')


def test_the_archive_takes_words_that_merely_contain_sk() -> None:
    from adroit.evidence import archive
    files: dict[str, bytes] = {}
    archive._put(files, "report.md", b"task-specific-settings and risk-weighted-averages-of-things")
    assert files


# --- AL2-18 ----------------------------------------------------------------------------------------------------

@pytest.mark.needs("ufo_models")
def test_the_inert_doublets_rate_today_has_its_off_shell_w_pairs() -> None:
    from adroit.parameter_space import library
    idm = library.entry("inert_doublet").model_class
    today = idm.sigma_v_today(Point(m_chi=72.0, m_med=120.0, g_chi=0.002, g_q=40.0), 1e-4)
    assert today.get("W", 0.0) > 1e-27 and sum(today.values()) > 1e3 * 8.7e-30


class _Shifted:
    """A stand-in whose physical mass differs from its Lagrangian m_χ (as a generic model's can)."""

    def self_conjugate(self) -> bool:
        return True

    def dark_matter_mass(self, p) -> float:
        return 114.15

    def sigma_v_today(self, p, v) -> dict[str, float]:
        return {"W": 1e-26}


def test_the_dwarfs_mixture_is_read_at_the_physical_mass(monkeypatch) -> None:
    seen = []

    def mixture(channels, mass, curves, conjugate):
        seen.append(mass)
        return SimpleNamespace(excluded=True, ratio=2.0, why=lambda: "excluded by the mixture rule")   # AL4-12: it states why
    monkeypatch.setattr(scan, "fermi_mixture", mixture)
    monkeypatch.setattr(scan, "_fermi_limits", lambda: {})
    scan._fermi_mixture(_Shifted(), Point(m_chi=100.0, m_med=1.0), {"b": 1e-26}, True)
    assert seen == [114.15]


def test_the_sun_applies_at_the_physical_mass(monkeypatch) -> None:
    """IceCube's curves from 110 GeV: a point stated at 100 GeV, physically 114.15 GeV, is in their range."""
    monkeypatch.setattr(scan, "_icecube_limits", lambda: {"WW": [[110.0, 1e-40], [1000.0, 1e-40]]})
    assert scan._icecube_applies(_Shifted(), Point(m_chi=100.0, m_med=1.0)) is True


# --- AL2-19 ----------------------------------------------------------------------------------------------------

def test_the_closed_forms_region_is_integrated_to_its_edges() -> None:
    """One Gaussian candidate on a flat background: the closed form agrees with the same measure on a grid twenty times
    finer, where the trapezoid rule's half cells had put it 6–9% above the toys."""
    def p_on(nodes: int) -> float:
        energies = np.linspace(0.0, 100.0, nodes)
        g = np.exp(-0.5 * ((energies - 20.0) / 2.0) ** 2)
        shape = (g / np.trapezoid(g, energies))[None, :]
        background = np.full(nodes, 0.05 / 100.0)
        z = look_elsewhere.max_significance(shape, energies, np.array([22.0]), background)
        return look_elsewhere.one_event_p_value(z - 1e-9, shape, energies, background)
    assert p_on(401) == pytest.approx(p_on(8001), rel=2e-3)


# --- AL2-20 ----------------------------------------------------------------------------------------------------

def test_the_fence_refuses_datagrams_reverse_lookups_and_keywords(_no_network) -> None:
    """Each call is made only once its function is seen to be the fence's, and the datagram is given a stand-in for a
    socket, which nothing can be sent through: on a tree without this fence the test fails sending nothing (as first
    written, at cycle 2's pin it sent one datagram to TEST-NET-1)."""
    for function in (socket.getaddrinfo, socket.gethostbyaddr, socket.gethostbyname_ex, socket.socket.sendto,
                     socket.socket.sendmsg):
        assert "_Fence.install" in getattr(function, "__qualname__", ""), function
    with pytest.raises(OSError, match="fenced"):
        socket.socket.sendto(SimpleNamespace(family=socket.AF_INET), b"x", ("192.0.2.1", 53))   # TEST-NET-1
    with pytest.raises(OSError, match="fenced"):
        socket.gethostbyaddr("192.0.2.1")
    with pytest.raises(OSError, match="fenced"):
        socket.gethostbyname_ex("example.invalid")
    with pytest.raises(OSError, match="fenced"):
        socket.getaddrinfo(host="example.invalid", port=80)
    assert len(_no_network) == 4
    _no_network.clear()                                                  # this test's own attempts: not its failure


def test_the_fence_takes_this_machines_own_name_as_local() -> None:
    from tests.conftest import FENCE
    assert not FENCE.remote(socket.gethostname()) and FENCE.remote("example.invalid")


def test_a_child_process_is_fenced(tmp_path) -> None:
    """A Python process a test starts imports the release layer's guard, first on its path, and refuses another host,
    journalling it (here to the test's own file, so this test's attempt is not its failure)."""
    from tests.conftest import CHILD_GUARD
    assert os.environ["PYTHONPATH"].split(os.pathsep)[0] == str(CHILD_GUARD)
    journal = tmp_path / "child.jsonl"
    code = ("import socket\nif not hasattr(socket, 'ADROIT_NETWORK_GUARD'):\n    print('unfenced')\nelse:\n    try:\n"
            "        socket.getaddrinfo('example.invalid', 80)\n        print('reached')\n    except OSError:\n"
            "        print('refused')\n")                     # nothing is tried unless the guard is there
    found = subprocess.run([sys.executable, "-c", code], env={**os.environ, "ADROIT_NETWORK_GUARD_LOG": str(journal)},
                           capture_output=True, text=True, timeout=60, check=True)
    assert found.stdout.strip() == "refused" and "example.invalid" in journal.read_text()


# --- AL2-21 ----------------------------------------------------------------------------------------------------

def test_small_values_are_compared_relatively() -> None:
    """The suite's own rule (``tests/conftest.py``): an expected value below 10⁻⁹ without ``abs`` is compared
    relatively, so a comparison of cross-sections or rates can fail; ``abs``, and an expected 0, are pytest's own."""
    assert 1e-25 != pytest.approx(2e-25, rel=0.03) and 1e-25 == pytest.approx(1.01e-25, rel=0.03)
    assert 1e-13 == pytest.approx(0.0) and 1e-25 == pytest.approx(2e-25, abs=1e-24)


def test_a_zero_sigma_result_stores_no_toys() -> None:
    assert signal.toy_record(0.0, 1.0, 200_000) == (None, None)
    toys, interval = signal.toy_record(2.0, 0.01, 1000)
    assert toys == 1000 and interval[0] < 0.01 < interval[1]


def test_a_zero_sigma_report_names_no_toys() -> None:
    zero = SimpleNamespace(max_local_z=0.0, global_method="rule that a largest local significance of 0σ is reached")
    drawn = SimpleNamespace(max_local_z=2.0, global_method="200,000 background-only toys")
    nothing = SimpleNamespace(max_local_z=1.0, global_method="not computed: no completed candidate fits")
    assert not signal._toys_drawn(zero) and signal._toys_drawn(drawn) and not signal._toys_drawn(nothing)


def test_the_release_notes_give_the_misses_measured() -> None:
    """The measured misses of the precomputed limit tables, stated where a user reads the known limits (the README
    of 1.0.0 points to the release notes for them)."""
    text = (Path(__file__).resolve().parents[2] / "docs" / "release_notes_v1.0.0.md").read_text()
    assert "by up to 1.7%" in text and "by at most 0.91%" not in text
