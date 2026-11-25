"""Completing the model builder's proposals so that the engines can compute them (the owner, 2026-11-21).

The model builder proposes field contents, and the generator writes every term the symmetries allow with symbolic
couplings (``model_building.spec``). On its own that is not a model ADROIT can run. The owner's rule: only usable
models are offered (``library.personal.usable``), and a model may not be unusable for want of a coupling or a
parameter (the usable models plan). This module makes a generated model complete, deterministically, each
change stated in its assumptions:

- **Standard Model names** (``canonical_fields``): a flavour the builder names in its own way (``tauL``, ``tau_R``) is
  written as the engines name it (``Ltau``, ``tauR``), when its quantum numbers are that field's.
- **Standard Model currents** (``prepare``): the generator writes a vector's current on a Standard Model multiplet in
  two-component form (ψ†σ̄ψ, "chiral"); it is written as f̄γ^μf, which the generic route projects by the field's
  chirality. Its coupling stays a free symbol, so no sign is chosen.
- **A gauge U(1)'s currents** (``prepare``): the generator writes no current for a new U(1)'s gauge boson; here each
  charged field gets g_X Q_f f̄γ^μf X_μ (or the scalar current), with one gauge coupling g_X.
- **Values** (``finish``): the couplings the idea calls for take the values the model builder proposed (with its
  reasons), checked here: finite, and |g| ≤ √(4π) for a dimensionless one. Every other coupling is set to zero and its
  term left out, each named. A value outside the bound is not used: the coupling stays without a value, so the model is
  not offered, with the reason.
- **What cannot be written** (``finish``): the builder's own list, and any operator of dimension above 4 the idea
  names, go into the model's ``dropped`` list.
- **Flavour** (``finish``, ``universal``): a coupling on Q, uR, dR, L or eR applies alike to all three generations;
  each such coupling given a value says so in the assumptions.
- **Not offered** (``inert``, ``unreachable``): a model whose dark matter has no interaction left, or whose dark
  sector has no route to the Standard Model.

Numbers come from the model builder only as model inputs (masses, couplings), labelled as its proposals and shown at
review; no result is computed here.
"""

from __future__ import annotations

import math
import re
from fractions import Fraction

import sympy

from adroit.core.arithmetic import check_formula
from adroit.core.model_spec import FieldRole, ModelCoupling, ModelField, ModelSpec, ModelTerm, Occurrence
from adroit.model_building.content import snap
from adroit.model_building.gauge_basis import GaugeBasisError

PERTURBATIVE = math.sqrt(4 * math.pi)        # the bound on a dimensionless coupling's proposed value

# A flavour's name, written lower case without underscores → the engines' name, with the quantum numbers it must have
# (SU(3), SU(2), Y, chirality). The engines' names are G2's (``model_building.feynman.sm_names``).
_DOUBLET, _SINGLET = ("1", 2, -0.5, "L"), ("1", 1, -1.0, "R")
CANONICAL: dict[str, tuple[str, tuple]] = {
    **{alias: ("Le", _DOUBLET) for alias in ("el", "le", "l1")},
    **{alias: ("Lmu", _DOUBLET) for alias in ("mul", "lmu", "l2")},
    **{alias: ("Ltau", _DOUBLET) for alias in ("taul", "ltau", "l3")},
    "er": ("eR", _SINGLET), "mur": ("muR", _SINGLET), "taur": ("tauR", _SINGLET),
    "ur": ("uR", ("3", 1, 2 / 3, "R")), "dr": ("dR", ("3", 1, -1 / 3, "R")),
}
DIMENSION = re.compile(r"dimension[- ]?(\d+)|\bdim[- ]?(\d+)\b|\bd\s*=\s*(\d+)\b", re.I)
ZERO_NOTE = ("a benchmark choice: the idea does not call for it; technically natural only if a symmetry protects this "
             "zero (otherwise loops regenerate the term)")


def canonical_fields(fields: list[ModelField]) -> tuple[list[ModelField], list[str]]:
    """The builder's fields with each Standard Model flavour named as the engines name it, and the notes saying so.
    A name is changed only where every physical property agrees with the engines' field: its quantum numbers, its
    chirality (an empty one is filled in, and said), and for one flavour (Le, muR, …) one generation. A field that
    contradicts the name (tauL right-handed, or in three generations) keeps its own name and is judged as written
    (the auditor's UM-06: the rename had silently changed chirality and generations)."""
    taken = {f.name for f in fields}
    out, notes = [], []
    for f in fields:
        f = _one_mass(f, notes)
        found = CANONICAL.get(f.name.lower().replace("_", "")) if f.role is FieldRole.standard_model else None
        if found is None or found[0] == f.name or found[0] in taken:
            out.append(f)
            continue
        name, (su3, su2, y, chirality) = found
        c = f.charges
        one_flavour = name not in ("eR", "uR", "dR")
        if (f.spin != 0.5 or f.self_conjugate or c.su3 != su3 or c.su2 != su2 or abs(snap(c.hypercharge) - y) > 1e-9
                or f.chirality not in ("", chirality) or (one_flavour and f.generations != 1)):
            out.append(f)
            continue
        out.append(f.model_copy(update={"name": name, "chirality": chirality}))
        notes.append(f"{f.name} is written {name}, the name ADROIT's engines give this Standard Model field"
                     + ("" if f.chirality else f" (its chirality, not stated, is {chirality})"))
        taken.add(name)
    return out, notes


