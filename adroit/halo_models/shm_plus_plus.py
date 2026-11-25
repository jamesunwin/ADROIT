"""SHM++ (Evans, O'Hare and McCabe, arXiv:1810.11468): its Galactic velocity distribution and the speed distributions a
detector and the Sun see, as tables (``docs/halo_shmplusplus.md`` is the specification, with every equation cited).

**The distribution** (Galactic rest frame; x toward the Galactic centre, y along the rotation, z toward the north pole):

    f(v) = (1 − η) f_R(v) + η f_S(v)                                        (Eq. 3)

- f_R, the round halo: a Maxwellian of dispersion σ_v = v₀/√2 (Eqs. 1–2);
- f_S, the Gaia Sausage: a Gaussian elongated along the radial axis, σ_r² = 3v₀²/[2(3 − 2β)] and
  σ_θ² = σ_φ² = 3v₀²(1 − β)/[2(3 − 2β)] (Eqs. 4–6);
- each cut at the same Galactic escape speed |v| = v_esc and normalised to one after the cut (N_R,esc, Eq. 2;
  N_S,esc, Eq. 7). The local density ρ₀ multiplies the whole, once.

**What a frame sees.** A detector moving at v_E sees f(u + v_E). The Sausage is anisotropic, so its speed distribution

    F(u) = u² ∮ f(u n̂ + v_E) dΩ

depends on the direction of v_E, not only its length. It is integrated with the polar axis along v_E: the escape cut is
then cos α < (v_esc² − u² − |v_E|²)/(2u|v_E|), and the integrand left is smooth (Gauss–Legendre nodes in cos α on the
allowed interval, the trapezoid rule in the periodic azimuth). Both components go through the same integration, so the
round one's agreement with the SHM's closed form checks it. The Sun's frame is the same with v_⊙ = v_LSR + v_peculiar.

**The tables.** F on a uniform grid of speeds from 0 to v_esc + |boost|: a ``HaloModel`` of kind ``tabulated`` in the
detector's frame, or a ``frames.SunFrameTable`` in the Sun's. ``physics.halo`` integrates a table exactly for its linear interpolant, so
η(v_min) and η⊥(v_min) serve every operator, elastic or inelastic of either sign. A table is an implementation of these
parameters at these numerical settings (``Numerics``), regenerated and compared before it is used (``agrees``): never
an anonymous replacement for the distribution.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Literal

import numpy as np
from pydantic import ConfigDict, Field, model_validator

from adroit.core.dm_state import HaloKind, HaloModel
from adroit.core.state import StrictModel
from adroit.halo_models.frames import SunFrameTable, frame_of

GENERATOR = 1                      # the generator's version: a change to how a table is computed is a new version
Frame = Literal["detector", "sun"]
Component = Literal["round", "sausage"]
Vector = tuple[float, float, float]
SQRT_PI = math.sqrt(math.pi)
FRAMES = {"detector": "the detector's frame", "sun": "the Sun's frame"}
AGREEMENT = 1e-9                   # a stored table and its regeneration: the largest difference, relative to its peak


def earth_velocity(n_days: float) -> Vector:
    """The Earth's velocity about the Sun in Galactic coordinates (km/s), ``n_days`` days after J2000.0 (2000 January
    1, 12h TT): McCabe, arXiv:1312.1355, Section 3.3's form u_E,i = ⟨u_E⟩ cos b_i [sin(ℓ − λ_i) − e cos(λ_i − λ₀)],
    λ₀ = ϖ − 270°, with ℓ = L + 2e sin g + (5/4)e² sin 2g and L, g, ϖ, e from Section 2 and (b_i, λ_i) from Section 3.2;
    the form the SHM++ authors' code uses."""
    t = n_days / 36525.0
    e1 = math.radians(0.9574)
    mean = math.radians(280.460 + 0.9856474 * n_days)
    anomaly = math.radians(357.528 + 0.9856003 * n_days)
    lam0 = math.radians(282.932 + 0.0000471 * n_days) - math.radians(270.0)
    longitude = mean + 2.0 * e1 * math.sin(anomaly) + 1.25 * e1 * e1 * math.sin(2.0 * anomaly)
    beta = (5.536 + 0.013 * t, -59.574 + 0.002 * t, -29.811 + 0.001 * t)
    lam = (266.840 + 1.397 * t, 347.340 + 1.375 * t, 180.023 + 1.404 * t)
    return tuple(29.79 * math.cos(math.radians(b)) * (math.sin(longitude - math.radians(lm))
                                                       - e1 * math.cos(math.radians(lm) - lam0))
                 for b, lm in zip(beta, lam))      # type: ignore[return-value]


