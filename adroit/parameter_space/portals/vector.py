"""Vector portals: a new or Standard Model neutral vector boson between dark matter and quarks or leptons.

- ``DarkPhoton``: a dark U(1) kinetically mixed with hypercharge (ε), its gauge boson
  A′ of mass m_A′, dark matter a Dirac fermion or a complex scalar of charge g_D
  (Holdom; Pospelov, Ritz & Voloshin arXiv:0711.4866; the thermal targets of
  Izaguirre, Krnjaic, Schuster & Toro arXiv:1505.00011). Slots: m_med = m_A′,
  g_χ = g_D, g_q = ε. The photon, Z and A′ are diagonalised exactly
  (``constraints.kinetic_mixing``); annihilation goes through both the Z and the
  A′, interfering, and into A′A′ when m_χ > m_A′.
- ``InelasticDarkPhoton``: pseudo-Dirac dark matter, two Majorana states split by
  δ = Δ m_χ, coupling off-diagonally to the A′ (Tucker-Smith & Weiner
  hep-ph/0101138; Izaguirre, Krnjaic & Shuve arXiv:1508.03050). Coannihilation
  χ₁χ₂ → f f̄ sets the relic density. Slot g_ℓ = Δ.
- ``ZPortal``: dark matter coupling to the Standard Model Z, vector or axial,
  Dirac or Majorana (Arcadi, Mambrini & Richard arXiv:1411.2985; Escudero,
  Berlin, Hooper & Lin arXiv:1609.09079). Annihilation into f f̄, W⁺W⁻ and Zh.
- ``ChargedZPrime``: the gauge boson of an anomaly-free U(1) that the Standard
  Model carries: B − L (with three right-handed neutrinos, taken heavy) or
  L_μ − L_τ, with Dirac dark matter. Slots: g_χ = the dark matter's coupling,
  g_q = the gauge coupling g′. For L_μ − L_τ the loop of μ and τ gives a kinetic
  mixing with the photon, ε = −(e g′/12π²) ln(m_τ²/m_μ²), through which it meets
  nucleons.

All couplings are at the level of the Feynman rule: a Majorana Lagrangian
written with ½ has the same rule as a Dirac one.
"""

from __future__ import annotations

import math
from typing import ClassVar, Literal

import numpy as np

from adroit.constraints import annihilation, exchange, hadrons as had, kinetic_mixing as km, processes, spin1
from adroit.constraints.exchange import Mediator
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.base import Nucleon, Portal, tabulated

FERMIONS = {f.name: f for f in spin1.FERMIONS}
HADRONIC_LIMIT_GEV = 1.0       # below: hadronic final states from the measured R ratio (``constraints.hadrons``)
LIGHTEST_GEV = 0.01            # below: the dark matter is in equilibrium during BBN (not computed)
LIGHT_QUARKS = ("u", "d", "s")
LIGHT_MEDIATOR_GEV = 1.0       # below: the momentum dependence of scattering is not in the envelope comparison
M_W, M_H = 80.37, 125.09
G_ZZH = 2.0 * km.M_Z ** 2 / 246.22
M_ELECTRON = 0.000511
CONVERSION_X_F = 20.0          # the inelastic χ₂'s freeze-out x for its conversion check (declared, as x_f ≈ 20)
G_ZWW = km.G * km.COS_W


def _hadron_coupling(f_couplings: dict, kind: str, i: int) -> float:
    """Mediator i's coupling for the hadron ratio: a_u − a_d (= εe, photon-like), or the muon's (baryonic)."""
    if kind == "photon":
        return f_couplings["u"][i][0] - f_couplings["d"][i][0]
    return f_couplings["mu"][i][0]


def _hadronic(s, m: float, dm: str, dm_couplings: list, f_couplings: dict, mediators: list, kind: str) -> np.ndarray:
    """σ(χχ̄ → hadrons) below 2 GeV: σ(→ μμ) × R (``constraints.hadrons``)."""
    root = np.sqrt(np.asarray(s, dtype=float))
    g = [(_hadron_coupling(f_couplings, kind, i), 0.0) for i in range(len(mediators))]
    if kind == "photon":
        muons = exchange.vector_to_fermions(s, m, dm, dm_couplings, 0.0, 1, g, mediators)
        return muons * had.r_ratio(root)
    muons = exchange.vector_to_fermions(s, m, dm, dm_couplings, FERMIONS["mu"].mass_gev, 1, g, mediators)
    return muons * had.baryonic_ratio(root)


