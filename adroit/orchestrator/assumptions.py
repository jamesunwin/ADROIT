"""The inventory of assumptions behind a result (DM9): deterministic.

Following DarkAgents (arXiv:2606.11157), an audit lists every prior,
approximation and validity limit that entered a result. Here the list is not left
to a language model: it is read from the result and its experiment module, item by
item, with where each comes from. The audit agent (``agents.audit``) then judges
each item's weight; it may add items, which are marked as its own.

Categories: data, convention, approximation, statistics, validity, model (what
the model space or the model leaves out), and prior (there are none in the
frequentist fits, which is itself recorded).
"""

from __future__ import annotations

from pydantic import Field

from adroit.core.state import StrictModel
from adroit.experiments import registry as modules
from adroit.inference import dm_tournament


class InventoryItem(StrictModel):
    """One assumption: its identifier, category, statement and where it comes from."""
    id: str
    category: str
    statement: str
    source: str


class Inventory(StrictModel):
    """Every assumption a result rests on, item by item."""
    subject: str
    items: list[InventoryItem] = Field(default_factory=list)

    def add(self, category: str, statement: str, source: str) -> None:
        """Append an item, numbered A1, A2, ... in order."""
        self.items.append(InventoryItem(id=f"A{len(self.items) + 1}", category=category, statement=statement,
                                        source=source))


def _module_items(inv: Inventory, name: str, role: str) -> None:
    module = modules.load_module(name)
    info, conventions = module.info, module.conventions()
    halo = conventions.halo
    inv.add("data", f"{role} {info.name}: {info.target}, exposure {info.exposure_kg_day:g} kg·day, window "
            f"{info.energy_window_kev[0]:g}–{info.energy_window_kev[1]:g} keV, fidelity {info.fidelity.value}"
            f"{'' if info.background_model else ', no background model of its own'}", f"module {info.name}")
    inv.add("convention", f"{info.name}: halo {halo.label}: ρ = {halo.rho_gev_cm3:g} GeV/cm³, v₀ = "
            f"{halo.v0_km_s:g} km/s, v_esc = {halo.v_esc_km_s:g} km/s", f"module {info.name}, conventions")
    inv.add("approximation", f"{info.name}: nuclear responses {conventions.nuclear_model.value} "
            f"(spin-dependent: {conventions.spin_dependent_model.value})", f"module {info.name}, conventions")


def path2(result) -> Inventory:
    """Everything a Path 2 result rests on (``orchestrator.signal.SignalResult``)."""
    r = result.request
    inv = Inventory(subject=f"Path 2 on {r.experiment}")
    _module_items(inv, r.experiment, "The search:")
    inv.add("statistics", "an extended unbinned likelihood in recoil energy, with the module's resolution; "
            "the signal strength is the only free parameter of a candidate (k = 1)", "inference.signal_fit")
    inv.add("statistics", f"global significance: {result.global_method}", "signal._global_significance")
    inv.add("model", "the model space: " + (f"{len(r.candidates)} given candidates" if r.candidates else
            "the search's published model space, or every operator and Lagrangian card in each isospin over "
            f"the mass grid, with splittings {r.splittings_kev} keV"), "signal.model_space")
    inv.add("approximation", f"candidates closer than {r.class_events:g} events (Jeffreys distance) form one "
            "degeneracy class; only the best of each of the leading classes is carried on", "degeneracy.classes")
    inv.add("statistics", f"the tournament ranks by AIC = −Z_joint² + 2k; within ΔAIC ≤ "
            f"{dm_tournament.INDISTINGUISHABLE_DAIC:g} candidates are indistinguishable", "inference.dm_tournament")
    inv.add("statistics", "null experiments enter as limit-equivalent likelihoods; their tension with the signal "
            "is the parameter goodness of fit", "inference.combination")
    for name in r.null_modules:
        if name != r.experiment:
            _module_items(inv, name, "Null experiment:")
    inv.add("prior", "no priors: profile-likelihood fits and frequentist limits throughout", "inference")
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for entry in result.tournament.ranking:
        for flag in entry.flags:
            grouped.setdefault(("validity", flag, "signal._flags"), []).append(entry.label)
    for label, verdicts in result.verdicts.items():
        for v in verdicts:
            for assumption in v.assumptions:
                grouped.setdefault(("approximation", f"{v.constraint_id}: {assumption}", "constraints.verdicts"),
                                   []).append(label)
            if v.needed_calculation:
                grouped.setdefault(("validity", f"{v.constraint_id}: not concluded without {v.needed_calculation}",
                                    "constraints.verdicts"), []).append(label)
    for (category, statement, source), labels in grouped.items():
        inv.add(category, f"{statement} (for {', '.join(labels)})", source)
    if not r.complementary:
        inv.add("model", "complementary constraints were not applied", "signal request")
    return inv


