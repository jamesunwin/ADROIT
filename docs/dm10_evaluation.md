# DM10: the evaluation suite and the baselines

**Done 2026-10-02. The gate passed: 5 of 5 of the owner's rules met on the
held-out half (section 6).**

Started 2026-10-01. Cost, all on the direct-prompting baseline's development
half (section 3), counted by the budget wrapper:
- claude-opus-5-5: $2.52 (78 cases; the call that crossed the $2.50 cap is counted);
- gpt-5.6-sol: $3.02 (44 cases);
- plus whatever OpenAI billed for dropped requests, which the wrapper cannot
  see.

The owner approved $5 and then a further $5 for these. The gate's held-out
baseline (approved $10) cost $6.99: claude-opus-5-5 $2.96, gpt-5.6-sol $4.03.
The gate's rules were chosen by the owner (section 6).

The plan (build plan, DM10) asks for four suites, two halves of each (the
owner keeps the held-out half), two baselines, a comparison with published
analyses, and a gate made of pre-registered rules the owner chooses. Each is
below. Nothing in DM10 changes what the system computes. It adds the means of
measuring it.

## 1. The harness

`adroit/evaluation/core.py`; the command line is `adroit eval SUITE`.
- **A case** is one test with its inputs. **A suite** lists its cases, runs
  one, and summarises a list of results.
- **The halves.** A case's half is fixed by a hash of a salt, the suite and
  the case's id (`half_of`). It is fixed before any result is seen, it does
  not depend on which other cases exist, and it cannot be moved afterwards.
  Splits (development/held-out): limits 80/81, LZ's tables 308/304, injection 416/384,
  historical 1/1, direct prompting 101/99.
- **The held-out half** is run only to confirm a change, with a stated reason
  (`adroit eval SUITE --held-out --reason "…"`). Each such run is appended to
  `docs/dm10/held_out_ledger.jsonl`, so how often the half has been looked at
  is on record. The gate's rules are applied to it.
- **The results store.** Every run is one line of `<store>/<suite>.jsonl`:
  commit, date, half, each case's result, summary. A held-out run always goes
  to the tracked store `docs/dm10/results/`, which the gate reads. A
  development run goes to `runs/eval/` unless `--out` names a store; give
  `--out docs/dm10/results` to add it to the tracked record (R0, 2026-10-10).
- **What is fresh.** DM3 and DM6 already computed every case of the limits and
  LZ-tables suites, so their held-out halves are not unseen data. The
  discipline starts now: later changes are confirmed on them. The injection
  draws, the historical case in the held-out half and the baselines are
  fresh.

## 2. The suites

### 2.1 Limit reproduction (`evaluation/limits.py`)

A case is one mass of one published curve, judged by DM3's rule: the
reproduced limit is within a factor 1.3 of the published one, or reaches it
within a 3% shift in mass where the curve is steeper than 8. The modules and
their trial masses are DM3's:
- CRESST-III with the owner's reading (cut survival in true energy);
- CDMSlite by its official procedure;
- PICO-60, DEAP-3600;
- the three xenon searches through DIAMX.

Each run computes only its own half's masses. DM3's gate, a decade of
contiguous validated range, needs whole curves and stays in `docs/dm3`. A case
is also marked if it lies inside its module's validated range. DM3 drew those
ranges from the same comparison, so inside them this suite is a regression
test.

**The development half** (80 masses, 42 minutes, mostly DIAMX):

| curve | pass | | curve | pass |
|---|---|---|---|---|
| CRESST-III SI | 11/13 | | DEAP-3600 SI | 8/9 |
| CRESST-III SD-n | 7/8 | | LZ WS2022+WS2024 SI | 4/6 |
| CDMSlite SI | 11/11 | | XENONnT SR0+SR1 SI | 3/4 |
| CDMSlite SD-p | 11/11 | | PandaX-4T Run0+Run1 SI | 3/6 |
| CDMSlite SD-n | 11/11 | | PICO-60 SD-p | 1/1 |

- **Inside the validated ranges:** 70 of 70 pass.
- **Overall:** 70 of 80 (87.5%). All ten failures lie outside the validated
  ranges:
  - CRESST-III at 0.16–0.27 GeV, below its range (0.35 GeV and up);
  - DEAP-3600 at 30 GeV, at its threshold;
  - PandaX-4T at 5, 12 and 63 GeV, below its range (147 GeV and up);
  - LZ at 201 and 2084 GeV and XENONnT at 17 GeV, at ×1.32–1.38, just past
    the rule.

### 2.2 LZ's tables (`evaluation/lz_tables.py`)

The 612 local significances of arXiv:2609.02823 (Tables S7, S8), each
recomputed with the fidelity-B LZ module under LZ's conventions and its own
L6 and L9. A case passes within 0.3σ, DM6's tolerance. DM6 found 94.6% of all
612 within it.

**The development half:** 290 of 308 (94.2%) within 0.3σ, in 1.7 minutes. The
18 outside are DM6's known ones:
- L6v at 100–1000 GeV, where LZ's own L6 still differs;
- L13 at 100–400 GeV;
- O1 at the kinematic edges (δ = 50 keV at 1–4 TeV, where LZ gives 0.0;
  δ = 100 and 300 keV at 0.4 and 4 TeV);
