"""Independent dense integration/score/gap references for synthetic event inputs."""
import json
import math
import numpy as np
from scipy.integrate import simpson,cumulative_trapezoid
from scipy.optimize import brentq
from scipy.special import erf
from adroit.core.experimental_input import ExperimentalClaim,ExperimentalResult,SourceLocator
from adroit.library.experimental import ExperimentalCatalog
from adroit.core.private_searches import SearchContract
from adroit.constraints.experimental_review import packet,approve,CHECKLIST
from adroit.constraints.experimental_search_review import validate,bind

def reference(values,mass,legacy=False):
    """Reuse the rate kernel only; independently integrate and fit all adapter steps (``legacy``: the densities
    normalised in true energy, as before the audit's A09)."""
    from adroit.core.dm_state import DarkMatterParticle,HaloModel,NuclearModel,CrossSectionKind
    from adroit.experiments.base import element_rates,reference_interaction
    from adroit.physics.targets import target
    grid=np.linspace(*values['window'],16001)
    sigma=1e-40
    raw=sum(element_rates(grid,DarkMatterParticle(mass_gev=mass),reference_interaction(CrossSectionKind.si,sigma,mass),
        target(values['target']),HaloModel(rho_gev_cm3=values['halo']['rho_gev_cm3'],v0_km_s=values['halo']['v0_km_s'],
            v_esc_km_s=values['halo']['v_esc_km_s'],v_lsr_km_s=(0.,values['halo']['v_earth_km_s'],0.),
            v_peculiar_km_s=(0.,0.,0.),v_earth_km_s=(0.,0.,0.)),NuclearModel.helm).values())
    rate=values['exposure']*np.interp(grid,values['efficiency']['recoil_energy_kev'],values['efficiency']['efficiency'])*raw
    total=float(simpson(rate,x=grid))
    # the share of the window's events seen inside it, which normalises the densities on the window (audit A09)
    width=values['resolution']*math.sqrt(2)
    seen=float(simpson(rate*.5*(erf((values['window'][1]-grid)/width)-erf((values['window'][0]-grid)/width)),x=grid))
    f=[]
    for energy in values['events']:
        kernel=np.exp(-.5*((grid-energy)/values['resolution'])**2)/(values['resolution']*math.sqrt(2*math.pi))
        f.append(float(simpson(rate*kernel,x=grid))/(total if legacy else seen))
    f=np.array(f)
    background=values['background_count']/np.ptp(values['window'])
    s=0. if not len(f) or (f/background).sum()<=1 else brentq(lambda s:(f/(s*f+background)).sum()-1,0,100)
    top=float(-s+np.log(s*f+background).sum())
    cumulative=cumulative_trapezoid(rate,grid,initial=0)
    cumulative/=cumulative[-1]
    fractions=np.interp(values['events'],grid,cumulative)
    gap=float(np.diff(np.r_[0,sorted(fractions),1]).max())
    def probability(mu):
        # Independent Poisson mixture of exact uniform-spacing inclusion/exclusion.
        weight=math.exp(-mu)
        answer=0.
        for n in range(200):
            conditional=sum((-1)**k*math.comb(n+1,k)*max(0.,1-k*gap)**n
                for k in range(min(n+1,int(1/gap))+1))
            answer+=weight*conditional
            weight*=mu/(n+1)
        return answer
    def bound(cl):return brentq(lambda mu:probability(mu)-cl,1e-8,80)/total
    return dict(mass_gev=mass,sigma_cm2=sigma,total_events=total,event_densities=f.tolist(),s_hat=s,log_l_hat=top,
                kappa90=bound(.9),kappa95=bound(.95))

def fixture(tmp_path,role='signal',catalog=None,legacy_anchors=False,**changes):
    tmp_path.mkdir(parents=True,exist_ok=True)
    catalog=catalog or ExperimentalCatalog(tmp_path/'private')
    values={'target':'Si','exposure':100.,'energy_scale':'keVnr','window':[1.,20.],
        'events':[3.,7.] if role=='signal' else [],'resolution':.2,'background_count':.3,
        'background_treatment':'fixed_flat','efficiency':{'recoil_energy_kev':[1.,20.],'efficiency':[.5,.5]},
        'efficiency_space':'true_energy','exposure_selection':'before_selection',
        'halo':{'rho_gev_cm3':.3,'v0_km_s':220.,'v_earth_km_s':232.,'v_esc_km_s':544.}}
    contract=SearchContract(role=role,benchmark='elastic_contact_O1_cp_equals_cn',mass_range=(10,40),dataset_id='synthetic:'+role,
        overlap='disjoint_from_selected',limit_construction='maximum_gap_no_background_subtraction',
        assumptions=['fidelity B: true-energy efficiency, constant Gaussian at events, fixed flat background',
                     'interval limits treat all events as possible signal; fixed-bg log L omits the constant -B'],**changes)
    values['search_contract']=contract.model_dump(mode='json')
    anchors={'anchors':[reference(values,m,legacy_anchors) for m in (10.,20.,40.)]}
    source=tmp_path/'event_source.json'
    independent=tmp_path/'independent_reference.json'
    source.write_text(json.dumps(values))
    independent.write_text(json.dumps(anchors))
    revision=catalog.import_files([source,independent],'Controlled synthetic '+role)
    units={'exposure':'kg day','window':'keVnr','events':'keVnr','resolution':'keVnr'}
    claims=[ExperimentalClaim(key=key,category='observation',value=value,status='sourced',units=units.get(key,''),
        sources=[SourceLocator(asset_sha256=revision.sources[0].sha256,method='structured',excerpt=source.read_text())]) for key,value in values.items()]
    claims.append(ExperimentalClaim(key='adapter_validation_reference',category='availability',value=anchors,status='sourced',
        sources=[SourceLocator(asset_sha256=revision.sources[1].sha256,method='structured',excerpt=independent.read_text())]))
    result=ExperimentalResult(result_id=role,kind='events',claims=claims,dataset_ids=[contract.dataset_id],
                              overlap={'disjoint_from_selected':'disjoint','supersedes':'overlapping','unknown':'unknown'}[contract.overlap],supersedes=contract.supersedes)
    dossier=revision.dossier.model_copy(update={'results':[result]})
    return catalog,catalog.save(dossier,revision.sources,revision.ingestions,revision.reference)

def eligible(catalog,revision,role='signal'):
    value=packet(revision.reference,role,catalog=catalog)
    review=approve(revision.reference,role,value['scientific_sha256'],'Controlled synthetic acceptance, not a publication reviewer',
                   confirmed=True,checks=CHECKLIST,catalog=catalog)
    validation=validate(revision.reference,role,.001,value['scientific_sha256'],catalog)
    assert validation.passed,validation.errors
    return bind(revision.reference,role,review.review_id,validation.validation_id,catalog)
