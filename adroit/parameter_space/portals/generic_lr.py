"""Long-range effects in freeze-out for the generic engine (G7): the Sommerfeld effect and bound states from the
model's own gauge representations and mediators.

**Multiplets.** The bath's states are grouped by the field each is made of (at least 99%): a self-conjugate field is
one multiplet, a complex one two (particles, antiparticles). Each pair of multiplets that a long-range force joins
is a *group*; its two-particle states are the ordered pairs (a, b), a in the first multiplet and b in the second,
with their colours and spins.

**The potential, from G3.** In a copy of the model with every Z₂-odd state at ``HEAVY`` GeV (the symmetric limit:
the W and Z masses, and the Higgs's couplings to the dark states, drop out), the elastic amplitudes (a, b) → (a′, b′)
at momentum transfer q ≪ p ≪ M give the Born potential: M = 16π M² α/q² + O(q⁰) (attractive α > 0; for two
fermions the engine's M carries the extra sign of their two lines' permutation, −1), so with two transfers the
coefficient of 1/q² is read off exactly. Spin-diagonal and spin-averaged, it is a matrix α_eff over (pair, colours).
Its eigenvectors are the irreducible channels, with the phases of the very amplitudes that annihilate; its
eigenvalues must be group theory's α[C₂(R₁) + C₂(R₂) − C₂(R)]/2 (SU(2), SU(3)) − αq₁q₂ (U(1)s), with G2's
couplings. Each cluster of eigenvalues is matched to a channel (I, R); a mismatch refuses the group.

**The hard rates, from G3.** At threshold (relative speed ``THRESHOLD_V``) the annihilation matrix
Γ_kl = Σ_f ∫ M_k M_l* k/(8π s^{3/2}) dcos θ (½ for identical final particles) over the same states, interference
between different charge and colour states included. A channel's s-wave rate is Tr(P Γ) over its states, and by
total spin S (σ/2 per leg: a fermion's label is its spin along z for u and v = C ūᵀ alike) for its bound states.
The rates are taken at the hard scale 2m: × (α(2m)/α_G2)² for the electroweak couplings (G2's are at M_Z), as the
library's engines take them; the strong coupling is already α_s(m).

**The Sommerfeld effect.** Each channel's s-wave rate is multiplied by its thermally averaged factor:
- SU(2): α₂ at the inverse Bohr radius α₂(M)M, Hulthén with the W mass below T_c and the Debye mass above
  (``portals.nplet``, MRSS);
- U(1)_Y: α_Y at the same scale, with SU(2)'s mediator mass where both act, else Coulomb;
- SU(3): α_s at the momentum transfer, not below the Bohr momentum (``portals.tchannel``);
- a new mediator: its own coupling and mass (Hulthén).
The correction to ⟨σ_eff v⟩ is Σ_ch (r²⟨S_ch⟩ − 1) σ_ch: the perturbative rate of every pair stays as G4 tabulates
it, and the group's s-wave part is replaced (``relic.omega_h2_species``'s thermal pairs).

**Bound states** (in ionisation equilibrium, 1s and 2s):
- a pure SU(2) multiplet with itself or its antiparticle, fermion or scalar: MRSS's capture by W (and B) emission
  (``portals.nplet``'s formulae, any spin), with the hard rates (I, S) from G3 above;
- a colour-triplet scalar with its antiparticle: Harz & Petraki's capture into the colour-singlet ground state
  (``sommerfeld.bound_state_rate``);
- otherwise not computed, which the flags say.

**Refused** (the D4 bracket then decides, as at G4): a group of mixed states, a group whose states are split by more
than ``DEGENERATE`` of their mass (outside the symmetric limit), a vector multiplet, a potential that group theory does
not reproduce, and an SU(2) n-plet with n > 5, whose bound states in channels I ≥ 7 are not computed
(``portals.nplet``).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace

import numpy as np

from adroit.constraints import long_range_bracket as lb
from adroit.constraints import tree
from adroit.parameter_space.portals import nplet

HEAVY = 1.0e6                     # GeV: the dark states' mass in the potential's copy of the model
P_FRACTION = 0.03                 # p/M of the elastic kinematics
Q_FRACTIONS = (0.002, 0.004)      # q/M of its two momentum transfers
THRESHOLD_V = 1.0e-3              # relative speed of the hard rates
FREEZE_V = 0.3                    # a relative speed at freeze-out (x ≈ 20–25)
PLATEAU = 2.0                     # the hard rate above this many times its rate at FREEZE_V: not the s-wave plateau
ANGLES = 16
PURE = 0.99                       # a state this much one field belongs to its multiplet
MATCH = 0.02                      # an eigenvalue within this fraction (or 10⁻⁴ absolute) of group theory's
MAX_N = 5                         # SU(2) multiplets beyond: bound states in I ≥ 7 not computed (``portals.nplet``)
DEGENERATE = 0.04                 # a group's states split by more than this fraction of their mass: not the symmetric
                                  # limit (the kinetic energy at freeze-out is about M/25; the inert doublet's 50%
                                  # splits, found by G7's held-out run, are far outside it)


@dataclass
class Multiplet:
    """A multiplet of the bath: the field, whether it is the antiparticle multiplet, and its states."""
    field: str
    anti: bool
    states: list[str]
    n: int
    colour: str
    y: float
    spin: float
    self_conjugate: bool
    mass: float


@dataclass
class Channel:
    """An irreducible channel of a group: SU(2) dimension, SU(3) representation, its states, its potential's parts
    (units of α₂, α_Y, α_s; dark (α, mass) pairs), and its s-wave rate at threshold (GeV⁻², summed over its states),
    in total and by spin."""
    su2: int
    su3: str
    dim: int
    lam: float
    y_term: float
    colour: float
    dark: list[tuple[float, float]]
    alpha_tree: float = 0.0
    rate: float = 0.0
    by_spin: dict[int, float] = field(default_factory=dict)


@dataclass
class Group:
    """Two multiplets joined by a long-range force, their channels, and the bath pair that carries their rate."""
    a: Multiplet
    b: Multiplet
    channels: list[Channel]
    pair: tuple[int, int]
    running: float                 # r² of the hard rates
    bound: str = ""                # "su2", "colour", "dark_u1" or "" (none computed)


@dataclass
class LongRange:
    """The bath's long-range analysis: the groups G7 computes, and why any other group is not."""
    groups: list[Group] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# --- multiplets and forces ----------------------------------------------------------------------------------

