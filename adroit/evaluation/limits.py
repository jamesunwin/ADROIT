"""Limit reproduction (DM10): each module against its collaboration's published limits.

DM3's rule (``experiments.validation``; ``docs/dm3/validate_modules.py``): a mass
passes when the reproduced limit is within a factor 1.3 of the published one, or
reaches it within a 3% shift in mass where the published curve is steeper than 8.
A case is one mass of one published curve, judged by that rule, and marked if it
lies inside the module's validated range. DM3 drew those ranges from the same
comparison, so inside them the suite is a regression test. Each run computes
only its own half's masses (DM3's gate, a decade of contiguous validated range,
needs the whole curve and stays in docs/dm3). As in DM3:
- CRESST-III uses the owner's reading (cut survival in true energy);
- CDMSlite uses its official procedure;
- the xenon searches use DIAMX (slow: minutes per mass).
"""

from __future__ import annotations

from functools import lru_cache

from adroit.core.dm_state import CrossSectionKind, ValidationResult
from adroit.evaluation.core import Case, CaseResult, Suite
from adroit.experiments import validation


def _every(masses: list[float], step: int) -> list[float]:
    out = masses[::step]
    return out if out[-1] == masses[-1] else [*out, masses[-1]]


@lru_cache(maxsize=None)
def _modules() -> dict[str, object]:
    from adroit.experiments.cdmslite import CdmsliteRun2
    from adroit.experiments.cresst_iii import CresstIII2019
    from adroit.experiments.deap3600 import Deap3600
    from adroit.experiments.pico60 import Pico60
    from adroit.experiments.xenon import SEARCHES, DiamxXenon
    out = {"CRESST-III": CresstIII2019(cut_survival="true"), "CDMSlite": CdmsliteRun2(), "PICO-60": Pico60(),
           "DEAP-3600": Deap3600()}
    return out | {f"xenon: {s}": DiamxXenon(s) for s in SEARCHES}


def _trial(name: str, curve) -> list[float]:
    """DM3's trial masses for each module."""
    if name == "CRESST-III":
        return list(curve.masses_gev)
    if name.startswith("xenon"):
        return [float(m) for m in validation.trial_masses(curve, 10)]
    return _every(list(curve.masses_gev), {"CDMSlite": 4, "PICO-60": 5, "DEAP-3600": 3}[name])


def cases() -> list[Case]:
    """One case per trial mass of each module's published curves (DM3's trial masses)."""
    return [Case(suite="limits", id=f"{name}|{curve.kind.value}|{m:.6g}",
                 inputs={"stage": name, "kind": curve.kind.value, "mass_gev": m})
            for name, module in _modules().items() for curve in module.published_limits() for m in _trial(name, curve)]


@lru_cache(maxsize=None)
def _validated(name: str, kind: str, masses: tuple[float, ...]) -> ValidationResult:
    """DM3's comparison at the given masses (one half's), computed once per run."""
    module = _modules()[name]
    curve = next(c for c in module.published_limits() if c.kind.value == kind)
    if name == "CDMSlite":
        return validation.validate(module, curve, list(masses),
                                   limits=lambda m: module.official_limits(curve.kind, m, workers=1))
    return validation.validate(module, curve, list(masses))


def run_case(case: Case) -> CaseResult:
    """Reproduced over published limit at the case's mass, from DM3's comparison over its half's masses; the case
    passes within the tolerance or by the edge clause."""
    name, kind = case.inputs["stage"], case.inputs["kind"]
    masses = tuple(c.inputs["mass_gev"] for c in cases()
                   if c.inputs["stage"] == name and c.inputs["kind"] == kind and c.half is case.half)
    result = _validated(name, kind, masses)
    i = masses.index(case.inputs["mass_gev"])
    ratio = result.reproduced_cm2[i] / result.published_cm2[i]
    passed = 1 / result.tolerance <= ratio <= result.tolerance or result.edge_passes[i]
    validated = _modules()[name].validated_range(CrossSectionKind(kind))
    inside = validated is not None and validated[0] <= case.inputs["mass_gev"] <= validated[1]
    return CaseResult(case_id=case.id, passed=bool(passed), metrics={"ratio": round(ratio, 4),
                      "edge_clause": result.edge_passes[i], "in_validated_range": inside},
                      note=f"reproduced/published = {ratio:.3g}")


def summarise(results: list[CaseResult], cases_: list[Case]) -> dict[str, float | str]:
    """Points within DM3's rule for each module and kind, over all points, and inside the validated ranges."""
    by = {c.id: c for c in cases_}
    out: dict[str, float | str] = {}
    for key in dict.fromkeys(f"{by[r.case_id].inputs['stage']} {by[r.case_id].inputs['kind']}" for r in results):
        rows = [r for r in results if f"{by[r.case_id].inputs['stage']} {by[r.case_id].inputs['kind']}" == key]
        out[key] = f"{sum(bool(r.passed) for r in rows)}/{len(rows)}"
    out["all points within DM3's rule"] = round(sum(bool(r.passed) for r in results) / max(len(results), 1), 3)
    inside = [r for r in results if r.metrics.get("in_validated_range")]
    out["points inside the validated ranges within DM3's rule"] = f"{sum(bool(r.passed) for r in inside)}/{len(inside)}"
    return out


SUITE = Suite(name="limits", description="each module against its published limits, point by point (DM3's rule)",
              cases=cases, run_case=run_case, summarise=summarise)