- three single entries (L2v at 200 GeV, L4s at 4 TeV, L12v at 200 GeV).

### 2.3 Injection and recovery against the number of events (`evaluation/injection.py`)

DM6's test (20 events, LZ's window) made general in the number of events and
the target:
- **Targets.**
  - Xenon: LZ's extended window and its 612 models.
  - CaWO₄: CRESST-III, 1–20 GeV.
  - Germanium: CDMSlite, 3–15 GeV.
  - Argon: DEAP-3600, 50–3000 GeV.
  The non-xenon targets use O1 and O3–O15 in both isospins.
- **Events.** N = 3, 5, 10, 20, 50 signal events drawn from one candidate's
  efficiency-weighted spectrum, plus Poisson background: LZ's own b* for
  xenon, one expected event over the window elsewhere. Forty cases for each
  target and N. Each case's random state comes from its id.
- **Recovery** has three readings, all reported:
  - *pairwise*, DM6's pre-declared rule: the best fit is the injected
    candidate, or one that N events cannot tell from it at 2σ
    (N₂σ = 4/J > N);
  - *class*, the reading the owner accepted for DM6: the best fit is in the
    injected candidate's single-linkage class at N;
  - *exact*: the best fit is the injected candidate itself.
- **The set** the system reports is the tournament's: candidates within
  ΔAIC ≤ 2 of the best (with one parameter each, Δ ln L ≤ 1). The suite
  reports how often it holds the injected candidate, and its mean size.

**The development half** (416 cases; commit 92b1c10 with DM10's changes;
`docs/dm10/results/injection.jsonl`). Each cell gives pairwise; class;
exact; the ΔAIC set's coverage, mean size; cases:

| target | N = 3 | N = 5 | N = 10 | N = 20 | N = 50 |
|---|---|---|---|---|---|
| Xe (612 candidates) | .59; 1.00; .06; .71, 60; 17 | .50; .95; .09; .50, 52; 22 | .61; .89; .11; .44, 25; 18 | .57; .96; .13; .65, 21; 23 | .60; .85; .05; .55, 11; 20 |
| CaWO₄ (196) | .68; 1.00; .05; .68, 43; 22 | .75; 1.00; .04; .71, 23; 24 | .71; 1.00; .10; .81, 15; 21 | .70; .81; .07; .74, 12; 27 | .86; .91; .23; .95, 7; 22 |
| Ge (140) | .73; .91; .09; .73, 21; 11 | .55; .65; .00; .80, 11; 20 | .86; .95; .09; .77, 8; 22 | .73; .77; .09; .77, 7; 22 | .93; 1.00; .20; .93, 5; 15 |
| Ar (168) | 1.00; 1.00; .04; .96, 46; 23 | 1.00; 1.00; .04; .92, 40; 25 | 1.00; 1.00; .04; .88, 37; 26 | 1.00; 1.00; .04; .91, 30; 23 | .92; 1.00; .00; .69, 25; 13 |

Overall: pairwise 76.9%, class 93.3%, exact 7.7%, ΔAIC set 76.2% (mean size 25,
median 18).

What the table says:
- **Single answers are almost never right.** With up to fifty events, the best
  fit is the injected candidate 7.7% of the time. The information is in the
  classes and the set.
- **The classes hold the truth** 93% of the time. Germanium at N = 5 and 20 is
  lowest, at 65% and 77%.
- **Argon's 100% is degeneracy, not discrimination.** The exact rate is 0–4%
  and the set holds 25–46 candidates. With these numbers of events, the
  operators' spectra above DEAP-3600's threshold are hard to tell apart.
- **The ΔAIC ≤ 2 set is not a confidence set.** Its coverage is 44–96%, and it
  is lowest for xenon at N = 10 and 50 and argon at N = 50. Among hundreds of
  candidates, the best of many near-degenerate shapes often beats the true one
  by more than Δ ln L = 1. A calibrated set (its Δ ln L threshold set by toys)
  is future work (section 7).
- **DM6's injection test** (xenon, 20 events, pairwise) gave 71% on its own
  draws, short of the 80% it declared; the owner accepted the class reading
  (91.6%). Here xenon at N = 20 gives 57% pairwise from 23 cases (binomial
  standard error ≈ 0.10) and 96% by class. The pairwise results agree within
  about 1.4 standard errors.
- The non-xenon targets have a flat background of one event over the window,
  and the xenon target LZ's own b*. A case's draw includes the background, so
  at N = 3 a background event is a large share of the sample.

### 2.4 Historical excesses (`evaluation/historical.py`, `experiments/historical.py`)

