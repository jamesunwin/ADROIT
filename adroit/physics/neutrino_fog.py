"""The neutrino fog: the background of coherent neutrino–nucleus scattering (CEνNS) beneath which a direct-detection
discovery is hard, after O'Hare (arXiv:2109.03116, the fog and its floor; arXiv:2002.07499, the fluxes and the
high-mass floor).

**The background.** Each neutrino flux j (solar pp, pep, hep, the two ⁷Be lines, ⁸B, ¹³N, ¹⁵O, ¹⁷F; the diffuse
supernova background; atmospheric; geoneutrinos and reactors at Gran Sasso) gives nuclear recoils,

    dR_j/dE_r = N_T ∫ dE_ν (dΦ_j/dE_ν) (G_F²/4π) Q_W² m_N (1 − m_N E_r / 2E_ν²) F²(E_r),
    Q_W = N − (1 − 4 sin²θ_W) Z,

with its normalisation known to a fractional uncertainty δ_j (``FLUXES``).

**The discovery limit.** For spin-independent isoscalar scattering (σ the nucleon cross section, rate ∝ A²), the
recoils are binned logarithmically and the Asimov data set (observed = expected) is tested for σ > 0 with every flux
normalisation profiled under its Gaussian constraint: q₀ = −2 ln[L(0, Φ̂̂)/L(σ, Φ)]; a 3σ discovery needs q₀ ≥ 9.
For each σ the exposure at which q₀ reaches 9 is found; its number of background events N grows with it.

**The fog and its floor.** As N grows the limit falls first as N⁻¹ (no background), then as N^{-1/2} (Poisson
subtraction), then slower, saturating where the signal is smaller than the background's uncertainty: in the counting
approximation σ ∝ √(N + δ²N²)/N = √(1 + δ²N)/√N, which tends to δ. The index n = −(d ln σ/d ln N)⁻¹ is 2 in the
Poisson regime and exceeds 2 in the fog; the floor is the n = 2 contour, the largest σ at each mass where n reaches 2
(O'Hare's definition; the same smoothing of the derivative as his public code, so that his published floors are
reproduced). In his construction, with a threshold well below the recoils that matter, it depends on no threshold or
exposure, only on how far the signal's spectrum overlaps the background's and on the flux uncertainties; a custom
recoil window that cuts into the signal or the background moves it.

**The statistic** is a sum of stable Poisson deviances, d = μ − n + n ln(n/μ) per bin (a series near n = μ, the
exact limits at n = 0 and μ = 0), so that it does not cancel at large exposure; a bin with signal and no background
at all makes the Asimov q₀ infinite (background-free), and a profile that does not converge is a numerical failure,
each reported apart from a discovery that is not reached (the focused audit's NF-01).

**What it is for.** An overlay on spin-independent limits and a classification of a model's predicted σ, never a
constraint: a point beneath the floor is not excluded, it is hard to discover.

The flux spectra and the published floors are O'Hare's (github.com/cajohare/NeutrinoFog, MIT licence, copied in
``data/neutrino_fog`` with the licence).
"""

from __future__ import annotations

import math
from functools import lru_cache
from importlib import resources

import numpy as np
from typing import Literal

from pydantic import Field, model_validator

from adroit.core.dm_state import HaloModel, Target
from adroit.core.state import StrictModel

G_F = 1.1663787e-5                 # GeV⁻²
SIN2_THETA_W = 0.2387              # at low momentum transfer (O'Hare 2021)
HBARC_CM = 1.973269804e-14         # GeV cm
AMU_GEV = 0.931494
AVOGADRO = 6.02214076e23
YEAR_S = 365.25 * 86400.0
C_KM_S = 299792.458
TON_GEV = 1.0e6 / 1.782661921e-24  # one tonne in GeV
REFERENCE_SIGMA = 1.0e-45          # cm², the signal's tabulation
DISCOVERY_Q0 = 9.0                 # 3σ


class NeutrinoFlux(StrictModel):
    """One neutrino source: its total flux (cm⁻² s⁻¹), fractional uncertainty, endpoint (MeV), whether a line, and
    its group (for scaling uncertainties together)."""
    name: str
    flux: float = Field(gt=0)
    uncertainty: float = Field(gt=0)
    endpoint_mev: float = Field(gt=0)
    line: bool = False
    group: str


