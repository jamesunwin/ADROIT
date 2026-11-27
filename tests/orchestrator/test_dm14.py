"""DM14: users' models in Path 2, the single-idea study, studies and promotion (offline, coarse)."""

import json
from pathlib import Path

import numpy as np
import pytest

from adroit.core.model_spec import ModelSpec
from adroit.experiments import registry
from adroit.orchestrator import promote, signal, single_idea, studies, user_models
from adroit.parameter_space import simplified
from adroit.parameter_space.classify import Unsupported

SI = "CDMS II Si (2013)"



def unbuildable() -> ModelSpec:
    """A model neither the library's classes nor the generic route computes: χχS with χ a hypercharged doublet is not
    gauge invariant, so G1 refuses it (since 2026-10-15 a model outside the classes is otherwise computed by the
    generic route)."""
    return ModelSpec.model_validate({"name": "not_invariant", "phase": "unbroken", "fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0,
         "charges": {"su2": 2, "hypercharge": 0.5}},
        {"name": "S", "role": "mediator", "spin": 0, "self_conjugate": True, "mass_gev": 200.0}],
        "couplings": [{"name": "y", "value": 0.3}],
        "terms": [{"fields": [{"field": "chi"}, {"field": "chi"}, {"field": "S"}], "lorentz": "scalar",
                   "coupling": "y"}]})

def majorana(spec):
    fields = [f.model_copy(update={"self_conjugate": True}) if f.name == spec.dark_matter.name else f
              for f in spec.fields]
    return spec.model_copy(update={"fields": fields})


def test_a_users_model_gives_one_candidate_per_mass():
    found = user_models.candidates(simplified.model("vector", 10, 1000), [8.6, 20.0])
    assert [c.label for c in found] == ["vector_mediator@8.6", "vector_mediator@20"]
    assert all(c.interaction is not None and not c.card_id and c.model == "vector_mediator" for c in found)


def test_a_model_outside_the_classes_needs_a_derivation():
    with pytest.raises(Unsupported, match="no derivation"):
        user_models.interaction(unbuildable(), 10.0)


def test_a_model_outside_the_classes_gets_the_generic_routes_interaction():
    """Majorana dark matter with a vector mediator, coupled through its axial current: outside the classes, computed
    from its own Lagrangian. Its vector current χ̄γχ would vanish, which G2 refuses rather than read as zero (G12)."""
    spec = majorana(simplified.model("vector", 10, 1000))
    axial = [t.model_copy(update={"lorentz": "axial"}) if spec.dark_matter.name in {o.field for o in t.fields} else t
             for t in spec.terms]
    assert user_models.interaction(spec.model_copy(update={"terms": axial}), 10.0) is not None
    with pytest.raises(Unsupported, match="no vector current"):
        user_models.interaction(spec, 10.0)


@pytest.mark.parametrize("kind, card", [("vector", "O1"), ("scalar", "O1")])   # SI: the records use Helm only
def test_a_simplified_model_has_the_shape_of_its_card(kind: str, card: str):
    module = registry.load_module(SI)
    mine = user_models.candidates(simplified.model(kind, 10, 1000), [10.0])[0]
    library = signal.Candidate(label="lib", card_id=card, isospin="s", mass_gev=10.0)
    a, b = np.array(signal._signal(module, mine).density), np.array(signal._signal(module, library).density)
    assert a / a.sum() == pytest.approx(b / b.sum(), rel=2e-3, abs=1e-12)    # nucleon form-factor terms: < 0.1%


def test_studies_record_parents_children_and_costs(tmp_path):
    parent, child = tmp_path / "p", tmp_path / "p" / "children" / "c"
    child.mkdir(parents=True)
    (parent / "report.md").write_text("r")
    studies.record(parent, "signal", "the parent")
    studies.record(child, "idea", "the child", cost_usd=0.25, parent=parent)
    assert studies.load(parent).children == [str(child.resolve())]
    assert studies.load(parent).outputs == ["report.md"]
    assert [(d, s.title) for d, s in studies.tree(tmp_path)] == [(0, "the parent"), (1, "the child")]
    assert studies.total_cost(tmp_path) == pytest.approx(0.25)


def test_the_single_idea_study_of_an_unsupported_model_is_undetermined(tmp_path):
    request = single_idea.SingleIdeaRequest(experiment=SI, spec=unbuildable(), masses_gev=[10.0], literature=False,
                                            workers=1)
    result = single_idea.run(request, tmp_path)
    assert result.level == "undetermined" and "cannot build it either" in result.unsupported
    assert "UNDETERMINED" in single_idea.report(result)


