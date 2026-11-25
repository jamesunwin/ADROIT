# Constraint discovery: finding, retrieving and reviewing the limits a model needs

After you define a model, ADROIT can work out which published limits bear on it, retrieve the ones the libraries do
not hold, and prepare them for you to verify and sign in your personal records. This is the user's guide; the design
and its record are in the constraint discovery build record of 2026-10-18.

## 1. Starting it

- **In the workbench:** a personal model's page has **Find relevant limits for this model**; the model-approval form
  has an optional **Then find relevant limits** that starts it as its own job once the model is saved. Either shows
  the scope, the language model and a cap you approve. A model is never sent anywhere without that consent.
- **At the command line:**

  ```bash
  uv run adroit constraints discover catalog:MODEL@REVISION --budget 2 --domain m_chi:10:500 --out runs/discovery
  uv run adroit constraints show SESSION          # stages, candidates, states and gaps ($0)
  uv run adroit constraints resume SESSION --budget 2   # continue after a stop or a failure
  ```

  The model is a personal revision (`catalog:…`) or a typed YAML file. `--domain` is the mass range you intend to scan;
  where it is given, existing limits are checked against it. `--max-sources` is the most papers retrieved (four by
  default; the results of one paper count once). `--vision` (in the workbench, **Read figures**) lets extraction read
  figures (§2, step 6).

**Cost.** One cap (at most $10) covers everything: the relevance request and every extraction step. Each request's
largest possible cost is shown before it is sent; a request the cap cannot cover is not sent, and the session stops
resumable (`adroit constraints raise-cap SESSION --budget … --confirmed` raises it, recorded). A rerun repeats no
finished stage and no batch already read, and never sends a relevance request whose answer was already received
(it is recovered from the session). An extraction answer is saved before it is published, so a rerun after a crash
publishes the saved answer, or reuses the revision already published with the same provenance, instead of asking
again. A retrieval that failed in transit (network, timeout, HTTP error) leaves
acquisition *incomplete*; `resume` retries it, then reads and packs what it retrieves. A refusal (another paper's
title or record, a table that does not parse) stays a named gap. A revision of the same paper is reused only
when it holds every requested table; otherwise a new revision holds the complete set. Reading figures adds page
images to some requests; their bound includes them.

**What leaves your machine.** Public arXiv queries carry physics terms only (no model file, name or path). The
provider receives the model's summary (its particles, couplings, Lorentz structures and engine), the titles and
identifiers of the records already held, and the abstracts; extraction sends the retrieved pages and tables. Only
arXiv and HEPData are contacted, over https, with sizes and times capped. Retrieved papers stay in your personal
library (`ADROIT_EXPERIMENTAL_LIBRARY_DIR`), never in the repository.

## 2. What it does

1. **Inventory** ($0): the standard records, experiment modules and signal searches, and your personal drafts,
   bindings and profiles.
2. **Search**: deterministic arXiv queries from the model's summary, kept in the session with their date. The shared
   literature cache is used unless you pass `--refresh`. For dark matter in an electroweak multiplet (an SU(2)
   doublet or larger) the queries lead with gamma-ray line searches, the multiplet by name (higgsino, wino, minimal
   dark matter, or "electroweak multiplet"), disappearing-track searches and gamma rays from the inner Galaxy.
3. **Relevance** (paid, one request): the language model proposes the published results that bear on the model, each
   cited by arXiv identifier or DOI; every reference is checked against arXiv or Crossref and an unconfirmed one is
   dropped (listed as a gap). It is asked not to propose a result superseded over its whole mass range by a held
   result or another of its proposals; one it lists anyway names the newer result (`superseded_by`). Where it
   proposes a result that ADROIT already holds, it names the held entry (`held_as`) and states the result's identity:
   the bounded quantity, observed or expected, the confidence level, and any channel, dataset, panel or benchmark.
