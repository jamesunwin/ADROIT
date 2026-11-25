"""Study organisation in the workbench (the owner's workbench plan of 2026-10-18, part 2 §G)."""
from urllib.parse import urlencode

from nicegui.testing import User

from adroit.orchestrator import annotations as an
from adroit.ui.app import build_pages
from tests.orchestrator.test_annotations import _study


async def test_a_study_is_labelled_on_its_page_and_filtered_on_the_list(user: User, tmp_path):
    root = tmp_path / 'runs'
    a = _study(root, 'a', verdict='viable')
    _study(root, 'b', verdict='excluded')
    (root / 'a' / 'report.md').write_text('# A\n')
    build_pages(root)
    await user.open('/study?' + urlencode({'path': 'a'}))
    user.find(marker='annotation_label').elements.pop().value = 'the final scan'
    user.find(marker='annotation_project').elements.pop().value = 'Paper A / final figures'
    user.find(marker='annotation_tags').elements.pop().value = 'figure, final'
    user.find(marker='save_annotation').click()
    await user.should_see('saved')
    assert an.load(root)['a'].tags == ['figure', 'final']
    await user.open('/studies')
    await user.should_see('the final scan')
    user.find(marker='filter_project').elements.pop().value = 'Paper A'
    await user.should_see('the final scan')
    await user.should_not_see('study b')
    assert a.title == 'study a'
