"""Pair production of a generic model's new states at the LHC: MadGraph at leading order from G2's UFO export (G9).

Where no production table applies (``portals.generic_lhc``), the model's own UFO (``model_building.ufo_export``, at the
point) is run through MadGraph 3.8 at 13 TeV:

    generate p p > vis odd QCD<=2 QED<=2

``odd`` is every Z₂-odd state and ``vis`` every odd state but the dark matter, so a pair of dark matter alone, which
leaves nothing to see, is not generated. The proton is the four-flavour one (g, u, d, s, c and their antiquarks, made
massless for production), and the PDF is NNPDF2.3 LO with the scale H_T/2. The run is offline (``maddm.offline``) and on
one core. Each pair's σ is the total times its share of the unweighted events (10,000, so a pair with 1% of them is
known to 10%).

**Every tree-level diagram** (``tree_orders``, the external audit of 2026-10-17, R17-1). With no coupling orders,
MadGraph keeps only the diagrams of the lowest weighted order (QCD counted once, QED twice) across the whole
multiprocess: a coloured partner's t-channel exchange of the dark matter (a dark Yukawa, order QED) and its
interference with QCD were dropped, and in a model with a coloured and an electroweak partner the electroweak pairs
were not generated at all. The orders are set explicitly, at the largest any 2 → 2 tree diagram of the exported model
can reach (twice a three-point vertex's, or a contact vertex's own: QCD ≤ 2, QED ≤ 2), so every diagram and its
interference, with its sign, is in σ. After generation every pair of states that a tree diagram from the proton's
partons can make (``expected_pairs``) must be among MadGraph's subprocesses (``generated_pairs``); otherwise the run
fails and nothing is decided. Both caches carry the generation command and ``GENERATION``, so a process or a σ from
an earlier command is never reused.

**Leading order is a lower bound.** At the LHC the NLO corrections to pair production raise σ (K ≈ 1.1–1.5 for
electroweak states, more for coloured ones; K = 1.35–1.37 against the tables, ``docs/g9_colliders.md``), so an
exclusion stands and "allowed" is not shown (``searches.lhc_search``). This rests on the complete tree-level σ: the
library's QCD-only partner tables are not a lower bound (decision D33).

**Decays** (``decay_table``): every two-body channel of each new state, from G2's vertices (``feynman.two_body_width``),
into Standard Model particles or other new states. A new state other than the dark matter with no open two-body
channel would be stable in SModelS's eyes (a long-lived charged or coloured particle that the HSCP and R-hadron
searches exclude) when it in fact decays through an off-shell boson. Where it is joined to a lighter new state by a W
or a Z with a splitting Δ ≪ m_W, its decay through W* or Z* is computed (``soft_decay_table``); otherwise such a
spectrum is not tested, and the reason is given.

**Decays through an off-shell boson** (``soft_widths``). For a heavy pair (M ≫ Δ), the transition current
χ̄₂γ^μ(V + Aγ⁵)χ₁ keeps only its time component's vector part and its space components' axial part (as the Fermi and
Gamow–Teller parts of a β decay), so to a pair f f̄′ of couplings f_L, f_R to the boson B:

    Γ = N_c (|V|² + 3|A|²)(|f_L|² + |f_R|²) Δ⁵ F / (120 π³ m_B⁴),

with F the muon-decay phase space of the massive daughter (x = m/Δ; for a Z*'s pair of equal masses, x = 2m/Δ, an
approximation). A scalar pair's current c (p₁ + p₂)^μ is a vector one, V = c. Through W*: π (below 1.5 GeV, with
|V|²Δ² + |A|²|q|² for the pion's momentum q), eν, μν, τν, and quarks (above 1.5 GeV); through Z*: three νν̄, e⁺e⁻,
μ⁺μ⁻, τ⁺τ⁻ and quarks above 1.5 GeV. A Z*'s hadrons below 1.5 GeV (π⁰ through the axial current, ππ through the
vector) and a radiative χ₂ → χ₁γ are not computed, so such a width is a lower bound. Checked against MadGraph's exact
three-body widths of G2's UFO at Δ = 1–5 GeV: the wino's χ⁺ → χ⁰eν (0.994), the inert doublet's H⁺ → H⁰eν (0.994) and
A⁰ → H⁰e⁺e⁻ (0.987), Cohen et al.'s vector χ₂⁰ → χ₁⁰e⁺e⁻ (0.999) and its pure-axial one (0.989 at Δ = 5 GeV; MadGraph
loses precision below).

Results are cached in ``<tools>/mg5-production`` by the UFO's content and the run's settings. The generated process
is kept and reused for every point of the same model (the same particles and vertices): the UFO's couplings are
external parameters (``ufo_export``'s ``external_couplings``), so a point sets its masses, widths and couplings and a
scan compiles once (F1: with the couplings written as numbers, which move with every m_χ through the mixing and g_s,
the process had been regenerated at every point).
"""

