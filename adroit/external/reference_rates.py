"""Small subprocess adapter for the pinned dmscatter rate reference.

The output is events/(keV kg day) for a pure isotope. Upstream writes rates
per GeV, so the only output conversion is 1e-6. Every attempt has a fresh
directory, checked exit status and retained stdout. This is a validation
reference and never substitutes for ADROIT's production recoil calculation.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import shutil

import numpy as np
from adroit.core.config import child_environment


def dmscatter(folder: Path, work: Path, density_file: Path, z: int, a: int,
              coefficients: dict[int, tuple[float, float]], low: float = 1,
              high: float = 200, step: float = 1, mass: float = 150,
              controls: dict[str, float] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate the upstream program with explicit halo and coefficient inputs.

    Args:
        folder: Pinned checkout containing bin/dmscatter.
        work: Parent directory for isolated attempts and logs.
        density_file: Absolute upstream .dres file for the selected nucleus.
        z: Nuclear proton number.
        a: Nuclear mass number.
        coefficients: Physical proton/neutron coefficients in GeV^-2.
        low: First recoil energy in keV.
        high: Last recoil energy in keV.
        step: Uniform recoil grid spacing in keV.
        mass: Dark matter mass in GeV.
        controls: Explicit upstream control overrides.

    Returns:
        Recoil energies and rates per keV, kg and day.
    """
    work.mkdir(parents=True, exist_ok=True)
    if any(op not in (1,*range(3,16)) for op in coefficients):
        raise ValueError('dmscatter reference covers O1 and O3–O15')
    attempt = Path(tempfile.mkdtemp(prefix='dmscatter_', dir=work))
    shutil.copyfile(density_file, attempt/'target.dres')
    settings = {'wimpmass': mass, 'dmdens': .3, 'dmspin': .5, 'vearth': 232.,
                'maxwellv0': 220., 'vescape': 550., 'quadrelerr': 1e-6}
    settings.update(controls or {})
    text = ''.join(f'{key} {value!r}\n' for key, value in settings.items())
    # Upstream reads dimensionless c_i and divides by its weak scale squared.
    weak_scale = settings.get('weakmscale',246.2)
    for op, (cp, cn) in coefficients.items():
        text += f'coefnonrel {op} p {cp*weak_scale**2!r}\ncoefnonrel {op} n {cn*weak_scale**2!r}\n'
    (attempt/'case.control').write_text(text)
    input_text = f'er\n{z}\n{a-z}\ncase\ntarget\n{low} {high} {step}\n'
    with (attempt/'stdout.txt').open('w') as log:
        subprocess.run([str(folder/'bin/dmscatter')], input=input_text, text=True,
                       cwd=attempt, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120,
                       env=child_environment())
    energies, rate = np.loadtxt(attempt/'eventrate_spectra.dat', unpack=True)
    if not np.all(np.isfinite(rate)) or not np.any(rate > 0):
        raise ValueError(f'invalid dmscatter spectrum; see {attempt}')
    return energies, rate * 1e-6
