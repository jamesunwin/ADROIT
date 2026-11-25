"""Deterministic checks of a typed model: gauge invariance, hermiticity, an anomaly flag (DM8).

They read ``ModelSpec`` terms field by field, so no formula is parsed:
- **Gauge invariance.** In each term the U(1) charges add to zero (Y above
  electroweak symmetry breaking, Q below it, and every new U(1)), the colour
  triality vanishes, an SU(2) singlet can be formed (an even number of
  half-integer-isospin multiplets) and no gauge charge stands alone. A
  self-conjugate field carries no U(1) charge.
- **Hermiticity.** A term whose fields are not their own conjugates needs
  "+ h.c.".
- **Anomalies (a flag, not a verdict).** For every new U(1), the anomaly
  coefficients of its chiral fermions, [X]³, gravity–X, [SU(3)]²X, [SU(2)]²X,
  [Y]²X and Y[X]², in the left-handed convention. Vector-like couplings (a
  Dirac field with one charge) cancel. Axial couplings of a new boson to
  Standard Model fermions written without chirality are flagged: anomaly
  freedom then needs new fermions, which can bring constraints of their own.

Flags for a freeze-out model (2026-10-01), reported but never stopping a run:
- **Stability.** Under the stated parity every term is even, the dark matter
  is odd, and no odd state is lighter than it.
- **Perturbativity.** A dimensionless coupling above √(4π) (above 4π for a
  scalar quartic) leaves the loop expansion out of control.
- **Validity of the contact interaction.** A mediator lighter than ten times
  the largest momentum transfer (xenon, 800 km/s) needs its propagator in
  direct detection; an s-channel mediator lighter than 4m_χ (twice the
  freeze-out energy 2m_χ), or a t-channel one lighter than 2m_χ, needs the
  full model at freeze-out.
- **Perturbative unitarity** of a massive vector with axial couplings: each
  fermion obeys m_f ≲ √(π/2) M/g_A (Kahlhoefer, Schmidt-Hoberg, Schwetz,
  Vogl, arXiv:1510.02110, eq. 2.8), with g_A the Feynman-rule coupling (twice
  the Lagrangian's for a Majorana field), and the model needs completing above
  √s ≈ π M²/(g_A² m_χ) (eq. 2.9).
"""

from __future__ import annotations

import math
from collections import Counter

from pydantic import Field

from adroit.core.model_spec import (HEAVY_QUARKS, STANDARD_MODEL_FIELDS, FieldRole, ModelField, ModelSpec,
                                    ModelTerm, Phase, sector)
from adroit.core.state import StrictModel
from adroit.library.interactions import derivation as dv

TRIALITY = {"1": 0, "3": 1, "3bar": -1, "8": 0}
DYNKIN_SU3 = {"1": 0.0, "3": 0.5, "3bar": 0.5, "8": 3.0}
DIM_SU3 = {"1": 1, "3": 3, "3bar": 3, "8": 8}
TOLERANCE = 1e-6                 # charges written to a few decimals (0.6666667 for 2/3) still sum to zero
XENON_MASS_GEV = 122.3                  # ¹³¹Xe
V_MAX = 800.0 / 299_792.458             # escape plus Earth speed, in units of c


class CheckReport(StrictModel):
    """What the deterministic checks found."""

    gauge: list[str] = Field(default_factory=list)
    hermiticity: list[str] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)
    coefficients: list[str] = Field(default_factory=list)
    stability: list[str] = Field(default_factory=list)
    perturbativity: list[str] = Field(default_factory=list)
    contact: list[str] = Field(default_factory=list)
    unitarity: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        """No gauge or hermiticity problem (anomalies and the freeze-out checks are flags)."""
        return not self.gauge and not self.hermiticity

    @property
    def flags(self) -> list[str]:
        """Everything flagged that does not stop a run."""
        return [*self.coefficients, *self.anomalies, *self.stability, *self.perturbativity, *self.contact,
                *self.unitarity]


def _label(term: ModelTerm) -> str:
    return term.text or " ".join(("†" if o.conjugate else "") + o.field for o in term.fields)


def _charge_sums(model: ModelSpec, term: ModelTerm) -> dict[str, float]:
    sums: Counter = Counter()
    for occurrence in term.fields:
        f = model.field(occurrence.field)
        sign = -1.0 if occurrence.conjugate else 1.0
        if model.phase is Phase.unbroken:
            sums["hypercharge Y"] += sign * f.charges.hypercharge
        else:
            sums["electric charge Q"] += sign * f.charges.electric_charge
        for name, value in f.charges.extra.items():
            sums[f"U(1) {name}"] += sign * value
    return dict(sums)


