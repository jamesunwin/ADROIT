"""DM9: references found in text and confirmed before a report carries them (no network)."""

from __future__ import annotations

import pytest

from adroit.retrieval import references as refs

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1510.02110v2</id>
    <published>2015-10-07T20:00:01Z</published>
    <title>Implications of unitarity and gauge invariance for
      simplified dark matter models</title>
    <author><name>Felix Kahlhoefer</name></author>
    <author><name>Kai Schmidt-Hoberg</name></author>
  </entry>
  <entry>
    <id>http://arxiv.org/api/errors#incorrect_id_format_for_9999.99999</id>
    <title>Error</title>
  </entry>
</feed>"""
TEXT = ("Unitarity bounds the mass (arXiv:1510.02110). See also 10.1007/JHEP02(2016)016 and "
        "arXiv:1508.05327v2, hep-ph/0601001, 10.48550/arXiv.2606.11157 and the invented 9999.99999.")


def fake(known: dict[str, refs.Reference]):
    calls = []

    def resolver(asked: list[refs.Reference]) -> dict[str, refs.Reference]:
        calls.append([r.id for r in asked])
        return {r.id: known[r.id] for r in asked if r.id in known}
    return resolver, calls


def confirmed(i: str, title: str, kind: str = "arxiv") -> refs.Reference:
    return refs.Reference(kind=kind, id=i, title=title, verified=True)


def test_identifiers_are_found_in_text() -> None:
    found = refs.find(TEXT)
    assert [(r.kind, r.id) for r in found] == [
        ("arxiv", "1510.02110"), ("doi", "10.1007/JHEP02(2016)016"), ("arxiv", "1508.05327"),
        ("arxiv", "hep-ph/0601001"), ("arxiv", "2606.11157"), ("arxiv", "9999.99999")]


def test_the_arxiv_api_response_is_read() -> None:
    out = refs.parse_arxiv(ATOM, ["1510.02110", "9999.99999"])
    assert set(out) == {"1510.02110"}
    paper = out["1510.02110"]
    assert paper.title.startswith("Implications of unitarity") and paper.year == 2015 and paper.verified
    assert paper.authors == ["Felix Kahlhoefer", "Kai Schmidt-Hoberg"]


def test_unconfirmed_references_are_removed(tmp_path) -> None:
    resolver, calls = fake({"1510.02110": confirmed("1510.02110", "Implications of unitarity and gauge invariance")})
    cache = refs.ReferenceCache(tmp_path / "refs.json")
    checked = refs.verify(refs.find(TEXT), resolver, cache)
    assert [r.id for r in checked if r.verified] == ["1510.02110"]
    assert all(r.note == "not found" for r in checked if not r.verified)
    clean = refs.scrub(TEXT, checked)
    assert "1510.02110" in clean and "9999.99999" not in clean and "1508.05327" not in clean
    assert clean.count(refs.REMOVED) == 5
    again = refs.verify(refs.find("arXiv:1510.02110"), resolver, refs.ReferenceCache(tmp_path / "refs.json"))
    assert again[0].verified and len(calls) == 1              # the cache answered


def test_a_real_identifier_with_the_wrong_title_is_not_confirmed() -> None:
    resolver, _ = fake({"1510.02110": confirmed("1510.02110", "Implications of unitarity and gauge invariance")})
    wrong = refs.verify([refs.Reference(kind="arxiv", id="1510.02110")], resolver,
                        claimed_titles={"1510.02110": "Neutrino masses from extra dimensions"})
    assert not wrong[0].verified and "not this paper's" in wrong[0].note
    right = refs.verify([refs.Reference(kind="arxiv", id="1510.02110")], resolver,
                        claimed_titles={"1510.02110": "implications of unitarity and gauge invariance"})
    assert right[0].verified


# arXiv's titles and the abstracts' relevant sentences, as its API returned them on 2026-10-16
PAPERS = {
    "1304.4279": ("Silicon Detector Dark Matter Results from the Final Exposure of CDMS II",
                  "We report results of a search for Weakly Interacting Massive Particles (WIMPS) with the silicon "
                  "detectors of the CDMS II experiment."),
    "1904.00498": ("First results from the CRESST-III low-mass dark matter program",
                   "With the current stage, CRESST-III, we focus on a low energy threshold."),
    "1509.02448": ("WIMP-Search Results from the Second CDMSlite Run",
                   "The CDMS low ionization threshold experiment (CDMSlite) uses cryogenic germanium detectors operated "
                   "at a relatively high bias voltage to amplify the phonon signal in the search for weakly "
                   "interacting massive particles (WIMPs). New parameter space is excluded for WIMP masses between "
                   "1.6 and 5.5 GeV."),
    "1902.04031": ("Dark Matter Search Results from the Complete Exposure of the PICO-60 C$_3$F$_8$ Bubble Chamber",
                   "Final results are reported from operation of the PICO-60 C$_3$F$_8$ dark matter detector."),
    "1702.07666": ("Dark Matter Search Results from the PICO-60 C$_3$F$_8$ Bubble Chamber",
                   "New results are reported from the operation of the PICO-60 dark matter detector, a bubble chamber "
                   "filled with 52 kg of C$_3$F$_8$ located in the SNOLAB underground laboratory. As in previous PICO "
                   "bubble chambers, PICO-60 C$_3$F$_8$ exhibits excellent electron recoil and alpha decay rejection"),
    "0912.3592": ("Results from the Final Exposure of the CDMS II Experiment",
                  "We report results from a blind analysis of the final data taken with the Cryogenic Dark Matter "
                  "Search experiment (CDMS II). These data set an upper limit on the Weakly Interacting Massive "
                  "Particle (WIMP)-nucleon elastic-scattering spin-independent cross-section."),
}


YEARS = {"1304.4279": 2013, "1904.00498": 2019, "1509.02448": 2015, "1902.04031": 2019, "1702.07666": 2017,
         "0912.3592": 2009}


def _paper(arxiv: str) -> refs.Reference:
    title, abstract = PAPERS[arxiv]
    return refs.Reference(kind="arxiv", id=arxiv, title=title, abstract=abstract, verified=True, year=YEARS[arxiv])


PICO_2017 = "Dark Matter Search Results from the PICO-60 C$_3$F$_8$ Bubble Chamber"


@pytest.mark.parametrize("arxiv,claimed,how", [
    # the papers' own titles identify them, TeX and case aside
    ("1702.07666", PICO_2017, "title"),
    ("1702.07666", "dark matter search results from the PICO-60 C3F8 bubble chamber", "title"),
    # a contradiction is found before any match of words (the external audit's A08: the 2017 title with "(2019)")
    ("1702.07666", PICO_2017 + " (2019)", "contradicted"),
    ("1702.07666", "PICO-60 C3F8 2019 complete exposure", "contradicted"),
    ("1702.07666", "PICO-60 C3F8, arXiv:1902.04031", "contradicted"),
    # a description fits but does not identify: another paper of the same experiment fits it too
    ("1702.07666", "PICO-60 C3F8 bubble chamber", "description"),
    ("1702.07666", "PICO-60", "description"),
    ("1902.04031", PICO_2017, "description"),                     # the 2017 title is 82% of the 2019 one's words
    ("1902.04031", "PICO-60 C3F8 2019 complete exposure", "description"),
    ("1304.4279", "CDMS II Si (2013) silicon WIMP-search result", "description"),
    ("1904.00498", "CRESST-III 2019 first results", "description"),
    ("1509.02448", "CDMSlite Run 2 low-mass WIMP search", "description"),
    # neither: a fragment, a related paper's description, a generic phrase
    ("1702.07666", "Search Results", ""),
    ("0912.3592", "CDMS II Si (2013) silicon WIMP-search result", "contradicted"),   # 2013 against 2009
    ("0912.3592", "CDMS II Si silicon WIMP-search result", ""),                    # 5 of 7 words: does not fit
    ("1902.04031", "CDMS II Si silicon WIMP-search result", ""),
    ("1904.00498", "first results of a low-mass dark matter program", ""),
])
def test_how_a_citation_identifies_a_paper(arxiv, claimed, how) -> None:
    """The external audit's A08 (2026-10-16): only a paper's own title identifies it, and nothing the citation states
    may contradict it. G12's L8a descriptions fit their papers, which exist, but are not confirmed."""
    assert refs.identify(claimed, _paper(arxiv))[0] == how


