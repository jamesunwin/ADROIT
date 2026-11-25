"""A decisive claim's certificate (the consolidation plan's M1, 2026-10-25): its models, kept in ``core`` so that
every producer can carry one (``parameter_space.certification`` builds them).

Different parts of ADROIT had read the same incomplete evidence differently (the combined audit's V1-01, the
consistency audit's CA-01–CA-03): the equation-of-state tables missing made one producer wait and another decide. A
decisive claim now carries a ``Certificate``: what kind of claim it is (``CLAIM_KINDS``) and over what (``scope``),
each check it needs with its state, the status the computed constraints gave before the certificate's gate
(``computed_status``), the data it was decided on (``Bound``), and the policy it was made under (``POLICY``).

The states of a check (``Check.state``):

- **satisfied**: the condition holds;
- **failed**: a physical condition shown not to hold (a thermal history outside the supported one; the
  equation-of-state tables disagreeing; the halo region disagreeing);
- **unknown**: evidence missing (the tables not installed or not as published, a calculation that did not finish, a
  comparison that is not a finite number). A missing calculation is never a demonstrated failure;
- **not_applicable**: the claim does not need it (an experimental exclusion of a fixed point needs no thermal check).

An exclusion is a result, not a failed prerequisite. A claim with a failed or unknown check is not decided: it is
pending with that check's reason, and the status its computed constraints gave stays in ``computed_status`` and
``computed_excluded_by`` (the owner's direction D-2: a waiting set that is all excluded by its computed constraints
reads "pending", not "viable, pending").

A result written before certificates has none: it reads "legacy, not assessed" (``reading``), unchanged, and never
acquires one silently; a certificate made under an earlier policy reads stale, and so does one whose bound data have
changed since (``stale_reasons``: an equation-of-state table no longer the one it was decided with, a record the
claim used whose content changed). The history pages show that assessment beside the stored level (``assessment``).

A certificate states the policy it was made under: there is no default, so a stored one whose policy is missing does
not load, and is named as damaged rather than read as made under the present policy (the auditor's CR recheck, CS-01,
2026-10-27: the constructor's default had supplied the present policy to a damaged certificate, which then read
certified).
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BeforeValidator, Field

from adroit.core.state import StrictModel

POLICY = "consistency-eos-nominal-2026-11-23"   # the owner, 2026-11-23: a thermal claim no longer needs the
                                          # equation of state's band (``EOS_POLICY``); the policy before it was
                                          # "consistency-hd-2026-11-12", under which the band was a prerequisite.
                                          # Changed whenever a claim kind's checks or bindings change (CO-01–CO-03:
                                          # every supporting table root certified, its records the claim's; CR-01:
                                          # every producer binds the tables it used; CS-02: every record a claim used,
                                          # verified or not, is bound; CT-01: as the evaluation held it; CT-02: a
                                          # thermal claim's target record too; CU-01, CU-02, CU-04: each record's data
                                          # and each table in the version read; CV-01, CV-02, CV-04: DarkCast's
                                          # metadata, every data read and every record looked up, each version read;
                                          # HC-01, HD-01, HD-05: a halo-dependent claim binds the halo data files its
                                          # point read, every one by a recorded identity, not those in force or as
                                          # they were when it was certified;
                                          # so earlier certificates read stale)


# The equation-of-state policy (the owner's decision of 2026-11-23, for 1.0.0): Ωh² is computed with ADROIT's nominal
# degrees of freedom, Saikawa & Shirai's 2018 fit (``relic.degrees_of_freedom``), and a thermal claim is decided on
# that nominal calculation. The uncertainty of the equation of state, its band across Saikawa & Shirai's 2020 upper
# and lower tables (``relic.EOS_BAND``), is not propagated: its assessment is deferred to 1.0.2
# (the deferred list, EOS-01). Every thermal claim's ``eos_band`` check is then ``not_applicable`` with
# ``EOS_NOT_ASSESSED`` as its reason (``nominal_eos_check``): not satisfied, and not robustness across the tables; no
# claim reads or binds the 2020 tables, which need not be installed. Every producer asks ``eos_band_assessed``, the
# one switch; ``EOS_BAND_ASSESSED`` restores the deferred assessment for its own tests and 1.0.2's work, and is set
# by nothing in the workbench or the command line.
EOS_POLICY = "nominal"
EOS_BAND_ASSESSED = False
EOS_NOT_ASSESSED = ("not assessed: ADROIT 1.0 computes Ωh² with its nominal equation of state (Saikawa & Shirai's "
                    "2018 fit); its uncertainty across Saikawa & Shirai's 2020 upper and lower tables is not "
                    "propagated (deferred to 1.0.2)")


def eos_band_assessed() -> bool:
    """Whether thermal claims assess the equation of state's band (False under ``EOS_POLICY`` "nominal")."""
    return EOS_BAND_ASSESSED


