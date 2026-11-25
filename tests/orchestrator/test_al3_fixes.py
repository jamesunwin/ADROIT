"""The audit loop's third cycle, its findings repaired (AL3-01..24, 2026-11-15; the AL3 repair record of 2026-11-15).

- AL3-01: a long-range group whose hard rate is a pole's peak at threshold is refused; the bracket decides.
- AL3-02: the generic engine's tables resolve a pole of any width to 10⁻¹² of its mass, and one at the opening;
  narrower, Ωh² is refused; the UFO portal's pole nodes reach out from the pole, about √2 apart.
- AL3-03: the single idea's fits move the couplings the model ties to g_χ.
- AL3-04: the UFO portal's table has nodes at each final state's opening.
- AL3-05: the inert doublet's UFO takes running b and c masses at m_h.
- AL3-06: the one-event closed form only where outcomes of two or more events are small against it.
- AL3-07: the combined direct-detection ratio carries its own channel's construction.
- AL3-08: a module's declared method is kept where its inputs cannot be walked.
- AL3-09: a generic model's CMB rate is G8's during recombination where long-range effects act today.
- AL3-10: the workbench answers only its own pages on this machine.
- AL3-11: an empty or unreadable propagation file leaves the antiprotons undecided.
- AL3-12: a heavy scalar that no search reaches gives no outcome.
- AL3-13: the dilepton search and the inert doublet's pairs are undecided where their σ is not tabulated.
- AL3-14: one rule for several outcomes of a name, everywhere.
- AL3-15: the 2HDM+a's entry names its gluon channel.
- AL3-16: a test needing the tools says so; the release checks run the fast suite without them.
- AL3-17: the children's guard fences reverse lookups and sendmsg, and keeps an outer guard; the tests' fence covers
  getnameinfo.
- AL3-18: a single idea's "no thermal" resting on an unverified relic target says so in its headline.
- AL3-19: the healer warns on a folder it cannot search, and looks again at a file passed over as young.
- AL3-20: tests that could not fail, made to fail on the behaviour.
- AL3-21: the relic grid resolves a pole to Γ/4m = 10⁻¹⁴ and refuses Ωh² below 10⁻¹⁶.
- AL3-22: the export counts the machine's paths it carries.
- AL3-23: the compatibility line says what it is of, with the best fit's own status.
- AL3-24: the replay restores the exact-limits setting.

Stand-ins where a calculation would need the network or the tools; no network, no key, no provider call.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from adroit.constraints import propagation, relic
from adroit.core.model_spec import ModelSpec
from adroit.inference import look_elsewhere
from adroit.orchestrator import signal
from adroit.parameter_space import library, limit_tables, limits, resonances, scan, searches
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals import generic as gm

ROOT = Path(__file__).resolve().parents[2]


def _with_couplings(entry, values: dict[str, float]):
    """The generic engine built from a library entry's own spec, its couplings set."""
    spec = entry.spec()
    spec = spec.model_copy(update={"couplings": [c.model_copy(update={"value": values[c.name]})
                                                 if c.name in values else c for c in spec.couplings]})
    return gm.GenericModel.for_spec(spec)


# --- AL3-01 ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("m_chi,g_q,still_falling", [(100.0, 0.006, True), (1000.0, 0.03, False)])
def test_a_pole_at_threshold_takes_no_long_range_correction(m_chi, g_q, still_falling, monkeypatch) -> None:
    """B − L with its Z′ at twice the dark matter's mass: α_eff ≤ 10⁻⁵, so the long-range terms change nothing, and
    the generic engine agrees with the library's class (it had given 0.0072 for 0.1198, flat in the coupling).

    The solves are compared with the late tests off (AL6-01's window and AL7-02's remainder); at 100 GeV the yield is
    still falling at x = 10⁴ (by a further 18%), so both routes refuse the published Ωh²; at 1 TeV its fall to x → ∞ is
    bounded at 9.5%, and it is published."""
    entry = library.entry("b_minus_l")
    p = entry.point.model_copy(update=dict(m_chi=m_chi, m_med=2 * m_chi, g_chi=g_q / 3, g_q=g_q))
    engine = _with_couplings(entry, {"g_chi": p.g_chi, "g_BL": p.g_q})
    q = Point(m_chi=m_chi, m_med=2 * m_chi)
    with monkeypatch.context() as late_off:
        late_off.setattr(relic, "LATE_TOLERANCE", math.inf)
        late_off.setattr(relic, "REMAINDER_TOLERANCE", math.inf)
        with_terms = engine.omega_h2(q)
        assert with_terms == pytest.approx(engine.model_copy(update={"sommerfeld": False}).omega_h2(q), rel=1e-6)
        assert with_terms == pytest.approx(entry.model_class.omega_h2(p), rel=0.01)
    if still_falling:
        for route in (lambda: engine.omega_h2(q), lambda: entry.model_class.omega_h2(p)):
            with pytest.raises(relic.RelicUnresolved, match="annihilation has not stopped"):
                route()
    else:
        assert engine.omega_h2(q) == pytest.approx(with_terms, rel=1e-12)


# --- AL3-02 ----------------------------------------------------------------------------------------------------

