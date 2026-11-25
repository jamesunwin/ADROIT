"""The named Planck estimator sets the same statistical boundary in both tracks."""
import pytest

from adroit.constraints import database, planck, verdicts
from adroit.parameter_space import likelihood
from tests.constraints.test_verdicts import candidate


@pytest.mark.needs("eos")              # the relic verdict's band reads the tables (AL3-16's check, cycle 4)
def test_planck_table2_boundary_and_shared_likelihood(monkeypatch, awaiting) -> None:
    awaiting("planck-2018-omega")                                       # held unverified, whatever the owner has signed
    density = planck.measurement()
    assert 'TT,TE,EE+lowE+lensing' in density.estimator
    assert density.value + 2*density.sigma == pytest.approx(.1224)
    monkeypatch.setattr(verdicts.annihilation, 'omega_h2', lambda *a: .1222)
    result = verdicts.relic(candidate('V1',1000,100), database.record('planck-2018-omega'))
    assert result.excluded is False
    settings = likelihood.LikelihoodSettings(relic_theory=0)
    assert likelihood.relic_chi2(.1222,density.value,settings) == pytest.approx((.0022/.0012)**2)
    assert not database.record('planck-2018-omega').usable
