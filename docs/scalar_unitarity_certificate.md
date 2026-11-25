# Scalar partial-wave certificate (M25)

ADROIT computes a complete scalar two-body scattering matrix for the M23 real
Z2 singlet potential in the **tree-level high-energy contact approximation**.
This supplies a calculation distinct from the existing heuristic coupling caps
and the M24 vacuum assessment. Finite-energy exchanges, gauge/Yukawa contributions,
running, quantum corrections and full-theory unitarity remain outside this claim.

## Domain and normalization

Write the Higgs doublet using four canonically normalized real components phi_a:

```text
H†H = (phi_1²+phi_2²+phi_3²+phi_4²)/2,
V4 = lambda_H*(sum phi_a²)²/4 + lambda_S*S⁴/4
     + lambda_HS*(sum phi_a²)*S²/4.
```

The real components include the physical Higgs and three Goldstones. The latter
retain the scalar potential's longitudinal-sector content in the gaugeless limit;
this does not certify complete longitudinal gauge scattering. The approximation
is formal `s/m_i² -> infinity` at **fixed declared coefficients and scale**.
It assigns no validated finite energy or RG cutoff.

There are 15 unordered scalar pairs from these five real fields. A pair of
identical species has state factor `1/sqrt(2)`; a distinct pair has factor 1.
For each incoming/outgoing pair, differentiate the quartic potential and apply
both state factors:

```text
M_ij,kl = -d⁴V4/(dphi_i dphi_j dphi_k dphi_l)
           /sqrt((1+delta_ij)*(1+delta_kl)),
a0 = (1/(32*pi))*integral_-1^1 M dcos(theta) = M/(16*pi).
```

This normalization follows [Goodsell and Staub, Eq. (2)](https://arxiv.org/abs/1805.07306).
The certificate tests every eigenvalue using `abs(Re(a0)) < 1/2`. A value at or
within the stated numerical resolution of the boundary is **unresolved**.
All basis states, matrix elements and eigenvectors are exported.

## Independent analytic checks

In ADROIT's potential convention, the positive quartic matrix has a two-dimensional
Higgs-trace/singlet block

```text
[[6*lambda_H, lambda_HS],
 [lambda_HS, 3*lambda_S]],
```

plus eigenvalues `2*lambda_H` (multiplicity 9) and `lambda_HS` (multiplicity 4).
The physical contact matrix is its negative. This accounts for all 15 channels.
The decoupled limits give `abs(lambda_H)<4*pi/3` and
`abs(lambda_S)<8*pi/3`. For example, lambda_S=10 satisfies the old 4*pi heuristic
but fails the partial-wave criterion.

The referenced paper's quartic convention uses
`lambda_H_source=2*lambda_H`, `lambda_S_source=lambda_S/2` and
`lambda_HS_source=lambda_HS`. Validation explicitly converts these coefficients;
no unconverted source bound is applied.

## Results and scope

`passed`/`failed` refer only to this scalar contact approximation. `complete=true`
means all 15 channels were included and the eigensystem checks resolved the
criterion. Missing inputs, an omitted channel or numerical ambiguity never yield
a passing complete certificate. A partial basis may be calculated diagnostically,
but is marked `incomplete_basis` even if its eigenvalues are small.

The default relative resolution is 1e-10. Eigenpair and orthogonality residuals
are saved and checked; overflow/underflow or a failed eigensystem is unresolved.
The parameter identity includes the entire specified potential, declared scale
and vacuum, even when masses/quadratic terms do not enter the contact limit.
Changes of basis preserve eigenvalues; field aliases remain visible in provenance.

## Run and export

```bash
uv run adroit theory unitarity docs/examples/complete_scalar_singlet.yaml \
  --out runs/scalar_unitarity
```

This writes `unitarity.json` and `report.md` at $0. It accepts a complete ModelSpec
or the full coefficient input described in the [vacuum guide](scalar_vacuum_certificate.md).
A legacy benchmark without a complete scalar potential receives missing-input
status; no singlet self-coupling is invented.

Complete scalar points in Track 1 and single-idea Track 2 automatically retain
`unitarity_certificate`. Reports show the high-energy result separately from
vacuum, thermal and experimental conclusions; common evidence exports include
the same matrix and input identity. Structural `audit.valid`, confidence levels,
fit parameters and heuristic solver-domain checks retain their meanings.

Reading/exporting an old result does not compute a missing certificate. Explicit
replay can calculate additional current evidence, retaining it in `actual` and
labelling its exclusion from the legacy comparison. Certificates present in new
saved results are strictly compared. Other numerical/reliability changes are not
hidden by this additive handling.

A passing high-energy certificate cannot establish unitarity near thresholds or
resonances. M26's declared-scale running and later finite-energy studies would
supply different, separately scoped information.
