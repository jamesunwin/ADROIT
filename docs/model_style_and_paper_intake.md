# Model styles and paper equations (M37.5)

M37.5a–d is complete. The ordered plan and completion receipt are linked from
M37.5a–d.

A required Track 2 property restricts the searched candidate space. A preference
marks matching entries in the likelihood ranking without changing their fit,
significance or AIC. Inelastic means a nonzero mass splitting used in the recoil
calculation. The vocabulary is open: enter any property or model-style statement.
Reviewed declarations carry a source, scope and reviewer; they do not certify a
theoretical completion. Undeclared properties of generic interaction cards are
unknown. A requirement with no established
matching candidates stops before calculation and asks for an eligible saved model.

Paper input selects a physical PDF page and equation label. Upload the paper or
explicitly retrieve its arXiv PDF; source bytes and hashes are retained. Nearby
definitions can be included on additional selected pages. Source equations,
interpreted TeX and the canonical model remain distinct. Review unclear signs,
charges, coefficients and assumptions, refine or apply typed corrections, then
save an approved personal revision. Both tracks select that same exact revision.
Missing parameters and unsupported numerical models remain explicit blockers.

Workbench: select **Model input kind → paper**, upload a PDF or enter its arXiv
identifier, then give an equation label and one to four physical pages. Approve the
intake budget and open the completed draft to refine TeX or canonical YAML. Review
and save it before using its pinned revision in either track. Optional model-property
declarations on the review form are a JSON list with source, scope and reviewer.
Blank retains prior declarations only for an unchanged model; `[]` clears them.

CLI example (replace the session/revision IDs):

```bash
adroit models start --budget 1
adroit models paper SESSION --pdf paper.pdf --equation 3.1 --pages 2,3 --budget 1 --out runs/paper_draft
# Or use --arxiv 1234.56789v2 instead of --pdf.
adroit models draft SESSION STEP
# Refine with models step in the same session, then approve the exact model hash.
adroit models approve SESSION STEP --expected-hash HASH --confirmed
adroit signal --experiment "LZ extended window (2026)" --model 'catalog:MODEL@REVISION' --prefer-style 'leptophilic mediator'
adroit signal --experiment "LZ extended window (2026)" --model 'catalog:MODEL@REVISION' --require-style 'should be composite dark matter'
```

`--require-style` and `--prefer-style` are repeatable. The workbench offers the same
text fields, one statement per line, and an explicit library splitting grid. No
property is selected by default. Multiple required properties must all match;
multiple preferred properties are independent annotations. Unknown required
properties stop or remove unresolved candidates before fitting. To attach a reviewed declaration by CLI, give
`models approve --styles declarations.json`; the file is a JSON list such as:

```json
[{"property":"composite dark matter","state":"yes","source":"paper equation/reference",
  "scope":"specified effective benchmark; reviewed model description",
  "reviewed_by":"actual researcher name"}]
```

Declarations are part of the immutable revision and are shown as assertions, not
physics certificates. Changed model parameters require renewed review; declarations
are inherited only for an unchanged canonical model. New equation material and its
source TeX remain recorded through subsequent typed corrections.

Matching normalizes case and whitespace and removes leading wording such as
“should be”, “with” or “prefer”. It preserves the remaining phrase, including
hyphens and qualifications. Use the same property wording in the request and
reviewed declaration: ADROIT does not infer arbitrary synonyms, negations or logical
combinations. A compound statement remains one opaque property requiring its own
reviewed evidence. Supported numerical properties (currently mass-splitting
inelasticity) use the actual calculation input and cannot be overridden by a
contradictory declaration. The earlier SUSY/inelastic names remain compatible
examples; they receive no default priority or scoring advantage.

API interpretation uses one durable intake budget including retries/refinement.
Original PDF/page images stay in the local personal library and enter the selected
model's source evidence; provider transfer occurs only for selected interpretation
pages. Old analyses retain their original revisions and calculation dates.