def _to_fermions(s, m: float, dm: str, dm_couplings: list, f_couplings: dict[str, list],
                 mediators: list[Mediator], hadrons: str | None = None) -> dict[str, np.ndarray]:
    """σ by final state; with ``hadrons`` ("photon" or "baryonic"), u d s become hadrons below 2 GeV."""
    out = {}
    s = np.asarray(s, dtype=float)
    light = (np.sqrt(s) < had.LIGHT_GEV) if hadrons else np.zeros(s.shape, dtype=bool)
    for name, f in FERMIONS.items():
        sigma = exchange.vector_to_fermions(s, m, dm, dm_couplings, f.mass_gev, f.colours, f_couplings[name], mediators)
        if hadrons and name in LIGHT_QUARKS:
            sigma = np.where(light, 0.0, sigma)
        key = "nu" if f.family == "neutrino" else name
        out[key] = out.get(key, 0.0) + sigma
    if hadrons and np.any(light):
        out["hadrons"] = np.where(light, _hadronic(s, m, dm, dm_couplings, f_couplings, mediators, hadrons), 0.0)
    return out


def _width(mass: float, fermions: dict[str, tuple[float, float]], dark: tuple[float, float], m_dm: float,
           dm: str, self_conjugate: bool = False, hadrons: str | None = None) -> float:
    light = hadrons is not None and mass < had.LIGHT_GEV
    total = sum(spin1.partial_width(mass, f.mass_gev, f.colours, *fermions[f.name]) for f in spin1.FERMIONS
                if not (light and f.name in LIGHT_QUARKS))
    if light:
        g = _hadron_coupling({k: [v] for k, v in fermions.items()}, hadrons, 0)
        if hadrons == "photon":
            total += had.muon_width(mass, g, massless=True) * float(had.r_ratio(np.array([mass]))[0])
        else:
            total += had.muon_width(mass, g) * float(had.baryonic_ratio(np.array([mass]))[0])
    if 2.0 * m_dm < mass:
        if dm == "complex_scalar":
            beta = math.sqrt(1.0 - 4.0 * m_dm ** 2 / mass ** 2)
            total += dark[0] ** 2 * mass * beta ** 3 / (48.0 * math.pi)
        else:
            to_dm = spin1.partial_width(mass, m_dm, 1, *dark)
            total += 0.5 * to_dm if self_conjugate else to_dm
    return total


def _light_domain(p: Point, kind: str) -> str:
    """Why Ωh² is not computed for light dark matter (nothing above 10 MeV once the hadron data are fetched)."""
    if p.m_chi >= HADRONIC_LIMIT_GEV:
        return ""
    if p.m_chi < LIGHTEST_GEV:
        return "below 10 MeV the dark matter is in equilibrium during BBN, which is not computed"
    from adroit.constraints.searches import _tool
    present = had.available() if kind == "photon" else _tool("DarkCast") is not None
    return "" if present else ("m_χ below 1 GeV (√s ≈ 2m_χ below 2 GeV): the hadronic final states need the measured "
                               "R ratio (the PDG's file, or DarkCast for B − L): adroit setup --fetch")


