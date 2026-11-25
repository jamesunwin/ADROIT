"""Review and numerical validation for the existing fidelity-B event adapter."""
import json
import math
from adroit.core.private_searches import SearchContract,SearchAnchor,SearchValidation,BoundPrivateSearch
from adroit.core.checkpoint import atomic_json,run_lock
from adroit.core.chronology import utc_now
from adroit.core.evidence import content_hash
from adroit.library.experimental import ExperimentalCatalog,SHA
from adroit.constraints.experimental_review import packet,load_review
from adroit.statistics.optimum_interval import OptimumIntervalUnavailable

def source(reference,result_id,catalog=None):
    """(contract, event record, review packet) of a complete event result: its ``search_contract`` and
    ``adapter_validation_reference`` must be source-linked, and the contract's dataset and overlap must agree with
    the result's."""
    from adroit.orchestrator.anomaly_intake import interpretation
    catalog=catalog or ExperimentalCatalog()
    value=packet(reference,result_id,catalog=catalog)
    parsed=interpretation(reference,result_id,catalog)
    if parsed.record is None or parsed.blockers:
        raise ValueError('only complete declared event inputs have this adapter: '+str(parsed.blockers))
    claims={c['key']:c for c in value['scientific']['claims']}
    for key in ('search_contract','adapter_validation_reference'):
        if key not in claims or claims[key]['status'] not in ('sourced','converted'):
            raise ValueError('source-linked '+key+' is required; digitisation/assumption alone cannot validate the adapter')
    contract=SearchContract.model_validate(claims['search_contract']['value'])
    if contract.dataset_id not in value['scientific']['dataset_ids']:
        raise ValueError('contract dataset must match the result dataset identity')
    expected_overlap={'disjoint_from_selected':'disjoint','supersedes':'overlapping','unknown':'unknown'}[contract.overlap]
    if expected_overlap!=value['scientific']['overlap'] or contract.supersedes!=value['scientific']['supersedes']:
        raise ValueError('contract and result overlap/replacement declarations disagree')
    return contract,parsed.record,value

def _prediction(record,anchor):
    """(the record's search, its expected signal at the anchor's mass and σ_SI)."""
    from adroit.experiments.anomaly import RecordSearch
    from adroit.experiments.base import reference_interaction
    from adroit.core.dm_state import DarkMatterParticle,CrossSectionKind
    module=RecordSearch(record)
    conventions=module.conventions()
    return module,module.expected_signal(DarkMatterParticle(mass_gev=anchor.mass_gev),
        reference_interaction(CrossSectionKind.si,anchor.sigma_cm2,anchor.mass_gev),conventions.halo,conventions.nuclear_model)

def calculate(record,anchor,contract=None):
    """The adapter's numbers at one anchor's mass and σ_SI: the expected total events, the event densities, the
    best-fit signal ŝ and its log-likelihood, and the 90% and 95% CL upper limits."""
    from adroit.inference import signal_fit
    module,prediction=_prediction(record,anchor)
    energies,resolution=module.observations()
    f=signal_fit.event_densities(prediction.observable,prediction.density,energies,resolution)
    fit=signal_fit.fit('validation',f,module.background_at(energies),module.background_rate())
    top=signal_fit.profile_log_likelihood(fit.s_hat,f,module.background_at(energies),module.background_rate())[0]
    def upper(cl):
        from adroit.experiments.private_search import interval_upper
        return interval_upper(module.events,prediction,cl,contract.limit_construction) if contract else module.upper_limit(prediction,cl)
    return dict(total_events=prediction.total_events,event_densities=f.tolist(),s_hat=fit.s_hat,log_l_hat=float(top),
                kappa90=upper(.9),kappa95=upper(.95))

def _refuse_true_energy_normalisation(record,anchor,actual,error,tolerance):
    """An anchor whose densities are this code's times ε_W, the share of the window's events seen inside it, was
    computed with the pre-A09 convention (normalised in true energy); it is refused by name, not as a mismatch."""
    from adroit.inference import signal_fit
    if error<=tolerance or not anchor.event_densities:
        return
    module,prediction=_prediction(record,anchor)
    epsilon=signal_fit.seen_fraction(prediction.observable,prediction.density,module.observations()[1])
    legacy=max(abs(a*epsilon-b)/max(abs(b),1e-12) for a,b in zip(actual['event_densities'],anchor.event_densities))
    if legacy<=tolerance:
        raise ValueError('this anchor normalises the event densities in true energy (before the audit A09); '
                         'recompute it normalised on the window as seen, with ŝ the count seen inside the window')

