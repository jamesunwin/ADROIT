"""Detector targets: elements and compounds with their natural isotopic compositions.

A target is a set of isotopes with their shares of the target's mass. The rate
per kg of target is the mass-weighted sum of the rates per kg of each isotope.
The compositions are in ``data/isotopes.yaml``, with their source.
"""

from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources

import yaml

from adroit.core.dm_state import Isotope, Target


@lru_cache(maxsize=1)
def isotope_data() -> dict:
    """The contents of ``data/isotopes.yaml``."""
    text = resources.files("adroit.physics").joinpath("data/isotopes.yaml").read_text()
    return yaml.safe_load(text)


def available_targets() -> list[str]:
    """The names ``target`` accepts: every element and compound in the data file."""
    data = isotope_data()
    return sorted(data["elements"]) + sorted(data["compounds"])


def _element_mass(symbol: str) -> float:
    """The mean mass number of an element, weighted by abundance."""
    isotopes = isotope_data()["elements"][symbol]["isotopes"]
    return sum(a * abundance for a, (abundance, _spin) in isotopes.items())


def _composition(name: str) -> dict[str, int]:
    """Atoms of each element per formula unit: from the compounds table, or one element."""
    data = isotope_data()
    if name in data["compounds"]:
        return dict(data["compounds"][name])
    if name in data["elements"]:
        return {name: 1}
    raise ValueError(f"unknown target {name!r}; available: {', '.join(available_targets())}")


def target(name: str) -> Target:
    """The natural target ``name`` (an element such as 'Xe', or a compound such as 'CaWO4')."""
    elements = isotope_data()["elements"]
    composition = _composition(name)
    formula_mass = sum(n * _element_mass(symbol) for symbol, n in composition.items())
    isotopes = []
    for symbol, count in composition.items():
        element = elements[symbol]
        for a, (abundance, spin) in element["isotopes"].items():
            share = count * a * abundance / formula_mass
            isotopes.append(Isotope(element=symbol, mass_number=a, atomic_number=element["Z"],
                                    spin=spin, mass_fraction=share))
    return Target(name=name, isotopes=isotopes)


def single_isotope(name: str) -> Target:
    """A target of one isotope, e.g. 'Xe131': for tests and for enriched targets."""
    match = re.fullmatch(r"([A-Z][a-z]?)(\d+)", name)
    if match is None:
        raise ValueError(f"an isotope is written as symbol then mass number, e.g. 'Xe131'; got {name!r}")
    symbol, a = match.group(1), int(match.group(2))
    element = isotope_data()["elements"].get(symbol)
    if element is None or a not in element["isotopes"]:
        raise ValueError(f"no data for the isotope {name}")
    spin = element["isotopes"][a][1]
    return Target(name=name, isotopes=[Isotope(element=symbol, mass_number=a,
                                               atomic_number=element["Z"], spin=spin,
                                               mass_fraction=1.0)])


def spin_expectations(isotope: Isotope) -> tuple[float, float] | None:
    """(⟨S_p⟩, ⟨S_n⟩) for an isotope in the approximation table, or None."""
    entry = isotope_data()["spin_expectations"].get(isotope.name)
    return None if entry is None else (entry["proton"], entry["neutron"])