def _non_abelian(model: ModelSpec, term: ModelTerm) -> list[str]:
    fields = [(model.field(o.field), o.conjugate) for o in term.fields]
    problems = []
    triality = sum((-1 if conj else 1) * TRIALITY[f.charges.su3] for f, conj in fields)
    coloured = [f for f, _ in fields if f.charges.su3 != "1"]
    if triality % 3 or len(coloured) == 1:
        problems.append("colour: no singlet can be formed")
    if model.phase is Phase.unbroken:
        doublet_like = sum(1 for f, _ in fields if f.charges.su2 % 2 == 0)
        charged = [f for f, _ in fields if f.charges.su2 > 1]
        if doublet_like % 2 or len(charged) == 1:
            problems.append("SU(2): no singlet can be formed")
    return problems


FIELD_STRENGTH = ("dipole", "anapole", "charge_radius", "tensor", "other")   # through F_μν or its derivatives


def _minimal_coupling_problems(model: ModelSpec, term: ModelTerm) -> list[str]:
    """A photon or gluon in A_μ form couples only to fields carrying its charge."""
    fields = [model.field(o.field) for o in term.fields]
    out = []
    for f in fields:
        kind = sector(f) or (STANDARD_MODEL_FIELDS.get(f.name) if f.role is FieldRole.mediator else None)
        others = [g for g in fields if g is not f]
        if kind == "photon" and term.lorentz not in FIELD_STRENGTH and not any(
                abs(g.charges.electric_charge) > TOLERANCE or sector(g) in ("quark", "lepton") for g in others):
            out.append("the photon couples through A_μ only to charged fields; a neutral field needs F_μν "
                       "(a dipole, an anapole, a charge radius)")
        if kind == "gluon" and term.lorentz not in FIELD_STRENGTH and not any(
                g.charges.su3 != "1" or sector(g) == "quark" for g in others):
            out.append("the gluon couples through G_μ only to coloured fields")
    return out


def gauge_problems(model: ModelSpec) -> list[str]:
    """Every term that is not gauge invariant, and why."""
    out = []
    for f in model.fields:
        if f.self_conjugate and (any(abs(v) > TOLERANCE for v in f.charges.extra.values())
                                 or abs(f.charges.hypercharge) > TOLERANCE
                                 or abs(f.charges.electric_charge) > TOLERANCE):
            out.append(f"{f.name}: a self-conjugate field cannot carry a U(1) charge")
    for term in model.terms:
        sums = {k: v for k, v in _charge_sums(model, term).items() if abs(v) > TOLERANCE}
        reasons = ([f"{k} adds to {v:+g}" for k, v in sums.items()] + _non_abelian(model, term)
                   + _minimal_coupling_problems(model, term))
        if reasons:
            out.append(f"{_label(term)}: " + "; ".join(reasons))
    return out


def _canonical(model: ModelSpec, term: ModelTerm, flip: bool) -> Counter:
    out: Counter = Counter()
    for o in term.fields:
        conjugate = (not o.conjugate) if flip else o.conjugate
        out[(o.field, False if model.field(o.field).self_conjugate else conjugate)] += 1
    return out


def _chiral_bilinear(model: ModelSpec, term: ModelTerm) -> bool:
    """A chiral Yukawa or mass term of four-component fermions, ψ̄P_Rχ (times scalars): never its own conjugate. A
    current, ψ†σ̄ψ with a vector, is hermitian by itself and is not one."""
    fields = [model.field(o.field) for o in term.fields]
    fermions = [f for f in fields if f.spin == 0.5]
    return (term.lorentz == "chiral" and len(fermions) == 2 and not any(f.spin == 1 for f in fields)
            and not any(f.chirality for f in fermions))


def hermiticity_problems(model: ModelSpec) -> tuple[list[str], list[str]]:
    """(problems, notes): terms that need "+ h.c.", and terms where it doubles a hermitian term."""
    problems, notes = [], []
    for term in model.terms:
        # a chiral bilinear is never its own conjugate, whatever its fields: (ψ̄P_Rχ)† = χ̄P_Lψ (the audit loop's
        # AL4-13(a): y S χ̄P_Rχ without + h.c. had passed here, then been dropped by the gauge basis, which keeps only
        # the P_R part's h.c.)
        own = (_canonical(model, term, flip=False) == _canonical(model, term, flip=True)
               and not _chiral_bilinear(model, term))
        if not own and not term.plus_hc:
            problems.append(f"{_label(term)}: not hermitian as written; add + h.c.")
        if own and term.plus_hc:
            notes.append(f"{_label(term)}: + h.c. doubles a term that is already its own conjugate")
    return problems, notes