def multiplets(mb, bath) -> tuple[list[Multiplet], list[str]]:
    """The bath's multiplets, and the states that are not pure enough to belong to one."""
    from adroit.parameter_space.portals.generic_checks import _state, dominant_field
    found: dict[tuple[str, bool], Multiplet] = {}
    impure = []
    for name, mass, _ in bath:
        st = _state(mb, name)
        f = dominant_field(mb, st)
        share = _share(st, f.name)
        if share < PURE:
            impure.append(f"{name} ({100 * share:.3g}% {f.name})")
        anti = name.endswith("~") and not f.self_conjugate
        key = (f.name, anti)
        if key not in found:
            y = f.charges.hypercharge
            colour = f.charges.su3 if not anti else {"3": "3bar", "3bar": "3"}.get(f.charges.su3, f.charges.su3)
            found[key] = Multiplet(f.name, anti, [], f.charges.su2, colour, -y if anti else y, st.spin,
                                   f.self_conjugate, mass)
        found[key].states.append(name)
    return list(found.values()), impure


def _share(state, field_name: str) -> float:
    """The share of a state in one field: its composition is |amplitude|² by component (a Dirac state lists its
    left- and right-handed ones), so the field's components over all of them."""
    total = sum(state.composition.values())
    mine = sum(c for k, c in state.composition.items() if k.split("[")[0].split(".")[0] == field_name)
    return mine / total if total else 0.0


def tree_forces(rules) -> list[lb.GaugeForce]:
    """The forces at G2's couplings (for matching the potential): SU(2), U(1)_Y, SU(3), massless."""
    from adroit.model_building.gauge_basis import G1, G2
    return [lb.GaugeForce(group="SU2", alpha=G2 ** 2 / (4 * math.pi)),
            lb.GaugeForce(group="U1", name="Y", alpha=G1 ** 2 / (4 * math.pi)),
            lb.GaugeForce(group="SU3", alpha=rules.g_s ** 2 / (4 * math.pi))]


def _parts(a: Multiplet, b: Multiplet, i: int, r: str, dark: list[tuple[float, float, float]]) -> dict:
    """A channel's potential in parts: SU(2) (units of α₂), U(1)_Y (units of α_Y), SU(3) (units of α_s), dark."""
    lam = (lb.su2_casimir(a.n) + lb.su2_casimir(b.n) - lb.su2_casimir(i)) / 2 if a.n > 1 and b.n > 1 else 0.0
    colour = 0.0
    if (a.colour, b.colour) != ("1", "1"):
        colour = (lb.SU3_CASIMIR[a.colour] + lb.SU3_CASIMIR[b.colour] - lb.SU3_CASIMIR[r]) / 2
    return {"lam": lam, "y_term": -a.y * b.y, "colour": colour,
            "dark": [(-alpha * qa * qb, mass) for alpha, qa, qb, mass in dark]}


def predicted(a: Multiplet, b: Multiplet, forces: list[lb.GaugeForce], dark) -> list[Channel]:
    """Group theory's channels of a ⊗ b with G2's couplings (``tree_forces``)."""
    alpha = {f.group if f.group != "U1" else f.name: f.alpha for f in forces}
    out = []
    for i in lb.su2_product(a.n, b.n):
        for r in lb.su3_product(a.colour, b.colour):
            p = _parts(a, b, i, r, dark)
            out.append(Channel(i, r, i * lb.SU3_DIMENSION[r], p["lam"], p["y_term"], p["colour"], p["dark"]))
    for ch in out:
        ch.alpha_tree = alpha["SU2"] * ch.lam + alpha["Y"] * ch.y_term + alpha["SU3"] * ch.colour + \
            sum(x for x, _ in ch.dark)
    return out


