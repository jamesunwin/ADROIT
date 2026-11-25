"""A study's page for public reading (the owner's JU1, item 5, 2026-11-16): the report's headline down to its plots,
the rest under "See details", no "to be built" column, a line saying the study is saved, and a Home button."""
from urllib.parse import urlencode

from nicegui.testing import User

from adroit.ui.app import build_pages
from adroit.ui.pages import split_at_figures, without_build_column
from tests.orchestrator.test_annotations import _study

CHECKLIST = ("**Thermal history**\n\n| check | status | for this model | to be built |\n|---|---|---|---|\n"
             "| Relic abundance | computed | roots found | — |\n"
             "| Initial chemical equilibrium | applies | Γ against H | the rate against H(T), for every class |\n\nTotals.\n")
REPORT = ("# Track 1: a model\n\n## 2. The verdict\n\n**VIABLE**: the headline.\n\n## 3. Parameter space\n\n"
          "![plane.png](plane.png)\n\n![dd.png](dd.png)\n\nPoints on the thermal-relic contour: the long table.\n\n"
          "## 6. Viability checklist\n\n" + CHECKLIST)


def test_the_report_is_cut_after_its_first_run_of_figures() -> None:
    head, rest = split_at_figures(REPORT)
    assert head.rstrip().endswith("![dd.png](dd.png)") and "the headline" in head
    assert rest.lstrip().startswith("Points on the thermal-relic contour") and "Viability checklist" in rest
    assert split_at_figures("# no figures\n\ntext\n") == ("# no figures\n\ntext\n", "")


def test_the_checklists_build_column_is_left_out_and_nothing_else() -> None:
    text = without_build_column("| a | b |\n|---|---|\n| 1 | 2 |\n\n" + CHECKLIST)
    assert "to be built" not in text and "for every class" not in text
    assert "| check | status | for this model |\n|---|---|---|\n| Relic abundance | computed | roots found |" in text
    assert text.startswith("| a | b |\n|---|---|\n| 1 | 2 |")                       # another table untouched


async def test_a_study_page_shows_its_headline_and_folds_the_rest(user: User, tmp_path) -> None:
    root = tmp_path / 'runs'
    _study(root, 'a', verdict='viable')
    (root / 'a' / 'report.md').write_text(REPORT)
    for name in ('plane.png', 'dd.png'):
        (root / 'a' / name).write_bytes(b'\x89PNG\r\n\x1a\n')
    build_pages(root)
    await user.open('/study?' + urlencode({'path': 'a'}))
    await user.should_see('This analysis has been successfully saved in Studies.')
    await user.should_see(marker='report_details')
    await user.should_see(marker='home')
    column = user.find(marker='report').elements.pop()
    shown = next(c for c in column.default_slot.children if hasattr(c, 'content')).content    # past its note
    assert 'the headline' in shown and 'the long table' not in shown
    details = user.find(marker='report_details').elements.pop()
    folded = details.default_slot.children[0].content
    assert 'the long table' in folded and 'Initial chemical equilibrium' in folded and 'for every class' not in folded
    assert (root / 'a' / 'report.md').read_text() == REPORT                       # the file keeps its column


async def test_add_a_signal_offers_the_papers_import_first(user: User, tmp_path) -> None:
    """The owner's JU1, item 9: on Add a signal, "1. Import it from the paper" comes before "2. Or write the record"."""
    build_pages(tmp_path / 'runs')
    await user.open('/new/anomaly')
    await user.should_see('1. Import it from the paper')
    titles = [e.text for e in user.client.layout.descendants() if 'adroit-section-title' in e.classes]
    assert titles.index('1. Import it from the paper') < titles.index('2. Or write the record'), titles
