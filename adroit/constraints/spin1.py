"""The spin-1 s-channel simplified models of the LHC Dark Matter Working Group (DM7).

A Dirac fermion χ and a mediator Z′ of mass M coupling to χ, to every quark
with one coupling g_q, and to every charged lepton with one coupling g_ℓ
(arXiv:1703.05703, eqs. 2.1–2.3):

    vector:        −Z′_μ [g_DM χ̄γ^μχ + g_q Σ q̄γ^μq + g_ℓ Σ ℓ̄γ^μℓ + g_ν Σ ν̄γ^μ P_L ν]
    axial-vector:  −Z′_μ [g_DM χ̄γ^μγ⁵χ + g_q Σ q̄γ^μγ⁵q + g_ℓ Σ ℓ̄γ^μγ⁵ℓ + g_ν Σ ν̄γ^μ P_L ν]

Gauge invariance ties the left-handed neutrinos to the charged leptons:
g_ν = g_ℓ (vector), g_ν = −g_ℓ (axial-vector). These are the "relativistic
completions" that the tier-3 constraints need: with them the mediator's
decays and the dark matter's annihilation are fixed.

Below the mediator mass the models reduce to the library's mediator cards
(``M_vector``, ``M_axial``), with nucleon couplings from the quark couplings:
g_V^N = 3 g_q (valence quarks), g_A^N = g_q (Δu + Δd + Δs).
"""

from __future__ import annotations

import math
from enum import Enum

from pydantic import Field,model_validator

from adroit.core.dm_state import DarkMatterParticle, InteractionModel
from adroit.core.state import StrictModel
from adroit.library.interactions import registry
from adroit.physics import conventions
from adroit.core.kinematics import KINEMATIC_MASSES
from adroit.core.model_contracts import VECTOR_FLAVOURS


class Spin1Kind(str, Enum):
    """The Lorentz structure of every coupling."""

    vector = "vector"
    axial = "axial"


class Fermion(StrictModel):
    """A Standard Model fermion the mediator couples to."""

    name: str
    mass_gev: float = Field(ge=0.0)
    colours: int = 1
    family: str                     # "quark", "charged_lepton" or "neutrino"


# The kinematic masses (``kinematics.KINEMATIC_MASSES``, shared with the generic route): u, d, s, c and b the DMsimp
# card's MASS-block inputs (MC 1.27, numerically m̄_c(m̄_c), not a pole mass; MB 4.7), t 172.5, τ, μ, e their pole
# masses; neutrinos massless.
FERMIONS = (
    [Fermion(name=q, mass_gev=KINEMATIC_MASSES[q], colours=3, family="quark") for q in ("u", "d", "s", "c", "b", "t")]
    + [Fermion(name=lep, mass_gev=KINEMATIC_MASSES[lep], family="charged_lepton") for lep in ("e", "mu", "tau")]
    + [Fermion(name=f"nu_{lepton}", mass_gev=0.0, family="neutrino") for lepton in ("e", "mu", "tau")])


class NucleonInputs(StrictModel):
    """The quark spin fractions of the proton, which set g_A^N."""

    delta_u: float
    delta_d: float
    delta_s: float
    source: str


# The values the Working Group recommends for these comparisons (arXiv:1603.04156, eq. 5.4).
DMWG_2016 = NucleonInputs(delta_u=0.84, delta_d=-0.43, delta_s=-0.09,
                          source="arXiv:1603.04156 (LHC DM WG)")


