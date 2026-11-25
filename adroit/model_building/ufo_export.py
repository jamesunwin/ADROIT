"""A typed model's Feynman rules as a UFO model at one parameter point (G2, for MadDM: decision D3).

The model is self-contained: its Standard Model and its dark sector both come from G2's rules, so that mixing
(h with a singlet, Z with a Z′, the photon with a dark photon) is in every vertex. The particles carry MadGraph's
names and PDG codes for the Standard Model's states (e-, ve, u, a, Z, W+, g, H, …) and codes from 9000101 on for
the new states (``names``), each Dirac fermion oriented for MadGraph's fermion flow (``flipped``). The libraries every UFO model shares (``object_library``, ``function_library``,
``write_param_card``, ``propagators``) are copied from MadGraph's ``sm``.

**Conventions.** A UFO vertex lists the particles its fields create (``ufo_model._translate``, checked against
MadGraph at G3), so each of ADROIT's vertices is written conjugated, with a fermion pair as [ψ̄'s, ψ's] and a
derivative coupling's sign changed (``_created``). The Feynman rule is coupling × Lorentz × colour; ADROIT's rule is
i × V, so each UFO coupling is i times G2's:
- FFS, FFSS: Γ = c + ic₂γ⁵ = (c − ic₂)P_L + (c + ic₂)P_R becomes ProjM(2,1), ProjP(2,1);
- FFV: γ(c + c₂γ⁵) becomes Gamma(3,2,−1)ProjM(−1,1) with c − c₂ and Gamma(3,2,−1)ProjP(−1,1) with c + c₂;
- VSS: c(p₂ − p₃) becomes P(1,2) − P(1,3);
- VVS, VVSS: Metric(1,2); VVV: the standard antisymmetric structure;
- SSS, SSSS: 1.

Masses and widths are external parameters (blocks MASS and DECAY), so a param_card sets them. The couplings are
numbers, or, with ``external_couplings``, external parameters too (each coupling GC_n = GCR_n + i GCI_n, blocks
ADROITGCR and ADROITGCI, code n: ``coupling_settings``), so that a model's generated MadGraph process holds no point's
numbers and is reused across a scan (F1: written as numbers, the couplings change with every m_χ through the mixing
and g_s, and the process was regenerated at every point). MadGraph's SMINPUTS (aEWM1, Gf, aS) are kept for its own
bookkeeping only; nothing here depends on them.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from adroit.library.interactions.ufo import code_name
from adroit.model_building.feynman import MassVertex, Rules

SM_NAMES = {"e": ("e-", "e+", 11), "mu": ("mu-", "mu+", 13), "tau": ("ta-", "ta+", 15), "nu_e": ("ve", "ve~", 12),
            "nu_mu": ("vm", "vm~", 14), "nu_tau": ("vt", "vt~", 16), "d": ("d", "d~", 1), "u": ("u", "u~", 2),
            "s": ("s", "s~", 3), "c": ("c", "c~", 4), "b": ("b", "b~", 5), "t": ("t", "t~", 6),
            "g": ("g", "g", 21), "A": ("a", "a", 22), "Z": ("Z", "Z", 23), "W": ("W+", "W-", 24), "h": ("H", "H", 25)}
PDG_START = 9000101            # MadDM takes 9000001–9000004 for FeynRules' ghosts and skips them
COPIED = ("__init__.py", "object_library.py", "function_library.py", "write_param_card.py")
VVV = ("P(3,1)*Metric(1,2) - P(3,2)*Metric(1,2) - P(2,1)*Metric(1,3) + P(2,3)*Metric(1,3) + P(1,2)*Metric(2,3) "
       "- P(1,3)*Metric(2,3)")


def _identifier(name: str) -> str:
    """A Python identifier for a UFO name (MadGraph's own: + → __plus__, - → __minus__, ~ → __tilde__)."""
    out = name.replace("+", "__plus__").replace("-", "__minus__").replace("~", "__tilde__")
    out = re.sub(r"[^A-Za-z0-9_]", "_", out)
    return out if out[0].isalpha() else f"p_{out}"


def flipped(rules: Rules) -> set[str]:
    """The Dirac fermions written with their antiparticle as the UFO particle, so that every fermion vertex pairs a
    UFO antiparticle with a UFO particle (MadGraph's fermion flow).

    G1 calls the state with positive charge the particle, which need not carry the fermion number of the Standard
    Model fermion it couples to: Giacchino et al.'s partner Ψ⁺ in Ψ̄ P_R e S enters as two incoming particles. ADROIT's
    tree engine follows any flow; MadGraph does not. The Standard Model's fermions fix the orientation, which spreads
    through the fermion vertices. Raises ValueError where the vertices violate fermion number."""
    dirac = {p.name for p in rules.particles if p.anti and p.spin == 0.5}
    def base(x: str) -> str:
        return x[:-1] if x.endswith("~") and x[:-1] in dirac else x
    links: dict[str, list[tuple[str, int]]] = {}
    for v in rules.vertices:
        if v.kind not in ("FFS", "FFSS", "FFV"):
            continue
        a, b = v.legs[0], v.legs[1]
        if base(a) not in dirac or base(b) not in dirac:
            continue                                      # a Majorana leg imposes nothing
        need = 1 ^ (a != base(a)) ^ (b != base(b))       # flip(a) XOR flip(b) = need
        links.setdefault(base(a), []).append((base(b), need))
        links.setdefault(base(b), []).append((base(a), need))
    flip: dict[str, int] = {}
    order = sorted(dirac, key=lambda n: (n not in SM_NAMES, n))          # the SM first: they are never flipped
    for start in order:
        if start in flip:
            continue
        flip[start], stack = 0, [start]
        while stack:
            x = stack.pop()
            for y, need in links.get(x, []):
                if y not in flip:
                    flip[y] = flip[x] ^ need
                    stack.append(y)
                elif flip[y] != flip[x] ^ need:
                    raise ValueError(f"the fermion vertices of {x} and {y} violate fermion number: MadGraph cannot "
                                     "take the model")
    return {n for n, f in flip.items() if f and n not in SM_NAMES}


ORDERS = ("QCD", "QED")                  # the exported coupling orders (``coupling_orders.py``)


def coupling_order(v: MassVertex) -> dict[str, int]:
    """A vertex's coupling orders: QCD 1 for a gluon's three-point vertex (g_s), QED 1 for any other three-point or
    scalar vertex, and for a contact VVSS one power per boson, QCD for a gluon and QED otherwise (g g φφ* ∝ g_s²;
    the external audit of 2026-10-17 found it labelled QCD 1)."""
    if v.kind == "VVSS":
        gluons = sum(leg == "g" for leg in v.legs[:2])
        return {k: n for k, n in (("QCD", gluons), ("QED", 2 - gluons)) if n}
    return {"QCD": 1} if "g" in v.legs and v.kind in ("FFV", "VSS", "VVV") else {"QED": 1}


def names(rules: Rules) -> dict[str, tuple[str, str, int]]:
    """ADROIT's particle → (UFO name of the particle, UFO name of its antiparticle, PDG code). A ``flipped`` fermion
    is the UFO antiparticle (its UFO particle, named …bar, is ADROIT's antiparticle). New names are lower-case letters
    and digits (MadGraph's renaming breaks on a name such as phi(p0.667)) and distinct in lower case: MadGraph lower-cases a model's names on import, so a name with a capital is not found
    afterwards (MadDM's ``define darkmatter Np0``). A name longer than five characters gets a code, n1, n2, …
    (``ufo.code_name``: MadDM's output cuts longer ones)."""
    out, code = {}, PDG_START
    flip = flipped(rules)
    taken = {name.lower() for name, anti, _ in SM_NAMES.values()} | {anti.lower() for _, anti, _ in SM_NAMES.values()}
    for p in sorted(rules.particles, key=lambda x: (x.parity, x.name)):
        if p.name in SM_NAMES:
            out[p.name] = SM_NAMES[p.name]
            continue
        base = re.sub(r"[^a-z0-9]", "", p.name.replace("+", "p").replace("-", "m").replace("'", "q").lower())
        base = (base if base[:1].isalpha() else f"x{base}") + ("bar" if p.name in flip else "")
        while base in taken or f"{base}~" in taken:
            base += "x"
        base = code_name(base, "n", taken)
        taken |= {base, f"{base}~"}
        if not p.anti:
            out[p.name] = (base, base, code)
        else:
            out[p.name] = (f"{base}~", base, code) if p.name in flip else (base, f"{base}~", code)
        code += 1
    return out


def _leg(name: str, table: dict, by_anti: dict) -> str:
    """The UFO name of a leg (a particle, or an antiparticle ``x~``)."""
    if name in table:
        return table[name][0]
    return table[by_anti[name]][1]


CREATED = {"3": "3bar", "3bar": "3"}     # a field's representation → that of the particle it creates


def _colour(v: MassVertex, reps: list[str]) -> list[str]:
    """UFO colour structures over the legs' positions (1-based) from the created particles' representations
    (``CREATED``): 1, δ, T(a, i, j) with i the triplet's position and j the antitriplet's, as MadGraph's own models
    write them, f, or the triplet pair's {T^a, T^b} (two structures)."""
    coloured = [k + 1 for k, r in enumerate(reps) if r != "1"]
    if not coloured:
        return ["1"]
    octets = [k + 1 for k, r in enumerate(reps) if r == "8"]
    triplet = [k + 1 for k, r in enumerate(reps) if r == "3"]
    anti = [k + 1 for k, r in enumerate(reps) if r == "3bar"]
    if len(coloured) == 2:
        return [f"Identity({coloured[0]},{coloured[1]})"]
    if len(octets) == 1 and triplet and anti:
        return [f"T({octets[0]},{triplet[0]},{anti[0]})"]
    if len(octets) == 3:
        return [f"f({octets[0]},{octets[1]},{octets[2]})"]
    if len(octets) == 2 and triplet and anti:
        a, b, i, j = octets[0], octets[1], triplet[0], anti[0]
        return [f"T({a},{i},-1)*T({b},-1,{j})", f"T({b},{i},-1)*T({a},-1,{j})"]
    raise ValueError(f"no UFO colour structure for {v.kind} {v.legs} with representations {reps}")


def _lorentz(v: MassVertex) -> list[tuple[str, list[int], complex]]:
    """(structure, spins, UFO coupling = i × ADROIT's) of each Lorentz piece of a vertex."""
    i = 1j
    spins = {"S": 1, "F": 2, "V": 3}
    s = [spins[k] for k in v.kind]
    if v.kind in ("FFS", "FFSS"):
        return [("ProjM(2,1)", s, i * (v.c - 1j * v.c2)), ("ProjP(2,1)", s, i * (v.c + 1j * v.c2))]
    if v.kind == "FFV":
        return [("Gamma(3,2,-1)*ProjM(-1,1)", s, i * (v.c - v.c2)), ("Gamma(3,2,-1)*ProjP(-1,1)", s, i * (v.c + v.c2))]
    structure = {"SSS": "1", "SSSS": "1", "VSS": "P(1,2) - P(1,3)", "VVS": "Metric(1,2)", "VVSS": "Metric(1,2)",
                 "VVV": VVV}[v.kind]
    return [(structure, s, i * v.c)]


def _ufo_particle(rec, table) -> tuple[str, str, float, str]:
    """(UFO particle name, its antiname, charge, colour) of a record: conjugated for a ``flipped`` fermion."""
    name, anti, _ = table[rec.name]
    if name.endswith("~") and anti == name[:-1]:
        return anti, name, -rec.charge, {"3": "3bar", "3bar": "3"}.get(rec.colour, rec.colour)
    return name, anti, rec.charge, rec.colour


def _particle_text(rec, table) -> str:
    name, anti, charge, colour_rep = _ufo_particle(rec, table)
    code = table[rec.name][2]
    spin = int(2 * rec.spin + 1)
    colour = {"1": 1, "3": 3, "3bar": -3, "8": 8}[colour_rep]
    mass = f"M{_identifier(name)}" if rec.mass > 0 else "ZERO"
    width = f"W{_identifier(name)}" if rec.width > 0 else "ZERO"
    ident = _identifier(name)
    text = (f"\n{ident} = Particle(pdg_code = {code}, name = '{name}', antiname = '{anti}', spin = {spin},\n"
            f"    color = {colour}, mass = Param.{mass}, width = Param.{width}, texname = '{name}',\n"
            f"    antitexname = '{anti}', charge = {float(charge)!r}, GhostNumber = 0, LeptonNumber = 0, Y = 0)\n")
    return text + ("" if anti == name else f"{_identifier(anti)} = {ident}.anti()\n")


def _parameters(rules: Rules, table) -> str:
    out = ["from object_library import all_parameters, Parameter\n",
           "\nZERO = Parameter(name = 'ZERO', nature = 'internal', type = 'real', value = '0.0', texname = '0')\n"]
    for name, value, code in (("aEWM1", 132.50698, 1), ("Gf", 1.16637e-5, 2), ("aS", 0.118, 3)):
        out.append(f"\n{name} = Parameter(name = '{name}', nature = 'external', type = 'real', value = {value},\n"
                   f"    texname = '{name}', lhablock = 'SMINPUTS', lhacode = [ {code} ])\n")
    for rec in rules.particles:
        name, code = _ufo_particle(rec, table)[0], table[rec.name][2]
        for kind, value, block in (("M", rec.mass, "MASS"), ("W", rec.width, "DECAY")):
            if value > 0:
                ident = f"{kind}{_identifier(name)}"
                out.append(f"\n{ident} = Parameter(name = '{ident}', nature = 'external', type = 'real', "
                           f"value = {float(value)!r},\n    texname = '{ident}', lhablock = '{block}', lhacode = [ {code} ])\n")
    return "".join(out)


def _coupling_parameters(values: list[complex]) -> str:
    """Each coupling's real and imaginary parts as external parameters (``external_couplings``)."""
    out = []
    for n, c in enumerate(values, 1):
        for part, value, block in (("GCR", c.real, "ADROITGCR"), ("GCI", c.imag, "ADROITGCI")):
            out.append(f"\n{part}{n} = Parameter(name = '{part}{n}', nature = 'external', type = 'real', "
                       f"value = {float(value)!r},\n    texname = '{part}{n}', lhablock = '{block}', lhacode = [ {n} ])\n")
    return "".join(out)


def _fermion_order(v: MassVertex, dirac: set[str], flip: set[str]) -> MassVertex:
    """MadGraph's order for a fermion vertex, [UFO antiparticle, UFO particle, …] (``flipped`` fermions counted in
    the UFO's frame): the slots swapped where needed (Ψ̄_XΓΨ_Y = Ψ̄_YᶜΓ′Ψ_Xᶜ: a vector coupling changes sign, a
    scalar one does not)."""
    if v.kind not in ("FFS", "FFSS", "FFV"):
        return v
    def base(x: str) -> str:
        return x[:-1] if x.endswith("~") and x[:-1] in dirac else x
    def ufo_anti(x: str) -> bool:
        return (x != base(x)) != (base(x) in flip)
    def majorana(x: str) -> bool:
        return base(x) not in dirac
    first, second = v.legs[0], v.legs[1]
    if ufo_anti(first) or (majorana(first) and not ufo_anti(second)):
        return v                                          # [antiparticle or Majorana, particle or Majorana]
    if not majorana(first) and not majorana(second) and not ufo_anti(second):
        return v                                          # fermion number two: ``flipped`` refuses such a model
    return MassVertex(v.kind, (second, first) + v.legs[2:], -v.c if v.kind == "FFV" else v.c, v.c2, v.colour)


def _created(v: MassVertex, conj: dict[str, str]) -> MassVertex:
    """The vertex as the UFO lists it: the particles its fields create, the inverse of ``ufo_model._translate``.
    Every leg is conjugated, a fermion pair is listed [ψ̄'s, ψ's] = [conj B, conj A] for ADROIT's (A, B), and a
    derivative coupling (VSS, VVV) changes sign with the momenta. A particle–antiparticle pair of one species reads
    the same either way, which is why only vertices joining two species (a partner's Yukawa) showed the
    difference. The colour indices are the created particles' (a field in 3̄ creates a particle in 3), as UFO models
    write them (``_colour``); each generator T in a coupling's colour structure is −Tᵀ of ADROIT's field
    representation, the conjugate representation's, so the coupling takes a sign per T (``_vertex_files``). Until
    2026-10-17 the indices kept ADROIT's field representations: every colour-summed σ was the same (an equivalent
    representation), but MadGraph assigns an event's colour flow from the positions and could not for g q → φ χ
    ("failed to reduce to color indices"), a channel the complete tree-level production (R17-1) generates."""
    legs = [conj[x] for x in v.legs]
    if v.kind in ("FFS", "FFSS", "FFV"):
        legs[0], legs[1] = legs[1], legs[0]
    sign = -1 if v.kind in ("VSS", "VVV") else 1
    return MassVertex(v.kind, tuple(legs), sign * v.c, v.c2 if sign == 1 else -v.c2, v.colour)


def _vertex_files(rules: Rules, table, external: bool = False) -> tuple[str, str, str, list[complex]]:
    """lorentz.py, couplings.py and vertices.py."""
    reps = {p.name: p.colour for p in rules.particles}
    conj = {"3": "3bar", "3bar": "3", "8": "8", "1": "1"}
    reps |= {p.anti: conj[p.colour] for p in rules.particles if p.anti}
    by_anti = {p.anti: p.name for p in rules.particles if p.anti}
    lorentz, couplings, vertices, values = {}, [], [], []
    dirac = {p.name for p in rules.particles if p.anti and p.spin == 0.5}
    flip = flipped(rules)
    conj = {p.name: p.anti or p.name for p in rules.particles} | {p.anti: p.name for p in rules.particles if p.anti}
    for n, v in enumerate(_fermion_order(x, dirac, flip) for x in rules.vertices):
        order = [1, 0, *range(2, len(v.legs))] if v.kind in ("FFS", "FFSS", "FFV") else list(range(len(v.legs)))
        colours = _colour(v, [CREATED.get(reps[v.legs[k]], reps[v.legs[k]]) for k in order])
        v = _created(v, conj)
        pieces = _lorentz(v)
        cells = []
        for li, (structure, spins, value) in enumerate(pieces):
            key = (structure, tuple(spins))
            lorentz.setdefault(key, f"L{len(lorentz) + 1}")
            for ci, colour in enumerate(colours):
                cname = f"GC_{len(couplings) + 1}"
                orders = ", ".join(f"'{k}':{n}" for k, n in coupling_order(v).items())
                c = value * (-1) ** colour.count("T(")      # the conjugate representation's generators, −Tᵀ
                n_c = len(couplings) + 1
                number = f"GCR{n_c} + complex(0,1)*GCI{n_c}" if external else \
                    f"complex({float(c.real)!r},{float(c.imag)!r})"
                couplings.append(f"\n{cname} = Coupling(name = '{cname}', value = '{number}', order = {{{orders}}})\n")
                values.append(complex(c))
                cells.append(f"({ci},{li}):C.{cname}")
        legs = ", ".join(f"P.{_identifier(_leg(x, table, by_anti))}" for x in v.legs)
        lnames = ", ".join(f"L.{lorentz[(s, tuple(sp))]}" for s, sp, _ in pieces)
        cols = ", ".join(f"'{c}'" for c in colours)
        vertices.append(f"\nV_{n + 1} = Vertex(name = 'V_{n + 1}', particles = [ {legs} ], color = [ {cols} ],\n"
                        f"    lorentz = [ {lnames} ], couplings = {{{', '.join(cells)}}})\n")
    lorentz_text = "".join(f"\n{name} = Lorentz(name = '{name}', spins = {list(spins)}, structure = '{s}')\n"
                           for (s, spins), name in lorentz.items())
    return lorentz_text, "".join(couplings), "".join(vertices), values


def coupling_settings(rules: Rules) -> list[str]:
    """MadGraph's ``set`` lines giving a point's couplings to a UFO written with ``external_couplings`` (and so to the
    process generated from it): GC_n's real and imaginary parts, blocks ADROITGCR and ADROITGCI."""
    values = _vertex_files(rules, names(rules), True)[3]
    return [line for n, c in enumerate(values, 1)
            for line in (f"set ADROITGCR {n} {c.real:.17g}", f"set ADROITGCI {n} {c.imag:.17g}")]


def write(rules: Rules, out_dir: Path, model: str, sm_dir: Path | None = None,
          external_couplings: bool = False) -> Path:
    """The UFO model folder for the rules (module docstring); ``external_couplings``: each coupling an external
    parameter, its value at this point the parameter's default."""
    from adroit.core.config import get_settings
    from adroit.library.interactions.ufo import MG5
    sm = sm_dir or get_settings().tools_dir / MG5 / "models" / "sm"
    target = Path(out_dir) / model
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for name in COPIED:
        shutil.copy(sm / name, target / name)
    init = (target / "__init__.py").read_text().replace("gauge = [0, 1]", "gauge = [0]")   # unitary gauge only
    (target / "__init__.py").write_text(init)
    table = names(rules)
    lorentz, couplings, vertices, values = _vertex_files(rules, table, external_couplings)
    header = "# Written by ADROIT (G2) from a typed model's Feynman rules at one parameter point.\n"
    files = {
        "parameters.py": _parameters(rules, table) + (_coupling_parameters(values) if external_couplings else ""),
        "particles.py": "from __future__ import division\nfrom object_library import all_particles, Particle\n"
                        "import parameters as Param\n" + "".join(_particle_text(p, table) for p in rules.particles),
        "lorentz.py": "from object_library import all_lorentz, Lorentz\n" + lorentz,
        "couplings.py": "from object_library import all_couplings, Coupling\n" + couplings,
        "vertices.py": "from object_library import all_vertices, Vertex\nimport particles as P\nimport couplings as C\n"
                       "import lorentz as L\n" + vertices,
        "coupling_orders.py": "from object_library import all_orders, CouplingOrder\n"
                              "QCD = CouplingOrder(name = 'QCD', expansion_order = 99, hierarchy = 1)\n"
                              "QED = CouplingOrder(name = 'QED', expansion_order = 99, hierarchy = 2)\n",
    }
    for name, text in files.items():
        (target / name).write_text(header + text)
    return target
