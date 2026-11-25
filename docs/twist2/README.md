# The coloured partner near degeneracy: the twist-2 bound, and the full calculation

**What ADROIT does** (since 2026-10-12, at the owner's request: a quick approximation, stated as one).

A Majorana χ with a coloured scalar partner φ of a right-handed quark, L ⊃ y φ* χ̄ P_R q + h.c., scatters on
nucleons through the partner's propagator. Hisano, Ishiwata & Nagata (arXiv:1007.2601, 1502.02244) expand that
propagator in the quark's momentum. With x the struck quark's momentum fraction in the nucleon and

  ε = 2 m_χ m_N / (m_φ² − m_χ²),

the n-th term of the twist-2 series is suppressed by (εx)ⁿ. Its nucleon matrix element is a momentum moment
⟨x^{n+1}⟩ of the quark plus antiquark distribution. ADROIT keeps the leading term (the second moment ⟨x⟩) and bounds
the rest.

- **Before (R2, the x = 1 bound):** every moment taken at its largest, ⟨x^{n+1}⟩ ≤ ⟨x⟩, so the remainder is at
  most ε/(1 − ε) of the leading term: about ±10% at m_φ − m_χ = 10 GeV, ±23% at 5 GeV and ±89% at 2 GeV.
- **Now (the moment bound):** since 0 ≤ x ≤ 1, every moment beyond the second is at most ⟨x²⟩, so

  remainder ≤ (⟨x²⟩/⟨x⟩) ε / (1 − ε).

  The ratios at μ = m_Z, from the central member of PDF4LHC21_40 (`docs/twist2/moments.py`, momentum sum
  1.0015), are u 0.18 (taking the larger of proton and neutron), d 0.18, s 0.06, c 0.06 and b 0.04
  (`loops.TWIST2_RATIO`).
- **The scalar and gluon parts:** these and the heavy-quark long-distance term keep the x = 1 bound, so the
  amplitude's band is δ = w ε/(1 − ε), with w = (r T + S + G)/(T + S + G) for the leading twist-2, scalar and
  gluon parts T, S and G (`loops.coloured_partner_weight`).
- **The result:** for a u_R partner, w ≈ 0.21, giving about ±2% at 10 GeV, ±5% at 5 GeV and ±18% at 2 GeV. For
  b_R, where the gluon term dominates, w ≈ 0.57.
- **What it is:** a bound, not the resummed value. It is conservative, because it takes every higher moment at
  ⟨x²⟩. Direct detection compares the ratio band [r(1 − δ)², r(1 + δ)²] with 1.
- **Dirac χ:** keeps ε/(1 − ε). Its leading term is the quark's vector charge, not a momentum moment.
- **Where the expansion fails:** for ε ≥ 1 (m_φ − m_χ ≲ m_N) the struck quark can put the partner on shell, and
  direct detection is not computed (pending).

## The full calculation (not built)

1. **Resum the series against the distributions.** Replace the leading coefficient with
   ∫₀¹ dx x q(x) [1/(1 − εx) + 1/(1 + εx)]/2 per quark (the two orderings of the partner exchange), using a PDF set
   at μ ≈ m_Z, the scale of the moments already used. PDF4LHC21_40 is in the tools folder, and
   `docs/twist2/moments.py` already reads it. Its error members give the PDF uncertainty, and a factor-2
   variation of μ gives the scale uncertainty.
2. **Expand the scalar and gluon parts at the same order:**
   - the scalar operator's corrections are the mass-insertion terms of the same propagator;
   - the gluon parts need the two-loop gluon diagrams of Hisano et al. (arXiv:1007.2601, eqs. 26–31) with the full
     propagator in place of its expansion.
3. **Very near degeneracy** (ε → 1): the expansion fails, and the full one-loop box with the partner nearly on
   shell is needed. The literature treats this regime as "compressed" or "near-degenerate" coloured mediators.
4. **Validate** against the near-degenerate results in that literature, then replace
   `loops.coloured_partner_weight` with the resummed amplitude and its PDF and scale band.
