"""Model classes whose whole picture ADROIT can compute at any parameter point (DM13).

A class turns a parameter point (masses and couplings) into:
- the relic density Ωh² (thermal freeze-out, the working assumption);
- the direct-detection cross-section of the kind its interaction reduces to;
- ⟨σv⟩ today by final state (for gamma rays and the Sun);
- the interaction for the rate code (capture in the Sun);
- and, for a spin-1 class, the completion DM7's collider records judge.

**Spin-1 mediator** (DM7's ``spin1``): Dirac dark matter, a vector or axial
mediator with couplings g_χ, g_q (every quark) and g_ℓ. Everything is
computed: the relic density with the exact thermal average across the
resonance and the mediator-pair channel.

**Scalar mediator**: Dirac dark matter coupling as S χ̄(y_s + i y_p γ⁵)χ, and a
mediator coupling to Standard Model fermions in proportion to their masses,
g (m_f/v) S f̄ (1 or iγ⁵) f. Annihilation into fermion pairs through the
s-channel scalar is computed exactly:

    σ(s) = N_c s (y_s² β_χ² + y_p²)(g_s,f² β_f² + g_p,f²) β_f / (16π β_χ |s − M² + iMΓ|²),

with Γ from its fermion and dark matter channels, and annihilation into two
mediators, χχ̄ → SS, from the explicit amplitude (t- and u-channel χ exchange; the
mediator's self-coupling S³ is taken as zero). Left out (and stated): S → gg
through the top loop. Direct
detection: scalar–scalar gives spin-independent scattering with
g_N = g f_N m_N/v (f_N = 0.307, DirectDM's value). The other combinations are
momentum-suppressed and are not compared with the spin-independent envelope.
"""

from __future__ import annotations

import math

import numpy as np
from pydantic import field_validator

from adroit.constraints import annihilation, relic, spin1
from adroit.core.dm_state import DarkMatterParticle, InteractionModel
from adroit.core.state import StrictModel
from adroit.library.interactions import registry
from adroit.physics import conventions

V_HIGGS = 246.22
F_N = 0.307                       # Σ f_Tq + (2/9) f_TG for the nucleon (DirectDM, DM4)
M_NUCLEON = 0.939
GEV2_TO_CM3_S = annihilation.GEV2_TO_CM3_S



class Point(StrictModel):
    """One parameter point: dark matter and mediator masses, and the couplings."""

    m_chi: float
    m_med: float
    g_chi: float = 1.0
    g_q: float = 0.25
    g_l: float = 0.0


