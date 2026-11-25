# Several generations in the generic route (the owner's decision #5, 2026-10-20)

The owner's decision: support the cases the calculation already covers; refuse several stable components and
unresolved thermal histories; require evidence for the decays and the equilibration the relic assumes, not merely a
stated splitting. Multi-component evolution can wait.

## What a model may state

- A new field with `generations: N` is N fields before G1, `F1 … FN`, with the field's quantum numbers
  (`model_building.generations`). Before, G1 refused it (the audit's G1-9: its other generations had been lost).
- **Masses:** `mass_gev` for every generation, or `masses_gev`, one per generation. The generations are mass
  eigenstates: no mass mixing between them is written.
- **Roles:** of a dark-matter field's generations the lightest is the dark matter, the others its partners; a
  mediator's are each a mediator (so a mediator of several generations is not the scan's m_med).
- **Couplings:** a term's `flavour` multiplies its coupling per generation: a list for one occurrence of a
  multi-generation field, a matrix for two (rows the first occurrence's generation, columns the second's). Without
  one: 1 for every generation, or the identity (each generation's number conserved). A zero entry writes no term.
  F̄ΓF X without "+ h.c." needs a symmetric matrix M: Σ_ij M_ij F̄_iΓF_j X is written as Σ_i M_ii F̄_iΓF_i X +
  Σ_{i<j} (M_ij F̄_iΓF_j X + h.c.). Entries are real. Three or more multi-generation occurrences in one term are refused.
- The schema's era 4 (`model_approval.SCHEMA_ERAS`): `masses_gev` and `flavour`, both None by default, so every stored
  model keeps its identity. The workbench's field form takes `generations`; `masses_gev` and `flavour` are written in
  the model's YAML or JSON.

## What is refused (the relic, with the reason; `generic._components`, `_thermal_history`)

For every generic model (the owner's answer, 2026-10-20: the same physics written as two fields or as one field of
two generations gets the same verdict):
- **Several stable components:** a Z₂-odd state that no chain of vertices joins to the dark matter (its number is
  conserved: each generation's, when the couplings conserve flavour, as by default), or a neutral one degenerate with
  the dark matter (it cannot decay to it). ADROIT computes one component's relic.
- **An unresolved thermal history:** each Z₂-odd state must convert, by decays and scatterings, to the dark matter or
  to a state already shown to, faster than 10 H at its own freeze-out (T = m/x_f; `generic_checks.CONTACT`).
  Otherwise its own abundance and its late decays are not computed. The chain matters: Bottaro et al.'s complex
  triplet converts χ⁺⁺ to χ⁰ only through χ⁺.

Chemical equilibrium is a substantive requirement of the usual coannihilation calculation, whose failure changes the
relic (Garny et al., arXiv:1705.09292): it is no longer a flag ("chemical equilibrium not certified") but refuses the
relic. The refusal is scoped to the relic and what depends on it: the model's other calculations (direct detection,
the LHC, indirect searches) and exclusions stay available, and a point another search excludes stays excluded.

Measured on the zoo's development half (the scratch `d5/measure.py`), the checks refuse two entries as the zoo writes
them: De Simone et al.'s and Harz & Petraki's coloured coannihilation, whose coloured partner is degenerate with the
dark matter and joined to it by no interaction (the conversion the papers assume is not written). That is a
limitation of the encoded specifications, not of the papers: their conversion interactions are to be restored from
the sources, the correction documented and the development comparisons rerun; they are not exempted. Every other
development-half model passes (Bottaro et al.'s triplet through the conversion chain).

**The sources, read (the auditor's Z, 2026-10-20).** Neither paper supplies a conversion interaction or coupling to
restore. De Simone et al. (arXiv:1402.6287, §2.1, p. 3): "The two dark particles are kept in thermal equilibrium
among themselves by dark interactions", unspecified. Harz & Petraki (arXiv:1805.01200, §3.1, printed p. 15) leave the
interactions between χ and X unspecified while assuming chemical equilibrium through freeze-out; their eq. (3.1) is the
coloured scalar's QCD. So nothing is restored and both entries stay pending (relic refused, the rest computed): a
conversion coupling would be a new declared modelling input, not a transcription. (De Simone et al.'s target
`g_chi: 2` is the dark matter's degrees of freedom, not a coupling.) The development comparisons are as measured above.

**On the library's route** (the same requirement, by each family's own calculation):
- the t-channel partner: chemical equilibrium was already the relic's prerequisite (the conversion certificate, M27:
  pending unless supported); with y = 0 the partner cannot decay, a second stable component, so its relic is refused;
- the inelastic dark photon's χ₂ (`InelasticDarkPhoton.conversion_reason`): χ₂ → χ₁ e⁺e⁻ through the off-shell A′,
  Γ = 4ε²αα_D δ⁵/(15π m_A′⁴), a lower bound on its conversion, must exceed 10 H at χ₂'s freeze-out (x_f = 20,
  declared); else the relic's prerequisite is pending ("scatterings are not computed on this route"); below δ = 2m_e
  there is no tree-level decay;
- the electroweak multiplets and the inert doublet convert through W and Z exchange with the bath, far faster than H at
  freeze-out: certified by their gauge interactions, which the model cannot switch off.
At the 256 crossings no status changes: all ten inelastic points are certified (about 10⁴ × 10 H at ε = 2.4 × 10⁻³)
and no t-channel point has y = 0.

## Gates

- `tests/model_building/test_generations.py`: three generations, the lightest the dark matter; a flavour matrix
  written once per off-diagonal pair with its h.c., G1 accepting every term; a list for one occurrence; each refusal
  by name; a model without generations unchanged.
- `tests/parameter_space/test_generic_generations.py`: two generations of Dirac dark matter that mix (M₁₂ = 0.3,
  130 against 100 GeV) give the same Ωh² as the two fields written one by one (10⁻⁹); flavour conserved, degenerate,
  and a feeble mixing (10⁻⁹: χ₂ converts at 1.4 × 10⁻²⁶ GeV against 10 H = 3.5 × 10⁻¹⁶ GeV) refused by name; the
  chain on Bottaro et al.'s triplet.
- `tests/model_building/test_spectrum.py`: the audit's G1-9, every generation kept.
- `tests/parameter_space/test_library_thermal_history.py`: the inelastic χ₂ certified at an R3 crossing and pending at
  ε = 10⁻⁹ or δ < 2m_e; a t-channel partner with y = 0 refused.

## What it changes

The expansion changes nothing for a model without a field of several generations (none in the zoo's development
half; G1 refused one before). The checks, now on every model, refuse the two coloured-coannihilation entries'
relic until their conversion is restored from the sources.
