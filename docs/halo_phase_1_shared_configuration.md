# Halo implementation, phase 1: shared configuration and unchanged SHM

This file is an implementation prompt. Read it in full and follow it. Implement only this phase, test it, and deliver its completion record. Do not begin phase 2 automatically.

## Objective and build order

ADROIT will offer three halo families when a researcher defines or chooses a particle model in either Track 1 or Track 2:

1. SHM — the default.
2. SHM++ — phase 2.
3. An explicitly sourced LMC-affected benchmark — phase 3, with the short display name “SHM + LMC” qualified by its actual definition.

The phases are:

- **This file:** one shared halo configuration, consumer inventory, compatibility, identity and UI plumbing; existing SHM physics preserved.
- [Phase 2](halo_phase_2_shmplusplus.md): implement and validate SHM++, then enable it in both tracks.
- [Phase 3](halo_phase_3_lmc.md): select, implement and validate one reproducible LMC benchmark, then enable it.

The critical invariant is: **a chosen halo reaches every calculation that supports it, and unsupported comparisons are named; the application never silently substitutes another halo.** Existing defaults, scientific safeguards and historical results must remain reproducible.

Phase 1 is independently useful and must not require completing the other phases to remain releasable. A disabled future option is not an implemented capability.

## Working rules

- Record the starting commit and read applicable repository instructions. Develop in an isolated worktree/branch, not in the owner's active checkout. Do not disturb concurrent repair work or the running workbench.
- Preserve unrelated edits, owner records, signatures, runs, projects and external tools. Never sign or reverify records, publish, tag, or change release status as part of this task.
- Use native arm64 Python 3.12 on this machine and the repository's locked dependencies. Point writable data, libraries, runs, projects, caches and temporary files into your scratch root; confirm their resolved locations before running workflows.
- No live provider calls, no API-key access, and no paid requests. Provider fixtures, if needed, must be labelled simulated. Tests stay offline except for localhost browser journeys. Do not run the model zoo's held-out half.
- Run one calculation at a time, `nice -n 10`, `OMP_NUM_THREADS=2`. Use targeted tests during development. List expensive checks and their expected cost before running them; do not launch broad scans or regenerate native tables casually. Run the established release gate before calling a release ready; an unrun requirement is not a pass.
- Changes to physics infrastructure may invalidate fingerprints. Respect that invalidation; do not bypass hashes, relax thresholds or edit golden outputs just to get a passing gate.
- Use the existing evidence/version infrastructure. Do not introduce another set of ad hoc file readers or duplicate certification/accounting logic.

## Read first and establish expectations

Read the current versions of:

- `docs/halo_region.md`;
- `adroit/core/dm_state.py`, `adroit/physics/halo.py`, `adroit/physics/rates.py`;
- `adroit/parameter_space/halo_region.py`, `halo_evaluation.py`, `halo_limits.py`, `searches.py`;
- `adroit/constraints/capture.py`, `adroit/constraints/data/records.yaml`, `adroit/constraints/data/local_densities.yaml`;
- Track 1, signal, single-idea, native-fit, promotion, physical-eligibility and checkpoint implementations;
- experimental modules, the registry, private/anomaly searches, accepted-count calculations, native adapters and cache identities;
- workbench forms, saved-request schemas, certificates, and the version handle plan with the current version-handle implementation.

Paths are starting points, not an exhaustive consumer list. Inspect the current code before designing the patch.

Write expectations and preserve baseline inputs/outputs before changes. Include default and published-halo Track 1, default signal fits, a single-idea study, direct-detection spectra/limits, capture, Galactic indirect limits, and unaffected constraints. Save request identities, status/pending reasons, relevant statistics and provenance. Reuse existing deterministic fixtures and validation results where appropriate, identifying their limits.

For numerical comparisons, declare tolerances in advance. Aim for identical scientific values on unchanged SHM paths; explain any floating-point differences individually. Preserve old saved files and bundle fixtures unchanged.

## Mandatory constraint-impact inventory

Create `docs/halo_constraint_support.md`. Enumerate every current curated record and registered experimental module, including private/historical/anomaly routes and library-specific limits. Give each a row or an explicit mapping to a fully specified family row. Do not assume `records.yaml` contains all direct-detection experiments.

Columns: consumer/record ID; code location; inputs actually needed; existing assumptions; reference frame/time convention; treatment under each new family; exact/validated approximation/unsupported; propagation and cache boundary; test/evidence; limitations.

