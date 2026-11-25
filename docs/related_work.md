# Related work, inspirations and tools

A record of the works that inspired the design of ADROIT and of the tools
it reuses, so that they are cited in the documentation and the paper. Started
2026-09-29.

For the current complete dependency inventory and ready-to-use references, see
[citations.md](citations.md), [dependencies.bib](dependencies.bib) and the
[README citation block](../README.md#citing-adroit-and-its-dependencies). Cite all
codes and datasets used in a study, including cross-checks such as MadDM, rather
than crediting only ADROIT. [Installation and API setup](installation.md) explains
how to install those components and keep provider credentials in a private `.env`.
The historical entries below retain their original survey dates and checking levels.

**Rule.** An entry is added only after its reference has been checked. The
level of checking is recorded:
- **read**: the paper was read in full;
- **abstract**: its arXiv abstract page was opened;
- **record**: its arXiv metadata record (title, authors, date) was matched,
  in the literature survey of 2026-09-29.

What a *record*-level entry is said to do comes from its abstract or from
search results, and must be confirmed against the paper before it is cited
for that. Entries marked *(to verify)* have not been checked at all and must
not be cited.

## The origin

ADROIT is built on the Nomothetica system (its commit `2a4fa6f`): the
typed state, provenance log, library cards and neighbour graph, fitting,
the tournament with flags, the agents behind one client interface, the human
gates and the evaluation harness.

## Motivation

- **LZ Collaboration, arXiv:2609.02823.** "Search for dark matter particle
  interactions in an extended nuclear recoil energy window with the
  LUX-ZEPLIN (LZ) experiment." Read in full, 2026-09-29.
  - It tests the twenty relativistic Lagrangians of arXiv:1308.6288 and the
    inelastic operators O1 and O4 as a library of 616 models.
  - Its Tables S7 and S8 are the first validation target (build plan, DM6).
  - Data: HEPData, DOI 10.17182/hepdata.182472.

## Agent systems that inspired design choices

| work | what is borrowed | where |
|---|---|---|
| **DarkAgents**, Lucente, Pascoli, Sala, Zandi, arXiv:2606.11157 (code: github.com/PhysicsZandi/DarkAgents) | a constraint agent that states when a literature bound cannot be applied without further calculation; a separate assumption-audit agent; the planned loop in which a missing analysis triggers a deterministic calculation; validation by a person running the same backend | DM7, DM9 |
| **FERMIACC**, Agrawal, Craig, Madden, Valenzuela Lombera, arXiv:2603.22538 | the explicit contract between the full model and the computed benchmark; a justification required for every mass and coupling; a critic with fixed axes where the worst axis decides; canonical signatures for de-duplicating models; user-supplied data overriding weaker public sources | DM4, DM8 |

Both were read in full on 2026-09-29. Both report that every number must come
from deterministic code, which is also Nomothetica's rule. Neither covers
direct detection, ranks a library of models, or applies complementary
constraints quantitatively.

DarkAgents also reports that agents invented references in final reports.
The reference check of DM9 and the curated database of DM7 respond to that.

## Physics framework

| work | role |
|---|---|
| Fitzpatrick, Haxton, Katz, Lubbers, Xu, arXiv:1203.3542 | the nonrelativistic effective theory and its operators |
| Anand, Fitzpatrick, Haxton, arXiv:1308.6288 | the Lagrangians L1–L20, their map to the nonrelativistic operators, and the DMFormFactor package |
| Barello, Chang, Newby, arXiv:1409.0536 | inelastic scattering in the effective theory |
| Baxter et al., arXiv:2105.00599 | recommended conventions for the halo model and for reporting results |
| Jeong, Kang, Scopel, Tomar, Comput. Phys. Commun. 276, 108342 (2022) | WimPyDD, the rate code LZ used |

These are cited by arXiv:2609.02823 for the roles given.

### Inputs to the forward model (DM2)

| work | level | used for |
|---|---|---|
| Baxter et al., arXiv:2105.00599 | read (section 3 and Table 1) | the Standard Halo Model parameters and the Earth's velocity, Eqs. 11–12 |
| Anand, Fitzpatrick, Haxton, arXiv:1308.6288 | used | the response functions and their coefficient algebra (Eq. 38), as implemented in both reference codes; its Table 1, the twenty interactions L1–L20 and their reductions, transcribed from the TeX source into the DM4 cards |
| Catena, Schwabe, arXiv:1501.03729 | record | shell-model responses for the light nuclei |
| Barello, Chang, Newby, arXiv:1409.0536 | record | v⊥² = v² − v_min² for inelastic scattering |
| Lewin, Smith, Astropart. Phys. 6 (1996) 87, doi:10.1016/S0927-6505(96)00047-3 | record (Crossref) | the Helm form factor and its parameters |
| Scopel, Yoon, Yoon, arXiv:1505.01926 | record | the approximate spin responses (Appendix C) |
| Divari, Kosmas, Vergados, Skouras, Phys. Rev. C 61 (2000) 054612 | record (Crossref) | ¹⁹F spin values, used to test the normalisation |
| Meija et al., Pure Appl. Chem. 88 (2016) 293, doi:10.1515/pac-2015-0503 | record (Crossref) | the natural isotopic compositions |
| Giuliani, Girard, hep-ph/0406218, Phys. Rev. D 71 (2005) 123503 | record | the ¹⁸³W single-particle ⟨S_n⟩ = −0.17, as cited by WimPyDD |
| Bednyakov, Šimkovic, hep-ph/0502232, Phys. Part. Nucl. 36 (2005) 131 | record | ¹⁸³W ⟨S_n⟩ = −0.031 in the odd-group model (Table II): with hep-ph/0406218's −0.17, the factor-six spread behind leaving ¹⁸³W without a spin response |
| Pacheco, Strottman, Phys. Rev. D 40 (1989) 2131 | record (as cited by CRESST, arXiv:1904.00498) | the ¹⁷O spin value ⟨S_n⟩ = 0.5 used here |
| RES-NOVA (Alloni et al.), arXiv:2601.16251; Kang, Scopel, Tomar, Yoon, arXiv:1805.06113 (effective-operator sensitivities, CRESST-II among them) | record | both leave ¹⁸³W out of spin-dependent limits on tungsten targets, as CRESST-III did |
| Croon, Smirnov, arXiv:2309.02495 | record | the ¹⁷O spin values, as cited by WimPyDD; a paper on dark matter heating planets, so a primary nuclear source is still wanted |
| Dent, Krauss, Newstead, Sabharwal, arXiv:1505.03117 | record | the spin-1 operators O₁₇–O₂₀ (phase 2) |

The response coefficients are transcribed from WIMpy_NREFT (MIT licence,
doi:10.5281/zenodo.1230503), which is to be cited with them.

### Experiments, data releases and statistics (DM3)

Each checked against its arXiv record on 2026-09-29; the data releases and
the papers marked *read* were read for the numbers the modules use.

| work | level | used for |
|---|---|---|
| CRESST Collaboration, arXiv:1904.00498 | read (sections V–VI) | CRESST-III: halo, form factor, method; ¹⁷O as the only spin carrier |
| CRESST Collaboration, arXiv:1905.07335 | read (whole) | CRESST-III data release: events, efficiencies, Eq. 1, limits |
| SuperCDMS Collaboration, arXiv:1509.02448 | record | CDMSlite Run 2, spin-independent result |
| SuperCDMS Collaboration, arXiv:1707.01632 | read (the release document) | CDMSlite Run 2 data release: events, efficiencies, energy scale, procedure, limits |
| PICO Collaboration, arXiv:1902.04031 | read (sections I–VI) | PICO-60: exposures, halo, nuclear responses, method |
| Bringmann et al. (DarkBit/DDCalc), arXiv:1705.07920 | record | DDCalc, whose PICO-60 tables are read at run time |
| S. Yellin, physics/0203002 | record | the maximum gap and optimum interval methods |
| S. Yellin, arXiv:0709.2701 | record | the high-statistics optimum interval; his code, from the CDMSlite release |
| Cowan, Cranmer, Gross, Vitells, arXiv:1007.1727 | record | asymptotic thresholds of the profile likelihood |
| An et al. (DIAMX), arXiv:2512.05850 | record | the xenon likelihoods (LZ, XENONnT, PandaX-4T) |
| LZ, arXiv:2207.03764 and 2410.17036 | record | the LZ searches DIAMX models |
| XENONnT, arXiv:2303.14729 and 2502.18005 | record | the XENONnT searches DIAMX models |
| PandaX-4T, arXiv:2408.00664 | record | the PandaX-4T search DIAMX models |
| Maltoni, Schwetz, hep-ph/0304176 | used | the parameter-goodness-of-fit test of the tension between the signal and the null experiments (DM6) |
| Haxton, McElvain, github.com/Berkeley-Electroweak-Physics/Elastic (2022) | used (fetched, not copied; no licence stated) | the revised one-body density matrices LZ uses since 2023: `NuclearModel.haxton_2022` (DM5) |
| Berkeley-Electroweak-Physics, Mu2e scripts (BSD-3; python/mu2e.py) | used (fetched, run in its own environment) | the multipole matrix elements that turn density matrices into response functions (DM5) |
| LZ Collaboration, arXiv:2312.02030 | record | the revision of the xenon density matrices, and its NREFT limits in an extended window |
| LZ Collaboration, arXiv:2404.17666 | record | LZ's covariant interactions: m_M = m_N, and its definitions of L6, L9, L10, L12, L18 (DM5) |
| Bishara, Brod, Grinstein, Zupan, arXiv:1708.02678 (DirectDM) | used | its nucleon inputs (num_input.py): σ-terms for the Higgs portal's f_N, g_A and Δq for the Z portal's axial charges, magnetic moments, s_W², G_F, boson masses (DM4) |
| Del Nobile, arXiv:2104.12785 | used as a check | the magnetic-dipole and anapole couplings the DM4 derivations reproduce |
| Klos, Menéndez, Gazit, Schwenk, arXiv:1304.7684 | used | the spin structure factors with two-body currents that CDMSlite (and the xenon experiments) used; the second spin-dependent nuclear model here (`NuclearModel.klos`), fits transcribed from the v4 TeX source |
| C. A. J. O'Hare, DirectDetectionPlots (GitHub) | fetched, then dropped | a first source of limit curves; replaced by digitising the collaborations' own figures, which it matched only to 5–7% |
| DEAP-3600 Collaboration, arXiv:1902.04048 | read (sections IV, VIII) | DEAP-3600: exposure, acceptance (Fig. 21), energy scale, resolution, systematics, limit (Fig. 24) |
| McCabe, arXiv:1005.0579 | record | the halo DEAP-3600 cites |
| Cousins & Highland, Nucl. Instrum. Meth. A 320 (1992) 331, doi:10.1016/0168-9002(92)90794-5 | record (Crossref) | folding systematic uncertainties into a Poisson limit |

### Viability of a freeze-out model (DM8)

| work | level | used for |
|---|---|---|
| Kahlhoefer, Schmidt-Hoberg, Schwetz, Vogl, arXiv:1510.02110, JHEP 02 (2016) 016 | read (section 2) | perturbative unitarity of axial couplings to a massive vector: m_f ≲ √(π/2) m_Z′/g_f^A for any fermion (eq. 2.8), and the scale √s ≈ π m_Z′²/((g^A_DM)² m_DM) (eq. 2.9), in `model_checks` |

## Tools

All at *record* level unless stated. Version, licence and interface are
checked in DM0.

### Rates, matching and nuclear physics

| tool | reference | input → output |
|---|---|---|
| WimPyDD | arXiv:2106.06207, 2110.11086 (abstract) | nonrelativistic coefficients, any spin, elastic or inelastic, any velocity distribution → expected rates |
| WIMpy_NREFT | Kavanagh and Edwards, doi:10.5281/zenodo.1230503 (tested in DM0) | nonrelativistic coefficients O1–O20 → rates; holds the tabulated nuclear responses |
| DMFormFactor | arXiv:1308.6288 (read: abstract) | operator coefficients, target isotope → response functions and dR/dE_R; Mathematica |
| dmscatter | arXiv:2209.09187 | as DMFormFactor; Fortran and Python |
| DirectDM | arXiv:1708.02678 (physics: 1707.06998, 1611.00368) | quark- and gluon-level coefficients → nonrelativistic coefficients |
| runDM | arXiv:1605.04917 | vector-mediator couplings at a high scale → at the low scale |
| RAPIDD | arXiv:1802.03174 | fast surrogate rates for scans |
| chiral structure factors | arXiv:1812.05617 | generalised spin-independent structure factors |
| nuclear-input uncertainties | arXiv:2305.08991 | shell-model uncertainty on effective-theory limits |
| matching dictionary | arXiv:1806.01291, 2104.12785 | relativistic → nonrelativistic tables, elastic and inelastic |

### Model → limits

| tool | reference | input → output |
|---|---|---|
| micrOMEGAs | arXiv:0803.2360, 1305.0237, 2312.14894 (v6), 2606.06645 (v7) | CalcHEP model files → relic density, nucleon cross-sections, recoil rates, indirect spectra |
| micrOMEGAs recasting | arXiv:2003.08621 | the same, plus a velocity distribution → exclusion from recast experiments |
| MadDM | arXiv:1308.4955, 1505.04190, 1804.00044, 2107.04598 | UFO model → relic density, cross-sections, recoil rates, indirect fluxes |
| DarkSUSY 6 | arXiv:1802.03399 | particle module → relic density, rates, indirect fluxes, solar capture |
| DDCalc, DarkBit, GAMBIT | arXiv:1705.07920, 1808.10465, 1705.07908 | nucleon or nonrelativistic couplings, halo model → counts and Poisson likelihoods per experiment |
| GUM | arXiv:2107.00030 | FeynRules or SARAH Lagrangian → GAMBIT code; the closest non-agent analogue of Path 1 |
| DIAMX | arXiv:2512.05850 | reproduces the LZ, PandaX-4T and XENONnT likelihoods from public data |
| detector response | NEST arXiv:1106.1613; flamedisx arXiv:2003.12483 | recoil spectrum → likelihood in the detector's observables |

### Complementary constraints

| class | tools |
|---|---|
| solar capture and neutrinos | Capt'n General (arXiv:2105.06810), WimPyC (arXiv:2510.21185), χaroν (arXiv:2007.15010), DarkCapPy (arXiv:1808.03700) |
| collider recasts | SModelS (arXiv:1312.4175, 2112.00769, 2409.12942), CheckMATE 2 (arXiv:1611.09856), MadAnalysis 5 (arXiv:1407.3278), Contur (arXiv:1606.05296, 2505.09272) |
| indirect detection | PPPC4DMID (arXiv:1012.4515), CosmiXs (arXiv:2312.01153), Hazma (arXiv:1907.11846) |
| relic density beyond kinetic equilibrium | DRAKE (arXiv:2103.01944) |
| beam dump and feebly interacting states | DarkCast (arXiv:1801.04847), MadDump (arXiv:1812.06771), SensCalc (arXiv:2305.13383), FORESEE (arXiv:2105.07077) |
| flavour | flavio (arXiv:1810.08132) |
| neutrino backgrounds | SNuDD (arXiv:2607.22817), NeutrinoFog (arXiv:2109.03116) |

### Used in DM7

| work | reference | used for |
|---|---|---|
| CMS, dark sector searches (summary) | arXiv:2405.13778, Phys. Rept. 1115 (2025) 448 | the gate's published summary; the collider records |
| LHC DM Working Group | arXiv:1507.00966, 1603.04156, 1703.05703 | the spin-1 benchmarks, widths, the translation to σ_SI and σ_SD, the relic comparison |
| Gondolo & Gelmini | Nucl. Phys. B360 (1991) 145 | the relativistic thermal average |
| Griest & Seckel | Phys. Rev. D 43 (1991) 3191 | forbidden annihilation, and the freeze-out equation |
| Gould | ApJ 321 (1987) 571 | the capture rate in the Sun |
| Jungman, Kamionkowski & Griest | Phys. Rept. 267 (1996) 195 | capture–annihilation equilibrium |
| Catena & Schwabe | arXiv:1501.03729 | nuclear responses of the solar elements (already shipped) |
| B16 standard solar models | arXiv:1611.09867 | the Sun's profile (fetched from Capt'n General, MIT) |
| inelastic capture | arXiv:0905.1333 (Nussinov, Wang, Yavin), 0905.1847 (Menon, Morris, Pierce, Weiner) | capture of inelastic dark matter, and its caveats |
| IceCube, solar dark matter | arXiv:1612.05949 (limits), 1601.00653 (DarkSUSY capture rates for validation) | the tier-2 record and the capture check |
| Fermi-LAT, dwarf galaxies | arXiv:1503.02641 | the tier-3 indirect-detection record |
| Planck 2018 | arXiv:1807.06209, Table 2, TT,TE,EE+lowE+lensing | Ωh² = 0.1200 ± 0.0012 |

