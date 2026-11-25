from types import SimpleNamespace
from datetime import datetime
import pytest
from adroit.core.chronology import analysis_report,dated_report,model_references
from adroit.core.evidence import EvidenceContext


def test_report_distinguishes_calculation_revision_and_render_dates():
    context=EvidenceContext(identity='abc',calculation_started_at='2020-01-01T01:00:00+00:00',
                            calculation_completed_at='2020-01-01T02:00:00+00:00')
    report=analysis_report('# Results\n\nexcluded',context=context,references=['catalog:old@revision'])
    assert '2020-01-01T01:00:00+00:00' in report and '2020-01-01T02:00:00+00:00' in report
    assert 'Report generated (UTC)' in report and 'catalog:old@revision' in report and 'excluded' in report
    again=analysis_report(report,context=context)
    assert again.count('Report generated (UTC)')==1
    assert 'unknown / not recorded' in analysis_report('# Old\nresult')


def test_dates_require_utc_order_and_legacy_remains_unknown():
    assert not EvidenceContext().calculation_started_at
    for body in [dict(calculation_started_at='2020-01-01'),dict(calculation_completed_at='2020-01-01T00:00:00+00:00'),
                 dict(calculation_started_at='2020-01-02T00:00:00+00:00',calculation_completed_at='2020-01-01T00:00:00+00:00')]:
        with pytest.raises(ValueError):
            EvidenceContext(**body)


def test_date_decorator_does_not_invent_a_legacy_calculation_date():
    @dated_report
    def report(result):return '# Test\n\nvalue: 0'
    result=SimpleNamespace(created='2026-10-09',model_fields_set=set(),request=SimpleNamespace(catalog_reference='pinned',user_models=[]))
    text=report(result)
    assert 'unknown / not recorded' in text and 'pinned' in text and 'value: 0' in text
    result.model_fields_set={'created'}
    assert '2026-10-09 (saved date; time not recorded)' in report(result)
    assert model_references(result)==['pinned']


def test_timed_records_utc_start_and_completion_and_reports_show_them():
    from adroit.core.chronology import timed
    from adroit.core.model_spec import FieldRole, ModelField, ModelSpec
    from adroit.orchestrator import ideas
    result=ideas.run(ideas.IdeaRequest(fields_spec=ModelSpec(name='singlet',fields=[ModelField(
        name='S',role=FieldRole.dark_matter,spin=0,self_conjugate=True,dark_parity=-1,mass_gev=60.0)])))
    started,completed=(datetime.fromisoformat(t) for t in (result.calculation_started_at,result.calculation_completed_at))
    assert started.utcoffset().total_seconds()==0 and completed>=started
    text=ideas.report(result)
    assert f'Calculation started (UTC): {result.calculation_started_at}' in text and 'unknown / not recorded' not in text
    reread=ideas.IdeaResult.model_validate_json(result.model_dump_json())
    assert 'unknown / not recorded' not in ideas.report(reread)
    legacy=ideas.IdeaResult.model_validate({'request':result.request.model_dump()})
    assert 'unknown / not recorded' in ideas.report(legacy)
    assert timed(lambda: legacy)().calculation_started_at and timed(lambda: 3)()==3


@pytest.mark.parametrize('module,name',[('adroit.orchestrator.promote','Promotion'),('adroit.orchestrator.agents','AgentResult'),
    ('adroit.orchestrator.single_idea','SingleIdeaResult'),('adroit.orchestrator.lagrangian','LagrangianResult'),
    ('adroit.core.assistance','AssistanceResult')])
def test_every_calculation_result_can_carry_its_dates(module,name):
    import importlib
    fields=getattr(importlib.import_module(module),name).model_fields
    assert {'calculation_started_at','calculation_completed_at'}<=set(fields)


def test_written_reports_use_the_results_own_dates(tmp_path,monkeypatch):
    from adroit.core.model_spec import FieldRole, ModelField, ModelSpec
    from adroit.orchestrator import ideas, runs
    from adroit.orchestrator import studies
    monkeypatch.setattr(studies,'record',lambda *a,**k:None)
    result=ideas.run(ideas.IdeaRequest(fields_spec=ModelSpec(name='singlet',fields=[ModelField(
        name='S',role=FieldRole.dark_matter,spin=0,self_conjugate=True,dark_parity=-1,mass_gev=60.0)])))
    text=runs._write(tmp_path,result,ideas.report(result),'idea','t')
    assert text.count('<!-- adroit-chronology -->')==1 and result.calculation_completed_at in text
