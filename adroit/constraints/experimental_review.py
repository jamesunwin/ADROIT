"""Scoped personal source approval and independent published-value validation."""
from __future__ import annotations
import json
from pathlib import Path
import math
from adroit.core.checkpoint import atomic_json,run_lock
from adroit.core.chronology import utc_now
from adroit.core.evidence import content_hash
import re
from adroit.core.experimental_input import SourceLocator
from adroit.core.private_limits import (AnchorCheck,FigureVerification,LimitContract,SourceReview,LimitValidation,
                                        BoundPrivateLimit)
from adroit.library.experimental import ExperimentalCatalog,SHA

CHECKLIST=['source_values','source_units_axes','confidence_construction','benchmark_assumptions',
           'dataset_overlap','digitisation_uncertainty']
FIGURE_CHECKLIST=['calibrated_overlay_inspected','full_mass_range_reviewed','printed_anchors_checked',
                  'axes_units_and_scales','same_result_as_anchors']
ANCHORS={'si_isoscalar_curve':3,'sm_higgs_invisible':1}
SCOPES={'separate_source':'Published-value transcription/adapter interpolation; no reconstructed experimental likelihood.',
        'same_paper_text':'Figure transcription checked against published text (the same paper); not independent '
                          'confirmation of the experiment; no reconstructed experimental likelihood.',
        'mixed':'Checked against a separate source and, for the figure transcription, against published text of the '
                'same paper; no reconstructed experimental likelihood.',
        'manual_figure':'Manually verified against the figure with limited numerical anchors ({n} printed); not the '
                        'ordinary three-anchor validation; no reconstructed experimental likelihood.'}
# An expected sensitivity, not merely the word "expected" ("corresponding to an expected 3.2 signal events", LUX 2016)
# or "sensitivity" ("improving sensitivity by a factor of two" describes an improvement; the focused audit's FA-02).
EXPECTED=re.compile(r'\b(?:expected|median|projected)\s+(?:sensitivit(?:y|ies)|limits?|upper\s+limits?|exclusions?|'
                    r'reach)|\bforecast|\bprojection',re.I)
# A combined result, not "combined systematic uncertainties".
COMBINED=re.compile(r'\bcombin(?:ed|ation)\s+(?:of\s+(?:the\s+)?)?(?:\w+\s+)?(?:limits?|results?|analys[ie]s|data(?:sets?)?|'
                    r'exposures?|runs?|searches|fits?|likelihoods?)\b',re.I)
OTHER_INTERACTION=re.compile(r'spin[- ]dependent|\bSD\b|neutron[- ]only|proton[- ]only',re.I)
CL_PRINTED=re.compile(r'(\d+(?:\.\d+)?)\s*(?:%|percent\b|per\s+cent\b)\s*(?:C\.?\s*L\.?|confidence)',re.I)
# A run or dataset the quotation names ("Run B", "Run II", "WS2014", "SR1"), to be one of the curve's: a name looks
# like one, a capital letter, a Roman numeral or a token with a digit (the recheck's FR-02: "an exposure of" and "the
# dataset collected" name no run).
RUN_NAME=re.compile(r'\b(?i:(?:science\s+)?(?:run|data[- ]?set|exposure))\s+((?:[A-Z]|[IVX]+|[A-Za-z]*\d[\w.+-]*)(?![\w+-]))'
                    r'|\b((?i:WS|SR|Run)\d[\w.+-]*)')
OBSERVED=re.compile(r'\bobserved\b',re.I)
# A source that states it was derived from a figure or another export: not separate evidence (FA-01).
DERIVED=re.compile(r'digiti[sz]|re-?export|\bexported\b|read\s+(?:off|from)\s+(?:the\s+)?fig|webplot|plot\s*digit',re.I)
LINEAGE=('printed_text','published_table')
# A table column that states another result than an observed limit (an expected or median sensitivity, its band)
HEADER_EXPECTED=re.compile(r'expected|median|projected|sensitivit|forecast|[±+-]\s*[12]\s*(?:σ|sigma)|\bband\b',re.I)
HEADER_CL=re.compile(r'(?:\bC\.?\s*L\.?|confidence)[^0-9]{0,12}(\d+(?:\.\d+)?)\s*%|(\d+(?:\.\d+)?)\s*%\s*(?:C\.?\s*L\.?|confidence)',re.I)
MASS_UNIT=re.compile(r'\s*(?:GeV|TeV|MeV)(?:\s*/?\s*c\s*(?:\^\s*\{?\s*[-−]?\s*2\s*\}?|[-−]\s*2|⁻²|²|2))?(?![A-Za-z])')
XS_UNIT=re.compile(r'\s*(?:cm\s*(?:\^\s*\{?\s*2\s*\}?|²|2)|[zafpn]b)\b',re.I)
CLAUSE=re.compile(r'(?<=[.;!?])\s+(?=[A-Z(\[])|;\s*|\n\s*\n')

def packet(reference: str,result_id: str,keys: list[str] | None=None,catalog: ExperimentalCatalog | None=None) -> dict:
    """Build source-selected review content, preserving missing/ambiguous claims."""
    catalog=catalog or ExperimentalCatalog()
    revision=catalog.load(reference)
    result=next((r for r in revision.dossier.results if r.result_id==result_id),None)
    if result is None:
        raise ValueError('selected result not in the pinned revision')
    selected=[c for c in result.claims if keys is None or c.key in keys]
    if not selected or (keys and len(selected)!=len(set(keys))):
        raise ValueError('select existing distinct claim keys')
    hashes={s.asset_sha256 for c in selected for s in c.sources}
    assets=[a for a in revision.sources if a.sha256 in hashes]
    scientific={'experiment_id':revision.experiment_id,'result_id':result_id,'kind':result.kind,
        'source_context':{'references':revision.dossier.references,'publication_date':str(revision.dossier.publication_date or ''),
                          'collaboration':revision.dossier.collaboration,'detector':revision.dossier.detector,'analysis':revision.dossier.analysis,
                          'common_claims':[c.model_dump(mode='json') for c in revision.dossier.claims]},
        'dataset_ids':result.dataset_ids,'supersedes':result.supersedes,'overlap':result.overlap,
        'claims':[c.model_dump(mode='json') for c in sorted(selected,key=lambda c:c.key)],
        'source_assets':[a.model_dump(mode='json') for a in sorted(assets,key=lambda a:a.sha256)]}
    warnings=[c.key+': '+c.status for c in selected if c.status not in ('sourced','converted','digitised','assumed','not_applicable','not_reported')]
    previous=None
    differences=[]
    if revision.parent_revision:
        parent=catalog.load(f'experimental:{revision.experiment_id}@{revision.parent_revision}')
        old=next((r for r in parent.dossier.results if r.result_id==result_id),None)
        if old:
            previous=old.model_dump(mode='json')
            before={c.key:c.model_dump(mode='json') for c in old.claims}
            differences=[{'key':c.key,'previous':before.get(c.key),'current':c.model_dump(mode='json')} for c in selected if before.get(c.key)!=c.model_dump(mode='json')]
    return {'revision':reference,'result_id':result_id,'keys':[c.key for c in selected],
        'scientific_sha256':content_hash(scientific),'scientific':scientific,'warnings':warnings,
        'source_files':[str(catalog.asset_path(a)) for a in assets], 'previous':previous,'differences':differences,
        'required_checks':CHECKLIST,'scope':'Expert source assertion; it neither creates nor validates a numerical adapter.'}

