"""Capture of dark matter in the Sun, for any nonrelativistic interaction (DM7, tier 2).

A dark matter particle crossing the Sun is captured when a scattering leaves
it slower than the local escape speed (Gould, ApJ 321 (1987) 571). With u
its speed far from the Sun and w² = u² + v_esc(r)² its speed at radius r,

    C = ∫ 4πr² dr Σ_i n_i(r) ∫ du n_χ f_⊙(u) (1/u) ∫ dE_R  w² dσ_i/dE_R (w, E_R) ,

the recoil energy running over the range that removes enough energy,
E_R + δ ≥ m_χ u²/2, and that the kinematics allow at speed w (v_min(E_R) ≤ w,
with v_min including the splitting δ). The cross-section is the rate code's
own (``rates.response_terms``):

    w² dσ/dE_R = m_T/(2π) [P(E_R) + Q(E_R)(w² − v_min²)] ,

so capture uses the same operators, couplings and nuclear responses as direct
detection, inelastic and exothermic scattering included. The nuclear
responses of the sixteen solar elements are those of Catena and Schwabe
(arXiv:1501.03729).

**Inputs.** The Sun is the B16 standard solar model with AGSS09 abundances
(Vinyoles et al., arXiv:1611.09867; fetched by `adroit setup --fetch`, see the
manifest; a calculation never downloads it, and without it a capture-based
verdict is undecided, named as such); each element is its dominant isotope. The halo is seen from the Sun: the Standard Halo
Model boosted by the Sun's velocity alone, or a generated benchmark's table in the Sun's frame (SHM++, halo phase 2).

**Equilibrium.** Captured dark matter annihilates; after the Sun's age t⊙ the
annihilation rate is Γ_A = (C/2) tanh²(t⊙/τ), τ = (C C_A)^{-1/2}, with
C_A = ⟨σv⟩/V_eff and V_eff = 5.8 × 10²⁷ cm³ (100 GeV/m_χ)^{3/2} (Jungman,
Kamionkowski & Griest, Phys. Rept. 267 (1996) 195). Neutrino telescopes quote
limits assuming Γ_A = C/2.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np

from adroit.core.dm_state import DarkMatterParticle, HaloKind, HaloModel, InteractionModel, Isotope
from adroit.core.state import StrictModel
from adroit.external import fetch
from adroit.halo_models.frames import frame_of
from adroit.physics import halo as halos
from adroit.physics import rates
from adroit.physics.conventions import C_KM_S, HBARC_GEV_CM, KEV, nuclear_mass_gev, reduced_mass
from adroit.physics.nuclear import NuclearModel

SOLAR_MODEL = "B16 standard solar model (AGSS09)"
SOLAR_FILE = "struct_b16_agss09.dat"
R_SUN_CM = 6.957e10
M_SUN_G = 1.98841e33
G_CGS = 6.67430e-8
ATOMIC_MASS_G = 1.66053907e-24
C_CM_S = C_KM_S * 1e5
SUN_AGE_S = 4.57e9 * 3.15576e7
UNAVAILABLE = f"the {SOLAR_MODEL} is not in the tools folder: run `adroit setup --fetch`"


class SolarModelUnavailable(RuntimeError):
    """The solar model has not been fetched (a calculation does not fetch it)."""


def available() -> bool:
    """Whether the solar model is in the tools folder."""
    return fetch.locate(SOLAR_MODEL) is not None

# Column of the B16 file → (element, mass number, atomic number, nuclear spin).
SOLAR_ISOTOPES = {
    "H1": ("H", 1, 1, 0.5), "He4": ("He", 4, 2, 0.0), "He3": ("He", 3, 2, 0.5),
    "C12": ("C", 12, 6, 0.0), "N14": ("N", 14, 7, 1.0), "O16": ("O", 16, 8, 0.0),
    "Ne": ("Ne", 20, 10, 0.0), "Na": ("Na", 23, 11, 1.5), "Mg": ("Mg", 24, 12, 0.0),
    "Al": ("Al", 27, 13, 2.5), "Si": ("Si", 28, 14, 0.0), "S": ("S", 32, 16, 0.0),
    "Ar": ("Ar", 40, 18, 0.0), "Ca": ("Ca", 40, 20, 0.0), "Fe": ("Fe", 56, 26, 0.0),
    "Ni": ("Ni", 58, 28, 0.0),
}


class SolarModel(StrictModel):
    """The Sun on a radial grid: shell volumes, escape speed and number densities."""

    radius_cm: list[float]
    shell_volume_cm3: list[float]
    escape_speed: list[float]                    # in units of c
    densities_cm3: dict[str, list[float]]        # isotope name → n_i(r)


def _read_b16(path) -> tuple[list[str], np.ndarray]:
    header, rows = [], []
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            fields = line[1:].split()
            if fields and fields[0] == "Mass":
                header = fields
        elif line.strip():
            rows.append([float(x) for x in line.split()])
    return header, np.array(rows)


def solar_model(points: int = 240) -> SolarModel:
    """The B16 AGSS09 model, resampled at ``points`` radii, with its escape speed profile; the file as it is now
    (``file_reads.stamp``: a replaced model is read again, BI-02).

    Raises:
        SolarModelUnavailable: if it has not been fetched (``adroit setup --fetch``; the fallback review's D3: a
            calculation had downloaded it from the network).
    """
    from adroit.core.file_reads import stamp
    folder = fetch.locate(SOLAR_MODEL)
    if folder is None:
        raise SolarModelUnavailable(UNAVAILABLE)
    return _solar(points, *stamp(folder / SOLAR_FILE))


@lru_cache(maxsize=4)
def _solar(points: int, path: str, size: int, mtime: int, ctime: int) -> SolarModel:
    header, table = _read_b16(Path(path))
    column = {name: i for i, name in enumerate(header)}
    r_frac, m_frac = table[:, column["Radius"]], table[:, column["Mass"]]
    # v_esc² = 2GM⊙/R⊙ + 2∫_r^R G M(r')/r'² dr'; outside the table's last radius M = M⊙.
    r_cm = r_frac * R_SUN_CM
    g_m = G_CGS * M_SUN_G * m_frac / r_cm ** 2
    outer = 2 * G_CGS * M_SUN_G * (1 / r_cm[-1] - 1 / R_SUN_CM) + 2 * G_CGS * M_SUN_G / R_SUN_CM
    tail = np.concatenate([np.cumsum((0.5 * (g_m[1:] + g_m[:-1]) * np.diff(r_cm))[::-1])[::-1], [0.0]])
    v_esc = np.sqrt(outer + 2 * tail) / C_CM_S
    edges = np.linspace(0.0, r_frac[-1], points + 1)
    centres = 0.5 * (edges[1:] + edges[:-1])
    volumes = 4.0 / 3.0 * math.pi * (edges[1:] ** 3 - edges[:-1] ** 3) * R_SUN_CM ** 3
    rho = np.interp(centres, r_frac, table[:, column["Rho"]])
    densities = {}
    for col, (element, a, _, _) in SOLAR_ISOTOPES.items():
        fraction = np.interp(centres, r_frac, table[:, column[col]])
        densities[f"{element}{a}"] = (rho * fraction / (a * ATOMIC_MASS_G)).tolist()
    return SolarModel(radius_cm=(centres * R_SUN_CM).tolist(), shell_volume_cm3=volumes.tolist(),
                      escape_speed=np.interp(centres, r_frac, v_esc).tolist(), densities_cm3=densities)


solar_model.cache_clear = _solar.cache_clear


def isotopes() -> list[Isotope]:
    """The solar isotopes, as the rate code's objects."""
    return [Isotope(element=e, mass_number=a, atomic_number=z, spin=j, mass_fraction=1.0)
            for e, a, z, j in SOLAR_ISOTOPES.values()]