def test_tex_and_unicode_spell_a_title_alike() -> None:
    """arXiv titles use TeX and citations often Unicode: the live discovery pilot (2026-10-18) dropped CMS's
    disappearing-track search (arXiv:2004.05153, its title as arXiv gave it) because "√s" was not "$\\sqrt{s}$".
    A longer title of the same experiment is still not the cited one."""
    cms = "Search for disappearing tracks in proton-proton collisions at $\\sqrt{s} =$ 13 TeV"
    assert refs.same_title("Search for disappearing tracks in proton-proton collisions at √s = 13 TeV", cms)
    assert refs.same_title("Search for disappearing tracks in proton-proton collisions at sqrt(s) = 13 TeV", cms)
    assert not refs.same_title("Search for disappearing tracks in proton-proton collisions at √s = 13 TeV",
                               "Search for disappearing tracks as a signature of new long-lived particles in "
                               "proton-proton collisions at $\\sqrt{s} =$ 13 TeV")
    assert refs.same_title("Results from a One Tonne×Year Exposure", "Results from a One Tonne$\\times$Year Exposure")
    assert refs.same_title("A search for γ-ray lines towards dwarf galaxies",
                           "A search for $\\gamma$-ray lines towards dwarf galaxies")


def test_only_an_identified_citation_is_verified() -> None:
    resolver, _ = fake({i: _paper(i) for i in PAPERS})
    def verified(arxiv, claimed):
        return refs.verify([refs.Reference(kind="arxiv", id=arxiv)], resolver, claimed_titles={arxiv: claimed})[0]
    assert verified("1702.07666", PICO_2017).verified
    for claimed in (PICO_2017 + " (2019)", "PICO-60 C3F8 bubble chamber", "Search Results"):
        checked = verified("1702.07666", claimed)
        assert not checked.verified and checked.note
    assert "fits this paper but is not its title" in verified("1702.07666", "PICO-60").note


