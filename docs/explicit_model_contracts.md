# Explicit model contracts (M22–M23)

These two deterministic model contracts supplement the existing simplified-model
and portal library benchmarks. A contract identifies the actual parameters and
normalisation used by the numerical component; it does not certify a UV
completion or complete experimental coverage. No new package or API key is needed.

## Flavour-diagonal vector model

Use [the complete example](examples/flavour_vector.yaml). This is a broken-phase
Dirac DM field and one real neutral vector with

```text
L_int = -V_mu [g_chi chi_bar gamma^mu chi + sum_f g_f f_bar gamma^mu f].
```

`vector_currents.flavours` maps each engine flavour (`u,d,s,c,b,t,e,mu,tau`)
to its declared one-generation field. Every other flavour must appear in
`zero_flavours`; `neutrinos: absent` is required. Each mapped field needs exactly
one hermitian full-Dirac `vector` term. `ModelTerm.coupling` is the **full coefficient
C in L**, so this convention maps `g_f = -C_f`, including its sign. Coupling
expressions must be dimensionless and have finite specified values. The mapping
supports field aliases and never expands a named flavour into a universal current.
Supplied positive DM/mediator masses and nonnegative individual SM fermion masses
are retained. An omitted SM mass uses the existing DMsimp pole-mass convention,
which is identified in the mapping notes; light u/d/s masses are zero in that
convention. Nonreference fermion masses are retained for amplitudes and thresholds,
but fixed-SM shower/deposition/solar source templates become pending; a rigorous
CMB allowance using only `f_eff <= 1` remains possible. The contract requires complete physical coefficients, unlike legacy
intake that can expose benchmark defaults.

The existing spin-1 amplitude and freeze-out components now use these individual
currents and masses. At tree level, conserved valence charges give
`gV_p = 2*g_u + g_d`, `gV_n = g_u + 2*g_d`. The complete existing vector NR
reduction and propagator are retained. For a general flavour current, the
95% DD comparison runs the actual eligible module procedures at these charges;
`sigma_p` is a diagnostic, **not** a limit rescaled from an isoscalar envelope.
The saved `dd_ratio` is the prediction/limit ratio of the actual rate. Individual
omissions and the chosen detector are saved.

The physically identical limit with all six quark couplings equal, all charged
leptons zero and unchanged pole masses uses the existing universal calculation,
including its collider eligibility. Nonzero charged-lepton-only couplings are
not identical to the old universal-lepton benchmark: that benchmark includes
tied left-handed neutrino currents. General flavour-specific collider and
low-energy recasts remain pending. Loop-induced nuclear scattering for
heavy-flavour/lepton-only currents is also pending. Chiral, axial, neutrino,
flavour-changing and extra nonzero dark/mediator interactions are specifically
refused. The SM interactions used by the component remain implicit; additional
explicit nonzero SM-sector terms without a validated coefficient map are also
refused. The native joint-SI pilot is not extended to these new current shapes.

Annihilation and fermionic widths inherit the existing partonic tree-level
component. This increment does not add low-energy quark hadronisation, radiative
precision or a new thermal-equilibrium certificate. The acceptance examples use
masses above the low-energy hadronic regime.

