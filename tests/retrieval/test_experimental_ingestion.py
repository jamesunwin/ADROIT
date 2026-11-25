import pytest

from tests.experimental_fixtures import paper
from adroit.library.experimental import ExperimentalCatalog
from adroit.retrieval.experimental_ingestion import read_table,finite_json,ingest,pdf_text,bounded_process


def test_pdf_pages_and_fragment_positions_are_not_concatenated(tmp_path):
    catalog=ExperimentalCatalog(tmp_path/'private')
    source=paper(tmp_path/'paper.pdf')
    asset=catalog.asset(source,'paper')
    item=ingest(catalog.asset_path(asset),asset,[],catalog.asset_bytes)
    assert item.page_count==2 and [p.page for p in item.pages]==[1,2]
    assert '1000 kg day' in item.pages[0].text and '95 percent' not in item.pages[0].text
    assert '95 percent' in item.pages[1].text
    fragment=item.pages[0].fragments[0]
    assert fragment.x_pt==50 and fragment.y_pt==340 and fragment.font_size_pt==12
    assert all(p.status=='text_extracted' for p in item.pages)
    assert item.pages[0].media_box==(0,0,600,400) and item.pages[0].crop_box==(0,0,600,400)


def test_scanned_page_render_is_bounded_and_remains_uninterpreted(tmp_path):
    from PIL import Image
    from io import BytesIO
    catalog=ExperimentalCatalog(tmp_path/'private')
    asset=catalog.asset(paper(tmp_path/'scan.pdf',scanned=True,pages=1),'paper')
    item=ingest(catalog.asset_path(asset),asset,[1],catalog.asset_bytes)
    page=item.pages[0]
    assert page.status=='needs_visual_interpretation' and not page.text and page.preview
    with Image.open(BytesIO(catalog.asset_path(page.preview).read_bytes())) as im:
        assert max(im.size)<=1600
    assert 'No OCR' in item.notes[-1]


def test_pdf_failures_limits_and_visual_backend_unavailability(tmp_path,monkeypatch):
    with pytest.raises(ValueError):
        pdf_text(paper(tmp_path/'locked.pdf',encrypted=True))
    with pytest.raises(ValueError):
        pdf_text(paper(tmp_path/'long.pdf',pages=121))
    bad=tmp_path/'bad.pdf'
    bad.write_bytes(b'%PDF- invalid')
    with pytest.raises(ValueError):
        pdf_text(bad)
    catalog=ExperimentalCatalog(tmp_path/'private')
    asset=catalog.asset(paper(tmp_path/'good.pdf'),'paper')
    with pytest.raises(ValueError,match='existing PDF pages'):
        ingest(catalog.asset_path(asset),asset,[3],catalog.asset_bytes)
    monkeypatch.setattr('adroit.retrieval.experimental_ingestion.shutil.which',lambda _:None)
    item=ingest(catalog.asset_path(asset),asset,[1],catalog.asset_bytes)
    assert item.pages[0].text and not item.pages[0].preview and 'Poppler' in item.pages[0].notes[0]


def test_table_rows_zero_sign_precision_and_malformed_rows():
    table=read_table('m_GeV,sigma_cm2\n10,0\n12,-1.234567890123456e-43\n',',')
    assert table.columns==['m_GeV','sigma_cm2']
    assert table.rows==[['10','0'],['12','-1.234567890123456e-43']] and table.source_lines==[2,3]
    for text in ('a,a\n1,2','a,b\n1','a,b\n1,2,3','a,b\n1,nan','a,b\n1,1e999','a,b\n'):
        with pytest.raises(ValueError):
            read_table(text,',')
    assert read_table('mass\tlimit\n10\t1e-40\n','\t').rows==[['10','1e-40']]


def test_structured_values_do_not_accept_nonfinite_or_cyclic_inputs():
    finite_json({'a':[0,-1,1e-40,None]})
    with pytest.raises(ValueError):
        finite_json({'a':float('nan')})
    cyclic=[]
    cyclic.append(cyclic)
    with pytest.raises(ValueError):
        finite_json(cyclic)
    with pytest.raises(ValueError):
        finite_json({1:'bad key'})


def test_worker_timeout_terminates_processing():
    import sys
    with pytest.raises(ValueError,match='time cap'):
        bounded_process([sys.executable,'-c','import time; time.sleep(4)'],timeout=1)
