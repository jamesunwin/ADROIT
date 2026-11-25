# DM14: Track 2 made general, and recursion

Started 2026-10-03. The owner's design is in the build plan ("The dual-track
system"). This record covers what was built, the gate (declared in section 6
before its first run) and its result.

## 1. Anomaly intake (`experiments/anomaly.py`, `agents/anomaly.py`, `adroit anomaly`)

- **The record.** Any search that reports its events is one YAML file in the
  schema of DM10's historical searches (`AnomalyRecord`):
  - the target, exposure and energy window;
  - the event energies and the resolution;
  - the expected background, with its uncertainties by source;
  - the efficiency, in exactly one of three forms: points from the text, a
    digitised figure in the package, or a digitiser's two-column CSV beside
    the record;
  - the halo;
  - `sources` (where each number is in the paper) and `verified_by`.

  `adroit anomaly template` writes a blank one, every field explained.
- **The check** (`adroit anomaly check`), before any fit:
  - events outside the window;
  - an efficiency outside [0, 1], decreasing energies, or a curve that
    misses the window;
  - an unknown target;
  - a resolution wider than half the window;
  - a downward background error larger than the background;
  - a halo outside plausible ranges (v₀ 150–300 km/s, v_esc 400–700 km/s,
    ρ 0.2–0.6 GeV/cm³);
  - no references.
- **As a module.** `RecordSearch` makes any record an experiment module.
  Path 2 loads it as `record:<path>`, so a new anomaly is a new file, not
  new code. A record with no `verified_by` is a draft: Path 2 refuses it
  unless asked (`--unverified`).
- **The drafter** (`adroit anomaly draft --arxiv ID --budget`; a language
  model, opt-in):
  - it reads the paper's full text and drafts the record, quoting the
    sentence each number comes from;
  - it never computes or invents a number;
  - every quote is checked against the text (up to whitespace and case), and
    an unfound quote goes on the record's `needs_person` list;
  - a required number the text does not give is left out, so the file does
    not load until a person supplies it;
  - the efficiency, usually a figure, is left for a person to digitise.

## 2. Users' models as candidates (`orchestrator/user_models.py`, `signal.py`)

- A typed model (DM8 or DM12) enters Path 2 as one candidate per dark matter
  mass (`--model m.yaml`, beside the library with `--with-library`). Its
  nucleon-level interaction comes from its DM13 class, or else from its DM8
  derivation through DirectDM. A model with neither is refused, with the
  reason.
- One strength μ scales every NR coefficient, as for a card, so μ̂ = 1 means the
  model's stated couplings explain the events. Variants and the scout skip
  or describe a user's candidate by its model, since it is not in the card
  graph.

## 3. The single-idea report (`orchestrator/single_idea.py`, `adroit single-idea`)

One user's model as the explanation of one anomaly:
1. **The fit** at each mass, with the global significance over the masses
   from background-only toys.
2. **The tension with the null experiments** at the best mass (Path 2's
   combination and its parameter-goodness-of-fit).
3. **The best-fit band.** Solve the model's actual NR coefficients for
   `g_chi`, holding physical masses and other couplings fixed. The branch has
   the input coupling's sign and `|g_chi| <= sqrt(4*pi)`. No universal
   mediator-mass power law is used. Verify the full predicted recoil spectrum
   (relative error <= 1e-6) and profile log likelihood (absolute error <= 1e-6).
   Unsupported, degenerate and out-of-domain inversions are explicit.
   - Every constraint is evaluated at the physical fitted point.
   - Thermal intersections are refined with the relic solver, re-fitting the
     anomaly at each trial mass; the relative relic residual must be <= 1%.
     Failed mass points are never bridged when making brackets.
4. **Track 1 on a window around the band:** the plane with the band drawn on
   it, the relic contour's verdict and the literature.

The verdict is one of:
- NO FIT (local Z < 1 at every mass);
- RESOLVED THERMAL EXPLANATIONS EXCLUDED (all certified intersections with local Z >= 1 are excluded);
- A VIABLE THERMAL EXPLANATION, with or without pending constraints;
- NO RESOLVED THERMAL EXPLANATION (none at the searched masses/resolution);
- UNDETERMINED (unsupported physical inversion or incomplete thermal calculation).

