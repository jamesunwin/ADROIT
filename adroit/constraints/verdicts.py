"""Applicability verdicts: what each constraint says about a candidate (DM7).

For every (candidate, record) pair the verdict is one of (build plan, DM7):
- **applies**: the constraint can be applied as it stands;
- **applies under stated assumptions**: it can be applied once named
  assumptions are made (an annihilation channel, equilibrium in the Sun, a
  standard thermal history);
- **needs a further calculation**, which is named, and no conclusion is drawn.

What a candidate must supply depends on the tier (``TIER_OF_CLASS``):
- tier 2, capture in the Sun: the nonrelativistic interaction alone fixes the
  capture rate; the annihilation channel and equilibrium are assumed, unless a
  completion computes them;
- tier 3, relic density, indirect detection and colliders: a relativistic
  completion (here, a spin-1 simplified model). Without one the verdict names
  the missing calculation.

**How capture meets a neutrino telescope.** A telescope limits the
annihilation rate in the Sun for one channel; the collaboration quotes it as
the cross-section σ_lim at which a pure SD (or SI) interaction would be
captured fast enough. Converting both through the system's own capture
calculation, C_lim = C(σ_lim), makes the comparison a comparison of capture
rates, C_candidate × tanh²(t⊙/τ) > C_lim, valid for any operator,
inelastic scattering included.
"""

from __future__ import annotations

import math

import numpy as np
from matplotlib.path import Path as Polygon

from adroit.constraints.speeds import DWARF_SPEED, sun_speed   # one definition with Track 1's scan (AL3-33)
from adroit.constraints import annihilation, capture, database, eos_reads, spin1
from adroit.constraints.spin1 import Spin1Model
from adroit.constraints.relic import RelicUnresolved
from adroit.core.certificate import POLICY, Bound, Certificate, Check
from adroit.core.dm_state import (Applicability, ConstraintClass, ConstraintRecord, ConstraintVerdict,
                                  DarkMatterParticle, HaloModel, InteractionModel, OperatorCoefficient)
from adroit.core.state import StrictModel
from adroit.physics import conventions

NEEDS_COMPLETION = ("a relativistic completion (a mediator model with couplings to Standard Model "
                    "particles), from which {what} follow")
TELESCOPE_CHANNELS = {"soft": "bb", "hard": "WW", "tau": "tautau"}


class Candidate(StrictModel):
    """What the verdicts judge: a particle, its interaction at the fitted strength, and any completion."""

    label: str
    particle: DarkMatterParticle
    interaction: InteractionModel
    completion: Spin1Model | None = None


def scaled(interaction: InteractionModel, factor: float) -> InteractionModel:
    """The interaction with every coupling multiplied by ``factor`` (rates scale as its square)."""
    return interaction.model_copy(update={"coefficients": [
        c.model_copy(update={"proton": c.proton * factor, "neutron": c.neutron * factor})
        for c in interaction.coefficients]})


def _needs(record: ConstraintRecord, candidate: Candidate, calculation: str, note: str = "") -> ConstraintVerdict:
    return ConstraintVerdict(constraint_id=record.id, interaction_id=candidate.label,
                             applicability=Applicability.needs_calculation,
                             needed_calculation=calculation, note=note)


def _hadronic(candidate: Candidate, today: bool) -> str:
    """Why the completion's annihilation is not computed (the hadronic window, the owner's decision, 2026-10-20): its
    quark pairs at √s ≈ 2m_χ in the window, or the mediator's uncomputed hadronic width moving the s-channel propagator
    (at s = 4m_χ² alone ``today``), or "" (``spin1.annihilation_window``, ``spin1.propagator_window``)."""
    model, m = candidate.completion, candidate.particle.mass_gev
    return spin1.annihilation_window(model, m) or spin1.propagator_window(model, m, fixed=today)


def _unverified(record: ConstraintRecord) -> str:
    return "" if record.usable else "record not yet verified by a person"


def relic(candidate: Candidate, record: ConstraintRecord) -> ConstraintVerdict:
    """Overabundance excludes, under a standard thermal history, where the comparison is the same across the
    equation of state's band (``_relic_band``); a density that is not a finite, nonnegative number decides nothing
    (the consistency audit's CA-03, 2026-10-24: Ωh² = nan had read as allowed). Its certificate: ``relic_judged``."""
    return relic_judged(candidate, record)[0]


