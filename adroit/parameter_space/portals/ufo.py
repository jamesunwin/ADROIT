"""Portals defined by a published UFO model: every tree-level channel found by the engine.

A model with many annihilation and coannihilation channels (the inert doublet, the 2HDM+a)
is taken as the literature publishes it, a UFO model, rather than rewritten by hand. At
each parameter point:
1. the model is evaluated with the scan's parameters (``ufo_model.dump``) and translated
   for the tree engine; the new particles' widths are computed from its vertices;
2. every pair of species in the bath (the dark matter and its partners) is annihilated into
   every pair of Standard Model particles that has a tree diagram (``tree.Process``);
3. the relic density follows from the coannihilation solver, with any Sommerfeld factors
   the entry supplies.

**Final states.** Every pair of particles outside the dark sector (the bath and any other
odd particles, ``odd``) that conserves electric charge and fermion number: pairs of bosons,
and a fermion with an antifermion (u d̄ through a W, for coannihilating charged partners).
Particles are recognised by their PDG codes, so a model's own names (``e``/``E`` or
``e-``/``e+``) do not matter.

Colour-singlet initial states only: gluon vertices are dropped (``ufo_model``), so a model
with coloured partners uses ``tchannel`` instead. The 125 GeV Higgs's loop-induced final states
(g g, γ γ, Z γ) are added to a pair that reaches it (``higgs_loops``).

**Trust.** A portal can arrive from a saved result or an evidence bundle, so its fields are data,
never code: each parameter expression is plain arithmetic in the scan's slots
(``core.arithmetic``, checked when the portal is read), and ``model_dir`` must be one of the
packaged library's UFO models (:data:`MODEL_DIRS`), resolved inside ``<tools>/ufo``. The UFO files
themselves are Python that MadGraph's interpreter imports: they are trusted as code, like every
program in the tools folder.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Callable, ClassVar, Literal

import numpy as np
from pydantic import Field, field_validator

from adroit.constraints import hadronic_window, loops, relic, tree, ufo_model
from adroit.core.arithmetic import evaluate, parse
from adroit.core.config import get_settings
from adroit.parameter_space.classes import F_N, M_NUCLEON, Point
from adroit.parameter_space.portals.base import Nucleon, Portal

OFF_SHELL = {23, 24}            # W and Z: produced off shell near and below threshold (V V*)
# a final state opening above the initial pair's threshold, within this fraction of it, gets nodes from its opening
# (the table is one per pair, its ln σ linear in √s: a channel opening inside a cell had been read as an exponential
# across it, the 2HDM+a's Ωh² 4–34% high below m_t; the audit loop's AL3-04, 2026-11-15)
OPENING_REACH = 0.6
OPENING_STEPS = np.concatenate([[0.0], np.geomspace(1e-6, 0.05, 15)])
OFF_SHELL_REACH = 30.0          # widths above threshold within which the off-shell integral is used
BW_NODES = 10
POLE_REACH = 15.0               # widths around a pole integrated in u; the tails beyond in m² (``_breit_wigner``)
TABLE_NODES = 40                # √s nodes of a pair's σ table (geometric in √s − threshold)
# a pole's nodes in widths, about √2 apart: ln σ is read linearly in √s between nodes, and its chord over a Lorentzian's
# tail lies above it (factors of 2 apart had made a pole 1.4% too strong, √2 apart 0.44%); beyond them its nodes go
# on at ``POLE_LADDER`` until they reach ``POLE_TABLE_REACH`` of its distance from the pair's threshold (from 60 widths
# to the next base node the Higgs's pole had been 1.4–2.9% too strong at its own Γ/M = 3.3 × 10⁻⁵, up to 2.9 times at
# 10⁻⁷; the UFO side of the audit loop's AL3-02, 2026-11-15)
_HALF_OFFSETS = (0.1, 0.2, 0.3, 0.5, 0.7, 1, 1.4, 2, 2.8, 4, 5.6, 8, 11, 16, 23, 32, 45, 64)
RESONANCE_OFFSETS = tuple(-o for o in reversed(_HALF_OFFSETS)) + (0,) + _HALF_OFFSETS
POLE_LADDER = 1.5
POLE_TABLE_REACH = 0.5
# A pole at or below the pair's threshold, within this many widths, is resolved from the threshold up to this many
# widths above its centre (the audit loop's AL4-02, 2026-11-16: a pole exactly at 2m_χ had fallen in the table's
# first cell, Ωh² six times too small at Γ/M = 6 × 10⁻⁶)
THRESHOLD_POLE_WIDTHS = 64.0
# The table's ladder in u = √s/start − 1: a first node at U_FIRST, then from U_BASE up. A pole near the threshold shapes
# σ below U_BASE: its threshold scale (``threshold_scale``: its half-width or its distance from the threshold in u, the
# larger) under THRESHOLD_NEAR, below the threshold, or above it within NEAR_ABOVE or THRESHOLD_POLE_WIDTHS widths. For
# such a pole the table runs a ladder of THRESHOLD_PER_DECADE nodes a decade, from a hundredth of that scale to
# THRESHOLD_REACH times it (at least to U_BASE), as the generic engine's tables do (``generic._nodes``, AL3-02); a wider
# or farther pole is resolved by the base ladder (within 2% from 10⁻³ below the threshold). The audit loop's AL5-01 (the auditor, 2026-11-17): the ladder had
# begun at U_FIRST whatever the pole, and only for a pole within 64 widths, so a narrower pole at the threshold was
# dropped below the first node, and a narrow one within 10⁻⁴ of it read across the gap from U_FIRST to U_BASE: from
# 0.007 to 4 × 10⁴ times its thermal average at Γ/M from 10⁻⁹ to 10⁻¹³, 1.10 times at 10⁻⁶ and 10⁻⁴ below.
U_FIRST, U_BASE = 1e-9, 1e-5
THRESHOLD_NEAR, NEAR_ABOVE = 1e-3, 2e-5
THRESHOLD_PER_DECADE = 16
THRESHOLD_RESOLUTION = 1e-2
THRESHOLD_REACH = 10.0
# The tree amplitudes vanish within 10⁻¹² of the initial threshold (``tree.Process.sigma``): the table's first node is
# no lower than U_LOWEST, and a pole whose threshold scale is below SCALE_RESOLVED is not resolved: Ωh² is refused
# (``domain``). Above it the interval lost below the first node is under 0.5% of the pole's thermal average.
U_LOWEST = 1.25e-12
SCALE_RESOLVED = 2e-11
GHOSTS = 9_000_000
GLUON = 21
PARTONS = frozenset({1, 2, 3, 4, 5, 6, GLUON})        # quark and gluon PDG codes
STANDARD_BOSONS = frozenset({GLUON, 22, 23, 24, 25})  # g, γ, Z, W, the 125 GeV Higgs: their own prescriptions
SM_NAMES = {1: "d", 2: "u", 3: "s", 4: "c", 5: "b", 6: "t", 11: "e", 13: "mu", 15: "tau", 12: "nu", 14: "nu", 16: "nu"}
SLOTS = frozenset({"m_chi", "m_med", "g_chi", "g_q", "g_l"})
MODEL_DIRS = frozenset({"ufo/InertDoublet_UFO", "ufo/Pseudoscalar_2HDM"})   # the packaged library's UFO models
_MODELS: dict[tuple, tuple] = {}
_SIGMA: dict[tuple, tuple[np.ndarray, np.ndarray, np.ndarray, float]] = {}   # nodes, total, non-partonic, opening


HIGGS_LOOPS = {"g": True, "gamma": False, "Zgamma": False}   # the Higgs's loop-induced final states: partonic?


def higgs_loops(model: tree.Model, a: str, b: str) -> Callable[[float], dict[str, float]] | None:
    """σ(a b → h* → X)(s) for the 125 GeV Higgs's loop-induced X (``HIGGS_LOOPS``) as {name: σ}, or None where a b do
    not reach h through a vertex of their own. The UFO route reads no gluon vertex, so these had been missing, about 9%
    of the Higgs's width: in its Higgs funnel the inert doublet's Ωh² was up to 17% above micrOMEGAs's once its b b̄
    width was right (the audit loop's AL3-05, 2026-11-15). The generic route's factorisation
    (``generic_id.higgs_loops``): σ(a b → h* → b b̄) through h alone, times Γ(h* → X)/Γ(h* → b b̄) at √s, Γ(h* → X)
    the Standard Model's (``higgs.partial_widths``) and Γ(h* → b b̄) the model's own at that mass (its vertex)."""
    from adroit.constraints import higgs
    h = next((x for x in model.particles.values() if x.pdg == 25), None)
    bottom = next((x for x in model.particles.values() if x.pdg == 5), None)
    if h is None or bottom is None:
        return None
    pair, quarks = sorted((a, b)), sorted((bottom.name, bottom.conjugate))
    keep = [v for v in model.vertices if len(v.legs) == 3 and h.name in v.legs
            and sorted(x for x in v.legs if x != h.name) in (pair, quarks)]
    if not any(sorted(x for x in v.legs if x != h.name) == quarks for v in keep) or len(keep) < 2:
        return None
    reduced = tree.Model({})
    reduced.particles, reduced.vertices = model.particles, keep
    try:
        process = tree.Process(reduced, a, b, bottom.name, bottom.conjugate, points=8)
    except (ValueError, KeyError):
        return None
    if not process.diagrams():
        return None
    anti = model.particles[bottom.conjugate]

    def sigma(s: float) -> dict[str, float]:
        root = math.sqrt(s)
        own = ufo_model._two_body(reduced, replace(h, mass=root), bottom, anti) if root > 2.2 * bottom.mass else 0.0
        if own <= 0.0:
            return {}
        base, widths = process.sigma(s), higgs.partial_widths(root)
        return {name: base * widths[name] / own for name in HIGGS_LOOPS if widths.get(name, 0.0) > 0.0}
    return sigma


def pole_offsets(width: float, reach: float) -> np.ndarray:
    """A pole's table nodes in units of its width: ``RESONANCE_OFFSETS``, continued on both sides at ``POLE_LADDER``
    until they reach ``reach`` (GeV) from its centre."""
    steps = np.array([o for o in RESONANCE_OFFSETS if o > 0], dtype=float)
    if width > 0 and steps[-1] * width < reach:
        more = math.ceil(math.log(reach / (steps[-1] * width)) / math.log(POLE_LADDER))
        steps = np.concatenate([steps, steps[-1] * POLE_LADDER ** np.arange(1, more + 1)])
    return np.concatenate([-steps[::-1], [0.0], steps])


def threshold_scale(start: float, mass: float, width: float) -> float | None:
    """The scale in u = √s/start − 1 on which a pole (mass, width in GeV) shapes σ near a pair's threshold ``start``:
    the larger of its half-width and its distance from the threshold; None for a pole not near it (``THRESHOLD_NEAR``,
    ``NEAR_ABOVE``, ``THRESHOLD_POLE_WIDTHS``) or without a width."""
    if width <= 0:
        return None
    u_r = mass / start - 1.0
    scale = max(width / (2.0 * start), abs(u_r))
    if scale >= THRESHOLD_NEAR or not (u_r < NEAR_ABOVE or abs(mass - start) <= THRESHOLD_POLE_WIDTHS * width):
        return None
    return scale


def table_roots(start: float, poles: list[tuple[float, float]]) -> np.ndarray:
    """A pair's table nodes in √s (GeV) from its threshold ``start``: the ladder above it; for a pole of ``poles``
    (mass, width) near the threshold, a ladder from a hundredth of its threshold scale up to the base ladder (AL5-01);
    and the nodes of each s-channel pole that the thermal average reaches: one above the threshold (AL3-02), and one
    at it or within ``THRESHOLD_POLE_WIDTHS`` widths below it, whose tail above it is then resolved too (AL4-02)."""
    scales = [x for x in (threshold_scale(start, mass, width) for mass, width in poles) if x is not None]
    first = min(U_FIRST, max(U_LOWEST, THRESHOLD_RESOLUTION * min(scales))) if scales else U_FIRST
    roots = start * (1.0 + np.concatenate([[first], np.geomspace(U_BASE, 25.0, TABLE_NODES)]))
    if scales:
        top = max(U_BASE, THRESHOLD_REACH * max(scales))
        count = math.ceil(math.log10(top / first) * THRESHOLD_PER_DECADE) + 1
        roots = np.union1d(roots, start * (1.0 + np.geomspace(first, top, count)))
    for mass, width in poles:
        if width <= 0 or not start - THRESHOLD_POLE_WIDTHS * width <= mass < roots[-1]:
            continue
        reach = POLE_TABLE_REACH * (mass - start) if mass > start else start - mass + THRESHOLD_POLE_WIDTHS * width
        near = mass + width * pole_offsets(width, reach)
        roots = np.union1d(roots, near[(near > roots[0]) & (near < roots[-1])])
    return roots


class UFOPortal(Portal):
    """A portal given by a UFO model (in the tools folder), its parameters set from the scan's slots."""

    family: Literal["ufo"] = "ufo"
    model_dir: str                                  # relative to the tools folder, e.g. "ufo/InertDoublet_UFO"
    dm: str                                         # the dark matter's UFO name
    partners: list[str] = Field(default_factory=list)   # coannihilating particles (UFO names)
    odd: list[str] = Field(default_factory=list)    # other particles of the dark sector, never final states
    parameters: dict[str, str] = Field(default_factory=dict)   # UFO external parameter → expression in the slots
    width_of: dict[str, str] = Field(default_factory=dict)   # UFO width parameter → its particle (computed)
    couplings: list[str] = Field(default_factory=lambda: ["g_chi", "g_q", "g_l"])   # slots that are couplings
    searches: list[str] = Field(default_factory=list)     # model-specific searches (``parameter_space.searches``)
    not_computed: list[str] = Field(default_factory=list)  # constraints that apply but are not computed (pending)
    loop_dd: str = ""                               # a loop-level scattering of ``constraints.loops`` (e.g. "2hdma")
    partial_lines: str = ""                         # why its γ-ray line rate is only partly computed: lines undecided
    spin_dm: float = 0.0
    self_conjugate_dm: bool = True
    LABELS: ClassVar[dict[str, str]] = {}
    labels: dict[str, str] = Field(default_factory=dict)

    @field_validator("parameters")
    @classmethod
    def _arithmetic_only(cls, parameters: dict[str, str]) -> dict[str, str]:
        """Each UFO parameter is set by plain arithmetic in the scan's slots (no code)."""
        for name, expression in parameters.items():
            if not name.isidentifier():
                raise ValueError(f"not a UFO parameter name: {name!r}")
            parse(expression, SLOTS)
        return parameters

    @field_validator("model_dir")
    @classmethod
    def _packaged_model(cls, model_dir: str) -> str:
        """Only the packaged library's UFO models: their files are run as code."""
        if model_dir not in MODEL_DIRS:
            raise ValueError(f"UFO model folder {model_dir!r} is not one of the packaged models {sorted(MODEL_DIRS)}")
        return model_dir

    def spin(self) -> float:
        """The dark matter's spin (``spin_dm``)."""
        return self.spin_dm

    def self_conjugate(self) -> bool:
        """Whether the dark matter is self-conjugate (``self_conjugate_dm``)."""
        return self.self_conjugate_dm

    def label(self, slot: str) -> str:
        """A slot's label from ``labels``, or the slot's own name."""
        return self.labels.get(slot, slot)

    def perturbative(self, p: Point) -> bool:
        """Whether every slot in ``couplings`` is at most 4π in magnitude."""
        return all(abs(getattr(p, s)) <= 4.0 * math.pi for s in self.couplings)

    def pending(self, p: Point) -> list[str]:
        """The entry's constraints that apply but are not computed (``not_computed``)."""
        return list(self.not_computed)

    # --- the model at a point ---------------------------------------------------------------------
    def _overrides(self, p: Point) -> dict[str, float]:
        values = {slot: getattr(p, slot) for slot in SLOTS}
        return {name: evaluate(expression, values) for name, expression in self.parameters.items()}

    def model_path(self) -> Path:
        """The UFO model's folder, resolved; refused unless it is a packaged model inside ``<tools>/ufo`` (checked
        again here, as ``model_copy`` skips the validators)."""
        self._packaged_model(self.model_dir)
        tools = get_settings().tools_dir
        path, root = (tools / self.model_dir).resolve(), (tools / "ufo").resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"the UFO model folder {self.model_dir!r} resolves outside {root}")
        return path

    def _identity(self) -> tuple:
        """What, beside the parameter values, shapes the built model and its rates: the folder, the dark matter,
        its partners and odd states, and the widths computed (release audit minor: the keys held only the first)."""
        return (self.model_dir, self.dm, tuple(self.partners), tuple(self.odd), tuple(sorted(self.width_of.items())))

    def model(self, p: Point) -> tree.Model:
        """The tree engine's model at the point: the UFO evaluated with the parameters set from the slots, the widths
        of the dark matter, its partners and ``width_of``'s particles (bosons only) computed from its vertices, and
        the Higgs boson's width into dark-sector pairs added; cached."""
        key = (*self._identity(), tuple(sorted(self._overrides(p).items())))
        if key not in _MODELS:
            if len(_MODELS) > 200:
                _MODELS.clear()
            data = ufo_model.dump(self.model_path(), self._overrides(p))
            model, dropped = ufo_model.to_model(data)
            new = [self.dm, *self.partners, *self.width_of.values()]
            names = [n for n in dict.fromkeys(new) if n in model.particles and model.particles[n].spin != 0.5]
            closed = frozenset(n for n in names if self._closed_boson(model.particles[n], model))
            for name, width in ufo_model.widths(model, names, closed).items():
                old = model.particles[name]
                model.particles[name] = replace(old, width=width)
                if old.anti:
                    model.particles[old.anti] = replace(model.particles[old.anti], width=width)
            self._add_invisible_higgs_width(model)
            _MODELS[key] = (model, dropped)
        return _MODELS[key][0]

    def _closed_boson(self, x: tree.Particle, model: tree.Model) -> bool:
        """Whether x is a new neutral, colourless, Z₂-even boson below the hadronic opening (2m_π: its current not
        classified here, so the lowest opening), its quark and gluon decays closed: its width is computed without them
        (the RX22 audit's RY23-01, 2026-10-23: the 2HDM+a's a at 0.24 GeV kept its free u, d, s widths, three
        quarters of its total, and its muon rate today was 16.6 times too small)."""
        from adroit.constraints import hadronic_window as hw
        return x.name not in self._dark(model) and x.spin != 0.5 and abs(x.pdg) not in STANDARD_BOSONS \
            and abs(x.pdg) < GHOSTS and x.colour == "1" and abs(x.charge) < 1e-9 and x.mass > 0 \
            and hw.state(x.mass) == hw.CLOSED

    def _add_invisible_higgs_width(self, model: tree.Model) -> None:
        """The 125 GeV Higgs's decays into dark-sector pairs, added to its (Standard Model) width."""
        h = next((x for x in model.particles.values() if x.pdg == 25), None)
        if h is None:
            return
        dark = sorted(self._dark(model))
        extra = 0.0
        for i, a in enumerate(dark):                     # each unordered pair once (½ for identical ones in _two_body)
            for b in dark[i:]:
                pa, pb = model.particles[a], model.particles[b]
                if pa.mass + pb.mass < h.mass:
                    extra += ufo_model._two_body(model, h, pa, pb)
        if extra > 0:
            model.particles[h.name] = replace(h, width=h.width + extra)

    # --- annihilation --------------------------------------------------------------------------------
    def _dark(self, model: tree.Model) -> set[str]:
        names = {self.dm, *self.partners, *self.odd}
        return names | {model.particles[n].conjugate for n in names if n in model.particles}

    def _finals(self, model: tree.Model, a: str, b: str, top: float) -> list[tuple[str, str]]:
        """Final pairs of a b (charge and fermion number conserved, threshold below √s = ``top``)."""
        dark = self._dark(model)
        charge = model.particles[a].charge + model.particles[b].charge
        visible = sorted((x for x in model.particles.values() if x.name not in dark and x.pdg != GLUON
                          and abs(x.pdg) < GHOSTS), key=lambda x: x.name)
        bosons = [x for x in visible if x.spin != 0.5]
        pairs = [(c, d) for i, c in enumerate(bosons) for d in bosons[i:]]
        pairs += [(f, g) for f in visible if f.spin == 0.5 and f.pdg > 0 for g in visible if g.spin == 0.5 and g.pdg < 0]
        return [(c.name, d.name) for c, d in pairs if abs(c.charge + d.charge - charge) < 1e-6 and c.mass + d.mass < top]

    def _sigma(self, p: Point, a: str, b: str) -> Callable[[np.ndarray], np.ndarray]:
        """σ(a b → any SM pair)(s), tabulated in √s from threshold: the total, and the total without the quark and
        gluon final states, which alone is read below the hadronic opening, at every √s (the re-audit's RR22-02,
        2026-10-22: one table, closed only at its nodes, interpolated partons back across the opening, 2.8% at
        0.279139 GeV). A node at the opening starts the open side's interpolation there: where the initial pair's
        threshold lies below 2m_π, the interval just above the opening is interpolated from that node (the parton
        channels open there, where the old table had interpolated across from a closed node; RV22-04). A table whose
        initial threshold is at or above 2m_π gets no such node and is tabulated and read as before."""
        model = self.model(p)
        key = (*self._identity(), tuple(sorted(self._overrides(p).items())), a, b)
        if key not in _SIGMA:
            if len(_SIGMA) > 2000:
                _SIGMA.clear()
            start = model.particles[a].mass + model.particles[b].mass
            roots = table_roots(start, [(x.mass, x.width) for x in model.particles.values() if x.spin != 0.5])
            opening = hadronic_window.opening(False)    # quarks and gluons closed below it (RC21-01, RR22-02)
            if roots[0] < opening < roots[-1]:
                roots = np.union1d(roots, [opening])
            finals = self._finals(model, a, b, roots[-1])
            for c, d in finals:                          # each channel's opening within the thermal reach (AL3-04)
                opens = model.particles[c].mass + model.particles[d].mass
                if roots[0] < opens < roots[0] * (1.0 + OPENING_REACH):
                    near = opens * (1.0 + OPENING_STEPS)
                    roots = np.union1d(roots, near[(near > roots[0]) & (near < roots[-1])])
            processes = []
            for c, d in finals:
                try:
                    processes.append(tree.Process(model, a, b, c, d, points=16))
                except ValueError:
                    continue
            partonic = [_partonic(proc) for proc in processes]
            loops = higgs_loops(model, a, b)
            totals, others = [], []
            for r in roots:
                sigmas = [off_shell_sigma(proc, r * r) if r >= opening or not q else 0.0
                          for proc, q in zip(processes, partonic)]
                extra = {k: v for k, v in (loops(r * r) if loops is not None else {}).items()
                         if r >= opening or not HIGGS_LOOPS[k]}
                totals.append(sum(sigmas) + sum(extra.values()))
                others.append(sum(x for x, q in zip(sigmas, partonic) if not q)
                              + sum(v for k, v in extra.items() if not HIGGS_LOOPS[k]))
            _SIGMA[key] = (roots, np.array(totals), np.array(others), opening)
        roots, totals, others, opening = _SIGMA[key]

        def table(values, root):
            logged = np.exp(np.interp(root, roots, np.log(np.maximum(values, 1e-300))))     # smooth across poles
            return np.where(logged > 1e-299, logged, 0.0)

        def sigma(s):
            root = np.sqrt(np.asarray(s, dtype=float))
            closed = root < opening                    # below 2m_π the table without the partons, at every √s
            return np.where(root > roots[0], np.where(closed, table(others, root), table(totals, root)), 0.0)
        return sigma

    def domain(self, p: Point) -> str:
        """Why Ωh² is not computed (the owner's hadronic-validity decision, 2026-10-20; the current not classified
        here, so its window reaches 3 GeV), or "": a pair of the relic's bath (``_bath``: the dark matter, its
        partners and their conjugates, as ``coannihilation`` integrates them) annihilating into quarks or gluons at
        its threshold in the window, or with a coloured state at or below 3 GeV; or a light boson whose hadronic width
        is not computed moving the s-channel propagator of a bath pair (``hadronic_window.propagator_insensitive``).
        The RV22 audit's RX22-02 (2026-10-22): the dark matter's pair alone was checked, so the inert doublet's light
        charged partners (H⁺H⁻ → uū at 0.32 GeV) and the 2HDM+a's light a, its width free partons', had an Ωh²."""
        model = self.model(p)
        dm = model.particles[self.dm]
        pairs = [(dm.name, dm.conjugate)] + [pair for pair in self._bath_pairs(model)
                                            if sorted(pair) != sorted((dm.name, dm.conjugate))]
        for a, b in pairs:
            if why := self._pair_reason(model, a, b):
                return why if (a, b) == pairs[0] else f"{why} ({a} {b}, coannihilating)"
        return self._propagator_reason(model, pairs) or self._resolution_reason(model, pairs)

    def _resolution_reason(self, model: tree.Model, pairs: list[tuple[str, str]]) -> str:
        """Why a pair's σ table cannot resolve an s-channel pole near its threshold (``threshold_scale`` below
        ``SCALE_RESOLVED``: the tree amplitudes vanish within 10⁻¹² of the threshold), or "" (AL5-01)."""
        for a, b in pairs:
            start = model.particles[a].mass + model.particles[b].mass
            for x in model.particles.values():
                scale = threshold_scale(start, x.mass, x.width) if x.spin != 0.5 else None
                if scale is not None and scale < SCALE_RESOLVED:
                    return (f"the s-channel resonance {x.name} at {x.mass:.9g} GeV, of width {x.width:.3g} GeV, lies "
                            f"within {scale:.2g} of the {a} {b} threshold at {start:.9g} GeV (in √s/threshold − 1), "
                            f"closer than the tree amplitudes resolve ({SCALE_RESOLVED:g}): Ωh² is not computed")
        return ""

    def today_unknown(self, p: Point) -> str:
        """The same, for annihilation today, of the dark matter's pair (its channels summed as one, so none is
        computed without the quarks), its propagators at s = 4m_χ² (RX22-02)."""
        model = self.model(p)
        dm = model.particles[self.dm]
        return self._pair_reason(model, dm.name, dm.conjugate) or \
            self._propagator_reason(model, [(dm.name, dm.conjugate)], fixed=True)

    def _bath(self, model: tree.Model) -> list[str]:
        """The relic's species: the dark matter and its partners, each with its conjugate."""
        return [name for n in [self.dm, *self.partners] for name in dict.fromkeys([n, model.particles[n].conjugate])]

    def _bath_pairs(self, model: tree.Model) -> list[tuple[str, str]]:
        """Every pair of the relic's species, as ``coannihilation`` gives the solver."""
        labels = self._bath(model)
        return [(labels[i], labels[j]) for i in range(len(labels)) for j in range(i, len(labels))]

    def _pair_reason(self, model: tree.Model, a: str, b: str) -> str:
        """Why the pair's annihilation at its threshold is not computed: a coloured state in it at or below 3 GeV
        (confined into hadrons, as the library's ``TChannel`` and the generic route), or its quark or gluon final
        states in the window; else ""."""
        from adroit.constraints import hadronic_window as hw
        pa, pb = model.particles[a], model.particles[b]
        root_s = pa.mass + pb.mass
        if root_s > hw.TOP:
            return ""
        if pa.colour != "1" or pb.colour != "1":
            return (f"the coloured state's pair {a} {b} annihilates from √s = {root_s:.4g} GeV, at or below "
                    f"{hw.TOP:g} GeV, where coloured states are confined into hadrons: its free-parton rates do not "
                    "establish them (ADROIT's hadronic-validity policy); not computed")
        if hw.state(root_s, vector=False, annihilation=True) != hw.UNKNOWN:
            return ""
        if not any(abs(model.particles[x].pdg) in PARTONS for pair in self._finals(model, a, b, hw.TOP) for x in pair):
            return ""
        return hw.annihilation_reason(root_s, False, False)

    def _windowed(self, model: tree.Model) -> dict[str, str]:
        """Each new neutral, colourless, Z₂-even boson in its hadronic window with an open quark or gluon decay (its
        width, where computed here, is free partons'), with why its hadronic width is not established; the current
        not classified, so from 2m_π to 3 GeV."""
        from adroit.constraints import hadronic_window as hw
        dark = self._dark(model)
        out = {}
        for x in model.particles.values():
            if x.name in dark or x.spin == 0.5 or abs(x.pdg) in STANDARD_BOSONS or abs(x.pdg) >= GHOSTS \
                    or x.colour != "1" or abs(x.charge) > 1e-9 or x.mass <= 0 or x.mass > hw.TOP \
                    or hw.state(x.mass) != hw.UNKNOWN:
                continue
            for v in model.vertices:
                rest = [leg for leg in v.legs if leg != x.name]
                if len(v.legs) == 3 and len(rest) == 2 and all(abs(model.particles[o].pdg) in PARTONS for o in rest) \
                        and sum(model.particles[o].mass for o in rest) < x.mass:
                    out[x.name] = hw.decay_reason(x.name, x.mass, False, False)
                    break
        return out

    def _propagator_reason(self, model: tree.Model, pairs: list[tuple[str, str]], fixed: bool = False) -> str:
        """Why a windowed boson's uncomputed width (``_windowed``; its declared bound Γ_had ≤ m) can move the
        s-channel propagator of a pair, at its threshold and above (at s = its threshold² alone, ``fixed``), or ""."""
        from collections import Counter

        from adroit.constraints import hadronic_window as hw
        unknown = self._windowed(model)
        if not unknown:
            return ""
        for a, b in pairs:
            s0 = (model.particles[a].mass + model.particles[b].mass) ** 2
            pair = Counter((a, b))
            for v in model.vertices:
                legs = Counter(v.legs)
                if len(v.legs) != 3 or sum((legs & pair).values()) != 2:
                    continue
                (x,) = legs - pair
                if x in unknown:
                    mx = model.particles[x].mass
                    if not hw.propagator_insensitive(s0, mx, model.particles[x].width + mx, fixed=fixed):
                        return (f"{unknown[x]}, and it moves the s-channel propagator of {a} {b} at √s "
                                f"{'=' if fixed else '≥'} {s0 ** 0.5:.4g} GeV")
        return ""

    def channels(self, s, p: Point) -> dict[str, np.ndarray]:
        """σ(DM DM̄ → any Standard Model pair)(s) in GeV⁻², summed over the tree processes as one channel named all."""
        model = self.model(p)
        dm = model.particles[self.dm]
        return {"all": self._sigma(p, dm.name, dm.conjugate)(s)}

    def sigma_v_today(self, p: Point, v_rel: float) -> dict[str, float]:
        """σv today by final state (each process separately), with a final W or Z off shell near and below its
        threshold (``off_shell_sigma``), as Ωh²'s tables have it (``_sigma``): a pair of them opens from √s above one
        boson's mass (the audit loop's AL2-18, 2026-11-14: on-shell pairs only, the inert doublet at 72 GeV had today
        b, c, τ, μ and s, 8.7 × 10⁻³⁰ cm³/s, for the W W* its relic density has, 1.3 × 10⁻²⁶); and the Higgs's
        loop-induced g g, γ γ and Z γ where the pair reaches it (``higgs_loops``)."""
        from adroit.constraints.annihilation import GEV2_TO_CM3_S
        model = self.model(p)
        dm = model.particles[self.dm]
        s = 4.0 * p.m_chi ** 2 / (1.0 - (0.5 * v_rel) ** 2)
        out = {}
        closed = math.sqrt(s) < hadronic_window.opening(False)          # quarks and gluons closed (RC21-01)
        for c, d in self._finals(model, dm.name, dm.conjugate, 2.0 * math.sqrt(s)):     # V V* opens below 2 m_V
            try:
                proc = tree.Process(model, dm.name, dm.conjugate, c, d, points=12)
            except ValueError:
                continue
            if closed and _partonic(proc):
                continue
            value = off_shell_sigma(proc, s) * v_rel * GEV2_TO_CM3_S
            if value > 0:
                name = channel_name(model.particles[c], model.particles[d])
                out[name] = out.get(name, 0.0) + value
        loops = higgs_loops(model, dm.name, dm.conjugate)          # the Higgs's g g, γ γ and Z γ (AL3-05)
        for name, sigma in (loops(s) if loops is not None else {}).items():
            if sigma > 0 and not (closed and HIGGS_LOOPS[name]):
                out[name] = out.get(name, 0.0) + sigma * v_rel * GEV2_TO_CM3_S
        return out

    def coannihilation(self, p: Point):
        """The dark matter, its partners and their conjugates as species (dof by spin), with σ(s) of every pair from
        the tree engine."""
        model = self.model(p)
        labels = self._bath(model)                    # the species the domain's checks see (RX22-02)
        species = [relic.Species(model.particles[n].mass, {0.0: 1.0, 0.5: 2.0, 1.0: 3.0}[model.particles[n].spin])
                   for n in labels]
        pairs = {(i, j): self._sigma(p, labels[i], labels[j]) for i in range(len(labels)) for j in range(i, len(labels))}
        return species, pairs

    def resonances(self, p: Point) -> list[tuple[float, float]]:
        """The poles (mass, width) of every boson of the model with a mass and a width."""
        model = self.model(p)
        return [(x.mass, x.width) for x in model.particles.values() if x.spin != 0.5 and x.mass > 0 and x.width > 0]

    def _higgs(self, model: tree.Model) -> tree.Particle | None:
        return next((x for x in model.particles.values() if x.pdg == 25), None)

    def invisible(self, p: Point) -> dict[str, float]:
        """Γ(h → DM DM̄) (GeV) from the model's vertices, below m_DM = m_h/2."""
        model = self.model(p)
        dm = model.particles[self.dm]
        h = self._higgs(model)
        if h is None or 2.0 * dm.mass >= h.mass:
            return {}
        width = ufo_model._two_body(model, h, dm, model.particles[dm.conjugate])
        return {"h": width} if width > 0 else {}

    def nucleon(self, p: Point) -> Nucleon:
        """Spin-independent scattering through the Higgs boson (scalar dark matter), at tree level."""
        if self.loop_dd == "2hdma":
            return self._two_hdma_nucleon(p)
        model = self.model(p)
        dm = model.particles[self.dm]
        if dm.spin != 0.0:
            return Nucleon(suppressed="loop-induced (not computed)")
        h = self._higgs(model)
        found = model.find([dm.name, dm.conjugate, h.name]) if h else []
        if not found:
            return Nucleon(suppressed="no tree-level Higgs exchange")
        v_ssh = found[0][0].c.real
        c = -v_ssh * F_N * M_NUCLEON / (2.0 * 246.22 * h.mass ** 2 * dm.mass)
        return Nucleon(c1_p=c, c1_n=c)


    def _two_hdma_nucleon(self, p: Point) -> Nucleon:
        """The 2HDM+a's spin-independent scattering through the h and H triangles (``loops.two_hdma_si``)."""
        x = self._overrides(p)
        c_p, c_n = loops.two_hdma_si(x["MXd"], x["mh4"], x["mh3"], x["mh2"], x["mhc"], x["sinp"], x["tanbeta"],
                                     x["lam3"], x["laP1"], x["laP2"], x["gPXd"])
        return Nucleon(c1_p=c_p, c1_n=c_n)


