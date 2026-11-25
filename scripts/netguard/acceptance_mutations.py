"""Defects the release layer's mutation controls restore in the workbench's children (``scripts/browser_acceptance.py
--mutation-controls``; the owner's acceptance criteria, 2026-10-25): each, named by ``ADROIT_ACCEPTANCE_MUTATION``, is
applied by an import hook when its module loads, in the processes it names only (the workbench, a batch's runner, a
promotion), so that the journey covering it must fail at its invariant. Never set outside the release layer's
controls.
"""
from __future__ import annotations

import importlib.abc
import os
import sys
from pathlib import Path


def _batch_interrupted_hidden(m) -> None:
    """B20-02: a batch whose runner died is left "running" (never interrupted, never resumable)."""
    m._checked = lambda folder: m.load(folder)


def _live_child_read_as_dead(m) -> None:
    """A resumed runner reads a live child as gone and closes its request."""
    m._alive = lambda pid: False


def _reservation_read_as_settled(m) -> None:
    """WA-03, CA-05: a request whose bill is unknown read as settled at $0, by every reading of a paid ledger's
    requests: ``read_ledger``, ``read_raised``, a session's reading of its requests with its cap raises (the auditor's DF
    recheck, DG-01, 2026-11-06), and ``read_held``, the same with what the ledger held, which a session's account is
    now rebuilt from (the auditor's DN recheck, DO-01, 2026-11-08: the control had restored the defect only in the readings
    the session's pages no longer use)."""
    read, raised, held = m.read_ledger, m.read_raised, m.read_held

    def erase(requests):
        return {k: (r.model_copy(update={"state": "settled", "cost_usd": 0.0, "settled_line": 0})
                    if r.state != "settled" else r) for k, r in requests.items()}
    m.read_ledger = lambda path: erase(read(path))
    m.read_raised = lambda path: (lambda found: (erase(found[0]), found[1]))(raised(path))
    m.read_held = lambda path: (lambda found: (erase(found[0]), *found[1:]))(held(path))


def _eos_open_ignored(m) -> None:
    """V1-01, CA-02: a single-idea study's headline decided at its nominal level although the equation of state's band
    leaves it open (the tables missing): "no resolved thermal explanation" where it is undetermined. (Ignoring the
    precondition itself, ``relic.band_unavailable``, is caught further in: the run stops, naming the tables.)"""
    m._eos_level = lambda level, text, added, unresolved: (level, text)


def _shared_budget_ignored(m) -> None:
    """CA-04: a linked extraction's page reads its own session's budget, not the discovery's it shares."""
    m.ExperimentalExtraction.budget_owner = lambda self, session: session


def _intake_read_as_study(m) -> None:
    """The owner's report of 2026-10-23: an intake's run read as a physics study."""
    m.kind_of = lambda job: "study"


def _damaged_record_breaks_listing(m) -> None:
    """CA-07: one malformed job record breaks the whole history."""
    m.listing = lambda root: ([m.load(p.parent) for p in Path(root).rglob(m.JOB)], [])


def _lost_journal_read_as_empty(m) -> None:
    """CO-05: a session's lost paid journal read as an empty one, its approved cap restored in full. Since DO-01
    (2026-11-08) the mark beside a ledger names it missing too: to the session (among its signs of spending,
    ``Intake.spending_evidence``), to every other reading (``budget.ledger_bytes``) and to every writer
    (``durable.append_held``), so the defect is restored whole: the session's signs of spending not consulted, and no
    mark read (the control had restored the first alone: the session read as empty, but its client's writer, finding
    the mark, refused its request), nor read back once an append has written it (``durable._recorded``, the auditor's DQ
    recheck, DR-01, 2026-11-09: with no mark read, the writer's reading back of its own found none, and refused). A
    mark is read, and read back, in the folder whose lock its writer holds, where one is given (the auditor's DT recheck,
    DU-01, 2026-11-10): none read there either."""
    from adroit.core import durable
    m.Intake.spending_evidence = lambda self, s: []
    durable.marked = lambda path, folder=None: None
    durable._recorded = lambda path, handle, after, folder=None: None


def _live_view_rebuilt_every_tick(m) -> None:
    """Before the auditor's CO recheck (2026-10-26): a run's live view rebuilt on every tick, whatever changed, so a
    finished run's primary button was replaced each second under a person's click."""
    import itertools
    count = itertools.count()
    m._live_key = lambda *shown: str(next(count))