def _tabled_over_exact(m: float, mass: float, ratio: float) -> float:
    """⟨σv⟩ of a Breit–Wigner tabulated on the generic engine's own nodes (which hold σβ) and read by its own
    interpolation (which gives σ), against the Breit–Wigner itself on a reference grid (x = 20)."""
    x, threshold = np.array([20.0]), 2 * m
    width = ratio * mass

    def bw(s):
        return mass * width / ((s - mass * mass) ** 2 + (mass * width) ** 2)

    def sigma(s):                                         # σ whose σβ is the Breit–Wigner
        beta = np.sqrt(np.clip((s - threshold ** 2) * s, 0, None)) / s
        return np.where(beta > 0, bw(s) / np.where(beta > 0, beta, 1.0), 0.0)
    nodes = gm._nodes(threshold, threshold, [(mass, width)])
    read = gm._interpolated(nodes, bw((threshold * (1 + nodes)) ** 2), threshold, m, m)
    u = relic.energy_grid(m, mass, width)
    tabled = relic.thermal_average(u, read((threshold * (1 + u)) ** 2), x)[0]
    u_r, w = mass / threshold - 1, width / (4 * m)
    ladder = w * np.geomspace(1e-4, 1e7, 40000)
    fine = np.union1d(np.geomspace(1e-13, 80, 400000), np.concatenate([u_r - ladder, u_r + ladder]))
    fine = np.concatenate([[0.0], fine[(fine > 0) & (fine < 80)]])
    return float(tabled / relic.thermal_average(fine, sigma((threshold * (1 + fine)) ** 2), x)[0])


@pytest.mark.parametrize("ratio", [1e-8, 1e-10, 1e-12])
def test_the_generic_tables_resolve_a_narrow_pole(ratio) -> None:
    """Γ/M = 10⁻⁸ had come out 4.1 times its average, 10⁻⁹ 25.6 times."""
    assert _tabled_over_exact(45.0, 100.0, ratio) == pytest.approx(1.0, abs=0.01)


@pytest.mark.parametrize("u_r", [0.0, 1e-6, -1e-6])
@pytest.mark.parametrize("ratio", [1e-5, 1e-6])
def test_the_generic_tables_resolve_a_pole_at_the_opening(u_r, ratio) -> None:
    """At threshold Γ/M = 10⁻⁶ had come out 0.50 of its average, and 0.67 just below it."""
    assert _tabled_over_exact(1000.0, 2000.0 * (1 + u_r), ratio) == pytest.approx(1.0, abs=0.01)


@pytest.mark.needs("pdg_r_ratio")      # the library's Z′ width below the hadronic opening reads it
def test_lmu_ltau_below_its_benchmarks_couplings_agrees_with_the_library() -> None:
    """At 0.3 times the benchmark's couplings (Γ/M = 7 × 10⁻⁹) the generic Ωh² had been 0.46 of the library's."""
    entry = library.entry("lmu_minus_ltau")
    p = entry.point.model_copy(update=dict(m_chi=0.5, m_med=1.5, g_chi=0.3 * entry.point.g_chi,
                                           g_q=0.3 * entry.point.g_q))
    engine = _with_couplings(entry, {"g_chi": p.g_chi, "g_mt": p.g_q})
    assert engine.omega_h2(Point(m_chi=0.5, m_med=1.5)) == pytest.approx(entry.model_class.omega_h2(p), rel=0.02)


def test_a_pole_narrower_than_the_tables_resolve_refuses_omega() -> None:
    entry = library.entry("lmu_minus_ltau")
    engine = _with_couplings(entry, {"g_chi": 1e-3 * entry.point.g_chi, "g_mt": 1e-3 * entry.point.g_q})
    assert "narrower than the generic engine's cross-section tables resolve" in engine.domain(
        Point(m_chi=0.5, m_med=1.5))


@pytest.mark.parametrize("ratio", [3.3e-5, 1e-7, 1e-9])
def test_the_ufo_tables_resolve_a_narrow_pole(ratio) -> None:
    """The UFO portal's rule (ln σ linear in √s, the class's own nodes ``ufo.pole_offsets``) about the Higgs: 1.4–2.9%
    too strong at its own width had been, 2.9 times at 10⁻⁷; now within half a per cent."""
    from adroit.parameter_space.portals import ufo
    x, m, mass = np.array([20.0]), 55.0, 125.25
    start, width = 2 * m, ratio * mass

    def sigma(root):
        s = root * root
        return mass * width / ((s - mass * mass) ** 2 + (mass * width) ** 2) / np.sqrt(
            np.clip(1 - start * start / s, 1e-300, None))
    roots = start * (1.0 + np.concatenate([[1e-9], np.geomspace(1e-5, 25.0, ufo.TABLE_NODES)]))
    near = mass + width * ufo.pole_offsets(width, ufo.POLE_TABLE_REACH * (mass - start))
    roots = np.union1d(roots, near[(near > roots[0]) & (near < roots[-1])])
    logs = np.log(np.maximum(sigma(roots), 1e-300))
    u = relic.energy_grid(m, mass, width)[1:]
    tabled = relic.thermal_average(u, np.exp(np.interp(start * (1 + u), roots, logs)), x)[0]
    u_r, w = mass / start - 1, width / (4 * m)
    ladder = w * np.geomspace(1e-4, 1e7, 40000)
    fine = np.union1d(np.geomspace(1e-9, 80, 200000), np.concatenate([u_r - ladder, u_r + ladder]))
    fine = fine[(fine > 1e-9) & (fine < 80)]
    assert tabled / relic.thermal_average(fine, sigma(start * (1 + fine)), x)[0] == pytest.approx(1.0, abs=0.006)


