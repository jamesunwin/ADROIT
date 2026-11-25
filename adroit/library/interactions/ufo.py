"""Model files in the UFO format from a ``ModelSpec`` (DM8's numerical cross-check).

UFO (arXiv:1108.2040) is the open Python format MadGraph and MadDM read. FeynRules,
which usually writes it, needs Mathematica, so ADROIT writes its own (the owner's
decision, 2026-10-01). The writer copies MadGraph's Standard Model (``models/sm`` of
the user's installation, never this repository) and adds a model's dark sector:

- **Particles.** One per new field: a Dirac fermion or complex scalar with its
  antiparticle, a Majorana fermion or real scalar as its own. Codes 9100001 on.
- **Parameters.** A mass (block MASS) and width (block DECAY, set to "auto" at run
  time) per new field, the dark matter's width zero; a parameter per coupling
  (block DMINPUTS). The u, d and s quarks get their masses and Higgs Yukawa
  couplings, so that couplings in proportion to m_q/v do not vanish.
- **Vertices.** One per term and flavour: i × the coupling as written in the
  Lagrangian × its Lorentz structure × the symmetry factor of identical fields (2
  for a Majorana bilinear or a pair of identical real scalars).

Terms: a fermion bilinear (scalar, pseudoscalar, vector, axial) with a scalar or
vector boson; a complex scalar's current with a vector; three scalars. Anything else
(dipoles, the anapole, derivative or higher-dimension operators, flavour-changing
terms, a model above electroweak symmetry breaking) is refused. Terms among Standard
Model fields only are taken from MadGraph's SM, with its sign conventions
(L ⊃ −(m_q/v) h q̄q).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from pydantic import Field

from adroit.core.config import get_settings
from adroit.core.model_spec import STANDARD_MODEL_FIELDS, ModelField, ModelSpec, ModelTerm
from adroit.core.state import StrictModel

MG5 = "mg5amcnlo-3.8.0"
PDG_START = 9100001
QUARKS = {"d": ("d", "MD", 1), "u": ("u", "MU", 2), "s": ("s", "MS", 3), "c": ("c", "MC", 4),
          "b": ("b", "MB", 5), "t": ("t", "MT", 6)}             # name → (MadGraph name, mass, PDG)
LIGHT = {"d": ("ymdown", 0.00467), "u": ("ymup", 0.00216), "s": ("ymstrange", 0.0934)}   # GeV, as derivation.py
GROUPS = {"q": "udscbt", "Q": "udscbt", "qL": "udscbt", "uR": "uct"}
SM_BOSONS = {"higgs": "H", "photon": "a", "z": "Z", "gluon": "g"}  # sector → UFO variable
SM_CONSTANTS = {"v": "vev", "e": "ee", "pi": "cmath.pi", "alpha": "aEW", "m_h": "MH", "m_Z": "MZ",
                "m_W": "MW", "G_F": "Gf", "sqrt": "cmath.sqrt", "exp": "cmath.exp", "log": "cmath.log",
                "abs": "abs", **{f"m_{q}": mass for q, (_, mass, _) in QUARKS.items()}}
_TOKEN = re.compile(r"\s*(?:(\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)|([A-Za-z][A-Za-z0-9_]*)|(\*\*|[-+*/()]))")
FERMION_LORENTZ = {("scalar", 0.0): ("Identity(2,1)", 1), ("pseudoscalar", 0.0): ("Gamma5(2,1)", -1),
                   ("vector", 1.0): ("Gamma(3,2,1)", 1), ("axial", 1.0): ("Gamma5(-1,1)*Gamma(3,2,-1)", 1)}


class UfoParticle(StrictModel):
    """A new particle, under its UFO (and MadGraph) name."""

    name: str
    pdg: int
    spin: int                              # 2s + 1
    self_conjugate: bool
    mass: str                              # a parameter name, or "ZERO"
    width: str


class UfoParameter(StrictModel):
    """An external parameter: its name, value, and block and code (MASS, DECAY or DMINPUTS)."""
    name: str
    value: float
    block: str
    code: int


class UfoVertex(StrictModel):
    """A vertex: its particles, colour structure, spins, Lorentz structure and coupling (a UFO expression)."""
    particles: list[str]                   # UFO variables, e.g. "P.dmchi__tilde__"
    color: str
    spins: list[int]
    structure: str
    coupling: str                          # a UFO expression
    order: str = "DMV"


class UfoExtension(StrictModel):
    """Everything the writer adds to MadGraph's Standard Model."""

    model: str
    names: dict[str, str] = Field(default_factory=dict)        # field → UFO name (new) or SM variable
    particles: list[UfoParticle] = Field(default_factory=list)
    parameters: list[UfoParameter] = Field(default_factory=list)
    vertices: list[UfoVertex] = Field(default_factory=list)


