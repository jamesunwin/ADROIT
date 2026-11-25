"""One read-only index over the standard records and the personal additions (the owner's request, 2026-10-18).

It wraps the existing stores without changing them: the packaged constraint records (``records.yaml``), the experiment
modules and signal searches, and the personal experimental library's draft revisions, bound limits, bound searches
and profiles. Each entry keeps its exact reference in its own store; nothing is copied, shadowed or migrated.
"""
from __future__ import annotations

import json
import re

from adroit.core.constraint_discovery import InventoryEntry, ResultIdentity

ARXIV = re.compile(r'(?:arxiv:)?(\d{4}\.\d{4,5})(?:v\d+)?', re.I)
DOI = re.compile(r'(?:doi:)?(10\.\d{4,9}/\S+)', re.I)


def source_ids(*texts: str) -> list[str]:
    """The arXiv identifiers (without version) and DOIs in ``texts``, normalised as ``arxiv:…`` and ``doi:…``."""
    found: list[str] = []
    for text in texts:
        for m in ARXIV.finditer(text or ''):
            found.append('arxiv:' + m.group(1))
        for m in DOI.finditer(text or ''):
            found.append('doi:' + m.group(1).rstrip('.,;)').lower())
    return list(dict.fromkeys(found))


def record_identity(r) -> ResultIdentity:
    """A packaged record's result as it states it: its quantity, observed unless the quantity says expected, its
    confidence level and benchmark, its figure or table as the panel (not a paper's abstract), and the channel and
    dataset declared for it in ``record_results.yaml`` (a sidecar, so that the signed records are not edited)."""
    from importlib import resources
    import yaml
    declared = yaml.safe_load(resources.files('adroit.constraints').joinpath('data/record_results.yaml').read_text()) or {}
    extra = declared.get(r.id, {})
    label = getattr(getattr(r, 'figure', None), 'label', '') or ''
    expected = 'expected' in (r.quantity or '').lower() and 'observed' not in (r.quantity or '').lower()
    return ResultIdentity(quantity=r.quantity or '', selection='expected' if expected else 'observed',
                          confidence_level=r.confidence_level, benchmark=r.benchmark or '',
                          panel='' if label.lower() == 'abstract' else label,
                          channel=extra.get('channel', ''), dataset=extra.get('dataset', ''))


def contract_identity(contract) -> ResultIdentity:
    """A bound personal limit's result: its quantity, selection, confidence level, dataset and source panel (its
    adapter's benchmark is ADROIT's convention, checked through the adapter, not a paper's)."""
    quantity = {'sigma_nucleon_cm2': 'spin-independent WIMP–nucleon cross section',
                'BR_h_invisible': 'BR(h → invisible)'}.get(contract.quantity, contract.quantity)
    return ResultIdentity(quantity=quantity, selection=contract.selection, confidence_level=contract.confidence_level,
                          dataset=contract.dataset_id, panel=contract.source_panel)


def record_review(r) -> str:
    """A packaged record's review state as its evaluator reads it (``review_identity.signature_status``, through
    ``usable``): "verified" only where the person's approval still applies to the record as it is; "stale" where it
    was signed and has changed since; else "unverified". The consistency audit's CA-10 (2026-10-24): the index read a
    date's presence, and called a stale, unusable record verified."""
    from adroit.constraints.review_identity import signature_status
    if r.usable:
        return 'verified'
    return 'stale' if signature_status(r).state == 'stale' else 'unverified'


def standard() -> list[InventoryEntry]:
    """The packaged records, experiment modules and signal searches, each with its result's stated identity."""
    from adroit.constraints.database import records
    from adroit.experiments.registry import MODULES, SIGNAL_SEARCHES, load_module
    out = [InventoryEntry(reference='record:' + r.id, kind='standard_record', library='standard', title=r.name,
                          constraint_class=r.constraint_class.value, source_ids=source_ids(r.source),
                          review=record_review(r), origin='packaged',
                          quantity=r.quantity, benchmark=r.benchmark, confidence_level=r.confidence_level,
                          result=record_identity(r))
           for r in records()]
    for names, kind in ((MODULES, 'experiment_module'), (SIGNAL_SEARCHES, 'signal_search')):
        for name in names:
            try:
                info = load_module(name).info
                refs = list(getattr(info, 'references', []) or [])
            except (ValueError, OSError, RuntimeError):
                refs = []
            out.append(InventoryEntry(reference='module:' + name, kind=kind, library='standard', title=name,
                                      constraint_class='direct_detection', source_ids=source_ids(*refs),
                                      review='packaged', origin='packaged',
                                      quantity='direct-detection likelihood (spin-independent and spin-dependent)',
                                      result=ResultIdentity(quantity='direct-detection likelihood', selection='observed',
                                                            dataset=name)))
    return out


