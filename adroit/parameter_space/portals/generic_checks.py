"""What the generic engine (G4) checks beside Ωh²: the reach of long-range forces, and the assumptions of freeze-out.

**Long-range forces (decision D4).** The bath's pairs are grouped by the multiplets they come from. Each group's share
of ⟨σ_eff v⟩ goes to G4's Sommerfeld bracket (``constraints.long_range_bracket``) with the group's representations and
the forces the bath feels:
- SU(2), exchanged with m_W, and U(1)_Y (or electromagnetism, for a broken-phase singlet with a charge), massless;
- SU(3), massless;
- a new boson that couples a state to itself (a dark photon, a dark Higgs, a Yukawa mediator) with α = |c|²/4π:
  a vector attracts a particle–antiparticle pair and repels two particles; a scalar attracts every pair.

α runs to the Bohr momentum of the most attractive channel, as in the bracket's calibration. The bracket's centre is
the criterion: where it moves Ωh² by more than ``LONG_RANGE_SHIFT`` from the perturbative value, the Sommerfeld
effect matters and Ωh² is refused (G7 computes it). A plain screen (α_eff μ > m_V) would let through the wino between
0.5 and 2 TeV, where the Sommerfeld effect lowers its Ωh² by 23–41% (``docs/g4_generic.md``).

**The assumptions of freeze-out, certified at x_f:**
- *chemical equilibrium of the bath:* each coannihilator converts to the dark matter (two-body decays, then
  scattering on the light Standard Model bath, from G3's processes) faster than ``CONTACT`` × H;
- *kinetic contact:* each new Z₂-even state the bath annihilates into decays to the Standard Model faster than H;
- *g\\*:* new states lighter than T_f would add to g\\* (not included: flagged);
- *three-body tails* other than W* and Z* just below a final pair's threshold (not computed: flagged).
"""

from __future__ import annotations

import math

import numpy as np

from adroit.constraints import long_range_bracket as lb
from adroit.constraints import relic

LONG_RANGE_SHIFT = 0.10                 # the bracket's centre moving Ωh² by more than this refuses it
X_NODES = np.geomspace(1.0, 2e4, 140)   # the bracket's x nodes (as its calibration)
CONTACT = 10.0                          # conversion and decay rates must exceed CONTACT × H at x_f
SM = frozenset({"A", "Z", "W", "W~", "g", "h", "e", "e~", "mu", "mu~", "tau", "tau~", "nu_e", "nu_e~", "nu_mu",
                "nu_mu~", "nu_tau", "nu_tau~", "u", "u~", "d", "d~", "s", "s~", "c", "c~", "b", "b~", "t", "t~"})
LIGHT_BATH = ("e", "mu", "tau", "nu_e", "nu_mu", "nu_tau", "u", "d", "s", "c", "b", "A", "g")
CONJUGATE_COLOUR = {"1": "1", "3": "3bar", "3bar": "3", "8": "8"}


# --- representations ----------------------------------------------------------------------------------------

def _state(mb, name: str):
    base = name[:-1] if name.endswith("~") else name
    return next(s for s in mb.spectrum.states if s.name == base)


def dominant_field(mb, state):
    """The field that makes up most of a mass-basis state."""
    key = max(state.composition, key=lambda k: abs(state.composition[k]))
    return mb.gauge.spec.field(key.split("[")[0].split(".")[0])


def representation(mb, name: str) -> tuple[int, str, float, float]:
    """(SU(2) dimension, SU(3) representation, hypercharge, electric charge) of a bath state, conjugated for an
    antiparticle (``s~``)."""
    state = _state(mb, name)
    field = dominant_field(mb, state)
    n, colour, y = field.charges.su2, field.charges.su3, field.charges.hypercharge
    q = state.charge
    if name.endswith("~"):
        return n, CONJUGATE_COLOUR[colour], -y, -q
    return n, colour, y, q


# --- the forces and the bracket -----------------------------------------------------------------------------

def dark_forces(rules, state: str) -> list[tuple[float, float, str, int]]:
    """(α = |c|²/4π, mediator mass, mediator, spin) of each new boson coupling ``state`` to itself."""
    by = {p.name: p for p in rules.particles}
    out = []
    for v in rules.vertices:
        if state not in v.legs or len(v.legs) != 3 or v.kind not in ("FFV", "FFS", "VSS", "SSS"):
            continue
        mediator = v.legs[2] if v.kind in ("FFV", "FFS") else v.legs[0] if v.kind == "VSS" else None
        if v.kind == "SSS":
            mediator = next((x for x in v.legs if x.rstrip("~") != state), None)
        if mediator is None or mediator in SM or mediator not in by or by[mediator].parity != 1:
            continue
        if [x.rstrip("~") for x in v.legs if x != mediator] != [state, state]:
            continue
        # a trilinear μ φ*φ S acts on the pair as a Yukawa coupling μ/(2m) (G3's amplitude at the pair's mass; the
        # audit's G3/G4-8, G12: it had been μ/m, α four times too large)
        coupling = abs(v.c) if v.kind != "SSS" else abs(v.c) / max(2.0 * by[state].mass, 1e-9)
        out.append((coupling ** 2 / (4 * math.pi), by[mediator].mass, mediator, int(by[mediator].spin)))
    return out


