"""1.0.1 (the independent audit's V1-01, 2026-11-25): a missing runtime for the revised xenon responses
(``haxton_2022``: the Elastic folder, the Mu2e script, the Mu2e environment's interpreter) is refused by name. It had
silently become the shell model's responses under the name ``haxton_2022``, and a physical fit at the axial example's
thermal point (325.24 GeV) came back resolved with the best g_χ at 0.778 instead of 0.561, its 68% interval moved, and
no warning. An isotope without revised matrices, using the shell model by design, is unchanged."""
from types import SimpleNamespace

import pytest

from adroit.core.dm_state import DarkMatterParticle, HaloModel, NuclearModel
from adroit.core.model_spec import PhysicalFitRange
from adroit.experiments import registry
from adroit.library.interactions import registry as interactions
from adroit.parameter_space import assessment, physical_fit
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.physics import haxton

LZ = "LZ extended window (2026)"
AXIAL = Spin1Class(name="axial", kind="axial")
POINT = Point(m_chi=325.243436, m_med=1000.0, g_chi=1.105263158, g_q=0.25, g_l=0.0)


@pytest.fixture
def runtime_hidden(monkeypatch, tmp_path):
    """Only the Mu2e environment's interpreter made unavailable: the tools folder the Haxton code reads is empty."""
    real = haxton.get_settings()
    monkeypatch.setattr(haxton, "get_settings", lambda: SimpleNamespace(**{**vars(real), "tools_dir": tmp_path}))
    with pytest.raises(haxton.ResponsesUnavailable):
        haxton._paths()


def _o1(mass: float):
    particle = DarkMatterParticle(mass_gev=mass)
    return particle, interactions.resolve("O1", particle, {"c_p": 1e-8, "c_n": 1e-8})


def test_a_missing_runtime_is_refused_by_name_never_computed_as_the_shell_model(runtime_hidden) -> None:
    module = registry.load_module(LZ)
    particle, interaction = _o1(300.0)
    with pytest.raises(haxton.ResponsesUnavailable, match="fetch|Mu2e"):
        module.expected_signal(particle, interaction, HaloModel(), NuclearModel.haxton_2022)
    assert module.expected_signal(particle, interaction, HaloModel(), NuclearModel.shell_model).total_events > 0


def test_no_resolved_fit_is_published_without_the_runtime(runtime_hidden) -> None:
    module = registry.load_module(LZ)
    with pytest.raises(haxton.ResponsesUnavailable):
        physical_fit.predict(AXIAL, POINT, module, 0.5)
    with pytest.raises(haxton.ResponsesUnavailable):          # its background is calibrated with the same inputs
        physical_fit.fit(AXIAL, POINT, module, 0.5, PhysicalFitRange(low=0.0, high=1.5))
    signal = assessment.signal_at(AXIAL, POINT, module, 0.5, 0.0, experiment=LZ, halo="the search's published halo")
    assert signal.state == "unassessed" and ("Mu2e" in signal.reason or "fetch" in signal.reason)


def test_forecasts_refuse_the_revised_responses_without_their_runtime(runtime_hidden) -> None:
    from adroit.inference import forecast
    a, b = _o1(100.0), _o1(200.0)
    with pytest.raises(haxton.ResponsesUnavailable):
        forecast.separate("a", a, "b", b, "Xe")


@pytest.mark.needs("revised_xenon")
def test_with_the_runtime_the_full_input_fit_is_reproduced() -> None:
    """The audit's full-input result at 325.24 GeV: best g_χ ≈ 0.5613, q₀ ≈ 6.593, the 68% interval ≈ [0.305, 0.864]."""
    module = registry.load_module(LZ)
    fit = physical_fit.fit(AXIAL, POINT, module, 0.5, PhysicalFitRange(low=0.0, high=1.5))
    assert fit.resolved and fit.point.g_chi == pytest.approx(0.561286496, rel=1e-4)
    assert fit.q0 == pytest.approx(6.593338006, rel=1e-4)
    [region] = fit.regions
    assert (region.low, region.high) == pytest.approx((0.304531563, 0.863530186), rel=1e-3)


def test_a_study_is_refused_when_its_request_is_checked(runtime_hidden) -> None:
    """Before any calculation: the request check both signal workflows run (``_checked``) refuses, naming the runtime."""
    from adroit.orchestrator import signal, single_idea
    from adroit.parameter_space import library
    saved = single_idea.SingleIdeaRequest(experiment=LZ, spec=library.entry("alp_portal").benchmark_spec())
    with pytest.raises(haxton.ResponsesUnavailable, match="Mu2e|fetch"):
        single_idea._checked(saved)
    with pytest.raises(haxton.ResponsesUnavailable, match="Mu2e|fetch"):
        signal._checked(signal.SignalRequest(experiment=LZ))


# --- F1-01 (the follow-up audit): a partial installation is refused too, not only a missing runtime ----------------

