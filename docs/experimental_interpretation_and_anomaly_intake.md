# Assisted experimental interpretation and confirmed anomaly intake

M36.5c and M37 extend the [private source library](experimental_source_ingestion.md).
They share source storage, immutable revisions, a durable budget and evidence
capture. They do not activate a new personal constraint profile or sign a source
verification. M36.5d–h and M38–M40 remain separate implementation increments.

## Researcher workflow

1. Open **Add a limit** (the experimental library), upload PDF/supplements, CSV/TSV, JSON/YAML,
   PNG/JPEG/WebP, or enter a written experimental description. Import is free.
2. Open the saved draft. **Start assisted interpretation** selects a provider/model,
   text/vision scope and one total session cap, behind explicit spending consent.
   Selected material is sent to the chosen provider. Keep keys in local `.env`,
   never in uploaded sources or descriptions. Anthropic supports this image workflow;
   OpenAI text interpretation is available only for source scopes without images.
3. The session shows selected source units, unread/unselected coverage, remaining
   funds and a conservative request bound. Preview the batch, then interpret it.
   Batches contain at most 12 units, 4 images and 45000 text characters. Large
   pages/tables/text remain indexed as chunks; unread content never disappears
   into an implied complete-paper interpretation. Figures/scans need vision.
4. Review the original text/pages/images beside the typed dossier and result
   descriptions. Every copied numerical value needs source/page or machine-row/
   column evidence. Literal copy checks catch absent numbers and invalid locators;
   they do **not** prove scientific entailment. Visual transcriptions still require
   checking against the original. Failed proposals remain in immutable extraction
   receipts and are marked unextracted in the dossier.
5. Refine with instructions, or edit and save the dossier as a new inactive revision.
   Interpretation disagreements remain conflicts until explicit refinement. Read
   batches require an explicit refinement before another paid interpretation, so a
   repeated click does not silently bill the same work. All revisions/receipts and
   the session cap survive process restarts. Retry/uncertain billing uses the existing
   reservation journal; an uncertain charge cannot fund another call.
6. Choose a result. ADROIT explains whether it describes actual events, histogram
   bins, a limit, response/background information or a likelihood. Inspect missing
   data, assumptions and the exact proposed numerical input. Plain descriptions
   require API interpretation before confirmation. Confirm understanding under your
   name and explicitly accept any investigator assumptions/adapter approximations.
   Edited dossiers cannot reuse the interpretation hash displayed before editing.
7. A supported confirmed event input offers **Continue to Track 2** and appears in
   its experiment selector. Run it against selected personal models and/or the
   existing candidate library. Saved reports are dated and explicitly exploratory,
   with source review pending. The underlying experimental revision stays inactive.

Confirmation means the researcher accepted this interpretation and its exploratory
use. It is not full expert source verification, an official likelihood validation,
or permission to use the 28 unverified packaged constraints. The existing curated
record gate remains in force; no blanket `--unverified` is needed for this handoff.

## Supported calculations and deliberate blockers

The first handoff reuses the fidelity-B historical unbinned nuclear-recoil adapter.
It requires actual event energies, explicit keVnr window and constant Gaussian
resolution, exposure **before** efficiency selection, efficiency in **true** recoil
energy, declared target and all four halo parameters. No default response, exposure,
halo or background is presented as a published value. Investigator assumptions can
be entered explicitly as assumed claims and must be accepted at confirmation.

Background treatment is explicitly fixed/profiled and flat/inline binned-shape.
Independent paired plus/minus errors are required for rate profiling; reported
uncertainties cannot silently be dropped. Correlated nuisance models and general
multidimensional response matrices require a dedicated adapter. Positive background
is required by this finite-significance handoff; zero-background observations stay
stored and blocked rather than receive an invented positive floor. Existing raw
legacy workflows keep their documented semantics.

Histogram bins remain bins, not individual events or repeated bin-centre events.
The binned adapter remains M36.5f. Limit curves never become event likelihoods;
native workspaces require supported loaders/validation. Digitised/estimated inputs
without the needed validated uncertainty treatment stay blocked. A blocked
interpretation can still be confirmed and saved for reference, without a fit link.
Model applicability/physical exclusion filtering is M38; this intake does not add
that filtering. Existing global significance is labelled an **unconstrained NR
reference**, not new bounded-physical-domain calibration.

## Deterministic conversions and provenance

The agent proposes raw source values and requested units. Code performs only named
fixed conversions: explicitly named tonne/kg days/years (year=365.25 days), nuclear
energy prefixes, percent fractions and pb/fb to cm². It refuses ambiguous electron-
to-nuclear energy conversions, coupling/benchmark transfers and generic CL scaling.
Exact original values/proposals remain in extraction receipts; converted claims
state their recipe. Source units are checked before conversion.

Source/scientific revision identities, confirmation, calculation start/completion
and report dates remain separate. Analyses pin exact `anomaly:CONFIRMATION_SHA256`
inputs. Editing produces new revisions/confirmations and never rewrites old studies.
Evidence bundles capture the confirmed numerical interpretation and source dossier,
while original PDFs/images are reference-only by default in this workflow. Their
local hashes/identities remain recorded; sharing copyrighted source material is a
separate choice. Selected signal-fit replay reconstructs the captured numerical
record and works without the local private library; source-file absence does not
become a claim of complete source re-verification.

## CLI

```bash
uv run adroit experiments import paper.pdf signal.csv --title 'My analysis' --out runs/source_draft
uv run adroit experiments start 'experimental:EXPERIMENT_ID@REVISION_ID' --budget 2
uv run adroit experiments preview SESSION_ID --batch 0
uv run adroit experiments extract SESSION_ID --batch 0 --budget 2 --out runs/interpretation
uv run adroit experiments extract SESSION_ID --batch 0 --budget 2 \
  --instruction 'Clarify the energy scale and preserve the stated backgrounds' --out runs/refinement
uv run adroit experiments interpretation 'experimental:EXPERIMENT_ID@NEW_REVISION_ID' --result RESULT_ID
uv run adroit experiments confirm 'experimental:EXPERIMENT_ID@NEW_REVISION_ID' --result RESULT_ID \
  --expected-hash INTERPRETATION_HASH --by 'Researcher name' --confirmed \
  --accept-assumption historical_unbinned_fidelity_B
uv run adroit signal --experiment 'anomaly:CONFIRMATION_SHA256' --toys 1000 --out runs/signal
```

Use IDs/hashes from the printed receipts and accept each additional displayed
assumption explicitly. Every paid extract command repeats the originally approved
`--budget`; it cannot reset the cap. `--text-only` at session creation omits ordinary
PDF images but cannot interpret scanned pages through OpenAI. `experiments revise`
supports deterministic typed corrections, retaining immutable source provenance.
The legacy `anomaly draft`/`record:<path>` interfaces remain available.
