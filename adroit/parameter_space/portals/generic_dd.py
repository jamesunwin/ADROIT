"""Direct detection for the generic engine (G5): the tree level, the loop library keyed by structure, inelastic
scattering and the fallback.

**The tree level** is ``model_building.dd_matching``: G2's vertices matched onto DirectDM's basis, and c₁, c₄ at q → 0.

**The loop library**, consulted where the tree-level spin-independent coupling vanishes:
- **an electroweak multiplet:** dark matter that is (to 99%) one SU(2) n-plet of hypercharge Y, n ≤ 5, gets the
  n-plet engine's two-loop σ_SI (``nplet.sigma_si``: Bottaro et al., with Hisano et al.'s nucleon inputs);
- **a coloured partner of Majorana dark matter** (one chirality): the scalar, twist-2 and gluon couplings of Hisano,
  Ishiwata & Nagata (``loops.coloured_partner_si``), c₁ = 2f_N as in ``portals.tchannel``;
- **a lepton partner of Majorana dark matter:** its anapole (``loops.anapole_moment``), compared through Path 1's
  tabulated structure (``operator_limits``).

**Inelastic scattering.** A Z₂-odd neutral state within xenon's kinematic reach (450 keV) above the dark matter,
joined to it by a vector that also couples to quarks, scatters inelastically. That is compared through Path 1 only:
the point's direct detection is ``inelastic`` if nothing scatters elastically, and the inelastic channel is pending
either way.

**The fallback.** Where no tree-level coupling survives at q → 0 and no loop entry applies, the scattering is
loop-dominated and not computed: the searches are undecided, and the reason is pending.

**Path 1** receives DirectDM's full nonrelativistic operator set (``interaction``), with every coefficient's q
dependence, for any comparison that needs more than c₁ and c₄.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from adroit.model_building import dd_matching as dd
from adroit.parameter_space.portals.base import Nucleon, c1_of_sigma

XENON_REACH_GEV = 450e-6               # the largest splitting xenon can scatter across (``nplet``)
PURE = 0.99                            # a state this much one field is that field's multiplet
LEPTONS = {"e": 0.000511, "mu": 0.10566, "tau": 1.77686}


@dataclass
class Scattering:
    """What the generic engine says about direct detection at one point."""
    nucleon: Nucleon
    matching: dd.Matching
    route: str                                  # tree, loop (...), tree + loop (...), inelastic, none
    pending: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    inelastic: bool = False


# --- the loop library ------------------------------------------------------------------------------------------

def _composition(mb, state) -> tuple[str, float]:
    """(the dominant field, its share of the state)."""
    from adroit.parameter_space.portals.generic_checks import dominant_field
    from adroit.parameter_space.portals.generic_lr import _share
    f = dominant_field(mb, state)
    return f.name, _share(state, f.name)


def _multiplet(mb) -> tuple[float, float, str] | None:
    """(c₁ᵖ, c₁ⁿ, label) of a pure electroweak n-plet, n ≤ 5."""
    from adroit.parameter_space.portals.nplet import sigma_si
    dm = mb.spectrum.dark_matter()
    name, share = _composition(mb, dm)
    f = mb.gauge.spec.field(name)
    n, y = f.charges.su2, abs(f.charges.hypercharge)
    if n < 2 or n > 5 or share < PURE or dm.spin != 0.5:
        return None
    (sp, sgp), (sn, sgn) = sigma_si(n, y, "p"), sigma_si(n, y, "n")
    m = dm.mass_gev
    return c1_of_sigma(sp, m, sgp), c1_of_sigma(sn, m, sgn), f"the electroweak {n}-plet's loops (n-plet engine)"


def _coloured(m: dd.Matching) -> tuple[float, float, str] | None:
    """(c₁ᵖ, c₁ⁿ, label) of Majorana dark matter's coloured partners of one chirality (``loops``)."""
    from adroit.constraints import loops
    if m.dm_type != "M" or not m.partners:
        return None
    fp = fn = 0.0
    for pt in m.partners:
        left, right = abs(pt.y_left), abs(pt.y_right)
        if (left and right) or pt.quark not in loops.MOMENTS["p"]:
            return None
        a, b = loops.coloured_partner_si(m.dm_mass, pt.mass, max(left, right), pt.quark)
        fp, fn = fp + a, fn + b
    return 2.0 * fp, 2.0 * fn, "the coloured partners' scalar, twist-2 and gluon couplings (Hisano et al.)"


