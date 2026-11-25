# Track 2 performance pilot

The owner authorised profiling Track 2 end to end after publishing the validated
Track 1 integration (`796e3f5`). This increment targets repeated work demonstrated
by profiles, preserving physical inputs, fitting, detector statistics, toy counts,
seeds, domains, constraint provenance and pending outcomes.

## Targeted changes

External-tool lookup repeatedly parses the same `tools.yaml`. `load_manifest`
now reuses the validated parse of identical file contents. It reads the file on
every call, returns an independent deep copy and bounds the process-local cache
to eight contents. Changed contents are validated immediately, even when the file
size and modification time match. Lookup still checks the filesystem for backend
availability. No detector result or physical number is cached by this change.

Track 1 recovery fingerprints are also part of single-model studies and promotion.
Traversal now reuses parent-directory resolution and relative names within one
fingerprint call. File content hashing, metadata checks, exclusions and symlink
handling retain their original rules. Directory reuse expires after the call;
the existing content-digest cache and checkpoint refusal rules remain in force.

## Measurement scope

The development case is CDMS II Si (2013), with 18 explicitly selected library
candidates plus a vector-mediator user model at 5, 10 and 20 GeV. It carries three
leaders into four null searches, using 1,000 background-only toys. The user model
then receives a single-idea study and one promotion into a Track 1 study, each
with three masses and a 4×4 physical parameter grid. Literature retrieval is off;
unverified constraint records are explicitly requested. This is a bounded
performance case, not a new calibration or protected evaluation.

Profiles distinguish the initial native-backend calculations from their existing
disk caches. Unprofiled signal timings use isolated committed/current source
in both orders. Complete result JSONs, not only rounded headlines, are compared.
Heavy runs use low priority, one scan worker and two native threads. No paid LLM
calls or DM10 held-out halves are needed. Evidence and command logs are local and
ignored (summary).

## Result, 2026-10-06

The full chosen signal pipeline takes 71.8753 s before and 36.7491 s after in
ordinary both-order measurements: 1.95584× faster, or 48.8711% less time. Complete
signal, single-idea and promoted-child JSONs match exactly; all four ordinary
signal runs also match. Warm fingerprint traversal returns the same dependency
identities and takes about half the time. The initial single-idea profile also
includes native-backend cache warming, so its larger timing reduction is not
claimed as a code-only gain.

Validation passes: 1,054 fast tests, 22 slow tests, focused identity/mutation/
availability checks, Ruff and diff checks. Protected validation data, records and
the held-out ledger are unchanged. New paid spend is zero. The local
report (summary) contains the numbers,
source lines and retained evidence. This Track 2 increment was committed and
pushed as `2bde23b`; the earlier Track 1 integration is also published.

The remaining measured cost is native detector calculation, especially initial
CDMSlite reference limits, PICO's Neyman construction and additional native-95
masses. Input-bound persistent reuse or batching is the next proposed investigation;
it requires separate validation of source/backend identities and statistical
construction before increasing scan coverage with the saved time.

## Planning status clarified, 2026-10-07

| Planned item | Status | Evidence |
|---|---|---|
| Profile candidate fitting → null comparisons → single-idea → promotion | Complete for the declared development case | `2bde23b`; saved complete signal, single-idea and promoted-child JSONs agree exactly. Profiles identify repeated manifest/identity work and remaining detector costs. |
| Remove demonstrated duplication while preserving science and eligibility | Complete for the measured duplication | `2bde23b` and `c061e12`: exact manifest reuse, fingerprint traversal reuse, input-bound detector calculation reuse and exact signal-spectrum reuse. Full scientific comparisons preserve fitted parameters, likelihoods, significance, domains and pending outcomes. |
| Fit directly within physical bounds when amplitude inversion fails | Implemented for the existing one-coupling band | `parameter_space/physical_fit.py` fits the actual profiled recoil likelihood within declared `g_chi` bounds, or the existing original-sign perturbative branch on failed inversion. Boundary/mode/coverage metadata and raw NR references remain separate. See [bounded physical fitting](bounded_physical_fitting.md). |

The broader detector-reuse and coverage follow-up is recorded in the local
closeout report and its closure metadata (summary). Whole-signal
benchmarks on Si, Ge and LZ demonstrate gains for their declared cache states;
this does not imply all possible repeated likelihood/response work was removed.

Bounded physical fitting uses declared ranges, actual spectra and independent
dense-scan checks, rather than clipping an unconstrained amplitude. This first
increment keeps masses and other couplings fixed. Multi-parameter physical fits,
native joint signal/null likelihoods and recalibrated discovery significance for
the physical search domain remain further extensions.
