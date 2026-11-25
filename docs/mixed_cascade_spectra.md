# Mixed and cascade photon spectra

The first increment combines PPPC4DMID photon showers by their actual branching
fractions and boosts on-shell spin-zero mediator decays at finite mediator mass.
It also supplies a source spectral recast for dwarf-galaxy gamma rays. Track 1
scans and Track 2's single-idea physical studies use this recast when the existing
pure-channel comparison cannot be made. This adds coverage through composition
of existing physics components; it does not improve their shower generator.

## Inputs and conventions

`adroit/constraints/spectra.py` accepts a typed `SpectrumRequest`. Prompt channels
are e, mu, tau, u/d/s, c, b, t, W, Z, g, hh and the three neutrino flavours. PPPC's
unpolarized, electroweak-inclusive columns are used; u, d and s share its light-quark
shower. There is no interpolation outside the shower mass domain, and a channel
needs valid brackets above its threshold. Branching fractions must sum to one;
no unknown positive-rate component is dropped. The physical rate adapter supplies
all annihilation branches, including the actual tree-level fermion decay fractions
of DM13's scalar or pseudoscalar mediator. Its existing omission of S → gg is
retained and stated in the class documentation.

PPPC gives dN/dlog10(x) for **one annihilation**, x=E/mχ. We interpolate yields in
log mass and log x, then divide by E ln(10) to obtain photons/GeV. For one scalar
mediator decay, the rest-frame pair shower has effective mass mS/2. Two mediators
are boosted with γ=mχ/mS and β=√(1−mS²/mχ²):

\[
\frac{dN_\gamma}{dE} = \frac1{\gamma\beta}
 \int_{E/[\gamma(1+\beta)]}^{E/[\gamma(1-\beta)]}
 \frac{dE_*}{E_*}\frac{dN_{\gamma,\mathrm{one\ decay}}}{dE_*}.
\]

The factor two for the two mediators is already included. At β=0 the result is
exactly twice the rest shower. Decays are isotropic and assumed prompt within the emitting source; displaced
mediator transport is not included. Annihilation is treated in
the nonrelativistic limit. Charged particles, polarized vector decays, off-shell
cascades and sub-GeV hadronisation require separate support and remain pending.
Unknown UFO decay topologies are not assigned a nearest Standard Model shower.

## Dwarf likelihood and review gate

The legacy 2015 Fermi-LAT curves retain their existing comparisons and signatures.
The new source is [McDaniel et al., PRD 109, 063024 (2024)](https://arxiv.org/abs/2311.04982)
and its [public Figshare release](https://figshare.com/articles/dataset/24058650):
14.3 years, standard point-source SEDs, 26 bins from 0.5 GeV to 1 TeV, the authors'
42-dwarf benchmark. This includes 30 measured and 12 estimated J factors. It is
not a replacement labelled as a 2015 recast. The older data download was
unavailable, and this newer source supplies the needed spectral likelihood.

Following the authors' example, each index-two bin template is evaluated at its
reference energy, using log-log interpolation of differential photon yields.
The scan's differential flux is `norm_scan × ref_dnde`; MeV energies become GeV
and differential fluxes gain a factor 1000. Self-conjugate flux is
⟨σv⟩ J dN/dE /(8πmχ²); Dirac flux is half this. The spectrum API also supports an
explicit dark-matter density fraction f, whose flux scales as f². Ordinary
thermal-contour scans continue to assume all of the dark matter.

`adroit/constraints/dwarf_likelihood.py` profiles independent Gaussian priors in
log10 J (paper Eq. 7), without a trial-J Jacobian. The search covers eight prior
standard deviations and refuses a maximum touching its bounds or the released
flux boundary. Flux is never extrapolated. It finds a best-fit annihilation rate
≥0 and the upper branch at 2Δlog L=2.71. These are observed upper limits at fixed
mass and spectrum, not discovery significances calibrated against blank fields.
The reference-energy templates remain an approximation to a full response recast.

The separate record `fermi-2311.04982-spectral` is **unverified** until a person
reviews it. Use the existing `--unverified` switch to exercise it provisionally.
Missing inputs or unsupported spectra return pending with a reason. Overlapping
2015 and 2024 dwarf data never enter a result twice. The optional global combined
mode still uses its documented generic ratio approximation; the new dwarf
calculation does not make that whole combination a native likelihood.

## Installation and use

Fetch the optional items with `uv run adroit setup --fetch --only "PPPC photon spectra"`
and `uv run adroit setup --fetch --only "McDaniel dwarf likelihoods"`. The checksum-checked installer extracts only
the pinned releases. External data remain in the tools folder and are not bundled.
Astropy reads their FITS tables. Source archive hashes are recorded in `tools.yaml`.

```python
from adroit.constraints.spectra import from_rates, spectrum
from adroit.constraints.dwarf_likelihood import upper_limit

photons = spectrum(from_rates(100., {'c': 1.e-26, 'b': 1.e-26}))
limit = upper_limit(photons, self_conjugate=False)
```

This explicit low-level calculation is useful for review; the scan/verdict entry
points enforce the record gate. `PointResult.photon_limit` retains the source,
confidence level, upper limit, best fit, conjugacy and assumptions beside the
comparison ratio.

## Validation

Eight b and tau upper limits at 10.608, 88.862, 366.524 and 1511.775 GeV agree with
the authors' separately released TS grids to within 1.49%. Different mass
interpolation and the published coarse annihilation-rate grid explain the tested
numerical spread; this is not a shower-systematics estimate. A scalar four-bottom
benchmark mχ=500 GeV, mS=100 GeV preserves photon number to 0.0040% and energy to
0.0061%. A two-million-photon isotropic-decay Monte Carlo differs by 0.4835% in
integrated absolute bin error over 0.5–500 GeV. Its photon energy fraction is
0.27129, below the available annihilation energy. The hierarchical Elor et al.
one-step reference (εf=0.1, mS=96 GeV) differs by 3.753% over 0.5–100 GeV; its
β=1 approximation and shower interpolation differ from this finite-β calculation.
This is an additional comparison, not an independent QCD generator.

Sources: [PPPC4DMID](https://www.marcocirelli.net/PPPC4DMID.html),
[Elor et al. cascade tables](https://web.mit.edu/lns/research/CascadeSpectra.html).
Full evidence and workflow results are in the dated ignored audit report and its
evidence folder (summary). Reproduce the installed-source checks offline with:

```bash
uv run pytest -m slow tests/constraints/test_spectral_sources.py
```

## Optional next extensions

Choose bounded physical fitting, source-native likelihoods, or measured agent
assistance. Agent assistance means bounded LLM planning/review that clarifies
missing inputs, collects source evidence and schedules existing deterministic
calculations. Measure its value against templates and current assistance by
errors caught/introduced, expert time and cost. It supplies neither physical
numbers nor source-record approval.