4. **Categories** ($0, by code): each result is matched to what is held, by its source identity:

   | stage you see | meaning |
   |---|---|
   | existing result | a standard record or module, or a bound personal limit, is shown to be this result (below) |
   | needs your review | a personal draft of it exists, or one was just drafted |
   | outside this model's domain | an existing limit does not cover your domain, or it cannot apply (with the reason) |
   | unclear whether it applies | absent, and its relevance or numbers are uncertain; if ADROIT could calculate it, the page offers to take it in ("It applies: fetch and draft its record", recorded as your decision), and it is then fetched and drafted at the next run |
   | source needed | absent, an existing adapter could compute it, and its paper is still to be fetched (resume the survey) |
   | draft ready / needs your review | absent, an existing adapter could compute it, and it was retrieved and drafted |
   | not currently supported | relevant, but ADROIT does not yet calculate its observable for this model (the prediction or recast it needs is named): a record of it could not be used, so it is not fetched; an analysis proceeds without it, and with the survey's assessment pinned it keeps allowed points pending |
   | needs calculation/validation | a reviewed draft awaits validation and binding |
   | ready to use | reviewed, validated and bound |
   | superseded by a newer result | the newer result it names is held, or proposed in the same session, and covers its declared mass range |

   **Identity, not the paper.** A held entry of the same paper is the proposed result only when the relevance step
   named it (`held_as`) and the two agree, each stated: the same constraint class and kind of quantity, observed or
   expected, the same confidence level (an experiment module computes at any), and every channel, dataset or panel
   the proposal names (a combination never matches a single channel or dataset); a benchmark-specific record counts
   only for its own benchmark. Anything unstated or different leaves the result unresolved, and a result that needs a
   calculation is never covered by a held entry. A personal limit counts only when it is bound for the same adapter
   and its stated identity agrees; a binding of another result of the same paper never resolves it.

   A superseded result is not retrieved, but the relevance step's mark does not show that the newer result is at
   least as strong over the older one's whole domain. Until you confirm it (§4, `--superseded-by`) it stays a
   requirement in the coverage pin, linked to the newer result for your review. Once confirmed, it needs nothing when
   the newer result is a held standard record; otherwise only selecting the newer result's bound limit for the run
   resolves it. A mark code rejects (an identifier neither held nor proposed, another constraint class, a bounded
   quantity of another kind or not stated, or a newer result declaring less of the mass range) is ignored and noted
   in the result's "missing" column.

5. **Retrieval** (network): for a result an existing adapter supports, the arXiv paper at its exact version and
   HEPData tables, only from a HEPData record that names the same paper: the tables the proposal names, or, when it
   names none, at most three chosen by code from the names and descriptions in the paper's own record (found by its
   arXiv identifier) for the adapter's quantity. A named table that does not exist is never replaced by another. The
   tables are taken in HEPData's submission format (YAML) and refused unless they parse as tables. Imported as a
   draft revision with its retrieval provenance and hashes; no record, or no fitting table, is a named gap. Results
   of the same paper are retrieved together: one paper, the tables each of them needs, one revision.