def _point_table_mislabelled(m) -> None:
    """The auditor's DJ recheck, DK-03 (2026-11-07): the study page's point table heading its Ωh² column as a cross section,
    its rows unchanged (the page cells read the columns given to the table; the history journey reads them drawn)."""
    import types
    real = m.ui

    def table(*args, columns=None, **kwargs):
        columns = [{**c, "label": "σ_SI (cm²)"} if c.get("name") == "omega" else c for c in columns or []]
        return real.table(*args, columns=columns, **kwargs)
    m.ui = types.SimpleNamespace(**{name: getattr(real, name) for name in dir(real)
                                    if not name.startswith("_") and name != "table"}, table=table)


def _command(argv: list[str]) -> list[str]:
    """The words after ``python -m``: the module and its arguments."""
    return argv[argv.index("-m") + 1:] if "-m" in argv else []


def _workbench(argv: list[str]) -> bool:
    return _command(argv)[:2] == ["adroit.orchestrator.cli", "workbench"]


def _resumed_runner(argv: list[str]) -> bool:
    """A batch's runner started by a resume (its generation, the last word, after the first)."""
    words = _command(argv)
    return words[:1] == ["adroit.ui.batch"] and len(words) > 3 and words[3] != "1"


def _workbench_or_extraction(argv: list[str]) -> bool:
    """The workbench, or the experimental extraction it launches (both read the session's journal)."""
    return _workbench(argv) or _command(argv)[:3] == ["adroit.orchestrator.cli", "experiments", "extract"]


def _promotion(argv: list[str]) -> bool:
    return _command(argv)[:2] == ["adroit.orchestrator.cli", "promote"]


def _halo_form_ignored(m) -> None:
    """Halo phase 1: the form shows the halo chosen but launches without it (``forms.halo_flags``)."""
    m.halo_flags = lambda *args, **kwargs: []


def _halo_dropped_by_child(m) -> None:
    """Halo phase 1: the run keeps the request's benchmark but calculates with the published halos (``halo_region.of``
    leaves a fixed benchmark out of force)."""
    from adroit.core.halo_choice import FixedHalo
    original = m.of
    m.of = lambda value: None if isinstance(value, FixedHalo) else original(value)


def _halo_checkpoint_identity_omitted(m) -> None:
    """Halo phase 1: a checkpoint's identity leaves the halo out (in every Track 1 run, the first and its resume), so a
    resume with another halo is taken."""
    original = m.Checkpoint.__init__

    def init(self, folder, inputs, dependencies, resume=False, context=None):
        original(self, folder, {k: v for k, v in inputs.items() if k != "halo"}, dependencies, resume, context)
    m.Checkpoint.__init__ = init


def _halo_export_unqualified(m) -> None:
    """Halo phase 1: the export drops each point's halo (``evidence.halo.point_label``)."""
    m.point_label = lambda *args: ""


def _future_family_as_shm(m) -> None:
    """Halo phase 1: a family not yet implemented taken as the SHM, available under its own label (since halo phase 2,
    SHM + LMC: SHM++ is implemented)."""
    m.FAMILIES["shm-lmc"] = m.FAMILIES["shm"].model_copy(update={"id": "shm-lmc", "label": "SHM + LMC"})


def _shmpp_as_shm(m) -> None:
    """Halo phase 2: SHM substituted for SHM++: the run calculates at the SHM with SHM++'s v₀, v_esc and ρ₀ (its
    tables ignored: ``halo_limits.at_tables`` giving a standard halo's state)."""
    def at_tables(fixed, budget):
        p = fixed.parameters
        return m.State(v0_km_s=p.v0_km_s, v_esc_km_s=p.v_esc_km_s, rho_gev_cm3=p.rho_gev_cm3, budget=budget,
                       benchmark=True)
    m.at_tables = at_tables


def _shmpp_isotropic(m) -> None:
    """Halo phase 2: the Sausage's anisotropy dropped (its dispersions and its normalisation the round halo's)."""
    import math
    m.dispersions = lambda p: (p.v0_km_s / math.sqrt(2.0), p.v0_km_s / math.sqrt(2.0))
    m.n_sausage = m.n_round


def _shmpp_frames_interchanged(m) -> None:
    """Halo phase 2: the detector's and the Sun's distributions interchanged (each table generated with the other's
    boost, its frame's name kept)."""
    m.Parameters.boost = lambda self, frame: self.v_sun() if frame == "detector" else self.v_detector()


def _shmpp_continuation_reset(m) -> None:
    """Halo phase 2: a continuation drafted with the SHM's benchmark in place of the study's SHM++."""
    original = m._converted_halo

    def converted(kind, request, target):
        found = original(kind, request, target)
        if isinstance(found.get("halo"), dict) and found["halo"].get("family") == "shm-plus-plus":
            from adroit.core.halo_choice import fixed
            found = {**found, "halo": fixed().model_dump(mode="json")}
        return found
    m._converted_halo = converted


