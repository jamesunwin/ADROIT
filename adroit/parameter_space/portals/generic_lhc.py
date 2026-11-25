"""Colliders for the generic engine (G9): an SLHA spectrum from G1 and G2 for SModelS, production from the LHC SUSY
Cross Section Working Group's tables by quantum numbers, and the Higgs's signal strength from scalar mixing.

**The spectrum.** Every Z₂-odd state of the model, with its quantum numbers (QNUMBERS), its mass, and its decays:
- two-body decays from G2's vertices (``feynman.two_body_width``), into Standard Model particles or other states;
- a near-degenerate pure electroweak n-plet: its components split at one loop (``generic_today.splitting``), the
  charged ones decaying to the neutral one and a pion (``lhc.chargino_width``, as the library's wino and higgsino),
  so that SModelS sees disappearing tracks where the width is small.

**Production at 13 TeV**, by the produced multiplet's quantum numbers, as the library takes them:

| multiplet | table |
|---|---|
| fermion, SU(2) triplet, Y = 0 (wino-like) | C₁±C₁∓, C₁±N₂ (aNNLO+NNLL) |
| fermion, SU(2) doublet, Y = ½ (higgsino-like) | C₁C₁, N₁C₁±, N₁N₂ (aNNLO+NNLL) |
| scalar, colour triplet, SU(2) singlet | the stop table (NNLO+NNLL, QCD only: not a lower bound where t-channel exchange adds and interferes, so it decides nothing, decision D33) |
| scalar, colour singlet, SU(2) singlet, Q = ±1 | the right-handed slepton table (NLO+NLL) |

Only a pure multiplet (``generic_lr.PURE``) reads these tables; a mixed dark matter state (singlet–doublet,
doublet–triplet) does not. A partner with no two-body decay to the dark matter and an SM fermion gives SModelS no
topology; one whose mass is outside its table, or whose table is not installed, has no cross-section; each is named as
such. Any other produced multiplet, a mixed state or a model with more than one partner sector takes MadGraph's
complete tree-level production of the model's own states (``madgraph_spectrum``, ``constraints.pair_production``).

**The Higgs's signal strength** for a model whose 125 GeV state mixes with a new scalar: μ = c⁴Γ_SM/(c²Γ_SM + Γ_new),
with c² that state's H⁰ share and Γ_new its width into new states, against ATLAS's combined μ (the library's record,
``searches.higgs_signal``). The measurement is the state's at the measured mass (``measured_higgs``: the one neutral
scalar within 3 GeV of 125.09 GeV identifies it; μ is decided only within 2σ of the measured mass), and the formula is
the record's singlet mixing: its couplings to the SM fermions, W and Z one common rescaling with κ² = c², CP-even, to
numerical accuracy, and no new charged or coloured state in its loops (``_rescaling_reason``); otherwise the search is
undecided, the reason named.
"""

from __future__ import annotations

import subprocess

from adroit.parameter_space.portals import generic_lr as lr

TABLE_PDG = {"wino": (1000022, 1000024), "higgsino": (1000022, 1000023, 1000024)}
STOP, SLEPTON = 1000006, 1000011
PION = 211


def _kind(m: lr.Multiplet) -> str:
    """The table a multiplet's pair production is read from (module docstring), or ""."""
    if m.spin == 0.5 and m.n == 3 and m.y == 0 and m.colour == "1" and m.self_conjugate:
        return "wino"                     # a Dirac triplet is not the Majorana wino (the audit's G9-3, G12)
    if m.spin == 0.5 and m.n == 2 and abs(m.y) == 0.5 and m.colour == "1":
        return "higgsino"
    if m.spin == 0 and m.n == 1 and m.colour in ("3", "3bar"):
        return "coloured"
    if m.spin == 0 and m.n == 1 and m.colour == "1" and abs(m.y) == 1.0:
        return "slepton"
    return ""


def odd_states(rules) -> list[tuple[str, float, float]]:
    """Every Z₂-odd state, particle and antiparticle, at any mass (the bath's form, without its mass cut: a heavy
    partner is produced at the LHC whether or not it coannihilates)."""
    out = []
    for x in rules.particles:
        if x.parity == -1:
            out.append((x.name, x.mass, 1.0))
            if x.anti:
                out.append((x.anti, x.mass, 1.0))
    return out


