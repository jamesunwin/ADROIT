# The neutrino fog

Coherent neutrino–nucleus scattering (CEνNS) from the Sun, the atmosphere, supernovae, the Earth and reactors gives
nuclear recoils that look like a dark matter signal. Beneath a certain cross section, a direct-detection discovery
needs an exposure out of all proportion: that region is the **neutrino fog**, and its edge is the **neutrino floor**.
ADROIT draws it as an overlay on spin-independent limits and reports where a model's prediction lies. **It is never a
constraint:** a point beneath the floor is not excluded; it is hard to discover.

The construction is O'Hare's (arXiv:2109.03116), with his fluxes and their uncertainties (arXiv:2002.07499, Table I);
his spectra and published floors are copied with their MIT licence (`adroit/physics/data/neutrino_fog/`).

## The standard floor

The curve LZ and XENONnT draw: O'Hare's published n = 2 floor for xenon (and for argon, germanium, NaI, CaWO₄,
helium and fluorine).

```bash
uv run adroit fog standard --target Xe --out runs/fog
```

## Where ADROIT shows it

- **Path 1** (`adroit exclude`): when the interaction is a multiple of the spin-independent reference at every mass,
  the run also writes `exclusion_sigma_si.png` (the limits as σ_SI, the model's own σ, xenon's fog shaded beneath)
  and a report section placing the model's σ above or beneath the floor at each mass.
- **The point inspector** (the workbench's "Explain a point", `adroit evidence point`): a spin-independent
  prediction is placed against xenon's published floor at the point's mass.
- **`adroit fog standard` and `adroit fog map`**, below.

None of these changes a verdict.

## How the fog is defined

For each mass, the 3σ discovery limit σ(N) is followed as the exposure, and with it the number of neutrino events N,
grows. With every flux normalisation a Gaussian nuisance in a binned profile likelihood (the Asimov data set, q₀ ≥ 9),
the limit falls through three regimes:

| regime | scaling | index n = −(d ln σ/d ln N)⁻¹ |
|---|---|---|
| no background | σ ∝ N⁻¹ | 1 |
| Poisson subtraction | σ ∝ N^{−1/2} | 2 |
| saturation by the flux uncertainty δΦ | σ ∝ √(N + δΦ² N²)/N = √(1 + δΦ² N)/√N → δΦ | > 2 |

The fog is where n > 2; the floor is the n = 2 contour, the largest σ at each mass where n reaches 2. In O'Hare's
construction (a threshold well below the recoils that matter) it depends on no threshold or exposure, only on how
closely the dark matter's recoil spectrum overlaps a neutrino source's and on that source's uncertainty (a custom
recoil window that cuts into either moves it): the ⁸B shoulder near 6 GeV (2%), the atmospheric floor above about 30 GeV (25%), the
diffuse supernova background near 20 GeV (50%), the ⁷Be lines below 1 GeV (6%).

## Advanced settings

`adroit fog map` computes the fog itself (about a second per mass):

| option | what it changes |
|---|---|
| `--target` | an isotope (`Xe131`, O'Hare's) or a natural target (`Xe`, `Ar`, `Ge`, `NaI`, `CaWO4`, …) |
| `--uncertainty NAME=δ` | one flux's uncertainty (`Atm=0.1`: a better atmospheric flux, O'Hare 2020's route below the high-mass floor) |
| `--scale GROUP=k` | a group's uncertainties scaled (`solar=0.1`: O'Hare 2021's improved solar case) |
| `--exclude NAME` | a flux left out (a detector deep enough to see no reactor flux, for example) |
| `--halo standard` | ADROIT's default halo (arXiv:2105.00599) in place of O'Hare's |
| `--threshold-kev` | the lowest recoil energy; the floor is independent of it above the masses it cuts off |
| `--binning` | `window` (the default): only the recoils inside the window count; `ohare`: each spectrum normalised to its whole physical range, as his code does, which moves recoils beyond the window into it (the reproduction of his floors) |
| `--exposure E` | also the classic 3σ discovery limit at E tonne-years above the threshold (how the floors before 2021 were drawn) |
| `--masses`, `--sigmas` | the grids; fewer than 500 σ points biases the floor by up to ~20% (the derivative is smoothed over cells) |

