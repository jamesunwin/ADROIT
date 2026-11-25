"""G9: a generic model's LHC pair production from MadGraph (``constraints.pair_production``)."""

import gzip
import json
from pathlib import Path

import pytest

from adroit.constraints import pair_production as pp
from adroit.evaluation import zoo
from adroit.model_building import ufo_export as ux


def _giacchino():
    e = next(x for x in zoo.entries() if x.id == "real_scalar_dm_vectorlike_lepton_giacchino")
    engine, p = zoo._generic(e, e.targets[0])
    return engine, p


def test_the_light_quarks_are_massless_for_production():
    engine, p = _giacchino()
    _, rules, _ = engine.at(p)
    prod = pp.production_rules(rules)
    masses = {x.name: x.mass for x in prod.particles}
    assert all(masses[q] == 0.0 for q in pp.LIGHT) and masses["b"] > 4 and masses["t"] > 170


def test_the_partner_decays_to_the_dark_matter_and_its_lepton_in_madgraphs_convention():
    """Ψ⁺ → S e⁺. The export flips the Dirac Ψ for MadGraph, so its PDG code is Ψ⁻'s: Ψ⁻ → S e⁻ (code 11)."""
    engine, p = _giacchino()
    _, rules, _ = engine.at(p)
    table = ux.names(rules)
    psi = next(x for x in rules.particles if x.parity == -1 and x.charge != 0)
    width, channels = pp.decay_table(rules, table, psi.name)
    dm = table[next(x.name for x in rules.particles if x.parity == -1 and x.charge == 0)][2]
    assert width > 0 and len(channels) == 1 and channels[0][0] == pytest.approx(1.0)
    assert sorted(channels[0][1]) == sorted([dm, -11 * pp.sign(psi, table)])     # Ψ⁺ → e⁺ (−11); Ψ⁻ → e⁻ (11)


def test_pairs_are_counted_from_the_events(tmp_path):
    lhe = tmp_path / "events.lhe.gz"
    rows = ["<event>", " 5 1 +1.0 1 1 1", " 2 -1 0 0 501 0 0 0 1 0 0 0 0 9", " -2 -1 0 0 0 501 0 0 1 0 0 0 0 9",
            " 9000101 1 1 2 0 0 0 0 1 0 0 0 0 9", " -9000101 1 1 2 0 0 0 0 1 0 0 0 0 9", " 21 1 1 2 0 0 0 0 1 0 0 0 0 9",
            "</event>"]
    with gzip.open(lhe, "wt") as stream:
        stream.write("\n".join(rows * 3) + "\n")
    assert pp.count_pairs(lhe, {9000101}) == {(-9000101, 9000101): 3}


def test_a_model_whose_only_odd_state_is_the_dark_matter_is_named():
    e = next(x for x in zoo.entries() if x.id == "singlet_fermion_scalar_mediator_das")
    engine, p = zoo._generic(e, e.targets[0])
    assert engine.lhc_spectrum(p)[2].startswith("only the dark matter is new and odd")


def test_a_partner_with_no_open_two_body_decay_decays_through_an_off_shell_w():
    """Yaguna's charged doublet state is 10 GeV above the dark matter: χ± → χ⁰ f f̄′ through W*, partonic."""
    e = next(x for x in zoo.entries() if x.id == "singlet_doublet_dirac_yaguna")
    engine, p = zoo._generic(e, e.targets[0])
    mb, rules, _ = engine.at(p)
    table = ux.names(rules)
    charged = next(x for x in rules.particles if x.parity == -1 and x.charge)
    assert not pp.decay_table(rules, table, charged.name)[1]
    width, channels = pp.soft_decay_table(rules, table, charged.name)
    assert width > 0 and {len(d) for _, d in channels} == {3}


