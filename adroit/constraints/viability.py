"""The viability checklist for thermal freeze-out dark matter (the owner's list, 2026-10-01).

Every item of ``data/viability.yaml`` gets a status for a given model, so that a
report never passes over a check in silence:

- **computed**: by the run itself, with its verdict (``orchestrator.checklist``);
- **undecided**: the run compared the item's constraints but none reached a verdict anywhere (a record awaiting
  verification, a model outside the search's benchmark, a channel mixture the search cannot bound); the reasons
  are given, and an undecided item neither excludes nor allows;
- **checked** or **flagged**: computed here (the model checks, or a pipeline
  step that ran), with what was found;
- **assumed**: a stated assumption (the cosmological history);
- **applies**: relevant to this model but not computed yet; the item says
  where it is to be built;
- **does not apply**: with the reason, read from the model's masses and
  couplings.

The rules are deliberately simple and stated with their thresholds; "does not
apply" is an estimate of relevance, never a calculation of a limit.
"""

from __future__ import annotations

import math
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Callable

import yaml
from pydantic import Field

from adroit.core.model_spec import STANDARD_COSMOLOGY, STANDARD_MODEL_FIELDS, FieldRole, ModelSpec, sector
from adroit.core.state import StrictModel
from adroit.library.interactions import model_checks

DATA = Path(__file__).with_name("data") / "viability.yaml"
M_W, M_Z, M_H, M_T = 80.37, 91.1876, 125.25, 172.5
B_TO_K_GEV = 5.2793 - 0.4937           # the heaviest state in B → K X
NEAR = 0.2                             # within 20%: a coannihilation partner, a resonance
WINDOW = 0.1                           # within 10% of a channel threshold
LIGHT_GEV = 1.0                        # stars and supernovae, the plasma, self-interactions
BEAM_DUMP_GEV = 3.0
BBN_GEV = 0.02
COLD_GEV = 1e-3
ALPHA_2 = 0.034                        # g²/4π of SU(2)_L
SIDM_NEGLIGIBLE = 0.01                 # cm²/g, ten times below the strongest bounds
GEV2_CM2, GEV_G = 3.8937938e-28, 1.78266192e-24
INDIVIDUAL = {"u", "d", "s", "c", "b", "t", "e", "mu", "tau", "nu_e", "nu_mu", "nu_tau"}


class Status(str, Enum):
    """An item's status for one model (see the module's text)."""
    computed = "computed"              # by a run: a constraint's verdict, the relic roots, a certificate (R8)
    undecided = "undecided"            # compared by the run, but no verdict at any point (each reason is given)
    checked = "checked"
    flagged = "flagged"
    assumed = "assumed"
    applies = "applies, not yet computed"
    not_applicable = "does not apply"


class Item(StrictModel):
    """One check of the list."""

    id: str
    group: str
    title: str
    check: str
    built: str
    planned: str


class Entry(StrictModel):
    """One item's status for one model."""

    id: str
    group: str
    title: str
    status: Status
    detail: str
    planned: str = ""


class Mediator(StrictModel):
    """A mediator as the rules read it: spin, mass (GeV), whether it is odd under the dark parity, and α = g²/4π of
    its coupling to the dark matter."""
    name: str
    spin: float
    mass_gev: float | None
    odd: bool
    alpha: float | None                # g²/4π of its Feynman-rule coupling to the dark matter


class Profile(StrictModel):
    """What the rules read from a model."""

    mass_gev: float | None
    su2: int = 1
    sectors: list[str] = Field(default_factory=list)
    flavour_specific: bool = False
    mediators: list[Mediator] = Field(default_factory=list)
    new_states: dict[str, float] = Field(default_factory=dict)       # every new field with a mass
    even_lighter: list[str] = Field(default_factory=list)            # new even states below m_χ
    partners: list[str] = Field(default_factory=list)                # odd states within NEAR above m_χ
    new_scalars: bool = False
    cosmology: str = STANDARD_COSMOLOGY
    relic_fraction: float = 1.0


