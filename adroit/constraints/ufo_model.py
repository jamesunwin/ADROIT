"""A published UFO model as input to the tree engine (``tree``): any FeynRules model, evaluated at a point.

The UFO format (arXiv:1108.2040) is how the literature publishes a model's Feynman rules
(the inert doublet's, the 2HDM+a's, DMSimpt's, the MSSM's, ...). This module reads one at a parameter
point and turns its vertices into ``tree.Model``:
1. **Evaluation.** The model's parameters and couplings are evaluated in MadGraph's Python
   (``maddm.python``): at the given external parameters, else at an SLHA param card, else at the
   model's own values (``dump``).
2. **Translation** of the Lorentz structures the tree engine knows: scalar vertices ('1');
   P(v,a) − P(v,b) (VSS); Metric (VVS, VVSS); the triple-gauge structure (VVV); sums of
   Metric·Metric (VVVV); Identity, Gamma5, ProjM, ProjP (FFS); Gamma with ProjM/ProjP (FFV). The
   Feynman rule is the UFO coupling times its structure, so V = −i × the coupling (``tree``'s rule
   is i V). **A UFO vertex names the particles its fields create** (checked against MadGraph's matrix
   elements, G3: ``docs/g3_tree.md``), where the engine names those its fields annihilate: every name
   is conjugated, a derivative coupling changes sign, and in Γ_{2,1} position 2 is ψ̄ (``_translate``).
3. **Colour.** By default (as the UFO portal reads its models) gluons and coloured vertices other than
   a colour singlet or a quark pair with a colourless boson are dropped, and a quark is a colour
   multiplicity of 3. With ``full_colour`` every particle keeps its representation and every vertex
   its colour string, remapped to the engine's slots: gluons, squarks, gluinos.
4. **What is dropped,** and listed: Goldstone bosons and ghosts (the engine works in the unitary
   gauge; a UFO marks a Goldstone as ``goldstone`` or ``goldstoneboson``); structures the engine does
   not know. A Majorana fermion of negative mass (SLHA's convention) is rotated to positive mass,
   χ → iγ⁵χ, with its couplings (``_positive_masses``).

Widths of bosons and fermions are computed at tree level from the same vertices (``widths``).

**Trust.** A UFO model is Python: ``dump`` imports it and evaluates its expressions in
MadGraph's interpreter. UFO models in ``ADROIT_TOOLS_DIR`` are therefore trusted as code, like
every program there; the UFO portal reads only the packaged library's models
(``portals.ufo.MODEL_DIRS``). Install models only from the sources ``adroit setup`` lists.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from itertools import product
from dataclasses import replace
from pathlib import Path

import numpy as np

from adroit.core.config import child_environment
from adroit.constraints import tree

_DUMP = r"""
import cmath, importlib, json, sys
model_dir, overrides = sys.argv[1], json.loads(sys.argv[2])
sys.path[:0] = [model_dir, model_dir.rsplit('/', 1)[0]]
m = importlib.import_module(model_dir.rsplit('/', 1)[1])
ns = {'cmath': cmath, 'complex': complex, 'abs': abs}
for f in m.all_functions:
    ns[f.name] = eval('lambda %s: %s' % (','.join(f.arguments), f.expr), ns)