Path 2 on searches whose verdict the literature has reached, with the verdict
beside the system's.
- **The searches** are new modules, one class for any search reported in a
  paper with its events. Each search is a record in
  `experiments/data/historical/`, and each number in it is the paper's
  unless the record says "declared". Both register as searches with signals,
  not as default null searches.
  - **CDMS II Si (2013)**, arXiv:1304.4279:
    - three events at 8.2, 9.5 and 12.3 keV;
    - 140.2 kg·day over 7–100 keV;
    - a background of 0.41 surface events;
    - the efficiency digitised from Fig. 1's vector paths
      (`docs/dm10/digitise_cdms_si.py`; 285 points).
  - **CDMS II Ge (2009)**, arXiv:0912.3592:
    - two events at 12.3 and 15.5 keV;
    - 612 kg·day over 10–100 keV;
    - a background of 0.9 events (surface events plus neutrons);
    - the efficiency from the text (about 25% at 10 keV, 32% at 20 keV, 25%
      at 100 keV), joined linearly.
  - **The background's shape.**
    - CDMS II Si's background is spread as its surface events are: those in the
      WIMP-search data that lie in the nuclear-recoil yield band but fail the
      timing cut. They are counted from Fig. 3's vector markers by energy
      colour: 22 at 7–20 keV, 6 at 20–30 keV, none above.
    - The same count finds the paper's three candidates (in the band, passing
      timing, all at 7–20 keV), which checks the reading.
    - The collaboration's pass-fail estimate of the leakage scales exactly this
      population.
    - This replaced the flat background of the first development run (both
      runs are below).
  - **The background's rate** is profiled within the uncertainty each paper
    states, combined in quadrature (section 2.5):
    - CDMS II Si: +0.20 −0.08 (stat) and +0.28 −0.24 (syst) on 0.41, so −62%
      and +84%;
    - CDMS II Ge: ±0.1 (stat) and ±0.2 (syst) on the surface events, plus the
      two neutron estimates, so ±25%.
  - **Declared approximations.**
    - The background is flat within each energy range (CDMS II Si), or over the
      whole window (CDMS II Ge, whose paper gives no shape).
    - The resolution is a single Gaussian width.
- **Each module reproduces the numbers its paper quotes:**

  | search | quantity | paper | module | ratio |
  |---|---|---|---|---|
  | CDMS II Si | SI limit at 10 GeV (optimum interval) | 2.4 × 10⁻⁴¹ cm² | 2.46 × 10⁻⁴¹ cm² | 1.03 |
  | CDMS II Si | equivalent exposure, 10 GeV, 7–100 keV | 23.4 kg·day | 23.5 kg·day | 1.004 |
  | CDMS II Ge | SI limit at 70 GeV (optimum interval) | 7.0 × 10⁻⁴⁴ cm² | 7.31 × 10⁻⁴⁴ cm² | 1.04 |
  | CDMS II Ge | equivalent exposure, 60 GeV | 194.1 kg·day | 180.9 kg·day | 0.93 |

  The last ratio is the cost of joining three stated efficiencies linearly.
