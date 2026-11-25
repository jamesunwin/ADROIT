# The 2HDM+a mono-Z: calibrating ATLAS's contours beyond their benchmarks

**What ADROIT does** (`parameter_space/resonances.monoz`). ATLAS's mono-Z search (arXiv:2111.08372, Z → ℓℓ,
139 fb⁻¹) publishes only exclusion contours in (m_a, m_H), one at sin θ = 0.35 and one at 0.7, both at tan β = 1,
λ₃ = λ_P1 = λ_P2 = 3, m_H = m_A = m_H±, m_χ = 10 GeV and y_χ = 1. ADROIT compares a point with each contour's
reference model at the same masses through the resonant rate

  σ_res = σ(gg → H) BR(H → a Z) BR(a → χχ̄),

by a monotone rule: inside the contour with at least the reference's rate, excluded; outside it (where the contour
covers) with at most that rate, allowed; otherwise undecided.

**Before (2026-10-12, the owner's data audit):** the rule only at each contour's own benchmark couplings, where the
point and the reference differ only through BR(a → χχ̄), which multiplies every diagram. Elsewhere, undecided:
the non-resonant share of the signal changes with the couplings, by up to 7× for mono-h.

**Now (the owner, 2026-10-12: calibrate, as for mono-h).** MadGraph computes the full gg → Z a at other couplings,
and the rule's threshold is moved by how far the resonant-to-full ratio moves there.

## Method (`scripts/madgraph_xsec/monoz_calibration.py`, $0, about 1 h on one core)

- **Process.** MG5 3.8.0 with the LHC DM Working Group's Pseudoscalar_2HDM UFO, `g g > z h4 / h1 [noborn=QCD]`: the
  loop-induced gg → Z a. Its diagrams are the H s-channel (gg → H → Z a, through the top loop) and the top-quark
  boxes, with their interference. There is no s-channel A or a, since CP forbids a Z A a or Z a a vertex, and no
  s-channel Z at this order.
- **No s-channel h₁.** Its h₁ Z a vertex is ∝ cos(β − α) sin θ = 0 in the alignment limit, so the diagram vanishes
  identically. Its empty integration channel stalled MadLoop (three points past 20 minutes each), as the Z did for
  mono-h; without it a point takes 1–2 minutes.
- **Widths.** MadGraph is given ADROIT's two-body total widths of H, A, a and H±, so the resonant and the full σ
  share Γ_H and their ratio measures the boxes alone.
- **σ from the survey,** as for mono-h (0.3–0.9% statistical).
- **The model** is read from a copy under the tools folder's `work/`: MadGraph rewrites a model's pickles when it
  imports it, and the UFO folder is part of Track 1's run identity.
- **Double ratio.** With σB = σ(gg → Z a) BR(a → χχ̄) (ADROIT's BR at the same point; a is narrow), the ratio of
  the resonant to the full rate moves from contour P's benchmark (sin θ_P, tan β = 1) by

    s_P(θ, β) = [σ_res(θ, β)/σ_res(P)] / [σB_MG(θ, β)/σB_MG(P)].

  PDFs, scales and the K-factor cancel. BR(a → χχ̄) is 0.973–1.000 on the grid; leaving it out of σB, as the
  first mono-h summary did, would bias s by up to 2.7%, as large as the effect measured here.
- **Grid.** sin θ ∈ {0.2, 0.35, 0.5, 0.7} × tan β ∈ {1, 2, 3, 5} at four nodes inside both contours, (m_H, m_a) =
  (500, 150), (600, 200), (700, 250), (800, 300) GeV, with m_H = m_A = m_H±, m_χ = 10 GeV, y_χ = 1 and λ's = 3. A
  point where ADROIT finds H broad (Γ_H/m_H > 10%) is not run, since the rule leaves it undecided whatever s is:
  one, (500, 150) at sin θ = 0.7, tan β = 5. At (800, 300) H is broad at sin θ = 0.7, tan β = 1, so that node
  calibrates only the 0.35 contour. 63 points ran, none failed.

## Validation: the resonant fraction at the benchmarks

| (m_H, m_a) GeV | σ_res / σB_MG, sin θ = 0.35 | sin θ = 0.7 |
|---|---|---|
| (500, 150) | 1.020 | 1.040 |
| (600, 200) | 1.006 | 1.015 |
| (700, 250) | 0.987 | 0.982 |
| (800, 300) | 0.967 | 0.946 (H broad) |

ADROIT's resonant rate equals MadGraph's full rate to 2–5% at both benchmarks: the boxes contribute little to
gg → Z a here. ATLAS publishes no mono-Z cross-sections, so there is no comparison with ATLAS's own σ (for mono-h,
MadGraph reproduced ATLAS's to 2–9%).

## Results (`docs/monoz/calibration.json`)

The shift s_P, its smallest and largest over the narrow-H nodes (their number in brackets), rounded outward.

**The sin θ = 0.35 contour:**

| sin θ \ tan β | 1 | 2 | 3 | 5 |
|---|---|---|---|---|
| 0.2 | 0.997–1.004 (4) | 0.981–1.017 (4) | 0.978–1.017 (4) | 0.981–1.021 (4) |
| 0.35 | 1.000–1.000 (4) | 0.983–1.015 (4) | 0.981–1.015 (4) | 0.986–1.014 (4) |
| 0.5 | 0.989–1.008 (4) | 0.991–1.008 (4) | 0.994–1.010 (4) | 1.004–1.007 (4) |
| 0.7 | 0.995–1.021 (3) | 0.988–1.010 (4) | 0.988–1.020 (4) | 0.982–1.015 (3) |

**The sin θ = 0.7 contour:**

| sin θ \ tan β | 1 | 2 | 3 | 5 |
|---|---|---|---|---|
| 0.2 | 0.977–1.009 (3) | 0.962–1.009 (3) | 0.959–1.011 (3) | 0.962–1.015 (3) |
| 0.35 | 0.980–1.005 (3) | 0.964–1.004 (3) | 0.962–1.009 (3) | 0.967–1.012 (3) |
| 0.5 | 0.987–1.006 (3) | 0.972–1.009 (3) | 0.975–1.010 (3) | 0.985–1.010 (3) |
| 0.7 | 1.000–1.000 (3) | 0.989–1.007 (3) | 0.998–1.005 (3) | 0.998–1.005 (2) |

Every shift lies within 0.959–1.021. The boxes' share of gg → Z a hardly changes with sin θ and tan β, unlike the
non-resonant share of mono-h (0.14–1.99). So beyond the benchmarks the rule decides almost as much as at them.

## What ADROIT now applies

- At a contour's own benchmark couplings: the rule as before (s = 1), at any mass the contour covers.
- Inside the box sin θ 0.2–0.7, tan β 1–5, λ₃ = λ_P1 = λ_P2 = 3, m_H = m_A = m_H± 500–800 GeV, m_a 150–300 GeV,
  for each contour P: excluded if the point is inside P with σ_res/σ_res(P) ≥ max s_P; allowed if it is outside P,
  where P covers, with σ_res/σ_res(P) ≤ min s_P; otherwise undecided. (min s_P, max s_P) is the envelope of the
  (at most four) grid points around the point's (sin θ, tan β) (`resonances.SHIFTS_Z`, `resonances.shift_range`).
  Exclusion by either contour takes precedence. At ATLAS's benchmark couplings inside the mass box, the other
  contour now applies too.
- Elsewhere: undecided, naming what lies outside the box.

## Limitations

- **Interpolation only.** Four mass nodes and sixteen coupling points; between them s is assumed to stay within
  the extremes of the surrounding corners. The masses stay within the nodes' span, and m_a below 2m_t.
- **Degenerate heavy states** (m_H = m_A = m_H±), as in ATLAS's benchmarks.
- **Leading order,** as ATLAS's benchmark is; the K-factor cancels in the double ratio.
- **The 2 → 2 factorisation:** σ(gg → Z χχ̄) = σ(gg → Z a) BR(a → χχ̄) neglects off-shell a; a is narrow here
  (Γ_a/m_a = 2.0–3.8% on the grid).
