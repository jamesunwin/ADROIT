"""LaTeX typeset for the workbench (the owner, 2026-10-13): a document compiled by the local TeX installation
(``latex``, then ``dvisvgm``) into an SVG, cached by the document's hash.

The compilation is sandboxed: no shell escape, files read and written only inside its temporary folder
(``openin_any``/``openout_any`` = p), and a time limit. Without TeX the caller shows the source instead.
"""

from __future__ import annotations

import base64
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

TEX_DIRS = ("/Library/TeX/texbin", "/usr/local/texlive/2026/bin/universal-darwin", "/opt/homebrew/bin",
            "/usr/local/bin", "/usr/bin")
TIMEOUT_S = 30


def _tool(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    return next((str(Path(d) / name) for d in TEX_DIRS if (Path(d) / name).is_file()), None)


def available() -> bool:
    """Whether ``latex`` and ``dvisvgm`` are installed."""
    return bool(_tool("latex") and _tool("dvisvgm"))


def svg(document: str, cache: Path) -> tuple[str | None, str]:
    """The document typeset as SVG text, and '' — or None and why it could not be."""
    key = hashlib.sha256(document.encode()).hexdigest()
    cached = cache / f"{key}.svg"
    if cached.is_file():
        return cached.read_text(), ""
    latex, dvisvgm = _tool("latex"), _tool("dvisvgm")
    if not (latex and dvisvgm):
        return None, "no TeX installation found (latex and dvisvgm), so the source is shown"
    from adroit.core.config import child_environment
    env = child_environment({"openin_any": "p", "openout_any": "p", "shell_escape": "f"})   # no credential (AL3-27)
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        (work / "model.tex").write_text(document)
        try:
            run = subprocess.run([latex, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "model.tex"],
                                 cwd=work, env=env, capture_output=True, text=True, timeout=TIMEOUT_S)
            if run.returncode != 0:
                errors = [line for line in run.stdout.splitlines() if line.startswith("!")]
                return None, "LaTeX could not typeset it: " + ("; ".join(errors[:3]) or f"exit {run.returncode}")
            run = subprocess.run([dvisvgm, "-n", "-e", "-o", "model.svg", "model.dvi"], cwd=work, env=env,
                                 capture_output=True, text=True, timeout=TIMEOUT_S)
            if run.returncode != 0 or not (work / "model.svg").is_file():
                return None, "dvisvgm could not convert it: " + (run.stderr.strip().splitlines() or ["no output"])[-1]
        except subprocess.TimeoutExpired:
            return None, f"typesetting took longer than {TIMEOUT_S} s"
        text = (work / "model.svg").read_text()
    cache.mkdir(parents=True, exist_ok=True)
    cached.write_text(text)
    return text, ""


def img(svg_text: str) -> str:
    """An <img> of the SVG as a data URI (scripts inside an SVG image never run)."""
    data = base64.b64encode(svg_text.encode()).decode()
    return f'<img src="data:image/svg+xml;base64,{data}" style="max-width:100%;height:auto" alt="typeset model">'


def show_model(spec, cache: Path | None = None) -> None:
    """A model as a physicist reads it: its field content and Lagrangian typeset by TeX (``display.document``), or
    the TeX source with the reason when it cannot be typeset."""
    from nicegui import ui

    from adroit.core.config import get_settings
    from adroit.model_building.display import document
    source = document(spec)
    text, why = svg(source, cache or get_settings().runs_dir / ".typeset")
    if text:
        ui.html(img(text), sanitize=False).classes("w-full")
        return
    ui.label(f"Typeset view unavailable: {why}.").classes("text-orange-700")
    ui.code(source, language="latex").classes("w-full")
