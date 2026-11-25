"""The halo phase 2 audit's findings, repaired (the independent audit of 2026-11-11 (halo phase2); the record
the halo phase2 repairs record of 2026-11-11):

- HB-01: the family, not which optional fields are present, decides a snapshot's form and the machinery it is
  calculated with; a snapshot naming SHM++ that holds a standard halo is not one, and is never calculated as the SHM.
- HB-02: every calculation that puts a saved halo in force refuses what a fresh run refuses, before anything is
  calculated or any request sent: a run, a variant, a combination, a scan's worker, a verdict, a replay, the agents.
- HB-03: a calculation reads the halo data files it was resolved with (the local densities for the γ-ray lines and the
  antiprotons, the count ratio's validation), never values cached from other bytes; a worker that cannot read them
  refuses; a claim binds what was read.
- HB-04: an SHM++ scan's note says how its limits were taken, not that standard tables were.

Offline: toy searches with real recoil rates (``test_halo_phase1``'s), the halo data files copied to a folder of the
test's."""
from __future__ import annotations

from collections import OrderedDict
from functools import lru_cache
from types import SimpleNamespace

import pytest
import yaml
from pydantic import TypeAdapter, ValidationError

from adroit.core import halo_choice
from adroit.core.dm_state import HaloModel
from adroit.core.halo_choice import FixedHalo, HaloDataChanged, resolve
from adroit.halo_models import shm_plus_plus as shmpp
from adroit.orchestrator import agents, signal, single_idea, track1, variants
from adroit.parameter_space import certification, halo_limits, halo_region, limit_tables, limits, scan
from adroit.agents.llm import FakeLLMClient
from tests.orchestrator.test_halo_phase1 import _request, toys  # noqa: F401 (a fixture)
from tests.parameter_space.test_halo_audit import XENON, _entry


@lru_cache(maxsize=1)
def plus() -> FixedHalo:
    return halo_choice.fixed("shm-plus-plus")


# --- HB-01: the family decides the form --------------------------------------------------------------------------------

HALO_FIELDS = {"signal": signal.SignalRequest, "track1": track1.Track1Request, "single idea": single_idea.SingleIdeaRequest,
               "scan": scan.ScanRequest}


def _wrong_shape() -> dict:
    """The auditor's snapshot: SHM++'s family, benchmark and version, a standard halo, no generated field."""
    raw = plus().model_dump(mode="json")
    return {**{k: raw[k] for k in ("treatment", "schema_version", "family", "benchmark", "version",
                                   "full_calculations")}, "halo": HaloModel().model_dump(mode="json")}


