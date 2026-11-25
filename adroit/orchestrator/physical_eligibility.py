"""Verify fitted physical points and assess them with Track1's existing evaluator."""
from __future__ import annotations
import math
from pathlib import Path
import numpy as np
from adroit.constraints import eos_reads
from adroit.core.eligibility import CandidateEligibility
from adroit.core.model_spec import STANDARD_COSMOLOGY
from adroit.core.evidence import content_hash
from adroit.orchestrator.model_approval import model_identity

def _match(request,candidate):
    matches=[u for u in request.user_models if candidate.model==(u.catalog_reference or u.spec.name)]
    if len(matches)!=1:
        raise ValueError('an exact unique supplied physical model is required; NR cards/completions are not interchangeable')
    return matches[0]

def _profile_inputs(request):
    if not request.experimental_profile:
        return [],[]
    from adroit.library.experimental_profiles import load
    from adroit.constraints.experimental_review import load_bound as limit
    from adroit.constraints.experimental_search_review import load_bound as search
    profile=load(request.experimental_profile)
    return [limit(n) for n in profile.limits],[search(n) for n in profile.null_modules if n.startswith('private-search:')]

def _current_context(request,model):
    from adroit.evidence.runtime import capture_request
    from adroit.orchestrator.track1 import Track1Request
    return capture_request(Track1Request(spec=model.spec,catalog_reference=model.catalog_reference,
        experimental_profile=request.experimental_profile,unverified_records=request.unverified_records))

def _saved(request,model,cls,point,context):
    """Reuse only exact current, captured model/point/profile/assumption matches: the saved result and its evidence
    one snapshot (``build.read_saved``; the auditor's CW recheck, CX-02, 2026-10-31: a result replaced between two reads
    would have joined its scan to another result's captured provenance). (the point, the result's resolved path, the
    digests of that snapshot's result and evidence bytes, notes): the version reused, kept with the point and reconciled
    with the run's captured inputs (the auditor's CX recheck, CY-01, 2026-11-01: B reused between A at both captures had
    left the run "captured", naming A)."""
    from adroit.evidence.version import resolve
    notes=[]
    for supplied in request.track1_results:
        path=Path(supplied)
        try:
            if path.name.startswith('.env') or path.is_symlink() or not path.is_file():
                raise ValueError('select a regular Track1 result file')
            found=resolve(path)                     # its result and evidence, one version (``evidence.version``)
            snapshot=found.saved()
            envelope=snapshot.envelope
            if envelope.workflow!='track1' or envelope.context.origin!='captured':
                raise ValueError("saved study's evidence lacks captured Track1 provenance")
            result=snapshot.result
            old=result.request
            if old.spec!=model.spec or old.catalog_reference!=model.catalog_reference:
                raise ValueError('model/revision differs')
            if old.experimental_profile!=request.experimental_profile or old.unverified_records!=request.unverified_records:
                raise ValueError('profile or source-review assumptions differ')
            if why := _other_halo(old, request):
                raise ValueError(why)
            if old.private_limits and not request.experimental_profile:
                raise ValueError('saved private selection is not requested')
            if envelope.context.identity!=context.identity or envelope.context.code_sha256!=context.code_sha256:
                raise ValueError('saved scientific inputs/software identity is stale or different')
            if result.scan is None or result.scan.request.model_class!=cls:
                raise ValueError('model engine differs or has no scan')
            rows=[r for r in result.scan.points if r.point==point]
            if not rows:
                raise ValueError('no exact fitted physical point; nearest points cannot be reused')
            if len({content_hash(r.model_dump(mode='json')) for r in rows})!=1:
                raise ValueError('conflicting saved evaluations at the same point')
            return rows[0],str(path.resolve()),(found.result_sha256,snapshot.sidecar_sha256),notes
        except (ValueError,OSError,KeyError) as error:
            notes.append(str(path)+': '+str(error))
    return None,'',('',''),notes