def multiplet_spectrum(kind: str, m: float) -> tuple[str, float | None]:
    """(SLHA, σ in pb) of a wino- or higgsino-like dark multiplet at mass m, with its one-loop splitting."""
    from adroit.constraints import lhc
    from adroit.parameter_space.portals.generic_today import splitting
    from adroit.parameter_space.portals.multiplet import ALPHA_2_MZ, M_W, M_Z
    n, y, weight = (3, 0.0, 2.0) if kind == "wino" else (2, 0.5, 1.0)
    delta = splitting(n, y, 1, M_W, M_Z, ALPHA_2_MZ)
    neutral = dict(charge3=0, spin_states=2, colour=1, distinct=False)
    charged = dict(pdg=1000024, label="chi+", charge3=3, spin_states=2, colour=1, distinct=True, mass=m + delta)
    decays = {1000024: (lhc.chargino_width(delta, weight), [(1.0, [1000022, PION])])}
    if kind == "wino":
        particles = [dict(pdg=1000022, label="chi0", mass=m, **neutral), charged]
        xs = [((1000022, 1000024), lhc.cross_section_pb("wino_c1p_n", m)),
              ((1000022, -1000024), lhc.cross_section_pb("wino_c1m_n", m)),
              ((1000024, -1000024), lhc.cross_section_pb("wino_c1c1", m))]
    else:                                               # as the library's higgsino (``searches``)
        particles = [dict(pdg=1000022, label="chi01", mass=m, **neutral),
                     dict(pdg=1000023, label="chi02", mass=m + 1e-3, **neutral), charged]
        decays = {1000024: (lhc.chargino_width(delta, weight), [(0.5, [1000022, PION]), (0.5, [1000023, PION])])}
        plus, minus = lhc.cross_section_pb("hino_n1c1p", m), lhc.cross_section_pb("hino_n1c1m", m)
        xs = [((1000022, 1000024), plus), ((1000022, -1000024), minus), ((1000023, 1000024), plus),
              ((1000023, -1000024), minus), ((1000024, -1000024), lhc.cross_section_pb("hino_c1c1", m)),
              ((1000022, 1000023), lhc.cross_section_pb("hino_n1n2", m))]
    if any(x is None for _, x in xs):
        return "", None
    return lhc.slha(particles, decays, xs), sum(x for _, x in xs)


def partner_spectrum(kind: str, mb, rules, partner) -> tuple[str, float | None, str]:
    """(SLHA, σ in pb, why not) of a coloured or slepton-like scalar partner decaying to the dark matter and an SM
    fermion; why not names the missing decay, the mass outside the production table, or the table not installed."""
    from adroit.constraints import lhc
    from adroit.model_building.ufo_export import SM_NAMES
    dm = mb.spectrum.dark_matter()
    name = partner.states[0]
    x = next(p for p in rules.particles if p.name == name)
    channels = []
    dm_legs = {dm.name, f"{dm.name}~"}                   # a Dirac dark matter's vertices carry χ or χ̄ (G9-5)
    for v in rules.vertices:
        if v.kind == "FFS" and name in [leg.rstrip("~") for leg in v.legs] and dm_legs & set(v.legs):
            sm = next((leg for leg in v.legs if leg.rstrip("~") in SM_NAMES), None)
            if sm is not None:
                channels.append(abs(SM_NAMES[sm.rstrip("~")][2]))
    if not channels:
        return "", None, (f"the partner {partner.field} has no two-body decay to the dark matter and an SM fermion in "
                          "the model, so SModelS has no topology for it")
    pdg = STOP if kind == "coloured" else SLEPTON
    chi = 1000022
    sigma = lhc.cross_section_pb(kind, x.mass)
    if sigma is None:
        span = lhc.table_range(kind)
        if span is None:
            return "", None, (f"the partner {partner.field}'s pair production needs the {kind} production table, "
                              "which is not in the tools folder (`adroit setup --fetch`)")
        return "", None, (f"the partner {partner.field}'s mass, {x.mass:g} GeV, is outside the {kind} production "
                          f"table ({span[0]:g}–{span[1]:g} GeV), so its pair production has no cross-section here")
    width = max(x.width, 1e-10)
    particles = [dict(pdg=pdg, label="phi", charge3=round(3 * x.charge), spin_states=1,
                      colour=3 if kind == "coloured" else 1, distinct=True, mass=x.mass),
                 dict(pdg=chi, label="chi", charge3=0, spin_states=int(2 * dm.spin + 1), colour=1,
                      distinct=dm.kind not in ("majorana", "real"), mass=dm.mass_gev)]
    return lhc.slha(particles, {pdg: (width, _partner_branchings(rules, name, dm.name, chi, x.charge))},
                    [((pdg, -pdg), sigma)]), sigma, ""