Fit quality, constraint compatibility (of the band's eligible fitted masses:
viable where any is; the report gives the best resolved fit's own status beside
it, AL3-23) and thermal viability are separate machine-readable fields. Promotion and the workbench retain the
thermal headline. A compatible fit at the wrong relic density cannot imply
thermal viability. Track 2 omits out-of-validation-range nulls with explicit
coverage reasons, and mass identities retain their full precision.

## 4. Studies and recursion (`orchestrator/studies.py`, `promote.py`, `adroit promote`, `adroit studies`)

- **Every run writes `study.json`:** its kind, title, inputs, steps, cost,
  outputs, parent and children. `adroit studies` prints the tree with the
  total spent.
- **Promotion.** `adroit promote RUN class:N` (or labels) turns Path 2
  candidates into studies inside the run's `children/`:
  - a user's candidate becomes its own model's single-idea study;
  - a library card becomes the single-idea studies of the simplified models
    that produce it at tree level (`parameter_space/simplified.py`):
    - O1 → vector or scalar mediator;
    - O4 and L15 → axial;
    - L1–L4 and the mediator cards → the scalar mediators with
      scalar/pseudoscalar couplings.

    Isovector candidates have none of these, and the report says so.
  - with `--budget`, DM12's model builder also proposes renormalizable
    completions. Their idea study is a child too. Those DM13 can compute get
    single-idea studies, and the rest are listed with the reason.

## 5. What is not yet built

- **Anomaly records:** background shapes from a user's CSV. The records use
  digitised shapes in the package only.
- **The historical records** use the Helm form factor only. They see no
  spin-dependent scattering, so an SD candidate has no signal in them.
- **Recursion below a single-idea study.** A child is a folder like any
  other, but its promotion would need a Path 2 run of its own.

## 6. The gate (declared 2026-10-03, before its first run)

Run by `docs/dm14/gate.py`. G1–G4 cost $0. G5 calls a language model, up to
$1 of the day's approved budget.

- **G1: intake.**
  - (a) Both historical records pass the check with no problem.
  - (b) Eight seeded errors in the template are each caught.
  - (c) The CDMS II Si record re-entered as a user's file (its efficiency as
    a digitiser's CSV) gives the built-in module's Path 2 fit of O1
    (isoscalar) at 5, 10 and 20 GeV: ŝ and the local Z within 0.1%.
  - (d) Path 2 refuses the file when `verified_by` is empty, and runs on it
    with `unverified_records`.
- **G2: users' models.** On CDMS II Si, the vector-mediator and
  scalar-mediator models as users' candidates at 5, 10, 20 and 50 GeV have
  the local Z of the library's O1 (isoscalar) at the same masses within
  0.01. Each falls in O1's degeneracy class.
- **G3: a single idea against the literature.** CDMS II Si with the vector
  mediator (g_χ = 1, g_q = 0.25) over m_χ = 5–40 GeV:
  - (a) the best-fit mass is within 7–11 GeV (the collaboration's best fit:
    8.6 GeV);
  - (b) the eleven resolved physical fits retain the 1000 GeV mediator, reproduce
    the fitted spectrum/likelihood and are all direct-detection-excluded. The
    5 GeV fit is outside the perturbative g_χ branch and explicitly pending.
    Fit compatibility and thermal viability remain separate; incomplete physical
    and thermal coverage yields UNDETERMINED, not a global exclusion claim;
  - (c) the report states thermal viability and the missing physical/thermal calculation.

The G3(b/c) expectations were corrected on 2026-10-05 after a fresh original
12-mass, 20,000-toy, 16×16 run exposed the old mediator-rescaling assumption
(F10/F11). No point, exclusion, grid, toy count or numerical tolerance was
changed. The original failed assertion is retained in the local remediation
ledger; the historical results below describe the earlier implementation.
- **G4: recursion.**
  - The setup: a Path 2 run on CDMS II Si over O1, L1 and M_vector,
    isoscalar and isovector, at 5, 10 and 20 GeV.
  - Promoting the leader's degeneracy class gives a single-idea study for
    each computable completion of its members, each inside the run's
    `children/`.
  - Each child's `study.json` names the run, and the run's lists them all.
  - `studies.tree` puts them one level below the run.
  - Every isovector member is listed without a study, with the reason.
