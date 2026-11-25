# Bounded multiparameter physical fitting (M28)

Fit one physical Point coherently to the existing CDMS Si + DEAP or CDMS Si +
PICO native module likelihoods. This adds named fit coordinates and profiles,
without replacing the signal-only band, thermal headline or unconstrained NR
reference. Experimental fidelity B and the existing nuisance omissions remain.
No package, network connection or API key is needed.

```bash
uv run adroit native-fit docs/dm13/vector_mediator.yaml \
  --domain docs/examples/native_fit_domain.yaml \
  --null "PICO-60 C3F8 (2019)" --evaluations 12000 --out runs/native_domain
# Repeat the same command with --resume to reuse matching, content-bound trials.
```

The domain YAML names Point slots: `m_chi`, `m_med` in GeV and dimensionless
`g_chi`, `g_q`, `g_l` for the supported simplified vector/scalar engines.
It does not reinterpret arbitrary Lagrangian symbols or map an unspecified
flavour coupling into a Point slot. General flavour-vector and complete scalar
potential native likelihoods remain unsupported. Use their existing theory/scan
workflows; this increment does not invent a new experimental certificate.

Each coordinate has either distinct `values` (a discrete coordinate) or finite
`low < high` (continuous). Positive continuous ranges can use `scale: log`.
At most three continuous coordinates are supported. Native `m_chi` remains a
discrete supplied mass bank, entirely inside the null search's existing native
SI envelope. The reusable Python solver also accepts direct continuous masses
for a separately justified evaluator, but the native adapter does not certify
such a search. Every newly varied mediator mass or quark coupling uses fresh
detector spectra; there is no shape interpolation. Only the existing checked
exact quadratic `g_chi` scaling is reused. The optimum's detector templates
are remade independently before reporting a resolved fit.

`fixed` overrides the recorded reference Point explicitly. Other unspecified
slots retain that Point and are recorded in the result. `relations` are direct
affine relations, e.g. `{target: m_med, source: m_chi, scale: 2, offset: 0}`;
chained/cyclic relations are refused. `branches` have unique labels and may
set non-free, non-related slots explicitly, e.g. opposite signs of a fixed
quark coupling. Signed free coordinates can expose disconnected sign modes.
All source nuisances are treated exactly as in the existing native pair; no
unknown nuisance covariance is inferred or shared between experiments.

Two Cartesian resolutions and bounded local optimisation check each declared
branch. Every sampled local basin is refined; endpoints and boundary faces
remain eligible maxima. All resolved local modes, including lower maxima,
are retained. Profiles maximise the other coordinates and branches at the
reported slice values, with coarse/fine checks on each slice. They are sampled
diagnostics, **not calibrated confidence regions**. `local_rank` is an interior
finite-difference curvature diagnostic, not proof of global uniqueness.
Equal modes, flat profiles and rank deficiencies prevent an identifiable claim.
The `identifiable` field is a diagnostic at the declared resolution even when true;
arbitrarily narrow unsampled modes or exact global uniqueness are not certified.

Resolution disagreement, missing predictions, optimiser failure or a compute
cap leave the fit unresolved. `q0` is descriptive; this multiparameter search
does **not** reuse the old mass/coupling toy p-value. M29–M31 calibration/coverage
remain post-release proposals. `complete` in this mode means the requested
finite-resolution fitting work completed, not that significance was calibrated
or an experiment's unreleased likelihood reconstructed.
The optional deterministic result reviewer distinguishes completed domain
optimisation from significance calibration and flags unsupported significance claims.

`--fit-grid`, `--profile-grid` and `--evaluations` declare compute/resolution
controls. The cap counts distinct physical likelihood trials, including failed
trials and a fresh final trial; native templates use extra fixed scaling checks
as documented above. Existing atomic checkpoint/locking/progress infrastructure
records trials and templates. Resume refuses changed requests, budgets, data,
code or runtimes. To change the cap or refine a failed resolution, start a new
output folder; results from different numerical contracts are not silently merged.

For a full single-idea study, add `--native-joint "PICO-60 C3F8 (2019)"` and
`--native-domain docs/examples/native_fit_domain.yaml`, with `--masses` equal
to the declared domain bank and the same experiment included in `--null`.
The native subrun resumes matching checkpoints in `native_fit/`. Python requests
can set `JointSettings(domain=PhysicalDomain(...), domain_settings=...)`, including
promotion's existing native settings. This view does not change thermal eligibility
or multiply the same dataset's reconstructed/reference likelihood twice.

Common evidence exports contain the domain, modes, profiles, settings and pending
reasons. Numerical native replay checks a fresh direct prediction at the saved
best Point; it does not rerun every profile or certify mode discovery. Older
one-parameter native archives remain readable and replayable.
