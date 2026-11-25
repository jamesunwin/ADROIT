"""Higgs portals: dark matter that talks to the Standard Model through the Higgs boson.

- ``HiggsPortalScalar``: a real singlet scalar S, V ⊃ ½ λ_hs S² H†H
  (Silveira & Zee; McDonald; GAMBIT, arXiv:1705.07931).
- ``HiggsPortalFermion``: a Dirac or Majorana singlet fermion with the
  dimension-5 operator (λ_hχ/Λ) χ̄(cos ξ + i sin ξ γ⁵)χ H†H, ½ of it for
  Majorana (GAMBIT, arXiv:1808.10465); ξ is the CP phase.
- ``HiggsPortalVector``: a real vector V_μ, L ⊃ ½ λ_hV V_μV^μ H†H (ibid.).
- ``SingletMixing``: a Dirac fermion coupling to a real singlet scalar that
  mixes with the Higgs boson by an angle θ (Kim, Lee & Shin, arXiv:0803.2932;
  Baek, Ko & Park, arXiv:1112.1847).

Annihilation into Standard Model states goes through the off-shell Higgs
boson(s) with the width of ``constraints.higgs`` (every final state of a
Higgs boson of mass √s); pairs of Higgs bosons (or of the singlet) from
explicit amplitudes (``constraints.processes``). Direct detection is
spin-independent with f_N = 0.307 (DM13's value); the invisible width of the
125 GeV Higgs boson is given wherever it decays into dark matter.
"""

from __future__ import annotations

import math
from typing import ClassVar, Literal

import numpy as np

from adroit.constraints import exchange, higgs, processes
from adroit.constraints.exchange import Mediator
from adroit.parameter_space.classes import F_N, M_NUCLEON, Point
from adroit.parameter_space.portals.base import Nucleon, Portal, tabulated

V = higgs.V_HIGGS
M_H = higgs.M_H
SM_CHANNELS = ("b", "c", "tau", "mu", "t", "W", "Z", "g", "gamma", "Zgamma")
LIGHT_CHANNELS = ("e", "mu", "gamma")   # an off-shell Higgs boson's below its SM table (``higgs.light_channel_width``)
LIGHT_LIMIT_GEV = 2.0          # below: the hadronic final states of an off-shell Higgs boson are not reliable


def _beta(m: float, M: float) -> float:
    return math.sqrt(max(1.0 - 4.0 * m * m / (M * M), 0.0))


def _standard_model(s, m: float, dm: str, couplings, kappas, mediators) -> dict[str, np.ndarray]:
    """σ into each Standard Model final state through the off-shell Higgs boson(s), by Γ_h*(√s): the SM table from
    ``higgs.WIDTH_FROM``; below it (√s < 2 GeV, annihilation today below m_DM = 1 GeV) the lepton pairs and γγ
    (``LIGHT_CHANNELS``): the table's zero there had been every rate, and the CMB took it as out of reach (the owner's
    follow-up to the RZ23 re-audit, 2026-10-23). The quark and gluon pairs there are closed below 2m_π and not
    computed in the hadronic window (``today_hadronic``)."""
    out = {c: exchange.scalar_to_standard_model(s, m, dm, couplings, kappas, mediators, (c,)) for c in SM_CHANNELS}
    below = np.sqrt(np.asarray(s, dtype=float)) < higgs.WIDTH_FROM
    if np.any(below):
        for c in LIGHT_CHANNELS:
            light = exchange.scalar_to_standard_model(s, m, dm, couplings, kappas, mediators,
                                                      width=lambda root, c=c: higgs.light_channel_width(root, c))
            out[c] = np.where(below, light, out.get(c, 0.0))
    return out


def _today_hadronic(p: Point) -> str:
    """Why the quark and gluon pairs' annihilation today through the off-shell Higgs boson is not computed: √s ≈ 2m_χ
    in the hadronic window of its CP-even current (2m_π to 3 GeV, ``hadronic_window``), or "". The CMB then decides
    only where the other channels exclude alone (``searches.cmb``); every other search that needs it is undecided."""
    from adroit.constraints import hadronic_window as hw
    if hw.state(2.0 * p.m_chi, annihilation=True) != hw.UNKNOWN:
        return ""
    return hw.annihilation_reason(2.0 * p.m_chi, False, False)