def approve(reference: str,result_id: str,expected_hash: str,researcher: str,*,confirmed: bool,
            checks: list[str],keys: list[str] | None=None,note: str='',catalog: ExperimentalCatalog | None=None) -> SourceReview:
    """Sign only the displayed scientific scope, under the actual researcher's name."""
    catalog=catalog or ExperimentalCatalog()
    value=packet(reference,result_id,keys,catalog)
    if not confirmed or not researcher.strip() or not set(CHECKLIST)<=set(checks):
        raise ValueError('expert source review requires name, explicit attestation and all displayed checks')
    if value['scientific_sha256']!=expected_hash:
        raise ValueError('scientific source changed since the displayed review')
    if value['warnings']:
        raise ValueError('unresolved/conflicting claims cannot receive source approval')
    body=dict(signed_revision=reference,result_id=result_id,keys=value['keys'],scientific_sha256=expected_hash,
              researcher=researcher.strip(),reviewed_at=utc_now(),checklist=checks,note=note)
    result=SourceReview(review_id=content_hash(body),**body)
    with run_lock(catalog.root):
        atomic_json(catalog.path(f'reviews/{result.review_id}.json'),result.model_dump(mode='json'))
    return result

def approve_by_model(check,catalog: ExperimentalCatalog | None=None) -> SourceReview:
    """Sign a result's displayed scope on a language model's passed check (``record_check.RecordCheck``), at the
    researcher's choice (the owner, 2026-11-18, the post-review changes item 2): the review names the model and
    its check and says it is not a person's. Refused as a person's review is (a changed source, unresolved claims),
    and unless the check passed on this very scope."""
    from adroit.core.pricing import model_name
    catalog=catalog or ExperimentalCatalog()
    value=packet(check.revision,check.result_id,check.keys,catalog)
    if not check.passed:
        raise ValueError('a record check that did not pass cannot approve the record')
    if value['scientific_sha256']!=check.scientific_sha256:
        raise ValueError('scientific source changed since the record check')
    if value['warnings']:
        raise ValueError('unresolved/conflicting claims cannot receive source approval')
    body=dict(signed_revision=check.revision,result_id=check.result_id,keys=value['keys'],
              scientific_sha256=check.scientific_sha256,researcher=f'{model_name(check.model)} (a model check, not a '
              'person)',reviewed_at=utc_now(),checklist=list(CHECKLIST),
              note=f'Checked by {model_name(check.model)} (record check {check.check_id}), at the researcher\'s choice '
                   'in place of a person\'s review.',checked_by_model=check.model,check_id=check.check_id)
    result=SourceReview(review_id=content_hash(body),**body)
    with run_lock(catalog.root):
        atomic_json(catalog.path(f'reviews/{result.review_id}.json'),result.model_dump(mode='json'))
    return result

def load_review(review_id: str,catalog: ExperimentalCatalog | None=None) -> SourceReview:
    """A source-review receipt by its exact ID, refused if the receipt was modified or the reviewed source has
    changed since it was signed."""
    catalog=catalog or ExperimentalCatalog()
    if not SHA.fullmatch(review_id):
        raise ValueError('exact source review ID required')
    raw=json.loads(catalog.path(f'reviews/{review_id}.json').read_text())
    if content_hash({k:v for k,v in raw.items() if k!='review_id'})!=review_id:
        raise ValueError('source review receipt modified')
    result=SourceReview.model_validate(raw)
    if result.review_id!=review_id:
        raise ValueError('review ID mismatch')
    if packet(result.signed_revision,result.result_id,result.keys,catalog)['scientific_sha256']!=result.scientific_sha256:
        raise ValueError('reviewed source bytes or assumptions changed')
    return result

def current_review(reference: str,result_id: str,catalog: ExperimentalCatalog | None=None) -> SourceReview | None:
    """Find a complete current result-scope assertion; partial review stays partial."""
    catalog=catalog or ExperimentalCatalog()
    value=packet(reference,result_id,catalog=catalog)
    found=[]
    for path in catalog.path('reviews').glob('*.json'):
        try:
            review=load_review(path.stem,catalog)
            if review.scientific_sha256==value['scientific_sha256']:
                found.append(review)
        except (ValueError,OSError):
            continue
    return max(found,key=lambda r:r.reviewed_at) if found else None

def limit_contract(reference: str,result_id: str,catalog: ExperimentalCatalog | None=None) -> tuple[LimitContract,dict]:
    """(contract, review packet) of a published-limit result; its limit and validation reference must be sourced,
    converted or digitised."""
    catalog=catalog or ExperimentalCatalog()
    value=packet(reference,result_id,['limit_contract','validation_reference'],catalog)
    if value['scientific']['kind']!='limit':
        raise ValueError('selected result is not a published limit')
    claims={c['key']:c for c in value['scientific']['claims']}
    if any(c['status'] not in ('sourced','converted','digitised') for c in claims.values()):
        raise ValueError('limit and reference need sourced finite data, not missing/assumed/conflicting values')
    return LimitContract.model_validate(claims['limit_contract']['value']),value

def interpolate(contract: LimitContract,mass: float) -> float | None:
    """Declared source-coordinate interpolation, never outside the curve/domain."""
    if contract.adapter=='sm_higgs_invisible':
        return contract.value
    if not contract.mass_range[0]<=mass<=contract.mass_range[1]:
        return None
    import numpy as np
    xs=[p[0] for p in contract.points]
    ys=[p[1] for p in contract.points]
    x=math.log(mass) if contract.x_scale=='log' else mass
    xx=np.log(xs) if contract.x_scale=='log' else xs
    yy=np.log(ys) if contract.y_scale=='log' else ys
    value=float(np.interp(x,xx,yy))
    return math.exp(value) if contract.y_scale=='log' else value


def validate(reference: str,result_id: str,tolerance: float,expected_hash: str,catalog: ExperimentalCatalog | None=None) -> LimitValidation:
    """Compare adapter output with reference anchors, each with numerical evidence of its own: a separate source, or,
    for a curve digitised from a figure, a quotation of the same paper's printed text (``anchor_checks``). An SI
    curve needs three anchors; a figure-digitised one with fewer can be verified by hand (``verify_figure``)."""
    catalog=catalog or ExperimentalCatalog()
    contract,checks=_checked(reference,result_id,tolerance,expected_hash,catalog)
    required=ANCHORS[contract.adapter]
    if len(checks)<required:
        hint=' (a curve digitised from a figure can be verified by hand: verify-figure)' if contract.origin=='figure_digitised' else ''
        raise ValueError(f'insufficient independent benchmark anchors: {len(checks)}, the validation needs {required}{hint}')
    return _receipt(reference,result_id,expected_hash,contract,checks,tolerance,catalog)

def _checked(reference: str,result_id: str,tolerance: float,expected_hash: str,catalog: ExperimentalCatalog) -> tuple[LimitContract,list[AnchorCheck]]:
    """(contract, anchor checks) of a limit and its validation reference, after the source checks every claim gets."""
    contract,value=limit_contract(reference,result_id,catalog)
    if value['scientific_sha256']!=expected_hash:
        raise ValueError('validation source changed')
    claims={c['key']:c for c in value['scientific']['claims']}
    reference_claim=claims['validation_reference']
    anchors=reference_claim['value']['points']
    if not reference_claim['sources']:
        raise ValueError('validation anchors require source evidence')
    if any(s.get('method')=='visual' for s in reference_claim['sources']):
        raise ValueError('validation anchors cannot be read from a figure: quote printed values')
    if len({float(x) for x,y in anchors})!=len(anchors):
        raise ValueError('duplicate validation anchor coordinates')
    if any(not math.isfinite(x) or not math.isfinite(y) or y<=0 for x,y in anchors):
        raise ValueError('invalid source anchor')
    from adroit.orchestrator.experimental_extraction import checked_claim,source_units
    revision=catalog.load(reference)
    claim=next(c for r in revision.dossier.results if r.result_id==result_id for c in r.claims if c.key=='validation_reference')
    _,issues=checked_claim(catalog,revision,claim,source_units(catalog,reference,False))
    if issues:
        raise ValueError('reference anchors lack checked numerical source evidence: '+str(issues))
    scope=_scope(reference,result_id,contract,reference_claim['value'])
    _policy(catalog,scope,expected_hash,tolerance,reference_claim['value'])
    checks=anchor_checks(revision,contract,claims,tolerance,catalog)
    _policy(catalog,scope,expected_hash,tolerance,reference_claim['value'],fix=True)    # compared: now it is fixed
    return contract,checks

