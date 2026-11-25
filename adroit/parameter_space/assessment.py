"""One assessment of a point, read by every output (the owner's plan of 2026-11-24, "signal-qualified planes and
decisive DD exclusions", section 1).

Four questions are kept apart, each with its own state:

1. **The signal** (``SignalAssessment``): does the model's physical prediction at this exact point meet the declared
   signal criterion, fail it, or lack a completed assessment? The prediction is the model's actual spectrum and
   accepted count (``physical_fit.predict``), only the background profiled: no signal amplitude is fitted, so a point
   whose physical coupling is too weak cannot borrow the reference fit's strength.
2. **The experimental exclusion at the reference halo** (``ExperimentalAssessment``): is the point excluded by an
   applicable comparison at the halo it was first judged at (the region's centre, a fixed benchmark, or the published
   halos), and by which? In cuts mode one supported exclusion suffices: an unrelated search left unfinished does not
   undo it.
3. **Halo robustness** (``RegionalAssessment``): does the conclusion hold throughout the tested halo region, change
   across it, or remain incomplete there?
4. **The thermal requirements** (``ThermalAssessment``): the refined root, its thermal history and the equation of
   state's policy.

A point that fails the signal criterion is not thereby excluded: it does not explain the signal. A central exclusion
is not automatically robust across the halo region. An incomplete thermal check does not erase an experimental
exclusion. These are combined only in ``joint``, the decision table for "a thermal explanation of the signal at this
point", whose rows are listed in ``JOINT``.

The criterion is the study's existing one (``CRITERION``), unchanged: the physical prediction must improve the
likelihood over the background alone by 2ΔlnL ≥ 1 (√q0 ≥ 1). It is neither a discovery threshold nor an absolute
goodness-of-fit test, and at a fixed point it is not a newly calibrated significance.
"""
from __future__ import annotations

import math
from typing import Literal

from pydantic import Field

from adroit.core.state import StrictModel

CRITERION = ("the model's physical prediction at the point improves the likelihood over the background alone by "
             "2ΔlnL ≥ 1 (√q0 ≥ 1); not a discovery threshold, nor an absolute goodness of fit")
THRESHOLD = 1.0                       # on 2ΔlnL: the study's anomaly-fit criterion (single_idea._fit_state)


class SignalAssessment(StrictModel):
    """Question 1 at one point: the physical prediction against the declared signal criterion (``CRITERION``).
    ``improvement`` is 2(lnL − lnL_background), signed: a prediction worse than the background alone keeps its
    negative value. ``halo`` names where the prediction was made (the search's published halo, or a fixed benchmark);
    ``inputs`` binds what it was computed from."""
    state: Literal["meets", "fails", "unassessed"]
    experiment: str = ""
    halo: str = ""
    log_l: float | None = None
    null_log_l: float | None = None
    improvement: float | None = None
    predicted_events: float | None = None
    reason: str = ""
    criterion: str = CRITERION
    inputs: dict[str, str] = Field(default_factory=dict, exclude_if=lambda v: not v)


class ExperimentalAssessment(StrictModel):
    """Question 2: the experimental outcome at the reference halo (``halo``), from the stored comparisons."""
    state: Literal["excluded", "not_excluded", "undecided"]
    halo: str = ""
    excluded_by: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)


class RegionalAssessment(StrictModel):
    """Question 3: robustness over the tested halo region (``one_halo`` where the point was judged at one halo only:
    a fixed benchmark or the published halos)."""
    state: Literal["excluded_throughout", "allowed_throughout", "halo_sensitive", "incomplete", "pending_throughout",
                   "one_halo"]
    detail: str = ""


class ThermalAssessment(StrictModel):
    """Question 4: the thermal requirements (``not_applicable`` for a point that is not a thermal root)."""
    state: Literal["satisfied", "failed", "unknown", "not_applicable"]
    reasons: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)


class PointAssessment(StrictModel):
    """The four answers at one point; ``signal`` is None where no signal is being explained (Constrain a model)."""
    experimental: ExperimentalAssessment
    regional: RegionalAssessment
    thermal: ThermalAssessment
    signal: SignalAssessment | None = Field(default=None, exclude_if=lambda v: v is None)