Each run writes `fog.json` (the map: exposures, n and the floor, and each exposure's status), `floor.csv`, `fog.png`
(n as a colour scale with the floors) and `report.md` (the settings, the fluxes and the floor beside the published
one). An exposure is `reached`, `not reached` within the exposure range, `background-free` (a bin with signal and no
background at all: the Asimov q₀ is infinite at any exposure), or `failed` (a profile that did not converge), never
a failure read as "not reached". Every setting is checked: ordered positive recoil bounds and grids, finite positive
flux uncertainties (zero is refused: a known flux is not a zero-width prior).

**The nuance at high mass (O'Hare 2020).** Above about 100 GeV the floor is set by the atmospheric flux and its 25%
uncertainty. Directional information from columnar recombination in liquid xenon or argon is too weak to help; a
better atmospheric flux (DUNE, JUNO, Hyper-K) is the practical route below it, and xenon and argon together, whose
recoil spectra differ, also help. `--uncertainty Atm=0.1` shows the first.

## The validation (gate declared before it was run)

ADROIT's map, with O'Hare's settings (single isotopes, his halo, 500 σ points, his normalisation of each spectrum:
`binning='ohare'`), must reproduce his published floors within 5% at every mass: xenon at 30 masses from 0.1 GeV to
10 TeV, argon and germanium at eight.

**Missed below about 3 GeV; met above** (2026-10-19). The worst deviations as built: xenon 11.4% (at 0.33 GeV),
argon 12.7%, germanium 6.6%, all between 0.2 and 2.7 GeV (argon's 5.7% at 2.68 GeV), where the ⁷Be and pep lines
set the floor. Above 3 GeV
xenon agrees within 1.1% and germanium within 0.4%, and argon within 3% above 10 GeV (5% at 3 GeV: a lighter
nucleus's floor feels the lines up to higher masses), from the ⁸B shoulder to the atmospheric floor.

**The cause.** O'Hare's public code multiplies a monochromatic flux's recoil rate by the line's energy in MeV
(`NeutrinoFuncs.dRdE`, its branch for lines: the cross section × the flux × E_ν), which lowers the ⁷Be lines' rates
by factors 0.38 and 0.86 and raises pep's by 1.44; for a continuous flux the same function integrates over E_ν, as it
should. This appears to be a slip in his code; ADROIT keeps the dimensionally correct rate (the cross section × the
line's flux). With his factor applied as a diagnostic, the agreement is 1.1% for xenon, 0.6% for germanium and 4.4%
for argon at every mass. The miss is recorded, not tuned: the standard overlay remains his published curve, and
ADROIT's own floor (`adroit fog map`) differs from it by up to about 13% below 3 GeV.

**The window and O'Hare's normalisation** (the focused audit's NF-02, 2026-10-19). His code normalises each
spectrum to its whole physical range before binning it in the window, so recoils above the window's top are counted
inside it; ADROIT's default (`--binning window`) counts only the recoils inside the window. The gate above is his
construction (`binning='ohare'`), which still reproduces his floors (xenon within 0.4% from 10 GeV to 10 TeV, argon
within 2–4%). With the default 200 keV top, the window construction gives a floor 10% lower for xenon at 10 GeV and
about 10% lower for argon above 100 GeV, whose atmospheric recoils reach above 200 keV (a window reaching higher
counts them in their own bins).

`tests/physics/test_neutrino_fog.py` (slow) holds both: as built within 5% above 3 GeV (argon: 10 GeV), and with
his line factor within 5% everywhere. Its passing is not the declared every-mass gate, which stays missed below 3 GeV.