- **The verdicts** are in `evaluation/data/historical_verdicts.yaml`. Each
  quotes its source; the sources' abstracts were read through the arXiv API.
  - *Significance.* Both collaborations: not evidence. CDMS Si's local
    p = 0.19%, "does not rise to the level of a discovery". CDMS Ge's
    P(≥ 2 background events) = 23%. The system agrees if its global
    significance is below 3σ.
  - *The standard reading* of CDMS Si (spin-independent, isospin-conserving,
    at the paper's best fit of 8.6 GeV) is excluded. LUX 2013
    (arXiv:1310.8214) is "in strong disagreement"; SuperCDMS 2014
    (arXiv:1402.7137) is "in tension", with 1.2 × 10⁻⁴² cm² at 8 GeV
    against the 1.9 × 10⁻⁴¹ needed. The system agrees if the joint test of
    the search and the null searches rejects the reading, p_PG < 0.01.
- **The run.**
  - Path 2 runs on the library's own space (748 candidates). The null
    searches are today's: CRESST-III, CDMSlite, PICO-60, DEAP-3600 and LZ
    WS2022+WS2024.
  - Four leading classes are carried forward. 200,000 toys give the global
    significance.
  - Leaders that survive the null searches are reported as findings: the
    literature's verdict covers only the readings it tested.

**The development half: CDMS II Si.** Three runs, all kept in
`docs/dm10/results/historical.jsonl`:

| background | local Z | global Z | significance | standard reading: p_PG (strongest null) | agrees | background ranks | leaders surviving the nulls |
|---|---|---|---|---|---|---|---|
| flat over 7–100 keV, rate fixed (first run) | 4.60 | 4.42 | disagrees | 4 × 10⁻⁶ (LZ) | yes | 1st | none |
| Fig. 3's surface events, rate fixed | 3.33 | 3.10 | disagrees | 8 × 10⁻⁴ (LZ) | yes | 1st | L18s@5 |
| **Fig. 3's surface events, rate profiled** | **3.03** | **2.90** | **agrees** | **2.3 × 10⁻³ (LZ)** | **yes** | **1st** | **L13v@20, L18s@5** |

The collaboration's own local significance, with its fitted background model,
is 2.9σ (p = 0.19%). **The case now agrees with the literature on both
items.**
- The rule (global Z < 3σ) was declared before the first run and never
  changed.
- The two changes that moved the result came from the paper: its surface-event
  energies (Fig. 3) and its stated uncertainties.
- Both were made before the held-out half was looked at, and the held-out
  record carries its own paper's uncertainties in the same way.
- The margin is narrow: 2.90σ against the 3σ line.
- **The standard reading is excluded,** as the literature found, in all three
  runs. With the rate profiled the joint test gives p_PG = 2.3 × 10⁻³ (with it
  fixed, 8 × 10⁻⁴), with LZ's limit the strongest.
- **Like for like, the module reproduces the collaboration's fit.** Fitting
  spin-independent, isospin-conserving scattering alone (O1s, mass scanned),
  the system's best fit is 8.6 GeV and 1.75 × 10⁻⁴¹ cm² (2.8 signal events).
  The paper's is 8.6 GeV and 1.9 × 10⁻⁴¹ cm².
- **The significance item fails, narrowly.** The system's global 3.10σ is just
  above the rule's 3σ, while the collaboration's value is 2.9σ. At the best
  SI mass the system's local value is 3.35σ, about 0.45σ above the
  collaboration's, for three reasons:
  - **The fixed background rate.** The collaboration profiled the background
    rates over their uncertainties (+0.20 −0.08 stat, +0.28 −0.24 syst on
    0.41); the system holds the rate fixed.
  - **The coarse shape.** The shape is three bins, and the neutron and ²⁰⁶Pb
    backgrounds (upper limits) are left out.
  - **The mass scan.** The collaboration's p-value tests WIMP + background
    against background with the mass free. The system's local value is at a
    fixed mass.

  The first two runs held the rate fixed. The owner approved profiling it
  (section 2.5), and the third run did:
  - the spin-independent local value at 8.6 GeV fell from 3.35σ to 3.05σ;
  - the largest local value over all candidates (L13v at 10 GeV) fell to
    3.03σ;
  - the global value fell to 2.90σ.
- **The flat background overstated the excess by 1.3σ.** That is the size of a
  declared approximation when the events sit where the background gathers. It
  is why the shape was taken from Fig. 3, the population the collaboration
  itself uses. The shape was not tuned: it is the only one the paper gives.
- **The tournament's verdict is the literature's.** Background alone ranks
  first, ahead of every candidate, because the null searches exclude the
  leaders.
  - Two leaders survive the null searches (p_PG ≥ 0.01), and both are
    momentum-dependent:
    - L18s at 5 GeV, i (P^μ/m_M) χ̄γ⁵χ N̄ iσ_μα (q^α/m_M) N;
    - L13v at 20 GeV, χ̄γ^μγ⁵χ (K_μ/m_M) N̄N.
  - Even so, both rank below background alone. They are readings the
    literature did not test, recorded as findings.
- **The held-out case** (CDMS II Ge 2009) keeps a flat background: its paper
  gives no shape. By the lesson above, if it errs, it errs towards a larger
  significance.

### 2.5 The background's rate as a nuisance parameter (`inference/nuisance.py`)

Approved by the owner on 2026-10-01, after the CDMS II Si development case
showed that the significance item turned on it.
- **The model.** A search that states its expected background B with an
  uncertainty (−σ₋, +σ₊, relative) has its background density become θ b(E).
  The likelihood gains a constraint from that statement, a bifurcated Gaussian
  about the auxiliary measurement a (a = 1 for the data):

      ln L(s, θ) = −s − θB + Σ_i ln[s f_i + θ b_i] − ½ ((θ − a)/σ)²,
      σ = σ₊ where θ > a, σ₋ where θ ≤ a .

- **Profiling.** θ is profiled in every statement about the signal count s:
  the best fit, the local significance, the intervals, the combination with
  the null searches, and the flags.
  - The function is concave in (s, θ), so damped Newton steps find the
    maximum. They are vectorised over candidates.
  - The profile in s is concave too, so ŝ > 0 exactly where its slope at
    s = 0 (with θ at the background-only fit θ̂₀) is positive.
- **The toys** for the global significance are drawn from θ̂₀ b(E). Each toy
  draws its own auxiliary measurement about θ̂₀, and every fit in it profiles
  θ, as on the data: the usual frequentist construction. 200,000 toys take
  about two minutes for CDMS II Si (264 live candidates).
- **Where nothing is stated, nothing changes.** The fixed-background code path
  is untouched, so the injection suite, LZ's tables and DM6's LZ result are
  exactly as before. Tests check the limits:
  - a vanishing σ gives the fixed fit to 10⁻⁴;
  - the profile equals a brute-force maximum over θ;
  - many candidates at once match one at a time.
- **On CDMS II Si,** the background-only fit has θ̂₀ = 1.85: background alone
  needs 85% more background to meet three events, which the stated +84% (1σ)
  makes affordable. The spin-independent local significance at 8.6 GeV falls
  from 3.35σ to 3.05σ, while ŝ barely moves (2.79 → 2.81 events).

## 3. The baselines

**Exhaustive likelihood fitting, no agents.** On the injection cases Path 2
and exhaustive fitting compute the same likelihoods. DM9's variant agent is
not triggered there: no tension with null searches, no complementary
constraint, and unit couplings. The difference is therefore in what is
reported:
- the exhaustive baseline names its single best fit, and is right 7.7% of the
  time;
- the system names the ΔAIC ≤ 2 set (right 76.2%, mean size 25) and the
  degeneracy class (right 93.3%).

On the historical case (section 2.4) the difference is the combination with
the null searches. Exhaustive fitting of CDMS II Si alone prefers a signal (a
low-mass candidate at 3.3σ local). The system's tournament ranks background
alone first, because the null searches exclude the leaders.

**Direct prompting of a language model** (`agents/direct.py`,
`evaluation/baselines.py`, `docs/dm10/direct_baseline.py`).
- **What the model is told** for each injection case is what Path 2 is told:
  - the search, target and window;
  - the expected background, flat over the window;
  - that the strength is free;
  - the event energies;
  - the candidate list, with each card's name and how a label is written.

  It is not told the spectra.
- **Its answer:** a best candidate and a plausible set of up to 30. Labels not
  on the list are dropped and counted.
- **Scoring** is the system's: pairwise, class, exact, and the set's coverage
  and size.
- **The cases** are the first ten injection cases of each target and N: 101
  in the development half, 99 held out.
- **Cost** (dry run, `--dry-run`):
  - stable prompts of 0.8–2.1 thousand tokens, cached across cases where the
    provider allows;
  - 66–165 tokens of events per case;
  - about $2.50 a model on the development half, with 1,200 output tokens
    allowed per case for reasoning.

  Both models (claude-opus-5-5 and gpt-5.6-sol) on both halves: about $10.
- **Historical cases are not given to the model.** It has read the papers, so
  its verdict would be recall, not inference.

**The development half** (approved by the owner, 2026-10-01: $5, $2.50 a
model). Scored with `docs/dm10/baseline_compare.py`, on the cases both the
system and the model answered.

*claude-opus-5-5*: 78 of 101 cases before the $2.50 cap ($0.032 a case, 30%
above the dry run's estimate).

| target | who | pairwise | class | exact | set holds truth | mean set size |
|---|---|---|---|---|---|---|
| Xe | system | 0.60 | 0.96 | 0.08 | 0.52 | 38.3 |
| Xe | claude-opus-5-5 | 0.48 | 0.88 | 0.04 | 0.20 | 27.6 |
| CaWO₄ | system | 0.71 | 0.92 | 0.04 | 0.75 | 15.7 |
| CaWO₄ | claude-opus-5-5 | 0.29 | 0.62 | 0.08 | 0.25 | 26.1 |
| Ge | system | 0.71 | 0.83 | 0.08 | 0.71 | 8.3 |
| Ge | claude-opus-5-5 | 0.38 | 0.54 | 0.08 | 0.71 | 27.6 |
| Ar (N = 3 only) | system | 1.00 | 1.00 | 0.20 | 1.00 | 45.2 |
| Ar (N = 3 only) | claude-opus-5-5 | 1.00 | 1.00 | 0.00 | 0.20 | 30.0 |
| **all** | **system** | **0.69** | **0.91** | **0.08** | **0.68** | **22.5** |
| **all** | **claude-opus-5-5** | **0.42** | **0.71** | **0.06** | **0.37** | **27.3** |

- **The system's class rate is 20 points above the model's** (0.91 against
  0.71), so G5's margin of 10 is met on the development half.
- **The system's set holds the truth nearly twice as often** (0.68 against
  0.37), with fewer members (22.5 against 27.3).
- **Neither names the exact candidate:** 8% and 6%. The model invented no
  labels in 78 answers. It filled its plausible set to the maximum of 30 in 53
  of them.
- **The model is closest on xenon,** where its class rate is 0.88. It is
  furthest on CaWO₄ and germanium, where telling the operators apart needs the
  spectra.
*gpt-5.6-sol*: 44 of 101 cases, in three launches.
- **The first launch** was refused at once by OpenAI's JSON mode, which needs
  the word "json" in the input messages. No cost; the client now adds it.
- **The second and third launches** stopped on dropped connections, after 10
  cases (not saved) and 8 cases (saved; $0.46 counted). The server closes a
  connection held open while the model reasons.
  - Retries of the dropped requests may have been billed without the budget
    seeing them, so the true total is on OpenAI's usage page.
  - `OpenAIClient(background=True)` now queues each request and polls for it,
    cancelling one past its deadline. The launcher takes `--resume`.
- **The fourth launch** resumed from the 8 saved cases in background mode,
  with $2.50 of the owner's second $5. The cap allowed for those uncounted
  retries. It added 36 cases at $0.07 a case and stopped at the cap ($2.56;
  the last call crosses it). Counted for the rerun: $3.02.

| target | who | pairwise | class | exact | set holds truth | mean set size |
|---|---|---|---|---|---|---|
| Xe | system | 0.64 | 0.91 | 0.09 | 0.64 | 34.4 |
| Xe | gpt-5.6-sol | 0.18 | 0.64 | 0.00 | 0.00 | 15.6 |
| CaWO₄ | system | 0.62 | 0.88 | 0.00 | 0.62 | 23.0 |
| CaWO₄ | gpt-5.6-sol | 0.00 | 0.50 | 0.00 | 0.12 | 15.8 |
| Ge | system | 0.83 | 0.92 | 0.17 | 0.75 | 8.2 |
| Ge | gpt-5.6-sol | 0.42 | 0.67 | 0.08 | 0.58 | 22.8 |
| Ar | system | 1.00 | 1.00 | 0.00 | 0.85 | 39.1 |
| Ar | gpt-5.6-sol | 0.85 | 0.85 | 0.00 | 0.08 | 20.6 |
| **all** | **system** | **0.80** | **0.93** | **0.07** | **0.73** | **26.6** |
| **all** | **gpt-5.6-sol** | **0.41** | **0.68** | **0.02** | **0.20** | **19.1** |

- **The system's class rate is 25 points above GPT's** (0.93 against 0.68),
  so G5's margin of 10 is met for both models on the development half.
- **GPT is weaker than Claude here** on every reading, though the two models
  saw different subsets of cases. Its plausible sets are smaller (19 on
  average) and hold the truth only 20% of the time; on xenon, never.
- No labels were invented in 44 answers. The interleaved order kept the
  partial run balanced across targets.

- **The sample is unbalanced.** Cases ran in target order, so the cap left
  argon with only its N = 3 cases. The cases are now interleaved by index
  (`baselines.cases`), so a capped run stays balanced. A full run costs about
  $3.30 a model per half.

## 4. Comparison with published analyses

Where a published analysis asked the same question, its conclusion is set beside
the system's. The conclusions are quoted from the abstracts (read through the
arXiv API) and, for arXiv:2609.21823, from the paper itself. The system's side
comes from DM6's stored result on LZ's event (`docs/dm6/lz_case_xenon.json`) or
is computed afresh (`docs/dm10/comparisons.py` → `comparisons.json`).

