"""Strict archive manifests and verification reports."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal

from pydantic import Field, JsonValue, field_validator

from adroit.core.evidence import InputArtifact
from adroit.core.state import StrictModel


def safe_member(name: str) -> str:
    """Accept only normalized relative POSIX paths, including on Windows hosts."""
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or "\\" in name or ":" in name
            or any(p in ("", ".", "..") for p in name.split("/")) or str(path) != name):
        raise ValueError("unsafe archive member path")
    return name


class ArchiveArtifact(StrictModel):
    """One content-bound member; no filesystem links or executable instructions."""

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0, le=100_000_000)
    role: str

    _safe = field_validator("path")(safe_member)


class ArchiveNode(StrictModel):
    """A typed workflow and explicit graph links independent of saved local paths."""

    id: str
    workflow: str
    result_path: str
    evidence_path: str
    children: list[str] = Field(default_factory=list)
    # a promotion's: the child node that is the result it was promoted from, as its record names it (the auditor's CY
    # recheck, CZ-01, 2026-11-01); absent where none is exported, and in older bundles
    parent: str = Field(default="", exclude_if=lambda v: not v)

    _safe = field_validator("result_path", "evidence_path")(safe_member)


class BundleManifest(StrictModel):
    """Versioned inventory of selected evidence, never a directory-wide backup. Version 2 names a promotion's parent
    (``ArchiveNode.parent``). Version 1 (before the auditor's CZ recheck, DA-03, 2026-11-02) has two layouts: from CZ-01's
    export (2026-11-01) it named the parent too; before, it linked the parent as the promotion's last linked study,
    unnamed (``archive._promotion_edges`` reads each as it was written: the auditor's DA recheck, DB-01, 2026-11-03)."""

    schema_version: Literal[1, 2] = 2
    root: str
    nodes: list[ArchiveNode]
    artifacts: list[ArchiveArtifact]
    references: list[InputArtifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    local_paths: str = ""        # what paths of the exporting machine the files carry (``archive.local_paths``)


class ReconstructedNode(StrictModel):
    """Exactly reconstructed saved decisions; this is not numerical reproduction."""

    id: str
    workflow: str
    evidence_identity: str
    provenance: str
    summary: dict[str, JsonValue]


class VerificationResult(StrictModel):
    """Integrity and reconstruction separately from availability of replay inputs."""

    valid: bool
    archive_sha256: str
    assurance: str = ("internally consistent; provenance not verified: the hashes show that the files agree with "
                      "each other, not who made them; anyone can build a self-consistent bundle")
    nodes: list[ReconstructedNode] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    reproduction_status: str = "not_checked"
    reproduction_reasons: list[str] = Field(default_factory=list)


class ReplayResult(StrictModel):
    """Explicit point/fit comparison under the installed deterministic calculation."""

    workflow: str
    node: str
    status: Literal["matched", "different", "incomplete"]
    calculation: str
    trust: str = ("installed ADROIT code ran on the bundle's inputs, which are untrusted data; the model class was "
                  "rebuilt from the typed model; a match does not establish who made the bundle")
    expected: dict[str, JsonValue] = Field(default_factory=dict)
    actual: dict[str, JsonValue] = Field(default_factory=dict)
    differences: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    relative_tolerance: float = 1e-7
    absolute_tolerance: float = 1e-9
