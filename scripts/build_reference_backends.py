"""Reproducible compatibility build for pinned optional reference programs."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess


def build_dmscatter(folder: Path) -> None:
    """Correct a malformed display FORMAT and a missing Makefile dependency; leave all physics expressions intact.

    orbitals.f90 uses the module ``main``, but the Makefile gives ``orbitals.o`` no prerequisite, so a parallel make
    could compile it first and stop at "Cannot open module file 'main.mod'" (seen in the clean-machine install test,
    2026-10-12)."""
    source = folder / 'src/parameters.f90'
    old, new = '(I2,x2e11.4,e11.4,e11.4,e11.4)', '(I2,2X,4E11.4)'
    text = source.read_text()
    if old not in text and new not in text:
        raise ValueError('unexpected dmscatter FORMAT: check the pinned source')
    if old in text:
        source.write_text(text.replace(old, new))
    makefile = folder / 'make/Makefile'
    lines = makefile.read_text().split('\n')
    rules = [i for i, line in enumerate(lines) if line.split(':')[0].strip() == 'orbitals.o' and ':' in line]
    if len(rules) != 1:
        raise ValueError('unexpected dmscatter Makefile: check the pinned source')
    if 'main.o' not in lines[rules[0]]:
        lines[rules[0]] = lines[rules[0]].rstrip() + ' main.o'
        makefile.write_text('\n'.join(lines))
    subprocess.run(['make', '-j2', 'openmp'], cwd=folder/'make', check=True)


def configure_madgraph(folder: Path) -> None:
    """MadGraph's input/mg5_configuration.txt (from its default, as MadGraph's first run makes it): no automatic
    updates, and the installed gfortran."""
    gfortran = shutil.which('gfortran')
    if gfortran is None:
        raise ValueError('MadGraph needs gfortran on the PATH')
    config = folder / 'input/mg5_configuration.txt'
    if not config.is_file():
        shutil.copyfile(folder / 'input/.mg5_configuration_default.txt', config)
    settings = {'auto_update': '0', 'fortran_compiler': gfortran}
    lines = config.read_text().split('\n')
    for i, line in enumerate(lines):
        key = line.lstrip('# ').split('=')[0].strip()
        if '=' in line and key in settings:
            lines[i] = f'{key} = {settings.pop(key)}'
    if settings:
        raise ValueError(f'unexpected MadGraph configuration: {sorted(settings)} not found')
    config.write_text('\n'.join(lines))


def main() -> None:
    """Build or configure only the explicitly selected item."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('backend', choices=['dmscatter', 'madgraph'])
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    {'dmscatter': build_dmscatter, 'madgraph': configure_madgraph}[args.backend](args.folder)


if __name__ == '__main__':
    main()
