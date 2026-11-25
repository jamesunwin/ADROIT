# ADROIT: phase 2 and future ideas

Ideas that are outside the build (`adroit_build.md`, whose status section
covers DM0–DM15, the portal library, the M-series and the release plan
R0–R12). Started 2026-09-29;
revised 12 October 2026. Add to it as ideas arise; nothing here is scheduled.
Items built since they were listed have been moved to the last section, with
where they were built.

## Set aside by the owner's decisions of 2026-09-29

- **Electron recoils and the Migdal effect.** ADROIT covers nuclear recoils
  only.
  - Candidate tools: DarkELF, QEdark, QCDark, obscura, EXCEED-DM.
  - This would bring in the XENON1T electron-recoil excess as a test case.
- **Other classes of constraint as full calculations.** Most are now built
  (last section). What remains:
  - beam dumps and fixed-target experiments for light mediators other than
    the dark photon (scalars, ALPs);
  - positrons, and indirect detection for bespoke Path 1 models;
  - collider recasts of bespoke spectra (CheckMATE, MadAnalysis 5);
  - flavour: meson mixing, lepton flavour violation, CP, and rare decays such
    as K → π X;
  - cosmology beyond the standard history (below).
- **Bayesian evidence** as a cross-check of the profile-likelihood ranking.

## Ideas from the design discussion and the literature survey

- **Halo-independent analysis.** Compare experiments without assuming a
  velocity distribution.
- **Alternative halo models as library entries:** debris flows, streams, the
  Large Magellanic Cloud's effect on the high-speed tail, a dark disc. A run
  can already take a tabulated speed distribution (`HaloModel`, DM2); none of
  these halos is a library entry.
- **Halo uncertainties as nuisance parameters** in the fits. Not built; Path 2
  flags a leader's sensitivity to the halo instead (DM6; `adroit_build.md`,
  status).
- **Annual and daily modulation as observables,** and a DAMA module with its
  NaI comparators (COSINE-100, ANAIS). The rate's annual modulation is
  computed (`physics/rates.annual_modulation`, DM2); its use in fits and a
  DAMA module are not built.
- **Directional detection.**
- **Signals that are not dark matter, as candidates in the tournament.** The
  LZ literature proposes neutron disappearance, neutrinos and absorption.
- **Boosted dark matter,** which changes the flux and not only the
  interaction.
- **Nuclear uncertainties as nuisance parameters:** shell-model
  uncertainties and chiral corrections to the responses. Path 2 flags a
  leader's sensitivity to the nuclear model (a refit with the published shell
  model, DM6); nothing is profiled.
- **Nuclear excitation channels,** as companion signals to an inelastic
  interpretation.
- **Operator interference in the fits.** The rate already handles any
  combination of operators, with every interference (DM2). The library's
  relativistic cards and user models (DM14) enter the fits with their fixed
  operator combinations. Fitting free relative coefficients of several
  operators, with the tournament ranking the combinations, is phase 2.
- **Spin-1 dark matter operators** O₁₇–O₂₀ (arXiv:1505.03117). The rate
  handles O₁ and O₃–O₁₅ for any spin (DM2).
- **Better nuclear input for isotopes without shell-model responses:**
  - ¹⁸³W, which has no spin-dependent response since DM3 (the owner's
    decision: no shell-model structure function exists, and the published
    estimates of ⟨S_n⟩ span a factor of six; `physics/data/isotopes.yaml`);
  - the spin values of ²⁹Si, ⁴³Ca and ¹³C, which are omitted now.
- **Automatic ingestion of limit curves and data releases,** with human
  verification (compare arXiv:2606.21658). Built in part for private sources
  (last section); the packaged records are still curated and verified by
  hand.
- **The constraint loop of DarkAgents:** a missing analysis flagged by the
  constraint agent triggers a deterministic calculation whose result returns
  to it.
- **Forecasts for planned experiments** (XLZD, DarkSide-20k, PandaX-xT, argon
  and xenon together).
- **The neutrino fog,** as a background model and a limit on discrimination. *Built 2026-10-19 as an overlay and an
  annotation ([neutrino_fog.md](neutrino_fog.md)); as a background in a likelihood, not built.*
- **The relic density below m_DM ≈ 10 GeV** (DM7, accepted by the owner
  2026-10-01). Freeze-out there happens near the QCD transition. It needs:
  - lattice-based degrees of freedom in place of the ideal gas
    (`constraints/relic.py` still uses the ideal gas);
  - annihilation into hadrons rather than free quarks (built below 2 GeV for
    photon-like couplings and B − L: portal library part 3,
    `constraints/hadrons.py`);
  - a reference that resolves low masses: a figure with a logarithmic mass
    axis, or a comparison with micrOMEGAs or MadDM, both now installed
    (micrOMEGAs 7.1.10 as the second relic code of part 3; MadDM for DM8's
    cross-check).

  CMS's contours there could not be read precisely enough to test it
  (`dm7_constraints.md`, section 3).