# O'Hare 2020, Table I, as used for the published floors (his code's Params.py): B16-GS98 solar fluxes with ⁸B's
# 2% from the global fit; geoneutrinos and reactors at Gran Sasso. The atmospheric uncertainty is the code's 25%
# (the 2021 paper's text says 20%).
FLUXES: tuple[NeutrinoFlux, ...] = tuple(NeutrinoFlux(name=n, flux=f, uncertainty=u, endpoint_mev=e, line=line, group=g)
    for n, f, u, e, line, g in (
        ('pp', 5.98e10, 0.006, 0.42341, False, 'solar'), ('pep', 1.44e8, 0.01, 1.44, True, 'solar'),
        ('hep', 7.98e3, 0.30, 18.765, False, 'solar'), ('7Be1', 4.93e8, 0.06, 0.3843, True, 'solar'),
        ('7Be2', 4.50e9, 0.06, 0.8613, True, 'solar'), ('8B', 5.16e6, 0.02, 16.34, False, 'solar'),
        ('13N', 2.78e8, 0.15, 1.193, False, 'solar'), ('15O', 2.05e8, 0.17, 1.7285, False, 'solar'),
        ('17F', 5.29e6, 0.20, 1.7365, False, 'solar'), ('DSNB', 85.7, 0.50, 91.201, False, 'dsnb'),
        ('Atm', 10.7, 0.25, 1.0e4, False, 'atmospheric'), ('GeoU', 4.34e6, 0.20, 4.54, False, 'geo'),
        ('GeoTh', 4.23e6, 0.257, 2.33, False, 'geo'), ('GeoK', 20.54e6, 0.168, 1.3572, False, 'geo'),
        ('Reactor', 3.06e6, 0.08, 11.418, False, 'reactor')))
GROUPS = ('solar', 'atmospheric', 'dsnb', 'geo', 'reactor')


def ohare_halo() -> HaloModel:
    """The halo of O'Hare's published floors: σ_v = 167 km/s (v₀ = 236.2 km/s), v_esc = 533 km/s, the detector at
    245.6 km/s, ρ₀ = 0.3 GeV/cm³."""
    return HaloModel(label="O'Hare 2021 floors' SHM", rho_gev_cm3=0.3, v0_km_s=167.0 * math.sqrt(2.0),
                     v_esc_km_s=533.0, v_lsr_km_s=(0.0, 245.6, 0.0), v_peculiar_km_s=(0.0, 0.0, 0.0),
                     v_earth_km_s=(0.0, 0.0, 0.0))


class FogSettings(StrictModel):
    """What a fog is computed for: the target (an isotope such as 'Xe131', O'Hare's choice, or a natural target
    such as 'Xe'), the recoil window and its binning, the halo, the flux uncertainties (each flux's own, or a group
    scaled together: 'solar' × 0.1 is O'Hare's improved-solar case), fluxes left out, and the mass and cross-section
    grids."""
    target: str = 'Xe131'
    threshold_kev: float = Field(default=1.0e-4, gt=0)
    max_recoil_kev: float = Field(default=200.0, gt=0)
    bins: int = Field(default=50, ge=10, le=400)
    halo: HaloModel = Field(default_factory=ohare_halo)
    uncertainties: dict[str, float] = Field(default_factory=dict)
    group_scale: dict[str, float] = Field(default_factory=dict)
    exclude: list[str] = Field(default_factory=list)
    masses_gev: tuple[float, float, int] = (0.1, 1.0e4, 60)
    sigmas_cm2: tuple[float, float, int] = (1.0e-50, 1.0e-43, 500)
    exposure_ton_year: tuple[float, float] = (1.0e-5, 1.0e19)
    # the recoil window's meaning: "window" counts only the recoils inside it; "ohare" normalises each spectrum to its
    # whole physical range, as his public code does (the reproduction of his published floors; the focused audit's
    # NF-02)
    binning: Literal['window', 'ohare'] = 'window'

    @model_validator(mode='after')
    def _meaningful(self) -> 'FogSettings':
        """Ordered positive bounds and grids, and finite positive uncertainties (the focused audit's NF-05)."""
        if not self.threshold_kev < self.max_recoil_kev:
            raise ValueError('the recoil threshold must lie below the window\'s top')
        for name, (low, high, points) in (('masses', self.masses_gev), ('cross sections', self.sigmas_cm2)):
            if not (0 < low < high and points >= 2 and math.isfinite(high)):
                raise ValueError(f'the {name} grid needs 0 < low < high and at least two points')
        if not 0 < self.exposure_ton_year[0] < self.exposure_ton_year[1] or not math.isfinite(self.exposure_ton_year[1]):
            raise ValueError('the exposure range needs 0 < low < high')
        for label, values in (('uncertainty', self.uncertainties), ('scale', self.group_scale)):
            bad = [k for k, v in values.items() if not (math.isfinite(v) and v > 0)]
            if bad:
                raise ValueError(f'each flux {label} must be finite and positive: {", ".join(bad)}')
        return self


