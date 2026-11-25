"""Bounded retrieval of a constraint's primary sources: the arXiv paper at an exact version and HEPData tables whose
record names that paper (the owner's discovery workflow, 2026-10-18).

The boundary: https only, to a short list of hosts; redirects followed one hop at a time and only within that list;
sizes and times capped; no credentials, query strings from documents or private addresses. A retrieved document is
data: nothing in it chooses what is fetched next. The fetcher is injected, so tests never touch the network.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import quote, urljoin, urlsplit

HOSTS = {'arxiv.org', 'export.arxiv.org', 'www.hepdata.net', 'hepdata.net'}
MAX_BYTES = 15_000_000
MAX_HOPS = 3
TIMEOUT_S = 30
ARXIV_ID = re.compile(r'^\d{4}\.\d{4,5}$')
INSPIRE = re.compile(r'^ins\d{1,9}$')
ATOM = '{http://www.w3.org/2005/Atom}'
USER_AGENT = 'adroit (research software; retrieves cited constraint sources)'
HEPDATA_TABLES = 3


def user_agent() -> str:
    """The client token of the HTTP library actually used, then ADROIT's description. HEPData's front end refuses a
    User-Agent that does not begin with a known client token (403 "Just a moment…"; probed 2026-10-18). Nothing
    personal is sent."""
    import requests
    return f'python-requests/{requests.__version__} {USER_AGENT}'


@dataclass
class Fetched:
    """A response: the bytes, the final URL and its content type."""
    data: bytes
    url: str
    content_type: str = ''


Fetch = Callable[[str], Fetched]


def check_url(url: str) -> str:
    """The URL if it is an allowed https address without credentials or an explicit port, else ValueError."""
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in HOSTS or parts.username or parts.password or parts.port:
        raise ValueError(f'refused source address: {url!r} (https to {sorted(HOSTS)} only)')
    return url


def network_fetch(url: str) -> Fetched:
    """GET within the boundary (module docstring): no automatic redirects, each hop checked, at most ``MAX_BYTES``."""
    import requests
    for _ in range(MAX_HOPS + 1):
        check_url(url)
        with requests.get(url, timeout=TIMEOUT_S, stream=True, allow_redirects=False,
                          headers={'User-Agent': user_agent()}) as response:
            if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, response.headers.get('location', ''))
                continue
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError(f'source exceeds the {MAX_BYTES} byte cap: {url}')
                chunks.append(chunk)
            return Fetched(b''.join(chunks), url, response.headers.get('content-type', ''))
    raise ValueError(f'too many redirects from the source address: {url}')


def arxiv_metadata(arxiv_id: str, fetch: Fetch = network_fetch) -> dict:
    """The arXiv API's record of a paper: title, latest version, publication date and licence."""
    if not ARXIV_ID.fullmatch(arxiv_id):
        raise ValueError(f'an arXiv identifier without version is required: {arxiv_id!r}')
    reply = fetch(f'https://export.arxiv.org/api/query?id_list={arxiv_id}&max_results=1')
    for entry in ET.fromstring(reply.data).iter(f'{ATOM}entry'):
        url = (entry.findtext(f'{ATOM}id') or '').strip()
        found = re.search(r'/abs/(\d{4}\.\d{4,5})(v\d+)?$', url)
        title = ' '.join((entry.findtext(f'{ATOM}title') or '').split())
        if not found or found.group(1) != arxiv_id or not title or title.lower() == 'error':
            continue
        licence = next((link.get('href', '') for link in entry.iter('{http://arxiv.org/schemas/atom}license')), '')
        return {'arxiv_id': arxiv_id, 'version': found.group(2) or '', 'title': title,
                'published': (entry.findtext(f'{ATOM}published') or '')[:10], 'licence': licence}
    raise ValueError(f'arXiv has no record of {arxiv_id}')


def arxiv_pdf(arxiv_id: str, version: str, fetch: Fetch = network_fetch) -> Fetched:
    """The paper's PDF at exactly ``version``."""
    if not ARXIV_ID.fullmatch(arxiv_id) or not re.fullmatch(r'v\d+', version):
        raise ValueError('an arXiv identifier and an explicit version are required')
    reply = fetch(f'https://arxiv.org/pdf/{arxiv_id}{version}')
    if not reply.data.startswith(b'%PDF-'):
        raise ValueError(f'arXiv did not return a PDF for {arxiv_id}{version}')
    return reply


class NoRecord(ValueError):
    """HEPData holds no record (or no matching table) for a paper: a named gap, not a transport failure."""


