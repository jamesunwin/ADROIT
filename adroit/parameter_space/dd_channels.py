"""Direct detection at one point: every non-zero scattering channel against its validated limits (R2).

A model can scatter through several channels at once: spin-independent (O₁, with couplings c₁ᵖ and c₁ⁿ to
protons and neutrons) and spin-dependent on protons and on neutrons (O₄: c₄ᵖ, c₄ⁿ). Each channel is compared
with its own validated 95% limits (``limits.per_module95``):

- **SI with c₁ᵖ ≠ c₁ⁿ:** module by module. Module m's isoscalar-equivalent cross-section is
  σ_m = μ²/π [f c₁ᵖ + (1 − f) c₁ⁿ]², with f = Z/A of its target, against that module's limit. The largest
  ratio decides, so a coupling that cancels on xenon (c₁ⁿ/c₁ᵖ ≈ −0.7) is still seen by argon. A compound target
  (CaWO₄, C₃F₈) gives a band over its elements' Z/A, since which element dominates depends on the mass.
- **SI with c₁ᵖ = c₁ⁿ:** σ against the strongest validated limit.
- **SD with one nucleon coupling:** σ against the strongest validated limit for the kind.
- **SD with both nucleons coupling:** each published limit assumes the other coupling vanishes, and in one
  target the two amplitudes interfere. A module validated for both kinds gives Tovey et al.'s band
  [(√r_p − √r_n)², (√r_p + √r_n)²] on its own ratios, which brackets the interference whatever its isotopes' spin
  signs. A module validated for one kind only (PICO's proton limit; CRESST-III's and CDMSlite's neutron limits)
  has its ratio scaled by its own rate ratio F = rate(c₄ᵖ, c₄ⁿ)/rate(the published coupling alone), computed
  with its target's nuclear responses, halo and nuclear model at the point's mass (2026-10-12, the owner's
  choice): exact within the module's nuclear model, signs included. For fluorine F stays within a few percent;
  for germanium, whose other-nucleon spin is small but not negligible, it can be much larger.

**The outcome.** The point is excluded if any channel exceeds its limit. If none does, and a non-zero channel
has no validated limit at the mass, the outcome is undecided (pending) and names that channel: a channel is
never dropped silently.

**Bands.** A channel can carry a relative uncertainty δ on its amplitude (a coloured partner near degeneracy,
``portals.tchannel``); the rate goes as the amplitude squared, so the ratio to the limit lies in
[r(1 − δ)², r(1 + δ)²]. With the compound-target and interference bands above, a channel excludes only if its
band's lower end exceeds 1, is allowed only if its upper end does not, and is pending, with its band, in between. A channel whose prediction is not computable
at all (``unreliable``) leaves the point pending unless another channel excludes it.

**Precomputed limits** (R10). A xenon search's limit may come from its precomputed table, within a tolerance η
(``limit_tables``). Each comparison that decides the verdict is checked: a ratio x is clear of the threshold if
x > 1 + η or x(1 + η) ≤ 1, and Tovey et al.'s difference √r − √s if its whole range, with r and s each moved by
up to η, lies on one side of ±1. If any comparison is not clear, the point is compared again with every limit
computed directly, so the verdict is the one the direct calculation gives. At a sample of the halo region
(``halo_limits``) the comparisons a count ratio cannot decide are noted instead (``State.fragile``): the region's
evaluation decides whether a full calculation is spent on them (``halo_evaluation``).
"""

from __future__ import annotations

import math
from contextvars import ContextVar

from adroit.core.state import StrictModel
from adroit.parameter_space import limit_tables, limits
from adroit.physics import conventions

# The elements of the target of each module validated for spin-independent scattering. A compound target gives a
# band: which element dominates depends on the mass (tungsten in CaWO₄ above a few GeV, its light elements below), so
# the isospin-violating ratio is bracketed by its elements (mini audit: CaWO₄ was 0.5). Within an element its
# isotopes are weighted as the rate weighs them (``element_coupling_squared``).
ELEMENTS = {"CRESST-III 2019": ("Ca", "W", "O"), "CDMSlite Run 2": ("Ge",), "DEAP-3600 (2019)": ("Ar",),
            "LZ WS2022+WS2024": ("Xe",), "XENONnT SR0+SR1": ("Xe",), "PandaX-4T Run0+Run1": ("Xe",),
            "PICO-60 C3F8 (2019)": ("C", "F")}


