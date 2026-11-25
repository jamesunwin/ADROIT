"""The halo region over which a point's halo-dependent constraints are evaluated (the owner's specification of
2026-10-19): the Standard Halo Model's ρ₀, v₀ and v_esc with declared working distributions, a finite joint region
declared before scanning, its samples, and the classification of a point over them.

**The preset** (the owner's working priors, not a published joint measurement; treated as independent, a declared
approximation): ρ₀ log-normal with median 0.40 GeV cm⁻³ and σ_lnρ = 0.35 (central 68% ≈ 0.28–0.57); v₀ Gaussian
233 ± 20 km s⁻¹; v_esc Gaussian 528 ± 30 km s⁻¹ (centres after McMillan, arXiv:1608.00971, and Deason et al.,
arXiv:1901.02016, with deliberately broadened widths; ρ₀'s width accommodates e.g. McMillan's 0.38 ± 0.04 and Söding
et al.'s 0.50 ± 0.15, arXiv:2506.02956).

**The region.** In the standardised coordinates (ln ρ₀, v₀, v_esc) the three are independent unit normals, so the
joint region of probability ``level`` (0.95) is the ball of radius r with P(χ²₃ ≤ r²) = level (r = 2.796). Its
probability belongs to the halo region, not to any experiment's confidence level, and is not an overall 95% statement;
the region is finite (no tail is minimised over). Along ρ₀ alone at the central velocities it spans 0.15–1.07 GeV cm⁻³.

**Density analytically.** Every halo-dependent constraint here strengthens with ρ₀ (direct detection and capture in
the Sun ∝ ρ₀; Galactic-halo γ-ray lines and antiprotons ∝ ρ₀²), so at fixed velocities a point is classified over the
ρ₀ the ball allows there by the interval's two ends, ln ρ₀ = ln 0.40 ± 0.35 √(r² − d²), d the velocity sample's
standardised distance. Only the velocity plane (v₀, v_esc) is sampled.

**The velocity samples:** the centre, four axis extremes and four diagonals on the disc's boundary, and interior points
from a scrambled Sobol sequence (fixed seed). A classification that holds throughout is checked again with the
interior points doubled (``converged``); a sample that differs makes the point halo-sensitive. Within the Standard
Halo Model the local circular speed moves with v₀ (v_LSR = v₀) and the laboratory velocity follows. Shape changes of
the velocity distribution, streams and the Large Magellanic Cloud are not covered.

**The classification** (``classify``): the whole point at each common halo, never a favourable halo per experiment.
Excluded throughout the tested region; allowed throughout it, with every sample's constraints complete; pending and
halo-sensitive where the classification changes across it (the nominal, the region's centre, shown); pending with the
halo coverage incomplete where a sample could not be evaluated. A halo-independent exclusion (a collider search, say)
excludes everywhere. This is an envelope over a region, not a profile likelihood: no halo parameter is profiled.
"""
from __future__ import annotations

import math
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache

from pydantic import Field

from adroit.core.halo_choice import FixedHalo
from adroit.core.state import StrictModel

LABEL = "the owner's working Standard Halo Model preset (2026-10-19)"


class HaloPreset(StrictModel):
    """Declared working distributions of the Standard Halo Model's parameters (independent) and the region's
    probability."""
    rho_median_gev_cm3: float = Field(default=0.40, gt=0)
    sigma_ln_rho: float = Field(default=0.35, gt=0)
    v0_km_s: float = Field(default=233.0, gt=0)
    sigma_v0_km_s: float = Field(default=20.0, gt=0)
    v_esc_km_s: float = Field(default=528.0, gt=0)
    sigma_v_esc_km_s: float = Field(default=30.0, gt=0)
    level: float = Field(default=0.95, gt=0, lt=1)
    interior: int = Field(default=12, ge=4, le=256)
    seed: int = 20261019
    full_calculations: int = Field(default=2, ge=0, le=64)   # per point: the slow modules' full procedure
    label: str = LABEL


class HaloSample(StrictModel):
    """One velocity sample, with the density interval the region allows there."""
    v0_km_s: float
    v_esc_km_s: float
    rho_low_gev_cm3: float
    rho_high_gev_cm3: float
    where: str                       # 'centre', 'boundary', 'interior' or 'interior (doubled)'


@lru_cache(maxsize=16)
def radius(level: float) -> float:
    """r with P(χ²₃ ≤ r²) = level."""
    from scipy.stats import chi2
    return math.sqrt(chi2.ppf(level, 3))


def _sample(preset: HaloPreset, a: float, b: float, where: str) -> HaloSample:
    """The sample at standardised velocity coordinates (a, b)."""
    r = radius(preset.level)
    spread = math.sqrt(max(r * r - a * a - b * b, 0.0)) * preset.sigma_ln_rho
    median = preset.rho_median_gev_cm3
    return HaloSample(v0_km_s=preset.v0_km_s + a * preset.sigma_v0_km_s,
                      v_esc_km_s=preset.v_esc_km_s + b * preset.sigma_v_esc_km_s,
                      rho_low_gev_cm3=median * math.exp(-spread), rho_high_gev_cm3=median * math.exp(spread),
                      where=where)