class FogMap(StrictModel):
    """A computed fog: for each mass the exposure (ton-years) at which each σ becomes a 3σ discovery (None where it
    is not, with the reason in ``status``), the index n, and the floor (None where none is found)."""
    settings: FogSettings
    fluxes: list[str]
    masses_gev: list[float]
    sigmas_cm2: list[float]
    log10_exposure: list[list[float | None]]
    index: list[list[float | None]]
    floor_cm2: list[float | None]
    # per mass and σ: 'reached', 'not reached' (not within the exposures), 'background-free' (q₀ infinite at every
    # exposure: a bin with signal and no background), or 'failed' (a profile that did not converge)
    status: list[list[str]] = Field(default_factory=list)


def fluxes(settings: FogSettings) -> list[NeutrinoFlux]:
    """The fluxes of ``settings``: the defaults less those excluded, each with its uncertainty replaced or its group's
    scaled."""
    unknown = (set(settings.uncertainties) | set(settings.exclude)) - {f.name for f in FLUXES}
    if unknown or set(settings.group_scale) - set(GROUPS):
        raise ValueError(f'unknown flux or group: {sorted(unknown | (set(settings.group_scale) - set(GROUPS)))}')
    out = []
    for f in FLUXES:
        if f.name in settings.exclude:
            continue
        u = settings.uncertainties.get(f.name, f.uncertainty * settings.group_scale.get(f.group, 1.0))
        out.append(NeutrinoFlux.model_validate({**f.model_dump(), 'uncertainty': u}))     # validated, not copied
    return out


@lru_cache(maxsize=32)
def spectrum(name: str) -> tuple[np.ndarray, np.ndarray]:
    """(E_ν in MeV, dΦ/dE_ν normalised to unit flux) of a continuous source."""
    text = resources.files('adroit.physics').joinpath(f'data/neutrino_fog/spectra/{name}.txt').read_text()
    data = np.loadtxt(text.splitlines(), delimiter=',')
    return data[:, 0], data[:, 1]


def target_of(name: str) -> Target:
    """An isotope ('Xe131': a symbol and a mass number the isotope data hold) or a natural or compound target ('Xe',
    'NaI', 'CaWO4'; the focused audit's NF-04: a compound's digits are its formula, not a mass number)."""
    from adroit.physics import targets
    import re
    match = re.fullmatch(r'([A-Z][a-z]?)(\d+)', name)
    if match is not None:
        element = targets.isotope_data()['elements'].get(match.group(1))
        if element is not None and int(match.group(2)) in element['isotopes']:
            return targets.single_isotope(name)
    return targets.target(name)


def published_target(name: str) -> str | None:
    """The target of O'Hare's published floors that a fog target belongs to: itself (a natural or compound target
    he published), an isotope's element, or None."""
    import re
    if name in PUBLISHED:
        return name
    match = re.fullmatch(r'([A-Z][a-z]?)(\d+)', name)
    return match.group(1) if match is not None and match.group(1) in PUBLISHED else None


def edges(settings: FogSettings) -> np.ndarray:
    """The recoil-energy bin edges (keV), logarithmic."""
    return np.logspace(math.log10(settings.threshold_kev), math.log10(settings.max_recoil_kev), settings.bins + 1)


SUBGRID = 33                     # points per bin of the window's integration


