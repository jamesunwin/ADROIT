"""Canonical, explicitly selected model approvals; no automatic completion of input."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, NamedTuple

import yaml
from pydantic import Field

from adroit.core.evidence import content_hash
from adroit.core.model_spec import ModelSpec
from adroit.core.state import StrictModel
from adroit.model_building.audit import audit


class ModelApproval(StrictModel):
    """The record of an approved model: its hash, the hash of the model it came from, how it was chosen, and the
    changes between the two."""
    model_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_model_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    choice: Literal["supplied", "generated_from_fields", "general_completion"]
    changes: list[str] = Field(default_factory=list)
    schema_version: int | None = None       # the model's schema era (SCHEMA_ERAS); None: written before 2026-10-16


class SchemaEra(NamedTuple):
    """One form of a stored model: its version, when it began, and the keys it added to ModelSpec, each as (where in
    the model's JSON: "" for the top level, "fields" for each field; the key; its default)."""

    version: int
    since: str
    added: tuple[tuple[str, str, Any], ...]


# Every change to the stored model's schema (ModelSpec and the models inside it) is an era here, with each key it
# added and its default. A stored record's identity is computed in its own era's form, and a record written before
# records carried their era is matched against each era's form in turn. tests/orchestrator/test_schema_eras.py fails
# on a schema field no era accounts for (the external audit of 2026-10-16, A14; before it, one list of later
# defaults, stripped all at once, which an intermediate era could not match).
SCHEMA_ERAS = (
    SchemaEra(1, "2026-10-10 (6c9c73b): models first stored, approved and drafted", ()),
    SchemaEra(2, "2026-10-13 (8e30714, G1): a field's vev_gev and a term's indices",
              (("fields", "vev_gev", None), ("terms", "indices", ""))),
    SchemaEra(3, "2026-10-19 (M27 at leading order in the plasma): the chemical-equilibrium request's plasma settings",
              (("chemical_equilibrium", "plasma", None),)),
    SchemaEra(4, "2026-10-20 (the owner's decision #5, several generations): a field's masses_gev and a term's flavour",
              (("fields", "masses_gev", None), ("terms", "flavour", None))),
    SchemaEra(5, "2026-10-20 (the owner's decision #2): the model's Yukawa convention", (("", "yukawa", "sm"),)),
)
SCHEMA_VERSION = SCHEMA_ERAS[-1].version


def model_identity(spec: ModelSpec) -> str:
    """The content hash of a model specification, in the current era's form."""
    return content_hash(spec.model_dump(mode="json"))


def _without(data: Any, where: list[str], key: str, default: Any) -> bool:
    """Remove ``key`` at ``where`` where it holds its default; False if it holds another value there."""
    if isinstance(data, list):
        return all(_without(item, where, key, default) for item in data)
    if not isinstance(data, dict):
        return True
    if where:
        return _without(data.get(where[0]), where[1:], key, default)
    if key in data:
        if data[key] != default:
            return False
        del data[key]
    return True


def era_identity(spec: ModelSpec, version: int) -> str | None:
    """The hash the model has in era ``version``'s form: the keys added after it removed where they hold their
    defaults. None if the model sets one of them to another value, which that era could not hold."""
    data = spec.model_dump(mode="json")
    for era in SCHEMA_ERAS:
        if era.version > version:
            for where, key, default in era.added:
                if not _without(data, [w for w in where.split(".") if w], key, default):
                    return None
    return content_hash(data)


def verify_identity(spec: ModelSpec, expected: str, version: int | None = None) -> None:
    """Refuse a model whose hash differs from the approved one (no check when none is given). The hash is compared in
    the form of the record's era (``version``), or of each era in turn for a record that does not say."""
    if not expected:
        return
    known = [era.version for era in SCHEMA_ERAS]
    if version is not None and version not in known:
        raise ValueError(f"model schema version {version} is not one this ADROIT knows (1–{SCHEMA_VERSION}); "
                         "it may have been written by a newer ADROIT")
    if expected not in {era_identity(spec, v) for v in ([version] if version is not None else known)}:
        raise ValueError("model changed since approval; review and approve the changed model")


def verify_request(request) -> None:
    """Approval also forbids an inconsistent explicit engine/reference-point override."""
    verify_identity(request.spec,request.approved_model_sha256)
    if request.approved_model_sha256 and (request.model_class is not None or request.fixed is not None):
        from adroit.parameter_space.classify import classify
        cls,point,_=classify(request.spec)
        if ((request.model_class is not None and request.model_class != cls) or
            (request.fixed is not None and request.fixed != point)):
            raise ValueError("engine or fixed point differs from the approved model's numerical mapping")


def _changes(left, right, path="") -> list[str]:
    if isinstance(left,dict) and isinstance(right,dict):
        return [d for key in sorted(left.keys()|right.keys()) for d in
                _changes(left.get(key),right.get(key),f"{path}.{key}".lstrip('.'))]
    if left == right:
        return []
    return [f"{path}: {left!r} -> {right!r}"]


def select_model(result, *, general_completion: bool = False) -> tuple[ModelSpec, ModelApproval]:
    """Keep a supplied Lagrangian exactly; completion is a separate opt-in choice."""
    if result.source == "lagrangian":
        if general_completion and result.general is None:
            raise ValueError("no generated general completion is available")
        selected = result.general if general_completion else result.spec
        choice = "general_completion" if general_completion else "supplied"
    else:
        if general_completion:
            raise ValueError("general completion choice applies only to supplied Lagrangians")
        selected = result.general or result.spec
        choice = "generated_from_fields"
    if not audit(selected).valid:
        raise ValueError("the selected model fails its structural audit")
    approval=ModelApproval(model_sha256=model_identity(selected),
        source_model_sha256=model_identity(result.spec),choice=choice,
        changes=_changes(result.spec.model_dump(mode="json"),selected.model_dump(mode="json")),
        schema_version=SCHEMA_VERSION)
    return selected.model_copy(deep=True),approval


def write_approved(path: Path, spec: ModelSpec, approval: ModelApproval) -> None:
    """Write an approved model with its approval as YAML, after checking its hash and its structural audit; an
    existing file is never overwritten with a different model."""
    verify_identity(spec,approval.model_sha256,approval.schema_version)
    if not audit(spec).valid:
        raise ValueError("the selected model no longer passes its structural audit")
    payload={"spec":spec.model_dump(mode="json"),"approval":approval.model_dump(mode="json")}
    from adroit.core.durable import write_new
    try:                                        # a new file only, whole; one there, written since too, is read below
        write_new(path,yaml.safe_dump(payload,sort_keys=False,allow_unicode=True))  # (the auditor's DL recheck, DM-02's
        return                                  # class, 2026-11-07: checked, then written over, through a link)
    except FileExistsError:
        pass
    existing=yaml.safe_load(path.read_text())
    if existing != payload and not _same_approval(existing, spec):
        raise ValueError("an existing approval cannot be overwritten with a different model")


def _same_approval(existing: Any, spec: ModelSpec) -> bool:
    """Whether an approved YAML written in an earlier era is the same approved model."""
    try:
        return isinstance(existing, dict) and "approval" in existing and read_model(existing) == spec
    except ValueError:
        return False


def read_model(data: dict) -> ModelSpec:
    """Legacy raw/spec-wrapped YAML remains readable; new approval digests are checked."""
    if not isinstance(data,dict):
        raise ValueError("the model must be a YAML object containing fields and interactions")
    spec=ModelSpec.model_validate(data.get("spec",data))
    if "approval" in data:
        approval=ModelApproval.model_validate(data["approval"])
        verify_identity(spec,approval.model_sha256,approval.schema_version)
    return spec
