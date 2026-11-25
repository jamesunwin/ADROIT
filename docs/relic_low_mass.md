# The relic density below 10 GeV: the Standard Model's equation of state

The batch plan's §4 (the pre audit batch plan of 2026-10-19). Until 2026-10-19 the relic density's degrees of freedom,
g_eff(T) = g*ρ and h_eff(T) = g*s, were the Standard Model as an ideal gas, the quarks and gluons giving way to a
hadron gas across 160 MeV (a tanh of width 20 MeV). Lattice QCD puts the plasma up to ~15% below the ideal gas at
T ≲ 0.5 GeV, which moved Ωh² by up to ~5% for dark matter above 10 GeV and more below; DM7 had left the region below
10 GeV unresolved.

## The change

`constraints.relic` now takes Saikawa & Shirai's equation of state (arXiv:1803.01038, JCAP 05 (2018) 035) through
their fitting functions, Appendix C, with the coefficients as printed there:

- above 120 MeV, eqs. C.1–C.2: g*ρ and g*ρ/g*s as ratios of eleventh-order polynomials in ln T (their Table 1),
  which follow their lattice QCD and perturbative matching across the crossover and the electroweak plasma above it;
- below 120 MeV, eqs. C.3–C.9: the electrons, muons, pions and four effective hadron masses, with the neutrinos'
  decoupling (g*ρ → 3.383, g*s → 3.931 today).

The two fits meet at 120 MeV within 0.04%. The fit gives 10.55 at 1 MeV (their tabulated 10.53) and 104.1 at 10 TeV
(the ideal gas: 106.75). The table still covers 1 MeV–10 TeV and is held below 1 MeV, where the thermal history stays
pending as before (the external audit's A06, signed: `thermal_history_reason`). The ideal gas is kept for comparison
(`relic.ideal_gas`). The coefficients are physical results printed in the paper; their data files, which carry no
licence, are not copied.

Unchanged: the hadronic final states below 2 GeV as built for the portal library (photon-like and B − L mediators
through the PDG's R ratio; scalars pending), the Boltzmann solution, and today's entropy density s₀ = 2891.2 cm⁻³
(g*s today 3.909).

## The gate (declared before running)

Against Saikawa & Shirai 2020 (arXiv:2005.03544), the s-wave cross section a Majorana fermion needs for
Ωh² = 0.120 (their `S_2`, from https://member.ipmu.jp/satoshi.shirai/DM2020/, fetched into the tools folder for
validation and never copied here): ADROIT's required ⟨σv⟩ within **3%** of theirs at every tabulated mass from 1 to
1000 GeV. Masses from 10 MeV to 1 GeV and above 1 TeV are reported, not gated. Known differences inside the
allowance, not corrected for: their g*s today (3.931 against 3.909, Ωh² 0.56% higher for them), their integration to
T = 1 eV against ADROIT's x = 10⁴, and their 2020 equation of state against the 2018 fit.

`scripts/validate_relic_ss2020.py` runs it and writes a development receipt (relic_ss2020_validation).

## The result

**Passed** (2026-10-19; a development receipt (relic_ss2020_validation), every tabulated mass): the largest deviation
from 1 to 1000 GeV is 0.47%, against the 3% gate. The ratio of ADROIT's required ⟨σv⟩ to theirs, by range:

| masses | tabulated | ADROIT / Saikawa–Shirai | the ideal gas, for comparison |
|---|---|---|---|
| 10–100 MeV (reported) | 78 | 0.947–0.991 | 0.981 at 30 MeV |
| 0.1–1 GeV (reported) | 78 | 0.991–0.996 | 0.992, 0.995, 0.996 at 0.1, 0.3, 1 GeV |
| 1–10 GeV | 78 | 0.996–1.004 | 0.94 at 3 GeV, 0.89 at 10 GeV |
| 10–1000 GeV | 156 | 0.995–1.000 | 0.94 at 30 GeV, 0.95 at 100 GeV, 0.96 at 1 TeV |
| 1–10 TeV (reported) | 78 | 0.993–0.998 | — |

The ideal gas required up to 11% less (at 10 GeV) and 4–6% less above 30 GeV than the lattice equation of state:
more than its own estimate (≲5% above 10 GeV). At fixed couplings Ωh² moves by about the same fraction, upward.
Below 1 GeV the two agree (freeze-out in the hadron gas); the reported deviations there (to 5% at 10 MeV) come from
the thermal history near and below 1 MeV, which stays pending as before (A06).

## What it changes

Ωh² at fixed couplings: little below 1 GeV, up to ~11% between 3 and 10 GeV, and 4–6% from 30 GeV to 1 TeV. The
verdict-change report records the documented studies it moves (`physics_extensions_verdict_changes_2026-10-19.md`).

## Against micrOMEGAs: the equation of state

micrOMEGAs (7.1.10) solves with Drees, Hajkarim & Schmitz's degrees of freedom (arXiv:1503.03513, its
`Data/hgEff/DHS.thg`), ADROIT now with Saikawa & Shirai's. At the cross-check's four points
(`tests/parameter_space/test_crosscheck.py`) ADROIT's Ωh² over micrOMEGAs':

| point | ADROIT (Saikawa & Shirai) | ADROIT on micrOMEGAs' table (DHS) | the two tables' ratio |
|---|---|---|---|
| Higgs-portal scalar on the pole, 62 GeV | 1.045 | 1.008 | 1.037 |
| Higgs-portal scalar, 300 GeV | 1.025 | 0.988 | 1.037 |
| inert doublet, 990 GeV | 1.022 | 0.986 | 1.036 |
| inert doublet, 72.8 GeV (W W*) | 1.024 | 0.987 | 1.037 |

Compared like with like (both on DHS) the two codes agree within 1.4%, so their cross sections and solutions agree;
the 3.7% is the equation of state's systematic: Saikawa & Shirai's fit gives Ωh² 3.7% above DHS's table at these
masses. The cross-check now compares like with like and records that ratio; it had passed at 3% with the ideal gas,
whose difference from DHS happened to be smaller there. The release run of 2026-10-20 found the failure.

The portal library's relic gates (`scripts/validate_portal_library_3.py`) compare like with like too. With ADROIT's
own table four scalar-singlet gates (40–60 GeV) had been 1.050–1.078, outside their 5%. On DHS all 17 pass, ADROIT /
micrOMEGAs 0.963–1.037 (inert doublet BP1–HP10, scalar singlet 40 GeV–3 TeV), and ADROIT's own equation of state
raises Ωh² by 3.2–4.3% at each point below 1 TeV and by 1.4% at 3 TeV, where freeze-out (T ≈ 120 GeV) is above the
range in which the two tables differ.

## A Boltzmann solve that stops short (2026-10-20)

The physics-extensions verdict study found the vector Higgs portal at λ = 10 just below m_h/2 with Ωh² ≈ 10⁷ at some
masses beside 0.13 at their neighbours: near the resonance the rate is so large that BDF's step underflowed at x ≈ 4,
and `freeze_out` read the yield where the integrator stopped (still at equilibrium) as the relic. A latent defect,
exposed here by the new table's slightly different g*^{1/2}. `relic._solved` now retries a solve that stops short
(Radau, then later starts from equilibrium while Γ/H > 10³); if none reaches x = 10⁴ it raises `RelicUnresolved`,
and the scan records the relic density as pending with the reason, never a number. A solve that reaches the end at
the first try is unchanged.
