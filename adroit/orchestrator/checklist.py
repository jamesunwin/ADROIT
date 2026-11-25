"""The viability checklist from what a run computed (R8): Track 1, single-idea and bespoke Path 1 results.

``constraints.viability`` states, for a model alone, which of the owner's 28 items apply to it. This module adds
what a run actually computed, item by item:

- **computed:** each constraint the scan compared, with its verdict over the grid and on the thermal-relic contour;
  the relic abundance from the thermal roots; the relic calculation's own physics (resonances, coannihilation
  partners, Sommerfeld factors and bound states) where the class has it; and the theory certificates (vacuum,
  partial-wave unitarity, running, chemical equilibrium) with their statuses;
- **assumed**, **applies, not yet computed** and **does not apply** stay as the model's rules give them.

A computed item carries no "to be built" text. Every constraint name a scan can produce maps to one item
(``ITEM_OF``); a name with no item is reported, never dropped.
"""

from __future__ import annotations

from collections import Counter

from adroit.constraints import viability
from adroit.constraints.viability import Entry, Status

ITEM_OF = {
    "direct detection": "direct_detection",
    "gamma rays (Fermi-LAT dwarfs)": "indirect_detection",
    "γ-ray lines (Fermi-LAT, H.E.S.S.)": "indirect_detection",
    "antiprotons (AMS-02)": "indirect_detection",
    "capture in the Sun (IceCube)": "neutrino_fluxes",
    "CMB (Planck)": "cmb_annihilation",
    "BBN and N_eff": "bbn_neff",
    "dark-photon searches": "beam_dumps",
    "flavour (B → K a)": "rare_meson_decays",
    "B → X_s γ (charged Higgs)": "rare_meson_decays",
    "B_s → μμ (2HDM)": "rare_meson_decays",
    "N_eff (Planck 2018)": "bbn_neff",
    "flavour (B → K a, a → μμ)": "rare_meson_decays",
    "electroweak precision (S, T)": "colliders",
    "LEP (charged partners)": "colliders",
    "colliders (CMS)": "colliders",
    "LHC searches (SModelS)": "colliders",
    "LHC dijet resonances (CMS, ATLAS)": "colliders",
    "LHC tt̄ resonances (CMS)": "colliders",
    "LHC monojet, spin-0 mediator (CMS)": "colliders",
    "LHC dilepton resonances (ATLAS)": "colliders",
    "LHC squark search (ATLAS)": "colliders",
    "LHC 2HDM+a searches (ATLAS)": "colliders",
    "2HDM+a mono-Higgs (ATLAS)": "colliders",
    "2HDM+a mono-Z (ATLAS)": "colliders",
    "heavy scalar → ZZ, WW (ATLAS)": "colliders",
    "LEP (inert doublet)": "colliders",
    "L_μ − L_τ (Z → 4μ)": "colliders",
    "L_μ − L_τ (BaBar/Belle II)": "colliders",
    "invisible Higgs width (ATLAS)": "precision",
    "invisible Z width (LEP)": "precision",
    "Higgs signal strength (ATLAS)": "precision",
    "muon g−2": "precision",
    "LEP-II contact interactions": "precision",
    "L_μ − L_τ (CCFR)": "precision",
    "perturbativity": "perturbativity",
}
CERTIFICATE_ITEM = {"vacuum_certificate": "vacuum_structure", "unitarity_certificate": "unitarity",
                    "running_certificate": "perturbativity", "chemical_certificate": "coannihilation_resonance_threshold"}
CERTIFICATE_TEXT = {"vacuum_certificate": "tree-level vacuum certificate (with the metastable vacuum's lifetime)",
                    "unitarity_certificate": "partial-wave unitarity certificate",
                    "running_certificate": "one-loop running certificate (boundedness and perturbativity)",
                    "chemical_certificate": "conversion chemical-equilibrium certificate"}


def item_of(name: str) -> str | None:
    """The checklist item a scan's constraint belongs to (a private limit or search is direct detection)."""
    if name.startswith(("private:", "private-search:")):
        return "direct_detection"
    return ITEM_OF.get(name)


