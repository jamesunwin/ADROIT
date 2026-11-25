# Neutrino-fog data (O'Hare)

Copied from Ciaran O'Hare's NeutrinoFog repository (https://github.com/cajohare/NeutrinoFog), commit
`0df3d0cd2322602dc147a66d94055f7f64879d80`, under its MIT licence (`LICENSE-NeutrinoFog`, kept with the files).

- `spectra/NAME.txt`: the normalised neutrino spectra (E_ν in MeV, dΦ/dE_ν per MeV, unit total flux), the
  repository's `data/neutrinos/normalised/`. The lines (pep, the two ⁷Be lines) are not files: their energies are in
  `adroit.physics.neutrino_fog.FLUXES`.
- `floors/TARGET_SI.txt`: the published spin-independent neutrino floors (mass in GeV, σ in cm²), the repository's
  `data/floors/`, from arXiv:2109.03116. `Xe_SI.txt` is the standard curve, as LZ and XENONnT draw it.

ADROIT's own calculation (`neutrino_fog.fog`) reproduces these floors from the spectra (the validation in
`docs/neutrino_fog.md`); the published curves are the standard overlay, the calculation the advanced settings.
