"""Several generations of a new field (the owner's decision #5, 2026-10-20; ``model_building.generations``): a new
field of N generations is N fields before G1, its terms expanded with their flavour factors."""
import pytest

from adroit.core.model_spec import ModelSpec, ModelTerm
from adroit.model_building import gauge_basis, generations
from adroit.model_building.gauge_basis import GaugeBasisError


def _spec(chi: dict, current: dict | None = None, more: list | None = None) -> ModelSpec:
    term = {'fields': [{'field': 'chi', 'conjugate': True}, {'field': 'chi'}, {'field': 'X'}], 'lorentz': 'vector',
            'coupling': 'g', **(current or {})}
    return ModelSpec.model_validate({'name': 'g', 'phase': 'broken', 'fields': [
        {'name': 'chi', 'role': 'dark_matter', 'spin': .5, 'dark_parity': -1, **chi},
        {'name': 'X', 'role': 'mediator', 'spin': 1, 'self_conjugate': True, 'mass_gev': 500.0},
        {'name': 'e', 'role': 'standard_model', 'spin': .5}],
        'terms': [term] + (more or []), 'couplings': [{'name': 'g', 'value': .5}]})


def _terms(spec: ModelSpec) -> list[tuple]:
    return [(tuple(o.field + ('*' if o.conjugate else '') for o in t.fields), t.coupling, t.plus_hc)
            for t in spec.terms]


def test_a_field_of_three_generations_is_three_fields_the_lightest_the_dark_matter():
    out = generations.expand(_spec({'generations': 3, 'masses_gev': [130.0, 100.0, 170.0]}))
    assert [(f.name, f.role.value, f.mass_gev, f.generations) for f in out.fields[:3]] == [
        ('chi1', 'other', 130.0, 1), ('chi2', 'dark_matter', 100.0, 1), ('chi3', 'other', 170.0, 1)]
    assert _terms(out) == [(('chi1*', 'chi1', 'X'), 'g', False), (('chi2*', 'chi2', 'X'), 'g', False),
                           (('chi3*', 'chi3', 'X'), 'g', False)]                   # flavour conserved by default


def test_a_flavour_matrix_writes_each_off_diagonal_pair_once_with_its_hermitian_conjugate():
    """Σ_ij M_ij χ̄_iγχ_j X = Σ_i M_ii χ̄_iγχ_i X + Σ_{i<j} (M_ij χ̄_iγχ_j X + h.c.) for symmetric M; a zero entry
    writes nothing."""
    flavour = [[1.0, 0.3, 0.0], [0.3, 2.0, 0.0], [0.0, 0.0, 0.0]]
    out = generations.expand(_spec({'generations': 3, 'masses_gev': [100.0, 130.0, 170.0]}, {'flavour': flavour}))
    assert _terms(out) == [(('chi1*', 'chi1', 'X'), 'g', False), (('chi1*', 'chi2', 'X'), '(g)*0.3', True),
                           (('chi2*', 'chi2', 'X'), '(g)*2.0', False)]
    gauge_basis.build(out)                                                         # G1 accepts every term


def test_one_occurrence_takes_a_list_and_a_degenerate_field_keeps_its_mass():
    spec = ModelSpec.model_validate({'name': 'g', 'phase': 'broken', 'fields': [
        {'name': 'chi', 'role': 'dark_matter', 'spin': .5, 'dark_parity': -1, 'mass_gev': 50.0},
        {'name': 'X', 'role': 'mediator', 'spin': 1, 'self_conjugate': True, 'generations': 2, 'mass_gev': 500.0},
        {'name': 'e', 'role': 'standard_model', 'spin': .5}],
        'terms': [{'fields': [{'field': 'e', 'conjugate': True}, {'field': 'e'}, {'field': 'X'}], 'lorentz': 'vector',
                   'coupling': 'g', 'flavour': [1.0, 0.5]}], 'couplings': [{'name': 'g', 'value': .5}]})
    out = generations.expand(spec)
    assert [(f.name, f.role.value, f.mass_gev) for f in out.fields if f.name.startswith('X')] == [
        ('X1', 'mediator', 500.0), ('X2', 'mediator', 500.0)]
    assert _terms(out) == [(('e*', 'e', 'X1'), 'g', False), (('e*', 'e', 'X2'), '(g)*0.5', False)]


@pytest.mark.parametrize('chi, current, message', [
    ({'generations': 2, 'masses_gev': [1.0]}, {}, '1 masses for 2 generations'),
    ({'generations': 2, 'masses_gev': [1.0, 2.0], 'mass_gev': 1.0}, {}, 'states its mass twice'),
    ({'masses_gev': [1.0, 2.0], 'mass_gev': None}, {}, 'masses_gev is for a new field of several generations'),
    ({'generations': 2, 'masses_gev': [1.0, 2.0]}, {'flavour': [[1, .2], [.3, 1]]}, 'must be symmetric'),
    ({'generations': 2, 'masses_gev': [1.0, 2.0]}, {'flavour': [1, 1]}, 'a 2 × 2 matrix'),
    ({'mass_gev': 1.0}, {'flavour': [[1]]}, 'no multi-generation field'),
])
def test_what_cannot_be_expanded_is_refused_by_name(chi, current, message):
    with pytest.raises(GaugeBasisError, match=message):
        gauge_basis.build(_spec(chi, current))


def test_a_generation_named_as_an_existing_field_and_three_occurrences_are_refused():
    spec = _spec({'generations': 2, 'masses_gev': [1.0, 2.0]})
    clash = spec.model_copy(update={'fields': spec.fields + [spec.fields[2].model_copy(update={'name': 'chi1'})]})
    with pytest.raises(generations.GenerationError, match='chi1, which the model uses'):
        generations.expand(clash)
    four = ModelTerm.model_validate({'fields': [{'field': 'chi', 'conjugate': True}, {'field': 'chi'},
                                                {'field': 'chi', 'conjugate': True}, {'field': 'chi'}],
                                     'lorentz': 'VV', 'coupling': 'g'})
    three = spec.model_copy(update={'terms': [four]})
    with pytest.raises(generations.GenerationError, match='more than two occurrences'):
        generations.expand(three)


def test_a_model_without_generations_is_unchanged():
    spec = _spec({'mass_gev': 1.0})
    assert generations.expand(spec) is spec