@eos_reads.producer             # bound to the tables as the comparison read them (the auditor's CT recheck, CU-02)
def relic_judged(candidate: Candidate, record: ConstraintRecord) -> tuple[ConstraintVerdict, Certificate | None]:
    """``relic``'s verdict and the comparison's certificate (M1's claim kind ``relic_comparison``; None where no
    comparison is made: no completion, or the hadronic window). The certificate is kept beside the verdict, not in
    it: ``ConstraintVerdict`` is among the inputs the native PICO certificate's fingerprint hashes, and is not changed."""
    if candidate.completion is None:
        return _needs(record, candidate, NEEDS_COMPLETION.format(what="the annihilation cross-sections")), None
    if why := _hadronic(candidate, today=False):
        return _needs(record, candidate, f"Ωh² where its hadronic rate is computed: {why}"), None
    try:
        omega, refused = annihilation.omega_h2(candidate.completion, candidate.particle.mass_gev), ""
    except RelicUnresolved as error:      # still annihilating at the endpoint, say (AL6-01): pending, its reason said
        omega, refused = None, str(error)          # (the auditor's cycle 7, AL7-04: it had escaped as an exception)
    if omega is None or not math.isfinite(omega) or omega < 0:
        why = (f"Ωh², which the relic solver refused here: {refused}" if refused else
               f"Ωh², which the relic solver did not compute here (it gave {omega})")
        return _needs(record, candidate, why), _relic_certificate(
            candidate, record, "", [Check(name="finite_comparisons", state="unknown", reason=why)])
    value, sigma = record.data['value'], record.data['sigma']     # the record bound to the certificate (CT-01)
    ceiling = value + 2.0 * sigma
    band, why, eos = _relic_band(candidate, omega, ceiling)
    certificate = _relic_certificate(candidate, record, "excluded" if omega > ceiling else "viable",
                                     [Check(name="finite_comparisons", state="satisfied"), eos])
    if why:
        return _needs(record, candidate, why, note=f"Ωh² = {omega:.3g} with the nominal degrees of freedom"), certificate
    assumptions = list(record.assumptions) + [band]
    if candidate.particle.mass_splitting_kev:
        assumptions.append("the excited state is treated as degenerate at freeze-out")
    note = f"Ωh² = {omega:.3g}"
    if omega < value - 2.0 * sigma:
        note += (f"; underabundant: it would be {omega / value:.2g} of the dark matter, "
                 "unless another mechanism makes the rest")
    return ConstraintVerdict(constraint_id=record.id, interaction_id=candidate.label,
                             applicability=Applicability.applies_with_assumptions,
                             excluded=omega > ceiling, assumptions=assumptions,
                             note="; ".join(filter(None, [note, _unverified(record)]))), certificate


def _relic_certificate(candidate: Candidate, record: ConstraintRecord, computed: str,
                       checks: list[Check]) -> Certificate:
    """The relic comparison's certificate (M1's claim kind ``relic_comparison``): a finite Ωh² and the same side of
    the ceiling with all three tables; bound to the tables read and to the density's record, verified or not (the auditor's
    CR recheck, CS-02, 2026-10-27), in the version whose value and error the comparison read: ``record`` itself, not
    the record as it reads when the certificate is made (the auditor's CS recheck, CT-01, 2026-10-28). Where that version
    cannot be taken, the comparison is not certified."""
    from adroit.constraints.review_identity import version
    from adroit.parameter_space.certification import eos_held, records_check
    used = version(record)
    return Certificate(claim_kind="relic_comparison", scope=f"{candidate.label}: Ωh² against the relic ceiling",
                       checks=[*checks, *([] if used else [records_check(False, [], [record.id])])],
                       computed_status=computed,
                       bound=Bound(eos_tables=eos_held() if any(c.name == "eos_band" and c.state != "not_applicable"
                                                                for c in checks) else {},
                                   unverified_records=[] if record.usable else [record.id],
                                   records={record.id: used}),
                       policy=POLICY)


