# DM0: tool audit and data inventory

Carried out 2026-09-29 on the development machine. Cost: $0. External tools
were fetched into `data/external/`, which git ignores, and installed in test
environments separate from the project's own.

## 1. Summary

- **The core rate tools work,** with repairs: WIMpy_NREFT, DirectDM and NEST
  run on the development machine.
- **Two sources block automated access** and need a manual download: WimPyDD
  (the rate code LZ used) and HEPData (LZ's released data).
- **The DM0 gate is met in the bulk of the spectrum,** and the exercise
  showed why the project should own its rate calculation (section 4).
- **Three findings affect the plan:** the nuclear form factor at high recoil
  energy, the development machine's architecture, and build scripts that fail
  in the project's folder path (section 5).

## 2. Tools tested

| tool | version tested | licence | result |
|---|---|---|---|
| **WIMpy_NREFT** | v1.2, commit `50581c6` (2024-10-30) | MIT | Runs after a two-line compatibility shim: it imports functions that current SciPy has removed. Operators O1–O20, dark matter spin 0, ½ and 1, dipole and millicharge interactions. No inelastic scattering. No tungsten. |
| **DirectDM** (Python) | GitHub commit `b949fb6` (2025-03-26) | MIT | Runs. The PyPI release 2.2.2 fails under current NumPy; the GitHub version carries the fix. Needs `setuptools<81`. |
| **NEST** (`nestpy`) | 2.1.1 | GPL-3.0 | Installs and imports. Its interface differs from the example I tried, so no yield was computed. |
| **DIAMX** | 0.3.0, commit `2577bc9` (2026-06-11) | Apache-2.0 | Installs only under a native (arm64) Python. Its own tests fail at import: a version mismatch among its unpinned dependencies. **Resolved in DM3:** built in `~/agentic-dm-tools` with blueice 1.2.1, all 15 of its tests pass (`docs/dm3_experiments.md`). |
| **dmscatter** | commit `d5c4046` (2025-06-04) | MIT | Compiles. Fails at run time under the installed gfortran, on a Fortran format statement. Needs a patch or a compiler flag. |
| **DDCalc** | commit `f504c9b` (2023-11-09) | its own: free for non-commercial use, with citation | Compiles, but only in a path without spaces. Examples not yet run. |

**DirectDM check.** A vector coupling of Dirac dark matter to up quarks,
with coefficient 1/(100 GeV)², gives the nonrelativistic coefficients
c₁(proton) = 2 × 10⁻⁴ and c₁(neutron) = 1 × 10⁻⁴ GeV⁻²: the quark content
of the nucleons, as it should be.

### What each offers

- **WIMpy_NREFT** holds the shell-model nuclear responses as tabulated
  polynomials, for 30 isotopes from hydrogen to xenon. These are the inputs a
  rate calculation needs.
- **DirectDM** carries quark-level coefficients to nonrelativistic
  coefficients, in the three-, four- and five-flavour theories, for Dirac,
  Majorana, complex and real scalar dark matter.
- **DIAMX** ships the public data of the xenon experiments in usable form:
  LZ's 2022 and 2024 event lists and efficiencies, XENONnT's two science
  runs, and PandaX-4T's two runs. Its XENONnT and PandaX-4T events were
  digitised from figures; LZ's come from the official releases.
- **DDCalc** holds coded likelihoods for 26 analyses, the latest being LZ
  2022, PandaX-4T and XENON1T 2022.

## 3. Tools recorded but not yet installed

These are needed from DM7 onward.

| tool | source | licence | for |
|---|---|---|---|
| **WimPyDD** | wimpydd.hepforge.org | not confirmed | rates, including inelastic; the reference for LZ's numbers |
| Capt'n General | github.com/aaronvincent/captngen | MIT | capture in the Sun |
| MadDM | github.com/maddmhep/maddm | none stated on GitHub | relic density, indirect detection |
| micrOMEGAs | its own site | not confirmed | relic density, indirect detection, recasts |
| flamedisx | github.com/FlamTeam/flamedisx | BSD-3-Clause | xenon detector likelihoods |
| appletree | github.com/XENONnT/appletree | BSD-3-Clause | xenon detector response |
| SModelS | github.com/SModelS/smodels | none stated on GitHub | collider limits |

## 4. The DM0 gate

**The gate:** a spin-independent xenon spectrum computed through the chosen
rate code agrees with an independent calculation to 1%.

**The test.** WIMpy_NREFT was compared with an independent calculation
written for this audit, which shares only the form factor with it. The
spectrum was computed for five xenon isotopes and dark matter masses of 20,
100 and 1000 GeV, from 1 to 100 keV.

| quantity compared | result |
|---|---|
| velocity integral η(v_min), at the same v_min | agree to 10⁻¹⁴ |
| spectrum, 100 and 1000 GeV | agree to 0.4–0.7% |
| spectrum, 20 GeV, below 20 keV | agree to 0.4–1.2% |
| spectrum, 20 GeV, in the kinematic tail (30 keV) | differ by 4%, and by up to 13% nearer the endpoint |

**The cause of the differences is rounding in WIMpy_NREFT's constants,** not
physics:
- It uses c = 3 × 10⁵ km/s. This shifts v_min by 0.07%, which the steep tail
  of the velocity distribution amplifies.
- Its rate prefactor is rounded to three figures, a constant 0.5%.

With its constants substituted into the independent calculation, the two
agree to a constant factor at every energy.

**A convention to fix in DM1.** WIMpy_NREFT uses the atomic mass unit
(0.9315 GeV) as the nucleon mass in the reduced mass. The physical nucleon
mass (0.9389 GeV) changes the rate by 1.5% at a given cross-section.

**Verdict.** The gate is met wherever the rate is not in its kinematic tail.
In the tail, the reference code's rounding exceeds the gate's tolerance.

## 5. Findings that affect the plan

### The nuclear form factor dominates at high recoil energy

For the spin-independent operator on xenon, the shell-model response and the
standard Helm form factor agree within 2% up to 30 keV. At higher energies
they differ greatly, because each has zeros at different momentum transfers:

| isotope | shell model / Helm at 100 keV | at 248 keV |
|---|---|---|
| ¹²⁹Xe | 1.65 | 0.23 |
| ¹³¹Xe | 0.13 | 0.20 |
| ¹³²Xe | 0.03 | 0.13 |

(Dark matter mass 1000 GeV; computed with WIMpy_NREFT.) For a signal at
248 keV the choice of nuclear response therefore changes the predicted rate
several-fold. The nuclear input should be recorded with every result, and
its uncertainty should be a flag in the tournament.

### The rate calculation should be the project's own (decision 10)

| option | for | against |
|---|---|---|
| wrap WimPyDD | the code LZ used; handles inelastic scattering | cannot be installed automatically; licence not confirmed |
| wrap WIMpy_NREFT | MIT; installs | unmaintained against current SciPy; rounded constants; no inelastic scattering; no tungsten |
| wrap dmscatter | MIT; fast | fails at run time under the current compiler |
| **the project's own implementation** | exact constants; inelastic and any halo under the project's control; no dependency for users to install | must be written and validated |

**Recommended:** the project's own implementation in `adroit/physics/`,
following arXiv:1203.3542 and 1308.6288, with the published nuclear
responses as data. WIMpy_NREFT and WimPyDD then serve as references in the
tests. The formulae are fixed and the calculation is short, so this costs
about one session, and it serves the aim that the core runs without
anything a user must install separately.

### The development machine is an Apple M1, not an Intel Mac

- The processor is an Apple M1 Max. The project's Python is an Intel build
  running under Rosetta, which is why the development record notes an Intel machine.
- Under Rosetta, packages compiled with AVX instructions do not run; this
  stopped DIAMX's JAX dependency.
- A native (arm64) Python avoids this, and removes the need for the pins on
  `onnxruntime`, `rasterio` and `pyproj` that Nomothetica carries
  (decision 12).

### Build scripts fail in the project's folder path

The project's path contains spaces and an apostrophe
(`My Mac (James’s MacBook Pro)`). DDCalc's Makefile fails there. Compiled
tools need a build folder without spaces (decision 11).

### Licences

| licence | tools | consequence |
|---|---|---|
| MIT, BSD, Apache-2.0 | WIMpy_NREFT, DirectDM, dmscatter, Capt'n General, flamedisx, appletree, DIAMX | none beyond attribution |
| GPL-3.0 | NEST (`nestpy`) | copyleft: a distributed program that includes it must itself be GPL. As an optional dependency that users install, it does not bind the project's own licence |
| non-commercial | DDCalc | free for non-commercial use, with citation |
| none stated | WimPyDD | used with citation, not redistributed (owner's decision) |
| not confirmed | micrOMEGAs, MadDM, SModelS | to be read before any of them is depended on |

## 6. Data inventory

| source | what | access |
|---|---|---|
| LZ extended window (arXiv:2609.02823) | HEPData record `ins3199115`, DOI 10.17182/hepdata.182472: the science, prompt-veto and delayed-veto samples, and further tables | **manual download needed**: HEPData blocks automated access |
| LZ 2022 and 2024 searches | event lists (S1c, S2c), efficiencies, the NEST detector file | in DIAMX's data folder, from LZ's official releases |
| XENONnT, two science runs | events and efficiencies | in DIAMX's data folder, digitised from figures |
| PandaX-4T, two runs | events, efficiencies, yields | in DIAMX's data folder, digitised from figures |
| 26 older analyses | coded efficiencies and counts | in DDCalc |
| argon, fluorine, CaWO₄, germanium experiments | – | not yet inventoried; DM3 |

## 7. The manual downloads

Both were supplied by the owner on 2026-09-29, and decisions 10–12 were
settled (build plan, section 7).

**The LZ record** (`data/external/manual/lz_2609.02823/`, licence CC0) holds
47 files:
- **Three event samples:** the science, prompt-veto and delayed-veto samples,
  as points in S1 and log₁₀(S2).
- **43 model tables:** L01–L20 in isoscalar and isovector form, and the
  inelastic O1 and O4. Each gives the upper and lower limits, the median
  expected limit with its bands, and the significance.
- **Not included:** the efficiency curve, the background models and the
  detector-response parameters. The efficiency appears in the paper only as a
  figure; the response parameters are printed in its supplement.

**WimPyDD** (`data/external/manual/WimPyDD/`) is version 2.0.3 of
2026-08-10, 2.4 GB with its tabulated response functions.
- It includes WimPyC, its extension for capture in celestial bodies.
- Its targets include tungsten, which the other rate codes lack.
- Its coded experiments are DAMA/LIBRA 2019, LZ 2022, PICO-60 2019 and
  XENON1T 2018.
- **It carries no licence file.** By the owner's decision of 2026-09-29 it is
  used as a freely available academic code, with citation of its papers
  (arXiv:2106.06207, 2110.11086). It is a reference in tests and is never
  copied into the repository; users download it from its authors' site.

## 8. Reproducing this audit

The gate script is kept in `docs/dm0/gate_si.py`. The test environments and
the fetched tools are in `data/external/` and are not committed.