def _sm_forces(reps: list[tuple[int, str, float, float]], m: float, phase: str) -> list[lb.GaugeForce]:
    """SU(2), U(1)_Y or electromagnetism, SU(3): α at the Bohr momentum of the most attractive channel."""
    from adroit.constraints import sommerfeld
    from adroit.parameter_space.portals.multiplet import ALPHA_EM, M_W, alpha_2, alpha_y
    n_max = max(r[0] for r in reps)
    strength = (n_max * n_max - 1) / 4 if n_max > 1 else max((r[2] ** 2 for r in reps), default=0.0)
    forces = []
    if n_max > 1:
        forces.append(lb.GaugeForce(group="SU2", alpha=lb.bohr_alpha(alpha_2, strength, 0.5 * m), mediator_gev=M_W))
    if any(r[2] for r in reps):
        forces.append(lb.GaugeForce(group="U1", name="Y", alpha=lb.bohr_alpha(alpha_y, max(strength, 1e-3), 0.5 * m)))
    elif phase == "broken" and any(r[3] for r in reps):
        forces.append(lb.GaugeForce(group="U1", name="em", alpha=ALPHA_EM))
    if any(r[1] != "1" for r in reps):
        forces.append(lb.GaugeForce(group="SU3", alpha=sommerfeld.alpha_bohr(m)))
    return forces


def _pair_charges(reps, i: int, j: int, names: list[str], dark: dict) -> dict[str, tuple[float, float]]:
    """Each U(1)'s charges of the pair (i, j): Y or Q, and each dark mediator's, as √(α_state/α_force)."""
    out = {"Y": (reps[i][2], reps[j][2]), "em": (reps[i][3], reps[j][3])}
    for mediator, (alpha, _, spin) in dark["forces"].items():
        a_i = dark["states"].get(names[i], {}).get(mediator, 0.0)
        a_j = dark["states"].get(names[j], {}).get(mediator, 0.0)
        if a_i and a_j:
            q_i, q_j = math.sqrt(a_i / alpha), math.sqrt(a_j / alpha)
            if spin == 1:                           # a vector: the antiparticle carries −q
                q_i *= -1 if names[i].endswith("~") else 1
                q_j *= -1 if names[j].endswith("~") else 1
            else:                                   # a scalar attracts every pair
                q_j = -q_j
            out[f"dark:{mediator}"] = (q_i, q_j)
    return out


def _dark(rules, names: list[str]) -> dict:
    """The bath's dark forces: per state, α by mediator; per mediator, the largest α, its mass and spin."""
    states, forces = {}, {}
    for name in names:
        for alpha, mass, mediator, spin in dark_forces(rules, name.rstrip("~")):
            states.setdefault(name, {})[mediator] = alpha
            if alpha > forces.get(mediator, (0.0,))[0]:
                forces[mediator] = (alpha, mass, spin)
    return {"states": states, "forces": forces}


def bracket_inputs(mb, rules, bath, species, pairs, finals, resonances) -> lb.BracketInputs | None:
    """The bracket's inputs (species, x nodes, each multiplet pair's rate, the forces), or None if no long-range
    force acts on the bath."""
    names = [b[0] for b in bath]
    reps = [representation(mb, n) for n in names]
    dark = _dark(rules, names)
    m = min(sp.mass for sp in species)
    forces = _sm_forces(reps, m, mb.gauge.spec.phase.value)
    forces += [lb.GaugeForce(group="U1", name=f"dark:{k}", alpha=a, mediator_gev=mass)
               for k, (a, mass, _) in dark["forces"].items()]
    if not forces:
        return None
    groups: dict[tuple, list[tuple[int, int]]] = {}
    for (i, j) in pairs:
        key = tuple(sorted(((dominant_field(mb, _state(mb, names[k])).name, names[k].endswith("~"))
                            for k in (i, j))))
        groups.setdefault(key, []).append((i, j))
    out = []
    for members in groups.values():
        i, j = members[0]
        rate = relic.coannihilation_average(species, {k: pairs[k] for k in members}, X_NODES, resonances)
        sm_only = all(c in SM and d in SM for k in members for c, d in finals[k])
        pair = lb.PairRep(su2=(reps[i][0], reps[j][0]), su3=(reps[i][1], reps[j][1]),
                          charges=_pair_charges(reps, i, j, names, dark))
        out.append(lb.PairRate(pair=pair, rate=rate.tolist(), final_su2_max=5 if sm_only else None))
    return species, X_NODES, out, forces


