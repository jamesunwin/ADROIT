"""t-channel portals: dark matter coupling to one Standard Model fermion through a charged scalar partner.

L ⊃ y φ* χ̄ P_R f + h.c., with χ a Majorana or Dirac fermion (the dark matter) and φ a
scalar carrying f_R's charges: a colour triplet for a quark (the LHC Dark Matter Working
Group's t-channel models, S3M_uR and S3D_uR of arXiv:2504.10597; Garny, Ibarra & Vogl
arXiv:1503.01500), or a colour singlet for a lepton (the "lepton portal", Bai & Berger
arXiv:1402.6696). Slots: m_med = m_φ, g_χ = y.

**The relic density** includes coannihilation with φ (Edsjö & Gondolo), which dominates
when m_φ is close to m_χ:
- χχ → f f̄ (t- and u-channel φ; p-wave for Majorana, s-wave for Dirac);
- χφ → f V; φφ* → VV and → f′f̄′ (an s-channel V, and χ exchange for f′ = f);
- φφ → ff (Majorana only),

with V the gluon (α_s at m_φ) for a coloured φ, and the hypercharge boson in the unbroken
phase (g′, φ's hypercharge) for a lepton partner, valid for m_φ ≫ m_Z. Electroweak
channels of a coloured φ and the Higgs-portal coupling φ†φ H†H are left out.

**Long-range effects** (``sommerfeld``), which the literature finds essential for a
coloured partner near degeneracy (arXiv:2203.04326, 2504.10597): the Sommerfeld factor of
each colour channel of φφ* (singlet, octet) and φφ (antitriplet, sextet), with α_s at the
momentum transfer; the hypercharge Coulomb factor for a lepton partner; and, for a coloured
partner, formation of the φφ* ground state in ionisation equilibrium (``thermal_pairs``).
Validated (2026-10-03) on the largest thermal mass as Δm → 0: 1.29 TeV without the effects
and 1.72 TeV with the Sommerfeld factor (De Simone et al., arXiv:1402.6287: 1.3 and 1.7);
2.91 TeV with bound states, inside the literature's 2.4–3.3 TeV (Becker et al. 2.4, Liew &
Luo 2.5, Harz & Petraki 3.3); and the gains over the perturbative mass of Garny & Heisig and
Becker et al. to 5–10%. The spread is a ±15% theory uncertainty on the thermal mass (±35% on
Ωh²) where coannihilation dominates; excited bound states and thermal masses are left out.

**Direct detection** at tree level, from the Fierz-rearranged exchange of φ with
denominator m_φ² − m_χ²: for Dirac χ a vector coupling to the quark (spin-independent,
G = y²/8(m_φ² − m_χ²)) and an axial one (spin-dependent); for Majorana χ the axial one
only. Beyond tree level (``constraints.loops``, 2026-10-04):
- a coloured partner's scalar, twist-2 and gluon couplings (Hisano et al.), spin-independent,
  which dominate a Majorana χ's scattering near degeneracy: c₁ = 2f_N for Majorana χ, f_N added to
  the vector coupling for Dirac χ;
- a lepton partner's anapole for Majorana χ (O₈ and O₉, compared through the Path 1 table of
  ``operator_limits``); for Dirac χ the charge radius and the magnetic moment's contact term
  (c₁ᵖ, protons only). A Dirac χ's long-range dipole scattering (1/q²) and anapole are not computed
  and are listed as pending: the rate from c₁ᵖ alone is a lower bound (O₁ interferes with neither).

**Near degeneracy** (2026-10-10, replacing a flag below m_φ − m_χ = 10 GeV). The coefficients expand the
partner's propagator 1/((p_χ + p_q)² − m_φ²) at a quark momentum p_q ≈ x p_N, i.e. in
ε(x) = 2x m_χ m_N/(m_φ² − m_χ²). At the kinematic maximum x = 1 the series' remainder bounds the relative
uncertainty of every coloured partner's scattering amplitude by δ = ε/(1 − ε) (``degeneracy``): about 10% at
m_φ − m_χ = 10 GeV, 23% at 5 GeV, 89% at 2 GeV, and negligible far from degeneracy. For Majorana χ, whose amplitude
is twist-2 dominated, the twist-2 part's remainder is bounded more tightly by the quark's ⟨x²⟩/⟨x⟩ (2026-10-12,
``loops.coloured_partner_weight``; docs/twist2/README.md): about ±2% at 10 GeV and ±18% at 2 GeV for u_R. Dirac χ
keeps ε/(1 − ε). Direct detection compares the ratio band [r(1 − δ)², r(1 + δ)²] with 1 (``dd_channels``). For ε ≥ 1 (m_φ − m_χ ≲ m_N) the quark's momentum can
put the partner on shell, the expansion fails, and direct detection is not computed (pending).
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import ClassVar, Literal
from adroit.core.chemical_equilibrium import ConversionRequest, ConversionInput, ChemicalEquilibriumCertificate

import numpy as np

from adroit.constraints import higgs, kinetic_mixing as km, loops, processes, relic, sommerfeld, spin1
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.base import Nucleon, Portal, close_partons, tabulated

PARTNERS = {"uR": ("u", 2 / 3, True), "dR": ("d", -1 / 3, True), "bR": ("b", -1 / 3, True),
            "muR": ("mu", -1.0, False), "eR": ("e", -1.0, False), "tauR": ("tau", -1.0, False)}
FERMIONS = {f.name: f for f in spin1.FERMIONS}
HYPERCHARGE = {"up": (1 / 6, 2 / 3), "down": (1 / 6, -1 / 3), "lepton": (-0.5, -1.0), "neutrino": (-0.5, 0.0)}
COMPRESSED = 1.2
M_N = 0.938918747                     # GeV: the nucleon mass in the propagator expansion (``degeneracy``)


def degeneracy(m_chi: float, m_med: float) -> tuple[float, float] | None:
    """(ε, δ) of a coloured partner's propagator expansion at x = 1 (module docstring); None if ε ≥ 1 or
    m_φ ≤ m_χ, where the expansion fails."""
    gap = m_med ** 2 - m_chi ** 2
    if gap <= 0:
        return None
    eps = 2.0 * m_chi * M_N / gap
    return (eps, eps / (1.0 - eps)) if eps < 1.0 else None
_PAIRS: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}


def _freeze_out_x(cls_json: str, point_json: str) -> float | None:
    """A t-channel point's freeze-out x_f, once per class, point and degrees of freedom (the certificate asks for it
    repeatedly; ``relic.current_eos``)."""
    from adroit.constraints import relic
    return _freeze_out_x_at(cls_json, point_json, relic.current_eos())


@lru_cache(maxsize=256)
def _freeze_out_x_at(cls_json: str, point_json: str, eos: str) -> float | None:
    return TChannel.model_validate_json(cls_json).freeze_out_x(Point.model_validate_json(point_json))


class TChannel(Portal):
    """Majorana or Dirac dark matter with a scalar partner of one right-handed fermion."""

    family: Literal["t_channel"] = "t_channel"
    partner: Literal["uR", "dR", "bR", "muR", "eR", "tauR"] = "uR"
    majorana: bool = True
    sommerfeld: bool = True               # the partner pair's Sommerfeld factor, by colour (or charge) channel
    bound_states: bool = True
    conversion: ConversionRequest | None = None             # bound-state formation of a coloured partner pair
    LABELS: ClassVar[dict[str, str]] = {"m_chi": "m_χ (GeV)", "m_med": "m_φ (GeV)", "g_chi": "y"}

    def self_conjugate(self) -> bool:
        """True for Majorana dark matter."""
        return self.majorana

    def _fermion(self):
        name, hypercharge, coloured = PARTNERS[self.partner]
        return FERMIONS[name], hypercharge, coloured

    def _gauge(self, p: Point) -> float:
        _, _, coloured = self._fermion()
        return math.sqrt(4.0 * math.pi * higgs.alpha_s(p.m_med)) if coloured else km.G_PRIME

    def domain(self, p: Point) -> str:
        """Ωh² is not computed unless m_φ > m_χ, nor with y = 0 (φ is then a second stable component), nor for a
        lepton partner below m_φ = 200 GeV (its coannihilation is computed in the unbroken phase). Its chemical
        equilibrium is the certificate's prerequisite (``pending``)."""
        if p.m_med <= p.m_chi:
            return "the partner φ must be heavier than the dark matter"
        if p.g_chi == 0:                                   # the owner's decision #5, 2026-10-20: one component only
            return ("several stable components: with y = 0 nothing lets the partner φ decay to the dark matter; ADROIT "
                    "computes one component's relic")
        _, _, coloured = self._fermion()
        if not coloured and p.m_med < 200.0:
            return "the lepton partner's coannihilation is computed in the unbroken phase, for m_φ ≳ 200 GeV"
        return self.today_hadronic(p) or self._coloured_bath(p)

    def _coloured_bath(self, p: Point) -> str:
        """Why the coloured partner's part of the bath is not computed, or "": its pairs (χφ from m_χ + m_φ, φφ* from
        2m_φ, and their bound states) reach the hadronic regime at or below the window's top, 3 GeV, where coloured
        states are confined: a free-parton bath is not their rate, and none is set to zero (the re-audit's RR22-01,
        2026-10-22: with χχ closed below 2m_π the partner pairs' free-quark and gluon rates had reached the relic
        solver)."""
        from adroit.constraints import hadronic_window as hw
        _, _, coloured = self._fermion()
        if not coloured or p.m_chi + p.m_med > hw.TOP:
            return ""
        return (f"the coloured partner's pairs in the bath annihilate from √s = m_χ + m_φ = {p.m_chi + p.m_med:.4g} "
                f"GeV, at or below {hw.TOP:g} GeV, where coloured states are confined into hadrons: the bath's "
                "free-parton rates do not establish them (ADROIT's hadronic-validity policy); not computed")

    def today_hadronic(self, p: Point) -> str:
        """Why the annihilation into the partner's quark at √s ≈ 2m_χ is not computed: a t-channel exchange is not a
        classified current, so the hadronic window runs to 3 GeV (the owner's hadronic-validity decision,
        2026-10-20); "" for a lepton partner or above it."""
        from adroit.constraints import hadronic_window as hw
        _, _, coloured = self._fermion()
        if not coloured or hw.state(2 * p.m_chi, vector=False, annihilation=True) != hw.UNKNOWN:
            return ""
        return hw.annihilation_reason(2 * p.m_chi, False, False)

    def flags(self, p: Point) -> list[str]:
        """Warnings for a coloured partner near degeneracy (m_φ < 1.2 m_χ with the Sommerfeld effect or bound states
        switched off; within about m_N, where direct detection is not computed), and the chemical-equilibrium
        certificate's status."""
        _, _, coloured = self._fermion()
        out = []
        if coloured and p.m_med < COMPRESSED * p.m_chi and not (self.sommerfeld and self.bound_states):
            out.append("unreliable: the coloured partner's Sommerfeld effect and bound states, switched off here, "
                       "change Ωh² where coannihilation dominates (m_φ < 1.2 m_χ)")
        if coloured and degeneracy(p.m_chi, p.m_med) is None:
            out.append("unreliable: within about m_N of degeneracy the quark's momentum can put the partner on shell; "
                       "direct detection is not computed here")
        certificate=self.chemical_certificate(p)
        from adroit.theory.chemical_equilibrium import PREREQUISITE_FLAG
        if _plasma_requested(certificate) and certificate.physical_prerequisite=='supported':
            out.append('effective coannihilation chemical equilibrium supported at leading order in the plasma '
                       '(thermal masses, quantum statistics); kinetic equilibrium separate')
        elif _plasma_requested(certificate):         # asked for, it decides even when it failed to compute (PX-08)
            out.append('effective coannihilation relic assumes chemical equilibrium, which '
                       + ('fails' if certificate.physical_prerequisite=='failed' else 'is unresolved')
                       + ' at leading order in the plasma')
        elif certificate.physical_prerequisite=='supported':
            out.append('effective coannihilation chemical equilibrium supported at leading order in the plasma '
                       '(thermal masses, quantum statistics); kinetic equilibrium separate')
        elif certificate.component_prerequisite=='supported':
            out.append('effective coannihilation chemical equilibrium supported at declared source-regulated component accuracy; higher-order/plasma and kinetic checks separate')
        else:
            out.append(PREREQUISITE_FLAG if certificate.physical_prerequisite=='pending'
                else 'effective coannihilation relic assumes chemical equilibrium; physical prerequisite failed')
        return out

    def pending(self, p: Point) -> list[str]:
        """What applies but is not computed (the squark search and the muon's g − 2 are, in ``searches``)."""
        f, _, coloured = self._fermion()
        certificate=self.chemical_certificate(p)
        if _plasma_requested(certificate):          # the leading-order plasma rates were asked for: they decide, and a
                                                    # failure to compute them leaves the prerequisite pending (PX-08)
            prerequisite=[] if certificate.physical_prerequisite=='supported' else [
                f"coannihilation chemical equilibrium {certificate.physical_prerequisite} at leading order in the plasma"]
        else:
            prerequisite=[] if certificate.component_prerequisite=='supported' else [
                f"coannihilation chemical equilibrium: {certificate.status}; {certificate.physical_prerequisite}"]
        if coloured:
            return prerequisite
        out = [] if self.majorana else ["direct detection: the Dirac χ's magnetic-dipole scattering (1/q², O₄–O₆) "
                                        "and anapole are not computed; the charge radius alone is a lower bound"]
        return out + prerequisite + (["LEP's selectron search: not yet a record"]
                                     if self.partner == "eR" and p.m_med < 110.0 else [])

    def chemical_certificate(self, p: Point) -> ChemicalEquilibriumCertificate:
        """Diagnose the chemical-equilibrium assumption without changing the relic solver; the declared window is
        tied to this point's freeze-out (audit M11)."""
        from adroit.theory.chemical_equilibrium import certify
        x_f = _freeze_out_x(self.model_dump_json(), p.model_dump_json()) if self.conversion is not None else None
        certificate = certify(ConversionInput(point=p,partner=self.partner,majorana=self.majorana,
            g_prime=km.G_PRIME,request=self.conversion,freeze_out_x=x_f))
        if self.conversion is not None and x_f is None:     # mini audit: no freeze-out to tie the window to
            return certificate.model_copy(update={
                "status": "unresolved", "passed": None, "complete": False,
                "component_prerequisite": "unresolved" if self.conversion.source_born is not None else None,
                "reasons": ["the relic solver gave no freeze-out x_f at this point, so the declared window cannot be "
                            "tied to it"]})
        return certificate

    # --- annihilation ----------------------------------------------------------------------------
    def _chi_chi(self, s, p: Point):
        f, _, _ = self._fermion()

        def sigma(ss: float) -> float:
            return processes.t_channel_to_fermions(ss, p.m_chi, f.mass_gev, p.m_med, p.g_chi, self.majorana,
                                                   f.colours)
        return tabulated(("tc_xx", self.partner, self.majorana, p.m_chi, p.m_med, p.g_chi), sigma, p.m_chi,
                         2.0 * f.mass_gev, s)

    def channels(self, s, p: Point) -> dict[str, np.ndarray]:
        """χχ (χχ̄ for Dirac) → f f̄ through t- and u-channel φ exchange."""
        f, _, _ = self._fermion()
        return {f.name: self._chi_chi(s, p)}

    def _pair(self, key: str, p: Point, fn, m_a: float, m_b: float, threshold: float, s) -> np.ndarray:
        """σ(s) of a pair of species of masses m_a, m_b, tabulated in √s from its threshold."""
        tag = (self.partner, self.majorana, self.sommerfeld, self.bound_states, key, p.m_chi, p.m_med, p.g_chi)
        if tag not in _PAIRS:
            if len(_PAIRS) > 2000:
                _PAIRS.clear()
            start = max(m_a + m_b, threshold)
            roots = start * (1.0 + np.concatenate([[1e-9], np.geomspace(1e-6, 25.0, 46)]))
            _PAIRS[tag] = (roots, np.array([fn(r * r) for r in roots]))
        roots, values = _PAIRS[tag]
        root = np.sqrt(np.asarray(s, dtype=float))
        return np.where(root > roots[0], np.interp(root, roots, values), 0.0)

    def coannihilation(self, p: Point):
        """The bath of χ (Majorana, or a Dirac pair) and φ, φ* (3 colour states each if coloured), with σ(s) of χχ,
        χφ, φφ* and, for Majorana χ, φφ and φ*φ*; the partner pairs carry Sommerfeld factors by colour or charge
        channel if ``sommerfeld``."""
        f, y_phi, coloured = self._fermion()
        g = self._gauge(p)
        m, M, y = p.m_chi, p.m_med, p.g_chi
        dof = 3.0 if coloured else 1.0
        se = self.sommerfeld

        def factor(channel: str, ss: float) -> float:
            """The Sommerfeld factor of the partner pair's channel at √s (1 without the effect)."""
            return self._partner_factor(channel, ss, M, coloured, y_phi) if se else 1.0

        phi_phibar, chi_phi = self._partner_channels(p, f, y_phi, coloured, g, factor)

        def phi_phi(ss: float) -> float:
            six, three = processes.partners_to_same_fermions_by_colour(ss, M, f.mass_gev, m, y, coloured)
            if not coloured:
                return six * factor("sextet", ss)
            return six * factor("sextet", ss) + three * factor("antitriplet", ss)

        sigma_xx = lambda s: close_partons(s, {f.name: self._chi_chi(s, p)})[f.name]       # noqa: E731
        sigma_xp = lambda s: self._pair("xp", p, chi_phi, m, M, f.mass_gev, s)                  # noqa: E731
        sigma_pp = lambda s: self._pair("pp", p, phi_phibar, M, M, 0.0, s)                     # noqa: E731
        if self.majorana:
            sigma_same = lambda s: self._pair("ss", p, phi_phi, M, M, 2.0 * f.mass_gev, s)     # noqa: E731
            species = [relic.Species(m, 2.0), relic.Species(M, dof), relic.Species(M, dof)]
            pairs = {(0, 0): sigma_xx, (0, 1): sigma_xp, (0, 2): sigma_xp, (1, 2): sigma_pp,
                     (1, 1): sigma_same, (2, 2): sigma_same}
        else:
            species = [relic.Species(m, 2.0), relic.Species(m, 2.0), relic.Species(M, dof), relic.Species(M, dof)]
            pairs = {(0, 1): sigma_xx, (0, 2): sigma_xp, (1, 3): sigma_xp, (2, 3): sigma_pp}
        return species, pairs

    def _partner_factor(self, channel: str, ss: float, M: float, coloured: bool, y_phi: float) -> float:
        """The Sommerfeld factor of the partner pair's colour or charge channel at √s (``coannihilation``)."""
        beta = sommerfeld.beta_of(ss, M)
        if coloured:
            return float(sommerfeld.colour_factor(channel, self.alpha_potential(M, beta), np.array([beta]))[0])
        alpha = km.G_PRIME ** 2 * y_phi ** 2 / (4.0 * math.pi)            # hypercharge, unbroken phase
        sign = {"singlet": 1.0, "sextet": -1.0}[channel]
        return float(sommerfeld.coulomb(sign * alpha, np.array([beta]))[0])

    def _partner_channels(self, p: Point, f, y_phi: float, coloured: bool, g: float, factor):
        """σ(s) of φφ* and χφ for ``coannihilation``: by colour for a coloured partner, else by hypercharge."""
        m, M, y = p.m_chi, p.m_med, p.g_chi
        if coloured:
            def phi_phibar(ss: float) -> float:
                one, eight = processes.partners_to_gauge_bosons_by_colour(ss, M, g, coloured=True)
                for q in ("u", "d", "s", "c", "b", "t"):
                    fq = FERMIONS[q]
                    coupled = q == f.name
                    a, b = processes.partners_to_fermions_by_colour(ss, M, fq.mass_gev, g, 1.0, True,
                                                                    y=y if coupled else 0.0, m_chi=m)
                    one, eight = one + a, eight + b
                return one * factor("singlet", ss) + eight * factor("octet", ss)

            def chi_phi(ss: float) -> float:
                return processes.dm_partner_to_fermion_boson(ss, m, M, f.mass_gev, y, g, 1.0, coloured=True)
        else:
            def phi_phibar(ss: float) -> float:
                total = processes.partners_to_gauge_bosons(ss, M, g * abs(y_phi), coloured=False)
                for name, fx in FERMIONS.items():
                    y_l, y_r = HYPERCHARGE[km.KIND[name]]
                    coupled = name == f.name
                    total += processes.partners_to_fermions(ss, M, fx.mass_gev, g, (y_phi * y_l, y_phi * y_r),
                                                            False, y=y if coupled else 0.0, m_chi=m,
                                                            colours_f=fx.colours)
                return total * factor("singlet", ss)

            def chi_phi(ss: float) -> float:
                return processes.dm_partner_to_fermion_boson(ss, m, M, f.mass_gev, y, g, y_phi, coloured=False)
        return phi_phibar, chi_phi

    @staticmethod
    def alpha_potential(m_phi: float, beta: float) -> float:
        """α_s of the partners' potential, at the momentum transfer m_φβ, not below the Bohr momentum."""
        hard = higgs.alpha_s(m_phi)
        return higgs.alpha_s(max(m_phi * beta, 0.5 * m_phi * sommerfeld.C_F * hard))

    def thermal_pairs(self, p: Point) -> dict:
        """Bound-state formation of a coloured partner and its antiparticle (``sommerfeld.bound_state_rate``)."""
        _, _, coloured = self._fermion()
        if not (coloured and self.bound_states) or self.domain(p):
            return {}
        pair = (1, 2) if self.majorana else (2, 3)
        return {pair: lambda temperature: sommerfeld.bound_state_rate(p.m_med, temperature)}

    # --- scattering ------------------------------------------------------------------------------
    def nucleon(self, p: Point) -> Nucleon:
        """A coloured partner's Fierz-rearranged tree-level couplings plus its loop-induced spin-independent ones
        (``loops.coloured_partner_si``); a lepton partner's loop-induced scattering (``_lepton_nucleon``)."""
        f, _, coloured = self._fermion()
        if not coloured:
            return self._lepton_nucleon(p, f.mass_gev)
        g = p.g_chi ** 2 / (8.0 * (p.m_med ** 2 - p.m_chi ** 2))
        n = spin1.DMWG_2016
        spin = {"u": (n.delta_u, n.delta_d), "d": (n.delta_d, n.delta_u), "b": (0.0, 0.0)}[f.name]
        valence = {"u": (2.0, 1.0), "d": (1.0, 2.0), "b": (0.0, 0.0)}[f.name]
        axial = 2.0 * g if self.majorana else g             # the Majorana axial current's factor of 2
        f_p, f_n = loops.coloured_partner_si(p.m_chi, p.m_med, p.g_chi, f.name)
        if self.majorana:                                    # twist-2, scalar and gluon: c₁ = 2 f_N
            return Nucleon(c1_p=2.0 * f_p, c1_n=2.0 * f_n, c4_p=4.0 * axial * spin[0], c4_n=4.0 * axial * spin[1])
        return Nucleon(c1_p=g * valence[0] + f_p, c1_n=g * valence[1] + f_n,
                       c4_p=4.0 * axial * spin[0], c4_n=4.0 * axial * spin[1])

    def dd_channels(self, p: Point) -> list:
        """The channels; a coloured partner's carry the amplitude uncertainty of the propagator's expansion
        (``degeneracy``), or are not computed where it fails."""
        from adroit.parameter_space import dd_channels
        n = self.nucleon(p)
        if n.structure:
            return []
        _, _, coloured = self._fermion()
        if not coloured:
            return dd_channels.channels_of(n.c1_p, n.c1_n, n.c4_p, n.c4_n, p.m_chi)
        found = degeneracy(p.m_chi, p.m_med)
        if found is None:
            return dd_channels.channels_of(n.c1_p, n.c1_n, n.c4_p, n.c4_n, p.m_chi, unreliable=(
                "within about m_N of degeneracy the quark's momentum can put the partner on shell"))
        eps, delta = found
        how = "the x = 1 bound"
        if self.majorana:                       # twist-2 dominated: its remainder is bounded by ⟨x²⟩/⟨x⟩ (``loops``)
            delta *= loops.coloured_partner_weight(p.m_chi, p.m_med, self._fermion()[0].name)
            how = "the twist-2 remainder bounded by the quark's ⟨x²⟩/⟨x⟩"
        return dd_channels.channels_of(n.c1_p, n.c1_n, n.c4_p, n.c4_n, p.m_chi, uncertainty=delta,
                                       note=f"±{100 * delta:.0f}% on the amplitude near degeneracy ({how}), ε = {eps:.3f}")

    def _lepton_nucleon(self, p: Point, m_lepton: float) -> Nucleon:
        """A lepton partner's loop-induced scattering: the anapole (Majorana) or the charge radius (Dirac)."""
        if self.majorana:
            return Nucleon(structure="anapole", scale=loops.anapole_moment(p.m_chi, p.m_med, p.g_chi, m_lepton))
        moment, radius = loops.dirac_moments(p.m_chi, p.m_med, p.g_chi, m_lepton)
        return Nucleon(c1_p=-loops.E_CHARGE * (radius + moment / (2.0 * p.m_chi)), c1_n=0.0)


def _plasma_requested(certificate) -> bool:
    """Whether the certificate's request asked for the leading-order plasma rates (not whether any came back)."""
    request = certificate.inputs.request
    return request is not None and request.plasma is not None
