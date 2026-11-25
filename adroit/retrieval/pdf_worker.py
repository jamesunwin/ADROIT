"""Disposable bounded PDF parser/render worker; no network, OCR or SDK calls."""
from __future__ import annotations

import json
from pathlib import Path
import resource
import subprocess
import sys


def limits() -> None:
    """Bound worker CPU, output files and (where supported) address space."""
    resource.setrlimit(resource.RLIMIT_CPU,(35,35))
    resource.setrlimit(resource.RLIMIT_FSIZE,(25_000_000,25_000_000))
    if sys.platform.startswith('linux'):
        resource.setrlimit(resource.RLIMIT_AS,(3_000_000_000,3_000_000_000))


def extract(path: Path) -> dict:
    """Extract page text/fragments; low-text pages require visual interpretation."""
    import pypdf
    from pypdf import PdfReader, mult
    reader=PdfReader(path,strict=True)
    if reader.is_encrypted:
        raise ValueError('encrypted PDF is not accepted')
    if not 1<=len(reader.pages)<=120:
        raise ValueError('PDF page count exceeds supported cap (120)')
    pages=[]
    total=0
    for number,page in enumerate(reader.pages,1):
        width=float(page.mediabox.width)
        height=float(page.mediabox.height)
        if not (0<width<=14400 and 0<height<=14400):
            raise ValueError('PDF page dimensions exceed cap')
        fragments=[]
        def visitor(text,cm,tm,font,size):
            if text and text.strip():
                matrix=mult(tm,cm)
                fragments.append(dict(text=text,x_pt=float(matrix[4]),y_pt=float(matrix[5]),font_size_pt=float(size)))
                if len(fragments)>50_000:
                    raise ValueError('PDF fragment count exceeds cap')
        notes=[]
        try:
            content=page.get_contents()
            if content and len(content.get_data())>8_000_000:
                raise ValueError('PDF content stream exceeds cap')
            text=page.extract_text(visitor_text=visitor) or ''
            status='text_extracted' if len(text.strip())>=20 else 'needs_visual_interpretation'
        except Exception as error:
            text=''
            fragments=[]
            status='text_failed'
            notes.append('Text extraction failed: '+type(error).__name__)
        total+=len(text)
        if total>4_000_000:
            raise ValueError('PDF extracted text exceeds cap')
        pages.append(dict(page=number,width_pt=width,height_pt=height,rotation=page.rotation,
                          media_box=tuple(float(v) for v in page.mediabox),crop_box=tuple(float(v) for v in page.cropbox),
                          text=text,fragments=fragments,status=status,notes=notes))
    return dict(pages=pages,extractor='pypdf '+pypdf.__version__)


if __name__=='__main__':
    limits()
    if sys.argv[1]=='--render':
        tool,path,page,prefix=sys.argv[2:]
        from adroit.core.config import child_environment
        result=subprocess.run([tool,'-f',page,'-l',page,'-singlefile','-scale-to','1600','-png',path,prefix],timeout=35,
                              env=child_environment())
        raise SystemExit(result.returncode)
    try:
        print(json.dumps(extract(Path(sys.argv[1])),allow_nan=False))
    except Exception as error:
        # Never return arbitrary PDF contents or parser exception text to the UI.
        note=str(error) if type(error) is ValueError else type(error).__name__
        print(json.dumps({'error':note}))
