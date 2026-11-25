"""The auditor's CU recheck (the independent audit of 2026-10-28 (cu recheck), 2026-10-28), each finding through its real consumer:
- CV-01: DarkCast's metadata (the darkcast-dark-photon record's data file) was kept for the process, so a changed mass
  resolution went on admitting an exclusion while the claim bound the changed file;
- CV-02: CMS's panel (``database.data``, read by the scan's collider comparison) and LEP's bounds (the record looked up
  again after its admission) were read in a version other than the one the claim was bound to;
- CV-03: the tables' current hashes were kept by size and modification time, so a replacement keeping both read as
  the published table (through the history in ``tests/ui/test_cv_history.py``);
- CV-04: a record's data and version, cached apart, could be of two versions after an eviction.
"""
from __future__ import annotations

import copy
import hashlib
import os
from unittest.mock import patch

import numpy as np
import pytest
import yaml

from adroit.constraints import database, hadrons, relic, review_identity
from adroit.constraints import searches as cs
from adroit.constraints.review_identity import version
from adroit.parameter_space import certification, halo_region, scan
from adroit.parameter_space import searches as ps
from adroit.parameter_space import verdict as v
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.scan import PointResult
from tests.orchestrator.test_cu_recheck import _rewrite, _scratch

DIJET = "cms-1806.00843-dijet"
CMS = "cms-2405.13778-V1"
LEP = "lep-charginos"
RERUN = "run it again to certify"


def _row(p, excluded: dict, pending: list | None = None) -> PointResult:
    return PointResult(point=p, omega_h2=.12, dd_kind="SI", dd_sigma_cm2=0, dd_limit_cm2=1, excluded=excluded,
                       pending=pending or [])


def _claim(row: PointResult, name: str):
    """The fixed-point claim a scan's evaluation makes of the search ``name``."""
    excluded = row.excluded[name]
    status = "excluded" if excluded else "pending" if excluded is None else "viable"
    crossing = v.Crossing(point=row.point, status=status, excluded_by=[name] if excluded else [],
                          pending=row.pending, evaluation=row)
    return certification.certify(crossing, "fixed_point_exclusion", "the point", [], enabled=True)


def _reading(claim) -> str:
    return certification.reading(claim.certificate, certification.current_bound(claim.certificate))


def _below_hadrons(root_s) -> np.ndarray:
    """``hadrons.r_ratio`` where it needs no table: 0 below 0.30 GeV; this test asks nothing above."""
    root_s = np.asarray(root_s, dtype=float)
    assert (root_s < .30).all(), "the R ratio is asked above the hadronic threshold"
    return np.zeros_like(root_s)


def test_a_changed_darkcast_resolution_is_read_at_once_and_its_version_bound(tmp_path, monkeypatch):
    """CV-01, the auditor's case: a dark photon (m_A′ = 0.1 GeV, m_χ = 1 GeV, ε = 0.1; Γ = 2.47 keV) against A1 alone,
    whose stated resolution, 89 keV, admits it: excluded. The resolution changed to 1 keV, the warm process reads it
    as a fresh one does: the search no longer applies at this width, and the point is pending; each evaluation is
    bound to the metadata it read, and the first claim reads stale. DarkCast's own limit is a fixture (it excludes,
    ratio 2): what is checked is the record's metadata. So is the R ratio, which at 0.1 GeV is 0 by its own definition
    (``hadrons.r_ratio``: 0 below 0.30 GeV), so that the test needs no PDG file (the auditor's CV recheck, CW-03)."""
    rid, stem = "darkcast-dark-photon", "A1_Merkel2014avp"
    monkeypatch.setattr(hadrons, "r_ratio", _below_hadrons)
    data = copy.deepcopy(database.data(rid))
    monkeypatch.setattr(review_identity, "PROJECT_ROOT", tmp_path)
    path, record, reading = _scratch(rid, tmp_path, data)
    for group, stems in (("VISIBLE_PROMPT", [stem]), ("VISIBLE_DISPLACED", []), ("INVISIBLE", [])):
        monkeypatch.setattr(ps, group, stems)
    tool = cs._tool
    monkeypatch.setattr(cs, "_tool", lambda name: tmp_path if name == "DarkCast" else tool(name))
    monkeypatch.setattr(cs, "darkcast_excludes", lambda stem, m, coupling: True)
    monkeypatch.setattr(cs, "darkcast_ratio", lambda stem, m, coupling: 2.0)
    from adroit.parameter_space.portals.vector import DarkPhoton
    p = Point(m_chi=1., m_med=.1, g_chi=.1, g_q=.1)

    def evaluator(cls, p, *args, **kwargs):
        out = ps.dark_photon(cls, p, True)
        return _row(p, {ps.DARK_PHOTON: out.excluded}, [out.why] if out.excluded is None else [])

    with reading, patch.object(scan, "_evaluate", evaluator), patch.object(halo_region, "preset", lambda: None):
        cs._bundled.cache_clear()
        first = scan.evaluate(DarkPhoton(), p, True)
        old = version(record)
        data["searches"][stem]["resolution_gev"] = 1e-6
        _rewrite(path, yaml.safe_dump(data).encode(), 2)
        warm = scan.evaluate(DarkPhoton(), p, True)
        cs._bundled.cache_clear()
        cold = scan.evaluate(DarkPhoton(), p, True)
        new = version(record)
        assert first.excluded == {ps.DARK_PHOTON: True}
        assert warm.excluded == cold.excluded == {ps.DARK_PHOTON: None} and warm.pending == cold.pending
        assert "is not below its mass resolution, 0.001 MeV" in warm.pending[0]
        assert first.records[rid] == old and warm.records[rid] == new != old
        assert _reading(_claim(first, ps.DARK_PHOTON)) == f"stale: the record {rid} changed since it was certified"
    cs._bundled.cache_clear()


