# DAMPE's γ-ray line search, staged for review (2026-10-20)

The owner's decision (2026-10-20): prepare the record and its verification package, review and sign when ready, and
keep it staged until then. The unsigned-record policy is unchanged. The record lives on the branch `dampe-record`
(off `evidence-upkeep`, rebased to `51e4b2f`), outside the stack under audit. Unsigned, it changes no verdict anywhere the
branch is not merged.

**The record.** `dampe-2112.08860-lines`:
- DAMPE, arXiv:2112.08860v2, supplementary Tables S1 and S2: 72 line energies from 10 to 300 GeV, three profiles,
  95% CL with systematic uncertainties, read from the PDF's printed text (`docs/` has no copy; the survey's PDF);
- the verdict uses the weakest of the three profiles at each energy (Einasto R16 only to 206 GeV);
- ρ⊙ = 0.4 GeV/cm³ (`local_densities.yaml`, for the halo region);
- Zγ lines as Fermi's, at one photon each;
- the Dirac half as the other line records.

**The choices for the reviewer.**
- **The two-line guard: 50%,** the half-width of the paper's nominal fit window: "only the photons in the window
  from 0.5 Eline to 1.5 Eline are used in the fittings" (its Methodology). Lines that close share one background
  fit, so they are left pending: every m above m_Z/√2 ≈ 64.5 GeV with both a γγ and a Zγ line. It is a conservative
  applicability guard, not a resolution or a joint-line likelihood. Fermi's guard is 20%. (Corrected after the auditor's
  recheck, RB20-06, 2026-10-20: it had been 30% and about 83 GeV, from the 0.7–1.3 E_line window, which the paper
  uses only as a systematic check of the window's width.)
- **A line outside 10–300 GeV is not DAMPE's.** For m just above m_Z/2 the Zγ line lies below 10 GeV; Fermi-LAT's
  curve covers it.
- **The search keeps its name,** "γ-ray lines (Fermi-LAT, H.E.S.S.)", so that saved results keep their keys. Renaming
  it to include DAMPE is a separate change.

**Checks.**
- The printed tables against an independent vector digitisation of Fig. 3a–c's red curves: median difference 1.0–1.4%,
  90% within 2–5% (two printed digits).
- The tables' rows at 10 and 100 GeV checked by hand.
- Tests: `tests/parameter_space/test_dampe_lines.py`. The Fermi-only test in `test_line_energies.py` now holds Fermi's
  three records, since DAMPE leaves its pair (100 GeV, both lines) pending.

**What it changes at the R3 acceptance's 256 crossings** (the halo verdict study's points, the γ-line outcome alone):
- **unsigned:** 22 outcomes allowed → pending (the record awaits verification);
- **signed:** 9 allowed → pending, all through the two-line guard: higgs_portal_dirac #5 and #6,
  higgs_portal_dirac_cpv #5 and #6, higgs_portal_majorana #5 and #6, higgs_portal_scalar #0, higgs_portal_vector #0
  and singlet_scalar_mixing #5 (with the 30% guard it had been 2: higgs_portal_dirac_cpv #5, singlet_scalar_mixing
  #5);
- **signed:** no exclusion added; every other outcome unchanged. The record's packet and scientific hash
  (`b67b8b3c…`) are unchanged by the correction, which is in the code's guard, not the record.

**The verification package:** `uv run adroit records review dampe-2112.08860-lines --out <folder>` (the record's
packet, its current curves and its scientific hash). Sign with `uv run adroit records verify
dampe-2112.08860-lines --by JU` once satisfied, in the checkout where the branch is merged.