SM_CHARGE = {1: -1 / 3, 2: 2 / 3, 3: -1 / 3, 4: 2 / 3, 5: -1 / 3, 6: 2 / 3, 11: -1.0, 13: -1.0, 15: -1.0}


def _conserving(code: int, charge: float) -> int:
    """The SM fermion's code, or its antiparticle's, carrying the partner's charge (the audit's G9-7, G12)."""
    return -code if abs(SM_CHARGE.get(code, 0.0) + charge) < 1e-9 and charge != 0 else code


def _partner_branchings(rules, name: str, dm: str, chi: int, charge: float = 0.0) -> list[tuple[float, list[int]]]:
    """The partner's branchings to the dark matter and each SM fermion, from its two-body decays
    (``pair_production.decay_table``); any other open decay keeps its share out of the table (the audit's G9-2, G12:
    the first channel had been written with branching 1). The fermion is signed so that the decay conserves the
    partner's ``charge``."""
    from adroit.constraints import pair_production as pp
    from adroit.model_building import ufo_export as ux
    table = ux.names(rules)
    dm_code = abs(table[dm][2])
    shares: dict[int, float] = {}
    for br, daughters in pp.decay_table(rules, table, name)[1]:
        sm = [abs(c) for c in daughters if abs(c) != dm_code]
        if len(daughters) == 2 and len(sm) == 1:
            shares[sm[0]] = shares.get(sm[0], 0.0) + br
    return [(br, [chi, _conserving(code, charge)]) for code, br in sorted(shares.items())]


def pure_dark_kind(mb, rules) -> str:
    """The table kind (``_kind``) of the dark matter's multiplet if every one of its states is pure, else ""."""
    dm = mb.spectrum.dark_matter().name
    mults, impure = lr.multiplets(mb, odd_states(rules))
    mixed = {x.split(" (")[0] for x in impure}
    dark = next((m for m in mults if dm in m.states and not m.anti), None)
    return _kind(dark) if dark is not None and not mixed & set(dark.states) else ""


def pure_majorana_nplet(mb, rules) -> int:
    """n if the dark matter is a pure Majorana fermion n-plet with odd n ≥ 3, Y = 0 and no colour (every state
    pure), else 0."""
    dm = mb.spectrum.dark_matter()
    mults, impure = lr.multiplets(mb, odd_states(rules))
    mixed = {x.split(" (")[0] for x in impure}
    dark = next((m for m in mults if dm.name in m.states and not m.anti), None)
    if dark is None or mixed & set(dark.states) or dm.kind != "majorana":
        return 0
    pure = dark.spin == 0.5 and dark.n % 2 == 1 and dark.n >= 3 and dark.y == 0 and dark.colour == "1"
    return dark.n if pure else 0


