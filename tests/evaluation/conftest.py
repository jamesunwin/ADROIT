"""A synthetic injection target: three candidates on a small grid, two of them the same shape."""

from __future__ import annotations

import numpy as np
import pytest

from adroit.evaluation import core, injection
from adroit.library.interactions import degeneracy

TOY = "Toy (synthetic)"


@pytest.fixture
def toy_target(monkeypatch):
    energies = np.linspace(1.0, 50.0, 200)
    falling = np.exp(-energies / 5.0)
    rising = energies.copy()
    shapes = np.array([falling, falling, rising])
    shapes /= np.trapezoid(shapes, energies, axis=1)[:, None]
    labels = ["O1s@5", "O1v@5", "O3s@50"]
    n2 = degeneracy.events_to_separate(degeneracy.jeffreys_matrix(shapes, energies))
    table = (labels, energies, shapes, 0.1 / 49.0, n2)
    monkeypatch.setattr(injection, "TARGETS", {TOY: ("Toy search", [5.0])})
    monkeypatch.setattr(injection, "EVENTS", [5, 50])
    monkeypatch.setattr(injection, "PER_POINT", 6)
    monkeypatch.setattr(injection, "table", lambda target: table)
    monkeypatch.setattr(injection, "models", lambda target: [
        ("O1s@5", "O1", "s", 5.0, 0.0), ("O1v@5", "O1", "v", 5.0, 0.0), ("O3s@50", "O3", "s", 50.0, 0.0)])
    injection.classes.cache_clear()
    yield table
    injection.classes.cache_clear()


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setattr(core, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(core, "LEDGER", tmp_path / "ledger.jsonl")
    return tmp_path