def test_the_arxiv_abstract_is_kept_for_the_check() -> None:
    atom = ATOM.replace("<author><name>Felix", "<summary>We study unitarity.\n  Bounds follow.</summary>"
                        "<author><name>Felix", 1)
    assert refs.parse_arxiv(atom, ["1510.02110"])["1510.02110"].abstract == "We study unitarity. Bounds follow."


def test_no_network_means_nothing_is_confirmed() -> None:
    def offline(asked):
        raise ConnectionError("no network")
    checked = refs.verify(refs.find("arXiv:1510.02110"), offline)
    assert not checked[0].verified and checked[0].note == "not checked: ConnectionError"


@pytest.mark.live
def test_the_real_services_confirm_a_known_paper_and_reject_an_invented_one() -> None:
    checked = refs.verify(refs.find("arXiv:1510.02110 and arXiv:2612.99999"), refs.network_resolver)
    assert checked[0].verified and "unitarity" in checked[0].title.lower()
    assert not checked[1].verified


def test_agent_text_keeps_only_confirmed_identifiers_and_no_author_year_citations() -> None:
    ok = confirmed("1510.02110", "Implications of unitarity")
    text = "As arXiv:1510.02110 shows, and arXiv:9999.12345 and Smith et al. (2019) claim; DEAP-3600 (2019) agrees."
    clean = refs.clean(text, [ok])
    assert "1510.02110" in clean and "9999.12345" not in clean and "Smith" not in clean
    assert "DEAP-3600 (2019)" in clean                      # a module's name is not a citation
    assert refs.clean("see arXiv:1510.02110", []) == f"see {refs.REMOVED}"


