"""Explicit numerical reproduction of a selected point or fit, never a hidden rerun."""

from __future__ import annotations

import math
from pathlib import Path
import tempfile
from typing import Any

from adroit.constraints import propagation
from adroit.core.evidence import EvidenceEnvelope
from adroit.evidence.archive import held_bundle, read_bundle
from adroit.evidence.archive_models import ReplayResult
from adroit.evidence.results import result_type
from adroit.parameter_space import halo_region, limits


def replay_bundle(path: Path, *, node_id: str = "n0", index: int = 0,
                  relative_tolerance: float = 1e-7, absolute_tolerance: float = 1e-9,
                  eligibility: bool = False) -> ReplayResult:
    """Recompute one saved physical point or signal/native fit with installed code.

    The bundle's contents are untrusted data. Its code and commands are never executed, and a saved model
    class is never run as given: the class is rebuilt from the bundle's typed model, and a stored class that
    differs from it is refused.

    Args:
        path: evidence ZIP; its code and shell commands are never executed.
        node_id: selected manifest node.
        index: saved grid point or candidate/fit index.
        relative_tolerance: comparison tolerance, reported with the outcome.
        absolute_tolerance: comparison tolerance near zero.
    """
    if index < 0 or not math.isfinite(relative_tolerance) or not math.isfinite(absolute_tolerance) or min(relative_tolerance, absolute_tolerance) < 0:
        raise ValueError("nonnegative index and finite nonnegative tolerances required")
    manifest, files = read_bundle(held_bundle(path))        # one read of its bytes (DC-06)
    node = next((n for n in manifest.nodes if n.id == node_id), None)
    if node is None:
        raise ValueError("unknown archive node")
    saved = result_type(node.workflow).model_validate_json(files[node.result_path])
    evidence = EvidenceEnvelope.model_validate_json(files[node.evidence_path])
    result = ReplayResult(workflow=node.workflow, node=node.id, status="incomplete",
        calculation="selected point/fit only; global toys and other points are not rerun",
        relative_tolerance=relative_tolerance, absolute_tolerance=absolute_tolerance)
    with tempfile.TemporaryDirectory(prefix="adroit-evidence-replay-") as directory:
        try:
            request = _request(evidence, files, Path(directory))
            with (propagation.using(_recorded_propagation(saved)), halo_region.using(_recorded_halo(saved)),
                  limits.exact_environment(_recorded_exact(saved))):
                expected, actual = (_eligibility_point(saved,evidence,index) if eligibility and node.workflow=='signal'
                                    else _calculate(node.workflow, saved, request, index))
        except (OSError, ValueError, RuntimeError, KeyError, IndexError, ArithmeticError) as error:
            result.reasons = [f"incomplete numerical reproduction: {error}"]
            return result
    result.expected, result.actual = expected, actual
    if eligibility:
        result.calculation='selected captured physical eligibility point: Track1 comparisons only; no global toys or model-domain exclusion'
    compared_expected,compared_actual=expected,actual
    if node.workflow=="track1":
        compared_expected,compared_actual,notes=_legacy_point_views(expected,actual)
        result.reasons.extend(notes)
    result.differences = _differences(compared_expected, compared_actual, relative_tolerance, absolute_tolerance)
    result.status = "different" if result.differences else "matched"
    if evidence.context.origin != "captured":
        result.reasons.append(f"saved provenance is {evidence.context.origin}; agreement does not upgrade it")
    return result