def _one_mass(f: ModelField, notes: list[str]) -> ModelField:
    """A new field the builder gave both ``mass_gev`` and per-generation ``masses_gev`` (L-10, 2026-11-21: the live
    gate's scotogenic N was refused, "states its mass twice"), with one of them kept and said: the per-generation masses
    where there are several; one mass where the two agree; none where they disagree, so the model is not offered (as a
    conflict of values is). A typed model's double statement is still refused (``generations``)."""
    if f.role is FieldRole.standard_model or f.mass_gev is None or not f.masses_gev:
        return f
    stated, each = f.mass_gev, list(f.masses_gev)
    if len(each) > 1:
        notes.append(f"{f.name} stated mass_gev = {stated:g} GeV and per-generation masses "
                     f"({', '.join(f'{m:g}' for m in each)} GeV): the per-generation masses are kept"
                     + (f", {stated:g} GeV being the lightest's" if math.isclose(stated, min(each), rel_tol=1e-9) else ""))
        return f.model_copy(update={"mass_gev": None})
    if math.isclose(stated, each[0], rel_tol=1e-9):
        notes.append(f"{f.name} stated its mass, {stated:g} GeV, twice: it is kept once")
        return f.model_copy(update={"masses_gev": None})
    notes.append(f"{f.name} stated two masses, {stated:g} and {each[0]:g} GeV: neither is used")
    return f.model_copy(update={"mass_gev": None, "masses_gev": None})


def _occurrences(vector: str, field: str) -> list[Occurrence]:
    return [Occurrence(field=vector), Occurrence(field=field, conjugate=True), Occurrence(field=field)]


def _sm_currents(spec: ModelSpec) -> ModelSpec:
    """Each generated two-component current V ψ†σ̄ψ of one Standard Model fermion, as V f̄γ^μf (module docstring)."""
    terms = []
    for t in spec.terms:
        names = [o.field for o in t.fields]
        fields = [spec.field(n) for n in names]
        sm = [f for f in fields if f.role is FieldRole.standard_model and f.spin == 0.5]
        vectors = [f for f in fields if f.spin == 1]
        if t.lorentz == "chiral" and len(names) == 3 and len(vectors) == 1 and len(sm) == 2 and sm[0].name == sm[1].name:
            v, f = vectors[0].name, sm[0].name
            t = t.model_copy(update={"fields": _occurrences(v, f), "lorentz": "vector",
                                     "text": f"{v}_μ {f}̄ γ^μ {f}"})
        terms.append(t)
    return spec.model_copy(update={"terms": terms})


def _exact(q: float) -> Fraction:
    """A charge ``snap`` has already read, exactly: the fraction it snapped to, or else the decimal as written (the auditor's
    UM-03: a second rounding had turned 0.01 into 0 and 0.02 into 1/90)."""
    near = Fraction(q).limit_denominator(36)
    return near if float(near) == q else Fraction(repr(q))


def _charge_formula(q: float, g: str) -> str:
    """g Q as a formula, Q exact (``_exact``)."""
    x = _exact(q)
    return g if x == 1 else f"-{g}" if x == -1 else f"({x})*{g}"


def _gauge_currents(spec: ModelSpec) -> tuple[ModelSpec, list[str]]:
    """Each new U(1)'s gauge currents from its fields' charges, with one gauge coupling (module docstring)."""
    groups = {k for f in spec.fields for k in f.charges.extra}
    vectors = sorted(f.name for f in spec.fields if f.spin == 1 and f.role is not FieldRole.standard_model
                     and f.name in groups)
    terms, couplings, notes = list(spec.terms), list(spec.couplings), []
    for x in vectors:
        g = f"g_{x}"
        added = []
        for f in spec.fields:
            q = snap(f.charges.extra.get(x, 0.0))
            if not q or f.spin == 1 or f.self_conjugate:
                continue
            # the fermion's current is +g Q f̄γf; ``scalar_current``'s coefficient k means D F = ∂F + i k X F
            # (``gauge_basis._current``), so the same covariant derivative D = ∂ − i g Q X, which gives the fermion's,
            # takes k = −g Q (the auditor's UM-04: +g Q had given a scalar the opposite sign to its hypercharge's)
            k = _charge_formula(q if f.spin == 0.5 else -q, g)
            lorentz = "vector" if f.spin == 0.5 else "scalar_current"
            shape = f"{f.name}̄ γ^μ {f.name}" if f.spin == 0.5 else f"{f.name}* i∂↔^μ {f.name}"
            added.append(ModelTerm(fields=_occurrences(x, f.name), lorentz=lorentz, coupling=k,
                                   text=f"{x}_μ {shape} (charge {_exact(q)})"))
        if added and g not in {c.name for c in couplings}:
            terms += added
            couplings.append(ModelCoupling(name=g, justification=f"the gauge coupling of {x}'s U(1)"))
            notes.append(f"{x} is the gauge boson of a new U(1): its currents g_{x} Q_f f̄γ^μf {x}_μ are written from "
                         "the fields' charges Q_f, with one gauge coupling; the U(1)'s anomaly cancellation is not "
                         "checked here")
    return spec.model_copy(update={"terms": terms, "couplings": couplings}), notes