def nominal_eos_check() -> "Check":
    """A thermal claim's ``eos_band`` check under the nominal policy: not applicable, and why."""
    return Check(name="eos_band", state="not_applicable", reason=EOS_NOT_ASSESSED)


def _versions(value):
    """A list of record ids, as results before CT-01 kept them, read as records whose version used is not known. A
    member that is not an id is damage, raised as a validation error (the auditor's CT recheck, CU-03, 2026-10-28: a list
    holding ``{}`` had raised TypeError past the readers' damage boundaries, and Studies was a server error)."""
    if not isinstance(value, list):
        return value
    if bad := [m for m in value if not isinstance(m, str)]:
        raise ValueError(f"a list of record ids holds {type(bad[0]).__name__} {bad[0]!r}, not an id")
    return dict.fromkeys(value, "")


# the records used, each with the version used (``review_identity.version``; "" where it is not known)
Versions = Annotated[dict[str, str], BeforeValidator(_versions)]
LEGACY = "legacy, not assessed"
CLAIM_KINDS = {
    "fixed_point_exclusion": "an experimental exclusion of one point",
    "thermal_solution": "a certified thermal solution (a contour root, a coverage root, a single-idea thermal point)",
    "theory_band_membership": "a grid point inside the combined mode's relic band",
    "path2_thermal_eligibility": "Path 2's physical eligibility at the declared thermal target",
    "relic_comparison": "the complementary relic comparison (DM7)",
    "statistical_ranking": "an AIC ranking, a candidate's PG compatibility or a search-wide significance",
    "no_sampled_fit": "no sampled model fits the events",
    "no_thermal_explanation": "no thermal explanation over the searched band",
}
State = Literal["satisfied", "failed", "unknown", "not_applicable"]
OPEN = ("failed", "unknown")


class Check(StrictModel):
    """One prerequisite of a claim: its name, its state and why; the unverified records the evidence it rests on used
    (``records``: the equation of state's band rests on the tables' roots, whose constraints may use one), which the
    claim then depends on too (the auditor's consolidation audit, CO-03, 2026-10-25); and every record that evidence used,
    verified or not, with the version it used (``evidence_records``), which the claim is bound to (the auditor's CR recheck,
    CS-02, 2026-10-27; CS recheck, CT-01, 2026-10-28)."""
    name: str
    state: State
    reason: str = ""
    records: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)
    evidence_records: Versions = Field(default_factory=dict, exclude_if=lambda v: not v)


class Bound(StrictModel):
    """The data a certificate was decided on: the equation-of-state tables' sha256s as read ("" for one missing); every
    record the claim and the evidence supporting it used, verified or not, with its content fingerprint (``records``:
    ``review_identity.fingerprint``; "" where it could not be read, as for a personal record); of those, the ones used
    while unverified (``unverified_records``: what the claim's D-4 qualifier names); the halo region or fixed
    benchmark; and the halo data files its halo-dependent comparisons read (``halo_data``: each file's sha256, halo
    phase 1). A change in the tables, a record's content or a halo data file since reads stale (``stale_reasons``).
    Before the auditor's CR recheck (CS-02, 2026-10-27) only the unverified records were bound, so a reviewed record that
    decided a claim could change without the claim reading stale."""
    eos_tables: dict[str, str] = Field(default_factory=dict, exclude_if=lambda v: not v)
    unverified_records: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)
    records: dict[str, str] = Field(default_factory=dict, exclude_if=lambda v: not v)
    halo: str = Field(default="", exclude_if=lambda v: not v)
    halo_data: dict[str, str] = Field(default_factory=dict, exclude_if=lambda v: not v)


class Certificate(StrictModel):
    """A decisive claim's certification (module docstring)."""
    claim_kind: str
    scope: str
    checks: list[Check] = Field(default_factory=list)
    computed_status: str = ""                 # the computed constraints' status, before the gate
    computed_excluded_by: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)
    qualifiers: list[str] = Field(default_factory=list, exclude_if=lambda v: not v)
    bound: Bound = Field(default_factory=Bound)
    policy: str                               # the policy it was made under (``POLICY`` when made): no default

    @property
    def decided(self) -> bool:
        """Whether every check the claim needs is satisfied (or not applicable)."""
        return not any(c.state in OPEN for c in self.checks)

    def open_reasons(self) -> list[str]:
        """The failed and unknown checks' reasons, in order."""
        return [c.reason or c.name for c in self.checks if c.state in OPEN]

    def check(self, name: str) -> Check | None:
        """The check called ``name``, or None."""
        return next((c for c in self.checks if c.name == name), None)