from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import gzip
import hashlib
import json
import math
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from adroit.core.config import child_environment
from adroit.core.checkpoint import atomic_json
from adroit.core.config import get_settings

NEVENTS = 10_000
SQRT_S = 13_000.0
REACH = 0.8                          # pairs heavier than 80% of √s are not produced at a usable rate
LIGHT = ("u", "d", "s", "c")
PROTON = "g u c d s u~ c~ d~ s~"
TIMEOUT_S = 3600
RUN = {"ebeam1": 6500.0, "ebeam2": 6500.0, "lpp1": 1, "lpp2": 1, "pdlabel": "nn23lo1", "nevents": NEVENTS,
       "use_syst": False, "dynamical_scale_choice": 3, "iseed": 12345, "hel_recycling": False}
XSEC = re.compile(r"Cross-section :\s+([0-9.eE+\-]+)\s+\+-\s+([0-9.eE+\-]+)\s+pb")
LABEL = "MG5LO"                      # the generator label the SLHA's XSECTION lines carry (``searches``)
GENERATION = "every tree-level 2 -> 2 diagram, explicit coupling orders (2026-10-17, R17-1)"   # in both cache keys
CACHE = "the model's work area locked across processes (2026-10-18, S18-01)"   # in the result key only:
# results cached before the lock may hold another point's σ and are recomputed; processes hold no point data
PARTONS = ("g", "u", "d", "s", "c")


def available() -> bool:
    """MadGraph and its Python are installed (``constraints.maddm``)."""
    from adroit.constraints import maddm
    return maddm.python().exists() and (maddm.mg5_dir() / "bin" / "mg5_aMC").exists()


def folder() -> Path:
    """The cache and work folder (no spaces: MadGraph cannot use them)."""
    return get_settings().tools_dir / "mg5-production"


def production_rules(rules):
    """The rules with u, d, s and c massless: the four-flavour proton's partons (module docstring)."""
    particles = [dataclasses.replace(p, mass=0.0) if p.name in LIGHT else p for p in rules.particles]
    return dataclasses.replace(rules, particles=particles)


def odd_names(rules, table: dict, dm: str) -> tuple[list[str], list[str]]:
    """(every odd state's MadGraph name, particle and antiparticle; those that are not the dark matter)."""
    odd, visible = [], []
    for p in rules.particles:
        if p.parity != -1:
            continue
        names = sorted({table[p.name][0], table[p.name][1]})
        odd += names
        if p.name != dm:
            visible += names
    return odd, visible


def _key(ufo: Path, request: dict, structure: bool = False) -> str:
    """The cache key of a run (every UFO file) or, with ``structure``, of its process (every file but the parameters,
    which a point sets: its masses and widths)."""
    from adroit.constraints import maddm
    files = [f for f in sorted(ufo.rglob("*.py")) if not (structure and f.name == "parameters.py")]
    material = {str(f.relative_to(ufo)): maddm._digest(f) for f in files}
    material["request"] = request
    material["engine"] = (maddm.mg5_dir() / "VERSION").read_text() if (maddm.mg5_dir() / "VERSION").exists() else ""
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()[:24]


