# ADROIT 1.0.1: release notes

A corrective release of ADROIT 1.0.0. It repairs a direct-detection defect that strengthened some spin-dependent
exclusions, closes the paths by which a missing or incomplete nuclear-response installation could change a fit without
warning, and repairs several defects found by independent audits of the release. The
1.0.0 notes ([`release_notes_v1.0.0.md`](release_notes_v1.0.0.md)) remain the description of the release's scope and
known limits; this file lists what changed.

## Physics corrections

**Spin-dependent direct detection with both nucleons coupling.** Where a xenon search is validated for one
spin-dependent kind only (PandaX-4T between about 148 and 341 GeV, validated for proton but not yet neutron
couplings), a model coupling to both protons and neutrons is compared by rescaling its rate onto the published
proton limit. That rescaling used the shell-model nuclear responses, while the limit itself was computed with Klos et
al.'s structure factors, as the collaborations' are. For equal couplings it was about 25 times too large (≈ 900
instead of ≈ 36), so models of this kind could be reported as excluded by direct detection when they are not. The
rescaling now uses the limit's own nuclear prescription and target.

- **Who is affected:** studies with both spin-dependent couplings non-zero (for example an axial-vector mediator
  coupling universally to quarks) and a dark matter mass between about 148 and 341 GeV. Spin-independent comparisons,
  other experiments and models with one nucleon coupling are unaffected. A study saved with 1.0.0 keeps its stored
  verdicts: **re-run it** to obtain the corrected ones. (`adroit reassess` does not recompute these comparisons: it
  keeps each completed point's saved direct-detection comparison.)
- **The reported cross section.** For such points the saved spin-dependent cross section had been the rescaled,
  experiment-equivalent value; it is now the model's own per-nucleon cross section, with the rescaling factor recorded
  beside it. (Other comparisons keep their convention: an isospin-violating spin-independent point, for example, is
  stored as the cross section equivalent to the experiment's.) The direct-detection plot, for every study whose points
  saved their comparisons, draws each point against the limit of its own stored comparison: above it when excluded, below it when allowed, and,
  where proton–neutron interference leaves the comparison undecided, inside the limit's drawn range (open-ended where
  the couplings can cancel). A study saved before its points kept their comparisons is drawn against the limits for a
  pure coupling, labelled as such, not as the model's own boundary.
- **Accuracy.** The rescaling is a ratio of recoil rates before the detector's acceptance; at 250 GeV in xenon it
  differs from the detector-level ratio by 9% (equal couplings) to 15% (opposite couplings), so a point within that of
  its limit is decided only to that accuracy. A margin is scheduled for 1.0.2.
- **Stored limit tables** are unchanged: the correction lies outside them.

**The revised xenon nuclear responses must be installed to be used.** The LZ extended-window search uses Haxton &
McElvain's revised xenon responses. If their runtime was missing, the calculation silently used the older shell-model
responses under the same name and could return a resolved fit with different couplings and intervals, and so could
an installation missing one published density matrix (¹²⁹Xe's alone moved the axial example's best-fit coupling from
0.561 to 0.710). Every workflow now refuses before calculating, naming what is missing: the runtime, the Mu2e script,
or each published matrix for the target's isotopes, which must be present and readable (`adroit setup` lists them).
This holds for Signal best fits and Explain a signal (their signal and null searches), Path 1 exclusion when the
revised responses are requested by name, and the forecasts. Isotopes for which no revised matrix is published (¹²⁴Xe,
¹²⁶Xe) still use the shell model, as before and as recorded.

## Other corrections

- **Joint explanations and exclusions.** A thermal point whose experimental comparison has an open prerequisite (for
  example an experimental record of unknown version) is no longer read as a thermal explanation of a signal: it is
  undecided, with the reason shown. An exclusion stands only on a deciding comparison whose own records are
  established: in both the separate-cut and the combined-likelihood modes, at the reference halo and at every sample
  of the halo region, for grid points and thermal points, whether the deciding comparison is named on the point or
  kept in its certificate, in the point table, plot and export, and in a regenerated Explain-a-signal plane, which is
  read again and says so where its reading changes. (A study's saved report and figures are its publication and are
  not rewritten: re-run, or regenerate them, for today's reading.) A thermal point
  whose certificate lacks its thermal checks is not counted as thermal.
- **One halo.** Explain a signal calls the signal and the constraints "the same single halo" only where every
  halo-dependent comparison (direct detection, capture in the Sun, the Galactic γ-ray line and antiproton searches)
  is shown to have used the signal's halo; a comparison whose halo was not saved counts as unknown, and the joint
  reading is then qualified. A saved plane's common halo is established again from its points' evidence when it is
  read, never taken from the flag saved with it.
- **Reassessment** writes only to a new folder: an existing folder, or the saved study itself under any name, is
  refused before anything is calculated or written; repeating the command makes `<study>_reassessed_2`, and so on.
  The new folder is claimed by its exclusive creation, so two reassessments can never share one; on a failure it is
  removed only if nothing was written in it, and otherwise kept, the error saying where. A reassessment never
  removes anything anyone wrote, and a study moved into its folder before it writes is never written over (another
  process renaming a study into the folder while it is writing is outside what it guards against).
- **Standard models.** A supplied mass or vacuum value the model's engine does not follow is refused rather than
  replaced by the benchmark's, and the unsupported inelastic dark photon is refused whatever it is renamed.
- **Path 1 exclusion.** Stating a search's own published halo (its label aside) no longer switches it to a direct
  calculation, and a direct calculation of a single-response interaction uses the validated procedure's nuclear
  prescription whatever its route; a direct limit is marked validated only for that prescription. Saved results record
  the prescription each direct limit was computed with.
- **Checklists.** A fixed-coupling study (the electroweak multiplets) shows the relic density and constraints it
  computed, rather than "not yet computed".
- **Plots.** The parameter plane draws every constraint that excludes somewhere (those without a colour of their own
  hatched), so that no exclusion is left to the notes; Explain a signal's plane colours its thermal solutions by
  whether they lie inside the fit's 68% interval at their mass, and no longer hatches the signal criterion's region
  (an option, `signal_region`). It marks a thermal solution "verdict may be unreliable" only for a real warning, not
  for an informational note such as "excluded throughout the tested halo region".
- **Tests.** The test suite reads the command line's plain text on continuous-integration machines too, and the tests
  that render PDF pages declare their need for Poppler's `pdftoppm`, skipping with its name where it is absent.

## Validation

- A regression for each correction fails before it and passes on 1.0.1.
- Independent audits reproduced the corrected rescaling factors with a direct spectrum calculation, confirmed that
  the stored limit tables are unchanged, and checked the repairs above.
- The full release checks were run on this release before publication (2026-11-27): lint; the fast suite with and without the external tools (6,730 and 6,186 tests); the slow suite; the portal-library validations; setup; 58 headless and 42 of 42 real-browser acceptance journeys. Of the 19 mutation controls, 18 were detected; the nineteenth was interrupted by the browser not answering a page load, and was detected on the same code in the development repository's run. Two optional steps were skipped offline, as documented.

## Known limits added in this release

Recorded with their repairs for 1.0.2: the rescaling's detector-level accuracy (above); and the refusal of missing
revised responses sits at the workflows rather than in the lowest-level response function, which a direct library
call must therefore precede with `experiments.prescription.require` (moving it would invalidate every stored limit
table). Everything deferred before 1.0.1 is now scheduled for 1.0.2.
