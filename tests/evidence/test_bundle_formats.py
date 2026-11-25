"""Every bundle format ADROIT has written is kept as an untouched export, and each still verifies (the owner,
2026-11-03, after the auditor's DA recheck: DA-03 had reasoned about an older layout instead of reading one, and refused
dba8e6c's genuine bundles, DB-01).

The practice: each manifest version, and each layout an export wrote under one version, has an untouched promotion
bundle with children and one without, made by the code that wrote it. Before a manifest version changes, the current
one's exports are made and added here; so are a new member format's that the verifier checks (from 3f00efc, study
records naming their result: the auditor's version-identity audit, VI-01, 2026-11-03). A fixture is never made by hand in the
newer code, nor edited after."""
from __future__ import annotations

import hashlib
import json
import typing
from pathlib import Path
from typing import NamedTuple

import pytest

from adroit.evidence import archive
from adroit.evidence.archive_models import BundleManifest

BUNDLES = Path(__file__).parents[1] / "fixtures" / "bundles"


class Export(NamedTuple):
    sha256: str
    version: int
    named: bool          # whether its manifest names the promotion's parent
    children: int        # the promotion's children linked (its parent linked too)
    made_by: str         # the commit whose own exporter wrote it
    records: bool = False   # whether each study record in it names its node's result (VI-01, from 3f00efc)


# the bundles ``promotion_v*_children_*`` and ``promotion_v2_no_child_*`` were made by
# ``scratch_evidence/db_bundles_2026-11-03/test_zz_make_bundle.py`` run in a worktree at the commit named (from
# 3f00efc, its copy in ``scratch_evidence/vi_bundles_2026-11-03/``, whose toy parent record names its result as the run
# writer's does); the others are the auditor's, from its CY and CZ rechecks
EXPORTS = {
    "promotion_v1_stable_A_1c039e0.zip":
        Export("c2933fa17687721b90426b2d90243f2cbcc5168f82e8e304a6873cf677854a02", 1, False, 0, "1c039e0"),
    "promotion_v1_children_1c039e0.zip":
        Export("a0c35010dbe6efd3dad0f53b7dc55317178a3ec5d366b63092a3443735e257e9", 1, False, 2, "1c039e0"),
    "promotion_v1_named_stable_A_dba8e6c.zip":
        Export("fe2bc1ffe59af9c9f61ef88bbbfc2ca1bbfd92e170025ede68099b104a65173f", 1, True, 0, "dba8e6c"),
    "promotion_v1_named_second_B_dba8e6c.zip":
        Export("ec3f6dcaeec54128b58fcdc564492b028792061755635898774452e023087b6b", 1, True, 0, "dba8e6c"),
    "promotion_v1_children_dba8e6c.zip":
        Export("65f7131d670000fc93d09e836dbf4e1a222b6084ad0e562924ebb9712b8d5a11", 1, True, 2, "dba8e6c"),
    "promotion_v2_no_child_5df9c6f.zip":
        Export("b7a66b001ca687805627d1535a3355f38bb70341f37448758e6badc3111cb540", 2, True, 0, "5df9c6f"),
    "promotion_v2_children_5df9c6f.zip":
        Export("231a11d0a6515affbca0aaedb50fac5cf27bab81b02dc84abfe5c76cec296fc3", 2, True, 2, "5df9c6f"),
    "promotion_v2_no_child_3f00efc.zip":
        Export("fbade668736d6ae1246927dabace52814facd42b32f9cac66b45e7244ea37127", 2, True, 0, "3f00efc", True),
    "promotion_v2_children_3f00efc.zip":
        Export("782bc40b0f090fde584d11896876e03cf078dffb29f9a746111de1b7351bef38", 2, True, 2, "3f00efc", True),
}


def test_every_manifest_version_and_layout_has_untouched_exports_with_and_without_children():
    """The practice above, held: every version the manifest admits, and both version 1 layouts (the parent unnamed,
    before CZ-01; named, from it), has a promotion with children and one without among the untouched exports."""
    versions = set(typing.get_args(BundleManifest.model_fields["schema_version"].annotation))
    layouts = {(e.version, e.named) for e in EXPORTS.values()}
    assert {v for v, _ in layouts} == versions, "a manifest version without an untouched export: add one"
    assert (1, False) in layouts and (1, True) in layouts
    for layout in layouts:
        kept = [e for e in EXPORTS.values() if (e.version, e.named) == layout]
        assert any(e.children for e in kept) and any(not e.children for e in kept), layout
    bound = [e for e in EXPORTS.values() if e.records]
    assert any(e.children for e in bound) and any(not e.children for e in bound), "study records naming their result"


@pytest.mark.parametrize("name", list(EXPORTS))
def test_each_untouched_export_verifies_as_it_was_written(name):
    """Each export's bytes are unchanged, its layout is the one recorded, and it verifies with no issue."""
    export = EXPORTS[name]
    path = BUNDLES / name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == export.sha256
    manifest, _ = archive.read_bundle(path)
    root = manifest.nodes[0]
    assert (manifest.schema_version, bool(root.parent), len(root.children)) == \
        (export.version, export.named, export.children + 1)
    found = archive.verify_bundle(path)
    assert found.valid and not found.issues
    records = [json.loads(data) for member, data in archive.read_bundle(path)[1].items() if member.endswith("/study.json")]
    assert all(bool(r.get("result_sha256")) == export.records for r in records)