def _propagator(s: float, mass: float, width: float) -> complex:
    return 1.0 / (s - mass * mass + 1j * mass * width)


RESONANCE_FLAG = ("unreliable: at the Higgs resonance (m_DM within 2 GeV of m_h/2) published codes and MadDM "
                  "differ from ADROIT, and from each other, by up to ~2 in σv (docs/portal_library.md, section 6; "
                  "kinetic decoupling, arXiv:1706.07433, matters here)")


def _resonance_flags(p: Point) -> list[str]:
    return [RESONANCE_FLAG] if abs(2.0 * p.m_chi - M_H) < 4.0 else []


class HiggsPortalScalar(Portal):
    """Real singlet scalar dark matter, V ⊃ ½ λ_hs S² H†H (g_χ is λ_hs)."""

    family: Literal["higgs_portal_scalar"] = "higgs_portal_scalar"
    LABELS: ClassVar[dict[str, str]] = {"m_chi": "m_S (GeV)", "g_chi": "λ_hs"}
    SPIN: ClassVar[float] = 0.0
    SELF_CONJUGATE: ClassVar[bool] = True

    def flags(self, p: Point) -> list[str]:
        """The Higgs-resonance warning (``RESONANCE_FLAG``) where m_DM is within 2 GeV of m_h/2."""
        return _resonance_flags(p)

    def today_hadronic(self, p: Point) -> str:
        """Why the quark pairs' annihilation today is not computed (``_today_hadronic``), or ""."""
        return _today_hadronic(p)

    def invisible(self, p: Point) -> dict[str, float]:
        """Γ(h → SS) = λ_hs² v² β/(32π m_h) in GeV, below m_S = m_h/2."""
        if 2.0 * p.m_chi >= M_H:
            return {}
        return {"h": p.g_chi ** 2 * V ** 2 * _beta(p.m_chi, M_H) / (32.0 * math.pi * M_H)}

    def width_h(self, p: Point) -> float:
        """The Higgs boson's total width (GeV): the Standard Model's plus Γ(h → SS)."""
        return higgs.GAMMA_H + self.invisible(p).get("h", 0.0)

    def resonances(self, p: Point) -> list[tuple[float, float]]:
        """The 125 GeV Higgs pole with its total width (``width_h``)."""
        return [(M_H, self.width_h(p))]

    def domain(self, p: Point) -> str:
        """Ωh² is not computed below m_DM = 2 GeV, where the off-shell Higgs boson's hadronic channels are not
        modelled."""
        return ("m_DM below 2 GeV (√s ≈ 2m_DM below 4 GeV): the hadronic channels of an off-shell Higgs boson are not "
                "modelled") if p.m_chi < LIGHT_LIMIT_GEV else ""

    def perturbative(self, p: Point) -> bool:
        """|λ_hs| ≤ 4π."""
        return abs(p.g_chi) <= 4.0 * math.pi

    def channels(self, s, p: Point) -> dict[str, np.ndarray]:
        """SS → Standard Model final states through the off-shell Higgs boson, and SS → hh from contact, s-channel h
        and t/u-channel S exchange."""
        lam, gamma = p.g_chi, self.width_h(p)
        out = _standard_model(s, p.m_chi, "scalar", [(lam * V, 0.0)], [1.0], [Mediator(M_H, gamma)])

        def hh(ss: float) -> float:
            contact = lam * (1.0 + 3.0 * M_H ** 2 * _propagator(ss, M_H, gamma))
            return processes.scalars_to_scalars(ss, p.m_chi, M_H, contact, lam * V, p.m_chi)
        out["hh"] = tabulated(("hps_hh", p.m_chi, lam), hh, p.m_chi, 2.0 * M_H, s)
        return out

    def nucleon(self, p: Point) -> Nucleon:
        """Spin-independent and isoscalar: c₁ = λ_hs f_N m_N/(2m_h² m_S)."""
        c = p.g_chi * F_N * M_NUCLEON / (2.0 * M_H ** 2 * p.m_chi)
        return Nucleon(c1_p=c, c1_n=c)


