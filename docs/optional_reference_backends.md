# Optional reference backends

These programs validate ADROIT's own calculations. They are optional and do not
replace its recoil rates, solar capture or experiment likelihoods.

Install the pinned Python extras with:

```bash
uv sync --extra retrieval --extra references
uv run adroit setup
uv run adroit setup --fetch --only dmscatter
uv run adroit setup --fetch --only "Capt'n General"
uv run adroit setup --fetch --only WIMpy_NREFT
```

The setup manifest records source versions and licences. Compiled programs live
in `ADROIT_TOOLS_DIR` (normally `~/agentic-dm-tools`), outside the repository.
Existing audited `data/external/WIMpy_NREFT` and `data/external/dmscatter`
checkouts are discovered when their preferred tools-directory checkout is absent.
An explicitly supplied tools directory takes precedence.

Semantic retrieval uses `sentence-transformers` and `all-MiniLM-L6-v2`, revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Its first use downloads the weights;
afterwards cached operation supports `HF_HUB_OFFLINE=1`. Hash embeddings and
existing hash collections retain their original names and vectors. NEST is
`nestpy==2.1.1`; both package resolutions are in `uv.lock`.

Run the numerical references after setup:

```bash
uv run --extra retrieval --extra references python scripts/validate_optional_backends.py
HF_HUB_OFFLINE=1 uv run --offline --extra retrieval --extra references pytest tests/retrieval/test_embeddings.py -m slow
```

The driver saves raw outputs and comparison summaries to the ignored
`audit/optional_backends/` directory; `--out` selects another evidence directory.
It requires `gfortran` for the capture caller. WIMpy runs in the same Python
environment as the validation driver, using ADROIT's core NumPy/SciPy dependencies
and the existing driver aliases for SciPy's removed `trapz`/`cumtrapz`. It
explicitly supplies its patched module path; no audit-only environment or
temporary `PYTHONPATH` is needed.
The driver checks each Git reference's installed revision against the manifest
before calculating and saves the full commits in `reference_revisions.json`.

| Reference | Pinned version | Check and interpretation |
|---|---|---|
| NEST | nestpy 2.1.1 | Nine mean nuclear-recoil yield cases at 1, 10, 50 keV and 124, 200, 500 V/cm. VDetector, liquid xenon density 2.9 g/cm³, A=131.293, Z=54. Repeated results agree with the upstream helper interface. This establishes interface consistency, not independent detector validation. |
| dmscatter | d5c4046b4d4cd715af12f1251fac40b6e25b85d5 | O1/O4/O6 spectra against archived DMFormFactor Si29 proton rates and ADROIT F19 rates. Declared bulk tolerance 5%; endpoint errors are retained separately. |
| Capt'n General | 59b55a4b31dc27e6d2435d588a6d72a463cb04ca | Independent capture integration for O1/O4/O6/O8/O11, with matched B16 AGSS09 solar input and halo. Declared tolerance 5%. The existing 18-point DarkSUSY/IceCube check is also retained. Nuclear responses and solar inputs are shared; integrations are independent. |
| WIMpy_NREFT | 50581c637069305a3def3865462ef1b4ed9a616d | Existing Python-3.12 compatibility driver and full-precision nuclear coefficients, O1/O4/O6; setup and calculation share discovery. |

## Explicit compatibility and convention choices

`build_reference_backends.py` changes dmscatter's malformed display FORMAT
`(I2,x2e11.4,e11.4,e11.4,e11.4)` to `(I2,2X,4E11.4)`. It changes no physics
expression. The adapter copies each nuclear density file to a fresh local attempt
directory, avoiding Fortran parsing of absolute paths containing spaces. It checks
the process and fresh output, retains stdout, converts physical GeV^-2 coefficients
to upstream weak-scale units, and converts rates per GeV to rates per keV.

The archived dmscatter comparison uses its smooth escape cutoff at 550 km/s.
ADROIT uses a sharp cutoff. The direct code comparison therefore uses an
effectively untruncated Maxwellian (2000 km/s) in both engines, with matched Earth
speed, masses, target normalisation and operator mass. This comparison does not
validate replacing one cutoff prescription by the other.

The pinned Capt'n Oper routine's `factor_final` uses
`N_A rho / mass_GeV` although its solar density is in g/cm³. A nuclear mass
`M_GeV` has molar mass `M_GeV / AMU_GEV` g/mol, so the physical number density is
`N_A rho AMU_GEV / M_GeV`. `reference_capture.physical_capture_rate` applies this
explicit unit factor to that reference routine only. Both raw and converted
values are saved; ADROIT's production integration is unchanged. The standard
upstream SI/SD example outputs are retained separately without this conversion.

Sources: [NEST bindings](https://github.com/NESTCollaboration/nestpy),
[dmscatter](https://github.com/ogorton/dmscatter),
[Capt'n General](https://github.com/aaronvincent/captngen), and
[sentence-transformers](https://www.sbert.net/docs/installation.html).