def _verdicts(values: list[bool | None]) -> str:
    n = Counter("excluded" if v else "allowed" if v is False else "undecided" for v in values)
    return ", ".join(f"{k} at {n[k]}" for k in ("excluded", "allowed", "undecided") if n[k]) + f" of {len(values)}"


def _at_root(name: str, crossing) -> bool | None:
    """The constraint's verdict at a thermal root: from the root's retained evaluation, else (older results) from
    its lists of excluding and pending constraints. A root its certificate leaves waiting (M1: the tables missing,
    EOS-sensitive) decides nothing here: its computed exclusion is counted apart, as nominal (``_nominal``)."""
    if _waiting(crossing):
        return None
    if crossing.evaluation is not None:
        return crossing.evaluation.excluded.get(name)
    if name in crossing.excluded_by:
        return True
    return None if any(p.startswith(name) for p in crossing.pending) else False


def _waiting(crossing) -> bool:
    """Whether a root's certificate leaves it waiting, its status not the one its computed constraints gave."""
    c = getattr(crossing, "certificate", None)
    return c is not None and crossing.status == "pending" and c.computed_status not in ("", "pending")


def _contour(name: str, crossings: list) -> str:
    """The constraint's verdicts on the thermal contour, over the roots where it was compared; a waiting root's own
    comparison labelled nominal, apart from the stored verdicts (M1)."""
    compared = [c for c in crossings if c.evaluation is None or name in c.evaluation.excluded]
    values = [_at_root(name, c) for c in compared]
    if not values:
        return ""
    nominal = sum(_waiting(c) and c.evaluation is not None and c.evaluation.excluded.get(name) is True
                  for c in compared)
    extra = (f" ({nominal} of them nominally excluded by it, awaiting their certificate)" if nominal else "")
    if all(v is False for v in values):
        return f"; on the thermal contour: allowed at all {len(values)} root(s)"
    return f"; on the thermal contour: {_verdicts(values)} root(s){extra}"


UNPREFIXED = {"capture in the Sun (IceCube)": ("no supported pure neutrino channel",)}   # texts without a name


def _labels(name: str) -> tuple[str, ...]:
    """The forms a pending text may name the constraint by: 'gamma rays (Fermi-LAT dwarfs)' is also 'gamma rays'
    and 'Fermi-LAT dwarfs'."""
    head, _, inner = name.partition(" (")
    return tuple(x for x in (name, head, inner.rstrip(")")) if x)


def _reasons(name: str, texts: list[str], limit: int = 2) -> str:
    """The distinct reasons the run gave for leaving the constraint undecided (its pending texts and notes)."""
    labels = _labels(name)
    found = []
    for text in texts:
        label, sep, rest = text.partition(":")
        if sep and label.strip() in labels:
            found.append(rest.strip())
        elif any(text.startswith(u) for u in UNPREFIXED.get(name, ())):
            found.append(text.strip())
    found = list(dict.fromkeys(found))
    return ("; why: " + " | ".join(found[:limit]) + (f" (and {len(found) - limit} more)" if len(found) > limit else "")
            ) if found else ""


def scan_evidence(scan, crossings: list | None = None, notes: list[str] | None = None
                  ) -> tuple[dict[str, list[str]], list[str], set[str]]:
    """({item: lines}, names without an item, items with a verdict somewhere): each constraint's verdicts over the
    grid's points and on the thermal contour's certified roots; an item whose constraints decided nothing anywhere
    is left out of the third set (``undecided``), with the run's reasons in its lines."""
    crossings = crossings or []
    points = list(scan.points) if scan is not None else []
    names: dict[str, list] = {}
    for point in points:
        for name, value in point.excluded.items():
            names.setdefault(name, []).append(value)
    evidence: dict[str, list[str]] = {}
    unmapped, decided = [], set()
    for name, values in names.items():
        item = item_of(name)
        if item is None:
            unmapped.append(name)
            continue
        roots = [_at_root(name, c) for c in crossings if c.evaluation is None or name in c.evaluation.excluded]
        some = any(v is not None for v in [*values, *roots])
        decided |= {item} if some else set()
        texts = [t for p in points for t in p.pending] + list(notes or [])
        evidence.setdefault(item, []).append(f"{name}: {_verdicts(values)} grid points{_contour(name, crossings)}"
                                             + ("" if some else _reasons(name, texts)))
    return evidence, sorted(unmapped), decided


