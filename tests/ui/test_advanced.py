"""Advanced calculation options of Explain a signal and the native-fit page (the owner's workbench plan of
2026-10-18, part 2 §E): the command line's options, written only when they differ from its defaults, shown only
where they apply, and accepted by the real commands."""
from pathlib import Path

import pytest
import yaml
from nicegui.testing import User
from typer.testing import CliRunner

from adroit.orchestrator import cli
from adroit.ui import forms
from adroit.ui.app import build_pages
from tests.ui.test_model_approval import launches, workspace


def test_only_changed_options_are_written_and_native_ones_need_a_pair() -> None:
    assert forms.advanced_options({}) == []
    assert forms.advanced_options({'nulls': 'DEAP-3600 (2019)', 'native_toys': 50}) == ['--null', 'DEAP-3600 (2019)']
    native = forms.advanced_options({'native_joint': 'PICO-60 C3F8 (2019)', 'native_toys': 50, 'fit_grid': 17,
                                     'profile': 'none'})
    assert native == ['--profile', 'none', '--fit-grid', '17', '--native-joint', 'PICO-60 C3F8 (2019)',
                      '--native-toys', '50']
    with pytest.raises(ValueError, match='native joint pair'):
        forms.advanced_options({'native_joint': 'LZ'})
    with pytest.raises(ValueError, match='unknown'):
        forms.advanced_options({'toys': 5})


@pytest.mark.parametrize('command', [
    forms.single_idea_command(Path('m.yaml'), 'LZ', Path('out'), advanced={
        'nulls': 'DEAP-3600 (2019)', 'profile': 'none', 'propagation': 'central', 'fit_grid': 17,
        'fit_evaluations': 64, 'native_joint': 'DEAP-3600 (2019)', 'native_toys': 10, 'native_seed': 1,
        'native_fit_budget': 99, 'native_domain': 'd.yaml'}),
    forms.native_fit_command(Path('m.yaml'), Path('d.yaml'), Path('out'), 'DEAP-3600 (2019)', 7, 7, 100)])
def test_the_commands_are_ones_the_command_line_accepts(command) -> None:
    result = CliRunner().invoke(cli.app, [command[0], '--help'])
    assert result.exit_code == 0
    for option in [a for a in command if a.startswith('--')]:
        assert option in result.output, option


async def test_explain_a_signal_shows_native_options_only_for_a_pair_and_launches_them(user: User, tmp_path,
                                                                                       monkeypatch):
    root, folder, spec = workspace(tmp_path)
    calls = launches(monkeypatch)
    build_pages(root)
    await user.open('/new/single')
    user.find('the model (YAML, with coupling values)').elements.pop().value = yaml.safe_dump(spec.model_dump(mode='json'))
    await user.should_see('this model declares no bounded physical-fit range')
    await user.should_not_see('background-only simulations for calibration')
    user.find(marker='native_pair').elements.pop().value = 'DEAP-3600 (2019)'
    await user.should_see('background-only simulations for calibration')
    await user.should_see('background-only simulation fits (cap)')
    await user.should_not_see('toy fits')                                   # MF-14: no 'toys' label left
    await user.should_see('it does not replace the reference global significance')
    user.find('Run the study').click()
    await user.should_see('Run:')
    command = calls[0][0]
    assert command[command.index('--native-joint') + 1] == 'DEAP-3600 (2019)' and '--native-toys' not in command


def test_native_fit_is_withdrawn_from_the_workbench_and_the_cli_listing(tmp_path) -> None:
    """The owner's JU1 (2026-11-16): Native fit is not part of 1.0.0 (deferred to 1.0.2). Its page is not served and not
    in the menu; its command stays callable (its studies, tests and 1.0.2) but is not listed in the CLI's help."""
    from nicegui import app as nicegui_app
    from adroit.ui import style
    build_pages(tmp_path)
    assert '/new/native' not in {getattr(r, 'path', '') for r in nicegui_app.routes}
    assert not any(target == '/new/native' for _, links in style.NAV_GROUPS for _, target in links)
    command = next(c for c in cli.app.registered_commands if c.name == 'native-fit')
    assert command.hidden
    # every form recovery offers is a served page (the post-review owner's MF-05: a failed native fit linked to a 404)
    from adroit.orchestrator.recovery import FORMS
    served = {getattr(r, 'path', '') for r in nicegui_app.routes}
    assert all(target in served for target in FORMS.values()) and 'native-fit' not in FORMS


def test_a_cleared_null_selection_reaches_the_request_as_none(tmp_path) -> None:
    """S18-07 (the stacked audit of 2026-10-18), the audit's control: clearing every null experiment means none
    (``--null ''``), not the four defaults, from the form's values through the command line to the typed request;
    an untouched selection keeps the defaults; a profile does not change what the form wrote."""
    from unittest.mock import patch
    from typer.testing import CliRunner
    from adroit.orchestrator import cli, runs
    model = tmp_path / 'model.yaml'
    model.write_text(yaml.safe_dump(workspace(tmp_path)[2].model_dump(mode='json')))
    seen = {}

    def capture(request, *args):
        seen['nulls'] = request.null_modules
        return tmp_path, 'captured, not calculated'
    command = forms.single_idea_command(model, 'CDMS-II Si', tmp_path / 'out', advanced={'nulls': ''})
    assert command[command.index('--null') + 1] == ''
    with patch.object(runs, 'single_idea', capture):
        found = CliRunner().invoke(cli.app, command)
    assert found.exit_code == 0 and seen['nulls'] == []
    assert '--null' not in forms.single_idea_command(model, 'CDMS-II Si', tmp_path / 'out', advanced={})
    profiled = forms.advanced_options({'nulls': '', 'profile': 'profile:' + 'a' * 64})
    assert profiled[profiled.index('--null') + 1] == ''