class Parameters(StrictModel):
    """One SHM++ distribution: Table I's quantities and the boosts (docstring)."""
    model_config = ConfigDict(frozen=True)
    rho_gev_cm3: float = Field(gt=0.0)
    v0_km_s: float = Field(gt=0.0)
    v_esc_km_s: float = Field(gt=0.0)
    beta: float = Field(ge=0.0, lt=1.0)          # the Sausage's anisotropy (Eq. 4); 0 is isotropic
    eta: float = Field(ge=0.0, le=1.0)           # the Sausage's share of the local density (Eq. 3)
    v_peculiar_km_s: Vector
    v_earth_km_s: Vector                         # the Earth's velocity about the Sun at the benchmark's instant

    @model_validator(mode="after")
    def _physical(self) -> "Parameters":
        values = (self.rho_gev_cm3, self.v0_km_s, self.v_esc_km_s, self.beta, self.eta, *self.v_peculiar_km_s,
                  *self.v_earth_km_s)
        if not all(math.isfinite(x) for x in values):
            raise ValueError("SHM++ parameters must be finite numbers")
        for name, boost in (("the Sun's", self.v_sun()), ("the detector's", self.v_detector())):
            if not 0.0 < float(np.linalg.norm(boost)) < self.v_esc_km_s:
                raise ValueError(f"{name} speed through the halo ({float(np.linalg.norm(boost)):.1f} km/s) must be "
                                 f"positive and below the escape speed ({self.v_esc_km_s:g} km/s)")
        return self

    def v_sun(self) -> np.ndarray:
        """The Sun's velocity in the Galactic frame: the local standard of rest (0, v₀, 0) plus its peculiar motion."""
        return np.array([0.0, self.v0_km_s, 0.0]) + np.array(self.v_peculiar_km_s)

    def v_detector(self) -> np.ndarray:
        """The detector's velocity: the Sun's plus the Earth's (Section III A)."""
        return self.v_sun() + np.array(self.v_earth_km_s)

    def boost(self, frame: Frame) -> np.ndarray:
        """The velocity of ``frame`` through the Galactic frame."""
        return self.v_detector() if frame == "detector" else self.v_sun()


INSTANT = 7364.3                   # days after J2000.0: 2020 February 29, 19:12 UT (the authors' code's "day 60.8")
BENCHMARK = Parameters(rho_gev_cm3=0.55, v0_km_s=233.0, v_esc_km_s=528.0, beta=0.9, eta=0.2,
                       v_peculiar_km_s=(11.1, 12.24, 7.25), v_earth_km_s=earth_velocity(INSTANT))
TIME = ("a fixed instant: 7364.3 days after J2000.0 (2020 February 29, 19:12 UT; the SHM++ authors' code's 'day 60.8'), "
        "where the detector's speed through the halo, 246.9 km/s, is near its annual mean of 247.2 km/s; no annual "
        "modulation and no directions")


class Numerics(StrictModel):
    """How a table is computed: its speed grid and angular nodes, and the generator's version."""
    model_config = ConfigDict(frozen=True)
    speeds: int = Field(default=1601, ge=101, le=40001)
    polar: int = Field(default=64, ge=8, le=1024)
    azimuth: int = Field(default=64, ge=8, le=1024)
    generator: int = GENERATOR


def dispersions(p: Parameters) -> tuple[float, float]:
    """(σ_r, σ_θ = σ_φ) of the Sausage, km/s (Eq. 6)."""
    return (math.sqrt(3.0 * p.v0_km_s ** 2 / (2.0 * (3.0 - 2.0 * p.beta))),
            math.sqrt(3.0 * p.v0_km_s ** 2 * (1.0 - p.beta) / (2.0 * (3.0 - 2.0 * p.beta))))


