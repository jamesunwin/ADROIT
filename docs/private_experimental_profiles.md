# Private searches and experimental profiles (M36.5f–h)

M36.5f–h is complete within the scope below: 122 focused/1453 fast/25 slow tests.
Receipt: local report (summary). Acceptance does not substitute for source review.

Private event searches reuse ADROIT's fidelity-B nuclear-recoil event adapter.
Declare target, exposure before selection, keVnr window/events, true-energy
efficiency, constant Gaussian resolution, background shape/treatment and all four
halo parameters. The initial validation contract supports **elastic isoscalar
contact O1 only**, over its explicit mass range. Binned observations, correlated
nuisances and arbitrary native workspaces remain stored references with calculation
blockers. Neither an uploaded PDF nor a source signature creates missing numerical
machinery. Native joint fitting continues to use its separately supported packaged
pair; a private reconstruction is not silently substituted into it.

An event result needs `search_contract` and `adapter_validation_reference` claims.
The contract declares signal/null role, benchmark, domain, dataset identity, overlap,
explicit replacement targets, assumptions and the limit procedure. Select either
optimum interval without background subtraction or maximum gap without background
subtraction. Missing optimum-interval code blocks that declared procedure; there is
no implicit method change. Its native90 and95 calculations are validated separately.

The separate reference contains at least three mass anchors spanning both domain
endpoints, with SI normalization, expected signal count, normalized densities at
actual events, fitted signal count, profile log likelihood and90/95 rate-multiplier
upper bounds. The reference must have independently checked source evidence in a
distinct selected asset. A copied output in a new file is not scientifically
independent. Response/interval/count errors are relative; fitted-count/log-likelihood
errors use a unit floor near zero. Fixed-background log likelihood omits the
parameter-independent constant -B, matching the existing engine convention.

In the workbench, open the experimental revision, review its complete event scope,
record the source assertion under your own name, validate independent anchors, then
prepare the pinned search. Source approval and numerical validation are separate.
Scientific edits create a new revision and require matching new receipts.

CLI sequence:

```bash
adroit experiments review EXPERIMENTAL_REFERENCE --result signal --out runs/source_review
# Review the packet, then use verify-source with its expected hash and all checks.
adroit experiments validate-search EXPERIMENTAL_REFERENCE --result signal --expected-hash HASH --tolerance 0.001
adroit experiments bind-search EXPERIMENTAL_REFERENCE --result signal --review REVIEW_ID --validation VALIDATION_ID
```

`private-search:SHA` is a pinned, reviewed, validated input. A private signal cannot
be used as an independent null. A private null contributes Track2's explicitly
labelled limit-equivalent term, rather than an invented official likelihood.
Unsupported mass/operator/splitting combinations are uncomputed/pending or refused;
they are never treated as valid exclusions or allowed models.

Open **Experimental profiles** to choose exact published limits, signal and
null searches. Review all datasets, independence, replacements and adapter/source
scopes. Save an immutable profile under your name, then explicitly activate it for
fresh runs. Activation and rollback use the displayed previous selection and refuse
a stale page. No packaged records or previous reports are rewritten.

Track1 preserves packaged constraints except explicit replacements and adds selected
private published-limit cuts and private null native95 cuts. Track2 uses the profile's
exact signal/null selection. Private published limits pass to physical child/Track1
studies; general NR candidate eligibility filtering remains M38. A profile review
does not certify a likelihood combination unavailable from the source.

```bash
adroit experiments profile-review --limit PRIVATE_LIMIT --signal PRIVATE_SIGNAL --null PRIVATE_NULL
adroit experiments profile-create "My profile" --limit PRIVATE_LIMIT --signal PRIVATE_SIGNAL --null PRIVATE_NULL --expected-hash HASH --by "My name" --confirmed --independent
adroit experiments profile-activate PROFILE_REFERENCE --expected-current PREVIOUS_REFERENCE --confirmed
adroit track1 MODEL --profile PROFILE_REFERENCE --no-literature
adroit signal --experiment PRIVATE_SIGNAL --model MODEL --profile PROFILE_REFERENCE
# Explicit baseline run:
adroit track1 MODEL --profile none --no-literature
```

With no `--profile`, new CLI requests select the active personal profile once. The
workbench shows it and pins its exact reference in the queued command, including
`none` for packaged defaults. Changing activation later leaves queued/pinned jobs
unchanged. Bare Track1 resume uses its original request; a different profile cannot
reuse its checkpoint. Promotions and single-idea children retain the same profile,
model revision, limits and null selection.

Revisions, profile creation/activation and calculation/report dates are distinct.
New and historical evidence bundles retain those dates and exact input identities.
Selected-point/fit replay uses captured compatible payloads without the personal
catalog; it does not imply a repeat of the global toy calculation. Original papers
can remain reference-only in exports, with missing source bytes disclosed.