def lhc_spectrum(mb, rules) -> tuple[str, float | None, str]:
    """(SLHA, σ in pb, why not) for SModelS (module docstring)."""
    dm = mb.spectrum.dark_matter().name
    mults, impure = lr.multiplets(mb, odd_states(rules))
    mixed = {x.split(" (")[0] for x in impure}
    dark = next((m for m in mults if dm in m.states and not m.anti), None)
    sectors = [m for m in mults if not m.anti]
    if mixed or len(sectors) > 2 or (len(sectors) == 2 and dark is not None and _kind(dark) in ("wino", "higgsino")):
        # a table covers one sector; with any other odd state produced, every one comes from MadGraph together
        # (the audit's G9-1, G12: the others had been dropped, so a coloured partner's exclusion read "allowed")
        return madgraph_spectrum(mb, rules)
    if dark is not None and _kind(dark) in ("wino", "higgsino"):
        if mixed & set(dark.states):                    # the pure tables do not apply: MadGraph's own
            return madgraph_spectrum(mb, rules)
        text, sigma = multiplet_spectrum(_kind(dark), mb.spectrum.dark_matter().mass_gev)
        if sigma is not None:
            return text, sigma, ""
        return madgraph_spectrum(mb, rules)            # beyond the electroweakino tables: MadGraph's LO
    partners = [m for m in mults if not m.anti and dm not in m.states and _kind(m) in ("coloured", "slepton")
                and not mixed & set(m.states)]
    reasons = []
    for partner in partners:
        text, sigma, why = partner_spectrum(_kind(partner), mb, rules, partner)
        if sigma is not None:
            return text, sigma, ""
        reasons.append(why)
    if partners:
        return "", None, "; ".join(reasons)
    return madgraph_spectrum(mb, rules)


def with_loop_splittings(mb, rules):
    """The rules with each pure electroweak multiplet's components split at one loop (G1's tree-level masses of a
    pure multiplet are degenerate; ``generic_today.splitting``), so that its charged states can decay."""
    import dataclasses
    from adroit.parameter_space.portals.generic_today import splitting
    from adroit.parameter_space.portals.multiplet import ALPHA_2_MZ, M_W, M_Z
    mults, impure = lr.multiplets(mb, odd_states(rules))
    mixed = {x.split(" (")[0] for x in impure}
    shift = {}
    for m in mults:
        if m.n < 2 or m.colour != "1" or m.anti or mixed & set(m.states):   # the anti-multiplet would overwrite
            continue                                                        # the shifts with q·Y's sign flipped (G9-4)
        for name in m.states:
            x = next((p for p in rules.particles if name in (p.name, p.anti)), None)
            if x is not None and x.charge:
                shift[x.name] = splitting(m.n, abs(m.y), abs(x.charge) if m.y == 0 else x.charge * (1 if m.y > 0 else -1),
                                          M_W, M_Z, ALPHA_2_MZ)
    if not shift:
        return rules
    return dataclasses.replace(rules, particles=[dataclasses.replace(p, mass=p.mass + shift[p.name]) if p.name in shift
                                                 else p for p in rules.particles])


SPINS = {0: 1, 0.5: 2, 1: 3}
COLOURS = {"1": 1, "3": 3, "3bar": 3, "8": 8}


def madgraph_spectrum(mb, rules) -> tuple[str, float | None, str]:
    """(SLHA, σ in pb, why not) from MadGraph's leading-order pair production of the model's own new states
    (``constraints.pair_production``), where no table applies."""
    from adroit.constraints import lhc
    from adroit.constraints import pair_production as pp
    from adroit.model_building import ufo_export as ux
    dm = mb.spectrum.dark_matter().name
    rules = with_loop_splittings(mb, rules)
    prod = pp.production_rules(rules)
    odd = [p for p in prod.particles if p.parity == -1]
    visible = [p for p in odd if p.name != dm]
    if not visible:
        return "", None, ("only the dark matter is new and odd: its pair production leaves nothing to see (the "
                          "monojet and mono-X searches are separate records)")
    if 2 * min(p.mass for p in visible) > pp.REACH * pp.SQRT_S:
        return "", None, "the model's new states are too heavy to be pair-produced at the LHC"
    if not pp.available():
        return "", None, "MadGraph is not in the tools folder, so no production cross-section is computed (G9)"
    table = ux.names(prod)
    decays = {}
    for p in visible:
        width, channels = pp.decay_table(prod, table, p.name)
        if not channels:                                 # through an off-shell W to a lighter partner
            width, channels = pp.soft_decay_table(prod, table, p.name)
        if not channels:
            return "", None, (f"{p.name} has no open two-body decay and no decay through an off-shell W to a lighter "
                              "partner (computed for fermions; a scalar's, and any through an off-shell Z, are not), "
                              "so SModelS would take it as stable")
        decays[table[p.name][2]] = (width, channels)
    try:
        found = pp.cross_sections(rules, dm, mb.gauge.spec.name)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        return "", None, f"MadGraph failed: {str(error)[:200]}"
    xs = [((int(a), int(b)), sigma) for key, sigma in found["pairs"].items() for a, b in [key.split()]]
    if not xs:
        return "", None, "MadGraph produced no pair of the model's visible new states"
    particles = [dict(pdg=table[p.name][2], label=table[p.name][0].rstrip("~"),
                      charge3=round(3 * pp.sign(p, table) * p.charge),
                      spin_states=SPINS.get(p.spin, 1), colour=COLOURS.get(p.colour, 1),
                      distinct=bool(p.anti) and p.anti != p.name, mass=p.mass) for p in odd]
    text = lhc.slha(particles, decays, xs, order=0, label=pp.LABEL)
    return text, sum(sigma for _, sigma in xs), ""