@pytest.mark.slow
@pytest.mark.skipif(not pp.available(), reason="MadGraph is not in the tools folder")
def test_madgraph_produces_the_charged_partners_and_smodels_reads_them_as_a_lower_bound():
    from adroit.parameter_space import searches
    engine, p = _giacchino()
    text, sigma, why = engine.lhc_spectrum(p)
    assert not why and 0.05 < sigma < 0.3 and "MG5LO" in text            # Drell–Yan Ψ⁺Ψ⁻ at 174 GeV, LO
    outcome = searches.lhc_search(engine, p, unverified=False)
    assert outcome.excluded is not False and "leading order" in (outcome.why if outcome.excluded is None else "leading order")


def test_the_soft_widths_reproduce_the_librarys_wino_and_add_the_muon():
    from adroit.constraints import lhc
    widths = pp.soft_widths(0.1654, 2.0)
    assert widths["pi"] + widths["e"] == pytest.approx(lhc.chargino_width(0.1654, 2.0), rel=1e-6)   # 1.6e-7 apart
    assert 0 < widths["mu"] < 0.2 * widths["e"]                      # μν opens just above m_μ
    assert set(pp.soft_widths(3.0, 1.0)) == {"e", "mu", "tau", "ud", "cs"}   # partonic above 1.5 GeV


def test_a_pure_winos_charged_state_decays_to_the_neutral_one_and_a_pion():
    """With its one-loop splitting (``generic_lhc.with_loop_splittings``), χ± → χ⁰ π± at 97.7%."""
    from adroit.parameter_space.portals import generic_lhc
    e = next(x for x in zoo.entries() if x.id == "wino_majorana_triplet_bottaro")
    engine, p = zoo._generic(e, e.targets[0])
    mb, rules, _ = engine.at(p)
    split = generic_lhc.with_loop_splittings(mb, rules)
    charged = next(x for x in split.particles if x.parity == -1 and x.charge)
    neutral = next(x for x in split.particles if x.parity == -1 and not x.charge)
    assert charged.mass - neutral.mass == pytest.approx(0.1654, abs=5e-4)
    table = ux.names(split)
    width, channels = pp.soft_decay_table(split, table, charged.name)
    pion = next(br for br, d in channels if 211 in [abs(c) for c in d])
    assert pion == pytest.approx(0.977, abs=0.005) and width > 0


def test_a_mixing_singlet_is_dmsimps_spin0_mediator():
    """Das et al.'s scalar couples to the quarks as sin θ times the SM Yukawas: g_q = 0.13."""
    from adroit.parameter_space.portals import generic_lhc
    e = next(x for x in zoo.entries() if x.id == "singlet_fermion_scalar_mediator_das")
    engine, p = zoo._generic(e, e.targets[2])                      # BP8: sin θ = 0.13
    mb, rules, _ = engine.at(p)
    found = generic_lhc.dmsimp_scalar(mb, rules)
    assert found is not None and found["g_q"] == pytest.approx(0.13, rel=1e-3) and not found["pseudoscalar"]


@pytest.mark.parametrize("weight, axial, boson, delta, madgraph", [
    (2.0, 0.0, "W", 1.0, 5.8140e-13),                  # the wino's χ⁺ → χ⁰ e⁺ν_e (a vector current)
    (0.5, 0.0, "W", 1.0, 1.4540e-13),                  # the inert doublet's H⁺ → H⁰ e⁺ν_e (a scalar pair)
    (0.6436557283, 0.0, "Z", 1.0, 3.6500e-14),         # its A⁰ → H⁰ e⁺e⁻
    (0.6434934326, 0.0, "Z", 1.0, 3.6920e-14),         # Cohen et al.'s χ₂⁰ → χ₁⁰ e⁺e⁻ (vector)
    (0.0, 1.6229571258e-4, "Z", 5.0, 8.6470e-14),      # its singlet-like S⁰ → D⁰ e⁺e⁻ (purely axial)
])
def test_the_off_shell_widths_are_madgraphs_three_body_widths(weight, axial, boson, delta, madgraph):
    """MadGraph's exact three-body widths of G2's UFO at M = 1 TeV (``soft_widths``'s docstring), the e⁺ channel: the
    heavy-limit Γ ∝ (|V|² + 3|A|²)(|f_L|² + |f_R|²) within 1.5% (the axial case had been a third of it)."""
    width = pp.soft_widths(delta, weight, axial, boson)["e"]
    assert width == pytest.approx(madgraph, rel=0.015)