**Combined fits of the high-energy recoil events.**
- **DIAMX, arXiv:2512.05850.**
  - *The paper:* combined fits of LZ, PandaX-4T and XENONnT. Velocity-dependent
    and inelastic interactions reproduce the high-energy events, at local
    significances up to 3.5σ. The ¹²⁴Xe double-electron-capture charge yield
    moves the result between null-like and 3.5σ.
  - *The system:* on LZ's window alone, the same two families lead:
    - inelastic, endothermic (O1 and O4 at δ = 300–350 keV, 0.4–4 TeV);
    - one momentum-dependent elastic interaction (L12, at 4 TeV).

    The largest local significance is 3.65σ; the global significance is 3.50σ
    (one-event closed form, checked by toys). It does not vary the DEC yield.
  - *Agreement* in kind. The DEC systematic is not modelled.
- **arXiv:2609.15985** (a posterior over mass, splitting and interaction).
  - *The paper:* the event selects (i) endothermic WIMP-like models at high
    mass, kinematically tuned, and (ii) exothermic models from sub-GeV to heavy
    with sizeable splittings. Elastic scattering needs momentum-suppressed or
    spin-dependent interactions.
  - *The system:*
    - (i) agrees: seven of the eight leaders are endothermic at δ = 300–350 keV
      and 0.4–4 TeV, at the kinematic edge (DM6);
    - the elastic leader, L12 (i χ̄ iσ^μν q_ν χ K_μ N̄γ⁵N), is
      momentum-dependent and couples to the nucleon spin, as the paper requires;
    - (ii) is not tested: LZ's model space, and so DM6's, has no exothermic
      splittings (δ < 0).
  - *Agreement* where both looked. Exothermic splittings are a gap in the space.