def dark_charges(rules, a: Multiplet, b: Multiplet) -> list[tuple[float, float, float, float]]:
    """(α, q_a, q_b, mass) of each new mediator joining the two multiplets (``generic_checks``: a vector's
    antiparticle carries −q; a scalar attracts every pair)."""
    from adroit.parameter_space.portals import generic_checks as gc
    names = [a.states[0], b.states[0]]
    dark = gc._dark(rules, names)
    reps = [(0, "1", 0.0, 0.0), (0, "1", 0.0, 0.0)]
    charges = gc._pair_charges(reps, 0, 1, names, dark)
    return [(dark["forces"][k[5:]][0], qa, qb, dark["forces"][k[5:]][1])
            for k, (qa, qb) in charges.items() if k.startswith("dark:")]


# --- the two-particle states and their matrices ---------------------------------------------------------------

def heavy_copy(model) -> tree.Model:
    """The model with every Z₂-odd particle at ``HEAVY`` GeV and no particle with a width (the potential's
    symmetric limit; a width would give the exchanged boson's propagator an imaginary part)."""
    parity = getattr(model, "parity", {})
    parts = {k: replace(v, mass=HEAVY, width=0.0) if parity.get(k, 1) == -1 else replace(v, width=0.0)
             for k, v in model.particles.items()}
    out = tree.Model(parts, list(model.vertices))
    out.parity = parity
    return out


def blocks(model, a: Multiplet, b: Multiplet) -> list[list[tuple[str, str]]]:
    """The ordered pairs (a, b) of the group, in blocks of equal total charge."""
    found: dict[float, list[tuple[str, str]]] = {}
    for x in a.states:
        for y in b.states:
            q = round(model.particles[x].charge + model.particles[y].charge, 6)
            found.setdefault(q, []).append((x, y))
    return list(found.values())


def _process(model, legs) -> tree.Process | None:
    try:
        return tree.Process(model, *legs, points=ANGLES)
    except (ValueError, KeyError):
        return None


def potential(heavy, block: list[tuple[str, str]]) -> np.ndarray:
    """α_eff over (pair, colour a, colour b) of one block (module docstring): out-states as rows."""
    m = HEAVY
    p = P_FRACTION * m
    s = 4.0 * (m * m + p * p)
    cos = np.array([1.0 - 0.5 * (q / P_FRACTION) ** 2 for q in Q_FRACTIONS])
    q2 = np.array([(q * m) ** 2 for q in Q_FRACTIONS])
    tensors = {}
    for k, out in enumerate(block):
        for col, inc in enumerate(block):
            proc = _process(heavy, (*inc, *out))
            if proc is None:
                continue
            amp = proc.amplitudes(s, cos)                 # (c0, c1, c2, c3, s0, s1, s2, s3, 2)
            n0, n1 = amp.shape[4], amp.shape[5]
            diag = sum(amp[:, :, :, :, i, j, i, j, :] for i in range(n0) for j in range(n1)) / (n0 * n1)
            coefficient = (diag[..., 0] - diag[..., 1]) / (1.0 / q2[0] - 1.0 / q2[1])
            sign = -1.0 if all(heavy.particles[x].spin == 0.5 for x in inc) else 1.0       # Fermi statistics
            tensors[(k, col)] = sign * np.transpose(coefficient, (2, 3, 0, 1)) / (16.0 * math.pi * m * m)
    dims = next(iter(tensors.values())).shape[:2] if tensors else (1, 1)
    size = dims[0] * dims[1]
    out_m = np.zeros((len(block) * size, len(block) * size), dtype=complex)
    for (row, col), value in tensors.items():
        out_m[row * size:(row + 1) * size, col * size:(col + 1) * size] = value.reshape(size, size)
    return out_m


