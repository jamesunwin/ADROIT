"""The independent audit of 774372f, its findings repaired (NA15-01..11, 2026-11-16;
The independent audit of 2026-11-16 (independent); the AL3 repair record of 2026-11-15).

- NA15-01: the background-rate profile reaches its maximum on θ's bound, and a fit that is not a maximum is
  unresolved, never published.
- NA15-02: recovery reads a journalled answer of either provider, so an OpenAI answer already paid for is not asked
  for again.
- NA15-03, NA15-04: a new state's widths, and the thermal-contact check, count colour and identical particles as
  ``feynman.widths`` does, over every structure.
- NA15-05: the Sun's equilibrium takes the population's convention (self-conjugate or a symmetric Dirac pair).
- NA15-06: toy events are drawn exactly from the piecewise-linear background.
- NA15-07: the mixture rule is an approximation, said where it decides.
- NA15-08: an experimental asset is parsed from one checked read of its bytes.
- NA15-09: an alternative with no events on a target separates by its rate.
- NA15-10: the Coulomb factor is not capped.
- NA15-11: a background response's deadline counts the time truly elapsed.

Simulated providers (local fixtures, no request sent) and synthetic detectors; no network, no key, $0.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from scipy.optimize import brentq, minimize_scalar

from adroit.inference import look_elsewhere, nuisance, signal_fit


# --- NA15-01 ---------------------------------------------------------------------------------------------------

def _reference(total: float, minus: float, plus: float, centre: float, f: list[float], b: list[float]) -> tuple:
    """(ŝ, θ̂, Δ ln L) by an independent route: θ profiled by its score's root on [0, ∞) (0 where the score is not
    positive there), s by a bounded scalar search (the auditor's ``nuisance_boundary``)."""
    f, b = np.array(f), np.array(b)

    def profile(s: float) -> tuple[float, float]:
        def score(t: float) -> float:
            den = s * f + t * b
            if (den == 0).any():
                return math.inf
            return -total + (b / den).sum() - (t - centre) / (plus if t > centre else minus) ** 2
        t = 0.0 if score(0.0) <= 0 else brentq(score, 0.0, max(10.0, centre + 100 * plus, len(f) / total + 1),
                                                 xtol=1e-14)
        den = s * f + t * b
        return float(-s - t * total + np.log(den).sum() - 0.5 * ((t - centre) / (plus if t > centre else minus)) ** 2), t

    found = minimize_scalar(lambda s: -profile(s)[0], bounds=(0.0, float(len(f) + 1)), method="bounded",
                            options={"xatol": 1e-13})
    best = 0.0 if profile(0.0)[0] >= profile(float(found.x))[0] else float(found.x)
    return best, profile(best)[1], profile(best)[0] - profile(0.0)[0]


@pytest.mark.parametrize("case", [(10.0, 1.0, 1.0, 1.0, [1.0], [0.1]), (0.41, 0.62, 0.84, -1.0, [1.0], [0.01]),
                                  (0.41, 0.62, 0.84, 1.0, [1.0], [0.01]), (10.0, 0.5, 0.5, 1.0, [10.0], [0.1]),
                                  (2.0, 0.6, 0.8, -0.3, [1.0, 2.0], [0.5, 1.0])])
def test_the_profile_reaches_its_maximum_on_thetas_bound(case) -> None:
    """The auditor's five cases, the negative auxiliary centres a toy draws included: ŝ = 1, θ̂ = 0 where the event needs no
    background (24.3 and Z = 0 had been published for the first)."""
    total, minus, plus, centre, f, b = case
    rate = nuisance.BackgroundRate(total=total, minus=minus, plus=plus, centre=centre)
    s, theta, gain = nuisance.best_fits(np.array([f]), np.array(b), rate)
    s_ref, theta_ref, gain_ref = _reference(*case)
    assert s[0] == pytest.approx(s_ref, rel=1e-6, abs=1e-7) and gain[0] == pytest.approx(gain_ref, rel=1e-8)
    assert theta[0] == pytest.approx(theta_ref, abs=1e-6)
    fit = signal_fit.fit("case", np.array(f), np.array(b), rate)
    assert fit.z_local == pytest.approx(math.sqrt(2 * gain_ref), rel=1e-8)


def test_a_fit_that_is_not_a_maximum_is_unresolved(monkeypatch) -> None:
    rate = nuisance.BackgroundRate(total=10.0, minus=1.0, plus=1.0)
    monkeypatch.setattr(nuisance, "_optimal", lambda *a, **k: np.zeros(1, bool))
    s, _, gain = nuisance.best_fits(np.array([[1.0]]), np.array([0.1]), rate)
    assert np.isnan(s[0]) and np.isnan(gain[0])
    with pytest.raises(ValueError, match="did not reach its maximum"):
        signal_fit.fit("case", np.array([1.0]), np.array([0.1]), rate)
    with pytest.raises(ArithmeticError):
        look_elsewhere.max_significance(np.ones((1, 2)), np.array([0.0, 1.0]), np.array([0.5]),
                                        np.array([0.1, 0.1]), rate)


@pytest.mark.parametrize("relative", [1.0, 0.5])
def test_path_two_publishes_the_maximum_on_the_bound(monkeypatch, relative) -> None:
    """The auditor's pipeline: one event at 0.1 keV on a background of 10 events, ±100% (and ±50%): the saved fit is the
    maximum, s = 1, Z = 3.0020 (3.0020 and 2.8791), and the compatibility statistic is not negative (−40.2 had been)."""
    from adroit.core.dm_state import ExperimentInfo, ExpectedSignal, Fidelity, HaloModel, NuclearModel, \
        PublishedConventions
    from adroit.experiments import registry
    from adroit.experiments.base import ExperimentModule
    from adroit.orchestrator import signal
    from adroit.physics import targets

    class Fixture(ExperimentModule):
        GRID = np.array([0.0, 0.1, 0.2, 1.0])

        @property
        def info(self):
            return ExperimentInfo(name="boundary audit fixture", target="Ge", exposure_kg_day=1,
                                  energy_window_kev=(0.0, 1.0), fidelity=Fidelity.C)

        def target(self):
            return targets.target("Ge")

        def conventions(self):
            return PublishedConventions(halo=HaloModel(), nuclear_model=NuclearModel.shell_model)

        def published_limits(self):
            return []

        def upper_limit(self, signal, cl=0.9):
            return 2.3

        def observations(self):
            return np.array([0.1]), np.zeros(1)

        def signal_grid_kev(self):
            return self.GRID

        def background_on_grid(self):
            return np.array([0.1, 0.1, 0.1, 24.85])

        def background_rate(self):
            return nuisance.BackgroundRate(total=10.0, minus=relative, plus=relative)

        def expected_signal(self, particle, interaction, halo, model, target=None):
            return ExpectedSignal(experiment=self.info.name, particle=particle, total_events=1.0,
                                  observable=self.GRID.tolist(), density=np.ones(4).tolist())

    monkeypatch.setitem(registry.SIGNAL_SEARCHES, "boundary audit fixture", Fixture)
    request = signal.SignalRequest(experiment="boundary audit fixture", null_modules=[], toys=20, leaders=1,
                                   complementary=False, candidates=[signal.Candidate(label="fixture O1", card_id="O1",
                                                                                     isospin="s", mass_gev=10.0)])
    result = signal.run(request)
    fit = result.fits[0]
    assert not result.candidate_failures and fit.s_hat == pytest.approx(1.0, rel=1e-6)
    assert fit.z_local == pytest.approx(3.00196863 if relative == 1.0 else 2.87911755, rel=1e-6)
    assert all(e.chi2_pg >= 0.0 for e in result.tournament.ranking)


# --- NA15-02 ---------------------------------------------------------------------------------------------------

def _response(provider: str, text: str, calls: list):
    class Response:
        id, status, stop_reason, output_text = "fixture", "completed", "end_turn", text
        content = [SimpleNamespace(type="text", text=text)]
        usage = SimpleNamespace(input_tokens=100, output_tokens=100, cache_read_input_tokens=0,
                                cache_creation_input_tokens=0, input_tokens_details=SimpleNamespace(cached_tokens=0))

        def model_dump(self, **kw):
            if provider == "openai":
                return {"id": self.id, "status": self.status, "output": [{"type": "message", "role": "assistant",
                        "content": [{"type": "output_text", "text": text}]}],
                        "usage": {"input_tokens": 100, "output_tokens": 100, "input_tokens_details": {"cached_tokens": 0}}}
            return {"id": self.id, "stop_reason": "end_turn", "content": [{"type": "text", "text": text}],
                    "usage": {"input_tokens": 100, "output_tokens": 100, "cache_read_input_tokens": 0,
                              "cache_creation_input_tokens": 0}}

    def create(**kw):
        calls.append(kw)
        return Response()
    return create


def _client(provider: str, create):
    from adroit.agents.llm import LLMClient, OpenAIClient

    def make(**kw):
        if provider == "openai":
            return OpenAIClient(client=SimpleNamespace(responses=SimpleNamespace(create=create)), background=False, **kw)
        return LLMClient(client=SimpleNamespace(messages=SimpleNamespace(create=create)), **kw)
    return ("adroit.agents.llm.OpenAIClient" if provider == "openai" else "adroit.agents.llm.LLMClient"), make


@pytest.mark.parametrize("provider,model", [("anthropic", "claude-opus-5-5"), ("openai", "gpt-5.6-sol")])
def test_an_extraction_answer_paid_for_is_recovered_whatever_the_provider(tmp_path, provider, model) -> None:
    """A crash after the answer was journalled and settled, before it was saved: the rerun publishes it, one dispatch
    and its cost unchanged (OpenAI's had been sent, and paid for, again)."""
    import adroit.orchestrator.experimental_extraction as extraction
    from adroit.agents.budget import read_ledger, settled_and_uncertain
    from adroit.agents.experimental_extraction import ExtractionAnswer
    from adroit.library.experimental import ExperimentalCatalog
    source = tmp_path / "source.txt"
    source.write_text("The upper limit is 0.33 at 95 percent confidence.\n")
    catalog = ExperimentalCatalog(tmp_path / "library")
    service = extraction.ExperimentalExtraction(catalog)
    scope = service.start(catalog.import_files([source], "Recovery fixture").reference, 2, model=model, vision=False)
    calls: list = []
    answer = ExtractionAnswer(explanation="A local provider fixture; the source awaits human interpretation.")
    constructor, make = _client(provider, _response(provider, answer.model_dump_json(), calls))
    original = extraction.atomic_json

    def cut_power(path, value):
        if Path(path).parent.name == "pending":
            raise RuntimeError("simulated crash after the settled response")
        return original(path, value)
    journal = service.budgets.folder(scope.session_id) / "paid.jsonl"
    with patch(constructor, make):
        with patch.object(extraction, "atomic_json", cut_power), pytest.raises(RuntimeError, match="simulated"):
            service.step(scope.session_id)
        cost = settled_and_uncertain(read_ledger(journal))
        step = service.step(scope.session_id)
    assert len(calls) == 1 and settled_and_uncertain(read_ledger(journal)) == cost and step.output_revision


@pytest.mark.parametrize("provider,model", [("anthropic", "claude-opus-5-5"), ("openai", "gpt-5.6-sol")])
def test_a_relevance_answer_paid_for_is_recovered_whatever_the_provider(tmp_path, provider, model) -> None:
    import yaml
    from adroit.agents.budget import read_ledger, settled_and_uncertain
    from adroit.agents.constraint_discovery import DiscoveryReport
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.orchestrator.constraint_discovery import Discovery, Options
    from adroit.parameter_space.library import entry
    source = tmp_path / "model.yaml"
    source.write_text(yaml.safe_dump(entry("higgs_portal_scalar").spec().model_dump(mode="json")))
    service = Discovery(ExperimentalCatalog(tmp_path / "library"), abstracts=lambda *a: [], fetch=lambda *a: None,
                        resolver=lambda *a: {})
    session = service.start(str(source), Options(model=model, budget=2, vision=False))
    service._write(session.session_id, "inventory.json", [])
    service._write(session.session_id, "literature.json", {"queries": {}})
    calls: list = []
    constructor, make = _client(provider, _response(provider, DiscoveryReport(summary="Offline fixture.")
                                                    .model_dump_json(), calls))
    original = service._write

    def cut_power(sid, name, value):
        if name == "proposals.json":
            raise OSError("simulated: publication interrupted after the settled answer")
        return original(sid, name, value)
    journal = service.budgets.folder(session.session_id) / "paid.jsonl"
    with patch(constructor, make):
        with patch.object(service, "_write", cut_power), pytest.raises(OSError, match="simulated"):
            service._relevance(session, None)
        cost = settled_and_uncertain(read_ledger(journal))
        service._relevance(session, None)
    assert len(calls) == 1 and settled_and_uncertain(read_ledger(journal)) == cost


def test_one_reader_takes_either_providers_journalled_answer() -> None:
    from adroit.agents.llm import journalled_text
    assert journalled_text({"content": [{"type": "text", "text": "A"}, {"type": "tool_use"}]}) == "A"
    assert journalled_text({"output_text": "B", "output": []}) == "B"
    assert journalled_text({"output": [{"type": "reasoning"}, {"type": "message", "content": [
        {"type": "output_text", "text": "C"}, {"type": "refusal", "refusal": "x"}]}]}) == "C"
    for damaged in (None, "text", {"content": "text"}, {"output": [{"type": "message", "content": [{"text": 5}]}]}, {}):
        assert journalled_text(damaged) == ""


# --- NA15-03, NA15-04 ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("colour,factor", [("1", 1.0), ("3", 3.0), ("8", 8.0)])
def test_a_new_states_width_counts_its_colours(colour, factor) -> None:
    """h → Φ Φ̄ with Φ a singlet, triplet or octet: the new partial equals ``feynman.widths``'s, the singlet's times
    the colours (a triplet's had been a third of itself)."""
    from adroit.model_building.feynman import MassVertex, ParticleRecord, Rules, two_body_width, widths
    from adroit.parameter_space.portals import generic as gm
    particles = [ParticleRecord("h", 0, 125.09, "", "1", 0, 1), ParticleRecord("Phi", 0, 40.0, "Phi~", colour, 0, -1)]
    vertex = MassVertex("SSS", ("h", "Phi", "Phi~"), 20.0)
    rules = Rules(particles, [vertex], 1.0)
    assert gm._dark_width(rules, "h") == pytest.approx(widths(particles, [vertex])["h"], rel=1e-12)
    assert gm._dark_width(rules, "h") == pytest.approx(factor * two_body_width(vertex, 0, [125.09, 40.0, 40.0]),
                                                       rel=1e-12)


def test_a_new_states_width_has_its_vss_channel() -> None:
    """h₂₀₀ → Z a (VSS): 0.669 GeV, which the width had left out."""
    from adroit.model_building.feynman import MassVertex, ParticleRecord, Rules, widths
    from adroit.parameter_space.portals import generic as gm
    particles = [ParticleRecord("h", 0, 200.0, "", "1", 0, 1), ParticleRecord("a", 0, 40.0, "", "1", 0, 1),
                 ParticleRecord("Z", 1, 91.1876, "", "1", 0, 1)]
    rules = Rules(particles, [MassVertex("VSS", ("Z", "h", "a"), 0.3)], 1.0)
    assert gm._dark_width(rules, "h") == pytest.approx(widths(particles, rules.vertices)["h"], rel=1e-12)
    assert gm._dark_width(rules, "h") == pytest.approx(0.669234362, rel=1e-6)


def test_identical_final_particles_do_not_certify_contact() -> None:
    """S → h h at 0.75 H (H the Hubble rate at x = 20): its rate is 0.75 H, counted once, so contact is not certified
    (it had been counted twice, 1.5 H, and certified)."""
    from adroit.model_building.feynman import MassVertex, ParticleRecord, Rules, widths
    from adroit.parameter_space.portals import generic_checks as gc
    mass, m_h, m, x = 300.0, 125.09, 400.0, 20.0
    hubble = gc.hubble(m / x)
    unit = math.sqrt(1 - 4 * m_h ** 2 / mass ** 2) / (32 * math.pi * mass)
    particles = [ParticleRecord("S", 0, mass, "", "1", 0, 1), ParticleRecord("h", 0, m_h, "", "1", 0, 1)]
    rules = Rules(particles, [MassVertex("SSS", ("S", "h", "h"), math.sqrt(0.75 * hubble / unit))], 1.0)
    assert gc._decays(rules, "S", set(gc.SM)) == pytest.approx(0.75 * hubble, rel=1e-9)
    assert gc._decays(rules, "S", set(gc.SM)) == pytest.approx(widths(particles, rules.vertices)["S"], rel=1e-12)
    flags = gc.kinetic_flags(rules, {("chi", "chi~"): [("S", "S")]}, x, m)
    assert flags and "kinetic contact not certified" in flags[0]


# --- NA15-05 ---------------------------------------------------------------------------------------------------

def _population(capture: float, rate: float, volume: float, dirac: bool) -> float:
    """The annihilation rate at t⊙ over C/2, from the rate equations integrated (χ and χ̄ apart for a Dirac pair)."""
    from scipy.integrate import solve_ivp
    from adroit.constraints.capture import SUN_AGE_S

    def dirac_rhs(t, y):
        n, nbar = y
        return [capture / 2 - rate * n * nbar / volume, capture / 2 - rate * n * nbar / volume]

    def majorana_rhs(t, y):
        return [capture - rate * y[0] ** 2 / volume]
    if dirac:
        n, nbar = solve_ivp(dirac_rhs, (0, SUN_AGE_S), [0.0, 0.0], rtol=1e-10, atol=1.0).y[:, -1]
        return rate * n * nbar / volume / (capture / 2)
    n = solve_ivp(majorana_rhs, (0, SUN_AGE_S), [0.0], rtol=1e-10, atol=1.0).y[0, -1]
    return 0.5 * rate * n ** 2 / volume / (capture / 2)


@pytest.mark.parametrize("scale", [0.1, 1.0, 10.0])
@pytest.mark.parametrize("self_conjugate", [True, False])
def test_the_suns_equilibrium_follows_the_population(scale, self_conjugate) -> None:
    """Weak, intermediate and strong equilibrium, each population against its rate equations (a Dirac pair's had
    taken the self-conjugate form: 0.580 for 0.371 at the auditor's point)."""
    from adroit.constraints import capture
    c, m = 1e20, 100.0
    volume = 5.8e27
    rate = scale * volume / (capture.SUN_AGE_S ** 2 * c)
    found = capture.equilibrium_fraction(c, rate, m, self_conjugate=self_conjugate)
    assert found == pytest.approx(_population(c, rate, volume, not self_conjugate), rel=1e-5)


@pytest.mark.parametrize("self_conjugate,excluded,ratio", [(False, False, 2 * math.tanh(1 / math.sqrt(2)) ** 2),
                                                           (True, True, 2 * math.tanh(1.0) ** 2)])
def test_icecube_reads_the_equilibrium_of_the_classs_population(self_conjugate, excluded, ratio) -> None:
    """The auditor's comparison through ``scan._icecube`` (capture inputs alone substituted; a reference capture of C/2):
    a Dirac class 0.741, allowed; a self-conjugate one 1.160, excluded (both had been 1.160)."""
    from adroit.constraints import capture
    from adroit.core.dm_state import InteractionModel
    from adroit.parameter_space import scan
    c, m, volume = 1e20, 100.0, 5.8e27
    rate = volume / (capture.SUN_AGE_S ** 2 * c)

    class Model:
        def self_conjugate(self):
            return self_conjugate

        def sigma_v_today(self, p, speed):
            return {"b": rate}

        def interaction(self, p):
            return InteractionModel(name="fixture", layer="nonrelativistic", coefficients=[])

    def capture_fixture(particle, interaction, halo=None):
        return c if interaction.name == "fixture" else 0.5 * c
    with patch.object(capture, "available", return_value=True), patch.object(capture, "capture_rate",
                                                                             side_effect=capture_fixture):
        found = scan._icecube(Model(), SimpleNamespace(m_chi=m))
    assert found[0] is excluded and found[1] == pytest.approx(ratio, rel=1e-9) and "approximation" in found[2]


# --- NA15-06 ---------------------------------------------------------------------------------------------------

def _events(grid: np.ndarray, background: np.ndarray, seed: int) -> np.ndarray:
    seen: list[float] = []

    def capture(shapes, energies, events, background, rate):
        seen.extend(events.tolist())
        return 0.0
    with patch.object(look_elsewhere, "max_significance", capture):
        look_elsewhere.toys(np.ones((1, len(grid))), grid, background, 10_000, seed=seed)
    return np.array(seen)


def test_toy_events_follow_the_linear_density_whatever_the_grid() -> None:
    """b(E) = 2E on [0, 1]: mean 2/3 and P(E < ½) = ¼, on two nodes as on 101 collinear ones (the events had been
    uniform within a cell: mean 0.501, P 0.498 on two nodes)."""
    two, many = _events(np.array([0.0, 1.0]), np.array([0.0, 2.0]), 171), _events(np.linspace(0, 1, 101),
                                                                                  2 * np.linspace(0, 1, 101), 171)
    assert two.size > 9_000 and np.allclose(np.sort(two), np.sort(many), atol=1e-12)
    assert two.mean() == pytest.approx(2 / 3, abs=0.01) and (two < 0.5).mean() == pytest.approx(0.25, abs=0.01)


def test_the_toys_significance_does_not_depend_on_collinear_nodes() -> None:
    grid, fine = np.array([0.0, 1.0]), np.linspace(0, 1, 101)
    coarse = look_elsewhere.toys(np.ones((1, 2)), grid, 0.01 + 0.18 * grid, 10_000, seed=177)
    refined = look_elsewhere.toys(np.ones((1, 101)), fine, 0.01 + 0.18 * fine, 10_000, seed=177)
    assert np.mean(coarse >= 2.0) == pytest.approx(np.mean(refined >= 2.0), abs=1e-12)


# --- NA15-07 ---------------------------------------------------------------------------------------------------

def test_the_mixture_rule_is_stated_as_an_approximation(monkeypatch) -> None:
    """The auditor's counterexample kept: two Poisson bins, backgrounds 10 and 10, observed 10 and 12; channel A at 1.01 of
    its limit is excluded alone, yet the mixture with B in the other bin is allowed by the joint likelihood. The rule
    excludes it, and says it decides by an approximation."""
    from scipy.stats import norm
    from adroit.constraints import mixtures
    n, b, threshold = np.array([10.0, 12.0]), np.array([10.0, 10.0]), norm.ppf(0.95) ** 2

    def nll(s):
        lam = b + np.asarray(s, float)
        return float(np.sum(lam - n * np.log(lam)))

    def q(v):
        v = np.asarray(v, float)
        t = float(minimize_scalar(lambda x: nll(x * v), bounds=(0, 10), method="bounded",
                                  options={"xatol": 1e-13}).x)
        t = 0.0 if nll(np.zeros(2)) < nll(t * v) else t
        return max(0.0, 2 * (nll(v) - nll(t * v))) if t <= 1 else 0.0
    limits = {name: brentq(lambda a, v=v: q(a * v) - threshold, 3, 30)
              for name, v in (("a", np.array([1.0, 0.0])), ("b", np.array([0.0, 1.0])))}
    rates = {"a": 1.01 * limits["a"], "b": 2.0}
    assert q([rates["a"], 0.0]) > threshold > q([rates["a"], rates["b"]])        # the joint likelihood allows it
    monkeypatch.setattr(mixtures, "rules", lambda: {"fixture": {"own": {"a": "a", "b": "b"}}})
    found = mixtures.bound("fixture", rates, 1.0, lambda c: 1 / limits[c])
    assert found.excluded is True and "approximation" in found.why()
    assert "Neither property is general" in mixtures.__doc__ and "an approximation" in mixtures.__doc__


# --- NA15-08 ---------------------------------------------------------------------------------------------------

def test_an_asset_is_parsed_from_the_bytes_checked(tmp_path) -> None:
    """The stored asset replaced by B after its check, while the parser runs, and put back (A → B → A): A's numbers are
    saved under A's digest (B's had been, the parser reading the stored file again)."""
    import adroit.library.experimental as module
    from adroit.library.experimental import ExperimentalCatalog
    first, second = b"mass,limit\n10,2\n", b"mass,limit\n10,9\n"
    source = tmp_path / "input.csv"
    source.write_bytes(first)
    catalog = ExperimentalCatalog(tmp_path / "catalog")
    original = module.ingest

    def parse(path, asset, *args, **kwargs):
        stored = catalog.path(f"assets/{asset.sha256}{asset.suffix}")
        stored.write_bytes(second)                  # replaced after its check, while the parser runs
        try:
            return original(path, asset, *args, **kwargs)
        finally:
            stored.write_bytes(first)               # and put back
    with patch.object(module, "ingest", parse):
        saved = catalog.import_files([source], "Replacement control")
    item = catalog.ingestion(catalog.load(saved.reference).ingestions[0])
    assert json.dumps(item.table.rows) in ('[["10", "2"]]', "[[10, 2]]")          # A's cells, never B's


def test_ingest_refuses_bytes_that_are_not_the_assets(tmp_path) -> None:
    from adroit.core.experimental_input import ExperimentalAsset
    from adroit.retrieval.experimental_ingestion import ingest
    import hashlib
    data = b"mass,limit\n10,2\n"
    path = tmp_path / "input.csv"
    path.write_bytes(b"mass,limit\n10,9\n")
    asset = ExperimentalAsset(name="input.csv", sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data),
                              suffix=".csv", role="data")
    with pytest.raises(ValueError, match="not the selected asset"):
        ingest(path, asset)


