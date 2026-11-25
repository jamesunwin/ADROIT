import pytest

from adroit.orchestrator import runs,track1
from adroit.parameter_space.scan import Axis
from adroit.evidence.archive import export_run,verify_bundle
from adroit.evidence.replay import replay_bundle
from adroit.evidence.build import read
from tests.private_limit_fixtures import fixture,eligible

@pytest.mark.needs("diamx", "cdmslite", "solar_model")
def test_private_limit_snapshot_changes_comparison_and_replays_without_library(tmp_path,monkeypatch):
    from adroit.core.config import get_settings
    from adroit.parameter_space.private_limits import HIGGS_RECORD
    catalog,r=fixture(tmp_path,'sm_higgs_invisible',overlap='supersedes',supersedes=[HIGGS_RECORD])
    bound=eligible(catalog,r)
    monkeypatch.setattr(get_settings(),'experimental_library_dir',catalog.root)
    request=track1.for_portal('higgs_portal_scalar',literature=False,workers=1,
        x=Axis(parameter='m_chi',low=39,high=41,n=2),y=Axis(parameter='g_chi',low=.008,high=.01,n=2),private_limits=[bound.reference])
    folder=tmp_path/'run'
    runs.track1(request,folder)
    result=track1.Track1Result.model_validate_json((folder/'result.json').read_text())
    assert result.scan.request.private_limits[0]==bound
    assert all(row.statistical_limits['invisible Higgs width (ATLAS)'].source==bound.reference for row in result.scan.points)
    envelope=read(folder/'result.json')
    assert envelope.context.origin=='captured'
    assert next(s for s in envelope.context.sources if s.id==bound.reference).review=='verified'
    bundle=tmp_path/'private.zip'
    export_run(folder/'result.json',bundle)
    assert verify_bundle(bundle).valid
    monkeypatch.setattr(get_settings(),'experimental_library_dir',tmp_path/'unavailable')
    replay=replay_bundle(bundle)
    assert replay.status=='matched',replay.model_dump()
