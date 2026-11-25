"""Studies that may need revisiting after an update (the owner's workbench plan of 2026-10-18, part 2 §H).

For each saved study, the inputs that have changed since it ran, with what actually changed:
- a personal **model** revision it used has a newer revision (the fields, couplings and terms that differ);
- a **constraint record** its comparisons used differs from the record as it is now (from the run's evidence: version,
  values, confidence level, assumptions or verification, field by field);
- its experimental **profile** has a successor (limits, signal or null searches added or removed);
- a **private limit** it selected is explicitly superseded by a newer binding.

Read only: nothing reruns, no study changes, and a newer input does not by itself make an old conclusion wrong. The
action offered is the existing reanalysis, which pins the new input and keeps the old result.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from adroit.core.state import StrictModel

CAVEAT = ('A newer input does not by itself make this result wrong; a reanalysis with the update gives a new, separate '
          'result and leaves this one as it is.')
MAX_LINES = 12


class Update(StrictModel):
    """One changed input of one study."""
    study: str                                      # the study's folder relative to the runs root
    title: str
    kind: Literal['model', 'record', 'profile', 'private limit']
    old: str
    new: str
    changes: list[str] = Field(default_factory=list)
    hint: str = ''                                  # how to pick the update up in a reanalysis
    # the version it was read from, which its reanalysis requires: its result's digest and its evidence's identity
    # (``build.evidence_held``), "" where not read (the auditor's DB/VI recheck, DC-04, 2026-11-03)
    sha256: str = ''
    evidence: str = ''


def differences(old, new, path: str = '') -> list[str]:
    """What differs between two JSON values, as "where: before → after" lines; lists of named items are matched by
    name."""
    if isinstance(old, dict) and isinstance(new, dict):
        out = []
        for k in sorted(set(old) | set(new)):
            out += differences(old.get(k), new.get(k), f'{path}.{k}' if path else str(k))
        return out
    if isinstance(old, list) and isinstance(new, list) and all(isinstance(x, dict) and 'name' in x for x in old + new):
        before, after = {x['name']: x for x in old}, {x['name']: x for x in new}
        out = [f'{path}: added {n}' for n in after if n not in before] + [f'{path}: removed {n}' for n in before
                                                                          if n not in after]
        for n in before:
            if n in after:
                out += differences(before[n], after[n], f'{path}[{n}]')
        return out
    if old != new:
        show = lambda v: '—' if v is None else json.dumps(v, ensure_ascii=False)[:80]  # noqa: E731
        return [f'{path}: {show(old)} → {show(new)}']
    return []


def _trim(lines: list[str]) -> list[str]:
    return lines[:MAX_LINES] + ([f'… and {len(lines) - MAX_LINES} more'] if len(lines) > MAX_LINES else [])


def _models(study, key: str, catalog) -> list[Update]:
    out = []
    for ref in study.model_references:
        if not ref.startswith('catalog:'):
            continue
        try:
            used = catalog.load(ref)
            later = [r for r in catalog.revisions(used.model_id) if r.created > used.created]
        except (ValueError, OSError):
            continue
        if later:
            newest = later[-1]
            out.append(Update(study=key, title=study.title, kind='model', old=ref, new=newest.reference,
                              changes=_trim(differences(used.spec.model_dump(mode='json'),
                                                        newest.spec.model_dump(mode='json'))),
                              hint=f'in the reanalysis, choose the model revision {newest.reference}'))
    return out


def _records(study, key: str, content: bytes | None, evidence) -> list[Update]:
    """Records the run's comparisons cited whose current content differs from the content the run recorded, from the
    evidence of the result's bytes as read (``content``; ``build.evidence_of``): evidence naming another version of the
    result says that which records were cited is not known (the auditor's CX recheck, CY-03, 2026-11-01: a page holding A had
    shown B's input history). While the records cannot be read, that whether they changed is not known (the auditor's CR
    recheck, CS-05, 2026-10-27: a damaged records file had made the study page a server error). ``evidence``: that
    evidence, read once (``build.evidence_held``), whose identity the update's reanalysis requires (DC-04)."""
    import yaml
    from adroit.constraints.database import records
    from adroit.core.durable import reason
    from adroit.evidence.build import NO_EVIDENCE
    if content is None or evidence.identity == NO_EVIDENCE:
        return []
    envelope = evidence.envelope
    if envelope is None:
        return [Update(study=key, title=study.title, kind='record', old='the records its run cited', new='not known',
                       changes=['its evidence is not of the result read (replaced while it was read, or damaged), so '
                                'which records its run cited, and in which versions, is not known'],
                       hint='reload the page; a reanalysis reads the evidence again')]
    used = {sid for o in envelope.observations for sid in o.source_ids}
    try:
        current = {r.id: r for r in records()}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError) as error:
        cited = sorted(source.id for source in envelope.context.sources if source.id in used)
        return [Update(study=key, title=study.title, kind='record', old=', '.join(cited), new='not known',
                       changes=[f'the constraint records cannot be read now ({reason(error)}), so whether these '
                                'changed is not known'], hint='restore the records file, then look again')] \
            if cited else []
    out = []
    for source in envelope.context.sources:
        record = current.get(source.id)
        if record is None or source.id not in used or not source.metadata:
            continue
        now = record.model_dump(mode='json')
        lines = [line for line in differences(source.metadata, now) if not line.startswith('notes')]
        if lines:
            out.append(Update(study=key, title=study.title, kind='record', old=f'{source.id} (version {source.version})',
                              new=f'{source.id} (version {record.version})', changes=_trim(lines),
                              hint='a reanalysis with the same inputs uses the record as it is now'))
    return out