def test_a_collider_panel_read_in_another_version_than_admitted_leaves_its_version_unknown(tmp_path, monkeypatch):
    """CV-02, the auditor's CMS case: the scan's collider comparison (``scan._collider`` → ``verdicts.collider`` →
    ``database.data``) at the benchmark m_DM = 100 GeV, m_med = 1 TeV. Its panel is A (no excluded region) when the
    record is admitted and after; B (a region holding the point) while the panel is read. The evaluation excludes on
    B, so it may be bound to neither A nor B alone: its version is unknown and the claim is not certified. Read as A
    throughout, it allows the point, bound to A, certified."""
    data = copy.deepcopy(database.data(CMS))
    monkeypatch.setattr(review_identity, "PROJECT_ROOT", tmp_path)
    a = copy.deepcopy(data)
    a["panels"]["V1"]["searches"] = {}
    b = copy.deepcopy(a)
    b["panels"]["V1"]["searches"] = {"a region": {"excluded_regions": [[[500, 0], [2000, 0], [2000, 200], [500, 200]]],
                                                  "observed": []}}
    path, record, reading = _scratch(CMS, tmp_path, a)
    first, second = path.read_bytes(), yaml.safe_dump(b).encode()
    real = database.data

    def in_b(record_id):
        if record_id != CMS:
            return real(record_id)
        path.write_bytes(second)
        try:
            return real(record_id)
        finally:
            path.write_bytes(first)

    def evaluator(cls, p, *args, **kwargs):
        return _row(p, {"colliders (CMS)": scan._collider(cls, p, True).excluded})

    p = Point(m_chi=100, m_med=1000, g_chi=1, g_q=.25, g_l=0)
    with reading, patch.object(scan, "_evaluate", evaluator), patch.object(halo_region, "preset", lambda: None):
        cs._bundled.cache_clear()
        normal = scan.evaluate(Spin1Class(), p, True)
        with patch.object(database, "data", in_b):
            raced = scan.evaluate(Spin1Class(), p, True)
        assert normal.excluded == {"colliders (CMS)": False} and normal.records == {CMS: version(record)}
        assert raced.excluded == {"colliders (CMS)": True} and raced.records == {CMS: ""}
        claim = _claim(raced, "colliders (CMS)")
        assert claim.status == "pending" and RERUN in claim.certificate.check("records").reason
        assert _reading(_claim(normal, "colliders (CMS)")).startswith("certified")
    cs._bundled.cache_clear()


def test_a_record_looked_up_again_in_another_version_than_admitted_leaves_its_version_unknown(tmp_path, monkeypatch):
    """CV-02, the auditor's LEP case: a chargino at 100 GeV, 20 GeV above the dark matter, against the record's bounds from a
    records file: A (every bound 50 GeV: allowed) when the record is admitted (``_blocked``), B (200 GeV: excluded) when
    it is looked up again for its bounds, A after. The evaluation excludes on B, so its version is unknown and the
    claim is not certified; looked up as A throughout, it is bound to A and certified."""
    held = database.record(LEP)
    a = held.model_copy(update={"data": {k: 50. for k in held.data}, "verified_by": "", "verified_on": None,
                                "verification_sha256": ""})
    b = a.model_copy(update={"data": {k: 200. for k in held.data}})
    first, second = (yaml.safe_dump({"records": [r.model_dump(mode="json")]}).encode() for r in (a, b))
    path = tmp_path / "records.yaml"
    path.write_bytes(first)
    monkeypatch.setattr(database, "RECORDS", path)
    real, lookups = cs._record, []

    def second_in_b(record_id):
        lookups.append(record_id)
        if len(lookups) != 2:
            return real(record_id)
        path.write_bytes(second)
        try:
            return real(record_id)
        finally:
            path.write_bytes(first)

    def evaluator(cls, p, *args, **kwargs):
        return _row(p, {ps.LEP_CHARGED: ps._lep_state("chargino", "", 100., 20., True).excluded})

    p = Point(m_chi=80, m_med=100)
    with patch.object(scan, "_evaluate", evaluator), patch.object(halo_region, "preset", lambda: None):
        normal = scan.evaluate(Spin1Class(), p, True)
        with patch.object(cs, "_record", second_in_b):
            raced = scan.evaluate(Spin1Class(), p, True)
    assert lookups == [LEP, LEP]
    assert normal.excluded == {ps.LEP_CHARGED: False} and normal.records == {LEP: version(a)}
    assert raced.excluded == {ps.LEP_CHARGED: True} and raced.records == {LEP: ""}
    claim = _claim(raced, ps.LEP_CHARGED)
    assert claim.status == "pending" and RERUN in claim.certificate.check("records").reason
    assert _reading(_claim(normal, ps.LEP_CHARGED)).startswith("certified")