def _relic_band(candidate: Candidate, omega: float, ceiling: float) -> tuple[str, str, Check]:
    """(the band's assumption, ""), or ("", why the comparison waits): the owner's decision #3 as on the plane
    (``verdict._eos_band``). Ωh² is computed with Saikawa & Shirai's upper and lower tables as well, and compared with
    the ceiling at each; the same at all three, the comparison stands. Without the tables, or with one not as
    published, it waits, with what to do (the consistency audit's CA-02, 2026-10-24: Ωh² = 0.12 allowed and 0.13
    excluded with the tables missing, where the plane's roots wait for them)."""
    from adroit.constraints import relic
    from adroit.core.certificate import eos_band_assessed, nominal_eos_check
    if not eos_band_assessed():            # the nominal policy (the owner, 2026-11-23): compared at the nominal Ωh²
        return ("Ωh² with ADROIT's nominal equation of state (Saikawa & Shirai's 2018 fit); its uncertainty is not "
                "propagated (deferred to 1.0.2)"), "", nominal_eos_check()
    if missing := relic.band_unavailable():
        return "", missing, Check(name="eos_band", state="unknown", reason=missing)
    values = relic.band_values(lambda: annihilation.omega_h2(candidate.completion, candidate.particle.mass_gev))
    shown = ", ".join(f"{v:.3g} with the {name} table" if v is not None else f"not computed with the {name} table"
                      for name, v in values.items())
    if any(v is None for v in values.values()):
        why = f"Ωh² across the equation of state's band ({shown})"
        return "", why, Check(name="eos_band", state="unknown", reason=why)
    if len({omega > ceiling, *(v > ceiling for v in values.values())}) > 1:
        why = (f"EOS-sensitive: Ωh² = {omega:.3g} with the nominal degrees of freedom, {shown}, against the ceiling "
               f"{ceiling:.4g}: whether it is overabundant depends on the equation of state")
        return "", why, Check(name="eos_band", state="failed", reason=why)
    band = (f"the equation of state's band: Ωh² = {shown}, on the same side of the ceiling; the two supplied tables, "
            "not every equation of state between them")
    return band, "", Check(name="eos_band", state="satisfied", reason=band)


def benchmark_of(completion: Spin1Model) -> str | None:
    """The Working Group benchmark a completion is, if it is one exactly."""
    if completion.flavour_couplings is not None or completion.fermion_masses_gev:
        return None
    for name, (kind, g_q, g_l) in spin1.BENCHMARKS.items():
        if (completion.kind is kind and math.isclose(completion.g_dm, 1.0)
                and math.isclose(completion.g_q, g_q) and math.isclose(completion.g_l, g_l, abs_tol=1e-12)):
            return name
    return None


def excluded_regions(panel: dict) -> dict[str, list[Polygon]]:
    """Each search's excluded region in (log₁₀ m_med, m_DM): its fill, or its contour closed to m_DM = 0."""
    out = {}
    for search, entry in panel["searches"].items():
        shapes = entry.get("excluded_regions") or [
            line + [[line[-1][0], 0.0], [line[0][0], 0.0]] for line in entry["observed"]]
        out[search] = [Polygon(np.column_stack([np.log10([p[0] for p in s]), [p[1] for p in s]]))
                       for s in shapes if len(s) > 2]
    return out


PLANE_M_MED, PLANE_M_DM = (40.0, 1e4), 2000.0     # CMS's summary plane (GeV)
FRAME = 5e-3                                      # the frame's width: points on it are outside
EDGE = 0.03                                       # near the frame: the figure's reach is unreliable (DM13)
EDGE_FLAG = ("unreliable: at the edge of CMS's summary plane (m_med 40 GeV–10 TeV, m_DM ≤ 2 TeV), where the "
             "published figure stops and its kinematic reach does not resolve the collider verdict")


def near_frame(m_med: float, m_dm: float) -> bool:
    """Within 3% of the edge of CMS's plane (in ln m_med, and in m_DM at the top), inside or on it.

    The digitised exclusion regions end at the figure's frame, so a verdict there is not
    resolved by the published reach: the owner's decision (2026-10-03) is to flag such
    points as unreliable rather than call them excluded or allowed.
    """
    low, high = math.log(PLANE_M_MED[0]), math.log(PLANE_M_MED[1])
    x = math.log(m_med)
    return (low <= x <= high and m_dm <= PLANE_M_DM * (1 + FRAME)
            and (x - low < EDGE or high - x < EDGE or m_dm > PLANE_M_DM * (1 - EDGE)))


