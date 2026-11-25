import pytest
from tests.private_search_fixtures import fixture,eligible
from adroit.constraints.experimental_search_review import validate,load_bound
from adroit.constraints.experimental_review import packet,approve,CHECKLIST
from adroit.experiments.private_search import PrivateEventSearch
from adroit.core.dm_state import DarkMatterParticle,CrossSectionKind
from adroit.experiments.base import reference_interaction
from adroit.orchestrator import signal

def test_independent_dense_response_score_and_gap_references_and_null_usage(tmp_path,monkeypatch):
    catalog,revision=fixture(tmp_path/'signal')
    bound=eligible(catalog,revision)
    assert load_bound(bound.reference,catalog)==bound
    module=PrivateEventSearch(bound,catalog)
    assert module.verified and module.info.name==bound.reference
    c=signal.Candidate(label='SI20',interaction=reference_interaction(CrossSectionKind.si,1e-40,20),mass_gev=20)
    prediction=signal._signal(module,c)
    assert prediction.total_events==pytest.approx(bound.validation.anchors[1].total_events,rel=.001)
    null_catalog,null_revision=fixture(tmp_path/'null',role='null',catalog=catalog)
    null=eligible(catalog,null_revision,'null')
    from adroit.core.config import get_settings
    monkeypatch.setattr(get_settings(),'experimental_library_dir',catalog.root)
    result=signal.run(signal.SignalRequest(experiment=bound.reference,candidates=[c],null_modules=[null.reference],toys=30,complementary=False))
    assert result.fits[0].s_hat>0 and result.combinations[0].null_coverage=='complete'
    assert null.reference in result.combinations[0].null_limits
    assert result.combinations[0].z_joint<=result.combinations[0].z_signal

def test_source_approval_failed_validation_and_changed_assumptions_are_distinct(tmp_path):
    catalog,revision=fixture(tmp_path)
    dossier=revision.dossier.model_copy(deep=True)
    next(c for c in dossier.results[0].claims if c.key=='adapter_validation_reference').value['anchors'][0]['total_events']*=2
    changed=catalog.save(dossier,revision.sources,revision.ingestions,revision.reference)
    value=packet(changed.reference,'signal',catalog=catalog)
    approve(changed.reference,'signal',value['scientific_sha256'],'Fixture',confirmed=True,checks=CHECKLIST,catalog=catalog)
    with pytest.raises(ValueError,match='unchecked'):
        validate(changed.reference,'signal',.001,value['scientific_sha256'],catalog)
    original=eligible(catalog,revision)
    altered=catalog.path(f'searches/{original.search_id}.json')
    altered.write_text(altered.read_text().replace('fixed flat background','different background'))
    with pytest.raises(ValueError,match='modified'):
        load_bound(original.reference,catalog)

def test_an_anchor_in_the_pre_a09_convention_is_refused_by_name(tmp_path):
    """Anchors whose densities are normalised in true energy (the leak across the window's edges left in) are named
    as the old convention, not reported as a mismatch (the external audit of 2026-10-16, A09)."""
    catalog,revision=fixture(tmp_path,legacy_anchors=True)
    value=packet(revision.reference,'signal',catalog=catalog)
    approve(revision.reference,'signal',value['scientific_sha256'],'Fixture',confirmed=True,checks=CHECKLIST,catalog=catalog)
    with pytest.raises(ValueError,match='before the audit A09'):
        validate(revision.reference,'signal',.001,value['scientific_sha256'],catalog)

def test_private_adapter_refuses_outside_benchmark_or_range(tmp_path):
    catalog,revision=fixture(tmp_path)
    bound=eligible(catalog,revision)
    module=PrivateEventSearch(bound,catalog)
    for mass,kind,delta in [(5,CrossSectionKind.si,0),(20,CrossSectionKind.sd_proton,0),(20,CrossSectionKind.si,10)]:
        particle=DarkMatterParticle(mass_gev=mass,mass_splitting_kev=delta)
        with pytest.raises(ValueError,match='validated only'):
            module.expected_signal(particle,reference_interaction(kind,1e-40,mass),module.conventions().halo,module.conventions().nuclear_model)
