"""Bounded deterministic file ingestion, retaining pages and machine-table rows."""
from __future__ import annotations

import csv
from io import StringIO
import json
import math
from pathlib import Path
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Literal

from pydantic import Field, JsonValue, model_validator

from adroit.core.config import child_environment
from adroit.core.experimental_input import ExperimentalAsset
from adroit.core.state import StrictModel


class TextFragment(StrictModel):
    """A piece of a PDF page's text, with its position (from the text matrix) and font size, in points."""
    text: str
    x_pt: float
    y_pt: float
    font_size_pt: float


class PDFPage(StrictModel):
    """One physical PDF page: its size, rotation and boxes in points, its text and fragments, whether the text was
    extracted or needs visual interpretation, and an optional preview image."""
    page: int = Field(ge=1)
    width_pt: float = Field(gt=0, le=14400)
    height_pt: float = Field(gt=0, le=14400)
    rotation: int = 0
    media_box: tuple[float,float,float,float] | None = None
    crop_box: tuple[float,float,float,float] | None = None
    text: str = ''
    fragments: list[TextFragment] = Field(default_factory=list)
    status: Literal['text_extracted', 'needs_visual_interpretation', 'text_failed']
    preview: ExperimentalAsset | None = None
    notes: list[str] = Field(default_factory=list)


class MachineTable(StrictModel):
    """A table's literal cells, with its column headers and source lines; no interpretation."""
    columns: list[str]
    rows: list[list[str]]
    source_lines: list[int]
    note: str = 'Literal cells; headers/units/observables require interpretation; no physics inference.'


class Ingestion(StrictModel):
    """What deterministic ingestion read from one source file: its PDF pages, table, structured data or text, by
    kind."""
    source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    kind: Literal['pdf', 'table', 'structured', 'text', 'image']
    extractor: str
    pages: list[PDFPage] = Field(default_factory=list)
    page_count: int = 0
    table: MachineTable | None = None
    structured: JsonValue = None
    text: str = ''
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def page_identity(self) -> Ingestion:
        """Require a PDF's page inventory to be complete and numbered in sequence, and the structured data to be
        finite."""
        if self.kind=='pdf' and (not self.pages or self.page_count!=len(self.pages) or
                                [p.page for p in self.pages]!=list(range(1,self.page_count+1))):
            raise ValueError('PDF page inventory must be complete and sequential')
        finite_json(self.structured)
        return self


def finite_json(value: JsonValue) -> None:
    """Reject non-finite scientific values, including nested numerical inputs."""
    stack=[(value,0)]
    seen=set()
    count=0
    while stack:
        item,depth=stack.pop()
        count+=1
        if depth>64 or count>200_000:
            raise ValueError('structured input nesting/size exceeds cap')
        if isinstance(item,float) and not math.isfinite(item):
            raise ValueError('nonfinite input value')
        if isinstance(item,(dict,list)):
            if id(item) in seen:
                raise ValueError('repeated/cyclic structured containers are unsupported')
            seen.add(id(item))
            if isinstance(item,dict) and any(not isinstance(k,str) for k in item):
                raise ValueError('structured keys must be strings')
            children=item.values() if isinstance(item,dict) else item
            stack.extend((c,depth+1) for c in children)


def read_table(text: str,delimiter: str) -> MachineTable:
    """Read exact cells without silently dropping malformed rows or duplicates."""
    reader=csv.reader(StringIO(text),delimiter=delimiter,strict=True)
    try:
        columns=next(reader)
    except StopIteration:
        raise ValueError('table has no header') from None
    if not columns or len(columns)>256 or any(not h.strip() for h in columns) or len(set(columns))!=len(columns):
        raise ValueError('table requires nonempty distinct headers')
    rows=[]
    lines=[]
    for row in reader:
        if len(row)!=len(columns):
            raise ValueError(f'table row ending at line {reader.line_num} has wrong column count')
        for cell in row:
            try:
                n=float(cell)
            except ValueError:
                continue
            if not math.isfinite(n):
                raise ValueError('nonfinite table value')
        rows.append(row)
        lines.append(reader.line_num)
        if len(rows)>100_000 or len(columns)>256:
            raise ValueError('table dimensions exceed ingestion cap')
    if not rows:
        raise ValueError('table has no data rows')
    return MachineTable(columns=columns,rows=rows,source_lines=lines)