- **arXiv:2609.21823** (capture in the Sun of the elastic operators that explain
  the event).
  - *The paper* (WimPyC capture; IceCube 2016 and 2025 solar data, and IceCube
    and Super-K atmospheric data):
    - the ν̄ν channel gives the strongest limits and b b̄ the weakest;
    - L6v, L8s and L8v (LZ's numbering) are almost entirely ruled out;
    - not even ν̄ν excludes L4, where the EFT is in any case invalid.
  - *The system,* computed here: every elastic candidate of LZ's space with
    Z ≥ 3 up to 1 TeV, 58 in all (L02, L04, L08, LZ's L9, L10–L12, L14, L16,
    L18–L20). Each is taken at the coupling that explains the event, and its
    capture rate is compared with what IceCube's 2016 record allows in b b̄,
    W⁺W⁻ and τ⁺τ⁻.
    - None is excluded. The largest C/allowed is 0.04 (L19s at 1 TeV, τ⁺τ⁻);
      the median is 10⁻⁴ and the smallest 10⁻⁷.
  - *Consistent, and partial.* The paper's exclusions come from the ν̄ν channel
    and the 2025 data, which the system's curated database does not hold. In
    the channels both have, the paper excludes nothing with b b̄ either. Both
    find L4 allowed.
  - L6v cannot be compared: it is DM6's known discrepancy with LZ's table
    (Z = 1.1–2.7 against LZ's 2.9–3.3), so it does not reach Z ≥ 3 here.
  - Adding the ν̄ν channel, IceCube's 2025 limits and Super-K's atmospheric
    data to the database is on the list of future work (section 7).

**Global operator fits.**
- **Catena, Gondolo, arXiv:1405.2637.**
  - *The paper:* the null searches constrain every coupling of the effective
    theory, including the velocity- and momentum-dependent ones. Pairs of
    couplings are degenerate in the searches that claim a signal (CoGeNT,
    DAMA).
  - *The system:* the same structure, found differently. DM4's degeneracy
    classes are the operators that a given number of events cannot separate:
    26 classes among LZ's 612 models at 20 events, and the argon classes in
    the injection suite (section 2.3). Path 1 sets limits on every card.
  - *Agreement in kind.* CoGeNT and DAMA have no modules.
- **Avis Kozar, Scott, Vincent, arXiv:2310.15392.**
  - *The paper:* neutrino telescopes beat underground searches above about
    100 GeV for many operators; the next underground generation will reverse
    that.
  - *The system:* DM7's telescope limits are carried beside the direct
    limits in Path 1 (`ExclusionResult.telescopes`). They were not set
    against each other operator by operator here.
  - *Not yet compared.* That comparison is a sweep of Path 1 over the cards,
    with no new code.

**The operator fits of DAMA.**
- **Catena, Ibarra, Wild, arXiv:1602.04074:** a strong tension between DAMA
  and the null searches across the effective theory, under the standard halo.
- **Kang, Scopel, Tomar, Yoon, arXiv:1804.07528:** most couplings fit DAMA's
  phase-2 modulation better than spin-independent scattering, and every best
  fit is in tension with XENON1T and PICO-60.
- *The system cannot yet compare.* It has no annual-modulation module and no
  NaI search. A DAMA module (the modulation amplitudes per energy bin, NaI
  quenching) is on the list (section 7).

## 5. What DM10 found

1. **Single best fits are almost never right.** Up to fifty events from a
   library candidate on four targets, the best fit is exact 7.7% of the time.
   The class holds the truth 93%, the ΔAIC ≤ 2 set 76% (section 2.3). The
   system's value is in the sets and classes it reports.
2. **The ΔAIC ≤ 2 set is not calibrated:** 44–96% coverage. A Δ ln L threshold
   set by toys would fix it (section 7).
3. **A background's shape and rate can make or unmake an excess.** On CDMS
   II Si, a flat background gave 4.4σ global. The collaboration's own
   surface-event shape gave 3.1σ, and profiling the rate within its stated
   uncertainty gave 2.9σ, the collaboration's own figure. Path 2 now profiles
   the rate wherever a search states one (section 2.5).
4. **The system reaches the literature's verdict on CDMS II Si.** The excess
   is below evidence (2.90σ global). The standard reading is excluded by the
   null searches (p_PG = 2.3 × 10⁻³, LZ strongest), and background alone ranks
   first. The module reproduces the collaboration's best fit (8.6 GeV, 1.75
   against 1.9 × 10⁻⁴¹ cm²).
5. **On LZ's event the system agrees in kind with all three published
   analyses** where it holds the inputs. It cannot test exothermic splittings
   or the ν̄ν channel of capture, which is where arXiv:2609.15985 and
   2609.21823 go beyond it (section 4).
6. **LZ's tables and the limits reproduce as in DM3 and DM6** on their
   development halves: 94.2% of LZ's entries within 0.3σ, and 70 of 70 limit
   points inside the validated ranges (sections 2.1, 2.2). Those halves are not
   fresh, since DM3 and DM6 used every case.

## 6. The gate: the owner's rules

The build plan leaves the gate's rules to the owner. They are fixed before the
held-out half is run, then applied to it once, at one commit, with the run in
the ledger. **The owner adopted the five rules below as proposed
(2026-10-01).** They are now pre-registered and are not to be changed without
the owner. The numbers beside them are the development half's, for
orientation; they did not set the thresholds.

| | rule (held-out half) | development half |
|---|---|---|
| G1 | limits: every point inside a validated range passes DM3's rule (a regression test; points outside are reported) | 70/70 (all points: 70/80) |
| G2 | LZ's tables: at least 90% within 0.3σ (DM6's rule) | 94.2% |
| G3 | injection: the class holds the truth in at least 85% of all cases, and in at least 75% for each target at N ≥ 20 (pooled) | 93.3%; Xe 90.7%, CaWO₄ 85.7%, Ge 86.5%, Ar 100% |
| G4 | historical: the system agrees with the literature on every held-out case (CDMS II Ge 2009: below evidence) | CDMS II Si: both items (2.90σ global; standard reading p_PG = 2.3 × 10⁻³) |
| G5 | baselines: on the held-out direct-prompting cases, the system's class reading beats each language model's by at least 10 percentage points | not yet run |

