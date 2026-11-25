# Halo implementation, phase 2: SHM++

This file is an implementation prompt. Read it in full and follow it. Implement only this phase; do not start the LMC phase automatically.

## Prerequisite and objective

Read [phase 1](halo_phase_1_shared_configuration.md), its working rules, `docs/halo_phase_1_completion.md`, and `docs/halo_constraint_support.md`. The working rules and scientific safeguards in phase 1 apply here. Verify the shared configuration and baseline tests are actually present in the chosen implementation base. If they are not, report that prerequisite; do not build a parallel configuration system.

Enable a scientifically defined, validated **SHM++** choice in both tracks. SHM remains the default and its existing results must stay unchanged. SHM++ is initially a fixed benchmark, not a new uncertainty envelope or a claim to describe every Galactic uncertainty.

## Scientific specification before code

Use Evans, O'Hare and McCabe, *SHM++: A Refinement of the Standard Halo Model for Dark Matter Searches in Light of the Gaia Sausage*, [arXiv:1810.11468](https://arxiv.org/abs/1810.11468). Read the full paper and inspect any associated author implementation; do not implement from its abstract or this prompt alone.

Write `docs/halo_shmplusplus.md` with equation/page citations and the exact benchmark:

- isotropic and anisotropic component distributions;
- Sausage fraction and anisotropy definition;
- circular-speed, escape-speed and density conventions;
- velocity-dispersion relations and coordinate axes;
- truncation and normalisation of each component;
- solar motion and laboratory transformation;
- fixed-date or exposure/annual-averaging convention;
- chosen values, source versions and any departure from the published prescription.

Choose the paper's stated benchmark where it provides one. If an essential choice has no unique published prescription, prepare a concrete proposal and ask the owner only for that scientific decision; continue independent work. Do not silently invent a value.

SHM++ is not SHM with updated numbers. Implement the anisotropic mixture. At zero Sausage fraction, it must reduce to the isotropic component at the same remaining parameters; it need not equal ADROIT's historical default if those parameters differ.

## Distribution and rate implementation

Use the shared registry and resolved configuration from phase 1. Retain the existing production SHM implementation for its established paths.

Transform the anisotropic Galactic distribution correctly before angle-integrating it into a speed distribution. The laboratory direction matters; its speed alone is insufficient. Support both the detector and Sun frames through a physically justified implementation.

Expose all moments the supported interactions need, including the inverse-speed and transverse-velocity moments used by ADROIT. Audit support for general operators and elastic, endothermic and exothermic scattering. Do not extrapolate validated SI support to other interactions automatically.

If tables are generated for speed, define their grid, interpolation, support and convergence criteria. Include those numerical settings in the relevant identity. Resolve source parameters and tables once; calculations use that snapshot. A table is an implementation of a declared distribution, not an anonymous replacement for it.

For time dependence, implement the supported convention explicitly. Do not claim annual-modulation or directional support merely because an annual-average nondirectional rate works. Unsupported requests must say why.

## Constraint integration

Update every row of the phase-1 support matrix for SHM++. At minimum:

- Recompute supported direct-detection spectra through their detector responses and statistical procedures.
- Require new validation for any shape-changing shortcut. The existing SHM count-ratio gate is not permission to apply it here.
- Use the correct solar-frame distribution in capture, retaining the capture-annihilation evolution and channel assumptions. Check the low-speed tail as well as the recoil-relevant high-speed tail.
- Retain explicitly declared spatial profiles for Galactic lines/antiprotons where using the existing fixed-profile density-normalisation prescription. State this conditional scope; local anisotropy is not a new Galactic J-factor model.
- Keep unsupported velocity-dependent Galactic annihilation reinterpretations pending, with their missing input named.
- Keep dwarf, cosmological, collider and other local-halo-independent inputs/results unchanged.
- Preserve review gates, confidence levels, likelihood procedures, theory refusals and certificate reductions.

Do not mark the entire phase complete with all alternative-halo comparisons pending. It must perform useful real calculations in both tracks on an explicitly listed supported set. As a minimum, demonstrate a detector comparison and signal fit with the same SHM++ configuration, a second detector-response integration, and a solar-capture validation. Any backend that cannot support the distribution must remain accurately qualified rather than being relabelled as supported.