def hepdata_find(arxiv_id: str, fetch: Fetch = network_fetch) -> str:
    """The INSPIRE identifier (ins…) of the HEPData record of exactly this arXiv paper, from HEPData's search on the
    bare identifier; full-text hits on other records are ignored. ``NoRecord`` if there is none."""
    if not ARXIV_ID.fullmatch(arxiv_id):
        raise ValueError(f'an arXiv identifier without version is required: {arxiv_id!r}')
    reply = fetch(f'https://www.hepdata.net/search/?q={arxiv_id}&format=json')
    try:
        results = json.loads(reply.data).get('results') or []
    except (ValueError, AttributeError):
        raise ValueError(f'HEPData search returned no JSON for arXiv:{arxiv_id}') from None
    found = sorted({str(r.get('inspire_id')) for r in results if isinstance(r, dict)
                    and re.sub(r'(?i)^arxiv:', '', str(r.get('arxiv_id') or '')).split('v')[0] == arxiv_id
                    and str(r.get('inspire_id') or '').isdigit()})
    if not found:
        raise NoRecord(f'HEPData has no record naming arXiv:{arxiv_id}')
    if len(found) > 1:
        raise NoRecord(f'HEPData has several records naming arXiv:{arxiv_id} ({", ".join(found)}); none was chosen')
    return 'ins' + found[0]


def hepdata_record(record: str, arxiv_id: str, fetch: Fetch = network_fetch) -> dict:
    """A HEPData record's identity and its tables (names and descriptions), refused unless the record names the same
    arXiv paper (the paper to data link; a matching experiment or title is not enough). The full record JSON is read:
    the light form omits the tables."""
    if not INSPIRE.fullmatch(record):
        raise ValueError(f'a HEPData record is named by its INSPIRE identifier (ins…): {record!r}')
    reply = fetch(f'https://www.hepdata.net/record/{record}?format=json')
    try:
        data = json.loads(reply.data)
    except ValueError:
        raise ValueError(f'HEPData returned no JSON for {record}') from None
    meta = data.get('record', data) if isinstance(data, dict) else {}
    linked = re.sub(r'(?i)^arxiv:', '', str(meta.get('arxiv_id', ''))).split('v')[0]
    if linked != arxiv_id:
        raise ValueError(f'HEPData {record} names arXiv:{linked or "none"}, not arXiv:{arxiv_id}')
    rows = [t if isinstance(t, dict) else {'name': str(t)} for t in (data.get('data_tables') or
                                                                    meta.get('data_tables') or [])]
    tables = {str(t.get('name', '')): {'description': str(t.get('description', '')), 'doi': str(t.get('doi', ''))}
              for t in rows if t.get('name')}
    return {'record': record, 'version': int(data.get('version', meta.get('version', 1)) or 1),
            'doi': str(meta.get('hepdata_doi', meta.get('doi', ''))), 'tables': list(tables), 'details': tables}


def _plain(text: str) -> str:
    return ' '.join(re.sub(r'[$\\{}]', ' ', text).lower().replace('-', ' ').split())


def select_tables(adapter: str, details: dict[str, dict]) -> list[str]:
    """At most ``HEPDATA_TABLES`` tables, in the record's order, whose name or description is the adapter's quantity:
    BR(h → invisible) limits, or spin-independent cross-section limits. Chosen by code from the record's own words;
    nothing is fetched when none matches."""
    def fits(name: str) -> bool:
        words = _plain(name + ' ' + details[name].get('description', ''))
        limit = 'limit' in words
        if adapter == 'sm_higgs_invisible':
            return limit and re.search(r'\binv(isible)?\b|\binv\.', words) is not None and 'nucleon' not in words
        if adapter == 'si_isoscalar_curve':
            return limit and ('spin independent' in words or re.search(r'\bsi\b', words) is not None) \
                and ('cross section' in words)
        return False
    return [name for name in details if fits(name)][:HEPDATA_TABLES]


def hepdata_table(record: str, table: str, version: int, fetch: Fetch = network_fetch) -> Fetched:
    """One HEPData table in its submission format (YAML), by its exact name and the record's version, refused unless
    it parses as a table (independent and dependent variables): HEPData answers some conversions with an HTML error
    page and status 200, which must never be imported as data."""
    import yaml
    if not INSPIRE.fullmatch(record) or not table or version < 1:
        raise ValueError('a HEPData record, an exact table name and a version are required')
    reply = fetch(f'https://www.hepdata.net/download/table/{record}/{quote(table, safe="")}/{version}/yaml')
    try:
        parsed = yaml.safe_load(reply.data) if not reply.data.lstrip()[:1] == b'<' else None
    except yaml.YAMLError:
        parsed = None
    if not isinstance(parsed, dict) or not isinstance(parsed.get('independent_variables'), list) \
            or not isinstance(parsed.get('dependent_variables'), list):
        raise ValueError(f'HEPData returned no table data for {record} {table!r} (version {version})')
    return reply
