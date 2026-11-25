"""Annihilation today for the generic engine (G6): σv by final state in the searches' channels, two-body cascades
through new states, the CMB's energy deposition, lines, and long-range effects today.

**σv today.** DM DM̄ → c d at s = 4m²/(1 − (v/2)²) from G3 (off-shell W and Z near and below threshold, as for Ωh²),
in cm³/s. Standard Model pairs carry the searches' names (``CHANNELS``: b, tau, W, Z, hh, Zh, gamma, Zgamma, …).

**Cascades** (decision D13). A final state with a new Z₂-even state X is named by its particles ("S S", "Zp h"). Its
photons are a two-body topology (``spectra.Daughter``): X decays at rest by G2's two-body widths into Standard Model
pairs, or into the dark matter (``invisible``), and is boosted to its energy. A decay of X into other new states (a
longer chain), or into a pair PPPC does not tabulate, leaves the channel without a spectrum; the searches then bound
it by their conservative mixture rules.

**The CMB** (``cmb_f_eff_range``): a cascade's f_eff lies between the smallest and largest f_eff of its daughters'
showers over the energies they can have (Slatyer's table), weighted by their branching and energy; ``invisible``
deposits nothing. Below a channel's first tabulated mass its f_eff is taken there (it varies slowly: bb̄ 0.22 at
6 GeV, 0.21 at 100 GeV).

A Higgs-like X (one with an H⁰ component) also decays through the Higgs's loops: Γ(X → gg) is its tree Γ(X → bb̄)
times the library's Γ(h* → gg)/Γ(h* → bb̄) at m_X, as ``higgs_loops``. Its γγ and Zγ (about 0.2%) are left out: the
spectra have no column for a line boosted from a moving parent.

**The Higgs's loop-induced channels** (gg, γγ, Zγ; ``higgs_loops``): where the pair couples to a Higgs-like scalar,
σ(→ S* → bb̄) through those scalars times the library's Γ(h* → X)/Γ(h* → bb̄), as the library's Higgs portals have
them. They enter Ωh² as well as annihilation today.

**Lines** beyond the Higgs's are loop-induced and are not computed here (G8): a model whose dark matter carries gauge
charge or couples to charged states is flagged.

**Long-range effects today** (``today_long_range``): the most attractive channel of the dark-matter pair (the G4
bracket's channels, with its forces) enhances annihilation at the dwarfs' v = 10⁻⁴ by S. Where S > 1.1 every search
that needs annihilation today is undecided until G8 computes it.
"""

from __future__ import annotations

import math

import numpy as np

from adroit.constraints import long_range_bracket as lb

TODAY_SPEED = 1e-4                       # the dwarf galaxies', the slowest search
TODAY_SHIFT = 0.10                       # S above 1 + this needs G8
FERMIONS = ("e", "mu", "tau", "nu_e", "nu_mu", "nu_tau", "u", "d", "s", "c", "b", "t")
CHANNELS = {**{tuple(sorted((f, f"{f}~"))): f for f in FERMIONS},
            ("W", "W~"): "W", ("Z", "Z"): "Z", ("h", "h"): "hh", ("Z", "h"): "Zh", ("A", "A"): "gamma",
            ("A", "Z"): "Zgamma", ("g", "g"): "g", ("A", "h"): "hgamma"}
SINGLE = {"Z": "Z", "W": "W", "W~": "W", "h": "hh", "g": "g", "t": "t", "t~": "t", "b": "b", "b~": "b"}
STANDARD = frozenset(FERMIONS) | {f"{f}~" for f in FERMIONS} | {"W", "W~", "Z", "A", "g", "h"}


def channel_name(c: str, d: str) -> str:
    """The searches' name of a final pair; a pair with a new state is named by its particles."""
    key = tuple(sorted((c, d)))
    return CHANNELS.get(key, " ".join(key))


def dark_pair(mb) -> tuple[str, str]:
    dm = mb.spectrum.dark_matter()
    return dm.name, dm.name if dm.kind in ("real", "majorana", "vector") else f"{dm.name}~"


