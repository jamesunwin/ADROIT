"""G11's gap drafting: where the core lacks a piece, an agent drafts the module and its tests, and the draft stays
in quarantine until a person reviews it (paid; opt-in).

**The quarantine.** A draft is written to ``drafts/quarantine/<name>/`` (git-ignored, outside the ``adroit``
package): the module, its tests, and ``DRAFT.md`` with its provenance (the agent, the date, the gap) and the words
"provisional: not reviewed". Nothing in ``adroit`` imports from ``drafts``, which a test checks over the whole
package. A person may run a draft's own tests (``review``), in a separate process with the draft's folder on its
path. A draft reaches a verdict only by being reviewed and moved into the package by a person, with its tests.

So every number a draft computes is provisional, and every verdict that would depend on it stays undecided with
the gap named, as before the draft.
"""

from __future__ import annotations

import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

from pydantic import Field

from adroit.core.config import child_environment
from adroit.agents.llm import StructuredLLM
from adroit.core.config import PROJECT_ROOT
from adroit.core.state import StrictModel

DEFAULT_MODEL = "claude-opus-5-5"
QUARANTINE = PROJECT_ROOT / "drafts" / "quarantine"
# A physics module and its tests come after a long reasoning: at 16,000 output tokens Opus 5.5 spent them all on
# reasoning and returned nothing (2026-10-15). A draft asks for 32,000; its client needs a request timeout of
# about ten minutes (``LLMClient(timeout_s=…)``).
DRAFT_TOKENS = 32_000

SYSTEM = """You draft one missing physics module for ADROIT, a Python 3.12 dark matter code, and its pytest tests.
The draft will be quarantined and reviewed by a physicist before any use. Return JSON for the Draft schema:
- name: a short snake_case module name;
- purpose: one paragraph, what the module computes and in which approximation;
- module_code: the module, self-contained (numpy and scipy only; no import from adroit), with Google-style
  docstrings citing the equations it implements (paper, arXiv number, equation);
- test_code: pytest tests of the module against limits and published numbers you can cite (import the module by
  its name);
- references: the papers, as "First author et al., arXiv:XXXX.XXXXX, eq. (N)";
- open_questions: what a reviewer must check (conventions, normalisations, ranges of validity).
Do not invent published numbers: a test against a published value quotes where it is printed. Return only the
JSON object."""


class Draft(StrictModel):
    """A drafted module (module docstring)."""
    name: str
    purpose: str
    module_code: str
    test_code: str
    references: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


def slug(name: str) -> str:
    """A safe folder and module name."""
    out = re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_")
    return out or "draft"


def write(draft: Draft, gap: str, model: str, root: Path = QUARANTINE) -> Path:
    """The draft's quarantine folder: the module, its tests, and DRAFT.md (module docstring)."""
    name = slug(draft.name)
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    from adroit.core.durable import write_atomic
    write_atomic(folder / f"{name}.py", draft.module_code)                    # each whole (M3)
    write_atomic(folder / f"test_{name}.py", draft.test_code)
    notes = [f"# {name} — provisional: not reviewed", "", f"Drafted by {model} on {dt.date.today().isoformat()} "
             "(ADROIT G11, gap drafting). Quarantined: nothing in `adroit` imports it, and no verdict depends on it.",
             "", f"**The gap.** {gap}", "", f"**Purpose.** {draft.purpose}", "", "**References.**",
             *[f"- {r}" for r in draft.references], "", "**For the reviewer.**",
             *[f"- {q}" for q in draft.open_questions]]
    write_atomic(folder / "DRAFT.md", "\n".join(notes) + "\n")
    return folder


def review(folder: Path, timeout: int = 600) -> tuple[bool, str]:
    """Run a draft's own tests in a separate process, the draft's folder on its path only (for a person)."""
    done = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(folder)],
                          cwd=folder, capture_output=True, text=True, timeout=timeout, env=child_environment())
    return done.returncode == 0, (done.stdout + done.stderr)[-3000:]


class GapDrafter:
    """A named gap → a quarantined draft (module docstring)."""

    def __init__(self, llm: StructuredLLM, model: str = DEFAULT_MODEL) -> None:
        self.llm, self.model = llm, model

    def run(self, gap: str, context: str = "", root: Path = QUARANTINE, run_id: str | None = None) -> Path:
        message = [{"role": "user", "content": f"The gap:\n{gap}\n\nContext from ADROIT:\n{context}"}]
        draft = self.llm.complete_structured(SYSTEM, message, Draft, model=self.model, run_id=run_id,
                                             actor="gap_drafter", max_tokens=DRAFT_TOKENS)
        return write(draft, gap, self.model, root)
