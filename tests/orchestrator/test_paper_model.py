import pytest
import yaml
from adroit.library.personal import Catalog
from adroit.orchestrator.model_intake import Intake
from adroit.orchestrator.paper_model import prepare,step,PaperInterpretation
from adroit.agents.llm import FakeLLMClient
from adroit.parameter_space.simplified import model
from adroit.orchestrator.model_approval import model_identity
from adroit.core.model_preferences import StyleDeclaration
from tests.experimental_fixtures import paper

def test_selected_pdf_pages_equation_original_and_model_revision_retained(tmp_path):
    service=Intake(Catalog(tmp_path/'models'))
    session=service.start(.5)
    pdf=paper(tmp_path/'source.pdf')
    spec=model('vector',10,125,.001,.25)
    fake=FakeLLMClient([PaperInterpretation(transcription='source Eq (7)',source_equation_tex='L = g V chi chi',
         equation_found=True,spec=spec,ambiguities=['Synthetic equation label; verify against original page'])])
    draft=step(service,session.session_id,pdf=pdf,pages=[2],equation='7',llm=fake)
    assert draft.transcription=='L = g V chi chi' and draft.choices[0].spec==spec
    text=fake.calls[0]['messages'][0]['content']
    assert 'PHYSICAL PAGE 2' in text and 'PHYSICAL PAGE 1' not in text
    assert len(fake.calls[0]['images'])==1
    edited=service.step(session.session_id,'typed',yaml.safe_dump(spec.model_dump(mode='json')),parent_step=draft.step_id)
    styles=[StyleDeclaration(property='susy',state='yes',source='Synthetic Eq 7',scope='Illustrative declaration, not a full SUSY theory',reviewed_by='Fixture')]
    r=service.approve(session.session_id,edited.step_id,0,confirmed=True,expected_model_hash=model_identity(spec),
                      tex=edited.choices[0].tex,style_declarations=styles)
    assert r.provenance['paper_equations'][0]['physical_pages']==[2]
    assert r.provenance['paper_equations'][0]['source_equation_tex']==draft.transcription
    assert r.provenance['model_styles'][0]['scope']==styles[0].scope
    assert any(a.suffix=='.pdf' for a in r.sources)
    assert service.catalog.verify_calculation(r.reference,spec,'track1').reference==r.reference
    assert service.catalog.verify_calculation(r.reference,spec,'track2').reference==r.reference
    with pytest.raises(ValueError,match='new draft/revision'):
        service.approve(session.session_id,edited.step_id,0,confirmed=True,expected_model_hash=model_identity(spec),
                        tex=edited.choices[0].tex,style_declarations=[])
    original=next(a for a in r.sources if a.suffix=='.pdf')
    service.catalog.asset_path(original).write_bytes(b'%PDF- modified')
    with pytest.raises(ValueError,match='source missing or modified'):
        service.catalog.load(r.reference)

def test_missing_equation_pages_and_credentials_blocked(tmp_path):
    service=Intake(Catalog(tmp_path/'models'))
    session=service.start(.5)
    pdf=paper(tmp_path/'source.pdf')
    fake=FakeLLMClient([PaperInterpretation(transcription='',source_equation_tex='',equation_found=False,spec=model('vector',10,125))])
    with pytest.raises(ValueError,match='not established'):
        step(service,session.session_id,pdf=pdf,pages=[1],equation='99',llm=fake)
    assert not service.steps(session.session_id) and not service.catalog.list()
    for pages in ([0],[3],[1,1],[]):
        with pytest.raises(ValueError):
            prepare(service,pdf=pdf,pages=pages,equation='1')
    with pytest.raises(ValueError):
        prepare(service,pdf=pdf,arxiv='1234.56789',pages=[1],equation='1')
    with pytest.raises(ValueError):
        prepare(service,arxiv='https://localhost/secret',pages=[1],equation='1')

def test_bounded_arxiv_retrieval_pins_actual_bytes_and_version(tmp_path,monkeypatch):
    service=Intake(Catalog(tmp_path/'models'))
    pdf=paper(tmp_path/'source.pdf')
    seen=[]
    def fetch(identifier):
        seen.append(identifier)
        return pdf.read_bytes()
    monkeypatch.setattr('adroit.retrieval.source_evidence.fetch_pdf',fetch)
    packet=prepare(service,arxiv='1234.56789v2',pages=[1],equation='2')
    assert seen==['1234.56789v2'] and packet['retrieval']['arxiv']=='1234.56789v2'
    assert service.catalog.asset_path(packet['sources'][0]).read_bytes()==pdf.read_bytes()
    assert packet['source']['sha256'] and packet['physical_pages']==[1]