## Workbench, requests and follow-up

Enable SHM++ in the shared model-choice component for both tracks. Show the resolved benchmark and “fixed benchmark; halo uncertainty not propagated.” Do not apply the SHM region automatically or call the difference from SHM a confidence interval.

Ensure the signal and its applicable null constraints use the same resolved choice. Existing sensitivity checks must be explicitly distinguished from the primary benchmark; do not let them override it or produce unlabelled cross-family checks.

Audit significance and toy calibration when signal templates/search definitions change. Never reuse incompatible statistical calibration or introduce an artificial background to make an unsupported fit run.

Carry identity and capability qualifications through native paths, promotion, batch, checkpoints, reruns, reanalysis, history and exports. Keep SHM as the default. Use the existing shared scientific-version mechanism, not new direct reads of saved output.

## Tests and validation

Write expected outcomes and tolerances before observing results. Independent reference calculations are required; two functions using the same implementation are not independent validation.

### Unit physics tests

- Finite, nonnegative and normalised component/mixture distributions.
- Physical parameter validation, endpoints and invalid fractions/anisotropy; NaN and infinity rejected.
- Independent three-dimensional or equivalent quadrature checks of frame-transformed distributions and velocity moments at representative parameters.
- Isotropic/zero-fraction limit against SHM at identical parameters, including truncation and units.
- Published/reference halo-integral or spectrum benchmarks with citations and declared tolerances.
- Speed-support boundaries, tiny rates and high-threshold tails; absolute and relative tolerances near zero.
- Convergence under grid/quadrature refinement without large routine test costs.
- Elastic and both signs of inelastic splitting; more than one operator's velocity dependence.
- Correct solar versus detector frame and the implemented time convention.
- Density and component weights applied exactly once.

### Integration and regression

- Compare real supported detector spectra, accepted counts and limits with independent/reference evaluations. Validate the limit procedure, not just the raw spectrum.
- Fit a small signal and evaluate its null searches using one shared benchmark.
- Compare solar capture to an independent integration/control, including a non-equilibrium case where annihilation need not scale linearly with density.
- Demonstrate accurate refusal/pending for an incapable native/private route, and preservation of an independent exclusion.
- Verify Galactic normalisation/profile qualifications and unaffected constraints.
- Change one parameter, the frame, a generated table's bytes and its data version: dependent caches/checkpoints must separate them.
- Run two distinct halo requests with interleaved resolution; neither may inherit the other's configuration.
- Promotion and resume inherit exactly the resolved benchmark or reject a change.
- Replay legacy results and verify historical exports without rewriting them.
- Rerun phase-1 SHM baselines. Record every changed value or status; unexplained differences block completion.

### Real-browser end-to-end

In each track, choose a supported model, select SHM++, inspect assumptions/applicability, launch a small real calculation, open the correct result, and compare it with the equivalent CLI request. Reopen from history after restart; promote/reanalyse and export/reopen. Confirm the primary calculation and child retain the selected benchmark and every qualification.

Test a missing required input, an unsupported comparison and a changed-data stale result. Keep SHM's ordinary default journey working.

Mutation controls must detect: SHM substituted for SHM++; anisotropy dropped; solar and detector distributions interchanged; a cache omitting mixture parameters; a continuation resetting to SHM; a pending comparison labelled allowed. Check the baseline passes before applying each mutation.

## Completion gate

Write `docs/halo_phase_2_completion.md`: implementation/base commits, scientific specification, source and numerical validation, support matrix, tests/commands, SHM baseline comparison, actual runtimes, browser evidence, substitutions and remaining limits. Update user documentation only for tested support. Prepare an independent audit prompt.

Done means SHM++ is physically validated and useful in both tracks, its limits are accurately exposed, the same resolved configuration survives the whole journey, and SHM defaults remain unchanged. A label-only feature, entirely fixture-based physics validation, or unsupported comparisons silently using SHM fails the gate.

Stop after reporting phase 2. Start phase 3 only when the owner asks.
