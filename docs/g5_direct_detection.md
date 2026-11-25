# G5 — Direct detection for a generic model (2026-10-14)

Milestone G5 of [`freeze_out_build.md`](freeze_out_build.md). A typed model computed by the generic route (G4) now
scatters on nuclei: at tree level from its own Feynman rules, through a loop library where the tree level vanishes,
inelastically where a neutral partner is within reach, and otherwise "loop-dominated, not computed".

## What was built

**Tree-level matching** (`adroit/model_building/dd_matching.py`). At zero momentum transfer the dark matter χ
scatters on a quark through:
- **Every neutral Z₂-even boson X:** the h, the Z, a Z′ or dark photon, or a new scalar, mixed mass eigenstates
  included. The exchange gives (χ̄Γχ)(q̄Γ′q) × (+1/m_X² for a scalar, −1/m_X² for a vector).
- **Every Z₂-odd coloured scalar partner φ of fermion dark matter**, L ⊃ φ*χ̄(y_L P_L + y_R P_R)q + h.c. It is
  Fierz-rearranged with the identity for anticommuting fields,
      (χ̄P_R q)(q̄P_L χ) = −½(χ̄γ^μP_Lχ)(q̄γ_μP_Rq),
  which was checked numerically with explicit γ matrices.

The result is written in DirectDM's quark- and gluon-level basis at μ = m_Z with five flavours: C61q…C64q, C71…C78q
for fermions; C61q…C64q, C65, C66 for scalars. The top is integrated out onto the gluon operators.

**One formula for every dark-matter type, in vertex terms.**
- DirectDM's Majorana and real-scalar operators carry a factor ½ (`maddm.expected_alpha`).
- G2's vertex of a Majorana or real field is twice its Lagrangian coefficient.

So C = (χ vertex)(q vertex)/m_X² × sign throughout. A partner's Yukawa joins two different fields and carries no
such 2, so for Majorana χ its axial and scalar Fierz terms are doubled explicitly.

**Nucleon couplings at q → 0** (`nucleon_couplings`), in ADROIT's normalisation (σ_SI = c₁²μ²/π, σ_SD = 3c₄²μ²/16π):
- **c₁ᴺ** from DirectDM's own sigma terms (σ_u^p = 0.017, σ_d^p = 0.032, σ_s = 0.0529 GeV) and m_G = 0.836 GeV.
  These give f_N = 0.3066, the library's F_N = 0.307.
- **c₄ᴺ** from the LHC DM Working Group's Δq, as the library's spin-1 portals use.
- **A Dirac or complex relic** is half particles and half antiparticles. The vector part of c₁ is C-odd and changes
  sign between them, so their rates add: c₁² = S² + V².
- **Spin-1 dark matter** has no DirectDM basis; its scalar exchange is computed directly, as the library's vector
  Higgs portal.

**The portal layer** (`adroit/parameter_space/portals/generic_dd.py`) assembles the point:
- **The loop library**, where the tree-level SI coupling vanishes:
  - **a pure electroweak n-plet** (n ≤ 5, at least 99% one field): the n-plet engine's two-loop σ_SI;
  - **coloured partners of Majorana dark matter** (one chirality): Hisano et al.'s scalar, twist-2 and gluon
    couplings, exactly as `portals.tchannel` computes them;
  - **a lepton partner of Majorana dark matter:** its anapole, through Path 1's tabulated structure.
- **Inelastic scattering.** A neutral Z₂-odd state within 450 keV above the dark matter, joined to it by a vector
  that couples to quarks. Direct detection is then `inelastic` (Path 1 only), and the channel is pending.
- **The fallback.** With no tree-level coupling at q → 0 and no loop entry: "loop-dominated, not computed". The
  searches are undecided and the reason is pending.
- **Momentum-suppressed operators only** (pseudoscalar exchange, axial × vector): reported as such, as the
  library's portals do.
- **Path 1** gets DirectDM's full nonrelativistic operator set with its q dependence (`GenericModel.interaction`).
- **A mediator below about 1 GeV:** the contact limit fails at the recoil's momentum transfer, so the channel is
  not computable and the point stays pending.

## The sign of a partner's vector term

The interference of a Z′ with a coloured partner in χu → χu settles it. Run through the tree engine, the full theory
shows constructive interference for a Dirac χ and destructive for a Majorana χ.

**The fix.** The Fierz formula above is for the χ of L ⊃ φ*χ̄Γq, which reaches φ only in the u-channel. G2's
dark-matter particle is the one that joins q in φ in the s-channel (χq → φ), that χ's conjugate. Under charge
conjugation the C-odd bilinears change sign, so C61 and C63 flip; C62, C64 and the scalar term do not
(`Partner.s_channel`).

**The check.** MadDM's own matching of the exported models confirms both signs and the magnitudes (below). It also
shows that MadDM computes the particle of the exported UFO pair, which for an oriented (flipped) fermion is ADROIT's
antiparticle.

## Validation

**Against MadDM's quark-level α** (its normalisation, `maddm.expected_alpha`), on exported models:

