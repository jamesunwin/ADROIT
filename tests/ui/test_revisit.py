"""Studies to revisit in the workbench (the owner's workbench plan of 2026-10-18, part 2 §H)."""
from urllib.parse import urlencode

from nicegui.testing import User

from adroit.ui.app import build_pages
from tests.orchestrator.test_revisit import _study


async def test_a_superseded_input_is_listed_with_its_reanalysis(user: User, tmp_path):
    import json
    from adroit.library.experimental import ExperimentalCatalog
    catalog = ExperimentalCatalog()
    (catalog.root / 'profiles').mkdir(parents=True)
    old, new = 'a' * 64, 'b' * 64
    (catalog.root / 'profiles' / f'{old}.json').write_text(json.dumps({'limits': [], 'null_modules': [], 'signal': ''}))
    (catalog.root / 'profiles' / f'{new}.json').write_text(json.dumps({'limits': ['private-limit:2'], 'signal': '',
                                                                       'null_modules': [], 'parent': f'profile:{old}'}))
    root = tmp_path / 'runs'
    _study(root, 'a', request={'experimental_profile': f'profile:{old}'})
    (root / 'a' / 'report.md').write_text('# A\n')
    build_pages(root)
    await user.open('/studies/revisit')
    await user.should_see('limits: added private-limit:2')
    await user.should_see('A newer input does not by itself make this result wrong')
    user.find(marker='prepare_reanalysis')
    await user.open('/study?' + urlencode({'path': 'a'}))
    await user.should_see('Inputs updated since this study ran (1)')
