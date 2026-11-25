"""Model-driven constraint discovery: from a reviewed model to review-ready personal limit drafts (the owner's
request and handover, 2026-10-18; the constraint discovery build record of 2026-10-18).

A session lives in the personal experimental library under ``discovery/<id>/``, one file per stage, so a stopped or
failed run resumes where it stopped without repeating a paid request:

1. ``inventory.json`` ($0): the unified records index (``library.records_index``);
2. ``literature.json`` (network): deterministic arXiv queries from the model's summary and the abstracts found;
3. ``proposals.json`` (paid): the relevance agent's proposals (``agents.constraint_discovery``);
4. ``candidates.json`` ($0 apart from reference checks): vetted proposals, matched to the inventory by source
   identity and placed in one category each by code; then updated by
5. acquisition (network): the arXiv PDF at its exact version and HEPData tables whose record names the paper,
   imported as a draft revision of the experimental library (one per paper, for every result drawn from it), and
6. extraction (paid): the experimental library's own assisted extraction on that draft (one session per revision,
   with figure pages as images for an SI curve without a table when the session reads figures), every step under
   the session's one cap;
7. ``packets/`` ($0): a review packet per candidate.

The researcher then reviews, validates and binds with the existing commands; ``coverage`` freezes the assessment
for a run (``discovery:<id>@<hash>``), and ``qualify`` keeps an allowed point pending while a relevant constraint is
unresolved for that run. Nothing here signs, validates, binds, activates or excludes.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from adroit.core.checkpoint import atomic_json, run_lock
from adroit.core.chronology import utc_now
from adroit.core.constraint_discovery import (STAGES, Acquisition, Candidate, Decision, DiscoveryCoverage, InventoryEntry, ModelDomain, Requirement, ResultIdentity)
from adroit.core.dm_state import Applicability, ConstraintClass
from adroit.core.evidence import content_hash
from adroit.core.model_spec import ModelSpec
from adroit.core.state import StrictModel
from adroit.library.experimental import ExperimentalCatalog, TOKEN
from adroit.library.personal import Catalog
from adroit.orchestrator.model_intake import Intake

BENCHMARKS = {'si_isoscalar_curve': ('elastic_contact_O1_cp_equals_cn', 'sigma_nucleon_cm2', 'cm2', 3),
              'sm_higgs_invisible': ('SM_higgs_125_production', 'BR_h_invisible', 'dimensionless', 1)}
UNRESOLVED = ('existing_needs_review', 'missing_supported', 'needs_new_machinery', 'uncertain')
STAGE_ORDER = ('inventory', 'search', 'relevance', 'assessment', 'acquisition', 'extraction', 'packets')
UNCHECKED = 'its reference could not be checked (network); kept pending, and a resume checks it again'
PER_QUERY = 5
MAX_QUERIES = 10
MULTIPLETS = {(2, 0.5): 'higgsino', (3, 0.0): 'wino', (5, 0.0): 'minimal dark matter'}   # (SU(2) dimension, |Y|)
SUPERSEDABLE = ('missing_supported', 'needs_new_machinery', 'uncertain', 'existing_needs_review')
FIGURE_PAGES = 3                              # the most pages of one paper sent as images for a curve
CAPTION = re.compile(r'(?m)^\s*(FIG\.|Fig\.|Figure|FIGURE)\s*\d+')
SI_QUANTITY = re.compile(r'(?i)spin[- ]independent|WIMP[- ]nucleon|(?:dark matter|DM)[- ]nucleon|nucleon cross[- ]section')
LIMIT_WORDS = re.compile(r'(?i)\blimits?\b|\bexclu|\bupper\b|\bC\.\s?L\.')


class Options(StrictModel):
    """A session's settings, fixed when it starts."""
    model: str = 'claude-opus-5-5'
    budget: float = 0.0
    domain: dict[str, tuple[float, float]] = {}
    refresh: bool = False
    max_acquisitions: int = 4
    vision: bool = False


class Session(StrictModel):
    """A discovery session's fixed inputs: the pinned model and its summary, the options and its budget session (the
    same identifier: one cap for the relevance request and every extraction step)."""
    session_id: str
    created_at: str
    model_reference: str
    spec: ModelSpec
    domain: ModelDomain
    options: Options
    integrity_sha256: str = ''


# The model's deterministic summary and the public queries ------------------------------------------------------

def summary(spec: ModelSpec, reference: str, domain: dict[str, tuple[float, float]] | None = None) -> ModelDomain:
    """The model as discovery reads it, from the canonical model alone: its particles, the Standard Model fields its
    terms reach, their Lorentz structures, the engine it maps to, and, at its own reference point, whether its
    direct detection is an elastic isoscalar contact interaction (an adapter's reason to retrieve, never a decision
    that a limit applies). Unknown masses stay unknown."""
    from adroit.orchestrator.model_approval import model_identity
    dark = [f for f in spec.fields if f.role.value == 'dark_matter']
    mediators = [f for f in spec.fields if f.role.value == 'mediator']
    sm = {f.name for f in spec.fields if f.role.value == 'standard_model'}
    dark_names = {f.name for f in spec.fields if f.role.value != 'standard_model'}
    couples = sorted({o.field for t in spec.terms if any(o.field in dark_names for o in t.fields)
                      for o in t.fields if o.field in sm})
    unknowns = [f'mass of {f.name}' for f in [*dark, *mediators] if f.mass_gev is None]
    out = ModelDomain(model_reference=reference, model_sha256=model_identity(spec), name=spec.name,
                      dark_matter={'name': dark[0].name, 'spin': dark[0].spin, 'self_conjugate': dark[0].self_conjugate,
                                   'mass_gev': dark[0].mass_gev, 'su2': dark[0].charges.su2,
                                   'hypercharge': dark[0].charges.hypercharge} if dark else {},
                      mediators=[{'name': f.name, 'spin': f.spin, 'mass_gev': f.mass_gev} for f in mediators],
                      couples_to=couples, interactions=sorted({t.lorentz for t in spec.terms}),
                      has_completion=bool(spec.terms), domain=dict(domain or {}), unknowns=unknowns)
    return _engine(spec, out)


def _engine(spec: ModelSpec, out: ModelDomain) -> ModelDomain:
    from adroit.parameter_space.classify import Unsupported, classify
    from adroit.parameter_space.portals.higgs import HiggsPortalFermion, HiggsPortalScalar, HiggsPortalVector
    try:
        cls, point, _ = classify(spec)
    except (Unsupported, ValueError, ArithmeticError) as error:
        return out.model_copy(update={'engine': f'not computed: {error}',
                                      'unknowns': out.unknowns + ['the direct-detection interaction']})
    update = {'engine': type(cls).__name__,
              'higgs_portal': isinstance(cls, (HiggsPortalScalar, HiggsPortalFermion, HiggsPortalVector))}
    try:
        kind, _ = cls.dd(point)
        active = [q for q in cls.interaction(point).coefficients if q.proton != 0 or q.neutron != 0]
        isoscalar = kind == 'SI' and active and all(
            q.operator == 1 and not q.depends_on_q and math.isclose(q.proton, q.neutron, rel_tol=1e-10)
            for q in active)
        update['direct_detection'] = 'elastic_isoscalar_O1' if isoscalar else 'other'
    except (ValueError, RuntimeError, ArithmeticError, AttributeError) as error:
        update['unknowns'] = out.unknowns + [f'the direct-detection interaction ({error})']
    return out.model_copy(update=update)


def _abs(*phrases: str) -> str:
    return ' AND '.join(f'abs:"{p}"' for p in phrases)


def _multiplet(d: ModelDomain) -> list[str]:
    """The leading searches for dark matter in an electroweak multiplet (SU(2) dimension ≥ 2): gamma-ray lines, the
    multiplet by its name, disappearing tracks and continuum gamma rays from the inner Galaxy. The live test of
    2026-10-18 found the generic queries missed the line searches that papers on such multiplets lead with."""
    n = d.dark_matter.get('su2') or 1
    if n < 2:
        return []
    name = MULTIPLETS.get((n, abs(d.dark_matter.get('hypercharge') or 0.0)), 'electroweak multiplet')
    return [_abs('dark matter', 'gamma-ray line'), _abs(name) if 'dark matter' in name else _abs(name, 'dark matter'),
            _abs('disappearing track'), _abs('dark matter', 'inner Galaxy', 'gamma-ray')]


def queries(d: ModelDomain) -> list[str]:
    """Public arXiv queries from physics terms only (no model file, name or path): for an electroweak multiplet its
    leading searches first (``_multiplet``), then direct detection of its kind, the collider and indirect channels its
    couplings open, light-mass and invisible-Higgs searches where they apply."""
    spin = d.dark_matter.get('spin')
    kind = {0: 'scalar dark matter', 0.5: 'Majorana dark matter' if d.dark_matter.get('self_conjugate')
            else 'Dirac dark matter', 1: 'vector dark matter'}.get(spin, 'dark matter')
    mass = d.dark_matter.get('mass_gev')
    low = (d.domain.get('m_chi') or (mass, mass))[0]
    quarks = any(name.lower().startswith(('u', 'd', 'q', 's', 'c', 'b', 't', 'g')) for name in d.couples_to)
    leptons = any(name.lower().startswith(('e', 'l', 'mu', 'tau', 'nu')) for name in d.couples_to)
    out = [*_multiplet(d), _abs(kind, 'direct detection')]
    out.append(_abs('dark matter', 'spin-independent', 'limit') if d.direct_detection == 'elastic_isoscalar_O1'
               else _abs('dark matter', 'spin-dependent', 'limit'))
    if low is not None and low < 10:
        out.append(_abs('light dark matter', 'direct detection'))
    if d.higgs_portal:
        out.append(_abs('invisible', 'Higgs boson', 'search'))
    for m in d.mediators:
        word = {0: 'scalar mediator', 1: "Z'", 0.5: 'fermion mediator'}.get(m.get('spin'), 'mediator')
        if quarks:
            out.append(_abs('dark matter', word, 'LHC'))
        if leptons:
            out.append(_abs('dark matter', word, 'lepton'))
        if m.get('mass_gev') is not None and m['mass_gev'] < 1:
            out.append(_abs(word if word != "Z'" else 'dark photon', 'beam dump'))
    if d.has_completion:
        out.append(_abs('dark matter', 'annihilation', 'dwarf galaxies'))
    return list(dict.fromkeys(out))[:MAX_QUERIES]


