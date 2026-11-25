# Private experimental drafts and source ingestion — M36.5a–b

The **Add a limit** workbench page (the experimental library) imports a paper PDF, supplementary
PDF, CSV/TSV, JSON/YAML, UTF-8 text or PNG/JPEG/WebP. Import is deterministic and
costs $0 in API fees. It saves an immutable, date-stamped private draft, not a
scientifically approved limit or signal analysis. M36.5c adds assisted scientific
extraction; d adds source review/adapter validation; e–g connect approved inputs
to calculations and personal activation profiles.

Storage defaults to gitignored `projects/experimental_library/`. Override it with
`ADROIT_EXPERIMENTAL_LIBRARY_DIR`. Originals and derived previews/ingestion data
are content-hashed. Revisions use `experimental:EXPERIMENT_ID@REVISION_ID`; edits
create a new revision under the same experiment ID. There is no implicit latest
revision, shared upload, packaged-record edit or automatic activation. Your own
filesystem backup/synchronisation settings still apply.

The dossier has typed claims for detector/selection/response, background/control
regions/uncertainties, observations, limits/statistics/benchmarks, overlap and
missing public inputs. Claims begin **unextracted**, including known zeros that
appear in a file: import alone does not interpret a column. Manually supplied
claims distinguish sourced/converted/digitised values, assumptions, conflicts,
not reported and not applicable. File/page/row references are checked structurally;
matching a text passage does not verify its scientific meaning. Capability
contracts declare future adapter requirements and remain unavailable or awaiting
validation. Draft source review, numerical validation and activation are separate
states; all are unapproved/inactive in this increment.

## PDF and data coverage

Each physical PDF page retains its text, dimensions, rotation and text-fragment
positions in PDF points. Physical page numbering starts at one; printed page,
table and figure labels are not guessed. Complex transforms can make fragment
positions unreliable, so use the original rendered page for review. Scanned or
low-text pages explicitly need visual interpretation; extraction failures retain
their page entry. Previews are whole-page source images from Poppler, not inferred
figure values. An uploaded figure can also be retained directly.

By default page 1 is previewed; select up to 12 pages with `--preview-pages 1,3,5`
(an empty value disables previews). All pages are text-inventoried for accepted
PDFs of up to 120 pages. PDFs above this cap or encrypted/malformed documents are
refused rather than silently truncated. Import selected sections as separate files
for larger documents. Preview failure or absent Poppler leaves text available and
records the missing visual backend. Install Poppler to use previews (`brew install
poppler` on macOS); no installation is performed automatically.

The parser runs in a disposable process with CPU/output/wall-time limits and, on
Linux, an address-space limit. macOS uses CPU/time/output and input/content caps;
it does not provide a hard address-space limit here. Files are capped at 25 MB,
PDF page size at 14400 points, extracted text at 4 million characters, and
rendering at 1600 pixels on the longest edge. No embedded action, uploaded code,
network fetch, API interpretation or local OCR is executed in a–b. Visual/OCR
semantic extraction and its paid budget gate belong to c.

CSV/TSV import retains exact cells, headers and source line numbers. It refuses
inconsistent rows, duplicate/empty headers and nonfinite numerical tokens; it
does not sort, deduplicate, round, infer units or reinterpret bins as events.
JSON/YAML uses safe parsing, JSON-compatible finite values and bounded nesting.
Original files remain the authority for subsequent review. Unit conversions,
table identification and figure digitisation are subsequent explicit operations.

[pypdf's extraction documentation](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)
explains why text extraction cannot read image-only scans and why complex PDF
coordinates/layout require visual checks (consulted 9 October 2026).

## CLI

```bash
uv run adroit experiments import paper.pdf supplement.pdf limits.csv \
  --title 'My experiment, run 2' --preview-pages 1,2 --out runs/my_experimental_draft
uv run adroit experiments list --query 'run 2'
uv run adroit experiments show 'experimental:EXPERIMENT_ID@REVISION_ID'
uv run adroit experiments source 'experimental:EXPERIMENT_ID@REVISION_ID' --index 0
uv run adroit experiments report 'experimental:EXPERIMENT_ID@REVISION_ID'
uv run adroit experiments revise 'experimental:EXPERIMENT_ID@REVISION_ID' \
  --dossier corrected_dossier.json
uv run adroit experiments import erratum.pdf --title 'Corrected result' \
  --parent 'experimental:EXPERIMENT_ID@REVISION_ID'
```

The import output supplies the real IDs. `--dossier` accepts an explicit typed
dossier with import; `revise` edits a saved dossier while retaining its originals.
Uploaded amendments supplement a parent's retained source evidence; they do not
automatically supersede a numerical limit. Review/replacement remains d/g.
The workbench shows source text/previews, completeness and editable dossier JSON,
and creates linked inactive revisions when edits are saved.

## Date-stamped analyses and reports

Revision creation, source publication, calculation start/completion and report
generation are different dates. New evidence captured through the run workflow
stores explicit UTC calculation timestamps and the exact calculation input identity.
Main saved reports include these dates and pinned model revisions; the model
library links its new dated analyses. Report generation is separately dated, so
opening or rendering a historical result does not make its physics current.
Complete Track 1/native-fit resume retains the original recorded calculation
times. Legacy results without timestamps stay unknown; a saved date-only result
is labelled as date-only. Historical result files/archives are not retroactively
rewritten. Standalone report renderers without captured calculation evidence show
an explicit unknown calculation date rather than inventing one.

The experimental profile and active-revision dates will be threaded through
calculations in M36.5g. A date describes the inputs actually used, not a guarantee
that all publications available worldwide on that date were included. Later data
can motivate a new analysis without changing the meaning of an old conclusion.