def n_round(p: Parameters) -> float:
    """N_R,esc: the share of the untruncated round Maxwellian below the escape speed (Eq. 2)."""
    z = p.v_esc_km_s / p.v0_km_s                  # v_esc/(√2 σ_v)
    return math.erf(z) - 2.0 * z * math.exp(-z * z) / SQRT_PI


def n_sausage(p: Parameters) -> float:
    """N_S,esc (Eq. 7), with e^(−v_esc²/2σ_θ²) erfi(y) written through Dawson's function, (2/√π) D(y) e^(−x²), which
    stays finite as β → 1; at β = 0 it is N_R,esc."""
    from scipy.special import dawsn
    if p.beta == 0.0:
        return n_round(p)
    sigma_r, _ = dispersions(p)
    x = p.v_esc_km_s / (math.sqrt(2.0) * sigma_r)
    y = x * math.sqrt(p.beta / (1.0 - p.beta))
    return math.erf(x) - math.sqrt((1.0 - p.beta) / p.beta) * 2.0 / SQRT_PI * float(dawsn(y)) * math.exp(-x * x)


def galactic_density(v: np.ndarray, p: Parameters, component: Component) -> np.ndarray:
    """f_R or f_S at Galactic velocities ``v`` (…, 3) in km/s, normalised to one (s³/km³), zero above v_esc."""
    v = np.asarray(v, dtype=float)
    speed2 = np.sum(v * v, axis=-1)
    if component == "round":
        s2 = p.v0_km_s ** 2 / 2.0
        f = np.exp(-speed2 / (2.0 * s2)) / ((2.0 * math.pi * s2) ** 1.5 * n_round(p))
    else:
        sigma_r, sigma_t = dispersions(p)
        exponent = v[..., 0] ** 2 / (2.0 * sigma_r ** 2) + (v[..., 1] ** 2 + v[..., 2] ** 2) / (2.0 * sigma_t ** 2)
        f = np.exp(-exponent) / ((2.0 * math.pi) ** 1.5 * sigma_r * sigma_t ** 2 * n_sausage(p))
    return np.where(speed2 < p.v_esc_km_s ** 2, f, 0.0)


