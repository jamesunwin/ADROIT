"""Several generations through the generic route (the owner's decision #5, 2026-10-20): the cases the calculation
covers are computed, the same as the fields written one by one; several stable components and an unresolved thermal
history are refused, by name (``generic._components``, ``_thermal_history``)."""
import pytest

from adroit.core.model_spec import ModelSpec
from adroit.parameter_space.portals.generic import GenericModel


def _model(masses: list[float], flavour, by_hand: bool = False) -> GenericModel:
    """Dirac dark matter in two generations, a 500 GeV vector X coupled to it (g χ̄_iγM_ijχ_j X) and to the electron."""
    fields = [{'name': 'X', 'role': 'mediator', 'spin': 1, 'self_conjugate': True, 'mass_gev': 500.0},
              {'name': 'e', 'role': 'standard_model', 'spin': .5}]
    electron = {'fields': [{'field': 'e', 'conjugate': True}, {'field': 'e'}, {'field': 'X'}], 'lorentz': 'vector',
                'coupling': 'g'}
    if by_hand:
        dark = [{'name': f'chi{i + 1}', 'role': 'dark_matter' if m == min(masses) else 'other', 'spin': .5,
                 'dark_parity': -1, 'mass_gev': m} for i, m in enumerate(masses)]
        terms = [{'fields': [{'field': 'chi1', 'conjugate': True}, {'field': 'chi1'}, {'field': 'X'}],
                  'lorentz': 'vector', 'coupling': 'g'},
                 {'fields': [{'field': 'chi1', 'conjugate': True}, {'field': 'chi2'}, {'field': 'X'}],
                  'lorentz': 'vector', 'coupling': f'(g)*{flavour[0][1]!r}', 'plus_hc': True},
                 {'fields': [{'field': 'chi2', 'conjugate': True}, {'field': 'chi2'}, {'field': 'X'}],
                  'lorentz': 'vector', 'coupling': 'g'}]
    else:
        dark = [{'name': 'chi', 'role': 'dark_matter', 'spin': .5, 'dark_parity': -1, 'generations': 2,
                 'masses_gev': masses}]
        terms = [{'fields': [{'field': 'chi', 'conjugate': True}, {'field': 'chi'}, {'field': 'X'}],
                  'lorentz': 'vector', 'coupling': 'g', **({'flavour': flavour} if flavour else {})}]
    spec = ModelSpec.model_validate({'name': 'two', 'phase': 'broken', 'fields': dark + fields,
                                     'terms': terms + [electron], 'couplings': [{'name': 'g', 'value': .5}]})
    return GenericModel.for_spec(spec)


MIXED = [[1.0, 0.3], [0.3, 1.0]]


def test_two_generations_that_mix_are_computed_as_the_same_fields_written_one_by_one():
    expanded, written = _model([100.0, 130.0], MIXED), _model([100.0, 130.0], MIXED, by_hand=True)
    p, q = expanded.point(), written.point()
    assert expanded.generations == ('chi',) and not written.generations
    assert expanded.domain(p) == '' and written.domain(q) == ''
    assert expanded.omega_h2(p) == pytest.approx(written.omega_h2(q), rel=1e-9)


@pytest.mark.parametrize('masses, flavour, reason', [
    ([100.0, 130.0], None, 'several stable components: chi20 (130 GeV) is joined to the dark matter by no interaction'),
    ([100.0, 100.0], MIXED, 'several stable components: chi20 is degenerate with the dark matter'),
    ([100.0, 130.0], [[1.0, 1e-9], [1e-9, 1.0]], 'the thermal history is not resolved: chi20 (130 GeV) converts'),
])
def test_several_stable_components_and_an_unresolved_thermal_history_are_refused(masses, flavour, reason):
    """Flavour conserved (the default): each generation's number conserved, a second stable component. Degenerate:
    χ₂ cannot decay. A feeble mixing: χ₂ converts at ~10⁻²⁶ GeV, far below 10 H at its freeze-out. Ωh² is not
    computed; the reason names the state."""
    engine = _model(masses, flavour)
    p = engine.point()
    assert engine.domain(p).startswith(reason) and engine.omega_h2(p) is None


def test_a_chain_of_conversions_certifies_a_state_that_does_not_reach_the_dark_matter_itself():
    """Bottaro et al.'s complex scalar triplet in the zoo's development half converts χ⁺⁺ to χ⁰ only through χ⁺ (rate
    0 directly, 10¹³ × 10 H through χ⁺): ``_thermal_history`` takes the chain, so the multiplet passes."""
    from adroit.evaluation import zoo
    from adroit.evaluation.core import Half, half_of
    from adroit.parameter_space.portals import generic
    entry = next(e for e in zoo.entries() if e.id == 'complex_scalar_triplet_y1_bottaro')
    assert half_of('model_zoo', entry.id) is Half.development
    target = entry.targets[0]
    engine = GenericModel.of(zoo._spec(entry, target), scan=target.scan, tied=target.tied or '')
    p = engine.point()
    mb, rules, model = engine.at(p)
    x_f = generic._freeze_out(engine.spec_json, engine.scan, engine.tied, p.m_chi, p.m_med)
    assert {x.name for x in rules.particles if x.parity == -1} >= {'chi++', 'chi+', 'chi0'}
    assert generic._components(mb, rules) == '' and generic._thermal_history(mb, rules, model, x_f) == ''