def _binned(density, settings: FogSettings, top_kev: float) -> np.ndarray:
    """A rate density binned on the settings' edges. ``window``: each bin's integral over its part of the physical
    support, recoils above ``top_kev`` (the kinematic end) or outside the window counted nowhere, so the bins sum to
    the integral over the window (the focused audit's NF-02). ``ohare``: as his public code, the trapezoid at the edges
    normalised to the whole spectrum's integral up to ``top_kev``, which moves recoils beyond the window into it."""
    e = edges(settings)
    if top_kev <= settings.threshold_kev:
        return np.zeros(settings.bins)
    if settings.binning == 'window':
        tops = np.minimum(e[1:], top_kev)
        live = tops > e[:-1]
        out = np.zeros(settings.bins)
        if live.any():
            x = np.geomspace(e[:-1][live], tops[live], SUBGRID, axis=1)
            out[live] = np.trapezoid(np.asarray(density(x.ravel())).reshape(x.shape), x, axis=1)
        return out
    fine = np.logspace(math.log10(settings.threshold_kev), math.log10(top_kev), 1000)
    total = np.trapezoid(density(fine), fine)
    d = density(e)
    r = 0.5 * (e[1:] - e[:-1]) * (d[1:] + d[:-1])
    return total * r / r.sum() if r.sum() > 0 else r


def cevns_density(e_kev: np.ndarray, flux: NeutrinoFlux, n: int, z: int) -> np.ndarray:
    """dR/dE_r (per tonne-year per keV) of one flux on one nucleus (module docstring)."""
    from adroit.physics.nuclear import helm_form_factor
    m_n = AMU_GEV * (n + z)
    q_w = n - (1.0 - 4.0 * SIN2_THETA_W) * z
    pref = G_F ** 2 / (4.0 * math.pi) * q_w ** 2 * m_n * HBARC_CM ** 2 * 1.0e-6        # cm² keV⁻¹ (× kinematics)
    per_ton = 1.0e6 / (n + z) * AVOGADRO
    q = np.sqrt(2.0 * m_n * np.asarray(e_kev) * 1.0e-6)
    ff = helm_form_factor(q, n + z) ** 2
    if flux.line:
        kin = 1.0 - m_n * 1.0e-6 * e_kev / (2.0 * (flux.endpoint_mev * 1.0e-3) ** 2)
        rate = np.where(kin > 0, kin, 0.0) * flux.flux
    else:
        e_nu, shape = spectrum(flux.name)
        kin = 1.0 - np.outer(m_n * 1.0e-6 * np.asarray(e_kev), 1.0 / (2.0 * (e_nu * 1.0e-3) ** 2))
        rate = np.trapezoid(np.clip(kin, 0.0, None) * shape * flux.flux, e_nu, axis=1)
    return pref * per_ton * rate * ff * YEAR_S


def background(settings: FogSettings) -> tuple[list[NeutrinoFlux], np.ndarray]:
    """(fluxes, binned rates per tonne-year, one row each) on the settings' target."""
    chosen = fluxes(settings)
    rows = []
    for f in chosen:
        row = np.zeros(settings.bins)
        for iso in target_of(settings.target).isotopes:
            n, z = iso.mass_number - iso.atomic_number, iso.atomic_number
            m_n_kev = AMU_GEV * iso.mass_number * 1.0e6
            top = 2.0 * (f.endpoint_mev * 1.0e3) ** 2 / m_n_kev
            row += iso.mass_fraction * _binned(lambda e: cevns_density(e, f, n, z), settings, top)
        rows.append(row)
    return chosen, np.array(rows)


def signal_density(e_kev: np.ndarray, mass_gev: float, a: int, halo: HaloModel) -> np.ndarray:
    """dR/dE_r (per tonne-year per keV) of spin-independent isoscalar scattering at σ = 10⁻⁴⁵ cm² on a nucleus of
    mass number a, with ADROIT's halo integrals and Helm form factor."""
    from adroit.physics.halo import velocity_integrals
    from adroit.physics.nuclear import helm_form_factor
    m_n = AMU_GEV * a
    mu_n, mu_p = mass_gev * m_n / (mass_gev + m_n), mass_gev * AMU_GEV / (mass_gev + AMU_GEV)
    e = np.asarray(e_kev) * 1.0e-6
    v_min = np.sqrt(m_n * e / (2.0 * mu_n ** 2)) * C_KM_S
    eta = velocity_integrals(v_min, halo)[0] * C_KM_S                       # dimensionless (units of 1/c)
    ff = helm_form_factor(np.sqrt(2.0 * m_n * e), a) ** 2
    per_gev_s = halo.rho_gev_cm3 / mass_gev * a ** 2 * REFERENCE_SIGMA * C_KM_S * 1.0e5 * TON_GEV / (2.0 * mu_p ** 2)
    return per_gev_s * eta * ff * 1.0e-6 * YEAR_S