# Categories (decided by code) ----------------------------------------------------------------------------------

def _source(reference) -> str:
    return ('arxiv:' if reference.kind == 'arxiv' else 'doi:') + reference.id.lower()


def _covers(entry: dict, wanted: dict) -> bool:
    """Whether an existing entry's declared mass range covers the requested one (unknown on either side: yes, since
    the adapter then checks each point)."""
    have, need = entry.get('mass_range'), wanted.get('m_chi')
    return not have or not need or (have[0] <= need[0] and need[1] <= have[1])


def adapter_for(proposal, d: ModelDomain) -> str:
    """The existing adapter that could compute this result for this model, or '' (the agent never chooses one)."""
    text = f'{proposal.name} {proposal.bound} {proposal.title}'.lower()
    if proposal.constraint_class is ConstraintClass.direct_detection and d.direct_detection == 'elastic_isoscalar_O1':
        return 'si_isoscalar_curve'
    if d.higgs_portal and 'invisible' in text and 'higgs' in text:
        return 'sm_higgs_invisible'
    return ''


QUANTITIES = (('higgs_invisible', re.compile(r'invisible', re.I), re.compile(r'higgs|\bh\b|h\s*→|h\s*->', re.I)),
              ('z_invisible', re.compile(r'invisible', re.I), re.compile(r'\bZ\b', re.I)),
              ('spin_dependent', re.compile(r'spin[- ]dependent|\bSD\b', re.I), None),
              ('spin_independent', re.compile(r'spin[- ]independent|\bSI\b|(?:WIMP|DM|dark matter)[- ]nucleon|direct[- ]detection likelihood', re.I), None),
              ('gamma_line', re.compile(r'line|γγ|gamma[- ]?gamma', re.I), None),
              ('antiproton', re.compile(r'antiproton|p̄|pbar', re.I), None))


def quantity_kind(text: str) -> str:
    """A bounded quantity's kind, from how it is written ('' if none is recognised)."""
    for kind, first, second in QUANTITIES:
        if first.search(text or '') and (second is None or second.search(text or '')):
            return kind
    return ''


def _tokens(text: str) -> set[str]:
    return set(re.findall(r'[a-z0-9]+', (text or '').lower()))


def _several(text: str) -> bool:
    """Whether a channel or dataset names a combination of several."""
    return bool(re.search(r'combin|\+|&|,|\band\b', text or '', re.I))


def compatible(want: ResultIdentity, have: ResultIdentity, module: bool = False) -> str:
    """'' if a held result's stated identity matches the wanted one positively, else why not (the fresh audit's
    F19-01: absence of a detected difference is not identity). The quantity's kind, the selection and the confidence
    level must be stated on both sides and agree (an experiment module computes at any confidence level); a held
    benchmark must be the wanted one; a channel, dataset or panel the wanted result states must be stated by the held
    one and agree, a combination never matching a single channel or dataset."""
    kind = quantity_kind(want.quantity)
    kinds = {'spin_independent', 'spin_dependent'} if module else {quantity_kind(have.quantity)}
    if not kind or kind not in kinds:
        return (f'another quantity ({have.quantity or "unstated"})' if kind and quantity_kind(have.quantity)
                else 'the quantity is not stated as one the held entry bounds')
    if not want.selection or want.selection != (have.selection or 'observed'):
        return 'observed or expected is not stated, or differs'
    if not module and (want.confidence_level is None or have.confidence_level is None
                       or abs(want.confidence_level - have.confidence_level) > 1e-9):
        return 'the confidence level is not stated on both sides, or differs'
    if have.benchmark and _tokens(have.benchmark) != _tokens(want.benchmark):
        return f'the held entry holds for its {have.benchmark} benchmark only'
    for field in ('channel', 'dataset', 'panel'):
        wanted, held = getattr(want, field), getattr(have, field)
        if not wanted:
            continue
        if not held:
            return f'its {field} ({wanted}) is not stated by the held entry'
        if _several(wanted) != _several(held) or not (_tokens(wanted) <= _tokens(held) or _tokens(held) <= _tokens(wanted)):
            return f'another {field} ({held} held, {wanted} wanted)'
    return ''


def same_result(proposal, vetted, entry: InventoryEntry, adapter: str) -> str:
    """'' if a held entry of the same paper is positively shown to be this proposal's result, else why it is not (the
    stacked audit's S18-05 and the fresh audit's F19-01: a publication identifier locates assets, it does not establish
    coverage, and unknown identity stays unresolved). Shown means: the proposal applies as it stands, its relevance is
    certain, the relevance step named this entry as the result (``held_as``), the constraint class is the same, a
    personal limit is bound for the same adapter, and ``compatible`` holds."""
    if vetted.proposal.applicability == Applicability.needs_calculation:
        return 'it needs a calculation the held entry does not supply'
    if proposal.uncertain:
        return 'its relevance is uncertain'
    if proposal.held_as != entry.reference:
        return 'the relevance step did not identify it as this result'
    if entry.constraint_class and entry.constraint_class != proposal.constraint_class.value:
        return 'the held entry is another kind of constraint'
    if entry.kind == 'personal_limit' and entry.adapter != adapter:
        return 'the bound limit is for another adapter'
    return compatible(proposal.result, entry.result, module=entry.kind == 'experiment_module')


def categorise(proposal, vetted, inventory: list[InventoryEntry], d: ModelDomain) -> dict:
    """A kept proposal's category, adapter, what is missing, the inventory entries with its source (``matches``,
    assets only) and the bound limits shown to be this result (``resolvers``, F19-02). A proposal that needs a
    calculation is never covered by a held entry (F19-01); a personal limit or a standard entry counts only when
    ``same_result`` shows it is this result, and a bound limit stays a requirement until a run selects it."""
    source = _source(vetted.reference)
    matches = [e for e in inventory if source in e.source_ids]
    refs = [e.reference for e in matches]
    adapter = adapter_for(proposal, d)
    drafts = [e for e in matches if e.kind == 'personal_revision']
    if proposal.inapplicable:
        return dict(category='inapplicable', matches=refs, missing=proposal.inapplicable)
    reasons = {e.reference: same_result(proposal, vetted, e, adapter)
               for e in matches if e.kind == 'personal_limit' or e.library == 'standard'}
    resolvers = [e for e in matches if e.kind == 'personal_limit' and not reasons[e.reference]]
    if resolvers:
        covered = [e for e in resolvers if _covers(e.domain, d.domain)]
        return dict(category='existing_applicable' if covered else 'existing_outside_domain', matches=refs,
                    adapter=adapter, resolvers=[e.reference for e in resolvers],
                    missing='a bound personal limit holds it; a run must select it' if covered else
                    "the bound limit's mass range covers only part of the requested domain")
    if any(not why for ref, why in reasons.items() if not ref.startswith('private-limit:')):
        return dict(category='existing_applicable', matches=refs)
    held = '; '.join(f'{ref} is of the same paper, but {why}' for ref, why in reasons.items())
    def missing(text: str) -> str:
        return '; '.join(x for x in (text, held) if x)
    if drafts:
        return dict(category='existing_needs_review', matches=refs, adapter=adapter,
                    missing=missing('a personal draft holds this source: review, validate and bind it'))
    if proposal.uncertain:
        return dict(category='uncertain', matches=refs, missing=missing('relevance or numerical content unresolved'))
    if adapter and vetted.proposal.applicability != Applicability.needs_calculation:
        return dict(category='missing_supported', matches=refs, adapter=adapter, missing=held)
    return dict(category='needs_new_machinery', matches=refs,
                missing=missing(vetted.proposal.needed_calculation or
                                f'a deterministic {proposal.constraint_class.value} adapter for this result (none exists)'))


def _identity(text: str) -> str:
    """An identifier as written (arXiv:2207.03764v2, 2207.03764, doi:…, an inventory reference), normalised."""
    key = text.strip().lower().removeprefix('arxiv:').removeprefix('doi:')
    return re.sub(r'^(\d{4}\.\d{4,5})v\d+$', r'\1', key)


def _unlike(c: Candidate, constraint_class: str, result: ResultIdentity) -> str:
    """Why a named newer result cannot replace this one ('' if it can): another constraint class, or a bounded
    quantity of another kind or unstated on either side (the fresh audit's F19-03)."""
    if constraint_class and constraint_class != c.constraint_class:
        return f'it is another kind of constraint ({constraint_class})'
    kind, other = quantity_kind(c.result.quantity), quantity_kind(result.quantity)
    if not kind or not other:
        return 'the bounded quantity is not stated on both sides'
    return '' if kind == other else f'it bounds another quantity ({result.quantity})'