def path1(result) -> Inventory:
    """Everything a bespoke Path 1 result rests on (``orchestrator.lagrangian.LagrangianResult``)."""
    spec, d = result.spec, result.derivation
    inv = Inventory(subject=f"Path 1 for {spec.name if spec else 'a bespoke model'}")
    for x in spec.assumptions if spec else []:
        inv.add("model", x, "the model (intake or user)")
    for x in spec.dropped if spec else []:
        inv.add("model", f"left out of the model: {x}", "the model (intake or user)")
    if spec:
        inv.add("convention", f"cosmology: {spec.cosmology}", "the model")
    for x in d.assumptions if d else []:
        inv.add("approximation", x, "the derivation")
    for x in d.dropped if d else []:
        inv.add("approximation", f"left out of the derivation: {x}", "the derivation")
    if d:
        inv.add("approximation", f"DirectDM in the {d.flavours}-flavour theory, with its running to 2 GeV and its "
                "nucleon inputs; tree-level matching", "library.interactions.quark_level")
    for flag in result.checks.flags if result.checks else []:
        inv.add("validity", flag, "model_checks")
    for e in result.viability:
        if e.status.value in ("assumed", "applies, not yet computed", "flagged"):
            inv.add("validity" if e.status.value != "assumed" else "convention",
                    f"{e.title}: {e.status.value} ({e.detail})", "constraints.viability")
    if result.exclusion:
        for m in result.exclusion.per_module:
            _module_items(inv, m.experiment, "Limit from")
    inv.add("prior", "no priors: frequentist limits", "orchestrator.exclusion")
    return inv


def _model(inv: Inventory, spec) -> None:
    for x in spec.assumptions:
        inv.add("model", x, "the model")
    for x in spec.dropped:
        inv.add("model", f"left out of the model: {x}", "the model")
    inv.add("convention", f"cosmology: {spec.cosmology}", "the model")


def applied_constraints(scan) -> list[str]:
    """Every constraint a Track 1 scan compared at some point (its cuts and its searches)."""
    if scan is None:
        return []
    return sorted({k for p in scan.points for k in p.excluded} | {o.name for p in scan.points for o in p.search_results})


def _counted(inv: Inventory, category: str, lists: list[list[str]], source: str, what: str) -> None:
    """Each distinct statement once, with the number of scan points it holds at."""
    counts: dict[str, int] = {}
    for items in lists:
        for x in dict.fromkeys(items):
            counts[x] = counts.get(x, 0) + 1
    for x, n in counts.items():
        inv.add(category, f"{x} ({what} at {n} of {len(lists)} points)", source)