def prepare(spec: ModelSpec) -> ModelSpec:
    """A generated model with its Standard Model currents in Dirac form and its gauge currents written: the couplings
    the model builder is then asked to give values to. Each change is in its assumptions."""
    spec = _sm_currents(spec)
    spec, notes = _gauge_currents(spec)
    return spec.model_copy(update={"assumptions": list(dict.fromkeys([*spec.assumptions, *notes]))})


def _vanishes(term: ModelTerm, zero: set[str]) -> bool:
    """Whether a term's coefficient is zero once the couplings ``zero`` are."""
    expr = sympy.sympify(check_formula(term.coupling))
    hit = {s: 0 for s in expr.free_symbols if str(s) in zero}
    return bool(hit) and sympy.simplify(expr.subs(hit)) == 0


def potential_couplings(spec: ModelSpec) -> set[str]:
    """The couplings that are the whole coefficient of pure-scalar terms only: the scalar potential's (L-1,
    2026-11-21). A model's coefficients are in L (``gauge_basis._scalar_term``: L ⊃ k P, so V ⊃ −k P), but a potential
    is quoted in V (V ⊃ λ₃|H|²|H₂|²): the builder had given the inert doublet's λs in V, every sign was reversed, and
    every proposal was a saddle. The values call asks for these in V and ``finish`` writes −λ in L."""
    by_name = {f.name: f for f in spec.fields}
    scalar = lambda t: t.lorentz == "scalar" and all(by_name[o.field].spin == 0 for o in t.fields)  # noqa: E731
    names = {t.coupling.strip() for t in spec.terms if scalar(t)}
    return {n for n in names if all(scalar(t) for t in spec.terms if n in re.findall(r"[A-Za-z_]\w*", t.coupling))}


def _value(c: ModelCoupling, proposed: tuple[float, str], in_v: bool = False) -> tuple[ModelCoupling, str]:
    """The coupling with its proposed value, or unchanged with the reason it is refused. ``in_v``: the builder gave a
    potential coefficient in V, so its coefficient in L is the opposite (``potential_couplings``)."""
    value, reason = proposed
    if not math.isfinite(value):
        return c, f"the value proposed for {c.name} is not a finite number"
    if c.mass_dimension == 0 and abs(value) > PERTURBATIVE:
        return c, f"the value {value:g} proposed for {c.name} exceeds the perturbative bound √(4π) ≈ 3.54"
    said = f"proposed by the model builder: {reason}".rstrip(": ")
    if in_v and value:
        said += f" (given in the potential, V ⊃ {value:g} × the term, so {-value:g} in L)"
    return c.model_copy(update={"value": -float(value) if in_v else float(value), "justification": said}), ""


def inert(spec: ModelSpec) -> str:
    """Why the model's dark matter has no interaction left ("" if it has one): no remaining term holds it and it
    carries no Standard Model gauge charge (an electroweak multiplet interacts through its gauge couplings)."""
    dm = [f for f in spec.fields if f.role is FieldRole.dark_matter]
    held = {o.field for t in spec.terms for o in t.fields}
    gauged = lambda f: f.charges.su3 != "1" or f.charges.su2 > 1 or f.charges.hypercharge or any(f.charges.extra.values())  # noqa: E731
    lost = [f.name for f in dm if f.name not in held and not gauged(f)]
    return (f"its dark matter ({', '.join(lost)}) has no interaction left: no coupling of it was given a value"
            if lost else "")


def _zero_at(term: ModelTerm, known: dict[str, float]) -> bool:
    """Whether the term's coefficient is zero at the model's values (every symbol it holds known)."""
    expr = sympy.sympify(check_formula(term.coupling))
    names = {str(s) for s in expr.free_symbols}
    # .is_zero, not == 0: SymPy's Float(0.0) does not equal its Integer 0
    return names <= known.keys() and bool(sympy.simplify(expr.subs({s: known[str(s)] for s in expr.free_symbols})).is_zero)


