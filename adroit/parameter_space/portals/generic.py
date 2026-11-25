"""The generic engine (G4): any typed model's relic density from its own Feynman rules, where the library has no
engine for it.

At each parameter point the model is rebuilt in four steps:
1. the stated parameter is set (``scan`` ← m_χ, ``tied`` ← m_med);
2. G1's spectrum (``model_building.spectrum``);
3. G2's Feynman rules (``model_building.feynman``);
4. G3's tree-level 2 → 2 engine (``constraints.tree``).

**The bath** is the dark matter and every Z₂-odd state within 30% of its mass (e^{−Δm x_f/m} ≳ 10⁻³ at x_f ≈ 25).
A particle and its antiparticle are two species.
- **Each pair's σ_ij(s)** is the sum over every final pair of Z₂-even particles that the tree engine finds diagrams
  for: odd–odd → even–even. A conversion between odd states keeps the bath in chemical equilibrium and is not a
  loss.
- **The tabulation:** σ·β is tabulated in u = √s/(m_i + m_j) − 1 on log-spaced nodes, with nodes added around every
  s-channel pole and final-state threshold, and is interpolated.
- **The relic density** is ``relic.omega_h2_species``: the Edsjö–Gondolo effective rate with the Gondolo–Gelmini
  average.

**Long-range effects** (G7, ``generic_lr``). The bath's multiplets that a long-range force joins (SU(2), U(1)_Y,
SU(3), a new mediator) are decomposed into irreducible channels from G3's own amplitudes: the potential from
elastic exchange in the symmetric limit, the hard rates from the annihilation matrix at threshold. Each channel's
s-wave rate takes its Sommerfeld factor, and bound states form where G7 has their capture (pure SU(2) multiplets of
spin 0 or ½; colour-triplet scalars); both enter Ωh² as thermal rates of the bath's pairs. Where G7 cannot
decompose a group (mixed states, vector multiplets, n > 5), G4's bracket decides as before (decision D4): if its
centre moves Ωh² by more than 10%, Ωh² is refused with ``sommerfeld`` (the default), and
``long_range = "estimate"`` adds the perturbative Ωh² and the bracket to the flags. ``bound_states = False`` leaves
out the bound states; ``sommerfeld = False`` computes the perturbative value: an author's own perturbative
treatment, which the zoo compares with.

**Certificates** (``flags``): the coannihilators' chemical equilibrium, the kinetic contact of new final states with
the Standard Model, and new states light enough to add to g*. Final W and Z bosons are taken off shell near and below
threshold (``ufo.off_shell_sigma``).

**Direct detection** (G5, ``generic_dd``): the tree-level matching of G2's vertices onto DirectDM's basis, the loop
library where it vanishes, inelastic scattering, and the fallback "loop-dominated, not computed".

**Annihilation today** (G6, ``generic_id``): σv by final state in the searches' channels, two-body cascades through
new states with boosted PPPC spectra, the CMB's f_eff, lines flagged; undecided where long-range effects today matter
(G8).

**Long-range effects today** (G8, ``generic_today``): where they matter at the dwarfs' speed and G7 has decomposed
the dark-matter pair's group, today's σv comes from the broken-phase multi-state Sommerfeld effect, with the
potentials boson by boson and the annihilation matrices by final state from G3, and the one-loop splittings of an
electroweak multiplet; its γ-ray lines are undecided where no resummed rate applies (``lines_upper_bound``).

**Colliders** (G9, ``generic_lhc``): an SLHA spectrum from G1 and G2 for SModelS with production from the LHC SUSY
Cross Section Working Group's tables by quantum numbers (else undecided, with the reason), and the Higgs's signal
strength where the h mixes with a new scalar.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import ClassVar, Literal

import numpy as np

from adroit.constraints import relic
from adroit.core.model_spec import ModelSpec
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.base import Nucleon, Portal

BATH = 1.3                        # odd states below 1.3 m_χ coannihilate
U_MAX = 25.0                      # √s/(m_i + m_j) − 1 beyond which the thermal weight vanishes
NODES = 36
ANGLES = 16                       # Gauss points in cos θ per tabulated σ (as ``UFOPortal``)
PENDING: list[str] = []                       # the LHC is decided, or undecided with its reason (G9, ``generic_lhc``)
M_PION = 0.13957                  # GeV: quarks and gluons open only as hadrons, from 2 m_π (``_table``)
PARTONIC_FROM = 2.0               # GeV: √s above which hadrons are computed as free quarks and gluons
PARTONS = {1, 2, 3, 4, 5, 6, 21}


class GenericModel(Portal):
    """A typed model computed from its own Feynman rules (module docstring)."""

    family: Literal["generic"] = "generic"
    spec_json: str                                   # the model (ModelSpec as JSON) at its benchmark
    scan: str = ""                                   # what m_χ sets: a field's mass or a coupling ("" the DM field's)
    tied: str = ""                                   # what m_med sets ("" nothing)
    sommerfeld: bool = True                          # refuse where long-range effects matter (no module yet)
    bound_states: bool = True
    long_range: Literal["refuse", "estimate"] = "refuse"
    generations: tuple[str, ...] = ()                # the stated fields of several generations, expanded (``of``)
    LABELS: ClassVar[dict[str, str]] = {"m_chi": "m_χ (GeV)", "m_med": "m_med (GeV)"}

    @classmethod
    def of(cls, spec: ModelSpec, **kwargs) -> "GenericModel":
        """The engine for a typed model: a new field of several generations written as that many fields
        (``model_building.generations``), which the stability and thermal-history checks then judge (``domain``)."""
        from adroit.model_building import generations
        many = tuple(f.name for f in spec.fields if f.role.value != "standard_model" and f.generations > 1)
        if many:
            spec = generations.expand(spec)
            kwargs["generations"] = tuple(dict.fromkeys(kwargs.get("generations", ()) + many))
        return cls(name=spec.name, spec_json=spec.model_dump_json(), **kwargs)

    @classmethod
    def for_spec(cls, spec: ModelSpec, **kwargs) -> "GenericModel":
        """The engine with m_med tied to the model's single mediator, where it has one with a stated mass (else m_med
        is not a coordinate of the model: ``scan_setup.active_coordinates``). The audit's G3/G4-3 (G12): a model the
        library refuses had reached the generic route with an inert m_med axis."""
        from adroit.model_building import generations
        mediators = [f for f in generations.expand(spec).fields if f.role.value == "mediator"]
        tied = mediators[0].name if len(mediators) == 1 and mediators[0].mass_gev is not None else ""
        return cls.of(spec, tied=tied, **kwargs)

    def model_spec(self) -> ModelSpec:
        """The stated model."""
        return ModelSpec.model_validate_json(self.spec_json)

    def point(self) -> Point:
        """The stated benchmark as a point: m_χ the scanned parameter, m_med the tied one."""
        spec = self.model_spec()
        return Point(m_chi=_read(spec, self.scan or _dm_field(spec)), m_med=_read(spec, self.tied) if self.tied else 1.0)

    # --- the model at a point ----------------------------------------------------------------------
    def at(self, p: Point):
        """(spectrum's mass basis, rules, tree model) at the point (cached)."""
        return _built(self.spec_json, self.scan, self.tied, p.m_chi, p.m_med)

    def spin(self) -> float:
        return self.at(self.point())[0].spectrum.dark_matter().spin

    def self_conjugate(self) -> bool:
        return self.at(self.point())[0].spectrum.dark_matter().kind in ("real", "majorana", "vector")

    def domain(self, p: Point) -> str:
        """Why Ωh² is not computed: the model cannot be built, or long-range effects matter where G7 does not
        compute them (module docstring)."""
        try:
            mb, rules, model = self.at(p)
        except ValueError as error:
            return f"the generic route cannot build the model: {error}"
        if why := _feeble(self.spec_json, self.scan, self.tied, p.m_chi, p.m_med):
            return why
        if why := _charged_relic(rules) or _light_higgs(mb, rules) or _hadronic_window(mb, rules, model) \
                or _no_channel(mb, rules, model) or _contact_validity(mb, rules):
            return why
        if why := _components(mb, rules) or self._thermal_history(p, mb, rules, model) or \
                _unresolved_pole(mb, rules, model):
            return why
        if self.sommerfeld:
            found = self.long_range_effects(p)
            if found.refused:
                from adroit.parameter_space.portals import generic_checks
                why = generic_checks.long_range_reason(self.estimate(p))
                return f"{why}; G7 does not compute it here: {'; '.join(found.refused)}" if why else ""
        return ""

    def _thermal_history(self, p: Point, mb, rules, model) -> str:
        """``_thermal_history`` at the point's freeze-out; "" where x_f is not computed (``domain``'s other reasons)."""
        x_f = _freeze_out(self.spec_json, self.scan, self.tied, p.m_chi, p.m_med)
        return _thermal_history(mb, rules, model, x_f) if x_f is not None else ""

    def dark_matter_mass(self, p: Point) -> float:
        """The dark matter's physical mass at the point (``searches.dm_mass``): G1's, which mixing and a vacuum value
        shift from the stated Lagrangian mass m_χ sets."""
        return self.at(p)[0].spectrum.dark_matter().mass_gev

    def long_range_effects(self, p: Point):
        """G7's analysis of the bath (``generic_lr.LongRange``): the groups whose Sommerfeld effect and bound
        states it computes, and the groups it refuses."""
        return _long_range(self.spec_json, self.scan, self.tied, p.m_chi, p.m_med)

    def thermal_pairs(self, p: Point) -> dict:
        """G7's Sommerfeld corrections and bound states, as rates of the bath's pairs (``relic.omega_h2_species``)."""
        if not self.sommerfeld or self.domain(p):
            return {}
        from adroit.parameter_space.portals import generic_lr
        bath, _, _, _ = _bath(self.spec_json, self.scan, self.tied, p.m_chi, p.m_med)
        return generic_lr.thermal_rates(self.long_range_effects(p), bath, self.bound_states)

    def estimate(self, p: Point):
        """The Sommerfeld bracket of the bath (``long_range_bracket.Bracket``), or None where no long-range force
        acts. It never reaches a verdict."""
        return _estimate(self.spec_json, self.scan, self.tied, p.m_chi, p.m_med)

    def flags(self, p: Point) -> list[str]:
        """The estimate on request, and the certificates of freeze-out's assumptions (module docstring)."""
        from adroit.parameter_space.portals import generic_checks as gc
        try:
            mb, rules, model = self.at(p)
        except ValueError:
            return []
        out = []
        if self.sommerfeld:
            found = self.long_range_effects(p)
            out += _long_range_flags(found, self.bound_states)
            b = self.estimate(p) if found.refused else None
            refused = bool(gc.long_range_reason(b))
            if b is not None and (self.long_range == "estimate" or not refused) and \
                    max(b.omega_perturbative / b.omega_low, b.omega_high / b.omega_perturbative) > 1 + gc.LONG_RANGE_SHIFT:
                out.append(gc.estimate_flag(b, refused))
        else:
            out.append("perturbative Ωh² by request: the Sommerfeld effect and bound states are left out")
        x_f = _freeze_out(self.spec_json, self.scan, self.tied, p.m_chi, p.m_med)
        if x_f is not None:
            bath, _, _, finals = _bath(self.spec_json, self.scan, self.tied, p.m_chi, p.m_med)
            m = mb.spectrum.dark_matter().mass_gev
            out += gc.kinetic_flags(rules, finals, x_f, m)
            out += gc.light_state_flags(rules, x_f, m)
        dm = mb.spectrum.dark_matter()
        anti = dm.name if dm.kind in ("real", "majorana", "vector") else f"{dm.name}~"
        out += gc.three_body_flags(model, final_states(model, dm.name, anti), dm.mass_gev)
        found = self.scattering(p)
        out += [f"direct detection ({found.route}): {note}" for note in found.notes]
        from adroit.parameter_space.portals import generic_id, generic_regimes
        try:                                                                                        # D35
            out += [f"{generic_regimes.QUALIFICATION}: {r}" for r in generic_regimes.regimes(self, p)]
        except (ValueError, RuntimeError, ArithmeticError) as error:
            out.append(f"{generic_regimes.QUALIFICATION}: the regime check could not be computed ({error})")
        lines = generic_id.lines_flag(mb, rules)
        contact = _contact_flag(mb, rules)
        return out + [flag for flag in (lines, contact) if flag]

    def invisible(self, p: Point) -> dict[str, float]:
        """Γ(h → DM DM̄) and Γ(Z → DM DM̄) where they are open."""
        from adroit.parameter_space.portals.generic_checks import invisible_widths
        mb, rules, _ = self.at(p)
        dm = mb.spectrum.dark_matter()
        return invisible_widths(rules, dm.name, dm.name if dm.kind in ("real", "majorana", "vector") else f"{dm.name}~")

    def resonances(self, p: Point) -> list[tuple[float, float]]:
        """Every Z₂-even boson with a width: the s-channel poles."""
        return _poles(self.at(p)[1])

    def annihilation_poles(self, p: Point) -> list[tuple[float, float]]:
        """The poles of the dark matter pair's own s-channel (``_exchanged``), whose velocity scales the CMB's rate
        reads (``constraints.searches.velocity_scales``, AL7-01)."""
        mb, rules, model = self.at(p)
        dm = mb.spectrum.dark_matter()
        anti = dm.name if dm.kind in ("real", "majorana", "vector") else f"{dm.name}~"
        return _exchanged(model, dm.name, anti, rules)

    def coannihilation(self, p: Point) -> tuple[list, dict]:
        """The bath and every pair's σ_ij(s) (module docstring)."""
        _, species, pairs, _ = _bath(self.spec_json, self.scan, self.tied, p.m_chi, p.m_med)
        return species, pairs

    def channels(self, s: np.ndarray, p: Point) -> dict[str, np.ndarray]:
        """σ(DM DM̄ → c d)(s) by final state, for annihilation today (G6 reads it)."""
        mb, rules, model = self.at(p)
        dm = mb.spectrum.dark_matter()
        anti = dm.name if dm.kind in ("real", "majorana", "vector") else f"{dm.name}~"
        out = {}
        for c, d in final_states(model, dm.name, anti):
            out[f"{c} {d}"] = _tabulate(model, dm.name, anti, (c, d), _s_channel(model, dm.name, anti, rules))(
                np.asarray(s, float))
        return out

    def scattering(self, p: Point):
        """Direct detection at the point (``generic_dd.scattering``: tree level, loop library, inelastic, fallback)."""
        return _scattering(self.spec_json, self.scan, self.tied, p.m_chi, p.m_med)

    def nucleon(self, p: Point) -> Nucleon:
        try:
            return self.scattering(p).nucleon
        except ValueError as error:
            return Nucleon(suppressed=f"not computed: the model cannot be built ({error})")

    def dd(self, p: Point) -> tuple[str, float]:
        """("inelastic", 0) where the only scattering is inelastic (compared through Path 1); else the channel that
        decides."""
        found = self.scattering(p)
        if found.inelastic and found.route == "inelastic":
            return "inelastic", 0.0
        return super().dd(p)

    def dd_channels(self, p: Point) -> list:
        """The channels, not computable where the contact limit fails (a mediator below about 1 GeV)."""
        from adroit.parameter_space import dd_channels
        found = self.scattering(p)
        n = found.nucleon
        if n.structure:
            return []
        contact = [x for x in found.notes if "contact limit" in x]
        return dd_channels.channels_of(n.c1_p, n.c1_n, n.c4_p, n.c4_n, self.dark_matter_mass(p),
                                       unreliable=contact[0] if contact else "", c1_odd=(n.c1_p_odd, n.c1_n_odd))

    def interaction(self, p: Point):
        """DirectDM's full nonrelativistic interaction of the tree-level coefficients (for Path 1), else the base
        one from ``nucleon``."""
        from adroit.parameter_space.portals import generic_dd
        found = self.scattering(p)
        full = generic_dd.interaction(found.matching, self.name or "generic") if found.route == "tree" else None
        return full[1] if full else super().interaction(p)

    def pending(self, p: Point) -> list[str]:
        try:
            return self.scattering(p).pending + list(PENDING)
        except ValueError:
            return ["direct detection: not computed (the model cannot be built)"] + list(PENDING)

    # --- colliders (G9, ``generic_lhc``) ----------------------------------------------------------------------
    def lhc_spectrum(self, p: Point) -> tuple[str, float | None, str]:
        """(SLHA, σ in pb, why not) for SModelS (``generic_lhc.lhc_spectrum``)."""
        from adroit.parameter_space.portals import generic_lhc
        try:
            mb, rules, _ = self.at(p)
        except ValueError as error:
            return "", None, f"the model cannot be built: {error}"
        return generic_lhc.lhc_spectrum(mb, rules)

    def higgs_mu_reason(self, p: Point) -> str:
        """Why the 125 GeV state's signal strength is not computed (``generic_lhc.higgs_mu_reason``: the state at the
        measured mass not one, or not a universal rescaling of the SM Higgs), or ""."""
        from adroit.parameter_space.portals import generic_lhc
        try:
            mb, rules, _ = self.at(p)
        except ValueError:
            return ""
        return generic_lhc.higgs_mu_reason(mb, rules)

    def higgs_mu(self, p: Point) -> float | None:
        """The 125 GeV state's signal strength where it mixes with a new scalar (``generic_lhc.higgs_mu``)."""
        from adroit.parameter_space.portals import generic_lhc
        try:
            mb, rules, _ = self.at(p)
        except ValueError:
            return None
        return generic_lhc.higgs_mu(mb, rules)

    # --- annihilation today (G6, ``generic_id``) ---------------------------------------------------------
    def sigma_v_today(self, p: Point, v_rel: float) -> dict[str, float]:
        """σv (cm³/s) by channel at relative speed v_rel: Standard Model pairs by the searches' names, cascades by
        their particles; with the broken-phase Sommerfeld effect where long-range forces act today and G8 computes
        them (``generic_today``). The channels with a quark or gluon are closed (zero) below the hadronic opening, as
        in Ωh²'s tables (``generic_hadronic.today_closed``, C21-02), and where ``today_hadronic`` gives a reason they
        are left out (not computed, not zero)."""
        from adroit.parameter_space.portals import generic_hadronic as gh
        rates = dict(_today(self.spec_json, self.scan, self.tied, p.m_chi, p.m_med, float(v_rel), self.sommerfeld))
        if not self.today_hadronic(p) and not gh.today_closed(*self.at(p)[:2]):
            return rates
        partons = {"u", "d", "s", "c", "b", "t", "g"} | gh.PARTON_NAMES
        return {k: v for k, v in rates.items() if not any(part in partons for part in k.split())}

    def cmb_sigma_v(self, p: Point) -> dict[str, float] | None:
        """⟨σv⟩ by channel during recombination where long-range effects act today: G8's rate at the era's speed
        ``CMB_SPEED``, where a mediator's mass has saturated the Sommerfeld factor (a bound-state resonance's rise
        below 10⁻⁵ included); None elsewhere, where the s-wave is taken from two small speeds
        (``constraints.searches.s_wave``). AL3-09: that extrapolation, right only for σv = a + bv², had given a 100 GeV
        Dirac χ with a 0.1 GeV vector (α = 0.01) 14.7 times its tree rate for the saturated 78."""
        args = (self.spec_json, self.scan, self.tied, p.m_chi, p.m_med)
        if not self.sommerfeld or not (_today_long_range(*args) or _split_today(*args)):
            return None
        return self.sigma_v_today(p, CMB_SPEED)

    def today_hadronic(self, p: Point) -> str:
        """Why today's quark and gluon rates are not computed (the dark matter at √s ≈ 2m_χ in the hadronic window,
        ``generic_hadronic.today_partons``), or "": the CMB then decides only where the other channels exclude alone."""
        from adroit.parameter_space.portals import generic_hadronic as gh
        try:
            mb, rules, model = self.at(p)
        except ValueError:
            return ""
        return gh.today_partons(mb, rules, model)

    def today_unknown(self, p: Point) -> str:
        """Why annihilation today is not computed: long-range effects today that G8 does not compute, a boson's
        uncomputed hadronic width moving the s-channel propagator at s = 4m_χ² (``generic_hadronic``), or the model
        cannot be built."""
        from adroit.parameter_space.portals import generic_hadronic as gh
        try:
            mb, rules, _ = self.at(p)
        except ValueError as error:
            return f"the generic route cannot build the model: {error}"
        if why := _light_higgs(mb, rules) or gh.propagator_reason(mb, rules, fixed=True):
            return why
        reason = _today_long_range(self.spec_json, self.scan, self.tied, p.m_chi, p.m_med)
        split = _split_today(self.spec_json, self.scan, self.tied, p.m_chi, p.m_med)
        if (reason or split) and self.sommerfeld and self._enhanced(p):
            return ""
        return reason or (SPLIT_REASON if split else "")

    def _enhanced(self, p: Point) -> bool:
        from adroit.parameter_space.portals.generic_id import TODAY_SPEED
        return _enhanced_today(self.spec_json, self.scan, self.tied, p.m_chi, p.m_med, TODAY_SPEED) is not None

    def resummed_line(self, p: Point) -> tuple[str, float | None]:
        """(the rate's source, σv_line in cm³/s) with the Sommerfeld effect on, where the dark matter is a pure
        wino- or higgsino-like multiplet: DMγSpec's NLL′ rate (``constraints.resummed_lines``); else, a pure Majorana
        odd n-plet: the NLL rate of ``constraints.endpoint_nll`` ("nplet<n>"); else ("", None)."""
        from adroit.constraints import endpoint_nll, resummed_lines
        from adroit.parameter_space.portals import generic_lhc
        from adroit.parameter_space.searches import HESS_LINE_RESOLUTION, LINE_SPEED
        if not self.sommerfeld:
            return "", None
        try:
            mb, rules, _ = self.at(p)
        except ValueError:
            return "", None
        m = mb.spectrum.dark_matter().mass_gev
        kind = generic_lhc.pure_dark_kind(mb, rules)
        if kind in resummed_lines.MODELS and (line := resummed_lines.line_sigma_v(kind, m)) is not None:
            return kind, line
        n = generic_lhc.pure_majorana_nplet(mb, rules)
        if not n:
            return "", None
        return f"nplet{n}", endpoint_nll.line_sigma_v(n, m, LINE_SPEED, HESS_LINE_RESOLUTION)

    def line_sigma_v(self, p: Point) -> dict[str, float]:
        """σv_γγ and σv_Zγ (cm³/s) for the line searches. A pure wino or higgsino takes DMγSpec's resummed rate as a
        γγ-equivalent, a pure Majorana odd n-plet the NLL rate (``resummed_line``). A higgsino's neutral states are split into Majorana states today, so, as
        the library's, its rate is doubled against the searches' halving for a Dirac pair. Otherwise the rates of
        ``sigma_v_today``."""
        from adroit.parameter_space.searches import LINE_SPEED
        kind, line = self.resummed_line(p)
        if line is not None:
            dirac = kind == "higgsino" and self.at(p)[0].spectrum.dark_matter().kind not in ("majorana", "real")
            return {"gamma": 2.0 * line if dirac else line}
        return self.sigma_v_today(p, LINE_SPEED)

    def line_band(self, p: Point) -> tuple[float, float, str]:
        """(low, high, why) bracketing ``line_sigma_v``'s rate where it is resummed (``endpoint_nll.theory_band``,
        ``resummed_lines.theory_band``), else (1, 1, "")."""
        from adroit.constraints import endpoint_nll, resummed_lines
        kind, line = self.resummed_line(p)
        if line is None:
            return 1.0, 1.0, ""
        if kind.startswith("nplet"):
            return endpoint_nll.theory_band(int(kind[len("nplet"):]))
        return resummed_lines.theory_band(self.at(p)[0].spectrum.dark_matter().mass_gev)

    def lines_upper_bound(self, p: Point) -> str:
        """Why the γ-ray lines are undecided (``generic_today.LINES_REASON``: an electroweak multiplet's
        tree-level Sommerfeld lines, where no resummed rate applies), or ""."""
        from adroit.parameter_space.portals import generic_today
        if not (self.sommerfeld and _today_long_range(self.spec_json, self.scan, self.tied, p.m_chi, p.m_med)
                and self._enhanced(p)) or self.resummed_line(p)[1] is not None:
            return ""
        found = self.long_range_effects(p)
        mb, _, model = self.at(p)
        block = generic_today.neutral_block(found, mb, model)
        return generic_today.LINES_REASON if block is not None and block[0].a.n > 1 else ""

    def cascade(self, channel: str, p: Point):
        """The two-body photon topology of a cascade channel (``spectra.from_rates``), or None."""
        from adroit.parameter_space.portals import generic_id
        mb, rules, model = self.at(p)
        return generic_id.cascade(mb, rules, model, channel)

    def cmb_f_eff_range(self, channel: str, p: Point) -> tuple[float, float] | None:
        """(lowest, highest) f_eff of a cascade channel (the CMB), or None."""
        from adroit.parameter_space.portals import generic_id
        mb, rules, model = self.at(p)
        return generic_id.f_eff_range(mb, rules, model, channel)


# --- building the model at a point ------------------------------------------------------------------

def _dm_field(spec: ModelSpec) -> str:
    """The dark matter's field: the first dark-matter field with a stated mass."""
    for f in spec.fields:
        if f.role.value == "dark_matter" and f.mass_gev is not None:
            return f.name
    raise ValueError("no dark-matter field states a mass: name the scanned parameter")


def _read(spec: ModelSpec, name: str) -> float:
    for f in spec.fields:
        if f.name == name:
            if f.mass_gev is None:                   # the audit's G3/G4-6: float(None) had crashed Track 1
                raise ValueError(f"{name} states no mass, so it cannot be a scan coordinate")
            return float(f.mass_gev)
    for c in spec.couplings:
        if c.name == name and c.value is not None:
            return float(c.value)
    raise ValueError(f"{name} is neither a field with a mass nor a coupling with a value")


def _set(spec: ModelSpec, name: str, value: float) -> ModelSpec:
    if not any(x.name == name for x in (*spec.fields, *spec.couplings)):
        raise ValueError(f"{name} is neither a field nor a coupling of the model")
    fields = [f.model_copy(update={"mass_gev": value}) if f.name == name else f for f in spec.fields]
    couplings = [c.model_copy(update={"value": value}) if c.name == name else c for c in spec.couplings]
    return spec.model_copy(update={"fields": fields, "couplings": couplings})


@lru_cache(maxsize=64)
def _built(spec_json: str, scan: str, tied: str, m_chi: float, m_med: float):
    from adroit.model_building import feynman, spectrum
    spec = ModelSpec.model_validate_json(spec_json)
    spec = _set(spec, scan or _dm_field(spec), m_chi)
    if tied:
        spec = _set(spec, tied, m_med)
    mb = spectrum.compute(spec)
    rules = feynman.feynman_rules(mb)
    rules = _with_higgs_width(mb, _without_closed_partons(rules, mb))
    return mb, rules, tree_model(rules)


def _without_closed_partons(rules, mb=None):
    """The rules with each new neutral boson whose quark and gluon decays are closed (below its hadronic opening:
    ``generic_hadronic.closed_decays``) given its tree width without them, as its portrait has it, so that every
    propagator, table and rate reads the width the policy states (the RX22 audit's RY23-01, 2026-10-23: a 0.2 GeV
    vector kept its free u, d widths in the tree model and its electron rate today near the pole was 49 times too
    small). The SM-like Higgs's own prescription is applied after (``_with_higgs_width``); a scalar the mixing makes
    mostly doublet below that prescription's start (``_light_higgs``) is closed here as any other boson (RZ23-03)."""
    from adroit.constraints import hadronic_window as hw
    from adroit.model_building import feynman
    from adroit.model_building.feynman import ParticleRecord, Rules
    from adroit.parameter_space.portals import generic_hadronic as gh
    light = {x.name for x in _light_higgs_states(mb, rules)} if mb is not None else set()
    closed = {x.name for x in rules.particles if gh.closed_decays(rules, x.name)
              or x.name in light and gh.state(rules, x.name) == hw.CLOSED}
    if not closed:
        return rules
    kept = [v for v in rules.vertices if not (len(v.legs) == 3 and any(
        v.legs.count(x) == 1 and all(o in gh.PARTON_NAMES for o in v.legs if o != x) for x in closed))]
    width = feynman.widths(rules.particles, kept)
    out = [ParticleRecord(x.name, x.spin, x.mass, x.anti, x.colour, x.charge, x.parity, width[x.name])
           if x.name in closed else x for x in rules.particles]
    return Rules(out, rules.vertices, rules.g_s, rules.notes)


def _with_higgs_width(mb, rules):
    """The SM widths, as the library's:
    - **the SM-like h:** its H⁰ share of the SM width at its mass (off-shell W*, Z*, gluons and photons included,
      ``higgs.width``) plus its two-body decays into new states;
    - **the W and Z:** their tree-level widths into SM states scaled to the measured widths (``higgs.GAMMA_W``,
      ``GAMMA_Z``: the higher orders, +2.0% and +2.3%), plus their decays into new states. A ratio, so that a Z
      mixed with a Z′ keeps its reduced couplings. The tail of an off-shell W or Z scales with its width (G6)."""
    from adroit.model_building.feynman import ParticleRecord, Rules
    out = []
    for x in rules.particles:
        state = next((s for s in mb.spectrum.states if s.name == x.name), None)
        share = (state.composition.get("H[m=-0.5,re]", 0.0) + state.composition.get("h[m=0,r]", 0.0)) \
            if state is not None and state.spin == 0 else 0.0
        width = None
        if share > 0.5 and x.mass >= _higgs_width_from():       # the SM prescription's range (RZ23-03: below it the
            width = share * _sm_higgs_width(x.mass) + _dark_width(rules, x.name)   # table's zero had been the width)
        elif share > 1e-12:
            # a lightly mixed scalar: its H share of the SM width carries the off-shell W*, Z* and the gluons that
            # its two-body tree width lacks (the audit's G3/G4-7, G12: 4.9e-5 against 1.27e-4 GeV at 140 GeV),
            # unless its own couplings (a second doublet's Yukawas) give it more
            width = max(x.width, share * _sm_higgs_width(x.mass) + _dark_width(rules, x.name))
        elif x.name in ("W", "Z") and x.width > 0:
            new = _dark_width(rules, x.name, VECTOR_DECAYS)
            width = (x.width - new) * _measured_over_tree()[x.name] + new
        if width is not None:
            x = ParticleRecord(x.name, x.spin, x.mass, x.anti, x.colour, x.charge, x.parity, width)
        out.append(x)
    return Rules(out, rules.vertices, rules.g_s, rules.notes)


VECTOR_DECAYS = ("FFV", "VSS", "VVS", "VVV")


def _higgs_width_from() -> float:
    from adroit.constraints import higgs
    return higgs.WIDTH_FROM


def _doublet_share(state) -> float:
    """A spin-0 state's share of the SM doublet (its H⁰ and h components)."""
    if state is None or state.spin != 0:
        return 0.0
    return state.composition.get("H[m=-0.5,re]", 0.0) + state.composition.get("h[m=0,r]", 0.0)


def _light_higgs_states(mb, rules) -> list:
    """The scalars the mixing makes mostly doublet (share > ½) below the SM width prescription's start
    (``higgs.WIDTH_FROM``): its width, its signal strength and its hadronic decays are not the SM Higgs's there."""
    states = {s.name: s for s in mb.spectrum.states}
    return [x for x in rules.particles if x.spin == 0 and x.parity == 1 and 0 < x.mass < _higgs_width_from()
            and _doublet_share(states.get(x.name)) > 0.5]


def _light_higgs(mb, rules) -> str:
    """Why Ωh² and today's rates are not computed: a mostly-doublet scalar below 2 GeV, where ADROIT has no SM-like
    width or hadronic prescription (the RY23 audit's RZ23-03, 2026-10-23: it was given a zero width, its open decays
    erased, and the Higgs signal strength divided by it; the signal strength is the 125 GeV state's since RF23-01,
    ``generic_lhc.measured_higgs``), or ""."""
    light = _light_higgs_states(mb, rules)
    if not light:
        return ""
    x = light[0]
    return (f"the scalar {x.name} at {x.mass:.4g} GeV is mostly the SM doublet: below "
            f"{_higgs_width_from():g} GeV ADROIT has no SM-like width or hadronic prescription for it "
            "(the library's Higgs portals refuse this region too); not computed")


@lru_cache(maxsize=1)
def _measured_over_tree() -> dict[str, float]:
    """Γ_measured/Γ_tree of the W and Z: G2's tree-level widths are those of the Standard Model alone."""
    from adroit.constraints import higgs
    from adroit.model_building import feynman, spectrum
    sm = ModelSpec.model_validate({"name": "sm", "phase": "unbroken", "fields": [
        {"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True, "dark_parity": -1, "mass_gev": 1e3},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}]})
    tree_widths = {p.name: p.width for p in feynman.feynman_rules(spectrum.compute(sm)).particles}
    return {"W": higgs.GAMMA_W / tree_widths["W"], "Z": higgs.GAMMA_Z / tree_widths["Z"]}


@lru_cache(maxsize=16)
def _sm_higgs_width(mass: float) -> float:
    from adroit.constraints import higgs
    return float(higgs.width(mass))


def _dark_width(rules, name: str, kinds: tuple[str, ...] = ("SSS", "FFS", "FFV", "VSS", "VVS")) -> float:
    """The two-body width of ``name`` into states that are not the SM's (Z₂-odd or new even states), each channel as
    ``feynman.widths`` sums it: its colour sum (``feynman._colour_factor``), ½ for identical final particles, over
    every structure it supports (the independent audit, NA15-03, 2026-11-16: the colour sum had been left out, a
    colour triplet pair's partial one third of itself, and VSS too, h₂₀₀ → Z a missing)."""
    from adroit.model_building.feynman import SM_FERMIONS, _colour_factor, two_body_width
    sm = {f.name for f in SM_FERMIONS} | {f"{f.name}~" for f in SM_FERMIONS} | {"W", "W~", "Z", "A", "g", "h"}
    by = {p.name: p for p in rules.particles} | {p.anti: p for p in rules.particles if p.anti}
    total = 0.0
    me = by[name]
    for v in rules.vertices:
        if v.kind not in kinds or v.legs.count(name) != 1:
            continue
        others = [x for x in v.legs if x != name]
        if all(x in sm for x in others) or sum(by[x].mass for x in others) >= me.mass:
            continue
        colour = _colour_factor(me.colour, [by[x].colour for x in others])
        if colour is None:
            continue
        k = v.legs.index(name)
        total += two_body_width(v, k, [by[x].mass for x in v.legs], colour) * (0.5 if others[0] == others[1] else 1.0)
    return total


def tree_model(rules):
    """The rules as ``constraints.tree``'s model."""
    from adroit.constraints import tree
    from adroit.model_building.ufo_export import SM_NAMES
    model = tree.Model({})
    for x in rules.particles:
        pdg = SM_NAMES[x.name][2] if x.name in SM_NAMES else 0           # W and Z by code: ``ufo.off_shell_sigma``
        model.add(tree.Particle(x.name, x.spin, x.mass, x.width, x.anti, pdg=pdg, colour=x.colour, charge=x.charge))
    model.vertices = [tree.Vertex(v.kind, v.legs, complex(v.c), complex(v.c2), colour=v.colour,
                                  structure=getattr(v, "structure", ())) for v in rules.vertices]
    model.parity = {x.name: x.parity for x in rules.particles} | {x.anti: x.parity for x in rules.particles if x.anti}
    return model


@lru_cache(maxsize=64)
def _bath(spec_json: str, scan: str, tied: str, m_chi: float, m_med: float):
    """(bath, species, each pair's σ(s), each pair's final states) at a point (cached: Ωh², the bracket and the
    certificates share one tabulation)."""
    mb, rules, model = _built(spec_json, scan, tied, m_chi, m_med)
    bath = bath_states(mb, rules)
    species = [relic.Species(m, dof) for _, m, dof in bath]
    poles = _poles(rules)
    pairs, finals = {}, {}
    for i in range(len(bath)):
        for j in range(i, len(bath)):
            found = final_states(model, bath[i][0], bath[j][0])
            poles = _s_channel(model, bath[i][0], bath[j][0], rules)
            loops = _loop_sigma(mb, model, bath[i][0], bath[j][0], poles)
            if found or loops:
                parts = [_pair_sigma(model, bath[i][0], bath[j][0], found, poles)] if found else []
                pairs[(i, j)] = _sum(parts + ([loops] if loops else []))
                finals[(i, j)] = found + ([("g", "g")] if loops else [])
    return bath, species, pairs, finals


def _s_channel(model, a: str, b: str, rules) -> list[tuple[float, float]]:
    """The poles that can appear in a b's s-channel: bosons carrying the pair's charge (exact, and it keeps the
    fine pole nodes to the poles that matter)."""
    charge = model.particles[a].charge + model.particles[b].charge
    return [(x.mass, x.width) for x in rules.particles
            if x.parity == 1 and x.spin != 0.5 and x.width > 0 and abs(abs(x.charge) - abs(charge)) < 1e-9]


def _exchanged(model, a: str, b: str, rules) -> list[tuple[float, float]]:
    """The poles of a b's s-channel that its amplitudes hold: each boson of ``_s_channel``'s kind joined both to the
    pair (a vertex a b X̄) and to one of its final pairs (X c̄ d̄), as ``tree.Process`` finds an s-channel diagram.
    The audit loop's AL7-03 (the auditor, 2026-11-17): a boson of the pair's charge coupled only to muons had been taken as
    an exchange of χ χ̄, and its pole at their threshold refused Ωh², though no diagram of the pair holds it."""
    parts, out = model.particles, []
    finals = final_states(model, a, b)
    for x in rules.particles:
        if not (x.parity == 1 and x.spin != 0.5 and x.width > 0) or x.name not in parts:
            continue
        if model.find([a, b, parts[x.name].conjugate]) and any(
                model.find([x.name, parts[c].conjugate, parts[d].conjugate]) for c, d in finals):
            out.append((x.mass, x.width))
    return out


def _poles(rules) -> list[tuple[float, float]]:
    return [(x.mass, x.width) for x in rules.particles if x.parity == 1 and x.spin != 0.5 and x.width > 0]


@lru_cache(maxsize=64)
def _estimate(spec_json: str, scan: str, tied: str, m_chi: float, m_med: float):
    from adroit.constraints import long_range_bracket
    from adroit.parameter_space.portals import generic_checks
    mb, rules, _ = _built(spec_json, scan, tied, m_chi, m_med)
    bath, species, pairs, finals = _bath(spec_json, scan, tied, m_chi, m_med)
    if not pairs:
        return None
    inputs = generic_checks.bracket_inputs(mb, rules, bath, species, pairs, finals, _poles(rules))
    return long_range_bracket.bracket(*inputs) if inputs is not None else None


@lru_cache(maxsize=64)
def _long_range(spec_json: str, scan: str, tied: str, m_chi: float, m_med: float):
    from adroit.parameter_space.portals import generic_lr
    mb, rules, model = _built(spec_json, scan, tied, m_chi, m_med)
    bath, _, _, _ = _bath(spec_json, scan, tied, m_chi, m_med)
    return generic_lr.analyse(mb, rules, model, bath)


def _long_range_flags(found, bound_states: bool) -> list[str]:
    """What G7 computed for each group, and what it left out."""
    out = []
    for grp in found.groups:
        label = f"{grp.a.field}{'~' if grp.a.anti else ''} {grp.b.field}{'~' if grp.b.anti else ''}"
        chans = ", ".join(f"{c.su2}{'' if c.su3 == '1' else '/' + c.su3} (α_eff {c.alpha_tree:+.3g})"
                          for c in grp.channels)
        bound = {"su2": "bound states by W and B emission (MRSS)", "colour": "the colour-singlet ground state "
                 "(Harz & Petraki)", "dark_u1": "the hydrogen-like ground state by dark-photon emission"
                 }.get(grp.bound, "")                                    # dark_u1: the audit's G7-7, G12
        if not bound_states:
            bound = "bound states left out by request"
        elif not bound:
            bound = "bound-state formation not computed for this structure (it would lower Ωh²)"
        out.append(f"long-range effects (G7), {label}: the Sommerfeld effect in channels {chans}; {bound}")
    return out


@lru_cache(maxsize=64)
def _scattering(spec_json: str, scan: str, tied: str, m_chi: float, m_med: float):
    from adroit.parameter_space.portals import generic_dd
    mb, rules, _ = _built(spec_json, scan, tied, m_chi, m_med)
    return generic_dd.scattering(mb, rules)


@lru_cache(maxsize=256)
def _today(spec_json: str, scan: str, tied: str, m_chi: float, m_med: float, v_rel: float,
           sommerfeld: bool = True) -> tuple:
    """Today's σv by channel: G6's tree level, or G8's where long-range effects matter today and G8 computes them
    (the Higgs's loop-induced gg then added at tree level)."""
    from adroit.parameter_space.portals import generic_id
    mb, rules, model = _built(spec_json, scan, tied, m_chi, m_med)
    tree = generic_id.annihilation_today(mb, rules, model, v_rel)
    if sommerfeld and (_today_long_range(spec_json, scan, tied, m_chi, m_med)
                       or _split_today(spec_json, scan, tied, m_chi, m_med)):
        enhanced = _enhanced_today(spec_json, scan, tied, m_chi, m_med, v_rel)
        if enhanced is not None:
            out = dict(enhanced)
            if "g" in tree and "g" not in out:
                out["g"] = tree["g"]
            return tuple(out.items())
    return tuple(tree.items())


@lru_cache(maxsize=256)
def _enhanced_today(spec_json: str, scan: str, tied: str, m_chi: float, m_med: float, v_rel: float):
    """G8's σv by channel (``generic_today.rates_today``), or None where it does not apply."""
    from adroit.parameter_space.portals import generic_today
    mb, rules, model = _built(spec_json, scan, tied, m_chi, m_med)
    found = _long_range(spec_json, scan, tied, m_chi, m_med)
    out = generic_today.rates_today(mb, rules, model, found, v_rel)
    return None if out is None else tuple(out.items())


SPLIT_REASON = ("a higgsino-like Dirac doublet's neutral states are split into Majorana states today, so only the "
                "lightest annihilates (spin 0 alone); that rate is computed by G8's spin sectors, which do not apply here")


@lru_cache(maxsize=64)
def _split_today(spec_json: str, scan: str, tied: str, m_chi: float, m_med: float) -> bool:
    """A higgsino-like Dirac doublet, whose lightest Majorana state alone annihilates today: G8's spin-0 sector
    (``generic_today.split_today``), G6's tree level being the degenerate Dirac pair's."""
    from adroit.parameter_space.portals import generic_today
    mb, rules, _ = _built(spec_json, scan, tied, m_chi, m_med)
    return generic_today.split_today(mb, rules)


@lru_cache(maxsize=64)
def _today_long_range(spec_json: str, scan: str, tied: str, m_chi: float, m_med: float) -> str:
    from adroit.parameter_space.portals import generic_id
    mb, rules, _ = _built(spec_json, scan, tied, m_chi, m_med)
    return generic_id.today_long_range(mb, rules)


def _freeze_out(spec_json: str, scan: str, tied: str, m_chi: float, m_med: float) -> float | None:
    """x_f of the bath at the point, under the degrees of freedom in use (``relic.current_eos``)."""
    return _freeze_out_at(spec_json, scan, tied, m_chi, m_med, relic.current_eos())


@lru_cache(maxsize=64)
def _freeze_out_at(spec_json: str, scan: str, tied: str, m_chi: float, m_med: float, eos: str) -> float | None:
    _, species, pairs, _ = _bath(spec_json, scan, tied, m_chi, m_med)
    if not pairs:
        return None
    mb, rules, _ = _built(spec_json, scan, tied, m_chi, m_med)
    return relic.freeze_out_x_species(species, pairs, _poles(rules))


# --- the bath and its pairs -------------------------------------------------------------------------------

def bath_states(mb, rules) -> list[tuple[str, float, float]]:
    """(name, mass, dof) of every species in the bath: odd states below BATH × m_χ, particle and antiparticle."""
    dm = mb.spectrum.dark_matter().mass_gev
    out = []
    for x in rules.particles:
        if x.parity != -1 or x.mass > BATH * dm:
            continue
        spin_dof = {0: 1.0, 0.5: 2.0, 1: 3.0 if x.mass > 0 else 2.0}[x.spin] * {"1": 1, "3": 3, "3bar": 3, "8": 8}[x.colour]
        out.append((x.name, x.mass, spin_dof))
        if x.anti:
            out.append((x.anti, x.mass, spin_dof))
    return out


def _no_channel(mb, rules, model) -> str:
    """Why Ωh² is refused when neither the dark matter's pair nor any pair of the bath has a final state (the audit's
    G3/G4-9, G12: the yield had frozen at its value at x = 3), or ""."""
    bath = [b[0] for b in bath_states(mb, rules)]
    if any(final_states(model, a, b) for i, a in enumerate(bath) for b in bath[i:]):
        return ""
    return "the dark matter has no annihilation channel at tree level (no term joins it to anything it can annihilate to)"


DEGENERATE_RELIC = 1e-6           # relative: a charged state this close to the dark matter is its multiplet partner


FEEBLE = 1e-10                    # G2's vertex resolution (``feynman.TOLERANCE`` for couplings below 1)


@lru_cache(maxsize=64)
def _feeble(spec_json: str, scan: str, tied: str, m_chi: float, m_med: float) -> str:
    """Why the model is outside the generic route: a term whose coupling is not zero but below G2's vertex resolution
    is dropped from the rules, so a feebly coupled state would look uncoupled to every search (P4's gate found a
    B − L vector at g = 10⁻¹² with no couplings at all); '' otherwise. A Yukawa-like term is taken at m_f = 1 GeV
    (its top or τ coupling is larger)."""
    from adroit.library.interactions.derivation import evaluate_expression, symbol_table
    from adroit.model_building.gauge_basis import ELECTROWEAK
    spec = ModelSpec.model_validate_json(spec_json)
    spec = _set(spec, scan or _dm_field(spec), m_chi)
    if tied:
        spec = _set(spec, tied, m_med)
    table = symbol_table(spec, {"m_q": 1.0, "m_l": 1.0, "m_f": 1.0}, ELECTROWEAK)
    tiny = []
    for term in spec.terms:
        try:
            value = abs(complex(evaluate_expression(term.coupling, table, allow_complex=True)))
        except (KeyError, ValueError, NameError, TypeError, ZeroDivisionError):
            continue
        if 0.0 < value < FEEBLE:
            tiny.append(f"{term.text or term.coupling} = {value:.2g}")
    if not tiny:
        return ""
    return ("a coupling below the generic route's resolution (10⁻¹⁰: G2 drops such vertices, and the state would look "
            "uncoupled): " + "; ".join(tiny[:3]))


CONTACT_MARGIN = 3.0             # a contact term's relic needs √s at freeze-out ≤ Λ/3 (declared, 2026-10-20)
CONTACT_FLAG_MARGIN = 5.0        # between Λ/5 and Λ/3 it is computed and flagged (the owner's decision #6, 2026-10-20)
CONTACT_X_F = 20.0               # x_f = m_χ/T at freeze-out for that check: √s ≈ 2m_χ(1 + 3/(2x_f))


def _contact_scale(mb, rules) -> tuple[float, float] | None:
    """(√s at freeze-out, Λ) for the dark matter's contact terms, or None without one: √s = 2m_χ(1 + 3/(2x_f)) and
    Λ = |c|^(−1/2) of the strongest contact structure. Each structure's c is the sum over every term with the same legs
    and the same pair of bilinears, so a contact written as two halves, or as two terms that cancel, is judged as the
    operator it adds up to (the tactical audit's T20-04, 2026-10-20: two halves had escaped the refusal of the whole)."""
    dm = mb.spectrum.dark_matter()
    summed: dict[tuple, complex] = {}
    for v in rules.vertices:
        if v.kind == "FFFF" and dm.name in {x.rstrip("~") for x in v.legs}:
            for first, second, c in v.structure:
                summed[v.legs, first, second] = summed.get((v.legs, first, second), 0.0) + c
    largest = max((abs(c) for c in summed.values()), default=0.0)
    if largest <= 0:
        return None
    return 2 * dm.mass_gev * (1 + 1.5 / CONTACT_X_F), largest ** -0.5


def contact_shift(root_s: float, scale: float) -> float:
    """The relative change of the rate if the contact is completed by a unit-coupling s-channel mediator of mass Λ:
    |M²/(M² − s)|² − 1 = 1/(1 − s/Λ²)² − 1, about 27% at √s = Λ/3 (s/Λ² = 1/9) and 9% at Λ/5."""
    return 1.0 / (1.0 - (root_s / scale) ** 2) ** 2 - 1.0


def _contact_validity(mb, rules) -> str:
    """Why a contact term's relic is not computed: √s at freeze-out is not well below its scale (``_contact_scale``),
    √s > Λ/``CONTACT_MARGIN``; or "". Below, the relic holds up to O(s/Λ²) corrections from whatever completes the
    contact (``contact_shift``: about 27% in the rate at the margin), and between Λ/``CONTACT_FLAG_MARGIN`` and the
    margin it is flagged (``_contact_flag``)."""
    found = _contact_scale(mb, rules)
    if found is None:
        return ""
    root_s, scale = found
    if root_s * CONTACT_MARGIN > scale:
        return (f"√s at freeze-out ({root_s:.4g} GeV) is not well below the contact term's scale Λ = {scale:.4g} GeV "
                f"(√s ≤ Λ/{CONTACT_MARGIN:g}): the contact is not a valid description there")
    return ""


def _contact_flag(mb, rules) -> str:
    """The flag of a contact term's relic computed near its validity's edge, Λ/``CONTACT_FLAG_MARGIN`` < √s ≤
    Λ/``CONTACT_MARGIN``, with the shift a unit-coupling mediator of mass Λ would make; or "" (the owner's decision #6,
    2026-10-20: keep Λ/3, flag Λ/5 to Λ/3). Above the margin the relic is refused, not flagged."""
    found = _contact_scale(mb, rules)
    if found is None:
        return ""
    root_s, scale = found
    if not scale / CONTACT_FLAG_MARGIN < root_s <= scale / CONTACT_MARGIN:
        return ""
    return (f"contact term near its validity's edge: √s at freeze-out ({root_s:.4g} GeV) is between "
            f"Λ/{CONTACT_FLAG_MARGIN:g} and Λ/{CONTACT_MARGIN:g} (Λ = {scale:.4g} GeV); a unit-coupling mediator of "
            f"mass Λ would change the annihilation rate by about {contact_shift(root_s, scale):.0%}")


def _components(mb, rules) -> str:
    """Why the relic is not one component's, or "" (the owner's decision #5, 2026-10-20, for every model however its
    generations are written: the same physics as two fields or as one field of two generations gets one verdict). A Z₂-odd state no chain of vertices joins to the dark matter is stable (a conserved number: each
    generation's, where flavour is conserved); a neutral one degenerate with it cannot decay to it. Either is a second
    stable component, whose evolution ADROIT does not compute. A charged partner degenerate at tree level is its
    multiplet partner, split at one loop (``_charged_relic``)."""
    dm = mb.spectrum.dark_matter()
    odd = {x.name: x for x in rules.particles if x.parity == -1}
    parent = {name: name for name in odd}

    def root(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name
    for v in rules.vertices:
        legs = [leg.rstrip("~") for leg in v.legs if leg.rstrip("~") in odd]
        for a, b in zip(legs, legs[1:]):
            parent[root(a)] = root(b)
    for name, x in sorted(odd.items(), key=lambda item: item[1].mass):
        if name == dm.name:
            continue
        if root(name) != root(dm.name):
            return (f"several stable components: {name} ({x.mass:.6g} GeV) is joined to the dark matter by no "
                    "interaction, so its number is conserved (each generation's, where the couplings conserve "
                    "flavour); ADROIT computes one component's relic")
        if abs(x.charge) < 1e-9 and x.colour == "1" and abs(x.mass - dm.mass_gev) <= DEGENERATE_RELIC * dm.mass_gev:
            return (f"several stable components: {name} is degenerate with the dark matter ({x.mass:.6g} GeV) and "
                    "cannot decay to it; ADROIT computes one component's relic")
    return ""


def _thermal_history(mb, rules, model, x_f: float) -> str:
    """Why the thermal history is not the one ADROIT computes, or "" (the owner's decision #5, every model: chemical
    equilibrium is a substantive requirement of the coannihilation calculation, whose failure changes the relic; Garny
    et al., arXiv:1705.09292; it had been a flag). Each Z₂-odd state must convert, by decays and scatterings, to the dark matter or to a state already shown to (a chain: χ⁺⁺ to
    χ⁺ to χ⁰), faster than ``generic_checks.CONTACT`` × H at its own freeze-out, T = m/x_f; else its own abundance and
    late decays are not computed."""
    from adroit.parameter_space.portals import generic_checks as gc
    dm = mb.spectrum.dark_matter()
    certified = {dm.name, f"{dm.name}~"}
    waiting = [x for x in rules.particles if x.parity == -1 and x.name != dm.name]
    while waiting:
        rates = {}
        for x in waiting:
            temperature = x.mass / x_f
            limit = gc.CONTACT * gc.hubble(temperature)
            rate = gc._decays(rules, x.name, certified)
            if rate < limit:
                rate += gc._scattering(model, x.name, certified, temperature)
            rates[x.name] = (rate, limit, temperature)
        passed = [x for x in waiting if rates[x.name][0] >= rates[x.name][1]]
        if not passed:
            x = min(waiting, key=lambda s: s.mass)
            rate, limit, temperature = rates[x.name]
            return (f"the thermal history is not resolved: {x.name} ({x.mass:.6g} GeV) converts to the dark matter at "
                    f"{rate:.2g} GeV, below {gc.CONTACT:g} H = {limit:.2g} GeV at its freeze-out (T = {temperature:.3g} "
                    "GeV); its own abundance and late decays are not computed")
        certified |= {x.name for x in passed} | {x.anti for x in passed if x.anti}
        waiting = [x for x in waiting if x not in passed]
    return ""


def _charged_relic(rules) -> str:
    """Why Ωh² is refused when a charged or coloured Z₂-odd state is lighter than the dark matter (it would be the
    stable relic, not the dark matter: the audit's G3/G4-2, G12), or "". A partner degenerate at tree level (a pure
    multiplet, whose neutral state the one-loop splitting makes the lightest) is not lighter: the zoo's development
    half found the complex triplet refused for its tree-level tie."""
    odd = [x for x in rules.particles if x.parity == -1]
    neutral = [x.mass for x in odd if abs(x.charge) <= 1e-9 and x.colour == "1"]
    lightest = min(odd, key=lambda x: x.mass, default=None)
    if lightest is not None and (abs(lightest.charge) > 1e-9 or lightest.colour != "1") and \
            (not neutral or lightest.mass < min(neutral) * (1.0 - DEGENERATE_RELIC)):
        return (f"the lightest Z₂-odd state, {lightest.name} at {lightest.mass:.6g} GeV, is charged or coloured: it would "
                "be the stable relic, which is excluded, not the neutral dark matter")
    return ""


def _hadronic_window(mb, rules, model) -> str:
    """Why Ωh² is refused for the hadronic window (the owner's decision, 2026-10-20; ``generic_hadronic``): a bath
    pair annihilating into quarks or gluons at its threshold in the window (2m_π to 2 GeV for a pure vector current,
    to 3 GeV inclusive for any other), or a boson's uncomputed hadronic width moving an s-channel propagator; or ""
    (the audit's G3/G4-1, G12, had refused 2m_π < √s < 2 GeV for every current, exclusive at 2 GeV). Below 2m_π the
    partons are closed (``_table``). A coloured state in the bath at or below 3 GeV refuses it too
    (``generic_hadronic.coloured_bath_reason``, RV22-01)."""
    from adroit.parameter_space.portals import generic_hadronic as gh
    return (gh.annihilation_reason(mb, rules, model) or gh.coloured_bath_reason(mb, rules)
            or gh.propagator_reason(mb, rules))


def final_states(model, a: str, b: str) -> list[tuple[str, str]]:
    """The Z₂-even final pairs (c, d) of a b → c d with at least one tree diagram and conserved charge."""
    from adroit.constraints import tree
    parts = model.particles
    charge = parts[a].charge + parts[b].charge
    even = sorted(n for n, x in parts.items() if _parity(model, n) == 1)
    out = []
    for i, c in enumerate(even):
        for d in even[i:]:
            if abs(parts[c].charge + parts[d].charge - charge) > 1e-9:
                continue
            try:
                found = tree.Process(model, a, b, c, d).diagrams()
            except ValueError:
                continue
            if found:
                out.append((c, d))
    return out


def _parity(model, name: str) -> int:
    """A particle's Z₂ parity (``tree_model`` attaches them)."""
    return getattr(model, "parity", {}).get(name, 1)


POLE_STEPS = np.array([0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 100, 200, 500])
NEAR_POLE = 3.0                   # u below which a pole is resolved finely (the thermal weight beyond is e^{−3x})
SPARSE_STEPS = np.array([0.5, 1, 2, 4, 8, 20])
REFINE = 1e-3                     # a final state refined at the poles if its σβ reaches this share of the pair's


CMB_SPEED = 1e-7                  # the dark matter's relative speed during recombination (a 100 GeV relic's ≲ 10⁻⁷)
POLE_FLOOR = 1e-12                # a narrower pole is not resolved by the tables: Ωh² is refused (``_unresolved_pole``)
POLE_LADDER = 1.5                 # the ratio of a pole's nodes beyond its steps
POLE_REACH = 0.5                  # a pole's nodes reach half its distance from the opening
BELOW_REACH = 1e-3                # a pole this close below the opening (in u) is resolved on the opening's side
OPENING_LADDER = 1.25             # there, the ratio of its nodes in u (the table is read in ln u)


def _nodes(threshold: float, finals_threshold: float, poles: list[tuple[float, float]], fine: bool = True) -> np.ndarray:
    """u nodes: log-spaced from the threshold, with nodes around each pole (in units of its width: ``POLE_STEPS``
    where the thermal average reaches it and ``fine``, a sparse set otherwise, its centre always, continued at
    ``POLE_LADDER`` to ``POLE_REACH`` of its distance from the opening) and just above the final threshold; a pole at
    or just below the opening (within ``BELOW_REACH``) has nodes on the opening's side, geometric in u (ratio
    ``OPENING_LADDER``) from a hundredth of its width or of its distance below, whichever is larger.

    A narrow pole needs both: with 13 nodes and linear interpolation, Choubey et al.'s Δ⁰ (Γ/M = 10⁻⁴) came out 8%
    too strong in Ωh² (``docs/g4_generic.md``). The width was floored at 10⁻⁶ of the mass, the steps stopped at 500
    widths, and a pole at or below the opening had none: ⟨σv⟩ 1.07 to 26 times too large for Γ/M of 10⁻⁷ to 10⁻⁹, and
    0.82 to 0.50 of itself at the opening (the audit loop's AL3-02, 2026-11-15)."""
    u0 = max(finals_threshold / threshold - 1.0, 0.0)
    nodes = list(u0 + np.concatenate([[1e-7], np.geomspace(1e-5, U_MAX, NODES)]))
    for mass, width in poles:
        ur = mass / threshold - 1.0
        w = max(width, POLE_FLOOR * mass) / threshold
        steps = POLE_STEPS if (fine and ur < NEAR_POLE) else SPARSE_STEPS
        if u0 < ur < U_MAX:
            steps = _reaching(steps, w, POLE_REACH * (ur - u0))
            nodes += [ur + k * w for k in np.concatenate([[0.0], steps, -steps]) if ur + k * w > u0]
        if u0 - BELOW_REACH < ur < u0 + BELOW_REACH:    # within reach of the opening, read there in ln u: a ladder
            start = 1e-2 * min(w, max(abs(ur - u0), w))
            nodes += list(u0 + np.geomspace(start, BELOW_REACH,
                                            1 + math.ceil(math.log(BELOW_REACH / start) / math.log(OPENING_LADDER))))
    nodes = np.unique(np.array(nodes))
    return nodes[np.concatenate([[True], np.diff(np.log(nodes)) > 1e-12])]      # one node where two meet in ln u


def _unresolved_pole(mb, rules, model) -> str:
    """Why Ωh² is not computed: an s-channel pole of the dark matter's pair narrower than the tables resolve (Γ/M below
    ``POLE_FLOOR``; at 10⁻¹³ their average was a quarter of the pole's), within the thermal reach; else "" (AL3-02)."""
    dm = mb.spectrum.dark_matter()
    anti = dm.name if dm.kind in ("real", "majorana", "vector") else f"{dm.name}~"
    for mass, width in _s_channel(model, dm.name, anti, rules):
        if 0.0 < width < POLE_FLOOR * mass and mass / (2.0 * dm.mass_gev) - 1.0 < U_MAX:
            return (f"an s-channel resonance at {mass:.4g} GeV with Γ/M = {width / mass:.2g} is narrower than the generic "
                    f"engine's cross-section tables resolve (Γ/M below {POLE_FLOOR:g})")
    return _unresolved_threshold(mb, rules, model)


def _unresolved_threshold(mb, rules, model) -> str:
    """Why Ωh² is not computed: an s-channel pole of a bath pair's amplitudes (``_exchanged``) closer to its threshold
    than the tree amplitudes resolve (``ufo.threshold_scale`` below ``ufo.SCALE_RESOLVED``: they vanish within 10⁻¹² of
    it), as the UFO route refuses it; else "". The audit loop's AL6-03 (the auditor, 2026-11-17): Γ/M = 1.4 × 10⁻¹², above ``POLE_FLOOR``, at the threshold
    lost a third of the pole's thermal rate under that floor, and Ωh² was 1.49 times too large at its thermal root."""
    from adroit.parameter_space.portals.ufo import SCALE_RESOLVED, threshold_scale
    names = [name for name, _, _ in bath_states(mb, rules)]
    for i, a in enumerate(names):
        for b in names[i:]:
            start = model.particles[a].mass + model.particles[b].mass
            for mass, width in _exchanged(model, a, b, rules):
                scale = threshold_scale(start, mass, width)
                if scale is not None and scale < SCALE_RESOLVED:
                    return (f"the s-channel resonance at {mass:.9g} GeV, of width {width:.3g} GeV, lies within "
                            f"{scale:.2g} of the {a} {b} threshold at {start:.9g} GeV (in √s/threshold − 1), closer "
                            f"than the tree amplitudes resolve ({SCALE_RESOLVED:g}): Ωh² is not computed")
    return ""


def _reaching(steps: np.ndarray, width: float, reach: float) -> np.ndarray:
    """``steps`` (in units of ``width``) continued at ``POLE_LADDER`` until they reach ``reach`` (in u)."""
    if steps[-1] * width >= reach:
        return steps
    more = math.ceil(math.log(reach / (steps[-1] * width)) / math.log(POLE_LADDER))
    return np.concatenate([steps, steps[-1] * POLE_LADDER ** np.arange(1, more + 1)])


def _tabulate(model, a: str, b: str, final: tuple[str, str], poles, fine: bool = True) -> callable:
    """σ(a b → c d)(s), from σ·β_in tabulated in u and interpolated; a final W or Z off shell near and below its
    threshold (``ufo.off_shell_sigma``). ``fine`` resolves the reachable poles finely (``_nodes``)."""
    return _interpolated(*_table(model, a, b, final, poles, fine))


def _table(model, a: str, b: str, final: tuple[str, str], poles, fine: bool):
    """(nodes, σβ on them, threshold, m_a, m_b) of one final state."""
    from adroit.constraints import tree
    from adroit.parameter_space.portals.ufo import OFF_SHELL
    ma, mb_ = model.particles[a].mass, model.particles[b].mass
    mc, md = model.particles[final[0]].mass, model.particles[final[1]].mass
    threshold = ma + mb_
    process = tree.Process(model, a, b, *final, points=ANGLES)
    off_shell = any(abs(x.pdg) in OFF_SHELL and x.width > 0 for x in process.p[2:])
    opens = mc + md
    if all(abs(x.pdg) in PARTONS for x in process.p[2:]):      # quarks and gluons appear only as hadrons
        opens = max(opens, 2.0 * M_PION)
    nodes = _nodes(threshold, threshold if off_shell else max(threshold, opens), poles, fine)
    s = (threshold * (1.0 + nodes)) ** 2
    beta = np.sqrt(np.clip((s - (ma + mb_) ** 2) * (s - (ma - mb_) ** 2), 0.0, None)) / s
    sigma = _off_shell(process, s, poles) if off_shell else np.array([process.sigma(x) for x in s])
    sigma = np.where(np.sqrt(s) >= opens, sigma, 0.0) if not off_shell else sigma
    return nodes, np.where(beta > 0, sigma * beta, 0.0), threshold, ma, mb_


def _off_shell(process, s: np.ndarray, poles) -> np.ndarray:
    """σ(s) with final W and Z off shell (``ufo.off_shell_sigma``), where it differs from on shell.

    The 2D Breit–Wigner quadrature costs about a hundred cross-sections, so it is evaluated only at nodes spaced at
    least a quarter of the narrowest final width apart in √s. Above the on-shell threshold the ratio
    R = σ_off/σ_on varies only on that scale (an s-channel pole's propagator cancels in it) and is interpolated onto
    every node; below it σ_off times the initial flux factor λ^½(s, m_a², m_b²)/s is interpolated in log, keeping
    every node within 20 widths of a pole. (σ_off itself grows as 1/β at the initial pair's threshold, so interpolating
    it across the first gap overstated the rate there twenty-fold: found by G7's held-out run, the inert doublet's
    H₀H₀ → WW* at 73 GeV.)"""
    from adroit.parameter_space.portals.ufo import OFF_SHELL, OFF_SHELL_REACH, off_shell_sigma
    ma, mb_ = process.p[0].mass, process.p[1].mass

    def flux(x: float) -> float:
        return math.sqrt(max((x - (ma + mb_) ** 2) * (x - (ma - mb_) ** 2), 0.0)) / x
    final = process.p[2:]
    vectors = [x for x in final if abs(x.pdg) in OFF_SHELL and x.width > 0]
    root = np.sqrt(s)
    on_threshold = sum(x.mass for x in final)
    top = on_threshold + OFF_SHELL_REACH * sum(x.width for x in vectors)
    spacing = 0.25 * min(x.width for x in vectors)
    on = np.array([process.sigma(x) if r > on_threshold else 0.0 for x, r in zip(s, root)])
    inside = np.flatnonzero(root <= top)
    if not inside.size:
        return on
    near = {k for k in inside for m, w in poles if abs(root[k] - m) <= 20 * max(w, 1e-6 * m)}
    chosen, last = [], -np.inf
    for k in inside:
        if k in near or root[k] - last >= spacing or k == inside[-1]:
            chosen.append(k)
            last = root[k]
    exact = {k: off_shell_sigma(process, s[k]) for k in chosen}
    out = on.copy()
    above = [k for k in chosen if on[k] > 0]
    below = [k for k in chosen if on[k] <= 0]
    for k in inside:
        if k in exact:
            out[k] = exact[k]
        elif on[k] > 0 and above:
            ratio = np.interp(root[k], root[above], [exact[j] / on[j] for j in above])
            out[k] = ratio * on[k]
        elif below:
            logs = np.log(np.maximum([exact[j] * flux(s[j]) for j in below], 1e-300))
            beta = flux(s[k])
            out[k] = float(np.exp(np.interp(root[k], root[below], logs))) / beta if beta > 0 else 0.0
    return out


def _interpolated(nodes: np.ndarray, table: np.ndarray, threshold: float, ma: float, mb_: float) -> callable:
    """σ(s) from σβ tabulated on the u nodes: interpolated in log(σβ) against log u between positive values, so a
    power of u (an s- or p-wave, a Breit–Wigner's tails) is followed exactly where a chord would overestimate it, and
    a p-wave's σβ ∝ u is not bent low between nodes (the audit's G4-11, G12: it had been log(σβ) against u, 2% low
    at u = 0.01); linearly next to a zero (a threshold)."""
    positive = table > 0
    logs = np.log(np.where(positive, table, 1.0))
    log_nodes = np.log(nodes)                     # every node is above zero (``_nodes`` starts at 10⁻⁷)

    def sigma(s: np.ndarray) -> np.ndarray:
        s = np.asarray(s, float)
        u = np.clip(np.sqrt(s) / threshold - 1.0, nodes[0], nodes[-1])
        beta = np.sqrt(np.clip((s - (ma + mb_) ** 2) * (s - (ma - mb_) ** 2), 0, None)) / s
        k = np.clip(np.searchsorted(nodes, u) - 1, 0, len(nodes) - 2)
        f = (u - nodes[k]) / (nodes[k + 1] - nodes[k])
        g = (np.log(u) - log_nodes[k]) / (log_nodes[k + 1] - log_nodes[k])
        both = positive[k] & positive[k + 1]
        logged = np.exp(logs[k] + g * (logs[k + 1] - logs[k]))
        linear = table[k] + f * (table[k + 1] - table[k])
        smooth = np.where(both, logged, linear)
        live = (np.sqrt(s) / threshold - 1.0 >= nodes[0]) & (beta > 0)
        return np.where(live, smooth / np.where(beta > 0, beta, 1.0), 0.0)
    return sigma


def _pair_sigma(model, a: str, b: str, finals, poles):
    """Σ over final states of σ(s), each tabulated once: with fine pole nodes where a probe of its σ (at each pole's
    centre and three energies, on shell) reaches ``REFINE`` of the pair's largest, sparse ones otherwise (a channel
    below that cannot move Ωh² by more than its own share)."""
    probes = [_probe(model, a, b, f, poles) for f in finals] if poles else [0.0] * len(finals)
    peak = max(probes, default=0.0)
    return _sum([_tabulate(model, a, b, f, poles, fine=bool(poles) and peak > 0 and probe >= REFINE * peak)
                 for f, probe in zip(finals, probes)])


def _loop_sigma(mb, model, a: str, b: str, poles):
    """The Higgs's loop-induced channels of a pair (``generic_id.higgs_loops``), tabulated as the others, or None."""
    from adroit.parameter_space.portals import generic_id
    found = generic_id.higgs_loops(mb, model, a, b)
    if found is None:
        return None
    ma, mb_ = model.particles[a].mass, model.particles[b].mass
    threshold = ma + mb_
    nodes = _nodes(threshold, threshold, poles, fine=True)
    s = (threshold * (1.0 + nodes)) ** 2
    beta = np.sqrt(np.clip((s - (ma + mb_) ** 2) * (s - (ma - mb_) ** 2), 0.0, None)) / s
    table = np.array([sum(found(x).values()) for x in s]) * beta
    return _interpolated(nodes, table, threshold, ma, mb_) if table.any() else None


def _sum(parts):
    return lambda s: sum(p(s) for p in parts)


def _probe(model, a: str, b: str, final: tuple[str, str], poles) -> float:
    """The largest on-shell σ of a final state at its poles' centres and at u = 0.01, 0.1, 0.5 (cheap)."""
    from adroit.constraints import tree
    threshold = model.particles[a].mass + model.particles[b].mass
    process = tree.Process(model, a, b, *final, points=ANGLES)
    roots = [m for m, _ in poles if m > threshold] + [threshold * (1 + u) for u in (0.01, 0.1, 0.5)]
    return max(process.sigma(r * r) for r in roots)
