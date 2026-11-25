# Inspecting and exporting results in the workbench

Four tools make a saved analysis easier to inspect and act on (the plan and its record:
the workbench inspection plan of 2026-10-18). All of them read what is
already saved: nothing is recalculated, no language model is asked and nothing is fetched. A value that was not
calculated is shown, and exported, as missing with its reason, never as zero.

## Explain a point

On a Track 1, Explain a signal or Signal best fits study page, **Explain a point** lists every point of the study:
Track 1's grid samples, its thermal roots and theory-band points; Explain a signal's fitted masses, thermal points and
its Track 1 plane; Signal best fits' physical candidates. Search it, filter it by status, or click a point on the
interactive plane above the table. A point's page shows:

- its coordinates (with units) and, for a thermal root, its target and residual;
- what was calculated there (Ωh² and its validity, the direct-detection prediction, the theory certificates);
- every constraint, **excluded**, **pending** or **allowed**, with the prediction, the limit, their ratio, units, the
  native and required confidence levels, the construction, the source and its review state. The numbers are those of
  this point's own saved evaluation (a grid sample and a refined root at the same coordinates are different
  evaluations). Where a comparison saved only the prediction/limit ratio, the ratio is shown and the limit is missing;
  direct detection shows its saved σ and limit in cm², the invisible widths their saved prediction and the bound the
  run used (a selected personal limit where it replaced the standard record);
- a grid sample's status is classified from its saved comparisons and the model's own pending reasons saved with
  them; for a model that names such reasons (the portal models and the generic route), a result saved before they
  were kept (2026-10-19) shows its point as pending on them ("not saved with this evaluation") rather than calling
  the model again;
- a study that pinned a constraint-discovery assessment shows its unresolved requirements on every point they cover,
  in the table, the plane and the downloads, as its verdict does;
- for each pending item, why, and a link to the step that resolves it (a record awaiting verification, a personal
  addition, a constraint-discovery session, or `adroit setup` for a missing backend). A reason that names nothing
  ADROIT knows gets no link rather than a guess.

At the command line: `uv run adroit evidence point runs/STUDY` lists the points;
`uv run adroit evidence point runs/STUDY --point contour:0` explains one.

## Download from the study page

The study page's **Download** menu gives:

- **the evidence bundle** (the same as `adroit evidence export`, verified after it is written);
- **numerical tables**: `points.csv` (full precision; one row per point and observable, with units, status,
  confidence levels, construction, sources, review state and the pending reasons; an uncalculated value is an empty
  cell with a `calculation` column saying why), `points.json`, `points_numeric.csv` (numbers and status codes only,
  for Mathematica's `Import`) and `README.txt` (the columns and units);
- **figures**: the saved PNGs and the parameter plane (with Explain a signal's band) and direct detection redrawn as
  PDF and SVG from saved numbers only: direct detection shows the σ and limit saved with each relic-contour point;
  nothing is recalculated and no current limit is read;
- **references and the request**: `references.bib` (the entries `docs/dependencies.bib` has for the run's sources),
  `sources.txt` (every source the run used, with whether an entry was found; none is invented) and the exact request.

Each download is built in a temporary place; the study folder is never changed. At the command line:
`uv run adroit evidence tables runs/STUDY --out FOLDER` and `uv run adroit evidence figures runs/STUDY --out FOLDER`.

## The scan editor

In **Constrain a model**, once a model is entered or loaded, the setup appears as a table: one row per parameter with its
label, units, role (scanned on x or y, fixed from the model, derived with its relation, or unused by the engine),
range, spacing and number of points. Only the engine's own scan coordinates can be scanned; a derived parameter shows
its relation and cannot be scanned. An edit applies at once, and **Scan** runs the current valid setup (pressing it
accepts what is shown); an invalid table (a missing bound, for example) keeps Scan refused until it is corrected. The axis strings (`m_chi:10:1000:log:24`) and the setup's
YAML remain under **Advanced**. Reanalysing a Track 1 study shows the same table above its request, and an edit
rewrites the request's axes (an invalid table cannot be saved or run).

## The setup check

Above **Scan** (with the setup shown) and behind **Check setup ($0)** in Explain a signal and Signal best fits:

- **This analysis will use:** the engine and its physics, the scanned, fixed and derived parameters, the private
  limits and profile, the signal search, and the data sets found on this machine;
- **Missing:** a parameter without a value, a setup that is not the one shown, an unknown search, or a data set or executable this
  analysis needs that is not on this machine, each with its fix (a page or the exact `adroit setup` command); a
  blocking item stops the run;
- **May stay pending:** physics the route does not compute for this model, records awaiting verification, optional
  backends that are absent;
- **Size, duration and cost:** grid points, fits and toys; an estimate from comparable earlier studies of the same
  engine, stated with how many it rests on (or "duration unknown"); $0 for these runs.

The machine check knows which data sets and executables each kind of analysis needs from an explicit table; anything it
does not know is listed as "not checked", never as present.

## Advanced calculation options and the native fit

Explain a signal has a folded **Advanced calculation options** section with the command line's further options,
showing only what applies: the null experiments, the experimental profile and the cosmic-ray propagation model; the
bounded physical fit's resolution and evaluation cap (only when the model declares a physical-fit range); and a
native joint fit with DEAP-3600 (2019) or PICO-60 C3F8 (2019) (toys, seed, fit cap and an optional named domain).
Each says what its result means: the reported global significance stays the NR reference calculation; the bounded
physical √q0 is descriptive, not calibrated; the native q0 is calibrated by its own toys for that pair only.
**Native fit** (in the menu) runs `adroit native-fit`: shared bounded physical parameters fitted to a native pair
over a named domain, with profile likelihoods and no calibrated p-value.

## Activity and recovery

The menu's **Activity** link shows how many runs are running and how many recent ones need attention and have not
yet been seen on the Activity page: opening it clears that count, and a run that fails afterwards brings it back. The
activity page lists them as cards with what went wrong in plain words and the action that recovers it:

| what happened | the action |
|---|---|
| budget stopped (nothing beyond the cap was sent) | the cap command the run printed, then run again |
| a data set, tool or backend is missing | the exact `adroit setup` command |
| an input was refused | back to the form, or review the inputs in a reanalysis |
| interrupted (cancelled, or the process ended without a word) | Resume from the completed checkpoints (Track 1), else run again |
| failed otherwise | the log's last lines, and the run's form again to start over (nothing is guessed about the cause) |

Only a Constrain-a-model run that kept a checkpoint can be continued; the card of any other says so. A run that ended
without a study can be deleted (**Delete this run**, on its card and in the Studies page's "Runs that ended without a
study"): a window says what goes; nothing is deleted while it, or any run inside its folder, still runs, or has a
calculation that still runs after its run ended, or if it ran in a batch; and its paid-call records are kept. The full log is one click away on each run's live view.

## Projects, tags, favourites and notes

Each study page has **Label, project, tags and notes**: a display label, a project path ("Paper A / vector mediator /
final figures"), tags, a favourite flag and a short note. They are stored apart from the study
(`<runs>/.adroit/annotations.json`), so labelling or filing a study never changes its results, its evidence or any
path. The Studies page filters by text, project (with everything filed under it), tag, favourites, model revision,
dataset or profile, verdict and completion status.

## Known gaps

- The setup check of Explain a signal does not yet check every advanced selection (null experiments, a pinned profile,
  a native pair); the run itself refuses what it cannot use.
- **Prepare reanalysis with this update** opens the reanalysis with a hint naming the update; the update is chosen
  there, not pinned automatically.
- A cleared selection of null experiments means none (`--null ''`); leaving it untouched keeps the defaults.

## Studies to revisit after an update

**Studies to revisit** (linked from the Studies page) lists studies whose inputs have changed since they ran, each
with what actually changed: a newer revision of a personal model it used (the fields, couplings and terms that
differ), a constraint record whose content has changed since (field by field, from the run's evidence), a successor
of its profile (limits, signal or nulls added or removed), or a private limit explicitly superseded by a newer one.
**Prepare reanalysis with this update** opens the existing reanalysis, which pins the new input and keeps the old
result. Nothing reruns, and a newer input does not by itself make an old conclusion wrong.