def unreachable(spec: ModelSpec) -> str:
    """Why the model's dark sector has no route to the Standard Model ("" if it has one; the live gate's L-5).

    Fields are joined by every remaining term whose coefficient is not zero at the model's values. The dark matter
    reaches the Standard Model when what it is joined to holds a Standard Model field or a field with a Standard Model
    gauge charge (an electroweak multiplet). A sector that reaches nothing has no process any constraint sees: a
    mediator whose Standard Model couplings were all zero, or a dark photon with no kinetic mixing. A zero-valued term
    joins nothing (the auditor's UM-01: a zero-valued current is not a coupling), and a new U(1)'s charge joins nothing by
    itself (the auditor's UO-01: with g = 0 the charges had still joined the sector to charged taus): no engine builds an
    interaction from ``charges.extra``, so a U(1)'s currents join fields only as the terms they are."""
    links: dict[str, set[str]] = {f.name: set() for f in spec.fields}
    known = {c.name: c.value for c in spec.couplings if c.value is not None}
    for t in spec.terms:
        if _zero_at(t, known):
            continue
        names = {o.field for o in t.fields} & links.keys()
        for n in names:
            links[n] |= names
    portal = spec.scalar_potential                        # a contract's Higgs portal λ_hs, outside the terms
    contracted = {portal.singlet_field} if portal is not None and portal.lambda_hs else set()
    for s in contracted & links.keys():
        if portal.higgs_field in links:
            links[s].add(portal.higgs_field)
            links[portal.higgs_field].add(s)
    by_name = {f.name: f for f in spec.fields}
    reaches = lambda f: (f.role is FieldRole.standard_model or f.charges.su3 != "1" or f.charges.su2 > 1  # noqa: E731
                         or bool(snap(f.charges.hypercharge))
                         or (f.name in contracted and portal.higgs_field not in links))
    dm = [f.name for f in spec.fields if f.role is FieldRole.dark_matter]
    seen, todo = set(dm), list(dm)
    while todo:
        for n in links[todo.pop()] - seen:
            seen.add(n)
            todo.append(n)
    if not dm or any(reaches(by_name[n]) for n in seen):
        return ""
    return (f"its dark sector ({', '.join(sorted(seen))}) has no route to the Standard Model: no remaining term joins it "
            "to a Standard Model field, and none of it carries a Standard Model charge, so no constraint sees it")


def universal(spec: ModelSpec, term: ModelTerm) -> list[str]:
    """The Standard Model fermions of ``term`` that come in several generations. The generator takes their flavour
    structure universal, so the term's one coupling applies to every generation alike (the live gate's L-4)."""
    by_name = {f.name: f for f in spec.fields}
    return [n for n in dict.fromkeys(o.field for o in term.fields)
            if n in by_name and by_name[n].role is FieldRole.standard_model and by_name[n].spin == 0.5
            and by_name[n].generations > 1]


def _universal_notes(spec: ModelSpec, kept: list[ModelTerm], couplings: list[ModelCoupling]) -> list[str]:
    """One statement per coupling with a non-zero value on a flavour-universal term: it applies to every generation."""
    value = {c.name: c.value for c in couplings}
    notes = []
    for t in kept:
        fields = universal(spec, t)
        for name in sorted(str(s) for s in sympy.sympify(check_formula(t.coupling)).free_symbols):
            if fields and value.get(name):
                notes.append(f"{name} = {value[name]:g} applies alike to all three generations of "
                             f"{' and '.join(fields)}: the model takes the Standard Model's flavour structure universal "
                             "(one coupling per structure)")
    return notes


def breaks_number(spec: ModelSpec, term: ModelTerm) -> str:
    """The complex new field whose number ``term`` changes, or "" (L-7, 2026-11-21: a complex singlet's builder had
    been offered H H* phi phi beside the portal H H* phi phi*, and the first splits phi into two real states that no
    interaction joins, two relics). Only a term in which one complex new field alone has a non-zero net count is named:
    phi₁ phi₂* may keep a combined number, so it is never called breaking."""
    by_name = {f.name: f for f in spec.fields}
    net: dict[str, int] = {}
    for o in term.fields:
        f = by_name.get(o.field)
        if f is not None and f.role is not FieldRole.standard_model and not f.self_conjugate and f.spin in (0, 0.5):
            net[o.field] = net.get(o.field, 0) + (-1 if o.conjugate else 1)
    moved = [n for n, k in net.items() if k]
    return moved[0] if len(moved) == 1 else ""


def _number_notes(spec: ModelSpec, kept: list[ModelTerm], couplings: list[ModelCoupling]) -> list[str]:
    """One statement per coupling with a non-zero value on a term that breaks a complex field's number."""
    value = {c.name: c.value for c in couplings}
    notes = []
    for t in kept:
        if not (field := breaks_number(spec, t)):
            continue
        for name in sorted(str(s) for s in sympy.sympify(check_formula(t.coupling)).free_symbols):
            if value.get(name):
                notes.append(f"{name} = {value[name]:g} breaks the number of {field}: its components are split in mass "
                             "and are separate particles, not one complex (Dirac) particle")
    return notes