def supersession(candidates: list[Candidate], marks: dict[str, str], inventory: list[InventoryEntry]) -> list[Candidate]:
    """The candidates with the relevance step's superseded marks (``marks``: candidate → the newer result it named)
    checked by code (the live test's item 8; the fresh audit's F19-03): the newer result must be held (an inventory
    entry, by identifier) or another kept candidate, of the same constraint class and bounding the same kind of
    quantity, and must cover the older one's declared mass range when both declare one; the older is then
    ``superseded``: not retrieved and not extracted, and in the pin a requirement until a researcher confirms it
    (``Discovery._superseded``). A mark that fails a check is noted and ignored; of two candidates naming each other,
    the first named is the superseded one."""
    rank = {'standard_record': 0, 'personal_limit': 1}
    held: dict[str, list[InventoryEntry]] = {}
    for e in inventory:
        for key in {_identity(e.reference), *map(_identity, e.source_ids)}:
            held.setdefault(key, []).append(e)
    proposed = {_identity(c.reference): c for c in candidates}
    out: list[Candidate] = []
    for c in candidates:
        mark = marks.get(c.candidate_id, '')
        if not mark or c.category not in SUPERSEDABLE or c.missing == UNCHECKED:
            out.append(c)
            continue
        key, newer, unlike = _identity(mark), None, ''
        other = proposed.get(key)
        if other is not None and other.candidate_id != c.candidate_id:
            if not any(o.superseded_by == f'candidate:{c.candidate_id}' for o in out):
                newer = (f'candidate:{other.candidate_id}', f'{other.name} ({other.reference})', other.domain.get('m_chi'))
                unlike = _unlike(c, other.constraint_class, other.result)
        elif key in held:
            e = min(held[key], key=lambda e: rank.get(e.kind, 9))
            newer = (e.reference, f'{e.title} ({e.reference})', e.domain.get('mass_range'))
            unlike = _unlike(c, e.constraint_class, e.result)
        own = c.domain.get('m_chi')
        if newer is None:
            note = f'named as superseded by {mark}, which is neither held nor proposed; kept as a result in its own right'
        elif unlike:
            note = f'named as superseded by {newer[1]}, but {unlike}; kept as a result in its own right'
        elif own and newer[2] and not (newer[2][0] <= own[0] and own[1] <= newer[2][1]):
            note = (f'named as superseded by {newer[1]}, which covers m_chi = {newer[2][0]:g}–{newer[2][1]:g} GeV, not '
                    f'all of its {own[0]:g}–{own[1]:g} GeV; kept as a result in its own right')
        else:
            out.append(c.model_copy(update={'category': 'superseded', 'superseded_by': newer[0],
                                            'missing': f'proposed as superseded by {newer[1]} (the relevance step\'s '
                                                       'judgement, checked by class, quantity and mass range; a '
                                                       'researcher confirms it)'}))
            continue
        out.append(c.model_copy(update={'missing': '; '.join(x for x in (c.missing, note) if x)}))
    return out


REFERENCES = re.compile(r'(?m)^\s*(References|REFERENCES|Bibliography|BIBLIOGRAPHY)\s*$')
KEPT_BACK_MATTER = re.compile(r'(?m)^\s*(Appendix|APPENDIX|Supplemental [Mm]aterial|SUPPLEMENTAL MATERIAL)\b'
                              r'|^\s*(Table|TABLE)\s+[IVX\d]+[.:]')


def body_units(units) -> list[str]:
    """The source units an extraction reads: every data unit, and each PDF's pages up to the one where its reference
    list begins (a "References" heading on its own line), plus any later page with an appendix heading or a table
    caption. Reference and author lists are left out (the live pilot spent a quarter of its extraction on them); a
    PDF without such a heading is read whole. The scope still lists every unit, so nothing disappears unrecorded."""
    first: dict[str, int] = {}
    for u in units:
        if u.page is not None and REFERENCES.search(u.text):
            first[u.asset_sha256] = min(first.get(u.asset_sha256, u.page), u.page)
    return [u.unit_id for u in units if u.page is None or u.asset_sha256 not in first
            or u.page <= first[u.asset_sha256] or KEPT_BACK_MATTER.search(u.text)]


def unread_pages(scope) -> list[str]:
    """The pages of each source an extraction scope left out, as "file: pages a–b, c"."""
    chosen = {i for batch in scope.batches for i in batch}
    out: dict[str, list[int]] = {}
    for u in scope.units:
        if u.unit_id not in chosen and u.page is not None:
            out.setdefault(u.source_name or u.asset_sha256[:12], []).append(u.page)
    def ranges(pages: list[int]) -> str:
        pages, parts, start = sorted(set(pages)), [], None
        for i, p in enumerate(pages):
            start = p if start is None else start
            if i + 1 == len(pages) or pages[i + 1] != p + 1:
                parts.append(f'{start}' if start == p else f'{start}–{p}')
                start = None
        return ', '.join(parts)
    return [f'{name}: pages {ranges(pages)}' for name, pages in out.items()]


def figure_pages(units, selected: list[str], adapters: set[str]) -> list[str]:
    """The PDF pages sent as images for a curve limit (``--vision``; the live test's item 4): among the pages read,
    those whose text holds a figure caption, the SI quantity and a limit, at most ``FIGURE_PAGES`` per paper, the most
    explicit first. None when no adapter's limit is a curve (a branching-ratio bound is printed)."""
    if 'si_isoscalar_curve' not in adapters:
        return []
    chosen, ranked = set(selected), {}
    for u in units:
        if u.unit_id not in chosen or u.page is None or (':part:' in u.unit_id and not u.unit_id.endswith(':part:0')):
            continue
        if CAPTION.search(u.text) and SI_QUANTITY.search(u.text) and LIMIT_WORDS.search(u.text):
            score = len(SI_QUANTITY.findall(u.text)) + len(LIMIT_WORDS.findall(u.text))
            ranked.setdefault(u.asset_sha256, []).append((-score, u.page, u.unit_id))
    return [unit for rows in ranked.values() for _, _, unit in sorted(rows)[:FIGURE_PAGES]]


def viewed(scope) -> list[int]:
    """The PDF pages an extraction scope sends as images."""
    chosen = {i for batch in scope.batches for i in batch}
    return sorted({u.page for u in scope.units if u.vision and u.page is not None and u.unit_id in chosen})


def _target(c: Candidate) -> str:
    benchmark, quantity, units, anchors = BENCHMARKS[c.adapter]
    shape = ('points [[mass_GeV, value], …] in increasing mass, mass_range [low, high] inside them, x_scale and y_scale, '
             'and halo {rho_gev_cm3, v0_km_s, v_earth_km_s, v_esc_km_s}' if c.adapter == 'si_isoscalar_curve'
             else 'value (the branching-ratio bound)')
    return (f'the published limit "{c.name}" ({c.reference}), in one result with result_id "{c.result_id}" and kind '
            f'"limit": its limit_contract has adapter "{c.adapter}", benchmark "{benchmark}", quantity "{quantity}", '
            f'units "{units}" and {shape}; its validation_reference: every anchor the sources print (the ordinary '
            f'validation needs {anchors}; give fewer if that is all there is: a curve digitised from a figure with '
            'fewer is verified by hand)')


def extraction_instruction(targets: Candidate | list[Candidate], pages: list[int] = ()) -> str:
    """What the extraction agent is asked for: each target result (every candidate drawn from the revision; the
    rerun's finding) with its adapter's contract and independent anchors, only where the sources state them (the
    extraction checks every value against its cited evidence); with ``pages`` sent as images, how to transcribe a
    curve from a figure."""
    targets = [targets] if isinstance(targets, Candidate) else list(targets)
    head = (f'Discovery target: {_target(targets[0])}.' if len(targets) == 1 else 'Discovery targets, each in its own '
            'result:\n' + '\n'.join(f'{i}. {_target(c)};' for i, c in enumerate(targets, 1)))
    rule = (' For each target, if, and only if, the selected sources state them, give two claims of category limit: '
            'limit_contract, an object with the adapter, benchmark, quantity and units above, confidence_level, '
            'construction, selection (observed or expected), dataset_id, datasets (for a combined result, its '
            'constituent datasets by name; [] for one), overlap ("unknown" unless the paper states it), supersedes '
            '[], the fields above, origin (machine_table, printed_scalar or figure_digitised; a digitised figure also '
            'needs x_relative_error and y_relative_error), assumptions and source_panel (the table, figure or '
            'panel); and validation_reference, {"points": [[x, y], …], "lineage": [for each point, either '
            '{"derivation": "printed_text", "document": the file name, "page": its page} or {"derivation": '
            '"published_table", "document": the file name, "row": the row (from 1), "mass_column", "limit_column": '
            'the two columns\' headers as printed}], "result": {"selection", "confidence_level", '
            '"dataset_id", "benchmark"} (the result the anchors state, as in the limit_contract)}: anchors the '
            "authors printed or tabulated, from a different source file than the limit_contract's, or, for a curve "
            "digitised from a figure, quoted from the paper's own text, each anchor in its own sentence that gives "
            'the mass with its unit and the limit with its unit, with its page (method text, one locator per anchor); '
            'never a value read from a figure, its axis labels or ticks, or a digitisation or re-export of the curve. '
            'Copy published values only; leave anything not stated unextracted and list it.')
    figures = '' if not pages else (
        f' Pages {", ".join(map(str, pages))} are also attached as images, because a figure there may hold a limit '
        'curve. Only if a curve is printed in no table or text, transcribe it from its figure: origin '
        'figure_digitised, points read along the drawn curve, each locator with method visual, the page and the '
        "figure's region in PDF points, figure_axes {\"asset_sha256\", \"page\", \"frame\": [left, top, right, "
        'bottom] of the plotting frame as fractions of the page image from its top left, "x_range" and "y_range": '
        "[low, high] at the frame's edges as labelled}, and x_relative_error and y_relative_error as your honest "
        'reading precision. Do not put printed values into the digitised points: they are its validation anchors.')
    return head + rule + figures


# The coordinator -----------------------------------------------------------------------------------------------