def _point_settings(rules, table: dict) -> list[str]:
    """MadGraph's ``set`` lines for a point: every particle's mass and width (the process is reused across points)."""
    lines = []
    for p in rules.particles:
        code = table[p.name][2]
        if p.mass > 0:
            lines.append(f"set MASS {code} {p.mass:.10g}")
        if p.width > 0:
            lines.append(f"set DECAY {code} {p.width:.10g}")
    return lines


def _run(script: str, path: Path, cwd: Path) -> str:
    from adroit.constraints import maddm
    path.write_text(script)
    done = subprocess.run(maddm.offline(["nice", "-n", "10", str(maddm.python()), str(maddm.mg5_dir() / "bin" / "mg5_aMC"),
                                         str(path)]), cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT_S,
                          env=child_environment())
    log = done.stdout + done.stderr
    path.with_suffix(".log").write_text(log)
    if done.returncode:
        raise RuntimeError(f"MadGraph exit {done.returncode}; see {path.with_suffix('.log')}\n{log[-1500:]}")
    return log


def _single_core(procdir: Path) -> None:
    cfg = procdir / "Cards" / "me5_configuration.txt"
    lines = []
    for line in cfg.read_text().splitlines():
        key = line.lstrip("# ").split("=")[0].strip()
        lines.append("run_mode = 0" if key == "run_mode" else "nb_core = 1" if key == "nb_core" else line)
    cfg.write_text("\n".join(lines) + "\n")


def count_pairs(lhe: Path, odd_pdgs: set[int]) -> Counter:
    """Unweighted events by their pair of odd final states (the PDG codes, sorted)."""
    pairs: Counter = Counter()
    event: list[int] | None = None
    with gzip.open(lhe, "rt") as stream:
        for line in stream:
            if line.startswith("<event"):
                event = []
            elif line.startswith("</event"):
                if event is not None and len(event) == 2:
                    pairs[tuple(sorted(event))] += 1
                event = None
            elif event is not None:
                parts = line.split()
                if len(parts) > 6 and parts[1] == "1" and abs(int(parts[0])) in odd_pdgs:
                    event.append(int(parts[0]))
    return pairs


def tree_orders(rules) -> dict[str, int]:
    """The coupling-order limits that admit every tree-level 2 → 2 diagram of the exported model: per order, twice the
    largest of a three-point vertex or a contact vertex's own (module docstring; ``ufo_export.coupling_order``)."""
    from adroit.model_building import ufo_export as ux
    limits = dict.fromkeys(ux.ORDERS, 0)
    for v in rules.vertices:
        for order, n in ux.coupling_order(v).items():
            limits[order] = max(limits[order], n * (2 if len(v.legs) == 3 else 1))
    return limits


def generate_command(rules) -> str:
    """MadGraph's process: every visible odd state with any odd state, at every tree-level order (``tree_orders``)."""
    return "generate p p > vis odd " + " ".join(f"{k}<={n}" for k, n in tree_orders(rules).items())


def _classes(rules) -> dict[str, str]:
    """Each name, particle or antiparticle, → its particle's name."""
    out = {p.name: p.name for p in rules.particles}
    out.update({p.anti: p.name for p in rules.particles if p.anti})
    return out


def expected_pairs(rules, visible: list[str], odd: list[str]) -> set[frozenset[str]]:
    """The pairs {a, b} (a visible, b odd; particles up to conjugation) that some tree-level 2 → 2 diagram makes from
    the proton's partons: s-channel (i j X)(X a b), t- or u-channel (i a X)(j b X), or a contact (i j a b) vertex.
    Charge flow is not followed, so it can only name a pair MadGraph might rightly not make (the run then fails,
    conservatively), never miss one a diagram makes."""
    cls = _classes(rules)
    legs = [tuple(sorted(cls[x] for x in v.legs)) for v in rules.vertices]
    three = {key for key in legs if len(key) == 3}
    four = {key for key in legs if len(key) == 4}
    fields = sorted(set(cls.values()))
    vis, dark = {cls[x] for x in visible}, {cls[x] for x in odd}

    def has(*names: str) -> bool:
        key = tuple(sorted(names))
        return key in three or key in four

    out = set()
    for a in vis:
        for b in dark:
            for i in PARTONS:
                for j in PARTONS:
                    if has(i, j, a, b) or any((has(i, j, x) and has(x, a, b)) or (has(i, a, x) and has(j, b, x))
                                              or (has(i, b, x) and has(j, a, x)) for x in fields):
                        out.add(frozenset((a, b)))
    return out


