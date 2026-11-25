"""Source-bound validation of an additional native likelihood response.

This certificate does not change the existing DM3 limit eligibility masks.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from pydantic import Field

from adroit.core.state import StrictModel
from adroit.core.dm_state import ValidationResult

ROOT = Path(__file__).resolve().parents[2]
CERTIFICATE = ROOT / "adroit/experiments/data/native_pico_si_validation.yaml"


class NativeCertificate(StrictModel):
    """Range, numerical comparisons and content identities behind native SI use."""

    experiment: str
    kind: str
    range_gev: tuple[float, float]
    purpose: str
    fidelity: str
    curve_file: str
    curve_sha256: str
    response_hashes: dict[str, str] = Field(min_length=1)
    validation: ValidationResult


def certified_range(experiment: str, certificate: Path = CERTIFICATE) -> tuple[float, float] | None:
    """Return the checked native SI range; changed inputs invalidate the certificate."""
    if not certificate.is_file():
        return None
    c = NativeCertificate.model_validate(yaml.safe_load(certificate.read_text()))
    if (
        c.experiment != experiment
        or c.kind != "SI"
        or not c.validation.passed
        or c.range_gev != c.validation.validated_range
    ):
        return None
    for name, expected in {**c.response_hashes, c.curve_file: c.curve_sha256}.items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or path.parts[0] != "adroit":
            return None
        target = ROOT / path
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            return None
    return c.range_gev