class Discovery:
    """Sessions of model-driven constraint discovery in the personal experimental library."""

    def __init__(self, catalog: ExperimentalCatalog | None = None, models: Catalog | None = None, *,
                 abstracts=None, fetch=None, resolver=None):
        from adroit.orchestrator.experimental_extraction import ExperimentalExtraction
        self.catalog = catalog or ExperimentalCatalog()
        self.models = models
        self.extraction = ExperimentalExtraction(self.catalog)
        self.budgets: Intake = self.extraction.budgets
        self.abstracts, self.fetch, self.resolver = abstracts, fetch, resolver

    # sessions ---------------------------------------------------------------------------------------------------
    def folder(self, session_id: str) -> Path:
        """A session's folder (the identifier must be a valid token)."""
        if not TOKEN.fullmatch(session_id):
            raise ValueError('invalid discovery session identifier')
        return self.catalog.path(f'discovery/{session_id}')

    def resolve(self, model: str) -> tuple[str, ModelSpec]:
        """(pinned reference, model) for a personal model revision (``catalog:…``) or a typed model file (pinned by
        its content hash as ``file:<sha256>``)."""
        if model.startswith('catalog:'):
            return model, (self.models or Catalog()).load(model).spec
        import yaml
        from adroit.orchestrator.model_approval import model_identity, read_model
        path = Path(model)
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in ('.yaml', '.yml'):
            raise ValueError('give a personal model revision (catalog:…) or a typed model YAML file')
        spec = read_model(yaml.safe_load(path.read_text()))
        return 'file:' + model_identity(spec), spec

    def start(self, model: str, options: Options) -> Session:
        """Open a session for a pinned model: its budget session (the cap, at most $10) and its fixed inputs. $0."""
        reference, spec = self.resolve(model)
        if options.vision and options.model.startswith('gpt-'):
            raise ValueError('reading figures (--vision) needs an Anthropic model')
        budget = self.budgets.start(options.budget, options.model)
        s = Session(session_id=budget.session_id, created_at=utc_now(), model_reference=reference, spec=spec,
                    domain=summary(spec, reference, options.domain), options=options)
        s.integrity_sha256 = content_hash(s.model_dump(mode='json', exclude={'integrity_sha256'}))
        atomic_json(self.folder(s.session_id) / 'session.json', s.model_dump(mode='json'))
        return s

    def session(self, session_id: str) -> Session:
        """A session's fixed inputs, checked against their integrity hash."""
        raw = json.loads((self.folder(session_id) / 'session.json').read_text())
        s = Session.model_validate(raw)
        if s.session_id != session_id or content_hash({k: v for k, v in raw.items() if k != 'integrity_sha256'}) != s.integrity_sha256:
            raise ValueError('discovery session inputs were modified; start a new session')
        return s

    def _read(self, session_id: str, name: str):
        path = self.folder(session_id) / name
        return json.loads(path.read_text()) if path.exists() else None

    def _write(self, session_id: str, name: str, value) -> None:
        atomic_json(self.folder(session_id) / name, value)

    def _stage(self, session_id: str, name: str, status: str, detail: str = '') -> None:
        state = self._read(session_id, 'state.json') or {}
        state[name] = {'status': status, 'at': utc_now(), 'detail': detail}
        self._write(session_id, 'state.json', state)

    # running ----------------------------------------------------------------------------------------------------
    def run(self, session_id: str, llm=None) -> dict:
        """Every unfinished stage in order; a budget stop leaves the rest resumable. Retrievals that failed for a
        transient reason leave acquisition "incomplete" (the later stages still run on what was retrieved), and a
        resume retries them; once acquisition or extraction runs again, the stages after it run again too, so new
        drafts are read and packed. Nothing already paid for is sent again: a relevance answer is recovered
        (``_recovered``) and a batch already read is skipped. Returns the stage states."""
        from adroit.agents.budget import BudgetExceeded
        s = self.session(session_id)
        with run_lock(self.folder(session_id)):
            again = False
            try:
                for name, step in (('inventory', self._inventory), ('search', self._search),
                                   ('relevance', lambda x: self._relevance(x, llm)), ('assessment', self._assess),
                                   ('acquisition', self._acquire), ('extraction', lambda x: self._extract(x, llm)),
                                   ('packets', self._packets)):
                    if (self._read(session_id, 'state.json') or {}).get(name, {}).get('status') == 'done' and not again:
                        continue
                    self._stage(session_id, name, 'running')
                    detail = step(s) or ''
                    retry = self._unfinished(session_id, name)
                    self._stage(session_id, name, 'incomplete' if retry else 'done',
                                detail + (f'; {retry}' if retry else ''))
                    again = again or name in ('assessment', 'acquisition', 'extraction')
            except BudgetExceeded as error:
                self._stage(session_id, name, 'stopped', f'budget: {error}')
            except (ValueError, OSError, RuntimeError) as error:
                self._stage(session_id, name, 'failed', str(error))
        return self._read(session_id, 'state.json')

    def _unfinished(self, session_id: str, stage: str) -> str:
        """Why a stage that ran is incomplete (a network failure a resume retries), or ''."""
        candidates = self.candidates(session_id) if stage in ('assessment', 'acquisition') else []
        if stage == 'assessment' and any(c.missing == UNCHECKED for c in candidates):
            return 'a resume checks the references that could not be checked'
        if stage == 'acquisition' and any(c.acquisition.status == 'retryable' for c in candidates):
            return 'a resume retries the retrievals that failed in transit'
        return ''

    def _inventory(self, s: Session) -> str:
        from adroit.library.records_index import index
        entries = index(self.catalog)
        self._write(s.session_id, 'inventory.json', [e.model_dump(mode='json') for e in entries])
        return f'{len(entries)} entries'

    def inventory(self, session_id: str) -> list[InventoryEntry]:
        """The inventory as the session recorded it."""
        return [InventoryEntry.model_validate(e) for e in self._read(session_id, 'inventory.json') or []]

    def _search(self, s: Session) -> str:
        """The queries' abstracts, snapshotted in the session; the shared literature cache is read unless the
        session asked for a refresh, and is never rewritten here."""
        from adroit.core.config import get_settings
        from adroit.retrieval.literature import fetch_arxiv_abstracts
        shared_path = get_settings().data_dir / 'literature_cache.json'
        shared = json.loads(shared_path.read_text()) if shared_path.exists() and not s.options.refresh else {}
        found, gaps = {}, []
        for q in queries(s.domain):
            try:
                rows = shared.get(q) or [a.model_dump() for a in (self.abstracts or fetch_arxiv_abstracts)(q, PER_QUERY)]
            except Exception as error:          # noqa: BLE001 - a failed search is a named gap, never a silent absence
                gaps.append(f'search failed for {q}: {type(error).__name__}: {error}')
                continue
            found[q] = rows
        self._write(s.session_id, 'literature.json', {'searched_at': utc_now(), 'refresh': s.options.refresh,
                                                     'per_query': PER_QUERY, 'queries': found, 'gaps': gaps,
                                                     'limits': f'at most {MAX_QUERIES} queries of {PER_QUERY} '
                                                               'abstracts each; arXiv abstracts only'})
        if gaps and not found:              # nothing to read: stop before the paid request, and search again on resume
            raise OSError(f'every arXiv search failed ({gaps[0]}); nothing was sent to the provider, and a resume '
                          'searches again')
        return f'{len(found)} queries, {sum(map(len, found.values()))} abstracts, {len(gaps)} failed'

    def _relevance(self, s: Session, llm) -> str:
        from adroit.agents.constraint_discovery import DiscoveryScout
        from adroit.retrieval.literature import Abstract
        literature = self._read(s.session_id, 'literature.json')
        abstracts = list({a['arxiv_id']: Abstract.model_validate(a) for rows in literature['queries'].values()
                          for a in rows}.values())
        recovered = self._recovered(s)
        if recovered is not None:
            self._write(s.session_id, 'proposals.json', recovered.model_dump(mode='json'))
            return f'{len(recovered.proposals)} proposals (recovered; not sent again)'
        with run_lock(self.budgets.folder(s.session_id)):
            client = self._client(s, llm)
            report = DiscoveryScout(client, s.options.model).run(s.domain, self.inventory(s.session_id), abstracts)
        self._write(s.session_id, 'proposals.json', report.model_dump(mode='json'))
        return f'{len(report.proposals)} proposals'

    def _recovered(self, s: Session):
        """A relevance answer already paid for: the saved proposals, or else the last answer in the session's paid
        journal that parses as a report (the relevance request is a session's first paid request, so every answer
        journalled before any extraction is one of its attempts). None if there is none."""
        from adroit.agents.constraint_discovery import DiscoveryReport
        from adroit.agents.llm import _extract_json, journalled_text
        saved = self._read(s.session_id, 'proposals.json')
        if saved is not None:
            try:
                return DiscoveryReport.model_validate(saved)
            except ValueError:
                pass
        from adroit.agents.budget import ledger_text
        from adroit.core.durable import absent
        journal = self.budgets.folder(s.session_id) / 'paid.jsonl'
        if absent(journal) or self._read(s.session_id, 'candidates.json'):   # one that cannot be read raises (DN-01)
            return None
        for line in reversed(ledger_text(journal).splitlines()):
            row = json.loads(line) if line.strip() else {}
            text = journalled_text(row.get('response')) if row.get('state') == 'received' else ''   # either provider's
            if not text:                    # a reservation, a settlement or an uncertain charge (F19-05): look further
                continue
            try:
                return DiscoveryReport.model_validate_json(_extract_json(text))
            except ValueError:
                continue
        return None

    def _client(self, s: Session, llm):
        """The session's budgeted client: the only route to a provider (an injected client must be the offline
        fake)."""
        from adroit.agents.llm import BudgetedLLMClient, FakeLLMClient, client_for
        if llm is not None:
            if not isinstance(llm, FakeLLMClient):
                raise ValueError('live discovery must use the session budget')
            return llm
        budget = self.budgets.session(s.session_id)
        if budget.budget <= 0:
            raise ValueError('the relevance request needs an up-front session budget')
        llm = BudgetedLLMClient(client_for(s.options.model), account=self.budgets.account(budget),
                                ledger_path=self.budgets.folder(s.session_id) / 'paid.jsonl')
        self.budgets.clients.append(llm)            # its requests: the run's own (``RunRequests``), as an extraction's
        return llm

    def _assess(self, s: Session) -> str:
        from adroit.agents.constraint_discovery import DiscoveryReport
        from adroit.agents.scout import ProposedConstraint, ScoutReport
        from adroit.constraints import scouting
        from adroit.retrieval.references import ReferenceCache
        report = DiscoveryReport.model_validate(self._read(s.session_id, 'proposals.json'))
        base = ScoutReport(proposals=[ProposedConstraint.model_validate(p.model_dump(include=set(ProposedConstraint.model_fields)))
                                      for p in report.proposals])
        vetted = scouting.vet(base, s.domain.has_completion, self.resolver,
                              ReferenceCache(self.folder(s.session_id) / 'references.json'))
        inventory = self.inventory(s.session_id)
        previous = {c.candidate_id: c for c in self.candidates(s.session_id)}
        included = {d.candidate_id: d for d in self.decisions(s.session_id) if d.kind == 'included'}
        candidates, gaps, marks = [], [], {}
        for proposal, v in zip(report.proposals, vetted):
            unchecked = not v.kept and ': not checked: ' in v.reason      # the network, not the reference
            if not v.kept and not unchecked:
                gaps.append(f'{proposal.name}: not acquired, {v.reason}')
                continue
            reference = ('arXiv:' if v.reference.kind == 'arxiv' else 'doi:') + v.reference.id
            key = content_hash({'reference': reference.lower(), 'name': proposal.name})[:16]
            found = dict(category='uncertain', matches=[], missing=UNCHECKED) if unchecked else \
                categorise(proposal, v, inventory, s.domain)
            decision = included.get(content_hash({'reference': reference.lower(), 'name': proposal.name})[:16])
            if decision and found['category'] == 'uncertain' and adapter_for(proposal, s.domain):
                found = dict(category='missing_supported', matches=found.get('matches', []),   # a re-assessment
                             adapter=adapter_for(proposal, s.domain),                           # keeps an inclusion
                             missing=f'included by {decision.researcher}: {decision.reason}')
            c = Candidate(candidate_id=key, name=proposal.name, constraint_class=proposal.constraint_class.value,
                          reference=reference, title=v.reference.title or proposal.title, relevance=proposal.relevance,
                          applicability=v.proposal.applicability, assumptions=v.proposal.assumptions,
                          needed_calculation=v.proposal.needed_calculation, hepdata=proposal.hepdata,
                          tables=proposal.tables, domain=proposal.domain, result_id=f'discovery_{key[:8]}',
                          held_as=proposal.held_as, result=proposal.result, **found)
            old = previous.get(key)                 # a re-assessment keeps what was retrieved and read
            if old is not None:
                c = c.model_copy(update={'acquisition': old.acquisition, 'extraction_session': old.extraction_session,
                                         'draft': old.draft})
            if proposal.superseded_by:
                marks[key] = proposal.superseded_by
            candidates.append(c)
        candidates = supersession(candidates, marks, inventory)
        self._save_candidates(s.session_id, candidates)
        self._write(s.session_id, 'gaps.json', gaps)
        superseded = sum(c.category == 'superseded' for c in candidates)
        return f'{len(candidates)} kept' + (f' ({superseded} superseded)' if superseded else '') + f', {len(gaps)} dropped'

    def candidates(self, session_id: str) -> list[Candidate]:
        """The session's candidates as last written."""
        return [Candidate.model_validate(c) for c in self._read(session_id, 'candidates.json') or []]

    def _save_candidates(self, session_id: str, candidates: list[Candidate]) -> None:
        self._write(session_id, 'candidates.json', [c.model_dump(mode='json') for c in candidates])

    def _acquire(self, s: Session) -> str:
        """Retrieve the papers of the supported missing results, at most ``max_acquisitions`` papers per session
        (counted across resumes: a retrieval that failed still holds its place). The results of one paper are
        retrieved together into one revision (``_retrieve_paper``). A failure in transit (the network, a timeout, an
        HTTP error) is ``retryable`` and a resume tries it again; a refusal (another paper's title or record, no PDF,
        a table that does not parse) is ``failed`` and stays a named gap."""
        from adroit.retrieval import constraint_sources as cs
        candidates, attempted = self.candidates(s.session_id), 0
        used = {c.reference.lower() for c in candidates if c.acquisition.status in ('retrieved', 'failed', 'retryable')}
        papers: dict[str, list[int]] = {}
        for i, c in enumerate(candidates):
            if c.category == 'missing_supported' and c.acquisition.status not in ('retrieved', 'failed'):
                papers.setdefault(c.reference.lower(), []).append(i)
        for paper, members in papers.items():
            if paper not in used and len(used) >= s.options.max_acquisitions:
                for i in members:
                    candidates[i] = candidates[i].model_copy(update={'acquisition': Acquisition(
                        reason=f'not attempted: the session retrieves at most {s.options.max_acquisitions} papers')})
                continue
            used.add(paper)
            attempted += 1
            group = [candidates[i] for i in members]
            try:
                found = self._retrieve_paper(s, group, cs)
            except ValueError as error:
                found = {c.candidate_id: Acquisition(status='failed', reason=str(error)) for c in group}
            except OSError as error:            # requests' errors are OSErrors: the network, timeouts, HTTP status
                found = {c.candidate_id: Acquisition(status='retryable', reason=f'{type(error).__name__}: {error}')
                         for c in group}
            except Exception as error:          # noqa: BLE001 - anything else is a named gap, not assumed transient
                found = {c.candidate_id: Acquisition(status='failed', reason=f'{type(error).__name__}: {error}')
                         for c in group}
            for i in members:
                candidates[i] = candidates[i].model_copy(update={'acquisition': found[candidates[i].candidate_id]})
            self._save_candidates(s.session_id, candidates)
        self._save_candidates(s.session_id, candidates)
        return f'{attempted} papers attempted'

    @staticmethod
    def _tables(c: Candidate, arxiv: str, fetch, cs) -> tuple[list, list[dict], list[str]]:
        """The paper's HEPData tables for the candidate's adapter: those the proposal named in the record it named, or
        else, when it named none, at most three chosen by code from their names and descriptions in the paper's own
        record (found by its arXiv identifier; ``select_tables``). A named table that does not exist is never
        replaced by another; no record or no fitting table is a named gap."""
        import hashlib
        files, tables, notes = [], [], []
        record_id = c.hepdata
        if not record_id:
            try:
                record_id = cs.hepdata_find(arxiv, fetch)
            except cs.NoRecord as gap:
                return files, tables, [str(gap)]
        record = cs.hepdata_record(record_id, arxiv, fetch)
        named = [t for t in c.tables if t in record['tables']]
        chosen = named if c.tables else cs.select_tables(c.adapter, record['details'])   # never a substitute
        notes += [f'HEPData {record_id} has no table named {t!r}' for t in c.tables if t not in record['tables']]
        if chosen and not named:
            notes.append(f'HEPData {record_id}: tables chosen by their names and descriptions for {c.adapter}: '
                         + '; '.join(repr(t) for t in chosen))
        if not chosen:
            notes.append(f"HEPData {record_id}: no table names {c.adapter}'s quantity, so none was retrieved")
        for name in chosen[:4]:
            reply = cs.hepdata_table(record_id, name, record['version'], fetch)
            safe = ''.join(ch if ch.isalnum() else '_' for ch in name)[:60]
            files.append((reply, f'HEPData_{record_id}_v{record["version"]}_{safe}.yaml'))
            tables.append({'record': record_id, 'version': record['version'],
                           'doi': record['details'].get(name, {}).get('doi') or record['doi'], 'table': name,
                           'url': reply.url, 'sha256': hashlib.sha256(reply.data).hexdigest()})
        return files, tables, notes

    def _retrieve(self, s: Session, c: Candidate, cs) -> Acquisition:
        """One candidate's paper and tables (``_retrieve_paper`` for a group of one); a refusal raises."""
        found = self._retrieve_paper(s, [c], cs)[c.candidate_id]
        if found.status == 'failed':
            raise ValueError(found.reason)
        return found

    def _retrieve_paper(self, s: Session, group: list[Candidate], cs) -> dict[str, Acquisition]:
        """The paper at its exact version for every candidate drawn from it, with the union of the HEPData tables they
        need, imported as one draft revision; a revision already holding the paper and every requested table is
        reused, and a new one records those it extends (S18-12). Each candidate keeps its own tables and notes; one
        whose cited title is not the paper's, or whose named record is another paper's, fails alone. Every address is
        requested once."""
        from adroit.retrieval.references import same_title
        import hashlib
        network, replies = self.fetch or cs.network_fetch, {}

        def fetch(url: str):
            if url not in replies:
                replies[url] = network(url)
            return replies[url]
        if not group[0].reference.startswith('arXiv:'):
            raise ValueError('only arXiv papers are retrieved in this build; a DOI-only source stays a named gap')
        arxiv = group[0].reference.removeprefix('arXiv:')
        meta = cs.arxiv_metadata(arxiv, fetch)
        out: dict[str, Acquisition] = {}
        for c in group:
            if not same_title(c.title, meta['title']):
                out[c.candidate_id] = Acquisition(status='failed',
                                                  reason=f'arXiv:{arxiv} is titled {meta["title"]!r}, not {c.title!r}')
        kept = [c for c in group if c.candidate_id not in out]
        if not kept:
            return out
        pdf = cs.arxiv_pdf(arxiv, meta['version'], fetch)
        files, own = self._paper_files(kept, arxiv, meta, pdf, fetch, cs, out)
        kept = [c for c in kept if c.candidate_id in own]
        if not kept:
            return out
        digest = hashlib.sha256(pdf.data).hexdigest()
        revision = self._paper_revision(s, kept, own, files, arxiv, meta, digest)
        for c in kept:
            out[c.candidate_id] = Acquisition(status='retrieved', arxiv_id=arxiv, version=meta['version'],
                                              title=meta['title'], published=meta['published'], url=pdf.url,
                                              retrieved_at=utc_now(), sha256=digest, size_bytes=len(pdf.data),
                                              hepdata=own[c.candidate_id][0], licence=meta['licence'],
                                              revision=revision.reference, reason='; '.join(own[c.candidate_id][1]))
        return out

    def _paper_files(self, kept: list[Candidate], arxiv: str, meta: dict, pdf, fetch, cs,
                     out: dict[str, Acquisition]) -> tuple[list, dict]:
        """The paper's PDF and each kept candidate's tables, every file once by its bytes, with each candidate's own
        tables and notes; one whose named record or table is refused fails alone, in ``out``."""
        import hashlib
        files, own = [(pdf, f'arXiv_{arxiv}{meta["version"]}.pdf')], {}
        for c in kept:
            try:
                extra, tables, notes = self._tables(c, arxiv, fetch, cs)
            except ValueError as error:      # its named record or table is refused: this candidate alone fails
                out[c.candidate_id] = Acquisition(status='failed', reason=str(error))
                continue
            own[c.candidate_id] = (tables, notes)
            held = {hashlib.sha256(reply.data).hexdigest() for reply, _ in files}
            files += [(reply, name) for reply, name in extra if hashlib.sha256(reply.data).hexdigest() not in held]
        return files, own

    def _paper_revision(self, s: Session, kept: list[Candidate], own: dict, files: list, arxiv: str, meta: dict,
                        digest: str):
        """The draft revision holding the paper and every table the kept candidates need: one already holding them
        all is reused, else a new one is imported with the complete set, recording those it extends (S18-12)."""
        from adroit.core.experimental_input import ExperimentalDossier
        import hashlib
        import tempfile
        tables = [t for c in kept for t in own[c.candidate_id][0]]
        notes = list(dict.fromkeys(n for c in kept for n in own[c.candidate_id][1]))
        wanted = {digest, *(t['sha256'] for t in tables)}
        held = [r for r in self.catalog.list() if digest in {a.sha256 for a in r.sources}] \
            if self.catalog.path('experiments').is_dir() else []
        existing = next((r for r in held if wanted <= {a.sha256 for a in r.sources}), None)
        if existing is not None:              # the same paper and every requested table: reuse it
            revision = existing
        else:                                 # a new revision with the complete set, linked to any that holds the paper
            dossier = ExperimentalDossier(title=meta['title'], references=list(dict.fromkeys(
                [f'arXiv:{arxiv}{meta["version"]}', *[t['doi'] for t in tables if t['doi']]])), notes=notes)
            with tempfile.TemporaryDirectory(prefix='adroit-discovery-') as folder:
                paths = []
                for reply, name in files:
                    path = Path(folder) / name
                    path.write_bytes(reply.data)
                    paths.append(path)
                revision = self.catalog.import_files(paths, meta['title'], dossier=dossier,
                                                     names=[n for _, n in files],
                                                     provenance={'discovery_session': s.session_id,
                                                                 'candidate_id': kept[0].candidate_id,
                                                                 'candidate_ids': [c.candidate_id for c in kept],
                                                                 'extends': [r.reference for r in held],
                                                                 'constraint_class': kept[0].constraint_class,
                                                                 'retrieval': [r.url for r, _ in files],
                                                                 # each file's address and the sha256 of its bytes:
                                                                 # what establishes a separate source's origin (FR-01)
                                                                 'retrieved': [{'url': r.url, 'name': n, 'sha256':
                                                                                hashlib.sha256(r.data).hexdigest()}
                                                                               for r, n in files],
                                                                 'retrieved_at': utc_now()})
        return revision

    def _extract(self, s: Session, llm) -> str:
        """The experimental library's assisted extraction on each retrieved draft, batch by batch under the session's
        cap: one extraction session per revision for the candidates drawn from it, each request asking for all their
        results (the rerun's finding: two results of one paper read its pages twice). A batch already read is never
        sent again, and a session already started keeps its candidates."""
        candidates, read = self.candidates(s.session_id), 0
        ready = [i for i, c in enumerate(candidates) if c.acquisition.status == 'retrieved' and c.adapter]
        for revision in dict.fromkeys(candidates[i].acquisition.revision for i in ready):
            members = [i for i in ready if candidates[i].acquisition.revision == revision]
            fresh = [i for i in members if not candidates[i].extraction_session]
            if fresh:
                scope = self._open(s, revision, [candidates[i] for i in fresh])
                for i in fresh:
                    candidates[i] = candidates[i].model_copy(update={'extraction_session': scope.session_id})
                self._save_candidates(s.session_id, candidates)
            for session in dict.fromkeys(candidates[i].extraction_session for i in members):
                read += self._read_session(s, candidates, [i for i in members
                                                           if candidates[i].extraction_session == session], llm)
        return f'{read} batches read'

    def _open(self, s: Session, revision: str, targets: list[Candidate]):
        """An extraction session over a revision's body (``body_units``) under the session's cap; when the session
        reads figures and an SI target has no data table, its figure pages are also sent as images
        (``figure_pages``)."""
        from adroit.orchestrator.experimental_extraction import source_units
        units = source_units(self.catalog, revision, False)
        selected = body_units(units)
        curve = any(c.adapter == 'si_isoscalar_curve' and not c.acquisition.hepdata for c in targets)
        visual = figure_pages(units, selected, {c.adapter for c in targets}) if s.options.vision and curve else []
        return self.extraction.start(revision, 0, s.options.model, False, selected=selected,
                                     budget_session=s.session_id, visual=visual)

    def _read_session(self, s: Session, candidates: list[Candidate], members: list[int], llm) -> int:
        """An extraction session's unread batches for its candidates (``members``, their indices), every request
        asking for all of their results, and each candidate's draft following the session. Returns the batches read."""
        from adroit.agents.budget import BudgetExceeded
        session = candidates[members[0]].extraction_session
        scope = self.extraction.scope(session)
        instruction = extraction_instruction([candidates[i] for i in members], viewed(scope))

        def follow(revision: str) -> None:
            for i in members:
                candidates[i] = candidates[i].model_copy(update={'draft': revision})
            self._save_candidates(s.session_id, candidates)
        done = self.extraction.steps(session)
        if done and any(candidates[i].draft != done[-1].output_revision for i in members):
            follow(done[-1].output_revision)  # a step saved before the candidates were: restore it
        read = 0
        for batch, units in enumerate(scope.batches):
            if any(set(step.unit_ids) == set(units) for step in self.extraction.steps(session)):
                continue
            if llm is None:
                plan = self.extraction.preview(session, batch, instruction)
                status = plan['budget']
                committed = status['spent'] + status['reserved_uncertain']
                if committed + plan['request_bound_usd'] > status['cap']:
                    raise BudgetExceeded(committed, status['cap'], plan['request_bound_usd'])
            follow(self.extraction.step(session, batch, instruction, llm=llm).output_revision)
            read += 1
        return read

    def _packets(self, s: Session) -> str:
        folder = self.folder(s.session_id) / 'packets'
        folder.mkdir(exist_ok=True)
        written = 0
        for c in self.candidates(s.session_id):
            atomic_json(folder / f'{c.candidate_id}.json', self.packet(s.session_id, c))
            written += 1
        return f'{written} packets'

    # reading ----------------------------------------------------------------------------------------------------
    def packet(self, session_id: str, c: Candidate) -> dict:
        """A candidate's review packet: why it is relevant, the exact source identity, the extracted claims with
        their locators and problems, whether the adapter's contract reads, what is missing and the next commands."""
        from adroit.constraints.experimental_review import limit_contract
        out = {'candidate': c.model_dump(mode='json'), 'stage': self.stage(c), 'states': self.states(c)}
        draft = c.draft or c.acquisition.revision
        if draft:
            revision = self.catalog.load(draft)
            result = next((r for r in revision.dossier.results if r.result_id == c.result_id), None)
            out['draft'] = draft
            out['claims'] = [cl.model_dump(mode='json') for cl in result.claims] if result else []
            out['notes'] = revision.dossier.notes
            if c.extraction_session:
                scope = self.extraction.scope(c.extraction_session)
                out['not_read'] = unread_pages(scope)
                out['viewed_as_images'] = viewed(scope)
                out['extracted_with'] = [o.candidate_id for o in self.candidates(session_id)
                                         if o.extraction_session == c.extraction_session and o.candidate_id != c.candidate_id]
            try:
                limit_contract(draft, c.result_id, self.catalog)
                out['contract'] = 'reads as the adapter\'s contract; review, validation and binding remain'
            except (ValueError, KeyError) as error:
                out['contract'] = f'not usable yet: {error}'
            out['next'] = [f'adroit experiments review {draft} --result {c.result_id} --out FOLDER',
                           f'adroit experiments verify-source {draft} --result {c.result_id} --expected-hash … --by NAME '
                           '--confirmed --checked … (all six checks)',
                           f'adroit experiments validate-limit {draft} --result {c.result_id} --tolerance … '
                           '--expected-hash …',
                           f'(a curve digitised from a figure with one or two printed anchors: adroit experiments '
                           f'verify-figure {draft} --result {c.result_id} --tolerance … --expected-hash … --by NAME '
                           '--from LOW --to HIGH --packet DIR (the review folder you inspected) --confirmed --checked … '
                           '(all five checks))',
                           f'adroit experiments bind-limit {draft} --result {c.result_id} --review … --validation …']
        return out

    def states(self, c: Candidate) -> dict:
        """The separate states: source, review, validation and selection (read live from the library)."""
        from adroit.constraints.experimental_review import current_review
        source = ('existing' if c.category.startswith('existing') else 'superseded' if c.category == 'superseded'
                  else c.acquisition.status if c.acquisition.status != 'not_attempted' else 'needed')
        review = validation = 'none'
        review_by = ''
        bound = self.bindings(c)
        draft = c.draft or c.acquisition.revision
        if draft and c.result_id:
            try:
                found = current_review(draft, c.result_id, self.catalog)
            except (ValueError, OSError, KeyError):
                found = None
            # a person's review is "signed"; a language model's is "checked", with the model named (the post-review
            # audit's PR-09: a model-checked record had read "Verified")
            if found is not None:
                review, review_by = ('checked', found.checked_by_model) if found.checked_by_model else ('signed', '')
        if bound:
            validation = 'passed'
        return {'source': source, 'review': review, 'review_by': review_by, 'validation': validation,
                'selection': 'bound' if bound else 'unbound', 'bindings': bound}

    def bindings(self, c: Candidate) -> list[str]:
        """Current private-limit bindings that are this candidate's result (the fresh audit's F19-02): for a drafted
        result, the bindings of its own draft lineage and result identifier; for an existing result, the bound limits
        shown to be it when assessed (``resolvers``) and later bindings of its drafts whose own identity is positively
        compatible with it. A binding of another result of the same paper never resolves it."""
        from adroit.library.records_index import _bound, contract_identity
        draft = c.draft or c.acquisition.revision
        if not draft:
            lineage = {m.removeprefix('experimental:').split('@')[0] for m in c.matches if m.startswith('experimental:')}
            later = [ref for ref, item in _bound(self.catalog).items() if c.adapter and item.contract.adapter == c.adapter
                     and item.revision.removeprefix('experimental:').split('@')[0] in lineage
                     and not compatible(c.result, contract_identity(item.contract))]
            return list(dict.fromkeys([*c.resolvers, *later]))
        experiment = draft.removeprefix('experimental:').split('@')[0]
        return [ref for ref, item in _bound(self.catalog).items()
                if item.revision.removeprefix('experimental:').split('@')[0] == experiment
                and item.result_id == c.result_id]

    def stage(self, c: Candidate) -> str:
        """The user-facing stage."""
        if c.category != 'missing_supported':
            return STAGES[c.category]
        states = self.states(c)
        if states['selection'] == 'bound':
            return 'ready to use'
        if states['review'] in ('signed', 'checked'):
            return 'needs calculation/validation'
        if c.draft:
            return 'needs your review'
        if c.acquisition.status == 'retrieved':
            return 'draft ready'
        return 'source needed'

    def _budget(self, session_id: str) -> dict:
        """The session's budget status (``Intake.budget_status``), or {'unavailable': why} where its ledger cannot be
        read: the session's page and report still show, and say so (M2; it had stopped them)."""
        try:
            return self.budgets.budget_status(session_id)
        except (ValueError, OSError) as error:
            return {'unavailable': f"the session's ledger could not be read ({error})"}

    def show(self, session_id: str) -> dict:
        """The session for people: its model, stages, candidates with their stages and states, decisions and gaps.
        Read-only."""
        s = self.session(session_id)
        literature = self._read(session_id, 'literature.json') or {}
        includable = self.includable(session_id)
        return {'session': session_id, 'model': s.model_reference, 'model_sha256': s.domain.model_sha256,
                'domain': s.domain.model_dump(mode='json'), 'state': self._read(session_id, 'state.json') or {},
                'budget': self._budget(session_id), 'searched_at': literature.get('searched_at', ''),
                'candidates': [{**c.model_dump(mode='json'), 'stage': self.stage(c), 'states': self.states(c),
                                'includable': c.candidate_id in includable} for c in self.candidates(session_id)],
                'decisions': [d.model_dump(mode='json') for d in self.decisions(session_id)],
                'gaps': (self._read(session_id, 'gaps.json') or []) + literature.get('gaps', []) +
                        [f'{c.name}: {c.acquisition.reason}' + (' (in transit; a resume retries it)'
                                                                 if c.acquisition.status == 'retryable' else '')
                         for c in self.candidates(session_id) if c.acquisition.status in ('failed', 'retryable')]}

    # decisions and coverage -------------------------------------------------------------------------------------
    def decisions(self, session_id: str) -> list[Decision]:
        """The researcher's recorded decisions."""
        return [Decision.model_validate(d) for d in self._read(session_id, 'decisions.json') or []]

    def decide(self, session_id: str, candidate_id: str, kind: str, reason: str, researcher: str,
               replacement: str = '') -> Decision:
        """Record that a candidate is inapplicable (with the reason), omitted from the study's scope, or superseded by
        the newer result ``replacement`` (a researcher's confirmation of the relevance step's mark, which must name the
        same newer result). $0."""
        found = {c.candidate_id: c for c in self.candidates(session_id)}
        if candidate_id not in found:
            raise ValueError('no such candidate in this session')
        if kind == 'superseded' and (found[candidate_id].category != 'superseded'
                                     or replacement != found[candidate_id].superseded_by):
            raise ValueError('only a result proposed as superseded can be confirmed, naming the same newer result ('
                             + (found[candidate_id].superseded_by or 'none proposed') + ')')
        decision = Decision(candidate_id=candidate_id, kind=kind, reason=reason, researcher=researcher.strip(),
                            at=utc_now(), replacement=replacement if kind == 'superseded' else '')
        with run_lock(self.folder(session_id)):
            kept = [d for d in self.decisions(session_id) if d.candidate_id != candidate_id]
            self._write(session_id, 'decisions.json', [d.model_dump(mode='json') for d in [*kept, decision]])
        return decision

    def include(self, session_id: str, candidate_id: str, reason: str, researcher: str) -> Decision:
        """Take an unclear result into the session's acquisition: the researcher judges that it applies, and ADROIT has
        a calculation for its quantity (its ``adapter``), so the session fetches its paper and drafts its record at its
        next run, as for any supported missing result (the owner's JU1, 2026-11-16). Recorded as an ``included``
        decision; acquisition, extraction and packets are set to run again. A result with no calculation is refused:
        a record of it could not be used. $0 (the fetch and the paid drafting happen at the resume)."""
        found = {c.candidate_id: c for c in self.candidates(session_id)}
        if candidate_id not in found:
            raise ValueError('no such candidate in this session')
        c = found[candidate_id]
        if c.category != 'uncertain':
            raise ValueError(f'only a result whose relevance is unclear can be included; this one is {self.stage(c)}')
        adapter = self._adapter(self.session(session_id), c)
        if not adapter:
            raise ValueError("ADROIT has no calculation for this result's quantity in this model, so a record of it "
                             'could not be used: it is not fetched')
        decision = Decision(candidate_id=candidate_id, kind='included', reason=reason, researcher=researcher.strip(),
                            at=utc_now())
        with run_lock(self.folder(session_id)):
            kept = [d for d in self.decisions(session_id) if d.candidate_id != candidate_id]
            self._write(session_id, 'decisions.json', [d.model_dump(mode='json') for d in [*kept, decision]])
            self._save_candidates(session_id, [x.model_copy(update={
                'category': 'missing_supported', 'adapter': adapter,
                'missing': f'included by {decision.researcher}: {reason}'}) if x.candidate_id == candidate_id else x
                for x in self.candidates(session_id)])
            for stage in ('acquisition', 'extraction', 'packets'):
                self._stage(session_id, stage, 'pending', 'a result was included by the researcher')
        return decision

    def _adapter(self, s: Session, c: Candidate) -> str:
        """The calculation (adapter) that could compute a candidate's result for this model, from the proposal it came
        from (``adapter_for``), or ''. An unclear result is kept without one; this is what including it would use."""
        from adroit.agents.constraint_discovery import DiscoveryReport
        report = DiscoveryReport.model_validate(self._read(s.session_id, 'proposals.json') or {'proposals': []})
        for proposal in report.proposals:
            reference = proposal.reference.lower().removeprefix('arxiv:')
            if proposal.name == c.name and c.reference.lower().removeprefix('arxiv:').removeprefix('doi:') == reference:
                return adapter_for(proposal, s.domain)
        return ''

    def includable(self, session_id: str) -> set[str]:
        """The unclear results ADROIT could calculate for this model, which ``include`` would fetch and draft."""
        s = self.session(session_id)
        return {c.candidate_id for c in self.candidates(session_id) if c.category == 'uncertain' and self._adapter(s, c)}

    def coverage(self, session_id: str, incomplete: bool = False) -> DiscoveryCoverage:
        """Freeze the assessment for runs: every relevant candidate not yet resolved, with what would resolve it; a
        result a bound personal limit holds stays a requirement that only selecting that limit resolves, split where
        the limit covers only part of the domain (S18-04); a superseded result as ``_superseded`` says; the gaps, the
        surveyed domain and each stage's state (S18-06). An incomplete session is refused unless ``incomplete``, which freezes it visibly: a requirement
        everywhere keeps every allowed point pending. Written once under its hash."""
        s = self.session(session_id)
        state = self._read(session_id, 'state.json') or {}
        stages = {name: state.get(name, {}).get('status', 'not run') for name in STAGE_ORDER}
        unfinished = {k: v for k, v in stages.items() if v != 'done'}
        if unfinished and not incomplete:
            raise ValueError('the assessment is incomplete (' + ', '.join(f'{k}: {v}' for k, v in unfinished.items())
                             + '); resume it, or freeze it as incomplete so that every allowed point stays pending')
        decisions = {d.candidate_id: d for d in self.decisions(session_id)}
        inventory = {e.reference: e for e in self.inventory(session_id)}
        candidates = self.candidates(session_id)
        by_id = {c.candidate_id: c for c in candidates}
        requirements = []
        for c in candidates:
            decision = decisions.get(c.candidate_id)
            if decision and decision.kind == 'inapplicable':
                continue
            if decision and decision.kind == 'omitted':
                reason = f'omitted from this study by {decision.researcher}: {decision.reason}'
            elif c.category == 'superseded':
                requirements += self._superseded(c, by_id, inventory, decision)
                continue
            elif c.category in UNRESOLVED:
                reason = f'{self.stage(c)}: {c.missing or c.category.replace("_", " ")}'
            elif c.category in ('existing_applicable', 'existing_outside_domain') and self.bindings(c):
                requirements += self._held(c, inventory, s.domain.domain)
                continue
            else:
                continue
            requirements.append(Requirement(candidate_id=c.candidate_id, name=c.name, reference=c.reference,
                                            constraint_class=c.constraint_class, reason=reason,
                                            resolved_by=[] if decision and decision.kind != 'included'
                                            else self.bindings(c), domain=c.domain))
        if unfinished:
            requirements.append(Requirement(candidate_id='incomplete-assessment', name='an incomplete assessment',
                                            reference=f'discovery:{session_id}', constraint_class='',
                                            reason='frozen before every stage finished (' + ', '.join(
                                                f'{k}: {v}' for k, v in unfinished.items()) + ')'))
        literature = self._read(session_id, 'literature.json') or {}
        body = {'session_id': session_id, 'model_sha256': s.domain.model_sha256, 'model_reference': s.model_reference,
                'searched_at': literature.get('searched_at', ''),
                'requirements': [r.model_dump(mode='json') for r in requirements],
                'gaps': self.show(session_id)['gaps'],
                'domain': {k: list(v) for k, v in s.domain.domain.items()}, 'complete': not unfinished,
                'stages': stages}
        digest = content_hash(body)
        result = DiscoveryCoverage(assessment_sha256=digest, **body)
        path = self.folder(session_id) / 'assessments' / f'{digest}.json'
        if not path.exists():
            atomic_json(path, result.model_dump(mode='json'))
        return result

    def _held(self, c: Candidate, inventory: dict, wanted: dict) -> list[Requirement]:
        """A result bound personal limits hold, as requirements over elementary intervals (the fresh audit's F19-02):
        the requested range cut at every binding's mass-range ends; each interval is resolved only by selecting a
        binding whose range covers it, and an interval none covers (beyond them, or a gap between them) stays
        unresolved. A binding without a declared range covers everywhere (its adapter then checks each point)."""
        refs = self.bindings(c)
        base = dict(candidate_id=c.candidate_id, name=c.name, reference=c.reference, constraint_class=c.constraint_class)
        ranges = {r: tuple(inventory[r].domain['mass_range']) if r in inventory and inventory[r].domain.get('mass_range')
                  else None for r in refs}
        everywhere = [r for r, span in ranges.items() if span is None]
        want = wanted.get('m_chi') or (0.0, 1e12)
        cuts = sorted({want[0], want[1], *(x for span in ranges.values() if span for x in span
                                           if want[0] < x < want[1])})
        out = []
        for low, high in zip(cuts, cuts[1:]):
            covering = everywhere + [r for r, span in ranges.items() if span and span[0] <= low and high <= span[1]]
            reason = ('a bound personal limit holds it over this range; select it for the run' if covering else
                      "no bound personal limit of this result covers this range")
            out.append(Requirement(**base, reason=reason, resolved_by=covering, domain={'m_chi': (low, high)}))
        return out

    def _superseded(self, c: Candidate, by_id: dict[str, Candidate], inventory: dict,
                    decision: Decision | None = None) -> list[Requirement]:
        """A superseded result in the pin (the fresh audit's F19-03): a relevance step's mark, even checked for class,
        quantity and range, does not show that the newer result dominates the older over its whole domain, so until a
        researcher confirms it (``decide --superseded-by``) the older stays a requirement linked to the newer one for
        review, and no selection resolves it. Once confirmed: no requirement when the newer is a held standard entry
        (runs apply it); else one that only selecting the newer result's bound limit resolves. A chain of superseded
        candidates is followed."""
        base = dict(candidate_id=c.candidate_id, name=c.name, reference=c.reference, constraint_class=c.constraint_class,
                    domain=c.domain)
        if decision is None or decision.kind != 'superseded' or decision.replacement != c.superseded_by:
            return [Requirement(**base, reason=f'proposed as superseded by {c.superseded_by}, not confirmed: confirm it '
                                '(constraints decide … --superseded-by) or the result stays required')]
        target, seen = c.superseded_by, {c.candidate_id}
        while target.startswith('candidate:'):
            newer = by_id.get(target.removeprefix('candidate:'))
            if newer is None or newer.candidate_id in seen:
                return [Requirement(**base, reason=f'superseded by {target}, which does not lead to a held result')]
            seen.add(newer.candidate_id)
            if newer.category != 'superseded':
                bound = self.bindings(newer)
                if newer.category == 'existing_applicable' and not bound:
                    return []                 # a held standard entry of the newer result
                return [Requirement(**base, reason=f'superseded by {newer.name} ({newer.reference}), which is not '
                                    f'resolved for this run ({self.stage(newer)})', resolved_by=bound)]
            target = newer.superseded_by
        entry = inventory.get(target)
        if entry is not None and entry.library == 'standard':
            return []
        if entry is not None and entry.kind == 'personal_limit':
            return [Requirement(**base, reason=f'superseded by the bound personal limit {target}; select it for the run',
                                resolved_by=[target])]
        return [Requirement(**base, reason=f'superseded by {target}, which is held but not a bound limit: review, '
                            'validate and bind it')]

    def load_coverage(self, reference: str) -> DiscoveryCoverage:
        """A frozen assessment by its pinned ``discovery:<session>@<hash>`` reference, refused if modified."""
        key, sep, digest = reference.removeprefix('discovery:').partition('@')
        if not reference.startswith('discovery:') or not sep or len(digest) != 64:
            raise ValueError('a pinned discovery:<session>@<hash> reference is required')
        raw = json.loads((self.folder(key) / 'assessments' / f'{digest}.json').read_text())
        result = DiscoveryCoverage.model_validate(raw)
        if result.assessment_sha256 != digest or content_hash({k: v for k, v in raw.items()
                                                               if k not in ('assessment_sha256', 'scope')}) != digest:
            raise ValueError('discovery assessment modified')
        return result


