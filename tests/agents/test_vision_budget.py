"""Known inline images reserve a conservative bound; unbounded inputs never dispatch."""
import base64
from io import BytesIO
from PIL import Image
import pytest

from adroit.agents.llm import _bounded_image_material

def block():
    data=BytesIO()
    Image.new('RGB',(400,200),'white').save(data,format='PNG')
    return {'type':'image','source':{'type':'base64','media_type':'image/png','data':base64.b64encode(data.getvalue()).decode()}}

def test_verified_inline_image_has_bound_without_base64_text_token_inflation():
    b=block()
    request={'messages':[{'role':'user','content':[{'type':'text','text':'interpret'},b]}]}
    clean,tokens=_bounded_image_material(request,'anthropic')
    assert tokens==8192 and clean['messages'][0]['content'][1]['source']['data']=='bounded image'
    assert request['messages'][0]['content'][1]['source']['data']==b['source']['data']

def test_multiple_images_accumulate_and_other_image_sources_still_fail():
    request={'messages':[{'role':'user','content':[block(),block()]}]}
    assert _bounded_image_material(request,'anthropic')[1]==16384
    with pytest.raises(ValueError):
        _bounded_image_material(request,'openai')
    with pytest.raises(ValueError):
        _bounded_image_material({'type':'image','source':{'type':'url','url':'https://invalid'}},'anthropic')

def test_invalid_mime_and_image_bytes_are_refused():
    b=block()
    b['source']['media_type']='image/jpeg'
    with pytest.raises(ValueError,match='media type'):
        _bounded_image_material(b,'anthropic')
    b['source']['data']=base64.b64encode(b'not an image').decode()
    with pytest.raises(Exception):
        _bounded_image_material(b,'anthropic')
