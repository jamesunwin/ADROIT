"""The auditor's DA recheck, DB-01 and DB-02 (2026-11-03). DB-01: DA-03's verifier had refused valid bundles exported at
dba8e6c, whose version 1 manifests name a promotion's parent, as "an invalid study graph". DB-02: ``adroit native-fit``
and ``adroit native-coverage`` printed ``report.md`` read again after publishing, so another result's report, published
there since, was printed beside the original run's exit. Each bundle here is an untouched export of the pin it names,
made by that pin's own exporter; each command runs through Typer, its request, its writer and its output, with only the
expensive calculation substituted by a typed saved result."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from adroit.core.durable import write_atomic
from adroit.evidence import archive, bindings, build
from tests.evidence.test_bundle_formats import EXPORTS as FORMATS

BUNDLES = Path(__file__).parents[1] / "fixtures" / "bundles"
# each untouched version 1 export: its digest, whether its manifest names the promotion's parent, and how many children
# it links (the registry of every format's exports, and how each was made: tests/evidence/test_bundle_formats.py)
EXPORTS = {name: (e.sha256, e.named, e.children) for name, e in FORMATS.items() if e.version == 1}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- DB-01 ------------------------------------------------------------------------------------------------------


def _parent(manifest) -> str:
    """The promotion's parent as its export linked it: named, or (unnamed) the last link."""
    root = manifest.nodes[0]
    return root.parent or root.children[-1]


def _other_parent(files: dict[str, bytes], node: str) -> dict[str, bytes]:
    """B: a coherent other version of the parent signal study, its result and that result's evidence."""
    from adroit.evidence.results import typed
    data = json.loads(files[f"studies/{node}/result.json"])
    data["created"] = "2026-10-30"
    content = json.dumps(data).encode()
    kind, result = typed(data, "signal")
    return {f"studies/{node}/result.json": content,
            f"studies/{node}/evidence.json": build.build(kind, result, sha(content)).model_dump_json().encode()}


@pytest.mark.parametrize("name", list(EXPORTS))
def test_an_untouched_bundle_of_each_earlier_format_verifies(name):
    """DB-01, the auditor's case and its regression: the exports of 1c039e0 (the parent linked after the children, unnamed)
    and of dba8e6c (the parent named and linked), each still version 1, with and without children, verify as they did
    at the pin that made them, their bytes unchanged."""
    digest, named, children = EXPORTS[name]
    path = BUNDLES / name
    assert sha(path.read_bytes()) == digest
    manifest, _ = archive.read_bundle(path)
    root = manifest.nodes[0]
    assert manifest.schema_version == 1 and bool(root.parent) == named and len(root.children) == children + 1
    found = archive.verify_bundle(path)
    assert found.valid and not found.issues


@pytest.mark.parametrize("name", [n for n in EXPORTS if "second_B" not in n])
def test_a_coherent_other_parent_is_refused_in_each_earlier_format(tmp_path, name):
    """DB-01's negative control in each layout: the parent replaced by another coherent version of it, the manifest's
    hashes updated. It does not verify: the parent, named or linked last, is checked against the record's digest."""
    from tests.orchestrator.test_cz_recheck import _forged
    manifest, files = archive.read_bundle(BUNDLES / name)
    forged = _forged(BUNDLES / name, tmp_path / "parent.zip", _other_parent(files, _parent(manifest)))
    found = archive.verify_bundle(forged)
    assert not found.valid and "promotion/parent mismatch" in found.issues[0]