def _eligibility_point(saved,evidence,index):
    """Recalculate a captured physical comparison without needing personal catalogs."""
    from adroit.orchestrator.model_approval import model_identity
    from adroit.parameter_space.classify import classify
    from adroit.parameter_space.scan import evaluate
    from adroit.core.private_limits import BoundPrivateLimit
    from adroit.core.private_searches import BoundPrivateSearch
    label=saved.fits[index].label
    row=saved.eligibility.get(label)
    if row is None or row.point is None or row.evaluation is None:
        raise ValueError('selected hypothesis has no captured physical-point evaluation')
    model=next((u for u in saved.request.user_models if model_identity(u.spec)==row.model_sha256
                and u.catalog_reference==row.catalog_reference),None)
    if model is None:
        raise ValueError('captured physical model identity differs')
    cls,_,_=classify(model.spec)
    if cls.model_dump(mode='json')!=row.model_class:
        raise ValueError('physical engine mapping differs')
    limits=[]
    searches=[]
    if saved.request.experimental_profile:
        source=next((s for s in evidence.context.sources if s.id==saved.request.experimental_profile),None)
        if source is None:
            raise ValueError('profile source missing')
        from adroit.core.evidence import content_hash
        profile_id=saved.request.experimental_profile.removeprefix('profile:')
        if source.payload_sha256!=profile_id or content_hash({k:v for k,v in source.metadata.items() if k!='profile_id'})!=profile_id:
            raise ValueError('captured profile identity mismatch')
        for reference in source.metadata['limits']:
            captured=next((s for s in evidence.context.sources if s.id==reference),None)
            if captured is None:
                raise ValueError('private limit source missing')
            if content_hash({k:v for k,v in captured.metadata.items() if k!='limit_id'})!=reference.removeprefix('private-limit:'):
                raise ValueError('captured private limit identity mismatch')
            limits.append(BoundPrivateLimit.model_validate(captured.metadata))
        for reference in source.metadata['null_modules']:
            if not reference.startswith('private-search:'):
                continue
            captured=next((s for s in evidence.context.sources if s.id=='experiment:'+reference),None)
            if captured is None:
                raise ValueError('private null source missing')
            if captured.payload_sha256!=content_hash(captured.metadata):
                raise ValueError('captured private null metadata changed')
            searches.append(BoundPrivateSearch.model_validate(captured.metadata['personal_interpretation']['bound_search']))
    extra={k:v for k,v in [('private_limits',limits),('private_searches',searches)] if v}
    actual=evaluate(cls,row.point,False,**extra)
    return row.evaluation.model_dump(mode='json'),actual.model_dump(mode='json')


def _request(evidence: EvidenceEnvelope, files: dict[str, bytes], folder: Path) -> dict:
    """Restore only a declared user anomaly input; never extract arbitrary paths."""
    import copy
    request = copy.deepcopy(evidence.original_inputs)
    selected=[request.get('experiment',''),*request.get('null_modules',[])]
    restored={}
    for name in selected:
        if not isinstance(name,str) or not name.startswith('private-search:') or name in restored:
            continue
        from adroit.core.evidence import content_hash
        from adroit.core.private_searches import BoundPrivateSearch
        import yaml
        source=next((s for s in evidence.context.sources if s.id=='experiment:'+name),None)
        if source is None or source.payload_sha256!=content_hash(source.metadata):
            raise ValueError('captured private search missing or modified')
        payload=source.metadata['personal_interpretation']['bound_search']
        key=name.removeprefix('private-search:')
        if content_hash({k:v for k,v in payload.items() if k!='search_id'})!=key:
            raise ValueError('private search binding hash mismatch')
        bound=BoundPrivateSearch.model_validate(payload)
        if not bound.validation.passed:
            raise ValueError('captured private search validation did not pass')
        path=folder/(key+'.yaml')
        path.write_text(yaml.safe_dump(bound.record.model_dump(mode='json')))
        restored[name]='record:'+str(path)
    if request.get('experiment') in restored:
        request['experiment']=restored[request['experiment']]
    if 'null_modules' in request:
        request['null_modules']=[restored.get(n,n) for n in request['null_modules']]
    experiment = request.get("experiment", "")
    if isinstance(experiment,str) and experiment.startswith('anomaly:'):
        import yaml
        from adroit.core.anomaly_intake import AnomalyConfirmation
        from adroit.core.evidence import content_hash
        source=next((s for s in evidence.context.sources if s.id=='experiment:'+experiment),None)
        if source is None or source.payload_sha256!=content_hash(source.metadata):
            raise ValueError('captured anomaly interpretation missing or modified')
        payload=source.metadata['personal_interpretation']['confirmation']
        key=experiment.removeprefix('anomaly:')
        if content_hash({k:v for k,v in payload.items() if k!='confirmation_id'})!=key:
            raise ValueError('captured anomaly confirmation identity mismatch')
        confirmation=AnomalyConfirmation.model_validate(payload)
        if confirmation.interpretation.record is None or confirmation.interpretation.blockers:
            raise ValueError('captured interpretation is not calculable')
        target=folder/'anomaly.yaml'
        target.write_text(yaml.safe_dump(confirmation.interpretation.record.model_dump(mode='json')))
        request['experiment']='record:'+str(target)
    if isinstance(experiment, str) and experiment.startswith("record:") and experiment not in restored.values():
        original = Path(experiment.removeprefix("record:")).resolve()
        artifact = next((i for i in evidence.context.inputs
                         if i.role == "user_input" and Path(i.location).resolve() == original), None)
        if artifact is None:
            raise ValueError("user anomaly source was not captured in this legacy archive")
        name = f"inputs/user_input/{artifact.sha256}/{Path(artifact.location).name}"
        if name not in files:
            raise ValueError("captured user anomaly input is unavailable")
        target = folder / "anomaly.yaml"
        target.write_bytes(files[name])
        request["experiment"] = f"record:{target}"
    return request


