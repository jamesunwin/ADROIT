# Halo phase 1: completion record (2026-11-10)

The implementation of `docs/halo_phase_1_shared_configuration.md`: one shared halo configuration, the inventory of every
consumer, identity, compatibility and the workbench, with the existing SHM physics kept. Phases 2 (SHM++) and 3 (an LMC
benchmark) were not started here.

| | |
|---|---|
| Base commit | `5eb3b37abb8bb4b3e5083c75519f621640d4fa81` (the DU pin, `cr-fixes`; the auditor's DU recheck runs on it, untouched) |
| End commit | the commit that adds this record (branch `halo-phase-1`): the implementation, its tests, the inventory and this record together; the three phase specifications copied unchanged from the owner's checkout |
| Worktree | a scratch worktree of its own; the owner's checkout, `cr-fixes`, `du-fixes` and the running workbench untouched |
| Environment | native arm64 Python 3.12, `uv sync --frozen --offline --all-extras`; writable runs, projects and temporary files in the scratch root; no provider keys, no network beyond 127.0.0.1; `nice -n 10`, `OMP_NUM_THREADS=2` |
| Inventory | [`halo_constraint_support.md`](halo_constraint_support.md) |
| Regression evidence | `scratch_evidence/halo_phase1_2026-11-10/` (the baseline, its comparison, the test and browser logs) |

## Design

**One contract, two choices** (`adroit/core/halo_choice.py`).
- **The family** is a stable machine id with a display label:
  - `shm` (SHM): implemented;
  - `shm-plus-plus` (SHM++) and `shm-lmc` (SHM + LMC): registered with their status, and refused everywhere until
    phases 2 and 3 build them. `available()` and every launch path refuse them before anything is calculated, and nothing
    runs under their names.
- **The treatment** is how a calculation uses the halo:
  - *region*: the SHM uncertainty region, `HaloPreset`, as before;
  - *published*: each experiment's and record's own halo, as before;
  - *benchmark*: one fixed common benchmark, `FixedHalo`.

**The request.** It records the choice in the form it always had, so that every earlier request keeps its saved form and
identity:
- Track 1 and Explain a signal: `HaloPreset`, `"published"`, or nothing (saved before the choice existed);
- Track 2: no field.

The benchmark is new: a `FixedHalo`, holding the benchmark's id, its version, its numerical `HaloModel` copied when the
request is made, and its per-point budget. A later change to the registry never changes a saved request's physics.

**The resolution.** `resolve()` turns any request value into a frozen `Resolution`:
- schema version, family, treatment, benchmark id and version;
- the numbers (ρ₀, v₀, v_esc, v_LSR, the solar and Earth velocities), components and weights;
- frame, axes, units and time convention;
- the declared uncertainty region;
- the halo data files' sha256 (local densities, the count ratio's validation and declaration);
- capabilities, sources, spatial assumptions and limitations, label and summary.

Its `identity` is the sha256 of the physical content only. A label or prose change never changes it; a number, a
convention or a data file's bytes do.

