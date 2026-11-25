"""Long-range effects today for the generic engine (G8): the broken-phase multi-state Sommerfeld effect of the
dark-matter pair, with its potentials and annihilation matrices from G3.

**The states.** The dark-matter pair today and every two-particle state it reaches through the potential: the
neutral block (total charge 0) of the pair's group in G7 (``generic_lr``), as ordered pairs (a, b).

**The thresholds.** Each state lies Δ = m_a + m_b − 2m_χ above the dark-matter pair. G1's masses are tree-level, so
the components of a pure electroweak n-plet are split at one loop as well (M ≫ M_W; Cirelli, Fornengo & Strumia,
hep-ph/0512090 eq. (3)):

    M_Q − M_0 = (α₂/2) [Q² s_W² M_Z + Q(Q − 2Y)(M_W − M_Z)],   s_W² = 1 − M_W²/M_Z²,

165 MeV for the wino and 353 MeV for the higgsino (the library takes 165 and 341).

**The potential, boson by boson.** In G7's heavy copy of the model with only the vertices of one boson B (W, Z, γ,
h, a new mediator), the elastic amplitudes give its coupling matrix α^B (G7's method); then

    V(r) = −Σ_B α^B e^{−m_B r}/r,

with the photon's (and any massless boson's) diagonal as each state's Coulomb tail. Nothing is written by hand:
the wino's Q = 0 matrix comes out as Hisano et al.'s, in the ordered basis (χ⁰χ⁰, χ⁺χ⁻, χ⁻χ⁺). The W, Z and γ terms
take the couplings at M_Z (α₂ = 0.0347, α = 1/128.9; Beneke et al., as ``portals.multiplet``) rather than G2's
G_F-scheme ones: 2% in α moves a zero-energy resonance by 2% in mass, and the rate near it by much more. Γ takes
G7's hard-scale factor.

**Annihilation by final state.** Γ^f over the same states and spins from G3 at threshold (G7's ``annihilation``,
one final state at a time). With A the wave functions at the origin (``sommerfeld.enhancement``),

    σv_f = (1/g²) Σ_S Tr_S[(A ⊗ 1)† Γ^f_S (A ⊗ 1)]_{χχ},

summed over the pair's total spin S (σ/2 per leg), each S only where the dark-matter pair can be in an s-wave with
it: S = 0 for two identical fermions, every S otherwise. Without the potential this is G6's tree-level σv.

**A higgsino-like Dirac doublet** (a pure SU(2) doublet with Y = ½, ``generic_lhc.pure_dark_kind``; AL2-02,
2026-11-14): its neutral states are split into Majorana states today, as the library's higgsino and both routes' lines
take them, so only the lightest annihilates, as two identical fermions: S = 0 only, and the rate doubled against the
searches' halving for a Dirac pair (``split_today``).

**Lines.** γγ and Zγ come out at tree level with the Sommerfeld effect (the charged states at the origin). The
exclusive photon final state is suppressed by electroweak Sudakov logarithms (0.3–0.8 at 1–10 TeV for the wino), which
are not computed: the line searches stay undecided for an electroweak multiplet, with that reason; the rates are
reported.
"""

from __future__ import annotations

import math

import numpy as np

from adroit.constraints import sommerfeld
from adroit.constraints.annihilation import GEV2_TO_CM3_S
from adroit.parameter_space.portals import generic_lr as lr

R_W = 1.0 / 80.377                      # GeV⁻¹: the W's range, the scale of r_max (as ``portals.multiplet``)
LINES_REASON = ("γ-ray lines of an electroweak multiplet need the electroweak Sudakov resummation of the exclusive "
                "photon final state (a factor 0.3–0.8 at 1–10 TeV), which is computed only for a pure wino or "
                "higgsino (DMγSpec) and a pure Majorana odd n-plet at 1–100 TeV (NLL); the tree-level Sommerfeld "
                "rate is no bound either way (near a zero of its amplitude the resummed rate is larger), so the "
                "lines are undecided")


def splitting(n: int, y: float, q: float, m_w: float, m_z: float, alpha_2: float) -> float:
    """M_Q − M_0 at one loop for a component of charge Q of an n-plet with hypercharge Y (module docstring)."""
    s2 = 1.0 - (m_w / m_z) ** 2
    return 0.5 * alpha_2 * (q * q * s2 * m_z + q * (q - 2.0 * y) * (m_w - m_z))


def boson_copy(heavy, boson: str):
    """G7's heavy copy with only the vertices that carry ``boson`` (or its antiparticle)."""
    from adroit.constraints import tree
    anti = heavy.particles[boson].conjugate
    out = tree.Model(heavy.particles, [v for v in heavy.vertices if boson in v.legs or anti in v.legs])
    out.parity = getattr(heavy, "parity", {})
    return out


def neutral_block(found: lr.LongRange, mb, model):
    """(the dark matter's group, its neutral block of ordered pairs, the dark-matter pair's index), or None where G7
    has not decomposed the pair's group or it carries colour."""
    dm = mb.spectrum.dark_matter()
    anti = dm.name if dm.kind in ("real", "majorana", "vector") else f"{dm.name}~"
    for grp in found.groups:
        for block in lr.blocks(model, grp.a, grp.b):
            for pair in ((dm.name, anti), (anti, dm.name)):
                if pair in block and grp.a.colour == "1" and grp.b.colour == "1":
                    return grp, block, block.index(pair)
    return None


