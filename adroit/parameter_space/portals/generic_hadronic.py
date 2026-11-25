"""The hadronic window on the generic route (the owner's decision, 2026-10-20; ``constraints.hadronic_window``).

**The current is classified, not the mediator's spin.** A hadronic rate is computed with free quarks only above the
window's top, 2 GeV for a pure vector current and 3 GeV (inclusive) for any other or unclassified one:

- **An annihilation** (``annihilation_vector``) is through a pure vector current only where no vertex joins either
  initial state directly to a quark or gluon (a t-channel exchange or a contact operator: unclassified) and, of the
  bosons X joining the pair to quarks, none has an axial or spin-0 quark coupling (a mixed current is not vector:
  RC21-02) and the vector part, taken coherently at the pair's threshold s₀ = (m_a + m_b)²,
  Σ_X g_abX v_qX / (s₀ − m_X² + i m_X Γ_X) for each quark pair and each structure of the pair's vertex, does not
  cancel (C21-03). The energy is the threshold m_a + m_b (2m_χ for the dark
  matter: the threshold approximation), and the opening is 2m_π for every current here (conservative; G2's tables
  open quarks and gluons from 2m_π, ``generic._table``).
- **A decaying boson** (``decay_current``) is vector where it has spin 1 and every quark coupling's axial part is at
  most ``VECTOR_PURITY`` of its vector part, CP-odd (opening 3m_π) where it has spin 0 and pseudoscalar quark
  couplings only.

**Where the window applies.** A pair of the bath (the dark matter and the states within ``generic.BATH``) annihilating
into quarks or gluons at a threshold in the window refuses Ωh² (``annihilation_reason``), and the dark-matter pair's
today's quark and gluon rates are not computed (``today_partons``). A new neutral, colourless Z₂-even boson in its
window with an open quark or gluon decay has an uncomputed hadronic width, bounded by 0 ≤ Γ_had ≤ m_X (``windowed``):
Ωh² is refused where that range can move an s-channel propagator at a bath pair's threshold or above
(``hadronic_window.propagator_insensitive``); annihilation today is not computed at all where it moves the
propagator at s = 4m_χ² (diagrams may interfere, so there is no one-sided bound); its cascades are not computed
(``generic_id.decays``); and the portrait's width and branching fractions are bounds (``generic_portrait``). Purely
leptonic and photonic channels are computed as before. Everything here reads G2's rules (``feynman.Rules``).
"""
from __future__ import annotations

from collections import Counter

from adroit.constraints import hadronic_window as hw

QUARK_NAMES = frozenset({q for f in "udscbt" for q in (f, f"{f}~")})
PARTON_NAMES = QUARK_NAMES | {"g"}
STANDARD_BOSONS = frozenset({"A", "Z", "W", "W~", "g", "h"})


def _by(rules) -> dict:
    return {r.name: r for r in rules.particles} | {r.anti: r for r in rules.particles if r.anti}


def _direct(rules, a: str, b: str) -> bool:
    """Whether a vertex joins a or b directly to a quark or gluon (a t-channel exchange or a contact operator)."""
    return any((a in v.legs or b in v.legs) and any(leg in PARTON_NAMES for leg in v.legs) for v in rules.vertices)


def _bosons(rules, a: str, b: str) -> dict[str, float]:
    """Each boson X with a three-point vertex (a, b, X), with that vertex's |c| + |c₂|."""
    out: dict[str, float] = {}
    pair = Counter((a, b))
    for v in rules.vertices:
        legs = Counter(v.legs)
        if len(v.legs) == 3 and sum((legs & pair).values()) == 2:
            (x,) = legs - pair
            out[x] = out.get(x, 0.0) + abs(v.c) + abs(v.c2)
    return out


def _quark_parts(rules, x: str, spin: float) -> tuple[float, float, float]:
    """(vector, axial, scalar-like) parts of X's quark couplings: an FFV vertex's |c| and |c₂| (spin 1); an FFS
    vertex's |c| (the scalar part) for spin 0, with its |c₂| (pseudoscalar) as the second entry."""
    first = second = 0.0
    for v in rules.vertices:
        if len(v.legs) != 3 or v.legs.count(x) != 1 or not all(leg in QUARK_NAMES for leg in v.legs if leg != x):
            continue
        first, second = first + abs(v.c), second + abs(v.c2)
    return (first, second, 0.0) if spin == 1 else (0.0, second, first)


def _signed(v, x: str) -> tuple[tuple[str, str], complex, complex]:
    """(the pair, c, c₂) of a three-point vertex with X = ``x``, in one orientation: a vector coupling's sign flips
    with the order of a field and its antiparticle (ψ̄γψ and φ*∂φ are C-odd), an axial one's does not (as
    ``generic_portrait._portrait``), so the vector parts of different bosons add with their physical signs."""
    f1, f2 = (leg for leg in v.legs if leg != x) if v.legs.count(x) == 1 else (x, x)
    c, c2 = complex(v.c), complex(v.c2)
    if v.kind in ("FFV", "VSS") and not f1.endswith("~") and f2.endswith("~"):
        return (f2, f1), -c, c2
    return (f1, f2), c, c2