def _refused_by_every_request(raw: dict, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        FixedHalo.model_validate(raw)
    for name, request in HALO_FIELDS.items():
        with pytest.raises(ValidationError):
            TypeAdapter(request.model_fields["halo"].annotation).validate_python(raw)


def test_a_snapshot_naming_shm_plus_plus_with_a_standard_halo_is_refused_as_it_is_read():
    _refused_by_every_request(_wrong_shape(), "without its parameters, numerical settings, Sun-frame table, tables")
    raw = plus().model_dump(mode="json")
    for field, words in halo_choice.GENERATED_TEXT.items():                  # each one missing alone
        _refused_by_every_request({k: v for k, v in raw.items() if k != field}, f"without its {words}")
    _refused_by_every_request({**raw, "tables": {"detector": raw["tables"]["detector"]}}, "not the detector and the Sun")


def test_a_standard_snapshot_holding_generated_fields_is_refused():
    raw = halo_choice.fixed().model_dump(mode="json")
    generated = plus().model_dump(mode="json")
    for field in halo_choice.GENERATED_FIELDS:
        _refused_by_every_request({**raw, field: generated[field]}, "a standard halo, holding a generated benchmark's")


def test_the_family_not_its_fields_chooses_the_machinery():
    shm, shmpp_ = halo_choice.fixed(), plus()
    for value in (shm, shmpp_):                                              # the healthy ones read back as they were
        again = FixedHalo.model_validate_json(value.model_dump_json())
        assert again == value and halo_region.checked(again) == again
    assert (shm.generated, shmpp_.generated) == (False, True)
    assert halo_choice.GENERATED == {"shm-plus-plus"}
    built = FixedHalo.model_construct(**_wrong_shape() | {"halo": HaloModel()})   # made without validation
    assert built.generated                                                   # by its family, though it holds no table
    with pytest.raises(ValueError, match="without its parameters.*nothing is calculated"):
        halo_region.checked(built)


def test_a_benchmark_of_another_family_is_never_calculated_under_this_ones_name():
    borrowed = FixedHalo(family="shm", benchmark="shmpp-1810.11468", version=1, halo=HaloModel())
    assert "is not a benchmark of shm (its benchmark is shm-2105.00599)" in halo_choice.verify(borrowed)
    with pytest.raises(ValueError, match="not a benchmark of shm"):
        halo_region.checked(borrowed)
    shown = resolve(borrowed)                                                # shown, never given SHM++'s source
    assert shown.sources == [] and "SHM++" not in shown.summary


def test_a_reanalysis_draft_edited_out_of_its_familys_form_is_refused_as_saved_in_its_own_words(tmp_path):
    """The workbench's reanalysis (``Reanalysis.revise``): a draft whose SHM++ snapshot lost its Sun-frame table is not
    saved, and the person reads why by the field it concerns, not pydantic's echo of the input."""
    from adroit.library.personal import Catalog
    from adroit.orchestrator.reanalysis import Reanalysis
    from tests.orchestrator.test_reanalysis import parent
    service = Reanalysis(Catalog(tmp_path / "models"))
    draft = service.open(str(parent(tmp_path)), "signal")
    request = {**draft.request, "experiment": "CDMS II Si (2013)", "halo": plus().model_dump(mode="json")}
    healthy = service.revise(draft.reference, request)                       # SHM++ whole: saved
    drafts = sorted((service.root / "drafts").glob("*.json"))
    request["halo"] = {k: v for k, v in request["halo"].items() if k != "sun"}
    with pytest.raises(ValueError) as refused:
        service.revise(healthy.reference, request)
    assert not isinstance(refused.value, ValidationError) and str(refused.value) == (
        "the edited request is refused: halo: shmpp-1810.11468: a snapshot of SHM++ without its Sun-frame table: "
        "refused, never calculated as another halo under its name")
    assert len(drafts) == 2 and sorted((service.root / "drafts").glob("*.json")) == drafts   # no draft saved


def test_the_auditors_public_run_refuses_before_anything_is_calculated(toys):  # noqa: F811
    built = FixedHalo.model_construct(**_wrong_shape() | {"halo": HaloModel()})
    with pytest.raises(ValueError, match="without its parameters"):
        signal.run(_request(plus()).model_copy(update={"halo": built}))
    assert toys["signal"] == [] and toys["exclusion"] == []


# --- HB-02: every calculation refuses what a fresh run refuses ----------------------------------------------------------

def _edited_table() -> FixedHalo:
    density = list(plus().halo.speed_density)
    density[700] *= 1.0 + 1e-6
    return plus().model_copy(update={"halo": plus().halo.model_copy(update={"speed_density": density})})


REFUSED = {                                   # each of a valid form; each refused by a fresh run
    "a newer generator": lambda: plus().model_copy(update={
        "numerics": plus().numerics.model_copy(update={"generator": shmpp.GENERATOR + 1})}),
    "a table's bytes edited": _edited_table,
    "a family not available": lambda: FixedHalo(family="shm-lmc", benchmark="shm-2105.00599", version=1,
                                                 halo=HaloModel()),
    "another family's benchmark": lambda: FixedHalo(family="shm", benchmark="shmpp-1810.11468", version=1,
                                                    halo=HaloModel()),
    "a standard halo the machinery does not take": lambda: halo_choice.fixed().model_copy(update={
        "halo": HaloModel(v_lsr_km_s=(0.0, 250.0, 0.0))}),
    "SHM++ holding a standard halo": lambda: FixedHalo.model_construct(**_wrong_shape() | {"halo": HaloModel()}),
}


def _fresh(halo) -> str:
    with pytest.raises(ValueError) as fresh:
        signal.run(_request(halo))
    return str(fresh.value)


@pytest.fixture(scope="module")
def saved():
    """One Track 2 result at SHM++, calculated once (the toys' real recoil rates)."""
    with pytest.MonkeyPatch.context() as mp:
        toys.__wrapped__(mp)
        return signal.run(_request(plus()))


def _as_saved(result, halo):
    return result.model_copy(update={"request": result.request.model_copy(update={"halo": halo})})


@pytest.mark.parametrize("case", list(REFUSED))
def test_a_continuation_refuses_what_a_fresh_run_refuses_and_calculates_nothing(case, toys, saved):  # noqa: F811
    bad = REFUSED[case]()
    why = _fresh(bad)
    old = _as_saved(saved, bad)
    candidate = old.request.candidates[0]
    option = variants.VariantOption(index=0, parent=candidate.label, deformation="the same point",
                                    description="identity", candidate=candidate)
    for continuation in (lambda: variants.evaluate(old, [option]), lambda: signal.combine(old.request, candidate)):
        with pytest.raises(ValueError) as refused:
            continuation()
        # the same refusal, by the same check (a fresh request holding a snapshot not of its family's form is refused
        # as it is read, its reason in pydantic's words; a saved one, as it is put in force)
        assert str(refused.value) == why or str(refused.value).removesuffix("; nothing is calculated") in why
    assert toys["signal"] == [] and toys["exclusion"] == [] and toys["judged"] == []


@pytest.mark.parametrize("case", list(REFUSED))
def test_putting_a_refused_halo_in_force_is_refused_wherever_it_is_done(case, monkeypatch):
    """``halo_region.using`` is where every calculation puts a saved halo in force: the runs, the variants, the
    combinations, both verdicts (``verdict.verdict``, ``verdict.verdict_pair``), a replay (``replay._recorded_halo``)
    and a scan's worker (``scan._task``), whose point is never evaluated."""
    bad = REFUSED[case]()
    with pytest.raises(ValueError):
        with halo_region.using(bad):
            pass
    assert halo_region.preset() is None
    evaluated = []
    monkeypatch.setattr(scan, "evaluate", lambda *a: evaluated.append(a))
    with pytest.raises(ValueError):
        scan._task(("central", bad, None, "a model", "a point", False, None))
    assert evaluated == []
    from adroit.parameter_space import verdict
    with pytest.raises(ValueError):
        verdict.verdict(SimpleNamespace(request=SimpleNamespace(relic_fraction=1.0, halo=bad)))


def test_every_healthy_halo_is_put_in_force_as_before():
    for value in (None, "published", halo_region.HaloPreset(), halo_choice.fixed(), plus()):
        with halo_region.using(value):
            assert halo_region.preset() == value


def _offline(tmp_path) -> agents.Tools:
    """The agents' network services replaced: no reference is confirmed, no abstract fetched, the caches the test's
    (the audit loop's AL1-16, 2026-11-14: run with the defaults, the report's citations had been looked up on arXiv
    from the test process, five times, unless an earlier test had left them in the data folder's cache)."""
    from adroit.retrieval import references
    return agents.Tools(resolver=lambda asked: {}, fetch=lambda query, n: [],
                        cache=references.ReferenceCache(tmp_path / "references.json"),
                        literature_cache=tmp_path / "literature.json")


@pytest.mark.parametrize("case", list(REFUSED))
def test_the_variant_agent_is_refused_before_any_request(case, saved, monkeypatch, tmp_path):
    llm = FakeLLMClient([])
    out = agents.run_path2(_as_saved(saved, REFUSED[case]()), llm, agents.AgentRequest(scout=False, audit=False),
                           _offline(tmp_path))
    assert out.variants_refused and llm.call_count == 0 and out.variants == [] and out.menu == []
    assert "Not run: the result's halo cannot be calculated" in agents.report(out)
    asked = []
    monkeypatch.setattr(variants, "triggers", lambda result: asked.append(result) or {})   # nothing to ask after
    healthy = agents.run_path2(saved, FakeLLMClient([]), agents.AgentRequest(scout=False, audit=False),
                               _offline(tmp_path))
    assert asked == [saved] and healthy.variants_refused == "" and "variants_refused" not in healthy.model_dump(mode="json")
    assert "Not run" not in agents.report(healthy)


def test_a_healthy_continuation_still_calculates(toys, saved):  # noqa: F811
    for halo in (halo_choice.fixed(), plus()):
        combined = signal.combine(_as_saved(saved, halo).request, saved.request.candidates[0])
        assert combined is not None
    assert toys["signal"]


# --- HB-03: the halo data files as the calculation was resolved with them ---------------------------------------------

RECORDS = ("fermi-lat-1506.00013-lines", "calore-2202.03076-pbar")      # a γ-ray line, the antiprotons


@pytest.fixture
def files(tmp_path, monkeypatch):
    """The three halo data files copied to a folder of the test's (``halo_choice.PACKAGE``), and a writer of new
    local densities."""
    for path in halo_choice.HALO_DATA.values():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_bytes((halo_choice.PACKAGE / path).read_bytes())
    monkeypatch.setattr(halo_choice, "PACKAGE", tmp_path)
    densities = tmp_path / halo_choice.HALO_DATA["local densities"]

    def write(rho: float) -> None:
        data = yaml.safe_load(densities.read_text())
        for record in RECORDS:
            data["records"][record]["rho_gev_cm3"] = rho
        densities.write_text(yaml.safe_dump(data))
    return SimpleNamespace(folder=tmp_path, densities=densities, write=write)


def _scales() -> list[float]:
    with halo_limits.using(halo_limits.at_tables(plus(), halo_limits.Budget(0))):
        return [halo_limits.density_scale(record) for record in RECORDS]


def test_a_warm_process_reads_the_densities_a_new_resolution_binds(files):
    files.write(0.4)
    assert _scales() == pytest.approx([(0.55 / 0.4) ** 2] * 2)              # warmed with A
    files.write(0.8)                                                         # B published
    resolution = resolve(plus())
    with halo_choice.holding(resolution.data):
        warm = _scales()
    assert warm == pytest.approx([(0.55 / 0.8) ** 2] * 2) == _scales()       # as a fresh process reads B
    halo_choice.unchanged(resolution)


def test_a_file_changed_during_the_run_is_never_read_under_its_identity(files, monkeypatch):
    files.write(0.4)
    resolution = resolve(plus())
    with halo_choice.holding(resolution.data):
        files.write(0.8)                                                     # edited while the run calculates
        assert _scales() == pytest.approx([(0.55 / 0.4) ** 2] * 2)          # the bytes it was resolved with
        from adroit.parameter_space.halo_evaluation import _reading
        with _reading() as read:                                             # a point calculated in the run
            evaluation = halo_region.HaloEvaluation(region="r", data=read)
        bound = certification._halo_data(SimpleNamespace(halo=evaluation))
        assert bound == resolution.data                                      # the claim binds what was read (HC-01)
        monkeypatch.setattr(halo_choice, "_HELD", OrderedDict())             # a worker, holding nothing yet
        monkeypatch.setattr(halo_choice, "_PARSED", OrderedDict())
        with pytest.raises(HaloDataChanged, match="local densities.*not the one this calculation was resolved with"):
            _scales()
    with pytest.raises(HaloDataChanged, match="local densities"):            # and the end refuses the run
        halo_choice.unchanged(resolution)


def test_each_run_calculates_with_the_files_its_resolution_read(toys, tmp_path, monkeypatch):  # noqa: F811
    """Track 2's, Track 1's and Explain a signal's runs: their calculation (stood in for here, but for Track 2's, which
    is the toys') reads with its resolution's identities in force, the same its result records."""
    from adroit.orchestrator import track1_identity
    from tests import version_matrix as vm
    seen = []
    real = signal._run
    monkeypatch.setattr(signal, "_run", lambda request: seen.append(halo_choice.in_force()) or real(request))
    result = signal.run(_request(plus()))
    monkeypatch.setattr(track1_identity, "dependencies", lambda: {})
    _, b = vm.versions(tmp_path / "track1")
    monkeypatch.setattr(track1, "_run", lambda *a, **k: seen.append(halo_choice.in_force()) or b)
    one = track1.run(b.request.model_copy(update={"halo": plus()}), tmp_path / "track1")
    item = vm.single_idea_versions()[1]
    monkeypatch.setattr(single_idea, "_study", lambda *a, **k: seen.append(halo_choice.in_force()) or item)
    idea = single_idea.run(item.request.model_copy(update={"halo": plus()}), tmp_path / "idea")
    assert seen == [r.halo_resolution.data for r in (result, one, idea)]
    assert all(set(files) == set(halo_choice.HALO_DATA) and all(files.values()) for files in seen)


def test_a_scans_workers_are_given_the_runs_files(files, monkeypatch):
    seen = []
    monkeypatch.setattr(scan, "evaluate", lambda *a: seen.append(halo_choice.in_force()))
    resolution = resolve(plus())
    with halo_choice.holding(resolution.data):
        files_in_force = halo_choice.in_force()
    scan._task(("central", plus(), files_in_force, "a model", "a point", False, None))
    assert seen == [resolution.data]


def test_the_count_ratios_validation_is_read_by_its_identity_never_cached_by_none(files, monkeypatch):
    monkeypatch.setattr(halo_limits, "inputs_sha256", lambda module: "inputs")
    validation = files.folder / halo_choice.HALO_DATA["count-ratio validation"]
    state = halo_limits.State(v0_km_s=233.0, v_esc_km_s=528.0, rho_gev_cm3=0.4)
    validation.write_text(yaml.safe_dump(_entry()))
    assert halo_limits.validated(XENON, "SI", 100.0, state) == pytest.approx(0.05)      # warmed with A
    spoiled = _entry()
    spoiled["modules"][XENON]["SI"]["points"].pop()
    validation.write_text(yaml.safe_dump(spoiled))                                    # B: an entry incomplete
    assert halo_limits.validated(XENON, "SI", 100.0, state) is None
    resolution = resolve(plus())
    validation.write_text(yaml.safe_dump(_entry()))                                   # A again, after resolving B
    with halo_choice.holding(resolution.data):
        assert halo_limits.validated(XENON, "SI", 100.0, state) is None               # the run reads B


# --- HB-04: an SHM++ scan says how its limits were taken -----------------------------------------------------------

def test_an_shm_plus_plus_scan_never_says_its_limits_came_from_standard_tables(monkeypatch):
    monkeypatch.setattr(limit_tables, "current", lambda: ["LZ WS2022+WS2024 SI", "CDMSlite Run 2 SI"])
    monkeypatch.setattr(limits, "tabulated", lambda: True)
    at_plus = " ".join(scan._scan_notes([], plus()))
    assert "precomputed tables" not in at_plus and "LZ WS2022+WS2024 SI" not in at_plus
    assert ("direct detection at shmpp-1810.11468 v1: every search's 95% limit is its own procedure with the "
            "benchmark's detector-frame table" in at_plus and "budget of 2 full calculations" in at_plus)
    for halo in (None, halo_region.HaloPreset(), halo_choice.fixed()):                # the tables' note kept
        notes = " ".join(scan._scan_notes([], halo))
        assert "come from precomputed tables where they cover the mass (2 current" in notes
        assert "detector-frame table" not in notes