6. **Extraction** (paid): the experimental library's assisted extraction reads the draft and transcribes the limit
   and independent reference values, each checked against its cited cell, page or excerpt. Each PDF is read up to
   the page where its reference list begins, plus any later page with an appendix or a table; the pages left out are
   listed in the review packet (`not_read`). A PDF without a references heading is read whole. Results of the same
   paper are extracted together: one session reads its pages once and asks for each result (`extracted_with` in the
   packet). With `--vision`, a spin-independent result for which no data table was retrieved also has its figure
   pages sent as images: the pages read whose text holds a figure caption and an SI cross-section limit, at most
   three per paper (`viewed_as_images` in the packet). A curve read from a figure is marked `figure_digitised`, with
   the reading precision on each axis and the figure's calibration, and you check it against the original page. Its
   validation anchors may be quoted from the paper's own text (each mass and limit in one exact quotation with its
   page; [the owner's rule](private_limit_review_and_track1.md)); a paper printing fewer than three goes through the
   manual figure verification (`verify-figure`). Reading figures needs an Anthropic model.
7. **Review packets** ($0): per result, the source identity, the extracted claims with their locators and problems,
   whether the adapter's contract reads, what is missing and the next commands.

## 3. Your steps (unchanged)

Discovery signs nothing. A drafted limit becomes usable only through the existing steps, each on the experimental
library's pages or at the command line:

```bash
uv run adroit experiments review DRAFT --result RESULT --out runs/review     # the packet beside the source
uv run adroit experiments verify-source DRAFT --result RESULT --expected-hash … --by "Your Name" --confirmed --checked …
uv run adroit experiments validate-limit DRAFT --result RESULT --tolerance 0.02 --expected-hash …
# or, for a curve digitised from a figure with one or two printed anchors:
uv run adroit experiments verify-figure DRAFT --result RESULT --tolerance 0.1 --expected-hash … --by "Your Name" --from LOW --to HIGH --confirmed --checked …
uv run adroit experiments bind-limit DRAFT --result RESULT --review … --validation …
uv run adroit experiments profile-review --limit private-limit:…   # then profile-create, if you want a profile
```

**Which limits can be computed.** Only results that fit an existing adapter: a spin-independent isoscalar
σ_nucleon(m) curve (elastic, contact O1 with c_p = c_n) and an upper bound on BR(h → invisible) for the Higgs-portal
classes. Signing a source review does not turn a 90% limit into a 95% one, a curve into a likelihood, or supply a
missing recast; other relevant results are kept, documented and named as not currently supported.

**In the workbench** (the survey's page, from the model's page or the run's "Review the discovery session"; the
owner's JU1, 2026-11-16): each result found is listed with what it means for your analysis and what to do next, in
plain words. Below the list:
- *Your actions*: open a drafted record to review and verify it; for an unclear result ADROIT could calculate, "It
  applies: fetch and draft its record" (recorded as your decision, with your name); for any unresolved result, record
  that it does not apply, or leave it out of this study, with your reason.
- *Fetch and draft what remains*: resume the survey within its approved cap; the papers are fetched (arXiv, HEPData)
  and their records drafted by the language model (paid).
- *Proceed with your analysis*: "Constrain this model" opens Constrain a model on the model, with the survey's
  verified (bound) limits selected and its assessment pinned (§4): a limit found but unresolved keeps allowed points
  pending and never excludes. You can untick the pin there.

## 4. Using the result in an analysis

```bash
uv run adroit constraints decide SESSION CANDIDATE --inapplicable "the mediator is heavier than the search reach" --by "Your Name"
uv run adroit constraints decide SESSION CANDIDATE --omit "outside this study" --by "Your Name"
uv run adroit constraints decide SESSION CANDIDATE --superseded-by NEWER --reason "stronger at every mass" --by "Your Name"
uv run adroit constraints coverage SESSION     # prints discovery:SESSION@HASH
uv run adroit track1 model.yaml --private-limit private-limit:… --discovery discovery:SESSION@HASH --out runs/…
```

`coverage` freezes the assessment, with its gaps, the surveyed mass range and the state of each stage. A session
whose stages did not all finish is refused; `coverage SESSION --incomplete` freezes it anyway, and then every allowed
point of a run that pins it stays pending. A run that pins it (`--discovery`, Track 1 or Explain a signal) checks that
it belongs to the same model, embeds it in the result, and applies it to every evaluated point before the verdict and
its band-wide certificate: an allowed point stays pending while a relevant constraint is unresolved for that run
("discovery: …"): not reviewed, not bound and selected (also when a bound personal limit already held it: select it
for the run), needing a calculation, of uncertain relevance, or omitted by you; and a point outside the surveyed range
is pending. A standard record from the same paper counts only when it is shown to be the same result (same kind of
constraint, the same kind of quantity, observed or expected and confidence level stated and agreeing, and a
general rather than benchmark-specific record; §2, step 4). A bound personal limit resolves a requirement only over
the mass range it declares: your range is cut at each binding's ends, and a piece that no selected binding covers
(beyond them, or in a gap between them) stays pending. `--domain` takes the dark-matter mass (`m_chi:LOW:HIGH`), the
mediator mass (`m_med:LOW:HIGH`) or both; a point outside either surveyed range is pending. An excluded point stays
excluded; nothing is excluded by discovery. The point table, the plane, the
inspector and `points.csv` show the same pending points.
Recording a result as inapplicable removes it, with your reason; an omission stays listed as an omission. A run
without `--discovery`, and every earlier result, is unchanged.

Discovery is a dated, bounded survey: a limit it did not find is not shown to be absent. Changing the model needs a
new assessment; your source reviews stay valid, since they are bound to the source, not to the model.
