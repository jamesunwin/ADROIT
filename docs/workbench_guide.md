# The workbench, step by step

`uv run adroit workbench` opens it at http://127.0.0.1:8765. Every run ends in one command-line call, so the
workbench and the CLI compute the same thing. A run continues if you close the page; **Studies** lists every run.

Every page opens with a sentence on what it does and what comes out, and a row of facts (what it costs and what
comes next); longer caveats are under **Details and assumptions**. The menu is grouped: **Run**
(Constrain a model, Signal best fits, Explain a signal), **Libraries** (Model library, Records) and **Add data** (Add
a limit, Add a signal). A "?" beside a term gives its definition. The home page has three examples to start from.

## Track 1: constrain a model (is it consistent, and what do the data allow?)

**A model from the literature (the quickest start).**

1. **Constrain a model** → tab **A library model** (the default).
2. Pick a portal (e.g. "Real scalar singlet (Higgs portal)"). Its scan setup appears: the two axes, the fixed values and the
   parameter relations.
3. Press **Scan the portal**. The live view shows progress and spend ($0 for a scan), with a checklist of the run's
   stages, each ticked as it finishes and the current one with its count.
4. When it finishes, **Open the study**: a summary card (the verdict, when it was calculated, how long it took,
   its cost, and **Run again**), then the full report: the verdict on the thermal-relic contour, the exclusion plane
   with every constraint, and the constraints still pending (with the reason for each).

**The model library** has two parts, switched at the top of its page:
- **Standard library:** every model ADROIT has the code to formulate, grouped by kind. It holds the 27 portal models,
  which Constrain a model scans, and the 55 interactions Signal best fits searches. Each page typesets the model and
  links to its run; **Copy into my personal library** opens a portal model as a draft to review, change and approve.
- **Personal library:** your own models, one card per model with its earlier revisions folded inside, and whether
  each page can run it (hover a grey "not yet" for the reason).

**Your own model.**

1. **Model library** → **Create or refine a model**. Give the model as TeX, a screenshot, words (all three are
   paid and budget-gated) or typed YAML ($0).
2. Review each candidate: the typeset Lagrangian and field table, the assumptions, and the parameters. Correct it if
   needed; tick *I reviewed…* and **Approve**. The model's page opens.
3. On the model's page, **Run this model** first says which route computes the model — a library engine, the
   generic route from the model's own Lagrangian, or none, with the reason — and lists the physics included and what
   is not (coannihilation, poles, long-range effects, direct detection, annihilation today, the lines, the LHC; $0,
   no language model; `parameter_space.route_report`, G12). It then links **Constrain this model (Track 1)** or says
   what is missing, for example "give a value to coefficient m₂", or "ADROIT's engines do not cover it: …".
4. The link opens **Constrain a model** with the model filled in (tab **My model**, where **A model from my library**
   also loads a saved one). The scan setup is shown at once; change the axes in its table if you wish (or keep
   the model's defaults), then press **Scan**, which accepts the setup shown.
5. **Open the results** when the run completes.

A field content alone also works: **Constrain a model** → **Build from fields** → **Build and audit**. Fill in one
row per field (its role, spin, colour, SU(2) multiplet, hypercharge, dark parity and, if you know it, its mass), or
switch on **Edit as YAML** to type or paste the same model as text; a mistake is named on its row or its line before
anything runs. ADROIT writes every allowed renormalizable term. The study page lists the models; approve those to constrain, and each runs as
its own Track 1 study.

## Track 2: signal best fits (which interactions best fit a signal?)

1. If the signal is not built in, add it first.
   - **Add a signal**: write a signal (anomaly) record in the page's editor (the template, every field explained),
     **Save and check** it (it is saved in the runs folder, under signal_records), or draft it from an arXiv paper
     (paid; a person must verify the draft). A draft goes to a new file, `signal_records/draft_<arXiv id>_<run>.yaml`
     unless you name one, and never replaces a file: a name already taken is refused before anything is paid for.
   - **Add a limit**: upload the paper's files for a reviewed reading. It can yield a signal as well as a limit.
2. **Signal best fits**: choose **the search with events**, which is a built-in search, a confirmed signal, or a
   signal record file.
3. Keep the default null experiments, or choose others (step 1 of the page).
4. Optional (step 2): add your own models (saved ones, or a typed model pasted) and their masses. Leave **the
   library's space as well** ticked. Step 3, **Options**, holds the number of background-only toys (fewer is faster
   while exploring), splittings, model properties and the physical-point checks.