def sun_frame(halo: HaloModel) -> HaloModel:
    """The halo seen from the Sun: a standard halo with the Earth's orbital velocity removed, or a table given in the
    Sun's frame (a generated benchmark's, ``halo_models``). A detector's table is refused: an anisotropic
    distribution's speeds depend on the direction of the boost, and no table is turned into another frame's."""
    if halo.kind is HaloKind.tabulated:
        if frame_of(halo) != "sun":
            raise ValueError(f"{halo.label}: a table in the detector's frame is not the distribution the Sun sees; "
                             "capture needs the Sun-frame table")
        return halo
    return halo.model_copy(update={"v_earth_km_s": (0.0, 0.0, 0.0)})


def recoil_window(w: np.ndarray, m_t: float, mu: float, delta_gev: float) -> tuple[np.ndarray, np.ndarray]:
    """(E₋, E₊) in GeV: the recoil energies with v_min(E_R) ≤ w (w in units of c).

    v_min ≤ w is a quadratic in x = √E_R: (m_T/μ) x² − w√(2m_T) x + δ ≤ 0.
    Empty (E₊ = E₋ = 0) when w² < 2δ/μ; E₋ = 0 for elastic and exothermic scattering.
    """
    root = np.sqrt(2.0 * m_t) * w
    disc = 2.0 * m_t * w * w - 4.0 * (m_t / mu) * delta_gev
    real = disc > 0
    s = np.sqrt(np.where(real, disc, 0.0))
    x_minus = np.clip((root - s) / (2.0 * m_t / mu), 0.0, None)
    x_plus = (root + s) / (2.0 * m_t / mu)
    return np.where(real, x_minus ** 2, 0.0), np.where(real, x_plus ** 2, 0.0)


def _cumulative(y: np.ndarray, x: np.ndarray) -> np.ndarray:
    return np.concatenate([[0.0], np.cumsum(0.5 * (y[1:] + y[:-1]) * np.diff(x))])


