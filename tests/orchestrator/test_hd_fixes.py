"""The auditor's recheck of the HC repairs, repaired (the independent audit of 2026-11-12 (hc recheck); the record
the HD repair record of 2026-11-12):

- HD-01: a point whose record of the halo data files it read is not whole (a file not named, recorded missing, or
  named by what is not a sha256; or only an unrelated name) is not certified; a decided certificate naming a halo
  data file by no identity reads stale.
- HD-02: each completion offer's files are its own (named by the SHA-256 of the request it saves, never written
  over), its candidate's study folder its own, and its command runs the request offered or refuses.
- HD-03: a promotion refuses its children's profile's private inputs at the halo their run states, before anything.
- HD-04: the HC-03 tests keep their toy searches throughout (``test_hc_fixes.py``), so their negative controls fail at
  the provider, not at a loader.
- HD-05: a certificate made under the earlier halo binding (the policy before ``consistency-hd-2026-11-12``) reads
  stale, the old writer's misbound crossing among them.

Offline: toy searches with real recoil rates (``test_halo_phase1``'s), the halo data files copied to a folder of the
test's (``test_hb_fixes``'s), the model builder a ``FakeLLMClient``, the final calculation of a completion captured."""
from __future__ import annotations

import hashlib
import json
import shlex
from pathlib import Path

import pytest
from typer.testing import CliRunner

from adroit.agents.ideas import CouplingValue, ModelProposal, ModelProposals, ModelValues, ValueProposals
from adroit.agents.llm import FakeLLMClient
from adroit.core import halo_choice
from adroit.core.certificate import POLICY, Bound, Certificate, assessment, reading
from adroit.orchestrator import cli, promote, runs, signal, single_idea
from adroit.parameter_space import certification
from adroit.parameter_space.classes import Point
from adroit.parameter_space.scan import ScanResult
from tests.orchestrator.test_completions import CHI, partner
from tests.orchestrator.test_halo_phase1 import _request, toys  # noqa: F401 (a fixture)
from tests.orchestrator.test_hb_fixes import files, plus  # noqa: F401 (a fixture)
from tests.orchestrator.test_hc_fixes import Provider, _calculated, _now, _parent, _saved, band  # noqa: F401

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


# --- HD-01: a record of the halo data that is not whole certifies nothing ---------------------------------------------

NOT_WHOLE = {
    "one file not named": lambda d: {k: v for k, v in d.items() if k != "local densities"},
    "one file recorded missing": lambda d: {**d, "local densities": ""},
    "only an unrelated name": lambda d: {"unrelated": "x"},
    "a malformed identity": lambda d: {**d, "local densities": "not-a-sha256"},
    "an identity cut short": lambda d: {**d, "count-ratio declaration": d["count-ratio declaration"][:12]},
}


@pytest.mark.parametrize("case", list(NOT_WHOLE))
def test_a_point_whose_halo_data_record_is_not_whole_is_not_certified(case, files, band):  # noqa: F811
    """The auditor's ``claim_edges``: the point calculated, its record damaged, the result saved and read back; by both
    public verdict entry points its exclusion is kept as computed, and waits. At ``ee61f82`` each read certified."""
    files.write(0.4)
    row = _calculated(Point(m_chi=100, m_med=1000))
    damaged = row.model_copy(update={"halo": row.halo.model_copy(update={"data": NOT_WHOLE[case](row.halo.data)})})
    saved = ScanResult.model_validate(json.loads(_saved(damaged).model_dump_json()))
    for claim in band(saved):
        assert not claim.certificate.decided and claim.status == "pending"
        assert claim.certificate.computed_status == "excluded"
        check = claim.certificate.check("halo_data")
        assert check.state == "unknown" and "is not whole" in check.reason and "run it again" in check.reason
        assert _now(claim.certificate).startswith("not certified")


def test_a_whole_record_is_certified_as_before(files, band):  # noqa: F811
    files.write(0.4)
    saved = ScanResult.model_validate(json.loads(_saved(_calculated(Point(m_chi=100, m_med=1000))).model_dump_json()))
    assert all(_now(claim.certificate).startswith("certified") for claim in band(saved))


def test_the_check_names_what_is_missing(files):  # noqa: F811
    row = _calculated(Point(m_chi=100, m_med=1000))
    data = {**row.halo.data, "local densities": ""}
    data.pop("count-ratio declaration")
    data["count-ratio validation"] = "x" * 64
    [check] = certification.halo_data_check(row.model_copy(update={"halo": row.halo.model_copy(update={"data": data})}))
    assert ("local densities: missing when the point read it" in check.reason
            and "count-ratio declaration: not recorded" in check.reason
            and "count-ratio validation: not a sha256" in check.reason)


