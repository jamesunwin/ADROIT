"""Building certificates (``core.certificate``) for the producers of decisive claims: the checks each claim kind needs,
from what a producer has already computed (the consolidation plan's M1, 2026-10-25). The models, the states and the
reading of a certificate are in ``core.certificate``, re-exported here."""
from __future__ import annotations

import hashlib
import re

from functools import lru_cache

from adroit.core import file_reads
from adroit.core.certificate import (ASSESSMENTS, CLAIM_KINDS, LEGACY, OPEN, POLICY, Bound,  # noqa: F401
                                     Certificate, Check, assessment, reading, stale_reasons, survives)


def eos_identity(names=None) -> dict[str, str]:
    """The sha256 of each equation-of-state table as installed now ("" where missing or unreadable), or of the tables
    ``names`` only: what a stored certificate's tables are compared with (``current_bound``)."""
    from adroit.constraints import relic
    folder = relic.eos_folder()
    out = {}
    for name, (file, _) in relic.EOS_TABLES.items():
        if names is not None and name not in names:
            continue
        try:
            where = str(folder / file) if folder is not None else ""
            out[name] = file_reads.consistent(where, lambda *version: _sha256(where, *version)) if where else ""
        except OSError:
            out[name] = ""
    return out


def eos_held(names=None) -> dict[str, str]:
    """The sha256 of each table, or of the tables ``names`` only, as the calculation in force read it
    (``constraints.eos_reads``: its prerequisite's check, or the table it used, as published): what a thermal
    certificate is bound to. Read as installed now only for a table the calculation did not read, or outside every
    calculation (the auditor's CT recheck, CU-02, 2026-10-28: the files had been hashed when the certificate was made, so a
    table changed after its use was bound as if it had been used)."""
    from adroit.constraints import eos_reads, relic
    held = eos_reads.held() or {}
    wanted = [n for n in relic.EOS_TABLES if names is None or n in names]
    unread = [n for n in wanted if n not in held]
    now = eos_identity(unread) if unread else {}
    return {n: held[n] if n in held else now.get(n, "") for n in wanted}


@lru_cache(maxsize=16)
def _sha256(path: str, *version: int) -> str:
    """A file's sha256, read once per version (``file_reads.identity``: its inode and change time too, so that a
    replacement keeping the size and the modification time is read again), and of exactly that version's bytes: the
    history pages ask for it on every listing (the auditor's CU recheck, CV-03, 2026-10-28: kept by the size and the
    modification time, a replaced table went on reading as the published one)."""
    return hashlib.sha256(file_reads.read(path, version)).hexdigest()


def record_fingerprints(ids) -> dict[str, str]:
    """Each record's content fingerprint (``review_identity.fingerprint``) as it reads now; "" for one that cannot be
    read (a personal library's record, a record removed), and for every one while the records themselves cannot be
    read (the auditor's CR recheck, CS-05, 2026-10-27: a damaged records file had raised from here, through every page that
    assesses a saved study, and the Studies page failed for the unrelated studies too; a claim bound to a record then
    reads stale, naming it)."""
    import yaml
    from adroit.constraints import database
    from adroit.constraints.review_identity import fingerprint
    out = {}
    for record in sorted(set(ids)):
        try:
            out[record] = fingerprint(database.record(record))
        except (KeyError, OSError, ValueError, TypeError, AttributeError, yaml.YAMLError):
            out[record] = ""
    return out


def current_bound(certificate: Certificate) -> Bound:
    """The data a stored certificate is bound to, as they are now (``core.certificate.stale_reasons``): the tables'
    hashes where it was bound to tables, the fingerprints of the records it names."""
    from adroit.core.halo_choice import data_identity
    return Bound(eos_tables=eos_identity(certificate.bound.eos_tables) if certificate.bound.eos_tables else {},
                 records=record_fingerprints(certificate.bound.records) if certificate.bound.records else {},
                 halo_data=data_identity(tuple(certificate.bound.halo_data)) if certificate.bound.halo_data else {})