- **G5: the drafter (live).** From the full text of arXiv:1304.4279, the draft
  record has:
  - the verified record's target, exposure, window, three event energies
    and background count;
  - the efficiency listed for a person;
  - an empty `verified_by`;
  - every quote found in the text, or flagged.

## 7. The gate's result (2026-10-03): passed, 5 of 5, $0.08

Record in the live gate's record (dm14) and `gate_live.json`; the single-idea study
is in `docs/dm14/single_idea_vector_cdms_si/`, and the promoted tree in
`docs/dm14/recursion/`.

**Two runs stopped before the result, both in the gate script.**
- **First run:** it stopped in G4's setup. The declaration listed M_vector
  among the Path 2 candidates, but mediator cards have no isospin variants
  and are not in Path 2's space. G4 now uses O1 and L1 only. This was
  changed after the first run, and the script says so where it builds the
  candidates.
- **Second run:** the drafter's paper fetch called a method the installed
  arXiv library no longer has. The fetch now downloads the PDF directly.
- **What was rerun:** the second run's G1–G3 results were kept (the script now
  saves each part as it ends), and G4 and G5 were rerun. Nothing in G1–G3
  depends on either change.

- **G1: passed.**
  - (a) Neither historical record has a problem.
  - (b) All eight seeded errors are caught.
  - (c) The user's copy of CDMS II Si gives identical ŝ and local Z
    (1.61, 2.99, 2.25 at 5, 10, 20 GeV).
  - (d) Path 2 refuses the unverified copy, and runs on it when asked.
- **G2: passed.** The vector- and scalar-mediator models as users' candidates
  match O1 (isoscalar) at 5, 10, 20 and 50 GeV to within ΔZ = 0.001, and
  fall in O1's degeneracy class.
- **G3: passed.**
  - (a) The best fit is m_χ = 8.8 GeV (the collaboration's: 8.6 GeV).
  - (b) EXCLUDED AS THE EXPLANATION: direct detection excludes all 12
    fitted points of the band.
  - (c) The report says the band never meets the thermal-relic contour. Along
    the band Ωh² is 1.5–90, so with g_χ = 1 and g_q = 0.25 the model would
    overclose the Universe.
- **G4: passed.**
  - The leader (O1v at 10 GeV) shares its class with O1s, L1s and L1v.
  - Promoting the class gave three single-idea studies: the vector and scalar
    completions of O1, and the scalar completion of L1. All three are
    EXCLUDED AS THE EXPLANATION.
  - Each names the run as its parent, the run lists all three, and the tree
    puts them one level below it.
  - The two isovector members are listed without a study, with the reason.
- **G5: passed** ($0.08).
  - From the paper's full text, the drafter gave the verified record's
    target, exposure (140.2 kg·days), window (7–100 keV), events (8.2, 9.5,
    12.3 keV) and background (0.41 events).
  - It also gave the background uncertainties by source and the halo.
  - It listed the efficiency for a person (Fig. 1), and left `verified_by`
    empty.
  - Every quote was found in the text.

After the run, study records were changed to store their parent and children
relative to their own folder, so a tree of studies can move. The gate's
records were converted to that form. This changed the format only.

## Bounded physical fitting, 2026-10-07

The existing one-coupling physical band now has a direct likelihood fallback.
A typed model may declare `physical_fit: {parameter: g_chi, low: 0, high: 0.02}`;
then its actual recoil likelihood is fitted over that range at fixed masses and
other couplings. Without a declaration, successful inversions remain unchanged
and failed inversions use the original-sign perturbative branch. Boundary hits,
missing regions, disconnected likelihood regions and ambiguous modes are retained.
Single-idea studies and promotion preserve the range. The constrained physical
fit and its screening statistic are separated from the existing unconstrained
amplitude/global and null-comparison reference calculations. See
[bounded_physical_fitting.md](bounded_physical_fitting.md) for controls, validation
and statistical limits. Historical results above describe their original code.
