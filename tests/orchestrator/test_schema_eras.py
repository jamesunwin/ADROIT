"""Stored models across the schema's eras (the external audit of 2026-10-16, A14).

``tests/fixtures/schema_eras`` holds records written by each era's own code (``generate.py``): a library revision
with its approval, an intake session's typed step, and an approved model's YAML. Era 1 is the code of 2026-10-10
(6c9c73b), when models were first stored; era 2 adds a field's ``vev_gev`` and a term's ``indices`` (G1, 8e30714),
here as written before records carried their version (b1b7cf5)."""

from __future__ import annotations

import json
import shutil
import typing
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel

from adroit.core.evidence import content_hash
from adroit.core.model_spec import ModelSpec
from adroit.library.personal import Catalog
from adroit.orchestrator import model_approval as ma
from adroit.orchestrator.model_intake import Intake

FIXTURES = Path(__file__).parents[1] / "fixtures" / "schema_eras"
ERAS = {"era1": 1, "era2_unversioned": 2}


def schema_paths(cls: type[BaseModel], prefix: str = "ModelSpec", ancestry: tuple = ()) -> list[str]:
    """Every field of a model and of the models inside it, as dotted paths (a model inside itself is not entered);
    the walk that wrote ``era1_model_fields.json`` from era 1's code."""
    out = []
    for name, f in cls.model_fields.items():
        path = f"{prefix}.{name}"
        out.append(path)
        stack = [f.annotation]
        while stack:
            a = stack.pop()
            if isinstance(a, type) and issubclass(a, BaseModel) and a not in ancestry + (cls,):
                out.extend(schema_paths(a, path, ancestry + (cls,)))
            stack.extend(typing.get_args(a))
    return sorted(set(out))


def _field(where: str, key: str):
    """The pydantic field at ``where.key`` inside ModelSpec."""
    cls: type[BaseModel] = ModelSpec
    for part in [p for p in where.split(".") if p]:
        stack, found = [cls.model_fields[part].annotation], None
        while stack and found is None:
            a = stack.pop()
            if isinstance(a, type) and issubclass(a, BaseModel):
                found = a
            stack.extend(typing.get_args(a))
        cls = found
    return cls.model_fields[key]


def _copy(tmp_path: Path, era: str) -> tuple[Path, dict]:
    shutil.copytree(FIXTURES / era, tmp_path / era)
    return tmp_path / era, json.loads((tmp_path / era / "index.json").read_text())


def _revision_file(root: Path, reference: str) -> Path:
    model_id, _, revision = reference.removeprefix("catalog:").partition("@")
    return root / "library" / "models" / model_id / "revisions" / f"{revision}.json"


def _rewrite(path: Path, change) -> str:
    """Change a stored revision and give it the revision id its new content hashes to (so only the model's own
    identity can catch the change); returns the new reference."""
    raw = json.loads(path.read_text())
    change(raw)
    raw.pop("revision_id")
    new = content_hash(raw)
    path.unlink()
    (path.parent / f"{new}.json").write_text(json.dumps({**raw, "revision_id": new}))
    return f"catalog:{raw['model_id']}@{new}"


def test_every_schema_field_is_accounted_for_by_an_era() -> None:
    """A field added to ModelSpec (or to a model inside it) without an era in ``SCHEMA_ERAS`` fails here, so the
    compatibility of stored records is decided, not left to chance; a removed field fails too."""
    era1 = set(json.loads((FIXTURES / "era1_model_fields.json").read_text())["fields"])
    now = set(schema_paths(ModelSpec))
    added = {".".join(filter(None, ["ModelSpec", where, key])) for e in ma.SCHEMA_ERAS for where, key, _ in e.added}
    assert not era1 - now, f"removed since era 1, which no era can describe: {sorted(era1 - now)}"
    unaccounted = sorted(p for p in now - era1 if not any(p == a or p.startswith(a + ".") for a in added))
    assert not unaccounted, f"add an era to model_approval.SCHEMA_ERAS for {unaccounted}"
    for e in ma.SCHEMA_ERAS:
        for where, key, default in e.added:
            assert _field(where, key).default == default, (where, key)
    assert [e.version for e in ma.SCHEMA_ERAS] == list(range(1, ma.SCHEMA_VERSION + 1))