PHYSICAL_TOLERANCE = 1e-7          # relative, on the dark matter's physical mass
PHYSICAL_STEPS = 40
SADDLE_CLIMBS = 12                 # doublings of the trial m² out of a saddle: up to about 4000 × m² (L-8)


def physical_mass(spec: ModelSpec) -> tuple[ModelSpec, list[str], list[str]]:
    """The builder's stated dark-matter mass read as the dark matter's physical mass (L-1, 2026-11-21): the generic
    route takes ``mass_gev`` as the Lagrangian mass (``gauge_basis``, "Masses as stated"), to which the Higgs adds
    λv²/2 and mixing adds more, whereas the builder, like a physicist naming "a 60 GeV inert doublet", states the
    physical mass. For a model only the generic route computes, the Lagrangian mass is solved so that the dark matter
    (the lightest neutral, colourless Z₂-odd state) has the stated mass at the proposed couplings: by fixed-point steps
    in m² for a scalar (the Higgs shifts m², and μ² may be smaller than m²) and in m for a fermion. Returns the model,
    its notes, and its problems (a physical mass no real Lagrangian mass gives). The library's own maps read the
    stated mass as physical already, and are left alone."""
    from adroit.model_building.spectrum import spectrum
    from adroit.parameter_space.classify import Unsupported, classify
    dark = [f for f in spec.fields if f.role is FieldRole.dark_matter and f.mass_gev and not f.vev_gev
            and f.spin in (0, 0.5) and not f.masses_gev]
    if len(dark) != 1:
        return spec, [], []
    f, target = dark[0], dark[0].mass_gev
    try:
        classify(spec, generic_route=False)              # a library map: it reads the stated mass as physical
        return spec, [], []
    except Unsupported:
        pass                                             # only the generic route (the classification itself had
    except (ValueError, ArithmeticError):                # failed on a saddle at the stated mass: L-8)
        return spec, [], []
    try:
        power = 2 if f.spin == 0 else 1
        x, climbs = target ** power, 0
        for _ in range(PHYSICAL_STEPS):
            trial = _with_mass(spec, f.name, x ** (1 / power))
            try:
                got = spectrum(trial).dark_matter().mass_gev
            except GaugeBasisError as error:
                if "saddle" not in str(error):
                    raise
                if climbs == SADDLE_CLIMBS:              # not the dark matter's own: its mass cannot lift it
                    return spec, [], [f"at these couplings {error}, whatever the Lagrangian mass of {f.name}"]
                climbs += 1                              # L-8: the trial mass was too low; raise it, then solve
                x = 2 * x + target ** power
                continue
            if abs(got - target) <= PHYSICAL_TOLERANCE * target:
                break
            x += target ** power - got ** power
            if x <= 0:                                   # left without a mass, so not offered (as a conflict is)
                return _with_mass(spec, f.name, None), [], [
                    f"the dark matter's stated mass, {target:g} GeV, cannot be its physical mass at these couplings: "
                    f"{f.name}'s Lagrangian mass² would have to be negative, since the Higgs adds more than m² to it"]
        else:
            return _with_mass(spec, f.name, None), [], [
                f"the Lagrangian mass of {f.name} giving the dark matter {target:g} GeV was not found"]
    except (ValueError, ArithmeticError, Unsupported):
        return spec, [], []                              # the engine's own refusal is said by usable()
    if abs(x ** (1 / power) - target) <= PHYSICAL_TOLERANCE * target:
        return spec, [], []
    lagrangian = x ** (1 / power)
    return trial, [f"{f.name}'s stated mass, {target:g} GeV, is the dark matter's physical mass: its Lagrangian mass "
                   f"is {lagrangian:.6g} GeV at the proposed couplings, which the Higgs and mixing shift to {target:g} "
                   "GeV (changing a coupling changes the dark matter's mass)"], []


def _state_of(states, name: str, spin: float) -> float | None:
    """The mass of the physical state of ``spin`` with the largest weight on field ``name`` (Goldstones aside)."""
    weight = lambda s: sum(w for k, w in s.composition.items() if k == name or k.startswith(f"{name}["))  # noqa: E731
    found = [s for s in states.states if s.spin == spin and s.kind != "goldstone" and weight(s) > 0.5]
    return max(found, key=weight).mass_gev if found else None