# --- AL3-21 ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("width", [1e-10, 1e-12, 1e-13])
def test_the_relic_grid_resolves_a_pole_to_its_floor(width) -> None:
    """Γ = 10⁻¹² GeV at M = 100, m = 45 (Γ/4m ≈ 6 × 10⁻¹⁵): the grid's floor of 10⁻⁹ in u had missed it."""
    m, mass, x = 45.0, 100.0, np.array([20.0])
    u_r, half = mass / (2 * m) - 1, 1e-7
    u_hat = np.array([u_r - 2 * half, u_r - half, u_r, u_r + half, u_r + 2 * half])
    hat = np.array([0.0, 1.0, 1.0, 1.0, 0.0]) / (8 * m * m * (1 + u_r) * 3 * half)
    limit = math.pi * relic.thermal_average(u_hat, hat, x)[0]
    u = relic.energy_grid(m, mass, width)
    s = (2 * m * (1 + u)) ** 2
    found = relic.thermal_average(u, mass * width / ((s - mass * mass) ** 2 + (mass * width) ** 2), x)[0]
    assert found == pytest.approx(limit, rel=0.01)


def test_omega_is_refused_for_a_pole_narrower_than_the_grid_resolves() -> None:
    with pytest.raises(relic.RelicUnresolved):
        relic.resolvable(45.0, [(100.0, 1e-15)])
    relic.resolvable(45.0, [(100.0, 1e-12)])                                  # resolved: nothing raised


# --- AL3-03 ----------------------------------------------------------------------------------------------------

def _one_coupling_spec() -> ModelSpec:
    import yaml
    data = yaml.safe_load((ROOT / "docs/dm13/vector_mediator.yaml").read_text())
    data["couplings"] = [{"name": "g", "value": 1.0}]
    data["terms"][0]["coupling"], data["terms"][1]["coupling"] = "g", "g"
    return ModelSpec.model_validate(data)


def test_a_one_coupling_models_inversion_moves_both_couplings() -> None:
    """One symbol g for the dark matter's and the quarks' currents: the fitted amplitude μ is g², so g = √μ for both
    (g_χ alone had been fitted, g_q left at 1)."""
    from adroit.orchestrator import single_idea
    from adroit.parameter_space.classify import classify
    from adroit.parameter_space.fit_inversion import invert
    spec = _one_coupling_spec()
    cls, point, _ = classify(spec)
    with single_idea._ties_of(spec) as ties:
        assert ties and single_idea._TIES.get() == ties
        found = invert(cls, point.model_copy(update={"m_chi": 10.0}), 0.25, single_idea._TIES.get())
    assert found.g_chi == pytest.approx(0.5, rel=1e-6) and found.g_q == pytest.approx(found.g_chi, rel=1e-12)
    assert single_idea._TIES.get() == ()


# --- AL3-04, AL3-05 --------------------------------------------------------------------------------------------

def test_the_inert_doublet_takes_the_higgs_modules_quark_masses_at_the_higgs_mass() -> None:
    """The Higgs's pole goes as Γ(h → H₀H₀) Γ(h → visible)/Γ_h², with Γ_h the measured 4.1 MeV: its b b̄ and c c̄
    widths are the Higgs module's (the running mass at m_h times the square root of its higher-order factor), not
    those of the file's pole-like 4.23 and 1.2 GeV."""
    from adroit.constraints import higgs
    parameters = library.INERT_DOUBLET.parameters
    for quark in ("b", "c"):
        expected = higgs.running_mass(quark, 125.09) * math.sqrt(higgs.anchor(quark, 125.09))
        assert float(parameters[f"MM{quark.upper()}"]) == pytest.approx(expected, rel=1e-5)
    assert 3.0 < float(parameters["MMB"]) < 3.2 and 0.6 < float(parameters["MMC"]) < 0.8


@pytest.mark.needs("ufo_models")
def test_the_inert_doublets_own_higgs_widths_fit_its_propagator() -> None:
    """The model's own two-body widths of h (b, c, τ, μ) had been 5.0 MeV, over the 4.1 of its propagator: now the
    Standard Model's for those channels (``constraints.higgs``, 2.76 MeV) within 6%."""
    from adroit.constraints import higgs, ufo_model
    cls = library.INERT_DOUBLET
    model = cls.model(Point(m_chi=60.0, m_med=120.0, g_chi=0.001, g_q=10.0))
    h = next(x for x in model.particles.values() if x.pdg == 25)
    standard = higgs.partial_widths(125.09)
    two_body = sum(standard[k] for k in ("b", "c", "tau", "mu"))
    assert ufo_model.widths(model, [h.name])[h.name] == pytest.approx(two_body, rel=0.06)
    assert h.width == pytest.approx(sum(standard.values()), rel=0.01)


@pytest.mark.needs("ufo_models")
def test_the_inert_doublet_annihilates_through_the_higgss_loops() -> None:
    """h* → g g, γ γ and Z γ, which the UFO route reads no vertex for, from the generic route's factorisation: at
    M_H₀ = 60 GeV g g against b b̄ as the Standard Model's Γ(h* → g g)/Γ(h* → b b̄) at √s ≈ 120 GeV (about 0.13);
    without them the funnel had been 7–17% above micrOMEGAs's Ωh² once its b b̄ width was right."""
    from adroit.constraints import higgs
    from adroit.parameter_space.portals import ufo
    cls = library.INERT_DOUBLET
    p = Point(m_chi=60.0, m_med=120.0, g_chi=0.002, g_q=10.0)
    today = cls.sigma_v_today(p, 1e-3)
    widths = higgs.partial_widths(120.0)
    assert {"g", "gamma", "Zgamma"} <= set(today)
    assert today["g"] / today["b"] == pytest.approx(widths["g"] / widths["b"], rel=0.1)
    model = cls.model(p)
    dm = model.particles[cls.dm]
    assert ufo.higgs_loops(model, dm.name, dm.conjugate) is not None
    other = library.TWO_HDM_A.model(Point(m_chi=150.0, m_med=400.0, g_chi=1.0, g_q=0.35, g_l=1.0))
    chi = other.particles[library.TWO_HDM_A.dm]
    assert ufo.higgs_loops(other, chi.name, chi.conjugate) is None                  # its χ does not reach h


