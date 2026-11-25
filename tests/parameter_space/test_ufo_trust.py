"""R1: a UFO portal read from a file is data. Its parameters are arithmetic and its folder a packaged model."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from adroit.parameter_space import resonances
from adroit.parameter_space.classes import Point
from adroit.parameter_space.library import INERT_DOUBLET, TWO_HDM_A
from adroit.parameter_space.portals import ufo
from adroit.parameter_space.portals.ufo import UFOPortal

PAYLOAD = ("([c for c in ().__class__.__base__.__subclasses__() if c.__name__=='_wrap_close'][0]"
           ".__init__.__globals__['mkdir']('/tmp/adroit_should_not_exist'), 1/0)[1]")


def test_the_packaged_portals_and_their_copies_are_accepted_and_evaluate_as_before() -> None:
    p = Point(m_chi=990.0, m_med=998.12, g_chi=-0.051, g_q=2.36)
    x = INERT_DOUBLET._overrides(p)
    assert x["mmH0"] == 990.0 and x["lamL"] == pytest.approx(-0.0255) and x["mmA0"] == pytest.approx(992.36)
    copy = resonances._reference(TWO_HDM_A, 0.35, 1200.0)
    y = copy._overrides(Point(m_chi=10.0, m_med=400.0, g_chi=1.0, g_q=0.7, g_l=1.0))
    assert y["sinp"] == 0.35 and y["mh2"] == 1200.0 and y["mh4"] == 400.0
    assert UFOPortal.model_validate(TWO_HDM_A.model_dump(mode="json")) == TWO_HDM_A


@pytest.mark.parametrize("parameters", [{"MX": PAYLOAD}, {"MX": "__import__('os')"}, {"MX": "m_chi.real"},
                                        {"MX": "open('x')"}, {"not a name": "m_chi"}])
def test_a_parameter_that_is_not_arithmetic_is_refused_when_the_portal_is_read(parameters: dict) -> None:
    data = {**INERT_DOUBLET.model_dump(mode="json"), "parameters": parameters}
    with pytest.raises(ValidationError):
        UFOPortal.model_validate(data)


@pytest.mark.parametrize("folder", ["nonexistent_ufo", "../evil", "/tmp/evil", "ufo/../../evil", "ufo/Other_UFO"])
def test_only_the_packaged_model_folders_are_accepted(folder: str) -> None:
    with pytest.raises(ValidationError):
        UFOPortal.model_validate({**INERT_DOUBLET.model_dump(mode="json"), "model_dir": folder})


def test_a_model_folder_that_links_outside_the_ufo_folder_is_refused(tmp_path, monkeypatch) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (tmp_path / "tools" / "ufo").mkdir(parents=True)
    (tmp_path / "tools" / "ufo" / "InertDoublet_UFO").symlink_to(outside)
    monkeypatch.setattr(ufo, "get_settings", lambda: SimpleNamespace(tools_dir=tmp_path / "tools"))
    with pytest.raises(ValueError, match="resolves outside"):
        INERT_DOUBLET.model_path()
    (tmp_path / "tools" / "ufo" / "InertDoublet_UFO").unlink()
    (tmp_path / "tools" / "ufo" / "InertDoublet_UFO").mkdir()
    assert INERT_DOUBLET.model_path() == (tmp_path / "tools" / "ufo" / "InertDoublet_UFO").resolve()


def test_a_copy_that_skips_validation_still_cannot_run_code_or_leave_the_library() -> None:
    p = Point(m_chi=10.0, m_med=500.0)
    with pytest.raises(ValueError):
        INERT_DOUBLET.model_copy(update={"parameters": {"MX": PAYLOAD}})._overrides(p)
    with pytest.raises(ValueError, match="packaged"):
        INERT_DOUBLET.model_copy(update={"model_dir": "../evil"}).model_path()


def test_no_eval_remains_in_the_portal_module() -> None:
    import inspect
    assert "eval(" not in inspect.getsource(ufo)