def _higgses(spec: ModelSpec, vector: str) -> list[str]:
    """The new scalars with a vacuum value whose currents join ``vector``: the vacuum values the completion may scale.
    A Standard Model H is never among them, since the engine fixes its vacuum (the auditor's UO-07: its stated value had been
    multiplied to 10³⁴ GeV with no vector reaching the target)."""
    return sorted({o.field for t in spec.terms if t.lorentz == "scalar_current" and any(o.field == vector for o in t.fields)
                   for o in t.fields if spec.field(o.field).spin == 0 and spec.field(o.field).vev_gev
                   and spec.field(o.field).role is not FieldRole.standard_model})


UNSOLVED = "the stated masses could not be given together: "      # a completion failure, which blocks (UO-07)


def _own_quartic(spec: ModelSpec, name: str) -> ModelTerm | None:
    return next((t for t in spec.terms if len(t.fields) == 4 and all(o.field == name for o in t.fields)
                 and re.fullmatch(r"[A-Za-z_]\w*", t.coupling.strip())), None)


def vacuum_masses(spec: ModelSpec) -> tuple[ModelSpec, list[str], list[str], dict]:
    """The builder's stated masses where a vacuum value also gives them (L-2, 2026-11-21: seven dark-Higgs proposals
    were refused, a vector "stating its mass twice: mass_gev and a vacuum value it couples to").

    The idea names a Higgsed vector's mass, so it is kept, and the new vacuum values Higgsing it are scaled for it
    (m_V ∝ g q v). A scalar with a vacuum value takes its mass from the potential, so its stated mass is read as
    physical and its self-quartic (in V, ∝ m²/v²) solved for it. Every target is solved **together** (the auditor's UO-07:
    solved one after another, a later scalar had moved an earlier one, a 400 GeV scalar ending at 272 GeV, and an
    exhausted loop had still said it succeeded): each step computes the spectrum once and moves every vacuum value and
    quartic, until all the stated masses hold at once. A solve that does not converge, or a target no state carries,
    is a problem beginning ``UNSOLVED``, which blocks the model. Returns the model, its notes, its problems and the
    targets ({(field, spin): mass}) for the final check (``final_check``)."""
    from adroit.model_building.spectrum import spectrum
    notes: list[str] = []
    vectors, scalars, trial = {}, {}, spec
    for v in [f for f in spec.fields if f.spin == 1 and f.role is not FieldRole.standard_model and f.mass_gev]:
        if higgses := _higgses(spec, v.name):
            vectors[v.name] = (v.mass_gev, higgses)
            trial = _with_mass(trial, v.name, None)
    for s in [f for f in spec.fields if f.spin == 0 and f.role is not FieldRole.standard_model and f.vev_gev
              and f.mass_gev]:
        trial = _with_mass(trial, s.name, None)
        own = _own_quartic(spec, s.name)
        if own is None:
            notes.append(f"{s.name}'s stated mass, {s.mass_gev:g} GeV, is not used: a scalar with a vacuum value takes "
                         "its mass from the potential, and this one has no self-quartic to give it")
            continue
        c = next(c for c in spec.couplings if c.name == own.coupling.strip())
        k = c.value if c.value and c.value < 0 else -(s.mass_gev / s.vev_gev) ** 2 / 2   # V ⊃ λ|φ|⁴: m² = 2λv²
        scalars[s.name] = (s.mass_gev, c.name, k, None if "solved from" in c.justification else c.value)
    if not vectors and not scalars:
        return trial, notes, [], {}
    targets = {**{(n, 1): m for n, (m, _) in vectors.items()}, **{(n, 0): m for n, (m, *_) in scalars.items()}}
    k = {n: q for n, (_, _, q, _) in scalars.items()}
    try:
        for _ in range(PHYSICAL_STEPS):
            trial = _with_quartics(trial, scalars, k)
            states = spectrum(trial)
            got = {key: _state_of(states, *key) for key in targets}
            if missing := [n for (n, _), m in got.items() if not m]:
                return spec, notes, [UNSOLVED + f"no state of {', '.join(missing)} carries its stated mass (a zero "
                                     "gauge coupling, or a state mixed past recognition)"], targets
            if all(abs(got[key] - m) <= PHYSICAL_TOLERANCE * m for key, m in targets.items()):
                break
            scale = {h: m / got[(n, 1)] for n, (m, hs) in vectors.items() for h in hs}
            trial = trial.model_copy(update={"fields": [f.model_copy(update={"vev_gev": f.vev_gev * scale[f.name]})
                                                        if f.name in scale else f for f in trial.fields]})
            k = {n: k[n] * (m / got[(n, 0)]) ** 2 for n, (m, *_) in scalars.items()}
        else:
            far = max(targets, key=lambda key: abs(got[key] - targets[key]) / targets[key])
            return spec, notes, [UNSOLVED + f"after {PHYSICAL_STEPS} steps {far[0]} is at {got[far]:.6g} GeV, not "
                                 f"{targets[far]:g} GeV: at these couplings the states mix so that these masses may not be reachable "
                                 "together"], targets
    except (ValueError, ArithmeticError) as error:
        return spec, notes, [UNSOLVED + str(error)], targets
    for n, (m, hs) in vectors.items():
        said = ", ".join(f"{f.name} {f.vev_gev:.6g} GeV" for f in trial.fields if f.name in hs)
        notes.append(f"{n}'s stated mass, {m:g} GeV, comes from the vacuum: the vacuum values are set to {said} so that "
                     "g q v gives it at the proposed gauge coupling (the proposal had stated both)")
    for n, (m, name, _, proposed) in scalars.items():
        before = (f", replacing the builder's {-proposed:g}" if proposed is not None
                  and abs(proposed - k[n]) > 1e-9 * abs(k[n]) else "")
        notes.append(f"{n}'s stated mass, {m:g} GeV, is its physical mass: its self-coupling {name} = {-k[n]:.6g} in V "
                     f"(so {k[n]:.6g} in L) gives it with its vacuum value {trial.field(n).vev_gev:.6g} GeV{before}")
    return trial, notes, [], targets


