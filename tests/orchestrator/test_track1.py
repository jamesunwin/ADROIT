"""DM13: Track 1 end to end, offline (a fake arXiv search, one worker, a coarse grid)."""

from pathlib import Path

import pytest
import yaml

from adroit.core.model_spec import ModelSpec
from adroit.orchestrator import track1
from adroit.parameter_space.scan import Axis
from adroit.retrieval.literature import Abstract

MODELS = Path(__file__).resolve().parents[2] / "docs" / "dm13"


def spec(name: str) -> ModelSpec:
    return ModelSpec.model_validate(yaml.safe_load((MODELS / f"{name}.yaml").read_text()))


def fake_fetch(query: str, n: int) -> list[Abstract]:
    return [Abstract(arxiv_id="1234.56789", title="An axial mediator", year=2020, query=query)]


def failing_fetch(query: str, n: int):
    raise ConnectionError("offline")


def test_literature_reports_papers_or_why_none():
    papers, note = track1.literature(spec("axial_mediator"), None, fake_fetch)
    assert papers[0].arxiv_id == "1234.56789" and note.startswith("arXiv search")
    papers, note = track1.literature(spec("axial_mediator"), None, failing_fetch)
    assert papers == [] and "could not be made: ConnectionError" in note


def test_an_unsupported_model_is_undetermined_with_its_validity(tmp_path):
    """A model neither the classes nor the generic route computes (a term that is not gauge invariant)."""
    from tests.orchestrator.test_dm14 import unbuildable
    result = track1.run(track1.Track1Request(spec=unbuildable(), literature=False), tmp_path)
    text = track1.report(result)
    assert "UNDETERMINED" in text and "cannot build it either" in text and "## 1. The model" in text


@pytest.mark.needs("diamx", "cdmslite", "solar_model")
def test_track1_report_is_complete(tmp_path):
    request = track1.Track1Request(spec=spec("axial_mediator"), workers=1, literature=True,
                                   x=Axis(parameter="m_med", low=100.0, high=3000.0, n=4),
                                   y=Axis(parameter="m_chi", low=50.0, high=1500.0, n=4))
    result = track1.run(request, tmp_path, fetch=fake_fetch)
    text = track1.report(result)
    assert result.verdict is not None and result.verdict.level in track1.LEVELS
    for section in ("## 2. The verdict", "## 3. Parameter space", "## 4. What was computed", "## 5. Literature",
                    "parameter_plane.png", "arXiv:1234.56789"):
        assert section in text
    assert (tmp_path / "parameter_plane.png").exists()


def test_report_uses_actual_planck_verification_status(monkeypatch):
    from datetime import date
    from adroit.constraints import database
    from adroit.model_building.audit import audit
    from adroit.parameter_space.classify import classify
    from adroit.parameter_space.scan import ScanRequest,ScanResult
    from adroit.parameter_space.verdict import Verdict
    model=spec('vector_mediator')
    cls,point,_=classify(model)
    scan=ScanResult(request=ScanRequest(model_class=cls,fixed=point,
        x=Axis(parameter='m_med',low=100,high=1000,n=2),
        y=Axis(parameter='m_chi',low=10,high=100,n=2)),xs=[100,1000],ys=[10,100],points=[])
    result=track1.Track1Result(request=track1.Track1Request(spec=model),audit=audit(model),
        fixed=point,scan=scan,verdict=Verdict(level='pending',target=.12,summary='No computed samples'))
    original=database.record
    def unverified(record_id):
        record=original(record_id)
        return record.model_copy(update={'verified_by':'','verified_on':None}) if record_id=='planck-2018-omega' else record
    monkeypatch.setattr(database,'record',unverified)
    text=track1.report(result)
    assert "Planck density record: awaits a person's verification" in text
    assert 'Curated records (verified by the owner)' not in text
    def verified(record_id):
        record=original(record_id)
        return record.model_copy(update={'verified_by':'Test reviewer','verified_on':date(2026,10,5)}) if record_id=='planck-2018-omega' else record
    monkeypatch.setattr(database,'record',verified)
    assert 'Planck density record: verified by Test reviewer on 2026-10-05' in track1.report(result)


def test_report_carries_one_chronology_block_under_its_title():
    from adroit.model_building.audit import audit
    from adroit.parameter_space.classify import classify
    from adroit.parameter_space.scan import ScanRequest,ScanResult
    from adroit.parameter_space.verdict import Verdict
    model=spec('vector_mediator')
    cls,point,_=classify(model)
    scan=ScanResult(request=ScanRequest(model_class=cls,fixed=point,
        x=Axis(parameter='m_med',low=100,high=1000,n=2),
        y=Axis(parameter='m_chi',low=10,high=100,n=2)),xs=[100,1000],ys=[10,100],points=[])
    result=track1.Track1Result(request=track1.Track1Request(spec=model),audit=audit(model),
        fixed=point,scan=scan,verdict=Verdict(level='pending',target=.12,summary='No computed samples'),created='2026-10-11')
    text=track1.report(result)
    assert text.count('<!-- adroit-chronology -->')==1 and text.startswith('# Track 1: ')
    assert text.splitlines()[2]=='<!-- adroit-chronology -->' and '2026-10-11 (saved date' in text
    assert track1.propagation_line('central').count('adroit-chronology')==0