def shift(b: lb.Bracket) -> float:
    """How far the bracket's centre moves Ωh² from the perturbative value (a fraction)."""
    return abs(b.omega_central / b.omega_perturbative - 1.0)


def long_range_reason(b: lb.Bracket | None) -> str:
    """Why Ωh² is refused for want of the Sommerfeld effect, or "" (module docstring)."""
    if b is None or shift(b) <= LONG_RANGE_SHIFT:
        return ""
    return (f"needs the Sommerfeld effect (G7): the attractive channel's α_eff = {b.alpha_max:.3g} moves Ωh² from "
            f"{b.omega_perturbative:.3g} (perturbative) to about {b.omega_central:.3g} (the bracket's centre; "
            f"bracket {b.omega_low:.3g}–{b.omega_high:.3g})")


def estimate_flag(b: lb.Bracket, refused: bool) -> str:
    """The estimate as a flag: the perturbative Ωh², the bracket, and the warning. Never a verdict."""
    head = "Ωh² refused; the estimate on request" if refused else "the Sommerfeld effect, bracketed"
    return (f"{head}: perturbative Ωh² = {b.omega_perturbative:.3g}; with the Sommerfeld effect between "
            f"{b.omega_low:.3g} and {b.omega_high:.3g} (rough centre {b.omega_central:.3g}, typically 5–40% low in "
            f"thermal mass). Bound states can lower Ωh² by up to about a factor 2 more. Warning: {lb.WARNING}")


# --- the assumptions of freeze-out ----------------------------------------------------------------------------

def hubble(temperature: float) -> float:
    """H (GeV) in radiation domination at T."""
    g, _, _ = relic.degrees_of_freedom(temperature)
    return 1.66 * math.sqrt(g) * temperature ** 2 / relic.M_PLANCK_GEV


def _decays(rules, name: str, into: set[str]) -> float:
    """Σ two-body widths of ``name`` into one of ``into`` plus anything lighter. A new neutral boson's quark and gluon
    pairs count only above its hadronic window (``generic_hadronic.partonic_decays``): below its opening they are
    closed, and in the window only Γ_had ≥ 0 is known, so the sum is a lower bound, which is what certifying contact
    needs (C21-02). Each channel as ``feynman.widths`` sums it: ½ for identical final particles, and its colour sum
    (the independent audit, NA15-04, 2026-11-16: S → h h had counted twice its rate, 1.5H for 0.75H, and contact
    was certified); a structure without a colour sum is left out, which keeps the bound."""
    from adroit.model_building.feynman import _colour_factor, two_body_width
    from adroit.parameter_space.portals import generic_hadronic as gh
    by = {p.name: p for p in rules.particles} | {p.anti: p for p in rules.particles if p.anti}
    partonic = gh.partonic_decays(rules, name)
    total = 0.0
    for v in rules.vertices:
        if v.kind not in ("SSS", "FFS", "FFV", "VSS", "VVS") or v.legs.count(name) != 1:
            continue
        others = [x for x in v.legs if x != name]
        if not any(o in into for o in others) or sum(by[o].mass for o in others) >= by[name].mass:
            continue
        if not partonic and all(o in gh.PARTON_NAMES for o in others):
            continue
        colour = _colour_factor(by[name].colour, [by[o].colour for o in others])
        if colour is None:
            continue
        total += two_body_width(v, v.legs.index(name), [by[x].mass for x in v.legs], colour) * (
            0.5 if others[0] == others[1] else 1.0)
    return total


def _scattering(model, name: str, targets: set[str], temperature: float) -> float:
    """Σ n_f ⟨σv⟩ of name + f → (a target) + f′ on the light Standard Model bath (f with m < T, v = 1, the f's
    energy 3T)."""
    from adroit.constraints import tree
    parts = model.particles
    total = 0.0
    for f in LIGHT_BATH:
        for f_name in dict.fromkeys((f, parts[f].conjugate)):
            if parts[f_name].mass > temperature:
                continue
            s = parts[name].mass ** 2 + 2 * parts[name].mass * 3 * temperature
            dof = {0.5: 2 * 0.75, 1: 2.0, 0: 1.0}[parts[f_name].spin] * parts[f_name].colours
            density = dof * 1.2020569 * temperature ** 3 / math.pi ** 2
            for target in targets:
                for out in SM:
                    try:
                        process = tree.Process(model, name, f_name, target, out, points=12)
                    except (ValueError, KeyError):
                        continue
                    if process.diagrams():
                        total += density * process.sigma(s)
    return total


