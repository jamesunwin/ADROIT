# After G12: a faster generic route, and the library's searches in it (plan, 2026-10-15)

The owner asked, after the closure audit, for a plan for two pieces of work (2026-10-15):
1. **make the generic route itself faster:** tabulate σ(s) once per model and interpolate across the scan grid, as
   MadGraph's process is now reused across points, so every model benefits, not only those that match the library;
2. **port the library-only searches into the generic route,** notably the resonance recasts, so that the "extra
   physics" gap closes for every model, not only exact matches.

Comparing generic models with the library (to switch engines when a model matches) is not pursued (the owner,
2026-10-15). Nothing here is built yet. Each part has a gate declared before it is run, and the zoo's held-out half
is not used to tune either.

## Part 1 — A faster generic route (milestones F1–F4)

**Where the time goes (to measure first).** A generic model is rebuilt from scratch at every point: G1's mass basis
(`spectrum.compute`), G2's rules (`feynman.feynman_rules`), G3's processes (`tree.Process`, one per initial pair and
final state), each σ(s) on 40–70 u nodes × 16 angles (`generic._table`), the thermal average, and G7's
long-range analysis. A Track 1 scan evaluates this at every grid point and again at every step of each thermal-root
refinement. The first step is a profile of three zoo models (a Higgs portal, a coannihilating singlet–doublet, an
electroweak triplet with the Sommerfeld effect) over a 4 × 4 scan, by stage.