def personal(catalog=None) -> list[InventoryEntry]:
    """The personal experimental library's revisions, bound limits, bound searches and profiles, each with its
    origin (a manual import, or the discovery session that retrieved it)."""
    from adroit.library.experimental import ExperimentalCatalog
    catalog = catalog or ExperimentalCatalog()
    if not catalog.root.is_dir():
        return []
    out: list[InventoryEntry] = []
    bound = _bound(catalog)
    revisions = catalog.list() if catalog.path('experiments').is_dir() else []
    sessions = {r.experiment_id: r.provenance['discovery_session'] for r in revisions
                if r.provenance.get('discovery_session')}       # an extraction's revisions keep their draft's origin
    for r in revisions:
        origin = sessions.get(r.experiment_id, '')
        out.append(InventoryEntry(
            reference=r.reference, kind='personal_revision', library='personal', title=r.dossier.title,
            constraint_class=r.provenance.get('constraint_class', ''),
            source_ids=source_ids(*r.dossier.references), review=_review_state(catalog, r, bound),
            origin=f'discovery:{origin}' if origin else 'manual import'))
    for item in bound.values():
        out.append(InventoryEntry(reference=item.reference, kind='personal_limit', library='personal', title=item.name,
                                  constraint_class=_class(item.contract.adapter),
                                  source_ids=source_ids(*catalog.load(item.revision).dossier.references),
                                  review=_bound_review(item), adapter=item.contract.adapter,
                                  domain={'mass_range': list(item.contract.mass_range)} if item.contract.mass_range else {},
                                  origin=item.revision, result=contract_identity(item.contract)))
    out += _searches(catalog) + _profiles(catalog)
    return out


def index(catalog=None) -> list[InventoryEntry]:
    """Every entry, standard first."""
    return standard() + personal(catalog)


def _class(adapter: str) -> str:
    return {'si_isoscalar_curve': 'direct_detection', 'sm_higgs_invisible': 'collider'}.get(adapter, '')


def _bound(catalog) -> dict:
    """The current bound private limits by reference; a stale or modified binding is left out."""
    from adroit.constraints.experimental_review import load_bound
    out = {}
    folder = catalog.path('limits')
    for path in sorted(folder.glob('*.json')) if folder.is_dir() else []:
        try:
            item = load_bound('private-limit:' + path.stem, catalog)
        except (ValueError, OSError):
            continue
        out[item.reference] = item
    return out


def _by_model(review) -> str:
    """" by <model>, not a person" for a review a language model made (the owner, 2026-11-18), else ""."""
    from adroit.core.pricing import model_name
    return f' by {model_name(review.checked_by_model)}, not a person' if review.checked_by_model else ''


def _bound_review(item) -> str:
    """A bound limit's review state: whose review, with its validation and binding."""
    return (f'source checked{_by_model(item.review)}; validated and bound' if item.review.checked_by_model else
            'reviewed, validated and bound')


def _review_state(catalog, revision, bound: dict) -> str:
    """A draft's state: bound (a current binding of this revision), source-reviewed (a current review of one of its
    results; a model's says so), or a draft."""
    if any(item.revision == revision.reference for item in bound.values()):
        return 'bound'
    from adroit.constraints.experimental_review import current_review
    for result in revision.dossier.results:
        try:
            review = current_review(revision.reference, result.result_id, catalog)
            if review:
                return 'source checked' + _by_model(review) if review.checked_by_model else 'source reviewed'
        except (ValueError, OSError, KeyError):
            continue
    return 'draft'


def _searches(catalog) -> list[InventoryEntry]:
    from adroit.constraints.experimental_search_review import load_bound
    out = []
    folder = catalog.path('searches')
    for path in sorted(folder.glob('*.json')) if folder.is_dir() else []:
        try:
            item = load_bound('private-search:' + path.stem, catalog)
        except (ValueError, OSError, KeyError):
            continue
        out.append(InventoryEntry(reference='private-search:' + path.stem, kind='personal_search', library='personal',
                                  title=f'{item.revision} / {item.result_id}', constraint_class='direct_detection',
                                  review=_bound_review(item), origin=item.revision))
    return out


def _profiles(catalog) -> list[InventoryEntry]:
    out = []
    folder = catalog.path('profiles')
    for path in sorted(folder.glob('*.json')) if folder.is_dir() else []:
        try:
            raw = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        out.append(InventoryEntry(reference='profile:' + path.stem, kind='profile', library='personal',
                                  title=raw.get('name', path.stem), review='reviewed selection',
                                  origin=f"{len(raw.get('limits', []))} limits, {len(raw.get('null_modules', []))} nulls"))
    return out