def _interior(preset: HaloPreset, count: int) -> list[tuple[float, float]]:
    """``count`` points uniform in the velocity disc from a scrambled Sobol sequence (radius √u, angle 2πv): the
    first of a longer request are those of a shorter one."""
    from scipy.stats import qmc
    r = radius(preset.level)
    draws = qmc.Sobol(d=2, scramble=True, seed=preset.seed).random(2 ** math.ceil(math.log2(max(count, 2))))
    return [(r * math.sqrt(u) * math.cos(2 * math.pi * v), r * math.sqrt(u) * math.sin(2 * math.pi * v))
            for u, v in draws[:count]]


def samples(preset: HaloPreset) -> list[HaloSample]:
    """The centre, the eight boundary samples and the interior points."""
    r = radius(preset.level)
    out = [_sample(preset, 0.0, 0.0, "centre")]
    out += [_sample(preset, r * math.cos(k * math.pi / 4), r * math.sin(k * math.pi / 4), "boundary") for k in range(8)]
    return out + [_sample(preset, a, b, "interior") for a, b in _interior(preset, preset.interior)]


def doubled(preset: HaloPreset) -> list[HaloSample]:
    """The convergence check's further interior points (the next ``interior`` of the same sequence)."""
    points = _interior(preset, 2 * preset.interior)[preset.interior:]
    return [_sample(preset, a, b, "interior (doubled)") for a, b in points]


def centre(preset: HaloPreset) -> tuple[float, float, float]:
    """(v₀, v_esc, ρ₀) at the region's centre: the nominal halo."""
    return preset.v0_km_s, preset.v_esc_km_s, preset.rho_median_gev_cm3


_PRESET: ContextVar[HaloPreset | None] = ContextVar("adroit_halo_region", default=None)


@contextmanager
def using(preset: HaloPreset | None):
    """Evaluate every point over this region (None: each experiment's published halo, the reproduction mode), or at
    this fixed benchmark. The value is checked (``checked``) before it is put in force, so that every calculation that
    puts a saved halo in force (a run, a variant, a combination, a verdict, a replay, a scan's worker) refuses what a
    fresh run refuses, before anything is calculated (a halo phase 2 audit's HB-02, 2026-11-11: a continuation and a
    bundle's replay had calculated a snapshot a fresh run refused)."""
    token = _PRESET.set(checked(preset))
    try:
        yield
    finally:
        _PRESET.reset(token)


def preset() -> HaloPreset | None:
    """The region in force, or None (the published-halo reproduction)."""
    return _PRESET.get()


def describe(p: HaloPreset) -> str:
    """One line naming the region."""
    return (f"{p.label}: ρ₀ log-normal (median {p.rho_median_gev_cm3:g} GeV cm⁻³, σ_ln {p.sigma_ln_rho:g}), "
            f"v₀ {p.v0_km_s:g} ± {p.sigma_v0_km_s:g} km/s, v_esc {p.v_esc_km_s:g} ± {p.sigma_v_esc_km_s:g} km/s, "
            f"independent; the joint {100 * p.level:g}% region (radius {radius(p.level):.4g}), a halo region, not an "
            "experiment's confidence level")


# --- what a point saves (``halo_evaluation``) and how it is labelled (``verdict.classify``) ------------------------

HALO_CONSTRAINTS = ("direct detection", "capture in the Sun (IceCube)", "γ-ray lines (Fermi-LAT, H.E.S.S.)",
                    "antiprotons (AMS-02)")
AT_BENCHMARK = "at the fixed benchmark halo"       # a point calculated at one fixed benchmark (``FixedHalo``)
EXCLUDED = "excluded throughout the tested halo region"
ALLOWED = "allowed throughout the tested halo region"
SAME_PENDING = "pending throughout the tested halo region"
SENSITIVE = "halo-sensitive"
INCOMPLETE = "halo coverage incomplete"
UNIFORM = (EXCLUDED, ALLOWED, SAME_PENDING)


class HaloOutcome(StrictModel):
    """One halo-dependent constraint at one halo."""
    excluded: bool | None
    ratio: float | None = None
    exact: bool = True             # its limit from a full procedure (a count ratio decides a cut, never a combination)
    why: str = ""
    # the statistical construction of the limit deciding here (direct detection: the deciding experiment can change
    # with the halo, PX-04); left out when absent, so earlier saves keep their identity
    confidence_level: float | None = Field(default=None, exclude_if=lambda v: v is None)
    sidedness: str | None = Field(default=None, exclude_if=lambda v: v is None)


