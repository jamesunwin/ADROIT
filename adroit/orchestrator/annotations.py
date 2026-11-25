"""Researcher annotations of studies: a display label, a project path, tags, a favourite flag and a short note (the
owner's workbench plan of 2026-10-18, part 2 §G).

They live in one file under the runs folder (``.adroit/annotations.json``), keyed by each study's folder relative to
the runs root, and never touch a study's folder, result, evidence or study record: labelling or filing a study
changes neither its scientific identity nor any path another study refers to. An annotation whose study is gone is
kept and shown as an orphan.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from adroit.core.chronology import utc_now
from adroit.core.state import StrictModel

FILE = Path('.adroit') / 'annotations.json'


class Annotation(StrictModel):
    """One study's annotation."""
    label: str = Field(default='', max_length=200)        # a display name; the study's own title is unchanged
    project: str = Field(default='', max_length=300)      # a path, e.g. "Paper A / vector mediator / final figures"
    tags: list[str] = Field(default_factory=list)
    favourite: bool = False
    note: str = Field(default='', max_length=4000)
    edited_at: str = ''


class StudyFacts(StrictModel):
    """What the filters read from a saved study (never written)."""
    key: str
    folder: str
    kind: str
    title: str
    created: str
    verdict: str = ''
    status: str = 'complete'                                # complete, or its job's status
    models: list[str] = Field(default_factory=list)          # model revisions (catalog:…), or the model's name
    datasets: list[str] = Field(default_factory=list)        # the signal search, nulls, profile and private limits
    badge: str = ''                                          # the headline's words (``study_headline``)
    certification: str = ''                                  # certified, not certified, stale, legacy, or ""
    damage: str = ''                                         # why its result could not be read in full (CO-06)


def key(root: Path, folder: Path) -> str:
    """A study's key: its folder relative to the runs root."""
    return Path(folder).resolve().relative_to(Path(root).resolve()).as_posix()


def load(root: Path) -> dict[str, Annotation]:
    """Every readable annotation by study key (``listing``)."""
    return listing(root)[0]


def listing(root: Path):
    """(every readable annotation by study key; each that cannot be read, named with why). The consistency audit's
    CA-07 (2026-10-24): one invalid entry made every annotation unreadable. An entry that is not an annotation is
    named and kept as it is in the file (``save`` leaves it untouched); a file that is not a JSON object names the
    file, and no annotation can be saved until it is repaired."""
    from adroit.core.durable import Unreadable, reason
    path = Path(root) / FILE
    try:
        raw = _raw(root)
    except (OSError, ValueError) as error:
        return {}, [Unreadable(path=str(path), why=reason(error))]
    found, damaged = {}, []
    for k, v in raw.items():
        try:
            found[k] = Annotation.model_validate(v)
        except ValueError as error:
            damaged.append(Unreadable(path=f"{path} [{k}]", why=reason(error)))
    return found, damaged


def _raw(root: Path) -> dict:
    """The annotations file's entries as written ({} without the file); ValueError if it is not a JSON object."""
    path = Path(root) / FILE
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{path} is not a JSON object of annotations")
    return raw


def save(root: Path, folder: Path, annotation: Annotation) -> Annotation:
    """Write one study's annotation (tags trimmed and de-duplicated); an empty one is removed."""
    tags = list(dict.fromkeys(t.strip() for t in annotation.tags if t.strip()))
    annotation = annotation.model_copy(update={'tags': tags, 'label': annotation.label.strip(),
                                               'project': ' / '.join(p.strip() for p in annotation.project.split('/')
                                                                      if p.strip()),
                                               'edited_at': utc_now()})
    folder_key = key(root, folder)
    (Path(root) / FILE).parent.mkdir(parents=True, exist_ok=True)
    from adroit.core.durable import lock, write_atomic
    with lock((Path(root) / FILE).parent / ".annotations.lock"):    # waited for, never refused (M3)
        everything = _raw(root)              # every other entry as written, a damaged one included (CA-07)
        empty = annotation.model_dump(exclude={'edited_at'}) == Annotation().model_dump(exclude={'edited_at'})
        if empty:
            everything.pop(folder_key, None)
        else:
            everything[folder_key] = annotation.model_dump(mode='json')
        write_atomic(Path(root) / FILE, json.dumps(dict(sorted(everything.items())), ensure_ascii=False))
    return annotation


def forget(root: Path, folders: list[Path]) -> None:
    """Remove the annotations of deleted study folders and of the studies inside them (``ui.deletion``); every other
    entry is kept as written."""
    keys = [key(root, folder) for folder in folders]
    if not keys or not (Path(root) / FILE).exists():
        return
    from adroit.core.durable import lock, write_atomic
    with lock((Path(root) / FILE).parent / ".annotations.lock"):
        everything = _raw(root)
        kept = {k: v for k, v in everything.items() if not any(k == g or k.startswith(g + "/") for g in keys)}
        if kept != everything:
            write_atomic(Path(root) / FILE, json.dumps(dict(sorted(kept.items())), ensure_ascii=False))


def orphans(root: Path) -> list[str]:
    """Annotations whose study folder no longer exists."""
    return [k for k in load(root) if not (Path(root) / k / 'study.json').exists()]


