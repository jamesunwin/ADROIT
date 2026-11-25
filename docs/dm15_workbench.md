# DM15: the workbench for the two tracks (NiceGUI)

Started 2026-10-03. The owner's decision was NiceGUI, taking what can be taken
from the inherited workbench (tag `pre-retirement`). This record covers what
was built, the gate (declared in section 5 before its new parts were run)
and its result.

## 1. What was taken, and what was rebuilt

The inherited workbench (`adroit/ui/` at `pre-retirement`, about 1,500 lines)
served the retired pipeline: projects, a problem YAML, the old stages and its
gate channel. None of that exists in ADROIT now. **Taken:**
- **The design:**
  - runs are subprocesses of the ordinary command line, controlled through
    files;
  - pages are registered by a function, so tests mount them on a temporary
    directory;
  - the app listens on 127.0.0.1 only;
  - the live view refreshes every second.
- **The test setup:** NiceGUI's headless User fixture, with pytest-asyncio in
  auto mode and no main file.

**Rebuilt** for the two tracks, at about 800 lines (an estimate of 650 stood
here when the gate was declared):
- the engine;
- the forms;
- the pages and wizards.

Rebuilding was smaller than porting, because every screen's data model
changed.

## 2. Runs through files (`ui/engine.py`, `ui/runner.py`)

1. **The launch** runs in a folder of its own: `forms.new_folder` creates it
   (kind, title, time and a random suffix) with an exclusive create, so two
   launches in one second never share one (the re-audit's R18-3). It writes
   `job.json` (the command, the budget the person confirmed, and the status)
   with an exclusive create too: a folder that already holds a job is
   refused. Only **Resume** restarts an existing job: an interrupted Track 1
   run, under the same folder, title and budget.
2. **The runner** starts detached, in its own process group, at `nice` 10. It
   runs `adroit <command>` with its output in `log.txt`, and writes the final
   status and exit code. A run therefore outlives the workbench.
3. **Cancel** writes `control.json` and sends SIGTERM to the group. The runner
   ends the command and records "cancelled".
4. **Spend** is the study's recorded cost, or the command line's last
   "spent $x".

A command with `--budget` is refused unless the person confirmed at least
that amount.

## 3. Forms and wizards (`ui/forms.py`, `ui/wizards.py`)

- **Forms** are pure (no interface code) and unit-tested. Every wizard ends in
  one command-line call, so the workbench and the command line run the same
  code.
- **The typed gates:**
  - *a budget*: an amount of at most $10 (the owner's daily testing budget)
    and a ticked approval, before any paid run;
  - *a model list*: of the models the builder proposed, only those the audit
    found valid can be approved for Track 1. Each approved model is written
    as YAML and scanned as a child study; its couplings need values before
    the scan can compute it, and its report says so;
  - *a promotion*: a Path 2 candidate or its degeneracy class becomes
    studies, optionally with the model builder behind the budget gate.
- **Wizards:**
  - Track 1: a field content, a Lagrangian, an idea in words (paid), or a
    typed model to scan;
  - Track 2: a built-in search or an anomaly record, the library and/or the
    user's models;
  - Single idea;
  - Anomaly record (in the menu since 2026-10-13: Add a signal): the template, the check, and the drafter (paid).

## 4. Pages (`ui/pages.py`, `ui/app.py`, `adroit workbench`)

- **Studies** (`/`): the tree of studies with costs and the total spent,
  what is running, and runs that ended without a study.
- **Live** (`/live`): status, time, spend against the confirmed budget, the
  command, the log, Cancel, and a link to the results.
- **A study** (`/study`):
  - its report, with its plots served from the runs directory;
  - its parent and children;
  - for a Path 2 run, the ranking and the promote form (recursion);
  - for an idea, the approval form.
- **Safety:**
  - a path outside the runs directory is refused;
  - `adroit workbench` serves on 127.0.0.1 only.

  DM11's page remains as `adroit workbench --classic`.

## 5. The gate (declared 2026-10-03)

Run by `docs/dm15/gate.py`. G1–G4 are the workbench's own tests: they were
written and run during development, before this declaration, and the gate
reruns them unchanged. G5 and G6 are new and have not been run. G6 calls a
language model, up to $1 of the day's approved budget.

- **G1: the pages** (`tests/ui/test_workbench.py`). On a runs directory holding
  DM14's promoted tree, a Track 1 study, an idea study and a failed run, all
  of the following render headless:
  - the home tree;
  - a Path 2 study with its promote form and children;
  - a child linking to its parent, with its report;
  - an idea study's approval form;
  - the failed run's live view with its log;
  - all four wizards.

  The plots are served from the runs directory, and a path outside it is
  refused.
- **G2: the commands.** Every command a wizard writes uses only options the
  command line declares (eight commands).
- **G3: runs through files.**
  - A Track 1 run launched by the engine completes as a subprocess, with its
    report and study record.
  - A long run is cancelled within 30 s, recorded as cancelled, with no
    process left.
- **G4: the gates.**
  - A paid command is refused without a confirmed budget at least its own.
  - The budget form refuses an empty amount, zero, more than $10, and an
    unticked approval.
  - Only valid models can be approved.
- **G5: the served app.** `adroit workbench --no-browser` started on a copy of
  G1's runs directory:
  - listens on 127.0.0.1;
  - answers 200 for the home page, a study page, a wizard and a plot under
    `/files/`;
  - serves no file outside the runs directory.
- **G6: a paid recursion through the engine (live).** On DM14's Path 2 run:
  - the promote command with the model builder, launched by the engine with
    a confirmed $1, completes;
  - the builder's proposals are a child idea study, its cost recorded and
    above zero;
  - every proposal is either studied or listed with the reason it is not;
  - the studies tree's total spent equals the cost the run reports.

## 6. The gate's result (2026-10-03): passed, 6 of 6, $0.06

Run once, as declared; record in the live gate's record (dm15) and `gate_live.json`.

- **G1–G4: passed.** The workbench's own tests passed on the rerun:
  - G1: 8 page tests;
  - G2: 8 commands;
  - G3: the completed run, and the cancel;
  - G4: 3 gate tests.
- **G5: passed.** The served app:
  - listens on 127.0.0.1 only;
  - answers 200 for the home page, a study, a wizard and a plot;
  - returns 404 for two attempts to read `/etc/passwd` through `/files/`.
- **G6: passed** ($0.06). Promoting O1 (isoscalar, 10 GeV) with the model
  builder through the engine completed:
  - the two simplified completions were studied;
  - the builder's three proposals form one idea study, costing $0.06;
  - the tree's total equals the run's reported spend.

**The finding from G6.** None of the builder's three proposals is
computable by DM13, and each is listed with its reason:
- a singlet scalar mixing with the Higgs;
- a dark photon;
- Majorana dark matter with a coloured t-channel scalar.

These are the most common completions in the literature. DM13's classes
(an s-channel mediator with direct quark couplings, Dirac dark matter) do
not cover them. Higgs-portal mixing, kinetic mixing and t-channel mediators
are the natural next classes.