5. Press **Fit, combine and rank**. When the run completes, the study page ranks the interactions. Above the table,
   once for the whole search, the global significance: the largest local excess, corrected for every candidate
   tried. In the table, each candidate's local significance and its compatibility with the null searches (the
   p-value of χ²_PG: high means the search with events and the searches that saw nothing agree; it is not a
   significance).
6. From the study page, **promote** a candidate or its class. ADROIT builds the mediator models that reproduce
   it, and each child runs Track 1 (recursion). Each child's size (its toys, its Track 1 plane, its masses) is set
   on the form; small values give a quick first look.

**Explain a signal** asks whether one model explains a signal and is otherwise viable: one model (pick a saved one,
or paste YAML), one signal, one report.
- **A standard model** loads its paper's complete benchmark into the editor, every coupling in its own notation with
  its value. Change any number before running; the fit varies the model's physical coupling (g_DM for the DMWG
  models, g_A for the axial Z portal, λ for the Higgs portals).
- **No free coupling:** a model with only gauge interactions (the wino, the higgsino, the quintuplets) is evaluated at
  its own couplings, never fitted. Its band column says "fixed couplings, not fitted".
- **Not offered:** the three standard models the page cannot compute are named under the picker, with what each
  needs: the inelastic dark photon, the CP-violating Higgs portal and the μ_R lepton portal.

## When a model cannot run

Track 1 computes the models its engines cover:

- singlet dark matter with one scalar or vector mediator;
- the portal library: Higgs, dark photon, Z, B − L, L_μ − L_τ, ALP, t-channel, lepton portal, inert doublet,
  2HDM+a;
- the wino and the higgsino.

Track 2 also takes a model whose nucleon couplings were derived (**Constrain a model** → **Derive coefficients
(DM8)**, paid). The model's page says which of these applies, and what is missing.

## The halo