card, block = {}, None
for line in (open(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else []):
    words = line.split('#')[0].split()
    if not words: continue
    if words[0].upper() == 'BLOCK': block = words[1].upper(); continue
    if words[0].upper() == 'DECAY': card[('DECAY', (int(words[1]),))] = float(words[2]); continue
    try: card[(block, tuple(int(w) for w in words[:-1]))] = float(words[-1])
    except ValueError: pass
for p in m.all_parameters:
    if p.nature == 'external':
        key = (p.lhablock.upper(), tuple(p.lhacode))
        ns[p.name] = overrides.get(p.name, card.get(key, p.value))
    else:
        ns[p.name] = eval(p.value, ns)
def value(x):
    if isinstance(x, (int, float, complex)): return complex(x)
    return complex(ns[x.name]) if hasattr(x, 'name') else complex(eval(str(x), ns))
parts = []
for p in m.all_particles:
    parts.append(dict(name=p.name, anti=p.antiname, spin=p.spin, color=p.color, mass=value(p.mass).real,
                      width=value(p.width).real, pdg=p.pdg_code, charge=float(p.charge),
                      goldstone=bool(getattr(p, 'goldstone', False) or getattr(p, 'goldstoneboson', False)
                                     or getattr(p, 'GoldstoneBoson', False)),
                      ghost=p.spin < 0))
verts = []
for v in m.all_vertices:
    for (i, j), c in v.couplings.items():
        z = complex(eval(c.value, ns))
        verts.append(dict(particles=[p.name for p in v.particles], color=v.color[i], lorentz=v.lorentz[j].structure,
                          re=z.real, im=z.imag))
print(json.dumps(dict(particles=parts, vertices=verts)))
"""

VVV = ("P(3,1)*Metric(1,2) - P(3,2)*Metric(1,2) - P(2,1)*Metric(1,3) + P(2,3)*Metric(1,3) + P(1,2)*Metric(2,3)"
       " - P(1,3)*Metric(2,3)")


def dump(model_dir: Path, overrides: dict[str, float], param_card: Path | None = None) -> dict:
    """The model's particles and every vertex's coupling value, evaluated at ``overrides`` (by parameter name),
    else at an SLHA ``param_card`` (by block and code), else at the model's own values."""
    from adroit.constraints import maddm
    done = subprocess.run(maddm.offline([str(maddm.python()), "-c", _DUMP, str(model_dir), json.dumps(overrides),
                                         str(param_card or "")]),
                          capture_output=True, text=True, timeout=600, env=child_environment())
    if done.returncode:
        raise RuntimeError(done.stderr[-2000:])
    return json.loads(done.stdout)


def _spin(ufo_spin: int) -> float:
    return {1: 0.0, 2: 0.5, 3: 1.0}[ufo_spin]


def _fermion_matrix(structure: str) -> tuple[complex, complex] | None:
    """A + Bγ⁵ of a scalar-type spinor structure, as (A, B); None if it is not one."""
    terms = {"Identity(2,1)": (1, 0), "Gamma5(2,1)": (0, 1), "ProjM(2,1)": (0.5, -0.5), "ProjP(2,1)": (0.5, 0.5)}
    return _linear(structure, terms)


def _vector_matrix(structure: str) -> tuple[complex, complex] | None:
    """(a, b) of γ^μ(a + bγ⁵) from Gamma(3,2,1) and its products with ProjM, ProjP, Gamma5."""
    terms = {"Gamma(3,2,1)": (1, 0), "Gamma(3,2,-1)*ProjM(-1,1)": (0.5, -0.5),
             "Gamma(3,2,-1)*ProjP(-1,1)": (0.5, 0.5), "Gamma(3,2,-1)*Gamma5(-1,1)": (0, 1)}
    return _linear(structure, terms)


def _linear(structure: str, terms: dict[str, tuple[float, float]]) -> tuple[complex, complex] | None:
    total_a = total_b = 0.0
    text = structure.replace(" ", "")
    for sign, coefficient, name in re.findall(r"([+-]?)(\d*\.?\d*)\*?([A-Za-z0-9]+\([^)]*\)(?:\*[A-Za-z0-9]+\([^)]*\))?)",
                                              text):
        if name not in terms:
            return None
        factor = float(coefficient) if coefficient else 1.0
        factor = -factor if sign == "-" else factor
        a, b = terms[name]
        total_a += factor * a
        total_b += factor * b
    return total_a, total_b


def _vss(structure: str) -> tuple[int, int, int, float] | None:
    """P(v,a) − P(v,b) → (v, a, b, sign), particle positions 1-based."""
    found = re.fullmatch(r"\s*(-?)\s*P\((\d),(\d)\)\s*([+-])\s*P\((\d),(\d)\)\s*", structure)
    if not found:
        return None
    s1, v1, a, s2, v2, b = found.groups()
    if v1 != v2:
        return None
    first = -1.0 if s1 == "-" else 1.0
    second = 1.0 if s2 == "+" else -1.0
    if first == -second:                         # ±(P(v,a) − P(v,b))
        return int(v1), int(a), int(b), first
    return None


def to_model(data: dict, keep_colour: bool = False, full_colour: bool = False) -> tuple[tree.Model, list[str]]:
    """The tree engine's model of a UFO dump, and what was dropped (with the reason).

    By default (as the UFO portal reads its models) gluons and coloured vertices other than a colour-singlet
    or a quark pair with a colourless boson are dropped, and a quark is a colour multiplicity of 3. With
    ``full_colour`` every particle keeps its SU(3) representation and every vertex its colour structure,
    remapped to the engine's slot order (``tree_colour``): gluons, squarks, gluinos.
    """
    model = tree.Model({})
    dropped = []
    ignore = set()
    for p in data["particles"]:
        if p["goldstone"] or p["ghost"] or (full_colour and abs(p["color"]) not in (1, 3, 8)):
            ignore.add(p["name"])
            if not (p["goldstone"] or p["ghost"]):
                dropped.append(f"{p['name']}: colour {p['color']}")
            continue
        colour = {3: "3", -3: "3bar", 8: "8"}.get(p["color"], "1") if full_colour else "1"
        particle = tree.Particle(p["name"], _spin(p["spin"]), p["mass"], p["width"],
                                 anti=p["anti"] if p["anti"] != p["name"] else "",
                                 colours=3 if abs(p["color"]) == 3 else 1, pdg=p["pdg"],
                                 charge=p.get("charge", 0.0), colour=colour)
        model.particles[particle.name] = particle
    gluons = {p["name"] for p in data["particles"] if abs(p["color"]) == 8}
    for v in data["vertices"]:
        names = v["particles"]
        if ignore & set(names):
            continue
        if not full_colour and (gluons & set(names) or
                                (v["color"] not in ("1", "Identity(1,2)", "Identity(2,1)") and not keep_colour)):
            dropped.append(f"{' '.join(names)}: colour {v['color']}")
            continue
        c = -1j * complex(v["re"], v["im"])
        if abs(c) < 1e-15:
            continue
        found = _translate(names, v["lorentz"], c, model)
        if found is None:
            dropped.append(f"{' '.join(names)}: Lorentz structure {v['lorentz']}")
            continue
        vertex, slots = found
        if full_colour:
            vertex = replace(vertex, colour=_remap_colour(v["color"], slots))
        model.vertices.append(vertex)
    return _positive_masses(_merge(model), dropped), dropped


def _positive_masses(model: tree.Model, notes: list[str]) -> tree.Model:
    """A Majorana fermion of negative mass (SLHA's convention) rotated to positive mass, χ → iγ⁵χ.

    The mass term −½(−m)χ̄χ becomes −½ m χ̄χ, and each vertex picks up iγ⁵ on that leg: Γ → iγ⁵Γ where χ̄ stands
    (slot f̄), Γ → Γ iγ⁵ where χ stands (slot f). For FFS, c + ic₂γ⁵ → (−c₂) + i(c)γ⁵ on one leg and → −Γ on both;
    for FFV, γ^μ(a + bγ⁵) → γ^μ(−ib − iaγ⁵) as f̄, γ^μ(ib + iaγ⁵) as f, unchanged on both.
    """
    flipped = {name for name, p in model.particles.items() if p.spin == 0.5 and not p.anti and p.mass < 0}
    if not flipped:
        return model
    for name in flipped:
        model.particles[name] = replace(model.particles[name], mass=-model.particles[name].mass)
        notes.append(f"{name}: a negative Majorana mass, rotated to positive (χ → iγ⁵χ)")
    out = []
    for v in model.vertices:
        if v.kind not in ("FFS", "FFV", "FFSS"):
            out.append(v)
            continue
        bar_side, plain_side = v.legs[0] in flipped, v.legs[1] in flipped
        c, c2 = v.c, v.c2
        if bar_side and plain_side:
            c, c2 = (-c, -c2) if v.kind != "FFV" else (c, c2)
        elif bar_side:
            c, c2 = (-c2, c) if v.kind != "FFV" else (-1j * c2, -1j * c)
        elif plain_side:
            c, c2 = (-c2, c) if v.kind != "FFV" else (1j * c2, 1j * c)
        out.append(replace(v, c=c, c2=c2))
    model.vertices = out
    return model


def _remap_colour(structure: str, slots: list[int]) -> str:
    """A UFO colour string over particle positions, rewritten over the vertex's slots (positions 1-based)."""
    position_to_slot = {position + 1: slot + 1 for slot, position in enumerate(slots)}

    def renumber(match: re.Match) -> str:
        args = [int(x) for x in match.group(2).split(",")]
        return f"{match.group(1)}({','.join(str(position_to_slot.get(a, a)) for a in args)})"
    return re.sub(r"([A-Za-z]+)\(([-0-9,\s]+)\)", renumber, structure)


_PAIRING = {frozenset({(1, 2), (3, 4)}): 0, frozenset({(1, 3), (2, 4)}): 1, frozenset({(1, 4), (2, 3)}): 2}


def _metric_pairs(structure: str) -> tuple[complex, complex, complex] | None:
    """(c₁₂, c₁₃, c₁₄) of Σ c Metric(a,b)*Metric(c,d) over the three pairings of four vectors; None otherwise."""
    out = [0.0, 0.0, 0.0]
    text = structure.replace(" ", "")
    pattern = (r"([+-]?)(\d*\.?\d*)\*?\(?Metric\((\d),(\d)\)\*Metric\((\d),(\d)\)\)?(?:/(\d+\.?\d*))?")
    consumed = 0
    for found in re.finditer(pattern, text):
        sign, number, a, b, c, d, divisor = found.groups()
        key = frozenset({tuple(sorted((int(a), int(b)))), tuple(sorted((int(c), int(d))))})
        if key not in _PAIRING:
            return None
        value = (float(number) if number else 1.0) / (float(divisor) if divisor else 1.0)
        out[_PAIRING[key]] += -value if sign == "-" else value
        consumed += len(found.group(0))
    return None if consumed != len(text) else (out[0], out[1], out[2])


def _translate(names: list[str], structure: str, c: complex,
               model: tree.Model) -> tuple[tree.Vertex, list[int]] | None:
    """The engine's vertex for a UFO vertex, and the UFO positions (0-based) in its slot order; None if the
    Lorentz structure is not one the engine knows.

    **Reading a UFO vertex** (checked against MadGraph, ``docs/g3_tree.md``). A UFO vertex lists the particles
    its fields create, and P(μ, j) is particle j's momentum in that sense; the engine's legs are the particles
    its fields annihilate, with incoming momenta. So every name is conjugated, a derivative coupling (VSS, VVV)
    changes sign, and in a fermion bilinear Γ_{2,1} the field of position 2 is ψ̄ (the engine's slot f̄) and
    that of position 1 is ψ (slot f). For a Dirac particle–antiparticle vertex the two readings coincide (the
    UFO lists both a term and its conjugate); they differ for Majorana fermions, for fermion-number-violating
    pairs and for a derivative coupling of two real scalars.
    """
    spins = [model.particles[n].spin if n in model.particles else None for n in names]
    if None in spins:
        return None
    conj = [model.particles[n].conjugate for n in names]
    vectors = [i for i, s in enumerate(spins) if s == 1.0]
    fermions = [i for i, s in enumerate(spins) if s == 0.5]
    every = list(range(len(names)))
    if not vectors and not fermions and structure.strip() == "1":
        return tree.Vertex("SSS" if len(names) == 3 else "SSSS", tuple(conj), c), every
    if len(names) == 3 and len(vectors) == 1 and not fermions:
        parsed = _vss(structure)
        if parsed is None:
            return None
        v, a, b, sign = parsed
        slots = [v - 1, a - 1, b - 1]
        return tree.Vertex("VSS", tuple(conj[k] for k in slots), -sign * c), slots
    if len(vectors) == 2 and not fermions:
        found = re.fullmatch(r"\s*Metric\((\d),(\d)\)\s*", structure)
        if not found:
            return None
        i, j = int(found.group(1)) - 1, int(found.group(2)) - 1
        slots = [i, j, *[k for k in every if k not in (i, j)]]
        return tree.Vertex("VVS" if len(names) == 3 else "VVSS", tuple(conj[k] for k in slots), c), slots
    if len(vectors) == 3 and len(names) == 3:
        squashed = structure.replace(" ", "")
        if squashed == VVV.replace(" ", ""):
            return tree.Vertex("VVV", tuple(conj), -c), every
        if squashed == "-(" + VVV.replace(" ", "") + ")":
            return tree.Vertex("VVV", tuple(conj), c), every
        return None
    if len(vectors) == 4:
        pairs = _metric_pairs(structure)
        if pairs is None:
            return None
        return tree.Vertex("VVVV", tuple(conj), c * pairs[0], c * pairs[1], c * pairs[2]), every
    if len(fermions) == 2 and len(names) == 3 and fermions == [0, 1]:
        return _bilinear(spins, conj, structure, c)
    return None


def _bilinear(spins: list, conj: list[str], structure: str, c: complex) -> tuple[tree.Vertex, list[int]] | None:
    """``_translate`` for a fermion bilinear with a scalar or a vector (FFS, FFV): ψ̄ the field of position 2."""
    slots = [1, 0, 2]
    legs = tuple(conj[k] for k in slots)
    if spins[2] == 0.0:
        ab = _fermion_matrix(structure)
        if ab is None:
            return None
        a, b = c * ab[0], c * ab[1]
        return tree.Vertex("FFS", legs, a, -1j * b), slots      # A + Bγ⁵ = c + i c₂ γ⁵
    if spins[2] == 1.0:
        ab = _vector_matrix(structure)
        if ab is None:
            return None
        return tree.Vertex("FFV", legs, c * ab[0], c * ab[1]), slots
    return None


def _merge(model: tree.Model) -> tree.Model:
    """One vertex per leg set, kind and colour structure: couplings of the same structure add (a UFO splits them
    by order)."""
    merged: dict[tuple, tree.Vertex] = {}
    for v in model.vertices:
        key = (v.kind, v.legs, v.colour)
        if key in merged:
            old = merged[key]
            merged[key] = replace(old, c=old.c + v.c, c2=old.c2 + v.c2, c3=old.c3 + v.c3)
        else:
            merged[key] = v
    model.vertices = list(merged.values())
    return model


def widths(model: tree.Model, names: list[str], closed: frozenset[str] = frozenset()) -> dict[str, float]:
    """Tree-level widths (GeV) of the named particles, bosons or fermions, from every two-body decay the vertices
    allow; for those in ``closed``, none into a pair of quarks or gluons (their hadronic opening not reached:
    ``portals.ufo``, RY23-01)."""
    partons = {1, 2, 3, 4, 5, 6, 21}
    out = {}
    for name in names:
        x = model.particles[name]
        total = 0.0
        finals = list(model.particles.values())
        seen = set()
        for c in finals:
            for d in finals:
                key = tuple(sorted((c.name, d.name)))
                if key in seen or abs(c.mass) + abs(d.mass) >= abs(x.mass):
                    continue
                seen.add(key)
                if name in closed and abs(c.pdg) in partons and abs(d.pdg) in partons:
                    continue
                total += _two_body(model, x, c, d)
        out[name] = total
    return out


def _two_body(model: tree.Model, x: tree.Particle, c: tree.Particle, d: tree.Particle) -> float:
    """Γ(x → c d) at tree level from the vertices (x, c̄, d̄), at rest: summed over final and averaged over x's
    spins and colours; ½ for identical final particles."""
    found = model.find([x.name, c.conjugate, d.conjugate])
    m = x.mass
    k = math.sqrt(max((m * m - (c.mass + d.mass) ** 2) * (m * m - (c.mass - d.mass) ** 2), 0.0)) / (2 * m)
    if not found or k <= 0:
        return 0.0
    momenta = (np.array([[m, 0.0, 0.0, 0.0]]), np.array([[math.sqrt(k * k + c.mass ** 2), 0.0, 0.0, k]]),
               np.array([[math.sqrt(k * k + d.mass ** 2), 0.0, 0.0, -k]]))
    total = sum(_decay_squared(model, v, order, (x, c, d), momenta) for v, order in found)
    average = {1.0: 3.0, 0.5: 2.0, 0.0: 1.0}[x.spin]
    symmetry = 0.5 if c.name == d.name else 1.0
    return symmetry * total / average * k / (8.0 * math.pi * m * m)


def _states(particle: tree.Particle, momentum: np.ndarray) -> list:
    from adroit.constraints.amplitudes import polarisations
    if particle.spin == 0:
        return [None]
    if particle.spin == 0.5:
        return [0, 1]
    if particle.mass > 0 and np.linalg.norm(momentum[0, 1:]) == 0:
        return [np.array([[0.0, 1.0, 0.0, 0.0]]), np.array([[0.0, 0.0, 1.0, 0.0]]), np.array([[0.0, 0.0, 0.0, 1.0]])]
    return polarisations(momentum, particle.mass) if particle.mass > 0 else polarisations(momentum, 1.0)[:2]


def _decay_squared(model: tree.Model, v: tree.Vertex, order: tuple, legs: tuple, momenta: tuple) -> float:
    """Σ|M|² of one vertex for x → c d (legs (x, c, d), incoming names (x, c̄, d̄)), colour-summed."""
    from adroit.constraints import tree_colour
    from adroit.constraints.amplitudes import _BASIS, bar, spinor_u
    from adroit.constraints.processes import conjugate
    x, c, d = legs
    names = [x.name, c.conjugate, d.conjugate]
    reps = [model.particles[n].representation for n in v.legs]
    colour = float(np.sum(np.abs(tree_colour.vertex_tensor(v.colour, reps)) ** 2)) / tree_colour.DIMENSION[
        x.representation]
    incoming = [momenta[0], -momenta[1], -momenta[2]]
    states = [_states(p, mom) for p, mom in zip(legs, momenta)]
    total = 0.0
    for chosen in product(*states):
        if v.kind not in tree.FERMIONIC:
            leg = [tree.Leg(names[i], incoming[i], chosen[i] if legs[i].spin == 1 else None) for i in range(3)]
            total += float(np.abs(tree._vertex_value(v, [leg[order[i]] for i in range(3)], None))[0] ** 2)
            continue
        fermions = [i for i in range(3) if legs[i].spin == 0.5]
        start, end = fermions                              # the flow from the first fermion leg to the second
        reverse = v.legs[1] != names[start] or v.legs[0] != names[end]
        spinor = [spinor_u(mom[:, 1:], p.mass, _BASIS[s]) if p.spin == 0.5 else None
                  for p, mom, s in zip(legs, momenta, chosen)]
        psi = spinor[start] if start == 0 else conjugate(spinor[start])
        psibar = bar(spinor[end])
        boson = next(i for i in range(3) if i not in fermions)
        gamma = tree._fermion_gamma(v, chosen[boson] if legs[boson].spin == 1 else None, reverse)
        total += float(np.abs(np.einsum("ni,nij,nj->n", psibar, gamma, psi))[0] ** 2)
    return colour * total


