"""S18-02 (the stacked audit of 2026-10-18): a private full-density SI curve applies only to a model that is all of
the dark matter, whichever route selects it: explicitly, through an experimental profile, or in a single-idea study.
The audit's control, adapted: the binding and the profile are in-memory stand-ins and the calculation is never
reached; no limit is signed."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from adroit.core.private_limits import LimitContract
from adroit.orchestrator import track1
from adroit.orchestrator.model_approval import model_identity
from adroit.parameter_space.library import entry
from adroit.parameter_space.private_limits import FULL_DENSITY, check_applicability

CONTRACT = LimitContract(adapter='si_isoscalar_curve', benchmark='elastic_contact_O1_cp_equals_cn',
                         quantity='sigma_nucleon_cm2', confidence_level=.95, construction='source upper limit',
                         selection='observed', dataset_id='synthetic-control', overlap='disjoint_from_selected',
                         units='cm2', points=[(1, 1e-40), (1000, 1e-40)], mass_range=(1, 1000), origin='machine_table',
                         halo={'rho_gev_cm3': .3, 'v0_km_s': 220, 'v_earth_km_s': 232, 'v_esc_km_s': 544},
                         assumptions=['full local dark matter density'], source_panel='synthetic source')
BINDING = SimpleNamespace(contract=CONTRACT, reference='private-limit:' + 'a' * 64)
REF = BINDING.reference


class Reached(Exception):
    pass


def _spec(fraction: float):
    return entry('higgs_portal_scalar').spec().model_copy(update={'relic_fraction': fraction})


def _track1(tmp_path: Path, name: str, **changes):
    spec = _spec(.1)
    request = track1.Track1Request(spec=spec, approved_model_sha256=model_identity(spec), literature=False, **changes)
    with patch('adroit.constraints.experimental_review.load_bound', return_value=BINDING), \
         patch('adroit.library.experimental_profiles.load', return_value=SimpleNamespace(limits=[REF])), \
         patch('adroit.orchestrator.track1_identity.dependencies', return_value={}), \
         patch.object(track1, '_run', side_effect=Reached):
        track1.run(request, tmp_path / name)


@pytest.mark.parametrize('route', [{'private_limits': [REF]}, {'experimental_profile': 'profile:' + 'b' * 64}])
def test_track1_refuses_a_subcomponent_model_whichever_route_selects_the_curve(tmp_path, route) -> None:
    with pytest.raises(ValueError, match='relic_fraction=1'):
        _track1(tmp_path, 'run', **route)


def test_single_idea_refuses_it_too() -> None:
    from adroit.orchestrator.single_idea import _fit_options
    request = SimpleNamespace(spec=_spec(.1), physical_fit_settings=None)
    profile = SimpleNamespace(limits=[REF], null_modules=[])
    with patch('adroit.constraints.experimental_review.load_bound', return_value=BINDING):
        with pytest.raises(ValueError, match='relic_fraction=1'):
            _fit_options(request, profile)


def test_the_shared_check_passes_a_full_density_model_and_names_the_rule() -> None:
    check_applicability(_spec(1.0), [BINDING])
    with pytest.raises(ValueError) as error:
        check_applicability(_spec(.5), [BINDING])
    assert str(error.value) == FULL_DENSITY and 'no implicit density rescaling' in FULL_DENSITY