def collider(candidate: Candidate, record: ConstraintRecord) -> ConstraintVerdict:
    """A published summary applies only to its own benchmark model."""
    completion = candidate.completion
    if completion is None:
        return _needs(record, candidate, NEEDS_COMPLETION.format(what="the mediator's production and decays"))
    if benchmark_of(completion) != record.benchmark or candidate.particle.mass_splitting_kev:
        return _needs(record, candidate, f"a recast of the searches in {record.name} to this model; "
                      f"the summary holds for its benchmark {record.benchmark} only")
    m_med, m_dm = completion.m_med_gev, candidate.particle.mass_gev
    inside = PLANE_M_MED[0] * (1 + FRAME) <= m_med <= PLANE_M_MED[1] * (1 - FRAME) and m_dm <= PLANE_M_DM * (1 - FRAME)
    if not inside:                     # on the frame the digitised regions end, and resolve nothing (DM13)
        return _needs(record, candidate, "the searches' reach outside the summary's plane "
                      "(m_med 40 GeV–10 TeV, m_DM below 2 TeV)")
    panel = database.data(record.id)["panels"][record.benchmark]
    point = (math.log10(m_med), m_dm)
    hits = [name for name, shapes in excluded_regions(panel).items()
            if any(s.contains_point(point) for s in shapes)]
    note = ("excluded by " + "; ".join(hits)) if hits else "outside every observed exclusion"
    return ConstraintVerdict(constraint_id=record.id, interaction_id=candidate.label,
                             applicability=Applicability.applies, excluded=bool(hits),
                             assumptions=list(record.assumptions),
                             note="; ".join(filter(None, [note, _unverified(record)])))


def _reference(kind: str, sigma_cm2: float, mass_gev: float) -> InteractionModel:
    """Pure SD-proton or isoscalar SI scattering at a cross-section: what a telescope's limit assumes."""
    if kind == "SD_proton":
        c = conventions.c4_from_sigma_sd(sigma_cm2, mass_gev)
        term = OperatorCoefficient(operator=4, proton=c, neutron=0.0)
    else:
        c = conventions.c1_from_sigma_si(sigma_cm2, mass_gev)
        term = OperatorCoefficient(operator=1, proton=c, neutron=c)
    return InteractionModel(name=f"reference {kind}", layer="nonrelativistic", coefficients=[term])


def _channel(candidate: Candidate, halo: HaloModel | None = None) -> tuple[str | None, float, list[str]]:
    """(telescope channel, equilibrium fraction or 1, assumptions) for annihilation in the Sun, its capture rate in
    ``halo`` (the default SHM where None; before halo phase 1 the fraction was always taken in the default SHM, even
    where the comparison's capture rates were in another halo)."""
    if candidate.completion is None:
        return "bb", 1.0, ["annihilation into b b̄ (the softest published channel: the weakest limit)",
                           "capture and annihilation in equilibrium"]
    if candidate.completion.spectrum_reference_reason():
        return None,1.0,[candidate.completion.spectrum_reference_reason()]
    channels = annihilation.sigma_v_today(candidate.completion, candidate.particle.mass_gev,
                                          sun_speed(candidate.particle.mass_gev))
    total = sum(channels.values())
    active = [name for name, rate in channels.items() if rate > 0]
    channel = {"b": "bb", "W": "WW", "tau": "tautau"}.get(active[0]) if len(active) == 1 else None
    if channel is None:
        return None, 1.0, []
    c = capture.capture_rate(candidate.particle, candidate.interaction, halo)
    fraction = capture.equilibrium_fraction(c, total, candidate.particle.mass_gev,
                                            self_conjugate=candidate.particle.self_conjugate)   # its population (NA15-05)
    return channel, fraction, [f"pure prompt {channel} final state",
                               f"equilibrium computed: tanh²(t⊙/τ) = {fraction:.3g}"]


