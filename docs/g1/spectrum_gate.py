"""G1's gate: the spectrum of every development-half zoo benchmark against the masses its paper prints.

Run: ``.venv/bin/python docs/g1/spectrum_gate.py``. The held-out half is not touched (docs/freeze_out_build.md, G1).
Each check is (state label → the paper's mass in GeV, its relative tolerance); a state is found by its role
(the dark matter, or the named field's lightest state of a given charge).
"""

from __future__ import annotations

from adroit.evaluation import core, zoo
from adroit.model_building import spectrum as sp

# (entry id, target index) → {description: (finder, printed mass, relative tolerance)}
PRINTED = {
    ("wino_majorana_triplet_bottaro", 0): {"DM (tree level)": ("dm", 2860.0, 1e-6)},
    ("complex_scalar_triplet_y1_bottaro", 0): {"DM (tree level)": ("dm", 2100.0, 1e-6)},
    ("dark_photon_complex_scalar_feng", 0): {"DM": ("dm", 0.03333, 1e-6), "A′": ("A_prime", 0.1, 1e-6)},
    ("doublet_triplet_fermion_dedes", 0): {"DM = M_D (custodial)": ("dm", 110.0, 1e-6)},
    ("doublet_triplet_fermion_dedes", 1): {"DM = M_D (custodial)": ("dm", 91.0, 1e-6)},
    ("real_scalar_dm_vectorlike_lepton_giacchino", 0): {"DM": ("dm", 150.0, 1e-6), "Ψ": ("Psi+", 174.0, 1e-6)},
    ("singlet_doublet_dirac_bhattacharya", 0): {"M1 (DM)": ("dm", 200.0, 1e-6), "M2": ("N0", 300.0, 1e-6),
                                               "N±": ("N+", 293.0, 1e-3)},
    ("singlet_doublet_dirac_bhattacharya", 2): {"M1 (DM)": ("dm", 325.0, 1e-6), "M2": ("N0", 365.0, 1e-6),
                                               "N±": ("N+", 364.6, 1e-3)},
    ("singlet_triplet_fermion_choubey", 0): {"ρ⁰₁ (DM)": ("dm", 87.6, 1e-6), "ρ⁰₂": ("rho0", 128.0, 1e-6),
                                            "h₁": ("h", 125.5, 1e-6), "h₂": ("Delta0", 195.5, 1e-6),
                                            "H±": ("Delta+", 195.5, 1e-6)},
    ("singlet_triplet_fermion_choubey", 2): {"ρ⁰₁ (DM)": ("dm", 171.1, 1e-6), "ρ⁰₂": ("rho0", 211.0, 1e-6),
                                            "h₂": ("Delta0", 400.0, 1e-6), "H±": ("Delta+", 400.0, 1e-6)},
    ("dirac_fermion_higgs_portal_eft_cpv_gambit", 0): {"DM": ("dm", 9895.0, 1e-6)},
    ("vector_higgs_portal_athron", 0): {"DM (m_V)": ("Vd", 62.46, 1e-6)},
    ("vector_higgs_portal_athron", 1): {"DM (m_V)": ("Vd", 62.46, 1e-6)},
    ("singlet_fermion_scalar_mediator_das", 0): {"h₁": ("h", 125.0, 1e-6), "h₂": ("s0", 200.0, 1e-6)},
    ("singlet_fermion_scalar_mediator_das", 2): {"h₁": ("h", 125.0, 1e-6), "h₂": ("s0", 200.0, 1e-6)},
    ("singlet_fermion_scalar_mediator_das", 3): {"h₂": ("s0", 70.0, 1e-6), "h₁": ("h", 125.0, 1e-6)},
}


def _find(spectrum: sp.Spectrum, finder: str) -> float:
    if finder == "dm":
        return spectrum.dark_matter().mass_gev
    return spectrum.state(finder).mass_gev


def main() -> int:
    """Print each development benchmark's spectrum check; return the number of failures."""
    failures = 0
    for entry in zoo.entries():
        if core.half_of(zoo.NAME, entry.id) is not core.Half.development:
            continue
        for k, target in enumerate(entry.targets):
            try:
                s = sp.spectrum(zoo._spec(entry, target))
            except ValueError as error:
                print(f"{entry.id}[{k}]: refused — {error}")
                continue
            checks = PRINTED.get((entry.id, k), {})
            cells = []
            for label, (finder, mass, tol) in checks.items():
                got = _find(s, finder)
                ok = abs(got / mass - 1) <= tol
                failures += not ok
                cells.append(f"{label} {got:.6g} (paper {mass:g}) {'ok' if ok else 'MISS'}")
            dm = s.dark_matter()
            print(f"{entry.id}[{k}]: DM {dm.name} {dm.kind} {dm.mass_gev:.6g} GeV; " + "; ".join(cells))
            for note in s.notes:
                print(f"    note: {note}")
    print(f"failures: {failures}")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
