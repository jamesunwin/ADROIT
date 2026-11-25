import pytest
from tests.private_limit_fixtures import fixture,eligible
from adroit.parameter_space.private_limits import outcome,limit_interval,validate_selection,HIGGS_RECORD
from adroit.parameter_space.classes import Point,Spin1Class,ScalarClass
from adroit.parameter_space.portals.higgs import HiggsPortalScalar

def test_private_si_native_cl_and_domain_are_preserved(tmp_path):
    catalog,r=fixture(tmp_path,confidence_level=.9)
    bound=eligible(catalog,r)
    result=outcome(HiggsPortalScalar(),Point(m_chi=20,m_med=125.09,g_chi=.001),bound)
    assert result.excluded is False and result.confidence_level==.9 and result.native_ratio is not None
    assert 'hence at 95%' in result.why                     # R3: allowed at the native 90% is allowed at 95%
    outside=outcome(HiggsPortalScalar(),Point(m_chi=5,m_med=125.09,g_chi=.001),bound)
    assert outside.excluded is None and outside.coverage['applicability']=='outside_domain'

def test_si_cannot_be_transferred_to_other_operators(tmp_path):
    catalog,r=fixture(tmp_path)
    bound=eligible(catalog,r)
    result=outcome(ScalarClass(dm_pseudoscalar=True),Point(m_chi=20,m_med=125),bound)
    assert result.excluded is None and 'dedicated source recast' in result.why
    subleading=outcome(Spin1Class(),Point(m_chi=20,m_med=125),bound)
    assert subleading.excluded is None and 'does not match' in subleading.why

def test_digitisation_range_preserves_ambiguous_thresholds(tmp_path):
    catalog,r=fixture(tmp_path,origin='figure_digitised',x_relative_error=.01,y_relative_error=.1)
    bound=eligible(catalog,r)
    central,low,high=limit_interval(bound.contract,20)
    assert low<central<high and limit_interval(bound.contract,10) is None
    with pytest.raises(ValueError):
        fixture(tmp_path,origin='figure_digitised')

def test_higgs_replacement_is_specific_and_duplicate_datasets_are_refused(tmp_path):
    catalog,r=fixture(tmp_path,'sm_higgs_invisible',overlap='supersedes',supersedes=[HIGGS_RECORD])
    bound=eligible(catalog,r)
    validate_selection([bound])
    result=outcome(HiggsPortalScalar(),Point(m_chi=40,m_med=125.09,g_chi=.01),bound)
    assert result.name=='invisible Higgs width (ATLAS)' and result.coverage['limit']==.05
    assert result.ratio is None
    with pytest.raises(ValueError):
        validate_selection([bound,bound])
    wrong=bound.model_copy(deep=True)
    wrong.contract.supersedes=['wrong_dataset']
    with pytest.raises(ValueError):
        validate_selection([wrong])
