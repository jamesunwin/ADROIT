"""Constraint discovery's verdict-change study (synthetic, $0; the constraint discovery verdicts record of 2026-10-18): a custom Higgs-portal scalar on a 3×3 grid at the Higgs
resonance, four ways: as before; with a discovery pin holding one unsupported relevant search; with a bound synthetic
private BR(h → invisible) limit (0.05, replacing the ATLAS record); with both. No provider, no network.

    uv run python scripts/constraint_discovery_verdicts.py OUT_FOLDER   (set ADROIT_RUNS_DIR to scratch too)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))

from adroit.core.config import get_settings  # noqa: E402

settings = get_settings()
settings.experimental_library_dir = OUT / 'experimental_library'

from adroit.core.constraint_discovery import DiscoveryCoverage, Requirement  # noqa: E402
from adroit.library.experimental import ExperimentalCatalog  # noqa: E402
from adroit.orchestrator import constraint_discovery as cd, track1  # noqa: E402
from adroit.orchestrator.model_approval import model_identity  # noqa: E402
from adroit.parameter_space.library import entry  # noqa: E402
from adroit.parameter_space.private_limits import HIGGS_RECORD  # noqa: E402
from adroit.parameter_space.scan import Axis  # noqa: E402
from tests.private_limit_fixtures import eligible, fixture  # noqa: E402


def main() -> None:
    spec = entry('higgs_portal_scalar').spec()
    spec = spec.model_copy(update={'name': 'my scalar singlet', 'fields': [
        f.model_copy(update={'mass_gev': 50.0}) if f.name == 'S' else f for f in spec.fields]})
    catalog = ExperimentalCatalog()
    _, revision = fixture(OUT / 'fixture', 'sm_higgs_invisible', catalog=catalog, overlap='supersedes',
                          supersedes=[HIGGS_RECORD])
    bound = eligible(catalog, revision)
    coverage = DiscoveryCoverage(session_id='a' * 32, assessment_sha256='b' * 64, model_sha256=model_identity(spec),
                                 model_reference='file:' + model_identity(spec), searched_at='2026-10-18', requirements=[
                                     Requirement(candidate_id='x', name='Monojet search (synthetic)',
                                                 reference='arXiv:2501.00002', reason='needs calculation/validation: '
                                                 'a recast of the monojet signal regions', constraint_class='collider')])
    cd.load_coverage = lambda reference: coverage
    x = Axis(parameter='m_chi', low=55.0, high=62.4, n=3, log=False)
    y = Axis(parameter='g_chi', low=1e-4, high=1e-2, n=3, log=True)
    rows = {}
    for name, changes in (('as before', {}), ('discovery pin', {'discovery': coverage.reference}),
                          ('private limit', {'private_limits': [bound.reference]}),
                          ('both', {'discovery': coverage.reference, 'private_limits': [bound.reference]})):
        request = track1.Track1Request(spec=spec, x=x, y=y, literature=False, **changes)
        r = track1.run(request, OUT / name.replace(' ', '_'))
        rows[name] = {'level': r.verdict.level, 'summary': r.verdict.summary,
                      'crossings': [{'m_chi': round(c.point.m_chi, 3), 'g_chi': c.point.g_chi, 'status': c.status,
                                     'excluded_by': c.excluded_by,
                                     'discovery': [p for p in c.pending if p.startswith('discovery:')]}
                                    for c in r.verdict.crossings]}
    (OUT / 'verdicts.json').write_text(json.dumps(rows, indent=1))
    for name, row in rows.items():
        print(name, '|', row['level'], '|', [(c['m_chi'], c['status'], c['excluded_by'][:2]) for c in row['crossings']])


if __name__ == '__main__':
    main()
