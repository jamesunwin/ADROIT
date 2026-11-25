"""The repair round after cycle 7's pin (2026-11-17; the AL7 repair record of 2026-11-17): the deferred highs of the auditor's
cycle 5, a non-physics audit's README finding, and the owner's naming of simplified models. The workbench's repairs
(NP17-01 to NP17-03) and AL5-03's hand-over are tested in ``tests/ui/test_al7_pages.py``.

- AL5-02: a halo sample's combined ratio carries its own channel's confidence level and sidedness.
- AL5-04: a link is read for what it points to, its target decoded (a journal's URL, an encoded identifier), and a DOI
  with parentheses is kept whole.
- NP17-04: the README offers no withdrawn page or hidden command.
- A model built from part of a larger theory is named "(simplified model)".

Offline: fixtures and scripted language models; no network, no key, no provider call.
"""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from adroit.agents.llm import FakeLLMClient
from adroit.retrieval import references as refs

ROOT = Path(__file__).resolve().parents[2]


# --- AL5-02 ----------------------------------------------------------------------------------------------------

def _mixed_channels():
    """The auditor's fixture: a one-sided SI limit with ratio 0.9 (combinable) beside a two-sided SD-neutron band
    (0.3, 2) that decides (it straddles, so direct detection is pending)."""
    from adroit.parameter_space import dd_channels as dc, limits
    one = limits.StatisticalLimit(value=1e-46, confidence_level=.95, source="CDMSlite Run 2", sidedness="one-sided",
                                  construction="synthetic")
    two = limits.StatisticalLimit(value=1e-40, confidence_level=.95, source="XENONnT SR0+SR1", sidedness="two-sided",
                                  construction="synthetic")
    return dc.Outcome(channels=[dc.ChannelOutcome(kind="SI", sigma_cm2=.9e-46, ratio=.9, limit=one),
                                dc.ChannelOutcome(kind="SD-neutron", sigma_cm2=2e-40, ratio=2., ratio_band=(.3, 2.),
                                                  limit=two)],
                      excluded=None, pending=["SD band straddles"])


def _halo_dd(found):
    from adroit.parameter_space import dd_channels as dc, halo_evaluation, halo_limits
    with patch.object(dc, "compare", lambda *a, **k: found):
        return halo_evaluation._dd([dc.Channel(kind="SI", sigma_cm2=.9e-46)], 100., halo_limits.State(233., 528., .4))


def test_a_halo_samples_ratio_keeps_its_own_channels_construction() -> None:
    found = _mixed_channels()
    halo, reasons = _halo_dd(found)
    assert found.decisive.kind == "SD-neutron" and found.combined_channel.kind == "SI"
    assert halo.ratio == pytest.approx(.9)
    assert (halo.sidedness, halo.confidence_level) == ("one-sided", .95)          # it had been the SD band's
    assert reasons == ["SD band straddles"]


def test_a_halo_samples_verdict_with_mixed_channels_stays_pending() -> None:
    """The verdict, not only the fields: with the band's two-sided construction the combination had made the point
    excluded (r = 1.07) and dropped its pending reason."""
    from adroit.parameter_space import likelihood
    from adroit.parameter_space.halo_region import HaloPointSample
    from adroit.parameter_space.verdict import classify
    from tests.parameter_space.test_halo_region import _point
    halo, reasons = _halo_dd(_mixed_channels())
    sample = HaloPointSample(v0_km_s=233., v_esc_km_s=528., rho_gev_cm3=.4, where="interior",
                             outcomes={"direct detection": halo}, pending=reasons)
    point = _point([sample], excluded={"direct detection": None}, pending=reasons).model_copy(update={
        "ratio_confidence_levels": {"direct detection": .95}, "ratio_sidedness": {"direct detection": "one-sided"}})
    verdict = classify(None, point, likelihood.LikelihoodSettings())
    assert verdict.status == "pending" and not verdict.excluded_by
    assert any("SD band straddles" in p for p in verdict.pending)