def generated_pairs(procdir: Path, rules, table: dict) -> tuple[set[frozenset[str]], list[str]]:
    """(the pairs of MadGraph's subprocesses, in ``expected_pairs``' terms; every subprocess line), read from the
    ``Process:`` comments of the generated matrix elements."""
    by_mg = {}
    for p in rules.particles:
        name, anti, _ = table[p.name]
        by_mg[name] = by_mg[anti] = p.name
    lines = sorted({line.split("Process:", 1)[1].strip() for f in procdir.glob("SubProcesses/P*/matrix*.f")
                    for line in f.read_text(errors="replace").splitlines() if "Process:" in line})
    pairs = set()
    for line in lines:
        final = line.split(">", 1)[1].split()
        names = [by_mg[x] for x in final if x in by_mg]
        if len(names) == 2:
            pairs.add(frozenset(names))
    return pairs, lines


def check_generated(procdir: Path, rules, table: dict, visible: list[str], odd: list[str], command: str) -> None:
    """Raise RuntimeError unless MadGraph's process was generated with the explicit orders and makes every pair a
    tree diagram makes (``expected_pairs``; the external audit's R17-1)."""
    made, lines = generated_pairs(procdir, rules, table)
    orders = command.split("odd", 1)[1].split()
    if not lines or any("WEIGHTED" in line or not all(o in line.split() for o in orders) for line in lines):
        raise RuntimeError(f"MadGraph's process is not at the explicit orders {' '.join(orders)} (see {procdir})")
    cls = _classes(rules)
    names = {cls[p.name]: table[p.name][0].rstrip("~") for p in rules.particles}
    missing = sorted(" ".join(sorted(names[x] for x in pair)) for pair in expected_pairs(rules, visible, odd) - made)
    if missing:
        raise RuntimeError(f"MadGraph did not generate pairs a tree diagram makes: {', '.join(missing)}")