def test_a_decided_certificate_naming_a_halo_file_by_no_identity_reads_stale():
    names = dict.fromkeys(halo_choice.HALO_DATA, "")
    certificate = Certificate(claim_kind="k", scope="s", bound=Bound(halo_data=names), policy=POLICY)
    assert certificate.decided
    assert reading(certificate, Bound(halo_data=names)) == "stale: " + "; ".join(
        f"the halo data file ({name}) it was certified with is not recorded" for name in halo_choice.HALO_DATA)


# --- HD-05: a certificate made under the earlier halo binding reads stale ---------------------------------------------

def _legacy():
    from adroit.parameter_space.verdict import Crossing
    found = json.loads((FIXTURES / "hd05_legacy_crossing.json").read_text())
    return found, Crossing.model_validate(found["crossing"])


def test_the_old_writers_misbound_crossing_no_longer_reads_certified():
    """The auditor's ``legacy_certificate_make``: 6bc3565's public verdict writer, its comparison (1.89) read from density
    file A, its certificate bound to B. At ``ee61f82``, with B current, it read certified."""
    found, crossing = _legacy()
    assert crossing.certificate.bound.halo_data["local densities"] == found["bound_B"] != \
        found["evaluated_A"]["local densities"]
    now = reading(crossing.certificate, certification.current_bound(crossing.certificate))
    assert now.startswith(f"stale: certified under policy consistency-cv-2026-10-28, not the current {POLICY}")
    assert crossing.status == "excluded" and crossing.r_combined == pytest.approx(1.890625)    # kept as saved


def test_an_earlier_halo_binding_reads_stale_on_its_own_and_its_headline_with_it():
    """The old certificate bound to the files as they are now, so that only its policy differs: stale; the same
    certificate under the current policy reads certified (the control)."""
    _, crossing = _legacy()
    now = certification.current_bound(crossing.certificate)
    old = crossing.certificate.model_copy(update={"bound": crossing.certificate.bound.model_copy(
        update={"halo_data": now.halo_data})})
    assert reading(old, now) == f"stale: certified under policy consistency-cv-2026-10-28, not the current {POLICY}"
    assert assessment([old], [now]) == "stale"
    assert reading(old.model_copy(update={"policy": POLICY}), now) == "certified"


# --- HD-02: a completion offer runs the request it offered ------------------------------------------------------------

def _offers(root: Path, monkeypatch):
    """The auditor's ``offers_proposals``: two candidates of one card, the model builder proposing the same model for
    each (simulated), through the real proposal pipeline, writer and offers."""
    proposal = ModelProposal(name="DownPartner", fields=[CHI, partner(-1 / 3, "3")], rationale="SIMULATED")
    values = ValueProposals(models=[ModelValues(model=1, couplings=[CouplingValue(name="y_dR_chi_phi_1", value=0.5)])])
    llm = FakeLLMClient([ModelProposals(proposals=[proposal]), values, ModelProposals(proposals=[proposal]), values])
    request = signal.SignalRequest(experiment="CDMS II Si (2013)", null_modules=[], halo=halo_choice.fixed())
    first = signal.Candidate(label="O4s@10", card_id="O4", isospin="s", mass_gev=10)
    second = first.model_copy(update={"label": "O4s@100", "mass_gev": 100})
    monkeypatch.setattr(promote, "_reproduces", lambda s, c: True)
    from adroit.parameter_space.classify import Unsupported
    # the offers' machinery under test: since 2026-11-21 a proposal is offered only when an engine computes it (here
    # the generic route), so the library's refusal that leads to its flavour completions is stood in for
    def refused(spec, generic_route=True):
        raise Unsupported("the t-channel portal needs one explicit SM flavour")
    monkeypatch.setattr(promote, "classify", refused)
    a = promote._proposals(root, first, llm, 1, request, {"span": 2, "masses": 3})
    b = promote._proposals(root, second, llm, 1, request, {"span": 2, "masses": 3})
    return a, b