def test_an_axial_current_decays_three_times_faster_to_leptons_and_slower_to_a_pion():
    """Fermi (|V|²) against Gamow–Teller (3|A|²) parts; the pion's amplitude has |V|²q⁰² + |A|²|q|²."""
    from adroit.constraints import lhc
    vector, axial = pp.soft_widths(0.5, 1.0, 0.0), pp.soft_widths(0.5, 0.0, 1.0)
    assert axial["e"] == pytest.approx(3.0 * vector["e"], rel=1e-12)
    q2 = 0.5 ** 2 - lhc.M_PI ** 2
    assert axial["pi"] == pytest.approx(vector["pi"] * q2 / 0.5 ** 2, rel=1e-12)


def test_a_scalar_doublets_states_decay_through_off_shell_w_and_z():
    """The inert doublet split by 1 GeV: H⁺ → H⁰ W* and A⁰ → H⁰ Z* get decay tables (a charged scalar had none)."""
    import dataclasses
    e = next(x for x in zoo.entries() if x.id == "inert_doublet_kalinowski")
    engine, p = zoo._generic(e, e.targets[0])
    _, rules, _ = engine.at(p)
    masses = {"phi_D0_1": 100.0, "phi_D0_2": 101.0, "phi_D+": 101.0}
    rules = dataclasses.replace(rules, particles=[dataclasses.replace(x, mass=masses.get(x.name, x.mass))
                                                  for x in rules.particles])
    table = ux.names(rules)
    for name, boson_codes in (("phi_D+", {-11, 12}), ("phi_D0_2", {11, -11})):
        width, channels = pp.soft_decay_table(rules, table, name)
        assert width > 0 and sum(br for br, _ in channels) == pytest.approx(1.0)
        assert any(boson_codes <= set(d) for _, d in channels)


def _two_partners():
    """The external audit's R17-1 control (2026-10-17): a Majorana singlet χ (300 GeV) with a colour-triplet scalar Φ
    (900 GeV) and a charged scalar E (500 GeV), y = 1 in Φ* χ̄ u_R + E* χ̄ e_R + h.c. Synthetic, not a zoo entry."""
    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space.portals.generic import GenericModel
    spec = ModelSpec.model_validate({"name": "synthetic_two_partners", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1, "mass_gev": 300.0},
        {"name": "Phi", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 900.0,
         "charges": {"su3": "3", "hypercharge": 2 / 3}},
        {"name": "E", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 500.0, "charges": {"hypercharge": -1.0}},
        {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R", "charges": {"su3": "3", "hypercharge": 2 / 3}},
        {"name": "eR", "role": "standard_model", "spin": 0.5, "chirality": "R", "charges": {"hypercharge": -1.0}}],
        "couplings": [{"name": "y", "value": 1.0}],
        "terms": [{"fields": [{"field": f, "conjugate": True}, {"field": "chi", "conjugate": True}, {"field": sm}],
                   "lorentz": "chiral", "coupling": "y", "plus_hc": True} for f, sm in [("Phi", "uR"), ("E", "eR")]]})
    engine = GenericModel.of(spec)
    mb, rules, _ = engine.at(engine.point())
    prod = pp.production_rules(rules)
    dm = mb.spectrum.dark_matter().name
    odd = [p.name for p in prod.particles if p.parity == -1]
    return prod, ux.names(prod), dm, odd