def assessed(certificates: list) -> str:
    """``core.certificate.assessment`` against the data as they are now (``current_bound``), each table's hash and
    each record's fingerprint read once for them all (a headline can rest on hundreds of claims, each bound to every
    record it used: CS-02)."""
    from adroit.core.halo_choice import data_identity
    names = {r for c in certificates if c is not None for r in c.bound.records}
    tables = {t for c in certificates if c is not None for t in c.bound.eos_tables}
    halo = tuple(sorted({h for c in certificates if c is not None for h in c.bound.halo_data}))
    prints, hashes = record_fingerprints(names) if names else {}, eos_identity(tables) if tables else {}
    files = data_identity(halo) if halo else {}
    return assessment(certificates, [Bound(eos_tables={t: hashes.get(t, "") for t in c.bound.eos_tables},
                                           records={r: prints.get(r, "") for r in c.bound.records},
                                           halo_data={h: files.get(h, "") for h in c.bound.halo_data})
                                     if c is not None else None for c in certificates])


def finite_check(evaluation, excluded: bool = False) -> Check:
    """The CA-03 boundary as a check: every ratio and Δχ² a finite number (``verdict.unfinite``). An exclusion rests on
    the finite comparisons alone (``verdict._combination``: their q is a lower bound), so for it the check holds."""
    from adroit.parameter_space.verdict import unfinite, unfinite_reasons
    if evaluation is None:
        return Check(name="finite_comparisons", state="unknown", reason="no comparisons were saved with the point")
    bad = unfinite(evaluation.ratios, evaluation.chi2)
    if bad and not excluded:
        return Check(name="finite_comparisons", state="unknown", reason="; ".join(unfinite_reasons(bad)))
    return Check(name="finite_comparisons", state="satisfied",
                 reason="the exclusion rests on the finite comparisons alone" if bad else "")


def history_check(evaluation) -> Check:
    """A06 as a check: Ωh² from a supported thermal history."""
    if evaluation is None:
        return Check(name="thermal_history", state="unknown", reason="no comparisons were saved with the point")
    if evaluation.relic_validity:
        return Check(name="thermal_history", state="failed",
                     reason=f"Ωh² is outside the supported thermal history: {evaluation.relic_validity[0]}")
    return Check(name="thermal_history", state="satisfied")


def halo_check(halo_label: str) -> Check:
    """The halo region as a check: decided alike over it (satisfied), sensitive to it (failed), or incomplete
    (unknown); the published halo alone, or one fixed benchmark, not applicable."""
    from adroit.parameter_space import halo_region
    if not halo_label:
        return Check(name="halo", state="not_applicable", reason="the published halo alone")
    if halo_label == halo_region.AT_BENCHMARK:
        return Check(name="halo", state="not_applicable",
                     reason="one fixed benchmark halo; the halo's uncertainty is not propagated")
    if halo_label in (halo_region.ALLOWED, halo_region.EXCLUDED):
        return Check(name="halo", state="satisfied", reason=halo_label)
    if halo_label == halo_region.SENSITIVE:
        return Check(name="halo", state="failed", reason=f"halo: {halo_label}")
    return Check(name="halo", state="unknown", reason=f"halo: {halo_label}")


def discovery_check(pending: list[str], discovery, excluded: bool = False) -> Check:
    """The discovery requirements as a check: none in force, or the point excluded (an exclusion stands whatever is
    still to be discovered: ``verdict.discovered``), not applicable; none covering the point, satisfied; one
    unresolved, unknown."""
    if not discovery:
        return Check(name="discovery", state="not_applicable", reason="no discovery assessment in force")
    if excluded:
        return Check(name="discovery", state="not_applicable", reason="an exclusion stands whatever is undiscovered")
    texts = {d.text for d in discovery}
    found = [p for p in pending if p in texts]
    if found:
        return Check(name="discovery", state="unknown", reason=found[0])
    return Check(name="discovery", state="satisfied")