# --- NA15-09 ---------------------------------------------------------------------------------------------------

def test_an_alternative_with_no_events_on_a_target_separates_by_its_rate(monkeypatch) -> None:
    """One alternative's rate zero on argon, the other's not: r = 0, N = 4 events (∞ had been stored); both zero, or
    no rate on the signal's target: not separable there."""
    from adroit.inference import forecast
    shape = np.ones(len(forecast.ENERGIES_KEV))

    def spectrum(particle, interaction, target, halo, model):
        zero = interaction == "b" and target == "Ar"
        return (0.0 * shape if zero else shape, 0.0 if zero else 1.0)
    monkeypatch.setattr(forecast, "target_spectrum", spectrum)
    found = forecast.separate("a", ("p", "a"), "b", ("p", "b"), "Xe")
    assert found.by_target["Ar"] == (math.inf, 4.0) and found.best_target == "Ar" and found.events_needed == 4.0


# --- NA15-10 ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("alpha,beta", [(0.1, 1e-4), (0.1, 1e-6), (0.01, 1e-6), (-0.1, 1e-4), (-0.1, 1e-2),
                                        (0.01, 0.3), (1e-12, 0.5)])
def test_the_coulomb_factor_is_not_capped(alpha, beta) -> None:
    """S = X/(1 − e^{−X}): 3141.6 at α = 0.1, β = 10⁻⁴ (700 had been the cap), and its repulsive limit |X| e^{−|X|}."""
    from adroit.constraints import sommerfeld
    x = math.pi * alpha / beta
    exact = (x if x > 0 else 0.0) if abs(x) > 700 else (1.0 + x / 2 if abs(x) < 1e-8 else x / -math.expm1(-x))
    assert float(sommerfeld.coulomb(alpha, np.array([beta]))[0]) == pytest.approx(exact, rel=1e-12, abs=1e-300)