def signal(settings: FogSettings, masses: np.ndarray) -> np.ndarray:
    """Binned signal rates per tonne-year at σ = 10⁻⁴⁵ cm², one row per mass."""
    from adroit.physics.halo import max_speed_km_s
    v_top = max_speed_km_s(settings.halo) / C_KM_S
    out = np.zeros((len(masses), settings.bins))
    for i, m in enumerate(masses):
        for iso in target_of(settings.target).isotopes:
            m_n = AMU_GEV * iso.mass_number
            mu = m * m_n / (m + m_n)
            top = 4.0 * mu ** 2 * v_top ** 2 / m_n * 1.0e6
            out[i] += iso.mass_fraction * _binned(lambda e: signal_density(e, m, iso.mass_number, settings.halo),
                                                  settings, top)
    return out


def deviance(observed: np.ndarray, mean: np.ndarray) -> np.ndarray:
    """The Poisson deviance per bin, μ − n + n ln(n/μ) ≥ 0, without cancellation: μ g(u) with u = (n − μ)/μ and
    g(u) = (1 + u) ln(1 + u) − u, by its series for |u| < 10⁻³; μ at n = 0, and infinite where μ = 0 < n."""
    n, mu = np.broadcast_arrays(np.asarray(observed, float), np.asarray(mean, float))
    out = np.where(n > 0, np.inf, mu)
    live = (n > 0) & (mu > 0)
    u = np.where(live, (n - mu) / np.where(live, mu, 1.0), 0.0)
    small = np.abs(u) < 1e-3
    series = u * u * (0.5 - u / 6.0 + u * u / 12.0 - u ** 3 / 20.0)
    with np.errstate(invalid='ignore', divide='ignore'):
        direct = (1.0 + u) * np.log1p(u) - u
    return np.where(live, mu * np.where(small, series, direct), out)


FLOOR = 1e-9                     # a flux normalisation this small is at its bound φ = 0 (``_profile``)