def _state(certificate) -> str:
    """A certificate's outcome: its status, or for the vacuum certificate its vacuum classification."""
    for field in ("status", "vacuum"):
        value = getattr(certificate, field, None)
        if isinstance(value, str) and value:
            return value
    passed = getattr(certificate, "passed", None)
    return "passed" if passed else "failed" if passed is False else "unresolved"


def _certificates(points: list) -> dict[str, list[str]]:
    found: dict[str, Counter] = {}
    for p in points:
        for attribute in CERTIFICATE_ITEM:
            certificate = getattr(p, attribute, None)
            if certificate is not None:
                found.setdefault(attribute, Counter())[_state(certificate)] += 1
    out: dict[str, list[str]] = {}
    for attribute, counts in found.items():
        text = ", ".join(f"{status} at {n}" for status, n in counts.most_common())
        out.setdefault(CERTIFICATE_ITEM[attribute], []).append(f"{CERTIFICATE_TEXT[attribute]}: {text} point(s)")
    return out


def relic_physics(cls, point) -> dict[str, str]:
    """What the class's relic calculation includes at a point: resonances, coannihilating species, and the
    Sommerfeld factor and bound states (empty where the class has none)."""
    out = {}
    try:
        resonances = cls.resonances(point) if hasattr(cls, "resonances") else []
        bath = cls.coannihilation(point) if hasattr(cls, "coannihilation") else None
    except Exception:  # noqa: BLE001 - a description, never a verdict
        resonances, bath = [], None
    if resonances:
        out["resonances"] = "thermal average across " + ", ".join(f"the {m:g} GeV pole" for m, _ in resonances)
    if bath is not None:
        species = bath[0]
        partners = sorted({f"{s.mass:g} GeV" for s in species[1:] if abs(s.mass - point.m_chi) > 1e-9})
        out["coannihilation"] = (f"{len(species)} species in the bath" + (f" (partners at {', '.join(partners)})"
                                                                          if partners else ""))
    long_range = [w for w, on in (("the Sommerfeld factor", getattr(cls, "sommerfeld", False)),
                                  ("bound-state formation", getattr(cls, "bound_states", False))) if on]
    if long_range:
        out["long_range"] = " and ".join(long_range) + " in the relic calculation"
    return out


INSTRUCTIONS = ("run Path 1's exclusion", "needs ⟨σv⟩ today by channel", "needs every annihilation channel",
                "to be computed")


def apply(entries: list[Entry], evidence: dict[str, list[str]], undecided: set[str] | None = None) -> list[Entry]:
    """The entries with each item that has evidence marked computed (or undecided, for an item in ``undecided``:
    compared, with no verdict anywhere), its evidence as the detail, the rule's remarks kept after it (but not its
    instructions to compute, now done), and no "to be built" text."""
    out = []
    for e in entries:
        lines = evidence.get(e.id)
        if lines:
            remarks = [] if e.status is Status.not_applicable else [
                x for x in e.detail.split("; ") if x and not any(i in x for i in INSTRUCTIONS)]
            status = Status.undecided if e.id in (undecided or set()) else Status.computed
            e = e.model_copy(update={"status": status, "planned": "",
                                     "detail": "; ".join([*lines, *([f"also: {'; '.join(remarks)}"] if remarks else [])])})
        out.append(e)
    return out


def _base(spec) -> list[Entry]:
    from adroit.library.interactions import model_checks
    try:
        report = model_checks.check(spec)
    except (ValueError, KeyError):
        report = None
    return viability.assess(spec, report)


