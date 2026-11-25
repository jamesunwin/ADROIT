"""Checksummed reuse of successful deterministic calculations with exact inputs."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Callable, TypeVar

from pydantic import BaseModel

from adroit.core.checkpoint import atomic_json
from adroit.core.config import env, get_settings
from adroit.core.state import StrictModel

T = TypeVar("T", bound=BaseModel)


class CalculationIdentity(StrictModel):
    """What identifies a cached calculation: the algorithm, its exact inputs, and its dependencies."""
    schema_version: int = 1
    algorithm: str
    inputs: dict
    dependencies: dict


def _sha(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


@contextmanager
def _lock(path: Path):
    try:
        stream = path.open("a")
    except OSError:
        yield False
        return
    with stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def reuse(algorithm: str, inputs: BaseModel, dependencies: Callable[[], dict],
          calculate: Callable[[], T], model: type[T], valid: Callable[[T], bool],
          enabled: bool = True) -> T:
    """Reuse an exact, successful result; otherwise calculate and publish atomically.

    Availability and dependency contents are checked on every lookup. Invalid or
    damaged cache records are misses. Exceptions and rejected outputs are never
    stored. Set ADROIT_CALCULATION_CACHE=off or enabled=False for fresh calculations.
    """
    if not enabled or env("CALCULATION_CACHE", "on") == "off":
        return calculate()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", algorithm):
        raise ValueError("Invalid calculation cache namespace")
    try:
        identity = CalculationIdentity(algorithm=algorithm, inputs=inputs.model_dump(mode="json"),
                                       dependencies=dependencies())
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return calculate()
    key = _sha(identity.model_dump(mode="json"))
    root = get_settings().data_dir / "calculation-cache" / algorithm
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        return calculate()
    path = root / f"{key}.json"
    with _lock(root / f"{key}.lock") as locked:
        if not locked:
            return calculate()
        if path.exists():
            try:
                record = json.loads(path.read_text())
                value = model.model_validate(record["payload"])
                if record["identity"] == key and _sha(record["payload"]) == record["sha256"] and valid(value):
                    return value
            except (OSError, ValueError, KeyError, TypeError):
                pass
        value = calculate()
        if valid(value):
            try:
                if dependencies() == identity.dependencies:
                    payload = value.model_dump(mode="json")
                    atomic_json(path, {"identity": key, "sha256": _sha(payload), "payload": payload})
            except (OSError, RuntimeError, subprocess.SubprocessError):
                pass
        return value