def annihilation_vector(rules, a: str, b: str) -> bool:
    """Whether the pair (a, b) annihilates into quarks through a pure vector current (module docstring).

    The vector part is coherent (C21-03): for each structure of the pair's vertex (its c and c₂) and each quark pair,
    V = Σ_X g_abX v_qX / (s₀ − m_X² + i m_X Γ_X), so vector amplitudes that cancel between bosons count as cancelled.
    Any other part, an axial quark coupling or a spin-0 boson's, makes the current mixed, not vector, however small
    its coupling (the owner: "mixed or unclassified cases should use the conservative refusal"): a ratio of couplings
    bounds no ratio of rates across Lorentz structures whose velocity dependence differs, an s-wave scalar or axial
    part outgrowing a p-wave vector one as v → 0 (the recheck's RC21-02, 2026-10-22: a 10⁻⁶ scalar coupling beside a
    0.01 vector one carried 98.7% of the rate today at 2.5 GeV). "Any" is above the rules' own resolution
    (``feynman.TOLERANCE`` of the whole). A dark-matter coupling's structure is not mistaken for the quarks'."""
    if _direct(rules, a, b):
        return False
    by = _by(rules)
    s0 = (by[a].mass + by[b].mass) ** 2
    pair = Counter((a, b))
    vector: dict[tuple, complex] = {}
    other = 0.0
    for v in rules.vertices:
        legs = Counter(v.legs)
        if len(v.legs) != 3 or sum((legs & pair).values()) != 2:
            continue
        (x,) = legs - pair
        _, g, g2 = _signed(v, x)
        mx, wx = by[x].mass, by[x].width
        propagator = complex(s0 - mx * mx, mx * wx)
        if abs(propagator) < 1e-300:
            return False
        for q in rules.vertices:
            if len(q.legs) != 3 or q.legs.count(x) != 1 or not all(leg in QUARK_NAMES for leg in q.legs if leg != x):
                continue
            quarks, c, c2 = _signed(q, x)
            for structure, gx in (("c", g), ("c2", g2)):
                if by[x].spin == 1:
                    key = (structure, quarks)
                    vector[key] = vector.get(key, 0j) + gx * c / propagator
                    other += abs(gx * c2 / propagator)
                else:
                    other += abs(gx) * (abs(c) + abs(c2)) / abs(propagator)
    from adroit.model_building.feynman import TOLERANCE
    coherent = sum(abs(z) for z in vector.values())
    return coherent > 0 and other <= TOLERANCE * (coherent + other)


def bath_pairs(mb, rules) -> list[tuple[str, str]]:
    """The dark-matter pair first, then every other pair of the relic's own bath, as (a, b) names. The species are
    the relic solver's (``generic.bath_states``: every odd state up to and including BATH × m_χ, with its conjugate),
    so every pair the solver integrates is one these checks see (the RV22 audit's RX22-01, 2026-10-22: this list had
    its own cut, strictly below BATH × m_χ, and a coloured partner at exactly 1.3 m_χ reached the solver unchecked)."""
    from adroit.parameter_space.portals.generic import bath_states
    dm = mb.spectrum.dark_matter()
    by = _by(rules)
    bath = sorted(bath_states(mb, rules), key=lambda s: (s[0].rstrip("~") != dm.name, s[1]))
    names = [name for name, _, _ in bath if name in by]
    first = (dm.name, dm.name if dm.kind in ("real", "majorana", "vector") else f"{dm.name}~")
    rest = [(x, y) for i, x in enumerate(names) for y in names[i:] if {x, y} != set(first)]
    return [first] + rest


def _window_reason(rules, model, a: str, b: str) -> str:
    """Why the pair's quark and gluon annihilation is not computed at its threshold, or ""."""
    from adroit.parameter_space.portals.generic import final_states
    by = _by(rules)
    root_s = by[a].mass + by[b].mass
    if root_s > hw.TOP:
        return ""
    vector = annihilation_vector(rules, a, b)
    if hw.state(root_s, vector=vector, annihilation=True) != hw.UNKNOWN:
        return ""
    if not any(c in PARTON_NAMES or d in PARTON_NAMES for c, d in final_states(model, a, b)):
        return ""
    return hw.annihilation_reason(root_s, vector, False)


def annihilation_reason(mb, rules, model) -> str:
    """Why Ωh² is not computed: a bath pair annihilating into quarks or gluons at its threshold in the window, or ""."""
    for a, b in bath_pairs(mb, rules):
        if why := _window_reason(rules, model, a, b):
            return why if (a, b) == bath_pairs(mb, rules)[0] else f"{why} ({a} {b}, coannihilating)"
    return ""