def records_qualifiers(enabled: bool, used: list[str]) -> list[str]:
    """D-4: the claim's dependence apart from the run's setting: "depends on unverified records: <ids>" where the
    claim's constraints used one; "unverified records enabled for this run (this claim uses none)" where the setting
    is on and it used none."""
    if used:
        return [f"depends on unverified records: {', '.join(sorted(used))}"]
    return ["unverified records enabled for this run (this claim uses none)"] if enabled else []


def records_check(enabled: bool, used: list[str], unknown: list[str] | tuple = ()) -> Check:
    """The records as a check. Verified records decided it, or unverified ones the run enabled, which the claim then
    states (``records_qualifiers``): satisfied either way. A record awaiting verification that the run did not enable
    leaves its constraint pending, which the claim's status already says. A record whose version used is not known
    (``unknown``: it changed while the calculation used it, or the result predates the record of versions) leaves
    the claim unknown: what it is bound to would not be what decided it (the auditor's CS recheck, CT-01, 2026-10-28)."""
    if unknown:
        return Check(name="records", state="unknown", reason=(
            f"which version of {', '.join(sorted(unknown))} the calculation used is not known (a record changed while "
            "it was in use, or the result predates the record of versions): run it again to certify"))
    if used:
        return Check(name="records", state="satisfied",
                     reason=f"unverified records enabled and used: {', '.join(sorted(used))}")
    return Check(name="records", state="satisfied",
                 reason="verified records only" + ("; unverified records enabled" if enabled else ""))


THERMAL = ("thermal_solution", "theory_band_membership", "path2_thermal_eligibility")


def density_check(record_id: str) -> Check:
    """A thermal claim's relic target read from a record awaiting a person's verification, in a run that does not
    enable unverified records: failed, so that the claim is pending on it (``certify``, AL1-07)."""
    return Check(name="relic target", state="failed",
                 reason=f"the relic target's record ({record_id}) awaits a person's verification: a thermal claim rests "
                        "on it only once it is verified, or in a run that enables unverified records")


def relic_target(enabled: bool) -> tuple[str, list[str]]:
    """A thermal level decided without a certificate (a scan's "overabundant" or "underabundant" with no thermal root,
    the single idea's "no thermal"): (why it waits on the relic target, or ""; the unverified records it rests on). The
    target's record awaiting a person's verification makes it wait, as ``certify`` makes a thermal claim wait, unless
    the run enables unverified records, and then it rests on that record (AL2-06: these levels had been decided from
    the grid's Ωh² against an unverified target)."""
    from adroit.constraints.planck import ID as DENSITY_RECORD
    from adroit.parameter_space.likelihood import DENSITY_USABLE
    if DENSITY_USABLE:
        return "", []
    return ("", [DENSITY_RECORD]) if enabled else (density_check(DENSITY_RECORD).reason, [])


def versions_used(*found: dict[str, str]) -> dict[str, str]:
    """The versions of the records several pieces of evidence used, merged: "" for a record they used in different
    versions, which no one binding can describe (CT-01)."""
    out: dict[str, str] = {}
    for versions in found:
        for rid, v in versions.items():
            out[rid] = v if out.setdefault(rid, v) == v else ""
    return dict(sorted(out.items()))