# Applying a frozen assessment to a run -------------------------------------------------------------------------

def check_model(coverage: DiscoveryCoverage, spec: ModelSpec) -> None:
    """Refuse an assessment pinned to a different model: a changed model needs its own assessment (its unchanged
    source reviews stay valid; they are bound to the source, not to the model)."""
    from adroit.orchestrator.model_approval import model_identity
    if model_identity(spec) != coverage.model_sha256:
        raise ValueError(f'{coverage.reference} belongs to a different model; run discovery for this one')


def load_coverage(reference: str) -> DiscoveryCoverage:
    """A frozen assessment from the personal experimental library by its pinned reference."""
    return Discovery().load_coverage(reference)


def pending_spans(coverage: DiscoveryCoverage, selected: list[str]) -> list:
    """The pinned assessment's unresolved requirements for a run, as a scan applies them (``ScanRequest.discovery``):
    each requirement that no selected private limit resolves, over its declared mass range (none: everywhere)."""
    from adroit.parameter_space.scan import DiscoveryPending
    out = [DiscoveryPending(text=f'discovery: {r.name} ({r.reference}): {r.reason}', m_chi=r.domain.get('m_chi'),
                            m_med=r.domain.get('m_med'))
           for r in coverage.requirements if not set(r.resolved_by) & set(selected)]
    spans = {k: tuple(coverage.domain[k]) for k in ('m_chi', 'm_med') if coverage.domain.get(k)}
    if spans:                                 # beyond the surveyed ranges nothing was assessed (S18-06, F19-04)
        ranges = ', '.join(f'{k} = {v[0]:g}–{v[1]:g} GeV' for k, v in spans.items())
        out.append(DiscoveryPending(text=f'discovery: outside the surveyed range {ranges} ({coverage.reference}); a '
                                         'survey of this range is needed', m_chi=spans.get('m_chi'),
                                    m_med=spans.get('m_med'), outside=True))
    return out