@pytest.fixture
def elastic_copy(monkeypatch, tmp_path):
    """The installed Elastic folder seen through a private copy of links (``haxton._paths`` points at it), with the
    real Mu2e script and interpreter; a test then removes or spoils one file. The response cache stays warm."""
    real_elastic, script, python = haxton._paths()
    copy = tmp_path / "elastic"
    copy.mkdir()
    for f in real_elastic.iterdir():
        (copy / f.name).symlink_to(f)
    monkeypatch.setattr(haxton, "_paths", lambda: (copy, script, python))
    return copy


@pytest.mark.needs("revised_xenon")
@pytest.mark.parametrize("spoil", ["missing", "empty", "unreadable"])
def test_a_missing_or_spoiled_published_matrix_is_refused_by_name(elastic_copy, spoil) -> None:
    """The audit's case: ¹²⁹Xe's matrix renamed, everything else installed and the cache warm, had given a resolved fit
    at 325.24 GeV with g_χ 0.710 instead of 0.561. Now the request check, the spectrum and the fit all refuse."""
    from adroit.experiments.prescription import require_module
    from adroit.orchestrator import single_idea
    from adroit.parameter_space import library
    path = elastic_copy / "Xe129_GCN5082.txt"
    path.unlink()
    if spoil == "empty":
        path.write_text("")
    elif spoil == "unreadable":
        path.write_text("x")
        path.chmod(0)
    module = registry.load_module(LZ)
    with pytest.raises(haxton.ResponsesUnavailable, match=rf"Xe129 \({spoil}"):
        require_module(module)
    with pytest.raises(haxton.ResponsesUnavailable, match="Xe129"):
        single_idea._checked(single_idea.SingleIdeaRequest(experiment=LZ,
                                                           spec=library.entry("alp_portal").benchmark_spec()))
    with pytest.raises(haxton.ResponsesUnavailable, match="Xe129"):
        physical_fit.fit(AXIAL, POINT, module, 0.5, PhysicalFitRange(low=0.0, high=1.5))
    if path.exists():
        path.chmod(0o600)


@pytest.mark.needs("revised_xenon")
def test_isotopes_without_published_matrices_still_take_the_shell_model(elastic_copy) -> None:
    """¹²⁴Xe and ¹²⁶Xe: none is published, so none is required, and the full-input result is unchanged."""
    from adroit.experiments.prescription import PUBLISHED, require
    from adroit.physics import targets
    xenon = targets.target("Xe")
    assert {i.mass_number for i in xenon.isotopes} - set(PUBLISHED["Xe"]) == {124, 126}
    require(NuclearModel.haxton_2022, xenon)
    assert all(haxton.density_matrix_file(i) is None for i in xenon.isotopes if i.mass_number in (124, 126))


@pytest.mark.needs("revised_xenon")
def test_a_missing_mu2e_script_is_refused_even_with_a_warm_cache(monkeypatch, tmp_path) -> None:
    elastic, _, python = haxton._paths()
    monkeypatch.setattr(haxton, "_paths", lambda: (elastic, tmp_path / "mu2e.py", python))
    from adroit.experiments.prescription import require
    with pytest.raises(haxton.ResponsesUnavailable, match="Mu2e script"):
        require(NuclearModel.haxton_2022)


@pytest.mark.needs("revised_xenon")
def test_other_targets_and_their_workflows_are_checked(elastic_copy) -> None:
    """A Path 1 exclusion asking for the revised responses by name, and a forecast, check the target they compute on
    (here germanium, ⁷³Ge's matrix missing): the exclusion skips that module by name and computes nothing for it."""
    from adroit.experiments.prescription import require
    from adroit.inference import forecast
    from adroit.physics import targets
    (elastic_copy / "Ge73_GCN2850.txt").unlink()
    with pytest.raises(haxton.ResponsesUnavailable, match="Ge73"):
        require(NuclearModel.haxton_2022, targets.target("Ge"))
    require(NuclearModel.haxton_2022, targets.target("Xe"))           # xenon is complete
    a, b = _o1(100.0), _o1(200.0)
    if "Ge" in forecast.TARGETS:
        with pytest.raises(haxton.ResponsesUnavailable, match="Ge73"):
            forecast.separate("a", a, "b", b, "Xe")