def certify(c, claim_kind: str, scope: str, checks: list[Check], *, enabled: bool = False, discovery=None,
            computed: tuple[str, list[str]] | None = None, eos: bool | tuple[str, ...] | None = None):
    """A point's ``Crossing`` (or any model with ``status``, ``excluded_by``, ``pending`` and ``evaluation``) with its
    certificate: the claim's own ``checks``, then those every point claim needs (the thermal history where the claim
    is thermal, finite comparisons, records, discovery, the halo region), bound to the data read; and gated: a decided
    point with a failed or unknown check is pending with that check's reason, the status its computed constraints
    gave (``computed``, by default the point's own) kept in the certificate (D-2). The records the claim depends on
    are its own constraints' and those its checks' evidence used (``Check.records``: the auditor's consolidation audit,
    CO-03, 2026-10-25). Every record the claim and that evidence used, verified or not, is bound (``Bound.records``:
    the auditor's CR recheck, CS-02, 2026-10-27) with the version the calculation used (``PointResult.records``,
    ``Check.evidence_records``), never the version read now (the auditor's CS recheck, CT-01, 2026-10-28: an edit between
    the evaluation and its certificate had been bound as if it had been used); the unverified ones are those the
    claim's qualifier names. A record whose version used is not known leaves the claim uncertified
    (``records_check``). A thermal claim is bound to the density record its target was read from too
    (``likelihood.DENSITY_VERSION``: CT-02); a fixed-point exclusion, which no relic density decides, is not. Where that
    record, as read, awaits a person's verification, a thermal claim is pending on it (``density_check``) unless the
    run enables unverified records, and then depends on it as on any unverified record (the audit loop's AL1-07,
    2026-11-14: its target had been taken from the unverified record and the claim read "verified records only").

    The equation-of-state tables the claim was decided with are bound here, for every producer (the auditor's CO recheck,
    CR-01, 2026-10-26: the single-idea study and Path 2's eligibility had left them out, so a changed table never
    made their certificates stale): by default (``eos`` None) every table where the claim has an applicable
    ``eos_band`` check; ``eos`` names the tables of a table's own point or root, the one it was computed with."""
    from adroit.constraints.planck import ID as DENSITY_RECORD
    from adroit.parameter_space.likelihood import DENSITY_USABLE, DENSITY_VERSION
    status, excluded_by = computed if computed is not None else (c.status, list(c.excluded_by))
    evaluation = getattr(c, "evaluation", None)
    thermal = claim_kind in THERMAL
    awaiting = thermal and not DENSITY_USABLE          # the relic target's record awaits verification (AL1-07)
    # the claim's records: its own constraints' and those of the evidence its checks rest on (CO-03)
    used = sorted({*(evaluation.unverified_records if evaluation is not None else []),
                   *(r for x in checks for r in x.records), *([DENSITY_RECORD] if awaiting and enabled else [])})
    found = versions_used(*([evaluation.records] if evaluation is not None else []),
                          *(x.evidence_records for x in checks),
                          *([{DENSITY_RECORD: DENSITY_VERSION}] if thermal else []))
    bound = dict(sorted({**{r: "" for r in used}, **found}.items()))    # an unverified record's version not noted:
                                                                         # not known (a result from before CS-02)
    excluded = status == "excluded"
    every = [*checks, *([history_check(evaluation)] if thermal else []), finite_check(evaluation, excluded),
             records_check(enabled, used, [r for r, v in bound.items() if not v]),
             *([density_check(DENSITY_RECORD)] if awaiting and not enabled else []),
             discovery if isinstance(discovery, Check) else discovery_check(list(c.pending), discovery, excluded),
             halo_check(getattr(c, "halo", "") or _halo_label(evaluation)), *halo_data_check(evaluation)]
    certificate = Certificate(
        claim_kind=claim_kind, scope=scope, checks=every, computed_status=status,
        computed_excluded_by=excluded_by if c.status != status else [],
        qualifiers=records_qualifiers(enabled, used),
        bound=Bound(eos_tables=_eos_bound(eos, checks), unverified_records=used, records=bound,
                    halo=evaluation.halo.region if evaluation is not None and evaluation.halo is not None else "",
                    halo_data=_halo_data(evaluation)),
        policy=POLICY)
    return gate(c, certificate)


def _halo_label(evaluation) -> str:
    """A point's halo label read from its saved evaluation, for a claim that keeps none of its own (an Explain a signal
    thermal point, a ``BandPoint``: before halo phase 1 its certificate read "the published halo alone" even over the
    region): its label over the region, or at the fixed benchmark; "" in the published-halo reproduction."""
    if evaluation is None or getattr(evaluation, "halo", None) is None:
        return ""
    from adroit.parameter_space.verdict import classify
    return classify(None, evaluation).halo