def _track1(argv: list[str]) -> bool:
    return _command(argv)[:2] == ["adroit.orchestrator.cli", "track1"]


SPAWNED_BY = "ADROIT_ACCEPTANCE_MUTATION_SPAWNED_BY"    # a run the mutation is applied in, named to the workers it spawns


def _spawned(argv: list[str]) -> bool:
    """A multiprocessing worker started by spawn (its command ends ``--multiprocessing-fork``)."""
    return "--multiprocessing-fork" in argv


def _track1_and_its_workers(argv: list[str]) -> bool:
    """A Track 1 run and the scan workers it spawns: a defect in the code is in every process of a run. A worker now
    checks the snapshot it is given (the halo phase 2 audit's HB-02), so a generator defect planted in the run's main
    process alone was refused by its own workers, before the journey's invariant could see it."""
    return _track1(argv) or (_spawned(argv) and os.environ.get(SPAWNED_BY) == "track1")


def _tables(argv: list[str]) -> bool:
    return _command(argv)[:3] == ["adroit.orchestrator.cli", "evidence", "tables"]


# name -> (the module patched, the processes it is applied in, the patch)
MUTATIONS = {
    "halo_form_ignored": ("adroit.ui.forms", _workbench, _halo_form_ignored),
    "halo_dropped_by_child": ("adroit.parameter_space.halo_region", _track1, _halo_dropped_by_child),
    "halo_checkpoint_identity_omitted": ("adroit.core.checkpoint", _track1, _halo_checkpoint_identity_omitted),
    "halo_export_unqualified": ("adroit.evidence.halo", _tables, _halo_export_unqualified),
    "future_family_as_shm": ("adroit.core.halo_choice", _workbench, _future_family_as_shm),
    "shmpp_as_shm": ("adroit.parameter_space.halo_limits", _track1, _shmpp_as_shm),
    "shmpp_isotropic": ("adroit.halo_models.shm_plus_plus", _track1_and_its_workers, _shmpp_isotropic),
    "shmpp_frames_interchanged": ("adroit.halo_models.shm_plus_plus", _track1_and_its_workers,
                                  _shmpp_frames_interchanged),
    "shmpp_continuation_reset": ("adroit.orchestrator.reanalysis", _workbench, _shmpp_continuation_reset),
    "batch_interrupted_hidden": ("adroit.ui.batch", _workbench, _batch_interrupted_hidden),
    "live_child_read_as_dead": ("adroit.ui.engine", _resumed_runner, _live_child_read_as_dead),
    "reservation_read_as_settled": ("adroit.agents.budget", _workbench, _reservation_read_as_settled),
    "eos_open_ignored": ("adroit.orchestrator.single_idea", _promotion, _eos_open_ignored),
    "shared_budget_ignored": ("adroit.orchestrator.experimental_extraction", _workbench, _shared_budget_ignored),
    "intake_read_as_study": ("adroit.ui.outcomes", _workbench, _intake_read_as_study),
    "damaged_record_breaks_listing": ("adroit.ui.engine", _workbench, _damaged_record_breaks_listing),
    "lost_journal_read_as_empty": ("adroit.orchestrator.model_intake", _workbench_or_extraction,
                                   _lost_journal_read_as_empty),
    "live_view_rebuilt_every_tick": ("adroit.ui.pages", _workbench, _live_view_rebuilt_every_tick),
    "point_table_mislabelled": ("adroit.ui.points", _workbench, _point_table_mislabelled),
}


class _Loader(importlib.abc.Loader):
    def __init__(self, inner, patch) -> None:
        self.inner, self.patch = inner, patch

    def create_module(self, spec):
        return self.inner.create_module(spec)

    def exec_module(self, module) -> None:
        self.inner.exec_module(module)
        self.patch(module)


class _Hook(importlib.abc.MetaPathFinder):
    def __init__(self, name: str, patch) -> None:
        self.name, self.patch = name, patch

    def find_spec(self, fullname, path, target=None):
        if fullname != self.name:
            return None
        for finder in sys.meta_path:
            if finder is self or not hasattr(finder, "find_spec"):
                continue
            spec = finder.find_spec(fullname, path, target)
            if spec is not None and spec.loader is not None:
                spec.loader = _Loader(spec.loader, self.patch)
                return spec
        return None


def install(name: str) -> None:
    """Apply the mutation ``name`` in this process if it is one of the processes the mutation names."""
    module, where, patch = MUTATIONS[name]
    argv = list(getattr(sys, "orig_argv", sys.argv))
    if where(argv):
        if where is _track1_and_its_workers and _track1(argv):
            os.environ[SPAWNED_BY] = "track1"          # inherited by the workers it spawns
        sys.meta_path.insert(0, _Hook(module, patch))