def _profile(b: np.ndarray, observed: np.ndarray, used: np.ndarray, inverse: np.ndarray,
             iterations: int = 100) -> tuple[np.ndarray, np.ndarray]:
    """(the flux normalisations φ ≥ 0 minimising each row's negative log-likelihood Σ deviance + ½ Σ (φ − 1)²/δ², and
    whether each row meets the bound-constrained optimality conditions). An active-set Newton method: the fluxes held at
    the bound (``FLOOR``) are fixed and the others take a Newton step; a step that would carry a free flux below the
    bound stops there and holds it (with nearly degenerate fluxes the Newton direction can push a flux down against its
    own gradient). When the free fluxes have converged (their Newton decrement, the predicted further decrease of the
    likelihood, below 10⁻¹⁰ of the likelihood and at least 10⁻¹⁰: q₀ to 2 × 10⁻¹⁰ near the discovery threshold), a held
    flux whose gradient points inwards is released if freeing it alone promises more than that tolerance (g²/2H: a
    smaller gain is rounding, and releasing it would only cycle); the row has converged when none is. A step shortened by one flux's
    bound never counts as convergence of the others (the audit's FR-05). Rows not converged continue with L-BFGS-B
    from there, and are checked again."""
    rows, fluxes = b.shape[0], b.shape[1]
    eye = np.eye(fluxes)

    def parts(phi):
        mu = np.einsum('rj,rji->ri', phi, b)
        safe = np.where(used, mu, 1.0)
        ratio = np.where(used & (observed > 0), observed / safe, 0.0)
        gradient = (b * np.where(used, 1.0 - ratio, 0.0)[:, None, :]).sum(-1) + (phi - 1.0) * inverse
        weight = np.where(used & (observed > 0), observed / safe ** 2, 0.0)
        nll = np.where(used, deviance(observed, mu), 0.0).sum(1) + 0.5 * ((phi - 1.0) ** 2 * inverse).sum(1)
        return gradient, np.einsum('rji,rki,ri->rjk', b, b, weight) + np.diag(inverse), nll

    phi = np.ones((rows, fluxes))
    held = np.zeros((rows, fluxes), bool)
    converged = np.zeros(rows, bool)
    for _ in range(iterations):
        gradient, hessian, nll = parts(phi)
        held |= (phi <= FLOOR) & (gradient > 0.0)
        free = ~held
        g = np.where(free, gradient, 0.0)
        step = np.linalg.solve(hessian * free[:, :, None] * free[:, None, :] + eye * held[:, :, None], g[..., None])[..., 0]
        tolerance = 1e-10 * np.maximum(1.0, nll)
        settled = np.isfinite((g * step).sum(1)) & ((g * step).sum(1) < tolerance)
        gain = gradient ** 2 / (2.0 * np.diagonal(hessian, axis1=1, axis2=2))      # what freeing a flux alone gains
        release = settled[:, None] & held & (gradient < 0.0) & (gain > tolerance[:, None])
        converged = settled & ~release.any(1)
        if converged.all():
            break
        held &= ~release
        moving = ~settled
        with np.errstate(divide='ignore', invalid='ignore'):
            room = np.where(free & (step > 0), (phi - FLOOR) / step, np.inf)
        t = np.minimum(1.0, room.min(1))
        blocked = moving[:, None] & (room <= t[:, None]) & (t[:, None] < 1.0)
        phi = np.where(moving[:, None], np.where(blocked, FLOOR, phi - t[:, None] * step), phi)
        held |= blocked
    for r in np.flatnonzero(~converged):
        phi[r], converged[r] = _bounded(b[r], observed[r], used[r], inverse, phi[r])
    return phi, converged


def _bounded(b: np.ndarray, observed: np.ndarray, used: np.ndarray, inverse: np.ndarray,
             start: np.ndarray) -> tuple[np.ndarray, bool]:
    """One row's profile by L-BFGS-B (φ ≥ 0, analytic gradient), and whether it meets the optimality conditions."""
    from scipy.optimize import minimize

    def nll(phi):
        mu = phi @ b
        value = np.where(used, deviance(observed, mu), 0.0).sum() + 0.5 * ((phi - 1.0) ** 2 * inverse).sum()
        safe = np.where(used, mu, 1.0)
        ratio = np.where(used & (observed > 0), observed / safe, 0.0)
        return value, (b * np.where(used, 1.0 - ratio, 0.0)).sum(-1) + (phi - 1.0) * inverse
    if not np.all(np.isfinite(start)):
        start = np.ones_like(start)
    found = minimize(nll, np.clip(start, FLOOR, None), jac=True, method='L-BFGS-B',
                     bounds=[(FLOOR, None)] * len(start), options={'maxiter': 2000, 'ftol': 1e-15, 'gtol': 1e-12})
    phi = np.clip(found.x, FLOOR, None)
    gradient = nll(phi)[1]
    projected = np.where(phi > FLOOR, gradient, np.minimum(gradient, 0.0))
    mu = phi @ b
    ratio = np.where(used & (observed > 0), observed / np.where(used, mu, 1.0), 0.0)
    scale = (b * np.where(used, 1.0 + ratio, 0.0)).sum(-1) + inverse * (1.0 + np.abs(phi - 1.0))
    return phi, bool(np.all(np.isfinite(phi)) and np.all(np.abs(projected) <= 1e-6 * scale))


