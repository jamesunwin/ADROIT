# Expert source review and private Track 1 limits — M36.5d–e

These increments add **scoped expert source review**, **independent numerical
validation**, and **explicit per-run private limit selection**. They reuse the
experimental catalog and recorded UTC chronology. Packaged records, default
experiment modules, historical results and public/shared libraries are unchanged.
Full persistent activation profiles/rollback remain M36.5g.

## Source review is separate from numerical validation

Open an experimental revision and its **Expert source review** panel. Select the
scientific fields to review and inspect the original source, canonical values,
units/axes, confidence construction, benchmark assumptions, overlap/replacement
declarations and digitisation uncertainty. The panel shows old/new field changes.
Limit plots compare decoded values with independently source-linked anchors. If
explicit source-axis calibration is supplied, a second plot overlays the curve
on the original source panel; absent calibration is reported instead of invented.

The expert enters their name and attests to each displayed check. Approval binds
the selected scientific payload, common source context, dataset relationships and
source bytes. This is a recorded personal assertion, not a cryptographic identity
certificate. Agents cannot sign it. Editing confidence level, benchmark, values,
calibration or source identity changes the binding. Editing an unrelated result
does not silently alter the selected scope. Historical approvals remain dated.

The numerical validation action is independent: it compares the declared adapter
with reference anchors, at least three distinct coordinates for an SI curve and
one printed reference for a scalar bound. Set the tolerance before checking. Failed
validation preserves its receipt and cannot enable a limit. Source review does not
imply adapter validation; matching anchors does not imply expert source approval.

**Each anchor needs numerical evidence of its own** (the owner's rule, 2026-10-19;
made stricter after the focused audit of 2026-10-19, FA-01 and FA-02, and its
recheck, FR-01 and FR-02). Each anchor declares its **lineage**
(`validation_reference.lineage`, one per point), typed so that it is bound to its
evidence: `{"derivation": "printed_text", "document": the file's name, "page"}` or
`{"derivation": "published_table", "document", "row", "mass_column",
"limit_column"}`. The lineage must name the file the anchor's locator cites and the
same place (its page; or its row); a published table's named columns at that row must
hold the anchor's two numbers, and the limit column's header (with its qualifiers)
must not state another result (an expected or median sensitivity for an observed
curve, another confidence level). A digitisation, a re-export or anything derived
from a figure is never evidence, whatever file it sits in. The anchor's locator must
print its mass and its limit **together**:

- from a **separate source whose independence is established**: a file ADROIT itself
  retrieved from the publisher (HEPData or arXiv, through constraint discovery: the
  revision records each file's address and the sha256 of its bytes), the authors'
  printed document (a PDF's text, with its page) as much as a data file. A file of
  undeclared origin (an export, a transcription, a PDF or data file you added
  yourself) counts as nothing on the ordinary validation, whatever it says about
  itself and whatever its format (the tactical audit's T20-09, 2026-10-20: a PDF
  printed from the curve's own numbers had passed as the authors'); retrieve the
  paper or the published table, or verify the curve by hand; or
- for a curve **digitised from a figure** (`origin: figure_digitised`), from the
  **same paper's printed text** (`method: text`, with its page): one sentence that
  pairs the mass with its unit (GeV, TeV, MeV) and the limit with its unit (cm², a
  barn), outside the figure itself, so that axis ticks, labels and lists of
  numbers pair nothing; one sentence anchors one point. This checks the figure's
  transcription against the published text; it is not independent confirmation of
  the experiment, and its receipt says so ("figure transcription checked against
  published text").

A number read again from the plot (a visual locator) never qualifies; a printed
value that happens to equal a digitised point does (copying is refused by its
lineage, not by equality); one unrelated separate source does not qualify the other
anchors. Same-paper anchors need the reference to declare its result,
`"result": {"selection", "confidence_level", "dataset_id", "benchmark"}`, equal to
the curve's. The **sentence the anchor is printed in** is checked against the
curve's result, with the quotation's preceding sentences speaking where it is silent
(FR-02: "These are the combined limits from Run A and Run B. At 12 GeV the upper
limit is …" states a combined result); a clause stating two results (observed and
expected, or two cross-sections) is ambiguous and refused: a printed confidence level, in figures or words
("95 percent confidence"), must match; an expected sensitivity against an observed
curve is refused (the word "sensitivity" alone, "improving sensitivity by a factor
of two", is not one); a combined result is refused against a curve that does not
name its constituent datasets (`limit_contract.datasets`: punctuation in an
identifier is not evidence of a combination; "combined systematic uncertainties"
is not a combined result); a run the curve does not hold ("Run B") is refused until
you resolve which result the sentence states (a run's name looks like one: "Run 2",
"Run A", "SR0", "WS2024"; "an exposure of" and "the dataset collected" name none); a spin-dependent or single-nucleon
result is refused against the isoscalar SI benchmark.

**The allowance and the tolerance are fixed before the comparison.** For a
digitised curve each anchor's allowance is its printed rounding plus the declared
reading errors, `y_round + y_err + δL`, with δL the curve's own variation, through
its declared interpolation (linear or logarithmic axes), over the mass interval
`x_round + x_err` (FA-05), never above the tolerance. The tolerance itself is the
one the reference declares (`validation_reference.tolerance`, reviewed with it) or,
if none, the one the comparison's numbers were first compared at (FA-04; FR-03: the
policy is keyed by the curve's numbers and stated result and the anchors' numbers,
so editing a lineage label or a note does not reset it): a comparison at another
tolerance is refused, so a failure is never turned into a pass by widening it; a new
tolerance needs a declaration in the reference, reviewed again, and is recorded as a
revision of the policy. An attempt refused before any numerical comparison fixes
nothing.
An anchor printed too coarsely to check the transcription at the tolerance ("about
10⁻⁴⁶") is refused. Each anchor's document hash, page, method, quotation (or table
cell), lineage, rounding and allowance are kept in the receipt.

**The manual figure-verification route** (`adroit experiments verify-figure`, or
"Verify the figure by hand" on the review panel) is for an SI curve digitised from a
figure whose paper prints only one or two anchors (often its best sensitivity): one
headline point cannot show that the rest of the curve was transcribed correctly. It
needs the calibrated source overlay (`figure_axes`: the page, the plotting frame and
its axis ranges), the declared mass range restated in full, every printed anchor
checked as above, five attested checks (`calibrated_overlay_inspected`,
`full_mass_range_reviewed`, `printed_anchors_checked`, `axes_units_and_scales`,
`same_result_as_anchors`), your name, and the review packet you inspected (the
folder `adroit experiments review --out` wrote, or the one the review panel drew:
`--packet`). Its receipt reads "manually verified
against the figure with limited numerical anchors", never a pass of the three-anchor
validation; a curve with three anchors uses the ordinary validation. The receipt
records what you looked at, from that packet itself (FR-04): the source page it was
drawn on (kept in the packet), the decoded curve's geometry on it through the
calibration, and the overlay image; the packet must be intact and drawn for this
curve, and no second rendering stands in for it. After a code update,
`adroit experiments renew-figure VALIDATION` checks its anchors again, renders the
overlay again and carries your verification over only while both are unchanged;
otherwise it asks for a new visual review (`verify-figure`; FA-06). The original
verification stays as its own receipt. Validations of likelihoods and
detector responses (private searches) are unchanged.

For published-curve adapters, this validates transcription/interpolation against
independent source values. It does **not** reconstruct the experiment's likelihood
or supply information absent from the paper. If reliable anchors, detector inputs
or assumptions are unavailable, retain a draft/pending input. Source-reviewed
M37 event values are separately recorded in evidence; their fidelity-B reconstruction
does not become an official likelihood through source review.

## First supported private limit contracts

Store a `limit` result with two source-linked claims:

- `limit_contract`: the typed contract described below, including observed/expected,
  native CL/construction, quantity/units, exact benchmark, dataset ID and overlap,
  source panel, assumptions, domain and uncertainty.
- `validation_reference`: `{"points": [[coordinate, published_value], ...]}` (with
  `"result"` for same-paper anchors) and a locator for each anchor, as above. These
  are published values, not numbers copied from the digitised curve being checked.

The first supported contracts are:

| Adapter | Exact benchmark | Quantity/domain |
|---|---|---|
| `si_isoscalar_curve` | `elastic_contact_O1_cp_equals_cn` | `sigma_nucleon_cm2`, units `cm2`, strictly increasing positive mass/limit points, explicit mass range and native halo |
| `sm_higgs_invisible` | `SM_higgs_125_production` | `BR_h_invisible`, units `dimensionless`, one positive bound ≤1; only the simple scalar/fermion/vector SM-like Higgs portal classes |

SI application checks the actual active interaction terms: pure constant O1 with
equal proton/neutron coefficients. Momentum-dependent, isospin-violating, inelastic
and mixed/subleading-operator interactions need a dedicated recast. The vector
mediator's fuller operator reduction is deliberately not silently treated as pure
O1. Pure SD predictions are labelled not applicable. Full-density curves require
`relic_fraction=1`; no density or benchmark rescaling is invented. Native source
halo assumptions are retained. Other model/quantity contracts remain unsupported.

`points`, `mass_range`, `x_scale`/`y_scale` specify interpolation in the actual
source coordinates. Nothing extrapolates beyond the declared data/domain.
`origin` distinguishes machine tables, printed scalar bounds and figure digitisation.
Digitised values require declared relative x/y errors. The comparison conservatively
brackets interpolated limits over those axis/value errors, including curve knots.
If the prediction straddles that interval, the cut stays undecided. These errors
are not converted into experimental covariance or confidence bands.

Only **observed** limits with explicit reviewed overlap declarations can be selected.
Native 90% values remain native; the 95% Track 1 decision stays pending without a
justified source-likelihood conversion. Private published limits stay **hard cuts**,
including in optional combined-likelihood runs; no extra likelihood term is invented.

## Additions, replacements and reproducibility

`overlap` must declare either `disjoint_from_selected` or `supersedes`. Unknown
overlap cannot become an eligible selection. Replacements name exact inputs:

- SI curves may supersede an existing null-module name, removing that module from
  the active 95% envelope in this run only.
- SM-like Higgs bounds may supersede `atlas-2301.10731-hinv`, replacing that
  comparison and removing its old ratio from the combined calculation.

Two selected inputs cannot share a dataset ID or replace the same existing input.
The researcher must check the declared independence; a new dataset name alone is
not proof that experiments are independent. The fuller profile/combination
management remains g. Native-90% baseline envelope views remain labelled historical
references and are not the active replacement's 95% decision.

After both review and validation pass, **Prepare pinned private-limit selection**
creates `private-limit:LIMIT_SHA256`. It does not activate a global default. Select
it explicitly in the Track 1 wizard or repeat `--private-limit` in the CLI. The
request and scan embed the exact bound payload; workers and refined thermal roots
use that same selection. Source/code changes invalidate current validation/use;
resume refuses changed selections. Existing results and their original dates stay
historical. Evidence exports include review/validation/binding snapshots and reference
source hashes; selected-point replay works without the personal catalog.

## CLI

```bash
uv run adroit experiments review 'experimental:EXPERIMENT_ID@REVISION_ID' \
  --result RESULT_ID --out runs/source_review
uv run adroit experiments verify-source 'experimental:EXPERIMENT_ID@REVISION_ID' \
  --result RESULT_ID --expected-hash REVIEWED_HASH --by 'Expert name' --confirmed \
  --checked source_values --checked source_units_axes --checked confidence_construction \
  --checked benchmark_assumptions --checked dataset_overlap --checked digitisation_uncertainty
uv run adroit experiments validate-limit 'experimental:EXPERIMENT_ID@REVISION_ID' \
  --result RESULT_ID --expected-hash REVIEWED_HASH --tolerance 0.02
uv run adroit experiments bind-limit 'experimental:EXPERIMENT_ID@REVISION_ID' \
  --result RESULT_ID --review REVIEW_ID --validation VALIDATION_ID
uv run adroit track1 my_model.yaml --private-limit 'private-limit:LIMIT_SHA256' \
  --no-literature --out runs/private_comparison
uv run adroit track1 --resume --out runs/private_comparison
```

Use the IDs/hashes from the actual receipts. `--key` on review/verification permits
narrow field scopes. Preparing a limit requires the exact contract/reference scope.
No `--unverified` override, API call or paid service is needed for d/e. Further
adapters and official numerical validation are separate scientific implementations,
not something an approval checkbox can manufacture.
