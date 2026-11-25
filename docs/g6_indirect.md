# G6 — Annihilation today and indirect detection for a generic model (2026-10-14)

Milestone G6 of [`freeze_out_build.md`](freeze_out_build.md). A typed model computed by the generic route (G4) now
annihilates today, channel by channel, into every indirect search the library has: the dwarfs, the CMB,
antiprotons, the Sun and the lines. Where the photons come from a new state's decays, the spectrum is built from
two-body cascades. Where long-range effects matter today, the searches are undecided until G8.

## What was built

**σv today by final state** (`adroit/parameter_space/portals/generic_id.py`, `GenericModel.sigma_v_today`). For
DM DM̄ → c d, G3 gives σ at s = 4m²/(1 − (v/2)²), with v the relative speed, and σv is in cm³/s. W and Z pairs near
and below threshold are integrated off shell, as in Ωh². Standard Model pairs carry the searches' names (b, tau, W,
Z, hh, Zh, gamma, Zgamma, …). The existing `s_wave` takes the s-wave part from two speeds.

**The Higgs's loop-induced channels** (gg, γγ, Zγ). Where the pair couples to a Higgs-like scalar S (a state with
an H⁰ component), the rate into X is

    σ(→ X) = σ(→ S* → b b̄) × Γ(h* → X)/Γ_tree(h* → b b̄),

all at √s. Here σ(→ S* → bb̄) is G3's, through the Higgs-like scalars only and with their interference kept. Γ(h* → X)
is the library's. This holds where S couples to quarks and gluons as the Higgs does. The same channels now enter
Ωh² as well.

**Cascades through new states** (decision D13). A final state with a new Z₂-even state X is named by its particles
("s0 s0", "h s0"). Its photons are a two-body topology (`spectra.Daughter`, mode `two_body`):
- a Standard Model daughter showers at its own energy E = (4m² + m_X² − m_Y²)/4m, as half of PPPC's pair spectrum;
- a new daughter decays at rest by G2's two-body widths and is boosted to E. Its decays go into Standard Model pairs
  or into the dark matter (`invisible`, no photons).
- a Higgs-like X also decays into gg, through the Higgs's loop as above. Its γγ and Zγ (about 0.2%) are left out:
  the spectra have no column for a boosted line.

A decay into other new states (a longer chain), or into a pair that PPPC does not tabulate, leaves the channel
without a spectrum. The searches then bound it by their conservative mixture rules where they have one.

**The CMB.** A cascade's f_eff is given as a range (`cmb_f_eff_range`). Each daughter's shower takes the lowest
and highest f_eff over the energies it can have, from Slatyer's table, weighted by its branching fraction and its
share of the energy. The search decides where the whole range does. When it decides, it gives no single ratio, so
the likelihood does not use one. Neutrinos and invisible decays deposit nothing (`NO_ENERGY`).

**Lines.** The Higgs's γγ and Zγ come from the loop factor above. Any other line is loop-induced and not computed
here. A model whose dark matter carries gauge charge, or couples to charged states, is flagged:
"γ-ray lines are loop-induced and are not computed for the generic route (G8)".

**Long-range effects today** (`today_unknown`). The dark-matter pair's most attractive channel is found from G4's
bracket: its forces and its irreducible representations. Its Sommerfeld factor S is evaluated at the dwarfs'
v = 10⁻⁴. Where S > 1.1, every search that needs annihilation today is undecided, with the reason "needs the
Sommerfeld effect today (G8)". The wino and Feng & Smolinsky's dark-photon model are undecided. The Higgs portals
are not.

**Decision D11, done with G6:**
- **A Majorana mass of a Dirac field** (G1, `gauge_basis._majorana_type`). The term
  −½δ(\overline{ψᶜ}ψ + h.c.) splits a Dirac ψ of mass M into Majorana states M ± δ. A current
  \overline{Ψ_aᶜ}ΓΨ_b of the two is mapped into the holomorphic basis. Tests: the pseudo-Dirac spectrum, and
  inelastic scattering in G5 (`test_spectrum.py`, `test_generic.py`).
