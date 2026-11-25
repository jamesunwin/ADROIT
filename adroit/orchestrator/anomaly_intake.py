"""Human-confirmed experimental interpretations and bounded Track 2 handoff."""
from __future__ import annotations
import json
from adroit.core.anomaly_intake import AnomalyInterpretation,AnomalyConfirmation
from adroit.core.checkpoint import atomic_json,run_lock
from adroit.core.chronology import utc_now
from adroit.core.evidence import content_hash
from adroit.core.experimental_input import ExperimentalClaim
from adroit.experiments.anomaly import AnomalyRecord,Efficiency,Curve,Halo,Uncertainty,check
from adroit.library.experimental import ExperimentalCatalog,SHA

ADAPTER_ASSUMPTION='historical_unbinned_fidelity_B'
REQUIRED=['target','exposure','energy_scale','window','events','resolution','background_count',
          'background_treatment','efficiency','efficiency_space','exposure_selection','halo']


def interpretation(reference: str,result_id: str,catalog: ExperimentalCatalog | None=None) -> AnomalyInterpretation:
    """Explain exact source classification and readiness without applying exclusions."""
    catalog=catalog or ExperimentalCatalog()
    r=catalog.load(reference)
    result=next((item for item in r.dossier.results if item.result_id==result_id),None)
    if result is None:
        raise ValueError('selected result is not in the pinned experimental revision')
    claims={c.key:c for c in result.claims}
    blockers=[]
    record=None
    assumptions=[c.key for c in result.claims if c.status=='assumed']
    warnings=[c.key+': '+c.note for c in result.claims if c.note]
    if result.kind!='events':
        blockers.append({'binned':'Histogram retained as bins; binned adapter is pending M36.5f.',
                         'limit':'A published limit is not an event likelihood.',
                         'likelihood':'Native likelihood/workspace loader requires a validated supported adapter.'}.get(result.kind,
                         'Selected response/background/reference is not an observed event search.'))
    else:
        missing=[key for key in REQUIRED if key not in claims or claims[key].value is None or
                 claims[key].status not in ('sourced','converted','assumed')]
        blockers += ['Missing/conflicting/unsupported interpretation: '+key for key in missing]
        if not missing:
            v={k:c.value for k,c in claims.items()}
            if v['energy_scale']!='keVnr':
                blockers.append('Only nuclear-recoil energy keVnr is supported; no implicit quenching conversion.')
            if v['efficiency_space']!='true_energy':
                blockers.append('Adapter requires declared efficiency in true recoil energy.')
            if v['exposure_selection']!='before_selection':
                blockers.append('Exposure must be before the efficiency selection; double application is refused.')
            if v['background_treatment'] not in ('fixed_flat','fixed_shape','profile_flat','profile_shape'):
                blockers.append('Declare fixed/profiled flat/binned-shape background reconstruction.')
            try:
                if v['background_count']<=0:
                    blockers.append('Finite-significance event adapter needs positive background; no invented floor.')
            except TypeError:
                blockers.append('Background count is not numeric.')
            if v.get('response_matrix') is not None:
                blockers.append('Multidimensional response needs a dedicated adapter.')
            if v.get('correlated_nuisances') is not None:
                blockers.append('Correlated nuisance model needs a dedicated adapter.')
            if not blockers:
                try:
                    record=_record(r,claims,result_id)
                except (ValueError,TypeError,KeyError) as error:
                    blockers.append('Event adapter inputs: '+str(error))
            assumptions.append(ADAPTER_ASSUMPTION)
    explanation=(f'{result_id} is {result.kind}. '+('Supported exploratory event reconstruction using supplied response/background/halo; '
        'source review remains pending.' if record is not None else 'Stored for review; calculation blocked: '+'; '.join(blockers)))
    out=AnomalyInterpretation(revision=reference,result_id=result_id,kind=result.kind,explanation=explanation,
        record=record,blockers=blockers,assumptions=sorted(set(assumptions)),evidence_warnings=warnings)
    out.interpretation_sha256=content_hash(out.model_dump(mode='json',exclude={'interpretation_sha256'}))
    return out


def acknowledgement(claim: ExperimentalClaim) -> str:
    """How a researcher accepts one assumed claim: its key, with its value and units when it carries one."""
    if claim.value is None:
        return claim.key
    shown = claim.value if isinstance(claim.value,str) else json.dumps(claim.value,sort_keys=True,separators=(',',':'))
    return f"{claim.key}={shown}"+(f" {claim.units}" if claim.units else "")


def acknowledgements(reference: str,result_id: str,catalog: ExperimentalCatalog | None=None) -> list[str]:
    """Every acknowledgement a confirmation needs: each assumed value as ``key=value units``, and each
    adapter approximation by name."""
    catalog=catalog or ExperimentalCatalog()
    value=interpretation(reference,result_id,catalog)
    result=next(item for item in catalog.load(reference).dossier.results if item.result_id==result_id)
    claims={c.key:c for c in result.claims if c.status=='assumed'}
    return [acknowledgement(claims[key]) if key in claims else key for key in value.assumptions]