class Spin1Model(StrictModel):
    """One spin-1 simplified model: the mediator's mass and every coupling."""

    kind: Spin1Kind
    m_med_gev: float = Field(gt=0.0)
    g_dm: float
    g_q: float
    g_l: float = 0.0
    label: str = ""
    flavour_couplings: dict[str,float] | None = None
    fermion_masses_gev: dict[str,float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _flavour_contract(self) -> Spin1Model:
        if self.flavour_couplings is not None:
            if self.g_q or self.g_l or not math.isfinite(self.g_dm) or not math.isfinite(self.m_med_gev):
                raise ValueError("explicit flavours require unused universal slots zero and finite physical inputs")
            if self.kind is not Spin1Kind.vector or set(self.flavour_couplings)!=set(VECTOR_FLAVOURS):
                raise ValueError("flavour model needs all nine vector quark/charged-lepton couplings")
            if any(not math.isfinite(g) for g in self.flavour_couplings.values()):
                raise ValueError("finite flavour couplings required")
        if not set(self.fermion_masses_gev)<=set(VECTOR_FLAVOURS) or any(
                not math.isfinite(m) or m<0 for m in self.fermion_masses_gev.values()):
            raise ValueError("declared fermion masses must be finite nonnegative named flavour masses")
        return self

    def fermions(self) -> list[Fermion]:
        """Use each explicitly declared flavour mass; retain the old pole convention otherwise."""
        return [f.model_copy(update={"mass_gev":self.fermion_masses_gev[f.name]})
                if f.name in self.fermion_masses_gev else f for f in FERMIONS]

    def spectrum_reference_reason(self) -> str:
        """Refuse fixed-SM shower/source templates for explicitly different fermion masses."""
        changed=[name for name,mass in self.fermion_masses_gev.items()
                 if mass != next(f.mass_gev for f in FERMIONS if f.name == name)]
        return ("nonreference SM fermion masses ("+", ".join(sorted(changed))+
                "): shower/deposition/source templates require a mass-specific recast") if changed else ""

    @property
    def g_nu(self) -> float:
        """The left-handed neutrino coupling that gauge invariance requires."""
        if self.flavour_couplings is not None:
            return 0.0
        return self.g_l if self.kind is Spin1Kind.vector else -self.g_l

    def dm_couplings(self) -> tuple[float, float]:
        """(a, b) of χ in −Z′_μ χ̄γ^μ(a + bγ⁵)χ."""
        return (self.g_dm, 0.0) if self.kind is Spin1Kind.vector else (0.0, self.g_dm)

    def couplings(self, fermion: Fermion) -> tuple[float, float]:
        """(a, b) of a Standard Model fermion."""
        if self.flavour_couplings is not None:
            return self.flavour_couplings.get(fermion.name,0.0),0.0
        if fermion.family == "neutrino":
            return 0.5 * self.g_nu, -0.5 * self.g_nu
        g = self.g_q if fermion.family == "quark" else self.g_l
        return (g, 0.0) if self.kind is Spin1Kind.vector else (0.0, g)


# The Working Group's four benchmarks (arXiv:1703.05703, section 2.3.1); g_DM = 1.
BENCHMARKS = {
    "V1": (Spin1Kind.vector, 0.25, 0.0),
    "A1": (Spin1Kind.axial, 0.25, 0.0),
    "V2": (Spin1Kind.vector, 0.1, 0.01),
    "A2": (Spin1Kind.axial, 0.1, 0.1),
}


def benchmark(name: str, m_med_gev: float) -> Spin1Model:
    """A Working Group benchmark at the given mediator mass."""
    kind, g_q, g_l = BENCHMARKS[name]
    return Spin1Model(kind=kind, m_med_gev=m_med_gev, g_dm=1.0, g_q=g_q, g_l=g_l, label=name)


def partial_width(m_med: float, mass: float, colours: int, a: float, b: float) -> float:
    """Γ(Z′ → f f̄) = N_c M β [a²(1 + 2z) + b²β²] / (12π), z = m²/M², β = √(1 − 4z).

    It reproduces arXiv:1703.05703, eqs. 2.4–2.11, for every channel.
    """
    z = (mass / m_med) ** 2
    if z >= 0.25:
        return 0.0
    beta = math.sqrt(1.0 - 4.0 * z)
    return colours * m_med * beta * (a * a * (1.0 + 2.0 * z) + b * b * beta * beta) / (12.0 * math.pi)


def width(model: Spin1Model, m_dm_gev: float) -> float:
    """The mediator's total width: dark matter, quarks, charged leptons and neutrinos. The quark pairs are closed
    below the hadronic opening, 2m_π (``hadronic_window.opening``: no hadronic final state there)."""
    from adroit.constraints import hadronic_window as hw
    hadrons = model.m_med_gev >= hw.opening(False)
    total = partial_width(model.m_med_gev, m_dm_gev, 1, *model.dm_couplings())
    for f in model.fermions():
        if f.family == "quark" and not hadrons:
            continue
        total += partial_width(model.m_med_gev, f.mass_gev, f.colours, *model.couplings(f))
    return total


# --- the hadronic window (the owner's decision, 2026-10-20; ``hadronic_window``) --------------------------------
# Read from the model's own couplings (the named flavour currents included), never from a scan's g_q slot (C21-01).

def quark_current(model: Spin1Model) -> bool:
    """Whether the mediator couples to any quark."""
    return any(a or b for f in model.fermions() if f.family == "quark" for a, b in [model.couplings(f)])


def annihilation_window(model: Spin1Model, m_dm_gev: float) -> str:
    """Why the annihilation into quarks at √s ≈ 2m_χ is not computed (in the hadronic window: to 2 GeV for the vector
    mediator's pure vector current, to 3 GeV for the axial one), or ""."""
    from adroit.constraints import hadronic_window as hw
    vector = model.kind is Spin1Kind.vector
    if not quark_current(model) or hw.state(2 * m_dm_gev, vector=vector, annihilation=True) != hw.UNKNOWN:
        return ""
    return hw.annihilation_reason(2 * m_dm_gev, vector, False)


def propagator_window(model: Spin1Model, m_dm_gev: float, fixed: bool) -> str:
    """Why the mediator's uncomputed hadronic width (its mass in the window, 0 ≤ Γ_had ≤ m) moves the s-channel
    propagator at √s ≥ 2m_χ (at s = 4m_χ² alone, ``fixed``: today), or ""."""
    from adroit.constraints import hadronic_window as hw
    vector = model.kind is Spin1Kind.vector
    m = model.m_med_gev
    if not quark_current(model) or hw.state(m, vector=vector) != hw.UNKNOWN:
        return ""
    if hw.propagator_insensitive(4 * m_dm_gev ** 2, m, width(model, m_dm_gev) + m, fixed=fixed):
        return ""
    return f"{hw.decay_reason('the mediator', m, vector, False)}, and it moves the s-channel propagator"


def card_values(model: Spin1Model, inputs: NucleonInputs = DMWG_2016) -> tuple[str, dict[str, float]]:
    """The library card this model reduces to at low momentum transfer, with its values."""
    common = {"g_chi": model.g_dm, "m_med": model.m_med_gev}
    if model.kind is Spin1Kind.vector:
        if model.flavour_couplings is not None:
            gu,gd=model.flavour_couplings["u"],model.flavour_couplings["d"]
            return "M_vector", {**common,"gV_p":2*gu+gd,"gV_n":gu+2*gd}
        g_v = 3.0 * model.g_q
        return "M_vector", {**common, "gV_p": g_v, "gV_n": g_v}
    g_a = model.g_q * (inputs.delta_u + inputs.delta_d + inputs.delta_s)
    return "M_axial", {**common, "gA_p": g_a, "gA_n": g_a}


def interaction(model: Spin1Model, m_dm_gev: float,
                inputs: NucleonInputs = DMWG_2016) -> InteractionModel:
    """The model as an interaction for the rate code, through its library card."""
    card_id, values = card_values(model, inputs)
    return registry.resolve(card_id, DarkMatterParticle(mass_gev=m_dm_gev), values,
                            name=f"{model.label or model.kind.value} (m_med = {model.m_med_gev:g} GeV)")


def nucleon_couplings(model: Spin1Model, m_dm_gev: float, inputs: NucleonInputs = DMWG_2016
                      ) -> tuple[int, float, float]:
    """(operator, c_p, c_n) at q → 0: O₁ for a vector mediator, O₄ for an axial one."""
    resolved = interaction(model, m_dm_gev, inputs)
    operator = 1 if model.kind is Spin1Kind.vector else 4
    terms = [t for t in resolved.coefficients if t.operator == operator and t.q_power == 0]
    return operator, sum(t.proton for t in terms), sum(t.neutron for t in terms)


def nucleon_cross_section_cm2(model: Spin1Model, m_dm_gev: float,
                              inputs: NucleonInputs = DMWG_2016) -> float:
    """σ_SI (vector) or σ_SD on the proton (axial), from the library card at q → 0."""
    resolved = interaction(model, m_dm_gev, inputs)
    operator = 1 if model.kind is Spin1Kind.vector else 4
    c = sum(term.proton for term in resolved.coefficients
            if term.operator == operator and term.q_power == 0)
    if operator == 1:
        return conventions.sigma_si_cm2(c, m_dm_gev)
    return conventions.sigma_sd_cm2(c, m_dm_gev)


def working_group_cross_section_cm2(model: Spin1Model, m_dm_gev: float,
                                    inputs: NucleonInputs = DMWG_2016) -> float:
    """The Working Group's formula (arXiv:1603.04156, eqs. 5.1–5.3), used for comparisons.

    σ_SI = f² g_DM² μ²/(π M⁴) with f = 3 g_q; σ_SD = 3 f² g_DM² μ²/(π M⁴) with
    f = g_q (Δu + Δd + Δs); μ is the dark matter–nucleon reduced mass.
    """
    mu = conventions.reduced_mass(m_dm_gev, conventions.M_NUCLEON_GEV)
    if model.kind is Spin1Kind.vector:
        f, spin = (2*model.flavour_couplings["u"]+model.flavour_couplings["d"]
                   if model.flavour_couplings is not None else 3.0*model.g_q),1.0
    else:
        f, spin = model.g_q * (inputs.delta_u + inputs.delta_d + inputs.delta_s), 3.0
    sigma = spin * f ** 2 * model.g_dm ** 2 * mu ** 2 / (math.pi * model.m_med_gev ** 4)
    return sigma * conventions.HBARC_GEV_CM ** 2