def _standard(field: ModelField) -> str | None:
    """The SM sector of a field by its name (a Higgs written as the mediator is still the Higgs)."""
    return STANDARD_MODEL_FIELDS.get(field.name) if field.role.value in ("standard_model", "mediator") else None


MADGRAPH_NAME_MAX = 5     # MadDM's maddm.out keeps 12 characters of "χχ̄_final" (2 × 5, "x", "_") and its parser needs the "_"


def code_name(name: str, prefix: str, taken: set[str]) -> str:
    """``name`` where MadGraph and MadDM carry it whole, else a short code: ``prefix`` and the first number not in
    ``taken`` (``MADGRAPH_NAME_MAX``). The code is the particle's name in MadGraph only; ADROIT keeps its own."""
    if len(name) <= MADGRAPH_NAME_MAX and name not in taken:
        return name
    k = 1
    while f"{prefix}{k}" in taken or f"{prefix}{k}~" in taken:
        k += 1
    return f"{prefix}{k}"


def _particles(spec: ModelSpec) -> tuple[list[UfoParticle], list[UfoParameter], dict[str, str]]:
    particles, parameters, names = [], [], {}
    dm = spec.dark_matter.name
    new = [f for f in spec.fields if _standard(f) is None and f.role.value != "standard_model"]
    for i, f in enumerate(new):
        name = code_name("dm" + re.sub(r"[^a-z0-9]", "", f.name.lower()), "dm", set(names.values()))
        if f.mass_gev is None:
            raise ValueError(f"{f.name}: a new field needs a mass for the UFO model")
        mass, width = f"M{name.upper()}", ("ZERO" if f.name == dm else f"W{name.upper()}")
        particles.append(UfoParticle(name=name, pdg=PDG_START + i, spin=int(2 * f.spin + 1),
                                     self_conjugate=f.self_conjugate, mass=mass, width=width))
        parameters.append(UfoParameter(name=mass, value=f.mass_gev, block="MASS", code=PDG_START + i))
        if width != "ZERO":
            parameters.append(UfoParameter(name=width, value=1.0, block="DECAY", code=PDG_START + i))
        names[f.name] = name
    parameters += [UfoParameter(name=f"dmc_{c.name}", value=c.value, block="DMINPUTS", code=i + 1)
                   for i, c in enumerate(spec.couplings) if c.value is not None]
    return particles, parameters, names


def expression(text: str, spec: ModelSpec, names: dict[str, str], quark: str | None = None) -> str:
    """A ModelSpec coupling in UFO's Python: couplings, masses and Standard Model constants renamed."""
    couplings = {c.name for c in spec.couplings}
    out, position, stripped = [], 0, text.strip()
    while position < len(stripped):
        match = _TOKEN.match(stripped, position)
        if not match or match.end() == position:
            raise ValueError(f"unexpected text in {text!r}")
        number, name, operator = match.groups()
        position = match.end()
        if name is None:
            out.append(number or operator)
        elif name in couplings:
            out.append(f"dmc_{name}")
        elif name in ("m_q", "m_f") and quark:
            out.append(QUARKS[quark][1])
        elif name.startswith("m_") and name[2:] in names:
            out.append(f"M{names[name[2:]].upper()}")
        elif name in SM_CONSTANTS:
            out.append(SM_CONSTANTS[name])
        else:
            raise ValueError(f"unknown symbol {name!r} in {text!r}")
    return "".join(out)


SM_FERMIONS = {**{q: (q, f"{q}__tilde__", "Identity(1,2)") for q in "udscbt"},
               "e": ("e__minus__", "e__plus__", "1"), "mu": ("mu__minus__", "mu__plus__", "1"),
               "tau": ("ta__minus__", "ta__plus__", "1"),
               **{n: (n, f"{n}__tilde__", "1") for n in ("ve", "vm", "vt")}}
SM_GROUPS = {**{g: tuple(q) for g, q in GROUPS.items()}, "l": ("e", "mu", "tau"), "L": ("e", "mu", "tau"),
             "lL": ("e", "mu", "tau"), "nu": ("ve", "vm", "vt"), "nu_e": ("ve",), "nu_mu": ("vm",),
             "nu_tau": ("vt",), **{f: (f,) for f in ("u", "d", "s", "c", "b", "t", "e", "mu", "tau")}}


def _boson(field: ModelField, names: dict[str, str]) -> str:
    if field.name in names:
        return f"P.{names[field.name]}"
    sector = _standard(field)
    if sector in SM_BOSONS:
        return f"P.{SM_BOSONS[sector]}"
    raise ValueError(f"{field.name}: no UFO boson for it")


def _label(term: ModelTerm) -> str:
    return term.text or " ".join(o.field for o in term.fields)


