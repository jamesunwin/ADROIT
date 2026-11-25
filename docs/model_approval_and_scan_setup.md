# Faithful model approval and model-aware scan setup (M33–M34)

When approving a supplied Lagrangian from an idea study, the workbench preserves
its complete canonical ModelSpec: interaction terms, coefficients, explicit zeros,
signs, masses, assumptions and model/certificate contracts. It does not substitute
the separately generated general Lagrangian. For an input that was only field
content or a plain-text field proposal, the generator's Lagrangian is still the
model being reviewed.

A generated general completion of a supplied Lagrangian appears as an explicit
alternative. Selecting it shows the changed model and parameter/term differences;
its structural audit is checked separately. Selecting a completion does not copy
the original numerical parameters into new interactions or invent missing values.
Full TeX editing and guided refinement remain M36 work.

Approved models are written as spec-wrapped YAML with an approval digest. The
workbench passes the independently reviewed model digest to Track 1, so changing
the file—even its own receipt—cannot silently change the reviewed model. The
Python boundary checks the same identity and rejects inconsistent explicit engine
or reference-point overrides. Existing raw/spec-wrapped model YAML remains usable;
legacy files do not acquire a retrospective approval claim.

The approval form also shows the actual scan plane before launch. The typed-model
wizard shows its scan setup as soon as there is a model, and **Scan** accepts the
setup shown (the owner, 2026-11-22: a separate review button read as optional). An
edit to the model, axes or mass relation applies at once, and Scan runs it. The
setup shown includes:

- active and inactive Point coordinates, their model-specific labels;
- axis ranges, spacing and sample counts;
- fixed Point values and any declared mediator/DM mass relation;
- the numerical engine contract at its reference point, including explicit flavour
  currents or potential parameters that are not generic Point slots;
- mapping notes, including any existing library-benchmark defaults for missing values.

The engine contract is a reference description: parameters mapped to a free Point
coordinate change during the scan. For a complete scalar potential the derived
quadratic coefficient follows the existing `CompleteScalarPortal.resolve` mapping;
this page does not redefine that physics.

Simple Higgs and Z portals use DM mass and their dark coupling rather than scanning
the fixed SM mediator mass. Other defaults reuse a matching library plane or the
engine's declared coordinates. A supplied negative coupling retains its sign branch
when the default template uses a positive logarithmic coupling. No benchmark mass
relation is added to a user model automatically. A chosen `mediator_ratio` removes
`m_med` from the independent axes; fixed-mediator models refuse such a relation.

UFO coordinates come from their declared parameter expressions; flavour-vector
unused `g_q/g_l` slots cannot be scanned as if they controlled the named currents.
The 25 existing portal-library planes are retained. The portal wizard also previews
its benchmark's fixed values and derived mass relation before scanning.

The CLI and Python calculation boundaries reject inactive/unknown axes and stale
review identities before evaluating physics. The workbench supplies review hashes
automatically. Direct CLI use can omit explicit axes to select the model-aware
defaults, or override the ranges with active coordinates:

```bash
uv run adroit track1 my_model.yaml --no-literature --out runs/my_model
uv run adroit track1 my_higgs_model.yaml \
  --x m_chi:70:90:log:4 --y g_chi:0.01:0.1:log:4 \
  --no-literature --out runs/my_higgs_scan
```

`--approved-model-hash` binds a supplied model, and `--reviewed-scan-hash` binds its
engine mapping, reference values, axes and relation. Saved requests retain these
identities through existing checkpoint, evidence and resume machinery. A new
software/data identity still requires a new run according to the existing rules.
Historical results with inactive axes remain readable/replayable as historical
evidence; new executions of those axes are refused.

These changes add no new physics formula, likelihood, source verification or paid
call. Structural validity is separate from numerical support and physical/theory
consistency. Unsupported models retain an explicit uncomputed/pending outcome.
Personal-library indexing and bidirectional saved-study editing remain later milestones.