def annihilation_today(mb, rules, model, v_rel: float) -> dict[str, float]:
    """σv (cm³/s) by channel at relative speed v_rel (module docstring)."""
    from adroit.constraints import tree
    from adroit.constraints.annihilation import GEV2_TO_CM3_S
    from adroit.parameter_space.portals.generic import final_states
    from adroit.parameter_space.portals.ufo import OFF_SHELL, OFF_SHELL_REACH, off_shell_sigma
    dm, anti = dark_pair(mb)
    m = model.particles[dm].mass
    s = 4.0 * m * m / (1.0 - (0.5 * v_rel) ** 2)
    out: dict[str, float] = {}
    for c, d in final_states(model, dm, anti):
        process = tree.Process(model, dm, anti, c, d)
        final = process.p[2:]
        vectors = [x for x in final if abs(x.pdg) in OFF_SHELL and x.width > 0]
        near = vectors and math.sqrt(s) <= sum(x.mass for x in final) + OFF_SHELL_REACH * sum(x.width for x in vectors)
        sigma = off_shell_sigma(process, s) if near else process.sigma(s)
        if sigma > 0:
            name = channel_name(c, d)
            out[name] = out.get(name, 0.0) + sigma * v_rel * GEV2_TO_CM3_S
    loops = higgs_loops(mb, model, dm, anti)
    for name, sigma in (loops(s) if loops else {}).items():
        out[name] = out.get(name, 0.0) + sigma * v_rel * GEV2_TO_CM3_S
    return out


# --- the Higgs's loop-induced channels ---------------------------------------------------------------------------

LOOPS = {"g": "g", "gamma": "gamma", "Zgamma": "Zgamma"}    # higgs.partial_widths name → the searches' name


def higgs_like(mb) -> list[str]:
    """The neutral even scalar states with an H⁰ component."""
    keys = ("H[m=-0.5,re]", "h[m=0,r]")
    return [st.name for st in mb.spectrum.states
            if st.spin == 0 and st.parity == 1 and st.charge == 0 and any(abs(st.composition.get(k, 0)) > 1e-12
                                                                           for k in keys)]


def higgs_loops(mb, model, a: str, b: str):
    """σ(a b → S* → X)(s) for the Higgs's loop-induced X (gg, γγ, Zγ) as a function of s returning {name: σ}, or
    None where a b does not couple to a Higgs-like scalar S.

    The pair's coupling and the propagators are G3's: σ(a b → S* → bb̄) through the Higgs-like scalars alone
    (interference between them kept) times Γ(h* → X)/Γ(h* → bb̄) at √s, Γ(h* → X) the library's
    (``higgs.partial_widths``) and Γ(h* → bb̄) the tree width with the same Yukawa. This factorisation holds where
    the scalars couple to quarks and gluons as the Higgs does (their H⁰ share)."""
    from adroit.constraints import higgs, tree
    from adroit.model_building.feynman import yukawa_mass
    from adroit.model_building.gauge_basis import V_EW
    scalars = set(higgs_like(mb))
    pair = sorted((a, b))
    keep = [v for v in model.vertices if len(v.legs) == 3 and set(v.legs) & scalars and
            (sorted(x for x in v.legs if x not in scalars) in (pair, ["b", "b~"]) or
             (a == b and sorted(v.legs[:2]) == [a, a]))]
    if not any(set(v.legs) >= {"b", "b~"} for v in keep) or len(keep) < 2:
        return None
    reduced = tree.Model({})
    reduced.particles = model.particles
    reduced.vertices = keep
    try:
        process = tree.Process(reduced, a, b, "b", "b~", points=8)
    except (ValueError, KeyError):
        return None
    if not process.diagrams():
        return None
    y_b, m_b = yukawa_mass("b") / V_EW, model.particles["b"].mass

    def sigma(s: float) -> dict[str, float]:
        root = math.sqrt(s)
        if root <= 2.2 * m_b:
            return {}
        tree_bb = 3 * y_b ** 2 * root * (1 - 4 * m_b ** 2 / s) ** 1.5 / (8 * math.pi)
        widths = higgs.partial_widths(root)
        base = process.sigma(s)
        return {name: base * widths[key] / tree_bb for key, name in LOOPS.items() if widths.get(key, 0) > 0}
    return sigma