# --- question 1: the signal ---------------------------------------------------------------------------------------------

def judge_signal(log_l: float | None, null_log_l: float | None, predicted_events: float | None, *, experiment: str,
                 halo: str, reason: str = "", inputs: dict[str, str] | None = None) -> SignalAssessment:
    """The signal assessment from a physical prediction's likelihoods: "meets" where 2(lnL − lnL_background) ≥
    ``THRESHOLD``, "fails" below it, "unassessed" where either likelihood is missing or not finite (``reason`` says
    why)."""
    finite = log_l is not None and null_log_l is not None and math.isfinite(log_l) and math.isfinite(null_log_l)
    if not finite:
        return SignalAssessment(state="unassessed", experiment=experiment, halo=halo, log_l=log_l,
                                null_log_l=null_log_l, predicted_events=predicted_events,
                                reason=reason or "the physical likelihood at this point is not a finite number",
                                inputs=dict(inputs or {}))
    improvement = 2.0 * (log_l - null_log_l)
    return SignalAssessment(state="meets" if improvement >= THRESHOLD else "fails", experiment=experiment, halo=halo,
                            log_l=log_l, null_log_l=null_log_l, improvement=improvement,
                            predicted_events=predicted_events, reason=reason, inputs=dict(inputs or {}))


def signal_at(cls, point, module, spin: float, null_log_l: float, *, experiment: str, halo: str,
              inputs: dict[str, str] | None = None) -> SignalAssessment:
    """``judge_signal`` of the model's physical prediction at ``point`` exactly (``physical_fit.predict``: its actual
    spectrum and accepted count, the background profiled as the experiment permits, no signal amplitude fitted). A
    prediction that cannot be made (outside the model's domain, a non-finite spectrum) is "unassessed", with why."""
    from adroit.parameter_space.physical_fit import predict
    try:
        trial = predict(cls, point, module, spin)
    except (ValueError, RuntimeError, ArithmeticError) as error:
        return judge_signal(None, null_log_l, None, experiment=experiment, halo=halo,
                            reason=f"no physical prediction here: {error}", inputs=inputs)
    return judge_signal(trial.log_l, null_log_l, trial.signal_events, experiment=experiment, halo=halo,
                        inputs=inputs)


# --- questions 2 to 4, from a stored Track 1 point ------------------------------------------------------------------

REGION = {"excluded throughout the tested halo region": "excluded_throughout",
          "allowed throughout the tested halo region": "allowed_throughout",
          "halo-sensitive": "halo_sensitive", "halo coverage incomplete": "incomplete",
          "pending throughout the tested halo region": "pending_throughout"}
THERMAL_CHECKS = ("root", "thermal_history", "eos_band")
QUALIFYING = ("records", "finite_comparisons", "discovery")      # a decisive experiment's own prerequisites
CENTRE = "the region's centre (the Standard Halo Model at v₀ 233, v_esc 528 km/s, ρ₀ 0.4 GeV cm⁻³)"


def nominal_exclusions(c) -> list[str]:
    """The constraints that excluded a stored point at its reference halo: those saved with it (``Crossing.
    nominal_excluded_by``), else, for a point saved before them, its own stored comparisons that excluded (the
    evaluation's ``excluded``), never recomputed."""
    saved = getattr(c, "nominal_excluded_by", None)
    if saved:
        return list(saved)
    evaluation = getattr(c, "evaluation", None)
    found = [k for k, v in ((evaluation.excluded if evaluation is not None else {}) or {}).items() if v]
    return found or list(getattr(c, "excluded_by", []) or [])