@pytest.mark.needs("ufo_models")
def test_the_ufo_table_has_nodes_at_a_final_states_opening() -> None:
    """The 2HDM+a at m_χ = 158 GeV: the tt̄ channel opens inside the table's cell (at 344 GeV); 2 GeV above it the
    table had been 0.026 of the processes' own σ."""
    from adroit.constraints import tree
    from adroit.parameter_space.portals import ufo
    cls = library.TWO_HDM_A
    p = Point(m_chi=158.0, m_med=400.0, g_chi=1.0, g_q=0.35, g_l=1.0)
    model = cls.model(p)
    dm = model.particles[cls.dm]
    top = next(x for x in model.particles.values() if x.pdg == 6)
    root = 2 * top.mass + 2.0
    table = cls._sigma(p, dm.name, dm.conjugate)(np.array([root * root]))[0]
    direct = 0.0
    for c, d in cls._finals(model, dm.name, dm.conjugate, root):
        try:
            direct += ufo.off_shell_sigma(tree.Process(model, dm.name, dm.conjugate, c, d, points=16), root * root)
        except ValueError:
            continue
    assert table == pytest.approx(direct, rel=0.05)


# --- AL3-06 ----------------------------------------------------------------------------------------------------

def _gaussian_window(where: float, expected: float):
    energies = np.linspace(0.0, 100.0, 2001)
    shape = np.exp(-0.5 * ((energies - 50.0) / 5.0) ** 2)
    shapes = np.array([shape / np.trapezoid(shape, energies)])
    background = np.full(energies.size, expected / 100.0)
    module = SimpleNamespace(resolution_on_grid=lambda: np.zeros(energies.size), background_on_grid=lambda: background,
                             background_rate=lambda: None, observations=lambda: (np.array([where]), 0.0))
    return module, shapes, energies, background


def test_the_closed_form_is_left_aside_where_two_events_matter() -> None:
    """One event at the best place a single event can be, on 0.03 expected events: the closed form had reported 5.7σ
    where the toys give 3.3σ (it counts single events only)."""
    module, shapes, energies, background = _gaussian_window(50.0, 0.03)
    z_max = float(look_elsewhere.max_significance(shapes, energies, np.array([50.0]), background))
    p_toys, p_closed, z, method = signal._toy_significance(module, shapes, energies, z_max, 20_000)
    assert p_closed is None and "left aside" in method and z < 4.5
    assert look_elsewhere.several_events(0.03) == pytest.approx(1 - math.exp(-0.03) * 1.03, rel=1e-9)


def test_the_closed_form_stands_where_one_event_is_all_that_matters() -> None:
    module, shapes, energies, background = _gaussian_window(55.0, 0.0015)
    z_max = float(look_elsewhere.max_significance(shapes, energies, np.array([55.0]), background))
    p_toys, p_closed, z, method = signal._toy_significance(module, shapes, energies, z_max, 20_000)
    assert p_closed is not None and method.startswith("one-event closed form")
    assert look_elsewhere.several_events(0.0015) <= signal.CLOSED_FORM_SHARE * p_closed


# --- AL3-07 ----------------------------------------------------------------------------------------------------

def test_the_combined_ratio_carries_its_own_channels_construction(monkeypatch) -> None:
    """SI at 0.9 from a one-sided module, SD (0.3, 2.0) from a two-sided one: the combination takes 0.9, and its
    construction is the SI module's (the decisive channel's two-sided one had been stored beside it)."""
    from adroit.parameter_space import dd_channels
    one = limits.StatisticalLimit(value=1e-46, confidence_level=.95, source="CDMSlite Run 2", sidedness="one-sided",
                                  construction="x")
    two = limits.StatisticalLimit(value=1e-40, confidence_level=.95, source="XENONnT SR0+SR1", sidedness="two-sided",
                                  construction="x")
    made = dd_channels.Outcome(channels=[
        dd_channels.ChannelOutcome(kind="SI", sigma_cm2=0.9e-46, ratio=0.9, limit=one),
        dd_channels.ChannelOutcome(kind="SD-neutron", sigma_cm2=2e-40, ratio=2.0, ratio_band=(0.3, 2.0), limit=two)],
        excluded=None, pending=["band"])
    monkeypatch.setattr(scan.dd_channels, "compare", lambda *a, **k: made)
    entry = library.entry("dmwg_A1")
    found = scan.direct_detection(entry.model_class, entry.point)
    assert found.ratio == 0.9 and found.statistic.source == "CDMSlite Run 2"
    assert found.statistic.sidedness == "one-sided" and made.combined_channel.kind == "SI"


# --- AL3-08 ----------------------------------------------------------------------------------------------------

def test_the_declared_method_is_kept_where_the_inputs_cannot_be_walked(monkeypatch) -> None:
    from adroit.experiments import registry
    method = "maximum gap (Yellin; the optimum interval code is not available here)"
    monkeypatch.setattr(registry, "load_module", lambda name: SimpleNamespace(
        info=SimpleNamespace(statistical_method=method)))

    def unreadable(module):
        raise OSError("an unreadable folder")
    monkeypatch.setattr(limit_tables, "_external", unreadable)
    version, declared = limit_tables._inputs_now("CRESST-III 2019")
    assert version.startswith("unreadable") and declared == method
    assert limits.fallback("CRESST-III 2019") == limits.MAXIMUM_GAP_FALLBACK


