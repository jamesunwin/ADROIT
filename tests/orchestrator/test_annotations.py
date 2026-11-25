"""Study annotations (the owner's workbench plan of 2026-10-18, part 2 §G): kept apart from the studies, filterable
by project, tag, favourite, model, dataset, verdict and status, and never changing a study's files."""
from __future__ import annotations

import hashlib
import json

from adroit.orchestrator import annotations as an
from adroit.orchestrator import studies


def _study(root, name, verdict='', models=(), request=None, status=''):
    """A study whose result is a real (minimal) result of its kind: an Explain-a-signal study where the request names
    an experiment, else a Track 1 study (the auditor's CR recheck, CS-01, 2026-10-27: the history reads a result as its
    kind's, so a partial one is damage)."""
    from adroit.model_building.audit import audit
    from adroit.orchestrator import track1
    from adroit.orchestrator.single_idea import SingleIdeaRequest, SingleIdeaResult
    from adroit.parameter_space import simplified
    from adroit.parameter_space.verdict import Verdict
    spec, request = simplified.model('vector', 10, 30), dict(request or {})
    if 'experiment' in request:
        kind, result = 'single_idea', SingleIdeaResult(request=SingleIdeaRequest(spec=spec, masses_gev=[10.0],
                                                                                 **request), level=verdict)
    else:
        kind, result = 'track1', track1.Track1Result(
            request=track1.Track1Request(spec=spec, **request), audit=audit(spec),
            verdict=Verdict(level=verdict, summary='', target=.12) if verdict else None)
    folder = root / name
    folder.mkdir(parents=True)
    (folder / 'result.json').write_text(result.model_dump_json())
    if status:
        (folder / 'job.json').write_text(json.dumps({'status': status}))
    studies.record(folder, kind, f'study {name}', model_references=list(models))
    return studies.load(folder)


def _digest(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def test_saving_normalises_and_an_empty_annotation_is_removed(tmp_path) -> None:
    s = _study(tmp_path, 'a')
    saved = an.save(tmp_path, s.folder, an.Annotation(project=' Paper A /vector mediator/ ', tags=['x', ' x', '', 'y']))
    assert saved.project == 'Paper A / vector mediator' and saved.tags == ['x', 'y'] and saved.edited_at
    assert an.load(tmp_path) == {'a': saved}
    an.save(tmp_path, s.folder, an.Annotation())
    assert an.load(tmp_path) == {}


def test_annotating_never_changes_a_studys_files(tmp_path) -> None:
    s = _study(tmp_path, 'a', verdict='viable')
    before = _digest(tmp_path / 'a')
    an.save(tmp_path, s.folder, an.Annotation(label='final figure', project='Paper A', note='the one in Fig. 2'))
    assert _digest(tmp_path / 'a') == before and (tmp_path / an.FILE).exists()


def test_the_filters_select_by_every_facet(tmp_path) -> None:
    a = _study(tmp_path, 'a', verdict='viable', models=['catalog:' + 'a' * 32 + '@' + 'b' * 64],
               request={'experiment': 'LZ', 'experimental_profile': 'profile:' + 'c' * 64})
    b = _study(tmp_path, 'b', verdict='excluded', status='failed')
    an.save(tmp_path, a.folder, an.Annotation(project='Paper A / vector mediator / final figures', tags=['figure'],
                                              favourite=True))
    an.save(tmp_path, b.folder, an.Annotation(project='Paper A / exploratory scans', note='a quick look'))
    notes = an.load(tmp_path)
    rows = [(an.facts(tmp_path, s), notes.get(an.key(tmp_path, s.folder))) for s in (a, b)]
    pick = lambda **f: [r[0].key for r in an.select(rows, **f)]  # noqa: E731
    assert pick(project='Paper A') == ['a', 'b'] and pick(project='Paper A / vector mediator') == ['a']
    assert pick(tag='figure') == pick(favourite=True) == pick(verdict='viable') == pick(dataset='LZ') == ['a']
    assert pick(model='catalog:' + 'a' * 32 + '@' + 'b' * 64) == ['a'] and pick(status='failed') == ['b']
    assert pick(text='quick look') == ['b']
    options = an.choices(rows)
    assert 'Paper A' in options['project'] and 'Paper A / vector mediator' in options['project']
    assert options['status'] == ['complete', 'failed']


def test_an_annotation_whose_study_is_gone_is_an_orphan(tmp_path) -> None:
    import shutil
    s = _study(tmp_path, 'a')
    an.save(tmp_path, s.folder, an.Annotation(note='keep'))
    shutil.rmtree(tmp_path / 'a')
    assert an.orphans(tmp_path) == ['a']