def rate_call_sites(root) -> dict[tuple[str, str, str], int]:
    """Every call of the rate functions outside ``physics``: (file, enclosing function, callee) → count. A call made
    through an alias (``from … import element_rates as er``) counts under the function's own name."""
    import ast
    import collections
    found: collections.Counter = collections.Counter()
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith("physics/"):
            continue
        tree = ast.parse(path.read_text())
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        # names bound to a rate function: ``from … import element_rates [as er]``; ``responses`` only from the nuclear
        # module (RB-05: a directly imported ``responses`` had escaped)
        alias = {a.asname or a.name: a.name for node in imports if isinstance(node, ast.ImportFrom)
                 for a in node.names if a.name in ("element_rates", "differential_rate")
                 or (a.name == "responses" and (node.module or "").endswith("nuclear"))}
        # names bound to the nuclear module itself: ``from adroit.physics import nuclear [as nk]``,
        # ``import adroit.physics.nuclear as nk``
        modules = {"nuclear"} | {a.asname or a.name for node in imports if isinstance(node, ast.ImportFrom)
                                 for a in node.names if a.name == "nuclear"} | {
            a.asname for node in imports if isinstance(node, ast.Import) for a in node.names
            if a.name.endswith(".nuclear") and a.asname}

        def callee(func) -> str | None:
            if isinstance(func, ast.Name):
                return alias.get(func.id)
            if isinstance(func, ast.Attribute):
                if func.attr in ("element_rates", "differential_rate"):
                    return func.attr
                if func.attr == "responses":
                    owner = func.value
                    if (isinstance(owner, ast.Name) and owner.id in modules) or ast.unparse(owner).endswith(".nuclear"):
                        return "responses"
            return None

        def visit(node, where):
            for child in ast.iter_child_nodes(node):
                here = where
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    here = f"{where}.{child.name}" if where else child.name
                if isinstance(child, ast.Call) and (name := callee(child.func)):
                    found[(rel, where, name)] += 1
                visit(child, here)
        visit(tree, "")
    return dict(found)


def test_every_rate_call_site_outside_physics_is_a_reviewed_one() -> None:
    """The refusal sits at the workflows (``experiments.prescription``), not in ``nuclear.responses`` (which would
    invalidate every stored table: deferred to 1.0.2). So every call of the rate functions is reviewed, call site by
    call site (the repairs audit's RA-07: a file list had let a new call inside a listed file pass): a new call, a
    moved one or a second call in the same function fails here until it is reviewed and listed."""
    from pathlib import Path
    import adroit
    assert rate_call_sites(Path(adroit.__file__).parent) == REVIEWED_RATE_CALLS


def test_the_call_site_inventory_sees_a_new_call_inside_a_listed_file(tmp_path) -> None:
    """The audit's mutation: an extra unguarded call inside an already-listed module, and one through an alias."""
    import shutil
    from pathlib import Path
    import adroit
    copy = tmp_path / "adroit"
    shutil.copytree(Path(adroit.__file__).parent, copy, ignore=shutil.ignore_patterns("__pycache__"))
    target = copy / "experiments" / "cdmslite.py"
    target.write_text(target.read_text() + "\n\ndef unguarded(*a):\n    return element_rates(*a)\n"
                      "\n\nfrom adroit.experiments.base import element_rates as er\n\n\ndef aliased(*a):\n"
                      "    return er(*a)\n"
                      "\n\nfrom adroit.physics.nuclear import responses as rr\n\n\ndef imported(*a):\n"
                      "    return rr(*a)\n"
                      "\n\nimport adroit.physics.nuclear as nk\n\n\ndef module_alias(*a):\n"
                      "    return nk.responses(*a)\n"
                      "\n\nimport adroit.physics.nuclear\n\n\ndef qualified(*a):\n"
                      "    return adroit.physics.nuclear.responses(*a)\n")
    found = rate_call_sites(copy)
    assert found != REVIEWED_RATE_CALLS
    assert found[("experiments/cdmslite.py", "unguarded", "element_rates")] == 1
    assert found[("experiments/cdmslite.py", "aliased", "element_rates")] == 1
    for function in ("imported", "module_alias", "qualified"):          # RB-05: every form of ``responses``
        assert found[("experiments/cdmslite.py", function, "responses")] == 1


# Each call site and why no workflow reaches it with ``haxton_2022`` unguarded. A module's ``expected_signal`` takes
# its prescription from the workflow's request, which ``require_module`` checks in signal, single_idea and exclusion;
# the LZ extended window, the one module whose own conventions are ``haxton_2022``, also checks itself. CDMSlite's
# ``official_limit`` and the historical searches' ``equivalent_exposure`` use the module's own conventions (Helm or
# shell); DEAP's ``_events`` is reached through its ``expected_signal``; the forecasts check every target first;
# the degeneracy shape uses the shell model by default and no caller passes ``haxton_2022``.
REVIEWED_RATE_CALLS = {
    ("experiments/cdmslite.py", "CdmsliteRun2.expected_signal", "element_rates"): 1,
    ("experiments/cdmslite.py", "CdmsliteRun2.official_limit", "element_rates"): 1,
    ("experiments/cresst_iii.py", "CresstIII2019.expected_signal", "element_rates"): 1,
    ("experiments/deap3600.py", "Deap3600._events", "element_rates"): 1,
    ("experiments/historical.py", "HistoricalSearch.equivalent_exposure", "element_rates"): 1,
    ("experiments/historical.py", "HistoricalSearch.expected_signal", "element_rates"): 1,
    ("experiments/lz_extended_window.py", "LzExtendedWindow.expected_signal", "element_rates"): 1,
    ("experiments/pico60.py", "Pico60.expected_signal", "element_rates"): 1,
    ("experiments/xenon.py", "DiamxXenon.expected_signal", "element_rates"): 1,
    ("inference/forecast.py", "target_spectrum", "differential_rate"): 1,
    ("library/interactions/degeneracy.py", "shape", "differential_rate"): 1,
}