class DarkPhoton(Portal):
    """Dark matter charged under a kinetically mixed dark U(1) (slots: m_med = m_A′, g_χ = g_D, g_q = ε)."""

    family: Literal["dark_photon"] = "dark_photon"
    scalar_dm: bool = False                  # a complex scalar instead of a Dirac fermion
    LABELS: ClassVar[dict[str, str]] = {"m_chi": "m_χ (GeV)", "m_med": "m_A′ (GeV)", "g_chi": "g_D", "g_q": "ε"}

    def spin(self) -> float:
        """0 for complex scalar dark matter, ½ for a Dirac fermion."""
        return 0.0 if self.scalar_dm else 0.5

    def _dm(self) -> str:
        return "complex_scalar" if self.scalar_dm else "fermion"

    def bosons(self, p: Point) -> tuple[list[Mediator], list[tuple[float, float]], dict[str, list]]:
        """The Z and A′ after exact diagonalisation (``kinetic_mixing.couplings``): the mediators (the Z's measured
        width plus its decays into dark matter; the A′'s computed width), the dark matter's couplings and each
        fermion's (vector, axial) couplings, in the order (Z, A′)."""
        c = km.couplings(p.m_med, p.g_q, p.g_chi)
        mediators, dark, fermions = [], [], {name: [] for name in FERMIONS}
        for label in ("Z", "A'"):
            d = (c[label]["dark"], 0.0)
            base = km.GAMMA_Z if label == "Z" else 0.0
            extra = _width(c[label]["mass"], c[label]["fermions"], d, p.m_chi, self._dm(), hadrons="photon")
            if label == "Z":                      # the measured width, plus decays into dark matter
                sm_only = _width(c[label]["mass"], c[label]["fermions"], (0.0, 0.0), 1e9, self._dm(), hadrons="photon")
                extra = base + extra - sm_only
            mediators.append(Mediator(c[label]["mass"], extra))
            dark.append(d)
            for name in FERMIONS:
                fermions[name].append(c[label]["fermions"][name])
        return mediators, dark, fermions

    def resonances(self, p: Point) -> list[tuple[float, float]]:
        """The Z and A′ poles with their widths (``bosons``)."""
        return [(md.mass, md.width) for md in self.bosons(p)[0]]

    def invisible(self, p: Point) -> dict[str, float]:
        """Γ(Z → dark matter) (GeV) through the mixing, where open."""
        meds, dark, _ = self.bosons(p)
        if 2.0 * p.m_chi >= meds[0].mass:
            return {}
        if self.scalar_dm:
            beta = math.sqrt(1.0 - 4.0 * p.m_chi ** 2 / meds[0].mass ** 2)
            return {"Z": dark[0][0] ** 2 * meds[0].mass * beta ** 3 / (48.0 * math.pi)}
        return {"Z": spin1.partial_width(meds[0].mass, p.m_chi, 1, *dark[0])}

    def domain(self, p: Point) -> str:
        """Light dark matter's limits (``_light_domain``): BBN below 10 MeV, and the measured R ratio needed below 1
        GeV."""
        return _light_domain(p, "photon")

    def pending(self, p: Point) -> list[str]:
        """What applies but is not computed (dark-photon searches and the CMB are, in ``searches``)."""
        if p.m_med < LIGHT_MEDIATOR_GEV:
            return ["direct detection: a light mediator's momentum dependence is not in the envelope comparison"]
        return []

    def channels(self, s, p: Point) -> dict[str, np.ndarray]:
        """χχ̄ → f f̄ through the interfering Z and A′ (hadrons from the R ratio below 2 GeV), and → A′A′ for m_χ >
        m_A′/2."""
        meds, dark, fermions = self.bosons(p)
        out = _to_fermions(s, p.m_chi, self._dm(), dark, fermions, meds, hadrons="photon")
        if p.m_chi > meds[1].mass * 0.5:          # A′A′ (open above m_χ = m_A′, forbidden tail below)
            g = dark[1][0]
            if self.scalar_dm:
                def pair(ss: float) -> float:
                    return processes.scalars_to_massive_vectors(ss, p.m_chi, meds[1].mass, g)
                out["A'A'"] = tabulated(("dp_pair_s", p.m_chi, p.m_med, p.g_chi, p.g_q), pair, p.m_chi,
                                        2.0 * meds[1].mass, s)
            else:
                u_nodes, table = annihilation._pair_table(p.m_chi, meds[1].mass, g, 0.0)
                out["A'A'"] = _from_pair_table(s, p.m_chi, u_nodes, table)
        return out

    def nucleon(self, p: Point) -> Nucleon:
        """Spin-independent: c₁ for protons and neutrons summed over Z and A′ exchange, g_χ a_N/m²."""
        meds, dark, fermions = self.bosons(p)
        c_p = c_n = 0.0
        for i, md in enumerate(meds):
            a_p, a_n = km.nucleon_vector({k: v[i] for k, v in fermions.items()})
            c_p += dark[i][0] * a_p / md.mass ** 2
            c_n += dark[i][0] * a_n / md.mass ** 2
        return Nucleon(c1_p=c_p, c1_n=c_n)


