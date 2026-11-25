"""Native-95 private null cuts through their declared event procedure."""
import math
from adroit.core.dm_state import DarkMatterParticle
from adroit.parameter_space.limits import StatisticalLimit

def apply(result,cls,point,searches):
    """Add each private null search to ``result`` at 95%: ratio 1/κ of its event procedure's limit κ on the rate
    multiplier, excluded above 1; a signal search or a point that is not elastic SI is pending instead."""
    from adroit.experiments.private_search import PrivateEventSearch
    excluded=dict(result.excluded)
    pending=list(result.pending)
    values=dict(result.values)
    stats=dict(result.statistical_limits)
    for bound in searches:
        name=bound.reference
        module=PrivateEventSearch(bound,False)
        particle=DarkMatterParticle(mass_gev=point.m_chi,spin=cls.SPIN if hasattr(cls,'SPIN') else .5)
        try:
            if bound.contract.role!='null':
                raise ValueError('signal search is not an independent null cut')
            if cls.dd(point)[0]!='SI':
                raise ValueError('private event null needs an elastic SI model mapping; no inelastic/operator transfer')
            prediction=module.expected_signal(particle,cls.interaction(point),module.conventions().halo,module.conventions().nuclear_model)
            kappa=module.upper_limit(prediction,.95) if prediction.total_events>0 else math.inf
            ratio=1/kappa if math.isfinite(kappa) and kappa>0 else 0.
            excluded[name]=ratio>1
            values[name]=ratio
            stats[name]=StatisticalLimit(value=kappa if math.isfinite(kappa) else None,confidence_level=.95,source=name,
                construction=bound.contract.limit_construction+' evaluated at CL=.95; value is dimensionless rate multiplier kappa; independent fidelity-B adapter')
        except (ValueError,RuntimeError,KeyError) as error:
            excluded[name]=None
            pending.append(name+': '+str(error))
            stats[name]=StatisticalLimit(value=None,confidence_level=.95,source=name,construction=bound.contract.limit_construction,
                                        omitted={name:str(error)})
    return result.model_copy(update={'excluded':excluded,'pending':pending,'values':values,'statistical_limits':stats})
