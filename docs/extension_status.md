# Audit and extension status — 10 October 2026 (corrected 12 October 2026)

ADROIT's goal is efficient integration of deterministic phenomenology components,
with optional LLMs improving interaction and additional checks. Greater accuracy
than those components is not a prerequisite for useful integration.

**Since this record was written (12 October 2026).** M32's release-closure audit
was carried out on 10 October 2026 (its report is kept with the development records). Its findings, and those of
the live checks, are being closed by the release plan R0–R12: R0–R8 are done,
R9 (record signatures) is under way, R10 and R11 are in progress, and R12 is
pending. The dated closure entries below keep the "next" steps they had when
written.

The requested user-workflow portion of **M32 was audited first (9 October); the rest of M32
followed on 10 October** (above). Its two approval/scan defects are resolved by **M33–M34**, with 1366 fast/25
slow tests, exact-model/scan-review identity checks, real CLI/Track 2 reuse and
new/legacy replay checks. See [model approval and scan setup](model_approval_and_scan_setup.md)
and the workflow milestone plan. **M35–M36 are complete**:
private immutable model revisions selectable in both tracks, reviewed TeX/image/idea
intake and editable refinement under one durable session budget. Closure:
123 focused/1390 fast/25 slow tests, both pinned tracks and new/legacy replays;
graded live checks cost $0.2493034 Anthropic / $0 OpenAI.
See [personal model intake](personal_model_library_and_intake.md).
M37 is complete for confirmed interpretation and supported exploratory event
handoff; M38 physical filtering and M39/M40 reanalysis/journey acceptance are also complete.
The owner-requested **M36.5** experimental-paper/private-update extension
has **a–b complete**, with private dated experimental drafts, bounded page/table
ingestion and distinct calculation/report dates. Closure: 118 focused/1408
fast/25 slow tests, source imports, dated tracks/resume and archive replays; $0 API.
See [usage](experimental_source_ingestion.md) and the experimental-paper milestone plan.
**M36.5c and M37 are complete**: budgeted source interpretation/refinement,
confirmed anomaly intake, supported exploratory Track 2 handoff and portable replay.
129 focused/1420 fast/25 slow tests; composite and independent image-only
live facts passed; $0.3474534 Anthropic/$0 OpenAI. See [usage](experimental_interpretation_and_anomaly_intake.md).
**M36.5d–e are complete** for scoped expert source assertions, independent
published-value validation, calibrated source overlays and exact per-run private
SI/Higgs limit selection. 120 focused/1433 fast/25 slow tests; source-bound
CLI/UI, actual baseline/private Track 1, resume and archive replay passed; $0 API.
See [private-limit usage](private_limit_review_and_track1.md). Real source approvals remain researcher tasks; completed private adapters/profiles retain narrow numerical scope.
**M37.5a–d are complete**: paper/equation model intake in both tracks and required/preferred
model-property selection;91 original focused checks, actual both-track replay, one Anthropic call
$0.088591. [Usage](model_style_and_paper_intake.md).
**M36.5f–h are complete** for the initial source-matched private event adapter,
immutable selection profiles, activation/rollback and both-track/child/evidence integration.
122 focused/1453 fast/25 slow tests; independent references, corrected profile,
resume, rollback, promotion and catalog-independent replay passed; $0 API.
[Usage](private_experimental_profiles.md); receipt summary.
M38 physical fitted-point eligibility and M39/M40 reanalysis/journey acceptance are complete. The remaining M32 independent release audit followed on 10 October (see the note at the top); broader adapters stay explicit options.

## Original audit remediation

**M01–M18, covering all 19 findings F01–F19, are complete.** Original acceptance,
optional backend calculations, both tracks and the 25-portal run are recorded in
the remediation plan and local audit ledger. Extension
regression runs check these fixes alongside the new capabilities. Deferred
physics scope and human record review remain explicit.

## Extensions: implemented increments and broader proposals

