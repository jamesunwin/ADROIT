"""Advanced calculation options of Explain a signal, and the native-fit page (the owner's workbench plan of
2026-10-18, part 2 §E): the command line's further options, shown only where they apply, each with what its result
means."""
from __future__ import annotations

from pathlib import Path

import yaml
from nicegui import ui

from adroit.ui import forms

MEANING = {
    'data': 'The null experiments combined with the signal, and the personal profile (reviewed private limits and '
            'searches) used for this run only; the propagation model sets the charged cosmic-ray bounds.',
    'physical': 'The bounded physical fit profiles the model\'s declared coupling range at each mass. Its √q0 is '
                'descriptive: it is not a calibrated significance. The reported global significance stays the NR '
                'reference calculation.',
    'native': 'A native joint fit of the signal with one null search, calibrated by its own background-only simulations for '
              'that pair only (q0 and its p-value); it does not replace the reference global significance.',
}


def _spec_of(text: str):
    from adroit.orchestrator.model_approval import read_model
    try:
        return read_model(yaml.safe_load(text or ''))
    except (ValueError, TypeError, yaml.YAMLError):
        return None


def advanced_section(model_text, halo=None) -> callable:
    """The folded options of Explain a signal; ``model_text()`` gives the model's YAML; ``halo``: the page's own halo
    choice (``halo.halo_section``, shown above the options), else one made here. Returns a function giving
    ``(advanced options, files to write)`` for ``forms.single_idea_command``."""
    from adroit.experiments.registry import module_names
    from adroit.ui.experimental_profiles import options as profiles
    state: dict = {}
    with ui.expansion('Advanced calculation options').classes('w-full').mark('advanced'):
        ui.label(MEANING['data']).classes('text-sm text-gray-600')
        nulls = ui.select(module_names(), multiple=True, label='null experiments',
                          value=forms.ADVANCED['nulls'][1].split(',')).classes('w-full')
        choices = {'': 'the active profile (or packaged defaults)', **profiles()}
        profile = ui.select(choices, value='', label='experimental profile').classes('w-96')
        propagation = ui.select({'': 'the setting (default conservative)', 'conservative': 'conservative',
                                 'central': 'central', 'aggressive': 'aggressive'}, value='',
                                label='cosmic-ray propagation').classes('w-72')
        if halo is None:
            from adroit.ui.halo import halo_section
            halo = halo_section('single_idea')
        _physical_section(model_text, state)

        native = ui.select({'': 'none', **{p: p for p in forms.NATIVE_PAIRS}}, value='',
                           label='native joint fit with').classes('w-72').mark('native_pair')

        @ui.refreshable
        def native_options() -> None:
            if not native.value:
                return
            ui.label(MEANING['native']).classes('text-sm text-gray-600')
            with ui.row():
                state['native_toys'] = ui.number('background-only simulations for calibration', value=1000, min=1, max=100000)
                state['native_seed'] = ui.number('seed', value=20261007, min=0)
                state['native_fit_budget'] = ui.number('background-only simulation fits (cap)', value=10000, min=1, max=1000000)
            state['native_domain'] = ui.textarea('optional named physical domain (YAML; a separate, uncalibrated '
                                                 'multiparameter fit)').classes('w-full font-mono').props('rows=6')
        native_options()
        native.on_value_change(lambda _: native_options.refresh())

    def values() -> tuple[dict, dict]:
        chosen = {'nulls': ','.join(nulls.value or []), 'profile': profile.value, 'propagation': propagation.value,
                  **halo(), 'native_joint': native.value}
        for name in ('fit_grid', 'fit_evaluations', 'native_toys', 'native_seed', 'native_fit_budget'):
            if name in state and (name.startswith('fit') or native.value):
                chosen[name] = int(state[name].value)
        files = {}
        domain = state.get('native_domain')
        if native.value and domain is not None and (domain.value or '').strip():
            files['native_domain'] = domain.value
        return chosen, files
    return values


def _physical_section(model_text, state: dict) -> None:
    """The physical-fit options, shown where the model declares a bounded range; its inputs go into ``state``."""
    @ui.refreshable
    def physical() -> None:
        spec = _spec_of(model_text())
        if spec is None or spec.physical_fit is None:
            ui.label('Physical fit: this model declares no bounded physical-fit range, so the NR reference fit is '
                     'used (declare physical_fit in the model to enable it).').classes('text-sm text-gray-600')
            state.pop('fit_grid', None)
            state.pop('fit_evaluations', None)
            return
        ui.label(MEANING['physical']).classes('text-sm text-gray-600')
        with ui.row():
            state['fit_grid'] = ui.number('physical-fit resolution', value=33, min=9, max=129, step=2)
            state['fit_evaluations'] = ui.number('spectrum evaluations per fit (cap)', value=512, min=5, max=5000)
    physical()
    ui.button('Refresh for the current model', on_click=physical.refresh).props('flat dense')


def native_page(root: Path) -> None:
    """The native fit: shared bounded physical parameters fitted to a declared native pair. $0; no calibrated p."""
    from adroit.core.config import PROJECT_ROOT
    from adroit.ui.pages import header
    from adroit.ui.wizards import _start
    header('Native fit', 'Fit shared bounded physical parameters of one model to a declared native pair (a signal '
           'search and its null) over a named physical domain. The result is a best fit with profile likelihoods; it '
           'gives no calibrated p-value.', facts=('$0', 'result: a study with the fit and its profiles'))
    examples = PROJECT_ROOT / 'docs' / 'examples'
    model = ui.textarea('the model (YAML, with coupling values)',
                        value=(examples / 'native_low_mass_model.yaml').read_text()).classes('w-full font-mono') \
        .props('rows=10')
    domain = ui.textarea('the named physical domain (YAML)', value=(examples / 'native_fit_domain.yaml').read_text()) \
        .classes('w-full font-mono').props('rows=10')
    with ui.row():
        null = ui.select({p: p for p in forms.NATIVE_PAIRS}, value='PICO-60 C3F8 (2019)', label='null experiment')
        fit_grid = ui.number('coarse points per free coordinate', value=5, min=3, max=17)
        profile_grid = ui.number('profile points per coordinate', value=5, min=3, max=17)
        evaluations = ui.number('likelihood evaluations (cap)', value=12000, min=5, max=100000)

    def run() -> None:
        _start(root, 'native_fit', 'native fit', {'model': model.value, 'domain': domain.value},
               lambda f, p: forms.native_fit_command(p['model'], p['domain'], f, null.value, int(fit_grid.value),
                                                     int(profile_grid.value), int(evaluations.value)))
    ui.button('Run the native fit', on_click=run).props('color=primary').mark('run_native')
