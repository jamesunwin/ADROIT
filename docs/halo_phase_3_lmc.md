# Halo implementation, phase 3: one sourced LMC-affected benchmark

This file is an implementation prompt. Read it in full and follow it. The aim is one reproducible scientific benchmark, not a universal model of the Milky Way–LMC system.

## Prerequisites and working rules

Read [phase 1](halo_phase_1_shared_configuration.md), [phase 2](halo_phase_2_shmplusplus.md), both completion records, and `docs/halo_constraint_support.md`. Their working rules, compatibility requirements, scientific safeguards and testing standards apply here.

Verify the shared configuration and SHM/SHM++ regression tests are present at the selected base. Reuse that architecture. Do not create a separate LMC implementation path in each track.

SHM stays the default. No owner's records or signatures are changed; no provider calls, paid requests or implicit runtime downloads. External scientific-source acquisition must be explicit and separate from calculations. Tests are offline except localhost. Preserve historical evidence and use isolated writable resources.

## First milestone: define what “SHM + LMC” means

This label is not a unique distribution. Do not begin a production LMC adapter with an arbitrary high-speed tail or mixture fraction.

Start with Smith-Orlik et al., *The impact of the Large Magellanic Cloud on dark matter direct detection signals*, [arXiv:2302.04281](https://arxiv.org/abs/2302.04281), and its available author data/code. Inspect the full source and relevant later author material if needed. A related nonstandard-interaction study is [arXiv:2409.09119](https://arxiv.org/abs/2409.09119). These are starting sources, not instructions to combine incompatible datasets.

The LMC can contribute debris and change the native Milky Way distribution. Do not double-count either effect or silently equate a perturbed simulation distribution with an analytic SHM plus an added stream.

Prepare `docs/halo_lmc_benchmark.md` with:

- exact publication/data/code versions, file hashes and usable redistribution terms;
- simulation/realisation, snapshot, local sample selection, Solar position and orientation;
- native Milky Way and LMC components, if separately available;
- whether the benchmark replaces the full local distribution or is a defined mixture;
- weights, density, units, normalisation, velocity origin/axes and reference frame;
- maximum supported velocities and treatment beyond the published table;
- available angular information and valid frame/time transformations;
- interpolation, smoothing/binning, sample noise, numerical resolution and uncertainty limitations;
- checks against published distributions, integrals or predictions;
- per-consumer applicability and what remains unavailable.

Prefer one documented published benchmark over a new phenomenological fit. If an essential benchmark choice is genuinely ambiguous, present a concrete recommendation and the evidence to the owner before committing that scientific choice; continue independent infrastructure/testing work meanwhile.

If data or terms are unavailable, stop the dependent implementation, leave the selector unavailable with the specific reason, and report the missing prerequisite. Do not manufacture data, digitise an unsuitable illustration as an exact distribution, or count disabled support as completion.

The short UI label may be “SHM + LMC”, but its subtitle/details must name the actual benchmark. If it is a full LMC-perturbed simulation distribution, say that clearly; recommend a more precise display label to the owner rather than misdescribe it.

## Implementation and capability boundaries

Register the benchmark with a stable ID/version in the shared halo system. Implement it as a fixed benchmark initially. Do not assign a confidence interval from a few simulations or reuse the SHM uncertainty region.

Where permitted, provide small versioned derived tables with provenance. Where source terms do not permit shipping, use the established external-input manifest with explicit setup and hash checks. Missing inputs yield a useful setup instruction before computation. Resolve consumed bytes/parameters and their identity once.

Keep the speed tail present in the chosen benchmark: do not clip it at the SHM escape-speed convention. Do not extrapolate beyond its evidenced support without a separately documented physical model.

Support all velocity moments required by the declared interactions. Pay particular attention to high recoils, low-mass thresholds, and endothermic scattering; those are important motivations for this feature. Preserve exothermic and zero-splitting behaviour too.

A one-dimensional distribution already in the detector frame cannot uniquely determine the angular distribution, solar-frame distribution or annual modulation. It must advertise those capabilities as unavailable unless separately supplied or derived from sufficient underlying data. Changing `v_earth` on such a table is not a solar-frame transformation.

For a tabulated implementation, quantify interpolation and binning errors with independent checks. Do not smooth away the tail or present Monte Carlo noise as precision. Preserve component and total-density accounting, including the particle model's abundance fraction.

## Constraints beyond direct detection

Update every row of `docs/halo_constraint_support.md` for the chosen LMC benchmark, with executable checks for supported and unsupported cases.

- **Direct detection:** use the actual distribution through detector response and supported likelihood/limit construction. No inherited SHM or SHM++ count-ratio validation. Verify each analysis/interaction/domain separately; private curves do not automatically become recastable.
- **Solar capture/IceCube:** compute it only if a justified solar-frame distribution is available. Otherwise retain a named pending comparison, not a detector-frame or SHM surrogate. If supported, validate capture and capture-annihilation evolution independently.
- **Galactic gamma-ray lines and antiprotons:** a local LMC-affected distribution is not a spatial model of the Galactic source region. Preserve an explicitly declared fixed-profile normalisation treatment where justified, and label it as conditional. Do not invent new J-factors, a Galactic wake signal or propagation changes. Unsupported velocity-dependent annihilation interpretations remain pending.
- **Dwarfs:** retain dwarf-specific profiles, J-factors and assumptions. Do not assign the Milky Way's local tail to them.
- **Relic abundance, CMB/BBN/N_eff, colliders, flavour and precision:** unchanged by this local-halo selection.
- **Independent exclusion and incomplete coverage:** preserve the existing certification reduction. Missing halo-dependent support cannot establish complete allowed coverage; it does not negate an independent valid exclusion.

Do not broaden scope into a general LMC spatial simulation or new indirect-search recast merely to avoid a truthful pending result. Conversely, do not advertise support for those searches when only local recoil rates changed.

## Both tracks and scientific identity

Enable the benchmark in the shared model-selection UI only when it is usable. State the benchmark ID/source and “fixed benchmark; halo uncertainty not propagated”, plus affected constraints and unavailable capabilities before launch.

Use it consistently in the signal and supported null comparisons. Audit native backends that accept only SHM parameters: forwarding surrogate `v0`/`vesc` values is not implementation of the benchmark.

The source/table checksum, normalisation, frame/time convention and numerical representation must enter affected identities. Preserve them through promotion, batch, resume, rerun, reanalysis, page links, history, reports, CSV and bundles. Use the existing scientific-version handle. Later source changes establish staleness, not a new interpretation of a saved result.

Review statistical calibration for changed templates/search definitions. Do not reuse incompatible toys or use accepted-count scaling for a fit/significance. Keep existing zero-background refusals and eligibility qualifications.

## Required tests

### Unit and independent numerical validation

- Validate input schema, finite/nonnegative distributions, increasing grids, weights, units, normalisation and checksums; malformed, missing and changed inputs fail usefully.
- Compare speed distributions and required integrals to the source/reference benchmark with predeclared tolerances.
- Independently integrate representative velocity moments and test grid/bin refinement, especially the tail and support boundary.
- Test density/component accounting and candidate abundance fractions exactly once.
- If a true mixture is defined, test its zero-LMC limit against its documented native component. If no such decomposition exists, mark this test not applicable; do not invent one.
- Test available frame transformations and reject unavailable ones. No implicit modulation or directional capability.
- Check elastic, endothermic and exothermic kinematic thresholds, including a case accessible under the sourced tail but inaccessible under the matched SHM baseline when the source supports that expectation.
- Exercise multiple supported velocity dependences, not SI alone.
- Validate solar capture independently if supported; otherwise test the precise pending reason through the result and export.

### Integration and preservation of existing physics

- Real supported detector spectrum, response, limit and signal-fit checks; separate density changes from shape changes in diagnostic comparisons.
- Equivalent explicit benchmark through both tracks: shared predictions agree where the procedures are the same; legitimate statistical differences are documented.
- At least one real useful direct-detection calculation in each track and a second detector-response integration. An entirely mocked or all-pending LMC implementation is not complete.
- Verify Galactic conditional assumptions, unsupported recasts and unchanged dwarf/cosmological/laboratory results.
- Test near a decision boundary; numerical uncertainty cannot be ignored if it changes the verdict. Apply the established conservative qualification or record a new explicit policy proposal.
- Cache/checkpoint separation when source bytes, sample, weights or frame change; filename and family string alone are insufficient.
- Inheritance through promotion/batch and rejection of incompatible resume.
- Replay older requests, results and exports without rewriting their bytes or assigning them the new default.
- Rerun SHM and SHM++ baselines. Explain every changed value/status; unintended differences block completion.

### Real-browser journeys and mutations

Through both ordinary track entry points: choose model → select LMC benchmark → inspect assumptions/applicability → launch small real calculation → open result → compare page/request/CLI/result/export → restart/reopen → follow promotion or reanalysis. Label every expensive calculation replaced by a fixture; such a fixture does not validate its physics.

Exercise absent data, wrong checksum, unsupported native backend, missing solar-frame support and stale results. The next step must be intelligible, with no silent SHM fallback or misleading successful tournament.

Mutation controls must catch an ignored selector, accidental SHM tail cutoff, component/density double counting, a detector table passed to solar capture, an omitted data hash in a cache, a child reverting to SHM, and an export dropping capability qualifications. Each control needs a passing unmutated baseline and failure at its named invariant.

## Final validation and delivery

Run targeted tests while building and the applicable established release checks at completion. Keep expensive independent validations outside the fast suite; record their tested domain, input identities and runtime. Do not weaken gates or refresh reference numbers without explaining the physics.

Write `docs/halo_phase_3_completion.md` with base/end commits, benchmark definition, data availability/terms, validation, support matrix, browser evidence, baseline comparisons, test commands, timings/storage, substitutions and outstanding limitations. Update halo/workbench/CLI documentation and prepare the independent audit prompt for all three phases.

Completion requires a well-defined useful LMC benchmark in both tracks, correct affected comparisons and named unsupported ones, stable provenance through the complete workflow, preserved SHM/SHM++ behaviour, and the acceptance evidence above. The three dropdown labels alone are not a completion criterion. Do not tag or publish a release; return the evidence and recommendation to the owner.