def _root_counts(verdict) -> str:
    """The thermal roots a verdict evaluated, and of them how many its stored certificates certify, apart from the
    roots only a table has (the owner's EOS review, 2026-11-23: every evaluated root had been called certified, "48
    certified" of 42). The outcome is the stored one; a certificate made under an earlier policy is not re-assessed."""
    roots = [c for c in verdict.crossings if c.kind in ("contour", "point")]
    certified = sum(c.certificate is not None and c.certificate.decided for c in roots)
    text = f"{len(roots)} evaluated crossing{'s' if len(roots) != 1 else ''}: {certified} certified"
    if open_ := sum(c.certificate is not None and not c.certificate.decided for c in roots):
        text += f", {open_} not certified"
    if legacy := sum(c.certificate is None for c in roots):
        text += f", {legacy} without a certificate (legacy)"
    if verdict.table_roots:
        text += f"; {len(verdict.table_roots)} more only an equation-of-state table has"
    return text


def for_track1(result) -> list[Entry]:
    """The checklist of a Track 1 result."""
    entries = _base(result.request.spec)
    verdict = result.verdict
    crossings = verdict.crossings if verdict else []
    evidence, unmapped, decided = scan_evidence(result.scan, crossings, result.notes)
    if verdict is not None:
        evidence.setdefault("relic_abundance", []).insert(0, f"thermal roots of Ωh² = {verdict.target:g}: "
                                                              f"{verdict.level} ({_root_counts(verdict)}); "
                                                              f"{verdict.summary}")
    elif result.unsupported:
        evidence.setdefault("relic_abundance", [])
    if result.scan is not None and verdict is not None:
        point = crossings[0].point if crossings else (result.fixed or result.scan.points[0].point)
        physics = relic_physics(result.scan.request.model_class, point)
        evidence.setdefault("coannihilation_resonance_threshold", []).extend(
            physics[k] for k in ("resonances", "coannihilation") if k in physics)
        if "long_range" in physics:
            evidence.setdefault("sommerfeld_bound_states", []).append(physics["long_range"])
        points = [c.evaluation for c in crossings if c.evaluation is not None] or list(result.scan.points)
        for item, lines in _certificates(points).items():
            evidence.setdefault(item, []).extend(lines)
    evidence = {k: v for k, v in evidence.items() if v}
    scanned = {checklist_item for name in {n for p in (result.scan.points if result.scan else []) for n in p.excluded}
               if (checklist_item := item_of(name))}
    entries = apply(entries, evidence, undecided={k for k in scanned - decided
                                                  if k not in ("relic_abundance", "coannihilation_resonance_threshold",
                                                               "sommerfeld_bound_states")})
    if unmapped:
        entries.append(Entry(id="unmapped", group="searches", title="Other constraints", status=Status.computed,
                             detail="compared, with no checklist item: " + ", ".join(unmapped)))
    return entries


def for_single_idea(result) -> list[Entry]:
    """The checklist of a single-idea result: its Track 1 study's, with the signal fit and the null experiments as
    direct-detection evidence."""
    entries = for_track1(result.track1) if result.track1 is not None else _base(result.request.spec)
    r = result.request
    fit = (f"the fit to {r.experiment} at {len(r.masses_gev)} masses: {result.level or 'no level'}"
           + (f", global Z = {result.global_z:.2f}" if result.global_method else ""))
    if result.combination is not None:
        nulls = list(result.combination.null_limits)
        fit += f"; null experiments {', '.join(nulls) or 'none'}: χ²_PG = {result.combination.chi2_pg:.2f}"
    return [e.model_copy(update={"status": Status.computed, "planned": "", "detail": f"{fit}; {e.detail}"
                                 if e.status is Status.computed else fit}) if e.id == "direct_detection" else e
            for e in entries]


def lagrangian_evidence(result) -> dict[str, list[str]]:
    """A bespoke Path 1 result's evidence: the modules' limits, and capture in the Sun."""
    evidence: dict[str, list[str]] = {}
    exclusion = result.exclusion
    if exclusion is not None:
        modules = [m.experiment for m in exclusion.per_module]
        if modules:
            evidence["direct_detection"] = [f"limits in {len(modules)} module(s): {', '.join(modules)}"]
        if getattr(exclusion, "telescopes", None):
            evidence["neutrino_fluxes"] = ["capture in the Sun against IceCube (Path 1's telescope tier)"]
    return evidence