IDENTIFY_WINDOW = 3.0     # GeV about m_h: which state may be the observed Higgs (identification, not compatibility)
MASS_SIGMAS = 2.0         # μ is decided only for a state within 2σ of the measured m_h (higgs.M_H_SIGMA)
KAPPA_NUMERICAL = 1e-4    # couplings equal to the generator's numerical accuracy (a pure doublet's: within 5 × 10⁻⁷)
HIGGS_KEYS = ("H[m=-0.5,re]", "h[m=0,r]")
LOOP_BOSONS = frozenset({"A", "W", "W~", "Z", "g"})


def measured_higgs(mb, rules) -> tuple[object | None, str]:
    """(the state ATLAS's signal strength is of, "") or (None, why it cannot be named). The record's μ is the 125 GeV
    state's (atlas-2207.00092-higgs-mu), so the measurement binds by mass, not by the largest doublet share nor by
    the name h (the RZ23 re-audit's RF23-01, 2026-10-23: a 2.5 GeV state 98% doublet had supplied μ, and the 125 GeV
    state 2% doublet that the measurement sees was never tested). ``IDENTIFY_WINDOW`` identifies the one Z₂-even
    neutral scalar that may be the observed Higgs; it is a declared identification rule, not the experiments'
    resolution nor an allowed mass interval (a state 3 GeV away is not thereby compatible with m_h). None there, or
    several (their combined signal is not implemented), is named. The identified state's μ is decided only where its
    mass is compatible with the measured m_h (``MASS_SIGMAS``; the owner's review, 2026-10-23); elsewhere the signal
    strength measured at m_h is not reinterpreted, and the search is pending."""
    from adroit.constraints import higgs
    near = [st for st in _neutral_scalars(mb) if abs(st.mass_gev - higgs.M_H) <= IDENTIFY_WINDOW]
    if not near:
        return None, (f"no neutral scalar within {IDENTIFY_WINDOW:g} GeV of the measured m_h = {higgs.M_H} GeV: the "
                      "state the signal strength is measured for is not identified in the model; not computed")
    if len(near) > 1:
        names = ", ".join(f"{st.name} ({st.mass_gev:.5g} GeV)" for st in near)
        return None, (f"the neutral scalars {names} all lie within {IDENTIFY_WINDOW:g} GeV of m_h = {higgs.M_H} GeV: "
                      "their combined signal is not implemented; not computed")
    if abs(near[0].mass_gev - higgs.M_H) > MASS_SIGMAS * higgs.M_H_SIGMA:
        return None, (f"{near[0].name} at {near[0].mass_gev:.5g} GeV is the scalar identified with the observed Higgs, "
                      f"but its mass is not compatible with the measured m_h = {higgs.M_H} ± {higgs.M_H_SIGMA} GeV "
                      f"(within {MASS_SIGMAS:g}σ): the signal strength measured at m_h is not reinterpreted at another "
                      "mass; not computed")
    return near[0], ""


def _neutral_scalars(mb) -> list:
    return [st for st in mb.spectrum.states if st.spin == 0 and st.parity == 1 and abs(st.charge) < 1e-9
            and st.kind != "goldstone"]


def _mixed(mb) -> bool:
    """Whether a new scalar mixes with the H⁰ (a state with part of its share): else the search is not the model's."""
    return any(1e-12 < _share(st) < 1.0 - 1e-9 for st in _neutral_scalars(mb))