def _halo_data(evaluation) -> dict[str, str]:
    """The halo data files a point over a region or at a fixed benchmark was calculated with (``halo_choice.HALO_DATA``:
    the local densities and the count ratio's validation and declaration), each file's sha256 as its evaluation saved
    it (``HaloEvaluation.data``: ``halo_evaluation._reading``); none in the published-halo reproduction, which reads
    none of them. Never the files in force or as they are when the claim is certified (the auditor's HB recheck, HC-01,
    2026-11-11: a saved point whose verdict was taken again had been bound to the data in force then, not those it was
    calculated with). A point saved before they were recorded has each named, not known (""), and its claim is not
    certified (``halo_data_check``); so has a file its record names by what is not a sha256 (HD-01), never bound as an
    identity a reader would compare."""
    from adroit.core.halo_choice import HALO_DATA
    halo = getattr(evaluation, "halo", None) if evaluation is not None else None
    if halo is None:
        return {}
    data = getattr(halo, "data", None) or {}
    return {name: data[name] if isinstance(data.get(name), str) and _SHA256.fullmatch(data[name]) else ""
            for name in HALO_DATA}


_SHA256 = re.compile(r"[0-9a-f]{64}")


def halo_data_check(evaluation) -> list[Check]:
    """A point over a region or at a fixed benchmark whose record of the halo data files it was calculated with is not
    whole, as a check: unknown, and its claim not certified, as for a record whose version used is not known
    (``records_check``); none where each file (``halo_choice.HALO_DATA``) has its sha256 recorded.

    Not whole: no record (a result from before HC-01); a file not named, recorded as missing when the point read it, or
    named by what is not a sha256. The auditor's HC recheck (HD-01, 2026-11-12) had found a record naming only some files,
    or none of them, certified: the check had asked only whether the record was empty, and a missing identity bound
    as "" was never read as stale."""
    from adroit.core.halo_choice import HALO_DATA
    halo = getattr(evaluation, "halo", None) if evaluation is not None else None
    if halo is None:
        return []
    data = getattr(halo, "data", None) or {}
    if not data:
        return [Check(name="halo_data", state="unknown", reason=(
            "which halo data files (the local densities, the count ratio's validation) this point was calculated "
            "with is not known (a result from before they were recorded): run it again to certify"))]
    wrong = [f"{name}: {'not recorded' if name not in data else 'missing when the point read it' if data[name] == '' else 'not a sha256'}"
             for name in HALO_DATA if not (isinstance(data.get(name), str) and _SHA256.fullmatch(data[name]))]
    if not wrong:
        return []
    return [Check(name="halo_data", state="unknown", reason=(
        "the record of the halo data files this point was calculated with is not whole (" + "; ".join(wrong) +
        "): run it again to certify"))]


def _eos_bound(eos: bool | tuple[str, ...] | None, checks: list[Check]) -> dict[str, str]:
    """The tables a certificate is bound to (``certify``), as its calculation read them (``eos_held``)."""
    if eos is None:
        eos = any(x.name == "eos_band" and x.state != "not_applicable" for x in checks)
    if eos is True:
        return eos_held()
    return eos_held(eos) if eos else {}


def gate(c, certificate: Certificate):
    """``c`` with its certificate; where the certificate is not decided and ``c`` is, pending with the open checks'
    reasons (each once), its exclusions moved into the certificate (``computed_excluded_by``)."""
    if certificate.decided or c.status not in ("viable", "excluded"):
        return c.model_copy(update={"certificate": certificate})
    if c.status == "excluded" and not certificate.computed_excluded_by:
        certificate = certificate.model_copy(update={"computed_excluded_by": list(c.excluded_by)})
    reasons = [r for r in certificate.open_reasons() if r not in c.pending]
    return c.model_copy(update={"status": "pending", "excluded_by": [], "pending": [*c.pending, *reasons],
                                "certificate": certificate})