def _other_halo(old, request) -> str:
    """Why a saved Track 1 result's points were calculated with another halo than this run's, or "": a point is
    reused only where its halo is this run's (each search's published halo, or the same fixed benchmark). Before halo
    phase 1 a point judged over the halo region was reused beside fresh published-halo points."""
    from adroit.core.halo_choice import equivalent, resolve
    saved, here = resolve(getattr(old, "halo", None)), resolve(getattr(request, "halo", None), track="track2")
    if equivalent(saved, here):
        return ""
    return f"its points were calculated with {saved.label}, not this run's {here.label}"


def _ties(spec):
    """The model's coupling ties (``classify.coupling_relations``), as the single idea fits with (``single_idea._ties_of``;
    the audit loop's AL4-06, 2026-11-16: Path 2's eligibility had inverted g_chi alone, so a model with g_chi = g_q was
    given a point off it); none where they cannot be stated linearly."""
    from adroit.parameter_space.classify import Unsupported, coupling_relations
    try:
        return tuple(coupling_relations(spec))
    except Unsupported:
        return ()


def _physical(request,candidate,fit,module,model):
    from adroit.parameter_space.classify import classify
    from adroit.parameter_space.physical_fit import predict,fit as bounded_fit
    from adroit.parameter_space.fit_inversion import invert, tied
    from adroit.orchestrator import signal
    from adroit.inference import signal_fit
    cls,reference,_=classify(model.spec)
    base=reference.model_copy(update={'m_chi':candidate.mass_gev})
    ties=_ties(model.spec)                       # a model of one coupling symbol moves both (AL4-06, as AL3-03)
    if candidate.spin!=model.spec.dark_matter.spin or candidate.splitting_kev!=0 or cls.dd(base)[0]=='inelastic':
        raise ValueError('physical particle spin/splitting mapping is not established for this candidate')
    source=signal._signal(module,candidate)
    if source.total_events<=0:
        raise ValueError('no nonzero signal to match to a physical amplitude')
    declared=model.spec.physical_fit
    bounded=None
    events,resolution=module.observations()
    seen=signal_fit.seen_events(source.observable,source.density,resolution)   # the count ŝ is measured against
    try:
        point=invert(cls,base,math.sqrt(fit.s_hat/seen),ties)
        if declared and not declared.low<=point.g_chi<=declared.high:
            raise ValueError('NR optimum outside the declared physical range')
        trial=predict(cls,point,module,candidate.spin)
    except (ValueError,RuntimeError,ArithmeticError):
        bounded=bounded_fit(cls,base,module,candidate.spin,declared,request.eligibility_settings.fit_settings,ties)
        if not bounded.resolved or not bounded.identifiable or bounded.point is None:
            return cls,None,bounded,None,None
        point=tied(bounded.point,ties)                # the fit's point as its predictions took it
        trial=predict(cls,point,module,candidate.spin)
    predicted=cls.interaction(base)
    def scientific(i):
        return i.model_dump(mode='json',exclude={'id','name','references','card_id'})
    if scientific(predicted)!=scientific(candidate.interaction):
        raise ValueError('candidate spectrum parameters differ from the exact model mapping')
    actual=signal._signal(module,signal.Candidate(label=candidate.label,mass_gev=point.m_chi,spin=candidate.spin,interaction=cls.interaction(point)))
    wanted=np.asarray(source.density)*fit.s_hat/seen
    error=float(np.max(np.abs(np.asarray(actual.density)-wanted))/max(float(np.max(np.abs(wanted))),1e-300))
    f=signal_fit.event_densities(source.observable,source.density,events,resolution)
    top=float(signal_fit.profile_log_likelihood(fit.s_hat,f,module.background_at(events),module.background_rate())[0])
    return cls,point,bounded,error,abs(trial.log_l-top)

def _declared(request,model,row):
    """Record the matched model's identity and assumptions; refuse one that cannot establish physical pruning."""
    row.model_sha256=model_identity(model.spec)
    row.catalog_reference=model.catalog_reference
    row.assumptions=[model.spec.cosmology,f'declared relic fraction {model.spec.relic_fraction}',
        'verified applicable Track1 comparisons at native95; no CL/benchmark conversion',
        'NR reference score transferable only after matching the physical spectrum and profile likelihood']
    from adroit.library.personal import support
    if not support(model.spec,model.derivation)['numerically_declared']:
        raise ValueError('physical model has unspecified masses/coefficients; benchmark defaults cannot establish exclusion')
    if request.unverified_records or not request.complementary:
        raise ValueError('verified complementary comparisons are required for physical pruning')
    if model.spec.cosmology!=STANDARD_COSMOLOGY or model.spec.relic_fraction!=1:
        raise ValueError('this eligibility adapter requires declared standard cosmology/full density; no implicit density/history rescaling')