def test_a_record_data_and_version_are_of_one_read_after_an_eviction(tmp_path, monkeypatch):
    """CV-04, the auditor's case: A's data and version cached, A's data then evicted (its version kept), and the file
    replaced by B (a limit a hundred times weaker) after it is stat'ed and before it is read. The data and the version
    returned are one version's, B's; within an evaluation that admitted A, two versions were read, and the version is
    unknown, though the file is A again before the end."""
    data = copy.deepcopy(database.data(DIJET))
    monkeypatch.setattr(review_identity, "PROJECT_ROOT", tmp_path)
    path, record, reading = _scratch(DIJET, tmp_path, data)
    first = path.read_bytes()
    second = yaml.safe_dump({**data, "limit": [[m, 100 * x] for m, x in data["limit"]]}).encode()
    where, real_stat, armed = str(path.resolve()), os.stat, []

    def stat_then_replace(target, *args, **kwargs):          # replaced once, between its stat and its read
        out = real_stat(target, *args, **kwargs)
        if armed and armed[0] and os.path.realpath(os.fspath(target)) == where:
            armed[0] = False
            path.write_bytes(second)
        return out

    def raced(read):
        path.write_bytes(first)
        cs._bundled(DIJET)                                    # A's data and version cached
        review_identity._data.cache_clear()                   # A's data evicted, its version kept
        assert review_identity._fingerprint.cache_info().currsize
        armed[:] = [True]
        with patch.object(os, "stat", stat_then_replace):
            return read()

    with reading:
        cs._bundled.cache_clear()
        a = version(record)
        held, held_version = raced(lambda: review_identity.snapshot(record))
        b = version(record)
        assert held["limit"][0][1] == 100 * data["limit"][0][1] and held_version == b != a
        with cs.records_used() as every:
            path.write_bytes(first)
            cs.admits(database.record(DIJET), True)
            raced(lambda: cs._bundled(DIJET))
            path.write_bytes(first)
        assert every == {DIJET: ""} and cs.confirmed(every) == {DIJET: ""}
    cs._bundled.cache_clear()


def _same_length(content: bytes) -> bytes:
    """``content`` with its last digit changed: the same length, other bytes."""
    i = next(i for i in range(len(content) - 1, -1, -1) if chr(content[i]).isdigit())
    return content[:i] + (b"2" if content[i:i + 1] == b"1" else b"1") + content[i + 1:]


@pytest.mark.needs("eos")
@pytest.mark.parametrize("how", ["replaced", "rewritten in place"])
def test_a_table_changed_keeping_its_size_and_modification_time_reads_changed(eos_copy, how):
    """CV-03, the auditor's case at its source: the current hash of the central table read (and cached), then the file
    replaced by other bytes of the same length (a new file renamed over it, or rewritten in place), its modification
    time set back. The current hash is the new bytes', so a certificate bound to the published table reads stale; the
    table restored, it reads certified again."""
    name, (file, published) = "central", relic.EOS_TABLES["central"]
    table = eos_copy / file
    original, stat = table.read_bytes(), table.stat()
    changed = _same_length(original)
    assert certification.eos_identity([name]) == {name: published}

    def put(content: bytes) -> None:
        if how == "replaced":
            fresh = table.with_name(file + ".new")
            fresh.write_bytes(content)
            os.replace(fresh, table)
        else:
            table.write_bytes(content)
        os.utime(table, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    bound = certification.Certificate(claim_kind="thermal_solution", scope="a root", policy=certification.POLICY,
                                      bound=certification.Bound(eos_tables={name: published}))
    put(changed)
    now = table.stat()
    assert (now.st_size, now.st_mtime_ns) == (stat.st_size, stat.st_mtime_ns)
    assert certification.eos_identity([name]) == {name: hashlib.sha256(changed).hexdigest()}
    assert certification.reading(bound, certification.current_bound(bound)) == \
        f"stale: the equation of state's {name} table is not the one it was certified with"
    put(original)
    assert certification.eos_identity([name]) == {name: published}
    assert certification.reading(bound, certification.current_bound(bound)) == "certified"
