"""The halo side of the rate: velocity distributions and their integrals.

A recoil rate needs two integrals of the dark matter velocity distribution in
the detector frame, f(v), over the particles fast enough to give the recoil
(speed above v_min):

    η(v_min)  = ∫_{v > v_min} d³v f(v) / v                  (s/km)
    η⊥(v_min) = ∫_{v > v_min} d³v f(v) (v² − v_min²) / v    (km/s)

η weights each particle by its inverse speed. η⊥ weights it also by v⊥², the
squared component of its velocity transverse to the momentum transfer, which
the velocity-dependent operators need. v⊥² = v² − v_min² holds for inelastic
scattering too, with v_min including the splitting (arXiv:1409.0536; WimPyDD
uses the same).

Two kinds of halo (``HaloModel.kind``):
- **standard**, the Standard Halo Model: a Maxwellian of most probable speed
  v0, truncated sharply at the escape speed v_esc in the Galactic frame, seen
  from a detector moving at v_lab. Both integrals are closed-form. Its
  parameters (ρ, v0, v_esc, the Sun's and the Earth's velocities) are fixed in
  every fit; no fit profiles them as nuisance parameters. Track 2 refits at
  other v0 and v_esc and flags a fit that depends on them
  (``orchestrator.signal``, ``ALTERNATIVE_HALOS``).
- **tabulated**: a speed distribution in the detector frame, given as a table.
  The integrals are exact for the table's linear interpolant.

The Earth's velocity about the Sun follows arXiv:2105.00599, Eq. (11).
"""

from __future__ import annotations

import math

import numpy as np
from scipy.special import erf

from adroit.core.dm_state import HaloKind, HaloModel

# The Earth's orbit (arXiv:2105.00599, Eq. 11 and Table 1), in Galactic
# coordinates: toward the Galactic centre, along the rotation, toward the north pole.
EARTH_SPEED_KM_S = 29.8
ORBIT_EPSILON_1 = (0.9941, 0.1088, 0.0042)
ORBIT_EPSILON_2 = (-0.0504, 0.4946, -0.8677)
DAYS_PER_YEAR = 365.25
REFERENCE_DAY = 80.0     # 22 March, the orbit's phase origin, in days after 1 January

SQRT_PI = math.sqrt(math.pi)


# --- the Earth's motion --------------------------------------------------------------


def earth_velocity_km_s(day: float) -> tuple[float, float, float]:
    """The Earth's velocity about the Sun, ``day`` days after 1 January (0h).

    v_E(t) = ⟨|v_E|⟩ [ε₁ cos ω(t − t₁) + ε₂ sin ω(t − t₁)], with t₁ = 22 March
    and ω = 2π per year (arXiv:2105.00599, Eq. 11).
    """
    phase = 2.0 * math.pi * (day - REFERENCE_DAY) / DAYS_PER_YEAR
    c, s = math.cos(phase), math.sin(phase)
    return tuple(EARTH_SPEED_KM_S * (a * c + b * s)  # type: ignore[return-value]
                 for a, b in zip(ORBIT_EPSILON_1, ORBIT_EPSILON_2))


def halo_on_day(halo: HaloModel, day: float) -> HaloModel:
    """The same halo seen on ``day`` (days after 1 January), for annual modulation."""
    if halo.kind is not HaloKind.standard:
        raise ValueError("a tabulated halo is given in the detector frame and has no "
                         "time dependence")
    return halo.model_copy(update={"v_earth_km_s": earth_velocity_km_s(day)})


def max_speed_km_s(halo: HaloModel) -> float:
    """The fastest dark matter particle in the detector frame."""
    if halo.kind is HaloKind.standard:
        return halo.v_esc_km_s + halo.v_lab_km_s
    return halo.speeds_km_s[-1]


# --- the Standard Halo Model ---------------------------------------------------------


def _shm_scales(halo: HaloModel) -> tuple[float, float, float, float]:
    """(v0, e = v_lab/v0, z = v_esc/v0, N_esc) of a standard halo."""
    v0 = halo.v0_km_s
    e, z = halo.v_lab_km_s / v0, halo.v_esc_km_s / v0
    if not 0.0 < e < z:
        raise ValueError(f"the detector speed ({halo.v_lab_km_s:.1f} km/s) must be positive "
                         f"and below the escape speed ({halo.v_esc_km_s:.1f} km/s)")
    n_esc = math.erf(z) - 2.0 * z * math.exp(-z * z) / SQRT_PI
    return v0, e, z, n_esc


def _shm_speed_distribution(speeds: np.ndarray, halo: HaloModel) -> np.ndarray:
    """f(v) of the Standard Halo Model in the detector frame, in s/km."""
    v0, e, z, n_esc = _shm_scales(halo)
    u = speeds / v0
    upper = np.minimum((u + e) ** 2, z * z)
    f = u / (SQRT_PI * n_esc * e * v0) * (np.exp(-((u - e) ** 2)) - np.exp(-upper))
    return np.where((u >= 0.0) & (u < z + e), f, 0.0)


def _shm_eta(x: np.ndarray, e: float, z: float) -> np.ndarray:
    """2 N_esc v_lab η, in units of v0, as a function of x = v_min/v0."""
    low = erf(x + e) - erf(x - e) - 4.0 * e * math.exp(-z * z) / SQRT_PI
    high = math.erf(z) - erf(x - e) - 2.0 * (z + e - x) * math.exp(-z * z) / SQRT_PI
    return np.where(x < z - e, low, np.where(x < z + e, high, 0.0))