def _with_quartics(spec: ModelSpec, scalars: dict, k: dict) -> ModelSpec:
    names = {name: n for n, (_, name, _, _) in scalars.items()}
    return spec.model_copy(update={"couplings": [
        c.model_copy(update={"value": k[names[c.name]], "justification": f"solved from {names[c.name]}'s stated mass, "
                             f"{scalars[names[c.name]][0]:g} GeV, and its vacuum value (L-2)"})
        if c.name in names else c for c in spec.couplings]})


def final_check(spec: ModelSpec, targets: dict, dark_mass: float | None) -> list[str]:
    """Every stated mass the completion solved, read again from the final model's own spectrum (UO-07: claims must come
    from the accepted values): [] where all hold within the tolerance, else one ``UNSOLVED`` problem naming each."""
    from adroit.model_building.spectrum import spectrum
    if not targets and dark_mass is None:
        return []
    try:
        states = spectrum(spec)
        got = {key: _state_of(states, *key) for key in targets}
        if dark_mass is not None:
            got[("the dark matter", None)] = states.dark_matter().mass_gev
            targets = {**targets, ("the dark matter", None): dark_mass}
    except (ValueError, ArithmeticError) as error:
        return [UNSOLVED + f"the final model's spectrum could not be computed: {error}"]
    off = [f"{n} is at {got[(n, s)]:.6g} GeV, not {m:g} GeV" if got[(n, s)] else f"no state of {n}"
           for (n, s), m in targets.items() if not got[(n, s)] or abs(got[(n, s)] - m) > PHYSICAL_TOLERANCE * 10 * m]
    return [UNSOLVED + "; ".join(off)] if off else []


def _seeded_quartics(spec: ModelSpec) -> dict[str, tuple[float, str]]:
    """A first value, in V, for the self-quartic of each scalar with a vacuum value and a stated mass: λ = m²/(2v²),
    which ``vacuum_masses`` then solves exactly. Without it, a quartic the builder left out would be zero and its term
    left out, and the stated mass could not be given."""
    out = {}
    for s in spec.fields:
        if s.spin == 0 and s.role is not FieldRole.standard_model and s.vev_gev and s.mass_gev:
            own = next((t for t in spec.terms if len(t.fields) == 4 and all(o.field == s.name for o in t.fields)
                        and re.fullmatch(r"[A-Za-z_]\w*", t.coupling.strip())), None)
            if own is not None:
                out[own.coupling.strip()] = ((s.mass_gev / s.vev_gev) ** 2 / 2,
                                             f"solved from {s.name}'s stated mass and vacuum value")
    return out


def _with_mass(spec: ModelSpec, name: str, mass: float | None) -> ModelSpec:
    return spec.model_copy(update={"fields": [f.model_copy(update={"mass_gev": mass}) if f.name == name else f
                                              for f in spec.fields]})


def dimension_flags(idea: str, said: list[str] = ()) -> list[str]:
    """An operator of dimension above 4 that the idea names: the model holds renormalizable terms only. A dimension a
    note already names is not said again (L-6)."""
    found = sorted({int(next(g for g in m.groups() if g)) for m in DIMENSION.finditer(idea or "")})
    named = {int(next(g for g in m.groups() if g)) for s in said for m in DIMENSION.finditer(s)}
    return [f"a dimension-{n} operator named in the idea: the model holds renormalizable terms only (dimension ≤ 4)"
            for n in found if n > 4 and n not in named]


_STOP = {"the", "and", "for", "from", "with", "that", "this", "into", "enter", "enters", "as", "its", "are",
         "per", "set", "sets", "only", "a", "an", "of", "in", "by", "to", "is", "be", "it", "or", "on"}
_NEGATIONS = {"not", "no", "never", "none", "without", "nor"}