# --- cascades -------------------------------------------------------------------------------------------------

def _loop_widths(mass: float, m_b: float, bb: float) -> dict[str, float]:
    """A Higgs-like X's widths into gg, γγ, Zγ from its tree width into bb̄ (module docstring)."""
    from adroit.constraints import higgs
    from adroit.model_building.feynman import yukawa_mass
    from adroit.model_building.gauge_basis import V_EW
    tree_bb = 3 * (yukawa_mass("b") / V_EW) ** 2 * mass * (1 - 4 * m_b ** 2 / mass ** 2) ** 1.5 / (8 * math.pi)
    widths = higgs.partial_widths(mass)
    return {name: bb * widths[key] / tree_bb for key, name in LOOPS.items() if widths.get(key, 0) > 0}


def decays(rules, name: str, dm: tuple[str, str], higgs_like_states: frozenset[str] = frozenset()):
    """X's two-body decay fractions as ``spectra.Decay``s (``invisible`` into the dark matter), or None where X
    decays into other new states or into a pair PPPC does not tabulate, or whose hadronic width is in the hadronic window
    (``generic_hadronic.windowed``: not computed). Below X's hadronic opening its quark and gluon pairs are closed, as
    in its portrait (``generic_hadronic.closed_decays``, C21-02). A Higgs-like X adds the Higgs's loop decays."""
    from adroit.parameter_space.portals import generic_hadronic as gh
    if name in gh.windowed(rules):
        return None
    from adroit.constraints.spectra import COLUMNS, Decay
    from adroit.model_building.feynman import _colour_factor, two_body_width
    by = {p.name: p for p in rules.particles} | {p.anti: p for p in rules.particles if p.anti}
    x = by[name]
    closed = gh.closed_decays(rules, name)
    widths: dict[str, float] = {}
    for v in rules.vertices:
        if v.kind not in ("SSS", "FFS", "FFV", "VSS", "VVS", "VVV") or v.legs.count(name) != 1:
            continue
        others = [o for o in v.legs if o != name]
        if sum(by[o].mass for o in others) >= x.mass or (closed and any(o in gh.PARTON_NAMES for o in others)):
            continue
        colour = _colour_factor(x.colour, [by[o].colour for o in others]) or 1.0
        width = two_body_width(v, v.legs.index(name), [by[o].mass for o in v.legs], colour)
        width *= 0.5 if others[0] == others[1] else 1.0
        if width <= 0:
            continue
        if set(others) <= set(dm):
            key = "invisible"
        elif set(others) <= STANDARD and channel_name(*others) in COLUMNS:
            key = channel_name(*others)
        else:
            return None
        widths[key] = widths.get(key, 0.0) + width
    if name in higgs_like_states and widths.get("b", 0) > 0 and x.mass > 10.0:
        for key, width in _loop_widths(x.mass, by["b"].mass, widths["b"]).items():
            if key in COLUMNS:                         # gg; γγ and Zγ (≈ 0.2%) have no shower column
                widths[key] = widths.get(key, 0.0) + width
    total = sum(widths.values())
    if total <= 0:
        return None
    return [Decay(channel=k, branching=w / total) for k, w in widths.items()]


def cascade(mb, rules, model, channel: str):
    """The two-body photon topology of a channel the PPPC table lacks (``spectra.Component``), or None."""
    from adroit.constraints.spectra import Component, Daughter
    names = channel.split(" ") if " " in channel else {"Zh": ["Z", "h"]}.get(channel)
    if not names or len(names) != 2:
        return None
    dm = dark_pair(mb)
    daughters = []
    for n in names:
        if n not in model.particles:
            return None
        if n in STANDARD:
            if n not in SINGLE:
                return None
            daughters.append(Daughter(mass_gev=model.particles[n].mass, channel=SINGLE[n]))
            continue
        found = decays(rules, n, dm, frozenset(higgs_like(mb)))
        if found is None:
            return None
        daughters.append(Daughter(mass_gev=model.particles[n].mass, decays=found))
    return Component(channel=channel, branching=1.0, mode="two_body", daughters=daughters)