class Spin1Class(StrictModel):
    """A vector or axial mediator (DMWG's simplified models with free couplings)."""

    name: str = "spin-1 mediator"
    kind: spin1.Spin1Kind = spin1.Spin1Kind.vector

    def model(self, p: Point) -> spin1.Spin1Model:
        """The ``spin1.Spin1Model`` at this point: mediator mass m_med and couplings g_χ, g_q, g_ℓ."""
        return spin1.Spin1Model(kind=self.kind, m_med_gev=p.m_med, g_dm=p.g_chi, g_q=p.g_q, g_l=p.g_l,
                                label=self.name)

    def omega_h2(self, p: Point) -> float | None:
        """Ωh² from thermal freeze-out of this point's spin-1 model (``annihilation.omega_h2``); None outside the
        ``domain`` (the hadronic window)."""
        if self.domain(p):
            return None
        return annihilation.omega_h2(self.model(p), p.m_chi)

    def annihilation_poles(self, p: Point) -> list[tuple[float, float]]:
        """The mediator's pole (mass, width in GeV), the dark matter pair's s-channel, as the relic solve takes it: its
        velocity scale is the CMB's (``constraints.searches.velocity_scales``, AL7-01)."""
        return [(p.m_med, spin1.width(self.model(p), p.m_chi))]

    def domain(self, p: Point) -> str:
        """Why Ωh² is not computed (the owner's hadronic-validity decision, 2026-10-20), or "": the annihilation into
        quarks at √s ≈ 2m_χ in the hadronic window (to 2 GeV for the vector mediator, 3 GeV for the axial), or the
        mediator's hadronic width unknown where it moves the propagator. Both read the model's own quark couplings
        (``spin1.annihilation_window``, ``spin1.propagator_window``): a named flavour current's too (C21-01)."""
        model = self.model(p)
        return spin1.annihilation_window(model, p.m_chi) or spin1.propagator_window(model, p.m_chi, fixed=False)

    def today_hadronic(self, p: Point) -> str:
        """Why the quark pairs' annihilation today (√s ≈ 2m_χ) is not computed, or "" (``searches.today_unknown``;
        the CMB decides only where the other channels exclude alone)."""
        return spin1.annihilation_window(self.model(p), p.m_chi)

    def today_unknown(self, p: Point) -> str:
        """Why annihilation today is not computed at all: the mediator's unknown hadronic width moving the propagator
        at s = 4m_χ²."""
        return spin1.propagator_window(self.model(p), p.m_chi, fixed=True)

    def dd_channels(self, p: Point) -> list:
        """SI for a vector mediator; SD on protons and on neutrons for an axial one."""
        from adroit.parameter_space import dd_channels
        operator, c_p, c_n = spin1.nucleon_couplings(self.model(p), p.m_chi)
        if c_p == 0 and c_n == 0:              # no coupling: a zero cross-section, compared as before (not pending)
            return [dd_channels.Channel(kind="SI" if operator == 1 else "SD-proton", sigma_cm2=0.0)]
        if operator == 1:
            return dd_channels.channels_of(c_p, c_n, 0.0, 0.0, p.m_chi)
        return dd_channels.channels_of(0.0, 0.0, c_p, c_n, p.m_chi)

    def dd(self, p: Point) -> tuple[str, float]:
        """(kind, σ in cm²) of the channel that decides (``dd_channels``)."""
        from adroit.parameter_space.portals.base import decisive
        return decisive(self.dd_channels(p), p.m_chi)

    def sigma_v_today(self, p: Point, v_rel: float) -> dict[str, float]:
        """σv (cm³/s) by final state at the relative speed ``v_rel`` (``annihilation.sigma_v_today``): the quark pairs
        zero below the hadronic opening, and, where ``today_hadronic`` gives a reason, left out (not computed, not
        zero)."""
        out = annihilation.sigma_v_today(self.model(p), p.m_chi, v_rel)
        if self.today_hadronic(p):
            quarks = {f.name for f in spin1.FERMIONS if f.family == "quark"}
            return {k: v for k, v in out.items() if k not in quarks}
        return out

    def interaction(self, p: Point) -> InteractionModel:
        """The point's spin-1 model as an interaction for the rate code (``spin1.interaction``)."""
        return spin1.interaction(self.model(p), p.m_chi)

    def completion(self, p: Point) -> spin1.Spin1Model:
        """The spin-1 model itself: the completion DM7's collider records judge."""
        return self.model(p)


def _beta(s: np.ndarray, m: float) -> np.ndarray:
    return np.sqrt(np.clip(1.0 - 4.0 * m * m / s, 0.0, None))


