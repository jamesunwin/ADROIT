"""G11's gap drafting: a draft stays in quarantine and reaches no verdict (``agents.gap_drafter``)."""

import re
import sys
from pathlib import Path

import pytest

from adroit.agents import gap_drafter as gd
from adroit.agents.llm import FakeLLMClient

PACKAGE = Path(gd.__file__).resolve().parents[1]

DRAFT = gd.Draft(name="Sudakov line factor", purpose="a test draft",
                 module_code="FACTOR = 0.5\n\ndef factor(m):\n    return FACTOR\n",
                 test_code="from sudakov_line_factor import factor\n\ndef test_factor():\n    assert factor(1.0) == 0.5\n",
                 references=["Someone et al., arXiv:0000.00000, eq. (1)"], open_questions=["check the normalisation"])


def test_a_draft_is_written_to_quarantine_with_its_provenance(tmp_path):
    folder = gd.GapDrafter(FakeLLMClient([DRAFT]), "fake-model").run("the line's Sudakov factor", root=tmp_path)
    assert folder.parent == tmp_path and (folder / "sudakov_line_factor.py").exists()
    notes = (folder / "DRAFT.md").read_text()
    assert "provisional: not reviewed" in notes and "fake-model" in notes and "check the normalisation" in notes


def test_a_drafts_tests_run_apart_for_a_reviewer(tmp_path):
    folder = gd.write(DRAFT, "a gap", "fake-model", tmp_path)
    ok, log = gd.review(folder)
    assert ok, log


DRAFT_FOLDER = re.compile(r"""PROJECT_ROOT\s*/\s*["']drafts["']|drafts/quarantine|["']quarantine["']"""
                          r"""|\bQUARANTINE\b.*gap_drafter|gap_drafter\b.*\bQUARANTINE\b""")     # the project's drafts


def test_nothing_in_the_package_imports_a_draft():
    """The quarantine's guarantee: no module of ``adroit`` imports from ``drafts`` or names its folder (``drafts/
    quarantine``, the gap drafter's ``QUARANTINE``), and so none puts it on the path. The word "quarantine" alone had
    stood for the folder; DIAMX's generations set aside (``experiments.xenon.quarantine``, the auditor's DW recheck, DX-01)
    are another thing, and the folder's own names are what is checked now (2026-11-13)."""
    offenders = []
    for path in PACKAGE.rglob("*.py"):
        if path.name == "gap_drafter.py":
            continue
        text = path.read_text()
        if re.search(r"^\s*(from|import)\s+drafts\b", text, re.M) or DRAFT_FOLDER.search(text):
            offenders.append(str(path.relative_to(PACKAGE)))
    assert offenders == []


@pytest.mark.parametrize("line", ['sys.path.insert(0, str(PROJECT_ROOT / "drafts"))', 'root = "drafts/quarantine/x"',
                                  "from adroit.agents.gap_drafter import QUARANTINE",
                                  'folder = PROJECT_ROOT / "drafts" / "quarantine"'])
def test_the_guard_catches_each_way_of_naming_the_drafts_folder(line):
    assert DRAFT_FOLDER.search(line)


@pytest.mark.needs("solar_model")
def test_a_scan_with_a_draft_present_reaches_no_drafted_code(tmp_path):
    """A full evaluation of a point, with a draft in the quarantine, imports nothing from it."""
    from adroit.evaluation import zoo
    from adroit.parameter_space.scan import evaluate
    gd.write(DRAFT, "a gap", "fake-model", tmp_path)
    e = next(x for x in zoo.entries() if x.id == "dirac_fermion_higgs_portal_eft_cpv_gambit")
    engine, point = zoo._generic(e, e.targets[0])
    evaluate(engine, point)
    assert not any("sudakov_line_factor" in name for name in sys.modules)
