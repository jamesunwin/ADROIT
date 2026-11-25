"""The owner's rule for figure anchors (2026-10-19): same-paper printed anchors for a curve digitised from a figure,
the same result, provenance per anchor, printed precision, and the manual figure-verification route."""
import io
from pathlib import Path
import json

import pytest

from adroit.constraints.experimental_review import (CHECKLIST, FIGURE_CHECKLIST, approve, bind, packet, renew_figure,
                                                    validate, verify_figure)
from adroit.core.experimental_input import ExperimentalClaim, ExperimentalResult, SourceLocator
from adroit.core.private_limits import LimitContract, LimitValidation
from adroit.library.experimental import ExperimentalCatalog
from adroit.orchestrator.experimental_extraction import printed_numbers, printed_precision

CURVE = [(10, 1e-43), (20, 2e-43), (40, 4e-43)]
QUOTES = ['At a WIMP mass of 12 GeV the 90% C.L. upper limit is 1.20e-43 cm2.',
          'At 15 GeV the upper limit on the WIMP-nucleon cross section is 1.50e-43 cm2.',
          'At 30 GeV the limit reaches 3.00e-43 cm2.']
ANCHORS = [[12, 1.2e-43], [15, 1.5e-43], [30, 3e-43]]
RESULT = {'selection': 'observed', 'confidence_level': .9, 'dataset_id': 'synthetic:run', 'benchmark':
          'elastic_contact_O1_cp_equals_cn'}
FRAME = (.125, .11, .9, .88)       # matplotlib's default axes, as fractions of the figure


def _figure_png() -> bytes:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(6, 4))
    ax = fig.add_axes((FRAME[0], 1 - FRAME[3], FRAME[2] - FRAME[0], FRAME[3] - FRAME[1]))
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlim(8, 50)
    ax.set_ylim(.8e-43, 5e-43)
    ax.plot(*zip(*CURVE))
    stream = io.BytesIO()
    fig.savefig(stream, format='png')
    plt.close(fig)
    return stream.getvalue()


def _paper(quotes: list[str]) -> bytes:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    stream = io.BytesIO()
    with matplotlib.rc_context({'pdf.fonttype': 42}), PdfPages(stream) as pdf:
        fig = plt.figure(figsize=(6, 4))
        for i, quote in enumerate(quotes):
            fig.text(.02, .8 - .15 * i, quote, fontsize=7)
        pdf.savefig(fig)
        plt.close(fig)
        fig = plt.figure(figsize=(6, 4))
        fig.text(.4, .02, 'FIG. 3. The upper limit.')
        pdf.savefig(fig)
        plt.close(fig)
    return stream.getvalue()


def lineage(anchors, derivation='printed_text', document='paper.pdf', columns=('mass', 'limit')):
    """Each anchor's declared lineage, typed (the focused audit's FA-01; the recheck's FR-01): printed text on page 1
    of the paper, or a published table's row and columns."""
    if derivation == 'printed_text':
        return [{'derivation': derivation, 'document': document, 'page': 1} for _ in anchors]
    return [{'derivation': derivation, 'document': document, 'row': i + 1, 'mass_column': columns[0],
             'limit_column': columns[1]} for i in range(len(anchors))]


def hepdata(points, limit='limit') -> str:
    """A table in HEPData's format (mass, and a limit column named ``limit``)."""
    return json.dumps({'independent_variables': [{'header': {'name': 'mass', 'units': 'GeV'},
                                                  'values': [{'value': x} for x, _ in points]}],
                       'dependent_variables': [{'header': {'name': limit, 'units': 'cm2'},
                                                'values': [{'value': y} for _, y in points]}]})