class HiggsPortalFermion(Portal):
    """Singlet fermion dark matter, (λ_hχ/Λ) χ̄(cos ξ + i sin ξ γ⁵)χ H†H (g_χ is λ_hχ/Λ in GeV⁻¹)."""

    family: Literal["higgs_portal_fermion"] = "higgs_portal_fermion"
    majorana: bool = False
    xi: float = 0.0                       # the CP phase: 0 scalar, π/2 pseudoscalar
    LABELS: ClassVar[dict[str, str]] = {"m_chi": "m_χ (GeV)", "g_chi": "λ_hχ/Λ (GeV⁻¹)"}

    def self_conjugate(self) -> bool:
        """True for Majorana dark matter."""
        return self.majorana

    def _yukawa(self, p: Point) -> tuple[float, float]:
        y = p.g_chi * V
        return y * math.cos(self.xi), y * math.sin(self.xi)

    def flags(self, p: Point) -> list[str]:
        """The Higgs-resonance warning (``RESONANCE_FLAG``) where m_DM is within 2 GeV of m_h/2."""
        return _resonance_flags(p)

    def today_hadronic(self, p: Point) -> str:
        """Why the quark pairs' annihilation today is not computed (``_today_hadronic``), or ""."""
        return _today_hadronic(p)

    def invisible(self, p: Point) -> dict[str, float]:
        """Γ(h → χχ̄) = m_h(y_s²β³ + y_p²β)/(8π), (y_s, y_p) = (λ_hχ/Λ)v(cos ξ, sin ξ), halved for Majorana; below
        m_χ = m_h/2."""
        if 2.0 * p.m_chi >= M_H:
            return {}
        ys, yp = self._yukawa(p)
        b = _beta(p.m_chi, M_H)
        width = M_H * (ys * ys * b ** 3 + yp * yp * b) / (8.0 * math.pi)
        return {"h": 0.5 * width if self.majorana else width}

    def width_h(self, p: Point) -> float:
        """The Higgs boson's total width (GeV): the Standard Model's plus Γ(h → χχ̄)."""
        return higgs.GAMMA_H + self.invisible(p).get("h", 0.0)

    def resonances(self, p: Point) -> list[tuple[float, float]]:
        """The 125 GeV Higgs pole with its total width (``width_h``)."""
        return [(M_H, self.width_h(p))]

    def domain(self, p: Point) -> str:
        """Ωh² is not computed below m_DM = 2 GeV, where the off-shell Higgs boson's hadronic channels are not
        modelled."""
        return ("m_DM below 2 GeV (√s ≈ 2m_DM below 4 GeV): the hadronic channels of an off-shell Higgs boson are not "
                "modelled") if p.m_chi < LIGHT_LIMIT_GEV else ""

    def perturbative(self, p: Point) -> bool:
        """The EFT holds while its scale exceeds the annihilation energy: (λ/Λ)·2m_χ < 4π (GAMBIT's choice)."""
        return abs(p.g_chi) * 2.0 * p.m_chi < 4.0 * math.pi

    def channels(self, s, p: Point) -> dict[str, np.ndarray]:
        """χχ̄ → Standard Model final states through the off-shell Higgs boson (CP phase ξ), and χχ̄ → hh from t- and
        u-channel χ exchange plus the contact and s-channel h terms."""
        ys, yp = self._yukawa(p)
        gamma = self.width_h(p)
        out = _standard_model(s, p.m_chi, "fermion", [(ys, yp)], [1.0], [Mediator(M_H, gamma)])
        cs, cp = p.g_chi * math.cos(self.xi), p.g_chi * math.sin(self.xi)

        def hh(ss: float) -> float:
            k = 1.0 + 3.0 * M_H ** 2 * _propagator(ss, M_H, gamma)
            return processes.fermion_to_scalars(ss, p.m_chi, M_H, M_H, (ys, yp), (ys, yp), (cs * k, cp * k),
                                                identical=True)
        out["hh"] = tabulated(("hpf_hh", p.m_chi, p.g_chi, self.xi, self.majorana), hh, p.m_chi, 2.0 * M_H, s)
        return out

    def nucleon(self, p: Point) -> Nucleon:
        """Spin-independent from the CP-even coupling, c₁ = y_s f_N m_N/(v m_h²); momentum-suppressed for a pure
        pseudoscalar coupling."""
        ys, _ = self._yukawa(p)
        if abs(ys) < 1e-12 * abs(p.g_chi * V or 1.0):
            return Nucleon(suppressed="momentum-suppressed (a pseudoscalar coupling)")
        c = ys * F_N * M_NUCLEON / (V * M_H ** 2)
        return Nucleon(c1_p=c, c1_n=c)