@lru_cache(maxsize=1)
def _data() -> dict:
    return yaml.safe_load(DATA.read_text())


def items() -> list[Item]:
    """The checklist, in order."""
    return [Item.model_validate(i) for i in _data()["items"]]


def groups() -> dict[str, str]:
    """Group id → heading."""
    return dict(_data()["groups"])


def _alpha(spec: ModelSpec, mediator: str) -> float | None:
    dm = spec.dark_matter
    for term in spec.terms:
        names = [o.field for o in term.fields]
        spins = [spec.field(n).spin for n in names]
        yukawa_or_gauge = spins.count(0.5) == 2 or (spins.count(0.0) == 2 and spec.field(mediator).spin == 1.0)
        if dm.name in names and mediator in names and len(names) == 3 and yukawa_or_gauge:
            g = model_checks.coupling_value(spec, term)
            if g is not None:
                return (g * (2.0 if dm.self_conjugate else 1.0)) ** 2 / (4 * math.pi)
    return None


def _couplings_to_standard_model(spec: ModelSpec) -> tuple[list[str], bool]:
    found, specific = set(), False
    for term in spec.terms:
        fields = [spec.field(o.field) for o in term.fields]
        if all(f.role is FieldRole.standard_model for f in fields):
            continue
        sm = [f for f in fields if f.role is FieldRole.standard_model]
        found |= {sector(f) for f in sm}
        found |= {STANDARD_MODEL_FIELDS[f.name] for f in fields       # a Higgs or Z written as the mediator
                  if f.role is FieldRole.mediator and f.name in STANDARD_MODEL_FIELDS}
        fermions = {f.name for f in sm if f.spin == 0.5}
        specific |= bool(fermions & INDIVIDUAL) or len(fermions) > 1
    return sorted(s for s in found if s), specific


def profile(spec: ModelSpec) -> Profile:
    """The model's masses, couplings and states, as the rules read them."""
    dm = spec.dark_matter
    m = dm.mass_gev
    parity, _ = model_checks.parities(spec)
    new = [f for f in spec.fields if f.role is not FieldRole.standard_model]
    sectors, specific = _couplings_to_standard_model(spec)
    mediators = [Mediator(name=f.name, spin=f.spin, mass_gev=f.mass_gev, odd=parity[f.name] == -1,
                          alpha=_alpha(spec, f.name)) for f in spec.fields if f.role is FieldRole.mediator]
    masses = {f.name: f.mass_gev for f in new if f.mass_gev is not None}
    lighter = [n for n, v in masses.items() if m and n != dm.name and parity[n] == 1 and v < m]
    partners = [n for n, v in masses.items() if m and n != dm.name and parity[n] == -1 and m <= v < (1 + NEAR) * m]
    return Profile(mass_gev=m, su2=dm.charges.su2, sectors=sectors, flavour_specific=specific,
                   mediators=mediators, new_states=masses, even_lighter=lighter, partners=partners,
                   new_scalars=any(f.spin == 0.0 for f in new), cosmology=spec.cosmology,
                   relic_fraction=spec.relic_fraction)


Rule = Callable[[Profile, model_checks.CheckReport, set[str]], tuple[Status, str]]


def _light(p: Profile, below: float) -> list[str]:
    return [f"{n} ({v:g} GeV)" for n, v in p.new_states.items() if v < below]


def _near_thresholds(p: Profile) -> list[str]:
    m, out = p.mass_gev or 0.0, []
    out += [f"coannihilation partner {n}" for n in p.partners]
    for med in p.mediators:
        if med.mass_gev and not med.odd and abs(med.mass_gev - 2 * m) < NEAR * 2 * m:
            out.append(f"the {med.name} resonance (M = {med.mass_gev:g} GeV ≈ 2m_χ)")
        if med.mass_gev and abs(m - med.mass_gev) < WINDOW * med.mass_gev:
            out.append(f"the {med.name}-pair threshold (m_χ ≈ M)")
    electroweak = bool({"higgs", "z", "w"} & set(p.sectors)) or p.su2 > 1
    reach = {"WW": electroweak, "ZZ": electroweak, "hh": "higgs" in p.sectors, "tt̄": "quark" in p.sectors}
    for pair, name, mass in (("WW", "W", M_W), ("ZZ", "Z", M_Z), ("hh", "h", M_H), ("tt̄", "t", M_T)):
        if reach[pair] and abs(m - mass) < WINDOW * mass:
            out.append(f"the {pair} threshold (m_χ ≈ m_{name})")
    return out