| Rank | Original proposal | Current status | Remaining scope |
|---:|---|---|---|
| 1 | Throughput, durable runs, adaptive coverage | **Agreed increment implemented:** measured Track 1/2 reuse, checkpoints, bounded adaptive checks and independent dense/broader benchmarks. | More detector costs/regions can be profiled; finite scans do not certify every branch. |
| 2 | Mixed/cascade spectra | **Photon increment implemented:** mixtures, finite-mass scalar cascades and public dwarf SED likelihood. | Charged-particle recasts, polarization/off-shell/low-mass hadronisation remain pending. Since 11 October, antiproton channel mixtures are bounded by conservative rules (`constraints/mixtures.py`), not recast. |
| 3 | Bounded physical fitting | **One-parameter and M28 increments implemented:** named bounded Point domains, shared native-pair fits, explicit relations/branches, modes, profile diagnostics and source-bound resume. | Native mass banks remain discrete; arbitrary model symbols and all alternative thermal branches are not covered. |
| 4 | Native experimental likelihoods | **First pairs implemented:** CDMS Si + DEAP and low-mass CDMS Si + PICO, coherent physical fits and conditional calibration. | Fidelity-B reconstructions; full workspaces/nuisance models and other searches remain proposals. |
| 5 | Common evidence export/expert review queue | **Agreed workflow implemented (M19–M21):** versioned evidence/export/replay; selected-run task priorities and shared CLI/UI/export reasons; scoped human signature invalidation, source/data/assumption diffs and researcher timers (on the command line; the record page's timer was removed on 12 October). | Actual human source verification (R9, under way) and measured expert-time savings (R12) remain pending; source review alone does not supply a new recast/likelihood or extend applicability. |
| 6 | Broader model contracts/completion | **Selected contracts implemented (M22–M23):** named vector currents and complete Z2 scalar potential, both tracks and evidence maps validated. | General flavour recasts, correlated parameter domains and further completions remain pending. |
| 7 | Identifiability/coverage/discrimination | **Partial:** bounded modes/regions, native discovery calibration and nested finite-grid nuisance checks. | Confidence-region coverage, general identifiability and new discrimination studies are not complete. |
| 8 | Narrow theory-consistency certificates | **M24–M26 implemented:** full-domain tree-level vacuum assessment, complete normalized 15-channel high-energy scalar partial waves and declared-scale one-loop running for the Z2 potential. A metastable vacuum's zero-temperature tunnelling lifetime was added on 11 October (`theory/vacuum_decay.py`). Since R5 a failed complete certificate excludes the point as an invalid model point, and an unresolved one leaves it pending. | Finite-energy/full-theory unitarity and finite-temperature certificates remain separate proposals. |
| 9 | Measured evidence-grounded agents | **Agreed increment implemented:** optional clarification, source gathering, bounded plans, checked review, baseline comparison, paid journals and researcher timers. | Human sessions are planned in R12 (or after release, if the owner prefers); broader tasks/participants are needed to establish added value. |

All **authorized implementation increments** are delivered; this does not mean
all nine broad proposals or every backend are fully covered. Remaining proposals
are not silently included in this work. See [native methodology](native_joint_likelihood.md),
[measured assistance](measured_agent_assistance.md),
[spectra](mixed_cascade_spectra.md), [bounded fits](bounded_physical_fitting.md)
and [performance/coverage](performance_and_scan_coverage.md).

The next broader programme is planned as **M19–M32** in the
broader extension plan: common evidence export,
additional explicit model contracts, scoped theory certificates and general
physical inference/coverage. **M19–M28 are complete at their declared scopes;
M32, the first-release audit, was carried out on 10 October, and its findings
are closed by R0–R12. M29–M31 are deferred post-release
proposals, retaining their numbers and acceptance requirements.** M28 keeps
bounded multiparameter fitting, mode/boundary resolution and degeneracy checks;
M32 audited this adopted release scope. Experimental likelihood/nuisance inputs
are unevenly available, as documented in the revised plan. Deferral does not
upgrade the existing conditional significance or certify confidence-region coverage.
See [evidence export](evidence_export.md) for the implemented scope and replay limits.
The [record-review workflow](record_review_workflow.md) documents M21's signature,
priority and human-timing boundaries.

## Fit-for-purpose assessment

The supported deterministic system is useful for **supervised theoretical
phenomenology**: it preserves inputs, composes components and exposes eligibility,
pending calculations and numerical certificates. It is not a universal arbitrary-
model or publication certificate. Agent roles now perform concrete workflow
tasks with a clear numerical boundary. In the first development comparison,
both providers caught the same five issues as the free baseline; no added
error-detection gain or researcher-time gain is yet established.

Before a clean public release, prioritize expert verification of relevant pending
records (now R9), a representative researcher timing/usability study (R12), and portable
installation/reproduction checks (R11). Stronger discovery claims need appropriate
native nuisance information and more than a finite grid of conditional coverage
tests. Select additional native searches or model contracts by the research
programme; keep assistance optional where interpretation/source routing helps.

The [explicit model contracts](explicit_model_contracts.md) document M22/M23
normalisations, input bases, fixed scan/fit coordinates and source-spectrum guards.
Closure: 1241 fast/25 slow tests pass; both contracts have
thermal scans and independently checked bounded fits; four new exports replay.

The [scalar vacuum certificate](scalar_vacuum_certificate.md) documents M24 scope,
flat directions, numerical ambiguity and the separate theory/experimental views.
M24 closure: 1271 fast/25 slow tests pass; both tracks and
evidence replays pass. M25 partial-wave unitarity is next.

[Scalar partial-wave unitarity](scalar_unitarity_certificate.md) documents M25
basis, normalization and approximation limits. Closure: 1292 fast/25
slow tests pass; 200 independent matrices and both tracks/replays pass. M26 RG is next.

[Declared-scale scalar running](scalar_running_certificate.md) completes M26.
Closure: 1312 fast/25 slow tests pass; independent source-convention RK4,
both scalar tracks and replays pass. [M27 prerequisite diagnostics](chemical_equilibrium_certificate.md)
are partial: regulated Born conversions and coupled reference checks are implemented,
but missing inclusive/thermal/odd-sector rates prevent a physical passing certificate.
Finish that acceptance gap before calling M27 complete. (Closed at the
owner-authorized scope by the source-accuracy closure below; R5 revised the
window and added a thermal-mass regulator.)

M27 continuation (9 October): explicit odd-sector conversion and nonlinear
coupled reference checks are implemented. 1316 fast/25 slow tests pass; older
M27, scalar-RG and native archives replay. Inclusive/plasma rates still keep
M27 partial, so M28 remains gated under the owner's current condition.

M27 source-accuracy closure (9 October, owner-authorized scope): 1325 fast/25
slow tests pass; matched micrOMEGAs conversion kernels and decay normalization,
fresh coupled/cut-varied references, actual scan and old/new replays pass.
Component support is separate from uncomputed inclusive/plasma accuracy.
M28 bounded multiparameter fitting is next.

M27 at leading order in the plasma (19 October, the owner's request): thermal masses on every light or charged leg
and quantum statistics decide `physical_prerequisite` when a request asks for them, validated against the vacuum,
collinear-logarithm, Maxwell–Boltzmann and detailed-balance limits
([chemical_equilibrium_certificate.md](chemical_equilibrium_certificate.md)). Not a matched or HTL-resummed
calculation; the broken-phase electroweak/Higgs channels remain outside.

[M28 bounded multiparameter fitting](multiparameter_physical_fitting.md) closure
(9 October): 1344 fast/25 slow tests pass; independent dense/separate-optimizer
maxima and profiles, fresh identifiable mediator/coupling examples, signed modes,
degeneracies, both boundary directions and unresolved threshold/budget cases pass.
Both native pairs, full single-idea/Track 1 runs, byte-identical CLI resume and
new/legacy evidence replays pass. Cached payloads must match their physical Point
and search; optional review distinguishes completed fitting from calibration.
Observed examples retain zero-signal mass/mediator ambiguity. M32's first-release
closure audit is next; M29–M31 remain deferred.

10 October 2026 M37.5 scope correction complete: arbitrary user-defined model properties/declarations replace the initial two-example restriction; 64 focused/1455 fast tests passed, $0 API. Receipt summary: M37.5 correction; [usage](model_style_and_paper_intake.md). No default/scoring preference was introduced.

M38 complete (10 October 2026): 129 focused/1463 fast/25 slow tests; exact physical-point eligibility, retained NR reference, pending branches, exact Track1 reuse/stale refusal and catalog-independent replay. $0 API. [Usage](physical_candidate_eligibility.md); report summary: M38. Historical next steps at the M38 receipt were M39/M40 (now complete). Remaining M32 is next; M29–M31 remain deferred.

M39/M40 complete (10 October 2026): 131 focused/headless/1468 fast/25 slow checks passed; both directions, revised model/anomaly children, parent-byte/date preservation, export/replay and public CLI/UI review/refusal controls passed. Two paid calls cost $0.210006 Anthropic/$0 OpenAI; all 33 setup-manifest items are present locally. [Usage](reanalysis_and_release_journeys.md); report summary: M39 and M40; audit handoff: summary. M32 independent closure, real source approval and human timing remain pending; M29–M31 remain deferred. (M32's audit followed the same day; source approval is now R9 and human timing R12.)