def _new_names(spec: ModelSpec) -> set[str]:
    return {f.name for f in spec.fields if _standard(f) is None and f.role.value != "standard_model"}


def _fermion_vertices(spec: ModelSpec, term: ModelTerm, names: dict[str, str]) -> list[UfoVertex]:
    fermions = [o.field for o in term.fields if spec.field(o.field).spin == 0.5]
    boson = next(spec.field(o.field) for o in term.fields if spec.field(o.field).spin != 0.5)
    if fermions[0] != fermions[1]:
        raise ValueError(f"{_label(term)}: flavour-changing terms are not written")
    if (term.lorentz, boson.spin) not in FERMION_LORENTZ:
        raise ValueError(f"{_label(term)}: a {term.lorentz} coupling to a spin-{boson.spin:g} boson is not written")
    if _standard(boson) in ("photon", "gluon") and spec.field(fermions[0]).name in _new_names(spec):
        raise ValueError(f"{_label(term)}: the {_standard(boson)} couples to a new neutral field only through "
                         "its field strength, which is not written")
    structure, phase = FERMION_LORENTZ[(term.lorentz, boson.spin)]
    spins, b, f = [2, 2, int(2 * boson.spin + 1)], _boson(boson, names), spec.field(fermions[0])
    factor = "complex(0,1)*" if phase == 1 else "-"
    if f.name in names:
        if f.self_conjugate and term.lorentz == "vector":
            raise ValueError(f"{_label(term)}: a Majorana field has no vector current")
        pair = ([f"P.{names[f.name]}"] * 2 if f.self_conjugate
                else [f"P.{names[f.name]}__tilde__", f"P.{names[f.name]}"])
        value = f"{factor}{2 if f.self_conjugate else 1}*({expression(term.coupling, spec, names)})"
        return [UfoVertex(particles=[*pair, b], color="1", spins=spins, structure=structure, coupling=value)]
    if f.name not in SM_GROUPS:
        raise ValueError(f"{f.name}: not a Standard Model fermion name the writer knows")
    out = []
    for flavour in SM_GROUPS[f.name]:
        particle, anti, color = SM_FERMIONS[flavour]
        value = f"{factor}1*({expression(term.coupling, spec, names, flavour if flavour in QUARKS else None)})"
        out.append(UfoVertex(particles=[f"P.{anti}", f"P.{particle}", b], color=color, spins=spins,
                             structure=structure, coupling=value))
    return out


def _scalar_vertices(spec: ModelSpec, term: ModelTerm, names: dict[str, str]) -> list[UfoVertex]:
    fields = [spec.field(o.field) for o in term.fields]
    scalars = [o for o in term.fields if spec.field(o.field).spin == 0.0]
    vectors = [f for f in fields if f.spin == 1.0]
    value = expression(term.coupling, spec, names)
    if len(vectors) == 1 and len(scalars) == 2:
        s = spec.field(scalars[0].field)
        if scalars[1].field != s.name or s.self_conjugate or s.name not in names:
            raise ValueError(f"{_label(term)}: a vector couples to a complex scalar's current only")
        parts = [_boson(vectors[0], names), f"P.{names[s.name]}__tilde__", f"P.{names[s.name]}"]
        return [UfoVertex(particles=parts, color="1", spins=[3, 1, 1], structure="P(1,3) - P(1,2)",
                          coupling=f"complex(0,1)*({value})")]
    if len(scalars) == 3:
        parts, factor = [], 1
        for name in {o.field for o in scalars}:
            f, count = spec.field(name), sum(o.field == name for o in scalars)
            factor *= 2 if (count == 2 and f.self_conjugate) else 6 if count == 3 and f.self_conjugate else 1
        for o in scalars:
            f = spec.field(o.field)
            anti = o.conjugate and not f.self_conjugate and f.name in names
            parts.append(f"P.{names[f.name]}__tilde__" if anti else
                         f"P.{names[f.name]}" if f.name in names else _boson(f, names))
        return [UfoVertex(particles=parts, color="1", spins=[1, 1, 1], structure="1",
                          coupling=f"complex(0,1)*{factor}*({value})")]
    raise ValueError(f"{_label(term)}: not a term the UFO writer handles")


def _light_quarks() -> tuple[list[UfoParameter], list[UfoVertex]]:
    """Masses and Higgs Yukawa couplings for u, d and s, which MadGraph's SM leaves massless."""
    parameters, vertices = [], []
    for q, (yukawa, mass) in LIGHT.items():
        name, mass_name, pdg = QUARKS[q]
        parameters += [UfoParameter(name=mass_name, value=mass, block="MASS", code=pdg),
                       UfoParameter(name=yukawa, value=mass, block="YUKAWA", code=pdg)]
        vertices.append(UfoVertex(particles=[f"P.{name}__tilde__", f"P.{name}", "P.H"], color="Identity(1,2)",
                                  spins=[2, 2, 1], structure="Identity(2,1)",
                                  coupling=f"-(complex(0,1)*{yukawa})/vev", order="QED"))
    return parameters, vertices


