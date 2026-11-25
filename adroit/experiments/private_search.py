"""Pinned reviewed event modules; no global registry or validation-range mutation."""
from adroit.experiments.anomaly import RecordSearch
from adroit.core.private_searches import BoundPrivateSearch

def interval_upper(events,signal,cl,construction):
    """Use the declared procedure; never silently replace optimum interval."""
    import numpy as np
    from adroit.statistics import intervals,optimum_interval
    fractions=intervals.cumulative_fractions(events,np.asarray(signal.observable),np.asarray(signal.density))
    if construction=='maximum_gap_no_background_subtraction':
        mu=intervals.maximum_gap_limit(fractions,cl)
    else:
        if not optimum_interval.available():
            raise ValueError('declared optimum-interval backend is unavailable; no silent fallback')
        mu,_=optimum_interval.optimum_interval_limit(fractions,cl)
    return mu/signal.total_events

class PrivateEventSearch(RecordSearch):
    """A record search pinned to a bound private search (``BoundPrivateSearch``): its reviewed record, contract and
    validation."""
    def __init__(self,bound:BoundPrivateSearch,catalog=None):
        from adroit.library.experimental import ExperimentalCatalog
        self.bound=bound
        self.catalog=catalog or ExperimentalCatalog()
        self.revision=self.catalog.load(bound.revision) if catalog is not False else None
        self.review=bound.review
        super().__init__(bound.record,key=bound.search_id)
        self.name=bound.reference

    @property
    def verified(self):
        """Always True: a bound private search carries its review."""
        return True

    @property
    def info(self):
        """The record's info under the bound search's reference, with its validation scope, its limit construction,
        and its data pointing at the search file."""
        value=super().info
        data=[d.model_copy(update={'path':str(self.catalog.path(f'searches/{self.bound.search_id}.json'))}) for d in value.data]
        return value.model_copy(update={'name':self.bound.reference,'validation_note':self.bound.validation.scope,'data':data,
            'statistical_method':self.bound.contract.limit_construction})

    def accepts_validation(self,particle,interaction,cl=.9):
        """Whether the point lies in the validated domain: CL of 90% or 95%, elastic, inside the contract's mass
        range, and an interaction proportional to the spin-independent reference (or O₁ with zero couplings)."""
        from adroit.orchestrator.exclusion import _reference_route
        from adroit.core.dm_state import CrossSectionKind
        route=_reference_route(interaction,particle.mass_gev)
        lo,hi=self.bound.contract.mass_range
        zero_o1=bool(interaction.coefficients) and all(c.operator==1 and c.proton==0 and c.neutron==0 and c.q_power==0
                                                     for c in interaction.coefficients)
        return cl in (.9,.95) and particle.mass_splitting_kev==0 and lo<=particle.mass_gev<=hi and (zero_o1 or route is not None and route[0]==CrossSectionKind.si)

    def expected_signal(self,particle,interaction,halo,model,target=None):
        """The record's signal, refused outside the validated domain (``accepts_validation``)."""
        if not self.accepts_validation(particle,interaction):
            raise ValueError('private event adapter is validated only for elastic isoscalar contact O1 in its declared mass range')
        return super().expected_signal(particle,interaction,halo,model,target)

    def upper_limit(self,signal,cl=.9):
        """κ_up by the contract's declared interval construction (``interval_upper``), at 90% or 95% CL only."""
        if cl not in (.9,.95):
            raise ValueError('private interval procedure validated only at native 90/95 percent')
        return interval_upper(self.events,signal,cl,self.bound.contract.limit_construction)

    def evidence(self):
        """The bound search, the dossier revision (if loaded) and the validation scope."""
        return {'bound_search':self.bound.model_dump(mode='json'),
                'dossier':self.revision.model_dump(mode='json') if self.revision else None,'scope':self.bound.validation.scope}

    def input_files(self):
        """The catalog files the module rests on: the search, its review, its validation and the dossier revision."""
        return [self.catalog.path(f'searches/{self.bound.search_id}.json'),
                self.catalog.path(f'reviews/{self.review.review_id}.json'),
                self.catalog.path(f'search_validations/{self.bound.validation.validation_id}.json'),
                self.catalog.path(f'experiments/{self.revision.experiment_id}/{self.revision.revision_id}.json')]

    @classmethod
    def from_name(cls,reference):
        """``private-search:<hash>`` → the module of that pinned bound search."""
        from adroit.constraints.experimental_search_review import load_bound
        return cls(load_bound(reference))
