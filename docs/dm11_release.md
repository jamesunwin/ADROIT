# DM11: the workbench, the documents and the release set-up

Built 2026-10-02. Cost: $0 (no language-model call was made; a sub-agent of the
coding session compiled the fact sheet the documents draw on).

The plan (build plan, DM11) asks for:
- a workbench and a dashboard for the two pipelines;
- the design document and the paper, with every number citing its run;
- a set-up command for the public release.

All three are built. The paper is a first draft for the owner, who is its
author.

## 1. The set-up command (`adroit setup`; `adroit/external/setup.py`)

- **What it reports.** For every item of the manifest (`external/tools.yaml`):
  - present or missing (a pip item by its installed version);
  - needed or optional;
  - what to do about it;
  - its licence, or that the licence is not confirmed.
- **What it does,** with `--fetch`:
  - fetches the missing git and download items;
  - runs their build commands where the manifest gives them (GSL's recipe is
    the first);
  - otherwise shows the recorded build notes;
  - for manual items (sources that block automated downloads), says what to
    download and where, and checks that it arrived.
- **New fields in the manifest:**
  - `build`: shell commands, with `{tools}` and `{folder}` filled in;
  - `present_if`: a glob that shows a tool is built;
  - `required`.

  Test references, cross-checks, NEST and DM8's opt-in numerical chain
  (MadGraph, MadDM, RAPIDD, GSL) are optional. RAPIDD's folder was corrected
  (it lives in MadDM's `vendor/`).
- **On the owner's machine:** 9 of 9 required items present, and 6 of 10
  optional ones.
  - The four optional items missing are WIMpy_NREFT and dmscatter (the DM2
    references, kept in the older location `data/external/`), NEST, and Capt'n
    General.
  - Of Capt'n General, only its copy of the solar model is used, and that
    copy is present as its own data item.
- **Builds are not attempted for DIAMX and MadGraph.** Their builds are
  platform-specific (separate Python environments, pinned versions, compiled
  extensions) and remain written instructions in the manifest. A build that
  could fail silently on another machine is worse than an instruction.

## 2. The workbench (`adroit workbench`; `adroit/workbench/`)

A local web page at http://127.0.0.1:8765, on this machine only.
- **Forms** for Path 1 (a library card, or a bespoke model as DM8's YAML) and
  for Path 2 (a search with events, its null searches, the number of classes
  and toys).
- **Jobs.** Each run is a background job, one at a time, so the owner's limit
  on parallel work holds. It runs in its own folder under `runs/`, with a
  status file, so runs survive a restart. Command-line runs appear too.
- **Pages:**
  - each run's report, rendered, with its plots;
  - DM10's gate and each suite's latest development and held-out summaries;
  - the external tools (`adroit setup`'s report).
- **One code path.** The command line and the workbench run the same functions
  (`orchestrator/runs.py`), so a result cannot depend on which was used.
- **Built on** Python's standard library plus markdown-it-py, now declared;
  NiceGUI and Streamlit were dropped at DM6. Raw HTML in a report is escaped,
  and a file outside a run's folder is never served.
- **Checked:**
  - the tests drive the routes, the forms and the job board directly;
  - a live run on a spare port loaded every page, ran Path 1 (O1, isoscalar,
    CRESST-III at 10 GeV) to completion and served its report and plot;
  - a path-traversal request got 404.
- **No language model is called** from the workbench. The paid steps (DM8's
  intake and derivation, DM9's agents, DM10's baselines) stay on the command
  line, with their budgets.

## 3. The documents

- **The design document** (`docs/design.md`):
  - the principles;
  - the physics (the rate as `physics/rates.py` implements it; the library and
    its degeneracy measure);
  - Path 1, Path 2, the complementary constraints and the evaluation;
  - the interfaces;
  - a section of results and one of limitations, each number cited.
- **The paper:** a first draft, kept with the development records.
  - Sections: introduction; related work; physics framework; system;
    validation against LZ's analysis; evaluation (gate, injection, baselines,
    historical excesses); LZ's event; comparison with published analyses;
    limitations.
  - The author is the owner; the affiliation is left for the owner.
- **Every number cites its run.**
  - In the paper, `\run{path}` prints a footnote naming the record or results
    file (with `#section`).
  - In the design document, the form is "(run: path)".
  - `adroit/evaluation/citations.py` finds every citation, and
    the check citations record checks that each cited file exists.
  - Now: 31 citations in the paper and 23 in the design document, none
    missing.
- **Where the numbers come from.** They were taken from a fact sheet compiled
  from the milestone records, with exact citations. It also lists where the
  records disagree with each other or leave something unclear (section 4).
  Where records disagree, the documents use the figure the results file
  supports.

## 4. Documentation audit (for the owner)

The fact sheet found these. Those in DM10's and DM8/DM9's status lines were
corrected; the others are listed here rather than edited silently, because
they are statements in records of milestones the owner has already approved.

**Corrected:**
- **DM10's record:**
  - CDMS II Si's p_PG with the rate profiled is 2.3×10⁻³; 8×10⁻⁴ was the
    fixed-rate run;
  - the profiled spin-independent local value is 3.05σ, while 3.03σ is the
    maximum over all candidates;
  - Claude's development spend was $2.52;
  - GPT's held-out $4.03 is now itemised by launch;
  - the rules were adopted on 2026-10-01 and the run approved on 2026-10-02;
  - `gate.md`'s G5 row carries the injection run's commit.
- **The stale "cost so far" and "awaits approval" lines** of the DM8 and DM9
  records and of the build plan's DM10 summary.

**For the owner to decide:**
1. **DM2:** the preamble says "better than 0.2%". The largest gate-case
   deviation in `docs/dm2/reference_summary.txt` is 2.0×10⁻³, equal to 0.2%;
   the table's 3.0×10⁻³ belongs to a case outside the gate.
2. **DM0:** the 1% gate is called met outside the kinematic tail, but 20 GeV
   below 20 keV agrees to 0.4–1.2%.
3. **DM0:** the LZ HEPData record "holds 47 files", but the enumeration
   (3 event samples + 43 tables) is 46.
4. **DEAP-3600's validated range** is written as 50 GeV–10 TeV, 50–9900 and
   49.7–9940 GeV in different places.
5. **DM4:** "five pairs differ by more than 0.15σ" lists four items. The
   stated 0.4σ scatter between identical models sits beside a 0.5σ example.
6. **DM6's halo sensitivity:** the record says "36-fold" and "4.9 times";
   the write-up notes say "factors of 5 to over 100" (the results file
   supports ×4.9 to ×130).
7. **DM7:** Ωh² low "by up to a factor 14" holds for V1 only (A1 and V2 reach
   factors of 16 and 18). The failures are "≤ 8.4 GeV" in one place and
   "below 8.4 GeV" in another.
8. **DM8:** the g* example's Ωh² is 2.02 in the record and 2.03 in
   `crosscheck.txt`. The DMsimp value 1.80 is in no results file.
9. **The write-up notes:** digitised curves match "to about 1%", but the
   DM3 table has a 2.4% gap (PICO-60) and a 0.3 keV gap (LZ's lower 50%
   point).
10. **Milestone dates** differ between the build plan and some records (DM7,
    DM8, DM9).
11. **DM8's final check 4** ("the owner's review") has no recorded
    completion.

## 5. What is left for the owner

- **The paper:** read, revise and decide its framing, title, affiliation and
  venue.
- **ADROIT's own licence,** before any public release. The repository has
  none yet; the external tools keep theirs and are never bundled.
- **The audit items above.**
- **Optionally, completing GPT's held-out baseline** (43 cases, about $3)
  after topping up the OpenAI account. The gate is not re-applied.

## 6. How to run

```bash
uv run adroit setup                       # every external tool and data set, and its licence
uv run adroit setup --fetch               # fetch (and build) what is missing
uv run adroit workbench                   # http://127.0.0.1:8765
```