def test_every_tree_level_order_is_generated():
    """R17-1: with no orders MadGraph kept only the lowest-weighted diagrams (QCD² for Φ); the limits admit every
    2 → 2 tree diagram: the Yukawa exchange (QED²) and its interference with QCD."""
    prod, _, _, _ = _two_partners()
    assert pp.tree_orders(prod) == {"QCD": 2, "QED": 2}
    assert pp.generate_command(prod) == "generate p p > vis odd QCD<=2 QED<=2"


def test_both_sectors_and_associated_production_are_expected():
    prod, _, dm, odd = _two_partners()
    found = {frozenset(x) for x in pp.expected_pairs(prod, [n for n in odd if n != dm], odd)}
    phi = next(n for n in odd if n.startswith("Phi"))
    e = next(n for n in odd if n.startswith("E"))
    assert found == {frozenset([phi]), frozenset([e]), frozenset([phi, dm])}


def _process(tmp_path, lines):
    folder = tmp_path / "SubProcesses" / "P1_x"
    folder.mkdir(parents=True)
    (folder / "matrix1.f").write_text("".join(f"C     Process: {line}\n" for line in lines))
    return tmp_path


def test_a_process_at_minimal_order_or_missing_a_sector_fails(tmp_path):
    """MadGraph's subprocesses are checked: the old minimal-order process (only Φ Φ*, at WEIGHTED<=2) fails, so does
    one at the explicit orders without the E pair; the complete one passes."""
    prod, table, dm, odd = _two_partners()
    vis = [n for n in odd if n != dm]
    mg = {n: table[n] for n in odd}
    phi, e = (next(table[n][:2] for n in odd if n.startswith(k)) for k in ("Phi", "E"))
    command = pp.generate_command(prod)
    old = _process(tmp_path / "old", [f"u u~ > {phi[0]} {phi[1]} WEIGHTED<=2 @1"])
    with pytest.raises(RuntimeError, match="explicit orders"):
        pp.check_generated(old, prod, table, vis, odd, command)
    partial = _process(tmp_path / "partial", [f"u u~ > {phi[0]} {phi[1]} QCD<=2 QED<=2 @1",
                                              f"u u > {phi[0]} {phi[0]} QCD<=2 QED<=2 @1",
                                              f"u g > {phi[0]} {mg[dm][0]} QCD<=2 QED<=2 @1"])
    with pytest.raises(RuntimeError, match="did not generate"):
        pp.check_generated(partial, prod, table, vis, odd, command)
    full = _process(tmp_path / "full", [f"u u~ > {phi[0]} {phi[1]} QCD<=2 QED<=2 @1",
                                        f"u g > {phi[0]} {mg[dm][0]} QCD<=2 QED<=2 @1",
                                        f"u u~ > {e[0]} {e[1]} QCD<=2 QED<=2 @1"])
    pp.check_generated(full, prod, table, vis, odd, command)


def test_both_caches_carry_the_generation_command(tmp_path, monkeypatch):
    """A process or σ generated by an earlier command is never reused: the request in both cache keys carries it."""
    prod, _, dm, _ = _two_partners()
    seen = []

    class Stop(Exception):
        pass

    def key(ufo, request, structure=False):
        seen.append(request)
        raise Stop
    monkeypatch.setattr(pp, "folder", lambda: tmp_path)
    monkeypatch.setattr(ux, "write", lambda *a, **k: tmp_path)
    monkeypatch.setattr(pp, "_key", key)
    with pytest.raises(Stop):
        pp.cross_sections(prod, dm, "synthetic_two_partners")
    assert seen[0]["generate"] == pp.generate_command(prod) and seen[0]["generation"] == pp.GENERATION