The owner's decisions (2026-10-01):
- **The rules:** G1–G5 as proposed.
- **The paid baselines:** $5 and then a further $5 on the development half
  (section 3); $10 on the held-out half for the gate.
- **The background-rate nuisance:** approved, built and run on the
  development half before the gate (section 2.5).

### The gate's run (2026-10-02)

The rules were committed as code before any held-out case was run
(`docs/dm10/gate.py`, commit 1586967) and applied once
(`docs/dm10/gate.md`). Every held-out run is in the ledger
(`docs/dm10/held_out_ledger.jsonl`).

| rule | held-out half | result |
|---|---|---|
| G1 | limits: 69 of 69 points inside the validated ranges pass (71 of 81 in all) | **PASS** |
| G2 | LZ's tables: 95.1% of 304 within 0.3σ | **PASS** |
| G3 | injection: the class holds the truth in 95.8% of 384; at N ≥ 20, Xe 94.6%, CaWO₄ 90.3%, Ge 93.0%, Ar 100% | **PASS** |
| G4 | historical: CDMS II Ge 2009, below evidence; the system agrees (global 2.48σ, local 2.82σ) | **PASS** |
| G5 | baselines: the system's class rate against claude-opus-5-5's, 97.0% to 79.8% on 99 cases (+17.2 points); against gpt-5.6-sol's, 94.6% to 75.0% on 56 cases (+19.6) | **PASS** |

**5 of 5 rules met: the gate passes.**

On the held-out half:
- **The ten failed limit points** all lie outside the validated ranges:
  - CRESST-III at 0.16–0.27 GeV;
  - DEAP-3600 at 24 GeV;
  - LZ from 438 GeV to 9.9 TeV, at ×1.31–1.35, as in DM3, which validated LZ
    below these masses;
  - XENONnT at 10 GeV and PandaX-4T at 27 GeV.
