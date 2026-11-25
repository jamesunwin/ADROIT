"""The scan setup as a table of parameters and back (the owner's workbench plan, 2026-10-18, §C): the round trip
gives the same setup and review token for every kind of engine; derived and inactive parameters cannot be scanned,
with the engine's own message; any scientific edit changes the review token."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from adroit.core.model_spec import ModelSpec
from adroit.parameter_space import scan_table as st
from adroit.parameter_space.scan import Axis
from adroit.parameter_space.scan_setup import setup_identity

DOCS = Path(__file__).resolve().parents[2] / 'docs'


def _spec(name: str) -> ModelSpec:
    data = yaml.safe_load((DOCS / name).read_text())
    return ModelSpec.model_validate(data.get('spec', data))


def _token(spec, setup) -> str:
    from adroit.parameter_space.classify import classify
    cls, point, _ = classify(spec)
    return setup_identity(spec, cls, point, setup)


@pytest.mark.parametrize('name, x, y, ratio', [
    ('dm13/axial_mediator.yaml', Axis(parameter='m_med', low=10, high=1e4, n=5), Axis(parameter='m_chi', low=1, high=2000, n=4), None),
    ('dm13/axial_mediator.yaml', Axis(parameter='g_chi', low=0.1, high=1, n=3), Axis(parameter='m_chi', low=1, high=2000, n=4), 3.0),
    ('examples/flavour_vector.yaml', Axis(parameter='g_chi', low=0.05, high=0.5, n=3), Axis(parameter='m_chi', low=40, high=60, n=3), None),
    ('examples/complete_scalar_singlet.yaml', None, None, None)])
def test_the_round_trip_keeps_the_setup_and_its_review_token(name, x, y, ratio) -> None:
    spec = _spec(name)
    setup = st.setup_of(spec, x, y, ratio)
    rows = st.table(setup)
    assert [r.parameter for r in rows] == ['m_chi', 'm_med', 'g_chi', 'g_q', 'g_l']
    assert sorted(r.role for r in rows if r.role in ('x', 'y')) == ['x', 'y']
    back = st.setup_of(spec, *st.axes(rows))
    assert back == setup and _token(spec, back) == _token(spec, setup)
    if ratio:
        derived = next(r for r in rows if r.parameter == 'm_med')
        assert derived.role == 'derived' and derived.relation == 'm_med = 3 * m_chi'


def test_a_derived_or_inactive_parameter_cannot_be_scanned() -> None:
    spec = _spec('dm13/axial_mediator.yaml')
    rows = st.table(st.setup_of(spec, Axis(parameter='g_chi', low=0.1, high=1, n=3),
                                Axis(parameter='m_chi', low=1, high=2000, n=4), 3.0))
    moved = [r.model_copy(update={'role': 'x', 'low': 10.0, 'high': 100.0, 'spacing': 'log', 'points': 3})
             if r.parameter == 'm_med' else r.model_copy(update={'role': 'fixed'}) if r.role == 'x' else r for r in rows]
    with pytest.raises(ValueError, match=r'derived \(m_med = 3 \* m_chi\) and cannot be scanned'):
        st.axes(moved)
    flavour = st.table(st.setup_of(_spec('examples/flavour_vector.yaml')))
    inactive = [r for r in flavour if r.role == 'inactive']
    assert inactive and all(r.parameter not in st.scannable(flavour) for r in inactive)
    with pytest.raises(ValueError, match='choose exactly one parameter to scan on x'):
        st.axes([r.model_copy(update={'role': 'fixed'}) if r.role == 'x' else r for r in flavour])


def test_an_edit_changes_the_review_token() -> None:
    spec = _spec('dm13/axial_mediator.yaml')
    setup = st.setup_of(spec, Axis(parameter='m_med', low=10, high=1e4, n=5), Axis(parameter='m_chi', low=1, high=2000, n=4))
    rows = [r.model_copy(update={'points': 6}) if r.role == 'y' else r for r in st.table(setup)]
    edited = st.setup_of(spec, *st.axes(rows))
    assert _token(spec, edited) != _token(spec, setup) and edited.y['n'] == 6