def summary_lines(points: list, what: str = "points") -> list[str]:
    """One line on a report: how many of ``points`` are certified, which are not and why (the commonest reasons), how
    many are legacy (no certificate), and what qualifies them (D-4); read from the stored certificates, never
    re-derived."""
    from collections import Counter
    if not points:
        return []
    certificates = [getattr(p, "certificate", None) for p in points]
    legacy = sum(c is None for c in certificates)
    # each certificate's outcome as stored, under the policy it was made under; that policy being an earlier one is
    # said apart (the owner's EOS review, 2026-11-23: a stale certificate had been counted as neither certified nor not)
    certified = sum(c is not None and c.decided for c in certificates)
    waiting = [c for c in certificates if c is not None and not c.decided]
    earlier = sorted({c.policy for c in certificates if c is not None and c.policy != POLICY})
    stale = sum(c is not None and c.policy != POLICY for c in certificates)
    text = f"Certification of these {len(points)} {what}: {certified} certified"
    if waiting:
        why = Counter(c.open_reasons()[0] for c in waiting).most_common(2)
        text += f"; {len(waiting)} not certified ({'; '.join(f'{n} × {r}' for r, n in why)})"
    if stale:
        text += (f"; {'all' if stale == len(points) else stale} made under an earlier policy "
                 f"({', '.join(earlier)}), as stored, not re-assessed (stale)")
    if legacy:
        text += f"; {legacy} {LEGACY} (written before certificates)"
    qualifiers = sorted({q for c in certificates if c is not None for q in c.qualifiers})
    return [text + ("; " + "; ".join(qualifiers) if qualifiers else "") + "."]


THERMAL_CHECKS = ("root", "eos_band", "thermal_history")      # a thermal claim's own checks, not the experiments'


def experimental_exclusion(point) -> list[str]:
    """The constraints that exclude a point by its computed comparisons where only its thermal claim's own checks
    (``THERMAL_CHECKS``) are open, else []: from the stored ``computed_status``, ``computed_excluded_by`` and checks,
    never re-derived. An open experimental check (its comparisons, records, halo or discovery) leaves it [], the
    experimental exclusion itself not established (the owner, 2026-11-23)."""
    c = getattr(point, "certificate", None)
    if c is None or getattr(point, "status", "") != "pending" or c.computed_status != "excluded":
        return []
    if any(x.state in OPEN and x.name not in THERMAL_CHECKS for x in c.checks):
        return []
    return list(c.computed_excluded_by)


def central_exclusion(point) -> str:
    """A point the region leaves pending that its comparisons excluded at the region's centre, in words ("excluded at
    the central SHM by direct detection; halo robustness incomplete" or "...; halo-sensitive across the tested
    region"), else "": the central exclusion shown, qualified, never reduced to plain pending nor called robust (the
    owner's plan of 2026-11-24, section 3; ``assessment.experimental_words``, from the stored point)."""
    from adroit.parameter_space.assessment import REGION, experimental_words, from_crossing
    if getattr(point, "status", "") == "excluded" or getattr(point, "halo", "") not in REGION \
            or getattr(point, "nominal_status", "") != "excluded":
        return ""
    return experimental_words(from_crossing(point))


def status_words(point) -> str:
    """A point's stored status, with the status its computed constraints gave where its certificate's gate changed it
    ("pending (computed: excluded)"); "excluded by <constraints>" where only its thermal claim is open
    (``experimental_exclusion``: the owner, 2026-11-23); a central exclusion the region leaves pending, qualified
    (``central_exclusion``: the owner, 2026-11-24)."""
    if by := experimental_exclusion(point):
        return f"excluded by {', '.join(by)}"
    if words := central_exclusion(point):
        return words
    c = getattr(point, "certificate", None)
    if c is not None and c.computed_status and c.computed_status != point.status:
        return f"{point.status} (computed: {c.computed_status})"
    return point.status