def _share(state) -> float:
    """A scalar state's H⁰ share c² (its SM-doublet components over all of its composition)."""
    total = sum(state.composition.values())
    return sum(state.composition.get(k, 0.0) for k in HIGGS_KEYS) / total if total else 0.0


def _kappas(rules, name: str) -> tuple[dict[str, complex], float]:
    """(κ by SM fermion and by W, Z, the state's coupling over the SM Higgs's; its largest CP-odd fermion coupling over
    the SM Higgs's). A fermion with no vertex has κ = 0."""
    from adroit.model_building import yukawa
    from adroit.model_building.feynman import SM_FERMIONS
    from adroit.model_building.gauge_basis import V_EW
    by = {p.name: p for p in rules.particles}
    charged = [f.name for f in SM_FERMIONS if not f.name.startswith("nu")]
    kappa: dict[str, complex] = {f: 0.0 for f in charged} | {"W": 0.0, "Z": 0.0}
    odd = 0.0
    for v in rules.vertices:
        if v.legs.count(name) != 1:
            continue
        others = [x for x in v.legs if x != name]
        if v.kind == "FFS" and others[0].rstrip("~") == others[1].rstrip("~") in kappa:
            reference = yukawa.mass(yukawa.SM, others[0].rstrip("~")) / V_EW     # the SM h's: −m_f/v (G2's sign)
            kappa[others[0].rstrip("~")] = -complex(v.c) / reference
            odd = max(odd, abs(complex(v.c2 or 0.0)) / reference)
        elif v.kind == "VVS" and sorted(o.rstrip("~") for o in others) in (["W", "W"], ["Z", "Z"]):
            boson = others[0].rstrip("~")
            kappa[boson] = complex(v.c) / (2.0 * by[boson].mass ** 2 / V_EW)          # the SM h's: 2m_V²/v
    return kappa, odd


def _rescaling_reason(rules, name: str, share: float) -> str:
    """Why μ = c⁴Γ_SM/(c²Γ_SM + Γ_new) is not this state's, or "". It holds where every coupling to the SM fermions and
    the W and Z is one common κ times the SM Higgs's with κ² = c², with no CP-odd part, and no new charged or coloured
    state runs in its gg → h or h → γγ loop (a vertex joining it to one): the record's singlet-mixing assumption. The
    couplings are compared to the generator's numerical accuracy (``KAPPA_NUMERICAL``), not to a physical tolerance
    (the owner's review, 2026-10-23: a small non-universality changes production, branching and interference by more
    than itself, and a small CP-odd part is physics, not a CP-even model): any physical departure leaves μ pending."""
    kappa, odd = _kappas(rules, name)
    scale = max(share ** 0.5, 1e-6)
    if odd > KAPPA_NUMERICAL * scale:
        return (f"{name} at the measured mass has a CP-odd coupling to the SM fermions: μ's CP-even rescaling is not "
                "its; not computed")
    common = kappa["W"]
    if any(abs(k - common) > KAPPA_NUMERICAL * scale for k in kappa.values()) or \
            abs(abs(common) ** 2 - share) > 2.0 * KAPPA_NUMERICAL * max(share, 1e-12):
        worst = max(kappa, key=lambda k: abs(kappa[k] - common))
        return (f"{name} at the measured mass does not couple to the SM states as one multiple of the SM Higgs: κ_W = "
                f"{common.real:.6g}, κ_{worst} = {kappa[worst].real:.6g}, κ_W² = {abs(common) ** 2:.6g} against its H⁰ "
                f"share c² = {share:.6g}, beyond numerical accuracy ({KAPPA_NUMERICAL:g}): μ's universal rescaling is not "
                "its; not computed")
    sm = {f for p in rules.particles if p.name in kappa for f in (p.name, p.anti) if f} | LOOP_BOSONS
    by = {p.name: p for p in rules.particles} | {p.anti: p for p in rules.particles if p.anti}
    for v in rules.vertices:
        if v.legs.count(name):
            loop = next((x for x in v.legs if x != name and x not in sm
                         and (abs(by[x].charge) > 1e-9 or by[x].colour != "1")), None)
            if loop:
                return (f"the new state {loop} (charged or coloured) couples to {name} at the measured mass: its loop "
                        "changes gg → h and h → γγ, which μ's rescaling leaves out; not computed")
    return ""