def stale_reasons(certificate: Certificate, current: Bound | None = None) -> list[str]:
    """Why a stored certificate no longer describes the present reading, or []: made under an earlier policy; and, given
    the data as they are now (``current``: ``certification.current_bound``), an equation-of-state table other than the
    one it was decided with, or a record it used whose content changed or that cannot be read now (gone, or the
    records damaged), or a halo data file it read that changed or cannot be read. A table now missing is not a change
    of data (the historical decision stands, its tables named in ``bound``)."""
    reasons = []
    if certificate.policy != POLICY:
        reasons.append(f"certified under policy {certificate.policy}, not the current {POLICY}")
    if current is None:
        return reasons
    for name, sha in certificate.bound.eos_tables.items():
        now = current.eos_tables.get(name, "")
        if sha and now and now != sha:
            reasons.append(f"the equation of state's {name} table is not the one it was certified with")
    for record, fingerprint in certificate.bound.records.items():
        now = current.records.get(record, "")
        if fingerprint and now != fingerprint:
            reasons.append(f"the record {record} {'changed' if now else 'cannot be read'} since it was certified")
    for name, sha in certificate.bound.halo_data.items():
        now = current.halo_data.get(name, "")
        if sha and now != sha:
            reasons.append(f"the halo data file ({name}) {'changed' if now else 'cannot be read'} since it was "
                           "certified")
        elif not sha and certificate.decided:      # decided on a file it names no identity of (HD-01)
            reasons.append(f"the halo data file ({name}) it was certified with is not recorded")
    return reasons


def reading(certificate: Certificate | None, current: Bound | None = None) -> str:
    """A certificate in words: "legacy, not assessed" (none: a result from before certificates), "stale: <why>" (made
    under an earlier policy or, given ``current``, on data that have changed: ``stale_reasons``), "certified", or "not
    certified: <the open checks' reasons>"."""
    if certificate is None:
        return LEGACY
    if stale := stale_reasons(certificate, current):
        return "stale: " + "; ".join(stale)
    if certificate.decided:
        return "certified" + (f" ({'; '.join(certificate.qualifiers)})" if certificate.qualifiers else "")
    return "not certified: " + "; ".join(certificate.open_reasons())


def survives(status: str, certificate: Certificate | None) -> bool:
    """Whether a point survives its computed constraints: a waiting point is judged by the status they gave
    (``computed_status``), never by its own pending (D-2); a point without a certificate by its status."""
    computed = certificate.computed_status if certificate is not None and certificate.computed_status else status
    return computed != "excluded"


def held(field: str, positions: list[int], size: int) -> None:
    """Raise ``ValueError`` where ``positions``, the claims a stored headline rests on (``field``), name one that a
    list of ``size`` claims does not hold: the models of results check that their named support is their own, so a
    result whose support is missing is damaged, never read as resting on less (the auditor's CR recheck, CS-01, 2026-10-27:
    with the table points removed and their positions kept, an excluded headline had read certified)."""
    if bad := [i for i in positions if not 0 <= i < size]:
        raise ValueError(f"{field} names position{'s' if len(bad) > 1 else ''} {', '.join(map(str, bad))}, which the "
                         f"result does not hold ({size} there)")


ASSESSMENTS = ("certified", "not certified", "stale", "legacy")


def assessment(certificates: list[Certificate | None], current: list[Bound | None] | None = None) -> str:
    """The certification of the claims a stored headline rests on, in one word of ``ASSESSMENTS`` for the history
    pages (the auditor's consolidation audit, CO-07, 2026-10-25: a stale or legacy headline had looked like a current one):
    "legacy" where any has no certificate, else "stale" where any is stale (``stale_reasons``, with ``current`` the data
    now, one per certificate), else "not certified" where any is undecided, else "certified". The stored level is not
    changed by it; it is shown beside it."""
    if not certificates or any(c is None for c in certificates):
        return "legacy"
    now = current or [None] * len(certificates)
    if any(stale_reasons(c, b) for c, b in zip(certificates, now)):
        return "stale"
    return "certified" if all(c.decided for c in certificates) else "not certified"