def requirements_at(coverage: DiscoveryCoverage, m_chi: float | None, selected: list[str],
                    m_med: float | None = None) -> list[str]:
    """The pending entries a point of masses ``m_chi`` (and ``m_med``) gets (``pending_spans``)."""
    return [p.text for p in pending_spans(coverage, selected) if p.applies(m_chi, m_med)]


def qualify(verdict, coverage: DiscoveryCoverage, selected: list[str]):
    """A Track 1 verdict with every allowed evaluated point that an unresolved requirement covers made pending; an
    excluded point stays excluded and over- or underabundance is unchanged."""
    if verdict is None:
        return None
    from adroit.parameter_space.verdict import discovered
    crossings = [discovered(c, pending_spans(coverage, selected)) for c in verdict.crossings]   # already applied in
    moved = sum(c.status == 'pending' and any(p.startswith('discovery:') for p in c.pending)    # Track 1's verdict
                for c in crossings)
    level = verdict.level
    if level == 'viable' and not any(c.status == 'viable' for c in crossings):
        level = 'viable_pending'
    names = sorted({r.name for r in coverage.requirements if not set(r.resolved_by) & set(selected)})
    summary = verdict.summary
    if names:
        summary += (f"; discovery-qualified ({coverage.reference}): {len(names)} relevant constraint(s) unresolved "
                    f"for this run ({'; '.join(names)})" + (f", {moved} allowed point(s) left pending" if moved else ''))
        if not verdict.discovery_applied and level == 'viable':
            # a verdict formed without the requirements at its grid and shifted roots cannot keep a "viable" claim:
            # they may apply at points it certified (S18-03); Track 1 applies them before the verdict
            level = 'pending'
            summary += ('; this verdict was formed before the requirements were applied to its evaluated points, so '
                        'viability is not established: rerun with the pin')
    update = {'crossings': crossings, 'level': level, 'summary': summary}
    if verdict.rests_on is not None:          # what the headline rests on, as qualified (CR-04)
        from adroit.parameter_space.verdict import resting, support_words
        rests = (resting(crossings, level) if level in ('viable', 'viable_pending') else verdict.rests_on
                 if level == verdict.level else list(range(len(crossings))))
        tables = verdict.rests_on_table_roots if level == verdict.level else []
        update.update(rests_on=rests, rests_on_table_roots=tables,
                      support=[support_words(c) for c in [*(crossings[i] for i in rests),
                                                          *(verdict.table_roots[j] for j in tables)]])
    return verdict.model_copy(update=update)


def qualify_points(points: list, coverage: DiscoveryCoverage, selected: list[str]) -> list:
    """Explain a signal's fitted and thermal points (``BandPoint``) with the same rule."""
    out = []
    for b in points:
        extra = (requirements_at(coverage, b.m_chi, selected, getattr(b, 'm_med', None))
                 if b.status and b.status != 'excluded' else [])
        out.append(b.model_copy(update={'status': 'pending', 'pending': [*b.pending, *extra]}) if extra else b)
    return out