def element_coupling_squared(symbol: str, c_p: float, c_n: float, mass: float) -> float:
    """The per-nucleon coupling squared whose σ_SI is the element's: ⟨(Z c_p + N c_n)²⟩ / ⟨A²⟩ over its isotopes,
    weighted by abundance × μ² (the rate's weight at small momentum transfer; Feng, Kumar, Marfatia & Sanford,
    arXiv:1102.4331). c_p² when c_n = c_p. One Z/A per element (the element's mean) had cancelled where its isotopes do
    not: xenon at c_n/c_p = −0.70 suppressed 6 × 10⁻⁷ for the rate's 1.3 × 10⁻⁴ (the addendum's AL3-31, 2026-11-16)."""
    from adroit.physics import targets
    element = targets.isotope_data()["elements"][symbol]
    z = element["Z"]
    top = bottom = 0.0
    for a, (abundance, _spin) in element["isotopes"].items():
        nucleus = conventions.AMU_GEV * a
        weight = abundance * (mass * nucleus / (mass + nucleus)) ** 2
        top += weight * (z * c_p + (a - z) * c_n) ** 2
        bottom += weight * a ** 2
    return top / bottom


_FRAGILE: ContextVar[list[str] | None] = ContextVar("dd_fragile", default=None)


def _clear(value: float, eta: float) -> bool:
    """Whether a ratio's comparison with 1 holds for its limit moved by any factor up to 1 + η."""
    return eta <= 0.0 or value > 1.0 + eta or value * (1.0 + eta) <= 1.0


def _clear_difference(r: float, s: float, eta_r: float, eta_s: float, scale: float) -> bool:
    """Whether |√r − √s| × scale stays on one side of 1 for r and s each moved by up to their η."""
    if eta_r <= 0.0 and eta_s <= 0.0:
        return True
    low = scale * (math.sqrt(r / (1.0 + eta_r)) - math.sqrt(s * (1.0 + eta_s)))
    high = scale * (math.sqrt(r * (1.0 + eta_r)) - math.sqrt(s / (1.0 + eta_s)))
    return low > 1.0 or high < -1.0 or (low >= -1.0 and high <= 1.0)


def _check(clear: bool, what: str) -> None:
    """Record a comparison that a tabulated limit's tolerance could reverse (``compare`` then recomputes)."""
    fragile = _FRAGILE.get()
    if fragile is not None and not clear:
        fragile.append(what)


def _widths(channel: "Channel") -> tuple[float, float]:
    """The amplitude band's factors on a ratio's low and high ends (``_band``)."""
    d = channel.amplitude_uncertainty
    return (max(1.0 - d, 0.0) ** 2, (1.0 + d) ** 2) if d > 0 else (1.0, 1.0)


class Channel(StrictModel):
    """One scattering channel at a point."""

    kind: str                                  # SI, SD-proton or SD-neutron
    sigma_cm2: float                           # σ per nucleon (SI: for c₁ᵖ = c₁ⁿ; else the proton's)
    c_p: float | None = None                   # SI with c₁ᵖ ≠ c₁ⁿ: the O₁ couplings (GeV⁻²), compared per module
    c_n: float | None = None
    odd_p: float = 0.0                         # a Dirac or complex relic's C-odd part: its rate adds per module
    odd_n: float = 0.0
    sd_p: float | None = None                  # SD: the signed O₄ couplings c₄ᵖ, c₄ⁿ (GeV⁻²), for interference
    sd_n: float | None = None
    amplitude_uncertainty: float = 0.0         # relative uncertainty δ on the amplitude (module docstring)
    uncertainty_note: str = ""                 # where δ comes from
    unreliable: str = ""                       # why the prediction is not computable here


class ChannelOutcome(StrictModel):
    """One channel's comparison."""

    kind: str
    sigma_cm2: float                           # the compared σ (SI with c₁ᵖ ≠ c₁ⁿ: in the deciding module)
    limit: limits.StatisticalLimit | None = None
    ratio: float | None = None
    ratio_band: tuple[float, float] | None = None   # [r(1 − δ)², r(1 + δ)²] with an amplitude uncertainty
    uncertainty_note: str = ""
    unreliable: str = ""