# --- AL3-09 ----------------------------------------------------------------------------------------------------

def test_a_long_range_models_cmb_rate_is_the_saturated_one() -> None:
    """A Dirac χ of 100 GeV and a vector of 0.1 GeV (α = 0.01): Sommerfeld-enhanced 78 times its tree rate once
    saturated; the extrapolation from 10⁻² and 5 × 10⁻³ had given 14.7."""
    from adroit.constraints import searches as cs
    spec = ModelSpec.model_validate({"name": "dqed", "phase": "broken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0},
        {"name": "Ad", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": 0.1}],
        "terms": [{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Ad"}],
                   "lorentz": "vector", "coupling": f"{math.sqrt(4 * math.pi * 0.01)}"}]})
    engine = gm.GenericModel.for_spec(spec)
    p = engine.point()
    saturated = sum(engine.sigma_v_today(p, 1e-5).values())
    assert sum(cs.s_wave(engine, p).values()) == pytest.approx(saturated, rel=0.03)
    tree = sum(engine.model_copy(update={"sommerfeld": False}).sigma_v_today(p, 1e-4).values())
    assert saturated / tree > 50.0


def test_a_model_without_long_range_effects_keeps_the_extrapolated_s_wave() -> None:
    entry = library.entry("dmwg_V1")
    engine = _with_couplings(entry, {"g_DM": 1.0, "g_q": 1.0})
    assert engine.cmb_sigma_v(Point(m_chi=45.0, m_med=100.0)) is None


# --- AL3-10 ----------------------------------------------------------------------------------------------------

def _asgi(scope: dict) -> tuple[list[dict], bool]:
    """What ``LocalOnly`` sends for a request, and whether it passed the request on."""
    from adroit.ui.local_only import LocalOnly
    reached, sent = [], []

    async def app(scope, receive, send):
        reached.append(scope)

    async def receive():
        return {"type": "websocket.connect"}

    async def send(message):
        sent.append(message)
    asyncio.run(LocalOnly(app)(scope, receive, send))
    return sent, bool(reached)


def _scope(kind: str, host: str, origin: str | None = None, port: int = 8765) -> dict:
    headers = [(b"host", host.encode())] + ([(b"origin", origin.encode())] if origin is not None else [])
    return {"type": kind, "headers": headers, "server": ("127.0.0.1", port), "path": "/"}


@pytest.mark.parametrize("host", ["127.0.0.1:8765", "localhost:8765", "[::1]:8765"])
def test_the_workbench_serves_its_own_pages(host) -> None:
    assert _asgi(_scope("http", host)) == ([], True)
    assert _asgi(_scope("http", host, f"http://{host}")) == ([], True)
    assert _asgi(_scope("websocket", host, f"http://{host}")) == ([], True)
    assert _asgi({"type": "lifespan"}) == ([], True)


@pytest.mark.parametrize("kind,host,origin", [
    ("http", "attacker.example:8765", None),                       # DNS rebinding: a foreign name for this machine
    ("http", "127.0.0.1:9999", None),                               # another port's name
    ("http", "127.0.0.1:8765", "http://attacker.example"),          # another site's page beside it
    ("http", "127.0.0.1:8765", "null"),
    ("websocket", "127.0.0.1:8765", "http://attacker.example"),     # the socket.io handshake from another site
    ("websocket", "attacker.example:8765", "http://attacker.example:8765")])
def test_the_workbench_refuses_another_sites_request(kind, host, origin) -> None:
    sent, reached = _asgi(_scope(kind, host, origin))
    assert not reached
    assert (sent[0]["type"], sent[0].get("status", sent[0].get("code"))) == (
        ("http.response.start", 403) if kind == "http" else ("websocket.close", 1008))


def test_the_workbench_installs_its_guard_when_it_serves(monkeypatch) -> None:
    from adroit.ui import app as workbench
    from adroit.ui.local_only import LocalOnly
    added = []
    monkeypatch.setattr(workbench, "build_pages", lambda runs_dir: None)
    monkeypatch.setattr(workbench.app, "add_middleware", lambda cls, **k: added.append(cls))
    monkeypatch.setattr(workbench.ui, "run", lambda **k: None)
    workbench.serve(None, 8765, show=False)
    assert added == [LocalOnly]


# --- AL3-11 ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["", "not: [a mapping", "just a string\n"])
def test_an_empty_or_unreadable_propagation_file_leaves_the_bound_undecided(tmp_path, monkeypatch, text) -> None:
    record = propagation.CHARGED[0]
    (tmp_path / f"{record}.yaml").write_text(text)
    monkeypatch.setattr(propagation, "DATA", tmp_path)
    propagation.load.cache_clear()
    try:
        assert "empty or unreadable" in propagation.unavailable(record)
        with pytest.raises(propagation.Unavailable):
            propagation.factor(record, "conservative", 100.0)
    finally:
        propagation.load.cache_clear()


# --- AL3-12 ----------------------------------------------------------------------------------------------------

def test_a_heavy_scalar_below_both_searches_gives_no_outcome() -> None:
    from adroit.parameter_space.searches import HIGGS_PDG
    cls = library.entry("singlet_scalar_mixing").model_class if "singlet_scalar_mixing" in library.BY_ID else next(
        e.model_class for e in library.BY_ID.values() if searches.family(e.model_class) == "singlet_mixing")
    widths = {HIGGS_PDG["Z"]: 1e-3, HIGGS_PDG["W"]: 2e-3}
    p = Point(m_chi=50.0, m_med=150.0, g_chi=0.1, g_q=0.1)
    assert searches._heavy_scalar(cls, p, 1.0, widths, True) is None
    assert searches._heavy_scalar(cls, p, 1.0, widths, True, "h₂") is None


# --- AL3-13 ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("why", ["1000 GeV is outside MadGraph's q q̄ → Z′ tables", ""])
def test_the_dilepton_search_without_a_tabulated_sigma_is_undecided(why) -> None:
    found = searches._atlas_dilepton(1000.0, 1.0, None, 0.1, True, why)
    assert found is not None and found.excluded is None and found.why


def test_an_inert_pair_below_the_tables_makes_the_spectrum_undecided(monkeypatch) -> None:
    """M_H₀ = 10, M_A₀ = 80 GeV: H₀A₀'s mean mass, 45 GeV, is below the tables' 50; its block had been left out."""
    from adroit.constraints import production
    state = lambda m: SimpleNamespace(mass=m, width=1e-3)                        # noqa: E731
    cls = SimpleNamespace(dm="~H0", model=lambda p: SimpleNamespace(particles={"~H0": state(10.0), "~A0": state(80.0),
                                                                               "~H+": state(120.0)}))
    monkeypatch.setattr(production, "unavailable", lambda *names: "")
    monkeypatch.setattr(production, "mass_range", lambda name: (50.0, 1000.0))
    monkeypatch.setattr(production, "sigma_pb", lambda name, m: None if m < 50.0 or m > 1000.0 else 1.0)
    assert searches._inert_pair(cls, Point(m_chi=10.0, m_med=120.0)) == ("", None)


# --- AL3-14 ----------------------------------------------------------------------------------------------------

def test_one_rule_takes_several_outcomes_of_a_name() -> None:
    name = resonances.DIJET
    low, high = (searches.Outcome(name=name, excluded=False, ratio=r) for r in (0.1, 0.9))
    one, two = (searches.Outcome(name=name, excluded=None, why=w) for w in ("reason one", "reason two"))
    excluding = searches.Outcome(name=name, excluded=True, ratio=3.0, confidence_level=0.9)
    assert resonances._strongest([low, high]).ratio == 0.9 == scan._by_name([low, high])[0].ratio
    assert resonances._strongest([one, two]).why == "reason one; reason two" == scan._by_name([one, two])[0].why
    assert searches.strongest([low, None, excluding]).excluded is True and searches.strongest([None]) is None
    allowed = searches.Outcome(name=name, excluded=False, ratio=0.2, confidence_level=0.95)
    assert scan._ratio_level(name, {}, [allowed, excluding]) == 0.9


def test_an_observation_reads_the_outcome_its_verdict_used() -> None:
    import inspect
    from adroit.evidence import observations
    source = inspect.getsource(observations._comparison)
    assert "strongest(" in source and "next((o for o in row.search_results" not in source


# --- AL3-15 ----------------------------------------------------------------------------------------------------

def test_the_2hdma_entry_names_its_gluon_channel() -> None:
    entry = library.entry("two_hdm_a")
    assert any("gg" in item and "a*" in item for item in entry.not_computed)
    assert library.TWO_HDM_A.not_computed == []                       # stated, never a pending reason at every point


# --- AL3-16 ----------------------------------------------------------------------------------------------------

def test_the_dijet_test_says_it_needs_the_production_tables() -> None:
    from tests.orchestrator import test_al2_fixes
    marks = getattr(test_al2_fixes.test_the_cms_dijet_limit_without_its_table_is_undecided, "pytestmark", [])
    assert any(m.name == "needs" and "production_tables" in m.args for m in marks)


def test_the_release_checks_run_the_fast_suite_with_an_empty_tools_folder(tmp_path) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location("release_checks_al3", ROOT / "scripts/release_checks.py")
    checks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checks)
    step = next(s for s in checks.steps(tmp_path) if s.name == "fast_without_tools")
    assert step.empty_tools and step.command[-3:] == ["-q", "-p", "no:cacheprovider"]
    probe = checks.Step(name="fast_without_tools", empty_tools=True, command=[sys.executable, "-c", (
        "import os; d = os.environ['ADROIT_TOOLS_DIR']; print(os.path.isdir(d), os.listdir(d), '3 passed in 0.1s')")])
    result = checks.run_step(probe, tmp_path)
    assert result.verdict == "pass" and "True []" in (tmp_path / "fast_without_tools.log").read_text()


