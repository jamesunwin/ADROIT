"""The records' source papers for review (prepared for the owner's signing, 2026-10-24): the PDG's review, which is
not an arXiv paper, is named as what it is, never fetched from arXiv nor linked there, and one paper that cannot be
fetched leaves the others fetched. (The review page's test is in tests/ui/test_combined_audit_v1.py, where the
workbench's tests run with their fixtures.)"""
from __future__ import annotations

from typer.testing import CliRunner

from adroit.constraints import database, review
from adroit.core.config import get_settings

PDG = "pdg-2024-electroweak-st"


def test_every_figure_reference_but_the_pdg_review_is_an_arxiv_paper():
    elsewhere = [r.id for r in database.records() if r.figure is not None and not review.on_arxiv(r)]
    assert elsewhere == [PDG]
    assert review.on_arxiv(database.record("lep-charginos"))                          # hep-ex/0311019


def test_fetching_the_sources_names_the_pdg_review_and_goes_past_a_failure(tmp_path, monkeypatch):
    """``pdg-2024-ew`` had been requested from arXiv (a 404, which ended the command, every later record unfetched)."""
    import requests
    from adroit.orchestrator import cli
    monkeypatch.setattr(get_settings(), "tools_dir", tmp_path)
    asked = []

    class Reply:
        content = b"%PDF"

        def raise_for_status(self):
            pass

    def get(url, timeout, headers):
        asked.append(url)
        if url.endswith("1808.03684"):
            raise requests.ConnectionError("no route")
        return Reply()
    monkeypatch.setattr(requests, "get", get)
    out = CliRunner().invoke(cli.app, ["records", "fetch-sources"])
    assert out.exit_code == 0, out.output
    assert not [u for u in asked if "pdg" in u]
    assert f"{PDG}: not an arXiv paper (Particle Data Group 2024" in out.output and "pdg-2024-ew.pdf by hand" in out.output
    assert "cms-1808.03684-4mu: not fetched (ConnectionError" in out.output
    assert (tmp_path / review.SOURCES / "2112.08860.pdf").exists()                   # a record after the failure


def test_showing_the_pdg_record_names_its_review():
    from adroit.orchestrator import cli
    out = CliRunner().invoke(cli.app, ["records", "show", PDG])
    assert "compare with: Particle Data Group 2024, Review 10" in out.output and "arXiv:pdg" not in out.output