# --- NA15-11 ---------------------------------------------------------------------------------------------------

def test_a_background_deadline_counts_the_time_truly_elapsed() -> None:
    """A 2 s deadline, a poll that takes 10 s (a virtual clock): cancelled when it returns, at 11 s, no second poll,
    and the time said is 11 s (a second poll had followed, and "after 2 s" had been said)."""
    from adroit.agents.llm import OpenAIClient
    clock, calls = [0.0], []

    def create(**kw):
        calls.append(("create", clock[0]))
        return SimpleNamespace(id="fixture", status="queued")

    def retrieve(rid):
        calls.append(("retrieve", clock[0]))
        clock[0] += 10.0
        return SimpleNamespace(id=rid, status="in_progress")

    def cancel(rid):
        calls.append(("cancel", clock[0]))
        return SimpleNamespace(id=rid, status="cancelled")

    def sleep(seconds):
        clock[0] += seconds
    client = OpenAIClient(model="gpt-5.6-sol", background=True, poll_s=1, deadline_s=2,
                          client=SimpleNamespace(responses=SimpleNamespace(create=create, retrieve=retrieve,
                                                                           cancel=cancel)))
    with patch("adroit.agents.llm.time.sleep", sleep), patch("adroit.agents.llm.time.monotonic", lambda: clock[0]):
        with pytest.raises(TimeoutError, match="after 11 s"):
            client._respond(model="gpt-5.6-sol")
    assert calls == [("create", 0.0), ("retrieve", 1.0), ("cancel", 11.0)]