# --- AL3-17 ----------------------------------------------------------------------------------------------------

def test_the_fence_refuses_a_reverse_lookup_by_getnameinfo(_no_network) -> None:
    """Called only once seen to be the fence's (on a tree without it the test fails sending nothing)."""
    assert "_Fence.install" in getattr(socket.getnameinfo, "__qualname__", "")
    with pytest.raises(OSError, match="fenced"):
        socket.getnameinfo(("192.0.2.1", 80), 0)                                   # TEST-NET-1
    assert socket.getnameinfo(("127.0.0.1", 80), socket.NI_NUMERICHOST | socket.NI_NUMERICSERV) == ("127.0.0.1", "80")
    assert len(_no_network) == 1
    _no_network.clear()


def test_a_child_is_fenced_against_reverse_lookups_and_sendmsg_and_keeps_an_outer_guard(tmp_path) -> None:
    """A child's guard (``scripts/netguard``) replaces gethostbyaddr, getnameinfo and sendmsg, and runs the
    ``sitecustomize`` it hides (an outer guard of the caller's). Nothing is called: the child names the functions."""
    from tests.conftest import CHILD_GUARD
    outer = tmp_path / "outer"
    outer.mkdir()
    (outer / "sitecustomize.py").write_text("import os\nopen(os.environ['OUTER_MARK'], 'w').write('ran')\n")
    code = ("import socket\nprint(socket.gethostbyaddr.__module__, socket.getnameinfo.__module__, "
            "socket.socket.sendmsg.__module__)\n")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(CHILD_GUARD), str(outer), os.environ.get("PYTHONPATH", "")]),
           "OUTER_MARK": str(tmp_path / "mark")}
    found = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60,
                           check=True)
    assert found.stdout.split() == ["sitecustomize"] * 3
    assert (tmp_path / "mark").read_text() == "ran"