def _request(content: bytes | None) -> dict:
    """The request of the result's bytes, or {} where the result is absent or damaged (``durable.parse_object``: a
    result holding ``null`` or a list had raised here and taken down its study's page; the auditor's CO recheck, CR-06)."""
    from adroit.core.durable import parse_object
    data = parse_object(content)[0] if content is not None else None
    return data.get('request') if data is not None and isinstance(data.get('request'), dict) else {}


def _profiles(study, key: str, catalog, request: dict) -> list[Update]:
    reference = request.get('experimental_profile', '')
    folder = catalog.path('profiles') if catalog.root.is_dir() else None
    if not reference or folder is None or not folder.is_dir():
        return []
    rows = {}
    for path in folder.glob('*.json'):
        try:
            rows['profile:' + path.stem] = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
    old = rows.get(reference)
    successors = [ref for ref, row in rows.items() if row.get('parent') == reference]
    if old is None or not successors:
        return []
    newest = max(successors, key=lambda ref: rows[ref].get('created_at', ''))
    new = rows[newest]
    lines = []
    for field in ('limits', 'null_modules'):
        lines += [f'{field}: added {x}' for x in new.get(field, []) if x not in old.get(field, [])]
        lines += [f'{field}: removed {x}' for x in old.get(field, []) if x not in new.get(field, [])]
    if new.get('signal') != old.get('signal'):
        lines.append(f"signal: {old.get('signal') or '—'} → {new.get('signal') or '—'}")
    return [Update(study=key, title=study.title, kind='profile', old=reference, new=newest,
                   changes=_trim(lines or ['the selection is unchanged; the profile was reviewed again']),
                   hint=f'in the reanalysis, choose the profile {newest}')]


def _limits(study, key: str, catalog, request: dict) -> list[Update]:
    selected = request.get('private_limits', [])
    if not selected:
        return []
    from adroit.library.records_index import _bound
    out = []
    for ref, item in _bound(catalog).items():
        replaced = [s for s in selected if s in item.contract.supersedes]
        for old in replaced:
            out.append(Update(study=key, title=study.title, kind='private limit', old=old, new=ref,
                              changes=[f'{item.name} explicitly supersedes it ({item.contract.dataset_id})'],
                              hint=f'in the reanalysis, select {ref} instead'))
    return out


def for_study(root: Path, found, catalog=None, models=None) -> list[Update]:
    """One study's updates, of one version of it (``found``: ``evidence.version.Version``, as its page resolved it; a
    study record in its place is resolved here, once): its request, its evidence and the record naming its models are
    of that version (the auditor's CW recheck, CX-02, 2026-10-31; its CX recheck, CY-03, 2026-11-01: the update card had read
    the evidence apart, and shown B's input history beside A). A record of another version, or none, names no models
    here. Each update names the result's digest and the evidence's identity it was read from, which its reanalysis
    requires (the auditor's DB/VI recheck, DC-04, 2026-11-03)."""
    from adroit.evidence.build import HeldEvidence
    from adroit.evidence.version import Version, resolve
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.library.personal import Catalog
    from adroit.orchestrator.annotations import key
    from adroit.orchestrator.study_headline import SHOWN, listed
    found = found if isinstance(found, Version) else resolve(Path(found.folder))
    catalog = catalog or ExperimentalCatalog()
    models = models or Catalog()
    k = key(root, found.folder)
    held = found.content
    evidence = found.held_evidence() if held is not None else HeldEvidence("", None)
    record = found.study() if found.record_state in SHOWN else None
    named = record if record is not None else _Unnamed(listed(found))
    asked = _request(held)
    out = (_models(named, k, models) + _records(named, k, held, evidence) + _profiles(named, k, catalog, asked)
           + _limits(named, k, catalog, asked))
    version = {'sha256': found.result_sha256, 'evidence': evidence.identity} if held is not None else {}
    return [update.model_copy(update=version) for update in out]


class _Unnamed:
    """A study whose record is not its result's (``for_study``): named by its folder, citing no models."""

    def __init__(self, title: str):
        self.title, self.model_references = title, []


def updates(root: Path, catalog=None, models=None) -> list[Update]:
    """Every study's updates under the runs root (see the module docstring)."""
    from adroit.library.experimental import ExperimentalCatalog
    from adroit.library.personal import Catalog
    from adroit.orchestrator import studies
    catalog = catalog or ExperimentalCatalog()
    models = models or Catalog()
    from adroit.evidence.version import Unsettled, resolve
    out = []
    for _, study in studies.tree(root):
        try:
            found = resolve(Path(study.folder))
        except Unsettled:                       # its files changed each time they were read: the history names it
            continue
        out += for_study(root, found, catalog, models)
    return out