def coloured_bath_reason(mb, rules) -> str:
    """Why Ωh² is not computed: a bath pair with a coloured state whose threshold is at or below the window's top,
    3 GeV, where coloured states are confined into hadrons: the bath's free-parton rates, whatever their final states,
    do not establish theirs, and none is set to zero (the re-audit's RV22-01, 2026-10-22: a colour-triplet partner at
    0.12 GeV had an Ωh²; as the library's ``TChannel._coloured_bath``); or ""."""
    by = _by(rules)
    for a, b in bath_pairs(mb, rules):
        if (by[a].colour != "1" or by[b].colour != "1") and by[a].mass + by[b].mass <= hw.TOP:
            return (f"the coloured state's pair {a} {b} in the bath annihilates from √s = "
                    f"{by[a].mass + by[b].mass:.4g} GeV, at or below {hw.TOP:g} GeV, where coloured states are confined "
                    "into hadrons: the bath's free-parton rates do not establish them (ADROIT's hadronic-validity "
                    "policy); not computed")
    return ""


def today_closed(mb, rules) -> bool:
    """Whether the dark-matter pair's quark and gluon channels are closed today: its threshold below the hadronic
    opening, 2m_π for every annihilation current here (as Ωh²'s tables, ``generic._table``)."""
    by = _by(rules)
    a, b = bath_pairs(mb, rules)[0]
    return by[a].mass + by[b].mass < hw.opening(False)


def closed_decays(rules, x: str) -> bool:
    """Whether a candidate boson's quark and gluon decays are closed: its mass below its hadronic opening (2m_π; 3m_π
    for a CP-odd current). The portrait (``generic_portrait._hadronic``) and the cascades (``generic_id.decays``) both
    read it."""
    return candidate(_by(rules)[x]) and state(rules, x) == hw.CLOSED


def partonic_decays(rules, x: str) -> bool:
    """Whether X's quark and gluon decays are computed as free partons: a candidate boson's above its window, any other
    state's as before."""
    return not candidate(_by(rules)[x]) or state(rules, x) == hw.PARTONIC


def today_partons(mb, rules, model) -> str:
    """Why today's quark and gluon rates of the dark-matter pair are not computed (√s ≈ 2m_χ in the window), or ""."""
    return _window_reason(rules, model, *bath_pairs(mb, rules)[0])


def decay_current(rules, x: str) -> tuple[bool, bool]:
    """(vector, CP-odd) of a boson's quark current (module docstring)."""
    by = _by(rules)
    vector, axial, scalar = _quark_parts(rules, x, by[x].spin)
    if by[x].spin == 1:
        return vector > 0 and axial <= hw.VECTOR_PURITY * (vector + axial), False
    return False, axial > 0 and scalar <= hw.VECTOR_PURITY * axial


def candidate(record) -> bool:
    """A new neutral, colourless Z₂-even boson (the portraits' states)."""
    return record.parity == 1 and record.name not in STANDARD_BOSONS and record.spin in (0, 1) and \
        record.colour == "1" and abs(record.charge) < 1e-9 and record.mass > 0


def state(rules, x: str) -> str:
    """X's quark and gluon decays: ``hadronic_window.CLOSED``, ``UNKNOWN`` or ``PARTONIC`` at its mass."""
    vector, cp_odd = decay_current(rules, x)
    return hw.state(_by(rules)[x].mass, vector=vector, cp_odd=cp_odd)


def windowed(rules) -> dict[str, str]:
    """Each candidate boson in its hadronic window with an open quark or gluon decay, with why its hadronic width is
    not computed (``hadronic_window.decay_reason``)."""
    by = _by(rules)
    out = {}
    for r in rules.particles:
        if not candidate(r) or r.mass > hw.TOP or state(rules, r.name) != hw.UNKNOWN:
            continue
        opens = any(len(v.legs) == 3 and v.legs.count(r.name) == 1 and all(o in PARTON_NAMES for o in v.legs
                                                                              if o != r.name)
                    and sum(by[o].mass for o in v.legs if o != r.name) < r.mass for v in rules.vertices)
        if opens:
            vector, cp_odd = decay_current(rules, r.name)
            out[r.name] = hw.decay_reason(r.name, r.mass, vector, cp_odd)
    return out


def propagator_reason(mb, rules, fixed: bool = False) -> str:
    """Why a windowed boson's uncomputed width can move an s-channel propagator of a bath pair (at its threshold and
    above; at s = 4m_χ² alone for the dark matter today, ``fixed``), or ""."""
    unknown = windowed(rules)
    if not unknown:
        return ""
    by = _by(rules)
    pairs = bath_pairs(mb, rules)
    for a, b in pairs[:1] if fixed else pairs:
        s0 = (by[a].mass + by[b].mass) ** 2
        for x in _bosons(rules, a, b):
            mx = by[x].mass
            if x in unknown and not hw.propagator_insensitive(s0, mx, by[x].width + mx, fixed=fixed):
                return f"{unknown[x]}, and it moves the s-channel propagator of {a} {b} at √s ≥ {s0 ** 0.5:.4g} GeV"
    return ""