def _scope(reference: str,result_id: str,contract: LimitContract,value: dict) -> str:
    """The comparison's numerical identity (the recheck's FR-03): the experiment, the result, the curve's numbers and
    the result it states, and the anchors' numbers; not the text around them (a lineage label, a note), so that editing
    those does not make a new scope."""
    numbers={'experiment':reference.split('@')[0],'result_id':result_id,'adapter':contract.adapter,
             'points':contract.points,'value':contract.value,'mass_range':contract.mass_range,
             'scales':[contract.x_scale,contract.y_scale],'selection':contract.selection,
             'confidence_level':contract.confidence_level,'dataset_id':contract.dataset_id,
             'datasets':contract.datasets,'benchmark':contract.benchmark,'anchors':value.get('points')}
    return content_hash(json.loads(json.dumps(numbers,default=str)))

def _policy(catalog: ExperimentalCatalog,scope: str,expected_hash: str,tolerance: float,value: dict,
            fix: bool=False) -> None:
    """The comparison's tolerance, fixed by the first comparison of its numbers (the focused audit's FA-04; the
    recheck's FR-03: keyed by the numbers, ``_scope``, so a textual edit does not reset it). A different tolerance is
    refused unless the reviewed reference declares it (``value['tolerance']``), which revises the policy and is recorded
    with the revisions before it. Checked before the comparison; written (``fix``) only once a numerical comparison has
    been made, so an attempt refused before it fixes nothing; the check and the write under one lock."""
    declared=value.get('tolerance')
    if declared is not None and abs(float(declared)-tolerance)>1e-12:
        raise ValueError(f'the reference declares the tolerance {float(declared):g}; compare at it, not {tolerance:g}')
    path=catalog.path(f'validation_policies/{scope}.json')
    with run_lock(catalog.root):
        fixed=json.loads(path.read_text()) if path.exists() else None
        if fixed is not None and abs(float(fixed['tolerance'])-tolerance)<=1e-12:
            return
        if fixed is not None and declared is None:
            raise ValueError(f"this comparison's tolerance was fixed at {float(fixed['tolerance']):g} when its numbers "
                             f"were first compared ({fixed['fixed_at']}); a different tolerance is a policy revision: "
                             "declare it in the validation reference (tolerance) and review it again")
        if not fix:
            return
        history=(fixed or {}).get('revisions',[])+([{k:fixed[k] for k in ('tolerance','fixed_at','scientific_sha256')}]
                                                    if fixed else [])
        atomic_json(path,{'scope':scope,'scientific_sha256':expected_hash,'tolerance':tolerance,'fixed_at':utc_now(),
                          'declared':declared is not None,'revisions':history})

def anchor_checks(revision,contract: LimitContract,claims: dict,tolerance: float,catalog: ExperimentalCatalog) -> list[AnchorCheck]:
    """Each anchor's own qualifying evidence (the owner's rule, 2026-10-19; the focused audit's FA-01 and FA-02; the
    recheck's FR-01): its declared lineage (``value['lineage']``, one per anchor: the authors' printed text or their
    published table), bound to the locator it names (the same file, by name or sha256, and the same page, or table row),
    and a locator that prints both of its numbers in one clause, or, for a published table, holds them in the named mass
    and limit columns of that row, whose headers state the curve's result. A separate source counts only where its
    independence is established: a file ADROIT itself retrieved from the publisher (HEPData, arXiv: the revision
    records each file's address and sha256), the authors' printed document as much as a data file; a file of
    undeclared origin counts as nothing, whatever it says about itself or whatever its format (the tactical audit's
    T20-09, 2026-10-20: a PDF printed from the curve's own numbers had passed as the authors'), and never one that
    says it was derived from a figure or exported. For a curve digitised from a figure, the same paper's text counts when the clause is a printed
    assertion pairing that mass (with its unit) and that limit (with its unit), outside the figure itself. Every such
    clause must state the curve's result, and one clause anchors one point."""
    curve={s['asset_sha256'] for s in claims['limit_contract']['sources']}
    reference=claims['validation_reference']
    locators=[SourceLocator.model_validate(s) for s in reference['sources']]
    digitised=contract.origin=='figure_digitised'
    declared=_declared(contract,reference['value'])
    lineages=_lineages(reference['value'])
    figure=[s for s in claims['limit_contract']['sources'] if s.get('method')=='visual' and s.get('region')]
    retrieved=_retrieved(revision,catalog)
    checks,used,why=[],set(),[]
    for (x,y),lineage in zip(reference['value']['points'],lineages):
        found=[]
        for i,loc in enumerate(locators):
            asset=next((a for a in revision.sources if a.sha256==loc.asset_sha256),None)
            if asset is None or not _bound(lineage,loc,asset):
                continue
            if lineage['derivation']=='published_table':
                cells=_cells(contract,lineage,loc,revision,catalog,x,y)
                if cells is None:
                    continue
                text=clause=cells
            else:
                text=_evidence(loc,revision,catalog)
                clause=_paired(contract,text,x,y,loc.method)
            if clause is None or (loc.method=='text' and (i,clause) in used):
                continue
            if loc.asset_sha256 not in curve:
                if DERIVED.search(text) or DERIVED.search(_asset_text(loc,revision,catalog)):
                    continue                              # derived from a figure or an export: not separate evidence
                if loc.asset_sha256 not in retrieved:     # a PDF as much as a data file (the tactical audit's T20-09)
                    why.append(f'{asset.name}: its origin is not established (a file ADROIT did not retrieve from the '
                               'publisher: a PDF made from the curve itself would otherwise pass)')
                    continue
                found.append(('separate_source',loc,text,clause,i))
            elif digitised and loc.method=='text' and loc.page and loc.excerpt and lineage['derivation']=='printed_text' \
                    and not _inside_figure(loc,figure):
                found.append(('same_paper_text',loc,text,clause,i))
        checks.append(_anchor_check(contract,x,y,lineage,found,why,declared,used,tolerance))
    return checks

def _anchor_check(contract: LimitContract,x: float,y: float,lineage: dict,found: list,why: list[str],declared: bool,
                  used: set,tolerance: float) -> AnchorCheck:
    """One anchor's check on its best evidence (a separate source before the same paper's text); an anchor without
    any is refused, with why."""
    if not found:
        raise ValueError(f'the anchor ({x:g}, {y:g}) has no evidence of its own: a separate source whose '
                         "independence is established (a file ADROIT retrieved from the publisher, the authors' "
                         "printed document included), or, for a curve digitised from a figure, a clause of the "
                         "paper's text, with its "
                         'page, that pairs the mass and its unit with the limit and its unit (one clause per anchor); '
                         'its lineage must name that file and place'
                         +(f" ({'; '.join(dict.fromkeys(why))})" if why else ''))
    basis,loc,text,clause,i=min(found,key=lambda f:f[0]!='separate_source')
    if basis=='same_paper_text' and not declared:
        raise ValueError('same-paper anchors need the reference to declare its result: selection, confidence_level, '
                         'dataset_id and benchmark')
    if loc.method=='text':
        _quotation(contract,clause,text[:max(text.find(clause),0)])
    used.add((i,clause))
    check=_allowance(contract,(x,y),basis,loc,text,tolerance)
    table=lineage['derivation']=='published_table'
    return check.model_copy(update={'lineage':lineage,'table':loc.table or lineage.get('table',''),
                                    'row':lineage['row'] if table else loc.row,
                                    'column':lineage['limit_column'] if table else loc.column})