def test_each_candidates_offer_runs_its_own_request(tmp_path, monkeypatch):
    """At ``ee61f82`` both candidates' offers shared one folder and one file: the 10 GeV offer's command studied
    50–200 GeV."""
    a, b = _offers(tmp_path, monkeypatch)
    assert a[0] != b[0] and a[4] and b[4]                       # each candidate's own study of its completions
    offers = [*a[4], *b[4]]
    assert len({o.request for o in offers}) == len(offers)      # each offer's own file
    seen = []
    monkeypatch.setattr(runs, "single_idea", lambda r, *x, **k: (seen.append(r) or tmp_path, "SIMULATED"))
    for o in offers:
        saved = json.loads(Path(o.request).read_text())
        assert hashlib.sha256(Path(o.request).read_bytes()).hexdigest() == o.request_sha256
        assert CliRunner().invoke(cli.app, shlex.split(o.command)[1:]).exit_code == 0
        assert seen[-1].model_dump(mode="json") == saved          # every field its own offer's
        assert seen[-1].masses_gev[len(seen[-1].masses_gev) // 2] == pytest.approx(10 if o.label == "O4s@10" else 100)


def test_an_offer_is_never_written_over(tmp_path):
    path = tmp_path / "choices" / "x.request.json"
    promote._written_once(path, b"A")
    promote._written_once(path, b"A")                              # the same offer again: nothing changes
    with pytest.raises(ValueError, match="holds another offer"):
        promote._written_once(path, b"B")
    assert path.read_bytes() == b"A"


def test_an_offered_command_refuses_a_request_changed_since_and_a_bare_file_runs_as_its_own(tmp_path, monkeypatch):
    a, _ = _offers(tmp_path, monkeypatch)
    offer = a[4][0]
    seen = []
    monkeypatch.setattr(runs, "single_idea", lambda r, *x, **k: (seen.append(r) or tmp_path, "SIMULATED"))
    edited = json.loads(Path(offer.request).read_text())
    edited["toys"] = 7
    Path(offer.request).write_text(json.dumps(edited))
    refused = CliRunner().invoke(cli.app, shlex.split(offer.command)[1:])
    words = " ".join(refused.output.replace("│", " ").split())
    assert refused.exit_code == 2 and "is not the request offered" in words and seen == []
    ran = CliRunner().invoke(cli.app, ["single-idea", "--request", offer.request])        # by hand: its own request
    assert ran.exit_code == 0 and seen[-1].toys == 7
    alone = CliRunner().invoke(cli.app, ["single-idea", "--request-sha256", offer.request_sha256])
    assert alone.exit_code == 2 and "give it with --request" in " ".join(alone.output.replace("│", " ").split())


# --- HD-03: the children's profile's private inputs refused before anything -------------------------------------------

def _profile_parent(halo, monkeypatch):
    """A parent whose request names a profile holding a private SI curve (a synthetic loader fixture)."""
    from types import SimpleNamespace
    from adroit.library import experimental_profiles
    from adroit.constraints import experimental_review
    curve = SimpleNamespace(name="private-si:test", contract=SimpleNamespace(adapter="si_isoscalar_curve"))
    monkeypatch.setattr(experimental_profiles, "load", lambda ref: SimpleNamespace(
        limits=["private-si:test"], null_modules=[]))
    monkeypatch.setattr(experimental_review, "load_bound", lambda ref: curve)
    return halo


@pytest.mark.parametrize("halo", ["a fixed benchmark", "published: the children over the region"])
def test_a_promotion_refuses_its_childrens_private_curve_before_any_request(halo, isovector_toy, toys, tmp_path,  # noqa: F811
                                                                            monkeypatch):
    """The auditor's ``promotion_profile``: at ``ee61f82`` the builder was reached (one simulated send), and the
    promotion's record written, before the child's fit refused the curve."""
    from adroit.parameter_space import halo_region
    monkeypatch.setattr(halo_region, "default", lambda: "preset")
    value = halo_choice.fixed() if halo == "a fixed benchmark" else None
    _profile_parent(value, monkeypatch)
    parent = isovector_toy.model_copy(update={"request": isovector_toy.request.model_copy(
        update={"halo": value, "experimental_profile": "profile:test"})})
    folder = _parent(tmp_path / "run", parent)
    client = Provider()
    with pytest.raises(ValueError, match="private direct-detection input has no halo variation"):
        promote.promote(folder, [parent.request.candidates[0].label], llm=client)
    assert client.sent == 0 and sorted(p.name for p in folder.iterdir()) == ["result.json"]


def test_the_childs_fit_and_the_promotion_refuse_with_one_check(monkeypatch):
    """One refusal for both: the child's fit (``_fit_options``) and the promotion (``refuse_profile``) ask
    ``_refuse_private``."""
    seen = []
    monkeypatch.setattr(single_idea, "_refuse_private", lambda *a: seen.append(a[0]))
    monkeypatch.setattr(single_idea, "_private", lambda profile: {"private_limits": [], "private_searches": []})
    monkeypatch.setattr("adroit.parameter_space.private_limits.check_applicability", lambda *a: None)
    from types import SimpleNamespace
    single_idea.refuse_profile(plus(), SimpleNamespace())
    single_idea._fit_options(SimpleNamespace(spec=SimpleNamespace(physical_fit=None), physical_fit_settings=None,
                                             halo=plus()), SimpleNamespace())
    assert seen == [plus(), plus()]


@pytest.fixture
def isovector_toy(toys):  # noqa: F811
    """A Track 2 result at the SHM benchmark whose one candidate is isovector (only the model builder completes it)."""
    request = _request(halo_choice.fixed())
    candidate = request.candidates[0].model_copy(update={"isospin": "v"})
    return signal.run(request.model_copy(update={"candidates": [candidate]}))
