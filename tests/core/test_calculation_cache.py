"""Exact inputs, durable reuse, corruption and changing dependencies."""
import json

import pytest

from adroit.core import calculation_cache as cache
from adroit.core.config import Settings
from adroit.core.state import StrictModel


class Input(StrictModel):
    x: float


class Output(StrictModel):
    value: float


def test_exact_reuse_invalidation_damage_and_opt_out(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, 'get_settings', lambda: Settings(data_dir=tmp_path))
    calls, dependency = [], {'source': 'a'}
    def calculate():
        calls.append(1)
        return Output(value=2.)
    def run(x=1., enabled=True):
        return cache.reuse('fixture', Input(x=x), lambda: dict(dependency), calculate,
                           Output, lambda r: r.value > 0, enabled=enabled)
    assert run() == run() == Output(value=2.) and len(calls) == 1
    assert run(1.000000000000001).value == 2 and len(calls) == 2
    dependency['source'] = 'b'
    assert run().value == 2 and len(calls) == 3
    for path in (tmp_path/'calculation-cache/fixture').glob('*.json'):
        value = json.loads(path.read_text())
        value['payload']['value'] = 999
        path.write_text(json.dumps(value))
    assert run().value == 2 and len(calls) == 4
    assert run(enabled=False).value == 2 and len(calls) == 5
    monkeypatch.setenv('ADROIT_CALCULATION_CACHE', 'off')
    assert run().value == 2 and len(calls) == 6


def test_failures_rejected_outputs_and_mid_calculation_changes_are_not_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, 'get_settings', lambda: Settings(data_dir=tmp_path))
    dependency = {'source': 'a'}
    def change():
        dependency['source'] = 'b'
        return Output(value=2)
    cache.reuse('change', Input(x=1), lambda: dict(dependency), change, Output, lambda r: True)
    assert not list(tmp_path.rglob('*.json'))
    cache.reuse('rejected', Input(x=1), lambda: {}, lambda: Output(value=-1), Output, lambda r: r.value > 0)
    def fail():
        raise RuntimeError('backend failed')
    with pytest.raises(RuntimeError, match='backend failed'):
        cache.reuse('failed', Input(x=1), lambda: {}, fail, Output, lambda r: True)
    assert not list(tmp_path.rglob('*.json'))


def test_unwritable_cache_or_untracked_runtime_still_calculates(tmp_path, monkeypatch):
    root = tmp_path/'not_a_directory'
    root.write_text('fixture')
    monkeypatch.setattr(cache, 'get_settings', lambda: Settings(data_dir=root))
    calls = []
    def calculate():
        calls.append(1)
        return Output(value=2)
    assert cache.reuse('fixture', Input(x=1), lambda: {}, calculate, Output, lambda r: True).value == 2
    def unavailable():
        raise RuntimeError('runtime identity unavailable')
    assert cache.reuse('fixture', Input(x=1), unavailable, calculate, Output, lambda r: True).value == 2
    assert calls == [1, 1]


def _worker(root: str) -> float:
    import time
    from pathlib import Path
    cache.get_settings = lambda: Settings(data_dir=Path(root))
    def calculate():
        with (Path(root)/'calls.txt').open('a') as stream:
            stream.write('call\n')
        time.sleep(.1)
        return Output(value=2)
    return cache.reuse('concurrent', Input(x=1), lambda: {'runtime':'a'}, calculate, Output, lambda r: True).value


def test_two_processes_compute_one_exact_key_once(tmp_path):
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing
    with ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context('spawn')) as pool:
        assert list(pool.map(_worker, [str(tmp_path)]*2)) == [2., 2.]
    assert (tmp_path/'calls.txt').read_text() == 'call\n'


def test_unavailable_file_lock_does_not_block_fresh_calculation(tmp_path,monkeypatch):
    monkeypatch.setattr(cache,'get_settings',lambda:Settings(data_dir=tmp_path))
    def fail(*args):
        raise OSError('locking unsupported')
    monkeypatch.setattr(cache.fcntl,'flock',fail)
    assert cache.reuse('fixture',Input(x=1),lambda:{},lambda:Output(value=2),Output,lambda r:True).value==2
    assert not list(tmp_path.rglob('*.json'))