@eos_reads.producer     # its claims bound to the tables as it read them (the auditor's CT recheck, CU-02)
def _judged(request,model,cls,point,row,contexts):
    """Evaluate the verified physical point (an exact saved Track1 point reused) and record its crossing and thermal status."""
    from adroit.parameter_space.verdict import classify as judge,OMEGA
    from adroit.parameter_space.scan import evaluate
    identity_key=(row.model_sha256,model.catalog_reference)
    if identity_key not in contexts:
        contexts[identity_key]=_current_context(request,model)
    context=contexts[identity_key]
    row.source_identity=context.identity
    row.source_sha256=context.code_sha256
    evaluation,path,(result_sha256,evidence_sha256),notes=_saved(request,model,cls,point,context)
    row.reuse_notes=notes
    if evaluation is None:
        limits,searches=_profile_inputs(request)
        from adroit.parameter_space.private_limits import check_applicability
        check_applicability(model.spec,limits)          # the same checks as Track 1's (S18-02)
        extra={k:v for k,v in [('private_limits',limits),('private_searches',searches)] if v}
        evaluation=evaluate(cls,point,False,**extra)
        row.constraints_origin='fresh_track1_point'
    else:
        row.constraints_origin='saved_exact_track1_point'
        row.reused_result=path
        row.reused_result_sha256=result_sha256
        row.reused_evidence_sha256=evidence_sha256
    row.evaluation=evaluation
    crossing=judge(cls,evaluation)
    row.excluded_by=crossing.excluded_by
    row.reasons.extend(crossing.pending)
    row.thermal_target=OMEGA*model.spec.relic_fraction
    omega=evaluation.omega_h2
    row.thermal_status=('uncomputed' if omega is None or not math.isfinite(omega) or omega<=0 else
        'at_declared_target' if abs(omega/row.thermal_target-1)<=THERMAL_TOLERANCE else 'off_target')
    from adroit.core.certificate import Check
    if row.thermal_status!='at_declared_target':
        row.reasons.append('this fitted point is not a resolved declared thermal target; other parameter branches need follow-up')
        eos=Check(name='eos_band',state='not_applicable',reason='not at the declared thermal target')
    else:
        found,eos=_eos_checked(cls,point,omega,row)
        row.reasons.extend(found)
    row.status='excluded_point' if crossing.excluded_by else 'pending' if row.reasons else 'eligible'
    row.certificate=_certificate(request,row,crossing,eos)
    if row.status=='eligible' and not row.certificate.decided:        # the gate (M1): never eligible on an open check
        row.status='pending'
        row.reasons.extend(row.certificate.open_reasons())

def _certificate(request,row,crossing,eos):
    """The claim's certificate (M1): an exclusion of the fixed point (its finite comparisons, records and halo: the
    tables do not decide it), or Path 2's thermal eligibility (the fit matched, at the declared target, the equation
    of state's band, the thermal history and the rest). Discovery requirements are not applied by this adapter, and
    the certificate does not claim them."""
    from adroit.core.certificate import Check
    from adroit.parameter_space import certification
    target={'at_declared_target':Check(name='thermal_target',state='satisfied',reason='Ωh² within 1% of the declared target'),
            'off_target':Check(name='thermal_target',state='failed',reason='this fitted point is not at the declared thermal target'),
            }.get(row.thermal_status,Check(name='thermal_target',state='unknown',reason='Ωh² not computed at this point'))
    fit=Check(name='fit_match',state='satisfied',reason='the physical spectrum and profile likelihood match the NR optimum to 1e-6')
    excluded=bool(crossing.excluded_by)
    kind='fixed_point_exclusion' if excluded else 'path2_thermal_eligibility'
    checks=[fit] if excluded else [fit,target,eos]
    judged=certification.certify(crossing,kind,f'{kind.replace("_"," ")} of {row.label}',checks,
                                 enabled=request.unverified_records,discovery=None)
    return judged.certificate

