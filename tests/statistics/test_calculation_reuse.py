"""Statistical reuse never changes CL, seed, bins or backend eligibility."""
import subprocess

import numpy as np
import pytest

from adroit.core import calculation_cache
from adroit.core.config import Settings
from adroit.statistics import poisson, optimum_interval as oi


def test_neyman_matches_fresh_and_every_statistical_input_invalidates(tmp_path, monkeypatch):
    monkeypatch.setattr(calculation_cache, 'get_settings', lambda: Settings(data_dir=tmp_path))
    monkeypatch.setattr(poisson.cache_identity, 'python_statistics', lambda: {'build': 'a'})
    original, calls = poisson._free_background_limit, []
    def counted(*args):
        calls.append(args)
        return original(*args)
    monkeypatch.setattr(poisson, '_free_background_limit', counted)
    cases = [([0, 3], [1., 2.], .9, 200, 17), ([0, 3], [1., 2.], .95, 200, 17),
             ([0, 3], [1., 2.], .9, 201, 17), ([0, 3], [1., 2.], .9, 200, 18),
             ([1, 3], [1., 2.], .9, 200, 17), ([0, 3], [1., 2.000000000000001], .9, 200, 17)]
    for args in cases:
        fresh = poisson.free_background_limit(*args, cache=False)
        before = len(calls)
        assert poisson.free_background_limit(*args) == fresh
        assert poisson.free_background_limit(*args) == fresh
        assert len(calls) == before + 1
    monkeypatch.setattr(poisson.cache_identity, 'python_statistics', lambda: {'build': 'b'})
    before = len(calls)
    poisson.free_background_limit(*cases[0])
    assert len(calls) == before + 1
    with pytest.raises(ValueError, match='finite'):
        poisson.free_background_limit([0], [0])


def test_yellin_matches_fresh_and_refuses_unavailable_failed_or_flagged_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(calculation_cache, 'get_settings', lambda: Settings(data_dir=tmp_path))
    binary = tmp_path/'binary'
    binary.write_text('backend')
    monkeypatch.setattr(oi, 'executable', lambda: binary)
    monkeypatch.setattr(oi.cache_identity, 'native', lambda b: {'contents': b.read_text()})
    calls, flag = [], [0]
    def calculate(binary, text):
        calls.append(text)
        return oi._Limit(mu=3., flag=flag[0])
    monkeypatch.setattr(oi, '_calculate', calculate)
    assert oi.optimum_interval_limit(np.array([.2, .8]), cache=False) == (3., 0)
    assert oi.optimum_interval_limit(np.array([.2, .8])) == (3., 0)
    assert oi.optimum_interval_limit(np.array([.2, .8])) == (3., 0) and len(calls) == 2
    oi.optimum_interval_limit(np.array([.2, .8]), .95)
    binary.write_text('updated backend')
    oi.optimum_interval_limit(np.array([.2, .8]))
    assert len(calls) == 4
    flag[0] = 1
    assert oi.optimum_interval_limit(np.array([.4])) == (3., 1)
    assert oi.optimum_interval_limit(np.array([.4])) == (3., 1) and len(calls) == 6
    def unavailable():
        raise oi.OptimumIntervalUnavailable('missing')
    monkeypatch.setattr(oi, 'executable', unavailable)
    with pytest.raises(oi.OptimumIntervalUnavailable):
        oi.optimum_interval_limit(np.array([.2, .8]))
    monkeypatch.setattr(oi, 'executable', lambda: binary)
    def failed(*args):
        raise subprocess.CalledProcessError(1, 'backend')
    monkeypatch.setattr(oi, '_calculate', failed)
    with pytest.raises(subprocess.CalledProcessError):
        oi.optimum_interval_limit(np.array([.6]))