A = Status.applies
NA = Status.not_applicable


def _from_report(flags: list[str], clean: str) -> tuple[Status, str]:
    return (Status.flagged, "; ".join(flags)) if flags else (Status.checked, clean)


def _relic(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    fraction = f"intended: {p.relic_fraction:g} of Ωh² = 0.12"
    return (Status.checked, fraction) if "relic" in done else (A, f"{fraction}; needs every annihilation channel")


def _equilibrium(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    if not p.sectors:
        return A, "no term couples the dark sector to the Standard Model: equilibrium with the bath is not established"
    return A, f"couples to the bath through {', '.join(p.sectors)}: Γ against H to be computed"


def _thresholds(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    found = _near_thresholds(p)
    return (A, "; ".join(found)) if found else (
        NA, "no odd state within 20% above m_χ, no mediator near 2m_χ, no channel opening within 10% of m_χ")


def _sommerfeld(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    m, out = p.mass_gev or 0.0, []
    for med in p.mediators:
        if med.mass_gev is None or med.odd:
            continue
        if med.alpha is None and med.mass_gev < m:
            out.append(f"{med.name} is lighter than m_χ and its coupling is not a number")
        elif med.alpha is not None and med.alpha * m / max(med.mass_gev, 1e-12) > 0.1:
            out.append(f"{med.name}: α m_χ/M = {med.alpha * m / max(med.mass_gev, 1e-12):.2g} > 0.1")
    if p.su2 > 1 and ALPHA_2 * m / M_W > 0.1:
        out.append(f"an SU(2) multiplet with α₂ m_χ/m_W = {ALPHA_2 * m / M_W:.2g} > 0.1")
    return (A, "; ".join(out)) if out else (NA, "every force carrier has α m_χ/M < 0.1: no long-range enhancement")


def _kinetic(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    m = p.mass_gev or 0.0
    special = [x for x in _near_thresholds(p) if "resonance" in x or "-pair threshold" in x]
    if p.even_lighter:
        special.append(f"annihilation into {', '.join(p.even_lighter)} is open")
    if special:
        return A, "; ".join(special)
    if not p.sectors:
        return A, "no coupling to the Standard Model bath"
    return NA, f"no resonance or forbidden channel near m_χ = {m:g} GeV: scattering on the bath outlasts annihilation"


def _cosmology(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    return (Status.assumed, p.cosmology) if p.cosmology == STANDARD_COSMOLOGY else (
        A, f"stated: {p.cosmology}; the relic code assumes the standard history")


def _secluded(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    return (A, f"annihilation into {', '.join(p.even_lighter)} is open: their decays and temperature matter"
            ) if p.even_lighter else (NA, "no new state is lighter than the dark matter")


def _direct(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    notes = []
    if (p.mass_gev or 0.0) < LIGHT_GEV and {"lepton", "photon"} & set(p.sectors):
        notes.append("electron recoils matter below 1 GeV and are not built")
    if not {"quark", "gluon", "photon", "higgs", "z"} & set(p.sectors):
        notes.append("no tree-level coupling to nuclei: only DirectDM's running reaches them")
    if "direct_detection" in done:
        return Status.checked, "; ".join(["nuclear recoils: Path 1's limits in the chosen modules", *notes])
    return A, "; ".join(["nuclear recoils: run Path 1's exclusion", *notes])


def _indirect(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    return (A, "needs ⟨σv⟩ today by channel") if p.sectors else (NA, "no visible annihilation channel")


def _colliders(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    if not p.sectors:
        return NA, "no coupling to the Standard Model"
    on_shell = [m.name for m in p.mediators if m.mass_gev is not None and m.mass_gev < 3000.0]
    how = f"mediators below 3 TeV ({', '.join(on_shell)}) are produced on shell" if on_shell else \
        "mediators above 3 TeV: contact-interaction (mono-X) searches"
    return A, f"couples to {', '.join(p.sectors)}; {how}"


def _light_rule(below: float, what: str, needs: set[str] | None = None) -> Rule:
    def rule(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
        light = _light(p, below)
        if light and (needs is None or needs & set(p.sectors)):
            return A, f"{', '.join(light)} below {below:.3g} GeV"
        return NA, f"no new state below {below:.3g} GeV{what}"
    return rule


def _neutrinos(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    if "neutrino_fluxes" in done:
        return Status.checked, "capture in the Sun against IceCube (Path 1's telescope tier); Earth and halo not built"
    return A, "capture in the Sun: run Path 1's exclusion"


def _flavour(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    return (A, "couplings single out flavours (individual fermions, or several in one term)"
            ) if p.flavour_specific else (NA, "one coupling for every quark and lepton, or none")


def _precision(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    m, out = p.mass_gev or 0.0, []
    if "higgs" in p.sectors and m < M_H / 2:
        out.append("invisible Higgs decays (m_χ < m_h/2)")
    if "z" in p.sectors and m < M_Z / 2:
        out.append("the invisible Z width (m_χ < m_Z/2)")
    if p.su2 > 1:
        out.append("electroweak precision data (an SU(2) multiplet)")
    if any(med.spin == 1.0 for med in p.mediators) and "lepton" in p.sectors:
        out.append("LEP's contact interactions and electroweak fits (a vector coupling to leptons)")
    return (A, "; ".join(out)) if out else (NA, "no light invisible Higgs or Z decay, no electroweak multiplet")


def _decay(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    if r.stability:
        return Status.flagged, "; ".join(r.stability)
    return NA, "stable under the stated symmetry, if it is exact (symmetry-breaking operators not checked)"


def _free_streaming(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    m = p.mass_gev or 0.0
    return (A, f"m_χ = {m:g} GeV is below 1 MeV") if m < COLD_GEV else (
        NA, f"a freeze-out relic of {m:g} GeV is cold")


def _cmb(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    return (A, "s-wave annihilation into visible states at recombination: Planck's p_ann") if p.sectors else (
        NA, "no visible annihilation channel")


def _self_interactions(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    m, worst, unknown, estimated = p.mass_gev or 0.0, 0.0, [], False
    for med in p.mediators:
        if med.mass_gev is None or med.odd:
            continue
        if med.alpha is None:
            unknown += [med.name] if med.mass_gev < LIGHT_GEV else []
            continue
        sigma_over_m = 4 * math.pi * med.alpha ** 2 * m / med.mass_gev ** 4 * GEV2_CM2 / GEV_G
        worst, estimated = max(worst, sigma_over_m), True
    if not estimated and not unknown:
        return NA, "no mediator below 1 GeV (σ/m not estimated: no Yukawa or gauge coupling to the dark matter)"
    if unknown or worst > SIDM_NEGLIGIBLE:
        return A, f"σ/m ≈ {worst:.2g} cm²/g (Born, contact)" + (f"; {', '.join(unknown)} light" if unknown else "")
    return NA, f"σ/m ≈ {worst:.2g} cm²/g (Born, contact), below {SIDM_NEGLIGIBLE} cm²/g"


def _plasma(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    m = p.mass_gev or 0.0
    light = [x for x in _light(p, 1e-3)]
    return (A, f"m_χ = {m:g} GeV" + (f"; {', '.join(light)}" if light else "")) if m < LIGHT_GEV or light else (
        NA, "the dark matter is above 1 GeV and no state is below 1 MeV")


def _unitarity(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    status, detail = _from_report(r.unitarity, "no axial coupling of a massive vector breaks eq. 2.8 of arXiv:1510.02110")
    scales = [n for n in r.notes if "needs completing" in n]
    if (p.mass_gev or 0.0) > 1e4:
        return A, "m_χ above 10 TeV: the thermal-relic unitarity bound needs the relic code"
    return status, "; ".join([detail, *scales])


def _vacuum(p: Profile, r: model_checks.CheckReport, done: set[str]) -> tuple[Status, str]:
    return (A, "new scalars: a vacuum certificate needs the complete potential (a typed scalar_potential)"
            ) if p.new_scalars else (NA, "no new scalar")


RULES: dict[str, Rule] = {
    "relic_abundance": _relic,
    "initial_equilibrium": _equilibrium,
    "coannihilation_resonance_threshold": _thresholds,
    "sommerfeld_bound_states": _sommerfeld,
    "kinetic_equilibrium": _kinetic,
    "cosmological_history": _cosmology,
    "secluded_sector": _secluded,
    "direct_detection": _direct,
    "indirect_detection": _indirect,
    "colliders": _colliders,
    "beam_dumps": _light_rule(BEAM_DUMP_GEV, " that couples to the Standard Model",
                              {"quark", "lepton", "photon", "higgs", "z"}),
    "rare_meson_decays": _light_rule(B_TO_K_GEV, " coupled to quarks", {"quark", "higgs", "gluon"}),
    "neutrino_fluxes": _neutrinos,
    "flavour": _flavour,
    "precision": _precision,
    "stellar_cooling": _light_rule(LIGHT_GEV, ""),
    "dm_decay": _decay,
    "free_streaming": _free_streaming,
    "bbn_neff": _light_rule(BBN_GEV, ", so none is in equilibrium at BBN (mediator lifetimes not computed)"),
    "cmb_annihilation": _cmb,
    "self_interactions": _self_interactions,
    "plasma_scattering": _plasma,
    "unitarity": _unitarity,
    "anomaly_cancellation": lambda p, r, d: _from_report(r.anomalies, "no anomalous U(1) and no unchecked axial coupling"),
    "perturbativity": lambda p, r, d: _from_report(r.perturbativity, "every dimensionless coupling below √(4π)"),
    "vacuum_structure": _vacuum,
    "stability_mechanism": lambda p, r, d: _from_report(r.stability, "the stated parity keeps the dark matter stable"),
    "eft_validity": lambda p, r, d: _from_report(r.contact, "every mediator is heavy enough for the contact interaction"),
}


def assess(spec: ModelSpec, report: model_checks.CheckReport | None = None,
           done: set[str] | None = None) -> list[Entry]:
    """Every item's status for the model. ``done``: what the pipeline computed
    ("relic", "direct_detection", "neutrino_fluxes")."""
    report = report or model_checks.check(spec)
    p, done = profile(spec), done or set()
    out = []
    for item in items():
        status, detail = RULES[item.id](p, report, done)
        out.append(Entry(id=item.id, group=item.group, title=item.title, status=status, detail=detail,
                         planned=item.planned if status is A else ""))
    return out


def report(entries: list[Entry]) -> str:
    """The checklist in Markdown, by group."""
    heads = groups()
    lines = ["## Viability checklist (thermal freeze-out)", "",
             "Each item for this model: computed by the run (with its verdict); undecided (compared by the run, but "
             "no verdict anywhere: the reasons are given, and it neither excludes nor allows); checked or flagged by "
             "the model checks; assumed; applies (not yet computed: where it will be built); or does not apply "
             "(why).", ""]
    for group, heading in heads.items():
        lines += [f"**{heading}**", "", "| check | status | for this model | to be built |", "|---|---|---|---|"]
        lines += [f"| {e.title} | {e.status.value} | {e.detail} | {e.planned or '—'} |"
                  for e in entries if e.group == group]
        lines.append("")
    counts = {s: sum(e.status is s for e in entries) for s in Status}
    lines.append("Totals: " + ", ".join(f"{s.value} {n}" for s, n in counts.items() if n) + ".")
    return "\n".join(lines) + "\n"
