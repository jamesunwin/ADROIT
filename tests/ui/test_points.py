"""The workbench's point table and point explanation (the owner's plan of 2026-10-18, §A), read from a saved study."""
from urllib.parse import urlencode

from nicegui.testing import User
from typer.testing import CliRunner

from adroit.ui.app import build_pages
from tests.evidence.test_points import _result


def _study(tmp_path):
    from adroit.orchestrator import studies
    folder = tmp_path / 'runs' / 'track1_vector'
    folder.mkdir(parents=True)
    path = _result(folder)
    (folder / 'report.md').write_text('# Track 1\n')
    studies.record(folder, 'track1', 'a vector mediator')
    return folder, path


async def test_a_study_lists_its_points_and_each_opens_its_explanation(user: User, tmp_path):
    folder, _ = _study(tmp_path)
    build_pages(tmp_path / 'runs')
    await user.open('/study?' + urlencode({'path': 'track1_vector'}))
    await user.should_see('Explain a point (5 points)')
    table = user.find(marker='points').elements.pop()
    assert {r['point'] for r in table.rows} == {'grid:0', 'grid:1', 'grid:2', 'grid:3', 'contour:0'}
    assert next(r for r in table.rows if r['point'] == 'grid:2')['omega'] == '—'
    await user.open('/study/point?' + urlencode({'path': 'track1_vector', 'point': 'grid:0'}))
    await user.should_see('Excluded here (1)')
    await user.should_see('Pending here (1)')
    await user.should_see('Allowed here (1)')
    await user.should_see('review the record atlas-2301.10731-hinv')
    await user.should_see("lies above xenon's floor")              # the neutrino fog, an annotation


def test_the_command_line_lists_and_explains_points(tmp_path):
    from adroit.orchestrator import cli
    _, path = _study(tmp_path)
    listed = CliRunner().invoke(cli.app, ['evidence', 'point', str(path)])
    assert listed.exit_code == 0 and 'grid:0\texcluded' in listed.stdout
    shown = CliRunner().invoke(cli.app, ['evidence', 'point', str(path), '--point', 'contour:0'])
    assert shown.exit_code == 0 and '"kind": "thermal root"' in shown.stdout


async def test_the_study_page_offers_its_downloads(user: User, tmp_path):
    import zipfile
    import io
    from adroit.ui import exports
    folder, path = _study(tmp_path)
    build_pages(tmp_path / 'runs')
    await user.open('/study?' + urlencode({'path': 'track1_vector'}))
    user.find(marker='downloads')
    for kind, _ in exports.CHOICES:
        name, data = exports.files(kind, path)
        assert name.startswith('track1_vector') and zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert not (folder / 'track1_vector_tables.zip').exists()


def test_the_command_line_writes_tables_and_figures(tmp_path):
    from adroit.orchestrator import cli
    _, path = _study(tmp_path)
    out = CliRunner().invoke(cli.app, ['evidence', 'tables', str(path), '--out', str(tmp_path / 'tables')])
    assert out.exit_code == 0 and (tmp_path / 'tables' / 'points.csv').exists()
    out = CliRunner().invoke(cli.app, ['evidence', 'figures', str(path), '--out', str(tmp_path / 'figures'),
                                       '--format', 'pdf'])
    assert out.exit_code == 0 and (tmp_path / 'figures' / 'parameter_plane.pdf').exists()
    assert CliRunner().invoke(cli.app, ['evidence', 'tables', str(path), '--out', str(tmp_path / 'tables')]).exit_code


async def test_the_plane_chart_places_every_point_and_marks_the_roots(user: User, tmp_path):
    from adroit.evidence.points import points
    from adroit.evidence.results import load_result
    from adroit.ui.points import chart_options
    _, path = _study(tmp_path)
    workflow, result = load_result(path)
    options = chart_options(workflow, result, points(workflow, result))
    names = {s['name']: [d['name'] for d in s['data']] for s in options['series']}
    assert names['excluded'] == ['grid:0'] and names['pending (thermal roots)'] == ['contour:0']
    assert sorted(n for v in names.values() for n in v) == ['contour:0', 'grid:0', 'grid:1', 'grid:2', 'grid:3']
    assert options['xAxis']['type'] == 'log' and options['xAxis']['name'] == 'm_med'
    build_pages(tmp_path / 'runs')
    await user.open('/study?' + urlencode({'path': 'track1_vector'}))
    user.find(marker='plane_chart')


def test_a_negative_logarithmic_scan_is_drawn_on_a_linear_axis() -> None:
    """The stacked audit's nonblocking note: the engine allows all-negative logarithmic coupling scans, which a log
    axis cannot draw; such an axis is linear and says so."""
    from types import SimpleNamespace
    from adroit.parameter_space.scan import Axis
    from adroit.ui.points import chart_options
    scan = SimpleNamespace(request=SimpleNamespace(x=Axis(parameter='m_chi', low=10, high=1000, n=3, log=True),
                                                   y=Axis(parameter='g_chi', low=-1.0, high=-0.01, n=3, log=True)))
    options = chart_options('track1', SimpleNamespace(scan=scan), [])
    assert options['xAxis']['type'] == 'log' and options['yAxis']['type'] == 'value'
    assert options['yAxis']['name'] == 'g_chi (linear axis)'