@contextlib.contextmanager
def _locked(work: Path):
    """Hold the model's production area exclusively across processes, waiting for another holder: its UFO, scripts,
    generated process, cards and events are shared by every point of the model (the stacked audit's S18-01)."""
    work.mkdir(parents=True, exist_ok=True)
    with (work / ".production.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def cross_sections(rules, dm: str, name: str) -> dict:
    """{"total_pb", "events", "pairs": {"pdg1 pdg2": σ in pb}} of every produced pair (module docstring). Raises
    RuntimeError where MadGraph fails or generates nothing."""
    from adroit.model_building import ufo_export as ux
    prod = production_rules(rules)
    table = ux.names(prod)
    odd, visible = odd_names(prod, table, dm)
    if not visible:
        return {"total_pb": 0.0, "events": 0, "pairs": {}}
    if any(v.kind == "FFFF" for v in prod.vertices):
        raise RuntimeError("a four-fermion contact term is not exported to MadGraph (its UFO Lorentz structures are not "
                           "written), so the model's pair production is not computed")
    work = folder() / re.sub(r"[^A-Za-z0-9_]", "_", name)
    work.mkdir(parents=True, exist_ok=True)
    with _locked(work):                    # export, generation, launch, collection, cache and cleanup (S18-01)
        ufo = ux.write(prod, work, "ufo_" + re.sub(r"[^A-Za-z0-9_]", "_", name)[:20], external_couplings=True)
        command = generate_command(prod)
        request = {"proton": PROTON, "odd": odd, "visible": visible, "run": RUN, "generate": command,
                   "generation": GENERATION}
        key = _key(ufo, {**request, "cache": CACHE})
        cached = work / f"xsec-{key}.json"
        if cached.exists():
            return json.loads(cached.read_text())
        procdir = work / f"proc-{_key(ufo, request, structure=True)}"      # reused across points of the same model
        if not (procdir / "bin" / "generate_events").exists():
            shutil.rmtree(procdir, ignore_errors=True)
            _run("\n".join([f"import model {ufo}", f"define p = {PROTON}", f"define odd = {' '.join(odd)}",
                            f"define vis = {' '.join(visible)}", command, f"output {procdir} -f"]) + "\n",
                 work / "generate.mg5", work)
            if not (procdir / "bin" / "generate_events").exists():
                raise RuntimeError(f"MadGraph generated no process for {name}; see {work / 'generate.log'}")
            _single_core(procdir)
        prod_odd = [p.name for p in prod.particles if p.parity == -1]
        check_generated(procdir, prod, table, [p for p in prod_odd if p != dm], prod_odd, command)
        (procdir / "RunWeb").unlink(missing_ok=True)
        log = _run("\n".join([f"launch {procdir}", *[f"set {k} {v}" for k, v in RUN.items()],
                              *_point_settings(prod, table), *ux.coupling_settings(prod), "done"]) + "\n",
                 work / "launch.mg5", work)
        found = XSEC.findall(log)
        lhe = sorted((procdir / "Events").glob("run_*/unweighted_events.lhe.gz"))
        if not found or not lhe:
            raise RuntimeError(f"MadGraph gave no cross-section for {name}; see {work / 'launch.log'}")
        total = float(found[-1][0])
        pdgs = {abs(table[p.name][2]) for p in prod.particles if p.parity == -1}
        pairs = count_pairs(lhe[-1], pdgs)
        events = sum(pairs.values())
        result = {"total_pb": total, "events": events,
                  "pairs": {f"{a} {b}": total * n / events for (a, b), n in pairs.items()} if events else {}}
        atomic_json(cached, result)
        for run in (procdir / "Events").glob("run_*"):                # the cache keeps the result; the process is kept
            shutil.rmtree(run, ignore_errors=True)
        return result


def sign(rec, table: dict) -> int:
    """+1 if the UFO's particle (its +PDG code) is the record's particle, −1 if the export flipped the Dirac fermion
    for MadGraph's fermion flow, so that the UFO's particle is the record's antiparticle (``ufo_export.flipped``)."""
    name, anti, _ = table[rec.name]
    return -1 if name.endswith("~") and anti == name[:-1] else 1


def pdg(name: str, rules, table: dict) -> int:
    """A leg's PDG code in the UFO's numbering (MadGraph's events), negative for the UFO's antiparticle."""
    for p in rules.particles:
        code = sign(p, table) * table[p.name][2]
        if name == p.name:
            return code
        if p.anti and name == p.anti:
            return -code if p.anti != p.name else code
    raise KeyError(name)


def self_conjugate_codes(rules, table: dict) -> set[int]:
    """The PDG codes of the particles that are their own antiparticles (h, Z, γ, g, Majorana and real states)."""
    return {table[p.name][2] for p in rules.particles if not p.anti or p.anti == p.name}


M_MU, M_TAU, M_C = 0.10566, 1.77686, 1.27
PARTONIC = 1.5                       # GeV: above this splitting W* → q q̄′ partonically, below it W* → π


def _phase_space(x: float) -> float:
    """The three-body phase space of a massive lepton (mass ratio x = m/Δ) against a massless one, as in muon decay."""
    if x >= 1.0:
        return 0.0
    r = math.sqrt(1.0 - x * x)
    return r * (1.0 - 4.5 * x * x - 4.0 * x ** 4) + 7.5 * x ** 4 * math.log((1.0 + r) / x)


def soft_widths(delta: float, weight: float, axial: float = 0.0, boson: str = "W") -> dict[str, float]:
    """Partial widths (GeV) of a heavy state's decay to a lighter partner through an off-shell W or Z, by the boson's
    final state (module docstring). ``weight`` = 2|V|²/g² and ``axial`` = 2|A|²/g² of the pair's vertex: a wino's
    weight is 2 and a higgsino's 1 (``lhc.chargino_width``), both with no axial part."""
    from adroit.constraints.lhc import F_PI, M_PI, V_UD
    from adroit.model_building.feynman import SM_FERMIONS
    from adroit.model_building.gauge_basis import G2, M_W, M_Z
    current = weight + 3.0 * axial                               # 2(|V|² + 3|A|²)/g²
    unit = G2 ** 2 / 2.0 * delta ** 5 / (120.0 * math.pi ** 3)    # × (|f_L|² + |f_R|²)/m_B⁴ and the phase space
    out: dict[str, float] = {}
    if boson == "W":
        lepton = current * unit * (G2 ** 2 / 2.0) / M_W ** 4
        out = {"e": lepton, "mu": lepton * _phase_space(M_MU / delta)}
        if delta > M_TAU:
            out["tau"] = lepton * _phase_space(M_TAU / delta)
        if delta < PARTONIC:
            if delta > M_PI:
                q2 = delta ** 2 - M_PI ** 2                              # |q|² of the pion; q⁰ = Δ
                pion = (G2 ** 4 / (32.0 * M_W ** 4)) * F_PI ** 2 * V_UD ** 2 * math.sqrt(q2) / math.pi
                out["pi"] = (weight * delta ** 2 + axial * q2) * pion
        else:
            out["ud"] = 3.0 * lepton
            if delta > M_C:
                out["cs"] = 3.0 * lepton * _phase_space(M_C / delta)
        return {k: v for k, v in out.items() if v > 0}
    cw2 = (M_W / M_Z) ** 2
    for f in SM_FERMIONS:
        coloured = f.colour == "3"
        if f.name == "t" or (coloured and delta < PARTONIC) or delta <= 2.0 * f.mass:
            continue
        f_l = G2 / math.sqrt(cw2) * (f.t3 - f.charge * (1.0 - cw2))
        f_r = -G2 / math.sqrt(cw2) * f.charge * (1.0 - cw2)
        space = _phase_space(2.0 * f.mass / delta) if f.mass > 0 else 1.0
        out[f.name] = (3.0 if coloured else 1.0) * current * unit * (abs(f_l) ** 2 + abs(f_r) ** 2) / M_Z ** 4 * space
    return {k: v for k, v in out.items() if v > 0}


W_STAR = {"pi": (211,), "e": (-11, 12), "mu": (-13, 14), "tau": (-15, 16), "ud": (2, -1), "cs": (4, -3)}
Z_STAR = {"nu_e": (12, -12), "nu_mu": (14, -14), "nu_tau": (16, -16), "e": (11, -11), "mu": (13, -13),
          "tau": (15, -15), "u": (2, -2), "d": (1, -1), "s": (3, -3), "c": (4, -4), "b": (5, -5)}
BOSONS = {"W": "W", "W~": "W", "Z": "Z"}


def _soft_partners(rules, name: str):
    """(other, boson, weight, axial) for each vertex joining ``name`` to a lighter new state of its spin by a W or a Z
    (one per partner and boson): weight = 2|V|²/g², axial = 2|A|²/g² (a scalar pair's current is a vector)."""
    from adroit.model_building.gauge_basis import G2
    by = {p.name: p for p in rules.particles} | {p.anti: p for p in rules.particles if p.anti}
    seen = set()
    for v in rules.vertices:
        if v.kind not in ("FFV", "VSS") or v.legs.count(name) != 1:
            continue
        bosons = [BOSONS[leg] for leg in v.legs if leg in BOSONS]
        others = [leg for leg in v.legs if leg != name and leg not in BOSONS]
        if len(bosons) != 1 or len(others) != 1 or others[0] not in by:
            continue
        other, boson = others[0], bosons[0]
        if by[other].parity != -1 or by[other].spin != by[name].spin or (other, boson) in seen:
            continue
        seen.add((other, boson))
        axial = 2.0 * abs(v.c2) ** 2 / G2 ** 2 if v.kind == "FFV" else 0.0
        yield other, boson, 2.0 * abs(v.c) ** 2 / G2 ** 2, axial


def soft_decay_table(rules, table: dict, name: str) -> tuple[float, list[tuple[float, list[int]]]]:
    """(Γ, [(branching, [daughters])]) of the UFO's particle of ``name`` decaying through an off-shell W or Z to a
    lighter new state of its spin (``soft_widths``), where it has no open two-body channel; (0, []) where none
    applies."""
    from adroit.model_building.gauge_basis import M_W, M_Z
    by = {p.name: p for p in rules.particles} | {p.anti: p for p in rules.particles if p.anti}
    charge = {p.name: p.charge for p in rules.particles} | {p.anti: -p.charge for p in rules.particles if p.anti}
    x = by[name]
    fixed = self_conjugate_codes(rules, table)
    flip = sign(x, table) < 0                         # the UFO's particle is the record's antiparticle: CP-conjugate
    channels: dict[tuple[int, ...], float] = {}
    for other, boson, weight, axial in _soft_partners(rules, name):
        delta = x.mass - by[other].mass
        q = round(charge[name] - charge[other])
        if not 0.0 < delta < (M_W if boson == "W" else M_Z) or abs(q) != (1 if boson == "W" else 0):
            continue
        codes = W_STAR if boson == "W" else Z_STAR
        for key, width in soft_widths(delta, weight, axial, boson).items():
            daughters = [pdg(other, rules, table), *(c if q >= 0 else -c for c in codes[key])]
            if flip:
                daughters = [c if abs(c) in fixed else -c for c in daughters]
            k = tuple(sorted(daughters))
            channels[k] = channels.get(k, 0.0) + width
    total = sum(channels.values())
    return (total, [(w / total, list(k)) for k, w in channels.items()]) if total > 0 else (0.0, [])


def decay_table(rules, table: dict, name: str) -> tuple[float, list[tuple[float, list[int]]]]:
    """(Γ in GeV, [(branching, [daughter PDG codes])]) of the UFO's particle of the record ``name`` (its +PDG code;
    the record's antiparticle where the export flipped it), from its two-body decays (module docstring). The
    daughters are conjugated where that conserves the charge."""
    from adroit.model_building.feynman import _colour_factor, two_body_width
    by = {p.name: p for p in rules.particles} | {p.anti: p for p in rules.particles if p.anti}
    x = by[name]
    charge = {p.name: p.charge for p in rules.particles} | {p.anti: -p.charge for p in rules.particles if p.anti}
    channels: dict[tuple[int, ...], float] = {}
    for v in rules.vertices:
        if v.legs.count(name) != 1 or len(v.legs) != 3:
            continue
        others = [o for o in v.legs if o != name]
        if sum(by[o].mass for o in others) >= x.mass:
            continue
        colour = _colour_factor(x.colour, [by[o].colour for o in others]) or 1.0
        width = two_body_width(v, v.legs.index(name), [by[o].mass for o in v.legs], colour)
        width *= 0.5 if others[0] == others[1] else 1.0
        if width <= 0:
            continue
        codes = [pdg(o, rules, table) for o in others]
        if abs(sum(charge[o] for o in others) - x.charge) > 1e-6:
            codes = [-c if by[o].anti and by[o].anti != by[o].name else c for c, o in zip(codes, others)]
        key = tuple(sorted(codes))
        channels[key] = channels.get(key, 0.0) + width
    total = sum(channels.values())
    if total <= 0:
        return 0.0, []
    if sign(x, table) < 0:                        # the UFO's particle is the record's antiparticle: CP-conjugate
        fixed = self_conjugate_codes(rules, table)
        return total, [(w / total, sorted(c if abs(c) in fixed else -c for c in k)) for k, w in channels.items()]
    return total, [(w / total, list(k)) for k, w in channels.items()]