class Outcome(StrictModel):
    """Every channel's comparison and the verdict."""

    channels: list[ChannelOutcome]
    excluded: bool | None
    pending: list[str]

    @property
    def decisive(self) -> ChannelOutcome | None:
        """The channel with the largest ratio, else the first channel without a limit."""
        rated = [c for c in self.channels if c.ratio is not None]
        if rated:
            return max(rated, key=lambda c: c.ratio)
        return self.channels[0] if self.channels else None

    @property
    def combinable(self) -> float | None:
        """The ratio a combined likelihood may take: the largest lower end of the computable channels' bands (a
        channel without a band, its ratio), so it never excludes where the cuts leave a band pending and never drops
        an exclusion the cuts make (a channel whose lower end exceeds 1); None where no computable channel has a
        ratio. A channel whose prediction the model declares not computable (``unreliable``) never enters a
        combination, as it never decides a cut (the audit loop's AL1-01, 2026-11-14: its ratio had been combined, so
        the likelihood excluded points the cuts left pending on that reason). It was the lower end of the channel
        with the largest ratio (AL2-07: an SI band (1.2, 1.25), which the cuts exclude by, beside an SD band
        (0.2, 3.0) gave 0.2)."""
        chosen = self.combined_channel
        if chosen is None:
            return None
        return chosen.ratio_band[0] if chosen.ratio_band else chosen.ratio

    @property
    def combined_channel(self) -> ChannelOutcome | None:
        """The channel whose lower end ``combinable`` takes, so that the ratio's construction (one- or two-sided) is
        that channel's too (AL3-07: the decisive channel's had been stored beside another channel's lower end)."""
        rated = [c for c in self.channels if c.ratio is not None and not c.unreliable]
        return max(rated, key=lambda c: c.ratio_band[0] if c.ratio_band else c.ratio, default=None)


def channels_of(c1_p: float, c1_n: float, c4_p: float, c4_n: float, mass: float, *, uncertainty: float = 0.0,
                note: str = "", unreliable: str = "", c1_odd: tuple[float, float] = (0.0, 0.0)) -> list[Channel]:
    """The non-zero channels of nucleon couplings at q → 0 (``portals.base.Nucleon``'s normalisation), each with
    the same amplitude uncertainty, or not computable (``unreliable``). ``c1_odd`` is a Dirac or complex relic's
    C-odd SI part (its sign flips between particle and antiparticle, so its rate adds to c₁'s nucleus by nucleus)."""
    common = dict(amplitude_uncertainty=uncertainty, uncertainty_note=note, unreliable=unreliable)
    out = []
    odd_p, odd_n = c1_odd
    if c1_p or c1_n or odd_p or odd_n:
        isoscalar = c1_p == c1_n and odd_p == odd_n == 0.0
        sigma = conventions.sigma_si_cm2(c1_p, mass) + conventions.sigma_si_cm2(odd_p, mass)
        out.append(Channel(kind="SI", sigma_cm2=sigma, c_p=None if isoscalar else c1_p,
                           c_n=None if isoscalar else c1_n, odd_p=odd_p, odd_n=odd_n, **common))
    if c4_p:
        out.append(Channel(kind="SD-proton", sigma_cm2=conventions.sigma_sd_cm2(c4_p, mass), sd_p=c4_p, sd_n=c4_n,
                           **common))
    if c4_n:
        out.append(Channel(kind="SD-neutron", sigma_cm2=conventions.sigma_sd_cm2(c4_n, mass), sd_p=c4_p, sd_n=c4_n,
                           **common))
    return out


def single_kind_factor(module: str, kind: str, mass: float, other_over_mine: float) -> float | None:
    """F = rate(both couplings)/rate(the module's published coupling alone) in the module's own target, for an O₄
    interaction whose other-nucleon coupling is ``other_over_mine`` times this kind's; None if the module's rate
    for its own kind vanishes. At a halo of the region, at its velocities (the density cancels); at a generated
    benchmark, at its detector table.

    Raises:
        limit_tables.InputsChanging: if the module's inputs changed each time the factor was computed; the caller
            then has no limit from the module, with the reason (the audit loop's AL1-13, 2026-11-14: taken as no
            factor, the ratio had been compared without it, and no reason given).
    """
    from adroit.parameter_space import halo_limits
    state = halo_limits.active()
    return _single_kind_factor(module, kind, mass, other_over_mine,
                               None if state is None else halo_limits.velocities(state))