def _retrieved(revision,catalog: ExperimentalCatalog) -> dict[str,str]:
    """{sha256: the address} of every file ADROIT itself retrieved from an allowed publisher (``constraint_sources``),
    as the revision and its ancestors recorded it (``provenance['retrieved']``: each file's address and sha256)."""
    from urllib.parse import urlsplit
    from adroit.retrieval.constraint_sources import HOSTS
    out,seen,current={},set(),revision
    while current is not None and current.revision_id not in seen:
        seen.add(current.revision_id)
        for item in current.provenance.get('retrieved') or []:
            url=str(item.get('url','')) if isinstance(item,dict) else ''
            if urlsplit(url).scheme=='https' and urlsplit(url).hostname in HOSTS:
                out.setdefault(str(item.get('sha256','')),url)
        parent=current.parent_revision
        current=catalog.load(f'experimental:{current.experiment_id}@{parent}') if parent else None
    return out

def _bound(lineage: dict,loc: SourceLocator,asset) -> bool:
    """Whether the lineage names this locator's file (its name or sha256) and place: printed text its page (a PDF's),
    a published table its row (where the locator gives one) in a machine table or a structured file."""
    if lineage['document'] not in (asset.name,asset.sha256):
        return False
    if lineage['derivation']=='printed_text':
        return loc.method=='text' and (asset.suffix!='.pdf' or lineage.get('page')==loc.page)
    return loc.method in ('table','structured') and (loc.row is None or loc.row==lineage['row'])

def _cells(contract: LimitContract,lineage: dict,loc: SourceLocator,revision,catalog: ExperimentalCatalog,x: float,
           y: float) -> str | None:
    """The row's mass and limit cells as printed ('mass limit'), where the named columns of the named row hold the
    anchor's two numbers; None where they do not. A limit column whose header (and qualifiers) states another result
    than the curve's (expected for observed, another confidence level) is refused."""
    from adroit.orchestrator.experimental_extraction import printed_tokens
    item=next((catalog.ingestion(a) for a in revision.ingestions if catalog.ingestion(a).source_sha256==loc.asset_sha256),None)
    found=_table_cells(item,lineage) if item is not None else None
    if found is None:
        return None
    mass,limit,header=found
    if not any(_same(t[0],x) for t in printed_tokens(str(mass))) or not any(_same(t[0],y) for t in printed_tokens(str(limit))):
        return None
    observed=re.search(r'\bobserved\b',header,re.I)
    if contract.selection=='observed' and HEADER_EXPECTED.search(header) and not observed:
        raise ValueError(f"the anchor's limit column ({header}) states an expected sensitivity, the curve an observed limit")
    if contract.selection=='expected' and not HEADER_EXPECTED.search(header):
        raise ValueError(f"the anchor's limit column ({header}) does not state an expected sensitivity, as the curve does")
    for match in HEADER_CL.finditer(header):
        if abs(float(match.group(1) or match.group(2))/100-contract.confidence_level)>1e-9:
            raise ValueError(f"the anchor's limit column ({header}) states another confidence level than the curve's "
                             f'{contract.confidence_level:g}')
    return f'{mass} {limit}'

def _table_cells(item,lineage: dict) -> tuple | None:
    """(mass cell, limit cell, the limit column's header with its units and qualifiers) at the lineage's row: a machine
    table's named columns, or a HEPData table's named independent and dependent variables; None if not found."""
    row=int(lineage['row'])-1
    if item.kind=='table' and item.table is not None:
        columns=item.table.columns
        if lineage['mass_column'] not in columns or lineage['limit_column'] not in columns or not 0<=row<len(item.table.rows):
            return None
        cells=item.table.rows[row]
        return cells[columns.index(lineage['mass_column'])],cells[columns.index(lineage['limit_column'])],lineage['limit_column']
    data=item.structured if item.kind=='structured' else None
    if not isinstance(data,dict) or not {'independent_variables','dependent_variables'}<=set(data):
        return None
    def named(variables,name):
        return next((v for v in variables if isinstance(v,dict) and (v.get('header') or {}).get('name')==name),None)
    mass,limit=named(data['independent_variables'],lineage['mass_column']),named(data['dependent_variables'],lineage['limit_column'])
    if mass is None or limit is None or not 0<=row<min(len(mass.get('values',[])),len(limit.get('values',[]))):
        return None
    def value(v):
        return v.get('value',v.get('low')) if isinstance(v,dict) else v
    header=' '.join([str(limit['header'].get('name','')),str(limit['header'].get('units','')),
                     *(f"{q.get('name','')} {q.get('value','')}" for q in limit.get('qualifiers',[]) if isinstance(q,dict))])
    return value(mass['values'][row]),value(limit['values'][row]),header

def _lineages(value: dict) -> list[dict]:
    """Each anchor's declared lineage, typed so that it can be bound to its evidence (the recheck's FR-01):
    {'derivation': 'printed_text', 'document': the file's name or sha256, 'page': its page (a PDF's)} or
    {'derivation': 'published_table', 'document', 'row', 'mass_column', 'limit_column'} ('table' and 'where' optional,
    for the reader); refused if missing, incomplete or another derivation."""
    lineage=value.get('lineage')
    points=value.get('points') or []
    if not isinstance(lineage,list) or len(lineage)!=len(points):
        raise ValueError("each anchor needs its lineage (validation_reference.lineage, one per point): "
                         "{'derivation': 'printed_text', 'document', 'page'} or {'derivation': 'published_table', "
                         "'document', 'row', 'mass_column', 'limit_column'}")
    for item in lineage:
        if not isinstance(item,dict) or item.get('derivation') not in LINEAGE or not str(item.get('document','')).strip():
            raise ValueError('an anchor derived from anything but the authors\' printed text or published table (a '
                             'digitisation, a re-export) is not evidence; each lineage needs its document')
        if item['derivation']=='published_table' and not (isinstance(item.get('row'),int) and item['row']>=1 and
                                                          all(str(item.get(k,'')).strip() for k in ('mass_column','limit_column'))):
            raise ValueError("a published table's lineage needs its row and its mass and limit columns (row, "
                             'mass_column, limit_column)')
        if item['derivation']=='printed_text' and item.get('page') is not None and not (isinstance(item['page'],int)
                                                                                        and item['page']>=1):
            raise ValueError("a printed text's lineage gives its page as a number")
    return lineage