def annihilation(model, block: list[tuple[str, str]], finals, v: float = THRESHOLD_V) -> tuple[np.ndarray, int]:
    """Γ over (pair, colour a, colour b, spin a, spin b) at relative speed ``v`` (GeV⁻², σv per state), by default at
    threshold, and the number of spin states of the pair."""
    m = max(model.particles[x].mass + model.particles[y].mass for x, y in block) / 2.0
    s = 4.0 * m * m / (1.0 - (0.5 * v) ** 2)
    nodes, weights = np.polynomial.legendre.leggauss(ANGLES)
    gamma = None
    for c, d in finals:
        mc, md = model.particles[c].mass, model.particles[d].mass
        if math.sqrt(s) <= mc + md:
            continue
        k = math.sqrt((s - (mc + md) ** 2) * (s - (mc - md) ** 2)) / (2.0 * math.sqrt(s))
        norm = k / (8.0 * math.pi * s ** 1.5) * (0.5 if c == d else 1.0)
        amps = []
        for pair in block:
            proc = _process(model, (*pair, c, d))
            amps.append(None if proc is None else proc.amplitudes(s, nodes))
        shape = next((x.shape for x in amps if x is not None), None)
        if shape is None:
            continue
        flat = np.array([np.zeros(shape, complex) if x is None else x for x in amps])
        # (pair, c0, c1, c2, c3, s0, s1, s2, s3, angle) → rows (pair, c0, c1, s0, s1), columns (c2, c3, s2, s3, angle)
        rows = np.transpose(flat, (0, 1, 2, 5, 6, 3, 4, 7, 8, 9)).reshape(len(block) * np.prod(shape[0:2]) *
                                                                        np.prod(shape[4:6]), -1)
        w = np.tile(weights, rows.shape[1] // len(weights))
        contribution = norm * (rows * w) @ rows.conj().T
        gamma = contribution if gamma is None else gamma + contribution
        spins = int(shape[4] * shape[5])
    return gamma, (spins if gamma is not None else 1)


def spin_projectors(spin: float) -> dict[int, np.ndarray]:
    """P_S over the pair's spin labels (s_a, s_b): S = 0, 1 for two fermions (σ/2 per leg); S = 0 for scalars."""
    if spin == 0:
        return {0: np.eye(1)}
    sigma = [np.array([[0, 1], [1, 0]], complex), np.array([[0, -1j], [1j, 0]]), np.array([[1, 0], [0, -1]], complex)]
    one = np.eye(2)
    total = sum((np.kron(x, one) + np.kron(one, x)) @ (np.kron(x, one) + np.kron(one, x)) for x in sigma) / 4.0
    values, vectors = np.linalg.eigh(total)
    out = {}
    for s_tot in (0, 1):
        keep = vectors[:, np.isclose(values, s_tot * (s_tot + 1))]
        out[s_tot] = keep @ keep.conj().T
    return out


# --- channels ---------------------------------------------------------------------------------------------------

def decompose(v: np.ndarray, gamma: np.ndarray | None, spins: int, spin: float, candidates: list[Channel],
              scale: float) -> tuple[dict[int, tuple[int, float, dict[int, float]]], str]:
    """Each eigencluster of the potential matched to a candidate channel: {candidate index: (states, rate,
    rate by spin)}, or a reason the potential does not match group theory."""
    hermitian = 0.5 * (v + v.conj().T)
    if np.max(np.abs(v - hermitian), initial=0.0) > 1e-6 * max(np.max(np.abs(v), initial=0.0), 1e-12):
        return {}, "the potential matrix is not Hermitian"
    values, vectors = np.linalg.eigh(hermitian)
    projectors = spin_projectors(spin)
    found: dict[int, tuple[int, float, dict[int, float]]] = {}
    for value in np.unique(np.round(values, 10)):
        cols = vectors[:, np.abs(values - value) < 1e-8 + 1e-6 * abs(value)]
        best = min(range(len(candidates)), key=lambda k: abs(candidates[k].alpha_tree - value))
        if abs(candidates[best].alpha_tree - value) > MATCH * abs(candidates[best].alpha_tree) + 1e-4 * scale:
            return {}, f"an eigenvalue of the potential, {value:.4g}, matches no channel of group theory"
        p = cols @ cols.conj().T
        rate, by_spin = 0.0, {}
        if gamma is not None:
            rate = float(np.real(np.trace(np.kron(p, np.eye(spins)) @ gamma)))
            if spins == len(next(iter(projectors.values()))):
                by_spin = {s_tot: float(np.real(np.trace(np.kron(p, ps) @ gamma))) for s_tot, ps in projectors.items()}
        states, total, spin_rates = found.get(best, (0, 0.0, {}))
        found[best] = (states + cols.shape[1], total + rate,
                       {k: spin_rates.get(k, 0.0) + by_spin.get(k, 0.0) for k in set(spin_rates) | set(by_spin)})
    return found, ""


def _off_plateau(model, block: list[tuple[str, str]], finals, gamma) -> str:
    """Why the block's hard rate is not its s-wave plateau, or "": its total at threshold more than ``PLATEAU`` times
    its total at a freeze-out speed (``FREEZE_V``). That is an s-channel pole at the pair's threshold, whose peak the
    form "Sommerfeld factor × the rate at threshold" multiplies as if it were the thermal rate: with a mediator at
    2m_χ the correction exceeded the whole perturbative rate however small the coupling (the audit loop's AL3-01: the
    library's B − L spec at 100/200 GeV, Ωh² 0.0072 for 0.1198). The group is then refused, and the bracket decides
    whether Ωh² is computed without its correction (``GenericModel.domain``)."""
    if gamma is None:
        return ""
    at_threshold = float(np.real(np.trace(gamma)))
    freeze, _ = annihilation(model, block, finals, FREEZE_V)
    at_freeze = float(np.real(np.trace(freeze))) if freeze is not None else 0.0
    if at_threshold > PLATEAU * at_freeze:
        return (f"its rate at threshold (v = {THRESHOLD_V:g}) is {at_threshold / max(at_freeze, 1e-300):.3g} times its "
                f"rate at v = {FREEZE_V:g}: an s-channel pole at the pair's threshold, which its Sommerfeld factor is "
                "not computed against")
    return ""


def group_channels(model, heavy, rules, a: Multiplet, b: Multiplet) -> tuple[list[Channel], str]:
    """The group's channels with their rates (module docstring), or a reason it is not computed."""
    from adroit.parameter_space.portals.generic import final_states
    forces = tree_forces(rules)
    candidates = predicted(a, b, forces, dark_charges(rules, a, b))
    scale = max(f.alpha for f in forces)
    totals: dict[int, tuple[int, float, dict[int, float]]] = {}
    for block in blocks(model, a, b):
        finals = sorted({f for pair in block for f in final_states(model, *pair)})
        v = potential(heavy, block)
        gamma, spins = annihilation(model, block, finals)
        if why := _off_plateau(model, block, finals, gamma):
            return [], why
        found, why = decompose(v, gamma, spins, a.spin if a.spin == b.spin else 0.5, candidates, scale)
        if why:
            return [], why
        for k, (states, rate, by_spin) in found.items():
            s0, r0, b0 = totals.get(k, (0, 0.0, {}))
            totals[k] = (s0 + states, r0 + rate, {x: b0.get(x, 0.0) + by_spin.get(x, 0.0) for x in set(b0) | set(by_spin)})
    out = []
    for k, (states, rate, by_spin) in totals.items():
        out.append(replace(candidates[k], rate=rate, by_spin=by_spin, dim=states))
    return out, ""


# --- the analysis -------------------------------------------------------------------------------------------------

def _joined(a: Multiplet, b: Multiplet, dark) -> bool:
    """Whether a long-range force acts between the two multiplets."""
    su2 = a.n > 1 and b.n > 1
    colour = a.colour != "1" and b.colour != "1"
    return su2 or colour or (a.y != 0 and b.y != 0) or bool(dark)


def _running(a: Multiplet, b: Multiplet, m: float) -> float:
    """r²: the hard rates' couplings at 2m against G2's (module docstring)."""
    from adroit.model_building.gauge_basis import G1, G2
    from adroit.parameter_space.portals.multiplet import alpha_2, alpha_y
    if a.n > 1 or b.n > 1:
        return (alpha_2(2.0 * m) / (G2 ** 2 / (4 * math.pi))) ** 2
    if a.y and b.y and a.colour == "1":
        return (alpha_y(2.0 * m) / (G1 ** 2 / (4 * math.pi))) ** 2
    return 1.0


def _bound_kind(a: Multiplet, b: Multiplet, channels: list[Channel] | tuple = ()) -> str:
    """Which bound states G7 computes for the group (module docstring)."""
    same_field = a.field == b.field and (a.self_conjugate or a.anti != b.anti)
    if same_field and a.n > 1 and a.colour == "1" and a.spin in (0, 0.5):
        return "su2"
    if same_field and a.n == 1 and a.spin == 0 and {a.colour, b.colour} == {"3", "3bar"}:
        return "colour"
    if same_field and not a.self_conjugate and _dark_u1_alpha(a, channels) is not None:
        return "dark_u1"
    return ""


# --- bound states of a dark U(1) (2026-10-15) ---------------------------------------------------------------------
# A particle–antiparticle pair of an SM-singlet (spin 0 or ½) bound by a dark U(1) whose vector is effectively
# massless: hydrogen-like states, captured into the ground state by emitting the dark photon (an electric dipole
# transition; von Harling & Petraki, arXiv:1407.7874; Petraki, Postma & Wiechers, arXiv:1505.00109):
#     σ_BSF v_rel = (2⁹/3) π α²/m² · S_BSF(ζ),   S_BSF = [2πζ/(1 − e^{−2πζ})] ζ⁴ e^{−4ζ arccot ζ}/(1 + ζ²)²,   ζ = α/v_rel,
# which is 3.13 times the annihilation σv = πα²/m² · 2πζ/(1 − e^{−2πζ}) as ζ → ∞. E_B = mα²/4 (μ = m/2). A
# fermion pair forms para (¼, → 2γ′, Γ = mα⁵/2) and ortho (¾, → 3γ′, Γ = 2(π² − 9)mα⁶/9π) states, a scalar pair
# one (→ 2γ′, Γ = mα⁵/4); each in ionisation equilibrium with the dark photons at the bath's temperature
# (``sommerfeld.ionisation_equilibrium``). Excited states and transitions between levels are left out.

DARK_LIGHT = 0.01               # a dark vector lighter than this fraction of E_B counts as massless for capture


def _vector_force(rules, a: Multiplet, b: Multiplet) -> bool:
    """Whether every new mediator joining the pair is a vector (a dark U(1)'s photon), not a scalar."""
    from adroit.parameter_space.portals import generic_checks as gc
    forces = gc._dark(rules, [a.states[0], b.states[0]])["forces"]
    return bool(forces) and all(spin == 1 for _, _, spin in forces.values())


def _dark_u1_alpha(a: Multiplet, channels) -> float | None:
    """The dark U(1)'s α where a singlet particle–antiparticle pair is bound by it alone with an effectively
    massless vector, else None."""
    if a.n != 1 or a.colour != "1" or a.spin not in (0, 0.5) or len(channels) != 1:
        return None
    ch = channels[0]
    if ch.lam or ch.colour or abs(ch.y_term) > 1e-12 or len(ch.dark) != 1 or ch.dark[0][0] <= 0:
        return None
    alpha, m_v = ch.dark[0]
    return alpha if m_v <= DARK_LIGHT * a.mass * alpha ** 2 / 4.0 else None


def dark_u1_capture(v_rel: np.ndarray, m: float, alpha: float) -> np.ndarray:
    """σ_BSF v_rel (GeV⁻²) of a dark-U(1) pair of mass m each into its ground state (comment above)."""
    from adroit.constraints import sommerfeld
    zeta = alpha / np.maximum(np.asarray(v_rel, dtype=float), 1e-9)
    return 2.0 ** 9 / 3.0 * math.pi * alpha ** 2 / m ** 2 * sommerfeld.capture_shape(zeta, zeta)


def dark_u1_bound_rate(a: Multiplet, alpha: float, temperature: np.ndarray) -> np.ndarray:
    """The spin-averaged ⟨σ_BSF v⟩_eff(T) (GeV⁻²) of the pair, its bound states in ionisation equilibrium."""
    from adroit.constraints import sommerfeld
    m = a.mass
    states = ([(1.0, m * alpha ** 5 / 4.0)] if a.spin == 0 else
              [(0.25, m * alpha ** 5 / 2.0), (0.75, 2.0 * (math.pi ** 2 - 9.0) * m * alpha ** 6 / (9.0 * math.pi))])
    return sum(w * sommerfeld.ionisation_equilibrium(lambda v: dark_u1_capture(v, m, alpha), m, m * alpha ** 2 / 4.0,
                                                     gamma, 1.0, temperature) for w, gamma in states)


def analyse(mb, rules, model, bath) -> LongRange:
    """The bath's groups and their channels (module docstring)."""
    out = LongRange()
    mults, impure = multiplets(mb, bath)
    names = [x[0] for x in bath]
    heavy = heavy_copy(model)
    for i, a in enumerate(mults):
        for b in mults[i:]:
            dark = dark_charges(rules, a, b)
            if not _joined(a, b, dark):
                continue
            label = f"{a.field}{'~' if a.anti else ''} {b.field}{'~' if b.anti else ''}"
            bad = [s for s in impure if s.split(" ")[0] in a.states + b.states]
            if bad:
                out.refused.append(f"{label}: mixed states ({', '.join(bad)})")
                continue
            if a.spin == 1 or b.spin == 1:
                out.refused.append(f"{label}: vector multiplets are not decomposed")
                continue
            masses = [model.particles[s].mass for s in a.states + b.states]
            if max(masses) - min(masses) > DEGENERATE * min(masses):
                out.refused.append(f"{label}: its states are split by {100 * (max(masses) / min(masses) - 1):.3g}%, "
                                   "outside the symmetric limit")
                continue
            if max(a.n, b.n) > MAX_N:
                out.refused.append(f"{label}: an SU(2) {max(a.n, b.n)}-plet's bound states in channels I ≥ 7 are not "
                                   "computed")
                continue
            channels, why = group_channels(model, heavy, rules, a, b)
            if why:
                out.refused.append(f"{label}: {why}")
                continue
            if not any(ch.rate > 0 for ch in channels):          # e.g. χχ of a complex field: nothing to enhance
                continue
            pair = (names.index(a.states[0]), names.index(b.states[0]))
            kind = _bound_kind(a, b, channels)
            if kind == "dark_u1" and not _vector_force(rules, a, b):
                kind = ""                     # a scalar's Yukawa force: no dipole capture (the audit's G7-4, G12)
            out.groups.append(Group(a, b, channels, tuple(sorted(pair)), _running(a, b, max(a.mass, b.mass)), kind))
    return out


# --- the Sommerfeld effect ------------------------------------------------------------------------------------------

def hulthen(alpha: np.ndarray, v: np.ndarray, m: float, m_v: float) -> np.ndarray:
    """``nplet.hulthen`` with α varying along v (the strong coupling runs with the momentum transfer); Coulomb
    where m_V = 0 or the range is long."""
    alpha, v = np.broadcast_arrays(np.asarray(alpha, float), np.asarray(v, float))
    x = 2.0 * math.pi * alpha / v
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        coulomb = np.where(np.abs(x) < 1e-8, 1.0 + 0.5 * x, x / -np.expm1(-np.clip(x, -700.0, 700.0)))
    if m_v <= 0.0:
        return np.maximum(np.nan_to_num(coulomb, nan=1.0), 0.0)
    a = math.pi * m * v / (nplet.KAPPA * m_v)
    near = (a <= 40.0) & (alpha != 0.0)
    out = np.array(coulomb, dtype=float)
    if near.any():
        an, vn, al = a[near], v[near], alpha[near]
        root = np.sqrt((1.0 - 4.0 * al * nplet.KAPPA * m_v / (m * vn ** 2)).astype(complex))
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            out[near] = 2.0 * math.pi * al * np.sinh(an) / (vn * (np.cosh(an) - np.cosh(an * root).real))
    return np.maximum(np.nan_to_num(out, nan=1.0, posinf=1e300), 0.0)


def channel_alpha(ch: Channel, m: float, v: np.ndarray) -> np.ndarray:
    """The channel's α_eff at relative speed v (module docstring's scales)."""
    from adroit.parameter_space.portals.multiplet import alpha_2, alpha_y
    from adroit.parameter_space.portals.tchannel import TChannel
    q = nplet.potential_scale(m)
    out = alpha_2(q) * ch.lam + alpha_y(q) * ch.y_term + sum(a for a, _ in ch.dark) + np.zeros_like(v)
    if ch.colour:
        out = out + ch.colour * np.array([TChannel.alpha_potential(m, 0.5 * x) for x in v])
    return out


def mediator_mass(ch: Channel, m: float, t: float, debye: bool = True) -> float:
    """The channel's one mediator mass for the Hulthén form: each part's mass weighted by its |α| — SU(2)'s and
    hypercharge's the W's (or Debye) where SU(2) acts, the dark mediators' their own, the gluon's 0 (at the typical
    speed √(4t/m)). The audit's G7-8 (G12): the W mass had screened the gluon's part too, so a coloured doublet's
    colour-singlet ⟨S⟩ came out 4–30% low at x = 25–1000 against the exact solution."""
    from adroit.parameter_space.portals.multiplet import alpha_2, alpha_y
    from adroit.parameter_space.portals.tchannel import TChannel
    q = nplet.potential_scale(m)
    parts = [(abs(alpha_2(q) * ch.lam + alpha_y(q) * ch.y_term),
              nplet.vector_mass(t, q, debye) if ch.lam else 0.0)] + [(abs(a), mass) for a, mass in ch.dark]
    if ch.colour:
        parts.append((abs(ch.colour * TChannel.alpha_potential(m, 0.5 * min(math.sqrt(4.0 * t / m), 1.0))), 0.0))
    weight = sum(a for a, _ in parts)
    return sum(a * mass for a, mass in parts) / weight if weight else 0.0


def thermal_factor(ch: Channel, m: float, t: float) -> float:
    """⟨S⟩ of the channel at temperature t (the Maxwell–Boltzmann average of ``portals.nplet``)."""
    v = np.minimum(np.sqrt(4.0 * t * nplet._Y_GRID / m), 1.0)
    return float(np.trapezoid(nplet._WEIGHT * hulthen(channel_alpha(ch, m, v), v, m, mediator_mass(ch, m, t)),
                              nplet._Y_GRID))


# --- bound states --------------------------------------------------------------------------------------------------

def degrees(mult: Multiplet, bath_dof: dict[str, float]) -> float:
    """The internal states of one multiplet."""
    return sum(bath_dof[s] for s in mult.states)


def su2_states(group: Group, rates: dict[tuple[int, int], float], g: float) -> list[dict]:
    """``nplet._bound_states`` for any spin: 1s and 2s of every attractive (I, S) the pair can form in s-wave,
    with its sources (W from I ± 2, and B for a complex pair), and its rate from G3 (averaged over g²)."""
    a = group.a
    n, y, real = a.n, abs(a.y), a.self_conjugate
    q = nplet.potential_scale(a.mass)
    from adroit.parameter_space.portals.multiplet import alpha_2, alpha_y
    a2, ay = alpha_2(q), alpha_y(q)
    spins = (0,) if a.spin == 0 else (0, 1)
    out = []
    for i_f in range(1, 2 * n, 2):
        for spin in spins:
            if real and (spin + (i_f - 1) // 2) % 2:
                continue
            a_f = nplet.strength(n, y, i_f, q)
            if a_f <= 0:
                continue
            sources = [(i_i, a2, *nplet.group_terms(n, i_i, i_f), a2 / a_f) for i_i in (i_f - 2, i_f + 2)
                       if 1 <= i_i < 2 * n]
            if not real:
                sources.append((i_f, ay, i_f * y * y, 0.0, 0.0, 0.0))
            for level in (1, 2):
                out.append({"I": i_f, "S": spin, "n_B": level, "alpha_f": a_f, "sources": sources,
                            "rate": rates.get((i_f, spin), 0.0), "g": g})
    return out


def su2_bound_rate(group: Group, rates: dict[tuple[int, int], float], g: float, temperature: np.ndarray) -> np.ndarray:
    """Σ over the bound states of ⟨σ_BSF v⟩ R(T), averaged over g² (``nplet._state_rate``, ionisation on)."""
    a = group.a
    out = np.zeros_like(temperature)
    for state in su2_states(group, rates, g):
        out = out + nplet._state_rate(state, a.n, abs(a.y), a.mass, temperature, True)
    return out


# --- the rate the relic density reads ----------------------------------------------------------------------------

def thermal_rates(lr: LongRange, bath, bound_states: bool = True) -> dict[tuple[int, int], object]:
    """For each group's bath pair, ⟨σv⟩(T) to add to ⟨σ_eff v⟩ with that pair's weight (``relic.omega_h2_species``):
    Σ_ch (r²⟨S_ch⟩ − 1) σ_ch and the bound states, normalised to the pair."""
    dof = {name: d for name, _, d in bath}
    out: dict[tuple[int, int], list] = {}
    for grp in lr.groups:
        i0, j0 = grp.pair
        norm = (1.0 if i0 == j0 else 2.0) * dof[bath[i0][0]] * dof[bath[j0][0]]
        mult = 1.0 if (grp.a.field, grp.a.anti) == (grp.b.field, grp.b.anti) else 2.0
        g = degrees(grp.a, dof) + (0.0 if mult == 1.0 else degrees(grp.b, dof))
        rates = {(ch.su2, s): mult * grp.running * r / g ** 2 for ch in grp.channels for s, r in ch.by_spin.items()}
        rate, share = _group_rate(grp, norm, mult, g, rates, bound_states), boltzmann_share(grp, bath)
        out.setdefault((i0, j0), []).append(lambda t, rate=rate, share=share: share(t) * rate(t))
    return {k: (lambda t, fs=fs: sum(f(t) for f in fs)) for k, fs in out.items()}


def boltzmann_share(grp: Group, bath) -> Callable[[np.ndarray], np.ndarray]:
    """F(T) = ⟨ρ̂⟩_a⟨ρ̂⟩_b / (ρ̂_a₀ρ̂_b₀): the group's correction, computed in the symmetric limit and so shared evenly
    by its internal states, enters with each state's own equilibrium density ρ̂ = m²K₂(m/T)e^{−m/T} (⟨⟩ weighted by
    the states' degrees of freedom), not only with the carrying pair's (a₀, b₀). The audit's G7-10 (G12): a component
    heavier by δ had been weighted by e^{∓δx}. 1 for a degenerate group."""
    from scipy.special import kve
    entry = {name: (mass, dof) for name, mass, dof in bath}
    floor = min(entry[s][0] for s in grp.a.states + grp.b.states)

    def density(name: str, t: np.ndarray) -> np.ndarray:
        mass = entry[name][0]
        return mass ** 2 * kve(2, mass / t) * np.exp(-(mass - floor) / t)

    def mean(states: list[str], t: np.ndarray) -> np.ndarray:
        return sum(entry[s][1] * density(s, t) for s in states) / sum(entry[s][1] for s in states)

    def share(t):
        t = np.atleast_1d(np.asarray(t, dtype=float))
        return mean(grp.a.states, t) * mean(grp.b.states, t) / (density(grp.a.states[0], t)
                                                                 * density(grp.b.states[0], t))
    return share


def _group_rate(grp: Group, norm: float, mult: float, g: float, rates: dict, bound_states: bool):
    """⟨σv⟩(T) of the group's Sommerfeld correction and bound states, normalised to its carrying pair."""
    m = max(grp.a.mass, grp.b.mass)

    def rate(temperature):
        temperature = np.atleast_1d(np.asarray(temperature, dtype=float))
        total = np.array([sum((grp.running * thermal_factor(ch, m, t) - 1.0) * ch.rate for ch in grp.channels)
                          for t in temperature]) * mult / norm
        if bound_states and grp.bound == "su2":
            total = total + g ** 2 * su2_bound_rate(grp, rates, g, temperature) / norm
        elif bound_states and grp.bound == "colour":
            from adroit.constraints import sommerfeld
            total = total + sommerfeld.bound_state_rate(m, temperature) * 2.0 * 9.0 / norm
        elif bound_states and grp.bound == "dark_u1":                 # spin-averaged, so × the pair's spin states
            spins = 2.0 if grp.a.spin == 0.5 else 1.0
            alpha = _dark_u1_alpha(grp.a, grp.channels)
            total = total + dark_u1_bound_rate(grp.a, alpha, temperature) * 2.0 * spins ** 2 / norm
        return total
    return rate
