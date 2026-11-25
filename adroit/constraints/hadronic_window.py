"""Where ADROIT does not compute a hadronic rate (the owner's decision, 2026-10-20).

Below a few GeV quarks and gluons appear only as hadrons, and a free-quark (partonic) rate there does not establish the
physical one. The guard is on the energy entering the calculation: an annihilation's invariant energy √s, taken at its
threshold 2m_χ (the threshold approximation: a thermal average also samples √s above it), and a decaying state's mass.
Between the lightest hadronic threshold (``opening``) and the window's top, a hadronic rate is not computed, unless a
class has a validated hadronic treatment of its own (the library's dark photon: the measured R ratio, kept):

- a **pure vector current** (``vector``: every state carrying the dark matter's annihilation couples vectorially to the
  quarks, with no axial or spin-0 part at all (a mixed current is not vector: the recheck's RC21-02); a decaying state
  couples vectorially with its axial part below ``VECTOR_PURITY``): free quarks above ``VECTOR_TOP`` = 2 GeV,
  where parton–hadron duality holds for vector currents (it is "roughly valid above 1 GeV for vector currents",
  arXiv:1811.03474 p. 2);
- **any other current, or one not classified** (scalar, pseudoscalar, axial, mixed, a t-channel exchange, a contact
  operator): free quarks only above ``TOP`` = 3 GeV, the top inclusive. This is ADROIT's conservative policy, not a
  threshold the literature proves. For a pseudoscalar, Aloni, Soreq & Williams (arXiv:1811.03474, p. 2) find the
  one-loop correction to the partonic rate as large as the leading one at m_a ≈ 2 GeV ("the smallest mass where Eq.
  (4) has O(1) validity"), "O(1) uncertainties" for 0.5 ≲ m_a ≲ 2 GeV, and treat the hadronic rates
  non-perturbatively up to 3 GeV (mixing with the η_c near 3 GeV left aside, their footnote 1); the policy extends
  that caution to scalars and to every current not shown to be vector.

Below ``opening`` no two- or three-pion state exists and the quark and gluon channels are closed (zero): 2m_π for a
CP-even or vector current, 3m_π for a CP-odd one (a → ππ is forbidden by CP and a → π⁰γ by C, arXiv:1811.03474 p. 1).
The one hadronic state below 2m_π, the radiative π⁰γ (from m_π⁰, through a vector current), is left out, a declared
approximation: for a photon-like current DarkCast's model puts it at most 6 × 10⁻⁶ of e⁺e⁻ below 0.30 GeV (the
recheck of 2026-10-22; the measured R ratio, from 0.30 GeV, does not include it below); for another current it is not
bounded here.
An annihilation within ``MARGIN`` below the opening is in the window too (its thermal tail opens it), as the generic
route had it. A purely leptonic or photonic channel is computed as before, and a quantity that depends on an
uncomputed hadronic rate is decided only where it does not depend on it, never with the rate set to zero.
"""
from __future__ import annotations

M_PION = 0.13957             # GeV, π±
VECTOR_TOP = 2.0             # GeV: a pure vector current's free quarks from here (exclusive)
TOP = 3.0                    # GeV: any other current's free quarks only above it (ADROIT's policy)
VECTOR_PURITY = 1e-3         # |axial/vector| of a decaying state's quark coupling below which its current counts as
                             # vector (rate: 10⁻⁶); an annihilation's current is vector only without any other part
MARGIN = 0.9                 # an annihilation from 0.9 × the opening is in the window (its thermal tail)
WIDTH_AGREEMENT = 1e-3       # a mediator's unknown hadronic width may move a propagator by at most this

CLOSED, UNKNOWN, PARTONIC = "closed", "unknown", "partonic"


class HadronicUnknown(ValueError):
    """A rate or width asked for inside the hadronic window, where it is not computed (the message says why)."""


def opening(cp_odd: bool) -> float:
    """The lightest hadronic final state's threshold (GeV): 3m_π for a CP-odd current, 2m_π otherwise."""
    return (3.0 if cp_odd else 2.0) * M_PION


def top(vector: bool) -> float:
    """The window's top (GeV): 2 GeV for a pure vector current, 3 GeV for any other."""
    return VECTOR_TOP if vector else TOP


def state(energy: float, vector: bool = False, cp_odd: bool = False, annihilation: bool = False) -> str:
    """``CLOSED`` (no hadron at this energy), ``UNKNOWN`` (in the window: not computed) or ``PARTONIC`` (free quarks
    and gluons) for a hadronic rate at ``energy`` (GeV): √s ≈ 2m_χ for an annihilation (``annihilation``: the
    ``MARGIN`` applies), a decaying state's mass for a decay."""
    low = opening(cp_odd) * (MARGIN if annihilation else 1.0)
    if energy < low:
        return CLOSED
    return UNKNOWN if energy <= top(vector) else PARTONIC


def describe(vector: bool, cp_odd: bool) -> str:
    """The window, for a reason: its current and its edges."""
    current = "a vector current" if vector else ("a CP-odd current" if cp_odd else "a current not shown to be vector")
    return (f"{opening(cp_odd):.3g} GeV ≤ E ≤ {top(vector):g} GeV for {current} (ADROIT's hadronic-validity policy: a "
            "free-quark rate there does not establish the hadronic one)")


def annihilation_reason(root_s: float, vector: bool, cp_odd: bool) -> str:
    """Why an annihilation's hadronic rate is not computed at √s ≈ 2m_χ = ``root_s``."""
    return (f"the annihilation into hadrons at √s ≈ 2m_χ = {root_s:.4g} GeV (the threshold approximation) is in the "
            f"hadronic window, {describe(vector, cp_odd)}; not computed")


def decay_reason(name: str, mass: float, vector: bool, cp_odd: bool) -> str:
    """Why a state's hadronic width is not computed at its mass."""
    return (f"{name}'s hadronic width at m = {mass:.4g} GeV is in the hadronic window, {describe(vector, cp_odd)}; not "
            f"computed, bounded by 0 ≤ Γ_had ≤ m (beyond it {name} is not a resonance the calculation describes)")


def propagator_insensitive(s_min: float, mass: float, width_high: float, fixed: bool = False) -> bool:
    """Whether a propagator 1/((s − m²)² + m²Γ²) moves by at most ``WIDTH_AGREEMENT`` for every Γ up to
    ``width_high``: m²Γ²/(s − m²)² ≤ ``WIDTH_AGREEMENT``, at every s ≥ ``s_min`` (a thermal average: s_min must lie
    above m², else the resonance is reached), or at s = ``s_min`` alone (``fixed``: annihilation today)."""
    gap = abs(s_min - mass * mass) if fixed else s_min - mass * mass
    return gap > 0 and (mass * width_high) ** 2 <= WIDTH_AGREEMENT * gap * gap