THERMAL_TOLERANCE=.01      # a fitted point is at the declared thermal target where its Ωh² is within 1% of it

def _eos_band(cls,point,omega,row):
    """``_eos_checked``'s reasons."""
    return _eos_checked(cls,point,omega,row)[0]

def _eos_checked(cls,point,omega,row):
    """Why this fitted point's thermal status is not established across the equation of state's band, or []: the
    owner's decision #3 as on the plane (``verdict._eos_band``), here at a point the fit fixes. Its Ωh² is computed
    with Saikawa & Shirai's upper and lower tables as well; at the declared target with all three, it stands, the
    band among the assumptions; else pending, EOS-sensitive, with the three values. Without the tables, or with one not
    as published, pending with what to do (the consistency audit's CA-02, 2026-10-24: a point at the target was
    eligible with the tables missing, where the plane's root waits for them). An experimental exclusion at the point
    does not depend on the tables, and stands."""
    from adroit.constraints import relic
    from adroit.core.certificate import Check,eos_band_assessed,nominal_eos_check
    if not eos_band_assessed():            # the nominal policy (the owner, 2026-11-23): decided on the nominal Ωh²
        return [],nominal_eos_check()
    if missing:=relic.band_unavailable():
        why=(f'nominal Ωh² is at the target ({omega:.4g}); thermal eligibility across the equation of state\'s band '
             f'is not established: {missing}')
        return [why],Check(name='eos_band',state='unknown',reason=missing)
    values=relic.band_values(lambda:None if hasattr(cls,'domain') and cls.domain(point) else cls.omega_h2(point))
    shown=', '.join(f'{v:.4g} with the {name} table' if v is not None else f'not computed with the {name} table'
                    for name,v in values.items())
    if all(v is not None and abs(v/row.thermal_target-1)<=THERMAL_TOLERANCE for v in values.values()):
        band=(f"the equation of state's band: at the declared target also with Saikawa & Shirai's upper and lower "
              f"tables (Ωh² = {shown}); the two supplied tables, not every equation of state between them")
        row.assumptions.append(band)
        return [],Check(name='eos_band',state='satisfied',reason=band)
    why=(f'EOS-sensitive: nominal Ωh² is at the target ({omega:.4g}); thermal eligibility across the supplied '
         f'tables is not established: Ωh² = {shown} (target {row.thermal_target:.4g}, to {THERMAL_TOLERANCE:.0%})')
    return [why],Check(name='eos_band',state='unknown' if None in values.values() else 'failed',reason=why)

def assess(request,candidates,fits,module):
    """Assess all requested fitted points within a declared budget; missing work is pending."""
    results={}
    contexts={}
    spent=0
    fit_by={f.label:f for f in fits}
    for candidate in candidates:
        row=CandidateEligibility(label=candidate.label)
        results[candidate.label]=row
        try:
            if not request.eligibility_settings.enabled:
                raise ValueError('physical eligibility was not requested')
            model=_match(request,candidate)
            _declared(request,model,row)
            if spent>=request.eligibility_settings.max_candidates:
                raise ValueError('physical candidate assessment budget exhausted')
            spent+=1
            cls,point,bounded,error,ll_error=_physical(request,candidate,fit_by[candidate.label],module,model)
            row.model_class=cls.model_dump(mode='json')
            row.physical_fit=bounded
            row.point=point
            row.spectrum_relative_error=error
            row.delta_log_l_error=ll_error
            if point is None:
                raise ValueError('bounded physical fit is incomplete/nonidentifiable; alternative modes remain unresolved')
            if error is None or not math.isfinite(error) or error>1e-6 or ll_error is None or not math.isfinite(ll_error) or ll_error>1e-6:
                raise ValueError('physical alternative differs from the NR optimum; its NR score cannot establish eligibility')
            _judged(request,model,cls,point,row,contexts)
        except (ValueError,RuntimeError,ArithmeticError,KeyError) as error:
            row.reasons.append(str(error))
    return results