def _from_pair_table(s, m: float, u_nodes: np.ndarray, table: np.ndarray) -> np.ndarray:
    s = np.asarray(s, dtype=float)
    u = np.sqrt(s) / (2.0 * m) - 1.0
    beta = np.sqrt(np.clip(1.0 - 4.0 * m * m / np.maximum(s, 1e-300), 0.0, None))
    smooth = np.interp(np.clip(u, u_nodes[0], u_nodes[-1]), u_nodes, table)
    return np.where((u > u_nodes[0]) & (beta > 0), smooth / np.where(beta > 0, beta, 1.0), 0.0)


class InelasticDarkPhoton(DarkPhoton):
    """Pseudo-Dirac dark matter: χ₁, χ₂ = χ₁ + Δ m_χ, coupling off-diagonally to the A′ (slot g_ℓ = Δ)."""

    family: Literal["inelastic_dark_photon"] = "inelastic_dark_photon"
    LABELS: ClassVar[dict[str, str]] = {"m_chi": "m_χ₁ (GeV)", "m_med": "m_A′ (GeV)", "g_chi": "g_D", "g_q": "ε",
                                        "g_l": "Δ = δ/m_χ₁"}
    SELF_CONJUGATE: ClassVar[bool] = True

    def domain(self, p: Point) -> str:
        """Not computed below m_A′ = 2m_χ₁(1 + Δ) (on-shell A′ and A′A′); otherwise the dark photon's light-mass
        limits."""
        if p.m_med < 2.0 * p.m_chi * (1.0 + p.g_l):
            return "the A′ below 2m_χ₁ (on-shell A′ and A′A′ channels) is not computed for the inelastic model"
        return super().domain(p)

    def pending(self, p: Point) -> list[str]:
        """The dark photon's, plus inelastic direct detection (compared through Path 1 only), and the coannihilation
        relic's chemical equilibrium where it is not certified (``conversion_reason``)."""
        out = super().pending(p) + ["direct detection: inelastic scattering (δ) is compared through Path 1 "
                                    "only (adroit lagrangian / exclude with the splitting)"]
        why = self.conversion_reason(p)
        return out + ([f"coannihilation chemical equilibrium not certified: {why}"] if why else [])

    def conversion_reason(self, p: Point) -> str:
        """Why χ₂'s chemical equilibrium with χ₁, which the coannihilation relic assumes, is not certified, or "" (the
        owner's decision #5, 2026-10-20, on the library's route as on the generic one). χ₂ → χ₁ e⁺e⁻ through the
        off-shell A′, at leading order in δ/m_χ and δ/m_A′, Γ = 4ε²αα_D δ⁵/(15π m_A′⁴) (α at the Thomson limit, as
        ε; electrons alone, and the propagator's growth with q² left out: a lower bound on the conversion rate), must
        exceed ``generic_checks.CONTACT`` × H at χ₂'s freeze-out, T = m_χ₂/``CONVERSION_X_F``."""
        from adroit.parameter_space.portals import generic_checks as gc
        delta = p.g_l * p.m_chi
        if delta <= 2 * M_ELECTRON:
            return f"δ = {delta:.3g} GeV is below 2m_e: χ₂ has no tree-level decay to χ₁"
        alpha, alpha_d = km.E_THOMSON ** 2 / (4 * math.pi), p.g_chi ** 2 / (4 * math.pi)
        rate = 4 * p.g_q ** 2 * alpha * alpha_d * delta ** 5 / (15 * math.pi * p.m_med ** 4)
        temperature = p.m_chi * (1 + p.g_l) / CONVERSION_X_F
        limit = gc.CONTACT * gc.hubble(temperature)
        if rate >= limit:
            return ""
        return (f"χ₂ → χ₁ e⁺e⁻ at {rate:.2g} GeV, below {gc.CONTACT:g} H = {limit:.2g} GeV at its freeze-out "
                f"(T = {temperature:.3g} GeV); scatterings are not computed on this route")

    def dd(self, p: Point) -> tuple[str, float]:
        """No elastic scattering: (inelastic, 0); the splitting makes direct detection a Path 1 comparison."""
        return "inelastic", 0.0

    def coannihilation(self, p: Point):
        """χ₁ and χ₂ (Majorana, 2 dof each, m₂ = m_χ₁(1 + Δ)) with σ(χ₁χ₂ → f f̄)(s) through the Z and A′, hadrons
        from the R ratio below 2 GeV."""
        from adroit.constraints import relic
        meds, dark, fermions = self.bosons(p)
        m1, m2 = p.m_chi, p.m_chi * (1.0 + p.g_l)

        def sigma_12(s):
            out, light = 0.0, np.sqrt(np.asarray(s, dtype=float)) < had.LIGHT_GEV
            for name, f in FERMIONS.items():
                term = exchange.vector_unequal_to_fermions(s, m1, m2, dark, f.mass_gev, f.colours, fermions[name], meds)
                out = out + (np.where(light, 0.0, term) if name in LIGHT_QUARKS else term)
            g = [(_hadron_coupling(fermions, "photon", i), 0.0) for i in range(len(meds))]
            muons = exchange.vector_unequal_to_fermions(s, m1, m2, dark, 0.0, 1, g, meds)
            return out + np.where(light, muons * had.r_ratio(np.sqrt(np.asarray(s, dtype=float))), 0.0)
        return [relic.Species(m1, 2.0), relic.Species(m2, 2.0)], {(0, 1): sigma_12}

    def channels(self, s, p: Point) -> dict[str, np.ndarray]:
        """None: χ₁χ₁ does not annihilate through the A′ (χ₁χ₂ does, in ``coannihilation``)."""
        return {}                                 # χ₁χ₁ does not annihilate through the A′ (today, nothing)


