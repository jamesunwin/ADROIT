"""The scan editor in the workbench (the owner's plan of 2026-10-18, §C): the reviewed setup as a table of
parameters; an edit rewrites the axes and clears the review, and the edited setup is what a new review and the run
use."""
import pytest
import yaml
from nicegui.testing import User

from adroit.ui.app import build_pages
from tests.ui.test_model_approval import launches, workspace


@pytest.mark.needs("cresst", "cdmslite", "optimum_interval", "solar_model")
async def test_the_setup_is_a_table_and_an_edit_is_what_scan_runs(user: User, tmp_path, monkeypatch):
    """The setup is shown as a table with no review button (the owner, 2026-11-22); an edit applies at once and Scan
    runs the edited setup."""
    root, folder, spec = workspace(tmp_path)
    calls = launches(monkeypatch)
    (root / 'model.yaml').write_text(yaml.safe_dump(spec.model_dump(mode='json')))
    build_pages(root)
    await user.open('/new/track1?model=model.yaml')
    await user.should_see('Scan setup: active coordinates')
    user.find(marker='scan_table')
    points = user.find(marker='points_m_chi').elements.pop()
    points.value = 3
    await user.should_see('edited: Scan runs the edited setup')
    x_axis, y_axis = (user.find(label).elements.pop().value for label in ('x axis', 'y axis'))
    assert any(text.startswith('m_chi:') and text.endswith(':3') for text in (x_axis, y_axis))
    user.find(marker='run_model_scan').click()
    await user.should_see('Run: model')
    command = calls[0][0]
    assert any(arg.startswith('m_chi:') and arg.endswith(':3') for arg in command)


async def test_an_invalid_table_edit_withdraws_the_review_and_cannot_launch(user: User, tmp_path, monkeypatch):
    """S18-08 (the stacked audit of 2026-10-18), the audit's control: clear the dark-matter mass's lower bound in the
    shown setup, see the table's error, press Scan. The old bounds had been launched; now nothing is."""
    root, folder, spec = workspace(tmp_path)
    calls = launches(monkeypatch)
    (root / 'model.yaml').write_text(yaml.safe_dump(spec.model_dump(mode='json')))
    build_pages(root)
    await user.open('/new/track1?model=model.yaml')
    await user.should_see('Scan setup: active coordinates')
    user.find(marker='low_m_chi').elements.pop().value = None
    await user.should_see('give its range, spacing and number of points')
    await user.should_see('the table is invalid')
    user.find(marker='run_model_scan').click()
    await user.should_see('the scan table is invalid')
    assert not calls