def _paired(contract: LimitContract,text: str,x: float,y: float,method: str) -> str | None:
    """The clause that prints the anchor's mass and limit together, or None: in a text quotation a sentence (for an
    SI curve each number with its unit, the mass GeV, TeV or MeV, the limit cm² or a barn, so a figure's axis ticks
    and a list of numbers pair nothing); in a table its row; in a structured file the two numbers next to each other."""
    from adroit.orchestrator.experimental_extraction import printed_tokens
    if method=='structured':
        tokens=printed_tokens(text)
        return text if any(_same(a[0],x) and _same(b[0],y) for a,b in zip(tokens,tokens[1:])) else None
    clauses=[text] if method!='text' else [c for c in CLAUSE.split(text) if c and c.strip()]
    for clause in clauses:
        tokens=printed_tokens(clause)
        masses=[t for t in tokens if _same(t[0],x)]
        limits=[t for t in tokens if _same(t[0],y)]
        if not masses or not limits:
            continue
        if method=='text' and contract.adapter=='si_isoscalar_curve':
            masses=[t for t in masses if MASS_UNIT.match(clause,t[3])]
            limits=[t for t in limits if XS_UNIT.match(clause,t[3])]
            if not masses or not limits or len(re.findall(r'[A-Za-z]{2,}',clause))<3:
                continue
        return clause.strip()
    return None

def _inside_figure(loc: SourceLocator,figure: list[dict]) -> bool:
    """Whether a quotation's region lies inside the figure the curve was digitised from (its own labels and ticks)."""
    if loc.region is None:
        return False
    x0,y0,x1,y1=loc.region
    return any(f.get('page')==loc.page and f['region'][0]<=x0 and f['region'][1]<=y0 and x1<=f['region'][2]
               and y1<=f['region'][3] for f in figure)

def _asset_text(loc: SourceLocator,revision,catalog: ExperimentalCatalog) -> str:
    """The text of a separate source's file (to see whether it says it was derived from a figure), '' for a PDF."""
    source=next((a for a in revision.sources if a.sha256==loc.asset_sha256),None)
    if source is None or source.suffix=='.pdf':
        return ''
    try:
        return catalog.asset_path(source).read_text(encoding='utf-8-sig')[:20000]
    except (OSError,UnicodeDecodeError):
        return ''

def _same(a: float,b: float) -> bool:
    return abs(a-b)<=1e-12*max(abs(a),abs(b),1e-300)

def _declared(contract: LimitContract,value: dict) -> bool:
    """Whether the reference declares its result; a declared result must be the curve's (observed or expected,
    confidence level, dataset, benchmark)."""
    declared=value.get('result')
    if declared is None:
        return False
    if not isinstance(declared,dict):
        raise ValueError('the validation reference\'s result must be an object')
    expected={'selection':contract.selection,'confidence_level':contract.confidence_level,
              'dataset_id':contract.dataset_id,'benchmark':contract.benchmark}
    differ=[k for k,v in expected.items() if declared.get(k)!=v]
    if differ:
        raise ValueError('the validation reference declares another result than the curve: '+', '.join(differ))
    return True

def _quotation(contract: LimitContract,clause: str,context: str='') -> None:
    """Refuse a clause that states another result than the curve (the focused audit's FA-02: the clause the anchor is
    printed in): another confidence level (in figures or words), an expected sensitivity for an observed limit (or the
    reverse), a combined result for one dataset, a run the curve does not hold, or another interaction. A clause that
    states two results (observed and expected, or two cross-sections) is ambiguous and refused; on a qualifier the
    clause is silent about (the confidence level, observed or expected, combined, the run), the quotation's preceding
    sentences (``context``) speak, and must agree with the curve too (the recheck's FR-02)."""
    from adroit.orchestrator.experimental_extraction import printed_tokens
    sections=[t for t in printed_tokens(clause) if XS_UNIT.match(clause,t[3])]
    if len(sections)>1:
        raise ValueError('the quotation states more than one cross-section in one clause: which is this limit is not '
                         'resolved (quote a clause that states it alone, or verify by hand)')
    if OBSERVED.search(clause) and EXPECTED.search(clause):
        raise ValueError('the quotation states both an observed and an expected result in one clause: which is this '
                         'limit is not resolved (quote a clause that states it alone, or verify by hand)')
    if context.strip():
        silent=clause
        if not CL_PRINTED.search(clause):
            silent+=' '+' '.join(m.group(0) for m in CL_PRINTED.finditer(context))
        if not (OBSERVED.search(clause) or EXPECTED.search(clause)):
            if OBSERVED.search(context) and EXPECTED.search(context):
                raise ValueError('the quotation\'s context states both observed and expected results and its clause '
                                 'neither: which is this limit is not resolved')
            silent+=' '+' '.join(m.group(0) for m in (*OBSERVED.finditer(context),*EXPECTED.finditer(context)))
        if not (COMBINED.search(clause) or RUN_NAME.search(clause)):
            silent+=' '+' '.join(m.group(0) for m in (*COMBINED.finditer(context),*RUN_NAME.finditer(context)))
        clause=silent
    for printed in CL_PRINTED.findall(clause):
        if abs(float(printed)/100-contract.confidence_level)>1e-9:
            raise ValueError(f'the quotation states a {printed}% confidence level, the curve {contract.confidence_level:g}')
    if contract.selection=='observed' and EXPECTED.search(clause) and not re.search(r'\bobserved\b',clause,re.I):
        raise ValueError('the quotation states an expected sensitivity, the curve an observed limit')
    if contract.selection=='expected' and not EXPECTED.search(clause):
        raise ValueError('the quotation does not state an expected sensitivity, as the curve does')
    if COMBINED.search(clause) and len(contract.datasets)<2:
        raise ValueError('the quotation states a combined result, the curve one dataset (a combination names its '
                         'datasets: limit_contract.datasets)')
    held={t.casefold() for d in [contract.dataset_id,*contract.datasets] for t in re.findall(r'[A-Za-z0-9]+',d)}
    for match in RUN_NAME.finditer(clause):
        name=match.group(1) or match.group(2)
        if not set(re.findall(r'[a-z0-9]+',name.casefold()))<=held:
            raise ValueError(f'the quotation names {match.group(0).strip()}, not among the curve\'s datasets '
                             f'({contract.dataset_id}): resolve which result it states')
    if contract.adapter=='si_isoscalar_curve' and OTHER_INTERACTION.search(clause):
        raise ValueError('the quotation states another interaction than the isoscalar spin-independent benchmark')

def _evidence(loc: SourceLocator,revision,catalog: ExperimentalCatalog) -> str:
    """The text a locator cites: its quotation, or, in a machine table, its whole row."""
    if loc.method=='table':
        item=next(catalog.ingestion(a) for a in revision.ingestions if catalog.ingestion(a).source_sha256==loc.asset_sha256)
        return ' '.join(map(str,item.table.rows[loc.row-1])) if loc.row else ''
    return loc.excerpt

def _variation(contract: LimitContract,x: float,relative: float) -> float:
    """The largest |L(m)/L(x) − 1| of the declared interpolation (its own axes: linear or logarithmic) over the masses
    m within the relative reading error of x, [x(1 − δ), x(1 + δ)] clipped to the domain: the interval's ends and
    every node inside it, so a steep segment, a node and an edge are all seen (the focused audit's FA-05: a log–log
    secant had been used whatever the axes)."""
    centre=interpolate(contract,x)
    if not relative or not centre:
        return 0.
    low,high=max(x*(1-relative),contract.mass_range[0]),min(x*(1+relative),contract.mass_range[1])
    masses=[low,high,*(m for m,_ in contract.points if low<m<high)]
    return max((abs(v/centre-1) for v in (interpolate(contract,m) for m in masses) if v is not None),default=0.)