class HiggsPortalVector(Portal):
    """Real vector dark matter, L ⊃ ½ λ_hV V_μV^μ H†H (g_χ is λ_hV)."""

    family: Literal["higgs_portal_vector"] = "higgs_portal_vector"
    LABELS: ClassVar[dict[str, str]] = {"m_chi": "m_V (GeV)", "g_chi": "λ_hV"}
    SPIN: ClassVar[float] = 1.0
    SELF_CONJUGATE: ClassVar[bool] = True

    def flags(self, p: Point) -> list[str]:
        """The Higgs-resonance warning (``RESONANCE_FLAG``) where m_DM is within 2 GeV of m_h/2."""
        return _resonance_flags(p)

    def today_hadronic(self, p: Point) -> str:
        """Why the quark pairs' annihilation today is not computed (``_today_hadronic``), or ""."""
        return _today_hadronic(p)

    def invisible(self, p: Point) -> dict[str, float]:
        """Γ(h → VV) = λ_hV² v² m_h³ β(1 − 4x + 12x²)/(128π m_V⁴), x = m_V²/m_h², below m_V = m_h/2."""
        if 2.0 * p.m_chi >= M_H:
            return {}
        x = (p.m_chi / M_H) ** 2
        return {"h": p.g_chi ** 2 * V ** 2 * M_H ** 3 * _beta(p.m_chi, M_H) * (1 - 4 * x + 12 * x * x)
                / (128.0 * math.pi * p.m_chi ** 4)}

    def width_h(self, p: Point) -> float:
        """The Higgs boson's total width (GeV): the Standard Model's plus Γ(h → VV)."""
        return higgs.GAMMA_H + self.invisible(p).get("h", 0.0)

    def resonances(self, p: Point) -> list[tuple[float, float]]:
        """The 125 GeV Higgs pole with its total width (``width_h``)."""
        return [(M_H, self.width_h(p))]

    def domain(self, p: Point) -> str:
        """Ωh² is not computed below m_DM = 2 GeV, where the off-shell Higgs boson's hadronic channels are not
        modelled."""
        return ("m_DM below 2 GeV (√s ≈ 2m_DM below 4 GeV): the hadronic channels of an off-shell Higgs boson are not "
                "modelled") if p.m_chi < LIGHT_LIMIT_GEV else ""

    def perturbative(self, p: Point) -> bool:
        """|λ_hV| ≤ 4π."""
        return abs(p.g_chi) <= 4.0 * math.pi

    def channels(self, s, p: Point) -> dict[str, np.ndarray]:
        """VV → Standard Model final states through the off-shell Higgs boson, and VV → hh from contact, s-channel h
        and t/u-channel V exchange."""
        lam, gamma = p.g_chi, self.width_h(p)
        out = _standard_model(s, p.m_chi, "vector", [(lam * V, 0.0)], [1.0], [Mediator(M_H, gamma)])

        def hh(ss: float) -> float:
            contact = lam * (1.0 + 3.0 * M_H ** 2 * _propagator(ss, M_H, gamma))
            return processes.vectors_to_scalars(ss, p.m_chi, M_H, contact, lam * V)
        out["hh"] = tabulated(("hpv_hh", p.m_chi, lam), hh, p.m_chi, 2.0 * M_H, s)
        return out

    def nucleon(self, p: Point) -> Nucleon:
        """Spin-independent and isoscalar: c₁ = λ_hV f_N m_N/(2m_h² m_V)."""
        c = p.g_chi * F_N * M_NUCLEON / (2.0 * M_H ** 2 * p.m_chi)
        return Nucleon(c1_p=c, c1_n=c)


def _standard_model_width(m: float) -> float:
    """A Higgs boson's width into Standard Model states at mass m: the SM table (``higgs.width``) from
    ``higgs.WIDTH_FROM``; below it the open charged leptons' (``higgs.leptonic_width``: no hadron is open below 2m_π,
    and above it the hadronic part is not computed, ``SingletMixing.light_reason``), never the table's zero."""
    return float(higgs.width(m)) if m >= higgs.WIDTH_FROM else higgs.leptonic_width(m)