**F1 — Structure once, numbers per point (the analogue of MadGraph's process reuse).** What a process is — its
diagrams, the vertices' Lorentz and colour structures, the propagators, the spin sums — depends on the model's
fields and terms, not on the values of its masses and couplings. Split each stage into a structure, built once per
model and cached by the model's content without its numbers, and a numerical evaluation per point:
- **G1:** the mass matrices are already polynomials in the couplings and vacuum values (`gauge_basis.Poly`); keep
  them, and only diagonalise per point;
- **G2:** keep each mass-basis vertex as its gauge-basis coupling contracted with the rotation matrices, evaluated
  per point;
- **G3:** build `tree.Process`'s diagram list and Lorentz structures once per (model, initial pair, final state),
  and evaluate them per point.

**F2 — σ(s) on the scan grid, vectorised.** Evaluate each process's amplitudes for all u nodes, angles and scan points
of a grid in one array pass (NumPy broadcasting over the point axis), instead of a Python loop per node. The nodes
are kept where they are physics, not numerics: in √s, an s-channel pole sits at the mediator's mass whatever m_χ
is, so pole nodes are shared across the m_χ axis; the initial and final thresholds move with the masses and keep
their own nodes.

**F3 — Interpolate across the grid where it is safe, and check it.** Between computed grid points, interpolate σ(√s)
in the masses only where the interpolant passes a declared check: at a fresh random point in each cell, the
interpolated and directly computed σ agree within 0.1% at every node, else the cell is refined. Never across a
threshold opening or a pole's crossing of a node (both are known in advance from the masses).

**F4 — Fewer evaluations per root.** The thermal root along m_χ is refined by bisection; a bracketed secant or Brent
step in log Ωh², with the same certificate (`verdict`'s root conditions), needs about a third of the evaluations.

**Gate (declared):** on a 4 × 4 scan of each of the three profiled models and of every development-half zoo model the
generic route computes,
- Ωh² within 0.1% of the direct path at every grid point and every root, and every verdict identical;
- the scan at least 5× faster in wall time on the development machine (`nice`, two threads), measured before and
  after;
- the full fast suite and the zoo's development half unchanged.

**The gate measured (2026-10-21/22), and the owner's decision.** Built: F2 in part and F4 (`db599c4`), and F1 for
MadGraph's production process only (`87daa2c`: couplings as external parameters, so the process is reused across a
scan); F1's structure caching and F3 are not built (the profile, the generic route profile record of 2026-10-19, put them at a
few percent and behind the off-shell integral and MadGraph). Measured on the 12 development-half zoo models the
generic route builds (each a 4 × 4 scan, or 16 points along m_χ where the model has no second coordinate), before
(`c920bf6`) and after (`87daa2c`), `nice`, two threads, two workers; the two runs shared the machine, with each other
and with release checks, for about ten waking hours. Script and outputs: `scratchpad/generic/speed_gate.py`,
`scratchpad/speedgate/`.
- **Ωh² and verdicts: met.** 155 grid values and 31 roots, the largest difference 3.7 × 10⁻⁵; every verdict (level and
  crossings' statuses) identical. The zoo's development half was unchanged within 2.8 × 10⁻⁵ when the speed-ups
  joined the generic route (CHANGELOG), and the fast suite passes at every later receipt.
- **Speed: 2.1× as recorded, 3.55× awake.** The script timed each scan with `time.time()`, which runs on while the
  laptop sleeps; the laptop slept, lid closed on battery, about 9.5 hours inside each run (`pmset -g log`). As
  recorded: 131 680 s → 61 559 s, 2.1×. With the sleep inside each model's scan removed: 97 267 s → 27 414 s,
  **3.55×**; by model, singlet–doublet 5.05×, singlet–triplet 3.76×, the vector Higgs portal 2.33×, Das et al.'s
  scalar mediator 2.60×, Giacchino et al.'s vector-like lepton 1.57×, doublet–triplet 1.68×, the six quick models
  0.8–2.1× (under 100 s each). Each scan's window
  is anchored on the MadGraph results it wrote first (`~/agentic-dm-tools/mg5-production`); the total does not depend
  on where the windows' edges fall, as every sleep lies inside one of the three slowest models in both runs
  (`scratchpad/speedgate/sleep_corrected.py`).
- **The ≥ 5× is not met.** The owner (2026-10-21): "if the system achieves at or near x3 i would consider this
  satisfactory and would defer any further improvement to future releases". This release keeps the speed-ups at the
  awake-time 3.55×, without a re-timing (the owner, 2026-10-22); the ≥ 5× stays the target of a later release (F1's
  structure caching, F3, MadGraph's event generation per point).
- **For the next measurement:** a clock that stops in sleep (`time.monotonic()`: `mach_absolute_time` on macOS; the
  script now records it and each scan's start); a machine kept awake; and a MadGraph folder of its own, as
  `mg5-production` is shared by every checkout and keys its results on the exported model's text, so a second run of
  the same code reuses the first's cross sections.

**Risks.** Caching by structure must key on everything that changes a diagram (a coupling set to zero removes one;
a mass crossing a threshold opens a channel); the key is the model's content with its numbers removed, and a test
flips each such switch. Vectorising G3 must keep its numerical guards (the light-vector Ward identity, G7-2).

## Part 2 — The library's searches in the generic route (milestones P1–P5)

**What the generic route lacks today.** `searches.EVALUATORS` and `resonances.EVALUATORS` decide by the model's
family. The generic route has the CMB, the γ-ray lines, antiprotons, SModelS and MadGraph (G9), the Higgs's signal
strength and the DMsimp monojet mapping. These apply to library families only:

| search | applies to | records |
|---|---|---|
| dijet resonances (CMS's coupling limit; ATLAS's Gaussian limits for broad Z′) | Z′ families, 2HDM+a | `cms-1806.00843-dijet`, `atlas-1910.08447-dijet-gaussian` |
| tt̄ resonances | scalar and pseudoscalar mediators | `cms-1908.01115-ttbar` |
| dileptons, and LEP's contact bound | B − L Z′ | `atlas-1903.06248-dilepton`, `lep-contact-bl` |
| heavy scalar to ZZ and WW | singlet mixing | `atlas-2009.14791-zz`, `atlas-2004.14636-ww` |
| mono-Higgs, mono-Z | 2HDM+a | `atlas-2108.13391-monoh`, `atlas-2111.08372-monoz` |
| DarkCast (visible, invisible, displaced) and BBN | dark photons, charged Z′ | `darkcast-dark-photon`, `sabti-1910.01649-bbn` |
| B → K + invisible | pseudoscalar portal | `flavour-b-to-k-invisible` |
| L_μ − L_τ: g − 2, trident | L_μ − L_τ Z′ | `muon-g2-2025`, `ccfr-1406.2332-trident` |
| LEP's inert-doublet limit | inert doublet | `lep-inert-doublet` |
| ATLAS's 2HDM+a combination | 2HDM+a | `atlas-2306.00641-2hdma` |

**P1 — The mediator's portrait.** For each Z₂-even new boson of a generic model, at the point, from G2's rules and
G6's decays: its mass, width and branching ratios; its couplings to each SM fermion (vector and axial for a vector,
scalar and pseudoscalar for a scalar); its mixing with h (a scalar's H share) and with the photon and Z (a vector's
SM share); its couplings to the dark states. A typed, tested object that every search below reads instead of the
family. Gate: for each library family, the portrait of its own model through the generic route reproduces the
library's mediator (couplings to 10⁻⁶, widths to 1%).

**P2 — Production from the portrait.** σ(pp → mediator) by flavour from MadGraph's tables at unit couplings
(`constraints.production`), scaled by each flavour's coupling squared, as the library does for its Z′ and scalars;
for couplings outside the tables' structures, MadGraph's LO per model (G9's process reuse), as a lower bound. Gate:
the library's σ for each family to 1%.

**P3 — The resonance recasts.** Dijets, tt̄, dileptons, heavy scalars to ZZ and WW, read from the portrait and P2 with
each record's own domain kept: the widths its paper states (`docs/widths.md`), the coupling structures a benchmark
limit extends to (`docs/benchmark_limits.md`), interference where the record has it (tt̄). Outside a record's
domain the search is undecided with the reason, never silent. Gate: on each library family through the generic
route, the same outcome as the library's at every point of its test scans.

**P4 — Light vectors and flavour.** DarkCast for any light vector from its couplings to each fermion, the visible,
invisible and displaced cases by its branching to dark states and its lifetime; BBN for a light vector in
equilibrium; B → K + invisible for a light pseudoscalar with Yukawa-like couplings; g − 2 and trident for a vector
coupled to muons. The coupling convention is D29's (ε e(0) Q). Gate: the library's dark photon, charged Z′ and
L_μ − L_τ through the generic route give the library's outcomes.

**P5 — The model-specific LEP and LHC combinations.** LEP's inert-doublet limit and ATLAS's 2HDM+a combination, the
mono-Higgs and mono-Z, apply only where the model is that model; through the generic route they need a structural
match (an inert doublet's quantum numbers; a 2HDM with a mixed pseudoscalar). This is the one place a comparison
with the library's models is needed, and only for these searches. Gate: the library's outcomes on its own models,
and undecided with the reason elsewhere.

**Order and the zoo.** P1 → P2 → P3 → P4 → P5. After P3 and after P5, the zoo's development half is rerun. The
held-out half is run once at the end, ledgered, as at G4, G7 and G12.

## Order of the two parts

Part 1 first: Part 2's recasts add searches at every point, so the speed-up helps them too, and the profile of F1
tells where Part 2's cost will go. Both parts keep G12's rules: a finding is fixed with its regression test, a gate is
declared before it is run, and a miss is recorded, not tuned away.
