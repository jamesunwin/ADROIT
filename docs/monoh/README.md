# The 2HDM+a mono-Higgs: calibrating the resonant-to-full band beyond ATLAS's benchmark

**What ADROIT does** (`parameter_space/resonances.monoh`). ATLAS's mono-Higgs search (arXiv:2108.13391) gives an
upper limit σ₉₅(m_A, m_a) on gg → h χχ̄. ADROIT compares it with the resonant rate

  σ_res = σ(gg → A) BR(A → a h) BR(a → χχ̄),

which omits the non-resonant diagrams (the a s-channel, gg → a* → h a, and the top box gg → h a) and their
interference with the A s-channel. So r = σ_res/σ₉₅ decides only outside a band [ℓ, u] of resonant-to-full
ratios: excluded if r > u, allowed if r < ℓ, undecided in between.

**Before (R4, 2026-10-10):** [ℓ, u] = [0.4189, 1.2400], the smallest and largest σ_res/σ_full over ATLAS's 50
narrow-A nodes (Γ_A/m_A ≤ 10%), with σ_full ATLAS's own benchmark σ. That holds at ATLAS's benchmark couplings
(sin θ = 0.35, tan β = 1, λ₃ = λ_P1 = λ_P2 = 3) only, so since the owner's decision of 2026-10-12 a point
elsewhere was undecided.

**Now (the owner, 2026-10-12: extend the calibration).** MadGraph computes the full σ at other couplings, and at
each (sin θ, tan β) the band is widened by how far the resonant-to-full ratio moves there.

## Method (`scripts/madgraph_xsec/monoh_calibration.py`, $0, about 3 h on one core)

- **Process.** MG5 3.8.0 with the LHC DM Working Group's Pseudoscalar_2HDM UFO, `g g > h1 h4 [noborn=QCD]`: the
  loop-induced gg → h a with every diagram (A and a s-channels, the box) and their interference. ATLAS generated
  gg → h χχ̄; with CutTools as MadLoop's only reduction library that took over 20 minutes per survey channel
  (eleven channels, then refinement), days for a grid. Since a is narrow here (Γ_a/m_a ≈ 3–4%), χχ̄ comes from an
  on-shell a, and σ(gg → h χχ̄) = σ(gg → h a) BR(a → χχ̄) up to the off-shell A* → χχ̄ diagrams, which m_A ≫ √ŝ − m_h
  suppresses.
- **Widths.** MadGraph is given ADROIT's two-body total widths of H, A, a and H±, so the resonant and the full σ
  share Γ_A and their ratio measures the non-resonant diagrams alone. (MadWidth's automatic widths also included
  3- and 4-body decays, at minutes per point; at (600, 250) both give the same σ to 10⁻⁴.)
- **σ from the survey.** Each point's σ is the sum over the survey's integration channels (0.3–0.9% statistical).
  MG 3.8.0's refinement asserts on a channel whose weight vanishes identically, so it is not relied on.
- **No s-channel Z.** Its Z h a vertex is ∝ cos(β − α) = 0 in the alignment limit, so the diagram vanishes
  identically. Its empty integration channel nevertheless stalled MadLoop at some points, so the process excludes it
  (`g g > h1 h4 / z [noborn=QCD]`). The points before that change kept it; at (600, 250) the two processes give
  0.17945 ± 0.00059 and 0.17995 ± 0.00064 pb (0.6σ apart).
- **Double ratio.** PDF and scale choices are made to cancel: at each node the full σ is ATLAS's benchmark σ times
  MadGraph's σB(θ, β)/σB(0.35, 1), with σB = σ(gg → h a) BR(a → χχ̄) and ADROIT's BR at the same point (the
  narrow-a factorisation above). The ratio then moves from the benchmark by

    s = [σ_res(θ, β)/σ_res(0.35, 1)] / [σB_MG(θ, β)/σB_MG(0.35, 1)].

  Corrected 2026-10-12, with the mono-Z calibration: the first summary left the BRs out of the denominator, so s
  carried BR(θ, β)/BR(0.35, 1), which is 0.97–1.03 on the grid (m_χ = 10 GeV, y_χ = 1). The shifts moved by at
  most 2.7%, at (0.7, 5): 1.236 → 1.271.
- **Grid.** sin θ ∈ {0.2, 0.35, 0.5, 0.7} × tan β ∈ {1, 2, 3, 5} at four of ATLAS's narrow-A nodes, (m_A, m_a) =
  (600, 250), (800, 150), (1000, 300), (1200, 300) GeV, with m_H = m_H± = m_A, m_χ = 10 GeV and y_χ = 1, as in
  ATLAS's benchmark. Points where ADROIT finds A broad are not run, since the rule leaves them undecided whatever
  the band: tan β = 0.5 (Γ_A/m_A = 13–29% at every node, so dropped from the grid) and six points at large sin θ.
  Heavier narrow-A nodes do not exist at the benchmark (A is broad above m_A = 1200 GeV there). (1500, 400) also
  stalled in CutTools' quadruple-precision rescue (m_a > 2m_t).