def _shm_first_moment(x: np.ndarray, e: float, z: float) -> np.ndarray:
    """√π N_esc v_lab ∫ f(v) v dv / v0², above x = v_min/v0.

    The integrand is u² [exp(−(u−e)²) − exp(−min((u+e)², z²))], whose
    antiderivatives are A(u) and B(u) below.
    """
    k = 0.25 * SQRT_PI * (1.0 + 2.0 * e * e)

    def a(u: np.ndarray | float) -> np.ndarray:
        return k * erf(u - e) - 0.5 * (u + e) * np.exp(-((u - e) ** 2))

    def b(u: np.ndarray | float) -> np.ndarray:
        return k * erf(u + e) - 0.5 * (u - e) * np.exp(-((u + e) ** 2))

    cut = math.exp(-z * z) / 3.0
    low = a(z + e) - a(x) - (b(z - e) - b(x)) - cut * ((z + e) ** 3 - (z - e) ** 3)
    high = a(z + e) - a(x) - cut * ((z + e) ** 3 - x ** 3)
    return np.where(x < z - e, low, np.where(x < z + e, high, 0.0))


def _shm_integrals(v_min: np.ndarray, halo: HaloModel) -> tuple[np.ndarray, np.ndarray]:
    """η and η⊥ of the Standard Halo Model, in closed form."""
    v0, e, z, n_esc = _shm_scales(halo)
    x = v_min / v0
    v_lab = halo.v_lab_km_s
    eta = _shm_eta(x, e, z) / (2.0 * n_esc * v_lab)
    first = v0 * v0 * _shm_first_moment(x, e, z) / (SQRT_PI * n_esc * v_lab)
    return eta, first - v_min ** 2 * eta


# --- tabulated halos -----------------------------------------------------------------


def _table(halo: HaloModel) -> tuple[np.ndarray, np.ndarray]:
    """The table's speeds and its density normalised to ∫ f dv = 1."""
    v = np.asarray(halo.speeds_km_s, dtype=float)
    f = np.asarray(halo.speed_density, dtype=float)
    if v[0] == 0.0 and f[0] > 0.0:
        raise ValueError("the speed density must vanish at zero speed, or η diverges")
    return v, f / np.trapezoid(f, v)


def _segment_integrals(v1: np.ndarray, v2: np.ndarray, f1: np.ndarray,
                       f2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """∫ f/v and ∫ f v over segments on which f is linear, from f1 at v1 to f2 at v2."""
    slope = (f2 - f1) / (v2 - v1)
    offset = f1 - slope * v1
    with np.errstate(divide="ignore", invalid="ignore"):
        log_term = np.where(offset == 0.0, 0.0, offset * np.log(v2 / v1))
    inverse = log_term + slope * (v2 - v1)
    first = offset * (v2 ** 2 - v1 ** 2) / 2.0 + slope * (v2 ** 3 - v1 ** 3) / 3.0
    return inverse, first


def _tabulated_integrals(v_min: np.ndarray, halo: HaloModel) -> tuple[np.ndarray, np.ndarray]:
    """η and η⊥ of a tabulated halo: exact for the linear interpolant of the table."""
    v, f = _table(halo)
    inverse, first = _segment_integrals(v[:-1], v[1:], f[:-1], f[1:])
    # Integrals from each node to the top of the table.
    tail_inverse = np.concatenate([np.cumsum(inverse[::-1])[::-1], [0.0]])
    tail_first = np.concatenate([np.cumsum(first[::-1])[::-1], [0.0]])
    below = v_min <= v[0]
    above = v_min >= v[-1]
    k = np.clip(np.searchsorted(v, v_min, side="right") - 1, 0, len(v) - 2)
    start = np.clip(v_min, v[0], v[-1])
    f_start = np.interp(start, v, f)
    part_inverse, part_first = _segment_integrals(start, v[k + 1], f_start, f[k + 1])
    eta = np.where(below, tail_inverse[0], part_inverse + tail_inverse[k + 1])
    moment = np.where(below, tail_first[0], part_first + tail_first[k + 1])
    eta, moment = np.where(above, 0.0, eta), np.where(above, 0.0, moment)
    return eta, moment - v_min ** 2 * eta


# --- the public interface ------------------------------------------------------------


def speed_distribution(speeds_km_s: np.ndarray, halo: HaloModel) -> np.ndarray:
    """The speed distribution f(v) in the detector frame, in s/km, with ∫ f dv = 1."""
    speeds = np.asarray(speeds_km_s, dtype=float)
    if halo.kind is HaloKind.standard:
        return _shm_speed_distribution(speeds, halo)
    v, f = _table(halo)
    return np.interp(speeds, v, f, left=0.0, right=0.0)


def velocity_integrals(v_min_km_s: np.ndarray, halo: HaloModel) -> tuple[np.ndarray, np.ndarray]:
    """η(v_min) in s/km and η⊥(v_min) in km/s, for each v_min (module docstring)."""
    v_min = np.asarray(v_min_km_s, dtype=float)
    if np.any(v_min < 0.0):
        raise ValueError("v_min must not be negative")
    if halo.kind is HaloKind.standard:
        eta, eta_perp = _shm_integrals(v_min, halo)
    else:
        eta, eta_perp = _tabulated_integrals(v_min, halo)
    return np.clip(eta, 0.0, None), np.clip(eta_perp, 0.0, None)


def tabulate(halo: HaloModel, points: int = 2000) -> HaloModel:
    """A standard halo as a table of its detector-frame speed distribution.

    The starting point for a deviation from the Standard Halo Model that is
    easiest to state as a change to f(v).
    """
    if halo.kind is not HaloKind.standard:
        return halo
    speeds = np.linspace(0.0, max_speed_km_s(halo), points)
    return HaloModel(kind=HaloKind.tabulated, label=f"{halo.label}, tabulated",
                     rho_gev_cm3=halo.rho_gev_cm3, speeds_km_s=speeds.tolist(),
                     speed_density=_shm_speed_distribution(speeds, halo).tolist())