def isotope_capture(isotope: Isotope, particle: DarkMatterParticle, interaction: InteractionModel,
                    sun: SolarModel, speeds_c: np.ndarray, flux: np.ndarray,
                    model: NuclearModel = NuclearModel.shell_model) -> float:
    """Captures per second on one isotope; ``flux`` is n_χ f(u) du at the speeds u (units of c)."""
    m, m_t = particle.mass_gev, nuclear_mass_gev(isotope.mass_number)
    mu, delta = reduced_mass(m, m_t), particle.mass_splitting_kev * KEV
    v_esc = np.array(sun.escape_speed)
    e_top = float(recoil_window(np.array([math.hypot(speeds_c[-1], v_esc.max())]), m_t, mu, delta)[1][0])
    if e_top <= 0.0:
        return 0.0
    energies = np.geomspace(e_top * 1e-8, e_top * 1.0001, 600)          # GeV
    plain, transverse = rates.response_terms(energies / KEV, particle, interaction, isotope, model)
    v_min2 = (m_t * energies / mu + delta) ** 2 / (2.0 * m_t * energies)
    grid = np.concatenate([[0.0], energies])
    cum = [np.concatenate([[0.0], _cumulative(y, energies) + y[0] * energies[0]])
           for y in (plain, transverse, transverse * v_min2)]
    w2 = speeds_c[None, :] ** 2 + v_esc[:, None] ** 2
    low, high = recoil_window(np.sqrt(w2), m_t, mu, delta)
    low = np.maximum(low, np.clip(0.5 * m * speeds_c[None, :] ** 2 - delta, 0.0, None))

    def bracket(e: np.ndarray) -> np.ndarray:
        e = np.clip(e, 0.0, grid[-1])
        return np.interp(e, grid, cum[0]) + w2 * np.interp(e, grid, cum[1]) - np.interp(e, grid, cum[2])
    captured = np.where(high > low, bracket(high) - bracket(low), 0.0)
    sigma_w2 = m_t / (2.0 * math.pi) * captured * HBARC_GEV_CM ** 2      # cm² (speeds in c)
    per_volume = (sigma_w2 * flux[None, :] / speeds_c[None, :]).sum(axis=1) * C_CM_S
    return float(np.sum(np.array(sun.densities_cm3[isotope.name]) * per_volume
                        * np.array(sun.shell_volume_cm3)))


def halo_flux(particle: DarkMatterParticle, halo: HaloModel, points: int = 400) -> tuple[np.ndarray, np.ndarray]:
    """(u in units of c, n_χ f(u) du in cm⁻³) in the Sun's frame."""
    seen = sun_frame(halo)
    edges = np.linspace(0.0, halos.max_speed_km_s(seen), points + 1)
    speeds = 0.5 * (edges[1:] + edges[:-1])
    density = halo.rho_gev_cm3 / particle.mass_gev
    return speeds / C_KM_S, density * halos.speed_distribution(speeds, seen) * np.diff(edges)


def capture_rate(particle: DarkMatterParticle, interaction: InteractionModel,
                 halo: HaloModel | None = None, model: NuclearModel = NuclearModel.shell_model,
                 by_isotope: bool = False) -> float | dict[str, float]:
    """The capture rate C of the Sun, in s⁻¹ (or by isotope)."""
    sun = solar_model()
    speeds, flux = halo_flux(particle, halo or HaloModel())
    out = {iso.name: isotope_capture(iso, particle, interaction, sun, speeds, flux, model)
           for iso in isotopes()}
    return out if by_isotope else sum(out.values())


def equilibrium_fraction(capture_s: float, sigma_v_cm3_s: float, m_dm_gev: float, *, self_conjugate: bool) -> float:
    """tanh²(t⊙/τ): the annihilation rate today as a fraction of its equilibrium value C/2, for N particles captured
    at the total rate C (ρ/m counts every particle). Self-conjugate dark matter: dN/dt = C − ⟨σv⟩N²/V_eff, so
    t⊙/τ = t⊙ √(C⟨σv⟩/V_eff). A symmetric Dirac population, N/2 each of χ and χ̄, with ⟨σv⟩ the pair's: χχ̄ annihilate
    at ⟨σv⟩N²/(4V_eff), two particles each, so dN/dt = C − ⟨σv⟩N²/(2V_eff) and t⊙/τ = t⊙ √(C⟨σv⟩/2V_eff); the
    equilibrium C/2 is the same. The caller states which (the independent audit, NA15-05, 2026-11-16: every
    population had taken the self-conjugate form, 0.580 for a Dirac particle's 0.371, and a constructed comparison
    excluded at 1.16 for 0.74)."""
    v_eff = 5.8e27 * (100.0 / m_dm_gev) ** 1.5
    if capture_s <= 0.0 or sigma_v_cm3_s <= 0.0:
        return 0.0
    rate = sigma_v_cm3_s if self_conjugate else 0.5 * sigma_v_cm3_s
    return math.tanh(SUN_AGE_S * math.sqrt(capture_s * rate / v_eff)) ** 2