# The auditor's LT16-01 (2026-11-16): each citation form enumerated here, apart from the recognizer, with the identifier it
# names; an arXiv or DOI link had passed both the cleaner and the gate's measure, so the gate said PASS over it.
UNCONFIRMED = {
    "arxiv_abs": ("[supporting analysis](https://arxiv.org/abs/9999.99999)", "9999.99999"),
    "arxiv_abs_version": ("[supporting analysis](https://arxiv.org/abs/9999.99999v3)", "9999.99999"),
    "arxiv_pdf": ("[supporting analysis](https://arxiv.org/pdf/9999.99999)", "9999.99999"),
    "arxiv_pdf_file": ("[supporting analysis](https://arxiv.org/pdf/9999.99999v1.pdf)", "9999.99999"),
    "old_arxiv": ("[supporting analysis](https://arxiv.org/abs/hep-ph/9999999)", "hep-ph/9999999"),
    "doi_url": ("[supporting analysis](https://doi.org/10.9999/nonexistent-audit-paper)",
                "10.9999/nonexistent-audit-paper"),
    "dx_doi_url": ("[supporting analysis](http://dx.doi.org/10.9999/nonexistent-audit-paper)",
                   "10.9999/nonexistent-audit-paper"),
    "arxiv_doi_url": ("[supporting analysis](https://doi.org/10.48550/arXiv.9999.99999)", "9999.99999"),
    "bare_url": ("https://arxiv.org/abs/9999.99999v2", "9999.99999"),
    "bare_arxiv": ("arXiv:9999.99999", "9999.99999"),
    "bare_doi": ("10.9999/nonexistent-audit-paper", "10.9999/nonexistent-audit-paper"),
}


def _gate():
    import runpy
    from pathlib import Path
    return runpy.run_path(str(Path(__file__).resolve().parents[2] / "docs" / "dm9" / "gate.py"),
                          run_name="offline_gate_import")


@pytest.mark.parametrize("name", list(UNCONFIRMED))
def test_an_unconfirmed_citation_in_any_form_is_withheld_and_the_gate_fails_if_one_is_left(name) -> None:
    from adroit.agents.audit import AuditReport
    from adroit.orchestrator.agents import AgentResult, report
    from adroit.orchestrator.assumptions import Inventory
    citation, identifier = UNCONFIRMED[name]
    calls = []

    def resolver(items):
        calls.append([r.id for r in items])
        return {}
    out = AgentResult(subject="fixture", inventory=Inventory(subject="fixture"),
                      audit=AuditReport(additional=["The assumption is supported by " + citation + "."]))
    body = report(out)                                     # the real DM9 report, its confirmed set empty
    assert identifier not in body and refs.REMOVED in body
    if citation.startswith("["):
        assert "supporting analysis" not in body           # the link withheld whole, its label with it
    assert refs.unverified_in(body, resolver=resolver) == []
    gate = _gate()
    left = out.model_copy(update={"report_unverified": refs.unverified_in(body + "\n" + citation, resolver=resolver)})
    assert identifier in left.report_unverified and calls[-1] == [identifier]   # counted, and sent to be checked
    assert " FAIL " in gate["line"](gate["row"]("a link left in", left))


def test_a_confirmed_link_stays_usable_beside_an_unconfirmed_one() -> None:
    confirmed = [refs.Reference(kind="arxiv", id="1510.02110", verified=True),
                 refs.Reference(kind="doi", id="10.1007/JHEP02(2016)016", verified=True)]
    text = ("[unitarity](https://arxiv.org/abs/1510.02110v2), https://arxiv.org/pdf/1510.02110 and "
            "[invented](https://arxiv.org/abs/9999.99999)")
    cleaned = refs.clean(text, confirmed)
    assert cleaned == ("[unitarity](https://arxiv.org/abs/1510.02110v2), https://arxiv.org/pdf/1510.02110 and "
                       + refs.REMOVED)
    assert [r.id for r in refs.find(text)] == ["1510.02110", "9999.99999"]