def bounded_process(args: list[str],timeout: int=60) -> bytes:
    """Run a bounded parser/render worker; terminate its descendants on timeout."""
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        proc=subprocess.Popen(args,stdout=stdout,stderr=stderr,start_new_session=True,
                              env=child_environment({'OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'}))
        try:
            code=proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGKILL)
            proc.wait()
            raise ValueError('input processing exceeded time cap') from None
        if code:
            raise ValueError('input could not be processed within parser/resource limits')
        stdout.seek(0,2)
        if stdout.tell()>20_000_000:
            raise ValueError('extracted content exceeds output cap')
        stdout.seek(0)
        return stdout.read()


def pdf_text(path: Path) -> dict:
    """Page-aware extraction in a disposable resource-bounded worker."""
    raw=bounded_process([sys.executable,'-m','adroit.retrieval.pdf_worker',str(path)])
    result=json.loads(raw)
    if 'error' in result:
        raise ValueError('PDF ingestion refused: '+result['error'])
    return result


def render_page(path: Path,page: int) -> bytes:
    """Render one bounded page with Poppler; never execute embedded PDF actions."""
    tool=shutil.which('pdftoppm')
    if not tool:
        raise ValueError('PDF preview needs Poppler pdftoppm; text remains available')
    with tempfile.TemporaryDirectory(prefix='adroit-pdf-') as folder:
        prefix=Path(folder)/'page'
        bounded_process([sys.executable,'-m','adroit.retrieval.pdf_worker','--render',tool,
                         str(path),str(page),str(prefix)],timeout=40)
        data=prefix.with_suffix('.png').read_bytes()
        if len(data)>8_000_000:
            raise ValueError('rendered page exceeds byte cap')
        return data


def ingest(path: Path,asset: ExperimentalAsset,preview_pages: list[int] | None=None,
           store_preview=None) -> Ingestion:
    """Ingest a selected immutable asset; visual interpretation follows later. The bytes read must be the asset's
    (its digest): the record binds what was consumed (NA15-08)."""
    import hashlib
    suffix=asset.suffix
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=asset.sha256:
        raise ValueError('the source read is not the selected asset (its bytes changed)')
    if suffix=='.pdf':
        body=pdf_text(path)
        pages=[PDFPage.model_validate(p) for p in body['pages']]
        selected=preview_pages if preview_pages is not None else [1]
        if len(set(selected))>12 or any(p<1 or p>len(pages) for p in selected):
            raise ValueError('choose at most twelve existing PDF pages for previews')
        for number in sorted(set(selected)):
            page=pages[number-1]
            try:
                image=render_page(path,number)
                if store_preview:
                    page.preview=store_preview(f'page-{number}.png',image,'page_preview')
            except ValueError as error:
                page.notes.append(str(error))
        return Ingestion(source_sha256=asset.sha256,kind='pdf',extractor=body['extractor'],
            pages=pages,page_count=len(pages),notes=[
                'Physical pages are one-based. Printed page/figure labels are not inferred.',
                'Fragment coordinates are PDF points; complex transforms/rotation may need visual checking.',
                'No OCR or semantic extraction performed; scanned/layout-sensitive pages await reviewed vision in M36.5c.'])
    if suffix in ('.png','.jpg','.jpeg','.webp'):
        return Ingestion(source_sha256=asset.sha256,kind='image',extractor='verified original image',
                         notes=['Image retained for subsequent reviewed visual interpretation.'])
    text=data.decode('utf-8-sig')
    if suffix in ('.csv','.tsv'):
        return Ingestion(source_sha256=asset.sha256,kind='table',extractor='Python csv strict',
                         table=read_table(text,'\t' if suffix=='.tsv' else ','))
    if suffix in ('.json','.yaml','.yml'):
        import yaml
        structured=json.loads(text) if suffix=='.json' else yaml.safe_load(text)
        finite_json(structured)
        # Ensure the data really are JSON-compatible (no YAML timestamps/objects).
        try:
            structured=json.loads(json.dumps(structured,allow_nan=False))
        except (TypeError,ValueError):
            raise ValueError('structured input must contain JSON-compatible values') from None
        return Ingestion(source_sha256=asset.sha256,kind='structured',extractor='safe structured input',structured=structured)
    return Ingestion(source_sha256=asset.sha256,kind='text',extractor='UTF-8',text=text)