def _recorded_halo(saved: Any):
    """The halo a saved result was calculated with, put in force for its replay: a Track 1 scan's region or fixed
    benchmark; an Explain a signal or Track 2 request's (its region for its points, its fixed benchmark for its fit,
    nulls and points); None: the published halos. Before halo phase 1 only a Track 1 scan's was read, so a single-idea
    study's points replayed with the published halos whatever region they were judged over."""
    scan = getattr(getattr(saved, "scan", None), "request", None)
    if scan is not None:
        return getattr(scan, "halo", None)
    return halo_region.of(getattr(getattr(saved, "request", None), "halo", None))


def _recorded_exact(saved: Any) -> bool:
    """Whether a saved result's limits were computed directly, never read from the tables: a Track 1 run with exact
    limits or the combined likelihood (``track1.run``), put in force for its replay (the audit loop's AL3-24,
    2026-11-15: a replay had read the tables, and called a matching point different)."""
    request = getattr(saved, "request", None)
    return bool(getattr(request, "exact_limits", False) or getattr(request, "likelihood", None) is not None)


def _recorded_propagation(saved: Any) -> str:
    """The propagation model a saved result used: its scan's or request's; central for results saved before the
    choice existed, which all used the central antiproton bound."""
    for owner in (getattr(getattr(saved, "scan", None), "request", None), getattr(saved, "request", None)):
        value = getattr(owner, "propagation", None)
        if value:
            return value
    return "central"


def _calculate(kind: str, saved: Any, request: dict, index: int) -> tuple[dict, dict]:
    if kind == "track1":
        from adroit.orchestrator.track1 import checked_class
        from adroit.parameter_space.scan import evaluate
        if saved.scan is None:
            raise ValueError("no saved computable scan")
        cls = checked_class(saved.request, saved.scan.request.model_class)
        row = saved.scan.points[index]
        if saved.scan.request.private_searches:
            actual=evaluate(cls,row.point,saved.scan.request.unverified_records,
                private_limits=saved.scan.request.private_limits,private_searches=saved.scan.request.private_searches)
        elif saved.scan.request.private_limits:
            actual=evaluate(cls,row.point,saved.scan.request.unverified_records,
                            private_limits=saved.scan.request.private_limits)
        else:
            actual = evaluate(cls, row.point, saved.scan.request.unverified_records)
        expected, found = row.model_dump(mode="json"), actual.model_dump(mode="json")
        if "model_pending" not in expected:       # saved since F19-07: an older result has none to compare
            found.pop("model_pending", None)
        return expected, found
    if kind in ("signal", "single_idea"):
        return _signal_fit(kind, saved, request, index)
    if kind == "native_joint":
        return _native_fit(saved, request, index)
    raise ValueError(f"point replay is not available for {kind}; saved evidence reconstruction remains available")


def _signal_fit(kind: str, saved: Any, request: dict, index: int) -> tuple[dict, dict]:
    from adroit.experiments.registry import load_module
    from adroit.inference import signal_fit
    from adroit.orchestrator import signal, single_idea, user_models

    module = load_module(request["experiment"])
    if kind == "signal":
        typed = signal.SignalRequest.model_validate(request)
        expected = saved.fits[index]
        candidates = saved.engine_candidates or signal.candidates_for(typed, module)
        candidate = next(c for c in candidates if c.label == expected.label)
    else:
        typed = single_idea.SingleIdeaRequest.model_validate(request)
        candidates = user_models.candidates(typed.spec, typed.masses_gev, typed.derivation)
        band = saved.band[index]
        candidate = next(c for c in candidates if c.mass_gev == band.m_chi)
        if band.reference_interaction is not None:
            candidate = candidate.model_copy(update={"interaction": band.reference_interaction})
    prediction = signal._signal(module, candidate)
    events, resolution = module.observations()
    f = signal_fit.event_densities(module.signal_grid_kev(), prediction.density, events, resolution)
    actual = signal_fit.fit(candidate.label, f, module.background_at(events), module.background_rate())
    if kind == "signal":
        return expected.model_dump(mode="json"), actual.model_dump(mode="json")
    band = saved.band[index]
    return {"s_hat": band.s_hat, "z_local": band.z_local, "events_at_unit": band.events_at_unit}, {
        "s_hat": actual.s_hat, "z_local": actual.z_local,
        "events_at_unit": signal_fit.seen_events(module.signal_grid_kev(), prediction.density, resolution)}