def _breit_wigner(x: tree.Particle, root: float, splits: tuple[float, ...] = ()) -> list[tuple[float, float]]:
    """(mass, weight) nodes of a W or Z's Breit–Wigner from 1 GeV to √s.

    The weight is (1/π) m Γ(m)/((m² − M²)² + M²Γ²) dm² with the running width Γ(m) = Γ m/M of a vector decaying into
    massless fermions. Within ``POLE_REACH`` widths of the pole it is integrated in u = arctan((m² − M²)/MΓ), where it
    is (m/M)² du/π; each tail beyond is a segment of its own, integrated in m², where it is smooth (up to the kinematic
    limit √s − m₁, as m² = b² − (b² − a²)t², which takes the phase space's square root). (One rule over the
    whole range left the far tail, a fraction of a percent of u, without a node: there the other boson can be on its
    shell, so χχ → VV* lost about half its rate below the VV threshold. G6, 2026-10-14.) ``splits`` adds edges: the outer
    integral is split where the other boson's resonance enters its range, √s − M₂ (± ``POLE_REACH`` widths).
    """
    low, high = 1.0, root
    if high <= low:
        return []
    mg = x.mass * x.width
    edges = sorted({low, high, *(m for m in (x.mass - POLE_REACH * x.width, x.mass + POLE_REACH * x.width, *splits)
                                 if low < m < high)})
    nodes, weights = tree.gauss(BW_NODES)
    out: list[tuple[float, float]] = []
    for a, b in zip(edges[:-1], edges[1:]):
        if a >= x.mass - POLE_REACH * x.width and b <= x.mass + POLE_REACH * x.width:
            u_a, u_b = (math.atan((m * m - x.mass ** 2) / mg) for m in (a, b))
            if b == high:                        # the kinematic limit: u = u_b − (u_b − u_a)t²
                t = 0.5 * nodes + 0.5
                u = u_b - (u_b - u_a) * t * t
                jacobian = 0.5 * weights * 2 * (u_b - u_a) * t
            else:
                u = 0.5 * (u_b - u_a) * nodes + 0.5 * (u_b + u_a)
                jacobian = 0.5 * (u_b - u_a) * weights
            masses = np.sqrt(x.mass ** 2 + mg * np.tan(u))
            w = jacobian / math.pi * (masses / x.mass) ** 2
        elif b == high:                          # up to the kinematic limit: q = b² − (b² − a²)t² takes its √
            t = 0.5 * nodes + 0.5
            q = b * b - (b * b - a * a) * t * t
            masses = np.sqrt(q)
            w = 0.5 * weights * 2 * (b * b - a * a) * t / math.pi * (x.width * q / x.mass) / \
                ((q - x.mass ** 2) ** 2 + mg ** 2)
        else:
            q = 0.5 * (b * b - a * a) * nodes + 0.5 * (b * b + a * a)
            masses = np.sqrt(q)
            w = 0.5 * (b * b - a * a) * weights / math.pi * (x.width * q / x.mass) / ((q - x.mass ** 2) ** 2 + mg ** 2)
        out += list(zip(masses.tolist(), w.tolist()))
    return out