def figure_curve(tmp_path, quotes=QUOTES, anchors=ANCHORS, *, result=RESULT, located=None, extra=(), lineages=None,
                 retrieved=(), **changes):
    """A synthetic paper whose page 2 holds the figure (the curve, digitised) and page 1 the printed anchors;
    ``located`` maps an anchor's index to the quotation that locates it (default: its own)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    catalog = ExperimentalCatalog(tmp_path / 'private')
    path = tmp_path / 'paper.pdf'
    path.write_bytes(_paper(quotes))
    files = [path]
    for name, content in extra:                       # text, or a file's bytes (a PDF)
        (tmp_path / name).write_bytes(content) if isinstance(content, bytes) else (tmp_path / name).write_text(content)
        files.append(tmp_path / name)
    import hashlib
    origin = [{'url': f'https://www.hepdata.net/download/table/ins0000000/{name}/1/json', 'name': name,
               'sha256': hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()} for name in retrieved]
    r = catalog.import_files(files, 'Synthetic figure paper', provenance={'retrieved': origin} if origin else None)
    paper = r.sources[0].sha256
    data = dict(adapter='si_isoscalar_curve', benchmark='elastic_contact_O1_cp_equals_cn', quantity='sigma_nucleon_cm2',
                units='cm2', points=CURVE, mass_range=(10, 40), confidence_level=.9, construction='published',
                selection='observed', dataset_id='synthetic:run', overlap='disjoint_from_selected',
                origin='figure_digitised', x_relative_error=.01, y_relative_error=.05,
                halo={'rho_gev_cm3': .3, 'v0_km_s': 220., 'v_earth_km_s': 232., 'v_esc_km_s': 544.},
                assumptions=['as published'], source_panel='Fig. 3',
                figure_axes={'asset_sha256': paper, 'page': 2, 'frame': list(FRAME), 'x_range': [8, 50],
                             'y_range': [.8e-43, 5e-43]})
    data.update(changes)
    contract = LimitContract(**data)
    curve = ExperimentalClaim(key='limit_contract', category='limit', value=contract.model_dump(mode='json'),
                              status='digitised', sources=[SourceLocator(asset_sha256=paper, page=2, method='visual',
                                                                         figure='3', region=(50, 40, 400, 260))])
    located = located or {i: quotes[i] for i in range(len(anchors))}
    sources = [SourceLocator(asset_sha256=paper, page=1, method='text', excerpt=q) for q in dict.fromkeys(located.values())]
    for name, content in extra:
        sha = next(a.sha256 for a in r.sources if a.name == name)
        if isinstance(content, str):
            sources.append(SourceLocator(asset_sha256=sha, method='structured', excerpt=content))
    value = {'points': anchors, 'lineage': lineages or lineage(anchors)} | ({'result': result} if result is not None else {})
    reference = ExperimentalClaim(key='validation_reference', category='limit', value=value, status='sourced',
                                  sources=sources)
    dossier = r.dossier.model_copy(update={'results': [ExperimentalResult(result_id='limit', kind='limit',
                                                                          claims=[curve, reference])]})
    return catalog, catalog.save(dossier, r.sources, r.ingestions, r.reference)


def _hash(catalog, r) -> str:
    return packet(r.reference, 'limit', catalog=catalog)['scientific_sha256']


def test_printed_values_read_a_dropped_times_sign_and_their_rounding():
    assert any(abs(v - 1.1e-46) < 1e-58 for v in printed_numbers('a limit of 1.1 10−46 cm2'))
    assert printed_precision('1.1 × 10−46 cm2', 1.1e-46) == pytest.approx(.05 / 1.1)
    assert printed_precision('at 50 GeV', 50) == pytest.approx(.01)
    assert printed_precision('below 10−46 cm2', 1e-46) == .5
    assert printed_precision('at 50 GeV', 51) is None


def test_same_paper_printed_text_validates_a_figure_digitised_curve(tmp_path):
    catalog, r = figure_curve(tmp_path)
    receipt = validate(r.reference, 'limit', .2, _hash(catalog, r), catalog)
    assert receipt.passed and receipt.basis == 'same_paper_text'
    assert receipt.scope.startswith('Figure transcription checked against published text')
    first = receipt.anchors[0]
    assert first.page == 1 and first.method == 'text' and first.excerpt == QUOTES[0]
    # y_round + y_err + the curve's variation over x_round + x_err (a log–log slope of 1 here), from the printed
    # digits and the declared errors
    assert first.allowance == pytest.approx(.005 / 1.2 + .05 + 1 * (.5 / 12 + .01))
    assert first.lineage['derivation'] == 'printed_text'
    # the focused audit's FA-04: the tolerance is fixed when the scope is first compared; another is a new scope
    with pytest.raises(ValueError, match='fixed at 0.2'):
        validate(r.reference, 'limit', .1, _hash(catalog, r), catalog)
    catalog, r = figure_curve(tmp_path / 'capped')
    assert validate(r.reference, 'limit', .1, _hash(catalog, r), catalog).anchors[0].allowance == .1   # capped


def test_same_paper_anchors_do_not_validate_a_curve_read_from_a_table(tmp_path):
    catalog, r = figure_curve(tmp_path, origin='machine_table', figure_axes={})
    with pytest.raises(ValueError, match='no evidence of its own'):
        validate(r.reference, 'limit', .1, _hash(catalog, r), catalog)


def test_one_separate_source_does_not_qualify_the_other_anchors(tmp_path):
    # the old rule passed once any reference source was a separate file; each anchor now needs its own evidence
    lineages = lineage(ANCHORS[:1], 'published_table', 'other.json') + lineage(ANCHORS[1:])
    catalog, r = figure_curve(tmp_path, origin='machine_table', figure_axes={},
                              extra=[('other.json', hepdata(ANCHORS[:1]))], lineages=lineages, retrieved=['other.json'])
    with pytest.raises(ValueError, match=r'anchor \(15, 1.5e-43\) has no evidence of its own'):
        validate(r.reference, 'limit', .1, _hash(catalog, r), catalog)


def test_an_anchor_read_from_the_figure_or_copied_from_the_curve_is_refused(tmp_path):
    """The focused audit's FA-01: copying is refused by provenance, not by equality. A printed value that equals a
    digitised node is genuine evidence; an anchor whose lineage is a digitisation is not, whatever it equals."""
    printed = ['At 10 GeV the observed upper limit is 1.00e-43 cm2.', *QUOTES[1:]]
    catalog, r = figure_curve(tmp_path / 'node', printed, [[10, 1e-43], *ANCHORS[1:]])
    assert validate(r.reference, 'limit', .1, _hash(catalog, r), catalog).passed
    digitised = lineage(ANCHORS)
    digitised[0]['derivation'] = 'digitised_from_the_figure'
    catalog, r = figure_curve(tmp_path / 'copied', lineages=digitised)
    with pytest.raises(ValueError, match='not evidence'):
        validate(r.reference, 'limit', .1, _hash(catalog, r), catalog)
    catalog, r = figure_curve(tmp_path / 'visual')
    dossier = r.dossier.model_copy(deep=True)
    dossier.results[0].claims[1].sources[0] = SourceLocator(asset_sha256=r.sources[0].sha256, page=2, method='visual',
                                                             region=(50, 40, 400, 260))
    r = catalog.save(dossier, r.sources, r.ingestions, r.reference)
    with pytest.raises(ValueError, match='cannot be read from a figure'):
        validate(r.reference, 'limit', .1, _hash(catalog, r), catalog)


@pytest.mark.parametrize('quote,result,match', [
    (QUOTES[0], None, 'declare its result'),
    (QUOTES[0], RESULT | {'selection': 'expected'}, 'another result than the curve: selection'),
    ('At a WIMP mass of 12 GeV the 95% C.L. upper limit is 1.20e-43 cm2.', RESULT, '95% confidence level'),
    ('The expected sensitivity at 12 GeV is 1.20e-43 cm2.', RESULT, 'expected sensitivity'),
    ('The combined limit at 12 GeV is 1.20e-43 cm2.', RESULT, 'combined result'),
    ('The spin-dependent limit at 12 GeV is 1.20e-43 cm2.', RESULT, 'another interaction'),
])
def test_anchors_must_state_the_curves_own_result(tmp_path, quote, result, match):
    catalog, r = figure_curve(tmp_path, [quote, *QUOTES[1:]], result=result)
    with pytest.raises(ValueError, match=match):
        validate(r.reference, 'limit', .1, _hash(catalog, r), catalog)


def test_printed_precision_sets_the_allowance_and_a_tolerance_never_widens_it(tmp_path):
    off = ['At 15 GeV the upper limit is 1.30e-43 cm2.', *QUOTES[:1], *QUOTES[2:]]
    catalog, r = figure_curve(tmp_path / 'off', off, [[15, 1.3e-43], ANCHORS[0], ANCHORS[2]])
    receipt = validate(r.reference, 'limit', .3, _hash(catalog, r), catalog)
    assert not receipt.passed and receipt.relative_errors[0] > receipt.anchors[0].allowance
    coarse = ['At 12 GeV the limit is about 10−43 cm2.', *QUOTES[1:]]
    catalog, r = figure_curve(tmp_path / 'coarse', coarse, [[12, 1e-43], *ANCHORS[1:]])
    with pytest.raises(ValueError, match='printed too coarsely'):
        validate(r.reference, 'limit', .3, _hash(catalog, r), catalog)


def _verify(catalog, r, **changes):
    """The manual verification of the review packet just drawn (the recheck's FR-04: it binds to what was shown)."""
    from adroit.constraints.experimental_review import plot_packet
    folder = Path(catalog.root) / 'packet'
    if 'packet' not in changes:
        plot_packet(r.reference, 'limit', folder, catalog)
    arguments = dict(confirmed=True, checks=FIGURE_CHECKLIST, reviewed_range=(10, 40), packet=folder,
                     catalog=catalog) | changes
    return verify_figure(r.reference, 'limit', .1, _hash(catalog, r), 'Synthetic verifier', **arguments)


def test_one_printed_anchor_needs_the_manual_figure_route(tmp_path, monkeypatch):
    import adroit.retrieval.experimental_ingestion as ingestion
    monkeypatch.setattr(ingestion, 'render_page', lambda path, page: _figure_png())
    catalog, r = figure_curve(tmp_path, QUOTES[1:2], ANCHORS[1:2])
    with pytest.raises(ValueError, match='verify-figure'):
        validate(r.reference, 'limit', .1, _hash(catalog, r), catalog)
    with pytest.raises(ValueError, match='every check'):
        _verify(catalog, r, checks=FIGURE_CHECKLIST[:-1])
    with pytest.raises(ValueError, match='full declared mass range'):
        _verify(catalog, r, reviewed_range=(10, 30))
    receipt = _verify(catalog, r)
    assert receipt.passed and receipt.basis == 'manual_figure' and receipt.manual.researcher == 'Synthetic verifier'
    assert receipt.scope.startswith('Manually verified against the figure with limited numerical anchors (1 printed)')
    review = approve(r.reference, 'limit', _hash(catalog, r), 'Synthetic reviewer', confirmed=True, checks=CHECKLIST,
                     catalog=catalog)
    assert bind(r.reference, 'limit', review.review_id, receipt.validation_id, catalog).validation == receipt
    renewed = renew_figure(receipt.validation_id, catalog)
    assert renewed.manual.renewed_from == receipt.validation_id and renewed.manual.researcher == 'Synthetic verifier'


def test_the_manual_route_needs_a_calibrated_overlay_and_is_not_for_three_anchors(tmp_path, monkeypatch):
    import adroit.retrieval.experimental_ingestion as ingestion
    monkeypatch.setattr(ingestion, 'render_page', lambda path, page: _figure_png())
    catalog, r = figure_curve(tmp_path / 'three')
    with pytest.raises(ValueError, match='use validate-limit'):
        _verify(catalog, r)
    catalog, r = figure_curve(tmp_path / 'uncalibrated', QUOTES[1:2], ANCHORS[1:2], figure_axes={})
    with pytest.raises(ValueError, match='calibrated source overlay'):
        _verify(catalog, r)
    catalog, r = figure_curve(tmp_path / 'table', QUOTES[1:2], ANCHORS[1:2], origin='machine_table')
    with pytest.raises(ValueError, match='no evidence of its own'):
        _verify(catalog, r)


def test_receipts_saved_before_figure_anchors_keep_their_identity():
    from adroit.core.evidence import content_hash
    raw = dict(revision='experimental:x@y', result_id='limit', scientific_sha256='b' * 64, adapter_version=1,
               code_sha256='c' * 64, created_at='2026-10-01T00:00:00Z', reference=[[10.0, 1e-43]], reproduced=[1e-43],
               relative_errors=[0.0], tolerance=.02, passed=True,
               scope='Published-value transcription/adapter interpolation; no reconstructed experimental likelihood.')
    loaded = LimitValidation.model_validate(raw | {'validation_id': content_hash(raw)})
    assert content_hash(loaded.model_dump(mode='json', exclude={'validation_id'})) == content_hash(raw)


def test_the_command_line_verifies_a_figure_only_with_every_attestation(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    import adroit.retrieval.experimental_ingestion as ingestion
    from adroit.core.config import get_settings
    from adroit.orchestrator.cli import app
    monkeypatch.setattr(ingestion, 'render_page', lambda path, page: _figure_png())
    catalog, r = figure_curve(tmp_path, QUOTES[1:2], ANCHORS[1:2])
    monkeypatch.setattr(get_settings(), 'experimental_library_dir', catalog.root)
    from adroit.constraints.experimental_review import plot_packet
    plot_packet(r.reference, 'limit', tmp_path / 'packet', catalog)                 # the packet the researcher saw
    arguments = ['experiments', 'verify-figure', r.reference, '--result', 'limit', '--tolerance', '0.1',
                 '--expected-hash', _hash(catalog, r), '--by', 'Synthetic verifier', '--from', '10', '--to', '40',
                 '--packet', str(tmp_path / 'packet'), *[a for name in FIGURE_CHECKLIST for a in ('--checked', name)]]
    refused = CliRunner().invoke(app, arguments)
    import re
    assert refused.exit_code != 0 and 'explicit attestation' in re.sub(r'[\s│╭╮╰╯─]+', ' ', refused.output)
    done = CliRunner().invoke(app, [*arguments, '--confirmed'])
    assert done.exit_code == 0, done.output
    assert json.loads(done.output)['basis'] == 'manual_figure'


@pytest.mark.parametrize('dataset,constituents,match', [('synthetic:WS2013+WS2014-16', ['WS2013', 'WS2014-16'],
                                                         'verify-figure'),
                                                        ('synthetic:WS2014-16', [], 'combined result'),
                                                        ('synthetic:WS2013+WS2014-16', [], 'combined result')])
def test_the_live_tests_sentence_checks_a_combined_curve_and_refuses_a_constituent(tmp_path, dataset, constituents,
                                                                                   match):
    # LUX 2016's wording (the live test, 2026-10-19), with this fixture's numbers: "combined" against a curve that
    # names its constituent datasets (the focused audit's FA-02: an identifier's punctuation is not evidence of a
    # combination), and "an expected 3.2 signal events", which is no expected sensitivity
    sentence = ('This combined exclusion limit reaches a minimum of 1.5× 10−43 cm2 at 15 GeVc−2, corresponding to '
                'an expected 3.2 signal events.')
    catalog, r = figure_curve(tmp_path, [sentence], ANCHORS[1:2], result=RESULT | {'dataset_id': dataset},
                              dataset_id=dataset, datasets=constituents)
    with pytest.raises(ValueError, match=match):
        validate(r.reference, 'limit', .1, _hash(catalog, r), catalog)


def test_the_extraction_asks_for_every_printed_anchor_even_fewer_than_three():
    from adroit.orchestrator.constraint_discovery import Candidate, extraction_instruction
    text = extraction_instruction(Candidate(candidate_id='c', name='LUX', reference='1608.07648', title='t',
                                            category='missing_supported', adapter='si_isoscalar_curve',
                                            result_id='r', constraint_class='direct_detection',
                                            applicability='applies'), [6])
    assert 'every anchor the sources print' in text and 'give fewer if that is all there is' in text


def test_the_allowance_follows_the_declared_interpolation_on_linear_axes(tmp_path):
    """The focused audit's FA-05: a linear–linear curve (10, 1e-43)–(20, 1e-41) and a printed anchor at 19 GeV 9.9%
    away. Its allowance is the curve's own variation over the mass-reading interval (≈ 7.6%) plus the printed and
    declared y errors (1.5%), ≈ 9.1%: refused (the log–log secant had given ≈ 25.6% and passed it)."""
    from adroit.constraints import experimental_review as er
    quotes = ['At 19 GeV the observed limit is 1.00e-41 cm2.', 'At 15 GeV the observed limit is 5.05e-42 cm2.',
              'At 12 GeV the observed limit is 2.08e-42 cm2.']
    catalog, r = figure_curve(tmp_path, quotes, [[19, 1e-41], [15, 5.05e-42], [12, 2.08e-42]])
    d = r.dossier.model_copy(deep=True)
    d.results[0].claims[0].value.update(points=[[10, 1e-43], [20, 100e-43]], mass_range=[10, 20], x_scale='linear',
                                        y_scale='linear', x_relative_error=.01, y_relative_error=.01)
    r = catalog.save(d, r.sources, r.ingestions, r.reference)
    v = er.validate(r.reference, 'limit', .3, _hash(catalog, r), catalog)
    assert v.anchors[0].allowance == pytest.approx(0.0908, abs=5e-4) and v.relative_errors[0] == pytest.approx(0.099)
    assert not v.passed
    contract, _ = er.limit_contract(r.reference, 'limit', catalog)
    assert er._variation(contract, 15, 0.1) == pytest.approx(abs(er.interpolate(contract, 16.5)
                                                                   / er.interpolate(contract, 15) - 1))
    assert er._variation(contract, 19.5, 0.1) == pytest.approx(abs(er.interpolate(contract, 17.55)
                                                                     / er.interpolate(contract, 19.5) - 1))  # the edge


# --- the focused audit of 2026-10-19 (FA-01, FA-02, FA-06) ------------------------------------------------------------

def _plot_paper(*_):
    """A paper whose second page is a plot whose ticks print the anchors' numbers, and no sentence states them."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    stream = io.BytesIO()
    with matplotlib.rc_context({'pdf.fonttype': 42}), PdfPages(stream) as pdf:
        fig = plt.figure()
        fig.text(.2, .5, 'Synthetic figure-only paper')
        pdf.savefig(fig)
        plt.close(fig)
        fig, ax = plt.subplots()
        ax.plot([10, 20, 40], [1e-43, 2e-43, 4e-43])
        ax.set_xticks([12, 15, 30], ['12', '15', '30'])
        ax.set_yticks([1.2e-43, 1.5e-43, 3e-43], ['1.20e-43', '1.50e-43', '3.00e-43'])
        ax.set_xlabel('mass (GeV)')
        ax.set_ylabel('cross section (cm2)')
        pdf.savefig(fig)
        plt.close(fig)
    return stream.getvalue()


def test_a_plots_ticks_are_not_printed_assertions(tmp_path, monkeypatch):
    """FA-01: the plot's own vector text prints the numbers but pairs no mass (with its unit) with a limit."""
    monkeypatch.setitem(figure_curve.__globals__, '_paper', _plot_paper)
    catalog, r = figure_curve(tmp_path, ['Synthetic figure-only paper'] * 3)
    excerpt = catalog.ingestion(r.ingestions[0]).pages[1].text
    d = r.dossier.model_copy(deep=True)
    d.results[0].claims[1].sources = [SourceLocator(asset_sha256=r.sources[0].sha256, page=2, method='text',
                                                    excerpt=excerpt)]
    r = catalog.save(d, r.sources, r.ingestions, r.reference)
    with pytest.raises(ValueError, match='no evidence of its own'):
        validate(r.reference, 'limit', .2, _hash(catalog, r), catalog)


def test_a_re_export_of_the_digitisation_is_not_a_separate_source(tmp_path):
    """FA-01: a file that says it was digitised from the same curve qualifies nothing, whatever its hash."""
    copied = json.dumps({'description': 'exported by digitising the very same curve', 'points': ANCHORS})
    catalog, r = figure_curve(tmp_path, extra=[('reexport.json', copied)], result=None,
                              lineages=lineage(ANCHORS, 'published_table', 'reexport.json'))
    d = r.dossier.model_copy(deep=True)
    d.results[0].claims[1].sources = [s for s in d.results[0].claims[1].sources if s.method == 'structured']
    r = catalog.save(d, r.sources, r.ingestions, r.reference)
    with pytest.raises(ValueError, match='no evidence of its own'):
        validate(r.reference, 'limit', .2, _hash(catalog, r), catalog)


def test_one_sentence_anchors_one_point(tmp_path):
    """FA-01: a sentence printing two pairs cannot anchor both (which mass goes with which limit is not resolved)."""
    both = 'The limit is 1.20e-43 cm2 at 12 GeV and 1.50e-43 cm2 at 15 GeV.'
    catalog, r = figure_curve(tmp_path, [both, QUOTES[2]], located={0: both, 1: both, 2: QUOTES[2]})
    with pytest.raises(ValueError, match='more than one cross-section in one clause'):    # FR-02
        validate(r.reference, 'limit', .2, _hash(catalog, r), catalog)


@pytest.mark.parametrize('quote, match', [
    ('The Run B limit at 12 GeV is 1.20e-43 cm2.', 'names Run B'),
    ('At a WIMP mass of 12 GeV the 95 percent confidence upper limit is 1.20e-43 cm2.', '95% confidence level'),
    ('The observed limit at 12 GeV is 9.00e-43 cm2; the expected limit is 1.20e-43 cm2.', 'no evidence of its own'),
])
def test_the_anchors_own_clause_must_state_the_curves_result(tmp_path, quote, match):
    """FA-02: another run, a confidence level in words, an expected value in another clause of the sentence."""
    catalog, r = figure_curve(tmp_path, [quote, *QUOTES[1:]])
    with pytest.raises(ValueError, match=match):
        validate(r.reference, 'limit', .2, _hash(catalog, r), catalog)


@pytest.mark.parametrize('quote', ['At 12 GeV the limit is 1.20e-43 cm2, improving sensitivity by a factor of two.',
                                   'At 12 GeV the limit is 1.20e-43 cm2 with combined systematic uncertainties.'])
def test_an_improvement_or_combined_uncertainties_are_not_another_result(tmp_path, quote):
    """FA-02: the former false refusals."""
    catalog, r = figure_curve(tmp_path, [quote, *QUOTES[1:]])
    assert validate(r.reference, 'limit', .2, _hash(catalog, r), catalog).passed


@pytest.mark.parametrize('dataset', ['synthetic:run and selection', 'synthetic:run, fiducial', 'synthetic:run+quality'])
def test_punctuation_in_a_dataset_identifier_is_not_a_combination(tmp_path, dataset):
    """FA-02: a combined headline against a curve that names no constituent datasets is refused."""
    catalog, r = figure_curve(tmp_path, ['The combined limit at 12 GeV is 1.20e-43 cm2.', *QUOTES[1:]],
                              dataset_id=dataset, result=RESULT | {'dataset_id': dataset})
    with pytest.raises(ValueError, match='combined result'):
        validate(r.reference, 'limit', .2, _hash(catalog, r), catalog)


def test_renewal_needs_a_new_visual_review_when_the_overlay_changes(tmp_path, monkeypatch):
    """FA-06: the manual verification records the rendered page and the curve's geometry on it; a renewal whose
    overlay differs (here the renderer refuses the calibration, then draws another page) is refused."""
    from adroit.constraints import experimental_review as er
    catalog, r = figure_curve(tmp_path, QUOTES[1:2], ANCHORS[1:2])
    monkeypatch.setattr('adroit.retrieval.experimental_ingestion.render_page', lambda *a: _figure_png())
    verified = _verify(catalog, r)
    assert verified.manual.geometry_sha256 and verified.manual.source_image_sha256
    assert er.renew_figure(verified.validation_id, catalog).manual.renewed_from == verified.validation_id
    monkeypatch.setattr(er, '_source_overlay', lambda *a: (_ for _ in ()).throw(ValueError('renderer refuses')))
    with pytest.raises(ValueError, match='renderer refuses'):
        er.renew_figure(verified.validation_id, catalog)
    monkeypatch.undo()
    from PIL import Image
    other = io.BytesIO()
    Image.new('RGB', (900, 700), 'white').save(other, format='PNG')          # another rendering of the page
    monkeypatch.setattr('adroit.retrieval.experimental_ingestion.render_page', lambda *a: other.getvalue())
    with pytest.raises(ValueError, match='new visual review'):
        er.renew_figure(verified.validation_id, catalog)


# --- the recheck of 2026-10-19 (FR-01–FR-04) -------------------------------------------------------------------------

def _machine(tmp_path, extra, lineages, retrieved=()):
    return figure_curve(tmp_path, origin='machine_table', figure_axes={}, extra=extra, lineages=lineages,
                        retrieved=retrieved)


def test_a_retrieved_published_table_qualifies_its_anchors_by_their_cells(tmp_path):
    """FR-01: the authors' table as ADROIT retrieved it, its lineage naming the file, the row and the two columns."""
    catalog, r = _machine(tmp_path, [('table.json', hepdata(ANCHORS))], lineage(ANCHORS, 'published_table', 'table.json'),
                          retrieved=['table.json'])
    receipt = validate(r.reference, 'limit', .1, _hash(catalog, r), catalog)
    assert receipt.passed and receipt.basis == 'separate_source'
    assert [(a.row, a.column) for a in receipt.anchors] == [(1, 'limit'), (2, 'limit'), (3, 'limit')]


def test_a_data_file_of_undeclared_origin_is_no_evidence_whatever_it_claims(tmp_path):
    """FR-01 (the recheck's control): an export generated from the draft anchors, declared as a published table, is
    not retrieved from the publisher: it qualifies nothing."""
    catalog, r = _machine(tmp_path, [('table.json', hepdata(ANCHORS))], lineage(ANCHORS, 'published_table', 'table.json'))
    with pytest.raises(ValueError, match='origin is not established'):
        validate(r.reference, 'limit', .1, _hash(catalog, r), catalog)


@pytest.mark.parametrize('column, match', [('expected', 'states an expected sensitivity'),
                                           ('observed', 'no evidence of its own')])
def test_a_table_lineage_must_name_the_column_holding_the_curves_result(tmp_path, column, match):
    """FR-01 (the recheck's control): a table with observed and expected columns, the anchors equal to the expected
    ones. Naming the expected column states another result; naming the observed one, its cells do not hold the
    anchors."""
    table = json.dumps({'independent_variables': [{'header': {'name': 'mass'}, 'values': [{'value': x} for x, _ in ANCHORS]}],
                        'dependent_variables': [{'header': {'name': 'observed'}, 'values': [{'value': 9e-43}] * 3},
                                                {'header': {'name': 'expected'}, 'values': [{'value': y} for _, y in ANCHORS]}]})
    catalog, r = _machine(tmp_path, [('table.json', table)],
                          lineage(ANCHORS, 'published_table', 'table.json', ('mass', column)), retrieved=['table.json'])
    with pytest.raises(ValueError, match=match):
        validate(r.reference, 'limit', .1, _hash(catalog, r), catalog)


def test_a_lineage_naming_another_document_is_not_bound(tmp_path):
    catalog, r = _machine(tmp_path, [('table.json', hepdata(ANCHORS))],
                          lineage(ANCHORS, 'published_table', 'Table 99 of another paper'), retrieved=['table.json'])
    with pytest.raises(ValueError, match='no evidence of its own'):
        validate(r.reference, 'limit', .1, _hash(catalog, r), catalog)


@pytest.mark.parametrize('quote, match', [
    ('At 12 GeV the observed and expected upper limits are 9.00e-43 cm2 and 1.20e-43 cm2, respectively.',
     'more than one cross-section'),
    ('These are the combined limits from Run A and Run B. At 12 GeV the upper limit is 1.20e-43 cm2.', 'combined result'),
    ('The expected sensitivity is shown in Fig. 4. At 12 GeV the upper limit is 1.20e-43 cm2.', 'expected sensitivity'),
])
def test_a_clause_and_its_context_must_state_the_curves_result(tmp_path, quote, match):
    """FR-02 (the recheck's controls): two results in one clause are ambiguous; a clause silent on a qualifier takes
    the quotation's preceding sentence, here a combination or an expected sensitivity."""
    catalog, r = figure_curve(tmp_path, [quote, *QUOTES[1:]])
    with pytest.raises(ValueError, match=match):
        validate(r.reference, 'limit', .2, _hash(catalog, r), catalog)


@pytest.mark.parametrize('quote', ['With an exposure of 1.4 tonne-years, at 12 GeV the upper limit is 1.20e-43 cm2.',
                                   'Using the dataset collected in 2020, at 12 GeV the upper limit is 1.20e-43 cm2.'])
def test_an_exposure_or_a_dataset_described_in_words_is_not_another_run(tmp_path, quote):
    """FR-02: "an exposure of" and "the dataset collected" name no run (the former false refusals)."""
    catalog, r = figure_curve(tmp_path, [quote, *QUOTES[1:]])
    assert validate(r.reference, 'limit', .2, _hash(catalog, r), catalog).passed


def test_editing_a_lineage_label_does_not_reset_the_fixed_tolerance(tmp_path):
    """FR-03 (the recheck's control): the policy is keyed by the comparison's numbers, so a textual edit of the
    reference (a lineage's 'where') keeps the tolerance fixed; a declared tolerance revises it."""
    catalog, r = figure_curve(tmp_path)
    validate(r.reference, 'limit', .2, _hash(catalog, r), catalog)
    d = r.dossier.model_copy(deep=True)
    d.results[0].claims[1].value['lineage'][0]['where'] = 'the first sentence'
    edited = catalog.save(d, r.sources, r.ingestions, r.reference)
    with pytest.raises(ValueError, match='fixed at 0.2'):
        validate(edited.reference, 'limit', .3, _hash(catalog, edited), catalog)
    d.results[0].claims[1].value['tolerance'] = .3
    declared = catalog.save(d, r.sources, r.ingestions, edited.reference)
    assert validate(declared.reference, 'limit', .3, _hash(catalog, declared), catalog).tolerance == .3


def test_an_attempt_refused_before_any_comparison_fixes_no_tolerance(tmp_path):
    """FR-03 (the recheck's control): a tolerance finer than the printed precision is refused before any comparison
    and leaves the scope free."""
    catalog, r = figure_curve(tmp_path)
    with pytest.raises(ValueError):
        validate(r.reference, 'limit', 1e-5, _hash(catalog, r), catalog)
    assert validate(r.reference, 'limit', .2, _hash(catalog, r), catalog).passed


def test_the_verification_binds_to_the_packet_shown(tmp_path, monkeypatch):
    """FR-04 (the recheck's control): the packet's own page and overlay are hashed; a packet changed after it was
    drawn, or drawn for another curve, is refused; a second rendering never stands in for it."""
    from adroit.constraints import experimental_review as er
    monkeypatch.setattr('adroit.retrieval.experimental_ingestion.render_page', lambda *a: _figure_png())
    catalog, r = figure_curve(tmp_path, QUOTES[1:2], ANCHORS[1:2])
    folder = tmp_path / 'packet'
    shown = er.plot_packet(r.reference, 'limit', folder, catalog)
    monkeypatch.setattr(er, '_page_image', lambda *a: b'not what was shown')          # a later rendering differs
    receipt = _verify(catalog, r, packet=folder)
    assert receipt.manual.source_image_sha256 == shown['source_image_sha256']
    assert receipt.manual.overlay_sha256 == shown['overlay_sha256']
    (folder / 'source_overlay.png').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='has changed since it was drawn'):
        _verify(catalog, r, packet=folder)


@pytest.mark.parametrize('retrieved', [False, True])
def test_a_pdf_qualifies_as_a_separate_source_only_as_the_publisher_gave_it(tmp_path, retrieved):
    """The tactical audit's T20-09: a PDF printed from the machine-table curve's own numbers, imported without any
    retrieval, had passed as the authors' printed document. Its origin must be established as a data file's is."""
    quotes = [f'At {x:.1f} GeV the observed upper limit is {y:.3e} cm2.' for x, y in CURVE]
    points = [list(p) for p in CURVE]
    catalog, r = figure_curve(tmp_path, anchors=points, origin='machine_table', figure_axes={},
                              extra=[('transcribed.pdf', _paper(quotes))],
                              lineages=lineage(points, document='transcribed.pdf'),
                              retrieved=['transcribed.pdf'] if retrieved else [])
    d = r.dossier.model_copy(deep=True)
    sha = next(a.sha256 for a in r.sources if a.name == 'transcribed.pdf')
    d.results[0].claims[1].sources = [SourceLocator(asset_sha256=sha, method='text', page=1, excerpt=q) for q in quotes]
    r = catalog.save(d, r.sources, r.ingestions, r.reference)
    if retrieved:
        assert validate(r.reference, 'limit', .2, _hash(catalog, r), catalog).basis == 'separate_source'
    else:
        with pytest.raises(ValueError, match='origin is not established'):
            validate(r.reference, 'limit', .2, _hash(catalog, r), catalog)