@pytest.mark.parametrize("edit", ["a child named the parent", "an unlinked study named the parent"])
def test_a_version_1_manifest_naming_another_study_its_parent_does_not_verify(tmp_path, edit):
    """DB-01: a version 1 manifest naming a parent is checked by that name, as version 2's is: one naming a child
    (another version than the result it was promoted from), or a study it does not link, does not verify."""
    from tests.orchestrator.test_cz_recheck import _forged
    source = BUNDLES / "promotion_v1_children_dba8e6c.zip"

    def edited(manifest):
        manifest.nodes[0].parent = "n1"
        if edit == "an unlinked study named the parent":
            manifest.nodes[0].children.remove("n1")
    found = archive.verify_bundle(_forged(source, tmp_path / "named.zip", {}, edited))
    assert not found.valid
    assert ("promotion/parent mismatch" if edit == "a child named the parent" else "is not one of its linked studies") \
        in found.issues[0]


def test_a_dba8e6c_bundle_read_in_the_older_layout_keeps_its_parent(tmp_path):
    """DB-01: the dba8e6c export with its parent's name removed is 1c039e0's layout (the parent linked last); it reads
    the same parent and verifies, and with its parent then replaced it does not."""
    from tests.orchestrator.test_cz_recheck import _forged
    source = BUNDLES / "promotion_v1_children_dba8e6c.zip"

    def unnamed(manifest):
        manifest.nodes[0].parent = ""
    assert archive.verify_bundle(_forged(source, tmp_path / "unnamed.zip", {}, unnamed)).valid
    _, files = archive.read_bundle(source)
    found = archive.verify_bundle(_forged(source, tmp_path / "both.zip", _other_parent(files, "n3"), unnamed))
    assert not found.valid and "promotion/parent mismatch" in found.issues[0]


# --- DB-02 ------------------------------------------------------------------------------------------------------


def _lines(text: str) -> set[str]:
    """A report's lines, without its dates (``chronology.analysis_report``'s block: each rendering has its own)."""
    start, end = "<!-- adroit-chronology -->", "<!-- /adroit-chronology -->"
    while start in text and end in text.split(start, 1)[1]:
        before, rest = text.split(start, 1)
        text = before + rest.split(end, 1)[1]
    return {line.strip() for line in text.splitlines() if line.strip()}


def _native_fit(tmp_path: Path):
    """The auditor's final fixture: the model and domain files, and A and B of a bounded domain fit (q0 2 against 99)."""
    from adroit.core.fit_domain import FitCoordinate, PhysicalDomain
    from adroit.parameter_space import native_joint, simplified
    from adroit.parameter_space.classify import classify
    from adroit.parameter_space.multiparameter_fit import DomainFit
    spec = simplified.model("vector", 60, 125)
    domain = PhysicalDomain(coordinates=[FitCoordinate(parameter="g_chi", low=0.01, high=1)])
    (tmp_path / "model.yaml").write_text(yaml.safe_dump(spec.model_dump(mode="json")))
    (tmp_path / "domain.yaml").write_text(yaml.safe_dump(domain.model_dump(mode="json")))
    settings = native_joint.JointSettings(toys=20, domain=domain)
    point = classify(spec)[1]
    a = native_joint.JointResult(settings=settings, masses_gev=[60], complete=True, observed_max_q0=2.0,
                                 assumptions=["AUDIT A computed q0=2"],
                                 domain_fit=DomainFit(domain=domain, reference_point=point,
                                                      settings=settings.domain_settings, point=point, log_l=1.0,
                                                      null_log_l=0.0, q0=2.0, resolved=True, identifiable=True))
    b = a.model_copy(deep=True)
    b.observed_max_q0, b.domain_fit.q0, b.domain_fit.log_l, b.assumptions = 99.0, 99.0, 49.5, ["AUDIT B other q0=99"]
    return a, b


def _after_kept(folder: Path, report_b: str, b, replace: bool):
    """The writer's last check of its parts (``build.kept_parts`` with its report; ``build.kept`` until the auditor's DD
    recheck, DE-02, added it), after which (``replace``) B's report, bound to B, is published at the folder: after the
    writer's last check, before the command prints."""
    real = build.kept_parts

    def kept_parts(path, content, wrote, *args, **kw):
        answer = real(path, content, wrote, *args, **kw)
        if replace and "report" in wrote:
            write_atomic(folder / "report.md", bindings.bind(report_b, sha(b.model_dump_json(indent=2).encode()),
                                                             folder, []))
        return answer
    return kept_parts


