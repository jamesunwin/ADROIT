# Benchmark-specific limits: how each is extended beyond its benchmark

Some published limits are not on a model-independent quantity (σ × BR into a final state, a coupling) but on one
benchmark model: a contour in a plane at fixed other parameters. ADROIT applies such a limit away from its
benchmark only where a calculation shows the comparison still holds; elsewhere the point is **undecided**, with the
reason (the owner's data audit, 2026-10-12). [`widths.md`](widths.md) covers the related question of width domains.

| limit (record) | the benchmark | how ADROIT extends it | status |
|---|---|---|---|
| **ATLAS mono-h** (`atlas-2108.13391-monoh`) | 2HDM+a, sin θ = 0.35, tan β = 1, λ's = 3: σ₉₅(m_A, m_a) on the full gg → h χχ̄ | ADROIT's resonant σ against ATLAS's limit, decided outside a band of resonant/full ratios. Beyond the benchmark the band is widened per (sin θ, tan β) by MadGraph's full gg → h a, over sin θ 0.2–0.7, tan β 1–5, m_A 600–1200, m_a 150–300 GeV ([`monoh/README.md`](monoh/README.md)) | calibrated (2026-10-12); outside the box undecided |
| **ATLAS mono-Z** (`atlas-2111.08372-monoz`) | 2HDM+a, sin θ = 0.35 and 0.7, tan β = 1, λ's = 3: contours in (m_a, m_H) | A monotone rule (inside the contour with at least the benchmark's rate: excluded; outside with at most: allowed), exact at the benchmark couplings, where the rates differ only through BR(a → χχ̄). Beyond them the thresholds move by the shift of the resonant-to-full ratio, from MadGraph's full gg → Z a over sin θ 0.2–0.7, tan β 1–5, m_H 500–800, m_a 150–300 GeV: 0.959–1.021 ([`monoz/README.md`](monoz/README.md)) | calibrated (2026-10-12; before that day, applied at any tan β by the resonant rate alone, then benchmark only); outside the box undecided |
| **ATLAS 2HDM+a combination** (`atlas-2306.00641-2hdma`) | scenario 1a: m_χ = 10 GeV, sin θ = 0.35, tan β = 1, λ's = 3, degenerate heavy scalars | Exactly the scenario; anything else is undecided, naming the differing parameters | strict (R4) |
| **CMS summary planes** (`cms-2405.13778-*`) | the LHC DM Working Group's V1, A1, V2, A2 couplings | Only a model that is exactly one of them | strict (R4) |
| **ATLAS one-squark contour** (`atlas-2010.14293-squark`) | one light-flavour squark, QCD pair production, q̃ → q χ̃⁰ | Applied to a u_R or d_R partner. Its t-channel χ exchange adds production (∝ y⁴) that is not computed. So inside the contour: excluded (conservative); outside: undecided | **one-sided** (2026-10-12; before, "allowed" outside) |
| **SModelS for coloured partners** (`smodels-3.2.1`) | SMS maps with the σ ADROIT supplies: QCD pair production of one colour triplet | The same: r ≥ 1 excludes, r < 1 leaves the point undecided | **one-sided** (2026-10-12) |
| **CMS monojet, spin 0** (`cms-2107.13021-monojet-spin0`) | DMsimp, g_q = g_χ = 1, m_DM = 1 GeV | μ = g_q² BR_inv / BR_inv(benchmark) at the same mediator mass. The production loop is the same (Yukawa-like couplings scaled together), and m_χ enters through BR_inv. Only for widths no broader than the benchmark's | rescaled with its domain (2026-10-06) |
| **LEP's inert-doublet region** (`lep-inert-doublet`) | the inert doublet | Applied to the inert doublet only | model-specific |

Model-independent limits (σ × BR, couplings, rates) need no such extension. Each carries its own domain: masses,
widths ([`widths.md`](widths.md)) and confidence level.

## Known limitation: coloured t-channel partners (deferred to a future release)

**Which models.** A t-channel portal whose partner φ is coloured (a squark-like scalar coupling as y φ* χ̄ q, e.g.
the u_R and d_R partners), wherever its LHC production enters: ATLAS's one-squark contour
(`atlas-2010.14293-squark`) and SModelS (`smodels-3.2.1`).

**What ADROIT computes.** σ(pp → φφ*) from QCD alone: the NNLL-fast squark/stop tables, which depend on m_φ only.

**What it leaves out.**
- t-channel χ exchange, q q̄ → φφ* (and q q → φφ for Majorana χ), whose square grows as y⁴. It is comparable to
  QCD once y is of order g_s ≈ 1 and dominates beyond.
- Its interference with QCD in q q̄ → φφ*, of order y² g_s², for the quark flavour φ couples to. Its colour factor
  does not vanish, and its sign is not established here.

**What ADROIT does about it (decision D33, 2026-10-16).** Nothing is decided from the QCD σ alone: inside ATLAS's
contour or outside it, and at any SModelS r, the point is **undecided**, with the reason stated. A coloured partner
is therefore neither excluded nor allowed by these searches; a model excluded by another valid constraint stays
excluded. Until 2026-10-16 the QCD σ was taken as a lower bound, so that r ≥ 1 excluded; but the bound holds only
where the y⁴ term dominates or the interference is not destructive, and at intermediate y a destructive
interference could make the full σ smaller than QCD's (the external audit's R20). Earlier exclusions of coloured
partners by these two searches therefore become undecided.

**What would remove it** (the owner, 2026-10-12: deferred to a future release). σ(pp → φφ*, φφ) with every
diagram, as a function of y, m_φ and m_χ: the LHC DM Working Group's t-channel simplified model (DMSimpt, from the
FeynRules model database, not yet in the tools folder) and a MadGraph table at LO, as for mono-h and mono-Z (a few
hours on one core). With it, a point would be excluded where the full σ lies above the limit and allowed where it
lies below.
