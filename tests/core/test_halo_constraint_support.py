"""The halo inventory (``docs/halo_constraint_support.md``) names every consumer the code registers: each curated record,
each experiment module and search with events, and each consumer ``halo_choice`` can name as unsupported; and the
records it calls halo-independent are none of those the halo machinery varies. Offline."""
from __future__ import annotations

from pathlib import Path

from adroit.constraints import database
from adroit.core import halo_choice
from adroit.core.halo_choice import CONSUMERS
from adroit.experiments import registry
from adroit.parameter_space import halo_limits

DOC = (Path(__file__).resolve().parents[2] / "docs" / "halo_constraint_support.md").read_text()


def test_every_record_and_module_has_a_row_or_a_mapping():
    missing = [r.id for r in database.records() if f"`{r.id}`" not in DOC]
    assert not missing, f"records with no row or mapping: {missing}"
    modules = [*registry.module_names(), *registry.signal_search_names()]
    assert not [m for m in modules if f"`{m}`" not in DOC]
    for route in ("record:<path>", "anomaly:<ref>", "private-search:<hash>", "si_isoscalar_curve", "sm_higgs_invisible"):
        assert route in DOC, route


def test_the_halo_independent_mapping_holds_none_the_halo_machinery_varies():
    mapped = DOC.split("## The records with no halo input: one row", 1)[1]
    varied = set(halo_limits.recorded_densities()) | {"icecube-1612.05949-sd", "icecube-1612.05949-si"}
    assert not [r for r in varied if f"`{r}`" in mapped]


def test_each_consumer_halo_choice_can_name_is_in_the_inventory():
    assert not [c for c in CONSUMERS if f"`{c}`" not in DOC]
    assert "`shm-2105.00599`" in DOC and all(f.label in DOC for f in halo_choice.FAMILIES.values())