def _allowance(contract: LimitContract,point: tuple[float,float],basis: str,loc: SourceLocator,text: str,
               tolerance: float) -> AnchorCheck:
    """An anchor's check with its allowance, set before the comparison: the tolerance, or, for a digitised curve,
    the printed rounding and the declared reading errors, y_round + y_err + the curve's own variation over the mass
    interval x_round + x_err (``_variation``), never above the tolerance; an anchor printed too coarsely to check the
    transcription at the tolerance is refused."""
    from adroit.orchestrator.experimental_extraction import printed_precision
    x,y=point
    x_round=y_round=0.
    if loc.method=='text':
        x_round,y_round=printed_precision(text,x) or 0.,printed_precision(text,y) or 0.
    allowance=tolerance
    if contract.origin=='figure_digitised':
        printed=y_round+_variation(contract,x,x_round)
        if printed>=tolerance:
            raise ValueError(f'the anchor ({x:g}, {y:g}) is printed too coarsely (±{printed:.1%}) to check the '
                             f'transcription at the tolerance {tolerance:g}')
        allowance=min(tolerance,y_round+contract.y_relative_error+_variation(contract,x,x_round+contract.x_relative_error))
    return AnchorCheck(point=(x,y),asset_sha256=loc.asset_sha256,page=loc.page,method=loc.method,
                       excerpt=text if loc.method=='text' else text[:1000],basis=basis,x_rounding=x_round,
                       y_rounding=y_round,allowance=allowance)

def _receipt(reference: str,result_id: str,expected_hash: str,contract: LimitContract,checks: list[AnchorCheck],
             tolerance: float,catalog: ExperimentalCatalog,manual: FigureVerification | None=None) -> LimitValidation:
    """Interpolate the curve at each anchor, compare within each anchor's allowance, and save the receipt with its
    basis and the matching scope."""
    reproduced=[]
    for check in checks:
        calculated=interpolate(contract,check.point[0])
        if calculated is None:
            raise ValueError('anchor outside declared source domain')
        reproduced.append(calculated)
    errors=[abs(r/c.point[1]-1) for r,c in zip(reproduced,checks)]
    bases={c.basis for c in checks}
    basis='manual_figure' if manual else bases.pop() if len(bases)==1 else 'mixed'
    from adroit.core.config import PROJECT_ROOT
    from adroit.orchestrator.track1_identity import tree_identity
    body=dict(revision=reference,result_id=result_id,scientific_sha256=expected_hash,adapter_version=1,
        code_sha256=tree_identity(PROJECT_ROOT/'adroit'),created_at=utc_now(),reference=[c.point for c in checks],
        reproduced=reproduced,relative_errors=errors,tolerance=tolerance,
        passed=all(e<=c.allowance for e,c in zip(errors,checks)),scope=SCOPES[basis].format(n=len(checks)),
        basis=basis,anchors=checks,manual=manual)
    result=LimitValidation(validation_id='0'*64,**body)
    result.validation_id=content_hash(result.model_dump(mode='json',exclude={'validation_id'}))
    with run_lock(catalog.root):
        atomic_json(catalog.path(f'validations/{result.validation_id}.json'),result.model_dump(mode='json'))
    return result

def verify_figure(reference: str,result_id: str,tolerance: float,expected_hash: str,researcher: str,*,confirmed: bool,
                  checks: list[str],reviewed_range: tuple[float,float],packet: Path,
                  catalog: ExperimentalCatalog | None=None,shown: tuple[str,str,str] | None=None) -> LimitValidation:
    """The manual figure-verification route (the owner's rule, 2026-10-19), for an SI curve digitised from a figure
    with one or two printed anchors: the review packet the researcher inspected (``packet``, the folder ``plot_packet``
    wrote: its calibrated source overlay, the source page it was drawn on and their hashes), the declared mass range
    restated in full, every printed anchor checked as in ``validate``, the attested checklist and the researcher's
    name. The verification records the hashes of that packet's own source page and of the curve's geometry on it, after
    checking the packet is intact and was drawn for this curve, never a second rendering (the recheck's FR-04). Its
    receipt says it was verified by hand with limited numerical anchors, not that it passed the ordinary validation.
    ``shown``: the (source page, geometry, overlay) digests of the packet a page showed the researcher; the packet in
    its folder must be that one, or nothing is verified (the auditor's DH recheck, DI-01, 2026-11-06)."""
    catalog=catalog or ExperimentalCatalog()
    if not confirmed or not researcher.strip() or not set(FIGURE_CHECKLIST)<=set(checks):
        raise ValueError('a manual figure verification requires your name, explicit attestation and every check: '
                         +', '.join(FIGURE_CHECKLIST))
    contract,anchors=_checked(reference,result_id,tolerance,expected_hash,catalog)
    _manual_scope(contract,anchors)
    if tuple(float(v) for v in reviewed_range)!=tuple(contract.mass_range):
        raise ValueError(f'restate the full declared mass range you reviewed: {contract.mass_range[0]:g} to '
                         f'{contract.mass_range[1]:g} GeV')
    if not contract.figure_axes:
        raise ValueError('a manual figure verification needs a calibrated source overlay (figure_axes)')
    image,geometry,overlay=_reviewed(Path(packet),reference,result_id,contract)
    if shown is not None and (image,geometry,overlay)!=tuple(shown):
        raise ValueError('the review packet in its folder is not the one you were shown: render it again and review it')
    manual=FigureVerification(researcher=researcher.strip(),signed_at=utc_now(),checklist=sorted(set(checks)),
                              reviewed_range=contract.mass_range,anchors_required=ANCHORS[contract.adapter],
                              source_image_sha256=image,geometry_sha256=geometry,overlay_sha256=overlay)
    return _receipt(reference,result_id,expected_hash,contract,anchors,tolerance,catalog,manual)

def renew_figure(validation_id: str,catalog: ExperimentalCatalog | None=None) -> LimitValidation:
    """A manual figure verification renewed under the current code: its anchors checked again, the overlay rendered
    again, and the researcher's verification carried over (``renewed_from``) only while what they looked at is
    unchanged, the rendered source page and the decoded curve's geometry on it (the focused audit's FA-06);
    otherwise a new visual review is needed. The original verification stays as its own receipt."""
    catalog=catalog or ExperimentalCatalog()
    old=load_validation(validation_id,catalog)
    if old.manual is None:
        raise ValueError('only a manual figure verification is renewed; rerun validate-limit')
    contract,anchors=_checked(old.revision,old.result_id,old.tolerance,old.scientific_sha256,catalog)
    _manual_scope(contract,anchors)
    if not old.manual.geometry_sha256:
        raise ValueError('this verification did not record the overlay it reviewed: a new visual review is needed '
                         '(verify-figure)')
    import tempfile
    with tempfile.TemporaryDirectory(prefix='adroit-overlay-') as folder:
        fresh=plot_packet(old.revision,old.result_id,Path(folder),catalog)           # one rendering, hashed as drawn
    image,geometry=fresh.get('source_image_sha256'),fresh.get('geometry_sha256')
    if (image,geometry)!=(old.manual.source_image_sha256,old.manual.geometry_sha256):
        raise ValueError('the overlay the researcher reviewed has changed under the current code (the rendered page or '
                         'the decoded curve on it): a new visual review is needed (verify-figure)')
    manual=old.manual.model_copy(update={'renewed_from':validation_id})
    return _receipt(old.revision,old.result_id,old.scientific_sha256,contract,anchors,old.tolerance,catalog,manual)

def _manual_scope(contract: LimitContract,anchors: list[AnchorCheck]) -> None:
    """The manual route is for an SI curve digitised from a figure with at least one, and fewer than the ordinary
    number of, printed anchors."""
    if contract.adapter!='si_isoscalar_curve' or contract.origin!='figure_digitised':
        raise ValueError('the manual route is for spin-independent curves digitised from a figure')
    if not anchors:
        raise ValueError('a manual figure verification still checks at least one printed anchor')
    if len(anchors)>=ANCHORS[contract.adapter]:
        raise ValueError('enough anchors for the ordinary validation: use validate-limit')

