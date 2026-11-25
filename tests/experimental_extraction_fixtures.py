"""Known typed source facts; independent expected values for intake tests."""
import json
from adroit.core.experimental_input import ExperimentalClaim,ExperimentalResult,SourceLocator
from adroit.agents.experimental_extraction import ExtractionAnswer

VALUES={'target':'Si','exposure':1000.,'energy_scale':'keVnr','window':[5.,30.],
    'events':[8.6,10.4,14.2],'resolution':.2,'background_count':.4,'background_treatment':'fixed_flat',
    'efficiency':{'recoil_energy_kev':[5.,30.],'efficiency':[1.,1.]},'efficiency_space':'true_energy',
    'exposure_selection':'before_selection','halo':{'v0_km_s':220.,'v_earth_km_s':232.,'v_esc_km_s':544.,'rho_gev_cm3':.3}}
TEXT='Synthetic source; all energies are nuclear recoil keVnr. Exposure in kg day.\n'+json.dumps(VALUES)+'\nAlternative background estimate: 0.5 events.'

def answer(asset_sha: str,text: str=TEXT,page=None,method='text',kind='events'):
    claims=[]
    for key,value in VALUES.items():
        unit='kg day' if key=='exposure' else ('keVnr' if key in ('window','events','resolution') else '')
        source=SourceLocator(asset_sha256=asset_sha,page=page,method=method,excerpt=text,
                             region=(0,0,600,400) if page and method=='visual' else None)
        claims.append(ExperimentalClaim(key=key,category='observation',value=value,units=unit,status='sourced',sources=[source]))
    return ExtractionAnswer(results=[ExperimentalResult(result_id='signal',kind=kind,claims=claims)],
                            explanation='Interpreted actual event list, explicit response, exposure and fixed positive background.')