def track1(result) -> Inventory:
    """Everything a Track 1 result rests on (``orchestrator.track1.Track1Result``)."""
    from adroit.constraints.propagation import normalise, stronger
    r, spec = result.request, result.request.spec
    inv = Inventory(subject=f"Track 1 for {spec.name}")
    _model(inv, spec)
    for x in result.audit.notes:
        inv.add("model", x, "model_building.audit")
    for x in result.audit.flags:
        inv.add("validity", x, "model_building.audit")
    if result.audit.missing:
        inv.add("model", "terms the field content allows but the model leaves out: "
                + ", ".join(t.text or t.lorentz for t in result.audit.missing), "model_building.audit")
    if result.unsupported:
        inv.add("validity", f"not computed: {result.unsupported}", "parameter_space.classify")
    for x in result.notes:
        inv.add("approximation", x, "the model's map onto a computed class")
    if result.scan is not None:
        q = result.scan.request
        inv.add("approximation", f"a {len(result.scan.xs)} × {len(result.scan.ys)} grid in {q.x.parameter} "
                f"({q.x.low:g}–{q.x.high:g}) and {q.y.parameter} ({q.y.low:g}–{q.y.high:g}); between grid points "
                "only the thermal contour is refined", "parameter_space.scan")
        inv.add("data", "constraints compared: " + (", ".join(applied_constraints(result.scan)) or "none"),
                "parameter_space.scan")
        _counted(inv, "validity", [p.flags for p in result.scan.points], "parameter_space.scan", "flagged")
        _counted(inv, "validity", [p.pending for p in result.scan.points], "parameter_space.scan", "undecided")
    if r.propagation is None:
        inv.add("convention", "charged cosmic rays: the propagation model is not recorded (results from before the "
                "choice existed used the source's central bound)", "constraints.propagation")
    else:
        model = normalise(r.propagation)
        inv.add("convention", f"charged cosmic rays: the {model} propagation model decides"
                + (f"; the {' and '.join(stronger(model))} models only flag" if stronger(model) else ""),
                "constraints.propagation")
    for v in (result.verdict, result.likelihood_verdict):
        for x in v.unresolved if v else []:
            inv.add("validity", f"unresolved: {x}", "parameter_space.verdict")
    if r.unverified_records:
        inv.add("data", "constraint records awaiting a person's verification are used", "track1 request")
    for ref in r.private_limits:
        inv.add("data", f"a private published limit: {ref}", "track1 request")
    inv.add("statistics", "each constraint is a hard cut at 95% CL" + (", and a combined likelihood verdict"
            if result.likelihood_verdict else ""), "parameter_space.verdict")
    inv.add("prior", "no priors: frequentist cuts and limits", "parameter_space.verdict")
    return inv


def single_idea(result) -> Inventory:
    """Everything a single-idea result rests on (``orchestrator.single_idea.SingleIdeaResult``); its Track 1 study's
    items follow, marked as Track 1's."""
    r, spec = result.request, result.request.spec
    inv = Inventory(subject=f"{spec.name} for {r.experiment}")
    _model(inv, spec)
    try:
        _module_items(inv, r.experiment, "The search:")
    except (KeyError, ValueError, OSError):
        inv.add("data", f"the search: {r.experiment}", "single-idea request")
    masses = r.masses_gev
    inv.add("statistics", f"the model's fit at {len(masses)} dark-matter masses ({min(masses):g}–{max(masses):g} GeV); "
            f"global significance: {result.global_method or 'not computed'}", "orchestrator.single_idea")
    for name in r.null_modules:
        if name != r.experiment:
            _module_items(inv, name, "Null experiment:")
    if result.combination is not None:
        inv.add("statistics", "null experiments enter as limit-equivalent likelihoods; their tension with the signal "
                "is the parameter goodness of fit", "inference.combination")
    if result.unsupported:
        inv.add("validity", f"not computed: {result.unsupported}", "orchestrator.single_idea")
    for x in result.thermal_pending:
        inv.add("validity", f"thermal history pending: {x}", "orchestrator.single_idea")
    if result.physical_significance_note:
        inv.add("statistics", result.physical_significance_note, "orchestrator.single_idea")
    if result.track1 is not None:
        for item in track1(result.track1).items:
            if item.category not in ("model", "prior") and not item.statement.startswith("cosmology:"):
                inv.add(item.category, f"Track 1: {item.statement}", item.source)
    inv.add("prior", "no priors: profile-likelihood fits and frequentist limits throughout", "inference")
    return inv


def text(inv: Inventory) -> str:
    """The inventory as the audit agent reads it."""
    return "\n".join(f"{i.id} [{i.category}] {i.statement}  (source: {i.source})" for i in inv.items)