def _native_class(saved: Any, request: dict):
    """(class, reference point) rebuilt from the bundle's typed model; a stored class must equal the class.

    Without a typed model (a standalone result made through the Python API), the saved class is used: a native
    result's class is a simplified model (couplings only; no expressions or files, ``JointResult.model_class``).
    """
    from adroit.core.model_spec import ModelSpec
    from adroit.orchestrator.track1 import MISMATCH
    from adroit.parameter_space.classify import classify
    if "spec" not in request:
        if saved.model_class is None:
            raise ValueError("native physical model contract missing in legacy evidence")
        return saved.model_class, saved.reference_point
    cls, point, _ = classify(ModelSpec.model_validate(request["spec"]))
    if saved.model_class is not None and saved.model_class != cls:
        raise ValueError(MISMATCH)
    return cls, saved.reference_point if saved.model_class is not None else point


def _native_fit(saved: Any, request: dict, index: int) -> tuple[dict, dict]:
    from adroit.experiments.registry import load_module
    from adroit.parameter_space.native_joint import prepare, fit_pair, observed_data

    if saved.domain_fit is not None:
        from adroit.parameter_space.native_domain import evaluator
        if index != 0 or saved.best_point is None or saved.model_class is None or saved.spin is None:
            raise ValueError("native multiparameter replay requires the resolved best point at index zero")
        cls, _ = _native_class(saved, request)
        signal, null = load_module(saved.signal_experiment), load_module(saved.null_experiment)
        evaluate, _ = evaluator(cls,saved.spin,signal,null,observed_data(signal))
        trial = evaluate(saved.best_point)
        expected = {"point":saved.best_point.model_dump(mode="json"),"log_l":saved.domain_fit.log_l,
                    "signal_events":saved.domain_fit.signal_events}
        return expected, {"point":trial.point.model_dump(mode="json"),"log_l":trial.log_l,
                          "signal_events":trial.signal_events}

    if saved.model_class is None and "spec" not in request:
        raise ValueError("native physical model contract missing in legacy evidence")
    cls, point = _native_class(saved, request)
    from adroit.core.model_spec import ModelSpec
    spin = saved.spin if saved.model_class is not None else ModelSpec.model_validate(request["spec"]).dark_matter.spin
    expected = saved.fits[index]
    if expected.point is None or saved.bounds is None or point is None or spin is None:
        raise ValueError("saved native point or bounds unresolved")
    signal, null = load_module(saved.signal_experiment), load_module(saved.null_experiment)
    template = prepare(cls, point.model_copy(update={"m_chi": expected.point.m_chi}),
                       saved.bounds, signal, null, spin)
    actual = fit_pair(template, observed_data(signal), saved.fit_settings)
    return expected.model_dump(mode="json"), actual.model_dump(mode="json")


def _differences(expected: Any, actual: Any, relative: float, absolute: float, key: str = "") -> list[str]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        if expected.keys() != actual.keys():
            return [f"{key}: different fields"]
        return [d for field in expected for d in _differences(expected[field], actual[field], relative, absolute,
                                                            f"{key}/{field}")]
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"{key}: different lengths"]
        return [d for i, (x, y) in enumerate(zip(expected, actual))
                for d in _differences(x, y, relative, absolute, f"{key}/{i}")]
    if isinstance(expected, (float, int)) and not isinstance(expected, bool) and isinstance(actual, (float, int)):
        # A count/log-likelihood tolerance must never hide orders-of-magnitude
        # changes in a cross-section measured in cm² or a small physical coupling.
        near_zero = {"omega_h2", "q0", "log_l", "null_log_l", "s_hat", "signal_events",
                     "z_local", "delta_log_l", "theta_hat", "events_at_unit"}
        tolerance = absolute if key.rsplit("/", 1)[-1] in near_zero else 0.0
        same = (math.isnan(expected) and math.isnan(actual)) or expected == actual or math.isclose(expected, actual,
                                                                                               rel_tol=relative, abs_tol=tolerance)
        return [] if same else [f"{key}: {expected} != {actual}"]
    return [] if expected == actual else [f"{key}: saved/actual value differs"]