def higgs_mu_reason(mb, rules) -> str:
    """Why the 125 GeV state's signal strength is not computed (``measured_higgs``, ``_rescaling_reason``), or ""."""
    if not _mixed(mb):                                     # no new scalar mixes with the H⁰
        return ""
    state, why = measured_higgs(mb, rules)
    if why or _share(state) >= 1.0 - 1e-9:
        return why
    return _rescaling_reason(rules, state.name, _share(state))


def higgs_mu(mb, rules) -> float | None:
    """The 125 GeV state's signal strength μ = c⁴Γ_SM/(c²Γ_SM + Γ_new) (module docstring), with c² its H⁰ share; None
    without mixing or where ``higgs_mu_reason`` gives a reason. Γ_SM is the SM Higgs's width at its mass."""
    from adroit.constraints import higgs
    if not _mixed(mb) or higgs_mu_reason(mb, rules):
        return None
    state, _ = measured_higgs(mb, rules)
    share = _share(state)
    if share >= 1.0 - 1e-9:
        return None
    width = next(p.width for p in rules.particles if p.name == state.name)
    gamma_sm = float(higgs.width(state.mass_gev))
    total = max(width, share * gamma_sm)                   # c²Γ_SM + Γ_new, Γ_new = what the width holds beyond it
    return share ** 2 * gamma_sm / total if total > 0 else 0.0


YUKAWA_LIKE = 0.02                 # a scalar's quark couplings within 2% of a common multiple of the SM Yukawas


def dmsimp_scalar(mb, rules) -> dict | None:
    """The DMsimp spin-0 mediator a generic model reduces to, for CMS's monojet recast: a new even neutral scalar S
    (not the SM-like h) coupled to the dark matter and to the quarks in proportion to the SM Yukawas (g_q y_q, as a
    singlet mixing with h gives sin θ y_q), CP-even or CP-odd. {"m_med", "g_q", "g_chi", "pseudoscalar", "width",
    "br_invisible"}, or None."""
    from adroit.model_building import yukawa
    from adroit.model_building.gauge_basis import V_EW
    dm = mb.spectrum.dark_matter().name
    for s in mb.spectrum.states:
        if s.spin != 0 or s.parity != 1 or s.charge or s.name == "h":
            continue
        quark, chi = {}, None
        for v in rules.vertices:
            if v.kind != "FFS" or s.name not in v.legs:
                continue
            f = v.legs[0].rstrip("~")
            if f in ("u", "d", "s", "c", "b", "t") and v.legs[1].rstrip("~") == f:
                quark[f] = (v.c, v.c2)
            elif {v.legs[0].rstrip("~"), v.legs[1].rstrip("~")} == {dm}:
                chi = (v.c, v.c2)
        if chi is None or not quark:
            continue
        carried = yukawa.carried_masses(mb, s.name)        # the model's declared Yukawa inputs (decision #2)
        if carried is None:
            continue                                        # two conventions in one state: not DMsimp's
        pseudo = all(abs(c) < 1e-12 for c, _ in quark.values())
        ratios = [abs(c2 if pseudo else c) / (carried[f] / V_EW) for f, (c, c2) in quark.items()]
        g_q = max(ratios)
        if g_q <= 0 or min(ratios) < (1 - YUKAWA_LIKE) * g_q or len(quark) < 6:
            continue
        x = next(p for p in rules.particles if p.name == s.name)
        from adroit.parameter_space.portals import generic_id
        decays = generic_id.decays(rules, s.name, (dm, dm if dm.endswith("~") else f"{dm}~"))
        # a decay G6 cannot name leaves BR_inv unknown, not zero (the audit's G9-6, G12)
        br = None if decays is None else sum(d.branching for d in decays if d.channel == "invisible")
        top = abs(quark["t"][1] if pseudo else quark["t"][0]) * V_EW / yukawa.mass("DMsimp_s_spin0_MD", "t")
        return {"m_med": x.mass, "g_q": g_q, "g_chi": abs(complex(*chi)), "pseudoscalar": pseudo, "width": x.width,
                "br_invisible": br, "g_t": top}           # g_t: the top coupling in CMS's DMsimp card's units
    return None