def telescope(candidate: Candidate, record: ConstraintRecord, halo: HaloModel | None = None) -> ConstraintVerdict:
    """A neutrino telescope's limit, through capture rates (module docstring)."""
    if candidate.completion is not None and (reason := candidate.completion.spectrum_reference_reason()):
        return _needs(record,candidate,reason)
    if candidate.completion is not None and (why := _hadronic(candidate, today=True)):
        return _needs(record, candidate, f"annihilation in the Sun where its hadronic rate is computed: {why}")
    if not capture.available():                       # never downloaded mid-calculation (the fallback review's D3)
        return _needs(record, candidate, capture.UNAVAILABLE)
    kind = "SD_proton" if record.id.endswith("-sd") else "SI_proton"
    limits = database.data(record.id)["limits"][kind]["limits_cm2"]
    channel, fraction, assumptions = _channel(candidate, halo)
    if channel is None:
        return _needs(record, candidate, "a solar-neutrino spectrum for the mixed/cascade annihilation channels")
    m = candidate.particle.mass_gev
    sigma_limit = database.interpolate_limit(limits[channel], m)
    if sigma_limit is None:
        lowest = min(p[0] for p in limits[channel])
        return _needs(record, candidate, f"a telescope limit at {m:g} GeV; {record.name} starts at "
                      f"{lowest:.0f} GeV for {channel}")
    rate = capture.capture_rate(candidate.particle, candidate.interaction, halo)
    elastic = DarkMatterParticle(mass_gev=m)
    allowed = capture.capture_rate(elastic, _reference(kind, sigma_limit, m), halo)
    excluded = rate * fraction > allowed
    note = (f"C = {rate:.3g}/s{f' × {fraction:.2g}' if fraction < 1 else ''} against {allowed:.3g}/s "
            f"allowed (σ_lim = {sigma_limit:.2g} cm², {channel})")
    if rate == 0.0:
        note = "the Sun cannot capture it: no scattering leaves it bound"
    if candidate.particle.mass_splitting_kev > 0:
        assumptions.append("captured particles settle in the core, although every later scattering "
                           "must also excite the splitting")
    return ConstraintVerdict(constraint_id=record.id, interaction_id=candidate.label,
                             applicability=Applicability.needs_calculation, excluded=None,
                             confidence_level=0.9, native_excluded=excluded,
                             needed_calculation="95% IceCube comparison requires the source likelihood; curve is native 90%",
                             assumptions=[*assumptions, "the Standard Halo Model seen from the Sun" if halo is None or
                                          halo.kind.value == "standard" else f"{halo.label} (its table)",
                                          "the B16 AGSS09 solar model"],
                             note="; ".join(filter(None, [note, _unverified(record)])))




def indirect(candidate: Candidate, record: ConstraintRecord) -> ConstraintVerdict:
    """Gamma rays from dwarf galaxies: a source-supported pure prompt spectrum."""
    if candidate.completion is None:
        return _needs(record, candidate, NEEDS_COMPLETION.format(what="⟨σv⟩ today and its final states"))
    if reason := candidate.completion.spectrum_reference_reason():
        return _needs(record,candidate,reason)
    if why := _hadronic(candidate, today=True):
        return _needs(record, candidate, f"⟨σv⟩ today where its hadronic rate is computed: {why}")
    from adroit.constraints.dwarf_likelihood import RECORD
    if record.id not in ("fermi-1503.02641-dsph", RECORD):     # lines and antiprotons: Track 1's own evaluators
        return _needs(record, candidate, "its comparison (a γ-ray line or antiproton record), which Track 1's searches "
                                         "make; this verdict covers the dwarf-galaxy records only")
    m = candidate.particle.mass_gev
    channels = annihilation.sigma_v_today(candidate.completion, m, DWARF_SPEED)
    from adroit.constraints.indirect import FERMI_CHANNELS, pure_ratio, spectral_comparison
    if record.id == RECORD:
        # Preserve the verified 2015 comparison and avoid combining overlapping data.
        old = database.data("fermi-1503.02641-dsph")["limits"]
        if pure_ratio(channels, m, {k:v["limit_cm3_s"] for k,v in old.items()}, FERMI_CHANNELS, False) is not None:
            return _needs(record, candidate, "overlapping 2024 data omitted; the existing pure-channel comparison is retained")
        result = spectral_comparison(channels, m, False, include_unverified=True)
        if result.ratio is None:
            return _needs(record, candidate, result.why)
        return ConstraintVerdict(constraint_id=record.id, interaction_id=candidate.label,
            applicability=Applicability.applies_with_assumptions, excluded=result.ratio > 1.,
            confidence_level=.95, assumptions=[*record.assumptions, *result.limit.assumptions],
            note="; ".join(filter(None, [f"spectral ⟨σv⟩/profiled upper limit = {result.ratio:.3g}", _unverified(record)])))
    limits = database.data(record.id)["limits"]
    ratio = pure_ratio(channels, m, {k: v["limit_cm3_s"] for k, v in limits.items()}, FERMI_CHANNELS, False)
    if ratio is None:
        return _needs(record, candidate, "a spectral recast for the mixed/cascade final states or off-domain mass")
    assumptions = [*record.assumptions, "published pure prompt final-state spectrum"]
    return ConstraintVerdict(constraint_id=record.id, interaction_id=candidate.label,
                             applicability=Applicability.applies_with_assumptions, excluded=ratio > 1.0,
                             assumptions=assumptions,
                             note="; ".join(filter(None, [f"pure-channel ⟨σv⟩/limit = {ratio:.2g}", _unverified(record)])))