def from_crossing(c, signal: SignalAssessment | None = None) -> PointAssessment:
    """The assessment of a stored Track 1 point (a ``verdict.Crossing``), read from what it stores: its status at the
    reference halo (``nominal_status`` over a region, else its constraints' computed status), the constraints that
    excluded it there (``nominal_exclusions``), its region label and its certificate's checks."""
    certificate = getattr(c, "certificate", None)
    checks = {x.name: x for x in (certificate.checks if certificate is not None else [])}
    region = getattr(c, "halo", "") or ""
    over_region = region in REGION
    reference = getattr(c, "nominal_status", "") if over_region else (
        certificate.computed_status if certificate is not None and certificate.computed_status else c.status)
    reference = reference or c.status
    qualifications = [x.reason or x.name for name, x in checks.items() if name in QUALIFYING and x.state in
                      ("failed", "unknown")]
    excluded = reference == "excluded"
    experimental = ExperimentalAssessment(
        state="excluded" if excluded else "not_excluded" if reference == "viable" else "undecided",
        halo=CENTRE if over_region else region or "the halo the point was judged at",
        excluded_by=nominal_exclusions(c) if excluded else [], qualifications=qualifications)
    regional = RegionalAssessment(state=REGION.get(region, "one_halo"), detail=region)
    if getattr(c, "kind", "") not in ("contour", "point") or certificate is None:
        thermal = ThermalAssessment(state="not_applicable" if getattr(c, "kind", "") not in ("contour", "point")
                                    else "unknown", reasons=[] if certificate is not None else ["no certificate"])
    else:
        own = [checks[n] for n in THERMAL_CHECKS if n in checks]
        failed = [x.reason or x.name for x in own if x.state == "failed"]
        unknown = [x.reason or x.name for x in own if x.state == "unknown" and not (x.name == "eos_band" and
                                                                                   _band_waits_on_others(x))]
        thermal = ThermalAssessment(state="failed" if failed else "unknown" if unknown else "satisfied",
                                    reasons=failed or unknown)
    return PointAssessment(experimental=experimental, regional=regional, thermal=thermal, signal=signal)


def _band_waits_on_others(check) -> bool:
    """A band check left unknown only because the point was undecided by its constraints (the earlier policy wrote
    so): not a thermal fault of the point."""
    return (check.reason or "").startswith("not computed: the point is undecided")


# --- the reading --------------------------------------------------------------------------------------------------------

def experimental_words(a: PointAssessment) -> str:
    """The experimental outcome in words, with its halo robustness: "excluded by direct detection throughout the
    tested halo region", "excluded at the region's centre by direct detection; halo robustness incomplete", "...;
    halo-sensitive", or "" where the point is not excluded at its reference halo."""
    e, r = a.experimental, a.regional
    if e.state != "excluded":
        return ""
    by = ", ".join(e.excluded_by) or "its constraints"
    if r.state == "excluded_throughout":
        return f"excluded by {by} throughout the tested halo region"
    if r.state == "one_halo":
        return f"excluded by {by}"
    tail = {"halo_sensitive": "halo-sensitive across the tested region",
            "incomplete": "halo robustness incomplete"}.get(r.state, f"over the region: {r.detail}")
    return f"excluded at the central SHM by {by}; {tail}"


JOINT = {
    "unresolved_signal": "the signal criterion is not assessed here",
    "does_not_explain": "the physical prediction does not meet the signal criterion: it does not explain the signal "
                        "(this is not an experimental exclusion)",
    "not_thermal": "not a thermal solution: a thermal requirement fails",
    "unresolved_thermal": "a thermal requirement is not yet established",
    "excluded": "experimentally excluded at the reference halo",
    "unresolved_experiment": "the constraints do not decide it at the reference halo",
    "unresolved_halo": "allowed at the reference halo but not established across the halo region",
    "explains_one_halo": "a thermal explanation of the signal, the signal and the constraints at the same single halo",
    "explains_published_halo": "meets the signal criterion at the search's published halo and survives the constraints "
                               "throughout the halo region: the two rest on different halo assignments, so this is not "
                               "a halo-robust joint claim",
    "explains": "a thermal explanation of the signal, robust across the tested halo region",
}