def _anomaly_sums(fermions: list[tuple[ModelField, float]], model: ModelSpec, name: str) -> dict[str, float]:
    sums: Counter = Counter()
    for f, x in fermions:
        sign = 1.0 if f.chirality == "L" else -1.0
        d3, d2, y = DIM_SU3[f.charges.su3], f.charges.su2, f.charges.hypercharge
        weight = sign * f.generations
        sums[f"[{name}]³"] += weight * d3 * d2 * x ** 3
        sums[f"gravity–{name}"] += weight * d3 * d2 * x
        sums[f"[SU(3)]²{name}"] += weight * DYNKIN_SU3[f.charges.su3] * d2 * x
        sums[f"[SU(2)]²{name}"] += weight * d3 * ((d2 ** 2 - 1) * d2 / 12.0) * x
        if model.phase is Phase.unbroken:
            sums[f"[Y]²{name}"] += weight * d3 * d2 * y * y * x
            sums[f"Y[{name}]²"] += weight * d3 * d2 * y * x * x
    return dict(sums)


def anomaly_flags(model: ModelSpec) -> list[str]:
    """Nonzero anomaly coefficients of each new U(1), and axial couplings that cannot be checked."""
    out = []
    names = sorted({n for f in model.fields for n in f.charges.extra})
    for name in names:
        fermions = [(f, f.charges.extra[name]) for f in model.fields
                    if f.spin == 0.5 and f.chirality and abs(f.charges.extra.get(name, 0.0)) > TOLERANCE]
        for anomaly, value in _anomaly_sums(fermions, model, name).items():
            if abs(value) > TOLERANCE:
                out.append(f"{anomaly} = {value:+g}: new fermions are needed to cancel it")
    for term in model.terms:
        sm = [model.field(o.field) for o in term.fields if model.field(o.field).role.value == "standard_model"]
        if "axial" in term.lorentz and any(f.spin == 0.5 and not f.chirality for f in sm):
            out.append(f"{_label(term)}: an axial coupling to Standard Model fermions is anomalous "
                       "unless the full model adds fermions (not checked: no chiral charges given)")
    return out


def coupling_value(model: ModelSpec, term: ModelTerm) -> float | None:
    """A term's coupling as a number, if its expression evaluates (else None)."""
    try:
        return dv.evaluate_expression(term.coupling, dv.symbol_table(model))
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def coefficient_flags(model: ModelSpec) -> list[str]:
    """Terms whose coupling is not an expression in known symbols (m_q stands for each quark's own mass)."""
    table = {**dv.symbol_table(model), "m_q": (1.0, 1), "m_f": (1.0, 1), "m_l": (1.0, 1)}
    out = []
    for term in model.terms:
        try:
            dv.evaluate_expression(term.coupling, table)
        except (ValueError, TypeError, ZeroDivisionError) as exc:
            out.append(f"{_label(term)}: its coupling {term.coupling!r} does not evaluate ({exc})")
    return out


def parities(model: ModelSpec) -> tuple[dict[str, int], list[str]]:
    """Each field's dark parity: Standard Model fields even; a new field left unstated is taken as even."""
    out, assumed = {}, []
    for f in model.fields:
        if f.dark_parity is not None:
            out[f.name] = f.dark_parity
        else:
            out[f.name] = 1
            if f.role is not FieldRole.standard_model:
                assumed.append(f.name)
    return out, assumed


def stability_flags(model: ModelSpec) -> list[str]:
    """Problems with the stated stabilising symmetry, or that none is stated."""
    dm = model.dark_matter
    if dm.dark_parity is None and not model.stability:
        return ["no stabilising symmetry stated: the dark matter's stability is assumed, not checked"]
    parity, assumed = parities(model)
    out = [f"{', '.join(assumed)}: no parity stated, taken as even"] if assumed else []
    if parity[dm.name] != -1:
        out.append(f"{dm.name}: the dark matter is not odd under the stated symmetry")
    for term in model.terms:
        if math.prod(parity[o.field] for o in term.fields) != 1:
            out.append(f"{_label(term)}: odd, so the stated parity is not a symmetry of the model and does not "
                       "protect the dark matter")
    lighter = [f.name for f in model.fields if parity[f.name] == -1 and f.name != dm.name
               and f.mass_gev is not None and dm.mass_gev is not None and f.mass_gev < dm.mass_gev]
    if lighter:
        out.append(f"{', '.join(lighter)}: odd and lighter than the dark matter, so stable instead")
    return out