def off_shell_sigma(proc: tree.Process, s: float) -> float:
    """σ(s) with final W and Z bosons off shell near and below threshold (a Breit–Wigner for each, running
    width; V V* → V f f̄′ and V* V* → 4f), and on shell above ``OFF_SHELL_REACH`` widths."""
    final = proc.p[2:]
    vectors = [x for x in final if abs(x.pdg) in OFF_SHELL and x.width > 0]
    root = math.sqrt(s)
    if not vectors or root > sum(x.mass for x in final) + OFF_SHELL_REACH * sum(x.width for x in vectors):
        return proc.sigma(s)
    first, second = final
    masses, weights = [], []
    splits = tuple(root - second.mass + k * POLE_REACH * second.width for k in (-1, 0, 1)) if second in vectors else ()
    for m1, w1 in (_breit_wigner(first, root - 1.0, splits) if first in vectors else [(first.mass, 1.0)]):
        reach = root - m1 - 1e-3                    # the second boson's masses that fit: the nested range
        if reach <= 1.0:
            continue
        nodes = _breit_wigner(second, reach) if second in vectors else ([(second.mass, 1.0)] if second.mass < reach else [])
        masses += [(m1, m2) for m2, _ in nodes]
        weights += [w1 * w2 for _, w2 in nodes]
    if not masses:
        return 0.0
    return float(np.sum(np.array(weights) * proc.sigma_offshell(s, np.array(masses))))   # every node at once (F2)


def _partonic(process: tree.Process) -> bool:
    """Whether a process's final state is quarks and gluons only."""
    return all(abs(x.pdg) in (1, 2, 3, 4, 5, 6, GLUON) for x in process.p[2:])


def channel_name(c: tree.Particle, d: tree.Particle) -> str:
    """The final state's name as the indirect-detection records know it (``base.FERMI``).

    Standard Model pairs retain their PDG identity. New-particle final states
    stay explicitly labelled cascades until their spectra have been calculated.
    """
    codes = sorted((abs(c.pdg), abs(d.pdg)))
    if c.spin == 0.5 and codes[0] == codes[1] and codes[0] in SM_NAMES:
        return SM_NAMES[codes[0]]
    pairs = {(24, 24): "W", (23, 23): "Z", (25, 25): "hh", (23, 25): "Zh", (22, 22): "aa_photons",
             (22, 23): "Zgamma"}
    if tuple(codes) in pairs:
        return pairs[tuple(codes)]
    if c.spin == 0.5:
        return "ff'"
    return f"cascade({codes[0]},{codes[1]})"