# --- AL3-18 ----------------------------------------------------------------------------------------------------

def test_a_no_thermal_resting_on_an_unverified_target_says_so() -> None:
    from adroit.orchestrator.study_headline import headline
    summary = ("no thermal intersection fitting the anomaly was resolved over the searched masses; this conclusion "
               "depends on unverified records: planck-2018-omega")
    found = headline({"band": [], "thermal": [], "eos_thermal": {}, "level": "no_thermal", "summary": summary},
                     "single_idea")
    assert "UNVERIFIED RECORDS" in found.words
    plain = headline({"band": [], "thermal": [], "eos_thermal": {}, "level": "no_thermal", "summary": "none"},
                     "single_idea")
    assert "UNVERIFIED" not in plain.words


# --- AL3-19 ----------------------------------------------------------------------------------------------------

@pytest.mark.skipif(os.geteuid() == 0, reason="a folder of mode 0 can be searched by root")
def test_the_healer_warns_on_a_folder_it_cannot_search(tmp_path, caplog) -> None:
    from adroit.experiments import response_cache
    tools = tmp_path / "tools"
    (tools / "nuclear-responses").mkdir(parents=True)
    tools.chmod(0)
    try:
        assert response_cache.heal(tools) == ()
    finally:
        tools.chmod(0o755)
    assert any("could not be searched" in r.getMessage() for r in caplog.records)
    assert tools not in response_cache._HEALED                    # looked at again at the next load


def test_a_young_cut_short_file_is_set_aside_at_a_later_load(tmp_path) -> None:
    from adroit.experiments import response_cache
    folder = tmp_path / "nuclear-responses"
    folder.mkdir()
    young = folder / "haxton_Xe131_GCN5082.json"
    young.write_text('{"F|0|0": [1.0, 0.9')
    assert response_cache.heal(tmp_path) == ()
    old = time.time() - 2 * response_cache.SETTLED_S
    os.utime(young, (old, old))
    assert len(response_cache.heal(tmp_path)) == 1 and not young.exists()
    assert response_cache.heal(tmp_path) == response_cache._HEALED[tmp_path]          # then done with


# --- AL3-20 ----------------------------------------------------------------------------------------------------

def test_the_relic_targets_rule_waits_where_its_record_is_unusable(monkeypatch) -> None:
    from adroit.parameter_space import certification, likelihood
    monkeypatch.setattr(likelihood, "DENSITY_USABLE", False)
    waits, rests = certification.relic_target(False)
    assert "awaits" in waits and rests == []
    assert certification.relic_target(True) == ("", ["planck-2018-omega"])
    monkeypatch.setattr(likelihood, "DENSITY_USABLE", True)
    assert certification.relic_target(False) == ("", [])


def test_a_zero_sigma_report_names_no_toys_when_rendered() -> None:
    from adroit.inference.dm_tournament import NULL, Entry, TournamentResult
    tournament = TournamentResult(ranking=[Entry(label=NULL, z_signal=0.0, z_joint=0.0, chi2_pg=0.0, p_pg=1.0,
                                                 aic=0.0)], indistinguishable=[], classes_in_top_set=[],
                                  signal_fit_leader=NULL, null_rank=1)
    zero = signal.SignalResult(request=signal.SignalRequest(experiment="CDMS II Si (2013)"), fits=[], classes={},
                               n_classes=0, max_local_z=0.0, global_p_toys=1.0, global_p_closed_form=None,
                               global_z=0.0, global_method="rule that a largest local significance of 0σ is reached by "
                               "every outcome", combinations=[], tournament=tournament, separations=[])
    first = next(line for line in signal.report(zero).splitlines() if "global significance" in line)
    assert "p = 1.00e+00" in first and "toys:" not in first
    drawn = zero.model_copy(update={"max_local_z": 2.0, "global_p_toys": 0.01, "global_toys": 1000,
                                    "global_method": "1,000 background-only toys"})
    assert "toys: 1.00e-02" in next(line for line in signal.report(drawn).splitlines() if "global significance" in line)


