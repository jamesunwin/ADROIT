"""Independent deterministic private source/reference fixtures, not publication review."""
import json
from adroit.library.experimental import ExperimentalCatalog
from adroit.core.experimental_input import ExperimentalResult,ExperimentalClaim,SourceLocator
from adroit.core.private_limits import LimitContract
from adroit.constraints.experimental_review import packet,approve,validate,bind,CHECKLIST

def fixture(tmp_path,adapter='si_isoscalar_curve',catalog=None,**changes):
    tmp_path.mkdir(parents=True,exist_ok=True)
    catalog=catalog or ExperimentalCatalog(tmp_path/'private')
    if adapter=='si_isoscalar_curve':
        data=dict(adapter=adapter,benchmark='elastic_contact_O1_cp_equals_cn',quantity='sigma_nucleon_cm2',
            units='cm2',points=[(10,1e-43),(20,2e-43),(40,4e-43)],mass_range=(10,40),
            halo={'rho_gev_cm3':.3,'v0_km_s':220.,'v_earth_km_s':232.,'v_esc_km_s':544.})
        anchors=[[10,1e-43],[15,1.5e-43],[40,4e-43]]
    else:
        data=dict(adapter=adapter,benchmark='SM_higgs_125_production',quantity='BR_h_invisible',units='dimensionless',value=.05)
        anchors=[[125.09,.05]]
    data.update(confidence_level=.95,construction='native published upper-limit construction',selection='observed',
        dataset_id='synthetic:'+adapter,overlap='disjoint_from_selected',origin='machine_table',
        assumptions=['native source convention, no benchmark or confidence-level transfer'],source_panel='Controlled source panel')
    data.update(changes)
    if data['origin']=='figure_digitised' and adapter=='si_isoscalar_curve':
        anchors=[[12,1.2e-43],[15,1.5e-43],[30,3e-43]]    # on the curve, not its digitised points
    contract=LimitContract(**data)
    source=tmp_path/'source.json'
    reference=tmp_path/'independent.json'
    source.write_text(contract.model_dump_json())
    # the authors' table in HEPData's format, as ADROIT retrieves it (its address and sha256 recorded: FR-01)
    reference.write_text(json.dumps({'independent_variables':[{'header':{'name':'mass','units':'GeV'},
                                                               'values':[{'value':x} for x,_ in anchors]}],
                                     'dependent_variables':[{'header':{'name':'limit','units':data['units']},
                                                             'qualifiers':[{'name':'CL','value':f"{100*data['confidence_level']:g}%"}],
                                                             'values':[{'value':y} for _,y in anchors]}]}))
    import hashlib
    retrieved=[{'url':'https://www.hepdata.net/download/table/ins0000000/limit/1/json','name':reference.name,
                'sha256':hashlib.sha256(reference.read_bytes()).hexdigest()}]
    r=catalog.import_files([source,reference],'Synthetic '+adapter,provenance={'retrieved':retrieved})
    claims=[ExperimentalClaim(key='limit_contract',category='limit',value=contract.model_dump(mode='json'),status='sourced',
        sources=[SourceLocator(asset_sha256=r.sources[0].sha256,method='structured',excerpt=source.read_text())]),
        ExperimentalClaim(key='validation_reference',category='limit',value={'points':anchors,'lineage':[
            {'derivation':'published_table','document':reference.name,'row':i+1,'mass_column':'mass',
             'limit_column':'limit'} for i in range(len(anchors))]},status='sourced',
        sources=[SourceLocator(asset_sha256=r.sources[1].sha256,method='structured',excerpt=reference.read_text())])]
    dossier=r.dossier.model_copy(update={'results':[ExperimentalResult(result_id='limit',kind='limit',claims=claims)]})
    r=catalog.save(dossier,r.sources,r.ingestions,r.reference)
    return catalog,r

def eligible(catalog,r):
    value=packet(r.reference,'limit',catalog=catalog)
    review=approve(r.reference,'limit',value['scientific_sha256'],'Controlled synthetic acceptance (not a publication review)',
        confirmed=True,checks=CHECKLIST,catalog=catalog)
    validation=validate(r.reference,'limit',.02,value['scientific_sha256'],catalog)
    assert validation.passed
    return bind(r.reference,'limit',review.review_id,validation.validation_id,catalog)
