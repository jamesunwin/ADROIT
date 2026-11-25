"""Calibrate G4's Sommerfeld bracket (``constraints.long_range_bracket``) against ADROIT's full engines.

For each model: the perturbative thermal mass, the bracket's low / central / high thermal masses (central both by
state counting, which is what the generic engine will know, and by the hard rate's channel shares where an engine
knows them), and ADROIT's Sommerfeld-only and full (with bound states) thermal masses, all for Ωh² = 0.11933. The
choices of the bracket (the Hulthén phase frozen at π/2, α at the Bohr momentum of the most attractive channel, no
Debye masses, U(1)_Y's mediator massless, SU(2)'s at m_W, SU(3)'s massless) were fixed before this was run.

Run:  python docs/g4/bracket_calibration.py      (two processes; writes docs/g4/bracket_calibration.json)
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

TARGET = 0.11933
X_NODES = np.geomspace(1.0, 2e4, 140)
OUT = Path(__file__).with_name("bracket_calibration.json")
PUBLISHED = {
    "wino": {"full": "2.86 ± 0.01 (Bottaro et al.)", "sommerfeld": "2.88 (Beneke et al.)", "tree": "2.22 (Beneke et al.)"},
    "higgsino": {"full": "1.08 ± 0.02 (Bottaro et al.)", "sommerfeld": "≈ 1.1 (Cirelli et al.)", "tree": ""},
    "quintuplet": {"full": "13.6 ± 0.8 (Bottaro et al.)", "sommerfeld": "9.3 (Mitridate et al.)",
                   "tree": "4.4 (Cirelli et al.)"},
    "quintuplet_dirac": {"full": "9.9 ± 0.7 (Bottaro et al.)", "sommerfeld": "", "tree": ""},
    "coloured_triplet": {"full": "3.3 (Harz & Petraki, band 3.16–3.31)",
                         "sommerfeld": "1.7 (De Simone et al.); 1.865 (Harz & Petraki)",
                         "tree": "1.3 (De Simone et al.); 1.33 (Harz & Petraki)"},
}


def _root(f, guess: float) -> float | None:
    from adroit.constraints.long_range_bracket import _nearest_root
    return _nearest_root(lambda m: f(m) - TARGET, guess, 2e-3)


def _shares(rates: dict[tuple[int, int], float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for (i, _), r in rates.items():
        out[f"{i}/1"] = out.get(f"{i}/1", 0.0) + r
    return out


# --- the electroweak multiplets ----------------------------------------------------------------------------------

def multiplet_case(kind: str, guess: float) -> dict:
    """The wino or the higgsino through ``portals.multiplet``."""
    from adroit.constraints import long_range_bracket as lb
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.portals import multiplet as mp
    from adroit.parameter_space.portals import nplet
    delta = mp.SPLITTING[kind]
    n, y = (3, 0.0) if kind == "wino" else (2, 0.5)
    strongest = nplet.lam(n, 1)

    def inputs(m: float, hard: bool = False):
        a2 = lb.bohr_alpha(mp.alpha_2, strongest, 0.5 * m)
        ay = lb.bohr_alpha(mp.alpha_y, strongest, 0.5 * m)
        forces = [lb.GaugeForce(group="SU2", alpha=a2, mediator_gev=mp.M_W)]
        pair = lb.PairRep(su2=(n, n))
        if y:
            forces.append(lb.GaugeForce(group="U1", name="Y", alpha=ay))
            pair = lb.PairRep(su2=(n, n), charges={"Y": (y, -y)})
        rate = mp.effective_rate(kind, m, delta, m / X_NODES, sommerfeld_on=False)
        shares = _shares(nplet.hard_rates(n, y, m)) if hard else {}
        return mp._species(kind, m, delta), X_NODES, [lb.PairRate(pair=pair, rate=rate.tolist(), shares=shares)], forces

    out = _bracket_masses(inputs, guess)
    for name, bound in (("sommerfeld", False), ("full", True)):
        engine = mp.ElectroweakMultiplet(name=kind, multiplet=kind, bound_states=bound)
        out[name] = _root(lambda m: engine.omega_h2(Point(m_chi=m, m_med=1.0, g_q=0.0)), out["perturbative"] * 1.3)
    return out


def _bracket_masses(inputs, guess: float) -> dict:
    """The bracket's thermal masses as first fixed; with the hard rate's channel shares; and with the selection rule
    (channels I ≤ 5 only, ``final_su2_max``; added after the first 5-plet results, no free constant)."""
    from adroit.constraints import long_range_bracket as lb
    masses = lb.thermal_masses(inputs, TARGET, guess)
    hard = lb.thermal_masses(lambda m: inputs(m, hard=True), TARGET, guess)

    def ruled(m: float):
        species, x, pairs, forces = inputs(m)
        return species, x, [p.model_copy(update={"final_su2_max": 5}) for p in pairs], forces
    rule = lb.thermal_masses(ruled, TARGET, guess)
    sample = lb.bracket(*inputs(masses["perturbative"]))
    return {**masses, "central_hard": hard["central"], "rule_low": rule["low"], "rule_central": rule["central"],
            "rule_high": rule["high"], "alpha_max": sample.alpha_max, "alpha_min": sample.alpha_min}


# --- the n-plets ---------------------------------------------------------------------------------------------------

def nplet_case(n: int, y: float, guess: float) -> dict:
    """A 5-plet through ``portals.nplet``."""
    from adroit.constraints import long_range_bracket as lb
    from adroit.constraints import relic
    from adroit.parameter_space.portals import multiplet as mp
    from adroit.parameter_space.portals import nplet

    def inputs(m: float, hard: bool = False):
        a2 = lb.bohr_alpha(mp.alpha_2, nplet.lam(n, 1), 0.5 * m)
        ay = lb.bohr_alpha(mp.alpha_y, nplet.lam(n, 1), 0.5 * m)
        forces = [lb.GaugeForce(group="SU2", alpha=a2, mediator_gev=mp.M_W)]
        pair = lb.PairRep(su2=(n, n))
        if y:
            forces.append(lb.GaugeForce(group="U1", name="Y", alpha=ay))
            pair = lb.PairRep(su2=(n, n), charges={"Y": (y, -y)})
        count = n if y == 0 else 2 * n
        species = [relic.Species(m, 2.0)] * count
        rate = nplet.effective_rate(n, y, m, m / X_NODES, sommerfeld_on=False)
        shares = _shares(nplet.hard_rates(n, y, m)) if hard else {}
        return species, X_NODES, [lb.PairRate(pair=pair, rate=rate.tolist(), shares=shares)], forces

    out = _bracket_masses(inputs, guess)
    out["sommerfeld"] = nplet.thermal_mass(n, y, TARGET, bound_states=False)
    out["full"] = nplet.thermal_mass(n, y, TARGET)
    return out


# --- the coloured partner ------------------------------------------------------------------------------------------

REPS = {(0, 0): (("1", "1")), (0, 1): ("1", "3"), (0, 2): ("1", "3bar"), (1, 2): ("3", "3bar"), (1, 1): ("3", "3"),
        (2, 2): ("3bar", "3bar")}


def coloured_case(guess: float) -> dict:
    """A Majorana χ with a degenerate colour-triplet scalar partner (``portals.tchannel``, u_R, y = 0.1)."""
    from adroit.constraints import long_range_bracket as lb
    from adroit.constraints import processes, relic, sommerfeld
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.portals.tchannel import TChannel

    def point(m: float) -> Point:
        return Point(m_chi=m, m_med=1.0001 * m, g_chi=0.1)

    def inputs(m: float, hard: bool = False):
        cls = TChannel(name="c", partner="uR", majorana=True, sommerfeld=False, bound_states=False)
        p = point(m)
        species, pairs = cls.coannihilation(p)
        forces = [lb.GaugeForce(group="SU3", alpha=sommerfeld.alpha_bohr(m))]
        out = []
        for key, sigma in pairs.items():
            rate = relic.coannihilation_average(species, {key: sigma}, X_NODES, cls.resonances(p))
            shares = {}
            if hard and key == (1, 2):
                s = (2 * p.m_med) ** 2 * (1 + 1e-4)
                one, eight = processes.partners_to_gauge_bosons_by_colour(s, p.m_med, cls._gauge(p), coloured=True)
                shares = {"1/1": float(one), "1/8": float(eight)}
            if hard and key in ((1, 1), (2, 2)):
                s = (2 * p.m_med) ** 2 * (1 + 1e-4)
                six, three = processes.partners_to_same_fermions_by_colour(s, p.m_med, 0.00216, m, 0.1, True)
                shares = {"1/6": float(six), "1/3bar" if key == (1, 1) else "1/3": float(three)}
                if key == (2, 2):
                    shares = {"1/6bar": float(six), "1/3": float(three)}
            out.append(lb.PairRate(pair=lb.PairRep(su3=REPS[key]), rate=rate.tolist(), shares=shares))
        return species, X_NODES, out, forces

    out = _bracket_masses(inputs, guess)
    for name, bound in (("sommerfeld", False), ("full", True)):
        engine = TChannel(name="c", partner="uR", majorana=True, sommerfeld=True, bound_states=bound)
        out[name] = _root(lambda m: engine.omega_h2(point(m)), out["perturbative"] * (1.4 if not bound else 2.4))
    return out


CASES = {"wino": (multiplet_case, ("wino", 2300.0)), "higgsino": (multiplet_case, ("higgsino", 1000.0)),
         "quintuplet": (nplet_case, (5, 0.0, 4500.0)), "quintuplet_dirac": (nplet_case, (5, 1.0, 4000.0)),
         "coloured_triplet": (coloured_case, (1300.0,))}


def run(name: str) -> tuple[str, dict, float]:
    """One case: (name, its thermal masses in GeV, seconds)."""
    start = time.time()
    fn, args = CASES[name]
    return name, fn(*args), time.time() - start


def table(results: dict) -> str:
    """The calibration as a Markdown table (TeV)."""
    def tev(v):
        return "—" if v is None else f"{v / 1e3:.2f}"
    rows = ["| model | α_max / α_min | perturbative | bracket: high-Ω · central · low-Ω | with I ≤ 5 | central (hard "
            "shares) | ADROIT Sommerfeld only | ADROIT full | published (full; Sommerfeld only; tree) |",
            "|---|---|---|---|---|---|---|---|---|"]
    for name, r in results.items():
        pub = PUBLISHED[name]
        rows.append(f"| {name} | {r['alpha_max']:.4f} / {r['alpha_min']:.4f} | {tev(r['perturbative'])} | "
                    f"{tev(r['high'])} · {tev(r['central'])} · {tev(r['low'])} | "
                    f"{tev(r.get('rule_high'))} · {tev(r.get('rule_central'))} · {tev(r.get('rule_low'))} | "
                    f"{tev(r['central_hard'])} | {tev(r['sommerfeld'])} | {tev(r['full'])} | "
                    f"{pub['full']}; {pub['sommerfeld']}; {pub['tree']} |")
    return "\n".join(rows)


if __name__ == "__main__":
    names = sys.argv[1:] or list(CASES)
    results = json.loads(OUT.read_text()) if OUT.exists() else {}
    with ProcessPoolExecutor(max_workers=2) as pool:
        for name, masses, seconds in pool.map(run, names):
            results[name] = masses
            print(f"{name}: {seconds:.0f} s {masses}", flush=True)
            OUT.write_text(json.dumps(results, indent=1))
    print(table({k: results[k] for k in CASES if k in results}))