@pytest.mark.needs("diamx", "cdmslite", "solar_model")
def test_the_single_idea_study_fits_and_draws_the_band(tmp_path):
    request = single_idea.SingleIdeaRequest(experiment=SI, spec=simplified.model("vector", 10, 1000),
                                            masses_gev=[7.0, 9.0, 12.0], null_modules=[], toys=500, grid=4,
                                            literature=False, workers=1)
    result = single_idea.run(request, tmp_path)
    assert result.best and all(b.m_med and b.status for b in result.band)
    assert result.level in single_idea.LEVELS and (tmp_path / "parameter_plane.png").exists()
    text = single_idea.report(result)
    assert "## 1. The fit" in text and "## 3. The plane around the band" in text
    # the plane with the signal requirement imposed (the owner's plan of 2026-11-24): a stored assessment at every grid
    # point and crossing, the report's conclusion read from it
    plane = result.signal_plane
    assert plane is not None and len(plane.grid) == len(result.track1.scan.points)
    assert len(plane.crossings) == len(plane.joint) == len(result.track1.verdict.crossings)
    assert f"**On the plane:** {plane.summary()}." in text and plane.summary() in result.summary


@pytest.mark.needs("diamx", "cdmslite", "solar_model")
def test_promotion_writes_children_that_name_their_parent(tmp_path):
    request = signal.SignalRequest(experiment=SI, null_modules=[], toys=500, leaders=1,
                                   candidates=[signal.Candidate(label="O1s@10", card_id="O1", isospin="s",
                                                                mass_gev=10.0)])
    parent = tmp_path / "run"
    parent.mkdir()
    (parent / "result.json").write_text(signal.run(request).model_dump_json())
    out = promote.promote(parent, ["class:0"], {"toys": 300, "grid": 4, "masses": 3, "literature": False,
                                                "workers": 1})
    assert [c.model for c in out.children] == ["vector_mediator_for_O1", "scalar_mediator_for_O1"]
    child = studies.load(out.children[0].folder)
    assert child.parent == str(parent.resolve()) and studies.load(parent).children[0] == child.folder
    assert "scalar_mediator_for_O1" in promote.report(out)
    assert json.loads((parent / "result.json").read_text())["request"]["experiment"] == SI
    child_result = json.loads((Path(out.children[0].folder) / "result.json").read_text())
    parent_z = json.loads((parent / "result.json").read_text())["global_z"]
    assert "promoted from a library-wide search" in child_result["global_method"]       # release audit minor
    assert child_result["global_z"] <= parent_z + 1e-12


def test_an_isovector_card_has_no_computable_completion():
    assert simplified.completions("O1", "v") == [] and simplified.completions("O1", "s") == ["vector", "scalar"]


@pytest.mark.parametrize("candidate,why", [
    (signal.Candidate(label="O1s@1000,d=300", card_id="O1", isospin="s", mass_gev=1000.0, splitting_kev=300.0),
     "inelastic (δ = 300 keV)"),
    (signal.Candidate(label="O1v@10", card_id="O1", isospin="v", mass_gev=10.0), "isovector"),
    (signal.Candidate(label="O1s@10*", card_id="O1", isospin="s", mass_gev=10.0, values={"c1p": 2.0}), "a variant"),
])
def test_promotion_refuses_a_candidate_its_completions_would_not_reproduce(candidate, why):
    """Release audit M7: O1 at δ = 300 keV was promoted to elastic mediators under the inelastic label."""
    assert promote.completion_refusal(candidate).startswith(why)
    assert promote.models_for(None, candidate) == []
    elastic = signal.Candidate(label="O1s@10", card_id="O1", isospin="s", mass_gev=10.0)
    assert promote.completion_refusal(elastic) == "" and len(promote.models_for(None, elastic)) == 2