def _lepton_partner(mb, rules) -> Nucleon | None:
    """The anapole of Majorana dark matter with charged scalar lepton partners (``loops.anapole_moment``): the sum
    over every lepton vertex and partner, whose loops add (the audit loop's AL4-03, 2026-11-16: the first vertex alone
    had been taken, so one partner coupled to e, μ and τ gave 1.90 times too small an anapole)."""
    from adroit.constraints import loops
    dm = mb.spectrum.dark_matter()
    if dm.kind != "majorana":
        return None
    by = {p.name: p for p in rules.particles} | {p.anti: p for p in rules.particles if p.anti}
    moments = {}
    for v in rules.vertices:
        if v.kind != "FFS" or v.legs[0] != dm.name or v.legs[1] not in LEPTONS:
            continue
        phi = by.get(v.legs[2])
        if phi is None or phi.parity != -1 or phi.spin != 0 or phi.colour != "1":
            continue
        y = max(abs(v.c - 1j * v.c2), abs(v.c + 1j * v.c2))
        key = (LEPTONS[v.legs[1]], phi.name)                 # a vertex and its conjugate are one loop
        moments[key] = max(moments.get(key, 0.0), loops.anapole_moment(dm.mass_gev, phi.mass, y, key[0]))
    if not moments:
        return None
    return Nucleon(structure="anapole", scale=sum(moments.values()))


# --- inelastic scattering --------------------------------------------------------------------------------------

def inelastic_partner(mb, rules) -> str:
    """A neutral Z₂-odd state within xenon's reach above the dark matter, joined to it by a boson that couples to
    quarks (a vector through FFV or VSS, a scalar through FFS or SSS); "" if none. The audit's G5-2 (G12): a scalar
    dark matter joined to its partner through a VSS vertex (the inert doublet's H⁰A⁰Z) had not been found."""
    dm = mb.spectrum.dark_matter()
    near = {s.name: s.mass_gev - dm.mass_gev for s in mb.spectrum.states
            if s.parity == -1 and s.charge == 0 and s.name != dm.name and 0 < s.mass_gev - dm.mass_gev < XENON_REACH_GEV}
    if not near:
        return ""
    to_quarks = {v.legs[2].rstrip("~") for v in rules.vertices
                 if v.kind in ("FFV", "FFS") and v.legs[0].rstrip("~") in dd.QUARKS}
    for v in rules.vertices:
        if v.kind not in ("FFV", "FFS", "VSS", "SSS"):
            continue
        bosons = [x for x in v.legs if x.rstrip("~") in to_quarks]
        if len(bosons) != 1:
            continue
        ends = {x.rstrip("~") for x in v.legs if x != bosons[0]}
        other = (ends - {dm.name}).pop() if dm.name in ends and len(ends) == 2 else None
        if other in near:
            return f"{other}, {1e6 * near[other]:.3g} keV above the dark matter, through {bosons[0]}"
    return ""


# --- assembling the point ----------------------------------------------------------------------------------------

def _tree(m: dd.Matching) -> dict[str, float]:
    return dd.nucleon_couplings(m)


def scattering(mb, rules) -> Scattering:
    """The point's direct detection (module docstring)."""
    m = dd.match(mb, rules)
    c = _tree(m)
    notes = list(m.notes) + dd.contact_notes(m)
    route = "tree" if any(c.values()) else ""
    if not (c["c1_p"] or c["c1_n"] or c["c1_p_odd"] or c["c1_n_odd"]):
        loop = _multiplet(mb) if not c["c4_p"] and not c["c4_n"] else None
        loop = loop or _coloured(m)
        if loop:
            c["c1_p"], c["c1_n"], label = loop
            route = f"{route} + loop ({label})" if route else f"loop ({label})"
    pending = [f"direct detection: {dd.TENSOR_CONTACT}"] if dd.TENSOR_CONTACT in m.notes else []
    pending += [f"direct detection: {n}" for n in m.notes if dd.MIXED_CONVENTION in n]
    partner = inelastic_partner(mb, rules)
    if partner:
        pending.append(f"direct detection: inelastic scattering to {partner}, compared through Path 1 only")
    if any(c.values()):
        return Scattering(Nucleon(**c), m, route, pending, notes, inelastic=bool(partner))
    anapole = _lepton_partner(mb, rules)
    if anapole is not None:
        return Scattering(anapole, m, "loop (the lepton partner's anapole)", pending, notes)
    if partner:
        return Scattering(Nucleon(suppressed="inelastic only"), m, "inelastic", pending, notes, inelastic=True)
    suppressed = dd.momentum_suppressed(m)
    if suppressed:
        return Scattering(Nucleon(suppressed=f"momentum-suppressed at tree level ({', '.join(suppressed)})"), m,
                          "tree (momentum-suppressed)", pending, notes)
    pending.append("direct detection: loop-dominated, not computed (no tree-level coupling at q → 0 and no loop "
                   "entry for this structure)")
    return Scattering(Nucleon(suppressed="loop-dominated, not computed"), m, "none", pending, notes)


def interaction(m: dd.Matching, name: str):
    """DirectDM's full nonrelativistic interaction of the tree-level coefficients ((particle, InteractionModel)), or
    None where DirectDM does not apply (spin-1 dark matter, no coefficient, DirectDM not set up)."""
    from adroit.library.interactions import quark_level as ql
    if m.dm_type == "V" or not m.coefficients or not ql.available():
        return None
    model = ql.QuarkLevelModel(name=name, dm_type=ql.DMType(m.dm_type), flavours=5, coefficients=m.coefficients,
                               dropped=list(m.notes), references=["G5 tree-level matching (dd_matching)"])
    return ql.to_interaction(model, m.dm_mass)