def test_the_centre_and_a_halo_sample_carry_the_same_construction() -> None:
    from adroit.parameter_space import dd_channels as dc, library, limits, scan
    found = _mixed_channels()
    entry = library.entry("dmwg_A1")
    with patch.object(dc, "compare", lambda *a, **k: found), patch.object(limits, "envelope", lambda *a: 1.), \
            patch.object(limits, "setter", lambda *a: "fixture"):
        centre = scan.direct_detection(entry.model_class, entry.point)
    halo, _ = _halo_dd(found)
    assert (centre.statistic.sidedness, centre.statistic.confidence_level) == (halo.sidedness, halo.confidence_level)


# --- AL5-04 ----------------------------------------------------------------------------------------------------

JOURNAL = "https://journals.aps.org/prd/abstract/10.1103/PhysRevD.999.999999"
ENCODED_ARXIV = "https://arxiv.org/abs/9999%2E99999"
ENCODED_DOI = "https://doi.org/10.1103%2FPhysRevD.999.999999"
PARENTHESES = "10.1016/S0370-2693(99)99999-9"


@pytest.mark.parametrize("text,identifier", [
    (JOURNAL, "10.1103/PhysRevD.999.999999"),
    (ENCODED_ARXIV, "9999.99999"),
    (ENCODED_DOI, "10.1103/PhysRevD.999.999999"),
    (f"[the paper]({JOURNAL})", "10.1103/PhysRevD.999.999999"),
    ("<https://arxiv.org/abs/9999%252E99999>", "9999.99999"),
    ('<a href="https://doi.org/10.1103%2FPhysRevD.9.9">the paper</a>', "10.1103/PhysRevD.9.9"),
])
def test_a_link_is_read_for_what_it_points_to_and_an_unconfirmed_one_is_removed_whole(text, identifier) -> None:
    report = f"As shown in {text}, the bound holds."
    assert [r.id for r in refs.find(report)] == [identifier]
    cleaned = refs.clean(report, [])
    assert cleaned == f"As shown in {refs.REMOVED}, the bound holds."
    assert refs.unverified_in(report, resolver=lambda asked: {}) == [identifier]      # the gate's measure fails it
    assert refs.unverified_in(cleaned, resolver=lambda asked: {}) == []


def test_a_confirmed_paper_linked_or_encoded_is_kept() -> None:
    known = refs.Reference(kind="doi", id="10.1103/PhysRevD.999.999999", verified=True)
    for text in (JOURNAL, ENCODED_DOI, f"see {ENCODED_DOI}."):
        assert refs.clean(text, [known]) == text
        assert refs.unverified_in(text, resolver=lambda asked: {known.id: known}) == []


def test_a_doi_with_parentheses_is_kept_whole() -> None:
    confirmed = refs.Reference(kind="doi", id=PARENTHESES, verified=True)
    text = (f"See {PARENTHESES} and doi:{PARENTHESES}. Also https://doi.org/{PARENTHESES} and "
            f"[it](https://doi.org/{PARENTHESES}); (see 10.1103/PhysRevD.99.1).")
    assert [r.id for r in refs.find(text)] == [PARENTHESES, "10.1103/PhysRevD.99.1"]
    assert refs.clean(text, [confirmed]) == text.replace("10.1103/PhysRevD.99.1", refs.REMOVED)


def test_a_sentences_full_stop_is_not_a_dois() -> None:
    assert [r.id for r in refs.find("as in 10.1103/PhysRevD.99.1.")] == ["10.1103/PhysRevD.99.1"]


# --- NP17-04 ---------------------------------------------------------------------------------------------------

def test_the_readme_offers_no_withdrawn_page_or_hidden_command() -> None:
    """The non-physics audit's NP17-04: the README had offered the withdrawn native-fit page (a 404) and its command.
    Every ``adroit <command>`` it names is one the command line lists, and every route it names is a page served."""
    from typer.main import get_command
    from adroit.orchestrator.cli import app
    text = (ROOT / "README.md").read_text()
    assert "native-fit page" not in text
    listed = {name for name, c in get_command(app).commands.items() if not c.hidden}
    named = set(re.findall(r"(?:`|uv run )adroit ([a-z][a-z0-9-]*)", text))
    assert named and named <= listed, named - listed
    served = set(re.findall(r"""@ui\.page\(["']([^"']+)""", (ROOT / "adroit/ui/app.py").read_text()))
    routes = set(re.findall(r"`(/[a-z][a-z0-9/_-]*)`", text))
    assert "/studies" in served and "/new/native" not in served
    assert routes <= served, routes - served                 # the README of 1.0.0 names pages by their menu names