class ZPortal(Portal):
    """Dark matter coupling to the Z boson: −Z_μ χ̄γ^μ(g_V + g_A γ⁵)χ (slot g_χ is g_V or g_A)."""

    family: Literal["z_portal"] = "z_portal"
    coupling: Literal["vector", "axial"] = "vector"
    majorana: bool = False
    LABELS: ClassVar[dict[str, str]] = {"m_chi": "m_χ (GeV)", "g_chi": "g_V^χ"}

    def model_post_init(self, _context) -> None:
        """Refuse Majorana dark matter with a vector coupling (it has no vector current)."""
        if self.majorana and self.coupling == "vector":
            raise ValueError("a Majorana fermion has no vector current")

    def self_conjugate(self) -> bool:
        """True for Majorana dark matter."""
        return self.majorana

    def label(self, slot: str) -> str:
        """g_A^χ for the g_χ slot of an axial coupling; otherwise the class's labels."""
        return "g_A^χ" if slot == "g_chi" and self.coupling == "axial" else super().label(slot)

    def _dark(self, p: Point) -> tuple[float, float]:
        return (p.g_chi, 0.0) if self.coupling == "vector" else (0.0, p.g_chi)

    def _z(self, p: Point) -> tuple[Mediator, dict[str, tuple[float, float]]]:
        fermions = km.couplings(km.M_Z, 0.0, 0.0)["Z"]["fermions"]
        return Mediator(km.M_Z, km.GAMMA_Z + self.invisible(p).get("Z", 0.0)), fermions

    def invisible(self, p: Point) -> dict[str, float]:
        """Γ(Z → χχ̄) (GeV) of the vector or axial coupling, halved for Majorana; below m_χ = m_Z/2."""
        if 2.0 * p.m_chi >= km.M_Z:
            return {}
        width = spin1.partial_width(km.M_Z, p.m_chi, 1, *self._dark(p))
        return {"Z": 0.5 * width if self.majorana else width}

    def resonances(self, p: Point) -> list[tuple[float, float]]:
        """The Z pole with its measured width plus Γ(Z → χχ̄)."""
        z, _ = self._z(p)
        return [(z.mass, z.width)]

    def domain(self, p: Point) -> str:
        """Ωh² is not computed below m_χ = 1 GeV, where the hadronic final states need the R ratio, nor where the
        annihilation into quarks at √s ≈ 2m_χ is in the hadronic window: the Z's quark current is vector and axial,
        not pure vector, so to 3 GeV (the owner's hadronic-validity decision, 2026-10-20)."""
        if p.m_chi < HADRONIC_LIMIT_GEV:
            return ("m_χ below 1 GeV (√s ≈ 2m_χ below 2 GeV): the hadronic final states need the measured R ratio, "
                    "which is not modelled")
        return self.today_hadronic(p)

    def today_hadronic(self, p: Point) -> str:
        """Why the quark pairs' annihilation at √s ≈ 2m_χ is not computed (the hadronic window), or ""."""
        from adroit.constraints import hadronic_window as hw
        if hw.state(2 * p.m_chi, vector=False, annihilation=True) != hw.UNKNOWN:
            return ""
        return hw.annihilation_reason(2 * p.m_chi, False, False)

    def channels(self, s, p: Point) -> dict[str, np.ndarray]:
        """χχ̄ → f f̄, W⁺W⁻ and Zh through the s-channel Z."""
        z, fermions = self._z(p)
        dark = self._dark(p)
        out = _to_fermions(s, p.m_chi, "fermion", [dark], {k: [v] for k, v in fermions.items()}, [z])
        s_ = np.asarray(s, dtype=float)
        beta = np.sqrt(np.clip(1.0 - 4.0 * p.m_chi ** 2 / np.maximum(s_, 1e-300), 0.0, None))
        root = np.sqrt(np.maximum(s_, 1e-300))
        bw = np.sqrt(np.clip(1.0 - 4.0 * M_W ** 2 / np.maximum(s_, 1e-300), 0.0, None))
        x = M_W ** 2 / np.maximum(s_, 1e-300)
        gamma_ww = G_ZWW ** 2 * root / (192.0 * math.pi) * (s_ / M_W ** 2) ** 2 * bw ** 3 * (1 + 20 * x + 12 * x * x)
        inner = (dark[0] ** 2 * (s_ + 2 * p.m_chi ** 2) + dark[1] ** 2 * (s_ - 4 * p.m_chi ** 2)) / np.where(
            beta > 0, root * beta, 1.0)
        prop = 1.0 / ((s_ - z.mass ** 2) ** 2 + (z.mass * z.width) ** 2)
        out["W"] = np.where((beta > 0) & (bw > 0), inner * gamma_ww * prop, 0.0)

        def zh(ss: float) -> float:
            return processes.fermion_to_vector_scalar(ss, p.m_chi, dark, km.M_Z, M_H, G_ZZH, z.mass, z.width)
        out["Zh"] = tabulated(("zp_zh", p.m_chi, p.g_chi, self.coupling, self.majorana), zh, p.m_chi, km.M_Z + M_H, s)
        return out

    def nucleon(self, p: Point) -> Nucleon:
        """Z exchange: c₁ from the vector coupling and c₄ from the axial one, with the quarks' axial charges of
        ``spin1.DMWG_2016``."""
        _, fermions = self._z(p)
        g_v, g_a = self._dark(p)
        a_p, a_n = km.nucleon_vector(fermions)
        n = spin1.DMWG_2016
        b_u, b_d, b_s = fermions["u"][1], fermions["d"][1], fermions["s"][1]
        axial_p = b_u * n.delta_u + b_d * n.delta_d + b_s * n.delta_s
        axial_n = b_u * n.delta_d + b_d * n.delta_u + b_s * n.delta_s
        z2 = km.M_Z ** 2
        return Nucleon(c1_p=g_v * a_p / z2, c1_n=g_v * a_n / z2,
                       c4_p=4.0 * g_a * axial_p / z2, c4_n=4.0 * g_a * axial_n / z2)