Physics conventions: [DM Working Group widths](https://arxiv.org/abs/1703.05703)
and [NR response conventions](https://arxiv.org/abs/1308.6288). These are tree-level
broken-phase inputs, not an anomaly-free electroweak gauge completion.

## Complete real scalar potential

Use [the complete example](examples/complete_scalar_singlet.yaml). Declare

```text
V = -mu_H^2 H†H + lambda_H (H†H)^2
    + mu_S^2 S^2/2 + lambda_S S^4/4 + lambda_HS H†H S^2/2,
S -> -S, <H> = (0, v/sqrt(2)), <S> = 0; L = -V.
```

`scalar_potential` requires field identities, `scale_gev`, `lambda_s`,
`lambda_hs` and the declared `vacuum`. Choose either:

- `basis: potential`: specify `mu_h2_gev2`, `mu_s2_gev2`, `lambda_h`;
  derive `m_h^2 = 2*lambda_H*v^2`, `m_S^2 = mu_S^2 + lambda_HS*v^2/2`.
- `basis: mass`: specify `higgs_mass_gev`, `singlet_mass_gev`;
  derive `lambda_H = m_h^2/(2*v^2)`, `mu_H^2 = lambda_H*v^2` and
  `mu_S^2 = m_S^2 - lambda_HS*v^2/2`.

Signed quadratic coefficients are supported. Positive physical mass squares and
stationarity at the stated vacuum are checked. Redundant supplied masses and
coefficients must agree within relative/absolute `1e-10`; field mass inputs must
also agree. Explicit L-term coefficients use relative `1e-10`, absolute `1e-12`
comparison tolerance. The Higgs component currently fixes `v=246.22 GeV`, `m_h=125.09 GeV`;
alternate SM inputs are refused rather than silently overwritten.

Empty `terms` means **derive all scalar terms from the fully specified potential**.
If terms are provided, every potential term—including an explicitly zero
coefficient—must be present and agree, with its declared mass dimension.
Unbroken H†H and broken real-h representations are supported. Broken-phase
vertices follow derivatives of V: `hSS: lambda_HS*v`, `hhSS: lambda_HS`,
`SSSS: 6*lambda_S`, `hhh: 3*m_h^2/v`, `hhhh: 3*m_h^2/v^2`, each multiplying
`-i` in the Feynman rule. Additional nonzero scalar interactions, Z2 breaking,
incomplete potentials, nonzero singlet vev or requested mixing are refused.
The component fixes the remaining SM interactions; additional explicitly supplied
nonzero SM terms outside this potential are refused without a validated map.

The existing [tree-level scalar Higgs-portal component](https://arxiv.org/abs/1705.07931)
computes annihilation, widths, NR scattering and relic density. The declared
`lambda_S` and scale are retained in the engine map and every physical-point
contract even when these tree-level observables do not depend on `lambda_S`.
Scan/fit coordinates are `m_chi=m_S` and `g_chi=lambda_HS`; changing either derives
`mu_S^2` at that point while fixing Higgs inputs, `lambda_S` and scale. This is
an explicitly reparameterised family, not variation at fixed original `mu_S^2`.
The `m_med` slot is fixed to the Higgs mass; `g_q/g_l` must stay zero.

Existing heuristic `4*pi` perturbativity checks apply to the portal/self
couplings and are not partial-wave certificates. Global vacuum boundedness and competing minima are assessed by the
[tree-level certificate (M24)](scalar_vacuum_certificate.md). [High-energy scalar partial-wave unitarity (M25)](scalar_unitarity_certificate.md)
is assessed separately. RG running (M26) remains pending. A structurally valid model is not a globally stable-vacuum claim. The
existing library entry `higgs_portal_scalar` remains a separate benchmark mode;
it has no new default singlet self-coupling.

## Run and inspect

For modest offline demonstration scans:

```bash
uv run adroit track1 docs/examples/flavour_vector.yaml \
  --x g_chi:0.05:0.5:log:3 --y m_chi:40:60:log:3 \
  --no-literature --out runs/flavour_demo
uv run adroit track1 docs/examples/complete_scalar_singlet.yaml \
  --x g_chi:0.05:0.5:log:3 --y m_chi:150:250:log:3 \
  --no-literature --out runs/scalar_demo
uv run adroit single-idea docs/examples/flavour_vector.yaml \
  --experiment 'CDMS II Si (2013)' --masses 8,8.5 --toys 20 \
  --grid 4 --no-literature --out runs/flavour_fit
uv run adroit evidence export runs/flavour_demo --out runs/flavour_demo.zip
uv run adroit evidence verify runs/flavour_demo.zip
uv run adroit evidence replay runs/flavour_demo.zip --index 0
```

The small toy count is a workflow demonstration, not discovery calibration.
`physical_fit` in the examples explicitly bounds the physical `g_chi` slot;
other flavour couplings or `lambda_S` stay fixed. The single-idea workflow saves
the unconstrained NR reference separately from the bounded physical fit.
Evidence exports include the original contract, coefficients/mass basis,
resolved engine class, per-point potential/current, comparisons and pending
coverage. Verification requires no physics rerun; replay is an explicit action.
No source review is inferred from a successful numerical check.