@limit_tables.held(4096, lambda module, *_: limit_tables.inputs(module))      # by the module's inputs (DY-01)
def _single_kind_factor(module: str, kind: str, mass: float, other_over_mine: float,
                        velocities: tuple | None) -> float | None:
    from adroit.core.dm_state import DarkMatterParticle
    from adroit.experiments import registry as modules
    from adroit.library.interactions import registry
    from adroit.parameter_space import halo_limits
    m = modules.load_module(module)
    conv = m.conventions()
    halo = conv.halo if velocities is None else halo_limits.halo_at(velocities)
    particle = DarkMatterParticle(mass_gev=mass)

    def events(c_p: float, c_n: float) -> float:
        interaction = registry.resolve("O4", particle, {"c_p": c_p, "c_n": c_n})
        return m.expected_signal(particle, interaction, halo, conv.spin_dependent_model).total_events
    mine, other = (1.0, other_over_mine)
    both = events(mine, other) if kind == "SD-proton" else events(other, mine)
    alone = events(1.0, 0.0) if kind == "SD-proton" else events(0.0, 1.0)
    return both / alone if alone > 0 else None


def _band(outcome: ChannelOutcome, channel: Channel) -> ChannelOutcome:
    """The outcome with its ratio band widened by the channel's amplitude uncertainty, if any."""
    d = channel.amplitude_uncertainty
    if outcome.ratio is None or d <= 0:
        return outcome
    low, high = outcome.ratio_band or (outcome.ratio, outcome.ratio)
    note = "; ".join(filter(None, [outcome.uncertainty_note, channel.uncertainty_note]))
    return outcome.model_copy(update={"ratio_band": (low * max(1.0 - d, 0.0) ** 2, high * (1.0 + d) ** 2),
                                      "uncertainty_note": note})


def _compare(channel: Channel, mass: float, excluded_modules: tuple[str, ...]) -> ChannelOutcome:
    """One channel against its validated 95% limits, with its ratio band."""
    return _band(_compare_central(channel, mass, excluded_modules), channel)


def _compare_central(channel: Channel, mass: float, excluded_modules: tuple[str, ...]) -> ChannelOutcome:
    """One channel's central prediction against its validated 95% limits."""
    down, up = _widths(channel)
    if channel.c_p is None:
        limit = limits.at95(channel.kind, mass, excluded_modules)
        ratio = channel.sigma_cm2 / limit.value if limit.value else None
        if ratio is not None:
            _check_every(channel, mass, excluded_modules, down, up)
        return ChannelOutcome(kind=channel.kind, sigma_cm2=channel.sigma_cm2, limit=limit, ratio=ratio,
                              unreliable=channel.unreliable)
    found, omitted = limits.per_module95("SI", mass, excluded_modules)
    rows = []                                        # (low, high, σ at the high end, module, limit)
    for module, value in found:
        elements = ELEMENTS.get(module)
        if elements is None:
            omitted += ((module, "no target elements for a proton–neutron comparison"),)
            continue
        sigmas = [conventions.sigma_si_cm2(math.sqrt(element_coupling_squared(e, channel.c_p, channel.c_n, mass)), mass)
                  + conventions.sigma_si_cm2(math.sqrt(element_coupling_squared(e, channel.odd_p, channel.odd_n, mass)),
                                             mass) for e in elements]
        rows.append((min(sigmas) / value, max(sigmas) / value, max(sigmas), module, value))
        eta = limits.tolerance(module, "SI", mass)
        _check(_clear(rows[-1][0] * down, eta) and _clear(rows[-1][1] * up, eta), f"SI ({module})")
    if not rows:
        return ChannelOutcome(kind="SI", sigma_cm2=channel.sigma_cm2, unreliable=channel.unreliable,
                              limit=limits.StatisticalLimit(value=None, confidence_level=0.95, omitted=dict(omitted),
                                                            construction="no validated module at this mass"))
    return _decisive_row("SI", rows, omitted, "per module with its target's isotopes",
                         "the target's elements bracket the proton–neutron combination", channel.unreliable)


