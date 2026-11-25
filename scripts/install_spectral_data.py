"""Verify and unpack the two public spectral data items in the external manifest."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import tarfile
import zipfile


def install(kind: str, folder: Path) -> None:
    """Unpack only the pinned author release, refusing changed downloads."""
    if kind == "pppc":
        archive = folder / "AtProduction_gammas.dat.zip"
        expected = "5adff547fd16ae3cefa55fc37f3d62f0adc37e317a9297ec374708429fac601a"
        if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
            raise ValueError("PPPC archive differs from the validated release")
        with zipfile.ZipFile(archive) as stream:
            (folder / "AtProduction_gammas.dat").write_bytes(stream.read("AtProduction_gammas.dat"))
    else:
        expected = {
            "42263853": "53ece3239910abec1934432c621c54b0",
            "44477168": "1627630e27c73cded88370a9344c66a2",
        }
        for name, digest in expected.items():
            if hashlib.md5((folder / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Dwarf release {name} differs from the validated source")
        with tarfile.open(folder / "42263853") as stream:
            stream.extractall(folder, filter="data")
        (folder / "dSphs.csv").write_bytes((folder / "44477168").read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["pppc", "dwarfs"])
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    install(args.kind, args.folder)