### Used in DM8's numerical cross-check (2026-10-01)

Called as dependencies, never bundled. MadDM and micrOMEGAs, which state no
licence, are used under fair use (the owner's decision, 2026-10-01); micrOMEGAs
is not used yet.

| tool | version | reference, and how it was checked |
|---|---|---|
| MadGraph5_aMC@NLO | v3.8.0 | Alwall et al., JHEP 07 (2014) 079, arXiv:1405.0301 (abstract) |
| MadDM | 3.3 release candidate, commit 6570bb5 | arXiv:1308.4955, 1505.04190, 1804.00044, 2107.04598, as MadDM's CITATION.bib requests |
| RAPIDD (MadDM's copy) | f471a10 | arXiv:1802.03174 (record) |
| UFO, the model format ADROIT writes | 1.x | Degrande, Duhr, Fuks, Grellscheid, Mattelaer, Reiter, Comput. Phys. Commun. 183 (2012) 1201, arXiv:1108.2040 (abstract) |
| DMsimp_s_spin1, the reference UFO model | from the FeynRules model database | arXiv:1508.05327 and 1703.05703, as its wiki page lists (page read) |
| GNU Scientific Library | 2.8 | gnu.org (GPL-3.0-or-later) |

### Model building

FeynRules (arXiv:1310.1921), SARAH (arXiv:1309.7223), CalcHEP
(arXiv:1207.6082), Matchete (arXiv:2212.04510).

FeynRules and SARAH need Mathematica and are not used (the owner's decision,
2026-10-01). Open alternatives, *(to verify)*: the UFO format (UFO 2.0,
arXiv:2304.09883), which the project's own generator will write; LanHEP
(CalcHEP model files); MARTY (arXiv:2003.07384).

### Electron recoils (a later extension)

DarkELF (arXiv:2104.12786), QEdark (arXiv:1509.01598), QCDark
(arXiv:2306.14944), obscura (arXiv:2112.01489), EXCEED-DM (arXiv:2210.14917).

## Data sources

| source | content | status |
|---|---|---|
| HEPData, LZ extended window | DOI 10.17182/hepdata.182472; reported to hold 46 tables | found in search; not opened (HEPData blocks automated access) |
| HEPData, LZ 4.2 tonne-year search (arXiv:2410.17036) | limits | from search results *(to verify)* |
| XENON public data | an approximate bin-wise XENON1T likelihood for any recoil spectrum (arXiv:2210.07231); a XENONnT light-WIMP recast tool (arXiv:2409.17868) | record |
| PandaX data releases | pandax.sjtu.edu.cn | exists; no likelihood release found |
| CRESST | event-level data descriptions (arXiv:1701.08157, 1905.07335) | record |
| DirectDetectionPlots (O'Hare) | github.com/cajohare/DirectDetectionPlots: limit curves as text files | no licence stated *(to verify)* |
| SuperCDMS limit plotter, DMTools | limit compilations | exist; no programmatic interface confirmed |
| arXiv:2606.21658 (Yuan, Ramanathan) | a pipeline that extracts limit curves from papers | abstract; its repository is AxionLimits (axions and dark photons), not WIMP–nucleon limits |
| reporting conventions | arXiv:2105.00599 | cited by LZ |

## Other systems to be aware of

No agent system was found that computes direct-detection observables,
ingests direct-detection data, or ranks operators against a recoil signal
(survey of 2026-09-29).

| system | reference | what it does | overlap |
|---|---|---|---|
| ColliderAgent | arXiv:2603.14553 | Lagrangian → collider exclusion limits from natural-language prompts | Path 1 in architecture; collider only |
| bsm_agent | arXiv:2606.21316 (abstract; PDF searched 2026-10-02) | particle content (quantum numbers, in natural language) → renormalizable Lagrangian, gauge-anomaly checks, symmetry breaking and mass matrices, by a deterministic Python backend; the language model only orchestrates. Open source, no Mathematica. Stops before observables; dark matter only as motivation (minimal dark matter multiplets) | Path 1 front end: DM8's intake and model checks, with the same division of labour |
| HEP-CoPilot | arXiv:2605.02491 | retrieval over papers and HEPData; rebuilds exclusion limits | constraint agent |
| Albert | arXiv:2603.28935 (abstract) | a transformer with reinforcement learning searches theories against LEP data | Path 2 in spirit |
| Program synthesis for simulation-based inference | arXiv:2607.17540 | a language model proposes simulators, scored by density estimation | tournament method |
| llm4smeft | arXiv:2608.04100 (abstract) | proposes which effective operators to fit | operator hypotheses |
| LeWRON | arXiv:2606.19425 | Lagrangian → phase transition → gravitational waves, with auditor agents | design pattern |
| Agentic Re-Casting | arXiv:2607.22813 | agents update a global collider analysis with a physicist in the loop | collider recast |
| EasyScan_HEP 2 | arXiv:2606.31214 | an agent-addressable parameter-scan framework | scan layer |
| Agentic Diagrammatica | arXiv:2603.26990 (abstract, 2026-10-02) | a HEPTAPOD extension: the agent writes a compact diagram specification and a trusted backend computes (FeynCalc for tree-level amplitudes, naive dimensional analysis for estimates); "tool-constrained computation" | bespoke amplitudes; the same principle as DM8's derivation (the agent writes a typed specification, code derives) |
| Reining in an Agentic Harness for HEP | arXiv:2609.00107 (abstract) | position paper: versioned tools and machine-readable contracts | design guidance |
| "Plausible but Wrong" | arXiv:2604.25345 | a cosmology agent fails silently with plausible posteriors | a caution |

Other agent systems, with low overlap: MadAgents (arXiv:2601.21015),
SMEFT-Pheno-Agent (arXiv:2607.22331, abstract), JFC (arXiv:2603.20179,
abstract), CMBAgent (arXiv:2507.07257), Denario (arXiv:2510.26887), The AI
Cosmologist (arXiv:2504.03424), DeepInflation (arXiv:2601.14288), and the
stocktake arXiv:2609.32874 (abstract). Checked at abstract level, with their
PDFs searched for direct detection, nuclear recoils, operators and dark matter
(2026-10-02):
- **HEPTAPOD**, Menzo et al., arXiv:2512.15867: an orchestration layer between
  language models and HEP tools. Its case study validates a BSM Monte Carlo
  signal from model generation (FeynRules, UFO) through MadGraph to analysis,
  with provenance and human oversight. Overlap: the pipeline of DM8's
  numerical cross-check; no direct detection.
- **ArgoLOOM**, Bakshi et al., arXiv:2510.02426: an agentic framework joining
  cosmology (CLASS), collider (MadGraph) and nuclear-science tools around a
  retrieval knowledge base, shown on two small problems. Dark matter appears
  only in passing (sterile neutrinos, supersymmetric candidates for CLASS).
- **PhysMaster** and **PRL-Bench**, Miao et al., arXiv:2512.19799: a general
  physics agent (tree search over trajectories, hierarchical memory), and a
  benchmark of 100 Physical Review Letters reproductions. It finds agents
  unreliable over long research workflows. Relevant to DM10's evaluation
  design, not to the physics.
- **Collider-Bench**, Faroughy et al., arXiv:2605.13950: a benchmark of agents
  reproducing LHC analyses from public papers and open software. It scores
  yields by histogram metrics, reports the cost of each task, and has a model
  judge check traces for fabrication. No agent reliably beats the
  physicist-in-the-loop solution. Relevant to DM10: its reproduction tasks
  parallel the limit-reproduction suite, its cost reporting parallels the
  baselines' accounting, and its fabrication check parallels DM9's reference
  check.

**Scan of 2026-10-02.** None of the seven systems in the owner's list
(ArgoLOOM, HEPTAPOD, PhysMaster, FERMIACC, Agentic Diagrammatica,
Collider-Bench, bsm_agent) mentions direct detection or nuclear recoils.
- **FERMIACC** is the closest to Path 2: excess → hypotheses → simulated test,
  on LHC excesses, including the historical 750 GeV diphoton excess. It
  differs from ADROIT in three ways:
  - its hypotheses are free model-building by a language model (sampled at
    several temperatures, de-duplicated), where ADROIT's are a fixed library
    with a menu-constrained variant agent;
  - it tests each hypothesis on its own analysis by agentic recasting
    (MadAnalysis 5, HEPData), with no ranking of a library, no degeneracy
    classes and no combination with null searches;
  - it builds models through FeynRules, which needs Mathematica.
- **The shared principle** (the language model orchestrates, deterministic
  code computes) is now common: FERMIACC, bsm_agent, Diagrammatica and
  HEPTAPOD all state it. The paper should present it as shared practice, not
  as ADROIT's contribution.

## Prior physics closest to Path 2

All at *record* level. These are the analyses the system's results should be
compared with, and several are candidate test cases for DM10.

| work | what it did |
|---|---|
| arXiv:2512.05850 (DIAMX) | combined profile-likelihood fits of high-energy recoil events in LZ, PandaX-4T and XENONnT, comparing velocity-dependent and inelastic interactions; the closest antecedent |
| Catena, Gondolo, arXiv:1405.2637 | global fit of the nonrelativistic operators to direct-detection data |
| Avis Kozar, Scott, Vincent, arXiv:2310.15392 | operator global fit over 13 experiments plus solar neutrino limits |
| Catena, Ibarra, Wild, arXiv:1602.04074 | DAMA against the null searches across the operator basis |
| Kang, Scopel, Tomar, Yoon, arXiv:1804.07528 | DAMA/LIBRA phase 2, operator by operator |
| Gluscevic et al., arXiv:1506.04454, 1406.7008 | Bayesian model selection among operators from simulated signals |
| Arina, Hamann, Wong, arXiv:1105.5121 | Bayesian evidence for DAMA and CoGeNT against null results |
| GAMBIT, arXiv:2106.02056, 2209.13266, 2303.08351 | effective and simplified models with direct, indirect, collider and relic constraints together |
| Brenner et al., arXiv:2203.04210 | direct detection and neutrino telescopes, operator by operator |
| Bozorgnia et al., arXiv:1810.05576 | a wider energy window improves operator discrimination |
| Baum et al., arXiv:1709.06051 | a xenon signal combined with collider monojet searches |
| Bloch et al., arXiv:2006.14521; GAMBIT, arXiv:2007.05517 | survey and global fit of explanations of the XENON1T excess |

## Interpretations of the LZ event

INSPIRE listed 106 records citing arXiv:2609.02823 on 2026-09-29. Most argue
for one model. None runs the full operator basis against all constraints in
one ranked comparison. All entries are at *record* level.

**Closest to Path 2:**
- arXiv:2609.15985: a Bayesian posterior over mass, splitting and interaction.
- arXiv:2609.21823: LZ's elastic operators, with solar neutrino limits per
  operator.
- arXiv:2609.14799: boosted against inelastic, with the same operators.
- arXiv:2609.09230: interference in the isovector L6 operator; xenon against
  argon.
- arXiv:2609.04175, 2609.04673, 2609.26698: tests against the energy
  sidebands.
- arXiv:2609.05291, 2609.16529: nuclear excitation channels and responses.
- arXiv:2609.04186: the elastic pseudoscalar L4 interaction.
- arXiv:2609.15782: argon as a discriminator.

**Recurring tests in this literature,** which the tournament should contain:
the low- and high-energy sidebands, capture in the Sun, dependence on the
tail of the halo, and complementarity between targets.

**By class** (identifiers from the survey):
- Solar capture: 2609.02775, 2609.06760, 2609.07807, 2609.11833, 2609.15321,
  2609.10636, 2609.28218, 2609.28129, 2609.32435, 2609.19174.
- Halo and kinematics: 2609.21444, 2609.35737, 2609.04181, 2609.15634,
  2609.02608, 2609.35650, 2609.17935.
- Boosted dark matter: 2609.06756, 2609.06890, 2609.07742, 2609.11600,
  2609.24982, 2609.29462.
- Elastic with a non-standard form factor: 2609.25114, 2609.25723.
- Higgsino and electroweak multiplets: 24 papers, among them 2609.01583 and
  2609.28740.
- Inelastic model building: 37 papers, among them 2609.05204 and 2609.07225.
- Not dark matter: neutron disappearance, neutrinos, absorption, modified
  gravity (8 papers).