def _legacy_direct_detection(expected: dict, left: dict, right: dict) -> list[str]:
    """R2's additive direct-detection records, absent from a point saved before them, compared as absent.

    Verdicts, numbers and every other reason stay strict: only the per-channel list, the ratios'
    sidedness and its note in a limit's construction, and the named "no validated limit" reason of a point
    already undecided are set aside, each with a note.
    """
    notes = []
    if not expected.get("dd_channels") and right.get("dd_channels"):
        left.pop("dd_channels", None)
        right.pop("dd_channels", None)
        notes.append("legacy point has no per-channel direct-detection record; the new one is retained in actual")
    if not expected.get("ratio_sidedness") and right.get("ratio_sidedness"):
        left.pop("ratio_sidedness", None)
        right.pop("ratio_sidedness", None)
        notes.append("legacy point records no limit sidedness; compared without it")
    saved, now = expected.get("statistical_limits") or {}, dict(right.get("statistical_limits") or {})
    for name, limit in saved.items():
        if name in now and limit.get("sidedness", "unknown") == "unknown" and now[name].get("sidedness") != "unknown":
            fixed = dict(now[name], sidedness="unknown")
            for side in (" (one-sided)", " (two-sided)"):
                if fixed.get("construction") == limit.get("construction", "") + side:
                    fixed["construction"] = limit["construction"]
            now[name] = fixed
            notes.append(f"legacy limit '{name}' records no sidedness; compared without it")
    if saved:
        right["statistical_limits"] = now
    undecided = (expected.get("excluded") or {}).get("direct detection") is None
    if undecided and (right.get("excluded") or {}).get("direct detection") is None:
        added = [r for r in right.get("pending", []) if r.startswith("direct detection (") and "no validated limit" in r
                 and r not in expected.get("pending", [])]
        if added:
            right["pending"] = [r for r in right["pending"] if r not in added]
            notes.append("the undecided direct-detection outcome now names its channel; compared without the new reason")
    return notes


def _legacy_point_views(expected: dict,actual: dict) -> tuple[dict,dict,list[str]]:
    """Retain additional new certificates while comparing original saved conclusions exactly."""
    left,right=dict(expected),dict(actual)
    notes=[]
    for field in ("vacuum_certificate","unitarity_certificate","running_certificate","chemical_certificate"):
        if expected.get(field) is None and actual.get(field) is not None:
            left.pop(field,None)
            right.pop(field,None)
            notes.append(f"legacy point has no saved {field}; comparison excludes the new certificate retained in actual")
    if expected.get("chemical_certificate") is None and actual.get("chemical_certificate") is not None:
        # Only the explicit new prerequisite diagnostic is additive. Rates/old exclusions stay strict.
        right["pending"]=[p for p in right.get("pending",[]) if not p.startswith("coannihilation chemical equilibrium:")]
        right["flags"]=[f for f in right.get("flags",[]) if not f.startswith("effective coannihilation relic assumes chemical equilibrium;")]
        notes.append("legacy relic assumed chemical equilibrium; new pending prerequisite retained in actual, original archival conclusion compared separately")
    notes += _legacy_direct_detection(expected, left, right)
    if notes:
        old="complete scalar potential retained; global vacuum/unitarity/RG certificates not yet computed"
        pending="complete scalar potential retained; partial-wave unitarity/RG certificates remain pending"
        current="complete scalar potential retained; RG certificate remains pending"
        # Only these known informational flag migrations are ignored; all other flags compare.
        if old in left.get("flags",[]):
            left["flags"]=[f for f in left["flags"] if f!=old]
            right["flags"]=[f for f in right.get("flags",[]) if f not in (pending,current) and not f.startswith("tree-level scalar vacuum:")]
        elif pending in left.get("flags",[]) and current in right.get("flags",[]):
            left["flags"]=[f for f in left["flags"] if f!=pending]
            right["flags"]=[f for f in right["flags"] if f!=current]
    return left,right,notes