def thresholds(mb, model, grp, block) -> np.ndarray:
    """Δ of each state above the dark-matter pair (GeV), with the one-loop splitting of a pure n-plet's components."""
    from adroit.parameter_space.portals.multiplet import ALPHA_2_MZ, M_W, M_Z
    dm = mb.spectrum.dark_matter().mass_gev

    def mass(name: str, mult) -> float:
        particle = model.particles[name]
        q = -particle.charge if name.endswith("~") else particle.charge
        y = -mult.y if mult.anti else mult.y
        extra = splitting(mult.n, y, q, M_W, M_Z, ALPHA_2_MZ) if mult.n > 1 else 0.0
        return particle.mass + extra
    neutral = min(mass(a, grp.a) + mass(b, grp.b) for a, b in block)
    out = np.array([mass(a, grp.a) + mass(b, grp.b) for a, b in block]) - neutral
    return np.maximum(out, 0.0) if dm > 0 else out


def _low_scale(name: str) -> float:
    """The electroweak bosons' couplings at the potential's scale: α₂(M_Z) = 0.0347 for W and Z and α(M_Z) = 1/128.9
    for the photon (Beneke et al., as ``portals.multiplet``), against G2's tree-level couplings (G_F scheme)."""
    from adroit.model_building.gauge_basis import G1, G2
    from adroit.parameter_space.portals.multiplet import ALPHA_2_MZ, ALPHA_EM
    a2 = G2 ** 2 / (4 * math.pi)
    e2 = (G1 * G2) ** 2 / (G1 ** 2 + G2 ** 2) / (4 * math.pi)
    return {"W": ALPHA_2_MZ / a2, "Z": ALPHA_2_MZ / a2, "A": ALPHA_EM / e2}.get(name, 1.0)


def potential_terms(model, block) -> list[tuple[np.ndarray, float]]:
    """(α^B over the block's pairs, m_B) for each boson B that joins them (module docstring), the electroweak ones
    at the potential's scale (``_low_scale``)."""
    heavy = lr.heavy_copy(model)
    parity = getattr(model, "parity", {})
    seen, out = set(), []
    for name, particle in model.particles.items():
        if parity.get(name, 1) != 1 or particle.spin == 0.5 or particle.conjugate in seen:
            continue
        seen.add(name)
        alpha = lr.potential(boson_copy(heavy, name), block)
        if alpha.shape[0] != len(block):
            return []                                 # colour: not the dark-matter pair's sector today
        alpha = np.real(alpha) * _low_scale(name)
        if np.max(np.abs(alpha), initial=0.0) > 1e-9:
            out.append((alpha, particle.mass))
    return out


def matching_radius(masses: list[float], mu: float, kinetic: float) -> float:
    """The radius (GeV⁻¹) where the waves are matched: past the reach of the lightest massive boson of the potential
    (40 ranges; the W's 30 where none is lighter) and six wavelengths, at most 400 of those ranges. The audit's G8-1
    (G12): it had been the W's range alone, so a sub-GeV mediator was matched inside its own potential (S = 8.8
    against 78 for α = 0.01, m = 100 GeV, m_V = 0.1 GeV, v = 10⁻⁴)."""
    massive = [x for x in masses if x > 0.0]
    reach = 40.0 / min(massive) if massive and min(massive) < 1.0 / R_W else 30.0 * R_W
    return min(max(reach, 6.0 / math.sqrt(2.0 * mu * kinetic)), 400.0 * max(reach / 40.0, R_W))


def split_today(mb, rules) -> bool:
    """True for a higgsino-like Dirac doublet, whose lightest Majorana state alone annihilates today (module
    docstring)."""
    from adroit.parameter_space.portals.generic_lhc import pure_dark_kind
    return mb.spectrum.dark_matter().kind == "dirac" and pure_dark_kind(mb, rules) == "higgsino"


def rates_today(mb, rules, model, found: lr.LongRange, v_rel: float) -> dict[str, float] | None:
    """σv (cm³/s) by final state of the dark-matter pair at relative speed v_rel with the broken-phase Sommerfeld
    effect (module docstring), or None where G8 does not apply."""
    from adroit.parameter_space.portals.generic import final_states
    from adroit.parameter_space.portals.generic_id import channel_name
    found_block = neutral_block(found, mb, model)
    if found_block is None:
        return None
    grp, block, j = found_block
    terms = potential_terms(model, block)
    if not terms:
        return None
    delta = thresholds(mb, model, grp, block)
    if delta[j] > 0.0:            # a charged pair lies below the dark matter's (the audit's G8-9, G12): not computed
        return None
    tails = np.array([sum(a[i, i] for a, mass in terms if mass == 0.0) for i in range(len(block))])

    def potential(r):
        return -sum(a * math.exp(-mass * r) for a, mass in terms) / r
    m = mb.spectrum.dark_matter().mass_gev
    mu, kinetic = 0.5 * m, 0.25 * m * v_rel ** 2
    r_max = matching_radius([mass for _, mass in terms], mu, kinetic)
    amplitude = sommerfeld.enhancement(potential, delta, tails, mu, kinetic, r_max=r_max)[:, j]
    spin = grp.a.spin
    projectors = lr.spin_projectors(spin)
    dm = mb.spectrum.dark_matter()
    split = split_today(mb, rules)
    identical = dm.kind in ("real", "majorana") or split
    allowed = [s for s in projectors if not (identical and spin == 0.5 and s == 1)]
    out: dict[str, float] = {}
    for f in sorted({f for pair in block for f in final_states(model, *pair)}):
        gamma, spins = lr.annihilation(model, block, [f])
        if gamma is None:
            continue
        a = np.kron(amplitude.reshape(-1, 1), np.eye(spins))           # (pairs × spins, spins)
        x = a.conj().T @ gamma @ a
        value = grp.running * sum(float(np.real(np.trace(projectors[s] @ x))) for s in allowed
                                  if projectors[s].shape == x.shape)
        if value > 0:
            name = channel_name(*f)
            out[name] = out.get(name, 0.0) + (2.0 if split else 1.0) * value / spins * GEV2_TO_CM3_S
    return out
