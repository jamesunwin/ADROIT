import pytest
from tests.private_search_fixtures import fixture,eligible
from adroit.library import experimental_profiles as profiles
from adroit.orchestrator.signal import SignalRequest
from adroit.orchestrator.track1 import for_portal

def make_profile(catalog,signal,null,parent=''):
    review=profiles.review_selection([],signal.reference,[null.reference],catalog)
    return profiles.create('Controlled fixture',[],signal.reference,[null.reference],review['review_sha256'],'Fixture',
                           confirmed=True,independence_confirmed=True,parent=parent,catalog=catalog)

def test_immutable_profile_activation_rollback_and_pinned_jobs(tmp_path):
    catalog,r=fixture(tmp_path/'signal')
    signal=eligible(catalog,r)
    _,r=fixture(tmp_path/'null','null',catalog=catalog)
    null=eligible(catalog,r,'null')
    p=make_profile(catalog,signal,null)
    assert profiles.active(catalog)==''
    with pytest.raises(ValueError):
        profiles.activate(p.reference,'',confirmed=False,catalog=catalog)
    profiles.activate(p.reference,'',confirmed=True,catalog=catalog)
    assert profiles.active(catalog)==p.reference
    pinned=profiles.selected('',catalog)
    next_=make_profile(catalog,signal,null,parent=p.reference)
    profiles.activate(next_.reference,p.reference,confirmed=True,catalog=catalog)
    assert pinned==p.reference and profiles.load(pinned,catalog)==p
    with pytest.raises(ValueError,match='changed since review'):
        profiles.activate(p.reference,p.reference,confirmed=True,catalog=catalog)
    profiles.activate(p.reference,next_.reference,confirmed=True,catalog=catalog)
    profiles.activate('',p.reference,confirmed=True,catalog=catalog)
    assert profiles.active(catalog)=='' and profiles.selected('none',catalog)==''
    assert profiles.apply_signal(SignalRequest(experiment=signal.reference,experimental_profile=p.reference),catalog).null_modules==[null.reference]
    assert profiles.apply_track1(for_portal('higgs_portal_scalar',experimental_profile=p.reference),catalog).experimental_profile==p.reference
    with pytest.raises(ValueError,match='signal differs'):
        profiles.apply_signal(SignalRequest(experiment='LZ extended window (2026)',experimental_profile=p.reference),catalog)

def test_overlap_wrong_roles_unknowns_and_stale_binding_refused(tmp_path):
    catalog,r=fixture(tmp_path/'signal')
    signal=eligible(catalog,r)
    _,r=fixture(tmp_path/'null','null',catalog=catalog)
    null=eligible(catalog,r,'null')
    for signal_name,nulls in [(signal.reference,[signal.reference]),(null.reference,[]),('',[signal.reference]),('',[null.reference,null.reference])]:
        with pytest.raises(ValueError):
            profiles.review_selection([],signal_name,nulls,catalog)
    p=make_profile(catalog,signal,null)
    path=catalog.path(f'profiles/{p.profile_id}.json')
    path.write_text(path.read_text().replace('Controlled fixture','Modified fixture'))
    with pytest.raises(ValueError,match='modified'):
        profiles.load(p.reference,catalog)

def test_profile_receipt_requires_exact_displayed_scope(tmp_path):
    catalog,r=fixture(tmp_path/'signal')
    signal=eligible(catalog,r)
    review=profiles.review_selection([],signal.reference,[],catalog)
    for consent in (False,True):
        with pytest.raises(ValueError):
            profiles.create('Fixture',[],signal.reference,[],
            'bad hash' if consent else review['review_sha256'],'Fixture',confirmed=consent,
            independence_confirmed=consent,catalog=catalog)
