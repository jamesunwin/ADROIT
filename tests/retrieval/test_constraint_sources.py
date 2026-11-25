"""The retrieval boundary of constraint discovery (the owner's request, 2026-10-18): allowed hosts only, redirects
checked hop by hop, sizes capped, exact arXiv versions and HEPData's paper-to-data link. No network: ``requests`` is
replaced."""

from __future__ import annotations

import json

import pytest

from adroit.retrieval import constraint_sources as cs


@pytest.mark.parametrize('url', ['http://arxiv.org/pdf/2501.00001v1', 'https://evil.example/x',
                                 'https://user:pw@arxiv.org/pdf/1', 'https://arxiv.org:8443/pdf/1',
                                 'https://127.0.0.1/x', 'file:///etc/passwd', 'https://arxiv.org.evil.example/'])
def test_only_allowed_https_hosts_are_fetched(url) -> None:
    with pytest.raises(ValueError, match='refused'):
        cs.check_url(url)
    assert cs.check_url('https://www.hepdata.net/record/ins1?format=json')


class _Reply:
    def __init__(self, status=200, body=b'%PDF-1.4', location=''):
        self.status_code, self.body, self.headers = status, body, {'location': location, 'content-type': 'application/pdf'}
        self.is_redirect = status in (301, 302, 303, 307, 308)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise OSError(f'HTTP {self.status_code}')

    def iter_content(self, n):
        for i in range(0, len(self.body), n):
            yield self.body[i:i + n]


def test_a_redirect_out_of_the_allowed_hosts_is_refused(monkeypatch) -> None:
    import requests
    seen = []

    def get(url, **kwargs):
        seen.append((url, kwargs['allow_redirects']))
        return _Reply(302, location='https://evil.example/paper.pdf') if 'arxiv' in url else _Reply()
    monkeypatch.setattr(requests, 'get', get)
    with pytest.raises(ValueError, match='refused'):
        cs.network_fetch('https://arxiv.org/pdf/2501.00001v1')
    assert seen == [('https://arxiv.org/pdf/2501.00001v1', False)]


def test_an_allowed_redirect_is_followed_and_the_size_is_capped(monkeypatch) -> None:
    import requests
    replies = iter([_Reply(301, location='/pdf/2501.00001v1'), _Reply(body=b'%PDF-1.4 small')])
    monkeypatch.setattr(requests, 'get', lambda url, **k: next(replies))
    got = cs.network_fetch('https://export.arxiv.org/pdf/2501.00001v1')
    assert got.data == b'%PDF-1.4 small' and got.url == 'https://export.arxiv.org/pdf/2501.00001v1'
    monkeypatch.setattr(requests, 'get', lambda url, **k: _Reply(body=b'x' * 100))
    monkeypatch.setattr(cs, 'MAX_BYTES', 50)
    with pytest.raises(ValueError, match='byte cap'):
        cs.network_fetch('https://arxiv.org/pdf/2501.00001v1')


def _fake(pages):
    def fetch(url):
        cs.check_url(url)
        return cs.Fetched(pages[url], url)
    return fetch


def test_the_arxiv_version_is_read_and_pinned() -> None:
    atom = (b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2501.00001v3</id>'
            b'<title>A  title\n across lines</title><published>2025-01-02T00:00:00Z</published></entry></feed>')
    fetch = _fake({'https://export.arxiv.org/api/query?id_list=2501.00001&max_results=1': atom,
                   'https://arxiv.org/pdf/2501.00001v3': b'%PDF-1.7'})
    meta = cs.arxiv_metadata('2501.00001', fetch)
    assert meta == {'arxiv_id': '2501.00001', 'version': 'v3', 'title': 'A title across lines',
                    'published': '2025-01-02', 'licence': ''}
    assert cs.arxiv_pdf('2501.00001', 'v3', fetch).data == b'%PDF-1.7'
    with pytest.raises(ValueError):
        cs.arxiv_pdf('2501.00001', '', fetch)              # never an implicit latest
    with pytest.raises(ValueError):
        cs.arxiv_metadata('2501.00001v3', fetch)