def _check_every(channel: Channel, mass: float, excluded_modules: tuple[str, ...], down: float, up: float) -> None:
    """``_check`` of the channel against every module's limit with its own tolerance: the strongest decides the ratio,
    but a weaker tabulated module's true limit can lie below it within its η, and then the verdict could change (the
    audit loop's AL1-06, 2026-11-14: the strongest module's tolerance alone had been tested)."""
    found, _ = limits.per_module95(channel.kind, mass, excluded_modules)
    for module, value in found:
        eta = limits.tolerance(module, channel.kind, mass)
        r = channel.sigma_cm2 / value
        _check(_clear(r * down, eta) and _clear(r * up, eta), f"{channel.kind} ({module})")


def _decisive_row(kind: str, rows: list[tuple], omitted: tuple, how: str, band_note: str,
                  unreliable: str) -> ChannelOutcome:
    """The deciding module of per-module (low, high) ratios: the one whose low end is largest if any exceeds 1,
    else the one whose high end is largest; a band where low and high differ."""
    low, high, sigma, module, value = (max(rows, key=lambda r: r[0]) if any(r[0] > 1.0 for r in rows)
                                       else max(rows, key=lambda r: r[1]))
    limit = limits.StatisticalLimit(value=value, confidence_level=0.95, source=module, omitted=dict(omitted),
                                    sidedness=limits.sidedness(module),
                                    construction=f"module procedure at CL=0.95, {how} ({limits.sidedness(module)})")
    banded = not math.isclose(low, high, rel_tol=1e-12)
    return ChannelOutcome(kind=kind, sigma_cm2=sigma, limit=limit, ratio=high, unreliable=unreliable,
                          ratio_band=(low, high) if banded else None, uncertainty_note=band_note if banded else "")


def _sd_with_interference(channel: Channel, other: Channel, mass: float) -> ChannelOutcome | None:
    """An SD channel when the other nucleon also couples: per module, a module validated for both SD kinds gives
    Tovey et al.'s band (√r_p ∓ √r_n)², which brackets the two couplings' interference in the same target
    whatever its isotopes' signs; a module validated for this kind only keeps its single-channel ratio. None if
    no module is validated for the kind (the caller's ordinary comparison names why)."""
    mine, omitted = limits.per_module95(channel.kind, mass)
    theirs = dict(limits.per_module95(other.kind, mass)[0])
    rows = []
    signed = channel.sd_p is not None and channel.sd_n is not None
    down, up = _widths(channel)
    for module, value in mine:
        r = channel.sigma_cm2 / value
        eta_r = limits.tolerance(module, channel.kind, mass)
        if module in theirs:
            s = other.sigma_cm2 / theirs[module]
            rows.append(((math.sqrt(r) - math.sqrt(s)) ** 2, (math.sqrt(r) + math.sqrt(s)) ** 2, channel.sigma_cm2,
                         module, value))
            eta_s = limits.tolerance(module, other.kind, mass)
            high_low = (math.sqrt(r / (1 + eta_r)) + math.sqrt(s / (1 + eta_s))) ** 2 * up
            high_high = (math.sqrt(r * (1 + eta_r)) + math.sqrt(s * (1 + eta_s))) ** 2 * up
            _check(_clear_difference(r, s, eta_r, eta_s, math.sqrt(down))
                   and (high_low > 1.0 or high_high <= 1.0 or max(eta_r, eta_s) <= 0.0), f"{channel.kind} ({module})")
            continue
        factor = None
        if signed:                                   # one kind only: the module's own rate ratio (docstring)
            mine_c, other_c = ((channel.sd_p, channel.sd_n) if channel.kind == "SD-proton"
                               else (channel.sd_n, channel.sd_p))
            try:
                factor = single_kind_factor(module, channel.kind, mass, float(f"{other_c / mine_c:.6g}"))
            except limit_tables.InputsChanging as error:   # no limit from it, with the reason (AL1-13)
                omitted += ((module, f"its rate ratio for the other nucleon's coupling: {error}"),)
                continue
        if factor is None:
            rows.append((r, r, channel.sigma_cm2, module, value))
        else:
            rows.append((r * factor, r * factor, channel.sigma_cm2 * factor, module, value))
        _check(_clear(rows[-1][0] * down, eta_r) and _clear(rows[-1][1] * up, eta_r), f"{channel.kind} ({module})")
    if not rows and mine:              # every validated module set aside (AL1-13): no limit, with the reasons
        return ChannelOutcome(kind=channel.kind, sigma_cm2=channel.sigma_cm2, unreliable=channel.unreliable,
                              limit=limits.StatisticalLimit(value=None, confidence_level=0.95, omitted=dict(omitted),
                                                            construction="no module's limit at this mass"))
    if not rows:
        return None
    return _decisive_row(channel.kind, rows, omitted, "per module, with proton–neutron interference (Tovey et al.'s "
                         "band, or the module's own rate ratio where it is validated for one kind)",
                         "proton–neutron interference in the same target (Tovey et al.)", channel.unreliable)