Use these starting entries, checking their IDs against the implementation base:

| Family or record | Treatment to establish |
|---|---|
| LZ, XENONnT, PandaX-4T, CRESST, DEAP, PICO, CDMSlite, historical searches, confirmed anomalies and private searches | Density and velocity-dependent recoil spectrum, detector response and statistical procedure. Audit SI, SD, general operators and inelastic cases separately. |
| `icecube-1612.05949-sd`, `icecube-1612.05949-si` | Solar-frame distribution, capture and capture-annihilation evolution. The annihilation bound and its channel assumptions are distinct from a converted scattering limit. |
| `fermi-lat-1506.00013-lines`, `hess-1805.05741-lines`, `hess-2608.07234-lines`, `dampe-2112.08860-lines` | Local normalisation, spatial profile/J-factor, region of interest and any annihilation-velocity assumptions. |
| `calore-2202.03076-pbar` | Source profile, normalisation, propagation and annihilation-velocity dependence; retain conservative/central/aggressive semantics. |
| `fermi-1503.02641-dsph`, `fermi-2311.04982-spectral` | Dwarf-specific J-factors and velocity assumptions, not the Milky Way's local distribution. |
| `planck-2018-omega`, `planck-2018-pann`, BBN and N_eff records | Cosmological calculations; not changed by a present-day local halo selector. |
| Collider, accelerator, flavour, precision, laboratory and theory constraints | Local-halo independent; numerical results and review gates unchanged. |
| Operator-limit routes, flavour-vector limits, private curves and multi-component models | Explicit applicability audit; do not infer support from the generic rate engine. |

Scientific requirements for this inventory and later phases:

- A local velocity distribution does not define a Galactic spatial density profile or new J-factors. Keep those assumptions separate and visible.
- Existing Galactic density-squared rescaling is conditional on fixed profile shape and the applicable annihilation assumptions. Do not label it a complete alternative-halo spatial recast.
- Velocity-dependent annihilation may require a pairwise relative-velocity distribution over the source region. A local detector speed table does not supply it. Unsupported claims remain pending.
- Solar capture needs a solar-frame distribution. Changing a metadata velocity on an already detector-frame speed table is not a valid frame transformation.
- Do not double-count component weights, total density, or the particle candidate's dark-matter fraction.
- Preserve dwarf-specific assumptions and all cosmological/laboratory constraints.
- The current SHM accepted-count-ratio validation, including its 15% gate, domains, margins and budgets, does not validate other distribution shapes. Preserve it for its existing domain only.
- Unknown halo-dependent comparisons cannot certify complete allowed coverage. Independent valid exclusions may still decide according to the established certification rule. Do not make every result pending simply because one unrelated comparison is unsupported.
- Preserve signed record contents and verification gates. Store derived halo/recast assumptions in their own versioned provenance, without relabelling the underlying experimental record as newly verified.

## Shared configuration: preserve default behaviour explicitly

Separate **halo family** from **evaluation treatment**. Treatment must distinguish a fixed common benchmark, an uncertainty-region evaluation, and reproduction of published assumptions.

Preserve existing meanings of `--halo preset`, `--halo published`, environment settings and historical requests. Add unambiguous options for the new concepts after inspecting the CLI; do not repurpose existing flags incompatibly.

In particular:

- Track 1 currently defaults to its declared SHM uncertainty region. Keep its parameters, sampling, certification and budgets unchanged.
- Path 2 currently uses its established fitting conventions and separately labelled sensitivity checks. Keep its default numerical behaviour unchanged.
- Those defaults need not be one common numerical SHM. Label them honestly. Do not claim common assumptions merely because both are called SHM.
- A user may explicitly request a **fixed common SHM benchmark**, with a documented numerical specification. All capable comparisons then use that benchmark; incapable ones are named. This is a new explicit request, not a silent change to the default.
- Selecting a family does not invent uncertainty priors. Alternative families will initially be fixed benchmarks. Three benchmark results are not a confidence interval.

Use one typed request/resolution contract shared by both tracks. Extend existing types where suitable rather than duplicating machinery. It should carry:

- schema version, family and benchmark ID/version;
- numerical values, density and component weights;
- frame, axes, units, laboratory/solar motion and time convention;
- distribution source/data identities;
- treatment and uncertainty specification, when present;
- spatial assumptions or an explicit reference to the retained experimental profile;
- capabilities and limitations.