def extension(spec: ModelSpec) -> UfoExtension:
    """What the writer adds for this model (pure: no files)."""
    particles, parameters, names = _particles(spec)
    vertices = []
    for term in spec.terms:
        fields = [spec.field(o.field) for o in term.fields]
        if all(f.name not in names for f in fields):
            continue                                  # among Standard Model fields: MadGraph's SM has it
        if len(fields) != 3:
            raise ValueError(f"{_label(term)}: only three-field terms are written")
        writer = _fermion_vertices if sum(f.spin == 0.5 for f in fields) == 2 else _scalar_vertices
        vertices += writer(spec, term, names)
    light_parameters, light_vertices = _light_quarks()
    return UfoExtension(model="adroit_" + re.sub(r"[^A-Za-z0-9]", "_", spec.name), names=names,
                        particles=particles, parameters=parameters + light_parameters,
                        vertices=vertices + light_vertices)


def _particle_text(p: UfoParticle) -> str:
    anti = p.name if p.self_conjugate else f"{p.name}~"
    text = (f"\n{p.name} = Particle(pdg_code = {p.pdg}, name = '{p.name}', antiname = '{anti}', spin = {p.spin},\n"
            f"    color = 1, mass = Param.{p.mass}, width = Param.{p.width}, texname = '{p.name}',\n"
            f"    antitexname = '{anti}', charge = 0, GhostNumber = 0, LeptonNumber = 0, Y = 0)\n")
    return text + ("" if p.self_conjugate else f"{p.name}__tilde__ = {p.name}.anti()\n")


def _parameter_text(p: UfoParameter) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", p.name):      # written into Python source (AL2-11)
        raise ValueError(f"{p.name!r} cannot name a UFO parameter: it is not an identifier")
    return (f"\n{p.name} = Parameter(name = '{p.name}', nature = 'external', type = 'real', value = {p.value!r},\n"
            f"    texname = '{p.name}', lhablock = '{p.block}', lhacode = [ {p.code} ])\n")


def _vertex_texts(vertices: list[UfoVertex]) -> tuple[str, str, str]:
    lorentz, couplings, out = "", "", ""
    for i, v in enumerate(vertices):
        lorentz += (f"\nDM_L{i} = Lorentz(name = 'DM_L{i}', spins = {v.spins},\n"
                    f"    structure = '{v.structure}')\n")
        couplings += f"\nGC_DM_{i} = Coupling(name = 'GC_DM_{i}', value = '{v.coupling}', order = {{'{v.order}':1}})\n"
        out += (f"\nV_DM_{i} = Vertex(name = 'V_DM_{i}', particles = [ {', '.join(v.particles)} ],\n"
                f"    color = [ '{v.color}' ], lorentz = [ L.DM_L{i} ], couplings = {{(0,0):C.GC_DM_{i}}})\n")
    return lorentz, couplings, out


def _give_light_quarks_mass(particles_py: Path) -> None:
    text = particles_py.read_text()
    for q in LIGHT:
        block = re.search(rf"(?ms)^{q} = Particle\(.*?\)\n", text)
        text = text.replace(block.group(0), block.group(0).replace("mass = Param.ZERO", f"mass = Param.{QUARKS[q][1]}"))
    particles_py.write_text(text)


def write(spec: ModelSpec, out_dir: Path, sm_dir: Path | None = None) -> Path:
    """The UFO model folder for ``spec``: MadGraph's SM, copied, with the dark sector added."""
    ext = extension(spec)
    sm = sm_dir or get_settings().tools_dir / MG5 / "models" / "sm"
    target = Path(out_dir) / ext.model
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(sm, target, ignore=shutil.ignore_patterns("__pycache__", "*.pkl", "restrict_*.dat",
                                                              "build_restrict.py", "decays.py"))
    lorentz, couplings, vertices = _vertex_texts(ext.vertices)
    additions = {
        "parameters.py": "".join(map(_parameter_text, ext.parameters)),
        "particles.py": "".join(map(_particle_text, ext.particles)),
        "lorentz.py": lorentz, "couplings.py": couplings, "vertices.py": vertices,
        "coupling_orders.py": "\nDMV = CouplingOrder(name = 'DMV', expansion_order = 2, hierarchy = 2)\n",
    }
    for name, text in additions.items():
        path = target / name
        path.write_text(path.read_text() + f"\n# --- added by ADROIT for the model {spec.name!r} ---\n" + text)
    _give_light_quarks_mass(target / "particles.py")
    return target