@pytest.mark.parametrize("replace", [False, True], ids=["stable", "replaced after publication"])
def test_native_fit_prints_the_report_of_the_result_it_computed(tmp_path, replace):
    """DB-02, the auditor's native-fit case: B's report (the production formatter's, bound to B) published after the writer's
    last check. The command prints A's report, as written, with A's exit; unraced, the same."""
    from adroit.orchestrator import cli
    from adroit.orchestrator.single_idea import _native_report
    from adroit.parameter_space import native_joint
    a, b = _native_fit(tmp_path)
    folder = tmp_path / "out"
    report_a, report_b = ("\n".join(_native_report(r)) + "\n" for r in (a, b))
    with patch.object(native_joint, "run", return_value=a), \
            patch.object(build, "kept_parts", _after_kept(folder, report_b, b, replace)):
        done = CliRunner().invoke(cli.app, ["native-fit", str(tmp_path / "model.yaml"), "--domain",
                                            str(tmp_path / "domain.yaml"), "--out", str(folder)])
    assert done.exit_code == 0, done.output
    assert json.loads((folder / "result.json").read_bytes())["observed_max_q0"] == 2.0
    assert _lines(report_a) - _lines(report_b) <= _lines(done.stdout)
    assert not (_lines(report_b) - _lines(report_a)) & _lines(done.stdout)
    state = bindings.read_report(folder / "report.md", sha((folder / "result.json").read_bytes())).state
    assert state == ("other" if replace else "bound")


@pytest.mark.parametrize("replace", [False, True], ids=["stable", "replaced after publication"])
def test_native_coverage_prints_the_report_and_exit_of_the_result_it_holds(tmp_path, replace):
    """DB-02, the auditor's native-coverage case: A complete (20 maxima, inconclusive on the tested grid), B's report
    (incomplete, none) published after the writer's last check. The command prints A's report and exits as A does."""
    from adroit.orchestrator import cli
    from adroit.orchestrator import native_coverage as nc
    from adroit.parameter_space import simplified
    from adroit.parameter_space.native_coverage import CoverageCase
    request = nc.CoverageRequest(spec=simplified.model("vector", 60, 125), masses_gev=[60],
                                 scenarios=[nc.NuisanceScenario(theta=1.0, null_backgrounds=[1.0, 1.0])],
                                 settings=nc.CoverageSettings(outer_trials=1, inner_toys=19))
    (tmp_path / "request.json").write_text(request.model_dump_json())
    a = nc.CoverageResult(settings=request.settings, masses_gev=[60], complete=True, fits=20,
                          conclusion="inconclusive_on_tested_grid",
                          cases=[CoverageCase(scenario=request.scenarios[0], complete=True, trials=1, rejections=0,
                                              fraction=0.0, interval=(0.0, 0.975), conclusion="inconclusive")])
    b = a.model_copy(update={"complete": False, "fits": 0, "conclusion": "incomplete", "cases": []})
    folder = tmp_path / "out"
    with patch.object(nc, "prepare", return_value=None), patch.object(nc, "observed_data", return_value=None), \
            patch.object(nc, "study", return_value=a), \
            patch.object(build, "kept_parts", _after_kept(folder, nc.report(b), b, replace)):
        done = CliRunner().invoke(cli.app, ["native-coverage", str(tmp_path / "request.json"), "--out", str(folder)])
    assert done.exit_code == 0, done.output
    assert json.loads((folder / "result.json").read_bytes())["conclusion"] == "inconclusive_on_tested_grid"
    assert _lines(nc.report(a)) - _lines(nc.report(b)) <= _lines(done.stdout)
    assert not (_lines(nc.report(b)) - _lines(nc.report(a))) & _lines(done.stdout)