- **The pole refinement's cost** (`generic._pair_sigma`). Each channel is first probed on shell at its pole centres
  and at u = 0.01, 0.1 and 0.5. It is then tabulated once, finely where a pole matters and sparsely elsewhere. The
  off-shell quadrature, the dominant cost at about 0.2 s a node, now runs only at nodes spaced at least a quarter of
  the narrowest width apart. Above the on-shell threshold the off-shell/on-shell ratio is interpolated.

**The Standard Model's bosons are now the library's.** Four changes:
- **M_H.** G1 takes M_H = 125.09 GeV (it had 125.0). With m_DM ≈ M_H/2, Athron et al.'s point had been ×4 off.
- **Running masses.** G2's Yukawas and G5's matching use m_b and m_c run to M_H (`feynman.yukawa_mass`), as the
  library's widths do. The pole masses had given bb̄ ×1.9 and cc̄ ×3.6.
- **The W and Z widths.** G2's tree-level widths (2.044 and 2.440 GeV) were 2% below the measured ones that the
  library uses (2.085 and 2.4952). The far tail of an off-shell W or Z scales with its width. The generic route now
  multiplies the W's and Z's widths into Standard Model states by Γ_measured/Γ_tree, so a Z mixed with a Z′ keeps
  its reduced couplings, and adds their tree-level decays into new states (`generic._with_higgs_width`).
