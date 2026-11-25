"""Scientific reuse refuses changed identity, damaged payloads and concurrent writers."""
import json

import pytest

from adroit.core.checkpoint import Checkpoint, CheckpointMismatch, run_lock
from adroit.core.state import StrictModel
from adroit.orchestrator.track1_identity import tree_identity


class Row(StrictModel):
    value: float


def test_artifacts_resume_only_under_matching_inputs_and_dependencies(tmp_path):
    saved = Checkpoint(tmp_path, {"mass":100.}, {"code":"a"})
    saved.save("phase", "0", Row(value=2.))
    resumed = Checkpoint(tmp_path, {"mass":100.}, {"code":"a"}, resume=True)
    assert resumed.load("phase", "0", Row).value == 2
    for inputs, dependencies in [({"mass":101.},{"code":"a"}), ({"mass":100.},{"code":"b"})]:
        with pytest.raises(CheckpointMismatch, match="changed"):
            Checkpoint(tmp_path, inputs, dependencies, resume=True)


def test_damaged_payload_is_refused_and_failed_fit_infinity_is_preserved(tmp_path):
    saved = Checkpoint(tmp_path, {}, {})
    saved.save("phase", "0", Row(value=float('inf')))
    assert saved.load("phase", "0", Row).value == float('inf')
    path = tmp_path/'.track1-checkpoint/phase/0.json'
    content = json.loads(path.read_text())
    content['payload']['value'] = 3
    path.write_text(json.dumps(content))
    with pytest.raises(CheckpointMismatch):
        saved.load("phase", "0", Row)
    with pytest.raises(ValueError):
        saved.save("../escape", "0", Row(value=3))


def test_invalidated_epoch_cannot_be_resumed_even_after_sources_are_restored(tmp_path):
    saved = Checkpoint(tmp_path, {}, {"source":"original"})
    saved.invalidate()
    with pytest.raises(CheckpointMismatch):
        Checkpoint(tmp_path, {}, {"source":"original"}, resume=True)


def test_one_folder_has_one_writer_and_fresh_runs_archive_their_own_epoch(tmp_path):
    with run_lock(tmp_path):
        with pytest.raises(RuntimeError, match="already active") as refused:
            with run_lock(tmp_path):
                pass
    assert str(tmp_path) in str(refused.value) and "Track 1" not in str(refused.value)   # the folder, not a kind
    saved = Checkpoint(tmp_path, {}, {})
    saved.save("phase", "0", Row(value=2))
    (tmp_path/'model.yaml').write_text('owner input')
    Checkpoint(tmp_path, {}, {})
    assert len(list((tmp_path/'.track1-history').iterdir())) == 1
    assert (tmp_path/'model.yaml').read_text() == 'owner input'


def test_data_content_changes_identity_but_generated_bytecode_does_not(tmp_path):
    path=tmp_path/'physical.csv'
    path.write_text('1,2\n')
    before=tree_identity(tmp_path)
    cache=tmp_path/'__pycache__'
    cache.mkdir()
    (cache/'generated.pyc').write_bytes(b'temporary')
    assert tree_identity(tmp_path)==before
    path.write_text('1,3\n')
    assert tree_identity(tmp_path)!=before