Each run resolves once, before it writes anything (`halo_region.checked` refuses an unavailable family or a benchmark the
machinery cannot evaluate). It saves the resolution with its result (`halo_resolution`) and refuses to publish when a
halo data file changed before its end (`halo_choice.unchanged`; Track 1's software identity check covers the same).

**Capabilities and consumers.** `CONSUMERS` names each halo-dependent comparison, the capabilities it needs (`recoil`,
`solar`, `local-density`, …) and the treatments it supports. `unsupported()` gives the typed, readable reason that a
calculation turns into a named pending reason or a refusal.

**One halo in force.** `halo_region.using`, the context that Track 1 already used for the region, now carries any of the
three values:
- **Track 1** (`scan.evaluate`) dispatches on it. A region is evaluated as before. A benchmark is evaluated by
  `halo_evaluation.at_benchmark`: the point at one `halo_limits.State`.
  - A module whose own published halo the benchmark is (the xenon searches) keeps its own published procedure
    (`halo_limits.own_halo`), never a count ratio.
  - The fast modules run their procedure at the benchmark. CDMSlite (count ratio not validated) gets its full procedure
    within the point's budget.
  - Capture is taken in the benchmark's Sun frame, and the Galactic searches' density is rescaled.
  - Path 1 structures and flavour-vector limits are pending and named, and their published-halo exclusions are not taken.
- **Track 2** (`signal.run`) puts its request's halo in force. `_signal` reads it, so the fit, the toys, the bounded
  fits and the eligibility points follow, and the null limits go by the direct route at the benchmark
  (`_null_halos`; a null whose published halo it is keeps its reference route). The flags are relative to the
  benchmark and say so; the complementary verdicts and the forecast are asked at it.
- **Explain a signal** does both. Its fit and nulls stay at each search's published halo unless the benchmark is
  chosen, which then applies to everything.

The native joint fit and private searches have no benchmark form, and are refused at launch.

**Not built:** an uncertainty prior for any other family, any profile likelihood over the halo, a new count-ratio
validation, any change to `adroit/physics` (fingerprinted by the limit tables) or to `halo_limits.accepted` and `_runs`
(hashed into the count ratio's validation identity).

## Compatibility mapping

| Saved or given | Read as | Identity |
|---|---|---|
| Track 1 request without `halo` (saved before 2026-10-19) | published, *not recorded* (the historical schema: such runs used the published halos) | unchanged |
| Track 1 `halo: published` / a `HaloPreset` | published / region, as before | unchanged |
| A new Track 1 request with no `--halo` | the setting `ADROIT_HALO_REGION`, resolved when it starts (as before) | as before |
| `--halo benchmark` (Track 1, Explain a signal, Track 2) | a `FixedHalo` of `--halo-family` (default `shm`) | new |
| Track 2 request without `halo` | each search's own published halo (its established reading, recorded) | unchanged |
| A result without `halo_resolution` | resolved on viewing from its request, "read from its saved request", no data identities shown | unchanged bytes |
| `HaloEvaluation` without `treatment`, `Bound` without `halo_data` | the region / no halo data bound | unchanged bytes |
| A checkpoint whose request's halo differs | refused, naming the halo | — |

Behaviour that changed where it had mixed or dropped a halo:
- **Track 2 reuse:** a saved Track 1 point is reused in Track 2 only if its halo is the run's (`_other_halo`). A point
  judged over the region had been reused beside published-halo points.
- **Promotion:** a child takes its parent's benchmark. A parent with the published halos leaves the child its own
  default, as before.
- **Reanalysis into another track:** the draft carries the halo where the target has it (`_converted_halo`). It had
  taken the setting.
- **Replay:** an Explain a signal study replays with its own halo (`_recorded_halo`). It had used the published halos.
- **Explain a signal over the region:** a private SI curve or private search is refused, as in Track 1 and
  `docs/halo_region.md`. Its band had applied it over the region beside the module it supersedes.
- **Thermal points:** a thermal point's certificate names its halo label (`certification._halo_label`). It had read
  "the published halo alone".
- **Track 2's IceCube verdict:** the equilibrium fraction is taken in the comparison's halo (`verdicts._channel`).

## Tests and commands

New tests (62), all offline but the browser layer:
- `tests/core/test_halo_choice.py` (10): the contract.
  - The historical conventions are pinned; the registry and the refusal of planned families.
  - The benchmark copied at request time; every treatment's resolution.
  - The identity: stable, blind to labels, changed by every number, convention and data file.
  - A data file changed before a run ends is refused; unsupported comparisons are named.
  - Requests round-trip, and earlier ones keep their saved form; two threads never share a halo.
  - A saved benchmark of an unavailable family is refused.
- `tests/core/test_halo_constraint_support.py` (3): the inventory names every record, module, route and consumer the
  code registers; none it calls halo-independent is varied.
- `tests/orchestrator/test_halo_phase1.py` (23): the calculations.
  - Track 2 at the benchmark, against toy searches whose published halo differs from it: the fit, toys, null limits,
    flags and verdicts at the benchmark. Unset, each search's own halo.
  - The published and benchmark fits differ where the halos do; a private search is refused.
  - Request, result, report and export name one resolution.
  - Track 1's benchmark evaluation: the state in force; a Path 1 structure pending while an independent exclusion
    stands; the scan's dispatch; the own-halo route against the region's count ratio.
  - Continuations: promotion, resume, reanalysis in seven conversions, replay and eligibility reuse.
  - Refusals: the native joint fit and private inputs.
  - Certificates: bound to the halo data and stale when they change; a band point's halo label; the fit's halo in
    force.
- `tests/ui/test_halo_selector.py` (10): the workbench.
  - The command options for every track, and the refusals; each command accepted by the command line.
  - The families listed with the planned ones disabled; a planned family forced behind the form refused, not launched.
  - Explain a signal, Signal best fits, the portal and the typed model each launch the halo chosen beside them.
- `tests/ui/acceptance/test_halo_journeys.py` (13): headless journeys.
  - Track 1 and Track 2 at the benchmark, from the form to the study, export, resume and reanalysis.
  - Five mutation controls, each first passing as built and then detecting its defect at its invariant: the form
    ignoring the choice, the calculation dropping it, a checkpoint's identity omitting it, an export losing the
    qualification, and a future family taken as the SHM.
  - Their five negative controls.
- `tests/orchestrator/test_halo_browser.py` (3): the browser layer offline. Its journeys and controls are registered,
  each mutation applies only in its processes, and each restores its defect.

Changed tests:
- `tests/evidence/test_exports.py` and `tests/evidence/test_points.py`: the new `halo.json`, the `halo` column and the
  halo context line.
- `tests/version_matrix.py` and `tests/evidence/test_version_matrix.py`: the point table's `halo` column declared, and
  each row's halo compared field by field. Both matrix modules: 561 passed, 650 skipped (each a stated N/A), the DU
  round's counts.

Commands and results (`scratch_evidence/halo_phase1_2026-11-10/`):
- **The fast suite on the final tree** (`pytest -q -p no:cacheprovider`): 5,218 passed, 0 failed, 652 skipped,
  3,218 s. That is the DU round's 5,156 and the 62 new tests.
  - Its tree hash was taken before it ran and was unchanged after it.
  - The first full run, 5,186 passed and 32 failed (all in the version matrix: the new column undeclared, a stand-in
    without `halo`), is kept with what changed after it.
- **The headless acceptance gate** (`pytest tests/ui/acceptance`): 42 passed, 306 s.
- **The release browser layer's halo journeys** (`scripts/browser_acceptance.py --only
  network,halo_track1,halo_track2,halo_unavailable,halo_default --repeat 2 --mutation-controls`, Chrome 157).
  - 10 of 10 journeys pass, each twice in a fresh profile with fresh servers:
    - `halo_track1` 158/149 s: the benchmark through Track 1, a real 3 × 2 scan;
    - `halo_track2` 49/48 s: through Track 2;
    - `halo_unavailable` 20/20 s: Explain a signal's native joint fit refused at the benchmark, its reason named;
    - `halo_default` 667/685 s: Track 1 over the region on a real 2 × 2 plane, and Track 2 with the published halos.
  - Each journey covers the form's summary, the launched command, the study, a server restart, the export, the
    continuation and, for Track 1 at the benchmark, a resume refused.
  - 5 of 5 halo controls detect their defect at their invariant.
- **ruff:** clean.

**Not run:** the full release checks (the owner's rule of 2026-11-09: once, on the commit an audit finds ready). Their
slow suite, portal validations, PICO validation, optional backends and setup step were not run. Neither were the other
browser journeys (intake, history, batch, promotion, accounting), which the halo changes do not reach; the fast suite
covers their offline machinery.

## The SHM baseline, compared

Declared before any change (`scratch_evidence/halo_phase1_2026-11-10/baseline/expectations.md`): every number and
string identical, the non-science fields listed apart. The same harness ran at `5eb3b37` and on the branch. The parts:
- **requests:** the saved forms and identities of Track 1, scan, Explain a signal and Track 2 requests;
- **physics:** η and η⊥ for three halos; the fast modules' own limits at two halos; each module's reference limit at two
  masses; PandaX's count-ratio factor; capture in the Sun at two halos;
- **points:** twelve crossings of the halo verdict study, one per outcome it found, each judged with the published halos
  and over the region, every sample;
- **track1:** a whole run with the published halos (the Higgs-portal scalar, 3 × 3) and one over the region (the ALP
  portal, 3 × 3);
- **track2:** CDMS II Si, three candidates, the four nulls, 2,000 toys;
- **single_idea:** Explain a signal on CDMS II Si with the vector model, the published halos and the region, a 4 × 4
  plane.

| part | different | added (phase 1's fields) | not science |
|---|---|---|---|
| requests | 0 | 0 | — |
| physics | 0 | 0 | — |
| points | 0 | 0 | timings |
| track1 | 0 | 7: each result's `halo_resolution`; over the region, each of five crossings' certificate `bound.halo_data` | timings |
| track2 | 3: each candidate's interaction `id` | 1: `halo_resolution` | timings |
| single_idea | 6: each band point's reference interaction `id` | 4: `halo_resolution` of each study and its plane | timings, dates |

Each `id` is a fresh random UUID drawn in every run (`core.state._new_id`), not science. Every other value is identical:
every limit, ratio, status, pending reason, label, sample, construction, statistic, significance, toy count and
certificate check.

Its limits:
- It is a sample, chosen for low cost across every outcome, not the 256-crossing halo verdict study.
- Neither single-idea run has a thermal point (the model gives none on its band), so the band point's new certificate
  label is checked by its unit test only.
- It repeats no count-ratio validation; it checks that the validation is read and used identically.

## Costs

All runs are at nice 10 with two threads, beside the auditor's DU audit; wall times include that load.

| run | at `5eb3b37` | on the branch |
|---|---|---|
| baseline: requests / physics | 24 s / 17 s | 1 s / 16 s |
| baseline: twelve points, both treatments | 1,003 s (region 944 s of it) | 980 s |
| baseline: Track 1, published / region | 47 s / 898 s | 45 s / 868 s |
| baseline: Track 2 | 64 s | 39 s |
| baseline: Explain a signal, published / region | 40 s / 767 s | 39 s / 589 s |
| fast suite | — | 3,412 s first run, 3,218 s on the final tree |
| headless acceptance gate | — | 306 s |
| matrix modules (rerun after the column) | — | 801 s |
| browser layer, the halo journeys twice and their controls | — | about 1.5 h |

The benchmark's own cost in Track 1 is that of one halo of the region. The xenon searches take their table at their own
halo, and the fast modules run their procedure there; CDMSlite's full procedure is spent only where a point needs it,
within the budget of 2.

$0: no provider call, no network beyond 127.0.0.1.

## Substitutions

- **The headless journeys** (`test_halo_journeys.SUBSTITUTED`):
  - Track 1's points are a toy evaluation (Ωh² = 0.12 m_χ/100 GeV, colliders allowed). The halo in force is recorded
    as its value, and the halo's dispatch, the benchmark's evaluation, scan, verdict, certificate, writer, pages and
    exports are ADROIT's own.
  - The setup check's machine items are reported as not used, and scan workers run as threads.
  - Track 2's search and null are a toy germanium module with real recoil rates and the older published halo.
  - The complementary verdicts are recorded with the halo they are asked at, not computed.
- **The browser layer:** no calculation substituted. Each run computes its own points:
  - a typed vector model on a 3 × 2 plane at the benchmark, and on a 2 × 2 plane over the region;
  - CDMS II Si at 10 GeV with 1,000 toys and the four nulls.
  - The calculation cache is the checkout's own, shared as journey 2's is.
- **The baseline:** none. Its only substitution is its small size (above).

## Remaining limitations

- **Existing inconsistencies, documented and not changed** (they would change default results; the owner's to decide):
  - Track 2's halo flags vary the default SHM, not each search's own halo;
  - IceCube's limit is converted to a capture rate at the default SHM (*corrected 2026-11-12, the auditor's halo phase 1
    audit, HA-06:* in Track 1 and Path 1; Track 2 converts it at the comparison's halo, the one its candidate's
    capture is taken in);
  - `hess-2608.07234-lines` is rescaled by ρ₀² over the region and at the benchmark, although its record says its limit
    is not rescaled;
  - the ⟨σv⟩ velocity conventions differ between the tracks and never follow the halo;
  - the default halo's values live in `core/dm_state.py`, which the limit tables do not fingerprint; a test now pins them
    (`tests/core/test_halo_choice.py`);
  - an anomaly record without a halo is given the older convention silently.
- **Not offered:** a halo choice on `adroit exclude` (Path 1; its telescope rows always use the default SHM) and on
  `adroit promote` (a child inherits its parent's).
- **Not established:** a resume of a checkpoint saved before the halo choice existed. It is refused, its software
  identity differing in any case.
- **The fixed benchmark's own limits:** it is a point, not an interval. CDMSlite at the benchmark can leave a point
  pending on its budget (2 full procedures a point), as over the region.

## Not started

Phase 2 (SHM++) and phase 3 (an LMC benchmark): the owner queued them, in order, once this phase is complete.
