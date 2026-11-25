"""The standard model library (the owner, 2026-10-13): every model ADROIT has the code to formulate."""

import pytest

from adroit.library import standard


def test_every_portal_model_and_interaction_is_listed_once():
    from adroit.library.interactions import registry
    from adroit.parameter_space import library
    entries = standard.entries()
    assert len({e.id for e in entries}) == len(entries) == len(library.ENTRIES) + len(registry.cards())
    assert sum(e.kind == "portal" for e in entries) == 27 and len(entries) == 82


def test_over_fifty_entries_are_grouped_by_category_and_subcategory():
    groups = standard.grouped()
    assert list(groups) == [standard.PORTALS, standard.INTERACTIONS]
    assert set(groups[standard.PORTALS]) == set(standard.FAMILIES.values())
    assert len(groups[standard.INTERACTIONS]["Nucleon-level operators O_i"]) == 14
    assert len(groups[standard.INTERACTIONS]["Relativistic interactions in LZ's conventions"]) == 7
    assert all(e.subcategory == sub for subs in groups.values() for sub, items in subs.items() for e in items)


def test_search_keeps_entries_matching_every_word():
    found = [e.id for subs in standard.grouped("dark photon dirac").values() for items in subs.values() for e in items]
    assert "dark_photon_dirac" in found and "wino" not in found
    assert standard.grouped("no such model anywhere") == {}


def test_an_unknown_id_is_refused():
    assert standard.entry("wino").kind == "portal" and standard.entry("L01").kind == "interaction"
    with pytest.raises(KeyError):
        standard.entry("no_such_model")