- **Injection, in all four readings:**
  - pairwise 84.9%;
  - class 95.8%;
  - exact 8.3%;
  - the ΔAIC set holds the truth 80.7% of the time.
- **CDMS II Ge 2009:**
  - background alone ranks first;
  - one leader survives the null searches, L18s at 10 GeV;
  - the background rate was profiled (±25%).
- **The baselines, with the system on the same cases:**

  | | cases | pairwise | class | exact | set holds truth (size) | labels invented |
  |---|---|---|---|---|---|---|
  | system | 99 | 0.85 | 0.97 | 0.09 | 0.82 (24.9) | — |
  | claude-opus-5-5 | 99 | 0.49 | 0.80 | 0.03 | 0.42 (28.2) | 0 |
  | system | 56 | 0.82 | 0.95 | 0.07 | 0.80 (22.1) | — |
  | gpt-5.6-sol | 56 | 0.39 | 0.75 | 0.02 | 0.20 (18.5) | 0 |

The run's history, for completeness:
- **The dates.** The owner adopted the rules on 2026-10-01 and approved the
  run on 2026-10-02; the ledger's reasons quote the second date.
- **Two commits.** The suites before limits ran at commit 1586967. A
  documentation commit was made by mistake during the run (60d74b4: the
  related-work scan; only `docs/related_work.md` and the write-up notes
  differ, no code), and limits and the baselines are stamped with it.
  - In `gate.md`, the G5 row shows the injection run's commit (1586967),
    since G5 compares the baselines with that run's results. The baseline
    runs themselves are at 60d74b4 (ledger).
- **GPT's held-out run took several launches.**
  - The first stopped at once on a dropped connection (0 cases); the second
    after 28.
  - A driver resumed it across further drops (`--resume`; each launch is in
    the ledger) until OpenAI refused with `credit_balance_exhausted` after 56
    cases.
  - Its $4.03 is the sum of the launches' counted spend, as each launcher
    printed it (the per-launch output was not committed):
    - $1.92 (to 28 cases);
    - $1.89 (to 53);
    - $0.07 (to 54);
    - $0.15 (to 56);
    - $0.00 for each failed launch.
  - Its order interleaves targets and N, so the 56 cover every target and N.
  - G5 compares on the cases each model answered, as on the development half.
  - Topping up the account and resuming would complete the 99. G5's margin
    (+19.6 points) makes a different verdict unlikely, but the gate is not
    re-applied.

## 7. Future work found by DM10

- **More historical searches.** Each is a record in
  `experiments/data/historical/` once its inputs are digitised.
  - EDELWEISS-II 2011 (five events against an estimated background below three).
  - CRESST-II 2012 (67 events in a multi-element target with α, neutron and
    ²⁰⁶Pb backgrounds of known shape).
  - CoGeNT 2010–2014 (a low-energy excess, later attributed largely to surface
    events).
  - XENON100 2012 (two events against one).
- **An annual-modulation module** (DAMA/LIBRA, NaI with its quenching). The
  operator fits of DAMA (arXiv:1602.04074, 1804.07528) can then be compared.
- **Stated background uncertainties for the LZ extended window,** so that its
  fits profile the rate as the historical searches now do. It declares none,
  which keeps DM6's result exactly as it was.
- **Background spectra** for the historical searches, where a paper gives them,
  in place of flat densities (CDMS II Ge 2009, EDELWEISS-II).
- **Exothermic splittings** (δ < 0) in Path 2's space. arXiv:2609.15985 finds
  them favoured by LZ's event, and neither LZ's space nor the library's
  includes them.
- **Capture in the Sun:** the ν̄ν channel, IceCube's 2025 ten-year limits
  (arXiv:2507.08457) and the IceCube and Super-K atmospheric data, as curated
  records the owner verifies. arXiv:2609.21823's exclusions come from these.
- **The ¹²⁴Xe double-electron-capture systematic** in the LZ module
  (arXiv:2512.05850 finds it moves the significance between null-like and
  3.5σ).
- **A calibrated candidate set.** The tournament's ΔAIC ≤ 2 set covers the
  truth 44–96% of the time on injections (section 2.3). A threshold on Δ ln L
  set by toys over the candidate space would give a set with stated coverage.
- **Telescope against direct limits, card by card** (the comparison with
  arXiv:2310.15392): a sweep of Path 1, no new code.

## 8. How to run

```bash
uv run adroit eval injection                  # development half, to runs/eval/; a few minutes
uv run adroit eval lz_tables                  # development half
nice -n 10 uv run adroit eval limits          # slow: DIAMX takes minutes per xenon mass
nice -n 10 uv run adroit eval historical      # Path 2 with LZ as a null search
uv run adroit eval injection --held-out --reason "confirm <change>"   # the owner's half; logged
uv run python docs/dm10/direct_baseline.py --dry-run                  # cost estimate, no calls
uv run python docs/dm10/direct_baseline.py --live --budget 3 --model claude-opus-5-5   # paid
nice -n 10 uv run python docs/dm10/comparisons.py                    # section 4
uv run --with pymupdf python docs/dm10/digitise_cdms_si.py            # CDMS II Si's efficiency
```