def test_the_classic_workbench_starts_a_run_from_its_own_page(tmp_path, monkeypatch) -> None:
    """AL2-12's other side: a POST from the workbench's own page (its Origin) starts the run."""
    import threading
    import urllib.error
    import urllib.request
    from http.server import ThreadingHTTPServer
    from adroit.workbench import server
    from adroit.workbench.jobs import Board
    started = []
    monkeypatch.setattr(server, "submit", lambda board, kind, fields: started.append((kind, fields))
                        or SimpleNamespace(id="job-1"))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler_for(Board(tmp_path / "runs")))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    class Keep(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        own = f"127.0.0.1:{httpd.server_port}"
        request = urllib.request.Request(f"http://{own}/run/exclusion", data=b"card=L01&isospin=s&values=&masses=",
                                         headers={"Host": own, "Origin": f"http://{own}"})
        try:
            status = urllib.request.build_opener(Keep).open(request, timeout=10).status
        except urllib.error.HTTPError as error:
            status = error.code
    finally:
        httpd.shutdown()
    assert status == 303 and started and started[0][0] == "exclusion" and started[0][1]["card"] == ["L01"]


def test_the_fence_reads_its_childrens_journal_from_an_offset(tmp_path) -> None:
    """On a journal of its own (the session's is the running test's)."""
    from tests.conftest import FENCE
    journal = tmp_path / "children.jsonl"
    journal.write_text('{"kind": "resolution", "target": "a.example"}\n')
    offset = journal.stat().st_size
    with journal.open("a") as stream:
        stream.write('{"kind": "datagram", "target": "192.0.2.1"}\n\n')
    own = SimpleNamespace(journal=journal)
    assert type(FENCE).children_since(own, offset) == ['a child process: {"kind": "datagram", "target": "192.0.2.1"}']
    assert len(type(FENCE).children_since(own, 0)) == 2


def test_the_session_fails_for_an_attempt_outside_any_test(monkeypatch) -> None:
    import pytest as pt
    from tests import conftest
    monkeypatch.setattr(conftest.FENCE, "early", ["example.invalid (thread MainThread)"])
    session = SimpleNamespace(exitstatus=pt.ExitCode.OK)
    conftest.pytest_sessionfinish(session, 0)
    assert session.exitstatus == pt.ExitCode.TESTS_FAILED
    monkeypatch.setattr(conftest.FENCE, "early", [])
    calm = SimpleNamespace(exitstatus=pt.ExitCode.OK)
    conftest.pytest_sessionfinish(calm, 0)
    assert calm.exitstatus == pt.ExitCode.OK


# --- AL3-22 ----------------------------------------------------------------------------------------------------

def test_the_export_counts_the_machines_paths_it_carries(tmp_path) -> None:
    from adroit.evidence import archive
    home = str(Path.home())
    inside = str(tmp_path / "inputs" / "lz.yaml")
    files = {"studies/n0/evidence.json": json.dumps({
        "command": f"adroit track1 --out {home}/runs/x --data {inside}",
        "inputs": [{"location": inside}, {"location": f"{home}/agentic-dm-tools/smodels"}],
        "page": "/files/plot.png"}).encode(), "studies/n0/report.md": f"{home}/elsewhere".encode()}
    note = archive.local_paths(files)
    assert note.startswith("this bundle carries 3 absolute paths") and f"under its home directory ({home})" in note
    assert archive.local_paths({"a.json": b'{"page": "/files/plot.png", "n": 1}'}) == ""


# --- AL3-23 ----------------------------------------------------------------------------------------------------

def test_the_compatibility_line_names_what_it_is_of(monkeypatch) -> None:
    from adroit.orchestrator import single_idea
    band = [SimpleNamespace(m_chi=7.5, status="excluded", physical_fit=None, inversion_reason=""),
            SimpleNamespace(m_chi=30.0, status="pending", physical_fit=None, inversion_reason="")]
    result = SimpleNamespace(best="L01s@7.5", band=band, global_z=2.0, global_method="toys",
                             physical_significance_note="note", physical_best_mass_gev=7.5,
                             constraint_compatibility="pending", thermal_viability="", level="viable_pending",
                             thermal_pending=[])
    monkeypatch.setattr(single_idea, "_band_table", lambda rows: [])
    line = next(x for x in single_idea._fit_section(result) if "Constraint compatibility" in x)
    assert "of the band's eligible fitted masses" in line and "of the best resolved physical fit (7.5 GeV): excluded" in line


# --- AL3-24 ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("exact,likelihood,expected", [(True, None, True), (False, object(), True),
                                                       (False, None, False)])
def test_the_replay_restores_the_exact_limits_setting(monkeypatch, exact, likelihood, expected) -> None:
    from adroit.evidence import replay
    saved = SimpleNamespace(request=SimpleNamespace(exact_limits=exact, likelihood=likelihood))
    assert replay._recorded_exact(saved) is expected
    seen = []
    monkeypatch.setattr(replay, "_calculate", lambda *a: seen.append(os.environ.get(limits.EXACT_VARIABLE)) or ({}, {}))
    monkeypatch.setattr(replay, "_request", lambda *a: {})
    monkeypatch.setattr(replay, "_recorded_halo", lambda saved: None)
    node = SimpleNamespace(workflow="track1", id="n0", result_path="r.json", evidence_path="e.json")
    manifest = SimpleNamespace(nodes=[node])
    monkeypatch.setattr(replay, "held_bundle", lambda path: b"")
    monkeypatch.setattr(replay, "read_bundle", lambda data: (manifest, {"r.json": b"{}", "e.json": b"{}"}))
    monkeypatch.setattr(replay, "result_type", lambda workflow: SimpleNamespace(model_validate_json=lambda b: saved))
    captured = SimpleNamespace(context=SimpleNamespace(origin="captured"))
    monkeypatch.setattr(replay.EvidenceEnvelope, "model_validate_json", classmethod(lambda cls, b: captured))
    replay.replay_bundle(Path("bundle.zip"), node_id="n0", index=0)
    assert seen == (["1"] if expected else [None])