def perturbativity_flags(model: ModelSpec) -> list[str]:
    """Dimensionless couplings above √(4π) (4π for a scalar quartic)."""
    out = []
    for c in model.couplings:
        if c.value is None or c.mass_dimension != 0:
            continue
        quartic = any(c.name in t.coupling and len(t.fields) == 4
                      and all(model.field(o.field).spin == 0.0 for o in t.fields) for t in model.terms)
        limit, label = (4 * math.pi, "4π") if quartic else (math.sqrt(4 * math.pi), "√(4π)")
        if abs(c.value) > limit:
            out.append(f"{c.name} = {c.value:g} exceeds {label}: the loop expansion is not under control")
    return out


def contact_flags(model: ModelSpec) -> list[str]:
    """Where integrating the mediators out (as the derivation does) fails."""
    m = model.dark_matter.mass_gev
    if m is None:
        return ["no dark matter mass: the contact interaction's validity is not checked"]
    q_max = 2.0 * m * XENON_MASS_GEV / (m + XENON_MASS_GEV) * V_MAX
    out = []
    for f in model.fields:
        if f.role is not FieldRole.mediator or f.mass_gev is None:
            continue
        if f.mass_gev < 10.0 * q_max:
            out.append(f"{f.name} ({f.mass_gev:g} GeV) is below 10 q_max = {10 * q_max:.3g} GeV: direct "
                       "detection needs its propagator, which a contact derivation drops")
        t_channel = f.dark_parity == -1
        floor = 2.0 * m if t_channel else 4.0 * m
        if f.mass_gev < floor:
            out.append(f"{f.name} ({f.mass_gev:g} GeV) is below {floor:g} GeV ({'2' if t_channel else '4'}m_χ): "
                       "the contact interaction does not hold at freeze-out (√s ≈ 2m_χ); the relic "
                       "density needs the mediator itself")
    return out


def _fermion_mass(model: ModelSpec, f: ModelField) -> float | None:
    if f.mass_gev is not None:
        return f.mass_gev
    if sector(f) == "quark":
        return HEAVY_QUARKS["t"] if f.name in ("q", "Q", "qL", "uR", "t") else HEAVY_QUARKS.get(f.name)
    return None


def unitarity_flags(model: ModelSpec) -> tuple[list[str], list[str]]:
    """(violations, notes) of perturbative unitarity for axial couplings of massive vectors."""
    out, notes = [], []
    for term in model.terms:
        vectors = [model.field(o.field) for o in term.fields
                   if model.field(o.field).spin == 1.0 and model.field(o.field).role is FieldRole.mediator]
        fermions = {model.field(o.field).name: model.field(o.field) for o in term.fields
                    if model.field(o.field).spin == 0.5}
        if not vectors or vectors[0].mass_gev is None or term.lorentz not in ("axial", "chiral") or not fermions:
            continue
        g = coupling_value(model, term)
        if g is None:
            continue
        mediator = vectors[0]
        for f in fermions.values():
            g_a = abs(g) * (0.5 if term.lorentz == "chiral" else 1.0) * (2.0 if f.self_conjugate else 1.0)
            mass = _fermion_mass(model, f)
            if mass is None or g_a == 0.0:
                continue
            bound = math.sqrt(math.pi / 2.0) * mediator.mass_gev / g_a
            if mass > bound:
                out.append(f"{_label(term)}: m_{f.name} = {mass:g} GeV exceeds √(π/2) M/g_A = {bound:.3g} GeV "
                           "(arXiv:1510.02110, eq. 2.8)")
            if f.role is FieldRole.dark_matter:
                notes.append(f"{_label(term)}: the model needs completing above √s ≈ π M²/(g_A² m_χ) = "
                             f"{math.pi * mediator.mass_gev ** 2 / (g_a ** 2 * mass):.3g} GeV (arXiv:1510.02110, eq. 2.9)")
    return out, notes


def check(model: ModelSpec) -> CheckReport:
    """All the checks: gauge and hermiticity (which stop a run), and the flags."""
    hermiticity, notes = hermiticity_problems(model)
    unitarity, unitarity_notes = unitarity_flags(model)
    return CheckReport(gauge=gauge_problems(model), hermiticity=hermiticity, coefficients=coefficient_flags(model),
                       anomalies=anomaly_flags(model), stability=stability_flags(model),
                       perturbativity=perturbativity_flags(model), contact=contact_flags(model),
                       unitarity=unitarity, notes=[*notes, *unitarity_notes])