def test_hepdata_must_name_the_same_paper() -> None:
    record = {'record': {'arxiv_id': 'arXiv:2501.00001', 'hepdata_doi': '10.17182/hepdata.1.v2'},
              'data_tables': [{'name': 'Figure 3', 'description': 'Observed limits', 'doi': '10.17182/hepdata.1.v2/t1'}],
              'version': 2}
    url = 'https://www.hepdata.net/record/ins123?format=json'          # the light form omits the tables
    found = cs.hepdata_record('ins123', '2501.00001', _fake({url: json.dumps(record).encode()}))
    assert found == {'record': 'ins123', 'version': 2, 'doi': '10.17182/hepdata.1.v2', 'tables': ['Figure 3'],
                     'details': {'Figure 3': {'description': 'Observed limits', 'doi': '10.17182/hepdata.1.v2/t1'}}}
    with pytest.raises(ValueError, match='not arXiv:2501.00009'):
        cs.hepdata_record('ins123', '2501.00009', _fake({url: json.dumps(record).encode()}))
    with pytest.raises(ValueError, match='INSPIRE'):
        cs.hepdata_record('123', '2501.00001', _fake({}))
    table = 'https://www.hepdata.net/download/table/ins123/Figure%203/2/yaml'
    data = b'independent_variables: []\ndependent_variables:\n- values: [{value: 0.1}]\n'
    assert cs.hepdata_table('ins123', 'Figure 3', 2, _fake({table: data})).data == data


def test_an_html_error_page_is_never_a_table() -> None:
    """HEPData answered a table download with its server's HTML error page and status 200 (2026-10-18)."""
    table = 'https://www.hepdata.net/download/table/ins123/Figure%203/2/yaml'
    for body in (b'<!doctype html><title>FileNotFoundError</title>', b'just: text\n', b': not yaml ['):
        with pytest.raises(ValueError, match='no table data'):
            cs.hepdata_table('ins123', 'Figure 3', 2, _fake({table: body}))


def test_the_record_of_exactly_this_paper_is_found() -> None:
    """HEPData's search on a bare identifier returns full-text hits on other records too (2026-10-18): only a record
    whose arXiv field is exactly this paper counts; none, or several, is a named gap."""
    url = 'https://www.hepdata.net/search/?q=2303.01214&format=json'
    hits = [{'inspire_id': '2637936', 'arxiv_id': 'arXiv:2303.01214'}, {'inspire_id': 339265, 'arxiv_id': None},
            {'inspire_id': 262690, 'arxiv_id': 'arXiv:2303.01215'}]
    assert cs.hepdata_find('2303.01214', _fake({url: json.dumps({'results': hits}).encode()})) == 'ins2637936'
    with pytest.raises(cs.NoRecord, match='no record naming arXiv:2303.01214'):
        cs.hepdata_find('2303.01214', _fake({url: json.dumps({'results': hits[1:]}).encode()}))
    twice = hits + [{'inspire_id': '9', 'arxiv_id': 'arXiv:2303.01214v2'}]
    with pytest.raises(cs.NoRecord, match='several records'):
        cs.hepdata_find('2303.01214', _fake({url: json.dumps({'results': twice}).encode()}))


def test_tables_are_chosen_from_the_records_own_words() -> None:
    """The tables of CMS's HEPData record ins2637936 (names and descriptions as HEPData gave them, 2026-10-18)."""
    details = {name: {'description': text} for name, text in [
        ('ttH and VH limits on the H$\\to$inv. branching fraction', 'Observed and expected 95% CL upper limits'),
        ('Run1+Run2 H$\\to$inv upper limits', 'Observed and expected 95% CL upper limits'),
        ('Run2 H$\\to$inv upper limits', 'Observed and expected 95% CL upper limits'),
        ('H$\\to$inv upper limits per data-taking period', 'Observed and expected 95% CL upper limits'),
        ('Upper limits on SI dark matter nucleon cross section', 'The 90% CL upper limits on the spin-independent '
         'DM-nucleon scattering cross section in Higgs-portal models'),
        ('Postfit event yields in ttH SR', 'Postfit event yields in each category'),
        ('Invariant mass distribution', 'Observed events')]}
    names = list(details)
    assert cs.select_tables('sm_higgs_invisible', details) == names[:3]
    assert cs.select_tables('si_isoscalar_curve', details) == [names[4]]
    assert cs.select_tables('unknown_adapter', details) == []


def test_the_user_agent_leads_with_the_client_and_names_no_one() -> None:
    agent = cs.user_agent()
    assert agent.startswith('python-requests/') and agent.endswith(cs.USER_AGENT) and '@' not in agent