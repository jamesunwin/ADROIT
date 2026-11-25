"""Independently specified PDF sources, with text and image-only pages."""
from pathlib import Path
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,NumberObject,DecodedStreamObject


def paper(path: Path,*,encrypted: bool=False,scanned: bool=False,pages: int=2) -> Path:
    writer=PdfWriter()
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),
                           NameObject('/BaseFont'):NameObject('/Helvetica')})
    for number in range(pages):
        page=writer.add_blank_page(width=600,height=400)
        if scanned:
            image=DecodedStreamObject()
            image.set_data(bytes([245,245,245])*80*40)
            image.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Image'),
                NameObject('/Width'):NumberObject(80),NameObject('/Height'):NumberObject(40),
                NameObject('/ColorSpace'):NameObject('/DeviceRGB'),NameObject('/BitsPerComponent'):NumberObject(8)})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/XObject'):DictionaryObject({NameObject('/Im0'):writer._add_object(image)})})
            body=b'q 400 0 0 200 50 100 cm /Im0 Do Q'
        else:
            text='Synthetic search. Exposure: 1000 kg day. Background: 0.3 events.' if number==0 else 'Supplement: observed 95 percent limit; m=10 GeV, sigma=1e-43 cm2.'
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
            body=f'BT /F1 12 Tf 50 340 Td ({text}) Tj ET'.encode()
        content=DecodedStreamObject()
        content.set_data(body)
        page[NameObject('/Contents')]=writer._add_object(content)
    if encrypted:
        writer.encrypt('password')
    with path.open('wb') as stream:
        writer.write(stream)
    return path