## Validation against ATLAS's full benchmark σ

| (m_A, m_a) GeV | MG σ(gg → h a) BR(a → χχ̄) / ATLAS's full σ | σ_res/σ_full at the benchmark | Γ_A/m_A |
|---|---|---|---|
| (600, 250) | 1.060 | 0.887 | 0.054 |
| (800, 150) | 1.083 | 0.519 | 0.072 |
| (1000, 300) | 1.023 | 0.769 | 0.080 |
| (1200, 300) | 1.092 | 0.822 | 0.096 |

MadGraph's 2 → 2 reproduces ATLAS's full 2 → 3 benchmark σ to 2–9%, the size expected from different PDFs and
scales (NNPDF2.3 LO, μ = √ŝ here), which the double ratio cancels. The resonant fractions lie inside ATLAS's band
and are lowest at small m_a, as found over ATLAS's 50 nodes.

## Results

All 54 grid points and the 4 benchmark points ran (`docs/monoh/calibration.json`). The shift s of the
resonant-to-full ratio from the benchmark, its smallest and largest over the narrow-A nodes (their number in
brackets), and the band ADROIT applies there, [0.4189 s_min, 1.2400 s_max] (bands rounded outward):

| sin θ \ tan β | 1 | 2 | 3 | 5 |
|---|---|---|---|---|
| 0.2 | 0.58–0.97 (4); band 0.24–1.20 | 0.85–1.31 (4); band 0.35–1.64 | 0.94–1.52 (4); band 0.39–1.89 | 0.99–1.69 (4); band 0.41–2.10 |
| 0.35 | 1.00–1.00 (4); band 0.41–1.24 | 1.09–1.35 (4); band 0.45–1.68 | 1.11–1.47 (4); band 0.46–1.83 | 1.12–1.59 (4); band 0.46–1.97 |
| 0.5 | 1.08–1.89 (3); band 0.45–2.35 | 0.35–1.96 (4); band 0.14–2.43 | 0.37–1.97 (4); band 0.15–2.45 | 0.39–1.99 (4); band 0.16–2.47 |
| 0.7 | 0.31–1.35 (2); band 0.13–1.68 | 0.14–1.29 (3); band 0.05–1.61 | 0.15–1.28 (3); band 0.06–1.60 | 0.16–1.27 (3); band 0.06–1.58 |

- **Near the benchmark** (sin θ ≤ 0.35, any tan β here): s stays within 0.58–1.7, and the band is about as wide as
  ATLAS's own.
- **Large mixing** (sin θ = 0.5 at m_A = 1200 GeV; sin θ = 0.7 at m_A ≥ 800 GeV): the full σ is up to seven times the
  resonant one (s = 0.14–0.49). The a s-channel (gg → a* → h a) and the box grow with the a–quark mixing, so the
  resonant rate alone says little and the band there decides only clear cases.
- The nodes differ (at sin θ = 0.5, tan β = 2: 0.35 at (1200, 300) and 1.95 at (800, 150)); the envelope over them
  makes each band conservative across the mass box.
- A single band for the whole box would have been 0.06–2.46, which decides almost nothing; hence the band per
  (sin θ, tan β).

## What ADROIT now applies

- At ATLAS's benchmark couplings: ATLAS's own band, [0.4189, 1.2400], at any mass of ATLAS's grid (unchanged).
- Inside the box sin θ 0.2–0.7, tan β 1–5, λ₃ = λ_P1 = λ_P2 = 3, m_A 600–1200 GeV, m_a 150–300 GeV:
  [0.4189 s_min, 1.2400 s_max], where (s_min, s_max) is the range of the shift over the four nodes at the grid
  point (`resonances.SHIFTS`). Between grid points it is the envelope of the (at most four) surrounding corners
  (`resonances.shift_range`).
- Elsewhere: undecided, with the reason naming what lies outside the box.

## Limitations

- **Conservative by construction.** At each grid point the band combines the worst node's shift with the
  worst of ATLAS's 50 benchmark ratios, and between grid points it takes the envelope of the corners. So it
  decides less than an exact calculation would.
- **Interpolation only.** The shift is measured at four mass nodes and sixteen coupling points; between them it is
  assumed to stay within the extremes of the surrounding corners. The masses are restricted to the nodes' span, and m_a stays below
  2m_t, where a → tt̄ would change the non-resonant a propagator.
- **m_H and m_H± are not varied.** The non-resonant gg → h a has no H or H± diagram in the alignment limit, so
  they enter only through the widths, which both σ share. The box does not require m_H = m_A.
- **Leading order,** as ATLAS's benchmark is; the K-factors of the resonant and full σ are taken to be equal.
- **The 2 → 2 factorisation** neglects off-shell A* → χχ̄; the 2–9% agreement with ATLAS's 2 → 3 σ bounds it.