def asimov_q0(signal_rows: np.ndarray, rates: np.ndarray, uncertainty: np.ndarray, exposure: np.ndarray,
              sigma: np.ndarray) -> np.ndarray:
    """q₀ of the Asimov data set for each row (a signal spectrum at 10⁻⁴⁵ cm², an exposure in tonne-years and a σ),
    with the background ``rates`` (fluxes × bins, per tonne-year) and every flux normalisation profiled under its
    Gaussian constraint, φ ≥ 0 (``_profile``): 2 Σ deviance + Σ (φ − 1)²/δ² at the profile (module docstring).
    Infinite where a bin holds signal and no background at all (background-free); nan where the profile does not meet
    the optimality conditions."""
    if not np.all(np.isfinite(uncertainty)) or np.any(np.asarray(uncertainty) <= 0):
        raise ValueError('every flux uncertainty must be finite and positive (a known flux is not a zero-width prior)')
    s = (np.asarray(sigma) / REFERENCE_SIGMA * np.asarray(exposure))[:, None] * signal_rows
    b = np.asarray(exposure)[:, None, None] * rates[None]
    observed = s + b.sum(1)
    free = (b.sum(1) <= 0) & (observed > 0)                  # signal with no background: no finite profile term
    used = (b.sum(1) > 0)
    inverse = 1.0 / np.asarray(uncertainty) ** 2
    phi, converged = _profile(b, observed, used, inverse)
    mu = np.einsum('rj,rji->ri', phi, b)
    terms = np.where(used, deviance(observed, mu), 0.0).sum(1)
    q0 = 2.0 * terms + ((phi - 1.0) ** 2 * inverse).sum(1)
    q0 = np.where(converged & np.isfinite(q0) & np.isfinite(phi).all(1), q0, np.nan)
    return np.where(free.any(1), np.inf, q0)


def discovery_exposure(signal_row: np.ndarray, rates: np.ndarray, uncertainty: np.ndarray, sigmas: np.ndarray,
                       limits: tuple[float, float], steps: int = 55) -> tuple[np.ndarray, np.ndarray]:
    """(the exposure in tonne-years at which q₀ reaches 9, by bisection in its logarithm, and the status) for each σ:
    'reached' (nan exposure otherwise), 'not reached' within ``limits``, 'background-free' (q₀ already infinite at the
    lowest exposure) or 'failed' (a profile that did not converge on the way: never read as not reached)."""
    rows = np.repeat(signal_row[None], len(sigmas), axis=0)
    low, high = np.full(len(sigmas), math.log(limits[0])), np.full(len(sigmas), math.log(limits[1]))
    q_low = asimov_q0(rows, rates, uncertainty, np.exp(low), sigmas)
    q_high = asimov_q0(rows, rates, uncertainty, np.exp(high), sigmas)
    failed = np.isnan(q_low) | np.isnan(q_high)
    for _ in range(steps):
        middle = 0.5 * (low + high)
        q = asimov_q0(rows, rates, uncertainty, np.exp(middle), sigmas)
        failed |= np.isnan(q)
        up = q >= DISCOVERY_Q0
        high, low = np.where(up, middle, high), np.where(up, low, middle)
    status = np.where(failed, 'failed', np.where(np.isinf(q_low), 'background-free',
                      np.where(q_high >= DISCOVERY_Q0, 'reached', 'not reached')))
    return np.where(status == 'reached', np.exp(high), np.nan), status


def index_and_floor(sigmas: np.ndarray, exposure: np.ndarray, cap: float = 1.0e10) -> tuple[np.ndarray, float]:
    """(n at each σ, the floor) from the discovery exposures at one mass, as in O'Hare's code (``Floor_2D``): log₁₀
    exposure smoothed (Gaussian filters of 3 cells), its gradient in log₁₀ σ smoothed again, n = −gradient, the floor
    the largest σ with n ≥ 2 (interpolated over the next ten cells); exposures above ``cap`` are not trusted."""
    from scipy.ndimage import gaussian_filter1d
    exposure = np.where(exposure > cap, np.nan, exposure)
    y = np.log10(exposure)
    good = np.isfinite(y)
    if good.sum() < 10:
        return np.full(len(sigmas), np.nan), math.nan
    y = np.where(good, y, np.nanmax(y))
    x = np.log10(sigmas)
    smooth = gaussian_filter1d(gaussian_filter1d(y, 3), 3)
    gradient = gaussian_filter1d(np.gradient(smooth, x[1] - x[0]), 3)
    index = np.where(good, -gradient, np.nan)
    for i in range(len(sigmas) - 1, -1, -1):
        if good[i] and gradient[i] <= -2.0:
            j = min(i + 10, len(sigmas) - 1)
            order = np.argsort(gradient[i:j + 1])
            return index, float(10 ** np.interp(-2.0, gradient[i:j + 1][order], x[i:j + 1][order]))
    return index, math.nan