def compare(channels: list[Channel], mass: float, si_excluded_modules: tuple[str, ...] = ()) -> Outcome:
    """Every channel against its limits, and the verdict (module docstring).

    ``si_excluded_modules`` are modules superseded by a selected private spin-independent result: they leave
    the SI comparison only, never the spin-dependent ones. Compared first with any precomputed limits; again with
    every limit computed directly if a tabulated limit's tolerance could change the verdict.
    """
    with limit_tables.reading():                   # one version of each module's inputs for the comparison (DY-01)
        fragile: list[str] = []
        token = _FRAGILE.set(fragile)
        try:
            outcome = _compare_all(channels, mass, si_excluded_modules)
        finally:
            _FRAGILE.reset(token)
        if not fragile:
            return outcome
        from adroit.parameter_space import halo_limits
        state = halo_limits.active()
        if state is not None and state.defer:      # the halo region decides whether a full calculation is spent
            state.fragile += [f for f in fragile if f not in state.fragile]
            return outcome
        with limits.exact():
            return _compare_all(channels, mass, si_excluded_modules)


def _compare_all(channels: list[Channel], mass: float, si_excluded_modules: tuple[str, ...]) -> Outcome:
    sd = {c.kind: c for c in channels if c.kind in ("SD-proton", "SD-neutron") and c.sigma_cm2 > 0}
    results = []
    for c in channels:
        combined = None
        if c.kind in sd and len(sd) == 2:      # both nucleons couple: bracket their interference (mini audit)
            other = sd["SD-neutron" if c.kind == "SD-proton" else "SD-proton"]
            combined = _sd_with_interference(c, other, mass)
        results.append(_band(combined, c) if combined is not None else
                       _compare(c, mass, si_excluded_modules if c.kind == "SI" else ()))
    pending = []
    for r in results:
        pending += [f"direct detection ({name}): {why}" for name, why in (r.limit.omitted if r.limit else {}).items()]
    computable = [r for r in results if not r.unreliable]
    if any(_lowest(r) > 1.0 for r in computable if r.ratio is not None):
        return Outcome(channels=results, excluded=True, pending=list(dict.fromkeys(pending)))
    pending += [f"direct detection ({r.kind}): not computed here: {r.unreliable}" for r in results if r.unreliable]
    straddling = [r for r in computable if r.ratio is not None and _lowest(r) <= 1.0 < _highest(r)]
    pending += [f"direct detection ({r.kind}): ratio {r.ratio_band[0]:.3g}–{r.ratio_band[1]:.3g} straddles the limit "
                f"({r.uncertainty_note})" for r in straddling]
    missing = [r for r in computable if r.ratio is None]
    pending += [f"direct detection ({r.kind}): no validated limit at m_χ = {mass:.4g} GeV" for r in missing]
    weaker = any(why == limits.MAXIMUM_GAP_FALLBACK for r in results for why in (r.limit.omitted if r.limit else {}).values())
    undecided = bool(missing) or bool(straddling) or len(computable) < len(results) or weaker    # D1
    return Outcome(channels=results, excluded=None if undecided else False, pending=list(dict.fromkeys(pending)))


def _lowest(r: ChannelOutcome) -> float:
    return r.ratio_band[0] if r.ratio_band else r.ratio


def _highest(r: ChannelOutcome) -> float:
    return r.ratio_band[1] if r.ratio_band else r.ratio