def f_eff_range(mb, rules, model, channel: str) -> tuple[float, float] | None:
    """(lowest, highest) f_eff of a cascade (module docstring), or None."""
    from adroit.parameter_space.searches import F_EFF, NO_ENERGY, _f_eff, _first_tabulated
    component = cascade(mb, rules, model, channel)
    if component is None:
        return None
    m = model.particles[dark_pair(mb)[0]].mass
    (x, y) = component.daughters
    low = high = 0.0
    for d, other in ((x, y), (y, x)):
        energy = (4 * m * m + d.mass_gev ** 2 - other.mass_gev ** 2) / (4 * m)
        weight = energy / (2 * m)
        if d.channel:
            pieces = [(1.0, d.channel, energy, energy)]
        else:
            beta = math.sqrt(max(1 - (d.mass_gev / energy) ** 2, 0.0))
            pieces = [(dec.branching, dec.channel, 0.5 * energy * (1 - beta), 0.5 * energy * (1 + beta))
                      for dec in d.decays]
        for share, name, e_low, e_high in pieces:
            if name in NO_ENERGY:                           # neutrinos deposit nothing (the audit's G6-1, G12)
                continue
            floor = max(5.0, _first_tabulated(F_EFF.get(name, "")) or 5.0)       # the table's first mass
            values = [(_f_eff(e) or ({}, 0, 0))[0].get(F_EFF.get(name, ""), None)
                      for e in (max(e_low, floor), max(e_high, floor))]
            if any(v is None for v in values):
                return None
            low += weight * share * min(values)
            high += weight * share * max(values)
    return low, high


# --- long-range effects today ------------------------------------------------------------------------------------

def today_long_range(mb, rules) -> str:
    """Why annihilation today needs G8 (module docstring), or ""."""
    from adroit.parameter_space.portals import generic_checks as gc
    dm = mb.spectrum.dark_matter()
    names = list(dark_pair(mb))
    reps = [gc.representation(mb, n) for n in names]
    dark = gc._dark(rules, names)
    forces = gc._sm_forces(reps, dm.mass_gev, mb.gauge.spec.phase.value)
    forces += [lb.GaugeForce(group="U1", name=f"dark:{k}", alpha=a, mediator_gev=mass)
               for k, (a, mass, _) in dark["forces"].items()]
    if not forces:
        return ""
    pair = lb.PairRep(su2=(reps[0][0], reps[1][0]), su3=(reps[0][1], reps[1][1]),
                      charges=gc._pair_charges(reps, 0, 1, names, dark))
    channels = lb.channels(pair, forces)
    channels = [c for c in channels if c.su2 <= 5] or channels
    best = max(channels, key=lambda c: c.alpha)
    if best.alpha <= 0:
        return ""
    s = float(lb.sommerfeld_factor(best.alpha, np.array([TODAY_SPEED]), dm.mass_gev, best.mediator_gev)[0])
    if s <= 1 + TODAY_SHIFT:
        return ""
    return (f"needs the Sommerfeld effect today (G8): the dark matter's most attractive channel (α_eff = "
            f"{best.alpha:.3g}, mediator {best.mediator_gev:.3g} GeV) enhances annihilation at v = 10⁻⁴ by about "
            f"{s:.3g}")


def lines_flag(mb, rules) -> str:
    """A flag where loop-induced lines could matter: the dark matter carries gauge charge or couples to charged
    states."""
    dm = mb.spectrum.dark_matter()
    n, colour, y, _ = __import__("adroit.parameter_space.portals.generic_checks", fromlist=["representation"]) \
        .representation(mb, dm.name)
    by = {p.name: p for p in rules.particles} | {p.anti: p for p in rules.particles if p.anti}
    charged = any(dm.name in v.legs and any(by[x].charge != 0 for x in v.legs if x in by) for v in rules.vertices)
    if n > 1 or y or colour != "1" or charged:
        return "γ-ray lines are loop-induced and are not computed for the generic route (G8)"
    return ""