def grid(spec: tuple[float, float, int]) -> np.ndarray:
    """A logarithmic grid (low, high, points)."""
    return np.logspace(math.log10(spec[0]), math.log10(spec[1]), int(spec[2]))


def fog(settings: FogSettings | None = None) -> FogMap:
    """The fog over the settings' masses and cross sections, and its floor."""
    settings = settings or FogSettings()
    chosen, rates = background(settings)
    uncertainty = np.array([f.uncertainty for f in chosen])
    masses, sigmas = grid(settings.masses_gev), grid(settings.sigmas_cm2)
    signals = signal(settings, masses)
    exposures, indices, floors, statuses = [], [], [], []
    for row in signals:
        exposure, status = discovery_exposure(row, rates, uncertainty, sigmas, settings.exposure_ton_year)
        index, value = index_and_floor(sigmas, exposure)
        if (status == 'failed').any():          # a failed profile is not an unreached exposure: no floor from it
            value = math.nan
        exposures.append(np.log10(exposure))
        indices.append(index)
        floors.append(value)
        statuses.append([str(v) for v in status])
    clean = lambda a: [None if not math.isfinite(v) else float(v) for v in a]        # noqa: E731
    return FogMap(settings=settings, fluxes=[f.name for f in chosen], masses_gev=masses.tolist(),
                  sigmas_cm2=sigmas.tolist(), log10_exposure=[clean(e) for e in exposures],
                  index=[clean(i) for i in indices], floor_cm2=clean(floors), status=statuses)


def discovery_limit(settings: FogSettings, exposure_ton_year: float, steps: int = 60) -> tuple[np.ndarray, np.ndarray]:
    """(masses, σ) of the classic 3σ discovery limit at a fixed exposure and the settings' threshold (as the floors
    of Billard et al. 2014 were built): σ where q₀ reaches 9, by bisection in log σ; nan where it is not reached by
    10⁻³⁰ cm²."""
    chosen, rates = background(settings)
    uncertainty = np.array([f.uncertainty for f in chosen])
    masses = grid(settings.masses_gev)
    rows = signal(settings, masses)
    exposure = np.full(len(masses), exposure_ton_year)
    low, high = np.full(len(masses), math.log(1e-55)), np.full(len(masses), math.log(1e-30))
    q_high = asimov_q0(rows, rates, uncertainty, exposure, np.exp(high))
    reached = q_high >= DISCOVERY_Q0
    failed = np.isnan(q_high)
    for _ in range(steps):
        middle = 0.5 * (low + high)
        q = asimov_q0(rows, rates, uncertainty, exposure, np.exp(middle))
        failed |= np.isnan(q)
        up = q >= DISCOVERY_Q0
        high, low = np.where(up, middle, high), np.where(up, low, middle)
    return masses, np.where(reached & ~failed & (rows.sum(1) > 0), np.exp(high), np.nan)


PUBLISHED = {'Xe': 'Xe_SI', 'Ar': 'Ar_SI', 'Ge': 'Ge_SI', 'NaI': 'NaI_SI', 'CaWO4': 'CaWO4_SI', 'He': 'He_SI',
             'F': 'F_SI'}


@lru_cache(maxsize=16)
def published_floor(target: str = 'Xe') -> tuple[tuple[float, ...], tuple[float, ...]]:
    """(masses GeV, σ cm²) of O'Hare's published spin-independent floor for a target (his data/floors): the standard
    curve, as LZ and XENONnT draw it for xenon."""
    if target not in PUBLISHED:
        raise ValueError(f'no published floor for {target!r}; available: {", ".join(PUBLISHED)}')
    text = resources.files('adroit.physics').joinpath(f'data/neutrino_fog/floors/{PUBLISHED[target]}.txt').read_text()
    data = np.loadtxt([line for line in text.splitlines() if line.strip() and not line.startswith('#')])
    return tuple(data[:, 0].tolist()), tuple(data[:, 1].tolist())


def floor_at(mass_gev: float, target: str = 'Xe') -> float | None:
    """The published floor at a mass (log–log interpolation), or None outside its masses."""
    masses, sigmas = published_floor(target)
    if not masses[0] <= mass_gev <= masses[-1]:
        return None
    return float(10 ** np.interp(math.log10(mass_gev), np.log10(masses), np.log10(sigmas)))