## Language models

- **More uses of the optional consistency check.** Reading papers into drafts
  is built in part (last section). Not built: a draft of a complete
  experiment module, with its reproduction of the published limits, and a
  draft card for the packaged library. Each draft would be verified by a
  person.
- **Local models,** so that the optional checks can also run at no cost.

## The viability checklist's later items (2026-10-01)

The owner's 28 checks for freeze-out dark matter are in every Track 1,
single-idea and Path 1 report, each with its status
(`adroit/constraints/data/viability.yaml`, refreshed in R8). The items that
remain for phase 2:
- **Light dark sectors:**
  - beam dumps and fixed-target experiments for mediators other than the dark
    photon;
  - rare meson decays other than B → K + invisible (K → π X and others);
  - stellar and supernova cooling;
  - self-interactions with light mediators (velocity-dependent, beyond
    Born); a heavy-mediator Born estimate is built;
  - scattering with the cosmological plasma;
  - free streaming;
  - electron recoils, and light mediators in bespoke models.
- **Theory and cosmology:**
  - Sommerfeld enhancement and bound states with light-mediator (Yukawa)
    potentials, for the general classes;
  - non-standard cosmological histories (early matter domination, late
    entropy release);
  - the temperature and fate of a secluded sector (now: annihilation into
    mediator pairs, with prompt decays assumed);
  - flavour observables: meson mixing, lepton flavour violation, CP;
  - electroweak precision data (S, T, U) and dipole moments;
  - decay through symmetry-breaking operators;
  - the vacuum of scalar potentials other than the complete scalar portal's;
  - the running of couplings for the other classes;
  - the thermal-relic unitarity bound for m_χ above 10 TeV.
- **Beyond freeze-out:** freeze-in and other non-thermal production, once
  the owner widens the working assumption.

## Built since these lists were written

- **Indirect detection beyond DM7:**
  - the CMB: Planck's limit on p_ann with Slatyer's f_eff (portal library
    part 2, extended below 5 GeV in part 4);
  - γ-ray lines from Fermi-LAT and H.E.S.S., and AMS-02 antiprotons (part 4);
  - mixed and cascade photon spectra, with a dwarf-galaxy spectral likelihood
    ([`mixed_cascade_spectra.md`](mixed_cascade_spectra.md));
  - conservative rules for channel mixtures, and conservative, central and
    aggressive propagation models for antiprotons (the owner's follow-ups of
    2026-10-11, the release plan).
- **Collider recasts in place of published summaries:**
  - SModelS 3.2.1 (part 3), with MadGraph's production cross-sections
    (part 4);
  - dedicated resonance and mono-X recasts (parts 2, 4 and 5; revised in R4);
  - the mono-h band calibrated with MadGraph beyond ATLAS's benchmark (the
    owner's follow-up of 2026-10-12).
- **Beam dumps and fixed-target experiments, for dark photons,** through
  DarkCast (part 2).
- **Flavour and rare decays:** B → K + invisible (part 2, restricted in R4);
  BaBar and Belle II on L_μ − L_τ (part 2); the CCFR neutrino trident
  (part 3).
- **Cosmology:** the BBN and N_eff bounds on light states (part 3).
- **Precision:** the invisible Higgs and Z widths (part 1), the muon g − 2 and
  LEP-II contact interactions (part 2).
- **Sommerfeld enhancement and bound states** for electroweak multiplets and
  coloured or charged t-channel partners (part 2; the wino's bound state in
  part 3; `constraints/sommerfeld.py`).
- **Theory certificates for the complete scalar portal:** the vacuum (M24),
  partial-wave unitarity (M25), one-loop running (M26), and the metastable
  vacuum's tunnelling lifetime (the owner's follow-up of 2026-10-11,
  `theory/vacuum_decay.py`).
- **Reading papers with a language model,** each draft for a person to check:
  - an anomaly's paper into a draft anomaly record (`adroit anomaly draft`,
    DM14);
  - an experiment's paper into a private dossier (`adroit experiments
    extract`, M36.5c), with source review, independent validation and per-run
    selection in M36.5d–h;
  - a paper's equation into a typed model for the personal catalog (`adroit
    models paper`, M37.5).
- **Ingesting papers and data, in part:** papers, supplements and tables are
  imported into private, dated drafts (M36.5a–b;
  [`experimental_source_ingestion.md`](experimental_source_ingestion.md)).
- **¹⁷O's spin values:** CRESST's ⟨S_n⟩ = 0.5, which cites the shell model of
  Pacheco & Strottman (DM3; `physics/data/isotopes.yaml`).