# --- simplified models (the owner, 2026-11-17) ------------------------------------------------------------------

def test_a_simplified_name_says_so_once() -> None:
    from adroit.orchestrator.ideas import simplified_name
    assert simplified_name("Bino-stau coannihilation") == "Bino-stau coannihilation (simplified model)"
    assert simplified_name("Bino-stau (Simplified Model)") == "Bino-stau (Simplified Model)"
    assert simplified_name(simplified_name("x")) == "x (simplified model)"


def _service(tmp_path):
    from adroit.library.personal import Catalog
    from adroit.orchestrator.model_intake import Intake
    return Intake(Catalog(tmp_path / "library"))


def test_an_interpreted_simplified_model_is_named_and_says_what_it_leaves_out(tmp_path) -> None:
    from adroit.agents.model_intake import Interpretation
    from adroit.orchestrator.model_approval import model_identity
    from adroit.parameter_space.simplified import model
    service = _service(tmp_path)
    s = service.start(1)
    spec = model("vector", 10, 125, .001, .25).model_copy(update={"name": "Bino with a light stau"})
    fake = FakeLLMClient([Interpretation(transcription="t", spec=spec, simplified="the other superpartners")])
    d = service.step(s.session_id, "tex", "a bino and a stau of the MSSM", llm=fake)
    choice = d.choices[0]
    assert choice.spec.name == "Bino with a light stau (simplified model)"
    assert choice.simplified == "the other superpartners"
    r = service.approve(s.session_id, d.step_id, 0, confirmed=True, expected_model_hash=model_identity(choice.spec),
                        tex=choice.tex)
    assert service.catalog.load(r.reference).spec.name == "Bino with a light stau (simplified model)"


def test_a_complete_model_keeps_its_name_and_its_draft_as_before(tmp_path) -> None:
    import json
    from adroit.agents.model_intake import Interpretation
    from adroit.parameter_space.simplified import model
    service = _service(tmp_path)
    s = service.start(1)
    spec = model("vector", 10, 125, .001, .25)
    d = service.step(s.session_id, "tex", "x", llm=FakeLLMClient([Interpretation(transcription="t", spec=spec)]))
    assert d.choices[0].spec.name == spec.name and d.choices[0].simplified == ""
    stored = json.loads((service.folder(s.session_id) / "steps" / f"{d.step_id}.json").read_text())
    assert "simplified" not in stored["choices"][0]               # a draft's stored content as before
    assert service.load(s.session_id, d.step_id).choices[0].spec == spec


def test_a_proposed_simplified_model_is_named_so() -> None:
    from adroit.agents.ideas import ModelProposal, ModelProposals
    from adroit.core.model_spec import Charges, FieldRole, ModelField
    from adroit.orchestrator import ideas
    bino = ModelField(name="B1", role=FieldRole.dark_matter, spin=0.5, self_conjugate=True, dark_parity=-1,
                      mass_gev=100.0)
    stau = ModelField(name="tau1", role=FieldRole.other, spin=0, dark_parity=-1, mass_gev=110.0,
                      charges=Charges(hypercharge=-1.0, electric_charge=-1.0))
    from adroit.agents.ideas import CouplingValue, ModelValues, ValueProposals
    values = ValueProposals(models=[ModelValues(model=1, couplings=[CouplingValue(name="y_eR_B1_tau1_1", value=0.3)])])
    fake = FakeLLMClient([ModelProposals(proposals=[ModelProposal(name="Bino and stau", fields=[bino, stau],
                                                                  simplified="the other superpartners")]), values])
    result = ideas.run(ideas.IdeaRequest(text="bino dark matter with a stau"), fake)
    m = result.models[0]
    assert m.spec.name == "Bino and stau (simplified model)" and m.simplified == "the other superpartners"
    assert yaml.safe_load(yaml.safe_dump(m.model_dump(mode="json")))["simplified"] == "the other superpartners"