class HaloPointSample(StrictModel):
    """A point's halo-dependent constraints at one halo of the region."""
    v0_km_s: float
    v_esc_km_s: float
    rho_gev_cm3: float
    where: str
    outcomes: dict[str, HaloOutcome] = Field(default_factory=dict)
    pending: list[str] = Field(default_factory=list)          # their pending reasons here
    unresolved: list[str] = Field(default_factory=list)       # comparisons no calculation decided here
    full_calculations: list[str] = Field(default_factory=list)


class HaloEvaluation(StrictModel):
    """A point over the halo region: every sample's halo-dependent constraints. At a fixed benchmark
    (``treatment`` "benchmark"), no samples: the point itself is calculated there, and ``region`` names the benchmark."""
    region: str
    treatment: str = Field(default="", exclude_if=lambda v: not v)     # "" the region (every earlier save)
    samples: list[HaloPointSample] = Field(default_factory=list)
    nominal_pending: list[str] = Field(default_factory=list)  # the centre's pending reasons from these constraints
    unsupported: list[str] = Field(default_factory=list)      # comparisons with no halo variation here
    converged: bool | None = None                              # doubling the interior changed nothing
    full_calculations: list[str] = Field(default_factory=list)
    # the halo data files the point was calculated with, by name: sha256 ("" missing), as it read them; {} in a point
    # saved before they were recorded (the auditor's HB recheck, HC-01, 2026-11-11: its certificate is bound to them)
    data: dict[str, str] = Field(default_factory=dict, exclude_if=lambda v: not v)


def over(statuses: list[str], unresolved: list[bool]) -> str:
    """The region's label from each sample's status and whether a comparison there is undecided: an excluded sample
    is decided whatever is undecided there."""
    decided = {s for s, u in zip(statuses, unresolved) if s == "excluded" or not u}
    if len(decided) > 1:
        return SENSITIVE
    if any(u and s != "excluded" for s, u in zip(statuses, unresolved)) or not decided:
        return INCOMPLETE
    return {"excluded": EXCLUDED, "viable": ALLOWED, "pending": SAME_PENDING}[decided.pop()]


# --- a request's halo ------------------------------------------------------------------------------------------------

PUBLISHED = "published"


def default() -> str:
    """The setting ``ADROIT_HALO_REGION``: "preset" (the default) or "published"."""
    from adroit.core.config import get_settings
    setting = str(getattr(get_settings(), "halo_region", "preset")).strip().lower()
    if setting not in ("preset", PUBLISHED):
        raise ValueError(f"ADROIT_HALO_REGION is {setting!r}: give preset or published")
    return setting


def stated(value):
    """A request's halo value as its run states it: its own, else the setting's (the owner's preset unless it says
    published)."""
    if value is not None:
        return value
    return HaloPreset() if default() == "preset" else PUBLISHED


def resolved(request):
    """The request with its halo stated (``stated``)."""
    if request.halo is not None:
        return request
    return request.model_copy(update={"halo": stated(None)})


def of(value) -> HaloPreset | FixedHalo | None:
    """The halo a request's value puts in force: its region, its fixed benchmark, or None (the published halos)."""
    return value if isinstance(value, (HaloPreset, FixedHalo)) else None


def checked(value):
    """A request's halo value, refused (``ValueError``) where it cannot be calculated: a fixed benchmark whose family is
    not available; one not of its family's form, or naming another family's benchmark (``halo_choice.verify``, HB-01);
    a generated one (SHM++) whose tables are not its generator's output for its parameters, or not the bytes their
    sha256 records (``verify``); a standard one whose halo is not one the direct-detection machinery evaluates at
    (``halo_limits.parameterised``: a standard halo with v_LSR = v₀ and the default solar and Earth velocities).
    Refused before anything is calculated, never calculated at another halo."""
    if isinstance(value, FixedHalo):
        from adroit.core.halo_choice import available, verify
        from adroit.parameter_space.halo_limits import parameterised
        available(value.family)
        if why := verify(value):
            raise ValueError(f"{why}; nothing is calculated")
        if value.generated:
            return value
        if not parameterised(value.halo):
            raise ValueError(f"{value.benchmark}: its halo is not one the direct-detection machinery evaluates at (a "
                             "standard halo with v_LSR = v₀ and the default solar and Earth velocities); nothing is "
                             "calculated")
    return value


def check_inputs(request) -> None:
    """Refuse a scan over the region, or at a fixed benchmark, with an input that has no halo variation yet: a private
    spin-independent curve or a private search holds only its paper's halo. Such a run uses the published-halo
    reproduction."""
    found = [b.name for b in request.private_limits if b.contract.adapter == "si_isoscalar_curve"]
    found += [b.search_id for b in request.private_searches]
    if found:
        where = "at a fixed benchmark halo" if isinstance(of(getattr(request, "halo", None)), FixedHalo) \
            else "over the halo region"
        raise ValueError(f"{', '.join(found)}: a private direct-detection input has no halo variation yet, so it "
                         f"cannot be calculated {where}; run with the published halos (--halo published) or without "
                         "it")
