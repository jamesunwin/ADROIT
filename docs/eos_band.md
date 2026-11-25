# The equation of state's band (the owner's decision #3, 2026-10-20)

> **ADROIT 1.0.0: the band is not assessed** (the owner's decision of 2026-11-23; `core.certificate.EOS_POLICY`).
>
> - **Unchanged:** Ωh² is computed with ADROIT's nominal equation of state, Saikawa & Shirai's 2018 fit
>   (`relic.degrees_of_freedom`), as before. It is not replaced by the 2020 central table.
> - **Decided on the nominal:** a thermal claim (a contour or coverage root, a theory-band point, a single-idea
>   thermal point, Path 2's eligibility, the complementary relic comparison) is decided on that nominal calculation.
> - **The band check:** its `eos_band` check is *not applicable*, with the reason `certificate.EOS_NOT_ASSESSED`. It is
>   never *satisfied*, and no claim is one of robustness across equations of state.
> - **The 2020 tables:** no claim reads or binds them, and they need not be installed for a verdict. The manifest
>   item stays, since a Majorana fermion's s-wave cross section (`S_2.dat`) comes from the same release.
> - **Deferred:** propagating the uncertainty is deferred to 1.0.2 (the deferred list, EOS-01), with the
>   bracket limitation of `verdict._eos_root` below.
> - **Every other check stays:** root convergence and the final relic recheck, the thermal history, the model's
>   domain, the records, the halo, discovery, coverage and the physical-fit checks.
> - **Policy identity:** it changed from `consistency-hd-2026-11-12` to `consistency-eos-nominal-2026-11-23`. Earlier
>   certificates read stale and are never re-assessed; their stored outcomes and table bindings stand.
> - **The machinery:** it is kept, and every producer asks `certificate.eos_band_assessed()`.
>   `certificate.EOS_BAND_ASSESSED` restores the band for its tests (`@pytest.mark.eos_band`) and for 1.0.2's work.
>   Nothing in the workbench or the command line sets it.
>
> The low-temperature comparison (`relic.low_temperature_history`) now keeps the equation of state in force above
> 1 MeV and changes only the history below it. It had substituted the nominal above 1 MeV too, so with a table in
> force it attributed the change of table to the history below 1 MeV. The repair is shown by a synthetic control, a
> false 20% warning that is gone (`tests/constraints/test_low_temperature_comparison.py`). The B−L run's band
> recalculations (2026-11-22) were not run again, so how much of their reported 5–6% thermal-history sensitivity was
> spurious is not known.
>
> The rest of this document describes the band as it is assessed when `EOS_BAND_ASSESSED` is set.

The owner's decision: propagate Saikawa & Shirai's central, upper and lower tables; keep the nominal result; mark
EOS-sensitive points pending; keep the solver's error and Planck's uncertainty separate.

## The tables

Saikawa & Shirai's 2020 data release (arXiv:2005.03544; member.ipmu.jp/satoshi.shirai/DM2020/), as published
(columns T in GeV, g*s, g*ρ; 529 rows from T = 0 to 1.47 × 10⁶ GeV), each checked against its sha256 when read
(`relic.EOS_TABLES`, `eos_table`). **Fetched, not shipped** (the release audit's PR23-05; the owner's decision,
2026-10-23): the authors' page states no licence or redistribution terms, as for their 2018 tables
(`docs/relic_low_mass.md`), so `adroit setup --fetch` downloads them into the tools folder (the manifest's
"Saikawa-Shirai relic cross sections (DM2020)", a required item). Without them the band is not computed and a decided
result waits for it, pending with the setup command (`relic.eos_unavailable`, `verdict._eos_missing`); nothing is
decided on the nominal alone. The files fetched on 2026-10-23 are byte-identical to the ones the band was built and
studied with (until then shipped as `adroit/constraints/data/eos/ss2020_*.dat`):

| the authors' file | the band's | sha256 |
|---|---|---|
| `eos2020.dat` | central | `c2a8429a…` |
| `eos2020_err1.dat` | upper (the upper edge of g*) | `9fc0c404…` |
| `eos2020_err2.dat` | lower (the lower edge) | `14e83e7b…` |

ADROIT's nominal stays the 2018 paper's fitting functions (`relic.degrees_of_freedom`, arXiv:1803.01038 App. C). At
the 256 R3 crossings the 2020 central table moves Ωh² by −0.85% to +0.40% (median −0.14%) from it; the upper table by
−5.5% to −1% and the lower by +1% to +6.5% from the central (median ∓4%, largest near the QCD transition: the study,
2026-10-20). Every library family's relic responds to the table.

## The band on the thermal contour (`verdict._eos_band`)

- A decided crossing (viable or excluded) is judged again at its root refound with the upper and with the lower table,
  on the same grid bracket (`_eos_root`: `thermal.refine` inside `relic.eos_variant`; the point is then judged inside
  the table too, so its Ωh² and everything reading it are that table's).
- The same status at all three roots: it stands, and its flags note the two roots, as the result at the two supplied
  tables, not of every equation of state between them (below).
- Otherwise it is pending, **EOS-sensitive**, with the three statuses, the two roots and the constraints that differ.
  A bracket that holds no root of a table (a grid value within the band of the target) leaves it pending with that
  reason.
- At the request's target only. The O(1)-disagreement checks at other targets (`_across`, `_beyond`, D35) are not
  repeated per table. A pending crossing is not judged again. Every root a verdict judges carries its cell
  (`ThermalRoot.bracket`, left out of its JSON when absent): the plane's (`_thermal_roots`) and the optional coverage
  diagnostic's (`coverage._roots`), which are refined between its finer grid's points and judged across the band in
  the same way. A decided root without one is pending, the band not computable, never decided on the nominal alone
  (the consistency audit's CA-01, 2026-10-24: the coverage diagnostic's roots, carrying no cell, had been taken for
  roots of a result written before the band and decided viable without the tables).
- The cost: two root refinements and two judgements per decided crossing. Grid points are not tripled.
- Kept apart: the solver's tolerance (the root's 1% acceptance) and Planck's measurement (the likelihood mode); the
  micrOMEGAs DHS comparison stays a cross-check.
- **Without the tables** (`relic.band_unavailable`), every decided thermal result waits for them, pending with what
  to do: the contour's roots, the coverage diagnostic's, and the combined mode's theory-band points, which are nominal
  grid points within the band of the relic target (`_awaiting_eos`; the combined audit's V1-01, 2026-10-24: the band
  points had decided the combined headline viable). **A table that is present but cannot be read, or is not the table
  as published** (each file is checked against its published sha256, `relic.eos_unavailable`), counts as missing,
  naming the file to delete and fetch again (CA-01: a plane root had raised on it, while the band points and the
  coverage roots, which checked only that the folder existed, decided). With the tables, the band points are judged
  as before, on the nominal degrees of freedom; the band is not recomputed with each table (its width is the combined
  mode's relic theory uncertainty, 10% of Ωh²; the owner's direction D-1 of 2026-10-25, to check them across the
  tables at the same parameters, belongs to the consolidation plan's M1).
- **The same certification wherever the thermal claim is made** (the consistency audit's CA-02, 2026-10-24: with the
  tables missing, Path 2's physical eligibility called a fitted point at the target eligible, and the complementary
  relic comparison allowed Ωh² = 0.12 and excluded 0.13, where the plane's roots wait):
  - **Path 2's physical eligibility** (`physical_eligibility._eos_band`): the fit fixes the point, so its Ωh² is
    computed there with each table. At the declared target (to 1%) with all three, it stands, the band among its
    assumptions; otherwise, or without the tables, it is pending: "nominal Ωh² is at the target; thermal eligibility
    across the supplied tables is not established", with the values or what to do. An experimental exclusion at the
    point does not depend on the tables and stands. At low masses, where the tables move Ωh² by more than 1%, most
    points read "not established"; a shifted thermal solution, refitted, is the plan's M1.
  - **The complementary relic comparison** (DM7, `verdicts._relic_band`): overabundance excludes where the comparison
    with the ceiling is the same with the nominal degrees of freedom and with both tables; otherwise it needs a
    calculation, EOS-sensitive, and without the tables it waits, with what to do. A density that is not a finite,
    nonnegative number decides nothing (CA-03).

**Roots a table adds** (`_eos_new_roots`). A table can create a thermal root where the nominal degrees of freedom
have none. The grid edges holding no nominal root (nor a nominal bracket left unrefined) whose Ωh² range meets the
targets a table can move onto the target, within the declared bound `EOS_SHIFT_BOUND` = 10% (the 256 crossings' shifts
lie within −5.5% and +6.5%), are solved with each table at both ends; a bracketed root is refined and judged inside the
table. A rootless verdict (over- or underabundant) with such a root is pending, EOS-sensitive; so is an all-excluded
verdict where such a root is viable or undecided. A viable verdict is not changed by them (one viable root suffices).
A table that moves Ωh² beyond the bound at a searched point is reported, the search being then incomplete.

**What the band claims, and what it does not** (the auditor's recheck, RB20-07, 2026-10-20). The check is of the owner's
three tables: the nominal, the upper and the lower. Agreement at their roots does not establish the status of every
equation of state between them: an exclusion confined to a narrow coupling interval between two sampled roots can meet
the root of an intermediate table. The flag says so. A stronger method, for the owner to choose if wanted: interpolated
tables (t = ±½) as further scenarios, or every constraint checked across the coupling interval the band's roots span.

Everything cached that the table moves is keyed on it (`relic.current_eos`): the generic route's and the t-channel's
x_f (`generic._freeze_out`, `tchannel._freeze_out_x`). Ωh² itself is not cached by point.

## Gates

- `tests/constraints/test_eos_band.py`: the three files are the published ones, a changed one refused; the label
  follows the table and is restored; a library relic (DMWG V1) moved as the study found (upper −1 to −6%, lower +1 to
  +7%, central within 1%); the generic route's x_f cached per table.
- `tests/parameter_space/test_eos_verdict.py`: a toy whose roots sit at m_χ = 20, 20.83 and 19.23 GeV under the three
  tables; a constraint excluding above 20.5 GeV leaves its crossings pending, EOS-sensitive, naming it; one at 25 or
  15 GeV leaves them viable or excluded with the band noted; the band absent at other targets and for a root without
  its bracket.
- The method gate, the recheck's two analytic cases (`test_eos_verdict.py`): Ωh² = 0.12(1 − 0.04t)/g² with an
  exclusion for 1.009 < g < 1.011 between the sampled roots is viable with the flag stating the two-table scope;
  Ωh² = 0.121 + 0.04(g − 1)² − 0.004t, with no nominal root and two roots of the upper table (g = 0.726, 1.274), is
  pending, EOS-sensitive, both roots named.

## What it changes

Each decided R3 crossing (204: 194 excluded, 10 viable; the halo verdict study's, with each experiment's published
halo and verified records) judged at its point and at its root refound with the upper and lower tables, the point's
own Ωh² the target (the scratch `d3/eos_verdict_study.py`, along g_χ within ×0.8–1.25, then along m_χ within ±10%
where g_χ did not hold the root):
- **201 unchanged** at both tables' roots; the roots move by −18% to +11% in g_χ (most by 1–2%; more where Ωh²
  depends weakly on g_χ). Every nominal status reproduces the receipt's.
- **higgs_portal_dirac_cpv #9**: its Ωh² hardly depends on g_χ; along m_χ the roots are 1.5% away and still excluded.
- **inert_doublet #2 and #5 become pending, EOS-sensitive**: at 1.3 TeV they sit on a narrow ridge, Ωh² peaking at
  0.1236 and falling twentyfold within ±3% in m_χ; the upper table lowers the peak to 0.1197, below the target, so
  its root disappears, while the lower table's peak, 0.1279, has two. A root that vanishes under a supplied table is
  the branch the recheck's RB20-07 described, met in a library model: the band leaves it pending ("the root with the
  equation of state's upper table is not in its grid cell"). Both were excluded by direct detection at the nominal
  root; with no thermal solution in that cell under the upper table, the excluded thermal solution is not established
  for every supplied table, so the crossing is pending rather than excluded.
- No viable crossing changes.

The fast suite: 3,200 passed with the band, its one count-of-judgements test now leaving the band out.

## The single-idea workflow (C21-07, 2026-10-21)

The candidate audit found the single-idea headline reading the nominal table alone: its fitted band's thermal points
are refined by the workflow itself, not taken from the plane, so a point the plane gave as pending, EOS-sensitive, was
headlined "a certified thermal intersection fits the anomaly". The same rule now applies to the fitted band
(`single_idea._eos_band`, `_eos_level`):

- With each table the band's Ωh² is computed again at the fitted points, and its thermal points refound and judged
  inside the table (the fits do not depend on it).
- A decided nominal point stands where both tables give a point between the same fitted masses that keeps it: for a
  viable one, a viable point that also fits the anomaly (the recheck's RC21-03, 2026-10-22: a table's point below the
  anomaly-fit criterion had supported viability); for an excluded one, an excluded point or one that definitively
  fails the fit (an unresolved, unidentifiable or range-edge fit decides nothing). Otherwise it is pending,
  EOS-sensitive, with the three statuses and the tables' fits (the headline then "pending a calculation", as the
  plane's).
- A point a table has between fitted masses where the nominal has none, unless it definitively fails the fit: a
  headline without a thermal point is then undetermined, EOS-sensitive, and so is an all-excluded one where that point
  is viable or pending; a viable headline is not changed by it.
- A table's unresolved bracket (its refinement failed) could hold a viable explanation: an all-excluded or
  no-thermal headline is then undetermined, and the saved result's `thermal_pending` keeps it, "the <table> table:
  <reason>" (RC21-04: they had been dropped).
- An excluded point keeps an exclusion only if its fit is eligible (or definitively poor): a table's excluded point
  whose bounded physical fit sits at its range's edge, or is unresolved or unidentifiable, decides nothing, since an
  explanation beyond it is neither found nor excluded; the nominal point is then pending, and a table-only excluded
  point of that kind leaves an all-excluded headline undetermined (the re-audit's RR22-03, 2026-10-22).
- The cost: the band's Ωh² twice more, and each table's root refinements and judgements.
- **A fit the study made speaks for the fit** (the third re-audit's RX22-04, 2026-10-22). "No fit" is decided over
  every fit evaluated: the fitted band's and its certified thermal points', each refitted at its own mass (`_fits`).
  A band fitted at 10 and 30 GeV alone (Z = 0.26) had said "no fit" over a root at 20 GeV refitted to Z = 2, viable at
  all three tables. A table's point whose own fit is not definitively poor leaves a "no fit" headline undetermined,
  EOS-sensitive, its reason saved in `thermal_pending`.

**The plane's tables, the same discipline** (RX22-03, RX22-05, 2026-10-22). On the plane, a table's root exactly at a
grid node is a root (the strict sign change had skipped it, so a rootless grid read overabundant), found once per
node; a table whose Ωh² cannot be computed at an edge's end is reported, the search incomplete, not skipped; and
every table's root, refound for a nominal root, newly found or read from a checkpoint, has its own Ωh², evaluated
again with the constraints, within 1% of the target, as the nominal root (`_recertified`), else it is pending with
that reason and decides nothing.

**One reading of the fits** (the fourth re-audit's RY23-02 and RY23-03, 2026-10-23). The headline's "no fit" and
the saved fit quality are one reduction, `single_idea._fit_verdict`, over every fit the study evaluated, each by
its state (`_fit_state`): one that meets the criterion fits; "no fit" only where every one is definitively below it
(a bounded fit held at its range's edge counts so only with √q0 < 1 there, the release audit's rule); a fit with
no finite statistic, unresolved, unidentifiable or at its edge with √q0 ≥ 1 leaves it undetermined, its reason saved
in `thermal_pending` (a missing statistic had read as Z < 1). The fit quality also reads the tables' refitted
thermal points, saved in the result as `eos_thermal` and its evidence summary: a table's point refitted to Z = 2 is
"fits" while the thermal headline stays undetermined (it had been saved as "no_fit").

**A fit's state, never its bare number** (RZ23-01, RZ23-02, 2026-10-23). A thermal point is accepted only by its
fit's state (`_eligible`: an infinite statistic had passed Z ≥ 1 and certified a viable headline); a certified thermal
point whose fit is undecided (no finite statistic, unresolved, unidentifiable, at its edge with √q0 ≥ 1) keeps a
headline without an eligible viable point undetermined, its reason saved. The evidence reads a result's NaN as NaN:
its summary and copies are compared as canonical JSON (`evidence.results._canonical`), so an unchanged pending result
with a NaN fit reads back, and a changed one is still refused.