def _axes(boost: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """An orthonormal basis whose first vector is along the boost."""
    e = boost / np.linalg.norm(boost)
    other = np.array([1.0, 0.0, 0.0]) if abs(e[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = np.cross(e, other)
    e1 /= np.linalg.norm(e1)
    return e, e1, np.cross(e, e1)


def speed_distribution(speeds: np.ndarray, boost: np.ndarray, p: Parameters, component: Component,
                       numerics: Numerics = Numerics()) -> np.ndarray:
    """F(u) = u² ∮ f(u n̂ + boost) dΩ (s/km) of one component, seen from a frame moving at ``boost`` (docstring)."""
    speeds = np.asarray(speeds, dtype=float)
    w = float(np.linalg.norm(boost))
    e, e1, e2 = _axes(boost)
    nodes, weights = np.polynomial.legendre.leggauss(numerics.polar)
    phi = 2.0 * math.pi * np.arange(numerics.azimuth) / numerics.azimuth
    ring = np.cos(phi)[:, None] * e1 + np.sin(phi)[:, None] * e2                  # (azimuth, 3)
    out = np.zeros(speeds.size)
    for start in range(0, speeds.size, 64):
        u = speeds[start:start + 64]
        with np.errstate(divide="ignore", invalid="ignore"):
            top = np.where(u > 0.0, (p.v_esc_km_s ** 2 - u * u - w * w) / (2.0 * u * w), -np.inf)
        top = np.minimum(top, 1.0)
        live = top > -1.0
        half = np.where(live, (top + 1.0) / 2.0, 0.0)
        mu = -1.0 + (nodes[None, :] + 1.0) * half[:, None]                         # (speeds, polar)
        sine = np.sqrt(np.clip(1.0 - mu * mu, 0.0, None))
        directions = mu[..., None, None] * e + sine[..., None, None] * ring          # (speeds, polar, azimuth, 3)
        f = galactic_density(u[:, None, None, None] * directions + boost, p, component)
        angular = np.einsum("sp,spa->s", weights[None, :] * half[:, None], f) * (2.0 * math.pi / numerics.azimuth)
        out[start:start + 64] = np.where(live, u * u * angular, 0.0)
    return out


def mixture(speeds: np.ndarray, boost: np.ndarray, p: Parameters, numerics: Numerics = Numerics()) -> np.ndarray:
    """(1 − η) F_R + η F_S: the weights applied once, each component normalised on its own."""
    round_ = speed_distribution(speeds, boost, p, "round", numerics) if p.eta < 1.0 else 0.0
    sausage = speed_distribution(speeds, boost, p, "sausage", numerics) if p.eta > 0.0 else 0.0
    return (1.0 - p.eta) * round_ + p.eta * sausage


def table(p: Parameters, frame: Frame, numerics: Numerics = Numerics(), label: str = "SHM++") -> HaloModel:
    """The speed distribution ``frame`` sees, as a tabulated halo of density ρ₀ (its SHM fields record v₀, v_esc and
    the boosts, so that v_lab is the frame's speed; the rate code reads only the table)."""
    boost = p.boost(frame)
    speeds = np.linspace(0.0, p.v_esc_km_s + float(np.linalg.norm(boost)), numerics.speeds)
    density = mixture(speeds, boost, p, numerics)
    kind = SunFrameTable if frame == "sun" else HaloModel
    return kind(kind=HaloKind.tabulated, label=f"{label}, {FRAMES[frame]}",
                     rho_gev_cm3=p.rho_gev_cm3, v0_km_s=p.v0_km_s, v_esc_km_s=p.v_esc_km_s,
                     v_lsr_km_s=(0.0, p.v0_km_s, 0.0), v_peculiar_km_s=p.v_peculiar_km_s,
                     v_earth_km_s=p.v_earth_km_s if frame == "detector" else (0.0, 0.0, 0.0),
                     speeds_km_s=speeds.tolist(), speed_density=density.tolist())


def tables(p: Parameters, numerics: Numerics = Numerics(), label: str = "SHM++") -> tuple[HaloModel, HaloModel]:
    """(the detector's table, the Sun's)."""
    return table(p, "detector", numerics, label), table(p, "sun", numerics, label)


def sha256(halo: HaloModel) -> str:
    """The identity of a table: the sha256 of its canonical record, its label aside."""
    text = json.dumps(halo.model_dump(mode="json", exclude={"label"}), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def agrees(stored: HaloModel, p: Parameters, frame: Frame, numerics: Numerics) -> str:
    """Why a stored table is not this generator's output for ``p`` in ``frame`` at ``numerics`` ("" when it is,
    within ``AGREEMENT`` of its peak): its version, frame, density, boosts, grid and values are all checked."""
    if numerics.generator != GENERATOR:
        return (f"it was generated by version {numerics.generator} of the SHM++ generator; this ADROIT has version "
                f"{GENERATOR}")
    fresh = table(p, frame, numerics)
    if stored.kind is not HaloKind.tabulated or frame_of(stored) != frame:
        return f"it is not a table in the {frame}'s frame"
    if stored.model_dump(exclude={"label", "speeds_km_s", "speed_density"}) != \
            fresh.model_dump(exclude={"label", "speeds_km_s", "speed_density"}):
        return "its density or boosts differ from its parameters"
    if len(stored.speeds_km_s) != len(fresh.speeds_km_s) or \
            not np.allclose(stored.speeds_km_s, fresh.speeds_km_s, rtol=1e-12, atol=1e-9):
        return "its speed grid differs from its numerical settings"
    a, b = np.asarray(stored.speed_density), np.asarray(fresh.speed_density)
    if not np.all(np.isfinite(a)) or np.max(np.abs(a - b)) > AGREEMENT * np.max(b):
        return f"its values differ from the generator's by up to {np.max(np.abs(a - b)) / np.max(b):.2g} of the peak"
    return ""