def test_both_caches_carry_the_generation_command_and_only_the_result_its_epoch(tmp_path, monkeypatch):
    """S18-01: results cached before the work area was locked may hold another point's σ, so the result key carries
    the cache epoch and they are recomputed; the generated process (no point data) is still reused."""
    prod, _, dm, _ = _two_partners()
    seen = []

    class Stop(Exception):
        pass

    def key(ufo, request, structure=False):
        seen.append((structure, request))
        if len(seen) == 2:
            raise Stop
        return "k"
    monkeypatch.setattr(pp, "folder", lambda: tmp_path)
    monkeypatch.setattr(ux, "write", lambda *a, **k: tmp_path)
    monkeypatch.setattr(pp, "_key", key)
    with pytest.raises(Stop):
        pp.cross_sections(prod, dm, "synthetic_two_partners")
    (_, result), (structure, process) = seen
    assert result["cache"] == pp.CACHE and structure and "cache" not in process


@pytest.mark.needs("madgraph")
def test_concurrent_points_of_one_model_give_serial_results(tmp_path, monkeypatch):
    """S18-01 (the stacked audit of 2026-10-18): two jobs computing different masses of one model shared its work
    area, so one could read the other's launch script and cache that σ under its own key. The engine here is a
    stand-in that answers with the mass it reads from the script it is given (the audit's control, adapted): with
    the area locked, each point gets its own mass, and the cached rereads agree."""
    import dataclasses
    import re
    import threading
    prod, table, dm, odd = _two_partners()
    dm_code, phi_code = table[dm][2], table[next(n for n in odd if n.startswith("Phi"))][2]
    heavier = dataclasses.replace(prod, particles=[dataclasses.replace(p, mass=400.0) if p.name == dm else p
                                                   for p in prod.particles])
    b_started, b_in_engine = threading.Event(), threading.Event()
    monkeypatch.setattr(pp, "folder", lambda: tmp_path)

    def engine(script, path, cwd):
        path.write_text(script)
        if script.startswith("import model"):
            proc = Path(re.search(r"^output (.+) -f$", script, re.M).group(1))
            (proc / "bin").mkdir(parents=True)
            (proc / "bin" / "generate_events").write_text("stand-in")
            (proc / "Cards").mkdir()
            (proc / "Cards" / "me5_configuration.txt").write_text("run_mode = 2\nnb_core = 2\n")
            sub = proc / "SubProcesses" / "P1_synthetic"
            sub.mkdir(parents=True)
            rows = []
            for pair in pp.expected_pairs(prod, [n for n in odd if n != dm], odd):
                names = sorted(pair)
                names = names * 2 if len(names) == 1 else names
                rows.append("C Process: u u~ > " + " ".join(table[n][0] for n in names) + " QCD<=2 QED<=2 @1")
            (sub / "matrix1.f").write_text("\n".join(rows))
            return "generated"
        if threading.current_thread().name == "A":
            assert b_started.wait(10)
            b_in_engine.wait(1.0)                 # unlocked, B would now overwrite the script A is about to read
        else:
            b_in_engine.set()
        text = path.read_text()
        mass = float(re.search(rf"^set MASS {dm_code} (.+)$", text, re.M).group(1))
        run = Path(re.search(r"^launch (.+)$", text, re.M).group(1)) / "Events" / f"run_{threading.current_thread().name}"
        run.mkdir(parents=True, exist_ok=True)
        with gzip.open(run / "unweighted_events.lhe.gz", "wt") as f:
            f.write(f"<event>\n 2 1 +1.0 1 1 1\n {dm_code} 1 1 2 0 0 0 0 1 0 0 0 0 9\n "
                    f"{phi_code} 1 1 2 0 0 0 0 1 0 0 0 0 9\n</event>\n")
        return f"Cross-section : {mass} +- 0.0 pb"
    monkeypatch.setattr(pp, "_run", engine)
    out = {}

    def job(name, rules):
        if name == "B":
            b_started.set()
        out[name] = pp.cross_sections(rules, dm, "one-synthetic-model")["total_pb"]
    a = threading.Thread(target=job, args=("A", prod), name="A")
    b = threading.Thread(target=job, args=("B", heavier), name="B")
    a.start()
    b.start()
    a.join(30)
    b.join(30)
    assert out == {"A": 300.0, "B": 400.0}
    assert pp.cross_sections(prod, dm, "one-synthetic-model")["total_pb"] == 300.0
    assert pp.cross_sections(heavier, dm, "one-synthetic-model")["total_pb"] == 400.0
    assert sorted(json.loads(f.read_text())["total_pb"] for f in tmp_path.rglob("xsec-*.json")) == [300.0, 400.0]