def verdict(candidate: Candidate, record: ConstraintRecord, halo: HaloModel | None = None,
            certificates: dict | None = None) -> ConstraintVerdict:
    """What one record says about one candidate; a certificate made for it put in ``certificates`` by record id."""
    match record.constraint_class:
        case ConstraintClass.relic_density:
            found, certificate = relic_judged(candidate, record)
            if certificates is not None and certificate is not None:
                certificates[record.id] = certificate
            return found
        case ConstraintClass.collider:
            return collider(candidate, record)
        case ConstraintClass.solar_capture:
            return telescope(candidate, record, halo)
        case ConstraintClass.indirect_detection:
            return indirect(candidate, record)
    return _needs(record, candidate, f"a calculator for {record.constraint_class.value} constraints")


def judge(candidate: Candidate, include_unverified: bool = False,
          halo: HaloModel | None = None, certificates: dict | None = None) -> list[ConstraintVerdict]:
    """Every usable record's verdict on the candidate (the certificates made, into ``certificates`` by record id).
    Each record judged is admitted (``searches.admits``), so that the evaluation in force notes its version: the relic
    comparison reads its record's own values, which no data read notes (``judged``)."""
    from adroit.constraints.searches import admits
    rows = [verdict(candidate, r, halo, certificates) for r in database.usable(include_unverified)
            if admits(r, include_unverified)]
    # A successful new spectral recast resolves the old record's mixed-spectrum gap.
    from adroit.constraints.dwarf_likelihood import RECORD
    if any(v.constraint_id == RECORD and v.excluded is not None for v in rows):
        rows = [v for v in rows if v.constraint_id != "fermi-1503.02641-dsph"]
    elif any(v.constraint_id == "fermi-1503.02641-dsph" and v.excluded is not None for v in rows):
        rows = [v for v in rows if v.constraint_id != RECORD]
    return rows


def judged(candidate: Candidate, include_unverified: bool = False, halo: HaloModel | None = None,
           certificates: dict | None = None) -> tuple[list[ConstraintVerdict], dict[str, str]]:
    """``judge``, with the version of each record its verdicts read (``searches.records_read``: "" where two were, or
    the record changed before they were done), for a study to keep beside them (the auditor's CV recheck, CW-02,
    2026-10-30: outside the scan, the complementary verdicts read records that no claim was bound to)."""
    from adroit.constraints.searches import records_read
    with records_read() as read:
        rows = judge(candidate, include_unverified, halo, certificates)
    return rows, read


def summary(verdicts: list[ConstraintVerdict]) -> str:
    """One line for the tournament: exclusions first, then what applies, then what needs work."""
    excluded = [v.constraint_id for v in verdicts if v.excluded]
    allowed = [v.constraint_id for v in verdicts if v.excluded is False]
    pending = [v for v in verdicts if v.applicability is Applicability.needs_calculation]
    parts = []
    if excluded:
        parts.append("excluded by " + ", ".join(excluded))
    if allowed:
        parts.append("allowed by " + ", ".join(allowed))
    if pending:
        parts.append(f"{len(pending)} need a further calculation")
    return "; ".join(parts) or "no usable record"
