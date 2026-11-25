# G11 — The language-model layer II: benchmarks and gaps (2026-10-15; paid gate)

Milestone G11 of [`freeze_out_build.md`](freeze_out_build.md). An agent finds a paper's published benchmarks for a
model, as the zoo's survey did by hand, and each quote is checked deterministically against the paper's text. Where
the core lacks a piece, a second agent drafts it with its tests. The draft stays quarantined until a person reviews
it.

## What was built

- **The benchmark agent** (`adroit/agents/benchmarks.py`). It reads the paper page by page (pdftotext's pages, the
  first 110,000 characters) and returns the targets ADROIT can compare: Ωh² at a stated point, a thermal mass, a
  thermal splitting, σ_SI at a stated point. Each target has its point, page, location and verbatim quote.
- **The check** (`quote_check`). Every number printed in the quote must appear on the stated page or a neighbour
  (a table can straddle pdftotext's page break). The target's value must be one of the quote's numbers. The check
  reads the paper's forms:
  - scientific notation, including a mantissa and exponent split by the text extraction ("8.45 10−46", the × lost);
  - percentages;
  - ranges.

  A target that fails is dropped, with the reason. Only what passes is compared, in ADROIT's units
  (`in_adroit_units`).
- **Gap drafting** (`adroit/agents/gap_drafter.py`). A named gap gives the module, its pytest tests and `DRAFT.md`
  (the agent, the date, the gap, the references, the open questions, and the words "provisional: not reviewed").
  They are written to `drafts/quarantine/<name>/`, which is git-ignored and outside the package. A test checks that
  no module of `adroit` imports from `drafts` or names the quarantine. A second test checks that a full evaluation
  with a draft present imports nothing from it. `review` runs a draft's own tests in a separate process, for a
  person.
- **The gate's script** (`scripts/g11_benchmark_gate.py`). It has three modes:
  - `--dry-run` ($0);
  - the paid run;
  - `--recheck` ($0): the stored targets through today's check, and the gate recomputed.

## The gate run (Claude Opus 5.5, $2.24)

The agent read each development-half entry's source papers, each target in its own paper: 12 entries, 26 targets.

**As run: 18 of 26 recovered** (the same quantity, within 2% in ADROIT's units). **One quote failed the check**:
"the scattering cross-section on a proton amounts to 8.45 10−46 cm2" (Giacchino et al.). The number is printed on
that page. pdftotext dropped the "×", and the check did not then read a mantissa and an exponent without it. The
check was fixed after the run. With `--recheck`, all 58 extracted targets pass and none fails.

**With `--recheck` after two fixes to the comparison, both made after the run: 19 of 26 recovered, no quote
failing.** The second fix is the unit "%". The agent read Yaguna's "Mχ2/Mχ1 is respectively of order 6%" as 6
with the unit "%", correctly. `in_adroit_units` had no "%", so it compared 6 with the zoo's 0.06. It now reads
"%" as 0.01.

**Re-checked at G12 with the audit's corrected check (AG-2, AG-3):** the quote must now be in the paper verbatim, or
as a table row with its numbers in order, and the parameter point's numbers must be printed in the paper; an
unknown unit is refused. **19 of 26 recovered; one quote fails**: Yaguna's "we find that M_χ1 ≲ 733 GeV" is on the cited page 6, but its
formula is a display fraction that the PDF's text splits across lines, and the agent wrote it inline as
"(Mχ2/1.1 TeV)^2", so the quote is not verbatim (733 GeV itself is printed there; `docs/g11/benchmark_results.json`).
**G11's gate is not met by that one quote.** It is recorded as a finding; the check is not widened after the
result.

**Not recovered** (as rechecked):

| entry | zoo target | the agent's |
|---|---|---|
| Dedes & Karamitros | Ωh² = 0.12 at two benchmark points | two thermal masses (91 and 110 GeV): other quantities, both correct as quoted |
| Feng et al., complex scalar | Ωh² = 0.1199 at two points | none |
| Harz & Petraki | thermal masses 1865 and 1330 GeV | only the 3300 GeV one |
| Choubey et al. | σ_SI = 8.22 × 10⁻⁴⁸ cm² (eq. (23), decision D12) | the table's 2.1 × 10⁻¹² pb in the same row as Ωh² = 0.1207: the value D12 found to be a quarter of eq. (23)'s |

**Gate:**
- **recovered:** 18 of 26 as run, 19 after the unit fix; at least half (met);
- **no failing quote:** one as run, from the check's own gap; none after the fix (met after the fix, which came
  after the run);
- **drafted code reaches no verdict:** tested (`tests/agents/test_gap_drafter.py`; met).

## A live draft

One paid draft was tried. The gap: the electroweak Sudakov factor of the wino's line, the gap G8 names. It
**produced nothing**: both requests (the first and the client's retry) spent all 16,000 output tokens on Opus 5.5's
reasoning and returned no text. Cost: $0.65. No folder was written.

Two consequences:
- **The client no longer retries a reply that has no answer text after reaching max_tokens**
  (`LLMClient.complete_structured`). The same request would spend its budget alike and be billed again. It now
  stops with that reason.
- **The drafter now asks for 32,000 output tokens** (`gap_drafter.DRAFT_TOKENS`), and the client's request timeout
  can be set (`LLMClient(timeout_s=…)`; the default 180 s would cut such a reply off after it was billed).

**A test on a gap with a known answer** (the owner's question 7, 2026-10-15; $0.18). The gap was the one-loop mass
splitting M_Q − M_0 of a pure SU(2) n-plet with hypercharge Y, with a stated function signature. The draft's own 11
tests pass (`review`), and in a separate process its function gives ADROIT's `generic_today.splitting` to 10⁻¹⁵ at
six (n, Y, Q). The draft stays in `drafts/quarantine/ew_mass_splitting/`. So the drafter works end to end. The
Sudakov factor was not drafted again: for the wino and higgsino, G8 now uses DMγSpec instead.

## Limits

- The agent reads the first 110,000 characters of a paper, about 40 pages. A benchmark printed later, in a long
  appendix, is not seen.
- The comparison needs the same quantity. An agent that quotes a thermal mass where the zoo quotes Ωh² at that mass
  is correct and not counted.
- A draft is never run by ADROIT. Promoting one is a person's act: read it, run `review`, move it into the package
  with its tests.

Tests: `tests/agents/test_benchmarks.py`, `tests/agents/test_gap_drafter.py`.

## The rerun (2026-10-20; the batch plan's §8; declared before the run)

**The fix.** The one failing quote (Yaguna's "M_χ1 ≲ 733 GeV") was the agent's re-typesetting of a display formula the
text extraction splits across lines. The agent is now told to copy its quote character for character from the page
text it is given, never rewriting a formula, fraction, power or symbol in its own notation, and to quote a split
formula as split or quote the words and numbers around it (`agents.benchmarks.SYSTEM`). The check is unchanged.

**The gate, declared before the run, as G11's own:** on the development half (12 entries, 26 targets), at least half
the targets recovered (the same quantity within 2% in ADROIT's units), and no extracted quote failing the check. A
miss is recorded, not tuned away. The model and the budget as before: Claude Opus 5.5, a cap of $2.40 (the owner's
approval, 2026-10-19).

**The result** (`docs/g11/benchmark_results_2026-10-20.json`; $1.77): **13 of 26 recovered, no quote failing: the gate
is met, at its threshold.** The `--recheck` of the stored targets ($0) agrees.

- **Yaguna** now recovers both targets. The quote that failed before is copied as the page prints it.
- **Two entries were not run.** These are Athron et al.'s vector Higgs portal (2 targets) and Das et al.'s scalar
  mediator (4 targets). Before each request, the budget reserves its worst case (the request's output tokens at the
  output price, about $1.13). After ten entries $1.63 was committed of the $2.40 cap, so both were refused before
  dispatch: nothing was sent and nothing billed. Giacchino et al., the last entry, needed less and ran. In the first
  run these two cost $0.20 and $0.29 and recovered all six of their targets. That result is not counted here.
- **On the ten entries run both times:** 12 of 20 targets recovered then, 13 of 20 now (Yaguna's second). The other
  nine recover the same targets as before. Each entry's cost is within a cent of the first run's.
- **Not recovered**, as before: Dedes & Karamitros (two thermal masses quoted where the zoo has Ωh²), Feng et al.
  (none), Harz & Petraki (one of three), Choubey et al. (the table's σ_SI; D12).

**Gate:** at least half recovered, 13 of 26 (met, at the threshold, with six targets not attempted); no failing quote
(met). Running the two entries not reached would cost about $0.50, judged by the first run. Its cap must exceed the
$1.13 reservation. That is the owner's decision; it is not done here.

**The supplementary completion run** (the owner's approval, 2026-10-20; `docs/g11/benchmark_results_2026-10-20_completion.json`;
$0.51). The rerun's setup unchanged (the gate script's own `run`, the same model, prompt, check and output limit),
on the two entries its reservation had refused, with a cap of $2.30 so that both requests' worst cases fit:
- Athron et al.'s vector Higgs portal: 2 of 2 recovered ($0.21);
- Das et al.'s scalar mediator: 4 of 4 recovered ($0.30);
- no quote failing; the `--recheck` ($0) agrees.

**The rerun, completed over two passes:**
- 19 of 26 targets recovered, every one of the 12 entries attempted, no quote failing;
- 13 of 26 in the first pass, the six more in this one;
- $2.28 in all ($1.77 and $0.51).

The two entries were run in a separate pass, not as part of the first, and are reported as such. The not recovered
are as before.