@pytest.mark.parametrize("era", ERAS)
def test_a_revision_of_each_era_loads_in_its_own_form(tmp_path: Path, era: str) -> None:
    root, index = _copy(tmp_path, era)
    r = Catalog(root / "library").load(index["revision"])
    assert r.schema_version is None and r.approval.schema_version is None      # written before versions
    assert ma.era_identity(r.spec, ERAS[era]) == index["model_sha256"] == r.model_sha256
    assert ma.era_identity(r.spec, 3 - ERAS[era]) != r.model_sha256              # the other era's form differs


@pytest.mark.parametrize("era", ERAS)
def test_a_draft_and_an_approved_yaml_of_each_era_load(tmp_path: Path, era: str) -> None:
    root, index = _copy(tmp_path, era)
    intake = Intake(Catalog(root / "library"))
    draft = intake.load(index["session"], index["step"])
    assert draft.schema_version is None
    spec = ma.read_model(yaml.safe_load((root / "approved.yaml").read_text()))
    assert ma.era_identity(spec, ERAS[era]) == index["model_sha256"]
    # approving the stored step again, with the hash its era showed, returns the revision already saved
    choice = draft.choices[0]
    again = intake.approve(index["session"], index["step"], 0, confirmed=True,
                           expected_model_hash=index["model_sha256"], tex=choice.tex)
    assert again.reference == index["revision"]


def test_a_changed_value_matches_no_era(tmp_path: Path) -> None:
    """Tamper rejection is kept: a changed mass, or a later key (a term's indices) set to a value era 1 could not
    hold."""
    root, index = _copy(tmp_path, "era1")
    path = _revision_file(root, index["revision"])
    catalog = Catalog(root / "library")

    def mass(raw):
        raw["spec"]["fields"][0]["mass_gev"] = 11.0

    with pytest.raises(ValueError, match="model changed"):
        catalog.load(_rewrite(path, mass))
    root, index = _copy(tmp_path / "again", "era1")

    def indices(raw):
        raw["spec"]["terms"][0]["indices"] = "chi*[a] chi[a]"

    with pytest.raises(ValueError, match="model changed"):
        Catalog(root / "library").load(_rewrite(_revision_file(root, index["revision"]), indices))


def test_a_declared_era_is_the_only_form_tried(tmp_path: Path) -> None:
    """A record that says it is of era 2 but carries era 1's hash is refused; an era this code does not know is
    named as such."""
    root, index = _copy(tmp_path, "era1")
    path = _revision_file(root, index["revision"])

    def claim(raw):
        raw["schema_version"] = raw["approval"]["schema_version"] = 2

    with pytest.raises(ValueError, match="model changed"):
        Catalog(root / "library").load(_rewrite(path, claim))
    spec = ModelSpec.model_validate(json.loads(next((root / "library" / "models").rglob("*.json")).read_text())["spec"])
    with pytest.raises(ValueError, match="newer"):
        ma.verify_identity(spec, index["model_sha256"], 99)


def test_new_records_carry_the_current_version(tmp_path: Path) -> None:
    from adroit.orchestrator import ideas
    from adroit.parameter_space.simplified import model
    selected, approval = ma.select_model(ideas.from_lagrangian(model("vector", 10, 125, .001, .25)))
    assert approval.schema_version == ma.SCHEMA_VERSION
    catalog = Catalog(tmp_path / "library")
    r = catalog.save(selected, approval)
    assert r.schema_version == ma.SCHEMA_VERSION and catalog.load(r.reference) == r
    intake = Intake(catalog)
    s = intake.start()
    step = intake.step(s.session_id, "typed", yaml.safe_dump(selected.model_dump(mode="json")))
    assert step.schema_version == ma.SCHEMA_VERSION
    assert intake.load(s.session_id, step.step_id) == step


@pytest.mark.parametrize("era", ERAS)
def test_saving_an_older_eras_approval_writes_a_readable_revision(tmp_path: Path, era: str) -> None:
    """The external audit of 2026-10-17, I17-1: ``Catalog.save`` with an authentic era-1 approval stored its era-1
    hash under schema version 2, so the revision could be neither loaded nor listed. The revision now carries its
    own current identity; the approval is kept as written."""
    root, _ = _copy(tmp_path, era)
    data = yaml.safe_load((root / "approved.yaml").read_text())
    spec, approval = ma.read_model(data), ma.ModelApproval.model_validate(data["approval"])
    catalog = Catalog(tmp_path / "fresh")
    saved = catalog.save(spec, approval)
    loaded = catalog.load(saved.reference)
    assert loaded.model_sha256 == ma.model_identity(spec) and loaded.schema_version == ma.SCHEMA_VERSION
    assert loaded.approval == approval and loaded.approval.schema_version is None
    assert [r.reference for r in catalog.list()] == [saved.reference]