- **The off-shell quadrature** (`ufo._breit_wigner`, shared with the library's UFO portals). The far tail of the
  Breit–Wigner, a fraction of a percent of the measure, had no node. There the other boson can be on its shell, so
  χχ → VV* lost about half its rate below the VV threshold. Each tail is now a segment of its own, with a square-root
  substitution at the kinematic limit. It is within 1.8% of an adaptive integral (below). **This changes the
  library's UFO portals too** wherever they integrate W or Z pairs off shell.

## Validation

**Against the library engines' σv today** (v = 10⁻³; `test_generic.py`):

| control | agreement |
|---|---|
| GAMBIT's Dirac Higgs-portal EFT | every channel within 2×10⁻³: W, Z, hh, tt̄, and the loop-induced γγ (3.36×10⁻³¹ cm³/s) and Zγ (2.28×10⁻³¹) |
| Das et al.'s singlet mixing (BP8) | W, Z, gg, γγ and Zγ within 0.5%; ττ +0.9%; bb̄ −1.8% and cc̄ +33% (the library runs m_q to √s, the generic route to M_H) |
| the vector Higgs portal (Athron et al., 62.5 GeV) | gg, γγ, Zγ exact, ττ +0.9%; bb̄ −7%, cc̄ +25% (running, as above); WW* and ZZ* −3.9% |

At √s ≈ M_H the library's Γ(h* → VV) is the Higgs Working Group's, which includes the higher orders. Against the
exact leading order (the adaptive integral below), it is 3.6% higher for W and 2% for Z. The generic route is
leading order, so its WW* and ZZ* sit 3.9% below. Das et al.'s cascades, h₁h₂ and h₂h₂ in the library, are "h s0"
and "s0 s0" in the generic route, and are compared with MadDM below.

**Against MadDM** (decision D14; `maddm.indirect`, `test_maddm_gives_the_generic_annihilation_today`). This is
MadDM's tree-level 2 → 2 σv today (`generate indirect_detection 2to2lo`, `sigmav_method inclusive`), offline. No
download was needed: the 'sigmav' mode needs no spectra, so Pythia 8 and DRAGON were not installed. PPPC4DMID's
tables are in MadGraph's folder, extracted at 01:18 on 14 October by MadDM's unrequested fetch. G5's clean-up
removed that fetch's archive but not the extracted tables. With D14's approval they are kept. MadDM's first-run tool prompt is answered by setting
`maddm_first_indirect False`, which MadDM saves in MadGraph's configuration.

**Two conventions of MadDM's**, found and corrected in `maddm.relative`:
- its 2 → 2 mode gives each particle the momentum m·u, with u = √3 v_halo, and multiplies σ by u. So it prints
  ½σv_rel at v_rel = 2u. A uniform factor of 2 on every channel, s- and p-wave alike, settles this reading;
- it converts with c = 2.99×10¹⁰ cm/s (`pbtocm3`), 0.27% low.

| model | dark matter | channels | generic / MadDM |
|---|---|---|---|
| real-scalar Higgs portal (305 GeV) | real scalar | W, Z, hh, tt̄, bb̄, cc̄, ττ | 0.9999 on each |
| complex scalar with a Z′ (300 GeV) | complex scalar | uū, dd̄ | 0.9999 |
| GAMBIT's Dirac EFT (9.9 TeV) | Dirac | W, Z, hh, tt̄ | 0.9999 |
| a singlet–doublet Dirac model (200 GeV) | Dirac | Zh, W, Z, every fermion, ν | 0.9999–1.0000 (ν: ν_e only, see below) |
| Das et al. BP2 (242 GeV) | Dirac | the cascades S S and h S (p-wave) | 0.9999 |
| a Majorana χ with a Higgs-mixed S (200 GeV) | Majorana | W, Z, hh, tt̄, bb̄, ττ, cc̄, S S, h S | 0.9999 |
| the vector Higgs portal (62.5 GeV) | vector | bb̄, ττ, cc̄, ss̄, μμ, dd̄ | 0.9999; WW* and ZZ* are 0 in MadDM (on shell only) |
| Choubey et al. BP1 (87.6 GeV) | Majorana | W⁺W⁻ | 0.933; on shell 0.99994 |
| Dedes & Karamitros t0 (110 GeV) | Majorana | W⁺W⁻, ZZ | 0.952, 0.933 |

Every tree-level matrix element agrees to 10⁻⁴: Dirac, Majorana, real, complex and vector dark matter, s- and
p-wave, cascades included. The differences are all in W and Z pairs within 30 widths of their threshold. There the
generic route integrates the bosons off shell, and MadDM's 2 → 2 mode does not. On shell, Choubey et al.'s W⁺W⁻
agrees to 6×10⁻⁵.

**The finite-width treatment** (`ufo.off_shell_sigma`). Its integrand is G3's σ at the bosons' virtualities times
a running-width Breit–Wigner for each. For a Higgs-like s-channel this is the leading-order four-fermion width with
massless fermions, which is HDECAY's double Breit–Wigner. Compared with an adaptive integral of that formula (the
real-scalar Higgs portal; the library's own Γ(h* → VV) used for the normalisation):

- **The integrands are the same:** G3's σ at the virtualities (q₁, q₂), times q₁²q₂²/M⁴ from the running widths, is
  proportional to HDECAY's Γ₀(q₁, q₂) to 10⁻⁷ at every point tried.
- **The quadratures agree.** The generic route uses 10 Gauss nodes a segment. Against an adaptive integral (the
  real-scalar Higgs portal; ours / the adaptive integral):

| √s (GeV) | W, 10 nodes | W, 40 nodes | Z, 10 nodes | Z, 40 nodes |
|---|---|---|---|---|
| 126.9 | 0.9967 | 0.9995 | 0.9900 | 0.9996 |
| 148.2 | 0.9895 | 0.9985 | 0.9822 | 1.0035 |
| 163.4 (1.3 Γ_W above the WW threshold) | 1.0083 | 1.0102 | 0.9873 | 0.9993 |
| 174.9 | 1.0008 | 1.0013 | 0.9913 | 0.9940 |
| 225.3 | 1.0003 | 1.0000 | 1.0005 | 1.0002 |

  At 10 nodes the error is at most 1.8%, below threshold; 40 nodes would cost about 16 times as much. These numbers
  are with the measured W and Z widths (above). With G2's tree-level widths the route was a further 2% low below
  threshold, which is how that difference was found.
- **MadDM merges identical neutrino final states** (found 2026-10-15, `docs/g7_long_range.md`): it generates
  χχ → ν_μν̄_μ and ν_τν̄_τ but writes them out with ν_eν̄_e as one process and counts one flavour. The ν row
  above therefore compares ν_e alone; ν_μ and ν_τ were absent from MadDM's list, not compared. None of the relic
  cross-checks with MadDM (G4; the portal library's P2) has νν̄ near freeze-out, so they are unaffected. A B − L-like
  Z′ model, where νν̄ is a sixth of the rate, shows the effect: MadDM's Ωh² is 15% high.
- **The differences from MadDM are finite-width physics.** For h* → WW, HDECAY's double Breit–Wigner at
  √s = 175 GeV is 0.944 of its on-shell value. Choubey et al.'s χχ → WW at the same √s is 0.933 of on shell.

- **Far above threshold**, both sit about 1.6% below the narrow-width limit, because a Breit–Wigner on q² ≥ 0 has
  weight 1 − Γ/πM. This is a convention at the approximation's own order, Γ/M. The generic route switches to on
  shell at 30 widths, and the library's Higgs at 40.
- **The library's own** double Breit–Wigner (a 400-node trapezoid in arctan) is coarse below threshold: +2% for W
  and −7% for Z at 125.09 GeV. It is anchored to the Higgs Working Group's widths there, which absorbs the error at
  M_H but not elsewhere.

**The cascade spectra against PPPC's own**, where both exist:
- two identical daughters are the scalar class's SS cascade, to the bit;
- at threshold (X at rest), a cascade is two of PPPC's pair showers at m_X/2 (`test_cascade_at_threshold…`);
- a Standard Model daughter is half of PPPC's pair shower at its own energy (Zh as ½ZZ + ½hh).

**The gate: every search reads a generic model.** `scan.evaluate` runs on a generic Higgs portal (GAMBIT's EFT)
and on the cascade model above, with every search and without an exception (`test_every_search_reads_a_generic_model`).
The cascade model's verdicts:
- **dwarfs:** allowed, at 0.14 of the 2015 limit, through the mixture rule;
- **the CMB:** below its reach;
- **the Sun:** allowed;
- **lines:** undecided (overlapping Fermi lines need a two-line likelihood);
- **antiprotons:** undecided, since the mixture rules have no entry for a cascade;
- **the LHC:** pending (G9).

**The zoo's development half**, rerun with G6 (2026-10-14, `runs/eval/model_zoo.jsonl`; the last run after D12's
retarget and D18's replacement entry):

| | G5 | G6 |
|---|---|---|
| new models computed | 4 of 6 | 5 of 6 |
| new targets compared, met | 9, 4 | 10, 9 |
| controls' targets met | 11 of 15 | 11 of 15 |
| generic route agreeing with the controls' engines | 8 of 10 | 8 of 10 |

- **Feng & Smolinsky** (D9, perturbative as the paper): Ωh² = 0.073 and 0.069 against 0.120 ± 0.070, both met.
- **Dedes & Karamitros t1:** 0.157 → 0.134 (target 0.12), now met. This is the off-shell fix: the point is just
  below its WW threshold. t0 moves 0.1348 → 0.1358.
- **Choubey et al.:** σ_SI 8.57×10⁻⁴⁸ against the retargeted 8.22×10⁻⁴⁸ (D12, below), now met. t0's Ωh²,
  0.0818 → 0.0821, is still not met.
- **The controls' engines** are unchanged. Of the generic route's values, Athron et al.'s moved: 0.0572 → 0.0708
  at t0, against the library's 0.0673 (−15% → +5%), after G6's changes together (M_H = 125.09 GeV, the gg channel,
  the off-shell fix). The two disagreements are still Das et al.'s BP2 and BP9, where the library drops the
  trilinears (G4).
- **Yaguna's singlet–doublet Dirac model** (D18, replacing the withdrawn entry): the splitting at M_χ1 = 200 GeV
  is 0.0536 against "of order 6%" (0.06 ± 0.01), inside the band of the paper's Fig. 2 (about 0.048–0.054). The
  largest dark matter mass is 730 GeV against "of order 750", beside the paper's analytic 733. Both met.
- **The complex scalar triplet** is refused for the Sommerfeld effect (G7), as before.

## Decision D12: the papers re-read

The owner's decisions on the re-read (2026-10-14):

- **Choubey et al.: retargeted.** Table IV's σ_SI is a quarter of the paper's own eq. (23), σ = 4μ²f²/π for
  Majorana dark matter, at every benchmark point (eq. (23)/table = 3.92, 3.90, 3.97, 3.52, 3.98). It matches the
  Dirac μ²/π with the Majorana coupling. The target is now eq. (23) at BP1's inputs, 8.22×10⁻⁴⁸ cm² (it was
  2.1×10⁻⁴⁸); the entry's notes say so. ADROIT gives 8.57×10⁻⁴⁸, 4% above: f_N = 0.3066 against the paper's 0.3.
  BP1's Ωh² is unsettled. It moves by its target's spread with a 0.65 GeV shift in m_DM, 1.4 GeV in M_h2, or
  sin δ ≈ 0.026.
- **Dedes & Karamitros: kept as quoted.** t1 is the paper's text (m_χ ≃ 91, m ≃ 140). That point lies about 1 GeV
  outside Fig. 7b's plotted region, whose 0.12 contour passes near M_D = M_T = 92 GeV, m ≈ 138.5 GeV. The text is
  the paper's own statement, and the entry already notes that the point is read with "≃" at M_D ≈ M_Z, which the
  authors do not treat. Moving it now that it is met would be an edit after seeing a result, so the re-read is a
  note only.
- **The singlet–doublet Dirac entry** is withdrawn and replaced (D18): Yaguna's singlet–doublet Dirac model,
  arXiv:1510.06151 (`docs/model_zoo.md`).

## Found on the way

| what | where | effect |
|---|---|---|
| The off-shell quadrature's far tail had no node | `ufo._breit_wigner` (shared with the library's UFO portals) | χχ → VV* about half its rate below threshold |
| M_H = 125.0 in G1 | `gauge_basis` | Athron et al.'s point (m_DM ≈ M_H/2) ×4 |
| Pole masses in the Yukawas | G2, G5 | bb̄ ×1.9, cc̄ ×3.6 against the library's Higgs |
| Tree-level W and Z widths | G2 (the generic route) | χχ → VV* about 2% low below threshold |
| The Majorana current of one self-conjugate field was charged under its U(1) (D10) | G1, `indices.check_invariant` | fixed; Okada et al.'s entry is not blind at G7 |
| MadDM 3.3's madevent route for indirect detection does not compile with MadGraph 3.8 (`vecsize_memmax`) | MadDM | the 2 → 2 inclusive mode is used |
| MadDM's `maddm.out` keeps 12 characters of a process name, and MadDM's own parser fails when the cut removes the "_" | MadDM | `maddm.indirect` reads the names from `process_names.inc`. Both UFO writers give a name longer than five characters a code for MadGraph (n1, n2, … in the export; dm1, … in DM8's writer; `ufo.code_name`). Dedes & Karamitros's dark matter is now n3 |
| The 2024 dwarf recast refuses a channel set with a γ-ray line (γγ, Zγ) | `spectra.from_rates` (library) | by design, now with the reason: its released likelihoods read dΦ/dE at each bin's reference energy, which a line does not have. The 2015 mixture rule counts the line's photons in their bin (`spectra.binned`), rigorously (convexity and monotonicity of the likelihood), so it decides these mixtures; only where it cannot do they stay undecided. No record's use changed |

## Limits

- σv today is tree level, plus the Higgs's loop-induced channels through Higgs-like scalars. Other loops (a charged
  or coloured state's γγ, gg) are not computed; the lines are flagged.
- Cascades are two-body. A chain through a second new state, or into an untabulated pair, has no spectrum.
- A cascade's f_eff below Slatyer's first tabulated mass for a channel is taken at that mass.
- Antiprotons have no mixture rule for a cascade: undecided (the owner, D17). The published limits are for pure
  channels, and no proxy bounds a cascade's spectrum in every bin.
- A mixture with a γ-ray line is decided by the 2015 dwarf curves' mixture rule or stays undecided (the owner, D16);
  the 2024 recast cannot hold a line.
- The Sommerfeld effect today is refused (G8).

Tests: the G6 section of `tests/parameter_space/test_generic.py`, additions to `tests/constraints/test_spectra.py`,
`tests/parameter_space/test_searches.py` and `tests/constraints/test_maddm.py`.