| model | dark matter | agreement |
|---|---|---|
| Bhattacharya et al. BP4 (h, Z) | Dirac | 7×10⁻⁴, vector signs included |
| Das et al. BP2 (h₁, h₂) | Dirac | 5×10⁻⁴ |
| Choubey et al. BP1 (h, Δ⁰) | Majorana | 3×10⁻⁵ |
| a real-scalar Higgs portal | real scalar | 10⁻⁵ |
| a complex scalar with a Z′ | complex scalar | 10⁻⁴ on the coupled quarks (MadDM also gives the uncoupled s, c, b u's value, an artefact `maddm.check` already excludes) |
| a Dirac χ with a Z′ and a coloured partner | Dirac | 10⁻³; constructive, as the tree engine |
| a Majorana χ with an axial Z′ or a coloured partner | Majorana | magnitudes 10⁻³; one overall SD sign (a convention: SD has no other term to interfere with) |

MadDM could not generate direct detection for Dedes & Karamitros (below).

**Against the library engines' `nucleon()`:**

| control | agreement |
|---|---|
| GAMBIT's Dirac Higgs-portal EFT (ξ = 2.07, 2.06) | 0.995 (the library takes m_h = 125.09 GeV) |
| the vector Higgs portal (Athron et al.) | 0.995 |
| Das et al.'s singlet mixing, all four points | 0.997–1.0003 |
| a real-scalar Higgs portal | 1% (F_N 0.307 against 0.3066, and the model's own physical mass) |
| a Majorana χ with a partner of u_R | equal to `portals.tchannel` (c₁ and c₄, to 10⁻⁹) |
| the wino | the n-plet engine's σ_SI |

**Against DirectDM's full chain** (running included), c₁ᵖ at q → 0:
- the Higgs-like models: +0.7%;
- the complex scalar: −1.9%;
- Bhattacharya et al. BP4: −15%. Its axial-vector coefficient is ten times its vector one, and the
  renormalisation-group mixing below m_Z moves the vector channel.

**The zoo's σ_SI targets** (development half; G5 compares the published dark matter–proton cross-section,
σ_p = (c₁ᵖ)²μ²/π):

| model | published | generic | met | reading |
|---|---|---|---|---|
| Das et al. BP2 (control) | 6.72×10⁻⁵⁰ | 7.06×10⁻⁵⁰ | yes | equal to the library's |
| Bhattacharya et al. BP4 | 2.04×10⁻⁴³ | 3.89×10⁻⁴³ | yes (×1.9) | Z exchange on protons, suppressed by 1 − 4s_W² (on neutrons it is 40 times larger); DirectDM's running gives 2.8×10⁻⁴³ |
| Choubey et al. BP1 | 2.1×10⁻⁴⁸ | 8.57×10⁻⁴⁸ | no (×4.1) | exactly a factor 2 in amplitude (1.98 with the paper's f_N = 0.3). MadDM reproduces ADROIT's coefficients for this model to 3×10⁻⁵, so the factor lies in the paper's normalisation of its Majorana coupling against its σ formula, not settled |

In the development run (2026-10-14, `runs/eval/model_zoo.jsonl`) the new models' compared targets rose from 7 to
9, and met from 3 to 4. The generic route agrees with the controls' engines on 8 of 10 targets; Das et al.'s σ_SI is
now among them. The two that disagree are still Das et al.'s BP2 and BP9 Ωh², where the library drops the
trilinears (G4).

**The gate:** the zoo's σ_SI targets are met or their misses are localised, and the controls agree. G5 has no
held-out run (the plan's gates with one are G4, G7 and G12).

## Found on the way

| what | where | effect |
|---|---|---|
| A UFO name with brackets, phi(p0.667) | G2, `ufo_export.names` | MadGraph's renaming broke on it. Names are now lower-case letters and digits |
| ψᵀCψ, a bilinear of two unconjugated Dirac fields, was read as a Dirac mass ψ̄ψ | G1, `gauge_basis._fermion_term` | a stated Majorana mass of a Dirac field became M + δ for both states. It is refused until implemented (state the Weyl components as fields) |
| MadDM fetched tools from the network | the MadDM driver | when a `generate` produced nothing (Dedes & Karamitros's direct detection), MadDM's `output` fell back to every mode, and its indirect mode downloaded and began installing tools (DRAGON, LHAPDF). The earlier indirect attempt for Choubey et al. had downloaded PPPC4DMID.tgz. MadGraph and MadDM now run with the network denied (`maddm.offline`: sandbox-exec), and what they had fetched was removed |

**A note on Majorana currents.** Between two Majorana fields χ̄₁γ^μχ₂ = −χ̄₂γ^μχ₁. So a real vector coupling plus
its conjugate vanishes, and G2 correctly gives no vertex. The axial coupling, χ̄₁γ^μγ⁵χ₂ = χ̄₂γ^μγ⁵χ₁, survives.

## Limits

- The tree-level closed forms do not run the coefficients below m_Z; DirectDM's chain (Path 1) does.
- A scalar dark matter's fermion partner (twist-2 for scalars) is not in the matching; a model with only that
  coupling to quarks falls back to "not computed".
- The tensor part of a partner's Fierz rearrangement (both chiralities) is left out, with a note.
- The loop library has no entry for a mixed multiplet, a 2HDM+a structure read from a generic model, or Rayleigh and
  charge-radius terms of scalar dark matter.
- A Majorana mass of a Dirac field is refused (above).

Tests: `tests/model_building/test_dd_matching.py`, the G5 section of `tests/parameter_space/test_generic.py`, and
additions to `test_spectrum.py` and `test_ufo_export.py`.
