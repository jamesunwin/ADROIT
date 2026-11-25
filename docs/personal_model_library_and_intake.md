# Personal model revisions and reviewed intake (M35–M36)

The **Model library** workbench page holds private, immutable model revisions.
Storage defaults to the gitignored `projects/model_library/` directory. Set
`ADROIT_MODEL_LIBRARY_DIR` to use another personal location. ADROIT does not publish
this catalog or add it to the shared interaction library. Your filesystem's backup
or synchronisation settings still apply.

A model has a stable model ID and immutable revision IDs. Each revision contains
its complete canonical ModelSpec, approval identity, parent revision, source
assets/hashes, TeX view, provenance and an applicability snapshot. Editing creates
a new revision; selecting an older revision never silently selects the newest.
Integrity checks refuse missing/modified model files or source assets.

The library offers **Review in Track 1**, **Compare in Track 2**, and **Refine as a
new revision**. Both track wizards also have catalog pickers. Same-named revisions
remain distinct Track 2 candidates. Saved analyses record pinned model references
and source identities; evidence exports include the selected model/source artifacts.
Numerical replay uses the captured model, so a missing local catalog does not erase
the archived calculation. Approving a model does not verify any experimental record.

## Intake and refinement

Open **Create or refine a model**. Choose a plain idea, TeX, field-content YAML,
typed model YAML, or a PNG/JPEG/WebP screenshot. Text/model files may also be uploaded.
Pure typed/field intake is deterministic and free. TeX, screenshots and clarification
use an opt-in model call behind one session budget confirmation.

Review the original source image/text, transcription, assumptions/ambiguities,
canonical model YAML, numerical support and editable TeX. Plain ideas yield candidate
field contents and deterministically generated Lagrangians. Field-only TeX/images
are interpreted as field content and use that same generator. A supplied Lagrangian
is retained; mixed field/interaction descriptions are flagged rather than discarding
coefficients. Missing numerical values remain unspecified.

- **Interpret edited TeX** parses the edited source as a new immutable draft.
- **Refine this candidate** sends the prior canonical model and clarification
  instructions, then shows the new interpretation and differences.
- **Apply typed corrections** makes a deterministic new draft and updates its TeX
  view, without a paid call. Apply a changed YAML model before further TeX refinement.
- **Save reviewed revision** requires explicit review and exact matching of the
  displayed draft, model and TeX. Edited/unchecked material cannot use an old approval.

The TeX view is generated deterministically from typed terms, arithmetic coefficients,
parameters and fields. Unsupported Lorentz structures are shown as explicitly named
operators; it is not a universal inverse TeX parser or a new amplitude derivation.
General model parsing/refinement uses the LLM, followed by canonical review. Structural
validity is separate from numerical support, physical consistency and constraint scope.

Conceptual/unsupported models can be saved for reference with their limitations.
Catalog calculations require declared numerical parameters and a supported engine.
Do not mistake a successful interpretation for complete backend coverage. Unspecified
parameters are not filled with invented values; refine or explicitly enter them before
using that revision in calculations. Existing direct raw-YAML benchmark workflows
retain their documented behaviour.

## Budget and privacy

The intake session's total budget is fixed at creation, persists across process
restarts and covers all subsequent interpretation/refinement calls. Paid commands
repeat that original `--budget`; they do not reset remaining funds. Every request
reserves a conservative bound and settles known provider usage in `paid.jsonl`.
Uncertain billing remains committed and cannot be silently released for another call.
An exhausted budget preserves drafts and receipts; start another explicitly approved
session if additional paid work is needed.

Screenshot interpretation currently uses Anthropic inline vision. The budget adapter
verifies bytes/type/size and conservatively reserves 8192 input tokens per image,
above the documented 4784-token maximum plus framing allowance. URL/file-ID and
unsupported provider image inputs are refused before dispatch. See
[Anthropic's vision documentation](https://platform.claude.com/docs/en/build-with-claude/vision)
(checked 9 October 2026). OpenAI text/TeX interpretation can use the existing text
adapter; its screenshot workflow remains unsupported.

Selected source material is sent to the configured provider only for an opted-in paid
interpretation. **Keep API keys only in your local `.env`; never paste keys into model
text, TeX, screenshots or uploads.** Credentials, directories and unsupported source
file types are refused as catalog assets. Sources are stored locally; exporting a
calculation's evidence also exports its explicitly selected model sources.

## CLI

```bash
uv run adroit models import my_model.yaml --source original.tex
uv run adroit models list --query mediator
uv run adroit models show 'catalog:MODEL_ID@REVISION_ID'
uv run adroit track1 'catalog:MODEL_ID@REVISION_ID' --no-literature --out runs/my_model
uv run adroit signal --experiment 'CDMS II Si (2013)' \
  --model 'catalog:MODEL_ID@REVISION_ID' --masses 8.6,10 --toys 1000 --out runs/comparison

uv run adroit models start --budget 1 --model claude-opus-5-5
uv run adroit models step SESSION_ID --kind image --source model.png --budget 1
uv run adroit models step SESSION_ID --kind tex --source corrected.tex \
  --parent-step STEP_ID --candidate 0 --budget 1
uv run adroit models draft SESSION_ID STEP_ID
uv run adroit models approve SESSION_ID STEP_ID --candidate 0 \
  --expected-hash REVIEWED_MODEL_SHA256 --confirmed
```

The example IDs/hashes come from the printed results. Approval is an explicit user
decision, not a paid agent's signature. `models export` writes a portable typed model
without overwriting an existing file; it records origin metadata. The catalog sources
themselves remain in the library and in evidence bundles that include them.

These milestones do not add anomaly-figure ingestion, full physical candidate
filtering, general saved-analysis reanalysis, or calibrated inference coverage.
Those remain M37–M40 and the deferred M29–M31 proposals.