def _record(revision,claims: dict[str,ExperimentalClaim],result_id: str) -> AnomalyRecord:
    """Map a declared observation to the existing deterministic event adapter."""
    v={k:c.value for k,c in claims.items()}
    shape=None
    uncertainty=None
    import math
    def real(n):
        return isinstance(n,(int,float)) and not isinstance(n,bool) and math.isfinite(n)
    if any(not real(v[k]) for k in ('exposure','resolution','background_count')):
        raise ValueError('counts/exposure/resolution require finite numerical values, not strings/booleans')
    if any(not isinstance(v[k],list) or any(not real(n) for n in v[k]) for k in ('events','window')):
        raise ValueError('event/window arrays require finite numerical values')
    if v['background_treatment'].endswith('shape'):
        raw=v.get('background_shape')
        if not isinstance(raw,dict):
            raise ValueError('background shape needs explicit edges/counts')
        from adroit.experiments.anomaly import check_background_bins
        check_background_bins(raw.get('edges_kev',[]),raw.get('counts',[]),tuple(v['window']))
        shape={'points':raw}
    if v['background_treatment'].startswith('profile'):
        raw=v.get('background_uncertainty')
        if not isinstance(raw,dict):
            raise ValueError('profiling needs declared independent plus/minus errors')
        uncertainty=Uncertainty.model_validate(raw)
        if not uncertainty.plus or len(uncertainty.plus)!=len(uncertainty.minus):
            raise ValueError('background errors must have paired components')
    elif v.get('background_uncertainty') is not None:
        raise ValueError('reported background uncertainty cannot silently be discarded; select profile treatment')
    if not isinstance(v['halo'],dict) or set(v['halo'])!={'v0_km_s','v_earth_km_s','v_esc_km_s','rho_gev_cm3'}:
        raise ValueError('all four declared halo parameters are required')
    if claims['exposure'].units!='kg day' or any(claims[k].units!='keVnr' for k in ('resolution','events','window')):
        raise ValueError('canonical exposure/energy units must be declared or explicitly converted')
    record=AnomalyRecord(name=revision.dossier.title+' / '+result_id,target=v['target'],
        references=revision.dossier.references or [revision.reference],exposure_kg_day=v['exposure'],window_kev=v['window'],
        events_kev=v['events'],resolution_kev=v['resolution'],background_events=v['background_count'],
        efficiency=Efficiency(points=Curve.model_validate(v['efficiency'])),halo=Halo.model_validate(v['halo']),
        background_shape=shape,background_uncertainty=uncertainty,
        background_note='Explicit '+v['background_treatment']+' reconstruction; source review pending.',
        resolution_note='Declared constant Gaussian sigma; fidelity-B reconstruction.',halo_note='Explicit interpreted/assumed parameters.',
        sources={key:json.dumps(c.sources[0].model_dump(mode='json')) if c.sources else 'researcher-declared assumption: '+c.note for key,c in claims.items()})
    from adroit.retrieval.experimental_ingestion import finite_json
    finite_json(record.model_dump(mode='python'))
    problems=check(record)
    if problems:
        raise ValueError('; '.join(problems))
    return record


def confirm(reference: str,result_id: str,expected_hash: str,researcher: str,*,confirmed: bool,
            accepted_assumptions: list[str],catalog: ExperimentalCatalog | None=None) -> AnomalyConfirmation:
    """Bind interpretation consent; never sign an experimental source."""
    catalog=catalog or ExperimentalCatalog()
    value=interpretation(reference,result_id,catalog)
    if not confirmed or not researcher.strip():
        raise ValueError('researcher confirmation and name are required')
    if value.interpretation_sha256!=expected_hash:
        raise ValueError('interpretation changed since review')
    missing=[token for token in acknowledgements(reference,result_id,catalog) if token not in accepted_assumptions]
    if missing:
        raise ValueError('accept each assumed value and approximation as displayed: '+'; '.join(missing))
    revision=catalog.load(reference)
    if any(catalog.ingestion(a).kind=='text' for a in revision.ingestions):
        cursor=revision
        found=False
        while True:
            if cursor.provenance.get('extraction_session'):
                found=True
                break
            if not cursor.parent_revision:
                break
            cursor=catalog.load(f'experimental:{cursor.experiment_id}@{cursor.parent_revision}')
        if not found:
            raise ValueError('plain text needs API interpretation before confirmation')
    body=dict(created_at=utc_now(),researcher=researcher.strip(),interpretation=value.model_dump(mode='json'),
              accepted_assumptions=accepted_assumptions,source_review='unreviewed',
              use='exploratory interpretation; not source verification or experiment activation')
    result=AnomalyConfirmation(confirmation_id=content_hash(body),**body)
    with run_lock(catalog.root):
        atomic_json(catalog.path(f'confirmations/{result.confirmation_id}.json'),result.model_dump(mode='json'))
    return result


def load_confirmation(reference: str,catalog: ExperimentalCatalog | None=None) -> AnomalyConfirmation:
    """Verify immutable confirmation and exact underlying source revision."""
    catalog=catalog or ExperimentalCatalog()
    key=reference.removeprefix('anomaly:')
    if not reference.startswith('anomaly:') or not SHA.fullmatch(key):
        raise ValueError('an exact anomaly confirmation is required')
    raw=json.loads(catalog.path(f'confirmations/{key}.json').read_text())
    result=AnomalyConfirmation.model_validate(raw)
    if result.confirmation_id!=key or content_hash({k:v for k,v in raw.items() if k!='confirmation_id'})!=key:
        raise ValueError('anomaly confirmation integrity mismatch')
    current=interpretation(result.interpretation.revision,result.interpretation.result_id,catalog)
    if current.interpretation_sha256!=result.interpretation.interpretation_sha256:
        raise ValueError('confirmed interpretation no longer matches source inputs')
    return result


def readiness(reference: str,catalog: ExperimentalCatalog | None=None) -> AnomalyConfirmation:
    """Refuse blocked descriptions before any physics calculation."""
    result=load_confirmation(reference,catalog)
    if result.interpretation.record is None or result.interpretation.blockers:
        raise ValueError('Anomaly calculation blocked: '+'; '.join(result.interpretation.blockers))
    return result