def validate(reference,result_id,tolerance,expected_hash,catalog=None):
    """Recompute the adapter at three or more independent, source-linked anchors spanning the declared mass range,
    and write the validation receipt with each relative error."""
    catalog=catalog or ExperimentalCatalog()
    contract,record,value=source(reference,result_id,catalog)
    if value['scientific_sha256']!=expected_hash:
        raise ValueError('adapter source changed since review')
    revision=catalog.load(reference)
    claims={c.key:c for r in revision.dossier.results if r.result_id==result_id for c in r.claims}
    anchors_claim=claims['adapter_validation_reference']
    original_hashes={s.asset_sha256 for key,c in claims.items() if key!='adapter_validation_reference' for s in c.sources}
    if not anchors_claim.sources or all(s.asset_sha256 in original_hashes for s in anchors_claim.sources):
        raise ValueError('independent adapter anchors need a separate selected source asset')
    from adroit.orchestrator.experimental_extraction import checked_claim,source_units
    _,issues=checked_claim(catalog,revision,anchors_claim,source_units(catalog,reference,False))
    if issues:
        raise ValueError('unchecked adapter reference evidence: '+str(issues))
    anchors=[SearchAnchor.model_validate(a) for a in anchors_claim.value['anchors']]
    masses=[a.mass_gev for a in anchors]
    if len(anchors)<3 or len(set(masses))!=len(masses) or (min(masses),max(masses))!=contract.mass_range:
        raise ValueError('at least three distinct anchors must span the declared domain endpoints')
    reproduced=[]
    errors=[]
    for anchor in anchors:
        if len(anchor.event_densities)!=len(record.events_kev):
            raise ValueError('anchor event density count differs from observations')
        try:
            actual=calculate(record,anchor,contract)
        except OptimumIntervalUnavailable as error:   # the tool's refusal is the review's own, its reason kept: no receipt
            raise ValueError(f'the anchor at {anchor.mass_gev:g} GeV could not be calculated ({error}); '
                             'not validated') from None                  # (the auditor's DV–IE recheck, DW-05)
        expected=anchor.model_dump()
        error={}
        for key in ('total_events','s_hat','log_l_hat','kappa90','kappa95'):
            floor=1 if key in ('s_hat','log_l_hat') else 1e-300
            error[key]=abs(actual[key]-expected[key])/max(abs(expected[key]),floor)
        error['event_densities']=max((abs(a-b)/max(abs(b),1e-12) for a,b in zip(actual['event_densities'],anchor.event_densities)),default=0)
        _refuse_true_energy_normalisation(record,anchor,actual,error['event_densities'],tolerance)
        if any(not math.isfinite(x) for x in error.values()):
            raise ValueError('nonfinite adapter validation result')
        reproduced.append(actual)
        errors.append(error)
    from adroit.core.config import PROJECT_ROOT
    from adroit.orchestrator.track1_identity import tree_identity
    result=SearchValidation(validation_id='0'*64,revision=reference,result_id=result_id,scientific_sha256=expected_hash,
        code_sha256=tree_identity(PROJECT_ROOT/'adroit'),created_at=utc_now(),tolerance=tolerance,anchors=anchors,
        reproduced=reproduced,errors=errors,passed=all(e<=tolerance for row in errors for e in row.values()))
    result.validation_id=content_hash(result.model_dump(mode='json',exclude={'validation_id'}))
    with run_lock(catalog.root):
        atomic_json(catalog.path(f'search_validations/{result.validation_id}.json'),result.model_dump(mode='json'))
    return result

def load_validation(key,catalog=None):
    """A search-validation receipt by its exact ID, refused if it was modified."""
    catalog=catalog or ExperimentalCatalog()
    if not SHA.fullmatch(key):
        raise ValueError('exact search validation identifier required')
    raw=json.loads(catalog.path(f'search_validations/{key}.json').read_text())
    if raw['validation_id']!=key or content_hash({k:v for k,v in raw.items() if k!='validation_id'})!=key:
        raise ValueError('search validation receipt changed')
    return SearchValidation.model_validate(raw)

def bind(reference,result_id,review_id,validation_id,catalog=None):
    """Freeze a reviewed event result, validated under the current code and with declared dataset overlap, as a
    private search."""
    catalog=catalog or ExperimentalCatalog()
    contract,record,value=source(reference,result_id,catalog)
    review=load_review(review_id,catalog)
    validation=load_validation(validation_id,catalog)
    from adroit.core.config import PROJECT_ROOT
    from adroit.orchestrator.track1_identity import tree_identity
    if any(x.scientific_sha256!=value['scientific_sha256'] for x in (review,validation)):
        raise ValueError('review/validation must cover this complete event result')
    if not validation.passed or validation.code_sha256!=tree_identity(PROJECT_ROOT/'adroit'):
        raise ValueError('failed/stale private search validation')
    if contract.overlap=='unknown':
        raise ValueError('declare dataset overlap before binding')
    result=BoundPrivateSearch(search_id='0'*64,revision=reference,result_id=result_id,created_at=utc_now(),
        scientific_sha256=value['scientific_sha256'],contract=contract,record=record,review=review,validation=validation)
    result.search_id=content_hash(result.model_dump(mode='json',exclude={'search_id'}))
    with run_lock(catalog.root):
        atomic_json(catalog.path(f'searches/{result.search_id}.json'),result.model_dump(mode='json'))
    return result

def load_bound(reference,catalog=None):
    """A pinned ``private-search:`` binding, refused if it no longer matches its source, its review or validation
    receipt changed, or the validation is not a pass under the current code."""
    catalog=catalog or ExperimentalCatalog()
    key=reference.removeprefix('private-search:')
    if not reference.startswith('private-search:') or not SHA.fullmatch(key):
        raise ValueError('pinned private-search reference required')
    raw=json.loads(catalog.path(f'searches/{key}.json').read_text())
    if raw['search_id']!=key or content_hash({k:v for k,v in raw.items() if k!='search_id'})!=key:
        raise ValueError('private search binding modified')
    result=BoundPrivateSearch.model_validate(raw)
    contract,record,value=source(result.revision,result.result_id,catalog)
    if contract!=result.contract or record!=result.record or value['scientific_sha256']!=result.scientific_sha256:
        raise ValueError('bound search no longer matches source')
    if load_review(result.review.review_id,catalog)!=result.review or load_validation(result.validation.validation_id,catalog)!=result.validation:
        raise ValueError('bound search review/validation modified')
    from adroit.core.config import PROJECT_ROOT
    from adroit.orchestrator.track1_identity import tree_identity
    if not result.validation.passed or result.validation.code_sha256!=tree_identity(PROJECT_ROOT/'adroit'):
        raise ValueError('private search validation needs renewal under this software')
    return result
