"""The workbench typesets a model with the local TeX installation, sandboxed and cached (the owner, 2026-10-13)."""

import pytest

from adroit.model_building import display
from adroit.ui import typeset

needs_tex = pytest.mark.skipif(not typeset.available(), reason="no TeX installation (latex, dvisvgm)")


@needs_tex
def test_a_model_is_typeset_to_svg_and_cached(tmp_path):
    from adroit.parameter_space import library
    source = display.document(library.entry("dmwg_V1").spec())
    text, why = typeset.svg(source, tmp_path)
    assert why == "" and text.lstrip().startswith("<?xml") and "<svg" in text
    assert len(list(tmp_path.glob("*.svg"))) == 1 and typeset.svg(source, tmp_path) == (text, "")
    assert typeset.img(text).startswith('<img src="data:image/svg+xml;base64,')


@needs_tex
def test_typesetting_cannot_read_files_outside_its_folder(tmp_path):
    secret = tmp_path / "secret.tex"
    secret.write_text("SECRET")
    source = "\\documentclass{standalone}\\begin{document}\\input{" + str(secret) + "}\\end{document}"
    text, why = typeset.svg(source, tmp_path / "cache")
    assert text is None and why


def test_without_tex_the_reason_is_given(tmp_path, monkeypatch):
    monkeypatch.setattr(typeset, "_tool", lambda name: None)
    assert typeset.svg("anything", tmp_path) == (None, "no TeX installation found (latex and dvisvgm), so the source "
                                                      "is shown")


@needs_tex
def test_every_library_model_typesets(tmp_path):
    """The dark-photon models had failed with a double subscript (X_d's index): every standard model must compile."""
    from adroit.parameter_space import library
    failed = {e.id: why for e in library.ENTRIES
              for text, why in [typeset.svg(display.document(e.spec()), tmp_path)] if text is None}
    assert failed == {}