class SingletMixing(Portal):
    """Dirac fermion dark matter and a singlet scalar mixing with the Higgs boson.

    L ⊃ −y χ̄(1 or iγ⁵)χ s, with the mass eigenstates h₁ (125 GeV) = cos θ h + sin θ s and
    h₂ = −sin θ h + cos θ s: h₁ couples to χ with y sin θ and to the Standard Model with
    cos θ (× the Higgs boson's couplings), h₂ with y cos θ and −sin θ. Slots: m_med = m₂,
    g_χ = y, g_q = sin θ. The scalar potential's trilinear couplings (h₂ → h₁h₁, and the
    s-channel parts of χχ̄ → h_ih_j) depend on parameters this model leaves free and are
    set to zero.
    """

    family: Literal["singlet_mixing"] = "singlet_mixing"
    dm_pseudoscalar: bool = False
    LABELS: ClassVar[dict[str, str]] = {"m_chi": "m_χ (GeV)", "m_med": "m₂ (GeV)", "g_chi": "y_χ",
                                        "g_q": "sin θ"}

    def _mixing(self, p: Point) -> tuple[float, float]:
        sin_t = max(min(p.g_q, 1.0), -1.0)
        return sin_t, math.sqrt(1.0 - sin_t * sin_t)

    def _yukawas(self, p: Point) -> list[tuple[float, float]]:
        sin_t, cos_t = self._mixing(p)
        return [(0.0, p.g_chi * sin_t), (0.0, p.g_chi * cos_t)] if self.dm_pseudoscalar else \
            [(p.g_chi * sin_t, 0.0), (p.g_chi * cos_t, 0.0)]

    def _to_dm(self, mass: float, coupling: tuple[float, float], m: float) -> float:
        if 2.0 * m >= mass:
            return 0.0
        b = _beta(m, mass)
        return mass * (coupling[0] ** 2 * b ** 3 + coupling[1] ** 2 * b) / (8.0 * math.pi)

    def mediators(self, p: Point) -> list[Mediator]:
        """h₁ (125 GeV) and h₂ (m₂) with their widths: a Higgs boson's Standard Model width at that mass scaled by
        cos²θ or sin²θ (``_standard_model_width``), plus the decays into χχ̄."""
        sin_t, cos_t = self._mixing(p)
        y1, y2 = self._yukawas(p)
        return [Mediator(M_H, cos_t ** 2 * higgs.GAMMA_H + self._to_dm(M_H, y1, p.m_chi)),
                Mediator(p.m_med, sin_t ** 2 * _standard_model_width(p.m_med) + self._to_dm(p.m_med, y2, p.m_chi))]

    def light_reason(self, p: Point, fixed: bool = False) -> str:
        """Why h₂'s width below the SM table, or in the hadronic window, decides what is computed, or "" (the RZ23
        re-audit's RF23-02, 2026-10-23: the table's zero below 2 GeV had been h₂'s width, its open muon decay erased),
        as the generic route has the same scalar (``generic._light_higgs``, ``generic_hadronic.propagator_reason``):
        - **mostly the SM doublet** (sin²θ > ½) below ``higgs.WIDTH_FROM``: no SM-like width or hadronic prescription;
        - **mostly the singlet**, its mass in the hadronic window (2m_π to 3 GeV for its CP-even current): its hadronic
          width is not computed, bounded by 0 ≤ Γ_had ≤ m₂, and decides where it can move the s-channel propagator at
          √s ≥ 2m_χ (at s = 4m_χ² alone, ``fixed``: annihilation today)."""
        from adroit.constraints import hadronic_window as hw
        sin_t, _ = self._mixing(p)
        if not sin_t or p.m_med <= 0:
            return ""
        if sin_t ** 2 > 0.5:
            if p.m_med >= higgs.WIDTH_FROM:
                return ""
            return (f"the scalar h₂ at {p.m_med:.4g} GeV is mostly the SM doublet (sin²θ = {sin_t ** 2:.3g}): below "
                    f"{higgs.WIDTH_FROM:g} GeV ADROIT has no SM-like width or hadronic prescription for it; not computed")
        if hw.state(p.m_med) != hw.UNKNOWN:
            return ""
        width = self.mediators(p)[1].width
        if hw.propagator_insensitive(4.0 * p.m_chi ** 2, p.m_med, width + p.m_med, fixed=fixed):
            return ""
        return f"{hw.decay_reason('h₂', p.m_med, False, False)}, and it moves the s-channel propagator"

    def flags(self, p: Point) -> list[str]:
        """The Higgs-resonance warning (``RESONANCE_FLAG``) where m_DM is within 2 GeV of m_h/2."""
        return _resonance_flags(p)

    def today_hadronic(self, p: Point) -> str:
        """Why the quark pairs' annihilation today is not computed (``_today_hadronic``), or ""."""
        return _today_hadronic(p)

    def invisible(self, p: Point) -> dict[str, float]:
        """Γ(h₁ → χχ̄) (GeV) through the coupling y sin θ, where open."""
        width = self._to_dm(M_H, self._yukawas(p)[0], p.m_chi)
        return {"h": width} if width else {}

    def higgs_coupling_scale(self, p: Point) -> float:
        """cos²θ: the 125 GeV state's Standard Model production and width relative to the Higgs boson's."""
        return self._mixing(p)[1] ** 2

    def resonances(self, p: Point) -> list[tuple[float, float]]:
        """The h₁ and h₂ poles with their widths (``mediators``)."""
        return [(md.mass, md.width) for md in self.mediators(p)]

    def domain(self, p: Point) -> str:
        """Ωh² is not computed below m_DM = 2 GeV, where the off-shell Higgs boson's hadronic channels are not
        modelled, nor where h₂'s light width decides it (``light_reason``)."""
        if p.m_chi < LIGHT_LIMIT_GEV:
            return ("m_DM below 2 GeV (√s ≈ 2m_DM below 4 GeV): the hadronic channels of an off-shell Higgs boson are "
                    "not modelled")
        return self.light_reason(p)

    def today_unknown(self, p: Point) -> str:
        """Why annihilation today is not computed at all: h₂'s light width deciding it at s = 4m_χ² (``light_reason``)."""
        return self.light_reason(p, fixed=True)

    def pending(self, p: Point) -> list[str]:
        """Nothing: the Higgs signal strength, ATLAS's ZZ and WW resonance searches and SModelS's (monojet, dijets) are
        in ``searches``; h₂ → h₁h₁ is absent (the trilinear couplings are set to zero)."""
        return []

    def channels(self, s, p: Point) -> dict[str, np.ndarray]:
        """χχ̄ → Standard Model final states through h₁ and h₂, and χχ̄ → h₁h₁, h₁h₂, h₂h₂ from t- and u-channel χ
        exchange."""
        sin_t, cos_t = self._mixing(p)
        meds = self.mediators(p)
        ys = self._yukawas(p)
        out = _standard_model(s, p.m_chi, "fermion", ys, [cos_t, -sin_t], meds)
        masses = {"h1": M_H, "h2": p.m_med}
        couplings = {"h1": ys[0], "h2": ys[1]}
        for a, b in (("h1", "h1"), ("h1", "h2"), ("h2", "h2")):
            def pair(ss: float, a=a, b=b) -> float:
                return processes.fermion_to_scalars(ss, p.m_chi, masses[a], masses[b], couplings[a], couplings[b],
                                                    identical=a == b)
            key = ("mix", a + b, p.m_chi, p.m_med, p.g_chi, p.g_q, self.dm_pseudoscalar)
            out[a + b] = tabulated(key, pair, p.m_chi, masses[a] + masses[b], s)
        return out

    def nucleon(self, p: Point) -> Nucleon:
        """Spin-independent: c₁ = y sin θ cos θ f_N m_N/v (1/m₁² − 1/m₂²); momentum-suppressed for a pseudoscalar
        coupling."""
        if self.dm_pseudoscalar:
            return Nucleon(suppressed="momentum-suppressed (a pseudoscalar coupling)")
        sin_t, cos_t = self._mixing(p)
        c = p.g_chi * sin_t * cos_t * F_N * M_NUCLEON / V * (1.0 / M_H ** 2 - 1.0 / p.m_med ** 2)
        return Nucleon(c1_p=c, c1_n=c)