def load_validation(validation_id: str,catalog: ExperimentalCatalog | None=None) -> LimitValidation:
    """A limit-validation receipt by its exact ID, refused if it was modified."""
    catalog=catalog or ExperimentalCatalog()
    if not SHA.fullmatch(validation_id):
        raise ValueError('exact validation ID required')
    raw=json.loads(catalog.path(f'validations/{validation_id}.json').read_text())
    if content_hash({k:v for k,v in raw.items() if k!='validation_id'})!=validation_id:
        raise ValueError('validation receipt modified')
    result=LimitValidation.model_validate(raw)
    if result.validation_id!=validation_id:
        raise ValueError('validation ID mismatch')
    return result

def bind(reference: str,result_id: str,review_id: str,validation_id: str,catalog: ExperimentalCatalog | None=None) -> BoundPrivateLimit:
    """Freeze an explicitly selected eligible limit; never mutate packaged defaults."""
    catalog=catalog or ExperimentalCatalog()
    contract,value=limit_contract(reference,result_id,catalog)
    review=load_review(review_id,catalog)
    validation=load_validation(validation_id,catalog)
    from adroit.core.config import PROJECT_ROOT
    from adroit.orchestrator.track1_identity import tree_identity
    if any(item.scientific_sha256!=value['scientific_sha256'] for item in (review,validation)):
        raise ValueError('source approval/validation does not cover this exact limit and reference')
    if not validation.passed or validation.code_sha256!=tree_identity(PROJECT_ROOT/'adroit'):
        raise ValueError('numerical validation failed or needs renewal under current software')
    if contract.selection!='observed' or contract.overlap=='unknown':
        raise ValueError('only observed limits with reviewed overlap declarations can be selected')
    expected={'si_isoscalar_curve':'elastic_contact_O1_cp_equals_cn','sm_higgs_invisible':'SM_higgs_125_production'}[contract.adapter]
    if contract.benchmark!=expected:
        raise ValueError('no exact adapter for this declared benchmark')
    revision=catalog.load(reference)
    body=dict(revision=reference,result_id=result_id,name=revision.dossier.title+' / '+result_id,contract=contract.model_dump(mode='json'),
              review=review.model_dump(mode='json'),validation=validation.model_dump(mode='json'),scientific_sha256=value['scientific_sha256'],created_at=utc_now())
    result=BoundPrivateLimit(limit_id=content_hash(body),**body)
    with run_lock(catalog.root):
        atomic_json(catalog.path(f'limits/{result.limit_id}.json'),result.model_dump(mode='json'))
    return result

def load_bound(reference: str,catalog: ExperimentalCatalog | None=None) -> BoundPrivateLimit:
    """A pinned ``private-limit:`` binding, refused if its contract, source, review or validation receipt changed, or
    if the validation is not a pass under the current code."""
    catalog=catalog or ExperimentalCatalog()
    key=reference.removeprefix('private-limit:')
    if not reference.startswith('private-limit:') or not SHA.fullmatch(key):
        raise ValueError('pinned private-limit reference required')
    raw=json.loads(catalog.path(f'limits/{key}.json').read_text())
    if content_hash({k:v for k,v in raw.items() if k!='limit_id'})!=key:
        raise ValueError('private limit binding modified')
    result=BoundPrivateLimit.model_validate(raw)
    if result.limit_id!=key:
        raise ValueError('limit ID mismatch')
    contract,value=limit_contract(result.revision,result.result_id,catalog)
    if contract!=result.contract or value['scientific_sha256']!=result.scientific_sha256:
        raise ValueError('private scientific inputs changed')
    review=load_review(result.review.review_id,catalog)
    validation=load_validation(result.validation.validation_id,catalog)
    if review!=result.review or validation!=result.validation:
        raise ValueError('embedded review/validation differs from its immutable receipt')
    from adroit.core.config import PROJECT_ROOT
    from adroit.orchestrator.track1_identity import tree_identity
    if not validation.passed or validation.code_sha256!=tree_identity(PROJECT_ROOT/'adroit'):
        raise ValueError('private numerical validation stale')
    return result

def plot_packet(reference: str,result_id: str,out: Path,catalog: ExperimentalCatalog | None=None,claim=None) -> dict:
    """Plot decoded values/anchors and, when calibrated, overlay the source panel. The packet is written under one hold
    of its folder (``durable.publishing``; ``claim``: its caller's), from its first file to its record
    (``review_packet.json``), and its overlay's identity is the digest its draw keeps under that hold: a packet is its
    writer's whole, and another packet writer into the folder waits for it (the auditor's DG recheck, DH-01, 2026-11-06: the
    overlay's digest read from this process's map of draws after its draw's hold had ended, a packet completed meanwhile
    by another thread had given its overlay to the first packet, beside the first curve's geometry). Each file is
    written whole to its own entry in the folder held (``write_atomic``), never through a link to another folder's
    (the auditor's DH recheck, DI-03, 2026-11-06: the values plot, the source page and the record had been written through
    links into a folder another writer held)."""
    return rendered_packet(reference,result_id,out,catalog,claim)[0]

def rendered_packet(reference: str,result_id: str,out: Path,catalog: ExperimentalCatalog | None=None,
                    claim=None) -> tuple[dict,dict]:
    """``plot_packet``'s report, and the bytes of each image it wrote (``plot``, ``source_overlay``: None where it drew
    none), as written under its hold: what a page shows of the packet, never the files read again once the hold has
    ended (the auditor's DH recheck, DI-01, 2026-11-06: the review page had named its images by their paths, and the browser,
    reading them later, had shown another packet's plots beside this source's text)."""
    from adroit.core.durable import publishing
    catalog=catalog or ExperimentalCatalog()
    contract,value=limit_contract(reference,result_id,catalog)
    with publishing(Path(out),claim):
        return _packet(reference,result_id,Path(out),catalog,contract,value)