def chemical_flags(mb, rules, model, bath, x_f: float) -> list[str]:
    """Each coannihilator whose conversion to the dark matter is slower than CONTACT × H at x_f."""
    dm = mb.spectrum.dark_matter()
    targets = {dm.name} | ({f"{dm.name}~"} if dm.kind not in ("real", "majorana", "vector") else set())
    temperature = dm.mass_gev / x_f
    h = hubble(temperature)
    out = []
    for name, mass, _ in bath:
        if name in targets or name.endswith("~"):
            continue
        rate = _decays(rules, name, targets)
        if rate < CONTACT * h:
            rate += _scattering(model, name, targets, temperature)
        if rate < CONTACT * h:
            out.append(f"chemical equilibrium not certified: {name} converts to the dark matter at {rate:.2g} GeV, "
                       f"below {CONTACT:g} H = {CONTACT * h:.2g} GeV at x_f = {x_f:.3g}; the coannihilating bath "
                       f"assumes it")
    return out


def kinetic_flags(rules, finals: dict, x_f: float, m: float) -> list[str]:
    """Each new Z₂-even final state that decays to the Standard Model slower than H at x_f."""
    h = hubble(m / x_f)
    new = sorted({x for pair in finals.values() for c, d in pair for x in (c, d) if x not in SM})
    out = []
    for name in new:
        rate = _decays(rules, name, set(SM))
        if rate < h:
            out.append(f"kinetic contact not certified: {name} decays to the Standard Model at {rate:.2g} GeV, "
                       f"below H = {h:.2g} GeV at x_f = {x_f:.3g}; the dark sector may not share the bath's "
                       f"temperature")
    return out


def light_state_flags(rules, x_f: float, m: float) -> list[str]:
    """New states lighter than T_f, which would add to g* (not included)."""
    temperature = m / x_f
    light = [p.name for p in rules.particles if p.name not in SM and p.mass < temperature]
    if not light:
        return []
    return [f"new states lighter than T_f = {temperature:.3g} GeV ({', '.join(light)}) would add to g*; Ωh² uses the "
            f"Standard Model's g*"]


UNSTABLE_SM = frozenset({"t", "t~", "h"})
THREE_BODY = 0.8                    # a final pair opening below 2m_χ/0.8 has a three-body tail that matters


def three_body_flags(model, finals: list[tuple[str, str]], m: float) -> list[str]:
    """Final pairs of the dark matter that open just above 2m_χ through an unstable particle other than the W or
    the Z: the thermal tail reaches them on shell, but their three-body tail below threshold (one particle off
    shell) is not computed. The W* and Z* tails are (``ufo.off_shell_sigma``)."""
    out = []
    for c, d in finals:
        pc, pd = model.particles[c], model.particles[d]
        threshold = pc.mass + pd.mass
        if not 2 * m < threshold <= 2 * m / THREE_BODY:
            continue
        unstable = [x.name for x in (pc, pd)
                    if x.name in UNSTABLE_SM or (x.width > 0 and abs(x.pdg) not in (23, 24) and x.name not in SM)]
        if unstable:
            out.append(f"three-body tail not computed: {c} {d} opens at √s = {threshold:.4g} GeV, above 2m_χ = "
                       f"{2 * m:.4g} GeV; it is reached through the thermal tail, but not below threshold with "
                       f"{unstable[0]} off shell")
    return out


def invisible_widths(rules, dm_name: str, dm_anti: str) -> dict[str, float]:
    """Γ(h → DM DM̄) and Γ(Z → DM DM̄) (GeV) at tree level, where they are open."""
    from adroit.model_building.feynman import two_body_width
    by = {p.name: p for p in rules.particles} | {p.anti: p for p in rules.particles if p.anti}
    out = {}
    for boson in ("h", "Z"):
        if boson not in by:
            continue
        for v in rules.vertices:
            if boson not in v.legs or sorted(x for x in v.legs if x != boson) != sorted((dm_name, dm_anti)):
                continue
            width = two_body_width(v, v.legs.index(boson), [by[x].mass for x in v.legs])
            if width > 0:
                out[boson] = out.get(boson, 0.0) + width * (0.5 if dm_name == dm_anti else 1.0)
    return out