class ScalarClass(StrictModel):
    """A real scalar mediator with mass-proportional couplings to the Standard Model's fermions."""

    name: str = "scalar mediator"
    dm_pseudoscalar: bool = False          # S χ̄ iγ⁵ χ instead of S χ̄ χ
    sm_pseudoscalar: bool = False          # S f̄ iγ⁵ f instead of S f̄ f
    yukawa: str = "DMsimp_s_spin0_MD"      # the masses in g m_f/v (``model_building.yukawa``; the owner's #2)

    @field_validator("yukawa")
    @classmethod
    def _known_convention(cls, value: str) -> str:
        from adroit.core.model_spec import YUKAWA_CONVENTIONS
        if value not in YUKAWA_CONVENTIONS:
            raise ValueError(f"yukawa is one of {', '.join(YUKAWA_CONVENTIONS)}, not {value!r}")
        return value

    def _couplings(self, p: Point) -> tuple[tuple[float, float], list[tuple[spin1.Fermion, float, float]]]:
        """The dark matter's (scalar, pseudoscalar) coupling and each fermion's, g m_f/v with m_f the declared Yukawa
        input (``yukawa``); the kinematics keep the table's kinematic masses (``kinematics.KINEMATIC_MASSES``)."""
        from adroit.model_building import yukawa
        y = (0.0, p.g_chi) if self.dm_pseudoscalar else (p.g_chi, 0.0)
        out = []
        for f in spin1.FERMIONS:
            if f.family == "neutrino":
                continue
            g = (p.g_q if f.family == "quark" else p.g_l) * yukawa.mass(self.yukawa, f.name) / V_HIGGS
            out.append((f, *((0.0, g) if self.sm_pseudoscalar else (g, 0.0))))
        return y, out

    def _quarks(self, energy: float, annihilation: bool = False) -> str:
        """The quark channels' state at ``energy`` (``hadronic_window.state``): the scalar's quark current is scalar,
        or pseudoscalar (CP-odd) for ``sm_pseudoscalar``, never vector, so its window is 2m_π or 3m_π to 3 GeV."""
        from adroit.constraints import hadronic_window as hw
        return hw.state(energy, vector=False, cp_odd=self.sm_pseudoscalar, annihilation=annihilation)

    def _widths(self, p: Point) -> tuple[dict[str, float], str]:
        """(the partial widths computed, by channel: each fermion's name, "dm" the dark matter's; why the quark
        channels' are not, or ""): the quark channels closed below the hadronic opening, free quarks above the
        hadronic window, left out with the reason inside it (the owner's decision, 2026-10-20: never set to zero)."""
        from adroit.constraints import hadronic_window as hw
        (ys, yp), fermions = self._couplings(p)
        quarks = self._quarks(p.m_med)
        widths, unknown = {}, ""
        for f, gs, gp in fermions:
            if p.m_med <= 2 * f.mass_gev or (gs == 0 and gp == 0):
                continue
            if f.family == "quark" and quarks != hw.PARTONIC:
                if quarks == hw.UNKNOWN:
                    unknown = hw.decay_reason("S", p.m_med, False, self.sm_pseudoscalar)
                continue
            b = math.sqrt(1 - 4 * f.mass_gev ** 2 / p.m_med ** 2)
            widths[f.name] = f.colours * p.m_med * (gs * gs * b ** 3 + gp * gp * b) / (8 * math.pi)
        if p.m_med > 2 * p.m_chi:
            b = math.sqrt(1 - 4 * p.m_chi ** 2 / p.m_med ** 2)
            widths["dm"] = p.m_med * (ys * ys * b ** 3 + yp * yp * b) / (8 * math.pi)
        return widths, unknown

    def width_bounds(self, p: Point) -> tuple[float, float, str]:
        """(Γ_S's lower and upper bound in GeV, why they differ or ""): where m_S is in the hadronic window the
        hadronic width is 0 ≤ Γ_had ≤ m_S, else both are Γ_S."""
        widths, unknown = self._widths(p)
        known = sum(widths.values())
        return known, known + (p.m_med if unknown else 0.0), unknown

    def width(self, p: Point) -> float:
        """Total width Γ_S (GeV): decays to Standard Model fermion pairs (neutrinos excluded) and, above 2m_χ, to
        χχ̄. Raises ``hadronic_window.HadronicUnknown`` where m_S is in the hadronic window and S couples to quarks
        (``width_bounds`` gives the bounds there)."""
        from adroit.constraints import hadronic_window as hw
        widths, unknown = self._widths(p)
        if unknown:
            raise hw.HadronicUnknown(unknown)
        return sum(widths.values())

    def _propagator_width(self, p: Point) -> float:
        """Γ_S in the s-channel propagator at √s ≥ 2m_χ: the computed width, or, in the hadronic window, its lower
        bound where no Γ_had up to m_S moves the propagator (``hadronic_window.propagator_insensitive``); raises
        ``HadronicUnknown`` where one would."""
        from adroit.constraints import hadronic_window as hw
        low, high, unknown = self.width_bounds(p)
        if unknown and not hw.propagator_insensitive(4 * p.m_chi ** 2, p.m_med, high):
            raise hw.HadronicUnknown(f"{unknown}, and it moves the s-channel propagator at √s ≥ 2m_χ")
        return low

    def domain(self, p: Point) -> str:
        """Why Ωh² is not computed (the owner's hadronic-validity decision, 2026-10-20), or "": the annihilation into
        quarks at √s ≈ 2m_χ in the hadronic window, or S's hadronic width unknown where it moves the s-channel
        propagator. Annihilation through leptons alone (g_q = 0) is always computed."""
        from adroit.constraints import hadronic_window as hw
        if p.g_q == 0:
            return ""
        if self._quarks(2 * p.m_chi, annihilation=True) == hw.UNKNOWN:
            return hw.annihilation_reason(2 * p.m_chi, False, self.sm_pseudoscalar)
        try:
            self._propagator_width(p)
        except hw.HadronicUnknown as error:
            return str(error)
        return ""

    def _sigma(self, s: np.ndarray, p: Point, only: str | None = None,
               gamma: float | None = None) -> np.ndarray | dict[str, np.ndarray]:
        """σ(χχ̄ → f f̄) by fermion through the s-channel scalar of width ``gamma`` (``_propagator_width`` if None):
        each quark pair closed below the hadronic opening (``hadronic_window.opening``; ``domain`` refuses an
        annihilation in the window)."""
        from adroit.constraints import hadronic_window as hw
        (ys, yp), fermions = self._couplings(p)
        gamma = self._propagator_width(p) if gamma is None else gamma
        bx = _beta(s, p.m_chi)
        prop = (s - p.m_med ** 2) ** 2 + (p.m_med * gamma) ** 2
        hadrons = np.sqrt(s) >= hw.opening(self.sm_pseudoscalar)
        out = {}
        for f, gs, gp in fermions:
            bf = _beta(s, f.mass_gev)
            with np.errstate(divide="ignore", invalid="ignore"):
                sig = f.colours * s * (ys * ys * bx * bx + yp * yp) * (gs * gs * bf * bf + gp * gp) * bf / (
                    16 * math.pi * bx * prop)
            sig = np.nan_to_num(sig, nan=0.0, posinf=0.0)
            out[f.name] = np.where(hadrons, sig, 0.0) if f.family == "quark" else sig
        return out

    def _pair(self, s: np.ndarray, p: Point) -> np.ndarray:
        """σ(χχ̄ → SS) from t- and u-channel χ exchange (the explicit amplitude; S³ taken as zero)."""
        from adroit.constraints import processes
        from adroit.parameter_space.portals.base import tabulated
        y = (0.0, p.g_chi) if self.dm_pseudoscalar else (p.g_chi, 0.0)

        def sigma(ss: float) -> float:
            return processes.fermion_to_scalars(ss, p.m_chi, p.m_med, p.m_med, y, y, identical=True)
        return tabulated(("scalar_class_SS", p.m_chi, p.m_med, p.g_chi, self.dm_pseudoscalar), sigma, p.m_chi,
                         2.0 * p.m_med, s)

    def omega_h2(self, p: Point) -> float | None:
        """Ωh² from annihilation to fermion pairs and, above (and in the thermal tail below) m_χ = m_S, to SS; None
        outside the ``domain`` (the hadronic window)."""
        if self.domain(p):
            return None
        return relic.omega_h2(lambda s: sum(self._sigma(s, p).values()) + self._pair(s, p), p.m_chi,
                              resonance_gev=p.m_med, width_gev=self._propagator_width(p))

    def annihilation_poles(self, p: Point) -> list[tuple[float, float]]:
        """The mediator's pole (mass, and the width's lower bound in GeV, ``width_bounds``: in the hadronic window the
        width without its uncomputed hadronic part, which gives the smallest velocity scale): its velocity scale is the
        CMB's (``constraints.searches.velocity_scales``, AL7-01)."""
        return [(p.m_med, self.width_bounds(p)[0])]

    def dd(self, p: Point) -> tuple[str, float]:
        """(kind, σ in cm²): spin-independent from scalar–scalar exchange with g_N = g_q f_N m_N/v;
        momentum-suppressed (zero) if either coupling is pseudoscalar."""
        if self.dm_pseudoscalar or self.sm_pseudoscalar:
            return "momentum-suppressed", 0.0
        g_n = p.g_q * F_N * M_NUCLEON / V_HIGGS
        c1 = p.g_chi * g_n / p.m_med ** 2
        return "SI", conventions.sigma_si_cm2(c1, p.m_chi)

    def _today(self, p: Point) -> tuple[float, list[str]]:
        """(Γ_S for today's rates, why they are not all computed): the quark pairs at √s ≈ 2m_χ in the hadronic window;
        S's hadronic width unknown where it moves the propagator at s = 4m_χ² (every σv falls as Γ rises, so the
        width's upper bound gives each rate's lower bound)."""
        from adroit.constraints import hadronic_window as hw
        reasons = []
        if p.g_q and self._quarks(2 * p.m_chi, annihilation=True) == hw.UNKNOWN:
            reasons.append(hw.annihilation_reason(2 * p.m_chi, False, self.sm_pseudoscalar))
        low, high, unknown = self.width_bounds(p)
        if unknown and not hw.propagator_insensitive(4 * p.m_chi ** 2, p.m_med, high, fixed=True):
            reasons.append(f"{unknown}, and it moves the s-channel propagator at √s ≈ 2m_χ: the rates computed are "
                           "their lower bounds, at Γ_had = m")
            return high, reasons
        return low, reasons

    def today_hadronic(self, p: Point) -> str:
        """Why annihilation today is not all computed (the hadronic window), or "": ``sigma_v_today`` then gives
        lower bounds of the other channels only; ``searches.today_unknown`` keeps every search that needs the total
        undecided, and the CMB decides only where those lower bounds exclude by themselves."""
        return "; ".join(self._today(p)[1])

    def sigma_v_today(self, p: Point, v_rel: float) -> dict[str, float]:
        """σv (cm³/s) by final state at the relative speed ``v_rel``: each fermion pair through the s-channel scalar,
        and SS. Where ``today_hadronic`` gives a reason, the quark pairs in the hadronic window are left out (not
        computed, not zero) and the others are lower bounds."""
        from adroit.constraints import hadronic_window as hw
        beta = 0.5 * v_rel
        s = np.array([4.0 * p.m_chi ** 2 / (1.0 - beta ** 2)])
        gamma, _ = self._today(p)
        window = p.g_q and self._quarks(2 * p.m_chi, annihilation=True) == hw.UNKNOWN
        quarks = {f.name for f in spin1.FERMIONS if f.family == "quark"} if window else set()
        out = {k: float(v[0]) * v_rel * GEV2_TO_CM3_S for k, v in self._sigma(s, p, gamma=gamma).items()
               if k not in quarks}
        out["SS"] = float(self._pair(s, p)[0]) * v_rel * GEV2_TO_CM3_S
        return out

    def interaction(self, p: Point) -> InteractionModel:
        """The interaction for the rate code: the scalar/pseudoscalar card matching the two couplings, with every
        nucleon coupling set to g_q f_N m_N/v."""
        g_n = p.g_q * F_N * M_NUCLEON / V_HIGGS
        card = {(False, False): "M_scalar", (True, False): "M_pseudoscalar_scalar",
                (False, True): "M_scalar_pseudoscalar", (True, True): "M_pseudoscalar"}[
            (self.dm_pseudoscalar, self.sm_pseudoscalar)]
        values = {"g_chi": p.g_chi, "m_med": p.m_med}
        params = {q.name for q in registry.card(card).parameters}
        for name in params:
            if name.startswith(("gS_", "gP_", "g_N", "gN")):
                values[name] = g_n
        return registry.resolve(card, DarkMatterParticle(mass_gev=p.m_chi), values, name=self.name)

    def completion(self, p: Point) -> None:
        """None: only the spin-1 class has a completion for the collider records."""
        return None


def fermi_ratio(channels: dict[str, float], m_chi: float, limits: dict) -> float | None:
    """Published pure-channel limit for Dirac dark matter, or pending coverage."""
    from adroit.constraints.indirect import FERMI_CHANNELS, pure_ratio
    return pure_ratio(channels, m_chi, {k: v["limit_cm3_s"] for k, v in limits.items()},
                      FERMI_CHANNELS, False)


ModelClass = Spin1Class | ScalarClass