@pytest.mark.needs("revised_xenon")
def test_promotion_reports_built_and_dropped_class_members(tmp_path, monkeypatch):
    request = signal.SignalRequest(experiment=SI, null_modules=[], toys=200, leaders=1,
                                   candidates=[signal.Candidate(label=f"O1s@{m}", card_id="O1", isospin="s",
                                                                mass_gev=float(m)) for m in (10, 11)])
    parent = tmp_path / "run"
    parent.mkdir()
    result = signal.run(request)
    (parent / "result.json").write_text(result.model_dump_json())
    built = []
    monkeypatch.setattr(promote, "_study", lambda parent, result, c, origin, spec, options, fetch, under=None:
                        built.append(spec.name) or promote.Child(label=c.label, model=spec.name, origin=origin,
                                                                 folder=str(parent / spec.name)))
    out = promote.promote(parent, ["O1s@10", "O1s@11"], {})
    assert built == ["vector_mediator_for_O1", "scalar_mediator_for_O1"]
    assert out.undetermined["O1s@11"].startswith("its completions were already studied for O1s@10")
    # a class member whose fitted point is excluded is left out of class:N, and the promotion says so
    from adroit.core.eligibility import CandidateEligibility
    n = result.classes["O1s@10"]
    result.eligibility["O1s@10"] = CandidateEligibility(label="O1s@10", status="excluded_point")
    (parent / "result.json").write_text(result.model_dump_json())
    built.clear()
    out = promote.promote(parent, [f"class:{n}"], {})
    assert "O1s@10" in out.dropped and "excluded" in out.dropped["O1s@10"] and "Left out" in promote.report(out)


def test_a_builder_proposal_must_reproduce_the_candidates_couplings():
    """Mini audit: the model builder's proposals were studied without checking them against the candidate."""
    vector = simplified.model("vector", 10.0, 1000.0)
    o1 = lambda iso: signal.Candidate(label=f"O1{iso}@10", card_id="O1", isospin=iso, mass_gev=10.0)  # noqa: E731
    assert promote._reproduces(vector, o1("s")) and not promote._reproduces(vector, o1("v"))
    assert not promote._reproduces(vector, signal.Candidate(label="O4s@10", card_id="O4", isospin="s", mass_gev=10.0))


def test_the_builder_is_not_asked_for_an_inelastic_candidate(tmp_path, monkeypatch):
    """Mini audit: an inelastic isovector leader reached the model builder and was studied as elastic."""
    request = signal.SignalRequest(experiment=SI, null_modules=[], toys=200, leaders=1,
                                   candidates=[signal.Candidate(label="O1v@10", card_id="O1", isospin="v",
                                                                mass_gev=10.0)])
    parent = tmp_path / "run"
    parent.mkdir()
    result = signal.run(request)
    (parent / "result.json").write_text(result.model_dump_json())
    pool = promote.candidates_of(result)
    inelastic = pool["O1v@10"].model_copy(update={"splitting_kev": 300.0})
    monkeypatch.setattr(promote, "candidates_of", lambda r: {"O1v@10": inelastic})
    monkeypatch.setattr(promote, "_proposals", lambda *a, **k: (_ for _ in ()).throw(AssertionError("builder asked")))
    out = promote.promote(parent, ["O1v@10"], {}, llm=object())
    why = out.undetermined["O1v@10"]
    # never offered the builder; and, since 2026-11-19 (the owner), told that it was not asked
    assert why.startswith("inelastic") and "the model builder can propose" not in why
    assert why.endswith("the model builder was not asked: it is asked only for an elastic candidate with the card's "
                        "own couplings")


@pytest.mark.needs("revised_xenon")
def test_promotion_studies_a_model_again_outside_the_earlier_mass_window(tmp_path, monkeypatch):
    """Minor (after R6): completions were de-duplicated by name across masses, so a far mass was never studied."""
    pool = {"O1s@10": signal.Candidate(label="O1s@10", card_id="O1", isospin="s", mass_gev=10.0),
            "O1s@11": signal.Candidate(label="O1s@11", card_id="O1", isospin="s", mass_gev=11.0),
            "O1s@1000": signal.Candidate(label="O1s@1000", card_id="O1", isospin="s", mass_gev=1000.0)}
    request = signal.SignalRequest(experiment=SI, null_modules=[], toys=200, leaders=1, candidates=list(pool.values()))
    parent = tmp_path / "run"
    parent.mkdir()
    (parent / "result.json").write_text(signal.run(request).model_dump_json())
    monkeypatch.setattr(promote, "candidates_of", lambda r: pool)
    monkeypatch.setattr(promote, "labels_of", lambda r, w, include=False: [w])
    built = []
    monkeypatch.setattr(promote, "_study", lambda parent, result, c, origin, spec, options, fetch, under=None:
                        built.append((spec.name, c.label)) or promote.Child(label=c.label, model=spec.name,
                                                                         origin=origin, folder=str(parent / c.label)))
    out = promote.promote(parent, ["O1s@10", "O1s@11", "O1s@1000"], {"span": 4.0})
    assert {label for _, label in built} == {"O1s@10", "O1s@1000"}
    assert "whose mass window holds 11 GeV" in out.undetermined["O1s@11"]