Every form that launches a calculation (a library or typed model in Constrain a model, an approved idea, Explain a
signal's advanced options, Signal best fits) has the same halo choice:
- **the family:** the SHM, or SHM++ (the round halo and the Gaia Sausage, arXiv:1810.11468). SHM + LMC is listed,
  disabled: it is deferred to a later release.
- **the treatment:** the region (Track 1's default), each experiment's published halos (Track 2's), or a fixed common
  benchmark. SHM++ is a fixed benchmark only: choosing it sets the treatment to the benchmark and offers no other, and
  its line reads "fixed benchmark; halo uncertainty not propagated". Its details give its parameters (ρ₀, v₀, v_esc,
  β, η), its time convention, its tables (speeds, angular nodes, generator version and sha256) and what it cannot
  calculate: no accepted-count ratio (the slow searches take their full procedure within the point's budget), no
  annual modulation or directions, no Path 1 structure, private input or native joint fit.

Under them, the halo the run will use, in one line, with its parameters, source, what it cannot calculate and its
limitations folded beneath. The study page, the point table and inspector, `points.csv` (its `halo` column),
`halo.json` in the tables download and every report state the halo the run used.

## Reading a result: what is certified

A decisive claim carries a certificate: the checks its kind needs (a thermal solution: its refined root, a supported
thermal history, finite comparisons, its records, discovery, the halo region; an experimental exclusion of a fixed
point needs no thermal check). Ωh² uses the nominal equation of state, Saikawa & Shirai's 2018 fit; its uncertainty is
not assessed in 1.0, each report says so once, and no claim waits for it ([`eos_band.md`](eos_band.md)). A claim
with a check failed or unknown is pending. A point that its comparisons exclude, where only its thermal claim's own
checks are open, reads "excluded by …"; otherwise the report shows what its computed constraints gave ("pending
(computed: excluded)"). Under each table the report says how many points are certified and why the rest are not.
A pending verdict whose every thermal solution found is excluded leads with that ("ALL FOUND EXCLUDED · COVERAGE
INCOMPLETE" on the Studies badge), the region still undecided. The Studies badge is the stored headline: Track 1's level, the
combined view where it differs ("VIABLE · combined: VIABLE PENDING"), an Explain study's headline, and "UNVERIFIED
RECORDS" where the conclusion depends on a record no person has verified (a run that only enables them says so in its
headline, not on the badge). A result saved before certificates reads "legacy, not assessed", unchanged
(the consolidation m1 certification record of 2026-10-25). The badge keeps the
level as it was decided and says beside it when its certification is stale (an earlier policy, or a table or record
that has changed since) or legacy ("VIABLE · STALE CERTIFICATION", "VIABLE · NOT ASSESSED (LEGACY)"); the Studies
page filters on certification apart from the level, and a point's explanation gives its certificate's reading. The
unverified records a conclusion's claims used are the conclusion's (the consolidation audit repair record of 2026-10-25).

**A point excluded at the halo region's centre.** Over the halo region, a point that direct detection excludes at
the region's centre, but whose exclusion is not established at every sampled halo, reads "excluded at the central
SHM by direct detection; halo robustness incomplete" (or "…; halo-sensitive"). It is listed with its own status
("excluded at the central SHM") and drawn excluded with a gold outline. It is never plain pending, and never an
exclusion throughout the region.

**Explain a signal's plane.** The plane around the fitted band shows where the model's own prediction can explain the
signal:
- the hatched region is where the prediction meets the signal criterion: its actual spectrum and count, no amplitude
  fitted, at least 2ΔlnL = 1 better than background alone;
- each thermal crossing on the relic contour shows its joint reading: a joint explanation, excluded, does not explain
  the signal, or unresolved.

A constraint-only point is never shown as explaining the signal. Over the halo region the signal is assessed at the
search's published halo; a joint claim at one halo for both needs `--halo benchmark`.

**Reassessing a saved study.** `uv run adroit reassess <study folder>` calculates only what a saved study lacks, into
a new child study, and leaves the original unchanged:
- for Explain a signal, the signal requirement on its plane;
- for Constrain a model, the halo work of each thermal point whose halo coverage was incomplete, with
  `--budget N` full calculations per point.

## A damaged record

A record that cannot be read (a run's, a batch's, an annotation, a draft step, a library revision, a study's or its
links, or a study's result whose content is not a result's) is named where it would be listed, with why, and
everything else is listed; opening it directly says it cannot
be read. Anything that calculates from a damaged record (a selected model, the active profile, a budget's ledger)
stops with the reason rather than going on without it. A paid ledger whose last line was cut short reads "not
available" until `adroit ledger recover PATH` keeps its bytes aside and, where the cut entry can be identified, keeps
its request's reservation in full (the consolidation m3 durable record of 2026-10-25).

## Paid steps

Every step that calls a language model is marked "(paid)", asks for a hard cap and your approval, and shows "AI can
make mistakes." under its model choice: ADROIT's code checks every proposal, and a person reviews a model or a record
before it is used.

A run's page shows what it cost from its own paid ledger (a session's runs, from the session's): the dollars settled,
and apart from them any still reserved for a request whose bill is not known (a connection lost after sending, say).
It says "no paid request was sent" only where the ledger shows none; a run from before these ledgers whose log rounds
to the cent shows "about", or "not available" at $0.00. Every page words money the same way, from one reading of
the records (the consolidation m2 accounting record of 2026-10-25): a reservation
or a committed bound is kept beside any other figure, and records that disagree or are damaged are named. A session
sharing another's budget shows that session's money. Without the provider's API key a paid step stops before
anything is reserved or sent and names the variable to set (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`;
[installation](installation.md)).

