import pytest
from adroit.core.model_preferences import ModelPreference,StyleDeclaration,normalize_property,properties,parse_preference,select
from adroit.orchestrator import signal

def test_style_language_unknown_theory_and_exact_splitting():
    assert parse_preference('should be SUSY')==ModelPreference(property='susy')
    assert parse_preference('prefer inelastic dark matter')==ModelPreference(property='inelastic',mode='preferred')
    assert parse_preference('SUSY or composite').property=='susy or composite'
    assert parse_preference('with a leptophilic mediator').property=='a leptophilic mediator'
    cards=[signal.Candidate(label='elastic',card_id='O1',mass_gev=50),
           signal.Candidate(label='endothermic',card_id='O1',mass_gev=50,splitting_kev=20),
           signal.Candidate(label='exothermic',card_id='O1',mass_gev=50,splitting_kev=-20)]
    kept,excluded,matches=select(cards,[ModelPreference(property='inelastic')])
    assert [c.label for c in kept]==['endothermic','exothermic'] and excluded=={'elastic':'inelastic: no'}
    with pytest.raises(ValueError,match='no candidates establish'):
        select(cards,[ModelPreference(property='susy')])
    kept,_,matches=select(cards,[ModelPreference(property='susy',mode='preferred')])
    assert kept==cards and matches['elastic']['susy']=='unknown'

def test_preferences_leave_fits_and_ranking_unchanged_and_a_requirement_keeps_the_trials_factor(monkeypatch):
    from tests.orchestrator.test_signal import ToyGermanium
    monkeypatch.setitem(signal.modules.SIGNAL_SEARCHES,'toy germanium',ToyGermanium)
    declaration=StyleDeclaration(property='leptophilic mediator',state='yes',source='Controlled synthetic model declaration',
                                  scope='Illustrative reviewed property, not a theory certificate',reviewed_by='Test fixture')
    candidates=[signal.Candidate(label='a',card_id='O1',isospin='s',mass_gev=30,style_declarations=[declaration]),
                signal.Candidate(label='b',card_id='O4',isospin='s',mass_gev=30)]
    request=signal.SignalRequest(experiment='toy germanium',candidates=candidates,null_modules=[],toys=20,complementary=False)
    base=signal.run(request)
    preferred=signal.run(request.model_copy(update={'model_preferences':[ModelPreference(property='leptophilic mediator',mode='preferred')]}))
    assert preferred.fits==base.fits and preferred.combinations==base.combinations and preferred.tournament==base.tournament
    assert preferred.style_matches=={'a':{'leptophilic mediator':'yes'},'b':{'leptophilic mediator':'unknown'}}
    required=signal.run(request.model_copy(update={'model_preferences':[ModelPreference(property='leptophilic mediator')]}))
    assert [f.label for f in required.fits]==['a'] and required.style_excluded=={'b':'leptophilic mediator: unknown'}
    assert 'selected NR candidate space' in required.global_method
    assert required.fits[0]==base.fits[0]
    # release audit minor: a requirement no longer shrinks the headline's trials factor
    assert 'before the style filter' in required.global_method and required.global_z<=base.global_z+1e-9

def test_duplicate_or_contradictory_property_policies_refused():
    c=signal.Candidate(label='a',mass_gev=30)
    with pytest.raises(ValueError,match='one required/preferred'):
        select([c],[ModelPreference(property='susy'),ModelPreference(property='susy',mode='preferred')])
    with pytest.raises(ValueError):
        StyleDeclaration(property='susy',state='yes',source=' ',scope='model',reviewed_by='Reviewer')

def test_explicit_library_splitting_grid_is_used_even_with_published_space(monkeypatch):
    class Published:
        def model_space(self):return [{'label':'elastic published','card_id':'O1','mass_gev':30}]
    monkeypatch.setattr(signal,'LIBRARY_MASSES',[30])
    request=signal.SignalRequest(experiment='fixture',splittings_kev=[0,50],model_preferences=[ModelPreference(property='inelastic')])
    candidates=signal.candidates_for(request,Published())
    assert candidates and all(c.splitting_kev==50 for c in candidates)
    assert signal.model_space(Published(),[0])[0].label=='elastic published'

def test_open_vocabulary_multiple_properties_unknowns_and_contradictions():
    def declaration(key,state='yes'):
        return StyleDeclaration(property=key,state=state,source='Independent controlled source',scope='Reviewed assertion only',reviewed_by='Fixture')
    c=signal.Candidate(label='custom',mass_gev=30,style_declarations=[declaration('Hidden-sector U(1)'),declaration('  composite  dark matter '),declaration('thermal relic','no')])
    assert normalize_property('Hidden-sector U(1)')=='hidden-sector u(1)'
    policies=[parse_preference('with Hidden-sector U(1)'),parse_preference('should be composite dark matter')]
    kept,_,matches=select([c],policies)
    assert kept==[c] and set(matches['custom'])=={'hidden-sector u(1)','composite dark matter'}
    assert select([c],[parse_preference('prefer axion-like interactions')])[2]['custom']['axion-like interactions']=='unknown'
    with pytest.raises(ValueError,match='no candidates establish'):
        select([c],[parse_preference('require thermal relic')])
    with pytest.raises(ValueError,match='no candidates establish'):
        select([c],[parse_preference('require axion-like interactions')])
    assert select([c],[])==([c],{}, {})
    bad=c.model_copy(update={'style_declarations':[declaration('thermal relic'),declaration('thermal relic','no')]})
    with pytest.raises(ValueError,match='contradictory'):
        properties(bad)
    bad=c.model_copy(update={'style_declarations':[declaration('inelastic')]})
    with pytest.raises(ValueError,match='contradictory'):
        properties(bad)
    for text in ('','   ','x'*201):
        with pytest.raises(ValueError):
            normalize_property(text)

def test_catalog_general_declarations_are_pinned_and_available_to_selection(tmp_path,monkeypatch):
    from adroit.orchestrator.model_intake import Intake
    from adroit.library.personal import Catalog
    from adroit.core.config import get_settings
    from adroit.orchestrator.model_approval import model_identity
    from adroit.parameter_space.simplified import model
    import yaml
    catalog=Catalog(tmp_path/'models')
    service=Intake(catalog)
    session=service.start()
    spec=model('vector',30,125,.001,.25)
    d=service.step(session.session_id,'typed',yaml.safe_dump(spec.model_dump(mode='json')))
    declaration=StyleDeclaration(property='arbitrary reviewed property',state='yes',source='Controlled fixture',scope='Synthetic assertion, not a classification',reviewed_by='Fixture')
    r=service.approve(session.session_id,d.step_id,0,confirmed=True,expected_model_hash=model_identity(spec),
        tex=d.choices[0].tex,style_declarations=[declaration])
    monkeypatch.setattr(get_settings(),'model_library_dir',catalog.root)
    request=signal.SignalRequest(experiment='fixture',user_models=[signal.UserModel(spec=spec,catalog_reference=r.reference,masses_gev=[30])],
        model_preferences=[ModelPreference(property='arbitrary reviewed property')])
    assert signal.candidates_for(request,object())[0].style_declarations==[declaration]
    assert catalog.load(r.reference).provenance['model_styles'][0]['property']==declaration.property