Keep the resolved object immutable in practice. A run consumes values and hashes from the same resolution, not a later lookup of mutable defaults or data files. Consumers must request the capability they need. Missing capabilities produce typed, intelligible pending/refusal reasons.

Use a small registry for future families, with stable machine IDs distinct from UI labels. Do not build unused framework layers.

## Identity, caching and continuations

Inventory every affected cache and checkpoint. Include the relevant resolved numerical/data/frame/time identity, not just a family string. Changing a display label alone should not invalidate physical calculations. Changing distribution bytes under the same filename must invalidate affected results.

Halo-independent calculations can remain reusable through explicit dependencies. Do not globally invalidate unrelated calculations without reason.

Propagate the request through Track 1, single-idea/Explain a signal, Track 2, native fits where applicable, promotion, batch, resume, rerun and reanalysis. A changed halo starts a new scientific request; incompatible checkpoints must not resume silently. Promotion must use its parent's resolved identity unless the user explicitly starts a distinct, labelled analysis.

Legacy results keep their original bytes, hashes and readings. Missing historical configuration is qualified as legacy/not recorded or interpreted through a documented historical schema where unambiguous; never apply today's defaults retroactively.

Bind the resolved halo and input versions to certificates/evidence using the existing shared mechanism. A changed input may make an old claim stale; viewing must not rewrite that claim.

## Workbench and CLI

Create one reusable halo component used during model definition/selection, including library and personal-model paths. SHM is selected by default. The two future choices may be shown disabled with their implementation status, or withheld until enabled; neither may launch SHM under an alternative label.

Show family, treatment and a concise resolved-assumptions summary. Expandable details should give parameters, source and applicability. Published reproduction must say that experiments may use different numerical assumptions.

The form, launched command, saved request and calculation must agree. A model-intake LLM prompt must not independently set hidden halo parameters. If it proposes them, the resolved review form must expose them.

Use stored halo information consistently on progress, study and point pages, fit tables, reports, CLI output, CSV and bundles. Preserve pending reasons and per-constraint qualifications. Viewing and exporting must not dispatch new calculations.

## Required tests

### Unit and compatibility

- Request parsing, resolution and validation; default, explicit fixed SHM, region and published modes.
- Round trips and legacy requests without new fields; no rewrite of historical fixtures.
- Invalid combinations, missing capabilities and unknown family IDs produce useful errors.
- Stable canonical identities; parameter/data/frame changes invalidate relevant caches; display-only changes do not.
- A/B concurrent requests do not leak halo configuration through global state or reused modules.
- Existing SHM formulas, density scaling and region sampling match the baseline.

### Integration

- Explicit common SHM reaches signal and null comparisons consistently.
- Default Track 1, Path 2 and single-idea results remain unchanged.
- A request crosses forms, CLI, child process and saved result without losing its configuration.
- Promotion, batch, resume and reanalysis preserve it or reject incompatibility.
- Unsupported comparison remains pending; a separate sound exclusion still stands.
- Unaffected cosmological, collider and dwarf calculations remain unchanged.
- Saved request/result/report/export have the same resolved identity.
- Source files changed between resolution and use cannot relabel the calculation; changed files later cause the appropriate staleness.

### Real-browser acceptance

Use your own server/profile and scratch outputs. Exercise default SHM and explicit fixed SHM through each track: model choice → halo summary → launch → actual result → reload/history → continuation → export/reopen. Use small real supported calculations to prove the selected configuration reaches physics; label any substitutions in expensive paths.

Include server restart, absent dependency, incompatible checkpoint and unavailable comparison. No traceback, misleading success, endless spinner or silent fallback is acceptable.

Keep mutation controls that fail if the form ignores the choice, a child drops it, a cache omits its identity, an export loses its qualification, or a future family is mapped silently to SHM. Establish each control's passing baseline first.

## Deliverables and completion gate

Write `docs/halo_phase_1_completion.md` containing base/end commits, design, compatibility mapping, tests and commands, numerical baseline comparison, substitutions, costs and remaining limitations. Link the completed constraint matrix and regression evidence. Update relevant user documentation only for implemented behaviour.

Phase 1 is done when the common configuration works end to end in both tracks, all existing SHM default physics and safeguards retain their established behaviour, explicit common SHM is coherent within its declared support, and legacy saved evidence still reads correctly. Unrun essential checks mean the phase is not established.

Provide the owner a concise completion report and a ready-to-run audit prompt. Do not start phase 2 until instructed.