def _words(note: str) -> set[str]:
    """A note's content words, numbers and negations kept (the auditor's UO-09: 100 and 200 keV, or a negated note and its
    opposite, had read alike)."""
    words = re.findall(r"[a-z]+|\d+(?:\.\d+)?", note.lower())
    return {w.rstrip("s") if w[0].isalpha() else w for w in words
            if (w in _NEGATIONS or w[0].isdigit() or (len(w) > 2 and w not in _STOP))}


def distinct(notes: list[str]) -> list[str]:
    """The notes with repeats merged (L-6, 2026-11-21: the two calls had said the same omission two or three ways,
    "Loop mass splitting" beside "Radiative charged-neutral mass splitting (~166 MeV)"), keeping the longer, which
    says more, in the first one's place. Two notes are one only where every content word, number and negation of the
    shorter is in the longer and both are negated or neither (the auditor's UO-09: "Electron coupling omitted" and "Muon
    coupling omitted" had merged at a 60% overlap); when unsure, both are kept."""
    kept: list[str] = []
    for note in (n.strip() for n in notes):
        if not note:
            continue
        mine = _words(note)
        for k, other in enumerate(kept):
            theirs = _words(other)
            small, large = (mine, theirs) if len(mine) <= len(theirs) else (theirs, mine)
            if note == other or (small and small <= large
                                 and bool(mine & _NEGATIONS) == bool(theirs & _NEGATIONS)):
                kept[k] = max(other, note, key=len)
                break
        else:
            kept.append(note)
    return kept


def finish(spec: ModelSpec, values: dict[str, tuple[float, str]], not_encoded: list[str],
           idea: str = "", conflicts: dict[str, list[float]] | None = None) -> tuple[ModelSpec, list[str]]:
    """The prepared model with the builder's values: the couplings it names take them (checked), every other coupling
    without a value is zero and its term left out (each stated), and what the model leaves out of the idea is in
    ``dropped``. Returns the model and the problems with the values (a refused value leaves its coupling empty; so does
    a conflict, two different values proposed for one coupling, which is never read as an omission: the auditor's UM-05)."""
    conflicts = conflicts or {}
    names = {c.name for c in spec.couplings}
    problems = [f"a value was proposed for {name}, which is not one of this model's couplings: it was not used"
                + (" (a mass is the proposal's own)" if name.lower().startswith(("m_", "mass")) else "")
                for name in values if name not in names]
    problems += [f"conflicting values were proposed for {name} ({', '.join(f'{x:g}' for x in xs)}): none was used"
                 for name, xs in conflicts.items()]
    couplings, zero = [], set()
    in_v = potential_couplings(spec)
    values = {**_seeded_quartics(spec), **values}      # a dark Higgs's quartic is kept, to be solved (L-2)
    for c in spec.couplings:
        if c.value is not None:
            couplings.append(c)
        elif c.name in conflicts:
            couplings.append(c)
        elif c.name in values:
            c, problem = _value(c, values[c.name], c.name in in_v)
            couplings.append(c)
            problems += [problem] * bool(problem)
        else:
            zero.add(c.name)
    kept, notes = [], []
    for t in spec.terms:
        if _vanishes(t, zero):
            notes.append(f"{t.text or t.coupling} is left out ({t.coupling} = 0): {ZERO_NOTE}")
        else:
            kept.append(t)
    used = {str(s) for t in kept for s in sympy.sympify(check_formula(t.coupling)).free_symbols}
    couplings = [c for c in couplings if c.name not in zero] + [          # a zero inside a term that remains
        c.model_copy(update={"value": 0.0, "justification": f"zero: {ZERO_NOTE}"})
        for c in spec.couplings if c.name in zero and c.name in used]
    said = distinct([*spec.dropped, *not_encoded])
    dropped = [*said, *dimension_flags(idea, said)]
    notes += _universal_notes(spec, kept, couplings) + _number_notes(spec, kept, couplings)
    done = spec.model_copy(update={"terms": kept, "couplings": couplings, "dropped": dropped,
                                   "assumptions": list(dict.fromkeys([*spec.assumptions, *notes]))})
    if any(c.value is None for c in done.couplings):
        return done, problems                            # incomplete: not offered, whatever its mass
    done, vacuum_notes, vacuum_problems, targets = vacuum_masses(done)
    if vacuum_problems:                                  # blocks (UO-07): no physical-mass solve on top of it
        return done, problems + vacuum_problems
    done, mass_notes, mass_problems = physical_mass(done)
    dark = next((f for f in done.fields if f.role is FieldRole.dark_matter), None)
    converted = dark is not None and any(n.startswith(f"{dark.name}'s stated mass") for n in mass_notes)
    checked = [] if mass_problems else final_check(done, targets, spec.field(dark.name).mass_gev if converted else None)
    return done.model_copy(update={"assumptions": list(dict.fromkeys([*done.assumptions, *vacuum_notes,
                                                                       *mass_notes]))}), \
        problems + mass_problems + checked