def joint(a: PointAssessment, same_halo: bool) -> tuple[str, str]:
    """The decision table (``JOINT``) for "a thermal explanation of the signal at this point": (its row, the reason).
    Read in order: the signal first (a failure is not an exclusion), then the thermal requirements, then the
    experimental outcome at the reference halo, then its robustness. ``same_halo``: whether the signal was assessed at
    the halo the constraints were judged at (a fixed benchmark for both, or the published halos for both); a joint
    claim never silently joins two halo assignments."""
    s = a.signal
    if s is None or s.state == "unassessed":
        return "unresolved_signal", JOINT["unresolved_signal"] + (f" ({s.reason})" if s is not None and s.reason else "")
    if s.state == "fails":
        return "does_not_explain", JOINT["does_not_explain"]
    if a.thermal.state == "failed":
        return "not_thermal", JOINT["not_thermal"] + f" ({'; '.join(a.thermal.reasons)})"
    if a.thermal.state in ("unknown", "not_applicable"):
        return "unresolved_thermal", JOINT["unresolved_thermal"] + (f" ({'; '.join(a.thermal.reasons)})"
                                                                     if a.thermal.reasons else "")
    if a.experimental.state == "excluded":
        return "excluded", experimental_words(a)
    if a.experimental.state == "undecided":
        return "unresolved_experiment", JOINT["unresolved_experiment"]
    if a.regional.state == "one_halo":
        if same_halo:
            return "explains_one_halo", JOINT["explains_one_halo"]
        return "unresolved_halo", ("allowed at one halo, but the signal was assessed at another: no joint claim joins "
                                   "two halo assignments")
    if a.regional.state != "allowed_throughout":
        return "unresolved_halo", JOINT["unresolved_halo"] + f" ({a.regional.detail})"
    return ("explains", JOINT["explains"]) if same_halo else ("explains_published_halo",
                                                              JOINT["explains_published_halo"])


EXPLAINS = ("explains", "explains_one_halo")      # rows that support a joint thermal explanation without qualification


# --- Explain a signal's plane (the owner's plan of 2026-11-24, section 2) ---------------------------------------------

class GridSignal(StrictModel):
    """The signal assessment at one grid point of the plane, compactly (the plane names the experiment and halo)."""
    state: Literal["meets", "fails", "unassessed"]
    improvement: float | None = None
    predicted_events: float | None = None
    reason: str = Field(default="", exclude_if=lambda v: not v)


class SignalPlane(StrictModel):
    """Explain a signal's plane with the signal requirement imposed: the signal assessment at every grid point
    (``grid``, aligned with the plane's scan points) and at every thermal crossing at its own parameters
    (``crossings``, aligned with the plane's crossings, each with its four answers), and each crossing's row of the
    decision table (``joint``). ``same_halo``: whether the signal and the constraints were judged at the same halo
    and density assignment; where not, no crossing is an unqualified joint explanation."""
    experiment: str
    halo: str
    constraints_halo: str
    same_halo: bool
    assignment: str = ""
    criterion: str = CRITERION
    null_log_l: float | None = None
    grid: list[GridSignal] = Field(default_factory=list)
    crossings: list[PointAssessment] = Field(default_factory=list)
    joint: list[str] = Field(default_factory=list)

    def counts(self) -> dict[str, int]:
        """How many crossings fall in each row of the decision table."""
        out: dict[str, int] = {}
        for row in self.joint:
            out[row] = out.get(row, 0) + 1
        return out

    def summary(self) -> str:
        """The plane's joint conclusion in one sentence, from the stored rows."""
        n = len(self.joint)
        if not n:
            return "the constraint plane holds no thermal crossing, so no joint thermal explanation was resolved there"
        meets = sum(a.signal is not None and a.signal.state == "meets" for a in self.crossings)
        counts = self.counts()
        explains = sum(counts.get(r, 0) for r in EXPLAINS)
        qualified = counts.get("explains_published_halo", 0)
        text = (f"on the plane, {meets} of {n} thermal crossing{'s' if n != 1 else ''} meet{'s' if meets == 1 else ''} "
                f"the signal criterion at {self.halo}")
        if explains:
            return text + f"; {explains} {'is a' if explains == 1 else 'are'} joint thermal explanation{'s' if explains != 1 else ''}"
        if qualified:
            return text + (f"; {qualified} survive{'s' if qualified == 1 else ''} the constraints throughout the halo "
                           "region, but the signal and the constraints rest on different halo assignments, so no "
                           "halo-robust joint explanation is established")
        return text + "; no joint thermal explanation was resolved there"


def grid_signal(s: SignalAssessment) -> GridSignal:
    """A grid point's compact signal assessment."""
    return GridSignal(state=s.state, improvement=s.improvement, predicted_events=s.predicted_events,
                      reason=s.reason if s.state == "unassessed" else "")