def _packet(reference: str,result_id: str,out: Path,catalog: ExperimentalCatalog,contract: LimitContract,
            value: dict) -> tuple[dict,dict]:
    """``rendered_packet``'s files, under its hold of ``out``: its report and its images' bytes."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out.mkdir(parents=True,exist_ok=True)
    claims={c['key']:c for c in value['scientific']['claims']}
    anchors=claims['validation_reference']['value']['points']
    fig,ax=plt.subplots(figsize=(7,5))
    if contract.points:
        x,y=zip(*contract.points)
        ax.plot(x,y,'o-',label='selected published values')
        if contract.x_scale=='log':
            ax.set_xscale('log')
        if contract.y_scale=='log':
            ax.set_yscale('log')
        ax.scatter(*zip(*anchors),marker='x',label='source anchors')
        ax.set_xlabel('mass (GeV)')
        ax.set_ylabel(contract.quantity+' ('+contract.units+')')
    else:
        ax.axhline(contract.value,label='selected observed bound')
        ax.scatter(*zip(*anchors),marker='x',label='source anchor')
        ax.set_xlabel('source benchmark coordinate')
        ax.set_ylabel(contract.quantity)
    ax.legend()
    fig.tight_layout()
    from io import BytesIO
    from adroit.core.durable import write_atomic          # each file to its own entry, never a link's target (DI-03)
    stream=BytesIO()
    fig.savefig(stream,format='png',dpi=140)
    plt.close(fig)
    path=out/'published_values.png'
    images={'plot':stream.getvalue(),'source_overlay':None}
    write_atomic(path,images['plot'])
    report={'plot':str(path),'source_overlay':None,'overlay_status':'No calibrated source axes supplied; source must be inspected beside decoded values.'}
    if contract.figure_axes:
        data=_page_image(reference,contract,catalog)               # rendered once: drawn on, kept and hashed
        overlay=_source_overlay(reference,contract,anchors,out,catalog,data)
        image,geometry=_identity(data,contract)
        page=out/'source_page.bin'
        write_atomic(page,data)
        from adroit.evidence.bindings import drawn_digest     # its identity as drawn under this hold (DA-01, DH-01)
        drawn=drawn_digest(overlay)
        images['source_overlay']=_as_drawn(Path(overlay),drawn)   # its bytes read once against it, for the page (DI-01)
        identity={'reference':reference,'result_id':result_id,'source_page':page.name,'overlay':Path(overlay).name,
                  'source_image_sha256':image,'geometry_sha256':geometry,'overlay_sha256':drawn}
        write_atomic(out/'review_packet.json',json.dumps(identity,indent=2))
        report.update(source_overlay=overlay,review_packet=str(out/'review_packet.json'),
                      **{k:identity[k] for k in ('source_image_sha256','geometry_sha256','overlay_sha256')},
                      overlay_status='Calibrated original source overlay; calibration is part of the scientific review binding.')
    return report,images

def _as_drawn(path: Path,digest: str) -> bytes:
    """The overlay's bytes for its page, read once under the hold it was drawn under and checked against the digest
    its draw kept (``drawn_digest``): the overlay drawn, or nothing shown (DI-01)."""
    import hashlib
    data=path.read_bytes()
    if not digest or hashlib.sha256(data).hexdigest()!=digest:
        raise ValueError('the source overlay changed as it was drawn: render the packet again')
    return data

def _reviewed(packet: Path,reference: str,result_id: str,contract: LimitContract) -> tuple[str,str,str]:
    """(source page sha256, geometry sha256, overlay sha256) of the review packet the researcher inspected, after
    checking it is this result's, intact (its page and overlay files hash as recorded) and drawn for this curve and
    calibration (the geometry recomputed on its own page)."""
    import hashlib
    try:
        identity=json.loads((packet/'review_packet.json').read_text())
        page=(packet/identity['source_page']).read_bytes()
        overlay=(packet/identity['overlay']).read_bytes()
    except (OSError,KeyError,ValueError) as error:
        raise ValueError(f'name the review packet you inspected (the folder experiments review wrote): {error}') from None
    if (identity.get('reference'),identity.get('result_id'))!=(reference,result_id):
        raise ValueError('the review packet is for another revision or result')
    if hashlib.sha256(page).hexdigest()!=identity['source_image_sha256'] or \
            hashlib.sha256(overlay).hexdigest()!=identity['overlay_sha256']:
        raise ValueError('the review packet has changed since it was drawn: render it again and review it')
    if _identity(page,contract)[1]!=identity['geometry_sha256']:
        raise ValueError('the review packet was drawn for another curve or calibration: render it again and review it')
    return identity['source_image_sha256'],identity['geometry_sha256'],identity['overlay_sha256']

def _frame(cal: dict,width: int,height: int) -> tuple[float,float,float,float]:
    """The plotting frame in page-image pixels: ``frame`` as fractions of the image (from the top left, whatever its
    resolution) or ``pixel_box`` in the rendered page's pixels."""
    if 'frame' in cal:
        fl,ft,fr,fb=map(float,cal['frame'])
        if not 0<=fl<fr<=1 or not 0<=ft<fb<=1:
            raise ValueError('calibration frame outside the page image (fractions 0 to 1)')
        return fl*width,ft*height,fr*width,fb*height
    left,top,right,bottom=map(float,cal['pixel_box'])
    if not 0<=left<right<=width or not 0<=top<bottom<=height:
        raise ValueError('calibration box outside original source preview')
    return left,top,right,bottom

def _page_image(reference: str,contract: LimitContract,catalog: ExperimentalCatalog) -> bytes:
    """The rendered source page (or original image) the calibration refers to."""
    from adroit.retrieval.experimental_ingestion import render_page
    cal=contract.figure_axes
    revision=catalog.load(reference)
    source=next(a for a in revision.sources if a.sha256==cal['asset_sha256'])
    return render_page(catalog.asset_path(source),int(cal['page'])) if source.suffix=='.pdf' else catalog.asset_path(source).read_bytes()

def overlay_identity(reference: str,contract: LimitContract,catalog: ExperimentalCatalog) -> tuple[str,str]:
    """``_identity`` of a fresh rendering of the source page."""
    return _identity(_page_image(reference,contract,catalog),contract)

def _identity(data: bytes,contract: LimitContract) -> tuple[str,str]:
    """(sha256 of the rendered source page, sha256 of the decoded curve's geometry on it: the calibration, the image
    size and every point's pixel position to 0.01 px): what a manual figure verification reviewed (FA-06, FR-04)."""
    from PIL import Image
    from io import BytesIO
    image=Image.open(BytesIO(data))
    px,py=_pixels(contract,image)
    geometry={'calibration':contract.figure_axes,'size':[image.width,image.height],
              'points':[[round(float(a),2),round(float(b),2)] for a,b in zip(px,py)]}
    import hashlib
    return hashlib.sha256(data).hexdigest(),content_hash(geometry)

def _pixels(contract: LimitContract,image,points=None):
    """The points (default: the curve's) in page-image pixels through the declared calibration."""
    import numpy as np
    cal=contract.figure_axes
    left,top,right,bottom=_frame(cal,image.width,image.height)
    xmin,xmax=map(float,cal['x_range'])
    ymin,ymax=map(float,cal['y_range'])
    if not contract.points or not 0<xmin<xmax or not 0<ymin<ymax:
        raise ValueError('source overlay needs a positive calibrated curve domain')
    transform_x=np.log10 if contract.x_scale=='log' else lambda z:z
    transform_y=np.log10 if contract.y_scale=='log' else lambda z:z
    x,y=np.array(points if points is not None else contract.points,dtype=float).T
    return (left+(right-left)*(transform_x(x)-transform_x(xmin))/(transform_x(xmax)-transform_x(xmin)),
            bottom-(bottom-top)*(transform_y(y)-transform_y(ymin))/(transform_y(ymax)-transform_y(ymin)))

def _source_overlay(reference: str,contract: LimitContract,anchors: list,out: Path,catalog: ExperimentalCatalog,
                    data: bytes | None=None) -> str:
    """The decoded curve, and the anchors, drawn over the original page (``data``: as rendered once for the packet)
    through the declared calibration."""
    import matplotlib.pyplot as plt
    from PIL import Image
    from io import BytesIO
    data=data if data is not None else _page_image(reference,contract,catalog)
    image=Image.open(BytesIO(data))
    left,top,right,bottom=_frame(contract.figure_axes,image.width,image.height)
    px,py=_pixels(contract,image)
    if any(px<left) or any(px>right) or any(py<top) or any(py>bottom):
        raise ValueError('decoded values outside calibrated source axes')
    fig,ax=plt.subplots(figsize=(9,6))
    ax.imshow(image)
    ax.plot(px,py,'r.-',label='decoded limit overlay')
    if anchors:
        ax.scatter(*_pixels(contract,image,anchors),marker='x',color='b',label='printed anchors')
    ax.legend()
    ax.axis('off')
    target=out/'source_overlay.png'
    fig.tight_layout()
    from adroit.evidence.bindings import write_figure      # its digest held for the packet (DA-01)
    write_figure(fig,target,140)
    plt.close(fig)
    return str(target)
