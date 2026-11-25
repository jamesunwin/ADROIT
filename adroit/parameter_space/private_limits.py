"""Pure application of explicitly selected reviewed private published limits."""
from __future__ import annotations
import math
from adroit.core.private_limits import BoundPrivateLimit
from adroit.constraints.searches import Outcome
from adroit.constraints.experimental_review import interpolate

HIGGS_RECORD='atlas-2301.10731-hinv'

FULL_DENSITY = 'private full-density SI curves need relic_fraction=1; no implicit density rescaling'


def check_applicability(spec, items: list[BoundPrivateLimit]) -> None:
    """The request-wide checks of a final private-limit selection, however it was made (explicitly, through an
    experimental profile, or in a child study): ``validate_selection``, and a full-density SI curve only for a model
    that is all of the dark matter (the stacked audit's S18-02; no density rescaling is implied)."""
    validate_selection(items)
    if spec.relic_fraction != 1 and any(i.contract.adapter == 'si_isoscalar_curve' for i in items):
        raise ValueError(FULL_DENSITY)


def validate_selection(items: list[BoundPrivateLimit]) -> tuple[str,...]:
    """Refuse unresolved overlaps, duplicate datasets and incompatible replacements."""
    from adroit.experiments.registry import module_names
    datasets=set()
    replaced=set()
    ignored=[]
    for item in items:
        c=item.contract
        if c.dataset_id in datasets:
            raise ValueError('selected private limits share a dataset; choose one result')
        datasets.add(c.dataset_id)
        if c.overlap=='unknown':
            raise ValueError('selected input has unresolved dataset overlap')
        for target in c.supersedes:
            if target in replaced:
                raise ValueError('multiple private results replace the same input')
            replaced.add(target)
            if c.adapter=='si_isoscalar_curve' and target in module_names():
                ignored.append(target)
            elif c.adapter=='sm_higgs_invisible' and target==HIGGS_RECORD:
                pass
            else:
                raise ValueError('replacement target does not match this evaluator contract: '+target)
    return tuple(sorted(ignored))

def limit_interval(contract,mass: float) -> tuple[float,float,float] | None:
    """Conservative digitisation range, including source knots; never extrapolate."""
    central=interpolate(contract,mass)
    if central is None:
        return None
    dx=contract.x_relative_error or 0.
    dy=contract.y_relative_error or 0.
    if contract.adapter=='sm_higgs_invisible':
        return central,central*(1-dy),central*(1+dy)
    low,high=mass*(1-dx),mass*(1+dx)
    if low<contract.mass_range[0] or high>contract.mass_range[1]:
        return None
    values=[interpolate(contract,x) for x in [low,high,*[x for x,y in contract.points if low<=x<=high]]]
    return central,min(values)*(1-dy),max(values)*(1+dy)

def _si_channel(cls,p) -> tuple[str,float]:
    """(kind, σ) the SI benchmark compares: the model's SI channel when it has one (even if an SD channel
    decides elsewhere); a pure SD model gives its SD kind (not applicable); anything else its own kind."""
    kind,sigma=cls.dd(p)
    channels=cls.dd_channels(p) if hasattr(cls,'dd_channels') and kind in ('SI','SD-proton','SD-neutron') else []
    si=next((c for c in channels if c.kind=='SI'),None)
    return ('SI',si.sigma_cm2) if si is not None else (kind,sigma)

def outcome(cls,p,item: BoundPrivateLimit) -> Outcome:
    """Apply exact source benchmarks; unsupported reductions stay undecided."""
    from adroit.parameter_space.portals.higgs import HiggsPortalScalar,HiggsPortalFermion,HiggsPortalVector
    from adroit.constraints import higgs
    c=item.contract
    name='private: '+item.name
    if HIGGS_RECORD in c.supersedes:
        from adroit.parameter_space.scan import INVISIBLE_H
        name=INVISIBLE_H
    base=dict(name=name,source=item.reference,confidence_level=c.confidence_level,statistical_construction=c.construction)
    applicability='applicable'
    prediction=None
    reason=''
    if c.adapter=='si_isoscalar_curve':
        kind,prediction=_si_channel(cls,p)
        if kind in ('SD-proton','SD-neutron'):
            return Outcome(**base,excluded=False,why='not applicable: pure SD prediction is outside this SI benchmark',
                           coverage={'applicability':'not_applicable','benchmark':c.benchmark})
        if kind!='SI':
            reason='this operator/inelastic prediction needs a dedicated source recast'
        else:
            interaction=cls.interaction(p)
            active=[q for q in interaction.coefficients if q.proton!=0 or q.neutron!=0]
            if any(q.depends_on_q or q.operator!=1 or
                not math.isclose(q.proton,q.neutron,rel_tol=1e-10,abs_tol=1e-300) for q in active):
                reason='published elastic isoscalar contact O1 curve does not match this interaction'
    else:
        if not isinstance(cls,(HiggsPortalScalar,HiggsPortalFermion,HiggsPortalVector)):
            reason='SM-like Higgs production benchmark is not certified for this model class'
        else:
            width=cls.invisible(p).get('h',0.)
            prediction=width/(higgs.GAMMA_H+width)
    limits=limit_interval(c,p.m_chi)
    if reason or limits is None or prediction is None or not math.isfinite(prediction) or prediction<0:
        return Outcome(**base,excluded=None,why=reason or 'outside source/validated digitisation domain',
                       coverage={'applicability':'unsupported' if reason else 'outside_domain','benchmark':c.benchmark})
    central,low,high=limits
    excluded=True if prediction>high else False if prediction<low or (low==high and prediction<=low) else None
    why='' if excluded is not None else 'digitisation uncertainty straddles the exclusion threshold'
    # Curves are hard cuts, not newly invented likelihood terms.
    result=Outcome(**base,excluded=excluded,value=prediction/central,ratio=prediction/central,why=why,
        coverage={'applicability':applicability,'benchmark':c.benchmark,'prediction':prediction,
                  'limit':central,'limit_low':low,'limit_high':high,'mass_range':c.mass_range,
                  'source_review_id':item.review.review_id,'validation_id':item.validation.validation_id}).at95()
    return result.model_copy(update={'ratio':None})

def apply(row,cls,p,items: list[BoundPrivateLimit]):
    """Add/replace only selected comparisons, retaining all other physics decisions."""
    from adroit.parameter_space.limits import StatisticalLimit
    result=row.model_copy(deep=True)
    for item in items:
        value=outcome(cls,p,item)
        name=value.name
        if item.contract.supersedes and HIGGS_RECORD in item.contract.supersedes:
            result.ratios.pop(name,None)
            result.chi2.pop(name,None)
            result.pending=[s for s in result.pending if name not in s]
        result.excluded[name]=value.excluded
        if value.value is not None:
            result.values[name]=value.value
        if value.excluded is None:
            result.pending.append(name+': '+value.why)
        if value.confidence_level!=.95:
            result.native_constraints[name]=value
        result.search_results=[o for o in result.search_results if o.name!=name]+[value]
        result.statistical_limits[name]=StatisticalLimit(value=value.value,confidence_level=value.confidence_level,
            source=item.reference,construction=value.statistical_construction)
    return result