@pytest.mark.slow
@pytest.mark.skipif(not pp.available(), reason="MadGraph is not in the tools folder")
def test_madgraph_generates_both_sectors_and_associated_production(tmp_path):
    """The audit's control with the actual MadGraph (diagrams only): 13 subprocesses, the E pair and Φχ among them;
    the old command's 5 were Φ's alone."""
    prod, table, dm, odd = _two_partners()
    names = [table[n] for n in odd]
    mg_odd = sorted({x for n in names for x in n[:2]})
    mg_vis = sorted({x for n in odd if n != dm for x in table[n][:2]})
    ufo = ux.write(prod, tmp_path, "ufo_control")
    command = pp.generate_command(prod)
    procdir = tmp_path / "proc"
    pp._run("\n".join([f"import model {ufo}", f"define p = {pp.PROTON}", f"define odd = {' '.join(mg_odd)}",
                       f"define vis = {' '.join(mg_vis)}", command, f"output {procdir} -f"]) + "\n",
            tmp_path / "generate.mg5", tmp_path)
    made, lines = pp.generated_pairs(procdir, prod, table)
    assert len(lines) == 13 and len(made) == 3
    pp.check_generated(procdir, prod, table, [n for n in odd if n != dm], odd, command)


@pytest.mark.slow
@pytest.mark.skipif(not pp.available(), reason="MadGraph is not in the tools folder")
def test_madgraph_reproduces_the_tree_engine_and_assigns_the_colour_flow(tmp_path):
    """The UFO's colour convention in MadGraph: g g → Φ Φ* at √ŝ = 3 TeV equals the tree engine's (by detailed balance
    from Φ Φ* → g g; it fixes the relative sign of the triple-gluon diagram), and g u → Φ χ, which R17-1's complete
    production generates, runs: with ADROIT's field representations in the indices MadGraph could not assign its
    colour flow ("failed to reduce to color indices")."""
    import math
    from adroit.constraints import tree
    from adroit.parameter_space.portals.generic import tree_model
    prod, table, dm, odd = _two_partners()
    phi = next(n for n in odd if n.startswith("Phi"))
    roots, mass = 3000.0, next(p.mass for p in prod.particles if p.name == phi)
    beta = math.sqrt(1 - 4 * mass ** 2 / roots ** 2)
    expected = tree.Process(tree_model(prod), phi, phi + "~", "g", "g").sigma(roots ** 2) * 9 / 256 * beta ** 2 * 2
    ufo = ux.write(prod, tmp_path, "ufo_colour")
    run = {**pp.RUN, "lpp1": 0, "lpp2": 0, "ebeam1": roots / 2, "ebeam2": roots / 2, "nevents": 2000}
    sigma = {}
    for label, process in (("gg", f"g g > {table[phi][0]} {table[phi][1]}"), ("gu", f"g u > {table[phi][0]} {table[dm][0]}")):
        procdir = tmp_path / label
        pp._run("\n".join([f"import model {ufo}", f"generate {process} QCD<=2 QED<=2", f"output {procdir} -f"]) + "\n",
                tmp_path / f"{label}.mg5", tmp_path)
        pp._single_core(procdir)
        log = pp._run("\n".join([f"launch {procdir}", *[f"set {k} {v}" for k, v in run.items()],
                                 *pp._point_settings(prod, table), "done"]) + "\n", tmp_path / f"{label}-launch.mg5", tmp_path)
        assert "failed to reduce to color indices" not in log
        sigma[label] = float(pp.XSEC.findall(log)[-1][0])
    assert sigma["gg"] == pytest.approx(expected * 0.3894e9, rel=0.02) and sigma["gu"] > 0