CHARGES = {
    "B-L": {"u": 1 / 3, "d": 1 / 3, "s": 1 / 3, "c": 1 / 3, "b": 1 / 3, "t": 1 / 3, "e": -1.0, "mu": -1.0,
            "tau": -1.0, "nu_e": -1.0, "nu_mu": -1.0, "nu_tau": -1.0},
    "Lmu-Ltau": {"mu": 1.0, "nu_mu": 1.0, "tau": -1.0, "nu_tau": -1.0},
}


class ChargedZPrime(Portal):
    """The Z′ of B − L or L_μ − L_τ with Dirac dark matter (slots: m_med = m_Z′, g_χ, g_q = g′)."""

    family: Literal["charged_zprime"] = "charged_zprime"
    charges: Literal["B-L", "Lmu-Ltau"] = "B-L"
    LABELS: ClassVar[dict[str, str]] = {"m_chi": "m_χ (GeV)", "m_med": "m_Z′ (GeV)", "g_chi": "g_χ",
                                        "g_q": "g′"}

    def epsilon(self, p: Point) -> float:
        """The kinetic mixing with the photon from the μ and τ loop (L_μ − L_τ), at q → 0, where the charge is
        e(0) (decision D29, G12: it had been e(m_Z))."""
        if self.charges != "Lmu-Ltau":
            return 0.0
        return -km.E_THOMSON * p.g_q / (12.0 * math.pi ** 2) * math.log((1.77686 / 0.10566) ** 2)

    def fermions(self, p: Point) -> dict[str, tuple[float, float]]:
        """Each Standard Model fermion's (vector, axial) coupling to the Z′: g′ times its charge (neutrinos
        left-handed), plus εeQ for the charged ones from L_μ − L_τ's kinetic mixing."""
        out = {}
        charge_em = {"u": 2 / 3, "c": 2 / 3, "t": 2 / 3, "d": -1 / 3, "s": -1 / 3, "b": -1 / 3, "e": -1.0,
                     "mu": -1.0, "tau": -1.0}
        eps = self.epsilon(p)
        for name, f in FERMIONS.items():
            q = CHARGES[self.charges].get(name, 0.0) * p.g_q
            if f.family == "neutrino":
                out[name] = (0.5 * q, -0.5 * q)          # left-handed only
            else:
                out[name] = (q + eps * km.E_THOMSON * charge_em[name], 0.0)
        return out

    def _hadrons(self) -> str:
        return "baryonic" if self.charges == "B-L" else "photon"

    def mediator(self, p: Point) -> Mediator:
        """The Z′ with its total width: Standard Model fermions (hadrons below 2 GeV) and the dark matter."""
        return Mediator(p.m_med, _width(p.m_med, self.fermions(p), (p.g_chi, 0.0), p.m_chi, "fermion",
                                        hadrons=self._hadrons()))

    def resonances(self, p: Point) -> list[tuple[float, float]]:
        """The Z′ pole with its width (``mediator``)."""
        md = self.mediator(p)
        return [(md.mass, md.width)]

    def domain(self, p: Point) -> str:
        """Light dark matter's limits (``_light_domain``) with the hadronic data of B − L (DarkCast) or of the photon
        (L_μ − L_τ)."""
        return _light_domain(p, self._hadrons())

    def pending(self, p: Point) -> list[str]:
        """What applies but is not computed (LHC dileptons, LEP-II, g − 2, BaBar and Belle II are, in ``searches``)."""
        if self.charges == "B-L":
            return [] if p.m_med >= 209.0 else ["searches below LEP-II's energy (NA64, BaBar, LHCb, CMS dimuons) "
                                                 "recast to B − L: not yet records"]
        return ["BBN and ΔN_eff bound a Z′ below ~10 MeV: not yet records"] if p.m_med < 0.01 else []

    def channels(self, s, p: Point) -> dict[str, np.ndarray]:
        """χχ̄ → f f̄ through the Z′ (hadrons below 2 GeV) and → Z′Z′ for m_χ > m_Z′/2; channels that vanish are
        dropped."""
        md = self.mediator(p)
        out = _to_fermions(s, p.m_chi, "fermion", [(p.g_chi, 0.0)], {k: [v] for k, v in self.fermions(p).items()},
                           [md], hadrons=self._hadrons())
        if p.m_chi > 0.5 * p.m_med:
            u_nodes, table = annihilation._pair_table(p.m_chi, p.m_med, p.g_chi, 0.0)
            out["Z'Z'"] = _from_pair_table(s, p.m_chi, u_nodes, table)
        return {k: v for k, v in out.items() if np.any(v)}

    def nucleon(self, p: Point) -> Nucleon:
        """Spin-independent through Z′ exchange: c₁ = g_χ a_N/m_Z′², a_N the vector coupling to the nucleon."""
        a_p, a_n = km.nucleon_vector(self.fermions(p))
        return Nucleon(c1_p=p.g_chi * a_p / p.m_med ** 2, c1_n=p.g_chi * a_n / p.m_med ** 2)