def facts(root: Path, study) -> StudyFacts:
    """``held_facts``' facts."""
    return held_facts(root, study)[0]


def held_facts(root: Path, study):
    """A study's filterable facts from its record, result and job (read only). A result whose content is not what a
    result holds (a ``null`` or a number where a list belongs, a malformed certificate, truncated JSON) gives the
    study's facts without what it could not read, and says why (``damage``; the auditor's consolidation audit, CO-06,
    2026-10-25: one such result had made the whole Studies page fail); the study is still listed. The badge, the facts
    and the record they name the study by are of one version (``study_headline.held``: the record and the result read
    as one checked transaction; the version handle, the owner, 2026-11-03). A record of another version than the result
    is named in ``damage``, and its title, models and date are not taken as the result's (the auditor's version-identity
    audit, VI-01; its DB/VI recheck, DC-01, 2026-11-03: the history had joined A's title to B's verdict). With them, the
    version they are of, which the history's row shows. ``study``: the record as the list found it, whose kind names a
    study whose record cannot be read with its result."""
    from adroit.evidence.version import Unsettled
    from adroit.orchestrator import study_headline
    folder = Path(study.folder)
    try:
        found = study_headline.held(folder)
    except Unsettled as error:
        found = None
        why = str(error)
    if found is None:
        return StudyFacts(key=key(root, folder), folder=str(folder), kind=study.kind,
                          title=f"{folder.name} (its files changed each time they were read)", created="",
                          damage=why), None
    record = found.study() if found.record_state in study_headline.SHOWN else None
    headline = found.headline()                         # the badge, its level and certification (M1, CO-07)
    damage = [headline.damage] if headline.damage else []
    if record is None:
        damage.append("its study record describes another version of its result (one was replaced since the other was "
                      "written); its title, date and models are not shown" if found.record_state == "other" else
                      f"its study record is {found.record_state} when read with its result")
    read = found.snapshot()
    data = read.data if not headline.damage and isinstance(read.data, dict) else {}
    request = data.get('request') if isinstance(data.get('request'), dict) else {}
    datasets = [_word(request.get('experiment')), *_words(request, 'null_modules', damage),
                _word(request.get('experimental_profile')), *_words(request, 'private_limits', damage)]
    spec = request.get('spec') if isinstance(request.get('spec'), dict) else {}
    models = (list(record.model_references) if record is not None else []) \
        or ([spec['name']] if _word(spec.get('name')) else [])
    status = 'complete'
    job = folder / 'job.json'
    if job.exists():
        try:
            status = str(json.loads(job.read_text()).get('status', 'complete'))
        except (OSError, ValueError, AttributeError):
            pass
    return StudyFacts(key=key(root, folder), folder=str(folder), kind=found.kind or study.kind,
                      title=study_headline.listed(found), created=record.created if record is not None else "",
                      verdict=headline.level, status=status,
                      models=[m for m in models if m], datasets=[d for d in datasets if d], badge=headline.words,
                      certification=headline.certification, damage='; '.join(damage)), found


def _word(value) -> str:
    return value if isinstance(value, str) else ''


def _words(request: dict, name: str, damage: list[str]) -> list[str]:
    """A request's list of names (``null_modules``, ``private_limits``), absent for a kind without it; a value of
    another kind (``null``, a number) is noted in ``damage`` and read as none."""
    if name not in request:
        return []
    value = request[name]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        damage.append(f'its request\'s {name} is not a list of names')
        return []
    return value


def select(rows: list[tuple[StudyFacts, Annotation | None]], *, text: str = '', project: str = '', tag: str = '',
           favourite: bool = False, model: str = '', dataset: str = '', verdict: str = '',
           status: str = '', certification: str = '') -> list[tuple[StudyFacts, Annotation | None]]:
    """The rows that pass every filter given (a project matches itself and everything filed under it)."""
    out = []
    for f, a in rows:
        a_ = a or Annotation()
        words = ' '.join([f.title, a_.label, a_.project, a_.note, *a_.tags, f.kind]).lower()
        if text and text.lower() not in words:
            continue
        if project and not (a_.project == project or a_.project.startswith(project + ' / ')):
            continue
        if (tag and tag not in a_.tags) or (favourite and not a_.favourite) or (model and model not in f.models) \
                or (dataset and dataset not in f.datasets) or (verdict and f.verdict != verdict) \
                or (status and f.status != status) or (certification and f.certification != certification):
            continue
        out.append((f, a))
    return out


def choices(rows: list[tuple[StudyFacts, Annotation | None]]) -> dict[str, list[str]]:
    """The values each filter can take, from the studies and annotations present (projects with their parents)."""
    projects: set[str] = set()
    for _, a in rows:
        if a and a.project:
            parts = a.project.split(' / ')
            projects |= {' / '.join(parts[:i]) for i in range(1, len(parts) + 1)}
    return {'project': sorted(projects), 'tag': sorted({t for _, a in rows if a for t in a.tags}),
            'model': sorted({m for f, _ in rows for m in f.models}),
            'dataset': sorted({d for f, _ in rows for d in f.datasets}),
            'verdict': sorted({f.verdict for f, _ in rows if f.verdict}),
            'certification': sorted({f.certification for f, _ in rows if f.certification}),
            'status': sorted({f.status for f, _ in rows})}
